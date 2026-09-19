"""Render a validated SSIR document as an A4 PDF standard draft."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from html import escape
import hashlib
import json
import math
from pathlib import Path
import re
from string import ascii_letters
from typing import Any

import yaml

from .parser import inline_script_item_breaks
from .validation import validate_ssir

try:  # reportlab 依赖在 render 函数内延迟导入；占位类需在模块层可继承
    from reportlab.platypus import Flowable as _FlowableBase
except Exception:  # pragma: no cover - 无 reportlab 环境仅影响 pdf 渲染
    _FlowableBase = object


DEFAULT_PROFILE = Path(__file__).resolve().parents[2] / "config" / "rendering" / "GB_T_1.1-2020.yaml"

# 通栏对象（表/图/并列定位组/公式图）按"所在容器可用内容宽"排布
# （2026-09-07 根因修复，规则对应: GBT-B07/GBT-B11 执行侧）。此前渲染把所有
# 通栏对象按固定 455pt（正文版心历史常量，≈ A4 减 profile 左右边距）排布，
# 正文容器恰好合适；但附录示例线框（_example_box，GBT-B11）的单元格内容可用
# 宽只有 框宽(≈doc_width-2×Frame padding) - 2×10pt padding ≈ 421.5pt，
# 455pt 的表/图/并列组会从右侧穿出黑色框线（GB_T_20001.5-2017 附录A 示例1）。
# 因此把"当前容器可用内容宽"随 _append_* 调用链显式传递：正文默认
# _BODY_MEASURE（保持既有观感），示例框内按 _example_box_inner_width 收缩。
_BODY_MEASURE = 455.0  # 正文通栏对象版心宽（历史常量，总宽恒=版心）
_FRAME_PADDING = 6.0  # reportlab Frame 默认内衬（SimpleDocTemplate 未覆盖）
_EXAMPLE_PADDING = 10.0  # 附录示例框单元格左右 padding（与 _example_box 同值）
# 示例线框线宽（pt）：GB/T 1.1-2020 10.4.5「区分示例的线框应为细实线」；源 PDF
# 实测示例框 0.33pt（细实线）、表外框线/表头框线 0.76pt（粗实线，10.4.2.2）。
# 渲染端细线族统一 0.5pt（与表网格线同宽，docx 侧 w:sz=4 即 0.5pt）——框线不得
# 粗于表线，否则示例框喧宾夺主（2026-09-11 用户裁定：默认细框线）。
_EXAMPLE_FRAME_WIDTH = 0.5
# 表格单元格左右边距（_append_table 的 LEFTPADDING/RIGHTPADDING），列宽下界与窄表
# 边距压缩都以它为口径（GEN-103）。
_TABLE_CELL_PADDING = 4.0
# 宽表横排（GEN-103）可用宽：整表旋转 90° 后沿页面高度排布，等于正文 Frame 的可用
# 高（A4 高 − 上下边距 − Frame 内衬）。由 render_pdf 在页边距确定后写入；None =
# 未进入文档上下文（单表渲染 / 单测），此时不横排。
_ROTATED_TABLE_MEASURE: float | None = None
# 旋转 Flowable 类：reportlab 延迟导入（依赖可选），类在 render_pdf 内定义后写进本
# 槽位（与 _LABEL_FONT 同法）；None = 不横排。
_ROTATED_TABLE_CLASS: type | None = None


def _register_emphasis_family(profile: dict[str, Any], *, body: str, bold: str, primary: str, warnings: list[str]) -> None:
    """注册强调字形字族（docs/07 §6.1；GEN-108）。

    reportlab 的 ``<b>``/``<i>`` **只从已注册字族取成员**：字体未登记字族时两个标签
    被静默忽略（实测 `普通 <b>粗</b> <i>斜</i>` 出来仍是同一字体、无告警）——与
    GBT-B10「reportlab cannot fake bold」同源，因此强调要生效必须有**真实字形资产**：

    - 粗体（``**X**``）= 黑体（profile ``fonts.label``，GB/T 20001.10 表1 注解
      「黑体表示"必备要素"」，源 PDF 该列即方正黑体）；
    - 斜体（``*X*``）= 宋体机斜（``fonts.italic-file``，源 PDF 实测倾斜 15.8°）；
    - 粗斜体（``***X***``）= 黑体粗机斜（``fonts.bold-italic-file``）。

    斜体资产由 ``tools/prepare_oblique_font.py`` 生成；文件缺失时退回同字族的直立
    字形并在渲染报告记一条告警（不伪造、不静默）。
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    fonts = profile.get("fonts") or {}

    def _member(name_key: str, file_key: str) -> str:
        name = str(fonts.get(name_key) or "").strip()
        if not name:
            return ""
        font_file = Path(str(fonts.get(file_key) or ""))
        if not font_file.is_file():
            warnings.append(f"[GEN-108] 强调斜体字形文件缺失：{font_file}（按直立字形渲染）")
            return ""
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(font_file), subfontIndex=0))
        return name

    italic = _member("italic", "italic-file")
    bold_italic = _member("bold-italic", "bold-italic-file")
    if not bold:
        bold = primary
    if not italic:
        italic = body
    if not bold_italic:
        # 粗斜体 = 黑体机斜（缺资产时按黑体直立渲染，斜体支路退回同字族直立字形）。
        bold_italic = bold
    # 黑体族的斜体成员用黑体机斜（粗斜体资产与 primary/label 同为黑体族）。
    hei_italic = bold_italic or italic
    pdfmetrics.registerFontFamily(body, normal=body, bold=bold, italic=italic, boldItalic=bold_italic)
    for hei_name in {primary, bold}:
        pdfmetrics.registerFontFamily(hei_name, normal=hei_name, bold=hei_name, italic=hei_italic, boldItalic=hei_italic)


