"""kg SQLite 层（P1a：标准元数据 + 结构树索引 + 全文载荷）。

设计原则（docs/semantic_Stage/ 规划 v0.1 §2.3/§4.2/§6 阶段1）：
- **文件 SSIR JSON 是唯一真源**；本库只是"可重建索引/缓存"——文档重跑（hash 变化）
  后一键重导即可，绝不手工编辑。
- 不做全量 EAV 规范化：documents 存整篇载荷 JSON1（浏览渲染按需解析），
  structure 只落**扁平结构树**（id/parent/number/title/md 行）供树导航 SQL。
- 内容元素（段落/注/列表/表图公式引用）渲染时直接从 payload 取——树行不重复落。
- 代码层以 KGDocStore 类抽象；未来切 PostgreSQL 时替换该类的 SQL 方言/连接即可
  （当前 MVP 单人工作站用 sqlite3 标准库，不引入 SQLAlchemy）。
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id          TEXT PRIMARY KEY,
    standard_number TEXT,
    chinese_title   TEXT,
    document_type   TEXT,
    ics             TEXT,
    ccs             TEXT,
    replaces        TEXT,
    meta_json       TEXT,
    ssir_path       TEXT,
    canonical_path  TEXT,
    asset_root      TEXT,
    file_hash       TEXT,
    imported_at     TEXT,
    node_count      INTEGER,
    ce_count        INTEGER,
    payload_json    TEXT
);
CREATE TABLE IF NOT EXISTS structure (
    id            TEXT PRIMARY KEY,
    doc_id        TEXT NOT NULL,
    parent_id     TEXT,
    node_type     TEXT,
    number        TEXT,
    title         TEXT,
    term          TEXT,
    english_term  TEXT,
    level         INTEGER,
    sort_order    INTEGER,
    md_start_line INTEGER,
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_structure_doc    ON structure(doc_id);
CREATE INDEX IF NOT EXISTS idx_structure_parent ON structure(doc_id, parent_id);
CREATE INDEX IF NOT EXISTS idx_structure_number ON structure(doc_id, number);
"""

_DOC_COLS = (
    "doc_id, standard_number, chinese_title, document_type, ics, ccs, replaces, "
    "meta_json, ssir_path, canonical_path, asset_root, file_hash, imported_at, "
    "node_count, ce_count, payload_json"
)

