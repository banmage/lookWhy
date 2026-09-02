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
# 行内注切分：OCR 把术语定义后的「注1：…。注2：…。」合并进定义段时，
# 在「。注N：」句界处切分为独立块（GBT-X04/B10；GB_T_20001.6 3.1 型）。
NOTE_SPLIT_RE = re.compile(r"(?<=。)(?=注\s*\d*\s*[:：])")
# 句末标点后出现点分条号（6.3.5.2 等）→ 把被 OCR 合并进上一句的条号分段
#（零宽切分点，条号本身保留在下一段开头）。
CLAUSE_SPLIT_RE = re.compile(r"(?<=[。；])\s*(?=\d+(?:\.\d+)+[\u4e00-\u9fff])")
# GB/T 1.1 列项符号为破折号（——）或间隔号（·）；OCR 常把 "——" 压成
# 单个 "-" 或 "—" 且丢失后方空格，故破折号允许无空格（GBT-C12）。
# CommonMark 的 "*"/"+" 项目符号仍要求后方空格，避免误吞 "**加粗**" 行首。
# ●/•/·/○（U+25CF/U+2022/U+00B7/U+25CB）是规程/规范类标准示例常用的
# 项目符号与 GB/T 1.1 第二层次间隔号；OCR 可能全角半角混用、圆点/短横
# 互读（GB_T_1.1-2020 前言 8.3 的 ·/• 混用），且无 Markdown 强调歧义，
# 故允许无空格。
UNORDERED_ITEM_RE = re.compile(r"^(?:([-—–]+)|([*+]\s+)|([●•·○])\s*)\s*(.*)$")
# 项目符号族（OCR 常混读）：同一列表内按多数派统一（CSM-OCR-001）。
_BULLET_MARKERS = ("●", "•", "·", "○")
# 破折号族：OCR 把同一破折号读成长度不一的横杠（-、—、——、———、–，
# 全角/半角混用）。与项目符号族一起参与同列表多数派统一（CSM-OCR-001）。
_DASH_RUN_RE = re.compile(r"^[-—–]+$")
TABLE_CAPTION_RE = re.compile(r"^\*\*表([^\s]+)\s+(.+?)\*\*$")
# Bare numbered caption: "**表N**" — 行业标准/企业标准常见排版，题注只有编号
# 无题名 (GBT-B08 编号必备；题名可省略)。
TABLE_BARE_CAPTION_RE = re.compile(r"^\*\*表([^\s]+)\*\*$")
# Heading-shaped table caption ("## 表4 物理性能要求") — MinerU 偶尔把表题注
# 提升为 ## 标题且位于 ssir:table directive 之前；解析时降级为表格 caption，
# 避免渲染出「表4 物理性能要求」+「表4」双题注（GEN-032/033、GBT-B08）。
# 允许 "表" 与编号之间有空格（OCR 排法 "表 3 轴伸径向圆跳动"，2026-08-31）。
TABLE_HEADING_CAPTION_RE = re.compile(r"^表\s*([^\s]+)\s+(.+)$")

