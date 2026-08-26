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


class StructureComplianceTests(unittest.TestCase):
    def test_reference_chapter_title_and_lead_in(self) -> None:
        # GBT-C06：第 2 章标题应为"规范性引用文件"，且带规定引导语。
        doc = _document(children=[
            _clause("1", "范围"),
            _clause("2", "引用文件"),  # 标题不符
        ])
        report = verify_compliance(doc)
        c06 = [f for f in report.findings if f.rule_id == "GBT-C06"]
        self.assertTrue(any("标题" in f.message for f in c06))
        self.assertTrue(any("引导语" in f.message for f in c06))

    def test_reference_no_normative_references_declared_passes(self) -> None:
        doc = _document(children=[
            _clause("1", "范围"),
            _clause("2", "规范性引用文件", content=[
                {"presentationType": "paragraph", "textContent": "本文件没有规范性引用文件。"},
            ]),
        ])
        report = verify_compliance(doc)
        self.assertFalse([f for f in report.findings if f.rule_id == "GBT-C06"])

    def test_sibling_heading_titles_inconsistent(self) -> None:
        # GBT-H04：同一层次各条有无标题应一致。
        doc = _document(children=[
            _clause("1", "范围"),
            _clause("4", "技术要求", children=[
                _clause("4.1", "现场运行条件"),
                _clause("4.2", ""),  # 无标题
                _clause("4.3", "安装尺寸"),
            ]),
        ])
        report = verify_compliance(doc)
        h04 = [f for f in report.findings if f.rule_id == "GBT-H04"]
        self.assertTrue(any("应一致" in f.message for f in h04))

    def test_hanging_paragraph_flagged(self) -> None:
        # GBT-H05：章/条标题与子条之间存在段 = 悬置段。
        doc = _document(children=[
            _clause("1", "范围"),
            _clause("4", "技术要求", children=[_clause("4.1", "现场运行条件")]),
        ])
        report = verify_compliance(doc)
        h05 = [f for f in report.findings if f.rule_id == "GBT-H05"]
        self.assertEqual(len(h05), 1)
        self.assertIn("悬置段", h05[0].message)

    def test_note_and_example_lead_in_checked(self) -> None:
        # GBT-X03/X05：注/示例必须用规定引导语起始。
        doc = _document(children=[
            _clause("1", "范围", content=[
                {"presentationType": "paragraph", "textContent": "内容。"},
                {"presentationType": "note", "textContent": "补充说明。"},
                {"presentationType": "example", "textContent": "某示例。"},
                {"presentationType": "note", "textContent": "注：正确。"},
                {"presentationType": "example", "textContent": "示例1：正确。"},
            ]),
        ])
        report = verify_compliance(doc)
        x03 = [f for f in report.findings if f.rule_id == "GBT-X03"]
        x05 = [f for f in report.findings if f.rule_id == "GBT-X05"]
        self.assertTrue(any("注：" in f.message for f in x03))
        self.assertTrue(any("示例：" in f.message for f in x05))

    def test_footnote_numbering_continuous(self) -> None:
        # GBT-X04：条文脚注编号 1)、2)… 全文连续。
        doc = _document(children=[
            _clause("1", "范围", content=[
                {"presentationType": "paragraph", "textContent": "内容。"},
                {"presentationType": "footnote", "textContent": "1) 说明一。"},
                {"presentationType": "footnote", "textContent": "3) 说明三。"},  # 跳号
            ]),
        ])
        report = verify_compliance(doc)
        x04 = [f for f in report.findings if f.rule_id == "GBT-X04"]
        self.assertTrue(any("连续" in f.message for f in x04))


def _clause(number: str, title: str = "范围", *, children: list[dict] | None = None, content: list[dict] | None = None) -> dict:
    return {
        "nodeType": "clause",
        "number": number,
        "title": title,
        "contentElements": content or [{"presentationType": "paragraph", "textContent": "内容。"}],
        "children": children or [],
    }


