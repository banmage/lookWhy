#!/usr/bin/env python3
"""独立的一致性验证程序：SSIR 投影 ＋ 合规/质量报告 ＋（可选）PDF 版面/文本量对比。

从构建流水线里抽出来的**可单独运行**的验证入口：只读既有产物，不生成 canonical，
不修改任何输入。构建流程本身不做任何验证（docs/16 §P0-F：回环验证永久下线）。

用法::

    # 裸标准 ID（默认文档根 out/mineru/<ID>）
    .venv/bin/python tools/verify_conversion.py GB_T_20001.6-2017

    # 文档根目录 / canonical 文件 / SSIR 文件都可以作为输入
    .venv/bin/python tools/verify_conversion.py out/mineru/GB_T_20001.6-2017
    .venv/bin/python tools/verify_conversion.py out/mineru/GB_T_20001.6-2017/02_canonical/GB_T_20001.6-2017.canonical.md

    # 顺带做源 PDF 与渲染 PDF 的版面/文本量对比（需源 PDF；缺省查 corpus/golden/<ID>.pdf）
    .venv/bin/python tools/verify_conversion.py GB_T_20001.6-2017 --source-pdf corpus/golden/GB_T_20001.6-2017.pdf

产物（写入既有文档根，不覆盖 canonical）::

    04_render/<stem>.render.md               SSIR 的标准 markdown 投影（零指令、零 HTML 注释）
    04_render/<stem>.render-comparison.json 与源 PDF 的对比统计（需源 PDF）
    05_verify/<stem>.verify.json             SSIR 合规/质量报告（parse report）

退出码：``0`` 通过；``2`` 用法/引擎错误。

规则对应：GEN-090（机器验证）、GEN-091（基于 PDF 内部对象验证）。
回环验证（canonical↔SSIR↔render.md↔verify）已于 2026-09-22 永久下线（用户裁定）：
本程序只做「投影 + 合规/质量报告 + （可选）PDF 对比」。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from leleby_ssir.pdf_compare import compare  # noqa: E402
from leleby_ssir.csm_renderer import asset_base_for, render_csm  # noqa: E402
from leleby_ssir.html_renderer import render_html  # noqa: E402
from leleby_ssir.pipeline import _log, _stage_paths  # noqa: E402
from leleby_ssir.service import parse_csm_with_report  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
VERIFY_DIR = "05_verify"  # 验证报告目录（构建流程不写；本程序与 docs 的约定）

CANONICAL_SUFFIX = ".canonical.md"
SSIR_SUFFIX = ".ssir.json"


def resolve_targets(entry: str | Path, root: Path, output_dir: Path | None = None) -> tuple[Path, Path, str]:
    """输入 → ``(docroot, canonical, stem)``。

    - ``<ID>``（裸名）→ ``<root>/out/mineru/<ID>``；
    - 目录 → 该文档根（内部找唯一的 ``02_canonical/*.canonical.md``）；
    - ``*.canonical.md`` → 其所在文档根（``02_canonical/`` 的上一级，否则 ``--output-dir``／同级）；
    - ``*.ssir.json`` → ``03_ssir/`` 的上一级，canonical 按同名推导。
    """
    path = Path(entry)
    if path.is_file():
        name = path.name
        if name.endswith(CANONICAL_SUFFIX):
            docroot = output_dir or (
                path.parent.parent if path.parent.name == "02_canonical" else Path(".").resolve())
            stem = name[: -len(CANONICAL_SUFFIX)]
            return docroot, path, stem
        if name.endswith(SSIR_SUFFIX):
            docroot = output_dir or (
                path.parent.parent if path.parent.name == "03_ssir" else Path(".").resolve())
            stem = name[: -len(SSIR_SUFFIX)]
            canonical = docroot / "02_canonical" / f"{stem}{CANONICAL_SUFFIX}"
            if not canonical.is_file():
                raise RuntimeError(f"找不到与 {path.name} 对应的 canonical：{canonical}")
            return docroot, canonical, stem
        raise RuntimeError(f"不支持的输入 {path}（需要 *.canonical.md / *.ssir.json / 文档根目录 / 裸标准 ID）")
    docroot = output_dir or (path if path.is_dir() else root / "out" / "mineru" / path.name)
    if not docroot.is_dir():
        raise RuntimeError(f"文档根目录不存在：{docroot}")
    candidates = sorted(docroot.glob(f"02_canonical/*{CANONICAL_SUFFIX}")) or sorted(docroot.glob(f"*{CANONICAL_SUFFIX}"))
    if len(candidates) != 1:
        raise RuntimeError(f"{docroot} 下应能定位唯一一份 *{CANONICAL_SUFFIX}，实际 {len(candidates)} 份")
    canonical = candidates[0]
    return docroot, canonical, canonical.name[: -len(CANONICAL_SUFFIX)]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="独立验证：SSIR markdown 投影 + 合规/质量报告（+ 可选 PDF 对比），只读既有产物。"
    )
    parser.add_argument("entry", nargs="?", help="裸标准 ID / 文档根目录 / *.canonical.md / *.ssir.json")
    parser.add_argument("--input", type=Path, help="与位置参数二选一")
    parser.add_argument("--output-dir", type=Path, help="文档根目录（默认由输入推导）")
    parser.add_argument("--source-pdf", type=Path, help="源 PDF（用于版面/文本量对比；缺省查 corpus/golden/<ID>.pdf）")
    parser.add_argument("--no-pdf-comparison", action="store_true", help="跳过源 PDF 与渲染 PDF 的对比")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    if not args.entry and not args.input:
        parser.error("需要输入：裸标准 ID / 文档根目录 / canonical 文件 / SSIR 文件")
    try:
        docroot, canonical, stem = resolve_targets(args.input or args.entry, ROOT, args.output_dir)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    paths = _stage_paths(docroot, stem)
    for stage_path in (paths["render_md"], paths["render_html"], paths["render_pdf"]):
        stage_path.parent.mkdir(parents=True, exist_ok=True)

    # render.md = SSIR 的标准 markdown 投影；verify.json = 合规/质量报告（parse report）。
    # 报告是**本验证程序**的产物（构建流程不写），故路径在此定义而不取自流水线阶段表。
    verify_path = docroot / VERIFY_DIR / f"{stem}.verify.json"
    verify_path.parent.mkdir(parents=True, exist_ok=True)
    _log(f"Verifying {stem}: SSIR markdown projection + compliance/quality report")
    _ssir, report = parse_csm_with_report(canonical)
    report.write_json(verify_path)
    document = json.loads(paths["ssir"].read_text(encoding="utf-8")) if paths["ssir"].is_file() else _ssir
    paths["render_md"].write_text(
        render_csm(document, asset_base=asset_base_for(paths["render_md"], docroot)),
        encoding="utf-8",
        newline="\n",
    )
    # render.html 与 render.md 同一 SSIR、同一批次写出（GEN-130 结构投影）。
    paths["render_html"].write_text(
        render_html(document, asset_base=asset_base_for(paths["render_html"], docroot)),
        encoding="utf-8",
        newline="\n",
    )
    _log(f"Reports: {verify_path} / {paths['render_md']}")
    print(json.dumps({"documentId": _ssir.get("id") or stem, "verify": str(verify_path),
                      "renderMd": str(paths["render_md"]), "renderHtml": str(paths["render_html"]),
                      "overallStatus": report.overall_status}, ensure_ascii=False))

    source_pdf = args.source_pdf
    if source_pdf is None:
        default_pdf = ROOT / "corpus" / "golden" / f"{stem}.pdf"
        kept_pdf = Path(paths["source"]) if paths["source"].is_file() else None
        source_pdf = default_pdf if default_pdf.is_file() else kept_pdf
    if args.no_pdf_comparison:
        _log("PDF comparison skipped (--no-pdf-comparison)")
    elif source_pdf is None or not Path(source_pdf).is_file():
        _log("No source PDF available; skipping the PDF layout/text comparison")
    elif not paths["render_pdf"].is_file():
        _log(f"No rendered PDF at {paths['render_pdf']}; skipping the PDF comparison")
    else:
        compare(Path(source_pdf), paths["render_pdf"], paths["render_comparison"])
        _log(f"Generated PDF comparison: {paths['render_comparison']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
