#!/usr/bin/env python3
"""Replay GEN-114 (表头行数) onto curated canonicals: ``header-rows="1"`` → 表头区跨度。

规则（GEN-114，`mineru_html.html_table_to_csm` 的写入侧同源）：**表头行数 = 首行起点的
最大 rowspan**（表头区的垂直跨度），至少 1 行、至多「表格行数 − 1」（留一行数据，否则
repeatRows 吃掉整表、表永不可分页）。证据是 canonical 自带的 `ssir:table-merge` 指令
（rowspan 直接来自 MinerU HTML，不需要重新抽取），因此回放是**确定性**的：
对每个表，取该表 row="0" 的合并指令里最大的 rowspan。

只改指令行的 `header-rows="N"` 一处属性；其余行必须逐字节不变（脚本自带内容不变量断言），
重复运行零命中（幂等）。

用法：
    .venv/bin/python tools/replay_table_header_rows.py            # 干跑，只列将要改的表
    .venv/bin/python tools/replay_table_header_rows.py --apply    # 写回
    .venv/bin/python tools/replay_table_header_rows.py --apply <canonical.md | 文档根目录>
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 表指令行（含 header-rows 与其它属性）：只重写 header-rows 的值。
TABLE_DIRECTIVE_RE = re.compile(r'^(?P<prefix><!--\s*ssir:table\s+id="(?P<id>[^"]+)")(?P<attrs>[^>]*)-->\s*$')
MERGE_RE = re.compile(r'<!--\s*ssir:table-merge\s+table="([^"]+)"\s+row="(\d+)"\s+column="(\d+)"\s+rowspan="(\d+)"\s+colspan="(\d+)"\s*-->')
ROW_RE = re.compile(r"^\s*\|")


def _header_rows(rows: list[str]) -> int:
    """canonical 文本块 → 表头行数（GEN-114）：首行起点（row="0"）的最大 rowspan。"""
    spans = [int(match.group(4)) for match in MERGE_RE.finditer("\n".join(rows)) if match.group(2) == "0"]
    body_rows = sum(1 for line in rows if ROW_RE.match(line)) - 1  # 减去 GFM 分隔行
    return max(1, min(max(spans, default=1), max(body_rows - 1, 1)))


def replay(path: Path, *, apply: bool) -> list[tuple[str, int, int]]:
    """单个 canonical → [(表 id, 旧值, 新值)]；apply 时写回。"""
    original = path.read_text(encoding="utf-8")
    lines = original.split("\n")
    changes: list[tuple[str, int, int]] = []
    # 先按表指令切块（指令行到下一个指令行为止）。
    blocks: list[tuple[int, str, list[str]]] = []
    current: tuple[int, str, list[str]] | None = None
    for index, line in enumerate(lines):
        match = TABLE_DIRECTIVE_RE.match(line)
        if match:
            if current:
                blocks.append(current)
            current = (index, match.group("id"), [])
            continue
        if current is not None:
            current[2].append(line)
    if current:
        blocks.append(current)
    for index, table_id, rows in blocks:
        directive = TABLE_DIRECTIVE_RE.match(lines[index])
        assert directive is not None
        attrs = directive.group("attrs")
        match = re.search(r'header-rows="(\d+)"', attrs)
        if not match:
            continue
        old = int(match.group(1))
        new = _header_rows(rows)
        if new != old:
            changes.append((table_id, old, new))
            if apply:
                lines[index] = lines[index].replace(f'header-rows="{old}"', f'header-rows="{new}"', 1)
    if apply and changes:
        updated = "\n".join(lines)
        # 内容不变量：除指令行的 header-rows 属性外，其余逐字节不变。
        strip = lambda text: re.sub(r'header-rows="\d+"', 'header-rows="#"', text)
        assert strip(original) == strip(updated), f"{path}: 回放改动了指令行以外的内容"
        path.write_text(updated, encoding="utf-8")
    return changes


def _targets(args: list[str]) -> list[Path]:
    if args:
        paths: list[Path] = []
        for raw in args:
            path = Path(raw)
            if path.is_dir():
                paths.extend(sorted(path.glob("02_canonical/*.canonical.md")) or sorted(path.glob("*.canonical.md")))
            else:
                paths.append(path)
        return paths
    # canonical 与 raw 同源回放：raw.md 是 normalize 的上游——只改 canonical 的话，任何
    # 一次合法的 normalize 重跑都会用旧 raw 的 header-rows 覆盖回去（实测 2026-09-19：
    # 并发会话在 07:32 重跑 normalize，canonical 的 12 处回放被覆盖）。
    return sorted(ROOT.glob("out/mineru/*/02_canonical/*.canonical.md")) + sorted(
        ROOT.glob("out/mineru/*/01_extract/*.raw.md")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", help="canonical 文件或文档根目录（默认全部 out/mineru/*）")
    parser.add_argument("--apply", action="store_true", help="写回 canonical（默认只报告）")
    options = parser.parse_args()
    total = 0
    for path in _targets(options.paths):
        if not path.is_file():
            print(f"skip (not a file): {path}", file=sys.stderr)
            continue
        changes = replay(path, apply=options.apply)
        total += len(changes)
        for table_id, old, new in changes:
            print(f"{'write' if options.apply else 'would write'} {path.parent.parent.name:26s} {table_id:26s} header-rows {old} → {new}")
    print(f"{'applied' if options.apply else 'dry run'}: {total} table(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
