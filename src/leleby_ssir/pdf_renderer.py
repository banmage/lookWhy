"""Render a validated SSIR document as an A4 PDF standard draft."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from html import escape
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

from .validation import validate_ssir


DEFAULT_PROFILE = Path(__file__).resolve().parents[2] / "config" / "rendering" / "gb-t-1-1-2020.yaml"


@dataclass(slots=True)
class PDFRenderReport:
    input_file: str
    output_file: str
    profile_file: str
    profile_id: str
    font_file: str
    page_count: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        # 规则对应: GEN-076（渲染报告）——有目次时预检与最终构建各跑一次封面故事，
        # 占位 warning 去重后再写报告。
        warnings = list(dict.fromkeys(self.warnings))
        return {
            "inputFile": self.input_file,
            "outputFile": self.output_file,
            "profileFile": self.profile_file,
            "profileId": self.profile_id,
            "fontFile": self.font_file,
            "pageCount": self.page_count,
            "warnings": warnings,
        }

    def write_json(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_pdf(
    document: dict[str, Any],
    output: str | Path,
    *,
    profile_path: str | Path | None = None,
    input_file: str = "",
    toc_depth: int | None = 2,
) -> PDFRenderReport:
    """Render SSIR JSON to a text-searchable PDF using an embedded CJK font.

    规则对应: GEN-071（排版参数一律来自渲染 profile）、GEN-070（仅注册 TrueType 轮廓字体）、
    GEN-072（页底锚定元素由页回调绘制）、GEN-076（渲染完成自动生成报告）。
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import (
            Flowable,
            HRFlowable,
            Image,
            KeepTogether,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError("PDF rendering requires reportlab. Install project dependencies with: .venv/bin/pip install -e .") from exc

    validate_ssir(document)
    if toc_depth is not None and toc_depth < 1:
        raise ValueError("toc_depth must be a positive integer or None")
    profile_file = Path(profile_path or DEFAULT_PROFILE)
    profile = yaml.safe_load(profile_file.read_text(encoding="utf-8"))
    if not isinstance(profile, dict) or profile.get("kind") != "rendering-profile":
        raise ValueError(f"invalid rendering profile: {profile_file}")
    font_file = Path(profile["fonts"]["primary-file"])
    if not font_file.is_file():
        raise FileNotFoundError(f"CJK font not found: {font_file}")
    font_name = str(profile["fonts"].get("primary", "WenQuanYiZenHei"))
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font_name, str(font_file), subfontIndex=0))
    # GB/T 1.1 Appendix F distinguishes heading typefaces (Hei, the primary
    # font) from body typefaces (Song); fall back to the primary when the
    # profile does not declare a separate body font.
    body_font_file = Path(profile["fonts"].get("body-file") or font_file)
    if not body_font_file.is_file():
        raise FileNotFoundError(f"CJK body font not found: {body_font_file}")
    body_font_name = str(profile["fonts"].get("body") or font_name)
    if body_font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(body_font_name, str(body_font_file), subfontIndex=0))

    page = profile["page"]
    margins = page["margin-mm"]
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Relative assetRef paths are resolved against the SSIR input file's
    # directory first (MinerU writes assets/ next to the SSIR JSON), falling
    # back to the output directory for generated formula images.
    asset_dir = Path(input_file).resolve().parent if input_file and Path(input_file).is_file() else target.parent
    report = PDFRenderReport(input_file, str(target), str(profile_file), profile["id"], str(font_file))
    standard_no = document.get("metadata", {}).get("standard", {}).get("standardNumber", "")
    title = document["metadata"]["common"].get("title", "")

    class _PageNumber(Flowable):
        def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
            return available_width, 0

    def footer(canvas: Any, doc: Any) -> None:
        # 规则对应: GBT-P03（书眉：正文页编排文件编号）、GBT-P04（页码：正文起阿拉伯数字）、
        # GEN-072（页底锚定元素由页回调绘制）、GEN-018/GBT-L01（封面徽标与分类号区块）。
        canvas.saveState()
        canvas.setFont(font_name, 8)
        if standard_no and doc.page > 1:
            # GB/T covers carry no running header; body pages put the
            # standard number flush right.
            canvas.drawRightString(A4[0] - float(margins["right"]) * mm, A4[1] - 14 * mm, standard_no)
        if doc.page > 1 or not has_cover:
            canvas.drawRightString(A4[0] - float(margins["right"]) * mm, 12 * mm, str(doc.page))
        # The cover publication block (dates, solid rule, issuing bodies,
        # 批准发布) is anchored near the bottom of the first page only,
        # matching the GB/T 1.1 cover layout.
        if has_cover and doc.page == 1:
            _draw_cover_publication(
                canvas,
                float(margins["left"]) * mm,
                A4[0] - float(margins["right"]) * mm,
                common.get("publicationDate", ""),
                common.get("effectiveDate", ""),
                common.get("issuer", ""),
                28 * mm,
                font_name,
            )
            badge = standard.get("coverBadge")
            if badge:
                badge_path = (asset_dir / badge).resolve()
                if badge_path.is_file():
                    # Emblem sits at the top-right of the cover, above the
                    # standard-number block and clear of the banner text.
                    canvas.saveState()
                    canvas.drawImage(str(badge_path), A4[0] - float(margins["right"]) * mm - 100, A4[1] - 42 * mm, width=100, height=42, preserveAspectRatio=True, mask="auto")
                    canvas.restoreState()
        canvas.restoreState()

    styles = _styles(getSampleStyleSheet(), profile, font_name, body_font_name, TA_CENTER, TA_JUSTIFY, TA_LEFT)
    registries = {kind: {item["id"]: item for item in document.get(kind, [])} for kind in ("tables", "figures", "formulas", "unknownContents")}
    common = document.get("metadata", {}).get("common", {})
    standard = document.get("metadata", {}).get("standard", {})
    # 规则对应: GBT-C01（封面必备信息）——标准类文档一律渲染封面；ICS/CCS/日期缺失时
    # 由 _cover_story 以 "××" 占位并记录 warning，而不是跳过整个封面。
    has_cover = document.get("documentType") == "standard" or bool(standard.get("standardNumber"))
    root_nodes = sorted(document["structuralRoot"].get("children", []), key=_order)
    has_toc = any(_is_toc_node(node) for node in root_nodes)

    class _TOCMarker(Flowable):
        def __init__(self, node_id: str) -> None:
            super().__init__()
            self.node_id = node_id

        def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
            return 0, 0

        def draw(self) -> None:
            return None

    class _TOCFlowable(Flowable):
        """Fixed-leading TOC rows with measured dot leaders and right page numbers."""
        def __init__(self, rows: list[tuple[str, int, int]], width: float) -> None:
            super().__init__()
            self.rows = rows
            self.width = width
            self.leading = 18
            self.font_size = 10.5

        def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
            return available_width, len(self.rows) * self.leading

        def split(self, available_width: float, available_height: float) -> list[Any]:
            # If even one row cannot fit, move the whole flowable to the
            # next page — returning a piece that itself does not fit makes
            # reportlab raise a splitting error.
            count = int(available_height // self.leading)
            if count >= len(self.rows):
                return [self]
            if count < 1:
                return []
            return [_TOCFlowable(self.rows[:count], self.width), _TOCFlowable(self.rows[count:], self.width)]

        def draw(self) -> None:
            canvas = self.canv
            canvas.setFont(font_name, self.font_size)
            dot_width = canvas.stringWidth(".", font_name, self.font_size)
            for index, (label, level, page_no) in enumerate(self.rows):
                y = (len(self.rows) - index - 1) * self.leading + 4
                indent = level * 2 * self.font_size
                page_text = str(page_no)
                label_width = canvas.stringWidth(label, font_name, self.font_size)
                page_width = canvas.stringWidth(page_text, font_name, self.font_size)
                leader_space = self.width - indent - label_width - page_width - 8
                dot_count = max(int(leader_space // dot_width), 0)
                canvas.drawString(indent, y, label)
                canvas.drawString(indent + label_width + 4, y, "." * dot_count)
                canvas.drawRightString(self.width, y, page_text)

    class _IndexFlowable(Flowable):
        """Index rows with measured leaders and wrapped locator continuations."""
        def __init__(self, rows: list[tuple[str, str | None]], width: float) -> None:
            super().__init__()
            self.rows = rows
            self.width = width
            self.leading = 17
            self.font_size = 10.5
            self._layout: list[tuple[str, str | None, list[str]]] = []

        def _prepare(self) -> list[tuple[str, str | None, list[str]]]:
            if self._layout:
                return self._layout
            dot_width = pdfmetrics.stringWidth(".", font_name, self.font_size)
            for label, locator in self.rows:
                if locator is None:
                    self._layout.append((label, None, []))
                    continue
                label_width = pdfmetrics.stringWidth(label, font_name, self.font_size)
                leader_space = max(self.width - label_width - 2 * self.font_size, 0)
                locator_width = max(self.width - label_width - max(leader_space, 6 * dot_width), self.width * 0.45)
                pieces = _wrap_index_locator(locator, locator_width, font_name, self.font_size, pdfmetrics)
                self._layout.append((label, locator, pieces or [locator]))
            return self._layout

        def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
            return available_width, sum((1 if locator is None else len(parts)) * self.leading for _, locator, parts in self._prepare())

        def draw(self) -> None:
            canvas = self.canv
            canvas.setFont(font_name, self.font_size)
            dot_width = canvas.stringWidth(".", font_name, self.font_size)
            rows = self._prepare()
            y = sum((1 if locator is None else len(parts)) * self.leading for _, locator, parts in rows) - self.leading + 4
            for label, locator, parts in rows:
                if locator is None:
                    canvas.drawString(0, y, label)
                    y -= self.leading
                    continue
                label_width = canvas.stringWidth(label, font_name, self.font_size)
                first = parts[0]
                first_width = canvas.stringWidth(first, font_name, self.font_size)
                leader_space = max(self.width - label_width - first_width - 8, 0)
                dot_count = max(int(leader_space // dot_width), 0)
                canvas.drawString(0, y, label)
                canvas.drawString(label_width + 4, y, "." * dot_count)
                canvas.drawRightString(self.width, y, first)
                for continuation in parts[1:]:
                    y -= self.leading
                    canvas.drawRightString(self.width, y, continuation)
                y -= self.leading

    class _CoverBanner(Flowable):
        """Spread the national-standard banner across the cover's text block."""
        def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
            self.width = available_width
            return available_width, 30

        def draw(self) -> None:
            text = "中华人民共和国国家标准"
            # GB/T 1.1 Appendix F: cover banner is 一号黑体 (26pt).
            size = 26
            canvas = self.canv
            text_width = canvas.stringWidth(text, font_name, size)
            char_space = max((self.width - text_width) / max(len(text) - 1, 1), 0)
            x = 0.0
            for character in text:
                canvas.setFont(font_name, size)
                canvas.drawString(x, 3, character)
                x += canvas.stringWidth(character, font_name, size) + char_space

    class _CoverPublicationBlock(Flowable):
        """Fixed cover footer: dates, solid rule, issuing bodies, and 发布.

        Follows the GB/T 1.1 cover layout: a single solid rule near the page
        bottom with the two issuing bodies stacked vertically to its left and
        批准发布 (one character per line) at its right end.
        """
        def __init__(self, issued: str, effective: str, issuer: str) -> None:
            super().__init__()
            self.issued = issued
            self.effective = effective
            self.issuer = issuer

        def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
            self.width = available_width
            return available_width, 90

        def draw(self) -> None:
            canvas = self.canv
            # Dates row sits above the rule.
            canvas.setFont(font_name, 11)
            if self.issued:
                canvas.drawString(0, 75, f"{self.issued} 发布")
            if self.effective:
                canvas.drawRightString(self.width, 75, f"{self.effective} 实施")
            # Single solid rule; the bodies and 批准发布 hang below it.
            canvas.setLineWidth(1.8)
            canvas.line(0, 62, self.width, 62)
            bodies = [part.strip() for part in re.split(r"[、，,]", self.issuer) if part.strip()]
            canvas.setFont(font_name, 10.5)
            for index, body in enumerate(bodies[:2]):
                # Stacked vertically under the rule's left half.
                canvas.drawCentredString(self.width * 0.40, 42 - index * 18, body)
            if self.issuer:
                canvas.setFont(font_name, 11)
                canvas.drawCentredString(self.width - 12, 46, "批")
                canvas.drawCentredString(self.width - 12, 30, "准")
                canvas.drawCentredString(self.width - 12, 14, "发")
                canvas.drawCentredString(self.width - 12, -2, "布")

    def toc_story(toc_nodes: list[dict[str, Any]], toc_pages: dict[str, int]) -> list[Any]:
        rows = []
        for node in toc_nodes:
            label = _toc_label(node)
            if not label:
                continue
            level = _toc_indent_level(node)
            rows.append((label, level, toc_pages.get(node["id"], 0)))
        # Keep every TOC flowable within one frame.  ReportLab's generic split
        # protocol cannot safely split a flowable that calculates dot leaders
        # directly on the canvas.
        result: list[Any] = [Paragraph("目 次", styles["toc-title"])]
        # Fill the frame: usable height (A4 minus margins minus the title)
        # divided by the TOC row leading, with a safety margin.
        usable_pt = A4[1] - (float(margins["top"]) + float(margins["bottom"])) * mm - 30 * mm
        rows_per_page = max(int(usable_pt // 18), 18)
        for offset in range(0, len(rows), rows_per_page):
            result.append(_TOCFlowable(rows[offset:offset + rows_per_page], float(doc_width)))
            if offset + rows_per_page < len(rows):
                result.append(PageBreak())
        result.append(PageBreak())
        return result

    def make_doc(path: Path) -> Any:
        return SimpleDocTemplate(
            str(path), pagesize=A4,
            leftMargin=float(margins["left"]) * mm,
            rightMargin=float(margins["right"]) * mm,
            topMargin=float(margins["top"]) * mm,
            bottomMargin=float(margins["bottom"]) * mm,
            title=title,
            author="leleby SSIR",
        )

    def make_story(toc_pages: dict[str, int], record_pages: dict[str, int] | None = None) -> list[Any]:
        story: list[Any] = []
        if has_cover:
            story.extend(_cover_story(common, standard, styles, Paragraph, Spacer, PageBreak, HRFlowable, _CoverBanner, _CoverPublicationBlock, include_front_title=not has_toc, report=report))
        else:
            story.extend([Paragraph(_markup(title), styles["title"]), Spacer(1, 14 * mm)])
        body_title_inserted = False
        for node in root_nodes:
            if _is_toc_node(node):
                story.extend(toc_story(_toc_nodes(root_nodes, toc_depth), toc_pages))
                continue
            if _is_rendered_index_node(node):
                marker = _TOCMarker(node["id"]) if record_pages is not None else None
                story.extend(_index_story(root_nodes, styles, _IndexFlowable, PageBreak, Paragraph, marker))
                break
            # GB/T正文首页在前言、引言之后重复标准名称，然后才从第1章开始。
            if not body_title_inserted and node.get("number") == "1":
                story.extend([PageBreak(), Paragraph(_markup(title), styles["title"]), Spacer(1, 14 * mm)])
                body_title_inserted = True
            marker_factory = (lambda item: _TOCMarker(item["id"])) if record_pages is not None else None
            _append_node(story, node, registries, styles, font_name, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak)
        return story

    doc_width = A4[0] - (float(margins["left"]) + float(margins["right"])) * mm
    provisional_pages: dict[str, int] = {}
    if has_toc:
        # First pass has the same fixed-height TOC rows but placeholder page
        # values.  Markers record actual heading pages for the final pass.
        preflight = target.with_name(target.stem + ".toc-preflight.pdf")
        preflight_doc = make_doc(preflight)
        preflight_doc.afterFlowable = lambda flowable: provisional_pages.setdefault(flowable.node_id, preflight_doc.page) if isinstance(flowable, _TOCMarker) else None
        preflight_doc.build(make_story({}, provisional_pages), onFirstPage=footer, onLaterPages=footer)
        preflight.unlink(missing_ok=True)

    doc = make_doc(target)
    doc.build(make_story(provisional_pages), onFirstPage=footer, onLaterPages=footer)
    report.page_count = _pdf_page_count(target)
    return report


def render_pdf_file(
    input_path: str | Path,
    output: str | Path,
    *,
    profile_path: str | Path | None = None,
    toc_depth: int | None = 2,
) -> PDFRenderReport:
    source = Path(input_path)
    document = json.loads(source.read_text(encoding="utf-8"))
    return render_pdf(document, output, profile_path=profile_path, input_file=str(source), toc_depth=toc_depth)


def _styles(base: Any, profile: dict[str, Any], font: str, body_font: str, center: int, justify: int, left: int) -> dict[str, Any]:
    # 规则对应: GBT-P02（字号字体符合附录F）、GBT-FM2（前言/引言标题三号黑体居中）、
    # GBT-B02/B03（章条标题五号黑体、正文五号宋体）、GBT-B05（附录标题居中）、
    # GBT-B10（注小五号）、GEN-071（排版参数来自 profile）。
    from reportlab.lib.styles import ParagraphStyle

    rules = profile["styles"]
    body = rules["body"]
    # GB/T 1.1-2020 Appendix F (Table F.1): headings, captions and the table
    # number line use Hei (黑体); body text, notes and examples use Song
    # (宋体).  Heading sizes follow the same appendix: front-matter/TOC titles
    # 三号 (16pt), chapter headings 五号-equivalent scale per profile.
    return {
        "title": ParagraphStyle("gbt-title", parent=base["Title"], fontName=font, fontSize=26, leading=34, alignment=center, spaceAfter=8),
        "front": ParagraphStyle("gbt-front", parent=base["BodyText"], fontName=body_font, fontSize=rules["front-matter"]["size-pt"], leading=rules["front-matter"]["leading-pt"], alignment=justify, firstLineIndent=2 * body["size-pt"], spaceAfter=4),
        # GB/T 1.1 keeps chapter and clause headings flush left.  The chapter
        # line is one size larger; all clause levels share a size and leading.
        "section": ParagraphStyle("gbt-section", parent=base["Heading2"], fontName=font, fontSize=12, leading=22, alignment=left, leftIndent=0, firstLineIndent=0, spaceBefore=16, spaceAfter=10),
        "clause": ParagraphStyle("gbt-clause", parent=base["Heading3"], fontName=font, fontSize=10.5, leading=18, alignment=left, leftIndent=0, firstLineIndent=0, spaceBefore=8, spaceAfter=4),
        "subclause": ParagraphStyle("gbt-subclause", parent=base["Heading4"], fontName=font, fontSize=10.5, leading=18, alignment=left, leftIndent=0, firstLineIndent=0, spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("gbt-body", parent=base["BodyText"], fontName=body_font, fontSize=body["size-pt"], leading=body["leading-pt"], alignment=justify, firstLineIndent=2 * body["size-pt"], spaceAfter=4),
        "note": ParagraphStyle("gbt-note", parent=base["BodyText"], fontName=body_font, fontSize=9, leading=15, alignment=justify, leftIndent=2 * body["size-pt"], spaceAfter=4),
        "list": ParagraphStyle("gbt-list", parent=base["BodyText"], fontName=body_font, fontSize=body["size-pt"], leading=body["leading-pt"], alignment=justify, leftIndent=2 * body["size-pt"], firstLineIndent=-2 * body["size-pt"], spaceAfter=2),
        "list-sub": ParagraphStyle("gbt-list-sub", parent=base["BodyText"], fontName=body_font, fontSize=body["size-pt"], leading=body["leading-pt"], alignment=justify, leftIndent=4 * body["size-pt"], firstLineIndent=-2 * body["size-pt"], spaceAfter=2),
        "caption": ParagraphStyle("gbt-caption", parent=base["BodyText"], fontName=font, fontSize=10.5, leading=14, alignment=center, spaceBefore=4, spaceAfter=4),
        "formula": ParagraphStyle("gbt-formula", parent=base["Code"], fontName=body_font, fontSize=10, leading=16, alignment=center, spaceAfter=4),
        "table": ParagraphStyle("gbt-table", parent=base["BodyText"], fontName=body_font, fontSize=rules["table"]["size-pt"], leading=rules["table"]["leading-pt"], alignment=left),
        "toc-title": ParagraphStyle("gbt-toc-title", parent=base["Title"], fontName=font, fontSize=16, leading=22, alignment=center, spaceAfter=14),
        # GB/T 1.1 annex heading block: 附录 letter, status and title are
        # centred, in that order, with the title in the largest size.
        "annex-letter": ParagraphStyle("gbt-annex-letter", parent=base["Heading2"], fontName=font, fontSize=12, leading=20, alignment=center, spaceBefore=6, spaceAfter=4),
        "annex-status": ParagraphStyle("gbt-annex-status", parent=base["Heading3"], fontName=font, fontSize=10.5, leading=16, alignment=center, spaceAfter=4),
        "annex-title": ParagraphStyle("gbt-annex-title", parent=base["Heading2"], fontName=font, fontSize=14, leading=22, alignment=center, spaceAfter=14),
        "table-unit": ParagraphStyle("gbt-table-unit", parent=base["BodyText"], fontName=body_font, fontSize=9, leading=12, alignment=2, firstLineIndent=0, spaceBefore=2, spaceAfter=0),
    }


def _append_node(story: list[Any], node: dict[str, Any], registries: dict[str, dict[str, dict[str, Any]]], styles: dict[str, Any], font: str, report: PDFRenderReport, asset_dir: Path, colors: Any, Table: Any, TableStyle: Any, Paragraph: Any, Spacer: Any, Image: Any, marker_factory: Any = None, PageBreak: Any = None) -> None:
    # 规则对应: GBT-B02（章条编号顶格、空一字接排标题）、GBT-B05（附录另起一面、编号/
    # 性质/标题各占一行居中）、GBT-B06/B07（图题表题五号黑体居中）、GEN-073（整体性保护）。
    node_type = node.get("nodeType")
    number, title, is_annex = _heading_parts(node)
    if PageBreak is not None and _starts_new_page(node, title, is_annex):
        story.append(PageBreak())
    heading = _heading_text(number, title, is_annex)
    depth = _heading_depth(number)
    if is_annex:
        # GB/T 1.1: annex headings are centred; the annex letter, the
        # (规范性/资料性) marker and the title render as centred lines.
        story.append(marker_factory(node) if marker_factory else Spacer(1, 0))
        story.append(Paragraph(_markup(f"附　录　{number}"), styles["annex-letter"]))
        status = _heading_annex_status(node)
        if status:
            story.append(Paragraph(_markup(status), styles["annex-status"]))
        story.append(Paragraph(_markup(title), styles["annex-title"]))
        for content in sorted(node.get("contentElements", []), key=_order):
            _append_content(story, content, registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image)
        for child in sorted(node.get("children", []), key=_order):
            _append_node(story, child, registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak)
        return
    heading_style = styles["section"] if depth == 1 else styles["subclause"] if depth >= 3 else styles["clause"] if depth else styles["front"]
    if marker_factory:
        story.append(marker_factory(node))
    story.append(Paragraph(_markup(heading), heading_style))
    for content in sorted(node.get("contentElements", []), key=_order):
        _append_content(story, content, registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image)
    for child in sorted(node.get("children", []), key=_order):
        _append_node(story, child, registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak)


def _draw_cover_publication(canvas: Any, left: float, right: float, issued: str, effective: str, issuer: str, bottom: float, font: str) -> None:
    """Draw the GB/T cover publication block anchored near the page bottom.

    规则对应: GBT-L07（发布/实施日期倒数第二行左右分置）、GBT-L08（发布机构倒数第一行）、
    GBT-L09（"发布"整体一词编排，字距实现）、GEN-072（页回调绘制）。

    Layout per GB/T 1.1: the 发布/实施 dates sit above a single solid rule;
    below the rule the two issuing bodies stack vertically on the left while
    批准发布 runs vertically at the right end.
    """
    canvas.saveState()
    canvas.setFont(font, 11)
    # GBT-C01：发布/实施日期为封面必备信息，缺失时以 "××" 占位并保持版式。
    canvas.drawString(left, bottom + 52, f"{issued if issued else '××'} 发布")
    canvas.drawRightString(right, bottom + 52, f"{effective if effective else '××'} 实施")
    canvas.setLineWidth(1.8)
    canvas.line(left, bottom + 40, right, bottom + 40)
    bodies = [part.strip() for part in re.split(r"[、，,]|[\s　]+", issuer) if part.strip()]
    center = left + (right - left) * 0.40
    canvas.setFont(font, 10.5)
    if len(bodies) > 1:
        # Two issuing bodies stack vertically below the rule, the group
        # centred between the rule and the bottom margin.
        line_height = 18
        top = bottom + 26
        for index, body in enumerate(bodies[:2]):
            canvas.drawCentredString(center, top - index * line_height, body)
    elif bodies:
        canvas.drawCentredString(center, bottom + 20, bodies[0])
    if issuer:
        # Joint publication: a single horizontal 发布 (kept as one word with
        # modest letter-spacing) placed about one character-width to the
        # right of the issuing-body block.
        canvas.setFont(font, 12)
        pub = "发布"
        gap = canvas.stringWidth("国", font, 12)
        offset = 0
        for body in bodies[:2]:
            offset = max(offset, canvas.stringWidth(body, font, 10.5) / 2)
        x = center + offset + gap
        text_obj = canvas.beginText(x, bottom + 20)
        text_obj.setFont(font, 12)
        text_obj.setCharSpace(gap * 0.5)
        text_obj.textOut(pub)
        canvas.drawText(text_obj)
    canvas.restoreState()


def _cover_story(common: dict[str, Any], standard: dict[str, Any], styles: dict[str, Any], Paragraph: Any, Spacer: Any, PageBreak: Any, HRFlowable: Any, CoverBanner: Any, CoverPublicationBlock: Any, *, include_front_title: bool = True, report: Any = None) -> list[Any]:
    """Render mandatory GB/T cover fields when the SSIR metadata provides them.

    规则对应: GBT-L01（ICS/CCS 左上两行左端对齐）、GBT-L02（文件编号四号黑体）、
    GBT-L03（横幅"中华人民共和国国家标准"）、GBT-L04（文件名称一号黑体）、
    GBT-L05（英文译名四号黑体）、GBT-L06（一致性程度标识加圆括号）；
    GBT-C01（必备信息齐全性，缺失以 ×× 占位并记录 warning）。
    """
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle

    cover_left = ParagraphStyle("gbt-cover-left", parent=styles["front"], alignment=0, fontSize=10, leading=15, spaceAfter=0)
    cover_number = ParagraphStyle("gbt-cover-number", parent=styles["title"], alignment=2, fontSize=14, leading=19, spaceAfter=2)
    cover_replaces = ParagraphStyle("gbt-cover-replaces", parent=styles["front"], alignment=2, fontSize=10, leading=14, firstLineIndent=0, spaceAfter=0)
    cover_en = ParagraphStyle("gbt-cover-en", parent=styles["front"], alignment=1, fontSize=10, leading=15, spaceAfter=5)
    cover_conformity = ParagraphStyle("gbt-cover-conformity", parent=styles["front"], alignment=1, fontSize=8.5, leading=12, firstLineIndent=0, spaceAfter=0)
    title = common.get("title", "")
    english = common.get("titleEn", "")
    issued = common.get("publicationDate", "")
    effective = common.get("effectiveDate", "")
    issuer = common.get("issuer", "")
    conformity = common.get("conformityStatement", "")

    # GBT-C01 / GEN-090：封面必备信息（文件编号、ICS、CCS、发布/实施日期、
    # 发布机构、名称）任一缺失时，渲染以 "××" 占位并在渲染报告 warning
    # 中记录对应规则 ID —— 让占位在成品上可见、在报告中可追溯。
    def _required(value: str, field: str, rule: str) -> str:
        if str(value).strip():
            return str(value)
        if report is not None:
            report.warnings.append(f"[{rule}] 封面必备信息缺失，已用占位符渲染：{field}")
        return "××"

    standard_number = _required(standard.get("standardNumber", ""), "文件编号", "GBT-C01")
    ics = _required(standard.get("ics", ""), "ICS 号", "GBT-C01")
    ccs = _required(standard.get("ccs", ""), "CCS 号", "GBT-C01")
    title = _required(title, "文件名称", "GBT-C01")
    issued = _required(issued, "发布日期", "GBT-C01")
    effective = _required(effective, "实施日期", "GBT-C01")
    issuer = _required(issuer, "发布机构", "GBT-C01")

    result: list[Any] = []
    result.append(Paragraph(_markup(f"ICS {ics}"), cover_left))
    result.append(Paragraph(_markup(f"CCS {ccs}"), cover_left))
    result.extend([Spacer(1, 34), CoverBanner(), Spacer(1, 30), Paragraph(_markup(standard_number), cover_number)])
    if standard.get("replaces"):
        result.append(Paragraph(_markup(f"代替： {standard['replaces']}"), cover_replaces))
    result.extend([Spacer(1, 7), HRFlowable(width="100%", thickness=1.8, spaceBefore=0, spaceAfter=0, color=colors.black)])
    # GB/T 1.1 cover: the standard name sits clearly below the rule.
    result.extend([Spacer(1, 48), Paragraph(_markup(title), styles["title"])])
    if english:
        result.append(Paragraph(_markup(english), cover_en))
    if conformity:
        result.append(Paragraph(_markup(conformity), cover_conformity))
    result.extend([Spacer(1, 54)])
    # The publication block (dates/rule/bodies/批准发布) is drawn by the
    # first-page footer callback so it stays anchored near the page bottom.
    result.append(PageBreak())
    if include_front_title:
        result.extend([Paragraph(_markup(title), styles["title"]), Spacer(1, 14)])
    return result


def _append_content(story: list[Any], content: dict[str, Any], registries: dict[str, dict[str, dict[str, Any]]], styles: dict[str, Any], font: str, report: PDFRenderReport, asset_dir: Path, colors: Any, Table: Any, TableStyle: Any, Paragraph: Any, Spacer: Any, Image: Any) -> None:
    # 规则对应: GEN-032（表格题注拆分：居中题注 + 右对齐单位行）、GBT-B04（列项缩进）、
    # GBT-B10（注小五号宋体）、GBT-X06（公式另行居中、编号右对齐）、GBT-X01/B06（图与图题）。
    from reportlab.platypus import KeepTogether

    kind = content.get("presentationType")
    if kind in {"paragraph", "quote", "warning", "example"}:
        text = str(content.get("textContent", ""))
        # GB/T 1.1 table caption block: "表 X.Y 题名\n单位为毫米" — the unit
        # line renders small and flush right, directly above the table frame.
        caption_match = re.match(r"^(表\s*[A-Z]?\d*\.?\d*[^\n]*)\n(单位为[^\s]{1,4})\s*$", text.strip())
        unit_only = re.fullmatch(r"单位为[^\s]{1,4}", text.strip())
        if caption_match:
            story.append(Paragraph(_markup(caption_match.group(1).strip()), styles["caption"]))
            from reportlab.lib.styles import ParagraphStyle
            unit_style = styles.get("table-unit") or ParagraphStyle(
                "gbt-table-unit", parent=styles["body"], alignment=2, fontSize=9, leading=12, spaceAfter=0, firstLineIndent=0,
            )
            story.append(Paragraph(_markup(caption_match.group(2)), unit_style))
        elif unit_only:
            from reportlab.lib.styles import ParagraphStyle
            unit_style = styles.get("table-unit") or ParagraphStyle(
                "gbt-table-unit", parent=styles["body"], alignment=2, fontSize=9, leading=12, spaceAfter=0, firstLineIndent=0,
            )
            story.append(Paragraph(_markup(text.strip()), unit_style))
        else:
            story.append(Paragraph(_markup(text), styles["body"]))
    elif kind == "note":
        story.append(Paragraph(_markup(content.get("textContent", "")), styles["note"]))
    elif kind == "list":
        for item in sorted(content.get("listItems", []), key=_order):
            marker = str(item.get("marker", "-"))
            # GB/T 1.1 lists use two Han-character indents for a), and an
            # additional two for its 1) subitems.
            list_style = styles["list-sub"] if marker.rstrip(")）").isdigit() else styles["list"]
            story.append(Paragraph(_markup(f"{marker} {item.get('text', '')}"), list_style))
    elif kind == "table":
        _append_table(story, registries["tables"][content["tableRef"]], styles, colors, Table, TableStyle, Paragraph)
    elif kind == "formula":
        formula = registries["formulas"][content["formulaRef"]]
        asset = formula.get("assetRef")
        source_image = (asset_dir / asset).resolve() if asset and not Path(asset).is_absolute() else Path(asset or "")
        image_path = source_image if source_image.is_file() else _formula_image(formula.get("latex") or formula.get("rawText", ""), asset_dir)
        if image_path:
            image = Image(str(image_path))
            # MinerU equation crops are already tightly fitted at approximately
            # document scale; generated MathText images need the same upper
            # bounds but are otherwise kept at their native size.
            scale = min(1.0, 455 / image.imageWidth, 140 / image.imageHeight)
            image.drawWidth = image.imageWidth * scale
            image.drawHeight = image.imageHeight * scale
            image.hAlign = "CENTER"
            story.append(image)
        else:
            report.warnings.append(f"Formula could not be typeset; retained as text: {formula['id']}")
            story.append(Paragraph(_markup(formula.get("rawText", "")), styles["formula"]))
        if formula.get("number"):
            story.append(Paragraph(_markup(str(formula["number"])), styles["caption"]))
    elif kind == "figure":
        figure = registries["figures"][content["figureRef"]]
        asset = figure.get("assetRef")
        asset_path = (asset_dir / asset).resolve() if asset and not Path(asset).is_absolute() else Path(asset or "")
        if asset and asset_path.is_file():
            image = Image(str(asset_path))
            scale = min(455 / image.imageWidth, 520 / image.imageHeight)
            image.drawWidth = image.imageWidth * scale
            image.drawHeight = image.imageHeight * scale
            image.hAlign = "CENTER"
            figure_flowables: list[Any] = [image]
        else:
            report.warnings.append(f"Missing figure asset retained as placeholder: {figure['id']}")
            figure_flowables = [Paragraph(_markup("[图像资产缺失]"), styles["caption"])]
        figure_number = str(figure.get("number") or "")
        figure_caption = str(figure.get("caption") or "")
        caption = f"图{figure_number} {figure_caption}".strip() if (figure_number or figure_caption) else ""
        if caption:
            figure_flowables.append(Paragraph(_markup(caption), styles["caption"]))
        story.append(KeepTogether(figure_flowables))
    elif kind == "other":
        unknown = registries["unknownContents"].get(content.get("unknownRef"), {})
        report.warnings.append(f"Unknown content rendered as text: {unknown.get('id', content.get('id'))}")
        story.append(Paragraph(_markup(unknown.get("rawContent", "")), styles["body"]))


def _append_table(story: list[Any], table: dict[str, Any], styles: dict[str, Any], colors: Any, Table: Any, TableStyle: Any, Paragraph: Any) -> None:
    # 规则对应: GBT-B07（表编号表题居中置于表上、表头框线、数字小五号宋体）、
    # GBT-X02（不准许分表/表中套表；转页重复表头 repeatRows）、GEN-033（无编号无题名不输出题注）。
    from reportlab.platypus import Spacer

    number = str(table.get("number") or "").strip()
    caption = str(table.get("caption") or "").strip()
    # A table with neither number nor caption gets no caption line at all
    # (otherwise a lone "表" character would appear above the table).
    if number or caption:
        story.append(Paragraph(_markup(f"表{number} {caption}".strip()), styles["caption"]))
    rows = sorted(table.get("rows", []), key=lambda row: row["rowIndex"])
    data = [[Paragraph(_markup(cell.get("text", "")), styles["table"]) for cell in sorted(row.get("cells", []), key=lambda cell: cell["colIndex"])] for row in rows]
    if not data:
        return
    width = 455
    grid = Table(data, colWidths=[width / max(len(data[0]), 1)] * len(data[0]), repeatRows=sum(1 for row in rows if row.get("isHeader")))
    commands: list[tuple[Any, ...]] = [("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if rows and rows[0].get("isHeader"):
        commands.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")))
    for row in rows:
        for cell in row.get("cells", []):
            if cell.get("rowspan", 1) > 1 or cell.get("colspan", 1) > 1:
                commands.append(("SPAN", (cell["colIndex"], cell["rowIndex"]), (cell["colIndex"] + cell.get("colspan", 1) - 1, cell["rowIndex"] + cell.get("rowspan", 1) - 1)))
    grid.setStyle(TableStyle(commands))
    story.extend([grid, Spacer(1, 6)])


def _markup(text: str) -> str:
    escaped = escape(str(text)).replace("\n", "<br/>")
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*(.+?)\*", r"<i>\1</i>", escaped)
    return escaped


def _formula_image(latex: str, asset_dir: Path) -> Path | None:
    """Render a display formula through Matplotlib's bundled MathText engine.

    规则对应: GBT-X06（数学公式另行居中编排的资产支撑）。
    """
    expression = latex.strip()
    if not expression:
        return None
    path = asset_dir / "assets" / "formulas" / f"{hashlib.sha256(expression.encode('utf-8')).hexdigest()}.png"
    if path.is_file():
        return path
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure

        path.parent.mkdir(parents=True, exist_ok=True)
        figure = Figure(figsize=(6.2, 0.7), dpi=180)
        FigureCanvasAgg(figure)
        figure.text(0.5, 0.5, f"${expression}$", fontsize=14, ha="center", va="center")
        figure.savefig(path, dpi=180, transparent=True, bbox_inches="tight", pad_inches=0.04)
        return path
    except Exception:
        path.unlink(missing_ok=True)
        return None


def _order(value: dict[str, Any]) -> int:
    return int(value.get("sortOrder", value.get("rowIndex", 0)))


def _is_toc_node(node: dict[str, Any]) -> bool:
    return not node.get("number") and "目次" in str(node.get("title", "")).replace(" ", "")


def _heading_parts(node: dict[str, Any]) -> tuple[str, str, bool]:
    """Normalize headings where extraction kept the number in title text.

    规则对应: GEN-031（层次编号规范化：点分阿拉伯数字 / 附录大写字母点分链）。
    """
    raw_number = str(node.get("number") or "").strip()
    title = str(node.get("title") or "").strip()
    annex = node.get("nodeType") == "annex"
    status = ""
    if annex:
        status_match = re.match(r"^（(规范性|资料性|未判定)）\s*(.*)$", title)
        if status_match:
            status, title = status_match.group(1), status_match.group(2).strip()
    annex_match = re.match(r"^附\s*录\s*([A-Z])(?:\s*(.*))?$", title)
    if annex_match:
        return annex_match.group(1), (annex_match.group(2) or "").strip(), True
    if annex:
        node = {**node, "annexStatus": status}  # type: ignore[assignment]
        return raw_number, title, True
    if not raw_number:
        pure_numbered = re.match(r"^([A-Z](?:\.\d+)+|\d+(?:\.\d+)*)$", title)
        numbered = re.match(r"^([A-Z](?:\.\d+)+|\d+(?:\.\d+)*)(?:\s+|(?=[\u4e00-\u9fffA-Za-z（]))(.+)$", title)
        if numbered:
            raw_number, title = numbered.group(1), numbered.group(2).strip()
        elif pure_numbered:
            raw_number, title = pure_numbered.group(1), ""
    return raw_number, title, False


def _heading_annex_status(node: dict[str, Any]) -> str:
    """Return the (规范性/资料性) marker stored in an annex title, if any."""
    title = str(node.get("title") or "").strip()
    match = re.match(r"^（(规范性|资料性|未判定)）", title)
    return f"（{match.group(1)}）" if match else ""


def _heading_text(number: str, title: str, is_annex: bool) -> str:
    if is_annex:
        return f"附录 {number}\u3000{title}".strip()
    if number:
        return f"{number}\u3000{title}".strip()
    return title


def _heading_depth(number: str) -> int:
    # 规则对应: GEN-031/GBT-H02-H03（章条层次：点分编号决定字号层级）。
    if re.fullmatch(r"\d+", number):
        return 1
    if re.fullmatch(r"\d+(?:\.\d)+", number):
        return number.count(".") + 1
    if re.fullmatch(r"[A-Z](?:\.\d+)*", number):
        return number.count(".") + 2
    return 0


def _starts_new_page(node: dict[str, Any], title: str, is_annex: bool) -> bool:
    # 规则对应: GBT-B05（附录另起一面）、GBT-FM2（前言、引言另起一面）、GBT-FM5（参考文献/索引另起一面）。
    normalized = title.replace(" ", "")
    return is_annex or (not node.get("number") and normalized in {"引言", "参考文献"})


def _toc_nodes(root_nodes: list[dict[str, Any]], depth: int | None = 2) -> list[dict[str, Any]]:
    # 规则对应: GBT-C02/GBT-FM1（目次：前言、引言、章、条(需要时)、附录、参考文献、索引）。
    result: list[dict[str, Any]] = []

    def visit(node: dict[str, Any]) -> None:
        if _is_toc_node(node):
            return
        number, title, is_annex = _heading_parts(node)
        normalized_title = title.replace(" ", "")
        # Front matter is represented as unnumbered document blocks.
        number_depth = len(number.split(".")) if re.fullmatch(r"\d+(?:\.\d+)*", number) else 1 if is_annex else 0
        if (number and (depth is None or number_depth <= depth)) or normalized_title in {"前言", "引言", "参考文献", "索引"} or is_annex:
            result.append(node)
        for child in sorted(node.get("children", []), key=_order):
            visit(child)

    for node in root_nodes:
        visit(node)
    return result


def _toc_label(node: dict[str, Any]) -> str:
    number, title, is_annex = _heading_parts(node)
    return _heading_text(number, title.replace(" ", ""), is_annex)


def _toc_indent_level(node: dict[str, Any]) -> int:
    # 规则对应: GBT-FM1（目次第一层次条空一个汉字起排、第二层次空两个，依此类推）。
    number, _, is_annex = _heading_parts(node)
    if is_annex:
        return 0
    if not number:
        return 0
    return max(number.count("."), 0)


def _is_rendered_index_node(node: dict[str, Any]) -> bool:
    """Distinguish the document's final index from a chapter titled 索引."""
    _, title, _ = _heading_parts(node)
    return node.get("nodeType") == "documentBlock" and not node.get("number") and title.replace(" ", "") == "索引"


def _index_story(root_nodes: list[dict[str, Any]], styles: dict[str, Any], IndexFlowable: Any, PageBreak: Any, Paragraph: Any, marker: Any = None) -> list[Any]:
    # 规则对应: GBT-FM5（索引另起一面、标题居中、关键词与编号间"……"连接）。
    start = next((index for index, node in enumerate(root_nodes) if _is_rendered_index_node(node)), None)
    if start is None:
        return []
    rows: list[tuple[str, str | None]] = []
    for node in root_nodes[start + 1:]:
        title = str(node.get("title") or "").strip()
        if re.fullmatch(r"[A-Z]", title):
            rows.append((title, None))
        for content in sorted(node.get("contentElements", []), key=_order):
            if content.get("presentationType") != "paragraph":
                continue
            for line in str(content.get("textContent") or "").splitlines():
                text = line.strip()
                if not text:
                    continue
                if re.fullmatch(r"[A-Z]", text):
                    rows.append((text, None))
                    continue
                match = re.match(r"^(.*?)…{2,}\s*(.*)$", text)
                if match:
                    rows.append((match.group(1).strip(), match.group(2).strip()))
                elif rows and rows[-1][1] is not None:
                    label, locator = rows[-1]
                    rows[-1] = (label, f"{locator} {text}".strip())
                else:
                    rows.append((text, ""))
    result: list[Any] = [PageBreak()]
    if marker is not None:
        result.append(marker)
    result.append(Paragraph("索 引", styles["toc-title"]))
    # The extraction normally represents each alphabetic group as a large
    # paragraph.  Pack by measured height so continuation lines do not either
    # overflow a page or leave an arbitrary amount of blank space.
    batch: list[tuple[str, str | None]] = []
    for row in rows:
        candidate = batch + [row]
        height = IndexFlowable(candidate, 455).wrap(455, 650)[1]
        if batch and height > 620:
            result.append(IndexFlowable(batch, 455))
            result.append(PageBreak())
            batch = [row]
        else:
            batch = candidate
    if batch:
        result.append(IndexFlowable(batch, 455))
    return result


def _wrap_index_locator(text: str, width: float, font: str, size: float, pdfmetrics: Any) -> list[str]:
    """Break a locator list at its natural separators without overflowing."""
    tokens = re.split(r"(?<=[,，;；])\s*", text.strip())
    lines: list[str] = []
    current = ""
    for token in filter(None, tokens):
        candidate = f"{current} {token}".strip()
        if current and pdfmetrics.stringWidth(candidate, font, size) > width:
            lines.append(current)
            current = token
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _pdf_page_count(path: Path) -> int:
    # 规则对应: GEN-076（渲染报告页数统计）。
    # A page object marker is deterministic enough for a render report and needs no PDF parser.
    return len(re.findall(rb"/Type\s*/Page\b", path.read_bytes()))
