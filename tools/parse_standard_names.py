#!/usr/bin/env python3
"""批量解析标准名称 → 标准类型 / 标准化主对象 / 应用场合 / 修饰词。

用法:
    python tools/parse_standard_names.py 标准名称.csv
    python tools/parse_standard_names.py 标准名称.csv -o 解析结果.tsv

输入 CSV 需含「标准号」「标准中文名称」两列（表头顺序不限，GBK 或 UTF-8
自动识别）。输出 TSV 便于在表格软件中查看；不指定 -o 时打印前 20 行预览
与类型统计。

示例:
    python tools/parse_standard_names.py 标准名称.csv -o /tmp/parsed.tsv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leleby_ssir.standard_name import parse_standard_name  # noqa: E402


def _read_csv(path: Path) -> list[tuple[str, str]]:
    """读取 CSV（自动识别 GBK / UTF-8），返回 [(标准号, 名称)]。"""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gbk"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"无法识别 {path} 的编码（尝试了 UTF-8/GBK）")
    rows = list(csv.DictReader(text.splitlines()))
    if not rows:
        raise ValueError(f"{path} 为空或没有数据行")
    num_key = next((k for k in rows[0] if "标准号" in k), None)
    name_key = next((k for k in rows[0] if "名称" in k), None)
    if not name_key:
        raise ValueError(f"CSV 缺少「标准中文名称」列，实际表头: {list(rows[0])}")
    return [(row.get(num_key, "").strip(), row[name_key].strip()) for row in rows]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("csv", type=Path, help="标准名称 CSV（GBK 或 UTF-8）")
    parser.add_argument("-o", "--output", type=Path, help="输出 TSV 路径（默认仅打印预览）")
    args = parser.parse_args()

    pairs = _read_csv(args.csv)
    parsed = []
    for num, name in pairs:
        info = parse_standard_name(name)
        parsed.append((num, name, info))

    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerow(["标准号", "标准中文名称", "标准类型", "主对象", "应用场合", "修饰词", "类型依据", "置信度"])
            for num, name, info in parsed:
                writer.writerow(
                    [num, name, info.standard_type, info.subject, info.application,
                     info.modifier, info.type_basis, info.confidence]
                )
        print(f"已写出 {len(parsed)} 条 → {args.output}")

    print(f"\n共 {len(parsed)} 条，类型分布：")
    for t, c in Counter(i.standard_type for _, _, i in parsed).most_common():
        print(f"  {t:<6} {c}")
    print("\n预览（前 20 条）：")
    print(f"{'标准号':<20}{'类型':<8}{'主对象':<14}{'场合':<8}{'名称'}")
    print("-" * 100)
    for num, name, info in parsed[:20]:
        print(f"{num:<20}{info.standard_type:<8}{info.subject:<14}{info.application or '-':<8}{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
