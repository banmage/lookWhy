from pathlib import Path
import sys
import tempfile
import unittest

from reportlab.pdfgen import canvas

from leleby_ssir.pdf_extractor import extract_pdf_to_csm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from mineru_full_standard import _detect_broken_text_layer  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
