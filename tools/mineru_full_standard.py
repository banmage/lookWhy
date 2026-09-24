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
from leleby_ssir.process_env import normalize_proxy_environment


ROOT = Path(__file__).resolve().parents[1]

# 下游构建/验证阶段已搬到 src/leleby_ssir/pipeline.py 与 pdf_compare.py——
# 抽取工具只保留 扫描/合并 职责；这里 re-export 保持既有 import（测试、其它工具）不变。
from leleby_ssir.pdf_compare import compare  # noqa: E402,F401
from leleby_ssir.pipeline import (  # noqa: E402,F401
    _ANCHOR_COLUMN_GAP_RATIO,
    _BANNER_FRAGMENTS,
    _COVER_BANNER_RE,
    _ELLIPSIS_CHARS,
    _EXAMPLE_CAPTION_RE,
    _FULLWIDTH_DIGITS,
    _FULL_WIDTH_RATIO,
    _MAX_SIDE_COLUMNS,
    _PART_PAGE_RANGE_RE,
    _REGION_GAP_LINES,
    _TABLE_NOTE_DEF_CELL_RE,
    _TABLE_NOTE_ITEM_SPLIT_RE,
    _asset_basename,
    _canonical_issuer,
    _canonical_issuer_known,
    _cell_note_letters,
    _clause_skeleton,
    _cluster_visual_lines,
    _cover_english_from_pdf,
    _cover_issuer_from_pdf,
    _cover_metadata,
    _cover_title,
    _demote_banner_fragments,
    _demote_cover_headings,
    _insert_table_cell_marker,
    _insert_table_cell_marker_at,
    _is_cover_banner,
    _is_cover_banner_fragment,
    _is_gbt_1_1_2020,
    _is_short_ellipsis,
    _load_json,
    _log,
    _looks_like_document_number,
    _normalize_part_title,
    _note_item_boundaries,
    _page_count,
    _place_footnote_definitions,
    _plain_note_cell_text,
    _post_parse_verify_render,
    _raw_line_starts_with_number,
    _recover_annex_headings,
    _recover_pdf_footnotes,
    _recover_table_note_markers,
    _restore_ellipsis_lines,
    _run_from_existing_canonical,
    _segment_word,
    _stage_paths,
    _stamp_example_styles,
    _stamp_figure_source_sizes,
    _stamp_figure_source_sizes_from_map,
    _stamp_side_by_side_layout,
    _system_word_list,
    _text_layer_content_lines,
    _tidy_english_title,
    _usable_title,
    _wrap_note_items,
    _write_json,
    _write_manifest,
    finalize,
    load_stage_layout,
    resolve_stage_layout_path,
    write_stage_layout,
)


def _mineru_command() -> str:
    local = Path(sys.prefix) / "bin" / "mineru"
    if local.is_file() and local.stat().st_mode & 0o111:
        return str(local)
    found = shutil.which("mineru")
    if found:
        return found
    raise RuntimeError("MinerU is not installed in the active environment. Install mineru first.")


def _mineru_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """交给 MinerU 子进程的环境：os.environ 副本 + 代理规整（GEN-132）。

    MinerU 3.x 的 CLI 先起本地 mineru-api 再用 httpx 访问它，httpx 只认
    http/https/socks5/socks5h 四种代理方案——调用方 shell 里一个 `socks://`
    （代理工具设「系统代理（SOCKS）」时的写法）会让整次抽取在启动阶段抛
    ValueError。这里统一规整，并把回环地址写进 NO_PROXY（本地 API 不该走代理）。
    os.environ 本身不改。
    """
    env = dict(os.environ)
    if extra:
        env.update(extra)
    for note in normalize_proxy_environment(env):
        _log(f"Proxy environment: {note}")
    return env


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


def _range_dir(output_dir: Path, start: int, end: int) -> Path:
    return output_dir / "parts" / f"pages-{start + 1:03d}-{end + 1:03d}"


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
        result = subprocess.run(invocation, cwd=ROOT, env=_mineru_env())
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
        env = _mineru_env()
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


def merge(args: argparse.Namespace, state: dict[str, Any]) -> Path:
    # 规则对应: GEN-005（按原始页序合并、带页码范围标记）、GEN-010（页眉页脚回收）、
    # GEN-030（附录标题重组）、GEN-019（显式 front-matter 优先）。
    expected = list(range(0, state.get("pageCount", 0), args.chunk_size))
    completed = {item["start"]: item for item in state.get("parts", []) if item.get("status") == "complete"}
    missing = [start + 1 for start in expected if start not in completed]
    if missing:
        raise RuntimeError(f"Cannot merge: MinerU output is missing for pages starting at {missing}")
    if not expected:
        # 没有任何分片记录时，后面的封面/标题恢复会以 parts_raw[0] 触发 IndexError
        # （实测：对 raw 起点文档根跑 --stage merge）。这里给出可操作的说明而不是崩栈。
        raise RuntimeError(
            "Cannot merge: this document has no MinerU page ranges recorded "
            "（pipeline-state 里没有 pageCount/parts）——请先跑 --stage extract，"
            "或对已有 raw 输入改用 tools/build_ssir.py")
    if not completed:
        raise RuntimeError("Cannot merge: no completed MinerU page range found under this document root")

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
    if not parts_raw:
        raise RuntimeError("Cannot merge: no page range produced any CSM text under this document root")
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
            # 封面兜底（GEN-016 英文标题 / GEN-014 机构）只读抽取阶段写出的
            # layout.json ``cover`` 通道（docs/16 §3；通道缺失时函数内部回退源 PDF）。
            cover_meta = _cover_metadata(part_dir, parts_raw[0], layout=load_stage_layout(args))
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
    # 单元格行结构，源 PDF 文本层完整保留——merge 阶段按抽取阶段写出的
    # layout.json 文本层通道恢复（docs/16 §3：merge 不再打开源 PDF）。
    merged_text = _restore_ellipsis_lines(merged_text, load_stage_layout(args))
    # 表注锚点上标字母回收（CSM-OCR-015）：MinerU OCR 丢表头/单元格上标字母、只留
    # 表注定义行（GB_T_20001.10-2014 表1 型）→ 从源 PDF 文本层补回单元格尾部标记。
    # 表角标回收的读数来自 layout.json 的 textSpans/pages 通道（docs/16 §3；通道缺失时
    # 函数内部回退读源 PDF）。
    merged_text, recovered_markers = _recover_table_note_markers(
        merged_text, args.input, layout=load_stage_layout(args)
    )
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


