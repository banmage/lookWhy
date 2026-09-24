"""GEN-130：SSIR → HTML 结构投影（``04_render/<ID>.render.html``）回归夹具。

C 方案（2026-09-23 用户裁定）：markdown 子集表达不了的版式结构（示例框线、并列分栏、
合并单元格）由 HTML 投影补足；两条投影同源同判据（内容集合、顺序、式中解释组、
资产引用前缀），HTML 不做任何新的语义推断。
"""

from __future__ import annotations

import re
import textwrap
import unittest
from pathlib import Path

from leleby_ssir.csm_renderer import asset_base_for, render_csm
from leleby_ssir.html_renderer import render_html
from leleby_ssir.service import parse_csm

FIXTURE = """\
---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/XYZ 001—2026"
standard-number: "Q/XYZ 001—2026"
title: "HTML 投影夹具"
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

# HTML 投影夹具

## 1 范围

本文档用于 HTML 结构投影的回归。

<!-- ssir:box -->
###### 示例1：

<!-- ssir:columns -->
<!-- ssir:column -->
正确：
<!-- ssir:formula id="fm-a" -->
$$
v = \\frac {l}{t}
$$
式中：
<!-- ssir:formula-vars formula="fm-a" -->
$v$ —— 速度；
$l$ —— 距离。
<!-- ssir:/formula-vars -->
<!-- ssir:column -->
不正确：
<!-- ssir:/columns -->
<!-- ssir:/box -->

<!-- ssir:table id="tb-1" header-rows="1" caption-number="1" caption="网格表" -->
**表1 网格表**
| 项目 | 数值 |
| --- | --- |
| 甲[foot:a] | 1 |
| 乙 | 2 |
<!--ssir:foot:a-->表脚注内容。<!--ssir:/foot-->

![图 1 示意图](assets/images/demo.png)

<!-- ssir:unknown id="uk-1" type-hint="layout-fragment" -->
```text
无法归类的原始内容
```
"""


def _ssir(text: str) -> dict:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "fixture.canonical.md"
        path.write_text(textwrap.dedent(text), encoding="utf-8")
        return parse_csm(path)


class HtmlStructureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = _ssir(FIXTURE)
        self.html = render_html(self.document)

    def test_document_is_standalone_and_script_free(self) -> None:
        # 静态单文件：无脚本、无外部依赖（离线可看），样式内嵌。
        self.assertTrue(self.html.startswith("<!DOCTYPE html>"))
        self.assertIn("<style>", self.html)
        self.assertNotIn("<script", self.html)
        self.assertNotIn("http://", self.html)
        self.assertNotIn("https://", self.html)

    def test_example_box_is_a_bordered_div(self) -> None:
        # 示例框 → 仅外框线的容器（markdown 无法表达）。
        self.assertEqual(self.html.count('<div class="example-box">'), 1)
        self.assertIn(".example-box { border: 1px solid #000;", self.html)

    def test_side_by_side_columns_are_real_columns(self) -> None:
        # 并列组 → flex 两列，且列内顺序为列优先（与 markdown 投影同序）。
        self.assertEqual(self.html.count('<div class="columns cols-2">'), 1)
        self.assertEqual(self.html.count('<div class="column">'), 2)
        first_column = self.html.index("正确：")
        second_column = self.html.index("不正确：")
        self.assertLess(first_column, second_column)

    def test_explanation_items_follow_the_intro_line(self) -> None:
        # 与 markdown / PDF 同判据（GEN-126/129）：「式中：」在前，条目在后，终结符保留。
        intro = self.html.index("式中：")
        self.assertGreater(self.html.index("速度；"), intro)
        self.assertLessEqual(self.html.index("速度；"), self.html.index("距离。"))
        self.assertIn('<div class="formula-vars">', self.html)

    def test_table_is_a_real_table_with_header(self) -> None:
        # 表格 → 真 <table> + <thead>（表头行数来自 GEN-114 的 header-rows 打标）。
        self.assertEqual(self.html.count('<table class="gbt-table">'), 1)
        self.assertIn("<thead>", self.html)
        self.assertIn("<th>项目</th>", self.html)
        # 引用点 [foot:a] → 上标裸字母（GB/T 1.1-2020 9.12.2 图表脚注编号，无半圆括号）
        self.assertIn("<td>甲<sup>a</sup></td>", self.html)

    def test_figure_keeps_caption_and_asset(self) -> None:
        self.assertIn('<figure class="figure">', self.html)
        self.assertIn('src="assets/images/demo.png"', self.html)
        self.assertIn("<figcaption>图1 示意图</figcaption>", self.html)

    def test_table_footnote_lands_inside_the_table(self) -> None:
        # 表脚注在表框内（GB/T 1.1 10.4.2.2/10.4.4.2）：表末通栏行，不出现在表外。
        self.assertIn('<tr><td class="table-note" colspan="2"><sup>a</sup> 表脚注内容。</td></tr>', self.html)
        table = self.html[self.html.index('<table class="gbt-table">'):self.html.index("</table>")]
        self.assertIn("表脚注内容", table)

    def test_no_ssir_markers_or_html_comments_leak(self) -> None:
        self.assertNotIn("ssir:", self.html)
        self.assertNotIn("<!--", self.html)

    def test_render_is_deterministic(self) -> None:
        self.assertEqual(self.html, render_html(self.document))


