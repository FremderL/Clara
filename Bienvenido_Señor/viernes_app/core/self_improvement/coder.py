from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from viernes_app.core.self_improvement.analyzer import ImprovementAnalysis
from viernes_app.paths import RUNTIME_DIR


PROPOSALS_DIR = RUNTIME_DIR / "self_improvement" / "proposals"


@dataclass(frozen=True)
class ChangeProposal:
    id: str
    objective: str
    summary: str
    proposed_steps: list[str] = field(default_factory=list)
    files_to_review: list[str] = field(default_factory=list)
    created_at: str = ""
    status: str = "proposal"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "objective": self.objective,
            "summary": self.summary,
            "proposed_steps": list(self.proposed_steps),
            "files_to_review": list(self.files_to_review),
            "created_at": self.created_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChangeProposal":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:12]),
            objective=str(data.get("objective") or ""),
            summary=str(data.get("summary") or ""),
            proposed_steps=[str(item) for item in data.get("proposed_steps", []) if str(item).strip()]
            if isinstance(data.get("proposed_steps", []), list)
            else [],
            files_to_review=[str(item) for item in data.get("files_to_review", []) if str(item).strip()]
            if isinstance(data.get("files_to_review", []), list)
            else [],
            created_at=str(data.get("created_at") or ""),
            status=str(data.get("status") or "proposal"),
        )


class ImprovementCoder:
    """Genera propuestas; no escribe codigo ni aplica parches."""

    def draft_proposal(self, analysis: ImprovementAnalysis) -> ChangeProposal:
        steps = [
            "Confirmar alcance y archivos afectados.",
            "Preparar parche minimo y reversible.",
            "Ejecutar pruebas unitarias relevantes.",
            "Solicitar aprobacion explicita antes de aplicar.",
        ]
        if analysis.findings:
            steps.insert(1, "Atender hallazgos de severidad media/alta primero.")
        return ChangeProposal(
            id=uuid.uuid4().hex[:12],
            objective=analysis.objective,
            summary="Propuesta generada sin modificar archivos.",
            proposed_steps=steps,
            files_to_review=list(analysis.touched_candidates[:12]),
            created_at=datetime.now().isoformat(timespec="seconds"),
        )

    def save_proposal(
        self,
        proposal: ChangeProposal,
        *,
        analysis: ImprovementAnalysis | None = None,
        tests: Any = None,
        review: Any = None,
        root: Path | None = None,
    ) -> Path:
        proposals_dir = Path(root or PROPOSALS_DIR)
        proposals_dir.mkdir(parents=True, exist_ok=True)
        path = proposals_dir / f"{proposal.id}.json"
        payload = {
            "proposal": proposal.to_dict(),
            "analysis": analysis.to_dict() if analysis is not None and hasattr(analysis, "to_dict") else {},
            "tests": tests.to_dict() if tests is not None and hasattr(tests, "to_dict") else {},
            "review": review.to_dict() if review is not None and hasattr(review, "to_dict") else {},
            "policy": {
                "direct_code_mutation": False,
                "requires_tests_passed": True,
                "requires_user_approval": True,
            },
        }
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
        return path

    def load_proposal(self, proposal_id: str, *, root: Path | None = None) -> ChangeProposal | None:
        proposals_dir = Path(root or PROPOSALS_DIR)
        path = proposals_dir / f"{proposal_id}.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        proposal = data.get("proposal") if isinstance(data, dict) else None
        return ChangeProposal.from_dict(proposal) if isinstance(proposal, dict) else None
