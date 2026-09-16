"""MinerU ``middle.json``（版面中间产物）→ CSM raw Markdown 适配器。

用途：把 MinerU 的 ``*_middle.json``（``pdf_info`` 分页版面结构：标题/正文/表格/图/
公式块 + bbox）确定性翻译成与 MinerU 自带 markdown 同形的 raw CSM Markdown，交给
既有下游（``leleby_ssir.mineru_html.convert_mineru_markup`` → normalize → parse →
SSIR → 渲染）处理。JSON 里比 markdown 多的信息（版面块类型、行列合并、公式资产）在
这一层用完即止，产物仍是同一套 raw/canonical/SSIR 阶段文件，不新增表示法。

映射规则（对任何 ``middle.json`` 成立，不针对某份文档）：

- ``para_blocks`` 按页序、块序输出；``discarded_blocks``（``header``/``footer``/
  ``page_number``）是页眉页脚页码，整块丢弃（与 MinerU 自带 markdown 一致）；
- ``title`` → ``#`` × level（1~6 钳制）标题行（MinerU 的 level 语义：1 = 封面横幅/
  文件名称，2 = 其余标题；章节层级由 parser 的编号修复族按编号重排）；
- ``text`` → 段落（块内可视行按 CJK 规则拼接：汉字侧不补空格，拉丁词边界补一个空格；
  ``merge_prev`` 为真时并入前一段落——MinerU 跨栏/跨页切断的同一段）；
- 文本 ``span``：``type=text`` 取 ``content``；``inline_equation`` → ``$LaTeX$``；
  ``image`` → ``![](path)``；``table`` → 内嵌 HTML 表格原文；
- ``table`` 块 → 先 ``table_caption`` 内层块文本（``表 N 题名``，供下游按「题注吸附」
  规则绑到表格），再 ``table_body`` 的 ``<table>…</table>`` HTML（行列合并、
  ``<eq>`` 行内公式由下游 ``html_table_to_csm``/GEN-097 处理）；``table_footnote``
  内层块排在表后。``table_body`` 无 HTML 但带 ``image_path`` 时按表格图输出
  （``![表 N 题名](path)``）；两者都无 → 如实回报为抽取局限（不编造表格内容）；
- ``image`` 块 → ``![图 N 题名](path)`` 图片行（``image_caption`` 直接写进替代文本——
  MinerU 已把题注绑在该图上；CSM docs/07 §6.5 规定替代文本 = 图号 + 图题）
  + ``image_footnote`` 行；``chart`` 块同处理（MinerU 把版式示意图整块栅格化成一张图，
  内层块名 ``chart_*`` 与前缀无关，按后缀取 body/caption/footnote）；
- ``ref_text`` / ``index`` / ``list`` 块 → 每行一条记录（参考文献条目 / 目次与索引条目 /
  列项），不做段落内拼接——这些块的 ``lines[]`` 是记录边界，粘成一段会丢条目结构；
- ``interline_equation`` 块 → ``$$`` 公式块（LaTeX 取 ``content``/``latex``）；
  无 LaTeX 但有 ``image_path`` 时按公式图输出；
- 其它/未知块类型：不猜测，跳过并记入 ``warnings`` 回报。

规则对应: GEN-002（来源登记）、GEN-004（资产路径）、GEN-030（附录标题）、
GEN-032/033（表格题注吸附/孤立题注抑制）、GEN-096/097（占位替代文本与行内公式）、
GEN-099（ref_text/index/list 记录行块全收录）、GEN-100（chart 图块与图类内层块按部件族处理）、
GBT-X02（合并单元格展开网格）、GBT-X06（公式资产绑定）。
"""

from __future__ import annotations

import re
from typing import Any

