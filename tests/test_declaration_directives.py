"""声明型指令回归（docs/15 §2.2/§3.7/§3.8）：`ssir:figure-legend` / `ssir:figure-sub` /
`ssir:formula-vars`。

规则（本轮新增，parser 侧单一判据 + builder 侧归属）：
- 指令行后的**连续非空行**即条目，终止于空行/下一个指令/标题/围栏/表行/引语/图片行；
- 条目落目标元素字段（`Figure.legend` / `Figure.subCaptions` / `Formula.explanationGroup`），
  **不产生内容元素**（不属于文本流，故不参与段落判型）；
- 归属优先 `figure=` / `formula=` 指定的指令 id，缺省取最近一个图/公式；无法归属时登记
  `qualityAssessments.comments`（不猜、不丢）。
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import textwrap
import unittest

from leleby_ssir.service import parse_csm
from leleby_ssir.validation import validate_ssir

FRONT_MATTER = """\
---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/XYZ 001—2026"
standard-number: "Q/XYZ 001—2026"
title: "声明型指令夹具"
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

# 声明型指令夹具

## 1 范围

本文档用于声明型指令回归。

![图1 结构示意](assets/fig1.png)

<!-- ssir:figure id="fig-001" -->

<!-- ssir:figure-legend figure="fig-001" -->
1——气隙；

2——定子绕组。

<!-- ssir:figure-sub figure="fig-001" -->
a）局部剖面

b）整体装配

<!-- ssir:formula id="fm-001" -->
$$
\\overline{\\eta} = \\dfrac{\\overline{P}_{2}}{\\overline{P}_{1}}
$$
式(1)

<!-- ssir:formula-vars formula="fm-001" -->
$\\overline{\\eta}$——传动效率；

$\\overline{P}_{1}$——输入端功率算术平均值，单位为千瓦（kW）。
"""


TOC_DECLARATION = """\
<!-- ssir:toc -->
前言 …… V

1 范围……………………1

3.1 文件……………2

附录 A（规范性） 试验记录…………10
<!-- ssir:/toc -->

