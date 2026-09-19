"""MinerU Markdown → CSM 适配（表格/图/公式），全流水线与简单抽取路径共用。

规则对应: GEN-004（资产相对路径重写）、GEN-032/033（表格题注拆分与孤立题注抑制）、
GBT-X06（公式资产绑定）、GBT-B08（表题注）、GBT-X02（合并单元格表达）。

表格合并单元格通用方案（GBT-X02）：
- MinerU 的 HTML 表格携带 ``rowspan``/``colspan``；CSM 无法用 GFM 原生表达合并，
  因此按 CSM 规范（docs/07 §6.4）展开为等宽网格 + 紧跟 ``ssir:table-merge`` 指令：
  - ``colspan`` 展开为 [文本, 空, …] 占位，保持列对齐；
  - ``rowspan`` 在后续行对应列补空占位（防止行错位），并在源单元格上记录
    ``rowspan``；
  - 合并单元格统一输出 ``<!-- ssir:table-merge row=… column=… rowspan=…
    colspan=… -->`` 指令：column 从 1 开始；row 为 0-based 表格行（header-rows=1
    时 row=0 是表头行，数据行从 1 开始）——与 csm_renderer 的坐标一致；
  - MinerU 对 rowspan 行的展开并不一致（常多一个尾部空单元格），若仅单一最长行
    且其超出第二大宽度的尾部全为空，裁剪幻影空位，防网格撑宽。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from .parser import escape_table_cell


def html_table_to_csm(html: str, table_id: str, caption: str | None) -> str:
    """Turn MinerU HTML tables into the constrained CSM table representation.

    规则对应: GBT-B08（题注形如"表X 题名"，编号必备）+ GEN-033（无编号且无题名不输出题注）
    + GBT-X02（合并单元格以展开网格 + ssir:table-merge 指令表达，保持列对齐）。
    """
    soup = BeautifulSoup(_inline_equations_to_csm(html), "html.parser")
    rows: list[list[dict[str, Any]]] = []  # 每格: {text, colspan, rowspan}
    merges: list[dict[str, Any]] = []
    occupied_until: dict[int, int] = {}    # col -> 被上方 rowspan 覆盖到的最后一个行号（含）
    for row_index, tr in enumerate(soup.find_all("tr")):
        row: list[dict[str, Any]] = []
        col = 0
        for cell in tr.find_all(["th", "td"], recursive=False):
            # 被上方 rowspan 覆盖的列在 HTML 行里没有对应 <td>，且空位可能出现在行中
            # **任何**位置（表10 寿命的「运行方式」列在第 2~5 行都由首行 rowspan="5"
            # 覆盖）——因此每个单元格落位前都要按列号跳过被覆盖列、补空占位，否则其后
            # 单元格整体左移、列错位（GBT-X02：展开网格必须保持列对齐）。
            while occupied_until.get(col, -1) >= row_index:
                row.append({"text": "", "colspan": 1, "rowspan": 1})
                col += 1
            # 单元格内嵌图（GBT-X02 表中图）：MinerU 把表单元格里的 <img> 以
            # markdown 图片语法附在单元格文本后（如 表2 锋利度试验区域 的
            # 试验区域分割/插入角度列示意图），随文本一起流转 CSM/SSIR，
            # 渲染端再拆分为单元格内 Image flowable。src 为相对路径
            # （images/<hash>.jpg），末尾统一重写为 assets/images/。
            cell_imgs = [str(img.get("src", "")) for img in cell.find_all("img") if img.get("src")]
            text = " ".join(cell.get_text(" ", strip=True).split())
            text = escape_table_cell(text)
            # GB 表格中"不适用"用一字线 —（U+2014）；OCR 常把它误读为
            # 汉字"一/二"、斜杠"/"、全角减号"－"等。单独成格的这些符号
            # 不可能是合法数据，统一归一为 "—"，保证表格横杠一致（GBT-C17）。
            if text in {"一", "二", "/", "－", "–", "﹣"}:
                text = "—"
            for src in cell_imgs:
                if src:
                    text += f" ![](images/{Path(str(src)).name})"
            colspan = max(int(str(cell.get("colspan", "1"))), 1)
            rowspan = max(int(str(cell.get("rowspan", "1"))), 1)
            row.append({"text": text, "colspan": colspan, "rowspan": rowspan})
            for _ in range(colspan - 1):
                row.append({"text": "", "colspan": 1, "rowspan": 1})
            if rowspan > 1:
                for covered in range(col, col + colspan):
                    occupied_until[covered] = row_index + rowspan - 1
            col += colspan
        if row:
            rows.append(row)
    if not rows:
        return ""
    _restore_table_footnote_markers(rows)
    # MinerU 对 rowspan 行的展开并不一致（常多一个尾部空单元格），会把网格
    # 撑宽一列。若仅单一最长行且其超出第二大宽度的尾部全为空，裁剪幻影空位，
    # 保持网格与表头一致（有内容的行绝不裁剪）。
    widths = sorted({len(row) for row in rows}, reverse=True)
    if len(widths) > 1:
        target = widths[1]
        for row in rows:
            if len(row) > target and all(cell["text"] == "" for cell in row[target:]):
                del row[target:]
    width = max(len(row) for row in rows)
    # 合并单元格统一产 merge 指令：row/column 坐标按 CSM 契约——**绝对** 0-based
    # 表格行（row=0 即第一行，表头行也算在内；数据行的 row = header-rows + 序号 − 1）；
    # column 从 1 开始。rowspan/colspan 钳制到表格实际范围，防止越界破坏渲染。
    for row_index, row in enumerate(rows):
        for col_index, cell in enumerate(row):
            if cell["colspan"] > 1 or cell["rowspan"] > 1:
                merge = {
                    "row": row_index,
                    "column": col_index + 1,
                    "rowspan": min(cell["rowspan"], len(rows) - row_index),
                    "colspan": min(cell["colspan"], width - col_index),
                }
                if merge["rowspan"] > 1 or merge["colspan"] > 1:
                    merges.append(merge)
    # 表头行数（GEN-114）：表头区的垂直跨度 = **首行**起点的最大 rowspan。GB/T 表的
    # 表头常不止一行（「尺寸代号 | 规格代号」+ 各列规格号、「参数名称 | 转速」+ 各转速段、
    # 「机座号 | 基本尺寸及公差带」+ D/D₁/L/L₁ + h7/H7…），MinerU 的 HTML 用 rowspan
    # 表达这一跨度（实测 2~4）。旧实现硬编码 header-rows="1" → 转页接排只重复第一行、
    # 表头底纹也只盖一行。至少保留一行数据行：表头跨度不得吃掉整表，否则
    # repeatRows == 行数、reportlab 认为「切点落在表头内」而永不可分页。
    header_rows = max((max(int(cell.get("rowspan", 1)), 1) for cell in rows[0]), default=1)
    header_rows = max(1, min(header_rows, len(rows) - 1))
    attrs = [f'id="mineru-table-{table_id}"', f'header-rows="{header_rows}"']
    if caption:
        match = re.match(r"^表\s*([^\s]+)(?:\s+(.+))?$", caption.strip())
        if match:
            # Bare "表 N" captions (no title) set only caption-number; the
            # renderer prints the number line, GBT-X02 passes, and the
            # roundtrip keeps the attribute (GEN-033 孤立题注抑制).
            attrs.append(f'caption-number="{match.group(1)}"')
            if match.group(2):
                attrs.append(f'caption="{match.group(2).replace(chr(34), "&quot;")}"')
    lines = [f"<!-- ssir:table {' '.join(attrs)} -->"]
    for index, row in enumerate(rows):
        cells = [cell["text"] for cell in row]
        cells.extend([""] * (width - len(row)))
        lines.append("| " + " | ".join(cells) + " |")
        if index == 0:
            lines.append("| " + " | ".join("---" for _ in cells) + " |")
    for merge in merges:
        lines.append(
            f'<!-- ssir:table-merge table="mineru-table-{table_id}" row="{merge["row"]}" column="{merge["column"]}" '
            f'rowspan="{merge["rowspan"]}" colspan="{merge["colspan"]}" -->'
        )
    return "\n".join(lines)


def _restore_table_footnote_markers(rows: list[list[dict[str, Any]]]) -> None:
    """Restore footnote-reference markers lost by OCR (GBT-C18).

    GB/T 1.1 表脚注：被注释内容后跟上角标字母（如 匝间绝缘ᵃ），表下方以
    "a 说明" 列出。MinerU OCR 常把单元格里的上角标字母丢掉，只留下脚注行
    （"a 匝间绝缘的检验可在部件生产过程中进行。"）。此处把脚注行的标记
    补回"说明文本包含其完整内容"的最长单元格末尾（匝间绝缘 → 匝间绝缘a）；
    找不到匹配单元格时不猜测，保持原样。渲染端把该标记渲染为上角标。
    """
    footnote_line = re.compile(r"^([a-zA-Zａ-ｚＡ-Ｚ\d])[ \u3000]+(.+)$")
    footnotes: list[tuple[int, str, str]] = []
    for row_index, row in enumerate(rows):
        non_empty = [(j, cell) for j, cell in enumerate(row) if cell["text"]]
        if len(non_empty) != 1:
            continue
        match = footnote_line.match(non_empty[0][1]["text"])
        if match:
            footnotes.append((row_index, match.group(1), match.group(2)))
    for footnote_row, marker, text in footnotes:
        best: tuple[str, dict[str, Any]] | None = None
        for row_index, row in enumerate(rows):
            if row_index == footnote_row:
                continue
            for cell in row:
                content = cell["text"]
                if len(content) < 2:
                    continue
                if content in text and (best is None or len(content) > len(best[0])):
                    best = (content, cell)
        if best and not best[1]["text"].endswith(marker):
            best[1]["text"] += marker


def formula_assets_index(source: Path) -> dict[str, list[str]]:
    """Index MinerU equation crops by their normalized display-LaTex text.

    规则对应: GEN-004（公式资产相对路径引用）+ GBT-X06（数学公式另行居中编排）。
    """
    candidates = sorted(source.parent.glob("*_content_list.json"))
    if not candidates:
        return {}
    try:
        entries = json.loads(candidates[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    result: dict[str, list[str]] = {}
    for item in entries:
        if item.get("type") != "equation" or not item.get("img_path"):
            continue
        text = str(item.get("text", "")).strip()
        if text.startswith("$$") and text.endswith("$$"):
            text = text[2:-2].strip()
        key = re.sub(r"\s+", "", text)
        result.setdefault(key, []).append("assets/images/" + Path(str(item["img_path"])).name)
    return result


_PLACEHOLDER_IMAGE_ALT_RE = re.compile(r"^(?:image|img|picture|图片|图像)\d*$", re.IGNORECASE)
# 图片替代文本里已带的图号：整图号「图 N 题名」/「图 A.1 题名」，或分图号「a) Ⅹ型」/「a）Ⅹ型」。
# 用于题注吸附护栏（GEN-113）：题注行的图号与替代文本里的图号不一致时，那是**别的图**的
# 题注，吸附只会把本图题注覆盖掉。
_FIGURE_ALT_NUMBER_RE = re.compile(r"^图\s*([A-Z]?\.?\d+(?:\.\d+)?)")
_SUB_FIGURE_ALT_NUMBER_RE = re.compile(r"^([A-Za-z])[)）]")


def _figure_number_token(alt: str) -> str:
    """图片替代文本里的图号（``1``/``E.4``/分图 ``a``）；没有图号返回空串。"""
    text = alt.strip()
    match = _FIGURE_ALT_NUMBER_RE.match(text)
    if match:
        return match.group(1)
    match = _SUB_FIGURE_ALT_NUMBER_RE.match(text)
    if match:
        return match.group(1)
    return ""
# MinerU HTML 片段里的行内公式标记（内容为 LaTeX）；见 _inline_equations_to_csm（GEN-097）。
_INLINE_EQ_RE = re.compile(r"<eq\b[^>]*>(.*?)</eq>", re.IGNORECASE | re.DOTALL)


def _drop_placeholder_image_alt(line: str) -> str:
    """把 MinerU 的占位替代文本清空：``![image](x)`` → ``![](x)``（GEN-096）。

    规则对应: docs/07 §6.5（图片替代文本必须包含图号和图题——占位串不是题名）
    + GBT-B09（图题注）。只处理整行图片语法且替代文本恰为通用占位串的情况：
    真实题名（``![图 1 接线图](x)``、``![接线图](x)``）与页内其它文本一律不动。
    """
    match = re.match(r"^(\s*)!\[(.*?)\]\((.*)\)(\s*)$", line)
    if not match:
        return line
    indent, alt, target, tail = match.groups()
    if not _PLACEHOLDER_IMAGE_ALT_RE.match(alt.strip()):
        return line
    return f"{indent}![]({target}){tail}"


def _inline_equations_to_csm(markdown: str) -> str:
    """MinerU 的 ``<eq>…</eq>`` 行内公式标记 → CSM 行内公式 ``$…$``（GEN-097）。

    ``<eq>`` 出现在 MinerU 的 HTML 片段里（表格单元格为主，如 表10 寿命的
    ``<eq>\\frac{1}{2}</eq>连续堵转转矩``），内容是 LaTeX。原样保留时表解析会把标签
    当普通文本剥掉、只留裸 LaTeX 源码 → 渲染端不识别、把 ``\\frac{1}{2}`` 印进 PDF。
    统一转成 CSM 的行内公式定界形式（docs/07 §6.6），由既有行内公式通道处理；
    已是 ``$…$`` 的内容不会被重复包装。空公式（``<eq></eq>``）删除。
    """
    def _replace(match: re.Match[str]) -> str:
        latex = " ".join(match.group(1).split())
        return f"${latex}$" if latex else ""

    return _INLINE_EQ_RE.sub(_replace, markdown)


def convert_mineru_markup(raw: str, part_prefix: str, formula_assets: dict[str, list[str]] | None = None, gbt_1_1_quirks: bool = False) -> str:
    """Adapt MinerU HTML tables and relative image paths without altering prose.

    规则对应: GEN-004（资产相对路径重写）、GEN-032/033（表格题注拆分与孤立题注抑制）、
    GBT-X06（公式资产绑定）、GEN-096（占位替代文本 image/img/… 不是图题名，清空）、
    GEN-097（HTML 行内公式 `<eq>` → CSM `$…$`；GBT-X02 展开网格保持列对齐）。
    """
    raw = _inline_equations_to_csm(raw)
    table_index = 0
    output: list[str] = []
    position = 0
    used_caption_numbers: set[str] = set()
    for match in re.finditer(r"<table\b[^>]*>.*?</table>", raw, flags=re.IGNORECASE | re.DOTALL):
        before = raw[position:match.start()]
        output.append(before)
        caption = None
        previous = "".join(output).rstrip().splitlines()
        if previous:
            candidate = previous[-1].strip()
            # Caption forms: "表 N 题名" (numbered with title) or a bare
            # "表 N" line (JB/QB 行业标准常见排版——题注只有编号，题名省略).
            # Both carry the mandatory table number (GBT-B08/GBT-X02), so both
            # must be attached to the following table instead of leaking into
            # the body as an orphan paragraph.
            if re.match(r"^表\s*([A-Z](?:\.\d+)+|[A-Z]?\d+(?:\.\d+)*)(\s+.+)?$", candidate):
                caption = candidate
                # 题注行吸附进表格指令：剥离 output 末尾的题注行（允许其后跟任意换行）。
                output[-1] = re.sub(r"[^\n]+(?=\n*$)", "", output[-1])
        if caption:
            number_match = re.match(r"^表\s*([^\s]+)", caption)
            if number_match:
                used_caption_numbers.add(number_match.group(1))
        else:
            # OCR sometimes drops the bare "表 N" caption line entirely while
            # keeping the in-prose reference ("…应符合表2的规定。").  Infer the
            # number from the closest preceding unused prose reference so the
            # table keeps its mandatory number (GBT-B08 编号必备).  The pattern
            # covers body tables ("表2") and annex tables ("表A.1").
            inferred = re.findall(
                r"表\s*([A-Z](?:\.\d+)+|[A-Z]?\d+(?:\.\d+)*)",
                "".join(output)[-600:],
            )
            for number in reversed(inferred):
                if number not in used_caption_numbers:
                    caption = f"表 {number}"
                    used_caption_numbers.add(number)
                    break
        table_index += 1
        converted = html_table_to_csm(match.group(0), f"{part_prefix}-{table_index:03d}", caption)
        output.append(converted if converted else match.group(0))
        position = match.end()
    output.append(raw[position:])
    converted = "".join(output).replace("](images/", "](assets/images/")
    lines = converted.splitlines()
    cleaned: list[str] = []
    image_pattern = re.compile(r"^!\[(.*?)\]\(([^)]+)\)$")
    figure_caption = re.compile(r"^图\s*([A-Z]?\.?\d+(?:\.\d+)?)\s+(.+)$")
    index = 0
    while index < len(lines):
        image = image_pattern.match(lines[index].strip())
        if not image:
            cleaned.append(lines[index])
            index += 1
            continue
        caption_at = None
        caption_match = None
        # 题注行的图号与图片替代文本里的图号**不一致**时不得吸附：那是别的图的题注，
        # 吸附会把本图已有的题注**覆盖**掉（GB_T_30819-2024 4.1.8 实测：分图 b 的
        # 「b) Ⅱ型」曾被整行图的题注「图3 输入端与波发生器凸轮连接方式」顶掉；
        # GB_T_1.1-2020 附录 E 的「图E.4 封底格式」曾被下一张图的题注顶掉）。
        # 替代文本里没有图号（空 / 占位串 / 只有题名）或图号一致时照旧吸附——后者顺带把
        # 「图1 题名」规范成「图 1 题名」（docs/07 §6.5）。
        alt_number = _figure_number_token(image.group(1))
        for probe in range(index + 1, min(index + 7, len(lines))):
            candidate = figure_caption.match(lines[probe].strip())
            if not candidate:
                continue
            if alt_number and alt_number != candidate.group(1):
                break
            caption_at, caption_match = probe, candidate
            break
        if caption_match:
            assert caption_at is not None
            label = f"图 {caption_match.group(1)} {caption_match.group(2)}"
            cleaned.append(f"![{label}]({image.group(2)})")
            cleaned.extend(lines[index + 1:caption_at])
            index = caption_at + 1
        else:
            # GEN-096：MinerU（云端 markdown）对没有题注的插图一律写占位替代文本
            # （`![image](…)`/`![image1](…)`）。按 docs/07 §6.5，图片替代文本必须
            # 包含图号和图题——占位串不是题名，若原样进 CSM 渲染端会印出「图 image」。
            # 此处只把它清成空替代文本（图片块与资产引用保持不变），真实题名不动。
            cleaned.append(_drop_placeholder_image_alt(lines[index]))
            index += 1
    converted = "\n".join(cleaned)
    if gbt_1_1_quirks:
        # GB/T 1.1-2020 appendix E only: MinerU omitted the E.11 raster and
        # misidentified its index-layout image as a table directly after 图 E.10.
        # Do not render that unrelated table under the E.10 caption.
        converted = re.sub(
            r"\n<!-- ssir:table id=\"mineru-table-p055-001\".*?\n图\s*E\.11\s+索引格式\n\n单位为毫米\n",
            "\n> [待复核：MinerU 将图 E.11 索引格式误识别为表格，未提取可渲染的图像资产]\n",
            converted,
            flags=re.DOTALL,
        )
    formula_assets = formula_assets or {}
    formula_index = 0

    def bind_formula(match: re.Match[str]) -> str:
        nonlocal formula_index
        expression = match.group(1).strip()
        candidates = formula_assets.get(re.sub(r"\s+", "", expression), [])
        if not candidates:
            return match.group(0)
        asset = candidates.pop(0)
        formula_index += 1
        identifier = f"{part_prefix}-{formula_index:03d}"
        return f'<!-- ssir:formula id="mineru-formula-{identifier}" asset-ref="{asset}" -->\n{match.group(0)}'

    return re.sub(r"\$\$\s*\n(.*?)\n\$\$", bind_formula, converted, flags=re.DOTALL)
