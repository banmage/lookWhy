"""规范性引用抽取：外部标准引用 + 本文内部引用点（parse 层）。

规则依据
--------
- GB/T 1.1-2020 **8.6**（规范性引用文件：固定引导语、清单条目的写法与排列）、
  **9.5.4**（引用的表示：注日期/不注日期/所有部分；规范性引用与资料性引用的区分）、
  **9.9.2**（公式编号的引用表示）；
- 设计说明《技术文件智能审查系统（TDRS）设计说明文档 v2.0》「标准中规范性引用文件
  的管理」§二（六元组：标准号/版本/名称/引用类型/引用条款/出现条款 + 引用性质/来源
  位置）、§三（SSIR 顶层 ``references`` 数据模型）、§四（抽取流程：**第 2 章清单为主
  来源，全文扫描为补充**，按标准标识合并）。

判据来源（不另造）
------------------
- 标准号识别：``compliance._STANDARD_NUMBER_RE``（GBT-C06 同一前缀表，含 GB/JB/QB/SJ/
  DB/Q/T/ISO/IEC 等 30+ 代号）；
- 标准标识转义：``naming.escape_standard_number``（``GB/T 1.1—2020`` → ``GB_T_1.1-2020``）；
- 表/图/公式目标标识：``naming.table_element_id`` / ``figure_element_id`` /
  ``formula_element_id``。

产出形态
--------
``extract()`` 返回 **occurrence 级**的引用数组，逐项满足 ``ssir.schema.json`` 的
``Reference`` 定义（不新增字段；``resolved*`` 承载 TDRS 六元组的版本/被引条款等，
``rawTarget`` 原样保留引用原文，故「注日期 / 不注日期 / 所有部分」这一轴可由 rawTarget +
resolvedVersion 无损还原，见 ``references.reference_type_of``）。

规范性/资料性判定（GB/T 1.1-2020 9.5.4.2）按下列**通用**判据逐条判定，不针对任何
具体文档：

1. 第 2 章「规范性引用文件」清单条目 → **规范性**（清单即规范性引用清单）；
2. 引用点落在前置/文后要素（前言/引言/目次/封面/参考文献/索引）或附录示例内容内
   → **资料性**（9.5.4.2.2：资料性引用不应列入清单）；
3. 引用点落在注/脚注内，或所在文本为术语来源标注（``[来源：…]``）→ **资料性**；
4. 引用引导词为「参见/参考/参阅」→ **资料性**；
5. 引用所在句子含要求型/指示型表述（应/不应/宜/不宜/可/须/必须/按照…的规定/符合…的
   规定）→ **规范性**（9.5.4.2.1：由要求型或指示型条款提及属规范性引用）；
6. 其余 → **资料性**（保守默认；不把范围章、术语章里的提及误算作规范性引用）。
"""

from __future__ import annotations

import re
from typing import Any, Iterator, Optional

from .parser import EX_HEADER_RE

from .naming import (
    element_id,
    escape_standard_number,
    figure_element_id,
    formula_element_id,
    table_element_id,
)

# --- 词法 -----------------------------------------------------------------

# 公式引用（式(1)／式（A.1））：与 compliance._check_formula_numbering 的 GBT-X06 判据
# 同形（tests/test_references.py::test_formula_pattern_matches_compliance_judgement 守住
# 两者一致，避免判据漂移）。
FORMULA_REFERENCE_RE = re.compile(r"式\s*[（(]\s*(?P<number>\d+(?:\.\d+)*|[A-Z]\.\d+)\s*[）)]")

# 表/图引用（表1、表 3、表C.1、图2、图B.1）。前缀表/图二字后必须紧跟编号，
# 「表面」「图中」等无编号语词不命中。
TABLE_REFERENCE_RE = re.compile(r"(?P<lead>参见|见|按|如|符合)?\s*表\s*(?P<number>[A-Z]?\d+(?:[.\-]\d+)*)")
FIGURE_REFERENCE_RE = re.compile(r"(?P<lead>参见|见|按|如|符合)?\s*图\s*(?P<number>[A-Z]?\d+(?:[.\-]\d+)*)")
# 内部条款引用：必须带显式引导词（见/参见/按/符合），裸编号不算（避免与列表项、数值混淆）。
CLAUSE_REFERENCE_RE = re.compile(r"(?P<lead>参见|见|按|符合)\s*(?P<number>\d+(?:\.\d+)*)\s*(?=[的条章]|的规定|的要求|$|\s)")

# 年份（注日期引用）：一字线/半字线 + 4 位年份，紧跟标准号。
_VERSION_RE = re.compile(r"[—\-–－~〜一]\s*((?:19|20)\d{2})\s*$")
# 标准号正则（compliance._STANDARD_NUMBER_RE）只吃到编号部分时的年份补读：紧随其后的
# 「分隔符 + 发布年份号」（16 进制范围外的常见 OCR 变体都接受）。
_VERSION_TAIL_RE = re.compile(r"^\s*[—\-–－~〜一]\s*((?:19|20)\d{2})(?!\d)")
# 标准顺序号（忽略文件代号）：把「清单写 GB 14023 / 正文写 GB/T 14023」这类同号不同形的
# 清单条目提示为可复核线索，而不是简单判「未引用」。
_NUMBER_CORE_RE = re.compile(r"([0-9]+(?:\.[0-9]+)*)")
# 被引条款（注日期引用具体条款）：标准号后紧接「,5.2」或「，5.2」。
_CITED_CLAUSE_RE = re.compile(r"^\s*[,，]\s*(\d+(?:\.\d+)*)")
# 年份形状的数字（修订年表「1981,1987」中的后一个数字不是条款号）。
_YEAR_LIKE_RE = re.compile(r"(?:19|20)\d{2}")
# 所有部分：编号后紧跟「（所有部分）」/「(所有部分)」。
_ALL_PARTS_RE = re.compile(r"[（(]\s*所有部分\s*[）)]")

# 前置/文后要素（其中的引用一律资料性，GB/T 1.1-2020 8.3/8.13）。
_BACK_AND_FRONT_MATTER = {"前言", "引言", "目次", "封面", "参考文献", "索引", "封底"}
# 要求型（应/不应）与「符合…的规定」表述（9.5.4.2.1 a）。
_REQUIREMENT_RE = re.compile(r"应|符合.{0,20}的规定")
# 资料性引导词（9.5.4.2.2 示例：「……的信息见 GB/T xxxxx」「GB/T xxxxx 给出了……」）。
# 「见」不得落在「意见/预见」这类词内（前缀紧邻判定，故用后视断言排除）。
_INFORMATIVE_LEAD_RE = re.compile(r"(?:参见|参阅|参考|给出了|(?<!意)见)\s*$")
# 括号内「见/参见」引出的并列引用（「……（见GB/T 7714、ISO 690）」）：同一括号内的**每一个**
# 引用点都属资料性（9.5.4.2.2）——顿号并列的第二项之后没有引导词，单看局部前缀会漏判。
_SEE_LEAD_RE = re.compile(r"(?:参见|参阅|参考|(?<!意)见)")
# 指示型表述（9.5.4.2.1 b）：句内「按/按照/依据 … 规定/进行/试验…」。引用常以顿号并列
# 多个文件（「按 GB/T A、GB/T B 的有关规定进行」），故按**句**判定，不看单个引用点前缀。
_INDICATIVE_SENTENCE_RE = re.compile(
    r"(?:按|按照|依据)[^。；;！？]{0,160}?(?:规定|进行|执行|测定|试验|检验|测量|施加|方法)"
)
# 指示型引导词（9.5.4.2.1 b：由「按」或「按照」提及）。
_INDICATIVE_LEAD_RE = re.compile(r"(?:按|按照|依据)\s*$")
# 术语来源标注（9.5.4.3：[来源：GB/T xxxxx—2015，4.3.5]）。
_SOURCE_NOTE_RE = re.compile(r"\[\s*来源\s*[:：]")
# 「术语和定义」章引导语（9.5.4.2.1 d）。
_TERMS_CHAPTER_LEAD_RE = re.compile(r"术语")
_TERMS_LEAD_RE = re.compile(r"界定|下列术语和定义|术语和定义适用")
# 指南标准（导则/指南）的推荐型条款（9.5.4.2.1 c）。
_GUIDE_STANDARD_RE = re.compile(r"指南|导则")

