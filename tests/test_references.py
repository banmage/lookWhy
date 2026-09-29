"""规范性引用抽取回归（TDRS「标准中规范性引用文件的管理」§二/§四）。

判据来源：GB/T 1.1-2020 8.6.3（清单）、9.5.3（内容编号）、9.5.4.1.1（注日期引用具体
内容）、9.5.4.2.1 a)-d)（规范性引用）、9.5.4.2.2（资料性引用）、9.5.4.3（标明来源）。
每个判据都配正例 + 反例，避免把「提及」当「引用」或反之。
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from leleby_ssir import references as R
from leleby_ssir.service import parse_csm
from leleby_ssir.validation import validate_ssir

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = """---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/REFTEST 001—2026"
standard-number: "Q/REFTEST 001—2026"
title: "引用抽取回归 技术规范"
language: zh-CN
source:
  mode: user-markdown
  original-file-name: "Q_REFTEST_001-2026.md"
  provenance: none
---

# 引用抽取回归 技术规范

## 前言

本文件按照 GB/T 1.1—2020《标准化工作导则 第1部分：标准化文件的结构和起草规则》的规定起草。

## 1 范围

本文件适用于 GB/T 9999—2011 规定的场合。

## 2 规范性引用文件

下列文件中的内容通过文中的规范性引用而构成本文件必不可少的条款。

