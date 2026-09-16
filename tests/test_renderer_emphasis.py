r"""强调标记渲染（docs/07 §6.1；GEN-108）与机斜字形资产（tools/prepare_oblique_font.py）。

背景（2026-09-16 用户报告）：GB_T_20001.10-2014 表1 用 * 号定义要素的字体语义
（表注「a黑体表示"必备要素"；正体表示"规范性要素"；斜体表示"资料性要素"」），
canonical 用 CSM 强调标记表达（`***封面***`、`*目次*`、`**范围**`），渲染稿却把
星号**原样打成字面文本**。三层根因：

① 字面星号判据只看**邻接字符**（`(?<![A-Za-z0-9])\*+(?![A-Za-z0-9])`）——汉字
   不在 `[A-Za-z0-9]` 里，于是汉字内容的强调标记全部被判为字面星号；
② 旧实现只有 `**`/`*` 两条正则，没有 `***X***`（粗斜体）这种形式——即使标记未被
   误判，`**\*(.+?)\*\*` 也会把 `***X***` 拆成 `<b>*X</b>*`；
③ reportlab 的 `<b>`/`<i>` **只从已注册字族取成员**，字体未登记字族时两个标签被
   静默忽略（同 GBT-B10「reportlab cannot fake bold」）；且中文「斜体」在中文排版
   里是**机斜**（整体右倾），没有现成字形资产——必须由 `tools/prepare_oblique_font.py`
   生成真实机斜字体。

近负例（必须继续按字面星号输出）：`即 * 、 ** 、 ***`（GB_T_1.1-2020 9.12.1 条文
脚注星号）、`共*页` / `(\第#页/共\*页)`（9.7.3/9.8.4 续图续表页脚）、转义 `\*`、
未成对的孤立星号。
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

_HEADER = (
    "---\n"
    "csm-version: 1.0\n"
    "document-type: standard\n"
    "document-identifier: GB/T 20001.10-2014\n"
    "standard-number: GB/T 20001.10-2014\n"
    "title: 标准编写规则 第10部分：产品标准\n"
    "language: zh-CN\n"
    "---\n\n"
)

# 表1 的强调形态（§5 要素的起草）：粗斜体、斜体、粗体、正体四类，外加表注行
# （注解里的「黑体」「斜体」本身也带强调）与三处字面星号负例。
CANON = _HEADER + """# 标准编写规则 第10部分：产品标准

## 5 结构

