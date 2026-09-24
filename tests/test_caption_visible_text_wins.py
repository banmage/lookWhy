"""GEN-139 / CSM-TABLE-005：题注与单位陈述「可见文字优先 + 告警」的回归夹具。

规则（2026-09-24 用户裁定，docs/12 §3.88）：
- canonical 里的**可见文字**——`**表N 题名**` 题注行、"单位为毫米" 单位陈述行、
  图题注 alt 文本（`![图 1 电路图](…)`）——是人所见即所得的真值；指令属性
  （`caption-number`/`caption`/`unit`）只是它的投影。
- 两者不一致时**以可见文字为准**（SSIR `tables[].caption` 即取可见值），并落
  结构化 warning `CSM-TABLE-005`（带行号/表 id/属性值/可见值）；不再静默覆写。
- 指令**上方**的加粗题注行同样折入（此前不折 → 同一题注印两次）；编号不一致时
  仍保守不并（防把正文"见表5"误并进表4），但也不静默。
- 渲染端不参与：它只读 SSIR（零文本推断），故本规则只在解析层落地。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leleby_ssir.builder import SSIRBuilder  # noqa: E402
from leleby_ssir.parser import CSMParser  # noqa: E402

HEAD = """---
docType: national-standard
standardNumber: GB/T 99999-2026
title: 探针文件
language: zh-CN
---

# 探针文件

## 1 范围

本文件适用于探针。

"""

TABLE_ROWS = "| A | B |\n| --- | --- |\n| 1 | 2 |\n"
FIGURE = "![图 1 行图题](assets/images/x.jpg)\n"


class CaptionAuthorityTest(unittest.TestCase):
    def _parse(self, body: str):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "probe.canonical.md"
            path.write_text(HEAD + body, encoding="utf-8")
            return CSMParser().read(path)

    @staticmethod
    def _table_attrs(document):
        for block in document.blocks:
            if block.kind == "table" and block.directive:
                return block.directive.attrs
        return {}

    @staticmethod
    def _hits(document):
        return [issue for issue in document.issues if issue.code == "CSM-TABLE-005"]

    # --- 表格题注 ---------------------------------------------------------
    def test_consistent_caption_warns_nothing(self):
        body = (
            '<!-- ssir:table id="t1" header-rows="1" caption-number="1" caption="物理性能" unit="毫米" -->\n'
            "**表1 物理性能**\n" + TABLE_ROWS
        )
        document = self._parse(body)
        self.assertEqual(self._hits(document), [])
        self.assertEqual(self._table_attrs(document)["caption"], "物理性能")

    def test_visible_caption_wins_and_warns(self):
        body = (
            '<!-- ssir:table id="t1" header-rows="1" caption-number="1" caption="属性题名" unit="毫米" -->\n'
            "**表1 行题名**\n" + TABLE_ROWS
        )
        document = self._parse(body)
        hits = self._hits(document)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].severity, "warning")
        self.assertIn("caption", hits[0].message)
        self.assertIn("属性题名", hits[0].message)
        self.assertEqual(self._table_attrs(document)["caption"], "行题名")

    def test_visible_caption_number_wins_and_warns(self):
        body = (
            '<!-- ssir:table id="t1" header-rows="1" caption-number="9" caption="行题名" -->\n'
            "**表1 行题名**\n" + TABLE_ROWS
        )
        document = self._parse(body)
        self.assertEqual(len(self._hits(document)), 1)
        self.assertEqual(self._table_attrs(document)["caption-number"], "1")

    def test_bare_caption_number_keeps_title(self):
        body = (
            '<!-- ssir:table id="t1" header-rows="1" caption-number="1" caption="行题名" -->\n'
            "**表1**\n" + TABLE_ROWS
        )
        document = self._parse(body)
        attrs = self._table_attrs(document)
        self.assertEqual((attrs["caption-number"], attrs["caption"]), ("1", "行题名"))
        self.assertEqual(self._hits(document), [])

    def test_caption_above_directive_bold_is_folded(self):
        body = "**表1 行题名**\n\n" + (
            '<!-- ssir:table id="t1" header-rows="1" caption-number="1" caption="属性题名" -->\n' + TABLE_ROWS
        )
        document = self._parse(body)
        self.assertEqual(self._table_attrs(document)["caption"], "行题名")
        self.assertEqual(len(self._hits(document)), 1)
        # 题注行不再作为独立段落留下（否则渲染成「属性题名 + 行题名」双题注）。
        self.assertFalse(
            [block for block in document.blocks if block.text.strip() == "**表1 行题名**"]
        )

    def test_caption_above_directive_mismatched_number_is_not_merged_but_warns(self):
        body = "**表1 行题名**\n\n" + (
            '<!-- ssir:table id="t1" header-rows="1" caption-number="9" caption="属性题名" -->\n' + TABLE_ROWS
        )
        document = self._parse(body)
        hits = self._hits(document)
        self.assertEqual(len(hits), 1)
        self.assertIn("未并入", hits[0].message)
        attrs = self._table_attrs(document)
        self.assertEqual((attrs["caption-number"], attrs["caption"]), ("9", "属性题名"))

    # --- 单位陈述 ---------------------------------------------------------
    def test_unit_line_wins_and_warns(self):
        body = "单位为毫米\n\n" + (
            '<!-- ssir:table id="t1" header-rows="1" caption-number="1" caption="行题名" unit="厘米" -->\n'
            "**表1 行题名**\n" + TABLE_ROWS
        )
        document = self._parse(body)
        hits = self._hits(document)
        self.assertEqual(len(hits), 1)
        self.assertIn("unit", hits[0].message)
        self.assertEqual(self._table_attrs(document)["unit"], "毫米")

    def test_figure_unit_line_wins_and_warns(self):
        body = "单位为毫米\n\n" + (
            '<!-- ssir:figure id="f1" caption-number="1" caption="行图题" unit="厘米" -->\n\n' + FIGURE
        )
        document = self._parse(body)
        hits = self._hits(document)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].message.count("unit"), 1)

    # --- 图题注（alt 文本） ----------------------------------------------
    def test_figure_caption_attr_aligned_to_alt_text(self):
        body = '<!-- ssir:figure id="f1" caption-number="7" caption="属性图题" -->\n\n' + FIGURE
        document = self._parse(body)
        hits = self._hits(document)
        self.assertEqual(len(hits), 2)  # 编号 + 题名各一条
        for block in document.blocks:
            if block.kind == "figure" and block.directive:
                self.assertEqual(block.directive.attrs["caption-number"], "1")
                self.assertEqual(block.directive.attrs["caption"], "行图题")
                break
        else:
            self.fail("未解析出图块")

    def test_consistent_figure_warns_nothing(self):
        body = '<!-- ssir:figure id="f1" caption-number="1" caption="行图题" -->\n\n' + FIGURE
        self.assertEqual(self._hits(self._parse(body)), [])

    # --- SSIR 层：不一致时 tables[].caption 取可见值 ----------------------
    def test_ssir_caption_takes_visible_text(self):
        body = (
            '<!-- ssir:table id="t1" header-rows="1" caption-number="1" caption="属性题名" unit="厘米" -->\n'
            "**表1 行题名**\n" + TABLE_ROWS
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "probe.canonical.md"
            path.write_text(HEAD + body, encoding="utf-8")
            document = CSMParser().read(path)
        ssir = SSIRBuilder().build(document)
        self.assertEqual(len(ssir["tables"]), 1)
        self.assertEqual(ssir["tables"][0]["caption"], "行题名")


if __name__ == "__main__":
    unittest.main()
