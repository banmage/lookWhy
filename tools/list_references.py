#!/usr/bin/env python3
"""列出某个标准的规范性引用文件（＋本文内部引用点），精确到具体条款/图/表/公式。

读既有 SSIR 产物（或 canonical，现场 parse），**只读不写**：不改 canonical、不重跑构建。

用法::

    # 裸标准 ID（默认文档根 out/mineru/<ID>，优先 03_ssir/*.ssir.json）
    .venv/bin/python tools/list_references.py GB_T_1.1-2020

    # 只看某个被引标准（按标识或标准号模糊匹配；可反复指定）
    .venv/bin/python tools/list_references.py GB_T_1.1-2020 --standard 3101 --standard 20001.10

    # 连资料性引用（注/示例/前言/参考文献里的提及）一起列出
    .venv/bin/python tools/list_references.py GB_T_1.1-2020 --include-informative

    # 文档根 / canonical / SSIR 文件都可作输入，输出结构化 JSON
    .venv/bin/python tools/list_references.py out/mineru/GB_T_1.1-2020 --json

退出码：``0`` 正常；``2`` 用法/引擎错误。

规则对应：GB/T 1.1-2020 8.6（规范性引用文件清单）、9.5.4（引用的表示）、9.9.2（公式引用）；
TDRS 设计说明 v2.0「标准中规范性引用文件的管理」§二/§三/§四（六元组、SSIR.references、
第 2 章清单为主来源 + 全文扫描为补充）。抽取实现见 ``leleby_ssir.references``。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leleby_ssir.references import format_summary, format_target_view, query_target, summarise  # noqa: E402
from leleby_ssir.service import parse_csm  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SSIR_DIR = "03_ssir"
CANONICAL_DIR = "02_canonical"


def _candidates(arg: str) -> list[Path]:
    path = Path(arg)
    if path.is_file():
        return [path]
    if path.is_dir():
        name = path.name
        return [
            path / SSIR_DIR / f"{name}.ssir.json",
            path / CANONICAL_DIR / f"{name}.canonical.md",
        ]
    docroot = ROOT / "out" / "mineru" / arg
    return [
        docroot / SSIR_DIR / f"{arg}.ssir.json",
        docroot / CANONICAL_DIR / f"{arg}.canonical.md",
        path / f"{arg}.ssir.json",
        path / f"{arg}.canonical.md",
    ]


def _load(arg: str) -> tuple[dict, Path]:
    tried: list[Path] = []
    for candidate in _candidates(arg):
        tried.append(candidate)
        if not candidate.exists():
            continue
        if candidate.suffix.lower() == ".json":
            return json.loads(candidate.read_text(encoding="utf-8")), candidate
        return parse_csm(candidate), candidate
    raise FileNotFoundError("找不到输入：" + "、".join(str(path) for path in tried))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="列出标准的规范性引用文件（精确到条款/图/表/公式）")
    parser.add_argument("input", help="标准 ID / 文档根目录 / canonical.md / ssir.json")
    parser.add_argument("--standard", action="append", default=[], help="只看匹配的被引标准（可多次）")
    parser.add_argument("--include-informative", action="store_true", help="连资料性引用一起列出")
    parser.add_argument("--no-internal", action="store_true", help="不列本文内部引用点（表/图/公式/条款）")
    parser.add_argument("--target", action="append", default=[], metavar="表1|图2|式(3)",
                        help="关系查询：某本文目标（表/图/公式/条款）被哪些条款引用（可多次）")
    parser.add_argument("--json", action="store_true", help="输出结构化 JSON（六元组视图）")
    args = parser.parse_args(argv)
    try:
        document, path = _load(args.input)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if "references" not in document:
        print(
            f"提示：{path} 没有 references 键（该产物早于引用抽取）——"
            "用 tools/build_ssir.py 重跑该文档即可产出；或直接把 canonical 作为输入现场解析。",
            file=sys.stderr,
        )
    summary = summarise(document)
    if args.json:
        payload: object = summary
        if args.target:
            payload = {"targets": {target: query_target(summary, target) for target in args.target}}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    header = f"来源产物：{path}"
    if args.target:
        print(header)
        print(format_target_view(summary, args.target))
        return 0
    lines: list[str] = []
    for needle in args.standard or [None]:
        lines.append(format_summary(
            summary,
            standard=needle,
            include_informative=args.include_informative,
            include_internal=not args.no_internal,
        ))
    print(header)
    print("\n\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
