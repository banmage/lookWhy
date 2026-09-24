#!/usr/bin/env python3
"""Replay TDRS 元素命名（docs/16 §10）onto existing SSIR products.

规则（`builder.assign_element_ids`，与新建产物同源）：SSIR 元素标识统一为
``{标准标识}#{条款路径}``——正文章条 ``#8.2.1``、附录 ``#Annex_A``/``#Annex_A.1``、
表/图/公式 ``#Table_3``/``#Figure_5``/``#Formula_3``（附录内带字母 ``#Table_A.1``）、
无编号要素 ``#Foreword``/``#Contents``…、内容元素 ``#<条款路径>/<Kind>-<序号>``、
列表项 ``#<条款路径>_<marker>``；文档标识（旧 ``ssir:*``）改为标准号转义
（``GB_T_1.1-2020``）。标准标识取自 ``metadata.standard.standardNumber``，不猜。

只改标识类字段（id/logicalId/documentId/runId/parentNodeId/*Ref/unresolvedFigures/
sourceElementRefs）；其余 JSON 路径必须逐值不变（脚本自带内容不变量断言）。规则幂等，
重复运行零命中；schema 校验前后都必须通过。

用法：
    .venv/bin/python tools/replay_element_ids.py            # 干跑，只列将要改的产物
    .venv/bin/python tools/replay_element_ids.py --apply    # 写回
    .venv/bin/python tools/replay_element_ids.py --apply <ssir.json | 文档根目录>
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from leleby_ssir.builder import apply_element_ids  # noqa: E402
from leleby_ssir.exporters import json_bytes  # noqa: E402
from leleby_ssir.validation import SSIRValidationError, validate_ssir  # noqa: E402

# 允许被回放改写的 JSON 字段（标识类）；其余字段变化即内容不变量违例。
IDENTITY_FIELDS = {
    "id", "logicalId", "documentId", "runId", "parentNodeId",
    "tableRef", "figureRef", "formulaRef", "unknownRef", "footnoteAnchorRef",
    "unresolvedFigures", "sourceElementRefs",
}


def _flatten(node: Any, prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    if isinstance(node, dict):
        for key, value in node.items():
            flat.update(_flatten(value, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            flat.update(_flatten(value, f"{prefix}[{index}]"))
    else:
        flat[prefix] = node
    return flat


def _legacy_ids(ssir: dict[str, Any]) -> list[str]:
    """旧形态标识（``ssir:*`` 前缀或非 TDRS 的 id 字段）。"""
    flat = _flatten(ssir)
    return sorted({str(value) for key, value in flat.items()
                   if key.split(".")[-1].split("[")[0] in IDENTITY_FIELDS
                   and isinstance(value, str) and value.startswith("ssir:")})


def _legacy_id_error(message: str) -> bool:
    """旧产物预期失败：标识字段不符合 TDRS pattern（旧 ``ssir:*`` 或 ``li-0001`` 形态）。"""
    match = re.match(r"^schema (?P<path>[^:]+): .* does not match ", message)
    if not match:
        return False
    field = match.group("path").split("/")[-1].split("[")[0]
    return field in IDENTITY_FIELDS


def replay(path: Path, *, apply: bool) -> tuple[int, list[str]]:
    """单个 SSIR → (改动字段数, 登记信息)；apply 时写回（内容不变量 + 幂等断言）。"""
    original = json.loads(path.read_text(encoding="utf-8"))
    try:
        validate_ssir(original)
    except SSIRValidationError as exc:
        # 旧产物带 ``ssir:*`` 标识，必然不通过；但只允许这一类错误通过——其它
        # schema/语义问题必须照常抛出（回放不负责掩盖无关缺陷）。
        if not all(_legacy_id_error(message) for message in exc.errors):
            raise
    updated = copy.deepcopy(original)
    collisions, fallbacks = apply_element_ids(updated)

    before, after = _flatten(original), _flatten(updated)
    assert set(before) == set(after), f"{path}: 回放增删了字段"
    changed = [key for key in before if before[key] != after[key]]
    for key in changed:
        field = key.split(".")[-1].split("[")[0]
        assert field in IDENTITY_FIELDS, f"{path}: 回放改动了非标识字段 {key}"
    validate_ssir(updated)

    # 幂等：对已回放的结果再执行一次，结果必须逐值相同。
    twice = copy.deepcopy(updated)
    apply_element_ids(twice)
    assert _flatten(twice) == _flatten(updated), f"{path}: 回放不幂等"

    if apply and changed:
        path.write_bytes(json_bytes(updated))
    notes = [f"collision {item}" for item in collisions] + [
        f"fallback {item}" for item in fallbacks
    ]
    return len(changed), notes


def _targets(args: list[str]) -> list[Path]:
    if args:
        paths: list[Path] = []
        for raw in args:
            path = Path(raw)
            if path.is_dir():
                found = sorted(path.glob("03_ssir/*.ssir.json")) or sorted(path.glob("*.ssir.json"))
                paths.extend(found)
            else:
                paths.append(path)
        return paths
    return sorted(ROOT.glob("out/mineru/*/03_ssir/*.ssir.json")) + sorted(
        ROOT.glob("tests/fixtures/*.ssir.json")
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="*", help="SSIR 文件或文档根目录（默认 out/mineru/* + tests/fixtures）")
    parser.add_argument("--apply", action="store_true", help="写回 SSIR（默认只报告）")
    options = parser.parse_args()
    total = 0
    for path in _targets(options.paths):
        if not path.is_file():
            print(f"skip (not a file): {path}", file=sys.stderr)
            continue
        ssir = json.loads(path.read_text(encoding="utf-8"))
        legacy = _legacy_ids(ssir)
        changes, notes = replay(path, apply=options.apply)
        total += changes
        name = path.parent.parent.name if path.parent.name == "03_ssir" else path.name
        print(f"{'write' if options.apply else 'would write'} {name:30s} fields={changes:5d} legacy-ids={len(legacy)}")
        for note in notes:
            print(f"    {name:30s} {note}")
    print(f"{'applied' if options.apply else 'dry run'}: {total} field(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
