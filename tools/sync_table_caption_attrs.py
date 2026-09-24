#!/usr/bin/env python3
"""规则实例回放：canonical 里表/图题注与单位属性 → 对齐**可见文字**（GEN-139，docs/12 §3.88）。

判据单源：`leleby_ssir.parser`（同一函数路径解析该文件后，指令上的
`caption-number`/`caption`/`unit` 已是可见文字的值）。本工具把这一判据
**确定性地**回放到既有 canonical 文件：把属性值改成可见文字的值，使文件与成品一致。

- 干跑（默认）：逐文件列出 `行号 | 表/图 id | 属性 | 旧值 → 新值`，并给汇总。
- `--apply`：就地改写（写前留 `.bak-caption-attr`），四重断言——
  ① 行数不变；② 每个指令行只改 GEN-139 三个属性键的值、其余字节不变；
  ③ 幂等（再跑一次 0 处改动）；④ 改后重 parse 的 `CSM-TABLE-005` 为 0。
- 只替换**既有**属性值，不新增/删除属性键（宁少改不多改）。

用法:
    tools/sync_table_caption_attrs.py                     # 干跑全部 canonical
    tools/sync_table_caption_attrs.py <文件…>             # 干跑指定文件
    tools/sync_table_caption_attrs.py --apply [<文件…>]   # 回放
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leleby_ssir.parser import CSMParser  # noqa: E402

KEYS = ("caption-number", "caption", "unit")
DIRECTIVE_RE = re.compile(r"^<!--\s*ssir:(?:table|figure)\b(.*?)-->\s*$")
ATTR_RE = re.compile(r'([A-Za-z][\w-]*)="([^"]*)"')


def default_targets() -> list[Path]:
    roots = [Path("out/mineru")] + ([Path("canonical")] if Path("canonical").is_dir() else [])
    files: list[Path] = []
    for root in roots:
        files.extend(sorted(root.glob("*/02_canonical/*.canonical.md")))
        files.extend(sorted(root.glob("*.canonical.md")))
    return files


def parsed_attrs(path: Path) -> tuple[dict[str, dict[str, str]], int]:
    """解析该文件：{指令 id: 指令属性}（属性值已是可见文字的值）+ CSM-TABLE-005 计数。"""
    document = CSMParser().read(path)
    attrs: dict[str, dict[str, str]] = {}
    for block in document.blocks:
        if block.kind in {"table", "figure"} and block.directive:
            ident = block.directive.attrs.get("id")
            if ident:
                attrs[ident] = block.directive.attrs
    hits = sum(1 for issue in document.issues if issue.code == "CSM-TABLE-005")
    return attrs, hits


def plan(path: Path) -> list[tuple[int, str, str, str, str]]:
    """[(行号, id, 属性, 文件里的旧值, 可见文字的新值)]，按行号排序。"""
    targets, _ = parsed_attrs(path)
    changes: list[tuple[int, str, str, str, str]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").split("\n"), start=1):
        match = DIRECTIVE_RE.match(line)
        if not match:
            continue
        found = dict(ATTR_RE.findall(match.group(1)))
        target = targets.get(found.get("id", ""))
        if not target:
            continue
        for key in KEYS:
            new = target.get(key)
            # 只回放**既有**属性值：文件里没有该键时不新增（可见文字行本身已能供值，
            # 新增键只会让两个表示再次分叉）。
            if key in found and new and found[key] != new:
                changes.append((index, found["id"], key, found[key], new))
    return changes


def rewrite_line(line: str, changes: dict[str, tuple[str, str]]) -> str:
    def replace(match: re.Match[str]) -> str:
        key, value = match.group(1), match.group(2)
        if key in changes and changes[key][0] == value:
            return f'{key}="{changes[key][1]}"'
        return match.group(0)

    return ATTR_RE.sub(replace, line)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", type=Path, help="canonical 文件（默认：全部 out/mineru/*/02_canonical 与 canonical/）")
    parser.add_argument("--apply", action="store_true", help="就地回放（写前留 .bak-caption-attr）")
    args = parser.parse_args()

    files = args.files or default_targets()
    total = 0
    touched = 0
    for path in files:
        if not path.exists():
            print(f"跳过（不存在）：{path}")
            continue
        changes = plan(path)
        if not changes:
            continue
        touched += 1
        total += len(changes)
        print(f"{path}：{len(changes)} 处")
        for line_no, ident, key, old, new in changes:
            print(f"   L{line_no} {ident} {key}: {old!r} → {new!r}")
    if not args.apply:
        print(f"\n干跑：{touched} 个文件、{total} 处待回放（加 --apply 落地）")
        return 0

    for path in files:
        if not path.exists():
            continue
        changes = plan(path)
        if not changes:
            continue
        by_line: dict[int, dict[str, tuple[str, str]]] = {}
        for line_no, _ident, key, old, new in changes:
            by_line.setdefault(line_no, {})[key] = (old, new)
        lines = path.read_text(encoding="utf-8").split("\n")
        for line_no, items in by_line.items():
            lines[line_no - 1] = rewrite_line(lines[line_no - 1], items)
        before_lines = path.read_text(encoding="utf-8").split("\n")
        assert len(lines) == len(before_lines), f"{path}: 行数变了"
        # ② 只改 GEN-139 的键值：去掉三键后逐行比对
        stripped_old = [re.sub(r'(?:caption-number|caption|unit)="[^"]*"', "", l) for l in before_lines]
        stripped_new = [re.sub(r'(?:caption-number|caption|unit)="[^"]*"', "", l) for l in lines]
        assert stripped_old == stripped_new, f"{path}: 改动了 GEN-139 之外的字节"
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak-caption-attr"))
        path.write_text("\n".join(lines), encoding="utf-8")
        # ③④ 幂等 + 改后无残留告警
        assert plan(path) == [], f"{path}: 回放不幂等"
        _attrs, hits = parsed_attrs(path)
        assert hits == 0, f"{path}: 回放后仍有 {hits} 处 CSM-TABLE-005"
        print(f"已回放 {path}（{len(changes)} 处；备份 .bak-caption-attr）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
