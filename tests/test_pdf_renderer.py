import re
import unittest

from leleby_ssir.pdf_renderer import _TABLE_NOTE_CELL_RE, _append_nodes, _cell_text_natural_width, _clause_leading_number, _example_box, _footnote_superscripts, _heading_depth, _heading_parts, _latex_to_text, _list_marker, _markup, _ocr_l_one, _split_table_note_parts, _starts_new_page, _strip_pagebreaks, _table_cell_superscripts, _table_column_widths, _toc_label


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
        # _latex_to_text 对 _/^ 输出 reportlab 哨兵（\x00SUB\x00/\x00SUP\x00），
        # 由 _markup 恢复为 <sub>/<super> 标签（2026-09-02，GB_3100-2026）。
        self.assertEqual(
            _markup(_latex_to_text(r"K _ { \mathrm { T } } = \frac { T _ { \mathrm { L } } } { I _ { \mathrm { L } } }")),
            "K<sub>T</sub> = (T<sub>L</sub>)/(I<sub>L</sub>)",
        )

    def test_operators_map_to_unicode(self):
        self.assertEqual(_latex_to_text(r"a \cdot b \times c \leq d"), "a·b×c≤d")
        self.assertEqual(_latex_to_text(r"\leqslant 1"), "≤1")
        self.assertEqual(_markup(_latex_to_text(r"\mathrm { m ^ { 3 } / h }")), "m<super>3</super>/h")


class MarkupNormalisationTests(unittest.TestCase):
    def test_markup_flattens_inline_math(self):
        text = "式中： $K _ { \\mathrm { ~ T ~ } }$ 堵转转矩灵敏度，单位为牛米每安培 $( \\mathrm { N } \\cdot \\mathrm { m } / \\mathrm { A } )$"
        out = _markup(text)
        self.assertNotIn("mathrm", out)
        self.assertNotIn("$", out)
        self.assertIn("K<sub>T</sub>", out)
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

    def test_markup_unit_gap_unifies_tight_and_spaced_units(self):
        # GBT-B12 执行侧（GB/T 1.1-2020 10.4.6）：单位符号前空四分之一汉字间隙。
        # 紧贴（OCR/源文 "210mm"）与已有空格（"50 Hz"）统一成 \u00A0，消除同文档
        # 不一致；% 前不留间隙（GB/T 15835-2011 示例 "34.05%"、"63%~68%"）。
        self.assertEqual(
            _markup("外形尺寸为210mm×150mm"),
            "外形尺寸为210\xa0mm×150\xa0mm",
        )
        self.assertEqual(_markup("0.2℃时测得"), "0.2\xa0℃时测得")
        self.assertEqual(_markup("电压为85K与15N的试样"), "电压为85\xa0K与15\xa0N的试样")
        self.assertEqual(_markup("持续2h 30min"), "持续2\xa0h 30\xa0min")
        self.assertEqual(_markup("偏差应在±10 %范围内"), "偏差应在±10%范围内")
        self.assertEqual(_markup("34.05% 63%~68%"), "34.05% 63%~68%")
        self.assertEqual(_markup("525 μm"), "525\xa0μm")
        # 分表/分图代号（GB/T 1.1 9.8.1.3 引用的 “表2a”）不是单位，不插间隙；
        # 列项引用（“4.2b)”）按排版惯例留间隙；表/图前的量值不受排除影响。
        self.assertEqual(
            _markup("将“表2”分为“表2a”和“表2b”"),
            "将“表2”分为“表2a”和“表2b”",
        )
        self.assertEqual(_markup("见4.2b)的规定"), "见4.2\xa0b)的规定")
        self.assertEqual(_markup("在5℃～40℃下"), "在5\xa0℃～40\xa0℃下")


