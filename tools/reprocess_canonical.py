#!/usr/bin/env python3
"""Re-run the downstream stages from an existing curated canonical CSM.

“半程处理程序”（新主程序，尽量复用 tools/mineru_full_standard.py 的既有函数）：
以 ``out/mineru/<ID>/02_canonical/<ID>.canonical.md``（唯一人工可编辑的权威基线，
见 AGENTS.md §2）为输入，跳过 抽取/合并/normalize——绝不重跑 normalize、绝不覆盖
curated canonical——直接重跑 parse → roundtrip → render（PDF + 内容等价 docx）→
（源 PDF 存在时）PDF 版面印记恢复与渲染对比，最后刷新 ``manifest.json``。

复用关系（不重复实现）：
- ``mineru_full_standard._stage_paths``：阶段目录与产物命名（naming_specification §4）；
- ``mineru_full_standard._stamp_example_styles/_stamp_figure_source_sizes/
  _stamp_side_by_side_layout``：PDF 源几何印记恢复（规则对应见各自 docstring）；
- ``mineru_full_standard._post_parse_verify_render``：roundtrip → render（PDF+docx）
  → compare → manifest 公共尾部（规则对应：verify=GEN-051/090/091，render=GEN-070—076）；
- ``mineru_full_standard._load_json``：pipeline-state / manifest 读取。

本文件只新增 ``main`` 与 ``_resolve_canonical`` 两个函数。

用法：
    .venv/bin/python tools/reprocess_canonical.py GB_T_1.1-2020
    .venv/bin/python tools/reprocess_canonical.py \\
        --input out/mineru/GB_T_1.1-2020/02_canonical/GB_T_1.1-2020.canonical.md

退出码：0 成功；2 失败（roundtrip 返回 3 = SSIR 与 Verify 不等价/关键损失，
与全流程工具一致：记录结果但不算失败）。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
for _path in (str(TOOLS), str(ROOT / "src")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# 复用全流程工具的阶段路径 / 版面印记 / 尾部 roundtrip-render-manifest（同仓库内稳定私有接口）。
import mineru_full_standard as mfs  # noqa: E402


def _resolve_canonical(raw: str | Path, output_dir: Path | None) -> tuple[Path, Path, str]:
    """Return (docroot, canonical, stem) for an ID or a canonical path/directory.

    - 裸 ID（如 ``GB_T_1.1-2020``，无目录/后缀）→ ``out/mineru/<ID>/02_canonical/<ID>.canonical.md``；
    - ``*.canonical.md`` 文件路径或含唯一该文件的目录路径。
    """
    path = Path(raw)
    if path.is_dir():
        matches = sorted(path.glob("*.canonical.md"))
        if len(matches) != 1:
            raise RuntimeError(f"{path} 下应有且仅有 1 份 *.canonical.md，实际 {len(matches)} 份")
        canonical = matches[0]
    elif path.is_file():
        if not path.name.endswith(".canonical.md"):
            raise RuntimeError(f"输入应为 canonical CSM（*.canonical.md）：{path}")
        canonical = path
    else:
        canonical = ROOT / "out" / "mineru" / path.name / "02_canonical" / f"{path.name}.canonical.md"
        if not canonical.is_file():
            raise RuntimeError(
                f"找不到 {canonical}\n"
                "  先跑 .venv/bin/python tools/mineru_full_standard.py <ID> 生成，"
                "或直接传 canonical.md 文件/目录路径。"
            )
    stem = canonical.name[: -len(".canonical.md")]
    if output_dir is not None:
        docroot = output_dir
    elif canonical.parent.name == "02_canonical":
        docroot = canonical.parent.parent
    else:
        raise RuntimeError(f"{canonical} 不在 <docroot>/02_canonical/ 布局内，请显式 --output-dir")
    return docroot, canonical, stem


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Re-run the downstream stages from an existing curated canonical CSM "
            "(parse -> roundtrip -> render -> compare -> manifest) without re-running "
            "extract/merge/normalize, so a hand-edited canonical is preserved as-is."
        )
    )
    parser.add_argument(
        "file", nargs="?", type=str, default=None,
        help="标准 ID（默认在 out/mineru/<ID>/02_canonical/<ID>.canonical.md 查找，"
             "同 mineru_full_standard 用法），或 canonical.md 文件/目录路径",
    )
    parser.add_argument("--input", type=Path, help="canonical CSM 输入（与位置参数二选一）")
    parser.add_argument("--output-dir", type=Path, help="文档根目录（默认 canonical 所在 02_canonical 的父目录）")
    parser.add_argument("--output-stem", type=str, help="输出文件名前缀（默认取 canonical 的 ID）")
    parser.add_argument("--toc-depth", default="2", help="渲染目次最大层数（正整数或 all；默认 2）")
    parser.add_argument("--no-roundtrip", action="store_true", help="跳过回旋验证")
    parser.add_argument("--no-render", action="store_true", help="跳过 PDF/docx 渲染与对比")
    args = parser.parse_args()
    if not args.input and not args.file:
        parser.error("an input is required: pass a standard ID (e.g. GB_T_1.1-2020) or --input PATH")

    try:
        docroot, canonical, stem = _resolve_canonical(args.input or args.file, args.output_dir)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.output_stem:
        stem = args.output_stem
    paths = mfs._stage_paths(docroot, stem)
    for stage_path in (paths["ssir"], paths["render_pdf"], paths["render_md"], paths["render_docx"], paths["verify"]):
        stage_path.parent.mkdir(parents=True, exist_ok=True)

    # provenance 保留：pipeline-state/manifest 里的 created/sha/title/number/原输入
    state = mfs._load_json(docroot / "pipeline-state.json", {})
    old_manifest = mfs._load_json(docroot / "manifest.json", {})
    state.setdefault("title", old_manifest.get("title", ""))
    state.setdefault("number", old_manifest.get("standardNumber", ""))
    state.setdefault("createdAt", old_manifest.get("created"))
    if not state.get("sourceSha256") and old_manifest.get("source", {}).get("checksum", "").startswith("sha256:"):
        state["sourceSha256"] = old_manifest["source"]["checksum"][len("sha256:"):]
    original = state.get("input")
    source = Path(original) if original and Path(original).is_file() else None
    if source is None:
        for candidate in (paths["source"], docroot / "00_source" / f"{stem}.source.docx"):
            if candidate.is_file():
                source = candidate
                break
    if source is None:
        source = canonical
    args.input_kind = "pdf" if source.suffix.lower() == ".pdf" else ("docx" if source.suffix.lower() in (".docx", ".doc") else "")
    args.input = source  # compare / 版面印记读源 PDF；manifest 保留原输入出处
    # 复用 mineru_full_standard._post_parse_verify_render 需要的其余命名空间属性
    args.output_dir = docroot
    args.output_stem = stem
    args.roundtrip = not args.no_roundtrip
    args.render = not args.no_render

    mfs._log(f"Input canonical: {canonical.resolve()}")
    mfs._log(f"Document root: {docroot.resolve()}")
    mfs._log("Stages: parse -> roundtrip -> render (PDF + docx) -> manifest")

    # parse canonical -> SSIR（normalize 已跳过，canonical 保持人工编辑原样）
    mfs._log("Parsing canonical CSM into SSIR JSON")
    ssir_exe = Path(sys.prefix) / "bin" / "ssir"
    parse_cmd = [
        str(ssir_exe), "csm", "parse",
        "--input", str(canonical),
        "--output", str(paths["ssir"]),
        "--report", str(paths["parse_report"]),
    ]
    if subprocess.run(parse_cmd, cwd=ROOT).returncode:
        print("SSIR parsing needs review; check the canonical CSM and the parse report.", file=sys.stderr)
        return 2
    mfs._log(f"SSIR JSON written: {paths['ssir']}")

    # PDF 源才有的版面印记恢复（复用原函数；无源 PDF 时无几何可读，跳过）
    if args.input_kind == "pdf":
        mfs._stamp_example_styles(paths["ssir"], args.input)
        mfs._stamp_figure_source_sizes(paths["ssir"], args.input)
        parts_dir = docroot / "parts"
        if parts_dir.is_dir():
            mfs._stamp_side_by_side_layout(paths["ssir"], parts_dir)
    else:
        mfs._log("No source PDF present; skipping PDF-geometry stamps (example style / figure sizes / side-by-side)")

    # 公共尾部（复用原函数）：roundtrip -> render（PDF+docx）-> compare -> manifest
    try:
        mfs._post_parse_verify_render(args, state, paths, ssir=paths["ssir"])
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    mfs._log("Workflow completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
