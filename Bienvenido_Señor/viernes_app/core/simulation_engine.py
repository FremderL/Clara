from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class SimulationRequest:
    text: str
    kind: str = "simulation"


@dataclass(frozen=True)
class SimulationAssumption:
    key: str
    value: str
    confidence: float = 0.7

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "value": self.value, "confidence": self.confidence}


@dataclass(frozen=True)
class SimulationTable:
    title: str
    columns: list[str]
    rows: list[list[str]]

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "columns": list(self.columns), "rows": [list(row) for row in self.rows]}


@dataclass(frozen=True)
class SimulationChart:
    title: str
    chart_type: str
    labels: list[str]
    values: list[float]
    y_label: str = ""
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "chart_type": self.chart_type,
            "labels": list(self.labels),
            "values": list(self.values),
            "y_label": self.y_label,
            "path": self.path,
        }


@dataclass(frozen=True)
class SimulationResult:
    title: str
    summary: str
    assumptions: list[SimulationAssumption] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    recommendation: str = ""
    table: SimulationTable | None = None
    chart: SimulationChart | None = None
    needs_input: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "assumptions": [item.to_dict() for item in self.assumptions],
            "risks": list(self.risks),
            "recommendation": self.recommendation,
            "table": self.table.to_dict() if self.table else None,
            "chart": self.chart.to_dict() if self.chart else None,
            "needs_input": list(self.needs_input),
        }


