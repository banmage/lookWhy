"""术语条目版式与归一（GB/T 1.1-2020 8.7.3.1、10.3.5、附录F 表F.1 序号22—24）。

背景（2026-09-11，用户报告）：GB_T_1.1-2020 第 3 章里 3.1.2 起的术语条目被渲染成
「3.1.2 标准 standard」**一行**（条目编号与术语并排），只有 3.1.1（抽取成两个段落
的那一条）是编号单独一行——同一要素内两种形态不一致，且都不符合 10.3.5
（条目编号顶格单独占一行、术语与英文对应词另起一行空两个汉字、均五号黑体、
上下无空行）。修复分两层：

- parser（CSM-OCR-007）：段落形态（``3.1.1`` + ``标准化文件　standardizing
  document``）并入编号标题，与标题形态同形；术语行中英文间隙归一为 U+3000；
- 渲染端（pdf_renderer `_term_entry_flowables` / docx_renderer `_term_entry`）：
  术语条目按两行版式排版，编号行顶格、术语行空两个汉字。

近负例：GB_3100-2026「5.2 具有专门名称的SI导出单位」这类编号条款标题里也带拉丁，
但不是术语条目（拉丁段后面还接汉字），必须仍按普通标题单行排版。
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

_HEADER = (
    "---\n"
    "csm-version: 1.0\n"
    "document-type: standard\n"
    "document-identifier: GB/T 1.1-2020\n"
    "standard-number: GB/T 1.1-2020\n"
    "title: 标准化工作导则 第1部分：标准化文件的结构和起草规则\n"
    "language: zh-CN\n"
    "---\n\n"
)

# 标题形态（3.1.2，抽取成两条同级标题）与段落形态（3.1.1）并存的第 3 章。
CANON = _HEADER + """# 标准化工作导则

## 3 术语和定义

GB/T 20000.1界定的以及下列术语和定义适用于本文件。

### 3.1 文件

3.1.1

标准化文件 standardizing document

通过标准化活动制定的文件。

## 3.1.2

## 标准 standard

通过标准化活动，按照规定的程序经协商一致制定，供共同使用和重复使用的文件。

## 4 文件的类别

### 4.1 概述

4.1.1 按照标准化对象可以将标准划分为不同类别。

### 5.2 具有专门名称的SI导出单位

