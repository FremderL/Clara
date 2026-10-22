from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable

from viernes_app.core.simulation_engine import SimulationAssumption, SimulationResult, SimulationTable


SearchFunction = Callable[[str], str | None]


@dataclass(frozen=True)
class ResearchTableResult:
    query: str
    source_summary: str
    table: SimulationTable
    warnings: list[str]

    def to_simulation_result(self) -> SimulationResult:
        return SimulationResult(
            title="Investigacion estructurada",
            summary=f"Organice resultados para: {self.query}.",
            assumptions=[
                SimulationAssumption("fuente", "busqueda web best-effort", 0.65),
                SimulationAssumption("exactitud", "solo datos encontrados en el resumen", 0.6),
            ],
            risks=list(self.warnings),
            recommendation="Para mejorar la tabla, especifique columnas y datos a investigar.",
            table=self.table,
        )


class ResearchTableBuilder:
    def build(self, query: str, search_fn: SearchFunction | None, max_rows: int = 20) -> ResearchTableResult:
        clean_query = _clean_query(query)
        if not clean_query:
            table = SimulationTable("Investigacion", ["dato", "resultado", "fuente"], [])
            return ResearchTableResult("", "sin consulta", table, ["falta consulta de investigacion"])
        source_summary = search_fn(clean_query) if search_fn is not None else None
        if not source_summary:
            source_summary = "No encontre resultados claros."
        columns = _infer_columns(clean_query)
        rows = _extract_rows(clean_query, source_summary, columns, max_rows=max_rows)
        warnings: list[str] = []
        if not rows:
            rows = [["no disponible" for _ in columns]]
            warnings.append("no se pudieron extraer filas confiables")
        if any("no disponible" in cell for row in rows for cell in row):
            warnings.append("algunos datos no estaban disponibles en el resumen de busqueda")
        return ResearchTableResult(
            query=clean_query,
            source_summary=source_summary,
            table=SimulationTable("Tabla de investigacion", columns, rows),
            warnings=warnings,
        )


def _clean_query(query: str) -> str:
    value = re.sub(r"\b(haz|hacer|crea|crear|genera|generar)\s+(una\s+)?tabla\b", " ", query, flags=re.IGNORECASE)
    value = re.sub(r"\b(en\s+)?tabla\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip(" ,-")
    return value


def _infer_columns(query: str) -> list[str]:
    low = query.lower()
    explicit = re.search(r"(?:con\s+)?columnas?\s+(.+)$", low)
    if explicit:
        raw = re.split(r",| y | / |\|", explicit.group(1))
        columns = [item.strip(" ,.-") for item in raw if item.strip(" ,.-")]
        if 2 <= len(columns) <= 6:
            return columns
    if "ventaja" in low or "desventaja" in low or "pros" in low or "contras" in low:
        return ["elemento", "ventajas", "desventajas", "fuente"]
    if "caracteristica" in low or "especificacion" in low or "propiedad" in low:
        return ["elemento", "caracteristica", "detalle", "fuente"]
    if "uso" in low or "aplicacion" in low or "sirve" in low:
        return ["elemento", "uso", "detalle", "fuente"]
    if "precio" in low or "costo" in low:
        return ["elemento", "precio", "fuente"]
    if "compara" in low or "comparar" in low:
        return ["elemento", "criterio", "resultado", "fuente"]
    return ["elemento", "resumen", "fuente"]


def _extract_rows(query: str, source_summary: str, columns: list[str], max_rows: int) -> list[list[str]]:
    parts = [part.strip(" .") for part in re.split(r"\s+\d+\.\s+", " " + source_summary) if part.strip(" .")]
    if not parts:
        parts = [source_summary.strip()]
    rows: list[list[str]] = []
    for idx, part in enumerate(parts[:max_rows], start=1):
        price = _extract_price(part)
        label = _short_label(part, idx)
        if columns == ["elemento", "precio", "fuente"]:
            rows.append([label, price or "no disponible", f"resultado {idx}"])
        elif columns == ["elemento", "ventajas", "desventajas", "fuente"]:
            rows.append([label, _extract_positive(part), _extract_negative(part), f"resultado {idx}"])
        elif columns == ["elemento", "caracteristica", "detalle", "fuente"]:
            rows.append([label, _extract_feature(part), _short_text(part), f"resultado {idx}"])
        elif columns == ["elemento", "uso", "detalle", "fuente"]:
            rows.append([label, _extract_use(part), _short_text(part), f"resultado {idx}"])
        elif columns == ["elemento", "criterio", "resultado", "fuente"]:
            rows.append([label, _extract_criterion(part), _short_text(part), f"resultado {idx}"])
        elif len(columns) == 3:
            rows.append([label, _short_text(part), f"resultado {idx}"])
        elif len(columns) == 4:
            rows.append([label, _extract_criterion(part), _short_text(part), f"resultado {idx}"])
        else:
            row = [label, _short_text(part)]
            while len(row) < len(columns):
                row.append("no disponible")
            rows.append(row[: len(columns)])
    return rows


def _extract_price(text: str) -> str:
    match = re.search(r"(\$\s*\d[\d,]*(?:\.\d+)?)", text)
    if match:
        return match.group(1).replace(" ", "")
    match = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(?:pesos|mxn|usd|dolares)", text, re.IGNORECASE)
    if match:
        return match.group(0)
    return ""


def _short_label(text: str, idx: int) -> str:
    value = re.sub(r"https?://\S+", "", text)
    value = re.sub(r"[^A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ $.,:-]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return f"resultado {idx}"
    return value[:60]


def _short_text(text: str) -> str:
    value = re.sub(r"\s+", " ", text).strip()
    return value[:180] if value else "no disponible"


def _extract_positive(text: str) -> str:
    match = re.search(r"(?:ventaja|pro|beneficio)s?\s*[:\-]?\s*([^.;]+)", text, re.IGNORECASE)
    return match.group(1).strip()[:120] if match else "no disponible"


def _extract_negative(text: str) -> str:
    match = re.search(r"(?:desventaja|contra|riesgo)s?\s*[:\-]?\s*([^.;]+)", text, re.IGNORECASE)
    return match.group(1).strip()[:120] if match else "no disponible"


def _extract_feature(text: str) -> str:
    match = re.search(r"(?:caracteristica|propiedad|especificacion)\s*[:\-]?\s*([^.;]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()[:120]
    return _first_meaningful_phrase(text)


def _extract_use(text: str) -> str:
    match = re.search(r"(?:sirve\s+para|se\s+usa\s+para|uso\s*[:\-]?)\s*([^.;]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()[:120]
    return "no disponible"


def _extract_criterion(text: str) -> str:
    if _extract_price(text):
        return "precio"
    if re.search(r"\b(ventaja|desventaja|beneficio|riesgo)\b", text, re.IGNORECASE):
        return "pros/contras"
    if re.search(r"\b(uso|sirve|aplicacion)\b", text, re.IGNORECASE):
        return "uso"
    return "resumen"


def _first_meaningful_phrase(text: str) -> str:
    value = re.sub(r"\s+", " ", text).strip()
    if not value:
        return "no disponible"
    return re.split(r"[.;]", value, maxsplit=1)[0][:120]
