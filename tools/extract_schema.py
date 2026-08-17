"""Extract the executable JSON Schema embedded in the design document."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "02_leleby SSIR JSON Schema Specification v0.3.md"
TARGET = ROOT / "src" / "leleby_ssir" / "ssir.schema.json"


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    start = text.index("```json") + len("```json")
    end = text.index("```", start)
    schema = json.loads(text[start:end])
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
