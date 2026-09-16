"""tools/build_ssir.py（raw 起点流水线）的回归测试。

覆盖本工具新增的通用步骤（其余阶段复用 mineru_full_standard 的既有函数，由既有
测试与流水线验证覆盖）：

- ``_split_front_matter``：有/无 YAML front matter 的切分；
- ``_cover_metadata``：封面区字段恢复（代替标准 / 发布实施日期 / 英文译名 / ICS、CCS），
  取不到留空、正文里的同名句子不参与（封面块以外不匹配）；
- ``_infer_title``：横幅与英文译名不是标题（GBT-C01）；
- ``_build_front_matter``：最小合法 front matter（键与 merge 一致、值 JSON 引号），
  且能被真正的 CSM 解析器接受（normalize 端到端的最小夹具）；
- ``_rewrite_front_matter``：既有 front matter 上覆盖顶层键、缺键追加、其它行不动；
- ``_materialize_remote_images``：远程图片落地为 assets/images/<name>、幂等、
  失败保持原链接且不产出半成品文件；
- ``_resolve_raw``：裸 ID 的查找顺序（out/mineru/<ID>/01_extract 优先于 rawFile/）。
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import build_ssir as r2s  # noqa: E402

BARE_RAW = """# 中华人民共和国国家标准

GB/T 10401—2023

代替 GB/T 10401—2008

# 永磁式直流力矩电动机通用技术规范

# General specification for permanent magnet direct current torque motors

2023-09-07 发布

2024-04-01 实施

ICS 29.160.30

CCS K 24

## 目次

前言 …… III

## 前言

本文件按照 GB/T 1.1—2020 的规定起草。

## 1 范围

本文件规定了永磁式直流力矩电动机的通用技术要求。

## 2 规范性引用文件

- 代替条款中的正文句子不得被当成封面字段。
"""

WITH_FRONT_MATTER = """---
csm-version: "1.0"
document-type: standard
document-identifier: "GB/T 10401-2023"
standard-number: "GB/T 10401-2023"
title: "永磁式直流力矩电动机通用技术规范"
language: zh-CN
---

# 永磁式直流力矩电动机通用技术规范

## 1 范围

