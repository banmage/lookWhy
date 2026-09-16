"""`tools/extract_schema.py` 的安全约定回归。

背景（2026-09-12 实测事故）：该脚本是「从设计文档 docs/02 提取 Schema 覆盖
`src/leleby_ssir/ssir.schema.json`」的维护脚本，旧版**无参数即写入**。一次
「把所有工具脚本 `--help` 巡查一遍」的命令把它直接执行，按 v0.3 设计稿重生成，
静默删掉 107 行属性声明（`box`/`boxStyle`/`exampleContent`/`englishTerm`/`term`/
`sideBySide*`/`sourceWidth`/`footnoteMarker` …），导致 `csm normalize/parse` 与
13 个单测因 `Additional properties are not allowed` 失败、整条构建链路退出码 2。

现在的约定（本测试钉住）：
- 默认**只比对不写入**；
- `--write` 在「会删除目标文件已有属性」时**拒绝**（退出码 2）；
- `--write --force` 才真正覆盖；
- `--help` 必须是打印帮助，不得产生任何写入。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import extract_schema  # noqa: E402

PYTHON = str(ROOT / ".venv" / "bin" / "python")


class ExtractSchemaGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.source = self.root / "design.md"
        self.target = self.root / "schema.json"
        design = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": {
                "metadata": {"type": "object", "properties": {"title": {"type": "string"}}},
            },
        }
        self.source.write_text("说明\n\n```json\n" + json.dumps(design, ensure_ascii=False) + "\n```\n",
                               encoding="utf-8")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([PYTHON, str(ROOT / "tools" / "extract_schema.py"),
                               "--source", str(self.source), "--target", str(self.target), *args],
                              cwd=ROOT, capture_output=True, text=True)

    def test_default_run_compares_without_writing(self) -> None:
        self.target.write_text(json.dumps({"type": "object", "properties": {"metadata": {}}}), encoding="utf-8")
        before = self.target.read_text(encoding="utf-8")
        result = self._run()
        self.assertEqual(result.returncode, 0)
        self.assertIn("只比对，未写入", result.stdout)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_write_refuses_to_drop_existing_properties(self) -> None:
        # 目标文件带执行侧新增属性（设计稿没有）→ 拒绝
        self.target.write_text(json.dumps({
            "type": "object",
            "properties": {"metadata": {}, "exampleContent": {"type": "boolean"}},
        }, ensure_ascii=False), encoding="utf-8")
        result = self._run("--write")
        self.assertEqual(result.returncode, 2)
        self.assertIn("拒绝写入", result.stderr)
        self.assertIn("exampleContent", result.stderr)
        self.assertIn("exampleContent", self.target.read_text(encoding="utf-8"))   # 未被删掉

    def test_write_force_replaces_the_target(self) -> None:
        self.target.write_text(json.dumps({
            "type": "object", "properties": {"metadata": {}, "exampleContent": {}}}), encoding="utf-8")
        result = self._run("--write", "--force")
        self.assertEqual(result.returncode, 0)
        written = json.loads(self.target.read_text(encoding="utf-8"))
        self.assertIn("metadata", written["properties"])
        self.assertNotIn("exampleContent", written["properties"])

    def test_help_never_writes(self) -> None:
        """旧版无 argparse：`--help` 会照常执行并覆盖 Schema（本次事故的直接原因）。"""
        self.target.write_text("ORIGINAL", encoding="utf-8")
        result = subprocess.run([PYTHON, str(ROOT / "tools" / "extract_schema.py"), "--help"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("--write", result.stdout)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "ORIGINAL")

    def test_real_schema_is_newer_than_the_design_document(self) -> None:
        """执行侧 Schema 比设计稿新：--write 必须拒绝，否则会删掉这些属性。"""
        missing, extra = extract_schema.compare(
            extract_schema.schema_from_design_document(extract_schema.SOURCE),
            json.loads(extract_schema.TARGET.read_text(encoding="utf-8")))
        self.assertGreater(len(extra), 0, "执行侧 Schema 应含设计稿没有的属性")
        for name in ("exampleContent", "englishTerm", "boxStyle", "sourceWidth"):
            self.assertIn(name, extra)


if __name__ == "__main__":
    unittest.main()
