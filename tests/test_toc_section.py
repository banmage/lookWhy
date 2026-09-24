"""GEN-133（2026-09-23 裁定后语义）/ GEN-134：目次区段与声明型指令块的 normalize 回归夹具。

背景（2026-09-23，用户报告 JB_T_14425-2023 的 GBT-H03「章编号不连续、重复 1—8」）：
MinerU 把目次抽成裸段落行（`1 范围.... 1`、`5 型式与基本参数2`、`6 技术要求…`——点线
残缺甚至全丢），normalize 的**裸条号提升**（GEN-035）把它们当成章标题，于是 SSIR 章树里
出现两套 1..8、`目次` documentBlock 没有条目；渲染端又按章树生成目录行。

用户裁定（2026-09-23）：「目次都是根据正文内容生成，而不是根据原来的目次显示（应丢弃）」
——故区段条目行**只消费、不落块**：既不提升成标题，也不带进 canonical/SSIR（原「原样保留
进 `ssir:toc` 声明块」的 GEN-133 初版据此作废），`目次` 标题保留为渲染端插入**生成目次**
（`_toc_nodes` 按章树出行）的位置。

本文件锁四件事：
① 区段判据（前缀像条目 + 无句末标点 + 遇标题/块起始行终止；
   点线残缺或丢失也要收得住——判据不依赖导引符）；② 区段行被丢弃：canonical 无条目行、
   不产生 `ssir:toc` 块、SSIR 章树只有一套 1..8、`tocEntries` 为空（目次由章树生成）；
③ 声明型指令块的条目体在**重渲染**时不丢（curated canonical 里显式的 `toc` 声明连同配对
   结束指令一起回写，旧实现整块丢弃）；④ 反例：目次标题下的正文段不被吞、无条目时不产生
   空声明块、`8.2 目次` 这类编号标题不当区段入口。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from leleby_ssir.builder import SSIRBuilder
from leleby_ssir.csm_normalizer import render_canonical
from leleby_ssir.parser import CSMDocument, CSMParser, _is_toc_entry_line, _toc_region_lines

FRONT_MATTER = "---\ndocumentId: JB_T_14425-2023\nstandardNumber: JB/T 14425—2023\n---\n"

# MinerU 抽出的目次形态（JB_T_14425-2023 实测）：点线残缺/全丢、页码粘连、单个省略号。
TOC_RAW = FRONT_MATTER + """## 目 次

