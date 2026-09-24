"""ssir:box 显式文档框声明（2026-09-08 实施，docs/13 裁定推广为任意文档块）。

回归夹具覆盖：
- parser：开/关事件块、配对/嵌套/未闭合的 CSM-STRUCT-006 校验；
- builder：节点级与"同一条款内容中途"的框归属 + style 透传；
- csm_renderer：标记确定性重放 → roundtrip（box 纳入比较口径）等价；
- 无标记文档零命中（既有启发式路径不受影响）。
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from leleby_ssir.builder import SSIRBuilder
from leleby_ssir.parser import CSMParser

ROOT = Path(__file__).resolve().parents[1]

CANON = """---
csm-version: 1.0
document-type: standard
document-identifier: T_BOX_001-2026
standard-number: T/BOX 001-2026
title: 框声明测试文档
language: zh-CN
---
# 框声明测试文档
## 1 范围
本文件规定了显式文档框声明的测试行为。
## 2 测试
### 2.1 条款甲
框外开头文字。
<!-- ssir:box -->
### 2.2 条款乙
框内第一段，进入显式框。
| 列1 | 列2 |
| --- | --- |
| a | b |
框内第二段。
<!-- ssir:/box -->
框外结尾文字。
### 2.3 条款丙
<!-- ssir:box style="shaded" -->
框内浅色段甲。
<!-- ssir:/box -->
框外普通段乙。
### 2.4 无框段
普通内容。
<!-- ssir:box -->
### 2.5 框内条款戊
框内段甲。
<!-- ssir:/box -->
框外段尾（父节点仍是 2.5 的内容元素）。
"""


def _all_nodes(root: dict) -> list[dict]:
    out: list[dict] = []
    for node in root.get("children", []) or []:
        out.append(node)
        out.extend(_all_nodes(node))
    return out


def _boxed(ssir: dict) -> list[tuple]:
    """收集 (单元, box, boxStyle)：(nodeType/title) 或 (CE kind/text 前缀)。"""
    found: list[tuple] = []
    for node in _all_nodes(ssir["structuralRoot"]):
        if "box" in node:
            found.append((node.get("nodeType"), str(node.get("title") or node.get("number") or "")[:20], node["box"], node.get("boxStyle")))
        for content in node.get("contentElements", []) or []:
            if "box" in content:
                text = str(content.get("textContent") or content.get("tableRef") or "")[:20]
                found.append(("CE:" + str(content.get("presentationType")), text, content["box"], content.get("boxStyle")))
    return found


class ParserBoxTests(unittest.TestCase):
    def _parse_issues(self, body: str) -> tuple[list[str], list]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t.canonical.md"
            front = CANON.split("## 1 范围")[0]
            path.write_text(front + body, encoding="utf-8")
            doc = CSMParser().read(str(path))
            return [issue.code for issue in doc.issues], [b for b in doc.blocks if b.kind == "box"]

    def test_open_close_events_parsed(self) -> None:
        body = """## 1 范围
开头。
<!-- ssir:box -->
中间。
<!-- ssir:/box -->
结尾。
"""
        codes, events = self._parse_issues(body)
        self.assertNotIn("CSM-STRUCT-006", codes)
        self.assertEqual([e.data["event"] for e in events], ["open", "close"])
        self.assertEqual(events[0].data["style"], "frame")

    def test_style_attribute_and_invalid_style(self) -> None:
        body = """## 1 范围
<!-- ssir:box style="shaded" -->
中间。
<!-- ssir:/box -->
"""
        codes, events = self._parse_issues(body)
        self.assertNotIn("CSM-STRUCT-006", codes)
        self.assertEqual(events[0].data["style"], "shaded")

    def test_indented_marker_lines_still_parse(self) -> None:
        # 手工编辑常给注释行加缩进：对 strip 后的行匹配（2026-09-08 修复）。
        body = """## 1 范围
开头段。
 <!-- ssir:box -->
中间段。
 <!-- ssir:/box -->