def _example_box_inner_width(doc_width: float) -> float:
    """附录示例线框内的可用内容宽（pt）：线框表格 colWidths=[None] 时跨整个
    Frame 可用宽（doc_width - 2×Frame padding），单元格内容再减去左右 padding。
    """
    return doc_width - 2 * _FRAME_PADDING - 2 * _EXAMPLE_PADDING


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
    # 注/示例标记字体（GB/T 1.1-2020 附录F 表F.1 序号42/44「小五号黑体」）：标记
    # 要能与宋体正文一眼分开，profile 可单独指定黑体粗（primary 可能是细黑）。
    global _LABEL_FONT
    label_font_file = Path(profile["fonts"].get("label-file") or font_file)
    label_font_name = str(profile["fonts"].get("label") or "")
    if label_font_name and not label_font_file.is_file():
        raise FileNotFoundError(f"CJK label font not found: {label_font_file}")
    if label_font_name and label_font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(label_font_name, str(label_font_file), subfontIndex=0))
    _LABEL_FONT = label_font_name
    # 强调字形（docs/07 §6.1；GEN-108）：`**粗体**`→黑体、`*斜体*`→机斜资产、
    # `***粗斜体***`→黑体粗机斜。reportlab 的 <b>/<i> 只认已注册字族成员，故必须
    # 在渲染前把字族登记好（未登记时两个标签被静默忽略，见 GBT-B10）。
    # 告警先收到本地列表：渲染报告对象在其下方才创建。
    emphasis_warnings: list[str] = []
    _register_emphasis_family(
        profile,
        body=body_font_name,
        bold=label_font_name or font_name,
        primary=font_name,
        warnings=emphasis_warnings,
    )

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
    report.warnings.extend(emphasis_warnings)
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
    # 目次里的图/表行（8.2.2 i)/j)）：标签与取页对象 id 在这里算一次，供目次渲染
    # 与 docx 孪生共用。
    toc_caption_rows = _toc_caption_rows(root_nodes, registries)

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
                if not label and level == _TOC_BLANK_ROW:
                    # 10.3.2：图或表的目次与其前面的内容之间空一行（占一行行高、
                    # 无文字无引导点）。
                    continue
                indent = level * 2 * self.font_size
                page_text = str(page_no)
                label_width = canvas.stringWidth(label, font_name, self.font_size)
                page_width = canvas.stringWidth(page_text, font_name, self.font_size)
                leader_space = self.width - indent - label_width - page_width - 8
                dot_count = max(int(leader_space // dot_width), 0)
                canvas.drawString(indent, y, label)
                canvas.drawString(indent + label_width + 4, y, "." * dot_count)
                canvas.drawRightString(self.width, y, page_text)

    class _RotatedTable(Flowable):
        """整表（含题注/单位行）旋转 90° 逆时针（GEN-103 宽表横排）。

        表头落订口一侧（左）、文字自下而上，题注排在表上方（旋转后即表格左侧）——
        与 GB/T 5171.1-2014 表9 的源排版同向。旋转后表格沿页面高度排布，可用宽 =
        版心高（60 列以上的表也排得下）。reportlab 的 flowable 没有旋转绘图，按
        canvas 变换实现：wrap 交换可用宽高、把若干流式对象叠成一列（题注在上、表格
        在下），draw 先平移到右上再旋转（表顶边落旋转原点）。
        """

        def __init__(self, stack: list[Any], ssir_id: str = "") -> None:
            super().__init__()
            self.stack = list(stack)
            self.ssir_id = ssir_id or str(getattr(self.stack[-1], "ssir_id", "") or "")
            self._heights: list[float] = []
            # 旋转后内块的稳定可用宽 = 横排可用宽（页高口径），与当前页剩多少无关：
            # wrap 曾经用「本页剩余高」当内块宽，表在页面下方时被压窄→折行变高→
            # 沿页宽方向的尺寸变大，reportlab 拿到一个本页放不下的片段后
            # Splitting error(n==2) 中止整篇（GB/T 30819-2024 表2/表4）。
            self._measure = _ROTATED_TABLE_MEASURE

        def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
            inner_width = float(self._measure or available_height)
            width = 0.0
            self._heights = []
            for flowable in self.stack:
                item_width, item_height = flowable.wrap(inner_width, inner_width)
                width = max(width, float(item_width))
                self._heights.append(float(item_height))
            self.width, self.height = sum(self._heights), width
            return self.width, self.height

        def draw(self) -> None:
            canvas = self.canv
            canvas.saveState()
            canvas.translate(self.width, 0)
            canvas.rotate(90)
            offset = 0.0
            for flowable, height in reversed(list(zip(self.stack, self._heights))):
                flowable.drawOn(canvas, 0, offset)
                offset += height
            canvas.restoreState()

        def split(self, available_width: float, available_height: float) -> list[Any]:
            # 旋转后：内块宽（列宽之和）受页高约束、内块高（题注 + 行高之和）受页宽
            # 约束（available_width 就是版心宽）。两个「放不下」的判断：
            #  ① 旋转后的垂直尺寸（= 内块宽）高于本页剩余高 → 本页放不下，返回空列表
            #     让 reportlab 把整表推迟到下一页；此时若返回片段，该片段同样放不下，
            #     reportlab 直接抛 Splitting error(n==2) 中止整篇。
            #  ② 内块切不出更小片段 → 同样返回空列表（放下不才报 "too large"）。
            if self.height > available_height + 0.5:
                return []
            budget = available_width - sum(self._heights[:-1])
            if budget <= 1.0:
                return []
            pieces = self.stack[-1].split(self.height or available_height, budget)
            if len(pieces) < 2:
                return []
            return [type(self)([*self.stack[:-1], piece], self.ssir_id) for piece in pieces]

    # _append_table 是模块级函数，取不到本函数的局部类；按 _LABEL_FONT 同法写进模块槽位。
    global _ROTATED_TABLE_CLASS
    _ROTATED_TABLE_CLASS = _RotatedTable

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

    def toc_story(toc_nodes: list[dict[str, Any]], toc_pages: dict[str, int], extra_contents: list[dict[str, Any]] | None = None,
                  caption_rows: list[list[tuple[str, str]]] | None = None) -> list[Any]:
        rows = []
        for node in toc_nodes:
            label = _toc_label(node)
            if not label:
                continue
            level = _toc_indent_level(node)
            rows.append((label, level, toc_pages.get(node["id"], 0)))
        # 图/表行（8.2.2 i)/j)）：接在条/附录/参考文献/索引之后，顶格；与前面内容
        # 之间空一行（10.3.2「图或表的目次与其前面的内容之间均应空一行」）。
        for group in caption_rows or []:
            if not group:
                continue
            rows.append(("", _TOC_BLANK_ROW, _TOC_BLANK_ROW))
            for label, reference in group:
                rows.append((label, 0, toc_pages.get(reference, 0)))
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
        # 示例线框内可用内容宽（doc_width 见 render_pdf 尾部；make_story 在执行时
        # 才能取到）：框内表/图按此宽排布，不再按正文 455pt 穿出黑色框线。
        example_inner_width = _example_box_inner_width(doc_width)
        idx = 0
        root_len = len(root_nodes)
        # ssir:box 显式声明（2026-09-08）：文档含标记 → 全部框决策交给显式分组
        # （_append_marked_node 流式开合）；无标记文档维持旧 exampleContent 启发式。
        doc_boxed = _tree_has_boxes(root_nodes)
        sink = _BoxSink(story, colors, Table, TableStyle, example_default, PageBreak=PageBreak, box_inner_width=example_inner_width) if doc_boxed else None
        while idx < root_len:
            node = root_nodes[idx]
            if _is_toc_node(node):
                story.extend(toc_story(_toc_nodes(root_nodes, toc_depth), toc_pages, node.get("contentElements", []), toc_caption_rows))
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
            if doc_boxed:
                if sink is not None:
                    sink.flush()
                # 「示例N：」框外题注（黑体顶格）：不进框；其后子内容/正文照旧渲染。
                if _is_example_header(node) and node.get("exampleContent") and not node.get("box"):
                    story.append(Paragraph(_markup(str(node.get("title") or "").strip()), styles["example-label"]))
                    idx += 1
                    for child in node.get("children", []) or []:
                        _append_marked_node(sink, child, registries, styles, font_name, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default, box_inner_width=example_inner_width)
                    contents = node.get("contentElements") or []
                    if contents:
                        _append_marked_content_sequence(sink, contents, registries, styles, font_name, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, example_inner_width, example_inner_width, enclosing=_node_clause_number(node))
                    continue
                leading = bool(node.get("box") is not None and (sink is None or sink.active != node.get("box")))
                _append_marked_node(sink, node, registries, styles, font_name, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default, example_leading=leading, box_inner_width=example_inner_width)
                idx += 1
                continue
            if node.get("exampleContent"):
                # 附录示例块（GBT-B11）：连续 exampleContent 兄弟打包成框。
                # 「示例N：」是框外题注（黑体顶格），不进框；框内第一个节点
                # 是示例文档真实标题（黑体居中），其后是示例文档自身编号章条。
                if _is_example_header(node):
                    story.append(Paragraph(_markup(str(node.get("title") or "").strip()), styles["example-label"]))
                    idx += 1
                    # 树形/扁平混合：内容挂在题注节点下时（GB_T_20001.10-2014
                    # A.3.1 型扁平附录），题注子内容照常渲染（正文宽度，非线框内），
                    # 不因“题注只打印、子级被跳过”丢内容；box_inner_width 仍传递，
                    # 供子内容里更深层的示例分组（_append_nodes）创建线框时收缩。
                    for child in node.get("children", []) or []:
                        _append_node(story, child, registries, styles, font_name, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default, box_inner_width=example_inner_width)
                    contents = node.get("contentElements") or []
                    if contents:
                        _append_content_sequence(story, contents, registries, styles, font_name, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, enclosing=_node_clause_number(node))
                    continue
                box: list[Any] = []
                mode = str(node.get("exampleStyle") or example_default)
                while idx < root_len and root_nodes[idx].get("exampleContent"):
                    if _is_example_header(root_nodes[idx]):
                        break
                    _append_node(box, root_nodes[idx], registries, styles, font_name, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default, example_leading=not box, content_width=example_inner_width, box_inner_width=example_inner_width)
                    idx += 1
                box = _strip_pagebreaks(box, PageBreak)
                story.append(_example_box(box, mode, colors, Table, TableStyle))
                continue
            _append_node(story, node, registries, styles, font_name, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default, box_inner_width=example_inner_width)
            idx += 1
        if sink is not None:
            sink.flush()
        if has_cover:
            # GB/T 1.1-2020 末页应有终结线（GBT-C13）；仅标准类文档（与封面同门控）。
            story.append(_EndLine())
        return story

    doc_width = A4[0] - (float(margins["left"]) + float(margins["right"])) * mm
    # 宽表横排（GEN-103）可用宽 = 正文 Frame 的可用高（A4 高 − 上下边距 − Frame 内衬）；
    # 与 _LABEL_FONT 同法：模块级取值由 render_pdf 在页边距确定后写入。
    global _ROTATED_TABLE_MEASURE
    _ROTATED_TABLE_MEASURE = A4[1] - (float(margins["top"]) + float(margins["bottom"])) * mm - 2 * _FRAME_PADDING
    provisional_pages: dict[str, int] = {}

    def _record_pages(flowable: Any) -> None:
        """预检通道：记下标题/目次标记与带 ``ssir_id`` 的图题、表格所在页。"""
        if isinstance(flowable, _TOCMarker):
            provisional_pages.setdefault(flowable.node_id, preflight_doc.page)
            return
        ssir_id = getattr(flowable, "ssir_id", "")
        if ssir_id:
            provisional_pages.setdefault(ssir_id, preflight_doc.page)

    if has_toc:
        # First pass has the same fixed-height TOC rows but placeholder page
        # values.  Markers record actual heading pages for the final pass.
        preflight = target.with_name(target.stem + ".toc-preflight.pdf")
        preflight_doc = make_doc(preflight)
        preflight_doc.afterFlowable = _record_pages
        preflight_doc.build(make_story({}, provisional_pages), onFirstPage=footer, onLaterPages=footer)
        preflight.unlink(missing_ok=True)

    doc = make_doc(target)
    # 条文脚注页底绘制（GBT-X04 执行侧）：0 高占位在 afterFlowable 阶段把定义画到
    # 本页页脚（正文框之下、页码之上的页边带），首条脚注上方画居左黑色细分隔线。
    # 不占正文流位置、不依赖定义块在 canonical 中的摆放位置。
    from reportlab.platypus import Paragraph as _PageNoteParagraph
    from reportlab.lib.styles import ParagraphStyle as _PageNoteStyle
    _page_note_y: dict[int, float] = {}
    note_base = float(margins["bottom"]) * mm - 6.0
    note_left = float(margins["left"]) * mm
    note_width = A4[0] - float(margins["left"]) * mm - float(margins["right"]) * mm
    _note_style = _PageNoteStyle(
        "gbt-page-note", parent=styles.get("note") or styles["body"],
        fontSize=9, leading=12, firstLineIndent=0, leftIndent=0,
        spaceBefore=0, spaceAfter=0, alignment=TA_JUSTIFY if "TA_JUSTIFY" in globals() else 4,
    )

    def _draw_page_note(text: str) -> None:
        canvas = doc.canv
        page = doc.page
        match = re.match(r"^\s*(\d+|[A-Za-z])[)）]?\s*(.*)$", text, re.S)
        marker = match.group(1) if match else ""
        body = match.group(2) if match else text
        markup = (f"<super>{marker})</super> " if marker else "") + body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        paragraph = _PageNoteParagraph(markup, _note_style)
        paragraph.wrap(note_width, 600)
        if page not in _page_note_y:
            canvas.saveState()
            canvas.setStrokeColorRGB(0, 0, 0)
            canvas.setLineWidth(0.8)
            canvas.line(note_left, note_base, note_left + note_width / 4.0, note_base)
            canvas.restoreState()
        y = _page_note_y.get(page, note_base - 2)
        paragraph.drawOn(canvas, note_left, y - paragraph.height)
        _page_note_y[page] = y - paragraph.height - 3

    def _after_flow(flowable: Any) -> None:
        if isinstance(flowable, _FootnoteAnchor):
            _draw_page_note(str(flowable.text))

    doc.afterFlowable = _after_flow
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


# 目次里的空行占位（GB/T 1.1-2020 10.3.2：图或表的目次与其前面的内容之间空一行）：
# 行元组用 (label="", level=_TOC_BLANK_ROW, page=_TOC_BLANK_ROW) 标记，绘制时跳过。
_TOC_BLANK_ROW = -1


def _toc_tracked_table_class(Table: Any) -> type:
    """Table 子类：分页拆分时把 ``ssir_id`` 传给每个分片（目次图/表行页码）。

    reportlab 拆表时新建 Table 分片，子类属性不会自动继承——大表（GB_T_1.1-2020
    表3/表4）跨页后 afterFlowable 拿到的分片没有 id，目次页码就成了 0。
    表类由 render_pdf 注入（reportlab 是延迟导入的可选依赖），故按基类缓存子类。

    另加**续表题注**（GEN-115、GB/T 1.1-2020 9.8.3/10.4.2）：表跨页时每一片续表在
    重复的表头行之上插入「表N 表题（续）」与单位陈述行（单位为××，右对齐）——由
    ``_append_table`` 把这两行作为 ``_continuation_flowables`` 挂到表对象上；本子类在
    ``split()`` 里给需要它的分片插行（详见 ``_insert_continuation_rows``）。
    """
    cached = _TOC_TRACKED_TABLES.get(Table)
    if cached is not None:
        return cached

    class _TrackedTable(Table):  # type: ignore[misc, valid-type]
        ssir_id = ""
        # 续表题注行（Paragraph 列表，自上而下）：仅当表确实分页时使用。
        _continuation_flowables: list[Any] | None = None
        # 本表**自身**就是从续页起排的续表（其上片也要题注）。
        _is_continuation_piece = False

        def split(self, availWidth: float, availHeight: float) -> list[Any]:
            pieces = super().split(availWidth, availHeight)
            for piece in pieces:
                piece.ssir_id = getattr(self, "ssir_id", "")
            if len(pieces) == 2:
                top, bottom = pieces
                if getattr(self, "_is_continuation_piece", False):
                    # 本表已是续表：题注/单位行就是它的前几行，reportlab 会把它们
                    # 连同表头一起重复到下片（repeatRows 已含题注行数）——两片都不再插行，
                    # 只把标记传下去（否则再拆一层会重复印一遍题注）。
                    top._is_continuation_piece = True
                    bottom._is_continuation_piece = True
                else:
                    # 首次分片：下片落在下一页 → 成为续表，补题注/单位行，并把
                    # repeatRows 提到「题注 + 单位 + 全部表头行」，使更深的拆分重复整块。
                    added = self._insert_continuation_rows(bottom)
                    bottom._is_continuation_piece = True
                    if added:
                        bottom.repeatRows = (bottom.repeatRows or 0) + added
            return pieces

        def _insert_continuation_rows(self, piece: Any) -> int:
            """在分片**表头行之前**插入续表题注/单位行（行坐标整体下移），返回插入行数。

            插行后不变量：行的 cellValues/cellStyles/_argH/_nrows 长度一致；所有按行
            索引的样式命令（GRID/底纹/SPAN/禁拆）整体下移 K 行，两条插入行各以
            SPAN 横跨全表（题注居中、单位右对齐由 Paragraph 自身样式决定）。表框
            （GRID 命令）随之只覆盖表头与数据行，题注/单位行留白在表框之上。
            """
            rows_to_add = list(getattr(self, "_continuation_flowables", None) or [])
            if not rows_to_add:
                return 0
            k = len(rows_to_add)
            ncols = len(piece._colWidths)
            values = [list(row) for row in piece._cellvalues]
            styles = [list(row) for row in piece._cellStyles]
            base_style = piece._cellStyles[0][0]
            for offset, flowables in enumerate(rows_to_add):
                values.insert(offset, [flowables] + [""] * (ncols - 1))
                styles.insert(offset, [base_style.copy() for _ in range(ncols)])
            piece._cellvalues = values
            piece._cellStyles = styles
            heights = list(piece._argH) if piece._argH is not None else None
            if heights is not None:
                for _ in range(k):
                    heights.insert(0, None)
            piece._argH = heights
            piece._rowHeights = heights
            piece._nrows = piece._nrows + k
            for attr in ("_linecmds", "_bkgrndcmds", "_spanCmds", "_nosplitcmds", "_srflcmds", "_sircmds"):
                commands = getattr(piece, attr, None)
                if not commands:
                    continue
                setattr(piece, attr, [_shift_command_rows(command, k) for command in commands])
            piece._spanCmds = list(piece._spanCmds or []) + [
                ("SPAN", (0, offset), (-1, offset)) for offset in range(k)
            ]
            return k

    _TOC_TRACKED_TABLES[Table] = _TrackedTable
    return _TrackedTable


def _shift_command_rows(command: Any, rows: int) -> Any:
    """样式命令的行索引整体下移（插行用）：``(op, (sc,sr), (ec,er), …)``。

    ``-1`` 是 reportlab 的「最后一行」哨兵，保持不动；其余行号 +rows。
    """
    if not isinstance(command, tuple) or len(command) < 3:
        return command
    start, end = command[1], command[2]
    if not (isinstance(start, tuple) and isinstance(end, tuple) and len(start) == 2 and len(end) == 2):
        return command
    shifted_start = (start[0], start[1] + rows if start[1] >= 0 else start[1])
    shifted_end = (end[0], end[1] + rows if end[1] >= 0 else end[1])
    return (command[0], shifted_start, shifted_end, *command[3:])


_TOC_TRACKED_TABLES: dict[Any, type] = {}


def _styles(base: Any, profile: dict[str, Any], font: str, body_font: str, center: int, justify: int, left: int) -> dict[str, Any]:
    # 规则对应: GBT-P02（字号字体符合附录F）、GBT-FM2（前言/引言标题三号黑体居中）、
    # GBT-B02/B03（章条标题五号黑体、正文五号宋体）、GBT-B05（附录标题居中）、
    # GBT-B10（注小五号）、GEN-071（排版参数来自 profile）。
    from reportlab.lib.styles import ParagraphStyle

    rules = profile["styles"]
    body = rules["body"]
    # 数值-单位固定字隙（GBT-B12）基准 = 正文号；容器字号不同者在调用点显式传
    # em_size（如表单元格、注），避免间隙随正文号之外的容器漂移。
    global _MARKUP_EM_SIZE
    try:
        if float(body.get("size-pt")):
            _MARKUP_EM_SIZE = float(body["size-pt"])
    except (TypeError, ValueError):
        pass
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
        # 术语条目（GB/T 1.1-2020 8.7.3.1、10.3.5、附录F 表F.1 序号 22/23）：
        # 条目编号单独占一行、顶格起排、上下无空行（五号黑体）；术语与英文对应词
        # 另起一行、空两个汉字起排（五号黑体，中英文之间空一个汉字）。
        "term-number": ParagraphStyle("gbt-term-number", parent=base["BodyText"], fontName=font, fontSize=body["size-pt"], leading=body["leading-pt"], alignment=left, leftIndent=0, firstLineIndent=0, spaceBefore=0, spaceAfter=0, wordWrap="CJK"),
        "term-title": ParagraphStyle("gbt-term-title", parent=base["BodyText"], fontName=font, fontSize=body["size-pt"], leading=body["leading-pt"], alignment=left, leftIndent=2 * body["size-pt"], firstLineIndent=0, spaceBefore=0, spaceAfter=0, wordWrap="CJK"),
        "body": ParagraphStyle("gbt-body", parent=base["BodyText"], fontName=body_font, fontSize=body["size-pt"], leading=body["leading-pt"], alignment=justify, firstLineIndent=2 * body["size-pt"], spaceAfter=4, wordWrap="CJK"),
        # Untitled clause paragraphs start with the clause number; GB/T 1.1
        # puts those numbers flush left (顶格) instead of taking the body
        # two-Han-character first-line indent (GBT-B02).  They are left
        # aligned, not justified: reportlab's justification stretches every
        # space on a short first line, blowing up the gap after the clause
        # number ("5.5.3" + 50pt), which OCR standards exhibit as noise.
        "body-flush": ParagraphStyle("gbt-body-flush", parent=base["BodyText"], fontName=body_font, fontSize=body["size-pt"], leading=body["leading-pt"], alignment=left, firstLineIndent=0, spaceAfter=4, wordWrap="CJK"),
        # 原样块（docs/07 §6.10，GEN-107）：逐字保留换行与行首缩进 → 左对齐（两端
        # 对齐会拉伸行内空格、破坏缩进列），首行不缩进，字号/行距与正文一致。
        "verbatim": ParagraphStyle("gbt-verbatim", parent=base["BodyText"], fontName=body_font, fontSize=body["size-pt"], leading=body["leading-pt"], alignment=left, firstLineIndent=0, spaceAfter=4, wordWrap="CJK"),
        "note": ParagraphStyle("gbt-note", parent=base["BodyText"], fontName=body_font, fontSize=9, leading=15, alignment=justify, leftIndent=2 * body["size-pt"], spaceAfter=4, wordWrap="CJK"),
        # GB/T 1.1-2020 6.6.3：第一层次列项（——/a)）空两个汉字起排、
        # 回行对齐第5汉字；第二层次列项（·/1)）空四个汉字起排、回行对齐第7汉字。
        "list": ParagraphStyle("gbt-list", parent=base["BodyText"], fontName=body_font, fontSize=body["size-pt"], leading=body["leading-pt"], alignment=justify, leftIndent=4 * body["size-pt"], firstLineIndent=-2 * body["size-pt"], spaceAfter=2, wordWrap="CJK"),
        "list-sub": ParagraphStyle("gbt-list-sub", parent=base["BodyText"], fontName=body_font, fontSize=body["size-pt"], leading=body["leading-pt"], alignment=justify, leftIndent=6 * body["size-pt"], firstLineIndent=-2 * body["size-pt"], spaceAfter=2, wordWrap="CJK"),
        "caption": ParagraphStyle("gbt-caption", parent=base["BodyText"], fontName=font, fontSize=10.5, leading=14, alignment=center, spaceBefore=4, spaceAfter=4),
        # 分图题注（GBT-B06：分图编号、分图题小五号黑体；GB/T 1.1-2020 9.7.6、
        # 附录F 表F.1 序号38/39）：与图题注同为黑体居中，但小一号、上下留白更紧。
        "subcaption": ParagraphStyle("gbt-subcaption", parent=base["BodyText"], fontName=font, fontSize=9, leading=12, alignment=center, spaceBefore=2, spaceAfter=2),
        "formula": ParagraphStyle("gbt-formula", parent=base["Code"], fontName=body_font, fontSize=10, leading=16, alignment=center, spaceAfter=4),
        "table": ParagraphStyle("gbt-table", parent=base["BodyText"], fontName=body_font, fontSize=rules["table"]["size-pt"], leading=rules["table"]["leading-pt"], alignment=center),
        "table-body": ParagraphStyle("gbt-table-body", parent=base["BodyText"], fontName=body_font, fontSize=rules["table"]["size-pt"], leading=rules["table"]["leading-pt"], alignment=left, wordWrap="CJK"),
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
        ("LEFTPADDING", (0, 0), (-1, -1), _EXAMPLE_PADDING),
        ("RIGHTPADDING", (0, 0), (-1, -1), _EXAMPLE_PADDING),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if mode == "shaded":
        # 浅色背景（类代码块）：无边框，淡灰底。
        commands.append(("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0F2F5")))
    else:
        # 黑色细实线框（默认，GB/T 1.1 10.4.5；线宽见 _EXAMPLE_FRAME_WIDTH）。
        commands.append(("BOX", (0, 0), (-1, -1), _EXAMPLE_FRAME_WIDTH, colors.black))
    table.setStyle(TableStyle(commands))
    return table


def _append_nodes(story: list[Any], nodes: list[dict[str, Any]], registries: dict[str, dict[str, dict[str, Any]]], styles: dict[str, Any], font: str, report: PDFRenderReport, asset_dir: Path, colors: Any, Table: Any, TableStyle: Any, Paragraph: Any, Spacer: Any, Image: Any, marker_factory: Any = None, PageBreak: Any = None, example_default: str = "frame", content_width: float = _BODY_MEASURE, box_inner_width: float | None = None) -> None:
    """Append sibling nodes, grouping consecutive annex example-content nodes
    into boxed example blocks (GBT-B11); each '示例N：' label stays outside the
    box as a caption, and the first boxed node is the example's real title.

    ``content_width`` 是当前容器内通栏对象（表/图/并列组）可用的内容宽；
    进入示例线框（_example_box）时收窄为 ``box_inner_width``（= _example_box_inner_width），
    使框内表/图不再按正文 455pt 排布而穿出黑色框线（GBT-B07/GBT-B11 执行侧）。
    """
    index = 0
    while index < len(nodes):
        node = nodes[index]
        if node.get("exampleContent"):
            # 「示例N：」框外题注：不进框，黑体顶格排在框上方。
            if _is_example_header(node):
                story.append(Paragraph(_markup(str(node.get("title") or "").strip()), styles["example-label"]))
                index += 1
                # 树形附录示例（内容挂在题注节点下，GB_T_20001.10-2014 A.3.1）：
                # 题注后的子内容照常渲染，不再因“题注只打印、子级被跳过”而丢内容；
                # 20001.5/6 型扁平示例（题注无内容、后续兄弟入框）不受影响。
                for child in node.get("children", []) or []:
                    _append_node(story, child, registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default, content_width=content_width, box_inner_width=box_inner_width)
                contents = node.get("contentElements") or []
                if contents:
                    _append_content_sequence(story, contents, registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, content_width=content_width, enclosing=_node_clause_number(node))
                continue
            box: list[Any] = []
            mode = str(node.get("exampleStyle") or example_default)
            # 框内节点（含其表/图）统一按框内可用内容宽排布。
            box_width = box_inner_width if box_inner_width is not None else content_width
            while index < len(nodes) and nodes[index].get("exampleContent"):
                if _is_example_header(nodes[index]):
                    break
                _append_node(box, nodes[index], registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default, example_leading=not box, content_width=box_width, box_inner_width=box_inner_width)
                index += 1
            box = _strip_pagebreaks(box, PageBreak)
            story.append(_example_box(box, mode, colors, Table, TableStyle))
            continue
        _append_node(story, node, registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default, content_width=content_width, box_inner_width=box_inner_width)
        index += 1


def _append_content_sequence(story: list[Any], contents: list[dict[str, Any]], registries: dict[str, dict[str, dict[str, Any]]], styles: dict[str, Any], font: str, report: PDFRenderReport, asset_dir: Path, colors: Any, Table: Any, TableStyle: Any, Paragraph: Any, Spacer: Any, Image: Any, content_width: float = _BODY_MEASURE, enclosing: str | None = None) -> None:
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
            _append_side_by_side(story, members, registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, content_width=content_width)
            prev_figure_note = True  # 并列组整体是"图的说明"
            continue
        # 图注行（图题/图）后紧跟表头名称 → 空一行/更大间距（通用要求）。
        if prev_figure_note and _is_table_caption_shape(content):
            story.append(Spacer(1, 10))
        _append_content(story, content, registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, content_width=content_width, enclosing=enclosing)
        prev_figure_note = _is_figure_note_shape(content)
        index += 1


def _tree_has_boxes(nodes: list[dict[str, Any]]) -> bool:
    """节点列表（任意层级）是否存在 ssir:box 显式声明（2026-09-08）：有则渲染
    走显式分组，无则行为与旧版逐字节一致（exampleContent 连续打包等启发式原样保留）。"""

    def visit(nodes: list[dict[str, Any]]) -> bool:
        for node in nodes:
            if "box" in node:
                return True
            for content in node.get("contentElements", []) or []:
                if "box" in content:
                    return True
            if visit(node.get("children", []) or []):
                return True
        return False

    return visit(nodes)


class _BoxSink:
    """显式框渲染的流式缓冲：单元（标题/内容元素/子节点起始）按 box 归属推进，
    框 id 变化或回到框外时把缓冲整体交给 _example_box 画框/浅底（2026-09-08）。

    与旧"连续 exampleContent 兄弟打包"的区别：框边界来自 canonical 显式声明，
    可出现在任意两个相邻块之间（含同一条款内容元素序列中途），且不限于附录示例。
    """

    def __init__(self, story: list[Any], colors: Any, Table: Any, TableStyle: Any,
                 example_default: str, *, box_inner_width: float, PageBreak: Any = None) -> None:
        self.story = story
        self.colors = colors
        self.Table = Table
        self.TableStyle = TableStyle
        self.example_default = example_default
        self.box_inner_width = box_inner_width
        self.PageBreak = PageBreak
        self.active: int | None = None
        self.mode: str = example_default
        self.pending: list[Any] = []

    def add(self, flowables: list[Any], box: int | None, box_style: str | None = None) -> None:
        if not flowables:
            return
        if box is None:
            self.flush()
            self.story.extend(flowables)
            return
        if self.active != box:
            self.flush()
            self.active = box
            self.mode = box_style if box_style in ("frame", "shaded") else self.example_default
        self.pending.extend(flowables)

    def flush(self) -> None:
        if not self.pending:
            self.active = None
            return
        content = self.pending
        if self.PageBreak is not None:
            # 换页符在单列框表格内会把行撑到整帧高 → LayoutError；框表自身可跨页。
            content = [f for f in content if not isinstance(f, self.PageBreak)]
        if content:
            self.story.append(_example_box(content, self.mode, self.colors, self.Table, self.TableStyle))
        self.pending = []
        self.active = None


def _append_marked_content(sink: _BoxSink, content: dict[str, Any],
                           registries: dict[str, Any], styles: dict[str, Any], font: str,
                           report: PDFRenderReport, asset_dir: Path, colors: Any, Table: Any,
                           TableStyle: Any, Paragraph: Any, Spacer: Any, Image: Any,
                           content_width: float, inner_width: float,
                           enclosing: str | None = None) -> None:
    """把单个内容元素作为单元送入 sink（ssir:box 显式模式；2026-09-08）。

    框归属只看内容元素自身的 box 字段，**不回退继承父节点**：逐块扫描时每个
    内容元素在自身位置独立取值——节点标题在框内、其尾部内容在关标记之后时
    （20001.5 引导段型），该内容元素 box 为 None，必须留在框外。
    """
    box = content.get("box")
    if content.get("presentationType") == "footnote" and box is not None:
        report.warnings.append(
            "ssir:box 框内条文脚注占位无法在页脚绘制（框为表格单元格，afterFlowable 不触发）；请把脚注定义移出框或不要框住脚注。"
        )
    scratch: list[Any] = []
    width = inner_width if box is not None else content_width
    _append_content(scratch, content, registries, styles, font, report, asset_dir, colors,
                    Table, TableStyle, Paragraph, Spacer, Image, content_width=width, enclosing=enclosing)
    sink.add(scratch, box, content.get("boxStyle"))


def _append_marked_content_sequence(sink: _BoxSink, contents: list[dict[str, Any]],
                                    registries: dict[str, Any], styles: dict[str, Any], font: str,
                                    report: PDFRenderReport, asset_dir: Path, colors: Any, Table: Any,
                                    TableStyle: Any, Paragraph: Any, Spacer: Any, Image: Any,
                                    content_width: float, inner_width: float,
                                    enclosing: str | None = None) -> None:
    """节点内容元素序列的显式模式发射：保持并列定位组与图注-表题间距规则，
    每个单元按自身 box 归属进出框（边界可在同一条款内容中途，20001.5 引导段型）。"""
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
            scratch: list[Any] = []
            box = members[0].get("box")
            _append_side_by_side(scratch, members, registries, styles, font, report, asset_dir,
                                 colors, Table, TableStyle, Paragraph, Spacer, Image,
                                 content_width=inner_width if box is not None else content_width)
            sink.add(scratch, box, members[0].get("boxStyle"))
            prev_figure_note = True
            continue
        box = content.get("box")
        if prev_figure_note and _is_table_caption_shape(content):
            # 图注后紧跟表题 → 空行间距（与 _append_content_sequence 同规则）。
            sink.add([Spacer(1, 10)], box, content.get("boxStyle"))
        _append_marked_content(sink, content, registries, styles, font, report,
                               asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image,
                               content_width, inner_width, enclosing=enclosing)
        prev_figure_note = _is_figure_note_shape(content)
        index += 1


def _append_marked_node(sink: _BoxSink, node: dict[str, Any], registries: dict[str, Any],
                        styles: dict[str, Any], font: str, report: PDFRenderReport, asset_dir: Path,
                        colors: Any, Table: Any, TableStyle: Any, Paragraph: Any, Spacer: Any,
                        Image: Any, marker_factory: Any = None, PageBreak: Any = None,
                        example_default: str = "frame", example_leading: bool = False,
                        content_width: float = _BODY_MEASURE, box_inner_width: float | None = None) -> None:
    """显式模式（文档含 ssir:box）的节点发射：与 _append_node 同级语义（附录/
    示例标题样式/换页/通栏宽度），但按单元粒度经 _BoxSink 开合框。无标记文档不走此路径。

    规则对应: GBT-B02/B05/B06/B07、GBT-B11（示例线框执行侧=显式声明，2026-09-08）。
    """
    inner = box_inner_width if box_inner_width is not None else content_width
    node_type = node.get("nodeType")
    number, title, is_annex = _heading_parts(node)
    box = node.get("box")
    box_style = node.get("boxStyle") or example_default
    if is_annex:
        unit: list[Any] = []
        if PageBreak is not None and box is None and _starts_new_page(node, title, is_annex):
            unit.append(PageBreak())
        unit.append(marker_factory(node) if marker_factory else Spacer(1, 0))
        unit.append(Paragraph(_markup(f"附　录　{number}"), styles["annex-letter"]))
        status = _heading_annex_status(node)
        if status:
            unit.append(Paragraph(_markup(status), styles["annex-status"]))
        unit.append(Paragraph(_markup(title), styles["annex-title"]))
        sink.add(unit, box, box_style)
        _append_marked_content_sequence(sink, node.get("contentElements", []), registries,
                                        styles, font, report, asset_dir, colors, Table, TableStyle,
                                        Paragraph, Spacer, Image, content_width, inner, enclosing=number or None)
        for child in node.get("children", []) or []:
            _append_marked_node(sink, child, registries, styles, font, report, asset_dir, colors,
                                Table, TableStyle, Paragraph, Spacer, Image, marker_factory,
                                PageBreak, example_default, example_leading=False,
                                content_width=content_width, box_inner_width=inner)
        return
    heading = _heading_text(number, title, is_annex)
    depth = _heading_depth(number)
    heading_style = styles["section"] if depth == 1 else styles["subclause"] if depth >= 3 else styles["clause"] if depth else styles["front"]
    if node.get("exampleContent"):
        # 附录编写示例块（GB/T 20001 表框/图框内容，CSM-OCR-006）：框内第一个无编号
        # 节点是示例文档真实标题（黑体居中），其余节点黑体顶格左对齐（与旧分组一致）。
        heading_style = styles["example-title"] if (example_leading and not number) else styles["example-content"]
    elif not number and title.replace(" ", "") in {"前言", "引言", "参考文献", "索引"}:
        heading_style = styles["front-title"]
    unit = []
    if PageBreak is not None and box is None and _starts_new_page(node, title, is_annex):
        unit.append(PageBreak())
    if marker_factory and box is None:
        unit.append(marker_factory(node))
    unit.extend(_term_entry_flowables(node, number, title, heading, heading_style, styles, font, Paragraph))
    sink.add(unit, box, box_style)
    _append_marked_content_sequence(sink, node.get("contentElements", []), registries,
                                    styles, font, report, asset_dir, colors, Table, TableStyle,
                                    Paragraph, Spacer, Image, content_width, inner, enclosing=number or None)
    for child in node.get("children", []) or []:
        _append_marked_node(sink, child, registries, styles, font, report, asset_dir, colors,
                            Table, TableStyle, Paragraph, Spacer, Image, marker_factory,
                            PageBreak, example_default, example_leading=False,
                            content_width=content_width, box_inner_width=inner)


class _FormulaLeaderLine(_FlowableBase):
    """公式行（GBT-X06；GB/T 1.1-2020 10.4.3）：公式另行居中编排，编号右端对齐，
    公式与编号之间由「……」连接，公式与省略号之间留两个汉字间隔；

    reportlab 没有制表位引导线（tab leader），故用自定义 Flowable 精确摆放：公式块
    居中绘制、编号按实测宽度贴版心右缘，中间按**可用宽度计算省略号个数**（每个
    U+2026 字形的推进宽为分母），余量用字间距（Tc）均摊——等价于源文里引导线填满
    整段的排法，且不受两端对齐影响（不是空格字节）。

    规则对应: GBT-X06（数学公式另行居中、编号右端对齐、与公式以「…」连接）。
    """

    def __init__(self, formula: Any, number: str, font: str, size: float, *,
                 gap_em: float = 2.0, min_leader_em: float = 4.0, ellipsis: str = "…",
                 space_before: float = 0.0, space_after: float = 6.0) -> None:
        super().__init__()
        self.formula = formula
        self.number = str(number)
        self.font = font
        self.size = float(size)
        self.gap_em = float(gap_em)
        self.min_leader_em = float(min_leader_em)
        self.ellipsis = ellipsis
        self.space_before = float(space_before)
        self.space_after = float(space_after)
        self.avail = 0.0
        self.formula_w = 0.0
        self.formula_h = 0.0

    def getSpaceBefore(self) -> float:  # platypus 读这两个钩子
        return self.space_before

    def getSpaceAfter(self) -> float:
        return self.space_after

    def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
        from reportlab.pdfbase.pdfmetrics import stringWidth

        self.avail = float(available_width)
        number_w = stringWidth(self.number, self.font, self.size)
        # 公式居中后，左右各有 (可用宽 − 公式宽)/2；公式与编号之间要容下
        # 「两个汉字间隔 + 省略号引导线（至少 min_leader_em 个汉字位）」，故公式
        # 宽度上限 = 可用宽 − 2×(间隔 + 编号宽 + 引导线)。超宽时只缩小不放大。
        reserve = 2 * (self.gap_em * self.size + number_w + self.min_leader_em * self.size)
        limit = self.avail - reserve
        if limit > 0 and hasattr(self.formula, "drawWidth"):
            if float(self.formula.drawWidth) > limit:
                ratio = limit / float(self.formula.drawWidth)
                self.formula.drawWidth = float(self.formula.drawWidth) * ratio
                self.formula.drawHeight = float(self.formula.drawHeight) * ratio
        # 文本回退（无公式图资产，段落拍平呈现）时按上限宽度排版，同样给引导线留位。
        available = min(self.avail, limit) if (limit > 0 and not hasattr(self.formula, "drawWidth")) else self.avail
        self.formula_w, self.formula_h = self.formula.wrap(available, available_height)
        self.formula_w = min(float(self.formula_w), available)
        self.height = max(self.formula_h, self.size * 1.2)
        return self.avail, self.height

    def draw(self) -> None:
        from reportlab.pdfbase.pdfmetrics import stringWidth

        canvas = self.canv
        formula_x = max(0.0, (self.avail - self.formula_w) / 2.0)
        formula_y = max(0.0, (self.height - self.formula_h) / 2.0)
        self.formula.drawOn(canvas, formula_x, formula_y)
        baseline = formula_y + self.formula_h / 2.0 - self.size * 0.35
        number_w = stringWidth(self.number, self.font, self.size)
        number_x = max(0.0, self.avail - number_w)
        leader_start = formula_x + self.formula_w + self.gap_em * self.size
        span = number_x - leader_start
        canvas.setFont(self.font, self.size)
        if span > 0:
            dot = stringWidth(self.ellipsis, self.font, self.size)
            count = int(span / dot + 1e-9) if dot > 0 else 0
            if count > 0:
                # 余量按字间距均摊到每个省略号字形之间，引导线恰好填满公式与
                # 编号之间的整段（源文排法：编号前无空格）。
                extra = span - count * dot
                text = canvas.beginText()
                text.setFont(self.font, self.size)
                text.setCharSpace(extra / count)
                text.setTextOrigin(leader_start, baseline)
                text.textOut(self.ellipsis * count)
                canvas.drawText(text)
        canvas.drawString(number_x, baseline, self.number)


def _formula_number_text(number: Any) -> str:
    """公式编号标签 → 显示文本：1 → (1)、A.1 → (A.1)（GB/T 1.1-2020 9.9.2 圆括号）。"""
    label = str(number or "").strip()
    return f"({label})" if label else ""


def _text_width(text: str, style: Any) -> float:
    """按段落样式的字体/字号测算文本宽度（reportlab 在本模块内延迟导入）。"""
    try:
        from reportlab.pdfbase.pdfmetrics import stringWidth

        return float(stringWidth(str(text), style.fontName, style.fontSize))
    except Exception:  # pragma: no cover - 无 reportlab 环境时仅作估算
        return len(str(text)) * float(getattr(style, "fontSize", 0.0)) / 2.0


class _FootnoteAnchor(_FlowableBase):
    """条文脚注定义占位（鸭子类型 Flowable，不依赖 reportlab 顶层导入）：
    wrap 高度 0，不占正文流；文本由页面钩子在当页页脚（居左细实线下）绘制。

    reportlab 依赖在 render_pdf_file 内延迟导入（本模块顶层不 import reportlab），
    因此这里不继承 Flowable，仅实现 platypus 需要的 wrap/split/draw 协议。
    """

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = str(text)
        self.width = 0
        self.height = 0

    def wrap(self, available_width: float, available_height: float) -> tuple[float, float]:
        return 0, 0

    def split(self, available_width: float, available_height: float) -> list:
        return []  # 0 高块不可再分

    def draw(self) -> None:
        return None


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


def _flowable_natural_width(flowable: Any) -> float:
    """并列列内容的一行自然宽（pt）——GEN-111 的列宽依据。

    段落按 reportlab **自己解析出的片段**（``Paragraph.frags``）用同一套字宽表累加：
    `_markup` 生成的字体切换、上下标（缩小字号）、黑体标签都算进去，与最终排版同源
    （实测「正确：」31.5pt、「dim (能量) = dim (力)×dim (长度)」166.4pt，与渲染出的
    文本行宽一致）。图片用绘制宽（``drawWidth``，与列宽上限收窄同口径）。其余
    flowable（Spacer 等）不参与，返回 0。
    """
    draw_width = getattr(flowable, "drawWidth", None)
    if draw_width:
        return float(draw_width)
    frags = getattr(flowable, "frags", None)
    if not frags:
        return 0.0
    from reportlab.pdfbase import pdfmetrics

    total = 0.0
    for frag in frags:
        for item in (frag if isinstance(frag, list) else [frag]):
            text = getattr(item, "text", "")
            if not text:
                continue
            try:
                total += pdfmetrics.stringWidth(text, item.fontName, item.fontSize)
            except Exception:                   # 字体未注册等不该拖垮整篇渲染
                continue
    return total


def _side_by_side_widths(needs: list[float], avail: float) -> list[float]:
    """并列组列宽（GEN-111）：先**等分**（对照型「正确/不正确」并列保持对称），
    再把排不下的列的缺口从有余量的列按余量比例补过去（让宽），直到每列都容得下
    自己的内容、或再无可让。

    与旧口径（只按图/公式绘制宽比例分）的区别：① 文字内容（含 GEN-106 拍平的
    含汉字公式）也计入需求——旧口径对无图列给 60pt 占位，GB/T 1.1-2020 9.9.3.1
    示例4 右栏因此只有 131pt，把「dim (能量) = dim (力)×dim (长度)」挤成两行；
    ② 总量够时每列都拿到自身所需（不会出现「版心明明够却折行」），且对称性不被
    内容长短打破（示例4 源排版即约 226/235 的近等分）。
    """
    count = len(needs)
    if count == 0:
        return []
    widths = [avail / count] * count
    for _ in range(4 * count + 8):
        shortfall = [max(0.0, need - width) for need, width in zip(needs, widths)]
        surplus = [max(0.0, width - need) for need, width in zip(needs, widths)]
        total_shortfall = sum(shortfall)
        total_surplus = sum(surplus)
        if total_shortfall <= 1e-9 or total_surplus <= 1e-9:
            break
        give = min(total_shortfall, total_surplus)
        for index, value in enumerate(shortfall):
            if value > 0:
                widths[index] += give * value / total_shortfall
        for index, value in enumerate(surplus):
            if value > 0:
                widths[index] -= give * value / total_surplus
    return widths


# 分图编号（GB/T 1.1-2020 9.7.6：只准许对图作一个层次的细分，分图用后带半圆括号的
# 小写拉丁字母编号 a)、b)…）。渲染端据此区分「图题注」与「分图题注」两种形态。
_SUB_FIGURE_NUMBER_RE = re.compile(r"^[A-Za-z][)）]$")


def _figure_caption_text(figure: dict[str, Any]) -> str:
    """图题注文本（GBT-B06、GB/T 1.1-2020 9.7.2/9.7.6、10.4.2）。

    - 通栏图：``图{编号} {图题}``（如「图3 输入端与波发生器凸轮连接方式」）；
    - 分图：分图题注**不带「图」字**——源版面即「a） Ⅰ型」，GB/T 1.1-2020 9.7.6 给分图
      编号而未把分图提升为独立图号，故输出 ``{分图编号} {分图题}``；
    - 编号与题名都缺时返回空串，渲染端据此不输出题注行（GBT-B08）。
    """
    number = str(figure.get("number") or "").strip()
    caption = str(figure.get("caption") or "").strip()
    if not number and not caption:
        return ""
    if number and _SUB_FIGURE_NUMBER_RE.match(number):
        return f"{number} {caption}".strip()
    return f"图{number} {caption}".strip()


def _figure_caption_style(figure: dict[str, Any], styles: dict[str, Any]) -> Any:
    """图题注样式：分图编号、分图题小五号黑体，其余五号黑体（GBT-B06、附录F 序号36—40）。"""
    number = str(figure.get("number") or "").strip()
    if number and _SUB_FIGURE_NUMBER_RE.match(number):
        return styles["subcaption"]
    return styles["caption"]


def _append_side_by_side(story: list[Any], members: list[dict[str, Any]], registries: dict[str, dict[str, dict[str, Any]]], styles: dict[str, Any], font: str, report: PDFRenderReport, asset_dir: Path, colors: Any, Table: Any, TableStyle: Any, Paragraph: Any, Spacer: Any, Image: Any, content_width: float = _BODY_MEASURE) -> None:
    """Render a side-by-side group as one borderless table row (div 定位等价物)。

    每列是一个单元格（flowables 垂直堆叠）：图按 sourceWidth 原尺寸居中，公式图
    按原尺寸居中（列宽上限内只缩小不放大），图内标注/说明文字用 side-cell 样式列内
    居中。无 GRID/BOX 命令 → 无表格线。列宽按 ssir:columns 的 widths 比例（缺省按
    GEN-111：等分起步、按各列内容的**实测自然宽**互补让宽）。
    """
    from reportlab.platypus import KeepTogether

    columns: dict[int, list[dict[str, Any]]] = {}
    for content in members:
        columns.setdefault(int(content.get("sideBySideColumn", 0)), []).append(content)
    col_keys = sorted(columns)
    if not col_keys:
        return
    col_index = {col: position for position, col in enumerate(col_keys)}
    # 显式列宽比（ssir:columns 的 widths 属性，同组成员同值；尺寸不符则忽略）。
    ratios: list[float] = []
    raw_ratios = members[0].get("sideBySideWidths")
    if raw_ratios:
        try:
            ratios = [float(value) for value in raw_ratios]
        except (TypeError, ValueError):
            ratios = []
    if len(ratios) != len(col_keys) or any(value <= 0 for value in ratios):
        ratios = []
    col_flowables: list[list[Any]] = []
    natural_widths: list[float] = []
    # 公式图（新）：记录 (image, 列序号) 供列宽定下后按列宽上限收窄，防穿列。
    formula_images: list[tuple[Any, int]] = []
    for col in col_keys:
        cell: list[Any] = []
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
                        scale = min(1.0, content_width / float(source_width), 520 / float(source_height))
                        draw_w = float(source_width) * scale
                        draw_h = float(source_height) * scale
                    else:
                        scale = min(1.0, content_width / image.imageWidth, 520 / image.imageHeight)
                        draw_w = image.imageWidth * scale
                        draw_h = image.imageHeight * scale
                    image.drawWidth = draw_w
                    image.drawHeight = draw_h
                    image.hAlign = "CENTER"
                    cell.append(image)
                    # 并列组内的图同样渲染图题注（GBT-B06：图编号和图题置于图之下居中）
                    # ——修复前图片成员只画图、不画题注，图题注在并列路径整体丢失，
                    # 只剩图内像素（GB_T_30819-2024 4.1.8 图3 的 a)～d) 分图题）。
                    caption = _figure_caption_text(figure)
                    if caption:
                        cell.append(Paragraph(_markup(caption), _figure_caption_style(figure, styles)))
                else:
                    report.warnings.append(f"Missing figure asset in side-by-side group: {figure.get('id')}")
            elif kind == "formula":
                # 并列列内的公式（GB/T 1.1 9.9.3.1 示例3/4 型"正确/不正确"对照）：
                # 与正文公式同规则取原图（MinerU 裁剪图 / MathText 生成图），列内居中。
                formula = registries["formulas"].get(content.get("formulaRef", ""))
                if formula:
                    asset = formula.get("assetRef")
                    source_image = _resolve_asset(asset_dir, asset) if asset else Path("")
                    raw_formula = str(formula.get("latex") or formula.get("rawText") or "")
                    # 列内公式与正文公式同规：GEN-105（生成图按 72/DPI 换算 + 归一到
                    # 正文字号）、GEN-106（含汉字且无可用资产 → 文本拍平，不交给 MathText）。
                    image_path: Path | None
                    if source_image.is_file():
                        image_path, native_scale, text_fallback_reason = source_image, 1.0, ""
                    elif _latex_has_cjk(raw_formula):
                        image_path, native_scale = None, 1.0
                        text_fallback_reason = "contains CJK and has no usable image asset"
                    else:
                        image_path = _formula_image(raw_formula, asset_dir)
                        native_scale = _formula_image_scale(float(styles["body"].fontSize))
                        text_fallback_reason = "could not be typeset"
                    if image_path:
                        image = Image(str(image_path))
                        scale = min(native_scale, content_width / image.imageWidth, 140 / image.imageHeight)
                        image.drawWidth = image.imageWidth * scale
                        image.drawHeight = image.imageHeight * scale
                        image.hAlign = "CENTER"
                        cell.append(image)
                        formula_images.append((image, col_index[col]))
                    else:
                        report.warnings.append(
                            f"Formula in side-by-side group typeset as text ({text_fallback_reason}): {formula.get('id')}"
                        )
                        fallback = _inline_math_markup(raw_formula)
                        if fallback.strip():
                            cell.append(Paragraph(_markup(fallback), styles["side-cell"]))
            elif kind in {"paragraph", "note", "quote", "example", "warning"}:
                text = str(content.get("textContent") or "")
                if text.strip():
                    # 图内注/示例标记同规则（GBT-B10/B11）：标记黑体。
                    cell.append(Paragraph(_label_markup(text.strip(), font, styles["side-cell"].fontSize), styles["side-cell"]))
            elif kind == "list":
                for item in sorted(content.get("listItems", []), key=_order):
                    marker = _list_marker(str(item.get("marker", "-")))
                    cell.append(Paragraph(_markup(f"{marker} {item.get('text', '')}".strip()), styles["side-cell"]))
        col_flowables.append(cell)
        # 列需求（GEN-111）：该列所有内容的一行自然宽（图/公式绘制宽、文字实测行宽），
        # 不是「最宽图」——GEN-106 拍平成文字的含汉字公式与「正确：」这类标签同样计入。
        natural_widths.append(max((_flowable_natural_width(item) for item in cell), default=0.0))
    # 列宽：显式 widths 比例优先；否则按 GEN-111 分配——等分起步、按各列实测需求
    # 互补让宽（总量够时每列都容得下自己的内容；示例框内宽 421.5pt 亦然）。
    # 无内容列给保底宽度（60pt），避免零宽列。
    avail = content_width - 8 * len(col_keys)  # 单元格左右 padding
    if ratios:
        total_ratio = sum(ratios)
        col_widths = [avail * value / total_ratio for value in ratios]
    else:
        col_widths = _side_by_side_widths([w or 60.0 for w in natural_widths], avail)
    # 公式图按所在列可用宽收窄（保留纵横比）：显式 ratios 比内容窄时不穿列。
    for image, position in formula_images:
        limit = col_widths[position] - 8
        if limit > 0 and image.drawWidth > limit:
            scale = limit / image.drawWidth
            image.drawWidth *= scale
            image.drawHeight *= scale
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


def _append_node(story: list[Any], node: dict[str, Any], registries: dict[str, dict[str, dict[str, Any]]], styles: dict[str, Any], font: str, report: PDFRenderReport, asset_dir: Path, colors: Any, Table: Any, TableStyle: Any, Paragraph: Any, Spacer: Any, Image: Any, marker_factory: Any = None, PageBreak: Any = None, example_default: str = "frame", example_leading: bool = False, content_width: float = _BODY_MEASURE, box_inner_width: float | None = None) -> None:
    # 规则对应: GBT-B02（章条编号顶格、空一字接排标题）、GBT-B05（附录另起一面、编号/
    # 性质/标题各占一行居中）、GBT-B06/B07（图题表题五号黑体居中）、GEN-073（整体性保护）。
    # content_width/box_inner_width：当前容器可用内容宽 / 示例线框内宽（见 _append_nodes）。
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
        _append_content_sequence(story, node.get("contentElements", []), registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, content_width=content_width, enclosing=number or None)
        _append_nodes(story, node.get("children", []), registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default, content_width=content_width, box_inner_width=box_inner_width)
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
    # 无编号"示例："块（parser 把独立示例题注行提升为 documentBlock，GB/T 1.1
    # 10.4.5）在 front 样式里渲染；标记仍按 GBT-B11 用黑体（_label_markup 对其余
    # 标题是恒等变换）。
    story.extend(_term_entry_flowables(node, number, title, heading, heading_style, styles, font, Paragraph))
    _append_content_sequence(story, node.get("contentElements", []), registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, content_width=content_width, enclosing=number or None)
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
                _append_node(story, child, registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default, content_width=content_width, box_inner_width=box_inner_width)
        else:
            _append_nodes(story, children, registries, styles, font, report, asset_dir, colors, Table, TableStyle, Paragraph, Spacer, Image, marker_factory, PageBreak, example_default, content_width=content_width, box_inner_width=box_inner_width)


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
    - •（U+2022，OCR 对实心圆点 ● 的常见误读/变体）→ ● 实心圆点——2026-09-07
      用户裁定：列项符号保持 ● 的视觉大小（● 在宋体字形墨迹约占 0.87 字高），
      不再归一为间隔号 ·（· 墨迹极小、不像列项；GB_T_1.1-2020 8.3 前言等列表
      原稿即为 ●）。官方第二层次间隔号 ·（U+00B7）标记不受影响、原样保留。
    解析层多数派统一未覆盖的平手列表（如 ['-', '—']、['———', '————']）在
    渲染层兜底归一，保证同一列表视觉一致（GBT-C12）。
    """
    if marker and all(ch in "-—–" for ch in marker):
        return "——"
    if marker == "•":
        return "●"
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
# 表注显式标记（GBT-X04 执行侧；2026-09-07 语法定案，docs/07 §6.7）：
# - [:^a] 引用点（插入被注释内容之后）→ 上标裸小写字母 a；
# - [^a]  注文段开始 → 上标裸小写字母 a（即原“a 说明”行首字母的版式）；
# - [^a/] 注文段结束 → 纯定界符，不渲染（注文段可多条、<br> 分隔同格排布，
#   文字以引号/汉字等任意字符开头均可——不再需要字形猜测）。
# 2026-09-07 起移除“汉字后小写字母=上标”的启发式：语料表注锚点/注文全部
# 迁移为显式标记（CSM-OCR-015 回收与 normalize 生成端同步发射标记），单元格
# 内字面小写字母（单位 kg/m、mm、变量等）一律按普通文本渲染。
# 行内角标标记（docs/07 §6.7；2026-09-11 通用化，取代按字母成对定义的
# [:^a] / [^a]…[^a/] 形式——那种写法每种角标字符都要一对新记号）：
# - 开标记 [:sup:a] / [:sub:2]：`sup`/`sub` = 上角标/下角标，其后是角标显示的
#   字符（1—4 个字符，如 a、1)、*、†）；
# - 闭标记 [:/sup] / [:/sub]：与最近的开标记配对，本身不渲染；开闭之间的文本是
#   该角标的**注解区**（表注注文、图表注、脚注解释文字），按普通文本渲染；
# - 自闭合 [:sup:a/]（= 空注解区）：角标插在此处，即“引用点”（表注引用、
#   单元格内被注释内容之后）。
# 配对校验与旧形式迁移见 parser（CSM-STRUCT-007）。
_INLINE_SCRIPT_OPEN_RE = re.compile(
    r"\[:(?P<script>sup|sub):(?P<char>[^\[\]/\s]{1,4})(?P<self>/)?\]"
)
_INLINE_SCRIPT_CLOSE_RE = re.compile(r"\[:/(?P<script>sup|sub)\]")
# 旧形式（2026-09-07 语法定案版）：[:^a] 引用点、[^a]…[^a/] 注文段；parser 迁移。
_TABLE_NOTE_CITE_RE = re.compile(r"\[\:\^([a-z])\]")
_TABLE_NOTE_DEF_OPEN_RE = re.compile(r"\[\^([a-z])\]")
_TABLE_NOTE_DEF_CLOSE_RE = re.compile(r"\[\^([a-z])\/\]")


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
    # GFM 条文脚注标记 [^N]（docs/07 §6.7 / CSM-OCR-014 回收产物）→ 上角标 “N)”。
    text = re.sub(r"\[\^([0-9A-Za-z_-]+)\]", lambda m: "\x00SUP\x00" + m.group(1) + ")\x00/SUP\x00", text)
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
    """表格单元格/表注的脚注角标渲染（GBT-X04 / GBT-C18 执行侧）。

    2026-09-11 起按**通用行内角标标记**处理（docs/07 §6.7）：
    - 自闭合 `[:sup:a/]` / `[:sub:2/]` → 角标字符（引用点：表注引用、被注释内容后）；
    - 成对 `[:sup:a]…[:/sup]` → 开标记处的角标字符 + 注解区文本（表注注文、
      注/脚注解释文字），闭标记不渲染；
    - 旧形式 `[:^a]` / `[^a]…[^a/]` 兼容渲染（parser 会迁移为新形式，见
      CSM-STRUCT-007）；
    - GFM 条文脚注 `[^N]`（表内引用条文脚注时）→ 上标 “N)”（不变，docs/07 §6.7）；
    - 拍平指数还原（s−1→s⁻¹、N/m2→N/m²、10-2→10⁻²、10²4→10²⁴）只保留
      **抽取里有证据**的分支（显式负号 / Unicode 上标字形 / 单位字母锚点）；
      「10+纯数字」的纯猜测分支已删除（GEN-104，2026-09-15：抽取层对
      “10 的正幂”没有任何字号或标签证据，`105`(温度等级)/`1024 bit`/
      `107`/`10800` 这类普通数值会被整串改写成 10 的幂）；
    - 表注列项连排（同格多条注）：相邻两对标记之间**自动换行**——canonical 连排
      不写 <br>，此处按 inline_script_item_breaks 插换行哨兵（2026-09-11 用户裁定）。
    语料表注锚点/注文全部为显式标记后，单元格内字面小写字母（单位 kg/m、mm、
    变量等）一律按普通文本渲染，不做任何字形猜测。
    """
    text = inline_script_item_breaks(text)
    text = _INLINE_SCRIPT_CLOSE_RE.sub("", text)
    text = _INLINE_SCRIPT_OPEN_RE.sub(
        lambda m: f"\x00{'SUP' if m.group('script') == 'sup' else 'SUB'}\x00{m.group('char')}\x00/{'SUP' if m.group('script') == 'sup' else 'SUB'}\x00",
        text,
    )
    # 旧形式兼容（parser 迁移前的 canonical/SSIT 仍可能带着）。
    text = _TABLE_NOTE_DEF_CLOSE_RE.sub("", text)
    text = _TABLE_NOTE_DEF_OPEN_RE.sub(lambda m: f"\x00SUP\x00{m.group(1)}\x00/SUP\x00", text)
    text = _TABLE_NOTE_CITE_RE.sub(lambda m: f"\x00SUP\x00{m.group(1)}\x00/SUP\x00", text)
    # GFM 条文脚注引用（[^N] → 上标 “N)”）；只做引用转换，不做任何字母字形
    # 猜测（正文解释行的行首字母规则见 _footnote_superscripts，仅用于表外段落）。
    text = re.sub(r"\[\^([0-9A-Za-z_-]+)\]", lambda m: f"\x00SUP\x00{m.group(1)})\x00/SUP\x00", text)
    # 上角标还原（2026-09-02，GB_3100-2026 表2/表3/附录B 等）：MinerU 文本抽取
    # 把上标拍平成普通字符——s−1→s⁻¹、N/m2→N/m²、10-2→10⁻²、10²4→10²⁴。
    # 只作用于表格单元格（上下文受限，单元格几乎必是单位/量值），正文不做
    # （正文的拍平指数要么带 <sup> 标签、要么是 LaTeX，各自处理）。
    #
    # 规则对应: GEN-104（上标还原只认抽取里存在的证据，纯数字串不猜）。原
    # 「10([1-9]\d{0,2})」纯数字分支已删除——抽取层（MinerU markdown 与
    # middle.json，span 不带字号）对「10 的正幂」没有任何证据可言，该串与
    # 普通数值完全同形：GB/T 5171.1-2014 表1 的「105(A级)」温度等级被印成
    # 10⁵（源 PDF p12 实测 105 与同行同为 8.25pt 普通数字）、GB_3100-2026 的
    # 「1024 bit」「(π/10800) rad」、GB/T 10401-2023 表内数据「107」同族。
    # 语料实测该分支命中 12 处、真阳性 0 处；真正的上标在抽取里带证据
    # （LaTeX `$10^{24}$`、`<sup>` 标签或 Unicode 上标字形），走下列分支。
    # 1) 单位字母后 −/[-] 数字（s−1、Ω−1、s-1）——字母限定小写+希腊防误伤
    #    "A-1" 类代号；数字后不再跟数字（"s-10" 整串上标由 {1,2} 覆盖）。
    text = re.sub(r"(?<=[a-zμΩ])[−-](\d{1,2})(?![0-9])", "\x00SUP\x00−\\1\x00/SUP\x00", text)
    # 2) 10 的负幂：10-1→10⁻¹、10-30→10⁻³⁰（"10-2" 前面是数字 0，规则 1 不命中）。
    #    负号是抽取里真实存在的证据（数字中间的减号不是数值的一部分）。
    text = re.sub(r"10[−-](\d{1,2})(?![0-9])", "10\x00SUP\x00−\\1\x00/SUP\x00", text)
    # 3) 半上标混合：10²4→10²⁴、10³0→10³⁰（MinerU 部分识别 Unicode 上标）；
    #    ²³¹ 归一为数字再进 <super>（字形本身已上标，双重缩小且与后续普通
    #    数字混排不齐）。Unicode 上标字形本身即证据。
    text = re.sub(
        r"10([²³¹])(\d)",
        lambda m: f"10\x00SUP\x00{_SUP_GLYPH_TO_DIGIT[m.group(1)]}{m.group(2)}\x00/SUP\x00",
        text,
    )
    # 4) 单位字母后平印 2/3：N/m2→N/m²、cm3→cm³（排除大写 "A2" 纸型等）。
    text = re.sub(r"(?<=[a-zμΩ])2(?![0-9A-Za-z])", "\x00SUP\x002\x00/SUP\x00", text)
    text = re.sub(r"(?<=[a-zμΩ])3(?![0-9A-Za-z])", "\x00SUP\x003\x00/SUP\x00", text)
    return text


_CLAUSE_NUMBER_RE = r"(?:\d+\.){1,4}\d+|[A-Z]\.\d+(?:\.\d+)*"
# 条号后允许的正文首字符：汉字、全角/半角括号、引号族（“”‘’「『《〈）。
# 引号必须包含——MinerU 常把 9.4.2.2“尽可能”这类裸条正文以引号开头，
# 若不在集合内则该行既不顶格、编号后也不补空格（GB_T_1.1-2020 实测）。
_CLAUSE_AFTER = r"\u4e00-\u9fff（(“”‘’「『《〈[('\""
# 条号后接拉丁字母的形态（"4.2 SI 是采用如下常量的单位制："、"8.2.5 SI词头符号…"）：
# 与「数值 + 单位符号」句（"3.2 kW 的电机应可靠工作。"）在文本上完全同形，单看文本
# 无法区分，故这一类只在**文档结构确认**时才算条首（见 _clause_leading_number）。
_CLAUSE_LATIN_AFTER_RE = re.compile(rf"^({_CLAUSE_NUMBER_RE})[ \u3000]*(?=[A-Za-z])")


def _clause_parent_number(number: str) -> str:
    """条号的父条号（"8.2.5" → "8.2"；单段编号返回空串）。"""
    return number.rsplit(".", 1)[0] if "." in number else ""


def _node_clause_number(node: dict[str, Any]) -> str | None:
    """结构节点自身的条号（无编号节点如前言/目次返回 None）。

    用于确认「编号后接拉丁字母」的裸条：编号必须是所在节点条号的**直接子条**
    （4.2 在章 4 内、8.2.5 在 8.2 内），见 `_clause_leading_number`。
    """
    number = _heading_parts(node)[0].strip()
    return number or None


def _clause_head_gap(text: str, number: str) -> str:
    """条首编号后的固定字隙（GBT-B02「编号后空一个汉字接排」的调用方补写）。

    编号后接拉丁字母的条首不走 `_markup()` 的共享正则（`_CLAUSE_AFTER` 不含拉丁
    字母，否则数值句 "3.2 kW 的电机…" 也会被认成条号并补间隔），故字隙由调用方
    写入：消费编号后的空白、写 1 汉字宽度的白色占位字哨兵。编号后是汉字/括号时
    原样返回——那种形态由 `_markup()` 的共享正则负责。
    """
    pattern = re.compile(rf"^(\s*{re.escape(number)})[ \u3000]*(?=[A-Za-z])")
    return pattern.sub(lambda match: match.group(1) + "\x00GAP\x00", text, count=1)


def _clause_leading_number(text: str, enclosing: str | None = None) -> str | None:
    """Return the leading clause number when a body paragraph starts with one.

    Untitled clauses (裸条) live in the CSM as bare paragraphs whose first
    line begins with the clause number ("5.5.2承压零件应做…").  GB/T 1.1
    typesets clause numbers flush left (顶格), so such paragraphs must not
    take the two-Han-character body first-line indent.  The lookahead is
    kept identical to _markup()'s clause-line normalisation so the two
    decisions stay consistent.

    编号后接汉字/括号/引号（含引号族，"9.4.2.2“尽可能”"）时，形态本身足以判定。
    编号后接**拉丁字母**（"4.2 SI 是采用如下常量的单位制："）时，文本与「数值 +
    单位符号」句（"3.2 kW 的电机应可靠工作。"）完全同形，故只在给了结构上下文
    ``enclosing``（所在节点的条号）且该编号是其**直接子条**时才认（4.2 在章 4
    内）；无上下文或父条号不匹配时保守退回正文段。已知局限：更深的裸条
    （4.2.1 直接挂在章 4 下）与落在同号章内的数值句仍无判据（docs/12 §3.59）。

    规则对应: GBT-B02（条编号顶格编排，编号后空一个汉字接排）。
    """
    stripped = str(text).strip()
    match = re.match(
        rf"^({_CLAUSE_NUMBER_RE})(?=[ \u3000]*[{_CLAUSE_AFTER}])",
        stripped,
    )
    if match:
        return match.group(1)
    if enclosing:
        latin = _CLAUSE_LATIN_AFTER_RE.match(stripped)
        if latin and _clause_parent_number(latin.group(1)) == str(enclosing).strip():
            return latin.group(1)
    return None


# 注/示例的标记（"注："/"注1："/"示例："/"示例1："）：GB/T 1.1-2020 10.4.4.1/10.4.5
# 与附录 F 表 F.1 序号 42/44 规定——**标记用小五号黑体、内容用小五号宋体**
# （GBT-B10/GBT-B11 执行侧，2026-09-11）。冒号是标记的一部分（"注1："整段加黑）；
# 无冒号的"示例1示出了…"（20001.5 附录 A 实测）是行内引用而非标记，不加黑。
_NOTE_EXAMPLE_LABEL_RE = re.compile(r"^(?:注|示例)\s*\d*\s*[:：]")


def _note_example_label_span(text: str) -> tuple[str, str, str]:
    """行首注/示例标记切分：(标记前空白, 标记, 其余)。无标记时标记为空串。

    前导空白（OCR/canonical 里 "…<br> 注1：…" 的空格）单独返回，不进黑体区——
    黑体只覆盖标记本身（GB/T 1.1-2020 附录 F 表 F.1 序号 42/44）。
    """
    raw = str(text)
    lead = raw[: len(raw) - len(raw.lstrip())]
    match = _NOTE_EXAMPLE_LABEL_RE.match(raw[len(lead):])
    if not match:
        return raw, "", ""
    return lead, match.group(0), raw[len(lead) + match.end():]


def _note_example_label(text: str) -> str:
    """行首注/示例标记（含冒号）；无标记返回空串。"""
    return _note_example_label_span(text)[1]


def _unit_line_style(styles: dict[str, Any]) -> Any:
    """单位陈述行（"单位为毫米"）样式（GEN-032）：小五号右对齐、上下无空（紧贴图/表框）。

    图与表共用同一样式，避免两处各写一份（图侧见 `_append_content` 的 figure 分支）。
    """
    from reportlab.lib.styles import ParagraphStyle

    return styles.get("table-unit") or ParagraphStyle(
        "gbt-table-unit", parent=styles["body"], alignment=2, fontSize=9, leading=12, spaceAfter=0, firstLineIndent=0,
    )


def _append_content(story: list[Any], content: dict[str, Any], registries: dict[str, dict[str, dict[str, Any]]], styles: dict[str, Any], font: str, report: PDFRenderReport, asset_dir: Path, colors: Any, Table: Any, TableStyle: Any, Paragraph: Any, Spacer: Any, Image: Any, content_width: float = _BODY_MEASURE, enclosing: str | None = None) -> None:
    # 规则对应: GEN-032（表格题注拆分：居中题注 + 右对齐单位行）、GBT-B04（列项缩进）、
    # GBT-B10（注标记小五号黑体、注内容小五号宋体）、GBT-B11（示例标记小五号黑体、
    # 示例内容小五号宋体）、GBT-X06（公式另行居中、编号右对齐）、GBT-X01/B06（图与图题）。
    from reportlab.platypus import KeepTogether

    kind = content.get("presentationType")
    if kind in {"paragraph", "quote", "warning", "example", "footnote"}:
        text = str(content.get("textContent", ""))
        # GB/T 1.1 figure caption paragraph: "图 2 尼龙丝卷曲判定" 等题注被
        # MinerU 抽成独立段落时按图题渲染（黑体居中，同 figure caption）。
        figure_caption_match = re.match(r"^(图\s*\d+\.?\d*[^\n]*)$", text.strip())
        # GB/T 1.1 table caption block: "表 X.Y 题名\n单位为毫米" — the unit
        # line renders small and flush right, directly above the table frame.
        caption_match = re.match(r"^(表\s*[A-Z]?\d*\.?\d*[^\n]*)\n(单位为[^\s]{1,4})\s*$", text.strip())
        unit_only = re.fullmatch(r"单位为[^\s]{1,4}", text.strip())
        if figure_caption_match:
            caption_flowable = Paragraph(_markup(figure_caption_match.group(1).strip()), styles["caption"])
            if _TOC_FIGURE_CAPTION_RE.match(text.strip()):
                # 目次「图N」行的页码来源（预检通道按 id 记录本段所在页）。
                caption_flowable.ssir_id = str(content.get("id") or "")
            story.append(caption_flowable)
        elif caption_match:
            story.append(Paragraph(_markup(caption_match.group(1).strip()), styles["caption"]))
            story.append(Paragraph(_markup(caption_match.group(2)), _unit_line_style(styles)))
        elif unit_only:
            # 兼容路径：未被折进图/表节点的独立单位行（旧 canonical 与手写稿）仍按
            # 右对齐渲染，只是不与图/表同组（新写出的单位行都折进节点，见 docs/12 §3.54）。
            story.append(Paragraph(_markup(text.strip()), _unit_line_style(styles)))
        else:
            # Untitled clause paragraphs (bare text starting with the clause
            # number) render flush left per GBT-B02; ordinary body text keeps
            # the two-Han-character first-line indent.
            if kind == "footnote":
                # 脚注定义：占位（0 高），文本由页钩子绘到本页页脚（不占正文流位置）。
                story.append(_FootnoteAnchor(content.get("textContent", "")))
            else:
                # 编号后接拉丁字母的裸条（"4.2 SI 是采用…"）需要所在节点的条号确认，
                # 故把节点的条号（enclosing）传进判定；无上下文时退回正文段。
                clause_number = _clause_leading_number(text, enclosing)
                style = styles["body-flush"] if clause_number else styles["body"]
                if clause_number:
                    # 该类条首的字隙不由 _markup 补（共享正则不含拉丁字母），
                    # 调用方写 1 汉字字隙哨兵（GBT-B02）；见 _clause_head_gap。
                    text = _clause_head_gap(text, clause_number)
                # 正文里的注/示例标记（"示例1：…"、"注2：…"，GB/T 1.1 10.4.4.1/
                # 10.4.5）与注块同规则：标记黑体、内容宋体。
                paragraph = Paragraph(_label_markup(_footnote_superscripts(text), font, style.fontSize), style)
                if _TOC_FIGURE_CAPTION_RE.match(text.strip()):
                    # 附录图题（「图 B.1 标记体系的组成」）不在上面的图题形态内，
                    # 按正文段落排版，但仍是目次「图N」行的页码来源。
                    paragraph.ssir_id = str(content.get("id") or "")
                story.append(paragraph)
    elif kind == "note":
        text = str(content.get("textContent") or "")
        style = styles["note"]
        # 注标记黑体、注内容小五号宋体（GBT-B10；附录F 表F.1 序号44/45）。
        label = _note_example_label(text)
        if label:
            from reportlab.pdfbase.pdfmetrics import stringWidth

            # 注自动回行对齐“注N：”冒号后的正文起点（悬挂缩进），而非对齐“注”字
            # 本身：回行行首 = 原缩进 + 题注前缀宽（firstLineIndent 为负拉回首行）。
            # 前缀已加黑（黑体字形），宽度按**实际标记字体**实测（profile 可指定
            # 黑体粗，见 _LABEL_FONT）。
            label_width = stringWidth(label, _LABEL_FONT or font, style.fontSize)
            hanging = style.clone("gbt-note-hang", leftIndent=style.leftIndent + label_width, firstLineIndent=-label_width)
            story.append(Paragraph(_label_markup(text, font, em_size=hanging.fontSize), hanging))
        else:
            story.append(Paragraph(_label_markup(text, font, em_size=style.fontSize), style))
    elif kind == "list":
        items = sorted(content.get("listItems", []), key=_order)
        markers = [str(item.get("marker", "-")) for item in items]
        ocr_l_one = _ocr_l_one(markers)
        # 实心/空心圆点（●○•）是下级列项符号：整组清一色圆点时为第一层次列项；
        # 与 a)/1)/—— 等第一层次标记混排时圆点项属第二层次（缩进 2 汉字）。
        norm_markers = [_list_marker(m) for m in markers]
        uniform_bullets = bool(norm_markers) and all(m in ("●", "○", "•") for m in norm_markers)
        for item in items:
            marker = _list_marker(str(item.get("marker", "-")))
            if ocr_l_one and marker in ("1)", "1）"):
                marker = "l）"
            is_bullet = marker in ("●", "○", "•")
            # 数字编号与间隔号属第二层次（list-sub），其余属第一层次（list）；
            # 判定与 docx 侧共用（docx_renderer 导入本函数）。
            list_style = styles["list-sub"] if _list_is_sub_level(marker, uniform_bullets) else styles["list"]
            label = marker
            marker_size = list_style.fontSize
            if is_bullet:
                # 圆点按 0.62× 字号缩小呈现（墨迹≈0.55 字高，2026-09-07 用户裁定
                # 原大字圆点过大；间隔号 · 级过小问题由本级圆点替代解决）。<font>
                # 标签须在 _markup 转义后用哨兵恢复（同 <super> 机制）。
                small = int(round(list_style.fontSize * 0.62))
                marker_size = small
                label = f"\x00BUL\x00{marker}\x00/BUL\x00"
            text_out = _markup(f"{label}{_list_marker_gap(list_style, marker, marker_size)}{item.get('text', '')}")
            if is_bullet:
                text_out = (
                    text_out.replace("\x00BUL\x00", f'<font size="{small}">')
                    .replace("\x00/BUL\x00", "</font>")
                )
            story.append(Paragraph(text_out, list_style))
    elif kind == "table":
        _append_table(story, registries["tables"][content["tableRef"]], styles, colors, Table, TableStyle, Paragraph, asset_dir=asset_dir, Image=Image, content_width=content_width, label_font=font)
    elif kind == "formula":
        formula = registries["formulas"][content["formulaRef"]]
        number = _formula_number_text(formula.get("number"))
        asset = formula.get("assetRef")
        source_image = _resolve_asset(asset_dir, asset) if asset else Path("")
        raw_formula = str(formula.get("latex") or formula.get("rawText") or "")
        # 规则对应: GEN-105（显示尺寸按目标字号还原，不把像素当点）、GEN-106（含汉字
        # 的公式不得交给 MathText——它没有汉字字形，会印成假字形方框）。MinerU 裁剪图
        # （assetRef，GEN-102）优先；无可用资产且含汉字 → 按文本拍平渲染。
        image_path: Path | None
        if source_image.is_file():
            image_path, native_scale, text_fallback_reason = source_image, 1.0, ""
        elif _latex_has_cjk(raw_formula):
            image_path, native_scale = None, 1.0
            text_fallback_reason = "contains CJK and has no usable image asset"
        else:
            image_path = _formula_image(raw_formula, asset_dir)
            native_scale = _formula_image_scale(float(styles["body"].fontSize))
            text_fallback_reason = "could not be typeset"
        number_style = styles["body"]
        formula_flowable: Any
        if image_path:
            image = Image(str(image_path))
            # MinerU equation crops are already tightly fitted at approximately
            # document scale; generated MathText images need the same upper
            # bounds but are otherwise kept at their native size.  Width cap is
            # the current container's content width (body / example box inner).
            # 带编号的公式还会在 _FormulaLeaderLine 里按「两个汉字间隔 + 省略号
            # 引导线 + 右端编号」的需要再收一次宽度（GBT-X06/10.4.3）。
            scale = min(native_scale, content_width / image.imageWidth, 140 / image.imageHeight)
            image.drawWidth = image.imageWidth * scale
            image.drawHeight = image.imageHeight * scale
            image.hAlign = "CENTER"
            formula_flowable = image
        else:
            report.warnings.append(f"Formula typeset as text ({text_fallback_reason}): {formula['id']}")
            formula_flowable = Paragraph(_markup(_inline_math_markup(raw_formula)), styles["formula"])
        if number:
            # 规则对应: GBT-X06（公式编号右端对齐、与公式以“……”连接）。
            story.append(
                _FormulaLeaderLine(
                    formula_flowable, number, number_style.fontName, number_style.fontSize
                )
            )
        else:
            story.append(formula_flowable)
    elif kind == "figure":
        figure = registries["figures"][content["figureRef"]]
        asset = figure.get("assetRef")
        asset_path = _resolve_asset(asset_dir, asset) if asset else Path("")
        if asset and asset_path.is_file():
            image = Image(str(asset_path))
            # 图尺寸：优先使用抽取时从源 PDF 记录的原始版面尺寸
            # （sourceWidth/sourceHeight，pt；_stamp_figure_source_sizes 在
            # 流水线 finalize 阶段写入），使渲染图与原图尺寸相当（GEN-098）。
            # 无记录时按图片固有尺寸（72dpi）缩放，但**只缩小不放大**——
            # MinerU 裁剪图常以高于原版的像素密度导出，放大会远超原图尺寸。
            source_width = figure.get("sourceWidth")
            source_height = figure.get("sourceHeight")
            if source_width and source_height:
                scale = min(1.0, content_width / float(source_width), 520 / float(source_height))
                draw_w = float(source_width) * scale
                draw_h = float(source_height) * scale
            else:
                scale = min(1.0, content_width / image.imageWidth, 520 / image.imageHeight)
                draw_w = image.imageWidth * scale
                draw_h = image.imageHeight * scale
            image.drawWidth = draw_w
            image.drawHeight = draw_h
            image.hAlign = "CENTER"
            # 目次「图N」行的页码来源：预检通道按 ssir_id 记录本图所在页。
            image.ssir_id = str(figure.get("id") or "")
            figure_flowables: list[Any] = [image]
        else:
            report.warnings.append(f"Missing figure asset retained as placeholder: {figure['id']}")
            figure_flowables = [Paragraph(_markup("[图像资产缺失]"), styles["caption"])]
        unit_text = str(figure.get("unit") or "").strip()
        if unit_text:
            # 图的单位陈述（GEN-032 / GB/T 1.1-2020 9.7.4.1）：右对齐画在图上方，并放进
            # 与图、图题同一个 KeepTogether——否则满页的图另起一面时这一行会被留在前页
            # 末（附录 E 的"单位为毫米"本应是每张图页的第一行，见 docs/12 §3.54）。
            figure_flowables.insert(0, Paragraph(_markup(f"单位为{unit_text}"), _unit_line_style(styles)))
        # 题注文本与样式按 GBT-B06 统一（分图编号/分图题 = 小五号黑体、不带「图」字）。
        caption = _figure_caption_text(figure)
        if caption:
            figure_flowables.append(Paragraph(_markup(caption), _figure_caption_style(figure, styles)))
        story.append(KeepTogether(figure_flowables))
    elif kind == "other":
        unknown = registries["unknownContents"].get(content.get("unknownRef"), {})
        # 规则对应: GEN-107（原样块逐字渲染：保留换行与行首缩进、左对齐不拉伸）。
        # 原样块是 canonical 表达「树状结构/伪代码/版式片段」的正式通道
        # （docs/07 §6.10），不能走 _markup 的软换行归一。
        verbatim_style = styles.get("verbatim", styles["body"])
        report.warnings.append(f"Unknown content rendered verbatim: {unknown.get('id', content.get('id'))}")
        story.append(
            Paragraph(
                _markup(_verbatim_markup(str(unknown.get("rawContent", "")), verbatim_style.fontSize)).replace("\x00BR\x00", "<br/>"),
                verbatim_style,
            )
        )


def _table_note_style(styles: dict[str, Any]) -> Any:
    """表注行样式（2026-09-02，GB_3100-2026 表1/表4 注行）：GB/T 1.1 表内注居左、
    首行空两格、小五号；GBT-B09 的"表内文字居中"对注行是例外。"""
    from reportlab.lib.styles import ParagraphStyle

    return ParagraphStyle(
        "gbt-table-note",
        parent=styles["table"],
        alignment=0,
        firstLineIndent=2 * styles["table"].fontSize,
        leftIndent=0,
        spaceAfter=0,
    )


def _table_note_hang_style(styles: dict[str, Any], part: str, base: Any) -> Any:
    """注行悬挂缩进（2026-09-07 用户裁定）：首行「注N：」仍从两字处起排，
    续行（折行文字）左缩进到「注N：」冒号后的文字对齐位置。前缀宽度按
    字形实测（_cell_text_natural_width），避免中文冒号/空格宽度偏差。
    """
    prefix = re.match(r"^(注\s*\d*\s*[:：])", part)
    if not prefix:
        return base
    label_width = _cell_text_natural_width(prefix.group(1), styles["table"].fontSize)
    return base.clone(
        "gbt-table-note-hang",
        leftIndent=2 * styles["table"].fontSize + label_width,
        firstLineIndent=-label_width,
    )


def _table_cell_flowables(
    cell_text: str,
    cell_width: float,
    is_header: bool,
    *,
    styles: dict[str, Any],
    cell_image_sizes: dict[str, list[float]],
    cell_image_re: re.Pattern[str],
    label_font: str = "",
    asset_dir: Path | None = None,
    Image: Any = None,
) -> list[Any]:
    """单元格内容 → 流式对象（列宽分配的折行测量与渲染共用同一实现）。

    表头行居中、数据行居左（2026-09-07 用户裁定；表内注行另行居左排版）。
    单元格行结构（merge 阶段从源文本层恢复的 <br>，如 表1 "术语和定义<br>……"）
    在 _markup 转义后恢复为真实 <br/>，使省略号等独占一行（GBT-B08 表格版式）。
    表中图（GBT-X02）：mineru_html 把单元格内 <img> 附成
    "![](assets/images/<hash>.jpg)" 文本，此处拆出为单元格内 Image flowable
    （优先按原版面尺寸、上限单元格宽缩放、不放大），图片前后文本各自成段。
    表注行（2026-09-02，GB_3100-2026 表1/表4）：单元格以「注N：」开头时，把合并
    进同一格的 注1：…注2：…（以及跨页吸收回表内的续注，<br> 分隔）拆成每条注独立
    一段，居左、首行空两格（GB/T 1.1 表内注版式）。

    2026-09-17：从 ``_append_table`` 的内嵌函数提为模块级——列宽分配（GEN-110）
    需要按同一实现测量「文本 × 列宽 → 折行行数」，测量与渲染必须是同一份代码。
    """
    from reportlab.platypus import Paragraph

    cell_style = styles["table"] if is_header else styles["table-body"]
    flowables: list[Any] = []
    stripped_note = cell_image_re.sub("", cell_text).strip()
    if _TABLE_NOTE_CELL_RE.match(stripped_note):
        base = _table_note_style(styles)
        for note_part in _split_table_note_parts(cell_text):
            note_style = _table_note_hang_style(styles, note_part, base)
            flowables.append(
                Paragraph(
                    # 表内注标记黑体、注内容小五号宋体（GBT-B10；附录F 序号44/45）。
                    _label_markup(_table_cell_superscripts(note_part), label_font, em_size=note_style.fontSize).replace("\x00BR\x00", "<br/>"),
                    note_style,
                )
            )
        return flowables
    position = 0
    for match in cell_image_re.finditer(cell_text):
        text_part = cell_text[position:match.start()]
        if text_part.strip():
            marked = text_part.replace("<br>", "\x00BR\x00")
            flowables.append(Paragraph(_label_markup(_table_cell_superscripts(marked), label_font, em_size=cell_style.fontSize).replace("\x00BR\x00", "<br/>"), cell_style))
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
        flowables.append(Paragraph(_label_markup(_table_cell_superscripts(marked), label_font, em_size=cell_style.fontSize).replace("\x00BR\x00", "<br/>"), cell_style))
    return flowables


def _table_caption_keep_height(
    caption_flowables: list[Any], grid: Any, header_row_count: int, content_width: float
) -> float | None:
    """表题/单位行与表框不得同页拆开（GEN-115 / GBT-B07、GBT-B13）：返回题注所需的竖向空间。

    现象（2026-09-19，GB_T_10401-2023 表A.1）：图 A.1 占满版面后表只放得下三行，
    reportlab 的「不得在 repeatRows/表头内切分」规则让整表推迟到下一页，而作为独立
    流元素的题注与单位行留在前页末尾——**题注孤行**（与 §3.x 图题被留在前页同一问题
    类）。判据只用几何：当前页剩余高 < 题注高 + 全部表头行 + 一行数据 → 先分页。
    只在文档上下文（``_ROTATED_TABLE_MEASURE`` 已由 render_pdf 写入）且所需高不到版心
    八成时返回数值；近乎满页的表头不参与，否则每页都会先分页、表永远起不来。
    """
    frame_height = _ROTATED_TABLE_MEASURE
    if frame_height is None or not caption_flowables:
        return None
    caption_height = 0.0
    for flowable in caption_flowables:
        _, height = flowable.wrap(content_width, frame_height)
        caption_height += float(height)
    grid.wrap(content_width, frame_height)
    # reportlab 的行高表可能留 None（未测量行），按整表均高兜底（只用于「够不够起排」
    # 的判据，不参与真实排版）。
    row_heights = list(getattr(grid, "_rowHeights", None) or [])
    total_height = float(getattr(grid, "height", 0.0) or 0.0)
    average = total_height / len(row_heights) if row_heights else 0.0
    keep_rows = [height if height is not None else average for height in row_heights[: header_row_count + 1]]
    required = caption_height + float(sum(keep_rows))
    if required <= 0 or required >= float(frame_height) * 0.8:
        return None
    return required


def _append_table(story: list[Any], table: dict[str, Any], styles: dict[str, Any], colors: Any, Table: Any, TableStyle: Any, Paragraph: Any, *, asset_dir: Path | None = None, Image: Any = None, content_width: float = _BODY_MEASURE, label_font: str = "") -> None:
    # 规则对应: GBT-B07（表编号表题居中置于表上、表头框线、数字小五号宋体）、
    # GBT-B13/GEN-115（转页接排：完整表头重复 + 续表题注「（续）」 + 单位陈述 + 题注不孤行）、
    # GEN-114（表头行数 header-rows → 底纹与 repeatRows 覆盖全部表头行）、
    # GBT-X02（不准许分表/表中套表；转页重复表头 repeatRows；表中图）、GEN-033（无编号无题名不输出题注）、
    # GBT-B10（表内注标记小五号黑体、注内容小五号宋体）。
    from reportlab.platypus import CondPageBreak, Spacer

    number = str(table.get("number") or "").strip()
    caption = str(table.get("caption") or "").strip()
    unit = str(table.get("unit") or "").strip()
    # A table with neither number nor caption gets no caption line at all
    # (otherwise a lone "表" character would appear above the table).
    # 题注/单位行先攒着：竖排放进正文流；横排（GEN-103）随表一起旋转、落在订口一侧。
    caption_flowables: list[Any] = []
    if number or caption:
        caption_flowables.append(Paragraph(_markup(f"表{number} {caption}".strip()), styles["caption"]))
    # GB/T 1.1 表题注块：单位行（"单位为毫米"）小号右对齐，紧贴表格上方
    # （GEN-032；table-unit 样式 alignment=2 右对齐、spaceAfter=0 贴表框）。
    if unit:
        from reportlab.lib.styles import ParagraphStyle
        unit_style = styles.get("table-unit") or ParagraphStyle(
            "gbt-table-unit", parent=styles["body"], alignment=2, fontSize=9, leading=12, spaceAfter=0, firstLineIndent=0,
        )
        caption_flowables.append(Paragraph(_markup(f"单位为{unit}"), unit_style))
    rows = sorted(table.get("rows", []), key=lambda row: row["rowIndex"])
    # 表头行数（GEN-114）：parser 按 header-rows 打标，此处只数前导表头行——底纹与
    # 转页重复都以它为界（reportlab 的 repeatRows 见 _grid）。
    header_row_count = 0
    for row in rows:
        if not row.get("isHeader"):
            break
        header_row_count += 1
    # 续表题注/单位行（GEN-115、GB/T 1.1-2020 9.8.3）：表跨页时每一片续表都要在重复的
    # 表头之上给出「表N 表题（续）」与单位的陈述（单位为××，右对齐）——由
    # _TrackedTable.split 在分片里插行（new Paragraph，不复用正文那两行）。
    continuation_flowables: list[Any] = []
    if number or caption:
        # 「（续）」按 GB/T 1.1-2020 附录 F 表 F.1 序号 38 用**五号宋体**（表编号/表题仍
        # 五号黑体）——在题注段后内联切换正文字体。
        serif_font = str(styles["body"].fontName)
        continuation_flowables.append(
            Paragraph(
                _markup(f"表{number} {caption}".strip()) + f'<font name="{serif_font}">（续）</font>',
                styles["caption"],
            )
        )
    if unit:
        from reportlab.lib.styles import ParagraphStyle
        unit_style = styles.get("table-unit") or ParagraphStyle(
            "gbt-table-unit", parent=styles["body"], alignment=2, fontSize=9, leading=12, spaceAfter=0, firstLineIndent=0,
        )
        continuation_flowables.append(Paragraph(_markup(f"单位为{unit}"), unit_style))

    cell_image_re = re.compile(r"!\[(?:[^\]]*)\]\(([^)]+)\)")
    # 表中图原始版面尺寸（pt）：_stamp_figure_source_sizes 在流水线 finalize
    # 写入 table["cellImageSizes"] = {ref: [w, h]}，渲染端按原尺寸（上限
    # 单元格宽、不放大）显示，使表中图与原图尺寸相当（GEN-098 / GBT-X02）。
    cell_image_sizes = table.get("cellImageSizes") or {}

    def _render_cell(cell_text: str, cell_width: float, is_header: bool = False) -> list[Any]:
        # 单元格渲染实现已提为模块级 _table_cell_flowables（列宽分配的折行测量与
        # 渲染共用同一份代码，GEN-110）。
        return _table_cell_flowables(
            cell_text, cell_width, is_header,
            styles=styles, cell_image_sizes=cell_image_sizes, cell_image_re=cell_image_re,
            label_font=label_font, asset_dir=asset_dir, Image=Image,
        )

    if not rows or not rows[0].get("cells"):
        return
    col_count = max(len(sorted(row.get("cells", []), key=lambda cell: cell["colIndex"])) for row in rows)
    # 列宽按内容分配（2026-09-03，通用规则：尽量利用版面宽度）：每列需求 =
    # 该列最宽单元格的自然宽度（CJK≈1em、拉丁≈0.55em；colspan 摊分；通栏
    # 注行/单长格不参与），按需求比例把“当前容器可用内容宽”（正文 455pt /
    # 示例框内 421.5pt，2026-09-07 修穿框）全部分配（列宽和恰等于容器宽），
    # 保底 24pt 防空列退化、每列下界「左右边距 + 一个汉字宽」（GEN-103）。
    # 跨列单元格的图片按跨列总宽缩放。
    commands: list[tuple[Any, ...]] = [("GRID", (0, 0), (-1, -1), 0.5, colors.black), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), _TABLE_CELL_PADDING), ("RIGHTPADDING", (0, 0), (-1, -1), _TABLE_CELL_PADDING), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header_row_count:
        # 表头底纹覆盖**全部**表头行（多行表头的 header_rows 实测 2~4，GEN-114）。
        commands.append(("BACKGROUND", (0, 0), (-1, header_row_count - 1), colors.HexColor("#F2F2F2")))
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

    def _grid(widths: list[float]) -> Any:
        """按给定列宽重建表格网格（横排重排时列宽变化 → 单元格需重新折行）。"""
        def _cell_render_width(cell: dict[str, Any]) -> float:
            colspan = int(cell.get("colspan", 1) or 1)
            start = cell["colIndex"]
            return sum(widths[start:start + colspan])

        data = [[_render_cell(cell.get("text", ""), _cell_render_width(cell), is_header=bool(row.get("isHeader"))) for cell in sorted(row.get("cells", []), key=lambda cell: cell["colIndex"])] for row in rows]
        built = _toc_tracked_table_class(Table)(data, colWidths=widths, repeatRows=sum(1 for row in rows if row.get("isHeader")))
        # 目次「表N」行的页码来源：预检通道按 ssir_id 记录本表所在页（render_pdf 的
        # _record_pages）。表在框内/单元格内时 afterFlowable 不触发，其行页码留 0。
        built.ssir_id = str(table.get("id") or "")
        built.setStyle(TableStyle(commands))
        return built

    # 列宽折行测量器（GEN-110）：用渲染端同一实现测「文本 × 列宽 → 行数」，分配按
    # 折行代价（总高 → 折行数 → 折行格数 → 空白平衡）逐段买入。测量器是**文档级**
    # 缓存（挂在 styles 上），同一文档的重复单元格与跨表重复内容直接命中。
    table_measurer = _table_measurer_for(
        styles, cell_image_sizes=cell_image_sizes, cell_image_re=cell_image_re,
        label_font=label_font, asset_dir=asset_dir, Image=Image,
        font_size=styles["table"].fontSize,
    )
    col_widths = _table_column_widths(
        rows, col_count, styles["table"].fontSize, cell_image_sizes, cell_image_re,
        frame_width=content_width, measurer=table_measurer,
    )
    grid = _grid(col_widths)
    # 续表题注/单位行挂在表对象上（GEN-115）：表不分页时这两行不出现（正文那两行照旧）。
    grid._continuation_flowables = continuation_flowables
    # 宽表横排（GEN-103）：竖排下必然排不下的多列表整表旋转 90°（表头落订口一侧）。
    landscape_widths = _table_landscape_widths(
        rows, col_count, styles["table"].fontSize, cell_image_sizes, cell_image_re, content_width, grid,
        measurer=table_measurer,      # 同一测量器：横排判定复用已测结果
        portrait_widths=col_widths,   # 判据③a：竖排列宽是否已被压到下界（读不成表）
    )
    if landscape_widths is not None and _ROTATED_TABLE_CLASS is not None:
        # 横排：题注 + 单位行 + 表格作为一个整体旋转（表头落订口一侧）。
        story.extend([_ROTATED_TABLE_CLASS([*caption_flowables, _grid(landscape_widths)]), Spacer(1, 6)])
        return
    # 框内（_BoxSink）不参与题注防孤行：条件分页是页面级动作，而框内内容最终要进表格
    # 单元格，单元格里不能有分页动作（同 §8「KeepTogether 不能进表格行」的坑）。
    caption_keep = (
        _table_caption_keep_height(caption_flowables, grid, header_row_count, content_width)
        if isinstance(story, list) else None
    )
    if caption_keep is not None:
        # 表题/单位行必须与表框同页（GBT-B07；与图题组同一问题类）：当前页剩余高放不下
        # 「题注 + 全部表头行 + 一行数据」时先分页，题注与表格一起落到下一页。
        story.append(CondPageBreak(caption_keep))
    story.extend([*caption_flowables, grid, Spacer(1, 6)])


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


def _table_column_demands(
    rows: list[dict],
    col_count: int,
    font_size: float,
    cell_image_sizes: dict[str, list[float]],
    cell_image_re: re.Pattern[str],
) -> tuple[list[float], list[float], list[float], list[int]]:
    """每列需求（含左右边距 8pt）、表头底线、数据 80% 分位需求、有内容的列号。

    列宽分配（``_table_column_widths``）与「该表能否在本容器内排下」（GEN-103
    横排判定）共用同一口径，避免两处各算一套需求模型而漂移。
    口径（2026-09-07 四次裁定）：表头行取自然宽 + 12pt（表头底线）；数据行取该列
    各行自然宽（<br> 多行格取最长行）的 80% 分位数 + 8pt；colspan 内容按跨列数
    均摊；整行通栏注行（colspan=全部）与 OCR 丢 colspan 的单长格不挤占；表格图片
    按源版面宽度计。
    """
    def _p80(vals: list[float]) -> float:
        sv = sorted(vals)
        return sv[min(len(sv) - 1, int(0.8 * len(sv)))]

    hdr_nat = [0.0] * col_count
    samples: list[list[float]] = [[] for _ in range(col_count)]
    for row in rows:
        cells = sorted(row.get("cells", []), key=lambda cell: cell["colIndex"])
        plain_text = lambda cell: cell_image_re.sub("", str(cell.get("text", "")))
        filled = [c for c in cells if plain_text(c).strip()]
        lone_full = len(cells) > 2 and len(filled) == 1 and len(plain_text(filled[0])) >= 20
        is_header_row = bool(row.get("isHeader"))
        for cell in cells:
            text = str(cell.get("text", ""))
            colspan = int(cell.get("colspan", 1) or 1)
            if colspan >= col_count or lone_full:
                continue
            # 渲染端 _markup 会把 $...$ LaTeX 拍平为可读文本；需求估算同样拍平，
            # 否则 LaTeX 命令噪声（\mathrm { D a } 等）把列需求撑大（表4 道尔顿行）。
            text = re.sub(r"\$([^$\n]+)\$", lambda m: _latex_to_text(m.group(1)), text)
            demand = _cell_text_natural_width(cell_image_re.sub("", text), font_size)
            for m in cell_image_re.finditer(text):
                src = cell_image_sizes.get(m.group(1))
                demand = max(demand, src[0] if src else 60.0)
            per_col = demand / colspan
            start_col = cell["colIndex"]
            for c in range(start_col, min(start_col + colspan, col_count)):
                if is_header_row:
                    hdr_nat[c] = max(hdr_nat[c], per_col)
                else:
                    samples[c].append(per_col)
    # 列需求 = max(表头底线, 数据 80% 分位 + 左右边距)；空列由调用点的 floor 兜底。
    header_min = [h + 12.0 if h > 0 else 0.0 for h in hdr_nat]
    body_need = [_p80(samples[c]) + 8.0 if samples[c] else 0.0 for c in range(col_count)]
    need = [max(header_min[c], body_need[c]) for c in range(col_count)]
    content = [c for c in range(col_count) if need[c] > 0]
    return need, header_min, body_need, content


class _TableCellMeasurer:
    """列宽分配的折行测量器（GEN-110）：单元格文本 × 列宽 → 折行行数。

    测量走**渲染端同一实现** ``_table_cell_flowables``（`$…$` 拍平、上下标、
    表注悬挂缩进、`<br>` 固定断行、表中图按列宽缩放），因此「分配时算出的行数」
    与「实际渲染的行数」同源；纯文本单元格的流式对象只构建一次、按不同宽度反复
    ``wrap``（reportlab 每次 wrap 都会重排，行数随宽度变化），结果按
    （文本, 表头, 列宽）缓存——同一文档的多张表共用，重复单元格（如「五号黑体」、
    「30」）直接命中。

    ``_synthetic`` 为无渲染上下文（单表渲染 / 单测）时的兜底：按
    ``_cell_text_natural_width`` 的字符宽模型估算行数。**正文渲染一律用真实测量**
    （``_append_table`` 构造），兜底只保证函数在缺 reportlab 样式时仍可用。
    """

    def __init__(self, *, styles: dict[str, Any] | None = None, cell_image_sizes: dict[str, list[float]] | None = None, cell_image_re: re.Pattern[str] | None = None, label_font: str = "", asset_dir: Path | None = None, Image: Any = None, font_size: float = 9.0) -> None:
        self.styles = styles
        self.cell_image_sizes = cell_image_sizes or {}
        self.cell_image_re = cell_image_re or re.compile(r"!\[(?:[^\]]*)\]\(([^)]+)\)")
        self.label_font = label_font
        self.asset_dir = asset_dir
        self.Image = Image
        self.font_size = font_size
        self._flowables: dict[tuple[str, bool], list[Any]] = {}
        self._lines: dict[tuple[str, bool, float], int] = {}
        self._ladders: dict[tuple[str, bool, float, float], list[tuple[float, int]]] = {}
        self._synthetic = styles is None

    @staticmethod
    def content_width(column_width: float) -> float:
        """单元格内容可用宽（reportlab 的 colWidths 减去左右边距）。"""
        return max(column_width - 2 * _TABLE_CELL_PADDING, 1.0)

    def leading(self, is_header: bool) -> float:
        if self._synthetic:
            return 1.0
        style = self.styles["table"] if is_header else self.styles["table-body"]
        return float(style.leading)

    def _flowable_lines(self, flowables: list[Any], column_width: float, is_header: bool) -> int:
        width = self.content_width(column_width)
        total = 0
        for flowable in flowables:
            style = getattr(flowable, "style", None)
            leading = float(getattr(style, "leading", 0) or 0) or self.leading(is_header)
            try:
                _w, height = flowable.wrap(width, 10000)
            except Exception:
                return max(1, int(len(str(getattr(flowable, "text", "")) or "x")))
            total += max(1, int(round(float(height) / leading)))
        return max(1, total)

    def lines(self, text: str, column_width: float, is_header: bool) -> int:
        key = (text, is_header, round(float(column_width), 1))
        cached = self._lines.get(key)
        if cached is not None:
            return cached
        if self._synthetic:
            # 兜底（无渲染上下文）：字符宽模型估算，按宽度等比换算行数。
            natural = _cell_text_natural_width(re.sub(r"\$([^$\n]+)\$", lambda m: _latex_to_text(m.group(1)), text), self.font_size)
            usable = self.content_width(column_width)
            result = max(1, int(math.ceil(natural / usable - 1e-9)))
        else:
            if self.cell_image_re.search(text):
                # 表中图的缩放随列宽变化 → 每个宽度重建一次流式对象。
                flowables = _table_cell_flowables(
                    text, column_width, is_header, styles=self.styles,
                    cell_image_sizes=self.cell_image_sizes, cell_image_re=self.cell_image_re,
                    label_font=self.label_font, asset_dir=self.asset_dir, Image=self.Image,
                )
            else:
                flowables = self._flowables.get((text, is_header))
                if flowables is None:
                    flowables = _table_cell_flowables(
                        text, column_width, is_header, styles=self.styles,
                        cell_image_sizes=self.cell_image_sizes, cell_image_re=self.cell_image_re,
                        label_font=self.label_font, asset_dir=self.asset_dir, Image=self.Image,
                    )
                    self._flowables[(text, is_header)] = flowables
            result = self._flowable_lines(flowables, column_width, is_header)
        self._lines[key] = result
        return result


# 规则对应: GEN-110（表格列宽按折行代价分配）——折行测量器（真实渲染行数）+
# 每格折行阶梯 + 「按单位宽度收益买入」的分配；旧口径（自然宽需求 + 富余分配）
# 只在无渲染上下文时兜底。详见 _table_column_widths 的 docstring。
_CELL_LADDER_MAX_TIERS = 24   # 单元格折行阶梯的层数上限（行数极多的长文本兜底）
_CELL_LADDER_BITS = 10        # 断点二分位数上限（455pt 量级下 ≈0.4pt，复核回补）
# 测量器挂载在 styles 上的键：styles 每个文档建一次，测量器随之为文档级缓存
# （跨表复用行数/阶梯缓存；见 _table_measurer_for）。
_TABLE_MEASURER_KEY = "_table-measurer"


def _table_measurer_for(
    styles: dict[str, Any],
    *,
    cell_image_sizes: dict[str, list[float]],
    cell_image_re: re.Pattern[str],
    label_font: str = "",
    asset_dir: Path | None = None,
    Image: Any = None,
    font_size: float = 9.0,
) -> _TableCellMeasurer:
    """取本**文档**的列宽折行测量器（GEN-110）：styles 建一次 → 测量器也建一次。

    同一文档的多张表共用行数缓存与折行阶梯缓存（重复单元格如「五号正常体」「30」
    直接命中，实测 GB_3100-2026 的阶梯重建由 898 次降到 355 次）；表中图的版面
    尺寸是**每张表**的（``cellImageSizes``），故每次取用时刷新（图片单元格本来
    就按宽度重建流式对象，不走缓存）。
    """
    measurer = styles.get(_TABLE_MEASURER_KEY)
    if not isinstance(measurer, _TableCellMeasurer):
        measurer = _TableCellMeasurer(
            styles=styles, cell_image_sizes=cell_image_sizes, cell_image_re=cell_image_re,
            label_font=label_font, asset_dir=asset_dir, Image=Image, font_size=font_size,
        )
        styles[_TABLE_MEASURER_KEY] = measurer
    else:
        measurer.cell_image_sizes = cell_image_sizes or {}
        measurer.label_font = label_font or measurer.label_font
    return measurer


def _table_cell_ladder(measurer: _TableCellMeasurer, text: str, is_header: bool, lower: float, upper: float) -> list[tuple[float, int]]:
    """单元格折行阶梯 ``[(列宽, 行数)]``（列宽升序、行数递减）——GEN-110 的分配依据。

    ``宽度`` 是**该单元格可用的总列宽**（含左右边距，与 reportlab 的 ``colWidths``
    同口径）；含义是「总宽 ≥ 该值时，该单元格折成 ≤ 行数 行」。含 `<br>` 的固定
    断行是行数的下限（阶梯顶层即此下限，再宽也降不下去）。

    逐级二分出「降到 k 行所需的最小宽度」：从下界 ``lower`` 处的最大行数出发，
    向 1 行逐级求断点，二分区间随已求出的断点收缩（``[上一个断点, upper]`` →
    精度够用即可，位数按区间自适应），层数上限 ``_CELL_LADDER_MAX_TIERS``。
    阶梯只覆盖 ``[lower, upper]``，分配时按下界起步、逐段买入，故不会用到区间外。
    """
    k_max = measurer.lines(text, lower, is_header)
    if k_max <= 1:
        return [(lower, 1)]
    cache_key = (text, is_header, round(lower, 1), round(upper, 1))
    cached = measurer._ladders.get(cache_key)
    if cached is not None:
        return cached
    best_lines = measurer.lines(text, upper, is_header)
    if best_lines >= k_max:
        measurer._ladders[cache_key] = [(lower, k_max)]
        return measurer._ladders[cache_key]                 # 上限宽度也降不下行数 → 无层可买
    steps: list[tuple[float, int]] = []
    previous = lower
    for target in range(k_max - 1, best_lines - 1, -1):
        lo, hi = previous, upper
        if measurer.lines(text, lo, is_header) <= target:
            width = lo
        else:
            span = max(hi - lo, 0.05)
            bits = max(6, min(_CELL_LADDER_BITS, int(math.ceil(math.log2(span / 0.05)))))
            for _ in range(bits):
                mid = (lo + hi) / 2.0
                if measurer.lines(text, mid, is_header) <= target:
                    hi = mid
                else:
                    lo = mid
            # 二分停在「不再达标」的一侧 0.03pt 之内，取整可能落到达标侧的边界外
            # （实测 44.045 → 44.05 又变回 2 行）→ 复核并按 0.05pt 回补。
            width = round(hi, 2)
            for _ in range(8):
                if measurer.lines(text, width, is_header) <= target:
                    break
                width = round(width + 0.05, 2)
            if measurer.lines(text, width, is_header) > target:
                break                  # 回补失败（异常文本），保守停止
        if width <= previous + 1e-9:
            # 该宽度不会让行数再降（同宽度不可能有两种更优行数）：跳过本层继续
            # 找更宽的层（例如「规格代号」在 26.06pt 直接 4 行→2 行，无 3 行层）。
            continue
        steps.append((width, target))
        previous = width
        if len(steps) >= _CELL_LADDER_MAX_TIERS:
            break                      # 层数上限（行数极多的长文本兜底）
    entries = [(lower, k_max), *steps]
    entries.sort(key=lambda pair: pair[0])
    ladder: list[tuple[float, int]] = []
    for width, count in entries:
        # 阶梯按「降到 k 行所需的最小宽度」生成，同一宽度可能跨了多层（「规格代号」
        # 在 26.1pt 处 4 行直落 2 行）→ 一律取该宽度的**实测**行数，声明不虚高。
        count = min(count, measurer.lines(text, width, is_header))
        if ladder and width <= ladder[-1][0] + 1e-9:
            if count < ladder[-1][1]:
                ladder[-1] = (width, count)
            continue
        ladder.append((width, count))
    measurer._ladders[cache_key] = ladder
    return ladder


def _table_ladder_lines(ladder: list[tuple[float, int]], width: float) -> int:
    """阶梯查表：总宽 = width 时该单元格的行数。"""
    result = ladder[0][1]
    for entry_width, count in ladder:
        if entry_width <= width + 1e-9:
            result = count
        else:
            break
    return result


def _table_ladder_next(ladder: list[tuple[float, int]], width: float) -> tuple[float, int] | None:
    """阶梯上宽 > width 的第一个断点 → (宽度, 行数)；没有则 None。"""
    for entry_width, count in ladder:
        if entry_width > width + 1e-9:
            return (entry_width, count)
    return None


def _table_column_widths(
    rows: list[dict],
    col_count: int,
    font_size: float,
    cell_image_sizes: dict[str, list[float]],
    cell_image_re: re.Pattern[str],
    frame_width: float = _BODY_MEASURE,
    floor: float = 24.0,
    min_column: float | None = None,
    measurer: _TableCellMeasurer | None = None,
) -> list[float]:
    """按**折行代价**分配表格列宽（2026-09-17 起；GEN-110 执行侧）。

    用户 2026-09-17 给定的四条目标，按字典序落实：
      ① 整表总高度尽可能小；② 折行总次数尽可能少；③ 单元格内容尽量保持完整
        （尽量不折行）；④ 上述条件下尽量让空白与文字的观感平衡。
    旧口径（需求 = 表头自然宽 + 12pt 与数据 80% 分位取大，再「富余各列均分 /
    按数据需求比例分」）满足不了 ①—④：它按**自然宽估计**给列，既不看折行
    代价，也不看超长单元格的成本，实测 GB/T 30819 表4 把「表头长、数据短」的
    第 4/5 列撑到 130/94pt（源排版 84/69pt，数据只要 19pt），而表头并不因此
    不折行；GB/T 1.1 表F.1 则把第 2 列撑到 112pt（内容 84pt 就够）而第 4 列
    只有 117pt、折行 8 处。

    新算法（总宽恒 = 版心，列宽和恰等于 ``frame_width``）：
      1. **测量**：每个单元格用渲染端同一实现测出折行阶梯（``_table_cell_ladder``）
         ——「列宽 → 行数」的分段常数函数；
      2. **分配**：从每列下界起步，反复买入「单位宽度换到的收益」最大的那一段。
         收益按字典序比较——先看整表高度（各行行数的最大值之和，行高由该行最高的
         单元格决定），再看折行总行数，最后看折行的单元格个数；同一优先级下按
         「收益/宽度」比选列。步长为该列阶梯上的下一个断点（即真正能减少折行所需
         的最小加宽），不逐点试探；
      3. **平衡**（④）：买无可买（所有单元格都不再折行）或版心用尽后的余额，按
         各列**当时宽度**比例分配——即各列「空白/文字」的比值一致，窄列不会被
         塞进大块空白（旧口径的「富余均分」正是宽度反差大的原因之一）；
      4. **空列**保底 ``floor``（不参与买入与余额分配）、每列下界 ``min_column``
         （默认「左右边距 + 一个汉字宽」，GEN-103）在最后统一施加，Σ 仍恒 = 版心。

    单元格集合与渲染端一致：整行通栏（colspan = 全部列）的注行、以及渲染端会
    自动 SPAN 成通栏的「单长格行」都不挤占单列宽度（``lone_full`` 判据与
    ``_append_table`` 相同）；跨列（colspan < 列数）单元格按**组宽**参与测量，
    买它所在任一行列的宽度都会计入组宽。

    ``measurer`` 缺省时退化为需求模型的兜底（无渲染上下文的单表渲染/单测），
    正文渲染路径一律传入 ``_TableCellMeasurer``（``_append_table``）。
    """
    lower = float(min_column) if min_column is not None else 2 * _TABLE_CELL_PADDING + font_size
    if col_count <= 0:
        return []
    if measurer is None:
        # 无渲染上下文（单表渲染 / 单测）：字符宽模型兜底。正文渲染路径总是传入
        # _TableCellMeasurer（真实折行测量），见 docstring。
        measurer = _TableCellMeasurer(font_size=font_size)
    # 单元格集合（与渲染端同判据）：(行, 起列, 止列, 表头?, 文本)
    raw_cells: list[tuple[int, int, int, bool, str]] = []
    for row in rows:
        cells = sorted(row.get("cells", []), key=lambda cell: cell["colIndex"])
        plain = lambda cell: cell_image_re.sub("", str(cell.get("text", "")))
        filled = [cell for cell in cells if plain(cell).strip()]
        lone_full = len(cells) > 2 and len(filled) == 1 and len(plain(filled[0])) >= 20
        if lone_full:
            continue
        is_header = bool(row.get("isHeader"))
        for cell in cells:
            text = plain(cell).strip()
            span = int(cell.get("colspan", 1) or 1)
            if not text or span >= col_count:
                continue
            start = int(cell["colIndex"])
            raw_cells.append((int(row["rowIndex"]), start, min(start + span, col_count), is_header, text))
    content_cols = sorted({cell[1] for cell in raw_cells} | {cell[2] - 1 for cell in raw_cells})
    if not raw_cells:
        return [frame_width / col_count] * col_count
    # 下界之和已超版心（列数极多）：任何分配都排不下，等分后由调用点决定
    # 压缩边距 / 整表横排（GEN-103）。
    budget = frame_width - floor * (col_count - len(content_cols))
    if budget <= lower * len(content_cols):
        return [frame_width / col_count] * col_count
    widths = [floor if c not in content_cols else lower for c in range(col_count)]
    # 阶梯宽度上限按「该单元格最多能拿到的组宽」取：其余列各自至少保留下界 lower，
    # 更宽的目标在这个表格里根本买不起（探它只是浪费折行测量）。
    reachable = [max(lower, min(frame_width, budget - lower * (col_count - (end - start)))) for _row, start, end, _h, _t in raw_cells]
    ladders: list[list[tuple[float, int]]] = [
        _table_cell_ladder(measurer, text, is_header, lower, reachable[index])
        for index, (_row, _start, _end, is_header, text) in enumerate(raw_cells)
    ]
    row_cells: dict[int, list[int]] = {}
    column_cells: dict[int, list[int]] = {c: [] for c in range(col_count)}
    for index, (row, start, end, _is_header, _text) in enumerate(raw_cells):
        row_cells.setdefault(row, []).append(index)
        for c in range(start, end):
            column_cells[c].append(index)
    header_rows = {cell[0] for cell in raw_cells if cell[3]}
    body_lead = measurer.leading(False)
    head_lead = measurer.leading(True)
    row_lead = {row: (head_lead if row in header_rows else body_lead) for row in row_cells}

    def _row_counts(widths_now: list[float]) -> tuple[list[int], dict[int, int]]:
        """各单元格行数与各行行数最大值（行高 = 该行最高单元格的行数 × 行高）。"""
        counts = [
            _table_ladder_lines(ladders[index], sum(widths_now[start:end]))
            for index, (_row, start, end, _is_header, _text) in enumerate(raw_cells)
        ]
        row_max = {row: max(counts[index] for index in indexes) for row, indexes in row_cells.items()}
        return counts, row_max

    counts, row_max = _row_counts(widths)
    remaining = budget - sum(widths)
    guard = 0
    while remaining > 0.5 and guard < 10000:
        guard += 1
        best: tuple[tuple[float, float, float], int, float] | None = None
        for col in range(col_count):
            candidates = column_cells[col]
            if not candidates:
                continue
            # 同一列内按「需要增加的组宽」去重：一次买入即可跨越该列上所有符合条件的
            # 断点，逐个单元格重复评估同一目标纯属浪费（表2/表4 的重复数字格尤甚）。
            increases: set[float] = set()
            for index in candidates:
                _row, start, end, _is_header, _text = raw_cells[index]
                group = sum(widths[start:end])
                step = _table_ladder_next(ladders[index], group)
                if step is None:
                    continue
                cost = step[0] - group
                if cost > 1e-9 and cost <= remaining + 1e-9:
                    increases.add(round(cost, 3))
            # 该列可省下的折行总行数（= 高度收益的上界）→ 用于剪掉无望的远目标。
            column_extra = sum(counts[index] - 1 for index in candidates)
            bound = column_extra * row_lead.get(raw_cells[candidates[0]][0], body_lead)
            for cost in sorted(increases):
                if best is not None and cost > 1e-9 and bound / cost < best[0][0]:
                    break                      # 更远的目标代价更高、上界不变 → 都不划算
                trial_counts = {}
                for index in candidates:
                    _row, start, end, _is_header, _text = raw_cells[index]
                    trial_counts[index] = _table_ladder_lines(ladders[index], sum(widths[start:end]) + cost)
                d_height = 0.0
                for row, indexes in row_cells.items():
                    if not any(index in trial_counts for index in indexes):
                        continue
                    before = row_max[row]
                    after = max(trial_counts.get(index, counts[index]) for index in indexes)
                    if after != before:
                        d_height += (before - after) * row_lead[row]
                d_extra = sum(counts[index] - new for index, new in trial_counts.items())
                d_wrapped = sum((counts[index] > 1) - (new > 1) for index, new in trial_counts.items())
                if d_height <= 1e-9 and d_extra <= 0 and d_wrapped <= 0:
                    continue
                score = (d_height / cost, d_extra / cost, d_wrapped / cost)
                if best is None or score > best[0]:
                    best = (score, col, cost)
        if best is None:
            break
        _score, col, cost = best
        target = widths[col] + cost
        # 应用买入：更新受影响单元格的行数、各行最大值与剩余额度
        affected = set(column_cells[col])
        for index in affected:
            _row, start, end, _is_header, _text = raw_cells[index]
            counts[index] = _table_ladder_lines(ladders[index], sum(widths[start:end]) + cost)
        widths[col] = target
        for row, indexes in row_cells.items():
            if not affected.isdisjoint(indexes):
                row_max[row] = max(counts[index] for index in indexes)
        remaining = budget - sum(widths)
    if remaining > 0.5:
        # ④ 视觉平衡：余额按各列当时宽度比例分配 → 空白/文字比值各列一致。
        weights = [widths[c] if c in content_cols else 0.0 for c in range(col_count)]
        total_weight = sum(weights)
        if total_weight > 0:
            for col in range(col_count):
                widths[col] += remaining * weights[col] / total_weight
    # 每列下界（2026-09-12，GEN-103）：见 docstring。
    if lower > 0 and col_count:
        if lower * col_count >= frame_width:
            widths = [frame_width / col_count] * col_count
        else:
            deficit = sum(lower - w for w in widths if w < lower)
            if deficit > 1e-9:
                widths = [max(w, lower) for w in widths]
                for i in sorted(range(col_count), key=lambda i: widths[i], reverse=True):
                    if deficit <= 1e-9:
                        break
                    give = min(widths[i] - lower, deficit)
                    widths[i] -= give
                    deficit -= give
    # 舍入残差并入最宽列，保证 Σ == frame_width
    widths[max(range(col_count), key=lambda i: widths[i])] += frame_width - sum(widths)
    return widths


def _table_rotated_measure(content_width: float) -> float | None:
    """宽表横排可用宽（GEN-103）：整表旋转 90° 后沿页面高度排布。

    仅在正文通栏容器内横排——示例线框内横排会穿出框线；未进入文档上下文
    （``_ROTATED_TABLE_MEASURE`` 为 None）时不横排。
    """
    rotated = _ROTATED_TABLE_MEASURE
    if rotated is None or content_width < _BODY_MEASURE - 1.0 or rotated <= content_width + 1.0:
        return None
    return float(rotated)


def _table_exceeds_frame(grid: Any, avail_width: float, frame_height: float, *, max_splits: int = 64) -> bool:
    """竖排网格在版心内能否**分页**排下：按 reportlab 的**递归**分页语义复算。

    跨行合并（rowspan）锁定的行组不可再分，组高超过一页时 reportlab 抛
    LayoutError；与其另立行高模型，不如直接问它（GEN-103 判据 ③）。

    reportlab 的一次 ``split()`` 只切出「本页装得下的第一片 + 其余」，**其余那一片
    可以高于一页**——它会被再切一次。只看一级片段会把「长表正常分页」误判成
    「竖排必然排不下」（GB/T 30819-2024 表2 9 列 ×54 行：一级片段 669pt + 741pt，
    再切一次即 669/627/150pt 三片全在版心内），于是整表被旋转 90°——旋转后沿页宽
    方向的尺寸 = 表高 624 + 题注 14 = 638pt > 版心宽 441.5pt，reportlab 抛
    ``Splitting error(n==2)``，04_render 为空、构建退出码 2，与源排版（该表竖排跨页、
    表头重复）也不符。因此判据改为「切到不动点仍有一片高于一页」才算排不下。

    返回 True = 竖排**确实**无法分页（可横排）；异常与切不动的片段一律按「无法
    分页」处理（保持原判据的保守取向：宁可不横排）。
    """
    pending: list[Any] = [grid]
    splits = 0
    while pending:
        piece = pending.pop()
        try:
            # reportlab 的 Table.wrap 返回 (宽, 高) 而不写 .height 属性，故取返回值。
            _width, height = piece.wrap(avail_width, frame_height)
        except Exception:
            return False
        if float(height) <= frame_height + 0.5:
            continue
        if splits >= max_splits:
            return True
        splits += 1
        try:
            sub = piece.split(avail_width, frame_height)
        except Exception:
            return False
        if len(sub or []) < 2:
            return True
        pending.extend(sub)
    return False


def _table_landscape_widths(
    rows: list[dict],
    col_count: int,
    font_size: float,
    cell_image_sizes: dict[str, list[float]],
    cell_image_re: re.Pattern[str],
    content_width: float,
    grid: Any,
    measurer: "_TableCellMeasurer | None" = None,
    portrait_widths: list[float] | None = None,
) -> list[float] | None:
    """宽表横排判定（GEN-103）：需要横排时返回横排列宽，否则返回 None。

    横排（整表旋转 90°、表头落订口一侧，与 GB/T 5171.1-2014 表9 源排版同向）需三条
    同时成立：
      ① 本容器内整表按需排不下（Σ列需求 > 容器宽）——列只能被压到折行；
      ② 横排可用宽（页面版心高）能整表按需排下（Σ列需求 ≤ 横排可用宽）；
      ③ 竖排**不可用**：二选一——
         a) 竖排列宽分配后仍有**半数以上（且 ≥3）的列被压到下界**（= 左右边距 + 一个
            汉字宽 → 每行只排得下一个字，读不成表；26 列的 表9 即此类）；或
         b) 竖排网格在本版心内**无法分页**（跨行合并锁定行组高于一页）→ 竖排必然
            LayoutError（``_table_exceeds_frame``）。
    ② 保证横排确有收益，③ 保证普通「要折行但能分页、列还排得下字」的长表不受影响
    （GB/T 30819-2024 表2/表4：9/11 列、最小列 31pt 以上 → 竖排跨页、表头重复，与源
    排版一致，不横排）。
    """
    measure = _table_rotated_measure(content_width)
    if measure is None:
        return None
    need, _header_min, _body_need, _content = _table_column_demands(
        rows, col_count, font_size, cell_image_sizes, cell_image_re
    )
    total_need = sum(need)
    if total_need <= content_width or total_need > measure:
        return None
    lower = 2 * _TABLE_CELL_PADDING + font_size
    squeezed = False
    if portrait_widths:
        at_lower = sum(1 for width in portrait_widths if width <= lower + 0.01)
        squeezed = at_lower >= max(3, math.ceil(len(portrait_widths) / 2))
    if not squeezed and not _table_exceeds_frame(grid, content_width, measure):
        return None
    return _table_column_widths(
        rows, col_count, font_size, cell_image_sizes, cell_image_re, frame_width=measure, measurer=measurer
    )


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


# 简单分数 \frac{a}{b} 的 Unicode 分数字形：渲染字体（思源宋体 NotoSerifCJKsc）只带
# ½ ¼ ¾（Latin-1 Supplement），Number Forms 区（⅓ ⅔ …）在该字体里没有字形、
# 映射过去会印成空框，故只映射这三个；其余（字母、多位、无字形）仍拍平为 (a)/(b)。
_FRACTION_GLYPHS = {("1", "4"): "¼", ("1", "2"): "½", ("3", "4"): "¾"}


def _flatten_fraction(numerator: str, denominator: str) -> str:
    """``\frac{a}{b}`` 的可读文本：有分数字形用 ½ 形式，否则 (a)/(b)。

    规则对应: GBT-X06（无法排版时以可读文本呈现）+ 标准表格/正文里的叠排简单分数
    （GB/T 10401-2023 表10「½连续堵转转矩」型）。
    """
    num = numerator.strip()
    den = denominator.strip()
    glyph = _FRACTION_GLYPHS.get((num, den))
    return glyph if glyph else f"({num})/({den})"


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
                out.append(_flatten_fraction(_latex_expand_nested(num_inner), _latex_expand_nested(den_inner)))
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

    规则对应: GBT-X06（数学公式另行居中编排；无法排版时以可读文本呈现）、
    GBT-B12/GEN-116（量符号斜体、上划线——行内通道由 `_inline_math_markup` 在拍平当步补齐；
    本函数只做「可读文本」这一层，保持与 docx 侧共用的纯文本语义）。
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
    # 2b) 不带花括号的单字符下标：`T_P`、`P_N`（MinerU 在表格单元格里常这样写）。
    #     旧码只认 `_{…}`，`_P` 的 `_` 会被当成普通字符保留下来（拍出 "T_P"），
    #     下标语义丢失且字母连成一段（GEN-116 变量斜体把整段当量符号）。
    text = re.sub(
        r"\s*_\s*([A-Za-z0-9])",
        lambda m: "\x00SUB\x00" + m.group(1) + "\x00/SUB\x00",
        text,
    )
    text = re.sub(
        r"\s*\^\s*\{([^{}]*)\}",
        lambda m: "\x00SUP\x00" + _latex_sup_content(m.group(1)) + "\x00/SUP\x00",
        text,
    )
    text = re.sub(r"\s*_\s*([A-Za-z0-9])", r"\1", text)
    text = re.sub(r"\s*\^\s*([A-Za-z0-9])", lambda m: "\x00SUP\x00" + _latex_sup_content(m.group(1)) + "\x00/SUP\x00", text)
    # 3) \frac{a}{b} -> ½（有字形时）或 (a)/(b)。
    text = re.sub(
        r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}",
        lambda m: _flatten_fraction(m.group(1), m.group(2)),
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
        # 希腊字母命令 → Unicode 字母（GEN-116）：`\eta` 这类不是「运算符」而是**量符号**，
        # 旧实现在收尾的「丢弃剩余 \command」步骤里把它们整条删掉（`\overline{\eta}` 拍平
        # 成空串）。语料实测：`\overline { { \eta } }`、`\mathrm{n}`、`\alpha` 等。
        (r"\alpha", "α"),
        (r"\beta", "β"),
        (r"\gamma", "γ"),
        (r"\delta", "δ"),
        (r"\epsilon", "ε"),
        (r"\varepsilon", "ε"),
        (r"\zeta", "ζ"),
        (r"\eta", "η"),
        (r"\theta", "θ"),
        (r"\vartheta", "θ"),
        (r"\iota", "ι"),
        (r"\kappa", "κ"),
        (r"\lambda", "λ"),
        (r"\nu", "ν"),
        (r"\xi", "ξ"),
        (r"\rho", "ρ"),
        (r"\sigma", "σ"),
        (r"\tau", "τ"),
        (r"\upsilon", "υ"),
        (r"\phi", "φ"),
        (r"\varphi", "φ"),
        (r"\chi", "χ"),
        (r"\psi", "ψ"),
        (r"\omega", "ω"),
        (r"\Gamma", "Γ"),
        (r"\Theta", "Θ"),
        (r"\Lambda", "Λ"),
        (r"\Xi", "Ξ"),
        (r"\Pi", "Π"),
        (r"\Sigma", "Σ"),
        (r"\Upsilon", "Υ"),
        (r"\Phi", "Φ"),
        (r"\Psi", "Ψ"),
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
    text = re.sub(r"(?<=[\u0370-\u03ff]) (?=[A-Za-z])", "", text)
    # 7) MinerU 逐字符空格数字（"6 . 6 2 6 0 7 0 1 5"）收紧为规范数值
    #    （"6.62607015"；2026-09-02，GB_3100-2026 4.2 常量行）。
    text = re.sub(r"\s+([.,])\s*", r"\1", text)
    text = re.sub(r"(?<=\d) (?=\d)", "", text)
    return re.sub(r"\s+", " ", text).strip()


# 渲染端星号/强调语法（docs/07 §6.1：`**粗体**`、`*斜体*`、`***粗斜体***`；
# 反斜杠转义 `\*` 表示字面星号）——**成对**才当强调，未成对的星号簇一律按字面
# 星号输出（`即 * 、 ** 、 ***`、`共*页`、`共\*页` 等负例）。
#
# 2026-09-16 用户报「GB_T_20001.10-2014 表1 用 * 号定义的斜体/粗体/粗斜体都没有
# 起作用」：旧实现只按**邻接字符**判断字面星号——`(?<![A-Za-z0-9])\*+(?![A-Za-z0-9])`
# ——而汉字不在 `[A-Za-z0-9]` 里，于是 `***封面***`、`*目次*`、`**范围**` 的星号簇
# 全被判为字面星号，强调标记成对出现却从未配对；且旧实现只有 `**`/`*` 两条正则
# （无 `***` 粗斜体形式，`**\*(.+?)\*\*` 会把 `***X***` 拆成 `<b>*X</b>*`）。
# 现在按**定界符簇配对**判定：可开 = 其后首个非空白字符存在且不是 `*`，可闭 =
# 其前首个非空白字符存在且不是 `*`；同长度簇就近配对（1=斜体、2=粗体、3=粗斜体，
# 4 个以上不成形式 → 字面）。配对判定忽略紧邻空白（OCR 常在闭标记前留空格，如
# `*注、脚注 *`），配对后**去掉强调区两端空白**；未配对簇还原为等长字面星号。
_STAR_RUN_RE = re.compile(r"\*+")
# 强调区哨兵（escape 之后换成 reportlab 的 <b>/<i>；NUL 哨兵不被 escape 改动）。
_EMPHASIS_OPEN = {"b": "\x00EMB\x00", "i": "\x00EMI\x00"}
_EMPHASIS_CLOSE = {"b": "\x00/EMB\x00", "i": "\x00/EMI\x00"}
_EMPHASIS_TAGS = {1: ("i",), 2: ("b",), 3: ("b", "i")}
_SPACE_CHARS = " \t\u3000\u00a0"


def _emphasis_tags(run_length: int) -> tuple[str, ...]:
    """星号簇长度 → 强调种类（1=斜体、2=粗体、3=粗斜体；其余不成形式）。"""
    return _EMPHASIS_TAGS.get(run_length, ())


def _next_nonspace(text: str, index: int) -> int | None:
    for position in range(index, len(text)):
        if text[position] not in _SPACE_CHARS:
            return position
    return None


def _prev_nonspace(text: str, index: int) -> int | None:
    for position in range(index - 1, -1, -1):
        if text[position] not in _SPACE_CHARS:
            return position
    return None


def _resolve_emphasis(text: str) -> str:
    """把成对强调标记换成哨兵、未成对星号簇换成字面星号哨兵。"""
    text = text.replace("\\*", "\x00AST1\x00")
    runs = [(match.start(), match.end(), len(match.group())) for match in _STAR_RUN_RE.finditer(text)]
    if not runs:
        return text
    pending: dict[int, list[int]] = {1: [], 2: [], 3: []}
    opener_of: dict[int, int] = {}
    closer_of: dict[int, int] = {}
    for index, (start, end, length) in enumerate(runs):
        tags = _emphasis_tags(length)
        if not tags:
            continue
        after = _next_nonspace(text, end)
        before = _prev_nonspace(text, start)
        can_open = after is not None and text[after] != "*"
        can_close = before is not None and text[before] != "*"
        if can_close and pending[length]:
            opener_of[pending[length].pop()] = index
            closer_of[index] = index
        elif can_open:
            pending[length].append(index)
    if not opener_of and not closer_of:
        return text
    out: list[str] = []
    cursor = 0
    strip_leading = False
    for index, (start, end, length) in enumerate(runs):
        chunk = text[cursor:start]
        if strip_leading:
            chunk = chunk.lstrip(_SPACE_CHARS)
            strip_leading = False
        if index in opener_of:
            out.append(chunk)
            out.extend(_EMPHASIS_OPEN[tag] for tag in _emphasis_tags(length))
            strip_leading = True
        elif index in closer_of:
            # 强调区右端的 OCR 空格不进强调区（`*注、脚注 *`）。
            if chunk.strip():
                chunk = chunk.rstrip(_SPACE_CHARS)
            elif out:
                out[-1] = out[-1].rstrip(_SPACE_CHARS)
            out.append(chunk)
            out.extend(_EMPHASIS_CLOSE[tag] for tag in reversed(_emphasis_tags(length)))
        else:
            out.append(chunk)
            out.append(f"\x00AST{length}\x00")
        cursor = end
    out.append(text[cursor:])
    return "".join(out)


# 字面星号簇保护（GBT-C13 星号脚注、GB_T_1.1-2020 9.12.1 "*、**、***"、
# 9.7.3 “共*页”）：CommonMark 转义 \*（parser 不反转义、textContent 保留
# 反斜杠）与两侧都不是拉丁字母/数字的星号簇都是字面星号（而非 markdown
# 强调）。先保护为 \x00AST{n}\x00 哨兵，等 bold/italic 处理完再按簇长还原，
# 否则 “即\*、\*\*、\*\*\*” 会被 italic/bold 正则错配吞字。markdown 强调
# （*word*、**word**）两侧至少一侧是词字符，不受影响。
_LIT_STAR_RE = re.compile(r"(?<![A-Za-z0-9])\*+(?![A-Za-z0-9])")


def _protect_literal_stars(text: str) -> str:
    r"""把字面星号（转义 \* 与两侧非词字符簇）编码为 AST 哨兵。

    仅 docx 渲染端（`docx_renderer._add_markup`）仍走本判据；PDF 侧已改用
    `_resolve_emphasis` 的**定界符簇配对**判据（汉字内容的强调不再被误判为字面
    星号），见其上方注释。docx 侧同步改造按文档暂停指令记为未做项。
    """
    text = text.replace("\\*", "\x00AST1\x00")
    return _LIT_STAR_RE.sub(lambda m: f"\x00AST{len(m.group())}\x00", text)


def _restore_literal_stars(text: str) -> str:
    """把 AST 哨兵还原为对应长度的字面星号串。"""
    return re.sub(r"\x00AST(\d+)\x00", lambda m: "*" * int(m.group(1)), text)


# 数值-单位固定字隙（GBT-B12）：哨兵在 escape 之后还原为按 1/4 字号绘制的白色
# 「中」，推进宽度恒为该字号的四分之一汉字；由 _markup(text, em_size) 的 em_size
# 或模块级 _MARKUP_EM_SIZE（正文号，_styles 依 profile 设置）决定。测试等独立调用
# 场景用 GB/T 1.1 附录F 正文五号 10.5pt 作默认值。
_MARKUP_EM_SIZE: float = 10.5
# 注/示例标记字体（GB/T 1.1-2020 10.4.4.1/10.4.5、附录F 表F.1 序号42/44「小五号
# 黑体」）：由渲染 profile 的 ``fonts.label`` 指定（render_pdf 里设置），标记要与
# 宋体正文一眼可分；未配置（空串）时各调用点退回传入的字体。与 _MARKUP_EM_SIZE
# 同属「profile 决定的渲染期全局」。
_LABEL_FONT: str = ""
_QEM_SENTINEL = "\x00QEM\x00"
# 任意宽度固定字隙哨兵（pt）：列项 marker 与文字之间按版式位置差排版（GBT-B04），
# 见 _fixed_gap()。占位字形宽 1em，故字号点数即字隙宽度。
_WSP_PATTERN = re.compile(r"\x00WSP([0-9.]+)\x00")


def _fixed_gap(width: float) -> str:
    """固定字隙哨兵：宽度（pt）严格等于 width，不随两端对齐变化。

    GB/T 1.1 版式里列项文字起点由版心汉字位决定（10.2.2/GBT-B04），是**固定位置**，
    不能交给可被两端对齐拉伸的空格字符（旧实现用普通空格，一行里出现 U+00A0 等
    reportlab 计作空格的字符时，整行空格会被字间距 Tw 拉开）。
    """
    if width <= 0.05:
        return ""
    return f"\x00WSP{width:.3f}\x00"


def _list_is_sub_level(marker: str, uniform_bullets: bool) -> bool:
    """列项层次归属（GB/T 1.1-2020 10.2.2；pdf/docx 两侧共用判定）。

    第二层次 = 数字编号（1)、2)）与间隔号（·）；圆点（●○•）在整组清一色圆点时
    属第一层次（纯圆点列项），与 a)/1)/—— 等标记混排时属第二层次。
    """
    if marker in ("●", "○", "•"):
        return not uniform_bullets
    return marker in ("·",) or bool(marker.rstrip(")）").isdigit())


def _list_marker_gap(style: Any, marker: str, marker_size: float) -> str:
    """列项 marker 与文字之间的固定字隙哨兵（GB/T 1.1-2020 10.2.2 / GBT-B04）。

    标准规定列项文字与回行同置版心左边「第五/第七个汉字位」，即文字起点 = 段落
    ``style.leftIndent``；marker 则从 ``leftIndent + firstLineIndent`` 起排，故
    marker 之后要补的固定字隙 = ``-firstLineIndent - marker 推进宽``。

    不能用 ``leftIndent + firstLineIndent`` 当「目标位」：那只在
    ``firstLineIndent == -leftIndent/2``（第一层次 4/2 汉字）时凑巧落到文字列，
    第二层次（6/2 汉字）会把文字推到第八个汉字位，且白字占位符的字号即字隙宽，
    26pt 的占位字又把行框撑高、与相邻行框重叠（2026-09-11 用户报：a) 下 1)/2)
    列项间距过大、行框互相重叠）。

    固定字隙不能用空格：空格会被两端对齐按字间距 Tw 拉伸——同一分组里只要有一个
    reportlab 计作空格的字符（旧实现的数值-单位 U+00A0 即其一），整行所有空格一起
    变宽，GB_T_5171.1-2014 4.1.1 的 a)/b) 因此出现同为空格的 marker 后空隙一窄一宽
    的差异。marker 宽于目标位时不后推文字（返回空串）。
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth

    return _fixed_gap(-style.firstLineIndent - stringWidth(marker, style.fontName, marker_size))