def _build_parser() -> argparse.ArgumentParser:
    """CLI 参数定义（独立函数便于单测断言默认值，如 --hybrid-tables 默认关闭）。"""
    parser = argparse.ArgumentParser(description="PDF extraction pipeline: PDF → MinerU recognition → merged raw CSM (add --stage all to continue to canonical/SSIR, --render for a PDF; round-trip verification is the separate tools/verify_conversion.py).")
    parser.add_argument("file", nargs="?", type=str, default=None,
                        help="standard file name resolved under corpus/golden/ (e.g. T_ZZB_2224-2021 or T_ZZB_2224-2021.pdf). "
                             "只解析 PDF（Word 输入已永久放弃）。 "
                             "Shortcut mode: implies --stage all --render (verification is the separate tools/verify_conversion.py). "
                             "若 out/mineru/<ID>/02_canonical/<ID>.canonical.md 已存在，则跳过 OCR/PDF 抽取与 "
                             "normalize，直接从 canonical 续跑（等同 tools/reprocess_canonical.py）。")
    parser.add_argument("--input", type=Path, help="input PDF of the national standard (alternative to the positional file name; full or relative path)")
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
    parser.add_argument("--stage", choices=("extract", "layout", "merge", "finalize", "all"), default="all")
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
        # 快捷模式：文件名默认在 corpus/golden/ 下解析，只解析 PDF
        # （Word 输入已暂时停用）；也允许子路径。
        file_path = Path(args.file)
        if file_path.is_file():
            args.input = file_path
        else:
            candidate = ROOT / "corpus" / "golden" / args.file
            # 注意：不能用 with_suffix(".pdf")——标准号含点（GB_T_1.1-2020）时
            # Path 会把 ".1-2020" 当成后缀替换成 GB_T_1.pdf；直接整体拼后缀保留点。
            resolved = None
            for ext in ("", ".pdf"):
                probe = candidate if not ext else ROOT / "corpus" / "golden" / f"{args.file}{ext}"
                if probe.is_file():
                    resolved = probe
                    break
            if resolved is None:
                parser.error(f"file not found under corpus/golden/: {args.file!r} (looked for the name, then .pdf)")
            args.input = resolved
        # 单命令完成全部：导入/提取 + 渲染（验证已独立成 tools/verify_conversion.py，需要时单独跑）。
        args.render = True
    suffix = args.input.suffix.lower() if args.input else ""
    if not args.input or not args.input.is_file() or suffix != ".pdf":
        # Word（.docx/.doc）输入已永久放弃：明确报错，不做任何 Word 导入。
        hint = "（Word 输入已永久放弃，请提供 PDF）" if suffix in (".docx", ".doc") else ""
        parser.error(f"input must be an existing PDF document{hint}: {args.input}")
    args.input_kind = "pdf"
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
    _log(f"Stage: {args.stage}; render after parsing: {args.render}")

    try:
        # 版面通道（docs/16 §2.3/§3）：抽取阶段产出 01_extract/<stem>.layout.json，
        # 下游（merge 的省略号恢复、finalize 与续跑的版面印记/脚注回收）只读它，
        # 不再打开源 PDF。独立的 `--stage layout` 只做这一件事——可对既有文档根
        # 单独补产出，不需要重跑 MinerU（抽取阶段是唯一可读源 PDF 的阶段）。
        if args.stage == "layout":
            write_stage_layout(args, state)
            _write_manifest(args, state)
            _log("Layout stage complete: 01_extract/<stem>.layout.json written; downstream stages read it instead of the source PDF.")
            return 0
        if args.stage in {"merge", "finalize", "all"}:
            write_stage_layout(args, state)
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


# 表注定义行的“注文拆条”：注文标记（小写字母）出现在句末标点之后或单元格行首，
# 且后随汉字/引号——用于把“a注文…b注文…”连排单元格拆成逐条注（GB_T_5171.1-2014
# 表19 a/b、表20 a~h 型，MinerU 把整段连排进一格且丢字）。
_TABLE_NOTE_ITEM_SPLIT_RE = re.compile(r"(?:(?<=^)|(?<=[。；;，,、:：])|\s(?=[a-z]))\s*([a-z])(?=[\u4e00-\u9fff“”『「\"'])")


if __name__ == "__main__":
    raise SystemExit(main())
