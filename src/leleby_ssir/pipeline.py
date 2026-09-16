"""构建与验证阶段库：raw（已有抽取稿）→ canonical → SSIR → 渲染 → 对比。

这是「下游」的唯一实现处——``tools/`` 下的入口程序都只是它的薄壳：

- **抽取程序**（MinerU 扫描 PDF/Word → 原始抽取稿）：不 import 本模块；
- **构建程序**（raw(json/md) → canonical（可人工修改）→ SSIR → render.pdf）：两个入口——
  从 raw 起跑（normalize → canonical，canonical 已存在时默认拒绝覆盖）或从 canonical 起跑
  （只重跑下游）——都调用本模块的 ``finalize`` / ``_post_parse_verify_render`` / ``_stage_paths``；
- **验证程序**（独立，可单独跑或由构建程序调用）：``ssir csm roundtrip``（引擎在
  ``leleby_ssir.roundtrip``）＋ ``leleby_ssir.pdf_compare.compare``。

本模块此前内嵌在 ``tools/mineru_full_standard.py``（抽取工具）里，导致 raw 起点的构建路径
必须 import 抽取脚本才能跑；2026-09-12 按用户提出的三层划分把这些阶段函数搬到 src，
抽取工具保留同名 re-export（既有 import 与测试不受影响）。

规则对应：normalize=GEN-031—034；封面/横幅=GBT-C01/GBT-L03/GEN-016/030；条文脚注回收=
CSM-OCR-014；表注锚点=CSM-OCR-015；版面印记=GEN-095/GEN-098/GBT-B11；verify=GEN-051/090/091。"""


from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any

from leleby_ssir.mineru_html import convert_mineru_markup, formula_assets_index, html_table_to_csm
from leleby_ssir.naming import standard_filename, standard_number_from_text

# 仓库根：src/leleby_ssir/<module>.py → parents[2]
ROOT = Path(__file__).resolve().parents[2]


def _log(message: str) -> None:
    print(f"[{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}", flush=True)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def _page_count(pdf: Path) -> int:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to count and compare PDF pages.") from exc
    with fitz.open(pdf) as document:
        return len(document)



# Generic helpers shared with the PDF extractor: these recognise common Chinese
# national/industry standard-number prefixes (GB, GB/T, DB, QB, JB, DL, NY, ISO)
# and are deliberately not specific to GB/T 1.1-2020.  The implementations live
# in src/leleby_ssir/naming.py (single source of truth for the naming scheme).
def _usable_title(text: str, fallback: str) -> str:
    # 规则对应: GBT-C01（封面必备信息——文件名称）；损坏字体解码兜底。
    compact = " ".join(text.split())
    # Broken embedded CJK fonts often decode as repeated mathematical letters.
    if not compact or sum(1 for char in compact if "犀" <= char <= "犿") > 4:
        return fallback
    return compact[:180]


def _normalize_part_title(title: str) -> str:
    """多部分标准名称规范：主体要素与分部分名称之间补空格（GBT-C01 执行侧）。

    GB/T 1.1-2020 8.2.2：多部分标准各部分的名称应为"主体要素 第X部分：分部分
    名称"。OCR 常丢失封面标题中"第X部分"前的空格（"标准编写规则第6部分：规程
    标准" → "标准编写规则 第6部分：规程标准"），而正文首页同名标题往往保留。
    仅在紧贴汉字且缺空格时补一个半角空格（已带空格/紧跟英文/非"第N部分："形态
    均不触碰）。
    """
    return re.sub(r"(?<=[\u4e00-\u9fff])第(\d+)部分(?=[：:])", r" 第\1部分", title)


def _is_gbt_1_1_2020(source: Path) -> bool:
    """True for the GB/T 1.1-2020 input that the standard-specific quirk fixes target.

    规则对应: GBT-* 专属修复开关（仅对 GB/T 1.1-2020 输入启用 7.4 版式图恢复等 quirks）。
    """
    return "1.1-2020" in source.stem or "1.1—2020" in source.stem


def _stage_paths(output_dir: Path, stem: str, *, source_ext: str = "pdf") -> dict[str, Path]:
    """阶段目录布局（naming_specification.txt 第 4 节）：每个表示一个子目录。

    00_source/ 01_extract/ 02_canonical/ 03_ssir/ 04_render/ 05_verify/；
    资产统一放文档根 assets/（SSIR 的 assetRef 相对路径以
    ``assets/images/...`` 引用，渲染器自 03_ssir/ 向上查找）。
    ``source_ext`` 区分源文档类型（目前只用 pdf；docx 导入已暂时停用）。
    """
    return {
        "source": output_dir / "00_source" / f"{stem}.source.{source_ext}",
        "checksum": output_dir / "00_source" / f"{stem}.checksum.sha256",
        "raw": output_dir / "01_extract" / f"{stem}.raw.md",
        "extract_report": output_dir / "01_extract" / f"{stem}.extract-report.json",
        "provenance": output_dir / "01_extract" / f"{stem}.provenance.json",
        "canonical": output_dir / "02_canonical" / f"{stem}.canonical.md",
        "normalize_report": output_dir / "02_canonical" / f"{stem}.normalize-report.json",
        "ssir": output_dir / "03_ssir" / f"{stem}.ssir.json",
        "parse_report": output_dir / "03_ssir" / f"{stem}.parse-report.json",
        "render_pdf": output_dir / "04_render" / f"{stem}.render.pdf",
        "render_md": output_dir / "04_render" / f"{stem}.render.md",
        "render_report": output_dir / "04_render" / f"{stem}.render-report.json",
        "render_comparison": output_dir / "04_render" / f"{stem}.render-comparison.json",
        "verify": output_dir / "05_verify" / f"{stem}.verify.json",
        "roundtrip": output_dir / "05_verify" / f"{stem}.roundtrip.json",
    }


def _write_manifest(args: argparse.Namespace, state: dict[str, Any], title: str = "", number: str = "", status: str = "in-progress") -> None:
    """写文档索引 manifest.json（naming_specification.txt 第 6 节）。"""
    stem = args.output_stem or args.input.stem
    paths = _stage_paths(args.output_dir, stem,
                         source_ext="pdf")
    manifest: dict[str, Any] = {
        "documentId": stem,
        "title": title or state.get("title", ""),
        "standardNumber": number or state.get("number", ""),
        "status": status,
        "created": state.get("createdAt"),
        "updated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": {
            "originalFile": str(args.input.resolve()),
            "checksum": f"sha256:{state.get('sourceSha256', '')}",
        },
        "pipeline": {
            "raw": str(paths["raw"].relative_to(args.output_dir)),
            "canonical": str(paths["canonical"].relative_to(args.output_dir)),
            "ssir": str(paths["ssir"].relative_to(args.output_dir)),
            "renderMd": str(paths["render_md"].relative_to(args.output_dir)),
            "render": str(paths["render_pdf"].relative_to(args.output_dir)),
            "verify": str(paths["verify"].relative_to(args.output_dir)),
            "roundtrip": str(paths["roundtrip"].relative_to(args.output_dir)),
        },
        "stages": {
            name: str(path.relative_to(args.output_dir)) if path.exists() else None
            for name, path in paths.items()
        },
    }
    _write_json(args.output_dir / "manifest.json", manifest)


def _looks_like_document_number(text: str) -> bool:
    """True for cover code lines ("GB/T 1.1—2020", "ICS01.120 CCS A 00") that
    must never be mistaken for English-title text.

    规则对应: GEN-016（英文标题识别的前置过滤）+ GEN-011/GEN-012（分类号、文件编号行）。
    """
    compact = re.sub(r"\s+", "", text)
    return bool(
        (
            re.match(r"^[A-Z]{1,4}", compact)
            and re.search(r"\d{2,4}$", compact)
            and re.search(r"[—\-.]\d", compact)
        )
        or bool(re.match(r"ICS", compact, re.I))
        or bool(re.search(r"CCS", compact, re.I))
    )