def _markup(text: str, em_size: float | None = None) -> str:
    text = str(text)
    # 公式变量解释项（「式中：」下方逐项，GB/T 1.1-2020 9.9.3/10.4.3；CSM-OCR-018）：
    # 变量与破折号之间、破折号与解释之间各空四分之一汉字。字隙用**固定字隙哨兵**
    # （同 GBT-B12 数值-单位间隙），不用空格——两端对齐会把空格字节一起拉伸。
    # 形态必须在行内 LaTeX 拍平**之前**判定：变量头 = 行内 $...$，或 1—4 个
    # 半角/希腊字母（可带下标），其后是「——」。
    text = re.sub(
        r"(?m)^(\$[^$\n]+\$|[\u0370-\u03ffA-Za-z][\u0370-\u03ffA-Za-z0-9]{0,3}"
        r"(?:[ \u3000]*[_^][ \u3000]*\{[^{}\n]{1,12}\})?)[ \u3000]*(—+)(?=[\u4e00-\u9fff])",
        lambda m: m.group(1) + _QEM_SENTINEL + m.group(2) + _QEM_SENTINEL,
        text,
    )
    # Inline MinerU math ("$...$") is LaTeX; flatten it to readable text so
    # command noise ("\\mathrm{~T~}") does not leak into the rendered PDF.
    # 同时保住「变量斜体 + 上划线」两条版式约定（GEN-116）：_inline_math_markup 在拍平
    # 当步完成斜体化（含直立内容遮罩），后续文本规则看到的仍是原样文本。
    text = re.sub(r"\$([^$\n]+)\$", lambda m: _inline_math_markup(m.group(1)), text)
    # OCR whitespace noise: collapse space runs ("、   32.4 V") and join
    # digit-group separators ("2 000 W" -> "2000 W").
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"(?<=\d) (?=\d)", "", text)
    # 强调标记配对（docs/07 §6.1：`**粗体**`/`*斜体*`/`***粗斜体***`；未成对的星号簇
    # 与转义 `\*` 走字面星号哨兵）——先编码为哨兵，escape 之后再换成 <b>/<i>。
    text = _resolve_emphasis(text)
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
    # GBT-B12）。用**固定宽度的字隙**实现：白色「中」按 1/4 字号绘制，推进宽度恒为
    # 该字号的四分之一汉字。不用 U+00A0：两端对齐时 reportlab 把不换行空格按空格
    # 字节计入 PDF 字间距 Tw 一并拉伸（实测 1.0–1.6 个汉字宽，同一文档内数值-单位
    # 间隙因此忽宽忽窄），而白字不是空格字节，两端对齐不会拉动它。原本想用 1/4 em
    # 的空白字符，但 Noto Serif CJK SC 没有 U+2009/U+202F 等窄空格字形（会渲染成
    # .notdef 方框），故沿用本文件既有的白字哨兵技术（同 CSM-OCR-003 术语间隔、
    # GAP 条号间隔）。
    # - 源文/OCR 已有空格（"50 Hz"）→ 换固定字隙；
    # - 紧贴（"210mm"、"0.2℃"、"85K"、"15N"）→ 补固定字隙，消除同一文档
    #   间隙不一致（GB 3100 数值与单位间留一个空格）；
    # - 例外：% 前不留间隙（GB/T 15835-2011 示例 "34.05%"、"63%~68%"），已有
    #   空格也收紧；平面角度分秒 °′″ 紧跟数值（GBT-B12 例外，字符不在集合内）；
    #   分表/分图代号（"表2a"，GB/T 1.1 9.8.1.3 示例）不插间隙。
    # 数值与单位之间：已有的空格、或紧贴处补入，统一成同一种固定字隙。
    # 例外（都不是「量值 + 单位」）：紧跟表/图编号的字母是标识符的一部分（分表代号
    # "表2a"、"图2b"）或题注里的公式变量（表题 "表A.1 C_p 等级评定及处理原则"）；上下标
    # 段内是记号/变量（"D_{1max}"），单位符号不会出现在上下标里。判据放在回调里
    # （Python re 不支持变长后顾）。
    def _identifier_letter(haystack: str, match: re.Match[str]) -> bool:
        prefix = haystack[: match.start()]
        if re.search(r"[图表]\s*[A-Z]?\.?\d+(?:\.\d+)*$", prefix):
            return True
        for open_mark, close_mark in (("<sub>", "</sub>"), ("<sup>", "</sup>"),
                                      ("\x00SUB\x00", "\x00/SUB\x00"), ("\x00SUP\x00", "\x00/SUP\x00")):
            if prefix.rfind(open_mark) > prefix.rfind(close_mark):
                return True
        return False

    text = re.sub(
        r"(?<=\d) (?=[A-Za-z℃Ωμµ])",
        lambda m: m.group(0) if _identifier_letter(text, m) else _QEM_SENTINEL,
        text,
    )
    text = re.sub(r"(?<=\d) (?=%)", "", text)
    text = re.sub(
        r"(?<=\d)(?=[A-Za-z℃Ωμµ])",
        lambda m: m.group(0) if _identifier_letter(text, m) else _QEM_SENTINEL,
        text,
    )
    # 幂次数量值（"10³ m"、"2.5×10³ m"、"10³m"）：量值以 <sup>/<sub> 收尾时，数值与单位
    # 之间同样归一为固定字隙。MinerU 的标签（<sup>/<sub>）与 _latex_to_text 的哨兵
    # （\x00SUP\x00/\x00SUB\x00）两种形态各处理一次；后顾必须定长，故分开两条。
    for tag_close in (r"(?<=</sup>|</sub>)", r"(?<=\x00/SUP\x00|\x00/SUB\x00)"):
        text = re.sub(
            tag_close + r"[ \u3000](?=[A-Za-z℃Ωμµ])",
            lambda m: m.group(0) if _identifier_letter(text, m) else _QEM_SENTINEL,
            text,
        )
        text = re.sub(
            tag_close + r"(?=[A-Za-z℃Ωμµ])",
            lambda m: m.group(0) if _identifier_letter(text, m) else _QEM_SENTINEL,
            text,
        )
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
    # 数值-单位字隙（GBT-B12）：按当前字号 1/4 绘制白色「中」，推进宽度恰为四分之一
    # 汉字；白字非空格字节，两端对齐不会把它拉宽（见上方 Number-unit gap 注释）。
    quarter = (em_size or _MARKUP_EM_SIZE) / 4
    escaped = escaped.replace(_QEM_SENTINEL, f'<font size="{quarter:g}" color="white">中</font>')
    # 列项 marker 与文字之间的固定字隙（GBT-B04）：宽度即哨兵里的点数，同为白字，
    # 两端对齐不拉伸。
    escaped = _WSP_PATTERN.sub(lambda m: f'<font size="{m.group(1)}" color="white">中</font>', escaped)
    # 正文宋体缺 ⁰⁵⁶⁷⁸⁹⁻⁺ 字形（Noto Serif CJK SC 实测无 glyph，2026-09-02；
    # ¹²³⁴ 有），Unicode 上标若直接渲染会成 .notdef 方框（PDF 文本层表现为
    # \x00）——转成 reportlab <super> 真上标（相邻上标合并为一个 run）。
    for sup_char, plain_char in (("⁰", "0"), ("⁵", "5"), ("⁶", "6"), ("⁷", "7"), ("⁸", "8"), ("⁹", "9"), ("⁻", "−"), ("⁺", "+"), ("ⁱ", "i")):
        escaped = escaped.replace(sup_char, f"<super>{plain_char}</super>")
    escaped = re.sub(r"</super><super>", "", escaped)
    # 强调标记（docs/07 §6.1）：配对判定在 `_resolve_emphasis` 完成（已排除转义
    # `\*` 与未成对星号簇），此处只把哨兵换成真标签——1=斜体、2=粗体、3=粗斜体
    # （`***X***` → `<b><i>X</i></b>`，嵌套由配对顺序保证）。
    escaped = escaped.replace("\x00EMB\x00", "<b>").replace("\x00/EMB\x00", "</b>")
    escaped = escaped.replace("\x00EMI\x00", "<i>").replace("\x00/EMI\x00", "</i>")
    return _restore_literal_stars(escaped)


