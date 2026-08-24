"""Write a parser-normalized CSM document without changing technical content."""

from __future__ import annotations

from pathlib import Path

import yaml

from .parser import Block, CSMDocument, Directive


def render_std0(document: CSMDocument) -> str:
    """Render the safe in-memory repairs as the immutable Std0 CSM baseline.

    规则对应: GEN-031（层次编号规范化）、GEN-032/033（表格题注处理）、GBT-B08（题注形如"表X 题名"）。
    """
    lines = ["---", yaml.safe_dump(document.metadata, allow_unicode=True, sort_keys=False).strip(), "---", ""]
    for block in document.blocks:
        _render_block(lines, block)
    return "\n".join(lines).rstrip() + "\n"


def write_std0(document: CSMDocument, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_std0(document), encoding="utf-8", newline="\n")


def _directive(directive: Directive) -> str:
    attributes = "".join(
        f' {key}="{value.replace("\\", "\\\\").replace(chr(34), "\\\"")}"'
        for key, value in directive.attrs.items()
    )
    return f"<!-- ssir:{directive.name}{attributes} -->"


def _render_block(lines: list[str], block: Block) -> None:
    # 规则对应: GBT-B08（表题注）、GBT-X06（公式编号）、GEN-052（未知内容保留原文）。
    if block.directive and block.directive.name != "table-merge":
        lines.append(_directive(block.directive))
    if block.kind == "heading":
        lines.extend(["#" * int(block.level or 1) + " " + block.text, ""])
    elif block.kind in {"paragraph", "note", "example", "warning", "quote"}:
        prefix = "> " if block.kind != "paragraph" else ""
        lines.extend(["\n".join(prefix + line for line in block.text.splitlines()), ""])
    elif block.kind == "list":
        lines.extend(f"{item['marker']} {item['text']}" for item in block.data["items"])
        lines.append("")
    elif block.kind == "table":
        if block.directive:
            caption_number = block.directive.attrs.get("caption-number")
            caption = block.directive.attrs.get("caption")
            if caption_number and caption:
                lines.append(f"**表{caption_number} {caption}**")
        for row_index, row in enumerate(block.data["rows"]):
            lines.append("| " + " | ".join(cell.replace("|", r"\|") for cell in row) + " |")
            if row_index == 0:
                lines.append("| " + " | ".join("---" for _ in row) + " |")
        for merge in block.data.get("merges", []):
            lines.append(_directive(Directive("table-merge", merge, block.end_line)))
        lines.append("")
    elif block.kind == "figure":
        if "asset_ref" in block.data:
            lines.append(f"![{block.text}]({block.data['asset_ref']})")
        else:
            lines.append("> " + block.text)
        lines.append("")
    elif block.kind == "formula":
        if block.data.get("format") == "raw":
            lines.extend(["```formula", block.text, "```"])
        else:
            lines.extend(["$$", block.text, "$$"])
        if block.data.get("number"):
            lines.append(block.data["number"])
        lines.append("")
    elif block.kind == "unknown":
        if block.directive:
            lines.extend(["```text", block.text, "```", ""])
        else:
            lines.extend([block.text, ""])