本文件规定了导出单位的用法。
"""


def _build_ssir(directory: Path) -> Path:
    from leleby_ssir.builder import SSIRBuilder
    from leleby_ssir.parser import CSMParser

    source = directory / "t.canonical.md"
    source.write_text(CANON, encoding="utf-8")
    ssir = directory / "t.ssir.json"
    ssir.write_text(
        json.dumps(SSIRBuilder().build(CSMParser().read(str(source))), ensure_ascii=False),
        encoding="utf-8",
    )
    return ssir


class TermEntryParserTests(unittest.TestCase):
    """CSM-OCR-007：两种抽取形态归一为同一术语节点；术语行间隙为 U+3000。"""

    @classmethod
    def setUpClass(cls) -> None:
        from leleby_ssir.parser import CSMParser

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "t.canonical.md"
            source.write_text(CANON, encoding="utf-8")
            cls.document = CSMParser().read(source)

    def _heading_titles(self) -> dict[str, str]:
        import re

        return {
            re.match(r"^([\d.]+)", block.text.strip()).group(1): block.text.strip()
            for block in self.document.blocks
            if block.kind == "heading" and re.match(r"^[\d.]+ ", block.text.strip())
        }

    def test_paragraph_shaped_term_entry_is_promoted_to_its_own_heading(self) -> None:
        titles = self._heading_titles()
        self.assertEqual(titles.get("3.1.1"), "3.1.1 标准化文件\u3000standardizing document")

    def test_heading_shaped_term_entry_gets_the_full_width_gap(self) -> None:
        titles = self._heading_titles()
        # 标题形态（## 3.1.2 + ## 标准 standard）合并后中英文之间空一个汉字。
        self.assertEqual(titles.get("3.1.2"), "3.1.2 标准\u3000standard")

    def test_non_term_clause_title_is_left_alone(self) -> None:
        titles = self._heading_titles()
        # 拉丁后面还接汉字（SI导出单位）→ 不是术语条目，标题原样。
        self.assertEqual(titles.get("5.2"), "5.2 具有专门名称的SI导出单位")


class TermEntryPdfLayoutTests(unittest.TestCase):
    """渲染端版式：编号行顶格、术语行空两个汉字，两行同为黑体五号。"""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            import pymupdf  # noqa: F401
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("pymupdf unavailable")
        font = ROOT / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font.is_file():  # pragma: no cover
            raise unittest.SkipTest("body font asset missing")
        import pymupdf

        from leleby_ssir.pdf_renderer import render_pdf_file

        cls.tempdir = tempfile.TemporaryDirectory()
        directory = Path(cls.tempdir.name)
        ssir = _build_ssir(directory)
        target = directory / "t.pdf"
        render_pdf_file(str(ssir), str(target), toc_depth=None)
        cls.document = pymupdf.open(str(target))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.document.close()
        cls.tempdir.cleanup()

    def _lines(self) -> list[tuple[str, float, float, list[tuple[str, str]]]]:
        rows = []
        for page in self.document:
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    text = "".join(span["text"] for span in line["spans"])
                    rows.append((text, line["bbox"][0], line["bbox"][1],
                                 [(span["font"], span["text"]) for span in line["spans"]]))
        return rows

    def test_number_and_term_are_on_separate_lines(self) -> None:
        rows = self._lines()
        index = next(
            (i for i, (text, _x0, _y, _spans) in enumerate(rows) if text.strip() == "3.1.2"),
            None,
        )
        self.assertIsNotNone(index, [row[0] for row in rows][:80])
        number_x, number_y = rows[index][1], rows[index][2]
        term_text, term_x, term_y, _spans = rows[index + 1]
        # 术语行紧接编号行：行文本为「标准 + 间隙字形 + standard」。
        self.assertIn("标准", term_text)
        self.assertIn("standard", term_text)
        # 条目编号顶格（版心左边 85.4pt），术语行空两个汉字（+2×10.5pt = 106.4pt）。
        self.assertAlmostEqual(number_x, 85.4, delta=0.5)
        self.assertAlmostEqual(term_x, 106.4, delta=0.5)
        # 术语行紧跟编号行（上下无空行）：行距 = 正文行距 18pt。
        self.assertAlmostEqual(term_y - number_y, 18.0, delta=1.5)

    def test_term_lines_use_hei_font(self) -> None:
        for text, _x0, _y, spans in self._lines():
            if text.strip() in {"3.1.2", "3.1.1"} or text.startswith(("标准", "标准化文件")):
                fonts = {font for font, span_text in spans if span_text.strip()}
                self.assertTrue(fonts, text)
                for font in fonts:
                    self.assertTrue(font.startswith("WenQuanYiZenHei"), f"{text!r} 非黑体: {font}")

    def test_term_gap_renders_as_one_em_white_glyph(self) -> None:
        # U+3000 由 _markup 换成恰好 1em 的白色汉字字隙（CSM-OCR-003）：文本层里
        # 该间隙是一个独立的「中」字形 span，而不是全角空格字符。
        rows = self._lines()
        index = next(
            (i for i, (text, _x0, _y, _spans) in enumerate(rows) if text.strip() == "3.1.2"),
            None,
        )
        self.assertIsNotNone(index, [row[0] for row in rows][:80])
        text, _x0, _y, spans = rows[index + 1]
        self.assertIn("standard", text)
        self.assertNotIn("\u3000", text)
        gap_spans = [font for font, span_text in spans if span_text.strip() == "中"]
        self.assertEqual(len(gap_spans), 1, spans)
        self.assertTrue(gap_spans[0].startswith("WenQuanYiZenHei"), spans)

    def test_plain_clause_with_latin_stays_on_one_line(self) -> None:
        rows = [(text, x0) for text, x0, _y, _ in self._lines() if text.strip().startswith("5.2")]
        self.assertTrue(rows, [row[0] for row in self._lines()][:80])
        for text, x0 in rows:
            self.assertIn("具有专门名称的SI导出单位", text.replace("\u3000", ""))
            self.assertAlmostEqual(x0, 85.4, delta=0.5)


class TermEntryTocLabelTests(unittest.TestCase):
    """目次行必须带出术语（用户可见症状，2026-09-15 GB_3100-2026）。

    裸术语节（条目编号 2 段，如 3.13）不满足 `_term_entry_text` 的「≥3 段编号」判据，
    目次标签只能由 builder 写入的 term 元数据合成——term/englishTerm 一丢，目次行就只剩
    条目编号（3.8/3.13 曾如此）。本用例走完整链路（canonical → SSIR → PDF 目次文本层）。
    """

    CANON = _HEADER.replace(
        "title: 标准化工作导则 第1部分：标准化文件的结构和起草规则",
        "title: 国际单位制及其应用",
    ) + """# 国际单位制及其应用

## 目次

1 范围....1
3 术语和定义....1

## 1 范围

本文件规定了国际单位制及其应用。

## 3 术语和定义

下列术语和定义适用于本文件。

### 3.8

国际单位制\u3000International System of Units, SI

