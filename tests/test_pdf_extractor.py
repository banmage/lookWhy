from pathlib import Path
import json
import sys
import tempfile
import unittest

from reportlab.pdfgen import canvas

from leleby_ssir.pdf_extractor import extract_pdf_to_csm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from mineru_full_standard import _detect_broken_text_layer, _latin_loss_check, _restore_ellipsis_lines  # noqa: E402


class RestoreEllipsisTests(unittest.TestCase):
    """merge 阶段从源 PDF 文本层恢复 OCR 丢弃的纯省略号行（GEN-092 后验补盲）。"""

    @staticmethod
    def _make_pdf(directory: Path, pages: list[list[tuple[float, float, str]]]) -> Path:
        import pymupdf

        path = directory / "synthetic.pdf"
        document = pymupdf.open()
        for page_lines in pages:
            page = document.new_page()
            for x, y, text in page_lines:
                # 内置 CJK 字体（helv 无汉字/省略号字形，抽取会变成 ·）。
                page.insert_text((x, y), text, fontsize=10, fontname="china-s")
        document.save(path)
        document.close()
        return path

    def test_body_ellipsis_inserted_before_next_clause_anchor(self) -> None:
        # 5.7.1 a) 之后、5.8 标题之前的纯"……"行被 OCR 丢弃 → 从文本层恢复。
        with tempfile.TemporaryDirectory() as directory:
            pdf = self._make_pdf(Path(directory), [
                [
                    (72, 100, "5.7.1 基础苗培养的操作如下："),
                    (92, 115, "a）在超净工作台上切段。"),
                    (72, 130, "……"),
                    (72, 150, "5.8 扩繁"),
                ],
            ])
            raw = "## 5.7 基础苗培养\n\n5.7.1 基础苗培养的操作如下：\n\na）在超净工作台上切段。\n\n## 5.8扩繁\n"
            out = _restore_ellipsis_lines(raw, pdf)
            self.assertIn("……", out)
            self.assertLess(out.index("a）在超净工作台上切段。"), out.index("……"))
            self.assertLess(out.index("……"), out.index("## 5.8扩繁"))

    def test_table_cell_ellipsis_rebuilt_with_br_lines(self) -> None:
        # 表1 型：单元格被 OCR 压成单行，文本层保留 术语和定义/……/程序确立/
        # ……/规范性附录 的逐行结构 → 恢复为 <br> 连接（渲染端转 <br/>）。
        with tempfile.TemporaryDirectory() as directory:
            pdf = self._make_pdf(Path(directory), [
                [
                    (100, 200, "术语和定义"),
                    (100, 210, "……"),
                    (100, 220, "程序确立"),
                    (100, 230, "……"),
                    (100, 240, "规范性附录"),
                    (300, 205, "条文"),
                    (300, 215, "图表"),
                    (300, 225, "注脚注"),
                    (300, 235, "文字"),
                ],
            ])
            raw = (
                "| 要素类型 | 要素的编排 | 表述形式 |\n"
                "| --- | --- | --- |\n"
                "| 规范性技术要素 | 术语和定义……程序确立……规范性附录 | 条文图表注脚注 |\n"
            )
            out = _restore_ellipsis_lines(raw, pdf)
            self.assertIn("术语和定义<br>……<br>程序确立<br>……<br>规范性附录", out)


class PdfExtractorTests(unittest.TestCase):
    def test_pymupdf_backend_writes_csm_and_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "sample.pdf"
            pdf = canvas.Canvas(str(source))
            pdf.drawString(72, 760, "GB/T 9999-2026")
            pdf.drawString(72, 730, "示例产品标准")
            pdf.showPage()
            pdf.save()
            output = root / "sample.csm.md"
            report = extract_pdf_to_csm(source, output, backend="pymupdf")
            self.assertEqual(report.backend, "pymupdf")
            self.assertEqual(report.page_count, 1)
            self.assertTrue(output.exists())
            self.assertTrue(Path(report.sidecar_file).exists())
            text = output.read_text(encoding="utf-8")
            self.assertIn("csm-version: \"1.0\"", text)
            self.assertIn("# GB/T 9999-2026", text)
            self.assertIn('ssir:block id="pdf-page-1"', text)


