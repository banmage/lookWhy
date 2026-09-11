from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from mineru_full_standard import (  # noqa: E402
    _cluster_visual_lines,
    _recover_table_note_markers,
)

# 表注锚点上标字母回收（CSM-OCR-015，2026-09-06）：MinerU OCR 丢表头/单元格里跟的
# 上标小写字母、只留表注定义行（GB_T_20001.10-2014 表1 型），从源 PDF 文本层几何
# 补回单元格尾部标记。夹具必须用 pymupdf 内置 CJK 字体造真实中文文本层（AGENTS §2）。

_HEADER = "| 要素类型 | 要素的编排 | 要素所允许的表述形式 |"
_NOTE_ROWS = (
    "| 注：表中各类要素的前后顺序即其在标准中所呈现的具体位置。 |  |  |\n"
    "| a黑体表示“必备要素”；正体表示“规范性要素”。 |  |  |"
)


def _make_pdf(directory: Path, runs: list[tuple[float | str, float, str, float]]) -> Path:
    """runs: (x, baseline_y, text, fontsize)。汉字用内置 china-s。

    x 传字符串 "after" 时取上一个 run 的右缘 + 0.5pt（上标要紧贴锚文本尾部，
    几何判定 dx∈[-2,6] 才成立；CJK 全角字符宽 = 字号，写死 x 容易压进锚文本框）。
    """
    import pymupdf

    path = directory / "synthetic.pdf"
    document = pymupdf.open()
    page = document.new_page(width=595.0, height=300.0)
    last_end = 0.0
    for x, y, text, size in runs:
        left = last_end + 0.5 if x == "after" else float(x)
        page.insert_text((left, y), text, fontsize=size, fontname="china-s")
        last_end = left + pymupdf.get_text_length(text, fontname="china-s", fontsize=size)
    document.save(path)
    document.close()
    return path