# 裸条号标题（MinerU 偶尔把章条标题抽成普通段落，无 ## 前缀——如
# QB_T_2946-2020 第 3 章 "3 产品分类和型号命名" / "3.1 电动机分类和型号命名" /
# "3.1.1 电动机分类"，只有 3.1.2 保留 ##，导致 GBT-H03 报"章编号不连续：缺失 3"
# 且 GBT-C06 把 "3 产品分类和型号命名" 误当引用条目）。判别（保守）：
# 行首编号 + 空白 + 汉字/括号开头（排除 "1 000 kV" 千分位，GEN-031）、
# 无句末标点、长度 ≤ 40（正文短句以编号开头时通常更长或带标点）。
BARE_HEADING_CANDIDATE_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+[\u4e00-\u9fff（(]")
# 段落句末标点（有则不可能为标题；标题行以句号/逗号/分号结尾的极罕见）。
_BARE_HEADING_TERMINAL_PUNCT = "。；，,、！？"
# 表注行：表格最后一行合并单元格以「注N：」开头（GB_3100-2026 表1/表4 型，
# MinerU 把表注整进表内最后一行）。
_TABLE_NOTE_CELL_RE = re.compile(r"^注\s*\d*\s*[:：]")


def _is_bare_enumeration(enum_lines: list[str]) -> bool:
    """裸列项判定（2026-09-02，GB_3100-2026 4.2 七个定义常量型）。

    MinerU 把源文中逐行排列的枚举行（引导语「…单位制：」+ 每条以 ；/。 收尾）
    收集进同一段，渲染时行内换行被折叠成空格 → 挤成一行流。判定（保守）：
    ≥2 行、≥2 行以句末标点（。；：;.）结尾、绝大多数行（≥2/3）如此、且
    ≥1 行以分号收尾（枚举特征）——普通折行段落几乎不可能同时满足（折行点
    极少恰好落在句界，更不可能多条连续如此）。行尾 LaTeX 闭合符 $ 先剥掉
    （4.2 的普朗克/玻尔兹曼常量行以 $ 结尾）。
    """
    if len(enum_lines) < 2:
        return False
    sentence_ends = sum(1 for ln in enum_lines if ln.endswith(("。", "；", "：", ";", ".")))
    semi_ends = sum(1 for ln in enum_lines if ln.endswith(("；", ";")))
    return sentence_ends >= 2 and sentence_ends * 3 >= len(enum_lines) * 2 and semi_ends >= 1


def _absorb_table_note_spill(blocks: list[Block], warnings: list[str]) -> list[Block]:
    """表注跨页断裂吸收（2026-09-02，GB_3100-2026 表4）。

    表注行（表内最后一行合并单元格，以「注N：」开头）跨页时，MinerU 把续行
    抽成表格外段落——注6 的续句（"于静止状态和基态的自由碳12原子…"）成为
    裸段落、注7~注11 成为「> 注N：」块，渲染时全部落在表格框外（用户报告
    "表4最后一行的内容应一直包括到注11"）。此处把紧随表注行的连续注块
    （注N：…）与续句段（表格注行文本尚未以句末标点收尾时的普通段落）合并
    回表末注行单元格，以 <br> 分行（与 merge 阶段恢复的 <br> 单元格行结构
    同一约定）；遇到新块（标题/条号段/新表格等）即停止。
    """
    result: list[Block] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        result.append(block)
        index += 1
        if block.kind != "table":
            continue
        rows = block.data.get("rows") or []
        if not rows or not rows[-1]:
            continue
        cell = str(rows[-1][0])
        if not _TABLE_NOTE_CELL_RE.match(cell.strip()):
            continue
        absorbed = False
        while index < len(blocks):
            nxt = blocks[index]
            text = str(nxt.text).strip()
            if nxt.kind == "note" and text.startswith("注"):
                cell += "<br>" + text
                rows[-1][0] = cell
                index += 1
                absorbed = True
                continue
            if (
                nxt.kind == "paragraph"
                and not cell.endswith(("。", "！", "？"))
                and not BARE_HEADING_CANDIDATE_RE.match(text)
            ):
                cell += "<br>" + text
                rows[-1][0] = cell
                index += 1
                absorbed = True
                continue
            break
        if absorbed:
            warnings.append(
                f"line {block.start_line}: spilled table notes were absorbed back "
                f"into the table's trailing note row ({rows[-1][0][:40]!r}…)."
            )
    return result


def _bare_heading_candidates(lines: list[str]) -> tuple[set[str], dict[int, str]]:
    """预扫描：返回 (已确认标题编号集合, {行号: 候选编号})。

    已确认标题 = 带 ## 前缀且文本以"编号+空白"开头的标题行；候选 = 形如
    标题的裸段落行（排除表格/引用/图片/代码/公式/指令/列项行）。用于
    级联提升：候选编号是某已确认编号的祖先（3 是 3.1.2 的祖先）、或父编号
    已提升（3.1.1 的父 3.1 提升后 3.1.1 跟随）时提升为标题。
    """
    confirmed: set[str] = set()
    candidates: dict[int, str] = {}
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        heading = HEADING_RE.match(line)
        if heading:
            number_match = re.match(r"^(\d+(?:\.\d+)*)\s", heading.group(2))
            if number_match:
                confirmed.add(number_match.group(1))
            continue
        if stripped.startswith(("|", ">", "!", "```", "$$", "<!--", "**")):
            continue
        if UNORDERED_ITEM_RE.match(line) or NUMBERED_ITEM_RE.match(line):
            continue
        candidate = BARE_HEADING_CANDIDATE_RE.match(stripped)
        if candidate and len(stripped) <= 40 and not any(
            ch in stripped for ch in _BARE_HEADING_TERMINAL_PUNCT
        ):
            candidates[idx] = candidate.group(1)
    return confirmed, candidates


def _promoted_bare_headings(confirmed: set[str], candidates: dict[int, str]) -> set[str]:
    """级联提升：初始 = 所有已确认编号的祖先链；迭代 = 父编号已提升的子编号。

    保守设计：没有已确认标题编号时什么都不提升（整树裸抽无法可靠区分
    标题与正文，留给人工核查，符合 CSM-OCR-002 的"无法唯一合法时不要猜"）。
    """
    promoted: set[str] = set()

    def ancestors(number: str) -> list[str]:
        parts = number.split(".")
        return [".".join(parts[:i]) for i in range(1, len(parts))]

    def parent(number: str) -> str:
        return number.rsplit(".", 1)[0] if "." in number else ""

    for number in confirmed:
        for ancestor in ancestors(number):
            promoted.add(ancestor)
    changed = True
    while changed:
        changed = False
        for number in candidates.values():
            if number in promoted:
                continue
            if parent(number) in promoted:
                promoted.add(number)
                changed = True
    return promoted


# 单位为毫米 等单位行：位于表题注与表格之间，题注折叠时的 lookahead 可跳过，
# 且折进 table directive 的 unit 属性（渲染为右对齐"单位为毫米"紧贴表格）。
TABLE_UNIT_LINE_RE = re.compile(r"^单位\s*[为:：]\s*(\S{1,8})$")


def _clause_digit_placements(digits: str, max_depth: int = 4) -> list[tuple[int, ...]]:
    """All ways to split a digit run into 1..max_depth non-empty segments.

    章条号点分隔修复（CSM-OCR-002）的候选空间：把 "7421" 拆成
    (7,4,2,1)、(7,4,21)、(7,42,1)、(74,2,1)… 每段无前导零。
    """
    placements: list[tuple[int, ...]] = []
    if not digits:
        return placements

    def rec(start: int, segments: list[int]) -> None:
        if start == len(digits):
            placements.append(tuple(segments))
            return
        if len(segments) >= max_depth:
            return
        for end in range(start + 1, len(digits) + 1):
            segment = digits[start:end]
            if len(segment) > 1 and segment[0] == "0":
                continue
            rec(end, segments + [int(segment)])

    rec(0, [])
    return placements


def _clause_continuation(placement: tuple[int, ...], stack: list[int]) -> list[int] | None:
    """Return the new numbering stack if placement continues stack, else None.

    合法续接（GB/T 1.1 6.1.1 层次编号规则，GBT-H02/H03）：
    - 同级兄弟 +1（含章级：新章 = 当前章 + 1）；
    - 子条：父号 + ".1"；
    - 回退：弹出若干层后最后一段 + 1（如 5.2.3 → 5.3）。
    """
    if not stack:
        return list(placement)
    depth = len(placement)
    if depth == len(stack):
        if placement[:-1] == tuple(stack[:-1]) and placement[-1] == stack[-1] + 1:
            return list(placement)
    elif depth == len(stack) + 1:
        if placement[:-1] == tuple(stack) and placement[-1] == 1:
            return list(placement)
    elif depth < len(stack):
        if placement[:-1] == tuple(stack[: depth - 1]) and placement[-1] == stack[depth - 1] + 1:
            return list(placement)
    return None

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


def _starts_with_han(text: str) -> bool:
    """下一续接行以汉字开头（CJK 句内续接特征）。引用条目/裸标题等以
    拉丁或数字开头的行不续接，避免吞并（2026-08-31 确立断行修复的
    窄化条件）。"""
    return bool(text) and "\u4e00" <= text[0] <= "\u9fff"


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
        self._repair_stray_table_images(blocks, issues)
        self._repair_table_image_layout(blocks, issues)
        self._repair_list_markers(blocks, issues)
        self._repair_clause_numbers(blocks, issues)
        self._repair_heading_levels(blocks, issues)
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
        # 裸条号标题提升预扫描（2026-08-31）：MinerU 偶尔把章条标题抽成裸段落
        # （无 ## 前缀），用"已确认标题祖先链 + 父已提升子级跟随"级联恢复。
        confirmed_numbers, bare_candidates = _bare_heading_candidates(lines)
        bare_promoted = _promoted_bare_headings(confirmed_numbers, bare_candidates)
        blocks: list[Block] = []
        errors: list[str] = []
        warnings: list[str] = []
        pending: dict[str, Directive] = {}
        pending_table_caption: tuple[str, str] | None = None
        pending_table_unit: str | None = None
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
                        # 表题注被提升为标题/普通段落（heading-/paragraph-shaped
                        # caption）已暂存，在此合并进 table attrs；已有显式
                        # caption 时以显式为准，且编号不一致的暂存题注不合并
                        # （防把正文"表5 …"误并进表4 的 directive）。
                        if pending_table_caption is not None:
                            if "caption-number" not in attrs or attrs["caption-number"] == pending_table_caption[0]:
                                attrs.setdefault("caption-number", pending_table_caption[0])
                                attrs.setdefault("caption", pending_table_caption[1])
                            pending_table_caption = None
                        # "单位为毫米" 等单位行折进 unit 属性（渲染右对齐紧贴表格）。
                        if pending_table_unit is not None:
                            attrs.setdefault("unit", pending_table_unit)
                            pending_table_unit = None
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

            # 表题注被抽成普通段落（"表4 安装配合面的同轴度"，GEN-032/033 变体）：
            # 位于 ssir:table directive 之前（可跨空行与"单位为毫米"等单位行）时，
            # 与 heading-shaped 题注一样折进 pending_table_caption，避免渲染出
            # 「表4 安装配合面的同轴度」+「表4」双题注。判定收窄防误伤正文：
            # 单行、无句末标点、长度 ≤ 40、后随（跳过空行/单位行）表格。
            paragraph_caption = TABLE_HEADING_CAPTION_RE.match(line.strip())
            if paragraph_caption and not any(mark in line for mark in "。；，："):
                lookahead = i + 1
                while lookahead < len(lines):
                    stripped = lines[lookahead].strip()
                    if not stripped:
                        lookahead += 1
                        continue
                    if TABLE_UNIT_LINE_RE.match(stripped):
                        lookahead += 1
                        continue
                    break
                next_line = lines[lookahead].strip() if lookahead < len(lines) else ""
                next_table = next_line.startswith("<!-- ssir:table ")
                if not next_table and next_line.startswith("|") and lookahead + 1 < len(lines):
                    next_table = bool(TABLE_SEPARATOR_RE.match(lines[lookahead + 1].strip()))
                if next_table and len(line.strip()) <= 40:
                    pending_table_caption = (paragraph_caption.group(1), paragraph_caption.group(2))
                    warnings.append(
                        f"line {line_no(i)}: paragraph-shaped table caption was folded into the table caption "
                        f"({paragraph_caption.group(1)} {paragraph_caption.group(2)!r})."
                    )
                    i += 1
                    continue

            # "单位为毫米" 等单位行（GEN-032：右对齐置于表格上方紧贴表框）：
            # 独立成段且后随（可跨空行）ssir:table directive 时折进 unit 属性，
            # 否则它会渲染成题注上方的正文段落（位置错误）。
            unit_line = TABLE_UNIT_LINE_RE.match(line.strip())
            if unit_line:
                lookahead = i + 1
                while lookahead < len(lines) and not lines[lookahead].strip():
                    lookahead += 1
                next_line = lines[lookahead].strip() if lookahead < len(lines) else ""
                if next_line.startswith("<!-- ssir:table "):
                    pending_table_unit = unit_line.group(1)
                    warnings.append(
                        f"line {line_no(i)}: table unit line was folded into the table "
                        f"(unit={unit_line.group(1)!r})."
                    )
                    i += 1
                    continue

            start = i
            # 裸条号标题提升（MinerU 把章条标题抽成裸段落，如 QB_T_2946-2020
            # 第 3 章 "3 产品分类和型号命名"）：候选编号是已确认标题的祖先链
            # 或父编号已提升时，提升为 heading，恢复章节结构（GBT-H03 连续
            # 编号、GBT-C06 引用清单边界）。保守：无确认标题时不提升。
            stripped_line = line.strip()
            if bare_promoted and not any((
                DIRECTIVE_RE.match(line),
                HEADING_RE.match(line),
                line.startswith(("$$", ">", "```")),
                IMAGE_RE.match(line),
                CSMParser._is_list_line(line),
            )):
                bare_match = BARE_HEADING_CANDIDATE_RE.match(stripped_line)
                if bare_match and bare_match.group(1) in bare_promoted:
                    level = bare_match.group(1).count(".") + 2
                    blocks.append(
                        Block(
                            kind="heading",
                            start_line=line_no(i),
                            end_line=line_no(i),
                            text=stripped_line,
                            level=level,
                            directive=pending.pop("block", None),
                        )
                    )
                    warnings.append(
                        f"line {line_no(i)}: bare numbered paragraph was promoted to a heading "
                        f"({bare_match.group(1)}, level {level}) by ancestor-chain promotion."
                    )
                    i += 1
                    continue
            # 段落行尾清理：MinerU 行尾常残留 Markdown 硬换行（两个尾随空格），
            # 会导致渲染时段落中途断行（如 "……25%时，  \n审查结论应为不通过"）。
            paragraph_lines = [line.rstrip()]
            i += 1
            while i < len(lines):
                if not lines[i].strip():
                    # 空行续接（6.4.2.4 "……列入多种方法时，\n应指明仲裁方法。"）：
                    # 上一行以连接性标点（，、）结尾且下一非空行不是新块时，视为
                    # 同一段落被 MinerU 误插空行，跳过空行继续收集（示例/注/图/表
                    # 引导语除外）。收窄到弱连接标点（2026-09-02，GB_3100-2026
                    # 3.7/4.2 型）：此前 "不以 。！？ 结尾" 会把术语行
                    # （"一贯单位制 coherent system of units"）与空行后的定义
                    # 正文并成一段；分号 "；" 与冒号 "：" 也排除——";"收尾的行
                    # 是完整分句（裸列项每条以 ；结尾，空行后必为新条目），
                    # "：" 后空行是引导语与裸列项的分界，续接都会吞掉逐条成行
                    # 的版式（4.2 七个定义常量）。
                    lookahead = i
                    while lookahead < len(lines) and not lines[lookahead].strip():
                        lookahead += 1
                    if (
                        lookahead < len(lines)
                        and not self._starts_new_block(lines, lookahead)
                        and paragraph_lines
                        and paragraph_lines[-1].endswith(("，", "、"))
                        and _starts_with_han(lines[lookahead].strip())
                        and not EX_LEAD_RE.match(lines[lookahead].strip())
                        and not NOTE_LEAD_RE.match(lines[lookahead].strip())
                    ):
                        i = lookahead
                        # 续接标记：跨空行续接的行之间不产生 \n（否则渲染折叠成
                        # 空格，词语仍可能断行——"确"+"立"型）。\x00 在 join 时移除。
                        paragraph_lines[-1] += "\x00"
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
            paragraph_text = "\n".join(paragraph_lines).replace("\x00\n", "")
            block_directive = pending.pop("block", None)
            # 裸列项分行（2026-09-02，GB_3100-2026 4.2 七个定义常量型）：源文把
            # 每条独立成行、以 ；/。 收尾的枚举行收集成单段后，_markup 会把行内
            # 换行折叠成空格 → 七个常量挤成一行流。若段落含 ≥2 行且绝大多数行
            # 以句末标点（。；：;.）结尾、其中 ≥2 行以分号收尾，按行拆分为独立
            # 段落块，恢复逐条成行的版式（每条渲染为正文段，首行空两字）。
            enum_lines = [ln.strip().rstrip("$").strip() for ln in paragraph_text.splitlines() if ln.strip()]
            if _is_bare_enumeration(enum_lines):
                for enum_index, enum_line in enumerate(enum_lines):
                    enum_block = Block(
                        kind="paragraph",
                        start_line=line_no(start),
                        end_line=line_no(i - 1),
                        text=enum_line,
                        directive=block_directive if enum_index == 0 else None,
                    )
                    if NOTE_LEAD_RE.match(enum_line):
                        enum_block.kind = "note"
                    blocks.append(enum_block)
                continue
            # 6.3.5.2 类合并：MinerU 把「……告知乘客。6.3.5.2为了确保……」
            # 挤进同一段，导致条号无法回车顶格（GBT-B02）。在句末标点（。；）
            # 之后出现的点分条号处把段落拆分为两个块。
            # 行内注切分（GBT-X04 注引导语）：OCR 常把术语定义后的「注1：…。
            # 注2：…。」合并进定义段（GB_T_20001.6 3.1 型）。在「。注N：」
            # 句界处切分，使注成为独立块（渲染按 GBT-B10 小五号）。
            note_parts = [p.strip() for p in NOTE_SPLIT_RE.split(paragraph_text) if p.strip()]
            if not note_parts:
                note_parts = [paragraph_text.strip()]
            for note_part_index, note_part in enumerate(note_parts):
                parts = [p.strip() for p in CLAUSE_SPLIT_RE.split(note_part) if p.strip()]
                if not parts:
                    parts = [note_part]
                for part_index, part in enumerate(parts):
                    block = Block(
                        kind="paragraph",
                        start_line=line_no(start),
                        end_line=line_no(i - 1),
                        text=part,
                        directive=block_directive if (note_part_index == 0 and part_index == 0) else None,
                    )
                    if EX_HEADER_RE.match(part):
                        # 独立「示例N：」行（附录框式示例的标题）提升为标题，
                        # 使其进入 SSIR 结构树并在示例框内居中（GBT-B11）。
                        block.kind = "heading"
                        block.level = 2
                    elif NOTE_LEAD_RE.match(part):
                        # 独立「注：/注1：」行 → note 块（渲染小五号宋体）。
                        block.kind = "note"
                    blocks.append(block)

        for name, directive in pending.items():
            warnings.append(f"line {directive.line}: ssir:{name} has no following compatible block")
        blocks = _absorb_table_note_spill(blocks, warnings)
        return blocks, errors, warnings

    @staticmethod
    def _is_list_line(line: str) -> bool:
        return bool(UNORDERED_ITEM_RE.match(line) or NUMBERED_ITEM_RE.match(line))

    @staticmethod
    def _parse_list_line(line: str) -> tuple[str, str]:
        unordered = UNORDERED_ITEM_RE.match(line)
        if unordered:
            return unordered.group(1) or unordered.group(2) or unordered.group(3), unordered.group(4)
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
    def _repair_stray_table_images(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """Fold a stray figure between two parts of a split table into the first
        part's last row (GBT-X02 表中图；GB_T_23132-2024 表2 型，CSM-TABLE-002).

        MinerU 跨页表格把某行单元格内的图排在 `<table>` 元素之外，读取顺序上
        表现为：前表 → 裸图 → 续表（题注带"续"）。该图其实是前表最后一行
        缺失的单元格图（旋转式行 试验区域分割 示意图）。全部条件满足才归位，
        否则保守不动：

        - 游离块是单张裸图（figure 块、有 asset_ref、无题注文本）；
        - 其前后相邻块都是表格块；
        - 两表 directive 的 caption-number 相同，且后表题注含"续"（跨页续表）；
        - 前表最后一行既含图单元格又含不含图单元格（说明该行确实有图、只是
          缺了一张——纯文本行不归位，避免把真正独立的图塞进表格）。

        归位目标：前表最后一行第一个不含图、且非首格（行标题列）的单元格；
        无法唯一确定（如多个候选列）时不猜。修复同时删除游离 figure 块，
        canonical/SSIR/render 三侧一致（_render_block 按 rows 输出表格、
        按 asset_ref 输出图，roundtrip 等价保持）。
        """
        cell_image_re = re.compile(r"!\[(?:[^\]]*)\]\(([^)]+)\)")
        for index, block in enumerate(blocks):
            if block.kind != "figure" or "asset_ref" not in block.data:
                continue
            if block.text.strip():
                continue  # 带题注文本的图不归位（是独立图，不是表中图）
            if index == 0 or index + 1 >= len(blocks):
                continue
            first_table = blocks[index - 1]
            second_table = blocks[index + 1]
            if first_table.kind != "table" or second_table.kind != "table":
                continue
            first_directive = first_table.directive
            second_directive = second_table.directive
            if not first_directive or not second_directive:
                continue
            first_number = first_directive.attrs.get("caption-number")
            second_number = second_directive.attrs.get("caption-number")
            second_caption = str(second_directive.attrs.get("caption", ""))
            if not first_number or first_number != second_number or "续" not in second_caption:
                continue
            rows: list[list[str]] = first_table.data.get("rows", [])
            if not rows:
                continue
            last_row = rows[-1]
            if len(last_row) < 2:
                continue
            has_image_cell = any(cell_image_re.search(cell) for cell in last_row)
            if not has_image_cell:
                continue
            # 归位到第一个不含图且非首格（行标题列）的单元格；多个候选不猜。
            target = next(
                (col for col, cell in enumerate(last_row[1:], start=1) if not cell_image_re.search(cell)),
                None,
            )
            if target is None:
                continue
            ref = str(block.data["asset_ref"])
            last_row[target] = (last_row[target].rstrip() + " " if last_row[target].strip() else "") + f"![]({ref})"
            CSMParser._issue(
                issues,
                "CSM-TABLE-002",
                f"Stray figure between two parts of a split table (表{first_number}…续) folded into the last row cell {target + 1} of the first part.",
                line=block.start_line,
                repaired=True,
                repair_action="Moved the bare image into the preceding table's last-row cell in memory.",
            )
            del blocks[index]

    @staticmethod
    def _repair_table_image_layout(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """表中图单元格版式修复（CSM-TABLE-003；GB_T_23132-2024 表2 型）。

        原则：**不把"图在上/文字在下"规定为通用版式**——图与说明文字的
        上下关系是各表原文自行安排的（GB_T_23132 表2 第2列恰好是 上图下
        文字，其它表未必）。渲染端（pdf_renderer._render_cell）按数据
        （cell 文本）顺序忠实复现：cell 为 `![]() 文字` 则图在上文字在下，
        `文字 ![]()` 则文字在上图在下。本修复只纠正**有明确证据**的提取
        错误：

        B. **说明文字错列**（有列间证据）：某行某列是"图+文字"，而该列在
           表内其它数据行都是纯图（该列文字仅此一行）、且该行**前一列**是
           纯图格——说明文字本属于前一列（图旁的说明），被 MinerU 误归到
           后一列。把文字移回前一列纯图格之后，原格只留图。保守条件（全部
           满足才移动，否则不猜）：数据行数 ≥ 2；当前格同时含图与文字；
           该列文字仅此一行（col_text_count == 1）且该列是图列；前一格是
           纯图格（文字落点明确）。

        A. **格内顺序**（仅作为 B 的配套，不独立触发）：只有当该表（或与其
           同 caption-number 的跨页续表）发生了 B 时，才把相关表块的图文混合
           单元格统一重排为 图在前、文字在后——B 移动的文字以"图前文字后"
           落位，同表（含跨页两部分）其它图文混合单元格保持同向才一致。
           **未发生 B 的表不重排**，严格按提取顺序渲染（原文若为文字在上
           图在下，数据保持原样，渲染也保持原样）。

        渲染端保持中立：_render_cell 按 cell 文本顺序流式输出（文字段 →
        图），数据怎么排就怎么渲染。
        """
        cell_image_re = re.compile(r"!\[(?:[^\]]*)\]\(([^)]+)\)")
        # 拆分用无捕获组版本：re.split 遇到捕获组会把捕获内容也放进结果
        # （导致裸 assetRef 泄漏进文字片段）。
        cell_image_split_re = re.compile(r"!\[[^\]]*\]\([^)]+\)")

        def _plain(cell: str) -> str:
            return cell_image_re.sub("", cell).strip()

        def _images(cell: str) -> list[str]:
            return [m.group(0) for m in cell_image_re.finditer(cell)]

        def _reorder_images_first(cell: str) -> str:
            """把全部图片标记提到文字之前（图在上、说明文字在下）。"""
            images = _images(cell)
            if not images:
                return cell
            texts = [part.strip() for part in cell_image_split_re.split(cell) if part.strip()]
            if not texts:
                return cell
            # 已满足"图在前"时不重排（避免无谓改动）。
            first_text = cell_image_split_re.split(cell)[0]
            if not first_text.strip():
                return cell
            joined = " ".join(images) + " " + " ".join(texts)
            return joined.strip()

        table_blocks = [block for block in blocks if block.kind == "table"]
        tables_info: list[tuple[Block, list[list[str]], str | None]] = []
        for block in table_blocks:
            rows = block.data.get("rows", [])
            header_rows = int(block.data.get("header_rows", 1) or 1)
            number = None
            if block.directive:
                number = block.directive.attrs.get("caption-number")
            tables_info.append((block, rows, number))

        # B. 列错位：文字归位到前一列纯图格；收集发生过移动的表（及同号续表）。
        moved_numbers: set[str] = set()
        for block, rows, number in tables_info:
            header_rows = int(block.data.get("header_rows", 1) or 1)
            data_rows = rows[header_rows:]
            if not data_rows:
                continue
            width = len(rows[0]) if rows else 0
            col_text_count = [0] * width
            col_image_count = [0] * width
            for row in data_rows:
                for c, cell in enumerate(row):
                    if c >= width:
                        continue
                    if _plain(cell):
                        col_text_count[c] += 1
                    if _images(cell):
                        col_image_count[c] += 1
            if len(data_rows) < 2:
                continue
            moved = False
            for row in data_rows:
                for c in range(1, len(row)):
                    cell = row[c]
                    if not cell or not _images(cell) or not _plain(cell):
                        continue
                    # 该列文字仅此一行（col_text_count==1，当前格必含文字）、
                    # 且该列是图列 → 说明文字疑似被误归到后一列。
                    if col_text_count[c] != 1 or col_image_count[c] == 0:
                        continue
                    prev = row[c - 1]
                    if not _images(prev) or _plain(prev):
                        continue  # 前一格不是纯图格 → 无明确落点，不猜
                    text = _plain(cell)
                    row[c - 1] = (prev.rstrip() + " " if prev.strip() else "") + text
                    row[c] = " ".join(_images(cell))
                    moved = True
                    CSMParser._issue(
                        issues,
                        "CSM-TABLE-003",
                        f"Cell text at data-row {data_rows.index(row) + 1} col {c + 1} belongs to the image column {c} (image-first layout); moved after the image.",
                        line=block.start_line,
                        repaired=True,
                        repair_action="Moved the text after the image in the previous cell; left only the image in the original cell.",
                    )
            if moved and number:
                moved_numbers.add(number)

        # A. 格内顺序——仅当本表（或同号跨页续表）发生列错位（B）时统一。
        for block, rows, number in tables_info:
            if number is None or number not in moved_numbers:
                continue
            header_rows = int(block.data.get("header_rows", 1) or 1)
            data_rows = rows[header_rows:]
            for row in data_rows:
                for c, cell in enumerate(row):
                    reordered = _reorder_images_first(cell)
                    if reordered != cell:
                        row[c] = reordered
                        CSMParser._issue(
                            issues,
                            "CSM-TABLE-003",
                            f"Cell (row {data_rows.index(row) + 1}, col {c + 1}) reordered to image-first layout (figure above, caption text below).",
                            line=block.start_line,
                            repaired=True,
                            repair_action="Moved image markdown before the caption text in the table cell.",
                        )

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
            # 符号族统一（CSM-OCR-001 扩展）：OCR 把 ●/•/·/○ 混读（源 PDF
            # 同一列表通常全用同一符号，如 GB_T_20001.6 6.1/6.2 全 ● 但 OCR
            # 把部分读成 •），也把同一破折号读成长度不一的横杠（GB_T_1.1-2020
            # 前言 8.3 列项混用 -/—/——/———，GB_T_20001.4/5/6/10 前言清单
            # 同样常见）。破折号族与项目符号族同属"符号型标记"：同一条款下
            # 列表符号应一致，按多数派统一（≥2 且严格多于其余），消除个别
            # 误识项（GBT-C12 列表层次）。字母/数字编号（a）/1））属另一
            # 维度，不参与符号统一，留给下方字形混淆纠正；真嵌套列项
            # （第一层次 —— 项下挂第二层次 · 子项）在扁平块里通常 1:1/2:2
            # 平手，多数派不明确时保守不统一，渲染层仍按层次区分样式。
            symbol_counts: dict[str, int] = {}
            for marker in markers:
                if marker in _BULLET_MARKERS or _DASH_RUN_RE.match(marker):
                    symbol_counts[marker] = symbol_counts.get(marker, 0) + 1
            if len(symbol_counts) >= 2:
                majority = max(symbol_counts, key=lambda k: symbol_counts[k])  # type: ignore[arg-type]
                minority = sum(symbol_counts.values()) - symbol_counts[majority]
                if symbol_counts[majority] >= 2 and symbol_counts[majority] > minority:
                    for target, marker in enumerate(markers):
                        if marker in _BULLET_MARKERS or _DASH_RUN_RE.match(marker):
                            if marker != majority:
                                items[target]["marker"] = majority
                                CSMParser._issue(
                                    issues,
                                    "CSM-OCR-001",
                                    f"List marker {marker!r} unified to {majority!r} "
                                    f"(majority of sibling list symbols).",
                                    line=int(items[target].get("line", 0)) or None,
                                    repaired=True,
                                    repair_action=f"Rewrote marker {marker} to {majority} in memory.",
                                )
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
    def _repair_clause_numbers(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """Re-insert decimal points that a broken text layer dropped from clause
        numbers (CSM-OCR-002).

        文本层损坏型 PDF（如 GB_T_43726-2024）经 MinerU auto 抽取后，标题里的
        点号整段丢失：7.4.2 → 742、5.10 → 510、5.2.1 → 521（数字本身完好，
        只是少了分隔点；同一文档内 7.4.2.2 又可能带点——损坏逐行不一致）。
        本修复用编号连续性约束为每个标题选择唯一合法的拆点：
        - 章级编号连续（1,2,3…，新章 = 当前章 + 1）；
        - 条级编号 = 父号前缀 + 连续兄弟（N.1, N.2…）或子条（父号 + .1）。
        无法唯一/合法拆点时保持原样（不猜测），由 GBT-H03 合规检查记录。
        """
        heading_blocks = [block for block in blocks if block.kind == "heading"]
        stack: list[int] = []
        for block in heading_blocks:
            match = re.match(r"^(\d[\d.]*)(\s*)(.*)$", block.text)
            if not match:
                continue
            raw_number, separator, title = match.group(1), match.group(2), match.group(3)
            placements = _clause_digit_placements(raw_number.replace(".", ""))
            if not placements:
                continue
            chosen: tuple[int, ...] | None = None
            if not stack:
                # 文档首个编号标题：章号取单段（"1 范围" → 1）。
                single = (int(placements[0][0]),) if len(placements[0]) == 1 else None
                if single is not None:
                    chosen = single
            else:
                for placement in placements:
                    if _clause_continuation(placement, stack) is not None:
                        chosen = placement
                        break
            if chosen is None:
                continue
            new_number = ".".join(str(segment) for segment in chosen)
            if new_number == raw_number:
                stack = list(chosen)
                continue
            block.text = f"{new_number}{separator}{title}"
            stack = list(chosen)
            CSMParser._issue(
                issues,
                "CSM-OCR-002",
                f"Clause number {raw_number!r} lost its decimal separators; restored as "
                f"{new_number!r} (continuity with neighbouring headings).",
                line=block.start_line,
                repaired=True,
                repair_action=f"Rewrote heading number {raw_number} to {new_number} in memory.",
            )

    @staticmethod
    def _repair_heading_levels(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """Normalise heading levels by clause-number depth (CSM-OCR-006).

        MinerU 常把章条标题全部压成同一层 ##（扁平树抽取，语料实测 90%+ 的
        标题层级错：GB_T_1.1-2020 176 个编号标题 166 个层级错）。正确层级由
        编号段数决定：章 1 段 → level 2（##）、条 2 段 → level 3（###）、
        子条 3 段 → level 4（####）…… 本修复只提升（当前层级低于编号深度），
        不降低——避免把用户手写的高层标题（如 #### 下的 ###）误压扁，也避免
        与 _repair_clause_numbers 的连续性修复冲突。标题文本本身不变，
        canonical/SSIR/render 三侧一致，roundtrip 等价性保持。
        """
        heading_number = re.compile(r"^(\d+(?:\.\d+)*)\s*[\u4e00-\u9fff（(]")
        for block in blocks:
            if block.kind != "heading" or not block.level:
                continue
            match = heading_number.match(block.text)
            if not match:
                continue
            segments = match.group(1).count(".") + 1
            expected = segments + 1  # 章=2, 条=3, 子条=4, …
            if expected > block.level:
                previous = block.level
                block.level = expected
                CSMParser._issue(
                    issues,
                    "CSM-OCR-006",
                    f"Heading {block.text!r} was flattened by the extractor (level {previous}); "
                    f"restored to level {expected} from its {segments}-segment clause number.",
                    line=block.start_line,
                    repaired=True,
                    repair_action=f"Raised heading level {previous} -> {expected} in memory.",
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
