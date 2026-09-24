"""附录条结构（annexSection）回归夹具。

背景（2026-09-12，用户报告）：kg_viewer 文档浏览页的结构树里，附录 A/B/… 的下属
条款没有折叠到附录之下。根因：canonical 中附录条与附录同为 `##`（MinerU 扁平
抽取），而 parser 的层级修复（CSM-OCR-006）只认十进制编号、不认附录条的
「大写字母 + 点分数字」编号 → 附录条层级未提升，builder 按层级把它们挂成附录的
兄弟（documentBlock），`annexSection` 从未产生。

覆盖：
- parser：附录条 heading 级别按段数提升（B.1→3、B.6.1→4），附录标题不动；
- builder：附录条 → annexSection 节点（number/title 拆分）并嵌套在所属附录之下；
- roundtrip：render.md 重放后再次解析得到同一棵树；
- 负例：标准号/型号等非「单字母.数字」前缀不被误判。
"""
from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from leleby_ssir.builder import SSIRBuilder
from leleby_ssir.csm_renderer import render_csm
from leleby_ssir.parser import CSMParser

FRONT = """---
csm-version: 1.0
document-type: standard
document-identifier: T_ANNEX_001-2026
standard-number: T/ANNEX 001-2026
title: 附录条结构测试文档
language: zh-CN
---
# 附录条结构测试文档
## 1 范围
本文件规定了附录条结构的测试行为。
"""

CANON = FRONT + """## 附录 A（规范性） 测试附录
## A.1 通则
A.1 的内容。
## A.2 识别段
## A.2.1 子项
A.2.1 的内容。
## 附录 B（资料性） 另一附录
## B.1 概述
B.1 的内容。
## 6 非附录标题不得误判
ISO 9001 与 T/ZZB 1064-2019 都不是附录条编号。
"""


def _parse(body: str = CANON):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "t.canonical.md"
        path.write_text(body, encoding="utf-8")
        return CSMParser().read(str(path))


def _walk(node: dict):
    yield node
    for child in node.get("children") or []:
        yield from _walk(child)


class ParserAnnexLevelTests(unittest.TestCase):
    def test_annex_clause_heading_levels_promoted(self) -> None:
        doc = _parse()
        levels = {b.text: b.level for b in doc.blocks if b.kind == "heading"}
        self.assertEqual(levels.get("附录 A（规范性） 测试附录"), 2)
        self.assertEqual(levels.get("A.1 通则"), 3)
        self.assertEqual(levels.get("A.2 识别段"), 3)
        self.assertEqual(levels.get("A.2.1 子项"), 4)
        self.assertEqual(levels.get("B.1 概述"), 3)

    def test_non_annex_prefix_headings_untouched(self) -> None:
        doc = _parse()
        levels = {b.text: b.level for b in doc.blocks if b.kind == "heading"}
        # 标准号/型号前缀不是附录条编号，不得被提升
        self.assertEqual(levels.get("6 非附录标题不得误判"), 2)


class BuilderAnnexSectionTests(unittest.TestCase):
    def test_annex_sections_nested_under_annex(self) -> None:
        ssir = SSIRBuilder().build(_parse())
        annex = next(n for n in _walk(ssir["structuralRoot"])
                     if n.get("nodeType") == "annex" and n.get("number") == "A")
        sections = annex.get("children") or []
        self.assertEqual([(n.get("number"), n.get("title"), n.get("nodeType")) for n in sections],
                         [("A.1", "通则", "annexSection"), ("A.2", "识别段", "annexSection")])
        sub = sections[1].get("children") or []
        self.assertEqual([(n.get("number"), n.get("title"), n.get("nodeType")) for n in sub],
                         [("A.2.1", "子项", "annexSection")])
        self.assertEqual(sections[0].get("level"), 2)
        self.assertEqual(sub[0].get("level"), 3)

    def test_annex_node_has_no_flat_sibling_sections(self) -> None:
        ssir = SSIRBuilder().build(_parse())
        root_children = ssir["structuralRoot"].get("children") or []
        self.assertFalse([n for n in root_children if n.get("nodeType") == "annexSection"])


