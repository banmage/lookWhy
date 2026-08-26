import unittest

from leleby_ssir.pdf_renderer import _clause_leading_number, _heading_depth, _heading_parts, _latex_to_text, _list_marker, _markup, _ocr_l_one, _starts_new_page, _table_cell_superscripts, _toc_label


class PdfRendererHeadingTests(unittest.TestCase):
    def test_heading_number_is_not_split_when_title_contains_only_number(self):
        node = {"nodeType": "documentBlock", "title": "3.1.2"}
        self.assertEqual(_heading_parts(node), ("3.1.2", "", False))
        self.assertEqual(_toc_label(node), "3.1.2")

    def test_heading_number_is_split_from_compact_title(self):
        node = {"nodeType": "documentBlock", "title": "9.4.3全称、简称和缩略语"}
        self.assertEqual(_heading_parts(node), ("9.4.3", "全称、简称和缩略语", False))

    def test_annex_and_front_matter_start_new_pages(self):
        self.assertTrue(_starts_new_page({"nodeType": "annex"}, "文件格式", True))
        self.assertTrue(_starts_new_page({"nodeType": "documentBlock"}, "引言", False))
        self.assertFalse(_starts_new_page({"nodeType": "section", "number": "8.4"}, "引言", False))

    def test_heading_depth_handles_multi_digit_segments(self):
        # A single-digit-only pattern mis-classified 5.10 as depth 0 and
        # dropped it into the indented body style; every segment may be
        # multi-digit (GBT-H02/H03).
        self.assertEqual(_heading_depth("5"), 1)
        self.assertEqual(_heading_depth("5.9"), 2)
        self.assertEqual(_heading_depth("5.10"), 2)
        self.assertEqual(_heading_depth("5.10.1"), 3)
        self.assertEqual(_heading_depth("A.10"), 3)


class LatexToTextTests(unittest.TestCase):
    def test_mathrm_wrapper_is_unwrapped(self):
        self.assertEqual(_latex_to_text(r"\mathrm{~T~}"), "T")
        self.assertEqual(_latex_to_text(r"$\mathrm{kPa}$".strip("$")), "kPa")
        self.assertEqual(_latex_to_text(r"\mathrm { k P a }"), "kPa")

    def test_subscript_and_fraction_flatten(self):
        self.assertEqual(_latex_to_text(r"K _ { \mathrm { T } } = \frac { T _ { \mathrm { L } } } { I _ { \mathrm { L } } }"), "KT = (TL)/(IL)")

    def test_operators_map_to_unicode(self):
        self.assertEqual(_latex_to_text(r"\mathrm { m ^ { 3 } / h }"), "m3/h")
        self.assertEqual(_latex_to_text(r"a \cdot b \times c \leq d"), "a·b×c≤d")
        self.assertEqual(_latex_to_text(r"\leqslant 1"), "≤1")


class MarkupNormalisationTests(unittest.TestCase):
    def test_markup_flattens_inline_math(self):
        text = "式中： $K _ { \\mathrm { ~ T ~ } }$ 堵转转矩灵敏度，单位为牛米每安培 $( \\mathrm { N } \\cdot \\mathrm { m } / \\mathrm { A } )$"
        out = _markup(text)
        self.assertNotIn("mathrm", out)
        self.assertNotIn("$", out)
        self.assertIn("KT", out)
        self.assertIn("N·m/A", out)

    def test_markup_normalises_untitled_clause_number_spacing(self):
        out = _markup("5.3.2泵抽送重要危险需降温冷却用水。")
        self.assertIn("5.3.2\u3000泵抽送", out)
        out2 = _markup("5.3.1 泵应选用与介质适宜的轴封。")
        self.assertIn("5.3.1\u3000泵应选用", out2)
        out3 = _markup("B.1.3.1抽样")
        self.assertIn("B.1.3.1\u3000抽样", out3)

    def test_markup_collapses_ocr_whitespace_and_joins_digit_groups(self):
        out = _markup("额定电压为28.8 V、   32.4 V、36 V 和 48 V")
        self.assertNotIn("    ", out)
        out2 = _markup("800 W、2 000 W、2 200 W和 2 400 W")
        self.assertIn("2000", out2)
        self.assertIn("2200", out2)

    def test_markup_uses_nbsp_between_number_and_unit(self):
        out = _markup("额定频率为50 Hz。")
        self.assertIn("50\u00A0Hz", out)