后面的正文段落。
"""


def _parse(text: str):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "doc.canonical.md"
        path.write_text(textwrap.dedent(text), encoding="utf-8")
        return parse_csm(path)


class DeclarationDirectiveTests(unittest.TestCase):
    def test_figure_legend_and_sub_captions_attach_to_declared_figure(self) -> None:
        ssir = _parse(FRONT_MATTER)
        validate_ssir(ssir)
        self.assertEqual(len(ssir["figures"]), 1)
        figure = ssir["figures"][0]
        self.assertEqual(figure["legend"], [
            {"index": "1", "text": "气隙"},
            {"index": "2", "text": "定子绕组"},
        ])
        self.assertEqual(figure["subCaptions"], [
            {"label": "a", "text": "局部剖面"},
            {"label": "b", "text": "整体装配"},
        ])

    def test_formula_explanation_group_attaches_with_unit(self) -> None:
        ssir = _parse(FRONT_MATTER)
        self.assertEqual(len(ssir["formulas"]), 1)
        group = ssir["formulas"][0]["explanationGroup"]
        self.assertEqual(group["items"][0], {
            "symbol": "$\\overline{\\eta}$", "definition": "传动效率", "terminator": "；",
        })
        second = group["items"][1]
        self.assertEqual(second["symbol"], "$\\overline{P}_{1}$")
        self.assertEqual(second["unit"], "千瓦（kW）")

    def test_declarations_do_not_create_content_elements(self) -> None:
        ssir = _parse(FRONT_MATTER)
        clause = ssir["structuralRoot"]["children"][0]
        presentation = [element["presentationType"] for element in clause["contentElements"]]
        # 声明块不落文本流：条款下只有正文段 + 图槽 + 公式槽
        self.assertNotIn("other", presentation)
        self.assertEqual(presentation.count("figure"), 1)
        self.assertEqual(presentation.count("formula"), 1)

    def test_toc_entries_are_registered_without_content_elements(self) -> None:
        text = FRONT_MATTER.split("![图1")[0] + TOC_DECLARATION
        ssir = _parse(text)
        validate_ssir(ssir)
        entries = ssir["tocEntries"]
        self.assertEqual(
            [(entry["id"], entry.get("number"), entry["title"], entry.get("sourcePageLabel"))
             for entry in entries],
            [
                ("Q_XYZ_001-2026#Contents_1", None, "前言", "V"),
                ("Q_XYZ_001-2026#Contents_2", "1", "范围", "1"),
                ("Q_XYZ_001-2026#Contents_3", "3.1", "文件", "2"),
                ("Q_XYZ_001-2026#Contents_4", None, "附录 A（规范性） 试验记录", "10"),
            ],
        )
        # 配对结束指令被消费，且目次条目不落文本流（正文段落照常存在）
        kinds = [
            element["presentationType"]
            for clause in ssir["structuralRoot"]["children"]
            for element in clause["contentElements"]
        ]
        self.assertNotIn("other", kinds)
        self.assertIn("paragraph", kinds)

    def test_toc_entry_without_page_is_kept(self) -> None:
        text = FRONT_MATTER.split("![图1")[0] + "<!-- ssir:toc -->\n引…………\n"
        ssir = _parse(text)
        self.assertEqual(ssir["tocEntries"][0]["title"], "引")
        self.assertNotIn("sourcePageLabel", ssir["tocEntries"][0])

    def test_note_declaration_registers_ownership_metadata(self) -> None:
        text = FRONT_MATTER.split("![图1")[0] + textwrap.dedent("""\
            <!-- ssir:note kind="table" label="1" scope="table" numbering-scope="document" -->
            > 注：表中数值为实测值。
            """)
        ssir = _parse(text)
        validate_ssir(ssir)
        notes = ssir["notes"]
        self.assertEqual(len(notes), 1)
        note = notes[0]
        self.assertEqual(note["id"], "Q_XYZ_001-2026#Note_1")
        self.assertEqual(note["type"], "note")
        self.assertEqual(note["kind"], "table")
        self.assertEqual(note["label"], "1")
        self.assertEqual(note["scope"], "table")
        # ownerRef 缺省为所在条款节点；contentRef 指向注的内容元素（均为 TDRS 标识）
        self.assertEqual(note["ownerRef"], "Q_XYZ_001-2026#1")
        self.assertTrue(note["contentRef"].startswith("Q_XYZ_001-2026#1/"))

    def test_note_declaration_binds_only_the_next_note(self) -> None:
        text = FRONT_MATTER.split("![图1")[0] + (
            "<!-- ssir:note scope=\"clause\" -->\n"
            "> 注：第一条注。\n\n"
            "> 注：第二条注（无声明，不登记）。\n"
        )
        ssir = _parse(text)
        validate_ssir(ssir)
        self.assertEqual(len(ssir["notes"]), 1)
        self.assertEqual(ssir["notes"][0]["scope"], "clause")

    def test_list_group_records_intro_terminator_and_kind(self) -> None:
        text = FRONT_MATTER.split("![图1")[0] + (
            "本文件规定下列要求：\n\n"
            "- 第一项；\n"
            "- 第二项；\n"
            "- 第三项；\n"
        )
        ssir = _parse(text)
        validate_ssir(ssir)
        clause = ssir["structuralRoot"]["children"][0]
        lists = [e for e in clause["contentElements"] if e["presentationType"] == "list"]
        self.assertEqual(len(lists), 1)
        group = lists[0]["listGroup"]
        self.assertEqual(group["kind"], "dash")
        self.assertEqual(group["terminator"], "；")
        # 引语 = 同节点前一个内容元素（TDRS 标识，无悬挂引用）
        intro_ref = group["introRef"]
        siblings = [e["id"] for e in clause["contentElements"]]
        self.assertIn(intro_ref, siblings)
        self.assertTrue(intro_ref.startswith("Q_XYZ_001-2026#1/"))

    def test_list_group_omitted_when_no_intro_and_mixed_terminators(self) -> None:
        text = FRONT_MATTER.split("![图1")[0] + (
            "本项目的规定如下。\n\n"
            "- 第一项；\n"
            "- 第二项。\n"
        )
        ssir = _parse(text)
        clause = ssir["structuralRoot"]["children"][0]
        lists = [e for e in clause["contentElements"] if e["presentationType"] == "list"]
        group = lists[0].get("listGroup") or {}
        self.assertEqual(group.get("kind"), "dash")
        # 终结符不一致 → 留空（不猜）；无冒号引语 → 无 introRef
        self.assertNotIn("terminator", group)
        self.assertNotIn("introRef", group)

    def test_paired_declaration_body_is_bounded_by_the_closer(self) -> None:
        # 括起式：体内的非条目行（如「目　次」这类无导引符行）整行保留为条目，
        # **不得截断**声明体——截断会让剩余行回落正文，目次页重复渲染（GB_T_1.1-2020
        # A/B 实验实测：截断时 144 行只吃进 17 行、文档由 72 页涨到 76 页）。
        text = FRONT_MATTER.split("![图1")[0] + (
            "<!-- ssir:toc -->\n"
            "前言 …… V\n"
            "\n"
            "目　次\n"
            "\n"
            "1 范围……………………1\n"
            "<!-- ssir:/toc -->\n"
        )
        ssir = _parse(text)
        validate_ssir(ssir)
        entries = ssir["tocEntries"]
        self.assertEqual([entry["title"] for entry in entries], ["前言", "目　次", "范围"])
        self.assertEqual(entries[2]["number"], "1")
        self.assertEqual(entries[1].get("sourcePageLabel"), None)
        # 目次行不落文本流：条款下不出现这些行的正文元素
        clause = ssir["structuralRoot"]["children"][0]
        texts = " ".join(str(e.get("textContent") or "") for e in clause["contentElements"])
        self.assertNotIn("范围………", texts)

    def test_unresolved_declaration_is_reported_not_guessed(self) -> None:
        # 无图文档中的图例声明：既无 `figure=` 目标也无「最近一图」可归属 → 记 issue。
        text = FRONT_MATTER.split("![图1")[0] + textwrap.dedent("""
            <!-- ssir:figure-legend -->
            1——气隙；
            """)
        ssir = _parse(text)
        comments = ssir["qualityAssessments"][0].get("comments") or ""
        self.assertIn("Unresolved declarations", comments)
        self.assertIn("figure-legend", comments)
        self.assertEqual(ssir["figures"], [])


CROSS_SCOPE_FIXTURE = """\
---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/XYZ 002—2026"
standard-number: "Q/XYZ 002—2026"
title: "跨作用域声明夹具"
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