def _cover_metadata(part_dir: Path, markdown_text: str) -> dict[str, str]:
    """Recover cover-only fields (English title, dates, issuer) for the front matter.

    规则对应: GEN-013（发布/实施日期识别）、GEN-014（发布机构识别）、
    GEN-015（代替文件编号）、GEN-016（英文标题识别）、GEN-017（一致性
    程度标识）、GEN-019（显式 front-matter 优先）；缺失项由 GBT-C01 在
    合规验证中记 finding、渲染时以 "××" 占位。

    MinerU's Markdown keeps the Chinese title but the cover publication block
    (发布/实施 dates and the issuing body) is either scattered as bare text or
    dropped with page footers, so it is recovered from the content list and
    the first-page Markdown.  Only page-0 entries are considered so that
    later occurrences in the body (e.g. 前言) do not shadow the cover values.
    """
    result: dict[str, str] = {}
    # Replaced standard ("代替 GB/T ...—....") from the cover text.  OCR/文本层
    # 可能不带空格（"代替GB/T23132—2008"），所以 \s* 而非 \s+；只扫描封面块
    # （第一个 heading 之前），避免正文以"代替…"开头的行（如"代替了…"）误命中。
    cover_lines = markdown_text.splitlines()
    for idx, line in enumerate(cover_lines):
        if line.lstrip().startswith("#"):
            cover_lines = cover_lines[:idx]
            break
    for line in cover_lines:
        match = re.match(r"^代替\s*(.+)$", line.strip())
        if match:
            result.setdefault("replaces", match.group(1).strip())
            break
    # English title: the consecutive English-only lines following the Chinese
    # title on the cover (handled below from the content list, which keeps
    # every English line regardless of Markdown heading treatment).
    # English title and adoption statement are recovered from the content
    # list below (see the consecutive-English-line rule).
    # Publication block from the page-0 content list entries.
    # English title and adoption statement: taken from the page-0 content
    # list entries (ordered by vertical position).  All consecutive
    # English-only lines that follow the Chinese title form the English
    # title (a standard may carry a name plus a part subtitle); a
    # parenthesized line naming the adopted international document is the
    # conformity statement.  Both rules are generic — no per-standard text.
    candidates = sorted(part_dir.rglob("*_content_list.json"))
    if not candidates:
        return result
    try:
        entries = json.loads(candidates[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return result

    def _is_english_line(text: str) -> bool:
        # 规则对应: GEN-016（英文标题识别：连续仅拉丁字符行）。
        # The em dash (—) is a legitimate title separator ("Rules for drafting
        # standards — Part 10: ...") but OCR often strips the spaces around it.
        return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9 ,.:;()'’/\\—\-]+", text.strip())) and len(text.strip()) > 3

    english_parts: list[str] = []
    seen_title = False
    for item in sorted(
        (item for item in entries if item.get("page_idx") in (0, None)),
        key=lambda item: float((item.get("bbox") or [0, 0, 0, 0])[1]),
    ):
        # 文本层 PDF 的机构行常被 MinerU 表示为逐字 <sup>…</sup> span
        # （如 "<sup>国</sup> <sup>家</sup> <sup>市</sup>…"），先去标签再
        # 处理，否则机构名录/日期/英文标题的连续子串匹配全被打断。
        text = re.sub(r"<[^>]+>", "", str(item.get("text") or item.get("content") or "").strip())
        if not text or re.match(r"^\d{4}-\d{2}-\d{2}", text):
            continue
        if re.search(r"[\u3400-\u9fff]", text):
            # The cover banner ("<……>标准", e.g. 国家/行业/地方/团体/企业标准)
            # marks where English lines may begin; a later Chinese line ends
            # the English-title run.  The issuing-body footer (发布机构 + 发布)
            # also contains Han characters and must not be treated as the
            # Chinese title.
            compact = re.sub(r"\s+", "", text)
            if "发布" in compact or "实施" in compact:
                continue
            if english_parts:
                break
            if not seen_title and re.search(r"标准$", compact) and len(compact) >= 6:
                seen_title = True
            continue
        adoption = re.fullmatch(r"\((.+)\)", text)
        if adoption and re.search(r"ISO|IEC|EN|ASTM|IEEE", adoption.group(1), re.I):
            result.setdefault("conformity-statement", text)
            continue
        if _is_english_line(text) and not _looks_like_document_number(text) and (seen_title or english_parts):
            english_parts.append(text)
    if not english_parts:
        # Fallback: read the cover English title straight from the PDF text
        # layer (MinerU may mangle spacing/case but the raw layer keeps it).
        english_parts = _cover_english_from_pdf(part_dir)
    if english_parts:
        result.setdefault("title-en", _tidy_english_title(" ".join(english_parts)))

    page0 = sorted(
        (item for item in entries if item.get("page_idx") in (0, None)),
        key=lambda item: float((item.get("bbox") or [0, 0, 0, 0])[1]),
    )
    prev_footer: str = ""
    for item in page0:
        text = re.sub(r"<[^>]+>", "", str(item.get("text") or item.get("content") or "").strip())
        # OCR may split the word ("发 布") and fuse both bodies into one footer
        # line, so compare on whitespace-stripped text.
        compact_line = re.sub(r"\s+", "", text)
        # GEN-013: 发布/实施日期可能同行（"2021-08-19 发布 2021-09-19 实施"），
        # 逐个识别全部「日期+发布/实施」对，而不是只认行首的日期。
        issued = re.match(r"^(\d{4}-\d{2}-\d{2})\s*发布", compact_line)
        effective = re.match(r"^(\d{4}-\d{2}-\d{2})\s*实施", compact_line)
        for date_pair in re.finditer(r"(\d{4}-\d{2}-\d{2})\s*(发布|实施)", compact_line):
            if date_pair.group(2) == "发布":
                result.setdefault("publication-date", date_pair.group(1))
            else:
                result.setdefault("effective-date", date_pair.group(1))
        if "发布" in compact_line and not issued and not effective:
            issuer_text = compact_line
            if compact_line == "发布" and prev_footer:
                # MinerU splits "<机构>发布" into a footer line (机构名) and a
                # bare "发布" line (page_number); merge them so the issuer
                # resolves instead of being reported missing (GBT-C01).
                issuer_text = prev_footer + "发布"
            issuer = _canonical_issuer(issuer_text)
            if issuer:
                result.setdefault("issuer", issuer)
        # Remember the most recent footer-like CJK line (机构名) so a later
        # standalone "发布" line can be merged with it.
        if (
            re.search(r"[\u3400-\u9fff]", compact_line)
            and not issued
            and not effective
            and "发布" not in compact_line
            and not re.match(r"^\d{4}-\d{2}-\d{2}", compact_line)
            and not _is_cover_banner(compact_line)
        ):
            prev_footer = compact_line
    # 机构行兜底：content_list 的 issuer 若只命中通用回退（OCR 常把机构名
    # 识别错，如"国家督管理委员 局会 发 布"），用原 PDF 文本层重取——文本层
    # 对封面字段可靠，命中机构名录才覆盖。
    if result.get("issuer") and not _canonical_issuer_known(result["issuer"]):
        pdf_issuer = _cover_issuer_from_pdf(part_dir)
        if pdf_issuer:
            result["issuer"] = pdf_issuer
    return result


def _cover_english_from_pdf(part_dir: Path) -> list[str]:
    """Read consecutive cover English-title lines from the PDF raw text layer.

    规则对应: GEN-016（英文标题识别，PDF 文本层兜底）。

    MinerU's OCR sometimes mangles the English title (dropped spaces, lost
    separators); the PDF text layer keeps the original characters.  Returns
    the run of Latin-only lines between the Chinese banner block and the
    publication dates.
    """
    markdown_candidates = sorted(part_dir.rglob("*.md"), key=lambda p: p.stat().st_size, reverse=True)
    pdf_candidates = sorted(part_dir.rglob("*.pdf"))
    if not markdown_candidates or not pdf_candidates:
        return []
    try:
        import pymupdf

        with pymupdf.open(pdf_candidates[0]) as doc:
            page0_text = doc[0].get_text()
    except Exception:
        return []
    lines = [line.strip() for line in page0_text.splitlines() if line.strip()]
    english: list[str] = []
    seen_banner = False
    for line in lines:
        compact = re.sub(r"\s+", "", line)
        if re.search(r"[\u3400-\u9fff]", compact):
            if english:
                break
            if re.search(r"标准$", compact) and len(compact) >= 6:
                seen_banner = True
            continue
        if re.match(r"^\d{4}-\d{2}-\d{2}", compact):
            break
        if (
            seen_banner
            and not _looks_like_document_number(line)
            and re.fullmatch(r"[A-Za-z][A-Za-z0-9 ,.:;()'’/\\—\-]+", line)
        ):
            english.append(line)
    return english


def _tidy_english_title(text: str) -> str:
    """Restore word spacing lost by OCR/font-embedding in an English title.

    规则对应: GEN-016（英文标题识别/去粘连修复，字典分割兜底）。

    Some PDFs store the title with no space glyphs ("Rulesfordrafting…").
    Two generic, order-dependent repairs:
    1. camel-case joins: a space between a lowercase letter and the following
       uppercase letter never hurts well-spaced text;
    2. dictionary segmentation: greedily split glued all-lowercase runs using
       the system word list (/usr/share/dict/words).  Applied only to tokens
       that the dictionary cannot find as-is, so correct text is untouched;
       if segmentation fails the original token is kept.
    """
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    lexicon = _system_word_list()
    if not lexicon:
        return re.sub(r"\s+", " ", spaced).strip()

    def repair(match: re.Match[str]) -> str:
        run = match.group(0)
        if len(run) < 10 or run.lower() in lexicon:
            return run
        return _segment_word(run.lower(), lexicon) or run

    # Segment each glued alphabetic run (>=10 letters, unknown to the
    # dictionary); digits and punctuation act as natural separators.
    repaired = re.sub(r"[A-Za-z]{10,}", repair, spaced)
    return re.sub(r"\s+", " ", repaired).strip()


def _system_word_list() -> set[str]:
    for candidate in ("/usr/share/dict/words", "/usr/share/dict/american-english"):
        try:
            return {line.strip().lower() for line in open(candidate, encoding="utf-8") if line.strip().isalpha()}
        except OSError:
            continue
    return set()


def _segment_word(word: str, lexicon: set[str]) -> str | None:
    """Greedy dynamic-programming split of a glued lowercase word."""
    n = len(word)
    best: list[list[str] | None] = [None] * (n + 1)
    best[0] = []
    max_len = min(24, n)
    for i in range(1, n + 1):
        for j in range(max(0, i - max_len), i - 2):
            previous = best[j]
            if previous is not None and word[j:i] in lexicon:
                candidate: list[str] = [*previous, word[j:i]]
                current = best[i]
                if current is None or len(candidate) < len(current):
                    best[i] = candidate
    result = best[n]
    return " ".join(result) if result else None



# Issuing bodies for national / industry / local / enterprise standards
# (GBT-C01 封面必备信息——发布机构).  Keyed by distinctive fragments of the
# cover footer ("<机构>发布"); deliberately generic so GB、JB/QB/DL/NY 等行业
# 标准、DB 地方标准与企业标准都能映射到规范全称。
_ISSUER_FRAGMENTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("质量监督", "质检"), "中华人民共和国国家质量监督检验检疫总局 中国国家标准化管理委员会"),
    (("市场监督", "标督管"), "国家市场监督管理总局 国家标准化管理委员会"),
    (("工业和信息化", "工信部", "机械行业", "机 行 业"), "中华人民共和国工业和信息化部"),
    (("住房和城乡建设", "住建部"), "中华人民共和国住房和城乡建设部"),
    (("交通运输", "交通部"), "中华人民共和国交通运输部"),
    (("水利部", "水利行业"), "中华人民共和国水利部"),
    (("农业农村", "农业部"), "中华人民共和国农业农村部"),
    (("卫生健康", "卫生部"), "中华人民共和国国家卫生健康委员会"),
    (("应急管理", "安监总局"), "中华人民共和国应急管理部"),
    (("生态环境", "环保部", "环境保护"), "中华人民共和国生态环境部"),
    (("文化和旅游", "文化部"), "中华人民共和国文化和旅游部"),
    (("市场监管总局",), "国家市场监督管理总局"),
    (("能源局", "能源行业"), "中华人民共和国国家能源局"),
    (("民航局",), "中国民用航空局"),
    (("轻工行业", "轻工业联合会"), "中国轻工业联合会"),
    (("纺织工业", "纺织行业"), "中国纺织工业联合会"),
    (("钢铁工业",), "中国钢铁工业协会"),
    (("电力行业", "中电联"), "中国电力企业联合会"),
    (("煤炭工业",), "中国煤炭工业协会"),
    (("石油化工", "石化行业"), "中国石油和化学工业联合会"),
    (("建筑材料", "建材行业"), "中国建筑材料联合会"),
    (("有色金属",), "中国有色金属工业协会"),
    (("包装行业",), "中国包装联合会"),
    (("物流与采购", "物流行业"), "中国物流与采购联合会"),
)

def _canonical_issuer(text: str) -> str:
    # 规则对应: GEN-014（发布机构识别与规范名称映射——通用机构名录，
    # 覆盖国家标准/行业标准/地方标准/企业标准发布机构）。
    compact = re.sub(r"\s+", "", text)
    for fragments, canonical in _ISSUER_FRAGMENTS:
        if any(fragment in compact for fragment in fragments):
            return canonical
    # Generic fallback: "<机构名>发布" — keep the body verbatim so enterprise
    # standards (企业标准 Q/…) whose issuer is an arbitrary company name still
    # resolve instead of being reported missing (GBT-C01).
    match = re.match(r"^([\u3400-\u9fff（）()·A-Za-z0-9\-]{4,40}?)发布$", compact)
    if match:
        return match.group(1)
    return ""


def _canonical_issuer_known(text: str) -> str:
    """Canonical issuer only when a known fragment matches; '' for the
    generic verbatim fallback (which may be OCR-garbled)."""
    compact = re.sub(r"\s+", "", text)
    for fragments, canonical in _ISSUER_FRAGMENTS:
        if any(fragment in compact for fragment in fragments):
            return canonical
    return ""


def _cover_issuer_from_pdf(part_dir: Path) -> str:
    """Recover the cover issuer from the PDF raw text layer (GEN-014 兜底).

    OCR 常把机构行识别错（"国家督管理委员 局会 发 布"），而原 PDF 文本层
    对封面字段可靠。pymupdf 会把 "<机构A>\\n<机构B>\\n发布" 拆成多行，
    从"发布"行向上合并相邻机构行再查机构名录。
    """
    pdf_candidates = sorted(part_dir.rglob("*.pdf"))
    if not pdf_candidates:
        return ""
    try:
        import pymupdf

        with pymupdf.open(pdf_candidates[0]) as doc:
            page0_text = doc[0].get_text()
    except Exception:
        return ""
    lines = [re.sub(r"\s+", "", line) for line in page0_text.splitlines() if line.strip()]
    for i, line in enumerate(lines):
        if "发布" in line and not re.match(r"^\d{4}-\d{2}-\d{2}", line):
            parts = [line]
            j = i - 1
            while j >= 0 and not re.search(r"发布|实施|^20\d\d-\d\d-\d\d|标准$", lines[j]):
                parts.insert(0, lines[j])
                j -= 1
            issuer = _canonical_issuer_known("".join(parts))
            if issuer:
                return issuer
    return ""


def _recover_annex_headings(markdown: str) -> str:
    """Rebuild annex headings that MinerU split into bare paragraphs.

    规则对应: GEN-030（附录标题重组：编号行 + 性质行 + 标题行合并）。

    MinerU emits the annex header as three consecutive paragraphs
    ("附录A" / "(规范性)" / "外形及安装尺寸"), which the CSM parser treats as
    plain body text, so no annex chapter is created and A.1-style clauses
    become orphans.  The three lines are joined into one proper
    "## 附录 X（规范性） 标题" heading.
    """
    # Variant 1: the same split emitted as consecutive heading lines
    # ("# 附录B" / "# (规范性)" / "# 可靠性试验方法").  Leaving three H1s
    # inflates the H1 count, corrupts merge title derivation and breaks the
    # round-trip structure layer, so they are merged like the bare-paragraph
    # variant.  Tried before the two-line variant so a 3-line split is not
    # partially consumed.
    heading_3 = re.compile(
        r"^#{1,2}\s*附\s*录\s*([A-Z])\s*\n+#{1,2}\s*[(（](规范性|资料性|推荐性|规范性附录|资料性附录)[)）]\s*\n+#{1,2}\s*([^\n#]+)",
        re.M,
    )
    markdown = heading_3.sub(
        lambda m: f"## 附录 {m.group(1)}（{m.group(2).replace('附录', '')}） {m.group(3).strip()}\n\n",
        markdown,
    )
    # Variant 2: "# 附 录 A" + "# (资料性附录) 质量评定程序或检验规则"
    # (status and title share the second heading line).
    heading_2 = re.compile(
        r"^#{1,2}\s*附\s*录\s*([A-Z])\s*\n+#{1,2}\s*[(（]([^)）]+)[)）]\s*([^\n#]+)",
        re.M,
    )
    markdown = heading_2.sub(
        lambda m: f"## 附录 {m.group(1)}（{m.group(2).replace('附录', '')}） {m.group(3).strip()}\n\n",
        markdown,
    )
    # Variant 3: "## 附录A" + optional bare "(资料性)" line + "## 标题".
    # The status marker may ride as a bare paragraph between the two heading
    # lines; when present it is recovered into the merged heading so GBT-C09
    # (性质标识必备) can pass.  A following clause heading ("A.1 ...") or
    # another annex stays untouched.
    heading_split = re.compile(
        r"^#{1,2}\s*附\s*录\s*([A-Z])\s*\n+(?:\s*[(（]([^)）]+)[)）]\s*\n+)?#{1,2}\s*(?!附录|[A-Z]\.\d)([^\n#]+)",
        re.M,
    )

    def repl_split(match: re.Match[str]) -> str:
        status = match.group(2).replace("附录", "").strip() if match.group(2) else ""
        marker = f"（{status}）" if status else ""
        return f"## 附录 {match.group(1)}{marker} {match.group(3).strip()}\n\n"

    markdown = heading_split.sub(repl_split, markdown)
    # Variant 3b: "# 附录C" + bare "(规范性)" line + bare title paragraph —
    # MinerU keeps only the annex letter as a heading and demotes both the
    # status marker and the title to plain paragraphs (SJT 11859-2022).
    heading_bare = re.compile(
        r"^#{1,2}\s*附\s*录\s*([A-Z])\s*\n+\s*[(（](规范性|资料性|推荐性|规范性附录|资料性附录)[)）]\s*\n+([^\n#]+)",
        re.M,
    )

    def repl_bare(match: re.Match[str]) -> str:
        status = match.group(2).replace("附录", "").strip()
        return f"## 附录 {match.group(1)}（{status}） {match.group(3).strip()}\n\n"

    markdown = heading_bare.sub(repl_bare, markdown)
    # Variant 0: bare paragraphs (no heading prefix), the original case.
    pattern = re.compile(
        r"^附录\s*([A-Z])\s*\n+\n*[(（](规范性|资料性|规范性附录|推荐性)[)）]\s*\n+\n*(.+?)\n+(?=##?\s|[^\n])",
        re.M,
    )

    def repl(match: re.Match[str]) -> str:
        return f"## 附录 {match.group(1)}（{match.group(2)}） {match.group(3).strip()}\n\n"

    return pattern.sub(repl, markdown)


_COVER_BANNER_RE = re.compile(
    r"(?:中华人民共和国)?[\u3400-\u9fff（）()·]{0,40}?(?:国家|行业|地方|团体|企业)标准"
)


