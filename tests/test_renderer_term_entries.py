"""术语条目版式与归一（GB/T 1.1-2020 8.7.3.1、10.3.5、附录F 表F.1 序号22—24）。

背景（2026-09-11，用户报告）：GB_T_1.1-2020 第 3 章里 3.1.2 起的术语条目被渲染成
「3.1.2 标准 standard」**一行**（条目编号与术语并排），只有 3.1.1（抽取成两个段落
的那一条）是编号单独一行——同一要素内两种形态不一致，且都不符合 10.3.5
（条目编号顶格单独占一行、术语与英文对应词另起一行空两个汉字、均五号黑体、
上下无空行）。修复分两层：

- parser（CSM-OCR-007）：段落形态（``3.1.1`` + ``标准化文件　standardizing
  document``）并入编号标题，与标题形态同形；术语行中英文间隙归一为 U+3000；
- 渲染端（pdf_renderer `_term_entry_flowables`）：
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


class TermEntryTocExclusionTests(unittest.TestCase):
    """术语条目不入目次（GB/T 1.1-2020 8.2.2：目次中不应列出「术语和定义」中的条目编号和术语）。

    2026-09-15 的 GB_3100-2026 症状是「目次出现只有条目编号、没有术语的行」——根因是
    2 段编号的术语条目没被识别成术语条目（`_term_entry_text` 当时要求编号 ≥3 段），于是
    绕过 `_toc_nodes` 的排除判据漏进目次；当时给了一个「标签补术语」的补丁。本轮把判据
    与 builder 配对的 term/englishTerm 对齐（同一判据也用于渲染端加黑）后，这类条目同样
    被排除，症状从根上消失。本用例走完整链路（canonical → SSIR → PDF 目次文本层）。
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

### 4.2 单位制的构成

国际单位制由SI基本单位和SI导出单位组成。
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

    def _rows(self) -> list[str]:
        return [line.strip() for line in self.toc_text.splitlines() if line.strip()]

    def test_standard_toc_still_lists_clauses(self) -> None:
        # 正向对照：排除只针对术语条目，普通条（4.2）照常入目次。
        rows = [line for line in self._rows() if line.startswith("4.2")]
        self.assertTrue(rows, self._rows())
        self.assertIn("单位制的构成", rows[0])

    def test_term_entries_are_not_listed_in_toc(self) -> None:
        for number in ("3.8", "3.13"):
            hits = [line for line in self._rows() if line.startswith(number)]
            self.assertFalse(hits, (number, self._rows()))

    def test_no_toc_row_is_a_bare_clause_number(self) -> None:
        # 反例守卫：目次里不得出现「3.8」这类只有条目编号、没有术语的行。
        bare = [line for line in self._rows() if line.rstrip(".·–—- ") in {"3.8", "3.13"}]
        self.assertFalse(bare, self._rows())

