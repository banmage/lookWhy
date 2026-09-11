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
GBT-X01/B06（图与图题）、GBT-X06（公式另行编排）、GBT-B11（示例框）、
GBT-B10/B11（注/示例标记黑体、内容宋体——`_add_label_markup`，与 PDF 侧
`_label_markup` 同规则）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .pdf_renderer import (
    _TABLE_NOTE_CELL_RE,
    _cell_text_natural_width,
    _clause_leading_number,
    _footnote_superscripts,
    _heading_parts,
    _heading_text,
    _is_toc_node,
    _latex_to_text,
    _list_is_sub_level,
    _list_marker,
    _note_example_label_span,
    _order,
    _protect_literal_stars,
    _resolve_asset,
    _restore_literal_stars,
    _split_table_note_parts,
    _table_cell_superscripts,
    _toc_indent_level,
    _toc_caption_rows,
    _toc_label,
    _toc_nodes,
    _term_entry_text,
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
STYLE_NOTE = "SSIR Note"                       # 注：…（标记黑体、内容小五宋体）
STYLE_LIST = "SSIR List Item"                  # 列项（原样 marker + 悬挂缩进）
# 列项版式（GB/T 1.1-2020 10.2.2，与 pdf_renderer 的 list/list-sub 同一汉字位）：
# 第一层次 marker 空两个汉字起排、文字与回行同置版心左边第五个汉字位（缩进 4 汉字）；
# 第二层次 marker 空四个汉字、文字置第七个汉字位（缩进 6 汉字）。列项细分不超过
# 两个层次，故只需两级。1 汉字 = 正文字号（10.5pt）——Word 里 210 twips。
_LIST_TEXT_HAN = {False: 4, True: 6}           # 层次 → 文字列（汉字位）
_LIST_MARKER_HAN = 2                           # marker 距上一层次文字列 = 2 汉字
HAN_PT = 10.5                                  # 正文字号 = 一汉字宽（pt）
STYLE_CODE = "SSIR Code"                       # 未知内容（等宽灰底）
STYLE_FORMULA = "SSIR Formula"                 # 公式（居中）
STYLE_TOC = "SSIR TOC"                         # 目次条目
STYLE_EXAMPLE = "SSIR Example"                 # 示例框内容（浅灰底）
STYLE_EXAMPLE_TITLE = "SSIR Example Title"     # 「示例N：」黑体居中
STYLE_TABLE_TEXT = "SSIR Table Text"           # 表内文字（小五）
STYLE_TABLE_NOTE = "SSIR Table Note"           # 表注行（居左首行空两格）
# 术语条目（GB/T 1.1-2020 8.7.3.1、10.3.5、附录F 表F.1 序号22/23）：条目编号单独
# 占一行顶格、术语与英文对应词另起一行空两个汉字，均五号黑体、上下无空行。
STYLE_TERM_NUMBER = "SSIR Term Number"         # 条目编号行（黑体五号顶格）
STYLE_TERM_TITLE = "SSIR Term Title"           # 术语 + 英文对应词行（黑体五号，空两个汉字）

_SUP_OPEN, _SUP_CLOSE = "\x00SUP\x00", "\x00/SUP\x00"
_SUB_OPEN, _SUB_CLOSE = "\x00SUB\x00", "\x00/SUB\x00"
_BR_SENTINEL = "\x00BR\x00"
_LATEX_INLINE_RE = re.compile(r"\$([^$\n]+)\$")
_IMG_MD_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)\)")
# PDF _markup 同款：平排条号前空一字距（Word 正文段显示贴近）
_CLAUSE_SPACE_RE = re.compile(
    r"(?m)^((?:\d+\.){1,3}\d+|[A-Z]\.\d+(?:\.\d+)*)[ \u3000]*([\u4e00-\u9fff（(])"
)

# 版心宽（cm）：A4 21cm − 左右页边距各 2.5cm（见 _setup_page）。
CONTENT_WIDTH_CM = 16.0
# 公式变量解释项头部（行内 LaTeX 或 1—4 位半角/希腊字母，可带下标）+ 破折号：
# 「变量——解释」固定形态（GBT-X06；CSM-OCR-018），渲染时补四分之一汉字字隙。
FORMULA_ITEM_HEAD_RE = re.compile(
    r"(?m)^(\$[^$\n]+\$|[\u0370-\u03ffA-Za-z][\u0370-\u03ffA-Za-z0-9]{0,3}"
    r"(?:[ \u3000]*[_^][ \u3000]*\{[^{}\n]{1,12}\})?)[ \u3000]*(—+)(?=[\u4e00-\u9fff])"
)