_DOC_LIST_COLS = (
    "doc_id, standard_number, chinese_title, document_type, ics, ccs, replaces, "
    "file_hash, imported_at, node_count"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class KGDocStore:
    """文档索引库：导入/查询/删除，全部方法自开自关连接（线程安全）。"""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA_SQL)
            try:
                conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.DatabaseError:
                pass

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ---------- 导入/删除 ----------

    def import_ssir(self, ssir_path: str | Path) -> dict:
        """导入一份 SSIR JSON（重建其全部 structure 行）。返回摘要 dict。"""
        p = Path(ssir_path)
        data = p.read_bytes()
        try:
            doc = json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError(f"非法 SSIR JSON: {p} ({exc})") from exc
        meta = (doc.get("metadata") or {}).get("standard") or {}
        common = (doc.get("metadata") or {}).get("common") or {}
        standard_number = meta.get("standardNumber") or ""
        try:
            from leleby_ssir.naming import standard_filename  # noqa: PLC0415

            doc_id = standard_filename(standard_number)
        except Exception:  # pragma: no cover - 兜底（命名规则：斜杠→下划线、大写）
            doc_id = standard_number.replace("/", "_").replace(" ", "_").upper()

        base = p.name[: -len(".ssir.json")] if p.name.endswith(".ssir.json") else p.stem
        docroot = p.parent.parent
        canonical = docroot / "02_canonical" / f"{base}.canonical.md"
        asset_root = docroot / "assets"

        rows = []  # (id, parent_id, node_type, number, title, term, en, level, sort, mdline)
        ce_count = 0

        def walk(node: dict, parent_id: Optional[str]):
            nonlocal ce_count
            cels = node.get("contentElements") or []
            ce_count += len(cels)
            anchor = None
            for a in node.get("sourceAnchors") or []:
                if a.get("anchorType") == "markdown":
                    anchor = a
                    break
            title = node.get("title")
            term = node.get("term")
            rows.append((
                node["id"], parent_id, node.get("nodeType"),
                node.get("number"),
                (title[:400] + "…") if isinstance(title, str) and len(title) > 400 else title,
                term, node.get("englishTerm"),
                node.get("level"), node.get("sortOrder"),
                anchor.get("markdownStartLine") if anchor else None,
            ))
            for child in node.get("children") or []:
                walk(child, node["id"])

        root = doc.get("structuralRoot") or {}
        if not root:
            raise ValueError(f"SSIR 无 structuralRoot: {p}")
        walk(root, None)

        hash_value = _sha256(data)
        meta_json = json.dumps({"standard": meta, "common": common}, ensure_ascii=False)
        replaced = False
        with self._connect() as conn:
            cur = conn.execute("SELECT 1 FROM documents WHERE doc_id=?", (doc_id,))
            replaced = cur.fetchone() is not None
            conn.execute(
                "DELETE FROM structure WHERE doc_id=?", (doc_id,)
            )
            # 重导既有文档：先删 documents 行（FK ON DELETE CASCADE 连带清 structure），
            # 再普通 INSERT。不用 INSERT OR REPLACE——documents 是被 structure 级联
            # 引用的父表，REPLACE 的内部删除在 WAL 下会以 "unable to open database
            # file" 失败（重导路径实测必现：首次导入空库可行、同 doc_id 再导即失败）。
            conn.execute("DELETE FROM documents WHERE doc_id=?", (doc_id,))
            placeholders = ",".join("?" * (len(_DOC_COLS.split(","))))
            conn.execute(
                f"INSERT INTO documents ({_DOC_COLS}) VALUES ({placeholders})",
                (
                    doc_id, standard_number,
                    meta.get("chineseTitle") or common.get("title"),
                    doc.get("documentType"), meta.get("ics"), meta.get("ccs"),
                    meta.get("replaces"), meta_json, str(p),
                    str(canonical) if canonical.exists() else None,
                    str(asset_root) if asset_root.is_dir() else None,
                    hash_value, _now_iso(), len(rows), ce_count,
                    data.decode("utf-8"),
                ),
            )
            conn.executemany(
                "INSERT INTO structure (id, doc_id, parent_id, node_type, number, "
                "title, term, english_term, level, sort_order, md_start_line) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [(r[0], doc_id, *r[1:]) for r in rows],
            )
        return {
            "doc_id": doc_id,
            "standard_number": standard_number,
            "chinese_title": meta.get("chineseTitle") or common.get("title"),
            "node_count": len(rows),
            "ce_count": ce_count,
            "payload_kb": round(len(data) / 1024, 1),
            "replaced": replaced,
        }

    def delete_document(self, doc_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM documents WHERE doc_id=?", (doc_id,))
            return cur.rowcount > 0

    def clear(self):
        with self._connect() as conn:
            conn.execute("DELETE FROM structure")
            conn.execute("DELETE FROM documents")

    # ---------- 查询 ----------

    def list_documents(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT {_DOC_LIST_COLS} FROM documents ORDER BY standard_number"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_document(self, doc_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT {_DOC_LIST_COLS}, ssir_path, canonical_path, asset_root, "
                f"meta_json FROM documents WHERE doc_id=?", (doc_id,)
            ).fetchone()
        return dict(row) if row else None

    def all_rows(self, doc_id: str) -> list[dict]:
        """结构树全量行（含 parent_id），供前端内存建树。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, parent_id, node_type, number, title, term, english_term, "
                "level, sort_order, md_start_line FROM structure WHERE doc_id=? "
                "ORDER BY COALESCE(sort_order, 0), number",
                (doc_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_row(self, doc_id: str, node_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, parent_id, node_type, number, title, term, english_term, "
                "level, sort_order, md_start_line FROM structure "
                "WHERE doc_id=? AND id=?",
                (doc_id, node_id),
            ).fetchone()
        return dict(row) if row else None

    def get_children(self, doc_id: str, parent_id: Optional[str]) -> list[dict]:
        """某结构节点的直接子节点（含根：parent_id 传文档根节点 id；根自身 parent NULL）。"""
        with self._connect() as conn:
            if parent_id is None:
                rows = conn.execute(
                    "SELECT id, node_type, number, title, term, level, sort_order, "
                    "md_start_line, (SELECT COUNT(*) FROM structure c WHERE c.parent_id=s.id) "
                    "AS child_count FROM structure s WHERE doc_id=? AND parent_id IS NULL "
                    "ORDER BY COALESCE(sort_order, 0), number",
                    (doc_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, node_type, number, title, term, level, sort_order, "
                    "md_start_line, (SELECT COUNT(*) FROM structure c WHERE c.parent_id=s.id) "
                    "AS child_count FROM structure s WHERE doc_id=? AND parent_id=? "
                    "ORDER BY COALESCE(sort_order, 0), number",
                    (doc_id, parent_id),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_payload(self, doc_id: str) -> Optional[dict]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM documents WHERE doc_id=?", (doc_id,)
            ).fetchone()
        return json.loads(row["payload_json"]) if row else None

    def canonical_lines(self, doc_id: str, start: int, end: int) -> Optional[list[dict]]:
        doc = self.get_document(doc_id)
        if not doc or not doc.get("canonical_path"):
            return None
        path = Path(doc["canonical_path"])
        if not path.exists():
            return None
        lines = path.read_text(encoding="utf-8").splitlines()
        s, e = max(1, start), min(len(lines), end)
        return [{"line": i, "text": lines[i - 1]} for i in range(s, e + 1)]
