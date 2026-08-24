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

from bs4 import BeautifulSoup


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
# and are deliberately not specific to GB/T 1.1-2020.
def _standard_number(text: str, fallback: str) -> str:
    # 规则对应: GEN-012（文件编号识别与一字线规范化）。
    match = re.search(r"\b(?:GB|GB/T|DB|QB|JB|DL|NY|ISO)[ /A-Z0-9.\-—]+", text, re.I)
    return (match.group(0).strip() if match else fallback).replace("—", "-")


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


def _mineru_markdown(part_dir: Path) -> Path | None:
    candidates = sorted(part_dir.rglob("*.md"), key=lambda path: path.stat().st_size, reverse=True)
    return candidates[0] if candidates else None


def _html_table_to_csm(html: str, table_id: str, caption: str | None) -> str:
    """Turn MinerU HTML tables into the constrained CSM table representation.

    规则对应: GBT-B08（题注形如"表X 题名"，编号必备）+ GEN-033（无编号且无题名不输出题注）。
    """
    soup = BeautifulSoup(html, "html.parser")
    rows: list[list[str]] = []
    for tr in soup.find_all("tr"):
        row: list[str] = []
        for cell in tr.find_all(["th", "td"], recursive=False):
            text = " ".join(cell.get_text(" ", strip=True).split()).replace("|", r"\|")
            span = max(int(cell.get("colspan", 1)), 1)
            row.extend([text] + [""] * (span - 1))
        if row:
            rows.append(row)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    for row in rows:
        row.extend([""] * (width - len(row)))
    attrs = [f'id="mineru-table-{table_id}"', 'header-rows="1"']
    if caption:
        match = re.match(r"^表\s*([^\s]+)\s+(.+)$", caption)
        if match:
            attrs.extend([f'caption-number="{match.group(1)}"', f'caption="{match.group(2).replace(chr(34), "&quot;")}"'])
    lines = [f"<!-- ssir:table {' '.join(attrs)} -->"]
    for index, row in enumerate(rows):
        lines.append("| " + " | ".join(row) + " |")
        if index == 0:
            lines.append("| " + " | ".join("---" for _ in row) + " |")
    return "\n".join(lines)


def _extract_cover_badge(source_pdf: Path, output_dir: Path) -> str | None:
    """Extract the cover "GB" emblem image from page 1 into an asset.

    规则对应: GEN-018（封面徽标图片恢复，should）。

    MinerU only recognises the emblem as an oversized header text block; the
    emblem itself is a raster image embedded in the source PDF.  The largest
    top-of-page image is recovered so rendering can place it back.
    Returns the asset path relative to the output directory, or None.
    """
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
        ics = re.search(r"ICS\s*([0-9]+(?:\.[0-9]+){0,3})", compact, re.I)
        ccs = re.search(r"(?:CCS)?\s*([A-Z])\s?(\d{1,2})\s*$", compact, re.I)
        if not ccs:
            # "A00" style with no separator between letter and digits.
            ccs = re.search(r"\b([A-Z])(\d{2})\b", compact)
        if ics:
            codes.setdefault("ics", _normalize_ics(ics.group(1)))
        if ccs and not compact.lower().startswith("ics"):
            codes.setdefault("ccs", f"{ccs.group(1).upper()} {ccs.group(2)}")
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
    # Replaced standard ("代替 GB/T ...—....") from the cover text.
    for line in markdown_text.splitlines():
        match = re.match(r"^代替\s+(.+)$", line.strip())
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
        text = str(item.get("text") or item.get("content") or "").strip()
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

    for item in entries:
        if item.get("page_idx") not in (0, None):
            continue
        text = str(item.get("text") or item.get("content") or "").strip()
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
            issuer = _canonical_issuer(compact_line)
            if issuer:
                result.setdefault("issuer", issuer)
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


def _canonical_issuer(text: str) -> str:
    # 规则对应: GEN-014（发布机构识别与规范名称映射——通用机构名录）。
    compact = re.sub(r"\s+", "", text)
    # Distinctive fragments decide the era; check the quality-supervision
    # administration first because its name embeds "标准化管理" via the
    # co-published standardization committee line.
    if "质量监督" in compact or "质检" in compact:
        return "中华人民共和国国家质量监督检验检疫总局 中国国家标准化管理委员会"
    if "市场监督" in compact or "标督管" in compact:
        return "国家市场监督管理总局 国家标准化管理委员会"
    if "标准化管理" in compact:
        return "国家市场监督管理总局 国家标准化管理委员会"
    return ""


