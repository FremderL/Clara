from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from viernes_app.core.simulation_engine import SimulationResult


class ReportBuilder:
    def format_result(self, result: SimulationResult) -> str:
        parts = [result.title + ": " + result.summary]
        if result.assumptions:
            assumptions = "; ".join(f"{item.key}={item.value}" for item in result.assumptions[:5])
            parts.append("Supuestos: " + assumptions + ".")
        if result.table:
            parts.append(f"Tabla: {result.table.title} ({len(result.table.rows)} fila(s)).")
        if result.chart:
            chart_note = f"Grafica: {result.chart.title}"
            if result.chart.path and Path(result.chart.path).exists():
                chart_note += f" guardada en {result.chart.path}"
            else:
                chart_note += " solicitada, pero sin archivo PNG confirmado; deje la tabla como respaldo"
            parts.append(chart_note + ".")
        if result.risks:
            parts.append("Riesgos: " + "; ".join(result.risks) + ".")
        if result.needs_input:
            parts.append("Falta: " + "; ".join(result.needs_input) + ".")
        if result.recommendation:
            parts.append("Recomendacion: " + result.recommendation)
        return " ".join(parts)

    def save_report(self, result: SimulationResult, output_dir: Path, slug: str | None = None) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = slug or result.title
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", base).strip("-").lower() or "reporte"
        target = output_dir / f"{stamp}-{safe}.json"
        payload: dict[str, Any] = result.to_dict()
        payload["created_at"] = datetime.now().isoformat(timespec="seconds")
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return target

    def list_reports(self, output_dir: Path, limit: int = 5) -> list[dict[str, str]]:
        if not output_dir.exists():
            return []
        files = sorted(output_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        return [{"name": item.name, "path": str(item)} for item in files[:limit]]
