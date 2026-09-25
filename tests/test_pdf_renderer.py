import re
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml

# GBT-B12 数值-单位固定字隙（正文五号 10.5pt 的 1/4 汉字）：_markup 输出的白字哨兵。
_UNIT_GAP = '<font size="2.625" color="white">中</font>'

from leleby_ssir.pdf_renderer import _TABLE_NOTE_CELL_RE, _BODY_MEASURE, _EXAMPLE_FRAME_WIDTH, _FORMULA_IMAGE_DPI, _FORMULA_IMAGE_EM_PT, _append_nodes, _cell_text_natural_width, _clause_head_gap, _clause_leading_number, _node_clause_number, _display_style_latex, _example_box, _example_box_inner_width, _formula_image, _formula_image_scale, _footnote_superscripts, _heading_depth, _heading_parts, _label_markup, _latex_has_cjk, _latex_to_text, _list_marker, _list_marker_gap, _mark_note_example_labels, _markup, _note_example_label, _note_example_label_span, _ocr_l_one, _script_gap_html, _split_table_note_parts, _starts_new_page, _strip_pagebreaks, _table_cell_superscripts, _table_column_widths, _toc_label


def _script_gap(em: float = 10.5, overhang: float = 0.0) -> str:
    """角标字隙（GEN-140）的期望形态：em ×（\\scriptspace 0.05em + 基字符超伸）。

    基字符在该角标垂直带内的墨迹超伸（em）在用例里写成常量（实测值，见
    `test_renderer_script_gap`）；未登记字面 / 无超伸时只剩固定部分，正文号
    10.5pt → 0.525pt。
    """
    return _script_gap_html(em * (0.05 + max(0.0, overhang)))


_SCRIPT_GAP_105 = _script_gap()      # 正文号下的固定字隙（无超伸）


def _pin_math_faces(test: unittest.TestCase, body: str = "", italic: str = "") -> None:
    """固定渲染期的 math 字面（GEN-140 的字隙含**字形度量**，用例不得依赖执行顺序）。"""
    from leleby_ssir import pdf_renderer as _renderer

    previous = (_renderer._MATH_BODY_FACE, _renderer._MATH_ITALIC_FACE)
    _renderer._MATH_BODY_FACE, _renderer._MATH_ITALIC_FACE = body, italic
    test.addCleanup(setattr, _renderer, "_MATH_BODY_FACE", previous[0])
    test.addCleanup(setattr, _renderer, "_MATH_ITALIC_FACE", previous[1])


TABLE_FIXTURE = {
    "id": "t1", "number": "1", "caption": "系统性能要求",
    "rows": [
        {"rowIndex": 0, "isHeader": True, "cells": [
            {"colIndex": 0, "text": "序号"},
            {"colIndex": 1, "text": "技术参数名称"},
            {"colIndex": 2, "text": "参数"},
        ]},
        {"rowIndex": 1, "isHeader": False, "cells": [
            {"colIndex": 0, "text": "1"},
            {"colIndex": 1, "text": "模拟量U、I测量误差"},
            {"colIndex": 2, "text": "≤0.2%"},
        ]},
    ],
}


class PdfRendererHeadingTests(unittest.TestCase):
    def test_heading_number_is_not_split_when_title_contains_only_number(self):
        node = {"nodeType": "documentBlock", "title": "3.1.2"}
        self.assertEqual(_heading_parts(node), ("3.1.2", "", False))
        self.assertEqual(_toc_label(node), "3.1.2")

    def test_heading_number_is_split_from_compact_title(self):
        node = {"nodeType": "documentBlock", "title": "9.4.3全称、简称和缩略语"}
        self.assertEqual(_heading_parts(node), ("9.4.3", "全称、简称和缩略语", False))

    def test_annex_toc_entry_keeps_normative_status(self):
        # GB/T 1.1-2020 10.3.2：附录的目次应给出附录编号，后跟“(规范性)”或
        # “(资料性)”，空一个汉字的间隙后给出附录标题。
        node = {"nodeType": "annex", "number": "A", "title": "（资料性） 层次编号示例"}
        self.assertEqual(_heading_parts(node), ("A", "层次编号示例", True))
        self.assertEqual(_toc_label(node), "附录 A（资料性）\u3000层次编号示例")

    def test_annex_toc_entry_without_status_stays_bare(self):
        node = {"nodeType": "annex", "number": "C", "title": "条款类型"}
        self.assertEqual(_toc_label(node), "附录 C\u3000条款类型")

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
    def setUp(self) -> None:
        # 角标字隙（GEN-140）的字形度量随字面全局变化：清空字面 → 只留固定部分。
        _pin_math_faces(self)

    def test_mathrm_wrapper_is_unwrapped(self):
        self.assertEqual(_latex_to_text(r"\mathrm{~T~}"), "T")
        self.assertEqual(_latex_to_text(r"$\mathrm{kPa}$".strip("$")), "kPa")
        self.assertEqual(_latex_to_text(r"\mathrm { k P a }"), "kPa")

    def test_subscript_and_fraction_flatten(self):
        # _latex_to_text 对 _/^ 输出 reportlab 哨兵（\x00SUB\x00/\x00SUP\x00），
        # 由 _markup 恢复为 <sub>/<super> 标签（2026-09-02，GB_3100-2026）；
        # 每个角标前有角标字隙（GEN-140：基字符超伸 + \scriptspace）。
        gap = _SCRIPT_GAP_105
        self.assertEqual(
            _markup(_latex_to_text(r"K _ { \mathrm { T } } = \frac { T _ { \mathrm { L } } } { I _ { \mathrm { L } } }")),
            f"K{gap}<sub>T</sub> = (T{gap}<sub>L</sub>)/(I{gap}<sub>L</sub>)",
        )

    def test_operators_map_to_unicode(self):
        self.assertEqual(_latex_to_text(r"a \cdot b \times c \leq d"), "a·b×c≤d")
        self.assertEqual(_latex_to_text(r"\leqslant 1"), "≤1")

    def test_simple_fractions_use_the_glyph_the_font_carries(self):
        """¼ ½ ¾ 用分数字形（思源宋体只带这三个分数字形；GB/T 10401-2023 表10 型）。"""
        self.assertEqual(_latex_to_text(r"\frac{1}{4}"), "¼")
        self.assertEqual(_latex_to_text(r"\frac{1}{2}"), "½")
        self.assertEqual(_latex_to_text(r"\frac{3}{4}"), "¾")
        self.assertEqual(_latex_to_text(r"\frac { 1 } { 2 }"), "½")

    def test_fractions_without_a_glyph_still_flatten(self):
        # Number Forms 区（⅓ ⅔ ⅕…）在渲染字体里缺字形，字母/多位分数同样不适用字形。
        self.assertEqual(_latex_to_text(r"\frac{2}{3}"), "(2)/(3)")
        self.assertEqual(_latex_to_text(r"\frac{1}{5}"), "(1)/(5)")
        self.assertEqual(_latex_to_text(r"\frac{10}{20}"), "(10)/(20)")
        self.assertEqual(_latex_to_text(r"\frac{V}{\mathrm{km/h}}"), "(V)/(km/h)")
        self.assertEqual(_markup(_latex_to_text(r"\frac{\frac{1}{2}}{3}")), "(½)/(3)")
        self.assertEqual(
            _markup(_latex_to_text(r"\mathrm { m ^ { 3 } / h }")),
            f"m{_SCRIPT_GAP_105}<super>3</super>/h",
        )


class MarkupNormalisationTests(unittest.TestCase):

    def setUp(self) -> None:
        """显式声明希腊字形族（GEN-122），用例不依赖执行顺序。"""
        from leleby_ssir import pdf_renderer as _renderer

        previous = (_renderer._GREEK_FONT, _renderer._GREEK_ITALIC_FONT)
        _renderer._GREEK_FONT, _renderer._GREEK_ITALIC_FONT = "LiberationSerif", "LiberationSerif-Italic"
        self.addCleanup(setattr, _renderer, "_GREEK_FONT", previous[0])
        self.addCleanup(setattr, _renderer, "_GREEK_ITALIC_FONT", previous[1])
        # 角标字隙（GEN-140）：字面清空 → 只留固定字隙，断言不随执行顺序变化。
        _pin_math_faces(self)

    def test_markup_flattens_inline_math(self):
        text = "式中： $K _ { \\mathrm { ~ T ~ } }$ 堵转转矩灵敏度，单位为牛米每安培 $( \\mathrm { N } \\cdot \\mathrm { m } / \\mathrm { A } )$"
        out = _markup(text)
        self.assertNotIn("mathrm", out)
        self.assertNotIn("$", out)
        self.assertIn(f"<i>K</i>{_SCRIPT_GAP_105}<sub>T</sub>", out)   # K 是量符号 → 斜体（GEN-116）+ 角标字隙（GEN-140）
        self.assertIn("N·m/A", out)

    def test_markup_normalises_untitled_clause_number_spacing(self):
        # reportlab 把所有空白（含 U+3000）折叠为窄空格，无法表达“编号后空
        # 一个汉字”——_markup 输出白字 GAP（escape 后为白色“中”字形，视觉
        # 恰好 1em 不可见间隙；2026-09-03 与 CSM-OCR-003 术语间隔同款）。
        out = _markup("5.3.2泵抽送重要危险需降温冷却用水。")
        self.assertIn("5.3.2<font color=\"white\">中</font>泵抽送", out)
        out2 = _markup("5.3.1 泵应选用与介质适宜的轴封。")
        self.assertIn("5.3.1<font color=\"white\">中</font>泵应选用", out2)
        out3 = _markup("B.1.3.1抽样")
        self.assertIn("B.1.3.1<font color=\"white\">中</font>抽样", out3)

    def test_markup_collapses_ocr_whitespace_and_joins_digit_groups(self):
        out = _markup("额定电压为28.8 V、   32.4 V、36 V 和 48 V")
        self.assertNotIn("    ", out)
        out2 = _markup("800 W、2 000 W、2 200 W和 2 400 W")
        self.assertIn("2000", out2)
        self.assertIn("2200", out2)

    def test_markup_uses_fixed_quarter_han_gap_between_number_and_unit(self):
        # GBT-B12：单位符号前空四分之一汉字间隙。用按 1/4 字号绘制的白字实现——
        # 推进宽度恒为 1/4 汉字，且非空格字节，两端对齐不会把它拉宽。
        out = _markup("额定频率为50 Hz。")
        self.assertIn('50<font size="2.625" color="white">中</font>Hz', out)
        self.assertNotIn("\u00A0", out)

    def test_markup_formula_variable_item_gap(self) -> None:
        # GBT-X06（GB/T 1.1-2020 9.9.3、10.4.3；CSM-OCR-018）：公式变量解释项
        # 「变量——解释」中，变量与破折号之间、破折号与解释之间各空四分之一汉字；
        # 用固定字隙哨兵（白字），不是空格——两端对齐拉伸不到它。
        gap = '<font size="2.625" color="white">中</font>'
        self.assertEqual(_markup(r"$\Delta t$——绕组温升，单位为开尔文(K)；"), f'<font name="LiberationSerif">Δ</font><i>t</i>{gap}——{gap}绕组温升，单位为开尔文(K)；')
        self.assertEqual(_markup(r"$R _ { 2 }$——试验结束时的绕组电阻，单位为欧姆(Ω)；"),
                         f"<i>R</i>{_SCRIPT_GAP_105}<sub>2</sub>{gap}——{gap}试验结束时的绕组电阻，单位为欧姆(<font name=\"LiberationSerif\">Ω</font>)；")
        self.assertEqual(_markup("k ——常数，对铜绕组为234.5；"), f"k{gap}——{gap}常数，对铜绕组为234.5；")
        # 列项 marker「——」不是变量解释项；无破折号的正文段落不受影响。
        self.assertEqual(_markup("——增加了第3章“术语和定义”；"), "——增加了第3章“术语和定义”；")
        self.assertEqual(_markup("GB/T 1.1—2020 规定如下："), "GB/T 1.1—2020 规定如下：")

    def test_markup_unit_gap_unifies_tight_and_spaced_units(self) -> None:
        # GBT-B12 执行侧（GB/T 1.1-2020 10.4.6）：单位符号前空四分之一汉字间隙。
        # 紧贴（OCR/源文 "210mm"）与已有空格（"50 Hz"）统一成同一种固定字隙，消除同
        # 文档不一致；% 前不留间隙（GB/T 15835-2011 示例 "34.05%"、"63%~68%"）。
        gap = '<font size="2.625" color="white">中</font>'
        self.assertEqual(_markup("外形尺寸为210mm×150mm"), f"外形尺寸为210{gap}mm×150{gap}mm")
        self.assertEqual(_markup("0.2℃时测得"), f"0.2{gap}℃时测得")
        self.assertEqual(_markup("电压为85K与15N的试样"), f"电压为85{gap}K与15{gap}N的试样")
        self.assertEqual(_markup("持续2h 30min"), f"持续2{gap}h 30{gap}min")
        self.assertEqual(_markup("偏差应在±10 %范围内"), "偏差应在±10%范围内")
        self.assertEqual(_markup("34.05% 63%~68%"), "34.05% 63%~68%")
        self.assertEqual(_markup("525 μm"), f'525{gap}<font name="LiberationSerif">μ</font>m')
        # 分表/分图代号（GB/T 1.1 9.8.1.3 引用的 “表2a”）不是单位，不插间隙；
        # 列项引用（“4.2b)”）按排版惯例留间隙；表/图前的量值不受排除影响。
        self.assertEqual(
            _markup("将“表2”分为“表2a”和“表2b”"),
            "将“表2”分为“表2a”和“表2b”",
        )
        self.assertEqual(_markup("见4.2b)的规定"), f"见4.2{gap}b)的规定")
        self.assertEqual(_markup("在5℃～40℃下"), f"在5{gap}℃～40{gap}℃下")
        # 表/图编号后紧跟的字母是标识符或公式变量，不是单位：分表代号 "表2a"、"图2b"、
        # 附录表编号 "表A.1" 后的公式变量（表题 "表A.1C_p 等级评定" 型）都不插间隙。
        self.assertEqual(_markup("见表A.1C_p 等级评定及处理原则"), "见表A.1C_p 等级评定及处理原则")
        self.assertEqual(_markup("图2b所示"), "图2b所示")
        self.assertEqual(_markup("见附录表B.1a"), "见附录表B.1a")
        # 幂次数量值（"10³ m"）与紧贴形态（"10³m"）同样归一为固定字隙；上下标内的记号
        # （"D_{1max}"）不是量值-单位，不插字隙。
        self.assertEqual(_markup("l = 2.5×10<sup>3</sup> m"), f"l = 2.5×10{_SCRIPT_GAP_105}<super>3</super>{gap}m")
        self.assertEqual(_markup("10<sup>3</sup>m"), f"10{_SCRIPT_GAP_105}<super>3</super>{gap}m")
        self.assertEqual(_markup(_latex_to_text(r"$D _ { \mathrm { 1 m a x } }$")), f"<i>D</i>{_SCRIPT_GAP_105}<sub>1max</sub>")
        # 间隙随容器字号（四分之一汉字，非固定点数）。
        self.assertEqual(_markup("1000 m", em_size=9), '1000<font size="2.25" color="white">中</font>m')


class FormulaNumberLineTests(unittest.TestCase):
    """GBT-X06（GB/T 1.1-2020 9.9.2、10.4.3）：公式编号右端对齐、与公式以“……”连接。

    以真实 PDF 的字符/图形坐标断言（GEN-090/091 同口径，非视觉比对）：公式另行
    居中、公式与引导线之间恰为两个汉字间隔、引导线填满到右端编号、编号右缘贴
    版心右缘；公式过宽时先收到「留得下引导线」的宽度（只缩小不放大）。
    """

    FONT_ASSET = Path(__file__).resolve().parents[1] / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"

    def _render(self, image_width: int, frame_width: float = 441.5):
        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        from PIL import Image as PILImage
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Image, SimpleDocTemplate

        from leleby_ssir.pdf_renderer import _FormulaLeaderLine

        if not self.FONT_ASSET.is_file():
            self.skipTest("body font asset missing")
        name = "FormulaLineBody"
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(self.FONT_ASSET)))
        directory = tempfile.mkdtemp()
        image_path = Path(directory) / "formula.png"
        PILImage.new("RGB", (image_width, 40), (255, 255, 255)).save(image_path)
        image = Image(str(image_path))
        line = _FormulaLeaderLine(image, "(1)", name, 10.5)
        target = Path(directory) / "formula.pdf"
        page_size = (frame_width + 12, 200)  # Frame 默认 6pt 内衬 → 可用宽 = frame_width
        SimpleDocTemplate(str(target), pagesize=page_size, leftMargin=0, rightMargin=0,
                          topMargin=0, bottomMargin=0).build([line])
        document = pymupdf.open(str(target))
        page = document[0]
        chars: list[tuple[str, float, float]] = []
        for block in page.get_text("rawdict")["blocks"]:
            for line_ in block.get("lines", []):
                for span in line_["spans"]:
                    for char in span["chars"]:
                        chars.append((char["c"], char["bbox"][0], char["bbox"][2]))
        images = page.get_image_info()
        return line, chars, images

    def test_number_is_right_aligned_and_leader_fills_the_gap(self) -> None:
        line, chars, images = self._render(image_width=220)
        dots = [c for c in chars if c[0] == "…"]
        number = [c for c in chars if c[0] in "()1"]
        self.assertEqual(len(images), 1)
        self.assertTrue(dots, f"leader dots missing: {[c[0] for c in chars]!r}")
        self.assertTrue(number)
        image_box = images[0]["bbox"]
        # 公式居中：图像中心 ≈ 版心中心。
        self.assertAlmostEqual((image_box[0] + image_box[2]) / 2, 6 + line.avail / 2, places=1)
        # 公式与引导线之间恰为两个汉字间隔（2em = 21pt）。
        self.assertAlmostEqual(dots[0][1] - image_box[2], 2 * 10.5, places=1)
        # 引导线紧跟右端编号：省略号最后一个字形与「(」之间的余量不足一个字位。
        self.assertLessEqual(number[0][1] - dots[-1][2], 10.5)
        # 编号右缘贴版心右缘（「)」字形墨迹可略超推进宽，容差 1.5pt）。
        self.assertAlmostEqual(number[-1][2], 6 + line.avail, delta=1.5)

    def test_wide_formula_is_shrunk_to_leave_room_for_the_leader(self) -> None:
        # 443px 宽的 MinerU 公式裁剪图（GB_T_5171.1-2014 式(1) 实测）远超版心：
        # 收窄到「留得下 2 汉字间隔 + 引导线 + 编号」，只缩小不放大。
        line, chars, images = self._render(image_width=600)
        dots = [c for c in chars if c[0] == "…"]
        number = [c for c in chars if c[0] in "()1"]
        self.assertTrue(dots and number)
        self.assertGreaterEqual(len(dots), 4, "至少留出四个汉字位的引导线")
        image_box = images[0]["bbox"]
        self.assertLess(image_box[2] - image_box[0], 600)
        self.assertLessEqual(image_box[2], number[0][1] - 2 * 10.5)
        self.assertAlmostEqual(number[-1][2], 6 + line.avail, delta=1.5)


def _formula_story(latex: str, body_size: float, content_width: float = _BODY_MEASURE, font_name: str = "Helvetica"):
    """把单个公式内容元素过一遍渲染端，返回 (story, report)（公式尺寸/回退类夹具共用）。"""
    import tempfile

    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

    from leleby_ssir.pdf_renderer import PDFRenderReport, _append_content_sequence

    asset_dir = Path(tempfile.mkdtemp())
    styles = {}
    for name in ("example-label", "example-title", "example-content", "body", "body-flush",
                 "caption", "table-unit", "table", "table-body", "note", "list", "list-sub",
                 "formula", "section", "subclause", "clause", "front", "side-cell"):
        styles[name] = ParagraphStyle(name, fontName=font_name, fontSize=body_size if name == "body" else 10)
    report = PDFRenderReport(input_file="t.pdf", output_file="t.render.pdf", profile_file="", profile_id="", font_file="")
    story: list = []
    _append_content_sequence(
        story, [{"presentationType": "formula", "formulaRef": "f1", "sortOrder": 0}],
        registries={"tables": {}, "figures": {}, "formulas": {"f1": {"id": "f1", "latex": latex}}},
        styles=styles, font="Helvetica", report=report, asset_dir=asset_dir,
        colors=colors, Table=Table, TableStyle=TableStyle, Paragraph=Paragraph,
        Spacer=Spacer, Image=Image, content_width=content_width,
    )
    return story, report


class FormulaImageSizeTests(unittest.TestCase):
    """GEN-105：生成的公式图按正文字号显示，不把像素当点。

    背景（GB/T 5171.1-2014 式(1)/式(2)）：`_formula_image` 以 180dpi 光栅化、字号
    14pt（图上 em = 35px），而 reportlab 的 `Image` 默认把 1px 当 1pt → 公式被整体
    放大 2.5 倍，再被宽度上限按内容比例压缩：同一文档内公式字号随长度漂移
    （实测式(1) 1.66×、式(2) 2.36× 正文字号）且被拉伸到整个版心 455pt，而源版面
    只有 313.6 / 281.1pt。
    """

    def test_scale_is_unit_conversion_times_target_ratio(self) -> None:
        # (72/180) × (10.5/14) = 0.3：正文字号 10.5pt 时生成图按 30% 像素宽显示。
        self.assertAlmostEqual(_formula_image_scale(10.5), (72.0 / _FORMULA_IMAGE_DPI) * (10.5 / _FORMULA_IMAGE_EM_PT), places=9)
        self.assertAlmostEqual(_formula_image_scale(10.5), 0.3, places=9)
        # 显示尺寸跟随 profile 正文字号（不是写死的常数）：字号 ×4/3 → 尺寸 ×4/3。
        self.assertAlmostEqual(_formula_image_scale(14.0), 0.4, places=9)

    def _formula_flowable(self, latex: str, body_size: float, content_width: float = _BODY_MEASURE):
        story, _report = _formula_story(latex, body_size, content_width)
        self.assertEqual(len(story), 1, f"期望单个流对象，实际 {[type(s).__name__ for s in story]}")
        return story[0]

    def test_generated_formula_is_drawn_at_the_body_size(self) -> None:
        latex = r"\Delta t = \frac {R_{2} - R_{1}}{R _{1}} (k + t_{1}) - (t_{2} - t_{1})"
        flowable = self._formula_flowable(latex, body_size=10.5)
        # px × scale：生成图的 em 恰为正文字号 10.5pt（修前是 35px × 0.497 上限缩放）。
        self.assertAlmostEqual(flowable.drawWidth, flowable.imageWidth * _formula_image_scale(10.5), places=6)
        self.assertAlmostEqual(flowable.drawHeight, flowable.imageHeight * _formula_image_scale(10.5), places=6)
        # 不再被拉伸到整个版心（源版面 313.6pt；旧实现恒为 455.0pt）。
        self.assertLess(flowable.drawWidth, _BODY_MEASURE * 0.8)

    def test_formula_size_follows_the_body_font_size(self) -> None:
        latex = r"\Delta t = \frac {R_{2} - R_{1}}{R _{1}} (k + t_{1}) - (t_{2} - t_{1})"
        small = self._formula_flowable(latex, body_size=10.5)
        large = self._formula_flowable(latex, body_size=14.0)
        self.assertAlmostEqual(large.drawWidth / small.drawWidth, 14.0 / 10.5, places=3)