由国际计量大会（CGPM）批准采用的基于国际量制的单位制。

### 3.13

SI词头\u3000SI prefix

与SI单位名称或符号结合，用以形成该单位十进倍数单位或分数单位的词头。

## 4 国际单位制的构成

4.1 国际单位制由SI基本单位和SI导出单位组成。
"""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            import pymupdf  # noqa: F401
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("pymupdf unavailable")
        font = ROOT / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font.is_file():  # pragma: no cover
            raise unittest.SkipTest("body font asset missing")
        import pymupdf

        from leleby_ssir.builder import SSIRBuilder
        from leleby_ssir.parser import CSMParser
        from leleby_ssir.pdf_renderer import render_pdf_file

        cls.tempdir = tempfile.TemporaryDirectory()
        directory = Path(cls.tempdir.name)
        source = directory / "t.canonical.md"
        source.write_text(cls.CANON, encoding="utf-8")
        ssir = directory / "t.ssir.json"
        ssir.write_text(
            json.dumps(SSIRBuilder().build(CSMParser().read(str(source))), ensure_ascii=False),
            encoding="utf-8",
        )
        target = directory / "t.pdf"
        render_pdf_file(str(ssir), str(target), toc_depth=2)
        cls.document = pymupdf.open(str(target))
        toc_pages = [
            page for page in cls.document
            if "目 次" in page.get_text() or "\n目 次" in page.get_text()
        ]
        cls.toc_text = "\n".join(page.get_text() for page in toc_pages) if toc_pages else ""

    @classmethod
    def tearDownClass(cls) -> None:
        cls.document.close()
        cls.tempdir.cleanup()

    def test_term_rows_carry_the_chinese_term(self) -> None:
        for label in ("3.8\u3000国际单位制", "3.13\u3000SI词头"):
            row = next((line for line in self.toc_text.splitlines() if line.startswith(label)), None)
            self.assertIsNotNone(row, (label, self.toc_text))
            # 行里必须有页码（点线连接），即不是半截标签。
            self.assertTrue(row.rsplit(".", 1)[-1].strip().isdigit(), row)

    def test_no_term_row_is_a_bare_clause_number(self) -> None:
        # 反例守卫：目次里不得出现「3.8」这类只有条目编号、没有术语的行。
        rows = [line for line in self.toc_text.splitlines() if line.strip()]
        bare = [line for line in rows if line.strip().rstrip(".·–—- ") in {"3.8", "3.13"}]
        self.assertFalse(bare, rows)


class TermEntryDocxLayoutTests(unittest.TestCase):
    """docx 孪生：编号行/术语行各自成段，术语行左侧空两个汉字（420 twips）。"""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            import docx  # noqa: F401
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("python-docx unavailable")
        from leleby_ssir.docx_renderer import render_docx_file

        cls.tempdir = tempfile.TemporaryDirectory()
        directory = Path(cls.tempdir.name)
        ssir = _build_ssir(directory)
        target = directory / "t.docx"
        render_docx_file(str(ssir), str(target), toc_depth=None)
        import zipfile

        with zipfile.ZipFile(target) as archive:
            cls.document_xml = archive.read("word/document.xml").decode("utf-8")
            cls.styles_xml = archive.read("word/styles.xml").decode("utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tempdir.cleanup()

    def test_number_and_term_are_separate_styled_paragraphs(self) -> None:
        import re

        paragraphs = re.findall(r"<w:p[ >].*?</w:p>", self.document_xml, re.S)
        texts = [
            ("".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S)), p)
            for p in paragraphs
        ]
        numbered = [(t, p) for t, p in texts if t.strip() == "3.1.2"]
        self.assertTrue(numbered, [t for t, _ in texts][:60])
        self.assertIn("SSIRTermNumber", numbered[0][1])

        index = texts.index(numbered[0])
        term_text, term_paragraph = texts[index + 1]
        self.assertEqual(term_text.strip(), "标准\u3000standard")
        self.assertIn("SSIRTermTitle", term_paragraph)
        self.assertIn('w:eastAsia="黑体"', term_paragraph)

    def test_term_title_style_indents_two_han(self) -> None:
        import re

        style = re.search(r'<w:style [^>]*w:styleId="SSIRTermTitle".*?</w:style>', self.styles_xml, re.S)
        self.assertIsNotNone(style, self.styles_xml[:2000])
        indent = re.search(r'<w:ind w:left="(\d+)"', style.group(0))
        self.assertIsNotNone(indent, style.group(0))
        # 2 汉字 × 10.5pt = 21pt = 420 twips
        self.assertEqual(indent.group(1), "420")


if __name__ == "__main__":
    unittest.main()
