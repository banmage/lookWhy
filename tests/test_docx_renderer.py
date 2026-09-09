"""docx_renderer 单元测试：SSIR JSON → docx（doc_1，与 render.pdf 内容等价）。

覆盖：封面/目次/正文结构、表格合并单元格语义（vMerge/gridSpan）、
表格单元格脚注标记与平拍指数上标还原、真实 canonical 解析冒烟。
"""

import tempfile
import unittest
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

from leleby_ssir.docx_importer import docx_metadata, docx_to_csm_markdown
from leleby_ssir.docx_renderer import _DocxBuilder, render_docx_file, render_ssir_docx
from leleby_ssir.service import normalize_csm, parse_csm, round_trip_csm


def _mini_document() -> dict:
    """结构最小但覆盖主要内容的 SSIR 文档（绕过 schema 校验，直接喂渲染器）。"""
    return {
        "documentType": "standard",
        "metadata": {
            "common": {
                "documentIdentifier": "GB/T 12345-2021",
                "title": "测试标准",
                "titleEn": "Test standard",
                "issuer": "测试发布机构",
                "publicationDate": "2021-01-01",
                "effectiveDate": "2021-02-01",
            },
            "standard": {"standardNumber": "GB/T 12345-2021", "replaces": "GB/T 9999-2010"},
        },
        "structuralRoot": {
            "children": [
                {
                    "id": "n-toc", "nodeType": "documentBlock", "level": 1, "title": "目 次",
                    "sortOrder": 0,
                    "contentElements": [
                        {"id": "c-toc-list", "presentationType": "list", "sortOrder": 0,
                         "listItems": [{"id": "li-1", "marker": "-", "text": "1 范围", "sortOrder": 0}]},
                    ],
                },
                {
                    "id": "n-1", "nodeType": "section", "level": 1, "title": "范围", "number": "1",
                    "sortOrder": 1,
                    "contentElements": [
                        {"id": "c-p1", "presentationType": "paragraph",
                         "textContent": "本文件规定了测试要求，见 6.62607015×10⁻³⁴ J·s。",
                         "sortOrder": 0},
                    ],
                },
                {
                    "id": "n-2", "nodeType": "section", "level": 1, "title": "表2 样例",
                    "number": "2", "sortOrder": 2,
                    "contentElements": [
                        {"id": "c-table", "presentationType": "table", "tableRef": "t1", "sortOrder": 0},
                        {"id": "c-note", "presentationType": "note",
                         "textContent": "注：表中数值为示例。", "sortOrder": 1},
                    ],
                },
                {
                    "id": "n-a", "nodeType": "annex", "level": 1,
                    "title": "（资料性） 示例附录", "number": "A",
                    "sortOrder": 3,
                    "contentElements": [
                        {"id": "c-pa", "presentationType": "paragraph",
                         "textContent": "5.3.1平排条号段落。", "sortOrder": 0},
                    ],
                },
            ]
        },
        "tables": [
            {
                "id": "t1", "number": "1", "caption": "测试表", "unit": "毫米",
                "rows": [
                    {"rowIndex": 0, "isHeader": True, "cells": [
                        {"colIndex": 0, "text": "项目"},
                        {"colIndex": 1, "text": "取值", "rowspan": 2},
                        {"colIndex": 2, "text": "备注"},
                    ]},
                    {"rowIndex": 1, "isHeader": False, "cells": [
                        {"colIndex": 0, "text": "1030"},
                        {"colIndex": 2, "text": "匝间绝缘[:^a]"},
                    ]},
                    {"rowIndex": 2, "isHeader": False, "cells": [
                        {"colIndex": 0, "text": "10-2"},
                        {"colIndex": 1, "text": "s−1"},
                        {"colIndex": 2, "text": ""},
                    ]},
                ],
            }
        ],
        "figures": [],
        "formulas": [],
        "unknownContents": [],
        "sourceFiles": [],
    }


class DocxRenderStructureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name) / "mini.docx"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def render(self, document: dict) -> list[str]:
        # 结构最小的合成文档不满足完整 schema（validate 路径由
        # DocxRenderGoldenSmokeTests 真实 canonical 覆盖），直接驱动渲染器。
        return _DocxBuilder(document).render(str(self.output))

    def read(self) -> Document:
        return Document(str(self.output))

    def test_cover_toc_body_present(self) -> None:
        warnings = self.render(_mini_document())
        self.assertEqual(warnings, [])
        doc = self.read()
        paragraphs = [p.text for p in doc.paragraphs]
        joined = "\n".join(paragraphs)
        # 封面信息（标准号/名称/机构/日期/代替/英文名）
        for expected in ("GB/T 12345-2021", "测试标准", "Test standard", "测试发布机构",
                         "2021-01-01 发布", "2021-02-01 实施", "代替 GB/T 9999-2010"):
            self.assertIn(expected, joined, expected)
        # 标题（Word 大纲；编号与标题间是 U+3000 全角空格）
        headings = [p.text.replace("\u3000", " ") for p in doc.paragraphs if p.style.name.startswith("Heading")]
        self.assertTrue(any(text == "1 范围" for text in headings), headings)
        self.assertTrue(any("附录 A" in text and "资料性" in text for text in headings), headings)
        # 注释与正文
        self.assertTrue(any("注：表中数值为示例。" in text for text in paragraphs))
        self.assertTrue(any("本文件规定了测试要求" in text for text in paragraphs))

    def test_table_merges_and_superscripts(self) -> None:
        self.render(_mini_document())
        doc = self.read()
        table = doc.tables[0]
        # 表题注与单位行
        texts = [p.text for p in doc.paragraphs]
        self.assertTrue(any(t == "表1 测试表" for t in texts))
        self.assertTrue(any(t == "单位为毫米" for t in texts))
        # 合并：取值 col1 跨两行；物理行1 是 [1030, vMerge continue, 匝间绝缘a] 三个 tc
        self.assertEqual(table.rows[0].cells[1].text.strip(), "取值")
        self.assertEqual(table.rows[1].cells[1].text.strip(), "取值")  # 虚拟网格延续
        tr1_tcs = table.rows[1]._tr.findall(qn("w:tc"))
        self.assertEqual(len(tr1_tcs), 3)
        vmerge = tr1_tcs[1].find(qn("w:tcPr")).find(qn("w:vMerge"))
        self.assertIsNotNone(vmerge)
        # 上标还原：1030 → 10 + sup(30)；s−1 → s + sup(−1)
        sup_runs: list[str] = []
        for t in doc.tables:
            for row in t.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        for run in p.runs:
                            if run.font.superscript:
                                sup_runs.append(run.text)
        self.assertIn("30", sup_runs)
        self.assertIn("−1", sup_runs)
        # 表注引用点（显式 [:^a] 标记）：匝间绝缘[:^a] 的 a 应为上标
        self.assertTrue(any(run.font.superscript and run.text == "a" for run in _all_runs(doc)))
        # 表头居中、数据行居左（2026-09-07 用户裁定）
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        header_align = table.rows[0].cells[0].paragraphs[0].alignment
        body_align = table.rows[1].cells[0].paragraphs[0].alignment
        self.assertEqual(header_align, WD_ALIGN_PARAGRAPH.CENTER)
        self.assertEqual(body_align, WD_ALIGN_PARAGRAPH.LEFT)

    def test_plain_text_units_not_marked_superscript(self) -> None:
        document = _mini_document()
        cell_texts = ["长度m", "规格mm", "a)中所述"]
        document["tables"][0]["rows"][2]["cells"] = [
            {"colIndex": 0, "text": cell_texts[0]},
            {"colIndex": 1, "text": cell_texts[1]},
            {"colIndex": 2, "text": cell_texts[2]},
        ]
        self.render(document)
        doc = self.read()
        sup = set()
        for run in _all_runs(doc):
            if run.font.superscript:
                sup.add(run.text)
        # 单位 m/mm 与列项引用 a) 不得被误判为脚注上标
        # （表内仍保留真实脚注标记 a 与指数 30 的上标，见上行数据）
        self.assertNotIn("m", sup)
        self.assertNotIn("mm", sup)
        self.assertNotIn("n", sup)