结尾段。
"""
        codes, events = self._parse_issues(body)
        self.assertNotIn("CSM-STRUCT-006", codes)
        self.assertEqual([e.data["event"] for e in events], ["open", "close"])
        # 标记行不得泄漏为正文段落
        leaked = [b for b in self._blocks(body) if b.kind == "paragraph" and "ssir:box" in b.text]
        self.assertEqual(leaked, [])

    def _blocks(self, body: str) -> list:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t.canonical.md"
            front = CANON.split("## 1 范围")[0]
            path.write_text(front + body, encoding="utf-8")
            return CSMParser().read(str(path)).blocks

    def test_malformed_marker_warns_instead_of_silent_leak(self) -> None:
        # 缺 --> 的残行不再静默渲染成 PDF 文本：显式告警并按普通段落保留内容。
        body = """## 1 范围
<!-- ssir:box>
残损指令行。
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t.canonical.md"
            front = CANON.split("## 1 范围")[0]
            path.write_text(front + body, encoding="utf-8")
            parsed = CSMParser().read(str(path))
        self.assertTrue(any("疑似 ssir 指令行未被识别" in issue.message for issue in parsed.issues), [i.message for i in parsed.issues])
        self.assertTrue(any(b.kind == "paragraph" and "ssir:box" in b.text for b in parsed.blocks))

    def test_dangling_close_reports_csm_struct_006(self) -> None:
        body = """## 1 范围
<!-- ssir:/box -->
没有开标记就关闭。
"""
        codes, _ = self._parse_issues(body)
        self.assertIn("CSM-STRUCT-006", codes)

    def test_nested_open_reports_csm_struct_006(self) -> None:
        body = """## 1 范围
<!-- ssir:box -->
一层。
<!-- ssir:box -->
二层嵌套（禁止）。
<!-- ssir:/box -->
一层收尾。
<!-- ssir:/box -->
"""
        codes, events = self._parse_issues(body)
        self.assertIn("CSM-STRUCT-006", codes)
        # 宽容语义：嵌套开被忽略，一层框延伸到文档尾（事件仍保留、确定性）。
        self.assertEqual([e.data["event"] for e in events], ["open", "open", "close", "close"])

    def test_unterminated_open_reports_csm_struct_006(self) -> None:
        body = """## 1 范围
<!-- ssir:box -->
一直到文档尾都没关。
"""
        codes, _ = self._parse_issues(body)
        self.assertIn("CSM-STRUCT-006", codes)


class BuilderBoxTests(unittest.TestCase):
    def test_node_and_mid_content_box_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t.canonical.md"
            path.write_text(CANON, encoding="utf-8")
            ssir = SSIRBuilder().build(CSMParser().read(str(path)))
        marks = _boxed(ssir)
        # 整节点入框：2.2 条款（含其全部正文/表格）在框 1
        self.assertTrue(any(t == "clause" and "条款乙" in title and box == 1 and style == "frame"
                            for t, title, box, style in marks), marks)
        self.assertTrue(any(t == "CE:table" and box == 1 for t, _, box, _ in marks), marks)
        # 同一条款内容中途切分：2.3 的框内浅色段 box=2/shaded，其后普通段乙在框外
        self.assertTrue(any(t == "CE:paragraph" and "浅色段" in title and box == 2 and style == "shaded"
                            for t, title, box, style in marks), marks)
        self.assertFalse(any(t == "CE:paragraph" and "普通段乙" in title for t, title, box, _ in marks), marks)
        # 框内节点的尾部内容（关标记后、无新标题前）不得继承父节点框（20001.5 引导段型）
        self.assertTrue(any(t == "clause" and "条款戊" in title and box == 3 for t, title, box, _ in marks), marks)
        self.assertTrue(any(t == "CE:paragraph" and "框内段甲" in title and box == 3 for t, title, box, _ in marks), marks)
        self.assertFalse(any(t == "CE:paragraph" and "框外段尾" in title for t, title, box, _ in marks), marks)
        # 框外节点/内容不带 box 字段
        self.assertFalse(any("条款甲" in title for t, title, box, _ in marks), marks)


class RoundTripBoxTests(unittest.TestCase):
    def test_unmarked_corpus_fixture_has_no_box_and_no_new_issues(self) -> None:
        # 无标记文档：零 box 归属、零 CSM-STRUCT-006，走旧 exampleContent 路径。
        path = ROOT / "corpus/golden/csm/Q_YYJD_001-2024.canonical.md"
        doc = CSMParser().read(str(path))
        ssir = SSIRBuilder().build(doc)
        self.assertEqual([b for b in doc.blocks if b.kind == "box"], [])
        self.assertNotIn("CSM-STRUCT-006", [issue.code for issue in doc.issues])
        self.assertFalse(any("box" in node for node in _all_nodes(ssir["structuralRoot"])))
        for node in _all_nodes(ssir["structuralRoot"]):
            for content in node.get("contentElements", []) or []:
                self.assertNotIn("box", content)


