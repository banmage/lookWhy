"""Write a parser-normalized CSM document without changing technical content."""

from __future__ import annotations

from pathlib import Path
import re

import yaml

from .parser import Block, CSMDocument, Directive, escape_table_cell


def render_canonical(document: CSMDocument) -> str:
    """Render the safe in-memory repairs as the immutable canonical CSM baseline.

    规则对应: GEN-031（层次编号规范化）、GEN-032/033（表格题注处理）、GBT-B08（题注形如"表X 题名"）。
    """
    lines = ["---", yaml.safe_dump(document.metadata, allow_unicode=True, sort_keys=False).strip(), "---", ""]
    for block in document.blocks:
        _render_block(lines, block)
    return "\n".join(lines).rstrip() + "\n"


def write_canonical(document: CSMDocument, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_canonical(document), encoding="utf-8", newline="\n")


def _escape_attr_text(value: str) -> str:
    # 反斜杠翻倍、双引号转义；抽成普通函数，避免在 f-string 表达式内写转义序列。
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _directive(directive: Directive) -> str:
    attributes = "".join(
        f' {key}="{_escape_attr_text(value)}"'
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
        # 正文条号与后续汉字之间统一留一个半角空格（GBT-B02 编号后空一格接排；
        # OCR 常把 "4.6.1电动机" 的空格吞掉，导致正文与标题的间隔不一致）。
        text = re.sub(
            r"(?m)^(\d+(?:\.\d+){1,3}|[A-Z]\.\d+(?:\.\d+)*)(?=[\u4e00-\u9fff（(])",
            r"\1 ",
            block.text,
        )
        lines.extend(["\n".join(prefix + line for line in text.splitlines()), ""])
    elif block.kind == "list":
        lines.extend(f"{item['marker']} {item['text']}" for item in block.data["items"])
        lines.append("")
    elif block.kind == "table":
        if block.directive:
            caption_number = block.directive.attrs.get("caption-number")
            caption = block.directive.attrs.get("caption")
            if caption_number and caption:
                lines.append(f"**表{caption_number} {caption}**")
            elif caption_number:
                # Bare numbered caption ("表 N") roundtrips as "**表N**".
                lines.append(f"**表{caption_number}**")
        for row_index, row in enumerate(block.data["rows"]):
            lines.append("| " + " | ".join(escape_table_cell(cell) for cell in row) + " |")
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
        if str(block.data.get("number") or "").strip():
            # 编号行是 CSM 语法「式(N)」（与 csm_renderer 同规，docs/07 §6.7）；
            # SSIR/builder 里的 formula.number 是纯编号标签。
            lines.append(f"式({block.data['number']})")
        lines.append("")
    elif block.kind == "unknown":
        if block.directive:
            lines.extend(["```text", block.text, "```", ""])
        else:
            lines.extend([block.text, ""])
