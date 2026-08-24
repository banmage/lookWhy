from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from leleby_ssir.exporters import json_bytes, turtle_text
from leleby_ssir.parser import CSMError, CSMParser
from leleby_ssir.roundtrip import compare_ssir
from leleby_ssir.service import normalize_csm, parse_csm, parse_csm_with_report, round_trip_csm


ROOT = Path(__file__).resolve().parents[1]


class CSMToSSIRTests(unittest.TestCase):
    def test_pmrz_preserves_figures_table_list_and_quality_notices(self) -> None:
        ssir = parse_csm(ROOT / "corpus/golden/csm/Q_PMRZ_9-2024.csm.md")
        self.assertEqual(ssir["documentType"], "standard")
        self.assertEqual(ssir["sourceFiles"][0]["mimeType"], "text/markdown")
        self.assertEqual(len(ssir["tables"]), 1)
        self.assertEqual(len(ssir["figures"]), 2)
        self.assertEqual(ssir["figures"][0]["preservationStatus"], "partiallyPreserved")
        self.assertEqual(ssir["qualityAssessments"][0]["overallStatus"], "partial")
        self.assertIn("GB20001-10-6.3", ssir["qualityAssessments"][0]["comments"])

    def test_tqdz_preserves_table_and_marked_lists(self) -> None:
        ssir = parse_csm(ROOT / "corpus/golden/csm/Q_TQDZ_004-2026.csm.md")
        table = ssir["tables"][0]
        self.assertEqual(table["caption"], "基本参数")
        self.assertEqual(table["number"], "1")
        self.assertEqual(table["colCount"], 3)
        lists = [
            element
            for node in self._nodes(ssir["structuralRoot"])
            for element in node.get("contentElements", [])
            if element["presentationType"] == "list"
        ]
        self.assertGreaterEqual(len(lists), 4)
        marker_types = {
            item["markerType"]
            for content in lists
            for item in content["listItems"]
        }
        self.assertIn("lowerAlpha", marker_types)

    def test_additional_product_standard_examples_convert(self) -> None:
        examples = {
            "Q_YYJD_001-2024.csm.md": {"tables": 1, "figures": 1, "formulas": 0, "status": "partial"},
            "Q_HKT_16016-2026.csm.md": {"tables": 1, "figures": 0, "formulas": 1, "status": "complete"},
            "T_ZZB_1064-2019.csm.md": {"tables": 1, "figures": 0, "formulas": 0, "status": "partial"},
        }
        for file_name, expected in examples.items():
            with self.subTest(file_name=file_name):
                ssir, report = parse_csm_with_report(ROOT / "corpus/golden/csm" / file_name)
                self.assertEqual(ssir["documentType"], "standard")
                self.assertEqual(len(ssir["tables"]), expected["tables"])
                self.assertEqual(len(ssir["figures"]), expected["figures"])
                self.assertEqual(len(ssir["formulas"]), expected["formulas"])
                self.assertEqual(report.overall_status, expected["status"])
                self.assertEqual(ssir["qualityAssessments"][0]["overallStatus"], expected["status"])

    def test_markdown_round_trip_preserves_all_csm_examples(self) -> None:
        paths = [
            *sorted((ROOT / "corpus/golden/csm").glob("*.csm.md")),
            ROOT / "corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md",
        ]
        with tempfile.TemporaryDirectory() as directory:
            for path in paths:
                with self.subTest(path=path.name):
                    std1 = Path(directory) / f"{path.stem}.std1.csm.md"
                    ssir1, ssir2, report = round_trip_csm(path, std1)
                    self.assertTrue(std1.exists())
                    self.assertTrue(report.passed, report.to_dict())
                    self.assertEqual(ssir1["metadata"]["common"], ssir2["metadata"]["common"])

    def test_comparator_reports_critical_normative_and_table_changes(self) -> None:
        ssir1 = parse_csm(ROOT / "corpus/golden/csm/Q_HKT_16016-2026.csm.md")
        ssir2 = deepcopy(ssir1)
        ssir2["tables"][0]["rows"][1]["cells"][0]["text"] = "999"
        content = next(
            element
            for node in self._nodes(ssir2["structuralRoot"])
            for element in node.get("contentElements", [])
            if element.get("textContent") and "应符合" in element["textContent"]
        )
        content["textContent"] = content["textContent"].replace("应符合", "宜符合", 1)
        report = compare_ssir(ssir1, ssir2)
        self.assertFalse(report.passed)
        self.assertIn("C1-normativeWording", report.critical_information_loss)
        self.assertIn("C8-tableCellContent", report.critical_information_loss)

    def test_template_formula_and_turtle_export(self) -> None:
        ssir = parse_csm(ROOT / "corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md")
        self.assertEqual(len(ssir["formulas"]), 1)
        self.assertEqual(ssir["formulas"][0]["number"], "式（1）")
        turtle = turtle_text(ssir)
        self.assertIn("ssir:jsonSha256", turtle)
        self.assertIn("https://leleby.io/resource/ssir%3AQ-EXAMPLE-001-2026", turtle)
        self.assertIn("a ssir:Table", turtle)
        self.assertIn("a ssir:Figure", turtle)
        self.assertIn("a ssir:Formula", turtle)

    def test_round_trip_preserves_annex_kind_and_identifier(self) -> None:
        path = ROOT / "corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md"
        with tempfile.TemporaryDirectory() as directory:
            ssir1, ssir2, report = round_trip_csm(path, Path(directory) / "std1.md")
        annex1 = next(node for node in self._nodes(ssir1["structuralRoot"]) if node["nodeType"] == "annex")
        annex2 = next(node for node in self._nodes(ssir2["structuralRoot"]) if node["nodeType"] == "annex")
        self.assertTrue(report.passed, report.to_dict())
        self.assertEqual((annex1["number"], annex1["title"]), (annex2["number"], annex2["title"]))

    def test_normalize_writes_std0_without_changing_body_semantics(self) -> None:
        raw = (
            b'\xef\xbb\xbf---\r\n'
            b'document-type: standard\r\n'
            b'document-identifier: "Q/TEST 003\xe2\x80\x942026"\r\n'
            b'standard-number: "Q/TEST 003\xe2\x80\x942026"\r\n'
            b'title: "Std0 \xe5\x9f\xba\xe7\xba\xbf"\r\n'
            b'language: zh-CN\r\n'
            b'---\r\n\r\n'
            b'# Std0 \xe5\x9f\xba\xe7\xba\xbf\r\n\r\n'
            b'## \xe5\x89\x8d\xe8\xa8\x80\r\n\r\n'
            b'\xe6\x9c\xac\xe6\x96\x87\xe4\xbb\xb6\xe6\x8c\x89\xe7\x85\xa7 GB/T 1.1\xe2\x80\x942020 \xe8\xb5\xb7\xe8\x8d\x89\xe3\x80\x82\r\n\r\n'
            b'## 1 \xe8\x8c\x83\xe5\x9b\xb4\r\n\r\n'
            b'\xe6\x9c\xac\xe6\x96\x87\xe4\xbb\xb6\xe8\xa7\x84\xe5\xae\x9a\xe6\xb5\x8b\xe8\xaf\x95\xe4\xba\xa7\xe5\x93\x81\xe3\x80\x82\r\n\r\n'
            b'## 4 \xe6\x8a\x80\xe6\x9c\xaf\xe8\xa6\x81\xe6\xb1\x82\r\n\r\n'
            b'\xe4\xba\xa7\xe5\x93\x81\xe9\xa2\x9d\xe5\xae\x9a\xe7\x94\xb5\xe5\x8e\x8b\xe5\xba\x94\xe4\xb8\xba 12 V\xe3\x80\x82\r\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            raw_path = Path(directory) / "raw.md"
            std0_path = Path(directory) / "standard.std0.csm.md"
            raw_path.write_bytes(raw)
            ssir0, report = normalize_csm(raw_path, std0_path)
            ssir0_reparsed = parse_csm(std0_path)
            rendered = std0_path.read_bytes()
        self.assertTrue(std0_path.name.endswith(".csm.md"))
        self.assertFalse(rendered.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r", rendered)
        self.assertIn(b'csm-version: \'1.0\'', rendered)
        self.assertTrue(any(issue.code == "CSM-ENC-001" for issue in report.issues))
        self.assertTrue(compare_ssir(ssir0, ssir0_reparsed).passed)

    def test_same_input_produces_deterministic_json(self) -> None:
        path = ROOT / "corpus/golden/csm/Q_TQDZ_004-2026.csm.md"
        self.assertEqual(json_bytes(parse_csm(path)), json_bytes(parse_csm(path)))

    def test_duplicate_ssir_id_is_rejected(self) -> None:
        text = (ROOT / "corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md").read_text(encoding="utf-8")
        duplicate = text.replace(
            '<!-- ssir:figure id="fig-001" asset-status="missing" -->',
            '<!-- ssir:table id="tbl-001" header-rows="1" -->',
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.md"
            path.write_text(duplicate, encoding="utf-8")
            with self.assertRaises(CSMError) as raised:
                CSMParser().read(path)
        self.assertIn("duplicate ssir id", str(raised.exception))

    def test_unknown_directive_is_rejected(self) -> None:
        text = (ROOT / "corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md").read_text(encoding="utf-8")
        invalid = text.replace("<!-- ssir:formula", "<!-- ssir:unsupported", 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.md"
            path.write_text(invalid, encoding="utf-8")
            ssir, report = parse_csm_with_report(path)
            with self.assertRaises(CSMError) as raised:
                CSMParser(strict=True).read(path)
        self.assertEqual(len(ssir["unknownContents"]), 1)
        self.assertTrue(any("unsupported ssir directive" in issue.message for issue in report.issues))
        self.assertIn("unsupported ssir directive", str(raised.exception))

    def test_recoverable_metadata_and_title_issues_convert_with_report(self) -> None:
        csm = '''---
document-type: standard
---

# 可恢复输入

## 1 范围

本文件规定测试产品。
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recoverable.csm.md"
            path.write_text(csm, encoding="utf-8", newline="\r\n")
            ssir, report = parse_csm_with_report(path)
            with self.assertRaises(CSMError):
                parse_csm(path, strict=True)
        self.assertEqual(ssir["metadata"]["common"]["title"], "可恢复输入")
        self.assertEqual(report.overall_status, "partial")
        codes = {issue.code for issue in report.issues}
        self.assertIn("CSM-META-005", codes)
        self.assertIn("CSM-ENC-002", codes)
        self.assertIn("GB-T-1.1-FOREWORD-001", codes)

    def test_mineru_page_markers_are_dropped_even_mid_paragraph(self) -> None:
        csm = '''---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/TEST 003—2026"
standard-number: "Q/TEST 003—2026"
title: "页码标记"
language: zh-CN
source: {mode: mineru-pdf, provenance: none}
extensions: {}
---

# 页码标记

## 1 范围

本文件规定测试产品。

3
<!-- /ssir:mineru-pages -->
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "markers.csm.md"
            path.write_text(csm, encoding="utf-8")
            ssir, report = parse_csm_with_report(path)
        texts = []
        for node in ssir["structuralRoot"]["children"]:
            for content in node.get("contentElements", []):
                texts.append(str(content.get("textContent", "")))
        joined = "\n".join(texts)
        self.assertNotIn("mineru-pages", joined)
        self.assertIn("本文件规定测试产品。", joined)

    def test_short_table_row_is_padded_and_reported(self) -> None:
        csm = '''---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/TEST 001—2026"
standard-number: "Q/TEST 001—2026"
title: "表格修复"
language: zh-CN
source: {mode: user-markdown, provenance: none}
extensions: {}
---

# 表格修复

## 前言

本文件按照 GB/T 1.1—2020 起草。

## 1 范围

本文件规定测试产品。

| 项目 | 条件 | 值 |
|---|---|---|
| 温度 | 40 |
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "short-table.csm.md"
            path.write_text(csm, encoding="utf-8")
            ssir, report = parse_csm_with_report(path)
        self.assertEqual(ssir["tables"][0]["rows"][1]["cells"][2]["text"], "")
        self.assertTrue(any(issue.code == "CSM-TABLE-001" and issue.repaired for issue in report.issues))

    def test_product_optional_sections_do_not_block_conversion(self) -> None:
        csm = '''---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/TEST 002—2026"
standard-number: "Q/TEST 002—2026"
title: "最小产品标准"
language: zh-CN
source: {mode: user-markdown, provenance: none}
extensions: {standard-profile: product}
---

# 最小产品标准

## 前言

本文件按照 GB/T 1.1—2020 起草。

## 1 范围

本文件规定测试产品。

## 4 技术要求

产品额定电压应为 12 V。
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "minimal-product.csm.md"
            path.write_text(csm, encoding="utf-8")
            ssir, report = parse_csm_with_report(path)
        self.assertEqual(ssir["documentType"], "standard")
        self.assertFalse(any("取样" in issue.message or "检验规则" in issue.message for issue in report.issues))

    def test_unclosed_formula_remains_unacceptable(self) -> None:
        text = (ROOT / "corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md").read_text(encoding="utf-8")
        invalid = text.replace("$$\nP = U I\n$$", "$$\nP = U I", 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unclosed.csm.md"
            path.write_text(invalid, encoding="utf-8")
            with self.assertRaises(CSMError) as raised:
                parse_csm(path)
        self.assertIn("unterminated formula block", str(raised.exception))

    def test_raw_formula_and_table_merge_are_preserved(self) -> None:
        csm = '''---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/TEST 001—2026"
standard-number: "Q/TEST 001—2026"
title: "合并单元格测试"
language: zh-CN
source:
  mode: user-markdown
  provenance: none
extensions: {}
---

# 合并单元格测试

## 1 范围

本文件规定测试产品的要求。

<!-- ssir:table id="tbl-001" header-rows="1" -->
**表1 测试数据**

| 项目 | 条件 | 值 |
|------|------|----|
| 温度 | 高温 | 40 |
| 温度 | 低温 | -20 |

<!-- ssir:table-merge table="tbl-001" row="1" column="1" rowspan="2" colspan="1" -->

<!-- ssir:formula id="fm-001" format="raw" -->
```formula
U_N = U_0 / sqrt(3)
```
式（1）
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "merge.csm.md"
            path.write_text(csm, encoding="utf-8")
            ssir = parse_csm(path)
        self.assertEqual(ssir["tables"][0]["rows"][1]["cells"][0]["rowspan"], 2)
        self.assertEqual(ssir["formulas"][0]["rawText"], "U_N = U_0 / sqrt(3)")
        self.assertNotIn("latex", ssir["formulas"][0])

    @staticmethod
    def _nodes(node: dict):
        yield node
        for child in node.get("children", []):
            yield from CSMToSSIRTests._nodes(child)


if __name__ == "__main__":
    unittest.main()
