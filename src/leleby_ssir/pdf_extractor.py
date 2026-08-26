"""PDF -> CSM Markdown extraction adapters.

MinerU is the preferred backend.  PyMuPDF is intentionally kept as a
deterministic text-layer fallback for development and for PDFs MinerU cannot
process; fallback output is marked as requiring review.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


from .mineru_html import convert_mineru_markup, formula_assets_index
from .naming import REP_EXTRACT_REPORT, REP_PROVENANCE, report_path, standard_number_from_text


@dataclass(slots=True)
class PdfExtractionReport:
    input_file: str
    output_file: str
    backend: str
    status: str
    page_count: int
    warnings: list[dict[str, Any]] = field(default_factory=list)
    sidecar_file: str | None = None

    def write_json(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _find_mineru() -> str | None:
    # Console entry points installed into the active virtual environment are
    # not necessarily present in PATH when ``.venv/bin/ssir`` is invoked.
    virtualenv_bin = Path(sys.prefix) / "bin"
    for name in ("mineru", "magic-pdf"):
        local = virtualenv_bin / name
        if local.is_file() and local.stat().st_mode & 0o111:
            return str(local)
        found = shutil.which(name)
        if found:
            return found
    return None


def _usable_title(text: str, fallback: str) -> str:
    compact = " ".join(text.split())
    # Broken embedded CJK fonts often decode as repeated mathematical letters.
    if not compact or sum(1 for char in compact if "犀" <= char <= "犿") > 4:
        return fallback
    return compact[:180]


def _front_matter(number: str, title: str, source_name: str, backend: str) -> str:
    # Keep metadata scalar and quote values so extracted punctuation cannot
    # accidentally become YAML syntax.
    def q(value: str) -> str:
        return json.dumps(value, ensure_ascii=False)

    return "\n".join([
        "---",
        "csm-version: \"1.0\"",
        "document-type: standard",
        f"document-identifier: {q(number)}",
        f"standard-number: {q(number)}",
        f"title: {q(title)}",
        "language: zh-CN",
        "source:",
        "  mode: mineru-pdf" if backend == "mineru" else "  mode: pymupdf-pdf",
        f"  original-file-name: {q(source_name)}",
        "  provenance: pdf-sidecar",
        "extraction-backend: " + q(backend),
        "---",
        "",
    ])


def _pymupdf_extract(source: Path, target: Path, asset_dir: Path) -> tuple[str, list[dict[str, Any]], int, list[dict[str, Any]]]:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required for the fallback backend; install it in .venv") from exc
    doc = fitz.open(source)
    pages: list[str] = []
    anchors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for page_index, page in enumerate(doc, 1):
        blocks = page.get_text("blocks")
        page_lines: list[str] = [f"<!-- ssir:block id=\"pdf-page-{page_index}\" -->", f"## 第{page_index}页"]
        if not blocks:
            warnings.append({"code": "PDF-TEXT-001", "severity": "warning", "page": page_index, "message": "Page has no text layer; OCR/manual review required."})
            page_lines.append(f"<!-- ssir:unknown id=\"unknown-page-{page_index}\" -->\n[待复核：第{page_index}页无可提取文本]\n<!-- /ssir:unknown -->")
        for block_index, block in enumerate(blocks):
            x0, y0, x1, y1, raw, *_ = block
            text = " ".join(str(raw).split())
            if not text:
                continue
            block_id = f"pdf-{page_index}-{block_index + 1}"
            page_lines.extend([f"<!-- ssir:block id=\"{block_id}\" -->", text, ""])
            anchors.append({"id": block_id, "page": page_index, "bbox": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)], "text": text})
        pages.append("\n".join(page_lines).rstrip())
    if len(doc) and sum(len(p.get_text()) for p in doc) == 0:
        warnings.append({"code": "PDF-TEXT-002", "severity": "error", "message": "PDF has no extractable text; use MinerU/OCR backend."})
    first_text = " ".join(doc[0].get_text().split()) if len(doc) else ""
    number = standard_number_from_text(first_text, source.stem)
    title = _usable_title(first_text, number)
    body = _front_matter(number, title, source.name, "pymupdf") + f"# {title}\n\n" + "\n\n---\n\n".join(pages) + "\n"
    return body, anchors, len(doc), warnings


def _locate_mineru_markdown(root: Path) -> Path | None:
    candidates = sorted(root.rglob("*.md"), key=lambda p: p.stat().st_size, reverse=True)
    return candidates[0] if candidates else None


def _mineru_extract(source: Path, target: Path, asset_dir: Path, executable: str) -> tuple[str, list[dict[str, Any]], int, list[dict[str, Any]]]:
    work = target.parent / f".mineru-{target.stem}"
    work.mkdir(parents=True, exist_ok=True)
    # New MinerU reads mineru.json from the user config directory. The command
    # is run with the configured ModelScope model cache; no model is copied.
    is_modern = Path(executable).name == "mineru"
    if is_modern:
        command = [executable, "-p", str(source), "-o", str(work), "-b", "pipeline", "-m", "auto", "-l", "ch", "-f", "true", "-t", "true"]
        env = dict(os.environ)
        env["MINERU_MODEL_SOURCE"] = "local"
        env["MPLCONFIGDIR"] = str(work / ".matplotlib")
    else:
        # magic-pdf 1.3.x requires this file even for local inference.
        config_path = work / "magic-pdf.json"
        config_path.write_text(json.dumps({
            "device-mode": "cpu",
            "models-dir": str(work / "models"),
            "layout-config": {"model": "doclayout_yolo"},
            "table-config": {"enable": False},
            "formula-config": {"enable": False},
        }), encoding="utf-8")
        command = [executable, "-p", str(source), "-o", str(work), "-m", "auto"]
        env = dict(os.environ)
        env["MINERU_TOOLS_CONFIG_JSON"] = str(config_path)
    completed = subprocess.run(command, capture_output=True, text=True, check=False, env=env)
    if completed.returncode != 0:
        raise RuntimeError(f"MinerU failed ({completed.returncode}): {completed.stderr[-1000:]}")
    markdown = _locate_mineru_markdown(work)
    if markdown is None:
        diagnostics = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"MinerU completed but produced no Markdown file{': ' + diagnostics[-1000:] if diagnostics else ''}")
    raw = markdown.read_text(encoding="utf-8", errors="replace")
    # MinerU HTML 表格/图片路径统一适配为 CSM（与全流水线共用同一转换器，
    # 合并单元格以 table-merge 指令保留），provenance 哈希仍记原始抽取文本。
    raw_hash = hashlib.sha256(raw.encode()).hexdigest()
    raw = convert_mineru_markup(raw, "ext", formula_assets_index(markdown))
    # MinerU Markdown is preserved as content; CSM metadata is added around it.
    try:
        import fitz  # type: ignore
        pages = len(fitz.open(source))
    except Exception:
        pages = 0
    number = standard_number_from_text(raw[:2000], source.stem)
    title = _usable_title(next((line.lstrip("# ").strip() for line in raw.splitlines() if line.startswith("#")), ""), number)
    anchors = [{"id": "mineru-markdown", "source": str(markdown.relative_to(work)), "textSha256": raw_hash}]
    return _front_matter(number, title, source.name, "mineru") + f"# {title}\n\n" + raw.rstrip() + "\n", anchors, pages, []


def extract_pdf_to_csm(source: str | Path, output: str | Path, *, backend: str = "auto", report: str | Path | None = None, sidecar: str | Path | None = None) -> PdfExtractionReport:
    source_path, target = Path(source).resolve(), Path(output).resolve()
    if not source_path.is_file() or source_path.suffix.lower() != ".pdf":
        raise ValueError(f"input must be an existing PDF: {source_path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    asset_dir = target.parent / f"{target.stem}.assets"
    asset_dir.mkdir(parents=True, exist_ok=True)
    executable = _find_mineru()
    selected = "mineru" if backend in {"auto", "mineru"} and executable else "pymupdf"
    warnings: list[dict[str, Any]] = []
    if backend == "mineru" and not executable:
        raise RuntimeError("MinerU is not installed; install magic-pdf/mineru or use --backend pymupdf")
    try:
        if selected == "mineru":
            body, anchors, pages, extraction_warnings = _mineru_extract(source_path, target, asset_dir, executable or "magic-pdf")
        else:
            body, anchors, pages, extraction_warnings = _pymupdf_extract(source_path, target, asset_dir)
            warnings.append({"code": "PDF-BACKEND-001", "severity": "warning", "message": "MinerU unavailable; PyMuPDF text-layer fallback used. OCR, tables, figures and reading order require review."})
    except Exception:
        if backend != "auto" or selected == "pymupdf":
            raise
        body, anchors, pages, extraction_warnings = _pymupdf_extract(source_path, target, asset_dir)
        selected = "pymupdf"
        warnings.append({"code": "PDF-BACKEND-002", "severity": "warning", "message": "MinerU failed; PyMuPDF fallback used."})
    warnings.extend(extraction_warnings)
    target.write_text(body, encoding="utf-8")
    sidecar_path = Path(sidecar) if sidecar else report_path(target, REP_PROVENANCE)
    sidecar_payload = {"sourceFile": str(source_path), "sourceSha256": hashlib.sha256(source_path.read_bytes()).hexdigest(), "backend": selected, "pageCount": pages, "anchors": anchors}
    sidecar_path.write_text(json.dumps(sidecar_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = PdfExtractionReport(str(source_path), str(target), selected, "partial" if warnings else "complete", pages, warnings, str(sidecar_path))
    report_path_arg = Path(report) if report else report_path(target, REP_EXTRACT_REPORT)
    result.write_json(report_path_arg)
    return result
