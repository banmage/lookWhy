"""Deterministic JSON and optional Turtle exports."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Iterator
from urllib.parse import quote


def json_bytes(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def turtle_text(document: dict[str, Any]) -> str:
    """Export a stable RDF projection; JSON remains the authoritative format."""
    payload_hash = sha256(json_bytes(document)).hexdigest()
    prefix = "https://leleby.io/ns/ssir#"
    resource = lambda value: f"<https://leleby.io/resource/{quote(value, safe='')}>"
    lines = [
        f"@prefix ssir: <{prefix}> .",
        "",
        f"{resource(document['id'])} a ssir:Document ;",
        f"  ssir:ssirVersion {json.dumps(document['ssirVersion'], ensure_ascii=False)} ;",
        f"  ssir:jsonSha256 {json.dumps(payload_hash)} ;",
        f"  ssir:title {json.dumps(document['metadata']['common']['title'], ensure_ascii=False)} .",
        "",
    ]
    for node, parent_id in _walk_nodes(document["structuralRoot"]):
        if node["nodeType"] == "document":
            continue
        lines.append(f"{resource(node['id'])} a ssir:StructuralNode ;")
        lines.append(f"  ssir:nodeType {json.dumps(node['nodeType'])} ;")
        if node.get("number"):
            lines.append(f"  ssir:number {json.dumps(node['number'], ensure_ascii=False)} ;")
        if node.get("title"):
            lines.append(f"  ssir:title {json.dumps(node['title'], ensure_ascii=False)} ;")
        lines.append(f"  ssir:parent {resource(parent_id)} .")
        lines.append("")
        for content in node.get("contentElements", []):
            lines.append(f"{resource(content['id'])} a ssir:ContentElement ;")
            lines.append(f"  ssir:presentationType {json.dumps(content['presentationType'])} ;")
            lines.append(f"  ssir:parent {resource(node['id'])} .")
            lines.append("")
    for source in document["sourceFiles"]:
        lines.append(f"{resource(source['id'])} a ssir:SourceFile ;")
        lines.append(f"  ssir:fileName {json.dumps(source['fileName'], ensure_ascii=False)} ;")
        lines.append(f"  ssir:mimeType {json.dumps(source['mimeType'])} .")
        lines.append("")
    for kind, objects in (("Table", document["tables"]), ("Figure", document["figures"]), ("Formula", document["formulas"])):
        for obj in objects:
            lines.append(f"{resource(obj['id'])} a ssir:{kind} ;")
            if obj.get("number"):
                lines.append(f"  ssir:number {json.dumps(obj['number'], ensure_ascii=False)} ;")
            label = obj.get("caption") or obj.get("rawText")
            if label:
                lines.append(f"  ssir:label {json.dumps(label, ensure_ascii=False)} ;")
            lines.append(f"  ssir:source {resource(document['id'])} .")
            lines.append("")
    return "\n".join(lines)


def _walk_nodes(node: dict[str, Any], parent_id: str | None = None) -> Iterator[tuple[dict[str, Any], str]]:
    yield node, parent_id or node["id"]
    for child in node.get("children", []):
        yield from _walk_nodes(child, node["id"])
