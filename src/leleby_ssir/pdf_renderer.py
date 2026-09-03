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


DEFAULT_PROFILE = Path(__file__).resolve().parents[2] / "config" / "rendering" / "GB_T_1.1-2020.yaml"


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


def _resolve_asset(asset_dir: Path, ref: str) -> Path:
    """Resolve a relative asset reference for rendering.

    Relative ``assetRef`` paths resolve against the SSIR input file's
    directory first, then upward toward the document root (stage-directory
    layout: ``03_ssir/<ID>.ssir.json`` -> ``<docroot>/assets/``), stopping at
    the directory that carries ``manifest.json`` or after four ancestors.
    Missing references return the primary candidate so callers fall back to
    their placeholder logic.
    """
    if not ref or Path(ref).is_absolute():
        return Path(ref or "")
    primary = asset_dir / ref
    if primary.is_file():
        return primary
    for parent in list(asset_dir.parents)[:4]:
        probe = parent / ref
        if probe.is_file():
            return probe
        if (parent / "manifest.json").is_file():
            break
    return primary


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
    # back to the output directory for generated formula images.  In the
    # stage-directory layout (03_ssir/<ID>.ssir.json -> <docroot>/assets/)
    # the reference is also searched upward toward the document root.
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
            # 封面徽标按标准类型从固定位置读取（GEN-018/GBT-L02），不再使用
            # 从 PDF 提取的 coverBadge 图块。徽标位于封面右上角、编号区块
            # 之上，避开横幅文字。尺寸/位置对齐官方封面模板（GB_T_23132-2024
            # 原稿实测：徽章 113.7x56.9pt、上边距 31.5pt≈11.1mm、右缘贴版心
            # 右边距；图像 2:1 全填充）。
            emblem_path = _cover_emblem_path(str(standard_no), profile, profile_file)
            if emblem_path:
                canvas.saveState()
                canvas.drawImage(
                    str(emblem_path),
                    A4[0] - float(margins["right"]) * mm - 114,
                    A4[1] - 11.1 * mm - 57,
                    width=114,
                    height=57,
                    preserveAspectRatio=True,
                    mask="auto",
                )
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
        """Spread the standard-level banner across the cover's text block."""
        def __init__(self, text: str = "中华人民共和国国家标准") -> None:
            super().__init__()
            self.text = text
        def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
            self.width = available_width
            return available_width, 30

        def draw(self) -> None:
            # 规则对应: GBT-L03（封面横幅）——按标准层级渲染：国家/行业/地方/
            # 团体/企业标准分别取 "中华人民共和国…" 横幅或元数据 banner 文本，
            # 而非硬编码国家标准横幅。
            text = self.text or "中华人民共和国国家标准"
            # GB/T 1.1 Appendix F: cover banner is 一号黑体 (26pt); shrink to
            # keep long industry banners on one line.
            size = 26 if len(text) <= 12 else max(26 - (len(text) - 12), 14)
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

    class _EndLine(Flowable):
        """GB/T 1.1-2020 终结线：标准正文末尾的居中粗实线，长度=版心宽度四分之一。

        Follows the GB/T 1.1 closing rule (末页应有终结线): a single centred
        rule whose length is one quarter of the text-block width, drawn a
        short gap below the last content line (GBT-C13).
        """

        def __init__(self, gap: float = 18, line_width: float = 1.5) -> None:
            super().__init__()
            self.gap = gap
            self.line_width = line_width
            self.height = gap + line_width

        def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
            self.width = available_width
            self.length = max(available_width / 4.0, 1.0)
            return available_width, self.height

        def draw(self) -> None:
            canvas = self.canv
            canvas.setLineWidth(self.line_width)
            # 线条画在 flowable 底部；gap 位于内容与线条之间。
            canvas.line((self.width - self.length) / 2, self.line_width, (self.width + self.length) / 2, self.line_width)

    def toc_story(toc_nodes: list[dict[str, Any]], toc_pages: dict[str, int], extra_contents: list[dict[str, Any]] | None = None) -> list[Any]:
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
        # 目次块内的非行内容（如目录页底部的装饰图）保留渲染；TOC 文本
        # paragraph 由 _toc_nodes 行生成，此处只补 figure 等，避免重复。
        for content in sorted(extra_contents or [], key=_order):
            if content.get("presentationType") == "figure":
                _append_content(result, content, registries, styles, font_name, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image)
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
        example_default = str((profile.get("styles") or {}).get("examples", {}).get("style", "frame"))
        idx = 0
        root_len = len(root_nodes)
        while idx < root_len:
            node = root_nodes[idx]
            if _is_toc_node(node):
                story.extend(toc_story(_toc_nodes(root_nodes, toc_depth), toc_pages, node.get("contentElements", [])))
                idx += 1
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
            if node.get("exampleContent"):
                # 附录示例块（GBT-B11）：连续 exampleContent 兄弟打包成框。
                # 「示例N：」是框外题注（黑体顶格），不进框；框内第一个节点
                # 是示例文档真实标题（黑体居中），其后是示例文档自身编号章条。
                if _is_example_header(node):
                    story.append(Paragraph(_markup(str(node.get("title") or "").strip()), styles["example-label"]))
                    idx += 1
                    continue
                box: list[Any] = []
                mode = str(node.get("exampleStyle") or example_default)
                while idx < root_len and root_nodes[idx].get("exampleContent"):
                    if _is_example_header(root_nodes[idx]):
                        break
                    _append_node(box, root_nodes[idx], registries, styles, font_name, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default, example_leading=not box)
                    idx += 1
                box = _strip_pagebreaks(box, PageBreak)
                story.append(_example_box(box, mode, colors, Table, TableStyle))
                continue
            _append_node(story, node, registries, styles, font_name, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default)
            idx += 1
        if has_cover:
            # GB/T 1.1-2020 末页应有终结线（GBT-C13）；仅标准类文档（与封面同门控）。
            story.append(_EndLine())
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
        "front": ParagraphStyle("gbt-front", parent=base["BodyText"], fontName=body_font, fontSize=rules["front-matter"]["size-pt"], leading=rules["front-matter"]["leading-pt"], alignment=justify, firstLineIndent=2 * body["size-pt"], spaceAfter=4, wordWrap="CJK"),
        # GB/T 1.1-2020 Appendix F (Table F.1): 前言/引言/目次等前置标题三号黑体居中。
        "front-title": ParagraphStyle(
            "gbt-front-title",
            parent=base["Title"],
            fontName=font,
            fontSize=(rules.get("front-matter-title") or {}).get("size-pt", 16),
            leading=(rules.get("front-matter-title") or {}).get("leading-pt", 22),
            alignment=center,
            spaceAfter=12,
        ),
        # GB/T 1.1 keeps chapter and clause headings flush left.  The chapter
        # line is one size larger; all clause levels share a size and leading.
        "section": ParagraphStyle("gbt-section", parent=base["Heading2"], fontName=font, fontSize=12, leading=22, alignment=left, leftIndent=0, firstLineIndent=0, spaceBefore=16, spaceAfter=10),
        "clause": ParagraphStyle("gbt-clause", parent=base["Heading3"], fontName=font, fontSize=10.5, leading=18, alignment=left, leftIndent=0, firstLineIndent=0, spaceBefore=8, spaceAfter=4),
        "subclause": ParagraphStyle("gbt-subclause", parent=base["Heading4"], fontName=font, fontSize=10.5, leading=18, alignment=left, leftIndent=0, firstLineIndent=0, spaceBefore=8, spaceAfter=4),
        "body": ParagraphStyle("gbt-body", parent=base["BodyText"], fontName=body_font, fontSize=body["size-pt"], leading=body["leading-pt"], alignment=justify, firstLineIndent=2 * body["size-pt"], spaceAfter=4, wordWrap="CJK"),
        # Untitled clause paragraphs start with the clause number; GB/T 1.1
        # puts those numbers flush left (顶格) instead of taking the body
        # two-Han-character first-line indent (GBT-B02).  They are left
        # aligned, not justified: reportlab's justification stretches every
        # space on a short first line, blowing up the gap after the clause
        # number ("5.5.3" + 50pt), which OCR standards exhibit as noise.
        "body-flush": ParagraphStyle("gbt-body-flush", parent=base["BodyText"], fontName=body_font, fontSize=body["size-pt"], leading=body["leading-pt"], alignment=left, firstLineIndent=0, spaceAfter=4, wordWrap="CJK"),
        "note": ParagraphStyle("gbt-note", parent=base["BodyText"], fontName=body_font, fontSize=9, leading=15, alignment=justify, leftIndent=2 * body["size-pt"], spaceAfter=4, wordWrap="CJK"),
        # GB/T 1.1-2020 6.6.3：第一层次列项（——/a)）空两个汉字起排、
        # 回行对齐第5汉字；第二层次列项（·/1)）空四个汉字起排、回行对齐第7汉字。
        "list": ParagraphStyle("gbt-list", parent=base["BodyText"], fontName=body_font, fontSize=body["size-pt"], leading=body["leading-pt"], alignment=justify, leftIndent=4 * body["size-pt"], firstLineIndent=-2 * body["size-pt"], spaceAfter=2, wordWrap="CJK"),
        "list-sub": ParagraphStyle("gbt-list-sub", parent=base["BodyText"], fontName=body_font, fontSize=body["size-pt"], leading=body["leading-pt"], alignment=justify, leftIndent=6 * body["size-pt"], firstLineIndent=-2 * body["size-pt"], spaceAfter=2, wordWrap="CJK"),
        "caption": ParagraphStyle("gbt-caption", parent=base["BodyText"], fontName=font, fontSize=10.5, leading=14, alignment=center, spaceBefore=4, spaceAfter=4),
        "formula": ParagraphStyle("gbt-formula", parent=base["Code"], fontName=body_font, fontSize=10, leading=16, alignment=center, spaceAfter=4),
        "table": ParagraphStyle("gbt-table", parent=base["BodyText"], fontName=body_font, fontSize=rules["table"]["size-pt"], leading=rules["table"]["leading-pt"], alignment=center),
        "toc-title": ParagraphStyle("gbt-toc-title", parent=base["Title"], fontName=font, fontSize=16, leading=22, alignment=center, spaceAfter=14),
        # GB/T 1.1 annex heading block: 附录 letter, status and title are
        # centred, in that order, with the title in the largest size.
        "annex-letter": ParagraphStyle("gbt-annex-letter", parent=base["Heading2"], fontName=font, fontSize=12, leading=20, alignment=center, spaceBefore=6, spaceAfter=4),
        "annex-status": ParagraphStyle("gbt-annex-status", parent=base["Heading3"], fontName=font, fontSize=10.5, leading=16, alignment=center, spaceAfter=4),
        "annex-title": ParagraphStyle("gbt-annex-title", parent=base["Heading2"], fontName=font, fontSize=14, leading=22, alignment=center, spaceAfter=14),
        # 附录编写示例块（GB/T 20001 表框/图框内容，CSM-OCR-006）：示例文档
        # 标题黑体居中；示例内部的编号标题（如 4 技术要求）用黑体加粗顶格，
        # 与正文章条区分（它们是示例文档自带的编号，不是本标准章条）。
        "example-title": ParagraphStyle("gbt-example-title", parent=base["Title"], fontName=font, fontSize=10.5, leading=16, alignment=center, spaceBefore=6, spaceAfter=4),
        "example-content": ParagraphStyle("gbt-example-content", parent=base["BodyText"], fontName=font, fontSize=10.5, leading=16, alignment=left, leftIndent=0, firstLineIndent=0, spaceBefore=4, spaceAfter=2, wordWrap="CJK"),
        # 附录示例框外的「示例N：」题注：黑体顶格，位于框上方（不进框）。
        "example-label": ParagraphStyle("gbt-example-label", parent=base["BodyText"], fontName=font, fontSize=10.5, leading=16, alignment=left, leftIndent=0, firstLineIndent=0, spaceBefore=8, spaceAfter=2, wordWrap="CJK"),
        "table-unit": ParagraphStyle("gbt-table-unit", parent=base["BodyText"], fontName=body_font, fontSize=9, leading=12, alignment=2, firstLineIndent=0, spaceBefore=2, spaceAfter=0),
        # 并列定位容器单元格（sideBySideGroup，无边框表格）：图内标注文字
        # 按列居中（L≤0.4 mm / a) 合格断面 等），不缩进、宋体。
        "side-cell": ParagraphStyle("gbt-side-cell", parent=base["BodyText"], fontName=body_font, fontSize=body["size-pt"], leading=body["leading-pt"], alignment=center, firstLineIndent=0, leftIndent=0, spaceAfter=2, wordWrap="CJK"),
    }