class SimulationEngine:
    """Calculadoras y proyecciones locales con dominios explicitamente soportados."""

    def evaluate(self, request: SimulationRequest, context: dict[str, Any], now: datetime) -> SimulationResult:
        low = _normalize(request.text)
        if self._looks_like_ideas(low):
            return self._ideas_simulation(low, context, now)
        if self._looks_like_circuit(low):
            return self._circuit_simulation(low, context, now)
        if self._looks_like_budget(low):
            return self._budget_simulation(low, context, now, request.kind)
        if self._looks_like_schedule(low):
            return self._schedule_simulation(low, context, now)
        if request.kind == "report":
            return self._daily_report(low, context, now)
        return self._unsupported_analysis(low)

    def _circuit_simulation(self, low: str, context: dict[str, Any], now: datetime) -> SimulationResult:
        voltage = _extract_voltage(low)
        resistances = _extract_resistances(low)
        mode = "paralelo" if "paralelo" in low else "serie"
        if voltage is None or not resistances:
            missing: list[str] = []
            if voltage is None:
                missing.append("voltaje de la fuente, por ejemplo 9V")
            if not resistances:
                missing.append("resistencia(s), por ejemplo 330 ohms")
            return SimulationResult(
                title="Simulacion de circuito electrico",
                summary="Puedo simular un circuito DC resistivo basico, pero faltan datos electricos.",
                assumptions=[
                    SimulationAssumption("modelo", "DC resistivo ideal con ley de Ohm", 0.8),
                    SimulationAssumption("conexion", mode, 0.7),
                ],
                needs_input=missing,
                recommendation="Ejemplo: simula circuito con fuente de 9V y resistencia de 330 ohms.",
            )

        equivalent = _equivalent_resistance(resistances, mode)
        if equivalent <= 0:
            return SimulationResult(
                title="Simulacion de circuito electrico",
                summary="La resistencia equivalente no es valida para calcular corriente.",
                risks=["revise que las resistencias sean mayores a cero"],
                needs_input=["resistencias validas en ohms"],
            )
        current_a = voltage / equivalent
        power_w = voltage * current_a
        rows = [
            ["fuente", f"{voltage:g} V", "entrada"],
            ["conexion", mode, "supuesto por frase"],
            ["resistencias", ", ".join(f"{value:g} ohm" for value in resistances), "entrada"],
            ["resistencia equivalente", f"{equivalent:.2f} ohm", "calculado"],
            ["corriente total", f"{current_a:.4f} A ({current_a * 1000:.2f} mA)", "I = V / R"],
            ["potencia total", f"{power_w:.4f} W", "P = V * I"],
        ]
        risks: list[str] = []
        if current_a > 0.05 and ("led" in low or "arduino" in low or "gpio" in low):
            risks.append("la corriente puede ser alta para LED/GPIO; revise limites reales del componente")
        if power_w > 0.25:
            risks.append("la potencia supera 0.25 W; revise la potencia nominal de la resistencia")
        return SimulationResult(
            title="Simulacion de circuito electrico",
            summary=(
                f"Con {voltage:g} V y resistencia equivalente de {equivalent:.2f} ohm en {mode}, "
                f"la corriente estimada es {current_a * 1000:.2f} mA."
            ),
            assumptions=[
                SimulationAssumption("modelo", "circuito DC resistivo ideal", 0.85),
                SimulationAssumption("conexion", mode, 0.8),
                SimulationAssumption("sin tolerancias", "no incluye tolerancia, temperatura ni caida de componentes activos", 0.75),
            ],
            risks=risks,
            recommendation="Use esta simulacion como estimacion; para hardware real confirme datasheets, potencia y polaridad.",
            table=SimulationTable("Calculo electrico", ["elemento", "valor", "formula/nota"], rows),
            chart=SimulationChart(
                "Resistencias del circuito",
                "bar",
                [f"R{idx}" for idx, _value in enumerate(resistances, start=1)],
                resistances,
                "ohms",
            ),
        )

    def _ideas_simulation(self, low: str, context: dict[str, Any], now: datetime) -> SimulationResult:
        subject = _extract_idea_subject(low)
        if not subject:
            subject = "mejorar el dia y tomar una siguiente accion util"
        agenda = list(context.get("agenda_today") or [])
        classes = list(context.get("classes_today") or [])
        pending = list(context.get("pending_tasks") or [])
        criteria = ["impacto", "esfuerzo", "riesgo", "primer paso"]
        ideas = _build_ideas(subject, has_classes=bool(classes), has_pending=bool(pending), has_agenda=bool(agenda))
        rows = [[idea["idea"], idea["impacto"], idea["esfuerzo"], idea["riesgo"], idea["primer_paso"]] for idea in ideas]
        return SimulationResult(
            title="Ideas locales de Viernes",
            summary=f"Genere {len(rows)} idea(s) por reglas locales para {subject}, priorizando utilidad y accion inmediata.",
            assumptions=[
                SimulationAssumption("criterios", ", ".join(criteria), 0.75),
                SimulationAssumption("contexto", "agenda, clases y pendientes locales si existen", 0.7),
            ],
            risks=["son sugerencias por reglas locales, no una simulacion predictiva; conviene validarlas antes de convertirlas en acciones"],
            recommendation="Elija una idea y pida: conviertela en plan, agenda esto o crea pendiente.",
            table=SimulationTable("Ideas propuestas", ["idea", "impacto", "esfuerzo", "riesgo", "primer paso"], rows),
        )

    def _budget_simulation(self, low: str, context: dict[str, Any], now: datetime, kind: str) -> SimulationResult:
        budget = context.get("budget", {}) if isinstance(context.get("budget", {}), dict) else {}
        categories = context.get("budget_categories", {}) if isinstance(context.get("budget_categories", {}), dict) else {}
        balance = float(budget.get("balance", 0) or 0)
        limit = float(budget.get("budget_limit", 0) or 0)
        total_expenses = float(budget.get("total_expenses", 0) or 0)

        if kind == "chart" and categories:
            labels = list(categories.keys())[:10]
            values = [float(categories[label] or 0) for label in labels]
            rows = [[label, f"${value:.2f}"] for label, value in zip(labels, values)]
            return SimulationResult(
                title="Grafica de gastos",
                summary=f"Prepare una grafica con {len(rows)} categoria(s) de gasto registradas.",
                assumptions=[SimulationAssumption("fuente", "presupuesto local actual", 0.95)],
                recommendation="Use la grafica como lectura rapida; para proyecciones pida una simulacion con monto y periodo.",
                table=SimulationTable("Gastos por categoria", ["categoria", "gasto"], rows),
                chart=SimulationChart("Gastos por categoria", "bar", labels, values, "pesos"),
            )

        amount = _extract_money(low)
        days = _extract_days(low) or 7
        if amount is None:
            return SimulationResult(
                title="Simulacion de presupuesto",
                summary="Puedo simular el presupuesto, pero falta el monto a proyectar.",
                assumptions=[SimulationAssumption("periodo", f"{days} dias", 0.6)],
                needs_input=["monto diario o total a simular"],
                recommendation="Ejemplo: simula si gasto 200 pesos diarios esta semana.",
            )

        daily = amount if _looks_daily(low) else amount / max(days, 1)
        rows: list[list[str]] = []
        labels: list[str] = []
        values: list[float] = []
        projected_total = 0.0
        for idx in range(1, days + 1):
            projected_total = daily * idx
            remaining = balance - projected_total
            day_label = (now.date() + timedelta(days=idx - 1)).isoformat()
            rows.append([day_label, f"${projected_total:.2f}", f"${remaining:.2f}"])
            labels.append(f"D{idx}")
            values.append(projected_total)

        risks: list[str] = []
        if balance and projected_total > balance:
            risks.append("la proyeccion supera el balance actual")
        if limit and total_expenses + projected_total > limit:
            risks.append("la proyeccion rebasa el limite de presupuesto")

        return SimulationResult(
            title="Simulacion de presupuesto",
            summary=f"Si mantiene ${daily:.2f} diarios durante {days} dia(s), el gasto proyectado seria ${projected_total:.2f}.",
            assumptions=[
                SimulationAssumption("monto diario", f"${daily:.2f}", 0.85),
                SimulationAssumption("periodo", f"{days} dias", 0.8),
                SimulationAssumption("balance base", f"${balance:.2f}", 0.9),
            ],
            risks=risks,
            recommendation="Revise el limite antes de confirmar gastos reales; esta simulacion no modifica el presupuesto.",
            table=SimulationTable("Proyeccion de gasto", ["dia", "gasto acumulado", "balance estimado"], rows),
            chart=SimulationChart("Gasto acumulado simulado", "line", labels, values, "pesos"),
        )

    def _schedule_simulation(self, low: str, context: dict[str, Any], now: datetime) -> SimulationResult:
        minutes = _extract_minutes(low) or 30
        leave_time = str(context.get("leave_time") or "")
        classes = list(context.get("classes_today") or [])
        agenda = list(context.get("agenda_today") or [])
        assumptions = [
            SimulationAssumption("retraso", f"{minutes} minutos", 0.85),
            SimulationAssumption("salida configurada", leave_time or "no disponible", 0.75),
        ]
        rows = [["salida original", leave_time or "no disponible", "base"]]
        risks: list[str] = []
        if leave_time and re.fullmatch(r"\d{2}:\d{2}", leave_time):
            shifted = _add_minutes_to_hhmm(leave_time, minutes)
            rows.append(["salida simulada", shifted, f"+{minutes} min"])
            if classes:
                risks.append("hay clases registradas; el retraso puede afectar llegada")
        if agenda:
            rows.append(["eventos de hoy", str(len(agenda)), "revise agenda"])
        if classes:
            rows.append(["clases de hoy", ", ".join(str(x) for x in classes[:4]), "contexto"])
        return SimulationResult(
            title="Simulacion de horario",
            summary=f"Simule un ajuste de {minutes} minutos sobre la rutina del dia.",
            assumptions=assumptions,
            risks=risks,
            recommendation="Si el escenario se vuelve real, pida el cambio como accion y Viernes solicitara confirmacion cuando aplique.",
            table=SimulationTable("Impacto de horario", ["elemento", "valor", "nota"], rows),
        )

    def _daily_report(self, low: str, context: dict[str, Any], now: datetime) -> SimulationResult:
        agenda = list(context.get("agenda_today") or [])
        classes = list(context.get("classes_today") or [])
        pending = list(context.get("pending_tasks") or [])
        rows = [
            ["agenda", str(len(agenda)), _join_titles(agenda)],
            ["clases", str(len(classes)), ", ".join(str(x) for x in classes) or "sin clases"],
            ["pendientes", str(len(pending)), _join_titles(pending)],
        ]
        risks: list[str] = []
        if len(agenda) >= 3:
            risks.append("dia con varios eventos en agenda")
        if pending:
            risks.append("hay pendientes abiertos")
        return SimulationResult(
            title="Reporte del dia",
            summary=f"Reporte operativo generado para {now.date().isoformat()}.",
            assumptions=[SimulationAssumption("fuente", "agenda, clases y pendientes locales", 0.9)],
            risks=risks,
            recommendation="Use este reporte como vista previa; no se cambio ningun dato.",
            table=SimulationTable("Resumen operativo", ["area", "cantidad", "detalle"], rows),
        )

    def _unsupported_analysis(self, low: str) -> SimulationResult:
        return SimulationResult(
            title="Escenario no soportado",
            summary="No voy a presentar una suma de numeros como si fuera una simulacion. Este motor solo calcula presupuesto, horario y circuitos DC resistivos.",
            needs_input=["un escenario de presupuesto, horario o circuito con variables claras"],
            recommendation="Ejemplos: 'simula gasto de 200 pesos diarios por 7 dias', 'simula 30 minutos de retraso' o 'simula 9V con 330 ohms'.",
        )

    def _looks_like_budget(self, low: str) -> bool:
        return bool(re.search(r"\b(presupuesto|gasto|gastos|dinero|pesos|balance|ahorro|ahorrar)\b", low))

    def _looks_like_schedule(self, low: str) -> bool:
        return bool(re.search(r"\b(salgo|salir|salida|rutina|clase|clases|llego|llegar|tarde|temprano|minutos?)\b", low))

    def _looks_like_circuit(self, low: str) -> bool:
        return bool(re.search(r"\b(circuito|electrico|electronico|resistencia|resistencias|resistor|ohm|ohms|voltaje|voltios|corriente|amperios|led)\b", low))

    def _looks_like_ideas(self, low: str) -> bool:
        return bool(re.search(r"\b(ideas?|sugerencias?|propuestas?|propone|propon|dame\s+ideas|tus\s+propias\s+ideas)\b", low))


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _extract_money(low: str) -> float | None:
    match = re.search(r"\$\s*(\d+(?:[\.,]\d+)?)", low)
    if not match:
        match = re.search(r"\b(\d+(?:[\.,]\d+)?)\s*(?:pesos|mxn)\b", low)
    if not match:
        match = re.search(r"\b(?:gasto|gastar|gastaria|ahorro|ahorrar|ingreso|ingresar)\s+(\d+(?:[\.,]\d+)?)\b", low)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def _extract_days(low: str) -> int | None:
    if "semana" in low:
        return 7
    if "quincena" in low:
        return 15
    if "mes" in low:
        return 30
    match = re.search(r"\b(\d{1,3})\s+dias?\b", low)
    if match:
        return max(1, min(365, int(match.group(1))))
    return None


