"""Render the M1 SSIR subset back into deterministic Canonical SSIR Markdown."""

from __future__ import annotations
import re

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from .parser import escape_table_cell


def render_csm(document: dict[str, Any]) -> str:
    """Render semantic SSIR content without copying derived provenance or quality data.

    规则对应: GEN-051（CSM→SSIR→CSM 身份层字段往返一致）。
    """
    metadata = _metadata(document)
    lines = ["---", yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).strip(), "---", ""]
    lines.extend([f"# {metadata['title']}", ""])
    state = _RenderState(document)
    for node in sorted(document["structuralRoot"].get("children", []), key=_sort_order):
        state.render_node(node)
    if state.box_open is not None:
        # 文档尾收拢未闭合的框（宽容语义：延伸到文档尾）。
        state.lines.append("<!-- ssir:/box -->")
        state.lines.append("")
    return "\n".join(lines + state.lines).rstrip() + "\n"


def write_csm(document: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_csm(document), encoding="utf-8", newline="\n")


def _metadata(document: dict[str, Any]) -> dict[str, Any]:
    # 规则对应: GEN-051（身份层字段——标题/英文名/日期/机构/分类号/代替关系/一致性声明逐字段相等）。
    common = document["metadata"]["common"]
    standard = document["metadata"].get("standard", {})
    source_file = document.get("sourceFiles", [{}])[0]
    metadata: dict[str, Any] = {
        "csm-version": "1.0",
        "document-type": "standard" if document.get("documentType") == "standard" else "other",
        "document-identifier": common["documentIdentifier"],
        "title": common["title"],
        "language": common.get("language", "und"),
        "source": {
            "mode": "user-markdown",
            "original-file-name": source_file.get("fileName", "source.csm.md"),
            "provenance": "none",
        },
        "extensions": {},
    }
    if document.get("documentType") == "standard":
        metadata["standard-number"] = standard.get("standardNumber", common["documentIdentifier"])
    # Round-trip identity fields: the renderer must emit the same metadata
    # keys it consumes, otherwise ssir and verify diverge on identity.
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
    profile = next(
        (
            quality["renderingProfile"]
            for quality in document.get("qualityAssessments", [])
            if quality.get("renderingProfile")
        ),
        None,
    )
    if profile:
        metadata["rendering-profile"] = profile
    return metadata


def _sort_order(value: dict[str, Any]) -> int:
    return int(value.get("sortOrder", 0))


def _format_width(value: float) -> str:
    """列宽比的确定性文本（整数不带小数点：2.0 → "2"，1.5 → "1.5"）。"""
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


