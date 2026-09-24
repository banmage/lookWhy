"""SSIR → 独立 HTML 投影（``04_render/<ID>.render.html``，C 方案 2026-09-23 用户裁定）。

**定位**：``render.pdf`` 是版式真值，``render.md`` 是可移植的纯文本投影（CommonMark+GFM
子集，表达不了框线/并排/合并），``render.html`` 补上 markdown 表达不了的那部分结构——
示例框（仅外框线）、并列分栏（无框线并排）、表格合并单元格与表头重复、图/式块。

**同源判据**：内容集合、顺序、式中解释组的发射位置、资产引用前缀全部与 ``render.md`` /
``render.pdf`` 同一实现（:mod:`leleby_ssir.csm_renderer` / :mod:`leleby_ssir.pdf_renderer`）；
本模块只把同一份结构换成 HTML 元素，**不做任何新的语义推断**。

**产物是无脚本、无外部依赖的静态单文件**（样式内嵌 ``<style>``）：离线可看，
``$…$``/``$$…$$`` 数学记号原样保留（不引入 MathJax/KaTeX，见 docs/16 §5.1）。

规则对应: GBT-B01—B12（正文/列项/注/示例）、GBT-X01—X06（图/表/公式/注）、
GBT-B07（表框线、表头）、GEN-126/129（式中解释组的投影与发射顺序）、GEN-127（资产引用前缀）、
GEN-130（HTML 结构投影：框/分栏/合并单元格）。
"""

from __future__ import annotations

import html as _html
import re
from typing import Any

# 与 markdown 投影共用同一批判据/实现（同源，避免两套产物对同一 SSIR 给出不同内容）。
from .csm_renderer import (
    _formula_explanation_lines,
    _metadata,
    _sort_order,
    _strip_footnote_marker_prefix,
    _walk_nodes,
)
from .pdf_renderer import (
    _MATH_OVERLINE_CLOSE,
    _MATH_OVERLINE_OPEN,
    _inline_math_markup,
)
from .parser import FOOTNOTE_CITE_RE, FORMULA_VAR_INTRO_RE, footnote_label_marker, footnote_marker_text

_CELL_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def _esc(text: Any) -> str:
    """HTML 文本转义（含引号；``<br>`` 由调用方按需补回）。"""
    return _html.escape(str(text), quote=True)


# 行内 $…$ 的判据与 PDF 端同源（`pdf_renderer._markup` 的 `\\$([^$\\n]+)\\$` 一步）；
# 拍平/斜体/上下标/上划线的判定统一走 `pdf_renderer._inline_math_markup`，这里只把它的
# 哨兵换成 HTML 标签——三份投影对「公式里是什么字」必须同一判据（GEN-116/130）。
_INLINE_MATH_RE = re.compile(r"\$([^$\n]+)\$")
_MATH_SENTINELS: tuple[tuple[str, str, str, str], ...] = (
    ("\x00EMI\x00", "<i>", "\x00/EMI\x00", "</i>"),
    ("\x00SUB\x00", "<sub>", "\x00/SUB\x00", "</sub>"),
    ("\x00SUP\x00", "<sup>", "\x00/SUP\x00", "</sup>"),
    (_MATH_OVERLINE_OPEN, '<span class="overline">', _MATH_OVERLINE_CLOSE, "</span>"),
)


def _math_sentinels_to_tags(text: str) -> str:
    for open_sentinel, open_tag, close_sentinel, close_tag in _MATH_SENTINELS:
        text = text.replace(open_sentinel, open_tag).replace(close_sentinel, close_tag)
    return text


def _html_text(text: Any) -> str:
    """文本 → HTML 正文（**正文统一入口**）：脚注标记转上标、行内 ``$…$`` 转可读标记。

    脚注引用点 ``[foot:a]`` 按 GB/T 1.1-2020 9.12.1/9.12.2 的标记字面写成上标
    （图表脚注裸小写字母 ``<sup>b、d</sup>``、条文脚注 ``<sup>1)</sup>``，判据单源
    `parser.footnote_marker_text`）——与 render.pdf 的角标、render.md 的平印字面同源。

    控制符不得出现在产物里（用户 2026-09-23 报告 render.html 残留多处 `$…$`）：数学片段
    一律经 PDF 端唯一实现拍平后再转 HTML 标签，未知命令随之丢弃（与 PDF 同判据）。
    """
    raw = FOOTNOTE_CITE_RE.sub(
        lambda match: "\x00SUP\x00" + footnote_marker_text(match.group(1)) + "\x00/SUP\x00",
        str(text),
    )
    out: list[str] = []
    index = 0
    for match in _INLINE_MATH_RE.finditer(raw):
        out.append(_math_sentinels_to_tags(_esc(raw[index:match.start()])))
        out.append(_math_sentinels_to_tags(_esc(_inline_math_markup(match.group(1)))))
        index = match.end()
    out.append(_math_sentinels_to_tags(_esc(raw[index:])))
    return "".join(out)


