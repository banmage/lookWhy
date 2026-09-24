"""SSIR → 标准 markdown 投影（render.md，GB/T 1.1 形态；无指令、无 HTML 注释）。

回环验证已永久下线（2026-09-22 用户裁定）：本模块不再产出「可往返的 CSM」，
只把 SSIR 投影成与渲染产物等价的 markdown。
"""

from __future__ import annotations
import os

import re
from pathlib import Path

from typing import Any


from .parser import (
    FOOTNOTE_CITE_RE,
    FORMULA_VAR_INTRO_RE,
    escape_table_cell,
    footnote_label_marker,
    footnote_marker_text,
)
# 式中解释行的文本形态由 PDF 渲染端唯一定义（`symbol——definition`）；投影复用同一实现，
# 避免两套渲染产物对同一 SSIR 字段给出不同写法。
from .pdf_renderer import _formula_explanation_lines


def asset_base_for(output_path: Path | str, docroot: Path | str) -> str:
    """投影产物所在目录 → 文档根的**相对前缀**（``"../"`` 之类）。

    SSIR 的 ``assetRef`` 一律相对文档根（``assets/…``）；投影产物落在
    ``04_render/`` 等子目录里，写成裸 ``assets/…`` 在阅读器里解析到
    ``04_render/assets/…``（不存在）→ 图全部不显示。此函数给出补前缀。
    """
    base = Path(output_path).parent
    rel = os.path.relpath(str(docroot), str(base))
    if rel in (".", ""):
        return ""
    return rel.replace(os.sep, "/") + "/"


def render_csm(document: dict[str, Any], *, asset_base: str = "") -> str:
    """SSIR → **标准 markdown 投影**（render.md）：零 `<!-- ssir:… -->` 指令、零 HTML 注释、
    无 front matter（2026-09-22 用户裁定：render.md 是 SSIR 的等价 markdown，不承担往返）。

    ``asset_base``：产物所在目录到文档根的前缀（见 :func:`asset_base_for`）；默认空串
    = 相对文档根写出（``ssir csm project`` 的输出路径未知时如此）。

    规则对应: GBT-B01—B12（正文/列项/注/示例）、GBT-X01—X06（图/表/公式/注）、GEN-126（式中解释组
    必须投影）、GEN-127（资产引用按产物位置解析）。
    """
    metadata = _metadata(document)
    lines: list[str] = [f"# {metadata['title']}", ""]
    state = _RenderState(document, asset_base=asset_base)
    for node in sorted(document["structuralRoot"].get("children", []), key=_sort_order):
        state.render_node(node)
    state.flush_explanation()
    return "\n".join(lines + state.lines).rstrip() + "\n"


def render_markdown(document: dict[str, Any], *, asset_base: str = "") -> str:
    """兼容别名（`render_csm` 的语义化名称；回环下线后本模块只做投影）。"""
    return render_csm(document, asset_base=asset_base)


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


def _walk_nodes(nodes: list[dict[str, Any]]) -> Any:
    """深度优先遍历结构节点（含子节点）。"""
    for node in nodes:
        yield node
        yield from _walk_nodes(node.get("children", []) or [])


def _project_text(text: str) -> str:
    """投影的文本规范化：脚注引用点 `[foot:a]` → 标记字面（`parser.footnote_marker_text`）。

    投影是 GB/T 1.1 版式的等价 markdown，引用点应与渲染产物同形（角标而非 CSM 标记）。
    标记字面按 9.12.1/9.12.2 分族：条文脚注（数字编号）`1)`、图表脚注（字母编号）裸字母
    `a`（一格多角标按源分隔符连排 `b、d`）。markdown 表达不了上标，故平印字面。
    """
    return FOOTNOTE_CITE_RE.sub(lambda m: footnote_marker_text(m.group(1)), str(text))


def _strip_footnote_marker_prefix(label: str, body: str) -> str:
    r"""去掉注文文本里**已有的**行首标记（旧抽取形态 `a) 注文` / 新形态 `a 注文`）。

    数字编号（条文脚注 9.12.1）只认带半圆括号的形态（编号必带括号，`^\s*1)\s*`）；
    字母编号（图表脚注 9.12.2）的标记与注文以空白分界（`a 注文`），故只在其后有空白时剥离——
    避免把注文正文里以该字母开头的词（`a 型电机…` 之外还有 `abc…` 这类）误剥。
    """
    label = str(label)
    if label.isdigit():
        return re.sub(rf"^\s*{re.escape(label)}\s*[)）]\s*", "", str(body))
    return re.sub(rf"^\s*{re.escape(label)}[\s\u3000]+", "", str(body))


