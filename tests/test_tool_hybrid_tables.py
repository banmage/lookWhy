"""GEN-094 表格块 hybrid-engine 第二遍的拼接/回退逻辑回归测试。

覆盖 tools/mineru_full_standard.py 新增纯函数：
- _splice_hybrid_table_blocks：按（页, 页内序）替换 pipeline 表块行，保留
  pipeline 指令行（id/题注/编号），merge 指令 table 引用改写为真实 id；
  块/页数不齐或该页 hybrid 不足时确定性回退 pipeline 表。
- _pipeline_table_pages / _hybrid_tables_by_page：MinerU content_list 的
  page_idx 是相对 invocation 起始页的本地索引，base 偏移得全局页号。
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import mineru_full_standard as mfs  # noqa: E402

# pipeline 转换后的 raw（两表：表1 被压平、表2 正常），块间以空行分隔
PIPELINE_RAW = """前言段…

<!-- ssir:table id="mineru-table-p001-001" header-rows="1" caption-number="1" -->
| 部件 | 温升/K |
| --- | --- |
| 电动机绕组：-105(A级)-120(E级)-130(B级) | 60(50)75(65)80(70) |

正文…

<!-- ssir:table id="mineru-table-p001-002" header-rows="1" caption-number="2" -->
| x | y |
| --- | --- |
| 1 | 2 |"""

# hybrid-engine 对表1 的 HTML：隐藏行恢复为逐行 + 通栏注行 colspan
HYBRID_T1_HTML = (
    "<table><tr><td>部件</td><td>温升/K</td></tr>"
    "<tr><td>—105(A级)</td><td>60(50)</td></tr>"
    "<tr><td>—120(E级)</td><td>75(65)</td></tr>"
    '<tr><td colspan="2">换向器注文…</td></tr></table>'
)
HYBRID_T2_HTML = (
    "<table><tr><td>部件</td><td>温升/K</td></tr>"
    '<tr><td colspan="2">注2…</td></tr></table>'
)

TBL_PAGES = [11, 12]  # 表1 在页 11、表2 在页 12


class SpliceTests(unittest.TestCase):
    def test_replaces_hidden_row_table_keeps_directive(self):
        hybrid = {11: [HYBRID_T1_HTML]}
        out, replaced, kept = mfs._splice_hybrid_table_blocks(PIPELINE_RAW, TBL_PAGES, hybrid)
        self.assertEqual((replaced, kept), (1, 1))
        # 指令行保留 pipeline 的 id/题注
        self.assertIn('<!-- ssir:table id="mineru-table-p001-001" header-rows="1" caption-number="1" -->', out)
        # 压平的粘接行消失、逐行结构出现
        self.assertNotIn("电动机绕组：-105(A级)-120(E级)-130(B级)", out)
        self.assertIn("| —105(A级) | 60(50) |", out)
        self.assertIn("| —120(E级) | 75(65) |", out)
        # colspan 注行 merge 指令引用真实表 id（而非 html_table_to_csm 占位 id）
        self.assertIn('<!-- ssir:table-merge table="mineru-table-p001-001"', out)
        self.assertNotIn('table="mineru-table-hybrid"', out)
        # 表2（无 hybrid 提供页）保持 pipeline 原样
        self.assertIn('<!-- ssir:table id="mineru-table-p001-002" header-rows="1" caption-number="2" -->', out)
        self.assertIn("| 1 | 2 |", out)
        self.assertNotIn("注2", out)

    def test_multiple_tables_same_page_use_page_ordinals(self):
        hybrid = {11: [HYBRID_T1_HTML, HYBRID_T2_HTML]}
        pages = [11, 11]
        out, replaced, kept = mfs._splice_hybrid_table_blocks(PIPELINE_RAW, pages, hybrid)
        self.assertEqual((replaced, kept), (2, 0))
        self.assertIn("| —105(A级) | 60(50) |", out)
        self.assertIn("注2", out)
        self.assertIn('table="mineru-table-p001-002"', out)

    def test_page_without_hybrid_keeps_pipeline(self):
        out, replaced, kept = mfs._splice_hybrid_table_blocks(PIPELINE_RAW, TBL_PAGES, {99: [HYBRID_T1_HTML]})
        self.assertEqual((replaced, kept), (0, 2))
        self.assertEqual(out, PIPELINE_RAW)

    def test_hybrid_page_has_fewer_tables_keeps_pipeline_for_that_page(self):
        # 同页 2 个 pipeline 表、hybrid 只给了 1 个：第 1 个替换、第 2 个保持 pipeline
        hybrid = {11: [HYBRID_T1_HTML]}
        pages = [11, 11]
        out, replaced, kept = mfs._splice_hybrid_table_blocks(PIPELINE_RAW, pages, hybrid)
        self.assertEqual((replaced, kept), (1, 1))
        self.assertIn("| —105(A级) | 60(50) |", out)
        self.assertIn("| x | y |", out)  # 表2 未被替换，保持原样

    def test_block_page_count_mismatch_keeps_all_pipeline(self):
        out, replaced, kept = mfs._splice_hybrid_table_blocks(PIPELINE_RAW, [11], {11: [HYBRID_T1_HTML]})
        self.assertEqual((replaced, kept), (0, 0))
        self.assertEqual(out, PIPELINE_RAW)

    def test_empty_hybrid_html_keeps_pipeline(self):
        out, replaced, kept = mfs._splice_hybrid_table_blocks(PIPELINE_RAW, TBL_PAGES, {11: ["<table></table>"]})
        self.assertEqual((replaced, kept), (0, 2))
        self.assertEqual(out, PIPELINE_RAW)

    def test_no_hybrid_input_returns_unchanged(self):
        out, replaced, kept = mfs._splice_hybrid_table_blocks(PIPELINE_RAW, TBL_PAGES, {})
        self.assertEqual((replaced, kept), (0, 0))
        self.assertEqual(out, PIPELINE_RAW)


class ContentListHelpersTests(unittest.TestCase):
    def _write_content_list(self, tmp: Path, items: list[dict]) -> None:
        (tmp / "doc_content_list.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")

    def test_page_index_is_local_and_needs_base_offset(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self._write_content_list(tmp, [
                {"type": "table", "page_idx": 0, "table_body": "<table><tr><td>a</td></tr></table>"},
                {"type": "paragraph", "page_idx": 0, "content": "正文"},
                {"type": "table", "page_idx": 2, "table_body": "<table><tr><td>b</td></tr></table>"},
            ])
            # -s 11 的 invocation 内 page_idx 0..，全局 = base + 本地
            self.assertEqual(mfs._pipeline_table_pages(tmp, base=11), [11, 13])
            hybrid = mfs._hybrid_tables_by_page(tmp, base=11)
            self.assertEqual(list(hybrid), [11, 13])
            self.assertEqual(len(hybrid[11]), 1)

    def test_missing_content_list_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            self.assertEqual(mfs._pipeline_table_pages(tmp, base=0), [])
            self.assertEqual(mfs._hybrid_tables_by_page(tmp, base=0), {})


class HybridFlagDefaultTests(unittest.TestCase):
    """GEN-094 表格通道默认关闭（2026-09-09 调整）：不加参数时表格保持 pipeline
    原样（原始逻辑），仅 --hybrid-tables 显式开启才跑 hybrid 第二遍。旧
    --no-hybrid-tables 旗标已移除。"""

    def _parse(self, *extra: str) -> argparse.Namespace:
        # parse_args 不做输入文件存在性校验（在 main() 里做），这里可传假路径。
        return mfs._build_parser().parse_args(["--input", "dummy.pdf", *extra])

    def test_hybrid_tables_off_by_default(self):
        ns = self._parse()
        self.assertFalse(getattr(ns, "hybrid_tables", True))
        self.assertFalse(hasattr(ns, "no_hybrid_tables"))

    def test_hybrid_tables_flag_enables(self):
        self.assertTrue(self._parse("--hybrid-tables").hybrid_tables)

    def test_old_no_hybrid_tables_flag_removed(self):
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                self._parse("--no-hybrid-tables")


if __name__ == "__main__":
    unittest.main()
