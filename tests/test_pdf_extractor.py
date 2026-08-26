from pathlib import Path
import tempfile
import unittest

from reportlab.pdfgen import canvas

from leleby_ssir.pdf_extractor import extract_pdf_to_csm


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
    """命名方案（用户确认）：/T、/Z 并入代号，企业/团体斜杠转下划线。"""

    def test_recommended_and_mandatory_national(self):
        from leleby_ssir.naming import standard_filename
        self.assertEqual(standard_filename("GB/T 15034-2012"), "GBT_15034-2012")
        self.assertEqual(standard_filename("GB 15034-2012"), "GB_15034-2012")
        self.assertEqual(standard_filename("GB/Z 123-2020"), "GBZ_123-2020")

    def test_industry_recommended_uses_t_suffix(self):
        from leleby_ssir.naming import standard_filename
        self.assertEqual(standard_filename("JB/T 14054-2021"), "JBT_14054-2021")
        self.assertEqual(standard_filename("SJ/T 11859-2022"), "SJT_11859-2022")
        self.assertEqual(standard_filename("QC/T 1000-2021"), "QCT_1000-2021")

    def test_local_enterprise_group(self):
        from leleby_ssir.naming import standard_filename
        self.assertEqual(standard_filename("DB11/T 1000-2020"), "DB11T_1000-2020")
        self.assertEqual(standard_filename("Q/XKBZ 002—2026"), "Q_XKBZ_002-2026")
        self.assertEqual(standard_filename("T/CAS 501-2021"), "T_CAS_501-2021")

    def test_dot_in_sequence_number_is_kept(self):
        from leleby_ssir.naming import standard_filename
        self.assertEqual(standard_filename("GB/T 1.1-2020"), "GBT_1.1-2020")
        self.assertEqual(standard_filename("GB/T 20001.10-2014"), "GBT_20001.10-2014")

    def test_unparsable_returns_empty(self):
        from leleby_ssir.naming import standard_filename
        self.assertEqual(standard_filename(""), "")
        self.assertEqual(standard_filename("草案"), "")


class ArtifactIdTests(unittest.TestCase):
    """<STANDARD_ID>.<representation>.<ext> 文件名解析（右往左，ID 可含点号）。"""

    def test_artifact_id_strips_known_representation_suffixes(self):
        from leleby_ssir.naming import artifact_id
        self.assertEqual(artifact_id("GBT_1.1-2020.canonical.md"), "GBT_1.1-2020")
        self.assertEqual(artifact_id("GBT_1.1-2020.ssir.json"), "GBT_1.1-2020")
        self.assertEqual(artifact_id("Q_003.raw.md"), "Q_003")
        self.assertEqual(artifact_id("Q_003.render.md"), "Q_003")
        self.assertEqual(artifact_id("JBT_14054-2021.render.pdf"), "JBT_14054-2021")
        self.assertEqual(artifact_id("JBT_14054-2021.render-report.json"), "JBT_14054-2021")
        self.assertEqual(artifact_id("T_CAS_501-2021.semantic.ttl"), "T_CAS_501-2021")
        self.assertEqual(artifact_id("Q_003.csm.md"), "Q_003")  # 历史后缀兼容

    def test_report_path_lives_beside_artifact(self):
        from leleby_ssir.naming import report_path
        self.assertEqual(
            str(report_path("03_ssir/GBT_1.1-2020.ssir.json", "parse-report")),
            "03_ssir/GBT_1.1-2020.parse-report.json",
        )
        self.assertEqual(
            str(report_path("02_canonical/GBT_1.1-2020.canonical.md", "normalize-report")),
            "02_canonical/GBT_1.1-2020.normalize-report.json",
        )
        self.assertEqual(
            str(report_path("04_render/GBT_1.1-2020.render.md", "roundtrip")),
            "04_render/GBT_1.1-2020.roundtrip.json",
        )


if __name__ == "__main__":
    unittest.main()