class HtmlParityWithMarkdownTests(unittest.TestCase):
    """两条投影必须同源：同一 SSIR 的内容元素一个都不少、顺序一致。"""

    def test_same_content_elements_appear_in_both_projections(self) -> None:
        document = _ssir(FIXTURE)
        markdown = render_csm(document)
        html = render_html(document)
        for probe in ("示例1：", "正确：", "不正确：", "式中：", "$v$——速度；", "甲", "示意", "表脚注内容。"):
            self.assertIn(probe, markdown, probe)
            probe_html = probe.replace("$v$——速度；", "速度；")
            self.assertIn(probe_html, html, probe)

    def test_asset_base_prefix_applies_to_both(self) -> None:
        document = _ssir(FIXTURE)
        base = asset_base_for("/tmp/docroot/04_render/x.render.html", "/tmp/docroot")
        self.assertEqual(base, "../")
        self.assertIn("](../assets/images/demo.png)", render_csm(document, asset_base=base))
        self.assertIn('src="../assets/images/demo.png"', render_html(document, asset_base=base))


class HtmlGridTests(unittest.TestCase):
    """合并单元格：跨行/跨列合并 → rowspan/colspan；被覆盖的占位空单元不重复输出。"""

    def test_rowspan_and_placeholder_skip(self) -> None:
        document = _ssir(
            """\
            ---
            csm-version: "1.0"
            document-type: standard
            document-identifier: "Q/XYZ 002—2026"
            standard-number: "Q/XYZ 002—2026"
            title: "网格夹具"
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

            # 网格夹具

            ## 1 范围

            <!-- ssir:table id="tb-grid" header-rows="1" -->
            | 序号 | 分组 | 内容 |
            | --- | --- | --- |
            | 01 | 甲组 | 第一项 |
            | 02 |  | 第二项 |
            <!-- ssir:table-merge table="tb-grid" row="1" column="2" rowspan="2" colspan="1" -->
            """
        )
        html = render_html(document)
        self.assertIn('rowspan="2"', html)
        self.assertEqual(html.count('<td rowspan="2">甲组</td>'), 1)
        # 占位空单元不得变成一行里多出来的空格子（否则列张冠李戴）。
        rows = re.findall(r"<tr>(.*?)</tr>", html, re.S)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[2].count("<td"), 2)


class HtmlUnknownContentTests(unittest.TestCase):
    def test_unknown_is_preserved(self) -> None:
        document = _ssir(
            """\
            ---
            csm-version: "1.0"
            document-type: standard
            document-identifier: "Q/XYZ 003—2026"
            standard-number: "Q/XYZ 003—2026"
            title: "未知内容夹具"
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

            # 未知内容夹具

            ## 1 范围

            <!-- ssir:unknown id="uk-1" type-hint="layout-fragment" -->
            ```text
            原始无法归类的内容
            ```
            """
        )
        html = render_html(document)
        self.assertIn('<div class="unknown"><pre>原始无法归类的内容</pre></div>', html)


class HtmlMathTests(unittest.TestCase):
    """行内 $…$ 必须转成 HTML 标记，控制符不得留在产物里（用户 2026-09-23 报告）。"""

    def setUp(self) -> None:
        self.html = render_html(
            _ssir(
                """\
                ---
                csm-version: "1.0"
                document-type: standard
                document-identifier: "Q/XYZ 005—2026"
                standard-number: "Q/XYZ 005—2026"
                title: "数学标记夹具"
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

                # 数学标记夹具

                ## 1 范围

                本文件使用符号 $l_{1}$、$d_{ext}$ 与 $80^{+2}_{0}$ mm，而不用 $\\eta$；平均值为 $\\overline { x }$。

                <!-- ssir:formula id="fm-math" -->
                $$
                E = \\overline { x } m
                $$
                式中：
                <!-- ssir:formula-vars formula="fm-math" -->
                $E$ —— 能量；
                <!-- ssir:/formula-vars -->

                <!-- ssir:table id="tb-math" header-rows="1" caption-number="1" caption="符号" -->
                **表1 $C_{p}$符号**
                | 符号 | 含义 |
                | --- | --- |
                | $l _ { 1 }$ | 长度 |
                """
            )
        )

    def test_control_markers_are_gone(self) -> None:
        self.assertNotIn("$", self.html)

    def test_variables_become_italic(self) -> None:
        self.assertIn("<i>l</i><sub>1</sub>", self.html)          # 下标
        self.assertIn("<i>d</i><sub>ext</sub>", self.html)        # 多字下标
        self.assertIn("<i>η</i>", self.html)                      # 希腊字母变量
        self.assertIn("80<sup>+2</sup><sub>0</sub>", self.html)   # 上下标并存（与 PDF 同判据）

    def test_overline_keeps_its_own_mark(self) -> None:
        self.assertIn('<span class="overline"><i>x</i></span>', self.html)

    def test_formula_body_is_flattened_like_the_pdf(self) -> None:
        # 公式本体（无资产时的文本形态）走 PDF 同判据拍平：变量斜体、上划线自有标记，
        # 不留 LaTeX 命令噪声（`\overline` 不得原样出现）。
        self.assertIn('<span class="formula-text"><i>E</i> = <span class="overline"><i>x</i></span> <i>m</i></span>', self.html)
        self.assertNotIn("\\overline {", self.html)   # LaTeX 命令不得原样出现（CSS 规则除外）

    def test_explanation_line_keeps_symbol_markup(self) -> None:
        self.assertIn('<div class="formula-var"><i>E</i>——能量；</div>', self.html)

    def test_table_cell_math(self) -> None:
        self.assertIn("<td><i>l</i><sub>1</sub></td>", self.html)

    def test_table_caption_math(self) -> None:
        # 表题里也可能带符号（GB_T_5171.1-2014 表A.1「$C_{p}$等级评定及处理原则」）。
        self.assertIn('<div class="table-caption">表1 <i>C</i><sub>p</sub>符号</div>', self.html)


if __name__ == "__main__":
    unittest.main()