class FormulaDisplayStyleTests(unittest.TestCase):
    """GEN-109：块级公式按**显示样式**排版——最外层分数为 `\\dfrac`。

    背景（2026-09-16 用户报告「9.9.3.1 的几个公式（如示例1、示例5）渲染后看起来仍然略显
    小」）：canonical 的 `ssir:formula` 是 LaTeX 的 display math（`$$…$$`），而 MathText 的
    `$…$` 等价于行内（text style）——`\\frac` 的分子/分母被降为脚标号（实测分数堆高只有
    12.9pt，而源文同一公式 17.0pt 且分子分母与左侧字母同大；示例5 的 `\\sqrt{\\frac{…}{…}}`
    被压得更扁）。修法不是放大字号（那会把字母本身放大到源文的 2 倍），而是按 TeX 的样式
    规则把**最外层**的 `\\frac` 写成 `\\dfrac`：分数参数内与上/下标内保持原样式。
    """

    def test_outermost_fraction_is_promoted(self) -> None:
        self.assertEqual(_display_style_latex(r"v = \frac {l}{t}"), r"v = \dfrac {l}{t}")
        self.assertEqual(
            _display_style_latex(r"K = \frac{T_{Lmax} - T_{Lmin}}{T_{Lmax} + T_{Lmin}} × 100%"),
            r"K = \dfrac{T_{Lmax} - T_{Lmin}}{T_{Lmax} + T_{Lmin}} × 100%",
        )

    def test_fraction_inside_a_radical_is_promoted(self) -> None:
        # 示例5：`\sqrt{…}` 的花括号只作分组、不改变样式 → 里面的分数仍是最外层。
        self.assertEqual(
            _display_style_latex(r"t_{i} =\sqrt {\frac {S_{ME,i}}{S_{MR, i}}}"),
            r"t_{i} =\sqrt {\dfrac {S_{ME,i}}{S_{MR, i}}}",
        )

    def test_nested_fraction_and_script_fraction_keep_their_style(self) -> None:
        self.assertEqual(_display_style_latex(r"\frac{a}{\frac{b}{c}}"), r"\dfrac{a}{\frac{b}{c}}")
        self.assertEqual(_display_style_latex(r"x^{\frac{a}{b}}"), r"x^{\frac{a}{b}}")
        # `\tfrac` 是作者显式要求的小分数，`\dfrac` 已是显示样式：都不动。
        self.assertEqual(_display_style_latex(r"\tfrac{a}{b}"), r"\tfrac{a}{b}")
        self.assertEqual(_display_style_latex(r"\dfrac{a}{b}"), r"\dfrac{a}{b}")

    def test_formula_without_a_fraction_is_untouched(self) -> None:
        latex = r"dim (E) =  dim (F) ×  dim (l)"
        self.assertEqual(_display_style_latex(latex), latex)

    def _display_vs_inline(self, latex: str) -> tuple[Any, Any]:
        """同一公式在「显示样式」与「行内样式（把提升退回）」下的渲染流对象。"""
        import leleby_ssir.pdf_renderer as module

        display = self._flowable(latex)
        saved = module._display_style_latex
        try:
            module._display_style_latex = lambda expression: expression
            inline = self._flowable(latex)
        finally:
            module._display_style_latex = saved
        return display, inline

    def _flowable(self, latex: str):
        story, _report = _formula_story(latex, body_size=10.5)
        self.assertEqual(len(story), 1, f"期望单个流对象，实际 {[type(s).__name__ for s in story]}")
        return story[0]

    def test_display_fraction_is_taller_without_changing_the_font_size(self) -> None:
        display, inline = self._display_vs_inline(r"v = \frac {l}{t}")
        # 显示样式只在垂直方向长高（分子分母恢复字号），宽度几乎不变。
        self.assertGreater(display.drawHeight, inline.drawHeight * 1.5)
        self.assertLess(display.drawWidth, inline.drawWidth * 1.2)
        # em 不变：仍是正文字号（没有放大字号——「不要过分」）。
        self.assertAlmostEqual(display.drawWidth, display.imageWidth * _formula_image_scale(10.5), places=6)
        self.assertAlmostEqual(inline.drawHeight, inline.imageHeight * _formula_image_scale(10.5), places=6)

    def test_radical_fraction_also_grows(self) -> None:
        display, inline = self._display_vs_inline(r"t_{i} =\sqrt {\frac {S_{ME,i}}{S_{MR, i}}}")
        self.assertGreater(display.drawHeight, inline.drawHeight * 1.3)
        self.assertGreater(display.drawWidth, inline.drawWidth)
        # 宽度上限仍然生效（容器宽/140pt 高，只缩小不放大）。
        self.assertLessEqual(display.drawHeight, 140)

    def test_cache_key_follows_the_promoted_expression(self) -> None:
        # 缓存文件按提升后的表达式取哈希：否则旧的行内样式图会一直被命中，
        # 修复对已渲染过的文档不生效（见 `_formula_image` 的 docstring）。
        import hashlib
        import tempfile

        from leleby_ssir.pdf_renderer import _formula_image

        latex = r"v = \frac {l}{t}"
        directory = Path(tempfile.mkdtemp())
        first = _formula_image(latex, directory)
        self.assertIsNotNone(first)
        self.assertEqual(first.name, hashlib.sha256(r"v = \dfrac {l}{t}".encode("utf-8")).hexdigest() + ".png")
        self.assertEqual(_formula_image(latex, directory), first)  # 幂等：第二次命中缓存


class CjkFormulaTextFallbackTests(unittest.TestCase):
    """GEN-106：含汉字的公式不得交给 MathText（数学字体无汉字字形 → 假字形方框）。

    背景（GB_3100-2026 8.2.3）：源 PDF 的中文单位行「米/秒；米·秒⁻¹；＋ 米/秒 分数」被
    MinerU 判成 **text 块**（8.2.2 的英文对应行是 interline_equation 并带裁剪图），
    canonical 里这一行是含汉字的 LaTeX 公式块且**没有图资产** → MathText 把「米/秒」印成
    一串方框。规则：无可用图资产且含汉字时按文本拍平渲染；有资产仍优先资产（GEN-102）。
    """

    def test_cjk_detection(self) -> None:
        self.assertTrue(_latex_has_cjk(r"米/秒;  米·秒⁻¹; \frac {米}{秒}"))
        self.assertTrue(_latex_has_cjk(r"\mathrm{密度} = \frac {\mathrm{质量}}{\mathrm{体积}}"))
        self.assertTrue(_latex_has_cjk("（米）"))  # 全角标点同样没有字形
        self.assertFalse(_latex_has_cjk(r"\mathrm{m/s;m} \cdot \mathrm{s} ^ {- 1}; \quad \frac {m}{s}"))
        self.assertFalse(_latex_has_cjk(r"J = 7.98 P_{N}^{1.15} /n_{N}^{2}"))
        self.assertFalse(_latex_has_cjk(""))

    def test_cjk_formula_without_asset_is_typeset_as_text(self) -> None:
        from reportlab.platypus import Image, Paragraph

        latex = r"米/秒;  米·秒⁻¹; \frac {米}{秒}"
        story, report = _formula_story(latex, body_size=10.5)
        self.assertEqual(len(story), 1)
        flowable = story[0]
        # 不是 MathText 图（旧行为），而是正常文本：汉字由宋体印出，分数按既有约定拍平。
        self.assertIsInstance(flowable, Paragraph)
        self.assertNotIsInstance(flowable, Image)
        self.assertIn("米/秒", flowable.text)
        self.assertIn("(米)/(秒)", flowable.text)
        self.assertTrue(any("CJK" in w for w in report.warnings), report.warnings)

    def test_ascii_formula_still_uses_a_generated_image(self) -> None:
        from reportlab.platypus import Image

        story, report = _formula_story(r"\mathrm{m/s;m} \cdot \mathrm{s} ^ {- 1}; \quad \frac {m}{s}", body_size=10.5)
        self.assertIsInstance(story[0], Image)
        self.assertEqual(report.warnings, [])

    def test_cjk_formula_text_reaches_the_pdf_text_layer(self) -> None:
        # 真 PDF 断言：汉字必须作为**文本**出现在文本层（MathText 图里没有任何字符可取）。
        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        import tempfile

        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import SimpleDocTemplate

        font_asset = Path(__file__).resolve().parents[1] / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font_asset.is_file():
            self.skipTest("body font asset missing")
        name = "CjkFormulaBody"
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(font_asset)))
        # 段落字体必须在**构造前**给定（reportlab 在构造时按 style 拆字/定字体）。
        story, _report = _formula_story(r"米/秒;  米·秒⁻¹; \frac {米}{秒}", body_size=10.5, font_name=name)
        target = Path(tempfile.mkdtemp()) / "cjk.pdf"
        SimpleDocTemplate(str(target), pagesize=(456, 200), leftMargin=0, rightMargin=0,
                          topMargin=0, bottomMargin=0).build([story[0]])
        page = pymupdf.open(str(target))[0]
        text = page.get_text()
        self.assertIn("米/秒", text)
        spans = [s for b in page.get_text("dict")["blocks"] if b.get("type") == 0
                 for l in b["lines"] for s in l["spans"]]
        # reportlab 内嵌的是字体真实名（NotoSerifCJKsc-Regular），不是注册别名；
        # 关键是汉字 span 用的是 CJK 字体、而非 Helvetica 回退。
        cjk_spans = [s for s in spans if "米" in s["text"] or "秒" in s["text"]]
        self.assertTrue(cjk_spans)
        self.assertTrue(all("Helvetica" not in s["font"] for s in cjk_spans), [s["font"] for s in cjk_spans])


class VerbatimBlockRenderingTests(unittest.TestCase):
    """GEN-107：原样块（docs/07 §6.10）逐字渲染——保留换行与缩进。

    背景（GB_3100-2026 4.1）：canonical 里「国际单位制」树写成 6 行纯文本，但
    `_markup` 的软换行规则（CSM §3.3，语料 31 个多行段落依赖它）把每行拼成一段，
    渲染稿里树被糊成一行。原样块（`ssir:unknown` + 围栏代码块）必须逐字保留；
    渲染端此前没有按行切分的处理。
    """

    TREE = "国际单位制\n  ├─ SI 单位\n  │    ├─ SI 基本单位（见表 1）\n  └─ SI 单位的倍数单位和分数单位"

    def test_verbatim_markup_keeps_newlines_and_indent(self) -> None:
        from leleby_ssir.pdf_renderer import _fixed_gap, _verbatim_gap_pt, _verbatim_markup

        self.assertEqual(_verbatim_markup("a b", 10.5), "a b")  # 行内单空格原样（仍可折行）
        self.assertEqual(_verbatim_markup("", 10.5), "")
        out = _verbatim_markup(self.TREE, 10.5)
        self.assertEqual(out.count("\x00BR\x00"), 3)  # 4 行 → 3 个硬换行哨兵
        self.assertIn(_fixed_gap(5.25) + "├─ SI 单位", out)  # 行首 2 空格 = 0.5em
        self.assertIn(_fixed_gap(5.25) + "│" + _fixed_gap(10.5) + "├─", out)  # 行内 ≥2 空格 = 1em
        # 字体实测：U+0020 = 0.256em、框线字 ├│└─ = 1.000em → 4 个半角空格 = 1 个全角位。
        self.assertAlmostEqual(_verbatim_gap_pt("    ", 10.5), 10.5, places=6)
        self.assertAlmostEqual(_verbatim_gap_pt("\t", 10.5), 10.5, places=6)

    def test_verbatim_block_lines_and_columns_in_a_real_pdf(self) -> None:
        records = self._render_block("other")
        self.assertEqual(len(records), 4, records)  # 4 行逐行保留（修前：1 行）
        texts = [self._strip_sentinels(text) for text, _marks in records]
        self.assertEqual(texts[0], "国际单位制")
        self.assertIn("SI 基本单位（见表 1）", texts[2])
        # 第 2/4 行的分支字符（├ / └）应同列；第 3 行的竖线与该列对齐；下一级分支右移 2em。
        self.assertEqual(records[1][1][0][0], "├")
        self.assertEqual(records[3][1][0][0], "└")
        self.assertAlmostEqual(records[1][1][0][1], records[3][1][0][1], places=2)
        level2 = dict(records[2][1])
        self.assertAlmostEqual(level2["│"], records[1][1][0][1], places=2)
        self.assertAlmostEqual(level2["├"] - records[1][1][0][1], 2 * 10.5, places=1)

    def test_plain_paragraph_still_collapses_soft_wraps(self) -> None:
        # 对照：同一段文本作为普通段落（语料 31 个多行段落的形态）必须继续归一为空格、
        # 排成一行，否则 MinerU 逐行折行的正文会全部多出硬换行。
        records = self._render_block("paragraph")
        self.assertEqual(len(records), 1, records)
        self.assertEqual(len(records[0][1]), 7, records)  # 7 个框线字符全挤在这一行
        self.assertIn("国际单位制", records[0][0])

    @staticmethod
    def _strip_sentinels(text: str) -> str:
        """去掉字隙哨兵字形（不可见的白色「中」，见 _fixed_gap）便于比较文本。"""
        return text.replace("中", "").strip()

    def _render_block(self, presentation_type: str):
        """把一个内容元素过真实渲染流程并导出（文本, 框线字符 x 列表）。"""
        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        import tempfile

        import yaml
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        from leleby_ssir.pdf_renderer import PDFRenderReport, _append_content_sequence, _styles

        root = Path(__file__).resolve().parents[1]
        font_asset = root / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        profile_asset = root / "config" / "rendering" / "GB_T_1.1-2020.yaml"
        if not font_asset.is_file() or not profile_asset.is_file():
            self.skipTest("font/profile asset missing")
        name = "VerbatimBody"
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(font_asset)))
        profile = yaml.safe_load(profile_asset.read_text(encoding="utf-8"))
        # 真实风格表（含 GEN-107 新增的 verbatim 样式），字号随 profile 正文 10.5pt。
        styles = _styles(getSampleStyleSheet(), profile, name, name, TA_CENTER, TA_JUSTIFY, TA_LEFT)
        report = PDFRenderReport(input_file="t.pdf", output_file="t.render.pdf", profile_file="", profile_id="", font_file="")
        content = {"presentationType": presentation_type, "sortOrder": 0, "textContent": self.TREE}
        if presentation_type == "other":
            content["unknownRef"] = "u1"
        story: list = []
        _append_content_sequence(
            story, [content],
            registries={"tables": {}, "figures": {}, "formulas": {},
                        "unknownContents": {"u1": {"id": "u1", "rawContent": self.TREE, "typeHint": "layout-fragment"}}},
            styles=styles, font=name, report=report, asset_dir=Path(tempfile.mkdtemp()),
            colors=__import__("reportlab.lib.colors", fromlist=["colors"]), Table=Table, TableStyle=TableStyle,
            Paragraph=Paragraph, Spacer=Spacer, Image=Image, content_width=_BODY_MEASURE,
        )
        target = Path(tempfile.mkdtemp()) / "verbatim.pdf"
        SimpleDocTemplate(str(target), pagesize=(600, 400), leftMargin=40, rightMargin=40,
                          topMargin=40, bottomMargin=40).build(story)
        page = pymupdf.open(str(target))[0]
        records = []
        for block in page.get_text("rawdict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                chars = [c for span in line["spans"] for c in span["chars"]]
                text = "".join(c["c"] for c in chars)
                if not text.strip():
                    continue
                marks = [(c["c"], round(c["bbox"][0], 2)) for c in chars if c["c"] in "├└│─"]
                records.append((text, marks))
        return records


class UnitGapRenderingTests(unittest.TestCase):
    """GBT-B12 数值-单位间隙：渲染实测恒为 1/4 汉字宽，两端对齐不拉伸。

    以 PDF 内部对象（字形坐标/字号）验证，不做视觉比对：reportlab 的两端对齐通过
    PDF 字间距（Tw）实现，只作用于空格字节，曾把 U+00A0 间隙拉到 1.0–1.6 个汉字
    宽；本用例强制长行换行+两端对齐，断言每个数值-单位间隙仍恰为 1/4 汉字。
    """

    FONT_ASSET = Path(__file__).resolve().parents[1] / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"

    def _measure(self, em: float) -> tuple[list[float], list[float]]:
        try:
            import pymupdf
        except ImportError:  # pragma: no cover - 环境缺 pymupdf 时跳过
            self.skipTest("pymupdf unavailable")
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate

        if not self.FONT_ASSET.is_file():
            self.skipTest("body font asset missing")
        name = "UnitGapRenderingBody"
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(self.FONT_ASSET)))
        style = ParagraphStyle("unit-gap", fontName=name, fontSize=em, leading=em * 1.7, alignment=4, wordWrap="CJK")
        sentence = "电动机温升限值的修正按GB755的规定，本部分适用于折算至1500r/min时最大连续额定功率不超过1.1kW的电动机。"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "unit-gap.pdf"
            SimpleDocTemplate(str(target)).build([Paragraph(_markup(sentence * 3, em_size=em), style)])
            document = pymupdf.open(str(target))
            page = document[0]
        chars: list[tuple[str, float, float]] = []
        lines: list[list[tuple[str, float, float]]] = []
        for block in page.get_text("rawdict")["blocks"]:
            for line in block.get("lines", []):
                current: list[tuple[str, float, float]] = []
                for span in line["spans"]:
                    for char in span["chars"]:
                        current.append((char["c"], char["origin"][0], span["size"]))
                if current:
                    lines.append(current)
                    chars.extend(current)
        digit_width = {char: pdfmetrics.stringWidth(char, name, em) for char in "0123456789"}
        gaps, sizes = [], []
        for current in lines:  # 同一行内比较，跨行/跨页不算间隙
            for index in range(len(current) - 2):
                before, filler, after = current[index], current[index + 1], current[index + 2]
                if before[0].isdigit() and filler[0] == "中" and after[0] in "mkr":
                    gaps.append(after[1] - before[1] - digit_width[before[0]])
                    sizes.append(filler[2])
        return gaps, sizes

    def test_gap_is_quarter_han_and_immune_to_justification(self) -> None:
        em = 10.5
        gaps, sizes = self._measure(em)
        self.assertGreaterEqual(len(gaps), 3, "fixture must produce several number-unit gaps")
        for size in sizes:
            self.assertAlmostEqual(size, em / 4, places=2)
        for gap in gaps:
            self.assertAlmostEqual(gap, em / 4, places=2)

    def test_gap_follows_container_font_size(self) -> None:
        em = 9.0
        gaps, _ = self._measure(em)
        self.assertGreaterEqual(len(gaps), 3)
        for gap in gaps:
            self.assertAlmostEqual(gap, em / 4, places=2)


class ListMarkerGapTests(unittest.TestCase):
    """GBT-B04：列项 marker 与文字之间是固定字隙，文字起点与回行同位置。

    4.1.1 b) 条目曾比 a) 条目的 marker 后空隙宽得多：两者 canonical 相同（一个空格），
    但 b) 首行触发了 reportlab 的字间距（同行有旧实现数值-单位用的 U+00A0），整行空格
    被一起拉开。修因：marker 后改用「回行位 − marker 宽」的固定白字字隙，不再是空格。
    """

    FONT_ASSET = Path(__file__).resolve().parents[1] / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"

    def _style(self, em: float = 10.5):
        from reportlab.lib.styles import ParagraphStyle

        return ParagraphStyle(
            "list-gap", fontName="ListGapBody", fontSize=em, leading=em * 1.7,
            alignment=4, wordWrap="CJK", leftIndent=4 * em, firstLineIndent=-2 * em,
        )

    def _register(self) -> str:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        if not self.FONT_ASSET.is_file():
            self.skipTest("body font asset missing")
        name = "ListGapBody"
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(self.FONT_ASSET)))
        return name

    def test_gap_is_fixed_width_filler_not_space(self) -> None:
        from reportlab.pdfbase import pdfmetrics

        name = self._register()
        style = self._style()
        gap = _list_marker_gap(style, "b）", style.fontSize)
        markup = _markup(f"b）{gap}当运行地点的海拔")
        expected = 2 * style.fontSize - pdfmetrics.stringWidth("b）", name, style.fontSize)
        # marker 与文字之间只有固定字隙（白字），没有任何空格字符。
        self.assertIn(f'b）<font size="{expected:.3f}" color="white">中</font>当运行地点的海拔', markup)
        self.assertNotIn("b） ", markup)
        # marker 宽于目标位时不后推文字（三段破折号已超过两个汉字位）。
        from reportlab.pdfbase import pdfmetrics as metrics

        wide = metrics.stringWidth("———", name, style.fontSize)
        self.assertGreater(wide, 2 * style.fontSize)
        self.assertEqual(_list_marker_gap(style, "———", style.fontSize), "")

    def test_marker_text_gap_matches_wrapped_line(self) -> None:
        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        from reportlab.platypus import Paragraph, SimpleDocTemplate

        name = self._register()
        style = self._style()
        gap = _list_marker_gap(style, "b）", style.fontSize)
        # 源文残留的 U+00A0 正是旧实现触发整行字间距拉伸的字符，仍须保持固定字隙。
        item = "当运行地点的海拔超过1000\u00a0m或运行地点的环境空气温度随海拔升高而下降时，电动机温升限值的修正按GB 755的规定。"
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "list-gap.pdf"
            SimpleDocTemplate(str(target)).build([Paragraph(_markup(f"b）{gap}{item}"), style)])
            page = pymupdf.open(str(target))[0]
        lines = []
        for block in page.get_text("rawdict")["blocks"]:
            for line in block.get("lines", []):
                chars = [(char["c"], char["origin"][0]) for span in line["spans"] for char in span["chars"]]
                if chars:
                    lines.append(chars)
        self.assertGreaterEqual(len(lines), 2, "fixture must wrap into two lines")
        first, second = lines[0], lines[1]
        self.assertEqual([char[0] for char in first[:3]], ["b", "）", "中"], first[:3])
        text_start = first[3][1]  # 固定字隙之后的第一个正文字形
        self.assertAlmostEqual(text_start, second[0][1], delta=0.2)
        self.assertAlmostEqual(text_start - first[0][1], 2 * style.fontSize, delta=0.2)

    def test_second_level_gap_uses_two_han_not_four(self) -> None:
        """第二层次列项（10.2.2：marker 空四汉字、文字列第七个汉字位）字隙 = 2 汉字 − 宽。

        旧实现把「目标位」错取成 ``leftIndent + firstLineIndent``（= 4 汉字位）当字隙
        宽度，第二层次因此得到 4 汉字 − marker 宽 ≈ 26pt 的白字占位符：文字被推到第八个
        汉字位，行框被撑高到 26pt 并与相邻行框重叠（2026-09-11 用户报 7.5.1 示例1 a) 下的
        1)/2) 列项）。反证：旧公式的值比字隙大一个汉字位以上。
        """
        from reportlab.pdfbase import pdfmetrics

        name = self._register()
        style = self._style().clone("list-sub", leftIndent=6 * 10.5, firstLineIndent=-2 * 10.5)
        marker_width = pdfmetrics.stringWidth("1）", name, style.fontSize)
        gap = _list_marker_gap(style, "1）", style.fontSize)
        expected = 2 * style.fontSize - marker_width
        self.assertAlmostEqual(float(gap.removeprefix("\x00WSP").removesuffix("\x00")), expected, places=3)
        self.assertIn(f'<font size="{expected:.3f}" color="white">中</font>', _markup(f"1）{gap}左向(含左上、左下)"))
        # 旧公式（leftIndent + firstLineIndent − marker 宽）= 4 汉字 − marker 宽。
        old = style.leftIndent + style.firstLineIndent - marker_width
        self.assertGreater(old - expected, 10.0)  # ≈ 2 汉字位 21pt 与 marker 宽之差

    def test_level_deepest_items_share_text_column_without_boxes_overlapping(self) -> None:
        """7.5.1 示例1 形态：a) 下挂 1)/2) —— 文字列 6 汉字、行框不重叠（真实 PDF 内部对象）。

        用户可见症状（间距过大、行框重叠）只在真实排版里出现：字隙哨兵是白字，其**字号
        即字隙宽**，26pt 的占位字把该行行框撑到 26pt（正文 leading 18pt）→ 与相邻行重叠。
        """
        import pymupdf
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Paragraph, SimpleDocTemplate

        name = self._register()
        em = 10.5
        base = dict(fontName=name, fontSize=em, leading=em * 1.7, alignment=4, wordWrap="CJK")
        flush = ParagraphStyle("flush-test", **base, leftIndent=0, firstLineIndent=0)
        lvl1 = ParagraphStyle("lvl1-test", **base, leftIndent=4 * em, firstLineIndent=-2 * em)
        lvl2 = ParagraphStyle("lvl2-test", **base, leftIndent=6 * em, firstLineIndent=-2 * em)
        story = [
            Paragraph(_markup("导向要素中图形符号与箭头的位置关系需要符合下列规则。"), flush),
            Paragraph(_markup(f"a）{_list_marker_gap(lvl1, 'a）', em)}当导向信息元素横向排列，并且箭头指："), lvl1),
            Paragraph(_markup(f"1）{_list_marker_gap(lvl2, '1）', em)}左向(含左上、左下)，图形符号应位于右侧；"), lvl2),
            Paragraph(_markup(f"2）{_list_marker_gap(lvl2, '2）', em)}右向(含右上、右下)，图形符号应位于左侧；"), lvl2),
        ]
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "list-columns.pdf"
            SimpleDocTemplate(str(target)).build(story)
            page = pymupdf.open(str(target))[0]
        lines: list[tuple[list[tuple[str, float]], tuple[float, ...]]] = []
        for block in page.get_text("rawdict")["blocks"]:
            for line in block.get("lines", []):
                chars = [(char["c"], char["origin"][0]) for span in line["spans"] for char in span["chars"]]
                if chars:
                    lines.append((chars, line["bbox"]))
        self.assertEqual(len(lines), 4, [line[0][:3] for line in lines])
        origin = lines[0][0][0][1]  # 正文段首 x（版心左）
        # a) 项：marker 空两汉字起排，文字（白字字隙之后）落在第五个汉字位。
        self.assertAlmostEqual(lines[1][0][0][1] - origin, 2 * em, delta=0.3)
        self.assertAlmostEqual(lines[1][0][3][1] - origin, 4 * em, delta=0.3)
        # 1)/2) 项：marker 空四汉字起排，文字落在第七个汉字位（旧实现为第八个）。
        for index in (2, 3):
            chars = lines[index][0]
            self.assertEqual([char[0] for char in chars[:3]], [str(index - 1), "）", "中"], chars[:3])
            self.assertAlmostEqual(chars[0][1] - origin, 4 * em, delta=0.3)
            self.assertAlmostEqual(chars[3][1] - origin, 6 * em, delta=0.3)
        # 行框高度不超过 leading（白字占位符不再撑高行框），相邻行框不重叠。
        for index, (chars, bbox) in enumerate(lines):
            self.assertLessEqual(bbox[3] - bbox[1], em * 1.7 + 0.5, f"line {index} box inflated: {bbox}")
            if index:
                self.assertGreaterEqual(bbox[1], lines[index - 1][1][3] - 0.5, f"line {index} overlaps the previous one")