# 跨作用域声明夹具

## 1 范围

本文档用于「式中」组跨作用域声明的回归（GEN-128）。

<!-- ssir:box -->

<!-- ssir:columns -->

正确：
<!-- ssir:formula id="fm-001" -->
$$
\\\\rho = \\\\frac {m}{V}
$$

<!-- ssir:column -->

不正确：
$$
密度 = \\\\frac {质量}{体积}
$$

<!-- ssir:/columns -->

<!-- ssir:/box -->

<!-- ssir:box -->

<!-- ssir:columns -->

正确：
$$
\\\\dim (E) = \\\\dim (F) × \\\\dim (l)
$$
式中：
<!-- ssir:formula-vars formula="fm-001" -->
$E$——能量；

$F$——力。
<!-- ssir:/formula-vars -->

<!-- ssir:column -->

不正确：
$$
\\\\dim (能量 ) = \\\\dim (力) × \\\\dim (长度)
$$

<!-- ssir:/columns -->

<!-- ssir:/box -->
"""


class CrossScopeExplanationTests(unittest.TestCase):
    """GEN-128：`formula-vars` 声明指向**别的框/并列组**里的公式时，按结构位置归属并登记。"""

    def test_group_attaches_to_the_structurally_adjacent_formula(self) -> None:
        ssir = _parse(CROSS_SCOPE_FIXTURE)
        validate_ssir(ssir)
        self.assertEqual(len(ssir["formulas"]), 4)
        declared, adjacent = ssir["formulas"][0], ssir["formulas"][2]
        self.assertNotIn("explanationGroup", declared, "条目不得跟随跨作用域的声明 id")
        self.assertEqual(
            [item["definition"] for item in adjacent["explanationGroup"]["items"]],
            ["能量", "力"],
        )

    def test_cross_scope_declaration_is_reported(self) -> None:
        ssir = _parse(CROSS_SCOPE_FIXTURE)
        comments = ssir["qualityAssessments"][0].get("comments") or ""
        self.assertIn("Unresolved declarations", comments)
        self.assertIn("不在同一框/并列作用域", comments)

    def test_same_scope_declaration_is_still_honoured(self) -> None:
        # 同框同列的显式声明照旧生效（不越界覆盖声明）：fm-001 位于本框本列。
        ssir = _parse(FRONT_MATTER)
        self.assertEqual(len(ssir["formulas"]), 1)
        self.assertIn("explanationGroup", ssir["formulas"][0])
        comments = ssir["qualityAssessments"][0].get("comments") or ""
        self.assertNotIn("不在同一框/并列作用域", comments)


if __name__ == "__main__":
    unittest.main()
