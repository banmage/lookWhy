"""Build schema-conformant SSIR JSON from a parsed CSM document."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import re
from typing import Any

from .naming import (
    annex_path,
    clause_path,
    element_id,
    escape_standard_number,
    local_element_id,
    numbered_element_path,
    owned_element_id,
)
from .parser import (
    DECLARATION_ITEM_RES,
    EX_HEADER_RE,
    FOOTNOTE_CITE_RE,
    TOC_NUMBER_RE,
    Block,
    CSMDocument,
    figure_caption_parts,
    footnote_citations,
    footnote_label_marker,
    term_entry_pair,
)

# 脚注引用标记 [foot:N]（docs/07 §6.7；GEN-118）：把脚注定义与其注释的条款关联；
# 渲染端绘成上角标——数字编号（条文脚注 9.12.1）为「N)」，字母编号（图表脚注 9.12.2）
# 为裸小写字母（`parser.footnote_marker_text`）。定义侧的正则由 parser 统一持有。
_FOOTNOTE_REF_RE = FOOTNOTE_CITE_RE

# --- 文档元素标识（TDRS 命名规则，见 docs/16 §10） --------------------------
# 无编号的前置/文后要素（TDRS 只规定编号元素与条款路径，此处按固定英文名补全，
# 保证标识稳定、可读、ASCII 安全）。
_UNNUMBERED_ELEMENT_PATHS = {
    "封面": "Cover",
    "目次": "Contents",
    "前言": "Foreword",
    "引言": "Introduction",
    "规范性引用文件": "NormativeReferences",
    "参考文献": "Bibliography",
    "索引": "Index",
}

# presentationType → 内容位置槽标识前缀（local_element_id 的 kind）。表/图/公式/原样块
# 的**对象**标识是编号元素标识（#Table_3 等），内容槽用 Block，避免与对象标识混淆。
_CONTENT_ELEMENT_KIND = {
    "paragraph": "paragraph",
    "quote": "paragraph",
    "list": "list",
    "example": "example",
    "note": "note",
    "warning": "note",
    "footnote": "footnote",
    "table": "block",
    "figure": "block",
    "formula": "block",
    "other": "block",
}

# 表/图/公式/原样块无编号时的回退序号段（TDRS 只规定编号元素）
_UNNUMBERED_ELEMENT_SEQ = "Seq"


class _ElementIds:
    """TDRS 元素标识分配器（``{标准标识}#{条款路径}``，见 docs/16 §10）。

    - ``used_ids``：已分配标识，保证唯一；重号追加 ``-2/-3`` 并登记 ``collisions``；
    - ``paths``：元素标识 → 条款路径（内容元素/注的属主寻址用）；
    - ``id_map``：改写前的标识 → 新标识（跨元素引用回填用）；
    - ``fallbacks``：编号畸形/缺失而回退到序号标识的登记项（如实报告，不猜）。
    """

    def __init__(self, standard_id: str) -> None:
        self.standard_id = standard_id
        self.paths: dict[str, str] = {}
        self.id_map: dict[str, str] = {}
        self.used_ids: set[str] = set()
        self.collisions: list[str] = []
        self.fallbacks: list[str] = []
        self._counters: dict[str, int] = defaultdict(int)

    def next(self, name: str) -> int:
        self._counters[name] += 1
        return self._counters[name]

    def unique(self, identifier: str) -> str:
        """登记元素标识；已存在时追加 -2/-3…（确定性，并记录重号）。"""
        if identifier not in self.used_ids:
            self.used_ids.add(identifier)
            return identifier
        suffix = 2
        while f"{identifier}-{suffix}" in self.used_ids:
            suffix += 1
        resolved = f"{identifier}-{suffix}"
        self.used_ids.add(resolved)
        self.collisions.append(f"{identifier} -> {resolved}")
        return resolved

    def element(self, path: str) -> str:
        return self.unique(element_id(self.standard_id, path))


def _node_element_path(ids: _ElementIds, node: dict[str, Any],
                       annex_letter: str | None) -> tuple[str, str | None]:
    """结构节点的条款路径（TDRS §二/§四；无编号要素按固定英文名）。"""
    node_type = str(node.get("nodeType") or "")
    number = str(node.get("number") or "").strip()
    title = str(node.get("title") or "").strip()
    if node_type == "annex" and number:
        letter = number.strip().upper()
        return annex_path(letter), letter
    lettered = re.fullmatch(r"([A-Z])\.(\d+(?:\.\d+)*)", number) if number else None
    if lettered:
        # 附录条及其内层（`A.1`、`A.2.1`）——附录字母来自编号本身，不依赖父链
        # （源文件常把附录条写成根级同级标题）。
        return annex_path(lettered.group(1), number), lettered.group(1)
    if number:
        return clause_path(number), annex_letter
    key = re.sub(r"^[(（][^)）]*[)）]\s*", "", title).replace(" ", "")
    if key in _UNNUMBERED_ELEMENT_PATHS:
        return _UNNUMBERED_ELEMENT_PATHS[key], annex_letter
    return f"{node_type or 'node'}_{ids.next('node_path'):04d}", annex_letter


def _assign_content_element_id(ids: _ElementIds, content: dict[str, Any],
                               owner_id: str, owner_path: str) -> None:
    """内容元素与列表项的 TDRS 标识（``#<条款路径>/<Kind>-<序号>``、``#<条款路径>_<marker>``）。"""
    kind = _CONTENT_ELEMENT_KIND.get(str(content.get("presentationType") or ""), "paragraph")
    new_id = ids.unique(local_element_id(owner_id, kind, ids.next("content_element")))
    ids.id_map[str(content["id"])] = new_id
    content["id"] = new_id
    if content.get("parentNodeId"):
        content["parentNodeId"] = owner_id
    # 列表项：TDRS §五「项（a、b、c）」——用 marker 作后缀；无字母/数字 marker
    # （破折号、间隔号等）用**该条款内的项序号**（`Item N`），保证标识确定、不丢项、
    # 同一章条内多个无标记列表也不重号。
    for index, item in enumerate(content.get("listItems") or [], start=1):
        item_seq = ids.next(f"item:{owner_path}")
        item_path = f"{owner_path}_{_item_token(str(item.get('marker') or ''), item_seq)}"
        item_id = ids.unique(element_id(ids.standard_id, item_path))
        ids.id_map[str(item["id"])] = item_id
        item["id"] = item_id
        for sub_index, sub in enumerate(item.get("subItems") or [], start=1):
            sub_seq = ids.next(f"subitem:{owner_path}")
            sub_path = f"{item_path}_{_item_token(str(sub.get('marker') or ''), sub_seq)}"
            sub_id = ids.unique(element_id(ids.standard_id, sub_path))
            ids.id_map[str(sub["id"])] = sub_id
            sub["id"] = sub_id


