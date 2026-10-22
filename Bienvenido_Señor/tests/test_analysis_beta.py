from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import queue
import re
import tempfile
import threading
import unittest
from unittest.mock import patch

from viernes_app.core.charting import render_chart
from viernes_app.core.decision import IntentDecision
from viernes_app.core.nlu import NaturalLanguageRouter
from viernes_app.core.research_tables import ResearchTableBuilder
from viernes_app.core.simulation_engine import SimulationEngine, SimulationRequest
from viernes_app.integrations.remote_control import RemoteCallAdapter, RemoteControlService
from tests.test_vnext import make_assistant


class SimulationEngineTests(unittest.TestCase):
    def test_budget_simulation_returns_table_assumptions_and_chart(self) -> None:
        engine = SimulationEngine()
        result = engine.evaluate(
            SimulationRequest("si gasto 200 pesos diarios esta semana"),
            {"budget": {"balance": 2000, "budget_limit": 1500, "total_expenses": 200}},
            datetime(2026, 5, 27, 10, 0),
        )

        self.assertIn("presupuesto", result.title.lower())
        self.assertIsNotNone(result.table)
        self.assertIsNotNone(result.chart)
        self.assertTrue(result.assumptions)
        self.assertEqual(7, len(result.table.rows))
        self.assertIn("$1400.00", result.summary)

    def test_schedule_simulation_does_not_need_mutation(self) -> None:
        engine = SimulationEngine()
        result = engine.evaluate(
            SimulationRequest("que pasaria si salgo 30 minutos tarde"),
            {"leave_time": "12:00", "classes_today": ["Ingles"], "agenda_today": []},
            datetime(2026, 5, 27, 10, 0),
        )

        self.assertIn("horario", result.title.lower())
        self.assertIn("12:30", str(result.table.rows))
        self.assertTrue(result.risks)

    def test_circuit_simulation_uses_ohm_law_for_series_resistors(self) -> None:
        engine = SimulationEngine()
        result = engine.evaluate(
            SimulationRequest("simula un circuito con fuente de 9v y resistencias de 100 y 220 ohms en serie"),
            {},
            datetime(2026, 5, 27, 10, 0),
        )

        self.assertIn("circuito electrico", result.title.lower())
        self.assertIsNotNone(result.table)
        self.assertIn("320.00 ohm", str(result.table.rows))
        self.assertIn("28.12 mA", result.summary)

    def test_ideas_simulation_generates_own_ranked_ideas(self) -> None:
        engine = SimulationEngine()
        result = engine.evaluate(
            SimulationRequest("dame tus propias ideas para mejorar mi estudio"),
            {"classes_today": ["POO"], "pending_tasks": [{"title": "entrega"}]},
            datetime(2026, 5, 27, 10, 0),
        )

        self.assertIn("Ideas locales de Viernes", result.title)
        self.assertIsNotNone(result.table)
        self.assertGreaterEqual(len(result.table.rows), 3)
        self.assertEqual(["idea", "impacto", "esfuerzo", "riesgo", "primer paso"], result.table.columns)

    def test_unsupported_simulation_is_honest_about_its_limits(self) -> None:
        engine = SimulationEngine()
        result = engine.evaluate(SimulationRequest("simula 3 planetas y 9 lunas"), {}, datetime(2026, 5, 27, 10, 0))

        self.assertEqual("Escenario no soportado", result.title)
        self.assertIsNone(result.table)
        self.assertTrue(result.needs_input)

    def test_chart_renderer_creates_or_returns_safe_fallback(self) -> None:
        engine = SimulationEngine()
        result = engine.evaluate(
            SimulationRequest("grafica de mis gastos", kind="chart"),
            {"budget": {}, "budget_categories": {"comida": 120, "transporte": 80}},
            datetime(2026, 5, 27, 10, 0),
        )
        self.assertIsNotNone(result.chart)
        with tempfile.TemporaryDirectory() as tmp:
            rendered = render_chart(result.chart, Path(tmp), "gastos")
            if rendered.path:
                self.assertTrue(Path(rendered.path).exists())


class ResearchTableTests(unittest.TestCase):
    def test_structured_research_uses_fake_search_and_marks_missing_values(self) -> None:
        builder = ResearchTableBuilder()
        result = builder.build(
            "precios de laptops",
            lambda _query: "1. Laptop A cuesta $100. 2. Laptop B sin precio publicado.",
            max_rows=5,
        )

        self.assertEqual(["elemento", "precio", "fuente"], result.table.columns)
        self.assertEqual(2, len(result.table.rows))
        self.assertIn("no disponible", str(result.table.rows))

    def test_structured_research_infers_general_columns_for_any_topic(self) -> None:
        builder = ResearchTableBuilder()
        result = builder.build(
            "ventajas y desventajas de paneles solares",
            lambda _query: "1. Panel solar ventaja: reduce consumo. desventaja: depende del sol. 2. Panel flexible ventaja: ligero.",
            max_rows=5,
        )

        self.assertEqual(["elemento", "ventajas", "desventajas", "fuente"], result.table.columns)
        self.assertEqual(2, len(result.table.rows))
        self.assertIn("reduce consumo", str(result.table.rows))