class UntitledClauseFlushTests(unittest.TestCase):
    """Bare paragraphs starting with a clause number render flush left."""

    def setUp(self) -> None:
        # 角标字隙（GEN-140）：字面清空 → 只留固定字隙，断言不随执行顺序变化。
        _pin_math_faces(self)

    def test_bare_clause_paragraphs_are_detected(self):
        self.assertEqual(_clause_leading_number("5.5.2承压零件应做静水压试验。"), "5.5.2")
        self.assertEqual(_clause_leading_number("5.3.1 泵应选用与介质适宜的轴封。"), "5.3.1")
        self.assertEqual(_clause_leading_number("B.1.3.1抽样"), "B.1.3.1")
        self.assertEqual(_clause_leading_number("A.2 试验应在 20 ℃ 下进行。"), "A.2")

    def test_latin_after_number_is_a_clause_head_only_when_the_structure_confirms_it(self):
        """编号后接拉丁字母：与「数值+单位」句同形，须由所在节点条号确认（GBT-B02）。

        2026-09-15（GB_3100-2026 4.2/4.3/6.1/8.2.5）：这四条正文以 "SI…" 起排，
        编号后不是汉字，此前被当作正文段落空两个汉字起排；源 PDF 与其余条号同列顶格。
        """
        # 结构确认：编号是所在节点条号的直接子条（4.2 在章 4 内、8.2.5 在 8.2 内）。
        self.assertEqual(_clause_leading_number("4.2 SI 是采用如下常量的单位制：", "4"), "4.2")
        self.assertEqual(_clause_leading_number("4.3 SI单位是…", "4"), "4.3")
        self.assertEqual(_clause_leading_number("6.1 SI 单位的十进倍数和分数单位…", "6"), "6.1")
        self.assertEqual(_clause_leading_number("8.2.5 SI词头符号一律用正体字母，…", "8.2"), "8.2.5")
        # 无结构上下文 → 保守退回正文段（既有行为，先前的 3.2 kW 负例仍成立）。
        self.assertIsNone(_clause_leading_number("4.2 SI 是采用如下常量的单位制："))
        self.assertIsNone(_clause_leading_number("3.2 kW 的电机应可靠工作。", "4"))
        self.assertIsNone(_clause_leading_number("3.2 kW 的电机应可靠工作。"))
        # 父条号不匹配（正文段在自己的章外）→ 仍是正文段。
        self.assertIsNone(_clause_leading_number("4.2 SI 是采用如下常量的单位制：", "5"))
        # 已知局限：更深的裸条（4.2.1 直接挂在章 4 下）无结构确认 → 保持正文段。
        self.assertIsNone(_clause_leading_number("4.2.1 SI 单位的符号…", "4"))
        # 汉字/括号形态不受影响（结构化上下文可有可无）。
        self.assertEqual(_clause_leading_number("5.3.1 泵应选用与介质适宜的轴封。", "5"), "5.3.1")

    def test_clause_head_gap_writes_one_han_gap_only_for_the_latin_form(self):
        """编号后接拉丁字母的条首由调用方补 1 汉字字隙；其余形态原样（GBT-B02）。"""
        self.assertEqual(
            _clause_head_gap("4.2 SI 是采用如下常量的单位制：", "4.2"),
            "4.2\x00GAP\x00SI 是采用如下常量的单位制：",
        )
        self.assertEqual(_clause_head_gap("8.2.5\u3000SI词头符号…", "8.2.5"), "8.2.5\x00GAP\x00SI词头符号…")
        # 编号后是汉字 → 归 _markup 的共享正则管，此处不得二次写入字隙。
        self.assertEqual(_clause_head_gap("4.1 国际单位制（SI）…", "4.1"), "4.1 国际单位制（SI）…")
        # 编号不匹配（别的段落的编号）→ 不动。
        self.assertEqual(_clause_head_gap("4.3 SI单位是…", "4.2"), "4.3 SI单位是…")

    def test_node_clause_number_reads_the_structure_node(self):
        self.assertEqual(_node_clause_number({"number": "4", "title": "国际单位制的构成"}), "4")
        self.assertEqual(_node_clause_number({"number": "8.2", "title": "单位符号"}), "8.2")
        self.assertEqual(_node_clause_number({"number": "A.1", "title": "秒"}), "A.1")
        self.assertEqual(_node_clause_number({"title": "4 国际单位制的构成"}), "4")  # 编号在标题里
        self.assertIsNone(_node_clause_number({"title": "前言"}))
        self.assertIsNone(_node_clause_number({}))

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
        self.assertEqual(_list_marker("•"), "●")
        self.assertEqual(_list_marker("a)"), "a)")
        self.assertEqual(_list_marker("1)"), "1)")
        self.assertEqual(_list_marker("·"), "·")
        self.assertEqual(_list_marker("●"), "●")

    def test_table_cell_superscripts_generic_tokens(self) -> None:
        """表内角标一律通用行内公式上角标（GEN-119，2026-09-19 用户裁定）。

        GB/T 1.1-2020 9.12.2 / 附录 F：表注由标记与解释成对组成。2026-09-19 起
        表内角标**只**写 `$^{a}$`（正体、小号、上移；未上榜 `[:sup:a]` 注解区家族
        ——含 `[:/sup]`、更早的 `[:^a]`/`[^a]…[^a/]`——已退役）；注文按源版面的
        `a）注文` 形态另排（同格多条以 `<br>` 分隔，canonical 显式书写）。
        """
        def rendered(text: str) -> str:
            return _markup(_table_cell_superscripts(text))

        # 引用点：词中（20001.10 表1 表头型）与词尾；角标前是角标字隙（GEN-140）
        gap = _SCRIPT_GAP_105
        self.assertEqual(rendered("要素$^{a}$的编排"), f"要素{gap}<super>a</super>的编排")
        self.assertEqual(rendered("表述形式$^{a}$"), f"表述形式{gap}<super>a</super>")
        self.assertEqual(
            rendered("程序指示$^{b}$\x00BR\x00追溯/证实方法$^{c}$"),
            f"程序指示{gap}<super>b</super>\x00BR\x00追溯/证实方法{gap}<super>c</super>",
        )
        # 注文行的行首标记：canonical 写 a）注文，渲染端只做上标还原
        self.assertEqual(rendered("a）黑体表示“必备的”。"), "a）黑体表示“必备的”。")
        self.assertEqual(
            rendered("a）黑体表示“必备的”。\x00BR\x00b）“程序指示”中的指示型条款…。"),
            "a）黑体表示“必备的”。\x00BR\x00b）“程序指示”中的指示型条款…。",
        )
        # 多字符角标（1)、†、a) 等）与下标
        self.assertEqual(rendered("匝间绝缘$^{a)}$"), f"匝间绝缘{gap}<super>a)</super>")
        self.assertEqual(rendered("注解$_{2}$"), f"注解{gap}<sub>2</sub>")
        # 退役写法不再有特殊语义（按普通文本渲染，不产生角标）
        self.assertNotIn("<super>", rendered("[:sup:a]注文[:/sup]"))
        # 条文脚注引用（表内）：[foot:N] → “N)”
        self.assertEqual(rendered("见注[foot:1]"), f"见注{gap}<super>1)</super>")

    def test_table_cell_superscripts_plain_letters_stay_plain(self) -> None:
        # 2026-09-07 移除“汉字后小写字母=上标”字形猜测（词尾/词中/行首解释
        # 标记在单元格内均不再猜测）：字面小写字母（单位、变量、旧式锚点残字、
        # 大写相位字母）一律按普通文本渲染。
        def rendered(text: str) -> str:
            return _markup(_table_cell_superscripts(text))

        self.assertEqual(rendered("匝间绝缘a"), "匝间绝缘a")
        self.assertEqual(rendered("匝间绝缘ａ"), "匝间绝缘ａ")
        self.assertEqual(rendered("要素a的编排"), "要素a的编排")
        self.assertEqual(rendered("表述形式a"), "表述形式a")
        self.assertEqual(rendered("a 说明"), "a 说明")
        self.assertEqual(rendered("b黑体表示…"), "b黑体表示…")
        # 单位/大写/列项引用不误伤（原负例保留）
        self.assertEqual(rendered("规格mm"), "规格mm")
        self.assertEqual(rendered("输入功率W"), "输入功率W")
        self.assertEqual(rendered("250V"), f"250{_UNIT_GAP}V")
        self.assertEqual(rendered("≤55 dB(A)"), f"≤55{_UNIT_GAP}dB(A)")
        self.assertEqual(rendered("A 相"), "A 相")
        self.assertEqual(rendered("B相"), "B相")
        self.assertEqual(rendered("编写a)中所述"), "编写a)中所述")
        # 词尾引用点经显式标记还原（20001.10/20001.5 表1 表头型）
        self.assertEqual(rendered("要素所允许的表述形式$^{a}$"), f"要素所允许的表述形式{_SCRIPT_GAP_105}<super>a</super>")


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
        # 公式变量行（字母后破折号）：不触发脚注上标；破折号两侧补四分之一汉字
        # 固定字隙（GBT-X06 / CSM-OCR-018 的变量解释形态，_markup 执行侧）。
        gap = '<font size="2.625" color="white">中</font>'
        self.assertEqual(rendered("n —转速，单位为转每分"), f"n{gap}—{gap}转速，单位为转每分")
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
        # 条号间隙 2026-09-03 起用白字“中”填充 1em（reportlab 折叠 U+3000
        # 成窄空格）；getPlainText 会提取该不可见字形——断言按编号+题名子串匹配。
        self.assertTrue(any("马铃薯脱毒试管苗繁育" in t for t in texts),
                        f"5 标题缺失: {texts!r}")
        self.assertTrue(any("5.1" in t and "田间选择" in t for t in texts),
                        f"5.1 标题缺失: {texts!r}")
        self.assertTrue(any("5.2" in t and "病毒检测筛选" in t for t in texts),
                        f"5.2 标题缺失: {texts!r}")


class UntitledClauseLatinGeometryTests(unittest.TestCase):
    """GBT-B02：编号后接拉丁字母的裸条顶格起排，且编号后空一个汉字。

    GB_3100-2026 4.2「SI 是采用如下常量的单位制：」/ 4.3 / 6.1 / 8.2.5 四条，
    源 PDF 与其余条号同列顶格。判定需要所在节点的条号，故从 `_append_nodes`
    入口渲染（节点带 number），并以 PDF 内部对象（字形原点坐标）验证：编号同列、
    编号→正文首字的推进宽为 1 个汉字（修前为 2 汉字缩进 + 1/4 汉字数值-单位字隙）。
    """

    EM = 10.5  # profile 正文五号（config/rendering/GB_T_1.1-2020.yaml）
    ROOT = Path(__file__).resolve().parents[1]

    @classmethod
    def _render_lines(cls, nodes):
        try:
            import pymupdf
        except ImportError:  # pragma: no cover - 环境缺 pymupdf 时跳过
            raise unittest.SkipTest("pymupdf unavailable")
        import tempfile

        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        from leleby_ssir.pdf_renderer import PDFRenderReport, _styles

        font_asset = cls.ROOT / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        profile_asset = cls.ROOT / "config" / "rendering" / "GB_T_1.1-2020.yaml"
        if not font_asset.is_file() or not profile_asset.is_file():
            raise unittest.SkipTest("font/profile asset missing")
        name = "ClauseHeadBody"
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(font_asset)))
        profile = yaml.safe_load(profile_asset.read_text(encoding="utf-8"))
        styles = _styles(getSampleStyleSheet(), profile, name, name, TA_CENTER, TA_JUSTIFY, TA_LEFT)
        report = PDFRenderReport(input_file="t.pdf", output_file="t.render.pdf",
                                 profile_file="", profile_id="", font_file="")
        story: list = []
        _append_nodes(
            story, nodes,
            registries={"tables": {}, "figures": {}, "formulas": {}},
            styles=styles, font=name, report=report, asset_dir=Path(tempfile.mkdtemp()),
            colors=colors, Table=Table, TableStyle=TableStyle, Paragraph=Paragraph,
            Spacer=Spacer, Image=Image, marker_factory=None, PageBreak=None,
            example_default="frame",
        )
        target = Path(tempfile.mkdtemp()) / "clause-head.pdf"
        SimpleDocTemplate(str(target), pagesize=(600, 400), leftMargin=40, rightMargin=40,
                          topMargin=40, bottomMargin=40).build(story)
        page = pymupdf.open(str(target))[0]
        records = []
        for block in page.get_text("rawdict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                chars = [c for span in line["spans"] for c in span["chars"]]
                text = "".join(c["c"] for c in chars)
                if text.strip():
                    records.append((text, [(c["c"], round(c["origin"][0], 2)) for c in chars]))
        return records

    @staticmethod
    def _node(number, title, paragraphs):
        return {
            "id": f"n-{number}", "nodeType": "section", "number": number, "title": title,
            "contentElements": [
                {"presentationType": "paragraph", "sortOrder": index, "textContent": text}
                for index, text in enumerate(paragraphs)
            ],
            "children": [],
        }

    @staticmethod
    def _line(records, prefix):
        for text, chars in records:
            if text.startswith(prefix):
                return text, chars
        raise AssertionError(f"line {prefix!r} not found in {[text for text, _ in records]}")

    def test_latin_clause_head_is_flush_and_keeps_one_han_gap(self) -> None:
        nodes = [self._node("4", "国际单位制的构成", [
            "4.1 国际单位制（SI）是国际计量大会（CGPM）采用和推荐的一贯单位制。",
            "4.2 SI 是采用如下常量的单位制：",
        ])]
        records = self._render_lines(nodes)
        _, cjk = self._line(records, "4.1")
        _, latin = self._line(records, "4.2")
        # 顶格：两条编号同列（修前 4.2 比 4.1 右移 2 汉字 = 21pt）。
        self.assertAlmostEqual(latin[0][1], cjk[0][1], places=2)
        # 字隙：编号后恰为 1 汉字（修前 4.2 落进数值-单位规则，只有 1/4 汉字 ≈ 2.6pt）。
        self.assertAlmostEqual(cjk[4][1] - cjk[3][1], self.EM, delta=0.3)
        self.assertAlmostEqual(latin[4][1] - latin[3][1], self.EM, delta=0.3)

    def test_latin_paragraph_under_a_foreign_clause_stays_indented(self) -> None:
        nodes = [
            self._node("5", "SI 单位", ["4.2 SI 是采用如下常量的单位制："]),
            self._node("6", "SI 单位及其十进倍数和分数单位的应用", ["普通正文段落，空两个汉字起排。"]),
        ]
        records = self._render_lines(nodes)
        _, body = self._line(records, "普通正文段落")
        _, foreign = self._line(records, "4.2")
        # 章 5 里的 "4.2 SI…" 不是本章的条号（父条号 3 ≠ 5）→ 与普通正文同列。
        self.assertAlmostEqual(foreign[0][1], body[0][1], places=2)


class TableCellLineBreakTests(unittest.TestCase):
    """表单元格行结构（<br>，merge 阶段从源文本层恢复）渲染为真实换行。

    Regression (2026-08-31, GB_T_20001.6-2017 表1)：单元格 "术语和定义
    ……程序确立程序指示b追溯/证实方法……规范性附录" 被 OCR 压成单行，恢复为
    <br> 连接的多行后，_markup 必须把它转成 <br/>（不能折叠为空格），且
    行尾表注引用点（2026-09-07 起为显式 $^{b}$ 标记）仍触发上标。
    """

    def test_br_becomes_line_break_and_footnote_superscript_fires(self) -> None:
        cell = "术语和定义<br>……<br>程序确立<br>程序指示$^{b}$<br>追溯/证实方法$^{c}$<br>……<br>规范性附录"
        marked = cell.replace("<br>", "\x00BR\x00")
        out = _markup(_table_cell_superscripts(marked)).replace("\x00BR\x00", "<br/>")
        self.assertIn("<br/>", out)
        self.assertIn("<super>b</super>", out)
        self.assertIn("<super>c</super>", out)
        self.assertEqual(out.count("<br/>"), 6)

    def test_plain_cells_unaffected(self) -> None:
        cell = "规格mm"
        marked = cell.replace("<br>", "\x00BR\x00")
        out = _markup(_table_cell_superscripts(marked)).replace("\x00BR\x00", "<br/>")
        self.assertNotIn("<br/>", out)
        self.assertNotIn("<super>", out)


class Gb3100SuperscriptTableNoteTests(unittest.TestCase):

    def setUp(self) -> None:
        """显式声明希腊字形族（GEN-122），用例不依赖执行顺序。"""
        from leleby_ssir import pdf_renderer as _renderer

        previous = (_renderer._GREEK_FONT, _renderer._GREEK_ITALIC_FONT)
        _renderer._GREEK_FONT, _renderer._GREEK_ITALIC_FONT = "LiberationSerif", "LiberationSerif-Italic"
        self.addCleanup(setattr, _renderer, "_GREEK_FONT", previous[0])
        self.addCleanup(setattr, _renderer, "_GREEK_ITALIC_FONT", previous[1])
        # 角标字隙（GEN-140）：字面清空 → 只留固定字隙，断言不随执行顺序变化。
        _pin_math_faces(self)

    """GB_3100-2026 六项排版修复回归（2026-09-02）。

    Fix C/D：HTML <sup>/<sub> 与缺字形 Unicode 上标（⁰⁵⁶⁷⁸⁹⁻⁺，Noto Serif
    CJK SC 无字形）→ reportlab <super>/<sub> 真上标；Fix E：表格平拍指数恢复；
    Fix F：LaTeX 拍平输出哨兵；Fix H：表注行按「注N：」拆分。
    """

    def test_html_sup_sub_map_to_reportlab_tags(self) -> None:
        # Fix C：MinerU 数学幂/原子下标标签 → 真上标/下标（sentinel 恢复）；
        # 角标前是角标字隙（GEN-140）。
        gap = _SCRIPT_GAP_105
        self.assertEqual(_markup("10<sup>27</sup>"), f"10{gap}<super>27</super>")
        self.assertEqual(_markup("N<sub>A</sub>为"), f"N{gap}<sub>A</sub>为")

    def test_missing_glyph_unicode_superscripts_become_super(self) -> None:
        # Fix D：正文宋体缺 ⁰⁵⁶⁷⁸⁹⁻⁺ 字形，直接渲染成 .notdef 方框；
        # 归一为 <super> 内普通字符，相邻上标合并为一个 run。
        gap = _SCRIPT_GAP_105
        self.assertEqual(_markup("10⁻⁸ s 可写成"), f"10{gap}<super>−8</super> s 可写成")
        self.assertEqual(_markup("10⁸称为亿"), f"10{gap}<super>8</super>称为亿")
        self.assertEqual(_markup("米·秒⁻¹"), f"米·秒{gap}<super>−</super>¹")

    def test_table_cell_flat_exponents_recovered(self) -> None:
        # Fix E：GB_3100-2026 表2/表3/附录B 拍平上标还原（s−1→s⁻¹、N/m2→N/m²、
        # 10-2→10⁻²、10²4→10²⁴）——只保留抽取里带证据的分支（GEN-104）。
        self.assertEqual(_markup(_table_cell_superscripts("10-2")), f"10{_SCRIPT_GAP_105}<super>−2</super>")
        self.assertEqual(_markup(_table_cell_superscripts("10²4")), f"10{_SCRIPT_GAP_105}<super>24</super>")
        self.assertEqual(_markup(_table_cell_superscripts("1 Hz = 1 s−1")), f"1{_UNIT_GAP}Hz = 1{_UNIT_GAP}s{_SCRIPT_GAP_105}<super>−1</super>")
        self.assertEqual(_markup(_table_cell_superscripts("1 Pa = 1 N/m2")), f"1{_UNIT_GAP}Pa = 1{_UNIT_GAP}N/m{_SCRIPT_GAP_105}<super>2</super>")
        self.assertEqual(_markup(_table_cell_superscripts("100")), "100")
        self.assertEqual(_markup(_table_cell_superscripts("centi")), "centi")

    def test_table_cell_plain_numbers_are_not_exponents(self) -> None:
        # GEN-104（2026-09-15）：删除「10+纯数字」猜测分支。抽取层对「10 的正幂」
        # 没有任何证据（MinerU markdown 无字号信息，middle.json 的 span 也不带字号），
        # 该形态与普通数值完全同形——不得改写成 10 的幂。
        # 语料实测（GB/T 5171.1-2014 表1「105(A级)」温度等级印成 10⁵，源 PDF p12
        # 实测 105 与同行同为 8.25pt 普通数字；GB_3100-2026「1024 bit」「(π/10800) rad」；
        # GB/T 10401-2023 表内数据「107」）。
        for text in ("1030", "105", "105(A级)", "100", "1024", "1024 bit", "107", "10800",
                     "1' = (1/60) = (π/10800) rad", "60(50)"):
            with self.subTest(text=text):
                self.assertEqual(_table_cell_superscripts(text), text)
                self.assertNotIn("\x00SUP\x00", _table_cell_superscripts(text))

    def test_latex_emits_sentinels_and_markup_restores_tags(self) -> None:
        # Fix F：4.2 常量行 LaTeX → 可读文本 + 上标哨兵；数字逐字空格收紧；
        # \Delta V 命令终止空格折叠（ΔV 同一量符号），单位内部拉丁乘积空格保留。
        # GBT-B12：量值以幂次收尾时（10⁻³⁴ J）单位前同样是固定字隙。
        self.assertEqual(
            _markup("$6 . 6 2 6 0 7 0 1 5 \\times 1 0 ^ { - 3 4 } \\mathrm { J } \\mathrm { s } ;$"),
            f"6.62607015×10{_SCRIPT_GAP_105}<super>−34</super>{_UNIT_GAP}J s ;",
        )
        self.assertEqual(_markup("$\\cdot \\Delta V _ { \\mathrm { c s } }$"), f'·<font name="LiberationSerif">Δ</font><i>V</i>{_SCRIPT_GAP_105}<sub>cs</sub>')
        self.assertEqual(_markup("$K _ { \\mathrm { c d } }$"), f"<i>K</i>{_SCRIPT_GAP_105}<sub>cd</sub>")

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

    def test_lettered_table_footnotes_split_into_per_note_parts(self) -> None:
        # 2026-09-23（用户裁定「所有表注：每条注的首行都要空两个汉字」）：表脚注用字母
        # 标记（a)/b）…），彼此之间同样是 <br>。旧实现只认「注N：」边界 → 整格只出一个
        # 段落 → 只有 a) 的首行带两字缩进，b) 起全部顶格（实测 GB_T_5171.1-2014 表20：
        # a) x0=100.6 有缩进、e) x0=82.6 顶格）。
        cell = "a) 第7项试验对交流换向器电动机允许抽查。<br>b) 仅对单相电容电动机才需进行。<br>e) 在实际热态下进行。"
        parts = _split_table_note_parts(cell)
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0], "a) 第7项试验对交流换向器电动机允许抽查。")
        self.assertEqual(parts[2], "e) 在实际热态下进行。")

    def test_lettered_footnote_inner_break_is_kept(self) -> None:
        # <br> 之后不是注标记 → 是该条注的**注内换行**（续行），保留在条内、不切条。
        cell = "a) 第一条注文很长，<br>跨行的续句。<br>b) 第二条注文。"
        parts = _split_table_note_parts(cell)
        self.assertEqual(len(parts), 2)
        self.assertIn("\x00BR\x00", parts[0])
        self.assertEqual(parts[1], "b) 第二条注文。")

    def test_plain_multiline_note_is_not_split_by_br(self) -> None:
        # 反向守卫：注文内的换行（后面不接注标记）不得被当成两条注。
        cell = "注1：第一条注的续行<br>仍然属于第一条注。"
        parts = _split_table_note_parts(cell)
        self.assertEqual(len(parts), 1)
        self.assertIn("\x00BR\x00", parts[0])


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

    def test_widths_fill_frame_proportional_to_content(self) -> None:
        # 2026-09-07 三次裁定：表格总宽恒 = 版心 455pt（充分利用版面空间，与
        # 文字版心等宽）；每列在"需求 + 左右边距 8pt"上按需求比例吸收富余空间
        # ——文字距两端线均有舒适留距、无临界折行；仅内容超版心才压缩。
        # 表4 型：关系列（长公式）需求最大，比例分配后仍显著宽于窄列。
        rows = self._rows(
            ["量的名称", "单位名称", "单位符号", "与SI单位的关系"],
            [
                ["时间", "分", "min", "1 min = 60 s"],
                ["速度", "节", "kn", "1 kn=1 n mile/h=（1852/3600）m/s（只用于航行）"],
                ["线密度", "特[克斯]", "tex", "1 tex = 10⁻¹ kg/m"],
            ],
        )
        widths = _table_column_widths(rows, 4, 9.0, {}, self._IMG)
        self.assertAlmostEqual(sum(widths), 455.0, delta=1e-3)
        self.assertGreater(widths[3], widths[0])
        self.assertGreater(widths[3], 2 * widths[0])  # 关系列显著宽于窄列
        # 列宽不低于"内容最大行宽 + 左右边距"（保证逐行不折行）
        self.assertGreaterEqual(widths[0], _cell_text_natural_width("量的名称", 9.0) + 8.0 - 1e-6)

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
        # 注行不撑爆任何单列（通栏行不计入单列需求）；总宽恒 = 版心
        self.assertLess(widths[0], 150)
        self.assertAlmostEqual(sum(widths), 455.0, delta=1e-3)

    def test_empty_column_gets_floor_width(self) -> None:
        rows = self._rows(["名称", "", "符号"], [["时间", "", "min"], ["长度", "", "m"]])
        widths = _table_column_widths(rows, 3, 9.0, {}, self._IMG)
        self.assertGreaterEqual(widths[1], 24.0)
        self.assertAlmostEqual(sum(widths), 455.0, delta=1e-3)


