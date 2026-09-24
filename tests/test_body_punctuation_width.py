"""正文半角标点 → 全角（GEN-138；docs/12 §3.87）的回归夹具。

判据单源：`parser.normalise_body_punctuation`（含句末句号守卫、括号成对/混配、
行内公式与指令的掩码）。载体覆盖：块文本（段落/标题）、列项条目、表格单元格；
公式块与 ` ```text ` 未知块保留原文。front matter 与 `<!-- ssir:…-->` 指令是
语法而非文字，必须**逐字节不变**（否则复现 docs/12 §3.86 事故）。
"""

from __future__ import annotations

import pathlib
import tempfile
import unittest

from leleby_ssir.parser import CSMParser, normalise_body_punctuation

FRONT_MATTER = """---
csm-version: "1.0"
document-type: standard
document-identifier: "GB/T 1.1-2020"
standard-number: "GB/T 1.1-2020"
title: "标点宽度夹具"
language: zh-CN
source:
  mode: user-markdown
  original-file-name: "fixture.md"
  provenance: none
rendering-profile: GB_T_1.1-2020
extensions:
  standard-profile: product
---
"""


def _parse(body: str):
    text = FRONT_MATTER + "\n" + body.lstrip("\n")
    with tempfile.TemporaryDirectory() as tmp:
        path = pathlib.Path(tmp) / "fixture.canonical.md"
        path.write_text(text, encoding="utf-8", newline="\n")
        document = CSMParser().read(path)
    assert document.text == text, "读取不得改动输入文本（front matter/指令原样）"
    return document