def _docx_ns() -> dict[str, Any]:
    try:
        from docx import Document  # noqa: F401
        from docx.enum.style import WD_STYLE_TYPE
        from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
        from docx.shared import Cm, Pt, RGBColor
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(DOCX_DEPENDENCY_HINT) from exc
    return {
        "Document": Document,
        "WD_STYLE_TYPE": WD_STYLE_TYPE,
        "ALIGN": WD_ALIGN_PARAGRAPH,
        "TAB_ALIGN": WD_TAB_ALIGNMENT,
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


def _list_marker_run(paragraph: Any, marker: str, docx: dict[str, Any], tab_pt: float) -> None:
    """写列项 marker，并用制表符把文字定位到回行位置（GB/T 1.1 10.2.2 / GBT-B04）。

    ``tab_pt`` = 文字列相对版心左的 pt（第一层次 4 汉字、第二层次 6 汉字），与段落
    ``left_indent`` 同值，故首行文字与回行同位。用制表符 + 显式制表位而不是空格：
    空格会被两端对齐拉伸（Word 与 PDF 侧 reportlab 同理，同一分组里只要有一个可按
    字间距调整的空格，整行空格一起变宽），marker 之后的空隙因此忽宽忽窄；制表符跳到
    固定位置，与对齐方式无关（PDF 侧对应 pdf_renderer._list_marker_gap 的固定字隙）。
    """
    tab_stops = paragraph.paragraph_format.tab_stops
    if not len(tab_stops):
        tab_stops.add_tab_stop(docx["Pt"](tab_pt))
    if marker in ("●", "○", "•"):
        # 圆点列项符号缩小呈现（0.62×，与 PDF 渲染同裁定 2026-09-07）
        _run_fonts(paragraph, marker, docx, ea=EA_SONG, size_pt=7)
    else:
        _run_fonts(paragraph, marker, docx, ea=EA_SONG)
    paragraph.add_run().add_tab()


def _list_indent(paragraph: Any, marker: str, docx: dict[str, Any], *, sub_level: bool) -> None:
    """列项悬挂缩进 + marker 制表位（GB/T 1.1-2020 10.2.2）。

    第一层次：marker 空 2 汉字起排、文字列（含回行）4 汉字；第二层次：marker 空 4 汉字
    起排、文字列 6 汉字。缩进随层次变化——此前两级共用固定 0.85cm，第二层次因此既没
    有 4 汉字 marker 位、文字也停在第 2.3 个汉字位（2026-09-11 用户报列项版式问题）。
    """
    text_pt = _LIST_TEXT_HAN[bool(sub_level)] * HAN_PT
    paragraph.paragraph_format.left_indent = docx["Pt"](text_pt)
    paragraph.paragraph_format.first_line_indent = docx["Pt"](-_LIST_MARKER_HAN * HAN_PT)
    _list_marker_run(paragraph, marker, docx, text_pt)


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


def _cm_from_px(path: Path) -> tuple[float, float]:
    """图片固有尺寸（cm，96dpi 换算，与 _picture_size 同规但不设上限）。"""
    try:
        from PIL import Image

        with Image.open(path) as image:
            width_px, height_px = image.size
    except Exception:
        return 8.0, 6.0
    if width_px <= 0 or height_px <= 0:
        return 8.0, 6.0
    return width_px * 2.54 / 96.0, height_px * 2.54 / 96.0


def _em_text_width(text: str, size_pt: float) -> float:
    """docx 侧文本宽度估算（cm）：汉字/全角（含「…」「——」）1em，半角 0.5em。

    只用于公式引导线的取整估算——Word 自身的断行/定位不在这里复刻。
    """
    em_cm = size_pt * 2.54 / 72.0
    return sum(0.5 if ord(char) < 0x2E80 else 1.0 for char in str(text)) * em_cm


def _formula_item_spacing(text: str) -> str:
    """公式变量解释项：变量与破折号之间、破折号与解释之间各空四分之一汉字。

    规则对应: GBT-X06（GB/T 1.1-2020 9.9.3、10.4.3；CSM-OCR-018 归一后的固定
    形态「变量——解释」）。与 PDF 渲染同规：PDF 用固定字隙哨兵（不被两端对齐
    拉伸），Word 侧用半角空格——Times New Roman 的空格推进宽度正是 0.25em。
    """
    return FORMULA_ITEM_HEAD_RE.sub(lambda m: f"{m.group(1)} {m.group(2)} ", str(text))


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


def _add_label_markup(paragraph: Any, text: str, docx: dict[str, Any], *,
                      asset_dir: Path | None = None, ea: str = EA_SONG,
                      size_pt: float | None = None) -> None:
    """行首注/示例标记黑体、其余照常（GB/T 1.1-2020 10.4.4.1、10.4.5、附录 F 表 F.1
    序号 42/44；GBT-B10/GBT-B11 执行侧，2026-09-11）。

    与 PDF 侧 ``pdf_renderer._label_markup`` 同一规则：标记（"注："/"注1："/"示例："
    /"示例1："）用黑体，内容用宋体；"示例1示出了…"这类无冒号的行内引用不是标记。
    """
    lead, label, rest = _note_example_label_span(text)
    if not label:
        _add_markup(paragraph, text, docx, asset_dir=asset_dir, ea=ea, size_pt=size_pt)
        return
    # 标记前导空白不进黑体区（"…<br> 注1：…" 的空格是 OCR 噪声，非标记的一部分）。
    if lead:
        _run_fonts(paragraph, lead, docx, ea=ea, size_pt=size_pt)
    _run_fonts(paragraph, label, docx, ea=EA_HEI, bold=True, size_pt=size_pt)
    _add_markup(paragraph, rest, docx, asset_dir=asset_dir, ea=ea, size_pt=size_pt)


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
        self._box: dict[str, Any] | None = None  # ssir:box 显式框（docx 侧活动容器，2026-09-08）
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
        table_note = custom(STYLE_TABLE_NOTE, size=9.0, align=align.LEFT, first_indent_pt=18.0, space_after=0)
        # 术语条目两行（10.3.5）：编号行顶格、术语行空两个汉字，均五号黑体、上下无空行。
        custom(STYLE_TERM_NUMBER, ea=EA_HEI, align=align.LEFT, space_after=0)
        custom(STYLE_TERM_TITLE, ea=EA_HEI, align=align.LEFT,
               indent_cm=2 * HAN_PT / 72 * 2.54, space_after=0)
        # 2026-09-07 用户裁定：表内文字行距适度放宽（PDF leading 15pt/9pt 字 ≈ 1.67×，
        # docx 用 1.5 倍行距近似，双胞胎一致观感）。
        cell.paragraph_format.line_spacing = 1.5
        table_note.paragraph_format.line_spacing = 1.5
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
        # 图/表行（GB/T 1.1-2020 8.2.2 i)/j)）：接在条/附录/参考文献/索引之后，顶格，
        # 与前面内容之间空一行（10.3.2）。
        for group in _toc_caption_rows(self._root_nodes(), self.registries):
            if not group:
                continue
            self.doc.add_paragraph(style=STYLE_TOC)
            for label, _reference in group:
                paragraph = self.doc.add_paragraph(style=STYLE_TOC)
                _run_fonts(paragraph, label, docx, ea=EA_SONG)
        # 目次块内非行内容（目录页装饰图等）保留
        toc_node = next((node for node in self._root_nodes() if _is_toc_node(node)), None)
        if toc_node:
            for content in sorted(toc_node.get("contentElements", []), key=_order):
                if content.get("presentationType") == "figure":
                    self._figure_content(content)
        self.doc.add_page_break()

    # -- 正文 ----------------------------------------------------------------
    def _has_boxes(self) -> bool:
        """文档是否存在 ssir:box 显式声明（2026-09-08）：有则框决策走显式流式分组。"""
        def visit(nodes: list[dict[str, Any]]) -> bool:
            for node in nodes:
                if "box" in node:
                    return True
                if any("box" in c for c in node.get("contentElements", []) or []):
                    return True
                if visit(node.get("children", []) or []):
                    return True
            return False
        return visit(self._root_nodes())

    def _box_cell(self, box: int | None, box_style: str | None = None) -> None:
        """显式框开合（docx 侧，2026-09-08）：1×1 外框表承载框内流；
        无标记文档不受影响。frame=黑细边框；shaded=浅灰底。"""
        if box is None:
            self._box = None
            return
        if self._box is not None and self._box.get("id") == box:
            return
        self._box = None  # 关闭上一框（关旧再开新 = 相邻两框）
        outer = self.doc.add_table(rows=1, cols=1)
        cell = outer.cell(0, 0)
        mode = box_style if box_style in ("frame", "shaded") else "frame"
        if mode == "shaded":
            tc_pr = cell._tc.get_or_add_tcPr()
            shd = tc_pr.makeelement(self.docx["qn"]("w:shd"), {
                self.docx["qn"]("w:val"): "clear",
                self.docx["qn"]("w:color"): "auto",
                self.docx["qn"]("w:fill"): "F2F2F2",
            })
            tc_pr.append(shd)
        else:
            _table_borders(outer, self.docx)
        self._box = {"id": box, "cell": cell, "para_used": False}

    def _container_paragraph(self, style: str | None = None) -> Any:
        """正文段落槽：显式框内写入框单元格（首个段落复用单元格默认空段），
        框外直接写文档体。"""
        if self._box is None:
            return self.doc.add_paragraph(style=style) if style else self.doc.add_paragraph()
        cell = self._box["cell"]
        if not self._box["para_used"]:
            self._box["para_used"] = True
            paragraph = cell.paragraphs[0]
            if style:
                paragraph.style = self.doc.styles[style]
            return paragraph
        return cell.add_paragraph(style=style) if style else cell.add_paragraph()

    def _container_table(self, rows: int, cols: int) -> Any:
        if self._box is None:
            return self.doc.add_table(rows=rows, cols=cols)
        return self._box["cell"].add_table(rows=rows, cols=cols)

    def render_body(self) -> None:
        nodes = self._root_nodes()
        if self._has_boxes():
            self._marked_body(nodes)
            return
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

    def _marked_body(self, nodes: list[dict[str, Any]]) -> None:
        """ssir:box 显式模式的根级发射（2026-09-08）：示例启发式连续打包停用，
        框归属完全来自标记（节点/内容元素均可中途开合）。"""
        self._box = None
        index = 0
        while index < len(nodes):
            node = nodes[index]
            if _is_toc_node(node):
                index += 1
                continue
            if not self.body_title_inserted and node.get("number") == "1":
                self.body_title_inserted = True
                if self.has_cover():
                    self.doc.add_page_break()
                paragraph = self.doc.add_paragraph(style="Heading 1")
                _run_fonts(paragraph, self.title, docx=self.docx, ea=EA_HEI, bold=True)
                self.doc.add_paragraph("")
            # 「示例N：」框外题注：不进框（黑体），其后子内容/正文照常渲染。
            title = str(node.get("title") or "").strip()
            if node.get("exampleContent") and not node.get("box") and re.match(r"^示例\s*\d*\s*[:：]\s*$", title):
                paragraph = self.doc.add_paragraph()
                _run_fonts(paragraph, title, self.docx, ea=EA_HEI, bold=True)
                index += 1
                for child in node.get("children", []) or []:
                    self._marked_node(child)
                for content in sorted(node.get("contentElements", []) or [], key=_order):
                    self._marked_content(content)
                continue
            self._marked_node(node)
            index += 1

    def _marked_node(self, node: dict[str, Any]) -> None:
        """显式模式的节点发射：标题（单元）→ 内容元素（逐单元）→ 子节点，单元按 box 进出框。

        示例内容（exampleContent）标题沿用 PDF 的示例排版语义（框内首个无编号
        标题黑体居中、编号标题黑体顶格），不套 Word Heading 字号，保持附录示例
        观感与旧 docx 一致；非示例节点照常使用 Heading 层级。
        """
        self._box_cell(node.get("box"), node.get("boxStyle"))
        if node.get("exampleContent"):
            heading_text = self._word_heading(node)
            if heading_text:
                paragraph = self._container_paragraph()
                paragraph.paragraph_format.alignment = self.docx["ALIGN"].CENTER if not node.get("number") else self.docx["ALIGN"].LEFT
                _run_fonts(paragraph, heading_text, self.docx, ea=EA_HEI, bold=True, size_pt=12)
        elif not self._term_entry(node):
            heading_text = self._word_heading(node)
            if heading_text:
                level = self._heading_level(node)
                paragraph = self._container_paragraph(style=f"Heading {level}")
                _run_fonts(paragraph, heading_text, self.docx, ea=EA_HEI, bold=True)
        for content in sorted(node.get("contentElements", []), key=_order):
            self._marked_content(content)
        for child in sorted(node.get("children", []), key=_order):
            self._marked_node(child)

    def _marked_content(self, content: dict[str, Any]) -> None:
        self._box_cell(content.get("box"), content.get("boxStyle"))
        self._content(content)

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

    def _term_entry(self, node: dict[str, Any]) -> bool:
        """术语条目两行版式（GB/T 1.1-2020 10.3.5）：编号行 + 术语行。

        不是术语条目（`_term_entry_text` 返回 None）时不写任何段落并返回 False，
        调用方照常走标题路径。
        """
        number, title, _ = _heading_parts(node)
        term = _term_entry_text(node, number, title)
        if term is None:
            return False
        number_paragraph = self._container_paragraph(style=STYLE_TERM_NUMBER)
        _run_fonts(number_paragraph, number, self.docx, ea=EA_HEI, bold=True)
        term_paragraph = self._container_paragraph(style=STYLE_TERM_TITLE)
        _run_fonts(term_paragraph, _flatten_latex(term), self.docx, ea=EA_HEI, bold=True)
        return True

    def _node(self, node: dict[str, Any]) -> None:
        if not self._term_entry(node):
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
        if kind in {"paragraph", "quote", "warning", "example", "footnote"}:
            text = str(content.get("textContent") or "")
            if not text.strip():
                return
            text = _footnote_superscripts(text)
            self._paragraph(text)
        elif kind == "note":
            text = str(content.get("textContent") or "")
            if not text.strip():
                return
            paragraph = self._container_paragraph(style=STYLE_NOTE)
            # 注标记黑体、注内容小五号宋体（GBT-B10；附录F 表F.1 序号44/45）。
            _add_label_markup(paragraph, _flatten_latex(text), self.docx, asset_dir=self.asset_dir, size_pt=9)
        elif kind == "list":
            items = sorted(content.get("listItems", []), key=_order)
            markers = [_list_marker(str(item.get("marker", "-"))) for item in items]
            uniform_bullets = bool(markers) and all(m in ("●", "○", "•") for m in markers)
            for item, marker in zip(items, markers):
                text = _flatten_latex(str(item.get("text") or ""))
                paragraph = self._container_paragraph(style=STYLE_LIST)
                _list_indent(paragraph, marker, self.docx,
                             sub_level=_list_is_sub_level(marker, uniform_bullets))
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
            paragraph = self._container_paragraph(style=STYLE_CODE)
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
            paragraph = self._container_paragraph(style=STYLE_FIGURE_CAPTION)
            _add_markup(paragraph, _flatten_latex(stripped), docx, asset_dir=self.asset_dir)
            return
        flush = bool(_clause_leading_number(stripped))
        style = None if not flush else None
        paragraph = self._container_paragraph()
        if not flush:
            paragraph.paragraph_format.first_line_indent = docx["Pt"](21)
        paragraph.paragraph_format.alignment = docx["ALIGN"].JUSTIFY
        # 平排条号后空一字（PDF _markup 同款：5.3.1泵→5.3.1 泵）
        display = _CLAUSE_SPACE_RE.sub(lambda m: f"{m.group(1)}\u3000{m.group(2)}", stripped)
        # 公式变量解释项：变量与破折号、破折号与解释之间各空四分之一汉字（GBT-X06）。
        display = _formula_item_spacing(display)
        # 注/示例标记黑体、内容宋体（GBT-B10/B11；附录F 序号42—45）：正文里以
        # "示例1：…"/"注2：…"起始的段落与注块、示例块同规则。
        _add_label_markup(paragraph, _flatten_latex(display), docx, asset_dir=self.asset_dir)

    # -- 表格 ----------------------------------------------------------------
    def _table(self, table: dict[str, Any]) -> None:
        docx = self.docx
        number = str(table.get("number") or "").strip()
        caption = str(table.get("caption") or "").strip()
        unit = str(table.get("unit") or "").strip()
        if number or caption:
            paragraph = self._container_paragraph(style=STYLE_TABLE_CAPTION)
            _run_fonts(paragraph, f"表{number} {caption}".strip(), docx, ea=EA_HEI)
        if unit:
            paragraph = self._container_paragraph(style=STYLE_UNIT)
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
        wtable = self._container_table(rows=len(grid), cols=cols)
        try:
            wtable.style = self.doc.styles["Table Grid"]
        except KeyError:
            pass
        _table_borders(wtable, docx)
        for row_index, row in enumerate(grid):
            for col_index in range(cols):
                text = row[col_index] if col_index < len(row) else ""
                self._write_cell(wtable.cell(row_index, col_index), text, is_header=row_index < header_rows)
        self._merge_cells(wtable, merges, grid)
        if header_rows:
            _repeat_header_rows(wtable, header_rows, docx)

    def _write_cell(self, cell: Any, text: str, is_header: bool = False) -> None:
        """单元格文本：脚注标记/平拍指数 → 上标；<br> → 分段/换行；表头居中、
        数据行居左、注行居左首行缩进（2026-09-07 用户裁定）。"""
        docx = self.docx
        # 表注行（注1：…）→ 每条注独立段、居左、首行空两格（GBT-B09 例外）；
        # 续行悬挂缩进到「注N：」冒号后文字对齐（2026-09-07 用户裁定）。
        stripped_images = _IMG_MD_RE.sub("", text).strip()
        if _TABLE_NOTE_CELL_RE.match(stripped_images):
            for part_index, part in enumerate(_split_table_note_parts(text)):
                paragraph = cell.paragraphs[0] if part_index == 0 and not cell.paragraphs[0].runs else cell.add_paragraph()
                paragraph.style = self.doc.styles[STYLE_TABLE_NOTE]
                paragraph.paragraph_format.alignment = docx["ALIGN"].LEFT
                paragraph.paragraph_format.left_indent = docx["Pt"](0)
                prefix = re.match(r"^(注\s*\d*\s*[:：])", part)
                if prefix:
                    label_width = _cell_text_natural_width(prefix.group(1), 9.0)
                    paragraph.paragraph_format.left_indent = docx["Pt"](18.0 + label_width)
                    paragraph.paragraph_format.first_line_indent = docx["Pt"](-label_width)
                self._write_cell_rich(paragraph, part)
            return
        paragraph = cell.paragraphs[0]
        paragraph.style = self.doc.styles[STYLE_TABLE_TEXT]
        paragraph.paragraph_format.alignment = docx["ALIGN"].CENTER if is_header else docx["ALIGN"].LEFT
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
        """单元格内分段处理：图片拆分 + 行内标记 + 行首注/示例标记黑体。"""
        docx = self.docx
        position = 0
        for match in _IMG_MD_RE.finditer(text):
            if match.start() > position:
                _add_label_markup(paragraph, text[position:match.start()], docx,
                                  asset_dir=self.asset_dir, size_pt=9)
            image_path = _resolve_asset(self.asset_dir, match.group(2)) if self.asset_dir else Path(match.group(2))
            if image_path.is_file():
                _add_picture(paragraph, image_path, docx, max_width_cm=4.0)
            position = match.end()
        tail = text[position:]
        if tail.strip() or position == 0:
            # 表内注标记黑体、注内容小五号宋体（GBT-B10；附录F 表F.1 序号44/45）。
            _add_label_markup(paragraph, tail, docx, asset_dir=self.asset_dir, size_pt=9)

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
        paragraph = self._container_paragraph()
        paragraph.alignment = self.docx["ALIGN"].CENTER
        image_path = _resolve_asset(self.asset_dir, asset) if asset else Path("")
        if asset and image_path.is_file():
            _add_picture(paragraph, image_path, self.docx)
        else:
            self.warnings.append(f"Missing figure asset retained as placeholder: {figure.get('id', '?')}")
            _run_fonts(paragraph, "[图像资产缺失]", self.docx, ea=EA_HEI)
        caption_text = f"图{number} {caption}".strip() if (number or caption) else ""
        if caption_text:
            caption_paragraph = self._container_paragraph(style=STYLE_FIGURE_CAPTION)
            _run_fonts(caption_paragraph, caption_text, self.docx, ea=EA_HEI)

    def _formula(self, content: dict[str, Any]) -> None:
        formula = self.registries["formulas"].get(content.get("formulaRef", ""), {})
        number_label = str(formula.get("number") or "").strip()
        asset = formula.get("assetRef")
        image_path = _resolve_asset(self.asset_dir, asset) if asset else Path("")
        has_image = bool(asset and image_path.is_file())
        raw = formula.get("latex") or formula.get("rawText") or ""
        text_formula = _latex_to_text(str(raw)) if str(raw).strip() else ""
        if number_label:
            # 规则对应: GBT-X06（公式编号右端对齐、与公式之间以“……”连接）。
            self._formula_number_line(
                image_path if has_image else None, text_formula, f"({number_label})"
            )
            if not has_image:
                self.warnings.append(f"Formula typeset as text: {formula.get('id', '?')}")
            return
        paragraph = self._container_paragraph()
        paragraph.alignment = self.docx["ALIGN"].CENTER
        if has_image:
            _add_picture(paragraph, image_path, self.docx)
        else:
            if text_formula.strip():
                _add_markup(paragraph, text_formula, self.docx, asset_dir=self.asset_dir)
                self.warnings.append(f"Formula typeset as text: {formula.get('id', '?')}")

    def _formula_number_line(self, image_path: Path | None, formula_text: str, number: str) -> None:
        """公式行（GBT-X06；GB/T 1.1-2020 10.4.3）：公式另行居中，编号右端对齐，
        公式与编号之间由「……」连接，公式与省略号之间留两个汉字间隔（与 PDF
        渲染同规，Word 侧用制表位实现）。

        居中制表位按「公式 + 两个汉字间隔 + 引导线」整段居中补偿（Word 的居中
        制表位把制表位后的内容整体居中于刻度处）；编号用右端制表位贴版心右缘。
        省略号个数按版心宽度计算（与 PDF 同一几何：公式居中后左右各
        (版心−公式)/2），公式图超宽时先收到「留够引导线」的宽度（只缩小不放大）。
        """
        docx = self.docx
        size_pt = 10.5
        em_cm = size_pt * 2.54 / 72.0
        number_w = _em_text_width(number, size_pt)
        gap_cm = 2 * em_cm
        min_leader_cm = 4 * em_cm
        limit_cm = CONTENT_WIDTH_CM - 2 * (gap_cm + number_w + min_leader_cm)
        if image_path is not None:
            width_cm, height_cm = _cm_from_px(image_path)
            if width_cm > limit_cm > 0:
                height_cm *= limit_cm / width_cm
                width_cm = limit_cm
        else:
            width_cm = min(_em_text_width(formula_text, size_pt), max(limit_cm, 0.0))
            height_cm = 0.0
        leader_cm = CONTENT_WIDTH_CM / 2 - number_w - gap_cm - width_cm / 2
        dot_cm = em_cm
        dots = "…" * max(0, int(leader_cm / dot_cm + 1e-9))
        paragraph = self._container_paragraph(style=STYLE_FORMULA)
        stops = paragraph.paragraph_format.tab_stops
        center_stop_cm = CONTENT_WIDTH_CM / 2 + (gap_cm + len(dots) * dot_cm) / 2
        stops.add_tab_stop(docx["Pt"](center_stop_cm * 72 / 2.54), docx["TAB_ALIGN"].CENTER)
        stops.add_tab_stop(docx["Pt"](CONTENT_WIDTH_CM * 72 / 2.54), docx["TAB_ALIGN"].RIGHT)
        paragraph.add_run().add_tab()
        if image_path is not None:
            paragraph.add_run().add_picture(
                str(image_path), width=docx["Cm"](width_cm), height=docx["Cm"](height_cm)
            )
        else:
            _run_fonts(paragraph, formula_text, docx, size_pt=size_pt)
        _run_fonts(paragraph, "　　" + dots, docx, size_pt=size_pt)
        paragraph.add_run().add_tab()
        _run_fonts(paragraph, number, docx, size_pt=size_pt)

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
            items = sorted(content.get("listItems", []), key=_order)
            markers = [_list_marker(str(item.get("marker", "-"))) for item in items]
            uniform_bullets = bool(markers) and all(m in ("●", "○", "•") for m in markers)
            for item, marker in zip(items, markers):
                paragraph = self.doc.add_paragraph(style=STYLE_EXAMPLE)
                _list_indent(paragraph, marker, self.docx,
                             sub_level=_list_is_sub_level(marker, uniform_bullets))
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