class StandardFilenameTests(unittest.TestCase):
    """命名方案（用户确认）：标准号斜杠一律转下划线（GB/T→GB_T 等）。"""

    def test_recommended_and_mandatory_national(self):
        from leleby_ssir.naming import standard_filename
        self.assertEqual(standard_filename("GB/T 15034-2012"), "GB_T_15034-2012")
        self.assertEqual(standard_filename("GB 15034-2012"), "GB_15034-2012")
        self.assertEqual(standard_filename("GB/Z 123-2020"), "GB_Z_123-2020")

    def test_industry_recommended_uses_t_suffix(self):
        from leleby_ssir.naming import standard_filename
        self.assertEqual(standard_filename("JB/T 14054-2021"), "JB_T_14054-2021")
        self.assertEqual(standard_filename("SJ/T 11859-2022"), "SJ_T_11859-2022")
        self.assertEqual(standard_filename("QC/T 1000-2021"), "QC_T_1000-2021")

    def test_local_enterprise_group(self):
        from leleby_ssir.naming import standard_filename
        self.assertEqual(standard_filename("DB11/T 1000-2020"), "DB11_T_1000-2020")
        self.assertEqual(standard_filename("Q/XKBZ 002—2026"), "Q_XKBZ_002-2026")
        self.assertEqual(standard_filename("T/CAS 501-2021"), "T_CAS_501-2021")

    def test_dot_in_sequence_number_is_kept(self):
        from leleby_ssir.naming import standard_filename
        self.assertEqual(standard_filename("GB/T 1.1-2020"), "GB_T_1.1-2020")
        self.assertEqual(standard_filename("GB/T 20001.10-2014"), "GB_T_20001.10-2014")

    def test_unparsable_returns_empty(self):
        from leleby_ssir.naming import standard_filename
        self.assertEqual(standard_filename(""), "")
        self.assertEqual(standard_filename("草案"), "")


class ArtifactIdTests(unittest.TestCase):
    """<STANDARD_ID>.<representation>.<ext> 文件名解析（右往左，ID 可含点号）。"""

    def test_artifact_id_strips_known_representation_suffixes(self):
        from leleby_ssir.naming import artifact_id
        self.assertEqual(artifact_id("GB_T_1.1-2020.canonical.md"), "GB_T_1.1-2020")
        self.assertEqual(artifact_id("GB_T_1.1-2020.ssir.json"), "GB_T_1.1-2020")
        self.assertEqual(artifact_id("Q_003.raw.md"), "Q_003")
        self.assertEqual(artifact_id("Q_003.render.md"), "Q_003")
        self.assertEqual(artifact_id("JB_T_14054-2021.render.pdf"), "JB_T_14054-2021")
        self.assertEqual(artifact_id("JB_T_14054-2021.render-report.json"), "JB_T_14054-2021")
        self.assertEqual(artifact_id("T_CAS_501-2021.semantic.ttl"), "T_CAS_501-2021")
        self.assertEqual(artifact_id("Q_003.csm.md"), "Q_003")  # 历史后缀兼容

    def test_report_path_lives_beside_artifact(self):
        from leleby_ssir.naming import report_path
        self.assertEqual(
            str(report_path("03_ssir/GB_T_1.1-2020.ssir.json", "parse-report")),
            "03_ssir/GB_T_1.1-2020.parse-report.json",
        )
        self.assertEqual(
            str(report_path("02_canonical/GB_T_1.1-2020.canonical.md", "normalize-report")),
            "02_canonical/GB_T_1.1-2020.normalize-report.json",
        )
        self.assertEqual(
            str(report_path("04_render/GB_T_1.1-2020.render.md", "roundtrip")),
            "04_render/GB_T_1.1-2020.roundtrip.json",
        )


