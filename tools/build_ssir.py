#!/usr/bin/env python3
"""raw 起点流水线：以**已有的 raw 输入**为输入，跑完 normalize → SSIR → 渲染。

支持两种输入形态（``_read_raw_source`` 按后缀分派）：
- ``*.md``：raw CSM Markdown（云端 MinerU 合并结果或人工整理稿），原样进入下游；
- ``*.json``：MinerU ``middle.json``（版面中间产物）——先由 ``leleby_ssir.mineru_middle``
  的 ``middle_json_to_csm_markdown`` 翻成与 MinerU markdown 同形的 raw
  （标题层级/段落拼接/表格行列合并/图片与公式），再走完全相同的下游。

用途（新程序，尽量复用 tools/mineru_full_standard.py 的既有函数）：当原始文档的
MinerU 抽取稿已经存在（例如仓库根 ``rawFile/<ID>.md``：云端 MinerU 合并结果或人工
整理的抽取稿），无需再跑一次 OCR/分块抽取，直接从其下游继续：

    raw.md
      →（封面标题归位 + 补最小合法 front matter + 远程图落地）
      → normalize → 02_canonical/<ID>.canonical.md
      →（源 PDF 存在时）条文脚注回收（CSM-OCR-014）+ 版面印记（示例框样式/图源尺寸/并列版面）
      → parse → 03_ssir/<ID>.ssir.json
      → render（04_render/render.pdf）→ manifest.json
      →（仅 --verify 时另起进程）tools/verify_conversion.py：标准 markdown 投影
        （04_render/render.md）+ 合规/质量报告（05_verify/*.json）+ 可选 PDF 对比

输入形态（按后缀分派）：``<ID>`` 或 ``*.raw.md``（raw 起点）、``*.json``（MinerU
middle.json 先翻成同形 raw）、``*.canonical.md`` 或文档根目录（**人工编辑后的权威基线**：
跳过 normalize，只重跑 parse 之后的阶段，canonical 不被写回）。

验证（投影 + 合规报告 + PDF 对比）**不属于构建流程**：默认不跑；需要时单独运行
``tools/verify_conversion.py``，或加 ``--verify`` 让本程序按显式要求把它调起来（另起进程）。

与既有工具的关系：
- ``mineru_full_standard.py``：从**源 PDF/Word** 开始，本工具替代其 extract/merge 两个
  阶段（抽取与合并），其余阶段全部复用同一批函数；
- ``reprocess_canonical.py``：从**curated canonical** 开始（跳过 normalize），本工具比它
  多一个 normalize 阶段（raw → canonical 由本工具生成）。

复用关系（不重复实现）：
- ``mineru_full_standard._stage_paths / _log / _write_json / _load_json /
  _write_manifest``：阶段目录与产物命名（naming_specification.txt §4/§6）；
- ``mineru_full_standard._recover_annex_headings / _demote_banner_fragments /
  _demote_cover_headings``：封面横幅与附录标题归位（与 merge 阶段同一套规则，
  GBT-L03/GBT-C01/GEN-030）；
- ``mineru_full_standard._is_cover_banner / _is_cover_banner_fragment /
  _usable_title / _normalize_part_title``：标题推导（与 merge 同规，GBT-C01）；
- ``mineru_full_standard.finalize``：normalize → 条文脚注回收（CSM-OCR-014，仅 PDF 源）
  → parse → 版面印记（GEN-095 等）；
- ``leleby_ssir.mineru_html.convert_mineru_markup``：MinerU 标记 → CSM（HTML 表格 →
  ``ssir:table`` 指令、资产路径与图题注归一、公式资产绑定、占位替代文本清空，
  GEN-004/032/033/096 + GBT-X06）——merge 阶段对每个分片用的同一套转换；
- ``leleby_ssir.pipeline._post_parse_verify_render``：render（PDF）→ manifest 公共尾部
  （render=GEN-070—076）；验证（投影 + 合规报告 + PDF 对比）已独立成 ``tools/verify_conversion.py``
  （verify=GEN-051/090/091），构建流程默认不做验证；
- ``mineru_full_standard._run_from_existing_canonical``：已存在 curated canonical 时
  改为下游续跑——**绝不重跑 normalize 覆盖人工编辑的 canonical**（AGENTS.md §2）。

本文件新增的通用步骤（对任何「裸 raw」都成立，不是针对某份文档的特判）：
1. ``_adapt_mineru_markup``：raw 里的 MinerU 标记先按 merge 的同一套转换落成 CSM——
   ``<table>`` HTML → ``ssir:table`` 指令（含题注吸附/编号推导）、``images/`` 路径 →
   ``assets/images/``、占位替代文本（``![image](…)``）清空、公式资产绑定；该转换
   幂等，已是 CSM 的历史 raw 不会因此改变；
2. ``_cover_metadata``：从封面区正则恢复 front matter 字段（代替标准、发布/实施日期、
   英文译名、ICS/CCS 编码）——取不到就留空，不猜测、不填补（AGENTS.md §0.3）；
3. ``_build_front_matter``：为不带 YAML front matter 的裸 raw 补最小合法 front matter
   （csm-version / document-type / document-identifier / standard-number / title /
   language / source / extraction-backend，与 merge 写出的键一致）；
4. ``_rewrite_front_matter``：既有 front matter 上按 `--standard-number` / `--title` /
   `--front-matter-json` 覆盖**顶层**键（显式值优先，不解析 YAML、不动其它行）；
5. ``_materialize_remote_images``：把 raw 里的远程图片链接（云端 MinerU 的
   ``https://cdn-mineru...``）下载到 ``assets/images/`` 并改写为相对链接，与 merge
   拷贝 MinerU 本地图片的落盘约定一致；下载失败保持原链接并回报（不伪造资产）。

用法：
    # 裸 ID：先找 out/mineru/<ID>/01_extract/<ID>.raw.md，再找 rawFile/<ID>.md 或 .json
    .venv/bin/python tools/build_ssir.py GB_T_10401-2023 \\
        --source-pdf corpus/golden/GB_T_10401-2023_bak.pdf

    # 显式路径 + 元数据覆盖
    .venv/bin/python tools/build_ssir.py rawFile/GB_T_10401-2023.md \\
        --front-matter-json cover.json --toc-depth all

    # MinerU middle.json（版面中间产物）：先翻成同形 raw，再走完全相同的下游
    .venv/bin/python tools/build_ssir.py rawFile/GB_T_20001.6-2017.json

    # 只看 normalize+parse，不渲染
    .venv/bin/python tools/build_ssir.py rawFile/GB_T_10401-2023.md --no-render

退出码：0 成功；2 失败（normalize/parse/render 任一阶段失败）。
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
for _path in (str(TOOLS), str(ROOT / "src")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# 复用全流程工具的阶段路径 / 元数据推导 / normalize+parse / 版面印记 / 尾部
# render + render.md 投影 + manifest（同仓库内稳定私有接口，见模块 docstring）。
from leleby_ssir.mineru_html import convert_mineru_markup
from leleby_ssir.mineru_middle import (
    MiddleJsonError,
    cover_hints as middle_json_cover_hints,
    image_source_sizes as middle_json_image_sizes,
    middle_json_to_csm_markdown,
)

import mineru_full_standard as mfs  # noqa: E402

_FRONT_MATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?", re.DOTALL)
_REMOTE_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(\s*(https?://[^)\s]+)\s*\)")
# 指令形态的远端资产：`<!-- ssir:formula asset-ref="https://…" -->`（GEN-102 的含中文公式改走图资产）。
_REMOTE_ASSET_REF_RE = re.compile(r'(asset-ref=")(https?://[^"\s]+)(")')
_ENGLISH_TITLE_RE = re.compile(r"[A-Za-z][A-Za-z0-9 ,.:;()'’/\\—-]+")
# 封面区字段（仅在封面块内匹配，避免正文里的同名句子被误用）；行首允许残留的
# H1 标记（# …）——裸 raw 的封面行常被 MinerU 提升为标题。
_REPLACES_RE = re.compile(r"^#?\s*代替\s*[:：]?\s*([A-Za-z][^\n]{2,60})$", re.MULTILINE)
_PUBLICATION_DATE_RE = re.compile(r"(\d{4})\s*[-—–.]\s*(\d{1,2})\s*[-—–.]\s*(\d{1,2})\s*发\s*布")
_EFFECTIVE_DATE_RE = re.compile(r"(\d{4})\s*[-—–.]\s*(\d{1,2})\s*[-—–.]\s*(\d{1,2})\s*实\s*施")
_ICS_RE = re.compile(r"^#?\s*ICS\s*[:：]?\s*([\d.]+)\s*$", re.MULTILINE)
_CCS_RE = re.compile(r"^#?\s*CCS\s*[:：]?\s*([A-Z]\s?\d+(?:\.\d+)?)\s*$", re.MULTILINE)
# front matter 字段顺序（与 merge 写出的一致）；显式 --front-matter-json 可补其它键。
_COVER_KEYS = ("replaces", "title-en", "conformity-statement", "publication-date", "effective-date", "issuer", "ics", "ccs")
# 表格 id 前缀：CSM 表格指令 id 形如 mineru-table-<prefix>-<NNN>（与 merge 的 p### 同族，
# 只是该文档不经分片合并，用固定前缀保证同一 raw 多次运行的 id 稳定）。
_RAW_PART_PREFIX = "raw"


def _split_front_matter(text: str) -> tuple[str | None, str]:
    """Return (front-matter text without the ``---`` fences, body); (None, text) when absent."""
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        return None, text
    return match.group(1), text[match.end():]


def _cover_block(body: str) -> str:
    """封面块：文首到第一个二级标题（目次/前言/第 1 章）之前的内容。"""
    head, sep, _tail = body.partition("\n## ")
    return head if sep else body[:4000]


def _date(match: re.Match[str] | None) -> str:
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _join_english_title(lines: list[str]) -> str:
    """英文译名折行拼接：行尾破折号是标题内部的分隔符（排版换行），接下一行时去掉。

    云端路线把封面英文标题拆成两个块（``Directives for standardization—`` /
    ``Part 1: Rules for …``），本地路线合成一行；两种形态都要还原成同一个标题
    （GBT-C01 的英文译名是**整条**标题，不是某一行）。
    """
    pieces = [re.sub(r"[—–-]+$", "", line.strip()).strip() for line in lines]
    return " ".join(piece for piece in pieces if piece)


def _issuer_from_cover(lines: list[str]) -> str:
    """封面区发布机构行 → 规范机构名（``国家市场监督管理总局 国家标准化管理委员会``）。

    「<机构A> 发布」行加紧随其后的机构名行（云端路线把两行放进同一个正文块，本地路线
    放在页脚里——页脚那份由 ``mineru_middle.cover_hints`` 兜住）。机构名按
    ``mineru_full_standard._ISSUER_FRAGMENTS`` 名录规范化；解析不出来就不写（§0.3）。
    """
    for index, line in enumerate(lines):
        text = line.strip()
        if "发布" not in text or re.match(r"^\d{4}", text):
            continue
        parts = [text]
        for follower in lines[index + 1:]:
            candidate = follower.strip()
            if not candidate or "发布" in candidate or re.match(r"^\d", candidate):
                break
            if _ICS_RE.fullmatch(candidate) or _CCS_RE.fullmatch(candidate):
                break
            if not re.fullmatch(r"[^\x00-\x7f][^A-Za-z\x00-\x40]{3,}", candidate):
                break
            parts.append(candidate)
        resolved = mfs._canonical_issuer("".join(re.sub(r"\s+", "", part) for part in parts))
        return resolved or ""
    return ""


def _cover_metadata(body: str) -> dict[str, str]:
    """从封面块恢复 front matter 字段（取不到就留空，不猜测——AGENTS.md §0.3）。

    - ``replaces``：``代替 GB/T 10401—2008``（可多条，按出现顺序以「、」连接）；
    - ``publication-date`` / ``effective-date``：``YYYY-MM-DD 发布 / 实施``
      （横线可为半角 ``-``、几何破折号 ``—``/``–`` 或 OCR 点号）；
    - ``title-en``：封面块里**连续纯拉丁行组**拼成的英文译名（组内是同一标题的排版
      折行，行尾破折号去掉），组间取最长的一组（GBT-C01）；
    - ``conformity-statement``：封面块里整行括号包起来的拉丁长句（如
      ``(ISO/IEC Directives, Part 2, 2018, …)``）；
    - ``issuer``：封面区「<机构A> 发布」行加紧随其后的机构行，按机构名录规范化；
    - ``ics`` / ``ccs``：``ICS 29.160.30`` / ``CCS K 24`` 整行形态。
    """
    cover = _cover_block(body)
    meta: dict[str, str] = {}
    replaces = [item.strip() for item in _REPLACES_RE.findall(cover) if item.strip()]
    if replaces:
        meta["replaces"] = "、".join(dict.fromkeys(replaces))
    publication = _date(_PUBLICATION_DATE_RE.search(cover))
    if publication:
        meta["publication-date"] = publication
    effective = _date(_EFFECTIVE_DATE_RE.search(cover))
    if effective:
        meta["effective-date"] = effective
    lines = [line.lstrip("#").strip() for line in cover.splitlines()]
    runs: list[str] = []
    current: list[str] = []
    for line in lines:
        if not line:
            # 段落空行不切断行组：封面里英文译名常被拆成相邻的块（块间即空行）。
            continue
        if _ENGLISH_TITLE_RE.fullmatch(line) and len(line.split()) >= 3:
            current.append(line)
            continue
        if current:
            runs.append(_join_english_title(current))
            current = []
    if current:
        runs.append(_join_english_title(current))
    english = [run for run in runs if run]
    if english:
        meta["title-en"] = max(english, key=len)
    conformity = next(
        (
            line
            for line in lines
            if re.fullmatch(r"\([A-Za-z][^()]{20,}\)", line) and len(line.split()) >= 4
        ),
        "",
    )
    if conformity:
        meta["conformity-statement"] = conformity
    issuer = _issuer_from_cover(lines)
    if issuer:
        meta["issuer"] = issuer
    ics = _ICS_RE.search(cover)
    if ics:
        meta["ics"] = ics.group(1)
    ccs = _CCS_RE.search(cover)
    if ccs:
        meta["ccs"] = re.sub(r"\s+", " ", ccs.group(1)).strip()
    return meta


def _adapt_mineru_markup(body: str, part_prefix: str, *, gbt_1_1_quirks: bool = False) -> str:
    """把 raw 里的 MinerU 标记适配成 CSM（与 merge 阶段对每个分片做的转换同一套函数）。

    规则对应: GEN-004（资产相对路径）、GEN-032/033（表格题注吸附/抑制）、
    GBT-X06（公式资产绑定）、GEN-096（占位替代文本 image/img/… 不是图题名）。
    转换是幂等的：已是 CSM 的 raw（无 ``<table>``、无 ``images/`` 相对路径、无占位
    替代文本）原样返回，因此带 front matter 的历史 raw 重复跑也不改变内容。
    """
    return convert_mineru_markup(body, part_prefix, None, gbt_1_1_quirks)


def _normalize_cover(markdown: str) -> str:
    """裸 raw 的封面/横幅与附录标题归位（merge 阶段同一套规则，幂等）。

    规则对应: GBT-L03（横幅）、GBT-C01（文件名称非横幅/英文译名）、GEN-016/030。
    """
    for helper in (mfs._recover_annex_headings, mfs._demote_banner_fragments, mfs._demote_cover_headings):
        markdown = helper(markdown)
    return markdown


def _final_cover_meta(
    number: str, title: str, body: str, overrides: dict[str, str], hints: dict[str, str] | None = None
) -> dict[str, str]:
    """最终 front matter 字段：推导值 + 封面恢复值 + 封面提示，**显式覆盖值最后生效**。

    优先级：``--front-matter-json``（及 ``--standard-number``/``--title``）> 正文封面区恢复
    > ``hints``（如 middle.json 首页页眉/页脚里的 ICS/CCS/发布机构）> 推导值；取不到就不写
    该键（AGENTS.md §0.3：不猜测、不填补）。
    """
    meta: dict[str, str] = {"standard-number": number, "title": title, **_cover_metadata(body)}
    for key, value in (hints or {}).items():
        if value and not meta.get(key):
            meta[key] = value
    meta.update({key: value for key, value in overrides.items() if value})
    return meta


def _infer_title(body: str, fallback: str) -> str:
    """文档标题推导（与 merge 同规）：首个非横幅、非英文译名、非横幅片段的 H1。"""
    headings = [line.lstrip("#").strip() for line in body.splitlines() if re.match(r"^#\s", line)]
    heading = next(
        (
            item
            for item in headings
            if not mfs._is_cover_banner(re.sub(r"\s+", "", item))
            and not _ENGLISH_TITLE_RE.fullmatch(item)
            and not mfs._is_cover_banner_fragment(re.sub(r"\s+", "", item))
        ),
        "",
    )
    if not heading:
        heading = mfs._cover_title(body)
    return mfs._normalize_part_title(mfs._usable_title(heading, fallback))


def _build_front_matter(meta: dict[str, str], source_name: str, source_mode: str, provenance: str) -> str:
    """最小合法 front matter（键顺序与 merge 写出的一致）。"""
    lines = [
        "---",
        'csm-version: "1.0"',
        "document-type: standard",
        f"document-identifier: {json.dumps(meta['standard-number'], ensure_ascii=False)}",
        f"standard-number: {json.dumps(meta['standard-number'], ensure_ascii=False)}",
        f"title: {json.dumps(meta['title'], ensure_ascii=False)}",
    ]
    for key in _COVER_KEYS:
        if meta.get(key):
            lines.append(f"{key}: {json.dumps(meta[key], ensure_ascii=False)}")
    lines.extend(
        [
            "language: zh-CN",
            "source:",
            f"  mode: {source_mode}",
            f"  original-file-name: {json.dumps(source_name, ensure_ascii=False)}",
            f"  provenance: {provenance}",
            f'extraction-backend: {json.dumps(meta.get("extraction-backend", "raw markdown input"), ensure_ascii=False)}',
            "---",
            "",
        ]
    )
    return "\n".join(lines)


def _materialize_raw(front_matter_text: str, body: str) -> str:
    """raw 文件内容 = front matter（**必须带 `---` 围栏**）+ 正文（GEN-123）。

    `_split_front_matter` 的约定是「FM 正文，不含围栏」，直接拼进 raw 会让下游
    parse/normalize 以「CSM must start with YAML front matter」拒收；这里统一补围栏，
    对已带围栏的输入（`_build_front_matter` / merge 写出的 raw）幂等。
    """
    front_matter = front_matter_text.strip()
    if not front_matter.startswith("---"):
        front_matter = f"---\n{front_matter}\n---"
    return f"{front_matter.rstrip()}\n\n{body.strip()}\n"


def _rewrite_front_matter(front_matter: str, overrides: dict[str, str]) -> str:
    """既有 front matter 上重写/追加**顶层**键（显式值优先；不解析 YAML、不动其它行）。"""
    lines = front_matter.splitlines()
    for key, value in overrides.items():
        rendered = f"{key}: {json.dumps(str(value), ensure_ascii=False)}"
        pattern = re.compile(rf"^{re.escape(key)}\s*:")
        for index, line in enumerate(lines):
            if pattern.match(line):
                lines[index] = rendered
                break
        else:
            lines.append(rendered)
    return "\n".join(lines)


def _remote_image_name(url: str) -> str:
    name = Path(url.split("?", 1)[0].split("#", 1)[0]).name
    return name or hashlib.sha256(url.encode("utf-8")).hexdigest()[:16] + ".bin"


def _fetch_image(url: str, timeout: float) -> bytes:
    """下载一个远程图片（独立函数便于单测打桩，不引入新的第三方依赖）。"""
    request = urllib.request.Request(url, headers={"User-Agent": "lookWhy-raw-to-ssir/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _materialize_remote_images(
    body: str, images_dir: Path, *, timeout: float = 30.0
) -> tuple[str, int, list[str]]:
    """远端图片落地：``![](https://cdn-mineru…)`` → ``assets/images/<name>``。

    与 merge 把 MinerU 本地图片拷到 ``<docroot>/assets/images/`` 的约定一致。已存在的
    同名文件不再下载（幂等）；下载失败保持原链接并在返回值里回报失败项（不伪造资产）。
    公式块的指令形态 ``<!-- ssir:formula asset-ref="https://…" -->``（含中文公式改走图
    资产时产生，GEN-102）同样落地——否则该公式会拿着远端链接进 SSIR，渲染端找不到文件
    只能退回现场排版、汉字再次变假字形。
    返回 (新正文, 下载数, 失败描述列表)。
    """
    failures: list[str] = []
    downloaded = 0

    def _download(url: str) -> str | None:
        """远端 URL → 落盘后的相对路径；失败返回 None（保持原样）。"""
        nonlocal downloaded
        name = _remote_image_name(url)
        target = images_dir / name
        if not target.is_file():
            images_dir.mkdir(parents=True, exist_ok=True)
            try:
                payload = _fetch_image(url, timeout)
            except Exception as exc:  # noqa: BLE001 - 网络原因不限类型，保持原链接并回报
                failures.append(f"{url} ({type(exc).__name__}: {exc})")
                return None
            target.write_bytes(payload)
            downloaded += 1
        return f"assets/images/{name}"

    def _replace(match: re.Match[str]) -> str:
        alt, url = match.group(1), match.group(2)
        local = _download(url)
        return match.group(0) if local is None else f"![{alt}]({local})"

    def _replace_directive(match: re.Match[str]) -> str:
        prefix, url, suffix = match.group(1), match.group(2), match.group(3)
        local = _download(url)
        return match.group(0) if local is None else f"{prefix}{local}{suffix}"

    body = _REMOTE_IMAGE_RE.sub(_replace, body)
    return _REMOTE_ASSET_REF_RE.sub(_replace_directive, body), downloaded, failures


def _read_raw_source(path: Path) -> tuple[str, str, list[str], dict[str, str]]:
    """读取 raw 输入 → (正文, 输入格式, 警告, 封面提示)。

    - ``*.md``：原样读取（MinerU 合并 raw / 人工整理稿）；
    - ``*.json``：MinerU ``middle.json`` 版面中间产物，先由
      ``leleby_ssir.mineru_middle.middle_json_to_csm_markdown`` 翻成同形的 raw CSM
      Markdown（块类型/行列合并/公式资产在这一层用完即止，下游完全共用）。
    """
    suffix = path.suffix.lower()
    if suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"无法解析 JSON 输入 {path}: {exc}") from exc
        try:
            markdown, warnings = middle_json_to_csm_markdown(data)
            hints = middle_json_cover_hints(data)
        except MiddleJsonError as exc:
            raise RuntimeError(f"{path}: {exc}") from exc
        # issuer 行原文按发布机构名录解析（GEN-014；名录与 merge 阶段同一份）。
        issuer_text = hints.pop("issuer-text", "")
        if issuer_text:
            issuer = mfs._canonical_issuer(issuer_text)
            if issuer:
                hints["issuer"] = issuer
            else:
                warnings.append(f"cover issuer line not resolved to a known body: {issuer_text[:40]}")
        return markdown, "middle-json", warnings, hints
    if suffix in (".md", ".markdown", ".txt", ""):
        return path.read_text(encoding="utf-8", errors="replace"), "markdown", [], {}
    raise RuntimeError(f"不支持的 raw 输入格式：{path.suffix}（支持 .md / .json）")


def _resolve_raw(raw: str | Path, root: Path) -> Path:
    """解析输入：raw Markdown 路径 / 文件主干，或裸标准 ID。

    裸 ID 的查找顺序：``out/mineru/<ID>/01_extract/<ID>.raw.md`` →
    ``out/mineru/<ID>/01_extract/*.raw.md``（唯一一份）→ ``rawFile/<ID>.md``。
    """
    path = Path(raw)
    if path.is_file():
        return path
    if path.exists():
        # 文档根目录：优先人工可编辑的 canonical（从 canonical 续跑），否则 raw
        canonicals = sorted(path.glob("02_canonical/*.canonical.md")) or sorted(path.glob("*.canonical.md"))
        candidates = canonicals or sorted(path.glob("*.raw.md"))
        if len(candidates) == 1:
            return candidates[0]
        raise RuntimeError(f"{path} 下应能找到唯一一份 *.canonical.md 或 *.raw.md，实际 {len(candidates)} 份")
    doc_id = path.name
    extract_dir = root / "out" / "mineru" / doc_id / "01_extract"
    probes = [
        extract_dir / f"{doc_id}.raw.md",
        root / "rawFile" / f"{doc_id}.md",
        root / "rawFile" / f"{doc_id}.json",
    ]
    for probe in probes:
        if probe.is_file():
            return probe
    loose = [item for item in sorted(extract_dir.glob("*.raw.md"))]
    candidates = loose or sorted(extract_dir.glob("*.json")) + sorted((root / "rawFile").glob(f"{doc_id}*.json"))
    if len(candidates) == 1:
        return candidates[0]
    raise RuntimeError(
        f"找不到 raw 输入 {raw!r}；已尝试：\n  "
        + "\n  ".join(str(item) for item in (*probes, extract_dir / "*.raw.md", extract_dir / "*.json"))
    )



def _front_matter_number(front_matter: str) -> str:
    match = re.search(r"^standard-number\s*:\s*\"?(\S+?)\"?\s*$", front_matter, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _front_matter_value(front_matter: str, key: str) -> str:
    match = re.search(rf"^{re.escape(key)}\s*:\s*\"?(.*?)\"?\s*$", front_matter, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _figure_size_map_from_docroot(docroot: Path, stem: str) -> dict:
    """已有文档根里回填图源尺寸映射（GEN-098）：provenance 记录的 middle.json 输入。"""
    provenance = mfs._load_json(docroot / "01_extract" / f"{stem}.provenance.json", {})
    source_raw = str(provenance.get("sourceRaw") or "")
    if not source_raw.lower().endswith(".json"):
        return {}
    json_path = Path(source_raw)
    if not json_path.is_file():
        return {}
    try:
        return middle_json_image_sizes(json.loads(json_path.read_text(encoding="utf-8", errors="replace")))
    except (OSError, ValueError):
        return {}


def _run_canonical_start(args: argparse.Namespace, canonical: Path, root: Path) -> int:
    """以人工编辑后的 canonical 为起点：只重跑下游（parse → SSIR → 印记 → 校验 → 渲染）。

    这里**不经过 normalize**——canonical 是权威基线，绝不写回（AGENTS.md §2）。于是两个
    可人工修改的点都能独立重跑：

    - 改 raw → ``build_ssir.py <raw>``（canonical 已存在时默认拒绝覆盖，需 --overwrite-canonical）；
    - 改 canonical → 本入口，或把文档根目录/该 canonical 路径交给同一个命令。

    几何印记按可用信息恢复：源 PDF（--source-pdf / corpus/golden/<ID>.pdf）优先；否则从文档
    根 provenance 记录的 middle.json 回填图源尺寸（GEN-098）。
    """
    text = canonical.read_text(encoding="utf-8", errors="replace")
    front_matter, _body = _split_front_matter(text)
    number = (args.standard_number or _front_matter_number(front_matter)
              or mfs.standard_number_from_text(text[:3000], canonical.name.split(".")[0]) or "")
    number = re.sub(r"\.(?=\d)", "", number) if number.count(".") > 1 else number
    stem = args.output_stem or mfs.standard_filename(number) or canonical.name.removesuffix(".canonical.md")
    docroot = args.output_dir or (
        canonical.parent.parent if canonical.parent.name == "02_canonical" else root / "out" / "mineru" / stem)
    args.output_stem = stem
    args.output_dir = docroot
    paths = mfs._stage_paths(docroot, stem)
    for stage_path in paths.values():
        stage_path.parent.mkdir(parents=True, exist_ok=True)

    source_pdf = args.source_pdf
    if source_pdf is None:
        default_pdf = root / "corpus" / "golden" / f"{stem}.pdf"
        source_pdf = default_pdf if default_pdf.is_file() else None
    if source_pdf is not None and not source_pdf.is_file():
        print(f"error: --source-pdf {source_pdf} does not exist", file=sys.stderr)
        return 2
    args.input = source_pdf or canonical
    args.input_kind = "pdf" if source_pdf is not None else ""
    args.figure_size_map = {} if source_pdf is not None else _figure_size_map_from_docroot(docroot, stem)
    # 验证（投影 + 合规报告 + PDF 对比）已从构建流程剥离：默认不跑，交给独立程序 tools/verify_conversion.py
    # （--verify 只是按显式要求把它调起来，另起进程）。
    args.render = not args.no_render

    state: dict[str, Any] = mfs._load_json(docroot / "pipeline-state.json", {})
    state.setdefault("createdAt", datetime.now().astimezone().isoformat(timespec="seconds"))
    state["outputStem"] = stem
    state["title"] = args.title or _front_matter_value(front_matter, "title") or state.get("title", "")
    state["number"] = number or state.get("number", "")
    state["backend"] = state.get("backend") or "raw-markdown"
    args.state_file = docroot / "pipeline-state.json"
    mfs._write_json(args.state_file, state)

    mfs._log(f"Input canonical (human-editable baseline): {canonical.resolve()}")
    layout_path = mfs.resolve_stage_layout_path(args)
    if layout_path is not None:
        mfs._log(f"Layout channel (only source-PDF reads live here): {layout_path}")
    else:
        mfs._log(
            "No layout.json in this document root; layout stamps fall back to "
            "parts/*_middle.json (side-by-side) / the recorded middle.json size map (figure sizes); "
            "run `tools/mineru_full_standard.py --stage layout` to produce it."
        )
    if source_pdf is not None:
        mfs._log(f"Source PDF kept for the fallback geometry check only: {source_pdf.resolve()}")
    elif args.figure_size_map:
        mfs._log(f"Figure source sizes available from the recorded middle.json: {len(args.figure_size_map)} image(s)")
    stages = "parse" + ("" if args.no_render else " -> render") + (" -> verify (standalone)" if args.verify else "")
    mfs._log(f"Stages: canonical -> {stages} -> manifest")
    try:
        status = mfs._run_from_existing_canonical(args, state, canonical)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.verify:
        verification = _run_verifier(args, docroot, source_pdf)
        if verification == 2:
            return 2
        mfs._write_manifest(args, state, status="completed")
    return status


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_verifier(args: argparse.Namespace, docroot: Path, source_pdf: Path | None) -> int:
    """按显式要求调起**独立验证程序**（另起进程：markdown 投影 + 合规报告 + 可选 PDF 对比）。

    返回值 0 等价 / 3 不等价 / 2 出错；不等价不算构建失败（与 verify_conversion.py 的口径一致）。
    """
    verifier = Path(__file__).resolve().parent / "verify_conversion.py"
    command = [str(Path(sys.prefix) / "bin" / "python"), str(verifier), str(docroot)]
    if source_pdf is not None:
        command += ["--source-pdf", str(source_pdf)]
    if args.no_pdf_comparison:
        command.append("--no-pdf-comparison")
    mfs._log("Running the standalone verification program (--verify): tools/verify_conversion.py")
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode not in (0, 3):
        print("error: verification program failed", file=sys.stderr)
        return 2
    return result.returncode


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "以已有的 raw CSM Markdown 为输入跑完后续流水线："
            "normalize → canonical → SSIR → render（PDF）→ render.md 投影 → manifest。"
        )
    )
    parser.add_argument(
        "file", nargs="?", type=str, default=None,
        help="raw 输入路径（.md 或 MinerU middle.json 的 .json）或标准 ID（裸 ID 先找 "
             "out/mineru/<ID>/01_extract/<ID>.raw.md，再找 rawFile/<ID>.md 与 rawFile/<ID>.json）",
    )
    parser.add_argument("--input", type=Path, help="输入：raw CSM Markdown（.md）/ MinerU middle.json（.json）/ 人工编辑后的 canonical"
            "（.canonical.md）；与位置参数二选一；也可直接传文档根目录")
    parser.add_argument(
        "--source-pdf", type=Path, help="源 PDF（用于条文脚注回收 CSM-OCR-014 与版面印记、渲染对比；"
                                        "默认找 corpus/golden/<ID>.pdf）",
    )
    parser.add_argument("--output-dir", type=Path, help="文档根目录（默认 out/mineru/<ID>）")
    parser.add_argument("--output-stem", type=str, help="产物文件名前缀（默认按推导出的标准号规范化：GB/T→GB_T）")
    parser.add_argument("--standard-number", type=str, help="写入 front matter 的标准号（默认从 raw 封面/文件名推导）")
    parser.add_argument("--title", type=str, help="写入 front matter 的标题（默认取 raw 的首个非横幅 H1）")
    parser.add_argument(
        "--front-matter-json", type=Path,
        help='补充/覆盖 front matter 顶层键的 JSON 对象文件，如 {"ics": "29.160.30", "issuer": "…"}',
    )
    parser.add_argument("--toc-depth", default="2", help="渲染目次最大层数（正整数或 all；默认 2）")
    parser.add_argument(
        "--side-by-side-middle", type=Path, metavar="PATH",
        help="并列版面识别（GEN-095）用的整份文档 middle.json（page_idx 为 0 基绝对页号）；"
             "输入是 .json 时默认就用它自己，与文档根的 parts/ 合并使用",
    )
    parser.add_argument("--no-image-download", action="store_true", help="不下载 raw 里的远程图片链接（保持原链接）")
    parser.add_argument(
        "--verify", action="store_true",
        help="渲染完成后**另起进程**调起独立验证程序 tools/verify_conversion.py（markdown 投影 + 合规报告 + 可选 PDF 对比）；"
             "默认不做任何验证——验证是独立程序，按需单独运行")
    parser.add_argument("--no-pdf-comparison", action="store_true",
                        help="仅在使用 --verify 时生效：跳过 PDF 版面/文本量对比")
    parser.add_argument("--no-render", action="store_true", help="跳过 PDF 渲染与对比")
    parser.add_argument(
        "--overwrite-canonical", action="store_true",
        help="已存在 02_canonical/<ID>.canonical.md 时仍重跑 normalize 覆盖它（默认绝不覆盖人工编辑基线，"
             "改为从 canonical 续跑下游；AGENTS.md §2）",
    )
    return parser


def main() -> int:
    # 规则对应（阶段 → 规则层）: normalize=GEN-031—034；封面/横幅=GBT-C01/GBT-L03/GEN-016/030；
    # build=GEN-050/052；verify=GEN-051/090/091 + 三层合规；render=GEN-070—076；
    # 版面印记=GEN-095 等；条文脚注回收=CSM-OCR-014（仅 PDF 源）。
    parser = _build_parser()
    args = parser.parse_args()
    if not args.input and not args.file:
        parser.error("an input is required: pass a raw CSM Markdown path / standard ID, or --input PATH")
    if args.input and args.file:
        parser.error("pass either a positional input or --input, not both")

    try:
        raw_path = _resolve_raw(args.input or args.file, ROOT)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    args.front_matter_json_value = {}
    if args.front_matter_json:
        try:
            extra = json.loads(args.front_matter_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: invalid --front-matter-json file {args.front_matter_json}: {exc}", file=sys.stderr)
            return 2
        if not isinstance(extra, dict):
            print("error: --front-matter-json must contain a JSON object", file=sys.stderr)
            return 2
        args.front_matter_json_value = {str(key): str(value) for key, value in extra.items()}

    if raw_path.name.endswith(".canonical.md"):
        return _run_canonical_start(args, raw_path, ROOT)

    # 并列版面识别（GEN-095）的几何来源：middle.json 输入时，抽取产物本身就是整份文档的
    # 版面数据（page_idx 为 0 基绝对页号），不必等 parts/ 分片目录；显式 --side-by-side-middle 优先。
    # 放在这里（而非 raw 分支内）：既有 canonical 时本工具会走「只重跑下游」的便捷路径。
    if args.side_by_side_middle is None and raw_path.name.endswith(".json"):
        args.side_by_side_middle = raw_path

    mfs._log(f"Input raw source: {raw_path.resolve()}")
    try:
        text, input_format, input_warnings, cover_field_hints = _read_raw_source(raw_path)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for warning in input_warnings:
        mfs._log(f"raw input note: {warning}")
    if input_format == "middle-json":
        mfs._log("Converted the MinerU middle.json layout into raw CSM Markdown")
    front_matter, body = _split_front_matter(text)
    # MinerU 标记适配（GEN-004/032/033/096、GBT-X06）：HTML 表格 → CSM 表格指令、
    # 资产路径与图题注归一、占位替代文本清空。与 merge 对每个分片做的转换同一套；
    # 对已是 CSM 的 raw 幂等（无 <table>、无占位 alt 时原样返回）。
    html_tables = len(re.findall(r"<table\b", body, re.IGNORECASE))
    body = _adapt_mineru_markup(body, _RAW_PART_PREFIX, gbt_1_1_quirks=mfs._is_gbt_1_1_2020(raw_path))
    if html_tables:
        mfs._log(f"Converted {html_tables} MinerU HTML table(s) into CSM table directives")

    # 标准号：显式 > 既有 front matter > 从封面/文件名推导（与 merge 同规，斜杠转下划线）
    existing_number = ""
    if front_matter:
        match = re.search(r"^standard-number\s*:\s*\"?([^\"\n]+)\"?\s*$", front_matter, re.MULTILINE)
        existing_number = match.group(1).strip() if match else ""
    number = args.standard_number or existing_number or mfs.standard_number_from_text(body[:3000], raw_path.stem)
    number = re.sub(r"\.(?=\d)", "", number) if number.count(".") > 1 else number
    stem = args.output_stem or mfs.standard_filename(number) or raw_path.stem.removesuffix(".raw")
    args.output_stem = stem
    docroot = args.output_dir or ROOT / "out" / "mineru" / stem
    args.output_dir = docroot
    paths = mfs._stage_paths(docroot, stem)
    for stage_path in paths.values():
        stage_path.parent.mkdir(parents=True, exist_ok=True)

    title = args.title or _infer_title(body, number)
    if not front_matter:
        # 裸 raw：封面/横幅与附录标题归位（merge 阶段的同一套规则），再补 front matter。
        body = _normalize_cover(body)
        if not args.title:
            title = _infer_title(body, number)
        meta = _final_cover_meta(number, title, body, args.front_matter_json_value, cover_field_hints)
        # source.mode 只接受 user-markdown / mineru-pdf（parser CSM-META-008/009）；
        # middle.json 属 MinerU 抽取产物，如实标 mineru-pdf。
        source_mode = "mineru-pdf" if input_format == "middle-json" else "raw-markdown"
        front_matter_text = _build_front_matter(meta, raw_path.name, source_mode, f"{stem}.provenance.json")
    else:
        overrides = dict(args.front_matter_json_value)
        if args.standard_number:
            overrides["standard-number"] = args.standard_number
            overrides["document-identifier"] = args.standard_number
        if args.title:
            overrides["title"] = args.title
        front_matter_text = _rewrite_front_matter(front_matter, overrides) if overrides else front_matter

    state: dict[str, Any] = mfs._load_json(docroot / "pipeline-state.json", {})
    state.setdefault("createdAt", datetime.now().astimezone().isoformat(timespec="seconds"))
    state["outputStem"] = stem
    state["title"] = title or state.get("title", "")
    state["number"] = number or state.get("number", "")
    state["backend"] = "raw-markdown"
    args.state_file = docroot / "pipeline-state.json"

    downloaded = 0
    image_failures: list[str] = []
    if args.no_image_download:
        body_after_images = body
    else:
        body_after_images, downloaded, image_failures = _materialize_remote_images(body, docroot / "assets" / "images")
        for failure in image_failures:
            mfs._log(f"Remote image kept as-is (download failed): {failure}")
        if downloaded:
            mfs._log(f"Downloaded {downloaded} remote image(s) into {docroot / 'assets' / 'images'}")

    materialized = _materialize_raw(front_matter_text, body_after_images)
    if paths["raw"].is_file() and paths["raw"].read_text(encoding="utf-8", errors="replace") == materialized:
        mfs._log(f"Raw Markdown already in place (unchanged): {paths['raw']}")
    else:
        paths["raw"].write_text(materialized, encoding="utf-8")
        mfs._log(f"Raw Markdown written: {paths['raw']}")

    # 源 PDF（可选）：条文脚注回收 / 版面印记 / 渲染对比都要读源 PDF 几何。
    source_pdf = args.source_pdf
    if source_pdf is None:
        default_pdf = ROOT / "corpus" / "golden" / f"{stem}.pdf"
        source_pdf = default_pdf if default_pdf.is_file() else None
        if source_pdf is None:
            mfs._log(f"No source PDF found at corpus/golden/{stem}.pdf; skipping PDF-geometry stamps, "
                     "footnote recovery and PDF comparison (pass --source-pdf PATH to enable them)")
    if source_pdf is not None and not source_pdf.is_file():
        print(f"error: --source-pdf {source_pdf} does not exist", file=sys.stderr)
        return 2
    args.input = source_pdf or paths["raw"]
    args.input_kind = "pdf" if source_pdf is not None else ""
    # 并列版面识别（GEN-095）的几何来源在解析输入路径时已确定（见 main 里的赋值）；显式
    # --side-by-side-middle 优先，其次 middle.json 自身。
    args.side_by_side_middle = args.side_by_side_middle or (raw_path if input_format == "middle-json" else None)
    # 图源尺寸来源（GEN-098）：源 PDF 在场时从 PDF 图元矩形取；不在场时取 middle.json
    # 图块 bbox（两者同坐标系同数值，实测一致）——raw 起点因此不必依赖源 PDF。
    args.figure_size_map = {}
    if source_pdf is None and input_format == "middle-json":
        try:
            args.figure_size_map = middle_json_image_sizes(
                json.loads(raw_path.read_text(encoding="utf-8", errors="replace")))
        except (OSError, ValueError) as exc:
            mfs._log(f"middle.json image sizes unavailable ({exc}); figures keep the renderer default size")
        else:
            if args.figure_size_map:
                mfs._log(f"Figure source sizes available from the middle.json layout: {len(args.figure_size_map)} image(s)")
    source_sha256 = _sha256(source_pdf) if source_pdf is not None else _sha256(paths["raw"])
    state["sourceSha256"] = state.get("sourceSha256") or source_sha256
    if source_pdf is not None and not paths["source"].is_file():
        shutil.copy2(source_pdf, paths["source"])
        paths["checksum"].write_text(f"sha256:{source_sha256}\n", encoding="utf-8")
        mfs._log(f"Source PDF kept: {paths['source']}")
    mfs._write_json(args.state_file, state)

    provenance: dict[str, Any] = {
        "backend": "raw-markdown",
        "inputFormat": input_format,
        "sourceRaw": str(raw_path.resolve()),
        "sourceRawSha256": _sha256(raw_path),
        "frontMatter": "preserved" if front_matter else "synthesized",
        "imagesDownloaded": downloaded,
        "imageFailures": image_failures,
    }
    if source_pdf is not None:
        provenance["sourcePdf"] = str(source_pdf.resolve())
        provenance["figureSizesSource"] = "source-pdf"
    elif args.figure_size_map:
        provenance["figureSizesSource"] = "middle-json-bbox"
        provenance["sourcePdfSha256"] = source_sha256
    mfs._write_json(paths["provenance"], provenance)

    # manifest 记录 title/number/created/source（_post_parse_verify_render 会用 state 回填）。
    mfs._log(f"Document root: {docroot.resolve()}")
    stages = "parse" + ("" if args.no_render else " -> render") + (" -> verify (standalone)" if args.verify else "")
    mfs._log(f"Stages: normalize -> canonical -> {stages} -> manifest")

    # 验证（投影 + 合规报告 + PDF 对比）已从构建流程剥离：默认不跑，交给独立程序 tools/verify_conversion.py
    # （--verify 只是按显式要求把它调起来，另起进程）。
    args.render = not args.no_render

    # 人工编辑基线保护：已存在 canonical 时默认不重跑 normalize 覆盖它（AGENTS.md §2）。
    if paths["canonical"].is_file() and not args.overwrite_canonical:
        mfs._log(f"Existing canonical found: {paths['canonical']}")
        mfs._log("Refusing to overwrite the curated canonical; re-running the downstream stages only "
                 "(pass --overwrite-canonical to rebuild it from this raw)")
        try:
            return mfs._run_from_existing_canonical(args, state, paths["canonical"])
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    try:
        ssir = mfs.finalize(args, paths["raw"])
        if ssir is None:
            return 2
        mfs._post_parse_verify_render(args, state, paths, ssir)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rendered_pdf = paths["render_pdf"]
    mfs._log("Workflow completed successfully" + ("" if not args.render else f"; rendered PDF: {rendered_pdf}"))
    if args.verify:
        verification = _run_verifier(args, docroot, source_pdf)
        if verification == 2:
            return 2
        # 验证产物已落地，重写 manifest 让 stages 索引反映实际情况。
        mfs._write_manifest(args, state, status="completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