def _is_example_header(node: dict[str, Any]) -> bool:
    """True for a standalone '示例N：' label (the annex example caption that
    sits OUTSIDE the box; the boxed title is the example's real document
    title, which follows it as the first exampleContent sibling)."""
    return bool(re.match(r"^示例\s*\d*\s*[:：]\s*$", str(node.get("title") or "").strip()))


def _strip_pagebreaks(flowables: list[Any], PageBreak: Any) -> list[Any]:
    """Drop page breaks from an example box before wrapping it in a table.

    A PageBreak flowable claims the full frame height, so inside the
    single-column example-box table it inflates a row to ~72000pt and
    reportlab raises LayoutError.  The box table already splits across
    pages on its own (one closed box per page fragment), so page breaks
    are never needed inside it.
    """
    if PageBreak is None:
        return flowables
    return [flowable for flowable in flowables if not isinstance(flowable, PageBreak)]


def _example_box(flowables: list[Any], mode: str, colors: Any, Table: Any, TableStyle: Any) -> Any:
    """Wrap an annex example block in a box: black thin-line frame or a light
    background (GBT-B11 示例线框；GB/T 1.1 10.4.5 区分线框细实线).

    每个 flowable 占一行：reportlab Table 按行跨页拆分，每页片段绘制
    闭合框/背景，与原标准示例框跨页续排的表现一致。

    KeepTogether 不能进表格行：其 wrap 恒返回 0xffffff（16,777,215pt，
    强制拆分的哨兵高度），单列表格会把该行撑到 ~16.7M pt → LayoutError
    （GB_T_20001.6-2017 附录示例框图崩溃：图 4.1/图 4.2 的
    KeepTogether([image, caption]) 进框即炸）。展开其内容，每个子
    flowable 单独成行；子内容里的 PageBreak 同样剔除。
    """
    from reportlab.platypus import KeepTogether, PageBreak

    rows: list[list[Any]] = []
    for flowable in flowables:
        if isinstance(flowable, KeepTogether):
            # reportlab stubs don't declare the private _content attribute.
            subs = getattr(flowable, "_content", [])
            for sub in subs:
                if not isinstance(sub, PageBreak):
                    rows.append([sub])
        else:
            rows.append([flowable])
    table = Table(rows, colWidths=[None])
    commands = [
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if mode == "shaded":
        # 浅色背景（类代码块）：无边框，淡灰底。
        commands.append(("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0F2F5")))
    else:
        # 黑色细实线框（默认，GB/T 1.1 10.4.5）。
        commands.append(("BOX", (0, 0), (-1, -1), 0.75, colors.black))
    table.setStyle(TableStyle(commands))
    return table


def _append_nodes(story: list[Any], nodes: list[dict[str, Any]], registries: dict[str, dict[str, dict[str, Any]]], styles: dict[str, Any], font: str, report: PDFRenderReport, asset_dir: Path, colors: Any, Table: Any, TableStyle: Any, Paragraph: Any, Spacer: Any, Image: Any, marker_factory: Any = None, PageBreak: Any = None, example_default: str = "frame") -> None:
    """Append sibling nodes, grouping consecutive annex example-content nodes
    into boxed example blocks (GBT-B11); each '示例N：' label stays outside the
    box as a caption, and the first boxed node is the example's real title."""
    index = 0
    while index < len(nodes):
        node = nodes[index]
        if node.get("exampleContent"):
            # 「示例N：」框外题注：不进框，黑体顶格排在框上方。
            if _is_example_header(node):
                story.append(Paragraph(_markup(str(node.get("title") or "").strip()), styles["example-label"]))
                index += 1
                continue
            box: list[Any] = []
            mode = str(node.get("exampleStyle") or example_default)
            while index < len(nodes) and nodes[index].get("exampleContent"):
                if _is_example_header(nodes[index]):
                    break
                _append_node(box, nodes[index], registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default, example_leading=not box)
                index += 1
            box = _strip_pagebreaks(box, PageBreak)
            story.append(_example_box(box, mode, colors, Table, TableStyle))
            continue
        _append_node(story, node, registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default)
        index += 1


def _append_content_sequence(story: list[Any], contents: list[dict[str, Any]], registries: dict[str, dict[str, dict[str, Any]]], styles: dict[str, Any], font: str, report: PDFRenderReport, asset_dir: Path, colors: Any, Table: Any, TableStyle: Any, Paragraph: Any, Spacer: Any, Image: Any) -> None:
    """Append a node's contentElements with two layout rules:

    1. **并列定位容器**（sideBySideGroup，pipeline 打标）：同组 content 渲染为
       一行无边框表格（等价 HTML div 布局），各列按源 PDF 几何并排——GB_T_23132-2024
       图2 的 a)/b) 子图及其图内标注（L≤0.4 mm / a) 合格断面 等）左右并列；
       列内图居中、标注文字居中（side-cell 样式）。
    2. **图注行间距**（通用要求）：上一行是图的说明（figure content 或
       "图 N …" 题注段落），下一行紧接另一表头名称（table 或 "表 N …" 段落）
       → 两行之间空一行/更大间距以示内容区分。
    """
    contents = sorted(contents, key=_order)
    index = 0
    prev_figure_note = False
    while index < len(contents):
        content = contents[index]
        group = content.get("sideBySideGroup")
        if group:
            members: list[dict[str, Any]] = []
            while index < len(contents) and contents[index].get("sideBySideGroup") == group:
                members.append(contents[index])
                index += 1
            _append_side_by_side(story, members, registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image)
            prev_figure_note = True  # 并列组整体是"图的说明"
            continue
        # 图注行（图题/图）后紧跟表头名称 → 空一行/更大间距（通用要求）。
        if prev_figure_note and _is_table_caption_shape(content):
            story.append(Spacer(1, 10))
        _append_content(story, content, registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image)
        prev_figure_note = _is_figure_note_shape(content)
        index += 1


def _is_figure_note_shape(content: dict[str, Any]) -> bool:
    kind = content.get("presentationType")
    if kind == "figure":
        return True
    if kind in {"paragraph", "note", "list"}:
        text = str(content.get("textContent") or "")
        if kind == "list":
            items = content.get("listItems") or []
            text = " ".join(str(item.get("text") or "") for item in items)
        return bool(re.match(r"^图\s*\d+\.?\d*", text.strip()))
    return False