_VERBATIM_SPACE_RUN_RE = re.compile(r"[ \t]{2,}")


def _verbatim_gap_pt(run: str, font_size: float) -> float:
    """原样块的空白宽度（pt）：半角空格 0.25em、制表符 4 个半角空格（GEN-107）。"""
    return 0.25 * float(font_size) * len(str(run).replace("\t", "    "))


def _verbatim_markup(text: str, font_size: float) -> str:
    """原样块（docs/07 §6.10）逐字渲染：保留换行与行首/行内缩进（GEN-107）。

    `_markup` 的常规通道会把段内换行连同其两侧空白归一为一个空格（CSM §3.3 的软
    换行规则——MinerU 逐行折行的段落必须如此，语料有 31 个这样的多行段落），但原样
    块的语义恰恰是「逐字保留原始文本」，因此这里：

    - 换行 → ``\\x00BR\\x00`` 硬换行哨兵（调用方在 `_markup` 之后还原为 ``<br/>``）；
    - 行首空白（任意长度）与行内 **≥2 个连续空白** → 固定字隙（白字哨兵，两端对齐
      不拉伸）：每个半角空格计 **0.25em**（正文字体 U+0020 实测 0.256em）、制表符计
      4 个半角空格 → 于是 **4 个半角空格 = 1 个全角位**；框线字（│ ├ └ ─，U+2500 区）
      在 CJK 字体中恰为 1em，因此树状结构按「每级 4 个半角空格」书写即可与框线对齐
      （也可直接写全角空格 U+3000 = 1em）。行内**单个**空格保持原样（reportlab 仍可
      在此折行，长句不会溢出）；
    - 其余文本交给 `_markup`（转义、角标、行内公式等既有机制不变）。
    """
    lines = str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    rendered: list[str] = []
    for line in lines:
        leading = re.match(r"[ \t]+", line)
        if leading:
            line = _fixed_gap(_verbatim_gap_pt(leading.group(0), font_size)) + line[leading.end():]
        line = _VERBATIM_SPACE_RUN_RE.sub(
            lambda m: _fixed_gap(_verbatim_gap_pt(m.group(0), font_size)), line
        )
        rendered.append(line)
    return "\x00BR\x00".join(rendered)


