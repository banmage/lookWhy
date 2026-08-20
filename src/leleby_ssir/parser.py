"""Parse Canonical SSIR Markdown (CSM) into a small, position-aware AST."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import re
from typing import Any

import yaml


class CSMError(ValueError):
    """Raised when a CSM input has one or more structural errors."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


@dataclass(slots=True)
class Directive:
    name: str
    attrs: dict[str, str]
    line: int


@dataclass(slots=True)
class Block:
    kind: str
    start_line: int
    end_line: int
    text: str = ""
    level: int | None = None
    directive: Directive | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CSMDocument:
    path: Path
    text: str
    metadata: dict[str, Any]
    body_start_line: int
    blocks: list[Block]
    warnings: list[str]
    issues: list["CSMIssue"]
    sha256: str


@dataclass(slots=True)
class CSMIssue:
    """A non-fatal import diagnostic, optionally describing a safe repair."""

    code: str
    severity: str
    message: str
    line: int | None = None
    repaired: bool = False
    repair_action: str | None = None

    def display(self) -> str:
        prefix = f"line {self.line}: " if self.line is not None else ""
        return f"[{self.code}/{self.severity}] {prefix}{self.message}"


DIRECTIVE_RE = re.compile(r"^<!--\s*ssir:([a-z-]+)(.*?)\s*-->\s*$")
ATTR_RE = re.compile(r'([A-Za-z][A-Za-z0-9-]*)="((?:\\.|[^"\\])*)"')
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
IMAGE_RE = re.compile(r"^!\[(.*?)\]\((.*?)\)\s*$")
NUMBERED_ITEM_RE = re.compile(r"^([A-Za-z]+[)）]|\d+[)）])\s*(.*)$")
UNORDERED_ITEM_RE = re.compile(r"^[-*+]\s+(.*)$")
TABLE_CAPTION_RE = re.compile(r"^\*\*表([^\s]+)\s+(.+?)\*\*$")

SUPPORTED_DIRECTIVES = {
    "block",
    "table",
    "table-merge",
    "figure",
    "formula",
    "list",
    "unknown",
}

# These markers are emitted by the MinerU adapter solely to retain page-range
# provenance while its chunks are merged.  They are not SSIR content and must
# never be preserved as visible/unknown document text.
MINERU_PAGE_MARKER_RE = re.compile(r"^<!--\s*/?ssir:mineru-pages\b.*-->\s*$")