1 范围.... 1  
2 规范性引用文件 …1  
3 术语和定义....  
4 信息确认..  
5 型式与基本参数2  
6 技术要求…  
7 试验与检验 …4  
8 交付准备...  
附录 B（资料性）基本参数…13  
附录 C(资料性） 产品试验记录14

## 前 言

本文件按照 GB/T 1.1—2020 的规定起草。

## 1 范围

本文件界定了电磁隔膜计量泵的术语和定义。

## 2 规范性引用文件

下列文件中的内容通过文中的规范性引用而构成本文件必不可少的条款。
"""

TOC_ENTRY_LINES = [
    "1 范围.... 1",
    "2 规范性引用文件 …1",
    "3 术语和定义....",
    "4 信息确认..",
    "5 型式与基本参数2",
    "6 技术要求…",
    "7 试验与检验 …4",
    "8 交付准备...",
    "附录 B（资料性）基本参数…13",
    "附录 C(资料性） 产品试验记录14",
]

CURATED_TOC_BLOCK = FRONT_MATTER + """## 目次

<!-- ssir:toc -->
前言 …… V
1 范围 …… 1
附录 A（资料性） 层次编号示例 …… 37
<!-- ssir:/toc -->

## 前言

本文件按照 GB/T 1.1—2020 的规定起草。
"""


def _read(text: str, directory: Path, name: str = "doc") -> "CSMDocument":
    source = directory / f"{name}.md"
    source.write_text(text, encoding="utf-8")
    return CSMParser().read(str(source))


def _normalize(text: str, directory: Path, name: str = "doc") -> tuple[str, "CSMDocument"]:
    document = _read(text, directory, name)
    return render_canonical(document), document


class TocEntryLineTests(unittest.TestCase):
    """判据层：条目行/区段边界。"""

    def test_leader_loss_still_counts_as_entry(self) -> None:
        # 点线残缺（`....`/`..`/单个 `…`）或全丢（页码粘连）都是同一份目次的条目。
        for line in TOC_ENTRY_LINES:
            self.assertTrue(_is_toc_entry_line(line), line)

    def test_sentence_punctuation_and_block_starts_are_not_entries(self) -> None:
        for line in (
            "本文件按照 GB/T 1.1—2020 的规定起草。",
            "## 前 言",
            "<!-- ssir:toc -->",
            "| 表头 | 值 |",
            "![图1 系统构成](assets/a.png)",
        ):
            self.assertFalse(_is_toc_entry_line(line), line)

    def test_region_stops_at_the_next_heading(self) -> None:
        lines = "## 目 次\n\n1 范围.... 1\n\n## 前 言\n\n本文件…。".splitlines()
        entries, index = _toc_region_lines(lines, 1)
        self.assertEqual(entries, ["1 范围.... 1"])
        rest = [line for line in lines[index:] if line.strip()]
        self.assertEqual(rest[0], "## 前 言")

    def test_region_stops_at_body_prose(self) -> None:
        lines = "## 目 次\n\n1 范围.... 1\n\n本文件界定了电磁隔膜计量泵。".splitlines()
        entries, index = _toc_region_lines(lines, 1)
        self.assertEqual(entries, ["1 范围.... 1"])
        rest = [line for line in lines[index:] if line.strip()]
        self.assertEqual(rest[0], "本文件界定了电磁隔膜计量泵。")


class TocSectionNormalizeTests(unittest.TestCase):
    """normalize（raw → canonical）：区段折进声明块。"""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_entries_are_dropped_from_the_canonical(self) -> None:
        # 用户裁定：原目次的显示应丢弃——条目行不带进 canonical（既不落 `ssir:toc` 块，
        # 也不留正文），`目次` 标题保留（渲染端插入生成目次的位置）。
        canonical, _ = _normalize(TOC_RAW, self.root)
        self.assertIn("## 目 次", canonical)
        self.assertNotIn("ssir:toc", canonical)
        for line in TOC_ENTRY_LINES:
            self.assertNotIn(line, canonical)
        # 目次之后的正文照旧
        self.assertIn("本文件按照 GB/T 1.1—2020 的规定起草。", canonical)

    def test_entries_are_not_promoted_to_headings(self) -> None:
        canonical, document = _normalize(TOC_RAW, self.root)
        for line in TOC_ENTRY_LINES:
            self.assertNotIn(f"## {line}", canonical)
        self.assertEqual(
            [warning for warning in document.warnings if "promoted to a heading" in warning], []
        )
        self.assertTrue(
            any("TOC entry lines dropped" in warning for warning in document.warnings),
            document.warnings,
        )

    def test_declaration_keeps_entries_when_renormalized(self) -> None:
        # GEN-134：curated canonical 的 `ssir:toc` 块重跑 normalize 不得丢条目
        # （旧实现只剩悬空开指令、条目与结束指令全丢）。
        canonical, _ = _normalize(CURATED_TOC_BLOCK, self.root, "curated")
        for entry in ("前言 …… V", "1 范围 …… 1", "附录 A（资料性） 层次编号示例 …… 37"):
            self.assertIn(entry, canonical)
        self.assertIn("<!-- ssir:/toc -->", canonical)
        body = canonical.split("<!-- ssir:toc -->")[1].split("<!-- ssir:/toc -->")[0]
        self.assertEqual([line for line in body.splitlines() if line.strip()], [
            "前言 …… V", "1 范围 …… 1", "附录 A（资料性） 层次编号示例 …… 37",
        ])
        # 二次 normalize 幂等（声明块自身）
        again, _ = _normalize(canonical, self.root, "curated2")
        self.assertEqual(
            again.split("<!-- ssir:toc -->")[1].split("<!-- ssir:/toc -->")[0],
            body,
        )

    def test_prose_after_entries_stays_prose(self) -> None:
        text = FRONT_MATTER + "## 目 次\n\n1 范围.... 1\n\n本文件界定了电磁隔膜计量泵。\n"
        canonical, _ = _normalize(text, self.root)
        self.assertIn("本文件界定了电磁隔膜计量泵。", canonical)
        self.assertNotIn("1 范围.... 1", canonical)
        self.assertNotIn("ssir:toc", canonical)

    def test_empty_toc_section_emits_no_declaration(self) -> None:
        text = FRONT_MATTER + "## 目 次\n\n## 前 言\n\n本文件按照 GB/T 1.1—2020 的规定起草。\n"
        canonical, _ = _normalize(text, self.root)
        self.assertNotIn("ssir:toc", canonical)

    def test_numbered_heading_named_after_toc_is_not_a_region(self) -> None:
        # `### 8.2 目次`（GB/T 1.1-2020 的条款）不是目次区段入口。
        text = (
            FRONT_MATTER
            + "## 8.2 目次\n\n目次这一要素用来呈现文件的结构。\n\n"
            + "## 目次格式\n\n1 范围.... 1\n"
        )
        canonical, _ = _normalize(text, self.root)
        self.assertNotIn("ssir:toc", canonical)


class TocSectionParseTests(unittest.TestCase):
    """解析层：区段不造第二套章条、条目不带进 SSIR（目次由章树生成）、GBT-H03 消失。"""

    def test_clause_tree_has_one_set_of_chapters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            canonical, _ = _normalize(TOC_RAW, Path(tmp))
            target = Path(tmp) / "doc.canonical.md"
            target.write_text(canonical, encoding="utf-8")
            document = CSMParser().read(str(target))
        ssir = SSIRBuilder().build(document)
        children = ssir["structuralRoot"]["children"]
        numbers = [child.get("number") for child in children if child.get("nodeType") == "section"]
        self.assertEqual(numbers, ["1", "2"])
        toc_nodes = [
            child for child in children
            if child.get("nodeType") == "documentBlock"
            and "目次" in str(child.get("title", "")).replace(" ", "")
        ]
        self.assertEqual(len(toc_nodes), 1)
        # 原目次的条目不带进 SSIR：目次行由渲染端按章树生成（`_toc_nodes`），
        # `tocEntries` 仅在有**显式** `ssir:toc` 声明时才有内容（legacy/curated canonical）。
        self.assertEqual(ssir.get("tocEntries") or [], [])

    def test_numbering_continuity_finding_is_gone(self) -> None:
        from leleby_ssir.compliance import verify_compliance

        with tempfile.TemporaryDirectory() as tmp:
            canonical, _ = _normalize(TOC_RAW, Path(tmp))
            target = Path(tmp) / "doc.canonical.md"
            target.write_text(canonical, encoding="utf-8")
            ssir = SSIRBuilder().build(CSMParser().read(str(target)))
        report = verify_compliance(ssir)
        self.assertEqual(
            [finding.rule_id for finding in report.findings if finding.rule_id == "GBT-H03"], []
        )


if __name__ == "__main__":
    unittest.main()
