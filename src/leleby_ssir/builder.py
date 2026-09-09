"""Build schema-conformant SSIR JSON from a parsed CSM document."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re


# GFM 脚注引用标记：[^N]（docs/07 §6.7）；用于把脚注定义与其注释的条款关联。
_FOOTNOTE_REF_RE = re.compile(r"\[\^([0-9A-Za-z_-]+)\]")
from typing import Any

from .parser import EX_HEADER_RE, Block, CSMDocument


def _slug(value: str) -> str:
    value = value.replace("—", "-").replace("–", "-")
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return value or "document"


def _caption_parts(text: str) -> tuple[str | None, str | None]:
    clean = text.strip().strip("[]")
    match = re.match(r"^图\s*([^\s]+)\s+(.+?)(?:（图片占位）)?$", clean)
    if match:
        return match.group(1), match.group(2)
    return None, clean or None


def _is_annex_heading(text: str) -> bool:
    return bool(re.match(r"^附\s*录\s*[A-Z]", text.strip()))


# 术语行：中文术语 + 间隙（U+3000/空格/历史 U+200B）+ 英文对应词。
# 英文部分只允许拉丁字母、数字、空白与少量符号，禁止中文标点/汉字，
# 避免把定义段误判为术语行。
TERM_LINE_RE = re.compile(
    r"^([\u4e00-\u9fff]{1,24})[\u3000 \u200b]+([A-Za-z][A-Za-z0-9 &()（）·.\-—]*)$"
)


def _match_term_line(text: str) -> tuple[str, str] | None:
    """Split a term line into (中文术语, 英文对应词), or None when it is not one."""
    match = TERM_LINE_RE.match(text.strip())
    if not match:
        return None
    return match.group(1), match.group(2).strip()


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
            "id": f"{self.document_id}/anchor/a-{number:04d}",
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
        document_id = f"ssir:{_slug(identifier)}"
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
            "id": f"{document_id}/document",
            "logicalId": "document",
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
        # ssir:box 显式文档框（2026-09-08）：开/关事件在块流上推进，当前打开的
        # 框 id（从 1 起单调递增）与样式挂到其后的每个结构节点/内容元素上；
        # 嵌套开（parser 已报 CSM-STRUCT-006）在此忽略，与宽容解析语义一致。
        active_box: int | None = None
        active_box_style: str = "frame"
        for block in document.blocks:
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
                    pair = _match_term_line(str(node.get("title") or "").strip())
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
                        pair = _match_term_line(title)
                        if pair:
                            pending_term["term"] = pair[0]
                            pending_term["englishTerm"] = pair[1]
                    pending_term = None
                    pending_def = None
                continue

            parent = stack[-1][1] if stack else root
            parent_id = parent["id"]
            element = self._make_content(state, block, parent_id, content_sort[parent_id])
            content_sort[parent_id] += 1
            if active_box is not None:
                element["box"] = active_box
                element["boxStyle"] = active_box_style
            parent.setdefault("contentElements", []).append(element)
            state.canonical_refs.append(element["id"])
            state.canonical_parts.append(self._canonical_fragment(block))
            # 脚注关系：正文元素中出现的 [^N] 记录其所属条款节点；脚注定义元素
            # 据此写入 footnoteMarker / footnoteAnchorRef（本体层可做 脚注-条款 关系）。
            text_content = str(element.get("textContent") or "")
            for m in _FOOTNOTE_REF_RE.finditer(text_content):
                marker_nodes[m.group(1)] = parent_id
            if element.get("presentationType") == "footnote":
                label = str(block.data.get("label") or "")
                if not label:
                    match = re.match(r"^(\d+)[)）]", text_content)
                    if match:
                        label = match.group(1)
                element.setdefault("footnoteMarker", label)
                element["footnoteAnchorRef"] = marker_nodes.get(label, parent_id)
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
                pair = _match_term_line(text)
                if pair:
                    pending_term["term"] = pair[0]
                    pending_term["englishTerm"] = pair[1]
                    element.setdefault("semanticTypes", []).append("termDefinition")
                pending_term = None

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
        run_id = "ssir:processing/run/19700101-001"
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
                "id": f"{document_id}/canonical",
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
        canonical/roundtrip 不受影响。
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
        if annex:
            number = annex.group(1)
            # Annex status is normative information, so retain it in the schema's title field.
            status = annex.group(2)
            title = f"（{status}） {annex.group(3)}".rstrip() if status else annex.group(3).strip()
            node_type = "annex"
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
            content["textContent"] = (f"{label}) {text}" if label else text)
        elif block.kind in {"paragraph", "note", "example", "warning", "quote"}:
            content["presentationType"] = block.kind if block.kind != "paragraph" else "paragraph"
            content["textContent"] = block.text
            content["semanticTypes"] = self._semantic_types(parent_id, block.text)
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
                data_row = header_rows + int(merge["row"]) - 1
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
        number, caption = _caption_parts(block.text)
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
        if block.data.get("asset_ref"):
            figure["assetRef"] = block.data["asset_ref"]
        elif block.directive and block.directive.attrs.get("asset-status") == "missing":
            figure["preservationStatus"] = "partiallyPreserved"
            state.unresolved_figures.append(figure["id"])
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
        status = "partial" if comments else "complete"
        quality: dict[str, Any] = {
            "id": f"{state.document_id}/qa/m1",
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
