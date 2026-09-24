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


if __name__ == "__main__":
    unittest.main()
