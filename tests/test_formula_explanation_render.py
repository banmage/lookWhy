"""P0-E 渲染端零推断（第二片）：`Formula.explanationGroup`（式中解释组）绘制。

规则（docs/15 §3.8 + docs/16 §11/§12）：
- 逐行绘 ``symbol——definition``；`symbol`/`definition` 缺一即按有的那部分绘；
- 渲染端**零推断**：只绘字段里有的内容，不回落到「式中：」正文正则；
- 未声明解释组的文档渲染结果不变（本片不触碰既有公式路径）。
"""

from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from leleby_ssir.pdf_renderer import _formula_explanation_lines
from leleby_ssir.service import parse_csm

FIXTURE = """\
---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/XYZ 003—2026"
standard-number: "Q/XYZ 003—2026"
title: "式中解释组渲染夹具"
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

# 式中解释组渲染夹具

## 1 范围

本文档用于式中解释组渲染回归。

<!-- ssir:formula id="fm-001" -->
$$
\\overline{\\eta} = \\dfrac{\\overline{P}_{2}}{\\overline{P}_{1}}
$$
式(1)

<!-- ssir:formula-vars formula="fm-001" -->
$\\overline{\\eta}$——传动效率；

$\\overline{P}_{1}$——输入端功率算术平均值，单位为千瓦（kW）。
"""


COLUMNS_FIXTURE = """\
---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/XYZ 004—2026"
standard-number: "Q/XYZ 004—2026"
title: "并列列内式中解释组夹具"
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

# 并列列内式中解释组夹具

## 1 范围

本文档用于并列列内式中解释组回归。

<!-- ssir:columns -->

正确：

<!-- ssir:formula id="fm-col-1" -->
$$
dim (E) = dim (F) \\\\times dim (l)
$$
式中：
<!-- ssir:formula-vars formula="fm-col-1" -->
$E$ —— 能量；
$F$ —— 作用力。

<!-- ssir:column -->

不正确：

$$
密度 = \\\\frac{质量}{体积}
$$
"""


class FormulaExplanationRenderTests(unittest.TestCase):
    def test_lines_are_built_from_fields_only(self) -> None:
        formula = {
            "explanationGroup": {
                "items": [
                    {"symbol": "$\\eta$", "definition": "传动效率"},
                    {"symbol": "$P$"},
                    {"definition": "孤立释义"},
                ]
            }
        }
        self.assertEqual(
            _formula_explanation_lines(formula),
            ["$\\eta$——传动效率", "$P$", "孤立释义"],
        )

    def test_absent_group_draws_nothing(self) -> None:
        self.assertEqual(_formula_explanation_lines({}), [])
        self.assertEqual(_formula_explanation_lines({"explanationGroup": {"items": []}}), [])

    def test_explanation_group_reaches_the_pdf_text_layer(self) -> None:
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
            group = ssir["formulas"][0].get("explanationGroup")
            self.assertEqual(len(group["items"]), 2)
            target = root / "doc.render.pdf"
            ssir_path = root / "doc.ssir.json"
            ssir_path.write_text(json.dumps(ssir, ensure_ascii=False), encoding="utf-8")
            render_pdf_file(ssir_path, target)
            document = pymupdf.open(str(target))
            text = "".join(page.get_text() for page in document)
            self.assertIn("传动效率", text)
            self.assertIn("输入端功率算术平均值", text)

    def test_explanation_group_in_side_by_side_column_reaches_text_layer(self) -> None:
        """并列（columns）路径的公式同样绘制式中解释组。

        缺陷与根因（2026-09-22，GB_T_1.1-2020 实测）：渲染端有两个公式绘制分支——
        主路径与并列列内路径；式中解释组的绘制最初只加在主路径，于是并列列内公式的
        `explanationGroup` 整组不进产物（实测「统计量」等释义在渲染文本层里 4 行只剩 1 行）。
        规则：**每个公式绘制点都必须绘制式中解释组**（与图例/分图题注的并列路径同规）。
        """
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
            canonical = root / "columns.canonical.md"
            canonical.write_text(textwrap.dedent(COLUMNS_FIXTURE), encoding="utf-8")
            ssir = parse_csm(canonical)
            items = [
                item for formula in ssir.get("formulas") or []
                for item in (formula.get("explanationGroup") or {}).get("items") or []
            ]
            self.assertEqual([item.get("definition") for item in items], ["能量", "作用力"])
            target = root / "columns.render.pdf"
            ssir_path = root / "columns.ssir.json"
            ssir_path.write_text(json.dumps(ssir, ensure_ascii=False), encoding="utf-8")
            render_pdf_file(ssir_path, target)
            document = pymupdf.open(str(target))
            text = "".join(page.get_text() for page in document)
            self.assertIn("能量", text, "并列列内公式的式中解释组未绘制")
            self.assertIn("作用力", text, "并列列内公式的式中解释组未绘制")


