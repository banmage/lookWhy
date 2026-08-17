"""Structured diagnostics for a single CSM-to-SSIR conversion."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .parser import CSMDocument, CSMIssue


@dataclass(slots=True)
class ConversionReport:
    input_file: str
    input_sha256: str
    parser_version: str
    converted: bool
    overall_status: str
    issues: list[CSMIssue]
    output_document_id: str | None = None
    block_ids_generated: bool = False

    @classmethod
    def completed(cls, document: CSMDocument, document_id: str) -> "ConversionReport":
        return cls(
            input_file=str(document.path),
            input_sha256=document.sha256,
            parser_version="0.1.0",
            converted=True,
            overall_status="partial" if document.issues else "complete",
            issues=document.issues,
            output_document_id=document_id,
            block_ids_generated=any(block.directive is None or "id" not in block.directive.attrs for block in document.blocks),
        )

    def to_dict(self) -> dict[str, Any]:
        def issue_dict(issue: CSMIssue) -> dict[str, Any]:
            return {
                "code": issue.code,
                "severity": issue.severity,
                "message": issue.message,
                "line": issue.line,
                "repaired": issue.repaired,
                "repairAction": issue.repair_action,
            }

        return {
            "inputFile": self.input_file,
            "inputSha256": self.input_sha256,
            "parserVersion": self.parser_version,
            "converted": self.converted,
            "overallStatus": self.overall_status,
            "outputDocumentId": self.output_document_id,
            "blockIdsGenerated": self.block_ids_generated,
            "issues": [issue_dict(issue) for issue in self.issues],
        }

    def write_json(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