class UntitledClauseFlushTests(unittest.TestCase):
    """Bare paragraphs starting with a clause number render flush left."""

    def test_bare_clause_paragraphs_are_detected(self):
        self.assertEqual(_clause_leading_number("5.5.2承压零件应做静水压试验。"), "5.5.2")
        self.assertEqual(_clause_leading_number("5.3.1 泵应选用与介质适宜的轴封。"), "5.3.1")
        self.assertEqual(_clause_leading_number("B.1.3.1抽样"), "B.1.3.1")
        self.assertEqual(_clause_leading_number("A.2 试验应在 20 ℃ 下进行。"), "A.2")

    def test_list_marker_normalisation_maps_ocr_dashes(self) -> None:
        # GB/T 1.1-2020 6.6.3：破折号族（-、—、——、———、– 等 OCR 长度变体）
        # 一律渲染为 ——，• 归一为 ·，其余原样保留。
        self.assertEqual(_list_marker("-"), "——")
        self.assertEqual(_list_marker("—"), "——")
        self.assertEqual(_list_marker("——"), "——")
        self.assertEqual(_list_marker("———"), "——")
        self.assertEqual(_list_marker("————"), "——")
        self.assertEqual(_list_marker("–"), "——")
        self.assertEqual(_list_marker("-—"), "——")
        self.assertEqual(_list_marker("•"), "·")
        self.assertEqual(_list_marker("a)"), "a)")
        self.assertEqual(_list_marker("1)"), "1)")
        self.assertEqual(_list_marker("·"), "·")
        self.assertEqual(_list_marker("●"), "●")

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
        # 单位字母/大写不误伤（仍不是上角标，但按 GBT-B12 补单位间隙）
        self.assertEqual(rendered("规格mm"), "规格mm")
        self.assertEqual(rendered("输入功率W"), "输入功率W")
        self.assertEqual(rendered("250V"), "250\xa0V")
        self.assertEqual(rendered("≤55 dB(A)"), "≤55\xa0dB(A)")

    def test_table_cell_superscripts_only_lowercase_leading_markers(self) -> None:
        # 回归（2026-08-31，GB_T_43726-2024 表6）："A 相"/"B相"/"C相" 的相位
        # 字母是内容，不是脚注标记，不应上角标；GB/T 1.1 表脚注用 a/b/c 小写。
        def rendered(text: str) -> str:
            return _markup(_table_cell_superscripts(text))

        self.assertEqual(rendered("A 相"), "A 相")
        self.assertEqual(rendered("B相"), "B相")
        self.assertEqual(rendered("C相"), "C相")
        # 小写脚注标记仍上角标
        self.assertEqual(rendered("a 说明"), "<super>a</super> 说明")
        self.assertEqual(rendered("b黑体表示…"), "<super>b</super>黑体表示…")
        # 列项引用 ")" 不误伤
        self.assertEqual(rendered("编写a)中所述"), "编写a)中所述")

    def test_body_footnote_explanation_marker_superscript(self) -> None:
        # 回归（2026-08-31，GB_T_1.1-2020 附录 E 图脚注）：脚注成对出现——
        # 正文脚注解释行（"a 填写行业标准代号。"）行首标记渲染为上角标
        # （GBT-X04 执行侧）；公式变量行/正文变量/列项引用不误伤。
        def rendered(text: str) -> str:
            return _markup(_footnote_superscripts(text))

        self.assertEqual(rendered("a 填写行业标准代号。"), "<super>a</super> 填写行业标准代号。")
        self.assertEqual(rendered("a国家标准发布部门按照有关规定填写。"), "<super>a</super>国家标准发布部门按照有关规定填写。")
        self.assertEqual(rendered("b行业标准发布部门按照有关规定填写。"), "<super>b</super>行业标准发布部门按照有关规定填写。")
        # 合并段落中的下一条解释标记（"a 说明。\nb说明。" → ᵇ；_markup 将 \n 折叠为空格）
        self.assertEqual(
            rendered("a 填写行业标准代号。\nb行业标准发布部门按照有关规定填写。"),
            "<super>a</super> 填写行业标准代号。 <super>b</super>行业标准发布部门按照有关规定填写。",
        )
        # 公式变量行（字母后破折号）不触发
        self.assertEqual(rendered("n —转速，单位为转每分"), "n —转速，单位为转每分")
        # 大写是内容不是标记；正文变量/列项引用不误伤
        self.assertEqual(rendered("A 相为红色。"), "A 相为红色。")
        self.assertEqual(rendered("驱动稳速转台至转速n，测量各相绕组"), "驱动稳速转台至转速n，测量各相绕组")
        self.assertEqual(rendered("产品规范标准通常考虑编写a)中所述的证实方法"), "产品规范标准通常考虑编写a)中所述的证实方法")

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


