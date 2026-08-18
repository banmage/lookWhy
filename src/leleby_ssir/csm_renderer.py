"""Render the M1 SSIR subset back into deterministic Canonical SSIR Markdown."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml


def render_csm(document: dict[str, Any]) -> str:
    """Render semantic SSIR content without copying derived provenance or quality data."""
    metadata = _metadata(document)
    lines = ["---", yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).strip(), "---", ""]
    lines.extend([f"# {metadata['title']}", ""])
    state = _RenderState(document)
    for node in sorted(document["structuralRoot"].get("children", []), key=_sort_order):
        state.render_node(node)
    return "\n".join(lines + state.lines).rstrip() + "\n"


def write_csm(document: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_csm(document), encoding="utf-8", newline="\n")


def _metadata(document: dict[str, Any]) -> dict[str, Any]:
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


class _RenderState:
    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document
        self.lines: list[str] = []
        self.tables = {table["id"]: table for table in document.get("tables", [])}
        self.figures = {figure["id"]: figure for figure in document.get("figures", [])}
        self.formulas = {formula["id"]: formula for formula in document.get("formulas", [])}
        self.unknowns = {unknown["id"]: unknown for unknown in document.get("unknownContents", [])}
        self.counts: defaultdict[str, int] = defaultdict(int)

    def render_node(self, node: dict[str, Any]) -> None:
        level = min(max(int(node.get("level", 1)) + 1, 2), 6)
        self.lines.extend(["#" * level + " " + self._heading(node), ""])
        for content in sorted(node.get("contentElements", []), key=_sort_order):
            self.render_content(content)
        for child in sorted(node.get("children", []), key=_sort_order):
            self.render_node(child)

    def _heading(self, node: dict[str, Any]) -> str:
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
        kind = content["presentationType"]
        if kind in {"paragraph", "note", "example", "warning", "quote"}:
            text = content.get("textContent", "")
            if kind == "paragraph":
                self.lines.extend([text, ""])
            else:
                self.lines.extend([f"> {text}", ""])
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
        table_id = self._next_id("tbl")
        header_rows = sum(1 for row in table["rows"] if row.get("isHeader")) or 1
        self.lines.append(f'<!-- ssir:table id="{table_id}" header-rows="{header_rows}" -->')
        if table.get("number") and table.get("caption"):
            self.lines.append(f"**表{table['number']} {table['caption']}**")
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
                    self.lines.append(
                        '<!-- ssir:table-merge table="{table}" row="{row}" column="{column}" rowspan="{rowspan}" colspan="{colspan}" -->'.format(
                            table=table_id,
                            row=max(int(cell["rowIndex"]) - header_rows + 1, 1),
                            column=int(cell["colIndex"]) + 1,
                            rowspan=cell.get("rowspan", 1),
                            colspan=cell.get("colspan", 1),
                        )
                    )
        self.lines.append("")

    @staticmethod
    def _table_cell(text: str) -> str:
        return text.replace("|", r"\|")

    def _render_figure(self, figure: dict[str, Any]) -> None:
        figure_id = self._next_id("fig")
        missing = figure.get("preservationStatus") == "partiallyPreserved" and not figure.get("assetRef")
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
        formula_id = self._next_id("fm")
        self.lines.extend([f'<!-- ssir:formula id="{formula_id}" -->', "$$", formula["rawText"], "$$"])
        if formula.get("number"):
            self.lines.append(formula["number"])
        self.lines.append("")

    def _render_unknown(self, unknown: dict[str, Any]) -> None:
        unknown_id = self._next_id("unk")
        hint = unknown.get("contentTypeHint")
        directive = f'<!-- ssir:unknown id="{unknown_id}"'
        if hint:
            directive += f' type-hint="{hint}"'
        self.lines.extend([directive + " -->", "```text", unknown["rawContent"], "```", ""])
