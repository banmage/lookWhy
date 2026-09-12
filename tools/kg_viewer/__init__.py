"""kg_viewer —— 标准知识图谱阶段 P1a/P1c 的轻量 Web 查看器（Flask）。

页面：
  /                标准列表（sqlite documents 表）
  /doc/<doc_id>    单标准浏览：左侧结构树 + 右侧内容（条款→段落/表/图/公式/术语）
  /graph/<doc_id>  vis-network 本体图（kg.json 切片；点节点→条款号/原文行定位）

API：
  /api/docs           文档列表
  /api/structure/<id> 结构树全量行（前端内存建树）
  /api/node/<id>/<nid> 节点内容 HTML + 祖先链 + 锚点
  /api/raw/<id>/<s>/<e> canonical.md 原文行
  /api/kg/<id>?scope=core|full  kg 图切片（core 去段落级 CE）
  /asset/<id>/<rel>    文档资产（图/公式图片）
"""
from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request
from flask.json.provider import DefaultJSONProvider

from leleby_ssir import kg as kglib
from leleby_ssir.kgstore import KGDocStore

from . import render as kg_render
from . import detail as kg_detail

_HERE = Path(__file__).parent


class _KGJSONProvider(DefaultJSONProvider):
    """统一中文直出（不转 \\uXXXX）。"""

    ensure_ascii = False


