"""Command line interface for CSM validation and SSIR conversion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .naming import REP_NORMALIZE_REPORT, REP_PARSE_REPORT, REP_RENDER_REPORT, report_path
from .parser import CSMError
from .service import normalize_csm, validate_csm, write_output
from .validation import SSIRValidationError


def _toc_depth(value: str) -> int | None:
    if value.lower() == "all":
        return None
    try:
        depth = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer or 'all'") from exc
    if depth < 1:
        raise argparse.ArgumentTypeError("must be a positive integer or 'all'")
    return depth


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ssir", description="Parse Canonical SSIR Markdown into SSIR")
    command = parser.add_subparsers(dest="command", required=True)
    csm = command.add_parser("csm", help="CSM Markdown commands")
    csm_command = csm.add_subparsers(dest="csm_command", required=True)
    validate = csm_command.add_parser("validate", help="validate a CSM file")
    validate.add_argument("--input", required=True, type=Path)
    validate.add_argument("--strict", action="store_true", help="treat recoverable warnings as errors")
    normalize = csm_command.add_parser("normalize", help="repair raw Markdown and write a canonical CSM baseline")
    normalize.add_argument("--input", required=True, type=Path, help="raw user Markdown input")
    normalize.add_argument("--canonical-output", dest="canonical_output", required=True, type=Path, help="corrected canonical CSM output path")
    normalize.add_argument("--report", type=Path, help="normalize report path; defaults beside --canonical-output")
    normalize.add_argument("--strict", action="store_true", help="reject recoverable input issues")
    parse = csm_command.add_parser("parse", help="convert CSM to SSIR")
    parse.add_argument("--input", required=True, type=Path)
    parse.add_argument("--output", required=True, type=Path)
    parse.add_argument("--format", choices=("json", "ttl"), default="json")
    parse.add_argument("--report", type=Path, help="parse report path; defaults beside --output")
    parse.add_argument("--strict", action="store_true", help="reject recoverable input issues")
    project = csm_command.add_parser("project", help="project SSIR as the standard Markdown equivalent (no directives, no HTML comments)")
    project.add_argument("--input", required=True, type=Path, help="canonical CSM Markdown or SSIR JSON input")
    project.add_argument("--output", required=True, type=Path, help="Markdown projection output path")
    pdf = command.add_parser("pdf", help="extract PDFs or render validated SSIR JSON")
    pdf_command = pdf.add_subparsers(dest="pdf_command", required=True)
    extract = pdf_command.add_parser("extract", help="extract a PDF into CSM Markdown")
    extract.add_argument("--input", required=True, type=Path, help="PDF input")
    extract.add_argument("--output", required=True, type=Path, help="CSM Markdown output")
    extract.add_argument("--backend", choices=("auto", "mineru", "pymupdf"), default="auto")
    extract.add_argument("--report", type=Path)
    extract.add_argument("--sidecar", type=Path)
    render = pdf_command.add_parser("render", help="render SSIR JSON to PDF")
    render.add_argument("--input", required=True, type=Path, help="validated SSIR JSON input")
    render.add_argument("--output", required=True, type=Path, help="PDF output path")
    render.add_argument("--profile", type=Path, help="rendering profile YAML")
    render.add_argument("--report", type=Path, help="rendering report path")
    render.add_argument("--toc-depth", type=_toc_depth, default=2, metavar="LEVEL|all", help="maximum numbered TOC level (default: 2; use all to expand every level)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if getattr(args, "command", None) == "pdf" and args.pdf_command == "extract":
            from .pdf_extractor import extract_pdf_to_csm
            report = extract_pdf_to_csm(args.input, args.output, backend=args.backend, report=args.report, sidecar=args.sidecar)
            print(json.dumps({"output": str(args.output), "backend": report.backend, "pages": report.page_count, "status": report.status, "warnings": len(report.warnings), "sidecar": report.sidecar_file}, ensure_ascii=False))
            return 0
        if getattr(args, "command", None) == "pdf" and args.pdf_command == "render":
            from .pdf_renderer import render_pdf_file
            report = render_pdf_file(args.input, args.output, profile_path=args.profile, toc_depth=args.toc_depth)
            report_path_arg = args.report or report_path(args.output, REP_RENDER_REPORT)
            report.write_json(report_path_arg)
            print(json.dumps({"output": str(args.output), "report": str(report_path_arg), "pageCount": report.page_count, "warnings": len(report.warnings)}, ensure_ascii=False))
            return 0
        if args.csm_command == "validate":
            document = validate_csm(args.input, strict=args.strict)
            for warning in document.warnings:
                print(f"warning: {warning}", file=sys.stderr)
            print(json.dumps({"valid": True, "warnings": len(document.warnings), "convertible": True}, ensure_ascii=False))
            return 0
        if args.csm_command == "project":
            from .csm_renderer import render_csm
            from .html_renderer import render_html
            from .service import parse_csm

            source = args.input
            if source.suffix.lower() == ".json":
                document = json.loads(source.read_text(encoding="utf-8"))
            else:
                document = parse_csm(source)
            # 产物形态按输出后缀判定（GEN-130）：.html → 结构投影（框/分栏/合并），
            # 其他 → 标准 markdown 投影。同一 SSIR，两条投影互不替代。
            text = render_html(document) if args.output.suffix.lower() in {".html", ".htm"} else render_csm(document)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8", newline="\n")
            print(json.dumps({"output": str(args.output), "lines": len(text.splitlines()),
                              "bytes": len(text.encode("utf-8"))}, ensure_ascii=False))
            return 0
        if args.csm_command == "normalize":
            ssir, report = normalize_csm(args.input, args.canonical_output, strict=args.strict)
            report_path_arg = args.report or report_path(args.canonical_output, REP_NORMALIZE_REPORT)
            report.write_json(report_path_arg)
            print(json.dumps({"canonical": str(args.canonical_output), "documentId": ssir["id"], "report": str(report_path_arg), "status": report.overall_status}, ensure_ascii=False))
            return 0
        ssir, report = write_output(args.input, args.output, args.format, strict=args.strict, report=args.report)
        report_path_arg = args.report or report_path(args.output, REP_PARSE_REPORT)
        print(json.dumps({"output": str(args.output), "documentId": ssir["id"], "format": args.format, "report": str(report_path_arg), "status": report.overall_status}, ensure_ascii=False))
        return 0
    except (CSMError, SSIRValidationError, OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