class TableNoteMarkerRecoveryTests(unittest.TestCase):
    def test_trailing_superscript_marker_restored_to_header_cell(self) -> None:
        # 表头第 3 列“要素所允许的表述形式”末尾的上标 a（OCR 丢）→ 补回
        # [:sup:a/] 引用点，与表注定义行“a黑体表示…”成对（GB_T_20001.10-2014 表1
        # 复刻形态；2026-09-11 起为通用行内角标标记，不写字面字母）。
        md = _HEADER + "\n| --- | --- | --- |\n| 资料性概述要素 | 封面 | 文字 |\n" + _NOTE_ROWS + "\n"
        with tempfile.TemporaryDirectory() as directory:
            pdf = _make_pdf(
                Path(directory),
                [
                    (84, 100, "要素类型", 10.0),
                    (84, 120, "资料性概述要素", 10.0),
                    (260, 100, "要素所允许的表述形式", 10.0),
                    (260, 120, "文字", 10.0),
                    (360.5, 97.0, "a", 4.66),  # 上标：紧跟“表述形式”尾部(x1≈360)、基线略抬高
                    (84, 140, "注：顺序说明。", 10.0),
                    (84, 155, "a黑体表示“必备要素”。", 10.0),
                ],
            )
            out, recovered = _recover_table_note_markers(md, pdf)
            # 1 处锚点引用点 + 1 行注文定义段包装
            self.assertEqual(recovered, 2)
            self.assertIn("要素所允许的表述形式[:sup:a/]", out)
            self.assertIn("| [:sup:a]黑体表示“必备要素”；正体表示“规范性要素”。[:/sup] |  |  |", out)
            self.assertNotIn("| 资料性概述要素 | 封面 | 文字a |", out)
            # 幂等：再次运行不重复补。
            out2, recovered2 = _recover_table_note_markers(out, pdf)
            self.assertEqual(recovered2, 0)
            self.assertEqual(out2, out)

    def test_literal_tail_marker_converted_to_token(self) -> None:
        # 单元格已有字面尾部字母（OCR 保留，如 GB_T_20001.5-2017 表1 “表述形式a”）
        # 且几何确认该处是上标 → 字面字母改写为显式 [:sup:a/]（渲染端不做字形猜测）。
        md = "| 要素类型 | 要素的编排 | 要素所允许的表述形式a |\n| --- | --- | --- |\n| 资料性概述要素 | 封面 | 文字 |\n" + _NOTE_ROWS + "\n"
        with tempfile.TemporaryDirectory() as directory:
            pdf = _make_pdf(
                Path(directory),
                [
                    (84, 100, "要素类型", 10.0),
                    (260, 100, "要素所允许的表述形式", 10.0),
                    (360.5, 97.0, "a", 4.66),
                    (84, 155, "a黑体表示“必备要素”。", 10.0),
                ],
            )
            out, recovered = _recover_table_note_markers(md, pdf)
            self.assertEqual(recovered, 2)  # 字面字母改写 + 注行包装
            self.assertIn("要素所允许的表述形式[:sup:a/]", out)
            self.assertNotIn("表述形式aa", out)
            # 幂等
            out2, recovered2 = _recover_table_note_markers(out, pdf)
            self.assertEqual(recovered2, 0)
            self.assertEqual(out2, out)

    def test_marker_without_def_row_is_left_alone(self) -> None:
        # 无“a汉字”形态的表注定义行（字母未被声明）→ 不猜。
        md = _HEADER + "\n| --- | --- | --- |\n| 资料性概述要素 | 封面 | 文字 |\n| 注：只有普通表注。 |  |  |\n"
        with tempfile.TemporaryDirectory() as directory:
            pdf = _make_pdf(
                Path(directory),
                [
                    (260, 100, "要素所允许的表述形式", 10.0),
                    (372, 97.0, "a", 4.66),
                    (84, 140, "注：只有普通表注。", 10.0),
                ],
            )
            out, recovered = _recover_table_note_markers(md, pdf)
            self.assertEqual(recovered, 0)
            self.assertEqual(out, md)

    def test_mid_cell_superscript_is_not_inserted(self) -> None:
        # “要素a的编排”式词中上标（2026-09-06 起支持唯一命中时补回），但本例归属
        # 不唯一：尾部有 资料性概述要素/规范性一般要素 两个单元格、词中有 表头
        # “要素类型”与“要素的编排”两处 → 双重歧义，保守不补锚点；注行定义段
        # 仍做显式包装（[:sup:a]…[:/sup]）。
        md = "| 要素类型 | 要素的编排 | 要素所允许的表述形式 |\n| --- | --- | --- |\n| 资料性概述要素 | 封面 | 文字 |\n| 规范性一般要素 | 范围 | 条文 |\n" + _NOTE_ROWS + "\n"
        with tempfile.TemporaryDirectory() as directory:
            pdf = _make_pdf(
                Path(directory),
                [
                    (200, 100, "要素", 10.0),
                    (220.3, 97.0, "a", 4.66),  # 上标紧跟“要素”(x1≈220)后，“的编排”还在后面
                    (228, 100, "的编排", 10.0),
                    (400, 100, "要素所允许的表述形式", 10.0),
                    (84, 155, "a黑体表示“必备要素”。", 10.0),
                ],
            )
            out, recovered = _recover_table_note_markers(md, pdf)
            self.assertEqual(recovered, 1)  # 仅注行包装，锚点不猜
            self.assertIn("| [:sup:a]黑体表示“必备要素”；正体表示“规范性要素”。[:/sup] |  |  |", out)
            self.assertNotIn("要素a的编排", out)
            self.assertIn("| 要素类型 | 要素的编排 | 要素所允许的表述形式 |", out)

    def test_midword_marker_restored_when_cell_unique(self) -> None:
        # 词中上标唯一命中（“要素a的编排”型、表内只有一处锚文本+汉字）→
        # [:sup:a/] 引用点补到锚文本之后（GB_T_20001.10-2014 表1 表头同型）。
        note_rows = "| 注：前后顺序即其在标准中呈现的位置。 |  |  |\n| a黑体表示“必备要素”。 |  |  |\n"
        md = "| 类别 | 要素的编排 | 允许的表述形式 |\n| --- | --- | --- |\n| 资料性概述 | 封面 | 文字 |\n| 规范性一般 | 范围 | 条文 |\n" + note_rows
        with tempfile.TemporaryDirectory() as directory:
            pdf = _make_pdf(
                Path(directory),
                [
                    (200, 100, "要素", 10.0),
                    (220.3, 97.0, "a", 4.66),
                    (228, 100, "的编排", 10.0),
                    (400, 100, "允许的表述形式", 10.0),
                    (84, 155, "a黑体表示“必备要素”。", 10.0),
                ],
            )
            out, recovered = _recover_table_note_markers(md, pdf)
            self.assertEqual(recovered, 2)  # 词中引用点 + 注行包装
            self.assertIn("| 类别 | 要素[:sup:a/]的编排 |", out)
            # 幂等：再跑不重复补
            out2, recovered2 = _recover_table_note_markers(out, pdf)
            self.assertEqual(recovered2, 0)
            self.assertEqual(out2, out)

    def test_non_han_tailed_anchor_is_not_recovered(self) -> None:
        # 锚文本非汉字收尾（如“型号GB”+a）→ 渲染端不会上标汉字后字母，不补。
        md = "| 项目 | 型号 |\n| --- | --- |\n| 样机 | 型号GB |\n| a说明文字。 |  |\n"
        with tempfile.TemporaryDirectory() as directory:
            pdf = _make_pdf(
                Path(directory),
                [
                    (200, 100, "型号GB", 10.0),
                    (228.5, 97.0, "a", 4.66),
                    (84, 140, "a说明文字。", 10.0),
                ],
            )
            out, recovered = _recover_table_note_markers(md, pdf)
            self.assertEqual(recovered, 0)
            self.assertEqual(out, md)

    def test_ambiguous_anchor_cell_is_skipped(self) -> None:
        # 同一表格多个单元格以锚文本结尾（无唯一归属）→ 不补锚点；注行定义段
        # 仍做显式包装。
        md = "| 文字 | 文字 |\n| --- | --- |\n| 文字 | 内容 |\n| a说明文字。 |  |\n"
        with tempfile.TemporaryDirectory() as directory:
            pdf = _make_pdf(
                Path(directory),
                [
                    (84, 100, "文字", 10.0),
                    (180, 100, "文字", 10.0),
                    (198.5, 97.0, "a", 4.66),
                    (84, 140, "a说明文字。", 10.0),
                ],
            )
            out, recovered = _recover_table_note_markers(md, pdf)
            self.assertEqual(recovered, 1)  # 仅注行包装
            self.assertNotIn("文字[:sup:a/]", out)
            self.assertIn("| [:sup:a]说明文字。[:/sup] |  |", out)