_MAX_HEADING_LEVEL = 6
# 封面分类号（页眉）：ICS 按「行内出现」取值（本地路线写成 `ICS01.120`，无空格）；
# CCS 代号取独立词元——前不接字母/数字/斜杠/点、后不接数字，避免把 `GB/T 20001.5—2017`
# 的 `T 20001` 或页眉里的 `GB` 误当分类号。
_ICS_INLINE_RE = re.compile(r"ICS\s*[:：]?\s*([0-9]+(?:\.[0-9]+)*)", re.IGNORECASE)
_CCS_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9/.])(?:CCS\s*[:：]?\s*)?([A-Z])\s?([0-9]{1,3})(?:\.([0-9]+))?(?![0-9])",
    re.IGNORECASE,
)
# CJK 字符（含中日韩标点与全角区）：公式 LaTeX 里出现即无法用 MathText 现场排版。
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3000-\u303f\u3040-\u30ff\uff00-\uffef]")


def _has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


class MiddleJsonError(ValueError):
    """``middle.json`` 结构不可用时抛出（缺 ``pdf_info`` 等）。"""


def _latex_of(span: dict[str, Any]) -> str:
    return str(span.get("content") or span.get("latex") or span.get("text") or "").strip()


def _span_markdown(span: dict[str, Any], warnings: list[str]) -> str:
    """单个 span → Markdown 片段（文本 / 行内公式 / 图 / 内嵌表格 HTML）。"""
    kind = str(span.get("type") or "").lower()
    if kind in ("text", ""):
        return str(span.get("content") or "")
    if kind in ("inline_equation", "equation", "interline_equation"):
        latex = _latex_of(span)
        if latex:
            return f"${latex}$"
        path = str(span.get("image_path") or "")
        return f"![]({path})" if path else ""
    if kind in ("image", "chart"):
        # ``chart``：MinerU 把「版式示意图」整块栅格化成一张图（如 GB/T 1.1-2020 图 E.8
        # 目次格式），span 内容为空、只有 image_path——与 image span 同处理。
        path = str(span.get("image_path") or "")
        if not path:
            warnings.append(f"{kind} span without image_path skipped")
            return ""
        return f"![]({path})"
    if kind == "table":
        html = str(span.get("html") or "").strip()
        if html:
            return html
        path = str(span.get("image_path") or "")
        return f"![]({path})" if path else ""
    warnings.append(f"unsupported span type skipped: {kind or '<empty>'}")
    return ""


def _line_rows(line: dict[str, Any], warnings: list[str]) -> list[str]:
    """单个可视行 → 行文本列表（行内 span 连续拼接，span 内容里的 ``\\n`` 是行分隔）。"""
    rows: list[str] = [""]
    for span in line.get("spans") or []:
        if not isinstance(span, dict):
            continue
        for index, piece in enumerate(_span_markdown(span, warnings).split("\n")):
            if index:
                rows.append("")
            if rows[-1] and piece:
                rows[-1] = _append_fragment(rows[-1], piece)
            else:
                rows[-1] += piece
    return rows


def _block_lines(block: dict[str, Any], warnings: list[str]) -> list[str]:
    """块 → 输出行列表（与 MinerU 自带 markdown 同形）。

    三条边界规则（与 MinerU markdown writer 实测一致）：

    - ``lines[]`` 之间是**同一段**的可视换行 → 直接拼接（不产生新行）；
    - span 内容里的单个 ``\\n`` 是**行分隔**（目录块整块 16 行就靠它，见 GB_T_20001.6-2017）；
    - span 内容里的空行（``\\n\\n``）是**段落分隔**（输出空行，如 6.3.3 与 6.3.4 之间）。

    行内不加分隔符（同一可视行的 span 是连续文本），跨行拼接时才按 CJK 规则决定是否
    补空格（见 ``_append_fragment``）；空字符串行表示段落分隔。
    """
    rows: list[str] = [""]
    for line in block.get("lines") or []:
        if not isinstance(line, dict):
            continue
        for index, piece in enumerate(_line_rows(line, warnings)):
            if index:
                rows.append("")
            if rows[-1] and piece:
                rows[-1] = _append_fragment(rows[-1], piece)
            else:
                rows[-1] += piece
    while rows and not rows[-1].strip():
        rows.pop()
    return rows or [""]


def _lines_text(block: dict[str, Any], warnings: list[str]) -> str:
    """块 → 文本（行间以换行相连；段落分隔保留为空行）。"""
    return "\n".join(_block_lines(block, warnings))


