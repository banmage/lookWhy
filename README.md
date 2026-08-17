# leleby SSIR M1

This repository currently implements the M1 conversion path:

```text
Canonical SSIR Markdown (CSM) -> SSIR JSON -> optional Turtle
```

PDF, MinerU, OCR, DOCX rendering, and round-trip verification are intentionally deferred to M2. The input contract is defined in `docs/07_leleby Canonical SSIR Markdown Format Specification v0.1.md`; the implementation contract is in `docs/08_leleby CSM-to-SSIR Implementation Specification v0.1.md`.

## Quick Start

```bash
python3 -m venv .venv
.venv/bin/pip install -e .

ssir csm validate --input examples/csm/Q_TQDZ_004-2026.csm.md
ssir csm parse --input examples/csm/Q_TQDZ_004-2026.csm.md --output out/Q_TQDZ_004-2026.ssir.json --format json --report out/Q_TQDZ_004-2026.conversion-report.json
ssir csm parse --input examples/csm/Q_TQDZ_004-2026.csm.md --output out/Q_TQDZ_004-2026.ttl --format ttl
```

Without installing the package, run the CLI from the repository root:

```bash
PYTHONPATH=src python3 -m leleby_ssir csm validate --input examples/csm/Q_PMRZ_9-2024.csm.md
```

## Test

```bash
PYTHONPATH=src python3 -m unittest discover -v
```

The parser defaults to tolerant import: missing machine metadata, BOM/line endings, short table rows, heading/numbering issues, and unknown directives are repaired or preserved without altering normative body text. Each successful parse writes a `.conversion-report.json` file containing every repair and quality issue; `--strict` rejects warnings for CI and Golden data. Non-UTF-8 input, malformed front matter, unclosed fenced blocks, duplicate explicit IDs, unsafe table structures, and invalid generated SSIR remain hard failures.

The bundled Draft-07 SSIR schema represents the standard metadata, document structure, tables/figures/formulas, Markdown source anchors, processing runs, and quality status required by the `standards/` references. GB/T 1.1 and GB/T 20001.10 optional or conditionally applicable components are not treated as import blockers.
