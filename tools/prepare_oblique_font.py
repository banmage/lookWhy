#!/usr/bin/env python3
"""Prepare the synthetic-oblique (机斜) TrueType faces used for canonical emphasis.

GB/T 20001.10-2014 表1 用字体语义区分要素属性（表注「a黑体表示"必备要素"；
正体表示"规范性要素"；斜体表示"资料性要素"），canonical 用 CSM 强调标记表达
（docs/07 §6.1：`**粗体**`、`*斜体*`、`***粗斜体***`）。渲染端「粗体」用黑体
（profile `fonts.label`，思源黑体 Bold），而「斜体」在中文里是**机斜**（把字面
整体向右倾斜），源 PDF 实测倾斜角 **15.8°**（tan≈0.282，GB_T_20001.10-2014
表1「目次」的「目」左竖笔按行最左墨迹线性拟合）。

reportlab 无法对字面做剪切（`<i>` 只查已注册的字族成员，未注册时静默保持原
字体——与 GBT-B10「reportlab cannot fake bold」同源），故斜体必须是**真实字体
资产**：本脚本把已入库的 TrueType 字体（宋体 Regular / 思源黑体 Bold，二者已是
otf2ttf 转换后的 TrueType）按剪切矩阵 x' = x + 0.282·y 逐笔形改写，并置
post.italicAngle / head.macStyle / OS/2.fsSelection 的斜体位。

用法:
    .venv/bin/python tools/prepare_oblique_font.py

依赖: fontTools（项目已依赖）。
产物:
    config/rendering/fonts/NotoSerifCJKsc-Oblique.ttf      （正文宋体机斜）
    config/rendering/fonts/NotoSansCJKsc-BoldOblique.ttf   （注/示例黑体粗机斜）
"""
from __future__ import annotations

import sys
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "config" / "rendering" / "fonts"
# 剪切系数 = tan(15.8°)，源 PDF 实测（见模块 docstring）。
SLANT = 0.282
# (源字体, 产物, 产物家族名, 产物子家族名)
TARGETS = (
    ("NotoSerifCJKsc-Regular.ttf", "NotoSerifCJKsc-Oblique.ttf", "Noto Serif CJK SC Oblique", "Regular"),
    ("NotoSansCJKsc-Bold.ttf", "NotoSansCJKsc-BoldOblique.ttf", "Noto Sans CJK SC Bold Oblique", "Bold"),
)
ITALIC_ANGLE = -15.8


def _rename(font: TTFont, ps_name: str, family: str, subfamily: str) -> None:
    """改写 name 表（ID 1/2/4/6/16/17），使机斜字体有**独立的 PostScript 名**。

    必须改：reportlab 在 `pdfmetrics.registerFont` 里按 `face.name`（= name 表 ID 6
    PostScript 名）去重——两份字体同名时后注册的会被丢弃、直接复用先注册的字体
    对象（实测：字形已机斜但 PDF 文本层仍是 Regular 字体名，`<i>` 静默无效）。
    """
    name = font["name"]
    full = family if subfamily == "Regular" else f"{family} {subfamily}"
    values = {1: family, 2: subfamily, 4: full, 6: ps_name, 16: family, 17: subfamily}
    for record in list(name.names):
        if record.nameID in values:
            name.setName(values[record.nameID], record.nameID, record.platformID, record.platEncID, record.langID)


def _skew_glyphs(font: TTFont) -> int:
    """把 glyf 全部笔形按剪切矩阵改写；返回处理的字形数。"""
    glyf = font["glyf"]
    order = font.getGlyphOrder()
    for name in order:
        glyph = glyf[name]
        if glyph.isComposite():
            # 复合字形的基字形已被剪切，组件自身的平移量随之变换：
            # 期望 S(T(base)) = T'(S(base))，其中 T' 的平移 = (dx + k·dy, dy)。
            for component in glyph.components:
                component.x = int(round(component.x + SLANT * component.y))
            glyph.recalcBounds(glyf)
            continue
        coordinates = getattr(glyph, "coordinates", None)
        if not coordinates:
            continue
        for index in range(len(coordinates)):
            x, y = coordinates[index]
            coordinates[index] = (int(round(x + SLANT * y)), y)
        glyph.recalcBounds(glyf)
    return len(order)


def _mark_italic(font: TTFont) -> None:
    """置斜体位（italicAngle / macStyle / fsSelection），供 PDF 字体描述符分类。"""
    font["post"].italicAngle = ITALIC_ANGLE
    font["head"].macStyle |= 0b10
    os2 = font.get("OS/2")
    if os2 is not None:
        # bit0 = ITALIC，bit6 = REGULAR（italic 与 regular 互斥，置斜体时清常规；
        # bit5 = BOLD 保留——黑体粗机斜仍是粗体）。
        os2.fsSelection |= 0b1
        os2.fsSelection &= ~0b1000000


def oblique(source: Path, target: Path, family: str, subfamily: str) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"源字体不存在: {source}（先运行 tools/prepare_serif_font.py / prepare_label_font.py）")
    font = TTFont(str(source))
    count = _skew_glyphs(font)
    _mark_italic(font)
    _rename(font, target.stem, family, subfamily)
    font.save(str(target))
    print(f"{source.name} → {target.name}：{count} 个字形机斜（k={SLANT}），{target.stat().st_size / 1e6:.1f} MB")


def main() -> int:
    for source_name, target_name, family, subfamily in TARGETS:
        oblique(FONT_DIR / source_name, FONT_DIR / target_name, family, subfamily)
    return 0


if __name__ == "__main__":
    sys.exit(main())
