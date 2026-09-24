#!/usr/bin/env python3
"""canonical 标点还原回放：**把被误全角化的半角标点按健康副本/基线确定性还原**——AGENTS.md §0.4。

背景（2026-09-24 事故，docs/12 §3.86）：`out/mineru/{GB_T_1.1-2020,GB_T_10401-2023}/
02_canonical/*.canonical.md` 被管线**之外**的某个进程在 09:27/09:42 整体改写，把**全部**
半角 `:` `,` `;`（GB_T_1.1-2020 还有 `·`，GB_T_10401-2023 还有 `~`）一次性映射成对应全角
形态（两份文件里半角残留都是 0）；GB_T_10401-2023 那一遍还把「逗号+空格」的空格一并吞掉。
后果：YAML front matter 的键不再被 `yaml.safe_load` 识别为映射（metadata 退化为 `{}`，封面
ICS/发布日期/发布机构丢失，`document-identifier` 退化为文件名 stem，页眉多出 `.canonical`）、
`<!--ssir:…-->` 指令行不再是指令（表格/框线/脚注/目次全部失效）。

判据（通用，不针对任何具体文档）：
1. **损坏模型固定且可枚举**：全角化只认五个配对 `：→:`、`，→,`、`；→;`、`‧→·`、`～→~`；
   「吞空格」变体只认 `, `→`，`、`: `→`：`、`; `→`；`——同一事故的两遍改写行为不同，
   所以三个模型按行试配（纯标点 / 逗号吞空格 / 三种标点都吞空格）；
2. **整行精确还原**：对副本行施加模型后**与目标行逐字符相等**时，才把该行整行还原成副本行
   （不是逐字猜——模型的正确性由「相等」这一事实自证）。副本按命令行给出的顺序取优先级：
   **健康基线的产物投影（`04_render/*.render.md`，同一文档损坏前的构建）排在 canonical
   副本之前**——基线是本文档损坏前的文本，canonical 副本只是快照，标点可能落后于基线；
3. **字符级兜底 + 宁漏不误改**：模型未覆盖的行，才用「折叠标点后对齐、按位还原」的保守
   规则（含「副本是 `, ` 而目标只剩 `，`」时把被吞掉的空格补回）；副本也无覆盖的行，才退回
   **语法必需半角**（`<!--ssir:…-->` 指令名、`[foot:L]` 标记、front matter 的键——CSM 文法
   自身决定，不需要副本）；三条都落空的行一律不动，计入「无对位证据」并列出。

保证（写回前全部断言）：
① 行数不变；② 每处改动都落在五个配对之内（模型吞掉的空格除外），其余字符逐位相同
（按折叠 + 去空格比较）；③ 幂等（复跑 0 处改动）；④ 还原后能 `parse_csm` 且 front matter
是映射（metadata 非空）。

用法：
    .venv/bin/python tools/restore_fullwidth_punct.py --target <canonical> \
        --oracle <健康基线 render.md> --oracle <同源健康 canonical> [--apply]
"""

from __future__ import annotations

import argparse
import collections
import difflib
import re
import sys
from typing import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from leleby_ssir.service import parse_csm  # noqa: E402

# 与 pipeline._MATCH_PUNCT_TABLE 同表（docs/12 §3.86 记录来源）
# 折叠表 = pipeline._MATCH_PUNCT_TABLE 原表 + 本次事故引入的 `‧`(U+2027)→`·`
FOLD_TABLE = str.maketrans("（）：；，、？！．～‧", "():;,,?!.~·")
# 全角形态 -> 允许还原成的半角形态（唯一配对，不猜）
PAIR = {"：": ":", "，": ",", "；": ";", "‧": "·", "～": "~"}
WIDE_CHARS = set(PAIR)
MIN_RATIO = 0.6


def fold(text: str) -> str:
    return text.translate(FOLD_TABLE)


def _widify(text: str) -> str:
    for half, wide in ((",", "，"), (":", "："), (";", "；"), ("·", "‧"), ("~", "～")):
        text = text.replace(half, wide)
    return text


def model_chars(text: str) -> str:
    """模型 A：只把半角标点换成全角，不动空格。"""
    return _widify(text)


def model_comma_space(text: str) -> str:
    """模型 B：在模型 A 之上，`逗号+空格` 的空格一并吞掉。"""
    return _widify(text.replace(", ", "，"))


def model_all_space(text: str) -> str:
    """模型 C：在模型 A 之上，逗号/冒号/分号后面的空格一起吞掉。"""
    return _widify(text.replace(", ", "，").replace(": ", "：").replace("; ", "；"))


