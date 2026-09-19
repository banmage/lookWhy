"""Parse Canonical SSIR Markdown (CSM) into a small, position-aware AST."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import re
from typing import Any

import yaml


class CSMError(ValueError):
    """Raised when a CSM input has one or more structural errors."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


@dataclass(slots=True)
class Directive:
    name: str
    attrs: dict[str, str]
    line: int


@dataclass(slots=True)
class Block:
    kind: str
    start_line: int
    end_line: int
    text: str = ""
    level: int | None = None
    directive: Directive | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CSMDocument:
    path: Path
    text: str
    metadata: dict[str, Any]
    body_start_line: int
    blocks: list[Block]
    warnings: list[str]
    issues: list["CSMIssue"]
    sha256: str


@dataclass(slots=True)
class CSMIssue:
    """A non-fatal import diagnostic, optionally describing a safe repair."""

    code: str
    severity: str
    message: str
    line: int | None = None
    repaired: bool = False
    repair_action: str | None = None

    def display(self) -> str:
        prefix = f"line {self.line}: " if self.line is not None else ""
        return f"[{self.code}/{self.severity}] {prefix}{self.message}"


DIRECTIVE_RE = re.compile(r"^<!--\s*ssir:([a-z-]+)(.*?)\s*-->\s*$")
# ssir:box 显式文档框声明（docs/13 裁定后实施，2026-09-08）：成对行级独占指令，
# 手工在 canonical 声明某段任意文档块内容的框线起止（frame=黑色细实线框 /
# shaded=浅色底）。开标记可带 style 属性；/box 以斜杠开头，DIRECTIVE_RE 的
# 名称字符类不含 "/"，故独立正则、先于通用指令分支匹配。
BOX_MARKER_RE = re.compile(r"^<!--\s*ssir:(/box|box)\s*(.*?)-->\s*$")
BOX_STYLE_ATTR_RE = re.compile(r'style="((?:\\.|[^"\\])*)"')
# 支持 style 属性（其余属性忽略并告警）。
_BOX_STYLES = {"frame", "shaded"}
# ssir:columns / ssir:column / ssir:/columns 显式并列声明（手工兜底 + 几何自动
# 打标的共同 canonical 载体）：成对行级独占指令，把若干内容元素声明为同一行内的
# N 列并列版式（渲染为无边框定位容器，等价 HTML div/两栏对照）。开标记可带
# widths="2,3"（列宽比，缺省等分）；column 分隔相邻列，/columns 结束。名称字符类
# 不含 "/"，故与 BOX_MARKER_RE 同型独立正则；备选顺序须把 /columns 放最前。
COLUMNS_MARKER_RE = re.compile(r"^<!--\s*ssir:(/columns|columns|column)\s*(.*?)-->\s*$")
COLUMNS_WIDTHS_ATTR_RE = re.compile(r'widths="((?:\\.|[^"\\])*)"')
ATTR_RE = re.compile(r'([A-Za-z][A-Za-z0-9-]*)="((?:\\.|[^"\\])*)"')
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
TABLE_SEPARATOR_RE = re.compile(r"^\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
IMAGE_RE = re.compile(r"^!\[(.*?)\]\((.*?)\)\s*$")
NUMBERED_ITEM_RE = re.compile(r"^([A-Za-z]+[)）]|\d+[)）])\s*(.*)$")
# 独立「示例N：」行（框式示例标题，GB/T 1.1 10.4.5 / GBT-B11）：冒号后无内容
# 才提升为标题；"示例1：γ辐照装置…" 这类行内示例（冒号后有内容）不受影响。
EX_HEADER_RE = re.compile(r"^示例\s*\d*\s*[:：]\s*$")
EX_LEAD_RE = re.compile(r"^示例\s*\d*\s*[:：]")
NOTE_LEAD_RE = re.compile(r"^注\s*\d*\s*[:：]")
# 行内注切分：OCR 把术语定义后的「注1：…。注2：…。」合并进定义段时，
# 在「。注N：」句界处切分为独立块（GBT-X04/B10；GB_T_20001.6 3.1 型）。
NOTE_SPLIT_RE = re.compile(r"(?<=。)(?=注\s*\d*\s*[:：])")
# 句末标点后出现点分条号（6.3.5.2 等）→ 把被 OCR 合并进上一句的条号分段
#（零宽切分点，条号本身保留在下一段开头）。
CLAUSE_SPLIT_RE = re.compile(r"(?<=[。；])\s*(?=\d+(?:\.\d+)+[\u4e00-\u9fff])")
# 多部分标准名称“第N部分：分部分名称”行（GB/T 1.1-2020 8.2.2 名称元素；封面/
# 正文首页把名称分两行排印时被 MinerU 拆成两个 H1——GB_T_20001.10-2014 正文首页）。
_PART_TITLE_RE = re.compile(r"^第\s*(?:\d+|[一二三四五六七八九十百千]+)\s*部分\s*[:：]")
# GB/T 1.1 规范性引用文件固定引导语“下列文件对于本文件的应用……”：OCR 偶把“下”
# 误读为形近字“卜”（GB_T_20001.10-2014 第 2 章，整句起点形态，安全修复）。
_REFERENCE_GUIDE_OCR_RE = re.compile(r"^卜列文件对于本文件")
# 规则对应: GEN-118（脚注标记改形）。正文引用点 `[foot:N]`；定义 = 指令对
# `<!--ssir:foot:N-->注释文字<!--ssir:/foot-->`（写在引用段落之后；渲染端仍绘到
# 引用所在页页脚——「其他逻辑不变」）。旧 GFM 写法 `[^N]` / `[^N]:` 已废弃：
# 解析时按 CSM-STRUCT-008 报 issue 并提示迁移，迁移工具 tools/replay_footnote_markers.py。
FOOTNOTE_CITE_RE = re.compile(r"\[foot:([0-9A-Za-z_-]+)\]")
FOOTNOTE_MARKER_PREFIX = "foot:"
_FOOTNOTE_DEF_RE = re.compile(
    r"<!--\s*ssir:foot:([0-9A-Za-z_-]+)\s*-->(.*?)<!--\s*ssir:/foot\s*-->", re.S
)
_FOOTNOTE_DEF_OPEN_RE = re.compile(r"<!--\s*ssir:foot:([0-9A-Za-z_-]+)\s*-->")
_FOOTNOTE_DEF_CLOSE = "<!--ssir:/foot-->"
# 旧写法（GFM 脚注，2026-09-19 由 GEN-118 取代）：仅用于识别并提示迁移。
LEGACY_FOOTNOTE_DEF_RE = re.compile(r"^\[\^([0-9A-Za-z_-]+)\]:\s*(.*)$")
LEGACY_FOOTNOTE_CITE_RE = re.compile(r"\[\^([0-9A-Za-z_-]+)\](?!:)")
# 定义行内容以句末标点收尾（允许后随闭引号/闭括号）＝ 该行是完整的单行定义、
# 下一行属于其它内容；用于把“段首定义行粘连后续内容行”的合并段剥离定义
# （防止把换行续写的长定义误拆）。
_FOOTNOTE_DEF_END_RE = re.compile(r"[。！？…；][」』）)】》]*$")
# 参考文献条目标准代号前缀（[N] 编号/括号形态修复的判别白名单，与 GBT-C06 一致）。
_REFERENCE_STD_PREFIX_RE = re.compile(
    r"^(?:GB/T|GB/Z|GB|JB/T|JB|DB\d{1,2}/T|QB/T|QB|SJ/T|SJ|DL/T|NY/T|HG/T|FZ/T|WS/T|YD/T|GA/T|CJ/T|JG/T|TB/T|SH/T|JC/T|EJ/T|MT/T|YY/T|YY|HJ/T|HJ|T/|Q/|ISO|IEC)\s"
)
# 标准号「文件代号 + 顺序号」之间的间隔（CSM-OCR-004）：正文中的标准号应写作
# “GB/T 20001”，OCR 常把空格丢掉（“GB/T20001”）。只认**已知文件代号**——
# 无斜杠的白名单代号（GB、GJB、ISO、IEC…）、斜杠后为 T/Z 的推荐性/指导性代号
# （GB/T、JB/T、DB11/T、GB/Z…）、斜杠后为组织字母的团体/企业代号（T/ZZB、Q/XKBZ）。
# 判据刻意不写成 `[A-Z]{2,4}(?=\d)`：那会把 RS485、AC1 500 V 之类**非标准号**的
# 字母数字串也拆开（2026-09-11 修复落在列项/表格载体后暴露）。代号清单与
# compliance._STANDARD_NUMBER_RE 同族（那是“是否为标准号”的检测式，本式是
# “代号与顺序号贴在一起”的间隔式）。
_STANDARD_GAP_DESIGNATOR = (
    r"(?:[A-Z]{1,4}\d{0,2}/[TZ]"          # GB/T  JB/T  DB11/T  GB/Z
    r"|(?:T|Q)/[A-Z]{1,8}"                # T/ZZB  Q/XKBZ（团体/企业）
    r"|(?:GJB|GB|ISO|IEC|ITU|EN|ANSI|ASTM|JIS|DIN|BS|NF|GOST|CIE|CISPR|IEEE|UL))"
)
_STANDARD_NUMBER_GAP_RE = re.compile(rf"(?<![A-Za-z0-9/])({_STANDARD_GAP_DESIGNATOR})(?=\d)")


def restore_standard_number_spacing(text: str) -> str:
    """在标准号的「文件代号」与「顺序号」之间补一个空格（GB/T20001 → GB/T 20001）。

    规则对应: CSM-OCR-004。幂等（已有空格的形态不匹配）。解析层修复与 canonical
    回放工具共用本实现，保证「规则实例回放」是同一规则的确定性应用。
    """
    return _STANDARD_NUMBER_GAP_RE.sub(lambda m: f"{m.group(1)} ", text)


# 术语条目行（CSM-OCR-003、CSM-OCR-007）：术语行 = 术语 + 间隔 + 英文对应词，中英文之间
# 空一个汉字（GB/T 1.1-2020 8.7.3.1、10.3.5）。接受两种载体——裸术语行「标准化文件
# standardizing document」与带条目编号的术语条目标题行「3.1.2 标准 standard」（条目编号
# 在 SSIR 里是独立字段，术语行只承载术语与英文对应词）。
#
# **字符类只在本文件写一份**：parser 的间隙归一（restore_term_entry_gap）、条目形态归一
# （_repair_term_entry_headings）与 builder 的 term/englishTerm 抽取（term_entry_pair）共用
# 同一判据。三处各写一份曾把字符类写宽窄不一：术语本体被限成**纯汉字串**、英文对应词不含
# 逗号，于是「SI词头　SI prefix」（术语带拉丁缩写）与「国际单位制　International System of
# Units, SI」（英文对应词带逗号）在两种形态下都识别不出（GB_3100-2026 3.13/3.8：SSIR 缺
# term/englishTerm，目次行只剩条目编号）。
#
# 判据的两条守卫：术语本体**至少含一个汉字**（纯拉丁行是正文或英文标题的换行，不是术语行，
# 如 GB_T_1.1-2020 前置部分 "structure and drafting of ISO and IEC documents,NEQ)"）；
# 英文对应词段不得含汉字（定义段不是术语行）。行内出现中文标点即不认。
TERM_ENTRY_TERM_PATTERN = r"[\u4e00-\u9fffA-Za-z0-9（）()·\-—]{1,24}"
TERM_ENTRY_ENGLISH_PATTERN = r"[A-Za-z][A-Za-z0-9 &()（）·.,\-—/:;'’]*"
_TERM_ENTRY_HAN_RE = re.compile(r"[\u4e00-\u9fff]")
_TERM_LINE_PUNCT_RE = re.compile(r"[，。；：？！、”“‘’《》【】（）…]")

# 术语行本体（不含行首条目编号）。
TERM_ENTRY_LINE_RE = re.compile(
    rf"^(?P<term>{TERM_ENTRY_TERM_PATTERN})"
    rf"[ \u3000\u200b]+(?P<english>{TERM_ENTRY_ENGLISH_PATTERN})$"
)


def term_entry_pair(text: str) -> tuple[str, str] | None:
    """把术语行拆成 (术语, 英文对应词)；不是术语行时返回 None。

    规则对应: CSM-OCR-003、CSM-OCR-007、GB/T 1.1-2020 8.7.3.1/10.3.5。parser 与 builder
    共用本判据（单源），使得「术语行被识别为条目」与「term/englishTerm 被抽出来」同步，
    不会各自随字符类漂移。
    """
    match = TERM_ENTRY_LINE_RE.match(text.strip())
    if not match or not _TERM_ENTRY_HAN_RE.search(match.group("term")):
        return None
    return match.group("term"), match.group("english")


_TERM_ENTRY_GAP_RE = re.compile(
    r"^(?P<lead>\s*)"
    r"(?:(?P<number>\d+(?:\.\d+)*)(?P<number_gap>[ \u3000]+))?"
    rf"(?P<term>{TERM_ENTRY_TERM_PATTERN})"
    r"(?P<gap>[ \u3000\u200b]+)"
    rf"(?P<english>{TERM_ENTRY_ENGLISH_PATTERN})$"
)
# 纯汉字术语形态（旧判据，术语与英文对应词之间可无间隔）：**先于**上面放宽判据试匹配。
# 放宽后的术语类含拉丁字母，先按「间隔必须存在」切分时 "标准化文件standardizing document"
# 只有一个空格、只能切成 术语="标准化文件standardizing" + 英文="document"（把英文词尾吞进
# 术语）；纯汉字术语类没有这个歧义。两形态输出同为「术语 + U+3000 + 英文对应词」。
_TERM_ENTRY_GAP_HAN_ONLY_RE = re.compile(
    r"^(?P<lead>\s*)"
    r"(?:(?P<number>\d+(?:\.\d+)*)(?P<number_gap>[ \u3000]+))?"
    r"(?P<term>[\u4e00-\u9fff]{1,24})"
    r"(?P<gap>[ \u3000\u200b]*)"
    r"(?P<english>[A-Za-z].*)$"
)


def restore_term_entry_gap(line: str) -> str:
    """把术语条目行「术语 英文对应词」之间的间隙归一为 U+3000（CSM-OCR-003）。

    规则对应: CSM-OCR-003、GB/T 1.1-2020 8.7.3.1/10.3.5（英文对应词与术语之间空
    一个汉字）。行首空白、条目编号与术语之间原有的空白、行尾换行原样保留，只重写
    中英文间隙；不是术语行（含中文标点、无英文对应词、术语整行为纯拉丁）时原样返回。
    是否属于「术语和定义」要素由调用方判定（parser 用 in_terms 跟踪、回放工具用
    行级章跟踪）。
    """
    if not line.strip() or _TERM_LINE_PUNCT_RE.search(line):
        return line
    body = line.rstrip("\r\n")
    ending = line[len(body):]
    match = _TERM_ENTRY_GAP_HAN_ONLY_RE.match(body)
    if not match:
        match = _TERM_ENTRY_GAP_RE.match(body)
        if match and not _TERM_ENTRY_HAN_RE.search(match.group("term")):
            match = None
    if not match:
        return line
    number = match.group("number") or ""
    number_gap = match.group("number_gap") or ""
    return f"{match.group('lead')}{number}{number_gap}{match.group('term')}\u3000{match.group('english')}{ending}"

# 句末/停顿标点（词中断段合并的“前段必须无此标点收尾”判别用）。
_SENTENCE_END_PUNCT = "。！？；：，、…"
# GB/T 1.1 列项符号为破折号（——）或间隔号（·）；OCR 常把 "——" 压成
# 单个 "-" 或 "—" 且丢失后方空格，故破折号允许无空格（GBT-C12）。
# CommonMark 的 "*"/"+" 项目符号仍要求后方空格，避免误吞 "**加粗**" 行首。
# ●/•/·/○（U+25CF/U+2022/U+00B7/U+25CB）是规程/规范类标准示例常用的
# 项目符号与 GB/T 1.1 第二层次间隔号；OCR 可能全角半角混用、圆点/短横
# 互读（GB_T_1.1-2020 前言 8.3 的 ·/• 混用），且无 Markdown 强调歧义，
# 故允许无空格。
UNORDERED_ITEM_RE = re.compile(r"^(?:([-—–]+)|([*+]\s+)|([●•·○])\s*)\s*(.*)$")
# 项目符号族（OCR 常混读）：同一列表内按多数派统一（CSM-OCR-001）。
_BULLET_MARKERS = ("●", "•", "·", "○")
# 破折号族：OCR 把同一破折号读成长度不一的横杠（-、—、——、———、–，
# 全角/半角混用）。与项目符号族一起参与同列表多数派统一（CSM-OCR-001）。
_DASH_RUN_RE = re.compile(r"^[-—–]+$")
TABLE_CAPTION_RE = re.compile(r"^\*\*表([^\s]+)\s+(.+?)\*\*$")
# Bare numbered caption: "**表N**" — 行业标准/企业标准常见排版，题注只有编号
# 无题名 (GBT-B08 编号必备；题名可省略)。
TABLE_BARE_CAPTION_RE = re.compile(r"^\*\*表([^\s]+)\*\*$")
# Heading-shaped table caption ("## 表4 物理性能要求") — MinerU 偶尔把表题注
# 提升为 ## 标题且位于 ssir:table directive 之前；解析时降级为表格 caption，
# 避免渲染出「表4 物理性能要求」+「表4」双题注（GEN-032/033、GBT-B08）。
# 允许 "表" 与编号之间有空格（OCR 排法 "表 3 轴伸径向圆跳动"，2026-08-31）。
TABLE_HEADING_CAPTION_RE = re.compile(r"^表\s*([^\s]+)\s+(.+)$")

# 裸条号标题（MinerU 偶尔把章条标题抽成普通段落，无 ## 前缀——如
# QB_T_2946-2020 第 3 章 "3 产品分类和型号命名" / "3.1 电动机分类和型号命名" /
# "3.1.1 电动机分类"，只有 3.1.2 保留 ##，导致 GBT-H03 报"章编号不连续：缺失 3"
# 且 GBT-C06 把 "3 产品分类和型号命名" 误当引用条目）。判别（保守）：
# 行首编号 + 空白 + 汉字/括号开头（排除 "1 000 kV" 千分位，GEN-031）、
# 无句末标点、长度 ≤ 40（正文短句以编号开头时通常更长或带标点）。
BARE_HEADING_CANDIDATE_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+[\u4e00-\u9fff（(]")
# 段落句末标点（有则不可能为标题；标题行以句号/逗号/分号结尾的极罕见）。
_BARE_HEADING_TERMINAL_PUNCT = "。；，,、！？"
# 表注行：表格最后一行合并单元格以「注N：」开头（GB_3100-2026 表1/表4 型，
# MinerU 把表注整进表内最后一行）。
_TABLE_NOTE_CELL_RE = re.compile(r"^注\s*\d*\s*[:：]")

# ---------------------------------------------------------------------------
# 公式编号与公式变量解释（GBT-X06 / GB/T 1.1-2020 9.9.2、9.9.3、10.4.3）
# ---------------------------------------------------------------------------
# 「式中：」引导行（空两个汉字起排，10.4.3）：变量解释组的锚点。
FORMULA_VAR_INTRO_RE = re.compile(r"^式中\s*[:：]\s*$")
# 变量解释项固定形态：变量（行内 LaTeX，或裸字母/希腊字母可带下标）+ 破折号
# （OCR 常压成单个「—」甚至整段丢失）+ 解释文字 + 终止符（；，末项 。）。
# 头部限短（1—4 个半角字母）以防把以英文单词开头的正文误判为解释项。
FORMULA_VAR_ITEM_RE = re.compile(
    r"^(?P<head>\$[^$\n]+\$|[\u0370-\u03ffA-Za-z][\u0370-\u03ffA-Za-z0-9]{0,3}"
    r"(?:[ \u3000]*[_^][ \u3000]*\{[^{}\n]{1,12}\})?)"
    r"(?P<dash>[ \u3000]*[-—–―－]{1,8}[ \u3000]*|[ \u3000]*[:：][ \u3000]*|[ \u3000]+|)"
    r"(?P<text>[\u4e00-\u9fff].*)$"
)
# 解释项终止符：分号（末项句号）。
_FORMULA_ITEM_END_RE = re.compile(r"[。；;.．]$")
# 变量与破折号之间、破折号与解释之间各空四分之一汉字（10.4.3 版式）；
# 规范化后的 CSM 形态不含空格，字隙由渲染层按固定字隙实现（同 GBT-B12）。
# 「式(N)」编号行（CSM 语法，docs/07 §6.7；式（1）全角半角、附录 A.1 均可）。
_FORMULA_NUMBER_LINE_RE = re.compile(r"^式\s*[（(]\s*(.+?)\s*[）)]\s*$")
# MinerU 把整条公式行（公式 + 「…………」引导线 + 编号）识别为一个 equation 块，
# 引导线与编号被写进 LaTeX 的 \tag{...}，且经常缺右花括号（\tag{……………………(1}）。
FORMULA_TAG_RE = re.compile(r"\\tag\s*\{([^{}]*)\}?")
# \tag 内容里的编号：引导线（…/⋯）清掉后取括号内（可缺右括号）或行尾的编号。
_FORMULA_TAG_LABEL_RE = re.compile(r"[（(]\s*([A-Za-z]?\d+(?:\.\d+)*)\s*[）)]?\s*$")
_FORMULA_NUMBER_LABEL_RE = re.compile(r"([A-Za-z]?\d+(?:\.\d+)*)\s*$")
# 附录标题（「附录 A（资料性）…」）：编号在附录内重新从 1 开始并加前缀字母。
ANNEX_HEADING_RE = re.compile(r"^附\s*录\s*([A-Z])(?![A-Za-z])")

# ---------------------------------------------------------------------------
# 表内角注/脚注标记（GEN-119，2026-09-19 用户裁定）
# ---------------------------------------------------------------------------
# 旧的「行内角标标记」族 `[:sup:a]` / `[:sub:2]` / `[:/sup]` / `[:/sub]`（含更早的
# `[:^a]`、`[^a]…[^a/]`）**不再支持**：表内角注一律写通用行内公式上角标 `$^{a}$`
# （正体、小号、上移；多标记连写 `$^{a、c}$`），注文由表后的 `a）…` 行/表注行承担，
# 关联逻辑不变。遇旧标记按 CSM-STRUCT-009 报 issue 并提示改写。
def _is_bare_enumeration(enum_lines: list[str]) -> bool:
    """裸列项判定（2026-09-02，GB_3100-2026 4.2 七个定义常量型）。

    MinerU 把源文中逐行排列的枚举行（引导语「…单位制：」+ 每条以 ；/。 收尾）
    收集进同一段，渲染时行内换行被折叠成空格 → 挤成一行流。判定（保守）：
    ≥2 行、≥2 行以句末标点（。；：;.）结尾、绝大多数行（≥2/3）如此、且
    ≥1 行以分号收尾（枚举特征）——普通折行段落几乎不可能同时满足（折行点
    极少恰好落在句界，更不可能多条连续如此）。行尾 LaTeX 闭合符 $ 先剥掉
    （4.2 的普朗克/玻尔兹曼常量行以 $ 结尾）。
    """
    if len(enum_lines) < 2:
        return False
    sentence_ends = sum(1 for ln in enum_lines if ln.endswith(("。", "；", "：", ";", ".")))
    semi_ends = sum(1 for ln in enum_lines if ln.endswith(("；", ";")))
    return sentence_ends >= 2 and sentence_ends * 3 >= len(enum_lines) * 2 and semi_ends >= 1


def _absorb_table_note_spill(blocks: list[Block], warnings: list[str]) -> list[Block]:
    """表注跨页断裂吸收（2026-09-02，GB_3100-2026 表4）。

    表注行（表内最后一行合并单元格，以「注N：」开头）跨页时，MinerU 把续行
    抽成表格外段落——注6 的续句（"于静止状态和基态的自由碳12原子…"）成为
    裸段落、注7~注11 成为「> 注N：」块，渲染时全部落在表格框外（用户报告
    "表4最后一行的内容应一直包括到注11"）。此处把紧随表注行的连续注块
    （注N：…）与续句段（表格注行文本尚未以句末标点收尾时的普通段落）合并
    回表末注行单元格，以 <br> 分行（与 merge 阶段恢复的 <br> 单元格行结构
    同一约定）；遇到新块（标题/条号段/新表格等）即停止。
    """
    result: list[Block] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        result.append(block)
        index += 1
        if block.kind != "table":
            continue
        rows = block.data.get("rows") or []
        if not rows or not rows[-1]:
            continue
        cell = str(rows[-1][0])
        if not _TABLE_NOTE_CELL_RE.match(cell.strip()):
            continue
        absorbed = False
        while index < len(blocks):
            nxt = blocks[index]
            text = str(nxt.text).strip()
            if nxt.kind == "note" and text.startswith("注"):
                cell += "<br>" + text
                rows[-1][0] = cell
                index += 1
                absorbed = True
                continue
            if (
                nxt.kind == "paragraph"
                and not cell.endswith(("。", "！", "？"))
                and not BARE_HEADING_CANDIDATE_RE.match(text)
            ):
                cell += "<br>" + text
                rows[-1][0] = cell
                index += 1
                absorbed = True
                continue
            break
        if absorbed:
            warnings.append(
                f"line {block.start_line}: spilled table notes were absorbed back "
                f"into the table's trailing note row ({rows[-1][0][:40]!r}…)."
            )
    return result


def _bare_heading_candidates(lines: list[str]) -> tuple[set[str], dict[int, str]]:
    """预扫描：返回 (已确认标题编号集合, {行号: 候选编号})。

    已确认标题 = 带 ## 前缀且文本以"编号+空白"开头的标题行；候选 = 形如
    标题的裸段落行（排除表格/引用/图片/代码/公式/指令/列项行）。用于
    级联提升：候选编号是某已确认编号的祖先（3 是 3.1.2 的祖先）、或父编号
    已提升（3.1.1 的父 3.1 提升后 3.1.1 跟随）时提升为标题。
    """
    confirmed: set[str] = set()
    candidates: dict[int, str] = {}
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        heading = HEADING_RE.match(line)
        if heading:
            # 规则对应: GEN-117（标题编号确认不依赖空格）。
            # 标题编号与标题文字之间可能缺空格（人工 curation 的 canonical 常见写法：
            # `### 6.4分类、标记和编码`，而渲染端统一写 `6.4 分类、标记和编码`）。
            # 旧判据要求编号后**必须**是空白，缺空格的标题就不算"已确认编号"，
            # 其下裸条款段（`6.4.3 产品分类的基本要求如下：`）的级联提升随之失效，
            # 于是同一份文件在回环两侧解析出不同的条款树（C7-clauseIdentifiers /
            # C4-numericalValues 关键信息丢失）。此处与 builder 的标题拆分同判据：
            # 编号后是空白，或直接跟标题文字（汉字/字母/括号）。
            number_match = re.match(
                r"^(\d+(?:\.\d+)*)(?:\s|(?=[\u4e00-\u9fffA-Za-z（(]))", heading.group(2)
            )
            if number_match:
                confirmed.add(number_match.group(1))
            continue
        if stripped.startswith(("|", ">", "!", "```", "$$", "<!--", "**")):
            continue
        if UNORDERED_ITEM_RE.match(line) or NUMBERED_ITEM_RE.match(line):
            continue
        candidate = BARE_HEADING_CANDIDATE_RE.match(stripped)
        if candidate and len(stripped) <= 40 and not any(
            ch in stripped for ch in _BARE_HEADING_TERMINAL_PUNCT
        ):
            candidates[idx] = candidate.group(1)
    return confirmed, candidates


def _promoted_bare_headings(confirmed: set[str], candidates: dict[int, str]) -> set[str]:
    """级联提升：初始 = 所有已确认编号的祖先链；迭代 = 父编号已提升的子编号。

    保守设计：没有已确认标题编号时什么都不提升（整树裸抽无法可靠区分
    标题与正文，留给人工核查，符合 CSM-OCR-002 的"无法唯一合法时不要猜"）。
    """
    promoted: set[str] = set()

    def ancestors(number: str) -> list[str]:
        parts = number.split(".")
        return [".".join(parts[:i]) for i in range(1, len(parts))]

    def parent(number: str) -> str:
        return number.rsplit(".", 1)[0] if "." in number else ""

    for number in confirmed:
        for ancestor in ancestors(number):
            promoted.add(ancestor)
        # 2026-09-03（GB_T_1.1-2020 第4章型）：已确认标题自身也作父链种子。
        # 祖先链只覆盖「有已确认子孙」的编号；若某章（4）的整层子条都被抽成裸
        # 段落（4.1/4.2 无 ##），没有任何 4.x 已确认标题 → "4" 不在 promoted，
        # 级联无从开始，第 4 章便永远没有子条。把已确认编号自身加入种子后，
        # 裸子条（4.1）的父（4）即命中，4.1/4.2 及更深连续候选正常级联提升。
        promoted.add(number)
    changed = True
    while changed:
        changed = False
        for number in candidates.values():
            if number in promoted:
                continue
            if parent(number) in promoted:
                promoted.add(number)
                changed = True
    return promoted


# 单位为毫米 等单位行：位于表题注与表格之间，题注折叠时的 lookahead 可跳过，
# 且折进 table directive 的 unit 属性（渲染为右对齐"单位为毫米"紧贴表格）。
TABLE_UNIT_LINE_RE = re.compile(r"^单位\s*[为:：]\s*(\S{1,8})$")


def _clause_digit_placements(digits: str, max_depth: int = 4) -> list[tuple[int, ...]]:
    """All ways to split a digit run into 1..max_depth non-empty segments.

    章条号点分隔修复（CSM-OCR-002）的候选空间：把 "7421" 拆成
    (7,4,2,1)、(7,4,21)、(7,42,1)、(74,2,1)… 每段无前导零。
    """
    placements: list[tuple[int, ...]] = []
    if not digits:
        return placements

    def rec(start: int, segments: list[int]) -> None:
        if start == len(digits):
            placements.append(tuple(segments))
            return
        if len(segments) >= max_depth:
            return
        for end in range(start + 1, len(digits) + 1):
            segment = digits[start:end]
            if len(segment) > 1 and segment[0] == "0":
                continue
            rec(end, segments + [int(segment)])

    rec(0, [])
    return placements


def _clause_continuation(placement: tuple[int, ...], stack: list[int]) -> list[int] | None:
    """Return the new numbering stack if placement continues stack, else None.

    合法续接（GB/T 1.1 6.1.1 层次编号规则，GBT-H02/H03）：
    - 同级兄弟 +1（含章级：新章 = 当前章 + 1）；
    - 子条：父号 + ".1"；
    - 回退：弹出若干层后最后一段 + 1（如 5.2.3 → 5.3）。
    """
    if not stack:
        return list(placement)
    depth = len(placement)
    if depth == len(stack):
        if placement[:-1] == tuple(stack[:-1]) and placement[-1] == stack[-1] + 1:
            return list(placement)
    elif depth == len(stack) + 1:
        if placement[:-1] == tuple(stack) and placement[-1] == 1:
            return list(placement)
    elif depth < len(stack):
        if placement[:-1] == tuple(stack[: depth - 1]) and placement[-1] == stack[depth - 1] + 1:
            return list(placement)
    return None

SUPPORTED_DIRECTIVES = {
    "block",
    "table",
    "table-merge",
    "figure",
    "formula",
    "list",
    "unknown",
}

# These markers are emitted by the MinerU adapter solely to retain page-range
# provenance while its chunks are merged.  They are not SSIR content and must
# never be preserved as visible/unknown document text.
MINERU_PAGE_MARKER_RE = re.compile(r"^<!--\s*/?ssir:mineru-pages\b.*-->\s*$")


def _unescape_attribute(value: str) -> str:
    return value.replace(r'\"', '"').replace(r"\\", "\\")


def _starts_with_han(text: str) -> bool:
    """下一续接行以汉字开头（CJK 句内续接特征）。引用条目/裸标题等以
    拉丁或数字开头的行不续接，避免吞并（2026-08-31 确立断行修复的
    窄化条件）。"""
    return bool(text) and "\u4e00" <= text[0] <= "\u9fff"


def escape_table_cell(text: str) -> str:
    """幂等转义表格单元格内的管道符（写侧；与 ``_split_table_row`` 读侧语义配对）。

    读侧把「奇数个反斜杠前缀的 |」当作单元格内的字面管道，偶数（含 0）个当作
    列分隔符。因此写侧只应为偶数前缀的 | 补一个反斜杠：裸 ``|`` 需要转义成
    ``\\|``，而已经转义的 ``\\|``（如 MinerU 内联公式里的范数竖线 ``$| a-b |$``
    经 mineru_html 首转义所得）必须保持原样——无条件 ``replace("|", r"\\|")``
    会把 ``\\|`` 二次转义成 ``\\\\|``，再次 parse 时反斜杠转义追踪失效、公式里
    的 | 被误判为列分隔符（GB_T_755-2025 表12/13/15 报 "table row has 6 cells;
    expected 4"，normalize→parse 中断、无渲染产物）。
    规则对应: normalize/roundtrip 幂等（写侧转义须与读侧语义一致）。
    """
    out: list[str] = []
    backslashes = 0
    for char in text:
        if char == "\\":
            backslashes += 1
            out.append(char)
        elif char == "|":
            if backslashes % 2 == 0:
                out.append("\\")
            out.append(char)
            backslashes = 0
        else:
            backslashes = 0
            out.append(char)
    return "".join(out)


def _split_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith(r"\|"):
        stripped = stripped[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in stripped:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
            current.append(char)
        elif char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    return cells


class CSMParser:
    """A deterministic parser for the constrained CSM 1.0 Markdown dialect."""

    def __init__(self, strict: bool = False) -> None:
        self.strict = strict

    def read(self, path: str | Path) -> CSMDocument:
        source = Path(path)
        raw = source.read_bytes()
        fatal_errors: list[str] = []
        issues: list[CSMIssue] = []
        if raw.startswith(b"\xef\xbb\xbf"):
            issues.append(
                CSMIssue(
                    "CSM-ENC-001",
                    "warning",
                    "UTF-8 BOM was removed while reading the input.",
                    repaired=True,
                    repair_action="Removed UTF-8 BOM in memory; the source file was not modified.",
                )
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CSMError([f"input is not valid UTF-8: {exc}"]) from exc
        if "\r" in text:
            text = text.replace("\r\n", "\n").replace("\r", "\n")
            issues.append(
                CSMIssue(
                    "CSM-ENC-002",
                    "warning",
                    "CRLF or CR line endings were normalized to LF while reading the input.",
                    repaired=True,
                    repair_action="Normalized line endings in memory; the source file was not modified.",
                )
            )
        if text.startswith("\ufeff"):
            text = text.removeprefix("\ufeff")
        if not text.startswith("---\n"):
            raise CSMError(["CSM must start with YAML front matter"])

        marker = text.find("\n---\n", 4)
        if marker < 0:
            raise CSMError(["YAML front matter closing marker is missing"])
        yaml_text = text[4:marker]
        try:
            metadata = yaml.safe_load(yaml_text)
        except yaml.YAMLError as exc:
            raise CSMError([f"invalid YAML front matter: {exc}"]) from exc
        if not isinstance(metadata, dict):
            issues.append(CSMIssue("CSM-META-001", "warning", "YAML front matter was not an object; an empty object was used.", repaired=True, repair_action="Replaced non-object front matter with an empty metadata object."))
            metadata = {}

        body_offset = marker + len("\n---\n")
        body_start_line = text[:body_offset].count("\n") + 1
        blocks, parse_errors, parse_warnings = self._parse_body(text[body_offset:], body_start_line)
        for warning in parse_warnings:
            issues.append(CSMIssue("CSM-STRUCT-001", "warning", warning))
        fatal_errors.extend(self._repair_tables(blocks, issues))
        self._repair_stray_table_images(blocks, issues)
        self._repair_table_image_layout(blocks, issues)
        self._repair_list_markers(blocks, issues)
        self._repair_clause_numbers(blocks, issues)
        self._repair_term_entry_headings(blocks, issues)
        self._repair_split_multipart_title(blocks, issues)
        self._repair_heading_levels(blocks, issues)
        self._repair_example_heading_levels(blocks, issues)
        self._repair_colon_led_lists(blocks, issues)
        self._repair_lost_list_markers(blocks, issues)
        self._repair_formula_numbers(blocks, issues)
        self._repair_formula_variable_lines(blocks, issues)
        self._repair_text_spacing(blocks, issues)
        self._repair_ocr_guide_phrase(blocks, issues)
        self._repair_reference_entry_brackets(blocks, issues)
        self._reclassify_footnote_definitions(blocks, issues)
        self._flag_retired_script_markers(blocks, issues)
        self._demote_sentence_headed_clauses(blocks, issues)
        self._demote_index_letter_headings(blocks, issues)
        fatal_errors.extend(self._classify_body_errors(parse_errors, issues))
        self._normalise_metadata(metadata, blocks, source, issues)
        document_errors: list[str] = []
        self._validate_document(metadata, blocks, document_errors)
        fatal_errors.extend(self._classify_document_errors(document_errors, issues))
        self._assess_standard_profile(metadata, blocks, issues)
        self._append_declared_quality_notices(metadata, issues)
        if self.strict:
            fatal_errors.extend(issue.display() for issue in issues if issue.severity in {"warning", "error"})
        if fatal_errors:
            raise CSMError(fatal_errors)
        return CSMDocument(
            path=source,
            text=text,
            metadata=metadata,
            body_start_line=body_start_line,
            blocks=blocks,
            warnings=[issue.display() for issue in issues if issue.severity in {"warning", "error"}],
            issues=issues,
            sha256=sha256(raw).hexdigest(),
        )

    @staticmethod
    def _issue(issues: list[CSMIssue], code: str, message: str, *, line: int | None = None, repaired: bool = False, repair_action: str | None = None) -> None:
        issues.append(CSMIssue(code, "warning", message, line, repaired, repair_action))

    def _normalise_metadata(self, metadata: dict[str, Any], blocks: list[Block], source: Path, issues: list[CSMIssue]) -> None:
        """Fill only machine metadata defaults; never alter a standard's body text.

        规则对应: GEN-050（元数据 schema 一致）+ GBT-C01（文件名称/文件编号等必备字段兜底）。
        """
        if metadata.get("csm-version") != "1.0":
            original = metadata.get("csm-version")
            metadata["csm-version"] = "1.0"
            self._issue(issues, "CSM-META-002", f'Unsupported or missing csm-version {original!r}; parsed as "1.0" compatibility mode.', repaired=True, repair_action='Set in-memory csm-version to "1.0".')
        if metadata.get("document-type") not in {"standard", "guidance", "technical-report", "contract", "other"}:
            metadata["document-type"] = "standard"
            self._issue(issues, "CSM-META-003", "Missing or unsupported document-type; assumed standard.", repaired=True, repair_action="Set in-memory document-type to standard.")
        h1 = next((block.text for block in blocks if block.kind == "heading" and block.level == 1), None)
        if not isinstance(metadata.get("title"), str) or not metadata["title"].strip():
            metadata["title"] = h1 or source.stem.replace(".csm", "").replace("_", " ")
            self._issue(issues, "CSM-META-004", "Missing title; derived a title from the H1 or file name.", repaired=True, repair_action="Set in-memory title without changing body text.")
        identifier = metadata.get("document-identifier")
        if not isinstance(identifier, str) or not identifier.strip():
            candidate = metadata.get("standard-number") or source.stem.replace(".csm", "").replace("_", "-")
            metadata["document-identifier"] = str(candidate)
            self._issue(issues, "CSM-META-005", "Missing document-identifier; derived it from the standard number or file name.", repaired=True, repair_action="Set in-memory document identifier.")
        if metadata["document-type"] == "standard" and (not isinstance(metadata.get("standard-number"), str) or not metadata["standard-number"].strip()):
            metadata["standard-number"] = str(metadata["document-identifier"])
            self._issue(issues, "CSM-META-006", "Missing standard-number for a standard; used document-identifier as a placeholder.", repaired=True, repair_action="Set in-memory standard number from document identifier.")
        if not isinstance(metadata.get("language"), str) or not metadata["language"].strip():
            body_text = "\n".join(block.text for block in blocks)
            metadata["language"] = "zh-CN" if re.search(r"[\u3400-\u9fff]", body_text) else "und"
            self._issue(issues, "CSM-META-007", f'Missing language; inferred {metadata["language"]}.', repaired=True, repair_action="Set in-memory language tag.")
        if not isinstance(metadata.get("source"), dict):
            metadata["source"] = {"mode": "user-markdown", "provenance": "none"}
            self._issue(issues, "CSM-META-008", "Missing or invalid source object; supplied user-markdown provenance defaults.", repaired=True, repair_action="Set in-memory source object.")
        elif metadata["source"].get("mode") not in {"user-markdown", "mineru-pdf"}:
            metadata["source"]["mode"] = "user-markdown"
            self._issue(issues, "CSM-META-009", "Unsupported source.mode; assumed user-markdown.", repaired=True, repair_action="Set in-memory source.mode to user-markdown.")
        if "provenance" not in metadata["source"]:
            metadata["source"]["provenance"] = "none"
            self._issue(issues, "CSM-META-011", "Missing source.provenance; assumed none.", repaired=True, repair_action="Set in-memory source.provenance to none.")
        if not isinstance(metadata.get("extensions"), dict):
            metadata["extensions"] = {}
            self._issue(issues, "CSM-META-010", "Missing or invalid extensions object; supplied an empty object.", repaired=True, repair_action="Set in-memory extensions to an empty object.")

    def _parse_body(self, body: str, start_line: int) -> tuple[list[Block], list[str], list[str]]:
        # 规则对应: GEN-031/GBT-H02-H03（章条编号与层级）、GBT-X02（表格）、GBT-X06（公式）、
        # GEN-052（ssir 指令/引用注册表化，未知指令保留原文）。
        lines = body.splitlines()
        # 裸条号标题提升预扫描（2026-08-31）：MinerU 偶尔把章条标题抽成裸段落
        # （无 ## 前缀），用"已确认标题祖先链 + 父已提升子级跟随"级联恢复。
        confirmed_numbers, bare_candidates = _bare_heading_candidates(lines)
        bare_promoted = _promoted_bare_headings(confirmed_numbers, bare_candidates)
        blocks: list[Block] = []
        errors: list[str] = []
        warnings: list[str] = []
        pending: dict[str, Directive] = {}
        pending_table_caption: tuple[str, str] | None = None
        pending_table_unit: str | None = None
        # 图/表单位陈述行的挂起态（GEN-032）：单位行折进紧随的图/表节点，见 docs/12 §3.54。
        pending_figure_unit: str | None = None
        directive_ids: set[str] = set()
        last_table: Block | None = None
        box_open_line: int | None = None  # ssir:box 配对状态（未闭合开标记的行号）
        columns_open_line: int | None = None  # ssir:columns 配对状态（未闭合开标记行号）
        i = 0

        def line_no(index: int) -> int:
            return start_line + index

        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue

            if MINERU_PAGE_MARKER_RE.match(line):
                i += 1
                continue

            # ssir:box 显式文档框声明（2026-09-08 实施）：开/关成对行级事件块。
            # 手工编辑常带行首缩进/行尾空白 → 对 strip 后的行匹配（与普通段落
            # 无歧义：注释指令行只在块边界独立成行）。
            # 校验：不得嵌套（内层开忽略并报错）、关必须匹配开、开必须闭合
            # （宽容模式：未闭合的开延伸到文档尾，保证渲染确定性）。
            stripped_box_line = line.strip()
            box_match = BOX_MARKER_RE.match(stripped_box_line)
            if box_match:
                token = box_match.group(1)
                attrs_text = box_match.group(2)
                attr_match = BOX_STYLE_ATTR_RE.search(attrs_text)
                style = _unescape_attribute(attr_match.group(1)) if attr_match else "frame"
                extra = BOX_STYLE_ATTR_RE.sub("", attrs_text).strip()
                if style not in _BOX_STYLES:
                    warnings.append(f"line {line_no(i)}: ssir:box style {style!r} unsupported; frame used.")
                    style = "frame"
                if extra:
                    warnings.append(f"line {line_no(i)}: ssir:box attributes {extra!r} ignored.")
                if token == "box":
                    if box_open_line is not None:
                        errors.append(f"line {line_no(i)}: ssir:box must not nest inside another ssir:box (nested open ignored)")
                    else:
                        box_open_line = line_no(i)
                    blocks.append(
                        Block(
                            kind="box",
                            start_line=line_no(i),
                            end_line=line_no(i),
                            text=stripped_box_line,
                            data={"event": "open", "style": style},
                        )
                    )
                else:
                    if box_open_line is None:
                        errors.append(f"line {line_no(i)}: ssir:/box has no matching ssir:box open (ignored)")
                    else:
                        box_open_line = None
                    blocks.append(
                        Block(
                            kind="box",
                            start_line=line_no(i),
                            end_line=line_no(i),
                            text=stripped_box_line,
                            data={"event": "close", "style": style},
                        )
                    )
                i += 1
                continue

            # ssir:columns 显式并列声明（与 ssir:box 同型的事件块，2026-09-11）：
            # 开/列分隔/关三段行级独占指令；校验不得嵌套、列分隔必须在组内、
            # 关必须匹配开（宽容模式：错位事件忽略并报 CSM-STRUCT-006，确定性继续）。
            stripped_columns_line = line.strip()
            columns_match = COLUMNS_MARKER_RE.match(stripped_columns_line)
            if columns_match:
                token = columns_match.group(1)
                attrs_text = columns_match.group(2)
                widths: list[float] | None = None
                widths_match = COLUMNS_WIDTHS_ATTR_RE.search(attrs_text)
                if widths_match:
                    raw_widths = _unescape_attribute(widths_match.group(1))
                    try:
                        parsed_widths = [float(item) for item in re.split(r"[,，\s]+", raw_widths) if item]
                    except ValueError:
                        parsed_widths = []
                    if parsed_widths and all(item > 0 for item in parsed_widths):
                        widths = parsed_widths
                    else:
                        warnings.append(f"line {line_no(i)}: ssir:columns widths {raw_widths!r} invalid; equal widths used.")
                    attrs_text = COLUMNS_WIDTHS_ATTR_RE.sub("", attrs_text)
                extra = attrs_text.strip()
                if extra:
                    warnings.append(f"line {line_no(i)}: ssir:columns attributes {extra!r} ignored.")
                if token == "columns":
                    if columns_open_line is not None:
                        errors.append(f"line {line_no(i)}: ssir:columns must not nest inside another ssir:columns (nested open ignored)")
                    else:
                        columns_open_line = line_no(i)
                    blocks.append(
                        Block(
                            kind="columns",
                            start_line=line_no(i),
                            end_line=line_no(i),
                            text=stripped_columns_line,
                            data={"event": "open", "widths": widths},
                        )
                    )
                elif token == "column":
                    if columns_open_line is None:
                        errors.append(f"line {line_no(i)}: ssir:column has no enclosing ssir:columns (ignored)")
                    blocks.append(
                        Block(
                            kind="columns",
                            start_line=line_no(i),
                            end_line=line_no(i),
                            text=stripped_columns_line,
                            data={"event": "column"},
                        )
                    )
                else:
                    if columns_open_line is None:
                        errors.append(f"line {line_no(i)}: ssir:/columns has no matching ssir:columns open (ignored)")
                    else:
                        columns_open_line = None
                    blocks.append(
                        Block(
                            kind="columns",
                            start_line=line_no(i),
                            end_line=line_no(i),
                            text=stripped_columns_line,
                            data={"event": "close"},
                        )
                    )
                i += 1
                continue

            # 规则对应: GEN-118——脚注定义指令对
            # `<!--ssir:foot:N-->注释文字<!--ssir:/foot-->` 直接落为 footnote 块
            # （不走通用 directive 处理：它不是 SSIR 指令，而是脚注定义载体）。
            # 定义允许跨行（开标记与闭标记之间可以有换行），此处向下收集到闭标记。
            footnote_def = _FOOTNOTE_DEF_RE.search(line)
            if footnote_def is None and _FOOTNOTE_DEF_OPEN_RE.search(line):
                collected = [line]
                cursor = i + 1
                while cursor < len(lines) and _FOOTNOTE_DEF_CLOSE not in collected[-1]:
                    collected.append(lines[cursor])
                    cursor += 1
                merged = "\n".join(collected)
                footnote_def = _FOOTNOTE_DEF_RE.search(merged)
                if footnote_def is not None:
                    blocks.append(
                        Block(
                            kind="footnote",
                            start_line=line_no(i),
                            end_line=line_no(cursor - 1),
                            text=f"<!--ssir:foot:{footnote_def.group(1)}-->{footnote_def.group(2).strip()}{_FOOTNOTE_DEF_CLOSE}",
                            data={"label": footnote_def.group(1), "text": footnote_def.group(2).strip()},
                        )
                    )
                    i = cursor
                    continue
            if footnote_def:
                # 一行内可有**多对**定义（回环写回每条独立成行，人工编辑可能连排）。
                cursor = 0
                for match in _FOOTNOTE_DEF_RE.finditer(line):
                    leading = line[cursor: match.start()].strip()
                    if leading:
                        blocks.append(Block(kind="paragraph", start_line=line_no(i), end_line=line_no(i), text=leading))
                    blocks.append(
                        Block(
                            kind="footnote",
                            start_line=line_no(i),
                            end_line=line_no(i),
                            text=line[match.start(): match.end()],
                            data={"label": match.group(1), "text": match.group(2).strip()},
                        )
                    )
                    cursor = match.end()
                trailing = line[cursor:].strip()
                if trailing:
                    blocks.append(Block(kind="paragraph", start_line=line_no(i), end_line=line_no(i), text=trailing))
                i += 1
                continue
            directive_match = DIRECTIVE_RE.match(line)
            if directive_match:
                name = directive_match.group(1)
                attrs = {
                    key: _unescape_attribute(value)
                    for key, value in ATTR_RE.findall(directive_match.group(2))
                }
                if name not in SUPPORTED_DIRECTIVES:
                    # Preserve unsupported directives rather than silently losing user content.
                    blocks.append(
                        Block(
                            kind="unknown",
                            start_line=line_no(i),
                            end_line=line_no(i),
                            text=line,
                            data={"type_hint": f"unsupported-ssir-directive:{name}"},
                        )
                    )
                    warnings.append(f"line {line_no(i)}: unsupported ssir directive was preserved as unknown content: {name}")
                else:
                    if "id" in attrs and attrs["id"] in directive_ids:
                        errors.append(f"line {line_no(i)}: duplicate ssir id: {attrs['id']}")
                    if "id" in attrs:
                        directive_ids.add(attrs["id"])
                    if name in {"table", "figure", "formula", "unknown", "block"} and "id" not in attrs:
                        errors.append(f"line {line_no(i)}: ssir:{name} requires id")
                    directive = Directive(name=name, attrs=attrs, line=line_no(i))
                    if name == "table":
                        # 表题注被提升为标题/普通段落（heading-/paragraph-shaped
                        # caption）已暂存，在此合并进 table attrs；已有显式
                        # caption 时以显式为准，且编号不一致的暂存题注不合并
                        # （防把正文"表5 …"误并进表4 的 directive）。
                        if pending_table_caption is not None:
                            if "caption-number" not in attrs or attrs["caption-number"] == pending_table_caption[0]:
                                attrs.setdefault("caption-number", pending_table_caption[0])
                                attrs.setdefault("caption", pending_table_caption[1])
                            pending_table_caption = None
                        # "单位为毫米" 等单位行折进 unit 属性（渲染右对齐紧贴表格）。
                        if pending_table_unit is not None:
                            attrs.setdefault("unit", pending_table_unit)
                            pending_table_unit = None
                    if name == "table-merge":
                        if last_table is None:
                            errors.append(f"line {line_no(i)}: ssir:table-merge must follow a table")
                        elif attrs.get("table") != (last_table.directive.attrs.get("id") if last_table.directive else None):
                            errors.append(f"line {line_no(i)}: ssir:table-merge references a different table")
                        else:
                            last_table.data.setdefault("merges", []).append(attrs)
                    else:
                        pending[name] = directive
                i += 1
                continue

            heading = HEADING_RE.match(line)
            if heading:
                heading_text = heading.group(2)
                # 表题注被提升为标题（"## 表4 物理性能要求"，GEN-032/033）：
                # 若形如「表N 题名」且后随（可跨空行）ssir:table directive 或
                # 表格行，则降级为表格 caption 并入待处理的 table attrs，
                # 避免渲染出「表4 物理性能要求」+「表4」双题注。
                table_heading_caption = TABLE_HEADING_CAPTION_RE.match(heading_text)
                if table_heading_caption and heading.group(1).count("#") >= 2:
                    lookahead = i + 1
                    while lookahead < len(lines) and not lines[lookahead].strip():
                        lookahead += 1
                    next_line = lines[lookahead].strip() if lookahead < len(lines) else ""
                    next_table = next_line.startswith("<!-- ssir:table ")
                    if not next_table and next_line.startswith("|") and lookahead + 1 < len(lines):
                        next_table = bool(TABLE_SEPARATOR_RE.match(lines[lookahead + 1].strip()))
                    if next_table:
                        pending_table_caption = (
                            table_heading_caption.group(1),
                            table_heading_caption.group(2),
                        )
                        warnings.append(
                            f"line {line_no(i)}: heading-shaped table caption was folded into the table caption "
                            f"({table_heading_caption.group(1)} {table_heading_caption.group(2)!r})."
                        )
                        i += 1
                        continue
                # GBT-C12 列项误识别为标题：MinerU 偶尔把列项（如 "c）定型和
                # 固化时间；"）提升成 ## 标题，导致渲染时按标题样式大缩进。
                # 标题文本若形如列项（字母/数字 + 全/半角括号）则降级为列项
                # 块，与相邻 a)/b) 同层对齐。真实章条号（5.1、A.1）不含括号，
                # 不会被误降。
                numbered_item = NUMBERED_ITEM_RE.match(heading_text)
                if numbered_item and heading.group(1).count("#") >= 2:
                    marker = numbered_item.group(1)
                    if marker.endswith(")"):
                        marker = marker[:-1] + "）"
                    blocks.append(
                        Block(
                            kind="list",
                            start_line=line_no(i),
                            end_line=line_no(i),
                            text=heading_text,
                            data={"items": [{"marker": marker, "text": numbered_item.group(2), "line": str(line_no(i))}]},
                        )
                    )
                    warnings.append(f"line {line_no(i)}: heading shaped like a list item was demoted to a list item ({marker} {numbered_item.group(2)!r}).")
                    i += 1
                    continue
                blocks.append(
                    Block(
                        kind="heading",
                        start_line=line_no(i),
                        end_line=line_no(i),
                        text=heading_text,
                        level=len(heading.group(1)),
                        directive=pending.pop("block", None),
                    )
                )
                i += 1
                continue

            if line.startswith("$$"):
                formula_directive = pending.pop("formula", None)
                start = i
                formula_lines = [line[2:]]
                i += 1
                while i < len(lines) and not lines[i].startswith("$$"):
                    formula_lines.append(lines[i])
                    i += 1
                if i >= len(lines):
                    errors.append(f"line {line_no(start)}: unterminated formula block")
                    break
                closing = lines[i][2:]
                if closing.strip():
                    formula_lines.append(closing)
                i += 1
                number = ""
                if i < len(lines) and re.match(r"^式[（(].+[）)]\s*$", lines[i].strip()):
                    number = lines[i].strip()
                    i += 1
                blocks.append(
                    Block(
                        kind="formula",
                        start_line=line_no(start),
                        end_line=line_no(i - 1),
                        text="\n".join(formula_lines).strip(),
                        directive=formula_directive,
                        data={"number": number},
                    )
                )
                continue

            if line.startswith("|") and i + 1 < len(lines) and TABLE_SEPARATOR_RE.match(lines[i + 1]):
                table_directive = pending.pop("table", None)
                start = i
                rows = [_split_table_row(line)]
                i += 2
                while i < len(lines) and lines[i].startswith("|"):
                    rows.append(_split_table_row(lines[i]))
                    i += 1
                width = len(rows[0])
                for row_index, row in enumerate(rows, start=1):
                    if len(row) != width:
                        errors.append(
                            f"line {line_no(start + row_index + 1)}: table row has {len(row)} cells; expected {width}"
                        )
                blocks.append(
                    Block(
                        kind="table",
                        start_line=line_no(start),
                        end_line=line_no(i - 1),
                        directive=table_directive,
                        data={"rows": rows, "header_rows": 1},
                    )
                )
                last_table = blocks[-1]
                continue

            if line.startswith(">"):
                start = i
                quote_lines: list[str] = []
                while i < len(lines) and lines[i].startswith(">"):
                    quote_lines.append(lines[i][1:].lstrip())
                    i += 1
                quote_text = "\n".join(quote_lines)
                figure_directive = pending.pop("figure", None)
                if figure_directive or quote_text.startswith("[图"):
                    blocks.append(
                        Block(
                            kind="figure",
                            start_line=line_no(start),
                            end_line=line_no(i - 1),
                            text=quote_text,
                            directive=figure_directive,
                        )
                    )
                else:
                    kind = "note"
                    if quote_text.startswith("示例："):
                        kind = "example"
                    elif quote_text.startswith("警示："):
                        kind = "warning"
                    elif not quote_text.startswith("注"):
                        kind = "quote"
                    blocks.append(Block(kind=kind, start_line=line_no(start), end_line=line_no(i - 1), text=quote_text))
                continue

            image = IMAGE_RE.match(line)
            if image:
                blocks.append(
                    Block(
                        kind="figure",
                        start_line=line_no(i),
                        end_line=line_no(i),
                        text=image.group(1),
                        directive=pending.pop("figure", None),
                        data={"asset_ref": image.group(2), "unit": pending_figure_unit},
                    )
                )
                pending_figure_unit = None
                i += 1
                continue

            if line.startswith("```"):
                start = i
                fence = line[:3]
                code_lines: list[str] = []
                i += 1
                while i < len(lines) and not lines[i].startswith(fence):
                    code_lines.append(lines[i])
                    i += 1
                if i >= len(lines):
                    errors.append(f"line {line_no(start)}: unterminated code fence")
                    break
                i += 1
                formula_directive = pending.pop("formula", None)
                unknown_directive = pending.pop("unknown", None)
                if formula_directive:
                    number = ""
                    if i < len(lines) and re.match(r"^式[（(].+[）)]\s*$", lines[i].strip()):
                        number = lines[i].strip()
                        i += 1
                    blocks.append(
                        Block(
                            kind="formula",
                            start_line=line_no(start),
                            end_line=line_no(i - 1),
                            text="\n".join(code_lines),
                            directive=formula_directive,
                            data={"number": number, "format": "raw"},
                        )
                    )
                elif unknown_directive:
                    blocks.append(
                        Block(
                            kind="unknown",
                            start_line=line_no(start),
                            end_line=line_no(i - 1),
                            text="\n".join(code_lines),
                            directive=unknown_directive,
                        )
                    )
                else:
                    blocks.append(
                        Block(
                            kind="paragraph",
                            start_line=line_no(start),
                            end_line=line_no(i - 1),
                            text="\n".join(code_lines),
                            data={"code_fence": True},
                        )
                    )
                continue

            if self._is_list_line(line):
                start = i
                list_directive = pending.pop("list", None)
                items: list[dict[str, str]] = []
                while i < len(lines):
                    if self._is_list_line(lines[i]):
                        marker, item_text = self._parse_list_line(lines[i])
                        items.append({"marker": marker, "text": item_text, "line": str(line_no(i))})
                        i += 1
                        continue
                    if not lines[i].strip():
                        # Loose list (CommonMark): blank lines between list items
                        # stay inside the list; MinerU 常以空行分隔各列项（GBT-C12）。
                        lookahead = i
                        while lookahead < len(lines) and not lines[lookahead].strip():
                            lookahead += 1
                        if lookahead < len(lines) and self._is_list_line(lines[lookahead]):
                            i = lookahead
                            continue
                    break
                blocks.append(
                    Block(
                        kind="list",
                        start_line=line_no(start),
                        end_line=line_no(i - 1),
                        directive=list_directive,
                        data={"items": items},
                    )
                )
                continue

            table_caption = TABLE_CAPTION_RE.match(line)
            if table_caption and "table" in pending:
                next_index = i + 1
                while next_index < len(lines) and not lines[next_index].strip():
                    next_index += 1
                if next_index < len(lines) and lines[next_index].startswith("|"):
                    pending["table"].attrs["caption-number"] = table_caption.group(1)
                    pending["table"].attrs["caption"] = table_caption.group(2)
                    i += 1
                    continue

            bare_caption = TABLE_BARE_CAPTION_RE.match(line)
            if bare_caption and "table" in pending:
                next_index = i + 1
                while next_index < len(lines) and not lines[next_index].strip():
                    next_index += 1
                if next_index < len(lines) and lines[next_index].startswith("|"):
                    # Bare "表 N" caption (number only, no title) — keep the
                    # number so GBT-X02 passes; no caption attribute.
                    pending["table"].attrs["caption-number"] = bare_caption.group(1)
                    i += 1
                    continue

            # 表题注被抽成普通段落（"表4 安装配合面的同轴度"，GEN-032/033 变体）：
            # 位于 ssir:table directive 之前（可跨空行与"单位为毫米"等单位行）时，
            # 与 heading-shaped 题注一样折进 pending_table_caption，避免渲染出
            # 「表4 安装配合面的同轴度」+「表4」双题注。判定收窄防误伤正文：
            # 单行、无句末标点、长度 ≤ 40、后随（跳过空行/单位行）表格。
            paragraph_caption = TABLE_HEADING_CAPTION_RE.match(line.strip())
            if paragraph_caption and not any(mark in line for mark in "。；，："):
                lookahead = i + 1
                while lookahead < len(lines):
                    stripped = lines[lookahead].strip()
                    if not stripped:
                        lookahead += 1
                        continue
                    if TABLE_UNIT_LINE_RE.match(stripped):
                        lookahead += 1
                        continue
                    break
                next_line = lines[lookahead].strip() if lookahead < len(lines) else ""
                next_table = next_line.startswith("<!-- ssir:table ")
                if not next_table and next_line.startswith("|") and lookahead + 1 < len(lines):
                    next_table = bool(TABLE_SEPARATOR_RE.match(lines[lookahead + 1].strip()))
                if next_table and len(line.strip()) <= 40:
                    pending_table_caption = (paragraph_caption.group(1), paragraph_caption.group(2))
                    warnings.append(
                        f"line {line_no(i)}: paragraph-shaped table caption was folded into the table caption "
                        f"({paragraph_caption.group(1)} {paragraph_caption.group(2)!r})."
                    )
                    i += 1
                    continue

            # "单位为毫米" 等单位行（GEN-032：右对齐置于图/表上方紧贴框线）：独立成段
            # 且后随（可跨空行，可隔一个 ssir:figure 指令行）图/表时折进该图/表的
            # unit —— 否则它渲染成题注上方的独立段落，分页时会被留在前页末（满页的
            # 图另起一面时，"单位为毫米" 本应是新页第一行，见 docs/12 §3.54）。
            unit_line = TABLE_UNIT_LINE_RE.match(line.strip())
            if unit_line:
                lookahead = i + 1
                while lookahead < len(lines) and not lines[lookahead].strip():
                    lookahead += 1
                next_line = lines[lookahead].strip() if lookahead < len(lines) else ""
                if next_line.startswith("<!-- ssir:figure "):
                    # 指令形态的图（`ssir:figure` 指令行 + 图片行）：单位行仍写在指令之前。
                    lookahead += 1
                    while lookahead < len(lines) and not lines[lookahead].strip():
                        lookahead += 1
                    next_line = lines[lookahead].strip() if lookahead < len(lines) else ""
                if next_line.startswith("<!-- ssir:table "):
                    pending_table_unit = unit_line.group(1)
                    warnings.append(
                        f"line {line_no(i)}: table unit line was folded into the table "
                        f"(unit={unit_line.group(1)!r})."
                    )
                    i += 1
                    continue
                if IMAGE_RE.match(next_line):
                    pending_figure_unit = unit_line.group(1)
                    warnings.append(
                        f"line {line_no(i)}: figure unit line was folded into the figure "
                        f"(unit={unit_line.group(1)!r})."
                    )
                    i += 1
                    continue

            start = i
            # 裸条号标题提升（MinerU 把章条标题抽成裸段落，如 QB_T_2946-2020
            # 第 3 章 "3 产品分类和型号命名"）：候选编号是已确认标题的祖先链
            # 或父编号已提升时，提升为 heading，恢复章节结构（GBT-H03 连续
            # 编号、GBT-C06 引用清单边界）。保守：无确认标题时不提升。
            stripped_line = line.strip()
            if bare_promoted and not any((
                DIRECTIVE_RE.match(line),
                HEADING_RE.match(line),
                line.startswith(("$$", ">", "```")),
                IMAGE_RE.match(line),
                CSMParser._is_list_line(line),
            )):
                bare_match = BARE_HEADING_CANDIDATE_RE.match(stripped_line)
                if bare_match and bare_match.group(1) in bare_promoted:
                    level = bare_match.group(1).count(".") + 2
                    blocks.append(
                        Block(
                            kind="heading",
                            start_line=line_no(i),
                            end_line=line_no(i),
                            text=stripped_line,
                            level=level,
                            directive=pending.pop("block", None),
                        )
                    )
                    warnings.append(
                        f"line {line_no(i)}: bare numbered paragraph was promoted to a heading "
                        f"({bare_match.group(1)}, level {level}) by ancestor-chain promotion."
                    )
                    i += 1
                    continue
            # 段落行尾清理：MinerU 行尾常残留 Markdown 硬换行（两个尾随空格），
            # 会导致渲染时段落中途断行（如 "……25%时，  \n审查结论应为不通过"）。
            paragraph_lines = [line.rstrip()]
            i += 1
            while i < len(lines):
                if not lines[i].strip():
                    # 空行续接（6.4.2.4 "……列入多种方法时，\n应指明仲裁方法。"）：
                    # 上一行以连接性标点（，、）结尾且下一非空行不是新块时，视为
                    # 同一段落被 MinerU 误插空行，跳过空行继续收集（示例/注/图/表
                    # 引导语除外）。收窄到弱连接标点（2026-09-02，GB_3100-2026
                    # 3.7/4.2 型）：此前 "不以 。！？ 结尾" 会把术语行
                    # （"一贯单位制 coherent system of units"）与空行后的定义
                    # 正文并成一段；分号 "；" 与冒号 "：" 也排除——";"收尾的行
                    # 是完整分句（裸列项每条以 ；结尾，空行后必为新条目），
                    # "：" 后空行是引导语与裸列项的分界，续接都会吞掉逐条成行
                    # 的版式（4.2 七个定义常量）。
                    lookahead = i
                    while lookahead < len(lines) and not lines[lookahead].strip():
                        lookahead += 1
                    if (
                        lookahead < len(lines)
                        and not self._starts_new_block(lines, lookahead)
                        and paragraph_lines
                        and paragraph_lines[-1].endswith(("，", "、"))
                        and _starts_with_han(lines[lookahead].strip())
                        and not EX_LEAD_RE.match(lines[lookahead].strip())
                        and not NOTE_LEAD_RE.match(lines[lookahead].strip())
                    ):
                        i = lookahead
                        # 续接标记：跨空行续接的行之间不产生 \n（否则渲染折叠成
                        # 空格，词语仍可能断行——"确"+"立"型）。\x00 在 join 时移除。
                        paragraph_lines[-1] += "\x00"
                        continue
                    break
                if self._starts_new_block(lines, i):
                    break
                if MINERU_PAGE_MARKER_RE.match(lines[i]):
                    # MinerU page-range markers are provenance, not content;
                    # skip them even mid-paragraph so they never leak into the
                    # rendered PDF (GEN-005 页码标记不计入正文).
                    i += 1
                    continue
                paragraph_lines.append(lines[i].rstrip())
                i += 1
            paragraph_text = "\n".join(paragraph_lines).replace("\x00\n", "")
            block_directive = pending.pop("block", None)
            # 裸列项分行（2026-09-02，GB_3100-2026 4.2 七个定义常量型）：源文把
            # 每条独立成行、以 ；/。 收尾的枚举行收集成单段后，_markup 会把行内
            # 换行折叠成空格 → 七个常量挤成一行流。若段落含 ≥2 行且绝大多数行
            # 以句末标点（。；：;.）结尾、其中 ≥2 行以分号收尾，按行拆分为独立
            # 段落块，恢复逐条成行的版式（每条渲染为正文段，首行空两字）。
            enum_lines = [ln.strip().rstrip("$").strip() for ln in paragraph_text.splitlines() if ln.strip()]
            if _is_bare_enumeration(enum_lines):
                for enum_index, enum_line in enumerate(enum_lines):
                    enum_block = Block(
                        kind="paragraph",
                        start_line=line_no(start),
                        end_line=line_no(i - 1),
                        text=enum_line,
                        directive=block_directive if enum_index == 0 else None,
                    )
                    if NOTE_LEAD_RE.match(enum_line):
                        enum_block.kind = "note"
                    blocks.append(enum_block)
                continue
            # 6.3.5.2 类合并：MinerU 把「……告知乘客。6.3.5.2为了确保……」
            # 挤进同一段，导致条号无法回车顶格（GBT-B02）。在句末标点（。；）
            # 之后出现的点分条号处把段落拆分为两个块。
            # 行内注切分（GBT-X04 注引导语）：OCR 常把术语定义后的「注1：…。
            # 注2：…。」合并进定义段（GB_T_20001.6 3.1 型）。在「。注N：」
            # 句界处切分，使注成为独立块（渲染按 GBT-B10 小五号）。
            note_parts = [p.strip() for p in NOTE_SPLIT_RE.split(paragraph_text) if p.strip()]
            if not note_parts:
                note_parts = [paragraph_text.strip()]
            for note_part_index, note_part in enumerate(note_parts):
                parts = [p.strip() for p in CLAUSE_SPLIT_RE.split(note_part) if p.strip()]
                if not parts:
                    parts = [note_part]
                for part_index, part in enumerate(parts):
                    block = Block(
                        kind="paragraph",
                        start_line=line_no(start),
                        end_line=line_no(i - 1),
                        text=part,
                        directive=block_directive if (note_part_index == 0 and part_index == 0) else None,
                    )
                    if EX_HEADER_RE.match(part):
                        # 独立「示例N：」行（附录框式示例的标题）提升为标题，
                        # 使其进入 SSIR 结构树并在示例框内居中（GBT-B11）。
                        block.kind = "heading"
                        block.level = 2
                    elif NOTE_LEAD_RE.match(part):
                        # 独立「注：/注1：」行 → note 块（渲染小五号宋体）。
                        block.kind = "note"
                    if part.startswith("<!--") and "ssir:" in part[:60]:
                        # 形似 ssir 指令却未被任何指令分支识别的行（缺 -->、行尾
                        # 混排正文、未登记指令名等）：按普通段落保留不丢内容，但
                        # 显式告警，防止“标记原样渲染进 PDF”式静默泄漏。
                        warnings.append(
                            f"line {line_no(start)}: 疑似 ssir 指令行未被识别为指令"
                            f"（检查是否顶格/整行独占、以 --> 闭合、指令名已登记），"
                            f"已按普通段落保留: {part[:50]!r}"
                        )
                    blocks.append(block)

        for name, directive in pending.items():
            warnings.append(f"line {directive.line}: ssir:{name} has no following compatible block")
        if box_open_line is not None:
            errors.append(f"line {box_open_line}: ssir:box opened here is never closed; box extends to end of document")
        if columns_open_line is not None:
            errors.append(f"line {columns_open_line}: ssir:columns opened here is never closed; columns extend to end of document")
        blocks = _absorb_table_note_spill(blocks, warnings)
        return blocks, errors, warnings

    @staticmethod
    def _is_list_line(line: str) -> bool:
        return bool(UNORDERED_ITEM_RE.match(line) or NUMBERED_ITEM_RE.match(line))

    @staticmethod
    def _parse_list_line(line: str) -> tuple[str, str]:
        unordered = UNORDERED_ITEM_RE.match(line)
        if unordered:
            return unordered.group(1) or unordered.group(2) or unordered.group(3), unordered.group(4)
        numbered = NUMBERED_ITEM_RE.match(line)
        assert numbered
        marker = numbered.group(1)
        # 编号括号统一为全角（GBT-C19）：OCR 常混用 a) / a）——半角括号在
        # 渲染时与文字的视觉间隔明显小于全角括号，导致列表项间隔不统一。
        if marker.endswith(")"):
            marker = marker[:-1] + "）"
        return marker, numbered.group(2)

    @staticmethod
    def _starts_new_block(lines: list[str], index: int) -> bool:
        line = lines[index]
        stripped = line.strip()
        return bool(
            # ssir:box 标记容忍行首/行尾空白（手工编辑常带缩进，2026-09-08）
            (stripped and BOX_MARKER_RE.match(stripped))
            or (stripped and COLUMNS_MARKER_RE.match(stripped))
            or DIRECTIVE_RE.match(line)
            or HEADING_RE.match(line)
            or line.startswith("$$")
            or line.startswith(">")
            or line.startswith("```")
            or IMAGE_RE.match(line)
            or (line.startswith("|") and index + 1 < len(lines) and TABLE_SEPARATOR_RE.match(lines[index + 1]))
            or CSMParser._is_list_line(line)
        )

    @staticmethod
    def _validate_document(metadata: dict[str, Any], blocks: list[Block], errors: list[str]) -> None:
        # 规则对应: GBT-H02（章从 1 起连续编号）、GEN-050/052（id 唯一性与引用完整性）。
        headings = [block for block in blocks if block.kind == "heading"]
        h1 = [block for block in headings if block.level == 1]
        if len(h1) != 1:
            errors.append(f"CSM must contain exactly one H1; found {len(h1)}")
        elif h1[0].text != metadata.get("title"):
            errors.append("H1 title must exactly match front matter title")

        seen_ids: set[str] = set()
        for block in blocks:
            if block.directive and "id" in block.directive.attrs:
                block_id = block.directive.attrs["id"]
                if block_id in seen_ids:
                    errors.append(f"line {block.directive.line}: duplicate ssir id: {block_id}")
                seen_ids.add(block_id)

        chapters: list[int] = []
        for block in headings:
            if block.level == 2:
                match = re.match(r"^(\d+)\s+", block.text)
                if match:
                    chapters.append(int(match.group(1)))
        if chapters and chapters != list(range(1, max(chapters) + 1)):
            errors.append(f"main chapter numbering must be continuous from 1; found {chapters}")

    @staticmethod
    def _repair_tables(blocks: list[Block], issues: list[CSMIssue]) -> list[str]:
        """Pad short rows only; extra cells have no safe, semantics-preserving repair.

        规则对应: GBT-X02（表格一致性；短行补空、多余单元格报错不猜测修复）。
        """
        fatal_errors: list[str] = []
        for block in blocks:
            if block.kind != "table":
                continue
            rows: list[list[str]] = block.data["rows"]
            if not rows or not rows[0]:
                fatal_errors.append(f"line {block.start_line}: table has no usable header row")
                continue
            width = len(rows[0])
            for row_index, row in enumerate(rows):
                if len(row) > width:
                    fatal_errors.append(
                        f"line {block.start_line + row_index + 1}: table row has {len(row)} cells; expected {width}"
                    )
                elif len(row) < width:
                    missing = width - len(row)
                    row.extend([""] * missing)
                    CSMParser._issue(
                        issues,
                        "CSM-TABLE-001",
                        f"Table row had {len(row) - missing} cells; padded {missing} trailing empty cell(s) to match its header.",
                        line=block.start_line + row_index + 1,
                        repaired=True,
                        repair_action="Padded trailing empty table cells in memory.",
                    )
        return fatal_errors

    @staticmethod
    def _repair_stray_table_images(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """Fold a stray figure between two parts of a split table into the first
        part's last row (GBT-X02 表中图；GB_T_23132-2024 表2 型，CSM-TABLE-002).

        MinerU 跨页表格把某行单元格内的图排在 `<table>` 元素之外，读取顺序上
        表现为：前表 → 裸图 → 续表（题注带"续"）。该图其实是前表最后一行
        缺失的单元格图（旋转式行 试验区域分割 示意图）。全部条件满足才归位，
        否则保守不动：

        - 游离块是单张裸图（figure 块、有 asset_ref、无题注文本）；
        - 其前后相邻块都是表格块；
        - 两表 directive 的 caption-number 相同，且后表题注含"续"（跨页续表）；
        - 前表最后一行既含图单元格又含不含图单元格（说明该行确实有图、只是
          缺了一张——纯文本行不归位，避免把真正独立的图塞进表格）。

        归位目标：前表最后一行第一个不含图、且非首格（行标题列）的单元格；
        无法唯一确定（如多个候选列）时不猜。修复同时删除游离 figure 块，
        canonical/SSIR/render 三侧一致（_render_block 按 rows 输出表格、
        按 asset_ref 输出图，roundtrip 等价保持）。
        """
        cell_image_re = re.compile(r"!\[(?:[^\]]*)\]\(([^)]+)\)")
        for index, block in enumerate(blocks):
            if block.kind != "figure" or "asset_ref" not in block.data:
                continue
            if block.text.strip():
                continue  # 带题注文本的图不归位（是独立图，不是表中图）
            if index == 0 or index + 1 >= len(blocks):
                continue
            first_table = blocks[index - 1]
            second_table = blocks[index + 1]
            if first_table.kind != "table" or second_table.kind != "table":
                continue
            first_directive = first_table.directive
            second_directive = second_table.directive
            if not first_directive or not second_directive:
                continue
            first_number = first_directive.attrs.get("caption-number")
            second_number = second_directive.attrs.get("caption-number")
            second_caption = str(second_directive.attrs.get("caption", ""))
            if not first_number or first_number != second_number or "续" not in second_caption:
                continue
            rows: list[list[str]] = first_table.data.get("rows", [])
            if not rows:
                continue
            last_row = rows[-1]
            if len(last_row) < 2:
                continue
            has_image_cell = any(cell_image_re.search(cell) for cell in last_row)
            if not has_image_cell:
                continue
            # 归位到第一个不含图且非首格（行标题列）的单元格；多个候选不猜。
            target = next(
                (col for col, cell in enumerate(last_row[1:], start=1) if not cell_image_re.search(cell)),
                None,
            )
            if target is None:
                continue
            ref = str(block.data["asset_ref"])
            last_row[target] = (last_row[target].rstrip() + " " if last_row[target].strip() else "") + f"![]({ref})"
            CSMParser._issue(
                issues,
                "CSM-TABLE-002",
                f"Stray figure between two parts of a split table (表{first_number}…续) folded into the last row cell {target + 1} of the first part.",
                line=block.start_line,
                repaired=True,
                repair_action="Moved the bare image into the preceding table's last-row cell in memory.",
            )
            del blocks[index]

    @staticmethod
    def _repair_table_image_layout(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """表中图单元格版式修复（CSM-TABLE-003；GB_T_23132-2024 表2 型）。

        原则：**不把"图在上/文字在下"规定为通用版式**——图与说明文字的
        上下关系是各表原文自行安排的（GB_T_23132 表2 第2列恰好是 上图下
        文字，其它表未必）。渲染端（pdf_renderer._render_cell）按数据
        （cell 文本）顺序忠实复现：cell 为 `![]() 文字` 则图在上文字在下，
        `文字 ![]()` 则文字在上图在下。本修复只纠正**有明确证据**的提取
        错误：

        B. **说明文字错列**（有列间证据）：某行某列是"图+文字"，而该列在
           表内其它数据行都是纯图（该列文字仅此一行）、且该行**前一列**是
           纯图格——说明文字本属于前一列（图旁的说明），被 MinerU 误归到
           后一列。把文字移回前一列纯图格之后，原格只留图。保守条件（全部
           满足才移动，否则不猜）：数据行数 ≥ 2；当前格同时含图与文字；
           该列文字仅此一行（col_text_count == 1）且该列是图列；前一格是
           纯图格（文字落点明确）。

        A. **格内顺序**（仅作为 B 的配套，不独立触发）：只有当该表（或与其
           同 caption-number 的跨页续表）发生了 B 时，才把相关表块的图文混合
           单元格统一重排为 图在前、文字在后——B 移动的文字以"图前文字后"
           落位，同表（含跨页两部分）其它图文混合单元格保持同向才一致。
           **未发生 B 的表不重排**，严格按提取顺序渲染（原文若为文字在上
           图在下，数据保持原样，渲染也保持原样）。

        渲染端保持中立：_render_cell 按 cell 文本顺序流式输出（文字段 →
        图），数据怎么排就怎么渲染。
        """
        cell_image_re = re.compile(r"!\[(?:[^\]]*)\]\(([^)]+)\)")
        # 拆分用无捕获组版本：re.split 遇到捕获组会把捕获内容也放进结果
        # （导致裸 assetRef 泄漏进文字片段）。
        cell_image_split_re = re.compile(r"!\[[^\]]*\]\([^)]+\)")

        def _plain(cell: str) -> str:
            return cell_image_re.sub("", cell).strip()

        def _images(cell: str) -> list[str]:
            return [m.group(0) for m in cell_image_re.finditer(cell)]

        def _reorder_images_first(cell: str) -> str:
            """把全部图片标记提到文字之前（图在上、说明文字在下）。"""
            images = _images(cell)
            if not images:
                return cell
            texts = [part.strip() for part in cell_image_split_re.split(cell) if part.strip()]
            if not texts:
                return cell
            # 已满足"图在前"时不重排（避免无谓改动）。
            first_text = cell_image_split_re.split(cell)[0]
            if not first_text.strip():
                return cell
            joined = " ".join(images) + " " + " ".join(texts)
            return joined.strip()

        table_blocks = [block for block in blocks if block.kind == "table"]
        tables_info: list[tuple[Block, list[list[str]], str | None]] = []
        for block in table_blocks:
            rows = block.data.get("rows", [])
            header_rows = int(block.data.get("header_rows", 1) or 1)
            number = None
            if block.directive:
                number = block.directive.attrs.get("caption-number")
            tables_info.append((block, rows, number))

        # B. 列错位：文字归位到前一列纯图格；收集发生过移动的表（及同号续表）。
        moved_numbers: set[str] = set()
        for block, rows, number in tables_info:
            header_rows = int(block.data.get("header_rows", 1) or 1)
            data_rows = rows[header_rows:]
            if not data_rows:
                continue
            width = len(rows[0]) if rows else 0
            col_text_count = [0] * width
            col_image_count = [0] * width
            for row in data_rows:
                for c, cell in enumerate(row):
                    if c >= width:
                        continue
                    if _plain(cell):
                        col_text_count[c] += 1
                    if _images(cell):
                        col_image_count[c] += 1
            if len(data_rows) < 2:
                continue
            moved = False
            for row in data_rows:
                for c in range(1, len(row)):
                    cell = row[c]
                    if not cell or not _images(cell) or not _plain(cell):
                        continue
                    # 该列文字仅此一行（col_text_count==1，当前格必含文字）、
                    # 且该列是图列 → 说明文字疑似被误归到后一列。
                    if col_text_count[c] != 1 or col_image_count[c] == 0:
                        continue
                    prev = row[c - 1]
                    if not _images(prev) or _plain(prev):
                        continue  # 前一格不是纯图格 → 无明确落点，不猜
                    text = _plain(cell)
                    row[c - 1] = (prev.rstrip() + " " if prev.strip() else "") + text
                    row[c] = " ".join(_images(cell))
                    moved = True
                    CSMParser._issue(
                        issues,
                        "CSM-TABLE-003",
                        f"Cell text at data-row {data_rows.index(row) + 1} col {c + 1} belongs to the image column {c} (image-first layout); moved after the image.",
                        line=block.start_line,
                        repaired=True,
                        repair_action="Moved the text after the image in the previous cell; left only the image in the original cell.",
                    )
            if moved and number:
                moved_numbers.add(number)

        # A. 格内顺序——仅当本表（或同号跨页续表）发生列错位（B）时统一。
        for block, rows, number in tables_info:
            if number is None or number not in moved_numbers:
                continue
            header_rows = int(block.data.get("header_rows", 1) or 1)
            data_rows = rows[header_rows:]
            for row in data_rows:
                for c, cell in enumerate(row):
                    reordered = _reorder_images_first(cell)
                    if reordered != cell:
                        row[c] = reordered
                        CSMParser._issue(
                            issues,
                            "CSM-TABLE-003",
                            f"Cell (row {data_rows.index(row) + 1}, col {c + 1}) reordered to image-first layout (figure above, caption text below).",
                            line=block.start_line,
                            repaired=True,
                            repair_action="Moved image markdown before the caption text in the table cell.",
                        )

    @staticmethod
    def _repair_list_markers(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """Correct OCR glyph-confused list markers in context (CSM-OCR-001).

        OCR 常把字母 l）误读为数字 1）、把 1 误读为 l/I、把 0 误读为 O。
        孤立纠正会误伤真子列表，因此只在多数派上下文中纠正少数派里的
        可混淆项（多数派至少 2 个且严格多于少数派）：
        - 字母多数 + 数字 outlier 1）/1） → l）/l）；
        - 数字多数 + 字母 outlier l/I）/l/I） → 1）/1）；O）/O） → 0）/0）。
        """
        letter_re = re.compile(r"^[A-Za-z][)）]$")
        digit_re = re.compile(r"^\d+[)）]$")
        letter_fix = {"1)": "l)", "1）": "l）"}
        digit_fix = {"l)": "1)", "l）": "1）", "I)": "1)", "I）": "1）", "O)": "0)", "O）": "0）"}
        for block in blocks:
            if block.kind != "list":
                continue
            items: list[dict[str, str]] = block.data["items"]
            markers = [str(item["marker"]) for item in items]
            if len(markers) < 3:
                continue
            # 符号族统一（CSM-OCR-001 扩展）：OCR 把 ●/•/·/○ 混读（源 PDF
            # 同一列表通常全用同一符号，如 GB_T_20001.6 6.1/6.2 全 ● 但 OCR
            # 把部分读成 •），也把同一破折号读成长度不一的横杠（GB_T_1.1-2020
            # 前言 8.3 列项混用 -/—/——/———，GB_T_20001.4/5/6/10 前言清单
            # 同样常见）。破折号族与项目符号族同属"符号型标记"：同一条款下
            # 列表符号应一致，按多数派统一（≥2 且严格多于其余），消除个别
            # 误识项（GBT-C12 列表层次）。字母/数字编号（a）/1））属另一
            # 维度，不参与符号统一，留给下方字形混淆纠正；真嵌套列项
            # （第一层次 —— 项下挂第二层次 · 子项）在扁平块里通常 1:1/2:2
            # 平手，多数派不明确时保守不统一，渲染层仍按层次区分样式。
            symbol_counts: dict[str, int] = {}
            for marker in markers:
                if marker in _BULLET_MARKERS or _DASH_RUN_RE.match(marker):
                    symbol_counts[marker] = symbol_counts.get(marker, 0) + 1
            if len(symbol_counts) >= 2:
                majority = max(symbol_counts, key=lambda k: symbol_counts[k])  # type: ignore[arg-type]
                minority = sum(symbol_counts.values()) - symbol_counts[majority]
                if symbol_counts[majority] >= 2 and symbol_counts[majority] > minority:
                    for target, marker in enumerate(markers):
                        if marker in _BULLET_MARKERS or _DASH_RUN_RE.match(marker):
                            if marker != majority:
                                items[target]["marker"] = majority
                                CSMParser._issue(
                                    issues,
                                    "CSM-OCR-001",
                                    f"List marker {marker!r} unified to {majority!r} "
                                    f"(majority of sibling list symbols).",
                                    line=int(items[target].get("line", 0)) or None,
                                    repaired=True,
                                    repair_action=f"Rewrote marker {marker} to {majority} in memory.",
                                )
                continue
            letter_indexes = [i for i, m in enumerate(markers) if letter_re.match(m)]
            digit_indexes = [i for i, m in enumerate(markers) if digit_re.match(m)]
            if len(letter_indexes) + len(digit_indexes) != len(markers):
                continue  # 混入破折号/间隔号等无编号标记，上下文不明确
            if len(letter_indexes) >= 2 and len(letter_indexes) > len(digit_indexes) and digit_indexes:
                targets = [i for i in digit_indexes if markers[i] in letter_fix]
                fix, context = letter_fix, "letters"
            elif len(digit_indexes) >= 2 and len(digit_indexes) > len(letter_indexes) and letter_indexes:
                targets = [i for i in letter_indexes if markers[i] in digit_fix]
                fix, context = digit_fix, "digits"
            else:
                continue
            for target in targets:
                original = markers[target]
                corrected = fix[original]
                items[target]["marker"] = corrected
                CSMParser._issue(
                    issues,
                    "CSM-OCR-001",
                    f"List marker {original!r} is a likely OCR misread of {corrected!r} "
                    f"(majority of sibling markers are {context}).",
                    line=int(items[target].get("line", 0)) or None,
                    repaired=True,
                    repair_action=f"Rewrote marker {original} to {corrected} in memory.",
                )

    @staticmethod
    def _repair_clause_numbers(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """Re-insert decimal points that a broken text layer dropped from clause
        numbers (CSM-OCR-002).

        文本层损坏型 PDF（如 GB_T_43726-2024）经 MinerU auto 抽取后，标题里的
        点号整段丢失：7.4.2 → 742、5.10 → 510、5.2.1 → 521（数字本身完好，
        只是少了分隔点；同一文档内 7.4.2.2 又可能带点——损坏逐行不一致）。
        本修复用编号连续性约束为每个标题选择唯一合法的拆点：
        - 章级编号连续（1,2,3…，新章 = 当前章 + 1）；
        - 条级编号 = 父号前缀 + 连续兄弟（N.1, N.2…）或子条（父号 + .1）。
        无法唯一/合法拆点时保持原样（不猜测），由 GBT-H03 合规检查记录。
        """
        heading_blocks = [block for block in blocks if block.kind == "heading"]
        stack: list[int] = []
        for block in heading_blocks:
            match = re.match(r"^(\d[\d.]*)(\s*)(.*)$", block.text)
            if not match:
                continue
            raw_number, separator, title = match.group(1), match.group(2), match.group(3)
            placements = _clause_digit_placements(raw_number.replace(".", ""))
            if not placements:
                continue
            chosen: tuple[int, ...] | None = None
            if not stack:
                # 文档首个编号标题：章号取单段（"1 范围" → 1）。
                single = (int(placements[0][0]),) if len(placements[0]) == 1 else None
                if single is not None:
                    chosen = single
            else:
                for placement in placements:
                    if _clause_continuation(placement, stack) is not None:
                        chosen = placement
                        break
            if chosen is None:
                continue
            new_number = ".".join(str(segment) for segment in chosen)
            if new_number == raw_number:
                stack = list(chosen)
                continue
            block.text = f"{new_number}{separator}{title}"
            stack = list(chosen)
            CSMParser._issue(
                issues,
                "CSM-OCR-002",
                f"Clause number {raw_number!r} lost its decimal separators; restored as "
                f"{new_number!r} (continuity with neighbouring headings).",
                line=block.start_line,
                repaired=True,
                repair_action=f"Rewrote heading number {raw_number} to {new_number} in memory.",
            )

    @staticmethod
    def _repair_term_entry_headings(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """Normalize flattened term entries into one numbered heading (CSM-OCR-007).

        术语和定义要素里的术语条目被 MinerU 抽成两种形态，都必须归一为单条编号
        标题「3.1.2 标准　standard」（GB/T 1.1-2020 8.7.3.1、10.3.5：条目编号
        单独占一行顶格、术语与英文对应词在下一行、中英文之间空一个汉字）：

        - **标题形态**：``## 3.1.2`` + ``## 标准　standard``。两条都是 ##（与章
          同级）时，编号标题会脱离 3.1 组提升到文档根级，标准层级被破坏
          （3.1.2/3.1.3/3.2.x 全变成章 3 的兄弟）；
        - **段落形态**：``3.1.1`` + ``标准化文件　standardizing document``。两条
          都是普通段落（GB_T_1.1-2020 第 3 章 3.1.1 即此形态）：编号与术语被抽成
          正文，条目在 SSIR 里没有结构节点，标题跟着正文缩进两字排版，渲染出的
          条目编号不再顶格、术语也不单独占行。

        合并后交给 _repair_heading_levels 按编号段数提升层级（3.1.2 → #### 或
        level 4），编号修复后自然嵌套回 3.1 组下；术语行原先承载的定义/注等后续
        块不受影响，仍接在合并标题之后，从而随术语节点一起入树。

        段落形态是更强的改写（把正文段落提升为结构标题），故只在**术语和定义要素
        内部**生效（8.7：该要素应设置为第 3 章，以章标题含“术语”判定）；标题形态
        维持原判据（两条同级标题，编号为 3 段以上）。术语行的中英文间隙一律归一到
        U+3000（与 CSM-OCR-003 同规），使两种形态渲染出的“空一个汉字”一致。
        """
        pure_number = re.compile(r"^(\d+(?:\.\d+){2,})$")
        bare_number = re.compile(r"^(\d+(?:\.\d+)*)$")
        # 术语行判据（term_entry_pair，与 CSM-OCR-003 间隙归一、builder 的 term/englishTerm
        # 抽取同一份字符类）：刻意要求英文部分以拉丁字母开头且不含汉字，避免把「概述」
        # 「示例」等无编号标题、定义段误并。
        term_gap = "\u3000"
        chapter_re = re.compile(r"^\d+\s+\S")
        # 「术语和定义」要素内的块下标（供段落形态判据用；与 _repair_text_spacing
        # 的 in_terms 跟踪同源）。
        in_terms_indexes: set[int] = set()
        in_terms = False
        for index, block in enumerate(blocks):
            if block.kind == "heading":
                text = block.text.strip()
                if chapter_re.match(text):
                    in_terms = "术语" in text
            if in_terms:
                in_terms_indexes.add(index)

        merges: list[tuple[int, str, bool]] = []  # (编号块下标, 合并文本, 是否需提升为标题)
        i = 0
        while i < len(blocks) - 1:
            first = blocks[i]
            second = blocks[i + 1]
            number_match = None
            promote = False
            if first.kind == "heading" and second.kind == "heading":
                number_match = pure_number.match(first.text.strip())
            elif (
                first.kind == "paragraph"
                and second.kind == "paragraph"
                and i in in_terms_indexes
            ):
                number_match = bare_number.match(first.text.strip())
                promote = number_match is not None
            if number_match:
                second_text = second.text.strip()
                pair = term_entry_pair(second_text) if not pure_number.match(second_text) else None
                if pair:
                    merged = f"{number_match.group(1)} {pair[0]}{term_gap}{pair[1]}"
                    merges.append((i, merged, promote))
                    i += 2
                    continue
            i += 1
        for index, merged_text, promote in merges:
            blocks[index].text = merged_text
            if promote:
                # 段落形态：先变成标题块（层级交给 _repair_heading_levels 按编号
                # 段数提升到 ####），使条目成为结构节点。
                blocks[index].kind = "heading"
                blocks[index].level = 2
        for index, _merged_text, promote in reversed(merges):
            second = blocks[index + 1]
            CSMParser._issue(
                issues,
                "CSM-OCR-007",
                (
                    f"Term entry split across paragraph and term line merged into one heading: "
                    f"{blocks[index].text!r} (removed term line {second.text!r} at line {second.start_line})."
                    if promote
                    else f"Flattened term-entry headings merged into one heading: {blocks[index].text!r} "
                    f"(removed duplicate heading {second.text!r} at line {second.start_line})."
                ),
                line=blocks[index].start_line,
                repaired=True,
                repair_action=(
                    "Promoted the term-entry number paragraph to a title and merged the term line into it."
                    if promote
                    else "Merged the term-title heading into the numbered heading so the term nests under its numbered group."
                ),
            )
            del blocks[index + 1]

    def _repair_split_multipart_title(self, blocks: list[Block], issues: list[CSMIssue]) -> None:
        """合并相邻两个 H1 拆开的多部分标准名称（CSM-STRUCT-004）。

        封面/正文首页把名称元素分两行排印时，MinerU/OCR 产出两个连续 H1：
        「# 主体要素」+「# 第N部分：分部分名称」（GB_T_20001.10-2014 正文首页
        「标准编写规则」/「第10部分：产品标准」）。GB/T 1.1-2020 8.2.2 名称元素
        间空一个汉字 → 合并为单个 H1「主体要素 第N部分：…」（与 merge 侧
        _normalize_part_title 同规），同时消除 CSM-STRUCT-003 对多余 H1 的计数。
        只在两个 H1 相邻（中间无任何内容块）、后者完整为「第N部分：…」且前者
        不含“部分”字样时合并；其余形态不猜。
        """
        index = 0
        while index + 1 < len(blocks):
            head, part = blocks[index], blocks[index + 1]
            if head.kind != "heading" or head.level != 1 or part.kind != "heading" or part.level != 1:
                index += 1
                continue
            head_text = head.text.strip()
            part_text = part.text.strip()
            if not head_text or not part_text or "部分" in head_text or not _PART_TITLE_RE.match(part_text):
                index += 1
                continue
            if len(head_text) + len(part_text) > 60:
                index += 1
                continue
            merged = f"{head_text} {part_text}"
            self._issue(
                issues, "CSM-STRUCT-004",
                f"Multi-part title split across two adjacent H1 lines "
                f"({head_text!r} + {part_text!r}); merged to {merged!r}.",
                line=head.start_line, repaired=True,
                repair_action=f"Merged the split H1 lines into {merged!r} in memory.",
            )
            head.text = merged
            head.end_line = part.end_line
            del blocks[index + 1]
            index += 1  # 合并一对后继续向后扫描（封面与正文首页可能各出现一对）

    def _reclassify_footnote_definitions(self, blocks: list[Block], issues: list[CSMIssue]) -> None:
        """脚注定义识别与绑定（GEN-118；docs/07 §6.7）。

        语法：正文引用点 ``[foot:N]``；定义 = 指令对
        ``<!--ssir:foot:N-->注释文字<!--ssir:/foot-->``。接受三种 canonical 摆放形态
        （回环写回统一用「定义独立成行、紧随引用段之后」）：
        1) 定义独立成行；
        2) 定义与段落同处一行（人工编辑遗留），解析时从行内剥离为独立 footnote 块
           （可多条连续）；
        3) 段首定义行与后续内容粘连成一个多行段——剥离定义，其余行保留为段落。
        仅处理段落类块。识别的 label/text 写入 block.data；builder 据此输出 footnote
        内容并写 footnoteMarker/footnoteAnchorRef。

        归类完成后按 label 把每个 footnote 块**绑定**到其锚点段（正文里含 ``[foot:N]``
        的块）之后：页脚绘制以锚点落页为准，定义若留在 canonical 原始位置（远离锚点、
        甚至落进后续列表条目之间），渲染会把定义画到错误页页脚。锚点唯一才搬，且已是
        锚点后「脚注连续段」一员时不搬；无锚点或多个候选（正文多处引用该标记）保守原地保留。

        旧 GFM 写法（``[^N]`` 引用 / ``[^N]: 定义``）已废弃（GEN-118）：不再解析为脚注，
        遇旧写法按 CSM-STRUCT-008 报 issue 并提示迁移，迁移工具
        ``tools/replay_footnote_markers.py``。
        """

        def _classify_line(text: str, start_line: int, end_line: int, issue_line: int) -> list[Block]:
            """归类一行文本 → [正文段(可无), *footnote]（指令对整行 / 行内剥离）。"""
            stripped = text.strip()
            pairs = list(_FOOTNOTE_DEF_RE.finditer(stripped))
            if not pairs:
                return [Block(kind="paragraph", start_line=start_line, end_line=end_line, text=text)]
            out: list[Block] = []
            if pairs[0].start() > 0:
                body = stripped[: pairs[0].start()].rstrip()
                if body:
                    out.append(Block(kind="paragraph", start_line=start_line, end_line=end_line, text=body))
            for pair in pairs:
                label = pair.group(1)
                content = pair.group(2).strip()
                out.append(Block(
                    kind="footnote", start_line=start_line, end_line=end_line,
                    text=f"<!--ssir:foot:{label}-->{content}{_FOOTNOTE_DEF_CLOSE}",
                    data={"label": label, "text": content},
                ))
                self._issue(
                    issues, "CSM-STRUCT-005",
                    f"Footnote definition recognised (foot:{label}: {content[:24]}...).",
                    line=issue_line, repaired=True,
                    repair_action="Reclassified the footnote definition as a footnote block in memory.",
                )
            return out

        rebuilt: list[Block] = []
        for block in blocks:
            if block.kind != "paragraph":
                rebuilt.append(block)
                continue
            text_lines = block.text.split("\n")
            # 形态 3：段首定义行 + 粘连内容 → 逐个剥离定义行，内容行留作段落。
            peeled: list[Block] = []
            cursor = 0
            while cursor < len(text_lines):
                line = text_lines[cursor].strip()
                if not line:
                    cursor += 1
                    continue
                whole = _FOOTNOTE_DEF_RE.fullmatch(line)
                has_rest = any(ln.strip() for ln in text_lines[cursor + 1:])
                if whole and has_rest:
                    peeled.append(Block(
                        kind="footnote", start_line=block.start_line + cursor, end_line=block.start_line + cursor,
                        text=line,
                        data={"label": whole.group(1), "text": whole.group(2).strip()},
                    ))
                    self._issue(
                        issues, "CSM-STRUCT-005",
                        f"Footnote definition glued to following content recognised "
                        f"(foot:{whole.group(1)}: {whole.group(2)[:24]}...).",
                        line=block.start_line + cursor, repaired=True,
                        repair_action="Split the leading footnote definition line off the glued paragraph into a footnote block.",
                    )
                    cursor += 1
                    continue
                break
            if peeled:
                rebuilt.extend(peeled)
                remainder = "\n".join(text_lines[cursor:]).strip()
                if remainder:
                    rebuilt.extend(_classify_line(
                        remainder, block.start_line + cursor, block.end_line, block.start_line + cursor,
                    ))
                continue
            rebuilt.extend(_classify_line(block.text, block.start_line, block.end_line, block.start_line))
        blocks[:] = rebuilt

        # 绑定：把每个 footnote 块移到其锚点段（唯一含 “[foot:N]” 标记的非脚注块）之后。
        seen: set[tuple[str, int]] = set()
        while True:
            pick: tuple[int, tuple[str, int]] | None = None
            for index in range(len(blocks) - 1, -1, -1):
                block = blocks[index]
                label = str(block.data.get("label", ""))
                key = (label, block.start_line)
                if block.kind == "footnote" and label and key not in seen:
                    pick = (index, key)
                    break
            if pick is None:
                break
            f_index, key = pick
            seen.add(key)
            note = blocks[f_index]
            label = key[0]
            candidates = [
                i for i, block in enumerate(blocks)
                if i != f_index and block.kind != "footnote"
                and any(m.group(1) == label for m in FOOTNOTE_CITE_RE.finditer(block.text))
            ]
            if len(candidates) != 1:
                continue  # 无锚点 / 正文多处引用该标记 → 保守不动
            anchor = candidates[0]
            # 已在锚点后的“脚注连续段”内（紧跟锚点，或紧跟同为该锚点的脚注）→ 不动
            run_start = f_index
            while run_start > 0 and blocks[run_start - 1].kind == "footnote":
                run_start -= 1
            if run_start > 0 and run_start - 1 == anchor:
                continue
            blocks.pop(f_index)
            insert_at = anchor + 1 if anchor < f_index else anchor
            blocks.insert(insert_at, note)
            self._issue(
                issues, "CSM-STRUCT-005",
                f"Footnote definition [^{label}] relocated right after its anchor paragraph "
                f"(now {insert_at + 1}-th block).",
                line=note.start_line, repaired=True,
                repair_action="Moved the footnote definition block directly after the block containing its anchor marker so page-bottom attribution lands on the anchor page.",
            )

        # 定义块（解析阶段由指令对直接落块）统一报 CSM-STRUCT-005，便于人工核查。
        for block in blocks:
            if block.kind == "footnote" and str(block.text).startswith("<!--ssir:foot:"):
                label = str(block.data.get("label", ""))
                content = str(block.data.get("text", ""))
                CSMParser._issue(
                    issues, "CSM-STRUCT-005",
                    f"Footnote definition recognised (foot:{label}: {content[:24]}...).",
                    line=block.start_line, repaired=True,
                    repair_action="Reclassified the footnote definition as a footnote block in memory.",
                )

        # 旧 GFM 写法（GEN-118）：不解析为脚注，报 issue 并提示迁移。
        for block in blocks:
            texts = [block.text]
            if block.kind == "list":
                texts = [str(item.get("text", "")) for item in block.data.get("items", [])]
            elif block.kind == "table":
                texts = [str(cell) for row in block.data.get("rows", []) for cell in row]
            for text in texts:
                legacy = (
                    LEGACY_FOOTNOTE_DEF_RE.match(text.strip())
                    or LEGACY_FOOTNOTE_CITE_RE.search(text)
                )
                if not legacy:
                    continue
                label = legacy.group(1)
                self._issue(
                    issues, "CSM-STRUCT-008",
                    f"旧式 GFM 脚注标记 [{label}] 已废弃（GEN-118）：请改用引用点 [foot:{label}]"
                    f"与定义对 <!--ssir:foot:{label}-->注释文字<!--ssir:/foot-->"
                    f"（迁移工具 tools/replay_footnote_markers.py）。",
                    line=block.start_line,
                )
                break

    @staticmethod
    def _flag_retired_script_markers(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """退役标记告警（GEN-119）：`[:sup:a]` / `[:sub:2]` / `[:/sup]` / `[:/sub]`
        及其更早形态 `[:^a]`、`[^a]…[^a/]` 不再支持，按 CSM-STRUCT-009 报 issue 并
        提示改用通用行内公式上角标 `$^{a}$`（表内角注），注文仍由表后的 `a）…` 行承担。
        """
        retired = re.compile(r"\[:(?:sup|sub):[^\[\]/\s]{1,4}/?\]|\[:/(?:sup|sub)\]|\[:\^[a-z]\]|\[\^[a-z](?:/)?\]")
        for block in blocks:
            texts = [block.text]
            if block.kind == "list":
                texts = [str(item.get("text", "")) for item in block.data.get("items", [])]
            elif block.kind == "table":
                texts = [str(cell) for row in block.data.get("rows", []) for cell in row]
            for text in texts:
                found = retired.search(text)
                if not found:
                    continue
                CSMParser._issue(
                    issues, "CSM-STRUCT-009",
                    f"旧式行内角标标记 {found.group(0)} 已退役（GEN-119）：请改用通用行内公式"
                    f"上角标 $^{{a}}$（表内角注；注文由表后的 a）… 行承担）。",
                    line=block.start_line,
                )
                break


    def _repair_reference_entry_brackets(self, blocks: list[Block], issues: list[CSMIssue]) -> None:
        """参考文献条目方括号形态归一（CSM-OCR-013）。

        OCR 可能丢掉 [N] 的左或右括号（GB_T_20001.10-2014 参考文献第 8、9 条：
        “8] GB/T 27050.1 …”）。判别（保守，防误伤正文）：
        - 段以 “数字] ” 开头且其后紧跟标准代号前缀（GBT-C06 白名单）→ 补回左括号；
        - 段以 “[数字<空格>” 开头（即数字后无 “]”）且其后紧跟标准代号前缀 →
          在数字后补回右括号。
        其余形态（正文里的 “[GB/T 20000.1—2014，定义 7.9]” 等）不触碰。
        """
        open_lost = re.compile(r"^(\d+)\]\s*")
        close_lost = re.compile(r"^\[(\d+)\s+")
        for block in blocks:
            if block.kind != "paragraph":
                continue
            text = block.text
            stripped = text.lstrip()
            indent = text[: len(text) - len(stripped)]
            repaired = None
            m = open_lost.match(stripped)
            if m and _REFERENCE_STD_PREFIX_RE.match(stripped[m.end():]):
                repaired = f"[{m.group(1)}] {stripped[m.end():]}"
            else:
                m2 = close_lost.match(stripped)
                if m2 and _REFERENCE_STD_PREFIX_RE.match(stripped[m2.end():]):
                    repaired = f"[{m2.group(1)}] {stripped[m2.end():]}"
            if repaired is None:
                continue
            block.text = indent + repaired
            self._issue(
                issues, "CSM-OCR-013",
                f"Reference entry bracket restored: {stripped[:40]!r} -> {repaired[:40]!r}.",
                line=block.start_line, repaired=True,
                repair_action="Restored the [N] bracket form of the reference entry in memory.",
            )

    def _repair_ocr_guide_phrase(self, blocks: list[Block], issues: list[CSMIssue]) -> None:
        """OCR 固定引导语形近字修复（CSM-OCR-011）。

        规范性引用文件引导语（GB/T 1.1-2020 固定句式“下列文件对于本文件的
        应用是必不可少的……”）被 OCR 把“下”误读为形近字“卜”时，整句以
        “卜列文件对于本文件”开头（“卜列”不是词，正文不可能这样写）——安全
        替换回“下列”，避免该句被 GBT-C06 当缺失引导语/缺编号清单条目误报。
        """
        for block in blocks:
            if block.kind not in ("paragraph", "heading"):
                continue
            if not _REFERENCE_GUIDE_OCR_RE.match(block.text.lstrip()):
                continue
            repaired = block.text.replace("卜列", "下列", 1)
            if repaired == block.text:
                continue
            block.text = repaired
            self._issue(
                issues, "CSM-OCR-011",
                "OCR misread the fixed reference-list guide sentence "
                "(‘卜列文件…’); restored ‘下列文件…’.",
                line=block.start_line, repaired=True,
                repair_action="Restored '下列文件对于本文件' guide sentence in memory.",
            )

    @staticmethod
    def _repair_heading_levels(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """Normalise heading levels by clause-number depth (CSM-OCR-006).

        MinerU 常把章条标题全部压成同一层 ##（扁平树抽取，语料实测 90%+ 的
        标题层级错：GB_T_1.1-2020 176 个编号标题 166 个层级错）。正确层级由
        编号段数决定：章 1 段 → level 2（##）、条 2 段 → level 3（###）、
        子条 3 段 → level 4（####）…… 本修复只提升（当前层级低于编号深度），
        不降低——避免把用户手写的高层标题（如 #### 下的 ###）误压扁，也避免
        与 _repair_clause_numbers 的连续性修复冲突。标题文本本身不变，
        canonical/SSIR/render 三侧一致，roundtrip 等价性保持。

        附录条（`B.1`/`B.6.1` 型，GB/T 1.1-2020 9.6.2/10.4.1）同规：以附录大写
        字母 + 点分数字编号，段数 = 点分链段数，层级 = 段数 + 1（附录本身 1 段 →
        level 2、附录条 2 段 → level 3、附录子条 3 段 → level 4），使其落入所属
        附录之下。此前本式只认十进制编号，附录条与附录同级 → 扁平化为文档块，
        SSIR 树中附录无子节点（查看器折叠失效、`annexSection` 从未产生）。
        """
        heading_number = re.compile(r"^(\d+(?:\.\d+)*|[A-Z]\.\d+(?:\.\d+)*)\s*[\u4e00-\u9fffA-Za-z0-9（(]")
        for block in blocks:
            if block.kind != "heading" or not block.level:
                continue
            match = heading_number.match(block.text)
            if not match:
                continue
            segments = match.group(1).count(".") + 1
            expected = segments + 1  # 章=2, 条=3, 子条=4, …
            if expected > block.level:
                previous = block.level
                block.level = expected
                CSMParser._issue(
                    issues,
                    "CSM-OCR-006",
                    f"Heading {block.text!r} was flattened by the extractor (level {previous}); "
                    f"restored to level {expected} from its {segments}-segment clause number.",
                    line=block.start_line,
                    repaired=True,
                    repair_action=f"Raised heading level {previous} -> {expected} in memory.",
                )

    @staticmethod
    def _repair_example_heading_levels(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """Nest example-title headings under their containing clause (CSM-OCR-008).

        现象（GB_T_1.1-2020 第6/7章，2026-09-03）：MinerU 把框式示例标题
        「示例：」「示例N：」抽成 ##（与章同级）标题，而 _repair_heading_levels
        只按编号段数提升编号标题，无编号的示例标题留在 ## → 恰好刺穿所在章条
        的嵌套：示例块被 builder 挂到文档根，其后更深的真实条款（6.1.3、
        6.2、7.2…）反而挂到示例节点之下，资源管理器里章内条款错位、示例
        不在对应条款内。修复：把示例标题提升到「当前最近的编号条款层级 + 1」
        （只升不降、上限 6 级），使其成为该条款的子节点；编号条款随后仍按
        自己的层级正常弹栈归位。示例标题不压栈（其原层级不可信，压栈会关闭
        编号条款上下文）。附录（附录 A…）内容按既有的扁平示例文档模型保留
        （GB_T_20001 系列附录示例依赖该模型），只有编号条款上下文内的示例
        才调整。

        2026-09-12 扩展（用户报告：附录 A 与 B.6.3.5/B.6.3.6 的示例被误为与附录
        同级）：
        - 附录条编号（`B.1`/`B.6.3`）与附录标题（`附录 A`）也作为示例的**归属
          上下文**——示例挂到所属附录条/附录之下（示例直接位于附录内时挂到附录
          之下）。此前上下文只认十进制编号，附录内示例留在 ## → 挂到文档根。
        - **模型示例**（示例内容本身是一份示例文档，自带 `1`/`5` 等章节标题，
          GB_T_20001 系列）保持扁平：示例标题之后的下一个标题既不是另一个示例/
          附录/附录条/十进制条号/文档级要素时，判定该标题属于示例文档本身，不做
          提升（否则示例文档章节会与附录条争夺层级，破坏渲染端的示例框分组）。
        """
        annex_heading = re.compile(r"^附\s*录\s*[A-Z]")
        annex_section_heading = re.compile(r"^[A-Z]\.\d+(?:\.\d+)*(?:\s|$)")
        digit_heading = re.compile(r"^\d+(?:\.\d+)*\s*[\u4e00-\u9fffA-Za-z（(]")
        element_only = re.compile(r"^(?:参考文献|索\s*引|前\s*言|引\s*言|目\s*次|封面|重要提示)$")

        def owns_following_heading(index: int) -> bool:
            """示例标题之后的标题是否构成示例文档（模型示例判据）。

            扫描到下一个「示例/附录/附录条/文档级要素」边界为止：其间只要出现
            十进制条号标题（示例文档自带的 1/5/6.1 章节），即认定示例内容本身是
            一份示例文档（模型示例）。单个 OCR 误升的标题（如 GB_T_1.1-2020
            示例2 里的「##     多刃刀片 GB/T 2079-…」）不算模型。
            """
            for later in blocks[index + 1:]:
                if later.kind != "heading" or not later.level:
                    continue
                later_text = later.text.strip()
                if (
                    EX_HEADER_RE.match(later_text)
                    or annex_heading.match(later_text)
                    or annex_section_heading.match(later_text)
                    or element_only.match(later_text.replace(" ", ""))
                ):
                    return False
                if digit_heading.match(later_text):
                    return True
            return False

        # 附录作用域：附录标题到下一个附录/文后要素之间的全部内容都属于该附录，
        # 不因中间的无编号标题（如示例内容里误升的标题）而退出——用显式作用域而非
        # 层级栈，避免噪声标题把附录上下文弹掉。
        annex_level: int | None = None
        annex_section_level: int | None = None
        clause_stack: list[int] = []  # 正文十进制条号层级栈
        simple_example = False  # 当前是否处于「简单示例」块内（内容非示例文档）
        for index, block in enumerate(blocks):
            if block.kind != "heading" or not block.level:
                continue
            text = block.text.strip()
            level = block.level
            if EX_HEADER_RE.match(text):
                if annex_level is not None:
                    context_level = annex_section_level or annex_level
                    if owns_following_heading(index):
                        # 模型示例：保持扁平示例文档模型（示例文档章节仍与其同级）。
                        simple_example = False
                        continue
                else:
                    context_level = clause_stack[-1] if clause_stack else None
                    if context_level is None:
                        simple_example = False
                        continue
                target = min(context_level + 1, 6)
                if level < target:
                    previous = level
                    block.level = target
                    CSMParser._issue(
                        issues,
                        "CSM-OCR-008",
                        f"Example heading {text!r} sat at level {previous} (extractor "
                        f"chapter level) inside clause context level {context_level}; raised to "
                        f"level {target} so it nests under its clause.",
                        line=block.start_line,
                        repaired=True,
                        repair_action=f"Raised example heading level {previous} -> {target} in memory.",
                    )
                simple_example = True
                continue
            # 简单示例内容里的无编号标题（MinerU 把示例的「标记：」行等抽成 ## 标题，
            # GB/T 1.1-2020 示例2 的「多刃刀片 GB/T 2079-…」）是示例内容，不是章条
            # 标题——降级为段落，避免它成为与章同级的结构节点并夺走后续解释段。
            is_boundary = bool(
                element_only.match(text.replace(" ", ""))
                or annex_heading.match(text)
                or annex_section_heading.match(text)
                or digit_heading.match(text)
            )
            if simple_example and not is_boundary:
                block.kind = "paragraph"
                block.level = None
                CSMParser._issue(
                    issues,
                    "CSM-OCR-020",
                    f"Heading {text!r} inside an example block is example content, "
                    f"not a clause title; demoted to a paragraph.",
                    line=block.start_line,
                    repaired=True,
                    repair_action="Demoted an example-content heading to a body paragraph in memory.",
                )
                continue
            simple_example = False
            if element_only.match(text.replace(" ", "")):
                annex_level = None
                annex_section_level = None
                clause_stack = []
                continue
            if annex_heading.match(text):
                annex_level = level
                annex_section_level = None
                clause_stack = []
                continue
            if annex_section_heading.match(text):
                annex_section_level = level
                continue
            if annex_level is not None:
                # 附录作用域内：无编号/噪声标题不影响附录条上下文。
                continue
            while clause_stack and clause_stack[-1] >= level:
                clause_stack.pop()
            if digit_heading.match(text):
                clause_stack.append(level)

    @staticmethod
    def _repair_lost_list_markers(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """Re-add dash list markers OCR dropped from whole lines (CSM-OCR-005).

        MinerU 常把破折号列项（——第3部分：分类标准；）整行丢失标记，只留下
        文本本身；该行会解析成独立段落，夹在两个破折号列表之间（前言部分
        清单是典型场景）。判定条件收窄以避免误伤真实段落：
        - 单行、长度 ≤ 40、以 ；或 。结尾；
        - 前后相邻块都是纯破折号标记列表；
        - 不以条号、注/示例/警示/表/图/附录开头。
        命中后转成单条目列表，标记取后一个列表（回退前一个）的破折号。
        """
        dash_marker = re.compile(r"^[-—–]+$")

        def is_dash_list(block: Block | None) -> bool:
            if block is None or block.kind != "list":
                return False
            items: list[dict[str, str]] = block.data.get("items", [])
            return bool(items) and all(dash_marker.match(str(item.get("marker", ""))) for item in items)

        for index, block in enumerate(blocks):
            if block.kind != "paragraph":
                continue
            text = block.text.strip()
            if not text or "\n" in text or len(text) > 40:
                continue
            if not re.search(r"[；。]$", text):
                continue
            if re.match(r"^\d+(?:\.\d+)*\s", text):
                continue  # 条号开头的裸条，不是列表项
            if re.match(r"^(注|示例|警示|表|图|附)", text):
                continue
            previous = blocks[index - 1] if index > 0 else None
            following = blocks[index + 1] if index + 1 < len(blocks) else None
            if not (is_dash_list(previous) and is_dash_list(following)):
                continue
            assert previous is not None and following is not None
            following_items: list[dict[str, Any]] = following.data.get("items", [])
            previous_items: list[dict[str, Any]] = previous.data.get("items", [])
            marker = str(following_items[0].get("marker") or "") or str(previous_items[0].get("marker") or "")
            if not marker:
                continue
            block.kind = "list"
            block.text = ""
            block.data = {"items": [{"marker": marker, "text": text, "line": str(block.start_line)}]}
            CSMParser._issue(
                issues,
                "CSM-OCR-005",
                f"Dash list marker lost by OCR; re-added {marker!r} to {text!r}.",
                line=block.start_line,
                repaired=True,
                repair_action="Converted the orphan paragraph into a dash list item using the neighbouring list marker.",
            )

    @staticmethod
    def _marker_family(marker: str) -> str | None:
        """列表 marker 族：dash 破折号 / dot 间隔号 / letter 字母编号 / number 数字编号。"""
        marker = str(marker or "").strip()
        if re.fullmatch(r"[-—–]{1,3}", marker):
            return "dash"
        if marker in ("·", "•", "・"):
            return "dot"
        if re.fullmatch(r"[A-Za-z][)）]", marker):
            return "letter"
        if re.fullmatch(r"\d+[)）]", marker):
            return "number"
        return None

    @classmethod
    def _repair_colon_led_lists(cls, blocks: list[Block], issues: list[CSMIssue]) -> None:
        """冒号引导完整列项组的缺失 marker 补齐（CSM-OCR-016）。

        现象（GB_T_20001.10-2014 6.7.1.1/6.4.3/6.4.4/A.1、GB_T_5171.1-2014 前言
        40 条清单等）：引导句以「：」收尾、条目逐段排布、条目以「；」收尾且仅末条
        以「。」收尾的列项组，OCR 常丢若干条目的 marker（破折号/间隔号/a）/1) 均
        可），只个别条目幸存——幸存条目成孤立列表、丢 marker 条目沦为普通段落
        （如 6.7.1.1 末条「形成标准的单独部分。」）。完整性机制（非个例判定）：
        - 整组按「：引导 + 『；』条目序列 + 『。』末条」判型；组内 ≥1 幸存 marker
          决定 marker 族，缺 marker 条目补同族 marker（破折号/间隔号沿用幸存
          marker 原样，字母/数字按组序重排 a）/1) 序号）；
        - 组尾判定不只看「。」：标记列表块末条即使以「。」收尾，只要紧随其后的仍是
          「强条目」（以「；」收尾的标记列表块或无标记段落），说明该「。」是源文组
          中偶发（GB_T_5171.1-2014 前言第 7 条「增加了第9章“结构要求”。」即 PDF
          文本层真值），组继续；直到末条「。」之后不再有强条目才收尾。如此整组
          （中间丢 marker 的普通段落一并）一次重建，不会被中间「。」截成碎组；
        - 条目末「；」被 OCR 读成「：」（GB_T_5171.1-2014 前言 2 处，PDF 文本层为
          「;」）时，仅当其后仍是强条目才按条目吸收，并把该终止符归一为「；」
          （列项各项以分号分列、末条以句号结束，GBT-H06/GB/T 1.1 7.5）；其后非强
          条目则视为新引语，截断不猜；
        - 6.4.4 型首条与引导句粘连（「…包括下述内容：分类原则与方法；」）按最后
          一个「：」拆出首条；
        - 保守不猜：组内无幸存 marker、幸存 marker 族不一致、条目数 <2、末条非
          「。」收尾、中途出现非条目块/编号条文/注示例表图 起始。
        命中后整组收敛为一个 list 块（条目保序），记 CSM-OCR-016。
        """
        clause_prefix = re.compile(r"^(?:\d+(?:\.\d+)+|[A-Z]\.\d+(?:\.\d+)*)\s*\S|^[A-Z](?:\.\d+)?\s")
        lead_prefix = re.compile(r"^(注|警示|示例|表|图|附录|附\s*录|参考文献|目\s*次)")
        colon_intro = re.compile(r"[:：]\s*$")

        def unmarked_item(block: Block) -> str | None:
            """普通段落形条目（无 marker）的文本；非条目形态返回 None。"""
            if block.kind != "paragraph":
                return None
            text = block.text.strip()
            if not text or "\n" in text:
                return None
            if not text.endswith(("；", "。")):
                return None
            if clause_prefix.match(text) or lead_prefix.match(text) or colon_intro.match(text):
                return None
            return text

        def strong_item(block: Block | None) -> bool:
            """「强条目」：以「；」收尾的标记列表块，或以「；」收尾的无标记段落。

            两种形态都不可能是组尾——列项末条必须以「。」结束（GBT-H06）——故其后
            必属同组。组尾判定只依赖这一无歧义证据，不猜「。」/「：」的歧义。
            """
            if block is None:
                return False
            if block.kind == "list":
                items = block.data.get("items") or []
                return bool(items) and all(str(item.get("text") or "").strip().endswith("；") for item in items)
            return (unmarked_item(block) or "").endswith("；")

        index = 0
        while index < len(blocks) - 1:
            intro = blocks[index]
            if intro.kind != "paragraph":
                index += 1
                continue
            intro_text = intro.text.strip()
            colon_at = intro_text.rfind("：")
            glued: str | None = None
            if colon_at >= 0 and colon_at < len(intro_text) - 1:
                # 粘连形态：引导句「：」后直接跟了首条（6.4.4「…内容：分类原则与方法；」）。
                tail = intro_text[colon_at + 1:].strip()
                if (
                    tail.endswith("；")
                    and "。" not in tail
                    and len(tail) <= 60
                    and not clause_prefix.match(tail)
                    and not lead_prefix.match(tail)
                ):
                    glued = tail
            if glued is None and not (colon_at >= 0 and colon_at == len(intro_text) - 1):
                index += 1
                continue

            entries: list[tuple[str | None, str, int, Block | None, bool]] = []  # (marker, text, line, src, 无标记推断)
            consumed_blocks: list[Block] = []
            normalized_terminators = 0
            if glued is not None:
                entries.append((None, glued, intro.start_line or 0, None, True))
            scan = index + 1
            while scan < len(blocks):
                block = blocks[scan]
                if block.kind == "list":
                    items = block.data.get("items") or []
                    if not items:
                        break
                    more: list[tuple[str | None, str, int, Block | None, bool]] = []
                    ok = True
                    for item in items:
                        itext = str(item.get("text") or "").strip()
                        if not itext.endswith(("；", "。")):
                            ok = False
                            break
                        more.append((str(item.get("marker") or ""), itext, int(item.get("line") or 0), None, False))
                    if not ok:
                        break
                    entries.extend(more)
                    consumed_blocks.append(block)
                    scan += 1
                    # 标记列表块末条「。」收尾：其后仍是强条目即说明该「。」是源文组中
                    # 偶发（GB_T_5171.1-2014 前言第 7 条），组继续；否则组在此收尾。
                    following = blocks[scan] if scan < len(blocks) else None
                    if more[-1][1].endswith("。") and not strong_item(following):
                        break
                    continue
                item_text = unmarked_item(block)
                if item_text is None:
                    # 条目末「；」被 OCR 读成「：」：仅当其后仍续有强条目才按条目吸收
                    # （否则视为新引语，截断不猜）；吸收时按列项结构归一终止符为「；」。
                    tail_text = block.text.strip()
                    following = blocks[scan + 1] if scan + 1 < len(blocks) else None
                    if (
                        block.kind == "paragraph"
                        and tail_text.endswith("：")
                        and "\n" not in tail_text
                        and not clause_prefix.match(tail_text)
                        and not lead_prefix.match(tail_text)
                        and strong_item(following)
                    ):
                        entries.append((None, tail_text[:-1] + "；", block.start_line or 0, block, True))
                        consumed_blocks.append(block)
                        normalized_terminators += 1
                        scan += 1
                        continue
                    break
                entries.append((None, item_text, block.start_line or 0, block, True))
                consumed_blocks.append(block)
                scan += 1
                # 完整性：末条以「。」收尾即列表完整；其后不再吸收（防把后续散文并入）。
                if item_text.endswith("。"):
                    break
            if len(entries) < 2 or not consumed_blocks:
                index += 1
                continue
            # 末条必须「。」收尾；组内无标记（推断）条目必须「；」收尾——完整性判定。
            # 标记列表块内条目的终止符由源文决定（组中偶发「。」不违规）。
            if not entries[-1][1].endswith("。"):
                index += 1
                continue
            if any(inferred and not text.endswith("；") for _, text, _, _, inferred in entries[:-1]):
                index += 1
                continue
            # 幸存 marker 族须 ≥1 且一致（首个幸存 marker 定族）。
            marked = [marker for marker, _, _, _, _ in entries if marker]
            if not marked:
                index += 1
                continue
            family = CSMParser._marker_family(marked[0])
            if family is None or any(CSMParser._marker_family(m) != family for m in marked):
                index += 1
                continue
            missing = [entry for entry in entries if not entry[0]]
            if not missing and not normalized_terminators:
                index += 1
                continue
            # 补 marker：破折号/间隔号沿用幸存 marker 族的多数派符号；字母/数字按组序重排
            # （缺号自然补齐）。整组已判型为同一列表（引语 + 条目序列），符号按 GBT-B04/
            # GB/T 1.1 7.5.3 取多数派形态，消除 OCR 长度变体（-/—/——）造成的组内不一致。
            if family in ("dash", "dot"):
                surviving: dict[str, int] = {}
                for marker in marked:
                    surviving[marker] = surviving.get(marker, 0) + 1
                restored = max(surviving, key=lambda marker: (surviving[marker], -marked.index(marker)))
                rebuilt = [(marker or restored, text, line) for marker, text, line, _, _ in entries]
            else:
                paren = "）" if marked[0].endswith("）") else ")"
                start = marked[0][0]
                def seq(i: int) -> str:
                    base = start.lower() if family == "letter" else "0"
                    if family == "letter":
                        letter = chr(ord(base) + i)
                        return letter.upper() if start.isupper() else letter
                    return str(i + 1)
                rebuilt = [(seq(i) + paren, text, line) for i, (_, text, line, _, _) in enumerate(entries)]
            # 整组收敛为单个 list 块：引导句去粘连，组内首个源块改为 list，删除其余。
            if glued is not None:
                intro.text = intro_text[:colon_at + 1]
            first_src = consumed_blocks[0]
            first_src.kind = "list"
            first_src.text = ""
            first_src.data = {"items": [{"marker": m, "text": t, "line": ln} for m, t, ln in rebuilt]}
            for extra in consumed_blocks[1:]:
                if extra in blocks:
                    blocks.remove(extra)
            CSMParser._issue(
                issues,
                "CSM-OCR-016",
                f"Colon-led list rebuilt with a complete item sequence: restored {len(missing)} "
                f"missing {family} marker(s)"
                + (f" and normalised {normalized_terminators} item terminator(s) to '；'" if normalized_terminators else "")
                + f" after {intro_text[:20]!r}.",
                line=first_src.start_line,
                repaired=True,
                repair_action="Rebuilt the colon-led item run as one list with family markers on every item.",
            )
            # 组内符号归一（CSM-OCR-001 同款判据：多数派 ≥2 且严格多于其余）：重建后整组为
            # 单一 list，OCR 长度变体（-、—、——）在此按多数派统一；平手不猜，不动。
            cls._repair_list_markers(blocks, issues)
            index += 2  # intro + 重建后的 list 块

    @staticmethod
    def _formula_number_label(raw: str) -> str | None:
        """「式（1）」/「(1)」/「1」→ 纯编号标签「1」（编号行归一，CSM-OCR-017）。"""
        text = str(raw).strip()
        match = _FORMULA_NUMBER_LINE_RE.match(text)
        if match:
            text = match.group(1)
        text = text.strip().strip("（）()").strip()
        return text or None

    @staticmethod
    def _formula_tag_label(tag_content: str) -> str | None:
        """从 \\tag 内容（引导线 + 编号）里取出编号：\tag{……………………(1} → 「1」。

        引导线由「…/⋯」组成，编号是行尾括号内的阿拉伯数字或附录式（A.1），
        OCR 常把右括号一起吞掉，故右括号可选。
        """
        cleaned = re.sub(r"[…⋯\u2024\u22ef\s]+", " ", str(tag_content)).strip()
        match = _FORMULA_TAG_LABEL_RE.search(cleaned)
        if match:
            return match.group(1)
        match = _FORMULA_NUMBER_LABEL_RE.search(cleaned)
        return match.group(1) if match else None

    @classmethod
    def _repair_formula_numbers(cls, blocks: list[Block], issues: list[CSMIssue]) -> None:
        """公式编号提取与全文档编号管理（CSM-OCR-017；GBT-X06）。

        MinerU 把整条公式行（公式 + 「…………」引导线 + 编号）识别成一个 equation
        块，引导线与编号被写进 LaTeX 的 ``\\tag{...}``（且常缺右花括号：
        ``\\tag{……………………(1}``），编号因此从未进入 SSIR，渲染端也无从按
        GB/T 1.1-2020 10.4.3「公式编号右端对齐，公式与编号之间由“……”连接」编排。

        本修复只做抽取层的事：把编号从 ``\\tag`` 里读出来、清掉该残留，让编号回到
        CSM 语法的独立行（``$$`` 块之后一行「式(N)」，docs/07），并把它归一为纯
        编号标签（「式（1）」→「1」；渲染端补圆括号）。

        编号本身**不猜测、不重排、不填补**：全文档编号序列（正文自引言起
        1..n 连续，附录内重新从 1 开始并加附录字母前缀，GB/T 1.1-2020 9.6.3/9.9.2）
        只用于一致性检查——抽取到的编号与序列位置不符时如实报出，缺编号的公式
        保持无编号（9.9.2 只在需要引用或提示时才要求编号）。
        """
        annex: str | None = None
        body_expected = 0
        annex_expected = 0
        for block in blocks:
            if block.kind == "heading":
                # 附录标题（「附录 A（资料性）…」）切换编号作用域：附录内公式重新编号。
                match = ANNEX_HEADING_RE.match(block.text.strip())
                if match:
                    annex = match.group(1)
                    annex_expected = 0
                continue
            if block.kind != "formula":
                continue
            tag = FORMULA_TAG_RE.search(block.text)
            if tag:
                label = cls._formula_tag_label(tag.group(1))
                block.text = (block.text[: tag.start()] + block.text[tag.end():]).rstrip()
                if label and not str(block.data.get("number") or "").strip():
                    block.data["number"] = label
                cls._issue(
                    issues,
                    "CSM-OCR-017",
                    f"公式行残留 MinerU 编号引导线 {tag.group(0)[:40]!r}；编号提取为 {label or '（无法识别）'}。",
                    line=block.start_line,
                    repaired=True,
                    repair_action="Extracted the formula number from the LaTeX \\tag residue and removed the leader-line noise from the formula text.",
                )
            raw_number = str(block.data.get("number") or "").strip()
            if not raw_number:
                continue
            label = cls._formula_number_label(raw_number)
            if label and label != raw_number:
                block.data["number"] = label
                if not _FORMULA_NUMBER_LINE_RE.match(raw_number):
                    # 只有非「式(N)」形态（OCR 噪声）才记修复；标准 CSM 编号行与
                    # 表题「**表N 题名**」同规——解析出编号标签属解析动作，不记 issue。
                    cls._issue(
                        issues,
                        "CSM-OCR-017",
                        f"公式编号行 {raw_number!r} 归一为编号 {label!r}。",
                        line=block.start_line,
                        repaired=True,
                        repair_action="Normalised the formula number line to the bare number label.",
                    )
            if not label:
                block.data.pop("number", None)
                cls._issue(
                    issues,
                    "CSM-OCR-017",
                    f"公式编号行 {raw_number!r} 无法识别为编号（未修正）。",
                    line=block.start_line,
                )
                continue
            # 全文档编号管理：期望编号 = 正文 1..n / 附录 <字母>.1..n。
            if annex:
                annex_expected += 1
                expected = f"{annex}.{annex_expected}"
            else:
                body_expected += 1
                expected = str(body_expected)
            if label != expected:
                cls._issue(
                    issues,
                    "CSM-OCR-017",
                    f"公式编号与文档内连续编号不一致：抽取为 ({label})，按 GBT-X06 应为 ({expected})"
                    f"（GB/T 1.1-2020 9.9.2/9.6.3；抽取值保留不改写）。",
                    line=block.start_line,
                )

    @classmethod
    def _repair_formula_variable_lines(cls, blocks: list[Block], issues: list[CSMIssue]) -> None:
        """公式变量解释组的模式化归一（CSM-OCR-018；GBT-X06）。

        GB/T 1.1-2020 9.9.3/10.4.3：变量由字母符号代表，公式后用「式中：」引出
        解释（「式中：」空两个汉字起排）。解释项固定形态 = **变量 + 破折号 +
        解释文字 + 分号（末项句号）**，变量与破折号之间、破折号与解释之间各空
        四分之一汉字（字隙由渲染层实现）。

        OCR 把这一组读坏的方式与列项同型（CSM-OCR-016/001）：破折号被压成单个
        「—」或整段丢失（GB_T_5171.1-2014 式(1) 六项里三项丢、两项压短），末标点
        被读成「：」或整段漏掉（式(2) 两项缺终止符）。

        判型（保守，全部满足才动）：以独占一行的「式中：」为锚；其后连续若干
        段落块逐项匹配「短变量头 + 可选破折号/冒号/空白 + 汉字解释」；组内至少
        两项。修复只碰**破折号族与终止符**，不重排、不改解释文字：破折号族
        （-、—、——、———、－…）统一为「——」，缺失的破折号补回，缺终止符的
        补「；」（末项补「。」），以「：」等非句末标点收尾的改为应有的终止符；
        **已有的「。」不强制改「；」**（组内句号可能是示例边界，如 GB/T 1.1-2020
        9.9.3.2 的"正确/不正确"对照示例）。
        """
        index = 0
        while index < len(blocks):
            intro = blocks[index]
            if intro.kind != "paragraph" or not FORMULA_VAR_INTRO_RE.match(intro.text.strip()):
                index += 1
                continue
            group: list[Block] = []
            cursor = index + 1
            while cursor < len(blocks):
                candidate = blocks[cursor]
                if candidate.kind != "paragraph":
                    break
                if not FORMULA_VAR_ITEM_RE.match(candidate.text.strip()):
                    break
                group.append(candidate)
                cursor += 1
            if len(group) >= 2:
                cls._normalise_formula_variable_group(group, issues)
            index = cursor if group else index + 1

    @classmethod
    def _normalise_formula_variable_group(cls, group: list[Block], issues: list[CSMIssue]) -> None:
        """把一组变量解释项归一为「变量——解释；/。」（CSM-OCR-018）。"""
        for position, block in enumerate(group):
            original = block.text
            match = FORMULA_VAR_ITEM_RE.match(block.text.strip())
            if not match:
                continue
            head = match.group("head").strip()
            explanation = match.group("text").strip()
            is_last = position == len(group) - 1
            terminator = "。" if is_last else "；"
            # 终止符：缺则补，非句末标点（：、,、等）改为应有终止符；
            # 已有「；/。」保持（组内句号可能是示例边界，不强制改写）。
            if explanation.endswith("；") or explanation.endswith("。"):
                body = explanation
            else:
                body = re.sub(r"[:：，,、;；.．。]+$", "", explanation).rstrip()
                body = f"{body}{terminator}"
            normalised = f"{head}——{body}"
            if normalised == original.strip():
                continue
            block.text = normalised
            cls._issue(
                issues,
                "CSM-OCR-018",
                f"公式变量解释项归一为固定形态（原 {original[:24]!r} → {normalised[:24]!r}）。",
                line=block.start_line,
                repaired=True,
                repair_action="Normalised the variable-explanation item to the fixed 'symbol —— explanation；' pattern.",
            )

    @classmethod
    @staticmethod
    def _repair_text_spacing(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """Restore spacing OCR drops inside standard-document text (CSM-OCR-003/004).

        - CSM-OCR-003 术语间隔：术语条目「中文English」（或 OCR 留下半角空格的
          「中文 English」）中英文之间应空一个汉字（GB/T 1.1-2020 10.3.5）。用
          U+3000 表示：渲染端 `_markup` 把「汉字 + U+3000 + 拉丁」换成恰好 1em 的
          不可见字隙（白色汉字填充），不会渲染成 .notdef 方框；历史实现曾用 U+200B
          （零宽空格）制造 1em 推进宽度，但 Noto Serif CJK SC 无 U+200B 字形，
          2026-08-29 起改用 U+3000（见 GB_T_20001.5 渲染回归）。
          只在「术语和定义」要素内、且行为术语行（汉字串 + 英文对应词）时修复——
          裸术语行与带条目编号的术语条目标题行（「3.1.2 标准 standard」）同规，
          行内出现中文标点即不认（定义/正文不是术语行），避免误伤正文。
        - CSM-OCR-004 标准号间隔：正文中的标准号「文件代号 + 顺序号」之间应有一个
          空格（GB/T20001 → GB/T 20001）。只匹配**已知文件代号**（带斜杠的
          GB/T、JB/T、DB11/T、GB/Z…、团体/企业 T/ZZB、Q/XKBZ、无斜杠的
          GB、GJB、ISO、IEC…），带斜杠前导被排除（SAC/TC286 不动），单字母
          前缀排除（维生素B1 不动）。旧实现的第二分支是 `[A-Z]{2,4}(?=[0-9])`
          —— 什么都吞，落到列项/单元格载体上会把 RS485、AC1 500 V 这类**非标准号**
          也拆开，故收窄为白名单（2026-09-11）。
          载体覆盖 块文本（段落/标题）、列项条目文本、表格单元格文本。
        """
        chapter_re = re.compile(r"^\d+\s+\S")
        annex_re = re.compile(r"^附\s*录")

        in_terms = False
        for block in blocks:
            if block.kind == "heading":
                text = block.text.strip()
                if annex_re.match(text) or (chapter_re.match(text) and "术语" not in text):
                    in_terms = False
                elif chapter_re.match(text) and "术语" in text:
                    in_terms = True
            # 载体：块文本（段落/标题）、列项条目文本、表格单元格文本。标准号间隔
            # 对三者一律适用——旧实现只修 block.text，列项分支写在不可达位置
            # （`if block.kind not in ("paragraph","heading"): continue` 之后），
            # 因此前言「GB/T1.2—2002」这类**列项里的**标准号从未被修复。
            before = block.text
            changed: list[tuple[str, str]] = []
            fixed = restore_standard_number_spacing(block.text)
            if fixed != block.text:
                changed.append((block.text, fixed))
                block.text = fixed
            for item in block.data.get("items", []):
                item_text = str(item.get("text", ""))
                item_fixed = restore_standard_number_spacing(item_text)
                if item_fixed != item_text:
                    changed.append((item_text, item_fixed))
                    item["text"] = item_fixed
            for row in block.data.get("rows", []):
                for cell_index, cell in enumerate(row):
                    cell_fixed = restore_standard_number_spacing(str(cell))
                    if cell_fixed != cell:
                        changed.append((str(cell), cell_fixed))
                        row[cell_index] = cell_fixed
            # 术语间隔（仅术语和定义要素内；行首为术语行或术语条目标题行）
            term_gap_applied = False
            if in_terms and block.kind in ("paragraph", "heading"):
                for line in block.text.splitlines():
                    fixed_line = restore_term_entry_gap(line)
                    if fixed_line != line:
                        block.text = block.text.replace(line, fixed_line, 1)
                        term_gap_applied = True
                        break
            if not changed and not term_gap_applied:
                continue
            if changed:
                original, repaired = changed[0]
            else:  # 术语行只补了中英文间隙
                original, repaired = before, block.text
            CSMParser._issue(
                issues,
                "CSM-OCR-003" if term_gap_applied else "CSM-OCR-004",
                f"Restored spacing in {original[:40]!r} -> {repaired[:40]!r}.",
                line=block.start_line,
                repaired=True,
                repair_action="Inserted the missing inter-word / standard-number space in memory.",
            )

    @staticmethod
    def _demote_sentence_headed_clauses(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """Demote sentence-bodied numbered headings back to body clauses (CSM-OCR-009).

        现象（GB_T_1.1-2020 附录 B.2.2/9.9.3.1、GB_T_23132-2008 8.1.2，2026-09-04）：
        MinerU 把「编号 + 整句条文内容、以句号收尾」的无标题条文误升成标题——例如
        「## B.2.2 这里描述的标记体系适用于下列各类文件。」，而真正的条标题从不以
        。！？ 收尾（同层兄弟 B.2.1/B.2.3 均为裸正文段）。误升的标题会把条文变成
        SSIR 结构节点/目次条目（附录二级跳号 #1 型）并脱离正文流。判据：
        编号（章条或附录条）开头 + 句末标点收尾 → 降级为正文段落。H1 除外
        （文档标题句末不带标点；H1 数量由 CSM-STRUCT-003 单独把关）。
        """
        numbered = re.compile(r"^(?:\d+(?:\.\d+)*|[A-Z]\.\d+(?:\.\d+)*)\s*\S")
        for block in blocks:
            if block.kind != "heading" or not block.level or block.level <= 1:
                continue
            text = block.text.strip()
            if not text.endswith(("。", "！", "？")):
                continue
            if not numbered.match(text):
                continue
            block.kind = "paragraph"
            block.level = None
            CSMParser._issue(
                issues,
                "CSM-OCR-009",
                f"Heading {text!r} is a sentence-bodied numbered clause, not a title "
                f"(ends with sentence-final punctuation); demoted to a paragraph.",
                line=block.start_line,
                repaired=True,
                repair_action="Demoted the mis-extracted title to a body paragraph in memory.",
            )

    @staticmethod
    def _demote_index_letter_headings(blocks: list[Block], issues: list[CSMIssue]) -> None:
        """索引要素内的单字母分组标签标题降级为正文段落（CSM-OCR-019）。

        现象（GB_T_1.1-2020 索引，2026-09-12 用户报告）：索引按汉语拼音首字母分组，
        组标签行「B」「D」「Z」被 MinerU 抽成 `##` 标题，而同一索引里的其他字母
        （C/F/W/X/Y）是普通段落 → 这三个字母在 SSIR 树里成为与附录同级的文档块，
        而索引其余内容挂在「索引」节点下（用户：「索引的 B、D、Z」）。
        判据：进入「索引」要素（无编号、文本为「索引」）后，形如单个大写字母的
        标题块一律降级为段落；遇下一个文档级要素（参考文献/前言/引言/目次/封面）
        或编号章条标题即退出索引模式。
        """
        letter_only = re.compile(r"^[A-Z]$")
        element_only = re.compile(r"^(?:参考文献|索\s*引|前\s*言|引\s*言|目\s*次|封面)$")
        in_index = False
        for block in blocks:
            if block.kind != "heading" or not block.level:
                continue
            text = block.text.strip()
            normalized = text.replace(" ", "")
            if letter_only.match(text) and in_index:
                block.kind = "paragraph"
                block.level = None
                CSMParser._issue(
                    issues,
                    "CSM-OCR-019",
                    f"Index group heading {text!r} demoted to a paragraph "
                    f"(index content, not a clause title).",
                    line=block.start_line,
                    repaired=True,
                    repair_action="Demoted the index letter heading to a body paragraph in memory.",
                )
                continue
            if element_only.match(normalized):
                in_index = "索引" in normalized
            elif re.match(r"^\d+", text):
                in_index = False

    @staticmethod
    def _classify_body_errors(errors: list[str], issues: list[CSMIssue]) -> list[str]:
        fatal_errors: list[str] = []
        for error in errors:
            if "unterminated formula block" in error or "unterminated code fence" in error:
                fatal_errors.append(error)
            elif "duplicate ssir id" in error:
                # Explicit IDs participate in reference resolution; changing them can mis-bind a merge or asset.
                fatal_errors.append(error)
            elif "ssir:box" in error:
                # ssir:box 配对/嵌套错误（2026-09-08 显式文档框声明）：不阻断解析，
                # 宽容模式按确定性规则继续（未闭合开 → 延伸到文档尾；关无开/嵌套 → 忽略）。
                CSMParser._issue(issues, "CSM-STRUCT-006", error)
            elif "ssir:column" in error:
                # ssir:columns 配对/嵌套/列错位错误（2026-09-11 显式并列声明，
                # docs/07 §6.9）：与 box 同族的宽容语义，独立 issue 码便于追溯。
                CSMParser._issue(issues, "CSM-STRUCT-008", error)
            elif "table row has" in error:
                # Short rows were repaired above. Extra cells have already been recorded as fatal there.
                continue
            elif "requires id" in error:
                CSMParser._issue(issues, "CSM-DIRECTIVE-001", error + "; generated IDs will be used.", repaired=True, repair_action="Used a deterministic generated SSIR object ID.")
            elif "table-merge" in error:
                CSMParser._issue(issues, "CSM-DIRECTIVE-002", error + "; the merge directive was ignored.", repaired=True, repair_action="Ignored an unresolvable table-merge directive.")
            else:
                CSMParser._issue(issues, "CSM-STRUCT-002", error)
        return fatal_errors

    @staticmethod
    def _classify_document_errors(errors: list[str], issues: list[CSMIssue]) -> list[str]:
        for error in errors:
            if error.startswith("CSM must contain exactly one H1"):
                CSMParser._issue(issues, "CSM-STRUCT-003", error + "; SSIR metadata title was retained.")
            elif error == "H1 title must exactly match front matter title":
                CSMParser._issue(issues, "CSM-STRUCT-004", error + "; neither value was changed.")
            elif error.startswith("main chapter numbering"):
                CSMParser._issue(issues, "GB-T-1.1-CHAPTER-001", error + "; original numbering was preserved.")
            elif "duplicate ssir id" in error:
                return [error]
            else:
                CSMParser._issue(issues, "CSM-STRUCT-005", error)
        return []

    @staticmethod
    def _assess_standard_profile(metadata: dict[str, Any], blocks: list[Block], issues: list[CSMIssue]) -> None:
        """Report only baseline mandatory concerns; optional GB/T components stay optional.

        规则对应: GBT-C03（前言必备）、GBT-C05（范围应为第 1 章）、P10-E03（产品标准技术要求必备）、
        GEN-012（文件编号年份与一字线）。
        """
        if metadata.get("document-type") != "standard":
            return
        # OCR/MinerU 常在标题字间插入空格（"前 言"），比对前去除空白。
        headings = [re.sub(r"\s+", "", block.text.strip()) for block in blocks if block.kind == "heading" and block.level == 2]
        if "前言" not in headings:
            CSMParser._issue(issues, "GB-T-1.1-FOREWORD-001", "Standard document has no 前言 section; GB/T 1.1 treats the foreword as a required document element.")
        if not any(re.match(r"^1\s*范围", title) for title in headings):
            CSMParser._issue(issues, "GB-T-1.1-SCOPE-001", "No identifiable chapter 1 范围 was found; confirm the document scope manually.")
        profile = metadata.get("extensions", {}).get("standard-profile")
        if profile == "product" and not any("技术要求" in title for title in headings):
            CSMParser._issue(issues, "GB20001-10-TECHNICAL-001", "Product-standard profile has no identifiable 技术要求 section; GB/T 20001.10 treats technical requirements as essential.")
        number = metadata.get("standard-number")
        if isinstance(number, str) and number and not re.search(r"\d{4}$", number):
            CSMParser._issue(issues, "GB-T-1.1-ID-001", "Standard number has no trailing four-digit year; original number was preserved.")
        if isinstance(number, str) and "-" in number:
            CSMParser._issue(issues, "GB-T-1.1-ID-002", "Standard number uses an ASCII hyphen; original number was preserved for source fidelity.")

    @staticmethod
    def _append_declared_quality_notices(metadata: dict[str, Any], issues: list[CSMIssue]) -> None:
        notices = metadata.get("extensions", {}).get("quality-notices", [])
        if not isinstance(notices, list):
            return
        for notice in notices:
            if isinstance(notice, dict):
                issues.append(
                    CSMIssue(
                        str(notice.get("code", "CSM-DECLARED-NOTICE")),
                        str(notice.get("severity", "warning")),
                        str(notice.get("message", "")),
                    )
                )