def _is_table_caption_shape(content: dict[str, Any]) -> bool:
    kind = content.get("presentationType")
    if kind == "table":
        return True
    if kind in {"paragraph", "note"}:
        return bool(re.match(r"^表\s*\d+\.?\d*", str(content.get("textContent") or "").strip()))
    return False


def _append_side_by_side(story: list[Any], members: list[dict[str, Any]], registries: dict[str, dict[str, dict[str, Any]]], styles: dict[str, Any], font: str, report: PDFRenderReport, asset_dir: Path, colors: Any, Table: Any, TableStyle: Any, Paragraph: Any, Spacer: Any, Image: Any) -> None:
    """Render a side-by-side group as one borderless table row (div 定位等价物)。

    每列是一个单元格（flowables 垂直堆叠）：图按 sourceWidth 原尺寸居中，
    图内标注/说明文字用 side-cell 样式列内居中。无 GRID/BOX 命令 → 无表格线。
    """
    from reportlab.platypus import KeepTogether

    columns: dict[int, list[dict[str, Any]]] = {}
    for content in members:
        columns.setdefault(int(content.get("sideBySideColumn", 0)), []).append(content)
    col_keys = sorted(columns)
    if not col_keys:
        return
    col_flowables: list[list[Any]] = []
    col_widths: list[float] = []
    for col in col_keys:
        cell: list[Any] = []
        widest = 0.0
        for content in sorted(columns[col], key=_order):
            kind = content.get("presentationType")
            if kind == "figure":
                figure = registries["figures"][content["figureRef"]]
                asset = figure.get("assetRef")
                asset_path = _resolve_asset(asset_dir, asset) if asset else Path("")
                if asset and asset_path.is_file():
                    image = Image(str(asset_path))
                    source_width = figure.get("sourceWidth")
                    source_height = figure.get("sourceHeight")
                    if source_width and source_height:
                        scale = min(1.0, 455 / float(source_width), 520 / float(source_height))
                        draw_w = float(source_width) * scale
                        draw_h = float(source_height) * scale
                    else:
                        scale = min(1.0, 455 / image.imageWidth, 520 / image.imageHeight)
                        draw_w = image.imageWidth * scale
                        draw_h = image.imageHeight * scale
                    image.drawWidth = draw_w
                    image.drawHeight = draw_h
                    image.hAlign = "CENTER"
                    cell.append(image)
                    widest = max(widest, draw_w)
                else:
                    report.warnings.append(f"Missing figure asset in side-by-side group: {figure.get('id')}")
            elif kind in {"paragraph", "note", "quote", "example", "warning"}:
                text = str(content.get("textContent") or "")
                if text.strip():
                    cell.append(Paragraph(_markup(text.strip()), styles["side-cell"]))
            elif kind == "list":
                for item in sorted(content.get("listItems", []), key=_order):
                    marker = _list_marker(str(item.get("marker", "-")))
                    cell.append(Paragraph(_markup(f"{marker} {item.get('text', '')}".strip()), styles["side-cell"]))
        col_flowables.append(cell)
        col_widths.append(widest or 60)
    # 列宽：按各列最宽图原尺寸比例分配版心宽（455pt），无图列给保底宽度。
    total = sum(col_widths)
    avail = 455 - 8 * len(col_keys)  # 单元格左右 padding
    if total <= 0:
        col_widths = [avail / len(col_keys)] * len(col_keys)
    elif total <= avail:
        col_widths = [w * avail / total for w in col_widths]
    else:
        col_widths = [w * avail / total for w in col_widths]
    grid = Table([col_flowables], colWidths=col_widths)
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(KeepTogether([grid]))
    story.append(Spacer(1, 4))


def _append_node(story: list[Any], node: dict[str, Any], registries: dict[str, dict[str, dict[str, Any]]], styles: dict[str, Any], font: str, report: PDFRenderReport, asset_dir: Path, colors: Any, Table: Any, TableStyle: Any, Paragraph: Any, Spacer: Any, Image: Any, marker_factory: Any = None, PageBreak: Any = None, example_default: str = "frame", example_leading: bool = False) -> None:
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
        _append_content_sequence(story, node.get("contentElements", []), registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image)
        _append_nodes(story, node.get("children", []), registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default)
        return
    heading_style = styles["section"] if depth == 1 else styles["subclause"] if depth >= 3 else styles["clause"] if depth else styles["front"]
    if node.get("exampleContent"):
        # 附录编写示例块（GB/T 20001 表框/图框内容，CSM-OCR-006）：框内第一个
        # 无编号节点是示例文档真实标题（黑体居中）；其余节点——示例内部编号
        # 标题（如 4 技术要求）以及被 OCR 误提升的无编号列表残留——一律黑体
        # 顶格左对齐，与正文章条（12pt 黑体）区分。
        heading_style = styles["example-title"] if (example_leading and not number) else styles["example-content"]
    elif not number and title.replace(" ", "") in {"前言", "引言", "参考文献", "索引"}:
        # GB/T 1.1-2020 Appendix F (Table F.1): 前置标题三号黑体居中（GBT-FM2）。
        heading_style = styles["front-title"]
    if marker_factory:
        story.append(marker_factory(node))
    story.append(Paragraph(_markup(heading), heading_style))
    _append_content_sequence(story, node.get("contentElements", []), registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image)
    children = node.get("children", [])
    if children:
        if node.get("exampleContent"):
            # 示例文档内部层级扁平化（2026-08-31，GB_T_20001.6-2017 附录
            # 规程标准编写示例）：示例文档自身的 5 → 5.1 → 5.4.1 章节树也是
            # exampleContent 标记的兄弟节点，走 _append_nodes 的分组逻辑会再
            # 包一层 _example_box → Table 套 Table：reportlab 表格单元格内
            # 的表格不能跨页拆分，整表高度超帧 → LayoutError（36 行 x 1194pt
            # 撞 688pt 帧高）。示例内部标题/内容逐节点直接追加进当前框
            # （黑体顶格 example-content），不产生嵌套框。
            for child in children:
                _append_node(story, child, registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default)
        else:
            _append_nodes(story, children, registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default)


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


def _cover_banner_text(standard_number: str) -> str:
    """Derive the cover banner from the standard-number prefix.

    规则对应: GBT-L03（封面横幅）——国家/行业/地方/团体/企业标准横幅各不相同：
    GB → 中华人民共和国国家标准；JB/QB 等行业标准 → 中华人民共和国××行业标准
    （机械、轻工…按前缀映射）；DB → ××地方标准；T/ → 团体标准；Q/ → 企业标准。
    """
    number = re.sub(r"\s+", "", standard_number).upper()
    if number.startswith(("GB/T", "GB ", "GB—", "GBZ", "GB")):
        return "中华人民共和国国家标准"
    industry = {
        "JB": "机械",
        "QB": "轻工",
        "QC": "汽车",
        "NJ": "农机",
        "YB": "黑色冶金",
        "YS": "有色金属",
        "SH": "石油化工",
        "HG": "化工",
        "DL": "电力",
        "MT": "煤炭",
        "JT": "交通",
        "TB": "铁道",
        "MH": "民用航空",
        "NY": "农业",
        "SC": "水产",
        "LY": "林业",
        "WS": "卫生",
        "YY": "医药",
        "MZ": "民政",
        "GA": "公共安全",
        "HJ": "生态环境",
        "QX": "气象",
        "WH": "文化",
        "TY": "体育",
        "JY": "教育",
        "GM": "密码",
    }
    prefix = re.match(r"^([A-Z]{1,2})/", number)
    if prefix and prefix.group(1) in industry:
        return f"中华人民共和国{industry[prefix.group(1)]}行业标准"
    if number.startswith("DB"):
        return "中华人民共和国地方标准"
    if re.match(r"^T/", number):
        return "团体标准"
    if re.match(r"^Q/", number):
        return "企业标准"
    return ""


def _standard_prefix(standard_number: str) -> str:
    """Extract the standard-number prefix used for emblem lookup.

    规则对应: GEN-018（封面徽标按标准类型分派）。归一化空格后取文件代号
    前缀：GB/T、GB/Z、GB（国家）；JB/QB/QC/SJ/DL/NY…（行业）；DB（地方）；
    T/（团体）；Q/（企业）。企业/团体标准的斜杠属于代号本身，保留。
    """
    number = re.sub(r"\s+", "", standard_number).upper()
    m = re.match(r"^(GB/T|GB/Z|GB|DB|T/|Q/|[A-Z]{1,2}/?)", number)
    return m.group(1) if m else ""


def _cover_emblem_path(
    standard_number: str,
    profile: dict[str, Any],
    profile_file: Path,
) -> Path | None:
    """Resolve the cover emblem image for a standard-number prefix.

    规则对应: GEN-018/GBT-L02——封面大图标按标准类型从固定位置读取（如
    GB_logo.png、JB_logo.png、company_logo.png），每类标准一条独立映射，
    互不影响；不再采用从 PDF 提取的 coverBadge 图块。mapping 最长前缀
    优先匹配；文件缺失回退 default；再缺失返回 None（不绘制）。

    The profile declares the emblems directory relative to the profile file;
    the mapping is prefix -> file name.  This function only *resolves* the
    path — the caller decides whether to draw it.
    """
    emblems = profile.get("emblems") or {}
    directory = Path(profile_file).resolve().parent / str(emblems.get("directory", "emblems"))
    mapping = emblems.get("mapping") or {}
    default_name = str(emblems.get("default", "default_logo.png"))
    number = re.sub(r"\s+", "", standard_number).upper()
    # Longest-prefix match first (GB/T before GB), then the file existence
    # fallback chain: mapped file -> default -> None.
    chosen = ""
    for prefix in sorted(mapping, key=len, reverse=True):
        if number.startswith(prefix):
            chosen = str(mapping[prefix])
            break
    for name in (chosen, default_name):
        if not name:
            continue
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


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
    # 规则对应: GBT-L03（封面横幅）——优先用元数据 banner；否则按 standard-number
    # 前缀推导标准层级（GB=国家、JB/QB/DB 等行业与地方、T/=团体、Q/=企业）。
    banner = common.get("banner", "") or _cover_banner_text(str(standard.get("standardNumber", "")))
    result.extend([Spacer(1, 34), CoverBanner(banner), Spacer(1, 30), Paragraph(_markup(standard_number), cover_number)])
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