class ExampleBoxPageBreakTests(unittest.TestCase):
    def test_strip_pagebreaks_removes_page_break_flowables(self) -> None:
        class FakePageBreak:
            pass

        class FakeParagraph:
            pass

        box = [FakeParagraph(), FakePageBreak(), FakeParagraph(), FakePageBreak()]
        stripped = _strip_pagebreaks(box, FakePageBreak)
        self.assertEqual(len(stripped), 2)
        self.assertTrue(all(isinstance(flowable, FakeParagraph) for flowable in stripped))

    def test_strip_pagebreaks_noop_without_pagebreak_type(self) -> None:
        box = ["a", "b"]
        self.assertEqual(_strip_pagebreaks(box, None), box)


class ExampleBoxKeepTogetherTests(unittest.TestCase):
    """Figures inside annex example boxes must not crash the box table.

    Regression (2026-08-31, GB_T_20001.6-2017 附录示例框 图 4.1/图 4.2):
    _append_content wraps figure + caption in reportlab KeepTogether, whose
    wrap() hardcodes 0xffffff (~16.7M pt) to force a split.  The example-box
    table puts every flowable in its own row, so the KeepTogether row becomes
    ~16.7M pt tall -> reportlab LayoutError.  _example_box must unwrap
    KeepTogether so each sub-flowable gets its own row.
    """

    @staticmethod
    def _box(*flowables):
        from reportlab.lib import colors
        from reportlab.platypus import Table, TableStyle

        return _example_box(list(flowables), "frame", colors, Table, TableStyle)

    def test_keep_together_contents_become_individual_rows(self) -> None:
        from reportlab.platypus import KeepTogether, Spacer

        image, caption = Spacer(1, 10), Spacer(1, 20)
        table = self._box(KeepTogether([image, caption]), Spacer(1, 30))
        cells = table._cellvalues
        self.assertEqual(len(cells), 3)
        self.assertFalse(any(isinstance(row[0], KeepTogether) for row in cells))

    def test_pagebreak_inside_keep_together_is_stripped(self) -> None:
        from reportlab.platypus import KeepTogether, PageBreak, Spacer

        table = self._box(KeepTogether([Spacer(1, 10), PageBreak()]))
        cells = table._cellvalues
        self.assertEqual(len(cells), 1)
        self.assertFalse(isinstance(cells[0][0], PageBreak))

    def test_plain_flowables_keep_their_rows(self) -> None:
        from reportlab.platypus import Spacer

        table = self._box(Spacer(1, 10), Spacer(1, 20))
        self.assertEqual(len(table._cellvalues), 2)


