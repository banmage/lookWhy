"""KG 阶段 P1a/P1c 单元测试：kg.json 映射器 + sqlite 索引库。

不依赖 out/mineru 真实产物——用内联最小 SSIR 夹具，保证任何环境可跑。
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from leleby_ssir import kg
from leleby_ssir.kgstore import KGDocStore


def _minimal_ssir() -> dict:
    """最小 SSIR 夹具：文档 → 章1(范围) / 章2(引用) / 章3(术语 3.1) + 表/图注册表。"""
    doc_id = "ssir:Q-TEST-001-2026"
    root = {
        "id": f"{doc_id}/document",
        "nodeType": "document",
        "sortOrder": 0,
        "children": [
            {
                "id": f"{doc_id}/section-1-001",
                "nodeType": "section",
                "number": "1",
                "title": "范围",
                "level": 1,
                "sortOrder": 0,
                "contentElements": [
                    {
                        "id": f"{doc_id}/content/c-0001",
                        "presentationType": "paragraph",
                        "parentNodeId": f"{doc_id}/section-1-001",
                        "sortOrder": 0,
                        "semanticTypes": ["scope"],
                        "textContent": "本文件规定了测试标准的最小结构。",
                        "sourceAnchors": [{
                            "anchorType": "markdown", "id": f"{doc_id}/anchor/a-001",
                            "markdownStartLine": 12, "markdownEndLine": 12,
                            "markdownNodePath": "md:paragraph:12",
                            "sourceFileId": "src:aaaa",
                        }],
                    }
                ],
                "sourceAnchors": [{
                    "anchorType": "markdown", "id": f"{doc_id}/anchor/a-002",
                    "markdownStartLine": 11, "markdownEndLine": 11,
                    "markdownNodePath": "md:heading:11", "sourceFileId": "src:aaaa",
                }],
            },
            {
                "id": f"{doc_id}/section-2-002",
                "nodeType": "section",
                "number": "2",
                "title": "规范性引用文件",
                "sortOrder": 1,
                "contentElements": [
                    {
                        "id": f"{doc_id}/content/c-0002",
                        "presentationType": "paragraph",
                        "parentNodeId": f"{doc_id}/section-2-002",
                        "sortOrder": 0,
                        "semanticTypes": ["normativeReference"],
                        "textContent": "下列文件中的内容通过文中的规范性引用而构成本文件必不可少的条款。GB/T 1.1—2020、GB/T 20000.2—2009。",
                        "sourceAnchors": [{
                            "anchorType": "markdown", "id": f"{doc_id}/anchor/a-003",
                            "markdownStartLine": 20, "markdownEndLine": 20,
                            "markdownNodePath": "md:paragraph:20",
                            "sourceFileId": "src:aaaa",
                        }],
                    }
                ],
            },
            {
                "id": f"{doc_id}/section-3-003",
                "nodeType": "section",
                "number": "3",
                "title": "术语和定义",
                "sortOrder": 2,
                "children": [
                    {
                        "id": f"{doc_id}/clause-3.1-004",
                        "nodeType": "clause",
                        "number": "3.1",
                        "title": "测试件",
                        "term": "测试件",
                        "englishTerm": "test piece",
                        "sortOrder": 0,
                        "contentElements": [
                            {
                                "id": f"{doc_id}/content/c-0003",
                                "presentationType": "paragraph",
                                "parentNodeId": f"{doc_id}/clause-3.1-004",
                                "sortOrder": 0,
                                "semanticTypes": ["termDefinition"],
                                "textContent": "用于执行规定试验的样品。",
                                "sourceAnchors": [{
                                    "anchorType": "markdown", "id": f"{doc_id}/anchor/a-004",
                                    "markdownStartLine": 30, "markdownEndLine": 30,
                                    "markdownNodePath": "md:paragraph:30",
                                    "sourceFileId": "src:aaaa",
                                }],
                            },
                            {
                                "id": f"{doc_id}/content/c-0004",
                                "presentationType": "table",
                                "parentNodeId": f"{doc_id}/clause-3.1-004",
                                "sortOrder": 1,
                                "tableRef": f"{doc_id}/table/t-001",
                                "textContent": "",
                            },
                        ],
                    }
                ],
            },
            {
                "id": f"{doc_id}/section-9-005",
                "nodeType": "section",
                "number": "9",
                "title": "包装与图示",
                "sortOrder": 3,
                "contentElements": [
                    {
                        "id": f"{doc_id}/content/c-0005",
                        "presentationType": "figure",
                        "parentNodeId": f"{doc_id}/section-9-005",
                        "sortOrder": 0,
                        "figureRef": f"{doc_id}/figure/f-001",
                        "textContent": "",
                    }
                ],
            },
        ],
    }
    return {
        "id": doc_id,
        "ssirVersion": "0.3",
        "documentType": "standard",
        "metadata": {
            "standard": {
                "standardNumber": "Q/TEST 001-2026",
                "chineseTitle": "测试标准（夹具）",
                "ics": "25.010",
                "ccs": "J 00",
                "replaces": "Q/TEST 001-2019",
            },
            "common": {"title": "测试标准（夹具）", "issuer": "某测试机构"},
        },
        "sourceFiles": [{"id": "src:aaaa", "fileName": "Q_TEST_001-2026.canonical.md"}],
        "canonicalText": {"id": f"{doc_id}/canonical", "text": "x"},
        "structuralRoot": root,
        "tables": [
            {
                "id": f"{doc_id}/table/t-001",
                "number": "1",
                "caption": "测试件状态",
                "rowCount": 2,
                "colCount": 2,
                "rows": [
                    {"cells": [
                        {"text": "状态", "isHeader": True},
                        {"text": "说明", "isHeader": True},
                    ]},
                    {"cells": [{"text": "A"}, {"text": "初始"}]},
                ],
            }
        ],
        "figures": [
            {
                "id": f"{doc_id}/figure/f-001",
                "number": "1",
                "caption": "包装示意",
                "assetRef": "assets/images/test.png",
            }
        ],
        "formulas": [],
    }


class BuildKgTests(unittest.TestCase):
    def setUp(self):
        self.kgd = kg.build_kg(_minimal_ssir(), artifact_path="/x/Q_TEST_001-2026.ssir.json")

    def test_counts_and_uri_reuse(self):
        ids = [n["id"] for n in self.kgd["nodes"]]
        self.assertIn("ssir:Q-TEST-001-2026/section-1-001", ids)  # SSIR URI 原样复用
        kinds = {}
        for n in self.kgd["nodes"]:
            kinds[n["kind"]] = kinds.get(n["kind"], 0) + 1
        self.assertEqual(kinds["Document"], 1)
        self.assertGreaterEqual(kinds["Clause"], 1)
        self.assertGreaterEqual(kinds["Term"], 1)
        self.assertGreaterEqual(kinds["Table"], 1)
        self.assertGreaterEqual(kinds["Figure"], 1)

    def test_term_node_and_definition(self):
        term_nodes = [n for n in self.kgd["nodes"] if n["kind"] == "Term"]
        self.assertEqual(len(term_nodes), 1)
        t = term_nodes[0]
        self.assertEqual(t["term"], "测试件")
        self.assertEqual(t["englishTerm"], "test piece")
        self.assertEqual(t["clauseNumber"], "3.1")
        self.assertIn("用于执行规定试验的样品", t["definitionText"])
        edges = [(e["from"], e["to"], e["type"]) for e in self.kgd["edges"]]
        self.assertIn(("ssir:Q-TEST-001-2026/clause-3.1-004", t["id"], "HAS_TERM"), edges)

    def test_edges_and_anchor(self):
        edge_types = {e["type"] for e in self.kgd["edges"]}
        self.assertTrue({"HAS_CHILD", "CONTAINS_ELEMENT", "HAS_TERM"} <= edge_types)
        # 图 → 表/图注册表引用边（父节点 → registry 实体）
        contains = [(e["from"], e["to"]) for e in self.kgd["edges"] if e["type"] == "CONTAINS_ELEMENT"]
        self.assertIn(("ssir:Q-TEST-001-2026/clause-3.1-004",
                       "ssir:Q-TEST-001-2026/table/t-001"), contains)
        self.assertIn(("ssir:Q-TEST-001-2026/section-9-005",
                       "ssir:Q-TEST-001-2026/figure/f-001"), contains)
        # 锚点透传
        sec1 = next(n for n in self.kgd["nodes"] if n["id"].endswith("/section-1-001"))
        self.assertEqual(sec1["anchor"]["markdownStartLine"], 11)
        self.assertEqual(sec1["anchor"]["sourceFileId"], "src:aaaa")
        self.assertEqual(self.kgd["document"]["rootNodeId"],
                         "ssir:Q-TEST-001-2026/document")

    def test_references_extraction(self):
        refs = {r["norm"]: r for r in self.kgd["document"]["references"]}
        self.assertIn("GB/T1.1-2020", refs)  # 一字线 → 连字符归一
        self.assertEqual(refs["GB/T1.1-2020"]["clause"], "2")
        self.assertEqual(refs["GB/T1.1-2020"]["mdLine"], 20)
        self.assertIn("GB/T20000.2-2009", refs)

    def test_schema_validation_passes(self):
        errs = kg.validate_kg(self.kgd)
        self.assertEqual(errs, [], "schema 校验失败: %r" % errs)


class StoreTests(unittest.TestCase):
    def _write_ssir(self, tmp: Path) -> Path:
        p = tmp / "03_ssir" / "Q_TEST_001-2026.ssir.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps(_minimal_ssir(), ensure_ascii=False), encoding="utf-8")
        (tmp / "02_canonical").mkdir()
        (tmp / "02_canonical" / "Q_TEST_001-2026.canonical.md").write_text(
            "\n".join(f"line {i}" for i in range(1, 41)), encoding="utf-8")
        return p

    def test_import_list_tree_delete(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            store = KGDocStore(tmp / "kg.db")
            ssir = self._write_ssir(tmp)
            summary = store.import_ssir(ssir)
            self.assertEqual(summary["doc_id"], "Q_TEST_001-2026")
            self.assertEqual(summary["node_count"], 6)  # document + 4 sections + 1 clause
            docs = store.list_documents()
            self.assertEqual(len(docs), 1)
            self.assertEqual(docs[0]["standard_number"], "Q/TEST 001-2026")
            # 根行 + 子行
            rows = store.all_rows("Q_TEST_001-2026")
            by_id = {r["id"]: r for r in rows}
            self.assertIn("ssir:Q-TEST-001-2026/section-1-001", by_id)
            sec1 = by_id["ssir:Q-TEST-001-2026/section-1-001"]
            self.assertEqual(sec1["md_start_line"], 11)
            # canonical 行读取
            lines = store.canonical_lines("Q_TEST_001-2026", 10, 12)
            assert lines is not None
            self.assertEqual(len(lines), 3)
            self.assertEqual(lines[1]["text"], "line 11")
            # payload 回读
            pl = store.get_payload("Q_TEST_001-2026")
            self.assertEqual(pl["metadata"]["standard"]["standardNumber"], "Q/TEST 001-2026")
            # 重导（replace 语义）
            s2 = store.import_ssir(ssir)
            self.assertTrue(s2["replaced"])
            self.assertEqual(len(store.list_documents()), 1)
            # 删除
            self.assertTrue(store.delete_document("Q_TEST_001-2026"))
            self.assertEqual(len(store.list_documents()), 0)

    def test_import_invalid_json_raises(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            store = KGDocStore(tmp / "kg.db")
            bad = tmp / "bad.json"
            bad.write_text("{ not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                store.import_ssir(bad)


class NamingIntegrationTest(unittest.TestCase):
    def test_standard_filename_convention(self):
        from leleby_ssir.naming import standard_filename  # noqa: PLC0415

        self.assertEqual(standard_filename("GB/T 1.1-2020"), "GB_T_1.1-2020")
        self.assertEqual(standard_filename("Q/YYJD 001-2024"), "Q_YYJD_001-2024")


if __name__ == "__main__":
    unittest.main()
