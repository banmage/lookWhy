#!/usr/bin/env python3
"""Resumable full MinerU extraction and SSIR/PDF comparison workflow.

The tool deliberately uses MinerU's complete pipeline backend.  It divides a
long PDF into page ranges only to make CPU runs restartable; every range still
enables layout analysis, OCR, formulas, and tables.

表格通道（GEN-094，2026-09-09）：MinerU pipeline 的表格结构识别只在可见网格线
处断行——"隐藏行表"（块内逐行叠印无网格线：GB_T_5171.1-2014 表1 温升限值、
GB_T_755-2025 表13 等）被压成单行单元格、数值串粘接不可逆。该通道**默认关闭**
（hybrid-engine 是 VLM 型表格结构识别、整页跑非常耗时）：不加参数时表格保持
pipeline 原样（原始逻辑）；仅显式加 --hybrid-tables，extract 才对含表页额外跑
hybrid-engine（能视觉恢复逐行对齐），merge 按（页, 页内序）把表格块替换为
hybrid 结果；正文一律仍用 pipeline（hybrid 整页正文会丢数字/拉丁短串，本仓库
不做整体换后端，与 GEN-092 同口径）。hybrid 缺失/失败/表数不齐时回退 pipeline
表格块。
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any

from leleby_ssir.mineru_html import convert_mineru_markup, formula_assets_index, html_table_to_csm
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


# 文本层损坏特征（2026-08-31，GB_T_43726-2024 等）：PDF 文本层是"半坏"的——
# 有内容但数字/拉丁被拆散或截断，MinerU auto/txt 直接抽取会逐行丢点丢数字
# （条号 4.2.1→421、标准号 GB/T2423.→"GB/T2423." 或整段丢失）。
_ORPHAN_NUMBER_DOT_RE = re.compile(r"^\d{1,3}\.$")
_TRUNCATED_STANDARD_RE = re.compile(r"^(?:GB/T|GB|JB/T|DB\d{1,2}/T|T/|Q/)\S*\.$")
# 标题编号整体丢失特征（2026-09-01，Q_TQDZ_004-2026 等企业标准）：PDF 文本层里
# 二级标题行的编号（7.1、9.1…）不存在——pymupdf 逐字符确认"外观检查"行只有 4 个
# 汉字，而视觉层（OCR 识别）编号齐全（7.1 外观检查、9.3 运输）。这是文本层
# "半坏"的另一种形态：章节号/条号（6.2.1、9.2.2）完好，唯独标题行编号丢失。
# 判别（对语料库 33 份 PDF 实测）：损坏文档（Q_TQDZ/Q_HKF/Q_XKBZ）的裸汉字短行
# （2-12 字、无数字无标点）中 ≥50% 后跟长正文行（≥15 字，即"标题+正文段落"
# 版式），且文档存在带点条款行（x.y 编号体系）；健康文档（GB_T_1.1-2020、
# T_ZZB_2224、DB11_T_1000.1、GB_3100 系列等）裸短行多为表格单元格/术语，
# 后跟长正文比例 <25% 或没有带点条款行（Q_YYJD 无 x.y 体系不误报）。
_BARE_HAN_HEAD_RE = re.compile(r"^[\u4e00-\u9fff]{2,12}$")
_NUMBERED_CLAUSE_RE = re.compile(r"^\d+(?:\.\d+)+\s")
# 标准号提及（文本层/raw 覆盖率对比用，2026-08-31）：宽匹配，前缀 + 数字/字母
# 即算一次提及。GB_T_15835-2011 类文档（文本层健康但 MinerU 抽取丢拉丁）的
# 特征是文本层标准号远多于抽取结果——用于 _latin_loss_check 的自动 OCR 判定。
_STANDARD_MENTION_RE = re.compile(
    r"(?:GB/T|GB/Z|GB|JB/T|JB|DB\d{1,2}/T|QB/T|QB|SJ/T|SJ|DL/T|NY/T|HG/T|FZ/T|WS/T|YD/T|GA/T|CJ/T|JG/T|TB/T|SH/T|JC/T|EJ/T|MT/T|YY/T|YY|HJ/T|HJ|T/|Q/|ISO|IEC)\s*[A-Z0-9]"
)



def _detect_broken_text_layer(pdf: Path, sample_pages: int = 30) -> str | None:
    """Return a reason string when the source PDF's text layer shows the typical
    damage pattern that makes text-based extraction (auto/txt) lose digits and
    Latin runs; return None for healthy text layers and for scanned PDFs
    (no text layer at all — MinerU auto already OCRs those).

    信号（对语料库实测，2026-08-31 / 2026-09-01）：
    - 孤立"4."/"2."行（条号被拆到独立行）：健康文本层 0 条，损坏文档 130+ 条；
    - 截断的标准号 "GB/T2423."（点号处切断）：健康 0 条，损坏文档 4+ 条；
    - 标题行编号整体丢失（Q_TQDZ_004-2026 等企标）：裸汉字短行（2-12 字）中
      ≥50% 后跟长正文行、且存在带点条款编号体系 → 文本层缺标题编号，
      MinerU 文本抽取只能得到无编号裸标题（7.1 外观检查 → "外观检查"）。
    """
    try:
        import fitz  # type: ignore
    except ImportError:
        return None
    orphan_dots = 0
    truncated_standards = 0
    bare_heads = 0
    bare_heads_followed = 0
    numbered_clauses = 0
    with fitz.open(pdf) as document:
        scanned = min(sample_pages, len(document))
        for page_index in range(scanned):
            lines = str(document[page_index].get_text()).splitlines()
            for i, line in enumerate(lines):
                stripped = line.strip()
                if not stripped:
                    continue
                if _ORPHAN_NUMBER_DOT_RE.match(stripped):
                    orphan_dots += 1
                elif _TRUNCATED_STANDARD_RE.match(stripped):
                    truncated_standards += 1
                if _NUMBERED_CLAUSE_RE.match(stripped):
                    numbered_clauses += 1
                elif _BARE_HAN_HEAD_RE.match(stripped):
                    bare_heads += 1
                    # 裸短行后 3 行内首个非空行：是长正文段落（标题-正文版式）
                    # 还是表格单元格/空行（健康文档的裸短行常是表格内容）。
                    following = ""
                    for j in range(i + 1, min(i + 4, len(lines))):
                        following = lines[j].strip()
                        if following:
                            break
                    if len(following) >= 15:
                        bare_heads_followed += 1
        if orphan_dots >= 30 or truncated_standards >= 3:
            return (
                f"text layer damage detected: {orphan_dots} orphaned number-dot lines, "
                f"{truncated_standards} truncated standard numbers in the first {scanned} pages"
            )
        if (
            bare_heads >= 5
            and numbered_clauses >= 5
            and bare_heads_followed >= 4
            and bare_heads_followed * 2 >= bare_heads
        ):
            return (
                f"text layer damage detected: {bare_heads_followed}/{bare_heads} bare Han "
                f"heading lines followed by body text while {numbered_clauses} numbered "
                f"clause lines exist (heading numbers lost in the text layer)"
            )
    return None


def _latin_loss_check(raw_markdowns: list[str], pdf: Path, sample_pages: int = 30) -> str | None:
    """Compare standard-number coverage between the source text layer and the
    extracted markdown; return a reason string when the extractor dropped
    Latin/digit runs (GB_T_15835-2011 / GB_T_23132-2024 class).

    GEN-092 预检（_detect_broken_text_layer）只覆盖"文本层本身损坏"型（孤立
    4. 行、截断 GB/T2423.）。但有一类 PDF 文本层**健康**（pymupdf 读得到
    "GB/T1.1—2009"），MinerU 的 txt/auto 抽取却按字体编码问题整段丢弃拉丁
    字母与数字（"GB/T 1.1—2020" → "/ — "）——语料实测 GB_T_15835-2011、
    GB_T_23132-2024 中招。这里在抽取完成后对比源 PDF 文本层与 raw 的标准号
    提及数：文本层 ≥5 且 raw 不足其一半时判定丢失，提示强制 OCR 重抽。
    健康文档（GB_T_1.1-2020：文本层/raw 都密）与扫描件（无文本层，提及数 0）
    均不会触发。
    """
    try:
        import fitz  # type: ignore
    except ImportError:
        return None
    text_hits = 0
    with fitz.open(pdf) as document:
        for page_index in range(min(sample_pages, len(document))):
            text_hits += len(_STANDARD_MENTION_RE.findall(str(document[page_index].get_text())))
    if text_hits < 5:
        return None  # 文本层本身标准号稀疏（扫描件/健康短文档），不判定
    raw_hits = sum(len(_STANDARD_MENTION_RE.findall(raw)) for raw in raw_markdowns)
    if raw_hits * 2 < text_hits:
        return (
            f"Latin/digit loss detected: the source text layer carries {text_hits} "
            f"standard-number mentions but the extraction preserved only {raw_hits}; "
            "text-based extraction dropped Latin/digit runs (re-run with --method ocr)"
        )
    return None


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


def _normalize_part_title(title: str) -> str:
    """多部分标准名称规范：主体要素与分部分名称之间补空格（GBT-C01 执行侧）。

    GB/T 1.1-2020 8.2.2：多部分标准各部分的名称应为"主体要素 第X部分：分部分
    名称"。OCR 常丢失封面标题中"第X部分"前的空格（"标准编写规则第6部分：规程
    标准" → "标准编写规则 第6部分：规程标准"），而正文首页同名标题往往保留。
    仅在紧贴汉字且缺空格时补一个半角空格（已带空格/紧跟英文/非"第N部分："形态
    均不触碰）。
    """
    return re.sub(r"(?<=[\u4e00-\u9fff])第(\d+)部分(?=[：:])", r" 第\1部分", title)


def _is_gbt_1_1_2020(source: Path) -> bool:
    """True for the GB/T 1.1-2020 input that the standard-specific quirk fixes target.

    规则对应: GBT-* 专属修复开关（仅对 GB/T 1.1-2020 输入启用 7.4 版式图恢复等 quirks）。
    """
    return "1.1-2020" in source.stem or "1.1—2020" in source.stem


def _range_dir(output_dir: Path, start: int, end: int) -> Path:
    return output_dir / "parts" / f"pages-{start + 1:03d}-{end + 1:03d}"


def _stage_paths(output_dir: Path, stem: str, *, source_ext: str = "pdf") -> dict[str, Path]:
    """阶段目录布局（naming_specification.txt 第 4 节）：每个表示一个子目录。

    00_source/ 01_extract/ 02_canonical/ 03_ssir/ 04_render/ 05_verify/；
    资产统一放文档根 assets/（SSIR 的 assetRef 相对路径以
    ``assets/images/...`` 引用，渲染器自 03_ssir/ 向上查找）。
    ``source_ext`` 区分源文档类型（pdf → MinerU 识别；docx → docx 导入）。
    """
    return {
        "source": output_dir / "00_source" / f"{stem}.source.{source_ext}",
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
        "render_docx": output_dir / "04_render" / f"{stem}.render.docx",
        "render_report": output_dir / "04_render" / f"{stem}.render-report.json",
        "render_comparison": output_dir / "04_render" / f"{stem}.render-comparison.json",
        "verify": output_dir / "05_verify" / f"{stem}.verify.json",
        "roundtrip": output_dir / "05_verify" / f"{stem}.roundtrip.json",
    }


def _write_manifest(args: argparse.Namespace, state: dict[str, Any], title: str = "", number: str = "", status: str = "in-progress") -> None:
    """写文档索引 manifest.json（naming_specification.txt 第 6 节）。"""
    stem = args.output_stem or args.input.stem
    paths = _stage_paths(args.output_dir, stem,
                         source_ext="docx" if getattr(args, "input_kind", "") == "docx" else "pdf")
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
            "renderDocx": str(paths["render_docx"].relative_to(args.output_dir)),
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
        # GEN-013: 发布/实施日期可能同行（"2021-08-19 发布 2021-09-19 实施"），
        # 逐个识别全部「日期+发布/实施」对，而不是只认行首的日期。
        issued = re.match(r"^(\d{4}-\d{2}-\d{2})\s*发布", compact_line)
        effective = re.match(r"^(\d{4}-\d{2}-\d{2})\s*实施", compact_line)
        for date_pair in re.finditer(r"(\d{4}-\d{2}-\d{2})\s*(发布|实施)", compact_line):
            if date_pair.group(2) == "发布":
                result.setdefault("publication-date", date_pair.group(1))
            else:
                result.setdefault("effective-date", date_pair.group(1))
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


def _replace_cover_title(markdown: str, old_title: str, new_title: str) -> str:
    """Replace the cover H1 title line (and any exact bare-paragraph match)
    after title normalization so normalize's H1==front-matter-title check holds.

    Only touches the exact title text, never a longer line containing it.
    """
    lines = markdown.splitlines()
    changed = False
    for i, line in enumerate(lines):
        content = re.sub(r"^#+\s*", "", line.strip())
        if content == old_title:
            if line.strip().startswith("#"):
                lines[i] = re.sub(r"^(#+\s*).*$", r"\1" + new_title, lines[i])
            else:
                lines[i] = new_title
            changed = True
    return "\n".join(lines) if changed else markdown


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
    state.setdefault("parts", [])

    # 提取方法变更失效（2026-08-31）：auto 抽出的损坏 parts（文本层丢点丢数字）
    # 在改走 OCR 后不能续跑复用——先读旧方法（state["parameters"] 尚未覆盖），
    # 不一致时全部重抽，且删除磁盘上的旧 parts（否则会被下方 "Markdown exists;
    # state was repaired" 分支当成有效产物重新登记，绕过重抽）。
    previous_method = (state.get("parameters") or {}).get("method")
    if previous_method and previous_method != args.method:
        _log(
            f"Extraction method changed {previous_method} -> {args.method}; "
            f"re-extracting all page ranges (previously completed parts are invalid)"
        )
        state["parts"] = []
        state.pop("hybridPasses", None)
        parts_root = args.output_dir / "parts"
        if parts_root.is_dir():
            shutil.rmtree(parts_root)
    state["parameters"] = {"method": args.method, "language": "ch", "formula": True, "table": True}

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

    # 表格块 hybrid-engine 第二遍（GEN-094）：pipeline 表格 TSR 压平"隐藏行表"，
    # hybrid VLM 能恢复逐行结构。只对含表页跑；失败不中断（merge 回退 pipeline 表）。
    if getattr(args, "hybrid_tables", False):
        _run_hybrid_table_passes(args, state)
    else:
        # 默认（未加 --hybrid-tables）不跑 hybrid 第二遍：表格保持 pipeline 原样
        # （原始逻辑）；丢弃历史 hybrid 结果，避免 merge 误用上一轮的替换。
        state.pop("hybridPasses", None)
        state.pop("hybridFailures", None)


# =====================================================================
# 表格块 hybrid-engine 第二遍（GEN-094，2026-09-09）
# ---------------------------------------------------------------------
# 问题类：MinerU pipeline 表格 TSR 只在可见网格线处断行——\"隐藏行表\"（块内
# 逐行叠印、无网格线：GB_T_5171.1-2014 表1 温升限值表、GB_T_755-2025 表13
# 等）被压成单行单元格、数值串粘接后不可逆拆分。hybrid-engine（MinerU
# 2.5-Pro VLM 表格结构识别）能视觉恢复逐行对齐；但其整页正文识别丢数字/拉丁
# 短串，故只取表格块、正文仍用 pipeline 通道（与 GEN-092 同口径：不做整体换
# 后端）。规则对应：GEN-094（extract 含表页跑 hybrid；merge 按（页, 页内序）
# 替换表格块，保留 pipeline 题注/编号；hybrid 缺失/失败/表数不齐时回退）。
# =====================================================================

def _find_content_list(part_dir: Path) -> Path | None:
    """Locate MinerU *_content_list.json（v1 条目表；不是 *_content_list_v2.json）。"""
    candidates = [
        f for f in sorted(part_dir.rglob("*_content_list.json"))
        if f.name.endswith("_content_list.json")
    ]
    return candidates[0] if candidates else None


def _table_entries_from_content_list(cl_path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(cl_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [it for it in data if isinstance(it, dict) and it.get("type") == "table"]


def _pipeline_table_pages(part_dir: Path, base: int = 0) -> list[int]:
    """pipeline content_list 的表格全局页号（文件顺序 = md/转换后表块顺序）。

    MinerU 的 content_list page_idx 是相对本次 invocation 起始页的本地索引
    （-s 11 的单页运行也报 0），需加 base（chunk 起始页）得全局页号。
    """
    cl = _find_content_list(part_dir)
    if cl is None:
        return []
    pages: list[int] = []
    for item in _table_entries_from_content_list(cl):
        try:
            pages.append(int(item["page_idx"]) + base)
        except (KeyError, TypeError, ValueError):
            continue
    return pages


def _hybrid_tables_by_page(part_dir: Path, base: int = 0) -> dict[int, list[str]]:
    """hybrid-engine 输出：全局页 -> 该页表格 HTML 列表（文件顺序 = 页内顺序）。"""
    cl = _find_content_list(part_dir)
    out: dict[int, list[str]] = {}
    if cl is None:
        return out
    for item in _table_entries_from_content_list(cl):
        try:
            page = int(item["page_idx"]) + base
        except (KeyError, TypeError, ValueError):
            continue
        body = item.get("table_body") or item.get("html")
        if not isinstance(body, str) or "<table" not in body.lower():
            continue
        out.setdefault(page, []).append(body)
    return out


def _hybrid_markdown_present(run_dir: Path) -> bool:
    return any(run_dir.rglob("*.md"))


def _run_hybrid_table_passes(args: argparse.Namespace, state: dict[str, Any]) -> None:
    """对含表页跑 hybrid-engine 第二遍；结果登记 state['hybridPasses']。

    失败不抛异常（merge 回退 pipeline 表格块），但记录 state['hybridFailures']
    并在日志显著提示；重跑同一命令可续跑失败区间（resumable）。
    """
    if getattr(args, "input_kind", "pdf") != "pdf":
        return
    completed = {
        item["start"]: item for item in state.get("parts", []) if item.get("status") == "complete"
    }
    if not completed:
        return
    pages: set[int] = set()
    for part in completed.values():
        part_dir = args.output_dir / Path(part["markdown"]).parent
        pages.update(_pipeline_table_pages(part_dir, int(part["start"])))
    if not pages:
        _log("No table pages detected in the pipeline output; skipping hybrid-engine table pass")
        return
    # 连续表页并成一个 invocation（每个 invocation 只有一次模型加载）。
    runs: list[list[int]] = []
    for page in sorted(pages):
        if runs and page == runs[-1][1] + 1:
            runs[-1][1] = page
        else:
            runs.append([page, page])
    existing = {
        item["start"]: item for item in state.get("hybridPasses", []) if item.get("status") == "complete"
    }
    command = _mineru_command()
    done: list[dict[str, Any]] = []
    for start, end in runs:
        run_dir = args.output_dir / "parts" / f"hybrid-table-{start + 1:03d}-{end + 1:03d}"
        prior = existing.get(start)
        if prior and prior.get("end") == end and _hybrid_markdown_present(args.output_dir / prior["dir"]):
            _log(f"Skipping hybrid table pages {start + 1}-{end + 1}: recorded complete")
            done.append(prior)
            continue
        invocation = [
            command, "-p", str(args.input), "-o", str(run_dir), "-b", "hybrid-engine",
            "--effort", "medium", "-l", "ch", "-f", "true", "-t", "true",
            "-s", str(start), "-e", str(end),
        ]
        env = dict(os.environ)
        if getattr(args, "hf_endpoint", None):
            env["HF_ENDPOINT"] = args.hf_endpoint
        env.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        _log(
            f"Starting hybrid-engine table pass for pages {start + 1}-{end + 1} of {args.input.name} "
            "(table rows only; body text stays with the pipeline backend)"
        )
        started = time.monotonic()
        result = subprocess.run(invocation, cwd=ROOT, env=env)
        elapsed = time.monotonic() - started
        run_dir.mkdir(parents=True, exist_ok=True)
        if result.returncode or not _hybrid_markdown_present(run_dir):
            state.setdefault("hybridFailures", []).append(
                {"start": start, "end": end, "returnCode": result.returncode}
            )
            _log(
                f"hybrid-engine table pass FAILED for pages {start + 1}-{end + 1} "
                f"(exit {result.returncode}) after {elapsed / 60:.1f} minutes; "
                "falling back to pipeline table blocks (rerun the same command to retry)"
            )
            _write_json(args.state_file, state)
            continue
        done.append({"start": start, "end": end, "status": "complete", "dir": str(run_dir.relative_to(args.output_dir))})
        _log(f"Completed hybrid table pages {start + 1}-{end + 1} in {elapsed / 60:.1f} minutes")
    if done:
        kept = [item for item in state.get("hybridPasses", []) if item.get("status") != "complete"]
        state["hybridPasses"] = done + kept
        _write_json(args.state_file, state)


def _splice_hybrid_table_blocks(
    raw: str, tbl_pages: list[int], hybrid_by_page: dict[int, list[str]]
) -> tuple[str, int, int]:
    """把 raw 中 pipeline 生成的表格块行替换为 hybrid-engine 行结构。

    对齐：pipeline content_list 的表格顺序 = 转换后 raw 中表块顺序，每个表块
    按 tbl_pages 对应页；hybrid 表按（页, 页内序）匹配。块/页数不齐或该页
    hybrid 表数不足时该表保持 pipeline（不猜测，确定性回退）。返回
    (新文本, 替换表数, 保留 pipeline 表数)。表格题注/编号保留 pipeline 的
    ssir:table 指令行（表号、caption 属性不被 hybrid 正文噪声污染）。
    """
    if not hybrid_by_page or not tbl_pages:
        return raw, 0, 0
    lines = raw.splitlines()
    blocks: list[tuple[int, int]] = []
    index = 0
    while index < len(lines):
        if lines[index].startswith("<!-- ssir:table id="):
            end = index + 1
            while end < len(lines) and lines[end].strip():
                end += 1
            blocks.append((index, end))
            index = end
        else:
            index += 1
    if len(blocks) != len(tbl_pages):
        _log(
            f"Table block/page alignment mismatch ({len(blocks)} blocks vs "
            f"{len(tbl_pages)} content_list tables); keeping pipeline tables"
        )
        return raw, 0, 0
    per_page: dict[int, int] = defaultdict(int)
    replaced = 0
    output: list[str] = []
    prev = 0
    for (start, end), page in zip(blocks, tbl_pages):
        output.extend(lines[prev:start])
        hybrid = hybrid_by_page.get(page, [])
        ordinal = per_page.get(page, 0)
        per_page[page] = ordinal + 1
        if ordinal < len(hybrid):
            converted = html_table_to_csm(hybrid[ordinal], "hybrid", None)
            rows = converted.splitlines()
            if rows and rows[0].startswith("<!-- ssir:table"):
                rows = rows[1:]
            if rows:
                # 保留 pipeline 指令行（题注/编号/id），只换行结构；merge 指令的
                # table 引用同步改指该 id（html_table_to_csm 内部用占位 id）。
                tid = re.search(r'id="([^"]+)"', lines[start])
                if tid:
                    rows = [row.replace('table="mineru-table-hybrid"', f'table="{tid.group(1)}"') for row in rows]
                block = [lines[start]] + [row.replace("](images/", "](assets/images/") for row in rows]
                output.extend(block)
                replaced += 1
                prev = end
                continue
        output.extend(lines[start:end])
        prev = end
    output.extend(lines[prev:])
    return "\n".join(output), replaced, len(blocks) - replaced


_ELLIPSIS_CHARS = ("…", "⋯")  # U+2026 与 U+22EF（中线省略号，部分字体映射）
_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９．", "0123456789.")


def _text_layer_content_lines(pdf: Path) -> list[dict[str, Any]]:
    """Extract content lines (page/x0/y0/text) from the source PDF text layer.

    通用后验的输入基础：文本层是版面真值的唯一权威来源（MinerU OCR 可能丢弃
    纯符号行——如"……"占位行——而文本层完整保留；中文虽可能乱码，但行数、
    坐标、数字、拉丁与标点符号可信）。
    """
    try:
        import pymupdf
    except ImportError:
        return []
    lines: list[dict[str, Any]] = []
    with pymupdf.open(pdf) as document:
        for page_index in range(len(document)):
            page = document[page_index]
            for block in page.get_text("dict")["blocks"]:  # type: ignore[index]
                for line in block.get("lines", []):  # type: ignore[union-attr]
                    text = "".join(span["text"] for span in line["spans"]).strip()  # type: ignore[index]
                    if not text:
                        continue
                    y0 = line["bbox"][1]  # type: ignore[index]
                    x0 = line["bbox"][0]  # type: ignore[index]
                    if y0 < 80:
                        continue  # 页眉（标准号眉线）
                    if y0 > 740 and re.fullmatch(r"[0-9０-９IVXⅣⅤⅧ]+", text):
                        continue  # 页脚页码（奇偶页左右交替，只按内容形态过滤）
                    lines.append({"page": page_index + 1, "x0": x0, "y0": y0, "text": text})
    return lines


def _is_short_ellipsis(text: str) -> bool:
    """Pure ellipsis line (1-6 个 …/⋯)。目录点线（40+ 个 …）不属于内容占位。"""
    t = text.replace(" ", "")
    return 1 <= len(t) <= 6 and set(t) <= set(_ELLIPSIS_CHARS)


def _clause_skeleton(text: str) -> str | None:
    """行首条号骨架：５．８ → 5.8、６ → 6。仅当行首（可带破折号/空白）是
    点分数字链**且后随空白或行尾**时返回——乱码行中段碎片（如 "7b…"）的
    伪编号不匹配，避免把省略号锚到错误位置。"""
    t = text.translate(_FULLWIDTH_DIGITS)
    # 后随空白时空白后不得再是数字（"１ 01" 型目录页码行不算条号）；
    # 后随行尾也可（孤立的章号行）。
    match = re.match(r"^[\s—–\-]*(\d+(?:\.\d+){0,3})(?=\s(?![0-9０-９])|$)", t)
    return match.group(1) if match else None


def _raw_line_starts_with_number(line: str, skeleton: str) -> bool:
    """raw 行（可带 markdown 标题前缀）是否以该条号骨架开头且不吞掉更长编号。"""
    s = line.lstrip("#").strip()
    return bool(re.match(rf"^{re.escape(skeleton)}(?=[^\d.]|$)", s))


def _restore_ellipsis_lines(body: str, pdf: Path) -> str:
    """Generic restoration of OCR-dropped pure-ellipsis lines (GEN-092 后验补盲)。

    现象（GB_T_20001.6-2017 等规程/指南标准的示例文档）：MinerU OCR 丢弃
    纯"……"占位行（5.3/5.4.1/5.4.2/5.4.3/5.7.1 a)/5.8/5.9/6.2 末尾等），
    源 PDF 文本层完整保留。恢复分两类：

    - 正文省略号：以省略号行之后的**下一个带条号骨架的文本层行**为锚（锚定到
      raw 中该骨架的最后一个出现位置，靠单调游标保持插入顺序），把"……"插到
      该行之前；无后随锚且位于最后一页末行时追加到文末（6.2 末尾型）。
    2026-09-07 用户裁定：不再做"表格单元格内按……切段、前后加 <br> 让省略号独占
    一行"的重建（单元格行结构恢复整条取消；正文恢复保留）——需要时在 canonical
    人工处理单元格换行。

    保守原则：锚点/长度无法可靠匹配时不改（不猜测）；raw 已在插入点附近有
    短省略号行时跳过（防重复）。
    """
    text_lines = _text_layer_content_lines(pdf)
    if not text_lines:
        return body
    ellipsis_indexes = [i for i, line in enumerate(text_lines) if _is_short_ellipsis(line["text"])]
    if not ellipsis_indexes:
        return body

    raw_lines = body.split("\n")
    insert_before: list[tuple[int, str]] = []  # (raw 行号, 插入文本)，逆序应用
    cursor = 0
    consumed: set[int] = set()

    def _table_like(line_index: int) -> bool:
        """省略号行是否位于表格单元格内：同页存在 **≥2 个** |Δy|≤40 且
        |Δx|≥60 的其他内容行（表格网格的同行多列特征；单条缩进行/居中行
        如示例引导语不会误判）。"""
        me = text_lines[line_index]
        hits = 0
        for other in text_lines:
            if other["page"] != me["page"]:
                continue
            if abs(other["y0"] - me["y0"]) <= 40 and abs(other["x0"] - me["x0"]) >= 60:
                hits += 1
                if hits >= 2:
                    return True
        return False

    # 第一遍：正文省略号（非表格），记录插入点。
    for e in ellipsis_indexes:
        if _table_like(e):
            continue
        # 下一个带条号骨架的文本层行——必须与省略号同页（跨页会把前言/引言
        # 中的省略号锚到正文章节，如 p3 前言省略号误锚到 p5 "2 规范性引用文件"）。
        f_index = None
        for j in range(e + 1, len(text_lines)):
            if text_lines[j]["page"] != text_lines[e]["page"]:
                break
            if _clause_skeleton(text_lines[j]["text"]):
                f_index = j
                break
        if f_index is None:
            # 无后随锚：仅当它是整份文档最后一页的末行内容时追加到文末
            # （如 6.2 末尾的"……"）。
            last_content = text_lines[-1]
            if text_lines[e] is last_content or (
                text_lines[e]["page"] == last_content["page"]
                and text_lines[e]["y0"] >= last_content["y0"]
            ):
                marker = next(
                    (ri for ri in range(len(raw_lines) - 1, -1, -1) if raw_lines[ri].startswith("<!-- /ssir:mineru-pages -->")),
                    len(raw_lines),
                )
                insert_before.append((marker, "……"))
                cursor = len(raw_lines)
            continue
        skeleton = _clause_skeleton(text_lines[f_index]["text"])
        if skeleton is None:
            continue
        # raw 中该骨架的最后一个出现位置（须在游标之后）——同号重复时
        # 省略号属于较早出现与较晚出现之间的位置，取后者。
        found = None
        for ri in range(len(raw_lines) - 1, cursor - 1, -1):
            if _raw_line_starts_with_number(raw_lines[ri], skeleton):
                found = ri
                break
        if found is None:
            continue
        if any(_is_short_ellipsis(raw_lines[k].strip()) for k in range(max(0, found - 3), found)):
            cursor = found + 1
            continue
        insert_before.append((found, "……"))
        cursor = found + 1
        consumed.add(e)

    if not insert_before:
        return body

    for ri, text in sorted(insert_before, key=lambda item: item[0], reverse=True):
        raw_lines.insert(ri, text)
    return "\n".join(raw_lines)


def merge(args: argparse.Namespace, state: dict[str, Any]) -> Path:
    # 规则对应: GEN-005（按原始页序合并、带页码范围标记）、GEN-010（页眉页脚回收）、
    # GEN-030（附录标题重组）、GEN-019（显式 front-matter 优先）。
    expected = list(range(0, state.get("pageCount", 0), args.chunk_size))
    completed = {item["start"]: item for item in state.get("parts", []) if item.get("status") == "complete"}
    missing = [start + 1 for start in expected if start not in completed]
    if missing:
        raise RuntimeError(f"Cannot merge: MinerU output is missing for pages starting at {missing}")

    # hybrid-engine 表格第二遍结果（GEN-094）：页 -> 该页 hybrid 表格 HTML。
    # 只用于替换同页 pipeline 表块的行结构；题注/正文仍以 pipeline 为准。
    # 默认关闭（原始逻辑：表格保持 pipeline 原样）；仅 --hybrid-tables 显式
    # 启用时才读取 hybridPasses 做行替换。
    hybrid_by_page: dict[int, list[str]] = {}
    hybrid_image_dirs: list[Path] = []
    if getattr(args, "hybrid_tables", False):
        for run in state.get("hybridPasses", []):
            if run.get("status") != "complete":
                continue
            run_dir = args.output_dir / run["dir"]
            if not run_dir.is_dir():
                continue
            for page, htmls in _hybrid_tables_by_page(run_dir, int(run["start"])).items():
                hybrid_by_page.setdefault(page, []).extend(htmls)
            hybrid_image_dirs.extend(d for d in run_dir.rglob("images") if d.is_dir())
    hybrid_replaced = 0
    hybrid_kept = 0

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
        if hybrid_by_page:
            tbl_pages = _pipeline_table_pages(source.parent, int(part["start"]))
            if tbl_pages:
                raw, n_replaced, n_kept = _splice_hybrid_table_blocks(raw, tbl_pages, hybrid_by_page)
                if n_replaced:
                    _log(
                        f"hybrid table rows spliced: {n_replaced} replaced / {n_kept} kept "
                        f"(pages {part['start'] + 1}-{part['end'] + 1})"
                    )
                    hybrid_replaced += n_replaced
                    hybrid_kept += n_kept
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

    # hybrid 表行内嵌图（如有）同样落入文档根 assets/images/（与 pipeline 图一致）。
    if hybrid_replaced and hybrid_image_dirs:
        image_target = args.output_dir / "assets" / "images"
        image_target.mkdir(parents=True, exist_ok=True)
        for image_dir in hybrid_image_dirs:
            for image in image_dir.iterdir():
                if image.is_file() and not (image_target / image.name).exists():
                    shutil.copy2(image, image_target / image.name)

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
    raw_title = args.title or _usable_title(real_heading, number)
    title = _normalize_part_title(raw_title)
    # 标题规范化（如补"第N部分"前空格）后，封面 H1 必须同步，否则
    # normalize 的 "H1 title must exactly match front matter title" 校验失败。
    if title != raw_title:
        parts_raw[0] = _replace_cover_title(parts_raw[0], raw_title, title)
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
    merged_text = "\n".join(lines).rstrip() + "\n"
    # 通用省略号恢复（GEN-092 后验补盲）：OCR 常丢弃纯"……"占位行与表格
    # 单元格行结构，源 PDF 文本层完整保留——merge 阶段从文本层恢复。
    merged_text = _restore_ellipsis_lines(merged_text, args.input)
    # 表注锚点上标字母回收（CSM-OCR-015）：MinerU OCR 丢表头/单元格上标字母、只留
    # 表注定义行（GB_T_20001.10-2014 表1 型）→ 从源 PDF 文本层补回单元格尾部标记。
    merged_text, recovered_markers = _recover_table_note_markers(merged_text, args.input)
    if recovered_markers:
        _log(f"Recovered {recovered_markers} table note marker(s) from the source PDF text layer")
    destination.write_text(merged_text, encoding="utf-8")
    provenance = paths["provenance"]
    provenance_payload: dict[str, Any] = {
        "sourcePdf": str(args.input.resolve()), "sourceSha256": state["sourceSha256"], "pageCount": state["pageCount"],
        "backend": state["backend"], "parameters": state["parameters"], "parts": sources,
    }
    if hybrid_replaced:
        provenance_payload["tableBackend"] = "mineru hybrid-engine (targeted table pages; body: mineru pipeline)"
        provenance_payload["hybridTableReplacement"] = {"replaced": hybrid_replaced, "keptPipeline": hybrid_kept}
        provenance_payload["hybridPasses"] = [
            {"pages": [run["start"] + 1, run["end"] + 1], "dir": run["dir"]}
            for run in state.get("hybridPasses", []) if run.get("status") == "complete"
        ]
    _write_json(provenance, provenance_payload)
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
        # 以前行为：normalize 失败时仍保留 merged 作为 fallback；不静默退出，
        # 防止无 canonical 时直接返回 None 导致流水线异常终止（GB_T_5171.1-2014 类）。
        # AGENTS.md §0.2/§0.4：不伪造数据，不修个例数据；此处仅保留原中间产物以供人工复核。
        print("CSM normalization needs review; MinerU extraction and provenance remain available (canonical not produced).", file=sys.stderr)
        # 回退：不覆盖已有 canonical（若存在），不生成新 canonical，返回 None 由主入口处理下游缺失。
        return None
    # 条文脚注回收（CSM-OCR-014）：MinerU 常把上标脚注标记与正文粘连（“—2003”+1)
    # →“—20031”），页底解释行被当普通正文；且 normalize 对 raw 里的 GFM
    # “[^N]: …” 定义行在内存归类为 footnote 后并不回写 canonical（实测丢失）。
    # 因此脚注回收只能作用于 normalize **刚生成**的 canonical：在本轮全流程
    # （--stage all 且无 canonical，或显式 --stage finalize 重生成）的 normalize
    # 之后、parse 之前执行——此刻 canonical 是本轮产物，不是人工编辑的 curated
    # 基线；从 canonical 续跑的半程路径（_run_from_existing_canonical）不经过本
    # 函数，绝不会改写已存在的 curated canonical（AGENTS.md §2）。幂等：已有
    # “[^N]” 标记与定义时不重复写。
    if args.input.suffix.lower() == ".pdf" and canonical.is_file():
        recovered = _recover_pdf_footnotes(canonical, args.input)
        if recovered:
            _log(f"Recovered {recovered} footnote(s) from the source PDF text layer into {canonical.name}")
    _log("Parsing normalized CSM into SSIR JSON")
    if subprocess.run(parsed, cwd=ROOT).returncode:
        print("SSIR parsing needs review; normalized CSM remains available.", file=sys.stderr)
        return None
    _log(f"SSIR JSON written: {ssir}\n")
    if args.input.suffix.lower() == ".pdf":
        # 版面几何印记仅对 PDF 源有效（读取源 PDF 的矢量几何/裁剪尺寸）。
        _stamp_example_styles(ssir, args.input)
        _stamp_figure_source_sizes(ssir, args.input)
        _stamp_side_by_side_layout(ssir, args.output_dir / "parts")
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


def _stamp_figure_source_sizes(ssir_path: Path, source_pdf: Path) -> None:
    """Record each figure's original layout size (pt) from the source PDF.

    MinerU 裁剪图常以高于原版的像素密度导出（GB_T_23132-2024 实测约 2.1-3x），
    渲染端按固有 72dpi 尺寸输出会远超原图（图1 42x76pt 被放大到 126x212pt）。
    本步骤把每张图在源 PDF 中的版面矩形尺寸写入 SSIR figure 的
    sourceWidth/sourceHeight（pt），渲染端据此还原原图尺寸（GEN-076）。

    匹配依据：裁剪图保持宽高比，源 PDF 图像矩形与资产宽高比接近
    （|Δaspect| < 0.12）且像素密度比在合理范围（[1.2, 4.0] px/pt）者胜出；
    每个源矩形只分配给一个资产（贪心：全局最接近宽高比者优先），防止
    两个相似裁剪图抢同一矩形（表2 旋转式 试验区域分割/插入角度 两张方形图）。
    **封面徽标/装饰小图不参与匹配**（第 1 页上高度 < 100pt 的矩形——标准封面
    的徽标与 logo，非内容图；正文图不会出现在封面），否则宽高比接近的
    内容图会误配到封面徽标矩形（如 表2 往复式 试验区域分割图 2.04 宽高比
    误配封面 GB_logo 113.7x56.9）。

    两类图片匹配不到独立矩形：
    - 子图裁剪（图2 卷曲判定图被拆分出的 a)/b) 无编号图块）：宽高比与整图
      矩形不符 → 回退到**文档像素密度估计**：取已匹配资产的 px/pt 中位数
      （OCR 重渲染页密度整本稳定，~200dpi/72 ≈ 2.78；扫描型 PDF 无任何匹配
      时直接默认 2.78），size = 像素/密度，仍接近原图尺寸；
    - 表格单元格内图（GBT-X02 表中图，`![](ref)` 挂在 table cell 文本上，
      如 表2 试验区域分割/插入角度示意图）：同样参与匹配与密度回退，尺寸
      写入 table["cellImageSizes"] = {ref: [w, h]}，渲染端按原尺寸（上限
      单元格宽）显示。

    注意 assetRef 是相对文档根的（<docroot>/assets/images/...），SSIR 位于
    03_ssir/ 子目录——必须沿祖先目录向上找（同 pdf_renderer._resolve_asset）。
    此前只按 ssir_path.parent / ref 解析导致所有图都拿不到尺寸（03_ssir/
    下没有 assets/），是"图太大"的直接根因。
    """
    try:
        import fitz  # type: ignore
        from PIL import Image as PILImage  # type: ignore
    except Exception:
        return
    try:
        data = json.loads(ssir_path.read_text(encoding="utf-8"))
    except Exception:
        return
    figures = data.get("figures") or []
    if not figures:
        return
    try:
        with fitz.open(source_pdf) as document:
            # (rw, rh, page_index)；第 1 页（封面）的徽标/装饰小图
            # （高 < 100pt）不参与匹配——封面徽标由 config/emblems/ 独立处理，
            # 非内容图；宽高比接近的内容图误配到徽标矩形会得到错误尺寸。
            rects: list[tuple[float, float, int]] = []
            for page_index, page in enumerate(document):
                for info in page.get_image_info():
                    r = info["bbox"]
                    rw, rh = r[2] - r[0], r[3] - r[1]
                    if rw >= 10 and rh >= 10 and not (page_index == 0 and rh < 100):
                        rects.append((rw, rh, page_index))
    except Exception:
        return
    if not rects:
        return

    def _resolve_asset(ref: str) -> Path:
        # assetRef 相对文档根；SSIR 在 03_ssir/ 时沿祖先目录向上找。
        for parent in ssir_path.parents:
            candidate = parent / ref
            if candidate.is_file():
                return candidate
        return ssir_path.parent / ref

    def _pixel_size(asset: Path) -> tuple[int, int] | None:
        try:
            with PILImage.open(asset) as im:
                aw, ah = im.size
        except Exception:
            return None
        if aw < 20 or ah < 20:
            return None
        return aw, ah

    # 候选图片：figures 注册表 + 表格单元格内图（GBT-X02 表中图）。
    cell_image_re = re.compile(r"!\[(?:[^\]]*)\]\(([^)]+)\)")
    # (kind, owner, ref, (aw, ah))
    candidates: list[tuple[str, dict[str, Any], str, tuple[int, int]]] = []
    seen_refs: set[str] = set()
    for figure in figures:
        ref = figure.get("assetRef")
        if not ref or ref in seen_refs:
            continue
        asset = _resolve_asset(ref)
        size = _pixel_size(asset) if asset.is_file() else None
        if size:
            seen_refs.add(ref)
            candidates.append(("figure", figure, ref, size))
    for table in data.get("tables") or []:
        for row in table.get("rows") or []:
            for cell in row.get("cells") or []:
                for match in cell_image_re.finditer(str(cell.get("text", ""))):
                    ref = match.group(1)
                    if ref in seen_refs:
                        continue
                    asset = _resolve_asset(ref)
                    size = _pixel_size(asset) if asset.is_file() else None
                    if size:
                        seen_refs.add(ref)
                        candidates.append(("table", table, ref, size))
    if not candidates:
        return

    # 贪心匹配：全局最小 |Δaspect| 的 (候选, 矩形) 对先占位，矩形不重复分配。
    used: set[int] = set()
    matched: dict[str, tuple[float, float]] = {}
    density_ratios: list[float] = []
    remaining = list(candidates)
    while remaining:
        best_pair: tuple[float, int, int] | None = None
        for ci, (kind, owner, ref, (aw, ah)) in enumerate(remaining):
            aspect = aw / ah
            for ri, (rw, rh, _page_index) in enumerate(rects):
                if ri in used:
                    continue
                aspect_diff = abs(aspect - rw / rh)
                if aspect_diff >= 0.12:
                    continue
                res_w = aw / rw
                res_h = ah / rh
                if not (1.2 <= res_w <= 4.0 and 1.2 <= res_h <= 4.0):
                    continue
                if best_pair is None or aspect_diff < best_pair[0]:
                    best_pair = (aspect_diff, ci, ri)
        if best_pair is None:
            break
        _, ci, ri = best_pair
        kind, owner, ref, (aw, ah) = remaining.pop(ci)
        rw, rh, _page_index = rects[ri]
        used.add(ri)
        matched[ref] = (rw, rh)
        density_ratios.append(aw / rw)
        density_ratios.append(ah / rh)
    # 无匹配（扫描型 PDF：源页是整页位图，宽高比/密度对不上任何内容裁剪图）时
    # 回退到 MinerU OCR 重渲染默认 200dpi/72 ≈ 2.78 px/pt（GB_T_23132-2024
    # 实测匹配中位数 2.77 一致）。
    density = sorted(density_ratios)[len(density_ratios) // 2] if density_ratios else (200 / 72)

    stamped = 0
    for kind, owner, ref, (aw, ah) in candidates:
        if ref in matched:
            rw, rh = matched[ref]
        elif density:
            rw, rh = aw / density, ah / density
        else:
            continue
        if kind == "figure":
            owner["sourceWidth"] = round(rw, 1)
            owner["sourceHeight"] = round(rh, 1)
        else:
            owner.setdefault("cellImageSizes", {})[ref] = [round(rw, 1), round(rh, 1)]
        stamped += 1
    if stamped:
        ssir_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        _log(f"Figure source sizes stamped from source PDF: {stamped}/{len(candidates)} images (density={density and round(density, 2)} px/pt)")


def _stamp_side_by_side_layout(ssir_path: Path, parts_dir: Path) -> None:
    """Detect side-by-side figure/annotations from MinerU geometry and mark them
    as a side-by-side group so the renderer lays them out on one row (无边框定位
    容器，等价 HTML div 布局——GB_T_23132-2024 图2 的 a)/b) 并列子图型).

    依据 MinerU OCR 中间产物 middle.json 的版面几何（preproc_blocks 的 bbox，
    pt 坐标，与源 PDF 同页面尺寸）：同一页内 **y 区间重叠、x 区间分离**的多个
    image block 判定为并列组；组内按 x 升序分配 sideBySideColumn。图块附带
    的图内文字 span（L≤0.4 mm 等）按 span bbox 的 x 中心归属列。命中后把
    SSIR content（figure 引用与相邻文字段）写入 sideBySideGroup/sideBySideColumn。

    通用性：不依赖具体文档——任何"同一水平带内并排的 2-3 块内容"都命中；
    无并列证据的图保持原样（单列不组）。
    """
    try:
        data = json.loads(ssir_path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not parts_dir.is_dir():
        return
    middle_files = sorted(parts_dir.rglob("*_middle.json"))
    if not middle_files:
        return
    # 收集每页的 image block 几何（含图内文字 span 的 bbox 与内容）。
    # page_blocks[page_idx] = {"images": [(image_path_basename, x0,y0,x1,y1), ...],
    #                          "spans": [(text, x0,y0,x1,y1), ...]}
    page_blocks: dict[int, dict[str, list[tuple]]] = {}
    for middle in middle_files:
        try:
            raw = json.loads(middle.read_text(encoding="utf-8"))
        except Exception:
            continue
        for info in raw.get("pdf_info") or []:
            page_idx = info.get("page_idx")
            if page_idx is None:
                continue
            page = page_blocks.setdefault(page_idx, {"images": [], "spans": []})
            for block in info.get("preproc_blocks") or []:
                if block.get("type") != "image":
                    continue
                bbox = block.get("bbox")
                if not bbox or len(bbox) != 4:
                    continue
                image_path = None
                for sub in block.get("blocks") or []:
                    for line in sub.get("lines") or []:
                        for span in line.get("spans") or []:
                            if span.get("type") == "image" and span.get("image_path"):
                                image_path = Path(span["image_path"]).name
                            elif span.get("type") == "text" and span.get("content"):
                                sb = span.get("bbox")
                                if sb and len(sb) == 4:
                                    page["spans"].append((str(span["content"]).strip(), sb[0], sb[1], sb[2], sb[3]))
                if image_path:
                    page["images"].append((image_path, bbox[0], bbox[1], bbox[2], bbox[3]))
    if not page_blocks:
        return

    # 图块 assetRef 索引（basename）。
    ref_by_basename: dict[str, str] = {}
    for figure in data.get("figures") or []:
        ref = figure.get("assetRef")
        if ref:
            ref_by_basename.setdefault(Path(ref).name, figure["id"])

    # 遍历 SSIR 树找 content 元素（figureRef / textContent 匹配用）。
    contents: list[dict] = []

    def _walk(node: dict) -> None:
        for content in node.get("contentElements") or []:
            contents.append(content)
        for child in node.get("children") or []:
            _walk(child)

    _walk(data.get("structuralRoot") or {})
    content_by_figure = {c.get("figureRef"): c for c in contents if c.get("presentationType") == "figure"}

    # 每页检测并列组：image blocks 两两 y 重叠（>60% 小高）且 x 分离 → 组内按 x 排序。
    def _norm(t: str) -> str:
        return re.sub(r"\s+", "", t).replace("（", "(").replace("）", ")")

    def _content_search_text(content: dict) -> list[str]:
        """content 的可搜索文本：段落取 textContent；列项取 marker+text。"""
        if content.get("presentationType") == "list":
            return [_norm(f"{item.get('marker', '')}{item.get('text', '')}") for item in content.get("listItems") or []]
        return [_norm(str(content.get("textContent", "")))]

    stamped_group = 0
    for page_idx in sorted(page_blocks):
        images = sorted(page_blocks[page_idx]["images"], key=lambda item: item[1])  # 按 x0
        spans = page_blocks[page_idx]["spans"]
        used: set[int] = set()
        for i, (name_i, x0i, y0i, x1i, y1i) in enumerate(images):
            if i in used:
                continue
            group = [i]
            used.add(i)
            # 贪心：与已组内任一成员 y 重叠且 x 分离的都并入（上限 3 列——用户
            # 描述"并列的两部分或三部分内容"；4+ 并排的罕见版面不猜测）。
            changed = True
            while changed:
                changed = False
                for j, (name_j, x0j, y0j, x1j, y1j) in enumerate(images):
                    if j in used or len(group) >= 3:
                        continue
                    for k in group:
                        _, _, y0k, _, y1k = images[k]
                        x0k, x1k = images[k][1], images[k][3]
                        overlap = min(y1k, y1j) - max(y0k, y0j)
                        small_h = min(y1k - y0k, y1j - y0j)
                        x_separated = x1k <= x0j or x1j <= x0k
                        if small_h > 0 and overlap > 0.6 * small_h and x_separated:
                            group.append(j)
                            used.add(j)
                            changed = True
                            break
                    if changed:
                        break
            if len(group) < 2:
                continue
            group.sort(key=lambda k: images[k][1])  # x 升序 → 列序
            group_x0 = min(images[k][1] for k in group)
            group_x1 = max(images[k][3] for k in group)
            group_id = f"p{page_idx:03d}-g{stamped_group:02d}"
            # image → 对应 figure content。
            fig_col: dict[str, int] = {}
            for col, k in enumerate(group):
                name = images[k][0]
                figure_id = ref_by_basename.get(name)
                if figure_id:
                    fig_col[figure_id] = col
            if not fig_col:
                continue
            # span 归属列：x 中心与各列图 x 区间距离最近者。
            col_ranges = []
            for k in group:
                col_ranges.append((images[k][1], images[k][3]))
            span_col: dict[str, int] = {}
            for span in spans:
                text, sx0, sy0, sx1, sy1 = span
                center = (sx0 + sx1) / 2
                best_col, best_dist = 0, 1e18
                for col, (cx0, cx1) in enumerate(col_ranges):
                    dist = 0.0 if cx0 <= center <= cx1 else min(abs(center - cx0), abs(center - cx1))
                    if dist < best_dist:
                        best_col, best_dist = col, dist
                if best_dist < (group_x1 - group_x0) / len(col_ranges):
                    span_col[text] = best_col
            # 写标：figure content。
            hit = False
            for figure_id, col in fig_col.items():
                content = content_by_figure.get(figure_id)
                if content is not None:
                    content["sideBySideGroup"] = group_id
                    content["sideBySideColumn"] = col
                    hit = True
            # 写标：图内文字（与 span 文本一致的段落/列项，含全角括号归一）。
            # 只打标与本组 figure 同父节点的 content，避免跨节点误组。
            parent_ids = {c.get("parentNodeId") for c in contents if c.get("sideBySideGroup") == group_id}
            for text, col in span_col.items():
                n = _norm(text)
                for content in contents:
                    if content.get("sideBySideGroup") or content.get("parentNodeId") not in parent_ids:
                        continue
                    if n in _content_search_text(content):
                        content["sideBySideGroup"] = group_id
                        content["sideBySideColumn"] = col
                        hit = True
                        break
            if hit:
                stamped_group += 1
                _log(f"Side-by-side group {group_id}: page {page_idx + 1}, {len(group)} columns "
                     f"({' + '.join(images[k][0][:8] for k in group)})")
    if stamped_group:
        ssir_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        _log(f"Side-by-side layout stamped: {stamped_group} group(s)")


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


def _build_parser() -> argparse.ArgumentParser:
    """CLI 参数定义（独立函数便于单测断言默认值，如 --hybrid-tables 默认关闭）。"""
    parser = argparse.ArgumentParser(description="Run the full standard pipeline: Word (.docx/.doc, default) or PDF → MinerU PDF recognition (when the input is PDF) → SSIR parse → round-trip verification → optional rendering (PDF + content-equivalent docx).")
    parser.add_argument("file", nargs="?", type=str, default=None,
                        help="standard file name resolved under corpus/golden/ (e.g. T_ZZB_2224-2021, T_ZZB_2224-2021.docx or T_ZZB_2224-2021.pdf). "
                             "Word 输入默认优先（docx/doc），未找到再回退 PDF 做 MinerU 识别。 "
                             "Shortcut mode: implies --stage all --roundtrip --render so one command runs the whole pipeline. "
                             "若 out/mineru/<ID>/02_canonical/<ID>.canonical.md 已存在，则跳过 OCR/PDF 抽取与 "
                             "normalize，直接从 canonical 续跑（等同 tools/reprocess_canonical.py）。")
    parser.add_argument("--input", type=Path, help="input document of the national standard (alternative to the positional file name; full path or relative path; .docx/.doc/.pdf)")
    parser.add_argument("--output-dir", type=Path, help="output directory (default: out/mineru/<input-stem>)")
    parser.add_argument("--output-stem", type=str, help="output filename stem for merged CSM/SSIR/PDF artifacts (default: input file name without the extension)")
    parser.add_argument("--front-matter-json", type=Path, help="optional JSON object with additional CSM front matter keys merged into the merged document (e.g. {\"ics\": \"01.120\", \"issuer\": \"...\"})")
    parser.add_argument("--standard-number", type=str, help="standard number written into the CSM front matter (default: inferred from the extraction, e.g. GB/T 10401-2023)")
    parser.add_argument("--title", type=str, help="standard title written into the CSM front matter (default: first H1 from the extraction)")
    parser.add_argument("--chunk-size", type=int, default=18, help="Pages per restartable MinerU invocation (default: 18).")
    parser.add_argument("--method", choices=("auto", "ocr", "txt"), default="auto", help="MinerU extraction method (default: auto). Use ocr when the PDF text layer loses Latin/digit runs (MinerU's txt extraction can drop them while pymupdf reads them fine).")
    parser.add_argument("--hybrid-tables", action="store_true",
                        help="enable the targeted hybrid-engine table pass (GEN-094): after extraction, table pages are additionally recognized with hybrid-engine (VLM) and rebuilt from its visual rows. Off by default (the VLM pass is slow) — tables then stay exactly as the MinerU pipeline backend produced them")
    parser.add_argument("--hf-endpoint", default=None,
                        help="HuggingFace endpoint used to download the hybrid-engine (VLM) models (default: the HF_ENDPOINT environment variable, else https://hf-mirror.com)")
    parser.add_argument("--stage", choices=("extract", "merge", "finalize", "all"), default="all")
    parser.add_argument("--roundtrip", action="store_true", help="Run CSM canonical -> SSIR -> CSM render.md -> verify round-trip verification after parsing.")
    parser.add_argument("--render", action="store_true", help="Render parsed SSIR to PDF and write a comparison report.")
    parser.add_argument("--toc-depth", default="2", help="Maximum numbered TOC level for --render (positive integer or all; default: 2).")
    return parser


def main() -> int:
    # 规则对应（流水线阶段 → 规则层）: extract=GEN-002/003；merge=GEN-005/010—019/030；
    # normalize=GEN-031—034；build=GEN-050/052；verify=GEN-051/090/091 + 三层合规
    # （GEN→GBT→P10，见 compliance.py）；render=GEN-070—076。
    parser = _build_parser()
    args = parser.parse_args()
    if not args.input and not args.file:
        parser.error("an input is required: pass a file name resolved under corpus/golden/ (e.g. T_ZZB_2224-2021) or --input PATH")
    if args.input and args.file:
        parser.error("pass either a positional file name or --input, not both")
    if args.file:
        # 快捷模式：文件名默认在 corpus/golden/ 下解析。Word 输入默认优先
        # （docx/doc），未找到才回退 PDF 做 MinerU 识别；也允许子路径。
        file_path = Path(args.file)
        if file_path.is_file():
            args.input = file_path
        else:
            candidate = ROOT / "corpus" / "golden" / args.file
            # 注意：不能用 with_suffix(".pdf")——标准号含点（GB_T_1.1-2020）时
            # Path 会把 ".1-2020" 当成后缀替换成 GB_T_1.pdf；直接整体拼后缀保留点。
            resolved = None
            for ext in ("", ".docx", ".doc", ".pdf"):
                probe = candidate if not ext else ROOT / "corpus" / "golden" / f"{args.file}{ext}"
                if probe.is_file():
                    resolved = probe
                    break
            if resolved is None:
                parser.error(f"file not found under corpus/golden/: {args.file!r} (looked for docx/doc, then pdf)")
            args.input = resolved
        # 单命令完成全部：导入/提取 + 渲染 + 回环验证（与 README「一条命令」承诺一致）。
        args.roundtrip = True
        args.render = True
    suffix = args.input.suffix.lower() if args.input else ""
    if not args.input or not args.input.is_file() or suffix not in (".pdf", ".docx", ".doc"):
        parser.error(f"input must be an existing PDF or Word (.docx/.doc) document: {args.input}")
    args.input_kind = "pdf" if suffix == ".pdf" else "docx"
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
    _log(f"Input {'Word document' if args.input_kind == 'docx' else 'PDF'}: {args.input.resolve()}")
    _log(f"Output directory: {args.output_dir.resolve()}")
    _log(f"Stage: {args.stage}; round-trip: {args.roundtrip}; render after parsing: {args.render}")

    try:
        if args.input_kind == "docx":
            # Word 输入：docx 导入（替代 MinerU 识别）→ finalize → roundtrip/render。
            return _run_docx_input(args, state)
        # 已有 curated canonical（02_canonical/<stem>.canonical.md）时，默认
        # --stage all 不再重跑 OCR/PDF 抽取/合并/normalize（防旧 raw 覆盖人工
        # 编辑基线，AGENTS.md §2），直接从 canonical 续跑下游（功能等同
        # tools/reprocess_canonical.py）。显式 --stage extract/merge/finalize 除外。
        canonical_path = args.output_dir / "02_canonical" / f"{args.output_stem or args.input.stem}.canonical.md"
        if args.stage == "all" and canonical_path.is_file():
            _log(f"Existing curated canonical found: {canonical_path}")
            _log("Skipping OCR/PDF extraction, merge and normalize; re-running from canonical")
            return _run_from_existing_canonical(args, state, canonical_path)
        # 文本层质量预检（2026-08-31）：默认 auto 模式下，若源 PDF 文本层呈典型
        # 损坏特征（孤立 "4."/"2." 行、截断标准号 "GB/T2423."），MinerU 直接抽取
        # 会丢点丢数字——自动改走 OCR；显式 --method 时尊重用户选择。
        if args.method == "auto":
            damage_reason = _detect_broken_text_layer(args.input)
            if damage_reason:
                _log(f"Text-layer quality check: {damage_reason}; forcing --method ocr")
                args.method = "ocr"
        if args.stage in {"extract", "all"}:
            extract(args, state)
        if args.stage == "extract":
            _log("Extraction stage complete. Run with --stage all to merge and parse after all page ranges finish.")
            return 0
        # 拉丁/数字丢失后验（2026-08-31，GB_T_15835-2011/GB_T_23132-2024 类）：
        # 文本层健康但 MinerU txt/auto 抽取按字体编码丢拉丁整段（"GB/T 1.1—2020"
        # → "/ — "）。GEN-092 预检只在抽取**前**看文本层损坏特征，覆盖不到这类；
        # 这里在抽取**后**对比文本层与 raw 的标准号提及数，命中则自动强制 OCR
        # 重抽（extract 的 previous_method 不一致逻辑会失效旧 parts）。显式
        # --method 尊重用户选择，不自动改。
        if args.method == "auto" and state.get("parts"):
            raw_markdowns = []
            for part in state["parts"]:
                if part.get("status") != "complete":
                    continue
                markdown_path = args.output_dir / part["markdown"]
                if markdown_path.is_file():
                    raw_markdowns.append(markdown_path.read_text(encoding="utf-8", errors="replace"))
            latin_reason = _latin_loss_check(raw_markdowns, args.input)
            if latin_reason:
                _log(f"Latin-loss check: {latin_reason}; forcing --method ocr and re-extracting")
                args.method = "ocr"
                extract(args, state)
        merged = merge(args, state)
        _log(f"Merged MinerU Markdown: {merged}")
        if args.stage == "merge":
            _write_manifest(args, state)
            return 0
        ssir = finalize(args, merged)
        paths = _stage_paths(args.output_dir, args.output_stem or args.input.stem)
        _post_parse_verify_render(args, state, paths, ssir)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _log("Workflow completed successfully")
    return 0


def _run_docx_input(args: argparse.Namespace, state: dict[str, Any]) -> int:
    """Word 输入全流程：docx 导入（替代 MinerU 识别）→ finalize → roundtrip/render。

    golden 里只放一个 docx（例如上一轮 04_render/<ID>.render.docx）时，从零
    重建整套阶段目录：00_source 永久保留原件（.source.docx + 校验和）→
    01_extract 写入 docx 导入得到的 canonical 级 CSM（assets/images 位图落文档根
    assets/）→ normalize → parse → roundtrip → render（PDF + doc_1 docx）。
    规则对应：source=GEN-002；finalize=GEN-031—034/050；render=GEN-070—076。
    """
    from leleby_ssir.docx_importer import docx_metadata, docx_to_csm_markdown

    stem = args.output_stem
    if not stem:
        stem = args.input.stem
        # golden 里放回 render.docx 时剥掉 representation token（*.render.docx）。
        if stem.lower().endswith(".render"):
            stem = stem[: -len(".render")]
    args.output_stem = stem
    state["outputStem"] = stem
    paths = _stage_paths(args.output_dir, stem, source_ext="docx")
    for stage_path in paths.values():
        stage_path.parent.mkdir(parents=True, exist_ok=True)
    if not paths["source"].is_file():
        shutil.copy2(args.input, paths["source"])
    source_sha256 = state.get("sourceSha256") or hashlib.sha256(args.input.read_bytes()).hexdigest()
    state["sourceSha256"] = source_sha256
    paths["checksum"].write_text(f"sha256:{source_sha256}\n", encoding="utf-8")

    number = args.standard_number or ""
    title = args.title or ""
    if args.stage in {"extract", "all"}:
        _log(f"Importing Word document into canonical-level CSM: {args.input.resolve()}")
        fm, md_text, warnings = docx_to_csm_markdown(
            args.input, assets_root=args.output_dir,
            title=args.title or None, standard_number=args.standard_number or None,
        )
        for warning in warnings:
            _log(f"docx import warning: {warning}")
        paths["raw"].write_text(md_text, encoding="utf-8")
        _write_json(paths["provenance"], {
            "sourceFile": str(args.input.resolve()), "sourceSha256": source_sha256,
            "backend": "docx-import", "sourceFormat": args.input.suffix.lower().lstrip("."),
            "mode": "docx-import", "warnings": warnings,
        })
        title = str(fm.get("title") or title or "")
        number = str(fm.get("standard-number") or number or "")
        state["title"] = title
        state["number"] = number
        state["backend"] = "docx-import"
        state["pageCount"] = None
        state["parts"] = []
        _write_json(args.state_file, state)
        _log(f"Imported CSM written: {paths['raw']}")
        _write_manifest(args, state, title=title, number=number)
        if args.stage == "extract":
            _log("Extraction (docx import) stage complete. Run with --stage all to normalize/parse and render.")
            return 0
    merged = paths["raw"]
    ssir = finalize(args, merged)
    paths = _stage_paths(args.output_dir, stem, source_ext="docx")
    _post_parse_verify_render(args, state, paths, ssir)
    return 0


def _post_parse_verify_render(args: argparse.Namespace, state: dict[str, Any],
                              paths: dict[str, Path], ssir: Path | None) -> None:
    """parse 之后公共尾部：roundtrip → render（PDF + doc_1 docx）→ manifest。"""
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
            # doc_1：同一 SSIR 渲染的 Word 孪生（与 PDF 技术内容等价）。
            "--docx-output", str(paths["render_docx"]),
        ]
        _log("Rendering SSIR JSON as a traditional standard-style PDF (+ content-equivalent docx)")
        if subprocess.run(render, cwd=ROOT).returncode:
            raise RuntimeError("SSIR PDF renderer failed")
        if args.input_kind == "pdf":
            compare(args.input, paths["render_pdf"], paths["render_comparison"])
            _log(f"Generated PDF comparison: {paths['render_comparison']}")
        if paths["render_docx"].is_file():
            _log(f"Generated docx twin (doc_1): {paths['render_docx']}")
    _write_manifest(args, state, status="completed")


# 表注锚点上标字母回收（CSM-OCR-015，2026-09-06，GB_T_20001.10-2014 表1）：
# 表注（如“a 黑体表示…”，GBT-X04/GBT-C18）的单元格锚点是小写拉丁上标字母。
# MinerU OCR 常在表格组装时把表头/单元格里跟上标字母整段丢弃，只剩表注定义行
# （表内末行“a说明…”）——GB_T_20001.5-2017 同模板表保留了（“表述形式a”），
# 20001.10 的源 PDF 文本层两版都有（“表述形式”+上标 a，4.66pt vs 正文 8.25pt）。
# mineru_html._restore_table_footnote_markers（GBT-C18）只能按“注文包含单元格
# 文本”恢复（GB/T 1.1 匝间绝缘型），注文不含锚点文本（字体样式说明型）时无从
# 匹配——此处从源 PDF 文本层几何补盲。
_TABLE_NOTE_DEF_CELL_RE = re.compile(r"^([a-zA-Z])(?:[ \u3000]+)?(?=[\u4e00-\u9fff])")
# 表注定义行的“注文拆条”：注文标记（小写字母）出现在句末标点之后或单元格行首，
# 且后随汉字/引号——用于把“a注文…b注文…”连排单元格拆成逐条注（GB_T_5171.1-2014
# 表19 a/b、表20 a~h 型，MinerU 把整段连排进一格且丢字）。
_TABLE_NOTE_ITEM_SPLIT_RE = re.compile(r"(?:(?<=^)|(?<=[。；;，,、:：])|\s(?=[a-z]))\s*([a-z])(?=[\u4e00-\u9fff“”『「\"'])")


def _plain_note_cell_text(cell: str) -> str:
    """表注单元格去角标标记后的纯注文文本（开标记 → 其角标字符、闭标记删除）。

    供表注行判型与“连排注文拆条”使用——对已 token 化的单元格（新通用形式
    ``[:sup:a]注文[:/sup]`` 或迁移前的旧形式 ``[^a]注文[^a/]``）同样可还原出注文
    本体，保证恢复流程幂等（结果只取决于注文文本本身）。
    """
    from leleby_ssir.parser import INLINE_SCRIPT_CLOSE_RE, INLINE_SCRIPT_OPEN_RE

    text = INLINE_SCRIPT_CLOSE_RE.sub("", str(cell))
    text = INLINE_SCRIPT_OPEN_RE.sub(lambda m: m.group(2), text)
    text = re.sub(r"\[\^([a-z])/\]", "", text)  # 旧形式（迁移期兼容）
    return re.sub(r"\[\^([a-z])\]", r"\1", text)


def _cell_note_letters(plain: str) -> set[str]:
    """整格纯注文里出现的注文标记字母集合（含 <br> 分隔的段首字母）。

    跨段取并集：拆条按 `<br>` 分段进行，但“该条字母是否已在文本里”必须按**整格**
    判断——否则同一格里已带标记的条（如 f）在其后续段的补位检索中会被另一条的
    头文本截短匹配误配（表20 f/g 两条都以“只有在产品标准中规定了”起头）。
    """
    pattern = re.compile(
        r"(?:(?<=^)|(?<=[。；;，,、:：])|(?<=<br>)|(?<=\s))\s*([a-z])(?=[\u4e00-\u9fff“”『「\"])"
    )
    return {match.group(1) for match in pattern.finditer(plain)}


def _note_item_boundaries(
    plain: str, note_defs: list[tuple[str, str]], known_letters: set[str] | None = None
) -> list[tuple[str, int, int]]:
    """连排注文 → 逐条注的 (字母, 标记位, 注文本体起点) 列表。

    两类证据（任一命中即定界，都不命中则不拆）：
    - md 文本自身的注文标记：句末标点/行首之后的“小写字母 + 汉字/引号”——标记
      字母就在正文里（标记位 = 字母位置，正文起点 = 其后一位）；
    - 源 PDF 表注定义行的 (字母, 注文头)：md 把注文标记字母读丢时（GB_T_5171.1-2014
      表20 的 d/e/f 即如此，MinerU 只留下注文文字），用注文头文本在**上一条之后**
      定位该条起点（标记位 = 正文起点）；头文本按 12→10→8→6 字逐级缩短匹配，仍
      找不到就不拆（不猜）。游标按注文顺序推进（md 标记与 PDF 补位共用同一游标），
      避免“上一条之后”被排在后文的 md 标记带偏（否则 d/e 会被后面的 g 挡住）。
      已由 ``known_letters``（整格已出现的字母）覆盖的条不补位：该条在别处已有
      标记，在本段里检索只会撞上相邻条的头文本。
    """
    ordered = sorted((match.start(1), match.group(1)) for match in _TABLE_NOTE_ITEM_SPLIT_RE.finditer(plain))
    positions = {letter: offset for offset, letter in ordered}
    marks: list[tuple[int, int, str]] = [(offset, offset + 1, letter) for offset, letter in ordered]
    claimed = {start for _mark, start, _letter in marks}
    cursor = 0
    for letter, head in note_defs:
        if letter in positions or (known_letters and letter in known_letters):
            cursor = max(cursor, positions.get(letter, 0))
            continue
        probe = re.sub(r"\s+", "", head)
        for length in (12, 10, 8, 6):
            candidate = probe[:length]
            if len(candidate) < 6:
                continue
            # 从游标处（含）开始找：注文头可能正好落在本段起点（<br> 分段后
            # 每条注文自成一段时即如此），cursor+1 会漏掉起点命中。
            found = plain.find(candidate, cursor)
            if found >= 0 and found not in claimed:
                marks.append((found, found, letter))
                claimed.add(found)
                cursor = found
                break
    marks.sort()
    return [(letter, mark, start) for mark, start, letter in marks]


def _wrap_note_items(plain: str, marks: list[tuple[str, int, int]]) -> str:
    """逐条注包装为通用角标标记 ``[:sup:x]注文[:/sup]``（连排，不写 ``<br>``）。

    ``marks`` 的元组是 (字母, 标记位, 注文本体起点)：注文区间取到**下一条标记位**
    为止，md 里残存的字面标记字母因此不会混进上一条注文（PDF 补位条的标记位与正文
    起点相同，无字面字母可留）。多条注在同一单元格内**连排**——标记成对自定界，
    渲染端在相邻两对之间自动换行（2026-09-11 用户裁定，docs/07 §6.7）。
    规则对应: GBT-X04 / GBT-C18 执行侧。
    """
    if not marks:
        return plain
    parts: list[str] = []
    residue = plain[: marks[0][1]].strip()
    if residue:
        parts.append(residue)  # 首条标记之前的残留文本（罕见）原样保留
    for index, (letter, _mark, start) in enumerate(marks):
        end = marks[index + 1][1] if index + 1 < len(marks) else len(plain)
        text = plain[start:end].strip()
        parts.append(f"[:sup:{letter}]{text}[:/sup]" if text else f"[:sup:{letter}/]")
    return "".join(parts)


def _cluster_visual_lines(spans: list[dict], tolerance: float = 5.0) -> list[list[dict]]:
    """按**基线**（origin[1]）聚类视觉行，容差 5pt。

    不能按 bbox 顶（bbox[1]）聚类：同一表格行里中文字体（CJK ascender ≈0.89）与
    西文字体（≈1.33）的字框顶差可达 size×0.45 ≈ 4pt，按 bbox 顶聚类会把锚文本与
    紧随它的上标角标拆成两行——GB_T_5171.1-2014 表20 第 7/10 行的 d/e 即因此漏检。
    表格行间距 ≈15pt，5pt 容差不会把相邻行并成一行。
    （回归测试: tests/test_mineru_table_note_markers.py::VisualLineClusteringTests）
    """
    ordered = sorted(spans, key=lambda s: (s["origin"][1], s["origin"][0]))
    lines: list[list[dict]] = []
    for span in ordered:
        if lines and abs(span["origin"][1] - lines[-1][0]["origin"][1]) <= tolerance:
            lines[-1].append(span)
        else:
            lines.append([span])
    return lines


def _recover_table_note_markers(markdown: str, pdf: Path) -> tuple[str, int]:
    """Recover trailing table-note superscript letters lost by OCR (CSM-OCR-015).

    现象（GB_T_20001.10-2014 表1）：源 PDF 表头第 3 列“要素所允许的表述形式”末尾
    带 4.66pt 上标 a（正文 8.25pt），MinerU OCR 表组装时把它整段丢弃，只留下表内
    末行的表注定义行“a黑体表示…”。渲染后表注解释在、锚点标记丢，不成对。

    恢复规则（保守、通用、幂等）：
    - 源 PDF 文本层找“正文行内、字号 ≤0.72×正文中位（≤7.8pt）、单小写拉丁字母”
      的上标 span，其 x0 与同一视觉行上紧邻的前一正文 span 的 x1 相邻（±2~6pt），
      该正文 span 文本即锚文本（锚文本必须汉字收尾——渲染端只上标汉字后字母）；
    - 该上标字母必须是当前 md 表格分组的“表注定义行”（唯一非空单元格以
      “字母+汉字”开头，如“a黑体…”）所声明的字母——无定义行的字母不猜；
    - 锚文本命中分两形态：尾部（单元格以其结尾，字母补到末尾）与词中（锚文本
      后紧接汉字——“要素a的编排”型，字母补到锚文本之后）；每形态都在表格分组
      内**恰好一个**单元格命中才补字母，词中归属不唯一（多个单元格含同一锚文本
      + 汉字，如表头两列同以“要素”开头）不猜——几何-列边界对齐留待后续；
    - 找不到唯一匹配/定义行缺失/字母已存在 → 不改。幂等：已恢复的单元格以
      字母结尾（尾部）或锚文本后已跟该字母（词中），再次运行不重复补。
    2026-09-07（语法定案）输出改为**显式标记**；2026-09-11 起标记通用化为
    “行内角标标记”（docs/07 §6.7）：锚点补回写自闭合引用点 ``[:sup:x/]``，
    表注定义行逐条改写为 ``[:sup:x]注文[:/sup]``（多条以 <br> 分隔同格排布；
    段首字母可后随引号/汉字）。已 token 化的内容幂等（先还原纯注文再重新拆条，
    结果只取决于注文文本；锚点命中检查对已带标记的单元格天然不再匹配）。
    规则对应: GBT-X04（表注由标记与解释成对组成）/ GBT-C18（表脚注上标）；
    执行侧工程规则，与 GFM 脚注回收 CSM-OCR-014 同族；渲染端按显式标记还原
    上角标（pdf_renderer._table_cell_superscripts）。
    """
    try:
        import pymupdf
    except ImportError:
        return markdown, 0
    if not pdf.is_file():
        return markdown, 0

    # —— 1) md 表格行分组（连续管道行），并取各组的表注定义行字母 ——
    lines = markdown.split("\n")
    groups: list[list[int]] = []
    current: list[int] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            current.append(i)
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    if not groups:
        return markdown, 0

    def row_cells(line: str) -> list[str]:
        """md 管道行的单元格文本（剥外管、去首尾空白）。"""
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            return []
        return [part.strip() for part in stripped[1:-1].split("|")]

    def note_cell_slots(row_indexes: list[int]) -> list[tuple[int, int]]:
        """表注定义行：分组内**单个非空单元格**且以“注文标记 + 汉字/引号”开头的行。

        返回 (行号, 单元格序号)。判型在去显式标记后的纯注文上进行（已 token 化的
        注文行同样识别，保证幂等）。
        """
        slots: list[tuple[int, int]] = []
        for i in row_indexes:
            raw_cells = row_cells(lines[i])
            filled = [k for k, cell in enumerate(raw_cells) if cell]
            if len(filled) != 1:
                continue
            if _TABLE_NOTE_DEF_CELL_RE.match(_plain_note_cell_text(raw_cells[filled[0]])):
                slots.append((i, filled[0]))
        return slots

    # —— 2) 源 PDF 文本层：正文行内的上标小写字母 span → (锚文本, 字母)；
    #         行首（其前无紧邻正文 span）的上标小写字母 → 表注定义行的 (字母, 注文头) ——
    candidates: list[tuple[str, str]] = []
    note_defs: list[tuple[str, str]] = []
    with pymupdf.open(pdf) as document:
        for page in document:
            spans: list[dict] = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        if span["text"].strip():
                            spans.append(span)
            if not spans:
                continue
            sizes = sorted(s["size"] for s in spans)
            body_median = sizes[len(sizes) // 2]
            sup_threshold = min(body_median * 0.72, 7.8)
            for vline in _cluster_visual_lines(spans):
                vline.sort(key=lambda s: s["origin"][0])
                for idx, sup in enumerate(vline):
                    letter = sup["text"].strip()
                    if sup["size"] > sup_threshold or not re.fullmatch(r"[a-z]", letter):
                        continue
                    anchor: dict | None = None
                    for j in range(idx - 1, -1, -1):
                        prev = vline[j]
                        if prev["size"] <= sup_threshold:
                            continue
                        dx = sup["bbox"][0] - prev["bbox"][2]
                        if -2 <= dx <= 6:
                            anchor = prev
                        break  # 只看紧邻（可含中间上标）的最近正文 span
                    if anchor is not None:
                        anchor_text = anchor["text"].strip()
                        if not anchor_text or not re.search(r"[\u4e00-\u9fff]$", anchor_text):
                            continue  # 渲染端只上标汉字后的字母，非汉字收尾锚不补
                        pair = (anchor_text, letter)
                        if pair not in candidates:
                            candidates.append(pair)
                        continue
                    # 其上没有紧邻正文 span → 这是**表注定义行**的行首注文标记
                    # （“a 注文…”）；同视觉行紧随其后的正文 span 文本即该条注文头，
                    # 供 md 丢掉注文标记字母时定位该条注文的起点。
                    following = next((s for s in vline[idx + 1:] if s["size"] > sup_threshold), None)
                    if following is None:
                        continue
                    head = re.sub(r"\s+", "", following["text"].strip())
                    if len(head) >= 6 and sup["bbox"][2] <= following["bbox"][0] + 8:
                        item = (letter, head)
                        if item not in note_defs:
                            note_defs.append(item)
    if not candidates and not note_defs:
        return markdown, 0

    # —— 3) 锚文本在含对应字母定义行的分组里命中单元格 → 补字母 ——
    # 两形态（2026-09-06 补词中）：
    #   a) 尾部锚点：单元格以锚文本结尾 → 字母补到单元格文本末尾（原逻辑）；
    #   b) 词中锚点：单元格内锚文本后紧接汉字（“要素a的编排”型，上标夹在
    #      两个汉字之间）→ 字母补到锚文本之后。两种均要求全组唯一命中；
    #      词中归属不唯一（多个单元格含同一锚文本+汉字，如表1 表头两列都从
    #      “要素”开头）时不猜——需单元格几何对齐列边界，留待后续。
    recovered = 0
    for group in groups:
        note_slots = note_cell_slots(group)
        if not note_slots:
            continue
        # 表注定义行 token 化：把“a注文…b注文…”连排注文逐条改写为通用角标标记
        # “[:sup:x]注文[:/sup]”（多条以 <br> 分隔同格排布）；md 丢掉的注文
        # 标记字母用源 PDF 的注文头文本定位后补回。幂等：先去掉既有标记还原纯注文
        # 再重新拆条，结果只取决于注文文本本身。
        group_letters: set[str] = set()
        for line_index, cell_index in note_slots:
            pipes = [k for k, ch in enumerate(lines[line_index]) if ch == "|"]
            if len(pipes) < cell_index + 2:
                continue
            start, end = pipes[cell_index] + 1, pipes[cell_index + 1]
            raw_cell = lines[line_index][start:end]
            plain = _plain_note_cell_text(raw_cell)
            cell_letters = _cell_note_letters(plain)
            tagged: list[str] = []
            # 兼容既有 canonical 的 <br> 分格写法（新格式连排，无需 <br>）。
            for segment in re.split(r"<br>", plain):
                boundaries = _note_item_boundaries(segment, note_defs, cell_letters)
                group_letters.update(letter for letter, _mark, _start in boundaries)
                tagged.append(_wrap_note_items(segment, boundaries))
            wrapped = "".join(tagged)
            if wrapped.strip() != raw_cell.strip():
                lead = raw_cell[: len(raw_cell) - len(raw_cell.lstrip())]
                trail = raw_cell[len(raw_cell.rstrip()):]
                lines[line_index] = lines[line_index][:start] + lead + wrapped + trail + lines[line_index][end:]
                recovered += 1
        if not group_letters:
            continue
        for anchor_text, letter in candidates:
            if letter not in group_letters:
                continue
            # 形态 a：尾部。目标行以锚文本结尾 → 补 [:x]；已带字面字母时仅在
            # “锚文本+该字母”同尾（几何确认为上标）时把字面字母改写为 [:x]；
            # 末位是单个数字（OCR 把上标标记读成数字，'g'→'8' 型）时同样改写。
            tail_targets: list[tuple[int, int]] = []
            literal_tail_targets: list[tuple[int, int]] = []
            mangled_tail_targets: list[tuple[int, int]] = []
            for i in group:
                for cell_index, cell in enumerate(row_cells(lines[i])):
                    latin_tail = re.search(r"[A-Za-z]$", cell)
                    if latin_tail:
                        if cell[-1] == letter and cell[:-1].rstrip().endswith(anchor_text):
                            literal_tail_targets.append((i, cell_index))
                        continue
                    if cell.endswith(anchor_text):
                        tail_targets.append((i, cell_index))
                        continue
                    # 锚文本 + 单个数字收尾且数字前不是数字（排除多位数值尾部），
                    # 几何上该数字正是源 PDF 里锚文本之后的上标标记位（CSM-OCR-015）。
                    if re.search(r"(?<![0-9])[0-9]$", cell) and cell[:-1].rstrip().endswith(anchor_text):
                        mangled_tail_targets.append((i, cell_index))
            if len(tail_targets) == 1:
                line_index, cell_index = tail_targets[0]
                patched = _insert_table_cell_marker(lines[line_index], cell_index, letter)
                if patched != lines[line_index]:
                    lines[line_index] = patched
                    recovered += 1
                continue
            if len(tail_targets) == 0 and len(literal_tail_targets) + len(mangled_tail_targets) == 1:
                # OCR 保留了字面锚点字母（如 20001.5 表1 “表述形式a”）：渲染端
                # 不再做字形猜测，此处把字面字母改写为显式 [:x] 引用点。
                line_index, cell_index = (literal_tail_targets or mangled_tail_targets)[0]
                line = lines[line_index]
                pipes = [k for k, ch in enumerate(line) if ch == "|"]
                if len(pipes) > cell_index + 1:
                    start, end = pipes[cell_index] + 1, pipes[cell_index + 1]
                    raw = line[start:end]
                    replace_at = start + len(raw.rstrip()) - 1  # 末尾字母（去行尾空白定位）
                    lines[line_index] = line[:replace_at] + f"[:sup:{letter}/]" + line[replace_at + 1:]
                    recovered += 1
                continue
            # 形态 b：词中。锚文本在单元格中部出现、后随汉字、该处尚未有该字母。
            mid_targets: list[tuple[int, int, int]] = []  # (line_index, cell_index, offset_after_anchor)
            for i in group:
                for cell_index, cell in enumerate(row_cells(lines[i])):
                    position = cell.find(anchor_text)
                    if position < 0:
                        continue
                    after = position + len(anchor_text)
                    if after >= len(cell):
                        continue  # 锚文本在词尾 → 形态 a 已覆盖
                    if not ("\u4e00" <= cell[after] <= "\u9fff"):
                        continue  # 后随非汉字 → 不是词中上标位
                    if cell[after] == letter:
                        continue  # 幂等：该字母已在
                    mid_targets.append((i, cell_index, after))
            if len(mid_targets) != 1:
                continue
            line_index, cell_index, offset = mid_targets[0]
            patched = _insert_table_cell_marker_at(lines[line_index], cell_index, letter, offset)
            if patched != lines[line_index]:
                lines[line_index] = patched
                recovered += 1
    if not recovered:
        return markdown, 0
    return "\n".join(lines), recovered


def _insert_table_cell_marker(line: str, cell_index: int, letter: str) -> str:
    """把表注引用点 token [:x] 插到管道行第 cell_index 个单元格文本末尾。

    2026-09-07 语法定案（docs/07 §6.7）：锚点以显式 [:x] 标记写回，渲染端按
    标记还原上角标，不再做字形猜测。
    """
    pipes = [i for i, ch in enumerate(line) if ch == "|"]
    if len(pipes) < 2 or cell_index < 0 or cell_index >= len(pipes) - 1:
        return line
    start, end = pipes[cell_index] + 1, pipes[cell_index + 1]
    text = line[start:end]
    insert_at = start + len(text.rstrip())
    return line[:insert_at] + f"[:sup:{letter}/]" + line[insert_at:]


def _insert_table_cell_marker_at(line: str, cell_index: int, letter: str, offset_in_cell: int) -> str:
    """把表注引用点 token [:x] 插到管道行第 cell_index 个单元格文本内 offset 处。

    offset_in_cell 以单元格**首个非空白字符**为 0 计数（md 单元格可能带首部空格，
    行内偏移与 row_cells 的去空白视图对齐）。词中锚点（“要素a的编排”型）写回
    [:x] 标记；渲染端按标记还原上角标。
    """
    pipes = [i for i, ch in enumerate(line) if ch == "|"]
    if len(pipes) < 2 or cell_index < 0 or cell_index >= len(pipes) - 1:
        return line
    start = pipes[cell_index] + 1
    raw = line[start:pipes[cell_index + 1]]
    lead = len(raw) - len(raw.lstrip(" \u3000"))
    insert_at = start + lead + offset_in_cell
    if insert_at < start or insert_at > pipes[cell_index + 1]:
        return line
    return line[:insert_at] + f"[:sup:{letter}/]" + line[insert_at:]


def _recover_pdf_footnotes(md_path: Path, pdf: Path) -> int:
    """从源 PDF 文本层回收上标脚注并写入 markdown 基线（GFM 语法，CSM-OCR-014）。

    MinerU 文本抽取把上标标记与正文粘连（“—2003”+1)→“—20031”；“单独的标准”+2)→
    “标准2。”），页底 8pt 解释行被当普通正文。用 pymupdf 读源 PDF：
    - 上标 span（字号显著小于正文）识别条文脚注标记“N)”，按 页→位置 全文连续编号；
    - md 尚无 “[^N]” 时，把粘连进正文的数字还原为 “[^N]”（锚定=标记左侧整段正文
      文本窗口，窗口+数字唯一且后随汉字/句末标点才替换，否则不猜）；
    - 页底小字解释行（y≥0.70×页高、字号≤8.5、以 数字) 开头，续行带合并）转
      “[^N]: 文本”；md 已有 “N） 文本” 残留正文段就地改前缀，否则插到锚点段后。
    幂等/自愈：已有 “[^N]: ” 定义的条目跳过；已有 “[^N]” 标记而缺定义（半途产物）
    时只补定义不改正文。只处理阿拉伯数字上标（条文脚注 GBT-X04）。返回处理条数。
    """
    try:
        import fitz  # type: ignore
    except ImportError:
        return 0
    import re as _re
    text = md_path.read_text(encoding="utf-8")
    markers: list[tuple[int, str, int, float]] = []  # (页, 原标记, y, x0)
    notes: list[tuple[int, str, str]] = []  # (页, 原标记, 定义文本)
    with fitz.open(pdf) as document:
        for page_index in range(len(document)):
            page = document[page_index]
            height = page.rect.height
            spans: list[dict] = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        if span["text"].strip():
                            spans.append(span)
            sizes = sorted(s["size"] for s in spans)
            body_median = sizes[len(sizes) // 2] if sizes else 10.0
            sup_threshold = min(body_median * 0.72, 7.8)
            sup = sorted(
                (s for s in spans if s["size"] <= sup_threshold),
                key=lambda s: (s["bbox"][1], s["bbox"][0]),
            )
            i = 0
            while i < len(sup):
                band = [sup[i]]
                j = i + 1
                while j < len(sup) and abs(sup[j]["bbox"][1] - band[0]["bbox"][1]) <= 3.5 and sup[j]["bbox"][0] <= band[-1]["bbox"][2] + 6:
                    band.append(sup[j])
                    j += 1
                token = "".join(s["text"] for s in sorted(band, key=lambda s: s["bbox"][0])).strip()
                if token and token[0].isdigit() and token.endswith((")", "）")):
                    markers.append((page_index, token, band[0]["bbox"][1], band[0]["bbox"][0]))
                i = j
            bottom = sorted(
                (s for s in spans if s["size"] <= 8.5 and s["bbox"][1] >= height * 0.68),
                key=lambda s: (s["bbox"][1], s["bbox"][0]),
            )
            band_lines: list[tuple[float, str]] = []
            cur: list[tuple[float, float, str]] = []
            band_y: float | None = None
            for s in bottom:
                y0 = s["bbox"][1]
                if band_y is None or abs(y0 - band_y) <= 4:
                    cur.append((s["bbox"][0], y0, s["text"]))
                    band_y = cur[0][1]
                else:
                    band_lines.append((band_y, "".join(it for _, _, it in sorted(cur)).strip()))
                    cur = [(s["bbox"][0], y0, s["text"])]
                    band_y = y0
            if cur:
                band_lines.append((band_y, "".join(it for _, _, it in sorted(cur)).strip()))
            idx = 0
            while idx < len(band_lines):
                y, line = band_lines[idx]
                m = _re.match(r"^(\d+)[)）](.*)$", line, _re.S)
                if not m:
                    idx += 1
                    continue
                text_def = m.group(2).strip()
                next_y = y
                while idx + 1 < len(band_lines):
                    ny, nline = band_lines[idx + 1]
                    if _re.match(r"^\d+[)）]", nline) or nline.startswith("注") or _re.fullmatch(r"\d{1,3}", nline) or ny - next_y > 30:
                        break
                    text_def += nline
                    next_y = ny
                    idx += 1
                notes.append((page_index, f"{m.group(1)})", text_def))
                idx += 1
    if not markers:
        return 0
    markers.sort(key=lambda m: (m[0], m[2], m[3]))
    note_by = {(pg, lbl): txt for pg, lbl, txt in notes}
    any_marker = "[^" in text
    new_text = text
    defs: list[tuple[str, str, str]] = []  # (原标记, label, 定义)
    replaced = 0
    with fitz.open(pdf) as document:
        for order, (page_index, token, my, mx) in enumerate(markers, start=1):
            label = str(order)
            digits = token[:-1]
            def_text = note_by.get((page_index, token), "")
            if _re.search(rf"\[\^{re.escape(label)}\]:", new_text):
                continue
            if def_text:
                defs.append((token, label, def_text))
                replaced += 1
            if any_marker or f"[^{label}]" in new_text:
                continue
            page_obj = document[page_index]
            norm = []
            for block in page_obj.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        if span["text"].strip() and span["size"] > 7.8:
                            norm.append(span)
            left = [s for s in norm if abs(s["bbox"][1] - my) <= 6 and s["bbox"][2] <= mx + 1]
            if not left:
                continue
            run_text = "".join(s["text"] for s in sorted(left, key=lambda s: s["bbox"][0])).strip()
            hit = -1
            tail_used = ""
            for tail in (run_text[-24:], run_text[-12:], run_text[-6:]):
                if not tail:
                    continue
                fused = tail + digits
                pos = 0
                while True:
                    h = new_text.find(fused, pos)
                    if h < 0:
                        break
                    before_ok = h == 0 or not new_text[h - 1].isdigit()
                    after = new_text[h + len(fused)] if h + len(fused) < len(new_text) else ""
                    if before_ok and after and (after in "。；，、：）】" or "\u4e00" <= after <= "\u9fff"):
                        hit = h
                        tail_used = tail
                        break
                    pos = h + 1
                if hit >= 0:
                    break
            if hit < 0 or not tail_used:
                continue
            new_text = new_text[: hit + len(tail_used)] + f"[^{label}]" + new_text[hit + len(tail_used) + len(digits):]
    if not defs:
        return 0
    final_text = _place_footnote_definitions(new_text, defs)
    md_path.write_text(final_text, encoding="utf-8")
    return replaced


def _place_footnote_definitions(markdown_text: str, defs: list[tuple[str, str, str]]) -> str:
    """把回收的脚注定义写进 markdown：GFM “[^N]: 文本” 独立段（幂等）。

    ``defs`` = [(原页底标记如 "1)", 标签如 "1", 定义文本), …]，只含当前缺定义的标签。
    - 正文残留的 “N） 文本”/“N) 文本” 段就地改前缀为 “[^N]: 文本”（自愈）；
    - 否则在含 “[^N]” 标记的段块之后插入定义行，**前后均以空行隔离**：
      定义行绝不离散粘贴到下一内容行（否则与下一条目并成一个多行段落块，parser
      的“整行定义”形态无法归类——GB_T_20001.10-2014 脚注 1 曾因此以正文段落身份
      渲染）；插入点越过锚点段与段后空行带、落在其后首个非空内容行之前，定义
      不会被插进列表条目序列中间。返回新文本（无插入/转换时逐字节不变）。
    """
    lines = markdown_text.split("\n")
    insert_before: dict[int, list[str]] = {}
    for token, label, def_text in defs:
        if f"[^{label}]:" in markdown_text:
            continue  # 幂等：定义已存在
        num = token[:-1]
        converted = False
        for i, ln in enumerate(lines):
            stripped = ln.lstrip()
            indent = ln[: len(ln) - len(stripped)]
            if stripped.startswith(f"{num}) ") or stripped.startswith(f"{num}） "):
                rest = stripped.split(" ", 1)[1]
                lines[i] = f"{indent}[^{label}]: {rest}"
                converted = True
                break
            if stripped.startswith(f"{num}）") or stripped.startswith(f"{num})"):
                rest = stripped[len(num) + 1:].lstrip()
                lines[i] = f"{indent}[^{label}]: {rest}"
                converted = True
                break
        if converted:
            continue
        anchor_line = next((i for i, ln in enumerate(lines) if f"[^{label}]" in ln), None)
        if anchor_line is None:
            continue  # 锚点标记不在（半途产物）→ 不猜
        # 越过锚点段连续非空行（同段多行）与段后空行带 → 插入点 = 段后首个内容行
        j = anchor_line + 1
        while j < len(lines) and lines[j].strip():
            j += 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        insert_before.setdefault(j, []).append(["", f"[^{label}]: {def_text}", ""])
    if not insert_before:
        return "\n".join(lines)
    final: list[str] = []
    for i, ln in enumerate(lines):
        for extra in insert_before.get(i, ()):
            final.extend(extra)
        final.append(ln)
    for extra in insert_before.get(len(lines), ()):
        final.extend(extra)
    return "\n".join(final)



def _run_from_existing_canonical(args: argparse.Namespace, state: dict[str, Any], canonical: Path) -> int:
    """已有 curated canonical（02_canonical/<stem>.canonical.md）时的续跑入口。

    跳过 MinerU OCR/PDF 抽取、合并与 normalize——绝不覆盖人工编辑的 canonical
    （AGENTS.md §0.1/§2），从 parse 开始执行与 tools/reprocess_canonical.py
    完全等同的后续阶段：parse -> SSIR →（PDF 源）版面印记恢复 → roundtrip →
    render（PDF + docx）→ compare → manifest。
    规则对应：build=GEN-050/052；verify=GEN-051/090/091 + 三层合规；
    render=GEN-070—076；版面印记恢复沿用 finalize 的 stamp 逻辑。
    """
    stem = args.output_stem or args.input.stem
    paths = _stage_paths(args.output_dir, stem)
    for stage_path in (paths["ssir"], paths["render_pdf"], paths["render_md"], paths["render_docx"], paths["verify"]):
        stage_path.parent.mkdir(parents=True, exist_ok=True)
    # provenance 保留：pipeline-state 可能缺 title/number/sha，回退旧 manifest
    old_manifest = _load_json(args.output_dir / "manifest.json", {})
    state.setdefault("title", old_manifest.get("title", ""))
    state.setdefault("number", old_manifest.get("standardNumber", ""))
    state.setdefault("createdAt", old_manifest.get("created"))
    if not state.get("sourceSha256") and old_manifest.get("source", {}).get("checksum", "").startswith("sha256:"):
        state["sourceSha256"] = old_manifest["source"]["checksum"][len("sha256:"):]

    # canonical 只读：此路径绝不写回 canonical——CSM-OCR-014（条文脚注）与
    # CSM-OCR-015（表注锚点上标字母）的回收此前在这里把结果直接写进 curated
    # canonical，违反「半程续跑仅刷新下游产物、canonical 不被覆盖」（AGENTS.md
    # §2 / README）。两类回收都已改到 canonical 的生成时刻执行：脚注回收在
    # finalize 的 normalize 之后（全流程/显式 --stage finalize），表注回收在
    # merge 全流程（随 raw 进 normalize）；此处 parse 直接读 canonical 原样。

    parsed = [
        str(Path(sys.prefix) / "bin" / "ssir"), "csm", "parse",
        "--input", str(canonical), "--output", str(paths["ssir"]),
        "--report", str(paths["parse_report"]),
    ]
    _log("Parsing canonical CSM into SSIR JSON")
    if subprocess.run(parsed, cwd=ROOT).returncode:
        raise RuntimeError("SSIR parsing needs review; check the canonical CSM and the parse report.")
    _log(f"SSIR JSON written: {paths['ssir']}")

    # PDF 源才有的版面印记恢复（示例框样式/图源尺寸/并列版面，读源 PDF 与 parts 几何）
    if args.input_kind == "pdf" and args.input.is_file():
        _stamp_example_styles(paths["ssir"], args.input)
        _stamp_figure_source_sizes(paths["ssir"], args.input)
        parts_dir = args.output_dir / "parts"
        if parts_dir.is_dir():
            _stamp_side_by_side_layout(paths["ssir"], parts_dir)
    else:
        _log("No source PDF present; skipping PDF-geometry stamps (example style / figure sizes / side-by-side)")

    # 公共尾部：roundtrip -> render（PDF+docx）-> compare -> manifest
    _post_parse_verify_render(args, state, paths, paths["ssir"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