class TableColumnWidthByWrapCostTests(unittest.TestCase):
    """按折行代价分配列宽（GEN-110，2026-09-17 用户四条目标）。

    现象：旧口径（需求 = 表头自然宽 + 12pt 与数据 80% 分位取大，再「富余均分 /
    按数据需求比例分」）不看折行代价——GB/T 30819-2024 表4 把「表头长、数据短」的
    第 4/5 列撑到 130/94pt（源排版 84/69pt，数据只要 19pt）而表头照样折行；
    GB/T 1.1-2020 表F.1 第 2 列 112pt（内容 84pt 够）而第 4 列 117pt、折行 8 处。
    新口径用**渲染端同一实现**测量每个单元格的折行行数，按字典序（总高 → 折行行数
    → 折行格数）逐段买入宽度，余额按各列宽度比例分配。

    断言均取自真实测量（``_TableCellMeasurer`` 走真实 reportlab 样式与折行），
    不依赖自然宽估计。
    """

    _IMG = re.compile(r"!\[(?:[^\]]*)\]\(([^)]+)\)")
    FRAME = 455.0
    FONT_SIZE = 9.0

    def _measurer(self) -> "_TableCellMeasurer":
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Image

        from leleby_ssir.pdf_renderer import _TableCellMeasurer, _styles

        root = Path(__file__).resolve().parents[1]
        font = root / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        profile_asset = root / "config" / "rendering" / "GB_T_1.1-2020.yaml"
        if not font.is_file() or not profile_asset.is_file():
            self.skipTest("font/profile asset missing")
        name = "WrapCostTest"
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(font)))
        profile = yaml.safe_load(profile_asset.read_text(encoding="utf-8"))
        styles = _styles(getSampleStyleSheet(), profile, name, name, TA_CENTER, TA_JUSTIFY, TA_LEFT)
        return _TableCellMeasurer(
            styles=styles, cell_image_sizes={}, cell_image_re=self._IMG,
            label_font=name, asset_dir=root, Image=Image, font_size=self.FONT_SIZE,
        )

    @staticmethod
    def _rows(header: list[str], data: list[list[str]]) -> list[dict]:
        def _cells(texts: list[str]) -> list[dict]:
            return [{"colIndex": i, "colspan": 1, "rowspan": 1, "text": t} for i, t in enumerate(texts)]

        return [
            {"rowIndex": 0, "isHeader": True, "cells": _cells(header)},
            *[{"rowIndex": i + 1, "isHeader": False, "cells": _cells(row)} for i, row in enumerate(data)],
        ]

    @staticmethod
    def _cost(rows: list[dict], widths: list[float], measurer: Any) -> tuple[float, int, int]:
        """(总高, 折行行数, 折行格数)：行高 = 该行最高单元格的行数。"""
        row_max: dict[int, int] = {}
        extra = 0
        wrapped = 0
        for row in rows:
            lead = measurer.leading(bool(row.get("isHeader")))
            for cell in row.get("cells", []):
                if not str(cell.get("text", "")).strip():
                    continue
                start = cell["colIndex"]
                span = int(cell.get("colspan", 1) or 1)
                lines = measurer.lines(cell["text"], sum(widths[start:start + span]), bool(row.get("isHeader")))
                extra += lines - 1
                wrapped += 1 if lines > 1 else 0
                row_max[row["rowIndex"]] = max(row_max.get(row["rowIndex"], 0), lines)
        height = sum(
            lines * measurer.leading(bool(row.get("isHeader")))
            for row in rows
            for lines in [row_max.get(row["rowIndex"], 0)]
        )
        return height, extra, wrapped

    def test_wrap_cost_beats_equal_split_on_the_stated_objectives(self) -> None:
        """长表头 + 数据格列：新口径在「总高 → 折行行数」上严格优于等分（GEN-110 ① ②）。

        表F.1 型：第 2 列表头长（「层次、要素及表述」）但数据很短，第 4 列数据长
        且行数多——旧口径把第 2 列按表头撑宽、第 4 列挤窄，折行集中在第 4 列。
        """
        measurer = self._measurer()
        header = ["序号", "层次、要素及表述", "位置", "文字内容", "字号和字体"]
        data = []
        for i in range(1, 22):
            data.append([f"{i:02d}", "封面" if i < 14 else "", f"第{i}行", "中华人民共和国××行业标准" if i == 7 else "四号黑体", "五号正常体"])
        rows = self._rows(header, data)
        widths = _table_column_widths(rows, 5, self.FONT_SIZE, {}, self._IMG, frame_width=self.FRAME, measurer=measurer)
        equal = [self.FRAME / 5] * 5
        self.assertAlmostEqual(sum(widths), self.FRAME, delta=1e-3)
        cost_new = self._cost(rows, widths, measurer)
        cost_equal = self._cost(rows, equal, measurer)
        self.assertLess(cost_new[0], cost_equal[0], (cost_new, cost_equal))     # ① 总高更小
        self.assertLessEqual(cost_new[1], cost_equal[1], (cost_new, cost_equal))  # ② 折行更少
        # 第 4 列（长内容）拿到足够宽度：其最长数据格不再折行
        longest = max((c for r in rows[1:] for c in r["cells"] if c["colIndex"] == 3), key=lambda c: len(c["text"]))
        self.assertEqual(measurer.lines(longest["text"], widths[3], False), 1, widths)

    def test_long_header_column_yields_width_instead_of_hogging_it(self) -> None:
        """表头长、数据短的列不再按「表头自然宽」撑满（GB/T 30819-2024 表4 的第 4/5 列）。

        同形的 7 列表：第 4/5/6 列表头 13/12/12 字（1 行需 157/112/104pt）而数据只有
        两三个数字。旧口径给这几列「表头自然宽 + 12pt」（实测 130/94/48pt），数据格
        大面积留白而表头照样折行；新口径允许表头折行、把宽度让给真正需要的列——
        验收：表头列宽 < 它自己的 1 行需求（表头折行）、**数据格一个都不折行**、
        三项代价（总高/折行行数/折行格数）全面优于等分。
        """
        measurer = self._measurer()
        header = ["规格代号", "传动比", "额定输出转矩N·m", "启动、停止时的允许最大输出转矩N·m",
                  "瞬间允许最大输出转矩N·m", "允许最高输入转速r/min", "润滑方式"]
        data = [
            [str(14 + i), str(30 + i * 5), f"{7.2 + i * 3.1:.1f}", f"{15.6 + i * 6.2:.1f}",
             f"{31.2 + i * 12.4:.1f}", f"{12000 - i * 300}", "润滑油润滑(O)" if i % 2 else "润滑脂润滑(G)"]
            for i in range(20)
        ]
        rows = self._rows(header, data)
        widths = _table_column_widths(rows, 7, self.FONT_SIZE, {}, self._IMG, frame_width=self.FRAME, measurer=measurer)
        self.assertAlmostEqual(sum(widths), self.FRAME, delta=1e-3)
        # 表头列宽 < 表头 1 行所需宽 → 表头折行、宽度让给数据列（旧口径按表头撑满）
        for col in (3, 4, 5):
            self.assertLess(widths[col], _cell_text_natural_width(header[col], self.FONT_SIZE) + 8.0, widths)
        # 数据格全部一行排下（用户目标 ②③：折行尽量少、内容保持完整）
        for row in rows[1:]:
            for cell in row["cells"]:
                self.assertEqual(measurer.lines(cell["text"], widths[cell["colIndex"]], False), 1, (cell["text"], widths))
        # 四项目标的量比：总高、折行行数、折行格数全面优于等分
        self.assertLess(self._cost(rows, widths, measurer)[0], self._cost(rows, [self.FRAME / 7] * 7, measurer)[0])
        self.assertLessEqual(self._cost(rows, widths, measurer)[1], self._cost(rows, [self.FRAME / 7] * 7, measurer)[1])

    def test_full_width_note_row_does_not_drag_a_column(self) -> None:
        """通栏注行/单长格行不参与列宽（测量与渲染同判据）。

        渲染端会把「一行只有一个长文本格」的行 SPAN 成通栏（colspan=全部列，或
        lone_full 判据），这类行按整表宽排版，不得把某一列撑宽。
        """
        measurer = self._measurer()
        rows = self._rows(["A", "B", "C", "D"], [["1", "2", "3", "4"], ["5", "6", "7", "8"]])
        rows.append({
            "rowIndex": 99, "isHeader": False,
            "cells": [
                {"colIndex": 0, "colspan": 4, "rowspan": 1, "text": "注1：" + "很长的通栏注内容。" * 30},
                {"colIndex": 1, "colspan": 1, "rowspan": 1, "text": ""},
                {"colIndex": 2, "colspan": 1, "rowspan": 1, "text": ""},
                {"colIndex": 3, "colspan": 1, "rowspan": 1, "text": ""},
            ],
        })
        rows.append({
            "rowIndex": 100, "isHeader": False,
            "cells": [{"colIndex": i, "colspan": 1, "rowspan": 1, "text": ("一" * 60) if i == 0 else ""} for i in range(4)],
        })
        widths = _table_column_widths(rows, 4, self.FONT_SIZE, {}, self._IMG, frame_width=self.FRAME, measurer=measurer)
        self.assertAlmostEqual(sum(widths), self.FRAME, delta=1e-3)
        # 两行的长文本都不撑宽任何单列：列宽不超「正常内容 + 均分余额」的量级
        self.assertLess(max(widths), 200.0, widths)

    def test_empty_column_keeps_floor_and_every_column_keeps_lower_bound(self) -> None:
        """空列保底 floor、每列 ≥ 下界（左右边距 + 一个汉字宽），Σ 恒 = 版心（GEN-103/110）。"""
        measurer = self._measurer()
        rows = self._rows(["名称", "", "符号"], [["时间", "", "min"], ["长度", "", "m"]])
        widths = _table_column_widths(rows, 3, self.FONT_SIZE, {}, self._IMG, frame_width=self.FRAME, measurer=measurer)
        lower = 2 * 4.0 + self.FONT_SIZE
        self.assertAlmostEqual(sum(widths), self.FRAME, delta=1e-3)
        self.assertEqual(widths[1], 24.0)          # 空列保底（不参与买入与余额分配）
        for width in widths:
            self.assertGreaterEqual(width + 1e-9, lower)


class WrapCostColumnWidthPdfTests(unittest.TestCase):
    """按折行代价分配列宽的**端到端**验收（GEN-110，PDF 内部对象）。

    测试内生成 canonical（两张表：7 列表头长/数据短 = GB/T 30819-2024 表4 形，
    5 列第 2 列宽/第 4 列挤 = GB/T 1.1-2020 表F.1 形）→ 真实渲染 → 断言：
      ① 数据行行高 = 一行（21pt = 15pt 行距 + 上下 3pt 边距），即**数据格零折行**；
      ② PDF 竖线间距 = 分配器算出的列宽（分配与渲染同一份列宽）。
    """

    ROOT = Path(__file__).resolve().parents[1]
    HEAD_A = ["规格代号", "传动比", "额定输出转矩N·m", "启动、停止时的允许最大输出转矩N·m",
              "瞬间允许最大输出转矩N·m", "允许最高输入转速r/min", "润滑方式"]
    HEAD_B = ["序号", "层次、要素及表述", "位置", "文字内容", "字号和字体"]

    def _canonical(self) -> str:
        lines = ["\n".join([
            "---", "csm-version: '1.0'", "document-type: standard",
            "document-identifier: T_WRAP_001-2026", "standard-number: T/WRAP 001-2026",
            "title: 列宽折行代价渲染夹具", "publication-date: '2026-01-01'",
            "effective-date: '2026-02-01'", "ics: '01.120'", "ccs: A 00", "language: zh-CN",
            "source:", "  mode: user-markdown", "extraction-backend: fixture", "extensions: {}", "---",
        ]), "# 列宽折行代价渲染夹具", "## 1 范围",
         "本夹具规定列宽按折行代价分配后的渲染结果。", "## 2 表", 
         '<!-- ssir:table id="wrap-001" header-rows="1" caption-number="4" -->', "**表4**",
         "| " + " | ".join(self.HEAD_A) + " |",
         "| " + " | ".join(["---"] * len(self.HEAD_A)) + " |"]
        for i in range(20):
            lines.append("| " + " | ".join([
                str(14 + i), str(30 + i * 5), f"{7.2 + i * 3.1:.1f}", f"{15.6 + i * 6.2:.1f}",
                f"{31.2 + i * 12.4:.1f}", f"{12000 - i * 300}", "润滑油润滑(O)" if i % 2 else "润滑脂润滑(G)",
            ]) + " |")
        lines += ["## 3 表F.1 形",
                  '<!-- ssir:table id="wrap-002" header-rows="1" caption-number="F.1" -->', "**表F.1**",
                  "| " + " | ".join(self.HEAD_B) + " |",
                  "| " + " | ".join(["---"] * len(self.HEAD_B)) + " |"]
        for i in range(1, 22):
            lines.append("| " + " | ".join([
                f"{i:02d}", "封面" if i < 14 else "", f"第{i}行",
                "中华人民共和国××行业标准" if i == 7 else "四号黑体", "五号正常体",
            ]) + " |")
        lines.append("")
        return "\n".join(lines)

    def test_data_cells_never_wrap_and_pdf_columns_match_the_allocation(self) -> None:
        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        import json
        import tempfile

        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import _TableCellMeasurer, _styles, _table_column_widths, render_pdf_file

        font = self.ROOT / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font.is_file():
            self.skipTest("body font asset missing")
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Image

        img_re = re.compile(r"!\[(?:[^\]]*)\]\(([^)]+)\)")
        name = "WrapCostPdf"
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(font)))
        profile = yaml.safe_load((self.ROOT / "config" / "rendering" / "GB_T_1.1-2020.yaml").read_text(encoding="utf-8"))
        styles = _styles(getSampleStyleSheet(), profile, name, name, TA_CENTER, TA_JUSTIFY, TA_LEFT)
        measurer = _TableCellMeasurer(
            styles=styles, cell_image_sizes={}, cell_image_re=img_re,
            label_font=name, asset_dir=self.ROOT, Image=Image, font_size=styles["table"].fontSize,
        )

        with tempfile.TemporaryDirectory() as directory:
            canonical = Path(directory) / "wrap.canonical.md"
            canonical.write_text(self._canonical(), encoding="utf-8")
            document = SSIRBuilder().build(CSMParser().read(str(canonical)))
            expected: dict[str, list[float]] = {}
            for table in document["tables"]:
                expected[str(table.get("number"))] = _table_column_widths(
                    table["rows"], table["colCount"], styles["table"].fontSize, {}, img_re,
                    frame_width=_BODY_MEASURE, measurer=measurer,
                )
            ssir = Path(directory) / "wrap.ssir.json"
            ssir.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            target = Path(directory) / "wrap.pdf"
            render_pdf_file(str(ssir), str(target), toc_depth=None)
            rendered = pymupdf.open(str(target))
            row_heights: list[float] = []
            column_widths: list[list[float]] = []
            for page in rendered:
                verticals = sorted({round((d["rect"].x0 + d["rect"].x1) / 2, 1) for d in page.get_drawings() if d["rect"].width < 1.5 and d["rect"].height >= 20})
                if len(verticals) < 2:
                    continue                      # 无表格网格的页（封面/目次/正文）跳过
                left, right = verticals[0], verticals[-1]
                horizontals = sorted({
                    round((d["rect"].y0 + d["rect"].y1) / 2, 1)
                    for d in page.get_drawings()
                    if d["rect"].height < 1.5 and d["rect"].width >= (right - left) * 0.9
                })
                row_heights.extend(round(b - a, 1) for a, b in zip(horizontals, horizontals[1:]))
                column_widths.append([round(b - a, 1) for a, b in zip(verticals, verticals[1:])])
            rendered.close()
        # ① 数据行全部一行高（21pt）；只有表头行可能更高（长表头折行不可避免）
        one_line = 15.0 + 2 * 3.0
        multi = sorted({height for height in row_heights if height > one_line + 0.6})
        self.assertTrue(row_heights, row_heights)
        self.assertLessEqual(len(multi), 2, multi)          # 两张表的表头行
        # ② PDF 竖线间距 == 分配器算出的列宽（同一份列宽；列宽和恒 = 版心）
        for number, widths in expected.items():
            self.assertAlmostEqual(sum(widths), _BODY_MEASURE, delta=1e-3, msg=number)
            matches = [page for page in column_widths if len(page) == len(widths)]
            self.assertTrue(matches, (number, widths, column_widths))
            self.assertLessEqual(
                min(max(abs(a - b) for a, b in zip(page, widths)) for page in matches), 1.0,
                (number, widths, matches),
            )


class SideBySideColumnWidthTests(unittest.TestCase):
    """并列组列宽按各列内容自然宽分配（GEN-111，2026-09-17 用户报告）。

    现象：GB/T 1.1-2020 9.9.3.1 示例4 的右栏「不正确：」下公式折行——旧口径的
    列需求只看**图片**（图/公式绘制宽），GEN-106 拍平成文字的含汉字公式
    （`dim (能量) = dim (力) × \\dim (长度)`）在这一列需求为 0 → 退化成 60pt 占位
    → 列宽 [274.5, 131]，而该列一行需要 166.4pt，于是被挤成
    「dim (能量) = dim (力)×(」+「长度)」两行（另一个公式同样）。
    """

    def test_equal_split_when_every_column_fits(self) -> None:
        """版心够时**等分**（对照型「正确/不正确」并列保持对称），不按内容长短拉偏。"""
        from leleby_ssir.pdf_renderer import _side_by_side_widths

        widths = _side_by_side_widths([125.7, 166.4], 405.5)
        self.assertAlmostEqual(widths[0], widths[1], places=6)
        self.assertAlmostEqual(sum(widths), 405.5, places=6)
        self.assertGreaterEqual(min(widths), 166.4)

    def test_width_is_donated_to_the_column_that_does_not_fit(self) -> None:
        """某列排不下时，从有余量的列按余量比例让宽，直到它排得下。"""
        from leleby_ssir.pdf_renderer import _side_by_side_widths

        widths = _side_by_side_widths([50.0, 300.0], 405.0)
        self.assertGreaterEqual(widths[1], 300.0)          # 排得下的那列拿到所需
        self.assertGreaterEqual(widths[0], 50.0)           # 让宽不把对方压到需求以下
        self.assertAlmostEqual(sum(widths), 405.0, places=6)

    def test_total_budget_is_preserved_when_nothing_can_fit(self) -> None:
        """所有列都排不下时等分（谁也占不到便宜），总额恒 = 容器宽。"""
        from leleby_ssir.pdf_renderer import _side_by_side_widths

        widths = _side_by_side_widths([300.0, 300.0], 405.0)
        self.assertAlmostEqual(widths[0], widths[1], places=6)
        self.assertAlmostEqual(sum(widths), 405.0, places=6)

    def test_three_columns_and_degenerate_inputs(self) -> None:
        from leleby_ssir.pdf_renderer import _side_by_side_widths

        self.assertEqual(_side_by_side_widths([], 400.0), [])
        self.assertAlmostEqual(sum(_side_by_side_widths([10.0], 400.0)), 400.0, places=6)
        widths = _side_by_side_widths([40.0, 380.0, 40.0], 480.0)
        self.assertAlmostEqual(sum(widths), 480.0, places=6)
        self.assertGreaterEqual(widths[1], 380.0)
        self.assertGreaterEqual(widths[0], 40.0)
        # 总量不够时（Σ需求 460 > 420）三列等分、总额仍恒 = 容器宽
        tight = _side_by_side_widths([40.0, 380.0, 40.0], 420.0)
        self.assertAlmostEqual(sum(tight), 420.0, places=6)
        self.assertAlmostEqual(tight[1], 340.0, places=6)

    def test_paragraph_natural_width_is_the_rendered_one_line_width(self) -> None:
        """自然宽与渲染同源：段落片段按 reportlab 字宽表累加（不是字符数模型）。"""
        try:
            from reportlab.platypus import Paragraph
        except ImportError:  # pragma: no cover
            self.skipTest("reportlab unavailable")
        from leleby_ssir.pdf_renderer import _flowable_natural_width, _markup

        styles = _side_cell_styles_or_skip(self)
        cases = {"正确：": 31.5, "dim (能量) = dim (力)×dim (长度)": 166.4}
        for text, expected in cases.items():
            width = _flowable_natural_width(Paragraph(_markup(text), styles["side-cell"]))
            self.assertAlmostEqual(width, expected, delta=1.5, msg=text)


def _side_cell_styles_or_skip(case: unittest.TestCase) -> dict:
    """取真实渲染样式（字体资产缺失时跳过）——并列列宽测试与表格测试同款前置。"""
    from pathlib import Path as _Path

    import yaml
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    from leleby_ssir.pdf_renderer import _styles

    root = _Path(__file__).resolve().parents[1]
    font = root / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
    if not font.is_file():
        case.skipTest("body font asset missing")
    name = "SideCellFont"
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, str(font)))
    profile = yaml.safe_load((root / "config" / "rendering" / "GB_T_1.1-2020.yaml").read_text(encoding="utf-8"))
    return _styles(getSampleStyleSheet(), profile, name, name, TA_CENTER, TA_JUSTIFY, TA_LEFT)