def _is_cover_banner(compact: str) -> bool:
    """True when the whitespace-stripped line is a cover banner.

    规则对应: GBT-L03（封面横幅）+ GBT-C01（文件名称非横幅）。
    横幅形态覆盖各级标准：中华人民共和国国家标准 / 中华人民共和国机械
    行业标准 / 晋中经纬新科机械有限公司企业标准 / 团体标准 / 上海市地方
    标准 等；机构名 + 层级字样（企业/团体/地方/行业/国家）均为横幅，
    整行匹配才判定，避免把标题（如「减速器」）误判为横幅。
    """
    return bool(_COVER_BANNER_RE.fullmatch(compact))



# OCR 会把带徽标页的横幅拆成两段（图前 "# 中华人民共和国" + 图后
# "国家标准"）。单独一段不是完整横幅，但拼起来才是；这些片段绝不能
# 当作文档标题（GBT-C01 文件名称）。
_BANNER_FRAGMENTS = ("中华人民共和国", "国家标准")


def _is_cover_banner_fragment(compact: str) -> bool:
    """True when the whitespace-stripped line is only a fragment of a banner."""
    return compact in _BANNER_FRAGMENTS


def _demote_banner_fragments(markdown: str) -> str:
    """Demote OCR-split cover-banner headings back to plain paragraphs.

    MinerU 常把封底/封面横幅在徽标图处拆成 "# 中华人民共和国" + "国家标准"
    两行（GB 标准封底版式）。前半段是 H1 时会污染标题推导并给正文引入
    孤立大标题；若它与其后首个非空行拼起来恰是完整横幅，就降级为普通
    段落。仅处理"拼成横幅"的情形，避免误伤正文标题。

    规则对应: GBT-L03（横幅）+ GBT-C01（文件名称）。
    """
    lines = markdown.splitlines()
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        match = re.match(r"^#\s+(.+?)\s*$", line)
        demoted = False
        if match:
            compact = re.sub(r"\s+", "", match.group(1))
            if compact in _BANNER_FRAGMENTS:
                j = i + 1
                while j < n and not lines[j].strip():
                    j += 1
                if j < n:
                    nxt = re.sub(r"^#+\s*", "", lines[j].strip())
                    if _is_cover_banner(compact + re.sub(r"\s+", "", nxt)):
                        out.append(match.group(1))  # demote: drop the H1 marker
                        demoted = True
        if not demoted:
            out.append(line)
        i += 1
    return "\n".join(out)


def _demote_cover_headings(markdown: str) -> str:
    """Demote cover-block H1 lines that are not the document title.

    MinerU promotes cover lines — the "中华人民共和国国家标准" banner (also
    "<机构名>企业标准" for enterprise standards, "团体标准", "<省>地方标准"
    etc.) and the English translation — to H1.  Neither is the document
    title (GBT-C01 文件名称); leaving them as H1s inflates the H1 count and
    corrupts title derivation.  Only lines before the first "##" heading (the
    cover block of the first part) are touched; the Chinese title H1, when
    present, stays.

    规则对应: GBT-C01（文件名称必备，横幅/英文译名非标题）+ GEN-016（标题识别）。
    """
    head, sep, tail = markdown.partition("\n## ")
    if not sep:
        return markdown
    fixed_lines: list[str] = []
    for line in head.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match and (
            _is_cover_banner(re.sub(r"\s+", "", match.group(1)))
            or re.fullmatch(r"[A-Za-z][A-Za-z0-9 ,.:;()'’/\\—\-]+", match.group(1).strip())
        ):
            fixed_lines.append(match.group(1))  # demote: drop the H1 marker
        else:
            fixed_lines.append(line)
    return "\n".join(fixed_lines) + sep + tail


def _cover_title(markdown: str) -> str:
    """Recover the Chinese standard name from the cover block.

    The cover name sits between the number/replaces lines and the English
    title.  MinerU usually emits it as a bare paragraph (no heading), but for
    enterprise standards it may promote the cover title to a heading too, so
    heading lines whose content is neither banner, date, number nor the 发布/
    实施 block are treated as the title.  Returns the first such CJK line.

    规则对应: GBT-C01（文件名称）+ GEN-016（标题识别，中文行）。
    """
    for line in markdown.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        is_heading = stripped.startswith("#")
        content = re.sub(r"^#+\s*", "", stripped)
        compact = re.sub(r"\s+", "", content)
        if _is_cover_banner(compact):
            continue
        if re.search(r"发布|实施", compact) or compact.startswith("代替"):
            continue
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}.*", compact):
            continue
        if not re.search(r"[\u3400-\u9fff]", compact):
            continue  # number line / English title / dates are not the name
        if is_heading and re.match(
            r"^(前\s*言|引\s*言|目\s*次|参考文献|索引|附录|范围|规范性引用文件|术语和定义)",
            compact,
        ):
            break  # a real body heading ends the cover block
        return compact
    return ""


_ELLIPSIS_CHARS = ("…", "⋯")  # U+2026 与 U+22EF（中线省略号，部分字体映射）


_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９．", "0123456789.")


def _text_layer_content_lines(pdf: Path) -> list[dict[str, Any]]:
    """Extract content lines (page/x0/y0/text) from the source PDF text layer.

    通用后验的输入基础：文本层是版面真值的唯一权威来源（MinerU OCR 可能丢弃
    纯符号行——如"……"占位行——而文本层完整保留；中文虽可能乱码，但行数、
    坐标、数字、拉丁与标点符号可信）。
    """
    try:
        import pymupdf
    except ImportError:
        return []
    lines: list[dict[str, Any]] = []
    with pymupdf.open(pdf) as document:
        for page_index in range(len(document)):
            page = document[page_index]
            for block in page.get_text("dict")["blocks"]:  # type: ignore[index]
                for line in block.get("lines", []):  # type: ignore[union-attr]
                    text = "".join(span["text"] for span in line["spans"]).strip()  # type: ignore[index]
                    if not text:
                        continue
                    y0 = line["bbox"][1]  # type: ignore[index]
                    x0 = line["bbox"][0]  # type: ignore[index]
                    if y0 < 80:
                        continue  # 页眉（标准号眉线）
                    if y0 > 740 and re.fullmatch(r"[0-9０-９IVXⅣⅤⅧ]+", text):
                        continue  # 页脚页码（奇偶页左右交替，只按内容形态过滤）
                    lines.append({"page": page_index + 1, "x0": x0, "y0": y0, "text": text})
    return lines


def _is_short_ellipsis(text: str) -> bool:
    """Pure ellipsis line (1-6 个 …/⋯)。目录点线（40+ 个 …）不属于内容占位。"""
    t = text.replace(" ", "")
    return 1 <= len(t) <= 6 and set(t) <= set(_ELLIPSIS_CHARS)


def _clause_skeleton(text: str) -> str | None:
    """行首条号骨架：５．８ → 5.8、６ → 6。仅当行首（可带破折号/空白）是
    点分数字链**且后随空白或行尾**时返回——乱码行中段碎片（如 "7b…"）的
    伪编号不匹配，避免把省略号锚到错误位置。"""
    t = text.translate(_FULLWIDTH_DIGITS)
    # 后随空白时空白后不得再是数字（"１ 01" 型目录页码行不算条号）；
    # 后随行尾也可（孤立的章号行）。
    match = re.match(r"^[\s—–\-]*(\d+(?:\.\d+){0,3})(?=\s(?![0-9０-９])|$)", t)
    return match.group(1) if match else None


def _raw_line_starts_with_number(line: str, skeleton: str) -> bool:
    """raw 行（可带 markdown 标题前缀）是否以该条号骨架开头且不吞掉更长编号。"""
    s = line.lstrip("#").strip()
    return bool(re.match(rf"^{re.escape(skeleton)}(?=[^\d.]|$)", s))


def _restore_ellipsis_lines(body: str, pdf: Path) -> str:
    """Generic restoration of OCR-dropped pure-ellipsis lines (GEN-092 后验补盲)。

    现象（GB_T_20001.6-2017 等规程/指南标准的示例文档）：MinerU OCR 丢弃
    纯"……"占位行（5.3/5.4.1/5.4.2/5.4.3/5.7.1 a)/5.8/5.9/6.2 末尾等），
    源 PDF 文本层完整保留。恢复分两类：

    - 正文省略号：以省略号行之后的**下一个带条号骨架的文本层行**为锚（锚定到
      raw 中该骨架的最后一个出现位置，靠单调游标保持插入顺序），把"……"插到
      该行之前；无后随锚且位于最后一页末行时追加到文末（6.2 末尾型）。
    2026-09-07 用户裁定：不再做"表格单元格内按……切段、前后加 <br> 让省略号独占
    一行"的重建（单元格行结构恢复整条取消；正文恢复保留）——需要时在 canonical
    人工处理单元格换行。

    保守原则：锚点/长度无法可靠匹配时不改（不猜测）；raw 已在插入点附近有
    短省略号行时跳过（防重复）。
    """
    text_lines = _text_layer_content_lines(pdf)
    if not text_lines:
        return body
    ellipsis_indexes = [i for i, line in enumerate(text_lines) if _is_short_ellipsis(line["text"])]
    if not ellipsis_indexes:
        return body

    raw_lines = body.split("\n")
    insert_before: list[tuple[int, str]] = []  # (raw 行号, 插入文本)，逆序应用
    cursor = 0
    consumed: set[int] = set()

    def _table_like(line_index: int) -> bool:
        """省略号行是否位于表格单元格内：同页存在 **≥2 个** |Δy|≤40 且
        |Δx|≥60 的其他内容行（表格网格的同行多列特征；单条缩进行/居中行
        如示例引导语不会误判）。"""
        me = text_lines[line_index]
        hits = 0
        for other in text_lines:
            if other["page"] != me["page"]:
                continue
            if abs(other["y0"] - me["y0"]) <= 40 and abs(other["x0"] - me["x0"]) >= 60:
                hits += 1
                if hits >= 2:
                    return True
        return False

    # 第一遍：正文省略号（非表格），记录插入点。
    for e in ellipsis_indexes:
        if _table_like(e):
            continue
        # 下一个带条号骨架的文本层行——必须与省略号同页（跨页会把前言/引言
        # 中的省略号锚到正文章节，如 p3 前言省略号误锚到 p5 "2 规范性引用文件"）。
        f_index = None
        for j in range(e + 1, len(text_lines)):
            if text_lines[j]["page"] != text_lines[e]["page"]:
                break
            if _clause_skeleton(text_lines[j]["text"]):
                f_index = j
                break
        if f_index is None:
            # 无后随锚：仅当它是整份文档最后一页的末行内容时追加到文末
            # （如 6.2 末尾的"……"）。
            last_content = text_lines[-1]
            if text_lines[e] is last_content or (
                text_lines[e]["page"] == last_content["page"]
                and text_lines[e]["y0"] >= last_content["y0"]
            ):
                marker = next(
                    (ri for ri in range(len(raw_lines) - 1, -1, -1) if raw_lines[ri].startswith("<!-- /ssir:mineru-pages -->")),
                    len(raw_lines),
                )
                insert_before.append((marker, "……"))
                cursor = len(raw_lines)
            continue
        skeleton = _clause_skeleton(text_lines[f_index]["text"])
        if skeleton is None:
            continue
        # raw 中该骨架的最后一个出现位置（须在游标之后）——同号重复时
        # 省略号属于较早出现与较晚出现之间的位置，取后者。
        found = None
        for ri in range(len(raw_lines) - 1, cursor - 1, -1):
            if _raw_line_starts_with_number(raw_lines[ri], skeleton):
                found = ri
                break
        if found is None:
            continue
        if any(_is_short_ellipsis(raw_lines[k].strip()) for k in range(max(0, found - 3), found)):
            cursor = found + 1
            continue
        insert_before.append((found, "……"))
        cursor = found + 1
        consumed.add(e)

    if not insert_before:
        return body

    for ri, text in sorted(insert_before, key=lambda item: item[0], reverse=True):
        raw_lines.insert(ri, text)
    return "\n".join(raw_lines)


def finalize(args: argparse.Namespace, merged: Path) -> Path | None:
    """Use the existing CSM normalizer/parser, retaining partial status if parsing needs review.

    规则对应: GEN-031（层次编号规范化）、GEN-050（元数据 schema 登记）；合规验证由
    service 层 verify_compliance 按 GEN-* → GBT-* → P10-* 三层执行并写入转换报告。
    """
    stem = args.output_stem or args.input.stem
    paths = _stage_paths(args.output_dir, stem)
    canonical = paths["canonical"]
    ssir = paths["ssir"]
    normalize = [
        str(Path(sys.prefix) / "bin" / "ssir"), "csm", "normalize",
        "--input", str(merged), "--canonical-output", str(canonical),
        "--report", str(paths["normalize_report"]),
    ]
    parsed = [
        str(Path(sys.prefix) / "bin" / "ssir"), "csm", "parse",
        "--input", str(canonical), "--output", str(ssir),
        "--report", str(paths["parse_report"]),
    ]
    _log("Normalizing merged MinerU Markdown into canonical CSM")
    if subprocess.run(normalize, cwd=ROOT).returncode:
        # 以前行为：normalize 失败时仍保留 merged 作为 fallback；不静默退出，
        # 防止无 canonical 时直接返回 None 导致流水线异常终止（GB_T_5171.1-2014 类）。
        # AGENTS.md §0.2/§0.4：不伪造数据，不修个例数据；此处仅保留原中间产物以供人工复核。
        print("CSM normalization needs review; MinerU extraction and provenance remain available (canonical not produced).", file=sys.stderr)
        # 回退：不覆盖已有 canonical（若存在），不生成新 canonical，返回 None 由主入口处理下游缺失。
        return None
    # 条文脚注回收（CSM-OCR-014）：MinerU 常把上标脚注标记与正文粘连（“—2003”+1)
    # →“—20031”），页底解释行被当普通正文；且 normalize 对 raw 里的 GFM
    # “[^N]: …” 定义行在内存归类为 footnote 后并不回写 canonical（实测丢失）。
    # 因此脚注回收只能作用于 normalize **刚生成**的 canonical：在本轮全流程
    # （--stage all 且无 canonical，或显式 --stage finalize 重生成）的 normalize
    # 之后、parse 之前执行——此刻 canonical 是本轮产物，不是人工编辑的 curated
    # 基线；从 canonical 续跑的半程路径（_run_from_existing_canonical）不经过本
    # 函数，绝不会改写已存在的 curated canonical（AGENTS.md §2）。幂等：已有
    # “[^N]” 标记与定义时不重复写。
    if args.input.suffix.lower() == ".pdf" and canonical.is_file():
        recovered = _recover_pdf_footnotes(canonical, args.input)
        if recovered:
            _log(f"Recovered {recovered} footnote(s) from the source PDF text layer into {canonical.name}")
    _log("Parsing normalized CSM into SSIR JSON")
    if subprocess.run(parsed, cwd=ROOT).returncode:
        print("SSIR parsing needs review; normalized CSM remains available.", file=sys.stderr)
        return None
    _log(f"SSIR JSON written: {ssir}\n")
    if args.input.suffix.lower() == ".pdf":
        # 版面几何印记仅对 PDF 源有效（读取源 PDF 的矢量几何/裁剪尺寸）。
        _stamp_example_styles(ssir, args.input)
        _stamp_figure_source_sizes(ssir, args.input)
        _stamp_side_by_side_layout(
            ssir, args.output_dir / "parts", middle_json=getattr(args, "side_by_side_middle", None)
        )
    elif getattr(args, "figure_size_map", None):
        # raw 起点（middle.json 输入）没有源 PDF：图源尺寸取图块 bbox（GEN-098 第二来源）。
        _stamp_figure_source_sizes_from_map(ssir, args.figure_size_map)
        _stamp_side_by_side_layout(
            ssir, args.output_dir / "parts", middle_json=getattr(args, "side_by_side_middle", None)
        )
    return ssir


