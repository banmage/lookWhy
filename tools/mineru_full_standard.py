#!/usr/bin/env python3
"""Resumable full MinerU extraction and SSIR/PDF comparison workflow.

The tool deliberately uses MinerU's complete pipeline backend.  It divides a
long PDF into page ranges only to make CPU runs restartable; every range still
enables layout analysis, OCR, formulas, and tables.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]


def _log(message: str) -> None:
    print(f"[{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}", flush=True)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def _mineru_command() -> str:
    local = Path(sys.prefix) / "bin" / "mineru"
    if local.is_file() and local.stat().st_mode & 0o111:
        return str(local)
    found = shutil.which("mineru")
    if found:
        return found
    raise RuntimeError("MinerU is not installed in the active environment. Install mineru first.")


def _page_count(pdf: Path) -> int:
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to count and compare PDF pages.") from exc
    with fitz.open(pdf) as document:
        return len(document)


def _range_dir(output_dir: Path, start: int, end: int) -> Path:
    return output_dir / "parts" / f"pages-{start + 1:03d}-{end + 1:03d}"


def _mineru_markdown(part_dir: Path) -> Path | None:
    candidates = sorted(part_dir.rglob("*.md"), key=lambda path: path.stat().st_size, reverse=True)
    return candidates[0] if candidates else None


def _html_table_to_csm(html: str, table_id: str, caption: str | None) -> str:
    """Turn MinerU HTML tables into the constrained CSM table representation."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[list[str]] = []
    for tr in soup.find_all("tr"):
        row: list[str] = []
        for cell in tr.find_all(["th", "td"], recursive=False):
            text = " ".join(cell.get_text(" ", strip=True).split()).replace("|", r"\|")
            span = max(int(cell.get("colspan", 1)), 1)
            row.extend([text] + [""] * (span - 1))
        if row:
            rows.append(row)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    for row in rows:
        row.extend([""] * (width - len(row)))
    attrs = [f'id="mineru-table-{table_id}"', 'header-rows="1"']
    if caption:
        match = re.match(r"^表\s*([^\s]+)\s+(.+)$", caption)
        if match:
            attrs.extend([f'caption-number="{match.group(1)}"', f'caption="{match.group(2).replace(chr(34), "&quot;")}"'])
    lines = [f"<!-- ssir:table {' '.join(attrs)} -->"]
    for index, row in enumerate(rows):
        lines.append("| " + " | ".join(row) + " |")
        if index == 0:
            lines.append("| " + " | ".join("---" for _ in row) + " |")
    return "\n".join(lines)