- GB/T 1.1—2020 标准化工作导则 第1部分：标准化文件的结构和起草规则
- GB/T 321 优先数和优先数系
- GB/T 3101(所有部分） 量和单位

## 3 术语和定义

GB/T 20000.1界定的以及下列术语和定义适用于本文件。

### 3.1 质量 mass

物质量，SI 基本量之一。

[来源：GB/T 20000.1—2014,5.2]

## 4 技术要求

### 4.1 一般要求

产品应符合 GB/T 1.1—2020 中 9.5.4 的规定。

试验按 GB/T 8888—2019 第5章确立的程序进行。

### 4.2 引用点

基本参数应符合表1的规定；试验装置见图1；计算按式(1)。

另见 GB/T 7777 给出的说明。

> 注：关于 GB/T 6666 的说明见其第 3 章。

<!-- ssir:table id="tbl-001" header-rows="1" -->
**表1 基本参数**

| 编号 | 名称 |
|------|------|
| 1 | 质量 |

<!-- ssir:figure id="fig-001" -->
> [图1 装置示意（图片占位）]

<!-- ssir:formula id="fm-001" -->
$$
P = U I
$$
式（1）
"""


def _parse(body: str = FIXTURE) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "t.canonical.md"
        path.write_text(body, encoding="utf-8")
        return parse_csm(path)


def _by_id(document: dict) -> dict[str, dict]:
    return {str(item["resolvedDocumentId"]): item for item in document.get("references") or []}


class ReferenceExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = _parse()
        self.items = self.document["references"]
        self.by_id = _by_id(self.document)

    # --- 产出与 schema -------------------------------------------------

    def test_references_present_and_schema_valid(self) -> None:
        self.assertTrue(self.items, "未产出任何规范性引用")
        validate_ssir(self.document)  # schema（含 Reference/TextSpan）必须通过

    def test_required_reference_fields(self) -> None:
        for item in self.items:
            self.assertTrue(item["id"].startswith(f"{self.document['id']}#Ref-"))
            self.assertTrue(item["sourceNodeId"].startswith(f"{self.document['id']}#"))
            self.assertIn(item["referenceType"], {"normative", "informative", "mandatory", "conditional"})
            self.assertIn(item["resolutionStatus"], {"resolved", "partiallyResolved", "unresolved"})
            self.assertTrue(item["rawTarget"])

    # --- 清单（8.6.3） --------------------------------------------------

    def test_chapter_two_list_entries_are_normative_undated(self) -> None:
        entry = self.by_id["GB_T_321"]
        self.assertEqual(entry["referenceType"], "normative")
        self.assertNotIn("resolvedVersion", entry)
        self.assertEqual(R.reference_type_of(entry), "undated")

    def test_dated_entry_keeps_version(self) -> None:
        entry = self.by_id["GB_T_1.1-2020"]
        self.assertEqual(entry["resolvedVersion"], "2020")
        self.assertEqual(R.reference_type_of(entry), "dated")

    def test_all_parts_entry_with_mixed_width_parentheses(self) -> None:
        # canonical 实测存在半/全角括号混用（“GB/T 3101(所有部分）”）：判据按字符类容忍，
        # 不做个例数据手术（AGENTS.md §0.1）。
        entry = self.by_id["GB_T_3101"]
        self.assertEqual(R.reference_type_of(entry), "all_parts")

    def test_entry_titles_come_from_the_list_entry(self) -> None:
        summary = R.summarise(self.document)
        entry = next(e for e in summary["references"] if e["standard_id"] == "GB_T_321")
        self.assertEqual(entry["title"], "优先数和优先数系")
        self.assertEqual(entry["nature"], "normative")
        self.assertEqual(entry["source_clauses"][0]["clause"], "2")
        self.assertTrue(entry["source_clauses"][0]["md_line"])

    # --- 全文扫描与合并（§四 第 2/3 点） --------------------------------

    def test_body_citation_adds_occurrence_to_list_entry(self) -> None:
        summary = R.summarise(self.document)
        entry = next(e for e in summary["references"] if e["standard_id"] == "GB_T_1.1-2020")
        clauses = {clause["clause"] for clause in entry["source_clauses"]}
        self.assertIn("2", clauses)
        self.assertIn("4.1", clauses)

    def test_body_only_normative_citation_is_listed(self) -> None:
        entry = self.by_id["GB_T_8888-2019"]
        self.assertEqual(entry["referenceType"], "normative")
        self.assertEqual(entry["resolvedClause"], "第5章")

    # --- 规范性/资料性（9.5.4.2） ---------------------------------------

    def test_scope_mention_is_informative(self) -> None:
        # 9.5.4.2.2：范围章里的提及不属规范性引用。
        self.assertEqual(self.by_id["GB_T_9999-2011"]["referenceType"], "informative")

    def test_terms_chapter_lead_is_normative(self) -> None:
        # 9.5.4.2.1 d)：术语和定义中由引导语提及 → 规范性引用。
        self.assertEqual(self.by_id["GB_T_20000.1"]["referenceType"], "normative")

    def test_source_note_is_informative(self) -> None:
        # 9.5.4.3 + 8.13：来源标注属资料性提及（进参考文献，不进清单）。
        self.assertEqual(self.by_id["GB_T_20000.1-2014"]["referenceType"], "informative")

    def test_see_lead_is_informative(self) -> None:
        # 9.5.4.2.2 示例：「……的信息见 GB/T xxxxx」为资料性引用。
        self.assertEqual(self.by_id["GB_T_7777"]["referenceType"], "informative")

    def test_note_citation_is_informative(self) -> None:
        self.assertEqual(self.by_id["GB_T_6666"]["referenceType"], "informative")

    def test_foreword_citation_is_informative(self) -> None:
        self.assertEqual(self.by_id["GB_T_1.1-2020"]["referenceType"], "normative")  # 清单+正文
        summary = R.summarise(self.document)
        entry = next(e for e in summary["references"] if e["standard_id"] == "GB_T_1.1-2020")
        foreword = [clause for clause in entry["source_clauses"] if clause["clause"] == "前言"]
        self.assertTrue(foreword, "前言里的引用应被记录（出现条款）")
        self.assertEqual({clause["nature"] for clause in foreword}, {"informative"})

    # --- 被引条款/内容编号（9.5.4.1.1、9.5.3） --------------------------

    def test_cited_clause_forms(self) -> None:
        self.assertEqual(self.by_id["GB_T_1.1-2020"]["resolvedClause"], "9.5.4")  # 「中 9.5.4」
        self.assertEqual(self.by_id["GB_T_8888-2019"]["resolvedClause"], "第5章")  # 「第5章」
        self.assertEqual(self.by_id["GB_T_20000.1-2014"]["resolvedClause"], "5.2")  # 「[来源：…,5.2]」

    def test_revision_year_is_not_a_cited_clause(self) -> None:
        # 「GB 1.1—1981,1987」里的 1987 是修订年，不是被引条款。
        self.assertIsNone(R._cited_clause_after(",1987"))

    # --- 本文内部引用点（引用体系：条款/图/表/公式） ---------------------

    def test_internal_targets_resolve_to_registry(self) -> None:
        summary = R.summarise(self.document)
        internal = summary["internalReferences"]
        self.assertEqual(internal["internalTable"][0]["number"], "1")
        self.assertTrue(internal["internalTable"][0]["target_id"].endswith("#Table_1"))
        self.assertTrue(internal["internalFigure"][0]["resolved"])
        self.assertEqual(internal["internalFormula"][0]["number"], "1")
        self.assertEqual(summary["unresolvedInternalCount"], 0)

    def test_unresolved_internal_target_is_reported(self) -> None:
        document = _parse(FIXTURE.replace("计算按式(1)。", "计算按式(1)，详见图9。"))
        summary = R.summarise(document)
        unresolved = [item for item in summary["unresolvedInternal"] if item["number"] == "9"]
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(summary["unresolvedInternalCount"], 1)

    # --- textSpan 精确定位 ---------------------------------------------

    def test_text_spans_point_at_the_exact_citation(self) -> None:
        canonical = self.document["canonicalText"]["text"]
        for item in self.items:
            span = item["textSpan"]
            self.assertEqual(span["canonicalTextId"], f"{self.document['id']}#Canonical")
            self.assertEqual(
                canonical[span["startChar"]:span["endChar"]],
                span["text"],
                f"{item['id']} 的字符区间与文本不一致",
            )

    def test_canonical_offsets_match_fragments(self) -> None:
        owners = ["a#One", "a#Two", "", "a#Three"]
        parts = ["第一段", "", "标题", "第三段"]
        text = "\n".join(part for part in parts if part)
        offsets = R.canonical_offsets(owners, parts, text)
        for owner, (start, end) in offsets.items():
            self.assertEqual(text[start:end], dict(zip(owners, parts))[owner])

    def test_canonical_offsets_reject_mismatched_ledger(self) -> None:
        with self.assertRaises(ValueError):
            R.canonical_offsets(["a#One"], ["第一段"], "别的内容")

    # --- 幂等与投影安全 -------------------------------------------------

    def test_references_are_stable_across_reparse(self) -> None:
        again = _parse()
        self.assertEqual(json.dumps(again["references"], ensure_ascii=False), json.dumps(self.items, ensure_ascii=False))

    def test_markdown_projection_ignores_references(self) -> None:
        from leleby_ssir.csm_renderer import render_csm

        text = render_csm(self.document)
        self.assertNotIn("Ref-", text)
        self.assertNotIn("references", text)

    def test_unnumbered_list_head_keeps_chapter_two_region(self) -> None:
        """清单首条被抽取升成无编号标题时，其余条目仍属第 2 章清单（GB_T_39567-2020 实测形态）。"""
        document = _parse(
            """---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/SPLIT 001—2026"
standard-number: "Q/SPLIT 001—2026"
title: "清单首条升标题 技术规范"
language: zh-CN
---

# 清单首条升标题 技术规范

## 1 范围

本文件规定了清单首条被抽取升成标题时的引用归属。

## 2 规范性引用文件

下列文件对于本文件的应用是必不可少的。

## GB/T 755 旋转电机 定额和性能

GB/T 2423.1—2008 电工电子产品环境试验 第2部分：试验方法 试验A：低温

GB/T 2423.2—2008 电工电子产品环境试验 第2部分：试验方法 试验B：高温

## 3 术语和定义

### 3.1 伺服电动机 servo motor

用于伺服系统的电动机。
"""
        )
        summary = R.summarise(document)
        entries = {entry["standard_number"]: entry for entry in summary["references"]}
        self.assertEqual(
            set(entries),
            {"GB/T 755", "GB/T 2423.1—2008", "GB/T 2423.2—2008"},
        )
        for entry in entries.values():
            self.assertEqual(entry["nature"], "normative")
            self.assertIn("2", [clause["clause"] for clause in entry["source_clauses"]])

    def test_document_without_citations_has_no_references_key(self) -> None:
        document = _parse(
            """---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/NOREF 001—2026"
standard-number: "Q/NOREF 001—2026"
title: "无引用 技术规范"
language: zh-CN
---

# 无引用 技术规范

## 1 范围

本文件规定了无引用文档的结构。

## 2 规范性引用文件

本文件没有规范性引用文件。
"""
        )
        self.assertNotIn("references", document)


class RealCorpusReferenceTests(unittest.TestCase):
    """真实语料：清单条目必须全部进入 SSIR.references，且定位精确。"""

    TEMPLATE = ROOT / "corpus/golden/SSIR_CANONICAL_MARKDOWN_TEMPLATE.md"

    def test_template_list_entries_and_internal_targets(self) -> None:
        document = parse_csm(self.TEMPLATE)
        by_id = _by_id(document)
        for expected in ("GB_T_1.1-2020", "GB_T_20001.10-2014", "GB_T_755-2025"):
            self.assertIn(expected, by_id, f"清单条目缺失：{expected}")
        summary = R.summarise(document)
        self.assertGreaterEqual(summary["internalCount"], 1)
        canonical = document["canonicalText"]["text"]
        for item in document["references"]:
            span = item["textSpan"]
            self.assertEqual(canonical[span["startChar"]:span["endChar"]], span["text"])

    def test_gb_t_1_1_list_is_complete(self) -> None:
        """GB/T 1.1-2020 第 2 章 14 条清单条目应全部抽取（含 ISO/IEC 国际文件）。"""
        canonical = ROOT / "out/mineru/GB_T_1.1-2020/02_canonical/GB_T_1.1-2020.canonical.md"
        if not canonical.exists():
            self.skipTest("缺少 GB_T_1.1-2020 canonical 产物")
        document = parse_csm(canonical)
        summary = R.summarise(document)
        chapter_two = {
            entry["standard_id"]
            for entry in summary["references"]
            if any(clause["clause"] == "2" for clause in entry["source_clauses"])
        }
        self.assertEqual(
            chapter_two,
            {
                "GB_T_321", "GB_T_3101", "GB_T_3102", "GB_T_7714", "GB_T_14559", "GB_T_15834",
                "GB_T_15835", "GB_T_20000.1", "GB_T_20000.2", "GB_T_20001", "GB_T_20002",
                "ISO_80000", "IEC_60027", "IEC_80000",
            },
        )
        canonical_text = document["canonicalText"]["text"]
        for item in document["references"]:
            span = item["textSpan"]
            self.assertEqual(canonical_text[span["startChar"]:span["endChar"]], span["text"])


class UncitedListEntryTests(unittest.TestCase):
    """清单条目未被正文引用（用户 2026-09-29 裁定；GBT-C06/reference-entry-not-cited）。"""

    FIXTURE = """---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/UNCITED 001—2026"
standard-number: "Q/UNCITED 001—2026"
title: "清单未引用 技术规范"
language: zh-CN
---

# 清单未引用 技术规范

## 前言

本文件按照 GB/T 1.1—2020《标准化工作导则 第1部分：标准化文件的结构和起草规则》的规定起草。

## 1 范围

本文件适用于电动机。

## 2 规范性引用文件

下列文件中的内容通过文中的规范性引用而构成本文件必不可少的条款。

- GB/T 1032—2022 三相异步电动机试验方法
- GB/T 191—2008 包装储运图示标志
- GB 14023—2011 车辆、船和由内燃机驱动的装置 无线电骚扰特性 限值和测量方法
- GB/T 4208-2017 外壳防护等级（IP 代码）
- GB/T 8128 单相串励电动机试验方法

## 4 技术要求

### 4.1 一般要求

电动机的试验方法应符合 GB/T 1032 的规定。

储运标志应符合 GB/T 191—2008 的规定。

电磁辐射应符合 GB/T 14023 的要求。

> 注：外壳防护试验按 GB/T 4208 的有关规定进行。
"""

    def test_uncited_entries_are_the_body_silent_ones(self):
        entries = {entry["standard_number"]: entry for entry in R.uncited_list_entries(_parse(self.FIXTURE))}
        # GB/T 8128 正文完全没有出现；GB 14023—2011 因清单与正文文件代号不同而报出（带线索）。
        # GB/T 4208-2017 只在注里出现 → 宽松判据算「正文出现过」，严格判据才算未引用。
        self.assertEqual(set(entries), {"GB/T 8128", "GB 14023—2011"})
        self.assertEqual(entries["GB/T 8128"]["similar_citations"], [])

    def test_same_sequence_number_different_code_is_reported_as_hint(self):
        """清单写 GB 14023、正文写 GB/T 14023：报出并附「同顺序号引用」线索，便于复核写法。"""
        entries = {entry["standard_number"]: entry for entry in R.uncited_list_entries(_parse(self.FIXTURE))}
        hint = entries["GB 14023—2011"]["similar_citations"]
        self.assertEqual([item["raw"] for item in hint], ["GB/T 14023"])
        self.assertEqual(hint[0]["clause"], "4.1")

    def test_dated_form_in_list_matches_undated_form_in_body(self):
        """清单写注日期、正文写不注日期（或版式变体）→ 同一标准，不算未引用。"""
        entries = {entry["standard_number"] for entry in R.uncited_list_entries(_parse(self.FIXTURE))}
        self.assertNotIn("GB/T 191—2008", entries)
        self.assertNotIn("GB/T 1032—2022", entries)

    def test_separator_variants_do_not_hide_a_body_citation(self):
        """抽取层把一字线认成「一」时（正文写「GB/T 1032一2022」）仍判为已引用。"""
        text = self.FIXTURE.replace("应符合 GB/T 1032 的规定", "应符合 GB/T 1032一2022 的规定")
        entries = {entry["standard_number"] for entry in R.uncited_list_entries(_parse(text))}
        self.assertNotIn("GB/T 1032—2022", entries)

    def test_strict_variant_requires_normative_citation(self):
        strict = {entry["standard_number"] for entry in R.uncited_list_entries(_parse(self.FIXTURE), require_normative=True)}
        self.assertIn("GB/T 4208-2017", strict)  # 只在注内（资料性引用）
        self.assertIn("GB/T 8128", strict)

    def test_foreword_mention_is_not_a_body_citation(self):
        """前言里提到的文件不算正文引用（前言只提到未列入清单的 GB/T 1.1—2020）。"""
        summary = R.summarise(_parse(self.FIXTURE))
        self.assertEqual(summary["uncitedListEntryCount"], len(summary["uncitedListEntries"]))
        self.assertIn("GB/T 8128", {entry["standard_number"] for entry in summary["uncitedListEntries"]})

    def test_compliance_reports_uncited_entry(self):
        """检查报告里逐条列为问题（GBT-C06 / reference-entry-not-cited）。"""
        from leleby_ssir.compliance import verify_compliance

        report = verify_compliance(_parse(self.FIXTURE), metadata=None)
        hits = [f for f in report.findings if f.check == "reference-entry-not-cited"]
        messages = " ".join(f.message for f in hits)
        self.assertEqual(len(hits), 2)
        self.assertIn("GB/T 8128", messages)
        self.assertIn("GB 14023—2011", messages)
        self.assertIn("正文有同顺序号但文件代号不同的引用：GB/T 14023", messages)
        for finding in hits:
            self.assertEqual(finding.rule_id, "GBT-C06")
            self.assertEqual(finding.priority, "should")
            self.assertEqual(finding.status, "warning")  # priority should → warning

    def test_compliance_silent_when_every_entry_is_cited(self):
        from leleby_ssir.compliance import verify_compliance

        text = (
            self.FIXTURE.replace("GB 14023—2011 车辆", "GB/T 14023—2011 车辆")
            .replace(
                "> 注：外壳防护试验按 GB/T 4208 的有关规定进行。",
                "电动机的外壳防护应符合 GB/T 4208-2017 的规定。",
            )
            .replace("\n- GB/T 8128 单相串励电动机试验方法\n", "")
        )
        report = verify_compliance(_parse(text), metadata=None)
        self.assertEqual([f for f in report.findings if f.check == "reference-entry-not-cited"], [])


class UnlistedCitationTests(unittest.TestCase):
    """正文规范性引用了、但清单未列出（用户 2026-09-29 裁定；GBT-C06/normative-citation-not-listed）。"""

    FIXTURE = """---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/UNLISTED 001—2026"
standard-number: "Q/UNLISTED 001—2026"
title: "未列引用回归 技术规范"
language: zh-CN
source:
  mode: user-markdown
  original-file-name: "Q_UNLISTED_001-2026.md"
  provenance: none
---

# 未列引用回归 技术规范

## 前言

本文件按照 GB/T 1.1—2020《标准化工作导则 第1部分：标准化文件的结构和起草规则》的规定起草。

## 1 范围

本文件适用于 GB/T 9999—2011 规定的场合。

## 2 规范性引用文件

下列文件中的内容通过文中的规范性引用而构成本文件必不可少的条款。

- GB/T 3102（所有部分） 量和单位
- GB 7552008 旋转电机 定额和性能
- GB/T 9001 列出的文件
- GB/T 20000.1 标准化工作指南 第1部分：标准化和相关活动的通用术语

## 3 术语和定义

GB/T 20000.1界定的以及下列术语和定义适用于本文件。

### 3.1 质量 mass

物质量，SI 基本量之一。

## 4 要求

### 4.1 防护等级

产品的防护等级应符合 GB/T 4001 的规定。

### 4.2 尺寸

尺寸的测量参见 GB/T 4002。

### 4.3 符号

图中用于表示角度量或线性量的字母符号应符合 GB/T 3102.1 的规定。

### 4.4 工作制

电动机的工作制应符合 GB 755—2008 的规定。

### 4.5 试验方法

示例：“甲醛含量按 GB/T 4003 描述的方法测定应不大于 20 mg/kg”。

### 4.6 包装

包装标志应符合 GB/T 9001 的规定。

"""

    def test_only_body_normative_citation_missing_from_list_is_reported(self):
        entries = {entry["base_id"] for entry in R.unlisted_citation_entries(_parse(self.FIXTURE))}
        # 4.1 规范性引用且清单未列 → 报出；其余各形态均不报（见后面的专项断言）。
        self.assertEqual(entries, {"GB_T_4001"})

    def test_informative_citation_is_not_reported(self):
        """资料性引用（参见/见）本就不应列入清单（9.5.4.2.2）。"""
        entries = {entry["base_id"] for entry in R.unlisted_citation_entries(_parse(self.FIXTURE))}
        self.assertNotIn("GB_T_4002", entries)

    def test_all_parts_list_entry_covers_specific_part(self):
        """清单写「GB/T 3102（所有部分）」、正文引用具体部分「GB/T 3102.1」→ 清单已覆盖。"""
        entries = {entry["base_id"] for entry in R.unlisted_citation_entries(_parse(self.FIXTURE))}
        self.assertNotIn("GB_T_3102.1", entries)

    def test_separator_and_fused_year_variants_are_the_same_file(self):
        """清单「GB 7552008」与正文「GB 755—2008」是同一文件（分隔符丢失/年份粘连）。"""
        entries = {entry["base_id"] for entry in R.unlisted_citation_entries(_parse(self.FIXTURE))}
        self.assertNotIn("GB_755", entries)

    def test_example_content_is_not_a_citation(self):
        """示例里的引用只是示范写法（正文示例常是裸段落）。"""
        entries = {entry["base_id"] for entry in R.unlisted_citation_entries(_parse(self.FIXTURE))}
        self.assertNotIn("GB_T_4003", entries)

    def test_foreword_and_scope_mentions_are_not_reported(self):
        entries = {entry["base_id"] for entry in R.unlisted_citation_entries(_parse(self.FIXTURE))}
        self.assertNotIn("GB_T_1.1", entries)  # 前言（前置要素）
        self.assertNotIn("GB_T_9999", entries)  # 范围章里的资料性提及

    def test_summary_and_compliance_expose_the_finding(self):
        from leleby_ssir.compliance import verify_compliance

        document = _parse(self.FIXTURE)
        summary = R.summarise(document)
        self.assertEqual(summary["unlistedCitationCount"], 1)
        self.assertEqual(summary["unlistedCitations"][0]["base_id"], "GB_T_4001")

        report = verify_compliance(document, metadata=None)
        hits = [f for f in report.findings if f.check == "normative-citation-not-listed"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].rule_id, "GBT-C06")
        self.assertEqual(hits[0].priority, "should")
        message = hits[0].message
        self.assertIn("GB/T 4001", message)
        self.assertIn("原文“GB/T 4001”", message)
        self.assertIn("4.1", message)
        self.assertNotIn("4002", message)
        self.assertNotIn("4003", message)


if __name__ == "__main__":
    unittest.main()
