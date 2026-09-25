"""式中条目判据回归（P0-D/§0.2）：符号位不得吞下指令行/标记行。

缺陷与根因（2026-09-22，GB_T_1.1-2020 实测暴露）：
`EXPLANATION_ITEM_RE` 早期符号位为 `[^—–-]{1,8}?`，`<!-- ssir:/box -->` 的前两个字符
`<!` 后紧跟 `--`，整行被判为「符号 `<!` + 破折号 + 释义」，于是式中解释组把紧随其后的
指令行吞进条目（实测 18 行括起只产出 13 条，缺的正是被吞/被截断的行）。

通用判据（落点在 parser 的正则，不在调用方）：
- 符号位为 `$…$` 数学式，或 ≤8 字符且**不以标记字符 `<! # | > ` [ -` 开头**的符号；
- 指令行（`<!-- … -->`）、围栏行永不算条目。

另附：`===` 破折号写法的容错（`———` 三连破折号，GB_T_1.1-2020 的式中行写法）。
"""

from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

from leleby_ssir.parser import EXPLANATION_ITEM_RE
from leleby_ssir.service import parse_csm
from leleby_ssir.validation import validate_ssir

FRONT_MATTER = """\
---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/XYZ 002—2026"
standard-number: "Q/XYZ 002—2026"
title: "式中判据夹具"
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

# 式中判据夹具

## 1 范围

本文档用于式中条目判据回归。

![图1 结构示意](assets/fig1.png)

<!-- ssir:figure id="fig-001" -->

<!-- ssir:formula id="fm-001" -->
$$
\\\\overline{\\\\eta} = \\\\dfrac{\\\\overline{P}_{2}}{\\\\overline{P}_{1}}
$$
式(1)

式中：

<!-- ssir:formula-vars formula="fm-001" -->
$\\overline{\\eta}$ —— 传动效率；

<!-- ssir:box -->

盒内段落。

<!-- ssir:/box -->
"""


def _parse(text: str) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "fixture.md"
        path.write_text(text, encoding="utf-8")
        ssir = parse_csm(path)
    validate_ssir(ssir)
    return ssir


class ExplanationItemJudgeTests(unittest.TestCase):
    """判据层：指令行/标记行不得被当作式中条目。"""

    def test_markup_lines_are_not_items(self) -> None:
        for line in (
            "<!-- ssir:/box -->",
            "<!-- ssir:box -->",
            '<!-- ssir:formula id="fm-001" -->',
            "# 标题",
            "```python",
            "| 表头 | 值 |",
            "> 注：说明",
        ):
            with self.subTest(line=line):
                self.assertIsNone(
                    EXPLANATION_ITEM_RE.match(line),
                    f"标记行被判为式中条目：{line}",
                )

    def test_real_items_still_match(self) -> None:
        cases = {
            "$v$——匀速运动质点的速度；": ("$v$", "匀速运动质点的速度"),
            "$l$ ———运行距离；": ("$l$", "运行距离"),
            "$E$ —— 能量": ("$E$", "能量"),
            "$t$ ——时间间隔。": ("$t$", "时间间隔"),
        }
        for line, (symbol, definition) in cases.items():
            with self.subTest(line=line):
                match = EXPLANATION_ITEM_RE.match(line)
                self.assertIsNotNone(match, f"真实条目未被识别：{line}")
                self.assertEqual(match.group("symbol").strip(), symbol)
                self.assertEqual(match.group("definition").strip(), definition)


class ExplanationGroupBoundaryTests(unittest.TestCase):
    """端到端：式中组遇指令行即止，指令行不落条目、后续块照常解析。"""

    def test_group_stops_before_directive_line(self) -> None:
        ssir = _parse(FRONT_MATTER)
        formulas = [item for item in ssir.get("formulas") or []]
        self.assertEqual(len(formulas), 1)
        items = (formulas[0].get("explanationGroup") or {}).get("items") or []
        self.assertEqual(
            [item.get("symbol") for item in items],
            ["$\\overline{\\eta}$"],
            "式中组应只含一条解释（指令行不得被吞进条目）",
        )
        self.assertNotIn("ssir", str(items), "条目里出现了指令文本")
        # 后续 box 块的正文仍在 SSIR 里（未被式中组吃掉）
        self.assertIn(
            "盒内段落",
            json.dumps(ssir, ensure_ascii=False),
            "box 正文未出现在 SSIR 中",
        )


MULTI_SYMBOL_FIXTURE = """\
---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/XYZ 004—2026"
standard-number: "Q/XYZ 004—2026"
title: "式中并列符号与取值行夹具"
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

# 式中并列符号与取值行夹具

## 1 范围

本文档用于式中并列符号与取值行回归。

<!-- ssir:formula id="fm-001" -->
$$
\\\\overline{\\\\eta} = \\\\dfrac{\\\\overline{P}_{2}}{\\\\overline{P}_{1}}
$$
式(1)

式中：

<!-- ssir:formula-vars formula="fm-001" -->
$t$ —— 综合差错率；

$C_{A}$ —— 译文使用目的系数，建议取值：

      I类使用目的系数： $C_{A}=1$;

      Ⅱ类使用目的系数： $C_{A}=0.75$ ;

$D_{I}$ 、 $D_{II}$ ——Ⅰ类、Ⅱ类差错出现的次数，重复性错误按一次计算；

$c_{I}$ 、 $c_{II}$  —— I 类、Ⅱ类差错的系数，建议取值如下：

$c_{I}$ = 3;
$c_{II}$ =1。

<!-- ssir:/formula-vars -->
"""


