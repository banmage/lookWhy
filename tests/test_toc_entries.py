"""目次里的图/表行（GB/T 1.1-2020 8.2.2 i)/j)、10.3.2；GBT-C02/GBT-FM1 执行侧）。

背景（2026-09-11，用户报告）：渲染出的目次只有章条/附录/参考文献/索引，排在附录之后的
**图与表的目次整段丢失**。根因：目次块在 SSIR 里只有一段文本（抽取原样），渲染端按
结构节点自行生成目次行，图/表没有对应的结构节点，谁也没生成它们。

修复：`_toc_caption_rows` 按**文档顺序**从内容元素收图/表行（图题名在 figures 注册表，
表题名在 tables 注册表；图题也可能是独立段落，作为兜底），页码由预检通道按流对象
``ssir_id`` 记录（表格分页拆分时分片继承 id）。剔除：附录编写示例块与显式框内的
图/表（示例文档自带的，不是本文件的）、「表× 表题」格式示例占位、同一编号的续块、
正文行内引用（「图E.1～图E.12规定了…」）。
"""

from __future__ import annotations

from pathlib import Path
import unittest

from leleby_ssir.pdf_renderer import _TOC_BLANK_ROW, _toc_caption_rows


def _node(number: str, *contents: dict) -> dict:
    return {"id": f"n-{number}", "nodeType": "section", "number": number, "title": "", "contentElements": list(contents)}


def _figure(ref: str) -> dict:
    return {"id": f"c-{ref}", "presentationType": "figure", "figureRef": ref}


def _table(ref: str) -> dict:
    return {"id": f"c-{ref}", "presentationType": "table", "tableRef": ref}


def _paragraph(text: str, identifier: str = "c-p") -> dict:
    return {"id": identifier, "presentationType": "paragraph", "textContent": text}


class TocCaptionRowsTests(unittest.TestCase):
    def _rows(self, nodes: list[dict], registries: dict) -> list[list[tuple[str, str]]]:
        return _toc_caption_rows(nodes, registries)

    def test_figure_and_table_rows_in_document_order(self) -> None:
        registries = {
            "figures": {"f1": {"id": "f1", "number": "B.1", "caption": "标记体系的组成"}},
            "tables": {"t1": {"id": "t1", "number": "1", "caption": "文件名称中表示标准功能类型的词语"}},
        }
        nodes = [_node("B.3", _figure("f1"), _paragraph("图B.1 标记体系的组成", "cap-1")), _node("6.1", _table("t1"))]
        figures, tables = self._rows(nodes, registries)
        self.assertEqual(figures, [("图B.1\u3000标记体系的组成", "f1")])
        self.assertEqual(tables, [("表1\u3000文件名称中表示标准功能类型的词语", "t1")])
        self.assertEqual(_TOC_BLANK_ROW, -1)  # 目次空行占位常量（toc_story 用它插空行）

    def test_figure_caption_paragraph_used_when_registry_has_no_title(self) -> None:
        registries = {"figures": {"f1": {"id": "f1"}}, "tables": {}}
        nodes = [_node("B.3", _figure("f1"), _paragraph("图 B.1 标记体系的组成", "cap-1"))]
        figures, _tables = self._rows(nodes, registries)
        self.assertEqual(figures, [("图B.1\u3000标记体系的组成", "cap-1")])

    def test_inline_reference_is_not_a_caption(self) -> None:
        registries = {"figures": {}, "tables": {}}
        nodes = [_node("E", _paragraph("图E.1～图E.12规定了不同文件的页面格式。这些图以推荐性标准作样板。", "p1"))]
        figures, _tables = self._rows(nodes, registries)
        self.assertEqual(figures, [])

    def test_placeholder_tables_and_split_continuations_are_dropped(self) -> None:
        registries = {
            "figures": {},
            "tables": {
                "t1": {"id": "t1", "number": "3", "caption": "文件中各要素的类别"},
                "t2": {"id": "t2", "number": "3", "caption": ""},          # 跨页续块（同编号、无题名）
                "t3": {"id": "t3", "number": "×", "caption": "表题"},      # 「表× 表题」格式示例
            },
        }
        nodes = [_node("6.2", _table("t1"), _table("t2"), _t3 := _table("t3"))]
        _figures, tables = self._rows(nodes, registries)
        self.assertEqual(tables, [("表3\u3000文件中各要素的类别", "t1")])

    def test_example_and_boxed_content_is_excluded(self) -> None:
        registries = {
            "figures": {},
            "tables": {
                "t-real": {"id": "t-real", "number": "1", "caption": "本文件的表"},
                "t-example": {"id": "t-example", "number": "2", "caption": "示例文档的表"},
                "t-boxed": {"id": "t-boxed", "number": "3", "caption": "框内示例的表"},
            },
        }
        example_node = {"id": "n-ex", "nodeType": "section", "number": "A", "exampleContent": True,
                        "contentElements": [_table("t-example")]}
        boxed_content = _table("t-boxed")
        boxed_content["box"] = 7
        nodes = [_node("1", _table("t-real")), example_node, _node("9.8", boxed_content)]
        _figures, tables = self._rows(nodes, registries)
        self.assertEqual(tables, [("表1\u3000本文件的表", "t-real")])


class TocRenderingTests(unittest.TestCase):
    """真 PDF 目次里必须出现图、表行与页码（含附录图题与跨页大表）。"""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            import pymupdf  # noqa: F401
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("pymupdf unavailable")
        root = Path(__file__).resolve().parents[1]
        ssir = root / "out" / "mineru" / "GB_T_1.1-2020" / "03_ssir" / "GB_T_1.1-2020.ssir.json"
        font = root / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not ssir.is_file() or not font.is_file():
            raise unittest.SkipTest("GB_T_1.1-2020 SSIR / font asset missing")
        from leleby_ssir.pdf_renderer import render_pdf_file

        cls.tempdir = __import__("tempfile").TemporaryDirectory()
        target = Path(cls.tempdir.name) / "toc.pdf"
        render_pdf_file(str(ssir), str(target), toc_depth=2)
        import pymupdf

        cls.document = pymupdf.open(str(target))
        cls.toc_text = "\n".join(cls.document[index].get_text() for index in range(1, 6))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.document.close()
        cls.tempdir.cleanup()

    def test_figure_rows_present(self) -> None:
        for label in ("图B.1\u3000标记体系的组成", "图E.1\u3000单数页格式", "图E.12\u3000附录格式"):
            self.assertIn(label, self.toc_text, label)

    def test_table_rows_present(self) -> None:
        for label in ("表1\u3000文件名称中表示标准功能类型的词语及其英文译名", "表F.1\u3000文件中使用的字号和字体"):
            self.assertIn(label, self.toc_text, label)

    def test_rows_carry_page_numbers(self) -> None:
        # 图B.1 与跨页大表 表4 的行都必须带页码（预检通道按流对象 id 记录）。
        for label in ("图B.1", "表4"):
            row = next((line for line in self.toc_text.splitlines() if line.startswith(label)), None)
            self.assertIsNotNone(row, label)
            tail = row.rsplit(".", 1)[-1].strip()
            self.assertTrue(tail.isdigit() and 0 < int(tail) < 200, row)


if __name__ == "__main__":
    unittest.main()
