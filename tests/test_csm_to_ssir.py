from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from leleby_ssir.exporters import json_bytes, turtle_text
from leleby_ssir.parser import Block, CSMError, CSMParser, _absorb_table_note_spill
from leleby_ssir.csm_renderer import render_csm
from tests.ssir_equivalence import assert_ssir_equivalent, semantic_view
from leleby_ssir.service import normalize_csm, parse_csm, parse_csm_with_report


ROOT = Path(__file__).resolve().parents[1]


class CSMToSSIRTests(unittest.TestCase):
    def test_pmrz_preserves_figures_table_list_and_quality_notices(self) -> None:
        ssir = parse_csm(ROOT / "corpus/golden/csm/Q_PMRZ_9-2024.canonical.md")
        self.assertEqual(ssir["documentType"], "standard")
        self.assertEqual(ssir["sourceFiles"][0]["mimeType"], "text/markdown")
        self.assertEqual(len(ssir["tables"]), 1)
        self.assertEqual(len(ssir["figures"]), 2)
        self.assertEqual(ssir["figures"][0]["preservationStatus"], "partiallyPreserved")
        self.assertEqual(ssir["qualityAssessments"][0]["overallStatus"], "partial")
        self.assertIn("GB20001-10-6.3", ssir["qualityAssessments"][0]["comments"])

    def test_tqdz_preserves_table_and_marked_lists(self) -> None:
        ssir = parse_csm(ROOT / "corpus/golden/csm/Q_TQDZ_004-2026.canonical.md")
        table = ssir["tables"][0]
        self.assertEqual(table["caption"], "基本参数")
        self.assertEqual(table["number"], "1")
        self.assertEqual(table["colCount"], 3)
        lists = [
            element
            for node in self._nodes(ssir["structuralRoot"])
            for element in node.get("contentElements", [])
            if element["presentationType"] == "list"
        ]
        self.assertGreaterEqual(len(lists), 4)
        marker_types = {
            item["markerType"]
            for content in lists
            for item in content["listItems"]
        }
        self.assertIn("lowerAlpha", marker_types)

    def test_additional_product_standard_examples_convert(self) -> None:
        examples = {
            "Q_YYJD_001-2024.canonical.md": {"tables": 1, "figures": 1, "formulas": 0, "status": "partial"},
            "Q_HKT_16016-2026.canonical.md": {"tables": 1, "figures": 0, "formulas": 1, "status": "complete"},
            "T_ZZB_1064-2019.canonical.md": {"tables": 1, "figures": 0, "formulas": 0, "status": "partial"},
        }
        for file_name, expected in examples.items():
            with self.subTest(file_name=file_name):
                ssir, report = parse_csm_with_report(ROOT / "corpus/golden/csm" / file_name)
                self.assertEqual(ssir["documentType"], "standard")
                self.assertEqual(len(ssir["tables"]), expected["tables"])
                self.assertEqual(len(ssir["figures"]), expected["figures"])
                self.assertEqual(len(ssir["formulas"]), expected["formulas"])
                self.assertEqual(report.overall_status, expected["status"])
                self.assertEqual(ssir["qualityAssessments"][0]["overallStatus"], expected["status"])

    def test_markdown_projection_covers_all_csm_examples(self) -> None:
        paths = [
            *sorted((ROOT / "corpus/golden/csm").glob("*.canonical.md")),
            ROOT / "corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md",
        ]
        with tempfile.TemporaryDirectory() as directory:
            for path in paths:
                with self.subTest(path=path.name):
                    render_md = Path(directory) / f"{path.stem}.render.md"
                    ssir = parse_csm(path)
                    render_md.write_text(render_csm(ssir), encoding="utf-8")
                    text = render_md.read_text(encoding="utf-8")
                    self.assertTrue(text.strip(), "投影为空")
                    # 投影是标准 markdown 等价物：零 ssir 指令、零 HTML 注释、无 front matter
                    self.assertNotIn("ssir:", text)
                    self.assertNotIn("<!--", text)
                    self.assertFalse(text.startswith("---"))
                    self.assertIn(str(ssir["metadata"]["common"].get("title") or ""), text)

    def test_template_formula_and_turtle_export(self) -> None:
        ssir = parse_csm(ROOT / "corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md")
        self.assertEqual(len(ssir["formulas"]), 1)
        # CSM 编号行「式（1）」解析为纯编号标签「1」，渲染端补圆括号并按
        # GB/T 1.1-2020 10.4.3 右端对齐（GBT-X06；CSM-OCR-017）。
        self.assertEqual(ssir["formulas"][0]["number"], "1")
        turtle = turtle_text(ssir)
        self.assertIn("ssir:jsonSha256", turtle)
        self.assertIn("https://leleby.io/resource/Q_EXAMPLE_001-2026", turtle)
        self.assertIn("a ssir:Table", turtle)
        self.assertIn("a ssir:Figure", turtle)
        self.assertIn("a ssir:Formula", turtle)

    def test_annex_kind_and_identifier_are_structured(self) -> None:
        path = ROOT / "corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md"
        ssir = parse_csm(path)
        annex = next(node for node in self._nodes(ssir["structuralRoot"]) if node["nodeType"] == "annex")
        self.assertTrue(str(annex["number"]).strip(), "附录编号缺失")
        self.assertIn(f"附录 {annex['number']}", render_csm(ssir))

    def test_back_matter_after_last_annex_not_marked_example_content(self) -> None:
        # 回归（2026-08-31，GB_T_1.1-2020 渲染 LayoutError）：扁平树（MinerU 全
        # ## 抽取）中最后一个附录之后的 参考文献/索 引/索引字母块曾被误标
        # exampleContent，渲染器把它们整体打包成示例框且框内含 PageBreak →
        # reportlab 崩溃。只有真正的附录示例（示例：/示例文档标题）才应标记。
        csm = """---
csm-version: "1.0"
document-type: standard
document-identifier: "GB/T 1.1—2020"
standard-number: "GB/T 1.1—2020"
title: "标准化工作导则 第1部分：标准化文件的结构和起草规则"
language: zh-CN
source:
  mode: mineru
  original-file-name: "GB_T_1.1-2020.pdf"
---

# 标准化工作导则 第1部分：标准化文件的结构和起草规则

## 1 范围

本文件规定了标准化文件的结构和起草规则。

## 附录 A（资料性） 层次编号示例

下面给出了层次编号的示例。

## 示例：

示例图片内容。

## 附录 B（规范性） 标准化项目标记

## B.1 概述

正文。

## 多刃刀片 GB/T 2079-TPGN 160308-EN-P20

示例文档内容。

## 参考文献

[1] GB/T 1.1—2020 标准化工作导则 第1部分：标准化文件的结构和起草规则

## 索 引

## B

必备要素 3.2.5

## Z

章 7.2
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flat.canonical.md"
            path.write_text(csm, encoding="utf-8")
            ssir = parse_csm(path)
        nodes = {str(node.get("title") or "").replace(" ", ""): node for node in self._nodes(ssir["structuralRoot"]) if node.get("nodeType") == "documentBlock"}
        for title in ("参考文献", "索引"):
            self.assertFalse(nodes[title].get("exampleContent"), f"{title} must not be example content")
        # 索引分组字母（B/Z）不是结构节点：按 CSM-OCR-019 降级为索引内容段落
        # （此前被 MinerU 抽成 ## 标题，成为与附录同级的文档块）。
        self.assertNotIn("B", nodes)
        self.assertNotIn("Z", nodes)
        index_node = next(node for node in nodes.values() if str(node.get("title") or "").replace(" ", "") == "索引")
        index_texts = {str(ce.get("textContent") or "") for ce in index_node.get("contentElements") or []}
        self.assertIn("B", index_texts)
        self.assertIn("Z", index_texts)
        for title in ("示例：", "多刃刀片GB/T2079-TPGN160308-EN-P20"):
            self.assertTrue(nodes[title].get("exampleContent"), f"{title} must be example content")

    def test_repair_restores_decimal_points_in_clause_numbers(self) -> None:
        # 回归（2026-08-31，GB_T_43726-2024）：文本层损坏型 PDF 经 MinerU auto
        # 抽取后标题点号整段丢失（7.4.2 → 742、5.10 → 510、5.2.1 → 521），
        # 且同一文档内损坏逐行不一致（7.4.2.2 又带点）。CSM-OCR-002 用编号
        # 连续性约束恢复点分隔；无法唯一合法拆点时不猜测。
        csm = """---
csm-version: "1.0"
document-type: standard
document-identifier: "GB/T 43726—2024"
standard-number: "GB/T 43726—2024"
title: "无刷直流力矩电动机通用技术条件"
language: zh-CN
source:
  mode: mineru
  original-file-name: "GB_T_43726-2024.pdf"
---

# 无刷直流力矩电动机通用技术条件

## 1 范围

本文件规定了电机的技术要求。

## 2 规范性引用文件

下列文件中的内容通过文中的规范性引用而构成本文件必不可少的条款。

## 3 术语和定义

## 4 分类与型号

## 41 分类

## 4.2 型号

## 421 型号结构

## 422 机座号

## 5 技术要求

## 51 外观

## 511 表面外观

## 512 标志

## 52 外形和安装尺寸

## 53 径向间隙

## 54 轴向间隙

## 55 轴伸径向圆跳动

## 56 安装配合面的同轴度

## 57 安装配合面的端面垂直度

## 58 引出线或接线端

## 59 绝缘电阻

## 510 绝缘介电强度

## 511 定子电阻

## 6 检验方法

## 7 检验规则

## 71 检验分类

## 72 检验条件

## 73 鉴定检验

## 74 质量一致性检验

## 741 A组检验

## 742 C组检验

## 7421 通则