def assign_element_ids(ids: _ElementIds, root: dict[str, Any],
                       registries: list[tuple[str, list[dict[str, Any]], str]],
                       notes: list[dict[str, Any]] | None = None) -> None:
    """把一棵 SSIR 树与注册表的元素标识改写为 TDRS 形式（就地改写，幂等）。

    分两阶段：先定标识（注册表 → 节点 → 内容元素/列表项），再统一改写跨元素引用
    （``footnoteAnchorRef`` 指向的节点可能在定义之后才被访问）。已符合 TDRS 规则的
    文档重复执行结果逐字节相同。
    """
    for kind, items, prefix in registries:
        for index, item in enumerate(items or [], start=1):
            number = str(item.get("number") or "").strip()
            path = None
            if number:
                try:
                    path = numbered_element_path(kind, number)
                except ValueError:
                    path = None
                    ids.fallbacks.append(f"{kind} {number!r}")
            if not path:
                path = f"{prefix}_{_UNNUMBERED_ELEMENT_SEQ}{index:04d}"
            new_id = ids.element(path)
            ids.id_map[str(item["id"])] = new_id
            item["id"] = new_id

    contents: list[dict[str, Any]] = []
    anchor_items: list[dict[str, Any]] = []

    def walk(node: dict[str, Any], annex_letter: str | None, is_root: bool) -> None:
        if is_root:
            path, child_annex = "Root", None
            new_id = ids.element("Root")
            ids.id_map[str(node["id"])] = new_id
            node["id"] = new_id
            node["logicalId"] = path
        else:
            path, child_annex = _node_element_path(ids, node, annex_letter)
            new_id = ids.element(path)
            ids.id_map[str(node["id"])] = new_id
            node["id"] = new_id
            node["logicalId"] = path
        ids.paths[str(node["id"])] = path
        anchor_items.append(node)
        for content in node.get("contentElements") or []:
            contents.append(content)
            anchor_items.append(content)
            for item in content.get("listItems") or []:
                anchor_items.append(item)
                anchor_items.extend(item.get("subItems") or [])
            _assign_content_element_id(ids, content, str(node["id"]), path)
        for child in node.get("children") or []:
            walk(child, child_annex, False)

    walk(root, None, True)

    for content in contents:
        for ref_key in ("tableRef", "figureRef", "formulaRef", "unknownRef", "footnoteAnchorRef"):
            ref = content.get(ref_key)
            if ref:
                content[ref_key] = ids.id_map.get(str(ref), str(ref))

    # 注登记（`notes[]`，docs/15 §3.6）的引用同源改写：声明登记时写的是内容元素/节点的
    # **当时**标识，此处按 id_map 统一换成 TDRS 标识（不猜、不落悬挂引用）。
    for note in notes or []:
        for key in ("contentRef", "ownerRef"):
            value = note.get(key)
            if value and str(value) in ids.id_map:
                note[key] = ids.id_map[str(value)]

    # 列表组引语引用（`ListGroup.introRef`）同源改写；内部占位永不进入 SSIR。
    for content in contents:
        group = content.get("listGroup")
        if not isinstance(group, dict):
            continue
        group.pop("introRefPending", None)
        intro = group.get("introRef")
        if intro:
            group["introRef"] = ids.id_map.get(str(intro), str(intro))

    # 源定位锚点（TDRS：``{标准标识}#Anchor-序号``）：按文档序（节点 → 其内容元素 →
    # 子节点，再注册表元素）重编号。锚点标识无外部引用（消费方只读 markdownStartLine
    # 等），故重编号是安全的。
    registry_items = [entry for _, items, _ in registries for entry in items or []]
    for item in anchor_items + registry_items:
        # 列表项用单数 ``sourceAnchor``，其余元素用 ``sourceAnchors``（schema 两种都有）。
        anchors = list(item.get("sourceAnchors") or [])
        single = item.get("sourceAnchor")
        if isinstance(single, dict):
            anchors.append(single)
        for anchor in anchors:
            new_id = ids.unique(element_id(ids.standard_id, f"Anchor-{ids.next('anchor'):04d}"))
            ids.id_map[str(anchor["id"])] = new_id
            anchor["id"] = new_id


def apply_element_ids(ssir: dict[str, Any]) -> tuple[list[str], list[str]]:
    """对既有 SSIR 产物确定性回放 TDRS 元素标识（AGENTS.md §0.4：先规则后数据）。

    标准标识取自 ``metadata.standard.standardNumber``（转义），缺失时沿用现有 ``id``。
    返回 ``(重号登记, 回退登记)``；幂等：二次执行逐字节相同。
    """
    standard_number = ""
    metadata = ssir.get("metadata") or {}
    if isinstance(metadata.get("standard"), dict):
        standard_number = str(metadata["standard"].get("standardNumber") or "")
    standard_id = escape_standard_number(standard_number) or str(ssir.get("id") or "")
    ids = _ElementIds(standard_id)
    ssir["id"] = standard_id
    assign_element_ids(
        ids,
        ssir["structuralRoot"],
        [("table", ssir.get("tables") or [], "Table"),
         ("figure", ssir.get("figures") or [], "Figure"),
         ("formula", ssir.get("formulas") or [], "Formula"),
         ("unknown", ssir.get("unknownContents") or [], "Unknown")],
        notes=ssir.get("notes") or None,
    )
    canonical = ssir.get("canonicalText")
    if isinstance(canonical, dict):
        canonical["id"] = element_id(standard_id, "Canonical")
        canonical["sourceElementRefs"] = [
            ids.id_map.get(ref, ref) for ref in canonical.get("sourceElementRefs") or []
        ]
    for run in ssir.get("processingRuns") or []:
        run["id"] = element_id(standard_id, "ProcessingRun_19700101-001")
    for quality in ssir.get("qualityAssessments") or []:
        quality["id"] = element_id(standard_id, "QualityAssessment_M1")
        quality["documentId"] = standard_id
        if quality.get("runId"):
            quality["runId"] = element_id(standard_id, "ProcessingRun_19700101-001")
        if quality.get("unresolvedFigures"):
            quality["unresolvedFigures"] = [
                ids.id_map.get(ref, ref) for ref in quality["unresolvedFigures"]
            ]
    return ids.collisions, ids.fallbacks


def _slug(value: str) -> str:
    value = value.replace("—", "-").replace("–", "-")
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return value or "document"


def _is_annex_heading(text: str) -> bool:
    return bool(re.match(r"^附\s*录\s*[A-Z]", text.strip()))


# 声明型指令的条目**结构化**（判据单源在 parser：DECLARATION_ITEM_RES；此处只做字段切分）：
# 图例 `1——气隙；`、分图题注 `a）局部图`、式中解释 `$η$——传动效率；`。不匹配判据的行
# 整行保留在 text 字段（不猜、不丢，供人工复核）。
def _declaration_items(kind: str, text: str) -> list[dict[str, Any]]:
    pattern = DECLARATION_ITEM_RES[kind]
    items: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = pattern.match(line)
        if not match:
            items.append({"text": line})
            continue
        item: dict[str, Any] = {key: value for key, value in match.groupdict().items() if value}
        if kind == "formula-vars" and item.get("definition"):
            unit = re.search(r"单位为(.+?)[。;；]?$", item["definition"])
            if unit:
                item["unit"] = unit.group(1).strip()
        items.append(item)
    return items


# 声明型指令（docs/15 §2.2）：消费为元素字段，不产生内容元素
DECLARATION_BLOCK_KINDS = {"figure-legend", "figure-sub", "formula-vars", "toc"}
# Note.kind 合法枚举（schema `Note.kind`；声明的 kind 值超出此集合即回退缺省并登记）
_NOTE_KINDS = {"clause", "table", "figure", "term", "example"}


# 列表组类别（docs/15 §3.x `ListGroup.kind`；取值沿用 schema 既有词表 dash/enumerated/
# lettered/roman/other）：全项 marker 同类才判定，混合即留空（不猜）。
_LIST_GROUP_KINDS = {
    "bullet": "dash",
    "numeric": "enumerated",
    "lowerAlpha": "lettered",
    "upperAlpha": "lettered",
}


def _list_kind(items: list[dict[str, Any]]) -> str | None:
    mapped = {_LIST_GROUP_KINDS.get(str(item.get("markerType") or "")) for item in items}
    if len(mapped) == 1 and None not in mapped:
        return mapped.pop()
    return None


def _item_token(marker: str, index: int) -> str:
    """列表项标识后缀（TDRS §五 项）：``a）`` → ``a``、``1)`` → ``1``。

    无字母/数字 marker（破折号、间隔号、圆点）按项序号 ``Item N``——标准里这些
    marker 不携带编号，用序号保证标识确定且不丢项。
    """
    value = marker.strip().rstrip(")）").strip()
    if re.fullmatch(r"[A-Za-z0-9]+", value):
        return value.lower() if value.isalpha() else value
    return f"Item{index}"


# 术语行判据（中文术语/拉丁缩写术语 + 间隙 + 英文对应词）定义在 parser.term_entry_pair，
# 与 CSM-OCR-003 的间隙归一、CSM-OCR-007 的条目形态归一同一份字符类——曾经这里各写一份
# 更窄的（术语限纯汉字串、英文对应词不含逗号），于是「SI词头　SI prefix」与「国际单位制
#　International System of Units, SI」抽不出 term/englishTerm（GB_3100-2026 3.13/3.8）。


def _marker_type(marker: str) -> str:
    value = marker.rstrip(")）")
    if marker in {"-", "*", "+"}:
        return "bullet"
    if value.isdigit():
        return "numeric"
    if value.isalpha() and value.islower():
        return "lowerAlpha"
    if value.isalpha() and value.isupper():
        return "upperAlpha"
    return "other"