class TermEntryMixedFormParserTests(unittest.TestCase):
    """混合形态（2026-09-23，GB_T_5171.1-2014 用户报告）：编号抽成标题 + 术语行是段落。

    该标准第 3 章的术语条目是「### 3.1」（标题，text 只剩编号）后跟段落形态的术语行
    ——既不是「标题+标题」也不是「段落+段落」，两条既有判据都不覆盖，术语行于是留在正文里：
    SSIR 节点 title 为空（term/englishTerm 虽已配对），渲染端认不出术语条目，术语的中英文
    标题按正文排（不加黑、不单独占行）。归一后与其它形态同形：标题 = 「3.1 术语　english」。
    判据按编号段数分档：**「术语和定义」要素内不限段数**（该标准按 3.1/3.2 两段编号列术语），
    要素外维持「≥3 段」。
    """

    CANON = _HEADER.replace(
        "title: 标准化工作导则 第1部分：标准化文件的结构和起草规则",
        "title: 单速三相异步电动机技术条件",
    ) + """# 单速三相异步电动机技术条件

## 3 术语和定义

下列术语和定义适用于本文件。

### 3.1

无刷直流电动机\u3000brushless direct current motor

没有电刷和机械换向器，用电子换向的电动机。

### 3.2

## 步进电动机 stepper motor

## 4 检验规则

### 4.1

基本要求 basic requirement

本文件规定的检验按本文件执行。
"""

    @classmethod
    def setUpClass(cls) -> None:
        from leleby_ssir.parser import CSMParser

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "t.canonical.md"
            source.write_text(cls.CANON, encoding="utf-8")
            cls.document = CSMParser().read(source)

    def _headings(self) -> dict[str, str]:
        import re

        return {
            re.match(r"^([\d.]+)", block.text.strip()).group(1): block.text.strip()
            for block in self.document.blocks
            if block.kind == "heading" and re.match(r"^[\d.]+ \S", block.text.strip())
        }

    def test_number_heading_and_term_paragraph_are_merged(self) -> None:
        headings = self._headings()
        self.assertEqual(
            headings.get("3.1"), "3.1 无刷直流电动机\u3000brushless direct current motor"
        )

    def test_term_line_no_longer_stays_in_the_body(self) -> None:
        texts = [block.text.strip() for block in self.document.blocks]
        term_lines = [text for text in texts if "brushless" in text]
        self.assertEqual(term_lines, ["3.1 无刷直流电动机\u3000brushless direct current motor"])
        # 定义段照旧留在正文。
        self.assertIn("没有电刷和机械换向器，用电子换向的电动机。", texts)

    def test_shallow_heading_form_inside_terms_chapter_is_merged(self) -> None:
        # 标题形态在「术语和定义」内同样不限段数（3.2 两段编号）。
        self.assertEqual(self._headings().get("3.2"), "3.2 步进电动机\u3000stepper motor")

    def test_shallow_number_outside_terms_chapter_is_left_alone(self) -> None:
        # 要素外维持 ≥3 段判据：4.1 的「基本要求 basic requirement」不是术语条目。
        headings = [block.text.strip() for block in self.document.blocks if block.kind == "heading"]
        self.assertIn("4.1", headings)
        texts = [block.text.strip() for block in self.document.blocks]
        self.assertIn("基本要求 basic requirement", texts)


class TermEntryShallowNumberPdfTests(unittest.TestCase):
    """渲染端：两段编号的术语条目同样「编号行顶格 + 术语行空两字、同为黑体」（2026-09-23）。

    判据改用 builder 配对的 term/englishTerm（只在「术语和定义」内配对），不再要求编号 ≥3 段
    —— GB/T 5171.1-2014 按 3.1/3.2 两段编号列术语，渲染端原先认不出，术语标题不加黑。
    """

    CANON = TermEntryMixedFormParserTests.CANON

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

    def test_shallow_term_entry_renders_number_then_hei_term_line(self) -> None:
        rows = self._lines()
        index = next((i for i, row in enumerate(rows) if row[0].strip() == "3.1"), None)
        self.assertIsNotNone(index, [row[0] for row in rows][:60])
        number_x, number_y = rows[index][1], rows[index][2]
        term_text, term_x, term_y, spans = rows[index + 1]
        self.assertIn("无刷直流电动机", term_text)
        self.assertIn("brushless", term_text)
        self.assertAlmostEqual(number_x, 85.4, delta=0.5)  # 编号行顶格
        self.assertAlmostEqual(term_x, 106.4, delta=0.5)  # 术语行空两个汉字
        self.assertAlmostEqual(term_y - number_y, 18.0, delta=1.5)
        fonts = {font for font, span_text in spans if span_text.strip()}
        self.assertTrue(fonts, spans)
        for font in fonts:
            self.assertTrue(font.startswith("WenQuanYiZenHei"), f"{term_text!r} 非黑体: {font}")

    def test_term_line_is_not_duplicated_in_the_body(self) -> None:
        occurrences = [
            row for row in self._lines()
            if "无刷直流电动机" in row[0] or "brushless direct current motor" in row[0]
        ]
        self.assertEqual(len(occurrences), 1, [row[0] for row in occurrences])

    def test_definition_paragraph_stays_in_body_flow(self) -> None:
        # 定义段与术语行同缩进（术语条目三段版式：编号顶格、术语行/定义/来源空两字）——
        # 与既有产物一致（GB/T 1.1-2020 render.pdf 第 11 页：3.1.1 顶格 85.4、
        # 术语行与定义段均 106.4 起）。
        rows = [row for row in self._lines() if "没有电刷和机械换向器" in row[0]]
        self.assertTrue(rows, [row[0] for row in self._lines()][:60])
        self.assertAlmostEqual(rows[0][1], 106.4, delta=0.5)


if __name__ == "__main__":
    unittest.main()
