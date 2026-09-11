import re
import tempfile
import unittest
from pathlib import Path

import yaml

# GBT-B12 数值-单位固定字隙（正文五号 10.5pt 的 1/4 汉字）：_markup 输出的白字哨兵。
_UNIT_GAP = '<font size="2.625" color="white">中</font>'

from leleby_ssir.pdf_renderer import _TABLE_NOTE_CELL_RE, _BODY_MEASURE, _EXAMPLE_FRAME_WIDTH, _append_nodes, _cell_text_natural_width, _clause_leading_number, _example_box, _example_box_inner_width, _footnote_superscripts, _heading_depth, _heading_parts, _label_markup, _latex_to_text, _list_marker, _list_marker_gap, _mark_note_example_labels, _markup, _note_example_label, _note_example_label_span, _ocr_l_one, _split_table_note_parts, _starts_new_page, _strip_pagebreaks, _table_cell_superscripts, _table_column_widths, _toc_label

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
        self.assertEqual(_markup(r"$\Delta t$——绕组温升，单位为开尔文(K)；"), f"Δt{gap}——{gap}绕组温升，单位为开尔文(K)；")
        self.assertEqual(_markup(r"$R _ { 2 }$——试验结束时的绕组电阻，单位为欧姆(Ω)；"),
                         f"R<sub>2</sub>{gap}——{gap}试验结束时的绕组电阻，单位为欧姆(Ω)；")
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
        self.assertEqual(_markup("525 μm"), f"525{gap}μm")
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
        self.assertEqual(_markup("l = 2.5×10<sup>3</sup> m"), f"l = 2.5×10<super>3</super>{gap}m")
        self.assertEqual(_markup("10<sup>3</sup>m"), f"10<super>3</super>{gap}m")
        self.assertEqual(_markup(_latex_to_text(r"$D _ { \mathrm { 1 m a x } }$")), "D<sub>1max</sub>")
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
        self.assertEqual(_list_marker("•"), "●")
        self.assertEqual(_list_marker("a)"), "a)")
        self.assertEqual(_list_marker("1)"), "1)")
        self.assertEqual(_list_marker("·"), "·")
        self.assertEqual(_list_marker("●"), "●")

    def test_table_cell_superscripts_generic_tokens(self) -> None:
        # 通用行内角标标记（docs/07 §6.7，2026-09-11 通用化，GBT-X04 执行侧）：
        #   [:sup:a] … [:/sup]  上标注解区（角标字符 + 注解文字，闭标记不渲染）
        #   [:sub:2] … [:/sub]  下标注解区
        #   [:sup:a/]           自闭合 = 空注解区（引用点）
        # 哨兵经 _markup 的 XML 转义后恢复为真实 <super>/<sub> 标签。
        def rendered(text: str) -> str:
            return _markup(_table_cell_superscripts(text))

        # 引用点：词中（20001.10 表1 表头型）与词尾
        self.assertEqual(rendered("要素[:sup:a/]的编排"), "要素<super>a</super>的编排")
        self.assertEqual(rendered("表述形式[:sup:a/]"), "表述形式<super>a</super>")
        self.assertEqual(
            rendered("程序指示[:sup:b/]\x00BR\x00追溯/证实方法[:sup:c/]"),
            "程序指示<super>b</super>\x00BR\x00追溯/证实方法<super>c</super>",
        )
        # 注解区（单条）
        self.assertEqual(
            rendered("[:sup:a]黑体表示“必备的”。[:/sup]"), "<super>a</super>黑体表示“必备的”。"
        )
        # 注解区（多注连排）：相邻两对之间自动换行，canonical 不写 <br>
        self.assertEqual(
            rendered("[:sup:a]黑体表示“必备的”。[:/sup][:sup:b]“程序指示”中的指示型条款…。[:/sup]"),
            "<super>a</super>黑体表示“必备的”。\x00BR\x00<super>b</super>“程序指示”中的指示型条款…。",
        )
        # 注解区（旧 canonical 的 <br> 分格写法在调用点先转哨兵，仍按换行处理）
        self.assertEqual(
            rendered("[:sup:a]黑体表示“必备的”。[:/sup]\x00BR\x00[:sup:b]“程序指示”中的指示型条款…。[:/sup]"),
            "<super>a</super>黑体表示“必备的”。\x00BR\x00<super>b</super>“程序指示”中的指示型条款…。",
        )
        # 注文以引号开头（GB_T_20001.6-2017 表1 实测形态）不依赖字形猜测
        self.assertEqual(
            rendered("[:sup:b]“程序指示”中的指示型条款。[:/sup]"), "<super>b</super>“程序指示”中的指示型条款。"
        )
        # 下标注解区；角标字符可为多字符（1)、†、a) 等）
        self.assertEqual(rendered("[:sub:2]注解文字。[:/sub]"), "<sub>2</sub>注解文字。")
        self.assertEqual(rendered("匝间绝缘[:sup:a)/]"), "匝间绝缘<super>a)</super>")
        # 闭标记无字面残留
        self.assertNotIn("[:", rendered("[:sup:c]追溯/证实方法中的…。[:/sup]"))
        # 旧形式（按字母成对定义，迁移期兼容）仍按同一语义渲染
        self.assertEqual(rendered("要素[:^a]的编排"), "要素<super>a</super>的编排")
        self.assertEqual(rendered("[^a]黑体表示“必备的”。[^a/]"), "<super>a</super>黑体表示“必备的”。")
        # GFM 条文脚注引用（表内）仍为 “N)”（脚注规则不变）
        self.assertEqual(rendered("见注[^1]"), "见注<super>1)</super>")

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
        self.assertEqual(rendered("要素所允许的表述形式[:sup:a/]"), "要素所允许的表述形式<super>a</super>")


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


