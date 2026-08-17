"""Command line interface for CSM validation and SSIR conversion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .parser import CSMError
from .service import validate_csm, write_output
from .validation import SSIRValidationError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ssir", description="Parse Canonical SSIR Markdown into SSIR")
    command = parser.add_subparsers(dest="command", required=True)
    csm = command.add_parser("csm", help="CSM Markdown commands")
    csm_command = csm.add_subparsers(dest="csm_command", required=True)
    validate = csm_command.add_parser("validate", help="validate a CSM file")
    validate.add_argument("--input", required=True, type=Path)
    validate.add_argument("--strict", action="store_true", help="treat recoverable warnings as errors")
    parse = csm_command.add_parser("parse", help="convert CSM to SSIR")
    parse.add_argument("--input", required=True, type=Path)
    parse.add_argument("--output", required=True, type=Path)
    parse.add_argument("--format", choices=("json", "ttl"), default="json")
    parse.add_argument("--report", type=Path, help="conversion report path; defaults beside --output")
    parse.add_argument("--strict", action="store_true", help="reject recoverable input issues")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.csm_command == "validate":
            document = validate_csm(args.input, strict=args.strict)
            for warning in document.warnings:
                print(f"warning: {warning}", file=sys.stderr)
            print(json.dumps({"valid": True, "warnings": len(document.warnings), "convertible": True}, ensure_ascii=False))
            return 0
        ssir, report = write_output(args.input, args.output, args.format, strict=args.strict, report=args.report)
        report_path = args.report or Path(f"{args.output}.conversion-report.json")
        print(json.dumps({"output": str(args.output), "documentId": ssir["id"], "format": args.format, "report": str(report_path), "status": report.overall_status}, ensure_ascii=False))
        return 0
    except (CSMError, SSIRValidationError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