class BodyPunctuationTest(unittest.TestCase):
    def test_half_width_punctuation_next_to_han_becomes_full_width(self) -> None:
        text, count = normalise_body_punctuation(
            "变频电源供电,并可通过频率改变来调节转速;电压不高于 80℃?是?"
        )
        self.assertEqual(text, "变频电源供电，并可通过频率改变来调节转速；电压不高于 80℃？是？")
        self.assertEqual(count, 4)

    def test_full_width_stays_and_is_idempotent(self) -> None:
        source = "本标准由全国标准化技术委员会（SAC/TC2）归口，见第5章。"
        self.assertEqual(normalise_body_punctuation(source), (source, 0))

    def test_ascii_context_is_untouched(self) -> None:
        for source in (
            "GB/T 1.1-2020 与 IEC 60050:2015 等同。",
            "额定电压 1,000 V; 频率 50 Hz.",  # 半角逗号在千分位、句号前是拉丁字母
            "m/s、0.5 mm、80%～90%、5 V±2%",
            "https://example.org/a,b?c=d",
        ):
            self.assertEqual(normalise_body_punctuation(source), (source, 0), source)

    def test_period_guard_keeps_toc_dots_and_decimals(self) -> None:
        for source in (
            "1 范围.... 1",
            "4.6.1 电动机",
            "附录 A.1 概述",
        ):
            self.assertEqual(normalise_body_punctuation(source), (source, 0), source)
        text, count = normalise_body_punctuation("本文件界定了术语。本标准归口.")
        self.assertEqual(text, "本文件界定了术语。本标准归口。")
        self.assertEqual(count, 1)
        # 行尾句号（含其后空白）才转；行中句号保留
        self.assertEqual(normalise_body_punctuation("本标准归口. 本文件由…")[0], "本标准归口. 本文件由…")
        # 引用文件/参考文献条目的分隔点号（GB/T 7714）保留，中文语境的逗号仍转
        reference = "国际计量局.国际单位制（SI）（第9版）,2019."
        text, _ = normalise_body_punctuation(reference)
        self.assertEqual(text, "国际计量局.国际单位制（SI）（第9版），2019.")

    def test_parentheses_convert_as_a_pair_only(self) -> None:
        cases = {
            "本标准由全国标准化技术委员会(SAC/TC2)归口。": "本标准由全国标准化技术委员会（SAC/TC2）归口。",
            "见(see 4.2)规定。": "见（see 4.2）规定。",
            "| 额定励磁电压 (交流有效值或直流值)V |": "| 额定励磁电压 （交流有效值或直流值）V |",
        }
        for source, expected in cases.items():
            self.assertEqual(normalise_body_punctuation(source)[0], expected, source)
        # 纯拉丁语境与单侧无法配对时不转换
        for source in ("foo (bar) baz", "abc(def)ghi", "列出(未闭合"):
            self.assertEqual(normalise_body_punctuation(source), (source, 0), source)

    def test_mixed_width_parenthesis_pairs_are_unified(self) -> None:
        for source, expected in (
            ("附录 C(资料性） 产品试验记录", "附录 C（资料性） 产品试验记录"),
            ("噪声不大于68dB（A)。", "噪声不大于68dB（A）。"),
        ):
            self.assertEqual(normalise_body_punctuation(source)[0], expected, source)

    def test_inline_math_and_directives_are_masked(self) -> None:
        source = "由 $S_{\\mathrm{ME},i}$ 计算,结果见式(1)。"
        text, _ = normalise_body_punctuation(source)
        self.assertEqual(text, "由 $S_{\\mathrm{ME},i}$ 计算，结果见式（1）。")
        self.assertIn("S_{\\mathrm{ME},i}", text)
        directive = "<!-- ssir:table id=\"t1\" header-rows=\"1\" caption-number=\"4\" -->"
        self.assertEqual(normalise_body_punctuation(directive), (directive, 0))

    def test_formula_block_and_code_fence_keep_original_text(self) -> None:
        document = _parse(
            "$$\nE = mc^2, \\quad x_{1}\n$$\n\n"
            "式(1)\n\n"
            '<!-- ssir:unknown id="u1" -->\n\n```text\n原文,保留 (a)\n```\n'
        )
        formula = next(block for block in document.blocks if block.kind == "formula")
        self.assertIn("E = mc^2, \\quad x_{1}", formula.text)
        unknown = next(block for block in document.blocks if block.kind == "unknown")
        self.assertEqual(unknown.text, "原文,保留 (a)")  # 未知块保留原文（GEN-052）

    def test_carriers_block_text_list_items_and_table_cells(self) -> None:
        document = _parse(
            "# 测试标准 第1部分:通用技术条件\n\n"
            "本标准由全国标准化技术委员会(SAC/TC2)归口,电压不高于 80℃.\n\n"
            "| 序号 | 项目 | 结果 |\n"
            "| --- | --- | --- |\n"
            "| 1 | 径向间隙[foot:a] | √ |\n"
            "| 2 | 额定电压 (交流有效值)V | 220 |\n\n"
            "a) 列项文本,后续\n"
        )
        heading = next(block for block in document.blocks if block.kind == "heading")
        self.assertEqual(heading.text, "测试标准 第1部分：通用技术条件")
        paragraph = next(block for block in document.blocks if block.kind == "paragraph")
        self.assertEqual(paragraph.text, "本标准由全国标准化技术委员会（SAC/TC2）归口，电压不高于 80℃.")
        table = next(block for block in document.blocks if block.kind == "table")
        self.assertEqual(table.data["rows"][2][1], "额定电压 （交流有效值）V")
        item = next(block for block in document.blocks if block.kind == "list").data["items"][0]
        self.assertEqual(item["text"], "列项文本，后续")
        self.assertEqual(item["marker"], "a）")  # 列表标记由 GBT-C19 判据单独处理

    def test_front_matter_and_directives_survive_parsing(self) -> None:
        document = _parse(
            "<!-- ssir:table id=\"t1\" header-rows=\"1\" -->\n\n"
            "| 序号 | 项目 |\n"
            "| --- | --- |\n"
            "| 1 | 间隙,偏差 |\n"
        )
        self.assertEqual(document.metadata["csm-version"], "1.0")
        self.assertEqual(document.metadata["document-identifier"], "GB/T 1.1-2020")
        table = next(block for block in document.blocks if block.kind == "table")
        self.assertEqual(table.directive.attrs["header-rows"], "1")
        self.assertEqual(table.directive.name, "table")


if __name__ == "__main__":
    unittest.main()
