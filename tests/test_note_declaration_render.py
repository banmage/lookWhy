"""P0-E 零推断：`notes[]`（`ssir:note` 声明的注）在渲染端的处置口径回归。

度量结论（2026-09-22，见 docs/16 §12）：声明的注**由内容元素原位绘制**（`contentRef` 指向的
`note`/`warning` 内容元素走既有 note 样式），渲染端**不消费** `notes[]` 做二次绘制：
- `notes[].label` 是结构化元数据（同一要素内多个注的编号来源），渲染端不据此**重写引导词**——
  把正文的「注：」改写成「注1：」属规范化改写，需专门规则 + 回归 + 跨语料验证，不在「零推断」
  范围内（AGENTS.md §0.3：抽取真值原样呈现，不用推断值替换）。
本文件锁该行为：注文必须出现，label 不得被无声明地注入渲染产物。
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from leleby_ssir.service import parse_csm

FIXTURE = """\
---
csm-version: "1.0"
document-type: standard
document-identifier: "Q/XYZ 006—2026"
standard-number: "Q/XYZ 006—2026"
title: "注声明渲染夹具"
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

# 注声明渲染夹具

## 1 范围

本文档用于注声明渲染回归。

<!-- ssir:note kind="clause" label="注1" -->
> 注：本条为条款注。

| 表头 | 值 |
| --- | --- |
| a | 1 |

<!-- ssir:note kind="table" label="注2" -->
> 注：表下注。
"""


class NoteDeclarationRenderTests(unittest.TestCase):
    def test_note_registry_is_structured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.md"
            path.write_text(FIXTURE, encoding="utf-8")
            ssir = parse_csm(path)
        notes = ssir.get("notes") or []
        self.assertEqual([note["kind"] for note in notes], ["clause", "table"])
        self.assertEqual([note["label"] for note in notes], ["注1", "注2"])
        for note in notes:
            self.assertTrue(note["ownerRef"].startswith("Q_XYZ_006-2026#"))
            self.assertTrue(note["contentRef"].startswith("Q_XYZ_006-2026#"))

    def test_note_text_renders_in_place_and_label_is_not_injected(self) -> None:
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
            source.write_text(FIXTURE, encoding="utf-8")
            ssir = parse_csm(source)
            ssir_path = root / "doc.ssir.json"
            ssir_path.write_text(json.dumps(ssir, ensure_ascii=False), encoding="utf-8")
            target = root / "doc.render.pdf"
            render_pdf_file(ssir_path, target)
            document = pymupdf.open(str(target))
            text = "".join(page.get_text() for page in document)

        self.assertIn("本条为条款注", text, "声明的注文本未原位绘制")
        self.assertIn("表下注", text, "表下注文本未原位绘制")
        # 零推断：不得把 notes[].label 拼进正文（正文是抽取真值，原样呈现）
        self.assertNotIn("注1", text, "渲染端把 label 注入正文（越出零推断范围）")
        self.assertNotIn("注2", text, "渲染端把 label 注入正文（越出零推断范围）")


if __name__ == "__main__":
    unittest.main()
