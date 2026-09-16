#!/usr/bin/env python3
"""从设计文档提取可执行 JSON Schema —— **默认只比对，不写入**。

背景（2026-09-12，本轮实测）：
`src/leleby_ssir/ssir.schema.json` 是引擎的**执行侧** Schema，它已经比设计稿
`docs/02_leleby SSIR JSON Schema Specification v0.3.md` 更新——设计稿里没有
`box` / `boxStyle` / `exampleContent` / `englishTerm` / `term` / `sideBySide*` /
`sourceWidth` / `footnoteMarker` 等后续新增属性。而本脚本旧版是「无参数即写入」，
一次 `--help` 巡查就把它按设计稿重生成，静默删掉 107 行属性声明，直接导致
`csm normalize/parse` 与 13 个单测因 `Additional properties are not allowed` 失败。

因此现在的约定：

- **不带 `--write`**：只把设计稿里的 Schema 与目标文件比对，打印差异摘要（安全默认）；
- **`--write`**：先比对；若目标文件存在设计稿没有的属性（会被删除），**拒绝写入**并列出
  这些属性，除非同时给 `--force`（明确知道要丢弃执行侧新增属性时才用）。

用法::

    python tools/extract_schema.py                      # 只比对
    python tools/extract_schema.py --write              # 目标不含额外属性时才写入
    python tools/extract_schema.py --write --force      # 强制按设计稿覆盖
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "02_leleby SSIR JSON Schema Specification v0.3.md"
TARGET = ROOT / "src" / "leleby_ssir" / "ssir.schema.json"


def schema_from_design_document(source: Path) -> dict:
    """取出设计文档里第一段 ```json 代码块作为 Schema。"""
    text = source.read_text(encoding="utf-8")
    start = text.index("```json") + len("```json")
    end = text.index("```", start)
    return json.loads(text[start:end])


def _property_names(schema: dict) -> set[str]:
    """递归收集 Schema 里声明的所有属性名（用于「会不会删掉现有属性」的判定）。"""
    names: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                names.update(str(key) for key in properties)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(schema)
    return names


def compare(design: dict, target: dict) -> tuple[set[str], set[str]]:
    """返回（设计稿有而目标没有的属性, 目标有而设计稿没有的属性）。"""
    design_names, target_names = _property_names(design), _property_names(target)
    return design_names - target_names, target_names - design_names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--write", action="store_true", help="比对通过后把设计稿 Schema 写入目标文件")
    parser.add_argument("--force", action="store_true", help="即使会删除目标文件里已有的属性也写入")
    parser.add_argument("--source", type=Path, default=SOURCE, help=f"设计文档（默认 {SOURCE.name}）")
    parser.add_argument("--target", type=Path, default=TARGET, help=f"目标 Schema（默认 {TARGET.name}）")
    args = parser.parse_args(argv)

    try:
        design = schema_from_design_document(args.source)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: 无法从 {args.source} 提取 Schema：{exc}", file=sys.stderr)
        return 2

    target: dict = {}
    if args.target.is_file():
        try:
            target = json.loads(args.target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: 无法读取 {args.target}：{exc}", file=sys.stderr)
            return 2

    missing_in_target, extra_in_target = compare(design, target)
    if target:
        print(f"设计稿：{len(_property_names(design))} 个属性；目标文件：{len(_property_names(target))} 个属性")
        if missing_in_target:
            print(f"  设计稿有、目标没有（写入后会新增）：{len(missing_in_target)} 个")
        if extra_in_target:
            print(f"  目标有、设计稿没有（写入后会删除）：{sorted(extra_in_target)}")

    if not args.write:
        print("只比对，未写入（需要写入请加 --write）")
        return 0

    if extra_in_target and not args.force:
        print("error: 拒绝写入——目标文件的这些属性不在设计稿里，按设计稿重生成会把它们删掉："
              f"{sorted(extra_in_target)}\n"
              "       执行侧 Schema 通常比设计稿新；确实要按设计稿覆盖请加 --force。", file=sys.stderr)
        return 2

    args.target.parent.mkdir(parents=True, exist_ok=True)
    args.target.write_text(json.dumps(design, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已写入 {args.target}（删除属性 {len(extra_in_target)} 个，新增 {len(missing_in_target)} 个）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
