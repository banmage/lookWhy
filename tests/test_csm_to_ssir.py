from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from leleby_ssir.exporters import json_bytes, turtle_text
from leleby_ssir.parser import CSMError, CSMParser
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


if __name__ == "__main__":
    unittest.main()
