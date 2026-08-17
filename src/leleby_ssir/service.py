"""Public conversion service used by the CLI and future HTTP adapter."""

from __future__ import annotations

from pathlib import Path

from .builder import SSIRBuilder
from .exporters import json_bytes, turtle_text
from .parser import CSMParser
from .report import ConversionReport
from .validation import validate_ssir


def validate_csm(path: str | Path, strict: bool = False):
    return CSMParser(strict=strict).read(path)


def parse_csm_with_report(path: str | Path, strict: bool = False) -> tuple[dict, ConversionReport]:
    document = CSMParser(strict=strict).read(path)
    ssir = SSIRBuilder().build(document)
    validate_ssir(ssir)
    return ssir, ConversionReport.completed(document, ssir["id"])


def parse_csm(path: str | Path, strict: bool = False) -> dict:
    return parse_csm_with_report(path, strict=strict)[0]


def write_output(
    path: str | Path,
    output: str | Path,
    output_format: str = "json",
    strict: bool = False,
    report: str | Path | None = None,
) -> tuple[dict, ConversionReport]:
    ssir, conversion_report = parse_csm_with_report(path, strict=strict)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        target.write_bytes(json_bytes(ssir))
    elif output_format == "ttl":
        target.write_text(turtle_text(ssir), encoding="utf-8")
    else:
        raise ValueError(f"unsupported output format: {output_format}")
    report_target = Path(report) if report is not None else Path(f"{target}.conversion-report.json")
    conversion_report.write_json(report_target)
    return ssir, conversion_report
