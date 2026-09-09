#!/usr/bin/env python3
"""kg_tool —— 知识图谱阶段 P1a/P1c 命令行入口。

子命令：
  build   <ssir.json>  [-o out.kg.json]    SSIR → kg.json 图切片（+schema 校验）
  import  <ID|路径> [--all] [--db out/kg/kg.db]   文档导入 sqlite（可重建索引）
  list    [--db out/kg/kg.db]              列出库中文档
  serve   [--db out/kg/kg.db] [--port 8600] 启动 Web 查看器（列表/浏览/图谱）

示例：
  .venv/bin/python tools/kg_tool.py build out/mineru/GB_T_1.1-2020/03_ssir/GB_T_1.1-2020.ssir.json
  .venv/bin/python tools/kg_tool.py import GB_T_1.1-2020
  .venv/bin/python tools/kg_tool.py import --all
  .venv/bin/python tools/kg_tool.py serve          # http://127.0.0.1:8600
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO / "out" / "kg" / "kg.db"


def _resolve_ssir(arg: str) -> Path:
    """ID 快捷解析（out/mineru/<ID>/03_ssir/<ID>.ssir.json）或显式路径。"""
    p = Path(arg)
    if p.exists() and p.is_file():
        return p
    # 快捷模式：ID → 03_ssir 目录
    cand = REPO / "out" / "mineru" / arg / "03_ssir" / f"{arg}.ssir.json"
    if cand.exists():
        return cand
    # 带/不带 .ssir.json 的文件名解析
    for name in (f"{arg}.ssir.json", arg):
        cand = REPO / "out" / "mineru" / name
        if cand.exists():
            return cand
    raise SystemExit(f"找不到 SSIR 输入: {arg}\n（ID 快捷模式查找 {cand}）")


def _scan_all() -> list[Path]:
    found = sorted((REPO / "out" / "mineru").glob("*/03_ssir/*.ssir.json"))
    if not found:
        raise SystemExit("out/mineru/ 下未找到任何 03_ssir/*.ssir.json")
    return found


def cmd_build(args: argparse.Namespace) -> int:
    from leleby_ssir import kg  # noqa: PLC0415

    src = _resolve_ssir(args.input)
    doc = json.loads(src.read_text(encoding="utf-8"))
    kgd = kg.build_kg(doc, artifact_path=str(src))
    out = Path(args.output) if args.output else src.with_name(f"{src.stem}.kg.json")
    if out.suffix != ".json":
        out = out.with_suffix(".json")
    out.write_text(json.dumps(kgd, ensure_ascii=False, indent=1), encoding="utf-8")
    errs = kg.validate_kg(kgd)
    print(f"构建完成: {src}")
    print(f"  输出: {out}")
    print(f"  节点 {len(kgd['nodes'])} · 边 {len(kgd['edges'])} · 分类 {kgd['counts']}")
    status = '通过' if not errs else 'FAIL\\n  ' + chr(10).join(errs)
    print(f"  schema 校验: {status}")
    if kgd["document"].get("references"):
        print(f"  第2章引用 {len(kgd['document']['references'])} 条（示例）:")
        for r in kgd["document"]["references"][:5]:
            print(f"    - {r['standardNumber']}  (clause={r['clause']}, mdLine={r['mdLine']})")
    return 0 if not errs else 2


def cmd_import(args: argparse.Namespace) -> int:
    from leleby_ssir.kgstore import KGDocStore  # noqa: PLC0415

    store = KGDocStore(args.db)
    sources: list[Path]
    if args.all:
        sources = _scan_all()
    else:
        sources = [_resolve_ssir(args.input)]
    total = 0
    for src in sources:
        try:
            summary = store.import_ssir(src)
        except ValueError as exc:
            print(f"跳过 {src}: {exc}", file=sys.stderr)
            continue
        flag = "更新" if summary["replaced"] else "新增"
        print(
            f"[{flag}] {summary['doc_id']:<24} 节点 {summary['node_count']:<5} "
            f"内容 {summary['ce_count']:<5} payload {summary['payload_kb']:>7} KB"
        )
        total += 1
    print(f"完成：共 {total} 份文档入库 -> {args.db}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    from leleby_ssir.kgstore import KGDocStore  # noqa: PLC0415

    store = KGDocStore(args.db)
    rows = store.list_documents()
    if not rows:
        print("（空库）")
        return 0
    for d in rows:
        print(
            f"{d['standard_number']:<22} {d['doc_id']:<26} "
            f"{(d['chinese_title'] or '')[:40]:<40} 节点 {d['node_count']}"
        )
    print(f"共 {len(rows)} 份")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(Path(__file__).parent))
    from kg_viewer import create_app  # noqa: PLC0415

    app = create_app(args.db)
    url = f"http://{args.host}:{args.port}"
    print(f"kg_viewer 启动: {url}")
    print(f"  文档库    {url}/")
    print(f"  文档浏览  {url}/doc/<doc_id>    例: {url}/doc/GB_T_1.1-2020")
    print(f"  本体图谱  {url}/graph/<doc_id>  例: {url}/graph/GB_T_1.1-2020")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="kg_tool", description="标准知识图谱 P1a/P1c 命令行工具"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_b = sub.add_parser("build", help="SSIR → kg.json")
    p_b.add_argument("input", help="ssir.json 路径或标准 ID")
    p_b.add_argument("-o", "--output", help="kg.json 输出路径（默认同目录）")
    p_b.set_defaults(fn=cmd_build)

    p_i = sub.add_parser("import", help="导入 sqlite 索引库")
    p_i.add_argument("input", nargs="?", help="标准 ID 或 ssir.json 路径（--all 时忽略）")
    p_i.add_argument("--all", action="store_true", help="扫描 out/mineru/*/03_ssir/ 全量导入")
    p_i.add_argument("--db", default=str(DEFAULT_DB))
    p_i.set_defaults(fn=cmd_import)

    p_l = sub.add_parser("list", help="列出库中文档")
    p_l.add_argument("--db", default=str(DEFAULT_DB))
    p_l.set_defaults(fn=cmd_list)

    p_s = sub.add_parser("serve", help="启动 Web 查看器")
    p_s.add_argument("--db", default=str(DEFAULT_DB))
    p_s.add_argument("--host", default="127.0.0.1")
    p_s.add_argument("--port", type=int, default=8600)
    p_s.set_defaults(fn=cmd_serve)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
