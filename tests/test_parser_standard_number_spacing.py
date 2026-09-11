"""CSM-OCR-004 标准号间隔：规则必须覆盖正文的**全部文本载体**。

背景（2026-09-11，用户报告）：GB_T_1.1-2020 前言里的版本发布行写成
「GB/T1.2—1996」——标准号的文件代号与顺序号之间丢了空格。根因是修复只作用于
``block.text``，而「列项条目」「表格单元格」里的文本分别存在 ``data.items`` /
``data.rows``，旧实现里的 list 分支写在 ``if block.kind not in ("paragraph",
"heading"): continue`` **之后**（永不执行）。同一处还把无斜杠分支写成
``[A-Z]{2,4}(?=[0-9])``，任何字母数字串都会中招，落到列项/单元格载体上会拆开
RS485、AC1 500 V 这类非标准号——本文件的负例就是为守住这一点。
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from leleby_ssir.parser import CSMParser, restore_standard_number_spacing


def _parse(body: str):
    csm = (
        "---\n"
        'csm-version: "1.0"\n'
        "document-type: standard\n"
        'document-identifier: "GB/T 1.1—2020"\n'
        'standard-number: "GB/T 1.1—2020"\n'
        'title: "标准化工作导则 第1部分：标准化文件的结构和起草规则"\n'
        "language: zh-CN\n"
        "---\n\n"
        + body
    )
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "fixture.canonical.md"
        path.write_text(csm, encoding="utf-8")
        doc = CSMParser().read(path)
    return doc.blocks, doc.issues


class StandardNumberSpacingUnitTests(unittest.TestCase):
    """规则本体：正例的每一种代号形态 + 近负例不得改动。"""

    def test_inserts_gap_after_every_designator_form(self) -> None:
        cases = {
            "并入了GB/T1.2—1996《标准化工作导则》": "并入了GB/T 1.2—1996《标准化工作导则》",
            "首次发布为GB1.1—1981": "首次发布为GB 1.1—1981",
            "按DB11/T1000.1—2020执行": "按DB11/T 1000.1—2020执行",
            "见T/ZZB1064—2019": "见T/ZZB 1064—2019",
            "见Q/XKBZ002—2026": "见Q/XKBZ 002—2026",
            "等同ISO9001": "等同ISO 9001",
            "按IEC60027执行": "按IEC 60027执行",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(restore_standard_number_spacing(source), expected)

    def test_leaves_non_standard_alnum_runs_alone(self) -> None:
        cases = [
            "RS485 接口通信试验",           # 总线名，不是标准号
            "电压调到AC1 500 V",            # 代号 + 量值
            "维生素B1",                     # 单字母前缀
            "SAC/TC286",                    # 斜杠前导（标准化技术委员会）
            "系统kV1 档",                   # 小写缩写
            "GB/T 1.1—2020",                # 已有间隔 → 幂等
        ]
        for source in cases:
            with self.subTest(source=source):
                self.assertEqual(restore_standard_number_spacing(source), source)


class StandardNumberSpacingCarrierTests(unittest.TestCase):
    """载体覆盖：段落 / 列项条目 / 表格单元格都要修，且规则码为 CSM-OCR-004。"""

    def test_paragraph_and_list_item_and_table_cell_are_repaired(self) -> None:
        body = (
            "## 前言\n\n"
            "本文件及其所代替文件的历次版本发布情况为：\n\n"
            "—— 2009年第四次修订时，并入了GB/T1.2—2002《标准化工作导则》的内容；\n"
            "—— 本次为第五次修订。\n\n"
            "## 2 规范性引用文件\n\n"
            "下列文件对于本文件的应用是必不可少的，均应使用GB/T1.1—2020的版本。\n\n"
            "| 试验项目 | 引用文件 |\n"
            "| --- | --- |\n"
            "| 静电放电 | GB/T17626.2 |\n\n"
        )
        blocks, issues = _parse(body)
        self.assertTrue(any(i.code == "CSM-OCR-004" for i in issues))

        item_texts = [
            item["text"]
            for block in blocks
            if block.kind == "list"
            for item in block.data.get("items", [])
        ]
        self.assertIn("2009年第四次修订时，并入了GB/T 1.2—2002《标准化工作导则》的内容；", item_texts)

        paragraph_texts = [b.text for b in blocks if b.kind == "paragraph"]
        self.assertTrue(any("GB/T 1.1—2020的版本" in text for text in paragraph_texts))

        rows = [row for block in blocks if block.kind == "table" for row in block.data.get("rows", [])]
        self.assertIn(["静电放电", "GB/T 17626.2"], rows)

    def test_non_standard_alnum_runs_inside_list_and_cell_survive(self) -> None:
        body = (
            "## 8 试验方法\n\n"
            "—— 通信接口：RS485，波特率9600；\n"
            "—— 电源：AC1 500 V。\n\n"
            "| 项目 | 参数 |\n"
            "| --- | --- |\n"
            "| 接口 | RS485 |\n\n"
        )
        blocks, issues = _parse(body)
        self.assertFalse(any(i.code == "CSM-OCR-004" for i in issues), [i.message for i in issues])
        item_texts = [
            item["text"]
            for block in blocks
            if block.kind == "list"
            for item in block.data.get("items", [])
        ]
        self.assertEqual(item_texts, ["通信接口：RS485，波特率9600；", "电源：AC1 500 V。"])
        rows = [row for block in blocks if block.kind == "table" for row in block.data.get("rows", [])]
        self.assertIn(["接口", "RS485"], rows)

    def test_rule_is_idempotent(self) -> None:
        body = (
            "## 前言\n\n"
            "—— 并入了GB/T1.2—2002《标准化工作导则》的内容；\n\n"
        )
        csm = (
            "---\n"
            'csm-version: "1.0"\n'
            "document-type: standard\n"
            'document-identifier: "GB/T 1.1—2020"\n'
            'standard-number: "GB/T 1.1—2020"\n'
            'title: "标准化工作导则"\n'
            "language: zh-CN\n"
            "---\n\n"
            + body
        )
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.canonical.md"
            second = Path(directory) / "second.canonical.md"
            first.write_text(csm, encoding="utf-8")
            # 第一次解析（记录修复）→ 把修复后的文本落盘 → 第二次解析不得再命中。
            doc = CSMParser().read(first)
            repaired = doc.text.replace("GB/T1.2—2002", "GB/T 1.2—2002")
            self.assertNotEqual(repaired, doc.text)
            second.write_text(repaired, encoding="utf-8")
            again = CSMParser().read(second)
        self.assertFalse(any(i.code == "CSM-OCR-004" for i in again.issues))


if __name__ == "__main__":
    unittest.main()