def _html_note_line(text: Any) -> str:
    """表脚注/图脚注**注文行** → HTML：行首标记上标化（GB/T 1.1-2020 9.12.2）。

    图表脚注的标记是上标形式的裸小写字母（`a 注文`），与 `render.pdf` 的表末通栏行、
    `render.md` 的平印字面同源；只认「单字母/数字括号 + 空白」的形态，注文正文以字母
    开头（`GB/T …`）不动。
    """
    match = re.match(r"^\s*(?P<label>[A-Za-z]|\d+[)）])(?=\s)\s*(?P<body>.*)$", str(text), re.S)
    if not match:
        return _html_text(text)
    return f'<sup>{_esc(match.group("label"))}</sup> {_html_text(match.group("body"))}'


def asset_base_for(output_path: Any, docroot: Any) -> str:
    """见 :func:`leleby_ssir.csm_renderer.asset_base_for`（两个投影产物同一实现）。"""
    from .csm_renderer import asset_base_for as _impl

    return _impl(output_path, docroot)


def render_html(document: dict[str, Any], *, asset_base: str = "") -> str:
    """SSIR → HTML 投影（``render.html``）。

    ``asset_base``：产物所在目录到文档根的前缀（与 markdown 投影同义；默认空串 = 直接
    相对文档根写出）。产物不写时间戳/随机量——同一 SSIR 两次渲染字节相等。
    """
    metadata = _metadata(document)
    state = _HtmlState(document, asset_base=asset_base)
    for node in sorted(document["structuralRoot"].get("children", []), key=_sort_order):
        state.render_node(node)
    state.flush_explanation()
    return state.document_text(metadata)