## 7.4.2.2 不合格
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "damaged.canonical.md"
            path.write_text(csm, encoding="utf-8")
            ssir = parse_csm(path)
        numbers = [
            node["number"]
            for node in self._nodes(ssir["structuralRoot"])
            if node.get("number")
        ]
        self.assertEqual(
            numbers,
            [
                "1", "2", "3", "4", "4.1", "4.2", "4.2.1", "4.2.2",
                "5", "5.1", "5.1.1", "5.1.2", "5.2", "5.3", "5.4", "5.5",
                "5.6", "5.7", "5.8", "5.9", "5.10", "5.11",
                "6", "7", "7.1", "7.2", "7.3", "7.4", "7.4.1", "7.4.2",
                "7.4.2.1", "7.4.2.2",
            ],
        )

    def test_bare_numbered_chapter_headings_are_promoted(self) -> None:
        # 回归（2026-08-31，QB_T_2946-2020 第 3 章）：MinerU 把章条标题抽成
        # 裸段落（"3 产品分类和型号命名"/"3.1 电动机分类和型号命名"/
        # "3.1.1 电动机分类"），只有 3.1.2 保留 ##。祖先链级联提升应恢复
        # 完整章节结构，否则 GBT-H03 报"章编号不连续：缺失 3"且 GBT-C06 把
        # "3 产品分类和型号命名" 误当引用清单条目。
        csm = """---
csm-version: "1.0"
document-type: standard
document-identifier: "QB/T 2946—2020"
standard-number: "QB/T 2946—2020"
title: "电动自行车用电动机及控制器"
language: zh-CN
source:
  mode: mineru
  original-file-name: "QB_T_2946-2020.pdf"
---

# 电动自行车用电动机及控制器

## 1 范围

本标准规定了电动自行车用电动机及控制器的要求。

## 2 规范性引用文件

下列文件中的内容通过文中的规范性引用而构成本文件必不可少的条款。

GB/T 755-2019 旋转电机 定额和性能

QB/T 1714自行车命名和型号编制方法

3 产品分类和型号命名

3.1 电动机分类和型号命名

3.1.1 电动机分类

电动机按结构分为轮毂电动机和轴旋转电动机。

## 3.1.2 电动机型号命名

## 3.1.2.1 总则

## 5 要求

## 6 检验规则
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bare-headings.canonical.md"
            path.write_text(csm, encoding="utf-8")
            doc = CSMParser().read(path)
        promoted = [issue.display() for issue in doc.issues if "promoted to a heading" in issue.message]
        self.assertEqual(len(promoted), 3)
        self.assertIn("3", doc.issues[0].message)
        # 提升后的标题进入 SSIR 结构树，章 3 恢复且挂在根下。
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bare-headings.canonical.md"
            path.write_text(csm, encoding="utf-8")
            ssir = parse_csm(path)
        numbers = [node["number"] for node in self._nodes(ssir["structuralRoot"]) if node.get("number")]
        self.assertIn("3", numbers)
        chapter3 = next(node for node in self._nodes(ssir["structuralRoot"]) if node.get("number") == "3")
        self.assertEqual(chapter3["title"], "产品分类和型号命名")
        self.assertEqual([c["number"] for c in chapter3.get("children", [])], ["3.1"])
        clause31 = next(c for c in chapter3.get("children", []) if c.get("number") == "3.1")
        self.assertEqual([c["number"] for c in clause31.get("children", [])], ["3.1.1", "3.1.2"])

    def test_flat_heading_levels_are_restored_from_clause_depth(self) -> None:
        # 回归（2026-08-31，语料 90%+ 标题层级错）：MinerU 把章条标题全部压成
        # 同一层 ##。CSM-OCR-006 按编号段数提升（章 1 段→2、条 2 段→3、子条
        # 3 段→4），只提升不降低，标题文本不变。3.1.2.5派生代号（编号后无空格）
        # 也应提升。
        csm = """---
csm-version: "1.0"
document-type: standard
document-identifier: "QB/T 2946—2020"
standard-number: "QB/T 2946—2020"
title: "电动自行车用电动机及控制器"
language: zh-CN
source:
  mode: mineru
  original-file-name: "QB_T_2946-2020.pdf"
---

# 电动自行车用电动机及控制器

## 1 范围

## 2 规范性引用文件

## 3 产品分类和型号命名

## 3.1 电动机分类和型号命名

## 3.1.1 电动机分类

## 3.1.2 电动机型号命名

## 3.1.2.1 总则

## 3.1.2.5派生代号

## 4一般规定
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flat.canonical.md"
            path.write_text(csm, encoding="utf-8")
            doc = CSMParser().read(path)
        levels = {block.text: block.level for block in doc.blocks if block.kind == "heading"}
        self.assertEqual(levels["3 产品分类和型号命名"], 2)
        self.assertEqual(levels["3.1 电动机分类和型号命名"], 3)
        self.assertEqual(levels["3.1.1 电动机分类"], 4)
        self.assertEqual(levels["3.1.2 电动机型号命名"], 4)
        self.assertEqual(levels["3.1.2.1 总则"], 5)
        self.assertEqual(levels["3.1.2.5派生代号"], 5)
        # 章级标题（1 段）本来正确，不误提升也不降低。
        self.assertEqual(levels["4一般规定"], 2)
        self.assertEqual(levels["1 范围"], 2)
        # 千分位名称（1 000 kV）不是编号，不得按编号段数提升。
        self.assertNotIn("1 000 kV 变电站监控系统 技术规范", levels)

    def test_circle_bullet_list_items_parse_as_lists(self) -> None:
        # 回归（2026-08-31，GB_T_20001.6-2017 附录示例 6.1/6.2）：规程/规范类
        # 标准示例常用 ●/• 作第一层次项目符号，OCR 可能全角半角混用且无空格。
        # 此前 UNORDERED_ITEM_RE 不认 ●/•，条目被并入单个段落。
        csm = """---
csm-version: "1.0"
document-type: standard
document-identifier: "GB/T 20001.6—2017"
standard-number: "GB/T 20001.6—2017"
title: "标准编写规则 第6部分：规程标准"
language: zh-CN
source:
  mode: mineru
  original-file-name: "GB_T_20001.6-2017.pdf"
---

# 标准编写规则 第6部分：规程标准

## 6 规程的表述

### 6.1 示例

● 马铃薯脱毒试管苗繁育程序

• 甘薯脱毒试管苗繁育程序
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "circle-list.canonical.md"
            path.write_text(csm, encoding="utf-8")
            ssir = parse_csm(path)
        lists = [
            element
            for node in self._nodes(ssir["structuralRoot"])
            for element in node.get("contentElements", [])
            if element["presentationType"] == "list"
        ]
        self.assertTrue(lists, "●/• 行应解析为列表而不是段落")
        markers = [item["marker"] for content in lists for item in content["listItems"]]
        self.assertEqual(markers, ["●", "•"])

    def test_paragraph_shaped_table_caption_is_folded(self) -> None:
        # 回归（2026-08-31，GB_T_43726-2024 表4）：MinerU 把表题注抽成 directive
        # 前的普通段落（"表4 安装配合面的同轴度"，可隔"单位为毫米"行），渲染出
        # 「表4 安装配合面的同轴度」+「表4」双题注。应折进表格 caption。
        csm = """---
csm-version: "1.0"
document-type: standard
document-identifier: "GB/T 43726—2024"
standard-number: "GB/T 43726—2024"
title: "无刷直流力矩电动机通用技术条件"
language: zh-CN
source:
  mode: mineru
  original-file-name: "GB_T_43726-2024.pdf"
---

# 无刷直流力矩电动机通用技术条件

## 1 范围

本文件规定了电机的技术要求。

## 5.6 安装配合面的同轴度

除另有规定外，组装式电机安装配合面的同轴度应符合表4的规定。