def _stamp_example_styles(ssir_path: Path, source_pdf: Path) -> None:
    """Detect the original example-box style and record it on SSIR example nodes
    (GBT-B11 示例线框：frame=黑色细实线框 / shaded=浅色背景，两种模式都要保留，
    渲染与原文一致).

    检测依据是源 PDF 的矢量几何：大尺寸描边矩形 → frame；大尺寸填充矩形 → shaded。
    扫描型 PDF（页面是位图、无矢量框线）检测不到，节点不带 exampleStyle，
    渲染时回退到渲染 profile 的 examples.style 默认值。
    """
    try:
        import fitz  # type: ignore
    except Exception:
        return
    stroke_rects = 0
    fill_rects = 0
    try:
        with fitz.open(source_pdf) as document:
            for page in document:
                for drawing in page.get_drawings():
                    rect = drawing["rect"]
                    if rect.width < 80 or rect.height < 30:
                        continue
                    if drawing.get("fill"):
                        fill_rects += 1
                    elif drawing.get("stroke"):
                        stroke_rects += 1
    except Exception:
        return
    if not (stroke_rects or fill_rects):
        return  # 无矢量几何（扫描型）→ 保留 profile 默认
    style = "frame" if stroke_rects >= fill_rects else "shaded"
    try:
        data = json.loads(ssir_path.read_text(encoding="utf-8"))
    except Exception:
        return

    def visit(nodes: list[Any]) -> None:
        for node in nodes:
            if node.get("exampleContent"):
                node.setdefault("exampleStyle", style)
            visit(node.get("children", []) or [])

    visit(data.get("structuralRoot", {}).get("children", []) or [])
    ssir_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"Example style detected from source PDF: {style} (stroke={stroke_rects}, fill={fill_rects})")


