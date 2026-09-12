"""kg_viewer 文档详情（tools/kg_viewer/detail.py）回归夹具。

验证从 SSIR 载荷派生：元数据（日期/代替/ICS/CCS）、前言机构（提出/归口/起草单位/
主要起草人）、术语条目（条数 + 定义）、顶层标准要素分组与 GBT-E01~E14 清单核对。
"""
from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from kg_viewer import detail as kg_detail  # noqa: E402


def _node(identifier: str, node_type: str, number=None, title=None, *, term=None, english=None,
          children=None, contents=None, line=None) -> dict:
    node = {
        "id": identifier,
        "nodeType": node_type,
        "sortOrder": 0,
        "title": title,
        "children": children or [],
        "contentElements": contents or [],
    }
    if number is not None:
        node["number"] = number
    if term is not None:
        node["term"] = term
    if english is not None:
        node["englishTerm"] = english
    if line is not None:
        node["sourceAnchors"] = [{"anchorType": "markdown", "markdownStartLine": line}]
    return node


def _para(text: str, semantic=None) -> dict:
    content = {"presentationType": "paragraph", "textContent": text, "sortOrder": 0}
    if semantic:
        content["semanticTypes"] = semantic
    return content


def _payload() -> dict:
    preface = _node("ssir:T/preface", "documentBlock", title="前 言", line=10, contents=[
        _para("本文件由全国示例标准化技术委员会(SAC/TC 999)提出。"),
        _para("本文件由全国示例标准化技术委员会(SAC/TC 999)归口。"),
        _para("本文件起草单位：甲研究院、乙出版社、丙有限公司。"),
        _para("本文件主要起草人：张三、李四，王五。"),
    ])
    terms = _node("ssir:T/clause-3", "section", number="3", title="术语和定义", children=[
        _node("ssir:T/sub-3.1", "subClause", number="3.1", title="", term="示例术语",
              english="example term", line=30,
              contents=[_para("示例术语的定义。", semantic=["termDefinition"])]),
    ])
    return {
        "id": "ssir:T-001-2026",
        "documentType": "standard",
        "metadata": {
            "common": {
                "documentIdentifier": "T/EXAMPLE 001-2026",
                "title": "示例标准",
                "titleEn": "Example standard",
                "publicationDate": "2026-01-01",
                "effectiveDate": "2026-07-01",
                "issuer": "示例发布机构",
                "language": "zh-CN",
                "conformityStatement": "(ISO 0001:2020, NEQ)",
            },
            "standard": {
                "standardNumber": "T/EXAMPLE 001-2026",
                "chineseTitle": "示例标准",
                "ics": "01.040",
                "ccs": "A 00",
                "replaces": "T/EXAMPLE 001—2020",
            },
        },
        "structuralRoot": {
            "id": "ssir:T-001-2026/document", "nodeType": "document", "sortOrder": 0,
            "children": [
                _node("ssir:T/toc", "documentBlock", title="目 次"),
                preface,
                _node("ssir:T/clause-1", "section", number="1", title="范围", line=20, contents=[_para("本文件规定了…")]),
                _node("ssir:T/clause-2", "section", number="2", title="规范性引用文件"),
                terms,
                _node("ssir:T/clause-4", "section", number="4", title="技术要求"),
                _node("ssir:T/annex-A", "annex", number="A", title="（资料性） 示例附录"),
                _node("ssir:T/refs", "documentBlock", title="参考文献"),
                _node("ssir:T/index", "documentBlock", title="索 引"),
            ],
        },
        "tables": [{"id": "t1"}], "figures": [{"id": "f1"}, {"id": "f2"}], "formulas": [],
    }


class DocumentDetailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detail = kg_detail.build_document_detail(_payload())

    def test_metadata_dates_and_relations(self) -> None:
        self.assertEqual(self.detail["identity"]["standard_number"], "T/EXAMPLE 001-2026")
        self.assertEqual(self.detail["identity"]["ics"], "01.040")
        self.assertEqual(self.detail["dates"], {"publication_date": "2026-01-01", "effective_date": "2026-07-01"})
        self.assertEqual(self.detail["relations"]["replaces"], "T/EXAMPLE 001—2020")
        self.assertIn("NEQ", self.detail["relations"]["conformity_statement"])

    def test_front_matter_organizations(self) -> None:
        orgs = self.detail["organizations"]
        self.assertEqual(orgs["proposing"], "全国示例标准化技术委员会(SAC/TC999)")
        self.assertEqual(orgs["secretariat"], "全国示例标准化技术委员会(SAC/TC999)")
        self.assertEqual(orgs["drafting_units"], ["甲研究院", "乙出版社", "丙有限公司"])
        self.assertEqual(orgs["drafters"], ["张三", "李四", "王五"])

    def test_terms_count_and_definition(self) -> None:
        self.assertEqual(self.detail["terms"]["count"], 1)
        term = self.detail["terms"]["items"][0]
        self.assertEqual(term["number"], "3.1")
        self.assertEqual(term["term"], "示例术语")
        self.assertEqual(term["english"], "example term")
        self.assertEqual(term["definition"], "示例术语的定义。")
        self.assertEqual(term["md_line"], 30)

    def test_element_groups(self) -> None:
        groups = {group["key"]: group for group in self.detail["elements"]["groups"]}
        self.assertEqual([item["code"] for item in groups["front"]["items"]], ["GBT-E02", "GBT-E03"])
        body_codes = [item["code"] for item in groups["body"]["items"]]
        self.assertEqual(body_codes, ["GBT-E05", "GBT-E06", "GBT-E07", "章"])
        self.assertEqual([item["code"] for item in groups["annex"]["items"]], ["附录A"])
        self.assertEqual(groups["annex"]["items"][0]["nature"], "资料性")
        self.assertEqual([item["code"] for item in groups["back"]["items"]], ["GBT-E13", "GBT-E14"])

    def test_coverage_present_and_missing(self) -> None:
        rows = {row["code"]: row for row in self.detail["coverage"]["elements"]}
        self.assertTrue(rows["GBT-E01"]["present"])  # 封面由元数据派生
        for code in ("GBT-E02", "GBT-E03", "GBT-E05", "GBT-E06", "GBT-E07", "GBT-E13", "GBT-E14"):
            self.assertTrue(rows[code]["present"], code)
        self.assertFalse(rows["GBT-E04"]["present"])  # 无引言
        self.assertFalse(rows["GBT-E08"]["present"])  # 无符号和缩略语
        self.assertTrue(rows["GBT-E11"]["present"])
        metadata_rows = {row["code"]: row for row in self.detail["coverage"]["metadata"]}
        self.assertTrue(metadata_rows["GBT-M05"]["present"])
        self.assertTrue(metadata_rows["GBT-M11"]["present"])  # 归口单位来自前言
        self.assertFalse(metadata_rows["GBT-M13"]["present"])  # 技术领域/关键词缺规则

    def test_stats(self) -> None:
        stats = self.detail["stats"]
        self.assertEqual(stats["chapters"], 4)
        self.assertEqual(stats["annexes"], 1)
        self.assertEqual(stats["terms"], 1)
        self.assertEqual(stats["tables"], 1)
        self.assertEqual(stats["figures"], 2)


if __name__ == "__main__":
    unittest.main()