正文。
"""


class FrontMatterSplitTests(unittest.TestCase):
    def test_split_returns_body_only_for_bare_raw(self) -> None:
        front_matter, body = r2s._split_front_matter(BARE_RAW)
        self.assertIsNone(front_matter)
        self.assertEqual(body, BARE_RAW)

    def test_split_strips_fences_and_keeps_body(self) -> None:
        front_matter, body = r2s._split_front_matter(WITH_FRONT_MATTER)
        self.assertIsNotNone(front_matter)
        self.assertIn('standard-number: "GB/T 10401-2023"', front_matter or "")
        self.assertNotIn("---", front_matter or "")
        self.assertTrue(body.startswith("\n# 永磁式直流力矩电动机通用技术规范"))


class CoverMetadataTests(unittest.TestCase):
    def test_cover_fields_recovered(self) -> None:
        meta = r2s._cover_metadata(BARE_RAW)
        self.assertEqual(meta["replaces"], "GB/T 10401—2008")
        self.assertEqual(meta["publication-date"], "2023-09-07")
        self.assertEqual(meta["effective-date"], "2024-04-01")
        self.assertEqual(meta["title-en"], "General specification for permanent magnet direct current torque motors")
        self.assertEqual(meta["ics"], "29.160.30")
        self.assertEqual(meta["ccs"], "K 24")

    def test_plain_cover_without_h1_markers(self) -> None:
        """封面行未提升为标题时同样恢复（归位前后两种形态都覆盖）。"""
        meta = r2s._cover_metadata("# 中华人民共和国国家标准\n\n# 标准化工作导则 第1部分：起草规则\n\nDirectives for standardization\n\n2020-03-31 发布\n\n## 1 范围\n")
        self.assertEqual(meta["title-en"], "Directives for standardization")
        self.assertEqual(meta["publication-date"], "2020-03-31")

    def test_body_text_after_first_section_is_not_cover(self) -> None:
        raw = "# 中华人民共和国国家标准\n\n# 标题\n\n## 1 范围\n\n代替 GB/T 9999—1999\n\n2020-01-01 发布\n"
        meta = r2s._cover_metadata(raw)
        self.assertNotIn("replaces", meta)
        self.assertNotIn("publication-date", meta)

    def test_missing_fields_are_left_empty_not_guessed(self) -> None:
        meta = r2s._cover_metadata("# 中华人民共和国国家标准\n\n# 标题\n")
        self.assertEqual(meta, {})

    def test_ocr_dash_variants_normalize_to_iso_date(self) -> None:
        raw = "# 中华人民共和国国家标准\n\n2023—9—7 发布\n\n2024–4–1 实施\n\n## 1 范围\n"
        meta = r2s._cover_metadata(raw)
        self.assertEqual(meta["publication-date"], "2023-09-07")
        self.assertEqual(meta["effective-date"], "2024-04-01")


class InferTitleTests(unittest.TestCase):
    def test_banner_and_english_title_are_skipped(self) -> None:
        self.assertEqual(r2s._infer_title(BARE_RAW, "GB/T 10401-2023"), "永磁式直流力矩电动机通用技术规范")

    def test_multi_part_title_gap_restored(self) -> None:
        raw = "# 标准编写规则第6部分：规程标准\n\n## 1 范围\n"
        self.assertEqual(r2s._infer_title(raw, "GB/T 1.1-2020"), "标准编写规则 第6部分：规程标准")

    def test_banner_only_falls_back_to_number(self) -> None:
        raw = "# 中华人民共和国国家标准\n\n## 目次\n"
        self.assertEqual(r2s._infer_title(raw, "GB/T 10401-2023"), "GB/T 10401-2023")


class BuildFrontMatterTests(unittest.TestCase):
    def _meta(self, **extra: str) -> dict[str, str]:
        return {"standard-number": "GB/T 10401-2023", "title": "永磁式直流力矩电动机通用技术规范", **extra}

    def test_required_keys_and_quoted_values(self) -> None:
        text = r2s._build_front_matter(self._meta(), "GB_T_10401-2023.md", "raw-markdown", "x.provenance.json")
        self.assertTrue(text.startswith("---\n"))
        self.assertTrue(text.rstrip().endswith("---"))
        for key in ("csm-version", "document-type", "document-identifier", "standard-number", "title", "language", "source", "extraction-backend"):
            self.assertIn(f"{key}", text)
        self.assertIn('standard-number: "GB/T 10401-2023"', text)
        self.assertIn('original-file-name: "GB_T_10401-2023.md"', text)
        self.assertIn("mode: raw-markdown", text)

    def test_cover_keys_order_follows_merge(self) -> None:
        text = r2s._build_front_matter(
            self._meta(replaces="GB/T 10401—2008", **{"publication-date": "2023-09-07"}), "a.md", "raw-markdown", "p.json"
        )
        lines = text.splitlines()
        self.assertLess(lines.index('replaces: "GB/T 10401—2008"'), lines.index('publication-date: "2023-09-07"'))
        self.assertLess(lines.index('title: "永磁式直流力矩电动机通用技术规范"'), lines.index('replaces: "GB/T 10401—2008"'))

    def test_synthesized_front_matter_is_accepted_by_the_csm_normalizer(self) -> None:
        """最小夹具端到端：合成 front matter 的裸 raw 能被 normalize 接受（不加壳、不特判）。"""
        from leleby_ssir.service import normalize_csm

        body = r2s._normalize_cover(BARE_RAW)
        meta = r2s._final_cover_meta("GB/T 10401-2023", r2s._infer_title(body, "GB/T 10401-2023"), body, {})
        text = r2s._build_front_matter(meta, "GB_T_10401-2023.md", "raw-markdown", "p.json")
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw.md"
            raw.write_text(f"{text.rstrip()}\n\n{body.strip()}\n", encoding="utf-8")
            ssir, _report = normalize_csm(raw, Path(tmp) / "out.canonical.md")
        self.assertEqual(ssir["id"], "ssir:GB-T-10401-2023")
        self.assertEqual(ssir["metadata"]["common"]["title"], "永磁式直流力矩电动机通用技术规范")
        self.assertEqual(ssir["metadata"]["standard"]["standardNumber"], "GB/T 10401-2023")


class CoverMetaPrecedenceTests(unittest.TestCase):
    def test_explicit_overrides_win_over_cover_recovery(self) -> None:
        body = r2s._normalize_cover(BARE_RAW)
        meta = r2s._final_cover_meta(
            "GB/T 10401-2023", "永磁式直流力矩电动机通用技术规范", body, {"publication-date": "2023-10-01"}
        )
        self.assertEqual(meta["publication-date"], "2023-10-01")
        self.assertEqual(meta["replaces"], "GB/T 10401—2008")
        text = r2s._build_front_matter(meta, "a.md", "raw-markdown", "p.json")
        self.assertIn('publication-date: "2023-10-01"', text)
        self.assertNotIn("2023-09-07", text)

    def test_blank_override_does_not_erase_recovered_value(self) -> None:
        meta = r2s._final_cover_meta("GB/T X", "T", BARE_RAW, {"ics": ""})
        self.assertEqual(meta["ics"], "29.160.30")


class CoverNormalizationTests(unittest.TestCase):
    def test_banner_and_english_h1_demoted_cover_title_kept(self) -> None:
        body = r2s._normalize_cover(BARE_RAW)
        h1 = [line for line in body.splitlines() if line.startswith("# ")]
        self.assertEqual(h1, ["# 永磁式直流力矩电动机通用技术规范"])
        self.assertIn("中华人民共和国国家标准", body.splitlines()[0].lstrip("# "))
        self.assertIn("General specification for permanent magnet direct current torque motors", body)

    def test_idempotent(self) -> None:
        once = r2s._normalize_cover(BARE_RAW)
        self.assertEqual(r2s._normalize_cover(once), once)


FIXTURE_MARKUP_RAW = """# 中华人民共和国国家标准

