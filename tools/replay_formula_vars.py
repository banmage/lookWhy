#!/usr/bin/env python3
"""canonical 标记回放（第二族：式中解释组）——AGENTS.md §0.4。

把 `式中：` 之后的连续解释行括进 `<!-- ssir:formula-vars formula="…" -->` … `<!-- ssir:/formula-vars -->`。

规则与判据：
- 条目判据**复用 parser 的 `EXPLANATION_ITEM_RE`**（判据单源，不在本工具另写一份）；
- 归属：取该组之前**最近的 `ssir:formula` 指令的 id**；取不到则不写 `formula=` 属性
  （parser 缺省即「最近一个公式」，确定而非猜测）；
- 组界：从 `式中：` 起，跳过空行，连续解释行（空行可分隔）到首个不匹配行止。

三重断言：
① **内容不变量**——只插入指令行，其余字节逐字节不变；
② **幂等**——已括起的组 0 改动；
③ **解析校验**——改写后可 parse 且 `validate_ssir` 通过，且解释条目总数 = 被括行非空行数（不丢行）。

用法：
    .venv/bin/python tools/replay_formula_vars.py [--apply] [文件…]
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from leleby_ssir.parser import EXPLANATION_ITEM_RE  # noqa: E402
from leleby_ssir.service import parse_csm  # noqa: E402
from leleby_ssir.validation import validate_ssir  # noqa: E402

VARS_OPEN_PREFIX = "<!-- ssir:formula-vars"
VARS_CLOSE = "<!-- ssir:/formula-vars -->"
VAR_LEAD = "式中"
FORMULA_DIRECTIVE_RE = re.compile(r"<!--\s*ssir:formula\b(?P<attrs>[^>]*)-->")
DIRECTIVE_ID_RE = re.compile(r'id\s*=\s*"(?P<id>[^"]+)"')


def _is_inserted(line: str) -> bool:
    stripped = line.strip()
    return stripped == VARS_CLOSE or stripped.startswith(VARS_OPEN_PREFIX)


def _is_item(line: str) -> bool:
    """条目判据（单源复用 parser 的正则）；指令/标记行永不算条目。"""
    stripped = line.strip()
    if stripped.startswith("<!--") or stripped.startswith("```"):
        return False
    return bool(EXPLANATION_ITEM_RE.match(stripped))


def _find_groups(lines: list[str]) -> list[tuple[int, int, str]]:
    """返回 [(组首行 index, 组尾行 index, formula id)]（0-based，含端点）。"""
    groups: list[tuple[int, int, str]] = []
    index = 0
    while index < len(lines):
        if not lines[index].strip().startswith(VAR_LEAD):
            index += 1
            continue
        head = index + 1
        while head < len(lines) and not lines[head].strip():
            head += 1
        if head >= len(lines):
            break
        if lines[head].strip().startswith(VARS_OPEN_PREFIX):
            index = head + 1
            continue
        if not _is_item(lines[head]):
            index += 1
            continue
        tail = head
        cursor = head
        while cursor < len(lines):
            candidate = lines[cursor].strip()
            if not candidate:
                lookahead = cursor + 1
                while lookahead < len(lines) and not lines[lookahead].strip():
                    lookahead += 1
                following = lines[lookahead].strip() if lookahead < len(lines) else ""
                if following and _is_item(following):
                    cursor = lookahead
                    continue
                break
            if not _is_item(candidate):
                break
            tail = cursor
            cursor += 1
        formula_id = ""
        for probe in range(index - 1, -1, -1):
            match = FORMULA_DIRECTIVE_RE.search(lines[probe])
            if match:
                id_match = DIRECTIVE_ID_RE.search(match.group("attrs"))
                formula_id = id_match.group("id") if id_match else ""
                break
        groups.append((head, tail, formula_id))
        index = tail + 1
    return groups


def _wrapped_groups(lines: list[str]) -> list[list[str]]:
    groups: list[list[str]] = []
    current: list[str] | None = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(VARS_OPEN_PREFIX):
            current = []
            continue
        if stripped == VARS_CLOSE:
            if current is not None:
                groups.append([line for line in current if line.strip()])
            current = None
            continue
        if current is not None:
            current.append(line)
    return groups


def _verified_parse(text: str) -> dict:
    handle = tempfile.NamedTemporaryFile("w", suffix=".canonical.md", delete=False, encoding="utf-8")
    handle.write(text)
    handle.close()
    path = Path(handle.name)
    try:
        result = parse_csm(path)
        validate_ssir(result)
        return result
    finally:
        path.unlink(missing_ok=True)


def replay(path: Path, apply: bool = False) -> tuple[int, list[str]]:
    original_text = path.read_text(encoding="utf-8")
    lines = original_text.split("\n")
    groups = _find_groups(lines)
    if not groups:
        return 0, ["无「式中：」解释组（跳过）"]
    insertions: list[tuple[int, str]] = []
    notes: list[str] = []
    for head, tail, formula_id in groups:
        attrs = f' formula="{formula_id}"' if formula_id else ""
        insertions.append((tail + 1, VARS_CLOSE))
        insertions.append((head, f"{VARS_OPEN_PREFIX}{attrs} -->"))
        notes.append(
            f"式中组 行 {head + 1}..{tail + 1}（{tail - head + 1} 行，"
            f"formula={formula_id or '最近一公式'}）"
        )
    updated = list(lines)
    for position, text in sorted(insertions, reverse=True):
        updated.insert(position, text)
    new_text = "\n".join(updated)

    # 断言 ①：内容不变量
    stripped = [line for line in updated if not _is_inserted(line)]
    if "\n".join(stripped) != original_text:
        raise SystemExit(f"{path.name}: 内容不变量失败（除插入指令外还有改动）")

    # 断言 ③：解析校验 + 不丢行
    checked = _verified_parse(new_text)
    expected = sum(len(group) for group in _wrapped_groups(updated))
    actual = sum(
        len(formula.get("explanationGroup", {}).get("items") or [])
        for formula in checked.get("formulas") or []
    )
    if actual != expected:
        raise SystemExit(f"{path.name}: 式中条目 {actual} ≠ 被括行数 {expected}（丢行）")
    notes.append(f"→ explanationGroup 条目 {actual} 条")

    if apply:
        path.write_text(new_text, encoding="utf-8")
    return len(insertions), notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="canonical 标记回放：式中解释组")
    parser.add_argument("files", nargs="*", help="canonical 文件（缺省 canonical/*.canonical.md）")
    parser.add_argument("--apply", action="store_true", help="写回文件（缺省干跑）")
    options = parser.parse_args(argv)
    targets = [Path(item) for item in options.files] or sorted((ROOT / "canonical").glob("*.canonical.md"))
    total = 0
    failures = 0
    for path in targets:
        try:
            inserted, notes = replay(path, apply=options.apply)
        except Exception as exc:  # noqa: BLE001
            print(f"{path.name}: 失败 {type(exc).__name__}: {exc}")
            failures += 1
            continue
        total += inserted
        state = "改写" if options.apply else "干跑"
        print(f"{path.name}: {state} 插入 {inserted} 行 | " + "；".join(notes))
    print(f"\n合计插入 {total} 行，失败 {failures} 项" + ("" if options.apply else "（干跑，未写回）"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
