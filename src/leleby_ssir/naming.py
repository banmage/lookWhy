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
REP_RENDER = "render"                    # 04_render：发布 PDF（.pdf）/ markdown 投影（.md）/ HTML 结构投影（.html）
REP_RENDER_REPORT = "render-report"      # 04_render：渲染报告
REP_RENDER_COMPARISON = "render-comparison"  # 04_render：原稿 vs 渲染 PDF 统计
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
    ".checksum.sha256",
    ".semantic.jsonld",
    ".semantic.ttl",
    ".canonical.md",
    ".render.html",
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


# --- 文档元素标识（TDRS 命名规则） ----------------------------------------
#
# 依据：`技术文件智能审查系统（TDRS）设计说明文档v2.0.md`「附录：标准元素标识 /
# 命名规则」（§一 标准号处理、§二 条款号引用格式、§四 附录、§五 项、§六 表图公式、
# §八 变量 ID、§九 概念 ID、§十三 总结）。SSIR 中所有**元素标识**（结构化节点、
# 表/图/公式、注、锚点）一律由此模块生成，不再使用 ``ssir:<文档>/…`` 旧形式。
#
#   {标准标识}#{条款路径}
#     GB_T_1.1-2020#8.2.1            正文条
#     GB_T_1.1-2020#8.2.1_a          列项 a)
#     GB_T_1.1-2020#8.2.1_a_1        a) 下的 1)
#     GB_T_1.1-2020#Annex_A          附录
#     GB_T_1.1-2020#Annex_A.2.1      附录内条
#     GB_T_1.1-2020#Table_3          表 3
#     GB_T_1.1-2020#Figure_5         图 5
#     GB_T_1.1-2020#Formula_3        公式 (3)
#
# 与 TDRS 的三处**有意偏离**（均为消除真实冲突，见 docs/16 §10.3）：
#   ① 附录内的表/图/公式写 ``#Table_A.1`` / ``#Figure_E.1`` / ``#Formula_A.1``，
#      不写 TDRS §六 的 ``#Annex_B.1``——同一附录下「A.1 条」与「表 A.1」否则会撞成
#      同一标识（GB/T 1.1 语料里二者同号极常见）；
#   ② 无编号的内容元素（段、注、示例、列项以外的块）追加 ``/<kind>-<序号>`` 段，
#      因为 TDRS 只规定了编号元素与条款路径，未覆盖这些元素；
#   ③ 无字母/数字 marker 的列表项（破折号、间隔号）用条款内运行序号 ``Item<序号>``
#      （TDRS §五 只给 ``a``/``b`` 形态的字母项，marker 本身无法作后缀）。

# 标准号转义（TDRS §一 / §十三）：/ 空格 : → _，一字线 → 半字线，连字符保留。
def escape_standard_number(text: str) -> str:
    """标准号原文 → 系统标识（TDRS §一转义规则）。

    Examples::

        GB/T 1.1—2020        -> GB_T_1.1-2020
        GB 3100—2026         -> GB_3100-2026
        GB/T 20001.10—2014   -> GB_T_20001.10-2014
        ISO 80000-1:2022     -> ISO_80000-1_2022
        IEC 60027            -> IEC_60027
    """
    raw = str(text).strip().replace("—", "-")
    raw = raw.replace("/", "_").replace(":", "_")
    return re.sub(r"\s+", "_", raw)


_IDENTIFIER_RE = re.compile(r"^(?P<standard>[^#\s]+)#(?P<path>[^#\s]+)$")

# 块级元素类型 → 标识前缀（TDRS §六）
_ELEMENT_PREFIX = {"table": "Table", "figure": "Figure", "formula": "Formula", "note": "Note",
                   "footnote": "Foot", "unknown": "Unknown", "example": "Example",
                   "list": "List", "paragraph": "Paragraph", "block": "Block"}


def element_id(standard_id: str, path: str) -> str:
    """``{标准标识}#{条款路径}``（TDRS §二基本格式）。"""
    standard = str(standard_id).strip()
    if not standard or "#" in standard:
        raise ValueError(f"非法标准标识（不得含 '#' 或为空）: {standard_id!r}")
    clause = str(path).strip().lstrip("#")
    if not clause:
        raise ValueError("条款路径不得为空")
    if re.search(r"\s", clause) or "#" in clause:
        raise ValueError(f"条款路径不得含空白或 '#': {path!r}")
    return f"{standard}#{clause}"


