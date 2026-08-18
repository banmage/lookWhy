#!/usr/bin/env python3
"""Batch-verify CSM Std0 -> SSIR1 -> CSM Std1 -> SSIR2 round trips."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from leleby_ssir.service import round_trip_csm


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", help="CSM Std0 file; repeat as needed")
    parser.add_argument(
        "--examples-dir",
        type=Path,
        help="verify every *.csm.md in this directory (used when --input is absent)",
    )
    parser.add_argument("--output-dir", type=Path, required=True, help="directory for Std1 and JSON reports")
    arguments = parser.parse_args()
    if not arguments.input and not arguments.examples_dir:
        parser.error("one of --input or --examples-dir is required")
    return arguments


def main() -> int:
    arguments = _arguments()
    paths = list(arguments.input or [])
    if arguments.examples_dir:
        paths.extend(sorted(arguments.examples_dir.glob("*.csm.md")))
    paths = list(dict.fromkeys(paths))
    arguments.output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for path in paths:
        stem = path.name.removesuffix(".csm.md")
        std1 = arguments.output_dir / f"{stem}.std1.csm.md"
        report_path = arguments.output_dir / f"{stem}.roundtrip-report.json"
        try:
            _, _, report = round_trip_csm(path, std1)
            report.write_json(report_path)
            results.append({"input": str(path), "std1": str(std1), "report": str(report_path), "passed": report.passed})
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
