"""图表脚注锚点（docs/15 §2；GB/T 1.1 9.12.2）：引用点、`notes[].anchorKind` 与绘制位置。

落点（2026-09-22）：
- 引用点扫描扩展到**表内/图内文本**（内容元素的 canonical 片段），表/图元素成为锚点；
- `notes[]` 为脚注登记 `type=footnote` + `anchorKind`（表 → `tableCell`、图 → `figurePart`、
  其余 → `page`），`ownerRef` 是锚点元素、`contentRef` 是脚注内容元素；
- `Table.noteRefs` 写**注的标识**（TDRS 引用），不写角标字母；
- 网格一格里多个角标（`[foot:b、d]`）展开为两个引用点，渲染成并排上角标 `b)d)`；
- 图表脚注**原位**排在表/图之下（不走页脚钩子——页脚排不下时实测丢字，GB_T_5171.1-2014
  8 条定义里丢 5 条），条文脚注仍走页脚。
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from leleby_ssir.service import parse_csm

FIXTURE = """\
---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/XYZ 007—2026"
standard-number: "Q/XYZ 007—2026"
title: "图表脚注锚点夹具"
language: zh-CN
source:
  mode: user-markdown
  original-file-name: "fixture.md"
  provenance: none
rendering-profile: GB_T_1.1-2020
extensions:
  standard-profile: product
  profile-rules: ["GB_T_1.1-2020"]
---

# 图表脚注锚点夹具

## 1 范围

本文档用于图表脚注锚点回归。

| 项目 | 要求 |
| --- | --- |
| 径向间隙[foot:a、b] | 3 |

<!--ssir:foot:a-->分装式电动机不检验。<!--ssir:/foot-->
<!--ssir:foot:b-->可用部件进行检验。<!--ssir:/foot-->

<!-- ssir:figure id="fig-001" asset-status="missing" -->
> [图1 电路图[foot:c]]

<!--ssir:foot:c-->图中尺寸单位为毫米。<!--ssir:/foot-->

条文脚注见下[foot:1]。

<!--ssir:foot:1-->条文脚注排页脚。<!--ssir:/foot-->
"""


def _parse(tmp: Path):
    source = tmp / "fixture.md"
    source.write_text(FIXTURE, encoding="utf-8")
    return parse_csm(source)


class FootnoteAnchorKindTests(unittest.TestCase):
    def test_anchor_kinds_and_note_refs_are_structured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ssir = _parse(Path(tmp))
        footnotes = [n for n in (ssir.get("notes") or []) if n.get("type") == "footnote"]
        by_label = {str(n.get("label")): n for n in footnotes}
        self.assertEqual(sorted(by_label), ["1", "a", "b", "c"])
        self.assertEqual(by_label["a"]["anchorKind"], "tableCell")
        self.assertEqual(by_label["b"]["anchorKind"], "tableCell")
        self.assertEqual(by_label["c"]["anchorKind"], "figurePart")
        self.assertEqual(by_label["1"]["anchorKind"], "page")
        self.assertEqual(by_label["a"]["kind"], "table")
        self.assertEqual(by_label["c"]["kind"], "figure")
        self.assertEqual(by_label["1"]["kind"], "clause")
        for label, note in by_label.items():
            self.assertTrue(str(note["ownerRef"]).startswith("Q_XYZ_007-2026#"), label)
            self.assertTrue(str(note["contentRef"]).startswith("Q_XYZ_007-2026#"), label)
        # ownerRef 指向**表/图内容元素**（而不是条款节点）：一格多角标的两个标签同锚点
        self.assertEqual(by_label["a"]["ownerRef"], by_label["b"]["ownerRef"])

    def test_table_note_refs_use_note_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ssir = _parse(Path(tmp))
        tables = [t for t in (ssir.get("tables") or []) if t.get("noteRefs")]
        self.assertEqual(len(tables), 1, "应恰有一张表带 noteRefs")
        refs = tables[0]["noteRefs"]
        self.assertEqual(len(refs), 2, "一格多角标应展开为两个引用点")
        for ref in refs:
            self.assertRegex(ref, r"^Q_XYZ_007-2026#[A-Za-z0-9][A-Za-z0-9._/-]*$")
        note_ids = {str(n["id"]) for n in ssir["notes"] if n.get("type") == "footnote"}
        self.assertTrue(set(refs) <= note_ids, "noteRefs 必须是 notes[] 的注标识")

    def test_table_footnotes_render_in_place_and_page_footnote_at_bottom(self) -> None:
        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        from leleby_ssir.pdf_renderer import render_pdf_file

        font_asset = Path(__file__).resolve().parents[1] / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font_asset.is_file():
            self.skipTest("body font asset missing")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ssir = _parse(root)
            ssir_path = root / "doc.ssir.json"
            ssir_path.write_text(json.dumps(ssir, ensure_ascii=False), encoding="utf-8")
            target = root / "doc.render.pdf"
            render_pdf_file(ssir_path, target)
            document = pymupdf.open(str(target))
            text = "".join(page.get_text() for page in document)

        flat = re.sub(r"\s+", "", text)
        # 图表脚注定义：原位（正文流里），三条都在文本层
        for fragment in ("分装式电动机不检验", "可用部件进行检验", "图中尺寸单位为毫米", "条文脚注排页脚"):
            self.assertIn(fragment, flat, f"脚注定义未绘出：{fragment}")
        # 一格多角标 → 上标「a、b」连排（GB/T 1.1-2020 9.12.2；源版面实测分隔符「、」
        # 本身也是 4.66pt 上标 span，标记**不带**半圆括号）
        self.assertRegex(flat, r"径向间隙a、b|径向间隙b、a")
        # 不泄漏标记
        self.assertNotIn("[foot:", flat)
        self.assertNotIn("ssir:", flat)


SHARED_LABEL_FIXTURE = """\
---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/XYZ 008—2026"
standard-number: "Q/XYZ 008—2026"
title: "标签重号锚点夹具"
language: zh-CN
source:
  mode: user-markdown
  original-file-name: "fixture.md"
  provenance: none
