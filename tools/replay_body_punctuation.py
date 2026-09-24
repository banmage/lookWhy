#!/usr/bin/env python3
"""规则实例回放：正文半角标点 → 全角（GEN-138，docs/12 §3.87）。

判据单源：`leleby_ssir.parser.normalise_body_punctuation`（与本引擎 normalize/parse
路径同一函数）。本工具只把该判据**确定性地**应用到既有 canonical 文件，用于
「规则已落地、产物尚未重跑」的回放；缺省干跑，`--apply` 才写回（写前留
`<文件名>.bak-punct-width` 备份）。

逐行规则（与 parse 层载体一致）：front matter、`<!-- ssir:…-->` 指令行、公式围栏
（`$$…$$`）与代码围栏（``` … ```）整段跳过；其余行按判据转换。

不变量（`--apply` 时逐条断言，任一失败即回滚该文件）：
  1. 行数不变；
  2. 改动只落在标点宽度（全/半角折叠后逐字符相同）；
  3. 幂等（复跑命中 0）；
  4. 写回后可 `CSMParser.read` 且解析层载体命中 0（无残留）。

用法：
  tools/replay_body_punctuation.py [--apply] [文件…]
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from leleby_ssir.parser import CSMParser, normalise_body_punctuation  # noqa: E402

FOLD = str.maketrans({"（": "(", "）": ")", "：": ":", "；": ";", "，": ",", "？": "?", "！": "!", "．": ".", "。": "."})
BACKUP_SUFFIX = ".bak-punct-width"


def default_targets() -> list[Path]:
    return sorted(ROOT.glob("out/mineru/*/02_canonical/*.canonical.md"))


def split_front_matter(lines: list[str]) -> int:
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return index + 1
    return 0


def convert_text(text: str) -> tuple[str, int, int]:
    """返回 (新文本, 改动行数, 改动字符数)。"""
    lines = text.split("\n")
    body_start = split_front_matter(lines)
    changed_lines = 0
    changed_chars = 0
    in_fence = False
    in_math = False
    for index, line in enumerate(lines):
        if index < body_start:
            continue
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith("$$"):
            # 单行 `$$…$$` 或围栏首尾；成对时按同一行闭合处理
            if stripped.count("$$") == 1:
                in_math = not in_math
            continue
        if in_math:
            continue
        if re.match(r"^\s*<!--.*-->\s*$", line):
            continue
        fixed, count = normalise_body_punctuation(line)
        if count:
            lines[index] = fixed
            changed_lines += 1
            changed_chars += count
    return "\n".join(lines), changed_lines, changed_chars


def residual_hits(path: Path) -> int:
    """解析层载体命中数（应为 0）；载体与 `_normalise_body_punctuation_width` 同集。"""
    document = CSMParser().read(path)
    total = 0
    for block in document.blocks:
        if block.kind in {"formula", "unknown"} or block.data.get("format") == "raw" or block.data.get("code_fence"):
            continue
        for text in [block.text, *[str(item.get("text", "")) for item in block.data.get("items", [])],
                     *[str(cell) for row in block.data.get("rows", []) for cell in row]]:
            total += normalise_body_punctuation(text)[1]
    return total


def replay(path: Path, *, apply: bool) -> dict:
    original = path.read_text(encoding="utf-8")
    new_text, changed_lines, changed_chars = convert_text(original)
    report = {"path": path, "changed_lines": changed_lines, "changed_chars": changed_chars, "applied": False, "samples": []}
    if not changed_lines:
        return report
    for line in difflib.unified_diff(original.split("\n"), new_text.split("\n"), lineterm="", n=0):
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---")):
            report["samples"].append(line[:160])
            if len(report["samples"]) >= 4:
                break
    if not apply:
        return report
    old_lines = original.split("\n")
    new_lines = new_text.split("\n")
    assert len(old_lines) == len(new_lines), f"{path}: 行数变化"
    for old_line, new_line in zip(old_lines, new_lines):
        assert old_line.translate(FOLD) == new_line.translate(FOLD), f"{path}: 改动超出标点宽度：{old_line!r} -> {new_line!r}"
    again = convert_text(new_text)[1]
    assert again == 0, f"{path}: 非幂等（复跑仍命中 {again} 行）"
    backup = path.with_suffix(path.suffix + BACKUP_SUFFIX)
    if not backup.exists():
        backup.write_text(original, encoding="utf-8", newline="\n")
    path.write_text(new_text, encoding="utf-8", newline="\n")
    residual = residual_hits(path)
    report["applied"] = True
    report["residual"] = residual
    assert residual == 0, f"{path}: 写回后解析层仍有 {residual} 处命中"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="正文半角标点 → 全角（GEN-138）回放")
    parser.add_argument("files", nargs="*", type=Path, help="canonical 文件（缺省：全部 docroot canonical）")
    parser.add_argument("--apply", action="store_true", help="写回（缺省只干跑）")
    args = parser.parse_args()
    targets = args.files or default_targets()
    if not targets:
        print("没有可回放的文件")
        return 1
    total_lines = total_chars = 0
    for path in targets:
        if not path.exists():
            print(f"缺失：{path}")
            return 2
        report = replay(path, apply=args.apply)
        total_lines += report["changed_lines"]
        total_chars += report["changed_chars"]
        suffix = "" if not report["applied"] else f"（已写回，备份 {path.name}{BACKUP_SUFFIX}）"
        print(f"{path.name}: {report['changed_lines']} 行 / {report['changed_chars']} 处{suffix}")
        for sample in report["samples"][:2]:
            print(f"    {sample}")
    mode = "已写回" if args.apply else "干跑"
    print(f"\n{mode}：{len(targets)} 份文件，共 {total_lines} 行 / {total_chars} 处标点归一")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
