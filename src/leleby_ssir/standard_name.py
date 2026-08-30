"""标准名称解析 —— 识别标准类型与标准化主对象（纯规则引擎，非 LLM）。

设计原则（源自 2026-08 确认的《关于标准名称的判断程序》设计稿）：
    「后缀定类型，中缀定主语，前缀定修饰，含"用"定场合」

本模块是 lookWhy 流水线中"名称 → 类型/主对象"的单一事实源：

* 标准类型（standard_type）：按 GB/T 20001 系列功能类型归类 ——
  方法标准 / 术语标准 / 分类标准 / 规程标准 / 指南标准 / 安全标准 /
  产品标准（规范·技术条件） / 其他标准。
* 标准化主对象（subject）：名称描述的核心技术名词（长词优先，词库外兜底
  取最后一个实词），如「三相异步电动机试验方法」→ 三相异步电动机。
* 应用场合（application）：主对象的使用场景（XX用），如「船用」。
* 修饰词（modifier）：剥离类型词、主词、应用场合后的剩余描述特征。

规则对应: GBT-N01（名称与功能类型一致性）、GBT-N02（标准化主对象识别）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# 标准类型规则（按优先级从高到低；复合词必须排在简单词之前）
# ---------------------------------------------------------------------------

# 方法标准：含"试验/测定/测试/校准/计算/测量/检验 + 方法/法"
_METHOD_RE = re.compile(
    r"(试验方法|测定方法|测试方法|校准方法|计算方法|测量方法|检验方法|"
    r"试验规范|性能试验|试验规程|测试法|试验确定|检定规程)"
)

# 术语标准
_TERMINOLOGY_RE = re.compile(r"(术语|词汇|定义)")

# 分类标准
_CLASSIFICATION_RE = re.compile(r"(分类|编码|代号|命名方法|型号命名|型号编制)")

# 规程标准（试验规程归方法标准，此处只保留独立规程）
_PROCEDURE_RE = re.compile(r"规程")

# 指南标准
_GUIDE_RE = re.compile(r"(指南|导则)")

# 安全标准：安全要求/安全规范/安全通用要求/安全技术规范 等
_SAFETY_RE = re.compile(r"安全")

# 产品标准（规范/技术条件/通则/总则/限值/要求）
_PRODUCT_RE = re.compile(
    r"(通用技术条件|通用技术规范|技术条件|技术规范|总规范|通用规范|"
    r"规范|通则|总则|限值|分级|基本技术要求|安全技术要求|要求)"
)

# 名称中不应出现的干扰词（作用于整个标题的排除判断）
_EXCLUDE_METHOD = re.compile(r"(指南|导则)")  # 应用导则 → 指南标准而非方法


@dataclass(slots=True)
class StandardNameInfo:
    """标准名称解析结果。"""

    title: str
    standard_type: str = "其他标准"
    subject: str = ""
    modifier: str = ""
    application: str = ""
    type_basis: str = ""  # 判定类型的命中关键词（供核查/调试）
    confidence: str = "low"  # high | medium | low

    def to_dict(self) -> dict[str, str]:
        return {
            "title": self.title,
            "standardType": self.standard_type,
            "subject": self.subject,
            "modifier": self.modifier,
            "application": self.application,
            "typeBasis": self.type_basis,
            "confidence": self.confidence,
        }


# ---------------------------------------------------------------------------
# 标准化主对象词库（按长度降序匹配，防止短词误吞长词）
# 来源：376 条标准名称清单中的高频核心技术名词（电机/泵/传感器三大族 + 附件）
# ---------------------------------------------------------------------------
_SUBJECT_LEXICON: tuple[str, ...] = tuple(
    sorted(
        {
            # --- 电机族 ---
            "三相异步电动机", "单相异步电动机", "永磁同步电动机", "三相同步电机",
            "单相同步电机", "变频调速三相异步电动机", "绕线转子三相异步电动机",
            "电磁制动三相异步电动机", "双速三相异步电动机", "多速三相异步电动机",
            "异步电动机", "同步电动机", "伺服电动机", "步进电动机", "永磁电动机",
            "永磁无刷电动机", "磁滞同步电动机", "感应电动机", "直流力矩电动机",
            "力矩电动机", "测速发电机", "直流电机", "交流电机", "旋转电机",
            "控制电机", "微电机", "小功率电动机", "电动机", "电机",
            "隐极同步发电机", "同步发电机", "发电机",
            "交流伺服系统", "励磁系统",
            # --- 泵族 ---
            "水环真空泵", "回转容积泵", "离心泵", "混流泵", "轴流泵", "螺杆泵",
            "往复泵", "回转泵", "转子泵", "计量泵", "真空泵", "水泵", "泵",
            # --- 传感器/检测器件族 ---
            "压力传感器", "温度传感器", "光纤传感器", "振动传感器", "雨量传感器",
            "电流传感器", "接近传感器", "加速度计", "地震计", "传感器",
            "电容式湿敏元件", "湿敏元件", "霍尔元件", "敏感元件", "元件",
            # --- 电器/开关/控制族 ---
            "低压开关设备", "开关设备", "可编程序控制器", "控制器", "换向器",
            "集电环", "移相器", "旋转变压器", "自整角机", "减速器", "压缩机",
            "制冷压缩机", "气体分析器", "电化学分析器", "分析器", "摄像机",
            "应用电视摄像机", "坐标测量机", "测量系统", "电气设备", "电器设备",
            "绝缘结构", "定子绕组", "绕组", "线圈", "联接装置",
            # --- 通用对象 ---
            "仪器", "设备", "装置", "系统", "机",
            # --- 元标准（编写/起草规则类文件自身） ---
            "标准编写规则", "编写规则", "起草规则", "标准化文件", "文件",
        },
        key=len,
        reverse=True,
    )
)

# 需从标题开头剥离的标准号/系列前缀（如 "YBZE、YBZSE系列" 中的系列名）
_SERIES_PREFIX_RE = re.compile(
    r"^(?:[A-Z]{1,5}系列|[A-Z]{2,6}(?:、[A-Z]{2,6})+系列)"
)

# 应用场合：XX用（长度 1..6 的汉字，避免误吞"作用/应用"）
_APPLICATION_RE = re.compile(r"([\u4e00-\u9fa5]{1,6})用")

# 需剔除的尾部类型词（清洗出纯粹的主语描述串）
_TAIL_REMOVE_RE = re.compile(
    r"(通用技术条件|通用技术规范|技术条件|技术规范|总规范|通用规范|安全技术规范|"
    r"基本技术要求|技术条件|技术要求|安全要求|试验方法|测定方法|测试方法|"
    r"校准方法|计算方法|测量方法|检验方法|试验规范|性能试验|试验规程|"
    r"术语|定义|词汇|分类|编码|代号|命名方法|型号命名|型号编制|"
    r"通则|总则|规范|规程|指南|导则|分级|限值|尺寸|效率|性能|"
    r"特殊要求|测定方法及限值|测量方法及评定|测量、评定及限值)$"
)

# 兜底取主词时视为"核心名词"的常见结尾（用于把长描述切成实词）
_NOUN_TAIL = (
    "电动机", "电机", "发电机", "传感器", "泵", "机", "器", "仪", "装置",
    "系统", "绕组", "元件", "结构", "接口", "设备", "性能", "要求", "方法",
    "规范", "规程", "指南", "导则", "分类", "代号", "符号", "标志",
)

# 应用场合候选词（常见场景，用于验证"XX用"提取结果）
_APPLICATION_KNOWN = {
    "船用", "洗衣机用", "起重用", "冶金用", "辊道用", "纺织用", "家用",
    "电梯用", "制冷用", "电子用", "拖拉机用", "农用", "汽车用", "风机用",
    "压缩机用", "泵用", "微型用",
}


def classify_standard_type(title: str) -> tuple[str, str]:
    """识别标准功能类型，返回 (类型, 命中关键词)。

    优先级: 方法 > 术语 > 分类 > 规程 > 指南 > 安全 > 产品 > 其他。
    复合规则先行（如"试验方法"先于"方法"），避免误判。
    """
    if not title:
        return "其他标准", ""

    # 方法标准（含"试验规程"——如 GB/T 17948 系列"试验规程 热评定和分级"）
    method_m = _METHOD_RE.search(title)
    if method_m and not _EXCLUDE_METHOD.search(title):
        # "性能试验"可能出现在安全标准里，但清单中未见，直接归方法
        return "方法标准", method_m.group(0)

    term_m = _TERMINOLOGY_RE.search(title)
    if term_m:
        return "术语标准", term_m.group(0)

    class_m = _CLASSIFICATION_RE.search(title)
    if class_m:
        return "分类标准", class_m.group(0)

    if _PROCEDURE_RE.search(title):
        return "规程标准", "规程"

    guide_m = _GUIDE_RE.search(title)
    if guide_m:
        return "指南标准", guide_m.group(0)

    if _SAFETY_RE.search(title):
        return "安全标准", "安全"

    product_m = _PRODUCT_RE.search(title)
    if product_m:
        return "产品标准", product_m.group(0)

    return "其他标准", ""


def _extract_subject(pure_part: str) -> tuple[str, str]:
    """从纯主语串提取标准化主对象，返回 (主词, 剩余串)。

    长词优先；未命中词库时按名词结尾切最后一个实词兜底。
    """
    for word in _SUBJECT_LEXICON:
        if word in pure_part:
            return word, pure_part.replace(word, "", 1)
    # 兜底：按常见名词结尾切分（取最后一段）
    for tail in _NOUN_TAIL:
        idx = pure_part.rfind(tail)
        if idx > 0:
            return pure_part[idx:], pure_part[:idx]
    return pure_part, ""


def parse_standard_name(title: str) -> StandardNameInfo:
    """解析标准名称 → 标准类型 + 标准化主对象 + 应用场合 + 修饰词。"""
    title = (title or "").strip()
    if not title:
        return StandardNameInfo(title="")

    # Step 1: 清洗 —— 剥离"第X部分"后的具体名称
    core = title
    if "第" in core and ("部分" in core or "：" in core or ":" in core):
        # 仅当冒号后还有实质内容时取冒号后的部分
        for sep in ("：", ":"):
            if sep in core:
                after = core.split(sep, 1)[1].strip()
                if after and not after.startswith("第"):
                    core = after
                break

    # Step 2: 标准类型（基于完整标题判断，类别词可能在清洗时被剥离）
    standard_type, basis = classify_standard_type(title)

    # Step 3: 剥离尾部类型词 → 纯主语串
    pure = _TAIL_REMOVE_RE.sub("", core).strip()
    if not pure:
        pure = core

    # Step 4: 应用场合（XX用）—— 先于主词提取，因为场景词紧邻主词之前
    # （"船用旋转电机"、"微电机用齿轮减速器"）。用 finditer 逐个候选尝试，
    # 拒绝"通用/作用/应用/使用"等干扰词（candidate 以 通/作/应/使/采/利/运
    # 结尾即视为干扰）。裁剪：去开头"系列/型号"、取"X式"后、超长并列取末段。
    application = ""
    _APP_FALSE_ENDINGS = ("通", "作", "应", "使", "采", "利", "运")
    for app_m in re.finditer(r"([\u4e00-\u9fa5]+)用", pure):
        candidate = app_m.group(1)
        # "X专用"（如"纺织专用"）→ 去掉尾部"专"还原为场景"纺织用"；
        # 但"…损耗的专用"这类含"的"的长串不是场景。
        if candidate.endswith("专"):
            candidate = candidate[:-1]
            if "的" in candidate or len(candidate) > 6:
                continue
        candidate = re.sub(r"^(?:系列|型号)", "", candidate)
        if "式" in candidate:
            candidate = candidate.split("式")[-1]
        if len(candidate) > 6:
            candidate = re.split(r"[和与、]", candidate)[-1]
        if not candidate or candidate.endswith(_APP_FALSE_ENDINGS):
            continue
        full = candidate + "用"
        application = full
        pure = pure.replace(full, "", 1)
        break

    # Step 5: 主对象（长词优先；提取失败或仅得兜底词时回退冒号前主标题重试）
    subject, remainder = _extract_subject(pure)
    if not subject or subject not in _SUBJECT_LEXICON:
        head = title.split("：", 1)[0].split(":", 1)[0].strip()
        if head and head != title:
            subject, remainder = _extract_subject(_TAIL_REMOVE_RE.sub("", head).strip())
            if not subject or subject == head:
                subject, remainder = "", ""
    remainder = remainder.strip()

    # Step 6: 修饰词（清理分隔符与"第X部分"残留）
    modifier = re.sub(r"[、，,．.。\s]+", "、", remainder).strip("、")
    modifier = re.sub(r"第\d+(?:\.\d+)?部分[、]?", "", modifier).strip("、")
    modifier = modifier.strip("的、")
    if modifier == subject:
        modifier = ""

    # Step 7: 置信度
    confidence = "high" if subject else "low"
    if standard_type == "其他标准" and not subject:
        confidence = "low"
    elif basis:
        confidence = "high" if subject else "medium"

    return StandardNameInfo(
        title=title,
        standard_type=standard_type,
        subject=subject,
        modifier=modifier,
        application=application,
        type_basis=basis,
        confidence=confidence,
    )


def name_matches_type(info: StandardNameInfo) -> bool:
    """核查标准名称与其功能类型是否一致（GBT-N01）。

    规则（GB/T 1.1-2020 命名要求）：
    - 方法标准名称应含"试验/测定/测试/校准/计算/测量/检验 + 方法/法/规程"；
    - 术语标准应含"术语/定义/词汇"；
    - 分类标准应含"分类/编码/命名/型号"；
    - 规程标准应含"规程"；
    - 指南标准应含"指南/导则"；
    - 安全标准应含"安全"；
    - 产品标准应含"条件/规范/通则/总则/要求/限值"等。
    """
    title = info.title
    t = info.standard_type
    if t == "方法标准":
        return bool(re.search(r"(试验|测定|测试|校准|计算|测量|检验|试验方法|测定方法|测试方法)", title))
    if t == "术语标准":
        return bool(re.search(r"(术语|定义|词汇)", title))
    if t == "分类标准":
        return bool(re.search(r"(分类|编码|命名|型号)", title))
    if t == "规程标准":
        return bool(re.search(r"规程", title))
    if t == "指南标准":
        return bool(re.search(r"(指南|导则)", title))
    if t == "安全标准":
        return bool(re.search(r"安全", title))
    if t == "产品标准":
        return bool(re.search(r"(条件|规范|通则|总则|要求|限值|分级)", title))
    return True  # 其他标准不做一致性断言