class TextLayerQualityTests(unittest.TestCase):
    """文本层质量预检（2026-08-31）：半坏文本层（孤立 "4."/"2." 行、截断标准号
    "GB/T2423."）会让 MinerU auto/txt 抽取丢点丢数字，应强制走 OCR。"""

    @staticmethod
    def _make_pdf(path: Path, lines: list[str]) -> None:
        pdf = canvas.Canvas(str(path))
        y = 780
        for line in lines:
            pdf.drawString(72, y, line)
            y -= 14
            if y < 40:
                pdf.showPage()
                y = 780
        pdf.showPage()
        pdf.save()

    def test_damaged_text_layer_is_detected(self) -> None:
        # 模拟 GB_T_43726-2024 文本层：条号被拆成孤立 "4."/"2." 行、
        # 标准号截断成 "GB/T2423."，且混有正常正文。
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "damaged.pdf"
            lines = ["1 范围", "本文件规定了电机的技术要求。"]
            lines += ["4.", "2.", "2 机座号"] * 12   # 36 条孤立点行
            lines += ["GB/T2423.", "GB/T7345."] * 2  # 4 条截断标准号
            self._make_pdf(source, lines)
            reason = _detect_broken_text_layer(source)
            self.assertIsNotNone(reason)
            self.assertIn("orphaned number-dot lines", reason)

    def test_healthy_text_layer_is_not_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "healthy.pdf"
            self._make_pdf(
                source,
                [
                    "GB/T 1.1—2020 标准化工作导则",
                    "1 范围",
                    "4.2.1 型号结构",
                    "本文件规定了电机的技术要求。",
                    "GB/T 2423.16—2008 环境试验",
                ],
            )
            self.assertIsNone(_detect_broken_text_layer(source))

    def test_scanned_pdf_without_text_layer_is_not_detected(self) -> None:
        # 无文本层的扫描件不误报：MinerU auto 本就会对空白文本层走 OCR。
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "blank.pdf"
            pdf = canvas.Canvas(str(source))
            pdf.showPage()
            pdf.save()
            self.assertIsNone(_detect_broken_text_layer(source))

    def test_latin_loss_detected_when_raw_drops_standard_numbers(self) -> None:
        # 回归（2026-08-31，GB_T_15835-2011/GB_T_23132-2024 类）：PDF 文本层
        # **健康**（pymupdf 读得到 "GB/T1.1—2009"），但 MinerU txt/auto 抽取
        # 按字体编码问题整段丢弃拉丁字母与数字（"GB/T 1.1—2020" → "/ — "）。
        # GEN-092 预检（看文本层损坏特征）覆盖不到这类，须在抽取后对比文本层
        # 与 raw 的标准号提及数。文本层 ≥5 且 raw 不足一半 → 判定丢失。
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "healthy-but-dropped.pdf"
            self._make_pdf(
                source,
                [
                    "本标准按照GB/T1.1—2009给出的规则起草。",
                    "本标准代替GB/T15835—1995《出版物上数字用法的规定》。",
                    "GB/T 7408 数据元和交换格式 信息交换 日期和时间表示法",
                    "GB/T 15835—2011 出版物上数字用法",
                ]
                * 3,  # 文本层 12 次提及
            )
            # raw 只保留了少量（模拟抽取丢拉丁："/ —" 是特征残迹）。
            raw_markdowns = ["本标准按照 / — 给出的规则起草。", "本标准代替 / — 的规定。"]
            reason = _latin_loss_check(raw_markdowns, source)
            self.assertIsNotNone(reason)
            self.assertIn("Latin/digit loss", reason)

    def test_latin_loss_not_detected_when_raw_keeps_standard_numbers(self) -> None:
        # 健康文档（GB_T_1.1-2020 类）：文本层与 raw 都密布标准号，不误报。
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "healthy-kept.pdf"
            self._make_pdf(
                source,
                [
                    "GB/T 1.1—2020 标准化工作导则",
                    "GB/T 20001.5—2017 标准编写规则",
                    "GB/T 15835—2011 出版物上数字用法",
                    "GB/T 2423.16—2008 环境试验",
                ]
                * 3,
            )
            raw_markdowns = [
                "GB/T 1.1—2020 标准化工作导则",
                "GB/T 20001.5—2017 标准编写规则",
                "GB/T 15835—2011 出版物上数字用法",
                "GB/T 2423.16—2008 环境试验",
            ] * 3  # 健康抽取 raw 与文本层同密度（12 次）
            self.assertIsNone(_latin_loss_check(raw_markdowns, source))

    def test_latin_loss_not_detected_when_text_layer_is_sparse(self) -> None:
        # 扫描件/无标准号的文档：文本层提及数不足 5，不判定（不强制 OCR）。
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sparse.pdf"
            self._make_pdf(source, ["1 范围", "本文件规定了技术要求。"])
            self.assertIsNone(_latin_loss_check(["1 范围", "本文件规定了技术要求。"], source))


