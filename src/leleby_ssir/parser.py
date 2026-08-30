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
# 独立「示例N：」行（框式示例标题，GB/T 1.1 10.4.5 / GBT-B11）：冒号后无内容
# 才提升为标题；"示例1：γ辐照装置…" 这类行内示例（冒号后有内容）不受影响。
EX_HEADER_RE = re.compile(r"^示例\s*\d*\s*[:：]\s*$")
EX_LEAD_RE = re.compile(r"^示例\s*\d*\s*[:：]")
NOTE_LEAD_RE = re.compile(r"^注\s*\d*\s*[:：]")
# 句末标点后出现点分条号（6.3.5.2 等）→ 把被 OCR 合并进上一句的条号分段
#（零宽切分点，条号本身保留在下一段开头）。
CLAUSE_SPLIT_RE = re.compile(r"(?<=[。；])\s*(?=\d+(?:\.\d+)+[\u4e00-\u9fff])")
# GB/T 1.1 列项符号为破折号（——）或间隔号（·）；OCR 常把 "——" 压成
# 单个 "-" 或 "—" 且丢失后方空格，故破折号允许无空格（GBT-C12）。
# CommonMark 的 "*"/"+" 项目符号仍要求后方空格，避免误吞 "**加粗**" 行首。
UNORDERED_ITEM_RE = re.compile(r"^(?:([-—]+)|([*+])\s+)\s*(.*)$")
TABLE_CAPTION_RE = re.compile(r"^\*\*表([^\s]+)\s+(.+?)\*\*$")
# Bare numbered caption: "**表N**" — 行业标准/企业标准常见排版，题注只有编号
# 无题名 (GBT-B08 编号必备；题名可省略)。
TABLE_BARE_CAPTION_RE = re.compile(r"^\*\*表([^\s]+)\*\*$")
# Heading-shaped table caption ("## 表4 物理性能要求") — MinerU 偶尔把表题注
# 提升为 ## 标题且位于 ssir:table directive 之前；解析时降级为表格 caption，
# 避免渲染出「表4 物理性能要求」+「表4」双题注（GEN-032/033、GBT-B08）。
TABLE_HEADING_CAPTION_RE = re.compile(r"^表([^\s]+)\s+(.+)$")

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
        self._repair_list_markers(blocks, issues)
        self._repair_lost_list_markers(blocks, issues)
        self._repair_text_spacing(blocks, issues)
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
        """Fill only machine metadata defaults; never alter a standard's body text.

        规则对应: GEN-050（元数据 schema 一致）+ GBT-C01（文件名称/文件编号等必备字段兜底）。
        """
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
        # 规则对应: GEN-031/GBT-H02-H03（章条编号与层级）、GBT-X02（表格）、GBT-X06（公式）、
        # GEN-052（ssir 指令/引用注册表化，未知指令保留原文）。
        lines = body.splitlines()
        blocks: list[Block] = []
        errors: list[str] = []
        warnings: list[str] = []
        pending: dict[str, Directive] = {}
        pending_table_caption: tuple[str, str] | None = None
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
                    if name == "table":
                        # 表题注被提升为标题（heading-shaped caption）已暂存，
                        # 在此合并进 table attrs；已有显式 caption 时以显式为准。
                        if pending_table_caption is not None:
                            attrs.setdefault("caption-number", pending_table_caption[0])
                            attrs.setdefault("caption", pending_table_caption[1])
                            pending_table_caption = None
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
                heading_text = heading.group(2)
                # 表题注被提升为标题（"## 表4 物理性能要求"，GEN-032/033）：
                # 若形如「表N 题名」且后随（可跨空行）ssir:table directive 或
                # 表格行，则降级为表格 caption 并入待处理的 table attrs，
                # 避免渲染出「表4 物理性能要求」+「表4」双题注。
                table_heading_caption = TABLE_HEADING_CAPTION_RE.match(heading_text)
                if table_heading_caption and heading.group(1).count("#") >= 2:
                    lookahead = i + 1
                    while lookahead < len(lines) and not lines[lookahead].strip():
                        lookahead += 1
                    next_line = lines[lookahead].strip() if lookahead < len(lines) else ""
                    next_table = next_line.startswith("<!-- ssir:table ")
                    if not next_table and next_line.startswith("|") and lookahead + 1 < len(lines):
                        next_table = bool(TABLE_SEPARATOR_RE.match(lines[lookahead + 1].strip()))
                    if next_table:
                        pending_table_caption = (
                            table_heading_caption.group(1),
                            table_heading_caption.group(2),
                        )
                        warnings.append(
                            f"line {line_no(i)}: heading-shaped table caption was folded into the table caption "
                            f"({table_heading_caption.group(1)} {table_heading_caption.group(2)!r})."
                        )
                        i += 1
                        continue
                # GBT-C12 列项误识别为标题：MinerU 偶尔把列项（如 "c）定型和
                # 固化时间；"）提升成 ## 标题，导致渲染时按标题样式大缩进。
                # 标题文本若形如列项（字母/数字 + 全/半角括号）则降级为列项
                # 块，与相邻 a)/b) 同层对齐。真实章条号（5.1、A.1）不含括号，
                # 不会被误降。
                numbered_item = NUMBERED_ITEM_RE.match(heading_text)
                if numbered_item and heading.group(1).count("#") >= 2:
                    marker = numbered_item.group(1)
                    if marker.endswith(")"):
                        marker = marker[:-1] + "）"
                    blocks.append(
                        Block(
                            kind="list",
                            start_line=line_no(i),
                            end_line=line_no(i),
                            text=heading_text,
                            data={"items": [{"marker": marker, "text": numbered_item.group(2), "line": str(line_no(i))}]},
                        )
                    )
                    warnings.append(f"line {line_no(i)}: heading shaped like a list item was demoted to a list item ({marker} {numbered_item.group(2)!r}).")
                    i += 1
                    continue
                blocks.append(
                    Block(
                        kind="heading",
                        start_line=line_no(i),
                        end_line=line_no(i),
                        text=heading_text,
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
                while i < len(lines):
                    if self._is_list_line(lines[i]):
                        marker, item_text = self._parse_list_line(lines[i])
                        items.append({"marker": marker, "text": item_text, "line": str(line_no(i))})
                        i += 1
                        continue
                    if not lines[i].strip():
                        # Loose list (CommonMark): blank lines between list items
                        # stay inside the list; MinerU 常以空行分隔各列项（GBT-C12）。
                        lookahead = i
                        while lookahead < len(lines) and not lines[lookahead].strip():
                            lookahead += 1
                        if lookahead < len(lines) and self._is_list_line(lines[lookahead]):
                            i = lookahead
                            continue
                    break
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

            bare_caption = TABLE_BARE_CAPTION_RE.match(line)
            if bare_caption and "table" in pending:
                next_index = i + 1
                while next_index < len(lines) and not lines[next_index].strip():
                    next_index += 1
                if next_index < len(lines) and lines[next_index].startswith("|"):
                    # Bare "表 N" caption (number only, no title) — keep the
                    # number so GBT-X02 passes; no caption attribute.
                    pending["table"].attrs["caption-number"] = bare_caption.group(1)
                    i += 1
                    continue

            start = i
            # 段落行尾清理：MinerU 行尾常残留 Markdown 硬换行（两个尾随空格），
            # 会导致渲染时段落中途断行（如 "……25%时，  \n审查结论应为不通过"）。
            paragraph_lines = [line.rstrip()]
            i += 1
            while i < len(lines):
                if not lines[i].strip():
                    # 空行续接（6.4.2.4 "……列入多种方法时，\n应指明仲裁方法。"）：
                    # 上一行以连接性标点结尾且下一非空行不是新块时，视为同一段落
                    # 被 MinerU 误插空行，跳过空行继续收集（示例/注/图/表引导语除外）。
                    lookahead = i
                    while lookahead < len(lines) and not lines[lookahead].strip():
                        lookahead += 1
                    if (
                        lookahead < len(lines)
                        and not self._starts_new_block(lines, lookahead)
                        and paragraph_lines
                        and paragraph_lines[-1].endswith(("，", "；", "：", "、", ","))
                        and not EX_LEAD_RE.match(lines[lookahead].strip())
                        and not NOTE_LEAD_RE.match(lines[lookahead].strip())
                    ):
                        i = lookahead
                        continue
                    break
                if self._starts_new_block(lines, i):
                    break
                if MINERU_PAGE_MARKER_RE.match(lines[i]):
                    # MinerU page-range markers are provenance, not content;
                    # skip them even mid-paragraph so they never leak into the
                    # rendered PDF (GEN-005 页码标记不计入正文).
                    i += 1
                    continue
                paragraph_lines.append(lines[i].rstrip())
                i += 1
            paragraph_text = "\n".join(paragraph_lines)
            # 6.3.5.2 类合并：MinerU 把「……告知乘客。6.3.5.2为了确保……」
            # 挤进同一段，导致条号无法回车顶格（GBT-B02）。在句末标点（。；）
            # 之后出现的点分条号处把段落拆分为两个块。
            block_directive = pending.pop("block", None)
            parts = [p.strip() for p in CLAUSE_SPLIT_RE.split(paragraph_text) if p.strip()]
            for part_index, part in enumerate(parts):
                block = Block(
                    kind="paragraph",
                    start_line=line_no(start),
                    end_line=line_no(i - 1),
                    text=part,
                    directive=block_directive if part_index == 0 else None,
                )
                if EX_HEADER_RE.match(part):
                    # 独立「示例N：」行（附录框式示例的标题）提升为标题，
                    # 使其进入 SSIR 结构树并在示例框内居中（GBT-B11）。
                    block.kind = "heading"
                    block.level = 2
                blocks.append(block)

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
            return unordered.group(1) or unordered.group(2), unordered.group(3)
        numbered = NUMBERED_ITEM_RE.match(line)
        assert numbered
        marker = numbered.group(1)
        # 编号括号统一为全角（GBT-C19）：OCR 常混用 a) / a）——半角括号在
        # 渲染时与文字的视觉间隔明显小于全角括号，导致列表项间隔不统一。
        if marker.endswith(")"):
            marker = marker[:-1] + "）"
        return marker, numbered.group(2)

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
        # 规则对应: GBT-H02（章从 1 起连续编号）、GEN-050/052（id 唯一性与引用完整性）。
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
        """Pad short rows only; extra cells have no safe, semantics-preserving repair.

        规则对应: GBT-X02（表格一致性；短行补空、多余单元格报错不猜测修复）。
        """
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
    def _repair_list_markers(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """Correct OCR glyph-confused list markers in context (CSM-OCR-001).

        OCR 常把字母 l）误读为数字 1）、把 1 误读为 l/I、把 0 误读为 O。
        孤立纠正会误伤真子列表，因此只在多数派上下文中纠正少数派里的
        可混淆项（多数派至少 2 个且严格多于少数派）：
        - 字母多数 + 数字 outlier 1）/1） → l）/l）；
        - 数字多数 + 字母 outlier l/I）/l/I） → 1）/1）；O）/O） → 0）/0）。
        """
        letter_re = re.compile(r"^[A-Za-z][)）]$")
        digit_re = re.compile(r"^\d+[)）]$")
        letter_fix = {"1)": "l)", "1）": "l）"}
        digit_fix = {"l)": "1)", "l）": "1）", "I)": "1)", "I）": "1）", "O)": "0)", "O）": "0）"}
        for block in blocks:
            if block.kind != "list":
                continue
            items: list[dict[str, str]] = block.data["items"]
            markers = [str(item["marker"]) for item in items]
            if len(markers) < 3:
                continue
            letter_indexes = [i for i, m in enumerate(markers) if letter_re.match(m)]
            digit_indexes = [i for i, m in enumerate(markers) if digit_re.match(m)]
            if len(letter_indexes) + len(digit_indexes) != len(markers):
                continue  # 混入破折号/间隔号等无编号标记，上下文不明确
            if len(letter_indexes) >= 2 and len(letter_indexes) > len(digit_indexes) and digit_indexes:
                targets = [i for i in digit_indexes if markers[i] in letter_fix]
                fix, context = letter_fix, "letters"
            elif len(digit_indexes) >= 2 and len(digit_indexes) > len(letter_indexes) and letter_indexes:
                targets = [i for i in letter_indexes if markers[i] in digit_fix]
                fix, context = digit_fix, "digits"
            else:
                continue
            for target in targets:
                original = markers[target]
                corrected = fix[original]
                items[target]["marker"] = corrected
                CSMParser._issue(
                    issues,
                    "CSM-OCR-001",
                    f"List marker {original!r} is a likely OCR misread of {corrected!r} "
                    f"(majority of sibling markers are {context}).",
                    line=int(items[target].get("line", 0)) or None,
                    repaired=True,
                    repair_action=f"Rewrote marker {original} to {corrected} in memory.",
                )

    @staticmethod
    def _repair_lost_list_markers(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """Re-add dash list markers OCR dropped from whole lines (CSM-OCR-005).

        MinerU 常把破折号列项（——第3部分：分类标准；）整行丢失标记，只留下
        文本本身；该行会解析成独立段落，夹在两个破折号列表之间（前言部分
        清单是典型场景）。判定条件收窄以避免误伤真实段落：
        - 单行、长度 ≤ 40、以 ；或 。结尾；
        - 前后相邻块都是纯破折号标记列表；
        - 不以条号、注/示例/警示/表/图/附录开头。
        命中后转成单条目列表，标记取后一个列表（回退前一个）的破折号。
        """
        dash_marker = re.compile(r"^[-—–]+$")

        def is_dash_list(block: Block | None) -> bool:
            if block is None or block.kind != "list":
                return False
            items: list[dict[str, str]] = block.data.get("items", [])
            return bool(items) and all(dash_marker.match(str(item.get("marker", ""))) for item in items)

        for index, block in enumerate(blocks):
            if block.kind != "paragraph":
                continue
            text = block.text.strip()
            if not text or "\n" in text or len(text) > 40:
                continue
            if not re.search(r"[；。]$", text):
                continue
            if re.match(r"^\d+(?:\.\d+)*\s", text):
                continue  # 条号开头的裸条，不是列表项
            if re.match(r"^(注|示例|警示|表|图|附)", text):
                continue
            previous = blocks[index - 1] if index > 0 else None
            following = blocks[index + 1] if index + 1 < len(blocks) else None
            if not (is_dash_list(previous) and is_dash_list(following)):
                continue
            assert previous is not None and following is not None
            following_items: list[dict[str, Any]] = following.data.get("items", [])
            previous_items: list[dict[str, Any]] = previous.data.get("items", [])
            marker = str(following_items[0].get("marker") or "") or str(previous_items[0].get("marker") or "")
            if not marker:
                continue
            block.kind = "list"
            block.text = ""
            block.data = {"items": [{"marker": marker, "text": text, "line": str(block.start_line)}]}
            CSMParser._issue(
                issues,
                "CSM-OCR-005",
                f"Dash list marker lost by OCR; re-added {marker!r} to {text!r}.",
                line=block.start_line,
                repaired=True,
                repair_action="Converted the orphan paragraph into a dash list item using the neighbouring list marker.",
            )

    @staticmethod
    def _repair_text_spacing(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """Restore spacing OCR drops inside standard-document text (CSM-OCR-003/004).

        - CSM-OCR-003 术语间隔：术语条目「中文English」（或 OCR 留下半角空格的
          「中文 English」）中英文之间应空一个汉字。用 U+3000（全角空格）实现：
          reportlab 段落渲染把它当作普通空白折叠成窄空格仍可显示，且该字体
          有 U+3000 字形（不会渲染成 .notdef 方框）；历史实现曾用 U+200B
          （零宽空格）制造 1em 推进宽度，但 Noto Serif CJK SC 无 U+200B 字形，
          2026-08-29 起改用 U+3000（见 GB_T_20001.5 渲染回归）。
          只在「术语和定义」章内、行首为汉字串后接拉丁字母、且不含中文标点的
          行上修复，避免误伤正文。
        - CSM-OCR-004 标准号间隔：正文中的标准号字母与数字之间应有一个空格
          （GB/T20001 → GB/T 20001）。只匹配已知前缀形态（GB/T、JB/T、SJ/T、
          DB11/T、GB/Z、GB 等），带斜杠前导被排除（SAC/TC286 不动），单字母
          前缀排除（维生素B1 不动）。
        """
        term_re = re.compile(r"^([\u4e00-\u9fff]{1,24})[ \u3000\u200b]*([A-Za-z])")
        no_cjk_punct = re.compile(r"[，。；：？！、”“‘’《》【】（）…]")
        chapter_re = re.compile(r"^\d+\s+\S")
        annex_re = re.compile(r"^附\s*录")
        standard_re = re.compile(
            r"(?<![A-Za-z0-9/])([A-Z]{1,4}\d{0,2}/[TZ])(?=\d)"
            r"|(?<![A-Za-z0-9/])([A-Z]{2,4})(?=\d)"
        )
        term_gap = "\u3000"

        in_terms = False
        for block in blocks:
            if block.kind == "heading":
                text = block.text.strip()
                if annex_re.match(text) or (chapter_re.match(text) and "术语" not in text):
                    in_terms = False
                elif chapter_re.match(text) and "术语" in text:
                    in_terms = True
            if block.kind not in ("paragraph", "heading"):
                continue
            original = block.text
            repaired = original
            # 标准号间隔（对所有文本行统一修复，幂等：已有空格则不再插入）
            repaired = standard_re.sub(lambda m: f"{m.group(1) or m.group(2)} ", repaired)
            # 术语间隔（仅术语章内、行首中文串后接拉丁、无中文标点）
            if in_terms:
                for line in repaired.splitlines():
                    stripped = line.strip()
                    if not stripped or no_cjk_punct.search(stripped):
                        continue
                    if re.match(r"^\d", stripped):
                        continue  # 术语章内的编号行（3.1 等）不动
                    if term_re.match(stripped):
                        repaired = re.sub(
                            r"^([\u4e00-\u9fff]{1,24})[ \u3000\u200b]*([A-Za-z])",
                            rf"\1{term_gap}\2",
                            repaired,
                            count=1,
                        )
                        break
            if repaired == original:
                continue
            block.text = repaired
            # 列表项文本同样修复（列表项的 text 在 data.items 里）
            if block.kind == "list":
                for item in block.data.get("items", []):
                    item_text = str(item.get("text", ""))
                    item_repaired = standard_re.sub(lambda m: f"{m.group(1) or m.group(2)} ", item_text)
                    if item_repaired != item_text:
                        item["text"] = item_repaired
            CSMParser._issue(
                issues,
                "CSM-OCR-003" if term_gap in repaired else "CSM-OCR-004",
                f"Restored spacing in {original[:40]!r} -> {repaired[:40]!r}.",
                line=block.start_line,
                repaired=True,
                repair_action="Inserted the missing inter-word / standard-number space in memory.",
            )

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
        """Report only baseline mandatory concerns; optional GB/T components stay optional.

        规则对应: GBT-C03（前言必备）、GBT-C05（范围应为第 1 章）、P10-E03（产品标准技术要求必备）、
        GEN-012（文件编号年份与一字线）。
        """
        if metadata.get("document-type") != "standard":
            return
        # OCR/MinerU 常在标题字间插入空格（"前 言"），比对前去除空白。
        headings = [re.sub(r"\s+", "", block.text.strip()) for block in blocks if block.kind == "heading" and block.level == 2]
        if "前言" not in headings:
            CSMParser._issue(issues, "GB-T-1.1-FOREWORD-001", "Standard document has no 前言 section; GB/T 1.1 treats the foreword as a required document element.")
        if not any(re.match(r"^1\s*范围", title) for title in headings):
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