class RenderBoxSmokeTests(unittest.TestCase):
    def test_pdf_render_marked_document(self) -> None:
        import json
        import fitz  # type: ignore

        from leleby_ssir.pdf_renderer import render_pdf_file

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t.canonical.md"
            path.write_text(CANON, encoding="utf-8")
            ssir = SSIRBuilder().build(CSMParser().read(str(path)))
            ssir_path = Path(directory) / "t.ssir.json"
            ssir_path.write_text(json.dumps(ssir, ensure_ascii=False, indent=2), encoding="utf-8")
            pdf_out = Path(directory) / "out.pdf"
            report = render_pdf_file(str(ssir_path), str(pdf_out), toc_depth=None)
            self.assertTrue(pdf_out.is_file())
            # frame 框：≥1 页存在成对长横/竖线；shaded 框：≥1 页存在大浅色填充
            stroke_pages = fill_pages = 0
            pdf = fitz.open(str(pdf_out))

            def frame_rects(page) -> list[tuple[float, float, float, float]]:
                hlines, vlines = [], []
                for drawing in page.get_drawings():
                    rect = drawing["rect"]
                    if drawing.get("fill"):
                        continue
                    if rect.width >= 80 and rect.height <= 4:
                        hlines.append((rect.x0, rect.x1, (rect.y0 + rect.y1) / 2))
                    elif rect.height >= 20 and rect.width <= 4:
                        vlines.append((rect.y0, rect.y1, (rect.x0 + rect.x1) / 2))
                rects = []
                for x0, x1, ytop in hlines:
                    for x0b, x1b, ybot in hlines:
                        if ybot <= ytop:
                            continue
                        if abs(x0b - x0) > 2 or abs(x1b - x1) > 2:
                            continue
                        left = any(abs(vx - x0) < 4 and vy0 <= ytop + 1 and vy1 >= ybot - 1 for vy0, vy1, vx in vlines)
                        right = any(abs(vx - x1) < 4 and vy0 <= ytop + 1 and vy1 >= ybot - 1 for vy0, vy1, vx in vlines)
                        if left and right:
                            rects.append((x0, ytop, x1, ybot))
                return rects

            def span_points(page, needle: str) -> list[tuple[float, float]]:
                points = []
                for block in page.get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            if needle in span["text"]:
                                x0, y0, x1, y1 = span["bbox"]
                                points.append(((x0 + x1) / 2, (y0 + y1) / 2))
                return points

            inside_found = False
            tail_outside_ok = True
            try:
                for page in pdf:
                    h = v = 0
                    fills = 0
                    try:
                        drawings = page.get_drawings()
                    except Exception:
                        drawings = []
                    for drawing in drawings:
                        rect = drawing["rect"]
                        if drawing.get("fill") and rect.width >= 100 and rect.height >= 12:
                            fills += 1
                        elif rect.width >= 80 and rect.height <= 4:
                            h += 1
                        elif rect.height >= 30 and rect.width <= 4:
                            v += 1
                    if h >= 2 and v >= 2:
                        stroke_pages += 1
                    if fills:
                        fill_pages += 1
                    rects = frame_rects(page)

                    def in_any_frame(point) -> bool:
                        x, y = point
                        return any(r[0] - 5 <= x <= r[2] + 5 and r[1] - 5 <= y <= r[3] + 5 for r in rects)

                    for px, py in span_points(page, "框内段甲"):
                        if in_any_frame((px, py)):
                            inside_found = True
                    for px, py in span_points(page, "框外段尾"):
                        if in_any_frame((px, py)):
                            tail_outside_ok = False
            finally:
                pdf.close()
            self.assertGreaterEqual(stroke_pages, 1, "frame 线框缺失")
            self.assertGreaterEqual(fill_pages, 1, "shaded 浅底缺失")
            self.assertTrue(inside_found, "框内段甲应位于某框线内")
            self.assertTrue(tail_outside_ok, "框外段尾不得位于任何框线内（不得继承父节点框）")


if __name__ == "__main__":
    unittest.main()
