"""脚注 / 表角标回收的 ``layout.json`` 通道消费端夹具（docs/16 §3，C1-6）。

两条恢复规则（``CSM-OCR-014`` 条文脚注、``CSM-OCR-015`` 表角标）迁移前各自打开源 PDF
读逐页 span；迁移后读数由抽取阶段写进 ``layout.json`` 的 ``textSpans`` / ``pages`` 通道，
消费端只读通道（源 PDF 不在场也必须成立）。本文件锁两件事：

① **通道 = 直读**：同一夹具下，走通道与走源 PDF 的结果逐字节相同（通道不改判据）；
② **无 PDF 也成立**：把 ``pdf`` 传 ``None``、只给通道，恢复结果不变（旧实现只能返回空）。
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from mineru_full_standard import (  # noqa: E402
    _recover_pdf_footnotes,
    _recover_table_note_markers,
)

from leleby_ssir.layout import build_layout  # noqa: E402

_HEADER = "| 要素类型 | 要素的编排 | 要素所允许的表述形式 |"
_NOTE_ROWS = (
    "| 注：表中各类要素的前后顺序即其在标准中所呈现的具体位置。 |  |  |\n"
    "| a黑体表示“必备要素”；正体表示“规范性要素”。 |  |  |"
)


def _make_pdf(directory: Path, runs: list[tuple[float | str, float, str, float]],
              *, height: float = 300.0) -> Path:
    """runs: (x, baseline_y, text, fontsize)；x 传 "after" 时紧贴上一条右缘 +0.5pt。"""
    import pymupdf

    path = directory / "synthetic.pdf"
    document = pymupdf.open()
    page = document.new_page(width=595.0, height=height)
    last_end = 0.0
    for x, y, text, size in runs:
        left = last_end + 0.5 if x == "after" else float(x)
        page.insert_text((left, y), text, fontsize=size, fontname="china-s")
        last_end = left + pymupdf.get_text_length(text, fontname="china-s", fontsize=size)
    document.save(path)
    document.close()
    return path


class TableNoteMarkerChannelTests(unittest.TestCase):
    """表角标回收（CSM-OCR-015）：通道优先，无源 PDF 也成立。"""

    def _markdown(self) -> str:
        return _HEADER + "\n| --- | --- | --- |\n| 资料性概述要素 | 封面 | 文字 |\n" + _NOTE_ROWS + "\n"

    def _fixture(self, directory: Path) -> Path:
        return _make_pdf(
            directory,
            [
                (84, 100, "要素类型", 10.0),
                (84, 120, "资料性概述要素", 10.0),
                (260, 100, "要素所允许的表述形式", 10.0),
                (260, 120, "文字", 10.0),
                (360.5, 97.0, "a", 4.66),   # 上标：紧跟“表述形式”尾部
                (84, 140, "注：顺序说明。", 10.0),
                (84, 155, "a黑体表示“必备要素”。", 10.0),
            ],
        )

    def test_channel_result_equals_the_source_pdf_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf = self._fixture(Path(directory))
            layout = build_layout(pdf)
            from_pdf = _recover_table_note_markers(self._markdown(), pdf)
            from_channel = _recover_table_note_markers(self._markdown(), None, layout=layout)
        self.assertEqual(from_pdf, from_channel)
        self.assertEqual(from_channel[1], 2)  # 1 处锚点引用点 + 1 行注文定义段包装
        self.assertIn("要素所允许的表述形式$^{a}$", from_channel[0])

    def test_channel_works_without_any_source_pdf(self) -> None:
        """源 PDF 不在场（已删除/仅剩 canonical + layout.json）时恢复照旧成立。"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = self._fixture(root)
            layout = build_layout(pdf)
            layout_path = root / "std.layout.json"
            layout_path.write_text(json.dumps(layout, ensure_ascii=False), encoding="utf-8")
            pdf.unlink()
            # 消费端拿到的是**从文件读回**的通道（JSON 往返：tuple→list，origin 保留）
            from leleby_ssir.layout import load_layout

            reloaded = load_layout(layout_path)
            out, recovered = _recover_table_note_markers(self._markdown(), None, layout=reloaded)
        self.assertEqual(recovered, 2)
        self.assertIn("要素所允许的表述形式$^{a}$", out)


class FootnoteChannelTests(unittest.TestCase):
    """条文脚注回收（CSM-OCR-014）：通道优先，无源 PDF 也成立。"""

    def _fixture(self, directory: Path) -> tuple[Path, str]:
        pdf = _make_pdf(
            directory,
            [
                (72, 100, "已修订为GB/T 20000.4—2003", 10.0),
                ("after", 97.0, "1)", 5.0),        # 上标标记：紧贴锚文本尾部（dx≈0.5pt）
                (72, 250, "1) 该标准已由新版代替。", 8.0),   # 页底小字解释行（y ≥ 0.68×页高）
            ],
            height=300.0,
        )
        markdown = "已修订为GB/T 20000.4—20031，自发布之日起实施。\n"
        return pdf, markdown

    def _run(self, pdf: Path | None, markdown: str, layout: dict | None) -> tuple[str, int]:
        with tempfile.TemporaryDirectory() as directory:
            md = Path(directory) / "std.canonical.md"
            md.write_text(markdown, encoding="utf-8")
            recovered = _recover_pdf_footnotes(md, pdf, layout=layout)
            return md.read_text(encoding="utf-8"), recovered

    def test_channel_result_equals_the_source_pdf_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pdf, markdown = self._fixture(Path(directory))
            layout = build_layout(pdf)
            from_pdf = self._run(pdf, markdown, None)
            from_channel = self._run(None, markdown, layout)
        self.assertEqual(from_pdf, from_channel)
        self.assertGreaterEqual(from_channel[1], 1, "夹具应至少回收 1 条脚注")
        self.assertIn("<!--ssir:foot:1-->", from_channel[0])

    def test_channel_works_without_any_source_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf, markdown = self._fixture(root)
            layout = build_layout(pdf)
            pdf.unlink()
            out, recovered = self._run(None, markdown, layout)
        self.assertGreaterEqual(recovered, 1)
        self.assertIn("<!--ssir:foot:1-->", out)


if __name__ == "__main__":
    unittest.main()