class NestedExampleContentTests(unittest.TestCase):
    """Nested exampleContent nodes must flatten into the current box.

    Regression (2026-08-31, GB_T_20001.6-2017 附录 规程标准编写示例): the
    example document's own clause tree (5 繁育程序 → 5.1 田间选择 → 5.4.1
    茎尖培养基的制备) is emitted as exampleContent-marked sibling nodes.
    _append_node recursed via _append_nodes, whose grouping logic wrapped the
    children in a second _example_box -> Table inside a Table cell.  Tables in
    cells cannot split across pages, so a 36-row / 1194pt inner table blew past
    the 688pt frame -> reportlab LayoutError.  Example-internal children are
    now appended one by one into the current box (no nested box).
    """

    @staticmethod
    def _render_story(nodes):
        from pathlib import Path

        from reportlab.lib import colors
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

        styles = {}
        for name in ("example-label", "example-title", "example-content", "body",
                     "body-flush", "caption", "table-unit", "note", "list", "list-sub",
                     "formula", "section", "subclause", "clause", "front"):
            styles[name] = ParagraphStyle(name, fontName="Helvetica", fontSize=10)
        from leleby_ssir.pdf_renderer import PDFRenderReport

        report = PDFRenderReport(
            input_file="test.pdf", output_file="test.render.pdf",
            profile_file="", profile_id="", font_file="",
        )
        story: list = []
        _append_nodes(
            story, nodes,
            registries={"tables": {}, "figures": {}, "formulas": {}},
            styles=styles, font="Helvetica", report=report, asset_dir=Path("."),
            colors=colors, Table=Table, TableStyle=TableStyle, Paragraph=Paragraph,
            Spacer=Spacer, Image=Image, marker_factory=None, PageBreak=None,
            example_default="frame",
        )
        return story

    def test_nested_example_content_produces_single_flat_box(self) -> None:
        nodes = [
            {
                "nodeType": "clause", "number": "5", "title": "马铃薯脱毒试管苗繁育",
                "exampleContent": True, "contentElements": [], "children": [
                    {
                        "nodeType": "clause", "number": "5.1", "title": "田间选择",
                        "exampleContent": True, "contentElements": [
                            {"presentationType": "paragraph", "textContent": "选择无病毒症状的种薯。"},
                        ], "children": [],
                    },
                    {
                        "nodeType": "clause", "number": "5.2", "title": "病毒检测筛选",
                        "exampleContent": True, "contentElements": [], "children": [],
                    },
                ],
            },
        ]
        story = self._render_story(nodes)
        # 只有一个外层示例框表格，框内不再嵌套表格。
        self.assertEqual(len(story), 1)
        box = story[0]
        for row in box._cellvalues:
            self.assertFalse(isinstance(row[0], type(box)),
                             f"nested box table found in cell: {row[0]!r}")
        texts = [str(cell[0].getPlainText()) for cell in box._cellvalues]
        self.assertIn("5 马铃薯脱毒试管苗繁育", texts)
        self.assertIn("5.1 田间选择", texts)
        self.assertIn("5.2 病毒检测筛选", texts)


class TableCellLineBreakTests(unittest.TestCase):
    """表单元格行结构（<br>，merge 阶段从源文本层恢复）渲染为真实换行。

    Regression (2026-08-31, GB_T_20001.6-2017 表1)：单元格 "术语和定义
    ……程序确立程序指示b追溯/证实方法……规范性附录" 被 OCR 压成单行，恢复为
    <br> 连接的多行后，_markup 必须把它转成 <br/>（不能折叠为空格），且
    行尾脚注标记 b 仍触发上标。
    """

    def test_br_becomes_line_break_and_footnote_superscript_fires(self) -> None:
        cell = "术语和定义<br>……<br>程序确立<br>程序指示b<br>追溯/证实方法<br>……<br>规范性附录"
        marked = cell.replace("<br>", "\x00BR\x00")
        out = _markup(_table_cell_superscripts(marked)).replace("\x00BR\x00", "<br/>")
        self.assertIn("<br/>", out)
        self.assertIn("<super>b</super>", out)
        self.assertEqual(out.count("<br/>"), 6)

    def test_plain_cells_unaffected(self) -> None:
        cell = "规格mm"
        marked = cell.replace("<br>", "\x00BR\x00")
        out = _markup(_table_cell_superscripts(marked)).replace("\x00BR\x00", "<br/>")
        self.assertNotIn("<br/>", out)
        self.assertNotIn("<super>", out)


