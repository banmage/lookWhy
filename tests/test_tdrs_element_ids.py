"""TDRS 元素命名回归（docs/16 §10 + `技术文件智能审查系统（TDRS）设计说明文档v2.0.md`）。

覆盖两条入口：新建（builder）与既有产物回放（`apply_element_ids`），二者必须同源同判据：
- 文档标识 = 标准号转义（``GB/T 1.1—2020`` → ``GB_T_1.1-2020``）；
- 结构节点 = ``{标准标识}#{条款路径}``（``#8.2.1`` / ``#Annex_A.2``）；
- 表/图/公式 = ``#Table_3`` 等（附录内带字母 ``#Table_A.1``）；
- 无编号要素 = 固定英文名（``#Foreword`` / ``#Contents`` / ``#Bibliography``）；
- 内容元素 = ``#<条款路径>/<Kind>-<序号>``；列表项 = ``#<条款路径>_<marker>``；
- 锚点 = ``#Anchor-0001``；canonicalText/质量评估/处理运行各有固定标识段。
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
import unittest

from leleby_ssir.builder import apply_element_ids
from leleby_ssir.exporters import json_bytes
from leleby_ssir.service import parse_csm
from leleby_ssir.validation import validate_ssir


ROOT = Path(__file__).resolve().parents[1]

# schema 的 ELEM pattern（`ssir.schema.json` 单一来源，此处照抄用于全量断言）
ELEMENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*#[A-Za-z0-9][A-Za-z0-9._/-]*$")
ANCHOR_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*#Anchor-[0-9]{4}$")


def _walk_nodes(node: dict):
    yield node
    for child in node.get("children") or []:
        yield from _walk_nodes(child)


class ElementIdSchemeTests(unittest.TestCase):
    """新建产物：builder 直接产出 TDRS 标识（GB/T 20001.10 体例的 csm 夹具）。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ssir = parse_csm(ROOT / "corpus/golden/csm/Q_TQDZ_004-2026.canonical.md")

    def test_document_identifier_is_escaped_standard_number(self) -> None:
        self.assertEqual(self.ssir["id"], "Q_TQDZ_004-2026")
        self.assertEqual(self.ssir["structuralRoot"]["id"], "Q_TQDZ_004-2026#Root")
        self.assertEqual(self.ssir["canonicalText"]["id"], "Q_TQDZ_004-2026#Canonical")

    def test_clause_and_content_ids_use_clause_path(self) -> None:
        nodes = {node.get("number"): node for node in _walk_nodes(self.ssir["structuralRoot"])}
        self.assertEqual(nodes["8.2.1"]["id"], "Q_TQDZ_004-2026#8.2.1")
        # 无编号要素按固定英文名（目次/前言）
        node_ids = {node["id"] for node in _walk_nodes(self.ssir["structuralRoot"])}
        self.assertIn("Q_TQDZ_004-2026#Contents", node_ids)
        self.assertIn("Q_TQDZ_004-2026#Foreword", node_ids)
        clause = nodes["8.2.1"]
        self.assertEqual(clause["logicalId"], "8.2.1", "logicalId 即条款路径")
        ids = [element["id"] for element in clause["contentElements"]]
        self.assertIn("Q_TQDZ_004-2026#8.2.1/List-057", ids)
        self.assertIn("Q_TQDZ_004-2026#8.2.1/Paragraph-058", ids)
        self.assertEqual(clause["contentElements"][0]["parentNodeId"], clause["id"])

    def test_list_items_use_marker_suffix(self) -> None:
        items = [item for node in _walk_nodes(self.ssir["structuralRoot"])
                 for element in node.get("contentElements") or []
                 for item in element.get("listItems") or []]
        ids = [item["id"] for item in items]
        self.assertIn("Q_TQDZ_004-2026#4.2_1", ids, "数字标记项 → #4.2_1")
        self.assertIn("Q_TQDZ_004-2026#5_a", ids, "字母标记项 → #5_a")
        self.assertTrue(all(identifier.startswith("Q_TQDZ_004-2026#") for identifier in ids))

    def test_numbered_objects_and_anchors(self) -> None:
        self.assertEqual(self.ssir["tables"][0]["id"], "Q_TQDZ_004-2026#Table_1")
        table_content = [element for node in _walk_nodes(self.ssir["structuralRoot"])
                         for element in node.get("contentElements") or []
                         if element.get("tableRef")]
        self.assertEqual(table_content[0]["tableRef"], "Q_TQDZ_004-2026#Table_1")
        # 表的内容槽标识与表的对象标识分属两套（Block-NNN vs Table_N），不混淆
        self.assertRegex(table_content[0]["id"], r"^Q_TQDZ_004-2026#4\.1/Block-\d{3}$")
        self.assertEqual(table_content[0]["sourceAnchors"][0]["id"],
                         "Q_TQDZ_004-2026#Anchor-0044")
        quality = self.ssir["qualityAssessments"][0]
        self.assertEqual(quality["id"], "Q_TQDZ_004-2026#QualityAssessment_M1")
        self.assertEqual(quality["runId"], self.ssir["processingRuns"][0]["id"])
        self.assertEqual(quality["documentId"], self.ssir["id"])

    def test_every_identifier_matches_schema_patterns(self) -> None:
        identifiers: list[tuple[str, str]] = []

        def collect(item: dict, where: str) -> None:
            identifiers.append((item["id"], where))
            for anchor in item.get("sourceAnchors") or []:
                identifiers.append((anchor["id"], f"anchor@{where}"))
            single = item.get("sourceAnchor")
            if isinstance(single, dict):
                identifiers.append((single["id"], f"anchor@{where}"))

        for node in _walk_nodes(self.ssir["structuralRoot"]):
            collect(node, f"node:{node['id']}")
            for element in node.get("contentElements") or []:
                collect(element, f"content:{element['id']}")
                for item in element.get("listItems") or []:
                    collect(item, f"item:{item['id']}")
        for key in ("tables", "figures", "formulas", "unknownContents"):
            for item in self.ssir.get(key) or []:
                collect(item, f"{key}:{item['id']}")
        for identifier, where in identifiers:
            pattern = ANCHOR_ID_PATTERN if "#Anchor-" in identifier else ELEMENT_ID_PATTERN
            self.assertRegex(identifier, pattern, f"{where} 的标识不符合 TDRS 形态")