def _list_marker(marker: str) -> str:
    """GB/T 1.1-2020 6.6.3 列项符号归一。

    - 破折号族（-、—、——、———、– 等 OCR 长度/全半角变体）→ ——（第一层次）；
    - • → ·（第二层次间隔号）。
    解析层多数派统一未覆盖的平手列表（如 ['-', '—']、['———', '————']）在
    渲染层兜底归一，保证同一列表视觉一致（GBT-C12）。
    """
    if marker and all(ch in "-—–" for ch in marker):
        return "——"
    if marker == "•":
        return "·"
    return marker


def _ocr_l_one(markers: list[str]) -> bool:
    """OCR 常把字母 l）误读为数字 1）（GBT-C12）。

    同一列表中其余项均为字母编号、且只有一个数字 1）时判定为 l）：
    真子列表（1)、2)、3)…）不会触发；单条 "a) + 1)" 也保留原样。
    """
    letters = [m for m in markers if re.match(r"^[A-Za-z][)）]$", m)]
    digit_ones = [m for m in markers if m in ("1)", "1）")]
    return bool(digit_ones) and len(letters) >= 2 and len(letters) + len(digit_ones) == len(markers)


# 表注行（GB_3100-2026 表1/表4 型）：MinerU 把表注整进表内最后一行合并
# 单元格，以「注N：」开头；渲染按表内注版式拆行居左（2026-09-02）。
_TABLE_NOTE_CELL_RE = re.compile(r"^注\s*\d*\s*[:：]")


def _split_table_note_parts(cell_text: str) -> list[str]:
    """把表注行单元格拆成每条注独立文本（2026-09-02，GB_3100-2026 表1/表4）。

    MinerU 把表注整进表末合并单元格：「注1：…注2：…」连排、跨页吸收回表内的
    续注以 <br> 分隔。按「注N：」边界拆分；行内 <br>（注6 续句换行）先转
    \\x00BR\\x00 哨兵保留，尾部哨兵（下一条注前的换行）整段剥掉——只
    strip NUL 会留下 "BR" 字面文本（哨兵是 \\x00BR\\x00 三字符，2026-09-02
    表4 注7~注10 实测泄漏成 Ⓡ-like 字符）。
    """
    parts: list[str] = []
    for part in re.split(r"(?=注\s*\d*\s*[:：])", cell_text.replace("<br>", "\x00BR\x00")):
        part = re.sub(r"(?:\x00BR\x00)+$", "", part).strip("\x00").strip()
        if part:
            parts.append(part)
    return parts


def _footnote_superscripts(text: str) -> str:
    """脚注标记渲染为上角标——正文/图脚注安全版（GBT-X04 执行侧）。

    GB/T 1.1-2020 9.12.2：图表脚注用小写拉丁字母 a)、b) 上标，脚注由标记与
    解释成对组成。处理：
    - 解释行行首标记："a 填写行业标准代号。" / "a国家标准…" → ᵃ；
    - 汉字后全角小写字母（OCR 还原的标记）→ 上角标。
    正文版刻意**不**做"汉字后半角小写单字母"（避免误伤变量/列项引用如
    "转速n，"、"a)中所述"）；公式变量行（"n —转速" 字母后是破折号）不触发。
    """
    # 行首脚注解释标记 + 空格 + 汉字；排除公式变量行（字母后是 — 破折号）。
    text = re.sub(r"^([ａ-ｚa-z])(?:[ \u3000]+)([\u4e00-\u9fff])", "\x00SUP\x00\\1\x00/SUP\x00 \\2", text)
    # 行首脚注解释标记后紧跟汉字（OCR 丢了分隔空格）。
    text = re.sub(r"^([ａ-ｚa-z])(?=[\u4e00-\u9fff])", "\x00SUP\x00\\1\x00/SUP\x00", text)
    # 句末标点后紧跟的下一条脚注解释标记（MinerU 常把 "a 说明。 b说明。" 合并
    # 成一段，2026-08-31 GB_T_1.1-2020 附录 E）："。 b行业…" → ᵇ。
    text = re.sub(r"(?<=[。；])([ \u3000\n]*)([ａ-ｚa-z])(?=[\u4e00-\u9fff])", "\\1\x00SUP\x00\\2\x00/SUP\x00", text)
    # 汉字后全角小写字母（全角必为 OCR 标记，非正文内容）。
    text = re.sub(r"(?<=[\u4e00-\u9fff])([ａ-ｚ])", "\x00SUP\x00\\1\x00/SUP\x00", text)
    return text


# 半上标字形（²³¹）在 <super> 内归一为数字：字形本身已上标，进 <super> 会双重
# 缩小（Noto Serif CJK SC 缺 ⁰⁵⁶⁷⁸⁹⁻⁺ 字形，¹²³⁴ 有但不应与普通数字混用）。
_SUP_GLYPH_TO_DIGIT = {"²": "2", "³": "3", "¹": "1"}


def _table_cell_superscripts(text: str) -> str:
    """表格单元格/表注的脚注引用标记渲染为上角标（GBT-C18 / GBT-X04）。

    "a 说明" 列出。OCR 把上角标还原为普通字符（半角 a 或全角 ａ），此处：
    - 表注行行首的 "a "（标记+空格）→ 上角标；
    - 汉字后紧跟的全角小写字母 ａ-ｚ → 上角标（全角必为 OCR 标记）；
    - 汉字后紧跟的半角小写单字母 → 上角标，但排除可能的小写单字母单位
      （m/s/g/l/t/h）与列项引用 ")"（避免误伤 "规格mm"/"长度m"/"a)中所述"）。
    行首规则只用小写（GB/T 1.1 表脚注 a/b/c；大写如 "A 相" 是内容，2026-08-31）。
    """
    text = _footnote_superscripts(text)
    # 汉字后半角小写单字母（排除单位与 ")" 列项引用）
    text = re.sub(
        r"(?<=[\u4e00-\u9fff])([abcefijknopqruvwxyz])(?![)\u4e00-\u9fffA-Za-z])",
        "\x00SUP\x00\\1\x00/SUP\x00",
        text,
    )
    # 上角标还原（2026-09-02，GB_3100-2026 表2/表3/附录B 等）：MinerU 文本抽取
    # 把上标拍平成普通字符——s−1→s⁻¹、N/m2→N/m²、1030→10³⁰、10-2→10⁻²、
    # 10²4→10²⁴。只作用于表格单元格（上下文受限，单元格几乎必是单位/量值），
    # 正文不做（正文的平拍指数要么带 <sup> 标签、要么是 LaTeX，各自处理）。
    # 1) 单位字母后 −/[-] 数字（s−1、Ω−1、s-1）——字母限定小写+希腊防误伤
    #    "A-1" 类代号；数字后不再跟数字（"s-10" 整串上标由 {1,2} 覆盖）。
    text = re.sub(r"(?<=[a-zμΩ])[−-](\d{1,2})(?![0-9])", "\x00SUP\x00−\\1\x00/SUP\x00", text)
    # 2) 10 的负幂：10-1→10⁻¹、10-30→10⁻³⁰（"10-2" 前面是数字 0，规则 1 不命中）。
    text = re.sub(r"10[−-](\d{1,2})(?![0-9])", "10\x00SUP\x00−\\1\x00/SUP\x00", text)
    # 3) 10 的正幂：1030→10³⁰、1024→10²⁴、109→10⁹、102→10²；100→"10"+"0"
    #    （首位数 0）不猜（防 "100"→10⁰）。
    text = re.sub(r"10([1-9]\d{0,2})(?![0-9])", "10\x00SUP\x00\\1\x00/SUP\x00", text)
    # 4) 半上标混合：10²4→10²⁴、10³0→10³⁰（MinerU 部分识别 Unicode 上标）；
    #    ²³¹ 归一为数字再进 <super>（字形本身已上标，双重缩小且与后续普通
    #    数字混排不齐）。
    text = re.sub(
        r"10([²³¹])(\d)",
        lambda m: f"10\x00SUP\x00{_SUP_GLYPH_TO_DIGIT[m.group(1)]}{m.group(2)}\x00/SUP\x00",
        text,
    )
    # 5) 单位字母后平印 2/3：N/m2→N/m²、cm3→cm³（排除大写 "A2" 纸型等）。
    text = re.sub(r"(?<=[a-zμΩ])2(?![0-9A-Za-z])", "\x00SUP\x002\x00/SUP\x00", text)
    text = re.sub(r"(?<=[a-zμΩ])3(?![0-9A-Za-z])", "\x00SUP\x003\x00/SUP\x00", text)
    return text