class FormulaExplanationOrderTests(unittest.TestCase):
    """GEN-129：解释条目必须排在「式中：」引入行**之后**（PDF 与投影同一判据）。

    缺陷（2026-09-23 用户报告）：条目挂在公式上，渲染端在公式后立刻绘制 → 版面上条目跑到了
    「式中：」上面（GB_T_1.1-2020 9.9.3.1 实测：v/l/t 三行在「式中：」之上）；同一缺陷也在
    并列列内路径与 render.md 投影里。规则：引入行在前、条目在后（引入行缺失则紧随公式）。
    """

    ORDER_FIXTURE = """\
---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/XYZ 005—2026"
standard-number: "Q/XYZ 005—2026"
title: "式中顺序夹具"
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

# 式中顺序夹具

## 1 范围

本文档用于「式中：」引入行与解释条目的先后回归。

<!-- ssir:formula id="fm-order" -->
$$
v = \\frac {l}{t}
$$
式中：
<!-- ssir:formula-vars formula="fm-order" -->
$v$ —— 匀速运动质点的速度；
$l$ —— 运行距离。
"""

    def _render(self, text: str, name: str) -> str:
        from leleby_ssir.pdf_renderer import render_pdf_file

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canonical = root / f"{name}.canonical.md"
            canonical.write_text(textwrap.dedent(text), encoding="utf-8")
            ssir = parse_csm(canonical)
            ssir_path = root / f"{name}.ssir.json"
            ssir_path.write_text(json.dumps(ssir, ensure_ascii=False), encoding="utf-8")
            target = root / f"{name}.render.pdf"
            render_pdf_file(ssir_path, target)
            import pymupdf

            with pymupdf.open(str(target)) as document:
                return "".join(page.get_text() for page in document)

    def setUp(self) -> None:
        font_asset = Path(__file__).resolve().parents[1] / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font_asset.is_file():
            self.skipTest("body font asset missing")
        try:
            import pymupdf  # noqa: F401
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")

    def test_main_path_prints_intro_before_items(self) -> None:
        text = self._render(self.ORDER_FIXTURE, "order")
        self.assertIn("式中：", text)
        self.assertLess(text.index("式中："), text.index("匀速运动质点的速度"),
                        "解释条目排到了「式中：」引入行之前")

    def test_terminators_are_kept(self) -> None:
        text = self._render(self.ORDER_FIXTURE, "order-term")
        self.assertIn("匀速运动质点的速度；", text, "解释项句尾分号丢失")
        self.assertIn("运行距离。", text, "末项句尾句号丢失")

    def test_side_by_side_path_prints_intro_before_items(self) -> None:
        text = self._render(COLUMNS_FIXTURE, "order-col")
        self.assertIn("式中：", text)
        self.assertLess(text.index("式中："), text.index("能量"),
                        "并列列内的解释条目排到了「式中：」引入行之前")


if __name__ == "__main__":
    unittest.main()