表4 安装配合面的同轴度
单位为毫米
<!-- ssir:table id="mineru-table-t4" header-rows="1" caption-number="4" -->
| 机座号 | 25~55(不含55) | 160~320 |
| --- | --- | --- |
| 安装配合面的同轴度 | ≤0.03 | ≤0.08 |
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "table4.canonical.md"
            path.write_text(csm, encoding="utf-8")
            ssir = parse_csm(path)
        table = ssir["tables"][0]
        self.assertEqual(table.get("caption"), "安装配合面的同轴度")
        # 正文里不应残留被折走的题注段落
        leftovers = [
            content.get("textContent", "")
            for node in self._nodes(ssir["structuralRoot"])
            for content in node.get("contentElements", [])
            if content.get("presentationType") == "paragraph" and str(content.get("textContent", "")).startswith("表")
        ]
        self.assertEqual(leftovers, [])

    def test_table_unit_line_and_spaced_caption_fold_into_table(self) -> None:
        # 回归（2026-08-31，GB_T_43726-2024 表3/表4/表5/表8）：MinerU 把
        # "单位为毫米" 抽成 directive 前的独立段落（渲染到题注上方），且题注
        # 可能带空格（"表 3 轴伸径向圆跳动"）导致不折叠 + 表格自带 "**表3**"
        # 双题注。两者都应折进 table（caption + unit 属性）。
        csm = """---
csm-version: "1.0"
document-type: standard
document-identifier: "GB/T 43726—2024"
standard-number: "GB/T 43726—2024"
title: "无刷直流力矩电动机通用技术条件"
language: zh-CN
source:
  mode: mineru
  original-file-name: "GB_T_43726-2024.pdf"
---

# 无刷直流力矩电动机通用技术条件

## 5.3 径向间隙

表 3 轴伸径向圆跳动
单位为毫米
<!-- ssir:table id="mineru-table-t3" header-rows="1" caption-number="3" -->
| 机座号 | 25~55(不含55) |
| --- | --- |
| 轴伸径向圆跳动 | ≤0.02 |

## 5.10 绝缘介电强度

单位为毫安
<!-- ssir:table id="mineru-table-t8" header-rows="1" caption-number="8" -->
| 试验电压 | 250V |
| --- | --- |
| 峰值漏电流 | ≤0.5 |
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "units.canonical.md"
            path.write_text(csm, encoding="utf-8")
            ssir = parse_csm(path)
        tables = {t.get("number"): t for t in ssir["tables"]}
        self.assertEqual(tables["3"].get("caption"), "轴伸径向圆跳动")
        self.assertEqual(tables["3"].get("unit"), "毫米")
        # 表8 夹具只有单位行无题注：unit 折叠、无 caption
        self.assertIsNone(tables["8"].get("caption"))
        self.assertEqual(tables["8"].get("unit"), "毫安")
        # 单位行/题注段落不应残留在正文里
        leftovers = [
            content.get("textContent", "")
            for node in self._nodes(ssir["structuralRoot"])
            for content in node.get("contentElements", [])
            if content.get("presentationType") == "paragraph"
            and ("单位为" in str(content.get("textContent", "")) or str(content.get("textContent", "")).startswith("表"))
        ]
        self.assertEqual(leftovers, [])

    def test_normalize_writes_canonical_without_changing_body_semantics(self) -> None:
        raw = (
            b'\xef\xbb\xbf---\r\n'
            b'document-type: standard\r\n'
            b'document-identifier: "Q/TEST 003\xe2\x80\x942026"\r\n'
            b'standard-number: "Q/TEST 003\xe2\x80\x942026"\r\n'
            b'title: "Canonical \xe5\x9f\xba\xe7\xba\xbf"\r\n'
            b'language: zh-CN\r\n'
            b'---\r\n\r\n'
            b'# Canonical \xe5\x9f\xba\xe7\xba\xbf\r\n\r\n'
            b'## \xe5\x89\x8d\xe8\xa8\x80\r\n\r\n'
            b'\xe6\x9c\xac\xe6\x96\x87\xe4\xbb\xb6\xe6\x8c\x89\xe7\x85\xa7 GB/T 1.1\xe2\x80\x942020 \xe8\xb5\xb7\xe8\x8d\x89\xe3\x80\x82\r\n\r\n'
            b'## 1 \xe8\x8c\x83\xe5\x9b\xb4\r\n\r\n'
            b'\xe6\x9c\xac\xe6\x96\x87\xe4\xbb\xb6\xe8\xa7\x84\xe5\xae\x9a\xe6\xb5\x8b\xe8\xaf\x95\xe4\xba\xa7\xe5\x93\x81\xe3\x80\x82\r\n\r\n'
            b'## 4 \xe6\x8a\x80\xe6\x9c\xaf\xe8\xa6\x81\xe6\xb1\x82\r\n\r\n'
            b'\xe4\xba\xa7\xe5\x93\x81\xe9\xa2\x9d\xe5\xae\x9a\xe7\x94\xb5\xe5\x8e\x8b\xe5\xba\x94\xe4\xb8\xba 12 V\xe3\x80\x82\r\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            raw_path = Path(directory) / "raw.md"
            canonical_path = Path(directory) / "standard.canonical.md"
            raw_path.write_bytes(raw)
            ssir0, report = normalize_csm(raw_path, canonical_path)
            ssir0_reparsed = parse_csm(canonical_path)
            rendered = canonical_path.read_bytes()
        self.assertTrue(canonical_path.name.endswith(".canonical.md"))
        self.assertFalse(rendered.startswith(b"\xef\xbb\xbf"))
        self.assertNotIn(b"\r", rendered)
        self.assertIn(b'csm-version: \'1.0\'', rendered)
        self.assertTrue(any(issue.code == "CSM-ENC-001" for issue in report.issues))
        assert_ssir_equivalent(self, ssir0, ssir0_reparsed)

    def test_escaped_pipe_in_table_cell_survives_normalize_idempotently(self) -> None:
        # MinerU 表格单元格内联公式的绝对值竖线先经 mineru_html 首转义（raw.md 里
        # 是单反斜杠转义管道）；csm_normalizer 旧实现无条件给每个 | 补反斜杠，会把
        # 已转义管道二次转义成双反斜杠，再次 parse 时反斜杠转义追踪失效、公式里的
        # | 被误判为列分隔符（GB_T_755-2025 表12/13/15：row has 6 cells; expected 4
        # → parse 中断、渲染缺失）。写侧转义必须与读侧语义一致且幂等：已转义管道
        # 保持原样，只有裸管道才补反斜杠。规则对应：normalize/roundtrip 幂等
        # （escape_table_cell）。
        raw = (
            "---\n"
            "document-type: standard\n"
            "document-identifier: \"Q/TEST 007—2026\"\n"
            "standard-number: \"Q/TEST 007—2026\"\n"
            "title: \"Escaped pipe in table\"\n"
            "language: zh-CN\n"
            "---\n\n"
            "# Escaped pipe in table\n\n"
            "## 1 范围\n\n"
            '<!-- ssir:table id="t1" header-rows="1" caption-number="1" caption="温升限值修正" -->\n'
            "**表1 温升限值修正**\n"
            "| 项号 | 运行条件 | 修正 |\n"
            "| --- | --- | --- |\n"
            "| 1 | $\\| \\theta _ { c } - \\theta _ { c T } \\| \\leqslant 3 0 \\ \\mathrm { K }$ | 按协议 |\n"
            "| 2 | 海拔差 $H _ { T }$ | 不作修正 |\n\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            raw_path = Path(directory) / "raw.md"
            canonical_path = Path(directory) / "standard.canonical.md"
            raw_path.write_text(raw, encoding="utf-8")
            normalize_csm(raw_path, canonical_path)
            rendered = canonical_path.read_text(encoding="utf-8")
            ssir = parse_csm(canonical_path)
            canonical2_path = Path(directory) / "standard2.canonical.md"
            normalize_csm(canonical_path, canonical2_path)
            ssir2 = parse_csm(canonical2_path)
            canonical_bytes = canonical_path.read_bytes()
            canonical2_bytes = canonical2_path.read_bytes()
        table = ssir["tables"][0]
        self.assertEqual(table["colCount"], 3)
        self.assertIn("\\|", rendered)
        self.assertNotIn("\\\\|", rendered)
        self.assertEqual(canonical_bytes, canonical2_bytes)
        assert_ssir_equivalent(self, ssir, ssir2)

    def test_ocr_collapsed_dash_markers_still_parse_as_lists(self) -> None:
        # OCR 常把 GB/T 1.1 的 "——" 压成单个 "-"/"—" 且丢失后方空格
        # （GBT-C12）。此类行必须仍按列项解析，marker 取整段破折号。
        raw = (
            "---\n"
            "document-type: standard\n"
            "document-identifier: \"Q/TEST 004—2026\"\n"
            "standard-number: \"Q/TEST 004—2026\"\n"
            "title: \"Dash markers\"\n"
            "language: zh-CN\n"
            "---\n\n"
            "# Dash markers\n\n"
            "## 前言\n\n"
            "-标准的适用范围扩展到了永磁无刷直流电动机；\n"
            "\n"
            "—修改了电动机输入功率的技术要求；\n"
            "\n"
            "——增加了空载试验的要求。\n\n"
            "## 1 范围\n\n"
            "-交流电动机额定电压为220V。\n"
            "-电动机具有功率因数补偿功能时，其保证值应不小于0.95。\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            raw_path = Path(directory) / "raw.md"
            canonical_path = Path(directory) / "standard.canonical.md"
            raw_path.write_text(raw, encoding="utf-8")
            ssir, report = normalize_csm(raw_path, canonical_path)
            ssir_reparsed = parse_csm(canonical_path)
        lists = [
            element
            for node in self._nodes(ssir["structuralRoot"])
            for element in node.get("contentElements", [])
            if element["presentationType"] == "list"
        ]
        markers = [item["marker"] for content in lists for item in content["listItems"]]
        self.assertEqual(markers, ["-", "—", "——", "-", "-"])
        assert_ssir_equivalent(self, ssir, ssir_reparsed)

    def test_figure_unit_line_folds_into_figure(self) -> None:
        # 回归（2026-09-13，GB_T_1.1-2020 附录 E）：源文件里"单位为毫米"是每张图页
        # 第一行（9.7.4.1：图的右上方），canonical 里它写在图行之前。折进图节点 unit
        # 后渲染端把它与图放进同一组，满页的图另起一面时这一行随之成为新页第一行，
        # 不会被留在前页末（docs/12 §3.54）。
        csm = """---
csm-version: "1.0"
document-type: standard
document-identifier: "GB/T 1.1—2020"
standard-number: "GB/T 1.1—2020"
title: "标准化工作导则"
language: zh-CN
source:
  mode: mineru
  original-file-name: "GB_T_1.1-2020.pdf"
---

# 标准化工作导则

## 附录 E（规范性） 文件格式

图E.1～图E.12规定了不同文件的页面格式。

单位为毫米

![图 E.2 双数页格式](assets/images/e2.jpg)
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "annex-e.canonical.md"
            path.write_text(csm, encoding="utf-8")
            ssir = parse_csm(path)
        self.assertEqual(ssir["figures"][0].get("unit"), "毫米")
        # 折走的单位行不得残留为段落（否则渲染成图上方独立一行，分页还会被拆开）
        paragraphs = [
            content.get("textContent", "")
            for node in self._nodes(ssir["structuralRoot"])
            for content in node.get("contentElements", [])
            if content.get("presentationType") == "paragraph"
        ]
        self.assertNotIn("单位为毫米", paragraphs)

    def test_figure_unit_line_folds_with_directive_and_without_blank_line(self) -> None:
        # 两种书写形态都要折：① 单位行与图指令、图片行相邻（附录 E 的 raw 形态）；
        # ② 指令形态（ssir:figure 指令行夹在中间）。
        csm = """---
csm-version: "1.0"
document-type: standard
document-identifier: "GB/T 1.1—2020"
standard-number: "GB/T 1.1—2020"
title: "标准化工作导则"
language: zh-CN
source:
  mode: mineru
  original-file-name: "GB_T_1.1-2020.pdf"
---

# 标准化工作导则

## 附录 E（规范性） 文件格式

单位为毫米
![图 E.3 正文首页格式](assets/images/e3.jpg)

单位为毫米

<!-- ssir:figure id="f-9" -->

![图 E.4 封底格式](assets/images/e4.jpg)
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "annex-e2.canonical.md"
            path.write_text(csm, encoding="utf-8")
            ssir = parse_csm(path)
        self.assertEqual([figure.get("unit") for figure in ssir["figures"]], ["毫米", "毫米"])

    def test_unit_line_before_body_text_is_not_folded(self) -> None:
        # 反例（防规则过度触发）：单位行后不是图/表时保持原样——它可能只是正文句子
        # 的独立成段（如"单位为毫米"出现在说明性文字里，后面跟普通段落）。
        csm = """---
csm-version: "1.0"
document-type: standard
document-identifier: "T/UNIT 001—2026"
standard-number: "T/UNIT 001—2026"
title: "单位行反例"
language: zh-CN
source:
  mode: mineru
  original-file-name: "T_UNIT_001.pdf"
---

# 单位行反例

## 1 范围

单位为毫米

