#!/usr/bin/env python3
"""Replay GEN-133（目次区段，2026-09-23 用户裁定后的语义）onto existing canonicals：**丢弃原目次的显示**。

裁定原文（2026-09-23）：「目次都是根据正文内容生成，而不是根据原来的目次显示（应丢弃）」。
规则（与 `parser._toc_region_lines` / `_is_toc_entry_line` **判据单源**，不另写一份）：`目次`/
`目录` 标题之后的条目行**不带进产物**——既不落 `ssir:toc` 声明块，也不留在正文，更不得被裸条号
提升（GEN-035）当成章标题。对既有 canonical 的回放 = 该规则对实例的**确定性应用**，两种历史形态：

1. **显式声明块**（curated canonical 的 `<!-- ssir:toc -->…<!-- ssir:/toc -->`，条目即原目次显示）
   → 整块删除（含配对结束指令）；
2. **区段行**（`目次` 标题之后的条目行，可能带 `## ` 提升标记）→ 逐行删除（判据同 normalize；
   回放时先按标记剥离再判据）。

`目次` 标题本身**保留**：渲染端按章树生成目次时以该元素为插入位置（`_toc_nodes` + `toc_story`），
删掉标题会让生成目次整页消失。

不变量（脚本自带断言）：被删掉的非空行**恰为**目次条目与指令行，其余行逐字节不变；已合规的文件
零命中（**幂等**）。

只动 canonical，不动 raw：规则落在 normalize 层，任何一次合法的 normalize 重跑都会自动产出同样的
形态（条目行被消费、不落块），无须（也不应）改抽取值原样。

用法：
    .venv/bin/python tools/replay_toc_sections.py            # 干跑，只列将要改的文档
    .venv/bin/python tools/replay_toc_sections.py --apply    # 写回
    .venv/bin/python tools/replay_toc_sections.py --apply <canonical.md | 文档根目录>
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from leleby_ssir.parser import TOC_HEADING_TEXT_RE, _is_toc_entry_line  # noqa: E402

HEADING_RE = re.compile(r"^(?P<marks>#{1,6})\s+(?P<text>.*)$")
DIRECTIVE_RE = re.compile(r"^<!--\s*ssir:/?\s*[A-Za-z][\w-]*(?:\s[^>]*)?-->\s*$")
OPEN_DIRECTIVE = "<!-- ssir:toc -->"
CLOSE_DIRECTIVE = "<!-- ssir:/toc -->"


def _entry_text(line: str) -> str | None:
    """canonical 行 → 目次条目文本（剥掉 `## ` 提升标记后仍须过条目判据）；不是条目返回 None。"""
    text = HEADING_RE.sub(lambda match: match.group("text"), line).strip()
    return text if _is_toc_entry_line(text) else None


def _toc_region(lines: list[str], start: int) -> tuple[list[str], int]:
    """收条目行（`start` = 目次标题的下一行），终止条件与 normalize 的 `_toc_region_lines` 相同。"""
    entries: list[str] = []
    index = start
    while index < len(lines):
        text = _entry_text(lines[index])
        if text is None:
            if lines[index].strip():
                break
            lookahead = index + 1
            while lookahead < len(lines) and not lines[lookahead].strip():
                lookahead += 1
            if lookahead < len(lines) and _entry_text(lines[lookahead]) is not None:
                index = lookahead
                continue
            break
        entries.append(text)
        index += 1
    return entries, index


def _is_toc_heading(line: str) -> bool:
    match = HEADING_RE.match(line)
    if not match:
        return False
    return bool(TOC_HEADING_TEXT_RE.match(re.sub(r"\s+", "", match.group("text"))))


def _content_multiset(lines: list[str]) -> Counter:
    """内容不变量用的多重集：非空、非指令行，且剥掉标题标记。"""
    counter: Counter = Counter()
    for line in lines:
        if not line.strip() or DIRECTIVE_RE.match(line.strip()):
            continue
        counter[HEADING_RE.sub(lambda match: match.group("text"), line).strip()] += 1
    return counter


def replay(path: Path, *, apply: bool) -> list[tuple[int, str, str]]:
    """单个 canonical → [(行号, 形态, 被删内容摘要)]；apply 时写回。"""
    original = path.read_text(encoding="utf-8")
    lines = original.split("\n")
    updated: list[str] = []
    changes: list[tuple[int, str, str]] = []
    removed: list[str] = []  # 被删掉的原始行（不变量断言用）
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.strip() == OPEN_DIRECTIVE:
            end = index
            while end < len(lines) and lines[end].strip() != CLOSE_DIRECTIVE:
                end += 1
            if end >= len(lines):
                # 无配对结束指令：不猜边界，原样保留（由 normalize 的 GEN-134 分支负责）
                updated.append(line)
                index += 1
                continue
            entries = [text for text in lines[index + 1 : end] if text.strip()]
            removed.extend(lines[index : end + 1])
            changes.append((index, "declaration", f"{len(entries)} 条目，末条 {entries[-1]!r}" if entries else "空块"))
            index = end + 1
            continue
        updated.append(line)
        index += 1
        if not _is_toc_heading(line):
            continue
        entries, next_index = _toc_region(lines, index)
        if not entries:
            continue
        removed.extend(lines[index:next_index])
        changes.append((index, "region", f"{len(entries)} 条目，末条 {entries[-1]!r}"))
        index = next_index
    if apply and changes:
        updated_text = "\n".join(updated)
        expected = _content_multiset(original.split("\n"))
        for line in removed:
            if not line.strip() or DIRECTIVE_RE.match(line.strip()):
                continue
            expected[HEADING_RE.sub(lambda match: match.group("text"), line).strip()] -= 1
        expected = Counter({key: value for key, value in expected.items() if value})
        assert expected == _content_multiset(updated_text.split("\n")), (
            f"{path}: 回放除了目次条目还改动了别的行"
        )
        path.write_text(updated_text, encoding="utf-8")
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
    return sorted(ROOT.glob("out/mineru/*/02_canonical/*.canonical.md")) + sorted(ROOT.glob("canonical/*.canonical.md"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", help="canonical 文件或文档根目录（默认全部 out/mineru/* 与 canonical/）")
    parser.add_argument("--apply", action="store_true", help="写回 canonical（默认只报告）")
    options = parser.parse_args()
    total = 0
    for path in _targets(options.paths):
        if not path.is_file():
            print(f"skip (not a file): {path}", file=sys.stderr)
            continue
        changes = replay(path, apply=options.apply)
        if not changes:
            continue
        total += len(changes)
        document = path.parent.parent.name if path.parent.name == "02_canonical" else path.stem
        for line_number, kind, summary in changes:
            print(
                f"{'write' if options.apply else 'would write'} {document:28s} line {line_number + 1:5d}: "
                f"丢弃原目次（{kind}）{summary}"
            )
    print(f"{'applied' if options.apply else 'dry run'}: {total} 处原目次显示")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