class SideBySideColumnWidthPdfTests(unittest.TestCase):
    """并列组列宽的**端到端**验收（GEN-111，PDF 内部对象）。

    测试内生成 canonical（`ssir:columns` 两列：左「正确：」+ 短公式，右「不正确：」+
    含汉字长公式 → 交给 GEN-106 拍平成文本）→ 真实渲染 → 断言右栏那行**只占一行**，
    且行宽 = 其自然宽（不被挤成两行）。
    """

    ROOT = Path(__file__).resolve().parents[1]

    def _canonical(self) -> str:
        return "\n".join([
            "---", "csm-version: '1.0'", "document-type: standard",
            "document-identifier: T_SIDE_001-2026", "standard-number: T/SIDE 001-2026",
            "title: 并列列宽渲染夹具", "publication-date: '2026-01-01'",
            "effective-date: '2026-02-01'", "ics: '01.120'", "ccs: A 00", "language: zh-CN",
            "source:", "  mode: user-markdown", "extraction-backend: fixture", "extensions: {}", "---",
            "# 并列列宽渲染夹具", "## 1 范围", "本夹具规定并列组列宽的渲染结果。",
            "###### 示例 4：", "", "<!-- ssir:box -->", "", "<!-- ssir:columns -->", "",
            "正确：", "", "$$", r"dim (E) =  dim (F) ×  dim (l)", "$$", "",
            "<!-- ssir:column -->", "", "不正确：", "", "$$",
            r"dim (能量 ) = dim (力) × dim ( 长度 )", "$$", "",
            "<!-- ssir:/columns -->", "", "<!-- ssir:/box -->", "",
        ])

    def test_long_formula_line_stays_on_one_line(self) -> None:
        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        import json
        import tempfile

        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import render_pdf_file

        with tempfile.TemporaryDirectory() as directory:
            canonical = Path(directory) / "side.canonical.md"
            canonical.write_text(self._canonical(), encoding="utf-8")
            document = SSIRBuilder().build(CSMParser().read(str(canonical)))
            ssir = Path(directory) / "side.ssir.json"
            ssir.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            target = Path(directory) / "side.pdf"
            render_pdf_file(str(ssir), str(target), toc_depth=None)
            rendered = pymupdf.open(str(target))
            lines = []
            for page in rendered:
                for block in page.get_text("dict")["blocks"]:
                    if block["type"] != 0:
                        continue
                    for line in block["lines"]:
                        text = "".join(span["text"] for span in line["spans"]).strip()
                        if text:
                            lines.append((line["bbox"][0], line["bbox"][2], text))
            long_lines = [item for item in lines if "能量" in item[2]]
            self.assertEqual(len(long_lines), 1, f"含汉字公式被折行：{long_lines!r}")
            x0, x1, text = long_lines[0]
            self.assertEqual(text, "dim (能量) = dim (力)×dim (长度)")
            self.assertAlmostEqual(x1 - x0, 166.4, delta=3.0, msg=text)


class SideBySideHeightFitTests(unittest.TestCase):
    """并列组竖向整组保护（GEN-144 执行侧）：整组放不进版心时**不得**中断渲染。

    现象（2026-09-25，SJ_T_11859-2022 附录 A）：一列里竖向堆两张图，列高 792pt >
    版心 688pt；并列组是**单行**表格，reportlab 不能切分，推向新页仍放不下 →
    `LayoutError: Flowable <Table …> too large on page …` —— **整份渲染中断**。
    修复后按几何同比例缩小整组的图（跨列同比例，保持并列对照的相对大小），
    非图内容不缩放；极端到连最小比例都放不下时退化为上下排布。
    """

    ROOT = Path(__file__).resolve().parents[1]

    def _render(self, canonical_text: str, directory: Path) -> tuple[Any, Any]:
        import json

        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import render_pdf_file

        source = directory / "t.canonical.md"
        source.write_text(canonical_text, encoding="utf-8")
        document = SSIRBuilder().build(CSMParser().read(str(source)))
        ssir = directory / "t.ssir.json"
        ssir.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        target = directory / "t.pdf"
        report = render_pdf_file(str(ssir), str(target), toc_depth=None)
        return report, target

    def test_over_tall_group_is_scaled_to_the_frame(self) -> None:
        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        from PIL import Image as PILImage

        font = self.ROOT / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font.is_file():
            self.skipTest("body font asset missing")
        directory = Path(tempfile.mkdtemp())
        assets = {}
        for name in ("a", "b", "c"):
            asset = directory / f"{name}.png"
            # 300x700px：图按源尺寸不可得 → 固有尺寸只缩小不放大、高度上限 520pt。
            PILImage.new("RGB", (300, 700), (255, 255, 255)).save(asset)
            assets[name] = asset
        canon = (
            "---\n"
            "csm-version: 1.0\n"
            "document-type: standard\n"
            "document-identifier: T_FIT_001-2026\n"
            "standard-number: T/FIT 001—2026\n"
            "title: 并列组竖向容纳夹具\n"
            "language: zh-CN\n"
            "---\n\n"
            "# 并列组竖向容纳夹具\n\n"
            "## 1 范围\n\n"
            "本夹具规定并列组竖向容纳的渲染结果。\n\n"
            "<!-- ssir:columns -->\n\n"
            f"![图 a） 甲]({assets['a']})\n\n"
            f"![图 c） 丙]({assets['c']})\n\n"
            "<!-- ssir:column -->\n\n"
            f"![图 b) 乙]({assets['b']})\n\n"
            "<!-- ssir:/columns -->\n"
        )
        report, target = self._render(canon, directory)

        self.assertTrue(
            any("scaled by" in warning for warning in report.warnings),
            f"整组缩放未记录 warning：{report.warnings!r}",
        )
        rendered = pymupdf.open(str(target))
        frame_height = 688.1574803149607   # 版心高（A4 − 上下边距 − Frame 内衬）
        pages = [
            [
                (info["bbox"][0], info["bbox"][3] - info["bbox"][1])
                for info in page.get_image_info()
            ]
            for page in rendered
        ]
        # 三张图同页（并列组整组同页）；同列图 x 起点相同（列内居中）→ 按 x 分列。
        group = [items for items in pages if len(items) == 3]
        self.assertEqual(len(group), 1, f"并列组未落在同一页：{pages!r}")
        columns: list[list[float]] = []
        for x0, height in group[0]:
            for column in columns:
                if abs(column[1] - x0) < 1.0:
                    column[0] += height
                    break
            else:
                columns.append([height, x0])
        self.assertEqual(len(columns), 2, f"并列组未分成两列：{group[0]!r}")
        # 每列竖向总高 ≤ 版心（修复前第二列那张不会被推下去，第一列 1040pt 直接抛异常）。
        for total, _x0 in columns:
            self.assertLessEqual(total, frame_height, f"整组仍超版心：{group[0]!r}")
        for _x0, height in group[0]:
            self.assertLess(height, 519.0, f"图未被缩放：{group[0]!r}")

    def test_group_that_cannot_fit_falls_back_to_stacked_columns(self) -> None:
        """列内非图内容本身就超版心 → 最小比例也放不下 → 上下排布，不抛 LayoutError。"""
        from leleby_ssir import pdf_renderer as renderer

        class _FakeImage:
            def __init__(self, height: float) -> None:
                self.drawWidth = 100.0
                self.drawHeight = height

            def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
                return self.drawWidth, self.drawHeight

        class _FakeText:
            def __init__(self, height: float) -> None:
                self._height = height

            def wrap(self, availWidth: float, availHeight: float) -> tuple[float, float]:
                return availWidth, self._height

        previous = renderer._ROTATED_TABLE_MEASURE
        renderer._ROTATED_TABLE_MEASURE = 688.0
        self.addCleanup(setattr, renderer, "_ROTATED_TABLE_MEASURE", previous)

        class _Report:
            def __init__(self) -> None:
                self.warnings: list[str] = []

        report = _Report()
        # 一列：图 600pt + 文字 600pt（文字远非图内容，缩图也放不下）。
        over = [[_FakeImage(600.0), _FakeText(600.0)], [_FakeImage(100.0)]]
        self.assertFalse(
            renderer._fit_side_by_side_to_frame(over, [200.0, 200.0], report, _FakeImage)
        )
        self.assertTrue(any("one above another" in warning for warning in report.warnings))
        # 放得下时不动任何图、也不记 warning。
        fits = [[_FakeImage(300.0)], [_FakeImage(200.0)]]
        fits_report = _Report()
        self.assertTrue(
            renderer._fit_side_by_side_to_frame(fits, [200.0, 200.0], fits_report, _FakeImage)
        )
        self.assertEqual(fits_report.warnings, [])
        self.assertEqual(fits[0][0].drawHeight, 300.0)


class ExampleBoxWidthTests(unittest.TestCase):
    """示例线框内容宽模型 + 通栏对象按容器宽排布（2026-09-07 穿框根因修复）。

    回归（GB_T_20001.5-2017 附录A 示例1）：表/图此前按正文固定 455pt 排布，
    而示例线框（_example_box）单元格内容可用宽只有
    doc_width - 2×Frame padding(6) - 2×框 padding(10) ≈ 421.5pt，
    455pt 的表格右侧穿出黑色框线。修复后线框内内容按框内容宽排布。
    """

    @staticmethod
    def _render(nodes: list[dict], box_inner_width: float | None, content_width: float = 455.0) -> list:
        from pathlib import Path

        from reportlab.lib import colors
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

        styles = {}
        for name in ("example-label", "example-title", "example-content", "body",
                     "body-flush", "caption", "table-unit", "table", "table-body",
                     "note", "list", "list-sub", "formula", "section", "subclause",
                     "clause", "front"):
            styles[name] = ParagraphStyle(name, fontName="Helvetica", fontSize=10)
        from leleby_ssir.pdf_renderer import PDFRenderReport

        report = PDFRenderReport(
            input_file="test.pdf", output_file="test.render.pdf",
            profile_file="", profile_id="", font_file="",
        )
        story: list = []
        _append_nodes(
            story, nodes,
            registries={"tables": {"t1": TABLE_FIXTURE}, "figures": {}, "formulas": {}},
            styles=styles, font="Helvetica", report=report, asset_dir=Path("."),
            colors=colors, Table=Table, TableStyle=TableStyle, Paragraph=Paragraph,
            Spacer=Spacer, Image=Image, marker_factory=None, PageBreak=None,
            example_default="frame", content_width=content_width,
            box_inner_width=box_inner_width,
        )
        return story

    @staticmethod
    def _find_table(flowables: list) -> list:
        """Find every reportlab grid Table (colWidths set) inside a story/box."""
        from reportlab.platypus import Table as ReportlabTable

        found: list = []
        for flowable in flowables:
            widths = getattr(flowable, "_colWidths", None)
            # 只认显式列宽的表格 GRID（示例线框外框 Table 的 colWidths=[None] 不算）。
            if isinstance(flowable, ReportlabTable) and widths and all(w is not None for w in widths):
                found.append(flowable)
            cells = getattr(flowable, "_cellvalues", None)
            if cells:  # example box rows: nested grid tables live in cells
                for row in cells:
                    for cell in row:
                        if isinstance(cell, ReportlabTable) and all(w is not None for w in getattr(cell, "_colWidths", [])):
                            found.append(cell)
        return found

    def test_box_inner_width_math(self) -> None:
        # A4 - (28+22)mm = 453.5433…；reportlab Frame 默认 padding 6×2 → 线框宽
        # 441.5433…；单元格内容再减左右 10pt padding → 421.5433…。
        self.assertAlmostEqual(_example_box_inner_width(453.5433070866142), 421.5433070866142, places=6)

    def test_table_outside_box_keeps_body_measure(self) -> None:
        # 正文容器（无框）表格总宽保持 _BODY_MEASURE（455pt），不因修复收窄。
        nodes = [{
            "nodeType": "section", "number": "1", "title": "范围",
            "exampleContent": False, "contentElements": [
                {"presentationType": "paragraph", "textContent": "本文件规定了…"},
                {"presentationType": "table", "tableRef": "t1"},
            ], "children": [],
        }]
        story = self._render(nodes, box_inner_width=None)
        grids = self._find_table(story)
        self.assertEqual(len(grids), 1)
        self.assertAlmostEqual(sum(grids[0]._colWidths), 455.0, delta=1e-3)

    def test_table_inside_example_box_uses_box_inner_width(self) -> None:
        # 线框内表格总宽 = 线框内容宽（421.54），不再按 455 穿出右侧黑框线。
        nodes = [
            {"nodeType": "documentBlock", "title": "示例 1：", "exampleContent": True,
             "children": [], "contentElements": []},
            {"nodeType": "clause", "number": "7.1", "title": "系统性能要求",
             "exampleContent": True, "children": [], "contentElements": [
                {"presentationType": "paragraph", "textContent": "系统性能应符合表1规定的要求。"},
                {"presentationType": "table", "tableRef": "t1"},
            ]},
        ]
        inner = _example_box_inner_width(453.5433070866142)
        story = self._render(nodes, box_inner_width=inner)
        # story = [示例题注 Paragraph, 线框 Table]
        self.assertEqual(len(story), 2)
        box = story[1]
        grids = self._find_table([box])
        self.assertEqual(len(grids), 1)
        self.assertAlmostEqual(sum(grids[0]._colWidths), inner, delta=1e-3)
        # 表宽 ≤ 线框内容可用宽：穿框必然消失。
        self.assertLessEqual(sum(grids[0]._colWidths), 455.0 - 2 * 10.0)


class RenderPdfExampleBoxGeometryTests(unittest.TestCase):
    """渲染几何回归（2026-09-07 穿框修复）：示例线框内表格不得穿出框线。

    夹具 tests/fixtures/render_example_box.ssir.json 由 GB_T_20001.5-2017
    附录 A 示例 1/2 区裁剪而来（三张表全部位于示例线框内，schema 校验通过）。
    断言基于 PDF 内部矢量对象（GEN-090/091 同口径，非视觉比对）：示例框是页面上最外
    的一对通高竖线（横跨版心 ≈441.5pt），框内表格竖线（≤ 框宽 − 2×10pt 示例框 padding）
    必须落在框内；框线线宽必须是 _EXAMPLE_FRAME_WIDTH —— GB/T 1.1-2020 10.4.5
    「区分示例的线框应为细实线」，与表网格线同宽（2026-09-11 用户裁定：默认细框线，
    此前 0.75pt 比表线还粗，且与表线同宽后无法再按线宽区分框/表，故按“最外一对”识别）。
    """

    def _geometry(self) -> tuple[int, int, list[str], list[float]]:
        import pymupdf

        font = Path(__file__).resolve().parents[1] / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font.is_file():
            self.skipTest("body font not available; skipping real-PDF geometry check")
        from leleby_ssir.pdf_renderer import render_pdf_file

        fixture = Path(__file__).resolve().parent / "fixtures" / "render_example_box.ssir.json"
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "render.pdf"
            render_pdf_file(str(fixture), str(out))
            doc = pymupdf.open(str(out))
            boxes = tables = 0
            violations: list[str] = []
            frame_widths: list[float] = []
            for pno in range(doc.page_count):
                verticals: list[tuple[float, float]] = []  # (x, 线宽)
                for d in doc[pno].get_drawings():
                    if d["type"] != "s" or d.get("color") != (0.0, 0.0, 0.0):
                        continue
                    rb = d["rect"]
                    if rb.height > 40:  # 竖线
                        verticals.append((rb.x0, float(d.get("width") or 0.0)))
                if len(verticals) < 2:
                    continue
                xs = [item[0] for item in verticals]
                left, right = min(xs), max(xs)
                if right - left < _BODY_MEASURE - 20:
                    continue  # 非示例框页（框横跨版心，框内表格 ≤ 框宽−20pt）
                boxes += 1
                for x, width in verticals:
                    if abs(x - left) <= 0.5 or abs(x - right) <= 0.5:
                        frame_widths.append(width)
                        continue
                    tables += 1
                    if x < left - 0.5 or x > right + 0.5:
                        violations.append(
                            f"page {pno + 1}: table vertical x={x:.1f} outside example box [{left:.1f},{right:.1f}]"
                        )
            return boxes, tables, violations, frame_widths

    def test_example_box_tables_stay_inside_thin_frame(self) -> None:
        boxes, tables, violations, frame_widths = self._geometry()
        self.assertGreater(boxes, 0, "fixture should contain example-box pages")
        self.assertGreater(tables, 0, "fixture should contain tables inside the box")
        self.assertEqual(violations, [])
        self.assertTrue(frame_widths, "fixture should contain example-box frame edges")
        self.assertEqual(frame_widths, [_EXAMPLE_FRAME_WIDTH] * len(frame_widths))


