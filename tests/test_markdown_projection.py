"""render.md = SSIR 的**标准 markdown 投影**（2026-09-22 用户裁定）。

回环验证永久下线后，render.md 不再由回环产生，而是 SSIR 的等价 markdown：投影结果必须
**零 `<!-- ssir:… -->` 指令、零 HTML 注释、无 front matter**，且保留 GB/T 1.1 的文档形态
（标题层级、GFM 表格、图表脚注 `a) 注文`、公式 `$$…$$` + `式(N)`、图题 `> [图N 题名]`）。
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from leleby_ssir.csm_renderer import asset_base_for, render_csm
from leleby_ssir.service import parse_csm

FIXTURE = """\
---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/XYZ 008—2026"
standard-number: "Q/XYZ 008—2026"
title: "投影夹具"
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

# 投影夹具

## 1 范围

本文档用于 markdown 投影回归。

### 1.1 一般要求

- 列项一；
- 列项二。

| 项目 | 要求 |
| --- | --- |
| 径向间隙[foot:a] | 3 |

<!--ssir:foot:a-->分装式电动机不检验。<!--ssir:/foot-->

$$
a^2+b^2=c^2
$$
式(1)

<!-- ssir:figure id="fig-001" asset-status="missing" -->
> [图1 电路图]

### 1.2 式中与资产

<!-- ssir:formula id="fx-002" -->
$$
v = \frac {l}{t}
$$
式中：
<!-- ssir:formula-vars formula="fx-002" -->
$v$ ———速度；
$l$ ———距离。
<!-- ssir:/formula-vars -->

![](assets/images/demo.jpg)

## 2 规范性引用文件

下列文件中的内容通过文中的规范性引用而构成本文件必不可少的条款。
"""


def _ssir(tmp: str):
    path = Path(tmp) / "fixture.md"
    path.write_text(FIXTURE, encoding="utf-8")
    return parse_csm(path)


class MarkdownProjectionTests(unittest.TestCase):
    def test_projection_has_no_directives_and_no_html_comments(self) -> None:
        with TemporaryDirectory() as tmp:
            markdown = render_csm(_ssir(tmp))
        self.assertNotIn("ssir:", markdown)
        self.assertNotIn("<!--", markdown)
        self.assertNotIn("-->", markdown)
        self.assertFalse(markdown.startswith("---"), "投影不得含 front matter")

    def test_projection_keeps_gbt_document_shape(self) -> None:
        with TemporaryDirectory() as tmp:
            markdown = render_csm(_ssir(tmp))
        self.assertIn("# 投影夹具", markdown)
        self.assertIn("## 1 范围", markdown)
        self.assertIn("### 1.1 一般要求", markdown)
        self.assertIn("- 列项一；", markdown)
        self.assertIn("| 项目 | 要求 |", markdown)
        self.assertIn("| --- | --- |", markdown)
        # 图表脚注的定义写成 `a 注文`（GB/T 1.1-2020 9.12.2 的裸小写字母标记，无半圆括号），
        # 不是指令对；markdown 无上标语法，故平印字面。
        self.assertIn("a 分装式电动机不检验。", markdown)
        self.assertNotIn("foot:", markdown)
        # 公式与编号行，图题占位（无资产时标注「（图片占位）」——投影保留该信息）
        self.assertIn("$$", markdown)
        self.assertIn("式(1)", markdown)
        self.assertIn("> [图1 电路图（图片占位）]", markdown)

    def test_projection_is_deterministic(self) -> None:
        with TemporaryDirectory() as tmp:
            first = render_csm(_ssir(tmp))
        with TemporaryDirectory() as tmp:
            second = render_csm(_ssir(tmp))
        self.assertEqual(first, second)


class FormulaExplanationProjectionTests(unittest.TestCase):
    """GEN-126：式中解释组必须出现在投影里，且粘回「式中：」引入行之后。"""

    def test_explanation_items_follow_their_intro_line(self) -> None:
        with TemporaryDirectory() as tmp:
            markdown = render_csm(_ssir(tmp))
        lines = markdown.splitlines()
        self.assertIn("式中：", lines)
        intro = lines.index("式中：")
        following = [line for line in lines[intro + 1:] if line.strip()]
        self.assertEqual(following[0], "$v$——速度；")
        self.assertEqual(following[1], "$l$——距离。")

    def test_explanation_items_survive_without_intro_line(self) -> None:
        # 引入行缺失（抽取残缺：条目挂在公式上而「式中：」段丢失）时不得整组丢失。
        with TemporaryDirectory() as tmp:
            document = _ssir(tmp)
        node = document["structuralRoot"]["children"][0]["children"][0]
        contents = node["contentElements"]
        for content in list(contents):
            if str(content.get("textContent") or "").strip() == "式中：":
                contents.remove(content)
        markdown = render_csm(document)
        self.assertIn("$v$——速度；", markdown)
        self.assertIn("$l$——距离。", markdown)


class ProjectionAssetPathTests(unittest.TestCase):
    """GEN-127：投影里的资产引用按**产物所在目录**解析，图必须能打开。"""

    def test_asset_base_prefix_matches_output_location(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(asset_base_for(root / "render.md", root), "")
            self.assertEqual(asset_base_for(root / "04_render" / "x.render.md", root), "../")
            self.assertEqual(asset_base_for(root / "a" / "b" / "x.render.md", root), "../../")

    def test_asset_link_resolves_from_render_dir(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            document = _ssir(tmp)
            asset = root / "assets" / "images" / "demo.jpg"
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_bytes(b"\xff\xd8\xff")  # 内容无关：只验证路径可解析
            output = root / "04_render" / "fixture.render.md"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                render_csm(document, asset_base=asset_base_for(output, root)), encoding="utf-8"
            )
            markdown = output.read_text(encoding="utf-8")
            self.assertIn("](../assets/images/demo.jpg)", markdown)
            for link in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", markdown):
                self.assertTrue((output.parent / link).is_file(), f"资产链接解析失败: {link}")

    def test_default_asset_base_keeps_docroot_relative_refs(self) -> None:
        # 默认（输出位置未知，如 `ssir csm project` 到 stdout 旁的文件）保持 SSIR 原值。
        with TemporaryDirectory() as tmp:
            markdown = render_csm(_ssir(tmp))
        self.assertIn("](assets/images/demo.jpg)", markdown)


if __name__ == "__main__":
    unittest.main()