_SENTENCE_SPLIT_RE = re.compile(r"[。；;!?！？\n]")
_TEXT_SPAN_LIMIT = 400
# 结束「第 2 章清单范围」的已知要素/章（清单里被误升为标题的条目不算）。
_REGION_BREAKERS = _BACK_AND_FRONT_MATTER | {"术语和定义", "范围", "引言", "附录", "索引", "参考文献"}


def _citation_re() -> re.Pattern[str]:
    """规范性引用清单/正文的标准号识别（复用 GBT-C06 的同一前缀表，判据单源）。"""
    from .compliance import _STANDARD_NUMBER_RE  # 延迟导入：避免 verification 层与 parse 层循环

    return _STANDARD_NUMBER_RE


# 被引文件「具体内容编号」的写法（GB/T 1.1-2020 9.5.4.1.1 示例列表逐条覆盖）：
#   「……按 GB/T xxxxx-2011描述的……」（无编号）
#   「……履行 GB/T xxxxx-2009第5章确立的程序……」（第 N 章）
#   「……按照 GB/T xxxxx.1-2016中5.2规定的……」（中 M.N）
#   「……使用 GB/T xxxxx.1-2012表1中界定的符号……」（表 N）
# 顺序即优先级；纯数字编号与年份形状冲突时以年份表（1981,1987）优先排除。
_CITED_PATTERNS: tuple[tuple[re.Pattern[str], Optional[str]], ...] = (
    (re.compile(r"^\s*[，,]\s*(\d+(?:\.\d+)*)"), None),
    (re.compile(r"^\s*中\s*第\s*(\d+)\s*章"), "第{}章"),
    (re.compile(r"^\s*中\s*(\d+(?:\.\d+)*)"), None),
    (re.compile(r"^\s*中?\s*表\s*([A-Z]?\d+(?:[.\-]\d+)*)"), "表{}"),
    (re.compile(r"^\s*中?\s*图\s*([A-Z]?\d+(?:[.\-]\d+)*)"), "图{}"),
    (re.compile(r"^\s*第\s*(\d+)\s*章"), "第{}章"),
)


def _cited_clause_after(tail: str) -> Optional[str]:
    """标准号之后紧跟的「被引条款/内容编号」（9.5.4.1.1、9.5.3）；无则 ``None``。"""
    for pattern, template in _CITED_PATTERNS:
        match = pattern.match(tail)
        if not match:
            continue
        value = match.group(1)
        if template is None and _YEAR_LIKE_RE.fullmatch(value):
            continue  # 修订年表（1981,1987）里的数字不是条款号
        return template.format(value) if template else value
    return None


# --- canonical 片段账本 ----------------------------------------------------


def canonical_offsets(
    owners: list[str],
    parts: list[str],
    canonical_text: str,
) -> dict[str, tuple[int, int]]:
    """``(片段属主 id, 片段文本)`` 账本 → 属主在 ``canonicalText.text`` 中的字符区间。

    builder 逐块追加 ``canonical_parts``（并用空串跳过不产出文本的块），最后
    ``"\\n".join(非空片段).strip()`` 得到 ``canonicalText.text``。本函数按同一构造
    重算每个片段在正文中的 ``[startChar, endChar)``，供 Reference.textSpan 精确指位
    （SSIR schema 的 TextSpan 要求 startChar/endChar，不能凭空填写）。
    """
    pairs = [(owner, part) for owner, part in zip(owners, parts) if part]
    joined = "\n".join(part for _, part in pairs)
    if joined.strip() != canonical_text:
        raise ValueError("canonical 片段账本与 canonicalText.text 不一致（无法精确定位引用点）")
    shift = len(joined) - len(joined.lstrip())
    offsets: dict[str, tuple[int, int]] = {}
    cursor = -shift
    for owner, part in pairs:
        start = cursor
        end = start + len(part)
        if owner:
            offsets[owner] = (max(start, 0), max(end, 0))
        cursor = end + 1
    return offsets


class _SpanLocator:
    """在 ``canonicalText.text`` 内定位引用点（逐属主游标，重复引用各得其所）。

    命中判据容忍空白差异（引用原文可能被抽取层去掉/加上空格，如 ``GB/T 20003.1``
    与 ``GBT20003.1``）：先按原文精确查找，再按「空白可省略」的等价形式查找。
    """

    def __init__(self, canonical_text: str, offsets: dict[str, tuple[int, int]]) -> None:
        self.text = canonical_text
        self.offsets = offsets
        self._cursor: dict[str, int] = {}

    def _patterns(self, needle: str) -> list[re.Pattern[str]]:
        parts = [re.escape(part) for part in needle.split()]
        if not parts:
            return []
        flexible = re.compile(r"\s*".join(parts))
        exact = re.compile(re.escape(needle))
        return [exact] if exact.pattern == flexible.pattern else [exact, flexible]

    def locate(self, owner_id: Optional[str], needle: str) -> tuple[Optional[int], Optional[int], str]:
        """返回 ``(start, end, status)``。

        - 片段内命中 → 精确区间 + ``resolved``；
        - 片段内未命中但全文命中 → 全文区间 + ``partiallyResolved``；
        - 都未命中 → 退回属主片段区间 + ``partiallyResolved``（字符级偏移不可得，
          区间记为该内容元素本身，绝不虚报偏移）。
        """
        if not needle:
            return self._fragment(owner_id, "partiallyResolved")
        patterns = self._patterns(needle)
        if owner_id and owner_id in self.offsets:
            start, end = self.offsets[owner_id]
            cursor = self._cursor.get(owner_id, 0)
            for pattern in patterns:
                match = pattern.search(self.text, start + cursor, end)
                if match is None:
                    match = pattern.search(self.text, start, end)
                if match is not None:
                    self._cursor[owner_id] = match.end() - start
                    return match.start(), match.end(), "resolved"
        for pattern in patterns:
            match = pattern.search(self.text)
            if match is not None:
                return match.start(), match.end(), "partiallyResolved"
        return self._fragment(owner_id, "partiallyResolved")

    def _fragment(self, owner_id: Optional[str], status: str) -> tuple[Optional[int], Optional[int], str]:
        if owner_id and owner_id in self.offsets:
            start, end = self.offsets[owner_id]
            return start, end, status
        return None, None, status


# --- 抽取 -----------------------------------------------------------------


def _normalised(text: str) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def _is_reference_chapter(number: str, title: str) -> bool:
    """第 2 章「规范性引用文件」：按章号或标题判定（编号缺失的文档也能命中）。"""
    number = str(number or "").strip()
    if number == "2" or number.startswith("2."):
        return True
    return "规范性引用文件" in _normalised(title)