# 注/示例标记黑体哨兵（_label_markup）：与 <super>/<sub>/GAP 同机制——先写入
# 哨兵（escape 不改动 NUL），escape 之后再换成 reportlab 的 <font name> 标签。
_LABEL_OPEN, _LABEL_CLOSE = "\x00HEI\x00", "\x00/HEI\x00"


def _mark_note_example_labels(text: str) -> str:
    """文本每个行首（串首，或 <br>/BR 哨兵之后的数据行首）的注/示例标记加哨兵。

    canonical 单元格把多行内容写成 <br> 分隔（"段…<br>注1：…"）：行首因此不等于
    串首——只认串首会漏掉 <br> 之后的注标记（GB_T_1.1-2020 表 F.1 单元格实测）。
    """
    parts = re.split(r"(\x00BR\x00|<br>)", str(text))
    marked: list[str] = []
    for index, part in enumerate(parts):
        if index % 2:  # 分隔符本身（捕获组）
            marked.append(part)
            continue
        lead, label, rest = _note_example_label_span(part)
        marked.append(f"{lead}{_LABEL_OPEN}{label}{_LABEL_CLOSE}{rest}" if label else part)
    return "".join(marked)


def _label_markup(text: str, label_font: str, em_size: float | None = None) -> str:
    """注/示例标记用黑体、其余照旧（GB/T 1.1-2020 10.4.4.1、10.4.5、附录 F 表 F.1
    序号 42/44；GBT-B10/GBT-B11 执行侧）。

    标记与内容是同一段落里的两段字面：只用黑体字形包住行首标记（"注："/"注1："/"
    示例："/"示例1："）。字体标签必须在 ``_markup`` 转义**之后**注入（先注入会被
    escape 成字面文本），故走 ``_mark_note_example_labels`` 的哨兵通道。

    实际字体 = profile 的 ``fonts.label``（黑体粗，见 ``_LABEL_FONT``）；未配置时
    退回调用点传入的字体。标记要与宋体正文一眼可分，细黑达不到该效果（见 profile
    注释与 docs/12 §3.33）。
    """
    font = _LABEL_FONT or label_font
    if not font:
        return _markup(text, em_size=em_size)
    marked = _markup(_mark_note_example_labels(text), em_size=em_size)
    return marked.replace(_LABEL_OPEN, f'<font name="{font}">').replace(_LABEL_CLOSE, "</font>")