def _formula_assets(source: Path) -> dict[str, list[str]]:
    """Index MinerU equation crops by their normalized display-LaTex text.

    规则对应: GEN-004（公式资产相对路径引用）+ GBT-X06（数学公式另行居中编排）。
    """
    candidates = sorted(source.parent.glob("*_content_list.json"))
    if not candidates:
        return {}
    try:
        entries = json.loads(candidates[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    result: dict[str, list[str]] = {}
    for item in entries:
        if item.get("type") != "equation" or not item.get("img_path"):
            continue
        text = str(item.get("text", "")).strip()
        if text.startswith("$$") and text.endswith("$$"):
            text = text[2:-2].strip()
        key = re.sub(r"\s+", "", text)
        result.setdefault(key, []).append("assets/images/" + Path(str(item["img_path"])).name)
    return result


def _recover_annex_headings(markdown: str) -> str:
    """Rebuild annex headings that MinerU split into bare paragraphs.

    规则对应: GEN-030（附录标题重组：编号行 + 性质行 + 标题行合并）。

    MinerU emits the annex header as three consecutive paragraphs
    ("附录A" / "(规范性)" / "外形及安装尺寸"), which the CSM parser treats as
    plain body text, so no annex chapter is created and A.1-style clauses
    become orphans.  The three lines are joined into one proper
    "## 附录 X（规范性） 标题" heading.
    """
    pattern = re.compile(
        r"^附录\s*([A-Z])\s*\n+\n*[(（](规范性|资料性|规范性附录|推荐性)[)）]\s*\n+\n*(.+?)\n+(?=##?\s|[^\n])",
        re.M,
    )

    def repl(match: re.Match[str]) -> str:
        return f"## 附录 {match.group(1)}（{match.group(2)}） {match.group(3).strip()}\n\n"

    return pattern.sub(repl, markdown)


def _convert_mineru_markup(raw: str, part_prefix: str, formula_assets: dict[str, list[str]] | None = None, gbt_1_1_quirks: bool = False) -> str:
    """Adapt MinerU HTML tables and relative image paths without altering prose.

    规则对应: GEN-004（资产相对路径重写）、GEN-032/033（表格题注拆分与孤立题注抑制）、
    GBT-X06（公式资产绑定）。
    """
    table_index = 0
    output: list[str] = []
    position = 0
    for match in re.finditer(r"<table\b[^>]*>.*?</table>", raw, flags=re.IGNORECASE | re.DOTALL):
        before = raw[position:match.start()]
        output.append(before)
        caption = None
        previous = "".join(output).rstrip().splitlines()
        if previous:
            candidate = previous[-1].strip()
            if re.match(r"^表\s*[^\s]+\s+.+$", candidate):
                caption = candidate
                output[-1] = re.sub(r"[^\n]+$", "", output[-1])
        table_index += 1
        converted = _html_table_to_csm(match.group(0), f"{part_prefix}-{table_index:03d}", caption)
        output.append(converted if converted else match.group(0))
        position = match.end()
    output.append(raw[position:])
    converted = "".join(output).replace("](images/", "](assets/images/")
    lines = converted.splitlines()
    cleaned: list[str] = []
    image_pattern = re.compile(r"^!\[.*?\]\(([^)]+)\)$")
    figure_caption = re.compile(r"^图\s*([A-Z]?\.?\d+(?:\.\d+)?)\s+(.+)$")
    index = 0
    while index < len(lines):
        image = image_pattern.match(lines[index].strip())
        if not image:
            cleaned.append(lines[index])
            index += 1
            continue
        caption_at = None
        caption_match = None
        for probe in range(index + 1, min(index + 7, len(lines))):
            candidate = figure_caption.match(lines[probe].strip())
            if candidate:
                caption_at, caption_match = probe, candidate
                break
        if caption_match:
            label = f"图 {caption_match.group(1)} {caption_match.group(2)}"
            cleaned.append(f"![{label}]({image.group(1)})")
            cleaned.extend(lines[index + 1:caption_at])
            index = caption_at + 1
        else:
            cleaned.append(lines[index])
            index += 1
    converted = "\n".join(cleaned)
    if gbt_1_1_quirks:
        # GB/T 1.1-2020 appendix E only: MinerU omitted the E.11 raster and
        # misidentified its index-layout image as a table directly after 图 E.10.
        # Do not render that unrelated table under the E.10 caption.
        converted = re.sub(
            r"\n<!-- ssir:table id=\"mineru-table-p055-001\".*?\n图\s*E\.11\s+索引格式\n\n单位为毫米\n",
            "\n> [待复核：MinerU 将图 E.11 索引格式误识别为表格，未提取可渲染的图像资产]\n",
            converted,
            flags=re.DOTALL,
        )
    formula_assets = formula_assets or {}
    formula_index = 0

    def bind_formula(match: re.Match[str]) -> str:
        nonlocal formula_index
        expression = match.group(1).strip()
        candidates = formula_assets.get(re.sub(r"\s+", "", expression), [])
        if not candidates:
            return match.group(0)
        asset = candidates.pop(0)
        formula_index += 1
        identifier = f"{part_prefix}-{formula_index:03d}"
        return f'<!-- ssir:formula id="mineru-formula-{identifier}" asset-ref="{asset}" -->\n{match.group(0)}'

    return re.sub(r"\$\$\s*\n(.*?)\n\$\$", bind_formula, converted, flags=re.DOTALL)


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
        crops = (("gbt-1-1-2020-7-4-diagrams.png", fitz.Rect(72, 275, 530, 548)),)
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


def extract(args: argparse.Namespace, state: dict[str, Any]) -> None:
    # 规则对应: GEN-002（分块抽取，每块可重试/断点续跑）、GEN-003（中间产物保留）。
    command = _mineru_command()
    total_pages = _page_count(args.input)
    _log(f"Extraction plan: {total_pages} pages, {args.chunk_size} pages per MinerU invocation")
    _log("Backend: pipeline; method: auto; language: ch; formulas: enabled; tables: enabled")
    state["input"] = str(args.input.resolve())
    state["sourceSha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    state["pageCount"] = total_pages
    state["chunkSize"] = args.chunk_size
    state["backend"] = "mineru pipeline"
    state["parameters"] = {"method": "auto", "language": "ch", "formula": True, "table": True}
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
            command, "-p", str(args.input), "-o", str(part_dir), "-b", "pipeline", "-m", "auto", "-l", "ch",
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
    destination = args.output_dir / f"{stem}.mineru.csm.md"
    parts_raw: list[str] = []
    sources: list[dict[str, Any]] = []
    for start in expected:
        part = completed[start]
        source = args.output_dir / part["markdown"]
        raw = _convert_mineru_markup(
            source.read_text(encoding="utf-8", errors="replace").strip(),
            f"p{part['start'] + 1:03d}",
            _formula_assets(source),
            gbt_1_1_quirks=_is_gbt_1_1_2020(args.input),
        )
        raw = _recover_annex_headings(raw)
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
    number = args.standard_number or _standard_number("\n".join(parts_raw)[:3000], stem)
    number = re.sub(r"\.(?=\d)", "", number) if number.count(".") > 1 else number
    # The first H1 is often the cover banner ("中华人民共和国国家标准"),
    # not the standard name.  Pick the first H1 that is neither the banner
    # (compared with whitespace stripped — OCR may space out the banner),
    # the English title, nor front-matter headings.
    banner_titles = {"中华人民共和国国家标准", "中华人民共和国国家标淮"}
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
            if re.sub(r"\s+", "", heading) not in {re.sub(r"\s+", "", b) for b in banner_titles}
            and not re.fullmatch(r"[A-Za-z][A-Za-z0-9 ,.:;()\-']+", heading)
        ),
        "",
    )
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
    # Recover the cover "GB" emblem as a croppable image asset.
    badge_asset = _extract_cover_badge(args.input, args.output_dir)
    if badge_asset:
        extra_front_matter.append("cover-badge: " + json.dumps(badge_asset))
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
        "  provenance: mineru-full-standard-state.json",
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
    provenance = args.output_dir / f"{stem}.mineru.provenance.json"
    _write_json(provenance, {
        "sourcePdf": str(args.input.resolve()), "sourceSha256": state["sourceSha256"], "pageCount": state["pageCount"],
        "backend": state["backend"], "parameters": state["parameters"], "parts": sources,
    })
    _log(f"Merged Markdown written: {destination}")
    _log(f"Provenance written: {provenance}")
    return destination


def finalize(args: argparse.Namespace, merged: Path) -> Path | None:
    """Use the existing CSM normalizer/parser, retaining partial status if parsing needs review.

    规则对应: GEN-031（层次编号规范化）、GEN-050（元数据 schema 登记）；合规验证由
    service 层 verify_compliance 按 GEN-* → GBT-* → P10-* 三层执行并写入转换报告。
    """
    stem = args.output_stem or args.input.stem
    std0 = args.output_dir / f"{stem}.mineru.std0.csm.md"
    ssir = args.output_dir / f"{stem}.mineru.ssir.json"
    normalize = [str(Path(sys.prefix) / "bin" / "ssir"), "csm", "normalize", "--input", str(merged), "--std0-output", str(std0)]
    parsed = [str(Path(sys.prefix) / "bin" / "ssir"), "csm", "parse", "--input", str(std0), "--output", str(ssir)]
    _log("Normalizing merged MinerU Markdown into CSM Std0")
    if subprocess.run(normalize, cwd=ROOT).returncode:
        print("CSM normalization needs review; MinerU extraction and provenance remain available.", file=sys.stderr)
        return None
    _log("Parsing normalized CSM into SSIR JSON")
    if subprocess.run(parsed, cwd=ROOT).returncode:
        print("SSIR parsing needs review; normalized CSM remains available.", file=sys.stderr)
        return None
    _log(f"SSIR JSON written: {ssir}")
    return ssir


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
    parser.add_argument("--stage", choices=("extract", "merge", "finalize", "all"), default="all")
    parser.add_argument("--roundtrip", action="store_true", help="Run CSM Std0 -> SSIR -> CSM Std1 -> SSIR round-trip verification after parsing.")
    parser.add_argument("--render", action="store_true", help="Render parsed SSIR to PDF and write a comparison report.")
    parser.add_argument("--toc-depth", default="2", help="Maximum numbered TOC level for --render (positive integer or all; default: 2).")
    args = parser.parse_args()
    if not args.input:
        parser.error("--input is required (a PDF of the national standard to extract)")
    if not args.input.is_file() or args.input.suffix.lower() != ".pdf":
        parser.error(f"input must be an existing PDF: {args.input}")
    if args.chunk_size < 1:
        parser.error("--chunk-size must be positive")
    args.output_dir = args.output_dir or ROOT / "out" / "mineru" / re.sub(r"\W+", "-", args.input.stem).strip("-")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.state_file = args.output_dir / "mineru-full-standard-state.json"
    state = _load_json(args.state_file, {})
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
            return 0
        ssir = finalize(args, merged)
        stem = args.output_stem or args.input.stem
        if args.roundtrip and ssir:
            std0 = args.output_dir / f"{stem}.mineru.std0.csm.md"
            std1 = args.output_dir / f"{stem}.mineru.std1.csm.md"
            roundtrip = [str(Path(sys.prefix) / "bin" / "ssir"), "csm", "roundtrip", "--input", str(std0), "--std1-output", str(std1)]
            _log("Running SSIR round-trip verification (Std0 -> SSIR1 -> Std1 -> SSIR2)")
            result = subprocess.run(roundtrip, cwd=ROOT)
            if result.returncode not in (0, 3):
                raise RuntimeError("SSIR round-trip verification failed")
            _log(f"Round-trip result: {result.returncode} (0 = SSIR1/SSIR2 equivalent; 3 = critical information loss)")
        if args.render and ssir:
            pdf = args.output_dir / f"{stem}.mineru.pdf"
            render = [str(Path(sys.prefix) / "bin" / "ssir"), "pdf", "render", "--input", str(ssir), "--output", str(pdf), "--toc-depth", args.toc_depth]
            _log("Rendering SSIR JSON as a traditional standard-style PDF")
            if subprocess.run(render, cwd=ROOT).returncode:
                raise RuntimeError("SSIR PDF renderer failed")
            comparison = args.output_dir / f"{stem}.mineru.pdf-comparison.json"
            compare(args.input, pdf, comparison)
            _log(f"Generated PDF comparison: {comparison}")
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _log("Workflow completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
