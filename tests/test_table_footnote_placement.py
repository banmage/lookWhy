"""GEN-131：表脚注排在**表框内**（表末通栏行），不是排在表格外面。

依据 GB/T 1.1-2020 10.4.2.2「表的外框线、表头的框线以及**表中的注、表脚注所在的框线**均应为
粗实线」与 10.4.4.2「表脚注应另行空两个汉字起排……置于**表的左框线**第四个汉字的位置」——
表脚注的框线属表的框线、正文在表的横向范围内。

缺陷（2026-09-23 用户报告，GB_T_1.1-2020 附录 F 表 F.1）：表脚注 a)/b) 排在表格下方、框线之外
（canonical 里 `ssir:foot:` 定义写在表格块外；渲染端把 anchorKind=tableCell 的脚注当普通段落
画在表之后）。修复：canonical 把表脚注写在表格块内（紧随表末行），三个渲染端一律把它们排成
**表末通栏行**（与表同框同框线）。
"""

from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from leleby_ssir.csm_renderer import render_csm
from leleby_ssir.html_renderer import render_html
from leleby_ssir.service import parse_csm

FIXTURE = """\
---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/XYZ 004—2026"
standard-number: "Q/XYZ 004—2026"
title: "表脚注并表夹具"
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

# 表脚注并表夹具

## 1 范围

本文档用于表脚注排版的回归。

<!-- ssir:table id="tb-foot" header-rows="1" caption-number="1" caption="检验项目" -->
**表1 检验项目**
| 序号 | 项目 | 要求 |
| --- | --- | --- |
| 1 | 径向间隙[foot:a] | √ |
| 2 | 轴向间隙[foot:b] | — |
<!--ssir:foot:a-->分装式电动机不检验。<!--ssir:/foot-->
<!--ssir:foot:b-->当有要求时进行。<!--ssir:/foot-->
"""


def _ssir() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "fixture.canonical.md"
        path.write_text(textwrap.dedent(FIXTURE), encoding="utf-8")
        return parse_csm(path)


class TableFootnoteProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = _ssir()

    def test_markdown_keeps_footnotes_as_trailing_row(self) -> None:
        markdown = render_csm(self.document).splitlines()
        last_row = next(index for index, line in enumerate(markdown) if line.startswith("| 2 "))
        following = markdown[last_row + 1]
        # 图表脚注标记 = 上标形式的裸小写字母（GB/T 1.1-2020 9.12.2，无半圆括号）——
        # markdown 表达不了上标，投影为平印字面。
        self.assertTrue(following.startswith("| a 分装式电动机不检验。<br>b 当有要求时进行。"), following)
        # 表外不得再出现脚注行（否则内容重复）。
        self.assertEqual([line for line in markdown if line.strip() == "a 分装式电动机不检验。"], [])

    def test_html_keeps_footnotes_inside_the_table(self) -> None:
        html = render_html(self.document)
        table = html[html.index('<table class="gbt-table">'):html.index("</table>")]
        self.assertIn(
            '<td class="table-note" colspan="3"><sup>a</sup> 分装式电动机不检验。<br>'
            '<sup>b</sup> 当有要求时进行。</td>',
            table,
        )

    def test_html_marks_the_footnote_reference(self) -> None:
        html = render_html(self.document)
        # 单元格引用点 = 上标裸字母（源版面 9.12.2 形态），不补右括号。
        self.assertIn("<td>径向间隙<sup>a</sup></td>", html)


class TableFootnotePdfTests(unittest.TestCase):
    """几何断言：PDF 里注文必须夹在表格框线之间（上面有最后一行数据下的框线、下面有表底框线）。"""

    def setUp(self) -> None:
        font_asset = Path(__file__).resolve().parents[1] / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font_asset.is_file():
            self.skipTest("body font asset missing")
        try:
            import pymupdf  # noqa: F401
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")

    def _render(self) -> str:
        import pymupdf

        from leleby_ssir.pdf_renderer import render_pdf_file

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical = root / "fixture.canonical.md"
            canonical.write_text(textwrap.dedent(FIXTURE), encoding="utf-8")
            ssir = parse_csm(canonical)
            ssir_path = root / "fixture.ssir.json"
            ssir_path.write_text(json.dumps(ssir, ensure_ascii=False), encoding="utf-8")
            target = root / "fixture.render.pdf"
            render_pdf_file(ssir_path, target)
            with pymupdf.open(str(target)) as document:
                return "".join(page.get_text() for page in document)

    def test_note_is_between_table_rules(self) -> None:
        import pymupdf

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical = root / "fixture.canonical.md"
            canonical.write_text(textwrap.dedent(FIXTURE), encoding="utf-8")
            ssir = parse_csm(canonical)
            ssir_path = root / "fixture.ssir.json"
            ssir_path.write_text(json.dumps(ssir, ensure_ascii=False), encoding="utf-8")
            target = root / "fixture.render.pdf"
            from leleby_ssir.pdf_renderer import render_pdf_file

            render_pdf_file(ssir_path, target)
            with pymupdf.open(str(target)) as document:
                page = next(page for page in document if "分装式电动机不检验" in page.get_text())
                note = page.search_for("分装式电动机不检验")[0]
                rules: list[tuple[float, float, float]] = []
                for drawing in page.get_drawings():
                    for item in drawing.get("items", []):
                        if item[0] == "l" and abs(item[1].y - item[2].y) < 0.9 and abs(item[1].x - item[2].x) > 60:
                            rules.append((item[1].y, min(item[1].x, item[2].x), max(item[1].x, item[2].x)))
                        elif item[0] == "re" and item[1].height < 1.5 and item[1].width > 60:
                            rules.append((item[1].y0, item[1].x0, item[1].x1))
        above = [rule for rule in rules if rule[0] <= note.y0 + 1 and note.y0 - rule[0] < 30 and rule[1] <= note.x0 and rule[2] >= note.x1]
        below = [rule for rule in rules if rule[0] >= note.y1 - 1 and rule[0] - note.y1 < 30 and rule[1] <= note.x0 and rule[2] >= note.x1]
        self.assertTrue(above, "注文上方没有表格框线（说明注文不在表框内）")
        self.assertTrue(below, "注文下方没有表格框线（表底框线没把注文包住）")

    def test_note_text_still_rendered(self) -> None:
        text = self._render()
        self.assertIn("分装式电动机不检验", text)
        self.assertIn("当有要求时进行", text)


if __name__ == "__main__":
    unittest.main()
