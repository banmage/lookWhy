"""Command line interface for CSM validation and SSIR conversion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .parser import CSMError
from .service import parse_csm, validate_csm, write_output
from .validation import SSIRValidationError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ssir", description="Parse Canonical SSIR Markdown into SSIR")
    command = parser.add_subparsers(dest="command", required=True)
    csm = command.add_parser("csm", help="CSM Markdown commands")
    csm_command = csm.add_subparsers(dest="csm_command", required=True)
    validate = csm_command.add_parser("validate", help="validate a CSM file")
    validate.add_argument("--input", required=True, type=Path)
    parse = csm_command.add_parser("parse", help="convert CSM to SSIR")
    parse.add_argument("--input", required=True, type=Path)
    parse.add_argument("--output", required=True, type=Path)
    parse.add_argument("--format", choices=("json", "ttl"), default="json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.csm_command == "validate":
            document = validate_csm(args.input)
            notices = document.metadata.get("extensions", {}).get("quality-notices", [])
            notice_messages = [
                "[{code}/{severity}] {message}".format(
                    code=notice.get("code", "CSM"),
                    severity=notice.get("severity", "warning"),
                    message=notice.get("message", ""),
                )
                for notice in notices
                if isinstance(notice, dict)
            ]
            for warning in [*document.warnings, *notice_messages]:
                print(f"warning: {warning}", file=sys.stderr)
            print(json.dumps({"valid": True, "warnings": len(document.warnings) + len(notice_messages)}, ensure_ascii=False))
            return 0
        ssir = write_output(args.input, args.output, args.format)
        print(json.dumps({"output": str(args.output), "documentId": ssir["id"], "format": args.format}, ensure_ascii=False))
        return 0
    except (CSMError, SSIRValidationError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