class UntitledClauseFlushTests(unittest.TestCase):
    """Bare paragraphs starting with a clause number render flush left."""

    def test_bare_clause_paragraphs_are_detected(self):
        self.assertEqual(_clause_leading_number("5.5.2承压零件应做静水压试验。"), "5.5.2")
        self.assertEqual(_clause_leading_number("5.3.1 泵应选用与介质适宜的轴封。"), "5.3.1")
        self.assertEqual(_clause_leading_number("B.1.3.1抽样"), "B.1.3.1")
        self.assertEqual(_clause_leading_number("A.2 试验应在 20 ℃ 下进行。"), "A.2")

    def test_list_marker_normalisation_maps_ocr_dashes(self) -> None:
        # GB/T 1.1-2020 6.6.3：- / — 渲染为 ——，• 归一为 ·，其余原样保留。
        self.assertEqual(_list_marker("-"), "——")
        self.assertEqual(_list_marker("—"), "——")
        self.assertEqual(_list_marker("——"), "——")
        self.assertEqual(_list_marker("•"), "·")
        self.assertEqual(_list_marker("a)"), "a)")
        self.assertEqual(_list_marker("1)"), "1)")
        self.assertEqual(_list_marker("·"), "·")

    def test_table_cell_superscripts_marks_footnote_references(self):
        # GB/T 1.1 表脚注：匝间绝缘ᵃ —— OCR 还原成普通字符后渲染回上角标（GBT-C18）。
        # 哨兵经 _markup 的 XML 转义后恢复为真实 <super> 标签。
        def rendered(text: str) -> str:
            return _markup(_table_cell_superscripts(text))

        self.assertEqual(rendered("匝间绝缘a"), "匝间绝缘<super>a</super>")
        self.assertEqual(rendered("匝间绝缘ａ"), "匝间绝缘<super>ａ</super>")
        self.assertEqual(
            rendered("a 匝间绝缘的检验可在部件生产过程中进行。"),
            "<super>a</super> 匝间绝缘的检验可在部件生产过程中进行。",
        )
        # 单位字母/大写不误伤
        self.assertEqual(rendered("规格mm"), "规格mm")
        self.assertEqual(rendered("输入功率W"), "输入功率W")
        self.assertEqual(rendered("250V"), "250V")
        self.assertEqual(rendered("≤55 dB(A)"), "≤55\xa0dB(A)")

    def test_ocr_l_one_heuristic(self) -> None:
        # 全字母列表中的孤立 1）是 OCR 把 l）误读成 1）。
        self.assertTrue(_ocr_l_one(["a）", "b）", "1）", "c）", "d）"]))
        self.assertTrue(_ocr_l_one(["a)", "1)", "b)"]))
        # 真子列表（多个数字）不触发；单条 a)+1) 也不触发。
        self.assertFalse(_ocr_l_one(["a）", "1）", "2）"]))
        self.assertFalse(_ocr_l_one(["a）", "1）"]))
        self.assertFalse(_ocr_l_one(["1）", "2）"]))
        self.assertFalse(_ocr_l_one(["a）", "b）"]))

    def test_plain_body_paragraphs_stay_indented(self):
        # No leading clause number: keeps the body first-line indent.
        self.assertIsNone(_clause_leading_number("额定电压为28.8 V、32.4 V和 48 V。"))
        # A number followed by a Latin letter is a value, not a clause.
        self.assertIsNone(_clause_leading_number("3.2 kW 的电机应可靠工作。"))
        self.assertIsNone(_clause_leading_number("GB/T 33634 规定了试验方法。"))


if __name__ == "__main__":
    unittest.main()