class FigureSourceSizeStampTests(unittest.TestCase):
    """图尺寸打标（2026-09-01，GEN-076 落实）：_stamp_figure_source_sizes 从源
    PDF 版面矩形还原原图尺寸，供渲染端按原比例显示（GB_T_23132-2024 图/表2 型）。"""

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.assets = self.root / "doc" / "assets" / "images"
        self.assets.mkdir(parents=True)

    def tearDown(self) -> None:
        self.directory.cleanup()

    @staticmethod
    def _png(path: Path, size: tuple[int, int], color: tuple[int, int, int]) -> None:
        from PIL import Image
        Image.new("RGB", size, color).save(path)

    def test_figure_and_table_cell_sizes_stamped_from_source_pdf(self) -> None:
        # 布局：第 1 页封面徽标 110x55（高 < 100pt，不参与匹配）；第 2 页
        # 内容图 W 100x50（宽高比 2.0，与徽标同宽高比——若不排除徽标会误配）、
        # S 100x100、干扰矩形 200x100。SSIR 放在 03_ssir/ 子目录、资产在文档根
        # assets/——验证祖先目录解析（此前只按 ssir 同目录解析，所有图都拿不到
        # 尺寸）。D（宽高比 2.667）无匹配矩形 → 密度回退。
        from mineru_full_standard import _stamp_figure_source_sizes
        import fitz

        img_w = self.assets / "img_w.png"
        img_s = self.assets / "img_s.png"
        img_d = self.assets / "img_d.png"
        img_t = self.assets / "img_t.png"
        self._png(img_w, (280, 140), (200, 30, 30))   # aspect 2.0, density 2.8
        self._png(img_s, (280, 280), (30, 200, 30))   # aspect 1.0
        self._png(img_d, (400, 150), (30, 30, 200))   # aspect 2.667, 无匹配矩形
        self._png(img_t, (200, 200), (200, 200, 30))  # aspect 1.0, 表单元格图
        source = self.root / "source.pdf"
        doc = fitz.open()
        doc.new_page(width=595, height=842)
        doc[0].insert_image(fitz.Rect(400, 30, 510, 85), filename=str(img_w))  # 封面徽标
        doc.new_page(width=595, height=842)
        doc[1].insert_image(fitz.Rect(100, 500, 200, 550), filename=str(img_w))  # W: 100x50
        doc[1].insert_image(fitz.Rect(250, 500, 350, 600), filename=str(img_s))  # S: 100x100
        doc[1].insert_image(fitz.Rect(100, 300, 300, 400), filename=str(img_w))  # 干扰 200x100
        doc[1].insert_image(fitz.Rect(400, 300, 500, 400), filename=str(img_t))  # T: 100x100 表中图
        doc.save(source)
        doc.close()

        ssir_dir = self.root / "doc" / "03_ssir"
        ssir_dir.mkdir(parents=True)
        ssir = ssir_dir / "doc.ssir.json"
        ssir.write_text(json.dumps({
            "metadata": {"common": {"title": "T"}, "standard": {"standardNumber": "GB/T 1—2026"}},
            "figures": [
                {"id": "f-001", "assetRef": "assets/images/img_w.png"},
                {"id": "f-002", "assetRef": "assets/images/img_s.png"},
                {"id": "f-003", "assetRef": "assets/images/img_d.png"},
            ],
            "tables": [
                {"id": "t-001", "rowCount": 2, "colCount": 2, "sourceAnchors": [{"id": "a1", "anchorType": "markdown", "sourceFileId": "s1", "markdownStartLine": 1, "markdownEndLine": 1}],
                 "rows": [{"rowIndex": 0, "cells": [{"id": "c1", "rowIndex": 0, "colIndex": 0, "text": "a"}, {"id": "c2", "rowIndex": 0, "colIndex": 1, "text": "b"}]},
                          {"rowIndex": 1, "cells": [{"id": "c3", "rowIndex": 1, "colIndex": 0, "text": "![](assets/images/img_t.png)"}]}]},
            ],
        }, ensure_ascii=False), encoding="utf-8")
        _stamp_figure_source_sizes(ssir, source)

        data = json.loads(ssir.read_text(encoding="utf-8"))
        by_ref = {fig["assetRef"].split("/")[-1]: fig for fig in data["figures"]}
        # W 匹配自己的矩形 100x50（而非封面徽标 110x55——徽标被排除）。
        self.assertEqual(by_ref["img_w.png"]["sourceWidth"], 100.0)
        self.assertEqual(by_ref["img_w.png"]["sourceHeight"], 50.0)
        # S 匹配 100x100。
        self.assertEqual(by_ref["img_s.png"]["sourceWidth"], 100.0)
        self.assertEqual(by_ref["img_s.png"]["sourceHeight"], 100.0)
        # D 无匹配矩形 → 按文档像素密度（2.8）回退：400/2.8 x 150/2.8。
        self.assertAlmostEqual(by_ref["img_d.png"]["sourceWidth"], 400 / 2.8, delta=1.0)
        self.assertAlmostEqual(by_ref["img_d.png"]["sourceHeight"], 150 / 2.8, delta=1.0)
        # 表格单元格内图（GBT-X02 表中图）尺寸写入 cellImageSizes。
        table = data["tables"][0]
        self.assertEqual(table["cellImageSizes"]["assets/images/img_t.png"], [100.0, 100.0])


if __name__ == "__main__":
    unittest.main()