def _append_fragment(text: str, fragment: str) -> str:
    """同一段落的两个可视行拼接：拉丁词边界补一个空格，汉字侧不补（CJK 无词间空格）。"""
    if not text:
        return fragment
    if not fragment:
        return text
    left, right = text[-1], fragment[0]
    joiner = " " if (left.isascii() and left.isalnum() and right.isascii() and right.isalnum()) else ""
    return f"{text}{joiner}{fragment}"


def _block_title(block: dict[str, Any], warnings: list[str]) -> str:
    level = block.get("level")
    depth = int(level) if isinstance(level, (int, str)) and str(level).strip().isdigit() else 1
    depth = min(max(depth, 1), _MAX_HEADING_LEVEL)
    text = _lines_text(block, warnings).strip()
    return f"{'#' * depth} {text}" if text else ""


def _inner_blocks(block: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in (block.get("blocks") or []) if isinstance(item, dict)]


def _table_markdown(block: dict[str, Any], warnings: list[str]) -> str:
    """``table`` 块 → 题注行 + 表格 HTML/表格图 + 表后注（与 MinerU markdown 同序）。"""
    caption = ""
    body = ""
    footnotes: list[str] = []
    for inner in _inner_blocks(block):
        kind = str(inner.get("type") or "")
        if kind == "table_caption":
            caption = _lines_text(inner, warnings).strip() or caption
        elif kind == "table_body":
            body = _lines_text(inner, warnings).strip()
        elif kind == "table_footnote":
            text = _lines_text(inner, warnings).strip()
            if text:
                footnotes.append(text)
    parts: list[str] = []
    if caption:
        parts.append(caption)
    if body:
        parts.append(body)
    elif caption:
        warnings.append(f"table body missing in middle.json (caption kept, structure reported): {caption[:40]}")
        parts.append(f"> [{caption}（表格结构未识别，原始抽取未提供表格正文）]")
    else:
        warnings.append("table block without caption and without body skipped")
    parts.extend(footnotes)
    return "\n\n".join(parts)


def _figure_inner_role(kind: str) -> str:
    """图类内层块名 → 版式部件（``body``/``caption``/``footnote``）。

    MinerU 只用后缀区分「图」的两族内层块：``image_*``（照片/截图类）与 ``chart_*``
    （整块栅格化的版式示意图，如 GB/T 1.1-2020 图 E.8 目次格式）。二者在 CSM 里都是
    「图」，故按后缀取部件，不再逐个列举块名。
    """
    lowered = kind.lower()
    for role in ("body", "caption", "footnote"):
        if lowered.endswith("_" + role):
            return role
    return ""


def _figure_markdown(block: dict[str, Any], warnings: list[str]) -> str:
    """``image``/``chart`` 块 → 图片行（题注写进替代文本）+ 图片脚注行。

    MinerU 的 ``image_caption`` 内层块**已经**绑定在该图上（如 p10 的流程图 + 题注），
    因此直接把题注写进替代文本——CSM 规定图片替代文本 = 图号 + 图题（docs/07 §6.5），
    这也是下游 ``convert_mineru_markup`` 对「图片后紧跟题注行」的归一结果。写成尾部
    独立题注行会让下游的「图片后 6 行内吸附」规则把题注抢给**前一**张图（GB_T_20001.6-2017
    附录 A 的两张连续图片实测如此）。``image_footnote`` 排在图片之后。
    块内多张图时题注给最后一张（MinerU 把题注绑在整块上）。
    """
    images: list[str] = []
    captions: list[str] = []
    footnotes: list[str] = []
    for inner in _inner_blocks(block):
        role = _figure_inner_role(str(inner.get("type") or ""))
        text = _lines_text(inner, warnings).strip()
        if role == "body":
            if text:
                images.append(text)
        elif role == "caption" and text:
            captions.append(text)
        elif role == "footnote" and text:
            footnotes.append(text)
    if not images:
        warnings.append("figure block without figure body skipped")
        return "\n\n".join(captions + footnotes)
    if captions:
        match = re.match(r"^!\[(.*?)\]\((.*)\)$", images[-1])
        if match:
            images[-1] = f"![{captions[0]}]({match.group(2)})"
        else:  # 形态意外（非图片行）时退回尾部题注行，不吞掉题注
            images.extend(captions)
            warnings.append("image caption kept as a trailing line (unexpected image shape)")
    return "\n\n".join(images + footnotes)