class _RenderState:
    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document
        self.lines: list[str] = []
        self.tables = {table["id"]: table for table in document.get("tables", [])}
        self.figures = {figure["id"]: figure for figure in document.get("figures", [])}
        self.formulas = {formula["id"]: formula for formula in document.get("formulas", [])}
        self.unknowns = {unknown["id"]: unknown for unknown in document.get("unknownContents", [])}
        self.counts: defaultdict[str, int] = defaultdict(int)
        self.last_kind: str | None = None
        self.box_open: int | None = None  # 当前输出流已打开的 ssir:box id

    def _sync_box(self, box: int | None, style: str | None = None) -> None:
        """单元边界确定性重放 ssir:box 开/关标记（roundtrip 等价前提，2026-09-08）。"""
        box = box if box is not None else None
        if box == self.box_open:
            return
        if self.box_open is not None:
            self.lines.append("<!-- ssir:/box -->")
            self.lines.append("")
            self.box_open = None
        if box is not None:
            box_style = style if style in ("frame", "shaded") else "frame"
            attr = f' style="{box_style}"' if box_style != "frame" else ""
            self.lines.append(f"<!-- ssir:box{attr} -->")
            self.lines.append("")
            self.box_open = box

    def render_node(self, node: dict[str, Any]) -> None:
        # 规则对应: GBT-H02—H04（章条编号与标题的层级编排）、GEN-031（编号规范化）。
        self._sync_box(node.get("box"), node.get("boxStyle"))
        level = min(max(int(node.get("level", 1)) + 1, 2), 6)
        self.lines.extend(["#" * level + " " + self._heading(node), ""])
        self.render_contents(node.get("contentElements", []) or [])
        for child in sorted(node.get("children", []), key=_sort_order):
            self.render_node(child)

    def render_contents(self, contents: list[dict[str, Any]]) -> None:
        """内容元素序列发射：并列组（sideBySideGroup）按**列优先**重排后重放
        `ssir:columns/column//columns` 标记（2026-09-11）。

        抽取顺序在源两栏版式下常按行跨栏交错，而 canonical 的并列声明是列优先
        的；这里统一输出列优先，使「canonical → SSIR → render.md → 再解析」得到
        同一组列内容（roundtrip 的并列视图按列比较，跨列交错不算差异）。
        """
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

    def _render_side_by_side(self, members: list[dict[str, Any]]) -> None:
        widths = members[0].get("sideBySideWidths")
        attr = ""
        if widths:
            rendered = ",".join(_format_width(float(value)) for value in widths)
            attr = f' widths="{rendered}"'
        self.lines.append(f"<!-- ssir:columns{attr} -->")
        self.lines.append("")
        columns: dict[int, list[dict[str, Any]]] = {}
        for member in members:
            columns.setdefault(int(member.get("sideBySideColumn", 0)), []).append(member)
        for position, column in enumerate(sorted(columns)):
            if position:
                self.lines.append("<!-- ssir:column -->")
                self.lines.append("")
            for member in sorted(columns[column], key=_sort_order):
                self.render_content(member)
        self.lines.append("<!-- ssir:/columns -->")
        self.lines.append("")

    def _heading(self, node: dict[str, Any]) -> str:
        # 规则对应: GBT-C09/GEN-030（附录编号、(规范性)/(资料性) 与标题连排不插空格）。
        title = node.get("title", "")
        number = node.get("number")
        if node.get("nodeType") == "annex":
            # The annex status is retained in title as "（规范性） ...". Do not
            # introduce a space between the annex letter and its status marker.
            return f"附录 {number}{title}".rstrip()
        if number:
            return f"{number} {title}".rstrip()
        return title

    def render_content(self, content: dict[str, Any]) -> None:
        # 规则对应: GBT-B03（段落）、GBT-B04（列项）、GBT-X03（注）、GBT-X05（示例）。
        self._sync_box(content.get("box"), content.get("boxStyle"))
        kind = content["presentationType"]
        prev_kind = self.last_kind
        self.last_kind = kind
        if kind == "footnote":
            # canonical 写回（GEN-118）：定义写成指令对、独立成行，紧随引用段之后；
            # 渲染端把注文绘到引用所在页页脚（0 高占位锚定页底）。旧写法（定义拼在
            # 段落同行、GFM 标记）已由 docs/07 §6.7 改为本形式，导入端三种摆放形态均接受。
            text = content.get("textContent", "")
            m = re.match(r"^(\d+)[)）]\s*(.*)$", text, re.S)
            label = str(content.get("footnoteMarker") or "").strip() or (m.group(1) if m else "")
            body = m.group(2) if m else text
            if not label:
                label = "1"
            def_line = f"<!--ssir:foot:{label}-->{body}<!--ssir:/foot-->"
            self.lines.extend([def_line, ""])
        elif kind in {"paragraph", "note", "example", "warning", "quote"}:
            text = content.get("textContent", "")
            if kind == "paragraph":
                self.lines.extend([text, ""])
            else:
                # 多行注/示例/警示/引文：每行都加引用前缀，否则续行重解析会
                # 变成普通段落（roundtrip structure 层不一致）。
                note_lines = text.splitlines() or [""]
                self.lines.extend([f"> {line}" for line in note_lines] + [""])
        elif kind == "list":
            for item in sorted(content.get("listItems", []), key=_sort_order):
                self.lines.append(f"{item.get('marker', '-')} {item.get('text', '')}")
            self.lines.append("")
        elif kind == "table":
            self._render_table(self.tables[content["tableRef"]])
        elif kind == "figure":
            self._render_figure(self.figures[content["figureRef"]])
        elif kind == "formula":
            self._render_formula(self.formulas[content["formulaRef"]])
        elif kind == "other":
            self._render_unknown(self.unknowns[content["unknownRef"]])
        else:
            self.lines.extend([content.get("textContent", ""), ""])

    def _next_id(self, kind: str) -> str:
        self.counts[kind] += 1
        return f"rt-{kind}-{self.counts[kind]:03d}"

    def _render_table(self, table: dict[str, Any]) -> None:
        # 规则对应: GBT-B08（题注形如"表X 题名"，无编号无题名不输出题注行）、GBT-X02（表头/
        # 合并单元格/空位以一字线表示）。
        table_id = self._next_id("tbl")
        header_rows = sum(1 for row in table["rows"] if row.get("isHeader")) or 1
        unit = str(table.get("unit") or "").strip()
        unit_attr = f' unit="{unit}"' if unit else ""
        self.lines.append(f'<!-- ssir:table id="{table_id}" header-rows="{header_rows}"{unit_attr} -->')
        if table.get("number") and table.get("caption"):
            self.lines.append(f"**表{table['number']} {table['caption']}**")
        elif table.get("number"):
            # Bare numbered caption ("表 N" with the title omitted — common in
            # 行业标准/企业标准 layouts); keep the number so the roundtrip
            # preserves GBT-X02 compliance (题注仅编号).
            self.lines.append(f"**表{table['number']}**")
        elif table.get("caption"):
            self.lines.append(f"**表 {table['caption']}**")
        for row_index, row in enumerate(table["rows"]):
            cells = [self._table_cell(cell.get("text", "")) for cell in sorted(row["cells"], key=lambda item: item["colIndex"])]
            self.lines.append("| " + " | ".join(cells) + " |")
            if row_index == 0:
                self.lines.append("| " + " | ".join("---" for _ in cells) + " |")
        for row in table["rows"]:
            for cell in row["cells"]:
                if cell.get("rowspan", 1) > 1 or cell.get("colspan", 1) > 1:
                    # row 为**绝对** 0-based 表格行（表头行也算在内：row=0 即第一行），
                    # 与 builder 的 data_row 同一基准（builder 直接取该值）。旧写法
                    # `rowIndex - header_rows + 1` 只在 header-rows=1 时等于绝对值。
                    self.lines.append(
                        '<!-- ssir:table-merge table="{table}" row="{row}" column="{column}" rowspan="{rowspan}" colspan="{colspan}" -->'.format(
                            table=table_id,
                            row=int(cell["rowIndex"]),
                            column=int(cell["colIndex"]) + 1,
                            rowspan=cell.get("rowspan", 1),
                            colspan=cell.get("colspan", 1),
                        )
                    )
        self.lines.append("")

    @staticmethod
    def _table_cell(text: str) -> str:
        return escape_table_cell(text)

    def _render_figure(self, figure: dict[str, Any]) -> None:
        # 规则对应: GBT-X01（图编号+图题；资产缺失时以占位符标注并保留编号）、
        # GEN-032（图的单位陈述行写在图指令之前——解析时折进图节点，重放须保形）。
        figure_id = self._next_id("fig")
        missing = figure.get("preservationStatus") == "partiallyPreserved" and not figure.get("assetRef")
        unit = str(figure.get("unit") or "").strip()
        if unit:
            self.lines.append(f"单位为{unit}")
            self.lines.append("")
        directive = f'<!-- ssir:figure id="{figure_id}"'
        if missing:
            directive += ' asset-status="missing"'
        directive += " -->"
        self.lines.append(directive)
        if figure.get("assetRef"):
            self.lines.append(f"![{figure.get('altText', figure.get('caption', ''))}]({figure['assetRef']})")
        else:
            caption = figure.get("caption", "")
            label = f"图{figure['number']} {caption}".strip() if figure.get("number") else caption
            suffix = "（图片占位）" if missing else ""
            self.lines.append(f"> [{label}{suffix}]")
        self.lines.append("")

    def _render_formula(self, formula: dict[str, Any]) -> None:
        # 规则对应: GBT-X06（数学公式另行编排、编号圆括号阿拉伯数字右端对齐）。
        # 编号以 CSM 语法的独立行「式(N)」写回（docs/07 §6.7；编号本身是纯标签，
        # 渲染端按 GB/T 1.1-2020 10.4.3 补圆括号并右端对齐连接）。
        formula_id = self._next_id("fm")
        self.lines.extend([f'<!-- ssir:formula id="{formula_id}" -->', "$$", formula["rawText"], "$$"])
        if str(formula.get("number") or "").strip():
            self.lines.append(f"式({formula['number']})")
        self.lines.append("")

    def _render_unknown(self, unknown: dict[str, Any]) -> None:
        # 规则对应: GEN-052（未知内容注册表化，保留原始内容不丢弃）。
        unknown_id = self._next_id("unk")
        hint = unknown.get("contentTypeHint")
        directive = f'<!-- ssir:unknown id="{unknown_id}"'
        if hint:
            directive += f' type-hint="{hint}"'
        self.lines.extend([directive + " -->", "```text", unknown["rawContent"], "```", ""])
