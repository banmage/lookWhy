"""图/表题注「标识部分」与「文字部分」之间的**一个汉字**间隔（GB/T 1.1-2020 10.4.2.1）。

标准原文（10.4.2.1，本库 canonical `GB_T_1.1-2020` 第 1980 行）：

    图编号和表编号之后均应空一个汉字的间隙接排图题和表题。

2026-09-24 用户报告：「所有表,图的标识部分与文字部分的间隔应为1个汉字,而目前只有半个
汉字」——旧实现用 **ASCII 空格**拼接（`f"图{number} {caption}"`），五号黑体下推进宽只有
3.15pt = 0.30 汉字（实测 GB_T_10401-2023 render.pdf 表11 题注）。

判据单源：`pdf_renderer._CAPTION_LABEL_GAP`（U+3000 表意空格，CJK 字体里恰为 1em），
由 `_figure_caption_text`（通栏图题 + 分图题注）与 `_table_caption_text`（表题 +
转页续表题注）共用。canonical 侧不变（抽取原样就是半个空格/双空格/U+3000 混杂：语料里
109 处单空格、34 处双空格、1 处 U+3000）——字隙是**渲染期**按版式规则补写的，与条首编号
后的一汉字字隙（GBT-B02、`_clause_head_gap`）同层；render.md / render.html 是结构投影，
不承载版式字隙，仍按抽取原样印一个空格。
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from leleby_ssir.service import parse_csm

_HEADER = """\
---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/XYZ 011—2026"
standard-number: "Q/XYZ 011—2026"
title: "题注字隙夹具"
language: zh-CN
source:
  mode: user-markdown
  original-file-name: "fixture.md"
  provenance: none
rendering-profile: GB_T_1.1-2020
extensions:
  standard-profile: product
  profile-rules: ["GB_T_1.1-2020"]
---

# 题注字隙夹具

## 1 范围

本文档用于图/表题注一汉字字隙的回归。

**表1 检验项目**

<!-- ssir:table id="t1" header-rows="1" caption-number="1" caption="检验项目" -->

| 序号 | 项目 | 要求 |
| --- | --- | --- |
| 1 | 径向间隙 | √ |

"""


def _fixture(asset: Path) -> str:
    """夹具正文：一张有编号有表题的表格 + 一幅有编号有图题的图（资产用绝对路径）。"""
    return _HEADER + f"![图1 结构示意]({asset})\n"


class CaptionLabelGapJudgeTests(unittest.TestCase):
    """判据单源：字隙常量与两处拼接（图题 / 表题）。"""

    def test_gap_constant_is_the_one_han_character_sentinel(self) -> None:
        from leleby_ssir.pdf_renderer import _CAPTION_LABEL_GAP

        # 固定字隙哨兵：escape 后转成白色「中」，推进宽恒 = 当前字号（一个汉字）。
        # 不能退回 ASCII 空格（0.26 汉字），也不能用 U+3000（reportlab 段落解析把它
        # 归一成 ASCII 空格，实测 10.5pt 只剩 2.69pt）。
        self.assertEqual(_CAPTION_LABEL_GAP, "\x00GAP\x00")

    def test_figure_and_table_captions_use_the_gap(self) -> None:
        from leleby_ssir.pdf_renderer import _figure_caption_text, _table_caption_text

        figure = _figure_caption_text({"number": "1", "caption": "结构示意"})
        table = _table_caption_text({"number": "1", "caption": "检验项目"})
        self.assertEqual(figure, "图1\x00GAP\x00结构示意")
        self.assertEqual(table, "表1\x00GAP\x00检验项目")
        # 编号与题名之间**只能**是字隙哨兵：不得出现 ASCII 空格 / 制表符 / U+3000
        for text in (figure, table):
            self.assertIsNone(re.search(r"[\u0020\t\u3000\u00a0]", text), repr(text))
        # 编号或题名缺失时不留尾巴（GEN-033、GBT-B08）
        self.assertEqual(_table_caption_text({"number": "1", "caption": ""}), "表1")
        self.assertEqual(_figure_caption_text({"number": "1", "caption": ""}), "图1")
        self.assertEqual(_table_caption_text({"number": "", "caption": "检验项目"}), "表\x00GAP\x00检验项目")


class CaptionLabelGapRenderTests(unittest.TestCase):
    """真实 PDF 几何：字隙推进宽 = 字号（一个汉字），不是 ASCII 空格的 0.30 汉字。"""

    def _build(self, tmp: Path) -> Path:
        import json

        from PIL import Image as PILImage

        from leleby_ssir.pdf_renderer import render_pdf_file

        asset = tmp / "fig1.png"
        PILImage.new("RGB", (240, 160), (200, 200, 200)).save(asset)
        source = tmp / "fixture.md"
        source.write_text(_fixture(asset), encoding="utf-8")
        document = parse_csm(source)
        ssir_path = tmp / "doc.ssir.json"
        ssir_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        target = tmp / "doc.render.pdf"
        render_pdf_file(ssir_path, target)
        return target

    def test_pdf_draws_exactly_one_han_character_between_label_and_title(self) -> None:
        try:
            import pymupdf
        except ImportError:  # pragma: no cover - 环境缺 pymupdf 时跳过
            self.skipTest("pymupdf unavailable")
        font_asset = (
            Path(__file__).resolve().parents[1]
            / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        )
        if not font_asset.is_file():
            self.skipTest("body font asset missing")

        measured: dict[str, tuple[float, float, str]] = {}
        with tempfile.TemporaryDirectory() as tmp:
            target = self._build(Path(tmp))
            document = pymupdf.open(str(target))
            for page in document:
                for block in page.get_text("rawdict")["blocks"]:
                    if block.get("type") != 0:
                        continue
                    for line in block["lines"]:
                        chars = [char for span in line["spans"] for char in span["chars"]]
                        text = "".join(char["c"] for char in chars).strip()
                        if "……" in text:  # 目次行另有口径（10.4.7，已是 U+3000）
                            continue
                        match = re.match(r"^(表1|图1)(\S)(\S)", text)
                        if not match:
                            continue
                        label, separator = match.group(1), match.group(2)
                        size = round(line["spans"][0]["size"], 2)
                        index = len(label)
                        gap = chars[index]["bbox"][2] - chars[index]["bbox"][0]
                        measured[label] = (gap, size, separator)
            document.close()

        self.assertEqual(set(measured), {"表1", "图1"}, measured)
        for label, (gap, size, separator) in measured.items():
            # 字隙哨兵绘成白色「中」（不可见），推进宽 = 字号 = 一个汉字
            self.assertEqual(separator, "中", (label, repr(separator)))
            ratio = gap / size
            self.assertGreater(ratio, 0.95, f"{label}: 字隙 {gap:.2f}pt / {size}pt = {ratio:.2f} 汉字")
            self.assertLess(ratio, 1.05, f"{label}: 字隙 {gap:.2f}pt / {size}pt = {ratio:.2f} 汉字")
            self.assertEqual(size, 10.5, (label, size))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