class AnnexElementIdTests(unittest.TestCase):
    """附录路径（TDRS §四）：附录与附录条都用 `Annex_` 前缀。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ssir = parse_csm(ROOT / "corpus/golden/csm/T_ZZB_1064-2019.canonical.md")

    def test_annex_and_annex_sections_use_annex_path(self) -> None:
        annexes = [node for node in _walk_nodes(self.ssir["structuralRoot"])
                   if node["nodeType"] == "annex"]
        self.assertTrue(annexes, "夹具应含附录")
        self.assertEqual(annexes[0]["id"], "T_ZZB_1064-2019#Annex_A")
        sections = [node for node in _walk_nodes(annexes[0]) if node["nodeType"] == "annexSection"]
        for section in sections:
            self.assertRegex(section["id"], r"^T_ZZB_1064-2019#Annex_A\.\d+$")
        # 附录内表/图若带附录字母编号，走 Table_A.1 形态
        for table in self.ssir["tables"]:
            number = str(table["number"])
            expected = f"Table_{number}" if not number[:1].isalpha() else f"Table_{number}"
            self.assertEqual(table["id"], f"T_ZZB_1064-2019#{expected}")


class ApplyElementIdsTests(unittest.TestCase):
    """既有产物回放（AGENTS.md §0.4）：只改标识字段、幂等、回放后 schema 通过。"""

    def _legacy_ssir(self) -> dict:
        """最小旧形态 SSIR（`ssir:*` 标识 + `li-0001` 列表项 + `a-0001` 锚点）。

        除标识外全部字段按 schema 合法填写——回放后必须通过 ``validate_ssir``，
        因此这个夹具同时是「除标识外逐值不变」的判据来源。
        """
        def anchor(identifier: str, line: int) -> dict:
            return {"id": identifier, "sourceFileId": "src:" + "0" * 16,
                    "anchorType": "markdown", "markdownStartLine": line,
                    "markdownEndLine": line + 1}

        return {
            "ssirVersion": "0.4",
            "id": "ssir:GB-T-1.1-2020",
            "documentType": "standard",
            "preservationLevel": "Level2",
            "createdAt": "1970-01-01T00:00:00Z",
            "metadata": {
                "common": {"documentIdentifier": "GB/T 1.1-2020", "title": "标准化工作导则",
                           "language": "zh-CN"},
                "standard": {"standardNumber": "GB/T 1.1-2020", "ics": "01.120"},
            },
            "sourceFiles": [{"id": "src:" + "0" * 16, "fileName": "raw.md",
                             "fileHash": {"algorithm": "SHA-256", "value": "0" * 64},
                             "mimeType": "text/markdown"}],
            "processingRuns": [{
                "id": "ssir:processing/run/19700101-001",
                "sourceFileId": "src:" + "0" * 16, "runType": "extraction",
                "tool": "leleby-ssir", "toolVersion": "0.4",
                "timestamp": "1970-01-01T00:00:00Z",
            }],
            "structuralRoot": {
                "id": "ssir:GB-T-1.1-2020/document", "logicalId": "ssir:GB-T-1.1-2020/document",
                "nodeType": "document", "title": "标准化工作导则", "sortOrder": 0,
                "children": [{
                    "id": "ssir:GB-T-1.1-2020/clause-1-001", "logicalId": "clause-1-001",
                    "nodeType": "clause", "number": "1", "title": "范围", "sortOrder": 1,
                    "sourceAnchors": [anchor("ssir:GB-T-1.1-2020/anchor/a-0001", 1)],
                    "children": [],
                    "contentElements": [{
                        "id": "ssir:GB-T-1.1-2020/content/c-0001", "presentationType": "list",
                        "parentNodeId": "ssir:GB-T-1.1-2020/clause-1-001", "sortOrder": 0,
                        "sourceAnchors": [anchor("ssir:GB-T-1.1-2020/anchor/a-0003", 3)],
                        "listItems": [{"id": "li-0001", "marker": "a）", "text": "范围",
                                       "sortOrder": 0,
                                       "sourceAnchor": anchor("ssir:GB-T-1.1-2020/anchor/a-0002", 2)}],
                    }],
                }],
            },
            "canonicalText": {"id": "ssir:GB-T-1.1-2020/canonical", "version": "1",
                              "text": "范围",
                              "sourceElementRefs": ["ssir:GB-T-1.1-2020/content/c-0001"]},
            "tables": [{"id": "ssir:GB-T-1.1-2020/table/t-001", "number": "1", "caption": "表",
                        "rowCount": 1, "colCount": 1,
                        "sourceAnchors": [anchor("ssir:GB-T-1.1-2020/anchor/a-0004", 4)],
                        "rows": [{"id": "r-0001", "rowIndex": 0,
                                  "cells": [{"id": "r0c0", "rowIndex": 0,
                                             "colIndex": 0, "text": "1"}]}]}],
            "figures": [], "formulas": [], "unknownContents": [],
            "qualityAssessments": [{"id": "ssir:GB-T-1.1-2020/qa/m1",
                                    "documentId": "ssir:GB-T-1.1-2020",
                                    "runId": "ssir:processing/run/19700101-001",
                                    "overallStatus": "complete", "structureConfidence": 1.0,
                                    "tableConfidence": 1.0, "figureConfidence": 1.0,
                                    "formulaConfidence": 1.0,
                                    "humanReviewStatus": "machineReviewed",
                                    "assessedAt": "1970-01-01T00:00:00Z"}],
        }

    def test_apply_rewrites_only_identity_fields_and_is_idempotent(self) -> None:
        legacy = self._legacy_ssir()
        updated = copy.deepcopy(legacy)
        apply_element_ids(updated)
        validate_ssir(updated)  # 回放后必须通过 schema 与语义校验

        self.assertEqual(updated["id"], "GB_T_1.1-2020")
        self.assertEqual(updated["structuralRoot"]["id"], "GB_T_1.1-2020#Root")
        clause = updated["structuralRoot"]["children"][0]
        self.assertEqual(clause["id"], "GB_T_1.1-2020#1")
        self.assertEqual(clause["logicalId"], "1")
        self.assertEqual(clause["sourceAnchors"][0]["id"], "GB_T_1.1-2020#Anchor-0001")
        element = clause["contentElements"][0]
        self.assertEqual(element["id"], "GB_T_1.1-2020#1/List-001")
        self.assertEqual(element["parentNodeId"], clause["id"])
        item = element["listItems"][0]
        self.assertEqual(item["id"], "GB_T_1.1-2020#1_a")
        # 锚点按文档序重编号（不沿用旧序号）：条款 → 内容元素 → 列表项
        self.assertEqual(item["sourceAnchor"]["id"], "GB_T_1.1-2020#Anchor-0003")
        self.assertEqual(updated["tables"][0]["id"], "GB_T_1.1-2020#Table_1")
        self.assertEqual(updated["canonicalText"]["sourceElementRefs"], [element["id"]])
        self.assertEqual(updated["canonicalText"]["id"], "GB_T_1.1-2020#Canonical")
        self.assertEqual(updated["processingRuns"][0]["id"],
                         "GB_T_1.1-2020#ProcessingRun_19700101-001")

        # 内容不变量：除标识字段外逐值不变
        def flatten(node, prefix=""):
            flat = {}
            if isinstance(node, dict):
                for key, value in node.items():
                    flat.update(flatten(value, f"{prefix}.{key}" if prefix else key))
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    flat.update(flatten(value, f"{prefix}[{index}]"))
            else:
                flat[prefix] = node
            return flat

        before, after = flatten(legacy), flatten(updated)
        self.assertEqual(set(before), set(after), "回放不得增删字段")
        identity = {"id", "logicalId", "documentId", "runId", "parentNodeId", "sourceElementRefs"}
        changed = {key for key in before if before[key] != after[key]}
        self.assertTrue(changed, "回放应改动标识")
        for key in changed:
            field = re.sub(r"\[\d+\]$", "", key.split(".")[-1])
            self.assertIn(field, identity, f"回放改动了非标识字段 {key}")

        # 幂等：对结果再回放一次，逐字节相同
        again = copy.deepcopy(updated)
        apply_element_ids(again)
        self.assertEqual(json_bytes(again), json_bytes(updated), "回放必须幂等")

    def test_apply_uses_metadata_standard_number_not_existing_id(self) -> None:
        legacy = self._legacy_ssir()
        legacy["id"] = "ssir:WRONG-SLUG"
        legacy["metadata"]["standard"]["standardNumber"] = "GB/T 5171.1-2014"
        updated = copy.deepcopy(legacy)
        apply_element_ids(updated)
        self.assertEqual(updated["id"], "GB_T_5171.1-2014")
        self.assertTrue(updated["structuralRoot"]["id"].startswith("GB_T_5171.1-2014#"))


if __name__ == "__main__":
    unittest.main()
