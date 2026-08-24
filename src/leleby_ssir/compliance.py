"""Rule-based compliance verification (逐条规则验证).

Loads the layered rule packages under ``rules/base/`` and checks a converted
SSIR document against them, producing per-rule findings that are recorded in
the conversion report:

Layer 1  GEN-xxx   rules/base/gbt-1-1-2020/extraction-rules.yaml
                   (通用抽取/合成/渲染/验证规则)
Layer 2  GBT-xxx   rules/base/gbt-1-1-2020/requirements.yaml
                   (GB/T 1.1-2020 内容、结构与排版要求)
Layer 3  P10-xxx   rules/base/gbt-20001.10-2014/requirements.yaml
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

RULES_ROOT = Path(__file__).resolve().parents[2] / "rules" / "base"

# Rule IDs referenced from code comments; keep in sync with requirements.yaml.
COVER_REQUIRED_FIELDS = ("standard-number", "title", "ics", "ccs", "publication-date", "effective-date", "issuer")  # GBT-C01
PRODUCT_STANDARD_HINT = re.compile(r"产品标准|product standard", re.IGNORECASE)


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
    """Decide whether the P10 product-standard rule layer applies (P10 meta)."""
    if str(metadata.get("document-type", "")).strip() == "product-standard":
        return True
    haystack = "\n".join(
        [
            str(metadata.get("title", "")),
            str(metadata.get("title-en", "")),
        ]
        + _node_titles(document)[:40]
    )
    return bool(PRODUCT_STANDARD_HINT.search(haystack))


# ---------------------------------------------------------------- checks --

def _check_cover_fields(metadata: dict[str, Any], report: ComplianceReport) -> None:
    """GBT-C01: 封面必备信息齐全性。缺失字段同时驱动渲染占位符。"""
    for key in COVER_REQUIRED_FIELDS:
        if not str(metadata.get(key, "")).strip():
            report.findings.append(
                ComplianceFinding(
                    rule_id="GBT-C01",
                    rule_set="gbt-1-1-2020",
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
    ]
    title_texts = [norm(t) for _, t in headings]
    if not any(t.startswith("前言") for t in title_texts):
        report.findings.append(
            ComplianceFinding("GBT-E03", "gbt-1-1-2020", "must", "foreword-present", "必备要素缺失：前言")
        )
    scope_index = next((i for i, t in enumerate(title_texts) if "范围" in t and len(t) <= 6), None)
    if scope_index is None:
        report.findings.append(
            ComplianceFinding("GBT-E05", "gbt-1-1-2020", "must", "scope-present", "必备要素缺失：范围（第 1 章）")
        )
    else:
        first_numbered = next((n for n, _ in headings if n), "")
        if first_numbered and not first_numbered.startswith("1"):
            report.findings.append(
                ComplianceFinding("GBT-C05", "gbt-1-1-2020", "must", "scope-is-chapter-1", f"范围应为第 1 章，实际首章编号为 {first_numbered}")
            )


def _check_annex_markers(document: dict[str, Any], report: ComplianceReport) -> None:
    """GBT-C09: 每个附录应有编号、(规范性)/(资料性) 标识及标题。"""
    for node in _walk_nodes(document.get("structuralRoot", {}).get("children", [])):
        if node.get("nodeType") != "annex":
            continue
        letter = str(node.get("number") or "").strip()
        title = str(node.get("title") or "").strip()
        if not letter:
            report.findings.append(
                ComplianceFinding("GBT-C09", "gbt-1-1-2020", "must", "annex-letter-present", f"附录缺少大写字母编号：{title[:30]}")
            )
        if not re.search(r"[（(](规范性|资料性|推荐性)[)）]", title):
            report.findings.append(
                ComplianceFinding("GBT-C09", "gbt-1-1-2020", "must", "annex-status-marked", f"附录 {letter or '?'} 缺少 (规范性)/(资料性) 性质标识")
            )


def _check_table_figure_numbers(document: dict[str, Any], registries: dict[str, list[dict[str, Any]]], report: ComplianceReport) -> None:
    """GBT-X01/X02: 图、表均应有连续编号。"""
    for table in registries.get("tables", []):
        if not str(table.get("number") or "").strip():
            report.findings.append(
                ComplianceFinding("GBT-X02", "gbt-1-1-2020", "must", "table-number-present", f"表格缺少编号：{str(table.get('caption') or table.get('id'))[:30]}")
            )
    for figure in registries.get("figures", []):
        if not str(figure.get("number") or "").strip():
            report.findings.append(
                ComplianceFinding("GBT-X01", "gbt-1-1-2020", "should", "figure-number-present", f"图缺少编号：{str(figure.get('caption') or figure.get('id'))[:30]}")
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
                "gbt-20001.10-2014",
                "must",
                "numeric-requirements-carry-units",
                f"{hits} 处定量要求疑似缺单位（“不大于/不小于/≤/≥ + 裸数值”）",
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
    report = ComplianceReport(applies=["gbt-1-1-2020"])

    # Layer 2: GB/T 1.1-2020 requirements (always applied).
    _check_cover_fields(flat_metadata, report)
    _check_element_order(document, report)
    _check_annex_markers(document, report)
    registries = {"tables": document.get("tables", []), "figures": document.get("figures", [])}
    _check_table_figure_numbers(document, registries, report)

    # Layer 3: GB/T 20001.10 product-standard requirements.
    if is_product_standard({"document-type": metadata.get("document-type", ""), "title": flat_metadata.get("title", "")}, document):
        report.applies.append("gbt-20001.10-2014")
        _check_numeric_requirements_have_units(document, report)

    # Priority-to-status normalisation: only must rules fail the report;
    # should/may rules produce warnings (GEN 优先级 措辞分级).
    for finding in report.findings:
        if finding.priority != "must" and finding.status == "fail":
            finding.status = "warning"

    return report


def compliance_issues(report: ComplianceReport) -> list["CSMIssue"]:
    """Convert compliance findings into conversion-report issue entries."""
    from .parser import CSMIssue

    return [
        CSMIssue(
            code=f"COMPLIANCE::{finding.rule_id}",
            severity="error" if finding.status == "fail" else "warning",
            message=f"[{finding.rule_id}/{finding.priority}] {finding.message}",
        )
        for finding in report.findings
    ]