def _all_runs(doc) -> list:
    runs = []
    for p in doc.paragraphs:
        runs.extend(p.runs)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    runs.extend(p.runs)
    return runs


def _table_cells(doc) -> list:
    return [cell for table in doc.tables for row in table.rows for cell in row.cells]


@unittest.skipUnless(
    Path("corpus/golden/csm/T_ZZB_1064-2019.canonical.md").is_file(),
    "corpus/golden/csm fixture unavailable",
)
class DocxRenderGoldenSmokeTests(unittest.TestCase):
    """真实语料 canonical → SSIR → docx 冒烟（schema 全量校验路径）。"""

    def test_real_standard_render_smoke(self) -> None:
        fixture = "corpus/golden/csm/T_ZZB_1064-2019.canonical.md"
        with tempfile.TemporaryDirectory() as temp:
            ssir = parse_csm(fixture)
            output = Path(temp) / "doc.docx"
            warnings = render_ssir_docx(ssir, str(output), input_file=fixture)
            self.assertEqual(warnings, [])
            doc = Document(str(output))
            self.assertGreater(len(doc.paragraphs), 20)
            headings = [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")]
            self.assertTrue(headings)
            # docx 应可被 python-docx 重新打开且标题含章号
            self.assertTrue(any(h.startswith("1") for h in headings if h[:1].isdigit()))


class DocxImportRoundtripTests(unittest.TestCase):
    """docx（doc_1 渲染产物）→ canonical 级 CSM 导入，闭环自洽。"""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp.name)
        self.docx_path = self.temp_path / "GB_T_12345-2021.docx"
        _DocxBuilder(_mini_document()).render(str(self.docx_path))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_metadata_restored_from_hidden_payload(self) -> None:
        metadata = docx_metadata(self.docx_path)
        self.assertEqual(metadata["title"], "测试标准")
        self.assertEqual(metadata["standard-number"], "GB/T 12345-2021")
        self.assertEqual(metadata["issuer"], "测试发布机构")
        self.assertEqual(metadata["publication-date"], "2021-01-01")
        self.assertEqual(metadata["document-type"], "standard")

    def test_import_markdown_structure(self) -> None:
        fm, md, warnings = docx_to_csm_markdown(self.docx_path, assets_root=self.temp_path)
        self.assertEqual(warnings, [])
        self.assertEqual(fm["title"], "测试标准")
        # 标题：docx Heading1（章）→ md ##（与 render.md 层级一致）
        self.assertIn("# 测试标准", md)
        self.assertIn("## 1 范围", md)
        self.assertIn("## 目 次", md)
        self.assertIn("## 2 表2 样例", md)
        self.assertIn("## 附录 A （资料性） 示例附录", md)
        # 表格：指令 + 加粗题注 + pipe + merge 坐标（row 0-based / column 1-based）
        self.assertIn("<!-- ssir:table id=\"docx-import-t001\" header-rows=\"1\" -->", md)
        self.assertIn("**表1 测试表**", md)
        self.assertIn("| 项目 | 取值 | 备注 |", md)
        self.assertIn('row="0" column="2" rowspan="2" colspan="1"', md)
        # 上标字形还原：s−1 → s⁻¹（表格单元），脚注标记字母原样保留
        self.assertIn("s⁻¹", md)
        self.assertIn("匝间绝缘a", md)

    def test_import_then_normalize_roundtrip(self) -> None:
        fm, md, _ = docx_to_csm_markdown(self.docx_path, assets_root=self.temp_path)
        raw = self.temp_path / "imported.md"
        raw.write_text(md, encoding="utf-8")
        canonical = self.temp_path / "imported.canonical.md"
        _, report = normalize_csm(raw, canonical)
        self.assertIsNotNone(report)
        render_md = self.temp_path / "imported.render.md"
        _ssir, _verify, rt = round_trip_csm(canonical, render_md)
        self.assertTrue(rt.passed)


class DocxRenderFileApiTests(unittest.TestCase):
    def test_render_docx_file_requires_existing_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "missing.ssir.json"
            with self.assertRaises(OSError):
                render_docx_file(str(source), str(Path(temp) / "x.docx"))


if __name__ == "__main__":
    unittest.main()
