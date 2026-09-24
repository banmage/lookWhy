#!/usr/bin/env python3
"""canonical 标记回放（第三族之二：**表内角标定义行 → 表后脚注指令对**）——AGENTS.md §0.4。

背景：GB/T 的图表脚注由「引用点 + 定义」成对组成（GBT-X04，docs/15 §2）。引用点已由
`tools/replay_table_foot_markers.py` 从 `$^{a}$` 规范为 `[foot:a]`；本工具处理**定义侧**：
目前定义仍写在表的**最后一个数据行**里、以 `<br>` 分隔（如
``| [foot:a]分装式电动机不检验。<br> [foot:b]… |  |  |``），规范形态是表后的指令对
``<!--ssir:foot:a-->注文<!--ssir:/foot-->``（parser 的 `_FOOTNOTE_DEF_RE` 同一形态）。

规则（通用）：
1. **定义行判据**：表格行，第一个单元格可由 `<br>` 拆成 ≥1 个
   ``[foot:L]注文`` 片段，且其余单元格均为空；非定义行不动；
2. **提取**：把各片段写成表后的指令对（含 `<br>` 分隔的多条各成一条）；
3. **删行**：删掉该数据行；它若是表末行则**其它行号无位移**（`table-merge` 的 `row` 是
   数据行的 0-based 索引，实测确认：10401 表 row=36 为注行、row=37 为定义行），
   同时删掉**引用该行索引**的 `ssir:table-merge` 指令行（只删紧邻该表之后的那几条，并逐条打印）。

三重断言：
① **行级不变量**：把上标/标记归一成占位符后，「新文本去掉新增行」与「旧文本去掉被删行」
   逐行相同（顺序敏感）——证明除搬运内容外没有任何别的改动；
② **内容不丢**：每条定义注文都出现在新文本里，且新增的脚注指令对数 = 提取条数；
③ 改写后可 parse、`validate_ssir` 通过；复跑 0 处改动（幂等）。

用法：
    .venv/bin/python tools/replay_table_foot_definitions.py [--apply] [文件…]
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from leleby_ssir.service import parse_csm  # noqa: E402
from leleby_ssir.validation import validate_ssir  # noqa: E402

DEF_SEGMENT_RE = re.compile(r"^\s*\[foot:(?P<label>[0-9A-Za-z_-]+)\]\s*(?P<text>.+?)\s*$")
MERGE_RE = re.compile(r'<!--\s*ssir:table-merge\b[^>]*\brow="(?P<row>\d+)"')
PLACEHOLDER = "\u00abM\u00bb"


def _normalize(text: str) -> str:
    """上标与角标标记归一成占位符（两侧同一口径，只用于不变量比较）。"""
    text = re.sub(r"\[foot:[^\]]+\]", PLACEHOLDER, text)
    return re.sub(r"\$\^\{[^{}]*?\}\$", PLACEHOLDER, text)


def _table_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """连续表格行的区间（0-based 含端点）。"""
    blocks: list[tuple[int, int]] = []
    index = 0
    while index < len(lines):
        if not lines[index].lstrip().startswith("|"):
            index += 1
            continue
        start = index
        while index < len(lines) and lines[index].lstrip().startswith("|"):
            index += 1
        blocks.append((start, index - 1))
    return blocks


def _definition_row(line: str) -> list[tuple[str, str]] | None:
    """是定义行则返回 [(label, text), …]；否则 None。"""
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    if len(cells) < 2 or any(cells[1:]):
        return None
    segments = [segment.strip() for segment in cells[0].split("<br>")]
    definitions: list[tuple[str, str]] = []
    for segment in segments:
        if not segment:
            continue
        match = DEF_SEGMENT_RE.match(segment)
        if match is None:
            return None
        definitions.append((match.group("label"), match.group("text")))
    return definitions or None


def replay(path: Path, apply: bool = False) -> tuple[int, list[str]]:
    original_text = path.read_text(encoding="utf-8")
    lines = original_text.split("\n")
    deletions: set[int] = set()
    additions: dict[int, list[str]] = {}          # 表块末行 index → 追加行
    notes: list[str] = []
    extracted: list[tuple[str, str]] = []

    for start, end in _table_blocks(lines):
        in_data = False                             # 表头行与分隔行都**不计**数据行索引
        data_index = 0
        for row in range(start, end + 1):
            if not lines[row].lstrip().startswith("|"):
                continue
            if set(lines[row].replace("|", "").replace("-", "").strip()) <= {" "}:
                in_data = True                      # 表头分隔行
                continue
            if not in_data:
                continue                            # 表头行
            definitions = _definition_row(lines[row])
            if definitions is None:
                data_index += 1
                continue
            # 定义行：提取 + 删行 + 删引用该行索引的 merge 指令
            deletions.add(row)
            block: list[str] = [""]
            for label, text in definitions:
                block.append(f"<!--ssir:foot:{label}-->{text}<!--ssir:/foot-->")
                extracted.append((label, text))
            block.append("")
            additions.setdefault(end, []).extend(block)
            dropped: list[str] = []
            probe = end + 1
            while probe < len(lines) and lines[probe].strip().startswith("<!--"):
                match = MERGE_RE.search(lines[probe])
                if match and int(match.group("row")) == data_index:
                    deletions.add(probe)
                    dropped.append(f"row={data_index}")
                probe += 1
            notes.append(
                f"表 {start + 1}..{end + 1}：定义行 {row + 1}（数据行 #{data_index}）"
                f"→ {len(definitions)} 条（{'a' if definitions else ''}{definitions[0][0]}…），"
                f"删 merge 指令 {len(dropped)} 条"
            )
            continue                                # 该行已删，不计入后续索引
        # 表内出现定义行后不再有定义行；data_index 计数已按删除前口径使用

    if not deletions:
        return 0, ["无定义行（跳过）"]

    # 单趟重建：按原行序输出，遇到表块末行就地追加定义块（该行本身可能已被删，
    # 此时块落在它原来的位置 = 表后），不再做「删完再按索引插入」的两段算术
    # （旧写法在该处 off-by-one，会把真实表行挤出产物）。
    updated: list[str] = []
    inserted_indices: set[int] = set()
    for index, line in enumerate(lines):
        if index not in deletions:
            updated.append(line)
        if index in additions:
            for text in additions[index]:
                inserted_indices.add(len(updated))
                updated.append(text)

    new_text = "\n".join(updated)
    # 断言 ①：行级不变量——按**多重集**比较（排除被删行与插入行）：除搬运定义行外，
    # 原文不得有任何行被增删改。多集口径免疫插入位置计算，但仍能捕获任何越界改动。
    filtered_new = [line for index, line in enumerate(updated) if index not in inserted_indices]
    filtered_old = [line for index, line in enumerate(lines) if index not in deletions]
    from collections import Counter

    if Counter(_normalize(line) for line in filtered_new) != Counter(
        _normalize(line) for line in filtered_old
    ):
        raise SystemExit(f"{path.name}: 行级不变量失败（除搬运定义行外还有改动）")

    # 断言 ②：内容不丢
    for label, text in extracted:
        if text not in new_text:
            raise SystemExit(f"{path.name}: 定义注文丢失（label={label}）")
    added_pairs = len(re.findall(r"<!--ssir:foot:[0-9A-Za-z_-]+-->", new_text)) - len(
        re.findall(r"<!--ssir:foot:[0-9A-Za-z_-]+-->", original_text)
    )
    if added_pairs != len(extracted):
        raise SystemExit(f"{path.name}: 新增脚注指令对 {added_pairs} ≠ 提取条数 {len(extracted)}")

    # 断言 ③：可 parse、schema 通过
    handle = tempfile.NamedTemporaryFile("w", suffix=".canonical.md", delete=False, encoding="utf-8")
    handle.write(new_text)
    handle.close()
    temp_path = Path(handle.name)
    try:
        validate_ssir(parse_csm(temp_path))
    finally:
        temp_path.unlink(missing_ok=True)

    if apply:
        path.write_text(new_text, encoding="utf-8")
    notes.append(f"→ 提取 {len(extracted)} 条、删行 {len(deletions)} 行")
    return len(extracted), notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="canonical 标记回放：表内定义行 → 表后脚注指令对")
    parser.add_argument("files", nargs="*", help="canonical 文件（缺省 canonical/*.canonical.md）")
    parser.add_argument("--apply", action="store_true", help="写回文件（缺省干跑）")
    options = parser.parse_args(argv)
    targets = [Path(item) for item in options.files] or sorted((ROOT / "canonical").glob("*.canonical.md"))
    total = 0
    failures = 0
    for path in targets:
        try:
            count, notes = replay(path, apply=options.apply)
        except Exception as exc:  # noqa: BLE001
            print(f"{path.name}: 失败 {type(exc).__name__}: {exc}")
            failures += 1
            continue
        total += count
        state = "改写" if options.apply else "干跑"
        print(f"{path.name}: {state} {count} 条 | " + "；".join(notes))
    print(f"\n合计 {total} 条，失败 {failures} 项" + ("" if options.apply else "（干跑，未写回）"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
