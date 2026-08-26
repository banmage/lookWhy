#!/usr/bin/env python3
"""Prepare the Song (宋体) body font used by the GB/T 1.1 rendering profile.

思源宋体（Noto Serif CJK SC）是大陆标准开源宋体，全角标点贴底（AR PL UMing
的标点居中，渲染出的句号/顿号悬在行高一半处）。系统里的 Noto Serif CJK 是
CFF 轮廓的 .ttc，reportlab 的 TTFont 无法加载，因此本脚本将其转换为
TrueType 版并输出到 config/rendering/fonts/。

用法:
    .venv/bin/pip install afdko   # 提供 otf2ttf（仅首次需要）
    .venv/bin/python tools/prepare_serif_font.py

依赖: fontTools（项目已用）、afdko 的 otf2ttf 命令行。
产物: config/rendering/fonts/NotoSerifCJKsc-Regular.ttf (~31MB)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "config" / "rendering" / "fonts"
OUTPUT = OUT_DIR / "NotoSerifCJKsc-Regular.ttf"
SOURCE_CANDIDATES = [
    Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSerifCJKsc-Regular.otf"),
    Path("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.otf"),
]


def find_source() -> Path:
    for candidate in SOURCE_CANDIDATES:
        if candidate.is_file():
            return candidate
    raise SystemExit(
        "Noto Serif CJK Regular not found. Install it with:\n"
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
    temp_otf = OUT_DIR / "NotoSerifCJKsc-Regular.otf.tmp"

    if source.suffix.lower() == ".ttc":
        number = find_sc_font_number(source)
        print(f"extracting SC subfont (fontNumber={number}) from {source}")
        TTFont(str(source), fontNumber=number).save(str(temp_otf))
    else:
        temp_otf.write_bytes(source.read_bytes())

    otf2ttf = shutil.which("otf2ttf") or str(ROOT / ".venv" / "bin" / "otf2ttf")
    if not Path(otf2ttf).is_file():
        raise SystemExit(
            "otf2ttf not found. Install it with: .venv/bin/pip install afdko"
        )
    print(f"converting CFF -> TrueType via {otf2ttf} (one-time, ~90s)")
    subprocess.run([otf2ttf, str(temp_otf), "-o", str(OUTPUT)], check=True)
    temp_otf.unlink(missing_ok=True)
    print(f"done: {OUTPUT} ({OUTPUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    sys.exit(main())