class AnalysisNluAndAssistantTests(unittest.TestCase):
    def test_nlu_detects_analysis_intents(self) -> None:
        router = NaturalLanguageRouter()

        self.assertEqual("simulation_request", router.classify("simula si gasto 200 pesos diarios esta semana").intent)
        self.assertEqual("research_table", router.classify("investiga modelos de laptop y haz tabla").intent)
        self.assertEqual("research_table", router.classify("haz una tabla de modelos de laptop").intent)
        self.assertEqual("chart_request", router.classify("haz una grafica de mis gastos").intent)
        self.assertEqual("analysis_report", router.classify("reporte de mi semana").intent)
        self.assertEqual("remote_control_status", router.classify("estado control remoto").intent)
        self.assertEqual("simulation_request", router.classify("dame tus propias ideas para mi proyecto").intent)

    def test_process_command_analysis_does_not_mutate_agenda_or_state_domains(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            assistant = make_assistant(Path(tmp) / "memory.json")
            assistant.config["analysis"] = {"enabled": True, "save_reports": False, "allow_web_research": True, "max_rows": 20}
            agenda_before = list(assistant.agenda["items"])
            overrides_before = dict(assistant.state.get("day_overrides", {}))

            response = assistant.process_command("simula si gasto 200 pesos diarios esta semana", now=datetime(2026, 5, 25, 10, 0))

        self.assertIn("Simulacion", response)
        self.assertEqual(agenda_before, assistant.agenda["items"])
        self.assertEqual(overrides_before, assistant.state.get("day_overrides", {}))

    def test_research_table_command_uses_structured_research_and_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            assistant = make_assistant(Path(tmp) / "memory.json")
            assistant.config["analysis"] = {"enabled": True, "save_reports": False, "allow_web_research": True, "max_rows": 20}
            with patch("viernes_app.core.assistant.search_web", return_value="1. Laptop A $100. 2. Laptop B $200."):
                response = assistant.process_command("investiga precios de laptops y haz tabla", now=datetime(2026, 5, 25, 10, 0))
            dashboard = assistant.today_dashboard(now=datetime(2026, 5, 25, 10, 0))

        self.assertIn("Investigacion estructurada", response)
        self.assertIn("analysis", dashboard)
        self.assertTrue(dashboard["analysis"]["last_result"])

    def test_process_command_circuit_and_ideas_are_real_analysis_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            assistant = make_assistant(Path(tmp) / "memory.json")
            assistant.config["analysis"] = {"enabled": True, "save_reports": False, "allow_web_research": True, "max_rows": 20}

            circuit = assistant.process_command(
                "simula un circuito con fuente de 9v y resistencia de 330 ohms",
                now=datetime(2026, 5, 25, 10, 0),
            )
            ideas = assistant.process_command(
                "dame tus propias ideas para mejorar mi estudio",
                now=datetime(2026, 5, 25, 10, 0),
            )

        self.assertIn("circuito electrico", circuit.lower())
        self.assertIn("27.27 mA", circuit)
        self.assertIn("Ideas locales de Viernes", ideas)


class RemoteControlTests(unittest.TestCase):
    def _service(self, decision: IntentDecision, calls: list[tuple[str, bool]]) -> RemoteControlService:
        config = {
            "remote_control": {
                "enabled": True,
                "allowed_chat_ids": ["42"],
                "require_confirmation": True,
                "blocked_intents": ["cleanup_past_events"],
            },
            "remote_calls": {"enabled": False},
        }

        def runner(command: str, now: datetime, confirmed: bool) -> str:
            calls.append((command, confirmed))
            return "ejecutado"

        return RemoteControlService(config, {"remote_control": {}}, lambda _text, _now: decision, runner)

    def test_remote_rejects_unauthorized_chat(self) -> None:
        calls: list[tuple[str, bool]] = []
        service = self._service(
            IntentDecision("today_status", 0.9, "low", "_build_today_status", "test"),
            calls,
        )

        result = service.handle_text("99", "que tengo hoy", datetime(2026, 5, 27, 10, 0))

        self.assertFalse(result.accepted)
        self.assertFalse(calls)

    def test_remote_executes_read_only_command(self) -> None:
        calls: list[tuple[str, bool]] = []
        service = self._service(
            IntentDecision("today_status", 0.9, "low", "_build_today_status", "test"),
            calls,
        )

        result = service.handle_text("42", "que tengo hoy", datetime(2026, 5, 27, 10, 0))

        self.assertTrue(result.executed)
        self.assertEqual([("que tengo hoy", False)], calls)

    def test_remote_requires_confirmation_for_mutating_command_and_executes_once(self) -> None:
        calls: list[tuple[str, bool]] = []
        service = self._service(
            IntentDecision("leave_time_change", 0.95, "medium", "_routine_command", "test", requires_confirmation=True, mutates=True),
            calls,
        )
        now = datetime(2026, 5, 27, 10, 0)

        pending = service.handle_text("42", "cambia salida a las 12 hoy", now)
        token = re.search(r"confirmar\s+(\d+)", pending.message).group(1)
        confirmed = service.handle_text("42", f"confirmar {token}", now + timedelta(minutes=1))
        repeated = service.handle_text("42", f"confirmar {token}", now + timedelta(minutes=2))

        self.assertTrue(pending.requires_confirmation)
        self.assertTrue(confirmed.executed)
        self.assertEqual([("cambia salida a las 12 hoy", True)], calls)
        self.assertIn("No encontre", repeated.message)

    def test_remote_blocks_dangerous_and_calls_are_disabled(self) -> None:
        calls: list[tuple[str, bool]] = []
        service = self._service(
            IntentDecision("today_status", 0.9, "low", "_build_today_status", "test"),
            calls,
        )

        blocked = service.handle_text("42", "apaga la laptop", datetime(2026, 5, 27, 10, 0))
        call = RemoteCallAdapter(enabled=False).handle("llama a casa")

        self.assertIn("bloqueado", blocked.message)
        self.assertIn("apagado", call)
        self.assertFalse(calls)
