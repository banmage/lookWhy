"""SSIR JSON → docx（最终渲染 Word 产物，doc_1）。

与 ``render.pdf`` 同源（同一个 SSIR document），保证**技术内容等价**：
封面信息（标准号/名称/英文名/机构/日期/代替关系）、目次、正文全部元素
（标题层级、段落、注、列项、表格含合并单元格与重复表头、图、公式、
示例框、未知内容）逐一呈现；Word 不承诺与 reportlab 逐页分页一致。

表示层修复与 PDF 渲染共用同一规则（复用 ``pdf_renderer`` 纯函数）：
- 正文脚注标记 → Word 上标（GBT-X04 执行侧 ``_footnote_superscripts``）；
- 表格单元格脚注标记/平拍指数（1030→10³⁰、s−1→s⁻¹）→ Word 上标
  （GBT-C18 ``_table_cell_superscripts``）；
- 行内 ``$...$`` LaTeX → 可读文本（``_latex_to_text``，PDF ``_markup`` 同款）。

规则对应: GEN-070（SSIR→渲染）、GBT-B02/B03（章条标题黑体/正文宋体）、
GBT-B07（表编号表题居中、表头框线）、GBT-X02（转页重复表头、合并单元格）、
GBT-X01/B06（图与图题）、GBT-X06（公式另行编排）、GBT-B11（示例框）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .pdf_renderer import (
    _TABLE_NOTE_CELL_RE,
    _clause_leading_number,
    _footnote_superscripts,
    _heading_parts,
    _heading_text,
    _is_toc_node,
    _latex_to_text,
    _order,
    _protect_literal_stars,
    _resolve_asset,
    _restore_literal_stars,
    _split_table_note_parts,
    _table_cell_superscripts,
    _toc_indent_level,
    _toc_label,
    _toc_nodes,
)
from .validation import validate_ssir

__all__ = ["render_ssir_docx", "render_docx_file", "flat_metadata", "DOCX_DEPENDENCY_HINT"]

DOCX_DEPENDENCY_HINT = "docx 渲染需要 python-docx；安装项目依赖: .venv/bin/pip install -e .（python-docx>=1.0）"

# 隐藏元数据段落标记（core properties 有 255 字符上限，完整 front matter
# JSON 存入正文首个隐藏段落，docx_importer 读取/跳过——docx→CSM 闭环载体）。
METADATA_MARK = "SSIR-META:"

# --------------------------------------------------------------------------
# 版式常量（GB/T 1.1-2020 附录 F 精神：标题黑体、正文宋体、小五注/表）
# --------------------------------------------------------------------------
EA_SONG = "宋体"
EA_HEI = "黑体"
LATIN = "Times New Roman"

STYLE_TABLE_CAPTION = "SSIR Table Caption"    # 表N 题名（黑体居中）
STYLE_FIGURE_CAPTION = "SSIR Figure Caption"   # 图N 题名（黑体居中）
STYLE_UNIT = "SSIR Unit"                       # 单位为毫米（小五右对齐贴表上）
STYLE_NOTE = "SSIR Note"                       # 注：…（小五宋体）
STYLE_LIST = "SSIR List Item"                  # 列项（原样 marker + 悬挂缩进）
STYLE_CODE = "SSIR Code"                       # 未知内容（等宽灰底）
STYLE_FORMULA = "SSIR Formula"                 # 公式（居中）
STYLE_TOC = "SSIR TOC"                         # 目次条目
STYLE_EXAMPLE = "SSIR Example"                 # 示例框内容（浅灰底）
STYLE_EXAMPLE_TITLE = "SSIR Example Title"     # 「示例N：」黑体居中
STYLE_TABLE_TEXT = "SSIR Table Text"           # 表内文字（小五）
STYLE_TABLE_NOTE = "SSIR Table Note"           # 表注行（居左首行空两格）

_SUP_OPEN, _SUP_CLOSE = "\x00SUP\x00", "\x00/SUP\x00"
_SUB_OPEN, _SUB_CLOSE = "\x00SUB\x00", "\x00/SUB\x00"
_BR_SENTINEL = "\x00BR\x00"
_LATEX_INLINE_RE = re.compile(r"\$([^$\n]+)\$")
_IMG_MD_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
# PDF _markup 同款：平排条号前空一字距（Word 正文段显示贴近）
_CLAUSE_SPACE_RE = re.compile(
    r"(?m)^((?:\d+\.){1,3}\d+|[A-Z]\.\d+(?:\.\d+)*)[ \u3000]*([\u4e00-\u9fff（(])"
)


def _docx_ns() -> dict[str, Any]:
    try:
        from docx import Document  # noqa: F401
        from docx.enum.style import WD_STYLE_TYPE
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Cm, Pt, RGBColor
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(DOCX_DEPENDENCY_HINT) from exc
    return {
        "Document": Document,
        "WD_STYLE_TYPE": WD_STYLE_TYPE,
        "ALIGN": WD_ALIGN_PARAGRAPH,
        "OxmlElement": OxmlElement,
        "qn": qn,
        "Cm": Cm,
        "Pt": Pt,
        "RGBColor": RGBColor,
    }


# --------------------------------------------------------------------------
# 字体/样式小工具
# --------------------------------------------------------------------------

def _style_fonts(style: Any, docx: dict[str, Any], *, ea: str, latin: str = LATIN,
                 size_pt: float | None = None, bold: bool = False) -> None:
    qn = docx["qn"]
    style.font.name = latin
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = docx["OxmlElement"]("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), latin)
    rfonts.set(qn("w:hAnsi"), latin)
    rfonts.set(qn("w:eastAsia"), ea)
    if size_pt is not None:
        style.font.size = docx["Pt"](size_pt)
    style.font.bold = bold
    style.font.color.rgb = docx["RGBColor"](0, 0, 0)


def _run_fonts(paragraph: Any, text: str, docx: dict[str, Any], *, ea: str = EA_SONG,
               latin: str = LATIN, bold: bool = False, italic: bool = False,
               superscript: bool = False, subscript: bool = False,
               size_pt: float | None = None) -> None:
    """写入 run 文本并设置中西文字体；防御性剔除 XML 非法控制字符。"""
    qn = docx["qn"]
    if not text:
        return
    # 字面星号 AST 哨兵在写 run 前还原（_add_markup 保护；含 NUL 会被下方
    # 非法字符过滤剔除，必须先还原成可见 *）。
    text = _restore_literal_stars(text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    run = paragraph.add_run(text)
    run.font.name = latin
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = docx["OxmlElement"]("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), latin)
    rfonts.set(qn("w:hAnsi"), latin)
    rfonts.set(qn("w:eastAsia"), ea)
    if bold:
        run.font.bold = True
    if italic:
        run.font.italic = True
    if superscript:
        run.font.superscript = True
    if subscript:
        run.font.subscript = True
    if size_pt is not None:
        run.font.size = docx["Pt"](size_pt)


def _style_shading(style: Any, docx: dict[str, Any], fill: str) -> None:
    qn = docx["qn"]
    ppr = style.element.get_or_add_pPr()
    shd = docx["OxmlElement"]("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    ppr.append(shd)


def _paragraph_shading(paragraph: Any, docx: dict[str, Any], fill: str) -> None:
    qn = docx["qn"]
    ppr = paragraph._p.get_or_add_pPr()
    shd = docx["OxmlElement"]("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    ppr.append(shd)


def _table_borders(table: Any, docx: dict[str, Any]) -> None:
    qn = docx["qn"]
    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = docx["OxmlElement"]("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = borders.find(qn(f"w:{edge}"))
        if element is None:
            element = docx["OxmlElement"](f"w:{edge}")
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")   # 0.5pt
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), "000000")


def _repeat_header_rows(table: Any, header_rows: int, docx: dict[str, Any]) -> None:
    qn = docx["qn"]
    for row in table.rows[:header_rows]:
        tr_pr = row._tr.get_or_add_trPr()
        if tr_pr.find(qn("w:tblHeader")) is None:
            tr_pr.append(docx["OxmlElement"]("w:tblHeader"))


def _merge_cleanup(cell: Any, docx: dict[str, Any]) -> None:
    """python-docx merge() 会把被合并格的空段落并入原点格——清除多余空行。"""
    qn = docx["qn"]
    paragraphs = cell._tc.findall(qn("w:p"))
    if len(paragraphs) <= 1:
        return
    for paragraph in paragraphs[1:]:
        text = "".join(node.text or "" for node in paragraph.iter(qn("w:t")))
        if not text.strip():
            paragraph.getparent().remove(paragraph)


def _picture_size(path: Path) -> tuple[float, float]:
    try:
        from PIL import Image
        with Image.open(path) as image:
            width_px, height_px = image.size
    except Exception:
        return 8.0, 6.0
    if width_px <= 0 or height_px <= 0:
        return 8.0, 6.0
    width_cm = width_px * 2.54 / 96.0
    height_cm = height_px * 2.54 / 96.0
    max_w, max_h = 14.5, 18.0
    scale = min(1.0, max_w / width_cm, max_h / height_cm)
    return width_cm * scale, height_cm * scale


def _add_picture(paragraph: Any, image_path: Path, docx: dict[str, Any],
                 max_width_cm: float | None = None) -> None:
    width_cm, height_cm = _picture_size(image_path)
    if max_width_cm is not None and width_cm > max_width_cm:
        scale = max_width_cm / width_cm
        width_cm, height_cm = max_width_cm, height_cm * scale
    paragraph.add_run().add_picture(
        str(image_path), width=docx["Cm"](width_cm), height=docx["Cm"](height_cm)
    )


# --------------------------------------------------------------------------
# 行内标记 → runs（**bold**、$latex$、SUP/SUB 哨兵、行内图）
# --------------------------------------------------------------------------

_SEGMENT_RE = re.compile(
    r"!\[([^\]]*)\]\(([^)\s]+)\)"                # 1-2 image
    r"|\*\*(.+?)\*\*"                            # 3 bold
    r"|(?<!\*)\*([^*\n]+)\*(?!\*)"               # 4 italic
    r"|`([^`\n]+)`"                              # 5 code
    r"|\$([^$\n]+)\$"                            # 6 latex
    r"|\x00SUP\x00(.*?)\x00/SUP\x00"             # 7 sup
    r"|\x00SUB\x00(.*?)\x00/SUB\x00"             # 8 sub
)


def _add_markup(paragraph: Any, text: str, docx: dict[str, Any], *,
                asset_dir: Path | None = None, ea: str = EA_SONG,
                size_pt: float | None = None, center_images: bool = True) -> None:
    """带行内标记/公式/图片的文本写入段落（哨兵 → 上/下标，$..$ → 拍平文本）。"""
    # CommonMark 转义字面星号（“\*、\*\*、\*\*\*”，GB_T_1.1-2020 9.12.1）
    # → 字面星号：parser 不反转义、textContent 保留反斜杠，Word 里会字面
    # 显示、且残留 * 会被 _SEGMENT_RE 的 italic/bold 组误配。保护为哨兵，
    # _run_fonts 写文本时还原（两侧非拉丁字母/数字的簇=字面星号；markdown
    # 强调 *word*/**word** 两侧有词字符，不受影响）。
    text = _protect_literal_stars(text)
    position = 0
    for match in _SEGMENT_RE.finditer(text):
        if match.start() > position:
            _run_fonts(paragraph, text[position:match.start()].replace(_BR_SENTINEL, ""),
                       docx, ea=ea, size_pt=size_pt)
        if match.group(1) is not None:
            image_path = _resolve_asset(asset_dir, match.group(2)) if asset_dir else Path(match.group(2))
            if image_path.is_file():
                _add_picture(paragraph, image_path, docx, max_width_cm=8.0)
            else:
                _run_fonts(paragraph, f"[图像资产缺失: {match.group(2)}]", docx, ea=ea, size_pt=size_pt)
        elif match.group(3) is not None:
            _run_fonts(paragraph, match.group(3), docx, ea=ea, size_pt=size_pt, bold=True)
        elif match.group(4) is not None:
            _run_fonts(paragraph, match.group(4), docx, ea=ea, size_pt=size_pt, italic=True)
        elif match.group(5) is not None:
            _run_fonts(paragraph, match.group(5), docx, ea=ea, size_pt=size_pt)
        elif match.group(6) is not None:
            # 行内 LaTeX 拍平（同 PDF _markup）：输出可能带 SUP/SUB 哨兵
            flat = _latex_to_text(match.group(6))
            _add_markup(paragraph, flat, docx, asset_dir=asset_dir, ea=ea, size_pt=size_pt)
        elif match.group(7) is not None:
            _run_fonts(paragraph, match.group(7), docx, ea=ea, size_pt=size_pt, superscript=True)
        elif match.group(8) is not None:
            _run_fonts(paragraph, match.group(8), docx, ea=ea, size_pt=size_pt, subscript=True)
        position = match.end()
    if position < len(text):
        _run_fonts(paragraph, text[position:].replace(_BR_SENTINEL, ""), docx, ea=ea, size_pt=size_pt)


def _plain(text: str) -> str:
    """剥行内标记得纯文本（用于样式判断）。"""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", text)
    return text


def _flatten_latex(text: str) -> str:
    """行内 $...$ → 可读文本（PDF _markup 同款）；SUP/SUB 哨兵交给 run 层。"""
    return _LATEX_INLINE_RE.sub(lambda m: _latex_to_text(m.group(1)), text)


# --------------------------------------------------------------------------
# 元数据扁平化（front matter 语义，docx core properties 存储载体）
# --------------------------------------------------------------------------

def flat_metadata(document: dict[str, Any]) -> dict[str, Any]:
    """把 SSIR 元数据投影为 CSM front matter 字典（键与 csm_renderer 一致）。

    写入 docx core properties.comments（JSON）；docx_to_csm_markdown() 导入时
    原样还原，使 docx → CSM → SSIR 闭环不丢封面身份信息（标准号/日期/机构/
    ICS/CCS/代替关系等）。
    """
    common = document.get("metadata", {}).get("common", {})
    standard = document.get("metadata", {}).get("standard", {})
    source_file = document.get("sourceFiles", [{}])[0] if document.get("sourceFiles") else {}
    metadata: dict[str, Any] = {
        "csm-version": "1.0",
        "document-type": "standard" if document.get("documentType") == "standard" else "other",
        "document-identifier": common.get("documentIdentifier", ""),
        "title": common.get("title", ""),
        "language": common.get("language", "zh-CN"),
        "source": {
            "mode": "docx-export",
            "original-file-name": source_file.get("fileName", "render.docx"),
            "provenance": "ssir-render",
        },
        "extensions": {},
    }
    if document.get("documentType") == "standard":
        metadata["standard-number"] = standard.get("standardNumber", common.get("documentIdentifier", ""))
    for source_key, target_key in (
        ("titleEn", "title-en"),
        ("publicationDate", "publication-date"),
        ("effectiveDate", "effective-date"),
        ("issuer", "issuer"),
        ("conformityStatement", "conformity-statement"),
    ):
        if common.get(source_key):
            metadata[target_key] = common[source_key]
    for key in ("ics", "ccs", "replaces"):
        if standard.get(key):
            metadata[key] = standard[key]
    return metadata


# --------------------------------------------------------------------------
# 文档构建器
# --------------------------------------------------------------------------

class _DocxBuilder:
    """一次 doc_1 渲染的上下文（样式/注册表/资产目录）。"""

    def __init__(self, document: dict[str, Any], *, input_file: str | Path = "",
                 toc_depth: int | None = 2) -> None:
        self.docx = _docx_ns()
        from docx import Document

        self.document = document
        self.doc = Document()
        self.toc_depth = toc_depth
        self.warnings: list[str] = []
        self.asset_dir = Path(input_file).resolve().parent if input_file and Path(input_file).is_file() else Path(".")
        self.registries = {
            kind: {item["id"]: item for item in document.get(kind, [])}
            for kind in ("tables", "figures", "formulas", "unknownContents")
        }
        self.common = document.get("metadata", {}).get("common", {})
        self.standard = document.get("metadata", {}).get("standard", {})
        self.title = str(self.common.get("title") or "")
        self.body_title_inserted = False
        self._configure()

    # -- 页面与样式 ---------------------------------------------------------
    def _configure(self) -> None:
        docx = self.docx
        section = self.doc.sections[0]
        section.page_width = docx["Cm"](21.0)
        section.page_height = docx["Cm"](29.7)
        section.left_margin = docx["Cm"](2.5)
        section.right_margin = docx["Cm"](2.5)
        section.top_margin = docx["Cm"](2.5)
        section.bottom_margin = docx["Cm"](2.5)

        normal = self.doc.styles["Normal"]
        _style_fonts(normal, docx, ea=EA_SONG, size_pt=10.5)
        normal.paragraph_format.space_before = docx["Pt"](0)
        normal.paragraph_format.space_after = docx["Pt"](0)
        sizes = {1: 16.0, 2: 14.0, 3: 12.0, 4: 11.0, 5: 10.5, 6: 10.5}
        for level in range(1, 7):
            style = self.doc.styles[f"Heading {level}"]
            _style_fonts(style, docx, ea=EA_HEI, size_pt=sizes[level], bold=True)
            style.paragraph_format.space_before = docx["Pt"](12 if level == 1 else 6)
            style.paragraph_format.space_after = docx["Pt"](3)
            style.paragraph_format.keep_with_next = True

        def custom(name: str, *, ea: str = EA_SONG, size: float = 10.5, bold: bool = False,
                   align: Any | None = None, indent_cm: float | None = None,
                   first_indent_pt: float | None = None, space_after: float = 3.0,
                   fill: str | None = None) -> Any:
            try:
                style = self.doc.styles[name]
            except KeyError:
                style = self.doc.styles.add_style(name, docx["WD_STYLE_TYPE"].PARAGRAPH)
            _style_fonts(style, docx, ea=ea, size_pt=size, bold=bold)
            if align is not None:
                style.paragraph_format.alignment = align
            if indent_cm is not None:
                style.paragraph_format.left_indent = docx["Cm"](indent_cm)
            if first_indent_pt is not None:
                style.paragraph_format.first_line_indent = docx["Pt"](first_indent_pt)
            style.paragraph_format.space_before = docx["Pt"](0)
            style.paragraph_format.space_after = docx["Pt"](space_after)
            if fill:
                _style_shading(style, docx, fill)
            return style

        align = docx["ALIGN"]
        custom(STYLE_TABLE_CAPTION, ea=EA_HEI, align=align.CENTER, space_after=2)
        custom(STYLE_FIGURE_CAPTION, ea=EA_HEI, align=align.CENTER, space_after=6)
        custom(STYLE_UNIT, size=9.0, align=align.RIGHT, space_after=2)
        note = custom(STYLE_NOTE, size=9.0, align=align.JUSTIFY, indent_cm=0.2,
                      first_indent_pt=16.0, space_after=2)
        custom(STYLE_LIST, align=align.JUSTIFY, space_after=1)
        custom(STYLE_CODE, size=9.0, align=align.LEFT, space_after=2, fill="F2F2F2")
        custom(STYLE_FORMULA, align=align.CENTER, space_after=4)
        custom(STYLE_TOC, align=align.LEFT, space_after=2)
        custom(STYLE_EXAMPLE, align=align.JUSTIFY, space_after=2, fill="F2F2F2")
        custom(STYLE_EXAMPLE_TITLE, ea=EA_HEI, align=align.CENTER, space_after=3, fill="F2F2F2")
        cell = custom(STYLE_TABLE_TEXT, size=9.0, align=align.CENTER, space_after=0)
        cell.paragraph_format.alignment = None  # 单元格内由段落自行控制
        custom(STYLE_TABLE_NOTE, size=9.0, align=align.LEFT, first_indent_pt=18.0, space_after=0)
        _style_fonts(self.doc.styles["Normal"], docx, ea=EA_SONG, size_pt=10.5)

    # -- core properties -----------------------------------------------------
    def _core(self) -> None:
        core = self.doc.core_properties
        core.title = self.title
        number = str(self.standard.get("standardNumber") or self.common.get("documentIdentifier") or "")
        if number:
            core.subject = number
        if self.common.get("issuer"):
            core.author = str(self.common["issuer"])
        # 完整 front matter 元数据以隐藏段落存进正文（core properties 255 字符
        # 上限放不下）；docx_to_csm_markdown() 回灌时读取并跳过该段。
        payload = METADATA_MARK + json.dumps(flat_metadata(self.document), ensure_ascii=False)
        first = self.doc.paragraphs[0] if self.doc.paragraphs else self.doc.add_paragraph()
        paragraph = first.insert_paragraph_before()
        run = paragraph.add_run(payload)
        run.font.size = self.docx["Pt"](1)
        run.font.hidden = True
        paragraph.paragraph_format.space_before = self.docx["Pt"](0)
        paragraph.paragraph_format.space_after = self.docx["Pt"](0)

    # -- 封面 ----------------------------------------------------------------
    def has_cover(self) -> bool:
        return self.document.get("documentType") == "standard" or bool(self.standard.get("standardNumber"))

    def _cover_label(self) -> str:
        number = str(self.standard.get("standardNumber") or "")
        if not number:
            return ""
        if re.match(r"^GB", number):
            return "中华人民共和国国家标准"
        if re.match(r"^JB", number):
            return "中华人民共和国机械行业标准"
        if re.match(r"^DB", number):
            return "中华人民共和国地方标准"
        if re.match(r"^T/", number):
            return "团体标准"
        if re.match(r"^Q/", number):
            return "企业标准"
        return ""

    def render_cover(self) -> None:
        docx = self.docx
        align = docx["ALIGN"]
        number = str(self.standard.get("standardNumber") or "")
        title_en = str(self.common.get("titleEn") or "")
        issuer = str(self.common.get("issuer") or "")
        published = str(self.common.get("publicationDate") or "")
        effective = str(self.common.get("effectiveDate") or "")
        replaces = str(self.standard.get("replaces") or "")

        label = self._cover_label()
        if label:
            paragraph = self.doc.add_paragraph()
            paragraph.alignment = align.CENTER
            paragraph.paragraph_format.space_before = docx["Pt"](48)
            _run_fonts(paragraph, label, docx, ea=EA_HEI, size_pt=16)
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = align.CENTER
        paragraph.paragraph_format.space_before = docx["Pt"](30)
        _run_fonts(paragraph, number or "××", docx, ea=EA_HEI, size_pt=14)
        if replaces:
            paragraph = self.doc.add_paragraph()
            paragraph.alignment = align.CENTER
            _run_fonts(paragraph, f"代替 {replaces}", docx, ea=EA_SONG, size_pt=10.5)
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = align.CENTER
        paragraph.paragraph_format.space_before = docx["Pt"](36)
        _run_fonts(paragraph, self.title, docx, ea=EA_HEI, size_pt=22, bold=True)
        if title_en:
            paragraph = self.doc.add_paragraph()
            paragraph.alignment = align.CENTER
            _run_fonts(paragraph, title_en, docx, ea=EA_SONG, size_pt=12, italic=True)
        for _ in range(7):
            self.doc.add_paragraph("")
        if published or effective:
            paragraph = self.doc.add_paragraph()
            paragraph.alignment = align.CENTER
            pieces = []
            if published:
                pieces.append(f"{published} 发布")
            if effective:
                pieces.append(f"{effective} 实施")
            _run_fonts(paragraph, "  ".join(pieces), docx, ea=EA_SONG, size_pt=10.5)
        if issuer:
            paragraph = self.doc.add_paragraph()
            paragraph.alignment = align.CENTER
            _run_fonts(paragraph, issuer, docx, ea=EA_SONG, size_pt=12)
        self.doc.add_page_break()

    # -- 目次 ----------------------------------------------------------------
    def has_toc(self) -> bool:
        return any(_is_toc_node(node) for node in self._root_nodes())

    def _root_nodes(self) -> list[dict[str, Any]]:
        return sorted(self.document["structuralRoot"].get("children", []), key=_order)

    def render_toc(self) -> None:
        docx = self.docx
        align = docx["ALIGN"]
        heading = self.doc.add_paragraph(style="Heading 1")
        _run_fonts(heading, "目 次", docx, ea=EA_HEI, bold=True)
        for node in _toc_nodes(self._root_nodes(), self.toc_depth):
            label = _toc_label(node)
            if not label:
                continue
            level = _toc_indent_level(node)
            paragraph = self.doc.add_paragraph(style=STYLE_TOC)
            paragraph.paragraph_format.left_indent = docx["Cm"](0.55 * min(level, 6))
            _run_fonts(paragraph, label, docx, ea=EA_SONG)
        # 目次块内非行内容（目录页装饰图等）保留
        toc_node = next((node for node in self._root_nodes() if _is_toc_node(node)), None)
        if toc_node:
            for content in sorted(toc_node.get("contentElements", []), key=_order):
                if content.get("presentationType") == "figure":
                    self._figure_content(content)
        self.doc.add_page_break()

    # -- 正文 ----------------------------------------------------------------
    def render_body(self) -> None:
        nodes = self._root_nodes()
        index = 0
        while index < len(nodes):
            node = nodes[index]
            if _is_toc_node(node):
                index += 1
                continue
            if node.get("exampleContent"):
                group: list[dict[str, Any]] = []
                while index < len(nodes) and nodes[index].get("exampleContent"):
                    group.append(nodes[index])
                    index += 1
                self._example_group(group)
                continue
            if not self.body_title_inserted and node.get("number") == "1":
                self.body_title_inserted = True
                if self.has_cover():
                    self.doc.add_page_break()
                paragraph = self.doc.add_paragraph(style="Heading 1")
                _run_fonts(paragraph, self.title, docx=self.docx, ea=EA_HEI, bold=True)
                self.doc.add_paragraph("")
            self._node(node)
            index += 1

    def _word_heading(self, node: dict[str, Any]) -> str:
        if node.get("nodeType") == "annex":
            # SSIR 附录节点 title 形如「（资料性） 具体标题」，无“附录”字样；
            # 与 CSM 一致拼回「附录 A （资料性） 具体标题」（保留状态前缀）。
            number = str(node.get("number") or "").strip()
            title = str(node.get("title") or "").strip()
            return f"附录 {number} {title}".rstrip()
        number, title, _ = _heading_parts(node)
        return _heading_text(number, title, False).strip()

    def _heading_level(self, node: dict[str, Any]) -> int:
        number = str(node.get("number") or "").strip()
        title = str(node.get("title") or "").strip()
        if node.get("nodeType") == "annex":
            # 附录与章同级（Word 大纲顶层），附录条 A.1 降一级
            return 1 + max(number.count("."), 0)
        if not number:
            # 无编号文档块（前言/引言/参考文献等）与章同级
            return 1
        if re.fullmatch(r"\d+(?:\.\d+)*", number):
            depth = number.count(".") + 1
        elif re.fullmatch(r"[A-Z](?:\.\d+)*", number):
            depth = number.count(".") + 2
        else:
            depth = 1
        return min(max(depth, 1), 6)

    def _node(self, node: dict[str, Any]) -> None:
        heading_text = self._word_heading(node)
        if heading_text:
            level = self._heading_level(node)
            paragraph = self.doc.add_paragraph(style=f"Heading {level}")
            _run_fonts(paragraph, heading_text, self.docx, ea=EA_HEI, bold=True)
        for content in sorted(node.get("contentElements", []), key=_order):
            self._content(content)
        for child in sorted(node.get("children", []), key=_order):
            self._node(child)

    # -- 内容元素分发 ---------------------------------------------------------
    def _content(self, content: dict[str, Any]) -> None:
        kind = content.get("presentationType")
        if kind in {"paragraph", "quote", "warning", "example"}:
            text = str(content.get("textContent") or "")
            if not text.strip():
                return
            text = _footnote_superscripts(text)
            self._paragraph(text)
        elif kind == "note":
            text = str(content.get("textContent") or "")
            if not text.strip():
                return
            paragraph = self.doc.add_paragraph(style=STYLE_NOTE)
            _add_markup(paragraph, _flatten_latex(text), self.docx, asset_dir=self.asset_dir, size_pt=9)
        elif kind == "list":
            items = sorted(content.get("listItems", []), key=_order)
            for item in items:
                marker = str(item.get("marker", "-"))
                text = _flatten_latex(str(item.get("text") or ""))
                paragraph = self.doc.add_paragraph(style=STYLE_LIST)
                paragraph.paragraph_format.left_indent = self.docx["Cm"](0.85)
                paragraph.paragraph_format.first_line_indent = self.docx["Cm"](-0.85)
                _run_fonts(paragraph, f"{marker} ", self.docx, ea=EA_SONG)
                _add_markup(paragraph, text, self.docx, asset_dir=self.asset_dir)
        elif kind == "table":
            table = self.registries["tables"].get(content.get("tableRef", ""))
            if table:
                self._table(table)
        elif kind == "figure":
            self._figure_content(content)
        elif kind == "formula":
            self._formula(content)
        elif kind == "other":
            unknown = self.registries["unknownContents"].get(content.get("unknownRef", ""), {})
            paragraph = self.doc.add_paragraph(style=STYLE_CODE)
            for part_index, part in enumerate(str(unknown.get("rawContent") or "").splitlines()):
                if part_index:
                    paragraph.add_run().add_break()
                _run_fonts(paragraph, part, self.docx, ea=EA_SONG, size_pt=9)
        else:
            text = str(content.get("textContent") or "")
            if text.strip():
                self._paragraph(_footnote_superscripts(text))

    def _paragraph(self, text: str) -> None:
        docx = self.docx
        stripped = text.strip()
        if not stripped:
            return
        # 图题/表题形态段落（MinerU 偶尔抽成独立段）→ 黑体居中（同 PDF caption）
        if re.fullmatch(r"图\s*[\d.]*[^。\n]{0,60}", stripped) and not _clause_leading_number(stripped):
            paragraph = self.doc.add_paragraph(style=STYLE_FIGURE_CAPTION)
            _add_markup(paragraph, _flatten_latex(stripped), docx, asset_dir=self.asset_dir)
            return
        flush = bool(_clause_leading_number(stripped))
        style = None if not flush else None
        paragraph = self.doc.add_paragraph()
        if not flush:
            paragraph.paragraph_format.first_line_indent = docx["Pt"](21)
        paragraph.paragraph_format.alignment = docx["ALIGN"].JUSTIFY
        # 平排条号后空一字（PDF _markup 同款：5.3.1泵→5.3.1 泵）
        display = _CLAUSE_SPACE_RE.sub(lambda m: f"{m.group(1)}\u3000{m.group(2)}", stripped)
        _add_markup(paragraph, _flatten_latex(display), docx, asset_dir=self.asset_dir)

    # -- 表格 ----------------------------------------------------------------
    def _table(self, table: dict[str, Any]) -> None:
        docx = self.docx
        number = str(table.get("number") or "").strip()
        caption = str(table.get("caption") or "").strip()
        unit = str(table.get("unit") or "").strip()
        if number or caption:
            paragraph = self.doc.add_paragraph(style=STYLE_TABLE_CAPTION)
            _run_fonts(paragraph, f"表{number} {caption}".strip(), docx, ea=EA_HEI)
        if unit:
            paragraph = self.doc.add_paragraph(style=STYLE_UNIT)
            _run_fonts(paragraph, f"单位为{unit}", docx, size_pt=9)
        rows = sorted(table.get("rows", []), key=lambda row: row["rowIndex"])
        if not rows:
            return
        header_rows = sum(1 for row in rows if row.get("isHeader"))
        grid: list[list[str]] = []
        merges: list[tuple[int, int, int, int]] = []
        for row in rows:
            by_col: dict[int, str] = {}
            for cell in row.get("cells", []):
                col_index = int(cell.get("colIndex", 0))
                by_col[col_index] = str(cell.get("text") or "")
                rowspan = int(cell.get("rowspan", 1) or 1)
                colspan = int(cell.get("colspan", 1) or 1)
                if rowspan > 1 or colspan > 1:
                    merges.append((int(row.get("rowIndex", 0)), col_index, rowspan, colspan))
            width = max(by_col) + 1 if by_col else 0
            grid.append([by_col.get(col, "") for col in range(width)])
        cols = max(len(row) for row in grid)
        if cols == 0:
            return
        wtable = self.doc.add_table(rows=len(grid), cols=cols)
        try:
            wtable.style = self.doc.styles["Table Grid"]
        except KeyError:
            pass
        _table_borders(wtable, docx)
        for row_index, row in enumerate(grid):
            for col_index in range(cols):
                text = row[col_index] if col_index < len(row) else ""
                self._write_cell(wtable.cell(row_index, col_index), text)
        self._merge_cells(wtable, merges, grid)
        if header_rows:
            _repeat_header_rows(wtable, header_rows, docx)

    def _write_cell(self, cell: Any, text: str) -> None:
        """单元格文本：脚注标记/平拍指数 → 上标；<br> → 分段/换行；注行居左。"""
        docx = self.docx
        # 表注行（注1：…）→ 每条注独立段、居左、首行空两格（GBT-B09 例外）
        stripped_images = _IMG_MD_RE.sub("", text).strip()
        if _TABLE_NOTE_CELL_RE.match(stripped_images):
            for part_index, part in enumerate(_split_table_note_parts(text)):
                paragraph = cell.paragraphs[0] if part_index == 0 and not cell.paragraphs[0].runs else cell.add_paragraph()
                paragraph.style = self.doc.styles[STYLE_TABLE_NOTE]
                paragraph.paragraph_format.first_line_indent = docx["Pt"](18)
                paragraph.paragraph_format.alignment = docx["ALIGN"].LEFT
                self._write_cell_rich(paragraph, part)
            return
        paragraph = cell.paragraphs[0]
        paragraph.style = self.doc.styles[STYLE_TABLE_TEXT]
        paragraph.paragraph_format.alignment = docx["ALIGN"].CENTER
        paragraph.paragraph_format.space_after = docx["Pt"](0)
        self._write_cell_rich(paragraph, text)

    def _write_cell_rich(self, paragraph: Any, text: str) -> None:
        """单元格富文本：<br>/BR 哨兵分段、图片、上标修复、行内公式。"""
        fixed = _table_cell_superscripts(text)
        parts = re.split(r"<br>|\x00BR\x00", fixed)
        for part_index, part in enumerate(parts):
            if part_index > 0:
                paragraph.add_run().add_break()
            self._cell_markup(paragraph, part)

    def _cell_markup(self, paragraph: Any, text: str) -> None:
        """单元格内分段处理：图片拆分 + 行内标记。"""
        docx = self.docx
        position = 0
        for match in _IMG_MD_RE.finditer(text):
            if match.start() > position:
                _add_markup(paragraph, text[position:match.start()], docx,
                            asset_dir=self.asset_dir, size_pt=9)
            image_path = _resolve_asset(self.asset_dir, match.group(2)) if self.asset_dir else Path(match.group(2))
            if image_path.is_file():
                _add_picture(paragraph, image_path, docx, max_width_cm=4.0)
            position = match.end()
        tail = text[position:]
        if tail.strip() or position == 0:
            _add_markup(paragraph, tail, docx, asset_dir=self.asset_dir, size_pt=9)

    def _merge_cells(self, table: Any, merges: list[tuple[int, int, int, int]],
                     grid: list[list[str]]) -> None:
        rows, cols = len(grid), max(len(row) for row in grid)
        for row, col, rowspan, colspan in merges:
            if rowspan <= 1 and colspan <= 1:
                continue
            if row < 0 or col < 0 or row >= rows or col >= cols:
                self.warnings.append(f"Table merge out of range skipped: row={row} col={col}")
                continue
            origin = table.cell(row, col)
            target = table.cell(min(row + rowspan - 1, rows - 1), min(col + colspan - 1, cols - 1))
            merged = origin.merge(target)
            _merge_cleanup(merged, self.docx)

    # -- 图/公式/示例 ---------------------------------------------------------
    def _figure_content(self, content: dict[str, Any]) -> None:
        figure = self.registries["figures"].get(content.get("figureRef", ""), {})
        asset = figure.get("assetRef")
        number = str(figure.get("number") or "")
        caption = str(figure.get("caption") or "")
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = self.docx["ALIGN"].CENTER
        image_path = _resolve_asset(self.asset_dir, asset) if asset else Path("")
        if asset and image_path.is_file():
            _add_picture(paragraph, image_path, self.docx)
        else:
            self.warnings.append(f"Missing figure asset retained as placeholder: {figure.get('id', '?')}")
            _run_fonts(paragraph, "[图像资产缺失]", self.docx, ea=EA_HEI)
        caption_text = f"图{number} {caption}".strip() if (number or caption) else ""
        if caption_text:
            caption_paragraph = self.doc.add_paragraph(style=STYLE_FIGURE_CAPTION)
            _run_fonts(caption_paragraph, caption_text, self.docx, ea=EA_HEI)

    def _formula(self, content: dict[str, Any]) -> None:
        formula = self.registries["formulas"].get(content.get("formulaRef", ""), {})
        asset = formula.get("assetRef")
        image_path = _resolve_asset(self.asset_dir, asset) if asset else Path("")
        paragraph = self.doc.add_paragraph()
        paragraph.alignment = self.docx["ALIGN"].CENTER
        if asset and image_path.is_file():
            _add_picture(paragraph, image_path, self.docx)
        else:
            raw = formula.get("latex") or formula.get("rawText") or ""
            if str(raw).strip():
                _add_markup(paragraph, _latex_to_text(str(raw)), self.docx, asset_dir=self.asset_dir)
                self.warnings.append(f"Formula typeset as text: {formula.get('id', '?')}")
        if formula.get("number"):
            number_paragraph = self.doc.add_paragraph(style=STYLE_TABLE_CAPTION)
            _run_fonts(number_paragraph, str(formula["number"]), self.docx, ea=EA_HEI)

    def _example_group(self, nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            title = str(node.get("title") or "").strip()
            if title.startswith("示例"):
                paragraph = self.doc.add_paragraph(style=STYLE_EXAMPLE_TITLE)
                _run_fonts(paragraph, title, self.docx, ea=EA_HEI, bold=True)
                continue
            self._example_node(node)

    def _example_node(self, node: dict[str, Any]) -> None:
        heading_text = self._word_heading(node)
        if heading_text:
            paragraph = self.doc.add_paragraph(style=STYLE_EXAMPLE_TITLE)
            _run_fonts(paragraph, heading_text, self.docx, ea=EA_HEI, bold=True)
        for content in sorted(node.get("contentElements", []), key=_order):
            self._example_content(content)
        for child in sorted(node.get("children", []), key=_order):
            self._example_node(child)

    def _example_content(self, content: dict[str, Any]) -> None:
        kind = content.get("presentationType")
        if kind in {"paragraph", "note", "quote", "warning", "example"}:
            text = str(content.get("textContent") or "")
            paragraph = self.doc.add_paragraph(style=STYLE_EXAMPLE)
            _add_markup(paragraph, _flatten_latex(_footnote_superscripts(text)), self.docx,
                        asset_dir=self.asset_dir)
        elif kind == "list":
            for item in sorted(content.get("listItems", []), key=_order):
                paragraph = self.doc.add_paragraph(style=STYLE_EXAMPLE)
                paragraph.paragraph_format.left_indent = self.docx["Cm"](0.85)
                paragraph.paragraph_format.first_line_indent = self.docx["Cm"](-0.85)
                marker = str(item.get("marker", "-"))
                _run_fonts(paragraph, f"{marker} ", self.docx, ea=EA_SONG)
                _add_markup(paragraph, _flatten_latex(str(item.get("text") or "")), self.docx,
                            asset_dir=self.asset_dir)
        elif kind == "table":
            table = self.registries["tables"].get(content.get("tableRef", ""))
            if table:
                self._table(table)
        elif kind == "figure":
            self._figure_content(content)
        elif kind == "formula":
            self._formula(content)
        else:
            text = str(content.get("textContent") or "")
            if text.strip():
                paragraph = self.doc.add_paragraph(style=STYLE_EXAMPLE)
                _add_markup(paragraph, text, self.docx, asset_dir=self.asset_dir)

    # -- 导出 ----------------------------------------------------------------
    def save(self, output: str | Path) -> None:
        self._core()
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(str(target))

    def render(self, output: str | Path) -> list[str]:
        if self.has_cover():
            self.render_cover()
        else:
            paragraph = self.doc.add_paragraph(style="Heading 1")
            _run_fonts(paragraph, self.title, self.docx, ea=EA_HEI, bold=True)
        if self.has_toc():
            self.render_toc()
        self.render_body()
        self.save(output)
        return self.warnings


# --------------------------------------------------------------------------
# 公共入口
# --------------------------------------------------------------------------

def render_ssir_docx(document: dict[str, Any], output: str | Path, *,
                     input_file: str | Path = "", toc_depth: int | None = 2) -> list[str]:
    """渲染 validated SSIR JSON 为 .docx（doc_1，与 render.pdf 同源等价）。

    - ``input_file``：SSIR 输入文件路径，用于把相对 assetRef（assets/images/…）
      解析到正确目录（同 pdf_renderer 向上查找语义）；
    - ``toc_depth``：目次最大条目层级（默认 2；None=全部）。
    返回渲染 warnings（缺失资产、公式降级文本等）。
    """
    validate_ssir(document)
    builder = _DocxBuilder(document, input_file=input_file, toc_depth=toc_depth)
    return builder.render(output)


def render_docx_file(input_path: str | Path, output: str | Path, *,
                     toc_depth: int | None = 2) -> list[str]:
    """从 SSIR JSON 文件渲染 .docx（CLI `ssir pdf render --docx-output` 后端）。"""
    source = Path(input_path)
    document = json.loads(source.read_text(encoding="utf-8"))
    return render_ssir_docx(document, output, input_file=str(source), toc_depth=toc_depth)
