"""脚注标记字面（GB/T 1.1-2020 9.12.1 / 9.12.2；GEN-137）。

两族的编号方案不同，2026-09-24 用户报告 GB_T_10401-2023 表11 后定案：

- **条文脚注**（9.12.1）：编号 = 从 1 开始的阿拉伯数字，形式为「后带半圆括号」→ `1)`、`2)`；
- **图表脚注**（9.12.2）：编号 = **上标形式的小写拉丁字母**（原文举例即 `a`、`b`、`c`），
  一格多角标按源分隔符连排 `b、d`——**不带**半圆括号。

历史缺陷：渲染端对两族一律补 `)`，源版面本不存在的 `b)d)` 被写进三份投影
（render.pdf / render.md / render.html）。源版面实测（标记 span 4.66pt / 正文 8.25pt）：
GB_T_10401-2023 p20 表11「振动^{b、d}」、表尾注文行「a 分装式电动机不检验。」（裸字母 +
空格）；条文脚注相反（GB_T_1.1-2020 封面条款「文件编号^{1)}」）。

本夹具把三份投影的标记形态一并钉住（判据单源 `parser.footnote_marker_text`）。
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from leleby_ssir.csm_renderer import render_csm
from leleby_ssir.html_renderer import render_html
from leleby_ssir.parser import footnote_label_marker, footnote_marker_text
from leleby_ssir.service import parse_csm


def _visible_layer_text(document) -> str:
    """渲染 PDF 文本层里**有色**字形的文本（跳过白色占位字形）。

    白色占位字（QEM 数值-单位 1/4 字隙、GAP 术语/条号 1em 字隙、角标字隙 GEN-140）
    是排版用的不可见填充字（「中」），被抽取出来会污染文本比对——按 span 颜色滤掉。
    """
    parts: list[str] = []
    for page in document:
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    if span["color"] != 0xFFFFFF:
                        parts.append(span["text"])
    return "".join(parts)

FIXTURE = """\
---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/XYZ 009—2026"
standard-number: "Q/XYZ 009—2026"
title: "脚注标记字面夹具"
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

# 脚注标记字面夹具

## 1 范围

本文档用于脚注标记字面回归。

| 项目 | 要求 |
| --- | --- |
| 振动[foot:b、d] | 3 |
| 盐雾[foot:c] | 4 |

<!--ssir:foot:b-->分装式电动机可用部件进行检验。<!--ssir:/foot-->
<!--ssir:foot:c-->当有要求时，进行检验的项目。<!--ssir:/foot-->
<!--ssir:foot:d-->分装式电动机可随整机考核。<!--ssir:/foot-->

条文脚注见下[foot:1]。

<!--ssir:foot:1-->条文脚注排页脚。<!--ssir:/foot-->
"""


class FootnoteMarkerTextTests(unittest.TestCase):
    """标记字面判据（判据单源）：数字编号带半圆括号、字母编号原样。"""

    def test_clause_footnote_numbers_keep_the_parenthesis(self) -> None:
        for payload, expected in (("1", "1)"), ("12", "12)"), ("1、2", "1)、2)")):
            self.assertEqual(footnote_marker_text(payload), expected)

    def test_chart_footnote_letters_have_no_parenthesis(self) -> None:
        for payload, expected in (("a", "a"), ("b、d", "b、d"), ("a，c", "a，c"), ("c", "c")):
            self.assertEqual(footnote_marker_text(payload), expected)
            self.assertEqual(footnote_label_marker(payload.split("、")[0]), payload.split("、")[0])

    def test_no_fabricated_parenthesis_anywhere(self) -> None:
        self.assertNotIn(")", footnote_marker_text("b、d"))


class FootnoteMarkerProjectionTests(unittest.TestCase):
    """三份投影的标记形态（render.md 平印、render.html 上标）。"""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        source = Path(tmp.name) / "fixture.md"
        source.write_text(FIXTURE, encoding="utf-8")
        self.document = parse_csm(source)

    def test_markdown_prints_the_bare_letters(self) -> None:
        markdown = render_csm(self.document)
        self.assertIn("| 振动b、d | 3 |", markdown)
        self.assertIn("| 盐雾c | 4 |", markdown)
        # 注文行：裸字母 + 空格，无半圆括号
        self.assertIn("| b 分装式电动机可用部件进行检验。<br>c 当有要求时，进行检验的项目。", markdown)
        # 条文脚注（数字编号）保留半圆括号
        self.assertIn("条文脚注见下1)。", markdown)
        self.assertNotIn("b)", markdown)
        self.assertNotIn("c)", markdown)

    def test_html_marks_them_as_superscript(self) -> None:
        html = render_html(self.document)
        self.assertIn("<td>振动<sup>b、d</sup></td>", html)
        self.assertIn("<td>盐雾<sup>c</sup></td>", html)
        self.assertIn("<sup>b</sup> 分装式电动机可用部件进行检验。", html)
        self.assertIn("条文脚注见下<sup>1)</sup>。", html)

    def test_pdf_keeps_the_letters_superscript_without_parenthesis(self) -> None:
        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        import json

        from leleby_ssir.pdf_renderer import render_pdf_file

        font_asset = (
            Path(__file__).resolve().parents[1]
            / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        )
        if not font_asset.is_file():
            self.skipTest("body font asset missing")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ssir_path = root / "doc.ssir.json"
            ssir_path.write_text(json.dumps(self.document, ensure_ascii=False), encoding="utf-8")
            target = root / "doc.render.pdf"
            render_pdf_file(ssir_path, target)
            document = pymupdf.open(str(target))
            text = _visible_layer_text(document)

        flat = re.sub(r"\s+", "", text)
        self.assertIn("振动b、d", flat)
        self.assertIn("盐雾c", flat)
        self.assertIn("b分装式电动机可用部件进行检验。", flat)
        # 条文脚注（数字编号）保持 `1)`
        self.assertIn("1)条文脚注排页脚。", flat)
        # 不得出现补出来的右括号形态
        self.assertNotIn("振动b)", flat)
        self.assertNotIn("b)分装式", flat)
        self.assertNotIn("[foot:", flat)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