class _HtmlState:
    def __init__(self, document: dict[str, Any], *, asset_base: str = "") -> None:
        self.document = document
        self.asset_base = asset_base
        self.lines: list[str] = []
        self.tables = {table["id"]: table for table in document.get("tables", [])}
        self.figures = {figure["id"]: figure for figure in document.get("figures", [])}
        self.formulas = {formula["id"]: formula for formula in document.get("formulas", [])}
        self.unknowns = {unknown["id"]: unknown for unknown in document.get("unknownContents", [])}
        # 表脚注（GB/T 1.1-2020 10.4.2.2/10.4.4.2）：归属某表的脚注由该表绘成表末通栏行。
        self.note_meta = {
            str(note.get("contentRef")): note
            for note in (document.get("notes") or [])
            if note.get("type") == "footnote" and note.get("contentRef")
        }
        self.note_texts = {
            str(element.get("id")): str(element.get("textContent") or "")
            for node in _walk_nodes(document["structuralRoot"].get("children", []) or [])
            for element in (node.get("contentElements") or [])
            if element.get("presentationType") == "footnote"
        }
        self.last_kind: str | None = None
        self.open_box: int | None = None
        # 待发射的式中解释行（GEN-126/129）：与 markdown 投影同判据——条目挂在公式上，
        # 版面上排在紧随其后的「式中：」引入行之后。
        self.pending_explanation: list[str] = []

    # --- 结构 ---------------------------------------------------------------

    def _sync_box(self, box: int | None, style: str | None = None) -> None:
        """示例框 → ``<div class="example-box">``（仅外框线）。

        框不可嵌套（parser 以 CSM-STRUCT-006 拒绝嵌套框），故只维护单层开关；
        ``boxStyle`` 非 ``frame`` 时附加样式类（底纹框等，config 定义）。
        """
        if box == self.open_box:
            return
        if self.open_box is not None:
            self.lines.append("</div>")
            self.open_box = None
        if box is None:
            return
        extra = "" if str(style or "frame") == "frame" else f" example-box-{_esc(str(style))}"
        self.lines.append(f'<div class="example-box{extra}">')
        self.open_box = box

    def flush_explanation(self) -> None:
        """发射暂存的式中解释行（幂等；无暂存时一个字符都不写）。"""
        if not self.pending_explanation:
            return
        self.lines.append('<div class="formula-vars">')
        for line in self.pending_explanation:
            self.lines.append(f'<div class="formula-var">{_html_text(line)}</div>')
        self.lines.append("</div>")
        self.pending_explanation = []

    def _is_explanation_intro(self, kind: str, content: dict[str, Any]) -> bool:
        # 判据与解析端同源（parser.FORMULA_VAR_INTRO_RE）：独占一行的「式中：」。
        if kind != "paragraph":
            return False
        return bool(FORMULA_VAR_INTRO_RE.match(str(content.get("textContent") or "").strip()))

    def render_node(self, node: dict[str, Any]) -> None:
        # 规则对应: GBT-H02—H04（章条编号与标题的层级编排）、GEN-031（编号规范化）。
        self._sync_box(node.get("box"), node.get("boxStyle"))
        level = min(max(int(node.get("level", 1)) + 1, 2), 6)
        self.lines.append(f"<h{level}>{_html_text(self._heading(node))}</h{level}>")
        self.render_contents(node.get("contentElements", []) or [])
        for child in sorted(node.get("children", []), key=_sort_order):
            self.render_node(child)

    def render_contents(self, contents: list[dict[str, Any]]) -> None:
        ordered = sorted(contents, key=_sort_order)
        index = 0
        while index < len(ordered):
            group = ordered[index].get("sideBySideGroup")
            if group:
                members: list[dict[str, Any]] = []
                while index < len(ordered) and ordered[index].get("sideBySideGroup") == group:
                    members.append(ordered[index])
                    index += 1
                self._render_side_by_side(members)
                continue
            self.render_content(ordered[index])
            index += 1
        self.flush_explanation()

    def _render_side_by_side(self, members: list[dict[str, Any]]) -> None:
        """并列组 → ``<div class="columns">`` + 每列一个 ``<div class="column">``。

        列内成员按**列优先**重放（与 markdown 投影同序：抽取顺序按行跨栏交错，canonical
        声明是列优先）。列宽 SSIR 未记录（sideBySideWidths 非 SSIR 字段）→ 等宽 flex，
        只表达「并排、无框线」这一结构事实（GB/T 1.1 对并列编排不规定线框）。
        """
        columns: dict[int, list[dict[str, Any]]] = {}
        for member in members:
            columns.setdefault(int(member.get("sideBySideColumn", 0)), []).append(member)
        keys = sorted(columns)
        self.lines.append(f'<div class="columns cols-{len(keys)}">')
        for column in keys:
            self.lines.append('<div class="column">')
            for member in sorted(columns[column], key=_sort_order):
                self.render_content(member)
            self.lines.append("</div>")
        self.lines.append("</div>")

    def _heading(self, node: dict[str, Any]) -> str:
        # 规则对应: GBT-C09/GEN-030（附录编号、(规范性)/(资料性) 与标题连排不插空格）。
        title = node.get("title", "")
        number = node.get("number")
        if node.get("nodeType") == "annex":
            return f"附录 {number}{title}".rstrip()
        if number:
            return f"{number} {title}".rstrip()
        return title

    # --- 内容元素 -----------------------------------------------------------

    def render_content(self, content: dict[str, Any]) -> None:
        # 规则对应: GBT-B03（段落）、GBT-B04（列项）、GBT-X03（注）、GBT-X05（示例）。
        self._sync_box(content.get("box"), content.get("boxStyle"))
        kind = content["presentationType"]
        intro = self._is_explanation_intro(kind, content)
        if not intro:
            self.flush_explanation()
        self.last_kind = kind
        if kind == "footnote":
            self._render_footnote(content)
        elif kind in {"paragraph", "note", "example", "warning", "quote"}:
            self._render_text(kind, content)
        elif kind == "list":
            self._render_list(content)
        elif kind == "table":
            self._render_table(self.tables[content["tableRef"]], content.get("id"))
        elif kind == "figure":
            self._render_figure(self.figures[content["figureRef"]])
        elif kind == "formula":
            self._render_formula(self.formulas[content["formulaRef"]])
        elif kind == "other":
            self._render_unknown(self.unknowns[content["unknownRef"]])
        else:
            self.lines.append(f'<p class="para">{_html_text(content.get("textContent", ""))}</p>')
        if intro:
            self.flush_explanation()

    def _render_text(self, kind: str, content: dict[str, Any]) -> None:
        text = str(content.get("textContent", ""))
        if kind == "paragraph":
            self.lines.append(f'<p class="para">{_html_text(text)}</p>')
            return
        # 注/示例/警示/引文：以左引线块与正文区分（GB/T 1.1 的注与示例版式），续行同块。
        body = "<br>".join(_html_text(line) for line in (text.splitlines() or [""]))
        self.lines.append(f'<div class="admonition {kind}">{body}</div>')

    def _render_footnote(self, content: dict[str, Any]) -> None:
        # 表脚注（notes[].anchorKind == tableCell）由所属表格绘成表末通栏行 → 此处跳过。
        note_meta = self.note_meta.get(str(content.get("id") or "")) or {}
        if str(note_meta.get("anchorKind") or "") == "tableCell":
            return
        # 与 markdown 投影同一判据：抽取文本常已带标记前缀（`a) 注文` / `a 注文`）→ 先剥再统一补。
        # 标记字面按 GB/T 1.1-2020 9.12.1（条文脚注 `1)`）/ 9.12.2（图表脚注裸字母 `a`）分族，
        # HTML 里是上标（`<sup>`），与 render.pdf 的角标同源。
        text = content.get("textContent", "")
        match = re.match(r"^(\d+)[)）]\s*(.*)$", text, re.S)
        label = str(content.get("footnoteMarker") or "").strip() or (match.group(1) if match else "")
        body = match.group(2) if match else text
        if not label:
            label = "1"
        stripped = _strip_footnote_marker_prefix(label, body)
        marker = _esc(footnote_label_marker(label))
        self.lines.append(
            f'<p class="footnote"><sup>{marker}</sup> {_html_text(stripped).strip()}</p>'
        )

    def _render_list(self, content: dict[str, Any]) -> None:
        # 标记本身是内容（a)、—、"1" 等，GB/T 1.1 附录 F 规定其字体）→ 显式输出，
        # 不用 <ul>/<ol> 的自动编号（那会替换掉标准里的标记形态）。
        self.lines.append('<div class="list">')
        for item in sorted(content.get("listItems", []), key=_sort_order):
            marker = _esc(item.get("marker", "-"))
            text = _html_text(item.get("text", ""))
            self.lines.append(f'<div class="list-item"><span class="marker">{marker}</span><span class="item-text">{text}</span></div>')
        self.lines.append("</div>")

    # --- 表 -----------------------------------------------------------------

    def _table_note_lines(self, owner_id: str | None) -> list[str]:
        """归属本表的表脚注正文行（`notes[].ownerRef` → 该表内容元素、`anchorKind` 为
        ``tableCell``）：GB/T 1.1 10.4.2.2/10.4.4.2 → 表框内的表末通栏行。"""
        lines: list[str] = []
        for content_ref, note in self.note_meta.items():
            if str(note.get("ownerRef") or "") != str(owner_id or ""):
                continue
            if str(note.get("anchorKind") or "") != "tableCell":
                continue
            text = str(self.note_texts.get(str(content_ref)) or "").strip()
            if text:
                lines.append(text)
        return lines

    def _render_table(self, table: dict[str, Any], owner_id: str | None = None) -> None:
        # 规则对应: GBT-B07（表编号表题居中置于表上、表头框线）、GBT-B08（无编号无题名不
        # 输出题注行）、GBT-X02（表头/合并单元格/空位；不准许分表、表中套表）、GEN-114
        # （表头行数 → thead）、GEN-115（续表注在 HTML 里没有分页语义，故只出现一次）。
        number = str(table.get("number") or "").strip()
        caption = str(table.get("caption") or "").strip()
        unit = str(table.get("unit") or "").strip()
        self.lines.append('<div class="table-block">')
        if number and caption:
            self.lines.append(f'<div class="table-caption">表{_esc(number)} {_html_text(caption)}</div>')
        elif number:
            self.lines.append(f'<div class="table-caption">表{_esc(number)}</div>')
        elif caption:
            self.lines.append(f'<div class="table-caption">表 {_html_text(caption)}</div>')
        if unit:
            self.lines.append(f'<div class="table-unit">单位为{_html_text(unit)}</div>')
        rows = sorted(table.get("rows", []) or [], key=lambda row: int(row["rowIndex"]))
        header_rows = 0
        for row in rows:
            if not row.get("isHeader"):
                break
            header_rows += 1
        # 表头格若跨到表体（rowspan 越过表头/表体边界），<thead> 会切断合并 → 整表退回 tbody。
        header_rowspan_bleeds = any(
            int(cell.get("rowspan", 1) or 1) + int(row["rowIndex"]) > header_rows
            for row in rows[:header_rows]
            for cell in (row.get("cells") or [])
        )
        if header_rowspan_bleeds:
            header_rows = 0
        rendered = [(row, self._table_row_cells(rows, row)) for row in rows]
        self.lines.append('<table class="gbt-table">')
        if header_rows:
            self.lines.append("<thead>")
            for row, cells in rendered[:header_rows]:
                self.lines.append("<tr>" + "".join(cells) + "</tr>")
            self.lines.append("</thead>")
        self.lines.append("<tbody>")
        for row, cells in rendered[header_rows:]:
            self.lines.append("<tr>" + "".join(cells) + "</tr>")
        # 表脚注并入表体（GB/T 1.1-2020 10.4.2.2「表脚注所在的框线」/10.4.4.2「置于表的左
        # 框线之内」）：作为表末**通栏行**绘在表框内，而不是排在表外。
        note_lines = self._table_note_lines(owner_id)
        if note_lines:
            width = max(len(row.get("cells") or []) for row in rows) if rows else 1
            body_text = "<br>".join(_html_note_line(line) for line in note_lines)
            self.lines.append(f'<tr><td class="table-note" colspan="{width}">{body_text}</td></tr>')
        self.lines.append("</tbody>")
        self.lines.append("</table>")
        self.lines.append("</div>")

    def _table_row_cells(self, rows: list[dict[str, Any]], row: dict[str, Any]) -> list[str]:
        """一行 → ``<td>/<th>`` 列表（合并单元格展开、被覆盖的占位格跳过）。

        网格模型与 SSIR 一致：跨行/跨列合并的**所有者格**输出 ``rowspan``/``colspan``，
        被覆盖位置上的占位空单元（``rowspan=1``/``colspan=1`` 且无文本）跳过；真有文本
        却落在被覆盖位置时**不丢弃**（保全抽取真值），按流式顺序输出。
        """
        row_index = int(row["rowIndex"])
        cells = sorted(row.get("cells") or [], key=lambda cell: int(cell["colIndex"]))
        col_indexes = {int(cell["colIndex"]) for data in rows for cell in (data.get("cells") or [])}
        col_of = {value: position for position, value in enumerate(sorted(col_indexes))}
        occupied: dict[tuple[int, int], bool] = {}
        for data in rows:
            data_index = int(data["rowIndex"])
            if data_index >= row_index:
                break
            for cell in data.get("cells") or []:
                start = col_of.get(int(cell["colIndex"]))
                if start is None:
                    continue
                colspan = max(1, int(cell.get("colspan", 1) or 1))
                rowspan = max(1, int(cell.get("rowspan", 1) or 1))
                for rr in range(data_index, data_index + rowspan):
                    for cc in range(start, start + colspan):
                        occupied[(rr, cc)] = True
        parts: list[str] = []
        cursor = 0
        for cell in cells:
            start = col_of.get(int(cell["colIndex"]))
            if start is None:
                continue
            colspan = max(1, int(cell.get("colspan", 1) or 1))
            rowspan = max(1, int(cell.get("rowspan", 1) or 1))
            text = str(cell.get("text") or "")
            # 跳过被上方跨行/跨列合并占住、本行又没有格的列（HTML 由 rowspan/colspan 表达）。
            while occupied.get((row_index, cursor)):
                cursor += 1
            if occupied.get((row_index, start)):
                # 本格落在被覆盖位置：占位空单元跳过；有文本的不丢弃（按流序重定位，宁移位不丢）。
                if not text.strip() and colspan == 1 and rowspan == 1:
                    continue
                start = cursor
            if start > cursor:
                # 稀疏行（该行缺列）：补空位保持列对齐。
                parts.extend('<td class="filler"></td>' for _ in range(start - cursor))
            attrs = ""
            if colspan > 1:
                attrs += f' colspan="{colspan}"'
            if rowspan > 1:
                attrs += f' rowspan="{rowspan}"'
            tag = "th" if (row.get("isHeader") or cell.get("isHeader")) else "td"
            parts.append(f"<{tag}{attrs}>{self._cell_html(text)}</{tag}>")
            cursor = start + colspan
        return parts

    def _cell_html(self, text: str) -> str:
        """单元格文本 → HTML：``<br>`` 保留换行、``![](…)`` 变 ``<img>``、其余转义。

        脚注引用点 ``[foot:a]`` 由 `_html_text`（正文统一入口）写成上标角标——图表脚注裸
        小写字母、条文脚注 ``N)``（GB/T 1.1-2020 9.12.1/9.12.2，与 markdown/PDF 同源）。
        """
        parts: list[str] = []
        position = 0
        for match in _CELL_IMAGE_RE.finditer(text):
            parts.append(_html_text(text[position:match.start()]))
            alt, ref = match.group(1), match.group(2)
            src = _esc(self.asset_base + ref.strip())
            parts.append(f'<img class="cell-image" src="{src}" alt="{_esc(alt)}">')
            position = match.end()
        parts.append(_html_text(text[position:]))
        return "".join(parts).replace("\n", "<br>")

    # --- 图 / 式 / 未知内容 -------------------------------------------------

    def _render_figure(self, figure: dict[str, Any]) -> None:
        # 规则对应: GBT-X01（图编号+图题）、GEN-032（单位陈述行在图之上）、GEN-127（资产前缀）。
        missing = figure.get("preservationStatus") == "partiallyPreserved" and not figure.get("assetRef")
        unit = str(figure.get("unit") or "").strip()
        caption = figure.get("caption", "")
        number = str(figure.get("number") or "").strip()
        label = f"图{number} {caption}".strip() if number else str(caption)
        self.lines.append('<figure class="figure">')
        if unit:
            self.lines.append(f'<div class="figure-unit">单位为{_html_text(unit)}</div>')
        if figure.get("assetRef"):
            alt = figure.get("altText") or caption
            src = _esc(self.asset_base + str(figure["assetRef"]))
            self.lines.append(f'<img src="{src}" alt="{_esc(alt)}">')
        else:
            suffix = "（图片占位）" if missing else ""
            self.lines.append(f'<div class="figure-placeholder">[{_esc(label)}{suffix}]</div>')
        if number or caption:
            self.lines.append(f"<figcaption>{_html_text(label)}</figcaption>")
        self.lines.append("</figure>")

    def _render_formula(self, formula: dict[str, Any]) -> None:
        # 规则对应: GBT-X06（公式另行编排、编号圆括号阿拉伯数字右端对齐）。
        body = (
            f'<img class="formula-image" src="{_esc(self.asset_base + str(formula["assetRef"]))}" alt="公式">'
            if formula.get("assetRef")
            else f'<span class="formula-text">{_math_sentinels_to_tags(_esc(_inline_math_markup(formula.get("rawText", ""))))}</span>'
        )
        self.lines.append('<div class="formula-block">')
        self.lines.append(f'<div class="formula-body">{body}</div>')
        if str(formula.get("number") or "").strip():
            self.lines.append(f'<div class="formula-number">式({_esc(formula["number"])})</div>')
        self.lines.append("</div>")
        # 式中解释组（GEN-126）：条目挂在本公式上，发射位置由紧随其后的引入行决定（累积）。
        self.pending_explanation.extend(_formula_explanation_lines(formula))

    def _render_unknown(self, unknown: dict[str, Any]) -> None:
        # 规则对应: GEN-052（未知内容注册表化，保留原始内容不丢弃）。
        self.lines.append(f'<div class="unknown"><pre>{_esc(unknown.get("rawContent", ""))}</pre></div>')

    # --- 文档 ---------------------------------------------------------------

    def document_text(self, metadata: dict[str, Any]) -> str:
        self._sync_box(None)
        head = [
            "<!DOCTYPE html>",
            f'<html lang="{_esc(metadata.get("language") or "zh-CN")}">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f'<title>{_esc(metadata.get("title", ""))}</title>',
            "<style>",
            _STYLE.strip(),
            "</style>",
            "</head>",
            "<body>",
            f'<h1 class="doc-title">{_esc(metadata.get("title", ""))}</h1>',
        ]
        tail = ["</body>", "</html>", ""]
        return "\n".join(head + self.lines + tail)


