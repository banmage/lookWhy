#!/usr/bin/env python3
"""canonical 标记回放（第三族之三：**图/附录下脚注定义行 → 脚注指令对**）——AGENTS.md §0.4。

背景：图表脚注的**定义**在旧 canonical 里写在图块内部、用数学上标形态带标签，如
``$^{b}$ 钉芯头的形状和尺寸由制造者确定。``；规范形态（GEN-118 / docs/07 §6.7）是
``<!--ssir:foot:b-->注文<!--ssir:/foot-->``（parser 的 `_FOOTNOTE_DEF_RE` 同一形态）。
本工具把前者确定性重放为后者，等价于 `tools/replay_table_foot_definitions.py` 对表内定义的
处理，但对象是**图块/附录下的独立定义行**。

判据（通用，不针对任何具体文档）：
1. **定义行**：整行形如 ``$^{L}$ 注文`` 或 ``[:sup:L] 注文``（L = 数字/字母标签，注文非空）；
2. **所属块**：该行所在的「空行分隔块」**只由定义行组成**（连续多条各自成条）；
3. **图文归属（证据门）**：块的上邻非空行是**图资产行**（``![…](…)``）或 ``单位为…`` 行，
   或块的下邻非空行是**图/表题注**（``图 …`` / ``表 …``）——即定义紧贴图块；
   两条都不满足则**不动**（宁可漏，不误改）。

变换：``$^{L}$ 注文`` → ``<!--ssir:foot:L-->注文<!--ssir:/foot-->``（注文原样搬运，不改一字）。

三重断言：
① 行级不变量：标记归一成占位符后，「新文本去掉新增行」与「旧文本去掉被改写行」逐行相同；
② 内容不丢：每条注文都出现在新文本里，新增 `<!--ssir:foot:` 数 = 改写条数；
③ 改写后可 parse 且 `validate_ssir` 通过；复跑 0 处改动（幂等）。

用法：
    .venv/bin/python tools/replay_figure_foot_definitions.py [--apply] [文件…]
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

# 定义行：$^{L}$ 注文 / [:sup:L] 注文（标签后的空白可有可无——抽取常把空格丢掉）
DEF_LINE_RE = re.compile(
    r"^\s*(?:\\?\$\^\{([0-9A-Za-z_-]+)\}\$|\[:sup:([0-9A-Za-z_-]+)\s*/?\])\s*(?P<text>\S.*?)\s*$"
)
IMAGE_RE = re.compile(r"^\s*!\[[^\]]*\]\([^)]*\)\s*$")
UNIT_RE = re.compile(r"^\s*单位为\s*\S+\s*$")
LEGEND_RE = re.compile(r"^\s*标引序号说明\s*[:：]?\s*$")
CAPTION_RE = re.compile(r"^\s*(?:图|表)\s*\S")
PLACEHOLDER = "\u00abM\u00bb"


def _normalize(text: str) -> str:
    """上标/角标标记归一成占位符（两侧同一口径，只用于不变量比较）。"""
    text = re.sub(r"<!--\s*ssir:foot:[^>]*?-->|<!--\s*ssir:/foot\s*-->", PLACEHOLDER, text)
    return re.sub(r"\\?\$\^\{[^{}]*?\}\$", PLACEHOLDER, text)


def _blank_separated_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """空行分隔的连续非空行区间（0-based 含端点）。"""
    blocks: list[tuple[int, int]] = []
    index = 0
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        start = index
        while index < len(lines) and lines[index].strip():
            index += 1
        blocks.append((start, index - 1))
    return blocks


def _neighbour(lines: list[str], blocks: list[tuple[int, int]], position: int, step: int) -> str | None:
    """相邻块的首（或末）行文本；越界返回 None。"""
    target = position + step
    if not 0 <= target < len(blocks):
        return None
    start, end = blocks[target]
    return lines[start if step > 0 else end]


def convert(text: str) -> tuple[str, list[str]]:
    """返回（新文本, 改写说明）。无条件、幂等：已是指令对的行不再匹配。"""
    lines = text.splitlines()
    blocks = _blank_separated_blocks(lines)
    notes: list[str] = []
    for position, (start, end) in enumerate(blocks):
        block_lines = lines[start : end + 1]
        # 块内**末尾连续**的定义行（图块里常见「单位为… / 图资产 / 定义行…」同块）。
        tail = len(block_lines)
        while tail > 0 and DEF_LINE_RE.match(block_lines[tail - 1]):
            tail -= 1
        if tail == len(block_lines):
            continue  # 末行不是定义行
        before = _neighbour(lines, blocks, position, -1)
        after = _neighbour(lines, blocks, position, +1)
        attached = (
            any(IMAGE_RE.match(line) or CAPTION_RE.match(line) or UNIT_RE.match(line) or LEGEND_RE.match(line)
                for line in block_lines[:tail])
            or (before is not None and (IMAGE_RE.match(before) or UNIT_RE.match(before)))
            or (after is not None and CAPTION_RE.match(after))
        )
        if not attached:
            continue
        for offset in range(tail, len(block_lines)):
            match = DEF_LINE_RE.match(block_lines[offset])
            label = match.group(1) or match.group(2)
            body = match.group("text")
            lines[start + offset] = f"<!--ssir:foot:{label}-->{body}<!--ssir:/foot-->"
            notes.append(f"{label}: {body[:32]}")
    new_text = "\n".join(lines)
    if text.endswith("\n"):
        new_text += "\n"
    return new_text, notes


def replay(path: Path, apply: bool) -> int:
    original = path.read_text(encoding="utf-8")
    new_text, notes = convert(original)
    stem = path.stem
    if not notes:
        print(f"  {stem}: 0 处（复跑/无需改动）")
        return 0
    # ① 行级不变量：去掉被改写行与新增行后逐行相同
    old_lines = [_normalize(line) for line in original.splitlines()]
    new_lines = [_normalize(line) for line in new_text.splitlines()]
    inserted = [line for line in new_lines if line not in old_lines]
    removed = [line for line in old_lines if line not in new_lines]
    old_rest = [line for line in old_lines if line not in removed]
    new_rest = [line for line in new_lines if line not in inserted]
    if old_rest != new_rest:
        print(f"  {stem}: 行级不变量失败（除改写定义行外还有改动）——不写入", file=sys.stderr)
        return -1
    # ② 内容不丢 + 计数
    for note in notes:
        body = note.split(": ", 1)[1]
        if body[:24] not in new_text:
            print(f"  {stem}: 内容不变量失败（注文丢失：{note}）", file=sys.stderr)
            return -1
    added = new_text.count("<!--ssir:foot:") - original.count("<!--ssir:foot:")
    if added != len(notes):
        print(f"  {stem}: 指令对数不符（新增 {added} ≠ 改写 {len(notes)}）", file=sys.stderr)
        return -1
    # ③ 可 parse + validate
    with tempfile.TemporaryDirectory() as tmp:
        candidate = Path(tmp) / path.name
        candidate.write_text(new_text, encoding="utf-8")
        try:
            ssir = parse_csm(candidate)
            validate_ssir(ssir)
        except Exception as exc:  # noqa: BLE001
            print(f"  {stem}: 改写后无法 parse/validate：{type(exc).__name__}: {str(exc)[:120]}", file=sys.stderr)
            return -1
    labels = [note.split(":", 1)[0] for note in notes]
    print(f"  {stem}: {len(notes)} 处 → " + "、".join(labels))
    for note in notes:
        print(f"      {note}")
    if apply:
        path.write_text(new_text, encoding="utf-8")
        print(f"      已写入 {path}")
    return len(notes)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help="默认 canonical/*.canonical.md")
    parser.add_argument("--apply", action="store_true", help="写回文件（缺省只干跑）")
    args = parser.parse_args()
    files = args.files or sorted((ROOT / "canonical").glob("*.canonical.md"))
    total = 0
    for path in files:
        if not path.is_file():
            print(f"  {path}: 不存在", file=sys.stderr)
            return 2
        result = replay(path, args.apply)
        if result < 0:
            return 1
        total += result
    print(f"  合计 {total} 处{'（已写入）' if args.apply else '（干跑，未写入）'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
