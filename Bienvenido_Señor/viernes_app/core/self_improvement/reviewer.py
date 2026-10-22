from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from viernes_app.core.self_improvement.coder import ChangeProposal
from viernes_app.core.self_improvement.tester import TestRunResult


@dataclass(frozen=True)
class ReviewResult:
    approved_for_request: bool
    summary: str
    risks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved_for_request": self.approved_for_request,
            "summary": self.summary,
            "risks": list(self.risks),
        }


class ImprovementReviewer:
    def review(self, proposal: ChangeProposal, tests: TestRunResult | None = None) -> ReviewResult:
        risks: list[str] = []
        if len(proposal.files_to_review) > 8:
            risks.append("El alcance toca muchos archivos; conviene dividir.")
        if tests is not None and not tests.passed:
            risks.append("Las pruebas no pasaron; no se debe aplicar.")
        approved = tests is not None and tests.passed and not risks
        summary = (
            "Listo para solicitar aprobacion de aplicacion." if approved else
            "Solo propuesta; requiere ajustes, pruebas o aprobacion antes de aplicar."
        )
        return ReviewResult(approved, summary, risks)