<!-- ssir:table id="t1" header-rows="1" caption-number="1" caption="产品标准中要素的典型编排" -->
**表1 产品标准中要素的典型编排**
| 要素类型 | 要素$^{a}$的编排 | 要素所允许的表述形式$^{a}$ |
| --- | --- | --- |
| 资料性概述要素 | ***封面*** | ***文字*** |
|  | *目次* | *文字(自动生成的内容) * |
|  | ***前言*** | ***条文***<br>*注、脚注 * |
| 规范性一般要素 | 标准名称(见6.2) | 文字 |
|  | **范围**(见 6.3) | **条文** |
| 规范性技术要素 | **技术要求**(见6.5) | *条文、图、表、注、脚注* |
| 注：表中各类要素的前后顺序即其在标准中所呈现的具体位置。 |  |  |
| [:sup:a/]**黑体**表示“必备要素”；正体表示“规范性要素”；*斜体*表示“资料性要素”。 |  |  |
| 共*页 | 即 $^{*}$ 、 $^{**}$ 、 $^{***}$ 代替 | (第#页/共\\*页) |
"""


def _build_ssir(directory: Path) -> Path:
    from leleby_ssir.builder import SSIRBuilder
    from leleby_ssir.parser import CSMParser

    source = directory / "t.canonical.md"
    source.write_text(CANON, encoding="utf-8")
    ssir = directory / "t.ssir.json"
    ssir.write_text(
        json.dumps(SSIRBuilder().build(CSMParser().read(str(source))), ensure_ascii=False),
        encoding="utf-8",
    )
    return ssir


class EmphasisMarkupTests(unittest.TestCase):
    """`_markup` 的强调配对：汉字内容照样生效，未成对星号簇仍是字面星号。"""

    def test_han_content_emphasis_becomes_font_tags(self) -> None:
        from leleby_ssir.pdf_renderer import _markup

        self.assertEqual(_markup("***封面***"), "<b><i>封面</i></b>")
        self.assertEqual(_markup("*目次*"), "<i>目次</i>")
        self.assertEqual(_markup("**范围**(见 6.3)"), "<b>范围</b>(见 6.3)")
        self.assertEqual(_markup("*文字(自动生成的内容) *"), "<i>文字(自动生成的内容)</i>")

    def test_latin_content_emphasis_still_works(self) -> None:
        from leleby_ssir.pdf_renderer import _markup

        self.assertEqual(_markup("**bold**"), "<b>bold</b>")
        self.assertEqual(_markup("*italic*"), "<i>italic</i>")
        self.assertEqual(_markup("***both***"), "<b><i>both</i></b>")

    def test_nested_emphasis_keeps_proper_nesting(self) -> None:
        from leleby_ssir.pdf_renderer import _markup

        self.assertEqual(_markup("**甲 *乙* 丙**"), "<b>甲 <i>乙</i> 丙</b>")

    def test_ocr_space_before_the_closing_delimiter_stays_outside_the_span(self) -> None:
        from leleby_ssir.pdf_renderer import _markup

        # 抽取在闭标记前留空格（`*注、脚注 *`）时仍按强调配对，且空格不进强调区。
        self.assertEqual(_markup("**条文**<br>*注、脚注 *".replace("<br>", "\x00BR\x00")),
                         "<b>条文</b>\x00BR\x00<i>注、脚注</i>")

    def test_unpaired_star_runs_stay_literal(self) -> None:
        from leleby_ssir.pdf_renderer import _markup

        # GB_T_1.1-2020 9.12.1：条文脚注星号（行内公式拍平后是空格夹着的星号簇）。
        self.assertEqual(_markup("即 $^{*}$ 、 $^{**}$ 、 $^{***}$ 代替"),
                         "即 <super>*</super> 、 <super>**</super> 、 <super>***</super> 代替")
        # 9.7.3/9.8.4 续图续表页脚、孤立星号脚注点。
        self.assertEqual(_markup("共*页"), "共*页")
        self.assertEqual(_markup("内圆直径*"), "内圆直径*")
        self.assertEqual(_markup("2*3"), "2*3")

    def test_escaped_star_is_literal(self) -> None:
        from leleby_ssir.pdf_renderer import _markup

        self.assertEqual(_markup("(第#页/共\\*页)"), "(第#页/共*页)")
        self.assertEqual(_markup("第\\*部分："), "第*部分：")


class ObliqueFontAssetTests(unittest.TestCase):
    """机斜字符资产（GEN-108）：字形真的倾斜，且 PostScript 名与直立体不同。"""

    @staticmethod
    def _glyph(name: str, char: str):
        from fontTools.ttLib import TTFont

        path = ROOT / "config" / "rendering" / "fonts" / name
        if not path.is_file():  # pragma: no cover
            raise unittest.SkipTest(f"font asset missing: {path}")
        font = TTFont(str(path))
        cmap = font.getBestCmap()
        glyph = font["glyf"][cmap[ord(char)]]
        coordinates, _ends, _flags = glyph.getCoordinates(font["glyf"])
        return font, [(float(x), float(y)) for x, y in coordinates]

    def _shear(self, font_name: str, char: str) -> float:
        """竖笔倾斜量（dx/dy）：字形顶部 20% 与底部 20% 高度区域的墨迹中心偏移差。

        宋体笔形本身带衬线，单看一个字形的绝对斜率会掺入字形噪声（实测「目」
        直立宋体 0.11、黑体 0.00），故用**同一字形直立/机斜之差**量机斜量。
        """
        _font, points = self._glyph(font_name, char)
        ys = [y for _x, y in points]
        low, high = min(ys), max(ys)
        height = high - low
        if height <= 0:  # pragma: no cover
            raise AssertionError(f"glyph {char!r} has no height")
        top = [(x, y) for x, y in points if y >= low + 0.8 * height]
        bottom = [(x, y) for x, y in points if y <= low + 0.2 * height]
        top_x = sum(x for x, _y in top) / len(top)
        top_y = sum(y for _x, y in top) / len(top)
        bottom_x = sum(x for x, _y in bottom) / len(bottom)
        bottom_y = sum(y for _x, y in bottom) / len(bottom)
        return (top_x - bottom_x) / (top_y - bottom_y)

    def test_upright_faces_are_not_slanted(self) -> None:
        # 对照：直立字体的竖笔上下同 x（黑体笔形无衬线噪声，绝对值即可判定）。
        for char in ("目", "日", "中"):
            self.assertLess(abs(self._shear("NotoSansCJKsc-Bold.ttf", char)), 0.02, char)

    def test_oblique_faces_are_slanted_by_the_measured_angle(self) -> None:
        # 源 PDF 实测 15.8°（tan≈0.282）：机斜字体相对同形直立体恰好右倾该斜率。
        pairs = (
            ("NotoSerifCJKsc-Regular.ttf", "NotoSerifCJKsc-Oblique.ttf"),
            ("NotoSansCJKsc-Bold.ttf", "NotoSansCJKsc-BoldOblique.ttf"),
        )
        for upright, oblique in pairs:
            for char in ("目", "日", "中"):
                shear = self._shear(oblique, char) - self._shear(upright, char)
                self.assertGreater(shear, 0.2, f"{oblique} {char}")
                self.assertAlmostEqual(shear, 0.282, delta=0.05, msg=f"{oblique} {char}")

    def test_postscript_names_differ_from_the_upright_faces(self) -> None:
        # reportlab 按 face.name（name 表 ID 6）去重：机斜字体若与直立体同名，
        # 注册时被静默丢弃、复用直立体对象，PDF 文本层仍是直立体字体名。
        from fontTools.ttLib import TTFont

        names = {}
        for asset in ("NotoSerifCJKsc-Regular.ttf", "NotoSerifCJKsc-Oblique.ttf",
                      "NotoSansCJKsc-Bold.ttf", "NotoSansCJKsc-BoldOblique.ttf"):
            path = ROOT / "config" / "rendering" / "fonts" / asset
            if not path.is_file():  # pragma: no cover
                raise unittest.SkipTest(f"font asset missing: {path}")
            font = TTFont(str(path))
            names[asset] = font["name"].getDebugName(6) or ""
            if "Oblique" in asset:
                self.assertEqual(names[asset], Path(asset).stem)
                self.assertNotEqual(font["post"].italicAngle, 0.0)
        self.assertEqual(len(set(names.values())), len(names), names)


class EmphasisPdfRenderingTests(unittest.TestCase):
    """真实 PDF 文本层：强调各形式分别落到粗体/斜体/粗斜体字形，负例保持字面星号。"""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            import pymupdf  # noqa: F401
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("pymupdf unavailable")
        for asset in ("NotoSerifCJKsc-Regular.ttf", "NotoSansCJKsc-Bold.ttf",
                      "NotoSerifCJKsc-Oblique.ttf", "NotoSansCJKsc-BoldOblique.ttf"):
            if not (ROOT / "config" / "rendering" / "fonts" / asset).is_file():  # pragma: no cover
                raise unittest.SkipTest("emphasis font assets missing")
        import pymupdf

        from leleby_ssir.pdf_renderer import render_pdf_file

        cls.tempdir = tempfile.TemporaryDirectory()
        directory = Path(cls.tempdir.name)
        ssir = _build_ssir(directory)
        target = directory / "t.pdf"
        render_pdf_file(str(ssir), str(target), toc_depth=None)
        cls.document = pymupdf.open(str(target))
        cls.spans = []
        for page in cls.document:
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        cls.spans.append(span)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.document.close()
        cls.tempdir.cleanup()

    def _font_of(self, text: str) -> str:
        """包含给定文本的 span 的字体名（强调会切换字体，故 span 边界即强调边界）。

        pymupdf 把过长的 span 字体名截短（PDF 内层 `AAAAAA+NotoSansCJKsc-BoldOblique`
        是完整的，见 `page.get_fonts()`），断言处按前缀关系比较。
        """
        hits = [span for span in self.spans if text in span["text"]]
        if not hits:
            raise AssertionError(f"{text!r} not found in the rendered pages")
        return min(hits, key=lambda span: len(span["text"]))["font"]

    def assertFace(self, text: str, expected: str) -> None:
        font = self._font_of(text)
        # pymupdf 的 span 字体名截断长度随版本而变，故按「前缀关系」判定。
        self.assertEqual(font, expected[: len(font)], f"{text}: {font} != {expected}")

    def test_bold_italic_and_plain_cells_use_the_expected_faces(self) -> None:
        self.assertFace("封面", "NotoSansCJKsc-BoldOblique")
        self.assertFace("前言", "NotoSansCJKsc-BoldOblique")
        self.assertFace("目次", "NotoSerifCJKsc-Oblique")
        self.assertFace("技术要求", "NotoSansCJKsc-Bold")
        self.assertFace("范围", "NotoSansCJKsc-Bold")
        self.assertFace("标准名称", "NotoSerifCJKsc-Regular")

    def test_note_row_emphasis_and_citation_superscript(self) -> None:
        # 表注：「黑体」二字的粗体、注解里的「斜体」二字本身也是强调。
        self.assertFace("黑体", "NotoSansCJKsc-Bold")
        self.assertFace("斜体", "NotoSerifCJKsc-Oblique")
        self.assertTrue(any(span["text"].strip() == "a" and span["size"] < 9 for span in self.spans),
                        "表注引用点 a 未排成小字号上标")

    def test_literal_stars_survive_in_the_text_layer(self) -> None:
        lines = "\n".join(page.get_text() for page in self.document)
        # 负例：条文脚注星号簇（行内公式拍平后）、共*页、转义星号仍按字面星号印出。
        self.assertIn("即 * 、 ** 、 *** 代替", lines)
        self.assertEqual(lines.count("共*页"), 2, lines)  # 未成对的裸星号 + 转义 \*
        self.assertIn("(第#页/共*页)", lines)
        # 正例：强调标记本身不得残留成字面文本。
        self.assertNotIn("***封面***", lines)
        self.assertNotIn("**范围**", lines)
        self.assertNotIn("*目次*", lines)


if __name__ == "__main__":
    unittest.main()
