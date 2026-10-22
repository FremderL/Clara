from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from viernes_app.paths import REPO_ROOT


@dataclass(frozen=True)
class AnalysisFinding:
    file: str
    line: int
    message: str
    severity: str = "info"

    def to_dict(self) -> dict[str, Any]:
        return {"file": self.file, "line": self.line, "message": self.message, "severity": self.severity}


@dataclass(frozen=True)
class ImprovementAnalysis:
    objective: str
    findings: list[AnalysisFinding] = field(default_factory=list)
    touched_candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "findings": [finding.to_dict() for finding in self.findings],
            "touched_candidates": list(self.touched_candidates),
        }


class ImprovementAnalyzer:
    def __init__(self, root: Path = REPO_ROOT) -> None:
        self.root = Path(root)

    def analyze(self, objective: str) -> ImprovementAnalysis:
        findings: list[AnalysisFinding] = []
        candidates: list[str] = []
        for path in self._candidate_files(objective):
            candidates.append(str(path.relative_to(self.root)))
            try:
                tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except SyntaxError as exc:
                findings.append(AnalysisFinding(str(path.relative_to(self.root)), int(exc.lineno or 0), exc.msg, "high"))
                continue
            function_count = sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in ast.walk(tree))
            if function_count > 60:
                findings.append(AnalysisFinding(str(path.relative_to(self.root)), 1, "Modulo grande; conviene dividir antes de crecer.", "medium"))
        return ImprovementAnalysis(objective, findings, candidates)

    def _candidate_files(self, objective: str) -> list[Path]:
        low = str(objective or "").lower()
        roots = [self.root / "viernes_app"]
        if "seguridad" in low or "permiso" in low:
            roots.append(self.root / "security")
        files: list[Path] = []
        for root in roots:
            if root.exists():
                files.extend(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)
        return files[:80]