def create_app(db_path: str | Path) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(_HERE / "templates"),
        static_folder=str(_HERE / "static"),
    )
    app.config["KG_DB"] = db_path
    app.json = _KGJSONProvider(app)

    def store() -> KGDocStore:
        return KGDocStore(app.config["KG_DB"])

    # ---------- 页面 ----------
    @app.get("/")
    def index():
        docs = store().list_documents()
        return render_template("index.html", docs=docs)

    @app.get("/doc/<doc_id>")
    def doc_page(doc_id: str):
        st = store()
        meta = st.get_document(doc_id)
        if not meta:
            abort(404, description=f"未知文档: {doc_id}")
        return render_template("doc.html", doc=meta)

    @app.get("/graph/<doc_id>")
    def graph_page(doc_id: str):
        st = store()
        meta = st.get_document(doc_id)
        if not meta:
            abort(404, description=f"未知文档: {doc_id}")
        return render_template("graph.html", doc=meta)

    # ---------- API ----------
    @app.get("/api/docs")
    def api_docs():
        return jsonify(store().list_documents())

    @app.get("/api/structure/<doc_id>")
    def api_structure(doc_id: str):
        st = store()
        if not st.get_document(doc_id):
            abort(404)
        rows = st.all_rows(doc_id)
        return jsonify({"doc_id": doc_id, "rows": rows})

    @app.get("/api/doc/<doc_id>/detail")
    def api_doc_detail(doc_id: str):
        """文档详情（弹窗）：元数据 + 前言机构 + 术语条目 + 标准要素分层 + 清单核对。"""
        st = store()
        meta = st.get_document(doc_id)
        if not meta:
            abort(404, description=f"未知文档: {doc_id}")
        payload = st.get_payload(doc_id)
        if payload is None:
            abort(404, description=f"文档 {doc_id} 无载荷（数据库可能损坏，请重导）")
        detail = kg_detail.build_document_detail(payload)
        detail["doc_id"] = doc_id
        detail["document"] = {k: meta.get(k) for k in ("standard_number", "chinese_title", "document_type")}
        return jsonify(detail)

    @app.get("/api/node/<doc_id>/<path:node_id>")
    def api_node(doc_id: str, node_id: str):
        st = store()
        meta = st.get_document(doc_id)
        if not meta:
            abort(404, description=f"未知文档: {doc_id}")
        payload = st.get_payload(doc_id)
        if payload is None:
            abort(404, description=f"文档 {doc_id} 无载荷（数据库可能损坏，请重导）")
        node = kg_render.find_node(payload, node_id) if payload else None
        if node is None:
            abort(404, description=f"未知节点: {node_id}")
        # 祖先链（含根），用于面包屑/自动展开
        chain: list[dict] = []
        seen = set()
        cur = node_id
        while cur and cur not in seen:
            seen.add(cur)
            row = st.get_row(doc_id, cur)
            if not row:
                break
            chain.append(
                {
                    "id": row["id"],
                    "node_type": row["node_type"],
                    "number": row["number"],
                    "title": row["title"],
                    "term": row["term"],
                }
            )
            cur = row.get("parent_id")
        chain.reverse()
        html = kg_render.render_node_content(payload, node, doc_id)
        row = st.get_row(doc_id, node_id)
        return jsonify(
            {
                "doc_id": doc_id,
                "doc_title": meta.get("chinese_title"),
                "node": {
                    "id": node_id,
                    "node_type": node.get("nodeType"),
                    "number": node.get("number"),
                    "title": node.get("title"),
                    "term": node.get("term"),
                    "english_term": node.get("englishTerm"),
                    "child_count": len(node.get("children") or []),
                },
                "row": row,
                "chain": chain,
                "html": html,
            }
        )

    @app.get("/api/raw/<doc_id>/<int:start>/<int:end>")
    def api_raw(doc_id: str, start: int, end: int):
        st = store()
        if start < 1 or end < start or end - start > 200:
            abort(400, description="行范围不合法（单次最多 200 行）")
        lines = st.canonical_lines(doc_id, start, end)
        if lines is None:
            abort(404, description="该文档无 canonical 原文")
        return jsonify({"lines": lines})

    @app.get("/api/kg/<doc_id>")
    def api_kg(doc_id: str):
        scope = request.args.get("scope", "core")
        if scope not in ("core", "full"):
            abort(400, description="scope 仅支持 core|full")
        st = store()
        meta = st.get_document(doc_id)
        if not meta:
            abort(404, description=f"未知文档: {doc_id}")
        payload = st.get_payload(doc_id)
        if payload is None:
            abort(404, description=f"文档 {doc_id} 无载荷（数据库可能损坏，请重导）")
        kgd = kglib.build_kg(payload, artifact_path=meta.get("ssir_path"))
        if scope == "core":
            keep_ids = {n["id"] for n in kgd["nodes"] if not n.get("CE")}
            nodes = [n for n in kgd["nodes"] if n["id"] in keep_ids]
            node_ids = keep_ids
            edges = [
                e
                for e in kgd["edges"]
                if e["from"] in node_ids
                and e["to"] in node_ids
                and not (e["type"] == "CONTAINS_ELEMENT" and e["to"] not in node_ids)
            ]
        else:
            nodes = kgd["nodes"]
            edges = kgd["edges"]
        return jsonify(
            {
                "doc_id": doc_id,
                "scope": scope,
                "document": kgd["document"],
                "nodes": nodes,
                "edges": edges,
                "counts": kgd["counts"],
            }
        )

    @app.get("/asset/<doc_id>/<path:rel>")
    def api_asset(doc_id: str, rel: str):
        st = store()
        meta = st.get_document(doc_id)
        if not meta or not meta.get("asset_root"):
            abort(404)
        asset_root = Path(meta["asset_root"]).resolve()
        docroot = asset_root.parent
        rel_p = Path(rel)
        # 与渲染器同策略：assetRef 常带 assets/ 前缀（相对文档根），向上解析
        candidates = []
        if rel.startswith("assets/"):
            candidates.append(asset_root / str(rel_p.relative_to("assets")))
            candidates.append(docroot / rel)
        candidates.append(asset_root / rel_p)
        if rel_p.is_absolute():
            candidates.append(rel_p)
        for cand in candidates:
            target = cand.resolve()
            if (
                str(target).startswith(str(docroot))
                and target.is_file()
            ):
                mime = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".gif": "image/gif",
                    ".svg": "image/svg+xml",
                }.get(target.suffix.lower(), "application/octet-stream")
                return app.response_class(target.read_bytes(), mimetype=mime)
        abort(404)

    @app.errorhandler(404)
    def not_found(_e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "not found"}), 404
        return render_template("404.html"), 404

    return app
