"""行内角标标记（通用形式）的迁移与配对校验测试（CSM-STRUCT-007）。

语法（docs/07 §6.7，2026-09-11 通用化）：
    [:sup:a] … [:/sup]   上标注解区（角标字符 + 注解文字）
    [:sub:2] … [:/sub]   下标注解区
    [:sup:a/]            自闭合 = 空注解区（引用点）
旧形式（按角标字符逐对定义，a~z 就是 26 对记号）在解析时确定性迁移：
    [:^a] → [:sup:a/]    注文段 [^a]X[^a/] → [:sup:a]X[:/sup]
配对校验：未闭合补闭标记、孤立闭标记删除、script 不符按开标记改写（宽容模式继续）。
"""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from leleby_ssir.parser import CSMParser, inline_script_item_breaks


def _parse(body: str) -> "tuple":
    csm = (
        "---\n"
        'csm-version: "1.0"\n'
        "document-type: standard\n"
        'document-identifier: "GB/T 5171.1—2014"\n'
        'standard-number: "GB/T 5171.1—2014"\n'
        'title: "小型电力设备用电动机 第1部分：通用技术条件"\n'
        "language: zh-CN\n"
        "extensions:\n"
        "  standard-profile: product\n"
        "---\n\n"
        + body
    )
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "fixture.canonical.md"
        path.write_text(csm, encoding="utf-8")
        document = CSMParser().read(path)
    return document.blocks, document.issues


def _paragraphs(blocks: "list") -> list[str]:
    return [block.text for block in blocks if block.kind == "paragraph"]


class InlineScriptTokenMigrationTests(unittest.TestCase):
    """旧形式 → 通用行内角标标记（CSM-STRUCT-007 迁移侧）。"""

    def test_legacy_citation_point_becomes_self_closing_token(self) -> None:
        blocks, issues = _parse("## 5 试验方法\n\n机械检查[:^a]应符合本文件要求。\n")
        self.assertEqual(_paragraphs(blocks), ["机械检查[:sup:a/]应符合本文件要求。"])
        migrated = [i for i in issues if i.code == "CSM-STRUCT-007"]
        self.assertEqual(len(migrated), 1)
        self.assertTrue(migrated[0].repaired)

    def test_legacy_note_pair_becomes_generic_pair(self) -> None:
        blocks, _issues = _parse(
            "## 5 试验方法\n\n[^a]对交直流两用电动机的型式检验以交流电动机为主。[^a/]\n"
        )
        self.assertEqual(
            _paragraphs(blocks),
            ["[:sup:a]对交直流两用电动机的型式检验以交流电动机为主。[:/sup]"],
        )

    def test_table_cell_tokens_are_migrated_too(self) -> None:
        body = (
            "## 5 试验方法\n\n"
            "| 序号 | 试验项目 |\n"
            "| --- | --- |\n"
            "| 7 | 堵转试验[:^a] |\n"
            "| [^a]第7项试验对交流换向器电动机允许抽查。[^a/] |  |\n"
        )
        blocks, issues = _parse(body)
        tables = [block for block in blocks if block.kind == "table"]
        self.assertEqual(len(tables), 1)
        rows = tables[0].data["rows"]
        self.assertEqual(rows[0], ["序号", "试验项目"])
        self.assertEqual(rows[1], ["7", "堵转试验[:sup:a/]"])
        self.assertEqual(rows[2], ["[:sup:a]第7项试验对交流换向器电动机允许抽查。[:/sup]", ""])
        self.assertTrue([i for i in issues if i.code == "CSM-STRUCT-007"])

    def test_migration_is_idempotent(self) -> None:
        blocks, _issues = _parse("## 5 试验方法\n\n机械检查[:^a]应符合要求。\n")
        migrated = _paragraphs(blocks)[0]
        self.assertEqual(migrated, "机械检查[:sup:a/]应符合要求。")
        # 迁移后的文本再解析：不再有 007（形态已是通用形式）。
        _blocks2, issues2 = _parse(f"## 5 试验方法\n\n{migrated}\n")
        self.assertFalse(any(i.code == "CSM-STRUCT-007" for i in issues2))