def _stamp_figure_source_sizes(ssir_path: Path, source_pdf: Path) -> None:
    """Record each figure's original layout size (pt) from the source PDF.

    MinerU 裁剪图常以高于原版的像素密度导出（GB_T_23132-2024 实测约 2.1-3x），
    渲染端按固有 72dpi 尺寸输出会远超原图（图1 42x76pt 被放大到 126x212pt）。
    本步骤把每张图在源 PDF 中的版面矩形尺寸写入 SSIR figure 的
    sourceWidth/sourceHeight（pt），渲染端据此还原原图尺寸（GEN-098）。

    匹配依据：裁剪图保持宽高比，源 PDF 图像矩形与资产宽高比接近
    （|Δaspect| < 0.12）且像素密度比在合理范围（[1.2, 4.0] px/pt）者胜出；
    每个源矩形只分配给一个资产（贪心：全局最接近宽高比者优先），防止
    两个相似裁剪图抢同一矩形（表2 旋转式 试验区域分割/插入角度 两张方形图）。
    **封面徽标/装饰小图不参与匹配**（第 1 页上高度 < 100pt 的矩形——标准封面
    的徽标与 logo，非内容图；正文图不会出现在封面），否则宽高比接近的
    内容图会误配到封面徽标矩形（如 表2 往复式 试验区域分割图 2.04 宽高比
    误配封面 GB_logo 113.7x56.9）。

    两类图片匹配不到独立矩形：
    - 子图裁剪（图2 卷曲判定图被拆分出的 a)/b) 无编号图块）：宽高比与整图
      矩形不符 → 回退到**文档像素密度估计**：取已匹配资产的 px/pt 中位数
      （OCR 重渲染页密度整本稳定，~200dpi/72 ≈ 2.78；扫描型 PDF 无任何匹配
      时直接默认 2.78），size = 像素/密度，仍接近原图尺寸；
    - 表格单元格内图（GBT-X02 表中图，`![](ref)` 挂在 table cell 文本上，
      如 表2 试验区域分割/插入角度示意图）：同样参与匹配与密度回退，尺寸
      写入 table["cellImageSizes"] = {ref: [w, h]}，渲染端按原尺寸（上限
      单元格宽）显示。

    注意 assetRef 是相对文档根的（<docroot>/assets/images/...），SSIR 位于
    03_ssir/ 子目录——必须沿祖先目录向上找（同 pdf_renderer._resolve_asset）。
    此前只按 ssir_path.parent / ref 解析导致所有图都拿不到尺寸（03_ssir/
    下没有 assets/），是"图太大"的直接根因。
    """
    try:
        import fitz  # type: ignore
        from PIL import Image as PILImage  # type: ignore
    except Exception:
        return
    try:
        data = json.loads(ssir_path.read_text(encoding="utf-8"))
    except Exception:
        return
    figures = data.get("figures") or []
    if not figures:
        return
    try:
        with fitz.open(source_pdf) as document:
            # (rw, rh, page_index)；第 1 页（封面）的徽标/装饰小图
            # （高 < 100pt）不参与匹配——封面徽标由 config/emblems/ 独立处理，
            # 非内容图；宽高比接近的内容图误配到徽标矩形会得到错误尺寸。
            rects: list[tuple[float, float, int]] = []
            for page_index, page in enumerate(document):
                for info in page.get_image_info():
                    r = info["bbox"]
                    rw, rh = r[2] - r[0], r[3] - r[1]
                    if rw >= 10 and rh >= 10 and not (page_index == 0 and rh < 100):
                        rects.append((rw, rh, page_index))
    except Exception:
        return
    if not rects:
        return

    def _resolve_asset(ref: str) -> Path:
        # assetRef 相对文档根；SSIR 在 03_ssir/ 时沿祖先目录向上找。
        for parent in ssir_path.parents:
            candidate = parent / ref
            if candidate.is_file():
                return candidate
        return ssir_path.parent / ref

    def _pixel_size(asset: Path) -> tuple[int, int] | None:
        try:
            with PILImage.open(asset) as im:
                aw, ah = im.size
        except Exception:
            return None
        if aw < 20 or ah < 20:
            return None
        return aw, ah

    # 候选图片：figures 注册表 + 表格单元格内图（GBT-X02 表中图）。
    cell_image_re = re.compile(r"!\[(?:[^\]]*)\]\(([^)]+)\)")
    # (kind, owner, ref, (aw, ah))
    candidates: list[tuple[str, dict[str, Any], str, tuple[int, int]]] = []
    seen_refs: set[str] = set()
    for figure in figures:
        ref = figure.get("assetRef")
        if not ref or ref in seen_refs:
            continue
        asset = _resolve_asset(ref)
        size = _pixel_size(asset) if asset.is_file() else None
        if size:
            seen_refs.add(ref)
            candidates.append(("figure", figure, ref, size))
    for table in data.get("tables") or []:
        for row in table.get("rows") or []:
            for cell in row.get("cells") or []:
                for match in cell_image_re.finditer(str(cell.get("text", ""))):
                    ref = match.group(1)
                    if ref in seen_refs:
                        continue
                    asset = _resolve_asset(ref)
                    size = _pixel_size(asset) if asset.is_file() else None
                    if size:
                        seen_refs.add(ref)
                        candidates.append(("table", table, ref, size))
    if not candidates:
        return

    # 贪心匹配：全局最小 |Δaspect| 的 (候选, 矩形) 对先占位，矩形不重复分配。
    used: set[int] = set()
    matched: dict[str, tuple[float, float]] = {}
    density_ratios: list[float] = []
    remaining = list(candidates)
    while remaining:
        best_pair: tuple[float, int, int] | None = None
        for ci, (kind, owner, ref, (aw, ah)) in enumerate(remaining):
            aspect = aw / ah
            for ri, (rw, rh, _page_index) in enumerate(rects):
                if ri in used:
                    continue
                aspect_diff = abs(aspect - rw / rh)
                if aspect_diff >= 0.12:
                    continue
                res_w = aw / rw
                res_h = ah / rh
                if not (1.2 <= res_w <= 4.0 and 1.2 <= res_h <= 4.0):
                    continue
                if best_pair is None or aspect_diff < best_pair[0]:
                    best_pair = (aspect_diff, ci, ri)
        if best_pair is None:
            break
        _, ci, ri = best_pair
        kind, owner, ref, (aw, ah) = remaining.pop(ci)
        rw, rh, _page_index = rects[ri]
        used.add(ri)
        matched[ref] = (rw, rh)
        density_ratios.append(aw / rw)
        density_ratios.append(ah / rh)
    # 无匹配（扫描型 PDF：源页是整页位图，宽高比/密度对不上任何内容裁剪图）时
    # 回退到 MinerU OCR 重渲染默认 200dpi/72 ≈ 2.78 px/pt（GB_T_23132-2024
    # 实测匹配中位数 2.77 一致）。
    density = sorted(density_ratios)[len(density_ratios) // 2] if density_ratios else (200 / 72)

    stamped = 0
    for kind, owner, ref, (aw, ah) in candidates:
        if ref in matched:
            rw, rh = matched[ref]
        elif density:
            rw, rh = aw / density, ah / density
        else:
            continue
        if kind == "figure":
            owner["sourceWidth"] = round(rw, 1)
            owner["sourceHeight"] = round(rh, 1)
        else:
            owner.setdefault("cellImageSizes", {})[ref] = [round(rw, 1), round(rh, 1)]
        stamped += 1
    if stamped:
        ssir_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        _log(f"Figure source sizes stamped from source PDF: {stamped}/{len(candidates)} images (density={density and round(density, 2)} px/pt)")


def _stamp_figure_source_sizes_from_map(ssir_path: Path, size_map: dict[str, tuple[float, float]]) -> None:
    """Record figure sizes (pt) from an ``{asset name: (w, h)}`` map (GEN-098 第二来源).

    源 PDF 不在场时（raw 起点 + MinerU middle.json，退出 `corpus/golden` 依赖）用
    ``mineru_middle.image_source_sizes`` 从图块 bbox 取尺寸：与源 PDF 图元矩形同坐标系
    同数值，且裁剪图与图块一一对应，因此不需要宽高比/密度匹配，也不做密度回退——
    拿不到尺寸的图保持无印记（渲染端按默认尺寸），不猜。
    表格单元格内图（GBT-X02 表中图）同样写入 ``cellImageSizes``。
    """
    if not size_map:
        return
    try:
        data = json.loads(ssir_path.read_text(encoding="utf-8"))
    except Exception:
        return
    figures = data.get("figures") or []
    cell_image_re = re.compile(r"!\[(?:[^\]]*)\]\(([^)]+)\)")
    stamped = 0
    for figure in figures:
        ref = figure.get("assetRef")
        size = size_map.get(_asset_basename(str(ref or "")))
        if not size:
            continue
        figure["sourceWidth"], figure["sourceHeight"] = size
        stamped += 1
    for table in data.get("tables") or []:
        for row in table.get("rows") or []:
            for cell in row.get("cells") or []:
                for match in cell_image_re.finditer(str(cell.get("text", ""))):
                    ref = match.group(1)
                    size = size_map.get(_asset_basename(ref))
                    if size:
                        table.setdefault("cellImageSizes", {})[ref] = [size[0], size[1]]
                        stamped += 1
    if stamped:
        ssir_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        _log(f"Figure source sizes stamped from the middle.json layout: {stamped} image(s)")


def _asset_basename(ref: str) -> str:
    """资产引用 → 文件名（去查询串；用于与 middle.json 图块 bbox 键对齐）。"""
    return ref.split("?", 1)[0].split("#", 1)[0].rstrip("/").rsplit("/", 1)[-1]



# 并列版面几何识别的通用参数（GEN-095）：只用版心比例与行高，不依赖具体文档。
_PART_PAGE_RANGE_RE = re.compile(r"pages-(\d+)-(\d+)")


_EXAMPLE_CAPTION_RE = re.compile(r"^示例\s*\d*\s*[:：]")


_FULL_WIDTH_RATIO = 0.62   # 宽度 ≥ 版心 62% → 通栏块（并列区天然分隔）


_ANCHOR_COLUMN_GAP_RATIO = 0.20  # 锚点 x 中心相距 > 20% 版心 → 不同列


_MAX_SIDE_COLUMNS = 3      # 并列列数上限（4+ 并排的罕见版面不猜测）


_REGION_GAP_LINES = 1.5    # 相邻块垂距 > 1.5×行高 → 另起并列区


def _latex_key(latex: str) -> str:
    """公式匹配键：去掉全部空白。

    两条抽取路线的同一公式在分词/空格上不同（本地 ``v = 3.6 \\times \\frac{l}{t}``、
    云端 ``v = 3. 6 \\times \\frac {l}{t}``），按空白归一后才是同一个键。
    """
    return re.sub(r"\s+", "", latex or "")


# 并列版式匹配用的标点折叠表（GEN-095）：MinerU 的行内 span 常把全角标点写成半角
# （几何块文本「在数学公式中,使用」vs SSIR「在数学公式中，使用」），只按空白归一会
# 让整块文本匹配落空、组内元素缺失（GB/T 1.1-2020 9.9.3.3 示例3 的左列标题行）。
_MATCH_PUNCT_TABLE = str.maketrans("（）：；，、？！．～", "():;,,?!.~")
# 行内公式的字体命令脱壳：SSIR 侧保留 LaTeX 拼写（``$S_{\\mathrm{ME},i}$``），
# MinerU 侧的行内 span 是朴素拼写（``S_{ME,i}``），不脱壳则子串匹配落空
# （GB/T 1.1-2020 9.9.3.1 示例5 的两条变量解释行）。
_MATCH_STYLE_RE = re.compile(r"\\(?:mathrm|text|mathit|mathbf|operatorname)\s*\{([^{}]*)\}")


def _fold_match_text(text: str) -> str:
    """并列版式内容匹配的文本归一（规则对应: GEN-095）。

    去全部空白 → 去行内公式定界符 ``$`` → 全/半角标点统一 → 行内 LaTeX 字体命令脱壳
    （可嵌套，循环到稳定）→ 破折号族压成单个 ``—``（SSIR 侧经 CSM-OCR-018 已归一为
    「——」，MinerU 块文本仍是 ``———``/``——``/``—`` 变体）。只用于匹配，不改数据。
    """
    text = re.sub(r"\s+", "", text or "")
    text = text.replace("$", "").translate(_MATCH_PUNCT_TABLE)
    while True:
        folded = _MATCH_STYLE_RE.sub(r"\1", text)
        if folded == text:
            break
        text = folded
    return re.sub(r"[—–]+", "—", text)


def _side_by_side_sources(parts_dir: Path, middle_json: Path | None = None) -> list[Path]:
    """并列版面识别用的 ``*_middle.json`` 清单（两条来源合并，按路径去重）。

    两条来源是**同一套版面几何的两种分片形态**，合并使用让两侧锚点都能参与匹配：

    - 整份文档的 ``middle.json``（raw 起点路线：云端/Pipeline 的抽取产物本身就是这份数据，
      ``page_idx`` 是 0 基绝对页号 → ``_absolute_page`` 落回 ``page_idx + 1``）；
    - 分片目录 ``parts/``（merge 起点路线：每个分片一个 middle.json，绝对页号从目录名
      ``pages-037-054`` 取起始页）。

    合并稿这类「文本来自一侧、公式来自另一侧」的文档，两边的资产名/LaTeX 各有一部分命中，
    只取一侧会丢掉另一半锚点；重复的锚点由内容级去重（``assigned``）挡住。
    """
    sources: list[Path] = []
    if middle_json is not None and Path(middle_json).is_file():
        sources.append(Path(middle_json))
    if parts_dir.is_dir():
        sources.extend(sorted(Path(parts_dir).rglob("*_middle.json")))
    unique: dict[str, Path] = {}
    for path in sources:
        unique.setdefault(str(path.resolve()), path)
    return list(unique.values())


def _stamp_side_by_side_layout(
    ssir_path: Path, parts_dir: Path, *, middle_json: Path | None = None
) -> None:
    """Detect side-by-side (parallel) layout from MinerU geometry and mark it so the
    renderer lays the members out on one row (无边框定位容器，等价 HTML div 布局)。

    规则对应: GEN-095（并列版面通用识别）。识别对象是**同一水平带内 x 分离的
    2~3 组内容**，锚点块可为 image（子图并列）或 interline_equation（公式对照，
    如 GB/T 1.1-2020 9.9.3.1 示例3/4 的「正确/不正确」）。通用规则：

    - 页键用**绝对页号**（分片目录 pages-037-054 → 起始页 37）：MinerU 分片的
      page_idx 各自从 0 起，旧实现按相对页号聚合会把不同分片的同号页混在一起；
    - 几何来源（见 ``_side_by_side_sources``）：``parts/`` 分片目录（merge 起点）与整份文档的
      ``middle.json``（``middle_json=``，raw 起点——云端识别产物就是这份数据）**合并**使用，
      两侧的资产名/LaTeX 锚点都能参与匹配；
    - 通栏块、`示例N：` 题注块、垂距 > 1.5×行高处切分为独立「并列区」，防止把
      同页多处并列/题注混进同一组；
    - 区内先按 x 中心对**锚点块**（图/公式）做 1D 聚类得到列（≥2 列、≤3 列），
      再按块 x 中心到各列 x 区间的距离把区内所有块归属列；
    - 内容映射：图/公式块按 asset basename 匹配注册表；文本块只在**锚点所在父
      节点**内匹配（「正确：/不正确：」等标签在多处出现，跨节点全局匹配会串组）；
      已有 sideBySideGroup（`ssir:columns` 手工声明）的内容绝不覆盖；
    - 收尾校验：≥2 列各有命中，且每个父节点内命中的内容元素 sortOrder **连续
      无空洞**（否则并列组会被渲染端切成多张表）——不满足则整组回滚，不留半组。
    纯文本并列（无任何图/公式锚点）不自动猜测，走 canonical `ssir:columns`。
    """
    try:
        data = json.loads(ssir_path.read_text(encoding="utf-8"))
    except Exception:
        return
    middle_files = _side_by_side_sources(parts_dir, middle_json)
    if not middle_files:
        return

    def _absolute_page(middle_path: Path, page_idx: int) -> int:
        for parent in middle_path.parents:
            match = _PART_PAGE_RANGE_RE.fullmatch(parent.name)
            if match:
                return int(match.group(1)) + int(page_idx)
        return int(page_idx) + 1

    def _block_lines(block: dict) -> list[dict]:
        # image 块的 span 在 blocks[*].lines[*]，text/interline_equation 块直接在
        # lines[*]（MinerU pipeline 后端的两种层级都要取）。
        lines: list[dict] = []
        for sub in block.get("blocks") or []:
            lines.extend(sub.get("lines") or [])
        lines.extend(block.get("lines") or [])
        return lines

    pages: dict[int, list[dict]] = {}
    for middle in middle_files:
        try:
            raw = json.loads(middle.read_text(encoding="utf-8"))
        except Exception:
            continue
        for info in raw.get("pdf_info") or []:
            page_idx = info.get("page_idx")
            if page_idx is None:
                continue
            page_no = _absolute_page(middle, page_idx)
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
                                latex = _latex_key(str(span["content"]))
                        elif span_type == "interline_equation" and span.get("content"):
                            latex = _latex_key(str(span["content"]))
                        elif span_type in ("text", "inline_equation") and span.get("content"):
                            # 行内公式 span 必须并入块文本：变量解释行「$t_i$——…」的
                            # 变量在 inline_equation span 里，只取 text span 会丢掉它
                            # → 与 SSIR 文本（含变量）精确匹配落空（示例5）。
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
    if not pages:
        return

    # 注册表索引：asset basename → figure/formula id。
    figure_by_basename: dict[str, str] = {}
    for figure in data.get("figures") or []:
        ref = figure.get("assetRef")
        if ref:
            figure_by_basename.setdefault(Path(ref).name, figure["id"])
    formula_by_basename: dict[str, str] = {}
    for formula in data.get("formulas") or []:
        ref = formula.get("assetRef")
        if ref:
            formula_by_basename.setdefault(Path(ref).name, formula["id"])
    # 公式的第二匹配键（LaTeX）：云端路线的公式没有裁剪图资产，SSIR 公式节点只有
    # latex/rawText——几何侧同样按 LaTeX 匹配（`_latex_key` 去空白归一）。**一键多值**：
    # 排版相同、几何上分处两列的公式（GB/T 1.1-2020 9.9.3.1 示例4 的「或」前后两条）
    # 共享同一个 LaTeX 键，一对一映射会让第二个几何块拿不到节点 → 组内 sortOrder
    # 出现空洞 → 整组回滚，故按注册表顺序保留候选列表，匹配时取第一个未被占用的。
    formulas_by_latex: dict[str, list[str]] = {}
    for formula in data.get("formulas") or []:
        key = _latex_key(str(formula.get("latex") or formula.get("rawText") or ""))
        if key:
            formulas_by_latex.setdefault(key, []).append(formula["id"])

    contents: list[dict] = []

    def _walk(node: dict) -> None:
        for content in node.get("contentElements") or []:
            contents.append(content)
        for child in node.get("children") or []:
            _walk(child)

    _walk(data.get("structuralRoot") or {})
    content_by_figure = {c.get("figureRef"): c for c in contents if c.get("presentationType") == "figure"}
    content_by_formula = {c.get("formulaRef"): c for c in contents if c.get("presentationType") == "formula"}

    def _norm(text: str) -> str:
        # 匹配用归一（见模块级 ``_fold_match_text``，规则对应: GEN-095）：去空白、去行内
        # 公式定界符 `$`、全/半角标点统一、行内 LaTeX 字体命令脱壳、破折号族压成单个 `—`。
        # MinerU 块文本与 SSIR 文本在标点宽度（`，`/`,`）、内联公式的 LaTeX 拼写
        # （`S_{ME,i}`/`S_{\mathrm{ME},i}`）、破折号长度上都可能不同，不归一会漏配，
        # 漏配的节点在组内留下 sortOrder 空洞 → 整组回滚（示例4/示例5）。
        return _fold_match_text(text)

    def _search_texts(content: dict) -> list[str]:
        if content.get("presentationType") == "list":
            return [_norm(f"{item.get('marker', '')}{item.get('text', '')}") for item in content.get("listItems") or []]
        return [_norm(str(content.get("textContent", "")))]

    def _match_text(text: str, parent_ids: set, used: set[int]) -> dict | None:
        needle = _norm(text)
        if not needle:
            return None
        for content in contents:
            if content.get("sideBySideGroup") or id(content) in used:
                continue
            if content.get("presentationType") not in ("paragraph", "note", "quote", "example", "warning", "list"):
                continue
            if parent_ids and content.get("parentNodeId") not in parent_ids:
                continue
            if needle in _search_texts(content):
                return content
        return None

    def _content_for_asset(asset: str) -> dict | None:
        figure_id = figure_by_basename.get(asset)
        if figure_id:
            return content_by_figure.get(figure_id)
        formula_id = formula_by_basename.get(asset)
        if formula_id:
            return content_by_formula.get(formula_id)
        return None

    def _content_for_block(block: dict, used: set[int]) -> dict | None:
        """几何块 → SSIR 内容元素：先按资产名（本地路线的裁剪图），再按 LaTeX（云端路线）。

        ``used`` 是本次并列区已占用的内容元素集合（`id(content)`）：同一资产名或同一
        LaTeX 可有多个几何块/节点，被占用后必须继续试下一个候选，否则元素缺失会导致
        组内 sortOrder 空洞 → 整组回滚（GB/T 1.1-2020 9.9.3.1 示例4）。
        """

        def _usable(candidate: dict | None) -> bool:
            return bool(candidate) and not candidate.get("sideBySideGroup") and id(candidate) not in used

        if block.get("asset"):
            content = _content_for_asset(str(block["asset"]))
            if _usable(content):
                return content
        key = block.get("latex")
        for formula_id in formulas_by_latex.get(str(key), []) if key else []:
            content = content_by_formula.get(formula_id)
            if _usable(content):
                return content
        return None

    # 已存在的并列组 id（手工 `ssir:columns-N` 或上一轮几何打标）：新一轮打标不得
    # 复用同 id（重复运行/半程续跑时否则会把两组内容并成一个组）。
    used_group_ids = {c.get("sideBySideGroup") for c in contents if c.get("sideBySideGroup")}
    stamped_group = 0
    for page_no in sorted(pages):
        blocks = [b for b in pages[page_no] if b["bbox"][3] > b["bbox"][1]]
        if len(blocks) < 2:
            continue
        frame_x0 = min(b["bbox"][0] for b in blocks)
        frame_x1 = max(b["bbox"][2] for b in blocks)
        frame_width = max(frame_x1 - frame_x0, 1.0)
        heights = sorted(b["bbox"][3] - b["bbox"][1] for b in blocks)
        line_height = heights[len(heights) // 2] or 10.0

        def _is_full_width(block: dict) -> bool:
            return (block["bbox"][2] - block["bbox"][0]) >= _FULL_WIDTH_RATIO * frame_width

        def _is_caption(block: dict) -> bool:
            return bool(_EXAMPLE_CAPTION_RE.match(block.get("text", "")))

        # 切分并列区：通栏块 / 示例题注 / 大垂距处断开。
        segments: list[list[dict]] = []
        current: list[dict] = []
        for block in sorted(blocks, key=lambda item: (item["bbox"][1], item["bbox"][0])):
            if _is_full_width(block) or _is_caption(block):
                if current:
                    segments.append(current)
                    current = []
                continue
            if current and block["bbox"][1] - current[-1]["bbox"][3] > _REGION_GAP_LINES * line_height:
                segments.append(current)
                current = []
            current.append(block)
        if current:
            segments.append(current)

        for segment in segments:
            # 锚点：有资产（裁剪图）或有 LaTeX 的公式/图块——两条抽取路线各占其一。
            anchors = [b for b in segment if b.get("asset") or b.get("latex")]
            if len(anchors) < 2:
                continue
            # 锚点按 x 中心聚类成列（列序 = x 升序）。
            anchor_columns: list[list[dict]] = []
            for anchor in sorted(anchors, key=lambda item: (item["bbox"][0] + item["bbox"][2]) / 2):
                center = (anchor["bbox"][0] + anchor["bbox"][2]) / 2
                if anchor_columns:
                    last_center = (anchor_columns[-1][-1]["bbox"][0] + anchor_columns[-1][-1]["bbox"][2]) / 2
                    if center - last_center <= _ANCHOR_COLUMN_GAP_RATIO * frame_width:
                        anchor_columns[-1].append(anchor)
                        continue
                anchor_columns.append([anchor])
            if not (2 <= len(anchor_columns) <= _MAX_SIDE_COLUMNS):
                continue
            column_ranges = [
                (min(a["bbox"][0] for a in column), max(a["bbox"][2] for a in column))
                for column in anchor_columns
            ]

            def _column_of(block: dict) -> int:
                center = (block["bbox"][0] + block["bbox"][2]) / 2
                best, best_distance = 0, None
                for index, (x0, x1) in enumerate(column_ranges):
                    if x0 <= center <= x1:
                        distance = 0.0
                    else:
                        distance = min(abs(center - x0), abs(center - x1))
                    if best_distance is None or distance < best_distance:
                        best, best_distance = index, distance
                return best

            # 锚点内容的父节点集合（文本匹配的作用域）。assigned 先于本循环建立，
            # 供 _content_for_block 消费「一键多值」的候选（同一 LaTeX 对应多个节点）。
            assigned: set[int] = set()
            parent_ids: set = set()
            for anchor in anchors:
                content = _content_for_block(anchor, assigned)
                if content is not None and not content.get("sideBySideGroup"):
                    parent_ids.add(content.get("parentNodeId"))
            if not parent_ids:
                continue

            pending: list[tuple[dict, int]] = []
            # 同文本内容去重（GB/T 1.1-2020 9.9.3.1 示例5 两列各有「式中：」与同形
            # 变量解释行）：按**行（y 容差 0.6 行高）+ x** 顺序匹配，同文本的第 n 次
            # 出现对应 sortOrder 序的第 n 个候选——否则重复文本永远命中第一个、后一列
            # 的内容落空 → 组内 sortOrder 出现空洞 → 整组被回滚。行聚类用容差而非
            # 取整分桶：两列同一行的块 y 可能差 1–2pt，取整会把左右列拆到不同行。
            rows: list[dict] = []
            for block in sorted(segment, key=lambda item: (item["bbox"][1], item["bbox"][0])):
                if rows and abs(block["bbox"][1] - rows[-1]["ref"]) <= 0.6 * line_height:
                    rows[-1]["blocks"].append(block)
                else:
                    rows.append({"ref": block["bbox"][1], "blocks": [block]})
            ordered_segment = [
                block
                for row in rows
                for block in sorted(row["blocks"], key=lambda item: item["bbox"][0])
            ]
            for block in ordered_segment:
                column = _column_of(block)
                content = None
                if block.get("asset") or block.get("latex"):
                    content = _content_for_block(block, assigned)
                if content is None:
                    content = _match_text(block.get("text", ""), parent_ids, assigned)
                    if content is None:
                        for span_text, *_ in block.get("spans") or []:
                            content = _match_text(span_text, parent_ids, assigned)
                            if content is not None:
                                break
                if content is None or content.get("sideBySideGroup") or id(content) in assigned:
                    continue
                assigned.add(id(content))
                pending.append((content, column))
            if len({column for _, column in pending}) < 2:
                continue
            # 每个父节点内命中的内容元素 sortOrder 必须连续（否则渲染端会切表）。
            by_parent: dict[str, list[dict]] = {}
            for content, _ in pending:
                by_parent.setdefault(str(content.get("parentNodeId")), []).append(content)
            contiguous = True
            for group_contents in by_parent.values():
                orders = sorted(int(item.get("sortOrder", 0)) for item in group_contents)
                if orders[-1] - orders[0] + 1 != len(orders):
                    contiguous = False
                    break
            if not contiguous:
                # 回滚原因必须留痕：组内某节点未被几何块匹配上（标点/内联公式拼写/资产名
                # 两条路线不一致）会让组内 sortOrder 出现空洞，静默回滚无法定位（诊断代价高）。
                _log(
                    f"Side-by-side region skipped (page {page_no}, y≈{segment[0]['bbox'][1]:.0f}): "
                    f"matched content is not contiguous in its parent node "
                    f"{ {k: sorted(int(i.get('sortOrder', 0)) for i in v) for k, v in by_parent.items()} }"
                )
                continue

            while f"p{page_no:03d}-c{stamped_group:02d}" in used_group_ids:
                stamped_group += 1
            group_id = f"p{page_no:03d}-c{stamped_group:02d}"
            used_group_ids.add(group_id)
            for content, column in pending:
                content["sideBySideGroup"] = group_id
                content["sideBySideColumn"] = column
            stamped_group += 1
            _log(f"Side-by-side group {group_id}: page {page_no}, {len(anchor_columns)} columns, "
                 f"{len(pending)} element(s)")

    if stamped_group:
        ssir_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        _log(f"Side-by-side layout stamped: {stamped_group} group(s)")


def _post_parse_verify_render(args: argparse.Namespace, state: dict[str, Any],
                              paths: dict[str, Path], ssir: Path | None) -> None:
    """parse 之后公共尾部：render（PDF）→ manifest；roundtrip 仅当调用方显式要求时执行。

    名称保留（调用方与测试沿用），但**验证已独立**：回环验证与 PDF 对比由
    ``tools/verify_conversion.py`` 按需单独运行，构建流程默认不做任何验证
    （``args.roundtrip`` 为 False，``compare`` 不再在此调用）。
    """
    if args.roundtrip and ssir:
        roundtrip = [
            str(Path(sys.prefix) / "bin" / "ssir"), "csm", "roundtrip",
            "--input", str(paths["canonical"]), "--render-md-output", str(paths["render_md"]),
            "--verify-output", str(paths["verify"]), "--report", str(paths["roundtrip"]),
        ]
        _log("Running SSIR round-trip verification (canonical -> SSIR -> render.md -> verify)")
        result = subprocess.run(roundtrip, cwd=ROOT)
        if result.returncode not in (0, 3):
            raise RuntimeError("SSIR round-trip verification failed")
        _log(f"Round-trip result: {result.returncode} (0 = equivalent; 3 = critical information loss)")
    if args.render and ssir:
        render = [
            str(Path(sys.prefix) / "bin" / "ssir"), "pdf", "render",
            "--input", str(paths["ssir"]), "--output", str(paths["render_pdf"]),
            "--report", str(paths["render_report"]), "--toc-depth", args.toc_depth,
        ]
        _log("Rendering SSIR JSON as a traditional standard-style PDF")
        if subprocess.run(render, cwd=ROOT).returncode:
            raise RuntimeError("SSIR PDF renderer failed")
        # PDF 版面/文本量对比属**验证**，已随回环验证一起剥离到独立程序
        # tools/verify_conversion.py（引擎：leleby_ssir.pdf_compare.compare）；
        # 构建流程只负责产出 render.pdf。
    _write_manifest(args, state, status="completed")



# 表注锚点上标字母回收（CSM-OCR-015，2026-09-06，GB_T_20001.10-2014 表1）：
# 表注（如“a 黑体表示…”，GBT-X04/GBT-C18）的单元格锚点是小写拉丁上标字母。
# MinerU OCR 常在表格组装时把表头/单元格里跟上标字母整段丢弃，只剩表注定义行
# （表内末行“a说明…”）——GB_T_20001.5-2017 同模板表保留了（“表述形式a”），
# 20001.10 的源 PDF 文本层两版都有（“表述形式”+上标 a，4.66pt vs 正文 8.25pt）。
# mineru_html._restore_table_footnote_markers（GBT-C18）只能按“注文包含单元格
# 文本”恢复（GB/T 1.1 匝间绝缘型），注文不含锚点文本（字体样式说明型）时无从
# 匹配——此处从源 PDF 文本层几何补盲。
_TABLE_NOTE_DEF_CELL_RE = re.compile(r"^([a-zA-Z])(?:[ \u3000]+)?(?=[\u4e00-\u9fff])")


_TABLE_NOTE_DEF_CELL_RE = re.compile(r"^([a-zA-Z])(?:[ \u3000]+)?(?=[\u4e00-\u9fff])")
# 表注定义行的“注文拆条”：注文标记（小写字母）出现在句末标点之后或单元格行首，
# 且后随汉字/引号——用于把“a注文…b注文…”连排单元格拆成逐条注（GB_T_5171.1-2014
# 表19 a/b、表20 a~h 型，MinerU 把整段连排进一格且丢字）。
_TABLE_NOTE_ITEM_SPLIT_RE = re.compile(r"(?:(?<=^)|(?<=[。；;，,、:：])|\s(?=[a-z]))\s*([a-z])(?=[\u4e00-\u9fff“”『「\"'])")


def _plain_note_cell_text(cell: str) -> str:
    """表注单元格去角标标记后的纯注文文本（开标记 → 其角标字符、闭标记删除）。

    供表注行判型与“连排注文拆条”使用——对已 token 化的单元格（新通用形式
    ``[:sup:a]注文[:/sup]`` 或迁移前的旧形式 ``[^a]注文[^a/]``）同样可还原出注文
    本体，保证恢复流程幂等（结果只取决于注文文本本身）。
    """
    from leleby_ssir.parser import INLINE_SCRIPT_CLOSE_RE, INLINE_SCRIPT_OPEN_RE

    text = INLINE_SCRIPT_CLOSE_RE.sub("", str(cell))
    text = INLINE_SCRIPT_OPEN_RE.sub(lambda m: m.group(2), text)
    text = re.sub(r"\[\^([a-z])/\]", "", text)  # 旧形式（迁移期兼容）
    return re.sub(r"\[\^([a-z])\]", r"\1", text)


def _cell_note_letters(plain: str) -> set[str]:
    """整格纯注文里出现的注文标记字母集合（含 <br> 分隔的段首字母）。

    跨段取并集：拆条按 `<br>` 分段进行，但“该条字母是否已在文本里”必须按**整格**
    判断——否则同一格里已带标记的条（如 f）在其后续段的补位检索中会被另一条的
    头文本截短匹配误配（表20 f/g 两条都以“只有在产品标准中规定了”起头）。
    """
    pattern = re.compile(
        r"(?:(?<=^)|(?<=[。；;，,、:：])|(?<=<br>)|(?<=\s))\s*([a-z])(?=[\u4e00-\u9fff“”『「\"])"
    )
    return {match.group(1) for match in pattern.finditer(plain)}


def _note_item_boundaries(
    plain: str, note_defs: list[tuple[str, str]], known_letters: set[str] | None = None
) -> list[tuple[str, int, int]]:
    """连排注文 → 逐条注的 (字母, 标记位, 注文本体起点) 列表。

    两类证据（任一命中即定界，都不命中则不拆）：
    - md 文本自身的注文标记：句末标点/行首之后的“小写字母 + 汉字/引号”——标记
      字母就在正文里（标记位 = 字母位置，正文起点 = 其后一位）；
    - 源 PDF 表注定义行的 (字母, 注文头)：md 把注文标记字母读丢时（GB_T_5171.1-2014
      表20 的 d/e/f 即如此，MinerU 只留下注文文字），用注文头文本在**上一条之后**
      定位该条起点（标记位 = 正文起点）；头文本按 12→10→8→6 字逐级缩短匹配，仍
      找不到就不拆（不猜）。游标按注文顺序推进（md 标记与 PDF 补位共用同一游标），
      避免“上一条之后”被排在后文的 md 标记带偏（否则 d/e 会被后面的 g 挡住）。
      已由 ``known_letters``（整格已出现的字母）覆盖的条不补位：该条在别处已有
      标记，在本段里检索只会撞上相邻条的头文本。
    """
    ordered = sorted((match.start(1), match.group(1)) for match in _TABLE_NOTE_ITEM_SPLIT_RE.finditer(plain))
    positions = {letter: offset for offset, letter in ordered}
    marks: list[tuple[int, int, str]] = [(offset, offset + 1, letter) for offset, letter in ordered]
    claimed = {start for _mark, start, _letter in marks}
    cursor = 0
    for letter, head in note_defs:
        if letter in positions or (known_letters and letter in known_letters):
            cursor = max(cursor, positions.get(letter, 0))
            continue
        probe = re.sub(r"\s+", "", head)
        for length in (12, 10, 8, 6):
            candidate = probe[:length]
            if len(candidate) < 6:
                continue
            # 从游标处（含）开始找：注文头可能正好落在本段起点（<br> 分段后
            # 每条注文自成一段时即如此），cursor+1 会漏掉起点命中。
            found = plain.find(candidate, cursor)
            if found >= 0 and found not in claimed:
                marks.append((found, found, letter))
                claimed.add(found)
                cursor = found
                break
    marks.sort()
    return [(letter, mark, start) for mark, start, letter in marks]


def _wrap_note_items(plain: str, marks: list[tuple[str, int, int]]) -> str:
    """逐条注包装为通用角标标记 ``[:sup:x]注文[:/sup]``（连排，不写 ``<br>``）。

    ``marks`` 的元组是 (字母, 标记位, 注文本体起点)：注文区间取到**下一条标记位**
    为止，md 里残存的字面标记字母因此不会混进上一条注文（PDF 补位条的标记位与正文
    起点相同，无字面字母可留）。多条注在同一单元格内**连排**——标记成对自定界，
    渲染端在相邻两对之间自动换行（2026-09-11 用户裁定，docs/07 §6.7）。
    规则对应: GBT-X04 / GBT-C18 执行侧。
    """
    if not marks:
        return plain
    parts: list[str] = []
    residue = plain[: marks[0][1]].strip()
    if residue:
        parts.append(residue)  # 首条标记之前的残留文本（罕见）原样保留
    for index, (letter, _mark, start) in enumerate(marks):
        end = marks[index + 1][1] if index + 1 < len(marks) else len(plain)
        text = plain[start:end].strip()
        parts.append(f"[:sup:{letter}]{text}[:/sup]" if text else f"[:sup:{letter}/]")
    return "".join(parts)


def _cluster_visual_lines(spans: list[dict], tolerance: float = 5.0) -> list[list[dict]]:
    """按**基线**（origin[1]）聚类视觉行，容差 5pt。

    不能按 bbox 顶（bbox[1]）聚类：同一表格行里中文字体（CJK ascender ≈0.89）与
    西文字体（≈1.33）的字框顶差可达 size×0.45 ≈ 4pt，按 bbox 顶聚类会把锚文本与
    紧随它的上标角标拆成两行——GB_T_5171.1-2014 表20 第 7/10 行的 d/e 即因此漏检。
    表格行间距 ≈15pt，5pt 容差不会把相邻行并成一行。
    （回归测试: tests/test_mineru_table_note_markers.py::VisualLineClusteringTests）
    """
    ordered = sorted(spans, key=lambda s: (s["origin"][1], s["origin"][0]))
    lines: list[list[dict]] = []
    for span in ordered:
        if lines and abs(span["origin"][1] - lines[-1][0]["origin"][1]) <= tolerance:
            lines[-1].append(span)
        else:
            lines.append([span])
    return lines


def _recover_table_note_markers(markdown: str, pdf: Path) -> tuple[str, int]:
    """Recover trailing table-note superscript letters lost by OCR (CSM-OCR-015).

    现象（GB_T_20001.10-2014 表1）：源 PDF 表头第 3 列“要素所允许的表述形式”末尾
    带 4.66pt 上标 a（正文 8.25pt），MinerU OCR 表组装时把它整段丢弃，只留下表内
    末行的表注定义行“a黑体表示…”。渲染后表注解释在、锚点标记丢，不成对。

    恢复规则（保守、通用、幂等）：
    - 源 PDF 文本层找“正文行内、字号 ≤0.72×正文中位（≤7.8pt）、单小写拉丁字母”
      的上标 span，其 x0 与同一视觉行上紧邻的前一正文 span 的 x1 相邻（±2~6pt），
      该正文 span 文本即锚文本（锚文本必须汉字收尾——渲染端只上标汉字后字母）；
    - 该上标字母必须是当前 md 表格分组的“表注定义行”（唯一非空单元格以
      “字母+汉字”开头，如“a黑体…”）所声明的字母——无定义行的字母不猜；
    - 锚文本命中分两形态：尾部（单元格以其结尾，字母补到末尾）与词中（锚文本
      后紧接汉字——“要素a的编排”型，字母补到锚文本之后）；每形态都在表格分组
      内**恰好一个**单元格命中才补字母，词中归属不唯一（多个单元格含同一锚文本
      + 汉字，如表头两列同以“要素”开头）不猜——几何-列边界对齐留待后续；
    - 找不到唯一匹配/定义行缺失/字母已存在 → 不改。幂等：已恢复的单元格以
      字母结尾（尾部）或锚文本后已跟该字母（词中），再次运行不重复补。
    2026-09-07（语法定案）输出改为**显式标记**；2026-09-11 起标记通用化为
    “行内角标标记”（docs/07 §6.7）：锚点补回写自闭合引用点 ``[:sup:x/]``，
    表注定义行逐条改写为 ``[:sup:x]注文[:/sup]``（多条以 <br> 分隔同格排布；
    段首字母可后随引号/汉字）。已 token 化的内容幂等（先还原纯注文再重新拆条，
    结果只取决于注文文本；锚点命中检查对已带标记的单元格天然不再匹配）。
    规则对应: GBT-X04（表注由标记与解释成对组成）/ GBT-C18（表脚注上标）；
    执行侧工程规则，与 GFM 脚注回收 CSM-OCR-014 同族；渲染端按显式标记还原
    上角标（pdf_renderer._table_cell_superscripts）。
    """
    try:
        import pymupdf
    except ImportError:
        return markdown, 0
    if not pdf.is_file():
        return markdown, 0

    # —— 1) md 表格行分组（连续管道行），并取各组的表注定义行字母 ——
    lines = markdown.split("\n")
    groups: list[list[int]] = []
    current: list[int] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            current.append(i)
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    if not groups:
        return markdown, 0

    def row_cells(line: str) -> list[str]:
        """md 管道行的单元格文本（剥外管、去首尾空白）。"""
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            return []
        return [part.strip() for part in stripped[1:-1].split("|")]

    def note_cell_slots(row_indexes: list[int]) -> list[tuple[int, int]]:
        """表注定义行：分组内**单个非空单元格**且以“注文标记 + 汉字/引号”开头的行。

        返回 (行号, 单元格序号)。判型在去显式标记后的纯注文上进行（已 token 化的
        注文行同样识别，保证幂等）。
        """
        slots: list[tuple[int, int]] = []
        for i in row_indexes:
            raw_cells = row_cells(lines[i])
            filled = [k for k, cell in enumerate(raw_cells) if cell]
            if len(filled) != 1:
                continue
            if _TABLE_NOTE_DEF_CELL_RE.match(_plain_note_cell_text(raw_cells[filled[0]])):
                slots.append((i, filled[0]))
        return slots

    # —— 2) 源 PDF 文本层：正文行内的上标小写字母 span → (锚文本, 字母)；
    #         行首（其前无紧邻正文 span）的上标小写字母 → 表注定义行的 (字母, 注文头) ——
    candidates: list[tuple[str, str]] = []
    note_defs: list[tuple[str, str]] = []
    with pymupdf.open(pdf) as document:
        for page in document:
            spans: list[dict] = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        if span["text"].strip():
                            spans.append(span)
            if not spans:
                continue
            sizes = sorted(s["size"] for s in spans)
            body_median = sizes[len(sizes) // 2]
            sup_threshold = min(body_median * 0.72, 7.8)
            for vline in _cluster_visual_lines(spans):
                vline.sort(key=lambda s: s["origin"][0])
                for idx, sup in enumerate(vline):
                    letter = sup["text"].strip()
                    if sup["size"] > sup_threshold or not re.fullmatch(r"[a-z]", letter):
                        continue
                    anchor: dict | None = None
                    for j in range(idx - 1, -1, -1):
                        prev = vline[j]
                        if prev["size"] <= sup_threshold:
                            continue
                        dx = sup["bbox"][0] - prev["bbox"][2]
                        if -2 <= dx <= 6:
                            anchor = prev
                        break  # 只看紧邻（可含中间上标）的最近正文 span
                    if anchor is not None:
                        anchor_text = anchor["text"].strip()
                        if not anchor_text or not re.search(r"[\u4e00-\u9fff]$", anchor_text):
                            continue  # 渲染端只上标汉字后的字母，非汉字收尾锚不补
                        pair = (anchor_text, letter)
                        if pair not in candidates:
                            candidates.append(pair)
                        continue
                    # 其上没有紧邻正文 span → 这是**表注定义行**的行首注文标记
                    # （“a 注文…”）；同视觉行紧随其后的正文 span 文本即该条注文头，
                    # 供 md 丢掉注文标记字母时定位该条注文的起点。
                    following = next((s for s in vline[idx + 1:] if s["size"] > sup_threshold), None)
                    if following is None:
                        continue
                    head = re.sub(r"\s+", "", following["text"].strip())
                    if len(head) >= 6 and sup["bbox"][2] <= following["bbox"][0] + 8:
                        item = (letter, head)
                        if item not in note_defs:
                            note_defs.append(item)
    if not candidates and not note_defs:
        return markdown, 0

    # —— 3) 锚文本在含对应字母定义行的分组里命中单元格 → 补字母 ——
    # 两形态（2026-09-06 补词中）：
    #   a) 尾部锚点：单元格以锚文本结尾 → 字母补到单元格文本末尾（原逻辑）；
    #   b) 词中锚点：单元格内锚文本后紧接汉字（“要素a的编排”型，上标夹在
    #      两个汉字之间）→ 字母补到锚文本之后。两种均要求全组唯一命中；
    #      词中归属不唯一（多个单元格含同一锚文本+汉字，如表1 表头两列都从
    #      “要素”开头）时不猜——需单元格几何对齐列边界，留待后续。
    recovered = 0
    for group in groups:
        note_slots = note_cell_slots(group)
        if not note_slots:
            continue
        # 表注定义行 token 化：把“a注文…b注文…”连排注文逐条改写为通用角标标记
        # “[:sup:x]注文[:/sup]”（多条以 <br> 分隔同格排布）；md 丢掉的注文
        # 标记字母用源 PDF 的注文头文本定位后补回。幂等：先去掉既有标记还原纯注文
        # 再重新拆条，结果只取决于注文文本本身。
        group_letters: set[str] = set()
        for line_index, cell_index in note_slots:
            pipes = [k for k, ch in enumerate(lines[line_index]) if ch == "|"]
            if len(pipes) < cell_index + 2:
                continue
            start, end = pipes[cell_index] + 1, pipes[cell_index + 1]
            raw_cell = lines[line_index][start:end]
            plain = _plain_note_cell_text(raw_cell)
            cell_letters = _cell_note_letters(plain)
            tagged: list[str] = []
            # 兼容既有 canonical 的 <br> 分格写法（新格式连排，无需 <br>）。
            for segment in re.split(r"<br>", plain):
                boundaries = _note_item_boundaries(segment, note_defs, cell_letters)
                group_letters.update(letter for letter, _mark, _start in boundaries)
                tagged.append(_wrap_note_items(segment, boundaries))
            wrapped = "".join(tagged)
            if wrapped.strip() != raw_cell.strip():
                lead = raw_cell[: len(raw_cell) - len(raw_cell.lstrip())]
                trail = raw_cell[len(raw_cell.rstrip()):]
                lines[line_index] = lines[line_index][:start] + lead + wrapped + trail + lines[line_index][end:]
                recovered += 1
        if not group_letters:
            continue
        for anchor_text, letter in candidates:
            if letter not in group_letters:
                continue
            # 形态 a：尾部。目标行以锚文本结尾 → 补 [:x]；已带字面字母时仅在
            # “锚文本+该字母”同尾（几何确认为上标）时把字面字母改写为 [:x]；
            # 末位是单个数字（OCR 把上标标记读成数字，'g'→'8' 型）时同样改写。
            tail_targets: list[tuple[int, int]] = []
            literal_tail_targets: list[tuple[int, int]] = []
            mangled_tail_targets: list[tuple[int, int]] = []
            for i in group:
                for cell_index, cell in enumerate(row_cells(lines[i])):
                    latin_tail = re.search(r"[A-Za-z]$", cell)
                    if latin_tail:
                        if cell[-1] == letter and cell[:-1].rstrip().endswith(anchor_text):
                            literal_tail_targets.append((i, cell_index))
                        continue
                    if cell.endswith(anchor_text):
                        tail_targets.append((i, cell_index))
                        continue
                    # 锚文本 + 单个数字收尾且数字前不是数字（排除多位数值尾部），
                    # 几何上该数字正是源 PDF 里锚文本之后的上标标记位（CSM-OCR-015）。
                    if re.search(r"(?<![0-9])[0-9]$", cell) and cell[:-1].rstrip().endswith(anchor_text):
                        mangled_tail_targets.append((i, cell_index))
            if len(tail_targets) == 1:
                line_index, cell_index = tail_targets[0]
                patched = _insert_table_cell_marker(lines[line_index], cell_index, letter)
                if patched != lines[line_index]:
                    lines[line_index] = patched
                    recovered += 1
                continue
            if len(tail_targets) == 0 and len(literal_tail_targets) + len(mangled_tail_targets) == 1:
                # OCR 保留了字面锚点字母（如 20001.5 表1 “表述形式a”）：渲染端
                # 不再做字形猜测，此处把字面字母改写为显式 [:x] 引用点。
                line_index, cell_index = (literal_tail_targets or mangled_tail_targets)[0]
                line = lines[line_index]
                pipes = [k for k, ch in enumerate(line) if ch == "|"]
                if len(pipes) > cell_index + 1:
                    start, end = pipes[cell_index] + 1, pipes[cell_index + 1]
                    raw = line[start:end]
                    replace_at = start + len(raw.rstrip()) - 1  # 末尾字母（去行尾空白定位）
                    lines[line_index] = line[:replace_at] + f"[:sup:{letter}/]" + line[replace_at + 1:]
                    recovered += 1
                continue
            # 形态 b：词中。锚文本在单元格中部出现、后随汉字、该处尚未有该字母。
            mid_targets: list[tuple[int, int, int]] = []  # (line_index, cell_index, offset_after_anchor)
            for i in group:
                for cell_index, cell in enumerate(row_cells(lines[i])):
                    position = cell.find(anchor_text)
                    if position < 0:
                        continue
                    after = position + len(anchor_text)
                    if after >= len(cell):
                        continue  # 锚文本在词尾 → 形态 a 已覆盖
                    if not ("\u4e00" <= cell[after] <= "\u9fff"):
                        continue  # 后随非汉字 → 不是词中上标位
                    if cell[after] == letter:
                        continue  # 幂等：该字母已在
                    mid_targets.append((i, cell_index, after))
            if len(mid_targets) != 1:
                continue
            line_index, cell_index, offset = mid_targets[0]
            patched = _insert_table_cell_marker_at(lines[line_index], cell_index, letter, offset)
            if patched != lines[line_index]:
                lines[line_index] = patched
                recovered += 1
    if not recovered:
        return markdown, 0
    return "\n".join(lines), recovered


def _insert_table_cell_marker(line: str, cell_index: int, letter: str) -> str:
    """把表注引用点 token [:x] 插到管道行第 cell_index 个单元格文本末尾。

    2026-09-07 语法定案（docs/07 §6.7）：锚点以显式 [:x] 标记写回，渲染端按
    标记还原上角标，不再做字形猜测。
    """
    pipes = [i for i, ch in enumerate(line) if ch == "|"]
    if len(pipes) < 2 or cell_index < 0 or cell_index >= len(pipes) - 1:
        return line
    start, end = pipes[cell_index] + 1, pipes[cell_index + 1]
    text = line[start:end]
    insert_at = start + len(text.rstrip())
    return line[:insert_at] + f"[:sup:{letter}/]" + line[insert_at:]


def _insert_table_cell_marker_at(line: str, cell_index: int, letter: str, offset_in_cell: int) -> str:
    """把表注引用点 token [:x] 插到管道行第 cell_index 个单元格文本内 offset 处。

    offset_in_cell 以单元格**首个非空白字符**为 0 计数（md 单元格可能带首部空格，
    行内偏移与 row_cells 的去空白视图对齐）。词中锚点（“要素a的编排”型）写回
    [:x] 标记；渲染端按标记还原上角标。
    """
    pipes = [i for i, ch in enumerate(line) if ch == "|"]
    if len(pipes) < 2 or cell_index < 0 or cell_index >= len(pipes) - 1:
        return line
    start = pipes[cell_index] + 1
    raw = line[start:pipes[cell_index + 1]]
    lead = len(raw) - len(raw.lstrip(" \u3000"))
    insert_at = start + lead + offset_in_cell
    if insert_at < start or insert_at > pipes[cell_index + 1]:
        return line
    return line[:insert_at] + f"[:sup:{letter}/]" + line[insert_at:]


def _recover_pdf_footnotes(md_path: Path, pdf: Path) -> int:
    """从源 PDF 文本层回收上标脚注并写入 markdown 基线（GFM 语法，CSM-OCR-014）。

    MinerU 文本抽取把上标标记与正文粘连（“—2003”+1)→“—20031”；“单独的标准”+2)→
    “标准2。”），页底 8pt 解释行被当普通正文。用 pymupdf 读源 PDF：
    - 上标 span（字号显著小于正文）识别条文脚注标记“N)”，按 页→位置 全文连续编号；
    - md 尚无 “[^N]” 时，把粘连进正文的数字还原为 “[^N]”（锚定=标记左侧整段正文
      文本窗口，窗口+数字唯一且后随汉字/句末标点才替换，否则不猜）；
    - 页底小字解释行（y≥0.70×页高、字号≤8.5、以 数字) 开头，续行带合并）转
      “[^N]: 文本”；md 已有 “N） 文本” 残留正文段就地改前缀，否则插到锚点段后。
    幂等/自愈：已有 “[^N]: ” 定义的条目跳过；已有 “[^N]” 标记而缺定义（半途产物）
    时只补定义不改正文。只处理阿拉伯数字上标（条文脚注 GBT-X04）。返回处理条数。
    """
    try:
        import fitz  # type: ignore
    except ImportError:
        return 0
    import re as _re
    text = md_path.read_text(encoding="utf-8")
    markers: list[tuple[int, str, int, float]] = []  # (页, 原标记, y, x0)
    notes: list[tuple[int, str, str]] = []  # (页, 原标记, 定义文本)
    with fitz.open(pdf) as document:
        for page_index in range(len(document)):
            page = document[page_index]
            height = page.rect.height
            spans: list[dict] = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        if span["text"].strip():
                            spans.append(span)
            sizes = sorted(s["size"] for s in spans)
            body_median = sizes[len(sizes) // 2] if sizes else 10.0
            sup_threshold = min(body_median * 0.72, 7.8)
            sup = sorted(
                (s for s in spans if s["size"] <= sup_threshold),
                key=lambda s: (s["bbox"][1], s["bbox"][0]),
            )
            i = 0
            while i < len(sup):
                band = [sup[i]]
                j = i + 1
                while j < len(sup) and abs(sup[j]["bbox"][1] - band[0]["bbox"][1]) <= 3.5 and sup[j]["bbox"][0] <= band[-1]["bbox"][2] + 6:
                    band.append(sup[j])
                    j += 1
                token = "".join(s["text"] for s in sorted(band, key=lambda s: s["bbox"][0])).strip()
                if token and token[0].isdigit() and token.endswith((")", "）")):
                    markers.append((page_index, token, band[0]["bbox"][1], band[0]["bbox"][0]))
                i = j
            bottom = sorted(
                (s for s in spans if s["size"] <= 8.5 and s["bbox"][1] >= height * 0.68),
                key=lambda s: (s["bbox"][1], s["bbox"][0]),
            )
            band_lines: list[tuple[float, str]] = []
            cur: list[tuple[float, float, str]] = []
            band_y: float | None = None
            for s in bottom:
                y0 = s["bbox"][1]
                if band_y is None or abs(y0 - band_y) <= 4:
                    cur.append((s["bbox"][0], y0, s["text"]))
                    band_y = cur[0][1]
                else:
                    band_lines.append((band_y, "".join(it for _, _, it in sorted(cur)).strip()))
                    cur = [(s["bbox"][0], y0, s["text"])]
                    band_y = y0
            if cur:
                band_lines.append((band_y, "".join(it for _, _, it in sorted(cur)).strip()))
            idx = 0
            while idx < len(band_lines):
                y, line = band_lines[idx]
                m = _re.match(r"^(\d+)[)）](.*)$", line, _re.S)
                if not m:
                    idx += 1
                    continue
                text_def = m.group(2).strip()
                next_y = y
                while idx + 1 < len(band_lines):
                    ny, nline = band_lines[idx + 1]
                    if _re.match(r"^\d+[)）]", nline) or nline.startswith("注") or _re.fullmatch(r"\d{1,3}", nline) or ny - next_y > 30:
                        break
                    text_def += nline
                    next_y = ny
                    idx += 1
                notes.append((page_index, f"{m.group(1)})", text_def))
                idx += 1
    if not markers:
        return 0
    markers.sort(key=lambda m: (m[0], m[2], m[3]))
    note_by = {(pg, lbl): txt for pg, lbl, txt in notes}
    any_marker = "[^" in text
    new_text = text
    defs: list[tuple[str, str, str]] = []  # (原标记, label, 定义)
    replaced = 0
    with fitz.open(pdf) as document:
        for order, (page_index, token, my, mx) in enumerate(markers, start=1):
            label = str(order)
            digits = token[:-1]
            def_text = note_by.get((page_index, token), "")
            if _re.search(rf"\[\^{re.escape(label)}\]:", new_text):
                continue
            if def_text:
                defs.append((token, label, def_text))
                replaced += 1
            if any_marker or f"[^{label}]" in new_text:
                continue
            page_obj = document[page_index]
            norm = []
            for block in page_obj.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        if span["text"].strip() and span["size"] > 7.8:
                            norm.append(span)
            left = [s for s in norm if abs(s["bbox"][1] - my) <= 6 and s["bbox"][2] <= mx + 1]
            if not left:
                continue
            run_text = "".join(s["text"] for s in sorted(left, key=lambda s: s["bbox"][0])).strip()
            hit = -1
            tail_used = ""
            for tail in (run_text[-24:], run_text[-12:], run_text[-6:]):
                if not tail:
                    continue
                fused = tail + digits
                pos = 0
                while True:
                    h = new_text.find(fused, pos)
                    if h < 0:
                        break
                    before_ok = h == 0 or not new_text[h - 1].isdigit()
                    after = new_text[h + len(fused)] if h + len(fused) < len(new_text) else ""
                    if before_ok and after and (after in "。；，、：）】" or "\u4e00" <= after <= "\u9fff"):
                        hit = h
                        tail_used = tail
                        break
                    pos = h + 1
                if hit >= 0:
                    break
            if hit < 0 or not tail_used:
                continue
            new_text = new_text[: hit + len(tail_used)] + f"[^{label}]" + new_text[hit + len(tail_used) + len(digits):]
    if not defs:
        return 0
    final_text = _place_footnote_definitions(new_text, defs)
    md_path.write_text(final_text, encoding="utf-8")
    return replaced


def _place_footnote_definitions(markdown_text: str, defs: list[tuple[str, str, str]]) -> str:
    """把回收的脚注定义写进 markdown：GFM “[^N]: 文本” 独立段（幂等）。

    ``defs`` = [(原页底标记如 "1)", 标签如 "1", 定义文本), …]，只含当前缺定义的标签。
    - 正文残留的 “N） 文本”/“N) 文本” 段就地改前缀为 “[^N]: 文本”（自愈）；
    - 否则在含 “[^N]” 标记的段块之后插入定义行，**前后均以空行隔离**：
      定义行绝不离散粘贴到下一内容行（否则与下一条目并成一个多行段落块，parser
      的“整行定义”形态无法归类——GB_T_20001.10-2014 脚注 1 曾因此以正文段落身份
      渲染）；插入点越过锚点段与段后空行带、落在其后首个非空内容行之前，定义
      不会被插进列表条目序列中间。返回新文本（无插入/转换时逐字节不变）。
    """
    lines = markdown_text.split("\n")
    insert_before: dict[int, list[str]] = {}
    for token, label, def_text in defs:
        if f"[^{label}]:" in markdown_text:
            continue  # 幂等：定义已存在
        num = token[:-1]
        converted = False
        for i, ln in enumerate(lines):
            stripped = ln.lstrip()
            indent = ln[: len(ln) - len(stripped)]
            if stripped.startswith(f"{num}) ") or stripped.startswith(f"{num}） "):
                rest = stripped.split(" ", 1)[1]
                lines[i] = f"{indent}[^{label}]: {rest}"
                converted = True
                break
            if stripped.startswith(f"{num}）") or stripped.startswith(f"{num})"):
                rest = stripped[len(num) + 1:].lstrip()
                lines[i] = f"{indent}[^{label}]: {rest}"
                converted = True
                break
        if converted:
            continue
        anchor_line = next((i for i, ln in enumerate(lines) if f"[^{label}]" in ln), None)
        if anchor_line is None:
            continue  # 锚点标记不在（半途产物）→ 不猜
        # 越过锚点段连续非空行（同段多行）与段后空行带 → 插入点 = 段后首个内容行
        j = anchor_line + 1
        while j < len(lines) and lines[j].strip():
            j += 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        insert_before.setdefault(j, []).append(["", f"[^{label}]: {def_text}", ""])
    if not insert_before:
        return "\n".join(lines)
    final: list[str] = []
    for i, ln in enumerate(lines):
        for extra in insert_before.get(i, ()):
            final.extend(extra)
        final.append(ln)
    for extra in insert_before.get(len(lines), ()):
        final.extend(extra)
    return "\n".join(final)


def _run_from_existing_canonical(args: argparse.Namespace, state: dict[str, Any], canonical: Path) -> int:
    """已有 curated canonical（02_canonical/<stem>.canonical.md）时的续跑入口。

    跳过 MinerU OCR/PDF 抽取、合并与 normalize——绝不覆盖人工编辑的 canonical
    （AGENTS.md §0.1/§2），从 parse 开始执行与 tools/reprocess_canonical.py
    完全等同的后续阶段：parse -> SSIR →（PDF 源）版面印记恢复 → roundtrip →
    render（PDF）→ compare → manifest。
    规则对应：build=GEN-050/052；verify=GEN-051/090/091 + 三层合规；
    render=GEN-070—076；版面印记恢复沿用 finalize 的 stamp 逻辑。
    """
    stem = args.output_stem or args.input.stem
    paths = _stage_paths(args.output_dir, stem)
    for stage_path in (paths["ssir"], paths["render_pdf"], paths["render_md"], paths["verify"]):
        stage_path.parent.mkdir(parents=True, exist_ok=True)
    # provenance 保留：pipeline-state 可能缺 title/number/sha，回退旧 manifest
    old_manifest = _load_json(args.output_dir / "manifest.json", {})
    state.setdefault("title", old_manifest.get("title", ""))
    state.setdefault("number", old_manifest.get("standardNumber", ""))
    state.setdefault("createdAt", old_manifest.get("created"))
    if not state.get("sourceSha256") and old_manifest.get("source", {}).get("checksum", "").startswith("sha256:"):
        state["sourceSha256"] = old_manifest["source"]["checksum"][len("sha256:"):]

    # canonical 只读：此路径绝不写回 canonical——CSM-OCR-014（条文脚注）与
    # CSM-OCR-015（表注锚点上标字母）的回收此前在这里把结果直接写进 curated
    # canonical，违反「半程续跑仅刷新下游产物、canonical 不被覆盖」（AGENTS.md
    # §2 / README）。两类回收都已改到 canonical 的生成时刻执行：脚注回收在
    # finalize 的 normalize 之后（全流程/显式 --stage finalize），表注回收在
    # merge 全流程（随 raw 进 normalize）；此处 parse 直接读 canonical 原样。

    parsed = [
        str(Path(sys.prefix) / "bin" / "ssir"), "csm", "parse",
        "--input", str(canonical), "--output", str(paths["ssir"]),
        "--report", str(paths["parse_report"]),
    ]
    _log("Parsing canonical CSM into SSIR JSON")
    if subprocess.run(parsed, cwd=ROOT).returncode:
        raise RuntimeError("SSIR parsing needs review; check the canonical CSM and the parse report.")
    _log(f"SSIR JSON written: {paths['ssir']}")

    # PDF 源才有的版面印记恢复（示例框样式/图源尺寸/并列版面，读源 PDF 与 parts 几何）
    side_by_side_middle = getattr(args, "side_by_side_middle", None)
    if args.input_kind == "pdf" and args.input.is_file():
        _stamp_example_styles(paths["ssir"], args.input)
        _stamp_figure_source_sizes(paths["ssir"], args.input)
        _stamp_side_by_side_layout(paths["ssir"], args.output_dir / "parts", middle_json=side_by_side_middle)
    elif getattr(args, "figure_size_map", None):
        # raw 起点：图源尺寸取 middle.json 图块 bbox（GEN-098 第二来源）。
        _stamp_figure_source_sizes_from_map(paths["ssir"], args.figure_size_map)
        _stamp_side_by_side_layout(paths["ssir"], args.output_dir / "parts", middle_json=side_by_side_middle)
    else:
        _log("No source PDF present; skipping PDF-geometry stamps (example style / figure sizes / side-by-side)")

    # 公共尾部：roundtrip -> render（PDF）-> compare -> manifest
    _post_parse_verify_render(args, state, paths, paths["ssir"])
    return 0
