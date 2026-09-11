#!/usr/bin/env python3
"""Prepare the bold Hei (黑体粗) font used for 注/示例 markers in the PDF.

GB/T 1.1-2020 10.4.4.1/10.4.5 与附录 F 表 F.1（序号 42/44）要求「注：」「注×：」
「示例：」「示例×：」用**小五号黑体**，而正文内容是宋体——标记与内容必须能一眼
分开。渲染 profile 的 primary（文泉驿正黑）是**细黑**：9pt 下实测笔画密度与宋体
正文相当（注 0.209 vs 按 0.232 墨度），换字体而不换字重看不出「加黑」，用户反馈
「注：仍没有加粗」即此。系统里的思源黑体 Bold（Noto Sans CJK SC Bold）是 CFF
轮廓的 .ttc，reportlab 的 TTFont 无法加载，故本脚本把它转成 TrueType 版。

用法:
    .venv/bin/pip install afdko   # 提供 otf2ttf（仅首次需要）
    .venv/bin/python tools/prepare_label_font.py

依赖: fontTools、afdko 的 otf2ttf 命令行。
产物: config/rendering/fonts/NotoSansCJKsc-Bold.ttf (~30MB)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "config" / "rendering" / "fonts"
OUTPUT = OUT_DIR / "NotoSansCJKsc-Bold.ttf"
SOURCE_CANDIDATES = [
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJKsc-Bold.otf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.otf"),
]


def find_source() -> Path:
    for candidate in SOURCE_CANDIDATES:
        if candidate.is_file():
            return candidate
    raise SystemExit(
        "Noto Sans CJK Bold not found. Install it with:\n"
        "  sudo apt-get install fonts-noto-cjk-extra"
    )


def find_sc_font_number(ttc_path: Path) -> int:
    """Locate the Simplified Chinese (SC) subfont inside a .ttc."""
    for number in range(8):
        try:
            font = TTFont(str(ttc_path), fontNumber=number, lazy=True)
            name = font["name"].getDebugName(1) or ""
        except Exception:
            continue
        if "SC" in name:
            return number
    raise SystemExit(f"no Simplified Chinese subfont found in {ttc_path}")


def main() -> None:
    source = find_source()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    temp_otf = OUT_DIR / "NotoSansCJKsc-Bold.otf.tmp"

    if source.suffix.lower() == ".ttc":
        number = find_sc_font_number(source)
        print(f"extracting SC subfont (fontNumber={number}) from {source}")
        TTFont(str(source), fontNumber=number).save(str(temp_otf))
    else:
        temp_otf.write_bytes(source.read_bytes())

    otf2ttf = shutil.which("otf2ttf") or str(ROOT / ".venv" / "bin" / "otf2ttf")
    if not Path(otf2ttf).is_file():
        raise SystemExit("otf2ttf not found. Install it with: .venv/bin/pip install afdko")
    print(f"converting CFF -> TrueType via {otf2ttf} (one-time, ~90s)")
    subprocess.run([otf2ttf, str(temp_otf), "-o", str(OUTPUT)], check=True)
    temp_otf.unlink(missing_ok=True)
    print(f"done: {OUTPUT} ({OUTPUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    sys.exit(main())