def _rows_markdown(block: dict[str, Any], warnings: list[str]) -> str:
    """``ref_text``/``index``/``list`` 块 → 每行一条（行即记录，跨行不拼接、不粘连）。

    这三族块的 ``lines[]`` 是**记录**而不是同一段文字的折行：``ref_text`` 一行一条参考
    文献（``[1] GB/T 1182 …``，GB/T 1.1-2020 共 18 条）、``index`` 一行一条目次/索引条
    目、``list`` 一行一项。若走 ``_lines_text`` 的「同段折行直接拼接」规则，整块会被粘
    成一段（``[1] …[2] …``）、条目边界全丢——raw 起点路线据此丢失参考文献与索引。
    行内仍按 span 顺序拼接（``_line_rows``），故行内公式/图/表格 HTML 与段落一致。
    """
    rows: list[str] = []
    for line in block.get("lines") or []:
        if not isinstance(line, dict):
            continue
        rows.extend(row.strip() for row in _line_rows(line, warnings) if row.strip())
    if not rows:
        warnings.append("row block without text skipped")
    return "\n".join(rows)


def _equation_markdown(block: dict[str, Any], warnings: list[str]) -> str:
    """``interline_equation`` 块 → ``$$`` 公式块（或公式图）。

    块内 span 可能同时带 LaTeX 与裁剪图（两条抽取路线都如此）。**LaTeX 含 CJK 时改用图
    资产**：渲染端现场排版走 matplotlib MathText，数学字体没有汉字字形，汉字会被替换成
    假字形——GB/T 20001.5-2017 示例1 的「综合差错率」实测印成一串方框（GEN-102，与
    merge 阶段对含中文公式一律保留 asset-ref 的裁定同源）。此时仍写成 **formula 块**
    （``<!-- ssir:formula asset-ref=… -->`` + ``$$LaTeX$$``），保住公式语义与 LaTeX 原文：
    渲染端对带 assetRef 的公式优先画图（``pdf_renderer``），公式编号/「式中」引用/
    合规检查照旧按公式处理。其余情况仍优先 LaTeX（更清晰、可检索）。
    """
    latex = ""
    asset = ""
    for line in block.get("lines") or []:
        for span in line.get("spans") or []:
            latex = _latex_of(span) or latex
            asset = str(span.get("image_path") or "") or asset
    if latex and asset and _has_cjk(latex):
        return f'<!-- ssir:formula asset-ref="{asset}" -->\n\n$$\n{latex}\n$$'
    if latex:
        return f"$$\n{latex}\n$$"
    if asset:
        return f"![]({asset})"
    warnings.append("interline_equation block without latex or image skipped")
    return ""


def _block_markdown(block: dict[str, Any], warnings: list[str]) -> str:
    kind = str(block.get("type") or "").lower()
    if kind == "title":
        return _block_title(block, warnings)
    if kind == "text":
        return _lines_text(block, warnings).strip()
    if kind == "table":
        return _table_markdown(block, warnings)
    if kind in ("image", "chart"):
        return _figure_markdown(block, warnings)
    if kind in ("ref_text", "index", "list"):
        # 一行一条记录的块（参考文献 / 目次与索引 / 列项）——见 _rows_markdown。
        return _rows_markdown(block, warnings)
    if kind in ("interline_equation", "equation"):
        return _equation_markdown(block, warnings)
    warnings.append(f"unsupported block type skipped: {kind or '<empty>'}")
    return ""


def _line_texts(block: dict[str, Any]) -> list[str]:
    """块内每个可视行一条文本（不跨行拼接——页眉/页脚的 ICS 与 CCS 各占一行）。"""
    return [row.strip() for row in _block_lines(block, []) if row.strip()]


