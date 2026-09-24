"""CSM-OCR-017/018：公式编号与公式变量解释（GB/T 1.1-2020 9.9.2/9.9.3/10.4.3）。

- CSM-OCR-017：MinerU 把公式行的「…………(1)」引导线连编号一起识别成 LaTeX
  ``\\tag{...}``（常缺右花括号），编号因此从未进入 SSIR；本规则把编号读出来、
  清掉残留，并做**全文档编号管理**（正文 1..n 连续、附录内重新编号加字母前缀）。
- CSM-OCR-018：公式下方「式中：」的变量解释项固定形态 = 变量 + 破折号 + 解释 +
  分号（末项句号）；OCR 常丢破折号、压短破折号或漏终止符（GB_T_5171.1-2014 式(1)/
  式(2) 型）。整组归一（与 CSM-OCR-016 列项组管理同构），不重排、不改解释文字。
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from leleby_ssir.parser import CSMParser


def _parse(body: str):
    csm = (
        "---\n"
        'csm-version: "1.0"\n'
        "document-type: standard\n"
        'document-identifier: "GB/T 5171.1—2014"\n'
        'standard-number: "GB/T 5171.1—2014"\n'
        'title: "小功率电动机 第1部分：通用技术条件"\n'
        "language: zh-CN\n"
        "---\n\n"
        + body
    )
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "fixture.canonical.md"
        path.write_text(csm, encoding="utf-8")
        doc = CSMParser().read(path)
    return doc.blocks, doc.issues


def _formulas(blocks):
    return [block for block in blocks if block.kind == "formula"]


def _paragraph_texts(blocks):
    return [block.text for block in blocks if block.kind == "paragraph"]


class FormulaNumberRepairTests(unittest.TestCase):
    """CSM-OCR-017：\\tag 引导线残留 → 编号提取 + 全文档编号管理（GBT-X06）。"""

    def test_tag_residue_yields_number_and_clean_latex(self) -> None:
        body = (
            "## 11 温升试验\n\n"
            "11.3.1.3 绕组温升可由式(1)计算求得：\n\n"
            '<!-- ssir:formula id="mineru-formula-p001-001" asset-ref="assets/images/eq1.jpg" -->\n'
            "$$\n"
            "\\Delta t = \\frac { R _ { 2 } - R _ { 1 } } { R _ { 1 } } ( k + t _ { 1 } )\\tag{……………………(1}\n"
            "$$\n\n"
        )
        blocks, issues = _parse(body)
        formula = _formulas(blocks)[0]
        self.assertEqual(formula.data.get("number"), "1")
        self.assertNotIn("\\tag", formula.text)
        self.assertTrue(formula.text.endswith("t _ { 1 } )"))
        self.assertTrue(any(i.code == "CSM-OCR-017" and i.repaired for i in issues))

    def test_well_formed_number_line_is_parsed_without_issue(self) -> None:
        # 标准 CSM 编号行「式（1）」只是解析出编号标签，同表题「**表N 题名**」，
        # 不算修复、不记 issue（干净夹具必须保持零发现）。
        body = (
            "## 6 试验方法\n\n"
            "按式（1）计算效率。\n\n"
            '<!-- ssir:formula id="fm-001" -->\n'
            "$$\n"
            "eta = P_{out} / P_{in} \\times 100\n"
            "$$\n"
            "式（1）\n\n"
        )
        blocks, issues = _parse(body)
        self.assertEqual(_formulas(blocks)[0].data.get("number"), "1")
        self.assertFalse(any(i.code == "CSM-OCR-017" for i in issues))

    def test_number_sequence_is_managed_document_wide(self) -> None:
        # 全文档编号管理：正文公式编号自 1 连续；抽取到的编号与序列位置不符时
        # 如实报出（不改写抽取值）——这是「全局编号管理」的执行面。
        body = (
            "## 12 效率\n\n"
            "按式(1)计算。\n\n"
            '<!-- ssir:formula id="fm-001" -->\n$$\na = b\n$$\n式(1)\n\n'
            "按式(3)计算。\n\n"
            '<!-- ssir:formula id="fm-002" -->\n$$\nc = d\n$$\n式(3)\n\n'
        )
        blocks, issues = _parse(body)
        formulas = _formulas(blocks)
        self.assertEqual([f.data.get("number") for f in formulas], ["1", "3"])
        mismatches = [i for i in issues if i.code == "CSM-OCR-017" and not i.repaired]
        self.assertEqual(len(mismatches), 1)
        self.assertIn("应为 (2)", mismatches[0].message)

    def test_annex_scope_restarts_numbering_with_letter_prefix(self) -> None:
        body = (
            "## 16 性能要求\n\n"
            "按式(1)计算。\n\n"
            '<!-- ssir:formula id="fm-001" -->\n$$\na = b\n$$\n式(1)\n\n'
            "## 附录 A（资料性） 应用工序能力指数分析\n\n"
            "A.2 工序能力指数：\n\n"
            '<!-- ssir:formula id="fm-002" -->\n$$\nC_p = T / 6 s\n$$\n式(A.1)\n\n'
        )
        blocks, issues = _parse(body)
        formulas = _formulas(blocks)
        self.assertEqual([f.data.get("number") for f in formulas], ["1", "A.1"])
        # 附录内重新从 1 起算并加字母前缀 → 与序列一致，无发现。
        self.assertFalse(any(i.code == "CSM-OCR-017" and not i.repaired for i in issues))

    def test_unnumbered_formula_stays_unnumbered(self) -> None:
        # 9.9.2 只在需要引用或提示时才要求编号；抽取没有编号不得填补（不伪造）。
        body = (
            "## 附录 A（资料性） 应用工序能力指数分析\n\n"
            "A.2 常用的符号有：\n\n"
            '<!-- ssir:formula id="fm-001" -->\n$$\nC_p = T / 6 s\n$$\n\n'
        )
        blocks, issues = _parse(body)
        self.assertFalse(str(_formulas(blocks)[0].data.get("number") or "").strip())
        self.assertFalse(any(i.code == "CSM-OCR-017" for i in issues))


class FormulaVariableLineRepairTests(unittest.TestCase):
    """CSM-OCR-018：「式中：」变量解释项固定形态归一（GBT-X06）。"""

    def test_lost_and_short_dashes_are_restored_with_terminators(self) -> None:
        # GB_T_5171.1-2014 式(1) 实测：6 项里 2 项破折号被压成单个「—」、
        # 2 项破折号整段丢失；末项句号齐全。
        body = (
            "## 11 温升试验\n\n"
            "$$\n\\Delta t = x\n$$\n式(1)\n\n"
            "式中：\n\n"
            "$\\Delta t$ ——绕组温升，单位为开尔文(K)；\n\n"
            "$R _ { 2 }$ —试验结束时的绕组电阻，单位为欧姆(Ω)；\n\n"
            "$k$ 常数，对铜绕组为234.5；\n\n"
            "$t _ { 1 }$ 试验开始时的绕组温度，单位为摄氏度(℃)；\n\n"
            "$t _ { 2 }$ —试验结束时的冷却介质温度，单位为摄氏度(℃)。\n\n"
        )
        blocks, issues = _parse(body)
        texts = _paragraph_texts(blocks)
        self.assertIn("$\\Delta t$——绕组温升，单位为开尔文（K）；", texts)
        self.assertIn("$R _ { 2 }$——试验结束时的绕组电阻，单位为欧姆（Ω）；", texts)
        self.assertIn("$k$——常数，对铜绕组为234.5；", texts)
        self.assertIn("$t _ { 2 }$——试验结束时的冷却介质温度，单位为摄氏度（℃）。", texts)
        self.assertTrue(any(i.code == "CSM-OCR-018" and i.repaired for i in issues))

    def test_missing_terminators_are_added_last_item_gets_period(self) -> None:
        # GB_T_5171.1-2014 式(2) 实测：两项缺终止符（末项应为句号）。
        body = (
            "## 16 性能要求\n\n"
            "$$\nJ = x\n$$\n式(2)\n\n"
            "式中：\n\n"
            "J ——负载的标称转动惯量，单位为千克二次方米\n\n"
            "$P _ { \\mathrm { ~ N ~ } }$ ——电动机的额定功率，单位为瓦(W)；\n\n"
            "$n _ { \\mathrm { ~ N ~ } }$ —电动机的同步转速，单位为转每分\n\n"
        )
        blocks, _ = _parse(body)
        texts = _paragraph_texts(blocks)
        self.assertIn("J——负载的标称转动惯量，单位为千克二次方米；", texts)
        self.assertIn("$P _ { \\mathrm { ~ N ~ } }$——电动机的额定功率，单位为瓦（W）；", texts)
        self.assertIn("$n _ { \\mathrm { ~ N ~ } }$——电动机的同步转速，单位为转每分。", texts)

    def test_wrong_terminator_is_normalised(self) -> None:
        body = (
            "## 16 性能要求\n\n$$\nJ = x\n$$\n式(2)\n\n"
            "式中：\n\n"
            "J ——负载的标称转动惯量：\n\n"
            "$P _ { \\mathrm { ~ N ~ } }$ ——电动机的额定功率，单位为瓦(W)。\n\n"
        )
        blocks, _ = _parse(body)
        texts = _paragraph_texts(blocks)
        self.assertIn("J——负载的标称转动惯量；", texts)
        self.assertIn("$P _ { \\mathrm { ~ N ~ } }$——电动机的额定功率，单位为瓦（W）。", texts)

    def test_existing_period_inside_group_is_not_forced_to_semicolon(self) -> None:
        # 组内已有的「。」可能是示例边界（GB/T 1.1-2020 9.9.3.2 的"正确/不正确"
        # 对照示例），不强制改成分号。
        body = (
            "## 9 数学公式\n\n$$\nt_i = \\sqrt{x}\n$$\n\n"
            "式中：\n\n"
            "$t _ { i }$——系统i 的统计量；\n\n"
            "MSEi——系统 i 的残差均方；\n\n"
            "$S _ { \\mathrm { M R } , i }$——系统i由于回归产生的均方。\n\n"
            "MSRi——系统 i 由于回归产生的均方。\n\n"
        )
        blocks, _ = _parse(body)
        texts = _paragraph_texts(blocks)
        self.assertIn("$S _ { \\mathrm { M R } , i }$——系统i由于回归产生的均方。", texts)
        self.assertIn("MSRi——系统 i 由于回归产生的均方。", texts)

    def test_single_item_group_is_left_alone(self) -> None:
        body = (
            "## 9 数学公式\n\n$$\nv = x\n$$\n\n"
            "式中：\n\n"
            "$v$ ——匀速运动质点的速度。\n\n"
            "特殊情况下，数学公式如果使用了数值关系式，应解释表示数值的符号。\n\n"
        )
        blocks, issues = _parse(body)
        self.assertIn("$v$ ——匀速运动质点的速度。", _paragraph_texts(blocks))
        self.assertFalse(any(i.code == "CSM-OCR-018" for i in issues))

    def test_latin_led_paragraph_outside_intro_is_untouched(self) -> None:
        # 没有「式中：」锚点（或不在其后）的拉丁字母开头段落不得被改写。
        body = (
            "## 9 数学公式\n\n"
            "GB/T 1.1—2020 规定如下：\n\n"
            "P ——功率，单位为瓦(W)；\n\n"
        )
        blocks, issues = _parse(body)
        self.assertIn("P ——功率，单位为瓦（W）；", _paragraph_texts(blocks))
        self.assertFalse(any(i.code == "CSM-OCR-018" for i in issues))


if __name__ == "__main__":
    unittest.main()
