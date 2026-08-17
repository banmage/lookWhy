from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from leleby_ssir.exporters import json_bytes, turtle_text
from leleby_ssir.parser import CSMError, CSMParser
from leleby_ssir.service import parse_csm


ROOT = Path(__file__).resolve().parents[1]


class CSMToSSIRTests(unittest.TestCase):
    def test_pmrz_preserves_figures_table_list_and_quality_notices(self) -> None:
        ssir = parse_csm(ROOT / "examples/csm/Q_PMRZ_9-2024.csm.md")
        self.assertEqual(ssir["documentType"], "standard")
        self.assertEqual(ssir["sourceFiles"][0]["mimeType"], "text/markdown")
        self.assertEqual(len(ssir["tables"]), 1)
        self.assertEqual(len(ssir["figures"]), 2)
        self.assertEqual(ssir["figures"][0]["preservationStatus"], "partiallyPreserved")
        self.assertEqual(ssir["qualityAssessments"][0]["overallStatus"], "partial")
        self.assertIn("GB20001-10-6.3", ssir["qualityAssessments"][0]["comments"])

    def test_tqdz_preserves_table_and_marked_lists(self) -> None:
        ssir = parse_csm(ROOT / "examples/csm/Q_TQDZ_004-2026.csm.md")
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

    def test_template_formula_and_turtle_export(self) -> None:
        ssir = parse_csm(ROOT / "examples/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md")
        self.assertEqual(len(ssir["formulas"]), 1)
        self.assertEqual(ssir["formulas"][0]["number"], "式（1）")
        turtle = turtle_text(ssir)
        self.assertIn("ssir:jsonSha256", turtle)
        self.assertIn("https://leleby.io/resource/ssir%3AQ-EXAMPLE-001-2026", turtle)
        self.assertIn("a ssir:Table", turtle)
        self.assertIn("a ssir:Figure", turtle)
        self.assertIn("a ssir:Formula", turtle)

    def test_same_input_produces_deterministic_json(self) -> None:
        path = ROOT / "examples/csm/Q_TQDZ_004-2026.csm.md"
        self.assertEqual(json_bytes(parse_csm(path)), json_bytes(parse_csm(path)))

    def test_duplicate_ssir_id_is_rejected(self) -> None:
        text = (ROOT / "examples/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md").read_text(encoding="utf-8")
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
        text = (ROOT / "examples/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md").read_text(encoding="utf-8")
        invalid = text.replace("<!-- ssir:formula", "<!-- ssir:unsupported", 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.md"
            path.write_text(invalid, encoding="utf-8")
            with self.assertRaises(CSMError) as raised:
                CSMParser().read(path)
        self.assertIn("unsupported ssir directive", str(raised.exception))

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