# 样式：仅表达版式结构（框线/分栏/表格边框/缩进），字体族给 CJK 标准的常规回落链。
_STYLE = """
:root { color-scheme: light dark; }
body {
  margin: 0 auto; max-width: 42em; padding: 2.5em 1.5em 4em;
  font-family: "Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", "SimSun", serif;
  font-size: 16px; line-height: 1.9; color: #111; background: #fff;
}
h1.doc-title { font-size: 1.6em; text-align: center; line-height: 1.5; }
h2, h3, h4, h5, h6 {
  font-family: "Noto Sans CJK SC", "Source Han Sans SC", "Heiti SC", "SimHei", sans-serif;
  line-height: 1.6;
}
p.para { margin: 0.7em 0; }
.example-box { border: 1px solid #000; padding: 0.7em 1em; margin: 1em 0; }
.example-box-shaded { background: #f7f7f7; }
.columns { display: flex; gap: 1.5em; align-items: flex-start; margin: 0.8em 0; }
.column { flex: 1 1 0; min-width: 0; }
.admonition { margin: 0.7em 0; padding: 0.1em 0 0.1em 0.9em; border-left: 2px solid #9a9a9a; }
.admonition.example { border-left-color: #6b6b6b; }
.admonition.warning { border-left-color: #c0392b; }
.admonition.quote { border-left-color: #b0b0b0; }
.footnote { font-size: 0.9em; margin: 0.3em 0; }
.list { margin: 0.7em 0; }
.list-item { display: flex; gap: 0.5em; }
.list-item .marker { flex: 0 0 auto; }
.list-item .item-text { flex: 1 1 auto; }
.table-block { margin: 1.2em 0; }
.table-caption {
  text-align: center; font-family: "Noto Sans CJK SC", "SimHei", sans-serif;
  font-size: 0.95em; margin-bottom: 0.15em;
}
.table-unit { text-align: right; font-size: 0.85em; }
table.gbt-table { border-collapse: collapse; width: 100%; font-size: 0.92em; }
table.gbt-table th, table.gbt-table td {
  border: 1px solid #000; padding: 0.25em 0.5em; vertical-align: top; text-align: left;
}
table.gbt-table thead th {
  background: #f0f0f0; font-family: "Noto Sans CJK SC", "SimHei", sans-serif; font-weight: normal;
}
table.gbt-table img.cell-image { max-width: 100%; vertical-align: middle; }
table.gbt-table td.table-note { text-align: left; font-size: 0.85em; }
/* 行内公式的 HTML 形态：变量斜体、上下标、上划线（GEN-116/130）。 */
.overline { text-decoration: overline; }
sub, sup { font-size: 0.75em; }
figure.figure { margin: 1.2em 0; text-align: center; }
figure.figure img { max-width: 100%; height: auto; }
figure.figure .figure-unit { text-align: right; font-size: 0.85em; }
figure.figure figcaption {
  font-family: "Noto Sans CJK SC", "SimHei", sans-serif; font-size: 0.95em; margin-top: 0.3em;
}
.figure-placeholder { color: #666; }
.formula-block { display: flex; align-items: center; gap: 1em; margin: 1em 0 1em 1.5em; }
.formula-body { flex: 1 1 auto; text-align: center; }
.formula-body img.formula-image { max-width: 100%; vertical-align: middle; }
.formula-body .formula-text {
  white-space: pre-wrap; font-family: "Cambria Math", "Latin Modern Math", "Times New Roman", serif;
}
.formula-number { flex: 0 0 auto; }
.formula-vars { margin: 0.2em 0 0.9em 2.5em; }
.formula-var { white-space: pre-wrap; }
.unknown { border: 1px dashed #999; background: #fafafa; padding: 0.5em 0.7em; margin: 0.8em 0; }
.unknown pre { margin: 0; white-space: pre-wrap; font-size: 0.85em; }
"""
