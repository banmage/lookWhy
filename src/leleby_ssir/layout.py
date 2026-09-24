"""版面/结构附加信息（`01_extract/<ID>.layout.json`）——抽取阶段唯一读源 PDF 的通道。

规则对应（docs/16 §1 新数据流 / §2.3 内容清单 / §3 读取点迁移表，D1 裁定「源 PDF 在
MinerU 之后不再读取」）：

- GEN-092（省略号后验补盲）——输入由「源 PDF 文本层」改为本文件的 ``textLines``；
- GEN-016 / GEN-014（英文标题、发布机构的 PDF 文本层兜底）——``cover.pdfPage0Lines``；
- GEN-052 / CSM-STRUCT-006（示例框线风格）——``frames``；
- GEN-096 / GEN-098（图源尺寸）——``imageRects``；
- GEN-095（并列版面）——``columns``（页 → 块几何；分列聚类与内容匹配的**判定**留在消费端）；
- GEN-119 / CSM-OCR-015（表角标回收）、GEN-118 / CSM-OCR-014（条文脚注回收）——
  ``textSpans`` + ``pages``（两条恢复规则共用的逐页 span 与页尺寸读数）。

设计口径（docs/16 §3「**通道不改判据**」）：本模块只负责**读源 PDF 取几何与文本**，
把结果按通道落进 ``layout.json``；所有判定（什么算省略号行、什么算机构行、图与资产
如何匹配、角标证据门）仍留在 ``pipeline.py`` 的消费端，逐字节可回放。通道缺失时消费端
按「无判据」处理——记 issue、不猜、不阻断（AGENTS.md §0.2/§0.3）。

**不记**模板化版式（页边距、字体字号、行距、列宽、线条粗细、页码位置等，由 GB/T 1.1
与渲染 profile 决定）。
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

LAYOUT_SCHEMA_VERSION = "1.0"
LAYOUT_PRODUCER = "mineru+layout"

#: 省略号字符（U+2026 与 U+22EF 中线省略号，部分字体映射）
_ELLIPSIS_CHARS = ("…", "⋯")

_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９．", "0123456789.")

#: 示例框线候选矩形的最小尺寸（迁移前判据：宽 ≥ 80pt、高 ≥ 30pt）
_FRAME_MIN_WIDTH = 80.0
_FRAME_MIN_HEIGHT = 30.0

#: 内容图候选矩形的最小尺寸（迁移前判据：宽高 ≥ 10pt）
_IMAGE_MIN_SIZE = 10.0

#: 封面页（第 1 页）上高 < 100pt 的矩形是徽标/装饰图，不做内容图候选（迁移前判据）
_COVER_BADGE_MAX_HEIGHT = 100.0

#: 分片目录名里的页范围（``pages-037-054`` → 起始页 37）：MinerU 分片的 ``page_idx``
#: 各自从 0 起，必须靠目录名映射回绝对页号（迁移前判据）
PART_PAGE_RANGE_RE = re.compile(r"pages-(\d+)-(\d+)")


def _pymupdf() -> Any | None:
    """延迟导入 pymupdf（缺失时返回 None：调用方按无判据处理）。"""
    try:
        import pymupdf  # type: ignore
    except ImportError:  # pragma: no cover - 依赖缺失时的降级路径
        return None
    return pymupdf


def text_layer_content_lines(pdf: Path) -> list[dict[str, Any]]:
    """Extract content lines (page/x0/y0/x1/y1/text) from the source PDF text layer.

    通用后验的输入基础：文本层是版面真值的唯一权威来源（MinerU OCR 可能丢弃
    纯符号行——如"……"占位行——而文本层完整保留；中文虽可能乱码，但行数、
    坐标、数字、拉丁与标点符号可信）。

    规则对应: GEN-092（省略号后验补盲的输入）。逐字节等价于迁移前的
    ``pipeline._text_layer_content_lines``（同一过滤：页眉 y0<80、页脚纯页码）。
    """
    module = _pymupdf()
    if module is None:
        return []
    lines: list[dict[str, Any]] = []
    with module.open(pdf) as document:
        for page_index in range(len(document)):
            page = document[page_index]
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    text = "".join(span["text"] for span in line["spans"]).strip()
                    if not text:
                        continue
                    y0 = line["bbox"][1]
                    x0 = line["bbox"][0]
                    if y0 < 80:
                        continue  # 页眉（标准号眉线）
                    if y0 > 740 and re.fullmatch(r"[0-9０-９IVXⅣⅤⅧ]+", text):
                        continue  # 页脚页码（奇偶页左右交替，只按内容形态过滤）
                    lines.append(
                        {
                            "page": page_index + 1,
                            "x0": x0,
                            "y0": y0,
                            "x1": line["bbox"][2],
                            "y1": line["bbox"][3],
                            "text": text,
                        }
                    )
    return lines


def is_short_ellipsis(text: str) -> bool:
    """Pure ellipsis line (1-6 个 …/⋯)。目录点线（40+ 个 …）不属于内容占位。"""
    t = text.replace(" ", "")
    return 1 <= len(t) <= 6 and set(t) <= set(_ELLIPSIS_CHARS)


def clause_skeleton(text: str) -> str | None:
    """行首条号骨架：５．８ → 5.8、６ → 6。仅当行首（可带破折号/空白）是
    点分数字链**且后随空白或行尾**时返回——乱码行中段碎片（如 "7b…"）的
    伪编号不匹配，避免把省略号锚到错误位置。"""
    t = text.translate(_FULLWIDTH_DIGITS)
    # 后随空白时空白后不得再是数字（"１ 01" 型目录页码行不算条号）；
    # 后随行尾也可（孤立的章号行）。
    match = re.match(r"^[\s—–\-]*(\d+(?:\.\d+){0,3})(?=\s(?![0-9０-９])|$)", t)
    return match.group(1) if match else None


def raw_line_starts_with_number(line: str, skeleton: str) -> bool:
    """raw 行（可带 markdown 标题前缀）是否以该条号骨架开头且不吞掉更长编号。"""
    s = line.lstrip("#").strip()
    return bool(re.match(rf"^{re.escape(skeleton)}(?=[^\d.]|$)", s))


def pdf_page_lines(pdf: Path, page_index: int = 0) -> list[str]:
    """源 PDF 指定页的原始文本行（逐行 strip、去空行，**不做任何判定**）。

    规则对应: GEN-016 / GEN-014 的文本层兜底输入。逐行判定（封面横幅、"标准" 结尾、
    日期行、文档号行过滤）留在 ``pipeline._cover_metadata``——通道只搬运文本。
    """
    module = _pymupdf()
    if module is None:
        return []
    try:
        with module.open(pdf) as document:
            if page_index >= len(document):
                return []
            page_text = document[page_index].get_text()
    except Exception:
        return []
    return [line.strip() for line in page_text.splitlines() if line.strip()]


def vector_frame_rects(pdf: Path) -> list[dict[str, Any]]:
    """示例框线候选矩形（GEN-052 / CSM-STRUCT-006 的输入读数）。

    逐字节等价于迁移前 ``pipeline._stamp_example_styles`` 的 PDF 扫描：只收**大尺寸
    矩形**（宽 ≥ 80pt、高 ≥ 30pt，页眉页脚与表格细线因此不入候选）；每条按读到的
    形状类别归一——有填充 → ``shaded``；否则有描边 → ``frame``。

    这是**读数**而不是风格判定：文档级风格（stroke ≥ fill → frame）仍由消费端按
    同一规则算，见 ``pipeline._stamp_example_styles``。
    """
    module = _pymupdf()
    if module is None:
        return []
    rects: list[dict[str, Any]] = []
    try:
        with module.open(pdf) as document:
            for page_index, page in enumerate(document):
                for drawing in page.get_drawings():
                    rect = drawing["rect"]
                    if rect.width < _FRAME_MIN_WIDTH or rect.height < _FRAME_MIN_HEIGHT:
                        continue
                    if drawing.get("fill"):
                        style = "shaded"
                    elif drawing.get("stroke"):
                        style = "frame"
                    else:
                        continue
                    rects.append(
                        {
                            "page": page_index + 1,
                            "bbox": [rect.x0, rect.y0, rect.x1, rect.y1],
                            "style": style,
                        }
                    )
    except Exception:
        return []
    return rects


def image_rects(pdf: Path) -> list[dict[str, Any]]:
    """内容图候选矩形（GEN-096 / GEN-098 的输入读数）。

    逐字节等价于迁移前 ``pipeline._stamp_figure_source_sizes`` 的 PDF 扫描：宽高均
    ≥ 10pt；第 1 页（封面）上高 < 100pt 的徽标/装饰小图不入候选（封面徽标由
    ``config/emblems/`` 独立处理，非内容图）。尺寸匹配（宽高比/密度贪心）与
    像素密度回退留在消费端。
    """
    module = _pymupdf()
    if module is None:
        return []
    rects: list[dict[str, Any]] = []
    try:
        with module.open(pdf) as document:
            for page_index, page in enumerate(document):
                for info in page.get_image_info():
                    r = info["bbox"]
                    rw, rh = r[2] - r[0], r[3] - r[1]
                    if rw < _IMAGE_MIN_SIZE or rh < _IMAGE_MIN_SIZE:
                        continue
                    if page_index == 0 and rh < _COVER_BADGE_MAX_HEIGHT:
                        continue
                    rects.append(
                        {"page": page_index + 1, "bbox": [r[0], r[1], r[2], r[3]], "width": rw, "height": rh}
                    )
    except Exception:
        return []
    return rects


def latex_key(latex: str) -> str:
    """公式匹配键：去掉全部空白（迁移前 ``pipeline._latex_key``，逐字节等价）。

    两条抽取路线的同一公式在分词/空格上不同（本地 ``v = 3.6 \\times \\frac{l}{t}``、
    云端 ``v = 3. 6 \\times \\frac {l}{t}``），按空白归一后才是同一个键。
    """
    return re.sub(r"\s+", "", latex or "")


def middle_geometry_sources(parts_dir: Path | None, middle_json: Path | None = None) -> list[Path]:
    """并列版面识别用的 ``*_middle.json`` 清单（两条来源合并，按路径去重）。

    两条来源是**同一套版面几何的两种分片形态**，合并使用让两侧锚点都能参与匹配：

    - 整份文档的 ``middle.json``（raw 起点路线：云端/Pipeline 的抽取产物本身就是这份数据，
      ``page_idx`` 是 0 基绝对页号 → 落回 ``page_idx + 1``）；
    - 分片目录 ``parts/``（merge 起点路线：每个分片一个 middle.json，绝对页号从目录名
      ``pages-037-054`` 取起始页）。

    合并稿这类「文本来自一侧、公式来自另一侧」的文档，两边的资产名/LaTeX 各有一部分命中，
    只取一侧会丢掉另一半锚点；重复的锚点由内容级去重挡住（消费端）。
    """
    sources: list[Path] = []
    if middle_json is not None and Path(middle_json).is_file():
        sources.append(Path(middle_json))
    if parts_dir is not None and Path(parts_dir).is_dir():
        sources.extend(sorted(Path(parts_dir).rglob("*_middle.json")))
    unique: dict[str, Path] = {}
    for path in sources:
        unique.setdefault(str(path.resolve()), path)
    return list(unique.values())


def parse_middle_geometry(sources: list[Path]) -> dict[int, list[dict[str, Any]]]:
    """MinerU ``middle.json`` 几何 → ``{绝对页号: [块]}``（并列检测的输入读数）。

    规则对应: GEN-095（并列版面通用识别的几何侧）。逐字节等价于迁移前
    ``pipeline._stamp_side_by_side_layout`` 的前半段：每块记为
    ``{type, bbox, text, asset, latex, spans}``；绝对页号由分片目录名（``pages-037-054``）
    或 ``page_idx + 1`` 得到；行内公式 span 的文本并入块文本（变量解释行的变量在
    inline_equation span 里，只取 text span 会漏），并保留 span 级文本+坐标供消费端
    做细粒度匹配。

    **判定不在这里**：分列聚类、内容匹配、连续性校验、并列组打标全部留在消费端
    （``pipeline._stamp_side_by_side_layout``）——通道只搬运读数。
    """
    pages: dict[int, list[dict[str, Any]]] = {}

    def _absolute_page(middle_path: Path, page_idx: int) -> int:
        for parent in middle_path.parents:
            match = PART_PAGE_RANGE_RE.fullmatch(parent.name)
            if match:
                return int(match.group(1)) + int(page_idx)
        return int(page_idx) + 1

    def _block_lines(block: dict) -> list[dict]:
        # image 块的 span 在 blocks[*].lines[*]，text/interline_equation 块直接在
        # lines[*]（MinerU pipeline 后端的两种层级都要取）。
        lines: list[dict] = []
        for sub_block in block.get("blocks") or []:
            lines.extend(sub_block.get("lines") or [])
        lines.extend(block.get("lines") or [])
        return lines

    for middle in sources:
        try:
            raw = json.loads(Path(middle).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for info in raw.get("pdf_info") or []:
            page_idx = info.get("page_idx")
            if page_idx is None:
                continue
            page_no = _absolute_page(Path(middle), page_idx)
            blocks = pages.setdefault(page_no, [])
            for block in info.get("preproc_blocks") or []:
                bbox = block.get("bbox")
                if not bbox or len(bbox) != 4:
                    continue
                text_parts: list[str] = []
                spans: list[tuple[str, float, float, float, float]] = []
                asset: str | None = None
                latex: str | None = None
                for line in _block_lines(block):
                    for span in line.get("spans") or []:
                        span_type = span.get("type")
                        span_bbox = span.get("bbox")
                        if span_type in ("image", "interline_equation") and span.get("image_path"):
                            asset = Path(str(span["image_path"])).name
                            # 公式锚点两种形态并存：本地路线用裁剪图资产、云端路线只有
                            # LaTeX（SSIR 公式节点也只有 latex）——两个键都记，匹配时资产优先。
                            if span_type == "interline_equation" and span.get("content"):
                                latex = latex_key(str(span["content"]))
                        elif span_type == "interline_equation" and span.get("content"):
                            latex = latex_key(str(span["content"]))
                        elif span_type in ("text", "inline_equation") and span.get("content"):
                            content = str(span["content"])
                            text_parts.append(content)
                            if span_bbox and len(span_bbox) == 4:
                                spans.append((content.strip(), float(span_bbox[0]), float(span_bbox[1]),
                                              float(span_bbox[2]), float(span_bbox[3])))
                blocks.append({
                    "type": block.get("type"),
                    "bbox": [float(value) for value in bbox],
                    "text": "".join(text_parts).strip(),
                    "asset": asset,
                    "latex": latex,
                    "spans": spans,
                })
    return {page: blocks for page, blocks in pages.items() if blocks}


def text_spans(pdf: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """逐页文本 span 与页尺寸（脚注/表角标回收的输入读数）。

    规则对应: CSM-OCR-014（条文脚注回收）、CSM-OCR-015（表角标回收）——两条恢复规则
    都要「正文中位字号、上标阈值、视觉行聚类、页底 0.68×页高」这些读数，本函数一次读出：
    只收**非空文本** span，每条记 ``page``（1 基）/``bbox``/``origin``（基线）/``size``/``text``，顺序即
    ``page.get_text("dict")`` 的块-行-span 顺序（消费端随后自行排序）。页尺寸记
    ``page``/``width``/``height``——页尺寸是版面真值，不是模板化版式。

    **判定不在这里**：上标阈值、标记成对、锚文本唯一性等全部留在消费端
    （``pipeline._recover_pdf_footnotes`` / ``_recover_table_note_markers``）。
    """
    module = _pymupdf()
    if module is None:
        return [], []
    spans: list[dict[str, Any]] = []
    sizes: list[dict[str, Any]] = []
    try:
        with module.open(pdf) as document:
            for page_index, page in enumerate(document):
                sizes.append(
                    {
                        "page": page_index + 1,
                        "width": float(page.rect.width),
                        "height": float(page.rect.height),
                    }
                )
                for block in page.get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        for span in line["spans"]:
                            if not str(span.get("text") or "").strip():
                                continue
                            spans.append(
                                {
                                    "page": page_index + 1,
                                    "bbox": [float(value) for value in span["bbox"]],
                                    "origin": [
                                        float(value) for value in (span.get("origin") or span["bbox"][:2])
                                    ],
                                    "size": float(span.get("size") or 0.0),
                                    "text": str(span["text"]),
                                }
                            )
    except Exception:
        return [], []
    return spans, sizes


def source_fingerprint(pdf: Path) -> dict[str, Any]:
    """源文件指纹（SHA-256 + 页数）；读不到时如实记 0/空并在 unresolved 里报。"""
    fingerprint: dict[str, Any] = {"pdfSha256": "", "pageCount": 0}
    try:
        fingerprint["pdfSha256"] = hashlib.sha256(pdf.read_bytes()).hexdigest()
    except OSError:
        pass
    module = _pymupdf()
    if module is not None:
        try:
            with module.open(pdf) as document:
                fingerprint["pageCount"] = len(document)
        except Exception:
            pass
    return fingerprint


def build_layout(
    source_pdf: Path,
    *,
    part_dir: Path | None = None,
    middle_json: Path | None = None,
) -> dict[str, Any]:
    """源 PDF → ``layout.json`` 数据（docs/16 §2.3）。

    ``part_dir`` / ``middle_json`` 是 MinerU 侧（parts 目录、middle.json）的来源，
    供只有 MinerU 几何才有的通道（``columns`` 等）使用；两者都可缺省，缺省即该通道
    记 ``unresolved``，不猜。
    """
    unresolved: list[dict[str, Any]] = []
    text_lines = text_layer_content_lines(source_pdf)
    if not text_lines:
        unresolved.append(
            {
                "channel": "textLines",
                "reason": "源 PDF 文本层无内容行（扫描型或 pymupdf 不可用）",
            }
        )
    frames = vector_frame_rects(source_pdf)
    images = image_rects(source_pdf)
    # 封面兜底的原始文本行（GEN-016 英文标题、GEN-014 发布机构）：pymupdf 的
    # ``page.get_text()`` 逐行、只 strip 去空行——**不含** textLines 的页眉/页脚过滤，
    # 与原读法逐字节一致（判定留在消费端）。
    cover_lines = pdf_page_lines(source_pdf, 0)
    span_items, page_sizes = text_spans(source_pdf)
    if not cover_lines:
        unresolved.append(
            {"channel": "cover.pdfPage0Lines", "reason": "封面页文本层读不到内容行"}
        )
    # 并列版面（GEN-095）的几何侧：MinerU middle.json / parts 分片——不是源 PDF 读数，
    # 但同属「抽取阶段才能拿到的输入」，一并落进本通道，供构建端只读 layout.json。
    geometry_sources = middle_geometry_sources(part_dir, middle_json)
    geometry = parse_middle_geometry(geometry_sources)
    if (part_dir or middle_json) and not geometry_sources:
        unresolved.append(
            {
                "channel": "columns",
                "reason": "指定的 parts 目录 / middle.json 不可读，并列版面几何缺失",
            }
        )
    layout: dict[str, Any] = {
        "schemaVersion": LAYOUT_SCHEMA_VERSION,
        "source": {
            **source_fingerprint(source_pdf),
            "producer": LAYOUT_PRODUCER,
        },
        "textLines": text_lines,
        "ellipsisLines": [
            {"page": line["page"], "x0": line["x0"], "y0": line["y0"], "text": line["text"]}
            for line in text_lines
            if is_short_ellipsis(line["text"])
        ],
        "frames": frames,
        "imageRects": images,
        "cover": {"pdfPage0Lines": cover_lines},
        "pages": page_sizes,
        "textSpans": span_items,
        "columns": [{"page": page, "blocks": geometry[page]} for page in sorted(geometry)],
        "unresolved": unresolved,
    }
    return layout


def write_layout(path: Path, data: dict[str, Any]) -> Path:
    """写 ``layout.json``（UTF-8、稳定键序，便于逐字节 diff）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_layout(path: Path | None) -> dict[str, Any]:
    """读 ``layout.json``；缺失/损坏时返回空 dict（消费端按「无判据」处理，不阻断）。"""
    if path is None:
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}