rendering-profile: GB_T_1.1-2020
extensions:
  standard-profile: product
  profile-rules: ["GB_T_1.1-2020"]
---

# 标签重号锚点夹具

## 1 范围

| 项目 | 要求 |
| --- | --- |
| 径向间隙[foot:a] | 3 |

<!--ssir:foot:a-->表的脚注。<!--ssir:/foot-->

## 2 图的脚注

<!-- ssir:figure id="fig-002" asset-status="missing" -->
> [图2 封面格式]

<!--ssir:foot:a-->图的脚注（编号只画在图内，无文本引用点）。<!--ssir:/foot-->
"""

BOXED_PAGE_FOOTNOTE_FIXTURE = """\
---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/XYZ 009—2026"
standard-number: "Q/XYZ 009—2026"
title: "框内条文脚注夹具"
language: zh-CN
source:
  mode: user-markdown
  original-file-name: "fixture.md"
  provenance: none
rendering-profile: GB_T_1.1-2020
extensions:
  standard-profile: product
  profile-rules: ["GB_T_1.1-2020"]
---

# 框内条文脚注夹具

## 3 示例

<!-- ssir:box -->
框内条文脚注见下[foot:1]。

<!--ssir:foot:1-->框内脚注内容不得丢失。<!--ssir:/foot-->
<!-- ssir:/box -->
"""


class SameLabelAcrossNodesTests(unittest.TestCase):
    """GEN-124：标签跨节点重号（图的 `a` 与别处表的 `a`）不得把锚点配到远处那张表。"""

    def test_citation_scope_is_own_node(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "fixture.md"
            source.write_text(SHARED_LABEL_FIXTURE, encoding="utf-8")
            ssir = parse_csm(source)
        notes = [n for n in (ssir.get("notes") or []) if n.get("type") == "footnote"]
        self.assertEqual(len(notes), 2, "两条同标签定义都应登记")
        kinds = sorted(str(n.get("anchorKind")) for n in notes)
        self.assertEqual(kinds, ["figurePart", "tableCell"])
        figure_note = next(n for n in notes if n.get("anchorKind") == "figurePart")
        self.assertEqual(figure_note.get("kind"), "figure")
        owners = {str(n.get("ownerRef")) for n in notes}
        self.assertEqual(len(owners), 2, "两条同标签定义的锚点必须不同（各归各的表/图）")

    def test_adjacent_figure_gets_the_uncited_definition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "fixture.md"
            source.write_text(SHARED_LABEL_FIXTURE, encoding="utf-8")
            ssir = parse_csm(source)
        notes = [n for n in ssir["notes"] if n.get("type") == "footnote"]
        figure_note = next(n for n in notes if n.get("anchorKind") == "figurePart")
        table_note = next(n for n in notes if n.get("anchorKind") == "tableCell")
        # 锚点元素各在自己的节点里：图下脚注挂在 §2 的图内容元素上，不跨到 §1 的表。
        self.assertIn("#2/", str(figure_note["ownerRef"]))
        self.assertIn("#1/", str(table_note["ownerRef"]))
        figure_ids = {str(f.get("id")) for f in (ssir.get("figures") or [])}
        self.assertTrue(figure_ids, "夹具应产出图本体对象")


class BoxedPageFootnoteTests(unittest.TestCase):
    """GEN-125：框内条文脚注不能丢——页脚钩子在框表内不触发，改就地绘制。"""

    def test_boxed_page_footnote_is_drawn(self) -> None:
        try:
            import pymupdf
        except ImportError:  # pragma: no cover
            self.skipTest("pymupdf unavailable")
        from leleby_ssir.pdf_renderer import render_pdf_file

        font_asset = Path(__file__).resolve().parents[1] / "config" / "rendering" / "fonts" / "NotoSerifCJKsc-Regular.ttf"
        if not font_asset.is_file():
            self.skipTest("body font asset missing")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "fixture.md"
            source.write_text(BOXED_PAGE_FOOTNOTE_FIXTURE, encoding="utf-8")
            ssir = parse_csm(source)
            anchor = [n for n in ssir["notes"] if str(n.get("label")) == "1"]
            self.assertEqual(len(anchor), 1)
            self.assertEqual(anchor[0].get("anchorKind"), "page", "框内条文脚注仍是 page 锚点")
            ssir_path = root / "doc.ssir.json"
            ssir_path.write_text(json.dumps(ssir, ensure_ascii=False), encoding="utf-8")
            target = root / "doc.render.pdf"
            render_pdf_file(ssir_path, target)
            document = pymupdf.open(str(target))
            text = "".join(page.get_text() for page in document)
            document.close()

        flat = re.sub(r"\s+", "", text)
        self.assertIn("框内脚注内容不得丢失", flat, "框内脚注定义被丢弃")
        self.assertNotIn("ssir:", flat)


if __name__ == "__main__":
    unittest.main()

