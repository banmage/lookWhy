#!/usr/bin/env python3
"""Verify multi-version management of the same standard across pipeline docroots.

Checks that two (or more) editions of one standard number coexist as distinct,
fully processed documents under the v2.0 stage layout (naming_specification.txt):

  1. ID independence      — each edition derives its own STANDARD_ID (year-suffixed)
  2. Pipeline completeness— all stage artifacts present, manifest status completed
  3. Metadata identity    — standardNumber/title per edition, no cross-contamination
  4. Version relationship — newer edition SSIR `replaces` == older edition number,
                            rendered on the PDF cover as "代替： …"
  5. Roundtrip integrity  — identity/structure/content/semantic layers pass

Usage:
  .venv/bin/python tools/verify_standard_versions.py \\
      --docroot out/mineru/gbt-23132-2008 --docroot out/mineru/gbt-23132-2024
  (order = chronological: oldest first; the last docroot is treated as the
   newest edition and must declare the replaces relationship)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import pymupdf  # PyMuPDF 1.28+; falls back to fitz below
except ImportError:  # pragma: no cover
    import fitz as pymupdf  # type: ignore


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def norm_number(text: str) -> str:
    """Whitespace/dash-insensitive standard-number comparison (封面原文可能
    "GB/T 23132" 与 "GB/T23132" 两种排法、一字线/半字线混用)."""
    return re.sub(r"\s+", "", text).replace("—", "-")


def artifact_exists(root: Path, rel: str) -> bool:
    return (root / rel).is_file()


def cover_replaces_text(render_pdf: Path) -> str:
    """Extract the 代替 line from the rendered PDF cover page (first page)."""
    try:
        with pymupdf.open(render_pdf) as doc:
            text = doc[0].get_text()
    except Exception:
        return ""
    for line in text.splitlines():
        if "代替" in line:
            return line.strip()
    return ""


def section_outline(ssir: dict, max_depth: int = 1) -> list[str]:
    """Collect numbered section titles up to max_depth (chapter-level by default)."""

    def walk(node: dict, depth: int, out: list[str]) -> None:
        for child in node.get("children", []) or []:
            ntype = child.get("nodeType", "")
            if ntype in ("section", "clause", "annex"):
                number = ""
                title = ""
                for ce in child.get("contentElements", []) or []:
                    if ce.get("kind") == "heading":
                        number = ce.get("number", "") or ""
                        title = ce.get("text", "") or ""
                        break
                label = (f"{number} {title}").strip()
                if label:
                    out.append(label)
                if depth < max_depth:
                    walk(child, depth + 1, out)
            else:
                walk(child, depth, out)

    out: list[str] = []
    walk(ssir.get("structuralRoot", {}), 0, out)
    return out


def check_document(root: Path, issues: list[str], passed: list[str]) -> dict:
    manifest = load_json(root / "manifest.json")
    doc_id: str = manifest["documentId"]
    print(f"\n=== {doc_id}  ({root}) ===")

    # 1. Pipeline completeness (naming_specification.txt §4.2)
    pipeline = manifest.get("pipeline", {})
    required = [
        ("raw", "01_extract/raw.md"),
        ("canonical", "02_canonical/canonical.md"),
        ("ssir", "03_ssir/ssir.json"),
        ("render", "04_render/render.pdf"),
        ("renderMd", "04_render/render.md"),
        ("verify", "05_verify/verify.json"),
        ("roundtrip", "05_verify/roundtrip.json"),
    ]
    for key, _ in required:
        rel = pipeline.get(key, "")
        if rel and artifact_exists(root, rel):
            passed.append(f"{doc_id}: artifact {rel}")
        else:
            issues.append(f"{doc_id}: MISSING pipeline artifact {key} -> {rel!r}")

    status = manifest.get("status", "")
    if status == "completed":
        passed.append(f"{doc_id}: manifest.status completed")
    else:
        issues.append(f"{doc_id}: manifest.status={status!r} (expected completed)")

    # 2. Metadata identity
    ssir_path = root / pipeline.get("ssir", "")
    ssir = load_json(ssir_path)
    meta = ssir.get("metadata", {})
    common = meta.get("common", {})
    standard = meta.get("standard", {})
    result = {
        "documentId": doc_id,
        "manifestNumber": manifest.get("standardNumber", ""),
        "title": manifest.get("title", ""),
        "ssirNumber": standard.get("standardNumber", ""),
        "ssirTitle": standard.get("chineseTitle", common.get("title", "")),
        "replaces": standard.get("replaces", ""),
        "publicationDate": common.get("publicationDate", ""),
        "effectiveDate": common.get("effectiveDate", ""),
        "ics": standard.get("ics", ""),
        "ccs": standard.get("ccs", ""),
        "ssirId": ssir.get("id", ""),
    }
    print(f"  standardNumber : {result['ssirNumber']}")
    print(f"  title          : {result['ssirTitle']}")
    print(f"  replaces       : {result['replaces'] or '(none)'}")
    print(f"  发布/实施      : {result['publicationDate']} / {result['effectiveDate']}")

    # 封面必备字段（GBT-C01）：发布机构缺失会渲染出无机构封面。
    if common.get("issuer"):
        passed.append(f"{doc_id}: issuer {common['issuer']}")
        result["issuer"] = common["issuer"]
    else:
        issues.append(f"{doc_id}: 封面发布机构 issuer 缺失（GBT-C01）")

    # 3. Roundtrip integrity
    roundtrip_path = root / pipeline.get("roundtrip", "")
    if roundtrip_path.is_file():
        rt = load_json(roundtrip_path)
        layers = rt.get("layerStatus", {})
        if rt.get("passed") is True:
            passed.append(f"{doc_id}: roundtrip overall pass")
        else:
            issues.append(f"{doc_id}: roundtrip NOT passed ({rt.get('overallStatus')})")
        for layer, st in layers.items():
            if st != "pass":
                issues.append(f"{doc_id}: roundtrip layer {layer}={st}")
        result["roundtripLayers"] = layers

    # 4. Render comparison
    comp_path = root / "04_render" / f"{doc_id}.render-comparison.json"
    if comp_path.is_file():
        comp = load_json(comp_path)
        result["renderPages"] = comp.get("generated", {}).get("pageCount")
        result["originalPages"] = comp.get("original", {}).get("pageCount")
        print(f"  渲染页数        : {result['originalPages']} -> {result['renderPages']}")

    # 5. Cover 代替 line in the rendered PDF
    render_pdf = root / pipeline.get("render", "")
    if render_pdf.is_file():
        rep = cover_replaces_text(render_pdf)
        result["coverReplaces"] = rep
        print(f"  封面代替行      : {rep or '(none)'}")

    # 6. Chapter outline (for the version diff table)
    result["outline"] = section_outline(ssir)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--docroot", action="append", required=True,
        help="Pipeline document root (order = chronological, oldest first). Repeatable.",
    )
    args = parser.parse_args()

    roots = [Path(p) for p in args.docroot]
    for r in roots:
        if not (r / "manifest.json").is_file():
            print(f"FATAL: no manifest.json in {r}", file=sys.stderr)
            return 2

    issues: list[str] = []
    passed: list[str] = []
    results = [check_document(r, issues, passed) for r in roots]

    print("\n\n=== 跨版本关系核查（同一标准多版本管理）===")
    ids = [r["documentId"] for r in results]
    nums = [r["ssirNumber"] for r in results]

    # Distinct IDs
    if len(set(ids)) == len(ids):
        passed.append(f"ID 相互独立：{', '.join(ids)}")
    else:
        issues.append(f"ID 冲突：{ids}")

    # Same standard number stem (whitespace-insensitive: 封面原文可能
    # "GB/T 23132" 或 "GB/T23132" 两种排法)
    stems = {norm_number(n.split("-")[0]) for n in nums if n}
    if len(stems) == 1:
        passed.append(f"同一标准号前缀：{stems.pop()}")
    else:
        issues.append(f"标准号前缀不一致：{nums}")

    # Newest edition declares the replaces relationship to the previous edition
    if len(results) >= 2:
        older, newer = results[-2], results[-1]
        expected = norm_number(older["ssirNumber"])
        actual = norm_number(newer["replaces"])
        if actual and actual == expected:
            passed.append(f"版本关系：{newer['documentId']} replaces {older['documentId']} ({newer['replaces']})")
        else:
            issues.append(
                f"版本关系缺失/不符：{newer['documentId']} replaces={newer['replaces']!r}, "
                f"expected {older['ssirNumber']!r} (来自 {older['documentId']})"
            )
        # Cover rendering of the replaces line
        if newer.get("coverReplaces") and expected in norm_number(newer["coverReplaces"]):
            passed.append(f"封面渲染代替行：{newer['coverReplaces']}")
        else:
            issues.append(f"封面未渲染代替行（{newer['documentId']}）")

    # Same title across versions (same standard)
    titles = {r["ssirTitle"] for r in results if r["ssirTitle"]}
    if len(titles) == 1:
        passed.append(f"两版本中文标题一致：{titles.pop()}")
    elif len(titles) > 1:
        issues.append(f"中文标题不一致（可能确为更名，需人工确认）：{titles}")

    # Version outline diff table
    print("\n=== 版本章节对照（章级）===")
    outlines = [r["outline"] for r in results]
    max_rows = max(len(o) for o in outlines)
    for i in range(max_rows):
        cells = []
        for o in outlines:
            cells.append(o[i] if i < len(o) else "")
        print("  | " + " | ".join(f"{c:<28}" for c in cells))

    print("\n=== 核查结果 ===")
    for p in passed:
        print(f"  PASS  {p}")
    for iss in issues:
        print(f"  FAIL  {iss}")
    print(f"\n{len(passed)} passed, {len(issues)} failed")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
