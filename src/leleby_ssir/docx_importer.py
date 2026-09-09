"""docx → canonical 级 CSM Markdown（把 Word 稿件放回流水线的输入侧）。

闭环场景（2026-09）：``04_render/<ID>.render.docx``（docx_renderer 产物）放回
``corpus/golden/`` 后，流水线不再做 MinerU PDF 识别，而是从 Word 直接导入：
docx → canonical 级 CSM → normalize → parse → SSIR → render（PDF + 新 docx）。

导入映射（与 docx_renderer 输出约定一一对应，保证自洽往返）：
- core properties.comments（JSON，见 docx_renderer.flat_metadata）→ YAML front
  matter；Word 内置标题样式（Heading 1..6 / outlineLvl）→ ``#`` 级标题
  （Heading N → ``#`` 重复 N+1 次，与 render.md 的章=``##`` 一致）；
- Word 原生表格（gridSpan/vMerge）→ pipe 表格 + ``<!-- ssir:table -->`` /
  ``<!-- ssir:table-merge -->`` 指令（坐标：row 0-based、column 1-based，
  与 csm_renderer 一致；被覆盖位置补 ``''`` 占位格）；
- 嵌入位图 → 导出 ``assets/images/<sha256前16>.<ext>`` 并以 ``![](assets/...)``
  引用；上标/下标 run → Unicode 上/下标字形（0-9、±()=n；PDF 渲染端对
  缺字形 Unicode 上标有 <super> 兜底，自环渲染视觉不变）；
- 全粗体行（题注形态 ``表N …``）→ ``**…**``。

注意：Word 不保存语义边界（SSIR 的 note/list/example 等 presentationType），
导入结果等同"raw 级用户 markdown"，交给 normalize（GEN-*）与 builder 重新
判定即可；SSIR 中表格合并、图、标题层级是保结构字段，导入精确还原。
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .docx_renderer import DOCX_DEPENDENCY_HINT, METADATA_MARK
from .naming import standard_number_from_text
from .parser import escape_table_cell

__all__ = ["docx_to_csm_markdown", "docx_metadata"]

# Unicode 上标/下标字形映射（PDF 渲染端对缺字形上标有 <super> 兜底）
_SUPERSCRIPT_MAP = {
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "-": "⁻", "−": "⁻", "+": "⁺", "(": "⁽", ")": "⁾", "=": "⁼", "n": "ⁿ",
}
_SUBSCRIPT_MAP = {
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "-": "₋", "−": "₋", "+": "₊", "(": "₍", ")": "₎", "=": "₌",
}
_HEADING_STYLE_RE = re.compile(r"heading\s*(\d+)|标题\s*(\d+)", re.IGNORECASE)


def _qn() -> Any:
    from docx.oxml.ns import qn
    return qn


def docx_metadata(path: str | Path) -> dict[str, Any]:
    """只读 docx 元数据（隐藏元数据段优先 → core properties），供流水线前置使用。"""
    docx = _document(path)
    metadata: dict[str, Any] = {}
    for paragraph in docx.paragraphs:
        text = paragraph.text or ""
        if text.startswith(METADATA_MARK):
            try:
                parsed = json.loads(text[len(METADATA_MARK):])
                if isinstance(parsed, dict):
                    metadata = parsed
            except (json.JSONDecodeError, ValueError):
                metadata = {}
            break
    core = docx.core_properties
    metadata.setdefault("csm-version", "1.0")
    metadata.setdefault("language", "zh-CN")
    if not metadata.get("title") and getattr(core, "title", ""):
        metadata["title"] = core.title
    number = str(metadata.get("standard-number") or metadata.get("document-identifier")
                  or getattr(core, "subject", "") or "")
    if not re.search(r"\d", number):
        number = ""
    metadata["document-identifier"] = number or metadata.get("document-identifier", "")
    if number:
        metadata["standard-number"] = number
    if not metadata.get("document-type"):
        metadata["document-type"] = "standard" if re.search(r"\d", number) else "other"
    metadata["source"] = {
        "mode": "docx-import",
        "original-file-name": Path(path).name,
        "provenance": "none",
    }
    metadata.setdefault("extensions", {})
    return metadata


def _document(path: str | Path):
    try:
        from docx import Document
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(DOCX_DEPENDENCY_HINT) from exc
    try:
        return Document(str(path))
    except Exception as exc:
        raise RuntimeError(
            f"无法读取 Word 文档 {path}：{exc}。仅支持 .docx（OOXML）；"
            "旧版二进制 .doc 请先用 Word「另存为 .docx」再导入。"
        ) from exc


def docx_to_csm_markdown(path: str | Path, *, assets_root: str | Path | None = None,
                         title: str | None = None, standard_number: str | None = None,
                         document_type: str | None = None) -> tuple[dict[str, Any], str, list[str]]:
    """docx → (front_matter, canonical 级 CSM 文本, warnings)。

    图片导出到 ``assets_root/assets/images/``（缺省为 docx 所在目录），
    md 中以 ``assets/images/…`` 相对路径引用（与流水线资产布局一致）。
    """
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    source = Path(path)
    assets_root = Path(assets_root) if assets_root else source.parent
    warnings: list[str] = []
    document = _document(source)
    metadata = docx_metadata(source)
    if title:
        metadata["title"] = title
    if standard_number:
        metadata["standard-number"] = standard_number
        metadata["document-identifier"] = standard_number
    if document_type:
        metadata["document-type"] = document_type
    doc_title = str(metadata.get("title") or "").strip()
    if not doc_title:
        doc_title = _first_heading(document)
        metadata["title"] = doc_title
    if not str(metadata.get("document-identifier") or "").strip():
        metadata["document-identifier"] = doc_title
        if not re.search(r"\d", doc_title):
            metadata["document-type"] = "other"

    lines: list[str] = [f"# {doc_title}", ""]
    pending_caption: str | None = None
    table_serial = 0

    qn = _qn()
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            paragraph = Paragraph(child, document)
            if (paragraph.text or "").startswith(METADATA_MARK):
                continue  # 隐藏元数据段不进入正文
            kind, payload = _paragraph_items(paragraph, source, assets_root, docx_warnings=warnings)
            if kind == "heading":
                level, text = payload
                if level == 1 and text.strip() == doc_title:
                    continue  # 封面/正文首页重复的标准名称标题（render.md 无此节点）
                heading_line = _heading_markdown(text, level)
                if heading_line:
                    lines.append(heading_line)
                    lines.append("")
                continue
            if kind == "caption":
                pending_caption = payload.strip()
                continue
            if kind == "unit":
                lines.append(payload.strip())
                lines.append("")
                continue
            # 普通文本 / 图片行
            if payload.strip():
                lines.append(payload.rstrip())
                lines.append("")
        elif child.tag == qn("w:tbl"):
            table_serial += 1
            table = Table(child, document)
            lines.extend(_table_markdown(table, pending_caption, table_serial))
            pending_caption = None
        else:
            continue

    # 未消费的题注（其后无表格）降级为加粗行
    if pending_caption:
        lines.append(f"**{pending_caption}**")
        lines.append("")

    text = _assemble(metadata, lines)
    return metadata, text, warnings


def _first_heading(document: Any) -> str:
    for paragraph in document.paragraphs:
        level = _heading_level_of(paragraph)
        if level is not None and paragraph.text.strip():
            return paragraph.text.strip()
    return ""


def _heading_level_of(paragraph: Any) -> int | None:
    style = paragraph.style
    name = ""
    style_id = ""
    try:
        name = style.name or ""
        style_id = getattr(style, "style_id", "") or ""
    except Exception:
        pass
    for candidate in (re.sub(r"\s+", "", name), re.sub(r"\s+", "", style_id)):
        match = _HEADING_STYLE_RE.search(candidate)
        if match:
            return int(match.group(1) or match.group(2))
    ppr = paragraph._p.pPr
    if ppr is not None:
        outline = ppr.find(_qn()("w:outlineLvl"))
        if outline is not None:
            try:
                return min(max(int(outline.get(_qn()("w:val"))) + 1, 1), 6)
            except (TypeError, ValueError):
                return None
    return None


def _heading_markdown(text: str, level: int) -> str:
    text = re.sub(r"\u3000", " ", text).strip()
    # 编号与标题间用普通空格（与 csm_renderer 的 `#` 输出一致）
    return f"{'#' * min(level + 1, 6)} {text}"


def _paragraph_items(paragraph: Any, source: Path, assets_root: Path,
                     docx_warnings: list[str]) -> tuple[str, Any]:
    """段落 → (kind, payload)。kind: heading/caption/unit/text。

    text 形态同时收集行内上/下标字形与行内图引用。
    """
    style_name = ""
    try:
        style_name = paragraph.style.name or ""
    except Exception:
        pass
    heading_level = _heading_level_of(paragraph)

    if heading_level is not None:
        return "heading", (heading_level, paragraph.text)

    text = _paragraph_text_runs(paragraph, source, assets_root, docx_warnings)
    plain = text.strip()
    if style_name.endswith("Table Caption") and (plain.startswith("表") or plain.startswith("图")):
        return "caption", _strip_emphasis(plain)
    if style_name.endswith("Figure Caption"):
        return "text", plain
    if plain.startswith("单位为") and len(plain) <= 12:
        return "unit", plain
    return "text", text


def _strip_emphasis(text: str) -> str:
    return text.replace("**", "").strip()


def _paragraph_text_runs(paragraph: Any, source: Path, assets_root: Path,
                         docx_warnings: list[str]) -> str:
    """run 级文本提取：上标/下标 → Unicode 字形；行内图 → md 引用并导出资产。"""
    qn = _qn()
    chunks: list[str] = []
    text_runs = [run for run in paragraph.runs if run.text and run.text.strip()]
    bold_all = bool(text_runs) and all(run.font.bold for run in text_runs)
    for run in paragraph.runs:
        if run.text:
            text = _map_run_text(run.text, run.font.superscript, run.font.subscript)
            chunks.append(text)
        for blip in run._r.iter(qn("a:blip")):
            ref = _export_blip(paragraph, blip, source, assets_root, docx_warnings)
            if ref:
                chunks.append(f"![]({ref})")
    if not chunks:
        return ""
    if bold_all:
        return "**" + "".join(chunks).strip() + "**"
    return "".join(chunks)


def _map_run_text(text: str, superscript: bool, subscript: bool) -> str:
    if superscript:
        return "".join(_SUPERSCRIPT_MAP.get(ch, ch) for ch in text)
    if subscript:
        return "".join(_SUBSCRIPT_MAP.get(ch, ch) for ch in text)
    return text


def _export_blip(paragraph: Any, blip: Any, source: Path, assets_root: Path,
                 docx_warnings: list[str]) -> str:
    embed = blip.get(_qn()("r:embed"))
    if not embed:
        return ""
    rels = paragraph.part.rels
    if embed not in rels:
        return ""
    try:
        target = rels[embed].target_part
        blob = target.blob
    except Exception:
        return ""
    content_type = getattr(target, "content_type", "") or "image/png"
    extension = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
                 "image/bmp": ".bmp", "image/tiff": ".tiff"}.get(content_type, ".png")
    digest = hashlib.sha256(blob).hexdigest()[:16]
    image_dir = assets_root / "assets" / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{digest}{extension}"
    target_path = image_dir / filename
    if not target_path.is_file():
        target_path.write_bytes(blob)
    return f"assets/images/{filename}"


def _table_markdown(table: Any, caption: str | None, table_serial: int) -> list[str]:
    """Word 原生表格 → 指令 + pipe 表格 + merge 注释（坐标同 csm_renderer）。"""
    qn = _qn()
    table_id = f"docx-import-t{table_serial:03d}"
    header_rows = 0
    rows: list[list[tuple[str, int, str | None]]] = []
    for row_index, tr in enumerate(table._tbl.findall(qn("w:tr"))):
        tr_pr = tr.find(qn("w:trPr"))
        if tr_pr is not None and tr_pr.find(qn("w:tblHeader")) is not None:
            header_rows = max(header_rows, row_index + 1)
        grid_row: list[tuple[str, int, str | None]] = []
        for tc in tr.findall(qn("w:tc")):
            tc_pr = tc.find(qn("w:tcPr"))
            colspan = 1
            vmerge: str | None = None
            if tc_pr is not None:
                grid_span = tc_pr.find(qn("w:gridSpan"))
                if grid_span is not None:
                    try:
                        colspan = int(grid_span.get(qn("w:val")) or 1)
                    except (TypeError, ValueError):
                        colspan = 1
                v_merge = tc_pr.find(qn("w:vMerge"))
                if v_merge is not None:
                    # OOXML: val="restart" 为合并起点；无 val 或 val="continue" 为延续格。
                    vmerge = "restart" if (v_merge.get(qn("w:val")) or "continue") == "restart" else "continue"
            grid_row.append((_tc_text(tc), colspan, vmerge))
        rows.append(grid_row)

    if not rows:
        return []

    columns = sum(item[1] for item in rows[0]) or max(len(grid_row) for grid_row in rows)
    occupied = [[False] * columns for _ in rows]
    output = [[""] * columns for _ in rows]
    merges: list[tuple[int, int, int, int]] = []

    for row_index, grid_row in enumerate(rows):
        col_index = 0
        for text, colspan, vmerge in grid_row:
            if vmerge == "continue":
                # 上方合并的延续格：其列必然已 occupied，直接消费并前进。
                for c in range(col_index, min(col_index + colspan, columns)):
                    occupied[row_index][c] = True
                col_index += colspan
                continue
            # 兜底：某些写入器省略被覆盖列的占位 tc 时，物理 tc 需越过上方
            # 合并占用的列再落位（Word/python-docx 总会写 vMerge continue，
            # 正常路径不会触发此分支）。
            while col_index < columns and occupied[row_index][col_index]:
                col_index += 1
            if col_index >= columns:
                break
            rowspan = 1
            if vmerge == "restart":
                for below in range(row_index + 1, len(rows)):
                    if _is_continue_at(rows[below], col_index, columns):
                        rowspan += 1
                    else:
                        break
            output[row_index][col_index] = text
            for r in range(row_index, min(row_index + rowspan, len(rows))):
                for c in range(col_index, min(col_index + colspan, columns)):
                    occupied[r][c] = True
            if rowspan > 1 or colspan > 1:
                merges.append((row_index, col_index, rowspan, colspan))
            col_index += colspan

    lines = [f'<!-- ssir:table id="{table_id}" header-rows="{header_rows}" -->', ""]
    if caption:
        lines.append(f"**{_strip_emphasis(caption)}**")
        lines.append("")
    header_separator_written = False
    for row_index in range(len(output)):
        cells = [_escape_pipe(cell) for cell in output[row_index]]
        lines.append("| " + " | ".join(cells) + " |")
        if not header_separator_written:
            lines.append("| " + " | ".join("---" for _ in cells) + " |")
            header_separator_written = True
    for r0, c0, rs, cs in merges:
        lines.append(
            f'<!-- ssir:table-merge table="{table_id}" row="{r0}" column="{c0 + 1}" '
            f'rowspan="{rs}" colspan="{cs}" -->'
        )
    lines.append("")
    return lines


def _tc_text(tc: Any) -> str:
    qn = _qn()
    paragraphs: list[str] = []
    for p in tc.findall(qn("w:p")):
        parts: list[str] = []
        for run in p.findall(qn("w:r")):
            rpr = run.find(qn("w:rPr"))
            superscript = False
            if rpr is not None:
                vert = rpr.find(qn("w:vertAlign"))
                superscript = vert is not None and vert.get(qn("w:val")) == "superscript"
            text = "".join(node.text or "" for node in run.iter(qn("w:t")))
            parts.append(_map_run_text(text, superscript, False))
        paragraphs.append("".join(parts))
    return "<br>".join(paragraphs)


def _is_continue_at(row: list[tuple[str, int, str | None]], col_index: int,
                    columns: int) -> bool:
    cursor = 0
    for _text, colspan, vmerge in row:
        if cursor <= col_index < cursor + colspan:
            return vmerge == "continue"
        cursor += colspan
        if cursor > col_index:
            return False
    return False


def _escape_pipe(text: str) -> str:
    # 幂等转义：docx 文本可能已含转义管道（自环 render.docx 导入），无条件转义会
    # 二次成双反斜杠、破坏后续 parse（与 csm_normalizer/escape_table_cell 同规则）。
    return escape_table_cell(text)


def _assemble(metadata: dict[str, Any], body_lines: list[str]) -> str:
    import yaml

    title = str(metadata.get("title") or "").strip()
    metadata.setdefault("document-identifier", title or "unknown")
    if not metadata.get("language"):
        metadata["language"] = "zh-CN"
    lines = ["---", yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).strip(), "---", ""]
    # 标题 H1 已在 body_lines 开头（# title）；body 不含标题时补
    has_h1 = any(line.startswith("# ") for line in body_lines)
    if not has_h1 and title:
        lines.append(f"# {title}")
        lines.append("")
    lines.extend(body_lines)
    return "\n".join(lines).rstrip() + "\n"
