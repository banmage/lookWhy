"""并列版式声明与几何自动识别（ssir:columns / GEN-094，2026-09-11）。

回归夹具覆盖：
- parser：columns/column//columns 事件块、widths 属性、配对/嵌套/错位校验；
- builder：内容元素写入 sideBySideGroup/Column/Widths（手工声明）；
- csm_renderer：标记确定性重放（列优先）→ roundtrip 并列视图等价；
- pdf/docx 渲染：同一行的并列列几何（正确/不正确 同基线、x 分离）；
- 几何自动识别（_stamp_side_by_side_layout）：跨栏交错的文本+公式块成组、
  单栏不误判、多分片 page_idx 各自从 0 起不串页；
- 无标记文档零命中（既有路径不受影响）。
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

from leleby_ssir.builder import SSIRBuilder
from leleby_ssir.csm_renderer import render_csm
from leleby_ssir.parser import CSMParser
from leleby_ssir.roundtrip import compare_ssir

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import mineru_full_standard as mfs  # noqa: E402

FRONT = """---
csm-version: 1.0
document-type: standard
document-identifier: T_COL_001-2026
standard-number: T/COL 001-2026
title: 并列声明测试文档
language: zh-CN
---
# 并列声明测试文档
## 1 范围
本文件规定了并列版式声明的测试行为。
"""

CANON = FRONT + """## 9 表示
### 9.1 示例3
<!-- ssir:columns -->
正确：
<!-- ssir:formula id="f-l" -->
$$
\\rho = \\frac{m}{V}
$$
<!-- ssir:column -->
不正确：
<!-- ssir:formula id="f-r" -->
$$
\\rho = \\frac{W}{V}
$$
<!-- ssir:/columns -->
### 9.2 示例4
<!-- ssir:columns widths="3,2" -->
正确：
<!-- ssir:formula id="f-l2" -->
$$
\\dim(E) = \\dim(F)
$$
式中：
<!-- ssir:column -->
不正确：
<!-- ssir:formula id="f-r2" -->
$$
\\dim(\\text{EE}) = \\dim(\\text{FF})
$$
<!-- ssir:/columns -->
### 9.3 单栏
普通段落，不属于任何并列组。
"""


def _parse(body: str):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "t.canonical.md"
        path.write_text(body, encoding="utf-8")
        return CSMParser().read(str(path))


def _contents(ssir: dict) -> list[dict]:
    found: list[dict] = []

    def visit(node: dict) -> None:
        found.extend(node.get("contentElements", []) or [])
        for child in node.get("children", []) or []:
            visit(child)

    visit(ssir["structuralRoot"])
    return found


class ParserColumnsTests(unittest.TestCase):
    def _events(self, body: str) -> tuple[list[str], list]:
        doc = _parse(FRONT + body)
        return [issue.code for issue in doc.issues], [b for b in doc.blocks if b.kind == "columns"]

    def test_open_column_close_events(self) -> None:
        codes, events = self._events("""## 1 范围
<!-- ssir:columns -->
左列。
<!-- ssir:column -->
右列。
<!-- ssir:/columns -->
""")
        self.assertNotIn("CSM-STRUCT-008", codes)
        self.assertEqual([e.data["event"] for e in events], ["open", "column", "close"])

    def test_widths_attribute_parsed(self) -> None:
        _, events = self._events("""## 1 范围
<!-- ssir:columns widths="3,2" -->
左。
<!-- ssir:column -->
右。
<!-- ssir:/columns -->
""")
        self.assertEqual(events[0].data["widths"], [3.0, 2.0])

    def test_invalid_widths_warn_and_equal(self) -> None:
        doc = _parse(FRONT + """## 1 范围
<!-- ssir:columns widths="x,2" -->
左。
<!-- ssir:column -->
右。
<!-- ssir:/columns -->
""")
        events = [b for b in doc.blocks if b.kind == "columns"]
        self.assertIsNone(events[0].data["widths"])
        self.assertTrue(any("widths" in issue.message for issue in doc.issues), [i.message for i in doc.issues])

    def test_dangling_column_and_close_report_008(self) -> None:
        codes, _ = self._events("""## 1 范围
<!-- ssir:column -->
没有开标记。
<!-- ssir:/columns -->
""")
        self.assertIn("CSM-STRUCT-008", codes)

    def test_nested_open_reports_006(self) -> None:
        codes, events = self._events("""## 1 范围
<!-- ssir:columns -->
一层。
<!-- ssir:columns -->
嵌套（禁止）。
<!-- ssir:/columns -->
收尾。
<!-- ssir:/columns -->
""")
        self.assertIn("CSM-STRUCT-008", codes)
        self.assertEqual([e.data["event"] for e in events], ["open", "open", "close", "close"])

    def test_unterminated_open_reports_006(self) -> None:
        codes, _ = self._events("""## 1 范围
