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
        'document-identifier: "GB/T 20001.10—2014"\n'
        'standard-number: "GB/T 20001.10—2014"\n'
        'title: "标准编写规则 第10部分：产品标准"\n'
        "language: zh-CN\n"
        "---\n\n"
        + body
    )
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "fixture.canonical.md"
        path.write_text(csm, encoding="utf-8")
        doc = CSMParser().read(path)
    return doc.blocks, doc.issues


def _dash_list_after(blocks, intro_text: str) -> list[dict]:
    """intro 段落之后的 list 块条目（marker/text）。"""
    for i, block in enumerate(blocks):
        if block.kind == "paragraph" and block.text.strip().startswith(intro_text):
            nxt = blocks[i + 1] if i + 1 < len(blocks) else None
            if nxt is not None and nxt.kind == "list":
                return nxt.data.get("items") or []
    return []


class ColonLedListRepairTests(unittest.TestCase):
    """CSM-OCR-016：冒号引导完整列项组的缺失 marker 补齐（完整性机制，非个例）。"""

    def test_last_dash_item_marker_restored(self) -> None:
        # 6.7.1.1 型：引导句冒号收尾，前三项带破折号、末项「形成标准的单独部分。」
        # 丢 marker 沦为普通段落 → 按幸存破折号补全为四项完整列表。
        body = (
            "## 6 要素的起草\n\n"
            "6.7.1.1 在标准中该要素可以：\n\n"
            "- 作为单独的章；\n\n"
            "- 融入技术要求(见6.5)中；\n\n"
            "- 成为标准的规范性附录；\n\n"
            "形成标准的单独部分。\n\n"
            "## 7 其他\n\n"
        )
        blocks, issues = _parse(body)
        self.assertTrue(any(i.code == "CSM-OCR-016" for i in issues))
        items = _dash_list_after(blocks, "6.7.1.1")
        self.assertEqual(
            [it["text"] for it in items],
            ["作为单独的章；", "融入技术要求（见6.5）中；", "成为标准的规范性附录；", "形成标准的单独部分。"],
        )
        self.assertTrue(all(it["marker"] for it in items))
        # 末项不再是游离段落
        self.assertFalse(any(b.kind == "paragraph" and "形成标准的单独部分" in b.text for b in blocks))

    def test_single_surviving_dash_marker_restores_group(self) -> None:
        # 6.4.3 型：三项里只有中间项幸存破折号 → 整组补齐为三项破折号列表。
        body = (
            "## 6 要素的起草\n\n"
            "6.4.3 产品分类的基本要求如下：\n\n"
            "划分的类别应满足使用的需要；\n\n"
            "— 应尽可能采用系列化的方法进行分类；\n\n"
            "对于系列产品应合理确定系列范围与疏密程度等，尽可能采用优先数和优先数系或模数制。\n\n"
            "6.4.4 其他说明文字。\n\n"
        )
        blocks, issues = _parse(body)
        self.assertTrue(any(i.code == "CSM-OCR-016" for i in issues))
        items = _dash_list_after(blocks, "6.4.3")
        self.assertEqual(len(items), 3)
        self.assertTrue(all(it["marker"] for it in items))

    def test_glued_first_item_is_split_off(self) -> None:
        # 6.4.4 型：引导句与首条粘连（“…内容：分类原则与方法；”）→ 按末个「：」
        # 拆出首条，连同后续幸存破折号条目与丢 marker 末条整组重建。
        body = (
            "## 6 要素的起草\n\n"
            "6.4.4 可根据产品不同的特性(如来源、结构、性能或用途等)进行分类。产品分类一般包括下述内容：分类原则与方法；\n\n"
            "— 划分的类别，如产品品种、型式(或型号)和规格及其系列；\n\n"
            "类别的识别，通常可用名称(一般由文字组成)、编码(一般由数字、字母或它们的组合而成)或标记(可由符号、字母、数字构成)进行识别。\n\n"
            "## 7 其他\n\n"
        )
        blocks, issues = _parse(body)
        self.assertTrue(any(i.code == "CSM-OCR-016" for i in issues))
        intro = next(b for b in blocks if b.kind == "paragraph" and "产品分类一般包括下述内容" in b.text)
        self.assertTrue(intro.text.strip().endswith("："))
        items = _dash_list_after(blocks, "6.4.4")
        self.assertEqual([it["text"] for it in items], ["分类原则与方法；", "划分的类别，如产品品种、型式（或型号）和规格及其系列；", "类别的识别，通常可用名称（一般由文字组成）、编码（一般由数字、字母或它们的组合而成）或标记（可由符号、字母、数字构成）进行识别。"])
        self.assertTrue(all(it["marker"] for it in items))

    def test_letter_family_markers_renumbered(self) -> None:
        # a)/1) 族：幸存 a） 与丢 marker 条目共存 → 按组序重排 a）b）c）。
        body = (
            "## 6 要素的起草\n\n"
            "适用时，含有产品标志内容的产品标准应规定：\n\n"
            "a） 用于识别产品的各种标志的内容；\n\n"
            "这类标志的表示方法；\n\n"
            "这类标志呈现在产品或包装上的位置。\n\n"
            "## 7 其他\n\n"
        )
        blocks, issues = _parse(body)
        self.assertTrue(any(i.code == "CSM-OCR-016" for i in issues))
        items = _dash_list_after(blocks, "适用时，含有产品标志内容的产品标准应规定")
        self.assertEqual([it["marker"] for it in items], ["a）", "b）", "c）"])

    def test_single_follow_up_paragraph_is_not_a_list(self) -> None:
        # 冒号后仅一段续文（非条目组）→ 不动。
        body = "## 6 要素的起草\n\n本标准应规定：\n\n本标准适用于电器产品的检验。\n\n## 7 其他\n\n"
        blocks, issues = _parse(body)
        self.assertFalse(any(i.code == "CSM-OCR-016" for i in issues))

    def test_no_surviving_marker_is_not_guessed(self) -> None:
        # 组内无幸存 marker（无法确定族）→ 保守不猜。
        body = (
            "## 6 要素的起草\n\n"
            "产品分类的基本要求如下：\n\n"
            "划分的类别应满足使用的需要；\n\n"
            "应尽可能采用系列化的方法进行分类；\n\n"
            "对于系列产品应合理确定系列范围。\n\n"
            "## 7 其他\n\n"
        )
        blocks, issues = _parse(body)
        self.assertFalse(any(i.code == "CSM-OCR-016" for i in issues))

    def test_list_final_item_ends_group_not_following_prose(self) -> None:
        # A.1 型：丢 marker 首条 + 幸存破折号末条（「。」收尾），其后是无关散文段——
        # list 末条「。」收尾即组完整，后续散文不得并入组（否则完整性校验失败漏修）。
        body = (
            "## A.1 检验分类\n\n"
            "根据行业和产品特点可选择下列一类或多类检验：\n\n"
            "型式检验(例行检验)、定型检验(鉴定检验)、首件检验等；\n\n"
            "— 出厂检验(常规检验、交收检验)、质量一致性检验等。\n\n"
            "可供选择的检验分类组合示例如下。\n\n"
            "示例1：型式检验(或例行检验)、出厂检验(或交收检验)。\n\n"
        )
        blocks, issues = _parse(body)
        self.assertTrue(any(i.code == "CSM-OCR-016" for i in issues))
        items = _dash_list_after(blocks, "根据行业和产品特点可选择下列一类或多类检验")
        self.assertEqual(
            [it["text"] for it in items],
            ["型式检验（例行检验）、定型检验（鉴定检验）、首件检验等；", "出厂检验（常规检验、交收检验）、质量一致性检验等。"],
        )
        self.assertTrue(all(it["marker"] for it in items))
        # 后续散文仍是独立段落
        self.assertTrue(any(b.kind == "paragraph" and b.text.startswith("可供选择") for b in blocks))

    def test_complete_list_is_untouched(self) -> None:
        # marker 齐全的列表 → 不重建不重复记录。
        body = (
            "## 6 要素的起草\n\n"
            "在标准中该要素可以：\n\n"
            "- 作为单独的章；\n\n"
            "- 融入技术要求中；\n\n"
            "- 成为标准的规范性附录。\n\n"
            "## 7 其他\n\n"
        )
        blocks, issues = _parse(body)
        self.assertFalse(any(i.code == "CSM-OCR-016" for i in issues))

    def test_mid_list_new_colon_intro_stops_group(self) -> None:
        # 组中间出现新冒号引导句（非条目）→ 截断不猜（防跨引导误并）。
        body = (
            "## 6 要素的起草\n\n"
            "分类方法如下：\n\n"
            "— 第一类；\n\n"
            "分级规则：\n\n"
            "其他说明。\n\n"
            "## 7 其他\n\n"
        )
        blocks, issues = _parse(body)
        self.assertFalse(any(i.code == "CSM-OCR-016" for i in issues))

    def test_group_survives_interior_period_inside_marked_list(self) -> None:
        # GB_T_5171.1-2014 前言型：整组清单是一个列项组，源文中间一条误用「。」
        # （PDF 文本层真值如此），且大量中间条目丢 marker 沦为普通段落。组尾不能
        # 只看首个「。」：标记列表块末条「。」之后仍是强条目（「；」条目）即说明
        # 该「。」属组中偶发，组继续吸收，直到末条「。」之后不再有强条目。
        body = (
            "## 前 言\n\n"
            "本部分与 GB/T 5171—2002 相比，主要变化如下：\n\n"
            "- 修改了适用的范围；\n\n"
            "- 增加了第3章“术语和定义”；\n\n"
            "- 增加了第9章“结构要求”。\n\n"
            "增加了10.2.4对电动机能效标识的要求；\n\n"
            "增加了11.1温升试验的表述；\n\n"
            "- 增加了12.3对所有非特定用途电动机考核其工作特性应提供三点的效率数据的要求；\n\n"
            "增加了13.3.2.2试验电压中对于带有信号控制的电动机试验电压的方式和限值：\n\n"
            "增加了13.5匝间电气强度试验内容；\n\n"
            "- 增加了附录B“电动机的选用”。\n\n"
            "本部分由中国电器工业协会提出。\n\n"
            "本部分由全国旋转电机标准化技术委员会(SAC/TC26)归口。\n\n"
        )
        blocks, issues = _parse(body)
        self.assertTrue(any(i.code == "CSM-OCR-016" for i in issues))
        items = _dash_list_after(blocks, "本部分与 GB/T 5171—2002 相比")
        # 整条清单（含中间丢 marker 的普通段落）收敛为一个 list 块。
        self.assertEqual(len(items), 9)
        self.assertTrue(all(it["marker"] for it in items))
        # 中间「；」被 OCR 读成「：」的条目按列项结构归一为「；」。
        self.assertEqual(items[6]["text"], "增加了13.3.2.2试验电压中对于带有信号控制的电动机试验电压的方式和限值；")
        # 组内符号一致（OCR 长度变体按多数派归一）。
        self.assertEqual(len({it["marker"] for it in items}), 1)
        # 组尾正确收在末条「。」：其后归口/提出段落不得并入组。
        self.assertTrue(items[-1]["text"].endswith("。"))
        self.assertTrue(any(b.kind == "paragraph" and b.text.startswith("本部分由中国电器工业协会提出") for b in blocks))
        self.assertTrue(any(b.kind == "paragraph" and b.text.startswith("本部分由全国旋转电机") for b in blocks))

    def test_interior_colon_terminator_normalised_only_when_run_continues(self) -> None:
        # 条目末「；」被 OCR 读成「：」：其后仍续有强条目（「；」条目）时按条目吸收并
        # 归一为「；」；其后不是强条目（散文/组尾）时按新引语截断不猜。
        continuing = (
            "## 6 要素的起草\n\n"
            "尺寸系列如下：\n\n"
            "— 第一系列的尺寸；\n\n"
            "增加了第二系列的尺寸：\n\n"
            "增加了第三系列的尺寸；\n\n"
            "— 第四系列的尺寸。\n\n"
            "## 7 其他\n\n"
        )
        blocks, issues = _parse(continuing)
        self.assertTrue(any(i.code == "CSM-OCR-016" for i in issues))
        items = _dash_list_after(blocks, "尺寸系列如下")
        self.assertEqual(
            [it["text"] for it in items],
            ["第一系列的尺寸；", "增加了第二系列的尺寸；", "增加了第三系列的尺寸；", "第四系列的尺寸。"],
        )
        self.assertTrue(all(it["marker"] for it in items))

        # 反向：同一「：」段落后紧跟组尾（「。」条目）→ 按新引语截断，不吸收不重建。
        stopped = (
            "## 6 要素的起草\n\n"
            "尺寸系列如下：\n\n"
            "— 第一系列的尺寸；\n\n"
            "增加了第二系列的尺寸：\n\n"
            "— 第三系列的尺寸。\n\n"
            "## 7 其他\n\n"
        )
        blocks, issues = _parse(stopped)
        self.assertFalse(any(i.code == "CSM-OCR-016" for i in issues))

    def test_marked_list_period_tail_stops_when_next_is_prose(self) -> None:
        # 反向：标记列表块末条「。」之后不是强条目（普通散文段）→ 组在此收尾，
        # 其后散文不得并入组（A.1 型判型不得因组中偶发「。」支持而被放宽）。
        body = (
            "## A.1 检验分类\n\n"
            "根据行业和产品特点可选择下列一类或多类检验：\n\n"
            "型式检验(例行检验)、定型检验(鉴定检验)、首件检验等；\n\n"
            "— 出厂检验(常规检验、交收检验)、质量一致性检验等。\n\n"
            "可供选择的检验分类组合示例如下。\n\n"
            "示例1：型式检验(或例行检验)、出厂检验(或交收检验)。\n\n"
        )
        blocks, issues = _parse(body)
        self.assertTrue(any(i.code == "CSM-OCR-016" for i in issues))
        items = _dash_list_after(blocks, "根据行业和产品特点可选择下列一类或多类检验")
        self.assertEqual(len(items), 2)
        self.assertTrue(any(b.kind == "paragraph" and b.text.startswith("可供选择") for b in blocks))


if __name__ == "__main__":
    unittest.main()
