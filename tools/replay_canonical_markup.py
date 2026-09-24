#!/usr/bin/env python3
"""canonical 标记回放：按 docs/15 的新标记规则给既有 curated canonical 补声明（AGENTS.md §0.4）。

本轮覆盖的标记族（判据与渲染影响均已验证）：

1. **目次括起**：把 `目次` 节点覆盖的行区间括进 `<!-- ssir:toc -->` … `<!-- ssir:/toc -->`。
   - 判据来源：SSIR 里 `目次` 节点内容元素的 markdown 源锚点（不靠正则猜行号）；
   - 渲染影响：A/B 实测（GB_T_1.1-2020）逐页文本完全一致（docs/16 §12「A/B 实测」）。

三重断言：
① **内容不变量**——改写只在原文里**插入**两行指令，其余字节逐字节不变（断言失败即中止）；
② **幂等**——文件已含 `ssir:toc` 声明时 0 处改动；
③ **解析校验**——改写后可 parse 且 `validate_ssir` 通过，且 `tocEntries` 条目数 =
   目次区非空行数（不丢行）。

用法：
    .venv/bin/python tools/replay_canonical_markup.py [--apply] [文件…]
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from leleby_ssir.service import parse_csm  # noqa: E402
from leleby_ssir.validation import validate_ssir  # noqa: E402

TOC_OPEN = "<!-- ssir:toc -->"
TOC_CLOSE = "<!-- ssir:/toc -->"
CONTENTS_TITLE = "目次"


def contents_span(ssir: dict) -> tuple[int, int] | None:
    """`目次` 节点覆盖的行区间（1-based，含端点）；无目次节点或已无正文行时返回 None。"""
    node = None
    for candidate in ssir["structuralRoot"].get("children") or []:
        title = str(candidate.get("title") or "").replace(" ", "")
        if CONTENTS_TITLE in title:
            node = candidate
            break
    if node is None:
        return None
    spans: list[tuple[int, int]] = []
    for element in node.get("contentElements") or []:
        for anchor in element.get("sourceAnchors") or []:
            spans.append((int(anchor["markdownStartLine"]), int(anchor["markdownEndLine"])))
    if not spans:
        return None
    return min(start for start, _ in spans), max(end for _, end in spans)


def wrap_toc(lines: list[str], span: tuple[int, int]) -> tuple[list[str], int]:
    """在 span 覆盖的**非空行**两侧插入指令行。"""
    start_index = span[0] - 1
    while start_index < len(lines) and not lines[start_index].strip():
        start_index += 1
    end_index = span[1] - 1
    while end_index >= 0 and not lines[end_index].strip():
        end_index -= 1
    if start_index >= len(lines) or end_index < start_index:
        return lines, 0
    updated = list(lines)
    updated.insert(end_index + 1, TOC_CLOSE)
    updated.insert(start_index, TOC_OPEN)
    return updated, 2


def _verified_parse(text: str) -> tuple[dict, Path]:
    """在临时目录里 parse 文本（不污染仓库目录）。"""
    handle = tempfile.NamedTemporaryFile("w", suffix=".canonical.md", delete=False, encoding="utf-8")
    handle.write(text)
    handle.close()
    path = Path(handle.name)
    return parse_csm(path), path


def replay(path: Path, apply: bool = False) -> tuple[int, list[str]]:
    """返回 (插入行数, 备注)。apply=False 时只统计（干跑），不写回。"""
    original_text = path.read_text(encoding="utf-8")
    if TOC_OPEN in original_text:
        return 0, ["已含 ssir:toc 声明（幂等跳过）"]
    ssir = parse_csm(path)
    span = contents_span(ssir)
    if span is None:
        return 0, ["无目次正文行（无需括起）"]
    updated, inserted = wrap_toc(original_text.split("\n"), span)
    if inserted == 0:
        return 0, [f"目次区无内容行（{span[0]}..{span[1]}）"]
    new_text = "\n".join(updated)

    # 断言 ①：内容不变量——去掉插入的两行后必须与原文字节相同
    stripped = [line for line in updated if line.strip() not in {TOC_OPEN, TOC_CLOSE}]
    if "\n".join(stripped) != original_text:
        raise SystemExit(f"{path.name}: 内容不变量失败（除插入指令外还有改动）")

    # 断言 ③：改写后可解析、schema 通过、条目数 = 目次区非空行数
    checked, temp_path = _verified_parse(new_text)
    try:
        validate_ssir(checked)
    finally:
        temp_path.unlink(missing_ok=True)
    expected = len([line for line in original_text.split("\n")[span[0] - 1:span[1]] if line.strip()])
    entries = len(checked.get("tocEntries") or [])
    if entries != expected:
        raise SystemExit(f"{path.name}: 目次条目数 {entries} ≠ 目次区非空行数 {expected}（丢行）")

    if apply:
        path.write_text(new_text, encoding="utf-8")
    return inserted, [f"目次行 {span[0]}..{span[1]}：非空 {expected} 行 → tocEntries {entries} 条"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="canonical 标记回放（目次括起）")
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
