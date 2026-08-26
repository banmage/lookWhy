"""Public conversion service used by the CLI and future HTTP adapter."""

from __future__ import annotations

from pathlib import Path

from .builder import SSIRBuilder
from .compliance import compliance_issues, verify_compliance
from .csm_normalizer import write_canonical
from .csm_renderer import write_csm
from .exporters import json_bytes, turtle_text
from .naming import REP_PARSE_REPORT, report_path
from .parser import CSMParser
from .report import ConversionReport
from .roundtrip import RoundTripReport, compare_ssir
from .validation import validate_ssir


def validate_csm(path: str | Path, strict: bool = False):
    return CSMParser(strict=strict).read(path)


def parse_csm_with_report(path: str | Path, strict: bool = False) -> tuple[dict, ConversionReport]:
    document = CSMParser(strict=strict).read(path)
    ssir = SSIRBuilder().build(document)
    validate_ssir(ssir)
    report = ConversionReport.completed(document, ssir["id"])
    # GEN-090 / 逐条规则验证：把规则包（GEN → GBT → P10）的违规发现
    # 合并进转换报告，must 违规记 error、should 记 warning。
    compliance = verify_compliance(ssir, metadata=document.metadata)
    report.compliance = compliance.to_dict()
    report.issues.extend(compliance_issues(compliance))
    return ssir, report


def parse_csm(path: str | Path, strict: bool = False) -> dict:
    return parse_csm_with_report(path, strict=strict)[0]


def normalize_csm(
    path: str | Path,
    canonical_output: str | Path,
    strict: bool = False,
) -> tuple[dict, ConversionReport]:
    """Safely repair raw Markdown and persist its canonical CSM baseline."""
    document = CSMParser(strict=strict).read(path)
    ssir = SSIRBuilder().build(document)
    validate_ssir(ssir)
    write_canonical(document, canonical_output)
    return ssir, ConversionReport.completed(document, ssir["id"])


def round_trip_csm(
    path: str | Path,
    render_md_output: str | Path,
    strict: bool = False,
    verify_output: str | Path | None = None,
) -> tuple[dict, dict, RoundTripReport]:
    """Execute CSM(canonical) -> SSIR -> CSM(render.md) -> verify and compare semantic views.

    ``render_md_output`` 是 SSIR 确定性渲染回的 CSM（04_render 中间产物，原 Std1）；
    ``verify_output`` 可选，用于持久化从 ``render.md`` 再解析得到的 SSIR
    （05_verify 的 verify.json，原 SSIR2），供回环报告引用。
    """
    source = Path(path)
    target = Path(render_md_output)
    ssir1 = parse_csm(source, strict=strict)
    write_csm(ssir1, target)
    ssir2 = parse_csm(target, strict=strict)
    if verify_output is not None:
        verify_target = Path(verify_output)
        verify_target.parent.mkdir(parents=True, exist_ok=True)
        verify_target.write_bytes(json_bytes(ssir2))
    report = compare_ssir(ssir1, ssir2, str(source), str(target))
    return ssir1, ssir2, report


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
    report_target = Path(report) if report is not None else report_path(target, REP_PARSE_REPORT)
    conversion_report.write_json(report_target)
    return ssir, conversion_report