class _RenderState:
    def __init__(self, document: dict[str, Any], *, asset_base: str = "") -> None:
        self.document = document
        self.asset_base = asset_base
        self.lines: list[str] = []
        self.tables = {table["id"]: table for table in document.get("tables", [])}
        self.figures = {figure["id"]: figure for figure in document.get("figures", [])}
        self.formulas = {formula["id"]: formula for formula in document.get("formulas", [])}
        self.unknowns = {unknown["id"]: unknown for unknown in document.get("unknownContents", [])}
        # 表脚注（GB/T 1.1-2020 10.4.2.2/10.4.4.2）：归属某表的脚注在**表框内**投影——
        # 由表投影成表末通栏行，脚注元素本身在正文流里跳过（与 PDF/HTML 同一判据）。
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
        self.box_open: int | None = None  # 当前输出流已打开的 ssir:box id
        # 待发射的式中解释行（GEN-126）：SSIR 把条目挂在公式上，而版面上它们排在
        # 「式中：」引入行**之后**——先暂存，粘回引入行位置再发射。
        self.pending_explanation: list[str] = []

    def _sync_box(self, box: int | None, style: str | None = None) -> None:
        """投影不写任何 HTML 注释：框是版式信息，由标题/段落层级与示例内容表达。"""
        return None

    def flush_explanation(self) -> None:
        """发射暂存的式中解释行（幂等；无暂存时不写任何行）。"""
        if self.pending_explanation:
            self.lines.extend(self.pending_explanation + [""])
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
        self.lines.extend(["#" * level + " " + self._heading(node), ""])
        self.render_contents(node.get("contentElements", []) or [])
        for child in sorted(node.get("children", []), key=_sort_order):
            self.render_node(child)

    def render_contents(self, contents: list[dict[str, Any]]) -> None:
        """内容元素序列发射：并列组（sideBySideGroup）按**列优先**重排后重放
        `ssir:columns/column//columns` 标记（2026-09-11）。

        抽取顺序在源两栏版式下常按行跨栏交错，而 canonical 的并列声明是列优先
        的；这里统一输出列优先，使「canonical → SSIR → render.md → 再解析」得到
        同一组列内容（并列编排：按列分组，跨列交错不算差异）。
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
        self.flush_explanation()

    def _render_side_by_side(self, members: list[dict[str, Any]]) -> None:
        # 投影：并列组按列顺序输出成员内容；`<!-- ssir:columns -->` 等版式指令不投影
        # （GB/T 1.1 对并列编排无 markdown 记号，成员内容本身的顺序即语义）。
        columns: dict[int, list[dict[str, Any]]] = {}
        for member in members:
            columns.setdefault(int(member.get("sideBySideColumn", 0)), []).append(member)
        for column in sorted(columns):
            for member in sorted(columns[column], key=_sort_order):
                self.render_content(member)

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
        # 式中解释行（GEN-126）：粘回「式中：」引入行之后；引入行缺失/顺序异常时**立即发射**
        # （宁可就地写出，也不让内容丢失）。
        intro = self._is_explanation_intro(kind, content)
        if not intro:
            self.flush_explanation()
        prev_kind = self.last_kind
        self.last_kind = kind
        if kind == "footnote":
            # 表脚注（notes[].anchorKind == tableCell）由所属表格投影成表末通栏行
            # （GB/T 1.1-2020 10.4.2.2/10.4.4.2）——此处跳过，不重复投影成表外一行。
            note_meta = self.note_meta.get(str(content.get("id") or "")) or {}
            if str(note_meta.get("anchorKind") or "") == "tableCell":
                if intro:
                    self.flush_explanation()
                return
            # 脚注定义写成 GB/T 1.1 9.12.1/9.12.2 的形态：条文脚注 `1) 注文`、
            # 图表脚注 `a 注文`（裸小写字母，**不补右括号**），独立成行、紧随引用段之后。
            # 抽取文本本身常已带标记前缀（`a) 注文` / `a 注文`），先去掉再统一补。
            text = content.get("textContent", "")
            m = re.match(r"^(\d+)[)）]\s*(.*)$", text, re.S)
            label = str(content.get("footnoteMarker") or "").strip() or (m.group(1) if m else "")
            body = m.group(2) if m else text
            if not label:
                label = "1"
            stripped = _strip_footnote_marker_prefix(label, body)
            self.lines.extend([_project_text(f"{footnote_label_marker(label)} {stripped}").strip(), ""])
        elif kind in {"paragraph", "note", "example", "warning", "quote"}:
            text = _project_text(content.get("textContent", ""))
            if kind == "paragraph":
                self.lines.extend([text, ""])
            else:
                # 多行注/示例/警示/引文：每行都加引用前缀（GB/T 1.1 的注/示例以引线块
                # 与正文区分），否则续行会变成普通段落。
                note_lines = text.splitlines() or [""]
                self.lines.extend([f"> {line}" for line in note_lines] + [""])
        elif kind == "list":
            for item in sorted(content.get("listItems", []), key=_sort_order):
                self.lines.append(f"{item.get('marker', '-')} {_project_text(item.get('text', ''))}")
            self.lines.append("")
        elif kind == "table":
            self._render_table(self.tables[content["tableRef"]], content.get("id"))
        elif kind == "figure":
            self._render_figure(self.figures[content["figureRef"]])
        elif kind == "formula":
            self._render_formula(self.formulas[content["formulaRef"]])
        elif kind == "other":
            self._render_unknown(self.unknowns[content["unknownRef"]])
        else:
            self.lines.extend([content.get("textContent", ""), ""])
        if intro:
            self.flush_explanation()

    def _table_note_lines(self, owner_id: str | None) -> list[str]:
        """归属本表的表脚注正文行（`notes[].ownerRef` 指向该表内容元素、`anchorKind` 为
        ``tableCell``）。规则依据：GB/T 1.1-2020 10.4.2.2（表脚注的框线属表的框线）/
        10.4.4.2（正文置于表的左框线之内）→ 投影为表末**通栏行**，而不是表外一行。"""
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
        # 规则对应: GBT-B08（题注形如"表X 题名"，无编号无题名不输出题注行）、GBT-X02（表头/
        # 合并单元格/空位以一字线表示）。投影里合并只体现在内容（GFM 无法表达，不写指令）。
        if table.get("number") and table.get("caption"):
            self.lines.append(f"**表{table['number']} {table['caption']}**")
        elif table.get("number"):
            # Bare numbered caption ("表 N" with the title omitted — common in
            # 行业标准/企业标准 layouts); keep the number so the projection
            # preserves GBT-X02 compliance (题注仅编号).
            self.lines.append(f"**表{table['number']}**")
        elif table.get("caption"):
            self.lines.append(f"**表 {table['caption']}**")
        for row_index, row in enumerate(table["rows"]):
            cells = [self._table_cell(cell.get("text", "")) for cell in sorted(row["cells"], key=lambda item: item["colIndex"])]
            self.lines.append("| " + " | ".join(_project_text(cell) for cell in cells) + " |")
            if row_index == 0:
                self.lines.append("| " + " | ".join("---" for _ in cells) + " |")
        # 表脚注并入表体（GB/T 1.1-2020 10.4.2.2/10.4.4.2）：作为表末**通栏行**投影，
        # 置空后续单元格（与 canonical 里表内通栏注行同一形态；GFM 无法表达单元格合并，
        # 但注文所在行的位置与表内顺序与 PDF/HTML 一致）。
        note_lines = self._table_note_lines(owner_id)
        if note_lines:
            width = max(len(row["cells"]) for row in table["rows"]) if table["rows"] else 1
            self.lines.append("| " + "<br>".join(note_lines) + " |" + "  |" * (width - 1))
        self.lines.append("")

    @staticmethod
    def _table_cell(text: str) -> str:
        return escape_table_cell(text)

    def _render_figure(self, figure: dict[str, Any]) -> None:
        # 规则对应: GBT-X01（图编号+图题；资产缺失时以占位符标注并保留编号）、
        # GEN-032（图的单位陈述行写在图指令之前——解析时折进图节点，重放须保形）。
        missing = figure.get("preservationStatus") == "partiallyPreserved" and not figure.get("assetRef")
        unit = str(figure.get("unit") or "").strip()
        if unit:
            self.lines.append(f"单位为{unit}")
            self.lines.append("")
        if figure.get("assetRef"):
            self.lines.append(f"![{figure.get('altText', figure.get('caption', ''))}]({self.asset_base}{figure['assetRef']})")
        else:
            caption = figure.get("caption", "")
            label = f"图{figure['number']} {caption}".strip() if figure.get("number") else caption
            suffix = "（图片占位）" if missing else ""
            self.lines.append(f"> [{label}{suffix}]")
        self.lines.append("")

    def _render_formula(self, formula: dict[str, Any]) -> None:
        # 规则对应: GBT-X06（数学公式另行编排、编号圆括号阿拉伯数字右端对齐）。
        # 编号以 GB/T 1.1-2020 10.4.3 的独立行「式(N)」（圆括号由渲染端补）。
        self.lines.extend(["$$", formula["rawText"], "$$"])
        if str(formula.get("number") or "").strip():
            self.lines.append(f"式({formula['number']})")
        self.lines.append("")
        # 式中解释组（GEN-126，docs/15 §3.8）：条目挂在本公式上，投影位置由紧随其后的
        # 「式中：」引入行决定（见 render_content）。仍按**累积**处理（同一公式可有多组）。
        self.pending_explanation.extend(_formula_explanation_lines(formula))

    def _render_unknown(self, unknown: dict[str, Any]) -> None:
        # 规则对应: GEN-052（未知内容注册表化，保留原始内容不丢弃）。
        self.lines.extend(["```text", unknown["rawContent"], "```", ""])