class Gb3100SuperscriptTableNoteTests(unittest.TestCase):
    """GB_3100-2026 六项排版修复回归（2026-09-02）。

    Fix C/D：HTML <sup>/<sub> 与缺字形 Unicode 上标（⁰⁵⁶⁷⁸⁹⁻⁺，Noto Serif
    CJK SC 无字形）→ reportlab <super>/<sub> 真上标；Fix E：表格平拍指数恢复；
    Fix F：LaTeX 拍平输出哨兵；Fix H：表注行按「注N：」拆分。
    """

    def test_html_sup_sub_map_to_reportlab_tags(self) -> None:
        # Fix C：MinerU 数学幂/原子下标标签 → 真上标/下标（sentinel 恢复）。
        self.assertEqual(_markup("10<sup>27</sup>"), "10<super>27</super>")
        self.assertEqual(_markup("N<sub>A</sub>为"), "N<sub>A</sub>为")

    def test_missing_glyph_unicode_superscripts_become_super(self) -> None:
        # Fix D：正文宋体缺 ⁰⁵⁶⁷⁸⁹⁻⁺ 字形，直接渲染成 .notdef 方框；
        # 归一为 <super> 内普通字符，相邻上标合并为一个 run。
        self.assertEqual(_markup("10⁻⁸ s 可写成"), "10<super>−8</super> s 可写成")
        self.assertEqual(_markup("10⁸称为亿"), "10<super>8</super>称为亿")
        self.assertEqual(_markup("米·秒⁻¹"), "米·秒<super>−</super>¹")

    def test_table_cell_flat_exponents_recovered(self) -> None:
        # Fix E：GB_3100-2026 表2/表3/附录B 平拍上标还原（1030→10³⁰、
        # s−1→s⁻¹、N/m2→N/m²、10-2→10⁻²、10²4→10²⁴；100 不猜）。
        self.assertEqual(_markup(_table_cell_superscripts("1030")), "10<super>30</super>")
        self.assertEqual(_markup(_table_cell_superscripts("10-2")), "10<super>−2</super>")
        self.assertEqual(_markup(_table_cell_superscripts("10²4")), "10<super>24</super>")
        self.assertEqual(_markup(_table_cell_superscripts("1 Hz = 1 s−1")), "1\xa0Hz = 1\xa0s<super>−1</super>")
        self.assertEqual(_markup(_table_cell_superscripts("1 Pa = 1 N/m2")), "1\xa0Pa = 1\xa0N/m<super>2</super>")
        self.assertEqual(_markup(_table_cell_superscripts("100")), "100")
        self.assertEqual(_markup(_table_cell_superscripts("centi")), "centi")

    def test_latex_emits_sentinels_and_markup_restores_tags(self) -> None:
        # Fix F：4.2 常量行 LaTeX → 可读文本 + 上标哨兵；数字逐字空格收紧；
        # \Delta V 命令终止空格折叠（ΔV 同一量符号），J s 拉丁乘积空格保留。
        self.assertEqual(
            _markup("$6 . 6 2 6 0 7 0 1 5 \\times 1 0 ^ { - 3 4 } \\mathrm { J } \\mathrm { s } ;$"),
            "6.62607015×10<super>−34</super> J s ;",
        )
        self.assertEqual(_markup("$\\cdot \\Delta V _ { \\mathrm { c s } }$"), "·ΔV<sub>cs</sub>")
        self.assertEqual(_markup("$K _ { \\mathrm { c d } }$"), "K<sub>cd</sub>")

    def test_table_note_cell_split_into_per_note_parts(self) -> None:
        # Fix H：表注行（注1：…注2：… 连排）拆成每条注独立文本；行内 <br>
        # （注6 续句）保留为哨兵，尾部 <br>（下一条注前）整段剥掉。
        cell = "注1：周、月、年为一般常用时间单位。注2：升的符号中，小写字母l为备用符号。"
        parts = _split_table_note_parts(cell)
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], "注1：周、月、年为一般常用时间单位。")
        self.assertEqual(parts[1], "注2：升的符号中，小写字母l为备用符号。")

    def test_table_note_cell_keeps_inner_br_and_drops_trailing_sentinel(self) -> None:
        # 回归（2026-09-02 表4 注7~注10）：跨页吸收回表内的续注以 <br> 分隔，
        # 拆分后下一条注前的尾部哨兵必须整段剥掉——只 strip NUL 会残留 "BR"
        # 字面文本（渲染成 Ⓡ-like 字符）；行中 <br>（注6 续句）必须保留。
        cell = "注6：道尔顿（Da）…它等于处<br>于静止状态和基态的自由碳12原子质量的1/12。<br>注7：电子伏是电子在真空中通过一个1 V的电位差而获得的动能。<br>注8：公顷的国际通用符号为ha。<br>注11：公里为千米的俗称，符号为km。"
        parts = _split_table_note_parts(cell)
        self.assertEqual(len(parts), 4)
        self.assertIn("\x00BR\x00", parts[0])  # 行中续句换行保留
        self.assertNotIn("BR", parts[1])  # 尾部哨兵不残留 "BR" 字面
        self.assertNotIn("BR", parts[2])
        self.assertEqual(parts[1], "注7：电子伏是电子在真空中通过一个1 V的电位差而获得的动能。")
        self.assertEqual(parts[3], "注11：公里为千米的俗称，符号为km。")

    def test_table_note_cell_requires_note_lead(self) -> None:
        self.assertFalse(_TABLE_NOTE_CELL_RE.match("规格mm"))
        self.assertTrue(_TABLE_NOTE_CELL_RE.match("注1：…"))
        self.assertTrue(_TABLE_NOTE_CELL_RE.match("注：…"))