# 生成公式图（MathText）的光栅参数与显示换算（GEN-105）：`_formula_image` 以
# `_FORMULA_IMAGE_DPI` 光栅化、字号为 `_FORMULA_IMAGE_EM_PT`（pt）——图上的 em
# 实际有 EM_PT × DPI/72 个像素（14pt@180dpi = 35px）。reportlab 的 `Image` 默认
# 把 **1 像素当 1pt**（72dpi 假设），直接放置正好把公式放大 DPI/72 = 2.5 倍；因此
# 放置时先按 72/DPI 做单位换算，再归一到文档正文字号（profile `body.size-pt`）。
_FORMULA_IMAGE_DPI = 180.0
_FORMULA_IMAGE_EM_PT = 14.0

# 含汉字（或全角标点）的公式不能交给 MathText：数学字体没有汉字字形，会印出一串
# 假字形方框（GB_3100-2026 8.2.3 的「米/秒；米·秒⁻¹；米/秒」实测）。可用的图资产
# （MinerU 裁剪图，GEN-102）仍优先；无可用资产时按文本拍平渲染（GEN-106）。
_CJK_IN_FORMULA_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3000-\u303f\uff01-\uff60]")


def _latex_has_cjk(text: str) -> bool:
    """公式源码是否含汉字/全角标点（判定 MathText 能否排版，GEN-106）。"""
    return bool(_CJK_IN_FORMULA_RE.search(text or ""))