class ConsecutiveNoteItemsTests(unittest.TestCase):
    """连排表注拆条（GB_T_5171.1-2014 表19/表20 型，2026-09-11 用户裁定）。

    - md 把注文标记字母读丢的条，用源 PDF 表注定义行的注文头文本定位；
    - 同一格里已带标记字母的条不参与补位检索（否则它会被另一条截短的头文本
      误配——表20 的 f/g 两条都以“只有在产品标准中规定了”起头）；
    - 多条注在单元格里**连排**（不写 <br>），标记成对自定界。
    """

    def test_shared_head_notes_do_not_steal_each_others_marks(self) -> None:
        # 表20 复刻：f、g 两条注文头共享 10 字前缀“只有在产品标准中规定了”，
        # 且它们的注文分在 <br> 两段里；f 的标记字母已丢（靠 PDF 注文头补位）。
        md = (
            "| 序号 | 试验项目 | 结果 |\n"
            "| --- | --- | --- |\n"
            "| 12 | 外壳防护等级试验 | √ |\n"
            "| 14 | 工作期限试验 | √ |\n"
            "| a第12项说明。<br>只有在产品标准中规定了外壳防护等级，在新产品设计定型时方进行试验。"
            "<br>g只有在产品标准中规定了工作期限，在新产品设计定型时方进行试验。 |  |  |\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            pdf = _make_pdf(
                Path(directory),
                [
                    (84, 100, "外壳防护等级试验", 10.0),
                    ("after", 97.0, "f", 4.66),
                    (84, 120, "工作期限试验", 10.0),
                    ("after", 117.0, "g", 4.66),
                    # 表注定义行：行首上标字母 + 紧随的注文头（与源 PDF 同形态，
                    # 注文头是 md 丢掉标记字母时定位该条注文起点的证据）。
                    (84, 137.0, "a", 4.66),
                    (90, 140, "第12项说明。", 10.0),
                    (84, 152.0, "f", 4.66),
                    (90, 155, "只有在产品标准中规定了外壳防护等级", 10.0),
                    (84, 167.0, "g", 4.66),
                    (90, 170, "只有在产品标准中规定了工作期限", 10.0),
                ],
            )
            out, _recovered = _recover_table_note_markers(md, pdf)
            self.assertIn(
                "| [:sup:a]第12项说明。[:/sup]"
                "[:sup:f]只有在产品标准中规定了外壳防护等级，在新产品设计定型时方进行试验。[:/sup]"
                "[:sup:g]只有在产品标准中规定了工作期限，在新产品设计定型时方进行试验。[:/sup] |  |  |",
                out,
            )
            # 三条注各归其位：注文行里不出现空注、不出现字母错配。
            note_row = [line for line in out.split("\n") if line.startswith("| [:sup:a]第12项说明")][0]
            self.assertNotIn("[:sup:f/]", note_row)
            self.assertNotIn("[:sup:g/]", note_row)
            self.assertNotIn("<br>", out)
            self.assertIn("| 12 | 外壳防护等级试验[:sup:f/] | √ |", out)
            self.assertIn("| 14 | 工作期限试验[:sup:g/] | √ |", out)
            # 幂等：注文条数、字母归属都不再变化。
            out2, recovered2 = _recover_table_note_markers(out, pdf)
            self.assertEqual(recovered2, 0)
            self.assertEqual(out2, out)

    def test_mixed_missing_letters_are_filled_from_pdf_heads(self) -> None:
        # 八条连排（表20 形态）：md 只保留 a、g 两个字面字母，其余六条靠 PDF
        # 注文头补位；输出连排不写 <br>，每条自成一对标记。
        defs = ["一条甲说明文字", "一条乙说明文字", "一条丙说明文字", "一条丁说明文字",
                "一条戊说明文字", "一条己说明文字", "一条庚说明文字", "一条辛说明文字"]
        md = (
            "| 序号 | 项目 | 结果 |\n"
            "| --- | --- | --- |\n"
            "| 1 | 机械检查 | √ |\n"
            "| "
            + "".join(f"{letter}{head}。" for letter, head in zip("abcdefgh", defs))
            + " |  |  |\n"
        )
        runs = [(84, 100, "机械检查", 10.0)]
        for index, head in enumerate(defs):
            y = 140 + index * 15
            runs.append((84, y - 3.0, "abcdefgh"[index], 4.66))  # 定义行行首上标字母
            runs.append((90, y, head + "。", 10.0))
        with tempfile.TemporaryDirectory() as directory:
            pdf = _make_pdf(Path(directory), runs)
            out, _recovered = _recover_table_note_markers(md, pdf)
            cell = [line for line in out.split("\n") if line.startswith("| [:sup:a]")][0]
            for letter, head in zip("abcdefgh", defs):
                self.assertIn(f"[:sup:{letter}]{head}。[:/sup]", cell)
            self.assertEqual(cell.count("[:/sup]"), 8)
            self.assertNotIn("<br>", cell)
            # 幂等
            out2, recovered2 = _recover_table_note_markers(out, pdf)
            self.assertEqual(recovered2, 0)
            self.assertEqual(out2, out)