def _unescape_attribute(value: str) -> str:
    return value.replace(r'\"', '"').replace(r"\\", "\\")


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith(r"\|"):
        stripped = stripped[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in stripped:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
            current.append(char)
        elif char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    return cells


class CSMParser:
    """A deterministic parser for the constrained CSM 1.0 Markdown dialect."""

    def __init__(self, strict: bool = False) -> None:
        self.strict = strict

    def read(self, path: str | Path) -> CSMDocument:
        source = Path(path)
        raw = source.read_bytes()
        fatal_errors: list[str] = []
        issues: list[CSMIssue] = []
        if raw.startswith(b"\xef\xbb\xbf"):
            issues.append(
                CSMIssue(
                    "CSM-ENC-001",
                    "warning",
                    "UTF-8 BOM was removed while reading the input.",
                    repaired=True,
                    repair_action="Removed UTF-8 BOM in memory; the source file was not modified.",
                )
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CSMError([f"input is not valid UTF-8: {exc}"]) from exc
        if "\r" in text:
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            issues.append(
                CSMIssue(
                    "CSM-ENC-002",
                    "warning",
                    "CRLF or CR line endings were normalized to LF while reading the input.",
                    repaired=True,
                    repair_action="Normalized line endings in memory; the source file was not modified.",
                )
            )
        if text.startswith("\ufeff"):
            text = text.removeprefix("\ufeff")
        if not text.startswith("---\n"):
            raise CSMError(["CSM must start with YAML front matter"])

        marker = text.find("\n---\n", 4)
        if marker < 0:
            raise CSMError(["YAML front matter closing marker is missing"])
        yaml_text = text[4:marker]
        try:
            metadata = yaml.safe_load(yaml_text)
        except yaml.YAMLError as exc:
            raise CSMError([f"invalid YAML front matter: {exc}"]) from exc
        if not isinstance(metadata, dict):
            issues.append(CSMIssue("CSM-META-001", "warning", "YAML front matter was not an object; an empty object was used.", repaired=True, repair_action="Replaced non-object front matter with an empty metadata object."))
            metadata = {}

        body_offset = marker + len("\n---\n")
        body_start_line = text[:body_offset].count("\n") + 1
        blocks, parse_errors, parse_warnings = self._parse_body(text[body_offset:], body_start_line)
        for warning in parse_warnings:
            issues.append(CSMIssue("CSM-STRUCT-001", "warning", warning))
        fatal_errors.extend(self._repair_tables(blocks, issues))
        fatal_errors.extend(self._classify_body_errors(parse_errors, issues))
        self._normalise_metadata(metadata, blocks, source, issues)
        document_errors: list[str] = []
        self._validate_document(metadata, blocks, document_errors)
        fatal_errors.extend(self._classify_document_errors(document_errors, issues))
        self._assess_standard_profile(metadata, blocks, issues)
        self._append_declared_quality_notices(metadata, issues)
        if self.strict:
            fatal_errors.extend(issue.display() for issue in issues if issue.severity in {"warning", "error"})
        if fatal_errors:
            raise CSMError(fatal_errors)
        return CSMDocument(
            path=source,
            text=text,
            metadata=metadata,
            body_start_line=body_start_line,
            blocks=blocks,
            warnings=[issue.display() for issue in issues if issue.severity in {"warning", "error"}],
            issues=issues,
            sha256=sha256(raw).hexdigest(),
        )

    @staticmethod
    def _issue(issues: list[CSMIssue], code: str, message: str, *, line: int | None = None, repaired: bool = False, repair_action: str | None = None) -> None:
        issues.append(CSMIssue(code, "warning", message, line, repaired, repair_action))

    def _normalise_metadata(self, metadata: dict[str, Any], blocks: list[Block], source: Path, issues: list[CSMIssue]) -> None:
        """Fill only machine metadata defaults; never alter a standard's body text."""
        if metadata.get("csm-version") != "1.0":
            original = metadata.get("csm-version")
            metadata["csm-version"] = "1.0"
            self._issue(issues, "CSM-META-002", f'Unsupported or missing csm-version {original!r}; parsed as "1.0" compatibility mode.', repaired=True, repair_action='Set in-memory csm-version to "1.0".')
        if metadata.get("document-type") not in {"standard", "guidance", "technical-report", "contract", "other"}:
            metadata["document-type"] = "standard"
            self._issue(issues, "CSM-META-003", "Missing or unsupported document-type; assumed standard.", repaired=True, repair_action="Set in-memory document-type to standard.")
        h1 = next((block.text for block in blocks if block.kind == "heading" and block.level == 1), None)
        if not isinstance(metadata.get("title"), str) or not metadata["title"].strip():
            metadata["title"] = h1 or source.stem.replace(".csm", "").replace("_", " ")
            self._issue(issues, "CSM-META-004", "Missing title; derived a title from the H1 or file name.", repaired=True, repair_action="Set in-memory title without changing body text.")
        identifier = metadata.get("document-identifier")
        if not isinstance(identifier, str) or not identifier.strip():
            candidate = metadata.get("standard-number") or source.stem.replace(".csm", "").replace("_", "-")
            metadata["document-identifier"] = str(candidate)
            self._issue(issues, "CSM-META-005", "Missing document-identifier; derived it from the standard number or file name.", repaired=True, repair_action="Set in-memory document identifier.")
        if metadata["document-type"] == "standard" and (not isinstance(metadata.get("standard-number"), str) or not metadata["standard-number"].strip()):
            metadata["standard-number"] = str(metadata["document-identifier"])
            self._issue(issues, "CSM-META-006", "Missing standard-number for a standard; used document-identifier as a placeholder.", repaired=True, repair_action="Set in-memory standard number from document identifier.")
        if not isinstance(metadata.get("language"), str) or not metadata["language"].strip():
            body_text = "\n".join(block.text for block in blocks)
            metadata["language"] = "zh-CN" if re.search(r"[\u3400-\u9fff]", body_text) else "und"
            self._issue(issues, "CSM-META-007", f'Missing language; inferred {metadata["language"]}.', repaired=True, repair_action="Set in-memory language tag.")
        if not isinstance(metadata.get("source"), dict):
            metadata["source"] = {"mode": "user-markdown", "provenance": "none"}
            self._issue(issues, "CSM-META-008", "Missing or invalid source object; supplied user-markdown provenance defaults.", repaired=True, repair_action="Set in-memory source object.")
        elif metadata["source"].get("mode") not in {"user-markdown", "mineru-pdf"}:
            metadata["source"]["mode"] = "user-markdown"
            self._issue(issues, "CSM-META-009", "Unsupported source.mode; assumed user-markdown.", repaired=True, repair_action="Set in-memory source.mode to user-markdown.")
        if "provenance" not in metadata["source"]:
            metadata["source"]["provenance"] = "none"
            self._issue(issues, "CSM-META-011", "Missing source.provenance; assumed none.", repaired=True, repair_action="Set in-memory source.provenance to none.")
        if not isinstance(metadata.get("extensions"), dict):
            metadata["extensions"] = {}
            self._issue(issues, "CSM-META-010", "Missing or invalid extensions object; supplied an empty object.", repaired=True, repair_action="Set in-memory extensions to an empty object.")

    def _parse_body(self, body: str, start_line: int) -> tuple[list[Block], list[str], list[str]]:
        lines = body.splitlines()
        blocks: list[Block] = []
        errors: list[str] = []
        warnings: list[str] = []
        pending: dict[str, Directive] = {}
        directive_ids: set[str] = set()
        last_table: Block | None = None
        i = 0

        def line_no(index: int) -> int:
            return start_line + index

        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue

            if MINERU_PAGE_MARKER_RE.match(line):
                i += 1
                continue

            directive_match = DIRECTIVE_RE.match(line)
            if directive_match:
                name = directive_match.group(1)
                attrs = {
                    key: _unescape_attribute(value)
                    for key, value in ATTR_RE.findall(directive_match.group(2))
                }
                if name not in SUPPORTED_DIRECTIVES:
                    # Preserve unsupported directives rather than silently losing user content.
                    blocks.append(
                        Block(
                            kind="unknown",
                            start_line=line_no(i),
                            end_line=line_no(i),
                            text=line,
                            data={"type_hint": f"unsupported-ssir-directive:{name}"},
                        )
                    )
                    warnings.append(f"line {line_no(i)}: unsupported ssir directive was preserved as unknown content: {name}")
                else:
                    if "id" in attrs and attrs["id"] in directive_ids:
                        errors.append(f"line {line_no(i)}: duplicate ssir id: {attrs['id']}")
                    if "id" in attrs:
                        directive_ids.add(attrs["id"])
                    if name in {"table", "figure", "formula", "unknown", "block"} and "id" not in attrs:
                        errors.append(f"line {line_no(i)}: ssir:{name} requires id")
                    directive = Directive(name=name, attrs=attrs, line=line_no(i))
                    if name == "table-merge":
                        if last_table is None:
                            errors.append(f"line {line_no(i)}: ssir:table-merge must follow a table")
                        elif attrs.get("table") != (last_table.directive.attrs.get("id") if last_table.directive else None):
                            errors.append(f"line {line_no(i)}: ssir:table-merge references a different table")
                        else:
                            last_table.data.setdefault("merges", []).append(attrs)
                    else:
                        pending[name] = directive
                i += 1
                continue

            heading = HEADING_RE.match(line)
            if heading:
                blocks.append(
                    Block(
                        kind="heading",
                        start_line=line_no(i),
                        end_line=line_no(i),
                        text=heading.group(2),
                        level=len(heading.group(1)),
                        directive=pending.pop("block", None),
                    )
                )
                i += 1
                continue

            if line.startswith("$$"):
                formula_directive = pending.pop("formula", None)
                start = i
                formula_lines = [line[2:]]
                i += 1
                while i < len(lines) and not lines[i].startswith("$$"):
                    formula_lines.append(lines[i])
                    i += 1
                if i >= len(lines):
                    errors.append(f"line {line_no(start)}: unterminated formula block")
                    break
                closing = lines[i][2:]
                if closing.strip():
                    formula_lines.append(closing)
                i += 1
                number = ""
                if i < len(lines) and re.match(r"^式[（(].+[）)]\s*$", lines[i].strip()):
                    number = lines[i].strip()
                    i += 1
                blocks.append(
                    Block(
                        kind="formula",
                        start_line=line_no(start),
                        end_line=line_no(i - 1),
                        text="\n".join(formula_lines).strip(),
                        directive=formula_directive,
                        data={"number": number},
                    )
                )
                continue

            if line.startswith("|") and i + 1 < len(lines) and TABLE_SEPARATOR_RE.match(lines[i + 1]):
                table_directive = pending.pop("table", None)
                start = i
                rows = [_split_table_row(line)]
                i += 2
                while i < len(lines) and lines[i].startswith("|"):
                    rows.append(_split_table_row(lines[i]))
                    i += 1
                width = len(rows[0])
                for row_index, row in enumerate(rows, start=1):
                    if len(row) != width:
                        errors.append(
                            f"line {line_no(start + row_index + 1)}: table row has {len(row)} cells; expected {width}"
                        )
                blocks.append(
                    Block(
                        kind="table",
                        start_line=line_no(start),
                        end_line=line_no(i - 1),
                        directive=table_directive,
                        data={"rows": rows, "header_rows": 1},
                    )
                )
                last_table = blocks[-1]
                continue

            if line.startswith(">"):
                start = i
                quote_lines: list[str] = []
                while i < len(lines) and lines[i].startswith(">"):
                    quote_lines.append(lines[i][1:].lstrip())
                    i += 1
                quote_text = "\n".join(quote_lines)
                figure_directive = pending.pop("figure", None)
                if figure_directive or quote_text.startswith("[图"):
                    blocks.append(
                        Block(
                            kind="figure",
                            start_line=line_no(start),
                            end_line=line_no(i - 1),
                            text=quote_text,
                            directive=figure_directive,
                        )
                    )
                else:
                    kind = "note"
                    if quote_text.startswith("示例："):
                        kind = "example"
                    elif quote_text.startswith("警示："):
                        kind = "warning"
                    elif not quote_text.startswith("注"):
                        kind = "quote"
                    blocks.append(Block(kind=kind, start_line=line_no(start), end_line=line_no(i - 1), text=quote_text))
                continue

            image = IMAGE_RE.match(line)
            if image:
                blocks.append(
                    Block(
                        kind="figure",
                        start_line=line_no(i),
                        end_line=line_no(i),
                        text=image.group(1),
                        directive=pending.pop("figure", None),
                        data={"asset_ref": image.group(2)},
                    )
                )
                i += 1
                continue

            if line.startswith("```"):
                start = i
                fence = line[:3]
                code_lines: list[str] = []
                i += 1
                while i < len(lines) and not lines[i].startswith(fence):
                    code_lines.append(lines[i])
                    i += 1
                if i >= len(lines):
                    errors.append(f"line {line_no(start)}: unterminated code fence")
                    break
                i += 1
                formula_directive = pending.pop("formula", None)
                unknown_directive = pending.pop("unknown", None)
                if formula_directive:
                    number = ""
                    if i < len(lines) and re.match(r"^式[（(].+[）)]\s*$", lines[i].strip()):
                        number = lines[i].strip()
                        i += 1
                    blocks.append(
                        Block(
                            kind="formula",
                            start_line=line_no(start),
                            end_line=line_no(i - 1),
                            text="\n".join(code_lines),
                            directive=formula_directive,
                            data={"number": number, "format": "raw"},
                        )
                    )
                elif unknown_directive:
                    blocks.append(
                        Block(
                            kind="unknown",
                            start_line=line_no(start),
                            end_line=line_no(i - 1),
                            text="\n".join(code_lines),
                            directive=unknown_directive,
                        )
                    )
                else:
                    blocks.append(
                        Block(
                            kind="paragraph",
                            start_line=line_no(start),
                            end_line=line_no(i - 1),
                            text="\n".join(code_lines),
                            data={"code_fence": True},
                        )
                    )
                continue

            if self._is_list_line(line):
                start = i
                list_directive = pending.pop("list", None)
                items: list[dict[str, str]] = []
                while i < len(lines) and self._is_list_line(lines[i]):
                    marker, item_text = self._parse_list_line(lines[i])
                    items.append({"marker": marker, "text": item_text, "line": str(line_no(i))})
                    i += 1
                blocks.append(
                    Block(
                        kind="list",
                        start_line=line_no(start),
                        end_line=line_no(i - 1),
                        directive=list_directive,
                        data={"items": items},
                    )
                )
                continue

            table_caption = TABLE_CAPTION_RE.match(line)
            if table_caption and "table" in pending:
                next_index = i + 1
                while next_index < len(lines) and not lines[next_index].strip():
                    next_index += 1
                if next_index < len(lines) and lines[next_index].startswith("|"):
                    pending["table"].attrs["caption-number"] = table_caption.group(1)
                    pending["table"].attrs["caption"] = table_caption.group(2)
                    i += 1
                    continue

            start = i
            paragraph_lines = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not self._starts_new_block(lines, i):
                paragraph_lines.append(lines[i])
                i += 1
            blocks.append(
                Block(
                    kind="paragraph",
                    start_line=line_no(start),
                    end_line=line_no(i - 1),
                    text="\n".join(paragraph_lines),
                    directive=pending.pop("block", None),
                )
            )

        for name, directive in pending.items():
            warnings.append(f"line {directive.line}: ssir:{name} has no following compatible block")
        return blocks, errors, warnings

    @staticmethod
    def _is_list_line(line: str) -> bool:
        return bool(UNORDERED_ITEM_RE.match(line) or NUMBERED_ITEM_RE.match(line))

    @staticmethod
    def _parse_list_line(line: str) -> tuple[str, str]:
        unordered = UNORDERED_ITEM_RE.match(line)
        if unordered:
            return line[0], unordered.group(1)
        numbered = NUMBERED_ITEM_RE.match(line)
        assert numbered
        return numbered.group(1), numbered.group(2)

    @staticmethod
    def _starts_new_block(lines: list[str], index: int) -> bool:
        line = lines[index]
        return bool(
            DIRECTIVE_RE.match(line)
            or HEADING_RE.match(line)
            or line.startswith("$$")
            or line.startswith(">")
            or line.startswith("```")
            or IMAGE_RE.match(line)
            or (line.startswith("|") and index + 1 < len(lines) and TABLE_SEPARATOR_RE.match(lines[index + 1]))
            or CSMParser._is_list_line(line)
        )

    @staticmethod
    def _validate_document(metadata: dict[str, Any], blocks: list[Block], errors: list[str]) -> None:
        headings = [block for block in blocks if block.kind == "heading"]
        h1 = [block for block in headings if block.level == 1]
        if len(h1) != 1:
            errors.append(f"CSM must contain exactly one H1; found {len(h1)}")
        elif h1[0].text != metadata.get("title"):
            errors.append("H1 title must exactly match front matter title")

        seen_ids: set[str] = set()
        for block in blocks:
            if block.directive and "id" in block.directive.attrs:
                block_id = block.directive.attrs["id"]
                if block_id in seen_ids:
                    errors.append(f"line {block.directive.line}: duplicate ssir id: {block_id}")
                seen_ids.add(block_id)

        chapters: list[int] = []
        for block in headings:
            if block.level == 2:
                match = re.match(r"^(\d+)\s+", block.text)
                if match:
                    chapters.append(int(match.group(1)))
        if chapters and chapters != list(range(1, max(chapters) + 1)):
            errors.append(f"main chapter numbering must be continuous from 1; found {chapters}")

    @staticmethod
    def _repair_tables(blocks: list[Block], issues: list[CSMIssue]) -> list[str]:
        """Pad short rows only; extra cells have no safe, semantics-preserving repair."""
        fatal_errors: list[str] = []
        for block in blocks:
            if block.kind != "table":
                continue
            rows: list[list[str]] = block.data["rows"]
            if not rows or not rows[0]:
                fatal_errors.append(f"line {block.start_line}: table has no usable header row")
                continue
            width = len(rows[0])
            for row_index, row in enumerate(rows):
                if len(row) > width:
                    fatal_errors.append(
                        f"line {block.start_line + row_index + 1}: table row has {len(row)} cells; expected {width}"
                    )
                elif len(row) < width:
                    missing = width - len(row)
                    row.extend([""] * missing)
                    CSMParser._issue(
                        issues,
                        "CSM-TABLE-001",
                        f"Table row had {len(row) - missing} cells; padded {missing} trailing empty cell(s) to match its header.",
                        line=block.start_line + row_index + 1,
                        repaired=True,
                        repair_action="Padded trailing empty table cells in memory.",
                    )
        return fatal_errors

    @staticmethod
    def _classify_body_errors(errors: list[str], issues: list[CSMIssue]) -> list[str]:
        fatal_errors: list[str] = []
        for error in errors:
            if "unterminated formula block" in error or "unterminated code fence" in error:
                fatal_errors.append(error)
            elif "duplicate ssir id" in error:
                # Explicit IDs participate in reference resolution; changing them can mis-bind a merge or asset.
                fatal_errors.append(error)
            elif "table row has" in error:
                # Short rows were repaired above. Extra cells have already been recorded as fatal there.
                continue
            elif "requires id" in error:
                CSMParser._issue(issues, "CSM-DIRECTIVE-001", error + "; generated IDs will be used.", repaired=True, repair_action="Used a deterministic generated SSIR object ID.")
            elif "table-merge" in error:
                CSMParser._issue(issues, "CSM-DIRECTIVE-002", error + "; the merge directive was ignored.", repaired=True, repair_action="Ignored an unresolvable table-merge directive.")
            else:
                CSMParser._issue(issues, "CSM-STRUCT-002", error)
        return fatal_errors

    @staticmethod
    def _classify_document_errors(errors: list[str], issues: list[CSMIssue]) -> list[str]:
        for error in errors:
            if error.startswith("CSM must contain exactly one H1"):
                CSMParser._issue(issues, "CSM-STRUCT-003", error + "; SSIR metadata title was retained.")
            elif error == "H1 title must exactly match front matter title":
                CSMParser._issue(issues, "CSM-STRUCT-004", error + "; neither value was changed.")
            elif error.startswith("main chapter numbering"):
                CSMParser._issue(issues, "GB-T-1.1-CHAPTER-001", error + "; original numbering was preserved.")
            elif "duplicate ssir id" in error:
                return [error]
            else:
                CSMParser._issue(issues, "CSM-STRUCT-005", error)
        return []

    @staticmethod
    def _assess_standard_profile(metadata: dict[str, Any], blocks: list[Block], issues: list[CSMIssue]) -> None:
        """Report only baseline mandatory concerns; optional GB/T components stay optional."""
        if metadata.get("document-type") != "standard":
            return
        headings = [block.text.strip() for block in blocks if block.kind == "heading" and block.level == 2]
        if "前言" not in headings:
            CSMParser._issue(issues, "GB-T-1.1-FOREWORD-001", "Standard document has no 前言 section; GB/T 1.1 treats the foreword as a required document element.")
        if not any(re.match(r"^1\s+范围(?:\s|$)", title) for title in headings):
            CSMParser._issue(issues, "GB-T-1.1-SCOPE-001", "No identifiable chapter 1 范围 was found; confirm the document scope manually.")
        profile = metadata.get("extensions", {}).get("standard-profile")
        if profile == "product" and not any("技术要求" in title for title in headings):
            CSMParser._issue(issues, "GB20001-10-TECHNICAL-001", "Product-standard profile has no identifiable 技术要求 section; GB/T 20001.10 treats technical requirements as essential.")
        number = metadata.get("standard-number")
        if isinstance(number, str) and number and not re.search(r"\d{4}$", number):
            CSMParser._issue(issues, "GB-T-1.1-ID-001", "Standard number has no trailing four-digit year; original number was preserved.")
        if isinstance(number, str) and "-" in number:
            CSMParser._issue(issues, "GB-T-1.1-ID-002", "Standard number uses an ASCII hyphen; original number was preserved for source fidelity.")

    @staticmethod
    def _append_declared_quality_notices(metadata: dict[str, Any], issues: list[CSMIssue]) -> None:
        notices = metadata.get("extensions", {}).get("quality-notices", [])
        if not isinstance(notices, list):
            return
        for notice in notices:
            if isinstance(notice, dict):
                issues.append(
                    CSMIssue(
                        str(notice.get("code", "CSM-DECLARED-NOTICE")),
                        str(notice.get("severity", "warning")),
                        str(notice.get("message", "")),
                    )
                )
