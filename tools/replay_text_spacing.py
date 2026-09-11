#!/usr/bin/env python3
"""Replay the text-spacing repair rules onto canonicals (CSM-OCR-003 / CSM-OCR-004).

规则对应:
- CSM-OCR-003 术语间隔：术语条目行「术语 英文对应词」之间空一个汉字
  （GB/T 1.1-2020 8.7.3.1/10.3.5），数据里用 U+3000 表示；
- CSM-OCR-004 标准号间隔：标准号「文件代号 + 顺序号」之间补一个空格
  （GB/T20001 → GB/T 20001）。

AGENTS.md §0.4 —— 规则先落地（parser 修复 + 回归测试），再以**该规则的确定性应用**
把实例回放进 canonical 数据。规则本体与解析层共用同一实现（parser 里的
``restore_term_entry_gap`` / ``restore_standard_number_spacing``），本工具只负责
「逐行找出要改的行 + 校验改动只动空白 + 写回 + 复验命中为 0」。

- 跳过 YAML front matter、代码围栏内的行、HTML 注释指令行、整行图片行；
- 术语间隔只在「术语和定义」要素内生效（行级章跟踪：章标题含“术语”，
  附录标题或其它章标题即离开该要素）——与解析层的 ``in_terms`` 跟踪同规；
- 改动行必须满足「只动空白、非空白字符序列不变」，否则中止且不落盘；
- ``--check``（默认）只报告；``--apply`` 才写回，写回后用解析器复验
  CSM-OCR-003/004 命中为 0（幂等断言）。

用法:
    .venv/bin/python tools/replay_text_spacing.py                 # 全语料 --check
    .venv/bin/python tools/replay_text_spacing.py --apply GB_T_1.1-2020
    .venv/bin/python tools/replay_text_spacing.py --apply         # 全语料写回

退出码: 0 干净；2 出现非「只动空白」的改动；3 写回后规则仍有命中。
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _path in (str(ROOT / "src"), str(ROOT / "tools")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from leleby_ssir.parser import (  # noqa: E402
    CSMParser,
    restore_standard_number_spacing,
    restore_term_entry_gap,
)

_FENCE_RE = re.compile(r"^\s*```")
_COMMENT_RE = re.compile(r"^\s*<!--")
_IMAGE_RE = re.compile(r"^\s*!\[")
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
_CHAPTER_RE = re.compile(r"^\d+\s+\S")
_ANNEX_RE = re.compile(r"^附\s*录")
_WHITESPACE_RE = re.compile(r"[ \u3000\u200b]")
RULE_CODES = ("CSM-OCR-003", "CSM-OCR-004")


def _iter_canonicals(root: Path, names: list[str]) -> list[Path]:
    found = sorted(root.glob("*/02_canonical/*.canonical.md"))
    if not names:
        return found
    wanted = tuple(names)
    return [path for path in found if path.parent.parent.name.startswith(wanted) or path.name.startswith(wanted)]


def _skip_flags(lines: list[str]) -> list[bool]:
    """标记不属于正文文本载体的行（front matter / 围栏 / 指令 / 图片）。"""
    skip = [False] * len(lines)
    in_front = False
    in_fence = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if index == 0 and stripped == "---":
            in_front = True
            skip[index] = True
            continue
        if in_front:
            skip[index] = True
            if stripped == "---":
                in_front = False
            continue
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            skip[index] = True
            continue
        if in_fence or _COMMENT_RE.match(line) or _IMAGE_RE.match(line):
            skip[index] = True
    return skip


def _replay_text(text: str) -> tuple[str, list[tuple[str, str]]]:
    lines = text.splitlines(keepends=True)
    skip = _skip_flags(lines)
    out: list[str] = []
    changes: list[tuple[str, str]] = []
    in_terms = False
    for index, line in enumerate(lines):
        if skip[index]:
            out.append(line)
            continue
        heading = _HEADING_RE.match(line)
        if heading:
            title = heading.group(1).strip()
            if _ANNEX_RE.match(title) or (_CHAPTER_RE.match(title) and "术语" not in title):
                in_terms = False
            elif _CHAPTER_RE.match(title) and "术语" in title:
                in_terms = True
        if heading:
            # 标题行：段首 "#" 标记与行尾不属于标题文本，分开处理后再拼回。
            title = heading.group(1)
            prefix, ending = line[: heading.start(1)], line[heading.end(1):]
            fixed_title = restore_standard_number_spacing(title)
            if in_terms:
                fixed_title = restore_term_entry_gap(fixed_title)
            fixed = prefix + fixed_title + ending
        else:
            fixed = restore_standard_number_spacing(line)
            if in_terms:
                fixed = restore_term_entry_gap(fixed)
        if fixed != line:
            changes.append((line.rstrip("\n"), fixed.rstrip("\n")))
        out.append(fixed)
    return "".join(out), changes


def _non_whitespace_only(changes: list[tuple[str, str]]) -> list[str]:
    problems: list[str] = []
    for old, new in changes:
        if _WHITESPACE_RE.sub("", new) != _WHITESPACE_RE.sub("", old):
            problems.append(f"not a whitespace-only change:\n  - {old}\n  + {new}")
    return problems


def _rule_hits(path: Path) -> list[str]:
    return [f"[{issue.code}] line {issue.line}: {issue.message}"
            for issue in CSMParser().read(path).issues
            if issue.code in RULE_CODES]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("ids", nargs="*", help="standard ids (default: every canonical under out/mineru)")
    parser.add_argument("--root", type=Path, default=ROOT / "out" / "mineru", help="corpus root")
    parser.add_argument("--apply", action="store_true", help="write the replay back over the canonical")
    arguments = parser.parse_args()

    canonicals = _iter_canonicals(arguments.root, arguments.ids)
    if not canonicals:
        print("no canonical found", file=sys.stderr)
        return 2
    total_changes = 0
    problems: list[str] = []
    for path in canonicals:
        text = path.read_text(encoding="utf-8")
        replayed, changes = _replay_text(text)
        total_changes += len(changes)
        if not changes:
            continue
        print(f"== {path.relative_to(ROOT)}  ({len(changes)} line(s))")
        for line in difflib.unified_diff(text.splitlines(), replayed.splitlines(), lineterm="", n=0):
            if line[:1] in "+-" and not line.startswith(("+++", "---")):
                print("   " + line)
        problems.extend(_non_whitespace_only(changes))
        if arguments.apply:
            path.write_text(replayed, encoding="utf-8")
            hits = _rule_hits(path)
            if hits:
                print(f"   rule still hits after replay: {hits}", file=sys.stderr)
                return 3
            print("   applied; CSM-OCR-003/004 hits now 0")

    print(f"total changed lines: {total_changes} over {len(canonicals)} canonical(s)"
          + ("" if arguments.apply else "  (dry run — use --apply)"))
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
