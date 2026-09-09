from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from leleby_ssir.exporters import json_bytes, turtle_text
from leleby_ssir.parser import Block, CSMError, CSMParser, _absorb_table_note_spill
from leleby_ssir.roundtrip import compare_ssir
from leleby_ssir.service import normalize_csm, parse_csm, parse_csm_with_report, round_trip_csm


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

    def test_markdown_round_trip_preserves_all_csm_examples(self) -> None:
        paths = [
            *sorted((ROOT / "corpus/golden/csm").glob("*.canonical.md")),
            ROOT / "corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md",
        ]
        with tempfile.TemporaryDirectory() as directory:
            for path in paths:
                with self.subTest(path=path.name):
                    render_md = Path(directory) / f"{path.stem}.render.md"
                    ssir, verify, report = round_trip_csm(path, render_md)
                    self.assertTrue(render_md.exists())
                    self.assertTrue(report.passed, report.to_dict())
                    self.assertEqual(ssir["metadata"]["common"], verify["metadata"]["common"])

    def test_comparator_reports_critical_normative_and_table_changes(self) -> None:
        ssir = parse_csm(ROOT / "corpus/golden/csm/Q_HKT_16016-2026.canonical.md")
        verify = deepcopy(ssir)
        verify["tables"][0]["rows"][1]["cells"][0]["text"] = "999"
        content = next(
            element
            for node in self._nodes(verify["structuralRoot"])
            for element in node.get("contentElements", [])
            if element.get("textContent") and "应符合" in element["textContent"]
        )
        content["textContent"] = content["textContent"].replace("应符合", "宜符合", 1)
        report = compare_ssir(ssir, verify)
        self.assertFalse(report.passed)
        self.assertIn("C1-normativeWording", report.critical_information_loss)
        self.assertIn("C8-tableCellContent", report.critical_information_loss)

    def test_template_formula_and_turtle_export(self) -> None:
        ssir = parse_csm(ROOT / "corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md")
        self.assertEqual(len(ssir["formulas"]), 1)
        self.assertEqual(ssir["formulas"][0]["number"], "式（1）")
        turtle = turtle_text(ssir)
        self.assertIn("ssir:jsonSha256", turtle)
        self.assertIn("https://leleby.io/resource/ssir%3AQ-EXAMPLE-001-2026", turtle)
        self.assertIn("a ssir:Table", turtle)
        self.assertIn("a ssir:Figure", turtle)
        self.assertIn("a ssir:Formula", turtle)

    def test_round_trip_preserves_annex_kind_and_identifier(self) -> None:
        path = ROOT / "corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md"
        with tempfile.TemporaryDirectory() as directory:
            ssir, verify, report = round_trip_csm(path, Path(directory) / "render.md")
        annex1 = next(node for node in self._nodes(ssir["structuralRoot"]) if node["nodeType"] == "annex")
        annex2 = next(node for node in self._nodes(verify["structuralRoot"]) if node["nodeType"] == "annex")
        self.assertTrue(report.passed, report.to_dict())
        self.assertEqual((annex1["number"], annex1["title"]), (annex2["number"], annex2["title"]))

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
        for title in ("参考文献", "索引", "B", "Z"):
            self.assertFalse(nodes[title].get("exampleContent"), f"{title} must not be example content")
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
        self.assertTrue(compare_ssir(ssir0, ssir0_reparsed).passed)

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
        self.assertTrue(compare_ssir(ssir, ssir2).passed)

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
        self.assertTrue(compare_ssir(ssir, ssir_reparsed).passed)

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
        self.assertTrue(compare_ssir(ssir, ssir_reparsed).passed)

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
        self.assertIn("d） 额定频率(Hz)；", rendered)
        self.assertIn("e） 额定电压(V)。", rendered)

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

if __name__ == "__main__":
    unittest.main()