def _starts_new_region(node: dict[str, Any]) -> bool:
    """该节点是否结束「第 2 章清单范围」（编号章条 / 已知要素 / 附录）。

    抽取常把清单的**首条条目**升成无编号文档块标题（GB_T_39567-2020 实测：
    ``## GB/T 755 旋转电机 定额和性能`` 与「2 规范性引用文件」同级，其余条目成为
    其内容）——这类无编号、非已知要素的块仍属清单范围，直到出现编号章条或已知要素。
    """
    if str(node.get("number") or "").strip():
        return True
    if str(node.get("nodeType") or "") == "annex":
        return True
    title = _normalised(str(node.get("title") or ""))
    return any(title == _normalised(name) or title.startswith(_normalised(name)) for name in _REGION_BREAKERS)


def _sector_of(node: dict[str, Any]) -> Optional[str]:
    title = _normalised(str(node.get("title") or ""))
    if not title:
        return None
    for name in _BACK_AND_FRONT_MATTER:
        if title == _normalised(name) or title.startswith(_normalised(name)):
            return name
    return None


def _sentence_around(text: str, index: int) -> str:
    start = 0
    for match in _SENTENCE_SPLIT_RE.finditer(text):
        if match.start() >= index:
            break
        start = match.end()
    end = len(text)
    for match in _SENTENCE_SPLIT_RE.finditer(text, index):
        end = match.start()
        break
    return text[start:end]


def _nature_of(
    *,
    in_reference_chapter: bool,
    sector: Optional[str],
    example_content: bool,
    presentation: str,
    text: str,
    index: int,
    matched: str,
    clause_title: str = "",
    guide_standard: bool = False,
) -> str:
    """规范性/资料性判定（GB/T 1.1-2020 9.5.4.1-9.5.4.3 的**逐条**判据，顺序即优先级）。

    1. 第 2 章「规范性引用文件」清单条目 → 规范性（8.6.3：清单所列均为规范性引用）；
    2. 前置/文后要素（前言/引言/目次/封面/参考文献/索引）、附录示例内容、注/脚注内
       → 资料性（9.5.4.2.2；8.13：资料性引用的文件应列入参考文献）；
    3. 术语来源标注（``[来源：GB/T xxxxx—2015，4.3.5]``）→ 资料性（9.5.4.3 标明来源
       属资料性提及，进参考文献）；
    4. 「术语和定义」章的**引导语**提及 → 规范性（9.5.4.2.1 d）；
    5. 引用由「见/参见/参考/参阅/给出了」引出，或处在「（见 A、B）」这类括号内与引导词
       并列（顿号后的第二项起没有引导词）→ 资料性（9.5.4.2.2）；
    6. 要求型（应/不应）、指示型（按/按照）、指南类标准的推荐型（宜/不宜）→ 规范性
       （9.5.4.2.1 a/b/c）；
    7. 其余 → 资料性（9.5.4.2.2：9.5.4.2.1 之外的表述形式）。
    """
    if in_reference_chapter:
        return "normative"
    if sector is not None or example_content:
        return "informative"
    if presentation in {"note", "footnote"}:
        return "informative"
    sentence = _sentence_around(text, index)
    if _SOURCE_NOTE_RE.search(sentence):
        return "informative"
    if _TERMS_CHAPTER_LEAD_RE.search(_normalised(clause_title)) and _TERMS_LEAD_RE.search(sentence):
        return "normative"
    lead_prefix = text[:index]
    if _INFORMATIVE_LEAD_RE.search(lead_prefix):
        return "informative"
    paren = max(lead_prefix.rfind("（"), lead_prefix.rfind("("))
    if paren >= 0 and index - paren <= 40:
        inner = text[paren:index]
        if not re.search(r"[。；;！？]", inner) and _SEE_LEAD_RE.search(inner):
            return "informative"
    if _REQUIREMENT_RE.search(sentence):
        return "normative"
    if guide_standard and re.search(r"[宜不宜]", sentence):
        return "normative"
    if _INDICATIVE_LEAD_RE.search(lead_prefix) or _INDICATIVE_SENTENCE_RE.search(sentence):
        return "normative"
    return "informative"