class InlineScriptTokenPairingTests(unittest.TestCase):
    """配对校验与修复（CSM-STRUCT-007 校验侧）。"""

    def test_unclosed_open_gets_closing_token_at_end(self) -> None:
        blocks, issues = _parse("## 5 试验方法\n\n[:sup:a]对交直流两用电动机的型式检验以交流电动机为主。\n")
        self.assertEqual(
            _paragraphs(blocks),
            ["[:sup:a]对交直流两用电动机的型式检验以交流电动机为主。[:/sup]"],
        )
        repaired = [i for i in issues if i.code == "CSM-STRUCT-007"]
        self.assertEqual(len(repaired), 1)
        self.assertTrue(repaired[0].repaired)

    def test_orphan_close_is_dropped(self) -> None:
        blocks, issues = _parse("## 5 试验方法\n\n机械检查[:/sup]应符合要求。\n")
        self.assertEqual(_paragraphs(blocks), ["机械检查应符合要求。"])
        self.assertEqual(len([i for i in issues if i.code == "CSM-STRUCT-007"]), 1)

    def test_script_mismatch_follows_the_open_token(self) -> None:
        blocks, _issues = _parse("## 5 试验方法\n\n[:sup:a]注解文字。[:/sub]\n")
        self.assertEqual(_paragraphs(blocks), ["[:sup:a]注解文字。[:/sup]"])

    def test_self_closing_and_well_formed_pairs_are_untouched(self) -> None:
        body = (
            "## 5 试验方法\n\n"
            "机械检查[:sup:a/]、水压试验[:sub:2/]；\n\n"
            "[:sup:a]对交直流两用电动机的型式检验以交流电动机为主。[:/sup]\n\n"
            "H[:sub:2/]O 与 [:sup:b]注解[:/sup] 并存。\n"
        )
        blocks, issues = _parse(body)
        self.assertEqual(
            _paragraphs(blocks),
            [
                "机械检查[:sup:a/]、水压试验[:sub:2/]；",
                "[:sup:a]对交直流两用电动机的型式检验以交流电动机为主。[:/sup]",
                "H[:sub:2/]O 与 [:sup:b]注解[:/sup] 并存。",
            ],
        )
        self.assertFalse(any(i.code == "CSM-STRUCT-007" for i in issues))

    def test_nested_pairs_close_in_order(self) -> None:
        blocks, issues = _parse("## 5 试验方法\n\n[:sup:a]外[:sub:2]内[:/sub]尾[:/sup]\n")
        self.assertEqual(_paragraphs(blocks), ["[:sup:a]外[:sub:2]内[:/sub]尾[:/sup]"])
        self.assertFalse(any(i.code == "CSM-STRUCT-007" for i in issues))


    def test_unclosed_open_in_word_closes_at_text_end(self) -> None:
        # 未闭合的开标记 = 注解区延伸到文本末尾（闭标记不渲染，故与自闭合的渲染
        # 结果相同）；规范写法是自闭合 [:sub:2/]（孤立的角标字符）。
        blocks, _issues = _parse("## 5 试验方法\n\nH[:sub:2]O 是水。\n")
        self.assertEqual(_paragraphs(blocks), ["H[:sub:2]O 是水。[:/sub]"])


class InlineScriptItemBreakTests(unittest.TestCase):
    """表注列项连排 → 渲染端自动换行（canonical 不写 <br>）。"""

    def test_break_inserted_between_consecutive_pairs(self) -> None:
        text = "[:sup:a]第7项试验说明。[:/sup][:sup:b]第10项试验说明。[:/sup]"
        self.assertEqual(
            inline_script_item_breaks(text),
            "[:sup:a]第7项试验说明。[:/sup]\x00BR\x00[:sup:b]第10项试验说明。[:/sup]",
        )

    def test_self_closing_citation_points_are_not_split(self) -> None:
        text = "机械检查[:sup:a/]水压试验[:sup:b/]"
        self.assertEqual(inline_script_item_breaks(text), text)

    def test_single_item_is_untouched(self) -> None:
        text = "[:sup:a]只有一条注文。[:/sup]"
        self.assertEqual(inline_script_item_breaks(text), text)


if __name__ == "__main__":
    unittest.main()
