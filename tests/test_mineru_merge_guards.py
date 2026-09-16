"""merge 阶段的输入校验：没有 MinerU 分片时给出可操作错误，而不是 IndexError。

背景（2026-09-12 三层拆分后回归实测）：对由 raw 起点构建的文档根执行
`mineru_full_standard.py --input <pdf> --stage merge`（该文档根本来就没有 parts/）会
以 `parts_raw[0]` 触发 IndexError。这是长期存在的报错质量问题，本轮改为明确的
RuntimeError（main 捕获后打印 error 并以非零退出）。
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from mineru_full_standard import merge  # noqa: E402


def _args(output_dir: Path, pdf: Path) -> argparse.Namespace:
    return argparse.Namespace(output_dir=output_dir, input=pdf, output_stem="T", chunk_size=18,
                              title="", front_matter_json_value={}, hybrid_tables=False)


class MergeGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_merge_without_any_parts_reports_a_usable_error(self) -> None:
        pdf = self.root / "T.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        with self.assertRaises(RuntimeError) as caught:
            merge(_args(self.root, pdf), {})
        message = str(caught.exception)
        self.assertIn("no MinerU page ranges", message)
        self.assertIn("build_ssir", message)          # 给出替代入口

    def test_merge_with_recorded_but_missing_parts_lists_the_pages(self) -> None:
        pdf = self.root / "T.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        state = {"pageCount": 36, "parts": []}
        with self.assertRaises(RuntimeError) as caught:
            merge(_args(self.root, pdf), state)
        self.assertIn("pages starting at", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
