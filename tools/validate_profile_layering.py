#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_profile_layering.py — R0 验证：规则包分层叠加材料化 + 分阶段审查（Q_YYJD_001-2024）

依据：
- docs/semantic_Stage/lookWhy 规则包分层叠加与审核规则包模型 v0.1（profile/layers/resolution/快照）
- docs/semantic_Stage/lookWhy 规则层分类与分阶段审查设计 v0.1（formal/technical、registry）
- out/profile-demo/registry-demo.yaml（演示注册表）

数据全部来自真实产物：
- 审查对象 Q_YYJD_001-2024.ssir.json（永磁直流无刷电动机 企业标准）
- 技术规则源 GB_T_5171.1-2014.ssir.json（小功率电动机 通用技术条件，auto-clause 抽取）
- 形式规则 rules/base/GB_T_1.1-2020/requirements.yaml（GBT-E*/H* 真实规则）

用法：<repo>/.venv/bin/python tools/validate_profile_layering.py
输出：out/profile-demo/report-qyyjd.json（机器可读）+ stdout 摘要
"""
from __future__ import annotations
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("需要 PyYAML：请用仓库 venv 运行")

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "out/profile-demo/registry-demo.yaml"
SUBJECT = ROOT / "out/mineru/Q_YYJD_001-2024/03_ssir/Q_YYJD_001-2024.ssir.json"
BASE_RULES = ROOT / "rules/base/GB_T_1.1-2020/requirements.yaml"
OUT_JSON = ROOT / "out/profile-demo/report-qyyjd.json"

UNITS = ["V", "W", "A", "Hz", "kHz", "r/min", "rpm", "dB", "℃", "°C", "K", "MΩ", "N·m", "mm", "kg", "g", "h", "min", "s", "%"]


# ---------------------------------------------------------------- IO/树
def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def iter_nodes(n):
    yield n
    for c in (n.get("children") or []):
        yield from iter_nodes(c)


def node_text(n) -> str:
    parts = []
    for ce in (n.get("contentElements") or []):
        t = ce.get("textContent", "")
        if t:
            parts.append(t)
    return "\n".join(parts)


def all_text(subject) -> str:
    """文档全文本（结构节点 + 顶层内容元素）"""
    parts = [node_text(n) for n in iter_nodes(subject["structuralRoot"])]
    parts.append(node_text(subject["structuralRoot"]))
    return "\n".join(parts)


def chapter2_citations(subject) -> list[str]:
    for c in (subject["structuralRoot"].get("children") or []):
        if str(c.get("number")) == "2":
            lines = node_text(c).splitlines()
            return [ln.strip() for ln in lines if re.search(r"GB|IEC|ISO|Q/", ln)]
    return []


def strip_noise(t: str) -> str:
    t = re.sub(r"\$([^$]*)\$", lambda m: re.sub(r"\s+", "", m.group(1)), t)  # $..$ 内去空格(拍平 LaTeX 数字)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"[{}]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t


# ---------------------------------------------------------------- 规则装载
def load_base_elements() -> list[dict]:
    """真实 GBT-E* 必备要素规则（来自 requirements.yaml content-and-structure.elements）"""
    y = yaml.safe_load(BASE_RULES.read_text(encoding="utf-8"))
    out = []
    for e in (y.get("content-and-structure", {}).get("elements") or []):
        req = e.get("required", "")
        if "必备" in req:  # 必备 / 必备/可选
            out.append({
                "id": e["id"], "element": e.get("element"), "required": req,
                "source": e.get("source", ""), "kind": e.get("kind", ""),
            })
    return out


def rules_for_base_11() -> list[dict]:
    return [{
        "id": r["id"], "rule": r.get("rule", r.get("element", "")), "source": r.get("source", ""),
        "category": "formal", "stage": "form", "obligation": "mandatory", "element": r.get("element"),
    } for r in load_base_elements()]


def auto_extract_small_power(params) -> tuple[list[dict], dict]:
    """从 GB/T 5171.1-2014 SSIR 自动抽取候选技术规则（应→强制/宜→推荐）"""
    ssir = load_json(ROOT / params["source-ssir"])
    labels = params["chapter-labels"]
    chapters = {str(k): v for k, v in labels.items()}
    rules, stats = [], Counter()
    for ch in (ssir["structuralRoot"].get("children") or []):
        ch_num = str(ch.get("number"))
        if ch_num not in chapters:
            continue
        n_rules = 0
        for node in iter_nodes(ch):
            if n_rules >= int(params.get("max-rules-per-chapter", 8)):
                break
            nnum = str(node.get("number") or "")
            # 只抽取嵌套子条（编号含点），跳过章本身与无编号节点
            if not re.fullmatch(r"\d+\.\d+(?:\.\d+)*", nnum):
                continue
            t = strip_noise(node_text(node))
            if not (re.search(r"应|宜|须|不得|不应", t) and re.search(r"\d", t) and len(t) > 12):
                continue
            anchor = None
            for ce in (node.get("contentElements") or []):
                for sa in (ce.get("sourceAnchors") or []):
                    anchor = sa.get("markdownStartLine")
                    break
                if anchor:
                    break
            obligation = "recommended" if ("宜" in t and "应" not in t) else "mandatory"
            rid = f"SPM-{ch_num}-{nnum}-{n_rules + 1}"
            rules.append({
                "id": rid, "domain": chapters[ch_num], "chapter": ch_num,
                "clause": nnum, "title": str(node.get("title") or "")[:30],
                "rule": t[:150], "obligation": obligation,
                "source-file": str(ROOT / params["source-ssir"]),
                "source-clause": nnum,
                "source-anchor-md-line": anchor,
                "stage": "technical", "category": "technical",
            })
            stats[(ch_num, chapters[ch_num], obligation)] += 1
            n_rules += 1
        # 回退：无编号子节点的章（正文内嵌 "8.1 …" 式条款），按条款标记切分
        if n_rules == 0:
            t = strip_noise(node_text(ch))
            marks = [(m.start(), m.group(1)) for m in re.finditer(
                r"(?<!\d\.)(\d{1,2}\.\d{1,2}(?:\.\d{1,2})?)(?!\.\d)(?=\s|[\u3000．。])", t)]
            for i in range(min(len(marks), int(params.get("max-rules-per-chapter", 8)))):
                seg = t[marks[i][0]: marks[i + 1][0] if i + 1 < len(marks) else len(t)]
                if not (re.search(r"应|宜|须|不得|不应", seg) and re.search(r"\d", seg)):
                    continue
                obligation = "recommended" if ("宜" in seg and "应" not in seg) else "mandatory"
                rules.append({
                    "id": f"SPM-{ch_num}-{marks[i][1]}-{i + 1}", "domain": chapters[ch_num],
                    "chapter": ch_num, "clause": marks[i][1], "title": "",
                    "rule": seg.strip()[:150], "obligation": obligation,
                    "source-file": str(ROOT / params["source-ssir"]), "source-clause": marks[i][1],
                    "source-anchor-md-line": None, "stage": "technical", "category": "technical",
                    "extract-mode": "flat-inline",
                })
                stats[(ch_num, chapters[ch_num], obligation)] += 1
    return rules, dict(stats)


def rule_for_layer(r: dict, pkg_id: str, layer_idx: int, role: str) -> dict:
    return {**r, "layerPath": f"L{layer_idx}:{role}:{pkg_id}"}


# ---------------------------------------------------------------- 阶段 A 执行器（真实结构检查）
def check_top_chapter_sequence(subject) -> list[dict]:
    chs = []
    for c in (subject["structuralRoot"].get("children") or []):
        if c.get("nodeType") == "section" and c.get("number"):
            chs.append((c.get("number"), c.get("title")))
    seq = [int(n) for n, _ in chs if str(n).isdigit()]
    findings, seen, dup = [], [], []
    for n in seq:
        (dup if n in seen else seen).append(n)
    expected = list(range(1, max(seq) + 1)) if seq else []
    missing = sorted(set(expected) - set(seq))
    if missing:
        findings.append({
            "severity": "error", "ruleId": "GBT-H02", "layerPath": "L1:formal-floor:base/GB_T_1.1-2020",
            "finding": f"章号序列 {seq} 缺少章：{missing}",
            "suggestion": "第 6 章(试验方法)标题缺失/被吞——文档内存在 6.1/6.4..6.18 试验条款，疑章标题丢失(参考 GEN-031/GEN-035 类修复)",
            "evidence": "structuralRoot 顶层 section number 序列",
        })
    for n in dup:
        titles = [t for num2, t in chs if str(num2) == str(n)]
        findings.append({
            "severity": "error", "ruleId": "GBT-H02", "layerPath": "L1:formal-floor:base/GB_T_1.1-2020",
            "finding": f"章号重复：{n}（{titles}）",
            "suggestion": "温升限值章疑实为 5.7（前缀 5. 丢失）；检验规则章编号应顺延",
            "evidence": "structuralRoot 顶层 section number 序列",
        })
    return findings


def _is_num(s: str) -> bool:
    return s.isdigit() or bool(re.fullmatch(r"\d+(?:\.\d+)+", s))


def check_parent_prefix(subject) -> list[dict]:
    findings = []
    for node in iter_nodes(subject["structuralRoot"]):
        kids = [c for c in (node.get("children") or []) if c.get("number")]
        if node.get("nodeType") == "section" and kids:
            pnum = str(node.get("number"))
            if not pnum.isdigit():
                continue
            bad = [str(k.get("number")) for k in kids
                   if _is_num(str(k.get("number"))) and not str(k.get("number")).startswith(pnum + ".")]
            if bad:
                findings.append({
                    "severity": "error", "ruleId": "GBT-H03", "layerPath": "L1:formal-floor:base/GB_T_1.1-2020",
                    "finding": f"章 {pnum}({node.get('title')}) 下子条号不以父号前缀：{bad[:8]}",
                    "suggestion": "温升限值若为 5.7，则 5.8..5.17 前缀正确、6.x 属第 6 章——编号/章标题在抽取中错位；建议源文件复核或规则化修复",
                    "evidence": "clause/subClause number 与父 number 前缀比对",
                })
    # 兄弟重复检测（跳过顶层：顶层章重复由 GBT-H02 报告）
    for node in iter_nodes(subject["structuralRoot"]):
        if node.get("nodeType") == "document":
            continue
        kids = [str(c.get("number")) for c in (node.get("children") or []) if c.get("number")]
        dups = sorted({n for n in kids if kids.count(n) > 1})
        if dups:
            findings.append({
                "severity": "error", "ruleId": "GBT-H03", "layerPath": "L1:formal-floor:base/GB_T_1.1-2020",
                "finding": f"同级条号重复：{dups}（父：{node.get('number') or node.get('nodeType')} {node.get('title')}）",
                "suggestion": "7.3.1 出厂检验/型式试验应顺序编号 7.3.1、7.3.2",
                "evidence": "同父下兄弟 number 集合",
            })
    return findings


def check_missing_5_prefix(subject) -> list[dict]:
    """5.x 序列缺口（5.1/5.2/5.7 未见）提示——信息级"""
    got = [n for n in iter_nodes(subject["structuralRoot"]) if re.fullmatch(r"5\.\d+", str(n.get("number")))]
    got.sort(key=lambda n: str(n.get("number")))
    nums = [str(n.get("number")) for n in got]
    want = [f"5.{i}" for i in range(1, 18)]
    absent = [w for w in want if w not in nums]
    if absent:
        return [{
            "severity": "info", "ruleId": "GBT-H03", "layerPath": "L1:formal-floor:base/GB_T_1.1-2020",
            "finding": f"5.x 编号缺口：{absent}（前段可能为无编号引导段，温升限值标题疑编号截断为 7）",
            "suggestion": "人工核对：5.1/5.2 若为无标题段属正常；5.7 温升限值需还原编号",
            "evidence": "全树 number 匹配 5.\\d+",
        }]
    return []


def check_stray_blocks(subject) -> list[dict]:
    out = []
    for c in (subject["structuralRoot"].get("children") or []):
        if c.get("nodeType") == "documentBlock" and not c.get("number") and c.get("title"):
            out.append({
                "severity": "warning", "ruleId": "GEN-093", "layerPath": "L1:formal-floor:base/GB_T_1.1-2020",
                "finding": f"游离顶层 documentBlock：{c.get('title')}",
                "suggestion": "内容疑属 8.2 使用说明书或包装条款，被误提升为文档级块；应并入 8.x 条款或按 GEN-093 处理",
                "evidence": "structuralRoot 顶层 documentBlock 无编号且位于末章之后",
            })
    return out


def check_units(subject) -> list[dict]:
    out, unit_re = [], re.compile("|".join(re.escape(u) for u in UNITS))
    for c in (subject["structuralRoot"].get("children") or []):
        num = str(c.get("number"))
        if num not in ("4", "5", "7") or "检验" in str(c.get("title")):
            continue
        t = strip_noise(node_text(c))
        nums = len(re.findall(r"\d+(?:\.\d+)?", t))
        uhits = len(unit_re.findall(t))
        sev = "warning" if nums >= 8 and uhits == 0 else "info"
        if nums >= 4:
            out.append({
                "severity": sev, "ruleId": "GB3100-R01", "layerPath": "L2:formal-floor:base/GB_3100-2026",
                "finding": f"第 {num} 章({c.get('title')})：数值 {nums} 处、单位命中 {uhits} 处",
                "suggestion": "0 单位命中且数值密集时核查量值是否漏单位（GB 3100-2026 包待建，演示条目）" if sev == "warning" else "单位表达常规，无需动作",
                "evidence": "文本层正则统计（演示级，正式检查以规则包建成后为准）",
            })
    return out


def check_template_structure(subject) -> list[dict]:
    titles = " | ".join(str(c.get("title")) for c in (subject["structuralRoot"].get("children") or []))
    got6 = any(re.fullmatch(r"6\.\d+", str(n.get("number"))) for n in iter_nodes(subject["structuralRoot"]))
    rows = [
        ("TPL-01", "要求章", "要求" in titles),
        ("TPL-02", "试验方法章标题", "试验" in titles),
        ("TPL-03", "检验规则章", "检验" in titles),
        ("TPL-04", "标志/包装/运输/贮存章", ("标志" in titles and "包装" in titles)),
    ]
    out = []
    for rid, name, ok in rows:
        if ok:
            out.append({"severity": "info", "ruleId": rid, "layerPath": "L3:formal-template:tenants/yyjd/std-template-v3",
                        "finding": f"企业模板要素「{name}」已覆盖", "suggestion": "", "evidence": "顶层章标题"})
        elif rid == "TPL-02" and got6:
            out.append({"severity": "warning", "ruleId": rid, "layerPath": "L3:formal-template:tenants/yyjd/std-template-v3",
                        "finding": "企业模板要素「试验方法章标题」缺失，但存在 6.x 试验条款",
                        "suggestion": "疑第 6 章标题在抽取中丢失（与 GBT-H02 章号缺失同源）；需人工复核源文件", "evidence": "顶层章标题 + 6.x 条款存在"})
        else:
            out.append({"severity": "error", "ruleId": rid, "layerPath": "L3:formal-template:tenants/yyjd/std-template-v3",
                        "finding": f"企业模板要素「{name}」缺失", "suggestion": "按企业标准模板补齐", "evidence": "顶层章标题"})
    return out


def check_elements(subject, elem_rules) -> list[dict]:
    titles = [str(c.get("title")) for c in (subject["structuralRoot"].get("children") or [])]
    nums = [str(c.get("number")) for c in (subject["structuralRoot"].get("children") or [])]
    alltext = all_text(subject)
    meta = subject.get("metadata", {}).get("standard", {})
    out = []
    for r in elem_rules:
        el = r["element"]
        if "封面" in el:
            ok = bool(meta.get("chineseTitle") and meta.get("standardNumber"))
            sev, sugg = ("info", "封面解析产物 metadata 已含标题与标准号") if ok else ("warning", "启发式未检出封面，请人工复核")
        elif "前言" in el:
            ok = bool(re.search(r"前\s*言", alltext))
            sev, sugg = ("info", "文本含前言") if ok else ("warning", "未检出「前言」文本；若企业标准确无前言则违反 GBT-E03(必备)——请人工复核")
        elif "范围" in el:
            ok = any("范围" in t for t in titles)
            sev, sugg = ("info", "章标题含范围") if ok else ("error", "必备要素缺失")
        elif "规范性引用" in el:
            ok = any("引用" in t for t in titles)
            sev, sugg = ("info", "章标题含规范性引用") if ok else ("error", "必备要素缺失")
        elif "术语" in el:
            ok = any("术语" in t for t in titles)
            sev, sugg = ("info", "章标题含术语和定义") if ok else ("warning", "必备/可选要素未检出")
        elif "核心" in el:
            ok = any(("要求" in t or "技术" in t) for t in titles) and any(n == "5" for n in nums)
            sev, sugg = ("info", "要求/技术要素章存在") if ok else ("error", "核心技术要素缺失")
        else:
            continue
        out.append({"severity": sev, "ruleId": r["id"], "layerPath": "L1:formal-floor:base/GB_T_1.1-2020",
                    "finding": f"要素「{el}」（{r.get('required')}，{r.get('source')}）：{'已检出' if ok else '未检出'}",
                    "suggestion": sugg, "evidence": "章节标题/全文文本/metadata 启发式"})
    return out


def citation_hints(subject) -> list[dict]:
    cites = "\n".join(chapter2_citations(subject))
    out = []
    if re.search(r"GB\s*755-2008", cites):
        out.append({"severity": "info", "ruleId": "CIT-HINT", "layerPath": "L4:technical-baseline:industries/motor/rotating",
                    "finding": "第 2 章引用「GB 755-2008 旋转电动机 定额和性能」",
                    "suggestion": "语料库存在更新版 corpus/golden/GB_T_755-2025.pdf（GB/T 755-2025）；核对现行版本与引用形式(GB→GB/T)——推荐性提示，无需登记",
                    "evidence": "第 2 章引用清单文本"})
    if not re.search(r"5171", cites):
        out.append({"severity": "info", "ruleId": "CIT-HINT", "layerPath": "L5:technical-optional:industries/motor/small-power",
                    "finding": "第 2 章未引用 GB/T 5171.1（小功率电动机通用技术条件）",
                    "suggestion": "小功率层按产品类(brushless-pm-motor)附加；若产品属小功率电动机建议核对是否应引用——推荐性提示",
                    "evidence": "第 2 章引用清单文本"})
    return out


# ---------------------------------------------------------------- 语义裁决（决策 2026-09-02）
def decide(obligation: str, relation: str, policy: dict, demo: bool = True) -> dict:
    """relation: relax | tighten | equal | gap"""
    cfg = policy.get(obligation, {}).get(relation, {})
    action = "pass" if relation in ("tighten", "equal") else cfg
    if isinstance(action, dict):
        action = action.get("default", "note")
    return {"obligation": obligation, "relation": relation, "action": action,
            "note": "演示语义验证" if demo else ""}


# ---------------------------------------------------------------- 主流程
def main() -> int:
    reg = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    subject = load_json(SUBJECT)
    meta = subject.get("metadata", {}).get("standard", {})
    sn = str(meta.get("standardNumber", ""))
    title = str(meta.get("chineseTitle", ""))
    doc_class = "Q_" if re.match(r"Q/", sn) else "?"
    products = ["brushless-pm-motor"] if "永磁直流无刷" in title or "无刷" in title else []

    # 1) 命中 profile
    profile = None
    for pr in reg.get("profiles", []):
        if (doc_class in pr["subject"].get("doc-classes", [])
                and any(p in products for p in pr["subject"].get("products", []))
                and pr.get("status") == "industry-approved"):
            profile = pr
            break
    if profile is None:
        sys.exit("未命中任何 industry-approved profile")
    pkg_by_id = {p["id"]: p for p in reg["rule-sources"]}

    # 2) 层解析与挂载原因
    cites_all = "\n".join(chapter2_citations(subject))
    layer_info = []
    for i, lay in enumerate(profile["layers"], start=1):
        pkg = pkg_by_id[lay["package"]]
        reason = "profile 声明"
        if "rotating" in lay["package"]:
            reason = "产品类归属 + 第2章引用命中(GB 755-2008→旋转电机域)"
        if "small-power" in lay["package"]:
            reason = "产品类归属(brushless-pm-motor 属小功率无刷；文档未引用 5171.1，见 CIT-HINT)"
        layer_info.append({"idx": i, "package": lay["package"], "role": lay["role"],
                           "category": pkg.get("review-category"), "stage": pkg.get("review-stage"),
                           "status": pkg.get("status"), "attach-reason": reason, "demo": pkg.get("demo", False)})

    # 3) 材料化有效规则集（分阶段）
    effective = {"form": [], "technical": []}
    for lay in profile["layers"]:
        pkg = pkg_by_id[lay["package"]]
        stage = pkg.get("review-stage", "form")
        rules = []
        if lay["package"] == "base/GB_T_1.1-2020":
            rules = rules_for_base_11()
        elif pkg.get("builder") == "auto-clause":
            rules, _ = auto_extract_small_power(pkg["builder-params"])
            for r in rules:
                r["source-package"] = lay["package"]
                r["source-status"] = "candidate(auto-extract)"
        for r in rules:
            effective[stage].append(rule_for_layer(r, lay["package"], profile["layers"].index(lay) + 1, lay["role"]))

    # legal-floor 校验（demo：模板层试图覆盖封面必备 → 拒绝）
    floor_demo = {
        "demo": True,
        "ruleId": "GBT-E01", "layerPath": "L3:formal-template:tenants/yyjd/std-template-v3",
        "attempt": "企业模板规则(演示)声明『封面可省略』，与 L1 GBT-E01 封面必备(legal-floor)冲突",
        "verdict": "override-blocked", "action": "blocked-by-legal-floor",
        "evidence": "profile.resolution.legal-floor 包含 base/GB_T_1.1-2020",
    }

    # 4) 阶段 A 执行
    stageA = []
    stageA += check_top_chapter_sequence(subject)
    stageA += check_parent_prefix(subject)
    stageA += check_missing_5_prefix(subject)
    stageA += check_stray_blocks(subject)
    stageA += check_elements(subject, load_base_elements())
    stageA += check_units(subject)
    stageA += check_template_structure(subject)
    stageA += citation_hints(subject)

    # 5) 阶段 B（technical）
    sp = pkg_by_id["industries/motor/small-power"]
    tech_rules, stats = auto_extract_small_power(sp["builder-params"])
    for r in tech_rules:
        r["source-package"] = "industries/motor/small-power"
    # 覆盖度（5171.1 域 vs Q_YYJD 全文）
    qtext = all_text(subject)
    kwmap = {
        "运行条件": ["环境", "海拔"], "额定值": ["额定功率", "定额", "额定电压"], "温升试验": ["温升"],
        "效率": ["效率"], "介电性能试验": ["绝缘电阻", "耐电压", "耐电", "介电"],
        "性能要求": ["过电流", "超速", "转矩", "转向"], "噪声": ["噪声"], "振动": ["振动"],
        "安全": ["安全", "接地", "防护"], "电磁兼容性": ["电磁兼容"],
    }
    coverage = []
    for (num, label, obl), cnt in sorted(stats.items()):
        hits = [k for k in kwmap.get(label, []) if k in qtext]
        gap = not hits
        sev = "warn" if gap and obl == "mandatory" else ("note" if gap else "info")
        coverage.append({"chapter": num, "domain": label, "obligation": obl, "auto-rules": cnt,
                         "qyyjd-hits": hits, "gap": gap, "severity": sev,
                         "suggestion": "建议企标声明覆盖或走偏差登记(强制缺口)" if (gap and obl == "mandatory") else "备注/提示即可(推荐缺口)" if gap else ""})
    # 语义裁决演示（值均为演示输入，非 Q_YYJD 真实合规结论）
    policy = profile["resolution"]["obligation"]
    sem = [
        {"demo": True, "ruleId": "ROT-DEMO-01", "layerPath": "L4:technical-baseline:industries/motor/rotating",
         "source": "GB/T 755-2025(规则包待建,演示条目)", "clause": "5.x(演示)",
         "rule": "电压偏差±5%时应能连续运行", "obligation": "mandatory",
         "subject-value": "电压偏差±10%(演示输入)", **decide("mandatory", "relax", policy)},
        {"demo": True, "ruleId": "SPM-auto-12", "layerPath": "L5:technical-optional:industries/motor/small-power",
         "source": "GB/T 5171.1-2014 §12.3(真实文本)", "clause": "12.3",
         "rule": "宜提供 75%/50% 额定负载效率三点数据", "obligation": "recommended",
         "subject-value": "企标未提供效率特性点(演示输入)", **decide("recommended", "gap", policy)},
        {"demo": True, "ruleId": "ROT-DEMO-02", "layerPath": "L4:technical-baseline:industries/motor/rotating",
         "source": "GB/T 755-2025(规则包待建,演示条目)", "clause": "噪声限值(演示)",
         "rule": "噪声限值应 ≤60dB(A)", "obligation": "mandatory",
         "subject-value": "企标 ≤55dB(A)(演示输入)", **decide("mandatory", "tighten", policy)},
    ]
    registers = [s for s in sem if s.get("action") == "register-required"]
    notes = [s for s in sem if s.get("action") == "note"]

    # 6) 快照
    ids = sorted({r["id"] for stage in effective.values() for r in stage} | {r["ruleId"] for r in stageA})
    snap_text = json.dumps({"profile": profile["id"], "version": profile["version"],
                            "layers": [f"L{i+1}:{l['package']}" for i, l in enumerate(profile["layers"])],
                            "rule-ids": ids}, sort_keys=True, ensure_ascii=False)
    snapshot = hashlib.sha256(snap_text.encode("utf-8")).hexdigest()[:16]

    report = {
        "schema": "profile-layering-validation/v0.1",
        "subject": {"standardNumber": sn, "title": title, "doc-class": doc_class, "products": products,
                    "ssir": str(SUBJECT.relative_to(ROOT))},
        "profile": {"id": profile["id"], "version": profile["version"], "share": profile.get("share"),
                    "status": profile.get("status")},
        "layers": layer_info,
        "effective-rules": {k: len(v) for k, v in effective.items()},
        "effective-form-sample": effective["form"][:6],
        "stage-A": {"count": len(stageA), "by-severity": dict(Counter(f["severity"] for f in stageA)),
                    "findings": stageA},
        "stage-B": {"auto-rules-total": len(tech_rules),
                    "auto-rules-by-domain": {f"{k[0]}:{k[1]}:{k[2]}": v for k, v in stats.items()},
                    "auto-rule-sample": tech_rules[:5], "coverage": coverage,
                    "semantics-demo": sem, "deviations-register": registers, "notes": notes},
        "legal-floor-demo": floor_demo,
        "snapshot": {"hash": snapshot, "profile-version": profile["version"], "pins-locked": profile.get("pins", {}).get("lock", True)},
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # stdout 摘要
    print(f"subject      : {sn} {title}")
    print(f"profile      : {profile['id']} v{profile['version']} ({profile.get('share')}, {profile.get('status')})")
    print("layers:")
    for l in layer_info:
        print(f"   L{l['idx']} {l['role']:<16} {l['package']:<36} {l['category']}/{l['stage']} {l['status']}  <- {l['attach-reason']}")
    print(f"effective    : form={len(effective['form'])} technical={len(effective['technical'])}  snapshot={snapshot}")
    print(f"stage A      : {len(stageA)} findings {dict(Counter(f['severity'] for f in stageA))}")
    for f in [x for x in stageA if x['severity'] == 'error'][:6]:
        print("   [E]", f['ruleId'], '|', f['finding'][:110])
    for f in [x for x in stageA if x['severity'] == 'warning'][:4]:
        print("   [W]", f['ruleId'], '|', f['finding'][:100])
    print(f"stage B      : small-power auto rules={len(tech_rules)}; coverage rows={len(coverage)}")
    for c in coverage:
        if c['gap']:
            print(f"   [GAP {c['severity']}] {c['domain']}({c['obligation']}) rules={c['auto-rules']} hits={c['qyyjd-hits']}")
    for s in sem:
        print(f"   verdict {s['ruleId']:<14} {s['obligation']:<10} {s['relation']:<8} -> {s['action']}")
    print(f"register     : {len(registers)} 条强制放宽需登记; notes={len(notes)} 条推荐性备注")
    print(f"legal-floor  : {floor_demo['verdict']}")
    print(f"report       : {OUT_JSON.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