def _carriers(node: dict[str, Any], document: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """节点内可承载引用的文本片段：正文/列表项/表内文本/图题图例/公式区。"""
    tables = {str(table.get("id")): table for table in document.get("tables") or []}
    figures = {str(figure.get("id")): figure for figure in document.get("figures") or []}
    formulas = {str(formula.get("id")): formula for formula in document.get("formulas") or []}
    for content in node.get("contentElements") or []:
        owner = str(content.get("id") or "")
        presentation = str(content.get("presentationType") or "")
        if content.get("tableRef") and str(content["tableRef"]) in tables:
            for row in tables[str(content["tableRef"])].get("rows") or []:
                for cell in row.get("cells") or []:
                    text = str(cell.get("text") or "")
                    if text.strip():
                        yield {"text": text, "owner": owner, "presentation": presentation}
        if content.get("figureRef") and str(content["figureRef"]) in figures:
            figure = figures[str(content["figureRef"])]
            for key in ("caption", "legend"):
                text = str(figure.get(key) or "")
                if text.strip():
                    yield {"text": text, "owner": owner, "presentation": presentation}
            for sub in figure.get("subCaptions") or []:
                text = str(sub.get("text") or "")
                if text.strip():
                    yield {"text": text, "owner": owner, "presentation": presentation}
        if content.get("formulaRef") and str(content["formulaRef"]) in formulas:
            formula = formulas[str(content["formulaRef"])]
            text = str(formula.get("rawText") or "")
            if text.strip():
                yield {"text": text, "owner": owner, "presentation": presentation}
        text = str(content.get("textContent") or "")
        if text.strip():
            yield {"text": text, "owner": owner, "presentation": presentation}
        for item in content.get("listItems") or []:
            item_text = str(item.get("text") or "")
            if item_text.strip():
                yield {"text": item_text, "owner": owner, "presentation": presentation}


def _reference_item(
    *,
    index: int,
    document_id: str,
    canonical_id: str,
    source_id: str,
    reference_type: str,
    target_type: str,
    raw_target: str,
    cited_text: str,
    span: dict[str, Any],
    resolved_document_id: Optional[str] = None,
    resolved_version: Optional[str] = None,
    resolved_clause: Optional[str] = None,
    resolved_target_id: Optional[str] = None,
    resolution_status: str = "resolved",
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "id": f"{document_id}#Ref-{index:04d}",
        "sourceNodeId": source_id,
        "referenceType": reference_type,
        "targetType": target_type,
        "rawTarget": raw_target,
        "textSpan": span,
        "resolutionStatus": resolution_status,
    }
    if resolved_document_id:
        item["resolvedDocumentId"] = resolved_document_id
    if resolved_version:
        item["resolvedVersion"] = resolved_version
    if resolved_clause:
        item["resolvedClause"] = resolved_clause
    if resolved_target_id:
        item["resolvedTargetId"] = resolved_target_id
    if cited_text:
        item["citedText"] = cited_text[:_TEXT_SPAN_LIMIT]
    return item


def _span(
    *,
    index: int,
    document_id: str,
    canonical_id: str,
    locator: _SpanLocator,
    owner: str,
    source_id: str,
    needle: str,
    body_anchor: Optional[dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    start, end, status = locator.locate(owner, needle)
    text = locator.text[start:end] if start is not None and end is not None else needle
    span: dict[str, Any] = {
        "id": f"{document_id}#RefText-{index:04d}",
        "canonicalTextId": canonical_id,
        "startChar": int(start if start is not None else 0),
        "endChar": int(end if end is not None else (start or 0) + 1),
        "text": text,
    }
    if body_anchor:
        span["sourceAnchor"] = body_anchor
    return span, status


def extract(
    document: dict[str, Any],
    offsets: Optional[dict[str, tuple[int, int]]] = None,
) -> list[dict[str, Any]]:
    """SSIRDocument → occurrence 级引用数组（外部标准引用 + 本文内部引用点）。

    ``offsets``：``canonical_offsets()`` 的结果（builder 提供）；缺省时 textSpan 只带
    ``canonicalTextId``/文本，偏移按全文首命中估算并置 ``partiallyResolved``。
    行号说明：本函数不给引用点行号（解析器 ``Block.start_line`` 在目次区段后有系统偏移，
    见 docs/12 §3.96 缺陷记录；引用点以 ``textSpan``（字符区间 + 原文）与 ``sourceNodeId``
    精确定位，宁可不给行号也不给错行号）。
    """
    document_id = str(document.get("id") or "")
    if not document_id:
        return []
    canonical = document.get("canonicalText") or {}
    canonical_id = str(canonical.get("id") or "") or f"{document_id}#Canonical"
    locator = _SpanLocator(str(canonical.get("text") or ""), offsets or {})

    citation_re = _citation_re()
    tables = {(str(t.get("number") or "").strip()): str(t.get("id")) for t in document.get("tables") or []}
    figures = {(str(f.get("number") or "").strip()): str(f.get("id")) for f in document.get("figures") or []}
    formulas = {(str(f.get("number") or "").strip()): str(f.get("id")) for f in document.get("formulas") or []}
    clause_numbers = _clause_number_set(document)
    guide_standard = bool(
        _GUIDE_STANDARD_RE.search(
            str(((document.get("metadata") or {}).get("standard") or {}).get("chineseTitle") or "")
            or str(((document.get("metadata") or {}).get("common") or {}).get("title") or "")
        )
    )

    items: list[dict[str, Any]] = []
    seen_internal: set[tuple[str, str, str, str]] = set()

    def add(**kwargs: Any) -> None:
        kwargs.setdefault("index", len(items) + 1)
        items.append(_reference_item(**kwargs))

    def scan_external(
        *,
        text: str,
        owner: str,
        source_id: str,
        clause_label: str,
        presentation: str,
        in_reference_chapter: bool,
        sector: Optional[str],
        example_content: bool,
        anchor: Optional[dict[str, Any]],
    ) -> None:
        clause_label = str(clause_label or "")
        for match in citation_re.finditer(text):
            raw = match.group(0).strip()
            if not raw:
                continue
            tail = text[match.end():]
            version_match = _VERSION_RE.search(raw)
            version = version_match.group(1) if version_match else None
            if version is None:
                # 标准号与发布年份号之间可能是 OCR 变体（「一」、全角连字符、波浪号等），
                # 标准号正则只吃到编号部分：这里补读紧随其后的「分隔符 + 年份」（注日期引用，
                # GB/T 1.1-2020 8.6.3.1「文件代号、顺序号及发布年份号」）。
                version_tail = _VERSION_TAIL_RE.match(tail)
                if version_tail:
                    version = version_tail.group(1)
                    raw = f"{raw}{version_tail.group(0)}"
                    tail = tail[version_tail.end():]
            # 被引文件的**具体内容编号**（9.5.4.1.1：提及被引文件的章、条、图、表编号
            # 才注日期；9.5.3 规定内容编号的写法）。
            cited_clause = _cited_clause_after(tail)
            nature = _nature_of(
                in_reference_chapter=in_reference_chapter,
                sector=sector,
                example_content=example_content,
                presentation=presentation,
                text=text,
                index=match.start(),
                matched=raw,
                clause_title=clause_label,
                guide_standard=guide_standard,
            )
            # rawTarget：清单条目原样保留整条（含标准名称/「所有部分」），正文引用保留
            # 标准号 + 被引条款（注日期引用具体条款的写法，9.5.4.1.1）。
            raw_target = text.strip() if in_reference_chapter and len(text.strip()) <= 200 else raw
            if cited_clause and cited_clause not in raw_target:
                raw_target = f"{raw_target},{cited_clause}"
            needle = raw
            span, status = _span(
                index=len(items) + 1,
                document_id=document_id,
                canonical_id=canonical_id,
                locator=locator,
                owner=owner,
                source_id=source_id,
                needle=needle,
                body_anchor=anchor,
            )
            add(
                document_id=document_id,
                canonical_id=canonical_id,
                source_id=source_id,
                reference_type=nature,
                target_type="externalStandard",
                raw_target=raw_target,
                cited_text=text.strip(),
                span=span,
                # 被引标准标识含版本（TDRS §三/§十一：GB/T 1.1—2020 → GB_T_1.1-2020），
                # 版本另在 resolvedVersion 冗余一份，便于按系列聚合。
                resolved_document_id=escape_standard_number(raw),
                resolved_version=version,
                resolved_clause=cited_clause,
                resolution_status=status,
            )

    def scan_internal(
        *,
        text: str,
        owner: str,
        source_id: str,
        clause_label: str,
        presentation: str,
        in_reference_chapter: bool,
        sector: Optional[str],
        example_content: bool,
        anchor: Optional[dict[str, Any]],
    ) -> None:
        if sector is not None:
            # 前置/文后要素（目次/索引/参考文献/封面）里的「表 3」是清单条目/索引项，
            # 不是引用点（GB/T 1.1-2020 9.5.3：引用点在正文条款内）。
            return
        clause_label = str(clause_label or "")

        def emit(regex: re.Pattern[str], target_type: str, registry: dict[str, str], kind: str) -> None:
            label = {"table": "表", "figure": "图", "formula": "式（"}[kind]
            for match in regex.finditer(text):
                number = match.group("number")
                # 引用目标名归一为「表1」「图1」「式（1）」形态：原文里「见图1」「图 1」「按图 11」
                # 是同一目标的引用点，仅引导词/空格不同（canonical 原文另在 textSpan 保留）。
                raw_target = f"{label}{number}）" if kind == "formula" else f"{label}{number}"
                target_id = registry.get(number)
                if target_id is None:
                    target_id = registry.get(number.replace("-", "."))
                resolved = target_id is not None
                nature = _nature_of(
                    in_reference_chapter=in_reference_chapter,
                    sector=sector,
                    example_content=example_content,
                    presentation=presentation,
                    text=text,
                    index=match.start(),
                    matched=match.group(0),
                    clause_title=clause_label,
                    guide_standard=guide_standard,
                )
                key = (target_type, number, source_id, nature)
                if key in seen_internal:
                    continue
                seen_internal.add(key)
                span, status = _span(
                    index=len(items) + 1,
                    document_id=document_id,
                    canonical_id=canonical_id,
                    locator=locator,
                    owner=owner,
                    source_id=source_id,
                    needle=match.group(0).strip(),
                    body_anchor=anchor,
                )
                resolved_target = target_id
                if resolved_target is None and kind:
                    builder = {"table": table_element_id, "figure": figure_element_id, "formula": formula_element_id}[kind]
                    resolved_target = builder(document_id, number)
                add(
                    document_id=document_id,
                    canonical_id=canonical_id,
                    source_id=source_id,
                    reference_type=nature,
                    target_type=target_type,
                    raw_target=raw_target,
                    cited_text=text.strip(),
                    span=span,
                    resolved_document_id=document_id,
                    resolved_clause=number,
                    resolved_target_id=resolved_target,
                    resolution_status="resolved" if resolved else "unresolved",
                )

        emit(TABLE_REFERENCE_RE, "internalTable", tables, "table")
        emit(FIGURE_REFERENCE_RE, "internalFigure", figures, "figure")
        emit(FORMULA_REFERENCE_RE, "internalFormula", formulas, "formula")
        for match in CLAUSE_REFERENCE_RE.finditer(text):
            number = match.group("number")
            if number not in clause_numbers:
                continue
            nature = _nature_of(
                in_reference_chapter=in_reference_chapter,
                sector=sector,
                example_content=example_content,
                presentation=presentation,
                text=text,
                index=match.start(),
                matched=match.group(0),
                clause_title=clause_label,
                guide_standard=guide_standard,
            )
            key = ("internalClause", number, source_id, nature)
            if key in seen_internal:
                continue
            seen_internal.add(key)
            span, status = _span(
                index=len(items) + 1,
                document_id=document_id,
                canonical_id=canonical_id,
                locator=locator,
                owner=owner,
                source_id=source_id,
                needle=match.group(0).strip(),
                body_anchor=anchor,
            )
            add(
                document_id=document_id,
                canonical_id=canonical_id,
                source_id=source_id,
                reference_type=nature,
                target_type="internalClause",
                raw_target=match.group(0).strip(),
                cited_text=text.strip(),
                span=span,
                resolved_document_id=document_id,
                resolved_clause=number,
                resolved_target_id=element_id(document_id, number),
                resolution_status="resolved",
            )

    def walk(node: dict[str, Any], sector: Optional[str], in_reference_chapter: bool) -> None:
        node_sector = _sector_of(node) or sector
        node_in_reference_chapter = in_reference_chapter or _is_reference_chapter(
            str(node.get("number") or ""), str(node.get("title") or "")
        )
        example_content = bool(node.get("exampleContent"))
        node_id = str(node.get("id") or "")
        # 章条标签（编号 + 标题）：既用于条款判定（9.5.4.2.1 d「术语和定义」引导语），
        # 也用于出现位置的显示。
        node_label = " ".join(
            part for part in (str(node.get("number") or "").strip(), str(node.get("title") or "").strip()) if part
        )
        for carrier in _carriers(node, document):
            owner = str(carrier.get("owner") or "")
            anchor = _content_anchor(node, owner)
            scan_external(
                text=str(carrier["text"]),
                owner=owner,
                source_id=owner or node_id,
                clause_label=node_label,
                presentation=str(carrier.get("presentation") or ""),
                in_reference_chapter=node_in_reference_chapter,
                sector=node_sector,
                example_content=example_content,
                anchor=anchor,
            )
            scan_internal(
                text=str(carrier["text"]),
                owner=owner,
                source_id=owner or node_id,
                clause_label=node_label,
                presentation=str(carrier.get("presentation") or ""),
                in_reference_chapter=node_in_reference_chapter,
                sector=node_sector,
                example_content=example_content,
                anchor=anchor,
            )
        # 标题本身也可能是引用（抽取把清单首条条目升成标题时，标准号只在标题里）：
        # 标题属于该节点的 canonical 片段，故以节点为属主扫描。
        node_title = str(node.get("title") or "").strip()
        if node_title and node_id:
            scan_external(
                text=node_title,
                owner=node_id,
                source_id=node_id,
                clause_label=node_label,
                presentation="heading",
                in_reference_chapter=node_in_reference_chapter,
                sector=node_sector,
                example_content=example_content,
                anchor=_content_anchor(node, node_id) or (node.get("sourceAnchors") or [None])[0],
            )
        region = node_in_reference_chapter
        for child in node.get("children") or []:
            if region and not _starts_new_region(child):
                # 第 2 章清单范围延续到紧邻的无编号非要素块
                # （首条条目被抽取升成标题的情形，见 _starts_new_region）。
                child_flag = True
            else:
                child_flag = _is_reference_chapter(
                    str(child.get("number") or ""), str(child.get("title") or "")
                )
            walk(child, node_sector, child_flag)
            region = child_flag

    root = document.get("structuralRoot") or {}
    walk(root, None, False)
    return items


def _content_anchor(node: dict[str, Any], content_id: str) -> Optional[dict[str, Any]]:
    for content in node.get("contentElements") or []:
        if str(content.get("id")) != content_id:
            continue
        for anchor in content.get("sourceAnchors") or []:
            return anchor
    for anchor in node.get("sourceAnchors") or []:
        return anchor
    return None


def _clause_number_set(document: dict[str, Any]) -> set[str]:
    numbers: set[str] = set()

    def walk(node: dict[str, Any]) -> None:
        number = str(node.get("number") or "").strip()
        if number:
            numbers.add(number)
            if "." in number:
                numbers.add(number.rsplit(".", 1)[0])
        for child in node.get("children") or []:
            walk(child)

    walk(document.get("structuralRoot") or {})
    return numbers


# --- 汇总（TDRS §二 六元组视图） -------------------------------------------


def reference_type_of(item: dict[str, Any]) -> str:
    """引用类型：``dated`` / ``undated`` / ``all_parts``（GB/T 1.1-2020 9.5.4.1）。

    由 ``rawTarget`` + ``resolvedVersion`` 无损还原：带年份 → 注日期引用；带「（所有
    部分）」→ 所有部分引用；否则不注日期引用。
    """
    raw = str(item.get("rawTarget") or "")
    if _ALL_PARTS_RE.search(raw):
        return "all_parts"
    return "dated" if item.get("resolvedVersion") else "undated"


def _entry_title(raw: str, need_version: bool = True) -> Optional[str]:
    """清单条目原文 → 标准名称（编号之后的部分，去掉「（所有部分）」标记）。"""
    text = _ALL_PARTS_RE.sub(" ", str(raw or "")).strip()
    match = _citation_re().search(text)
    if not match:
        return None
    title = text[match.end():].strip(" ,，、:：;；")
    return title or None


def summarise(document: dict[str, Any]) -> dict[str, Any]:
    """SSIRDocument → TDRS §二 六元组视图（按被引标准合并；内部引用单独成节）。"""
    metadata = (document.get("metadata") or {}).get("standard") or {}
    items = document.get("references") or []
    clause_index, md_lines = _clause_index(document)
    external: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    internal: dict[str, list[dict[str, Any]]] = {"internalTable": [], "internalFigure": [], "internalFormula": [], "internalClause": []}
    for item in items:
        target_type = str(item.get("targetType") or "")
        if target_type == "externalStandard":
            key = str(item.get("resolvedDocumentId") or item.get("rawTarget") or "")
            if key not in external:
                external[key] = {
                    "standard_id": key,
                    "standard_number": None,
                    "version": item.get("resolvedVersion"),
                    "title": None,
                    "reference_type": reference_type_of(item),
                    "nature": str(item.get("referenceType") or "informative"),
                    "source_clauses": [],
                    "cited_clauses": [],
                    "raw_text": None,
                    "canonical_line": None,
                }
                order.append(key)
            entry = external[key]
            clause = clause_index.get(str(item.get("sourceNodeId") or ""), "")
            md_line = (item.get("textSpan") or {}).get("sourceAnchor", {}).get("markdownStartLine") or md_lines.get(str(item.get("sourceNodeId") or ""))
            entry["source_clauses"].append(
                {
                    "clause": clause,
                    "md_line": md_line,
                    "nature": str(item.get("referenceType") or ""),
                    "element_id": str(item.get("sourceNodeId") or ""),
                    "raw": str(item.get("rawTarget") or ""),
                }
            )
            if item.get("resolvedClause"):
                entry["cited_clauses"].append(str(item["resolvedClause"]))
            raw = str(item.get("rawTarget") or "")
            if entry["standard_number"] is None and raw:
                number_text = _citation_re().match(raw) or _citation_re().search(raw)
                if number_text:
                    entry["standard_number"] = number_text.group(0).strip()
            if entry["title"] is None and str(clause) == "2":
                entry["raw_text"] = raw
                entry["title"] = _entry_title(raw)
                entry["canonical_line"] = md_line
            if item.get("referenceType") == "normative":
                entry["nature"] = "normative"
            entry["reference_type"] = entry["reference_type"] or reference_type_of(item)
        elif target_type in internal:
            internal[target_type].append(
                {
                    "raw": str(item.get("rawTarget") or ""),
                    "number": str(item.get("resolvedClause") or ""),
                    "target_id": str(item.get("resolvedTargetId") or ""),
                    "element_id": str(item.get("sourceNodeId") or ""),
                    "clause": clause_index.get(str(item.get("sourceNodeId") or ""), ""),
                    "md_line": (item.get("textSpan") or {}).get("sourceAnchor", {}).get("markdownStartLine"),
                    "nature": str(item.get("referenceType") or ""),
                    "resolved": str(item.get("resolutionStatus") or "") == "resolved",
                }
            )
    references = []
    for key in order:
        entry = external[key]
        entry["version"] = entry["version"] or None
        references.append(entry)
    references.sort(key=lambda entry: (str(entry["standard_number"] or entry["standard_id"])))
    uncited = uncited_list_entries(document)
    unlisted = unlisted_citation_entries(document)
    unresolved = [
        item
        for item in internal["internalTable"] + internal["internalFigure"] + internal["internalFormula"]
        if not item["resolved"]
    ]
    return {
        "standardId": document.get("id"),
        "standardNumber": metadata.get("standardNumber"),
        "standardTitle": metadata.get("chineseTitle") or (document.get("metadata") or {}).get("common", {}).get("title"),
        "referenceCount": len(references),
        "references": references,
        "internalReferences": {key: value for key, value in internal.items() if value},
        "internalCount": sum(len(value) for value in internal.values()),
        "unresolvedInternalCount": len(unresolved),
        "unresolvedInternal": unresolved,
        # 清单里列出、正文中没有任何引用点的条目（GBT-C06/reference-entry-not-cited）。
        "uncitedListEntries": uncited,
        "uncitedListEntryCount": len(uncited),
        # 正文规范性引用、但清单未列出（GBT-C06/normative-citation-not-listed）。
        "unlistedCitations": unlisted,
        "unlistedCitationCount": len(unlisted),
    }


def _structure_index(document: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """元素 id → {clause, md_line, in_reference_chapter, sector}（一次遍历，判据单源）。

    - ``clause``：出现条款（章条号/附录路径；清单条目一律记 ``2``，见 ``_starts_new_region``）；
    - ``in_reference_chapter``：该元素是否落在第 2 章文件清单范围内；
    - ``sector``：前置/文后要素名（前言/引言/目次/封面/参考文献/索引/封底），正文与附录为 ``None``。
    """
    index: dict[str, dict[str, Any]] = {}

    def walk(
        node: dict[str, Any],
        chain: list[str],
        in_reference_chapter: bool,
        sector: Optional[str],
        in_example: bool = False,
    ) -> None:
        number = str(node.get("number") or "").strip()
        title = str(node.get("title") or "").strip()
        node_in_reference_chapter = in_reference_chapter or _is_reference_chapter(number, title)
        node_sector = _sector_of(node) or sector
        # 清单条目（含被抽取升成无编号标题的首条条目）的出现条款是第 2 章，而非其标题。
        label = (number or "2" if node_in_reference_chapter else number or title) or (chain[-1] if chain else "")
        if label:
            chain = [*chain, label]
        path = chain[-1] if chain else ""
        node_id = str(node.get("id") or "")
        # 示例内容（附录示例由 builder 打 ``example`` 标记；正文/附录里的「示例：」标题子树
        # 按标题判据）内的引用只是示范写法，不构成本文对文件的引用（GBT-C06 反向检查用）。
        node_in_example = in_example or bool(node.get("example")) or bool(EX_HEADER_RE.match(title))
        index[node_id] = {
            "clause": path,
            "md_line": _markdown_line(node),
            "in_reference_chapter": node_in_reference_chapter,
            "sector": node_sector,
            "in_example": node_in_example,
        }
        for content in node.get("contentElements") or []:
            content_id = str(content.get("id") or "")
            index[content_id] = {
                "clause": path,
                "md_line": _markdown_line(content) or index[node_id]["md_line"],
                "in_reference_chapter": node_in_reference_chapter,
                "sector": node_sector,
                "in_example": node_in_example or bool(content.get("example")),
            }
        region = node_in_reference_chapter
        for child in node.get("children") or []:
            if region and not _starts_new_region(child):
                child_flag = True
            else:
                child_flag = _is_reference_chapter(
                    str(child.get("number") or ""), str(child.get("title") or "")
                )
            walk(child, chain, child_flag, node_sector, node_in_example)
            region = child_flag

    walk(document.get("structuralRoot") or {}, [], False, None, False)
    return index


def _clause_index(document: dict[str, Any]) -> tuple[dict[str, str], dict[str, Optional[int]]]:
    """内容元素 id → 出现条款（章条号/附录路径）；元素 id → markdown 行号。"""
    index = _structure_index(document)
    return (
        {element_id: info["clause"] for element_id, info in index.items()},
        {element_id: info["md_line"] for element_id, info in index.items()},
    )


def list_entries(document: dict[str, Any]) -> list[dict[str, Any]]:
    """第 2 章文件清单条目（每被引标准一条：标准号/版本/名称/清单行号/元素 id/引用性质）。

    判据依据 GB/T 1.1-2020 8.6.3.1：清单条目 = 第 2 章内的标准号出现点（``rawTarget``
    原文与元素 id 保留，供人工复核）。
    """
    index = _structure_index(document)
    entries: dict[str, dict[str, Any]] = {}
    for item in document.get("references") or []:
        if str(item.get("targetType") or "") != "externalStandard":
            continue
        node = str(item.get("sourceNodeId") or "")
        info = index.get(node) or {}
        if not info.get("in_reference_chapter"):
            continue
        key = str(item.get("resolvedDocumentId") or item.get("rawTarget") or "")
        if not key:
            continue
        entry = entries.setdefault(
            key,
            {
                "standard_id": key,
                "base_id": _base_standard_id(item),
                "version": item.get("resolvedVersion"),
                "standard_number": None,
                "title": None,
                "raw_text": None,
                "nature": str(item.get("referenceType") or "informative"),
                "clause": info.get("clause"),
                "md_line": info.get("md_line"),
                "element_id": node,
            },
        )
        raw = str(item.get("rawTarget") or "")
        if entry["raw_text"] is None and raw:
            match = _citation_re().match(raw) or _citation_re().search(raw)
            entry["raw_text"] = raw
            entry["standard_number"] = match.group(0).strip() if match else key
            entry["title"] = _entry_title(raw)
        if item.get("referenceType") == "normative":
            entry["nature"] = "normative"
    return sorted(entries.values(), key=lambda entry: str(entry["standard_number"] or entry["standard_id"]))


def _base_standard_id(item: dict[str, Any]) -> str:
    """被引标准标识去掉版本后的基标识（同一标准的注日期/不注日期形态归一）。

    清单条目可能写「GB/T 4208-2017」而正文写「GB/T 4208」（或被抽取层丢了年份）——
    「同一标准」的判定必须容忍版本差异，否则会把真实引用判成未引用。
    """
    key = str(item.get("resolvedDocumentId") or item.get("rawTarget") or "")
    match = re.match(r"^(.*?)[-_](?:19|20)\d{2}$", key)
    return match.group(1) if match else key


def _example_span(document: dict[str, Any], item: dict[str, Any]) -> bool:
    """引用点是否落在「示例」块内（按 canonical 行首判据）。

    示例里的引用只是示范写法（如「示例：“…按 GB/T 2912.1—2009 描述的方法测定…”」），
    不构成本文对文件的引用；正文里的示例常是**裸段落**（无「示例：」标题），
    故按引用点所在行的行首判据（``示例`` / ``示例N:``）判定，与块结构无关。
    """
    span = item.get("textSpan") or {}
    start = span.get("startChar")
    text = str((document.get("canonicalText") or {}).get("text") or "")
    if not isinstance(start, int) or start <= 0 or not text:
        return False
    line_start = text.rfind("\n", 0, min(start, len(text))) + 1
    head = text[line_start:start]
    # 引用点所在行的行首若有「示例：」标记（含条号前缀与加粗写法），其后的引用属示例内容。
    return bool(re.search(r"示例\s*\d*\s*[:：]", head))


def _comparison_key(base_id: str) -> str:
    """「同一文件」的比较键：忽略分隔符差异（空格/下划线/斜杠/连字符）与紧贴编号的年份。

    OCR 与抽取会把同一个文件写成不同形态——``GB/T 2423.3—2006`` / ``GBT2423.3—2006``、
    ``GB 755—2008`` / ``GB 7552008``（分隔符丢失）、``GB 12350-2009`` / ``GB123502009``
    （年份与编号粘连）。判「清单是否列了它」必须容忍这些形态，否则真实引用会被判成未列。
    仅用于**比较**，不改变任何标识（``standard_id`` 仍是权威主键）。
    """
    key = re.sub(r"[\s_/／\-—–－~〜一]", "", str(base_id or ""))
    if len(key) > 4 and re.search(r"(?:19|20)\d{2}$", key) and key[-5].isdigit():
        key = key[:-4]
    return key.upper()


def _number_core(key: str) -> str:
    """标准标识里的「顺序号」（忽略文件代号，如 GB/T vs GB 的差异）：14023、2423.1、20001.10。"""
    match = _NUMBER_CORE_RE.search(str(key or ""))
    return match.group(1) if match else str(key or "")


def uncited_list_entries(
    document: dict[str, Any], *, require_normative: bool = False
) -> list[dict[str, Any]]:
    """清单里列出、但在**正文（含附录）中没有任何引用点**的条目（用户 2026-09-29 裁定）。

    判据反向自 GB/T 1.1-2020 8.6.3.1（文件清单中应列出该文件中规范性引用的每个文件）
    与 9.5.4.2.2（资料性引用不应列入清单）：清单条目应在正文中被引用。

    不计作正文引用：前置/文后要素（前言/引言/目次/封面/参考文献/索引/封底；8.13、9.5.4.3）
    内的提及、清单自身（第 2 章）的出现点；附录（规范性/资料性）内的引用计入。
    同一标准的注日期/不注日期形态按基标识归一（清单写「GB/T 4208-2017」而正文写
    「GB/T 4208」不算未引用）。

    ``require_normative=True`` 时更严：正文里必须存在**规范性**引用（只出现在注/脚注/
    示例内容里的不算），供需要区分引用性质时使用。
    """
    index = _structure_index(document)
    cited: set[str] = set()
    body: dict[str, list[dict[str, Any]]] = {}
    for item in document.get("references") or []:
        if str(item.get("targetType") or "") != "externalStandard":
            continue
        info = index.get(str(item.get("sourceNodeId") or "")) or {}
        if info.get("in_reference_chapter") or info.get("sector"):
            continue
        base = _base_standard_id(item)
        if not require_normative or str(item.get("referenceType") or "") == "normative":
            cited.add(base)
        body.setdefault(_number_core(base), []).append(
            {
                "standard_id": base,
                "raw": str(item.get("rawTarget") or ""),
                "clause": info.get("clause"),
                "md_line": info.get("md_line"),
                "nature": str(item.get("referenceType") or ""),
            }
        )
    cited_keys = {_comparison_key(base) for base in cited}
    uncited: list[dict[str, Any]] = []
    for entry in list_entries(document):
        # 「同一文件」按比较键判定（忽略分隔符差异与紧贴编号的年份，如清单 `GB 7552008`
        # 对正文 `GB 755-2008`），避免把真实引用判成未引用。
        if _comparison_key(entry["base_id"]) in cited_keys:
            continue
        # 同顺序号、不同文件代号（清单写 GB 14023 而正文写 GB/T 14023）→ 附线索，便于复核
        # 是清单条目写法有误还是正文漏写引用；不据此认定已引用。
        entry["similar_citations"] = [
            other for other in body.get(_number_core(entry["base_id"]), []) if other["standard_id"] != entry["base_id"]
        ]
        uncited.append(entry)
    return uncited


def unlisted_citation_entries(document: dict[str, Any]) -> list[dict[str, Any]]:
    """正文**规范性引用**了、但第 2 章清单没有列出的被引文件（用户 2026-09-29 裁定 ③ 的反向）。

    判据正面来自 GB/T 1.1-2020 8.6.3.1「文件清单中应列出该文件中规范性引用的每个文件」；
    9.5.4.2.2 的资料性引用（参见/参考/参阅）不在检查范围（本就不应列入清单）。

    与 ``uncited_list_entries`` 对称：只算**正文（含附录）**内的规范性引用点，前置/文后要素
    （前言/引言/目次/封面/参考文献/索引/封底）与清单自身的出现点不计；同一标准的注日期/
    不注日期形态按基标识归一；正文按「所有部分」引用而清单逐个列出该系列的各个部分时
    视为已列（``matched_via="series"``），并保留 ``occurrences`` 供人工复核。
    """
    index = _structure_index(document)
    listed_ids = {entry["base_id"] for entry in list_entries(document)}
    listed_keys = {_comparison_key(base) for base in listed_ids}
    found: dict[str, dict[str, Any]] = {}
    for item in document.get("references") or []:
        if str(item.get("targetType") or "") != "externalStandard":
            continue
        if str(item.get("referenceType") or "") != "normative":
            continue  # 资料性引用不应列入清单（9.5.4.2.2），无所谓「未列」
        node = str(item.get("sourceNodeId") or "")
        info = index.get(node) or {}
        if info.get("in_reference_chapter") or info.get("sector"):
            continue
        if info.get("in_example") or _example_span(document, item):
            # 示例里的引用只是示范写法（如「示例：“…按 GB/T 2912.1—2009 描述的方法测定…”」），
            # 不构成本文对文件的规范性使用，不算「清单未列」。
            continue
        base = _base_standard_id(item)
        if not base:
            continue
        entry = found.setdefault(
            base,
            {
                "standard_id": str(item.get("resolvedDocumentId") or base),
                "base_id": base,
                "raw": str(item.get("rawTarget") or ""),
                "version": item.get("resolvedVersion"),
                "occurrences": [],
            },
        )
        entry["occurrences"].append(
            {
                "raw": str(item.get("rawTarget") or ""),
                "clause": info.get("clause"),
                "element_id": node,
                "md_line": info.get("md_line"),
                "nature": str(item.get("referenceType") or ""),
            }
        )
    unlisted: list[dict[str, Any]] = []
    for base, entry in found.items():
        key = _comparison_key(base)
        if key in listed_keys:
            continue
        series = sorted(candidate for candidate in listed_ids if _comparison_key(candidate).startswith(key + "."))
        if series:
            # 系列引用：正文写「GB/T 20001（所有部分）」，清单逐个列出各部分 → 视为已列。
            entry["matched_via"] = "series"
            entry["listed_parts"] = series
            continue
        covered = sorted(
            candidate
            for candidate in listed_ids
            if key.startswith(_comparison_key(candidate) + ".")
        )
        if covered:
            # 反向「所有部分」：清单写「GB/T 3102（所有部分）」，正文引用具体部分「GB/T 3102.1」
            # → 清单已覆盖该系列（8.6.3），不算未列。
            entry["matched_via"] = "all_parts"
            entry["listed_parts"] = covered
            continue
        unlisted.append(entry)
    return sorted(unlisted, key=lambda entry: entry["base_id"])


def _markdown_line(obj: dict[str, Any]) -> Optional[int]:
    for anchor in obj.get("sourceAnchors") or []:
        line = anchor.get("markdownStartLine")
        if line:
            return int(line)
    return None


def query_target(summary: dict[str, Any], needle: str) -> list[dict[str, Any]]:
    """关系查询：本文内部目标（表/图/式/条款）被哪些条款引用（用户 2026-09-29 裁定 ①）。

    按 ``resolvedTargetId`` / ``rawTarget``（归一形态）/ ``resolvedClause``（编号）匹配，
    支持 ``表1``、``Figure_1``、``GB_T_1.1-2020#Table_1``、``1`` 等写法。
    """
    wanted = _normalised(str(needle or "")).lower()
    hits: list[dict[str, Any]] = []
    for kind, entries in (summary.get("internalReferences") or {}).items():
        for entry in entries:
            candidates = {
                _normalised(str(entry.get("raw") or "")).lower(),
                _normalised(str(entry.get("number") or "")).lower(),
                str(entry.get("target_id") or "").lower(),
            }
            if wanted and wanted in candidates:
                hits.append({"kind": kind, **entry})
    return hits


def format_target_view(summary: dict[str, Any], targets: list[str]) -> str:
    """目标被引查询结果（文本）：「表1/图2/式(3)」分别被哪些条款引用。"""
    lines: list[str] = []
    kind_names = {"internalTable": "表", "internalFigure": "图", "internalFormula": "式", "internalClause": "条款"}
    for target in targets:
        hits = query_target(summary, target)
        lines.append(f"目标 {target}：被引用 {len(hits)} 处")
        for hit in hits:
            where = f"{hit['clause']}" if hit.get("clause") else "—"
            if hit.get("element_id"):
                where += f"（元素 {hit['element_id']}）"
            flag = "" if hit.get("resolved") else "  ← 目标未在本文件注册表中找到"
            lines.append(
                f"  {kind_names.get(hit['kind'], hit['kind'])} {hit.get('raw') or hit.get('number')}"
                f"｜出现于 {where}｜引用性质 {'规范性' if hit.get('nature') == 'normative' else '资料性'}"
                f"｜目标 {hit.get('target_id') or '—'}{flag}"
            )
    return "\n".join(lines)


def format_summary(
    summary: dict[str, Any],
    *,
    standard: Optional[str] = None,
    include_informative: bool = False,
    include_internal: bool = True,
    include_uncited: bool = True,
) -> str:
    """六元组视图 → 纯文本清单（CLI 输出；默认只列规范性引用）。"""
    lines: list[str] = []
    head = str(summary.get("standardNumber") or summary.get("standardId") or "")
    if summary.get("standardTitle"):
        head = f"{head} {summary['standardTitle']}"
    lines.append(head)
    selected = summary["references"]
    if standard:
        needle = _normalised(standard).lower()
        selected = [
            entry
            for entry in selected
            if needle in _normalised(entry["standard_id"]).lower()
            or needle in _normalised(entry["standard_number"] or "").lower()
        ]
    normative = [entry for entry in selected if entry["nature"] == "normative"]
    informative = [entry for entry in selected if entry["nature"] != "normative"]
    shown = selected if include_informative else normative
    lines.append(
        f"规范性引用文件：{len(normative)} 条"
        + (f"（文档内另有 {len(informative)} 条资料性引用）" if informative else "")
    )
    if not shown:
        lines.append("  （无）")
    for entry in shown:
        lines.extend(_format_entry(entry))
    if include_informative and informative:
        lines.append("")
        lines.append(f"资料性引用（{len(informative)} 条，不应列入第 2 章清单，GB/T 1.1-2020 9.5.4.2.2）：")
        for entry in informative:
            lines.extend(_format_entry(entry))
    if include_internal and summary.get("internalReferences"):
        lines.append("")
        lines.append(
            f"本文内部引用点：{summary['internalCount']} 处"
            f"（其中 {summary['unresolvedInternalCount']} 处未在本文件注册表中找到同编号对象）"
        )
        kind_names = {
            "internalTable": "表",
            "internalFigure": "图",
            "internalFormula": "公式",
            "internalClause": "条款",
        }
        for kind, entries in summary["internalReferences"].items():
            for entry in entries:
                flag = "" if entry["resolved"] else "  ← 未解析"
                target = entry.get("raw") or f"{kind_names.get(kind, kind)}{entry['number']}"
                line = f"  {target}｜出现于 {entry['clause']}"
                if entry.get("element_id"):
                    line += f"（元素 {entry['element_id']}）"
                if entry["target_id"]:
                    line += f"｜目标 {entry['target_id']}"
                lines.append(line + flag)
    if include_uncited and summary.get("unlistedCitations"):
        lines.append("")
        lines.append(
            f"待复核：正文规范性引用但清单未列出的 {summary['unlistedCitationCount']} 个文件"
            "（GB/T 1.1-2020 8.6.3.1；已在合规报告中记为 GBT-C06/normative-citation-not-listed）："
        )
        for entry in summary["unlistedCitations"]:
            first = (entry.get("occurrences") or [{}])[0]
            lines.append(
                f"  {entry.get('standard_id') or entry['base_id']}"
                f"｜首现 {first.get('clause') or '—'}（元素 {first.get('element_id') or '—'}）"
                f"｜原文 “{first.get('raw') or entry.get('raw') or ''}”"
                f"｜共 {len(entry.get('occurrences') or [])} 处"
            )
    if include_uncited and summary.get("uncitedListEntries"):
        lines.append("")
        lines.append(
            f"待复核：清单列出的 {summary['uncitedListEntryCount']} 个文件在正文中没有引用点"
            "（GB/T 1.1-2020 8.6.3.1；已在合规报告中记为 GBT-C06/reference-entry-not-cited）："
        )
        for entry in summary["uncitedListEntries"]:
            line = f"  {entry.get('standard_number') or entry['standard_id']}"
            if entry.get("title"):
                line += f" {entry['title']}"
            if entry.get("element_id"):
                line += f"｜清单元素 {entry['element_id']}"
            similar = entry.get("similar_citations") or []
            if similar:
                line += "；正文同顺序号引用：" + "、".join(
                    f"{item.get('raw') or item['standard_id']}"
                    + (f"（{item['clause']}）" if item.get("clause") else "")
                    for item in similar[:3]
                )
            lines.append(line)
    return "\n".join(lines)


def _format_entry(entry: dict[str, Any]) -> list[str]:
    nature = "规范性" if entry["nature"] == "normative" else "资料性"
    type_text = {"dated": "注日期", "undated": "不注日期", "all_parts": "所有部分"}.get(
        str(entry["reference_type"]), str(entry["reference_type"])
    )
    version = f" 版本 {entry['version']}" if entry["version"] else ""
    title = f" {entry['title']}" if entry["title"] else ""
    lines = [
        "",
        f"- {entry['standard_number'] or entry['standard_id']}{version}{title}",
        f"    标识 {entry['standard_id']}｜引用类型 {type_text}｜引用性质 {nature}",
    ]
    if entry["cited_clauses"]:
        lines.append(f"    被引条款 {'、'.join(sorted(set(entry['cited_clauses'])))}")
    occurrences = entry["source_clauses"]
    lines.append(f"    出现条款 {len(occurrences)} 处：")
    for occurrence in occurrences[:20]:
        line = f"      · {occurrence['clause'] or '(无条款号)'}｜{occurrence['nature']}"
        line += f"｜{occurrence['element_id']}"
        lines.append(line)
    if len(occurrences) > 20:
        lines.append(f"      · …另有 {len(occurrences) - 20} 处")
    return lines