本文件规定了单位陈述行的处理。
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "neg.canonical.md"
            path.write_text(csm, encoding="utf-8")
            ssir = parse_csm(path)
        self.assertEqual(ssir["figures"], [])
        paragraphs = [
            content.get("textContent", "")
            for node in self._nodes(ssir["structuralRoot"])
            for content in node.get("contentElements", [])
            if content.get("presentationType") == "paragraph"
        ]
        self.assertIn("单位为毫米", paragraphs)

    def test_ocr_glyph_confused_markers_are_corrected_and_recorded(self) -> None:
        # OCR 把 l）误读为 1）、把 1 误读为 l/I、把 0 误读为 O；多数派上下文
        # 中的可混淆项在解析时纠正（CSM-OCR-001 repaired），canonical 随之更正。
        raw = (
            "---\n"
            "document-type: standard\n"
            "document-identifier: \"Q/TEST 005—2026\"\n"
            "standard-number: \"Q/TEST 005—2026\"\n"
            "title: \"Glyph markers\"\n"
            "language: zh-CN\n"
            "---\n\n"
            "# Glyph markers\n\n"
            "## 4 技术要求\n\n"
            "铭牌上应标明的项目如下：\n\n"
            "a） 电动机名称；\n"
            "b） 电动机型号；\n"
            "c） 额定电压(V)；\n"
            "1） 绝缘等级；\n"
            "e） 防护等级；\n"
            "f） 制造日期。\n\n"
            "试验次数如下：\n\n"
            "1) 第一次；\n"
            "2) 第二次；\n"
            "3) 第三次；\n"
            "l) 第四次；\n"
            "O) 第五次。\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            raw_path = Path(directory) / "raw.md"
            canonical_path = Path(directory) / "standard.canonical.md"
            raw_path.write_text(raw, encoding="utf-8")
            ssir, report = normalize_csm(raw_path, canonical_path)
            rendered = canonical_path.read_text(encoding="utf-8")
            ssir_reparsed = parse_csm(canonical_path)
        self.assertIn("l） 绝缘等级；", rendered)
        self.assertIn("1） 第四次；", rendered)
        self.assertIn("0） 第五次。", rendered)
        self.assertNotIn("1） 绝缘等级；", rendered)
        repaired = [i for i in report.issues if i.code == "CSM-OCR-001" and i.repaired]
        self.assertEqual(len(repaired), 3)
        # 纠正后 SSIR 与 canonical 回环稳定
        assert_ssir_equivalent(self, ssir, ssir_reparsed)

    def test_marker_parens_and_clause_spacing_normalised(self) -> None:
        # GBT-C19：列表编号括号统一全角（d) → d））；GBT-B02：正文条号后
        # 统一一个空格（4.6.1电动机 → 4.6.1 电动机）。
        raw = (
            "---\n"
            "document-type: standard\n"
            "document-identifier: \"Q/TEST 006—2026\"\n"
            "standard-number: \"Q/TEST 006—2026\"\n"
            "title: \"Spacing\"\n"
            "language: zh-CN\n"
            "---\n\n"
            "# Spacing\n\n"
            "## 4 技术要求\n\n"
            "4.6.1电动机表面应无污迹。\n\n"
            "4.6.2试验项目如下：\n\n"
            "d) 额定频率(Hz)；\n"
            "e) 额定电压(V)。\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            raw_path = Path(directory) / "raw.md"
            canonical_path = Path(directory) / "standard.canonical.md"
            raw_path.write_text(raw, encoding="utf-8")
            normalize_csm(raw_path, canonical_path)
            rendered = canonical_path.read_text(encoding="utf-8")
        self.assertIn("4.6.1 电动机表面应无污迹。", rendered)
        self.assertIn("d） 额定频率（Hz）；", rendered)
        self.assertIn("e） 额定电压（V）。", rendered)

    def test_same_input_produces_deterministic_json(self) -> None:
        path = ROOT / "corpus/golden/csm/Q_TQDZ_004-2026.canonical.md"
        self.assertEqual(json_bytes(parse_csm(path)), json_bytes(parse_csm(path)))

    def test_duplicate_ssir_id_is_rejected(self) -> None:
        text = (ROOT / "corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md").read_text(encoding="utf-8")
        duplicate = text.replace(
            '<!-- ssir:figure id="fig-001" asset-status="missing" -->',
            '<!-- ssir:table id="tbl-001" header-rows="1" -->',
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.md"
            path.write_text(duplicate, encoding="utf-8")
            with self.assertRaises(CSMError) as raised:
                CSMParser().read(path)
        self.assertIn("duplicate ssir id", str(raised.exception))

    def test_unknown_directive_is_rejected(self) -> None:
        text = (ROOT / "corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md").read_text(encoding="utf-8")
        invalid = text.replace("<!-- ssir:formula", "<!-- ssir:unsupported", 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.md"
            path.write_text(invalid, encoding="utf-8")
            ssir, report = parse_csm_with_report(path)
            with self.assertRaises(CSMError) as raised:
                CSMParser(strict=True).read(path)
        self.assertEqual(len(ssir["unknownContents"]), 1)
        self.assertTrue(any("unsupported ssir directive" in issue.message for issue in report.issues))
        self.assertIn("unsupported ssir directive", str(raised.exception))

    def test_recoverable_metadata_and_title_issues_convert_with_report(self) -> None:
        csm = '''---
document-type: standard
---

# 可恢复输入

## 1 范围

本文件规定测试产品。
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "recoverable.csm.md"
            path.write_text(csm, encoding="utf-8", newline="\r\n")
            ssir, report = parse_csm_with_report(path)
            with self.assertRaises(CSMError):
                parse_csm(path, strict=True)
        self.assertEqual(ssir["metadata"]["common"]["title"], "可恢复输入")
        self.assertEqual(report.overall_status, "partial")
        codes = {issue.code for issue in report.issues}
        self.assertIn("CSM-META-005", codes)
        self.assertIn("CSM-ENC-002", codes)
        self.assertIn("GB-T-1.1-FOREWORD-001", codes)

    def test_mineru_page_markers_are_dropped_even_mid_paragraph(self) -> None:
        csm = '''---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/TEST 003—2026"
standard-number: "Q/TEST 003—2026"
title: "页码标记"
language: zh-CN
source: {mode: mineru-pdf, provenance: none}
extensions: {}
---

# 页码标记

## 1 范围

本文件规定测试产品。

3
<!-- /ssir:mineru-pages -->
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "markers.csm.md"
            path.write_text(csm, encoding="utf-8")
            ssir, report = parse_csm_with_report(path)
        texts = []
        for node in ssir["structuralRoot"]["children"]:
            for content in node.get("contentElements", []):
                texts.append(str(content.get("textContent", "")))
        joined = "\n".join(texts)
        self.assertNotIn("mineru-pages", joined)
        self.assertIn("本文件规定测试产品。", joined)

    def test_short_table_row_is_padded_and_reported(self) -> None:
        csm = '''---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/TEST 001—2026"
standard-number: "Q/TEST 001—2026"
title: "表格修复"
language: zh-CN
source: {mode: user-markdown, provenance: none}
extensions: {}
---

# 表格修复

## 前言

本文件按照 GB/T 1.1—2020 起草。

## 1 范围

本文件规定测试产品。

| 项目 | 条件 | 值 |
|---|---|---|
| 温度 | 40 |
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "short-table.csm.md"
            path.write_text(csm, encoding="utf-8")
            ssir, report = parse_csm_with_report(path)
        self.assertEqual(ssir["tables"][0]["rows"][1]["cells"][2]["text"], "")
        self.assertTrue(any(issue.code == "CSM-TABLE-001" and issue.repaired for issue in report.issues))

    def test_stray_figure_between_split_table_parts_folds_into_last_row(self) -> None:
        # GB_T_23132-2024 表2 型（CSM-TABLE-002）：MinerU 跨页表格把某行单元格
        # 内的图排在 <table> 元素外，读取顺序上前表 → 裸图 → 续表（题注带"续"）。
        # 修复：裸图折回前表最后一行第一个不含图且非首格的单元格。
        csm = '''---
csm-version: "1.0"
document-type: standard
document-identifier: "GB/T 23132—2024"
standard-number: "GB/T 23132—2024"
title: "表中图归位"
language: zh-CN
source: {mode: mineru, provenance: none}
extensions: {}
---

# 表中图归位

## 1 范围

本文件规定电动剃须刀。

<!-- ssir:table id="mineru-table-p001-002" header-rows="1" caption-number="2" caption="锋利度试验区域" -->
| 类型 | 试验区域分割 | 插入角度 |
| --- | --- | --- |
| 旋转式 | 单环旋转式取1、2、3区域 | ![](assets/images/5252cb2b.jpg) |

![](assets/images/89e2bc42.jpg)

<!-- ssir:table id="mineru-table-p001-003" header-rows="1" caption-number="2" caption="锋利度试验区域（续）" -->
| 类型 | 试验区域分割 | 插入角度 |
| --- | --- | --- |
| 往复式 | ![](assets/images/1e30288f.jpg) | ![](assets/images/5fff4593.jpg) |
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stray-table-image.csm.md"
            path.write_text(csm, encoding="utf-8")
            ssir, report = parse_csm_with_report(path)
        first = next(t for t in ssir["tables"] if t["caption"] == "锋利度试验区域")
        last_row = sorted(first["rows"], key=lambda r: r["rowIndex"])[-1]
        cells = sorted(last_row["cells"], key=lambda c: c["colIndex"])
        # 图折回试验区域分割（col 1）单元格，插入角度（col 2）原有图保留。
        self.assertIn("89e2bc42", cells[1]["text"])
        self.assertIn("5252cb2b", cells[2]["text"])
        # 游离图不再作为 figure 存在。
        self.assertFalse(any("89e2bc42" in str(fig.get("assetRef", "")) for fig in ssir["figures"]))
        self.assertTrue(any(issue.code == "CSM-TABLE-002" and issue.repaired for issue in report.issues))

    def test_stray_figure_not_folded_when_no_image_cell_in_last_row(self) -> None:
        # 前表最后一行全是纯文本（没有含图单元格）→ 不归位（无法确认图属于表格，
        # 保守保留为独立图）。
        csm = '''---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/TEST 003—2026"
standard-number: "Q/TEST 003—2026"
title: "不误归位"
language: zh-CN
source: {mode: user-markdown, provenance: none}
extensions: {}
---

# 不误归位

## 1 范围

本文件规定测试产品。

<!-- ssir:table id="t1" header-rows="1" caption-number="1" caption="示例" -->
| 项目 | 值 |
| --- | --- |
| 温度 | 40 |

![](assets/images/stray.jpg)

<!-- ssir:table id="t2" header-rows="1" caption-number="1" caption="示例（续）" -->
| 项目 | 值 |
| --- | --- |
| 湿度 | 60 |
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "no-fold.csm.md"
            path.write_text(csm, encoding="utf-8")
            ssir, report = parse_csm_with_report(path)
        self.assertFalse(any(issue.code == "CSM-TABLE-002" for issue in report.issues))
        # 图仍保留为独立 figure。
        self.assertTrue(any("stray" in str(fig.get("assetRef", "")) for fig in ssir["figures"]))
        table = ssir["tables"][0]
        cell_texts = [c.get("text", "") for r in table["rows"] for c in r.get("cells", [])]
        self.assertFalse(any("stray" in t for t in cell_texts))

    def test_table_cell_image_text_kept_as_extracted_without_column_move_evidence(self) -> None:
        # CSM-TABLE-003 原则：不把"图在上/文字在下"规定为通用版式。未发生列错位
        # （B）的表严格按提取顺序渲染——`文字 ![]()`（文字在图前）保持原样，
        # 不做格内重排。
        csm = '''---
csm-version: "1.0"
document-type: standard
document-identifier: "GB/T 23132—2024"
standard-number: "GB/T 23132—2024"
title: "格内顺序保持"
language: zh-CN
source: {mode: mineru, provenance: none}
extensions: {}
---

# 格内顺序保持

## 1 范围

本文件规定电动剃须刀。

<!-- ssir:table id="t1" header-rows="1" caption-number="1" caption="试验区域" -->
| 类型 | 试验区域分割 | 插入角度 |
| --- | --- | --- |
| 旋转式 | 单环旋转式取1、2、3区域 ![](assets/images/a.jpg) | ![](assets/images/b.jpg) |
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "img-order-kept.csm.md"
            path.write_text(csm, encoding="utf-8")
            ssir, report = parse_csm_with_report(path)
        table = ssir["tables"][0]
        data_row = sorted(table["rows"], key=lambda r: r["rowIndex"])[-1]
        cells = sorted(data_row["cells"], key=lambda c: c["colIndex"])
        # 无列错位证据 → 不重排：文字保持在前（提取原样）。
        self.assertIn("单环旋转式取1、2、3区域", cells[1]["text"])
        self.assertIn("![](assets/images/a.jpg)", cells[1]["text"])
        self.assertNotIn("CSM-TABLE-003", [issue.code for issue in report.issues])

    def test_misplaced_cell_text_moved_to_image_column(self) -> None:
        # CSM-TABLE-003 列错位：GB_T_23132 表2（续）往复式行——说明文字
        # "单片往复式取2个区域；…"被 MinerU 误归到第3列（插入角度，该列其它
        # 行均为纯图），第2列（试验区域分割）是纯图格 → 文字移回第2列图后，
        # 第3列只留图。
        csm = '''---
csm-version: "1.0"
document-type: standard
document-identifier: "GB/T 23132—2024"
standard-number: "GB/T 23132—2024"
title: "列错位归位"
language: zh-CN
source: {mode: mineru, provenance: none}
extensions: {}
---

# 列错位归位

## 1 范围

本文件规定电动剃须刀。

<!-- ssir:table id="t1" header-rows="1" caption-number="2" caption="锋利度试验区域（续）" -->
| 类型 | 试验区域分割 | 插入角度 |
| --- | --- | --- |
| 往复式 | ![](assets/images/1e30288f.jpg) | 单片往复式取2个区域；双片往复式按照单片往 ![](assets/images/5fff4593.jpg) |
| 修剪器 | 划分为2个区域 ![](assets/images/06cf2e4d.jpg) | ![](assets/images/16f5c3a2.jpg) |
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "misplaced.csm.md"
            path.write_text(csm, encoding="utf-8")
            ssir, report = parse_csm_with_report(path)
        table = ssir["tables"][0]
        by_row = {r["rowIndex"]: r for r in table["rows"]}
        wangfu = sorted(by_row[1]["cells"], key=lambda c: c["colIndex"])
        xiu = sorted(by_row[2]["cells"], key=lambda c: c["colIndex"])
        # 往复式：第2列 = 图 + 文字（图在前），第3列 = 纯图。
        self.assertTrue(wangfu[1]["text"].startswith("![](assets/images/1e30288f.jpg)"))
        self.assertIn("单片往复式取2个区域", wangfu[1]["text"])
        self.assertEqual(wangfu[1]["text"].count("assets/images/1e30288f.jpg"), 1)
        self.assertEqual(wangfu[2]["text"].strip(), "![](assets/images/5fff4593.jpg)")
        # 修剪器：第2列 = 图 + 文字（重排为图在前），第3列 = 纯图（不受影响）。
        self.assertTrue(xiu[1]["text"].startswith("![](assets/images/06cf2e4d.jpg)"))
        self.assertIn("划分为2个区域", xiu[1]["text"])
        self.assertEqual(xiu[2]["text"].strip(), "![](assets/images/16f5c3a2.jpg)")
        self.assertTrue(any(issue.code == "CSM-TABLE-003" and issue.repaired for issue in report.issues))

    def test_cell_text_not_moved_when_column_has_text_in_other_rows(self) -> None:
        # 列错位不误伤：第2列在多数行都含文字（旋转式/修剪器），第3列文字仅
        # 旋转式一行 → 保守不动（该列文字不是"仅此一行"），且整表不发生 B →
        # 格内顺序也保持提取原样（不强行重排为图在前）。
        csm = '''---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/TEST 004—2026"
standard-number: "Q/TEST 004—2026"
title: "不误移文字"
language: zh-CN
source: {mode: mineru, provenance: none}
extensions: {}
---

# 不误移文字

## 1 范围

本文件规定测试产品。

<!-- ssir:table id="t1" header-rows="1" caption-number="1" caption="示例" -->
| 类型 | 试验区域分割 | 插入角度 |
| --- | --- | --- |
| 旋转式 | 单环旋转式取1、2、3区域 ![](assets/images/a.jpg) | 角度说明 ![](assets/images/b.jpg) |
| 修剪器 | 划分为2个区域 ![](assets/images/c.jpg) | ![](assets/images/d.jpg) |
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "no-move.csm.md"
            path.write_text(csm, encoding="utf-8")
            ssir, report = parse_csm_with_report(path)
        table = ssir["tables"][0]
        by_row = {r["rowIndex"]: r for r in table["rows"]}
        rotary = sorted(by_row[1]["cells"], key=lambda c: c["colIndex"])
        # 旋转式第3列文字保留在第3列（未被移走）。
        self.assertIn("角度说明", rotary[2]["text"])
        self.assertIn("![](assets/images/b.jpg)", rotary[2]["text"])
        # 旋转式第2列保持提取顺序（文字在前、图在后）——整表无 B，不做格内重排。
        self.assertIn("单环旋转式", rotary[1]["text"])
        self.assertIn("![](assets/images/a.jpg)", rotary[1]["text"])
        self.assertNotIn("CSM-TABLE-003", [issue.code for issue in report.issues])

    def test_product_optional_sections_do_not_block_conversion(self) -> None:
        csm = '''---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/TEST 002—2026"
standard-number: "Q/TEST 002—2026"
title: "最小产品标准"
language: zh-CN
source: {mode: user-markdown, provenance: none}
extensions: {standard-profile: product}
---

# 最小产品标准

## 前言

本文件按照 GB/T 1.1—2020 起草。

## 1 范围

本文件规定测试产品。

## 4 技术要求

产品额定电压应为 12 V。
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "minimal-product.csm.md"
            path.write_text(csm, encoding="utf-8")
            ssir, report = parse_csm_with_report(path)
        self.assertEqual(ssir["documentType"], "standard")
        self.assertFalse(any("取样" in issue.message or "检验规则" in issue.message for issue in report.issues))

    def test_unclosed_formula_remains_unacceptable(self) -> None:
        text = (ROOT / "corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md").read_text(encoding="utf-8")
        invalid = text.replace("$$\nP = U I\n$$", "$$\nP = U I", 1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unclosed.csm.md"
            path.write_text(invalid, encoding="utf-8")
            with self.assertRaises(CSMError) as raised:
                parse_csm(path)
        self.assertIn("unterminated formula block", str(raised.exception))

    def test_raw_formula_and_table_merge_are_preserved(self) -> None:
        csm = '''---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/TEST 001—2026"
standard-number: "Q/TEST 001—2026"
title: "合并单元格测试"
language: zh-CN
source:
  mode: user-markdown
  provenance: none
extensions: {}
---

# 合并单元格测试

## 1 范围

本文件规定测试产品的要求。

<!-- ssir:table id="tbl-001" header-rows="1" -->
**表1 测试数据**

| 项目 | 条件 | 值 |
|------|------|----|
| 温度 | 高温 | 40 |
| 温度 | 低温 | -20 |

<!-- ssir:table-merge table="tbl-001" row="1" column="1" rowspan="2" colspan="1" -->

<!-- ssir:formula id="fm-001" format="raw" -->
```formula
U_N = U_0 / sqrt(3)
```
式（1）
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "merge.csm.md"
            path.write_text(csm, encoding="utf-8")
            ssir = parse_csm(path)
        self.assertEqual(ssir["tables"][0]["rows"][1]["cells"][0]["rowspan"], 2)
        self.assertEqual(ssir["formulas"][0]["rawText"], "U_N = U_0 / sqrt(3)")
        self.assertNotIn("latex", ssir["formulas"][0])

    @staticmethod
    def _nodes(node: dict):
        yield node
        for child in node.get("children", []):
            yield from CSMToSSIRTests._nodes(child)


class NoteAndListMarkerTests(unittest.TestCase):
    """2026-08-31 GB_T_20001.6 第二轮：注字号、确立断行、●/• 符号统一。"""

    @staticmethod
    def _parse(body: str):
        csm = (
            "---\n"
            'csm-version: "1.0"\n'
            "document-type: standard\n"
            "document-identifier: ssir:TEST-1\n"
            'title: "测试"\n'
            "---\n\n"
            f"# 测试\n\n{body}\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t.canonical.md"
            path.write_text(csm, encoding="utf-8")
            return parse_csm_with_report(path)

    @staticmethod
    def _elements(ssir: dict):
        for node in CSMToSSIRTests._nodes(ssir["structuralRoot"]):
            yield from node.get("contentElements", [])

    def test_standalone_note_line_becomes_note_element(self) -> None:
        # 3.2 的独立「注：」行必须是 note CE，渲染才走小五号（GBT-B10）。
        ssir, _ = self._parse(
            "## 3 术语和定义\n\n"
            "### 3.1 指示型条款\n\n"
            "表达需要履行的行动的条款。\n\n"
            "注：指示型条款用祈使句表达。"
        )
        notes = [ce for ce in self._elements(ssir) if ce["presentationType"] == "note"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["textContent"], "注：指示型条款用祈使句表达。")

    def test_inline_numbered_notes_split_into_note_elements(self) -> None:
        # 3.1 术语定义里被 OCR 合并进定义段的「注1：…。注2：…。」应在
        # 句界切分为独立 note（GB_T_20001.6 3.1 型）。
        ssir, _ = self._parse(
            "## 3 术语和定义\n\n"
            "### 3.1 规程标准\n\n"
            "为活动规定明确程序的标准。注1：过程包括设计、制造。注2：不产生试验结果。"
        )
        notes = [ce for ce in self._elements(ssir) if ce["presentationType"] == "note"]
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[0]["textContent"], "注1：过程包括设计、制造。")
        self.assertEqual(notes[1]["textContent"], "注2：不产生试验结果。")
        paras = [ce for ce in self._elements(ssir) if ce["presentationType"] == "paragraph"]
        self.assertEqual(paras[0]["textContent"], "为活动规定明确程序的标准。")

    def test_blank_line_paragraph_joins_non_sentence_final_line(self) -> None:
        # 6.2「使用词语"确\n\n立"」：MinerU 在词语中间插空行，上行不以连接性
        # 标点结尾（旧规则不合并）——应合并为一句（"确立"不再断行）。
        ssir, _ = self._parse(
            "## 6 要素的编写\n\n"
            "### 6.2 范围\n\n"
            "范围的典型表述形式为：使用词语“确\n\n"
            "立”；表述行为指示和转换条件时，使用词语“规定”。"
        )
        paras = [ce for ce in self._elements(ssir) if ce["presentationType"] == "paragraph"]
        joined = "".join(ce["textContent"] for ce in paras)
        self.assertIn("“确立”", joined)
        self.assertNotIn("“确\n", joined)

    def test_bullet_markers_unified_to_majority(self) -> None:
        # 6.1「其他」前符号不一致：源 PDF 全 ●，OCR 把末项读成 •——按多数派统一。
        ssir, report = self._parse(
            "### 6.1 标记方法\n\n"
            "标记的内容包括：\n\n"
            "● 做标记时植株的性状；\n"
            "● 标记的编号；\n"
            "● 标记时间；\n"
            "• 其他。"
        )
        lists = [ce for ce in self._elements(ssir) if ce["presentationType"] == "list"]
        markers = [item["marker"] for content in lists for item in content["listItems"]]
        self.assertEqual(set(markers), {"●"})
        repair = [i for i in report.issues if i.code == "CSM-OCR-001"]
        self.assertTrue(any("unified to" in (i.message or "") for i in repair))

    def test_interpunct_items_parse_as_list_and_unify_to_majority(self) -> None:
        # 回归（2026-08-31，GB_T_1.1-2020 前言 8.3）：OCR 把第二层次间隔号
        # · 与 • 混读。· 行此前不解析为列表项（UNORDERED_ITEM_RE 缺 U+00B7），
        # 沦为独立段落、兄弟 • 被并入相邻字母列表。应解析为列表项，且
        # b)/c) 两个子列表同块时 · 按多数派统一为 •（同一条款符号一致）。
        ssir, report = self._parse(
            "## 8 要素的编写\n\n"
            "### 8.3 前言\n\n"
            "a） 文件起草所依据的标准。\n"
            "b） 文件与其他文件的关系。需要说明以下两方面的内容：\n\n"
            "• 与其他标准的关系；\n"
            "• 分为部分的文件说明其所属的部分。\n\n"
            "c） 文件与代替文件的关系。需要说明以下两方面的内容：\n\n"
            "· 给出被代替、废止的所有文件的编号和名称；\n"
            "• 列出与前一版本相比的主要技术变化。\n"
        )
        lists = [ce for ce in self._elements(ssir) if ce["presentationType"] == "list"]
        markers = [item["marker"] for content in lists for item in content["listItems"]]
        self.assertIn("•", markers)
        self.assertNotIn("·", markers)
        item_texts = [str(item.get("text", "")) for content in lists for item in content["listItems"]]
        replaced = item_texts.index("给出被代替、废止的所有文件的编号和名称；")
        self.assertEqual(
            [item["marker"] for content in lists for item in content["listItems"]][replaced],
            "•",
        )
        repair = [i for i in report.issues if i.code == "CSM-OCR-001"]
        self.assertTrue(any("unified to" in (i.message or "") for i in repair))

    def test_dash_marker_variants_unified_to_majority(self) -> None:
        # 回归（2026-08-31）：OCR 把同一破折号读成长度不一的横杠（-、—、——、
        # ———）。同一条款列项符号应按多数派统一（GB_T_1.1-2020 前言 8.3 与
        # GB_T_20001.4/5/6/10 前言清单均出现 -/—/—— 混用）。
        ssir, report = self._parse(
            "## 6 要素的编写\n\n"
            "### 6.3 列项\n\n"
            "列项符号如下：\n\n"
            "- 第一项；\n"
            "- 第二项；\n"
            "—— 第三项。\n"
        )
        lists = [ce for ce in self._elements(ssir) if ce["presentationType"] == "list"]
        markers = [item["marker"] for content in lists for item in content["listItems"]]
        self.assertEqual(markers, ["-", "-", "-"])
        repair = [i for i in report.issues if i.code == "CSM-OCR-001"]
        self.assertTrue(any("unified to" in (i.message or "") for i in repair))

    def test_dash_interpunct_cross_family_unified_to_majority(self) -> None:
        # 同一条款下列表符号混用破折号与间隔号（GB_T_20001.6 同类案例：
        # ●/• 混读）：按多数派符号纠正个别误识项（· → ——）。
        ssir, report = self._parse(
            "## 6 规程的表述\n\n"
            "### 6.1 示例\n\n"
            "繁育程序包括：\n\n"
            "—— 马铃薯脱毒试管苗繁育程序；\n"
            "—— 甘薯脱毒试管苗繁育程序；\n"
            "· 其他。\n"
        )
        lists = [ce for ce in self._elements(ssir) if ce["presentationType"] == "list"]
        markers = [item["marker"] for content in lists for item in content["listItems"]]
        self.assertEqual(markers, ["——", "——", "——"])
        repair = [i for i in report.issues if i.code == "CSM-OCR-001"]
        self.assertTrue(any("unified to" in (i.message or "") for i in repair))

    def test_symbol_marker_ties_are_not_unified(self) -> None:
        # 平手（2:2）无法确认多数派，保守不统一——真嵌套列项（第一层次 ——
        # 项下挂第二层次 · 子项）不误伤；渲染层 _list_marker 仍会归一显示。
        ssir, report = self._parse(
            "### 6.1 标记方法\n\n"
            "标记的内容包括：\n\n"
            "—— 第一项；\n"
            "· 第二项。\n"
            "—— 第三项；\n"
            "· 第四项。\n"
        )
        lists = [ce for ce in self._elements(ssir) if ce["presentationType"] == "list"]
        markers = [item["marker"] for content in lists for item in content["listItems"]]
        self.assertEqual(markers, ["——", "·", "——", "·"])
        repair = [i for i in report.issues if i.code == "CSM-OCR-001"]
        self.assertFalse(any("unified to" in (i.message or "") for i in repair))


class Gb3100ParserFixTests(unittest.TestCase):
    """GB_3100-2026 解析层修复回归（2026-09-02）。

    Fix A：空行续接收窄到 ，、 结尾（术语行不与定义并段）；
    Fix B：裸列项（逐行、；收尾）按行拆段（4.2 七个常量）；
    Fix G：跨页表注外溢吸收回表末注行（表4 注6 续句 + 注7~注11）。
    """

    @staticmethod
    def _parse(body: str):
        csm = (
            "---\n"
            'csm-version: "1.0"\n'
            "document-type: standard\n"
            "document-identifier: ssir:TEST-1\n"
            'title: "测试"\n'
            "---\n\n"
            f"# 测试\n\n{body}\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t.canonical.md"
            path.write_text(csm, encoding="utf-8")
            return parse_csm_with_report(path)

    @staticmethod
    def _elements(ssir: dict):
        for node in CSMToSSIRTests._nodes(ssir["structuralRoot"]):
            yield from node.get("contentElements", [])

    def test_term_line_and_definition_not_merged(self) -> None:
        # Fix A（3.7 型）：术语行（拉丁结尾「coherent system of units」）与空行
        # 后的定义正文必须分成两段——旧规则（不以 。！？ 结尾即续接）会把
        # 术语行与定义并成一段（用户报告「术语3.7的解释正文没有另起一行」）。
        ssir, _ = self._parse(
            "## 3 术语和定义\n\n"
            "### 3.7 一贯单位制\n\n"
            "一贯单位制　coherent system of units\n\n"
            "在给定量制中，每个导出量的单位均为一贯导出单位的单位制。"
        )
        paras = [ce for ce in self._elements(ssir) if ce["presentationType"] == "paragraph"]
        texts = [ce["textContent"] for ce in paras]
        self.assertEqual(len(texts), 2)
        self.assertEqual(texts[0], "一贯单位制　coherent system of units")
        self.assertEqual(texts[1], "在给定量制中，每个导出量的单位均为一贯导出单位的单位制。")

    def test_comma_ending_line_still_joins_after_blank(self) -> None:
        # Fix A 的另一半：，/、 结尾（MinerU 误插空行的连接点）仍续接为同段。
        ssir, _ = self._parse(
            "## 6 要素的编写\n\n"
            "### 6.2 范围\n\n"
            "范围的典型表述形式为：使用词语“确，\n\n"
            "立”；表述行为指示和转换条件时，使用词语“规定”。"
        )
        paras = [ce for ce in self._elements(ssir) if ce["presentationType"] == "paragraph"]
        texts = [ce["textContent"] for ce in paras]
        self.assertEqual(len(texts), 1)
        self.assertIn("“确，立”", texts[0])

    def test_enumeration_lines_split_into_separate_paragraphs(self) -> None:
        # Fix B（4.2 型）：引导语后逐行成列的枚举行（每条以 ；收尾）必须各成
        # 一段——旧规则把 ；收尾行与下一行续接，七个定义常量挤成一行流。
        ssir, _ = self._parse(
            "## 4 SI\n\n"
            "4.2 SI 是采用如下常量的单位制：\n\n"
            "铯 133 原子不受干扰的基态超精细跃迁频率为 9 192 631 770 Hz；\n\n"
            "真空光速 c 为 299 792 458 m/s；\n\n"
            "普朗克常量 h为 6.62607015×10−34 J s；"
        )
        paras = [ce for ce in self._elements(ssir) if ce["presentationType"] == "paragraph"]
        texts = [ce["textContent"] for ce in paras]
        self.assertEqual(len(texts), 4)
        self.assertEqual(texts[1], "铯 133 原子不受干扰的基态超精细跃迁频率为 9 192 631 770 Hz；")
        self.assertEqual(texts[2], "真空光速 c 为 299 792 458 m/s；")
        self.assertEqual(texts[3], "普朗克常量 h为 6.62607015×10−34 J s；")

    def test_table_note_spill_absorbed_back_into_note_row(self) -> None:
        # Fix G（表4 型）：MinerU 把表末注行（注6 未以句末标点收尾）后的续句
        # 段与注7~注11 注块抽到表格外（渲染时落框外）——吸收回表末注行单元格，
        # 以 <br> 分行（与 merge 阶段恢复的 <br> 行结构同一约定）；新块停止。
        table = Block(
            kind="table",
            start_line=1,
            end_line=1,
            data={
                "rows": [
                    ["注6：道尔顿（Da）和统一的原子质量单位（u）是同一单位的可互用名称（和符号），它等于处", "", ""],
                ]
            },
        )
        continuation = Block(
            kind="paragraph",
            start_line=3,
            end_line=3,
            text="于静止状态和基态的自由碳12原子质量的1/12。道尔顿的这个值是2018年国际数据委员会（CODATA）平差给出的推荐值。",
        )
        note7 = Block(kind="note", start_line=5, end_line=5, text="注7：电子伏是电子在真空中通过一个1 V的电位差而获得的动能。")
        note11 = Block(kind="note", start_line=7, end_line=7, text="注11：公里为千米的俗称，符号为km。")
        heading = Block(kind="heading", start_line=9, end_line=9, text="9.2 根据习惯")
        warnings: list[str] = []
        result = _absorb_table_note_spill([table, continuation, note7, note11, heading], warnings)
        cell = result[0].data["rows"][-1][0]
        self.assertIn("它等于处<br>于静止状态和基态的自由碳12原子质量的1/12", cell)
        self.assertIn("<br>注7：电子伏", cell)
        self.assertIn("<br>注11：公里为千米的俗称", cell)
        # 溢出块被吸收（消费）进表格，剩余 table + 新块 heading 两个
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1].kind, "heading")
        self.assertTrue(warnings)

    def test_table_note_spill_not_absorbed_after_complete_sentence(self) -> None:
        # Fix G 保守边界：表末注行已以句号收尾时，后续普通段落是表格外正文，
        # 不吸收（防误并）。
        table = Block(
            kind="table",
            start_line=1,
            end_line=1,
            data={"rows": [["注1：一般常用时间单位。", "", ""]]},
        )
        para = Block(kind="paragraph", start_line=3, end_line=3, text="这是表格后的普通正文段落。")
        warnings: list[str] = []
        result = _absorb_table_note_spill([table, para], warnings)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].data["rows"][-1][0], "注1：一般常用时间单位。")


class TermEntryLineTests(unittest.TestCase):
    """术语行判据单源（CSM-OCR-003 / CSM-OCR-007，GB/T 1.1-2020 8.7.3.1、10.3.5）。

    用户报告（2026-09-15，GB_3100-2026）：术语 3.8「国际单位制　International System
    of Units, SI」与 3.13「SI词头　SI prefix」在目次里只剩条目编号——术语行的字符类在
    parser（间隙归一、条目形态归一）与 builder（term/englishTerm 抽取）各写一份且都偏窄
    （术语限**纯汉字串**、英文对应词不含逗号），于是术语带拉丁缩写、英文对应词带逗号的
    条目在两种抽取形态下都抽不出 term/englishTerm。判据现由 `term_entry_pair` 单源提供。
    """

    HEADER = (
        "---\n"
        'csm-version: "1.0"\n'
        "document-type: standard\n"
        "document-identifier: ssir:TEST-1\n"
        'title: "测试"\n'
        "---\n\n"
        "# 测试\n\n"
    )

    @classmethod
    def _parse(cls, body: str):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t.canonical.md"
            path.write_text(cls.HEADER + body + "\n", encoding="utf-8")
            return parse_csm_with_report(path)

    @classmethod
    def _nodes(cls, ssir: dict):
        return CSMToSSIRTests._nodes(ssir["structuralRoot"])

    def _term_node(self, ssir: dict, number: str) -> dict:
        node = next((n for n in self._nodes(ssir) if n.get("number") == number), None)
        self.assertIsNotNone(node, number)
        return node

    def test_bare_term_section_with_latin_initial_term_keeps_its_pair(self) -> None:
        # 裸条目编号（3.13）+ 术语行段落，术语本体带拉丁缩写。
        ssir, _ = self._parse(
            "## 3 术语和定义\n\n"
            "### 3.13\n\n"
            "SI词头\u3000SI prefix\n\n"
            "与SI单位名称或符号结合，用以形成该单位十进倍数单位或分数单位的词头。"
        )
        node = self._term_node(ssir, "3.13")
        self.assertEqual(node.get("term"), "SI词头")
        self.assertEqual(node.get("englishTerm"), "SI prefix")
        # 术语行仍被标为条目定义（渲染端据此版式化）。
        semantics = [ce.get("semanticTypes") for ce in node.get("contentElements", [])]
        self.assertIn(["termDefinition"], semantics)

    def test_bare_term_section_with_comma_in_english_term_keeps_its_pair(self) -> None:
        # 英文对应词含逗号（"… Units, SI"）。旧判据的英文类不含逗号，整条被漏。
        ssir, _ = self._parse(
            "## 3 术语和定义\n\n"
            "### 3.8\n\n"
            "国际单位制\u3000International System of Units, SI\n\n"
            "由国际计量大会（CGPM）批准采用的基于国际量制的单位制。"
        )
        node = self._term_node(ssir, "3.8")
        self.assertEqual(node.get("term"), "国际单位制")
        self.assertEqual(node.get("englishTerm"), "International System of Units, SI")

    def test_merged_heading_shape_keeps_the_same_pair(self) -> None:
        # 标题形态（## 3.8 + ## 术语行标题）：与裸编号形态必须给出同一对字段。
        ssir, _ = self._parse(
            "## 3 术语和定义\n\n"
            "## 3.13\n\n"
            "## SI词头 SI prefix\n\n"
            "与SI单位名称或符号结合的词头。"
        )
        node = self._term_node(ssir, "3.13")
        self.assertEqual(node.get("term"), "SI词头")
        self.assertEqual(node.get("englishTerm"), "SI prefix")

    def test_latin_only_line_in_terms_chapter_is_not_a_term(self) -> None:
        # 守卫：术语本体须含至少一个汉字——英文标题的换行（GB_T_1.1-2020 前置部分
        # "structure and drafting of ISO and IEC documents,NEQ)"）不是术语行。
        ssir, _ = self._parse(
            "## 3 术语和定义\n\n"
            "### 3.1\n\n"
            "structure and drafting of ISO and IEC documents,NEQ)\n\n"
            "本文件规定了用语。"
        )
        node = self._term_node(ssir, "3.1")
        self.assertIsNone(node.get("term"))
        self.assertIsNone(node.get("englishTerm"))

    def test_definition_line_with_latin_tail_is_not_a_term(self) -> None:
        # 守卫：英文对应词段不得含汉字——正文变量行（"普朗克常量 h为 …"）不是术语行。
        ssir, _ = self._parse(
            "## 3 术语和定义\n\n"
            "### 3.1\n\n"
            "普朗克常量 h为 6.62607015×10−34 J s；\n\n"
            "本文件规定了用语。"
        )
        node = self._term_node(ssir, "3.1")
        self.assertIsNone(node.get("term"))

    def test_term_gap_normalisation_accepts_latin_initial_term(self) -> None:
        # CSM-OCR-003 间隙归一：判据放宽后「SI词头 SI prefix」此类半角间隔也被归一为
        # U+3000；纯汉字术语的无间隔形态（OCR 丢间隔）沿用旧判据，不得把英文词尾吞进术语。
        from leleby_ssir.parser import restore_term_entry_gap

        self.assertEqual(restore_term_entry_gap("SI词头 SI prefix"), "SI词头\u3000SI prefix")
        self.assertEqual(restore_term_entry_gap("国际单位制 International System of Units, SI"),
                         "国际单位制\u3000International System of Units, SI")
        self.assertEqual(restore_term_entry_gap("标准化文件standardizing document"),
                         "标准化文件\u3000standardizing document")
        # 负例：整行纯拉丁（英文标题换行）原样返回。
        self.assertEqual(restore_term_entry_gap("structure and drafting of ISO and IEC documents,NEQ)"),
                         "structure and drafting of ISO and IEC documents,NEQ)")


class ClauseHeadingDemoteTests(unittest.TestCase):
    """2026-09-04 GB_T_1.1-2020：句子体条文被误升标题（CSM-OCR-009）。"""

    @staticmethod
    def _read(body: str):
        csm = (
            "---\n"
            'csm-version: "1.0"\n'
            "document-type: standard\n"
            "document-identifier: ssir:TEST-CLAUSE\n"
            'title: "测试"\n'
            "---\n\n"
            f"# 测试\n\n{body}\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t.canonical.md"
            path.write_text(csm, encoding="utf-8")
            doc = CSMParser().read(path)
        return doc

    def test_sentence_bodied_clause_heading_is_demoted_to_paragraph(self) -> None:
        # 回归（2026-09-04，GB_T_1.1-2020 附录 B）：MinerU 把无标题条文
        # 「B.2.2 这里描述的标记体系适用于下列各类文件。」误升为 ## 标题
        # （同层 B.2.1/B.2.3 均为裸正文段），导致附录 B.2 出现伪结构节点与
        # 目次跳号。句末标点收尾的编号标题不是标题 → 降级为正文段落。
        doc = self._read(
            "## 附录 B（规范性） 标准化项目标记\n\n"
            "## B.1 概述\n\n"
            "标准化项目既指有形的项目，也指无形的项目。\n\n"
            "## B.2 适用性\n\n"
            "B.2.1每个标准化项目都有多个特性，这些特性可以是单一的或者是多个的。\n\n"
            "## B.2.2 这里描述的标记体系适用于下列各类文件。\n\n"
            "对于某特性提供一种以上选择的文件。\n\n"
            "## B.2.3 标记体系\n\n"
            "B.2.3标记体系适用于各种类型的信息交流。\n"
        )
        paragraphs = [b.text for b in doc.blocks if b.kind == "paragraph"]
        headings = [b.text for b in doc.blocks if b.kind == "heading"]
        self.assertIn("B.2.2 这里描述的标记体系适用于下列各类文件。", paragraphs)
        self.assertNotIn("B.2.2 这里描述的标记体系适用于下列各类文件。", headings)
        # 真正的标题（不以句号收尾）保持不动。
        self.assertIn("B.1 概述", headings)
        self.assertIn("B.2 适用性", headings)
        self.assertIn("B.2.3 标记体系", headings)
        repair = [i for i in doc.issues if i.code == "CSM-OCR-009"]
        self.assertEqual(len(repair), 1)
        self.assertTrue(repair[0].repaired)

    def test_non_numbered_sentence_heading_is_not_demoted(self) -> None:
        # 无编号的句子式标题（如“前言”等要素的散文引言被人工写成 ##）不属于
        # 条文误升，009 不处理（只处理编号开头形态）。
        doc = self._read(
            "## 引言\n\n"
            "## 一般说明。\n\n"
            "本文件提供了编写标准化文件的结构和起草规则。\n"
        )
        headings = [b.text for b in doc.blocks if b.kind == "heading"]
        self.assertIn("一般说明。", headings)
        self.assertFalse([i for i in doc.issues if i.code == "CSM-OCR-009"])

class TableHeaderRowsAndMergeRowsTests(unittest.TestCase):
    """表头行数（GEN-114）与合并指令的行基准：merge 的 row 是**绝对** 0-based 行号。

    旧 builder 把 merge 的 row 当成「相对数据行」（data_row = header_rows + row − 1），
    在 header-rows=1 时与绝对行号恰好重合，所以一直没暴露；表头一旦是多行（GB/T 表
    常见 2~4 行表头），同一份合并指令就会整体下移 1~3 行——表头区的「尺寸代号」跨行格
    会跑到数据行上，表头第 2 行也不再被重复。
    """

    def test_two_row_header_and_absolute_merge_rows(self) -> None:
        csm = (
            "---\n"
            'csm-version: "1.0"\n'
            "document-type: standard\n"
            'document-identifier: "GB/T 30819—2024"\n'
            'standard-number: "GB/T 30819—2024"\n'
            'title: "结构尺寸"\n'
            "language: zh-CN\n"
            "source: {mode: mineru, provenance: none}\n"
            "extensions: {}\n"
            "---\n\n"
            "# 结构尺寸\n\n"
            "## 4.1.8　结构尺寸\n\n"
            '<!-- ssir:table id="t6" header-rows="2" caption-number="6" unit="毫米" -->\n'
            "**表6 CS-Ⅰ系列减速器结构尺寸表**\n"
            "| 尺寸代号 | 规格代号 |  |  |\n"
            "| --- | --- | --- | --- |\n"
            "|  | 8 | 11 | 14 |\n"
            "| $Φd_{1}$ | 3.0 | 5.0 | 6.0 |\n"
            '<!-- ssir:table-merge table="t6" row="0" column="1" rowspan="2" colspan="1" -->\n'
            '<!-- ssir:table-merge table="t6" row="0" column="2" rowspan="1" colspan="3" -->\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t.canonical.md"
            path.write_text(csm, encoding="utf-8")
            ssir, _ = parse_csm_with_report(path)
        table = ssir["tables"][0]
        self.assertEqual(table["unit"], "毫米")
        rows = sorted(table["rows"], key=lambda row: row["rowIndex"])
        # 两行表头：第 0、1 行都是表头，数据从第 2 行起
        self.assertEqual([row["isHeader"] for row in rows], [True, True, False])
        header_cells = sorted(rows[0]["cells"], key=lambda cell: cell["colIndex"])
        # row="0" 的两条合并指令落回第 0 行（不是被下移一行的第 1 行）
        self.assertEqual(header_cells[0]["rowspan"], 2)
        self.assertEqual(header_cells[0]["text"], "尺寸代号")
        self.assertEqual(header_cells[1]["colspan"], 3)
        self.assertEqual(header_cells[1]["text"], "规格代号")
        # 数据行没有被表头合并污染
        data_cells = sorted(rows[2]["cells"], key=lambda cell: cell["colIndex"])
        self.assertEqual([cell["rowspan"] for cell in data_cells], [1, 1, 1, 1])
        self.assertEqual([cell["colspan"] for cell in data_cells], [1, 1, 1, 1])
        self.assertEqual(data_cells[0]["text"], "$Φd_{1}$")

    def test_merge_on_the_first_data_row_uses_the_absolute_row(self) -> None:
        # 反例的姊妹形态：header-rows=2 时数据行的 row 必须是 2（表格第 3 行），
        # 旧口径把它理解成第 1 行（表头第 2 行）——表头会被数据行的跨列格顶掉。
        csm = (
            "---\n"
            'csm-version: "1.0"\n'
            "document-type: standard\n"
            'document-identifier: "GB/T 10000—2024"\n'
            'standard-number: "GB/T 10000—2024"\n'
            'title: "示例"\n'
            "language: zh-CN\n"
            "source: {mode: mineru, provenance: none}\n"
            "extensions: {}\n"
            "---\n\n"
            "# 示例\n\n"
            "## 1 范围\n\n"
            '<!-- ssir:table id="t1" header-rows="2" caption-number="1" -->\n'
            "**表1 示例表**\n"
            "| 甲 | 乙 |  |\n"
            "| --- | --- | --- |\n"
            "|  | 乙甲 | 乙乙 |\n"
            "| 注 | 说明文字 |  |\n"
            '<!-- ssir:table-merge table="t1" row="0" column="1" rowspan="2" colspan="1" -->\n'
            '<!-- ssir:table-merge table="t1" row="2" column="1" rowspan="1" colspan="2" -->\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t.canonical.md"
            path.write_text(csm, encoding="utf-8")
            ssir, _ = parse_csm_with_report(path)
        rows = sorted(ssir["tables"][0]["rows"], key=lambda row: row["rowIndex"])
        self.assertEqual(rows[1]["isHeader"], True)
        data_cells = sorted(rows[2]["cells"], key=lambda cell: cell["colIndex"])
        self.assertEqual(data_cells[0]["colspan"], 2)
        self.assertEqual(data_cells[0]["text"], "注")
        self.assertEqual(data_cells[1]["text"], "说明文字")

    def test_stale_merge_rows_from_edited_table_are_realigned(self) -> None:
        # GEN-147：canonical 的表格行被编辑过（去掉跨页重复表头行等）后，抽取端写下的
        # `ssir:table-merge` 绝对行号即失效——锚点落到空白续行上，带内的真实文字会被并合掉
        # （GB_T_20001.5-2017 表1 实测：`规范性一般要素`/`规范性技术要素` 在渲染产物里整体
        # 消失、后续行的第一列错位）。修正是确定性的：带上移到有文字的组标签行、下界收窄到
        # 下一个有文字的行之前（绝不把别的组标签并进来）。
        csm = (
            "---\n"
            'csm-version: "1.0"\n'
            "document-type: standard\n"
            'document-identifier: "GB/T 10001—2024"\n'
            'standard-number: "GB/T 10001—2024"\n'
            'title: "合并行号陈旧"\n'
            "language: zh-CN\n"
            "source: {mode: mineru, provenance: none}\n"
            "extensions: {}\n"
            "---\n\n"
            "# 合并行号陈旧\n\n"
            "## 5 结构\n\n"
            '<!-- ssir:table id="t1" header-rows="1" caption-number="1" -->\n'
            "**表1 要素的典型编排**\n"
            "| 要素类型 | 要素 | 表述形式 |\n"
            "| --- | --- | --- |\n"
            "| 甲组 | 一 | 文字 |\n"
            "|  | 二 | 文字 |\n"
            "| 乙组 | 三 | 文字 |\n"
            "|  | 四 | 文字 |\n"
            "|  | 五 | 文字 |\n"
            "| 注：表中顺序即位置。 |  |  |\n"
            '<!-- ssir:table-merge table="t1" row="4" column="1" rowspan="3" colspan="1" -->\n'
            '<!-- ssir:table-merge table="t1" row="6" column="1" rowspan="1" colspan="3" -->\n'
            '<!-- ssir:table-merge table="t1" row="7" column="1" rowspan="1" colspan="3" -->\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t.canonical.md"
            path.write_text(csm, encoding="utf-8")
            ssir, _ = parse_csm_with_report(path)
        table = ssir["tables"][0]
        rows = sorted(table["rows"], key=lambda row: row["rowIndex"])
        # 组标签行 3 承接合并（directive 说的第 4 行是空白续行），文字留下、续行不并进来
        self.assertEqual(rows[3]["cells"][0]["text"], "乙组")
        self.assertEqual(rows[3]["cells"][0]["rowspan"], 3)
        self.assertEqual([rows[i]["cells"][0]["rowspan"] for i in (4, 5)], [1, 1])
        self.assertEqual(rows[6]["cells"][0]["colspan"], 3)
        # 越界指令（row=7，表只有 0..6 行）如实降级为 partiallyPreserved
        self.assertEqual(table["preservationStatus"], "partiallyPreserved")
        comments = ssir["qualityAssessments"][0].get("comments", "")
        self.assertIn("Realigned table merge directives", comments)
        self.assertIn("rowspan realigned to row 3", comments)
        self.assertIn("is out of range", comments)

    def test_consistent_merge_rows_are_left_untouched(self) -> None:
        # 反例（干净夹具命中为 0）：行号与表格一致时不重锚、不登记 —— 同一张表，指令写对。
        csm = (
            "---\n"
            'csm-version: "1.0"\n'
            "document-type: standard\n"
            'document-identifier: "GB/T 10002—2024"\n'
            'standard-number: "GB/T 10002—2024"\n'
            'title: "合并行号一致"\n'
            "language: zh-CN\n"
            "source: {mode: mineru, provenance: none}\n"
            "extensions: {}\n"
            "---\n\n"
            "# 合并行号一致\n\n"
            "## 5 结构\n\n"
            '<!-- ssir:table id="t1" header-rows="1" caption-number="1" -->\n'
            "**表1 要素的典型编排**\n"
            "| 要素类型 | 要素 | 表述形式 |\n"
            "| --- | --- | --- |\n"
            "| 甲组 | 一 | 文字 |\n"
            "|  | 二 | 文字 |\n"
            "| 乙组 | 三 | 文字 |\n"
            "|  | 四 | 文字 |\n"
            "|  | 五 | 文字 |\n"
            "| 注：表中顺序即位置。 |  |  |\n"
            '<!-- ssir:table-merge table="t1" row="3" column="1" rowspan="3" colspan="1" -->\n'
            '<!-- ssir:table-merge table="t1" row="6" column="1" rowspan="1" colspan="3" -->\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t.canonical.md"
            path.write_text(csm, encoding="utf-8")
            ssir, _ = parse_csm_with_report(path)
        rows = sorted(ssir["tables"][0]["rows"], key=lambda row: row["rowIndex"])
        self.assertEqual(rows[3]["cells"][0]["rowspan"], 3)
        self.assertEqual(rows[6]["cells"][0]["colspan"], 3)
        self.assertEqual(ssir["tables"][0]["preservationStatus"], "preserved")
        comments = ssir["qualityAssessments"][0].get("comments", "")
        self.assertNotIn("Realigned table merge directives", comments)


class GluedHeadingNumberTests(unittest.TestCase):
    """GEN-117：标题编号与标题文字之间缺空格时，解析结果必须与有空格时一致。

    现象（2026-09-19，GB_T_20001.10-2014 回环失败 + 用户手工核对）：canonical 里存在
    `### 6.4分类、标记和编码`、`## 22电磁兼容性` 这类**编号紧贴标题文字**的写法（人工 curation /
    抽取遗留，缺一个空格），而渲染端统一写 `6.4 分类、标记和编码`。旧判据要求「标题编号后必须是
    空白」才算已确认编号 → 缺空格的标题不算已确认，其下裸条款段（`6.4.3 产品分类的基本要求如下：`）
    的级联提升随之失效 → 同一份文件在回环两侧解析出不同的条款树，报告出
    C7-clauseIdentifiers / C4-numericalValues 关键信息丢失。判据改为与 builder 的标题拆分一致：
    编号后是空白，或直接跟标题文字（汉字/字母/括号）——**canonical 不需要改写**。
    """

    HEADER = (
        "---\n"
        "csm-version: 1.0\n"
        "document-type: standard\n"
        "document-identifier: GB_T_20001.10-2014\n"
        "standard-number: GB/T 20001.10—2014\n"
        "title: 标准编写规则 第10部分：产品标准\n"
        "language: zh-CN\n"
        "---\n\n"
        "# 标准编写规则 第10部分：产品标准\n\n"
    )
    BODY = (
        "### {chapter}\n\n"
        "6.4.1 产品标准中分类、标记和编码为可选要素。\n\n"
        "6.4.2 根据具体情况，该要素可并入技术要求（见6.5）。\n\n"
        "6.4.3 产品分类的基本要求如下：\n\n"
        "— 划分的类别应满足使用的需要；\n\n"
        "## {chapter22}\n\n"
        "22.1 应进行电磁兼容性测试\n"
    )

    @classmethod
    def _write(cls, directory: str, name: str, chapter: str, chapter22: str) -> Path:
        path = Path(directory) / name
        path.write_text(
            cls.HEADER + cls.BODY.format(chapter=chapter, chapter22=chapter22), encoding="utf-8"
        )
        return path

    @staticmethod
    def _numbers(ssir: dict) -> list[str]:
        return [str(node["number"]) for node in CSMToSSIRTests._nodes(ssir["structuralRoot"]) if node.get("number")]

    def test_glued_heading_confirms_the_same_clause_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            spaced = parse_csm(self._write(directory, "spaced.canonical.md", "6.4 分类、标记和编码", "22 电磁兼容性"))
            glued = parse_csm(self._write(directory, "glued.canonical.md", "6.4分类、标记和编码", "22电磁兼容性"))
        self.assertEqual(self._numbers(spaced), self._numbers(glued))
        # 缺空格的标题同样要确认编号 → 其下裸条款段被提升为子条款
        self.assertIn("6.4.3", self._numbers(glued))
        self.assertIn("22.1", self._numbers(glued))

    def test_glued_heading_parses_into_the_same_structure(self) -> None:
        # 粘连写法（`6.4分类、标记和编码`）必须与规范写法解析出**同一结构**，
        # 且投影里恢复规范形态（编号与标题间一个空格）。
        views = {}
        with tempfile.TemporaryDirectory() as directory:
            for name, chapter, chapter22 in (
                ("spaced.canonical.md", "6.4 分类、标记和编码", "22 电磁兼容性"),
                ("glued.canonical.md", "6.4分类、标记和编码", "22电磁兼容性"),
            ):
                with self.subTest(name=name):
                    path = self._write(directory, name, chapter, chapter22)
                    ssir = parse_csm(path)
                    views[name] = semantic_view(ssir)
                    rendered = render_csm(ssir)
                    self.assertIn("## 6.4 分类、标记和编码", rendered)
        self.assertEqual(views["spaced.canonical.md"], views["glued.canonical.md"])


if __name__ == "__main__":
    unittest.main()