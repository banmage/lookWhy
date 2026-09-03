"""SSIR → kg.json 图切片映射器（知识图谱阶段 0/1，P1c）。

契约骨架见 docs/semantic_Stage/lookWhy 知识图谱阶段规划与存储选型建议 v0.1.md §3：
- 节点主键直接复用 SSIR 稳定 URI（不另造 ID）；
- 每个图谱节点携带 anchor（markdown 源行/路径/sourceFileId），满足"两步内得到
  (文档 ID, 条款号, canonical.md 行号, 源文件)"验收；
- 只做从 SSIR **无损派生**的结构/内容/术语/表图公式节点与边，零语义猜测；
  Requirement/Constraint 语义提升（阶段 3）不在此映射器范围。
- 文件 SSIR JSON 仍是唯一真源；kg.json 是"真源的可复现视图"（投影），可整体重建。

节点 kind（对应 Standard Ontology v1.5 / NSP 语义，供前端着色/过滤）：
  Document / DocumentBlock / Clause(structuralKind=section|clause|subClause) /
  Annex / ContentUnit(structuralKind=item|subItem) / ContentUnit(kind=CE,
  presentationType=paragraph|list|note|quote) / Term / Table / Figure / Formula。

边类型：
  HAS_CHILD        结构树父子（节点→子节点）
  CONTAINS_ELEMENT 结构节点→内容元素（CE 节点或 registry 表/图/公式实体）
  TERM_DEFINED_IN  Term→其定义所在结构节点
跨文档引用（CITES/REPLACES 真边）留给阶段 P2（需双侧文档在场）；本映射器先以
document.references 数组（standardNumber+出现条款+md 行）落盘，供 P2 生成边。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

KG_VERSION = "0.1"
KG_SCHEMA_RELPATH = "kg.schema.json"

# SSIR nodeType → 图 kind
_STRUCTURAL_KIND = {
    "document": "Document",
    "documentBlock": "DocumentBlock",
    "section": "Clause",
    "clause": "Clause",
    "subClause": "Clause",
    "annex": "Annex",
    "item": "ContentUnit",
    "subItem": "ContentUnit",
}

# 不单独建 CE 节点、直接由父节点连向 registry 实体的 presentationType
_REF_PRESENTATION = {"table": "Table", "figure": "Figure", "formula": "Formula"}

# 作为独立 CE 节点入图的 presentationType（段落/注/列表/引用等正文内容）
_CE_PRESENTATION = ("paragraph", "list", "note", "quote", "blockquote")

_CE_TEXT_LIMIT = 400  # CE 节点 text 预览截断长度（全文仍在 SSIR 真源）

_RE_SPACES = re.compile(r"\s+")


def _anchor_of(item: dict) -> Optional[dict]:
    """取元素第一个 markdown 型 sourceAnchor 的溯源字段子集。"""
    for a in item.get("sourceAnchors") or []:
        if a.get("anchorType") == "markdown":
            return {
                "markdownStartLine": a.get("markdownStartLine"),
                "markdownEndLine": a.get("markdownEndLine"),
                "markdownNodePath": a.get("markdownNodePath"),
                "sourceFileId": a.get("sourceFileId"),
            }
    return None


def _first_anchor_line(item: dict) -> Optional[int]:
    for a in item.get("sourceAnchors") or []:
        if a.get("anchorType") == "markdown" and a.get("markdownStartLine") is not None:
            return a["markdownStartLine"]
    return None


def _node_base(node: dict, kind: str, anchor: Optional[dict]) -> dict:
    out: dict[str, Any] = {"id": node["id"], "kind": kind}
    if anchor:
        out["anchor"] = anchor
    return out


def _norm_standard_number(raw: str) -> str:
    """引用标准号归一：去空白、一字/半字线→连字符（供跨文档比对）。"""
    return _RE_SPACES.sub("", raw).replace("—", "-").replace("–", "-")


def _standards_regex():
    """复用 compliance 的引用标准号正则（已覆盖 30+ 前缀），懒加载避免重依赖。"""
    try:
        from leleby_ssir import compliance  # noqa: PLC0415

        return compliance._STANDARD_NUMBER_RE
    except Exception:  # pragma: no cover - 兜底
        return re.compile(
            r"(?:GB(?:/T|/Z|/J)?|JB/T|QB/T|HG/T|FZ/T|DB\d{1,2}/T|Q/[A-Za-z]+"
            r"|T/[A-Za-z_]+|IEC|ISO|EN)\s*\d+(?:\.\d+)*(?:\s*[—\-–]\s*\d{4})?"
        )


def extract_references(doc: dict) -> list[dict]:
    """从规范性引用语义段（semanticTypes=normativeReference）与第 2 章内容中
    抽取引用标准号清单。返回 [{standardNumber, norm, clause, mdLine}]。"""
    regex = _standards_regex()
    hits: dict[str, dict] = {}

    def walk(node: dict, clause_number: Optional[str]):
        node_type = node.get("nodeType")
        if node_type in ("section", "clause", "subClause", "annex"):
            clause_number = node.get("number") or clause_number
        for ce in node.get("contentElements") or []:
            text = ce.get("textContent") or ""
            sem = ce.get("semanticTypes") or []
            is_ref = "normativeReference" in sem
            is_ch2 = clause_number == "2" or (clause_number or "").startswith("2.")
            if not (is_ref or is_ch2):
                continue
            for m in regex.finditer(text):
                raw = m.group(0).strip()
                norm = _norm_standard_number(raw)
                key = norm or raw
                if key not in hits:
                    hits[key] = {
                        "standardNumber": raw,
                        "norm": norm,
                        "clause": clause_number,
                        "mdLine": _first_anchor_line(ce),
                    }
        for child in node.get("children") or []:
            walk(child, clause_number)

    walk(doc.get("structuralRoot") or {}, None)
    return sorted(hits.values(), key=lambda r: r["norm"] or r["standardNumber"])


def _collect(doc: dict):
    """遍历结构树：产出 (node, parent_id, depth) 序列。"""
    seq = []

    def walk(node: dict, parent_id: Optional[str], depth: int):
        seq.append((node, parent_id, depth))
        for child in node.get("children") or []:
            walk(child, node["id"], depth + 1)

    walk(doc.get("structuralRoot") or {}, None, 0)
    return seq


def build_kg(doc: dict, artifact_path: Optional[str] = None) -> dict:
    """SSIRDocument → kg.json（纯函数，不触碰文件系统）。

    artifact_path：ssir.json 的仓库路径，写入 document.artifactPath 便于溯源。
    """
    if not doc or not doc.get("structuralRoot"):
        raise ValueError("不是合法 SSIR 文档：缺少 structuralRoot")

    meta = (doc.get("metadata") or {}).get("standard") or {}
    common = (doc.get("metadata") or {}).get("common") or {}
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_edges: set[tuple[str, str, str]] = set()

    def add_edge(from_id: str, to_id: str, etype: str):
        key = (from_id, to_id, etype)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append({"from": from_id, "to": to_id, "type": etype})

    # registry 实体（表/图/公式）先全部登记，供引用边指向
    registry_ids: dict[str, dict] = {}

    def register_unit(unit: dict, kind: str):
        registry_ids[unit["id"]] = _node_base(unit, kind, _anchor_of(unit))
        node = registry_ids[unit["id"]]
        for key in ("number", "caption", "assetRef", "sourceWidth", "sourceHeight",
                    "latex", "rawText", "altText", "unit", "rowCount", "colCount"):
            val = unit.get(key)
            if val is not None and val != "":
                node[key] = val
        # caption/题注可能在 registry 缺失（GB_T_1.1 图注册表无 caption 键）——容忍
        nodes.append(node)

    for u in doc.get("tables") or []:
        register_unit(u, "Table")
    for u in doc.get("figures") or []:
        register_unit(u, "Figure")
    for u in doc.get("formulas") or []:
        register_unit(u, "Formula")

    term_def_cache: dict[str, str] = {}

    def collect_term(node: dict) -> Optional[str]:
        """返回该节点 termDefinition 段正文（术语定义文本），无则 None。"""
        for ce in node.get("contentElements") or []:
            if "termDefinition" in (ce.get("semanticTypes") or []):
                return (ce.get("textContent") or "")[:_CE_TEXT_LIMIT]
        return None

    def walk(node: dict, parent_id: Optional[str], doc_depth: int):
        node_type = node.get("nodeType", "")
        kind = _STRUCTURAL_KIND.get(node_type, "ContentUnit")
        anchor = _anchor_of(node)
        n = _node_base(node, kind, anchor)
        # 通用属性（存在才带）
        for key in ("number", "title", "level", "term", "englishTerm", "sortOrder"):
            val = node.get(key)
            if val is not None and val != "":
                n[key] = val
        if kind == "Document":
            n.pop("number", None)
            n.pop("title", None)
            n["level"] = 0
        if kind == "Clause":
            n["structuralKind"] = node_type
        if kind == "ContentUnit" and node_type in ("item", "subItem"):
            n["structuralKind"] = node_type
        n["depth"] = doc_depth  # 树深度，供层级布局
        nodes.append(n)

        if parent_id is not None:
            add_edge(parent_id, node["id"], "HAS_CHILD")

        # 术语 → Term 节点（TERM_DEFINED_IN → 本节点）
        term = node.get("term")
        if term:
            tid = f"{node['id']}/term"
            tnode = {
                "id": tid,
                "kind": "Term",
                "term": term,
                "clauseNumber": node.get("number"),
                "clauseTitle": node.get("title"),
            }
            if node.get("englishTerm"):
                tnode["englishTerm"] = node["englishTerm"]
            definition = collect_term(node)
            if definition:
                tnode["definitionText"] = definition
            if anchor:
                tnode["anchor"] = anchor
            nodes.append(tnode)
            add_edge(node["id"], tid, "HAS_TERM")

        # 内容元素
        for ce in node.get("contentElements") or []:
            ptype = ce.get("presentationType")
            ref_type = _REF_PRESENTATION.get(ptype)
            if ref_type is not None:
                # 表/图/公式：父节点直接连 registry 实体
                ref = ce.get(f"{ptype}Ref")
                if ref and ref in registry_ids:
                    add_edge(node["id"], ref, "CONTAINS_ELEMENT")
                else:
                    # 无 ref 的注册表实体按 caption 反查兜底（同 id 前缀罕见）
                    nid = ce.get("id")
                    if nid and nid in registry_ids:
                        add_edge(node["id"], nid, "CONTAINS_ELEMENT")
                continue
            if ptype not in _CE_PRESENTATION:
                # 未知类型 CE：保留但不再扩张
                if not ptype:
                    continue
            anchor_ce = _anchor_of(ce)
            cnode = {
                "id": ce["id"],
                "kind": "ContentUnit",
                "CE": True,
                "presentationType": ptype,
                "parentNodeId": node["id"],
                "depth": doc_depth + 1,
            }
            if anchor_ce:
                cnode["anchor"] = anchor_ce
            text = ce.get("textContent") or ""
            if text:
                cnode["text"] = text[:_CE_TEXT_LIMIT]
                if len(text) > _CE_TEXT_LIMIT:
                    cnode["truncated"] = True
            sem = ce.get("semanticTypes")
            if sem:
                cnode["semantics"] = sem
            nodes.append(cnode)
            add_edge(node["id"], ce["id"], "CONTAINS_ELEMENT")

        for child in node.get("children") or []:
            walk(child, node["id"], doc_depth + 1)

    walk(doc.get("structuralRoot") or {}, None, 0)

    # 按 kind 统计
    counts: dict[str, int] = {}
    for node in nodes:
        key = node["kind"]
        if node.get("CE"):
            key = "ContentUnit(CE)"
        counts[key] = counts.get(key, 0) + 1

    # document 头（StandardDocument 概要）
    document = {
        "id": doc.get("id"),
        "rootNodeId": (doc.get("structuralRoot") or {}).get("id"),
        "standardNumber": meta.get("standardNumber"),
        "chineseTitle": meta.get("chineseTitle") or common.get("title"),
        "documentType": doc.get("documentType"),
        "ics": meta.get("ics"),
        "ccs": meta.get("ccs"),
        "replaces": meta.get("replaces"),
        "issuer": common.get("issuer"),
        "publicationDate": common.get("publicationDate"),
        "effectiveDate": common.get("effectiveDate"),
        "sourceFileName": (doc.get("sourceFiles") or [{}])[0].get("fileName"),
        "references": extract_references(doc),
    }
    if artifact_path:
        document["artifactPath"] = str(artifact_path)

    return {
        "kgVersion": KG_VERSION,
        "document": {k: v for k, v in document.items() if v is not None},
        "nodes": nodes,
        "edges": edges,
        "counts": counts,
    }


def _schema_path() -> Path:
    return Path(__file__).with_name(KG_SCHEMA_RELPATH)


def validate_kg(kg: dict) -> list[str]:
    """用 kg.schema.json 校验；返回错误列表，空=通过。"""
    import jsonschema  # noqa: PLC0415

    schema = json.loads(_schema_path().read_text(encoding="utf-8"))
    try:
        jsonschema.validate(kg, schema)
        return []
    except jsonschema.ValidationError as exc:
        return [f"{'.'.join(str(p) for p in exc.absolute_path) or '(root)'}: {exc.message}"]


def kg_to_file(kg: dict, out_path: str | Path) -> Path:
    out = Path(out_path)
    out.write_text(json.dumps(kg, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