_CLAUSE_NUMBER_RE = r"(?:\d+\.){1,4}\d+|[A-Z]\.\d+(?:\.\d+)*"
# 条号后允许的正文首字符：汉字、全角/半角括号、引号族（“”‘’「『《〈）。
# 引号必须包含——MinerU 常把 9.4.2.2“尽可能”这类裸条正文以引号开头，
# 若不在集合内则该行既不顶格、编号后也不补空格（GB_T_1.1-2020 实测）。
_CLAUSE_AFTER = r"\u4e00-\u9fff（(“”‘’「『《〈[('\""


def _clause_leading_number(text: str) -> str | None:
    """Return the leading clause number when a body paragraph starts with one.

    Untitled clauses (裸条) live in the CSM as bare paragraphs whose first
    line begins with the clause number ("5.5.2承压零件应做…").  GB/T 1.1
    typesets clause numbers flush left (顶格), so such paragraphs must not
    take the two-Han-character body first-line indent.  The lookahead is
    kept identical to _markup()'s clause-line normalisation so the two
    decisions stay consistent.

    规则对应: GBT-B02（条编号顶格编排，编号后空一个汉字接排）。
    """
    match = re.match(
        rf"^({_CLAUSE_NUMBER_RE})(?=[ \u3000]*[{_CLAUSE_AFTER}])",
        str(text).strip(),
    )
    return match.group(1) if match else None


def _append_content(story: list[Any], content: dict[str, Any], registries: dict[str, dict[str, dict[str, Any]]], styles: dict[str, Any], font: str, report: PDFRenderReport, asset_dir: Path, colors: Any, Table: Any, TableStyle: Any, Paragraph: Any, Spacer: Any, Image: Any) -> None:
    # 规则对应: GEN-032（表格题注拆分：居中题注 + 右对齐单位行）、GBT-B04（列项缩进）、
    # GBT-B10（注小五号宋体）、GBT-X06（公式另行居中、编号右对齐）、GBT-X01/B06（图与图题）。
    from reportlab.platypus import KeepTogether

    kind = content.get("presentationType")
    if kind in {"paragraph", "quote", "warning", "example"}:
        text = str(content.get("textContent", ""))
        # GB/T 1.1 figure caption paragraph: "图 2 尼龙丝卷曲判定" 等题注被
        # MinerU 抽成独立段落时按图题渲染（黑体居中，同 figure caption）。
        figure_caption_match = re.match(r"^(图\s*\d+\.?\d*[^\n]*)$", text.strip())
        # GB/T 1.1 table caption block: "表 X.Y 题名\n单位为毫米" — the unit
        # line renders small and flush right, directly above the table frame.
        caption_match = re.match(r"^(表\s*[A-Z]?\d*\.?\d*[^\n]*)\n(单位为[^\s]{1,4})\s*$", text.strip())
        unit_only = re.fullmatch(r"单位为[^\s]{1,4}", text.strip())
        if figure_caption_match:
            story.append(Paragraph(_markup(figure_caption_match.group(1).strip()), styles["caption"]))
        elif caption_match:
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
            # Untitled clause paragraphs (bare text starting with the clause
            # number) render flush left per GBT-B02; ordinary body text keeps
            # the two-Han-character first-line indent.
            style = styles["body-flush"] if _clause_leading_number(text) else styles["body"]
            story.append(Paragraph(_markup(_footnote_superscripts(text)), style))
    elif kind == "note":
        story.append(Paragraph(_markup(content.get("textContent", "")), styles["note"]))
    elif kind == "list":
        items = sorted(content.get("listItems", []), key=_order)
        markers = [str(item.get("marker", "-")) for item in items]
        ocr_l_one = _ocr_l_one(markers)
        for item in items:
            marker = _list_marker(str(item.get("marker", "-")))
            if ocr_l_one and marker in ("1)", "1）"):
                marker = "l）"
            # 数字编号与间隔号属于第二层次（list-sub），其余属第一层次（list）。
            list_style = styles["list-sub"] if (marker in ("·",) or marker.rstrip(")）").isdigit()) else styles["list"]
            story.append(Paragraph(_markup(f"{marker} {item.get('text', '')}"), list_style))
    elif kind == "table":
        _append_table(story, registries["tables"][content["tableRef"]], styles, colors, Table, TableStyle, Paragraph, asset_dir=asset_dir, Image=Image)
    elif kind == "formula":
        formula = registries["formulas"][content["formulaRef"]]
        asset = formula.get("assetRef")
        source_image = _resolve_asset(asset_dir, asset) if asset else Path("")
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
            story.append(Paragraph(_markup(_latex_to_text(formula.get("rawText", ""))), styles["formula"]))
        if formula.get("number"):
            story.append(Paragraph(_markup(str(formula["number"])), styles["caption"]))
    elif kind == "figure":
        figure = registries["figures"][content["figureRef"]]
        asset = figure.get("assetRef")
        asset_path = _resolve_asset(asset_dir, asset) if asset else Path("")
        if asset and asset_path.is_file():
            image = Image(str(asset_path))
            # 图尺寸：优先使用抽取时从源 PDF 记录的原始版面尺寸
            # （sourceWidth/sourceHeight，pt；_stamp_figure_source_sizes 在
            # 流水线 finalize 阶段写入），使渲染图与原图尺寸相当（GEN-076）。
            # 无记录时按图片固有尺寸（72dpi）缩放，但**只缩小不放大**——
            # MinerU 裁剪图常以高于原版的像素密度导出，放大会远超原图尺寸。
            source_width = figure.get("sourceWidth")
            source_height = figure.get("sourceHeight")
            if source_width and source_height:
                scale = min(1.0, 455 / float(source_width), 520 / float(source_height))
                draw_w = float(source_width) * scale
                draw_h = float(source_height) * scale
            else:
                scale = min(1.0, 455 / image.imageWidth, 520 / image.imageHeight)
                draw_w = image.imageWidth * scale
                draw_h = image.imageHeight * scale
            image.drawWidth = draw_w
            image.drawHeight = draw_h
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


