"""Public conversion service used by the CLI and future HTTP adapter."""

from __future__ import annotations

from pathlib import Path

from .builder import SSIRBuilder
from .exporters import json_bytes, turtle_text
from .parser import CSMParser
from .validation import validate_ssir


def validate_csm(path: str | Path):
    return CSMParser().read(path)


def parse_csm(path: str | Path) -> dict:
    document = CSMParser().read(path)
    ssir = SSIRBuilder().build(document)
    validate_ssir(ssir)
    return ssir


def write_output(path: str | Path, output: str | Path, output_format: str = "json") -> dict:
    ssir = parse_csm(path)
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        target.write_bytes(json_bytes(ssir))
    elif output_format == "ttl":
        target.write_text(turtle_text(ssir), encoding="utf-8")
    else:
        raise ValueError(f"unsupported output format: {output_format}")
    return ssir
