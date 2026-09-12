"""kg_viewer 文档详情：从 SSIR 载荷派生**文档级**元数据与分层展示结构。

供 ``/api/doc/<doc_id>/detail`` 使用。SSIR 载荷仍是唯一真源，本模块只读派生、不改写：
把元数据（发布日期/实施日期/代替/ICS/CCS…）、前言里的机构信息（提出/归口/起草单位/
主要起草人）、术语条目（条数 + 逐条定义）与标准要素（GB/T 1.1-2020 表3 +
`标准要素完整清单.md` 的 GBT-E01~E14）整理成分层结构，前端以可折叠弹窗逐层展开。

纯函数、无 Flask 依赖（便于单测）。
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Optional

# 标准要素清单（GBT-E01~E14，与仓库根 标准要素完整清单.md §2 对齐）。
# code / 名称 / 性质（必备·可选）
ELEMENT_DEFS: list[tuple[str, str, str]] = [
    ("GBT-E01", "封面", "必备"),
    ("GBT-E02", "目次", "可选"),
    ("GBT-E03", "前言", "必备"),
    ("GBT-E04", "引言", "可选"),
    ("GBT-E05", "范围（第1章）", "必备"),
    ("GBT-E06", "规范性引用文件（第2章）", "必备/可选（无则写明无）"),
    ("GBT-E07", "术语和定义", "必备/可选"),
    ("GBT-E08", "符号和缩略语", "可选"),
    ("GBT-E09", "分类和编码/系统构成", "可选"),
    ("GBT-E10", "总体原则和/或总体要求", "可选"),
    ("GBT-E11", "核心技术要素", "必备"),
    ("GBT-E12", "其他技术要素", "可选"),
    ("GBT-E13", "参考文献", "可选"),
    ("GBT-E14", "索引", "可选"),
]

# 文档元数据清单（GBT-M01~M14，标准要素完整清单.md §1）：供详情页「元数据核对」。
METADATA_DEFS: list[tuple[str, str, str]] = [
    ("GBT-M01", "标准文献编号", "必备"),
    ("GBT-M02", "标准名称（中文）", "必备"),
    ("GBT-M03", "英文译名", "必备（国家标准）"),
    ("GBT-M04", "发布机构", "必备"),
    ("GBT-M05", "发布日期", "必备"),
    ("GBT-M06", "实施日期", "必备"),
    ("GBT-M07", "ICS 分类号", "必备"),
    ("GBT-M08", "CCS 分类号", "必备"),
    ("GBT-M09", "被代替文件编号", "可选（有则必标）"),
    ("GBT-M10", "一致性程度标识", "可选"),
    ("GBT-M11", "归口单位／技术委员会", "必备"),
    ("GBT-M12", "标准状态", "必备"),
    ("GBT-M13", "技术领域／关键词", "可选"),
    ("GBT-M14", "国际对应关系", "可选"),
]

_PROPOSE_RE = re.compile(r"本文件由([^。]{2,80}?)提出(?:并归口)?")
_SECRETARIAT_RE = re.compile(r"本文件由([^。]{2,80}?)归口")
_DRAFT_UNITS_RE = re.compile(r"本文件起草单位[：:]\s*(.+?)(?:。|$)", re.S)
_DRAFTERS_RE = re.compile(r"本文件主要起草人[：:]\s*(.+?)(?:。|$)", re.S)
_SPLIT_UNITS_RE = re.compile(r"[、，,;；]")

# 顶层要素 title 归一（去空白）→ 清单代码
_BACK_MATTER = {"参考文献": ("GBT-E13", "参考文献", "可选"), "索引": ("GBT-E14", "索引", "可选")}
_FRONT_MATTER = {"目次": ("GBT-E02", "目次", "可选"), "目录": ("GBT-E02", "目次", "可选"),
                 "前言": ("GBT-E03", "前言", "必备"), "引言": ("GBT-E04", "引言", "可选")}


def _norm(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or ""))


def _iter_nodes(root: dict) -> Iterable[tuple[dict, int]]:
    yield root, 0
    for child in root.get("children") or []:
        yield from _iter_nodes(child)


def _anchor_line(node: dict) -> Optional[int]:
    for anchor in node.get("sourceAnchors") or []:
        if anchor.get("anchorType") == "markdown":
            line = anchor.get("markdownStartLine")
            return int(line) if line is not None else None
    return None


def _term_definition(node: dict) -> str:
    fallback = ""
    for content in node.get("contentElements") or []:
        if content.get("presentationType") != "paragraph":
            continue
        text = str(content.get("textContent") or "").strip()
        if not text:
            continue
        if "termDefinition" in (content.get("semanticTypes") or []):
            return text
        fallback = fallback or text
    return fallback


def _term_items(root: dict) -> list[dict]:
    items: list[dict] = []
    for node, _depth in _iter_nodes(root):
        term = str(node.get("term") or "").strip()
        if not term:
            continue
        items.append({
            "node_id": node.get("id"),
            "number": node.get("number"),
            "term": term,
            "english": str(node.get("englishTerm") or "").strip(),
            "definition": _term_definition(node),
            "md_line": _anchor_line(node),
        })
    items.sort(key=lambda item: [int(part) for part in re.findall(r"\d+", str(item.get("number") or "0"))] or [0])
    return items


def _front_matter_info(root: dict) -> dict:
    """从「前言」正文提取提出/归口/起草单位/主要起草人（标准正文没有这些元数据字段）。"""
    text = ""
    for node, _depth in _iter_nodes(root):
        if _norm(node.get("title")) == "前言":
            text = "\n".join(str(ce.get("textContent") or "") for ce in node.get("contentElements") or [])
            break
    flat = re.sub(r"\s+", "", text)
    info: dict[str, Any] = {"proposing": "", "secretariat": "", "drafting_units": [], "drafters": []}
    joint = re.search(r"本文件由(.{2,80}?)提出并归口", flat)
    if joint:
        info["proposing"] = info["secretariat"] = joint.group(1).strip()
    else:
        match = _PROPOSE_RE.search(flat)
        if match:
            info["proposing"] = match.group(1).strip()
        match = _SECRETARIAT_RE.search(flat)
        if match:
            info["secretariat"] = match.group(1).strip()
    match = _DRAFT_UNITS_RE.search(flat)
    if match:
        info["drafting_units"] = [unit for unit in _SPLIT_UNITS_RE.split(match.group(1).strip()) if unit]
    match = _DRAFTERS_RE.search(flat)
    if match:
        info["drafters"] = [name for name in _SPLIT_UNITS_RE.split(match.group(1).strip()) if name]
    return info


def _annex_status(title: str) -> str:
    if "规范性" in title:
        return "规范性"
    if "资料性" in title:
        return "资料性"
    return ""


def _classify_top(node: dict) -> dict:
    """顶层结构节点 → 要素分类（清单代码 + 名称 + 性质）。"""
    number = str(node.get("number") or "").strip()
    title = str(node.get("title") or "").strip()
    node_type = node.get("nodeType")
    key = _norm(title)
    if node_type == "annex":
        status = _annex_status(title)
        return {"code": f"附录{number}", "name": f"附录 {number}（{status}）".rstrip(), "nature": status or "附录"}
    if key in _FRONT_MATTER:
        code, name, nature = _FRONT_MATTER[key]
        return {"code": code, "name": name, "nature": nature}
    if key in _BACK_MATTER:
        code, name, nature = _BACK_MATTER[key]
        return {"code": code, "name": name, "nature": nature}
    if number == "1":
        return {"code": "GBT-E05", "name": "范围", "nature": "必备"}
    if number == "2":
        return {"code": "GBT-E06", "name": "规范性引用文件", "nature": "必备/可选"}
    if number == "3" or "术语" in key:
        return {"code": "GBT-E07", "name": "术语和定义", "nature": "必备/可选"}
    if "符号" in key or "缩略语" in key:
        return {"code": "GBT-E08", "name": "符号和缩略语", "nature": "可选"}
    if any(token in key for token in ("分类", "编码", "系统构成")):
        return {"code": "GBT-E09", "name": "分类和编码/系统构成", "nature": "可选"}
    if "总体" in key:
        return {"code": "GBT-E10", "name": "总体原则和/或总体要求", "nature": "可选"}
    if title:
        return {"code": "章", "name": title, "nature": "规范性"}
    return {"code": "其他", "name": number or node_type or "未命名", "nature": ""}


def _top_items(root: dict) -> list[dict]:
    items: list[dict] = []
    for node in root.get("children") or []:
        classified = _classify_top(node)
        children = node.get("children") or []
        items.append({
            "node_id": node.get("id"),
            "node_type": node.get("nodeType"),
            "number": node.get("number"),
            "title": node.get("title"),
            "code": classified["code"],
            "name": classified["name"],
            "nature": classified["nature"],
            "child_count": len(children),
            "ce_count": len(node.get("contentElements") or []),
            "md_line": _anchor_line(node),
        })
    return items


def _group_for(item: dict) -> str:
    if item["code"] in ("GBT-E02", "GBT-E03", "GBT-E04"):
        return "front"
    if item["code"].startswith("附录"):
        return "annex"
    if item["code"] in ("GBT-E13", "GBT-E14"):
        return "back"
    return "body"


def _elements(root: dict) -> dict:
    items = _top_items(root)
    groups = [
        {"key": "front", "label": "前置要素（目次/前言/引言）", "items": []},
        {"key": "body", "label": "主体要素（章）", "items": []},
        {"key": "annex", "label": "附录", "items": []},
        {"key": "back", "label": "文后要素（参考文献/索引）", "items": []},
    ]
    index = {group["key"]: group for group in groups}
    for item in items:
        index[_group_for(item)]["items"].append(item)
    return {"groups": groups, "items": items}


def _coverage(elements: dict, metadata_ok: dict) -> dict:
    present_codes = {item["code"] for item in elements["items"]}
    body_chapters = [item for item in elements["items"] if item["code"] == "章"]
    element_rows = []
    for code, name, nature in ELEMENT_DEFS:
        if code == "GBT-E01":
            present = bool(metadata_ok.get("封面"))
            note = "由元数据派生（无独立结构节点）" if present else "未识别"
        elif code in ("GBT-E11", "GBT-E12"):
            present = bool(body_chapters)
            note = ("见主体章节 " + "、".join(str(item["number"] or item["name"]) for item in body_chapters) +
                    "（具体归类取决于文件功能类型）") if present else "未识别"
        else:
            present = code in present_codes
            note = ""
        element_rows.append({"code": code, "name": name, "nature": nature, "present": present, "note": note})

    metadata_rows = []
    for code, name, nature in METADATA_DEFS:
        present = bool(metadata_ok.get(code))
        metadata_rows.append({"code": code, "name": name, "nature": nature, "present": present})
    return {"elements": element_rows, "metadata": metadata_rows}


def build_document_detail(payload: dict) -> dict:
    """SSIR 载荷 → 文档详情分层结构（身份/日期/关系/机构/术语/要素/统计/清单核对）。"""
    metadata = payload.get("metadata") or {}
    standard = metadata.get("standard") or {}
    common = metadata.get("common") or {}
    root = payload.get("structuralRoot") or {}
    nodes = [node for node, _depth in _iter_nodes(root)]

    terms = _term_items(root)
    orgs = _front_matter_info(root)
    elements = _elements(root)

    identity = {
        "standard_number": standard.get("standardNumber") or common.get("documentIdentifier") or "",
        "chinese_title": standard.get("chineseTitle") or common.get("title") or "",
        "title_en": common.get("titleEn") or "",
        "document_type": payload.get("documentType") or "",
        "language": common.get("language") or "",
        "ics": standard.get("ics") or "",
        "ccs": standard.get("ccs") or "",
    }
    dates = {
        "publication_date": common.get("publicationDate") or "",
        "effective_date": common.get("effectiveDate") or "",
    }
    relations = {
        "replaces": standard.get("replaces") or "",
        "conformity_statement": common.get("conformityStatement") or "",
        "issuer": common.get("issuer") or "",
    }
    organizations = {
        "issuer": common.get("issuer") or "",
        "proposing": orgs["proposing"],
        "secretariat": orgs["secretariat"],
        "drafting_units": orgs["drafting_units"],
        "drafters": orgs["drafters"],
    }
    stats = {
        "nodes": len(nodes),
        "clauses": sum(1 for node in nodes if node.get("nodeType") in ("section", "clause", "subClause", "item", "subItem")),
        "chapters": sum(1 for node in nodes if node.get("nodeType") == "section"),
        "annexes": sum(1 for node in nodes if node.get("nodeType") == "annex"),
        "annex_sections": sum(1 for node in nodes if node.get("nodeType") == "annexSection"),
        "document_blocks": sum(1 for node in nodes if node.get("nodeType") == "documentBlock"),
        "content_elements": sum(len(node.get("contentElements") or []) for node in nodes),
        "terms": len(terms),
        "tables": len(payload.get("tables") or []),
        "figures": len(payload.get("figures") or []),
        "formulas": len(payload.get("formulas") or []),
    }

    metadata_ok = {
        "封面": bool(identity["standard_number"] or identity["chinese_title"]),
        "GBT-M01": identity["standard_number"],
        "GBT-M02": identity["chinese_title"],
        "GBT-M03": identity["title_en"],
        "GBT-M04": relations["issuer"],
        "GBT-M05": dates["publication_date"],
        "GBT-M06": dates["effective_date"],
        "GBT-M07": identity["ics"],
        "GBT-M08": identity["ccs"],
        "GBT-M09": relations["replaces"],
        "GBT-M10": relations["conformity_statement"],
        "GBT-M11": organizations["secretariat"] or organizations["proposing"],
        "GBT-M12": bool(identity["standard_number"]),
        "GBT-M13": "",
        "GBT-M14": relations["conformity_statement"],
    }
    return {
        "doc_id": payload.get("id") or "",
        "identity": identity,
        "dates": dates,
        "relations": relations,
        "organizations": organizations,
        "terms": {"count": len(terms), "items": terms},
        "elements": elements,
        "stats": stats,
        "coverage": _coverage(elements, metadata_ok),
    }