def _append_table(story: list[Any], table: dict[str, Any], styles: dict[str, Any], colors: Any, Table: Any, TableStyle: Any, Paragraph: Any, *, asset_dir: Path | None = None, Image: Any = None) -> None:
    # 规则对应: GBT-B07（表编号表题居中置于表上、表头框线、数字小五号宋体）、
    # GBT-X02（不准许分表/表中套表；转页重复表头 repeatRows；表中图）、GEN-033（无编号无题名不输出题注）。
    from reportlab.platypus import Spacer

    number = str(table.get("number") or "").strip()
    caption = str(table.get("caption") or "").strip()
    unit = str(table.get("unit") or "").strip()
    # A table with neither number nor caption gets no caption line at all
    # (otherwise a lone "表" character would appear above the table).
    if number or caption:
        story.append(Paragraph(_markup(f"表{number} {caption}".strip()), styles["caption"]))
    # GB/T 1.1 表题注块：单位行（"单位为毫米"）小号右对齐，紧贴表格上方
    # （GEN-032；table-unit 样式 alignment=2 右对齐、spaceAfter=0 贴表框）。
    if unit:
        from reportlab.lib.styles import ParagraphStyle
        unit_style = styles.get("table-unit") or ParagraphStyle(
            "gbt-table-unit", parent=styles["body"], alignment=2, fontSize=9, leading=12, spaceAfter=0, firstLineIndent=0,
        )
        story.append(Paragraph(_markup(f"单位为{unit}"), unit_style))
    rows = sorted(table.get("rows", []), key=lambda row: row["rowIndex"])

    cell_image_re = re.compile(r"!\[(?:[^\]]*)\]\(([^)]+)\)")
    # 表注行样式（2026-09-02，GB_3100-2026 表1/表4 注行）：GB/T 1.1 表内注
    # 居左、首行空两格、小五号；GBT-B09 的"表内文字居中"对注行是例外。
    from reportlab.lib.styles import ParagraphStyle

    table_note_style = ParagraphStyle(
        "gbt-table-note",
        parent=styles["table"],
        alignment=0,
        firstLineIndent=2 * styles["table"].fontSize,
        leftIndent=0,
        spaceAfter=0,
    )
    # 表中图原始版面尺寸（pt）：_stamp_figure_source_sizes 在流水线 finalize
    # 写入 table["cellImageSizes"] = {ref: [w, h]}，渲染端按原尺寸（上限
    # 单元格宽、不放大）显示，使表中图与原图尺寸相当（GEN-076 / GBT-X02）。
    cell_image_sizes = table.get("cellImageSizes") or {}

    def _render_cell(cell_text: str, cell_width: float) -> list[Any]:
        # 单元格行结构（merge 阶段从源文本层恢复的 <br>，如 表1 "术语和定义
        # <br>……<br>程序确立…"）在 _markup 转义后恢复为真实 <br/>，使省略号
        # 等独占一行（GBT-B08 表格版式）。\x00BR\x00 哨兵走 _markup 不被转义。
        # 表中图（GBT-X02）：mineru_html 把单元格内 <img> 附成
        # "![](assets/images/<hash>.jpg)" 文本，此处拆出为单元格内 Image
        # flowable（优先按原版面尺寸、上限单元格宽缩放、不放大），图片前后
        # 文本各自成段。
        flowables: list[Any] = []
        # 表注行（2026-09-02，GB_3100-2026 表1/表4）：单元格以「注N：」开头时，
        # 把合并进同一格的 注1：…注2：…（以及跨页吸收回表内的续注，<br> 分隔）
        # 拆成每条注独立一段，居左、首行空两格（GB/T 1.1 表内注版式）。
        stripped_note = cell_image_re.sub("", cell_text).strip()
        if _TABLE_NOTE_CELL_RE.match(stripped_note):
            for note_part in _split_table_note_parts(cell_text):
                flowables.append(
                    Paragraph(
                        _markup(_table_cell_superscripts(note_part)).replace("\x00BR\x00", "<br/>"),
                        table_note_style,
                    )
                )
            return flowables
        position = 0
        for match in cell_image_re.finditer(cell_text):
            text_part = cell_text[position:match.start()]
            if text_part.strip():
                marked = text_part.replace("<br>", "\x00BR\x00")
                flowables.append(Paragraph(_markup(_table_cell_superscripts(marked)).replace("\x00BR\x00", "<br/>"), styles["table"]))
            if Image is not None and asset_dir is not None:
                image_path = _resolve_asset(asset_dir, match.group(1))
                if image_path.is_file():
                    image = Image(str(image_path))
                    src = cell_image_sizes.get(match.group(1))
                    if src:
                        scale = min(
                            1.0,
                            src[0] / image.imageWidth,
                            src[1] / image.imageHeight,
                            (cell_width - 8) / image.imageWidth,
                            200 / image.imageHeight,
                        )
                    else:
                        scale = min(1.0, (cell_width - 8) / image.imageWidth, 200 / image.imageHeight)
                    image.drawWidth = image.imageWidth * scale
                    image.drawHeight = image.imageHeight * scale
                    image.hAlign = "CENTER"
                    flowables.append(image)
            position = match.end()
        tail = cell_text[position:]
        if tail.strip() or not flowables:
            marked = tail.replace("<br>", "\x00BR\x00")
            flowables.append(Paragraph(_markup(_table_cell_superscripts(marked)).replace("\x00BR\x00", "<br/>"), styles["table"]))
        return flowables

    if not rows or not rows[0].get("cells"):
        return
    col_count = max(len(sorted(row.get("cells", []), key=lambda cell: cell["colIndex"])) for row in rows)
    # 列宽按内容分配（2026-09-03，通用规则：尽量利用版面宽度）：每列需求 =
    # 该列最宽单元格的自然宽度（CJK≈1em、拉丁≈0.55em；colspan 摊分；通栏
    # 注行/单长格不参与），按需求比例把版心宽 455pt 全部分配（列宽和恰等于
    # 版面宽），保底 24pt 防空列退化。跨列单元格的图片按跨列总宽缩放。
    col_widths = _table_column_widths(rows, col_count, styles["table"].fontSize, cell_image_sizes, cell_image_re)

    def _cell_render_width(cell: dict[str, Any]) -> float:
        colspan = int(cell.get("colspan", 1) or 1)
        start = cell["colIndex"]
        return sum(col_widths[start:start + colspan])

    data = [[_render_cell(cell.get("text", ""), _cell_render_width(cell)) for cell in sorted(row.get("cells", []), key=lambda cell: cell["colIndex"])] for row in rows]
    grid = Table(data, colWidths=col_widths, repeatRows=sum(1 for row in rows if row.get("isHeader")))
    commands: list[tuple[Any, ...]] = [("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if rows and rows[0].get("isHeader"):
        commands.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F2F2")))
    for row in rows:
        for cell in row.get("cells", []):
            if cell.get("rowspan", 1) > 1 or cell.get("colspan", 1) > 1:
                commands.append(("SPAN", (cell["colIndex"], cell["rowIndex"]), (cell["colIndex"] + cell.get("colspan", 1) - 1, cell["rowIndex"] + cell.get("rowspan", 1) - 1)))
        # OCR often loses the colspan of a full-width note row ("注：…" spread
        # over every column).  A lone long text cell left unmerged collapses to
        # one narrow column, wraps into dozens of lines and can exceed the page
        # frame (reportlab LayoutError).  Span it across the whole grid so the
        # note flows at full width.
        cells = sorted(row.get("cells", []), key=lambda c: c["colIndex"])
        # 排除表中图标记（![](...)）后再判断"仅一个长文本格"——纯图单元格
        # 不应触发通栏 SPAN。
        plain_text = lambda cell: cell_image_re.sub("", str(cell.get("text", "")))
        filled = [c for c in cells if plain_text(c).strip()]
        if len(cells) > 2 and len(filled) == 1 and len(plain_text(filled[0])) >= 20:
            r = row["rowIndex"]
            commands.append(("SPAN", (0, r), (-1, r)))
    grid.setStyle(TableStyle(commands))
    story.extend([grid, Spacer(1, 6)])


def _cell_text_natural_width(text: str, font_size: float) -> float:
    """单元格文本自然宽度估计（2026-09-03，GBT-B07 通用列宽规则执行侧）。

    按行（<br>/哨兵/换行）拆分取最长行；字符宽度：CJK 及全角（U+2E80 起）
    ≈ 1em、拉丁字母/数字 ≈ 0.55em、空白 ≈ 0.3em、其它 ≈ 0.5em；
    <sup>/<sub>/<super> 标签剥掉后内容按普通字符计（上标数字窄，近似拉丁）。
    返回 pt。
    """
    widest = 0.0
    for line in re.split(r"<br>|\x00BR\x00|\n", str(text)):
        stripped = re.sub(r"<[^>]+>", "", line)
        stripped = re.sub(r"\x00(?:SUP|SUB|GAP)\x00", "", stripped)
        width = 0.0
        for ch in stripped:
            if ch.isspace():
                width += 0.3
            elif ord(ch) >= 0x2E80:  # CJK 部首/统一表意文字/全角/兼容表意
                width += 1.0
            elif ch.isascii() and ch.isalnum():
                width += 0.55
            else:
                width += 0.5
        widest = max(widest, width)
    return widest * font_size


def _table_column_widths(
    rows: list[dict[str, Any]],
    col_count: int,
    font_size: float,
    cell_image_sizes: dict[str, list[float]],
    cell_image_re: re.Pattern[str],
    frame_width: float = 455.0,
    floor: float = 24.0,
) -> list[float]:
    """按内容分配表格列宽（2026-09-03，通用规则：尽量利用版面宽度）。

    每列需求 = 该列最宽单元格的自然宽度（CJK≈1em、拉丁≈0.55em，见
    _cell_text_natural_width）；colspan 内容按跨列数摊分到各列；整行通栏的
    注行（colspan=全部）与 OCR 丢 colspan 的单长格（渲染端 SPAN 全宽）不挤占
    单列需求；表格图片按原版面宽度计。按需求比例把版心宽（frame_width，
    默认 455pt）全部分配下去——列宽和恰等于版面宽度（尽量利用），保底
    floor（24pt）防空列/空单元格退化。返回与 col_count 等长的列宽列表。
    """
    col_demand = [0.0] * col_count
    for row in rows:
        cells = sorted(row.get("cells", []), key=lambda cell: cell["colIndex"])
        plain_text = lambda cell: cell_image_re.sub("", str(cell.get("text", "")))
        filled = [c for c in cells if plain_text(c).strip()]
        lone_full = len(cells) > 2 and len(filled) == 1 and len(plain_text(filled[0])) >= 20
        for cell in cells:
            text = str(cell.get("text", ""))
            colspan = int(cell.get("colspan", 1) or 1)
            if colspan >= col_count or lone_full:
                continue
            # 渲染端 _markup 会把 $...$ LaTeX 拍平为可读文本；需求估算同样拍平，
            # 否则 LaTeX 命令噪声（\mathrm { D a } 等）把列需求撑大（表4 道尔顿行）。
            text = re.sub(r"\$([^$\n]+)\$", lambda m: _latex_to_text(m.group(1)), text)
            demand = _cell_text_natural_width(text, font_size)
            for m in cell_image_re.finditer(text):
                src = cell_image_sizes.get(m.group(1))
                demand = max(demand, src[0] if src else 60.0)
            per_col = demand / colspan
            start = cell["colIndex"]
            for c in range(start, min(start + colspan, col_count)):
                col_demand[c] = max(col_demand[c], per_col)
    col_widths = [max(d, floor) for d in col_demand]
    total = sum(col_widths)
    if total <= 0:
        return [frame_width / col_count] * col_count
    return [w * frame_width / total for w in col_widths]


def _latex_sup_content(content: str) -> str:
    """上标组内容归一：去 ~ 与首尾空白、连字符转 U+2212 减号（字体有字形）。

    reportlab <super> 内仍用普通数字/字母，由渲染端统一抬高缩小；
    不用 Unicode 上标字形（Noto Serif CJK SC 缺 ⁰⁵⁶⁷⁸⁹⁻⁺，2026-09-02）。
    """
    return content.replace("~", "").strip().replace("-", "−")


def _latex_balanced_scan(text: str, start: int) -> tuple[str, int] | None:
    r"""从 start（指向 '{'）扫描配平的组，返回 (组内内容, 组后下标)。

    支持嵌套花括号（MinerU 的 \mathrm { { F } }、\frac { ... } { ... } 里
    再嵌 \frac）。无法配平（OCR 截断）时返回 None——留给外层兜底清理。
    """
    if start >= len(text) or text[start] != "{":
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
    return None


_LATEX_NESTED_CMD_RE = re.compile(r"\\([A-Za-z]+)\s*\{")
_LATEX_WRAPPER = frozenset(
    {"mathrm", "mathbf", "mathit", "mathsf", "mathtt", "pmb", "textbf",
     "textit", "textrm", "operatorname", "boldsymbol", "rm", "it", "bf",
     "overline", "underline", "bm", "text"}
)


def _latex_expand_nested(text: str) -> str:
    r"""把带嵌套花括号的 LaTeX 命令组展开（支持 frac 嵌套，2026-09-03）。

    原有 flattener 的正则只认单层花括号：\mathrm { { F } }、\frac 参数里
    再嵌 \frac/\mathrm 时匹配失败，命令噪声直接泄漏（9.4.4.4/9.4.5.2 型）。
    此处用配平扫描逐命令展开：wrapper 命令取内容（剥冗余花括号/空白），
    \frac 转 (a)/(b)；返回仍含简单单层组的文本，交给原 flattener 收尾。
    """
    out: list[str] = []
    pos = 0
    n = len(text)
    while pos < n:
        m = _LATEX_NESTED_CMD_RE.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        out.append(text[pos:m.start()])
        name = m.group(1)
        inner_start = m.end() - 1  # 指向 '{'
        scanned = _latex_balanced_scan(text, inner_start)
        if scanned is None:
            # 配平失败：保留字面，由后续兜底清除命令名。
            out.append(text[m.start():m.end()])
            pos = m.end()
            continue
        inner, after = scanned
        if name == "frac":
            num_inner, num_after = _latex_balanced_scan(text, inner_start)
            # 第二个参数紧跟（可跨空白）
            j = num_after
            while j < n and text[j] in " \t":
                j += 1
            den_inner: str | None = None
            den_after = num_after
            if j < n and text[j] == "{":
                den_pair = _latex_balanced_scan(text, j)
                if den_pair is not None:
                    den_inner, den_after = den_pair
            if num_inner is not None and den_inner is not None:
                out.append(f"({_latex_expand_nested(num_inner)})/({_latex_expand_nested(den_inner)})")
                pos = den_after
                continue
            out.append(text[m.start():after])
            pos = after
            continue
        if name in _LATEX_WRAPPER:
            # 与旧 flattener 第 1 步一致：排版族命令参数内部空白剥除
            # （"\\mathrm { k P a }" -> "kPa"；内层命令已递归展开）。
            out.append(re.sub(r"\s+", "", _latex_expand_nested(inner)))
            pos = after
            continue
        # 未知命令：保留原样（含花括号组），交给原 flattener 处理。
        out.append(text[m.start():after])
        pos = after
    return "".join(out)


def _latex_to_text(latex: str) -> str:
    """Flatten a LaTeX math snippet into readable plain text for display.

    MinerU embeds inline math as literal LaTeX in prose ("$\\mathrm{~T~}$",
    "$K_{T}$").  reportlab has no math typesetter, so the command noise must
    not leak into the rendered PDF: \\mathrm/\\pmb wrappers are unwrapped,
    \\frac becomes a/b, common operators map to Unicode, and sub/superscripts
    are flattened.  Only affects display; SSIR/CSM keep the LaTeX source.

    规则对应: GBT-X06（数学公式另行居中编排；无法排版时以可读文本呈现）。
    """
    text = latex.strip()
    # 0) 嵌套花括号命令组展开（2026-09-03，GB_T_1.1-2020 9.4.4.4/9.4.5.2 型：
    #    \mathrm { { F } }、\frac 参数内再嵌 \frac/\mathrm 时旧正则匹配失败，
    #    命令噪声/冗余花括号直接泄漏进渲染文本）。
    text = _latex_expand_nested(text)
    # 1) \command{...} wrappers -> content (roman/bold/italic families);
    #    inner whitespace is dropped ("\mathrm { k P a }" -> "kPa").
    text = re.sub(
        r"\\(?:mathrm|mathbf|mathit|mathsf|mathtt|pmb|textbf|textit|textrm|operatorname|boldsymbol|rm|it|bf)\s*\{([^{}]*)\}",
        lambda m: re.sub(r"\s+", "", m.group(1)),
        text,
    )
    # 2) sub/superscripts: K_{T} -> K<sub>T</sub>, x^{2} -> x<super>2</super>.
    #    Leading whitespace before _ / ^ is consumed so MinerU's spaced
    #    "K _ { T }" does not leave "K T" in the display text.  The ^/_
    #    groups are emitted as reportlab super/sub sentinels (2026-09-02,
    #    GB_3100-2026 4.2 型：10^{-34} 若拍平为 "10-34" 会丢上标版式）。
    text = re.sub(
        r"\s*_\s*\{([^{}]*)\}",
        lambda m: "\x00SUB\x00" + m.group(1).replace("~", "").strip() + "\x00/SUB\x00",
        text,
    )
    text = re.sub(
        r"\s*\^\s*\{([^{}]*)\}",
        lambda m: "\x00SUP\x00" + _latex_sup_content(m.group(1)) + "\x00/SUP\x00",
        text,
    )
    text = re.sub(r"\s*_\s*([A-Za-z0-9])", r"\1", text)
    text = re.sub(r"\s*\^\s*([A-Za-z0-9])", lambda m: "\x00SUP\x00" + _latex_sup_content(m.group(1)) + "\x00/SUP\x00", text)
    # 3) \frac{a}{b} -> (a)/(b).
    text = re.sub(
        r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}",
        lambda m: f"({m.group(1).strip()})/({m.group(2).strip()})",
        text,
    )
    # 4) Common operators -> Unicode (leqslant before leq to avoid prefix match).
    for src, dst in (
        (r"\leqslant", "≤"),
        (r"\geqslant", "≥"),
        (r"\leq", "≤"),
        (r"\geq", "≥"),
        (r"\cdot", "·"),
        (r"\times", "×"),
        (r"\pm", "±"),
        (r"\sim", "～"),
        (r"\approx", "≈"),
        (r"\neq", "≠"),
        (r"\infty", "∞"),
        (r"\ldots", "…"),
        (r"\cdots", "…"),
        (r"\sqrt", "√"),
        (r"\deg", "°"),
        (r"\mu", "μ"),
        (r"\Omega", "Ω"),
        (r"\pi", "π"),
        (r"\partial", "∂"),
        (r"\Delta", "Δ"),
        (r"\sum", "Σ"),
    ):
        text = text.replace(src, dst)
    # 5) Drop any remaining \command, stray braces, tildes, backslashes.
    text = re.sub(r"\\[a-zA-Z]+\s*", "", text)
    text = text.replace("{", "").replace("}", "").replace("~", "").replace("\\", "")
    # 6) Tighten spacing: no spaces around binary operators (a · b -> a·b),
    #    inside parentheses, or around "/"; keep spaces around "=" for reading.
    text = re.sub(r"\s*([·×≤≥±≈≠/+−])\s*", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    # LaTeX 命令终止空格（\Delta V 里 \Delta 后、V 前的空格）在命令替换后
    # 残留——希腊字母与后随拉丁字母同属一个量符号（ΔV、μs、Ωm），排版无空格；
    # 拉丁-拉丁乘积（J s）的空格保留（真实原文有间隙）。
    text = re.sub(r"(?<=[ΔαβγδεζηθικλμνξοπρστυφχψωΩ]) (?=[A-Za-z])", "", text)
    # 7) MinerU 逐字符空格数字（"6 . 6 2 6 0 7 0 1 5"）收紧为规范数值
    #    （"6.62607015"；2026-09-02，GB_3100-2026 4.2 常量行）。
    text = re.sub(r"\s+([.,])\s*", r"\1", text)
    text = re.sub(r"(?<=\d) (?=\d)", "", text)
    return re.sub(r"\s+", " ", text).strip()


# 字面星号簇保护（GBT-C13 星号脚注、GB_T_1.1-2020 9.12.1 “*、**、***”、
# 9.7.3 “共*页”）：CommonMark 转义 \*（parser 不反转义、textContent 保留
# 反斜杠）与两侧都不是拉丁字母/数字的星号簇都是字面星号（而非 markdown
# 强调）。先保护为 \x00AST{n}\x00 哨兵，等 bold/italic 处理完再按簇长还原，
# 否则 “即\*、\*\*、\*\*\*” 会被 italic/bold 正则错配吞字。markdown 强调
# （*word*、**word**）两侧至少一侧是词字符，不受影响。
_LIT_STAR_RE = re.compile(r"(?<![A-Za-z0-9])\*+(?![A-Za-z0-9])")


def _protect_literal_stars(text: str) -> str:
    r"""把字面星号（转义 \* 与两侧非词字符簇）编码为 AST 哨兵。"""
    text = text.replace("\\*", "\x00AST1\x00")
    return _LIT_STAR_RE.sub(lambda m: f"\x00AST{len(m.group())}\x00", text)


def _restore_literal_stars(text: str) -> str:
    """把 AST 哨兵还原为对应长度的字面星号串。"""
    return re.sub(r"\x00AST(\d+)\x00", lambda m: "*" * int(m.group(1)), text)


def _markup(text: str) -> str:
    text = str(text)
    # Inline MinerU math ("$...$") is LaTeX; flatten it to readable text so
    # command noise ("\\mathrm{~T~}") does not leak into the rendered PDF.
    text = re.sub(r"\$([^$\n]+)\$", lambda m: _latex_to_text(m.group(1)), text)
    # OCR whitespace noise: collapse space runs ("、   32.4 V") and join
    # digit-group separators ("2 000 W" -> "2000 W").
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"(?<=\d) (?=\d)", "", text)
    # 字面星号保护（CommonMark 转义 \* 与两侧非词字符簇，GB_T_1.1-2020
    # 9.12.1 “\*、\*\*、\*\*\*”、9.7.3 “共\*页”）：parser 不反转义、
    # textContent 保留反斜杠；先保护为哨兵，escape/bold/italic 后还原成
    # 字面星号——防止反斜杠字面泄漏、* 被 italic 正则错配吞字。
    text = _protect_literal_stars(text)
    # Untitled clause numbers: MinerU leaves the spacing after the number
    # irregular ("5.3.1 泵…" vs "5.3.2泵…"); normalise to one Han gap
    # (GBT-B02 编号后空一个汉字接排). reportlab 把所有空白（含 U+3000）折叠
    # 成窄空格，无法表达"空一个汉字"——直接输出 GAP 哨兵（escape 后转白字中，
    # 同 CSM-OCR-003 术语间隔技术），视觉恰好 1em；lookahead 与
    # _clause_leading_number 共享 _CLAUSE_AFTER（含引号族）。
    text = re.sub(
        rf"(?m)^({_CLAUSE_NUMBER_RE})[ \u3000]*([{_CLAUSE_AFTER}])",
        lambda m: m.group(1) + "\x00GAP\x00" + m.group(2),
        text,
    )
    # Number-unit gap: 单位符号前应空四分之一汉字的间隙（GB/T 1.1-2020 10.4.6，
    # GBT-B12）。统一用不换行空格（\u00A0）实现，两端对齐时不会被拉伸成宽隙：
    # - 源文/OCR 已有空格（"50 Hz"）→ 转 \u00A0；
    # - 紧贴（"210mm"、"0.2℃"、"85K"、"15N"）→ 补插 \u00A0，消除同一文档
    #   间隙不一致（GB 3100 数值与单位间留一个空格）；
    # - 例外：% 前不留间隙（GB/T 15835-2011 示例 "34.05%"、"63%~68%"），已有
    #   空格也收紧；平面角度分秒 °′″ 紧跟数值（GBT-B12 例外，字符不在集合内）；
    #   分表/分图代号（"表2a"，GB/T 1.1 9.8.1.3 示例）不插间隙。
    text = re.sub(r"(?<=\d) (?=[A-Za-z℃Ωμµ])", "\u00A0", text)
    text = re.sub(r"(?<=\d) (?=%)", "", text)
    text = re.sub(r"(?<![图表]\d)(?<=\d)(?=[A-Za-z℃Ωμµ])", "\u00A0", text)
    # 术语中英文间隔（CSM-OCR-003）：reportlab 把所有空白（含 U+3000）折叠为
    # 窄空格，无法表达 GB/T 1.1 要求的"空一个汉字"；用白色汉字填充获得恰好
    # 1em 的不可见间隙（Noto Serif CJK SC 有该字形，不会渲染成 .notdef 方框）。
    text = re.sub(r"(?<=[\u4e00-\u9fff])\u3000(?=[A-Za-z])", "\x00GAP\x00", text)
    # Mid-paragraph newlines are natural source line wraps (MinerU 按行宽换行)，
    # not hard breaks: collapse them to a single space so the PDF re-wraps
    # instead of forcing a break ("……25%时，\n审查结论应为不通过" -> one paragraph).
    text = re.sub(r"[ \t\u3000]*\n[ \t\u3000]*", " ", text)
    # HTML <sup>/<sub> 标签（MinerU 数学幂/原子下标，如 10<sup>27</sup>、
    # N<sub>A</sub>）→ reportlab 真上标/下标（2026-09-02，GB_3100-2026）。
    # 必须在 escape() 之前转成哨兵，escape 之后恢复为真实标签，否则会被
    # 转义成字面文本 "<sup>…</sup>"。
    text = re.sub(r"<sup>([^<]*)</sup>", "\x00SUP\x00\\1\x00/SUP\x00", text)
    text = re.sub(r"<sub>([^<]*)</sub>", "\x00SUB\x00\\1\x00/SUB\x00", text)
    escaped = escape(text)
    # Restore the footnote-superscript sentinels emitted by _table_cell_superscripts
    # (GBT-C18): they must survive XML escaping, so the real <super> tags are
    # re-inserted only after escape().
    escaped = escaped.replace("\x00SUP\x00", "<super>").replace("\x00/SUP\x00", "</super>")
    escaped = escaped.replace("\x00SUB\x00", "<sub>").replace("\x00/SUB\x00", "</sub>")
    escaped = escaped.replace("\x00GAP\x00", '<font color="white">中</font>')
    # 正文宋体缺 ⁰⁵⁶⁷⁸⁹⁻⁺ 字形（Noto Serif CJK SC 实测无 glyph，2026-09-02；
    # ¹²³⁴ 有），Unicode 上标若直接渲染会成 .notdef 方框（PDF 文本层表现为
    # \x00）——转成 reportlab <super> 真上标（相邻上标合并为一个 run）。
    for sup_char, plain_char in (("⁰", "0"), ("⁵", "5"), ("⁶", "6"), ("⁷", "7"), ("⁸", "8"), ("⁹", "9"), ("⁻", "−"), ("⁺", "+"), ("ⁱ", "i")):
        escaped = escaped.replace(sup_char, f"<super>{plain_char}</super>")
    escaped = re.sub(r"</super><super>", "", escaped)
    # bold/italic（markdown 强调 *word*/**word**；字面星号簇已在入口保护为
    # AST 哨兵，此处不会错配），处理完还原哨兵为对应长度字面星号。
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"(?<!\*)\*(.+?)\*", r"<i>\1</i>", escaped)
    return _restore_literal_stars(escaped)


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
    # 附录示例块（GB/T 20001 表框/图框内容）：示例文档的标题（如
    # "1 000 kV 变电站监控系统 技术规范"）是文档名而非章条编号，不能
    # 做编号提取——千位分隔会被误判成编号 "1"，且提取会破坏真实标题。
    # 示例内部自带的编号章条（如 5 系统结构）在 SSIR 里已有 number 字段，
    # 直接使用即可。
    if node.get("exampleContent"):
        return raw_number, title, False
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
    # Each dot-segment may hold multiple digits ("5.10", "5.10.1"); a
    # single-digit-only pattern silently mis-classifies 5.10.. as depth 0,
    # which drops the heading into the indented body/front style.
    if re.fullmatch(r"\d+(?:\.\d+)+", number):
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

    def visit(nodes: list[dict[str, Any]]) -> None:
        for index, node in enumerate(nodes):
            if _is_toc_node(node):
                continue
            if node.get("exampleContent"):
                # 附录编写示例块（CSM-OCR-006）：示例文档自带的编号不是本标准章条，
                # 不入目次（原标准附录示例即不出现在目次中）。
                continue
            number, title, is_annex = _heading_parts(node)
            normalized_title = title.replace(" ", "")
            # 术语裸节（number=3.1, title=""）：术语名在紧随其后的 documentBlock
            # 兄弟节点标题上（扁平树），或单个子 documentBlock（嵌套树）。目次
            # 标签合成 "3.1 中文术语"（只显示中文术语，英文对应词不入目次）。
            if number and not title:
                next_node = nodes[index + 1] if index + 1 < len(nodes) else None
                term_title = _term_title_from_sibling(node, next_node)
                # 段落形态术语（3.1 + contentElement）无 documentBlock 兄弟，
                # term_title 为空；此时用 builder 写入的 term 元数据即可。
                if term_title or node.get("term"):
                    # 中文术语优先用 builder 识别的 term 元数据；未识别时从
                    # 术语行里截取中文部分（到首个拉丁字母为止）。
                    cn = str(node.get("term") or _term_cn(term_title) or term_title)
                    node["_tocLabel"] = _heading_text(number, cn, is_annex)
            # Front matter is represented as unnumbered document blocks.
            number_depth = len(number.split(".")) if re.fullmatch(r"\d+(?:\.\d+)*", number) else 1 if is_annex else 0
            if (number and (depth is None or number_depth <= depth)) or normalized_title in {"前言", "引言", "参考文献", "索引"} or is_annex:
                result.append(node)
            visit(node.get("children", []))

    visit(root_nodes)
    return result