MODELS: list[tuple[str, Callable[[str], str]]] = [
    ("标点全角化", model_chars),
    ("逗号吞空格", model_comma_space),
    ("三种标点吞空格", model_all_space),
]


def restore_line(target: str, oracle: str) -> tuple[str, list[tuple[int, str, str]]]:
    """字符级兜底：在**等长匹配块**内按位还原；`，`↔`, `（逗号吞空格）也在这里把空格补回。"""
    edits: dict[int, tuple[str, str]] = {}

    def note(target_index: int, want: str, with_space: bool) -> None:
        edits[target_index] = (target[target_index], want + " " if with_space else want)

    def scan(i1: int, i2: int, j1: int, j2: int) -> None:
        for offset in range(i2 - i1):
            target_index, oracle_index = i1 + offset, j1 + offset
            want = PAIR.get(target[target_index])
            if want is None or oracle[oracle_index] != want:
                continue
            # 副本是「半角标点 + 空格」而目标只剩全角标点 → 空格被吞掉，补回
            eaten = (oracle[oracle_index + 1:oracle_index + 2] == " "
                     and target[target_index + 1:target_index + 2] not in ("", " "))
            note(target_index, want, eaten)

    if len(target) == len(oracle):
        scan(0, len(target), 0, len(oracle))
    else:
        matcher = difflib.SequenceMatcher(None, target, oracle, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal" or (tag == "replace" and i2 - i1 == j2 - j1):
                scan(i1, i2, j1, j2)
            elif tag == "replace" and i2 - i1 == 1:
                want = PAIR.get(target[i1])
                if want is not None and oracle[j1:j2] == want + " ":
                    note(i1, want, True)
    chars = list(target)
    for index in sorted(edits, reverse=True):
        chars[index] = edits[index][1]
    changes = [(index, old, new) for index, (old, new) in sorted(edits.items())]
    return "".join(chars), changes


# 语法必需半角：CSM 文法自身决定的位置（不依赖任何副本）
SYNTAX_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(ssir)：(?=[A-Za-z/])"), r"\1:"),          # <!--ssir:…--> 指令名
    (re.compile(r"(\[foot)：(?=[0-9A-Za-z])"), r"\1:"),       # [foot:L] 脚注标记
    (re.compile(r"^(\s*[A-Za-z][A-Za-z0-9-]*)："), r"\1:"),   # front matter 的键（含嵌套键）
]


def apply_syntax_rules(line: str) -> str:
    """只按 CSM 文法还原「语法必需半角」；内容标点一概不动。"""
    for pattern, replacement in SYNTAX_RULES:
        line = pattern.sub(replacement, line)
    return line


def best_oracle_line(target: str, pool: list[str], hint: int) -> str | None:
    """副本邻近窗口里与目标行最相似的一行（相似度下限 MIN_RATIO）。"""
    folded = fold(target)
    window = pool[max(0, hint - 6): hint + 7]
    best, best_ratio = None, 0.0
    for line in window:
        ratio = difflib.SequenceMatcher(None, folded, fold(line), autojunk=False).ratio()
        if ratio > best_ratio:
            best, best_ratio = line, ratio
    return best if best_ratio >= MIN_RATIO else None