def _looks_daily(low: str) -> bool:
    return bool(re.search(r"\b(diario|diaria|diarios|diarias|al\s+dia|por\s+dia|cada\s+dia)\b", low))


def _extract_minutes(low: str) -> int | None:
    match = re.search(r"\b(\d{1,3})\s*(?:min|mins|minuto|minutos)\b", low)
    if not match:
        return None
    return max(1, min(360, int(match.group(1))))


def _extract_voltage(low: str) -> float | None:
    match = re.search(r"\b(\d+(?:[\.,]\d+)?)\s*(?:v|volt|volts|voltio|voltios)\b", low)
    if not match:
        match = re.search(r"\b(?:fuente|voltaje|bateria)\s+(?:de\s+)?(\d+(?:[\.,]\d+)?)\b", low)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def _extract_resistances(low: str) -> list[float]:
    phrase = re.search(r"\bresistencias?\s+(?:de\s+)?(.+?)(?:\s+en\s+(?:serie|paralelo)|$)", low)
    if phrase:
        unit_factor = 1000.0 if re.search(r"\bk(?:ilo)?\s*ohm", phrase.group(1)) else 1.0
        numbers = [float(item.replace(",", ".")) * unit_factor for item in re.findall(r"\d+(?:[\.,]\d+)?", phrase.group(1))]
        if len(numbers) > 1:
            return numbers
    values: list[float] = []
    for match in re.finditer(r"\b(\d+(?:[\.,]\d+)?)\s*(k|kilo)?\s*(?:ohm|ohms)\b", low):
        value = float(match.group(1).replace(",", "."))
        if match.group(2):
            value *= 1000
        values.append(value)
    if values:
        return values
    if not phrase:
        return []
    unit_factor = 1000.0 if re.search(r"\bk(?:ilo)?\s*ohm", phrase.group(1)) else 1.0
    numbers = [float(item.replace(",", ".")) * unit_factor for item in re.findall(r"\d+(?:[\.,]\d+)?", phrase.group(1))]
    return numbers


