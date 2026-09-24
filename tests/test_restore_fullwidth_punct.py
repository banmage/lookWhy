"""`tools/restore_fullwidth_punct.py`（误全角化标点还原回放）的回归测试。

事故背景（docs/12 §3.86）：`out/mineru/{GB_T_1.1-2020,GB_T_10401-2023}/02_canonical/*.canonical.md`
被管线之外的进程整体「半角标点全角化 + 吞空格」，导致 front matter 不再是映射（metadata 退化为
`{}`、封面 ICS/发布日/发布机构丢失、`document-identifier` 退化为文件名 stem → 页眉多出
`.canonical`）、`<!--ssir:…-->` 指令行不再是指令（表格/框线/脚注/目次全部失效）。

本测试锁住回放工具的判据与保证（不依赖真实语料）：
① 模型精确还原（含「吞空格」变体）与字符级兜底都能还原，吞掉的空格也要补回；
② 语法必需半角（指令名 / `[foot:L]` / front matter 键）在副本无覆盖时也能还原；
③ 只改标点、行数不变、幂等（复跑 0 处改动）、还原后 front matter 仍是映射。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import restore_fullwidth_punct as rfp  # noqa: E402
from leleby_ssir.service import parse_csm  # noqa: E402

HEALTHY = """\
---
csm-version: '1.0'
document-type: standard
document-identifier: GB/T 1.1-2020
standard-number: GB/T 1.1-2020
title: 标准化工作导则 第1部分：标准化文件的结构和起草规则
title-en: 'Directives for standardization Part 1: Rules'
publication-date: '2020-03-31'
ics: '01.120'
ccs: A 00
language: zh-CN
source:
  mode: user-markdown
  provenance: none
extensions: {}
---

# 标准化工作导则

本文件按照 GB/T 1.1—2020《标准化工作导则》的规定起草。

**表1 检验项目**

<!-- ssir:table id="t1" header-rows="1" caption-number="1" -->

| 序号 | 项目 | 结果 |
| --- | --- | --- |
| 1 | 径向间隙[foot:a] | √ |

$a$ 径向间隙的实测值。

间隔号(·)用作分隔符。
"""


class RestoreFullwidthPunctTests(unittest.TestCase):
    """损坏模型、字符级兜底、语法还原与不变量。"""

    def _run(self, target_text: str, oracle_text: str, apply: bool = True) -> tuple[str, bool]:
        """跑一遍工具；返回（文件内容, 还原后 front matter 是否为非空映射）。"""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "GB_T_1.1-2020.canonical.md"
            oracle = Path(tmp) / "oracle.md"
            target.write_text(target_text, encoding="utf-8")
            oracle.write_text(oracle_text, encoding="utf-8")
            rfp.run(target, [oracle], apply)
            metadata_ok = bool((parse_csm(target).get("metadata") if apply else None))
            return target.read_text(encoding="utf-8"), metadata_ok

    def test_pure_widening_model_restores_exactly(self) -> None:
        """模型 A（只换标点）：整行还原成副本原文，front matter 恢复为映射。"""
        corrupted = rfp.model_chars(HEALTHY)
        # 事故特征：全角化后文件里半角 `,` `:` `;` 计数为 0
        self.assertEqual((corrupted.count(","), corrupted.count(":"), corrupted.count(";")), (0, 0, 0))
        restored, metadata_ok = self._run(corrupted, HEALTHY)
        self.assertEqual(restored, HEALTHY)
        self.assertTrue(metadata_ok)  # metadata 不再是空对象（封面 ICS/日期/机构因此得以恢复）

    def test_space_eating_model_restores_the_eaten_space(self) -> None:
        """模型 B（`逗号+空格` 连空格一起被吞）与字符级兜底都要把空格补回。"""
        spaced = "本文件按照 GB/T 1.1—2020 的规定, 以及 GB/T 2 的规定起草。\n"
        corrupted = rfp.model_comma_space(spaced)
        self.assertEqual(corrupted, "本文件按照 GB/T 1.1—2020 的规定，以及 GB/T 2 的规定起草。\n")
        new_text, changed_lines, uncovered, stats, _ = rfp.convert(corrupted, [spaced])
        self.assertEqual(new_text, spaced)
        self.assertEqual((len(changed_lines), uncovered), (1, []))
        # 模型不命中时（副本该行另有差异）字符级兜底同样补空格
        restored, changes = rfp.restore_line("规定，以及", "规定, 以及")
        self.assertEqual(restored, "规定, 以及")
        self.assertEqual(changes, [(2, "，", ", ")])
        # 模型 A 不会臆造空格（副本本来就没有空格时保持原样）
        self.assertEqual(rfp.model_chars(spaced).count(", "), 0)

    def test_syntax_rules_restore_without_any_oracle(self) -> None:
        """副本没有对应行时，语法必需半角（指令名 / [foot:L] / front matter 键）仍要还原。"""
        corrupted = rfp.model_chars(HEALTHY) + "无标点的一行\n"
        restored, _ = self._run(corrupted, "无关副本\n")
        self.assertIn("csm-version: '1.0'", restored)
        self.assertIn('<!-- ssir:table id="t1"', restored)
        self.assertIn("[foot:a]", restored)
        self.assertNotIn("ssir：", restored)
        self.assertNotIn("foot：", restored)

    def test_only_punctuation_changes_and_line_count_kept(self) -> None:
        """不变量：只动标点（折叠 + 去空格后逐位相同），行数不变。"""
        corrupted = rfp.model_chars(HEALTHY)
        restored, _ = self._run(corrupted, HEALTHY)
        old_lines, new_lines = corrupted.split("\n"), restored.split("\n")
        self.assertEqual(len(old_lines), len(new_lines))
        for old, new in zip(old_lines, new_lines):
            self.assertEqual(rfp.fold(old.replace(" ", "")), rfp.fold(new.replace(" ", "")), old)

    def test_idempotent(self) -> None:
        """幂等：已还原的文本复跑 0 处改动（含语法 pass）。"""
        restored, _ = self._run(rfp.model_chars(HEALTHY), HEALTHY)
        _, changed_lines, uncovered, stats, _ = rfp.convert(restored, [HEALTHY])
        self.assertEqual((changed_lines, uncovered, dict(stats)), ([], [], {}))

    def test_wide_pairs_are_fixed_and_unique(self) -> None:
        """配对表固定：只认这五对全角↔半角，且 `～`/`‧` 折叠到半角形态。"""
        self.assertEqual(rfp.PAIR, {"：": ":", "，": ",", "；": ";", "‧": "·", "～": "~"})
        self.assertEqual(rfp.fold("：，；‧～"), ":,;·~")


if __name__ == "__main__":
    unittest.main()
