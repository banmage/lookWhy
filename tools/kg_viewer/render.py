"""kg_viewer 内容渲染：把 SSIR 载荷节点渲染为浏览用 HTML。

纯函数、无 Flask 依赖（便于单测）；图片 URL 由调用方注入 builder。
"""
from __future__ import annotations

import html as _html
from typing import Callable, Optional


def _flatten(text: str) -> str:
    """LaTeX 命令噪声拍平（复用渲染管线 _latex_to_text），失败则原样返回。"""
    try:
        from leleby_ssir.pdf_renderer import _latex_to_text  # noqa: PLC0415

        return _latex_to_text(text)
    except Exception:  # pragma: no cover
        return text


def esc(value) -> str:
    return _html.escape(str(value)) if value is not None else ""


def _par(text: str) -> str:
    out = esc(_flatten(text))
    out = out.replace("\n", "<br>")
    return f'<p class="kg-ce kg-para">{out}</p>'


def _find_node(node: dict, node_id: str) -> Optional[dict]:
    if node.get("id") == node_id:
        return node
    for child in node.get("children") or []:
        found = _find_node(child, node_id)
        if found:
            return found
    return None


def find_node(payload: dict, node_id: str) -> Optional[dict]:
    root = payload.get("structuralRoot") or {}
    return _find_node(root, node_id) if root else None


def _registry_lookup(payload: dict, key: str, ref: Optional[str]) -> Optional[dict]:
    if not ref:
        return None
    for unit in payload.get(key) or []:
        if unit.get("id") == ref:
            return unit
    return None


def _asset_img(doc_id: str, asset_ref: Optional[str], cls: str = "kg-img") -> str:
    if not asset_ref:
        return ""
    return f'<img class="{cls}" src="/asset/{esc(doc_id)}/{esc(asset_ref)}" alt="">'


def render_node_content(payload: dict, node: dict, doc_id: str) -> str:
    """结构节点 → 其 contentElements 渲染 HTML。"""
    parts: list[str] = []
    for ce in node.get("contentElements") or []:
        ptype = ce.get("presentationType")
        try:
            if ptype == "paragraph":
                parts.append(_par(ce.get("textContent") or ""))
            elif ptype == "note":
                parts.append(
                    f'<div class="kg-ce kg-note">{_par(ce.get("textContent") or "")}</div>'
                )
            elif ptype == "quote":
                parts.append(
                    f'<blockquote class="kg-ce">{esc(_flatten(ce.get("textContent") or ""))}</blockquote>'
                )
            elif ptype == "list":
                items = ce.get("listItems") or []
                lis = []
                for li in items:
                    txt = li.get("text")
                    if txt:
                        lis.append(f"<li>{esc(_flatten(txt))}</li>")
                if not lis and ce.get("textContent"):
                    for raw in ce["textContent"].splitlines():
                        if raw.strip():
                            lis.append(f"<li>{esc(_flatten(raw))}</li>")
                parts.append(f'<ul class="kg-ce kg-list">{"".join(lis)}</ul>')
            elif ptype == "table":
                tbl = _registry_lookup(payload, "tables", ce.get("tableRef"))
                if tbl:
                    parts.append(_render_table(tbl, doc_id))
                # 无注册表命中的表：退化按文本展示（极少见）
                elif ce.get("textContent"):
                    parts.append(_par(ce["textContent"]))
            elif ptype == "figure":
                fig = _registry_lookup(payload, "figures", ce.get("figureRef"))
                if fig:
                    img = _asset_img(doc_id, fig.get("assetRef"))
                    cap = fig.get("caption") or ce.get("textContent") or ""
                    figcap = f"<figcaption>{esc(_flatten(cap))}</figcaption>" if cap.strip() else ""
                    parts.append(f"<figure class='kg-figure'>{img}{figcap}</figure>")
            elif ptype == "formula":
                fml = _registry_lookup(payload, "formulas", ce.get("formulaRef"))
                if fml:
                    if fml.get("assetRef"):
                        parts.append(f"<div class='kg-formula'>{_asset_img(doc_id, fml.get('assetRef'))}</div>")
                    else:
                        body = fml.get("latex") or fml.get("rawText") or ""
                        parts.append(f"<div class='kg-formula kg-formula-text'>{esc(_flatten(body))}</div>")
                elif ce.get("textContent"):
                    parts.append(_par(ce["textContent"]))
            elif ptype and ptype not in ("table",):
                # 其它类型一律按文本块展示（不失内容）
                if ce.get("textContent"):
                    parts.append(_par(ce["textContent"]))
        except Exception as exc:  # pragma: no cover - 单个 CE 渲染失败不拖垮整页
            parts.append(f'<p class="kg-ce kg-err">[渲染失败 {esc(ptype)}: {esc(exc)}]</p>')
    return "\n".join(parts)


def _render_table(tbl: dict, doc_id: str) -> str:
    caption = tbl.get("caption") or ""
    number = tbl.get("number")
    cap_html = ""
    if number or caption:
        cap_html = (
            f'<div class="kg-table-caption">{esc(number or "")}'
            f'{"　" if number and caption else ""}{esc(_flatten(caption))}</div>'
        )
    rows_html: list[str] = []
    for row in tbl.get("rows") or []:
        tds = []
        for cell in row.get("cells") or []:
            tag = "th" if cell.get("isHeader") else "td"
            cs = int(cell.get("colspan") or 1)
            rs = int(cell.get("rowspan") or 1)
            attrs = ""
            if cs > 1:
                attrs += f' colspan="{cs}"'
            if rs > 1:
                attrs += f' rowspan="{rs}"'
            tds.append(
                f"<{tag}{attrs}>{esc(_flatten(cell.get('text') or ''))}</{tag}>"
            )
        rows_html.append(f"<tr>{''.join(tds)}</tr>")
    unit = tbl.get("unit")
    unit_html = f'<div class="kg-table-unit">{esc(_flatten(unit))}</div>' if unit else ""
    note_html = ""
    tn = tbl.get("tableNote")
    if tn:
        notes = tn if isinstance(tn, list) else [tn]
        note_html = "".join(
            f'<div class="kg-table-note">{esc(_flatten(n if isinstance(n, str) else n.get("text", "")))}</div>'
            for n in notes
        )
    return (
        f"{cap_html}"
        f"<div class='kg-table-wrap'><table class='kg-table'>{''.join(rows_html)}</table></div>"
        f"{unit_html}{note_html}"
    )


# 树行 → 用于列表/图标的概要（前端用）
def structure_summary(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "node_type": row.get("node_type"),
        "number": row.get("number"),
        "title": row.get("title"),
        "term": row.get("term"),
        "md_start_line": row.get("md_start_line"),
        "child_count": row.get("child_count", 0),
    }
