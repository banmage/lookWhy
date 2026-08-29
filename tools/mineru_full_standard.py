#!/usr/bin/env python3
"""Resumable full MinerU extraction and SSIR/PDF comparison workflow.

The tool deliberately uses MinerU's complete pipeline backend.  It divides a
long PDF into page ranges only to make CPU runs restartable; every range still
enables layout analysis, OCR, formulas, and tables.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any

from leleby_ssir.mineru_html import convert_mineru_markup, formula_assets_index
from leleby_ssir.naming import standard_filename, standard_number_from_text


ROOT = Path(__file__).resolve().parents[1]


def _log(message: str) -> None:
    print(f"[{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}", flush=True)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def _mineru_command() -> str:
    local = Path(sys.prefix) / "bin" / "mineru"
    if local.is_file() and local.stat().st_mode & 0o111:
        return str(local)
    found = shutil.which("mineru")
    if found:
        return found
    raise RuntimeError("MinerU is not installed in the active environment. Install mineru first.")


def _page_count(pdf: Path) -> int:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to count and compare PDF pages.") from exc
    with fitz.open(pdf) as document:
        return len(document)


# Generic helpers shared with the PDF extractor: these recognise common Chinese
# national/industry standard-number prefixes (GB, GB/T, DB, QB, JB, DL, NY, ISO)
# and are deliberately not specific to GB/T 1.1-2020.  The implementations live
# in src/leleby_ssir/naming.py (single source of truth for the naming scheme).
def _usable_title(text: str, fallback: str) -> str:
    # 规则对应: GBT-C01（封面必备信息——文件名称）；损坏字体解码兜底。
    compact = " ".join(text.split())
    # Broken embedded CJK fonts often decode as repeated mathematical letters.
    if not compact or sum(1 for char in compact if "犀" <= char <= "犿") > 4:
        return fallback
    return compact[:180]


def _is_gbt_1_1_2020(source: Path) -> bool:
    """True for the GB/T 1.1-2020 input that the standard-specific quirk fixes target.

    规则对应: GBT-* 专属修复开关（仅对 GB/T 1.1-2020 输入启用 7.4 版式图恢复等 quirks）。
    """
    return "1.1-2020" in source.stem or "1.1—2020" in source.stem


def _range_dir(output_dir: Path, start: int, end: int) -> Path:
    return output_dir / "parts" / f"pages-{start + 1:03d}-{end + 1:03d}"


def _stage_paths(output_dir: Path, stem: str) -> dict[str, Path]:
    """阶段目录布局（naming_specification.txt 第 4 节）：每个表示一个子目录。

    00_source/ 01_extract/ 02_canonical/ 03_ssir/ 04_render/ 05_verify/；
    资产统一放文档根 assets/（SSIR 的 assetRef 相对路径以
    ``assets/images/...`` 引用，渲染器自 03_ssir/ 向上查找）。
    """
    return {
        "source": output_dir / "00_source" / f"{stem}.source.pdf",
        "checksum": output_dir / "00_source" / f"{stem}.checksum.sha256",
        "raw": output_dir / "01_extract" / f"{stem}.raw.md",
        "extract_report": output_dir / "01_extract" / f"{stem}.extract-report.json",
        "provenance": output_dir / "01_extract" / f"{stem}.provenance.json",
        "canonical": output_dir / "02_canonical" / f"{stem}.canonical.md",
        "normalize_report": output_dir / "02_canonical" / f"{stem}.normalize-report.json",
        "ssir": output_dir / "03_ssir" / f"{stem}.ssir.json",
        "parse_report": output_dir / "03_ssir" / f"{stem}.parse-report.json",
        "render_pdf": output_dir / "04_render" / f"{stem}.render.pdf",
        "render_md": output_dir / "04_render" / f"{stem}.render.md",
        "render_report": output_dir / "04_render" / f"{stem}.render-report.json",
        "render_comparison": output_dir / "04_render" / f"{stem}.render-comparison.json",
        "verify": output_dir / "05_verify" / f"{stem}.verify.json",
        "roundtrip": output_dir / "05_verify" / f"{stem}.roundtrip.json",
    }


def _write_manifest(args: argparse.Namespace, state: dict[str, Any], title: str = "", number: str = "", status: str = "in-progress") -> None:
    """写文档索引 manifest.json（naming_specification.txt 第 6 节）。"""
    stem = args.output_stem or args.input.stem
    paths = _stage_paths(args.output_dir, stem)
    manifest: dict[str, Any] = {
        "documentId": stem,
        "title": title or state.get("title", ""),
        "standardNumber": number or state.get("number", ""),
        "status": status,
        "created": state.get("createdAt"),
        "updated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": {
            "originalFile": str(args.input.resolve()),
            "checksum": f"sha256:{state.get('sourceSha256', '')}",
        },
        "pipeline": {
            "raw": str(paths["raw"].relative_to(args.output_dir)),
            "canonical": str(paths["canonical"].relative_to(args.output_dir)),
            "ssir": str(paths["ssir"].relative_to(args.output_dir)),
            "renderMd": str(paths["render_md"].relative_to(args.output_dir)),
            "render": str(paths["render_pdf"].relative_to(args.output_dir)),
            "verify": str(paths["verify"].relative_to(args.output_dir)),
            "roundtrip": str(paths["roundtrip"].relative_to(args.output_dir)),
        },
        "stages": {
            name: str(path.relative_to(args.output_dir)) if path.exists() else None
            for name, path in paths.items()
        },
    }
    _write_json(args.output_dir / "manifest.json", manifest)


def _mineru_markdown(part_dir: Path) -> Path | None:
    candidates = sorted(part_dir.rglob("*.md"), key=lambda path: path.stat().st_size, reverse=True)
    return candidates[0] if candidates else None


def _extract_cover_badge(source_pdf: Path, output_dir: Path, standard_number: str = "") -> str | None:
    """Extract the cover "GB" emblem image from page 1 into an asset.

    规则对应: GEN-018（封面徽标图片恢复，should）。

    MinerU only recognises the emblem as an oversized header text block; the
    emblem itself is a raster image embedded in the source PDF.  The largest
    top-of-page image is recovered so rendering can place it back.
    Returns the asset path relative to the output directory, or None.

    Enterprise standards (Q/) and group standards (T/) do not carry the GB
    emblem — their covers may contain a company logo or a product photo, which
    must NOT be cropped and drawn as a fake national emblem (GBT-L02 文件代号
    美术体字仅适用于国家/行业标准封面).
    """
    if re.match(r"^Q\s*/", standard_number.upper()) or re.match(r"^T\s*/", standard_number.upper()):
        return None
    try:
        import fitz  # type: ignore

        with fitz.open(source_pdf) as document:
            page = document[0]
            blocks = [
                block for block in page.get_text("dict")["blocks"]
                if block.get("type") == 1 and block.get("bbox")
            ]
            if not blocks:
                return None
            # The GB emblem is the widest image block in the upper half of
            # the cover (classification codes and body images sit lower).
            upper = [b for b in blocks if b["bbox"][1] < page.rect.height / 2]
            best = max(upper or blocks, key=lambda b: (b["bbox"][2] - b["bbox"][0]) * (b["bbox"][3] - b["bbox"][1]))
            rect = fitz.Rect(best["bbox"])
            pix = page.get_pixmap(clip=rect, matrix=fitz.Matrix(200 / 72, 200 / 72))
        target = output_dir / "assets" / "images" / "cover-gb-badge.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        pix.save(str(target))
        return "assets/images/cover-gb-badge.png"
    except Exception as exc:  # pragma: no cover - best-effort recovery
        _log(f"Warning: unable to recover cover GB badge: {exc}")
        return None


def _classification_codes(part_dir: Path) -> dict[str, str]:
    """Recover ICS/CCS codes from MinerU's content list for a part.

    规则对应: GEN-011（分类号行识别，gbt11-ref 10.3.1.5/8.1）+ GEN-010
    （页眉页脚内容回收）。

    MinerU classifies the cover-top ``ICS ... CCS ...`` line as a page header
    and drops it from the Markdown output (headers land in discarded_blocks).
    The content_list.json keeps those blocks, so the cover classification
    codes are recovered from there instead of being lost.
    """
    candidates = sorted(part_dir.rglob("*_content_list.json"))
    if not candidates:
        return {}
    try:
        entries = json.loads(candidates[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    codes: dict[str, str] = {}
    for item in entries:
        if item.get("type") not in {"header", "footer", "page-header", "page_footer", "text"}:
            continue
        text = str(item.get("text") or item.get("content") or "")
        # Normalise whitespace so OCR variants like "ICS01.\n120" or
        # "ICS01120 A00" still match the classification-code shape.
        compact = re.sub(r"\s+", " ", text)
        m_ics = re.search(r"ICS\s*([0-9]+(?:\.[0-9]+){0,3})", compact, re.I)
        if m_ics:
            codes.setdefault("ics", _normalize_ics(m_ics.group(1)))
        # CCS usually shares the ICS line ("ICS 01.120 CCS A 00"); tolerate
        # OCR spacing variants like "CCS  K  24".  The whole line may start
        # with ICS, so CCS is matched independently, not gated on the line
        # not starting with ICS.
        m_ccs = re.search(r"CCS\s*([A-Z])\s*(\d{1,2})\b", compact, re.I)
        if m_ccs:
            codes.setdefault("ccs", f"{m_ccs.group(1).upper()} {m_ccs.group(2)}")
        else:
            # Standalone "<字母><编号>" line without a CCS prefix (e.g. "A 00").
            m_ccs2 = re.search(r"^\s*([A-Z])\s*(\d{1,2})\s*$", compact, re.I)
            if m_ccs2:
                codes.setdefault("ccs", f"{m_ccs2.group(1).upper()} {m_ccs2.group(2)}")
            elif m_ics:
                # "ICS01120 A00": the CCS rides the same line without a CCS
                # prefix, as a trailing "<字母><编号>" token after the ICS
                # number (OCR drops the spaces and the CCS label).
                m_ccs3 = re.search(r"\b([A-Z])\s?(\d{1,2})\s*$", compact, re.I)
                if m_ccs3 and m_ccs3.start() > m_ics.end():
                    codes.setdefault("ccs", f"{m_ccs3.group(1).upper()} {m_ccs3.group(2)}")
    return codes


def _normalize_ics(raw: str) -> str:
    """Normalise an ICS number, restoring dots lost to OCR line breaks.

    规则对应: GEN-011（分类号行识别与 ICS 编号恢复，OCR 丢失小数点时重排）。

    ``01.120`` may arrive as ``01120`` (dot swallowed) or split across lines.
    Split the digit run into the ICS field pattern: first field 1-2 digits,
    following fields 3 digits each (e.g. ``01120`` -> ``01.120``).
    """
    if "." in raw:
        return raw
    if len(raw) > 2 and len(raw) % 3 == 2:  # 2 + n*3 digits
        return ".".join([raw[:2], *[raw[i:i + 3] for i in range(2, len(raw), 3)]])
    return raw


def _looks_like_document_number(text: str) -> bool:
    """True for cover code lines ("GB/T 1.1—2020", "ICS01.120 CCS A 00") that
    must never be mistaken for English-title text.

    规则对应: GEN-016（英文标题识别的前置过滤）+ GEN-011/GEN-012（分类号、文件编号行）。
    """
    compact = re.sub(r"\s+", "", text)
    return bool(
        (
            re.match(r"^[A-Z]{1,4}", compact)
            and re.search(r"\d{2,4}$", compact)
            and re.search(r"[—\-.]\d", compact)
        )
        or bool(re.match(r"ICS", compact, re.I))
        or bool(re.search(r"CCS", compact, re.I))
    )


def _cover_metadata(part_dir: Path, markdown_text: str) -> dict[str, str]:
    """Recover cover-only fields (English title, dates, issuer) for the front matter.

    规则对应: GEN-013（发布/实施日期识别）、GEN-014（发布机构识别）、
    GEN-015（代替文件编号）、GEN-016（英文标题识别）、GEN-017（一致性
    程度标识）、GEN-019（显式 front-matter 优先）；缺失项由 GBT-C01 在
    合规验证中记 finding、渲染时以 "××" 占位。

    MinerU's Markdown keeps the Chinese title but the cover publication block
    (发布/实施 dates and the issuing body) is either scattered as bare text or
    dropped with page footers, so it is recovered from the content list and
    the first-page Markdown.  Only page-0 entries are considered so that
    later occurrences in the body (e.g. 前言) do not shadow the cover values.
    """
    result: dict[str, str] = {}
    # Replaced standard ("代替 GB/T ...—....") from the cover text.  OCR/文本层
    # 可能不带空格（"代替GB/T23132—2008"），所以 \s* 而非 \s+；只扫描封面块
    # （第一个 heading 之前），避免正文以"代替…"开头的行（如"代替了…"）误命中。
    cover_lines = markdown_text.splitlines()
    for idx, line in enumerate(cover_lines):
        if line.lstrip().startswith("#"):
            cover_lines = cover_lines[:idx]
            break
    for line in cover_lines:
        match = re.match(r"^代替\s*(.+)$", line.strip())
        if match:
            result.setdefault("replaces", match.group(1).strip())
            break
    # English title: the consecutive English-only lines following the Chinese
    # title on the cover (handled below from the content list, which keeps
    # every English line regardless of Markdown heading treatment).
    # English title and adoption statement are recovered from the content
    # list below (see the consecutive-English-line rule).
    # Publication block from the page-0 content list entries.
    # English title and adoption statement: taken from the page-0 content
    # list entries (ordered by vertical position).  All consecutive
    # English-only lines that follow the Chinese title form the English
    # title (a standard may carry a name plus a part subtitle); a
    # parenthesized line naming the adopted international document is the
    # conformity statement.  Both rules are generic — no per-standard text.
    candidates = sorted(part_dir.rglob("*_content_list.json"))
    if not candidates:
        return result
    try:
        entries = json.loads(candidates[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return result

    def _is_english_line(text: str) -> bool:
        # 规则对应: GEN-016（英文标题识别：连续仅拉丁字符行）。
        # The em dash (—) is a legitimate title separator ("Rules for drafting
        # standards — Part 10: ...") but OCR often strips the spaces around it.
        return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9 ,.:;()'’/\\—\-]+", text.strip())) and len(text.strip()) > 3

    english_parts: list[str] = []
    seen_title = False
    for item in sorted(
        (item for item in entries if item.get("page_idx") in (0, None)),
        key=lambda item: float((item.get("bbox") or [0, 0, 0, 0])[1]),
    ):
        # 文本层 PDF 的机构行常被 MinerU 表示为逐字 <sup>…</sup> span
        # （如 "<sup>国</sup> <sup>家</sup> <sup>市</sup>…"），先去标签再
        # 处理，否则机构名录/日期/英文标题的连续子串匹配全被打断。
        text = re.sub(r"<[^>]+>", "", str(item.get("text") or item.get("content") or "").strip())
        if not text or re.match(r"^\d{4}-\d{2}-\d{2}", text):
            continue
        if re.search(r"[\u3400-\u9fff]", text):
            # The cover banner ("<……>标准", e.g. 国家/行业/地方/团体/企业标准)
            # marks where English lines may begin; a later Chinese line ends
            # the English-title run.  The issuing-body footer (发布机构 + 发布)
            # also contains Han characters and must not be treated as the
            # Chinese title.
            compact = re.sub(r"\s+", "", text)
            if "发布" in compact or "实施" in compact:
                continue
            if english_parts:
                break
            if not seen_title and re.search(r"标准$", compact) and len(compact) >= 6:
                seen_title = True
            continue
        adoption = re.fullmatch(r"\((.+)\)", text)
        if adoption and re.search(r"ISO|IEC|EN|ASTM|IEEE", adoption.group(1), re.I):
            result.setdefault("conformity-statement", text)
            continue
        if _is_english_line(text) and not _looks_like_document_number(text) and (seen_title or english_parts):
            english_parts.append(text)
    if not english_parts:
        # Fallback: read the cover English title straight from the PDF text
        # layer (MinerU may mangle spacing/case but the raw layer keeps it).
        english_parts = _cover_english_from_pdf(part_dir)
    if english_parts:
        result.setdefault("title-en", _tidy_english_title(" ".join(english_parts)))

    page0 = sorted(
        (item for item in entries if item.get("page_idx") in (0, None)),
        key=lambda item: float((item.get("bbox") or [0, 0, 0, 0])[1]),
    )
    prev_footer: str = ""
    for item in page0:
        text = re.sub(r"<[^>]+>", "", str(item.get("text") or item.get("content") or "").strip())
        # OCR may split the word ("发 布") and fuse both bodies into one footer
        # line, so compare on whitespace-stripped text.
        compact_line = re.sub(r"\s+", "", text)
        issued = re.match(r"^(\d{4}-\d{2}-\d{2})\s*发布", compact_line)
        effective = re.match(r"^(\d{4}-\d{2}-\d{2})\s*实施", compact_line)
        if issued:
            result.setdefault("publication-date", issued.group(1))
        if effective:
            result.setdefault("effective-date", effective.group(1))
        if "发布" in compact_line and not issued and not effective:
            issuer_text = compact_line
            if compact_line == "发布" and prev_footer:
                # MinerU splits "<机构>发布" into a footer line (机构名) and a
                # bare "发布" line (page_number); merge them so the issuer
                # resolves instead of being reported missing (GBT-C01).
                issuer_text = prev_footer + "发布"
            issuer = _canonical_issuer(issuer_text)
            if issuer:
                result.setdefault("issuer", issuer)
        # Remember the most recent footer-like CJK line (机构名) so a later
        # standalone "发布" line can be merged with it.
        if (
            re.search(r"[\u3400-\u9fff]", compact_line)
            and not issued
            and not effective
            and "发布" not in compact_line
            and not re.match(r"^\d{4}-\d{2}-\d{2}", compact_line)
            and not _is_cover_banner(compact_line)
        ):
            prev_footer = compact_line
    # 机构行兜底：content_list 的 issuer 若只命中通用回退（OCR 常把机构名
    # 识别错，如"国家督管理委员 局会 发 布"），用原 PDF 文本层重取——文本层
    # 对封面字段可靠，命中机构名录才覆盖。
    if result.get("issuer") and not _canonical_issuer_known(result["issuer"]):
        pdf_issuer = _cover_issuer_from_pdf(part_dir)
        if pdf_issuer:
            result["issuer"] = pdf_issuer
    return result


def _cover_english_from_pdf(part_dir: Path) -> list[str]:
    """Read consecutive cover English-title lines from the PDF raw text layer.

    规则对应: GEN-016（英文标题识别，PDF 文本层兜底）。

    MinerU's OCR sometimes mangles the English title (dropped spaces, lost
    separators); the PDF text layer keeps the original characters.  Returns
    the run of Latin-only lines between the Chinese banner block and the
    publication dates.
    """
    markdown_candidates = sorted(part_dir.rglob("*.md"), key=lambda p: p.stat().st_size, reverse=True)
    pdf_candidates = sorted(part_dir.rglob("*.pdf"))
    if not markdown_candidates or not pdf_candidates:
        return []
    try:
        import pymupdf

        with pymupdf.open(pdf_candidates[0]) as doc:
            page0_text = doc[0].get_text()
    except Exception:
        return []
    lines = [line.strip() for line in page0_text.splitlines() if line.strip()]
    english: list[str] = []
    seen_banner = False
    for line in lines:
        compact = re.sub(r"\s+", "", line)
        if re.search(r"[\u3400-\u9fff]", compact):
            if english:
                break
            if re.search(r"标准$", compact) and len(compact) >= 6:
                seen_banner = True
            continue
        if re.match(r"^\d{4}-\d{2}-\d{2}", compact):
            break
        if (
            seen_banner
            and not _looks_like_document_number(line)
            and re.fullmatch(r"[A-Za-z][A-Za-z0-9 ,.:;()'’/\\—\-]+", line)
        ):
            english.append(line)
    return english


def _tidy_english_title(text: str) -> str:
    """Restore word spacing lost by OCR/font-embedding in an English title.

    规则对应: GEN-016（英文标题识别/去粘连修复，字典分割兜底）。

    Some PDFs store the title with no space glyphs ("Rulesfordrafting…").
    Two generic, order-dependent repairs:
    1. camel-case joins: a space between a lowercase letter and the following
       uppercase letter never hurts well-spaced text;
    2. dictionary segmentation: greedily split glued all-lowercase runs using
       the system word list (/usr/share/dict/words).  Applied only to tokens
       that the dictionary cannot find as-is, so correct text is untouched;
       if segmentation fails the original token is kept.
    """
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    lexicon = _system_word_list()
    if not lexicon:
        return re.sub(r"\s+", " ", spaced).strip()

    def repair(match: re.Match[str]) -> str:
        run = match.group(0)
        if len(run) < 10 or run.lower() in lexicon:
            return run
        return _segment_word(run.lower(), lexicon) or run

    # Segment each glued alphabetic run (>=10 letters, unknown to the
    # dictionary); digits and punctuation act as natural separators.
    repaired = re.sub(r"[A-Za-z]{10,}", repair, spaced)
    return re.sub(r"\s+", " ", repaired).strip()


def _system_word_list() -> set[str]:
    for candidate in ("/usr/share/dict/words", "/usr/share/dict/american-english"):
        try:
            return {line.strip().lower() for line in open(candidate, encoding="utf-8") if line.strip().isalpha()}
        except OSError:
            continue
    return set()


def _segment_word(word: str, lexicon: set[str]) -> str | None:
    """Greedy dynamic-programming split of a glued lowercase word."""
    n = len(word)
    best: list[list[str] | None] = [None] * (n + 1)
    best[0] = []
    max_len = min(24, n)
    for i in range(1, n + 1):
        for j in range(max(0, i - max_len), i - 2):
            previous = best[j]
            if previous is not None and word[j:i] in lexicon:
                candidate: list[str] = [*previous, word[j:i]]
                current = best[i]
                if current is None or len(candidate) < len(current):
                    best[i] = candidate
    result = best[n]
    return " ".join(result) if result else None


# Issuing bodies for national / industry / local / enterprise standards
# (GBT-C01 封面必备信息——发布机构).  Keyed by distinctive fragments of the
# cover footer ("<机构>发布"); deliberately generic so GB、JB/QB/DL/NY 等行业
# 标准、DB 地方标准与企业标准都能映射到规范全称。
_ISSUER_FRAGMENTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("质量监督", "质检"), "中华人民共和国国家质量监督检验检疫总局 中国国家标准化管理委员会"),
    (("市场监督", "标督管"), "国家市场监督管理总局 国家标准化管理委员会"),
    (("工业和信息化", "工信部", "机械行业", "机 行 业"), "中华人民共和国工业和信息化部"),
    (("住房和城乡建设", "住建部"), "中华人民共和国住房和城乡建设部"),
    (("交通运输", "交通部"), "中华人民共和国交通运输部"),
    (("水利部", "水利行业"), "中华人民共和国水利部"),
    (("农业农村", "农业部"), "中华人民共和国农业农村部"),
    (("卫生健康", "卫生部"), "中华人民共和国国家卫生健康委员会"),
    (("应急管理", "安监总局"), "中华人民共和国应急管理部"),
    (("生态环境", "环保部", "环境保护"), "中华人民共和国生态环境部"),
    (("文化和旅游", "文化部"), "中华人民共和国文化和旅游部"),
    (("市场监管总局",), "国家市场监督管理总局"),
    (("能源局", "能源行业"), "中华人民共和国国家能源局"),
    (("民航局",), "中国民用航空局"),
    (("轻工行业", "轻工业联合会"), "中国轻工业联合会"),
    (("纺织工业", "纺织行业"), "中国纺织工业联合会"),
    (("钢铁工业",), "中国钢铁工业协会"),
    (("电力行业", "中电联"), "中国电力企业联合会"),
    (("煤炭工业",), "中国煤炭工业协会"),
    (("石油化工", "石化行业"), "中国石油和化学工业联合会"),
    (("建筑材料", "建材行业"), "中国建筑材料联合会"),
    (("有色金属",), "中国有色金属工业协会"),
    (("包装行业",), "中国包装联合会"),
    (("物流与采购", "物流行业"), "中国物流与采购联合会"),
)


def _canonical_issuer(text: str) -> str:
    # 规则对应: GEN-014（发布机构识别与规范名称映射——通用机构名录，
    # 覆盖国家标准/行业标准/地方标准/企业标准发布机构）。
    compact = re.sub(r"\s+", "", text)
    for fragments, canonical in _ISSUER_FRAGMENTS:
        if any(fragment in compact for fragment in fragments):
            return canonical
    # Generic fallback: "<机构名>发布" — keep the body verbatim so enterprise
    # standards (企业标准 Q/…) whose issuer is an arbitrary company name still
    # resolve instead of being reported missing (GBT-C01).
    match = re.match(r"^([\u3400-\u9fff（）()·A-Za-z0-9\-]{4,40}?)发布$", compact)
    if match:
        return match.group(1)
    return ""


def _canonical_issuer_known(text: str) -> str:
    """Canonical issuer only when a known fragment matches; '' for the
    generic verbatim fallback (which may be OCR-garbled)."""
    compact = re.sub(r"\s+", "", text)
    for fragments, canonical in _ISSUER_FRAGMENTS:
        if any(fragment in compact for fragment in fragments):
            return canonical
    return ""


def _cover_issuer_from_pdf(part_dir: Path) -> str:
    """Recover the cover issuer from the PDF raw text layer (GEN-014 兜底).

    OCR 常把机构行识别错（"国家督管理委员 局会 发 布"），而原 PDF 文本层
    对封面字段可靠。pymupdf 会把 "<机构A>\\n<机构B>\\n发布" 拆成多行，
    从"发布"行向上合并相邻机构行再查机构名录。
    """
    pdf_candidates = sorted(part_dir.rglob("*.pdf"))
    if not pdf_candidates:
        return ""
    try:
        import pymupdf

        with pymupdf.open(pdf_candidates[0]) as doc:
            page0_text = doc[0].get_text()
    except Exception:
        return ""
    lines = [re.sub(r"\s+", "", line) for line in page0_text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if "发布" in line and not re.match(r"^\d{4}-\d{2}-\d{2}", line):
            parts = [line]
            j = i - 1
            while j >= 0 and not re.search(r"发布|实施|^20\d\d-\d\d-\d\d|标准$", lines[j]):
                parts.insert(0, lines[j])
                j -= 1
            issuer = _canonical_issuer_known("".join(parts))
            if issuer:
                return issuer
    return ""


def _recover_annex_headings(markdown: str) -> str:
    """Rebuild annex headings that MinerU split into bare paragraphs.

    规则对应: GEN-030（附录标题重组：编号行 + 性质行 + 标题行合并）。

    MinerU emits the annex header as three consecutive paragraphs
    ("附录A" / "(规范性)" / "外形及安装尺寸"), which the CSM parser treats as
    plain body text, so no annex chapter is created and A.1-style clauses
    become orphans.  The three lines are joined into one proper
    "## 附录 X（规范性） 标题" heading.
    """
    # Variant 1: the same split emitted as consecutive heading lines
    # ("# 附录B" / "# (规范性)" / "# 可靠性试验方法").  Leaving three H1s
    # inflates the H1 count, corrupts merge title derivation and breaks the
    # round-trip structure layer, so they are merged like the bare-paragraph
    # variant.  Tried before the two-line variant so a 3-line split is not
    # partially consumed.
    heading_3 = re.compile(
        r"^#{1,2}\s*附\s*录\s*([A-Z])\s*\n+#{1,2}\s*[(（](规范性|资料性|推荐性|规范性附录|资料性附录)[)）]\s*\n+#{1,2}\s*([^\n#]+)",
        re.M,
    )
    markdown = heading_3.sub(
        lambda m: f"## 附录 {m.group(1)}（{m.group(2).replace('附录', '')}） {m.group(3).strip()}\n\n",
        markdown,
    )
    # Variant 2: "# 附 录 A" + "# (资料性附录) 质量评定程序或检验规则"
    # (status and title share the second heading line).
    heading_2 = re.compile(
        r"^#{1,2}\s*附\s*录\s*([A-Z])\s*\n+#{1,2}\s*[(（]([^)）]+)[)）]\s*([^\n#]+)",
        re.M,
    )
    markdown = heading_2.sub(
        lambda m: f"## 附录 {m.group(1)}（{m.group(2).replace('附录', '')}） {m.group(3).strip()}\n\n",
        markdown,
    )
    # Variant 3: "## 附录A" + optional bare "(资料性)" line + "## 标题".
    # The status marker may ride as a bare paragraph between the two heading
    # lines; when present it is recovered into the merged heading so GBT-C09
    # (性质标识必备) can pass.  A following clause heading ("A.1 ...") or
    # another annex stays untouched.
    heading_split = re.compile(
        r"^#{1,2}\s*附\s*录\s*([A-Z])\s*\n+(?:\s*[(（]([^)）]+)[)）]\s*\n+)?#{1,2}\s*(?!附录|[A-Z]\.\d)([^\n#]+)",
        re.M,
    )

    def repl_split(match: re.Match[str]) -> str:
        status = match.group(2).replace("附录", "").strip() if match.group(2) else ""
        marker = f"（{status}）" if status else ""
        return f"## 附录 {match.group(1)}{marker} {match.group(3).strip()}\n\n"

    markdown = heading_split.sub(repl_split, markdown)
    # Variant 3b: "# 附录C" + bare "(规范性)" line + bare title paragraph —
    # MinerU keeps only the annex letter as a heading and demotes both the
    # status marker and the title to plain paragraphs (SJT 11859-2022).
    heading_bare = re.compile(
        r"^#{1,2}\s*附\s*录\s*([A-Z])\s*\n+\s*[(（](规范性|资料性|推荐性|规范性附录|资料性附录)[)）]\s*\n+([^\n#]+)",
        re.M,
    )

    def repl_bare(match: re.Match[str]) -> str:
        status = match.group(2).replace("附录", "").strip()
        return f"## 附录 {match.group(1)}（{status}） {match.group(3).strip()}\n\n"

    markdown = heading_bare.sub(repl_bare, markdown)
    # Variant 0: bare paragraphs (no heading prefix), the original case.
    pattern = re.compile(
        r"^附录\s*([A-Z])\s*\n+\n*[(（](规范性|资料性|规范性附录|推荐性)[)）]\s*\n+\n*(.+?)\n+(?=##?\s|[^\n])",
        re.M,
    )

    def repl(match: re.Match[str]) -> str:
        return f"## 附录 {match.group(1)}（{match.group(2)}） {match.group(3).strip()}\n\n"

    return pattern.sub(repl, markdown)


def _recover_gbt_7_4_diagrams(markdown: str, source_pdf: Path, asset_dir: Path) -> str:
    """Restore the two page-18 7.4 layout diagrams MinerU split into text runs.

    规则对应: GBT-B06（图编排：图编号图题居中置于图下）；专属修复，仅 GB/T 1.1-2020 输入启用。

    The source extraction supplies neither a figure asset nor a coherent table.
    Both crops are taken verbatim from the original PDF and retain their labels,
    borders and typography.  The narrow match protects unrelated occurrences of
    the example's intentionally artificial placeholder text.
    """
    pattern = re.compile(
        r"## 5 要求\n\n×.*?\n\n## 6 试验方法\n\n## 6 试验方法",
        flags=re.DOTALL,
    )
    if not pattern.search(markdown):
        return markdown
    try:
        import fitz  # type: ignore

        asset_dir.mkdir(parents=True, exist_ok=True)
        crops = (("GB_T_1.1-2020-7-4-diagrams.png", fitz.Rect(72, 275, 530, 548)),)
        with fitz.open(source_pdf) as document:
            page = document[17]  # PDF page 18, where GB/T 1.1 clause 7.4 appears.
            for name, rect in crops:
                target = asset_dir / name
                if not target.is_file():
                    page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect, alpha=False).save(target)
    except Exception as exc:
        _log(f"Warning: unable to recover 7.4 diagrams from original PDF: {exc}")
        return markdown
    figures = "\n\n".join(f"![]({(Path('assets') / 'images' / name).as_posix()})" for name, _ in crops)
    return pattern.sub(figures, markdown, count=1)


_COVER_BANNER_RE = re.compile(
    r"(?:中华人民共和国)?[\u3400-\u9fff（）()·]{0,40}?(?:国家|行业|地方|团体|企业)标准"
)


def _is_cover_banner(compact: str) -> bool:
    """True when the whitespace-stripped line is a cover banner.

    规则对应: GBT-L03（封面横幅）+ GBT-C01（文件名称非横幅）。
    横幅形态覆盖各级标准：中华人民共和国国家标准 / 中华人民共和国机械
    行业标准 / 晋中经纬新科机械有限公司企业标准 / 团体标准 / 上海市地方
    标准 等；机构名 + 层级字样（企业/团体/地方/行业/国家）均为横幅，
    整行匹配才判定，避免把标题（如「减速器」）误判为横幅。
    """
    return bool(_COVER_BANNER_RE.fullmatch(compact))


# OCR 会把带徽标页的横幅拆成两段（图前 "# 中华人民共和国" + 图后
# "国家标准"）。单独一段不是完整横幅，但拼起来才是；这些片段绝不能
# 当作文档标题（GBT-C01 文件名称）。
_BANNER_FRAGMENTS = ("中华人民共和国", "国家标准")


def _is_cover_banner_fragment(compact: str) -> bool:
    """True when the whitespace-stripped line is only a fragment of a banner."""
    return compact in _BANNER_FRAGMENTS


def _demote_banner_fragments(markdown: str) -> str:
    """Demote OCR-split cover-banner headings back to plain paragraphs.

    MinerU 常把封底/封面横幅在徽标图处拆成 "# 中华人民共和国" + "国家标准"
    两行（GB 标准封底版式）。前半段是 H1 时会污染标题推导并给正文引入
    孤立大标题；若它与其后首个非空行拼起来恰是完整横幅，就降级为普通
    段落。仅处理"拼成横幅"的情形，避免误伤正文标题。

    规则对应: GBT-L03（横幅）+ GBT-C01（文件名称）。
    """
    lines = markdown.splitlines()
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        match = re.match(r"^#\s+(.+?)\s*$", line)
        demoted = False
        if match:
            compact = re.sub(r"\s+", "", match.group(1))
            if compact in _BANNER_FRAGMENTS:
                j = i + 1
                while j < n and not lines[j].strip():
                    j += 1
                if j < n:
                    nxt = re.sub(r"^#+\s*", "", lines[j].strip())
                    if _is_cover_banner(compact + re.sub(r"\s+", "", nxt)):
                        out.append(match.group(1))  # demote: drop the H1 marker
                        demoted = True
        if not demoted:
            out.append(line)
        i += 1
    return "\n".join(out)


def _demote_cover_headings(markdown: str) -> str:
    """Demote cover-block H1 lines that are not the document title.

    MinerU promotes cover lines — the "中华人民共和国国家标准" banner (also
    "<机构名>企业标准" for enterprise standards, "团体标准", "<省>地方标准"
    etc.) and the English translation — to H1.  Neither is the document
    title (GBT-C01 文件名称); leaving them as H1s inflates the H1 count and
    corrupts title derivation.  Only lines before the first "##" heading (the
    cover block of the first part) are touched; the Chinese title H1, when
    present, stays.

    规则对应: GBT-C01（文件名称必备，横幅/英文译名非标题）+ GEN-016（标题识别）。
    """
    head, sep, tail = markdown.partition("\n## ")
    if not sep:
        return markdown
    fixed_lines: list[str] = []
    for line in head.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match and (
            _is_cover_banner(re.sub(r"\s+", "", match.group(1)))
            or re.fullmatch(r"[A-Za-z][A-Za-z0-9 ,.:;()'’/\\—\-]+", match.group(1).strip())
        ):
            fixed_lines.append(match.group(1))  # demote: drop the H1 marker
        else:
            fixed_lines.append(line)
    return "\n".join(fixed_lines) + sep + tail


def _cover_title(markdown: str) -> str:
    """Recover the Chinese standard name from the cover block.

    The cover name sits between the number/replaces lines and the English
    title.  MinerU usually emits it as a bare paragraph (no heading), but for
    enterprise standards it may promote the cover title to a heading too, so
    heading lines whose content is neither banner, date, number nor the 发布/
    实施 block are treated as the title.  Returns the first such CJK line.

    规则对应: GBT-C01（文件名称）+ GEN-016（标题识别，中文行）。
    """
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        is_heading = stripped.startswith("#")
        content = re.sub(r"^#+\s*", "", stripped)
        compact = re.sub(r"\s+", "", content)
        if _is_cover_banner(compact):
            continue
        if re.search(r"发布|实施", compact) or compact.startswith("代替"):
            continue
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", compact):
            continue
        if not re.search(r"[\u3400-\u9fff]", compact):
            continue  # number line / English title / dates are not the name
        if is_heading and re.match(
            r"^(前\s*言|引\s*言|目\s*次|参考文献|索引|附录|范围|规范性引用文件|术语和定义)",
            compact,
        ):
            break  # a real body heading ends the cover block
        return compact
    return ""


def extract(args: argparse.Namespace, state: dict[str, Any]) -> None:
    # 规则对应: GEN-002（分块抽取，每块可重试/断点续跑）、GEN-003（中间产物保留）。
    command = _mineru_command()
    total_pages = _page_count(args.input)
    _log(f"Extraction plan: {total_pages} pages, {args.chunk_size} pages per MinerU invocation")
    _log(f"Backend: pipeline; method: {args.method}; language: ch; formulas: enabled; tables: enabled")
    state["input"] = str(args.input.resolve())
    state["sourceSha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    state["pageCount"] = total_pages
    state["chunkSize"] = args.chunk_size
    state["backend"] = "mineru pipeline"
    state["parameters"] = {"method": args.method, "language": "ch", "formula": True, "table": True}
    state.setdefault("parts", [])

    completed = {item["start"]: item for item in state["parts"] if item.get("status") == "complete"}
    for start in range(0, total_pages, args.chunk_size):
        end = min(start + args.chunk_size - 1, total_pages - 1)
        part_dir = _range_dir(args.output_dir, start, end)
        markdown = _mineru_markdown(part_dir)
        if start in completed and markdown:
            _log(f"Skipping pages {start + 1}-{end + 1}: recorded complete and Markdown exists")
            continue
        if markdown:
            state["parts"] = [item for item in state["parts"] if item.get("start") != start]
            state["parts"].append({"start": start, "end": end, "status": "complete", "markdown": str(markdown.relative_to(args.output_dir))})
            _write_json(args.state_file, state)
            _log(f"Skipping pages {start + 1}-{end + 1}: Markdown exists; state was repaired")
            continue

        part_dir.mkdir(parents=True, exist_ok=True)
        invocation = [
            command, "-p", str(args.input), "-o", str(part_dir), "-b", "pipeline", "-m", args.method, "-l", "ch",
            "-f", "true", "-t", "true", "-s", str(start), "-e", str(end),
        ]
        _log(f"Starting full MinerU pipeline for pages {start + 1}-{end + 1} of {total_pages}")
        _log(f"Persistent part directory: {part_dir}")
        started = time.monotonic()
        result = subprocess.run(invocation, cwd=ROOT)
        elapsed = time.monotonic() - started
        if result.returncode:
            state["lastFailure"] = {"start": start, "end": end, "returnCode": result.returncode}
            _write_json(args.state_file, state)
            _log(f"Pages {start + 1}-{end + 1} failed after {elapsed / 60:.1f} minutes; resume reruns only this range")
            raise RuntimeError(f"MinerU failed for pages {start + 1}-{end + 1} with exit code {result.returncode}")
        markdown = _mineru_markdown(part_dir)
        if markdown is None:
            raise RuntimeError(f"MinerU completed pages {start + 1}-{end + 1} but wrote no Markdown")
        state["parts"] = [item for item in state["parts"] if item.get("start") != start]
        state["parts"].append({"start": start, "end": end, "status": "complete", "markdown": str(markdown.relative_to(args.output_dir))})
        state.pop("lastFailure", None)
        _write_json(args.state_file, state)
        _log(f"Completed pages {start + 1}-{end + 1} in {elapsed / 60:.1f} minutes")
        _log(f"State saved: {args.state_file}")


def merge(args: argparse.Namespace, state: dict[str, Any]) -> Path:
    # 规则对应: GEN-005（按原始页序合并、带页码范围标记）、GEN-010（页眉页脚回收）、
    # GEN-030（附录标题重组）、GEN-019（显式 front-matter 优先）。
    expected = list(range(0, state.get("pageCount", 0), args.chunk_size))
    completed = {item["start"]: item for item in state.get("parts", []) if item.get("status") == "complete"}
    missing = [start + 1 for start in expected if start not in completed]
    if missing:
        raise RuntimeError(f"Cannot merge: MinerU output is missing for pages starting at {missing}")

    _log(f"Merging {len(expected)} completed MinerU page ranges into one CSM Markdown document")
    stem = args.output_stem or args.input.stem
    parts_raw: list[str] = []
    sources: list[dict[str, Any]] = []
    for start in expected:
        part = completed[start]
        source = args.output_dir / part["markdown"]
        raw = convert_mineru_markup(
            source.read_text(encoding="utf-8", errors="replace").strip(),
            f"p{part['start'] + 1:03d}",
            formula_assets_index(source),
            gbt_1_1_quirks=_is_gbt_1_1_2020(args.input),
        )
        raw = _recover_annex_headings(raw)
        raw = _demote_banner_fragments(raw)
        if part["start"] == 0:
            raw = _demote_cover_headings(raw)
        image_source = source.parent / "images"
        if image_source.is_dir():
            image_target = args.output_dir / "assets" / "images"
            image_target.mkdir(parents=True, exist_ok=True)
            for image in image_source.iterdir():
                if image.is_file():
                    shutil.copy2(image, image_target / image.name)
        if part["start"] == 0 and _is_gbt_1_1_2020(args.input):
            # GB/T 1.1-2020 only: restore the two page-18 7.4 layout diagrams.
            raw = _recover_gbt_7_4_diagrams(raw, args.input, args.output_dir / "assets" / "images")
        parts_raw.append(raw)
        sources.append({"pages": [part["start"] + 1, part["end"] + 1], "markdown": part["markdown"], "sha256": hashlib.sha256(raw.encode()).hexdigest()})

    # Derive the standard number and title from the extraction when the caller
    # did not supply them explicitly, matching the generic PDF extractor logic.
    number = args.standard_number or standard_number_from_text("\n".join(parts_raw)[:3000], stem)
    number = re.sub(r"\.(?=\d)", "", number) if number.count(".") > 1 else number
    # 输出文件命名方案（用户确认）：标准号中的斜杠一律转下划线
    # （GB/T→GB_T、JB/T→JB_T、Q/XKBZ→Q_XKBZ），代号与顺序号间加
    # 下划线（GB_T_15034-2012、Q_XKBZ_002-2026）。显式 --output-stem 优先；
    # 否则按解析出的标准号规范化命名并写入 state 供后续阶段复用。
    if not args.output_stem:
        derived = standard_filename(number)
        if derived:
            stem = derived
            args.output_stem = derived
            state["outputStem"] = derived
    paths = _stage_paths(args.output_dir, stem)
    destination = paths["raw"]
    # 阶段目录（00_source … 05_verify）可能尚不存在（例如推导出的 ID 与
    # 输入文件名不同导致目录名变化），确保父目录全部就位。
    for stage_path in paths.values():
        stage_path.parent.mkdir(parents=True, exist_ok=True)
    # 00_source：永久保留原始文件副本 + 校验和（只读，永不修改）。
    paths["source"].parent.mkdir(parents=True, exist_ok=True)
    if not paths["source"].is_file():
        shutil.copy2(args.input, paths["source"])
    source_sha256 = state.get("sourceSha256") or hashlib.sha256(args.input.read_bytes()).hexdigest()
    paths["checksum"].write_text(f"sha256:{source_sha256}\n", encoding="utf-8")
    # The first H1 is often the cover banner ("中华人民共和国国家标准" /
    # "中华人民共和国机械行业标准" / "<机构名>企业标准"), not the standard name.
    # Pick the first H1 that is neither a banner (compared with whitespace
    # stripped — OCR may space it out; _is_cover_banner covers 国家/行业/
    # 地方/团体/企业标准 so GB、JB、DB、T/、Q/ 语料都适用), the English
    # title, nor front-matter headings.
    heading_candidates = [
        line.lstrip("#").strip()
        for part in parts_raw
        for line in part.splitlines()
        if re.match(r"^#\s", line)
    ]
    real_heading = next(
        (
            heading
            for heading in heading_candidates
            if not _is_cover_banner(re.sub(r"\s+", "", heading))
            and not re.fullmatch(r"[A-Za-z][A-Za-z0-9 ,.:;()\-']+", heading)
            and not _is_cover_banner_fragment(re.sub(r"\s+", "", heading))
        ),
        "",
    )
    if not real_heading:
        # MinerU often leaves the cover standard name as a bare paragraph
        # (no heading); recover it so the front-matter title is the actual
        # document name, not a number fallback (GBT-C01 文件名称必备).
        real_heading = _cover_title(parts_raw[0])
    title = args.title or _usable_title(real_heading, number)
    extra_front_matter: list[str] = []
    # Recover the cover ICS/CCS codes that MinerU drops as page headers.  An
    # explicitly supplied --front-matter-json value always wins.
    recovered_codes: dict[str, str] = {}
    for start in expected:
        part = completed[start]
        source = args.output_dir / part["markdown"]
        part_dir = source.parent
        recovered_codes.update(_classification_codes(part_dir))
        if start == expected[0]:
            # Cover fields (English title, dates, issuer) come from page 1.
            cover_meta = _cover_metadata(part_dir, parts_raw[0])
            for key, value in cover_meta.items():
                extra_front_matter.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    for key in ("ics", "ccs"):
        if key in recovered_codes:
            extra_front_matter.append(f"{key}: {json.dumps(recovered_codes[key], ensure_ascii=False)}")
    if args.front_matter_json:
        try:
            extra = json.loads(args.front_matter_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"invalid --front-matter-json file {args.front_matter_json}: {exc}") from exc
        if not isinstance(extra, dict):
            raise RuntimeError("--front-matter-json must contain a JSON object")
        for key, value in extra.items():
            # Explicit caller values replace any auto-recovered ones.
            extra_front_matter = [line for line in extra_front_matter if not line.startswith(f"{key}:")]
            extra_front_matter.append(f"{key}: {json.dumps(str(value), ensure_ascii=False)}")
    # 封面徽标不再从 PDF 提取：渲染端按标准类型从 config/emblems/ 固定位置
    # 读取（GEN-018/GBT-L02），提取的图块既不可靠也不通用，故此处不再写入
    # cover-badge 资产（SSIR 的 coverBadge 字段保留以兼容历史数据）。
    lines = [
        "---",
        'csm-version: "1.0"',
        "document-type: standard",
        f"document-identifier: {json.dumps(number, ensure_ascii=False)}",
        f"standard-number: {json.dumps(number, ensure_ascii=False)}",
        f"title: {json.dumps(title, ensure_ascii=False)}",
        *extra_front_matter,
        "language: zh-CN",
        "source:",
        "  mode: mineru-pdf",
        f"  original-file-name: {json.dumps(args.input.name, ensure_ascii=False)}",
        "  provenance: pipeline-state.json",
        'extraction-backend: "mineru pipeline"',
        "---",
        "",
    ]
    body = "\n\n".join(
        f"<!-- ssir:mineru-pages start=\"{completed[start]['start'] + 1}\" end=\"{completed[start]['end'] + 1}\" -->\n{raw}\n<!-- /ssir:mineru-pages -->"
        for start, raw in zip(expected, parts_raw)
    )
    if not re.search(r"(?m)^#\s", body):
        body = f"# {title}\n\n{body}"
    lines.extend([body, ""])
    destination.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    provenance = paths["provenance"]
    _write_json(provenance, {
        "sourcePdf": str(args.input.resolve()), "sourceSha256": state["sourceSha256"], "pageCount": state["pageCount"],
        "backend": state["backend"], "parameters": state["parameters"], "parts": sources,
    })
    state["title"] = title
    state["number"] = number
    _write_json(args.state_file, state)
    _log(f"Merged Markdown written: {destination}")
    _log(f"Provenance written: {provenance}")
    return destination


def finalize(args: argparse.Namespace, merged: Path) -> Path | None:
    """Use the existing CSM normalizer/parser, retaining partial status if parsing needs review.

    规则对应: GEN-031（层次编号规范化）、GEN-050（元数据 schema 登记）；合规验证由
    service 层 verify_compliance 按 GEN-* → GBT-* → P10-* 三层执行并写入转换报告。
    """
    stem = args.output_stem or args.input.stem
    paths = _stage_paths(args.output_dir, stem)
    canonical = paths["canonical"]
    ssir = paths["ssir"]
    normalize = [
        str(Path(sys.prefix) / "bin" / "ssir"), "csm", "normalize",
        "--input", str(merged), "--canonical-output", str(canonical),
        "--report", str(paths["normalize_report"]),
    ]
    parsed = [
        str(Path(sys.prefix) / "bin" / "ssir"), "csm", "parse",
        "--input", str(canonical), "--output", str(ssir),
        "--report", str(paths["parse_report"]),
    ]
    _log("Normalizing merged MinerU Markdown into canonical CSM")
    if subprocess.run(normalize, cwd=ROOT).returncode:
        print("CSM normalization needs review; MinerU extraction and provenance remain available.", file=sys.stderr)
        return None
    _log("Parsing normalized CSM into SSIR JSON")
    if subprocess.run(parsed, cwd=ROOT).returncode:
        print("SSIR parsing needs review; normalized CSM remains available.", file=sys.stderr)
        return None
    _log(f"SSIR JSON written: {ssir}")
    _stamp_example_styles(ssir, args.input)
    return ssir


def _stamp_example_styles(ssir_path: Path, source_pdf: Path) -> None:
    """Detect the original example-box style and record it on SSIR example nodes
    (GBT-B11 示例线框：frame=黑色细实线框 / shaded=浅色背景，两种模式都要保留，
    渲染与原文一致).

    检测依据是源 PDF 的矢量几何：大尺寸描边矩形 → frame；大尺寸填充矩形 → shaded。
    扫描型 PDF（页面是位图、无矢量框线）检测不到，节点不带 exampleStyle，
    渲染时回退到渲染 profile 的 examples.style 默认值。
    """
    try:
        import fitz  # type: ignore
    except Exception:
        return
    stroke_rects = 0
    fill_rects = 0
    try:
        with fitz.open(source_pdf) as document:
            for page in document:
                for drawing in page.get_drawings():
                    rect = drawing["rect"]
                    if rect.width < 80 or rect.height < 30:
                        continue
                    if drawing.get("fill"):
                        fill_rects += 1
                    elif drawing.get("stroke"):
                        stroke_rects += 1
    except Exception:
        return
    if not (stroke_rects or fill_rects):
        return  # 无矢量几何（扫描型）→ 保留 profile 默认
    style = "frame" if stroke_rects >= fill_rects else "shaded"
    try:
        data = json.loads(ssir_path.read_text(encoding="utf-8"))
    except Exception:
        return

    def visit(nodes: list[Any]) -> None:
        for node in nodes:
            if node.get("exampleContent"):
                node.setdefault("exampleStyle", style)
            visit(node.get("children", []) or [])

    visit(data.get("structuralRoot", {}).get("children", []) or [])
    ssir_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"Example style detected from source PDF: {style} (stroke={stroke_rects}, fill={fill_rects})")


def compare(original: Path, generated: Path, output: Path) -> None:
    # 规则对应: GEN-051（元数据往返一致）、GEN-090（机器验证：关键封面字段齐全、
    # 页数合理）、GEN-091（基于 PDF 内部对象验证）。
    import fitz  # type: ignore
    def details(path: Path) -> dict[str, Any]:
        with fitz.open(path) as document:
            text = "".join(page.get_text() for page in document)
            return {"path": str(path), "bytes": path.stat().st_size, "pageCount": len(document), "textCharacters": len(text)}
    original_info, generated_info = details(original), details(generated)
    _write_json(output, {
        "original": original_info,
        "generated": generated_info,
        "delta": {"pages": generated_info["pageCount"] - original_info["pageCount"], "bytes": generated_info["bytes"] - original_info["bytes"], "textCharacters": generated_info["textCharacters"] - original_info["textCharacters"]},
        "review": "Page count and text volume are objective checks. Tables, formula layout, pagination, and typography require visual review against the original PDF.",
    })


def main() -> int:
    # 规则对应（流水线阶段 → 规则层）: extract=GEN-002/003；merge=GEN-005/010—019/030；
    # normalize=GEN-031—034；build=GEN-050/052；verify=GEN-051/090/091 + 三层合规
    # （GEN→GBT→P10，见 compliance.py）；render=GEN-070—076。
    parser = argparse.ArgumentParser(description="Run a resumable full MinerU extraction, SSIR parsing, round-trip verification and optional PDF rendering for a national-standard PDF.")
    parser.add_argument("--input", type=Path, help="PDF input of the national standard to extract (required)")
    parser.add_argument("--output-dir", type=Path, help="output directory (default: out/mineru/<input-stem>)")
    parser.add_argument("--output-stem", type=str, help="output filename stem for merged CSM/SSIR/PDF artifacts (default: input file name without the .pdf extension)")
    parser.add_argument("--front-matter-json", type=Path, help="optional JSON object with additional CSM front matter keys merged into the merged document (e.g. {\"ics\": \"01.120\", \"issuer\": \"...\"})")
    parser.add_argument("--standard-number", type=str, help="standard number written into the CSM front matter (default: inferred from the extraction, e.g. GB/T 10401-2023)")
    parser.add_argument("--title", type=str, help="standard title written into the CSM front matter (default: first H1 from the extraction)")
    parser.add_argument("--chunk-size", type=int, default=18, help="Pages per restartable MinerU invocation (default: 18).")
    parser.add_argument("--method", choices=("auto", "ocr", "txt"), default="auto", help="MinerU extraction method (default: auto). Use ocr when the PDF text layer loses Latin/digit runs (MinerU's txt extraction can drop them while pymupdf reads them fine).")
    parser.add_argument("--stage", choices=("extract", "merge", "finalize", "all"), default="all")
    parser.add_argument("--roundtrip", action="store_true", help="Run CSM canonical -> SSIR -> CSM render.md -> verify round-trip verification after parsing.")
    parser.add_argument("--render", action="store_true", help="Render parsed SSIR to PDF and write a comparison report.")
    parser.add_argument("--toc-depth", default="2", help="Maximum numbered TOC level for --render (positive integer or all; default: 2).")
    args = parser.parse_args()
    if not args.input:
        parser.error("--input is required (a PDF of the national standard to extract)")
    if not args.input.is_file() or args.input.suffix.lower() != ".pdf":
        parser.error(f"input must be an existing PDF: {args.input}")
    if args.chunk_size < 1:
        parser.error("--chunk-size must be positive")
    # 文档根目录（naming_specification.txt §4.2 out/mineru/{input}/）：默认用
    # 源文件名主干（corpus 已是规范 ID 形如 GB_T_23132-2008，保留下划线）；
    # 仅当主干含空白（如 "GB_T_1.1-2020 标准化文件的起草规则"）才把 \W+ 折叠为连字符。
    stem_dir = args.input.stem if not re.search(r"\s", args.input.stem) else re.sub(r"\W+", "-", args.input.stem).strip("-")
    args.output_dir = args.output_dir or ROOT / "out" / "mineru" / stem_dir
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.state_file = args.output_dir / "pipeline-state.json"
    state = _load_json(args.state_file, {})
    state.setdefault("createdAt", datetime.now().astimezone().isoformat(timespec="seconds"))
    # 断点续跑：stem 在上一次 merge 已推导并存入 state，直接复用。
    if not args.output_stem and state.get("outputStem"):
        args.output_stem = state["outputStem"]
    _log(f"Input PDF: {args.input.resolve()}")
    _log(f"Output directory: {args.output_dir.resolve()}")
    _log(f"Stage: {args.stage}; round-trip: {args.roundtrip}; render after parsing: {args.render}")

    try:
        if args.stage in {"extract", "all"}:
            extract(args, state)
        if args.stage == "extract":
            _log("Extraction stage complete. Run with --stage all to merge and parse after all page ranges finish.")
            return 0
        merged = merge(args, state)
        _log(f"Merged MinerU Markdown: {merged}")
        if args.stage == "merge":
            _write_manifest(args, state)
            return 0
        ssir = finalize(args, merged)
        paths = _stage_paths(args.output_dir, args.output_stem or args.input.stem)
        if args.roundtrip and ssir:
            roundtrip = [
                str(Path(sys.prefix) / "bin" / "ssir"), "csm", "roundtrip",
                "--input", str(paths["canonical"]), "--render-md-output", str(paths["render_md"]),
                "--verify-output", str(paths["verify"]), "--report", str(paths["roundtrip"]),
            ]
            _log("Running SSIR round-trip verification (canonical -> SSIR -> render.md -> verify)")
            result = subprocess.run(roundtrip, cwd=ROOT)
            if result.returncode not in (0, 3):
                raise RuntimeError("SSIR round-trip verification failed")
            _log(f"Round-trip result: {result.returncode} (0 = equivalent; 3 = critical information loss)")
        if args.render and ssir:
            render = [
                str(Path(sys.prefix) / "bin" / "ssir"), "pdf", "render",
                "--input", str(paths["ssir"]), "--output", str(paths["render_pdf"]),
                "--report", str(paths["render_report"]), "--toc-depth", args.toc_depth,
            ]
            _log("Rendering SSIR JSON as a traditional standard-style PDF")
            if subprocess.run(render, cwd=ROOT).returncode:
                raise RuntimeError("SSIR PDF renderer failed")
            compare(args.input, paths["render_pdf"], paths["render_comparison"])
            _log(f"Generated PDF comparison: {paths['render_comparison']}")
        _write_manifest(args, state, status="completed")
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _log("Workflow completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
