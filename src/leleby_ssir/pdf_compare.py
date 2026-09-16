"""PDF 版面/文本量对比（GEN-051/GEN-090/GEN-091 的机器验证部分）。

独立成模块，供验证程序（``tools/verify_conversion.py``）与构建程序使用；只读两个 PDF 的
内部对象（页数、字节、文本层字符数），不重新解析 Markdown。"""


from __future__ import annotations

from pathlib import Path
from typing import Any

from leleby_ssir.pipeline import _write_json


def compare(original: Path, generated: Path, output: Path) -> None:
    # 规则对应: GEN-051（元数据往返一致）、GEN-090（机器验证：关键封面字段齐全、
    # 页数合理）、GEN-091（基于 PDF 内部对象验证）。
    import fitz  # type: ignore
    def details(path: Path) -> dict[str, Any]:
        with fitz.open(path) as document:
            text = "".join(page.get_text() for page in document)
            return {"path": str(path), "bytes": path.stat().st_size, "pageCount": len(document), "textCharacters": len(text)}
    original_info, generated_info = details(original), details(generated)
    _write_json(output, {
        "original": original_info,
        "generated": generated_info,
        "delta": {"pages": generated_info["pageCount"] - original_info["pageCount"], "bytes": generated_info["bytes"] - original_info["bytes"], "textCharacters": generated_info["textCharacters"] - original_info["textCharacters"]},
        "review": "Page count and text volume are objective checks. Tables, formula layout, pagination, and typography require visual review against the original PDF.",
    })
