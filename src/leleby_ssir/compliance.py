"""Rule-based compliance verification (逐条规则验证).

Loads the layered rule packages under ``rules/base/`` and checks a converted
SSIR document against them, producing per-rule findings that are recorded in
the conversion report:

Layer 1  GEN-xxx   rules/base/GB_T_1.1-2020/extraction-rules.yaml
                   (通用抽取/合成/渲染/验证规则)
Layer 2  GBT-xxx   rules/base/GB_T_1.1-2020/requirements.yaml
                   (GB/T 1.1-2020 内容、结构与排版要求)
Layer 3  P10-xxx   rules/base/GB_T_20001.10-2014/requirements.yaml
                   (产品标准专项要求，仅对产品标准类文件加载)

Each finding carries the rule ID, priority (must→fail / should→warning),
a human-readable message and the machine check name, so downstream tools can
trace any violation back to the originating clause of the source standard.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from pathlib import Path
from typing import Any

from .standard_name import name_matches_type, parse_standard_name

RULES_ROOT = Path(__file__).resolve().parents[2] / "rules" / "base"

# Rule IDs referenced from code comments; keep in sync with requirements.yaml.
COVER_REQUIRED_FIELDS = ("standard-number", "title", "ics", "ccs", "publication-date", "effective-date", "issuer")  # GBT-C01
PRODUCT_STANDARD_HINT = re.compile(
    # 产品标准专项 (P10) 适用判定：产品标准、通用/总技术条件、技术条件、
    # 规范等命名都指向可检验的产品要求，覆盖国家/行业/地方/团体/企业标准的
    # 常用命名习惯。
    r"产品标准|product standard|通用技术条件|技术条件|总规范|通用规范|"
    r"technical condition|specification",
    re.IGNORECASE,
)
# 标题中的排除项：方法标准、管理标准等不加载 P10 专项。
_PRODUCT_STANDARD_EXCLUDE = re.compile(r"试验方法|测试方法|检验方法|导则|指南", re.IGNORECASE)


@dataclass(slots=True)
class ComplianceFinding:
    rule_id: str
    rule_set: str
    priority: str
    check: str
    message: str
    status: str = "fail"  # fail | warning

    def to_dict(self) -> dict[str, Any]:
        return {
            "ruleId": self.rule_id,
            "ruleSet": self.rule_set,
            "priority": self.priority,
            "check": self.check,
            "message": self.message,
            "status": self.status,
        }


@dataclass(slots=True)
class ComplianceReport:
    applies: list[str] = field(default_factory=list)  # rule sets actually loaded
    findings: list[ComplianceFinding] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(f.status == "fail" for f in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "appliedRuleSets": self.applies,
            "passed": self.passed,
            "findingCount": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
        }


def _walk_nodes(nodes: list[dict[str, Any]]):
    for node in nodes:
        yield node
        yield from _walk_nodes(node.get("children", []))


def _is_example_content(node: dict[str, Any]) -> bool:
    """True for nodes inside an annex example block (CSM-OCR-006).

    示例块（GB/T 20001 附录编写示例等）的编号是示例文档自带的，不是本标准
    的真实章条；合规检查对它们既不判定也不递归，避免与正文编号混淆。
    """
    return bool(node.get("exampleContent"))


def _node_titles(document: dict[str, Any]) -> list[str]:
    titles: list[str] = []
    for node in _walk_nodes(document.get("structuralRoot", {}).get("children", [])):
        number = str(node.get("number") or "")
        title = str(node.get("title") or "")
        text = f"{number} {title}".strip()
        if text:
            titles.append(text)
        for content in node.get("contentElements", []):
            body = str(content.get("textContent", "")).strip()
            if body:
                titles.append(body)
    return titles


def is_product_standard(metadata: dict[str, Any], document: dict[str, Any]) -> bool:
    """Decide whether the P10 product-standard rule layer applies (P10 meta).

    优先使用标准名称解析结果（standard_name.parse_standard_name）：方法/
    术语/分类/规程/指南标准明确不加载 P10；产品标准明确加载。解析不出
    明确类型（其他/安全/空标题）时回退到标题正则（PRODUCT_STANDARD_HINT）。
    """
    if str(metadata.get("document-type", "")).strip() == "product-standard":
        return True
    title = str(metadata.get("title", ""))
    if title:
        info = parse_standard_name(title)
        if info.standard_type in ("方法标准", "术语标准", "分类标准", "规程标准", "指南标准"):
            return False
        if info.standard_type == "产品标准":
            return True
    title_haystack = "\n".join(
        [
            str(metadata.get("title", "")),
            str(metadata.get("title-en", "")),
        ]
    )
    # Exclusions apply to the TITLE only: body headings like "技术要求和试验
    # 方法" appear in every product standard and must not veto P10.
    if _PRODUCT_STANDARD_EXCLUDE.search(title_haystack):
        return False
    haystack = "\n".join([title_haystack] + _node_titles(document)[:40])
    return bool(PRODUCT_STANDARD_HINT.search(haystack))


# ---------------------------------------------------------------- checks --

def _check_cover_fields(metadata: dict[str, Any], report: ComplianceReport) -> None:
    """GBT-C01: 封面必备信息齐全性。缺失字段同时驱动渲染占位符。"""
    for key in COVER_REQUIRED_FIELDS:
        if not str(metadata.get(key, "")).strip():
            report.findings.append(
                ComplianceFinding(
                    rule_id="GBT-C01",
                    rule_set="GB_T_1.1-2020",
                    priority="must",
                    check="cover-required-field-present",
                    message=f"封面必备信息缺失：{key}（渲染时以占位符标注）",
                )
            )


def _check_element_order(document: dict[str, Any], report: ComplianceReport) -> None:
    """GBT-E03/E05 + GBT-H02: 前言与范围必备；范围应为第 1 章。

    OCR/MinerU 常把标题字间插入空格（"前 言"、"范 围"），比对前先去除空白。
    """
    def norm(text: str) -> str:
        return re.sub(r"\s+", "", text).lower()

    headings = [
        (str(n.get("number") or ""), str(n.get("title") or ""))
        for n in _walk_nodes(document.get("structuralRoot", {}).get("children", []))
        if not _is_example_content(n)
    ]
    title_texts = [norm(t) for _, t in headings]
    if not any(t.startswith("前言") for t in title_texts):
        report.findings.append(
            ComplianceFinding("GBT-E03", "GB_T_1.1-2020", "must", "foreword-present", "必备要素缺失：前言")
        )
    scope_index = next((i for i, t in enumerate(title_texts) if "范围" in t and len(t) <= 6), None)
    if scope_index is None:
        report.findings.append(
            ComplianceFinding("GBT-E05", "GB_T_1.1-2020", "must", "scope-present", "必备要素缺失：范围（第 1 章）")
        )
    else:
        first_numbered = next((n for n, _ in headings if n), "")
        if first_numbered and not first_numbered.startswith("1"):
            report.findings.append(
                ComplianceFinding("GBT-C05", "GB_T_1.1-2020", "must", "scope-is-chapter-1", f"范围应为第 1 章，实际首章编号为 {first_numbered}")
            )


def _check_annex_markers(document: dict[str, Any], report: ComplianceReport) -> None:
    """GBT-C09/C15: 附录应有编号与 (规范性)/(资料性) 标识；字母编号连续。"""
    letters: list[str] = []
    for node in _walk_nodes(document.get("structuralRoot", {}).get("children", [])):
        if node.get("nodeType") != "annex":
            continue
        letter = str(node.get("number") or "").strip()
        title = str(node.get("title") or "").strip()
        if not letter:
            report.findings.append(
                ComplianceFinding("GBT-C09", "GB_T_1.1-2020", "must", "annex-letter-present", f"附录缺少大写字母编号：{title[:30]}")
            )
        elif re.match(r"^[A-Za-z]$", letter):
            letters.append(letter.upper())
        if not re.search(r"[（(](规范性|资料性|推荐性)[)）]", title):
            report.findings.append(
                ComplianceFinding("GBT-C09", "GB_T_1.1-2020", "must", "annex-status-marked", f"附录 {letter or '?'} 缺少 (规范性)/(资料性) 性质标识")
            )
    if letters:
        expected_ord = ord(letters[0])
        missing: list[str] = []
        for ch in letters:
            while expected_ord < ord(ch):
                missing.append(chr(expected_ord))
                expected_ord += 1
            expected_ord = ord(ch) + 1
        if missing:
            report.findings.append(
                ComplianceFinding(
                    "GBT-C15",
                    "GB_T_1.1-2020",
                    "should",
                    "annex-letters-continuous",
                    f"附录字母编号不连续，缺失：{', '.join(missing)}",
                )
            )


def _check_numbering_continuity(document: dict[str, Any], report: ComplianceReport) -> None:
    """GBT-H03: 章条编号连续（不跳号），同级编号不得重复。

    OCR/MinerU 丢失标题行时会出现 4.3.2 → 4.3.4 跳号；字形混淆（O/I/l）可能
    造成重复编号。章级（1、2、3…）为 must，条级（4.1、4.2…）为 should。
    """
    def segments(number: str) -> list[int] | None:
        return [int(part) for part in number.split(".")] if re.match(r"^\d+(?:\.\d+)*$", number) else None

    def check_siblings(children: list[dict[str, Any]]) -> None:
        groups: dict[tuple[int, ...], list[tuple[int, dict[str, Any]]]] = {}
        for child in children:
            segs = segments(str(child.get("number") or ""))
            if not segs:
                continue
            groups.setdefault(tuple(segs[:-1]), []).append((segs[-1], child))
        for prefix, entries in groups.items():
            entries.sort(key=lambda pair: pair[0])
            numbers = [n for n, _ in entries]
            seen: set[int] = set()
            duplicates = sorted({n for n in numbers if n in seen or seen.add(n)})
            missing: list[int] = []
            expected = numbers[0]
            for n in numbers:
                while expected < n:
                    missing.append(expected)
                    expected += 1
                expected = n + 1
            if not missing and not duplicates:
                continue
            depth = len(prefix) + 1
            label = "章" if depth == 1 else "条"
            prefix_text = ".".join(str(p) for p in prefix)
            def number_text(value: int) -> str:
                return f"{prefix_text}.{value}" if prefix_text else str(value)
            details: list[str] = []
            if missing:
                details.append(f"缺失 {', '.join(number_text(m) for m in missing)}")
            if duplicates:
                details.append(f"重复 {', '.join(number_text(d) for d in duplicates)}")
            report.findings.append(
                ComplianceFinding(
                    "GBT-H03",
                    "GB_T_1.1-2020",
                    "must" if depth == 1 else "should",
                    "numbering-continuous",
                    f"{label}编号不连续：{'；'.join(details)}",
                )
            )

    def walk(children: list[dict[str, Any]], parent_number: str | None = None) -> None:
        check_siblings([c for c in children if not _is_example_content(c)])
        for node in children:
            if _is_example_content(node):
                continue
            number = str(node.get("number") or "").strip()
            # 父号前缀一致（2026-08-31，GB_T_43726-2024 条号掉点 4.2.1→421）：
            # 子条号必须以"父号+."开头（GB/T 1.1 7.3.1 点分编号）。OCR 掉点后
            # "421" 挂在本章 "4" 之下，前缀校验直接命中（即使连续性缺口过大
            # 也可能被跳号检查掩盖）。附录子条（A.1 挂 A 下）同样适用。
            if parent_number and number:
                if not number.startswith(parent_number + "."):
                    report.findings.append(
                        ComplianceFinding(
                            "GBT-H03",
                            "GB_T_1.1-2020",
                            "should",
                            "clause-prefix-mismatch",
                            f"条号 {number} 未以父号 {parent_number} 为前缀（点分编号缺失或归属错误）",
                        )
                    )
            walk(node.get("children", []), number or parent_number)

    walk(document.get("structuralRoot", {}).get("children", []))


def _check_list_item_numbering(document: dict[str, Any], report: ComplianceReport) -> None:
    """GBT-C14: 列项编号连续（a、b、c… 或 1、2、3…）。

    OCR 丢行会使 a)、b)、c)、f) 缺 e)；只对纯字母或纯数字编号序列检查，
    混合（如 4.3 的 a)–o) 中混入 l）以外的记号）不判定。
    """
    def sequence(markers: list[str]) -> tuple[str, list[int]] | None:
        values: list[tuple[str, int]] = []
        for marker in markers:
            match = re.match(r"^([A-Za-z]|\d+)[)）]$", marker)
            if not match:
                return None
            token = match.group(1)
            values.append(("letter", ord(token.lower()) - 96) if token.isalpha() else ("digit", int(token)))
        kinds = {kind for kind, _ in values}
        if kinds == {"letter"}:
            return "letters", [value for _, value in values]
        if kinds == {"digit"}:
            return "digits", [value for _, value in values]
        return None

    for node in _walk_nodes(document.get("structuralRoot", {}).get("children", [])):
        if _is_example_content(node):
            continue
        for content in node.get("contentElements", []):
            if content.get("presentationType") != "list":
                continue
            markers = [str(item.get("marker", "")) for item in content.get("listItems", [])]
            seq = sequence(markers)
            if not seq or len(seq[1]) < 2:
                continue
            kind, numbers = seq
            missing: list[int] = []
            expected = numbers[0]
            for n in numbers:
                while expected < n:
                    missing.append(expected)
                    expected += 1
                expected = n + 1
            if not missing:
                continue
            missing_text = ", ".join(chr(m + 96) for m in missing) if kind == "letters" else ", ".join(str(m) for m in missing)
            report.findings.append(
                ComplianceFinding(
                    "GBT-C14",
                    "GB_T_1.1-2020",
                    "should",
                    "list-item-numbers-continuous",
                    f"列表项编号缺失：{missing_text}（「{str(node.get('title') or '')[:24]}」内）",
                )
            )


def _check_glyph_confusion(document: dict[str, Any], report: ComplianceReport) -> None:
    """GBT-C16: 编号/标准号中 O/I/l 疑似 0/1 的字形混淆。

    覆盖两种场景：标题开头形如 "4.O.1" 的编号前缀（O/I/l 混入数字），以及
    规范性引用等正文中的标准号（如 "GB/T 5O89"）。仅当同时含数字与混淆字符时
    才判定，避免误报 "O" 字母单词。
    """
    confusable_prefix = re.compile(r"^([0-9OIl.．]+)")
    standard_number_pattern = re.compile(r"(?:GB/T|GB|JB/T|SJ/T|DB\d*/T|Q/|T/|ISO|IEC)[\s/]*([0-9OIl.．\-]+)")
    has_confusables = lambda token: bool(re.search(r"[OIl]", token) and re.search(r"\d", token))

    heading_hits: list[str] = []
    reference_hits: list[str] = []
    for node in _walk_nodes(document.get("structuralRoot", {}).get("children", [])):
        number = str(node.get("number") or "")
        title = str(node.get("title") or "")
        if not number:
            match = confusable_prefix.match(title)
            if match and has_confusables(match.group(1)):
                heading_hits.append(match.group(1))
        for content in node.get("contentElements", []):
            text = str(content.get("textContent", ""))
            for match in standard_number_pattern.finditer(text):
                if has_confusables(match.group(1)):
                    reference_hits.append(match.group(0))
    if heading_hits:
        report.findings.append(
            ComplianceFinding(
                "GBT-C16",
                "GB_T_1.1-2020",
                "should",
                "number-glyph-confusion",
                f"{len(heading_hits)} 处标题编号疑似字形混淆（O/I/l 疑似 0/1）：{', '.join(heading_hits[:3])}",
            )
        )
    if reference_hits:
        report.findings.append(
            ComplianceFinding(
                "GBT-C16",
                "GB_T_1.1-2020",
                "should",
                "standard-number-glyph-confusion",
                f"{len(reference_hits)} 处标准号疑似字形混淆（O/I/l 疑似 0/1）：{', '.join(reference_hits[:3])}",
            )
        )


def _check_reference_chapter(document: dict[str, Any], report: ComplianceReport) -> None:
    """GBT-C06: 规范性引用文件应为第 2 章，由规定引导语引出，清单不加序号。

    无规范性引用时写明"本文件没有规范性引用文件。"。仅检查结构与引导语，
    不校验清单条目本身的准确性。
    """
    root_children = document.get("structuralRoot", {}).get("children", [])
    chapter2 = next((c for c in root_children if str(c.get("number") or "").strip() == "2"), None)
    if chapter2 is None:
        report.findings.append(
            ComplianceFinding(
                "GBT-C06", "GB_T_1.1-2020", "should", "reference-chapter-second",
                "规范性引用文件应为第 2 章，但未找到编号为 2 的章",
            )
        )
        return
    title = str(chapter2.get("title") or "")
    if "规范性引用文件" not in title:
        report.findings.append(
            ComplianceFinding(
                "GBT-C06", "GB_T_1.1-2020", "should", "reference-chapter-title",
                f"第 2 章标题应为\"规范性引用文件\"，实际为：{title}",
            )
        )
    texts = [str(c.get("textContent", "")) for c in chapter2.get("contentElements", [])]
    all_text = " ".join(texts)
    if "没有规范性引用文件" in all_text:
        return  # 明确声明无引用，不再要求引导语
    # 引导语随导则版本变化：GB/T 1.1-2020 "下列文件中的内容通过文中的规范性
    # 引用而构成本文件必不可少的条款…"；2009 版 "下列文件对于本文件的应用是
    # 必不可少的…"。以"下列文件"开头的段落即视为引导语。
    if not any(t.startswith("下列文件") for t in texts):
        report.findings.append(
            ComplianceFinding(
                "GBT-C06", "GB_T_1.1-2020", "should", "reference-lead-in",
                "规范性引用文件章缺少规定引导语（\"下列文件…\"），或未声明\"本文件没有规范性引用文件\"",
            )
        )
    for content in chapter2.get("contentElements", []):
        if content.get("presentationType") == "list":
            for item in content.get("listItems", []):
                marker = str(item.get("marker", ""))
                if marker and not marker.startswith("-") and marker not in ("—", "——"):
                    report.findings.append(
                        ComplianceFinding(
                            "GBT-C06", "GB_T_1.1-2020", "should", "reference-list-unordered",
                            f"规范性引用文件清单不应加序号，但列表项使用标记 {marker}",
                        )
                    )
                _check_reference_item_number(item.get("text", ""), report)
        elif content.get("presentationType") == "paragraph":
            text = str(content.get("textContent", "")).strip()
            if text and not text.startswith("下列文件") and "没有规范性引用文件" not in text:
                _check_reference_item_number(text, report)


_STANDARD_NUMBER_RE = re.compile(
    r"(?:GB/T|GB/Z|GB|JB/T|JB|DB\d{1,2}/T|QB/T|QB|SJ/T|SJ|DL/T|NY/T|HG/T|FZ/T|WS/T|YD/T|GA/T|CJ/T|JG/T|TB/T|SH/T|JC/T|EJ/T|MT/T|YY/T|YY|HJ/T|HJ|T/|Q/|ISO|IEC)\s*[A-Z0-9][A-Z0-9.\-—–]*\s*\d"
)


def _check_reference_item_number(text: str, report: ComplianceReport) -> None:
    """GBT-C06: 引用清单条目必须含标准文件编号（GB/T ×××—××××）。

    2026-08-31（GB_T_43726-2024）：文本层损坏时标准号整段丢失（raw 里
    "/ — 环境试验 第 部分:…"），条目缺编号即提示，便于强制 OCR 后复核。
    """
    if not text:
        return
    if not _STANDARD_NUMBER_RE.search(text):
        report.findings.append(
            ComplianceFinding(
                "GBT-C06", "GB_T_1.1-2020", "should", "reference-item-number",
                f"规范性引用清单条目缺少标准文件编号：{text[:40]}",
            )
        )


def _check_sibling_heading_titles(document: dict[str, Any], report: ComplianceReport) -> None:
    """GBT-H04: 同一层次各条有无标题应一致；无标题条不应再分条。"""
    root_children = document.get("structuralRoot", {}).get("children", [])

    def walk(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            if _is_example_content(node):
                continue
            kids = node.get("children", [])
            if kids:
                titled = [c for c in kids if not _is_example_content(c) and str(c.get("title") or "").strip()]
                untitled = [c for c in kids if not _is_example_content(c) and not str(c.get("title") or "").strip()]
                if titled and untitled:
                    report.findings.append(
                        ComplianceFinding(
                            "GBT-H04", "GB_T_1.1-2020", "should", "sibling-heading-titles-consistent",
                            f"「{node.get('title') or node.get('number') or ''}」下同一层次 "
                            f"{len(titled)} 个条有标题、{len(untitled)} 个条无标题，应一致",
                        )
                    )
                for child in untitled:
                    if child.get("children"):
                        report.findings.append(
                            ComplianceFinding(
                                "GBT-H04", "GB_T_1.1-2020", "should", "untitled-clause-keeps-children",
                                f"无标题条 {child.get('number')} 不应再分条",
                            )
                        )
                walk(kids)

    walk(root_children)


def _check_hanging_paragraphs(document: dict[str, Any], report: ComplianceReport) -> None:
    """GBT-H05: 不宜设悬置段——章标题与条之间、条标题与下一层次条之间的段。"""
    for node in _walk_nodes(document.get("structuralRoot", {}).get("children", [])):
        if _is_example_content(node):
            continue
        if not node.get("children"):
            continue
        paragraphs = [
            c for c in node.get("contentElements", [])
            if c.get("presentationType") == "paragraph" and str(c.get("textContent", "")).strip()
        ]
        if paragraphs:
            label = f"{node.get('number')} {node.get('title')}".strip()
            report.findings.append(
                ComplianceFinding(
                    "GBT-H05", "GB_T_1.1-2020", "should", "no-hanging-paragraph",
                    f"「{label}」标题与其子条之间存在悬置段（{len(paragraphs)} 段），不宜设悬置段",
                )
            )


def _check_note_example_formats(document: dict[str, Any], report: ComplianceReport) -> None:
    """GBT-X03/X05: 注以"注："/"注1："起始（多个注编号从 1 起）；示例以
    "示例："/"示例1："起始。"""
    for node in _walk_nodes(document.get("structuralRoot", {}).get("children", [])):
        for content in node.get("contentElements", []):
            kind = content.get("presentationType")
            text = str(content.get("textContent", "")).strip()
            if not text:
                continue
            if kind == "note":
                if not text.startswith(("注：", "注:", "注1：", "注1:", "注２：", "注2：")):
                    report.findings.append(
                        ComplianceFinding(
                            "GBT-X03", "GB_T_1.1-2020", "should", "note-lead-in",
                            f"注应以\"注：\"（单个）或\"注1：\"（多个，编号从 1 起）起始：{text[:24]}",
                        )
                    )
            elif kind == "example":
                if not text.startswith(("示例：", "示例:", "示例1：", "示例1:")):
                    report.findings.append(
                        ComplianceFinding(
                            "GBT-X05", "GB_T_1.1-2020", "should", "example-lead-in",
                            f"示例应以\"示例：\"（单个）或\"示例1：\"（多个）起始：{text[:24]}",
                        )
                    )


def _check_footnote_numbering(document: dict[str, Any], report: ComplianceReport) -> None:
    """GBT-X04: 条文脚注编号 1)、2)… 从前言起全文连续；图表脚注解释行标记为
    小写拉丁字母 a)、b) 且与标记成对（GB/T 1.1 9.12.1、9.12.2）。"""
    numbers: list[int] = []
    for node in _walk_nodes(document.get("structuralRoot", {}).get("children", [])):
        for content in node.get("contentElements", []):
            if content.get("presentationType") != "footnote":
                continue
            match = re.match(r"^\s*(\d+)[)）]", str(content.get("textContent", "")))
            if match:
                numbers.append(int(match.group(1)))
    if numbers:
        expected = 1
        for n in numbers:
            if n != expected:
                report.findings.append(
                    ComplianceFinding(
                        "GBT-X04", "GB_T_1.1-2020", "should", "footnote-numbers-continuous",
                        f"条文脚注编号应从前言起全文连续（1)、2)…），发现 {n}（应为 {expected}）",
                    )
                )
                break
            expected = n + 1
    # 图表脚注解释行（"a 说明" / "a说明"）：标记必须为小写拉丁字母（9.12.2）。
    # 2026-08-31（GB_T_43726-2024 表6）：大写 "A 相" 等是内容不是脚注标记，
    # 解释行若出现大写字母开头则提示（脚注由标记+解释成对组成）。
    for node in _walk_nodes(document.get("structuralRoot", {}).get("children", [])):
        for content in node.get("contentElements", []):
            if content.get("presentationType") != "paragraph":
                continue
            text = str(content.get("textContent", "")).strip()
            match = re.match(r"^([Ａ-ＺA-Z])(?:[ \u3000]+)([\u4e00-\u9fff])", text)
            if match:
                report.findings.append(
                    ComplianceFinding(
                        "GBT-X04", "GB_T_1.1-2020", "should", "footnote-marker-lowercase",
                        f"图表脚注解释行标记应为小写拉丁字母，实际为大写 {match.group(1)}：{text[:30]}",
                    )
                )


def _check_table_figure_numbers(document: dict[str, Any], registries: dict[str, list[dict[str, Any]]], report: ComplianceReport) -> None:
    """GBT-X01/X02: 图、表均应有连续编号。"""
    for table in registries.get("tables", []):
        if not str(table.get("number") or "").strip():
            report.findings.append(
                ComplianceFinding("GBT-X02", "GB_T_1.1-2020", "must", "table-number-present", f"表格缺少编号：{str(table.get('caption') or table.get('id'))[:30]}")
            )
    for figure in registries.get("figures", []):
        if not str(figure.get("number") or "").strip():
            report.findings.append(
                ComplianceFinding("GBT-X01", "GB_T_1.1-2020", "should", "figure-number-present", f"图缺少编号：{str(figure.get('caption') or figure.get('id'))[:30]}")
            )


def _check_numeric_requirements_have_units(document: dict[str, Any], report: ComplianceReport) -> None:
    """P10-R02: 定量要求必须带单位（数值后紧跟 ≤/≥ 或要求型措辞时检查）。"""
    unit = r"(?:dB\(A\)|r/min|MPa|kV|mA|kW|mm|min|%|℃|Pa|K|V|A|W|m|h|s|g|kg|t|L|ml)"
    pattern = re.compile(rf"(?:不大于|不小于|不超过|≥|≤)[^。；;\n]*?\d+(?:\.\d+)?(?!\s*{unit})(?!\s*(?:倍|个|次|片|只|根|条|号))")
    hits = 0
    for node in _walk_nodes(document.get("structuralRoot", {}).get("children", [])):
        for content in node.get("contentElements", []):
            text = str(content.get("textContent", ""))
            hit = pattern.findall(text)
            if hit:
                hits += len(hit)
    if hits:
        report.findings.append(
            ComplianceFinding(
                "P10-R02",
                "GB_T_20001.10-2014",
                "must",
                "numeric-requirements-carry-units",
                f"{hits} 处定量要求疑似缺单位（“不大于/不小于/≤/≥ + 裸数值”）",
            )
        )


def _check_standard_name(metadata: dict[str, Any], report: ComplianceReport) -> None:
    """GBT-N01/N02: 标准名称与功能类型一致性 + 标准化主对象识别。

    使用 standard_name 解析器（后缀定类型、中缀定主语、含"用"定场合）：
    - GBT-N01：名称必须体现其功能类型（术语标准应含"术语/定义/词汇"、
      方法标准应含"试验/测定/测试/校准/计算/测量/检验"、分类标准应含
      "分类/编码/命名/型号"、规程标准应含"规程"、指南标准应含"指南/
      导则"、安全标准应含"安全"、产品标准应含"条件/规范/通则/总则/
      要求/限值"），对应 GB/T 1.1-2020 6.1.4 命名要求；
    - GBT-N02：应能识别出标准化主对象（主语），识别失败提示人工核查。
    """
    title = str(metadata.get("title", "")).strip()
    if not title:
        return
    info = parse_standard_name(title)
    if not name_matches_type(info):
        report.findings.append(
            ComplianceFinding(
                "GBT-N01",
                "GB_T_1.1-2020",
                "must",
                "name-matches-type",
                f"标准名称与功能类型不符：识别为「{info.standard_type}」（命中 "
                f"「{info.type_basis}」），但名称未体现该类型的必备关键词：{title}",
            )
        )
    if not info.subject:
        report.findings.append(
            ComplianceFinding(
                "GBT-N02",
                "GB_T_1.1-2020",
                "should",
                "subject-identified",
                f"未能从标准名称识别出标准化主对象，需人工核查：{title}",
            )
        )


def _hyphenate(key: str) -> str:
    """camelCase -> hyphen-case so metadata lookups are key-name agnostic.

    ``publicationDate`` -> ``publication-date``, ``titleEn`` -> ``title-en``.
    """
    return re.sub(r"(?<!^)(?=[A-Z])", "-", key).lower()


def verify_compliance(document: dict[str, Any], metadata: dict[str, Any] | None = None, rules_root: Path | None = None) -> ComplianceReport:
    """Run all applicable rule layers against a parsed SSIR document."""
    root = rules_root or RULES_ROOT
    metadata = metadata or {}
    common = document.get("metadata", {}).get("common", {})
    flat_metadata = {
        **{_hyphenate(k): v for k, v in common.items()},
        **metadata,
        "standard-number": document.get("metadata", {}).get("standard", {}).get("standardNumber", ""),
        "ics": document.get("metadata", {}).get("standard", {}).get("ics", ""),
        "ccs": document.get("metadata", {}).get("standard", {}).get("ccs", ""),
    }
    report = ComplianceReport(applies=["GB_T_1.1-2020"])

    # Layer 2: GB/T 1.1-2020 requirements (always applied).
    _check_cover_fields(flat_metadata, report)
    _check_element_order(document, report)
    _check_annex_markers(document, report)
    _check_numbering_continuity(document, report)
    _check_list_item_numbering(document, report)
    _check_glyph_confusion(document, report)
    _check_reference_chapter(document, report)
    _check_sibling_heading_titles(document, report)
    _check_hanging_paragraphs(document, report)
    _check_note_example_formats(document, report)
    _check_footnote_numbering(document, report)
    registries = {"tables": document.get("tables", []), "figures": document.get("figures", [])}
    _check_table_figure_numbers(document, registries, report)
    _check_standard_name(flat_metadata, report)

    # Layer 3: GB/T 20001.10 product-standard requirements.
    if is_product_standard({"document-type": metadata.get("document-type", ""), "title": flat_metadata.get("title", "")}, document):
        report.applies.append("GB_T_20001.10-2014")
        _check_numeric_requirements_have_units(document, report)

    # Priority-to-status normalisation: only must rules fail the report;
    # should/may rules produce warnings (GEN 优先级 措辞分级).
    for finding in report.findings:
        if finding.priority != "must" and finding.status == "fail":
            finding.status = "warning"

    return report


def compliance_issues(report: ComplianceReport) -> list["CSMIssue"]:
    """Convert compliance findings into conversion/parse-report issue entries."""
    from .parser import CSMIssue

    return [
        CSMIssue(
            code=f"COMPLIANCE::{finding.rule_id}",
            severity="error" if finding.status == "fail" else "warning",
            message=f"[{finding.rule_id}/{finding.priority}] {finding.message}",
        )
        for finding in report.findings
    ]
