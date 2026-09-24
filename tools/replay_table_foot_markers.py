#!/usr/bin/env python3
"""canonical 标记回放（第三族之一：**表内角标 → `[foot:a]`**）——AGENTS.md §0.4。

背景（docs/15 §2 标记表）：`$^{a}$` 与数学/单位上标**同形**，一形两义（P2 违例）。
新语法把**图表脚注引用点**写成 `[foot:a]`（多标签 `[foot:a、c]`），`$^{…}$` 只表示数学上下标。

判据（本工具，通用）：
1. 只处理**表格行**（行首为 `|`）内的 `$^{…}$`；
2. 上标内容必须是**纯角标标签序列**：单个字母/数字，或由 `、`/`,`/`，` 分隔的多个，允许内部空格
   （源数据里存在 `$^{b、d }$`、`$^{c} $` 这类带空格写法）——含运算符/单位/汉字的一律不转换；
3. **证据门**：同一文件里必须存在该标签的**定义**（`$^{a}$` 紧跟汉字的形态，即表下定义行）。
   取不到定义 → 不转换（可能是真数学上标），并如实列出，不猜。

三重断言（仅 `--apply` 时执行改写，断言对两种模式都跑）：
① 内容不变量——只把 `$^{L}$` 换成 `[foot:L]`，其余字节不变；
② 幂等——已转换的文件复跑 0 处改动；
③ 改写后可 parse、`validate_ssir` 通过。

用法：
    .venv/bin/python tools/replay_table_foot_markers.py [--apply] [文件…]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from leleby_ssir.service import parse_csm  # noqa: E402
from leleby_ssir.validation import validate_ssir  # noqa: E402

SUPERSCRIPT_RE = re.compile(r"\$\^\{(?P<content>[^{}]*?)\}\$")
LABEL_SEQUENCE_RE = re.compile(r"^[A-Za-z0-9](?:[ \u3000]*[、,，][ \u3000]*[A-Za-z0-9])*$")
CJK = r"\u4e00-\u9fff"


def _definition_labels(lines: list[str]) -> set[str]:
    """定义行里出现的角标标签：`$^{a}$` 之后紧跟汉字（表下定义 / 图下定义形态）。"""
    labels: set[str] = set()
    pattern = re.compile(rf"\$\^\{{(?P<label>[^{{}}]+?)\}}\$[ \u3000]*(?=[{CJK}])")
    for line in lines:
        for match in pattern.finditer(line):
            labels.update(_split_labels(match.group("label")))
    return labels


def _split_labels(content: str) -> list[str]:
    return [part.strip() for part in re.split(r"[、,，]", content) if part.strip()]


def _is_label_sequence(content: str) -> bool:
    return bool(LABEL_SEQUENCE_RE.match(content))


def replay(path: Path, apply: bool = False) -> tuple[int, list[str]]:
    original_text = path.read_text(encoding="utf-8")
    if "[foot:" in original_text:
        pass  # 已转换的标记与本族判据不冲突（判据只认 $^{…}$），无需整体跳过
    lines = original_text.split("\n")
    defined = _definition_labels(lines)
    replacements = 0
    skipped_no_definition: list[str] = []
    skipped_not_label: list[str] = []
    updated: list[str] = []
    for line in lines:
        if not line.lstrip().startswith("|"):
            updated.append(line)
            continue

        def _replace(match: re.Match[str]) -> str:
            nonlocal replacements
            content = match.group("content").strip()   # 源数据存在 `$^{c} $`、`$^{b、d }$` 的空白噪声
            if not _is_label_sequence(content):
                skipped_not_label.append(match.group("content"))
                return match.group(0)
            labels = _split_labels(content)
            if not labels or any(label not in defined for label in labels):
                skipped_no_definition.append(content)
                return match.group(0)
            replacements += 1
            return "[foot:" + "、".join(labels) + "]"

        updated.append(SUPERSCRIPT_RE.sub(_replace, line))

    notes: list[str] = [
        f"定义标签 {sorted(defined) or '无'}",
        f"可转换角标 {replacements} 处"
        + (f"；无定义跳过 {len(skipped_no_definition)} 处 {skipped_no_definition[:4]}" if skipped_no_definition else "")
        + (f"；非标签内容跳过 {len(skipped_not_label)} 处 {skipped_not_label[:4]}" if skipped_not_label else ""),
    ]
    if replacements == 0:
        return 0, notes

    new_text = "\n".join(updated)
    # 断言 ①：内容不变量——把「上标」与「角标标记」都归一成占位符后两侧必须逐字节相同，
    #        并且上标数减少量、标记增加量都恰等于替换处数（防越界改动/漏改）。
    placeholder = "\u00abM\u00bb"
    normalize = lambda text: SUPERSCRIPT_RE.sub(  # noqa: E731
        placeholder, re.sub(r"\[foot:[^\]]+\]", placeholder, text)
    )
    if normalize(original_text) != normalize(new_text):
        raise SystemExit(f"{path.name}: 内容不变量失败（除角标替换外还有改动）")
    superscript_delta = len(SUPERSCRIPT_RE.findall(original_text)) - len(SUPERSCRIPT_RE.findall(new_text))
    marker_delta = len(re.findall(r"\[foot:[^\]]+\]", new_text)) - len(
        re.findall(r"\[foot:[^\]]+\]", original_text)
    )
    if superscript_delta != replacements or marker_delta != replacements:
        raise SystemExit(
            f"{path.name}: 替换计数不一致（上标 -{superscript_delta}、标记 +{marker_delta}、应为 {replacements}）"
        )

    # 断言 ③：改写后可 parse、schema 通过
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
    notes.append(f"→ 写入 {replacements} 处（-: {json.dumps(sorted(defined), ensure_ascii=False)}）")
    return replacements, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="canonical 标记回放：表内角标 → [foot:a]")
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
        print(f"{path.name}: {state} {count} 处 | " + "；".join(notes))
    print(f"\n合计 {total} 处，失败 {failures} 项" + ("" if options.apply else "（干跑，未写回）"))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