def _discarded_text_lines(page: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for block in page.get("discarded_blocks") or []:
        if not isinstance(block, dict):
            continue
        lines.extend(_line_texts(block))
    return lines


def image_source_sizes(data: dict[str, Any]) -> dict[str, tuple[float, float]]:
    """middle.json 图片图块的版面尺寸（pt）：资产文件名 → ``(宽, 高)``。

    MinerU 的块 ``bbox`` 与源 PDF 同一坐标系（pt），与
    ``mineru_full_standard._stamp_figure_source_sizes`` 从源 PDF 图元矩形取到的尺寸同量级：
    GB_T_20001.6-2017 附录 A 实测 259.0×365.0 与 251.0×198.0（源 PDF 图元矩形为
    271.6×361.4 与 253.2×197.6，偏差 0.2%~5%——块区域含少量留白）。因此 raw 起点
    （middle.json 输入、没有源 PDF）可以据此还原原图尺寸（GEN-098），不必依赖
    `corpus/golden` 的 PDF；裁剪图与图块一一对应，也不需要源 PDF 路径那套宽高比模糊匹配。
    两者都在场时以源 PDF 为准（更贴近真实图元）。

    键取 ``image_path`` 的文件名（远程下载/本地落地后的资产名同源，忽略查询串）。
    与 PDF 路径同样的保守过滤：宽或高 < 10pt 的图块（装饰/图标）、首页高度 < 100pt
    的图块（封面徽标）不参与。
    """
    sizes: dict[str, tuple[float, float]] = {}
    for page_index, page in enumerate(data.get("pdf_info") or []):
        if not isinstance(page, dict):
            continue
        # 页序以块自带的 ``page_idx`` 为准（列表顺序只是枚举顺序）；
        # 封面徽标过滤需要真实页号。
        page_number = page.get("page_idx")
        page_number = page_index if not isinstance(page_number, int) else page_number
        for block in page.get("para_blocks") or []:
            if not isinstance(block, dict) or str(block.get("type") or "") not in ("image", "chart"):
                continue
            bbox = block.get("bbox")
            if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                continue
            try:
                width = float(bbox[2]) - float(bbox[0])
                height = float(bbox[3]) - float(bbox[1])
            except (TypeError, ValueError):
                continue
            if width < 10 or height < 10 or (page_number == 0 and height < 100):
                continue
            for inner in _inner_blocks(block):
                if _figure_inner_role(str(inner.get("type") or "")) != "body":
                    continue
                for line in inner.get("lines") or []:
                    if not isinstance(line, dict):
                        continue
                    for span in line.get("spans") or []:
                        if not isinstance(span, dict):
                            continue
                        name = _asset_name(str(span.get("image_path") or ""))
                        if name:
                            sizes[name] = (round(width, 1), round(height, 1))
    return sizes


def _asset_name(image_path: str) -> str:
    """图片引用 → 资产文件名（去查询串/片段，与下载落地后的名字一致）。"""
    if not image_path:
        return ""
    return image_path.split("?", 1)[0].split("#", 1)[0].rstrip("/").rsplit("/", 1)[-1]


def _classification_hints(line: str) -> tuple[str, str]:
    """分类号行 → ``(ICS 号, CCS 代号)``；两号可能同处一行。

    两条路线的页眉形态不同：云端把 ``ICS 01.120`` 与 ``A 00`` 放在**两行**，本地路线
    放在**一行**且 ICS 与号码之间没有空格（实测 ``ICS01.120 A 00``）。因此 ICS 按
    「行内出现」取值，取出后从行里剔除，再在同一行残余里找 CCS 代号；CCS 代号必须是
    独立词元（前不接字母/数字/斜杠/点、后不接数字），以免把 ``GB/T 20001.5—2017``
    的 ``T 20001`` 或页眉里的 ``GB`` 当成分类号。
    """
    text = line.strip()
    match = _ICS_INLINE_RE.search(text)
    ics = match.group(1) if match else ""
    if match:
        text = f"{text[:match.start()]} {text[match.end():]}"
    token = _CCS_TOKEN_RE.search(text)
    ccs = ""
    if token:
        letter, number, fraction = token.group(1), token.group(2), token.group(3)
        ccs = f"{letter.upper()} {number}" + (f".{fraction}" if fraction else "")
    return ics, ccs


def cover_hints(data: dict[str, Any]) -> dict[str, str]:
    """首页页眉/页脚（``discarded_blocks``）里的封面字段。

    MinerU 把封面的分类号与发布机构放进首页页眉/页脚：页眉形如 ``ICS 01.120`` 加
    单独一行的 CCS 代号，页脚形如 ``<机构A> 发布`` 加 ``<机构B>``。CCS 行有两种
    写法——本地路线裸写（``A 00``），云端路线带前缀（``CCS A 00``）——两种都收；
    ICS 与 CCS 同处一行（``ICS01.120 A 00``）也能分开取值（见 ``_classification_hints``）；
    同一页眉里还有 ``GB`` 这类标准代号，按「字母 + 数字」且独立词元的形态排除。
    这些行不在 ``para_blocks`` 正文里，故单独从 ``discarded_blocks`` 恢复；机构行也可能
    落在正文封面块里（云端路线实测），那条路径由 ``tools/build_ssir.py:_cover_metadata``
    兜住——与 merge 阶段用 content_list/源 PDF 恢复封面字段同一目的（GEN-014、GBT-C01）。

    返回键：``ics``/``ccs``（分类号原文）与 ``issuer-text``（发布机构行原文，
    规范机构名由调用方按 ``_ISSUER_FRAGMENTS`` 名录解析，见 tools/build_ssir.py）；
    取不到的键不写入（不猜测，AGENTS.md §0.3）。
    """
    if not isinstance(data, dict) or not isinstance(data.get("pdf_info"), list):
        raise MiddleJsonError("middle.json 缺少 pdf_info 数组（不是 MinerU middle.json？）")
    pages = [page for page in data["pdf_info"] if isinstance(page, dict)]
    if not pages:
        return {}
    lines = _discarded_text_lines(pages[0])
    hints: dict[str, str] = {}
    for line in lines:
        ics, ccs = _classification_hints(line)
        if ics and "ics" not in hints:
            hints["ics"] = ics
        if ccs and "ccs" not in hints:
            hints["ccs"] = ccs
    for index, line in enumerate(lines):
        if "发布" not in line or re.match(r"^\d{4}-\d{2}-\d{2}", line):
            continue
        parts = [line]
        following = index + 1
        while following < len(lines):
            candidate = lines[following]
            compact = re.sub(r"\s+", "", candidate)
            if not compact or re.search(r"发布|实施|^\d", compact) or "ICS" in compact.upper():
                break
            parts.append(candidate)
            following += 1
        hints["issuer-text"] = "".join(re.sub(r"\s+", "", part) for part in parts)
        break
    return hints


def middle_json_to_csm_markdown(data: dict[str, Any]) -> tuple[str, list[str]]:
    """``middle.json`` → (raw CSM Markdown 正文, 警告列表)。

    返回的正文不含 YAML front matter（由调用方按封面区推导补齐，见
    ``tools/build_ssir.py``）；警告列表如实回报被跳过的块/字段（不编造内容）。
    """
    if not isinstance(data, dict) or not isinstance(data.get("pdf_info"), list):
        raise MiddleJsonError("middle.json 缺少 pdf_info 数组（不是 MinerU middle.json？）")
    warnings: list[str] = []
    paragraphs: list[str] = []
    for page in data["pdf_info"]:
        if not isinstance(page, dict):
            continue
        for block in page.get("para_blocks") or []:
            if not isinstance(block, dict):
                continue
            markdown = _block_markdown(block, warnings)
            if not markdown:
                continue
            if block.get("type") == "text" and block.get("merge_prev") and paragraphs:
                merged = _append_fragment(paragraphs[-1], markdown)
                if merged != paragraphs[-1]:
                    paragraphs[-1] = merged
                    continue
            paragraphs.append(markdown)
    return "\n\n".join(paragraphs).strip() + "\n", warnings