class FormulaVarsUnmatchedLineTests(unittest.TestCase):
    """括起式式中组里的续行/取值行与并列符号（GEN-142）。

    缺陷与根因（2026-09-24，GB/T 20001.5-2017 附录 A 示例 1 实测）：`symbol` 位要求
    单符号且 ≤8 字符，并列符号行（`$D_{I}$ 、 $D_{II}$ ——…`）与取值行/续行
    （`I类使用目的系数： …`、`$c_{I}$ = 3;`）都不匹配判据；builder 一律落
    `{"text": …}`，而 ExplanationItem 只接受 symbol/definition/unit/terminator
    （无 `text`）→ schema 校验失败、整份构建中断（6 行命中）。

    通用规则：并列符号进 symbol（整段并列写法原样保留）；无 `——` 的行按**无符号的
    解释行**登记（symbol 空、整行进 definition、句末标点进 terminator），行序与文字
    零丢失，且不产生 schema 不允许的字段。
    """

    def test_multi_symbol_line_keeps_both_symbols_in_one_item(self) -> None:
        cases = {
            "$D_{I}$ 、 $D_{II}$ ——Ⅰ类、Ⅱ类差错出现的次数，重复性错误按一次计算；": (
                "$D_{I}$ 、 $D_{II}$",
                "Ⅰ类、Ⅱ类差错出现的次数，重复性错误按一次计算",
            ),
            "$c_{I}$ 、 $c_{II}$  —— I 类、Ⅱ类差错的系数，建议取值如下：": (
                "$c_{I}$ 、 $c_{II}$",
                "I 类、Ⅱ类差错的系数，建议取值如下：",
            ),
            "A、B —— 两个符号共用一条解释。": ("A、B", "两个符号共用一条解释"),
            "k, m —— 拉丁符号也能并列；": ("k, m", "拉丁符号也能并列"),
        }
        for line, (symbol, definition) in cases.items():
            with self.subTest(line=line):
                match = EXPLANATION_ITEM_RE.match(line)
                self.assertIsNotNone(match, f"并列符号行未被识别：{line}")
                self.assertEqual(match.group("symbol").strip(), symbol)
                self.assertEqual(match.group("definition").strip(), definition)

    def test_value_lines_are_not_symbol_items(self) -> None:
        for line in (
            "I类使用目的系数： $C_{A}=1$;",
            "Ⅱ类使用目的系数： $C_{A}=0.75$ ;",
            "$c_{I}$ = 3;",
            "$c_{II}$ =1。",
        ):
            with self.subTest(line=line):
                self.assertIsNone(
                    EXPLANATION_ITEM_RE.match(line),
                    f"取值行/续行被误判为符号条目：{line}",
                )

    def test_group_parses_and_validates_with_continuation_lines(self) -> None:
        ssir = _parse(MULTI_SYMBOL_FIXTURE)
        items = (ssir["formulas"][0]["explanationGroup"])["items"]
        self.assertEqual(len(items), 8, "条目数与括起式声明体的行数不一致（丢行/并行了）")
        for index, item in enumerate(items):
            with self.subTest(index=index):
                self.assertNotIn("text", item, "ExplanationItem 不允许 text 字段")
                self.assertIn("symbol", item)
                self.assertTrue(set(item) <= {"symbol", "definition", "unit", "terminator"})
        self.assertEqual(items[2]["symbol"], "")
        self.assertEqual(items[2]["definition"], "I类使用目的系数： $C_{A}=1$")
        self.assertEqual(items[2]["terminator"], ";")
        self.assertEqual(items[4]["symbol"], "$D_{I}$ 、 $D_{II}$")
        self.assertEqual(items[7]["definition"], "$c_{II}$ =1")
        self.assertEqual(items[7]["terminator"], "。")

    def test_render_lines_keep_order_and_text(self) -> None:
        from leleby_ssir.pdf_renderer import _formula_explanation_lines

        ssir = _parse(MULTI_SYMBOL_FIXTURE)
        lines = _formula_explanation_lines(ssir["formulas"][0])
        self.assertEqual(len(lines), 8)
        self.assertEqual(lines[2], "I类使用目的系数： $C_{A}=1$;")
        self.assertEqual(
            lines[4],
            "$D_{I}$ 、 $D_{II}$——Ⅰ类、Ⅱ类差错出现的次数，重复性错误按一次计算；",
        )
        self.assertEqual(lines[7], "$c_{II}$ =1。")
        self.assertEqual(lines[0], "$t$——综合差错率；")


if __name__ == "__main__":
    unittest.main()
