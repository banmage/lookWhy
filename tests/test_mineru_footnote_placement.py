from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from mineru_full_standard import _place_footnote_definitions  # noqa: E402

# 条文脚注定义写入形态（CSM-OCR-014 执行侧，2026-09-06 修正）：回收的定义必须写成
# 前后空行隔离的 GFM 独立段——绝不粘连下一内容行（否则与下一条目并成一个多行段，
# parser 的“整行定义”形态无法归类，脚注以正文身份渲染），插入点越过锚点段空行带、
# 不落进列表条目序列中间。


def _lines(text: str) -> list[str]:
    return text.split("\n")


class FootnoteDefinitionPlacementTests(unittest.TestCase):
    def test_def_inserted_as_standalone_block_after_anchor(self) -> None:
        # 锚点段后是空行分隔的下一条目：定义插到锚点段之后、条目之前，前后空行隔离。
        text = "GB/T 20000.4—2003[^1]标准化工作指南\n\nGB/T 20001.4 标准编写规则\n"
        out = _place_footnote_definitions(text, [("1)", "1", "GB/T 20000.4—2003已修订。")])
        lines = _lines(out)
        i = lines.index("[^1]: GB/T 20000.4—2003已修订。")
        self.assertEqual(lines[i - 1].strip(), "")  # 前空行
        self.assertEqual(lines[i + 1].strip(), "")  # 后空行
        self.assertIn("GB/T 20001.4 标准编写规则", "\n".join(lines[i + 2:]))

    def test_glued_following_content_stays_separate(self) -> None:
        # 锚点段与后续行之间无空行（粘连输入）：定义行仍前后空行隔离、绝不吞内容行。
        text = "引用[^1]行。\n紧贴的内容行。\n"
        out = _place_footnote_definitions(text, [("1)", "1", "定义。")])
        lines = _lines(out)
        self.assertIn("紧贴的内容行", out)
        i = lines.index("[^1]: 定义。")
        self.assertEqual(lines[i - 1].strip(), "")  # 前空行
        self.assertEqual(lines[i + 1].strip(), "")  # 后空行（或文末空行）

    def test_def_not_inserted_inside_following_list(self) -> None:
        # 锚点段后跟列表：定义插在锚点段与列表之间，绝不落进列表条目序列中间。
        text = "6.4.2 该要素也可编制为单独的标准[^2]。\n\n- 条目一\n- 条目二\n\n后文。\n"
        out = _place_footnote_definitions(text, [("2)", "2", "这种情况属分类标准。")])
        lines = _lines(out)
        i = lines.index("[^2]: 这种情况属分类标准。")
        self.assertEqual(lines[i - 1].strip(), "")
        self.assertEqual(lines[i + 1].strip(), "")
        self.assertEqual(lines[i + 2], "- 条目一")  # 定义在列表之前
        self.assertEqual(lines[-2], "后文。")

    def test_idempotent_when_definition_already_present(self) -> None:
        text = "引用[^1]。\n\n[^1]: 已有定义。\n"
        out = _place_footnote_definitions(text, [("1)", "1", "重复定义。")])
        self.assertEqual(out, text)

    def test_no_anchor_marker_means_no_insertion(self) -> None:
        text = "没有标记的正文。\n\n后文。\n"
        out = _place_footnote_definitions(text, [("1)", "1", "定义。")])
        self.assertEqual(out, text)

    def test_residual_numbered_line_converted_in_place(self) -> None:
        # 半途产物 “N） 文本” 残留段：就地改前缀为 GFM 定义（自愈）。
        text = "正文[^1]尾部。\n\n1） 旧的页脚解释行\n"
        out = _place_footnote_definitions(text, [("1)", "1", "新定义")])
        self.assertIn("[^1]: 旧的页脚解释行", out)
        self.assertNotIn("1） 旧的页脚解释行", out)


if __name__ == "__main__":
    unittest.main()