class NoteExampleLabelBoldTests(unittest.TestCase):
    """注/示例标记加黑（2026-09-11，GB/T 1.1-2020 10.4.4.1/10.4.5、附录 F 表 F.1
    序号 42/44；GBT-B10/GBT-B11 执行侧）。

    标记（"注："/"注1："/"示例："/"示例1："）用黑体字形，内容仍是宋体；标记的冒号
    属于标记（"注1："整段加黑），"示例1示出了…"这类无冒号行内引用不是标记。集成
    用例按 PDF 内部文本层字形（rawdict span 字体名）断言，不做视觉比对。
    """

    ROOT = Path(__file__).resolve().parents[1]

    def setUp(self) -> None:
        # _label_markup 的标记字体来自模块级 _LABEL_FONT（render_pdf 依 profile 设置）；
        # 本类的前两个用例校验"未配置标记字体时退回传入字体"的路径，故先钉住它。
        import leleby_ssir.pdf_renderer as renderer

        self._renderer = renderer
        self._saved_label_font = renderer._LABEL_FONT
        renderer._LABEL_FONT = ""

    def tearDown(self) -> None:
        self._renderer._LABEL_FONT = self._saved_label_font

    CANON = """---
csm-version: 1.0
document-type: standard
document-identifier: T_LABEL_001-2026
standard-number: T/LABEL 001-2026
title: 注示例标记测试文档
language: zh-CN
---
# 注示例标记测试文档
## 1 范围
本文件规定了注与示例标记的渲染测试。

> 注：标记应为黑体，内容应为宋体。

> 注1：多个注编号从 1 起。
## 2 示例
示例1：正文中的示例标记也应加黑。
示例1示出了行内引用形态。
注意：此处的“注意”不是注标记。
"""

    def test_label_span_split(self) -> None:
        for text, expected in (
            ("注：内容", "注："),
            ("注1：内容", "注1："),
            ("示例：内容", "示例："),
            ("示例 1：内容", "示例 1："),
            ("示例1:半角冒号", "示例1:"),
            ("  注2：前导空白不进黑体区", "注2："),
        ):
            with self.subTest(text=text):
                lead, label, rest = _note_example_label_span(text)
                self.assertEqual(label, expected)
                self.assertEqual(lead + label + rest, text)
                self.assertEqual(_note_example_label(text), expected)
        for text in ("注意：不是注标记", "示例1示出了行内引用", "注解：不是标记",
                     "见表注：不在行首", "示例内容"):
            with self.subTest(text=text):
                self.assertEqual(_note_example_label(text), "", text)

    def test_label_markup_only_wraps_the_label(self) -> None:
        self.assertEqual(
            _label_markup("注：标记应为黑体，内容应为宋体。", "WenQuanYiZenHei", 9.0),
            '<font name="WenQuanYiZenHei">注：</font>标记应为黑体，内容应为宋体。',
        )
        self.assertEqual(
            _label_markup("示例1：正文示例标记。", "WenQuanYiZenHei", 10.5),
            '<font name="WenQuanYiZenHei">示例1：</font>正文示例标记。',
        )
        # 无标记 / 无黑体字形时是 _markup 的恒等路径（不产生字体标签）。
        for text in ("注意：不是注标记。", "示例1示出了行内引用形态。"):
            with self.subTest(text=text):
                out = _label_markup(text, "WenQuanYiZenHei", 10.5)
                self.assertNotIn("<font name=", out)
                self.assertEqual(out, _markup(text, em_size=10.5))
        self.assertEqual(_label_markup("注：内容", "", 9.0), _markup("注：内容", em_size=9.0))

    def test_label_markup_covers_br_separated_lines(self) -> None:
        # 单元格多行内容（canonical 写作 <br> 分隔）：行首不等于串首，<br> 之后的
        # 注标记同样加黑（GB_T_1.1-2020 表 F.1 单元格实测）。
        marked = _mark_note_example_labels("段(可包含要求型条款) <br> 注1：表中的注的内容 <br>注2：表中的注的内容")
        self.assertEqual(marked.count("\x00HEI\x00"), 2)
        out = _label_markup("段(可包含要求型条款) <br> 注1：表中的注的内容 <br>注2：表中的注的内容", "Hei", 9.0)
        self.assertEqual(out.count('<font name="Hei">注1：</font>'), 1)
        self.assertEqual(out.count('<font name="Hei">注2：</font>'), 1)
        self.assertIn("段(可包含要求型条款)", out)

    def test_render_bolds_label_and_keeps_body_font(self) -> None:
        try:
            import pymupdf
        except ImportError:  # pragma: no cover - 环境缺 pymupdf 时跳过
            self.skipTest("pymupdf unavailable")
        font = self.ROOT / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font.is_file():
            self.skipTest("body font asset missing")
        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import render_pdf_file
        import json

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "t.canonical.md"
            source.write_text(self.CANON, encoding="utf-8")
            ssir = Path(directory) / "t.ssir.json"
            ssir.write_text(json.dumps(SSIRBuilder().build(CSMParser().read(str(source))), ensure_ascii=False), encoding="utf-8")
            target = Path(directory) / "t.pdf"
            render_pdf_file(str(ssir), str(target), toc_depth=None)
            document = pymupdf.open(str(target))
            spans: list[tuple[str, str]] = []
            for page in document:
                for block in page.get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        for span in line["spans"]:
                            spans.append((span["text"].strip(), span["font"]))
            document.close()
        labelled = [span for span in spans if span[0] in {"注：", "注1：", "示例1："}]
        self.assertTrue(labelled, spans)
        # 标记字体取 profile 的 fonts.label（黑体粗）；未配置时才退回 primary 黑体。
        profile = yaml.safe_load((self.ROOT / "config" / "rendering" / "GB_T_1.1-2020.yaml").read_text(encoding="utf-8"))
        label_font_name = str((profile.get("fonts") or {}).get("label") or "")
        for text, name in labelled:
            if label_font_name:
                self.assertEqual(name, label_font_name, f"{text!r} 未用标记字体: {name}")
            else:  # pragma: no cover - profile 未配置标记字体时的旧行为
                self.assertTrue(name.startswith("WenQuanYiZenHei"), f"{text!r} 未加黑: {name}")
        content = [span for span in spans if span[0].startswith(("标记应为黑体", "多个注编号", "正文中的示例标记"))]
        self.assertTrue(content, spans)
        for text, name in content:
            self.assertTrue(name.startswith("NotoSerifCJKsc"), f"{text!r} 内容字体被改动: {name}")
        # 反例：无冒号行内引用与"注意"都不是标记，保持内容字体、不产生黑体 run。
        for text, name in spans:
            if text.startswith("示例1示出了") or text.startswith("注意："):
                self.assertTrue(name.startswith("NotoSerifCJKsc"), f"{text!r} 被误加黑: {name}")

    def test_label_is_visibly_heavier_than_content(self) -> None:
        """标记必须**看得出**比正文重（用户报告「注：仍没有加粗」的真正判据）。

        细黑（primary 文泉驿正黑）9pt 的笔画密度与宋体正文相当（实测 0.209 vs
        0.232），换字体不换字重看不出加黑；本用例用同一字形比对——注内容
        「注：注注注注」里两侧都是「注」，标记侧墨度必须显著高于内容侧。
        """
        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        font = self.ROOT / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        label_font = self.ROOT / "config" / "rendering" / "fonts" / "NotoSansCJKsc-Bold.ttf"
        if not font.is_file() or not label_font.is_file():
            self.skipTest("font assets missing")
        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import render_pdf_file
        import json

        canon = (
            "---\n"
            "csm-version: 1.0\n"
            "document-type: standard\n"
            "document-identifier: T_LABEL_002-2026\n"
            "standard-number: T/LABEL 002-2026\n"
            "title: 标记字重测试\n"
            "language: zh-CN\n"
            "---\n\n"
            "# 标记字重测试\n\n"
            "## 1 范围\n\n"
            "> 注：注注注注注注注注\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "t.canonical.md"
            source.write_text(canon, encoding="utf-8")
            ssir = Path(directory) / "t.ssir.json"
            ssir.write_text(json.dumps(SSIRBuilder().build(CSMParser().read(str(source))), ensure_ascii=False), encoding="utf-8")
            target = Path(directory) / "t.pdf"
            render_pdf_file(str(ssir), str(target), toc_depth=None)
            document = pymupdf.open(str(target))
            glyphs: list[tuple[str, str, tuple, int]] = []
            for page in document:
                for block in page.get_text("rawdict")["blocks"]:
                    for line in block.get("lines", []):
                        for span in line["spans"]:
                            for char in span["chars"]:
                                glyphs.append((char["c"], span["font"], tuple(char["bbox"]), page.number))

            def ink(bbox: tuple, page) -> float:
                rectangle = pymupdf.Rect(bbox[:4])
                pixmap = page.get_pixmap(clip=rectangle, dpi=900, colorspace=pymupdf.csGRAY)
                samples = pixmap.samples
                return sum(1 for value in samples if value < 128) / len(samples)

            notes = [glyph for glyph in glyphs if glyph[0] == "注"]
            self.assertGreaterEqual(len(notes), 9, [glyph[0] for glyph in glyphs][:80])
            pages = {glyph[3] for glyph in notes}
            self.assertEqual(len(pages), 1, pages)
            page = document[pages.pop()]
            label_glyph = notes[0]
            content_glyphs = notes[1:9]
            self.assertIn("Noto", label_glyph[1])
            label_ink = ink(label_glyph[2], page)
            content_ink = sum(ink(glyph[2], page) for glyph in content_glyphs) / len(content_glyphs)
            document.close()
            self.assertGreater(label_ink, content_ink * 1.3, (label_ink, content_ink))


class WideTableLandscapeTests(unittest.TestCase):
    """宽表横排（GEN-103，2026-09-12；用户裁定方案 A）。

    现象（GB/T 5171.1-2014 表9）：26 列表在竖排版心下超需求，列宽分配器把末列算成
    0.6pt，reportlab 以「负可用宽」中止**整篇**渲染（04_render 为空、构建退出码 2）。
    修复两段：① 列宽下界 = 左右边距 + 一个汉字宽（不足从最宽列扣减），任何表都不再
    产出非法列宽；② 竖排必然排不下（跨行合并锁定的行组高于一页）而横排排得下时，整表
    旋转 90°（表头落订口一侧、题注随表），与源 PDF 表9 的横排同向。

    夹具 tests/fixtures/wide_table.canonical.md：表9 的 26 列 × 15 行原样（含 rowspan
    锁定行组）+ 同文档一张 3 列窄表（反例：必须保持竖排）。断言基于 PDF 内部对象
    （pymupdf 文本行 dir、网格线坐标），非视觉比对。

    判据③「竖排能否分页」按 reportlab 的**递归**分页语义复算（2026-09-17，见
    test_portrait_grid_that_can_paginate_is_not_called_unpaginatable）：只看一次
    ``split()`` 的一级片段会把长表正常分页误判成「必然排不下」。
    """

    ROOT = Path(__file__).resolve().parents[1]
    FIXTURE = ROOT / "tests" / "fixtures" / "wide_table.canonical.md"
    FONT_SIZE = 9.0
    PADDING = 4.0

    def _tables(self) -> list[dict]:
        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser

        return SSIRBuilder().build(CSMParser().read(str(self.FIXTURE)))["tables"]

    _IMG = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")

    def test_wide_table_columns_never_narrower_than_padding_and_glyph(self) -> None:
        """列宽下界（GEN-103 ①）：26 列表的每一列都容得下一个字，且总宽恒 = 版心。

        修复前该表末列 = 0.6pt（< 左右边距 8pt），reportlab 负可用宽直接中止渲染；
        下界 = 2×边距(4) + 一个汉字宽(9pt 字号 → 9pt) = 17pt。
        """
        tables = {t.get("number"): t for t in self._tables()}
        wide = tables["9"]
        self.assertEqual(wide["colCount"], 26)
        widths = _table_column_widths(wide["rows"], wide["colCount"], self.FONT_SIZE, {}, self._IMG)
        lower = 2 * self.PADDING + self.FONT_SIZE
        self.assertGreaterEqual(min(widths), lower - 1e-6, widths)
        self.assertAlmostEqual(sum(widths), _BODY_MEASURE, delta=1e-3)
        # 崩溃条件本身：任何列都不得窄于左右边距（availableWidth = 列宽 − 2×边距）
        self.assertGreater(min(widths), 2 * self.PADDING)

    def test_wide_table_rotates_with_caption_and_narrow_table_stays_upright(self) -> None:
        try:
            import pymupdf
        except ImportError:  # pragma: no cover - 环境缺 pymupdf 时跳过
            self.skipTest("pymupdf unavailable")
        font = self.ROOT / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font.is_file():
            self.skipTest("body font asset missing")
        import json
        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import render_pdf_file

        with tempfile.TemporaryDirectory() as directory:
            ssir = Path(directory) / "t.ssir.json"
            ssir.write_text(
                json.dumps(SSIRBuilder().build(CSMParser().read(str(self.FIXTURE))), ensure_ascii=False),
                encoding="utf-8",
            )
            target = Path(directory) / "t.pdf"
            render_pdf_file(str(ssir), str(target), toc_depth=None)
            document = pymupdf.open(str(target))
            rotated: dict[str, tuple] = {}
            upright: list[str] = []
            table_span = 0.0
            columns = 0
            for page in document:
                for block in page.get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        text = "".join(span["text"] for span in line["spans"]).strip()
                        if line["dir"] == (0.0, -1.0) and text in {"表9", "轴承类别", "声功率级/dB(A)"}:
                            rotated.setdefault(text, tuple(line["bbox"]))
                        elif text in {"表10", "试验方法"}:
                            upright.append(text)
                ys = [
                    drawing["rect"].y0
                    for drawing in page.get_drawings()
                    if drawing["rect"].height < 1.5 and drawing["rect"].width > 20
                ]
                if ys and "表9" in rotated and not table_span:
                    table_span = max(ys) - min(ys)
                    columns = len(set(ys)) - 1
            document.close()
        # ① 横排表：整表（含题注）旋转 90°，表头与题注都读作自下而上（与源排版同向）
        self.assertCountEqual(list(rotated), ["声功率级/dB(A)", "轴承类别", "表9"])
        caption_bbox = rotated["表9"]
        header_bbox = rotated["轴承类别"]
        self.assertLess(caption_bbox[0], header_bbox[0], (caption_bbox, header_bbox))  # 题注在表格左侧（订口一侧）
        # ② 横排后 26 列沿页面高度排布，网格总高 ≈ 版心高（竖排时只有版心宽 455pt）
        self.assertGreater(table_span, _BODY_MEASURE)
        self.assertLessEqual(table_span, 700.0)
        self.assertEqual(columns, 26)  # 26 列 → 27 条列分隔线（含表格左右外框）
        # ③ 反例：同文档的 3 列窄表保持竖排（规则不外溢）
        self.assertCountEqual(upright, ["表10", "试验方法"])

    def test_portrait_grid_that_can_paginate_is_not_called_unpaginatable(self) -> None:
        """判据③按 reportlab 的**递归**分页语义（2026-09-17，GB/T 30819-2024 表2）。

        现象：9 列 ×54 行长表（源排版竖排跨页）在 455pt 版心下 Σ列需求 585pt 超版心，
        一次 ``split()`` 得到 669pt + 741pt 两片。reportlab 的语义里「其余那一片」本来
        就可以高于一页——它会被再切一次（实测 669/627/150pt）——但旧判据只看一级片段，
        于是判定「竖排必然排不下」→ 整表旋转 90°；旋转后沿页宽方向的尺寸 = 表高 624 +
        题注 14 = 638pt > 版心宽 441.5pt，reportlab 抛 ``Splitting error(n==2)``，
        04_render 为空、构建退出码 2。

        这里用一张 80 行普通表（无跨行合并）钉住两件事：一级片段确实有高于一页的
        （旧判据据此横排），而切到不动点后每一片都在版心内（新判据不得横排）。
        """
        from reportlab.platypus import Table

        from leleby_ssir.pdf_renderer import _table_exceeds_frame

        frame_height = 688.1574803149606  # A4 高 − 上下边距 − Frame 内衬（GEN-103 横排可用宽）
        grid = Table([[f"R{i}C{j}" for j in range(4)] for i in range(80)], colWidths=[120.0] * 4)
        first_pass = [piece.wrap(_BODY_MEASURE, frame_height)[1] for piece in grid.split(_BODY_MEASURE, frame_height)]
        self.assertTrue(any(height > frame_height + 0.5 for height in first_pass), first_pass)
        self.assertFalse(_table_exceeds_frame(grid, _BODY_MEASURE, frame_height))

    def test_portrait_grid_with_row_group_over_one_page_still_rotates(self) -> None:
        """判据③的正例：跨行合并锁定的行组高于一页时，竖排**真的**无法分页。

        与 wide_table.canonical.md 表9 同形（该表 26 列 × 15 行，一次 split 后仍有
        1897.5pt 的片段且切不动），横排仍然成立。
        """
        from reportlab.platypus import Table, TableStyle

        from leleby_ssir.pdf_renderer import _table_exceeds_frame

        frame_height = 688.1574803149606
        data = [[f"C{j}" for j in range(4)]] + [[f"R{i}", f"R{i}C1", f"R{i}C2", f"{i}.0"] for i in range(80)]
        grid = Table(data, colWidths=[120.0] * 4)
        grid.setStyle(TableStyle([("SPAN", (0, 1), (0, 79))]))  # 79 行锁成一个跨行合并组
        self.assertTrue(_table_exceeds_frame(grid, _BODY_MEASURE, frame_height))


class MultiRowHeaderLandscapeTests(unittest.TestCase):
    """多行表头不得否决横排（GEN-120，2026-09-19；用户裁定「表头续排修复不得破坏

    『表过宽自动转横排』判定」）。

    现象（GB/T 5171.1-2014 表9）：GEN-114 把表头行数按首行最大 rowspan 正确识别为
    4 行（该表首行「轴承类别」rowspan=4）后，判据② 用「Σ列**软需求**（表头自然宽
    + 12pt/列）」当可行性否决线：软需求 938.5 > 横排可用宽 688.2 → 判定「旋转后排
    不下」→ 表9 由横排退回竖排（源排版为整表旋转 90°）。可行性应与竖排同口径——只
    看列下界（列数 × 17pt = 442 ≤ 688.2），软需求只是列宽分配的目标。

    夹具 tests/fixtures/wide_table.canonical.md 的表 9 与真实表 9 同形；这里把
    ``header-rows`` 由 1 改成 4（= GEN-114 回放后的实际取值）复现回归。
    """

    ROOT = Path(__file__).resolve().parents[1]
    FIXTURE = ROOT / "tests" / "fixtures" / "wide_table.canonical.md"
    FRAME = 688.1574803149606  # A4 高 − 上下边距 − Frame 内衬（GEN-103 横排可用宽）
    FONT_SIZE = 9.0
    _IMG = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")

    def _rows(self, header_rows: int) -> list[dict]:
        import tempfile as _tempfile

        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser

        text = self.FIXTURE.read_text(encoding="utf-8").replace(
            'header-rows="1"', f'header-rows="{header_rows}"', 1
        )
        with _tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "f.canonical.md"
            source.write_text(text, encoding="utf-8")
            tables = SSIRBuilder().build(CSMParser().read(str(source)))["tables"]
        return [t for t in tables if t.get("colCount") == 26][0]["rows"]

    def test_soft_demand_over_frame_is_not_a_landscape_veto(self) -> None:
        """判据②（GEN-120）：软需求可超横排可用宽，列下界排得下即应横排。

        夹具前提自证：4 行表头时 Σ软需求 > 688.2（旧判据在此否决横排），而列下界和
        26 × 17 = 442 ≤ 688.2。直接判据同时钉住另一侧：列下界都排不下（64 列 =
        1088pt）时不得横排。
        """
        from reportlab.platypus import Table

        from leleby_ssir import pdf_renderer as renderer

        rows = self._rows(4)
        self.assertEqual([i for i, row in enumerate(rows) if row.get("isHeader")], [0, 1, 2, 3])
        need, _header_min, _body_need, _content = renderer._table_column_demands(
            rows, 26, self.FONT_SIZE, {}, self._IMG
        )
        lower = 2 * renderer._TABLE_CELL_PADDING + self.FONT_SIZE
        self.assertGreater(sum(need), self.FRAME)
        self.assertLessEqual(lower * 26, self.FRAME)
        previous = renderer._ROTATED_TABLE_MEASURE
        renderer._ROTATED_TABLE_MEASURE = self.FRAME
        self.addCleanup(setattr, renderer, "_ROTATED_TABLE_MEASURE", previous)
        grid = Table([[f"C{index}" for index in range(26)]], colWidths=[_BODY_MEASURE / 26] * 26)
        portrait = [lower] * 26  # 竖排列宽全被压到下界（判据③a）
        widths = renderer._table_landscape_widths(
            rows, 26, self.FONT_SIZE, {}, self._IMG, _BODY_MEASURE, grid, portrait_widths=portrait
        )
        self.assertIsNotNone(widths)
        self.assertAlmostEqual(sum(widths), self.FRAME, delta=1e-3)
        # 列下界都排不下 → 横排也不可行，保持竖排（规则不外溢）
        self.assertIsNone(
            renderer._table_landscape_widths(
                rows, 64, self.FONT_SIZE, {}, self._IMG, _BODY_MEASURE, grid, portrait_widths=portrait
            )
        )

    def test_multi_row_header_table_still_rotates_in_rendered_pdf(self) -> None:
        """端到端：4 行表头的 26 列表在 PDF 里整体旋转 90°（题注随表、表头落订口一侧）。"""
        import json
        import tempfile as _tempfile

        try:
            import pymupdf
        except ImportError:  # pragma: no cover - 环境缺 pymupdf 时跳过
            self.skipTest("pymupdf unavailable")
        font = self.ROOT / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font.is_file():
            self.skipTest("body font asset missing")
        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import render_pdf_file

        text = self.FIXTURE.read_text(encoding="utf-8").replace(
            'header-rows="1"', 'header-rows="4"', 1
        )
        with _tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "f.canonical.md"
            source.write_text(text, encoding="utf-8")
            ssir = Path(directory) / "t.ssir.json"
            ssir.write_text(
                json.dumps(SSIRBuilder().build(CSMParser().read(str(source))), ensure_ascii=False),
                encoding="utf-8",
            )
            target = Path(directory) / "t.pdf"
            render_pdf_file(str(ssir), str(target), toc_depth=None)
            document = pymupdf.open(str(target))
            rotated: set[str] = set()
            upright: set[str] = set()
            for page in document:
                for block in page.get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        label = "".join(span["text"] for span in line["spans"]).strip()
                        if label not in {"表9", "轴承类别", "声功率级/dB(A)", "表10", "试验方法"}:
                            continue
                        if line["dir"] == (0.0, -1.0):
                            rotated.add(label)
                        else:
                            upright.add(label)
            document.close()
        self.assertCountEqual(list(rotated), ["声功率级/dB(A)", "轴承类别", "表9"])
        self.assertCountEqual(list(upright), ["表10", "试验方法"])


class ColumnWidthDataNeedFloorTests(unittest.TestCase):
    """折行代价买入不得把列饿到「数据需求」之下（GEN-121，2026-09-19，用户报告）。

    现象（GB/T 5171.1-2014 表18，夹具 tests/fixtures/table18_columns.canonical.md 同形）：
    三列「项目 / 名称 / 容差」，源版面列宽 [27.1, 198.5, 235.5]pt。分配器从每列**下界**
    （17pt）起步、只按「加宽省下的行数」买入：「名称」列的长格由 `<br>` 固定断行（源版面
    的 a)/b)/c) 分行写法）→ 加宽省不下行数 → 被饿到 158.0pt（其数据需求 184.8pt）而
    不必要折行，余量全堆到「容差」列（267.3pt > 需求 223.1pt）。起点改为
    ``max(列下界, 该列数据需求 = 80% 分位 + 边距)`` 后实测 [26.7, 188.7, 239.6]。

    只取**数据需求**作起点、不取表头底线（表头自然宽 + 12pt）：源版面的长表头本就折行排
    （GEN-110 的 GB/T 30819-2024 表4：表头长、数据短 → 起点仍按数据）。
    """

    ROOT = Path(__file__).resolve().parents[1]
    FIXTURE = ROOT / "tests" / "fixtures" / "table18_columns.canonical.md"

    def test_rendered_name_column_keeps_its_data_need(self) -> None:
        import json
        import tempfile as _tempfile

        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        font = self.ROOT / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font.is_file():
            self.skipTest("body font asset missing")
        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import render_pdf_file

        with _tempfile.TemporaryDirectory() as directory:
            ssir = Path(directory) / "t.ssir.json"
            ssir.write_text(
                json.dumps(SSIRBuilder().build(CSMParser().read(str(self.FIXTURE))), ensure_ascii=False),
                encoding="utf-8",
            )
            target = Path(directory) / "t.pdf"
            render_pdf_file(str(ssir), str(target), toc_depth=None)
            document = pymupdf.open(str(target))
            columns: list[float] = []
            for page in document:
                xs = sorted(
                    {round(d["rect"].x0, 1) for d in page.get_drawings() if 5 < d["rect"].height and d["rect"].width < 1.5}
                    | {round(d["rect"].x1, 1) for d in page.get_drawings() if 5 < d["rect"].height and d["rect"].width < 1.5}
                )
                if len(xs) == 4:
                    columns = [round(xs[i + 1] - xs[i], 1) for i in range(3)]
                    break
            document.close()
        self.assertEqual(len(columns), 3, columns)
        self.assertAlmostEqual(sum(columns), 455.0, delta=1.5)
        # 「名称」列（中列）必须达到它的数据需求（≈184.8pt），而不是被挤到 158pt 折行
        self.assertGreaterEqual(columns[1], 180.0, columns)
        # 「容差」列不得吞掉多余宽度（源版面 235.5pt，实测修复后 ≈239.6pt）
        self.assertLessEqual(columns[2], 245.0, columns)

    def test_tight_budget_still_respects_the_column_lower_bound(self) -> None:
        """Σ数据需求超版心时退回旧起点（下界起步 + 买入），列下界仍然成立。"""
        from leleby_ssir.pdf_renderer import _table_column_widths

        image_re = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
        rows = [
            {
                "rowIndex": index,
                "isHeader": index == 0,
                "cells": [
                    {"colIndex": i, "colspan": 1, "rowspan": 1, "text": text, "isHeader": index == 0}
                    for i, text in enumerate(cells)
                ],
            }
            for index, cells in enumerate([
                ["项目", "名称", "容差"],
                ["1", "效率η", "—0.15(1—η)，最多为—0.04"],
                ["2", "交流电动机的功率因数 cosφ", "—(1—cosφ)/6，最少—0.02，最多—0.05"],
            ])
        ]
        frame = 200.0  # 版心远小于三列需求之和
        widths = _table_column_widths(rows, 3, 9.0, {}, image_re, frame_width=frame)
        self.assertAlmostEqual(sum(widths), frame, delta=1e-3)
        self.assertGreaterEqual(min(widths), 2 * 4.0 + 9.0 - 1e-6, widths)


class TallWideTablePaginationTests(unittest.TestCase):
    """长宽表竖排分页（GEN-103 判据③的实例回归，2026-09-17）。

    夹具在测试内生成（9 列 × 54 行，Σ列需求 674pt：> 版心 455pt 触发①、≤ 横排可用宽
    688pt 触发②，即旧判据下必然横排的形状），复现 GB/T 30819-2024 表2/表4 在旧判据下
    ``Splitting error(n==2)`` 中止整篇渲染的缺陷。断言基于 PDF 内部对象：题注文本行
    方向为横排（``dir == (1, 0)``，未被旋转）、表头行随分页重复出现于 ≥2 页。
    """

    ROOT = Path(__file__).resolve().parents[1]
    HEADERS = ["规格代号", "传动比", "额定输出转矩N·m", "启动、停止时的允许最大输出转矩N·m",
               "瞬间允许最大输出转矩N·m", "允许最高输入转速", "润滑方式", "精度等级", "备注"]
    FRONT_MATTER = """---
csm-version: '1.0'
document-type: standard
document-identifier: T_TALL_001-2026
standard-number: T/TALL 001-2026
title: 长表分页渲染夹具
publication-date: '2026-01-01'
effective-date: '2026-02-01'
ics: '01.120'
ccs: A 00
language: zh-CN
source:
  mode: user-markdown
extraction-backend: fixture
extensions: {}
---
"""

    def _canonical(self) -> str:
        rows = [" | ".join(self.HEADERS), " | ".join(["---"] * len(self.HEADERS))]
        for i in range(54):
            rows.append(" | ".join([
                str(14 + i),
                str(50 + i * 2),
                f"{7.8 + i * 13.3:.1f}",
                f"{15.6 + i * 26.6:.1f}",
                f"{31.2 + i * 53.2:.1f}",
                str(6000 - i * 100),
                "润滑油润滑(O)" if i % 2 else "润滑脂润滑(G)",
                str(1 + i % 3),
                "—",
            ]))
        body = "| " + " |\n| ".join(rows) + " |"
        return (
            self.FRONT_MATTER
            + "\n# 长表分页渲染夹具\n\n## 1 范围\n\n本夹具规定 9 列 × 54 行长表在版心内的分页渲染行为。\n"
            + "\n## 2 长表\n\n"
            + '<!-- ssir:table id="tall-001" header-rows="1" caption-number="2" -->\n**表2**\n'
            + body
            + "\n"
        )

    def test_tall_wide_table_paginates_upright_instead_of_aborting(self) -> None:
        try:
            import pymupdf
        except ImportError:  # pragma: no cover - 环境缺 pymupdf 时跳过
            self.skipTest("pymupdf unavailable")
        font = self.ROOT / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font.is_file():
            self.skipTest("body font asset missing")
        import json

        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import _table_column_demands, render_pdf_file

        with tempfile.TemporaryDirectory() as directory:
            canonical = Path(directory) / "tall.canonical.md"
            canonical.write_text(self._canonical(), encoding="utf-8")
            document = SSIRBuilder().build(CSMParser().read(str(canonical)))
            table = document["tables"][0]
            self.assertEqual(table["colCount"], len(self.HEADERS))
            needs = _table_column_demands(
                table["rows"], table["colCount"], 9.0, {}, re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
            )[0]
            # 判据①②都成立（旧代码据此横排），唯③（能否竖排分页）是本次修复的点位。
            self.assertGreater(sum(needs), _BODY_MEASURE, sum(needs))
            ssir = Path(directory) / "tall.ssir.json"
            ssir.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
            target = Path(directory) / "tall.pdf"
            report = render_pdf_file(str(ssir), str(target), toc_depth=None)
            rendered = pymupdf.open(str(target))
            caption_dirs: set[tuple] = set()
            header_pages: set[int] = set()
            for number, page in enumerate(rendered, start=1):
                for block in page.get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        text = "".join(span["text"] for span in line["spans"]).strip()
                        if text == "表2":
                            caption_dirs.add(tuple(round(value) for value in line["dir"]))
                        if text in {"规格", "传动", "备注"}:
                            header_pages.add(number)
            rendered.close()
        # ① 题注为竖排文本（未被旋转）：旧代码在这里把整表旋转 90°
        self.assertEqual(caption_dirs, {(1, 0)}, caption_dirs)
        # ② 表头随分页重复（profile repeat-header-rows）：长表确实跨页排布，未中止
        self.assertGreaterEqual(len(header_pages), 2, header_pages)
        self.assertGreaterEqual(report.page_count, 3)


class FigureUnitLineTests(unittest.TestCase):
    """图的单位陈述行（GEN-032 / GB/T 1.1-2020 9.7.4.1，"单位为毫米"）。

    现象（2026-09-13，GB_T_1.1-2020 附录 E）：canonical 里单位陈述行是图前的独立
    段落，满页的图另起一面时它被留在**前页末**（源文件里它本应是该图页的第一行）。
    修复后单位行折进图节点并在渲染端与图同组，断言取真实 PDF 的字符/图像坐标。
    """

    ROOT = Path(__file__).resolve().parents[1]

    def _render(self, *, filler: int, unit_line: bool):
        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        from PIL import Image as PILImage
        import json

        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import render_pdf_file

        font = self.ROOT / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        label_font = self.ROOT / "config" / "rendering" / "fonts" / "NotoSansCJKsc-Bold.ttf"
        if not font.is_file() or not label_font.is_file():
            self.skipTest("font assets missing")
        directory = tempfile.mkdtemp()
        asset = Path(directory) / "e2.png"
        PILImage.new("RGB", (500, 500), (255, 255, 255)).save(asset)
        body = ["填满版心的一行说明性文字，用于把图挤到下一页。" * 2 for _ in range(filler)]
        unit = "单位为毫米\n\n" if unit_line else ""
        canon = (
            "---\n"
            "csm-version: 1.0\n"
            "document-type: standard\n"
            "document-identifier: GB_T_1.1-2020\n"
            "standard-number: GB/T 1.1—2020\n"
            "title: 标准化工作导则\n"
            "language: zh-CN\n"
            "---\n\n"
            "# 标准化工作导则\n\n"
            "## 附录 E（规范性） 文件格式\n\n"
            + "\n\n".join(body) + "\n\n"
            + unit
            + f"![图 E.2 双数页格式]({asset})\n"
        )
        source = Path(directory) / "t.canonical.md"
        source.write_text(canon, encoding="utf-8")
        ssir_path = Path(directory) / "t.ssir.json"
        ssir = SSIRBuilder().build(CSMParser().read(str(source)))
        ssir_path.write_text(json.dumps(ssir, ensure_ascii=False), encoding="utf-8")
        target = Path(directory) / "t.pdf"
        render_pdf_file(str(ssir_path), str(target), toc_depth=None)
        document = pymupdf.open(str(target))
        unit_glyphs: list[tuple[str, tuple, int]] = []
        for page in document:
            for block in page.get_text("rawdict")["blocks"]:
                for line in block.get("lines", []):
                    text = "".join(char["c"] for span in line["spans"] for char in span["chars"])
                    if "单位为毫米" in text:
                        unit_glyphs.append((text.strip(), tuple(line["bbox"]), page.number))
        images = [
            (page.number, tuple(info["bbox"]))
            for page in document
            for info in page.get_image_info()
        ]
        # 封面徽标（GBT-L02）也是图片：只取面积最大的一张（= 本测试的图 E.2 资产）。
        figure_image = max(images, key=lambda item: (item[1][2] - item[1][0]) * (item[1][3] - item[1][1]))
        result = (ssir, unit_glyphs, figure_image, document)
        return result

    def test_unit_line_is_folded_and_stays_with_the_figure(self) -> None:
        ssir, unit_glyphs, figure_image, document = self._render(filler=26, unit_line=True)
        # ① 解析层：单位行折进图节点，不再残留为段落
        self.assertEqual(ssir["figures"][0].get("unit"), "毫米")
        paragraphs = [
            element.get("textContent", "")
            for node in ssir["structuralRoot"].get("children", [])
            for element in node.get("contentElements", [])
            if element.get("presentationType") == "paragraph"
        ]
        self.assertNotIn("单位为毫米", paragraphs)
        # ② 渲染层：图确实另起了一面（不在第 1 页），单位行与图同页同组
        image_page, image_bbox = figure_image
        self.assertGreater(image_page, 0, figure_image)
        unit_pages = {page for _, _, page in unit_glyphs}
        self.assertEqual(unit_pages, {image_page}, (unit_glyphs, figure_image))
        unit_bbox = unit_glyphs[0][1]
        # ③ 位置：单位行在图上方（y 更小）且右对齐（右缘贴版心右缘；字形墨迹与版心
        # 右缘有亚字宽的空隙，取一个汉字宽的容差）
        self.assertLess(unit_bbox[3], image_bbox[1], (unit_bbox, image_bbox))
        self.assertGreater(unit_bbox[2], document[image_page].rect.width / 2 + 100, unit_bbox)
        self.assertLessEqual(abs(unit_bbox[2] - image_bbox[2]), 12, (unit_bbox, image_bbox))
        document.close()

    def test_unit_line_absent_keeps_old_layout(self) -> None:
        # 反例：canonical 没有单位行时图照旧居中渲染（规则不外溢）
        ssir, unit_glyphs, figure_image, document = self._render(filler=26, unit_line=False)
        self.assertIsNone(ssir["figures"][0].get("unit"))
        self.assertEqual(unit_glyphs, [])
        self.assertGreater(figure_image[0], 0)
        document.close()


class SubFigureCaptionTests(unittest.TestCase):
    """GBT-B06：图题注一律渲染（含并列组内的图），分图编号/分图题小五号黑体、不带「图」字。

    现象（2026-09-19，GB_T_30819-2024 4.1.8 图3）：`ssir:columns` 组内的图成员在
    ``_append_side_by_side`` 里只画图、不画题注，a)～d) 四个分图题整体不渲染——源版面里
    只有第三张图的分图题因为 MinerU 的裁剪图恰好把题注像素一起带走才"显示"出来。
    修复后并列路径按同一 GBT-B06 渲染题注；断言取真实 PDF 文本层（字形/字号/坐标）。
    """

    ROOT = Path(__file__).resolve().parents[1]

    def test_caption_text_and_style_shapes(self) -> None:
        from leleby_ssir.pdf_renderer import _figure_caption_text, _table_caption_text

        # 编号与题名之间空一个汉字（GB/T 1.1-2020 10.4.2.1）——用固定字隙哨兵（白色
        # 「中」，推进宽 = 字号），不是 ASCII 空格（旧实现五号黑体下只有 0.30 汉字，
        # 2026-09-24 用户报告）。
        self.assertEqual(
            _figure_caption_text({"number": "3", "caption": "输入端与波发生器凸轮连接方式"}),
            "图3\x00GAP\x00输入端与波发生器凸轮连接方式",
        )
        # 分图题注不带「图」字（GB/T 1.1-2020 9.7.6 只给分图编号，源版面即「a） Ⅰ型」）
        self.assertEqual(_figure_caption_text({"number": "a）", "caption": "Ⅰ型"}), "a）\x00GAP\x00Ⅰ型")
        self.assertEqual(_figure_caption_text({"number": "b)", "caption": "Ⅱ型"}), "b)\x00GAP\x00Ⅱ型")
        self.assertEqual(_figure_caption_text({"number": "E.2", "caption": "双数页格式"}), "图E.2\x00GAP\x00双数页格式")
        self.assertEqual(_figure_caption_text({"number": "", "caption": ""}), "")
        # 编号与题名缺一：按 GBT-B08 有编号就出题注行
        self.assertEqual(_figure_caption_text({"number": "7", "caption": ""}), "图7")
        # 表题注与续表题注共用同一判决（GB/T 1.1-2020 9.8.3）
        self.assertEqual(_table_caption_text({"number": "11", "caption": "检验项目和顺序"}), "表11\x00GAP\x00检验项目和顺序")
        self.assertEqual(_table_caption_text({"number": "11", "caption": ""}), "表11")
        self.assertEqual(_table_caption_text({"number": "", "caption": ""}), "")

    def test_sub_captions_render_under_their_images(self) -> None:
        try:
            import pymupdf
        except ImportError:  # pragma: no cover - 环境缺 pymupdf 时跳过
            self.skipTest("pymupdf unavailable")
        from PIL import Image as PILImage
        import json

        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import render_pdf_file

        font = self.ROOT / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font.is_file():
            self.skipTest("body font asset missing")
        directory = Path(tempfile.mkdtemp())
        assets = {}
        for name, size in (("a", (200, 400)), ("b", (220, 420)), ("c", (240, 260))):
            asset = directory / f"{name}.png"
            PILImage.new("RGB", size, (255, 255, 255)).save(asset)
            assets[name] = asset
        canon = (
            "---\n"
            "csm-version: 1.0\n"
            "document-type: standard\n"
            "document-identifier: GB_T_30819-2024\n"
            "standard-number: GB/T 30819—2024\n"
            "title: 机器人用谐波齿轮减速器\n"
            "language: zh-CN\n"
            "---\n\n"
            "# 机器人用谐波齿轮减速器\n\n"
            "## 4.1.8　连接方式\n\n"
            "输入端与波发生器凸轮连接方式可分 4 种类型，如图3a)～d) 所示。\n\n"
            "<!-- ssir:columns -->\n\n"
            f"![图 a） Ⅰ型]({assets['a']})\n\n"
            "<!-- ssir:column -->\n\n"
            f"![图 b) Ⅱ型]({assets['b']})\n\n"
            "<!-- ssir:/columns -->\n\n"
            f"![图5 甲型结构]({assets['c']})\n"
        )
        source = Path(directory) / "t.canonical.md"
        source.write_text(canon, encoding="utf-8")
        ssir = json.loads(json.dumps(SSIRBuilder().build(CSMParser().read(str(source)))))
        ssir_path = Path(directory) / "t.ssir.json"
        ssir_path.write_text(json.dumps(ssir, ensure_ascii=False), encoding="utf-8")
        target = Path(directory) / "t.pdf"
        render_pdf_file(str(ssir_path), str(target), toc_depth=None)

        document = pymupdf.open(str(target))
        spans: list[tuple[str, str, float, tuple, int]] = []
        images: dict[int, list[tuple]] = {}
        for page_number, page in enumerate(document):
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") == 1:
                    images.setdefault(page_number, []).append(tuple(round(value, 1) for value in block["bbox"]))
                    continue
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        spans.append((span["text"].strip(), span["font"], round(span["size"], 1),
                                      tuple(round(value, 1) for value in span["bbox"]), page_number))
        document.close()

        by_text = {}
        for text, name, size, bbox, page_number in spans:
            by_text.setdefault(text, (name, size, bbox, page_number))

        def caption_parts(page_number: int, label: str, title: str) -> tuple:
            """题注按「编号 + 一个字汉字字隙（白色「中」）+ 题名」拆成三个 span。

            GB/T 1.1-2020 10.4.2.1：图编号和表编号之后均应空一个汉字的间隙接排图题和
            表题——字隙绘成白色「中」（固定字隙哨兵 `\\x00GAP\\x00`），推进宽 = 字号。
            """
            page_spans = [item for item in spans if item[4] == page_number]
            index = next(
                (i for i, item in enumerate(page_spans) if item[0] == label and item[4] == page_number),
                None,
            )
            self.assertIsNotNone(index, (label, page_number, by_text))
            gap_span, title_span = page_spans[index + 1], page_spans[index + 2]
            self.assertEqual(gap_span[0], "中", (label, gap_span))
            self.assertEqual(title_span[0], title, (label, title_span))
            # 字隙宽度 = 字号（一个汉字）；编号与题名之间不留 ASCII 空格
            self.assertAlmostEqual(gap_span[3][2] - gap_span[3][0], gap_span[2], delta=0.15)
            self.assertAlmostEqual(title_span[3][0] - gap_span[3][2], 0.0, delta=0.15)
            return gap_span, title_span

        # ① 四个题注都在（修复前并列组内的图题注一条都不渲染），编号与题名之间一个字汉字
        for label, title, page_number in (("a）", "Ⅰ型", 1), ("b)", "Ⅱ型", 1)):
            _, title_span = caption_parts(page_number, label, title)
            name, size = title_span[1], title_span[2]
            # ② 分图编号/分图题小五号黑体（GBT-B06、附录F 序号38/39）
            self.assertTrue(name.startswith("WenQuanYiZenHei"), (label, name))
            self.assertEqual(size, 9.0, (label, size))
        # ③ 不通栏的图题注仍是「图N＋1 汉字＋题名」、五号黑体
        _, title_span = caption_parts(2, "图5", "甲型结构")
        self.assertTrue(title_span[1].startswith("WenQuanYiZenHei"), title_span)
        self.assertEqual(title_span[2], 10.5, title_span)
        # ④ 分图题注在**自己那张**图之下（同页、横向重叠、图上题注下）
        for label, page_number in (("a）", 1), ("b)", 1)):
            _, title_span = caption_parts(page_number, label, "Ⅰ型" if label == "a）" else "Ⅱ型")
            caption = title_span[3]
            above = [
                image for image in images.get(page_number, [])
                if image[3] <= caption[1]
                and min(image[2], caption[2]) - max(image[0], caption[0]) > 0
            ]
            self.assertTrue(above, (label, caption, images.get(page_number)))




class ContinuationTableCaptionTests(unittest.TestCase):
    """表跨页（续表）：完整表头 + 「表N 表名（续）」+ 单位陈述（GEN-114 / GEN-115）。

    用户 2026-09-19 的通用要求：「表头实际由两行组成，接续到下一页时表头只显示了 1 行
    （应完整识别表头）；接续表应显示表名并在表名后加「（续）」；应保留表头右侧的
    「单位为毫米」」。依据 GB/T 1.1-2020 9.8.3（转页接排时重复表编号、表题可选 +「（续）」）
    与 9.8.2/附录 F（单位陈述在表题之下、表框右上）。
    """

    ROOT = Path(__file__).resolve().parents[1]

    def _render(self, *, data_rows: int, unit: bool = True):
        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        import json

        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import render_pdf_file

        font = self.ROOT / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font.is_file():
            self.skipTest("font assets missing")
        directory = tempfile.mkdtemp()
        unit_attr = ' unit="毫米"' if unit else ""
        rows = [
            "| 尺寸代号 | 规格代号 |  |  |",
            "| --- | --- | --- | --- |",
            "|  | 规格甲 | 规格乙 | 规格丙 |",
        ]
        rows += [f"| $Φd_{{{index}}}$ | {index}.0 | {index + 1}.0 | {index + 2}.0 |" for index in range(1, data_rows + 1)]
        canon = (
            "---\n"
            "csm-version: 1.0\n"
            "document-type: standard\n"
            "document-identifier: GB_T_30819-2024\n"
            "standard-number: GB/T 30819—2024\n"
            "title: 机器人用谐波齿轮减速器\n"
            "language: zh-CN\n"
            "---\n\n"
            "# 机器人用谐波齿轮减速器\n\n"
            "## 4.3　结构尺寸\n\n"
            "结构尺寸见表6。\n\n"
            f'<!-- ssir:table id="t6" header-rows="2" caption-number="6"{unit_attr} -->\n'
            "**表6 CS-Ⅰ系列减速器结构尺寸表**\n"
            + "\n".join(rows)
            + "\n"
            '<!-- ssir:table-merge table="t6" row="0" column="1" rowspan="2" colspan="1" -->\n'
            '<!-- ssir:table-merge table="t6" row="0" column="2" rowspan="1" colspan="3" -->\n'
        )
        source = Path(directory) / "t.canonical.md"
        source.write_text(canon, encoding="utf-8")
        ssir = SSIRBuilder().build(CSMParser().read(str(source)))
        ssir_path = Path(directory) / "t.ssir.json"
        ssir_path.write_text(json.dumps(ssir, ensure_ascii=False), encoding="utf-8")
        target = Path(directory) / "t.pdf"
        render_pdf_file(str(ssir_path), str(target), toc_depth=None)
        document = pymupdf.open(str(target))
        pages: list[list[tuple[str, tuple, list[tuple[str, str]]]]] = []
        for page in document:
            lines: list[tuple[str, tuple, list[tuple[str, str]]]] = []
            for block in page.get_text("dict")["blocks"]:
                if block.get("type") != 0:
                    continue
                for line in block["lines"]:
                    text = "".join(span["text"] for span in line["spans"]).strip()
                    if text:
                        spans = [(span["text"], span["font"]) for span in line["spans"]]
                        lines.append((text, tuple(line["bbox"]), spans))
            pages.append(lines)
        return ssir, pages, document

    @staticmethod
    def _find(lines: list[tuple[str, tuple, list]], needle: str) -> list[tuple]:
        return [bbox for text, bbox, _ in lines if needle in text]

    def test_continuation_page_repeats_caption_unit_and_full_header(self) -> None:
        ssir, pages, document = self._render(data_rows=60)
        # ① 解析层：表头是两行（GEN-114），第 2 行也标成表头
        table = ssir["tables"][0]
        self.assertEqual([row["isHeader"] for row in table["rows"][:3]], [True, True, False])
        # ② 表跨了多页：表首页之后的每一页都是续表
        first_table_page = next(
            index for index, lines in enumerate(pages)
            if self._find(lines, "CS-Ⅰ系列减速器结构尺寸表") and not self._find(lines, "（续）")
        )
        continuation = [index for index, lines in enumerate(pages) if self._find(lines, "（续）")]
        self.assertGreater(len(continuation), 0, pages)
        self.assertEqual(continuation, list(range(first_table_page + 1, len(pages))), pages)
        for page in continuation:
            lines = pages[page]
            # 表名 +（续）
            self.assertTrue(
                any("CS-Ⅰ系列减速器结构尺寸表（续）" in line[0] for line in lines),
                (page, lines),
            )
            # 单位为毫米保留在续页，且只有一次（不重复堆叠）
            unit = self._find(lines, "单位为毫米")
            self.assertEqual(len(unit), 1, (page, lines))
            # 完整表头（两行）都在续页重复：第 1 行「尺寸代号/规格代号」+ 第 2 行「规格甲…」
            for label in ("尺寸代号", "规格代号", "规格甲", "规格乙", "规格丙"):
                self.assertTrue(self._find(lines, label), (page, label, lines))
            # 次序：表名（续） → 单位为毫米 → 表头第 1 行 → 表头第 2 行
            cap = self._find(lines, "（续）")[0]
            self.assertLess(cap[1], unit[0][1], (page, cap, unit))
            self.assertLess(unit[0][1], self._find(lines, "尺寸代号")[0][1], (page, lines))
            self.assertLess(
                self._find(lines, "尺寸代号")[0][1], self._find(lines, "规格甲")[0][1], (page, lines)
            )
            # 单位行右对齐（表框右上，GB/T 1.1-2020 表 F.1 序号 37）
            self.assertGreater(unit[0][2], document[page].rect.width / 2 + 100, (page, unit))
            # 「（续）」五号宋体、表编号与表题五号黑体（表 F.1 序号 38）
            caption_line = next(line for line in lines if "（续）" in line[0])
            fonts = {text: font for text, font in caption_line[2] if text.strip()}
            continuation_font = next(font for text, font in caption_line[2] if "（续）" in text)
            name_font = next(font for text, font in caption_line[2] if "CS-Ⅰ" in text)
            self.assertIn("NotoSerifCJKsc-Regular", continuation_font, fonts)
            self.assertNotEqual(name_font, continuation_font, fonts)
            self.assertIn("Hei", name_font, fonts)  # 黑体（标目字体）
        # ③ 表首页照旧：题注不带（续），单位行在
        first = pages[first_table_page]
        self.assertFalse(self._find(first, "（续）"), first)
        self.assertTrue(self._find(first, "CS-Ⅰ系列减速器结构尺寸表"), first)
        self.assertTrue(self._find(first, "单位为毫米"), first)
        document.close()

    def test_short_table_gets_no_continuation_rows(self) -> None:
        # 反例：表不跨页时既没有「（续）」也不会多印一行单位陈述
        _, pages, document = self._render(data_rows=3, unit=False)
        for lines in pages:
            self.assertFalse(self._find(lines, "（续）"), lines)
        self.assertEqual(sum(len(self._find(lines, "单位为毫米")) for lines in pages), 0)


class InlineMathVariableStyleTests(unittest.TestCase):

    # 上划线定位用的字面（GEN-116）：profile 的 fonts.body / fonts.italic。
    BODY_FACE = "NotoSerifSC"
    ITALIC_FACE = "NotoSerifCJKsc-Oblique"
    ROOT = Path(__file__).resolve().parents[1]

    def setUp(self) -> None:
        """显式声明希腊字形族（GEN-122）与上划线定位字面（GEN-116），用例不依赖执行顺序。"""
        from leleby_ssir import pdf_renderer as _renderer

        previous = (
            _renderer._GREEK_FONT, _renderer._GREEK_ITALIC_FONT,
            _renderer._MATH_BODY_FACE, _renderer._MATH_ITALIC_FACE,
        )
        _renderer._GREEK_FONT, _renderer._GREEK_ITALIC_FONT = "LiberationSerif", "LiberationSerif-Italic"
        _renderer._MATH_BODY_FACE, _renderer._MATH_ITALIC_FACE = self.BODY_FACE, self.ITALIC_FACE
        for name, value in zip(
            ("_GREEK_FONT", "_GREEK_ITALIC_FONT", "_MATH_BODY_FACE", "_MATH_ITALIC_FACE"), previous
        ):
            self.addCleanup(setattr, _renderer, name, value)
        self._register_faces()

    def _register_faces(self) -> None:
        """登记上划线用到的真实字形资产：短横线高度取自**字形墨迹**，缺资产无法断言。"""
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        faces = {
            self.BODY_FACE: "NotoSerifCJKsc-Regular.ttf",
            self.ITALIC_FACE: "NotoSerifCJKsc-Oblique.ttf",
            "LiberationSerif": "LiberationSerif-Regular.ttf",
            "LiberationSerif-Italic": "LiberationSerif-Italic.ttf",
        }
        for name, filename in faces.items():
            path = self.ROOT / "config" / "rendering" / "fonts" / filename
            if not path.is_file():
                self.skipTest(f"font asset missing: {path}")
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(path), subfontIndex=0))

    r"""行内 math 的变量斜体与上划线（GEN-116；GB/T 1.1-2020 10.4.6、GBT-B12/GBT-X06）。

    现象（2026-09-19 用户报告，二轮）：「6.4 的公式下 $ 之间的 \overline 短横线很短、和字母粘连」
    「5171.1 A.2 的 \overline 没有任何效果」。根因：一轮用**字体的组合上划线 U+0304** 画短横线，
    而该字形属于 CJK em 框（ink 0.268em 宽、纵向 0.668–0.717em，advance 0），与被覆盖字母
    无关——η/n 悬空且只有半个字母宽，P/T/X 正好压进字母顶衬线（实测 5171.1 的 X̄ 整条埋在 X
    的顶衬线里，视觉上「没有效果」）。源版面实测（GB_T_30819-2024 p26 的 6.4 式中、p26 的 n̄：
    矢量线，厚 0.558pt、长 4.98pt = 字母推进宽、位于字母墨迹上方 0.19em；GB_T_5171.1-2014
    p27 的 X̄ 同为字母墨迹上方 0.18em）→ 改为 reportlab 的 **矢量线** `<u offset=…>`，
    高度 = 被覆盖字符在**其实际字面**里的墨迹高度 + 0.19em。
    """

    def test_overlined_symbol_becomes_a_vector_bar(self) -> None:
        out = _markup(r"$ \overline{η}$ ─ 传动效率；")
        self.assertEqual(
            out,
            '<u offset="0.661*f" width="0.056*f">'
            '<i><font name="LiberationSerif-Italic">η</font></i></u> ─ 传动效率；',
        )

    def test_nested_overline_form_is_not_lost(self) -> None:
        # MinerU 的 raw 写 `\overline { { \eta } }`：旧拍平把它整条拍成空串
        # （`_latex_expand_nested` 先拆命令、`\eta` 又被当未知命令丢弃）。
        self.assertEqual(
            _markup(r"$ \overline { { \eta } }$ ─ 传动效率；"),
            '<u offset="0.661*f" width="0.056*f">'
            '<i><font name="LiberationSerif-Italic">η</font></i></u> ─ 传动效率；',
        )

    def test_overline_height_comes_from_the_letter_glyph(self) -> None:
        """高度按被覆盖字符的**字形墨迹**：拉丁与 CJK 字族的同一字母差 0.7pt 以上。"""
        from leleby_ssir import pdf_renderer as _renderer

        self.assertAlmostEqual(_renderer._face_ink_em("LiberationSerif-Italic", "η"), 0.471, places=3)
        self.assertAlmostEqual(_renderer._face_ink_em("NotoSerifCJKsc-Oblique", "X"), 0.728, places=3)
        # 大写与 x 高字母各按自己的墨迹（源版面同为相对量：0.849em / 0.638em）
        self.assertLess(
            _renderer._face_ink_em("NotoSerifCJKsc-Oblique", "n"),
            _renderer._face_ink_em("NotoSerifCJKsc-Oblique", "P"),
        )
        self.assertIsNone(_renderer._face_ink_em("NoSuchFace", "X"))   # 取不到 → 调用方兜底

    def test_variables_italic_scripts_upright(self) -> None:
        # 角标字隙（GEN-140）：K 在机斜字面的下带墨迹超伸 0.009em（即内下勾），
        # 其余字母下带无超伸 → 只留固定 \scriptspace。
        self.assertEqual(_markup(r"$K_{T}$"), f'<i>K</i>{_script_gap(overhang=0.009)}<sub>T</sub>')
        self.assertEqual(_markup(r"$P_{N}$"), f"<i>P</i>{_SCRIPT_GAP_105}<sub>N</sub>")
        # 上划线只压基字：下标留在 `<u>` 之外
        self.assertEqual(_markup(r"$ \overline{P}_{1}$"), f'<u offset="0.918*f" width="0.056*f"><i>P</i></u>{_SCRIPT_GAP_105}<sub>1</sub>')
        self.assertEqual(_markup(r"$\Phi d_{1}$"), f'<i><font name="LiberationSerif-Italic">Φ</font>d</i>{_SCRIPT_GAP_105}<sub>1</sub>')
        self.assertEqual(_markup(r"$i$ ─ 传动比。"), "<i>i</i> ─ 传动比。")

    def test_units_operators_and_footnote_markers_stay_upright(self) -> None:
        gap = _SCRIPT_GAP_105
        self.assertEqual(_markup(r"$\mathrm{kPa}$"), "kPa")
        self.assertEqual(_markup(r"$100\mathrm{M}\Omega$"), '100<font size="2.625" color="white">中</font>M<font name="LiberationSerif">Ω</font>')
        self.assertEqual(_markup(r"$m^{2}$"), f"m{gap}<super>2</super>")          # 单位幂：基字正体
        self.assertEqual(_markup(r"$10^{-3}$"), f"10{gap}<super>−3</super>")
        self.assertEqual(_markup(r"$\Delta t$"), '<font name="LiberationSerif">Δ</font><i>t</i>')                # 算子正体、变量斜体
        self.assertEqual(_markup(r"$^{a}$"), "<super>a</super>")             # 表脚注标记：无基字 → 不打字隙
        self.assertEqual(_markup(r"$T _ { \mathrm { n } } / 2$"), f"<i>T</i>{gap}<sub>n</sub>/2")
        # 不带花括号的单字符下标（MinerU 表格单元格常见写法）：旧码把 `_` 当普通字符
        # 保留（拍出 "T_P"），下标语义丢失、字母连成一段被整体当量符号。
        self.assertEqual(_markup(r"$T_P$"), f"<i>T</i>{gap}<sub>P</sub>")
        self.assertEqual(_markup(r"$2U_N$"), f"2<i>U</i>{gap}<sub>N</sub>")

    def test_prime_command_keeps_the_apostrophe(self) -> None:
        """GEN-141：`^{\\prime}`（MinerU 拍出的数学撇号）拍平后不得丢字，且基字仍斜体。

        GB/T 10401-2023 的 K′_Ti、T′_i 在 raw 里就是 `$K_{Ti}^{\\prime}$`；旧码把
        `\\prime` 当未知命令删掉 → 上标组为空、渲染端印不出撇号（canonical 里人工写成
        `K'` 才绕开）。撇号不是幂：GEN-116 的「单字母基字紧跟上标 → 正体」例外不适用。
        """
        packed = _latex_to_text(r"K_{Ti}^{\prime}")
        self.assertNotIn("prime", packed)
        # 走真实行内 math 通道（`$…$`）：量符号 K 斜体，撇号是上标组内的 ′。
        self.assertEqual(
            _markup(r"$K_{Ti}^{\prime}$"),
            f'<i>K</i>{_script_gap(overhang=0.009)}<sub>Ti</sub>{_SCRIPT_GAP_105}<super>′</super>',
        )
        # 幂次与单位不受影响
        self.assertEqual(_markup(_latex_to_text(r"m^{2}")), f"m{_SCRIPT_GAP_105}<super>2</super>")

    def test_real_pdf_symbols_are_italic_with_the_bar(self) -> None:
        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        import json

        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import render_pdf_file

        oblique = self.ROOT / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Oblique.ttf"
        body = self.ROOT / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not oblique.is_file() or not body.is_file():
            self.skipTest("font assets missing")
        directory = tempfile.mkdtemp()
        canon = (
            "---\n"
            "csm-version: 1.0\n"
            "document-type: standard\n"
            "document-identifier: GB_T_30819-2024\n"
            "standard-number: GB/T 30819—2024\n"
            "title: 机器人用谐波齿轮减速器\n"
            "language: zh-CN\n"
            "---\n\n"
            "# 机器人用谐波齿轮减速器\n\n"
            "## 6.4　传动效率\n\n"
            "式中：\n\n"
            "$ \\overline{η}$ ─ 传动效率；\n\n"
            "$ \\overline{P}_{1}$ ─ 输入端功率算术平均值，单位为千瓦（kW）；\n"
        )
        source = Path(directory) / "t.canonical.md"
        source.write_text(canon, encoding="utf-8")
        ssir_path = Path(directory) / "t.ssir.json"
        ssir_path.write_text(json.dumps(SSIRBuilder().build(CSMParser().read(str(source))), ensure_ascii=False), encoding="utf-8")
        target = Path(directory) / "t.pdf"
        render_pdf_file(str(ssir_path), str(target), toc_depth=None)
        document = pymupdf.open(str(target))
        spans = [
            (span["text"], span["font"], round(span["size"], 1), span["bbox"], span["origin"][1])
            for page in document
            for block in page.get_text("dict")["blocks"] if block.get("type") == 0
            for line in block["lines"]
            for span in line["spans"]
        ]
        # 短横线是**矢量线**（不再输出 U+0304 字符）：取页面里的横线对象。
        bars = [
            drawing["rect"]
            for page in document
            for drawing in page.get_drawings()
            if (drawing.get("width") or 0) > 0.2 and abs(drawing["rect"].y0 - drawing["rect"].y1) < 0.5
        ]
        text_layer = "".join(page.get_text() for page in document)
        document.close()
        eta = [index for index, (text, _, *_) in enumerate(spans) if "η" in text]
        self.assertTrue(eta, spans[:12])
        text, font, size, bbox, baseline = spans[eta[0]]
        # 量符号斜体：拉丁字母用 GEN-108 机斜字族；希腊字母用拉丁斜体字形（GEN-122）
        self.assertTrue("Oblique" in font or "Italic" in font, spans[:12])
        self.assertEqual(size, 10.5)
        self.assertNotIn("\u0304", text_layer)          # 不再用组合上划线冒充短横线
        # 横线覆盖整个量符号（宽度 = 该字形推进宽）、位于字母墨迹上方 0.19em：
        # η 在拉丁斜体字面里墨迹高 0.471em → 短横线 0.661em = 6.94pt。
        bar = next(
            (rect for rect in bars if abs(rect.x0 - bbox[0]) < 0.5 and abs(rect.x1 - bbox[2]) < 0.5),
            None,
        )
        self.assertIsNotNone(bar, [tuple(round(v, 2) for v in r) for r in bars])
        self.assertAlmostEqual(baseline - bar.y0, 0.661 * 10.5, delta=0.2)
        power = [index for index, (text, *_) in enumerate(spans) if text.strip().startswith("P")]
        self.assertTrue(power, spans[:12])
        _, _, _, power_bbox, power_baseline = spans[power[0]]
        power_bar = next(
            (rect for rect in bars if abs(rect.x0 - power_bbox[0]) < 0.5 and abs(rect.x1 - power_bbox[2]) < 0.5),
            None,
        )
        self.assertIsNotNone(power_bar, [tuple(round(v, 2) for v in r) for r in bars])
        # P 是 cap 字母（墨迹 0.728em）→ 短横线更高，且不压进字母顶（源版面同为相对量）
        self.assertAlmostEqual(power_baseline - power_bar.y0, 0.918 * 10.5, delta=0.2)
        subscript = [span for span in spans[power[0]:power[0] + 4] if "Oblique" not in span[1]]
        self.assertTrue(any(text == "1" for text, *_ in subscript), spans[power[0]:power[0] + 4])

    def test_only_the_overlined_symbol_gets_a_bar(self) -> None:
        """同一行里未加 `\\overline` 的同名符号不得被连成一条横线（reportlab us_lines 分组）。"""
        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        import json

        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import render_pdf_file

        directory = tempfile.mkdtemp()
        canon = (
            "---\n"
            "csm-version: 1.0\n"
            "document-type: standard\n"
            "document-identifier: GB_T_10401-2023\n"
            "standard-number: GB/T 10401—2023\n"
            "title: 试验方法\n"
            "language: zh-CN\n"
            "---\n\n"
            "# 试验方法\n\n"
            "## A.1　空载数据\n\n"
            "$ \\overline{I}$ 中——相应各点的电流 $I_i$ 的平均数，单位为安培（A）；\n"
        )
        source = Path(directory) / "t.canonical.md"
        source.write_text(canon, encoding="utf-8")
        ssir_path = Path(directory) / "t.ssir.json"
        ssir_path.write_text(json.dumps(SSIRBuilder().build(CSMParser().read(str(source))), ensure_ascii=False), encoding="utf-8")
        target = Path(directory) / "t.pdf"
        render_pdf_file(str(ssir_path), str(target), toc_depth=None)
        document = pymupdf.open(str(target))
        bars = [
            drawing["rect"]
            for page in document
            for drawing in page.get_drawings()
            if (drawing.get("width") or 0) > 0.2 and abs(drawing["rect"].y0 - drawing["rect"].y1) < 0.5
        ]
        line = next(
            (
                line
                for page in document
                for block in page.get_text("dict")["blocks"] if block.get("type") == 0
                for line in block["lines"]
                if "平均数" in "".join(span["text"] for span in line["spans"])
            ),
            None,
        )
        document.close()
        self.assertIsNotNone(line, "电流平均数行未渲染")
        spans = line["spans"]
        # 两个变量 I：前者带 `\overline`、后者不带（同一行、同名符号）
        eyes = [span for span in spans if span["text"] == "I"]
        self.assertEqual(len(eyes), 2, spans)

        def bars_over(span):
            return [
                rect
                for rect in bars
                if abs(rect.x0 - span["bbox"][0]) < 0.5
                and abs(rect.x1 - span["bbox"][2]) < 0.5
                and span["bbox"][1] - 12 <= rect.y0 <= span["origin"][1]
            ]

        # 短横线只压带 `\overline` 的那个 I（同名符号不得被连成一条长横线）
        self.assertEqual(len(bars_over(eyes[0])), 1, [tuple(round(v, 2) for v in r) for r in bars])
        self.assertEqual(bars_over(eyes[1]), [], [tuple(round(v, 2) for v in r) for r in bars])