def _strip_cjk_gaps(title: str) -> str:
    """Remove the letter-spacing blanks in CJK titles (目 次 → 目次) but keep
    spaces inside English runs (code of practice standard) and the U+200B term
    separator between Chinese and English."""
    return re.sub(r"(?<=[\u4e00-\u9fff]) (?=[\u4e00-\u9fff])", "", title)


def _term_cn(term_title: str) -> str:
    """Extract the Chinese term from a '中文 English' term line (TOC shows CN only)."""
    match = re.match(r"^[\u4e00-\u9fff]{1,24}", term_title.strip())
    return match.group(0) if match else term_title


def _term_title_from_sibling(node: dict[str, Any], next_node: dict[str, Any] | None) -> str:
    """Return the term title for a bare term section, or '' when not applicable.

    GB/T 20001 术语条目「中文English」常被解析为裸节（number=3.1, title=""）
    加紧随的 documentBlock 标题（扁平树为兄弟节点，嵌套树为单个子节点）。
    目次需要 "3.1 中文 English" 形式的完整标签；正文顺序与 roundtrip 不受影响。
    """
    children = node.get("children", [])
    candidates: list[dict[str, Any]] = []
    if len(children) == 1:
        candidates.append(children[0])
    if next_node is not None:
        candidates.append(next_node)
    for candidate in candidates:
        if candidate.get("nodeType") != "documentBlock":
            continue
        title = str(candidate.get("title") or "").strip()
        # 术语名中文与英文之间可能有 U+200B（CSM-OCR-003 术语间隔修复插入）。
        if re.match(r"^[\u4e00-\u9fff]{1,24}\u200b?[A-Za-z]", title):
            return title
    return ""


def _toc_label(node: dict[str, Any]) -> str:
    synthesized = node.get("_tocLabel")
    if synthesized:
        return str(synthesized)
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
