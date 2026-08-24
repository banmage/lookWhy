"""Build schema-conformant SSIR JSON from a parsed CSM document."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re
from typing import Any

from .parser import Block, CSMDocument


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

        for block in document.blocks:
            if block.kind == "heading":
                # The document title is the sole H1 that is not a structural
                # node.  MinerU commonly emits annex starts as later H1s.
                if block.level == 1 and not _is_annex_heading(block.text):
                    state.canonical_parts.append(block.text)
                    continue
                node = self._make_node(state, block, node_sort)
                node_sort += 1
                depth = max((block.level or 2) - 1, 1)
                while stack and stack[-1][0] >= depth:
                    stack.pop()
                parent = stack[-1][1] if stack else root
                parent.setdefault("children", []).append(node)
                stack.append((depth, node))
                state.canonical_parts.append(block.text)
                continue

            parent = stack[-1][1] if stack else root
            parent_id = parent["id"]
            element = self._make_content(state, block, parent_id, content_sort[parent_id])
            content_sort[parent_id] += 1
            parent.setdefault("contentElements", []).append(element)
            state.canonical_refs.append(element["id"])
            state.canonical_parts.append(self._canonical_fragment(block))

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
        return ssir

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
        numbered = re.match(r"^(\d+(?:\.\d+)*)(?:\s+|(?=[\u4e00-\u9fffA-Za-z（]))(.+)$", title)
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
        if block.kind in {"paragraph", "note", "example", "warning", "quote"}:
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
            if number:
                table["number"] = number
            if caption:
                table["caption"] = caption
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
        if profile in {"gb-t-1-1-2020", "iso-iec-directives-part-2", "custom"}:
            quality["renderingProfile"] = profile
        if state.unresolved_figures:
            quality["unresolvedFigures"] = state.unresolved_figures
        if comments:
            quality["comments"] = "\n".join(comments)
        return quality