def parse_element_id(identifier: str) -> tuple[str, str]:
    """元素标识 → ``(标准标识, 条款路径)``；不符合格式时抛 ``ValueError``。"""
    match = _IDENTIFIER_RE.match(str(identifier).strip())
    if not match:
        raise ValueError(f"非法元素标识: {identifier!r}")
    return match.group("standard"), match.group("path")


def _clean_tokens(values) -> list[str]:
    tokens: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text:
            continue
        if text.endswith(")") or text.endswith("）"):
            text = text[:-1]
        text = text.strip().rstrip(".").replace("—", "-")
        if text:
            tokens.append(text)
    return tokens


def clause_path(number: str, items=()) -> str:
    """正文条款路径：``8.2.1`` / ``8.2.1_a`` / ``8.2.1_a_1``（TDRS §二、§五）。"""
    number = str(number).strip().replace(" ", "")
    if not number:
        raise ValueError("条款编号不得为空")
    tokens = _clean_tokens(items)
    return "_".join([number, *tokens]) if tokens else number


def annex_path(letter: str, number: str = "", items=()) -> str:
    """附录条款路径：``Annex_A`` / ``Annex_A.2.1`` / ``Annex_A.2.1_a``（TDRS §四、§五）。

    ``number`` 允许写成 ``A.2.1``（源文件写法）或 ``2.1``（附录内相对编号），
    两种写法归一为 ``Annex_A.2.1``。
    """
    letter = str(letter).strip()
    for prefix in ("附录", "Annex_", "Annex"):
        letter = letter.removeprefix(prefix).strip()
    letter = letter.upper()
    if not letter or not letter.isalpha():
        raise ValueError(f"附录字母不合法: {letter!r}")
    head = f"Annex_{letter}"
    number = str(number).strip().replace(" ", "")
    if number:
        if re.fullmatch(rf"{re.escape(letter)}\..*", number, re.I):
            number = number.split(".", 1)[1]
        elif number.upper() == letter:
            number = ""
        head = f"{head}.{number}" if number else head
    tokens = _clean_tokens(items)
    return "_".join([head, *tokens]) if tokens else head


def _clean_number(number: str) -> str:
    """元素编号规范化：去空白、去尾部括号与句点（``a）``→``a``、``3)``→``3``）。

    只保留 ``[A-Za-z0-9.-]``（TDRS 编号字符集 + 附录字母内的连字符）；无法规范化
    （结果为空）时返回空串，由调用方回退到无编号分支，不生成非法标识。
    """
    text = str(number).strip().replace(" ", "").rstrip(")）]。.、")
    return re.sub(r"[^A-Za-z0-9.-]", "", text)


def numbered_element_path(kind: str, number: str) -> str:
    """表/图/公式路径：``Table_3`` / ``Figure_5`` / ``Formula_3``（TDRS §六）。

    ``number`` 带附录字母时（``A.1``）写作 ``Table_A.1``——见模块头的偏离①。
    """
    try:
        prefix = _ELEMENT_PREFIX[str(kind).strip().lower()]
    except KeyError:
        raise ValueError(f"未知元素类型: {kind!r}") from None
    number = _clean_number(number)
    if not number:
        raise ValueError(f"{kind} 编号不得为空")
    return f"{prefix}_{number}"


def table_element_id(standard_id: str, number: str) -> str:
    return element_id(standard_id, numbered_element_path("table", number))


def figure_element_id(standard_id: str, number: str) -> str:
    return element_id(standard_id, numbered_element_path("figure", number))


def formula_element_id(standard_id: str, number: str) -> str:
    return element_id(standard_id, numbered_element_path("formula", number))


def owned_element_id(owner_id: str, kind: str, label: str) -> str:
    """属主元素下的从属元素（注/脚注/原样块）：``{owner}#Note_a``、``{owner}#Foot_1``。

    属主是条款或表/图标识；``kind`` 取 §_ELEMENT_PREFIX 的键（note/footnote/unknown/…）。
    """
    try:
        prefix = _ELEMENT_PREFIX[str(kind).strip().lower()]
    except KeyError:
        raise ValueError(f"未知元素类型: {kind!r}") from None
    label = str(label).strip().replace(" ", "")
    if not label:
        raise ValueError(f"{kind} 标签不得为空")
    standard, path = parse_element_id(owner_id)
    return element_id(standard, f"{path}.{prefix}_{label}")


