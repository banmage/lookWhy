"""构建/验证模块的完整性守护：函数体里的 LOAD_GLOBAL 必须真的存在。

背景（2026-09-12 把下游阶段从 `tools/mineru_full_standard.py` 搬到
`src/leleby_ssir/pipeline.py`）：搬移只按 AST 里的 ``Assign`` 收集顶层常量，
漏掉了 **``AnnAssign``** 形式的 `_ISSUER_FRAGMENTS`（带类型注解的常量）。
单测与产物哈希比对都没抓住它（产物是搬移前跑出来的、没有测试走到那条分支），
直到真实入口跑一遍 `build_ssir.py <json>` 才以 NameError 暴露。

因此这里做一次静态检查：把模块里每个函数的字节码扫描一遍，凡是 ``LOAD_GLOBAL`` /
``LOAD_NAME`` 的名字，要么在模块全局里有定义（含导入），要么是内建，否则判定为
「漏搬/未定义」并失败。这比单元测试更早、更全地覆盖「函数被搬走但依赖没搬」这一类
结构性错误。
"""

from __future__ import annotations

import builtins
import dis
import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

MODULES = (
    "leleby_ssir.pipeline",
    "leleby_ssir.pdf_compare",
    "leleby_ssir.mineru_middle",
    "leleby_ssir.mineru_html",
    "mineru_full_standard",
    "build_ssir",
    "verify_conversion",
)


def _undefined_globals(module) -> list[str]:
    """模块内所有代码对象里 LOAD_GLOBAL/LOAD_NAME 到未定义名字的清单。"""
    module_globals = set(vars(module))
    bad: set[str] = set()
    seen: set[int] = set()

    def walk(code) -> None:
        if id(code) in seen:
            return
        seen.add(id(code))
        for instruction in dis.get_instructions(code):
            if instruction.opname in ("LOAD_GLOBAL", "LOAD_NAME"):
                name = instruction.argval
                if isinstance(name, str) and name not in module_globals and not hasattr(builtins, name):
                    bad.add(name)
        for constant in code.co_consts:
            if hasattr(constant, "co_code"):
                walk(constant)

    for value in list(vars(module).values()):
        # 只检查**本模块定义**的函数：import 进来的函数属于别的模块，
        # 它们的全局名要在那个模块里解析（否则误报，例如 pipeline 里
        # 复用的 html_table_to_csm 会带上 mineru_html 的全局名）。
        if getattr(value, "__module__", None) != module.__name__:
            continue
        code = getattr(value, "__code__", None)
        if code is not None:
            walk(code)
        elif isinstance(value, property):
            for accessor in (value.fget, value.fset, value.fdel):
                if accessor is not None and hasattr(accessor, "__code__"):
                    walk(accessor.__code__)
    return sorted(bad)


class ModuleGlobalIntegrityTests(unittest.TestCase):
    """搬移/重构后：任何函数引用的全局名都必须在模块里存在（防「函数搬了、常量没搬」）。"""

    def test_no_undefined_globals(self) -> None:
        problems: dict[str, list[str]] = {}
        for name in MODULES:
            module = importlib.import_module(name)
            missing = _undefined_globals(module)
            if missing:
                problems[name] = missing
        self.assertEqual(problems, {}, f"存在未定义的全局引用（疑似漏搬）：{problems}")

    def test_pipeline_module_keeps_the_moved_downstream_api(self) -> None:
        """搬移后下游阶段必须在 pipeline 里可用（抽取工具只做 re-export）。"""
        from leleby_ssir import pipeline

        for name in ("finalize", "_post_parse_verify_render", "_run_from_existing_canonical",
                     "_stage_paths", "_write_manifest", "_stamp_example_styles",
                     "_stamp_figure_source_sizes", "_stamp_figure_source_sizes_from_map",
                     "_recover_pdf_footnotes", "_cover_metadata", "_canonical_issuer",
                     "_ISSUER_FRAGMENTS"):
            self.assertTrue(hasattr(pipeline, name), f"pipeline 缺少 {name}")

    def test_extraction_tool_no_longer_owns_the_downstream_stages(self) -> None:
        """抽取工具只保留扫描/合并职责：下游阶段的实现应来自 pipeline（同一对象）。"""
        import mineru_full_standard as mfs
        from leleby_ssir import pipeline

        for name in ("finalize", "_post_parse_verify_render", "_stamp_figure_source_sizes"):
            self.assertIs(getattr(mfs, name), getattr(pipeline, name), f"{name} 不是 pipeline 的实现")


if __name__ == "__main__":
    unittest.main()
