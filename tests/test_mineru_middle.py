"""MinerU ``middle.json`` → CSM raw Markdown 适配器（leleby_ssir.mineru_middle）回归测试。

覆盖（对任何 middle.json 成立的通用映射，不针对某份文档）：

- 标题 ``level`` → ``#`` 层数（钳制 1~6）；
- 段落：块内多行按 CJK 规则拼接（汉字侧不补空格、拉丁词边界补一个空格），
  ``merge_prev`` 并入前一段落；
- ``table`` 块：题注行 + ``table_body`` 的 HTML（行列合并、``<eq>`` 行内公式）；无正文时
  如实回报（题注保留 + 占位说明 + 警告），不编造表格内容；
- ``image`` 块：图片行 + 题注行（顺序与 MinerU markdown 一致，供下游吸附题注）；
  ``chart`` 块（整块栅格化的版式示意图）同处理，内层块按 ``*_body/*_caption/*_footnote``
  后缀取部件；
- ``ref_text``/``index``/``list`` 块：一行一条记录，条目边界保留（不按段落拼接）；
- ``interline_equation`` → ``$$`` 公式块；
- ``discarded_blocks``（页眉/页脚/页码）不进正文，但首页的 ICS/CCS 与发布机构行由
  ``cover_hints`` 单独恢复（``issuer-text`` 交调用方按机构名录解析）；
- 未知块类型：跳过并记警告。
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leleby_ssir.mineru_html import convert_mineru_markup  # noqa: E402
from leleby_ssir.mineru_middle import (  # noqa: E402
    MiddleJsonError,
    cover_hints,
    image_source_sizes,
    middle_json_to_csm_markdown,
)


def _span(text: str = "", **extra: object) -> dict:
    span = {"type": "text", "content": text}
    span.update(extra)
    return span


def _block(kind: str, lines: list[list[dict]], **extra: object) -> dict:
    block = {"type": kind, "lines": [{"spans": spans} for spans in lines]}
    block.update(extra)
    return block


FIXTURE = {
    "_backend": "hybrid",
    "pdf_info": [
        {
            "page_idx": 0,
            "para_blocks": [
                _block("title", [[_span("中华人民共和国国家标准")]], level=1),
                _block("text", [[_span("GB/T 20001.6—2017")]], merge_prev=False),
                _block("title", [[_span("标准编写规则 第 6 部分: 规程标准")]], level=1),
                _block("title", [[_span("Rules for drafting standards")]], level=2),
                _block("text", [[_span("2017-12-29 发布")]], merge_prev=False),
            ],
            "discarded_blocks": [
                # 真实形态：ICS 与 CCS 两行来自同一个 span 的内嵌换行
                {"type": "header", "lines": [{"spans": [_span("ICS 01.120\nA 00")]}]},
                {"type": "header", "lines": [{"spans": [_span("GB")]}]},
                {
                    "type": "footer",
                    "lines": [
                        {"spans": [_span("中华人民共和国国家质量监督检验检疫总局 发布")]},
                        {"spans": [_span("中国国家标准化管理委员会")]},
                    ],
                },
                {"type": "page_number", "lines": [{"spans": [_span("1")]}]},
            ],
        },
        {
            "page_idx": 1,
            "para_blocks": [
                _block("title", [[_span("5 结构")]], level=2),
                # 块内两行：汉字侧不补空格
                _block("text", [[_span("规程标准的必备要素包括：封面、前言、")], [_span("标准名称、范围。")]]),
                # 拉丁词边界补一个空格
                _block("text", [[_span("GB/T 1.1")], [_span("and GB/T 20000.1")]]),
                # merge_prev：跨栏切断的同一段
                _block("text", [[_span("程序确立和程序指示")]], merge_prev=True),
                _block("text", [[_span("-第1部分:术语标准;")]], merge_prev=False),
                _block(
                    "table",
                    [],
                    blocks=[
                        {"type": "table_caption", "lines": [{"spans": [_span("表 1 规程标准中要素的典型编排")]}]},
                        {
                            "type": "table_body",
                            "lines": [
                                {
                                    "spans": [
                                        {
                                            "type": "table",
                                            "html": '<table><tr><td>要素类型</td><td><eq>要素^a</eq>的编排</td></tr>'
                                                    '<tr><td rowspan="2">资料性概述要素</td><td>封面</td></tr>'
                                                    "<tr><td>目次</td></tr></table>",
                                        }
                                    ]
                                }
                            ],
                        },
                    ],
                ),
                _block(
                    "image",
                    [],
                    blocks=[
                        {
                            "type": "image_body",
                            "lines": [{"spans": [{"type": "image", "image_path": "https://cdn.example/a.jpg"}]}],
                        },
                        {"type": "image_caption", "lines": [{"spans": [_span("图 1 程序流程图")]}]},
                    ],
                ),
                _block("interline_equation", [[_span("E = m c ^ 2", type="interline_equation")]]),
                # 一行一条记录的块（GEN-099）：条目边界必须保留
                _block("ref_text", [[_span("[1] GB 3100 国际单位制及其应用")],
                                    [_span("[2] GB/T 4458.1 机械制图 图样画法 视图")]]),
                _block("index", [[_span("5 结构 …… 3")], [_span("5.1 通则 …… 4")]]),
                _block("list", [[_span("第一条列项。")], [_span("第二条列项。")]]),
                # chart 块（GEN-100）：整块栅格化的版式示意图，内层块名 chart_*
                _block(
                    "chart",
                    [],
                    bbox=[78.0, 112.0, 523.0, 739.0],
                    blocks=[
                        {"type": "chart_body",
                         "lines": [{"spans": [{"type": "chart", "image_path": "https://cdn.example/chart.png"}]}]},
                        {"type": "chart_caption", "lines": [{"spans": [_span("图 E.8 目次格式")]}]},
                        {"type": "chart_footnote", "lines": [{"spans": [_span("注：以单数页为例。")]}]},
                    ],
                ),
                {"type": "unknown_kind", "lines": [{"spans": [_span("???")]}]},
            ],
            "discarded_blocks": [{"type": "header", "lines": [{"spans": [_span("GB/T 20001.6—2017")]}]}],
        },
        {
            "page_idx": 2,
            "para_blocks": [
                _block(
                    "table",
                    [],
                    blocks=[
                        {"type": "table_caption", "lines": [{"spans": [_span("表 2 无正文的表格")]}]},
                        {"type": "table_body", "lines": []},
                    ],
                ),
            ],
        },
    ],
}


class TitleAndTextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.markdown, self.warnings = middle_json_to_csm_markdown(FIXTURE)

    def test_title_levels_map_to_heading_depth(self) -> None:
        self.assertIn("# 中华人民共和国国家标准\n", self.markdown)
        self.assertIn("# 标准编写规则 第 6 部分: 规程标准\n", self.markdown)
        self.assertIn("## Rules for drafting standards\n", self.markdown)

    def test_text_block_lines_join_by_cjk_rule(self) -> None:
        # 汉字侧不补空格
        self.assertIn("规程标准的必备要素包括：封面、前言、标准名称、范围。", self.markdown)
        # 拉丁词边界补一个空格
        self.assertIn("GB/T 1.1 and GB/T 20000.1", self.markdown)
        # 列表条目原文保留（下游按既有列项规则归一）
        self.assertIn("-第1部分:术语标准;", self.markdown)

    def test_merge_prev_joins_into_previous_paragraph(self) -> None:
        self.assertIn("GB/T 1.1 and GB/T 20000.1程序确立和程序指示", self.markdown)

    def test_discarded_blocks_are_not_in_body(self) -> None:
        self.assertNotIn("ICS 01.120", self.markdown)
        self.assertNotIn("中国国家标准化管理委员会", self.markdown)


class TableAndImageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.markdown, self.warnings = middle_json_to_csm_markdown(FIXTURE)

    def test_table_caption_precedes_html_body(self) -> None:
        self.assertLess(self.markdown.index("表 1 规程标准中要素的典型编排"), self.markdown.index("<table>"))
        self.assertIn('<eq>要素^a</eq>', self.markdown)
        self.assertIn('rowspan="2"', self.markdown)

    def test_table_without_body_is_reported_not_invented(self) -> None:
        self.assertIn("表 2 无正文的表格", self.markdown)
        self.assertIn("（表格结构未识别，原始抽取未提供表格正文）", self.markdown)
        self.assertTrue(any("table body missing" in warning for warning in self.warnings))

    def test_image_caption_goes_into_the_alt_text(self) -> None:
        """题注写进替代文本（MinerU 已绑定该图）——尾部独立题注行会被下游抢给前一张图。"""
        self.assertIn("![图 1 程序流程图](https://cdn.example/a.jpg)", self.markdown)

    def test_interline_equation_block(self) -> None:
        self.assertIn("$$\nE = m c ^ 2\n$$", self.markdown)

    def test_unknown_block_is_reported(self) -> None:
        self.assertTrue(any("unsupported block type" in warning for warning in self.warnings))
        self.assertNotIn("???", self.markdown)

    def test_downstream_adapter_turns_it_into_a_csm_table(self) -> None:
        """整合：转换产物交给 merge 阶段的同一个适配器 → CSM 表格指令（含 GEN-097 行内公式）。"""
        converted = convert_mineru_markup(self.markdown, "raw")
        self.assertIn('<!-- ssir:table id="mineru-table-raw-001"', converted)
        self.assertIn('caption="规程标准中要素的典型编排"', converted)
        self.assertIn("$要素^a$的编排", converted)
        self.assertIn("| 资料性概述要素 | 封面 |", converted)


class CoverHintsTests(unittest.TestCase):
    def test_ics_ccs_and_issuer_text(self) -> None:
        hints = cover_hints(FIXTURE)
        self.assertEqual(hints["ics"], "01.120")
        self.assertEqual(hints["ccs"], "A 00")
        self.assertEqual(hints["issuer-text"], "中华人民共和国国家质量监督检验检疫总局发布中国国家标准化管理委员会")

    def test_embedded_newline_in_a_span_is_two_visual_lines(self) -> None:
        """页眉 span 内容里的 \n 是可视行分隔（否则 ICS/CCS 会被当成一行解析失败）。"""
        hints = cover_hints(
            {"pdf_info": [{"para_blocks": [], "discarded_blocks": [
                {"type": "header", "lines": [{"spans": [{"type": "text", "content": "ICS 29.160.30\nK 24"}]}]}]}]}
        )
        self.assertEqual(hints["ics"], "29.160.30")
        self.assertEqual(hints["ccs"], "K 24")

    def test_ccs_prefixed_form_is_recovered(self) -> None:
        """CCS 行两种写法都收：本地路线裸写 ``A 00``，云端路线带前缀 ``CCS A 00``。"""
        hints = cover_hints(
            {"pdf_info": [{"para_blocks": [], "discarded_blocks": [
                {"type": "header", "lines": [{"spans": [{"type": "text", "content": "ICS 01.120\nCCS A 00"}]}]}]}]}
        )
        self.assertEqual(hints["ics"], "01.120")
        self.assertEqual(hints["ccs"], "A 00")

    def test_ics_and_ccs_on_one_line_are_split(self) -> None:
        """本地路线的页眉把两号写在同一行且 ICS 与号码无空格（``ICS01.120 A 00``）。"""
        hints = cover_hints(
            {"pdf_info": [{"para_blocks": [], "discarded_blocks": [
                {"type": "header", "lines": [{"spans": [{"type": "text", "content": "ICS01.120 A 00"}]}]}]}]}
        )
        self.assertEqual(hints["ics"], "01.120")
        self.assertEqual(hints["ccs"], "A 00")

    def test_standard_designation_is_not_read_as_a_ccs_code(self) -> None:
        """页眉里的标准代号（``GB``、``GB/T 20001.5—2017``）不得被当成 CCS 代号。"""
        hints = cover_hints(
            {"pdf_info": [{"para_blocks": [], "discarded_blocks": [
                {"type": "header", "lines": [{"spans": [{"type": "text", "content": "GB/T 20001.5—2017"}]}]},
                {"type": "header", "lines": [{"spans": [{"type": "text", "content": "GB"}]}]},
            ]}]}
        )
        self.assertNotIn("ccs", hints)
        self.assertNotIn("ics", hints)

    def test_ccs_fraction_form_is_kept(self) -> None:
        hints = cover_hints(
            {"pdf_info": [{"para_blocks": [], "discarded_blocks": [
                {"type": "header", "lines": [{"spans": [{"type": "text", "content": "ICS 29.160.30\nCCS K24.1"}]}]}]}]}
        )
        self.assertEqual(hints["ccs"], "K 24.1")

    def test_missing_cover_fields_are_absent(self) -> None:
        hints = cover_hints({"_backend": "hybrid", "pdf_info": [{"para_blocks": [], "discarded_blocks": []}]})
        self.assertEqual(hints, {})

    def test_stray_header_codes_do_not_become_ccs(self) -> None:
        # 页眉里的 "GB" 不是 CCS 代号（必须「字母 + 数字」形态）。
        hints = cover_hints(FIXTURE)
        self.assertNotIn("GB", hints.values())

    def test_malformed_payload_raises(self) -> None:
        with self.assertRaises(MiddleJsonError):
            middle_json_to_csm_markdown({"pages": []})
        with self.assertRaises(MiddleJsonError):
            cover_hints({"pages": []})



class ImageSourceSizeTests(unittest.TestCase):
    """GEN-076 第二来源：middle.json 图块 bbox → 资产版面尺寸（无源 PDF 时使用）。"""

    @staticmethod
    def _image_block(bbox: list[float] | None, path: str) -> dict:
        block = _block(
            "image",
            [],
            blocks=[{"type": "image_body",
                     "lines": [{"spans": [{"type": "image", "image_path": path}]}]}],
        )
        if bbox is not None:
            block["bbox"] = bbox
        return block

    def test_bbox_becomes_the_asset_size(self) -> None:
        data = {"pdf_info": [{"page_idx": 1, "para_blocks": [
            self._image_block([100.0, 200.0, 371.6, 561.4], "https://cdn.example/a.jpg")]}]}
        self.assertEqual(image_source_sizes(data), {"a.jpg": (271.6, 361.4)})

    def test_query_string_and_directory_are_normalised_to_the_asset_name(self) -> None:
        data = {"pdf_info": [{"page_idx": 2, "para_blocks": [
            self._image_block([0, 0, 50, 50], "images/b.png?v=2#frag")]}]}
        self.assertEqual(image_source_sizes(data), {"b.png": (50.0, 50.0)})

    def test_cover_emblem_and_tiny_blocks_are_skipped(self) -> None:
        """首页高 < 100pt 的徽标与 < 10pt 的装饰图不参与（与源 PDF 路径同一过滤）。"""
        data = {"pdf_info": [
            {"page_idx": 0, "para_blocks": [self._image_block([400, 30, 510, 85], "images/logo.png")]},
            {"page_idx": 1, "para_blocks": [self._image_block([0, 0, 6, 40], "images/dot.png")]},
        ]}
        self.assertEqual(image_source_sizes(data), {})

    def test_block_without_bbox_is_ignored(self) -> None:
        """没有几何信息就不猜尺寸（渲染端按默认尺寸），不编造。"""
        data = {"pdf_info": [{"page_idx": 1, "para_blocks": [
            self._image_block(None, "images/c.jpg")]}]}
        self.assertEqual(image_source_sizes(data), {})

class RecordBlockTests(unittest.TestCase):
    """GEN-099：``ref_text``/``index``/``list`` 是「一行一条记录」的块，条目边界必须保留。

    这三族块的 ``lines[]`` 是记录而不是段落折行；按段落规则拼接会把整块粘成一段
    （raw 起点路线据此丢失参考文献与索引，见 docs/12 §3）。
    """

    def setUp(self) -> None:
        self.markdown, self.warnings = middle_json_to_csm_markdown(FIXTURE)

    def test_reference_entries_stay_separate_lines(self) -> None:
        self.assertIn("[1] GB 3100 国际单位制及其应用\n[2] GB/T 4458.1 机械制图 图样画法 视图", self.markdown)

    def test_toc_and_index_rows_stay_separate_lines(self) -> None:
        self.assertIn("5 结构 …… 3\n5.1 通则 …… 4", self.markdown)

    def test_list_items_stay_separate_lines(self) -> None:
        self.assertIn("第一条列项。\n第二条列项。", self.markdown)

    def test_empty_record_block_is_reported_not_silently_dropped(self) -> None:
        markdown, warnings = middle_json_to_csm_markdown(
            {"pdf_info": [{"para_blocks": [_block("ref_text", [])]}]}
        )
        self.assertEqual(markdown.strip(), "")
        self.assertTrue(any("row block without text" in warning for warning in warnings))


class ChartBlockTests(unittest.TestCase):
    """GEN-100：``chart`` 块（整块栅格化的版式示意图）与 ``image`` 同处理。

    内层块名 ``chart_body``/``chart_caption``/``chart_footnote`` 与前缀无关，按后缀取
    部件——云端路线把 GB/T 1.1-2020 图 E.8 目次格式判成 ``chart``，旧适配器只认
    ``image_*``，整张图连同题注一起被丢掉（docs/12 §3）。
    """

    def setUp(self) -> None:
        self.markdown, self.warnings = middle_json_to_csm_markdown(FIXTURE)

    def test_chart_body_becomes_a_figure_with_the_caption_in_the_alt_text(self) -> None:
        self.assertIn("![图 E.8 目次格式](https://cdn.example/chart.png)", self.markdown)

    def test_chart_footnote_follows_the_figure(self) -> None:
        self.assertLess(self.markdown.index("chart.png"), self.markdown.index("注：以单数页为例。"))

    def test_chart_is_not_reported_as_unsupported(self) -> None:
        self.assertFalse(any("chart" in warning for warning in self.warnings))

    def test_chart_footprint_counts_as_a_figure_source_size(self) -> None:
        data = {"pdf_info": [{"page_idx": 3, "para_blocks": [
            {"type": "chart", "bbox": [78, 112, 523, 739], "blocks": [
                {"type": "chart_body",
                 "lines": [{"spans": [{"type": "chart", "image_path": "images/chart.png"}]}]}]}]}]}
        self.assertEqual(image_source_sizes(data), {"chart.png": (445.0, 627.0)})


class EquationBlockTests(unittest.TestCase):
    """GEN-102：`interline_equation` 块内的公式，含中文 LaTeX 时改用图资产。

    MathText 没有汉字字形，现场排版会把汉字印成假字形（GB/T 20001.5-2017 示例1
    「综合差错率」实测）；块内同时给了裁剪图时用图，其余情况仍优先 LaTeX。
    """

    @staticmethod
    def _block(latex: str, asset: str | None) -> dict:
        span = {"type": "interline_equation", "content": latex}
        if asset:
            span["image_path"] = asset
        return {"type": "interline_equation", "lines": [{"spans": [span]}]}

    def _markdown(self, latex: str, asset: str | None) -> str:
        markdown, _warnings = middle_json_to_csm_markdown(
            {"pdf_info": [{"para_blocks": [self._block(latex, asset)]}]}
        )
        return markdown

    def test_cjk_latex_becomes_a_formula_block_with_the_image_asset(self) -> None:
        markdown = self._markdown(r"\mathrm{综合差错率} = K C_{\mathrm{A}} \times 100", "https://cdn.example/f1.jpg")
        # 仍是 formula 块（保住公式语义/编号），但带 asset-ref 让渲染端画图而不是现场排版
        self.assertIn('<!-- ssir:formula asset-ref="https://cdn.example/f1.jpg" -->', markdown)
        self.assertIn(r"\mathrm{综合差错率}", markdown)

    def test_latin_latex_still_prefers_latex(self) -> None:
        markdown = self._markdown(r"v = 3.6 \times \frac{l}{t}", "https://cdn.example/f2.jpg")
        self.assertIn("$$\n", markdown)
        self.assertIn(r"v = 3.6 \times \frac{l}{t}", markdown)

    def test_cjk_latex_without_asset_is_still_emitted(self) -> None:
        markdown = self._markdown(r"\mathrm{密度} = \frac{m}{V}", None)
        self.assertIn("$$\n", markdown)

    def test_full_width_punctuation_counts_as_cjk(self) -> None:
        markdown = self._markdown(r"c_{\mathrm{II}} = 1 。", "https://cdn.example/f3.jpg")
        self.assertIn('asset-ref="https://cdn.example/f3.jpg"', markdown)


if __name__ == "__main__":
    unittest.main()