if __name__ == "__main__":
    unittest.main()

class GreekLetterFaceTests(unittest.TestCase):

    def setUp(self) -> None:
        """显式声明希腊字形族（GEN-122），用例不依赖执行顺序。"""
        from leleby_ssir import pdf_renderer as _renderer

        previous = (_renderer._GREEK_FONT, _renderer._GREEK_ITALIC_FONT)
        _renderer._GREEK_FONT, _renderer._GREEK_ITALIC_FONT = "LiberationSerif", "LiberationSerif-Italic"
        self.addCleanup(setattr, _renderer, "_GREEK_FONT", previous[0])
        self.addCleanup(setattr, _renderer, "_GREEK_ITALIC_FONT", previous[1])

    """希腊字母从拉丁字族取形（GEN-122，2026-09-19，用户报告）。

    现象（GB/T 5171.1-2014 表18）：canonical 与 PDF 文本层都是小写 U+03C6，但**字形**
    看起来像大写 Φ——Noto Serif CJK 把 U+03C6 画成「圆圈 + 贯穿竖线」的全高形（实测
    y∈[-215,681]/1000 em，而 x 高只有 516）；reportlab 内置 Symbol 的 φ 也是这一形。
    源版面同格的 `cos` 用正体 E-BZ、`φ` 用**斜体拉丁** E-BX（带尾的小写 φ）。修复：
    profile 声明拉丁（Times 度量）字形族 `fonts.greek` / `fonts.greek-italic`，希腊
    字母按其所在位置换族——变量位置（`<i>…</i>`，GEN-116 的判定）用拉丁斜体，其余
    （单位 μ/Ω、算子 Δ/Σ）用正体（GBT-B12：变量斜体、其他正体）。
    """

    ROOT = Path(__file__).resolve().parents[1]
    FIXTURE = ROOT / "tests" / "fixtures" / "table18_columns.canonical.md"

    def _with_faces(self, upright: str, italic: str):
        from leleby_ssir import pdf_renderer as renderer

        previous = (renderer._GREEK_FONT, renderer._GREEK_ITALIC_FONT)
        renderer._GREEK_FONT, renderer._GREEK_ITALIC_FONT = upright, italic
        self.addCleanup(setattr, renderer, "_GREEK_FONT", previous[0])
        self.addCleanup(setattr, renderer, "_GREEK_ITALIC_FONT", previous[1])
        return renderer

    def test_plain_text_greek_uses_the_upright_latin_face(self) -> None:
        renderer = self._with_faces("LatinUpright", "LatinItalic")
        markup = renderer._markup("交流电动机的功率因数 cosφ")
        self.assertIn('<font name="LatinUpright">φ</font>', markup)

    def test_greek_in_a_variable_position_uses_the_italic_latin_face(self) -> None:
        renderer = self._with_faces("LatinUpright", "LatinItalic")
        self.assertIn('<font name="LatinItalic">φ</font>', renderer._markup(r"$\varphi$"))
        # 单位/算子位置（Ω、Δ）保持正体
        self.assertIn('<font name="LatinUpright">Ω</font>', renderer._markup("100 MΩ"))
        self.assertIn('<font name="LatinUpright">Δ</font>', renderer._markup(r"$\Delta t$"))

    def test_without_a_declared_greek_face_nothing_changes(self) -> None:
        renderer = self._with_faces("", "")
        self.assertNotIn("<font name=", renderer._markup("cosφ MΩ"))

    def test_rendered_phi_span_uses_the_latin_face(self) -> None:
        """端到端：表18 夹具里的 φ 在 PDF 里由拉丁字族绘制（修复前为 NotoSerifCJKsc-Regular）。"""
        import json
        import tempfile as _tempfile

        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import render_pdf_file

        with _tempfile.TemporaryDirectory() as directory:
            ssir = Path(directory) / "t.ssir.json"
            ssir.write_text(
                json.dumps(SSIRBuilder().build(CSMParser().read(str(self.FIXTURE))), ensure_ascii=False),
                encoding="utf-8",
            )
            target = Path(directory) / "t.pdf"
            render_pdf_file(str(ssir), str(target), toc_depth=None)
            document = pymupdf.open(str(target))
            faces = {
                span["font"]
                for page in document
                for block in page.get_text("dict")["blocks"]
                for line in block.get("lines", [])
                for span in line["spans"]
                if "φ" in span["text"]
            }
            document.close()
        self.assertEqual(faces, {"LiberationSerif"}, faces)