class VisualLineClusteringTests(unittest.TestCase):
    """视觉行聚类按基线而非字框顶（d/e 漏检根因，2026-09-11）。

    复刻 GB_T_5171.1-2014 表20 第 7 行的几何：同一表格行内 '—'（西文字体，
    ascender 1.33，字框顶 ≈261.3）与 '电容器端电压'（中文字体，ascender 0.89，
    字框顶 ≈265.4）字框顶差 4.1pt，而基线相同；上标 'd'（4.66pt）基线略抬高
    3.9pt。若按字框顶聚类，锚文本会被拆到下一行 → 角标找不到锚 → d/e 漏检。
    """

    @staticmethod
    def _span(text: str, origin_y: float, origin_x: float, bbox_top: float, bbox_x1: float = 0.0) -> dict:
        return {
            "text": text,
            "size": 8.25,
            "origin": (origin_x, origin_y),
            "bbox": (origin_x, bbox_top, origin_x + bbox_x1, origin_y),
        }

    def test_cjk_anchor_stays_in_line_with_latin_span(self) -> None:
        spans = [
            self._span("—", 267.9, 428.4, 261.3, 8.2),          # 西文：字框顶低 4.1pt
            self._span("电容器端电压", 272.7, 116.3, 265.4, 53.3),  # 中文：字框顶高
            {"text": "d", "size": 4.66, "origin": (169.4, 269.9), "bbox": (169.4, 263.7, 174.0, 274.8)},
        ]
        lines = _cluster_visual_lines(spans)
        self.assertEqual(len(lines), 1)
        ordered = sorted(lines[0], key=lambda s: s["origin"][0])
        self.assertEqual([s["text"] for s in ordered], ["电容器端电压", "d", "—"])

    def test_bbox_top_clustering_would_split(self) -> None:
        # 反证：按字框顶聚类时锚文本被拆出去（这就是修复前的行为）。
        spans = [
            self._span("—", 267.9, 428.4, 261.3, 8.2),
            self._span("电容器端电压", 272.7, 116.3, 265.4, 53.3),
        ]
        ordered = sorted(spans, key=lambda s: (s["bbox"][1], s["bbox"][0]))
        lines: list[list[dict]] = []
        for span in ordered:
            if lines and abs(span["bbox"][1] - lines[-1][0]["bbox"][1]) <= 4:
                lines[-1].append(span)
            else:
                lines.append([span])
        self.assertEqual(len(lines), 2)

    def test_adjacent_table_rows_are_not_merged(self) -> None:
        # 相邻表格行基线相距 ≈15pt → 5pt 容差不会并成一行。
        spans = [
            self._span("堵转试验", 273.8, 84.0, 262.8, 33.0),
            self._span("振动的测定", 291.0, 99.8, 280.0, 44.0),
        ]
        lines = _cluster_visual_lines(spans)
        self.assertEqual(len(lines), 2)


if __name__ == "__main__":
    unittest.main()