GB/T 10401—2023

# 永磁式直流力矩电动机通用技术规范

2023-09-07 发布

## 1 范围

本文件规定了永磁式直流力矩电动机的技术要求。

## 5.1 引出线或接线端

电动机出线方式应符合表1的规定，接线见图 1。

表1 出线方式和标记

<table><tr><td>出线方式</td><td>正极性标记</td><td>负极性标记</td></tr><tr><td>引出线</td><td>红</td><td>黑或白</td></tr><tr><td>接线片(柱)</td><td>1</td><td>2</td></tr></table>

![image](https://cdn-mineru.example/x.jpg)

图 1 接线图

![image](https://cdn-mineru.example/y.jpg)

## 5.2 外观

外观应符合本文件的规定。
"""


class MineruMarkupAdaptationTests(unittest.TestCase):
    """raw 里的 MinerU 标记必须先按 merge 的同一套转换落成 CSM（GEN-032/033/096、GBT-X06）。

    用户报告的两个渲染缺陷即源于此：HTML 表格没转成 CSM 表格（表格不渲染）、
    ``![image](…)`` 的占位替代文本被当成图题名（图下多出「图 image」）。
    """

    def test_html_table_becomes_csm_table_directive_with_caption(self) -> None:
        out = r2s._adapt_mineru_markup(FIXTURE_MARKUP_RAW, r2s._RAW_PART_PREFIX)
        self.assertNotIn("<table", out)
        self.assertIn('<!-- ssir:table id="mineru-table-raw-001"', out)
        self.assertIn('caption="出线方式和标记"', out)
        self.assertIn("| 出线方式 | 正极性标记 | 负极性标记 |", out)
        # 题注行被吸附进表格指令，不再以孤立段落残留。
        self.assertNotIn("\n表1 出线方式和标记\n\n<!-- ssir:table", out)

    def test_adaptation_is_idempotent_for_csm_raw(self) -> None:
        once = r2s._adapt_mineru_markup(FIXTURE_MARKUP_RAW, r2s._RAW_PART_PREFIX)
        self.assertEqual(r2s._adapt_mineru_markup(once, r2s._RAW_PART_PREFIX), once)

    def test_end_to_end_table_and_figure_captions(self) -> None:
        """转换后经 normalize/parse：表进 SSIR tables，图题取原文题注、占位 alt 不留题注。"""
        from leleby_ssir.service import normalize_csm

        body = r2s._normalize_cover(r2s._adapt_mineru_markup(FIXTURE_MARKUP_RAW, r2s._RAW_PART_PREFIX))
        title = r2s._infer_title(body, "GB/T 10401-2023")
        meta = r2s._final_cover_meta("GB/T 10401-2023", title, body, {})
        front_matter = r2s._build_front_matter(meta, "GB_T_10401-2023.md", "raw-markdown", "p.json")
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw.md"
            raw.write_text(f"{front_matter.rstrip()}\n\n{body.strip()}\n", encoding="utf-8")
            ssir, _report = normalize_csm(raw, Path(tmp) / "out.canonical.md")
        tables = ssir["tables"]
        self.assertEqual([table["number"] for table in tables], ["1"])
        self.assertEqual(tables[0]["caption"], "出线方式和标记")
        self.assertEqual(len(tables[0]["rows"]), 3)
        captions = [figure.get("caption") for figure in ssir["figures"]]
        self.assertEqual(captions, ["接线图", None])
        self.assertEqual([figure.get("number") for figure in ssir["figures"]], ["1", None])
        self.assertNotIn("image", captions)


class FrontMatterRewriteTests(unittest.TestCase):
    def test_existing_key_replaced_in_place_and_others_untouched(self) -> None:
        text = r2s._rewrite_front_matter(
            'csm-version: "1.0"\ntitle: "旧标题"\nlanguage: zh-CN',
            {"title": "新标题", "ics": "29.160.30"},
        )
        self.assertEqual(text.splitlines(), ['csm-version: "1.0"', 'title: "新标题"', "language: zh-CN", 'ics: "29.160.30"'])

    def test_no_overrides_is_identity(self) -> None:
        front_matter = 'csm-version: "1.0"\ntitle: "标题"'
        self.assertEqual(r2s._rewrite_front_matter(front_matter, {}), front_matter)


class RemoteImageTests(unittest.TestCase):
    URL_A = "https://cdn-mineru.openxlab.org.cn/result/2026-09-12/abc/aaa.jpg"
    URL_B = "https://cdn-mineru.openxlab.org.cn/result/2026-09-12/abc/bbb.jpg"

    def test_remote_links_land_in_assets_and_local_links_stay(self) -> None:
        body = f"![image]({self.URL_A})\n\n![已落地](assets/images/keep.jpg)\n"
        with tempfile.TemporaryDirectory() as tmp:
            images = Path(tmp) / "assets" / "images"
            with mock.patch.object(r2s, "_fetch_image", return_value=b"jpeg") as fetch:
                text, downloaded, failures = r2s._materialize_remote_images(body, images)
        self.assertEqual(downloaded, 1)
        self.assertEqual(failures, [])
        self.assertEqual(fetch.call_count, 1)
        self.assertIn("![image](assets/images/aaa.jpg)", text)
        self.assertIn("![已落地](assets/images/keep.jpg)", text)
        self.assertNotIn("https://", text)

    def test_formula_directive_asset_ref_is_materialised_too(self) -> None:
        """指令形态的远端资产（GEN-102 的含中文公式）也要落地，否则渲染端退回现场排版。"""
        body = (
            f'<!-- ssir:formula asset-ref="{self.URL_A}" -->\n\n$$\n\\mathrm{{密度}} = \\frac{{m}}{{V}}\n$$\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            images = Path(tmp) / "assets" / "images"
            with mock.patch.object(r2s, "_fetch_image", return_value=b"png") as fetch:
                text, downloaded, failures = r2s._materialize_remote_images(body, images)
            self.assertTrue((images / "aaa.jpg").is_file())
        self.assertEqual((downloaded, failures), (1, []))
        self.assertEqual(fetch.call_count, 1)
        self.assertIn('asset-ref="assets/images/aaa.jpg"', text)
        self.assertNotIn("https://", text)

    def test_failure_keeps_original_link_and_writes_nothing(self) -> None:
        body = f"![image]({self.URL_B})\n"
        with tempfile.TemporaryDirectory() as tmp:
            images = Path(tmp) / "assets" / "images"
            with mock.patch.object(r2s, "_fetch_image", side_effect=OSError("network down")):
                text, downloaded, failures = r2s._materialize_remote_images(body, images)
            self.assertEqual(list(images.glob("*")), [])
        self.assertEqual(downloaded, 0)
        self.assertEqual(len(failures), 1)
        self.assertIn(self.URL_B, text)

    def test_second_run_is_idempotent_and_downloads_nothing(self) -> None:
        body = f"![image]({self.URL_A})\n"
        with tempfile.TemporaryDirectory() as tmp:
            images = Path(tmp) / "assets" / "images"
            with mock.patch.object(r2s, "_fetch_image", return_value=b"jpeg"):
                first, downloaded, _ = r2s._materialize_remote_images(body, images)
            with mock.patch.object(r2s, "_fetch_image", side_effect=AssertionError("must not refetch")):
                second, again, failures = r2s._materialize_remote_images(first, images)
        self.assertEqual(downloaded, 1)
        self.assertEqual(again, 0)
        self.assertEqual(failures, [])
        self.assertEqual(second, first)


class RawInputFormatTests(unittest.TestCase):
    """输入形态分派：.md 原样、.json = MinerU middle.json 先翻成同形 raw（GEN-002 来源登记）。"""

    MIDDLE = {
        "pdf_info": [
            {
                "page_idx": 0,
                "para_blocks": [{"type": "title", "level": 1, "lines": [{"spans": [{"type": "text", "content": "中华人民共和国国家标准"}]}]}],
                "discarded_blocks": [{"type": "header", "lines": [{"spans": [{"type": "text", "content": "ICS 01.120"}]}]}],
            }
        ]
    }

    def test_markdown_input_is_passed_through(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "GB_T_10401-2023.md"
            path.write_text("# 中华人民共和国国家标准\n", encoding="utf-8")
            text, fmt, warnings, hints = r2s._read_raw_source(path)
        self.assertEqual(fmt, "markdown")
        self.assertEqual(text, "# 中华人民共和国国家标准\n")
        self.assertEqual((warnings, hints), ([], {}))

    def test_middle_json_is_converted_with_cover_hints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "GB_T_20001.6-2017.json"
            path.write_text(json.dumps(self.MIDDLE, ensure_ascii=False), encoding="utf-8")
            text, fmt, warnings, hints = r2s._read_raw_source(path)
        self.assertEqual(fmt, "middle-json")
        self.assertIn("# 中华人民共和国国家标准", text)
        self.assertEqual(hints, {"ics": "01.120"})

    def test_unsupported_suffix_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.txt2"  # 未知后缀
            path.write_text("x", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                r2s._read_raw_source(path)

    def test_malformed_json_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.json"
            path.write_text('{"pages": []}', encoding="utf-8")
            with self.assertRaises(RuntimeError):
                r2s._read_raw_source(path)


class ResolveRawTests(unittest.TestCase):
    def test_extract_dir_wins_over_raw_file_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extract = root / "out" / "mineru" / "GB_T_10401-2023" / "01_extract"
            extract.mkdir(parents=True)
            (extract / "GB_T_10401-2023.raw.md").write_text("extract", encoding="utf-8")
            (root / "rawFile").mkdir()
            (root / "rawFile" / "GB_T_10401-2023.md").write_text("loose", encoding="utf-8")
            resolved = r2s._resolve_raw("GB_T_10401-2023", root)
        self.assertEqual(resolved.name, "GB_T_10401-2023.raw.md")
        self.assertIn("01_extract", str(resolved))

    def test_falls_back_to_raw_file_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "rawFile").mkdir()
            (root / "rawFile" / "GB_T_10401-2023.md").write_text("loose", encoding="utf-8")
            self.assertEqual(r2s._resolve_raw("GB_T_10401-2023", root).name, "GB_T_10401-2023.md")

    def test_falls_back_to_raw_file_dir_json(self) -> None:
        """裸 ID 也认 rawFile/<ID>.json（MinerU middle.json 输入）。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "rawFile").mkdir()
            (root / "rawFile" / "GB_T_20001.6-2017.json").write_text("{}", encoding="utf-8")
            self.assertEqual(r2s._resolve_raw("GB_T_20001.6-2017", root).name, "GB_T_20001.6-2017.json")

    def test_explicit_path_is_taken_as_is(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "whatever.md"
            path.write_text("x", encoding="utf-8")
            self.assertEqual(r2s._resolve_raw(path, Path(tmp)), path)

    def test_missing_input_raises_with_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError) as ctx:
                r2s._resolve_raw("GB_T_99999-1999", Path(tmp))
        self.assertIn("rawFile", str(ctx.exception))


CLOUD_COVER_RAW = """# 中华人民共和国国家标准

GB/T 1.1—2020

代替 GB/T 1.1—2009

# 标准化工作导则 第 1 部分: 标准化文件的结构和起草规则

Directives for standardization—

Part 1: Rules for the structure and drafting of standardizing documents

(ISO/IEC Directives, Part 2, 2018, Principles and rules for the structure and drafting of ISO and IEC documents, NEQ)

2020-03-31 发布

2020-10-01 实施

国家市场监督管理总局发布
国家标准标准化管理委员会

## 目次

前言 …… V
"""


class CloudCoverMetadataTests(unittest.TestCase):
    """云端 middle.json 路线封面（GB/T 1.1-2020 实测形态，docs/12 §3）。

    三处与本地路线不同，都要能恢复：英文译名被拆成相邻两块、发布机构行落在**正文**封面块
    （本地路线在页脚里，由 ``mineru_middle.cover_hints`` 恢复）、非等效采用的括号拉丁长句。
    """

    def setUp(self) -> None:
        self.meta = r2s._cover_metadata(CLOUD_COVER_RAW)

    def test_english_title_joined_across_consecutive_latin_blocks(self) -> None:
        self.assertEqual(
            self.meta["title-en"],
            "Directives for standardization Part 1: Rules for the structure and drafting of standardizing documents",
        )

    def test_conformity_statement_is_the_parenthesised_latin_sentence(self) -> None:
        self.assertTrue(self.meta["conformity-statement"].startswith("(ISO/IEC Directives, Part 2, 2018,"))
        self.assertTrue(self.meta["conformity-statement"].endswith("NEQ)"))

    def test_issuer_resolved_from_the_body_release_line(self) -> None:
        self.assertEqual(self.meta["issuer"], "国家市场监督管理总局 国家标准化管理委员会")

    def test_issuer_not_guessed_when_only_the_date_line_has_release(self) -> None:
        meta = r2s._cover_metadata("# 中华人民共和国国家标准\n\n# 标题\n\n2020-03-31 发布\n")
        self.assertNotIn("issuer", meta)

    def test_issuer_not_guessed_when_the_org_is_unknown(self) -> None:
        meta = r2s._cover_metadata("# 中华人民共和国国家标准\n\n某某部发布\n")
        self.assertNotIn("issuer", meta)

    def test_longest_latin_run_wins(self) -> None:
        """多组拉丁行时取最长的一组（单行标题仍按原样恢复）。"""
        meta = r2s._cover_metadata(BARE_RAW)
        self.assertEqual(meta["title-en"], "General specification for permanent magnet direct current torque motors")


if __name__ == "__main__":
    unittest.main()
