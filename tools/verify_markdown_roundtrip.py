#!/usr/bin/env python3
"""Batch-verify CSM canonical -> SSIR -> CSM render.md -> verify round trips."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from leleby_ssir.naming import artifact_id
from leleby_ssir.service import round_trip_csm


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", help="canonical CSM file; repeat as needed")
    parser.add_argument(
        "--examples-dir",
        type=Path,
        help="verify every *.canonical.md (legacy *.csm.md) in this directory (used when --input is absent)",
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="directory for render.md and JSON reports")
    arguments = parser.parse_args()
    if not arguments.input and not arguments.examples_dir:
        parser.error("one of --input or --examples-dir is required")
    return arguments


def main() -> int:
    arguments = _arguments()
    paths = list(arguments.input or [])
    if arguments.examples_dir:
        paths.extend(sorted(arguments.examples_dir.glob("*.canonical.md")))
        paths.extend(sorted(arguments.examples_dir.glob("*.csm.md")))  # 兼容旧夹具
    paths = list(dict.fromkeys(paths))
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for path in paths:
        stem = artifact_id(path.name)
        render_md = arguments.output_dir / f"{stem}.render.md"
        report_target = arguments.output_dir / f"{stem}.roundtrip.json"
        try:
            _, _, report = round_trip_csm(path, render_md)
            report.write_json(report_target)
            results.append({"input": str(path), "renderMd": str(render_md), "report": str(report_target), "passed": report.passed})
        except Exception as exc:  # Keep batch diagnostics for every supplied baseline.
            results.append({"input": str(path), "passed": False, "error": str(exc)})
    summary = {
        "total": len(results),
        "passed": sum(1 for result in results if result.get("passed")),
        "failed": sum(1 for result in results if not result.get("passed")),
        "results": results,
    }
    summary_path = arguments.output_dir / "roundtrip-summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": str(summary_path), **{key: summary[key] for key in ("total", "passed", "failed")}}, ensure_ascii=False))
    return 0 if not summary["failed"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