def _formula_image_scale(font_size_pt: float) -> float:
    """生成公式图的像素→点换算 × 目标字号比（GEN-105）。

    默认正文字号 10.5pt 时 = (72/180) × (10.5/14) = **0.3**，即「生成图按正文字号
    显示」；容器宽 / 140pt 高的上限仍在调用处用 ``min()`` 继续收窄（只缩小不放大）。
    """
    return (72.0 / _FORMULA_IMAGE_DPI) * (font_size_pt / _FORMULA_IMAGE_EM_PT)


# ---------------------------------------------------------------------------
# 行内 math 的变量斜体与上划线（GEN-116；GB/T 1.1-2020 10.4.6、GBT-B12/GBT-X06
# 执行侧）。源 PDF 实测（GB_T_30819-2024 p25 的 6.4 式中、GB_T_5171.1-2014 p10）：
#   量符号 P/n/T/R/i/Φ/η 用**斜体**字形；下标数字与描述性下标（P_N 的 N）、单位
#   （kW、r/min、K）、数字与运算符用正体；量符号上的短横线是**矢量短横线**压在
#   字母上方（`\overline{η}`）；数学算子希腊大写 Δ 正体而其后变量 t 斜体。
# 拍平（`_latex_to_text`）会把 `\overline` 当未知命令丢掉、字母一律正体——这两条
# 约定因此在渲染端丢失。
_MATH_REGION_OPEN = "\x00MATH\x00"      # 行内 math 区域边界（斜体化范围；escape 前剥离）
_MATH_REGION_CLOSE = "\x00/MATH\x00"
_MATH_UPRIGHT_OPEN = "\x00UPR\x00"      # \mathrm/\text 等直立内容（不斜体化的遮罩）
_MATH_UPRIGHT_CLOSE = "\x00/UPR\x00"
_MATH_OVERLINE = "\x00BAR\x00"          # \overline/\bar → U+0304 组合上划线
# 直立内容命令：单位与说明文字（源版面正体）
_MATH_UPRIGHT_COMMANDS = (
    "mathrm", "text", "textrm", "textup", "textnormal", "textsf", "texttt", "operatorname", "mbox",
)
# 正体字母（源版面或规范约定为直立）：数学算子 Δ 增量、Σ/Π 求和求积、∂ 偏导、∇ 梯度；
# Ω 在语料内只作**单位**（GB_T_10401-2023「绝缘电阻不应小于 100MΩ」，3 处），单位符号
# 正体。若出现作为量符号的 Ω（立体角/电阻）需按源版面另立证据。
_MATH_UPRIGHT_LETTERS = "ΔΣΠ∂∇Ω"
_MATH_VARIABLE_LETTERS = set(ascii_letters) | set(
    "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ" "αβγδεζηθικλμνξοπρστυφχψω"
)


