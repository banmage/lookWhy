"""P0-E 零推断回归：图注/表题形状判据只认结构化字段，不再从正文文本形状反推。

背景（2026-09-22）：`_is_figure_note_shape` / `_is_table_caption_shape` 原各含一段文本猜测分支
（段落/注/列表文本以 `图N`/`表N` 开头即判为图注/表题），用于「图注后紧跟表题 → 空一行」的间距决策。
按零推断口径删除猜测分支；删除依据 = 全语料度量（图注形状 47 处中仅 3 处来自猜测，表题 99 处中仅 4 处）
+ 真渲染 A/B（差异范围与度量一致）。

间距行为本身由全语料渲染 A/B 覆盖；本文件锁「判据不得回退到文本猜测」。
"""

from __future__ import annotations

import unittest

from leleby_ssir.pdf_renderer import _is_figure_note_shape, _is_table_caption_shape


class ShapeHeuristicStructuralOnlyTests(unittest.TestCase):
    def test_paragraph_text_starting_with_figure_number_is_not_a_figure_note(self) -> None:
        guesses = [
            {"presentationType": "paragraph", "textContent": "图3 示例结构"},
            {"presentationType": "paragraph", "textContent": "图 3.1 流程图"},
            {"presentationType": "note", "textContent": "图4 注"},
            {"presentationType": "list", "listItems": [{"text": "图5 分图"}]},
        ]
        for content in guesses:
            with self.subTest(content=content):
                self.assertFalse(
                    _is_figure_note_shape(content),
                    f"文本猜测分支回退了：{content}",
                )

    def test_paragraph_text_starting_with_table_number_is_not_a_table_caption(self) -> None:
        guesses = [
            {"presentationType": "paragraph", "textContent": "表2 试验条件"},
            {"presentationType": "paragraph", "textContent": "表 2.1 参数"},
            {"presentationType": "note", "textContent": "表3 注"},
        ]
        for content in guesses:
            with self.subTest(content=content):
                self.assertFalse(
                    _is_table_caption_shape(content),
                    f"文本猜测分支回退了：{content}",
                )

    def test_structural_kinds_still_recognized(self) -> None:
        self.assertTrue(_is_figure_note_shape({"presentationType": "figure"}))
        self.assertTrue(_is_table_caption_shape({"presentationType": "table"}))
        self.assertFalse(_is_figure_note_shape({"presentationType": "table"}))
        self.assertFalse(_is_table_caption_shape({"presentationType": "figure"}))
        self.assertFalse(_is_figure_note_shape({}))
        self.assertFalse(_is_table_caption_shape({}))


if __name__ == "__main__":
    unittest.main()