class AnnexHeadingBlockTests(unittest.TestCase):
    """GBT-B05（10.4.1、图 E.12、附录 F 表 F.1 序号 25—28）：附录编号、作用（规范性/
    资料性）、标题各占一行居中，三行同用五号黑体，且**紧排**（行间无额外空行）。

    现象（2026-09-19 用户报告）：渲染稿里附录主标题比正文/章标题还大，三行间距过松
    （GB_T_20001.10-2014 附录 B：三行 12/10.5/14pt、行位置差 31.7/28.7pt）。源版面
    实测（GB_T_20001.10-2014 附录 A/B、GB_T_10401-2023 附录 A—C）三行同号、编号行→
    性质行 14.2pt ≤ 正文行距 15.7pt。断言取真实 PDF 文本层（字号/字体/坐标）。
    """

    def test_annex_heading_lines_are_body_size_and_tight(self) -> None:
        try:
            import pymupdf
        except ImportError:  # pragma: no cover - 环境缺 pymupdf 时跳过
            self.skipTest("pymupdf unavailable")
        import json
        import tempfile as _tempfile

        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import render_pdf_file

        canon = (
            "---\n"
            "csm-version: 1.0\n"
            "document-type: standard\n"
            "document-identifier: GB_T_20001.10-2014\n"
            "standard-number: GB/T 20001.10—2014\n"
            "title: 产品标准编写规则\n"
            "language: zh-CN\n"
            "---\n\n"
            "# 产品标准编写规则\n\n"
            "## 1 范围\n\n"
            "本标准规定了产品标准的编写规则。\n\n"
            "## 附录 B（资料性） 包装、运输、贮存要求的编写规则\n\n"
            "### B.1 包装\n\n"
            "需要对产品的包装提出要求时，可将有关内容编入标准。\n"
        )
        with _tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "t.canonical.md"
            source.write_text(canon, encoding="utf-8")
            ssir_path = Path(directory) / "t.ssir.json"
            ssir_path.write_text(
                json.dumps(SSIRBuilder().build(CSMParser().read(str(source))), ensure_ascii=False),
                encoding="utf-8",
            )
            target = Path(directory) / "t.pdf"
            render_pdf_file(str(ssir_path), str(target), toc_depth=None)
            document = pymupdf.open(str(target))
            rows = [
                ("".join(span["text"] for span in line["spans"]).strip(), line["spans"], line["bbox"])
                for page in document
                for block in page.get_text("dict")["blocks"]
                if block.get("type") == 0
                for line in block.get("lines", [])
            ]
            document.close()

        def pick(predicate):
            for text, spans, bbox in rows:
                if predicate(text):
                    return text, spans, bbox
            self.fail(f"未找到目标行：{[text for text, _, _ in rows]}")

        _, letter_spans, letter_box = pick(lambda text: text.startswith("附") and "录" in text)
        _, status_spans, status_box = pick(lambda text: "资料性" in text)
        _, title_spans, title_box = pick(lambda text: text.startswith("包装、运输、贮存"))
        _, body_spans, _ = pick(lambda text: text.startswith("需要对产品的包装"))

        # ① 三行同用五号黑体（不得比章标题/正文更大）
        for label, spans in (("附录编号", letter_spans), ("性质", status_spans), ("标题", title_spans)):
            sizes = {round(span["size"], 1) for span in spans}
            self.assertEqual(sizes, {10.5}, (label, sizes))
            self.assertTrue(all(span["font"].startswith("WenQuanYiZenHei") for span in spans), (label, spans))
        # ② 与正文同号（GBT-B05「五号黑体」）
        self.assertEqual({round(span["size"], 1) for span in body_spans}, {10.5})
        # ③ 三行紧排：相邻行位置差 = 正文行距（18pt），无额外空行
        self.assertAlmostEqual(status_box[1] - letter_box[1], 18.0, delta=1.0)
        self.assertAlmostEqual(title_box[1] - status_box[1], 18.0, delta=1.0)
        # ④ 三行居中：水平中心一致
        centers = [round((box[0] + box[2]) / 2, 1) for box in (letter_box, status_box, title_box)]
        self.assertLess(max(centers) - min(centers), 1.0, centers)


class ScriptGapTests(unittest.TestCase):
    """角标字隙（GEN-140，docs/12 §3.89）：上标/下标/数学撇号与基字符之间的字隙。

    现象（2026-09-24 用户报告，GB_T_10401-2023 5.24.2 公式(7) 的参数解释）：「K′ 的右上
    角标渲染时离 K 太近，几乎贴到 K 的右上角与之重合」。根因：角标自基字符的**推进宽**
    起点起画，而机斜字面的拉丁字形墨迹越过推进宽（K 0.177em、I 0.152em、k 0.117em），
    「K′」两处墨迹实测重叠 0.124em（10.5pt 下 1.3pt）。正体字面同位置超伸≈0（K +0.001em），
    所以缺陷只出现在**斜体变量**之后。

    判据：字隙 = max(0, 基字符在角标垂直带内的墨迹超伸) + TeX \\scriptspace（0.05em）。
    """

    BODY_FACE = "NotoSerifCJKsc-Regular"
    ITALIC_FACE = "NotoSerifCJKsc-Oblique"
    ROOT = Path(__file__).resolve().parents[1]

    @classmethod
    def setUpClass(cls) -> None:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        for name, filename in (
            (cls.BODY_FACE, "NotoSerifCJKsc-Regular.ttf"),
            (cls.ITALIC_FACE, "NotoSerifCJKsc-Oblique.ttf"),
        ):
            path = cls.ROOT / "config" / "rendering" / "fonts" / filename
            if not path.is_file():
                raise unittest.SkipTest(f"font asset missing: {path}")
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(path), subfontIndex=0))

    def setUp(self) -> None:
        _pin_math_faces(self, body=self.BODY_FACE, italic=self.ITALIC_FACE)

    def test_overhang_metric_counts_only_ink_beyond_the_advance(self) -> None:
        """超伸量 = 字形墨迹在垂直带内的最大 x 减推进宽（取不到 → None，调用方按 0）。"""
        from leleby_ssir import pdf_renderer as _renderer

        raised, lowered = _renderer._SCRIPT_RAISED_BAND, _renderer._SCRIPT_LOWERED_BAND
        # 机斜字面（量符号）：上带（撇号/上标所在）普遍超伸——这就是「贴住」的来源
        self.assertAlmostEqual(_renderer._face_band_overhang_em(self.ITALIC_FACE, "K", raised), 0.177, places=3)
        self.assertAlmostEqual(_renderer._face_band_overhang_em(self.ITALIC_FACE, "I", raised), 0.152, places=3)
        self.assertAlmostEqual(_renderer._face_band_overhang_em(self.ITALIC_FACE, "k", raised), 0.117, places=3)
        # 下带（下标所在）：只有 K 的内下勾超伸，其余字母为负 → 取 0
        self.assertAlmostEqual(_renderer._face_band_overhang_em(self.ITALIC_FACE, "K", lowered), 0.009, places=3)
        self.assertLess(_renderer._face_band_overhang_em(self.ITALIC_FACE, "T", lowered), 0.0)
        # 正体字面：同位置≈0（数字、CJK 均不出界）——所以「10³」「要素ᵃ」不因重叠而需要它
        self.assertLess(_renderer._face_band_overhang_em(self.BODY_FACE, "K", raised), 0.0)
        self.assertLess(_renderer._face_band_overhang_em(self.BODY_FACE, "0", raised), 0.0)
        self.assertLess(_renderer._face_band_overhang_em(self.BODY_FACE, "中", raised), 0.0)
        # 取不到字面 / 字形 → None（只留固定字隙，不猜）
        self.assertIsNone(_renderer._face_band_overhang_em("NoSuchFace", "K", raised))

    def test_gap_is_scriptspace_plus_overhang(self) -> None:
        gap = _SCRIPT_GAP_105
        # 撇号作角标：0.05em 定长 + 基字符（斜体量符号）上带超伸
        self.assertEqual(_markup(r"$K'$"), f"<i>K</i>{_script_gap(overhang=0.177)}&#x27;")
        self.assertEqual(_markup(r"$T'$"), f"<i>T</i>{_script_gap(overhang=0.027)}&#x27;")
        # 下标紧跟斜体 T：T 的下带无超伸 → 只剩 \scriptspace
        self.assertEqual(_markup(r"$T_{i}$"), f"<i>T</i>{gap}<sub>i</sub>")
        # CJK 基字符（正体、无超伸）同样有定长字隙（「稍微分开一点点」按类生效）
        self.assertEqual(_markup("要素$^{a}$"), f"要素{gap}<super>a</super>")
        # 单位幂：基字按 GEN-116 走正体 → 无超伸，只有定长字隙；源的 m² 本就不贴
        self.assertEqual(_markup(r"$K^{2}$"), f"K{gap}<super>2</super>")
        self.assertEqual(_markup(r"$m^{2}$"), f"m{gap}<super>2</super>")

    def test_no_gap_without_a_base_character(self) -> None:
        gap = _SCRIPT_GAP_105
        self.assertEqual(_markup(r"$^{a}$"), "<super>a</super>")                 # 行首
        self.assertEqual(_markup(r"x$^{a}$"), f"x{gap}<super>a</super>")          # 有基字符
        self.assertEqual(_markup("x\x00BR\x00$^{a}$"), "x\x00BR\x00<super>a</super>")   # 硬换行 = 行首
        # 空角标（抽取丢字的 `^{}`）不打字隙：否则留下一段没有角标的空白
        self.assertEqual(_markup(r"$x^{}$"), "x<super></super>")
        self.assertEqual(_markup(r"$^{}$"), "<super></super>")

    def test_gap_scales_with_the_container_font_size(self) -> None:
        # 字隙随容器字号（\scriptspace 是 em 单位），不是固定点数
        self.assertEqual(
            _markup("要素$^{a}$", em_size=21),
            '要素<font size="1.05" color="white">中</font><super>a</super>',
        )

    def test_rendered_prime_clears_the_italic_base(self) -> None:
        """GB/T 10401-2023 5.24.2 的 `K′_Ti`：渲染稿里撇号前面真的多出整段字隙。"""
        try:
            import pymupdf
        except ImportError:  # pragma: no cover - 环境缺 pymupdf 时跳过
            self.skipTest("pymupdf unavailable")
        import json

        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import render_pdf_file

        canon = (
            "---\n"
            "csm-version: 1.0\n"
            "document-type: standard\n"
            "document-identifier: GB_T_10401-2023\n"
            "standard-number: GB/T 10401—2023\n"
            "title: 谐波齿轮传动装置\n"
            "language: zh-CN\n"
            "---\n\n"
            "# 谐波齿轮传动装置\n\n"
            "## 5 试验方法\n\n"
            "### 5.24 堵转转矩\n\n"
            "#### 5.24.2 试验程序\n\n"
            "式中：\n\n"
            "$K'_{Ti}$ ——堵转转矩灵敏度拟合值，单位为牛米每安培(N·m/A)；\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "t.canonical.md"
            source.write_text(canon, encoding="utf-8")
            ssir_path = Path(directory) / "t.ssir.json"
            ssir_path.write_text(
                json.dumps(SSIRBuilder().build(CSMParser().read(str(source))), ensure_ascii=False),
                encoding="utf-8",
            )
            target = Path(directory) / "t.pdf"
            render_pdf_file(str(ssir_path), str(target), toc_depth=None)
            document = pymupdf.open(str(target))
            rows = [
                line["spans"]
                for page in document
                for block in page.get_text("dict")["blocks"]
                for line in block.get("lines", [])
                if "".join(span["text"] for span in line["spans"]).startswith("K")
            ]
            document.close()
        self.assertTrue(rows, "未找到 K′_Ti 参数行")
        spans = rows[0]
        self.assertEqual([span["text"] for span in spans[:3]], ["K", "中", "'"])
        expected = 10.5 * (0.05 + 0.177)          # 定长 + K 上带超伸
        self.assertEqual(spans[1]["color"], 0xFFFFFF)                       # 字隙是白色占位字
        self.assertAlmostEqual(spans[1]["bbox"][2] - spans[1]["bbox"][0], expected, delta=0.02)
        # 撇号起点 = K 推进宽终点 + 整段字隙（修复前两者相等 → 墨迹重叠 0.124em）
        self.assertAlmostEqual(spans[2]["bbox"][0] - spans[0]["bbox"][2], expected, delta=0.02)