class ExampleNestingTests(unittest.TestCase):
    """附录内示例（CSM-OCR-008 扩展，2026-09-12）：简单示例挂到所属附录条/附录之下；
    内容本身是一份示例文档的模型示例保持扁平；索引分组字母降级为段落。"""

    CANON = FRONT + """## 附录 A（规范性） 测试附录
## A.1 通则
A.1 的内容。
## 示例：
简单示例内容。
## A.2 特性
## 示例1：
示例1 内容。
## 附录 B（资料性） 模型示例
## 示例 1：
## 1 模型章
模型内容。
## 2 模型章二
## 参考文献
[1] GB/T 1.1—2020 标准化工作导则
## 索 引
## B
必备要素 1.1
## Z
章 2.1
"""

    def _ssir(self):
        return SSIRBuilder().build(_parse(self.CANON))

    def _examples(self, ssir):
        found = []
        for node in _walk(ssir["structuralRoot"]):
            title = str(node.get("title") or "")
            if title.replace(" ", "").startswith("示例") and node.get("nodeType") == "documentBlock":
                found.append(node)
        return found

    def _parents(self, ssir):
        parents: dict[str, str] = {}

        def visit(node):
            for child in node.get("children") or []:
                parents[str(child.get("title") or child.get("number"))] = str(
                    node.get("number") or node.get("title") or node.get("nodeType")
                )
                visit(child)

        visit(ssir["structuralRoot"])
        return parents

    def test_simple_examples_nest_under_annex_scope(self) -> None:
        parents = self._parents(self._ssir())
        self.assertEqual(parents.get("示例："), "A.1")
        self.assertEqual(parents.get("示例1："), "A.2")

    def test_model_example_stays_flat(self) -> None:
        ssir = self._ssir()
        annex = next(n for n in _walk(ssir["structuralRoot"])
                     if n.get("nodeType") == "annex" and n.get("number") == "B")
        self.assertEqual(annex.get("children") or [], [])
        # 模型示例（后随示例文档自带的「## 1 模型章」）未提升，仍挂文档根级
        root_examples = [c for c in ssir["structuralRoot"].get("children", [])
                         if str(c.get("title") or "").replace(" ", "") == "示例1："]
        self.assertEqual(len(root_examples), 1)
        self.assertEqual(root_examples[0].get("level"), 1)

    def test_index_letter_headings_demoted(self) -> None:
        ssir = self._ssir()
        titles = {str(n.get("title") or "") for n in _walk(ssir["structuralRoot"])}
        self.assertNotIn("B", titles)
        self.assertNotIn("Z", titles)
        index = next(n for n in _walk(ssir["structuralRoot"])
                     if str(n.get("title") or "").replace(" ", "") == "索引")
        texts = [ce.get("textContent") for ce in index.get("contentElements") or []]
        self.assertIn("B", texts)
        self.assertIn("Z", texts)


    def test_example_content_heading_demoted(self) -> None:
        # MinerU 把示例内容里的「标记：」行抽成 ## 标题（GB_T_1.1-2020 示例2 的
        # 「多刃刀片 GB/T 2079-…」）→ 降级为示例段落，不再是章条级结构节点（CSM-OCR-020）。
        canon = FRONT + """## 附录 A（规范性） 测试附录
## A.1 通则
## 示例：
产品：
##    标记行 GB/T 0000-X
标记说明。
"""
        doc = _parse(canon)
        self.assertIn("CSM-OCR-020", [issue.code for issue in doc.issues])
        ssir = SSIRBuilder().build(doc)
        titles = {str(n.get("title") or "") for n in _walk(ssir["structuralRoot"])}
        self.assertNotIn("标记行 GB/T 0000-X", titles)
        example = next(n for n in _walk(ssir["structuralRoot"])
                       if str(n.get("title") or "").replace(" ", "") == "示例：")
        texts = [ce.get("textContent") for ce in example.get("contentElements") or []]
        self.assertIn("标记行 GB/T 0000-X", texts)
        self.assertIn("标记说明。", texts)


class IndexStoryTests(unittest.TestCase):
    """索引渲染（_index_story）：字母分组降级为段落（CSM-OCR-019）后，索引内容挂在
    「索引」节点自身的 contentElements 上，渲染器必须从该节点读取（2026-09-12
    曾因此把整页索引渲染成空页）。"""

    def test_entries_read_from_index_node_contents(self) -> None:
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import PageBreak, Paragraph

        from leleby_ssir.pdf_renderer import _index_story

        class FakeIndexFlowable:
            def __init__(self, rows, width):
                self.rows = rows

            def wrap(self, available_width, available_height):
                return available_width, 10 * len(self.rows)

        index_node = {
            "nodeType": "documentBlock",
            "title": "索 引",
            "contentElements": [
                {"presentationType": "paragraph", "sortOrder": 0, "textContent": "B"},
                {"presentationType": "paragraph", "sortOrder": 1,
                 "textContent": "必备要素………………………………………… 3.2.5,6.2.2.1\n必须……… 9.5.4.2.2"},
                {"presentationType": "paragraph", "sortOrder": 2, "textContent": "Z"},
                {"presentationType": "paragraph", "sortOrder": 3, "textContent": "章………………………………………… 7.2"},
            ],
        }
        styles = {"toc-title": getSampleStyleSheet()["Normal"]}
        story = _index_story([index_node], styles, FakeIndexFlowable, PageBreak, Paragraph)
        rows = [row for flowable in story if isinstance(flowable, FakeIndexFlowable) for row in flowable.rows]
        self.assertIn(("B", None), rows)
        self.assertIn(("Z", None), rows)
        self.assertIn(("必备要素", "3.2.5,6.2.2.1"), rows)
        self.assertIn(("必须", "9.5.4.2.2"), rows)
        self.assertIn(("章", "7.2"), rows)


class AnnexHeadingProjectionTests(unittest.TestCase):
    def test_annex_heading_levels_in_markdown_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t.canonical.md"
            path.write_text(CANON, encoding="utf-8")
            ssir = SSIRBuilder().build(CSMParser().read(str(path)))
            rendered = render_csm(ssir)
            self.assertIn("### A.1 通则", rendered)
            self.assertIn("#### A.2.1 子项", rendered)
            # 投影：零 ssir 指令、零 HTML 注释
            self.assertNotIn("ssir:", rendered)
            self.assertNotIn("<!--", rendered)


if __name__ == "__main__":
    unittest.main()
