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
ssir csm parse --input examples/csm/Q_TQDZ_004-2026.csm.md --output out/Q_TQDZ_004-2026.ssir.json --format json
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

The parser validates CSM front matter, headings, chapter numbering, SSIR directives, tables, and duplicate IDs. It produces SSIR v0.4 JSON validated against the bundled Draft-07 schema and uses Markdown line/AST SourceAnchors. Product-standard source issues recorded in `extensions.quality-notices` are preserved in `QualityAssessment.comments`.
