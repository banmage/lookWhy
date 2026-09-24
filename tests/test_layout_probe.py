"""`layout.json` 版面通道（抽取阶段唯一读源 PDF 处）回归夹具。

背景（docs/16 §1/§2.3/§3「D1 裁定：源 PDF 在 MinerU 之后不再读取」）：文本层的几何
与文本读数从 ``pipeline`` 搬到 ``leleby_ssir.layout``，由抽取阶段写成
``01_extract/<ID>.layout.json``；消费端（normalize/parse/render）只读该文件。判据本身
不变——GEN-092（省略号后验补盲）、GEN-016/014（封面文本层兜底）的判定仍在消费端。

本文件锁三件事：① 探针读数与迁移前的 ``pipeline._text_layer_content_lines`` 逐字段相同
（同一过滤：页眉 y0<80、页脚纯页码）；② ``ellipsisLines`` 通道的收录判据（1-6 个省略号，
目录点线不收录）；③ 通道文件的读写契约（缺失/损坏 → 空 dict，消费端按「无判据」处理）。
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from leleby_ssir import layout as layout_module
from leleby_ssir.pipeline import _text_layer_content_lines


def _make_pdf(directory: Path, pages: list[list[tuple[float, float, str]]]) -> Path:
    """合成真实中文文本层 PDF（pymupdf 内置 CJK 字体；helv 无中文字形）。"""
    import pymupdf

    path = directory / "synthetic.pdf"
    document = pymupdf.open()
    for page_lines in pages:
        page = document.new_page()
        for x, y, text in page_lines:
            page.insert_text((x, y), text, fontsize=10, fontname="china-s")
    document.save(path)
    document.close()
    return path


class TextLayerProbeTests(unittest.TestCase):
    """探针读数 == 迁移前 pipeline 的文本层读数（同一过滤，逐字段相等）。"""

    def test_text_lines_match_the_pre_migration_reader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf = _make_pdf(Path(directory), [
                [
                    (72, 40, "GB/T 9999-2026"),        # 页眉（y0<80）→ 过滤
                    (72, 100, "5.1 第一条"),
                    (72, 120, "……"),
                    (72, 760, "1"),                     # 页脚页码 → 过滤
                ],
                [
                    (72, 200, "6.2 第二条"),
                    (72, 210, "……"),
                    (72, 760, "2"),
                ],
            ])
            layout = layout_module.build_layout(pdf)
            self.assertEqual(
                [(line["page"], line["x0"], line["y0"], line["text"]) for line in layout["textLines"]],
                [
                    (line["page"], line["x0"], line["y0"], line["text"])
                    for line in _text_layer_content_lines(pdf)
                ],
            )
            # 过滤确实发生过：页眉/页码不在通道里
            texts = [line["text"] for line in layout["textLines"]]
            self.assertNotIn("GB/T 9999-2026", texts)
            self.assertNotIn("1", texts)

    def test_bbox_keys_are_present_for_layout_consumers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf = _make_pdf(Path(directory), [[(72, 100, "5.1 第一条")]])
            line = layout_module.build_layout(pdf)["textLines"][0]
            self.assertTrue({"page", "x0", "y0", "x1", "y1", "text"} <= set(line))
            self.assertLess(line["x0"], line["x1"])
            self.assertLess(line["y0"], line["y1"])


class EllipsisChannelTests(unittest.TestCase):
    """``ellipsisLines`` 收录判据（GEN-092 的输入通道）。"""

    def test_short_ellipsis_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf = _make_pdf(Path(directory), [[
                (72, 100, "……"),
                (72, 120, "……"),
                (72, 140, "6.2 第二条"),
                (72, 160, "……………………………………"),  # 目录点线（>6）→ 不收录
            ]])
            layout = layout_module.build_layout(pdf)
            lines = layout["ellipsisLines"]
            # 收录的正是文本层里那些 1-6 个省略号的短行（文本层字符由 PDF 字体决定，
            # china-s 把 U+2026 映射成 U+22EF，故按判据断言而不是写死字符）。
            expected = [
                line["text"] for line in layout["textLines"]
                if layout_module.is_short_ellipsis(line["text"]) and line["text"] != "6.2 第二条"
            ]
            self.assertEqual(len(lines), 2)
            self.assertEqual([line["text"] for line in lines], expected)
            for line in lines:
                self.assertTrue(layout_module.is_short_ellipsis(line["text"]))
            self.assertNotIn("6.2 第二条", [line["text"] for line in lines])

    def test_predicate_boundaries(self) -> None:
        self.assertTrue(layout_module.is_short_ellipsis("……"))
        self.assertTrue(layout_module.is_short_ellipsis("… …"))    # 去空格后 2 个
        self.assertFalse(layout_module.is_short_ellipsis(""))
        self.assertFalse(layout_module.is_short_ellipsis("…" * 7))  # 7 个（去空格后）
        self.assertFalse(layout_module.is_short_ellipsis("…… …… …… ……"))  # 目录点线形态


class SourceFingerprintTests(unittest.TestCase):
    """``source`` 通道：SHA-256 与页数。"""

    def test_sha256_and_page_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf = _make_pdf(Path(directory), [[(72, 100, "A")], [(72, 100, "B")]])
            source = layout_module.build_layout(pdf)["source"]
            self.assertEqual(source["pdfSha256"], hashlib.sha256(pdf.read_bytes()).hexdigest())
            self.assertEqual(source["pageCount"], 2)
            self.assertEqual(source["producer"], layout_module.LAYOUT_PRODUCER)
            self.assertEqual(layout_module.build_layout(pdf)["schemaVersion"], "1.0")

    def test_scan_like_pdf_reports_unresolved_text_lines(self) -> None:
        # 无文本层的 PDF（空页）→ textLines 为空且如实登记 unresolved，不猜、不阻断。
        import pymupdf

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "blank.pdf"
            document = pymupdf.open()
            document.new_page()
            document.save(path)
            document.close()
            layout = layout_module.build_layout(path)
            self.assertEqual(layout["textLines"], [])
            self.assertEqual(
                sorted(item["channel"] for item in layout["unresolved"]),
                ["cover.pdfPage0Lines", "textLines"],
            )


class LayoutFileContractTests(unittest.TestCase):
    """通道文件契约：写盘可读回，缺失/损坏按「无判据」处理。"""

    def test_write_and_load_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = _make_pdf(root, [[(72, 100, "5.1 第一条")]])
            data = layout_module.build_layout(pdf)
            path = layout_module.write_layout(root / "01_extract" / "X.layout.json", data)
            self.assertTrue(path.is_file())
            self.assertEqual(layout_module.load_layout(path), data)
            # 稳定键序（便于逐字节 diff）
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            )

    def test_missing_or_broken_file_yields_empty_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(layout_module.load_layout(root / "nope.json"), {})
            broken = root / "broken.layout.json"
            broken.write_text("{not json", encoding="utf-8")
            self.assertEqual(layout_module.load_layout(broken), {})
            self.assertEqual(layout_module.load_layout(None), {})

    def test_consumers_tolerate_an_absent_channel(self) -> None:
        # 通道缺失 → 消费端不改文本（无判据 · 不猜）
        from leleby_ssir.pipeline import _restore_ellipsis_lines

        raw = "## 5.7 基础苗培养\n\n5.7.1 操作如下：\n\n……\n\n## 5.8 扩繁\n"
        self.assertEqual(_restore_ellipsis_lines(raw, {}), raw)
        self.assertEqual(_restore_ellipsis_lines(raw, layout_module.load_layout(None)), raw)


class LayoutConsumerContractTests(unittest.TestCase):
    """消费端契约：版面印记只吃 layout 通道，通道缺失即无操作（不猜、不读源 PDF）。

    对应 docs/16 §3（D1：「源 PDF 在 MinerU 之后不再读取」）——签名与源码双重锁定，
    防止后来者把 source_pdf 参数或 ``fitz.open`` 又加回构建路径。
    """

    def test_cover_page0_lines_channel_matches_the_pre_migration_read(self) -> None:
        """``cover.pdfPage0Lines`` == 迁移前的 ``doc[0].get_text()`` 逐行 strip。

        与 ``textLines`` 不同：本通道**不做**页眉/页脚过滤（封面兜底读的是原始行序）。
        """
        with tempfile.TemporaryDirectory() as directory:
            pdf = _make_pdf(Path(directory), [[
                (72, 40, "GB/T 9999-2026"),          # 封面眉线：本通道**保留**
                (72, 100, "中华人民共和国国家标准"),
                (72, 120, "Standard for testing"),
            ]])
            layout = layout_module.build_layout(pdf)
            lines = layout["cover"]["pdfPage0Lines"]
            self.assertIn("GB/T 9999-2026", lines)
            self.assertIn("中华人民共和国国家标准", lines)
            self.assertIn("Standard for testing", lines)
            self.assertNotIn("GB/T 9999-2026", [line["text"] for line in layout["textLines"]])

    def test_cover_fallback_reads_the_channel_without_any_pdf(self) -> None:
        """有通道、无源 PDF：英文标题兜底仍成立（旧实现在此处只能返回空）。"""
        from leleby_ssir.pipeline import _cover_english_from_pdf

        layout = {
            "cover": {
                "pdfPage0Lines": [
                    "中华人民共和国国家标准",
                    "标准化工作导则 第1部分：标准化文件的结构和起草规则",
                    "Directives for standardization",
                    "2020-03-31 发布",
                ]
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            part_dir = Path(directory) / "pages-001-018"
            part_dir.mkdir(parents=True)          # 目录里没有 PDF，也没有 markdown
            self.assertEqual(_cover_english_from_pdf(part_dir), [])
            self.assertEqual(
                _cover_english_from_pdf(part_dir, layout=layout),
                ["Directives for standardization"],
            )

    def test_issuer_fallback_reads_the_channel_without_any_pdf(self) -> None:
        """机构兜底（GEN-014）同样只读通道：无 PDF 时由 ``pdfPage0Lines`` 命中名录。"""
        from leleby_ssir.pipeline import _cover_issuer_from_pdf

        layout = {
            "cover": {
                "pdfPage0Lines": [
                    "中华人民共和国国家标准",
                    "标准化工作导则 第1部分：标准化文件的结构和起草规则",
                    "国家市场监督管理总局",
                    "国家标准化管理委员会",
                    "发布",
                ]
            }
        }
        with tempfile.TemporaryDirectory() as directory:
            part_dir = Path(directory) / "pages-001-018"
            part_dir.mkdir(parents=True)
            self.assertEqual(_cover_issuer_from_pdf(part_dir), "")
            issuer = _cover_issuer_from_pdf(part_dir, layout=layout)
            self.assertTrue(issuer, "机构名录应从通道文本里命中")

    def test_layout_stamps_take_a_layout_channel_not_a_source_pdf(self) -> None:
        import inspect

        from leleby_ssir import pipeline

        for fn in (pipeline._stamp_example_styles, pipeline._stamp_figure_source_sizes):
            self.assertEqual(list(inspect.signature(fn).parameters), ["ssir_path", "layout"], fn.__name__)

    def test_canonical_continuation_never_opens_a_source_pdf(self) -> None:
        import inspect

        from leleby_ssir import pipeline

        source = inspect.getsource(pipeline._run_from_existing_canonical)
        for token in ("fitz.open", "pymupdf.open", "get_drawings", "get_image_info", "args.input,"):
            self.assertNotIn(token, source, f"构建路径又出现源 PDF 读数：{token}")

    def test_stamps_are_no_ops_without_the_channel(self) -> None:
        from leleby_ssir.pipeline import _stamp_example_styles, _stamp_figure_source_sizes

        with tempfile.TemporaryDirectory() as directory:
            ssir = Path(directory) / "doc.ssir.json"
            payload = {
                "metadata": {"common": {"title": "T"}, "standard": {"standardNumber": "GB/T 1—2026"}},
                "structuralRoot": {"children": [{"id": "c1", "exampleContent": [{"id": "e1"}]}]},
                "figures": [{"id": "f-001", "assetRef": "assets/images/a.png"}],
            }
            ssir.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            _stamp_example_styles(ssir, {})
            _stamp_figure_source_sizes(ssir, {})
            data = json.loads(ssir.read_text(encoding="utf-8"))
            self.assertNotIn("exampleStyle", data["structuralRoot"]["children"][0])
            self.assertNotIn("sourceWidth", data["figures"][0])


if __name__ == "__main__":
    unittest.main()
