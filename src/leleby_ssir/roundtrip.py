"""Markdown round-trip verification for the M1 SSIR subset."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
import unicodedata
from typing import Any


@dataclass(slots=True)
class EquivalenceDifference:
    layer: str
    path: str
    message: str


@dataclass(slots=True)
class RoundTripReport:
    input_file: str
    render_md_file: str
    ssir1_id: str
    ssir2_id: str
    passed: bool
    layer_status: dict[str, str]
    critical_information_loss: list[str] = field(default_factory=list)
    differences: list[EquivalenceDifference] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "inputFile": self.input_file,
            "renderMdFile": self.render_md_file,
            "ssir1Id": self.ssir1_id,
            "ssir2Id": self.ssir2_id,
            "passed": self.passed,
            "overallStatus": "pass" if self.passed else "fail",
            "layerStatus": self.layer_status,
            "criticalInformationLoss": self.critical_information_loss,
            "differences": [asdict(difference) for difference in self.differences],
        }

    def write_json(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def compare_ssir(ssir1: dict[str, Any], ssir2: dict[str, Any], input_file: str = "", render_md_file: str = "") -> RoundTripReport:
    """Compare semantic views, explicitly excluding derived IDs, anchors, runs and quality data."""
    first = _semantic_views(ssir1)
    second = _semantic_views(ssir2)
    differences: list[EquivalenceDifference] = []
    layer_status: dict[str, str] = {}
    for layer in ("identity", "structure", "content", "semantic"):
        if first[layer] == second[layer]:
            layer_status[layer] = "pass"
        else:
            layer_status[layer] = "fail"
            differences.append(
                EquivalenceDifference(layer, layer, "Semantic view differs after Markdown round-trip.")
            )
    critical = _critical_information_loss(first, second)
    if critical:
        layer_status["criticalInformation"] = "fail"
        differences.extend(
            EquivalenceDifference("criticalInformation", code, "Critical information changed or was lost.")
            for code in critical
        )
    else:
        layer_status["criticalInformation"] = "pass"
    return RoundTripReport(
        input_file=input_file,
        render_md_file=render_md_file,
        ssir1_id=ssir1["id"],
        ssir2_id=ssir2["id"],
        passed=not differences,
        layer_status=layer_status,
        critical_information_loss=critical,
        differences=differences,
    )


def _semantic_views(document: dict[str, Any]) -> dict[str, Any]:
    common = document["metadata"]["common"]
    standard = document["metadata"].get("standard", {})
    registries = {
        "tables": {item["id"]: item for item in document.get("tables", [])},
        "figures": {item["id"]: item for item in document.get("figures", [])},
        "formulas": {item["id"]: item for item in document.get("formulas", [])},
        "unknowns": {item["id"]: item for item in document.get("unknownContents", [])},
    }
    structure = [_node_view(node, registries) for node in sorted(document["structuralRoot"].get("children", []), key=_sort_order)]
    return {
        "identity": {
            "documentType": document.get("documentType"),
            "documentIdentifier": common.get("documentIdentifier"),
            "title": common.get("title"),
            "titleEn": common.get("titleEn"),
            "language": common.get("language"),
            "standardNumber": standard.get("standardNumber"),
            "chineseTitle": standard.get("chineseTitle"),
        },
        "structure": structure,
        "content": _content_inventory(document, registries),
        "semantic": _semantic_view(document, structure),
    }


def _node_view(node: dict[str, Any], registries: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    return {
        "nodeType": node.get("nodeType"),
        "level": node.get("level"),
        "number": node.get("number"),
        "title": _normalise(node.get("title", "")),
        "content": [_content_view(content, registries) for content in sorted(node.get("contentElements", []), key=_sort_order)],
        "children": [_node_view(child, registries) for child in sorted(node.get("children", []), key=_sort_order)],
    }


def _content_inventory(document: dict[str, Any], registries: dict[str, dict[str, dict[str, Any]]]) -> dict[str, list[Any]]:
    inventory: dict[str, list[Any]] = {"tables": [], "figures": [], "formulas": [], "unknownContents": []}

    def visit(node: dict[str, Any]) -> None:
        for content in node.get("contentElements", []):
            kind = content.get("presentationType")
            if kind == "table":
                inventory["tables"].append(_table_view(registries["tables"][content["tableRef"]]))
            elif kind == "figure":
                inventory["figures"].append(_figure_view(registries["figures"][content["figureRef"]]))
            elif kind == "formula":
                inventory["formulas"].append(_formula_view(registries["formulas"][content["formulaRef"]]))
            elif kind == "other":
                inventory["unknownContents"].append(_unknown_view(registries["unknowns"][content["unknownRef"]]))
        for child in node.get("children", []):
            visit(child)

    for root_child in document["structuralRoot"].get("children", []):
        visit(root_child)
    return inventory


def _semantic_view(document: dict[str, Any], structure: list[dict[str, Any]]) -> dict[str, Any]:
    values: list[dict[str, Any]] = []

    def visit(node: dict[str, Any]) -> None:
        for content in sorted(node.get("contentElements", []), key=_sort_order):
            semantic_types = content.get("semanticTypes")
            if semantic_types:
                values.append(
                    {
                        "nodeNumber": node.get("number"),
                        "semanticTypes": sorted(semantic_types),
                        "text": _normalise(content.get("textContent", "")),
                    }
                )
        for child in sorted(node.get("children", []), key=_sort_order):
            visit(child)

    for node in sorted(document["structuralRoot"].get("children", []), key=_sort_order):
        visit(node)
    return {"annotatedContent": values, "scope": _scope_text(structure)}


def _content_view(content: dict[str, Any], registries: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    kind = content.get("presentationType")
    if kind == "table":
        return {"type": kind, "value": _table_view(registries["tables"][content["tableRef"]])}
    if kind == "figure":
        return {"type": kind, "value": _figure_view(registries["figures"][content["figureRef"]])}
    if kind == "formula":
        return {"type": kind, "value": _formula_view(registries["formulas"][content["formulaRef"]])}
    if kind == "other":
        return {"type": kind, "value": _unknown_view(registries["unknowns"][content["unknownRef"]])}
    if kind == "list":
        return {
            "type": kind,
            "items": [
                {"marker": item.get("marker"), "text": _normalise(item.get("text", ""))}
                for item in sorted(content.get("listItems", []), key=_sort_order)
            ],
        }
    return {"type": kind, "text": _normalise(content.get("textContent", ""))}


def _table_view(table: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": table.get("number"),
        "caption": _normalise(table.get("caption", "")),
        "rows": [
            {
                "isHeader": row.get("isHeader", False),
                "cells": [
                    {
                        "text": _normalise(cell.get("text", "")),
                        "colspan": cell.get("colspan", 1),
                        "rowspan": cell.get("rowspan", 1),
                    }
                    for cell in sorted(row.get("cells", []), key=lambda item: item["colIndex"])
                ],
            }
            for row in sorted(table.get("rows", []), key=lambda item: item["rowIndex"])
        ],
    }


def _figure_view(figure: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": figure.get("number"),
        "caption": _normalise(figure.get("caption", "")),
        "assetRef": figure.get("assetRef"),
        "preservationStatus": figure.get("preservationStatus"),
    }


def _formula_view(formula: dict[str, Any]) -> dict[str, Any]:
    return {"number": formula.get("number"), "rawText": formula.get("rawText", "")}


def _unknown_view(unknown: dict[str, Any]) -> dict[str, Any]:
    return {"contentTypeHint": unknown.get("contentTypeHint"), "rawContent": unknown.get("rawContent", "")}


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


def _sort_order(item: dict[str, Any]) -> int:
    return int(item.get("sortOrder", 0))


def _critical_information_loss(first: dict[str, Any], second: dict[str, Any]) -> list[str]:
    losses: list[str] = []
    first_text = _all_text(first)
    second_text = _all_text(second)
    checks = {
        "C1-normativeWording": lambda text: _tokens(text, r"应当|必须|不得|不应|应|宜"),
        "C2-prohibitions": lambda text: _tokens(text, r"不得|禁止|严禁"),
        "C3-mandatoryConditions": lambda text: _tokens(text, r"在[^。；;]{0,80}(?:条件下|情况下)"),
        "C4-numericalValues": lambda text: _tokens(text, r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?"),
        "C5-units": lambda text: _tokens(text, r"[-+]?\d+(?:\.\d+)?\s*(?:dB\(A\)|r/min|MPa|kV|mA|kW|mm|min|%|℃|Pa|K|V|A|W|m|h|s)"),
        "C6-comparisonOperators": lambda text: _tokens(text, r"≤|≥|<|>|="),
        "C10-referenceTargets": lambda text: _tokens(text, r"(?:GB/T|GB|JB/T|QB/T|T/|Q/)\s*[A-Za-z0-9.]+(?:[—-]\d{4})?"),
    }
    for code, extractor in checks.items():
        if extractor(first_text) != extractor(second_text):
            losses.append(code)
    if _clause_numbers(first["structure"]) != _clause_numbers(second["structure"]):
        losses.append("C7-clauseIdentifiers")
    if first["content"]["tables"] != second["content"]["tables"]:
        losses.append("C8-tableCellContent")
    if first["content"]["formulas"] != second["content"]["formulas"]:
        losses.append("C9-formulaRawRepresentation")
    if _scope_text(first["structure"]) != _scope_text(second["structure"]):
        losses.extend(["C11-scope", "C12-applicability"])
    return losses


def _tokens(text: str, pattern: str) -> Counter[str]:
    return Counter(re.findall(pattern, text))


def _all_text(view: dict[str, Any]) -> str:
    return json.dumps({"identity": view["identity"], "structure": view["structure"], "content": view["content"]}, ensure_ascii=False)


def _clause_numbers(nodes: list[dict[str, Any]]) -> list[str]:
    result: list[str] = []
    for node in nodes:
        if node.get("number"):
            result.append(str(node["number"]))
        result.extend(_clause_numbers(node["children"]))
    return result


def _scope_text(nodes: list[dict[str, Any]]) -> str:
    for node in nodes:
        if node.get("number") == "1":
            return json.dumps(node.get("content", []), ensure_ascii=False, sort_keys=True)
        child_scope = _scope_text(node["children"])
        if child_scope:
            return child_scope
    return ""