def _inline_math_text(latex: str) -> str:
    """行内 $…$ → 可读文本，并保住变量斜体与上划线两条约定（GEN-116）。

    * **上划线**：`\\overline{X}`/`\\bar{X}` → 内容 + U+0304 组合上划线——源版面用
      矢量短横线压在字母上方；该字形的墨迹以**笔位为中心**（Noto Serif CJK 实测
      xMin/xMax = ∓134/1000 em、advance 0），紧跟字母绘制即落在字母上方。
    * **变量斜体**：基字位置的拉丁/希腊字母由 `_italicize_math_regions` 在 `_markup`
      末尾包成斜体哨兵（`\\x00EMI\\x00`，GEN-108 的机斜字形）；`\\mathrm{}`/`\\text{}`
      内容、上下标内容、数学算子（Δ/Σ/Π/∂）、紧跟 `^{…}` 的单字母基字（语料实测
      全是单位 m²/m³ 与 10 的幂）保持正体。
    """
    text = latex.strip()
    # ① 上划线先替换成记号：`\overline`/`\bar` 是「未知命令」，`_latex_expand_nested`
    #    与 `_latex_to_text` 都会连命令带花括号一起丢掉（同族的
    #    `\overline { { \eta } }` 形态更会拍成空串）。嵌套形态（MinerU 常写 `{ { X } }`）
    #    先处理，再处理单层——`\{…\}?\}` 式的可选括号会把外层 `_ { X }` 的收尾括号一起
    #    吃掉，把下标组拍坏。必须在 `_latex_expand_nested` **之前**做。
    text = re.sub(
        r"\\(?:overline|bar)\s*\{\s*\{\s*([^{}]*?)\s*\}\s*\}",
        lambda match: match.group(1) + _MATH_OVERLINE,
        text,
    )
    text = re.sub(
        r"\\(?:overline|bar)\s*\{\s*([^{}]*?)\s*\}",
        lambda match: match.group(1) + _MATH_OVERLINE,
        text,
    )
    # ② 直立内容（\mathrm{kPa}、\text{米} 等）包上遮罩：这些字符不参与斜体化。
    #    同样必须在 `_latex_expand_nested` 之前（它会把这些命令直接拆掉）。
    commands = "|".join(_MATH_UPRIGHT_COMMANDS)
    mask = lambda match: _MATH_UPRIGHT_OPEN + re.sub(r"\s+", "", match.group(1)) + _MATH_UPRIGHT_CLOSE
    text = re.sub(rf"\\(?:{commands})\s*\{{\s*\{{\s*([^{{}}]*?)\s*\}}\s*\}}", mask, text)
    text = re.sub(rf"\\(?:{commands})\s*\{{\s*([^{{}}]*?)\s*\}}", mask, text)
    return _latex_to_text(text).replace(_MATH_OVERLINE, "\u0304")


def _inline_math_markup(latex: str) -> str:
    """行内 $…$ 的完整渲染文本：拍平 + 变量斜体 + 上划线（GEN-116）。

    斜体化在**拍平当步**完成（区域哨兵只包住这一段片段本身），于是后续的
    「数值-单位固定字隙」等文本规则看到的仍是原样文本，行为与改动前一致；直立内容
    的遮罩也在同一步剥离，不会挡住那些规则。
    """
    return _italicize_math_regions(_MATH_REGION_OPEN + _inline_math_text(latex) + _MATH_REGION_CLOSE)


def _italicize_math_regions(text: str) -> str:
    """把行内 math 区域（`\\x00MATH\\x00…`）里的基字变量包成斜体哨兵，并剥离区域哨兵。

    只在 `_markup` 末段（`escape()` 之前）调用：数值-单位固定字隙、编号后字隙等
    既有文本规则先看到**原样文本**，行为与本次改动前一致。
    """
    out: list[str] = []
    index = 0
    while index < len(text):
        start = text.find(_MATH_REGION_OPEN, index)
        if start < 0:
            out.append(text[index:])
            break
        out.append(text[index:start])
        end = text.find(_MATH_REGION_CLOSE, start)
        if end < 0:                                # 未闭合：原样输出（不猜）
            out.append(text[start:])
            break
        out.append(_italicize_math_variables(text[start + len(_MATH_REGION_OPEN):end]))
        index = end + len(_MATH_REGION_CLOSE)
    joined = "".join(out)
    return joined.replace(_MATH_UPRIGHT_OPEN, "").replace(_MATH_UPRIGHT_CLOSE, "")


def _italicize_math_variables(segment: str) -> str:
    """math 区域内的变量斜体化（GEN-116）：跳过直立遮罩、上/下标内容与其它哨兵。"""
    out: list[str] = []
    index = 0
    while index < len(segment):
        if segment.startswith(_MATH_UPRIGHT_OPEN, index):
            end = segment.find(_MATH_UPRIGHT_CLOSE, index + len(_MATH_UPRIGHT_OPEN))
            end = len(segment) if end < 0 else end + len(_MATH_UPRIGHT_CLOSE)
            out.append(segment[index:end])         # 直立内容原样
            index = end
            continue
        if segment.startswith("\x00SUB\x00", index) or segment.startswith("\x00SUP\x00", index):
            close = "\x00/SUB\x00" if segment.startswith("\x00SUB\x00", index) else "\x00/SUP\x00"
            end = segment.find(close, index + 1)
            end = len(segment) if end < 0 else end + len(close)
            out.append(segment[index:end])         # 上/下标内容原样（源版面正体）
            index = end
            continue
        mark = re.match(r"\x00[^\x00]*\x00", segment[index:])
        if mark:                                   # 其它哨兵（QEM/WSP/GAP…）原样
            out.append(mark.group(0))
            index += mark.end()
            continue
        char = segment[index]
        if char in _MATH_VARIABLE_LETTERS and char not in _MATH_UPRIGHT_LETTERS:
            end = index
            while end < len(segment) and segment[end] in _MATH_VARIABLE_LETTERS and segment[end] not in _MATH_UPRIGHT_LETTERS:
                end += 1
            run = segment[index:end]
            # 例外：单字母基字紧跟上标（^{…}）→ 单位/常数（m²、m³），源版面正体。
            if segment.startswith("\x00SUP\x00", end):
                out.append(run)
            else:
                out.append("\x00EMI\x00" + run + "\x00/EMI\x00")
            index = end
            continue
        out.append(char)
        index += 1
    return "".join(out)



# 块级公式按**显示样式**排版（GEN-109）：canonical 的 `ssir:formula` 是 LaTeX 的 display
# math（`$$…$$`），而 MathText 的 `$…$` 等价于**行内（text style）**——`\frac` 的分子/分母
# 被降为脚标号、写在 `\sqrt{…}` 里的分数更小。GB/T 1.1-2020 9.9.3.1 示例1「v = l/t」实测：
# 分数堆高只有 12.9pt（源文同一公式 17.0pt，且源文分数的分子/分母与左侧字母同大），
# 示例5「t_i = √(S_ME,i / S_MR,i)」同理（用户报「公式看起来仍然略显小」）。
# MathText 不支持 `\displaystyle`，但支持 `\dfrac`（display 分数），故按 TeX 的样式规则把
# **最外层**的 `\frac` 提升为 `\dfrac`；分数参数内与上/下标内的分数保持原样式（TeX 在那里
# 本就是 text/script style），`\tfrac`（作者显式要求小分数）不改。
_FRAC_TOKEN_RE = re.compile(r"\\(dfrac|tfrac|frac)(?![A-Za-z])")


def _display_style_latex(expression: str) -> str:
    r"""把块级公式里**最外层**的 ``\frac`` 提升为 ``\dfrac``（GEN-109）。

    样式降级只由两处触发：**分数的参数**与**上/下标**；普通花括号只作分组、不改变样式
    （所以 ``\sqrt{\frac{a}{b}}`` 里的分数仍是最外层）。函数用栈跟踪当前是否处于降级区域，
    区域内的 ``\frac`` 原样保留。
    """
    expression = str(expression)
    if not _FRAC_TOKEN_RE.search(expression):
        return expression
    out: list[str] = []
    downgrade_stack: list[bool] = []
    downgraded = 0
    pending_frac_args = 0
    index = 0
    while index < len(expression):
        char = expression[index]
        if char == "{":
            is_downgrade = pending_frac_args > 0
            pending_frac_args = max(0, pending_frac_args - 1)
            downgrade_stack.append(is_downgrade)
            downgraded += 1 if is_downgrade else 0
            out.append(char)
            index += 1
            continue
        if char == "}":
            if downgrade_stack and downgrade_stack.pop():
                downgraded -= 1
            out.append(char)
            index += 1
            continue
        if char in "_^":
            out.append(char)
            index += 1
            if index < len(expression) and expression[index] == "{":
                downgrade_stack.append(True)
                downgraded += 1
                out.append("{")
                index += 1
            continue
        match = _FRAC_TOKEN_RE.match(expression, index)
        if match:
            name = match.group(1)
            out.append("\\dfrac" if (name == "frac" and downgraded == 0) else match.group(0))
            lookahead = match.end()
            while lookahead < len(expression) and expression[lookahead] in " \t":
                lookahead += 1
            # 只跟踪**带花括号**的参数（`\frac12` 这类不带括号的参数不参与降级跟踪）。
            pending_frac_args = 2 if lookahead < len(expression) and expression[lookahead] == "{" else 0
            index = match.end()
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _formula_image(latex: str, asset_dir: Path) -> Path | None:
    """Render a display formula through Matplotlib's bundled MathText engine.

    规则对应: GBT-X06（数学公式另行居中编排的资产支撑）、GEN-105（光栅参数与
    显示换算同源——尺寸换算见 ``_formula_image_scale``，改动这里的 dpi/字号必须
    同时改 ``_FORMULA_IMAGE_DPI`` / ``_FORMULA_IMAGE_EM_PT``）、GEN-109（块级公式
    按显示样式排版——最外层分数为 ``\\dfrac``，见 ``_display_style_latex``）。

    缓存文件按**提升后**的表达式取哈希：否则旧的（行内样式的）图会一直命中缓存，
    修复对已渲染过的文档不生效。
    """
    expression = _display_style_latex(latex.strip())
    if not expression:
        return None
    path = asset_dir / "assets" / "formulas" / f"{hashlib.sha256(expression.encode('utf-8')).hexdigest()}.png"
    if path.is_file():
        return path
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure

        path.parent.mkdir(parents=True, exist_ok=True)
        figure = Figure(figsize=(6.2, 0.7), dpi=_FORMULA_IMAGE_DPI)
        FigureCanvasAgg(figure)
        figure.text(0.5, 0.5, f"${expression}$", fontsize=_FORMULA_IMAGE_EM_PT, ha="center", va="center")
        figure.savefig(path, dpi=_FORMULA_IMAGE_DPI, transparent=True, bbox_inches="tight", pad_inches=0.04)
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
    # 附录标题里的 (规范性)/(资料性) 由 _heading_annex_status(node) 单独读取
    # （本函数只负责剥出，返回值为编号 + 纯标题）。
    if annex:
        status_match = re.match(r"^（(规范性|资料性|未判定)）\s*(.*)$", title)
        if status_match:
            title = status_match.group(2).strip()
    annex_match = re.match(r"^附\s*录\s*([A-Z])(?:\s*(.*))?$", title)
    if annex_match:
        return annex_match.group(1), (annex_match.group(2) or "").strip(), True
    if annex:
        # 附录的 (规范性)/(资料性) 已从 title 中剥出为 status；调用方需要时用
        # _heading_annex_status(node) 再读一次（节点本身未被改写，故此处只返回
        # 编号 + 纯标题）。
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


# 术语条目标题（GB/T 1.1-2020 8.7.3.1）：术语（中文）+ 英文对应词。英文段必须是
# 纯拉丁（汉字、全角标点即不认）——编号条款标题里也会出现拉丁（GB_3100-2026
# 「5.2 具有专门名称的SI导出单位」的拉丁后仍接汉字），那不是术语条目。
_TERM_ENTRY_TITLE_RE = re.compile(
    r"^([\u4e00-\u9fff]{1,24})[ \u3000\u200b]*([A-Za-z][A-Za-z0-9 &/(),.\-·'\u2019]*)$"
)


def _term_entry_text(node: dict[str, Any], number: str, title: str) -> str | None:
    """术语条目的术语行「术语　英文对应词」，不是术语条目时返回 None。

    判据：点分条目编号（≥3 段，如 3.1.2；与 parser 的术语条目合并判据同源）+
    标题为「汉字串 + 纯拉丁英文对应词」。附录/示例内容块不参与（示例文档自带
    编号与名称是文档名，不是本标准术语条目）。
    """
    if not number or number.count(".") < 2:
        return None
    if node.get("nodeType") == "annex" or node.get("exampleContent"):
        return None
    match = _TERM_ENTRY_TITLE_RE.match(str(title).strip())
    if not match:
        return None
    return f"{match.group(1)}\u3000{match.group(2)}"


def _term_entry_flowables(
    node: dict[str, Any],
    number: str,
    title: str,
    heading: str,
    heading_style: Any,
    styles: dict[str, Any],
    font: str,
    Paragraph: Any,
) -> list[Any]:
    """标题流：普通标题一行；术语条目按 GB/T 1.1-2020 10.3.5 分两行。

    术语条目 = 条目编号行（顶格）+ 术语行（空两个汉字、中英文之间空一个汉字），
    两行同字号同字体（附录F 表F.1 序号22/23「五号黑体」），且上下无空行——
    由 ``term-number``/``term-title`` 样式的 spaceBefore/After=0 与正文行距保证。
    """
    term = _term_entry_text(node, number, title)
    if term is None:
        return [Paragraph(_label_markup(heading, font, heading_style.fontSize), heading_style)]
    return [
        Paragraph(_markup(number, styles["term-number"].fontSize), styles["term-number"]),
        Paragraph(_markup(term, styles["term-title"].fontSize), styles["term-title"]),
    ]


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
            # 术语条目不入目次（GB/T 1.1-2020 8.2.2："在目次中不应列出'术语和定义'
            # 中的条目编号和术语"）；toc_depth=all 时才可能命中，默认深度 2 已排除。
            if _term_entry_text(node, number, title) is not None:
                continue
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


# 目次里的图行（GB/T 1.1-2020 8.2.2 i)、10.3.2）：图题在抽取结果里是独立段落
# （「图 B.1 标记体系的组成」；附录图题形如「图 B.1」），图资产本身不带题名。
# 判据刻意收窄：编号与题名之间必须有空白、题名是短题名且不含句末标点/波浪线——
# 正文行内引用「图E.1～图E.12规定了…」不是图题（8.2.2 列的是图编号和图题）。
_TOC_FIGURE_CAPTION_RE = re.compile(
    r"^图\s*(?P<number>(?:[A-Z]\.)?\d+(?:\.\d+)*)[ \u3000]+(?P<title>[^。；！？～]{1,40})$"
)
# 目次里的表行：表编号须是真实编号形态（拒「表× 表题」这类格式示例占位），
# 同一编号只列一次（表跨页被 MinerU 拆成多个表对象时,续块无题名）。
_TOC_TABLE_NUMBER_RE = re.compile(r"^(?:\d+(?:\.\d+)*|[A-Z]\.\d+(?:\.\d+)*)$")


def _toc_caption_rows(root_nodes: list[dict[str, Any]], registries: dict[str, dict[str, dict[str, Any]]]) -> list[list[tuple[str, str]]]:
    """目次里的图行与表行（GB/T 1.1-2020 8.2.2 i)/j)、10.3.2）。

    返回 ``[[(标签, 取页对象 id)…], [(标签, 取页对象 id)…]]``（图组、表组），标签按
    10.3.2「给出编号，空一个汉字的间隙后给出完整的标题」。抽取结果里图题是**独立
    段落**（「图 B.1 标记体系的组成」，附录图题形如「图 B.1」；图资产本身不带题名），
    表题名在表格注册表（``number``/``caption``）。

    附录编写示例块（CSM-OCR-006）与显式框（``ssir:box``）里的图/表是示例文档自带的，
    不是本文件的图、表，剔除。
    """
    figure_rows: list[tuple[str, str]] = []
    table_rows: list[tuple[str, str]] = []
    seen_tables: set[str] = set()
    seen_table_numbers: set[str] = set()
    seen_figure_numbers: set[str] = set()

    def visit(nodes: list[dict[str, Any]], inside: bool) -> None:
        for node in nodes:
            here = inside or bool(node.get("exampleContent")) or node.get("box") is not None
            for content in node.get("contentElements", []) or []:
                boxed = here or content.get("box") is not None
                if boxed:
                    continue
                if content.get("presentationType") == "figure":
                    figure = registries["figures"].get(str(content.get("figureRef") or ""))
                    if not figure:
                        continue
                    number = str(figure.get("number") or "").strip()
                    caption = str(figure.get("caption") or "").strip()
                    identifier = str(figure.get("id") or "")
                    if number and _TOC_TABLE_NUMBER_RE.match(number) and identifier and number not in seen_figure_numbers:
                        seen_figure_numbers.add(number)
                        figure_rows.append((f"图{number}\u3000{caption}".rstrip(), identifier))
                elif content.get("presentationType") == "paragraph":
                    match = _TOC_FIGURE_CAPTION_RE.match(str(content.get("textContent") or "").strip())
                    if match:
                        identifier = str(content.get("id") or "")
                        number = match.group("number")
                        if identifier and number not in seen_figure_numbers:
                            seen_figure_numbers.add(number)
                            figure_rows.append((f"图{number}\u3000{match.group('title').strip()}", identifier))
                elif content.get("presentationType") == "table":
                    table = registries["tables"].get(str(content.get("tableRef") or ""))
                    if not table:
                        continue
                    number = str(table.get("number") or "").strip()
                    caption = str(table.get("caption") or "").strip()
                    identifier = str(table.get("id") or "")
                    if not _TOC_TABLE_NUMBER_RE.match(number) or not identifier:
                        continue
                    if identifier in seen_tables or number in seen_table_numbers:
                        continue
                    seen_tables.add(identifier)
                    seen_table_numbers.add(number)
                    table_rows.append((f"表{number}\u3000{caption}".rstrip(), identifier))
            visit(node.get("children", []) or [], here)

    visit(root_nodes, False)
    return [figure_rows, table_rows]


def _toc_label(node: dict[str, Any]) -> str:
    synthesized = node.get("_tocLabel")
    if synthesized:
        return str(synthesized)
    number, title, is_annex = _heading_parts(node)
    title = title.replace(" ", "")
    if is_annex:
        # GB/T 1.1-2020 10.3.2：附录的目次应给出附录编号，后跟“(规范性)”或
        # “(资料性)”，空一个汉字的间隙后给出附录标题。状态在 _heading_parts
        # 里已被剥出（只返回编号 + 纯标题），故在此按节点标题回读一次。
        status = _heading_annex_status(node)
        entry = f"附录 {number}{status}"
        return f"{entry}\u3000{title}" if title else entry
    return _heading_text(number, title, is_annex)


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
    # 索引内容可能挂在「索引」节点自身的 contentElements（2026-09-12 起：字母分组
    # 行按 CSM-OCR-019 降级为段落、不再是与附录同级的兄弟节点），也可能在后续兄弟
    # 节点里（旧结构：`## B`/`## D`/`## Z` 节点）。两者都收，兼容两种结构。
    source_nodes = [root_nodes[start], *root_nodes[start + 1:]]
    for node in source_nodes:
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
        height = IndexFlowable(candidate, _BODY_MEASURE).wrap(_BODY_MEASURE, 650)[1]
        if batch and height > 620:
            result.append(IndexFlowable(batch, _BODY_MEASURE))
            result.append(PageBreak())
            batch = [row]
        else:
            batch = candidate
    if batch:
        result.append(IndexFlowable(batch, _BODY_MEASURE))
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
