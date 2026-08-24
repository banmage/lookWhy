"""Regression tests for layered rule compliance verification (compliance.py)."""

from __future__ import annotations

import unittest

from leleby_ssir.compliance import verify_compliance


def _document(
    *,
    common: dict | None = None,
    standard: dict | None = None,
    children: list[dict] | None = None,
    tables: list[dict] | None = None,
    figures: list[dict] | None = None,
) -> dict:
    return {
        "metadata": {
            "common": {
                "documentIdentifier": "GB/T 12345-2026",
                "title": "示例产品标准",
                **(common or {}),
            },
            "standard": {
                "standardNumber": "GB/T 12345-2026",
                "ics": "01.120",
                "ccs": "A 00",
                **(standard or {}),
            },
        },
        "structuralRoot": {
            # 默认只含合规的"范围"第 1 章；显式传 children 时完全替换默认值。
            "children": children
            if children is not None
            else [
                {
                    "nodeType": "clause",
                    "number": "1",
                    "title": "范围",
                    "contentElements": [{"presentationType": "paragraph", "textContent": "本文件规定了示例产品的技术要求。"}],
                },
            ]
        },
        "tables": tables or [],
        "figures": figures or [],
    }


class CoverFieldTests(unittest.TestCase):
    def test_camel_case_dates_do_not_trigger_false_missing_finding(self) -> None:
        """GBT-C01 must accept camelCase common keys (publicationDate/effectiveDate)."""
        doc = _document(
            common={
                "publicationDate": "2026-01-01",
                "effectiveDate": "2026-07-01",
                "issuer": "国家市场监督管理总局 国家标准化管理委员会",
            }
        )
        report = verify_compliance(doc)
        date_findings = [
            f
            for f in report.findings
            if f.rule_id == "GBT-C01" and ("publication" in f.message or "effective" in f.message)
        ]
        self.assertEqual(date_findings, [], f"camelCase dates were reported missing: {[f.message for f in date_findings]}")

    def test_missing_ics_flagged_and_recorded(self) -> None:
        doc = _document(standard={"standardNumber": "GB/T 12345-2026", "ics": "", "ccs": ""})
        report = verify_compliance(doc)
        ics = [f for f in report.findings if f.rule_id == "GBT-C01" and "ics" in f.message]
        self.assertEqual(len(ics), 1)
        self.assertEqual(ics[0].status, "fail")
        self.assertEqual(ics[0].check, "cover-required-field-present")

    def test_hyphenated_metadata_override_accepted(self) -> None:
        doc = _document(common={})
        report = verify_compliance(doc, metadata={"publication-date": "2026-01-01", "effective-date": "2026-07-01"})
        date_findings = [
            f
            for f in report.findings
            if f.rule_id == "GBT-C01" and ("publication" in f.message or "effective" in f.message)
        ]
        self.assertEqual(date_findings, [])


class ElementOrderTests(unittest.TestCase):
    def test_scope_must_be_chapter_1(self) -> None:
        doc = _document(
            children=[
                {"nodeType": "clause", "number": "3", "title": "术语和定义", "contentElements": []},
                {"nodeType": "clause", "number": "1", "title": "范围", "contentElements": []},
            ]
        )
        report = verify_compliance(doc)
        scope = [f for f in report.findings if f.rule_id == "GBT-C05"]
        self.assertEqual(len(scope), 1)
        self.assertIn("实际首章编号为 3", scope[0].message)


class ProductStandardLayerTests(unittest.TestCase):
    def test_product_standard_applies_p10_and_flags_bare_numeric_requirement(self) -> None:
        doc = _document(
            common={"title": "示例产品标准", "titleEn": "Example product standard"},
            children=[
                {
                    "nodeType": "clause",
                    "number": "5",
                    "title": "技术要求",
                    "contentElements": [
                        {"presentationType": "paragraph", "textContent": "额定电压不大于 220，额定电流不小于 10。"},
                    ],
                }
            ],
        )
        report = verify_compliance(doc)
        self.assertIn("gbt-20001.10-2014", report.applies)
        p10 = [f for f in report.findings if f.rule_id == "P10-R02"]
        self.assertEqual(len(p10), 1)
        self.assertIn("缺单位", p10[0].message)

    def test_non_product_standard_skips_p10(self) -> None:
        doc = _document(common={"title": "标准化工作导则"})
        report = verify_compliance(doc)
        self.assertNotIn("gbt-20001.10-2014", report.applies)
        self.assertFalse([f for f in report.findings if f.rule_id == "P10-R02"])


if __name__ == "__main__":
    unittest.main()