class TableColumnWidthTests(unittest.TestCase):
    """按内容分配表格列宽（2026-09-03，通用规则：尽量利用版面宽度）。

    GBT-B07 执行侧扩展：列宽 ∝ 列内容自然宽度（CJK≈1em、拉丁≈0.55em），
    比例充满版心宽 455pt；通栏注行/单长格不挤占单列需求；保底列宽防空列。
    """

    _IMG = re.compile(r"!\[(?:[^\]]*)\]\(([^)]+)\)")

    @staticmethod
    def _rows(header: list[str], data: list[list[str]]) -> list[dict]:
        def _cells(texts: list[str]) -> list[dict]:
            return [
                {"colIndex": i, "colspan": 1, "rowspan": 1, "text": t}
                for i, t in enumerate(texts)
            ]

        return [
            {"rowIndex": 0, "isHeader": True, "cells": _cells(header)},
            *[
                {"rowIndex": i + 1, "isHeader": False, "cells": _cells(row)}
                for i, row in enumerate(data)
            ],
        ]

    def test_natural_width_cjk_vs_latin(self) -> None:
        self.assertEqual(_cell_text_natural_width("量的名称", 9.0), 36.0)
        self.assertAlmostEqual(_cell_text_natural_width("tex", 9.0), 3 * 0.55 * 9.0)
        # <br> 拆行取最长行（14 个全角字符含句号）
        self.assertAlmostEqual(
            _cell_text_natural_width("短。\n这一行明显更长需要更宽的列。", 9.0),
            14 * 9.0,
        )

    def test_widths_fill_frame_and_follow_content(self) -> None:
        # 表4 型：关系列（长公式）明显宽于前三列；列宽和恰等于版心宽。
        rows = self._rows(
            ["量的名称", "单位名称", "单位符号", "与SI单位的关系"],
            [
                ["时间", "分", "min", "1 min = 60 s"],
                ["速度", "节", "kn", "1 kn=1 n mile/h=（1852/3600）m/s（只用于航行）"],
                ["线密度", "特[克斯]", "tex", "1 tex = 10⁻¹ kg/m"],
            ],
        )
        widths = _table_column_widths(rows, 4, 9.0, {}, self._IMG)
        self.assertAlmostEqual(sum(widths), 455.0, places=6)
        self.assertGreater(widths[3], widths[0])
        self.assertGreater(widths[3], 2 * widths[0])  # 关系列显著宽于窄列

    def test_full_width_note_row_does_not_dominate(self) -> None:
        # 通栏注行（colspan=全部）不挤占单列需求：表头 36pt 需求列仍按内容分配。
        rows = self._rows(["A", "B", "C", "D"], [])
        rows.append(
            {
                "rowIndex": 99,
                "isHeader": False,
                "cells": [
                    {"colIndex": 0, "colspan": 4, "rowspan": 1, "text": "注1：" + "很长的注内容。" * 40},
                    {"colIndex": 1, "colspan": 1, "rowspan": 1, "text": ""},
                    {"colIndex": 2, "colspan": 1, "rowspan": 1, "text": ""},
                    {"colIndex": 3, "colspan": 1, "rowspan": 1, "text": ""},
                ],
            },
        )
        widths = _table_column_widths(rows, 4, 9.0, {}, self._IMG)
        # 注行不撑爆任何单列（通栏摊分后各列仍按表头/数据内容分配）
        self.assertLess(widths[0], 150)
        self.assertAlmostEqual(sum(widths), 455.0, places=6)

    def test_empty_column_gets_floor_width(self) -> None:
        rows = self._rows(["名称", "", "符号"], [["时间", "", "min"], ["长度", "", "m"]])
        widths = _table_column_widths(rows, 3, 9.0, {}, self._IMG)
        self.assertGreaterEqual(widths[1], 24.0)
        self.assertAlmostEqual(sum(widths), 455.0, places=6)


if __name__ == "__main__":
    unittest.main()