@dataclass
class _BuilderState:
    document: CSMDocument
    document_id: str
    source_id: str
    counters: dict[str, int]
    tables: list[dict[str, Any]]
    figures: list[dict[str, Any]]
    formulas: list[dict[str, Any]]
    unknown_contents: list[dict[str, Any]]
    canonical_parts: list[str]
    canonical_refs: list[str]
    unresolved_figures: list[str]
    # 公式 id → 创建时的（框, 并列组）作用域（GEN-128）：「式中」组的显式声明 id 必须与
    # 结构位置处同一作用域，跨作用域的声明按结构位置归属。
    formula_scopes: dict[str, tuple[int | None, int | None]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # TDRS 元素标识（见 docs/16 §10）：document_id 即标准标识（{标准号转义}），
        # 元素标识 = document_id#条款路径。
        self.ids = _ElementIds(self.document_id)
        # 声明型指令（图例/分图题注/式中解释）按 `figure=`/`formula=` 属性（或最近一元素）
        # 归属；无法归属时如实登记，不猜、不丢。
        self.figures_by_directive: dict[str, dict[str, Any]] = {}
        self.formulas_by_directive: dict[str, dict[str, Any]] = {}
        self.declaration_issues: list[str] = []
        # 目次条目（docs/15 §3.9；TDRS 命名：`{文档标识}#Contents_N`）：声明型指令产出，
        # 不落文本流，故与内容元素分开登记。
        self.toc_entries: list[dict[str, Any]] = []
        # 注登记（`ssir:note` 声明；docs/15 §3.6）：只登记声明过的注，未声明的注保持现状。
        self.notes_registry: list[dict[str, Any]] = []
        # 元素标识 → 元素（**改写前**的传统 id）：脚注锚点归属需要在树上按 id 反查
        # 锚点元素是表/图还是条款（docs/15 §2：anchorKind = tableCell / figurePart / page）。
        self.elements_by_id: dict[str, dict[str, Any]] = {}
        # 表/图引用的角标标签（内容元素 id → [标签]）：延迟到脚注注册完成后解析成
        # **注的标识**（TDRS 引用），因为表处理时对应的脚注定义还没登记（表在定义之前）。
        self.pending_note_refs: dict[str, list[str]] = {}

    def next(self, name: str) -> int:
        self.counters[name] += 1
        return self.counters[name]

    def anchor(self, block: Block, suffix: str | None = None) -> dict[str, Any]:
        number = self.next("anchor")
        source_block_id = None
        if block.directive:
            source_block_id = block.directive.attrs.get("id")
        if suffix:
            source_block_id = f"{source_block_id or block.kind}:{suffix}"
        anchor: dict[str, Any] = {
            "id": element_id(self.document_id, f"Anchor-{number:04d}"),
            "sourceFileId": self.source_id,
            "anchorType": "markdown",
            "markdownStartLine": block.start_line,
            "markdownEndLine": block.end_line,
            "markdownNodePath": f"md:{block.kind}:{block.start_line}",
        }
        if source_block_id:
            anchor["sourceBlockId"] = source_block_id
        return anchor


class SSIRBuilder:
    """Convert the constrained CSM AST into the SSIR v0.4 object graph."""

    def build(self, document: CSMDocument) -> dict[str, Any]:
        metadata = document.metadata
        identifier = str(metadata["document-identifier"])
        # 文档标识 = 标准标识（TDRS §一 标准号转义）：GB/T 1.1—2020 → GB_T_1.1-2020。
        # 取不到标准号时回退到文档标识的 slug（非标准文档/夹具）。
        standard_id = escape_standard_number(
            str(metadata.get("standard-number") or identifier or "")
        ) or _slug(identifier)
        document_id = standard_id
        source_id = f"src:{document.sha256[:16]}"
        state = _BuilderState(
            document=document,
            document_id=document_id,
            source_id=source_id,
            counters=defaultdict(int),
            tables=[],
            figures=[],
            formulas=[],
            unknown_contents=[],
            canonical_parts=[],
            canonical_refs=[],
            unresolved_figures=[],
        )

        root: dict[str, Any] = {
            "id": element_id(document_id, "Root"),
            "logicalId": "Root",
            "nodeType": "document",
            "sortOrder": 0,
            "children": [],
        }
        stack: list[tuple[int, dict[str, Any]]] = [(0, root)]
        node_sort = 0
        content_sort: dict[str, int] = defaultdict(int)
        doc_title = str(metadata.get("title") or "").strip()
        # 术语和定义章（术语条目识别：CSM-OCR-003/GB-T 术语中英文两项元数据）。
        in_terms = False
        pending_term: dict[str, Any] | None = None
        # 合并形态术语条目（3.1.2 标准　standard）等待首个定义段打 termDefinition
        pending_def: dict[str, Any] | None = None
        chapter_re = re.compile(r"^\d+\s+\S")
        term_number_re = re.compile(r"^\d+(?:\.\d+)+$")

        marker_nodes: dict[str, str] = {}  # 脚注标记 label → 出现所在条款节点 id
        # 同上，但按**所在节点**分层（node id → label → 锚点标识）：标签跨表/跨章会重号
        # （Annex E 的图注 `a` 与第 9 章某表的 `a` 同名），全局表会把远处的表当成锚点
        # （2026-09-23 GEN-124：跨节点误配）。解析时只在**自身节点及其祖先**内查。
        node_markers: dict[str, dict[str, str]] = {}
        # ssir:box 显式文档框（2026-09-08）：开/关事件在块流上推进，当前打开的
        # 框 id（从 1 起单调递增）与样式挂到其后的每个结构节点/内容元素上；
        # 嵌套开（parser 已报 CSM-STRUCT-006）在此忽略，与宽容解析语义一致。
        active_box: int | None = None
        active_box_style: str = "frame"
        # 附录作用域（2026-09-12）：当前附录节点 + 其内附录条链（点数, 节点），
        # 供附录条按字母归位（不依赖层级栈，见 heading 分支）。
        current_annex: dict[str, Any] | None = None
        annex_chain: list[tuple[int, dict[str, Any]]] = []
        # ssir:columns 显式并列声明（2026-09-11）：开标记推进当前并列组，column
        # 事件推进列序号，其间的每个内容元素写入 sideBySideGroup/sideBySideColumn
        # （渲染为同一行内的无边框定位容器）。组宽比随内容元素下发。
        active_columns: int | None = None
        active_column: int = 0
        active_columns_widths: list[float] | None = None
        for block in document.blocks:
            if block.kind == "columns":
                event = block.data.get("event")
                if event == "open" and active_columns is None:
                    active_columns = state.counters["columns"] + 1
                    state.counters["columns"] = active_columns
                    active_column = 0
                    active_columns_widths = block.data.get("widths")
                elif event == "column":
                    if active_columns is not None:
                        active_column += 1
                elif event == "close":
                    active_columns = None
                    active_column = 0
                    active_columns_widths = None
                state.canonical_parts.append(block.text)
                continue
            if block.kind == "box":
                if block.data.get("event") == "open" and active_box is None:
                    active_box = (state.counters["box"] + 1)
                    state.counters["box"] = active_box
                    active_box_style = str(block.data.get("style") or "frame")
                elif block.data.get("event") == "close":
                    active_box = None
                    active_box_style = "frame"
                state.canonical_parts.append(block.text)
                continue
            if block.kind == "heading":
                # The document title is the sole H1 that is not a structural
                # node.  MinerU commonly emits annex starts as later H1s.
                if block.level == 1 and not _is_annex_heading(block.text):
                    state.canonical_parts.append(block.text)
                    continue
                heading_text = block.text.strip()
                # 正文首页标题重复：MinerU 把正文首页的标准名称也抽成 ## 标题，
                # 其文本与文档标题相同，不应作为章节节点（否则引言末尾多出
                # 一个标准名称且进入目次）。
                if (block.level or 0) >= 2 and heading_text == doc_title:
                    state.canonical_parts.append(block.text)
                    continue
                node = self._make_node(state, block, node_sort)
                node_sort += 1
                if active_box is not None:
                    node["box"] = active_box
                    node["boxStyle"] = active_box_style
                depth = max((block.level or 2) - 1, 1)
                node_type = node.get("nodeType")
                node_number = str(node.get("number") or "")
                if node_type == "documentBlock" and not node_number and str(node.get("title") or "").replace(" ", "") in {
                    "参考文献", "索引", "前言", "引言", "目次", "封面"
                }:
                    # 文后/前置要素：退出附录作用域，其后同名编号不再归入上一个附录。
                    current_annex = None
                    annex_chain = []
                    while stack and stack[-1][0] >= depth:
                        stack.pop()
                    parent = stack[-1][1] if stack else root
                elif node_type == "annex":
                    # 附录容器挂根级；记录当前附录，供其下附录条按字母归位。
                    while stack and stack[-1][0] >= depth:
                        stack.pop()
                    parent = stack[-1][1] if stack else root
                    current_annex = node
                    annex_chain = []
                elif (
                    node_type == "annexSection"
                    and current_annex is not None
                    and node_number.split(".")[0] == str(current_annex.get("number") or "")
                ):
                    # 附录条父节点由附录字母决定，不取层级栈——模型示例（GB_T_20001
                    # 系列）的章节标题与其同级，按层级会把附录条挂到示例章节之下。
                    dots = node_number.count(".")
                    while annex_chain and annex_chain[-1][0] >= dots:
                        annex_chain.pop()
                    parent = annex_chain[-1][1] if annex_chain else current_annex
                    annex_chain.append((dots, node))
                    while stack and stack[-1][0] >= depth:
                        stack.pop()
                elif (
                    current_annex is not None
                    and node_type == "documentBlock"
                    and EX_HEADER_RE.match(str(node.get("title") or "").strip())
                    and int(node.get("level") or 1)
                    > int((annex_chain[-1][1] if annex_chain else current_annex).get("level") or 1)
                ):
                    # 附录内的**简单示例**（parser CSM-OCR-008 已提升到所属附录条/
                    # 附录之下）：中间可能夹着示例内容里误升的无编号标题（如
                    # GB_T_1.1-2020 示例2 的「##    多刃刀片 …」），层级栈会被它弹出，
                    # 故按附录作用域直接归位。**模型示例**未被提升（层级不深于附录条），
                    # 不满足本分支，保持扁平示例文档模型。
                    parent = annex_chain[-1][1] if annex_chain else current_annex
                    while stack and stack[-1][0] >= depth:
                        stack.pop()
                else:
                    while stack and stack[-1][0] >= depth:
                        stack.pop()
                    parent = stack[-1][1] if stack else root
                parent.setdefault("children", []).append(node)
                stack.append((depth, node))
                state.canonical_parts.append(block.text)
                # 术语章/术语条目状态机（扁平树：3.1、3.2 与文档块都是根级兄弟）
                if chapter_re.match(heading_text) and "术语" in heading_text:
                    in_terms = True
                    pending_term = None
                    pending_def = None
                elif chapter_re.match(heading_text):
                    in_terms = False
                    pending_term = None
                    pending_def = None
                elif in_terms and term_number_re.match(str(node.get("number") or "")):
                    # 裸术语节（3.1，title=""）：期待紧随的术语行（段落或文档块标题）；
                    # 已合并形态（3.1.2 标准　standard，标题即术语行）直接取 term 字段。
                    pending_term = node
                    pair = term_entry_pair(str(node.get("title") or ""))
                    if pair:
                        node["term"] = pair[0]
                        node["englishTerm"] = pair[1]
                        pending_term = None
                        pending_def = node
                    else:
                        pending_def = None
                else:
                    # 文档块/子条：若是术语行的标题形态（3.2 + "功能function"）
                    if pending_term is not None and node.get("nodeType") in ("documentBlock", "clause", "subClause", "item", "subItem"):
                        title = str(node.get("title") or "").strip()
                        pair = term_entry_pair(title)
                        if pair:
                            pending_term["term"] = pair[0]
                            pending_term["englishTerm"] = pair[1]
                    pending_term = None
                    pending_def = None
                continue

            parent = stack[-1][1] if stack else root
            parent_id = parent["id"]
            if self._apply_declaration(state, block, box=active_box, columns=active_columns):
                # 声明型指令（图例/分图题注/式中解释组）不产生内容元素，只补目标元素字段。
                continue
            element = self._make_content(state, block, parent_id, content_sort[parent_id])
            content_sort[parent_id] += 1
            if active_box is not None:
                element["box"] = active_box
                element["boxStyle"] = active_box_style
            if active_columns is not None:
                element["sideBySideGroup"] = f"columns-{active_columns}"
                element["sideBySideColumn"] = active_column
                if active_columns_widths:
                    element["sideBySideWidths"] = list(active_columns_widths)
            if element.get("presentationType") == "formula":
                # 公式所属（框, 并列组）作用域：供「式中」声明的跨作用域校验（GEN-128）。
                state.formula_scopes[str(element["formulaRef"])] = (active_box, active_columns)
            if element.get("presentationType") == "list":
                self._resolve_list_group(element, parent)
            parent.setdefault("contentElements", []).append(element)
            state.canonical_refs.append(element["id"])
            state.canonical_parts.append(self._canonical_fragment(block))
            state.elements_by_id[element["id"]] = element
            # 脚注关系：正文元素中出现的 [^N] 记录其所属条款节点；脚注定义元素
            # 据此写入 footnoteMarker / footnoteAnchorRef（本体层可做 脚注-条款 关系）。
            # 2026-09-22（图表脚注锚点）：引用点扫描扩展到**表内/图内文本**（元素自身的
            # canonical 片段），并让表/图元素成为锚点——否则表内 `[foot:a]` 看不见，
            # 脚注一律挂到条款节点，渲染端无法区分图表脚注与条文脚注（GB/T 1.1 9.12.2）。
            citations = self._footnote_citations(state, element)
            if element.get("presentationType") in {"table", "figure"} and citations:
                for label in citations:
                    marker_nodes[label] = element["id"]
                    node_markers.setdefault(parent_id, {})[label] = element["id"]
                state.pending_note_refs[element["id"]] = sorted(set(citations))
            else:
                for label in citations:
                    marker_nodes.setdefault(label, parent_id)
                    node_markers.setdefault(parent_id, {}).setdefault(label, parent_id)
            text_content = str(element.get("textContent") or "")
            if element.get("presentationType") == "footnote":
                label = str(block.data.get("label") or "")
                if not label:
                    match = re.match(r"^(\d+)[)）]", text_content)
                    if match:
                        label = match.group(1)
                element.setdefault("footnoteMarker", label)
                anchor_chain = [entry[1]["id"] for entry in reversed(stack)] or [parent_id]
                element["footnoteAnchorRef"] = SSIRBuilder._footnote_anchor(
                    parent, element, label, anchor_chain, node_markers, marker_nodes
                )
                self._register_footnote_note(state, element, label)
            # 合并形态术语条目：紧随标题的首个正文段即定义（来源行 [来源：…] 除外）
            if pending_def is not None and parent is pending_def:
                raw_text = str(element.get("textContent") or "").strip()
                if raw_text and not raw_text.startswith("["):
                    element.setdefault("semanticTypes", []).append("termDefinition")
                    pending_def = None
                elif not raw_text:
                    pass  # 空段/非文本元素：继续等下一个正文段
            # 术语行的段落形态（3.1 + "规范标准 specification standard"）
            if pending_term is not None and parent is pending_term:
                text = str(element.get("textContent") or "")
                pair = term_entry_pair(text)
                if pair:
                    pending_term["term"] = pair[0]
                    pending_term["englishTerm"] = pair[1]
                    element.setdefault("semanticTypes", []).append("termDefinition")
                pending_term = None

        # 元素标识改写（TDRS）：树与注册表定稿后统一改写为 ``{标准标识}#{条款路径}``
        # （条款路径需附录/父链上下文，故在整树构建完成后一次性确定）。
        self._assign_element_ids(state, root)

        common: dict[str, Any] = {
            "documentIdentifier": identifier,
            "title": str(metadata["title"]),
            "language": str(metadata.get("language", "zh-CN")),
        }
        for source_key, target_key in (("title-en", "titleEn"), ("conformity-statement", "conformityStatement"), ("publication-date", "publicationDate"), ("effective-date", "effectiveDate"), ("issuer", "issuer")):
            if metadata.get(source_key):
                common[target_key] = str(metadata[source_key])
        standard: dict[str, Any] = {
            "standardNumber": str(metadata["standard-number"]),
            "chineseTitle": str(metadata["title"]),
        }
        for source_key, target_key in (("ics", "ics"), ("ccs", "ccs"), ("replaces", "replaces"), ("cover-badge", "coverBadge")):
            if metadata.get(source_key):
                standard[target_key] = str(metadata[source_key])
        document_type = "standard" if metadata.get("document-type") == "standard" else "other"
        run_id = element_id(document_id, "ProcessingRun_19700101-001")
        quality = self._quality_assessment(state, run_id)
        canonical_text = "\n".join(part for part in state.canonical_parts if part).strip()
        ssir: dict[str, Any] = {
            "id": document_id,
            "ssirVersion": "0.4",
            "documentType": document_type,
            "metadata": {"common": common, "standard": standard},
            "sourceFiles": [
                {
                    "id": source_id,
                    "fileName": document.path.name,
                    "fileHash": {"algorithm": "SHA-256", "value": document.sha256},
                    "fileSize": len(document.text.encode("utf-8")),
                    "mimeType": "text/markdown",
                }
            ],
            "canonicalText": {
                "id": element_id(document_id, "Canonical"),
                "text": canonical_text,
                "normalizationPolicy": "ssir-canonical-text-v1",
                "sourceElementRefs": state.canonical_refs,
                "version": "1",
            },
            "structuralRoot": root,
            "tables": state.tables,
            "figures": state.figures,
            "formulas": state.formulas,
            "unknownContents": state.unknown_contents,
            "processingRuns": [
                {
                    "id": run_id,
                    "sourceFileId": source_id,
                    "runType": "extraction",
                    "tool": "leleby-csm-parser",
                    "toolVersion": "0.1.0",
                    "ocrUsed": False,
                    "timestamp": "1970-01-01T00:00:00Z",
                    "configuration": {"csmVersion": "1.0"},
                }
            ],
            "qualityAssessments": [quality],
            "preservationLevel": "Level3",
            "createdAt": "1970-01-01T00:00:00Z",
        }
        if state.toc_entries:
            # 目次条目（docs/15 §3.9）：仅在文档含 ssir:toc 声明时输出——既有产物无此声明，
            # 保持与迁移前基线结构等价。
            ssir["tocEntries"] = state.toc_entries
        if state.notes_registry:
            # 注登记（docs/15 §3.6）：仅在文档含 ssir:note 声明时输出，同样保持结构等价。
            self._resolve_note_refs(state)
            ssir["notes"] = state.notes_registry
        self._mark_annex_examples(root)
        return ssir

    @staticmethod
    def _mark_annex_examples(root: dict[str, Any]) -> None:
        """Mark example-internal content inside annexes (CSM-OCR-006 / GBT-B05).

        GB/T 20001 系列附录里的编写示例（表框/图框内容）自带编号体系
        （如「4 技术要求」「5 试验方法」），这些编号不是本标准的真实章条，
        不应与正文编号混淆：合规编号检查、目次与渲染器据此排除/特殊处理。
        规则：在附录（或附录小节 A.x）内，无编号标题（示例文档标题，如
        「1 000 kV 变电站监控系统 技术规范」「示例1：」）之后出现的编号
        标题及其子树都属于示例内容；附录小节（A.1/A.2…）本身是真实标题。
        该标记仅附加在 SSIR 节点上，csm_renderer 仍按标题序列化，
        canonical 不受影响。
        """
        annex_section_re = re.compile(r"^[A-Z](?:\.\d+)*\s")

        def visit(nodes: list[dict[str, Any]], in_annex: bool = False, example_active: bool = False) -> None:
            for node in nodes:
                if node.get("nodeType") == "annex":
                    # 嵌套树：附录 children 即附录内容。扁平树（MinerU 全 ## 抽取，
                    # 附录无 children，示例内容是其后继兄弟）：保持 in_annex 状态
                    # 让同一列表的后续节点按附录内容处理，直到下一个 annex 节点。
                    visit(node.get("children", []), True, False)
                    in_annex = True
                    example_active = False
                    continue
                if not in_annex:
                    visit(node.get("children", []), False, False)
                    continue
                number = str(node.get("number") or "").strip()
                title = str(node.get("title") or "").strip()
                # 扁平树（MinerU 全 ## 抽取）中，最后一个附录之后的文档级要素
                # （参考文献/索引/目次/前言/引言）不是附录内容：遇到即退出附录
                # 模式，防止文后要素被误标为示例内容（GB_T_1.1-2020 曾把参考
                # 文献/索引起始块标成 exampleContent，渲染器将其整体打包成
                # 示例框并崩溃）。
                if not number and title.replace(" ", "") in {"参考文献", "索引", "目次", "前言", "引言"}:
                    visit(node.get("children", []), False, False)
                    in_annex = False
                    example_active = False
                    continue
                if not number:
                    if annex_section_re.match(title):
                        # 附录小节（A.1 产品规范标准编写示例）——真实标题，结束示例块。
                        visit(node.get("children", []), True, False)
                        example_active = False
                    else:
                        # 无编号标题 = 示例文档标题（示例1：/ 示例文档名），开始示例块。
                        node["exampleContent"] = True
                        visit(node.get("children", []), True, True)
                        example_active = True
                    continue
                if re.match(r"^[A-Z](?:\.\d+)*$", number):
                    # 带编号的附录小节（A.1 / A.2），结束示例块。
                    visit(node.get("children", []), True, False)
                    example_active = False
                elif example_active:
                    node["exampleContent"] = True
                    visit(node.get("children", []), True, True)
                else:
                    visit(node.get("children", []), True, False)

        visit(root.get("children", []))

    def _make_node(self, state: _BuilderState, block: Block, sort_order: int) -> dict[str, Any]:
        title = block.text
        number: str | None = None
        node_type = "documentBlock"
        # Clamp to >= 1: the CSM renderer maps levels back to Markdown
        # headings via max(level + 1, 2), so a level of 0 would render as an
        # H2 and re-parse as level 1 — breaking SSIR round-trip equivalence.
        level = max(block.level - 1, 1) if block.level else 1
        # Accept an optional separator before the status marker; the renderer emits
        # the compact GB/T form, while user Markdown sometimes contains a space.
        annex = re.match(r"^附\s*录\s*([A-Z])\s*(?:[(（](规范性|资料性|未判定|推荐性)[)）])?\s*(.*)$", title)
        pure_numbered = re.match(r"^(\d+(?:\.\d+)*)$", title)
        # 编号后必须接汉字/字母/括号，不能接数字："1 000 kV 变电站监控系统 技术规范"
        # 的 "1 000" 是名称本身（一千伏），不是章号 "1"（GEN-031 层次编号规范化）。
        numbered = re.match(r"^(\d+(?:\.\d+)*)(?:\s+)?(?=[\u4e00-\u9fffA-Za-z（(])(.+)$", title)
        # 附录条（`B.1`/`B.6.1`，GB/T 1.1-2020 9.6.2/10.4.1）：附录大写字母 + 点分
        # 数字链。段数决定层级（parser CSM-OCR-006 已按其提升 heading 级别），
        # 节点类型为数据模型定义的 annexSection（附录内的章/条）。缺此分支时标题
        # 连同编号落进 documentBlock、层级停留在附录同级 → 附录无子节点。
        annex_section = re.match(r"^([A-Z]\.\d+(?:\.\d+)*)(?:\s+)?(?=[\u4e00-\u9fffA-Za-z（(])(.+)$", title)
        annex_section_pure = re.match(r"^([A-Z]\.\d+(?:\.\d+)*)$", title)
        if annex:
            number = annex.group(1)
            # Annex status is normative information, so retain it in the schema's title field.
            status = annex.group(2)
            title = f"（{status}） {annex.group(3)}".rstrip() if status else annex.group(3).strip()
            node_type = "annex"
        elif annex_section or annex_section_pure:
            match = annex_section or annex_section_pure
            number = match.group(1)
            title = (match.group(2).strip() if annex_section else "")
            node_type = "annexSection"
        elif numbered:
            number = numbered.group(1)
            title = numbered.group(2)
            node_type = {2: "section", 3: "clause", 4: "subClause", 5: "item", 6: "subItem"}.get(block.level or 2, "clause")
        elif pure_numbered:
            number = pure_numbered.group(1)
            title = ""
            node_type = {2: "section", 3: "clause", 4: "subClause", 5: "item", 6: "subItem"}.get(block.level or 2, "clause")
        elif EX_HEADER_RE.match(title):
            # 示例框标题（「示例：」「示例N：」）是内容块节点。正文示例经
            # parser CSM-OCR-008 提升到所在条款层级 +1（block.level 3~6）后，
            # 仍必须保持 documentBlock 语义——不能落入下面 level>=3 的
            # clause/subClause/item/subItem 映射（节点类型影响渲染/树语义）。
            node_type = "documentBlock"
        elif block.level and block.level >= 3:
            node_type = {3: "clause", 4: "subClause", 5: "item", 6: "subItem"}.get(block.level, "clause")
        logical = _slug(number or title)
        index = state.next("node")
        node: dict[str, Any] = {
            "id": f"{state.document_id}/{node_type}-{logical}-{index:03d}",
            "logicalId": f"{node_type}-{logical}",
            "nodeType": node_type,
            "level": level,
            "title": title,
            "sourceAnchors": [state.anchor(block)],
            "sortOrder": sort_order,
        }
        if number:
            node["number"] = number
        return node

    def _apply_declaration(
        self,
        state: _BuilderState,
        block: Block,
        *,
        box: int | None = None,
        columns: int | None = None,
    ) -> bool:
        """声明型指令 → 目标元素字段（不产生内容元素）。返回是否已消费该块。

        归属规则（docs/15 §3.7/§3.8）：优先 `figure=`/`formula=` 指定的元素标识；
        缺省取**最近一个**图/公式（声明紧随其后是常态）。无法归属时记 issue，不猜。
        """
        if block.kind not in DECLARATION_BLOCK_KINDS:
            return False
        attrs = block.directive.attrs if block.directive else {}
        if block.kind == "toc":
            for entry in _declaration_items("toc", block.text):
                title = entry.get("title") or entry.get("text") or ""
                record: dict[str, Any] = {
                    "id": element_id(state.document_id, f"Contents_{len(state.toc_entries) + 1}"),
                    "title": title,
                }
                number_match = TOC_NUMBER_RE.match(title)
                if number_match:
                    record["number"] = number_match.group("number")
                    record["title"] = number_match.group("rest").strip() or title
                if entry.get("page"):
                    record["sourcePageLabel"] = entry["page"]
                state.toc_entries.append(record)
            return True
        if block.kind == "formula-vars":
            key = str(attrs.get("formula") or "")
            declared = state.formulas_by_directive.get(key)
            nearest = state.formulas[-1] if state.formulas else None
            formula = declared or nearest
            # GEN-128：显式声明的公式若**不在同一（框, 并列组）作用域**内，说明声明指向的是
            # 别处的公式（GB_T_1.1-2020 9.9.3.1：示例 4 的组误声明了示例 3 的公式 id）——
            # 「式中」组解释的永远是**结构上紧邻其前**的公式，故按结构位置归属并如实登记，
            # 不静默跟随错误声明。
            if declared is not None and declared is not nearest and nearest is not None:
                if state.formula_scopes.get(str(declared["id"])) != (box, columns):
                    state.declaration_issues.append(
                        f"ssir:formula-vars formula={key!r} 指向的公式不在同一框/并列作用域，"
                        f"按结构位置归属到 {nearest['id']!r}"
                    )
                    formula = nearest
            if formula is None:
                state.declaration_issues.append(
                    f"ssir:formula-vars 找不到目标公式（formula={key!r}）"
                )
                return True
            existing = formula.get("explanationGroup") or {}
            # 同一公式可有多个「式中」组（分段解释）：条目**累积**，不覆盖。
            formula["explanationGroup"] = {
                "items": list(existing.get("items") or [])
                + _declaration_items("formula-vars", block.text)
            }
            return True
        key = str(attrs.get("figure") or "")
        figure = state.figures_by_directive.get(key) or (state.figures[-1] if state.figures else None)
        if figure is None:
            state.declaration_issues.append(
                f"ssir:{block.kind} 找不到目标图（figure={key!r}）"
            )
            return True
        if block.kind == "figure-legend":
            figure.setdefault("legend", []).extend(_declaration_items("figure-legend", block.text))
        else:
            figure.setdefault("subCaptions", []).extend(_declaration_items("figure-sub", block.text))
        return True

    def _register_note(
        self, state: _BuilderState, block: Block, content: dict[str, Any], parent_id: str
    ) -> None:
        """`ssir:note` 声明的注 → `notes[]` 结构化登记（docs/15 §3.6）。

        文本仍在内容元素里（单一来源），此处只登记归属元数据：ownerRef / scope / kind /
        label；缺省归属为所在节点（parent_id）。声明未给出的字段不猜。
        """
        attrs = block.directive.attrs if block.directive else {}
        # Note.kind 枚举为 clause/table/figure/term/example：块类型 → 缺省归属类别，
        # 声明显式给出的 kind 仅在其为合法枚举值时生效；非法值回退缺省并如实登记。
        default_kind = "example" if block.kind == "example" else "clause"
        declared_kind = str(attrs.get("kind") or "").strip()
        note_kind = default_kind
        if declared_kind:
            if declared_kind in _NOTE_KINDS:
                note_kind = declared_kind
            else:
                state.declaration_issues.append(
                    f"ssir:note kind={declared_kind!r} 不在 {sorted(_NOTE_KINDS)} 内，按 {default_kind!r} 登记"
                )
        note: dict[str, Any] = {
            "id": element_id(state.document_id, f"Note_{len(state.notes_registry) + 1}"),
            "type": "note",
            "kind": note_kind,
        }
        for key, target in (("label", "label"), ("scope", "scope")):
            if attrs.get(key):
                note[target] = attrs[key]
        note["ownerRef"] = attrs.get("owner") or parent_id
        note["contentRef"] = content.get("id") or parent_id
        state.notes_registry.append(note)

    def _footnote_citations(self, state: _BuilderState, element: dict[str, Any]) -> list[str]:
        """元素上的脚注引用标签（`[foot:L]`），**含表内/图内文本**。

        正文判据看 `textContent`；表/图的引用点写在**单元格与图题/图例**里，而这些
        内容元素的 `textContent` 为空，故同时扫描该元素自身的 canonical 片段。两者用
        同一个 `_FOOTNOTE_REF_RE`（引用点语法），不是按文本形状猜测。
        """
        texts = [str(element.get("textContent") or "")]
        if state.canonical_parts:
            texts.append(state.canonical_parts[-1])
        labels: list[str] = []
        for text in texts:
            labels.extend(footnote_citations(text))
        return labels

    @staticmethod
    def _adjacent_figure_anchor(parent: dict[str, Any], element: dict[str, Any]) -> str | None:
        """结构上紧贴本脚注定义的**图**元素（GEN-124）：前邻优先，回跳连续的脚注兄弟。

        图注编号常直接画在图内（无文本引用点），此时锚点只能按结构取——定义紧贴哪张图，
        就是哪张图的图下脚注（GB/T 1.1 9.12.2）。前后都没有图则返回 None（不猜）。
        """
        items = parent.get("contentElements") or []
        try:
            index = items.index(element)
        except ValueError:
            return None
        for step in (-1, +1):
            position = index + step
            while 0 <= position < len(items):
                neighbour = items[position]
                kind = neighbour.get("presentationType")
                if kind == "figure":
                    return str(neighbour.get("id") or "") or None
                if kind != "footnote":
                    break
                position += step
        return None

    @staticmethod
    def _footnote_anchor(
        parent: dict[str, Any],
        element: dict[str, Any],
        label: str,
        chain: list[str],
        node_markers: dict[str, dict[str, str]],
        marker_nodes: dict[str, str],
    ) -> str:
        """脚注定义的锚点标识（docs/15 §2；2026-09-23 GEN-124）。

        ① **本节点及祖先**内该标签的引用点（表/图元素 → 该元素，条款节点 → 该节点）；
        ② 无引用点（编号只出现在图内等）→ 结构上紧贴的**图**元素（`figurePart`）；
        ③ 都没有 → 所在条款节点（`anchorKind=page`，与迁移前一致）。
        """
        for node_id in chain:
            anchor = node_markers.get(node_id, {}).get(label)
            if anchor:
                return anchor
        return SSIRBuilder._adjacent_figure_anchor(parent, element) or marker_nodes.get(label, parent["id"])

    @staticmethod
    def _citation_target(state: _BuilderState, element: dict[str, Any]) -> dict[str, Any] | None:
        """表/图内容元素对应的本体对象（`tables[]` / `figures[]` 里的那一条）。"""
        ref = element.get("tableRef") or element.get("figureRef")
        if not ref:
            return None
        for collection in (state.tables, state.figures):
            for item in collection:
                if item.get("id") == ref:
                    return item
        return None

    def _register_footnote_note(
        self, state: _BuilderState, element: dict[str, Any], label: str
    ) -> None:
        """脚注定义 → `notes[]` 结构化登记（docs/15 §2：`type=footnote` + `anchorKind`）。

        `anchorKind` 取**锚点元素的种类**（表 → `tableCell`，图 → `figurePart`，其余 →
        `page`），不按标号形状（字母/数字）猜：标号形状不是结构信息。`kind`/`scope` 是
        归属要素类别（clause/table/figure），与锚点同类。
        """
        anchor_id = str(element.get("footnoteAnchorRef") or "")
        anchor_type = (state.elements_by_id.get(anchor_id) or {}).get("presentationType")
        note: dict[str, Any] = {
            "id": element_id(state.document_id, f"Note_{len(state.notes_registry) + 1}"),
            "type": "footnote",
            "kind": {"table": "table", "figure": "figure"}.get(anchor_type, "clause"),
            "anchorKind": {"table": "tableCell", "figure": "figurePart"}.get(anchor_type, "page"),
            "ownerRef": anchor_id or element.get("id"),
            "contentRef": element.get("id"),
        }
        if label:
            note["label"] = label
        state.notes_registry.append(note)

    def _resolve_note_refs(self, state: _BuilderState) -> None:
        """表/图的 `noteRefs` ← **注的标识**（TDRS 引用）。

        标签跨表会重号（两个表各有 a、b），故按 `ownerRef`（表/图内容元素标识）配准；
        没有对应定义的标签不写（宁缺勿错，docs/15 §2）。解析发生在脚注登记之后，
        写入的是 `notes[]` 里的注标识（已是 TDRS 形态，不参与内容元素标识改写）。
        """
        by_owner: dict[str, dict[str, str]] = {}
        for note in state.notes_registry:
            if note.get("type") != "footnote" or not note.get("label"):
                continue
            by_owner.setdefault(str(note.get("ownerRef") or ""), {})[str(note["label"])] = str(note["id"])
        # 元素的 `id` 字段在 TDRS 标识改写后就地换过（而 elements_by_id 的键仍是登记时的
        # 传统标识）：注的 ownerRef 用的是**改写后**的值，故此处按元素当前 id 配准。
        current_ids = {key: str(el.get("id") or key) for key, el in state.elements_by_id.items()}
        for anchor_key, labels in state.pending_note_refs.items():
            element = state.elements_by_id.get(anchor_key)
            target = self._citation_target(state, element) if element else None
            if target is None:
                continue
            mapping = by_owner.get(current_ids.get(anchor_key, anchor_key), {})
            refs = [mapping[label] for label in labels if label in mapping]
            if refs:
                target["noteRefs"] = refs

    def _resolve_list_group(self, element: dict[str, Any], parent: dict[str, Any]) -> None:
        """列表组 `introRef` 落定（docs/15 §3.x）：引语 = 同节点**前一个**内容元素。

        无前序元素时留空（不猜）。`introRefPending` 是内部占位，绝不进入 SSIR。
        """
        group = element.get("listGroup")
        if not isinstance(group, dict):
            return
        if not group.pop("introRefPending", False):
            return
        siblings = parent.get("contentElements") or []
        if siblings:
            group["introRef"] = siblings[-1]["id"]

    def _make_content(self, state: _BuilderState, block: Block, parent_id: str, sort_order: int) -> dict[str, Any]:
        index = state.next("content")
        content: dict[str, Any] = {
            "id": f"{state.document_id}/content/c-{index:04d}",
            "parentNodeId": parent_id,
            "sortOrder": sort_order,
            "sourceAnchors": [state.anchor(block)],
        }
        if block.kind == "footnote":
            content["presentationType"] = "footnote"
            label = str(block.data.get("label") or "")
            text = str(block.data.get("text") or block.text)
            # 注文行首标记字面按 GB/T 1.1-2020 9.12.1/9.12.2 分族（判据单源
            # `parser.footnote_label_marker`）：条文脚注 `1)`、图表脚注裸小写字母 `a`
            # （**不补右括号**——源版面的标记就是上标裸字母，见 docs/12 §3.84）。
            content["textContent"] = (f"{footnote_label_marker(label)} {text}" if label else text)
        elif block.kind in {"paragraph", "note", "example", "warning", "quote"}:
            content["presentationType"] = block.kind if block.kind != "paragraph" else "paragraph"
            content["textContent"] = block.text
            content["semanticTypes"] = self._semantic_types(parent_id, block.text)
            if block.kind in {"note", "example", "warning"} and block.directive is not None:
                self._register_note(state, block, content, parent_id)
        elif block.kind == "list":
            content["presentationType"] = "list"
            content["listItems"] = []
            for item_index, item in enumerate(block.data["items"]):
                item_block = Block(kind="listItem", start_line=int(item["line"]), end_line=int(item["line"]))
                content["listItems"].append(
                    {
                        "id": f"li-{state.next('list_item'):04d}",
                        "text": item["text"],
                        "marker": item["marker"],
                        "markerType": _marker_type(item["marker"]),
                        "sourceAnchor": state.anchor(item_block),
                        "sortOrder": item_index,
                    }
                )
            group: dict[str, Any] = {}
            kind = _list_kind(content["listItems"])
            if kind:
                group["kind"] = kind
            if block.data.get("intro"):
                group["introRefPending"] = True
            if block.data.get("terminator"):
                group["terminator"] = block.data["terminator"]
            if group:
                content["listGroup"] = group
        elif block.kind == "table":
            content["presentationType"] = "table"
            table = self._table(state, block)
            state.tables.append(table)
            content["tableRef"] = table["id"]
        elif block.kind == "figure":
            content["presentationType"] = "figure"
            figure = self._figure(state, block)
            state.figures.append(figure)
            content["figureRef"] = figure["id"]
        elif block.kind == "formula":
            content["presentationType"] = "formula"
            formula = self._formula(state, block)
            state.formulas.append(formula)
            content["formulaRef"] = formula["id"]
        elif block.kind == "unknown":
            content["presentationType"] = "other"
            unknown = self._unknown(state, block)
            state.unknown_contents.append(unknown)
            content["unknownRef"] = unknown["id"]
        else:
            content["presentationType"] = "paragraph"
            content["textContent"] = block.text
        return content

    @staticmethod
    def _semantic_types(parent_id: str, text: str) -> list[str]:
        lowered = parent_id.lower()
        if "section-1" in lowered or "范围" in text[:20]:
            return ["scope"]
        if "规范性引用" in text[:30]:
            return ["normativeReference"]
        if "试验" in lowered:
            return ["testMethod"]
        if "检验" in lowered:
            return ["inspectionRule"]
        return []

    def _table(self, state: _BuilderState, block: Block) -> dict[str, Any]:
        directive_id = block.directive.attrs.get("id") if block.directive else None
        local_id = _slug(directive_id or f"t-{state.next('table') :03d}")
        rows: list[list[str]] = block.data["rows"]
        header_rows = int(block.directive.attrs.get("header-rows", "1")) if block.directive else 1
        table: dict[str, Any] = {
            "id": f"{state.document_id}/table/{local_id}",
            "rowCount": len(rows),
            "colCount": len(rows[0]) if rows else 0,
            "rows": [],
            "sourceAnchors": [state.anchor(block)],
            "preservationStatus": "preserved",
        }
        if block.directive:
            number = block.directive.attrs.get("caption-number")
            caption = block.directive.attrs.get("caption")
            unit = block.directive.attrs.get("unit")
            if number:
                table["number"] = number
            if caption:
                table["caption"] = caption
            if unit:
                table["unit"] = unit
        for row_index, row in enumerate(rows):
            row_data: dict[str, Any] = {
                "id": f"row-{state.next('row'):04d}",
                "rowIndex": row_index,
                "isHeader": row_index < header_rows,
                "cells": [],
            }
            for col_index, cell in enumerate(row):
                row_data["cells"].append(
                    {
                        "id": f"cell-{state.next('cell'):04d}",
                        "rowIndex": row_index,
                        "colIndex": col_index,
                        "text": cell.replace(r"\|", "|"),
                        "colspan": 1,
                        "rowspan": 1,
                        "isHeader": row_index < header_rows,
                    }
                )
            table["rows"].append(row_data)
        for merge in block.data.get("merges", []):
            try:
                # merge 的 row/column 是**绝对** 0-based 表格坐标（row=0 即第一行——
                # 表头行也算在内；数据行的 row = header-rows + 序号 − 1），与抽取端
                # （mineru_html 按源行号写）和 csm_renderer 的写法同一基准。
                # 旧实现写 `header_rows + row - 1`：header-rows=1 时与绝对值重合，
                # 一旦表头不止一行（GEN-114）就会把合并整体下移一行。
                data_row = int(merge["row"])
                column = int(merge["column"]) - 1
                cell = table["rows"][data_row]["cells"][column]
                cell["rowspan"] = int(merge.get("rowspan", "1"))
                cell["colspan"] = int(merge.get("colspan", "1"))
            except (IndexError, KeyError, ValueError):
                table["preservationStatus"] = "partiallyPreserved"
        return table

    def _figure(self, state: _BuilderState, block: Block) -> dict[str, Any]:
        directive_id = block.directive.attrs.get("id") if block.directive else None
        local_id = _slug(directive_id or f"f-{state.next('figure') :03d}")
        number, caption = figure_caption_parts(block.text)
        figure: dict[str, Any] = {
            "id": f"{state.document_id}/figure/{local_id}",
            "sourceAnchors": [state.anchor(block)],
            "preservationStatus": "preserved",
        }
        if number:
            figure["number"] = number
        if caption:
            figure["caption"] = caption
            figure["altText"] = block.text
        if block.data.get("unit"):
            # 单位陈述行（"单位为毫米"，GEN-032）：与表同型地挂在图节点上，
            # 渲染端右对齐画在图上方并与图同组（分页时不与图分离，见 docs/12 §3.54）。
            figure["unit"] = str(block.data["unit"])
        if block.data.get("asset_ref"):
            figure["assetRef"] = block.data["asset_ref"]
        elif block.directive and block.directive.attrs.get("asset-status") == "missing":
            figure["preservationStatus"] = "partiallyPreserved"
            state.unresolved_figures.append(figure["id"])
        if directive_id:
            state.figures_by_directive[str(directive_id)] = figure
        return figure

    def _formula(self, state: _BuilderState, block: Block) -> dict[str, Any]:
        directive_id = block.directive.attrs.get("id") if block.directive else None
        local_id = _slug(directive_id or f"fm-{state.next('formula') :03d}")
        formula: dict[str, Any] = {
            "id": f"{state.document_id}/formula/{local_id}",
            "rawText": block.text,
            "sourceAnchors": [state.anchor(block)],
            "preservationStatus": "preserved",
        }
        if block.data.get("format") != "raw":
            formula["latex"] = block.text
        if block.directive and block.directive.attrs.get("asset-ref"):
            formula["assetRef"] = block.directive.attrs["asset-ref"]
        if block.data.get("number"):
            formula["number"] = block.data["number"]
        if directive_id:
            state.formulas_by_directive[str(directive_id)] = formula
        return formula

    def _unknown(self, state: _BuilderState, block: Block) -> dict[str, Any]:
        directive_id = block.directive.attrs.get("id") if block.directive else None
        local_id = _slug(directive_id or f"u-{state.next('unknown') :03d}")
        unknown = {
            "id": f"{state.document_id}/unknown/{local_id}",
            "rawContent": block.text,
            "sourceAnchors": [state.anchor(block)],
        }
        if block.directive and block.directive.attrs.get("type-hint"):
            unknown["contentTypeHint"] = block.directive.attrs["type-hint"]
        elif block.data.get("type_hint"):
            unknown["contentTypeHint"] = block.data["type_hint"]
        return unknown

    def _assign_element_ids(self, state: _BuilderState, root: dict[str, Any]) -> None:
        """把 SSIR 元素标识统一改写为 TDRS 形式 ``{标准标识}#{条款路径}``。

        依据 `技术文件智能审查系统（TDRS）设计说明文档v2.0.md` 命名规则附录
        （§二 条款路径、§四 附录、§五 项、§六 表图公式；偏离项见 naming 模块头）：
        附录 ``#Annex_A`` / ``#Annex_A.2.1``；正文章条 ``#8.2.1``；表/图/公式
        ``#Table_3`` / ``#Figure_5`` / ``#Formula_3``（附录内 ``#Table_A.1``）；
        无编号要素按固定英文名（前言 → ``#Foreword``）；内容元素
        ``#<条款路径>/<Kind>-<序号>``；列表项 ``#<条款路径>_<marker>``。
        重号（源文件编号重复/抽取合并）由 ``_ElementIds.unique`` 追加 ``-2/-3`` 并
        登记 ``state.ids.collisions``，不丢元素、不静默改号。

        实现见模块级 ``assign_element_ids``（与 ``apply_element_ids`` 产物回放共用
        同一判据，保证「新建 = 回放」）。
        """
        assign_element_ids(
            state.ids,
            root,
            [("table", state.tables, "Table"),
             ("figure", state.figures, "Figure"),
             ("formula", state.formulas, "Formula"),
             ("unknown", state.unknown_contents, "Unknown")],
            notes=state.notes_registry,
        )
        state.canonical_refs[:] = [state.ids.id_map.get(ref, ref) for ref in state.canonical_refs]
        state.unresolved_figures[:] = [
            state.ids.id_map.get(ref, ref) for ref in state.unresolved_figures
        ]

    @staticmethod
    def _canonical_fragment(block: Block) -> str:
        if block.kind == "table":
            return "\n".join(" | ".join(row) for row in block.data["rows"])
        if block.kind == "list":
            return "\n".join(f"{item['marker']} {item['text']}" for item in block.data["items"])
        return block.text

    def _quality_assessment(self, state: _BuilderState, run_id: str) -> dict[str, Any]:
        comments: list[str] = list(state.document.warnings)
        if state.unresolved_figures:
            comments.append("Missing figure assets: " + ", ".join(state.unresolved_figures))
        if state.declaration_issues:
            # 声明型指令无法归属（不猜、不丢）：如实登记，供人工复核。
            comments.append("Unresolved declarations: " + "; ".join(state.declaration_issues))
        if state.ids.collisions:
            # 元素标识重号（源文件编号重复/抽取合并）：已按 -2/-3 去重，此处如实登记
            # （TDRS 标识唯一性要求；不静默改号、不丢元素，供人工复核）。
            comments.append("Element id collisions: " + ", ".join(state.ids.collisions))
        if state.ids.fallbacks:
            # 编号无法规范化为 TDRS 标识（源文件编号缺失/畸形）：按序号回退，如实登记。
            comments.append("Element ids fell back to sequence: " + ", ".join(state.ids.fallbacks))
        status = "partial" if comments else "complete"
        quality: dict[str, Any] = {
            "id": element_id(state.document_id, "QualityAssessment_M1"),
            "documentId": state.document_id,
            "runId": run_id,
            "overallStatus": status,
            "structureConfidence": 1.0,
            "tableConfidence": 1.0,
            "figureConfidence": 1.0 if not state.unresolved_figures else 0.5,
            "formulaConfidence": 1.0,
            "humanReviewStatus": "machineReviewed",
            "assessedAt": "1970-01-01T00:00:00Z",
        }
        profile = state.document.metadata.get("rendering-profile")
        if profile in {"GB_T_1.1-2020", "iso-iec-directives-part-2", "custom"}:
            quality["renderingProfile"] = profile
        if state.unresolved_figures:
            quality["unresolvedFigures"] = state.unresolved_figures
        if comments:
            quality["comments"] = "\n".join(comments)
        return quality