def _equivalent_resistance(resistances: list[float], mode: str) -> float:
    valid = [value for value in resistances if value > 0]
    if not valid:
        return 0.0
    if mode == "paralelo":
        inverse = sum(1.0 / value for value in valid)
        return 1.0 / inverse if inverse else 0.0
    return sum(valid)


def _extract_idea_subject(low: str) -> str:
    subject = re.sub(
        r"^(dame|dime|genera|generar|propone|propon|sugiere|sugerir|simula|simular)\s+",
        "",
        low,
        count=1,
    )
    subject = re.sub(r"^(tus\s+propias\s+)?ideas?\s+(para|sobre|de)?\s*", "", subject, count=1)
    subject = re.sub(r"^(sugerencias?|propuestas?)\s+(para|sobre|de)?\s*", "", subject, count=1)
    return subject.strip(" ,-")


def _build_ideas(subject: str, *, has_classes: bool, has_pending: bool, has_agenda: bool) -> list[dict[str, str]]:
    base = [
        {
            "idea": f"Crear una version minima de {subject}",
            "impacto": "alto",
            "esfuerzo": "medio",
            "riesgo": "bajo",
            "primer_paso": "definir resultado esperado en una frase",
        },
        {
            "idea": f"Hacer una tabla de opciones para {subject}",
            "impacto": "medio",
            "esfuerzo": "bajo",
            "riesgo": "bajo",
            "primer_paso": "listar 3 alternativas y 3 criterios",
        },
        {
            "idea": f"Convertir {subject} en plan de accion",
            "impacto": "alto",
            "esfuerzo": "medio",
            "riesgo": "medio",
            "primer_paso": "pedir a Viernes: conviertelo en plan confirmable",
        },
    ]
    if has_classes:
        base.append(
            {
                "idea": f"Relacionar {subject} con clases o estudio",
                "impacto": "medio",
                "esfuerzo": "medio",
                "riesgo": "bajo",
                "primer_paso": "separar investigacion, practica y entrega",
            }
        )
    if has_pending or has_agenda:
        base.append(
            {
                "idea": f"Reservar espacio real para {subject}",
                "impacto": "alto",
                "esfuerzo": "bajo",
                "riesgo": "medio",
                "primer_paso": "buscar hueco antes del siguiente compromiso",
            }
        )
    return base[:5]


def _add_minutes_to_hhmm(hhmm: str, minutes: int) -> str:
    hour, minute = [int(part) for part in hhmm.split(":", 1)]
    total = (hour * 60 + minute + minutes) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


def _join_titles(items: list[Any]) -> str:
    titles: list[str] = []
    for item in items[:4]:
        if isinstance(item, dict):
            titles.append(str(item.get("title") or item.get("name") or item))
        else:
            titles.append(str(item))
    return ", ".join(titles) if titles else "sin datos"