def local_element_id(base_id: str, kind: str, index: int) -> str:
    """无编号内容元素（内容位置槽）：``{base}#{kind}-{序号}``（偏离②，见模块头）。

    用于**内容位置**（段落/列项/示例/块槽/注/脚注所在的内容元素）；表/图/公式等
    编号元素**对象**另有其标识（``numbered_element_path``），内容槽只引用它们的标识。
    """
    standard, path = parse_element_id(base_id)
    kind_key = str(kind).strip().lower()
    if kind_key not in _ELEMENT_PREFIX:
        raise ValueError(f"未知内容元素类型: {kind!r}")
    return element_id(standard, f"{path}/{_ELEMENT_PREFIX[kind_key]}-{int(index):03d}")


# --- 变量 ID / 概念 ID（TDRS §八、§九） ------------------------------------

_GREEK = {
    "alpha": "ALPHA", "beta": "BETA", "gamma": "GAMMA", "delta": "DELTA", "epsilon": "EPSILON",
    "varepsilon": "EPSILON", "zeta": "ZETA", "eta": "ETA", "theta": "THETA", "vartheta": "THETA",
    "iota": "IOTA", "kappa": "KAPPA", "lambda": "LAMBDA", "mu": "MU", "nu": "NU", "xi": "XI",
    "pi": "PI", "rho": "RHO", "sigma": "SIGMA", "tau": "TAU", "upsilon": "UPSILON",
    "phi": "PHI", "varphi": "PHI", "chi": "CHI", "psi": "PSI", "omega": "OMEGA",
}
_VAR_MARKS = {"overline": "OVERLINE", "bar": "OVERLINE", "underline": "UNDERLINE",
              "vec": "VEC", "hat": "HAT", "tilde": "TILDE", "dot": "DOT", "ddot": "DDOT"}


def _var_token(text: str) -> str:
    """LaTeX 片段 → 变量 ID 片段（希腊字母按名、拉丁字母按字形、多字母符号原样大写）。"""
    text = text.strip().strip("{}")
    if not text:
        return ""
    if text.startswith("\\"):
        name = text.lstrip("\\").strip()
        if name in _GREEK:
            return _GREEK[name]
        return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()
    text = text.replace(",", " ").replace(";", " ")
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", text) if part]
    return "_".join(part.upper() for part in parts)


def variable_id(latex: str) -> str:
    """数学符号 → 变量 ID（TDRS §八：``VAR_{主体}_{下标}_{上标}_{符号}``）。

    Examples::

        \\overline{\\eta}  -> VAR_ETA_OVERLINE
        x_n^e            -> VAR_X_SUB_N_SUP_E
        S_{ME,i}         -> VAR_S_SUB_ME_I
    """
    text = str(latex).strip().strip("$").strip()
    if not text:
        raise ValueError("变量 latex 不得为空")
    marks: list[str] = []
    for command, mark in _VAR_MARKS.items():
        pattern = re.compile(rf"\\{command}\s*\{{([^{{}}]*)\}}")
        while True:
            match = pattern.search(text)
            if not match:
                break
            marks.append(mark)
            text = text[: match.start()] + match.group(1) + text[match.end():]
    text = re.sub(r"\\left|\\right|\\mathrm|\\text|\\operatorname", "", text)
    sub = re.search(r"_\{([^{}]*)\}|_([A-Za-z0-9])", text)
    sup = re.search(r"\^\{([^{}]*)\}|\^([A-Za-z0-9])", text)
    base = text[: min(x.start() for x in (sub, sup) if x) ] if (sub or sup) else text
    tokens = [_var_token(base)]
    if sub:
        tokens.append("SUB")
        tokens.append(_var_token(sub.group(1) or sub.group(2)))
    if sup:
        tokens.append("SUP")
        tokens.append(_var_token(sup.group(1) or sup.group(2)))
    tokens.extend(marks)
    body = "_".join(token for token in tokens if token)
    if not body:
        raise ValueError(f"无法生成变量 ID: {latex!r}")
    return f"VAR_{body}"


def concept_id(name: str) -> str:
    """概念 → 概念 ID（TDRS §九：``CONCEPT_{名称}``，名称用英文/拉丁文）。

    中文概念名需随附英文名（本体阶段再补；无英文名时抛 ``ValueError``，不生成伪 ID）。
    """
    text = str(name).strip()
    if not text:
        raise ValueError("概念名不得为空")
    token = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").upper()
    if not token:
        raise ValueError(f"概念名需为英文/拉丁文才能生成概念 ID: {name!r}")
    return f"CONCEPT_{token}"
