"""leleby SSIR 文件命名规范 —— 单一事实源（single source of truth）。

命名方案（用户 2026-08 确认，规范见仓库根 naming_specification.txt）：

1. STANDARD_ID 由标准号推导：标准号中的斜杠一律转为下划线，保持与
   原编号长度一致——
   - 推荐性/指导性标准：GB/T→GB_T、JB/T→JB_T、DB11/T→DB11_T、
     GB/Z→GB_Z（不再并入代号）；
   - 企业标准 Q/、团体标准 T/ 同样斜杠转下划线（Q/XKBZ→Q_XKBZ、
     T/CAS→T_CAS）；
   - 代号与顺序号之间用下划线，年份保留半字线（GB_T_15034-2012）。
   - 顺序号内部的点号是标准号的合法组成部分（GB/T 1.1-2020 → GB_T_1.1-2020），
     保留；文件名的解析规则见下。

2. 文件名统一为 ``<STANDARD_ID>.<representation>.<ext>``，其中 representation
   为单 token（可含连字符）。解析时从右往左：最后一段是扩展名、倒数第二段
   是 representation、其余为 STANDARD_ID。因此 ID 内部允许出现点号（如
   ``GB_T_1.1-2020.canonical.md``），不会被误切。

3. 报告类表示统一以 ``-report`` 结尾（extract-report / normalize-report /
   parse-report / render-report / render-comparison），不使用 ``.report``
   双点形式，保证 representation 恒为单 token。

规则对应: GEN-012（文件编号识别与一字线规范化）。
"""

from __future__ import annotations

import re
from pathlib import Path

# --- STANDARD_ID 推导 -----------------------------------------------------

# 通用标准号识别（GB/T 15034-2012、GB 15034-2012、JB/T 14054-2021、
# SJ/T 11859-2022、DB11/T 1000-2020、Q/XKBZ 002—2026、T/CAS 501-2021 等）。
# 前缀交替覆盖国家（GB/GB/T/GB/Z）、行业（JB/QB/SJ/DL/NY/HG/…）、地方（DB）、
# 团体（T/）与企业（Q/）编号；可选字母处理 SJ/T 式双字母代号。
_STANDARD_NUMBER_RE = re.compile(
    r"\b(?:[A-Z]{1,2}/?[A-Z]?|DB|T/|Q/)[ /A-Z0-9.\-—]*\d+(?:\.\d+)*(?:—|-)?\d*",
    re.I,
)


def standard_number_from_text(text: str, fallback: str = "") -> str:
    """从文本中提取标准号（GB/T 15034-2012、Q/XKBZ 002—2026 等）。

    规则对应: GEN-012（文件编号识别与一字线规范化）。
    未命中时返回 ``fallback``；一字线（—）统一规范化为半字线（-）。
    """
    match = _STANDARD_NUMBER_RE.search(text)
    return (match.group(0).strip() if match else fallback).replace("—", "-")


def standard_filename(standard_number: str) -> str:
    """由标准号生成规范文件名 stem（即 STANDARD_ID）。

    规则对应: GEN-012（文件编号识别与一字线规范化）+ 命名方案——标准号中的
    斜杠一律转为下划线（GB/T→GB_T、JB/T→JB_T、GB/Z→GB_Z、DB11/T→DB11_T、
    Q/XKBZ→Q_XKBZ、T/CAS→T_CAS），保持与原来编号长度一致；代号与顺序号
    之间用下划线，年份保留半字线（GB_T_15034-2012）。返回空串表示无法解析
    （调用方回退输入文件名）。

    Examples::

        GB/T 15034-2012 -> GB_T_15034-2012
        GB 15034-2012   -> GB_15034-2012
        JB/T 14054-2021 -> JB_T_14054-2021
        SJ/T 11859-2022 -> SJ_T_11859-2022
        DB11/T 1000-2020 -> DB11_T_1000-2020
        Q/XKBZ 002-2026 -> Q_XKBZ_002-2026
        T/CAS 501-2021  -> T_CAS_501-2021
    """
    raw = str(standard_number).strip().replace("—", "-")
    if not raw or not re.search(r"\d", raw):
        return ""
    # 拆「代号[ /T|/Z] + 空格 + 顺序号[-年份]」；斜杠在代号段内按 /T /Z
    # 识别（推荐性/指导性），再按企业/团体代号（Q/XKBZ、T/CAS）识别。
    # 两类斜杠一律转为下划线（GB/T→GB_T、Q/XKBZ→Q_XKBZ）。
    match = re.match(
        r"^([A-Z][A-Z0-9]*?)(?:/(T|Z)|/([A-Z0-9]+))?\s*(\d[\d.]*(?:-\d+)?)$",
        raw,
        re.I,
    )
    if not match:
        return ""
    code, tz, org = match.group(1), match.group(2), match.group(3)
    number = match.group(4)
    code = code.upper()
    if tz:
        code = f"{code}_{tz.upper()}"    # GB/T -> GB_T, JB/T -> JB_T, DB11/T -> DB11_T
    elif org:
        code = f"{code}_{org.upper()}"   # Q/XKBZ -> Q_XKBZ, T/CAS -> T_CAS
    return f"{code}_{number}"


