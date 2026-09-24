"""P0-E 渲染端零推断（第一片）：`Figure.legend` / `Figure.subCaptions` 绘制。

规则（docs/15 §3.7/§3.8 + docs/16 §11）：
- 图例项绘为 ``index——text``、分图题注绘为 ``label）text``（缺 index/label 时只绘 text）；
- 渲染端**零推断**：只绘字段里有的内容，不回落正文正则；
- 未声明图例/分图题注的文档渲染结果与改动前逐字节无关（本片不触碰既有路径）。
"""

from __future__ import annotations

import tempfile
import textwrap
import unittest
import json
from pathlib import Path

from leleby_ssir.pdf_renderer import _figure_ancillary_lines
from leleby_ssir.service import parse_csm

FIXTURE = """\
---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/XYZ 002—2026"
standard-number: "Q/XYZ 002—2026"
title: "图例渲染夹具"
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

# 图例渲染夹具

## 1 范围

本文档用于图例渲染回归。

![图1 结构示意](assets/fig1.png)

<!-- ssir:figure id="fig-001" -->

<!-- ssir:figure-legend figure="fig-001" -->
1——气隙；

2——定子绕组。

<!-- ssir:figure-sub figure="fig-001" -->
a）局部剖面
"""


class FigureAncillaryRenderTests(unittest.TestCase):
    def test_lines_are_built_from_fields_only(self) -> None:
        figure = {
            "legend": [{"index": "1", "text": "气隙"}, {"text": "无编号项"}],
            "subCaptions": [{"label": "a", "text": "局部剖面"}, {"text": "无标号"}],
        }
        self.assertEqual(
            _figure_ancillary_lines(figure),
            ["1——气隙", "无编号项", "a）局部剖面", "无标号"],
        )

    def test_absent_fields_draw_nothing(self) -> None:
        self.assertEqual(_figure_ancillary_lines({}), [])
        self.assertEqual(_figure_ancillary_lines({"legend": [{"text": "  "}]}), [])

    def test_legend_and_subcaptions_reach_the_pdf_text_layer(self) -> None:
        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        from leleby_ssir.pdf_renderer import render_pdf_file

        font_asset = Path(__file__).resolve().parents[1] / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font_asset.is_file():
            self.skipTest("body font asset missing")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical = root / "doc.canonical.md"
            canonical.write_text(textwrap.dedent(FIXTURE), encoding="utf-8")
            ssir = parse_csm(canonical)
            self.assertEqual(len(ssir["figures"][0]["legend"]), 2)
            target = root / "doc.render.pdf"
            ssir_path = root / "doc.ssir.json"
            ssir_path.write_text(json.dumps(ssir, ensure_ascii=False), encoding="utf-8")
            render_pdf_file(ssir_path, target)
            document = pymupdf.open(str(target))
            text = "".join(page.get_text() for page in document)
            self.assertIn("气隙", text)
            self.assertIn("定子绕组", text)
            self.assertIn("局部剖面", text)


if __name__ == "__main__":
    unittest.main()