class NumberingContinuityTests(unittest.TestCase):
    def test_chapter_gap_is_must_and_clause_gap_is_should(self) -> None:
        doc = _document(children=[
            _clause("1", "范围"),
            _clause("2", "规范性引用文件"),
            _clause("4", "技术要求"),  # 缺第 3 章
        ])
        report = verify_compliance(doc)
        h03 = [f for f in report.findings if f.rule_id == "GBT-H03"]
        self.assertEqual(len(h03), 1)
        self.assertEqual(h03[0].priority, "must")
        self.assertIn("缺失 3", h03[0].message)

    def test_clause_numbering_gap_flagged_as_should(self) -> None:
        doc = _document(children=[
            _clause("1", "范围"),
            _clause("4", "技术要求", children=[
                _clause("4.1", "现场运行条件"),
                _clause("4.2", "电气运行条件"),
                _clause("4.4", "电动机外形的安装尺寸"),  # 缺 4.3
            ]),
        ])
        report = verify_compliance(doc)
        h03 = [f for f in report.findings if f.rule_id == "GBT-H03"]
        self.assertTrue(any(f.priority == "should" and "缺失 4.3" in f.message for f in h03))

    def test_duplicate_clause_number_flagged(self) -> None:
        doc = _document(children=[
            _clause("1", "范围"),
            _clause("4", "技术要求", children=[
                _clause("4.1", "现场运行条件"),
                _clause("4.1", "电气运行条件"),  # 重复 4.1（字形混淆常致重复）
                _clause("4.2", "安装尺寸"),
            ]),
        ])
        report = verify_compliance(doc)
        h03 = [f for f in report.findings if f.rule_id == "GBT-H03"]
        self.assertTrue(any("重复 4.1" in f.message for f in h03))

    def test_list_item_numbering_gap_flagged(self) -> None:
        doc = _document(children=[
            _clause("1", "范围", content=[
                {"presentationType": "list", "listItems": [
                    {"marker": "a）", "text": "甲；"},
                    {"marker": "b）", "text": "乙；"},
                    {"marker": "c）", "text": "丙；"},
                    {"marker": "f）", "text": "丁。"},  # 缺 d、e
                ]},
            ]),
        ])
        report = verify_compliance(doc)
        c14 = [f for f in report.findings if f.rule_id == "GBT-C14"]
        self.assertEqual(len(c14), 1)
        self.assertIn("缺失：d, e", c14[0].message)
        self.assertEqual(c14[0].priority, "should")

    def test_continuous_lists_are_not_flagged(self) -> None:
        doc = _document(children=[
            _clause("1", "范围", content=[
                {"presentationType": "list", "listItems": [
                    {"marker": "a）", "text": "甲；"},
                    {"marker": "b）", "text": "乙；"},
                    {"marker": "c）", "text": "丙。"},
                ]},
                {"presentationType": "list", "listItems": [
                    {"marker": "1)", "text": "一；"},
                    {"marker": "2)", "text": "二。"},
                ]},
                {"presentationType": "list", "listItems": [
                    {"marker": "——", "text": "无编号项。"},
                    {"marker": "——", "text": "无编号项。"},
                ]},
            ]),
        ])
        report = verify_compliance(doc)
        self.assertFalse([f for f in report.findings if f.rule_id == "GBT-C14"])

    def test_annex_letter_gap_flagged(self) -> None:
        doc = _document(children=[
            _clause("1", "范围"),
            _clause("2", "规范性引用文件"),
            _clause("3", "术语和定义"),
            {"nodeType": "annex", "number": "A", "title": "附录A（规范性）资料性附录", "contentElements": []},
            {"nodeType": "annex", "number": "C", "title": "附录C（资料性）示例", "contentElements": []},  # 缺 B
        ])
        report = verify_compliance(doc)
        c15 = [f for f in report.findings if f.rule_id == "GBT-C15"]
        self.assertEqual(len(c15), 1)
        self.assertIn("缺失：B", c15[0].message)

    def test_glyph_confused_heading_and_standard_number_flagged(self) -> None:
        doc = _document(children=[
            _clause("1", "范围", content=[
                {"presentationType": "paragraph", "textContent": "本文件引用了 GB/T 5O89—2020 的规定。"},
            ]),
            {"nodeType": "clause", "number": "", "title": "4.O.1 安装尺寸", "contentElements": []},
        ])
        report = verify_compliance(doc)
        c16 = [f for f in report.findings if f.rule_id == "GBT-C16"]
        self.assertTrue(any("4.O.1" in f.message for f in c16))
        self.assertTrue(any("GB/T 5O89" in f.message for f in c16))


if __name__ == "__main__":
    unittest.main()
