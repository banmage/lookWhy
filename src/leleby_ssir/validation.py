"""Schema and M1 semantic validation for generated SSIR documents."""

from __future__ import annotations

from importlib.resources import files
import json
from typing import Any

from jsonschema import Draft7Validator, FormatChecker


class SSIRValidationError(ValueError):
    """Raised when a generated SSIR object does not meet the M1 contract."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


def load_schema() -> dict[str, Any]:
    return json.loads(files("leleby_ssir").joinpath("ssir.schema.json").read_text(encoding="utf-8"))


def validate_ssir(document: dict[str, Any]) -> None:
    schema_errors = sorted(
        Draft7Validator(load_schema(), format_checker=FormatChecker()).iter_errors(document),
        key=lambda error: list(error.absolute_path),
    )
    errors = [f"schema {'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}" for error in schema_errors]
    errors.extend(_semantic_errors(document))
    if errors:
        raise SSIRValidationError(errors)


def _semantic_errors(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    source_ids = {source["id"] for source in document.get("sourceFiles", [])}
    table_ids = {table["id"] for table in document.get("tables", [])}
    figure_ids = {figure["id"] for figure in document.get("figures", [])}
    formula_ids = {formula["id"] for formula in document.get("formulas", [])}
    unknown_ids = {unknown["id"] for unknown in document.get("unknownContents", [])}
    seen_ids: set[str] = set()

    def check_anchor(anchor: dict[str, Any], location: str) -> None:
        if anchor["id"] in seen_ids:
            errors.append(f"{location}: duplicate object ID {anchor['id']}")
        seen_ids.add(anchor["id"])
        if anchor["sourceFileId"] not in source_ids:
            errors.append(f"{location}: SourceAnchor references unknown source file")
        if anchor["anchorType"] == "markdown":
            if anchor.get("markdownStartLine", 0) > anchor.get("markdownEndLine", 0):
                errors.append(f"{location}: markdown anchor start line is after end line")
            if "pdfPageIndex" in anchor or "bbox" in anchor:
                errors.append(f"{location}: Markdown anchor must not contain PDF coordinates")

    def walk_node(node: dict[str, Any]) -> None:
        node_id = node["id"]
        if node_id in seen_ids:
            errors.append(f"structural node: duplicate object ID {node_id}")
        seen_ids.add(node_id)
        for anchor in node.get("sourceAnchors", []):
            check_anchor(anchor, f"node {node_id}")
        for element in node.get("contentElements", []):
            element_id = element["id"]
            if element_id in seen_ids:
                errors.append(f"content element: duplicate object ID {element_id}")
            seen_ids.add(element_id)
            if element["parentNodeId"] != node_id:
                errors.append(f"content {element_id}: parentNodeId does not match containing node")
            for anchor in element["sourceAnchors"]:
                check_anchor(anchor, f"content {element_id}")
            if element.get("tableRef") and element["tableRef"] not in table_ids:
                errors.append(f"content {element_id}: tableRef is not registered")
            if element.get("figureRef") and element["figureRef"] not in figure_ids:
                errors.append(f"content {element_id}: figureRef is not registered")
            if element.get("formulaRef") and element["formulaRef"] not in formula_ids:
                errors.append(f"content {element_id}: formulaRef is not registered")
            if element.get("unknownRef") and element["unknownRef"] not in unknown_ids:
                errors.append(f"content {element_id}: unknownRef is not registered")
            for item in element.get("listItems", []):
                if item["id"] in seen_ids:
                    errors.append(f"list item: duplicate object ID {item['id']}")
                seen_ids.add(item["id"])
                if "sourceAnchor" in item:
                    check_anchor(item["sourceAnchor"], f"list item {item['id']}")
        for child in node.get("children", []):
            walk_node(child)

    walk_node(document["structuralRoot"])
    for table in document.get("tables", []):
        if table["id"] in seen_ids:
            errors.append(f"table: duplicate object ID {table['id']}")
        seen_ids.add(table["id"])
        for anchor in table["sourceAnchors"]:
            check_anchor(anchor, f"table {table['id']}")
        if table["rowCount"] != len(table["rows"]):
            errors.append(f"table {table['id']}: rowCount does not match rows")
        for row in table["rows"]:
            if len(row["cells"]) != table["colCount"]:
                errors.append(f"table {table['id']}: row {row['rowIndex']} has inconsistent columns")
    for collection_name, objects in (("figure", document.get("figures", [])), ("formula", document.get("formulas", [])), ("unknown", document.get("unknownContents", []))):
        for obj in objects:
            if obj["id"] in seen_ids:
                errors.append(f"{collection_name}: duplicate object ID {obj['id']}")
            seen_ids.add(obj["id"])
            for anchor in obj["sourceAnchors"]:
                check_anchor(anchor, f"{collection_name} {obj['id']}")
    return errors