class TableCellLineBreakTests(unittest.TestCase):
    """表单元格行结构（<br>，merge 阶段从源文本层恢复）渲染为真实换行。

    Regression (2026-08-31, GB_T_20001.6-2017 表1)：单元格 "术语和定义
    ……程序确立程序指示b追溯/证实方法……规范性附录" 被 OCR 压成单行，恢复为
    <br> 连接的多行后，_markup 必须把它转成 <br/>（不能折叠为空格），且
    行尾表注引用点（2026-09-07 起为显式 [:^b] 标记）仍触发上标。
    """

    def test_br_becomes_line_break_and_footnote_superscript_fires(self) -> None:
        cell = "术语和定义<br>……<br>程序确立<br>程序指示[:^b]<br>追溯/证实方法[:^c]<br>……<br>规范性附录"
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
        self.assertEqual(_markup(_table_cell_superscripts("1 Hz = 1 s−1")), f"1{_UNIT_GAP}Hz = 1{_UNIT_GAP}s<super>−1</super>")
        self.assertEqual(_markup(_table_cell_superscripts("1 Pa = 1 N/m2")), f"1{_UNIT_GAP}Pa = 1{_UNIT_GAP}N/m<super>2</super>")
        self.assertEqual(_markup(_table_cell_superscripts("100")), "100")
        self.assertEqual(_markup(_table_cell_superscripts("centi")), "centi")

    def test_latex_emits_sentinels_and_markup_restores_tags(self) -> None:
        # Fix F：4.2 常量行 LaTeX → 可读文本 + 上标哨兵；数字逐字空格收紧；
        # \Delta V 命令终止空格折叠（ΔV 同一量符号），单位内部拉丁乘积空格保留。
        # GBT-B12：量值以幂次收尾时（10⁻³⁴ J）单位前同样是固定字隙。
        self.assertEqual(
            _markup("$6 . 6 2 6 0 7 0 1 5 \\times 1 0 ^ { - 3 4 } \\mathrm { J } \\mathrm { s } ;$"),
            f"6.62607015×10<super>−34</super>{_UNIT_GAP}J s ;",
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


if __name__ == "__main__":
    unittest.main()