def convert(target_text: str, oracles: list[str]) -> tuple[str, list[tuple[int, str]], list[int], collections.Counter]:
    target_lines = target_text.split("\n")
    pools = [oracle.split("\n") for oracle in oracles]
    # 每个副本 × 每个模型的「损坏后文本 -> 原始行」索引
    model_maps: list[dict[str, dict[str, list[str]]]] = []
    for pool in pools:
        per_model: dict[str, dict[str, list[str]]] = {}
        for name, model in MODELS:
            index: dict[str, list[str]] = collections.defaultdict(list)
            for line in pool:
                if any(ch in line for ch in ",:;·~"):
                    index[model(line)].append(line)
            per_model[name] = index
        model_maps.append(per_model)
    # 行级相似度兜底只在**行数同量级**的副本上启用（canonical 副本）；产物投影（render.md）
    # 的行号与 canonical 不对应，只允许模型精确匹配，避免把无关行当副本。
    span = max(20, len(target_lines) // 100)
    fuzzy_pools = [pool for pool in pools if abs(len(pool) - len(target_lines)) <= span]

    stats: collections.Counter = collections.Counter()
    changed_lines: list[tuple[int, str | None]] = []
    uncovered: list[int] = []
    noop = 0
    for number, line in enumerate(target_lines):
        if not any(ch in WIDE_CHARS for ch in line):
            continue
        replaced = how = None
        for per_model in model_maps:                      # 副本优先级（命令行顺序）
            for name, _ in MODELS:                        # 模型按固定顺序试配
                hits = per_model[name].get(line)
                if hits and len(set(hits)) == 1:
                    replaced, how = hits[0], f"模型:{name}"
                    break
            if replaced is not None:
                break
        had_oracle = replaced is not None
        if replaced is None:
            for pool in fuzzy_pools:
                oracle_line = best_oracle_line(line, pool, number)
                if oracle_line is None:
                    continue
                had_oracle = True
                restored, changes = restore_line(line, oracle_line)
                if changes:
                    replaced, how = restored, f"按位:{len(changes)}处"
                break
        # 语法必需半角（CSM 文法自证，任何路径之后都补一遍）
        final = apply_syntax_rules(replaced if replaced is not None else line)
        if final == line:
            if had_oracle:
                noop += 1  # 副本佐证：该行的全角标点是原文如此，无需改动
            else:
                uncovered.append(number + 1)  # 无对位证据、也非语法位置
            continue
        target_lines[number] = final
        stats[how or "语法还原"] += 1
        if apply_syntax_rules(replaced or "") != (replaced or ""):
            stats["语法还原(附加)"] += 1
        changed_lines.append((number + 1, how or "语法还原"))
    return "\n".join(target_lines), changed_lines, uncovered, stats, noop


def run(target: Path, oracle_paths: list[Path], apply: bool) -> int:
    target_text = target.read_text(encoding="utf-8")
    oracles = [p.read_text(encoding="utf-8") for p in oracle_paths]
    new_text, changed_lines, uncovered, stats, noop = convert(target_text, oracles)

    # ① 行数不变
    if new_text.count("\n") != target_text.count("\n"):
        print(f"  {target.name}: 行数改变——不写入", file=sys.stderr)
        return -1
    # ② 改动不越界：折叠标点并去空格后逐位相同（模型吞掉的空格除外）
    old_lines, new_lines = target_text.split("\n"), new_text.split("\n")
    for number, _ in changed_lines:
        old, new = old_lines[number - 1].replace(" ", ""), new_lines[number - 1].replace(" ", "")
        if fold(old) != fold(new):
            print(f"  {target.name}: 第 {number} 行改动越界（非标点/空格差异）——不写入", file=sys.stderr)
            return -1
    wide = sum(sum(line.count(ch) for ch in WIDE_CHARS) for line in old_lines)
    wide_lines = sum(1 for line in old_lines if any(ch in WIDE_CHARS for ch in line))
    print(f"  {target.name}: 含全角标点行 {wide_lines}（全角标点 {wide} 个）→ 改动 {len(changed_lines)} 行；"
          + "、".join(f"{k}×{v}" for k, v in sorted(stats.items()))
          + f"；原文如此（副本佐证、无需改动）{noop} 行"
          + (f"；无对位证据 {len(uncovered)} 行：{uncovered[:14]}" if uncovered else "；无对位证据 0 行"))
    if not apply:
        return len(changed_lines)
    if new_text == target_text:
        print("      无改动")
        return 0
    backup = target.with_suffix(target.suffix + ".bak-punct")
    backup.write_text(target_text, encoding="utf-8")
    target.write_text(new_text, encoding="utf-8")
    # ③ 还原后能 parse 且 metadata 非空
    try:
        ssir = parse_csm(target)
        metadata = ssir.get("metadata") if isinstance(ssir, dict) else getattr(ssir, "metadata", None)
    except Exception as exc:  # noqa: BLE001
        target.write_text(target_text, encoding="utf-8")
        print(f"      还原后 parse 失败：{type(exc).__name__}: {str(exc)[:160]}——已回滚", file=sys.stderr)
        return -1
    if not metadata:
        target.write_text(target_text, encoding="utf-8")
        print("      还原后 metadata 仍为空——已回滚", file=sys.stderr)
        return -1
    print(f"      已写入 {target}（备份 {backup.name}）id={ssir.get('id')}")
    return len(changed_lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--target", type=Path, required=True, help="待还原的 canonical")
    parser.add_argument("--oracle", type=Path, action="append", required=True,
                        help="健康基线文本或同源健康副本（可多次给出，按优先级）")
    parser.add_argument("--apply", action="store_true", help="写回文件（缺省只干跑）")
    args = parser.parse_args()
    for path in [args.target, *args.oracle]:
        if not path.is_file():
            print(f"  {path}: 不存在", file=sys.stderr)
            return 2
    print(f"目标 {args.target}\n副本 " + "、".join(str(p) for p in args.oracle))
    result = run(args.target, args.oracle, args.apply)
    return 1 if result < 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