def _formula_assets(source: Path) -> dict[str, list[str]]:
    """Index MinerU equation crops by their normalized display-LaTex text."""
    candidates = sorted(source.parent.glob("*_content_list.json"))
    if not candidates:
        return {}
    try:
        entries = json.loads(candidates[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    result: dict[str, list[str]] = {}
    for item in entries:
        if item.get("type") != "equation" or not item.get("img_path"):
            continue
        text = str(item.get("text", "")).strip()
        if text.startswith("$$") and text.endswith("$$"):
            text = text[2:-2].strip()
        key = re.sub(r"\s+", "", text)
        result.setdefault(key, []).append("assets/images/" + Path(str(item["img_path"])).name)
    return result


def _convert_mineru_markup(raw: str, part_prefix: str, formula_assets: dict[str, list[str]] | None = None) -> str:
    """Adapt MinerU HTML tables and relative image paths without altering prose."""
    table_index = 0
    output: list[str] = []
    position = 0
    for match in re.finditer(r"<table\b[^>]*>.*?</table>", raw, flags=re.IGNORECASE | re.DOTALL):
        before = raw[position:match.start()]
        output.append(before)
        caption = None
        previous = "".join(output).rstrip().splitlines()
        if previous:
            candidate = previous[-1].strip()
            if re.match(r"^表\s*[^\s]+\s+.+$", candidate):
                caption = candidate
                output[-1] = re.sub(r"[^\n]+$", "", output[-1])
        table_index += 1
        converted = _html_table_to_csm(match.group(0), f"{part_prefix}-{table_index:03d}", caption)
        output.append(converted if converted else match.group(0))
        position = match.end()
    output.append(raw[position:])
    converted = "".join(output).replace("](images/", "](assets/images/")
    lines = converted.splitlines()
    cleaned: list[str] = []
    image_pattern = re.compile(r"^!\[.*?\]\(([^)]+)\)$")
    figure_caption = re.compile(r"^图\s*([A-Z]?\.?\d+(?:\.\d+)?)\s+(.+)$")
    index = 0
    while index < len(lines):
        image = image_pattern.match(lines[index].strip())
        if not image:
            cleaned.append(lines[index])
            index += 1
            continue
        caption_at = None
        caption_match = None
        for probe in range(index + 1, min(index + 7, len(lines))):
            candidate = figure_caption.match(lines[probe].strip())
            if candidate:
                caption_at, caption_match = probe, candidate
                break
        if caption_match:
            label = f"图 {caption_match.group(1)} {caption_match.group(2)}"
            cleaned.append(f"![{label}]({image.group(1)})")
            cleaned.extend(lines[index + 1:caption_at])
            index = caption_at + 1
        else:
            cleaned.append(lines[index])
            index += 1
    # MinerU omitted the E.11 raster and misidentified its index-layout image
    # as a table directly after 图 E.10. Do not render that unrelated table
    # under the E.10 caption; retain a review marker instead.
    converted = "\n".join(cleaned)
    converted = re.sub(
        r"\n<!-- ssir:table id=\"mineru-table-p055-001\".*?\n图\s*E\.11\s+索引格式\n\n单位为毫米\n",
        "\n> [待复核：MinerU 将图 E.11 索引格式误识别为表格，未提取可渲染的图像资产]\n",
        converted,
        flags=re.DOTALL,
    )
    formula_assets = formula_assets or {}
    formula_index = 0

    def bind_formula(match: re.Match[str]) -> str:
        nonlocal formula_index
        expression = match.group(1).strip()
        candidates = formula_assets.get(re.sub(r"\s+", "", expression), [])
        if not candidates:
            return match.group(0)
        asset = candidates.pop(0)
        formula_index += 1
        identifier = f"{part_prefix}-{formula_index:03d}"
        return f'<!-- ssir:formula id="mineru-formula-{identifier}" asset-ref="{asset}" -->\n{match.group(0)}'

    return re.sub(r"\$\$\s*\n(.*?)\n\$\$", bind_formula, converted, flags=re.DOTALL)


def _recover_gbt_7_4_diagrams(markdown: str, source_pdf: Path, asset_dir: Path) -> str:
    """Restore the two page-18 7.4 layout diagrams MinerU split into text runs.

    The source extraction supplies neither a figure asset nor a coherent table.
    Both crops are taken verbatim from the original PDF and retain their labels,
    borders and typography.  The narrow match protects unrelated occurrences of
    the example's intentionally artificial placeholder text.
    """
    pattern = re.compile(
        r"## 5 要求\n\n×.*?\n\n## 6 试验方法\n\n## 6 试验方法",
        flags=re.DOTALL,
    )
    if not pattern.search(markdown):
        return markdown
    try:
        import fitz  # type: ignore

        asset_dir.mkdir(parents=True, exist_ok=True)
        crops = (("gbt-1-1-2020-7-4-diagrams.png", fitz.Rect(72, 275, 530, 548)),)
        with fitz.open(source_pdf) as document:
            page = document[17]  # PDF page 18, where GB/T 1.1 clause 7.4 appears.
            for name, rect in crops:
                target = asset_dir / name
                if not target.is_file():
                    page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=rect, alpha=False).save(target)
    except Exception as exc:
        _log(f"Warning: unable to recover 7.4 diagrams from original PDF: {exc}")
        return markdown
    figures = "\n\n".join(f"![]({(Path('assets') / 'images' / name).as_posix()})" for name, _ in crops)
    return pattern.sub(figures, markdown, count=1)


def extract(args: argparse.Namespace, state: dict[str, Any]) -> None:
    command = _mineru_command()
    total_pages = _page_count(args.input)
    _log(f"Extraction plan: {total_pages} pages, {args.chunk_size} pages per MinerU invocation")
    _log("Backend: pipeline; method: auto; language: ch; formulas: enabled; tables: enabled")
    state["input"] = str(args.input.resolve())
    state["sourceSha256"] = hashlib.sha256(args.input.read_bytes()).hexdigest()
    state["pageCount"] = total_pages
    state["chunkSize"] = args.chunk_size
    state["backend"] = "mineru pipeline"
    state["parameters"] = {"method": "auto", "language": "ch", "formula": True, "table": True}
    state.setdefault("parts", [])

    completed = {item["start"]: item for item in state["parts"] if item.get("status") == "complete"}
    for start in range(0, total_pages, args.chunk_size):
        end = min(start + args.chunk_size - 1, total_pages - 1)
        part_dir = _range_dir(args.output_dir, start, end)
        markdown = _mineru_markdown(part_dir)
        if start in completed and markdown:
            _log(f"Skipping pages {start + 1}-{end + 1}: recorded complete and Markdown exists")
            continue
        if markdown:
            state["parts"] = [item for item in state["parts"] if item.get("start") != start]
            state["parts"].append({"start": start, "end": end, "status": "complete", "markdown": str(markdown.relative_to(args.output_dir))})
            _write_json(args.state_file, state)
            _log(f"Skipping pages {start + 1}-{end + 1}: Markdown exists; state was repaired")
            continue

        part_dir.mkdir(parents=True, exist_ok=True)
        invocation = [
            command, "-p", str(args.input), "-o", str(part_dir), "-b", "pipeline", "-m", "auto", "-l", "ch",
            "-f", "true", "-t", "true", "-s", str(start), "-e", str(end),
        ]
        _log(f"Starting full MinerU pipeline for pages {start + 1}-{end + 1} of {total_pages}")
        _log(f"Persistent part directory: {part_dir}")
        started = time.monotonic()
        result = subprocess.run(invocation, cwd=ROOT)
        elapsed = time.monotonic() - started
        if result.returncode:
            state["lastFailure"] = {"start": start, "end": end, "returnCode": result.returncode}
            _write_json(args.state_file, state)
            _log(f"Pages {start + 1}-{end + 1} failed after {elapsed / 60:.1f} minutes; resume reruns only this range")
            raise RuntimeError(f"MinerU failed for pages {start + 1}-{end + 1} with exit code {result.returncode}")
        markdown = _mineru_markdown(part_dir)
        if markdown is None:
            raise RuntimeError(f"MinerU completed pages {start + 1}-{end + 1} but wrote no Markdown")
        state["parts"] = [item for item in state["parts"] if item.get("start") != start]
        state["parts"].append({"start": start, "end": end, "status": "complete", "markdown": str(markdown.relative_to(args.output_dir))})
        state.pop("lastFailure", None)
        _write_json(args.state_file, state)
        _log(f"Completed pages {start + 1}-{end + 1} in {elapsed / 60:.1f} minutes")
        _log(f"State saved: {args.state_file}")


def merge(args: argparse.Namespace, state: dict[str, Any]) -> Path:
    expected = list(range(0, state.get("pageCount", 0), args.chunk_size))
    completed = {item["start"]: item for item in state.get("parts", []) if item.get("status") == "complete"}
    missing = [start + 1 for start in expected if start not in completed]
    if missing:
        raise RuntimeError(f"Cannot merge: MinerU output is missing for pages starting at {missing}")

    _log(f"Merging {len(expected)} completed MinerU page ranges into one CSM Markdown document")
    destination = args.output_dir / "GBT-1.1-2020.mineru.csm.md"
    lines = [
        "---",
        'csm-version: "1.0"',
        "document-type: standard",
        'document-identifier: "GB/T 1.1-2020"',
        'standard-number: "GB/T 1.1-2020"',
        'title: "标准化工作导则 第1部分：标准化文件的结构和起草规则"',
        'title-en: "Directives for standardization - Part 1: Rules for the structure and drafting of standardizing documents"',
        'conformity-statement: "(ISO/IEC Directives，Part 2，2018，Principles and rules for the structure and drafting of ISO and IEC documents，NEQ)"',
        'ics: "01.120"',
        'ccs: "A 00"',
        'replaces: "GB/T 1.1—2009"',
        'publication-date: "2020-03-31"',
        'effective-date: "2020-10-01"',
        'issuer: "国家市场监督管理总局、国家标准化管理委员会"',
        "language: zh-CN",
        "source:",
        "  mode: mineru-pdf",
        f'  original-file-name: {json.dumps(args.input.name, ensure_ascii=False)}',
        "  provenance: mineru-full-standard-state.json",
        'extraction-backend: "mineru-3.4.5-pipeline"',
        "---",
        "",
        "# 标准化工作导则 第1部分：标准化文件的结构和起草规则",
        "",
    ]
    sources: list[dict[str, Any]] = []
    for start in expected:
        part = completed[start]
        source = args.output_dir / part["markdown"]
        raw = _convert_mineru_markup(
            source.read_text(encoding="utf-8", errors="replace").strip(),
            f"p{part['start'] + 1:03d}",
            _formula_assets(source),
        )
        image_source = source.parent / "images"
        if image_source.is_dir():
            image_target = args.output_dir / "assets" / "images"
            image_target.mkdir(parents=True, exist_ok=True)
            for image in image_source.iterdir():
                if image.is_file():
                    shutil.copy2(image, image_target / image.name)
        if part["start"] == 0:
            raw = _recover_gbt_7_4_diagrams(raw, args.input, args.output_dir / "assets" / "images")
        lines.extend([f"<!-- ssir:mineru-pages start=\"{part['start'] + 1}\" end=\"{part['end'] + 1}\" -->", raw, "", "<!-- /ssir:mineru-pages -->", ""])
        sources.append({"pages": [part["start"] + 1, part["end"] + 1], "markdown": part["markdown"], "sha256": hashlib.sha256(raw.encode()).hexdigest()})
    destination.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    _write_json(args.output_dir / "GBT-1.1-2020.mineru.provenance.json", {
        "sourcePdf": str(args.input.resolve()), "sourceSha256": state["sourceSha256"], "pageCount": state["pageCount"],
        "backend": state["backend"], "parameters": state["parameters"], "parts": sources,
    })
    _log(f"Merged Markdown written: {destination}")
    _log(f"Provenance written: {args.output_dir / 'GBT-1.1-2020.mineru.provenance.json'}")
    return destination


def finalize(args: argparse.Namespace, merged: Path) -> Path | None:
    """Use the existing CSM normalizer/parser, retaining partial status if parsing needs review."""
    std0 = args.output_dir / "GBT-1.1-2020.mineru.std0.csm.md"
    ssir = args.output_dir / "GBT-1.1-2020.mineru.ssir.json"
    normalize = [str(Path(sys.prefix) / "bin" / "ssir"), "csm", "normalize", "--input", str(merged), "--std0-output", str(std0)]
    parsed = [str(Path(sys.prefix) / "bin" / "ssir"), "csm", "parse", "--input", str(std0), "--output", str(ssir)]
    _log("Normalizing merged MinerU Markdown into CSM Std0")
    if subprocess.run(normalize, cwd=ROOT).returncode:
        print("CSM normalization needs review; MinerU extraction and provenance remain available.", file=sys.stderr)
        return None
    _log("Parsing normalized CSM into SSIR JSON")
    if subprocess.run(parsed, cwd=ROOT).returncode:
        print("SSIR parsing needs review; normalized CSM remains available.", file=sys.stderr)
        return None
    _log(f"SSIR JSON written: {ssir}")
    return ssir


def compare(original: Path, generated: Path, output: Path) -> None:
    import fitz  # type: ignore
    def details(path: Path) -> dict[str, Any]:
        with fitz.open(path) as document:
            text = "".join(page.get_text() for page in document)
            return {"path": str(path), "bytes": path.stat().st_size, "pageCount": len(document), "textCharacters": len(text)}
    original_info, generated_info = details(original), details(generated)
    _write_json(output, {
        "original": original_info,
        "generated": generated_info,
        "delta": {"pages": generated_info["pageCount"] - original_info["pageCount"], "bytes": generated_info["bytes"] - original_info["bytes"], "textCharacters": generated_info["textCharacters"] - original_info["textCharacters"]},
        "review": "Page count and text volume are objective checks. Tables, formula layout, pagination, and typography require visual review against the original PDF.",
    })


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a resumable full MinerU extraction for a standards PDF.")
    parser.add_argument("--input", type=Path, default=ROOT / "examples" / "GBT 1.1-2020.pdf")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "out" / "mineru" / "gbt-1.1-2020")
    parser.add_argument("--chunk-size", type=int, default=18, help="Pages per restartable MinerU invocation (default: 18).")
    parser.add_argument("--stage", choices=("extract", "merge", "finalize", "all"), default="all")
    parser.add_argument("--render", action="store_true", help="Render parsed SSIR to PDF and write a comparison report.")
    parser.add_argument("--toc-depth", default="2", help="Maximum numbered TOC level for --render (positive integer or all; default: 2).")
    args = parser.parse_args()
    if not args.input.is_file() or args.input.suffix.lower() != ".pdf":
        parser.error(f"input must be an existing PDF: {args.input}")
    if args.chunk_size < 1:
        parser.error("--chunk-size must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.state_file = args.output_dir / "mineru-full-standard-state.json"
    state = _load_json(args.state_file, {})
    _log(f"Input PDF: {args.input.resolve()}")
    _log(f"Output directory: {args.output_dir.resolve()}")
    _log(f"Stage: {args.stage}; render after parsing: {args.render}")

    try:
        if args.stage in {"extract", "all"}:
            extract(args, state)
        if args.stage == "extract":
            _log("Extraction stage complete. Run with --stage all to merge and parse after all page ranges finish.")
            return 0
        merged = merge(args, state)
        _log(f"Merged MinerU Markdown: {merged}")
        if args.stage == "merge":
            return 0
        ssir = finalize(args, merged)
        if args.render and ssir:
            pdf = args.output_dir / "GBT-1.1-2020.mineru.pdf"
            render = [str(Path(sys.prefix) / "bin" / "ssir"), "pdf", "render", "--input", str(ssir), "--output", str(pdf), "--toc-depth", args.toc_depth]
            _log("Rendering SSIR JSON as a GB/T 1.1-2020-style PDF")
            if subprocess.run(render, cwd=ROOT).returncode:
                raise RuntimeError("SSIR PDF renderer failed")
            compare(args.input, pdf, args.output_dir / "GBT-1.1-2020.mineru.pdf-comparison.json")
            _log(f"Generated PDF comparison: {args.output_dir / 'GBT-1.1-2020.mineru.pdf-comparison.json'}")
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _log("Workflow completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
