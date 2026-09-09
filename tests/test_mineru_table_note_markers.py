from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from mineru_full_standard import _recover_table_note_markers  # noqa: E402

# 表注锚点上标字母回收（CSM-OCR-015，2026-09-06）：MinerU OCR 丢表头/单元格里跟的
# 上标小写字母、只留表注定义行（GB_T_20001.10-2014 表1 型），从源 PDF 文本层几何
# 补回单元格尾部标记。夹具必须用 pymupdf 内置 CJK 字体造真实中文文本层（AGENTS §2）。

_HEADER = "| 要素类型 | 要素的编排 | 要素所允许的表述形式 |"
_NOTE_ROWS = (
    "| 注：表中各类要素的前后顺序即其在标准中所呈现的具体位置。 |  |  |\n"
    "| a黑体表示“必备要素”；正体表示“规范性要素”。 |  |  |"
)


def _make_pdf(directory: Path, runs: list[tuple[float, float, str, float]]) -> Path:
    """runs: (x, baseline_y, text, fontsize)。汉字用内置 china-s；上标字母用默认字体。"""
    import pymupdf

    path = directory / "synthetic.pdf"
    document = pymupdf.open()
    page = document.new_page(width=595.0, height=300.0)
    for x, y, text, size in runs:
        page.insert_text((x, y), text, fontsize=size, fontname="china-s")
    document.save(path)
    document.close()
    return path


class TableNoteMarkerRecoveryTests(unittest.TestCase):
    def test_trailing_superscript_marker_restored_to_header_cell(self) -> None:
        # 表头第 3 列“要素所允许的表述形式”末尾的上标 a（OCR 丢）→ 补回 [:^a]
        # 引用点，与表注定义行“a黑体表示…”成对（GB_T_20001.10-2014 表1 复刻形态，
        # 2026-09-07 语法定案：显式标记，不再写字面字母）。
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
            self.assertIn("要素所允许的表述形式[:^a]", out)
            self.assertIn("| [^a]黑体表示“必备要素”；正体表示“规范性要素”。[^a/] |  |  |", out)
            self.assertNotIn("| 资料性概述要素 | 封面 | 文字a |", out)
            # 幂等：再次运行不重复补。
            out2, recovered2 = _recover_table_note_markers(out, pdf)
            self.assertEqual(recovered2, 0)
            self.assertEqual(out2, out)

    def test_literal_tail_marker_converted_to_token(self) -> None:
        # 单元格已有字面尾部字母（OCR 保留，如 GB_T_20001.5-2017 表1 “表述形式a”）
        # 且几何确认该处是上标 → 字面字母改写为显式 [:a]（渲染端不再做字形猜测）。
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
            self.assertIn("要素所允许的表述形式[:^a]", out)
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
        # 仍做显式包装（[^a]…[^a/]，2026-09-07）。
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
            self.assertIn("| [^a]黑体表示“必备要素”；正体表示“规范性要素”。[^a/] |  |  |", out)
            self.assertNotIn("要素a的编排", out)
            self.assertIn("| 要素类型 | 要素的编排 | 要素所允许的表述形式 |", out)

    def test_midword_marker_restored_when_cell_unique(self) -> None:
        # 词中上标唯一命中（“要素a的编排”型、表内只有一处锚文本+汉字）→ [:a]
        # 引用点补到锚文本之后（GB_T_20001.10-2014 表1 表头同型，2026-09-06；
        # 2026-09-07 起输出显式 [:x] 标记）。
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
            self.assertIn("| 类别 | 要素[:^a]的编排 |", out)
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
            self.assertNotIn("文字[:^a]", out)
            self.assertIn("| [^a]说明文字。[^a/] |  |", out)


if __name__ == "__main__":
    unittest.main()