<!-- ssir:columns -->
一直没关。
""")
        self.assertIn("CSM-STRUCT-008", codes)

    def test_markers_do_not_leak_as_paragraphs(self) -> None:
        doc = _parse(CANON)
        leaked = [b for b in doc.blocks if b.kind == "paragraph" and "ssir:column" in b.text]
        self.assertEqual(leaked, [])


class BuilderColumnsTests(unittest.TestCase):
    def test_content_elements_stamped_with_column_and_widths(self) -> None:
        ssir = SSIRBuilder().build(_parse(CANON))
        marks = [
            (c.get("sideBySideGroup"), c.get("sideBySideColumn"), c.get("sideBySideWidths"),
             c.get("presentationType"), c.get("textContent") or c.get("formulaRef"))
            for c in _contents(ssir) if c.get("sideBySideGroup")
        ]
        # 示例3：4 个元素分两列（正确/公式 | 不正确/公式），无 widths
        example3 = [m for m in marks if m[0] == "columns-1"]
        self.assertEqual({m[1] for m in example3}, {0, 1})
        self.assertEqual([m[1] for m in example3], [0, 0, 1, 1])
        self.assertTrue(all(m[2] is None for m in example3))
        # 示例4：6+2 个元素，widths 透传 [3, 2]
        example4 = [m for m in marks if m[0] == "columns-2"]
        self.assertEqual({m[1] for m in example4}, {0, 1})
        self.assertTrue(all(m[2] == [3.0, 2.0] for m in example4))
        # 组外内容不带并列字段
        plain = [c for c in _contents(ssir) if c.get("textContent") == "普通段落，不属于任何并列组。"]
        self.assertEqual(len(plain), 1)
        self.assertNotIn("sideBySideGroup", plain[0])


class RoundTripColumnsTests(unittest.TestCase):
    def test_markers_replayed_and_roundtrip_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "t.canonical.md"
            path.write_text(CANON, encoding="utf-8")
            ssir = SSIRBuilder().build(CSMParser().read(str(path)))
            rendered = render_csm(ssir)
            self.assertIn("<!-- ssir:columns -->", rendered)
            self.assertIn("<!-- ssir:column -->", rendered)
            self.assertIn("<!-- ssir:/columns -->", rendered)
            self.assertIn('<!-- ssir:columns widths="3,2" -->', rendered)
            render_path = Path(directory) / "render.md"
            render_path.write_text(rendered, encoding="utf-8")
            verify = SSIRBuilder().build(CSMParser().read(str(render_path)))
            report = compare_ssir(ssir, verify, input_file=str(path), render_md_file=str(render_path))
            self.assertTrue(report.passed, report)

    def test_roundtrip_view_is_column_aware(self) -> None:
        # 抽取顺序按行跨栏交错（如 MinerU 输出）与 canonical 列优先顺序语义等价：
        # 只要列归属与列内顺序一致，roundtrip 视图不得因跨列交错而判异。
        ssir = SSIRBuilder().build(_parse(CANON))
        node = next(n for n in _walk_nodes(ssir["structuralRoot"])
                    if any(c.get("sideBySideGroup") == "columns-2" for c in n.get("contentElements", []) or []))
        by_column: dict[int, list[dict]] = {}
        for content in node["contentElements"]:
            by_column.setdefault(int(content.get("sideBySideColumn", 0)), []).append(content)
        interleaved: list[dict] = []
        for index in range(max(len(items) for items in by_column.values())):
            for column in sorted(by_column):
                if index < len(by_column[column]):
                    interleaved.append(by_column[column][index])
        from leleby_ssir.roundtrip import _content_sequence_view
        original = _content_sequence_view(node["contentElements"], _registries(ssir))
        shuffled = _content_sequence_view(interleaved, _registries(ssir))
        self.assertEqual(original, shuffled)


def _walk_nodes(root: dict):
    for child in root.get("children", []) or []:
        yield child
        yield from _walk_nodes(child)


def _registries(ssir: dict) -> dict:
    return {
        kind: {item["id"]: item for item in ssir.get(kind, [])}
        for kind in ("tables", "figures", "formulas", "unknownContents")
    }


class RenderColumnsTests(unittest.TestCase):
    def _ssir_files(self, directory: Path) -> tuple[Path, Path]:
        path = directory / "t.canonical.md"
        path.write_text(CANON, encoding="utf-8")
        ssir = SSIRBuilder().build(CSMParser().read(str(path)))
        ssir_path = directory / "t.ssir.json"
        ssir_path.write_text(json.dumps(ssir, ensure_ascii=False, indent=2), encoding="utf-8")
        return path, ssir_path

    def test_pdf_renders_correct_incorrect_on_one_row(self) -> None:
        import pymupdf

        from leleby_ssir.pdf_renderer import render_pdf_file

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            _, ssir_path = self._ssir_files(directory)
            pdf_out = directory / "out.pdf"
            render_pdf_file(str(ssir_path), str(pdf_out), toc_depth=None)
            document = pymupdf.open(str(pdf_out))
            rows = 0
            for page in document:
                labels = [w for w in page.get_text("words") if w[4] in ("正确：", "不正确：")]
                by_y: dict[float, list[tuple[float, str]]] = {}
                for word in labels:
                    by_y.setdefault(round(word[1], 1), []).append((round(word[0], 1), word[4]))
                for entries in by_y.values():
                    if {entry[1] for entry in entries} == {"正确：", "不正确："}:
                        rows += 1
            # 示例3、示例4 两个"正确/不正确"对照行
            self.assertGreaterEqual(rows, 2)

    def test_docx_renders_one_borderless_table_per_group(self) -> None:
        from docx import Document

        from leleby_ssir.docx_renderer import render_docx_file

        def walk_tables(tables):
            for table in tables:
                yield table
                for row in table.rows:
                    for cell in row.cells:
                        yield from walk_tables(cell.tables)

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            _, ssir_path = self._ssir_files(directory)
            docx_out = directory / "out.docx"
            render_docx_file(str(ssir_path), str(docx_out), toc_depth=None)
            document = Document(str(docx_out))
            # 并列组可能嵌在 ssir:box 外框单元格内，需递归查找。
            tables = [t for t in walk_tables(document.tables)
                      if len(t.rows) == 1 and len(t.columns) == 2 and "正确：" in t.cell(0, 0).text]
            self.assertEqual(len(tables), 2)
            for table in tables:
                self.assertIn("不正确：", table.cell(0, 1).text)


def _write_middle(path: Path, pages: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pdf_info": pages}, ensure_ascii=False), encoding="utf-8")


def _text_block(text: str, bbox: list[float]) -> dict:
    return {
        "type": "text",
        "bbox": bbox,
        "lines": [{"bbox": bbox, "spans": [{"bbox": bbox, "type": "text", "content": text}]}],
    }


def _equation_block(asset: str, bbox: list[float]) -> dict:
    return {
        "type": "interline_equation",
        "bbox": bbox,
        "lines": [{"bbox": bbox, "spans": [{"bbox": bbox, "type": "interline_equation",
                                            "content": "x=1", "image_path": asset}]}],
    }


def _inline_equation_block(formula: str, text: str, bbox: list[float]) -> dict:
    """变量解释行：行内公式 span + 文本 span（MinerU 的实际层级）。"""
    return {
        "type": "text",
        "bbox": bbox,
        "lines": [{"bbox": bbox, "spans": [
            {"bbox": [bbox[0], bbox[1], bbox[0] + 8, bbox[3]], "type": "inline_equation", "content": formula},
            {"bbox": [bbox[0] + 8, bbox[1], bbox[2], bbox[3]], "type": "text", "content": text},
        ]}],
    }


def _latex_equation_block(latex: str, bbox: list[float]) -> dict:
    """云端路线的公式块：只有 LaTeX，没有裁剪图资产（image_path）。"""
    return {
        "type": "interline_equation",
        "bbox": bbox,
        "lines": [{"bbox": bbox, "spans": [{"bbox": bbox, "type": "interline_equation", "content": latex}]}],
    }


def _latex_columns_ssir() -> dict:
    """公式节点只有 latex（无 assetRef）的并列夹具——云端路线形态。"""
    data = _columns_ssir()
    data["formulas"] = [
        {"id": "ssir:T/formula/l", "latex": r"v = 3.6 \times \frac{l}{t}"},
        {"id": "ssir:T/formula/r", "latex": r"\rho = \frac{m}{V}"},
    ]
    return data


def _duplicate_column_ssir() -> dict:
    """示例5 型：两列各有重复「式中：」与同形变量解释行（含行内公式）。"""
    def paragraph(identifier: str, order: int, text: str) -> dict:
        return {"id": identifier, "presentationType": "paragraph", "sortOrder": order,
                "textContent": text, "parentNodeId": "ssir:T/block-1"}

    return {
        "structuralRoot": {
            "id": "ssir:T/document", "nodeType": "document", "sortOrder": 0,
            "children": [{
                "id": "ssir:T/block-1", "nodeType": "documentBlock", "sortOrder": 0,
                "contentElements": [
                    paragraph("ssir:T/content/0", 0, "正确："),
                    {"id": "ssir:T/content/1", "presentationType": "formula", "sortOrder": 1,
                     "formulaRef": "ssir:T/formula/l", "parentNodeId": "ssir:T/block-1"},
                    paragraph("ssir:T/content/2", 2, "不正确："),
                    {"id": "ssir:T/content/3", "presentationType": "formula", "sortOrder": 3,
                     "formulaRef": "ssir:T/formula/r", "parentNodeId": "ssir:T/block-1"},
                    paragraph("ssir:T/content/4", 4, "式中："),
                    paragraph("ssir:T/content/5", 5, "式中："),
                    paragraph("ssir:T/content/6", 6, "$x$——甲；"),
                    paragraph("ssir:T/content/7", 7, "$x$——甲；"),
                ],
            }],
        },
        "figures": [],
        "formulas": [
            {"id": "ssir:T/formula/l", "assetRef": "assets/images/left.jpg"},
            {"id": "ssir:T/formula/r", "assetRef": "assets/images/right.jpg"},
        ],
    }


_DUPLICATE_PAGES = [{
    "page_idx": 0,
    "preproc_blocks": [
        _text_block("正确：", [78, 100, 105, 112]),
        _equation_block("left.jpg", [159, 120, 192, 140]),
        _text_block("不正确：", [308, 100, 344, 112]),
        _equation_block("right.jpg", [380, 118, 434, 142]),
        _text_block("式中：", [96, 150, 123, 162]),
        _text_block("式中：", [327, 150, 353, 162]),
        # 左右两行的 y 差 1pt（实际 MinerU 版式），行聚类容差须把二者并入同一行
        _inline_equation_block("x", "——甲；", [96, 166, 207, 178]),
        _inline_equation_block("x", "———甲；", [326, 165, 439, 178]),
    ],
}]


def _columns_ssir() -> dict:
    def paragraph(identifier: str, order: int, text: str) -> dict:
        return {"id": identifier, "presentationType": "paragraph", "sortOrder": order,
                "textContent": text, "parentNodeId": "ssir:T/block-1"}

    def formula(identifier: str, order: int, ref: str) -> dict:
        return {"id": identifier, "presentationType": "formula", "sortOrder": order,
                "formulaRef": ref, "parentNodeId": "ssir:T/block-1"}

    return {
        "structuralRoot": {
            "id": "ssir:T/document", "nodeType": "document", "sortOrder": 0,
            "children": [{
                "id": "ssir:T/block-1", "nodeType": "documentBlock", "sortOrder": 0,
                "contentElements": [
                    paragraph("ssir:T/content/1", 0, "正确："),
                    formula("ssir:T/content/2", 1, "ssir:T/formula/l"),
                    paragraph("ssir:T/content/3", 2, "不正确："),
                    formula("ssir:T/content/4", 3, "ssir:T/formula/r"),
                ],
            }],
        },
        "figures": [],
        "formulas": [
            {"id": "ssir:T/formula/l", "assetRef": "assets/images/left.jpg"},
            {"id": "ssir:T/formula/r", "assetRef": "assets/images/right.jpg"},
        ],
    }


class GeometryDuplicateTextTests(unittest.TestCase):
    """示例5 型：重复标签 + 行内公式变量解释行（MinerU 只把变量放在 inline span）。"""

    def _run(self, ssir: dict, pages: list[dict], *, runs: int = 1) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parts = root / "parts"
            _write_middle(parts / "pages-037-054" / "std" / "auto" / "std_middle.json", pages)
            ssir_path = root / "t.ssir.json"
            ssir_path.write_text(json.dumps(ssir, ensure_ascii=False), encoding="utf-8")
            for _ in range(runs):
                mfs._stamp_side_by_side_layout(ssir_path, parts)
            return json.loads(ssir_path.read_text(encoding="utf-8"))

    def test_duplicate_labels_and_inline_formula_rows_all_grouped(self) -> None:
        # 两列各有「式中：」与同形变量解释行：同文本按行序对应 sortOrder 序的候选，
        # 行内公式并入块文本、破折号族归一后仍能精确匹配 → 组内无空洞、不整组回滚。
        stamped = self._run(_duplicate_column_ssir(), _DUPLICATE_PAGES)
        contents = stamped["structuralRoot"]["children"][0]["contentElements"]
        self.assertEqual({c.get("sideBySideGroup") for c in contents}, {"p037-c00"})
        self.assertEqual([c.get("sideBySideColumn") for c in contents], [0, 0, 1, 1, 0, 1, 0, 1])

    def test_rerun_is_idempotent_and_never_reuses_group_id(self) -> None:
        # 重复运行（半程续跑/手工重跑）不得复用已存在的组 id，也不得把两组并成一组。
        once = self._run(_duplicate_column_ssir(), _DUPLICATE_PAGES, runs=1)
        twice = self._run(_duplicate_column_ssir(), _DUPLICATE_PAGES, runs=2)
        first = once["structuralRoot"]["children"][0]["contentElements"]
        second = twice["structuralRoot"]["children"][0]["contentElements"]
        self.assertEqual(
            [(c.get("sideBySideGroup"), c.get("sideBySideColumn")) for c in first],
            [(c.get("sideBySideGroup"), c.get("sideBySideColumn")) for c in second],
        )


class GeometryStampTests(unittest.TestCase):
    def _run(self, pages_by_part: dict[str, list[dict]]) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parts = root / "parts"
            for part, pages in pages_by_part.items():
                _write_middle(parts / part / "std" / "auto" / "std_middle.json", pages)
            ssir_path = root / "t.ssir.json"
            ssir_path.write_text(json.dumps(_columns_ssir(), ensure_ascii=False), encoding="utf-8")
            mfs._stamp_side_by_side_layout(ssir_path, parts)
            return json.loads(ssir_path.read_text(encoding="utf-8"))

    def test_two_equation_columns_stamped(self) -> None:
        pages = [{
            "page_idx": 0,
            "preproc_blocks": [
                _text_block("正确：", [78, 457, 105, 469]),
                _equation_block("left.jpg", [159, 473, 192, 493]),
                _text_block("不正确：", [308, 457, 344, 469]),
                _equation_block("right.jpg", [380, 471, 434, 495]),
            ],
        }]
        stamped = self._run({"pages-037-054": pages})
        contents = stamped["structuralRoot"]["children"][0]["contentElements"]
        groups = {c.get("sideBySideGroup") for c in contents}
        self.assertEqual(groups, {"p037-c00"})
        self.assertEqual([c.get("sideBySideColumn") for c in contents], [0, 0, 1, 1])

    def test_single_column_never_grouped(self) -> None:
        pages = [{
            "page_idx": 0,
            "preproc_blocks": [
                _text_block("正确：", [78, 457, 105, 469]),
                _equation_block("left.jpg", [80, 473, 120, 493]),
                _text_block("不正确：", [78, 517, 105, 529]),
                _equation_block("right.jpg", [80, 533, 120, 553]),
            ],
        }]
        stamped = self._run({"pages-001-018": pages})
        contents = stamped["structuralRoot"]["children"][0]["contentElements"]
        self.assertFalse(any(c.get("sideBySideGroup") for c in contents))

    def test_part_page_index_collision_does_not_cross_group(self) -> None:
        # 两个分片的 page_idx 都是 0，但绝对页不同（1 与 19）：各自的单列锚点不得
        # 跨分片凑成假并列（旧实现按相对 page_idx 聚合，会误组）。
        left_only = [
            _text_block("正确：", [78, 457, 105, 469]),
            _equation_block("left.jpg", [159, 473, 192, 493]),
        ]
        right_only = [
            _text_block("不正确：", [308, 457, 344, 469]),
            _equation_block("right.jpg", [380, 471, 434, 495]),
        ]
        stamped = self._run({"pages-001-018": [{"page_idx": 0, "preproc_blocks": left_only}],
                             "pages-019-036": [{"page_idx": 0, "preproc_blocks": right_only}]})
        contents = stamped["structuralRoot"]["children"][0]["contentElements"]
        self.assertFalse(any(c.get("sideBySideGroup") for c in contents))

    def test_whole_document_middle_json_is_a_geometry_source(self) -> None:
        """raw 起点（云端抽取产物）用整份 middle.json 作几何来源，不依赖 parts/ 分片目录。"""
        pages = [{
            "page_idx": 36,  # 0 基绝对页号：第 37 页
            "preproc_blocks": [
                _text_block("正确：", [78, 457, 105, 469]),
                _equation_block("left.jpg", [159, 473, 192, 493]),
                _text_block("不正确：", [308, 457, 344, 469]),
                _equation_block("right.jpg", [380, 471, 434, 495]),
            ],
        }]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            middle = root / "std_middle.json"
            _write_middle(middle, pages)
            ssir_path = root / "t.ssir.json"
            ssir_path.write_text(json.dumps(_columns_ssir(), ensure_ascii=False), encoding="utf-8")
            # 没有 parts/ 目录，只有整份 middle.json
            mfs._stamp_side_by_side_layout(ssir_path, root / "parts", middle_json=middle)
            stamped = json.loads(ssir_path.read_text(encoding="utf-8"))
        contents = stamped["structuralRoot"]["children"][0]["contentElements"]
        self.assertEqual({c.get("sideBySideGroup") for c in contents}, {"p037-c00"})

    def test_no_geometry_source_is_a_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ssir_path = root / "t.ssir.json"
            ssir_path.write_text(json.dumps(_columns_ssir(), ensure_ascii=False), encoding="utf-8")
            mfs._stamp_side_by_side_layout(ssir_path, root / "parts")
            stamped = json.loads(ssir_path.read_text(encoding="utf-8"))
        contents = stamped["structuralRoot"]["children"][0]["contentElements"]
        self.assertFalse(any(c.get("sideBySideGroup") for c in contents))

    def test_latex_only_geometry_matches_latex_only_formulas(self) -> None:
        """云端路线：几何与 SSIR 公式都只有 LaTeX（没有裁剪图资产）时仍能成组。"""
        pages = [{
            "page_idx": 36,
            "preproc_blocks": [
                _text_block("正确：", [78, 457, 105, 469]),
                _latex_equation_block(r"v = 3.6 \times \frac{l}{t}", [159, 473, 192, 493]),
                _text_block("不正确：", [308, 457, 344, 469]),
                _latex_equation_block(r"\rho = \frac{m}{V}", [380, 471, 434, 495]),
            ],
        }]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            middle = root / "std_middle.json"
            _write_middle(middle, pages)
            ssir_path = root / "t.ssir.json"
            ssir_path.write_text(json.dumps(_latex_columns_ssir(), ensure_ascii=False), encoding="utf-8")
            mfs._stamp_side_by_side_layout(ssir_path, root / "parts", middle_json=middle)
            stamped = json.loads(ssir_path.read_text(encoding="utf-8"))
        contents = stamped["structuralRoot"]["children"][0]["contentElements"]
        self.assertEqual({c.get("sideBySideGroup") for c in contents}, {"p037-c00"})
        self.assertEqual([c.get("sideBySideColumn") for c in contents], [0, 0, 1, 1])

    def test_latex_key_ignores_spacing_differences(self) -> None:
        """两条路线的同一公式只在空格/分词上不同，归一后仍匹配。"""
        pages = [{
            "page_idx": 36,
            "preproc_blocks": [
                _text_block("正确：", [78, 457, 105, 469]),
                _latex_equation_block(r"v=3.6\times \frac {l}{t}", [159, 473, 192, 493]),
                _text_block("不正确：", [308, 457, 344, 469]),
                _latex_equation_block(r"\rho =\frac{m}{V}", [380, 471, 434, 495]),
            ],
        }]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            middle = root / "std_middle.json"
            _write_middle(middle, pages)
            ssir_path = root / "t.ssir.json"
            ssir_path.write_text(json.dumps(_latex_columns_ssir(), ensure_ascii=False), encoding="utf-8")
            mfs._stamp_side_by_side_layout(ssir_path, root / "parts", middle_json=middle)
            stamped = json.loads(ssir_path.read_text(encoding="utf-8"))
        contents = stamped["structuralRoot"]["children"][0]["contentElements"]
        self.assertEqual({c.get("sideBySideGroup") for c in contents}, {"p037-c00"})

    def test_asset_matching_still_wins_when_both_forms_are_present(self) -> None:
        """资产与 LaTeX 都在场时按资产匹配（本地路线行为不变）。

        两列公式的 LaTeX 键相同（``x=1``，只靠 LaTeX 会去重成单列），资产名不同——
        能成组即证明匹配仍按资产优先。
        """
        pages = [{
            "page_idx": 36,
            "preproc_blocks": [
                _text_block("正确：", [78, 457, 105, 469]),
                _equation_block("left.jpg", [159, 473, 192, 493]),
                _text_block("不正确：", [308, 457, 344, 469]),
                _equation_block("right.jpg", [380, 471, 434, 495]),
            ],
        }]
        data = _latex_columns_ssir()
        data["formulas"] = [
            {"id": "ssir:T/formula/l", "assetRef": "assets/images/left.jpg", "latex": "x=1"},
            {"id": "ssir:T/formula/r", "assetRef": "assets/images/right.jpg", "latex": "x=1"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            middle = root / "std_middle.json"
            _write_middle(middle, pages)
            ssir_path = root / "t.ssir.json"
            ssir_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            mfs._stamp_side_by_side_layout(ssir_path, root / "parts", middle_json=middle)
            stamped = json.loads(ssir_path.read_text(encoding="utf-8"))
        contents = stamped["structuralRoot"]["children"][0]["contentElements"]
        self.assertEqual({c.get("sideBySideGroup") for c in contents}, {"p037-c00"})

    def test_manual_declaration_is_not_overwritten(self) -> None:
        pages = [{
            "page_idx": 0,
            "preproc_blocks": [
                _text_block("正确：", [78, 457, 105, 469]),
                _equation_block("left.jpg", [159, 473, 192, 493]),
                _text_block("不正确：", [308, 457, 344, 469]),
                _equation_block("right.jpg", [380, 471, 434, 495]),
            ],
        }]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parts = root / "parts"
            _write_middle(parts / "pages-037-054" / "std" / "auto" / "std_middle.json", pages)
            data = _columns_ssir()
            for content in data["structuralRoot"]["children"][0]["contentElements"]:
                content["sideBySideGroup"] = "columns-1"
                content["sideBySideColumn"] = 0 if content["sortOrder"] < 2 else 1
            ssir_path = root / "t.ssir.json"
            ssir_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            mfs._stamp_side_by_side_layout(ssir_path, parts)
            stamped = json.loads(ssir_path.read_text(encoding="utf-8"))
        groups = {c.get("sideBySideGroup") for c in stamped["structuralRoot"]["children"][0]["contentElements"]}
        self.assertEqual(groups, {"columns-1"})


def _identical_latex_column_ssir() -> dict:
    """示例4 型：右列「或」前后两条公式排版相同 → 共享同一 LaTeX 键、两个 SSIR 节点。"""
    def paragraph(identifier: str, order: int, text: str) -> dict:
        return {"id": identifier, "presentationType": "paragraph", "sortOrder": order,
                "textContent": text, "parentNodeId": "ssir:T/block-1"}

    def formula(identifier: str, order: int, ref: str) -> dict:
        return {"id": identifier, "presentationType": "formula", "sortOrder": order,
                "formulaRef": ref, "parentNodeId": "ssir:T/block-1"}

    return {
        "structuralRoot": {
            "id": "ssir:T/document", "nodeType": "document", "sortOrder": 0,
            "children": [{
                "id": "ssir:T/block-1", "nodeType": "documentBlock", "sortOrder": 0,
                "contentElements": [
                    paragraph("ssir:T/content/0", 0, "正确："),
                    formula("ssir:T/content/1", 1, "ssir:T/formula/l"),
                    paragraph("ssir:T/content/2", 2, "不正确："),
                    formula("ssir:T/content/3", 3, "ssir:T/formula/r1"),
                    paragraph("ssir:T/content/4", 4, "或"),
                    formula("ssir:T/content/5", 5, "ssir:T/formula/r2"),
                ],
            }],
        },
        "figures": [],
        "formulas": [
            {"id": "ssir:T/formula/l", "latex": r"\dim (E) = \dim (F) \times \dim (l)"},
            {"id": "ssir:T/formula/r1", "latex": r"\dim (\text { 能量 }) = \dim (\text { 力 }) \times \dim (\text { 长度 })"},
            {"id": "ssir:T/formula/r2", "latex": r"\dim (\text { 能量 }) = \dim (\text { 力 }) \times \dim (\text { 长度 })"},
        ],
    }


def _inline_latex_spelling_ssir() -> dict:
    """示例5 型：SSIR 变量解释行保留 LaTeX 拼写（``\\mathrm{ME}``），MinerU span 是朴素拼写。"""
    def paragraph(identifier: str, order: int, text: str) -> dict:
        return {"id": identifier, "presentationType": "paragraph", "sortOrder": order,
                "textContent": text, "parentNodeId": "ssir:T/block-1"}

    return {
        "structuralRoot": {
            "id": "ssir:T/document", "nodeType": "document", "sortOrder": 0,
            "children": [{
                "id": "ssir:T/block-1", "nodeType": "documentBlock", "sortOrder": 0,
                "contentElements": [
                    paragraph("ssir:T/content/0", 0, "正确："),
                    {"id": "ssir:T/content/1", "presentationType": "formula", "sortOrder": 1,
                     "formulaRef": "ssir:T/formula/l", "parentNodeId": "ssir:T/block-1"},
                    paragraph("ssir:T/content/2", 2, "不正确："),
                    {"id": "ssir:T/content/3", "presentationType": "formula", "sortOrder": 3,
                     "formulaRef": "ssir:T/formula/r", "parentNodeId": "ssir:T/block-1"},
                    paragraph("ssir:T/content/4", 4, "式中："),
                    paragraph("ssir:T/content/5", 5, r"$S _ { \mathrm { M E } , i }$ ———系统i的残差均方；"),
                    paragraph("ssir:T/content/6", 6, r"$M S E _ { i }$——系统 i 的残差均方；"),
                ],
            }],
        },
        "figures": [],
        "formulas": [
            {"id": "ssir:T/formula/l", "assetRef": "assets/images/left.jpg"},
            {"id": "ssir:T/formula/r", "assetRef": "assets/images/right.jpg"},
        ],
    }


def _half_width_punctuation_ssir() -> dict:
    """9.9.3.3 示例3 型：MinerU 几何块把全角逗号写成半角（「在数学公式中,使用」）。"""
    def paragraph(identifier: str, order: int, text: str) -> dict:
        return {"id": identifier, "presentationType": "paragraph", "sortOrder": order,
                "textContent": text, "parentNodeId": "ssir:T/block-1"}

    def formula(identifier: str, order: int, ref: str) -> dict:
        return {"id": identifier, "presentationType": "formula", "sortOrder": order,
                "formulaRef": ref, "parentNodeId": "ssir:T/block-1"}

    return {
        "structuralRoot": {
            "id": "ssir:T/document", "nodeType": "document", "sortOrder": 0,
            "children": [{
                "id": "ssir:T/block-1", "nodeType": "documentBlock", "sortOrder": 0,
                "contentElements": [
                    paragraph("ssir:T/content/0", 0, "在数学公式中，使用"),
                    formula("ssir:T/content/1", 1, "ssir:T/formula/l"),
                    paragraph("ssir:T/content/2", 2, "而不使用"),
                    formula("ssir:T/content/3", 3, "ssir:T/formula/r"),
                ],
            }],
        },
        "figures": [],
        "formulas": [
            {"id": "ssir:T/formula/l", "assetRef": "assets/images/left.jpg"},
            {"id": "ssir:T/formula/r", "assetRef": "assets/images/right.jpg"},
        ],
    }


class MatchFoldTests(unittest.TestCase):
    """并列版式匹配归一（``pipeline._fold_match_text``，GEN-095）。只用于匹配，不改数据。"""

    def test_fold_rules(self) -> None:
        from leleby_ssir.pipeline import _fold_match_text as fold

        # 全/半角标点、空白、行内公式定界符、破折号族
        self.assertEqual(fold("在数学公式中，使用"), "在数学公式中,使用")
        self.assertEqual(fold("t ——时间间隔。"), "t—时间间隔。")
        self.assertEqual(fold("t———时间间隔。"), fold("t ——时间间隔。"))
        # 行内 LaTeX 字体命令脱壳（MinerU 侧是朴素拼写）
        self.assertEqual(
            fold(r"$S _ { \mathrm { M E } , i }$ ———系统i的残差均方；"),
            "S_{ME,i}—系统i的残差均方;",
        )
        # 嵌套命令循环脱壳
        self.assertEqual(fold(r"\mathrm{\text{ME}}"), "ME")
        # 不同变量不得因脱壳而混同
        self.assertNotEqual(fold(r"$S_{\mathrm{ME},i}$——甲；"), fold(r"$S_{\mathrm{MR},i}$——甲；"))
        self.assertEqual(fold(""), "")


class GeometryMatchingKeyTests(unittest.TestCase):
    """几何打标的三类匹配键缺陷（GB/T 1.1-2020 9.9.3.1 示例4/5、9.9.3.3 示例3）：

    ① 同一 LaTeX 键对应多个 SSIR 节点时，候选必须逐个消费——否则第二个几何块拿不到
       节点，组内 sortOrder 出现空洞 → 整组回滚；
    ② SSIR 的变量解释行保留 LaTeX 拼写（``$S_{\\mathrm{ME},i}$``），MinerU 行内 span 是
       朴素拼写（``S_{ME,i}``）：归一须脱壳字体命令；
    ③ MinerU 几何块把全角标点写成半角：归一须折叠标点宽度。
    """

    def _run(self, ssir: dict, pages: list[dict], *, part: str = "pages-037-054") -> dict:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            parts = root / "parts"
            _write_middle(parts / part / "std" / "auto" / "std_middle.json", pages)
            ssir_path = root / "t.ssir.json"
            ssir_path.write_text(json.dumps(ssir, ensure_ascii=False), encoding="utf-8")
            mfs._stamp_side_by_side_layout(ssir_path, parts)
            return json.loads(ssir_path.read_text(encoding="utf-8"))

    def test_identical_latex_formulas_consume_both_nodes(self) -> None:
        # 右列「或」前后两条同形公式只有「节点」不同（LaTeX 键相同）：两个几何块各占一个
        # 节点才算匹配成功；一对一映射会让第二块无节点可用 → 缺 sortOrder 5 → 整组回滚。
        pages = [{
            "page_idx": 0,
            "preproc_blocks": [
                _text_block("正确：", [79, 540, 104, 552]),
                _latex_equation_block(r"\dim (E) = \dim (F) \times \dim (l)", [95, 555, 211, 566]),
                _text_block("不正确：", [308, 540, 344, 552]),
                _latex_equation_block(r"\dim (\text { 能量 }) = \dim (\text { 力 }) \times \dim (\text { 长度 })",
                                      [332, 554, 481, 567]),
                _text_block("或", [309, 569, 321, 581]),
                _latex_equation_block(r"\dim (\text { 能量 }) = \dim (\text { 力 }) \times \dim (\text { 长度 })",
                                      [334, 582, 480, 596]),
            ],
        }]
        stamped = self._run(_identical_latex_column_ssir(), pages)
        contents = stamped["structuralRoot"]["children"][0]["contentElements"]
        self.assertEqual({c.get("sideBySideGroup") for c in contents}, {"p037-c00"})
        self.assertEqual([c.get("sideBySideColumn") for c in contents], [0, 0, 1, 1, 1, 1])

    def test_inline_latex_spelling_still_matches(self) -> None:
        # 变量解释行：SSIR「$S _ { \mathrm { M E } , i }$ ———系统i…」对 MinerU 行内 span
        # 「S_{ME,i}」+ 文本 span「  ——系统 i …」：脱壳 + 破折号归一后仍须命中，
        # 否则该节点缺失（sortOrder 5）→ 整组回滚。右列变量行只有一处，普通形态。
        ssir = _inline_latex_spelling_ssir()
        pages = [{
            "page_idx": 0,
            "preproc_blocks": [
                _text_block("正确：", [79, 666, 104, 677]),
                _equation_block("left.jpg", [147, 682, 203, 706]),
                _text_block("不正确：", [308, 666, 344, 678]),
                _equation_block("right.jpg", [376, 682, 436, 705]),
                _inline_equation_block("S_{ME,i}", "  ——系统i 的残差均方；", [96, 723, 207, 735]),
                _inline_equation_block("MSE_{i}", "——系统 i 的残差均方；", [326, 723, 439, 735]),
            ],
        }]
        # 「式中：」在 SSIR 里只有一条，几何侧没有对应块 —— 但空缺落在中间会触发回滚，
        # 故此处把「式中：」放进几何（真实版面左列有该行）。
        pages[0]["preproc_blocks"].insert(4, _text_block("式中：", [96, 708, 123, 720]))
        stamped = self._run(ssir, pages)
        contents = stamped["structuralRoot"]["children"][0]["contentElements"]
        self.assertEqual({c.get("sideBySideGroup") for c in contents}, {"p037-c00"})
        self.assertEqual(len(contents), 7)

    def test_half_width_punctuation_still_matches(self) -> None:
        # 几何坐标取自源页（9.9.3.3 示例3）：左列标题 x85–167、公式 x111–257，
        # 右列「而不使用」x316–357、公式 x350–481；几何侧标题是全角→半角逗号变体。
        pages = [{
            "page_idx": 0,
            "preproc_blocks": [
                _text_block("在数学公式中,使用", [85, 218, 167, 230]),
                _equation_block("left.jpg", [111, 232, 257, 255]),
                _text_block("而不使用", [316, 218, 357, 230]),
                _equation_block("right.jpg", [350, 232, 481, 275]),
            ],
        }]
        stamped = self._run(_half_width_punctuation_ssir(), pages)
        contents = stamped["structuralRoot"]["children"][0]["contentElements"]
        self.assertEqual({c.get("sideBySideGroup") for c in contents}, {"p037-c00"})
        self.assertEqual([c.get("sideBySideColumn") for c in contents], [0, 0, 1, 1])

    def test_fold_does_not_over_match_near_miss_variable(self) -> None:
        # 反例（防归一过度）：SSIR 的 ME 变量行不得被 MinerU 的 MR 行匹配。空缺落在组中
        # （sortOrder 2）→ 整组回滚、不留半组。
        ssir = _inline_latex_spelling_ssir()
        pages = [{
            "page_idx": 0,
            "preproc_blocks": [
                _text_block("正确：", [79, 666, 104, 677]),
                _equation_block("left.jpg", [147, 682, 203, 706]),
                _inline_equation_block("S_{MR,i}", "  ——系统i 的残差均方；", [96, 700, 207, 712]),
                _text_block("不正确：", [308, 666, 344, 678]),
                _equation_block("right.jpg", [376, 682, 436, 705]),
                _text_block("式中：", [96, 720, 123, 732]),
                _inline_equation_block("MSE_{i}", "——系统 i 的残差均方；", [326, 723, 439, 735]),
            ],
        }]
        stamped = self._run(ssir, pages)
        contents = stamped["structuralRoot"]["children"][0]["contentElements"]
        self.assertFalse(any(c.get("sideBySideGroup") for c in contents))


class LegacyUntouchedTests(unittest.TestCase):
    def test_unmarked_corpus_fixture_has_no_group(self) -> None:
        path = ROOT / "corpus/golden/csm/Q_YYJD_001-2024.canonical.md"
        ssir = SSIRBuilder().build(CSMParser().read(str(path)))
        self.assertFalse(any("sideBySideGroup" in c for c in _contents(ssir)))


if __name__ == "__main__":
    unittest.main()