# --- representation 常量（单 token） --------------------------------------

REP_SOURCE = "source"                    # 00_source：用户原始文件（只读）
REP_RAW = "raw"                          # 01_extract：MinerU/OCR 未加工 Markdown
REP_EXTRACT_REPORT = "extract-report"    # 01_extract：抽取报告
REP_PROVENANCE = "provenance"            # 01_extract：来源/哈希/锚点 sidecar
REP_CANONICAL = "canonical"              # 02_canonical：权威 CSM（唯一人工编辑版）
REP_NORMALIZE_REPORT = "normalize-report"  # 02_canonical：纠错报告
REP_SSIR = "ssir"                        # 03_ssir：结构化语义 JSON
REP_SEMANTIC = "semantic"                # 03_ssir：TTL/JSON-LD 知识图谱投影（可选）
REP_PARSE_REPORT = "parse-report"        # 03_ssir：解析报告
REP_RENDER = "render"                    # 04_render：发布 PDF（.pdf）/中间渲染 CSM（.md）
REP_RENDER_REPORT = "render-report"      # 04_render：渲染报告
REP_RENDER_COMPARISON = "render-comparison"  # 04_render：原稿 vs 渲染 PDF 统计
REP_VERIFY = "verify"                    # 05_verify：从渲染结果再抽取的 SSIR（回环输入）
REP_ROUNDTRIP = "roundtrip"              # 05_verify：比较报告
REP_DIFF = "diff"                        # 05_verify：详细差异（可选）
REP_CHECKSUM = "checksum"                # 00_source：原始文件哈希

# 已知 "<representation>.<ext>" 后缀（含历史兼容项），按长度降序匹配。
# 注意顺序：较长的后缀（render-report.json）必须先于较短的后缀（render.md）
# 参与匹配，避免误切。
_REPRESENTATION_SUFFIXES = (
    ".extract-report.json",
    ".normalize-report.json",
    ".render-report.json",
    ".render-comparison.json",
    ".parse-report.json",
    ".provenance.json",
    ".roundtrip.json",
    ".checksum.sha256",
    ".semantic.jsonld",
    ".semantic.ttl",
    ".canonical.md",
    ".render.md",
    ".render.pdf",
    ".ssir.json",
    ".verify.json",
    ".raw.md",
    ".source.pdf",
    ".diff.json",
    ".csm.md",  # 历史：CSM 样例旧后缀（corpus/golden/csm 迁移前）
)


def artifact_id(name: str | Path) -> str:
    """剥离已知的 ``<representation>.<ext>`` 后缀，返回 STANDARD_ID。

    未按方案命名的文件回退到去掉最后一个扩展名的 stem（兼容临时命名）。
    """
    filename = Path(name).name
    for suffix in _REPRESENTATION_SUFFIXES:
        if filename.endswith(suffix):
            return filename[: -len(suffix)]
    return Path(filename).stem


def report_path(artifact: str | Path, representation: str) -> Path:
    """默认报告路径：与产物同目录的 ``<STANDARD_ID>.<representation>.json``。

    ``artifact`` 可以是任意按方案命名的产物（如 ``03_ssir/GB_T_1.1-2020.ssir.json``
    或 ``02_canonical/GB_T_1.1-2020.canonical.md``）；报告的 STANDARD_ID 与
    产物一致，报告类型由 ``representation`` 决定。
    """
    target = Path(artifact)
    return target.parent / f"{artifact_id(target.name)}.{representation}.json"
