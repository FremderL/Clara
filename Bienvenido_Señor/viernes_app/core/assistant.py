
from __future__ import annotations
from utils.command_registry import CommandRegistry
from utils.activity_monitor import ActivityMonitor, windows_system_idle_seconds
from utils.push_to_talk import PushToTalk

import atexit
import hashlib
import json
import queue
import random
import re
import threading
import unicodedata
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, replace
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path
from typing import Any, Optional

from viernes_app.core.cognition import ViernesBrain
from viernes_app.core.nlu import IntentResult, NaturalLanguageRouter
from viernes_app.core.action_executor import ActionExecutor
from viernes_app.core.action_history import ActionHistoryStore
from viernes_app.core.action_planner import ActionPlan, ActionPlanner, PlanStep
from viernes_app.core.activity_calendar import ActivityCalendar, ActivityCalendarBuilder, ActivityWeek
from viernes_app.core.clarification import ClarificationEngine, ClarificationRequest
from viernes_app.core.config_manager import ConfigValidationResult, ViernesConfigManager
from viernes_app.core.games import GameEngine
from viernes_app.core.charting import render_chart
from viernes_app.core.memory_manager import PersistentMemoryManager
from viernes_app.core.planner import AgentPlan, AgentPlanner
from viernes_app.core.tool_router import ToolRequest, ToolRouter
from viernes_app.core.decision import (
    COMMAND_AUDIT_MATRIX,
    TOOL_CAPABILITIES,
    CommandDryRun,
    IntentDecision,
    decision_for_intent,
)
from viernes_app.core.report_builder import ReportBuilder
from viernes_app.core.routine_helpers import (
    WEEKDAY_KEYS as ROUTINE_WEEKDAY_KEYS,
    WEEKDAY_LABELS as ROUTINE_WEEKDAY_LABELS,
    day_routine_enabled,
    migrate_legacy_routines,
    normalize_day_payload,
    resolve_day_cfg,
    routine_scope_for_day,
    validate_day_payload,
)
from viernes_app.core.reliability import (
    ExecutionReceipt,
    IntentArbiter,
    ToolRegistry,
    VerificationEvidence,
)
from viernes_app.core.research_tables import ResearchTableBuilder
from viernes_app.core.simulation_engine import SimulationEngine, SimulationRequest, SimulationResult
from viernes_app.core.self_improvement.analyzer import ImprovementAnalyzer
from viernes_app.core.self_improvement.coder import ImprovementCoder
from viernes_app.core.self_improvement.reviewer import ImprovementReviewer
from viernes_app.core.self_improvement.tester import ImprovementTester
from viernes_app.core.pending_tasks import PendingTaskStore
from viernes_app.core.pending_tasks import PendingTaskBoard
from viernes_app.core.personal_memory import MemoryFact, PersonalMemoryStore, PersonalRule, Preference, UserProfile
from viernes_app.core.proactivity import (
    DEFAULT_PROACTIVITY_CONFIG,
    ProactiveContext,
    ProactiveEngine,
    ProactiveSuggestion,
)
from viernes_app.paths import AGENDA_PATH, CONFIG_PATH, REPO_ROOT, RUNTIME_DIR, STATE_PATH
from viernes_app.services.budget_data import get_balance, get_expenses_by_category, get_recent_transactions
from viernes_app.services.agenda_service import full_agenda_summary as build_full_agenda_summary, sort_agenda_items
from viernes_app.services.apps import list_available_apps, open_application
from viernes_app.services.budget_service import handle_budget_command
from viernes_app.services.classes_service import classes_for_day as service_classes_for_day
from viernes_app.services.classes_service import classes_overview as service_classes_overview
from viernes_app.services.classes_service import classes_summary_for_day as service_classes_summary_for_day
from viernes_app.services.tools import calculate, get_news, search_web
from viernes_app.services.storage_legacy import ChatHistory
from viernes_app.services.learning import (
    HabitTracker,
    build_adaptive_profile,
    get_alias_suggestions,
    get_habit_recommendations,
    get_user_stats,
    log_user_action,
)
from viernes_app.services.security_monitor import SecurityMonitor
from viernes_app.services.personal_activity import PersonalActivityService
from viernes_app.voice.voice import ViernesVoice
from viernes_app.voice.speech_input import speech_input_available
from viernes_app.voice.continuous import ContinuousConversationController
from viernes_app.voice.interruption import InterruptionDetector
from viernes_app.voice.profiles import VoiceProfileManager
from viernes_app.voice.wake_word import WakeWordDetector
from viernes_app.integrations.wake import (
    get_energy_diagnostics,
    get_resident_status,
    install_resident_mode,
    remove_resident_mode,
    remove_scheduled_task,
    repair_wake_configuration,
    schedule_wake_test,
    session_lock_state,
    set_startup_enabled,
    setup_morning_wake,
    wake_on_lan,
)
from viernes_app.integrations.telegram import TelegramClient, TelegramNotifier
from viernes_app.integrations.remote_control import (
    RemoteControlService,
    get_remote_resident_status,
    install_remote_resident_mode,
    remove_remote_resident_mode,
)
from viernes_app.plugins import PluginManager
from security.auth import AuthManager
from security.permissions import PermissionManager

ROOT_DIR = REPO_ROOT

# Integraciones opcionales (no obligatorias, incorporar si existen)
try:
    from jarvis_os_v5.productivity.briefing import fetch_open_meteo_current
except Exception:
    fetch_open_meteo_current = None
try:
    from jarvis_os_v5.core.safe_math import safe_eval_math
except Exception:
    safe_eval_math = None
try:
    from jarvis_os_v5.core.startup_diagnostics import run_startup_ast_check
except Exception:
    run_startup_ast_check = None
try:
    from ai.semantic_router import SemanticRouter
except Exception:
    SemanticRouter = None
try:
    from utils.code_auditor import CodeAuditor
except Exception:
    CodeAuditor = None
try:
    from viernes_app.integrations.ai import OllamaClient as _AiOllamaClient, generate_ai_response
except Exception:
    _AiOllamaClient = None
    generate_ai_response = None
try:
    from ai.ollama_integration import OllamaClient as _LegacyOllamaClient
except Exception:
    _LegacyOllamaClient = None
# Preferir el cliente nuevo (viernes_app.integrations.ai) sobre el viejo
OllamaClient = _AiOllamaClient or _LegacyOllamaClient
try:
    from utils.concurrency_utils import ThreadSafeMixin, synchronized
except Exception:
    ThreadSafeMixin = None


WEEKDAY_KEYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
WEEKDAY_LABELS = {
    "monday": "lunes",
    "tuesday": "martes",
    "wednesday": "miercoles",
    "thursday": "jueves",
    "friday": "viernes",
    "saturday": "sabado",
    "sunday": "domingo",
}
WEEKDAY_NAMES = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
WEEKDAY_RE = r"(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)"
MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
MONTH_LABELS = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return json.loads(json.dumps(default))
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return json.loads(json.dumps(default))
    return data if isinstance(data, dict) else json.loads(json.dumps(default))


def _save_json(path: Path, data: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    for damaged, repaired in {
        "h?blame": "hablame",
        "cu?ntame": "cuentame",
        "sorpr?ndeme": "sorprendeme",
        "d?me": "dime",
        "qu?": "que",
        "c?mo": "como",
        "est?s": "estas",
        "ma?ana": "manana",
        "ba?o": "bano",
        "ba?e": "bane",
        "ba?arse": "banarse",
    }.items():
        text = text.replace(damaged, repaired)
    for src, dst in {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
        "Ã¡": "a",
        "Ã©": "e",
        "Ã­": "i",
        "Ã³": "o",
        "Ãº": "u",
        "Ã±": "n",
        "\u00e3\u00a1": "a",
        "\u00e3\u00a9": "e",
        "\u00e3\u00ad": "i",
        "\u00e3\u00b3": "o",
        "\u00e3\u00ba": "u",
        "\u00e3\u00bc": "u",
        "\u00e3\u00b1": "n",
    }.items():
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[¿?¡!.,;:\"'()]+", " ", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub("[\u00bf?\u00a1!.,;:\"'()]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_hhmm(value: str) -> dt_time:
    hh, mm = [int(x) for x in value.split(":", 1)]
    return dt_time(hour=hh, minute=mm)


def combine_today(now: datetime, hhmm: str) -> datetime:
    tt = parse_hhmm(hhmm)
    return now.replace(hour=tt.hour, minute=tt.minute, second=0, microsecond=0)


def weekday_key(day: date) -> str:
    return WEEKDAY_KEYS[day.weekday()]


def iso_day(day: date) -> str:
    return day.isoformat()


def weekday_name_to_key(name: str) -> str:
    return {
        "lunes": "monday",
        "martes": "tuesday",
        "miercoles": "wednesday",
        "jueves": "thursday",
        "viernes": "friday",
        "sabado": "saturday",
        "domingo": "sunday",
    }[name]


@dataclass
class ReminderEvent:
    event_id: str
    message: str
    level: str = "info"


class ViernesAssistant:
    def __init__(self) -> None:
        self.config = _load_json(CONFIG_PATH, {})
        self.state = _load_json(
            STATE_PATH,
            {"daily": {}, "day_overrides": {}, "habit_history": [], "classes_by_date": {}},
        )
        self.agenda = _load_json(AGENDA_PATH, {"items": []})
        self.pending_dialog: Optional[dict[str, Any]] = None
        self.messages: "queue.Queue[tuple[str, str]]" = queue.Queue()
        self.brain = ViernesBrain()
        self.nlu = NaturalLanguageRouter()
        self.proactivity = ProactiveEngine()
        self.memory_store = PersonalMemoryStore()
        self.pending_tasks = PendingTaskStore()
        self.activity_calendar_builder = ActivityCalendarBuilder()
        self.action_planner = ActionPlanner()
        self.action_executor = ActionExecutor()
        self.action_history = ActionHistoryStore()
        self.clarification_engine = ClarificationEngine()
        self.config_manager = ViernesConfigManager(CONFIG_PATH)
        self.simulation_engine = SimulationEngine()
        self.report_builder = ReportBuilder()
        self.research_table_builder = ResearchTableBuilder()
        self.tool_registry = ToolRegistry()
        self.game_engine = GameEngine()
        self.agent_planner = AgentPlanner()
        self.agent_memory = PersistentMemoryManager()
        self.permission_manager = PermissionManager.from_config(self.config)
        self.auth_manager = AuthManager(
            str(self.config.get("security", {}).get("password_hash", "") or "")
            if isinstance(self.config.get("security", {}), dict)
            else ""
        )
        self.tool_router = ToolRouter(self.permission_manager)
        plugin_cfg = self.config.get("plugins", {})
        self.plugin_manager = PluginManager(
            REPO_ROOT / "viernes_app" / "plugins",
            plugin_cfg if isinstance(plugin_cfg, dict) else {},
        )
        plugins_enabled = bool(plugin_cfg.get("enabled", True)) if isinstance(plugin_cfg, dict) else True
        self.loaded_plugins = self.plugin_manager.load_plugins(
            tool_router=self.tool_router,
            assistant=self,
            enabled=plugins_enabled,
        )
        self.security_monitor = SecurityMonitor()
        self.security_monitor.establish_baseline()
        personal_activity_cfg = self.config.get("personal_activity", {})
        self.personal_activity = PersonalActivityService(
            personal_activity_cfg if isinstance(personal_activity_cfg, dict) else {}
        )
        if self.personal_activity.enabled:
            self.personal_activity.start()
        atexit.register(self._shutdown_personal_activity)
        self.improvement_analyzer = ImprovementAnalyzer()
        self.improvement_coder = ImprovementCoder()
        self.improvement_tester = ImprovementTester()
        self.improvement_reviewer = ImprovementReviewer()
        self.voice_profiles = VoiceProfileManager()
        active_voice_profile = self.voice_profiles.get(str(self.config.get("voice_profile", "default") or "default"))
        self.wake_word_detector = WakeWordDetector(str(self.config.get("wake_word", active_voice_profile.wake_word) or "viernes"))
        self.interruption_detector = InterruptionDetector()
        self.continuous_conversation = ContinuousConversationController(
            self.process_command,
            wake_word=str(self.config.get("wake_word", active_voice_profile.wake_word) or "viernes"),
            interruption_detector=self.interruption_detector,
        )
        voice_rate = active_voice_profile.rate if active_voice_profile.name != "default" else int(self.config.get("tts_rate", 165))
        self.voice = ViernesVoice(
            rate=voice_rate,
            enabled=bool(self.config.get("voice_enabled", True)),
            interruption_detector=self.interruption_detector,
        )
        self._lock = threading.RLock()
        # Integraciones opcionales: instancias seguras si los módulos existen
        self._auditor = CodeAuditor() if CodeAuditor is not None else None
        self._ollama = None
        if OllamaClient is not None:
            try:
                client = OllamaClient(str(self.config.get("ai_base_url", "http://localhost:11434")))
                if hasattr(client, "set_model"):
                    client.set_model(str(self.config.get("ai_model", "llama3.2")))
                if client.is_available():
                    self._ollama = client
            except Exception:
                pass
        # El router semantico es opcional; el almacenamiento activo vive en los servicios que lo usan.
        self._router = SemanticRouter() if SemanticRouter is not None else None
        if self._router is not None:
            self._register_semantic_routes()
        # Registro dinámico de comandos
        self.command_registry = CommandRegistry()
        self._register_builtin_commands()
        # Registrar comando de ejemplo: di_hora
        import time as _time
        self.command_registry.register("di_hora", lambda: _time.strftime("%H:%M:%S"))
        # Push-to-talk (Alt izquierda) - se inicializa si está disponible
        try:
            hotkey = str(self.config.get("push_to_talk_hotkey", "left alt") or "left alt")
            self._ptt = PushToTalk(on_recognized=self.process_command, hotkey=hotkey)
            self._ptt.start()
        except Exception:
            self._ptt = None
        # Feedback visual/auditivo de módulos activos
        activos = []
        if getattr(self.voice, 'enabled', False):
            activos.append("Voz")
        if self._ollama:
            activos.append("IA local (Ollama - lenguaje natural activo)")
        elif OllamaClient is not None:
            activos.append("Ollama (modulo cargado pero servidor no disponible)")
        if self._auditor:
            activos.append("Auditor de codigo")
        if self._router:
            activos.append("Router semantico")
        activos.append("NLU local")
        activos.append("Contexto local")
        activos.append("Planificador de tareas")
        activos.append("Memoria persistente")
        activos.append("Herramientas con permisos")
        if getattr(self.personal_activity, "enabled", False):
            activos.append("Monitoreo personal")
        if self.loaded_plugins:
            activos.append(f"Plugins ({sum(1 for p in self.loaded_plugins if not p.error)})")
        self._emit(f"Modulos activos: {', '.join(activos) if activos else 'ninguno'}")

    def _register_builtin_commands(self):
        self.command_registry.register("borrar_evento", self._delete_agenda_item)
        self.command_registry.register("listar_comandos", self.command_registry.list_commands)
        # Puedes registrar más comandos aquí
        # Monitor de actividad
        self._activity_monitor = None
        if ActivityMonitor is not None:
            timeout = int(self.config.get("habit_monitor_timeout_seconds", 600) or 600)
            self._activity_monitor = ActivityMonitor(
                timeout_seconds=timeout,
                on_inactive=self._on_inactive,
                on_active=self._on_active,
                system_idle_provider=windows_system_idle_seconds,
            )
            self._activity_monitor.start()
        # Auditoría automática de capacidades
        if self._auditor is not None:
            result = self._auditor.analyze_file(__file__)
            if result.get("bad_practices"):
                self._emit(f"Advertencia: Se detectaron malas prácticas en assistant.py: {result['bad_practices']}")
            else:
                self._emit("Auditoría de assistant.py: sin malas prácticas detectadas.")

    def _on_inactive(self):
        now = datetime.now()
        daily = self._ensure_daily_state(now)
        daily["last_inactive_at"] = now.isoformat(timespec="seconds")
        self._remember_habit("inactive", now)
        try:
            log_user_action("inactividad detectada", category="monitoreo")
        except Exception:
            pass
        self._save_state()
        self._emit("Detecte un periodo de inactividad. " + self._habit_recommendation_message())

    def _on_active(self, idle_seconds: float = 0.0) -> None:
        now = datetime.now()
        daily = self._ensure_daily_state(now)
        daily["last_active_at"] = now.isoformat(timespec="seconds")
        if idle_seconds:
            daily["last_idle_minutes"] = round(idle_seconds / 60, 1)
        try:
            log_user_action("actividad retomada", category="monitoreo")
        except Exception:
            pass
        self._save_state()

    def _register_semantic_routes(self) -> None:
        """Registra rutas en el SemanticRouter para mapear lenguaje natural a comandos."""
        if self._router is None:
            return
        self._router.register(r"\b(agenda|eventos?|que tengo)\b", lambda t: "agenda")
        self._router.register(r"\b(clima|temperatura|pronostico|lluvia)\b", lambda t: "clima")
        self._router.register(r"\b(clases?|materias?)\b|\bhorario\b(?!\s+de\s+salida)", lambda t: "clases")
        self._router.register(r"\b(presupuesto|balance|gastos?|dinero|plata)\b", lambda t: "presupuesto")
        self._router.register(r"\b(noticias|titulares|novedades)\b", lambda t: "noticias")
        self._router.register(r"\b(abre|abrir|inicia|ejecuta)\b", lambda t: "app")
        self._router.register(r"\b(calcula|calcular|cuanto es|resuelve)\b", lambda t: "math")
        self._router.register(r"\b(habitos?|recomendaciones?|actualiza red neuronal|entrena red neuronal|aprende de mi)\b", lambda t: "habits")
        self._router.register(r"\b(investiga|busca en internet|consulta)\b", lambda t: "research")
        self._router.register(r"\b(recuerdame|recordatorio|avisa)\b", lambda t: "recordatorio")
        self._router.register(r"\b(borra|elimina|quita|limpia)\b.*\b(evento|agenda|recordatorio)\b", lambda t: "borrar")

    def _route_semantic(self, text: str) -> Optional[str]:
        """Intenta clasificar el texto con el router semantico. Retorna una categoria o None."""
        if self._router is None:
            return None
        try:
            result = self._router.route(text)
            return result if isinstance(result, str) else None
        except Exception:
            return None

    def _build_ollama_context(self, now: datetime) -> str:
        """Construye el contexto actual para que Ollama entienda la situacion."""
        parts = []
        parts.append(f"Fecha y hora actual: {self._format_date_spanish(now.date())}, {now.strftime('%H:%M')}.")
        agenda = self.agenda_summary_for_day(now.date())
        parts.append(f"Agenda de hoy: {agenda}")
        classes = self._classes_summary_for_day(now.date())
        if classes:
            parts.append(f"Clases: {classes}")
        parts.append(
            self.brain.context_line(
                now,
                self._agenda_items_for_day(now.date()),
                self._classes_for_day(now.date()),
                self._ensure_daily_state(now),
            )
        )
        try:
            balance = get_balance()
            parts.append(f"Balance: ${balance.get('balance', 0):.2f}")
        except Exception:
            pass
        override = self._current_override(now.date())
        if override.get("free_day"):
            parts.append("Hoy es dia libre.")
        if override.get("classes_cancelled"):
            parts.append("Las clases estan canceladas hoy.")
        if self.pending_dialog:
            parts.append(f"Dialogo pendiente: {self.pending_dialog.get('kind', 'ninguno')}")
        leave_override = self._leave_override_for_day(now.date())
        if leave_override:
            parts.append(f"Salida temporal de hoy: {leave_override}.")
        # Agregar historial reciente para contexto conversacional
        recent = self._get_recent_history(6)
        if recent:
            convo_lines = []
            for msg in recent:
                role = "Kaiser" if msg.get("role") == "user" else "Viernes"
                convo_lines.append(f"{role}: {msg.get('text', '')[:100]}")
            parts.append("Conversacion reciente: " + " | ".join(convo_lines))
        agent_memory = getattr(self, "agent_memory", None)
        if agent_memory is not None:
            memory_context = agent_memory.build_ollama_context("", 1200)
            if memory_context:
                parts.append(memory_context)
        return " | ".join(parts)

    def _ollama_fallback(self, text: str, now: datetime) -> Optional[str]:
        """Usa Ollama como fallback para entender lenguaje natural."""
        if self._ollama is None or generate_ai_response is None:
            return None
        try:
            context = self._build_ollama_context(now)
            response = generate_ai_response(self._ollama, text, context_info=context)
            if response and response.strip():
                return self._emit(response.strip())
        except Exception:
            pass
        return None

    def _greeting_response(self, now: datetime) -> str:
        """Genera un saludo contextual basado en la hora del dia."""
        hour = now.hour
        if hour < 12:
            saludo = "Buenos dias, Senor."
        elif hour < 19:
            saludo = "Buenas tardes, Senor."
        else:
            saludo = "Buenas noches, Senor."
        next_item = self._next_agenda_item_today(now)
        if next_item:
            saludo += f" Lo siguiente en su agenda es {next_item.get('title', 'un evento')} a las {next_item.get('time', '--:--')}."
        else:
            saludo += " No veo compromisos pendientes por ahora. En que le puedo ayudar?"
        return saludo

    def reload(self) -> None:
        self.config = _load_json(CONFIG_PATH, self.config)
        self.state = _load_json(STATE_PATH, self.state)
        self.agenda = _load_json(AGENDA_PATH, self.agenda)

    def save_config(self) -> None:
        _save_json(CONFIG_PATH, self.config)

    def _config_manager(self) -> ViernesConfigManager:
        manager = getattr(self, "config_manager", None)
        if not isinstance(manager, ViernesConfigManager):
            manager = ViernesConfigManager(CONFIG_PATH)
            self.config_manager = manager
        return manager

    def _save_state(self) -> None:
        _save_json(STATE_PATH, self.state)

    def _save_agenda(self) -> None:
        _save_json(AGENDA_PATH, self.agenda)

    def _emit(self, text: str) -> str:
        self.messages.put(("assistant", text))
        self.voice.speak(text)
        self._save_to_history("assistant", text)
        agent_memory = getattr(self, "agent_memory", None)
        if agent_memory is not None:
            try:
                agent_memory.record_conversation("assistant", text)
            except Exception:
                pass
        return text

    def _log_user(self, text: str) -> None:
        self.messages.put(("user", text))
        self._save_to_history("user", text)
        agent_memory = getattr(self, "agent_memory", None)
        if agent_memory is not None:
            try:
                agent_memory.record_conversation("user", text)
            except Exception:
                pass
        # Registrar accion para el tracker de habitos
        try:
            low = normalize_text(text)
            log_user_action(low[:50], category=self._habit_category_for_command(low))
        except Exception:
            pass

    def _habit_category_for_command(self, low: str) -> str:
        if low.startswith(("abre ", "abrir ", "inicia ", "ejecuta ", "lanza ", "pon ")):
            return "apps"
        if low.startswith(("busca ", "buscar ", "investiga ", "consulta ")):
            return "web"
        if low.startswith(("calcula ", "calcular ", "cuanto es ", "resuelve ", "resolver ")):
            return "math"
        if any(token in low for token in ("agenda", "recordatorio", "recuerdame", "evento", "que sigue", "pendiente", "tarea", "compromiso")):
            return "agenda"
        if any(token in low for token in ("presupuesto", "gasto", "ingreso", "balance", "dinero")):
            return "budget"
        if any(token in low for token in ("voz", "microfono", "escucha", "alt")):
            return "voice"
        if any(token in low for token in ("habito", "recomendacion", "aprende", "red neuronal")):
            return "habits"
        if any(token in low for token in ("dime algo", "cuentame", "chiste", "consejo", "frase")):
            return "conversation"
        return "comando"

    def _habit_recommendation_message(self) -> str:
        try:
            return get_habit_recommendations(7)
        except Exception:
            return "Aun no tengo datos suficientes para recomendar habitos."

    def _update_adaptive_model(self, now: datetime) -> str:
        profile = build_adaptive_profile(14)
        activity = self._personal_activity_service().summary(days=14, now=now)
        self.state["habit_summary"] = {
            "version": "local-habit-summary-v2",
            "updated_at": now.isoformat(timespec="seconds"),
            "command_profile": profile,
            "personal_activity": {
                "enabled": bool(activity.get("enabled", False)),
                "total_seconds": int(activity.get("total_seconds", 0) or 0),
                "youtube_seconds": int(activity.get("youtube_seconds", 0) or 0),
                "recommendations": list(activity.get("recommendations", []))[:3],
            },
        }
        self._save_state()
        recommendations = profile.get("recommendations", [])
        summary = " ".join(str(item) for item in recommendations[:3])
        return self._emit(
            "Resumen de habitos actualizado. Mide interacciones con Viernes; no entrena una red neuronal ni modifica codigo. "
            + ("Inclui la actividad personal agregada autorizada. " if activity.get("enabled") else "La actividad personal sigue desactivada. ")
            + (summary or "Aun necesito mas uso para detectar patrones fuertes.")
        )

    def _save_to_history(self, role: str, text: str) -> None:
        """Persiste mensajes al historial para memoria entre sesiones."""
        try:
            history = ChatHistory.load()
            history.append({
                "role": role,
                "text": text,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            })
            ChatHistory.save(history)
        except Exception:
            pass

    def _get_recent_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Recupera los ultimos mensajes del historial."""
        try:
            history = ChatHistory.load()
            return history[-limit:]
        except Exception:
            return []

    def _decide_command(self, original: str, now: datetime) -> IntentDecision:
        return self._intent_arbiter().decide(original, now)

    def _store_last_decision(self, decision: IntentDecision, original: str, now: datetime) -> None:
        payload = decision.to_dict()
        payload["command_preview"] = original[:120]
        payload["timestamp"] = now.isoformat(timespec="seconds")
        self.state["last_intent_decision"] = payload
        daily = self.state.setdefault("daily", {}).setdefault(iso_day(now.date()), {})
        daily["last_intent_decision"] = payload
        self._save_state()

    def _format_decision(self, decision: IntentDecision) -> str:
        slots = ", ".join(f"{key}={value}" for key, value in decision.slots.items() if key != "pattern") or "sin slots"
        confirmation = "si" if decision.requires_confirmation else "no"
        mutation = "si" if decision.mutates else "no"
        return (
            f"Entendi intent={decision.intent}, confianza={decision.confidence:.2f}, "
            f"handler={decision.handler}, riesgo={decision.risk}, cambia datos={mutation}, "
            f"requiere confirmacion={confirmation}. Slots: {slots}. Razon: {decision.reason}."
        )

    def _explain_last_decision(self) -> str:
        raw = self.state.get("last_intent_decision")
        if not isinstance(raw, dict):
            return self._emit("Aun no tengo una decision reciente para explicar.")
        decision = IntentDecision.from_dict(raw)
        command = str(raw.get("command_preview", "") or "").strip()
        prefix = f"Ultimo comando: {command}. " if command else ""
        return self._emit(prefix + self._format_decision(decision))

    def _extract_dry_run_command(self, original: str) -> str:
        text = original.strip()
        text = re.sub(r"^(probar\s+comando|simula\s+comando|prueba\s+sin\s+ejecutar)\s+", "", text, flags=re.IGNORECASE).strip()
        if len(text) >= 2 and text[0] in {"\"", "'"} and text[-1] == text[0]:
            text = text[1:-1].strip()
        return text

    def _dry_run_command(self, original: str, now: datetime) -> str:
        command = self._extract_dry_run_command(original)
        if not command:
            return self._emit("Diga el comando a simular. Ejemplo: probar comando \"cambia salida a las 12 hoy\".")
        decision = self._decide_command(command, now)
        predicted = self._predict_changes_for_decision(command, decision, now)
        evidence = self._evidence_requirements_for_decision(command, decision, now)
        dry_run = CommandDryRun(command=command, decision=decision, predicted_changes=predicted)
        changes = "; ".join(dry_run.predicted_changes) if dry_run.predicted_changes else "sin cambios previstos"
        evidence_text = "; ".join(evidence) if evidence else "respuesta generada"
        return self._emit(
            "Simulacion sin ejecutar: "
            + self._format_decision(dry_run.decision)
            + f" Cambios previstos: {changes}. Evidencia requerida: {evidence_text}."
        )

    def _predict_changes_for_decision(self, command: str, decision: IntentDecision, now: datetime) -> list[str]:
        if decision.intent in {"action_plan", "unprogrammed_help"} or decision.handler == "_plan_unprogrammed_action":
            plan = self._planner().create_plan(command, now)
            if plan is not None:
                return [step.description for step in plan.steps if step.mutates] or ["solo lectura"]
        if decision.intent == "activity_reorganize":
            target_day = self._parse_relative_date(command, now)
            plan = self._build_day_reorganization_plan(target_day, now)
            return [step.description for step in plan.steps if step.mutates]
        if decision.intent in {"cleanup_past_events"}:
            return ["pediria confirmacion antes de borrar eventos pasados"]
        if decision.intent in {"wake_schedule_change", "leave_time_change", "classes_change", "routine_slot_change"}:
            return [f"ejecutaria {decision.handler} con los slots detectados"]
        if decision.intent in {"memory_remember", "memory_preference_set", "personal_rule_create"}:
            return ["guardaria informacion estructurada en memoria local"]
        if decision.mutates:
            return ["aplicaria un cambio despues de confirmacion o validacion del handler"]
        return []

    def _evidence_requirements_for_decision(self, command: str, decision: IntentDecision, now: datetime) -> list[str]:
        if decision.intent in {"action_plan", "unprogrammed_help"} or decision.handler == "_plan_unprogrammed_action":
            plan = self._planner().create_plan(command, now)
            if plan is not None:
                requirements: list[str] = []
                for step in plan.steps:
                    for item in self._tool_registry().verification_requirements(step.action):
                        if item not in requirements:
                            requirements.append(item)
                return requirements
        if decision.intent in {"simulation_request", "research_table", "chart_request", "analysis_report"}:
            return ["resultado estructurado", "reporte o grafica existente cuando aplique"]
        if decision.intent == "game_command":
            low = normalize_text(command)
            if low in {"juegos", "que juegos tienes", "lista juegos", "juegos disponibles", "estado juego", "estado del juego", "tablero", "ver tablero", "ayuda juego", "ayuda del juego"}:
                return ["respuesta generada sin cambios"]
            return ["estado de juego actualizado si la jugada es valida", "recibo rechazado si la jugada es invalida"]
        if decision.intent == "wake_schedule_change":
            return ["configuracion guardada", "tarea Windows reprogramada"]
        if decision.mutates:
            return ["estado posterior verificado"]
        return ["respuesta generada sin cambios"]

    def _audit_commands(self, now: datetime) -> str:
        results: list[str] = []
        failures = 0
        for command, expected in COMMAND_AUDIT_MATRIX:
            decision = self._decide_command(command, now)
            ok = decision.intent == expected
            if not ok:
                failures += 1
            mark = "OK" if ok else "FALLO"
            results.append(f"{mark}: '{command}' -> {decision.intent} (esperado {expected})")
        self.state["last_command_audit"] = {
            "timestamp": now.isoformat(timespec="seconds"),
            "failures": failures,
            "total": len(COMMAND_AUDIT_MATRIX),
        }
        self._save_state()
        head = f"Auditoria de comandos: {len(COMMAND_AUDIT_MATRIX) - failures}/{len(COMMAND_AUDIT_MATRIX)} correctos."
        return self._emit(head + " " + " | ".join(results[:8]) + (f" | y {len(results) - 8} mas." if len(results) > 8 else ""))

    def _tool_capabilities_snapshot(self) -> list[dict[str, Any]]:
        return self._tool_registry().list_tools()

    def _record_execution_receipt(self, receipt: ExecutionReceipt) -> None:
        payload = receipt.to_dict()
        self.state["last_execution_receipt"] = payload
        receipts = self.state.setdefault("execution_receipts", [])
        if not isinstance(receipts, list):
            receipts = []
        receipts.insert(0, payload)
        self.state["execution_receipts"] = receipts[:50]
        self._save_state()

    def _last_execution_receipt(self) -> ExecutionReceipt | None:
        raw = self.state.get("last_execution_receipt")
        if not isinstance(raw, dict):
            return None
        return ExecutionReceipt.from_dict(raw)

    def _format_receipt(self, receipt: ExecutionReceipt) -> str:
        evidence = "; ".join(item.detail for item in receipt.evidence if item.detail) or "sin evidencia confirmada"
        changes = ", ".join(receipt.changed_domains) or "sin cambios"
        errors = "; ".join(receipt.errors) or "sin errores"
        rollback = "si" if receipt.rollback_available else "no"
        return (
            f"Recibo {receipt.id}: estado={receipt.status}, exito={'si' if receipt.success else 'no'}, "
            f"accion={receipt.executed_action}. Evidencia: {evidence}. Cambios: {changes}. "
            f"Errores: {errors}. Rollback disponible: {rollback}."
        )

    def _execution_status_command(self, low: str) -> Optional[str]:
        if low in {"estado de ejecuciones", "estado ejecuciones", "que hiciste realmente", "ver recibo de la ultima accion", "ver recibo ultima accion"}:
            receipt = self._last_execution_receipt()
            if receipt is None:
                return self._emit("Aun no tengo recibos de ejecucion verificable.")
            return self._emit(self._format_receipt(receipt))
        if low in {"por que fallo", "por que falló", "porque fallo", "porque falló"}:
            receipt = self._last_execution_receipt()
            if receipt is None:
                return self._emit("No tengo una ejecucion fallida reciente registrada.")
            if receipt.success:
                return self._emit("La ultima ejecucion registrada fue exitosa. " + self._format_receipt(receipt))
            errors = "; ".join(receipt.errors) or "no se junto evidencia suficiente para confirmar exito"
            return self._emit(f"La ultima ejecucion fallo o quedo sin confirmar porque: {errors}.")
        if low in {"reintenta con verificacion", "reintentar con verificacion"}:
            receipt = self._last_execution_receipt()
            if receipt is None or not receipt.requested_action:
                return self._emit("No tengo una accion reciente para reintentar con verificacion.")
            return self._emit(f"Accion lista para reintento verificable: {receipt.requested_action}. Diga ese comando de nuevo para ejecutarlo.")
        if low in {"estado de herramientas", "herramientas registradas", "estado herramientas"}:
            tools = self._tool_registry().list_tools()
            total = len(tools)
            mutating = sum(1 for item in tools if item.get("mutates"))
            confirmed = sum(1 for item in tools if item.get("requires_confirmation"))
            names = ", ".join(str(item.get("action")) for item in tools[:8])
            return self._emit(f"Herramientas registradas: {total}. Mutantes: {mutating}. Con confirmacion: {confirmed}. Primeras: {names}.")
        if low in {"audita comandos criticos", "audita comandos críticos"}:
            return self._audit_commands(datetime.now())
        if low in {"corrige lo que entendiste", "corrige entendimiento"}:
            return self._emit("Diga 'probar comando \"...\"' para ver como lo entiendo, o escriba el comando corregido con mas datos concretos.")
        if low in {"por que sabes eso", "porque sabes eso"}:
            return self._emit("Lo se por memoria local explicita, preferencias, agenda, rutinas, pendientes o datos de configuracion. Diga 'que sabes de mi' para verlo y 'olvida que...' para corregirlo.")
        return None

    def poll_messages(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        try:
            while True:
                out.append(self.messages.get_nowait())
        except queue.Empty:
            return out

    def _ensure_daily_state(self, now: datetime) -> dict[str, Any]:
        key = iso_day(now.date())
        daily = self.state.setdefault("daily", {})
        if key not in daily:
            daily[key] = {
                "sent": [],
                "bath_done": False,
                "arrived": False,
                "left_home": False,
                "attendance_done": False,
                "day_closed": False,
                "last_companion_chat": "",
                "ambient_news_count": 0,
                "ambient_news_cap": random.randint(2, 3),
                "recent_phrase_keys": [],
                "recent_ambient_topics": [],
                "notes": [],
            }
            self._save_state()
        else:
            daily[key].setdefault("ambient_news_count", 0)
            daily[key].setdefault("ambient_news_cap", random.randint(2, 3))
            daily[key].setdefault("recent_phrase_keys", [])
            daily[key].setdefault("recent_ambient_topics", [])
        return daily[key]

    def _current_override(self, today: date) -> dict[str, Any]:
        return dict(self.state.get("day_overrides", {}).get(iso_day(today), {}))

    def _leave_override_for_day(self, day: date) -> Optional[str]:
        value = self._current_override(day).get("leave_time")
        if isinstance(value, str) and re.fullmatch(r"\d{2}:\d{2}", value.strip()):
            return value.strip()
        return None

    def _reminders_with_leave_override(self, day: date, reminders: list[dict[str, Any]]) -> list[dict[str, Any]]:
        leave_time = self._leave_override_for_day(day)
        copied = [dict(item) for item in reminders]
        if not leave_time:
            return copied
        leave_ids = {"leave_checklist", "thursday_leave", "friday_leave_checklist"}
        for item in copied:
            item_id = normalize_text(str(item.get("id", "")))
            if item_id in leave_ids:
                item["time"] = leave_time
        return copied

    def _remember_habit(self, habit: str, now: datetime) -> None:
        history = self.state.setdefault("habit_history", [])
        history.append(
            {"habit": habit, "timestamp": now.isoformat(timespec="minutes"), "weekday": weekday_key(now.date())}
        )
        self.state["habit_history"] = history[-400:]
        self._save_state()

    def _agenda_items_for_day(self, today: date) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for item in self.agenda.get("items", []):
            if bool(item.get("paused", False)):
                continue
            recurring = str(item.get("recurring", "") or "")
            if str(item.get("date", "")) == iso_day(today):
                items.append(item)
            elif recurring == "weekly" and item.get("weekday") == weekday_key(today):
                items.append(item)
            elif recurring == "daily":
                items.append(item)
            elif recurring == "weekly_multi" and weekday_key(today) in list(item.get("weekdays", [])):
                items.append(item)
        items.sort(key=lambda x: (str(x.get("time", "")), str(x.get("title", ""))))
        return items

    def agenda_summary_for_day(self, today: date) -> str:
        items = self._agenda_items_for_day(today)
        if not items:
            return "No hay nada en la agenda para hoy."
        return "Agenda de hoy: " + "; ".join(
            f"{item.get('time', '--:--')} {item.get('title', 'Evento')}" for item in items
        )

    def _agenda_summary_for_target_day(self, target_day: date) -> str:
        items = self._agenda_items_for_day(target_day)
        label = self._format_date_spanish(target_day)
        if not items:
            return f"No hay eventos en la agenda para {label}."
        detail = "; ".join(
            f"{item.get('time', '--:--')} {item.get('title', 'Evento')}" for item in items
        )
        return f"Agenda para {label}: {detail}."

    def _agenda_items_between(self, start_day: date, end_day: date) -> dict[date, list[dict[str, Any]]]:
        grouped: dict[date, list[dict[str, Any]]] = {}
        cursor = start_day
        while cursor <= end_day:
            items = self._agenda_items_for_day(cursor)
            if items:
                grouped[cursor] = items
            cursor += timedelta(days=1)
        return grouped

    def _format_date_spanish(self, day: date) -> str:
        return f"{WEEKDAY_LABELS[weekday_key(day)]} {day.day} de {MONTH_LABELS[day.month]}"

    def _agenda_range_summary(self, start_day: date) -> str:
        if weekday_key(start_day) == "friday":
            end_day = start_day + timedelta(days=4)
        else:
            end_day = start_day + timedelta(days=(6 - start_day.weekday()))
        grouped = self._agenda_items_between(start_day, end_day)
        if not grouped:
            return "No hay eventos en la agenda para el resto del periodo."
        parts = []
        for day in sorted(grouped):
            detail = ", ".join(
                f"{item.get('time', '--:--')} {item.get('title', 'Evento')}" for item in grouped[day]
            )
            parts.append(f"{self._format_date_spanish(day)}: {detail}")
        return "Agenda desde hoy: " + " | ".join(parts)

    def full_agenda_summary(self) -> str:
        return build_full_agenda_summary(list(self.agenda.get("items", [])), WEEKDAY_LABELS)

    def get_all_agenda_items(self) -> list[dict[str, Any]]:
        return sort_agenda_items(list(self.agenda.get("items", [])))

    def gui_add_agenda_item(self, title: str, date_text: str, time_text: str, category: str = "evento") -> str:
        self.reload()
        title = title.strip() or "Evento"
        target_day = date.fromisoformat(date_text.strip())
        hhmm = self._parse_time(time_text.strip()) or time_text.strip()
        self._add_agenda_item(title, target_day, hhmm, category=category)
        return self._emit(f"Quedo agendado: {title} el {iso_day(target_day)} a las {hhmm}.")

    def gui_delete_agenda_item(self, item_id: str) -> str:
        self.reload()
        item = next((x for x in self.agenda.get("items", []) if str(x.get("id")) == str(item_id)), None)
        if not item:
            return self._emit("No encontre ese evento en la agenda.")
        self._delete_agenda_item(str(item_id))
        return self._emit(f"Elimine de la agenda: {item.get('title', 'Evento')}.")

    def gui_set_agenda_paused(self, item_id: str, paused: bool) -> str:
        self.reload()
        item = next((x for x in self.agenda.get("items", []) if str(x.get("id")) == str(item_id)), None)
        if not item:
            return self._emit("No encontre ese evento en la agenda.")
        self._set_agenda_paused(str(item_id), paused)
        action = "Pausado" if paused else "Reactivado"
        return self._emit(f"{action}: {item.get('title', 'Evento')}.")

    def _open_meteo_weather_line(self) -> Optional[str]:
        if fetch_open_meteo_current is None:
            return None
        lat = self.config.get("weather_lat")
        lon = self.config.get("weather_lon")
        if lat is None or lon is None:
            return None
        try:
            return f"Clima (Open-Meteo): {fetch_open_meteo_current(float(lat), float(lon))}"
        except Exception:
            return None

    def _weather_summary(self) -> str:
        om = self._open_meteo_weather_line()
        if om:
            return om
        city = str(self.config.get("default_city", "Colima, Colima, Mexico")).strip()
        if not city:
            return "No tengo ciudad configurada para revisar el clima."
        try:
            encoded = urllib.parse.quote(city)
            request = urllib.request.Request(
                f"https://wttr.in/{encoded}?format=j1",
                headers={"User-Agent": "Viernes/1.0"},
            )
            with urllib.request.urlopen(request, timeout=6) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            try:
                fallback_request = urllib.request.Request(
                    f"https://wttr.in/{encoded}?format=%C|%t",
                    headers={"User-Agent": "Viernes/1.0"},
                )
                with urllib.request.urlopen(fallback_request, timeout=6) as response:
                    raw = response.read().decode("utf-8").strip()
                if raw:
                    return f"Clima en {city}: {raw.replace('|', ', ')}."
            except Exception:
                pass
            return f"No pude consultar el clima ahora mismo para {city}. Revise su conexion o intente de nuevo en unos minutos."
        current = (payload.get("current_condition") or [{}])[0]
        forecast = (payload.get("weather") or [{}])[0]
        desc = str(((current.get("weatherDesc") or [{}])[0]).get("value", "")).strip().lower() or "sin descripcion"
        temp_c = str(current.get("temp_C", "")).strip()
        max_rain = 0
        for hour in forecast.get("hourly", []) or []:
            try:
                max_rain = max(max_rain, int(str(hour.get("chanceofrain", "0"))))
            except ValueError:
                pass
        sky = "con probabilidad de lluvia" if max_rain >= 40 else "sin lluvia probable"
        temp_part = f" Temperatura actual: {temp_c} grados." if temp_c else ""
        return f"Clima en {city}: {desc}, {sky}.{temp_part}"

    def _classes_for_day(self, target_day: date) -> list[str]:
        return service_classes_for_day(self.state, self.config, target_day, iso_day, weekday_key)

    def _classes_summary_for_day(self, target_day: date) -> str:
        return service_classes_summary_for_day(self.state, self.config, target_day, iso_day, weekday_key)

    def _classes_summary_for_target_day(self, target_day: date) -> str:
        classes = self._classes_for_day(target_day)
        label = self._format_date_spanish(target_day)
        if not classes:
            return f"No hay clases registradas para {label}."
        return f"Clases para {label}: " + ", ".join(classes) + "."

    def _build_today_status(self, now: datetime) -> str:
        override = self._current_override(now.date())
        classes = self._classes_for_day(now.date())
        parts: list[str] = []
        if override.get("free_day"):
            parts.append("Hoy esta marcado como dia libre.")
        if override.get("classes_cancelled"):
            parts.append("Hoy estan canceladas las clases.")
        leave_override = self._leave_override_for_day(now.date())
        if leave_override:
            parts.append(f"Salida temporal: {leave_override}.")
        if classes:
            parts.append("Clases: " + ", ".join(classes))
        parts.append(self.agenda_summary_for_day(now.date()))
        return " ".join(parts)

    def _build_day_status(self, target_day: date) -> str:
        override = self._current_override(target_day)
        parts: list[str] = [f"Para {self._format_date_spanish(target_day)}:"]
        if override.get("free_day"):
            parts.append("Esta marcado como dia libre.")
        if override.get("classes_cancelled"):
            parts.append("Las clases estan marcadas como canceladas.")
        leave_override = self._leave_override_for_day(target_day)
        if leave_override:
            parts.append(f"Salida temporal: {leave_override}.")
        classes = self._classes_summary_for_target_day(target_day)
        if classes:
            parts.append(classes)
        parts.append(self._agenda_summary_for_target_day(target_day))
        return " ".join(parts)

    def _has_calendar_date_reference(self, low: str) -> bool:
        if any(name in low.split() for name in WEEKDAY_NAMES):
            return True
        if any(token in low for token in ("hoy", "manana", "/")):
            return True
        return bool(re.search(r"\b\d{1,2}\s+de\s+[a-z]+(?:\s+de\s+\d{4})?\b", low))

    def _day_query_command(self, low: str, _original: str, now: datetime) -> Optional[str]:
        if not self._has_calendar_date_reference(low):
            return None
        if low.startswith((
            "agrega ",
            "agregar ",
            "anade ",
            "registrar ",
            "registra ",
            "pon ",
            "cambia ",
            "cambiar ",
            "modifica ",
            "modificar ",
            "ajusta ",
            "ajustar ",
            "mueve ",
            "mover ",
            "recuerdame ",
            "recordatorio ",
            "tengo clases ",
        )):
            return None

        calendar_word = any(
            word in low for word in ("agenda", "clase", "clases", "horario", "evento", "eventos", "pendiente", "pendientes")
        )
        broad_question = low.startswith(("que tengo", "que toca", "que me toca", "que viene"))
        generic_day_question = low.startswith("que hay") and not any(
            word in low for word in ("noticias", "clima", "presupuesto", "balance", "dinero")
        )
        query_start = broad_question or generic_day_question or (
            calendar_word
            and low.startswith((
                "que hay",
                "revisa",
                "revisame",
                "muestra",
                "mostrar",
                "ver",
                "consulta",
            ))
        )
        direct_calendar_query = re.match(
            rf"^(agenda|agendas|clase|clases|horario|eventos|pendientes)(?:\s+(?:de|del|para|el|en))?\s+",
            low,
        )
        if not query_start and not direct_calendar_query:
            return None
        if direct_calendar_query and not query_start:
            weekday_tail = re.sub(rf"^.*?\b{WEEKDAY_RE}\b", "", low, count=1).strip()
            weekday_tail = re.sub(r"\b(por favor|favor)\b", " ", weekday_tail).strip()
            if any(name in low.split() for name in WEEKDAY_NAMES) and weekday_tail:
                return None

        target_day = self._parse_relative_date(low, now)
        wants_agenda = any(word in low for word in ("agenda", "evento", "eventos", "pendiente", "pendientes"))
        wants_classes = "clase" in low or "horario" in low
        broad_question = low.startswith(("que tengo", "que toca", "que me toca", "que viene")) or (
            low.startswith("que hay") and not wants_agenda and not wants_classes
        )

        if wants_agenda and not wants_classes and not broad_question:
            return self._emit(self._agenda_summary_for_target_day(target_day))
        if wants_classes and not wants_agenda and not broad_question:
            return self._emit(self._classes_summary_for_target_day(target_day))
        return self._emit(self._build_day_status(target_day))

    def _next_commitment_summary(self, now: datetime) -> str:
        next_task = self._task_store().next_task(now)
        if next_task is not None and (not next_task.due_date or next_task.due_date <= iso_day(now.date())):
            due = ""
            if next_task.due_date:
                due = f" vence {next_task.due_date}"
                if next_task.due_time:
                    due += f" a las {next_task.due_time}"
            return f"Lo siguiente pendiente es {next_task.title}.{due}"
        next_item = self._next_agenda_item_today(now)
        if next_item:
            return (
                f"Lo siguiente en su agenda es {next_item.get('title', 'un evento')} "
                f"a las {next_item.get('time', '--:--')}."
            )
        if next_task is not None:
            due = f" para {next_task.due_date}" if next_task.due_date else ""
            return f"No veo mas eventos hoy. Pendiente proximo: {next_task.title}{due}."
        classes = self._classes_for_day(now.date())
        if classes:
            return "No veo mas eventos hoy, pero sus clases registradas son: " + ", ".join(classes) + "."
        return "Por ahora no veo mas compromisos registrados para hoy."

    def system_status_snapshot(self) -> dict[str, str]:
        status = get_resident_status()
        return {
            "startup": status["startup"],
            "task": status["task"],
            "wake_time": status["wake_time"],
            "next_run": status.get("next_run", "desconocido"),
            "action": status.get("action", "desconocida"),
            "voice": "activo" if bool(self.config.get("voice_enabled", True)) else "inactivo",
            "speech_input": "activo" if speech_input_available() else "no disponible",
            "telegram": "activo" if self._telegram_notifier().is_enabled() else "inactivo",
        }

    def config_snapshot(self) -> dict[str, Any]:
        snapshot = self._config_manager().snapshot(self.config)
        last_validation = self.state.get("last_config_validation", {})
        if isinstance(last_validation, dict):
            snapshot["last_validation"] = dict(last_validation)
        return snapshot

    def _apply_runtime_config(self) -> None:
        voice = getattr(self, "voice", None)
        if voice is not None:
            try:
                voice.enabled = bool(self.config.get("voice_enabled", True))
                voice.rate = int(self.config.get("tts_rate", 165) or 165)
            except Exception:
                pass

    def apply_gui_config_patch(self, patch: dict[str, Any]) -> ConfigValidationResult:
        result = self._config_manager().apply_patch(patch, base_config=self.config)
        self.state["last_config_validation"] = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "valid": result.valid,
            "errors": list(result.errors),
            "warnings": list(result.warnings),
        }
        if result.valid:
            self.config = result.normalized
            self._apply_runtime_config()
        self._save_state()
        return result

    def apply_wake_config_from_gui(self, wake_time: str) -> str:
        result = self._config_manager().validate_patch(
            {"automation": {"morning_wake_time": wake_time}},
            base_config=self.config,
        )
        if not result.valid:
            return self._emit("No guarde la rutina matutina: " + " ".join(result.errors))
        ok = setup_morning_wake(wake_time)
        if ok:
            self.reload()
            return self._emit(
                f"Rutina matutina verificada y reprogramada a las {wake_time}. "
                "Puede intentar reactivar desde suspension compatible; no enciende ni desbloquea Windows."
            )
        return self._emit(f"Windows no confirmo la tarea de rutina para las {wake_time}; no cambie la configuracion activa.")

    def apply_resident_config_from_gui(self, startup_enabled: bool, morning_enabled: bool, wake_time: str) -> str:
        """Apply the two Windows integrations and only reflect states they verify."""
        validation = self._config_manager().validate_patch(
            {"automation": {"morning_wake_time": wake_time}},
            base_config=self.config,
        )
        if not validation.valid:
            return self._emit("No aplique la configuracion de inicio: " + " ".join(validation.errors))

        startup_ok = set_startup_enabled(bool(startup_enabled))
        wake_ok = setup_morning_wake(wake_time) if morning_enabled else remove_scheduled_task()
        if startup_ok and wake_ok:
            self.reload()
            startup_label = "activo" if startup_enabled else "inactivo"
            routine_label = "activa" if morning_enabled else "inactiva"
            return self._emit(
                f"Inicio de sesion {startup_label} y rutina matutina {routine_label}, ambos verificados por Windows. "
                "La rutina no enciende un equipo apagado ni desbloquea Windows."
            )

        failures = []
        if not startup_ok:
            failures.append("inicio de sesion")
        if not wake_ok:
            failures.append("rutina matutina")
        return self._emit(
            "Windows no confirmo " + " y ".join(failures)
            + "; el estado de cada capacidad solo se actualiza cuando Windows la verifica. Revise el diagnostico."
        )

    def reset_sent_for_changed_routines(self, changed_ids: list[str], target_days: list[date | str]) -> None:
        if not changed_ids or not target_days:
            return
        normalized_ids = {str(item).strip() for item in changed_ids if str(item).strip()}
        if not normalized_ids:
            return
        daily_state = self.state.setdefault("daily", {})
        changed = False
        for target in target_days:
            day_key = target.isoformat() if isinstance(target, date) else str(target)
            daily = daily_state.get(day_key)
            if not isinstance(daily, dict):
                continue
            sent = list(daily.get("sent", []))
            kept = [event_id for event_id in sent if not self._sent_event_matches_routine(event_id, normalized_ids)]
            if kept != sent:
                daily["sent"] = kept
                daily["day_closed"] = False
                changed = True
        if changed:
            self._save_state()

    def _sent_event_matches_routine(self, event_id: str, changed_ids: set[str]) -> bool:
        if event_id in changed_ids:
            return True
        parts = event_id.split(":")
        tail = parts[-1] if parts else event_id
        if tail in changed_ids:
            return True
        if len(parts) >= 2 and f"{parts[0]}:{parts[1]}" in changed_ids:
            return True
        for changed_id in changed_ids:
            if changed_id.endswith("_bath") or changed_id in {"bath", "monday_bath", "thursday_bath"}:
                if event_id.startswith(changed_id + ":") or (changed_id == "bath" and event_id.startswith("bath:")):
                    return True
        return False

    def _phrase_key(self, text: str) -> str:
        return normalize_text(text)[:100]

    def _conversation_options(self, key: str, fallback: list[str]) -> list[str]:
        values = self.config.get("conversation", {}).get(key, [])
        raw_options: list[Any] = list(fallback)
        if isinstance(values, list):
            raw_options.extend(values)
        elif isinstance(values, str):
            raw_options.append(values)

        options: list[str] = []
        seen: set[str] = set()
        for value in raw_options:
            option = str(value).strip()
            if "Â" in option or "Ã" in option:
                continue
            option_key = self._phrase_key(option)
            if option and option_key not in seen:
                options.append(option)
                seen.add(option_key)
        return options or [str(x).strip() for x in fallback if str(x).strip()]

    def _recent_phrase_keys(self, daily: Optional[dict[str, Any]] = None) -> list[str]:
        holder = daily if daily is not None else self.state.setdefault("conversation_memory", {})
        recent = holder.get("recent_phrase_keys", [])
        if not isinstance(recent, list):
            recent = []
        holder["recent_phrase_keys"] = recent
        return recent

    def _remember_phrase(self, text: str, daily: Optional[dict[str, Any]] = None) -> None:
        key = self._phrase_key(text)
        if not key:
            return
        recent = self._recent_phrase_keys(daily)
        if key in recent:
            recent.remove(key)
        recent.append(key)
        del recent[:-14]
        self._save_state()

    def _pick_phrase(self, key: str, fallback: list[str], *, daily: Optional[dict[str, Any]] = None) -> str:
        options = self._conversation_options(key, fallback)
        recent = set(self._recent_phrase_keys(daily))
        fresh = [option for option in options if self._phrase_key(option) not in recent]
        choice = random.choice(fresh or options)
        self._remember_phrase(choice, daily)
        return choice

    def _pick_ambient_topic(self, daily: dict[str, Any], topics: list[str]) -> str:
        if not topics:
            return "small_talk"
        recent = daily.get("recent_ambient_topics", [])
        if not isinstance(recent, list):
            recent = []
        fresh = [topic for topic in topics if topic not in set(recent)]
        topic = random.choice(fresh or topics)
        if topic in recent:
            recent.remove(topic)
        recent.append(topic)
        daily["recent_ambient_topics"] = recent[-7:]
        self._save_state()
        return topic

    def _topic_phrase(self, topic: str, daily: Optional[dict[str, Any]] = None) -> str:
        if topic == "habits":
            return self._habit_recommendation_message()
        fallbacks = {
            "small_talk": [
                "Estaba pensando en algo: si hoy se siente pesado, podemos bajarlo a una sola accion clara y empezar por ahi.",
                "Me gustaria proponerle algo sencillo: revisar que sigue, cerrar lo urgente y dejar espacio para pensar.",
                "A veces el dia no necesita mas fuerza; necesita menos ruido. Puedo ayudarle a ordenar ese ruido.",
                "Si tiene ganas, podemos tomar un tema al azar y conversarlo un poco; no todo tiene que ser pendiente.",
                "Hay dias en los que conviene moverse con calma y precision. Yo puedo ayudarle a cuidar ese ritmo.",
            ],
            "study": [
                "Tema de estudio: elegir una pregunta concreta antes de abrir apuntes suele hacer que el bloque rinda mas.",
                "Para estudiar sin saturarse, puede empezar con diez minutos de repaso activo y luego decidir si aumenta el bloque.",
                "Una forma limpia de avanzar es explicar el tema en voz alta como si se lo contara a alguien mas.",
                "Si una materia se siente grande, la dividimos en conceptos, ejercicios y dudas. Asi deja de verse como una pared.",
            ],
            "planning": [
                "Idea de planeacion: separar lo fijo, lo urgente y lo opcional deja el dia mucho mas manejable.",
                "Podemos hacer una jugada simple: definir lo que no debe fallar hoy y dejar lo demas en segundo plano.",
                "Cuando el dia esta cargado, una lista de tres prioridades suele funcionar mejor que una lista perfecta.",
                "Si quiere, podemos revisar el siguiente compromiso y preparar solo lo necesario para ese tramo.",
            ],
            "wellbeing": [
                "Chequeo rapido: agua, postura y respiracion. A veces el sistema mejora antes que la agenda.",
                "Un descanso real de cinco minutos puede rendir mas que seguir empujando con la cabeza cansada.",
                "Si nota la mente muy llena, conviene escribir lo pendiente y sacar esa carga de la memoria inmediata.",
                "No todo avance tiene que ser intenso. Tambien sirve mantener el equilibrio para llegar mejor al final del dia.",
            ],
            "curiosity": [
                "Curiosidad: la memoria suele recordar mejor cuando conecta una idea con un lugar, una imagen o una historia.",
                "Tema curioso: muchas decisiones parecen logicas despues, pero nacen de pequenos habitos repetidos.",
                "Algo interesante: cambiar de contexto por unos minutos puede ayudar a ver un problema desde otro angulo.",
                "La atencion funciona mejor con limites claros; por eso un bloque corto bien definido puede sentirse mas facil.",
            ],
            "tech": [
                "Tema tecnologico: una IA util no solo responde; tambien debe notar patrones y ayudar a decidir el siguiente paso.",
                "En automatizacion, lo valioso no es hacer muchas cosas, sino quitar friccion de lo que se repite cada dia.",
                "Una buena interfaz deberia sentirse casi invisible: mostrar lo importante sin obligarlo a pelear con la pantalla.",
                "La memoria de Viernes va a ser mas util cuando conecte hora, contexto y habitos, no solo comandos sueltos.",
            ],
            "money": [
                "Idea de presupuesto: separar gastos inevitables de compras impulsivas ayuda a decidir sin culpa y sin sorpresa.",
                "Una revision breve del balance antes de gastar puede evitar ajustes molestos al final de la semana.",
                "Si quiere mejorar control financiero, conviene mirar categorias, no solo el total gastado.",
                "El dinero se entiende mejor por patrones: que se repite, que sube y que puede esperar.",
            ],
            "reflection": [
                "Pensamiento breve: no todos los avances hacen ruido, pero los constantes terminan notandose.",
                "A veces la mejor decision no es hacer mas, sino escoger mejor donde poner energia.",
                "La claridad no siempre aparece antes de empezar; muchas veces aparece cuando ya dio el primer paso.",
                "Si hoy algo sale torcido, lo ajustamos. Un dia util no necesita ser perfecto.",
            ],
            "facts": [
                "Dato curioso: la luz del Sol tarda alrededor de ocho minutos en llegar a la Tierra.",
                "Dato curioso: el vidrio puede reciclarse muchas veces sin perder demasiada calidad.",
                "Dato curioso: el primer correo electronico se envio en 1971.",
                "Dato curioso: el cerebro consolida parte de la memoria durante el descanso.",
                "Dato curioso: un segundo atomico se define usando oscilaciones del cesio 133.",
            ],
            "tips": [
                "Consejo breve: defina solo la siguiente accion concreta; no necesita resolver todo el mapa de una vez.",
                "Consejo breve: si una tarea le pesa, reduzca el inicio a dos minutos y deje que el impulso haga el resto.",
                "Consejo breve: revise primero lo que tiene hora fija. Eso ordena el resto del dia.",
                "Consejo breve: deje preparado lo que usara al salir; baja la friccion cuando ya hay prisa.",
                "Consejo breve: una pausa corta con pantalla lejos suele aclarar mas de lo que parece.",
            ],
            "quotes": [
                "La disciplina tranquila suele vencer a la motivacion pasajera.",
                "Avanzar un poco cada dia tambien cuenta como progreso serio.",
                "Hacer primero lo importante simplifica el resto del dia.",
                "La claridad en los siguientes pasos reduce mucho el desgaste mental.",
                "Lo constante no siempre se ve heroico, pero construye casi todo lo que dura.",
            ],
            "stories": [
                "Historia breve: una persona llevaba dias aplazando una idea porque parecia demasiado grande. Una manana decidio escribir solo la primera linea. Esa linea no resolvio todo, pero abrio la puerta. Al final del dia no tenia una obra terminada; tenia algo mejor, una forma de empezar sin miedo.",
                "Historia breve: alguien ordeno su escritorio buscando productividad y encontro una nota vieja con una meta olvidada. No era una meta enorme, solo una promesa sencilla. La puso al frente y trabajo veinte minutos. A veces el futuro no pide una revolucion, solo que recordemos donde lo dejamos.",
                "Historia breve: en una noche pesada, una pantalla en blanco parecia ganar. Entonces la persona escribio la pregunta exacta que queria responder. La respuesta no llego completa, pero el problema se hizo mas pequeno. Desde ahi, cada paso encontro al siguiente.",
            ],
            "jokes": [
                "Le iba a contar un chiste de Wi-Fi, pero se perdio la conexion.",
                "Un error entro a produccion y dijo: tranquilo, solo vengo a conocer.",
                "Mi teclado queria vacaciones, pero dejo todo en pausa.",
                "El codigo compilo a la primera. Nadie se movio. Todos sospecharon.",
            ],
        }
        return self._pick_phrase(topic, fallbacks.get(topic, fallbacks["small_talk"]), daily=daily)

    def _natural_topic_response(self, daily: dict[str, Any], *, allow_news: bool = True) -> tuple[str, str]:
        topics = [
            "small_talk",
            "study",
            "planning",
            "wellbeing",
            "curiosity",
            "tech",
            "money",
            "reflection",
            "facts",
            "tips",
            "habits",
        ]
        if allow_news:
            topics.append("news")
        topic = self._pick_ambient_topic(daily, topics)
        if topic == "news":
            return self._news_summary(max_items=1), "ambient_news"
        return self._topic_phrase(topic, daily=daily), "ambient"

    def _preferred_news_topic(self) -> str:
        news_preferences = self.config.get("news_preferences", {})
        topic = str(news_preferences.get("preferred_topic", "world") or "world").strip().lower()
        allowed = {"world", "general", "technology", "science", "mexico"}
        return topic if topic in allowed else "world"

    def _news_summary(self, max_items: int = 2) -> str:
        raw = get_news(self._preferred_news_topic(), max_items=max_items)
        low = normalize_text(raw)
        if low.startswith("no pude obtener noticias") or low.startswith("error al obtener noticias"):
            return raw
        lines = [line.strip("- ").strip() for line in raw.splitlines() if line.strip()]
        if lines and normalize_text(lines[0]) == "noticias":
            lines = lines[1:]
        if lines and normalize_text(lines[0]) == "noticias guardadas":
            lines = lines[1:]
        if not lines:
            return "No encontre titulares recientes en este momento."
        picked = lines[:max_items]
        return "Noticias destacadas: " + " | ".join(picked)

    def _compose_morning_brief(self, now: datetime, arrived_monday: bool = False) -> str:
        return self._compose_smart_daily_brief(now, arrived_monday=arrived_monday)

    def _compose_smart_daily_brief(
        self,
        now: datetime,
        *,
        target_day: Optional[date] = None,
        arrived_monday: bool = False,
    ) -> str:
        day = target_day or now.date()
        is_today = day == now.date()
        label = "hoy" if is_today else self._format_date_spanish(day)
        intro = f"Briefing inteligente de {label}. Hoy es {self._format_date_spanish(now.date())}."
        day_key = weekday_key(now.date())
        extras: list[str] = []
        if is_today and day_key == "monday":
            extras.append(
                " Ya registre su llegada y el pase de lista de hoy."
                if arrived_monday
                else " Hoy el pase de lista se hace cuando usted me diga que ya llego."
            )
        elif is_today and day_key == "thursday":
            extras.append("Hoy sale temprano por su clase de ingles; conviene revisar salida y preparacion.")
        elif is_today and day_key == "friday":
            extras.append("Hoy conviene contemplar pendientes para lunes y martes de la siguiente semana.")
        wake = self._wake_schedule_summary(now, target_day=day, include_live_status=False)
        weather = self._weather_summary() if is_today else ""
        classes = self._classes_summary_for_target_day(day)
        agenda = self._agenda_summary_for_target_day(day)
        pending = self._task_store().summary_for_day(day)
        calendar = self._activity_calendar_for_day(day, now)
        next_block = calendar.next_block(now) if is_today else (calendar.blocks[0] if calendar.blocks else None)
        next_action = (
            f"Siguiente accion: {next_block.title} de {next_block.start} a {next_block.end}."
            if next_block is not None
            else "Siguiente accion: no veo bloques operativos pendientes para ese dia."
        )
        risks = self._daily_risk_summary(day, now)
        daily = self._ensure_daily_state(now) if is_today else {}
        proactive = self._format_proactive_suggestions(self._proactive_suggestions(now, daily), limit=1) if is_today else ""
        news = self._news_summary(max_items=2) if is_today else ""
        segments = [
            " ".join([intro, *extras]).strip(),
            wake.strip(),
            weather.strip(),
            classes.strip(),
            agenda.strip(),
            pending.strip(),
            next_action.strip(),
            risks.strip(),
            proactive.strip(),
            news.strip(),
        ]
        return " | ".join(segment for segment in segments if segment)

    def _daily_risk_summary(self, target_day: date, now: datetime) -> str:
        risks: list[str] = []
        override = self._current_override(target_day)
        classes = [] if override.get("free_day") or override.get("classes_cancelled") else self._classes_for_day(target_day)
        leave_time = self._configured_leave_time_for_day(target_day)
        if classes and leave_time:
            risks.append(f"hay clases y salida configurada a las {leave_time}")
        due_tasks = self._task_store().tasks_for_day(target_day)
        high_tasks = [task for task in due_tasks if task.priority == "high"]
        if high_tasks:
            risks.append(f"{len(high_tasks)} pendiente(s) de prioridad alta")
        elif due_tasks:
            risks.append(f"{len(due_tasks)} pendiente(s) para el dia")
        agenda = self._agenda_items_for_day(target_day)
        if len(agenda) >= 3:
            risks.append(f"{len(agenda)} eventos en agenda")
        if target_day == now.date():
            past = len(self._past_agenda_items(now.date()))
            if past:
                risks.append(f"{past} evento(s) pasado(s) por limpiar")
        if not risks:
            return "Riesgos: no veo riesgos operativos fuertes."
        return "Riesgos: " + "; ".join(risks) + "."

    def _wake_schedule_summary(
        self,
        now: datetime,
        *,
        target_day: Optional[date] = None,
        include_live_status: bool = True,
    ) -> str:
        day = target_day or now.date()
        wake_time = str(self.config.get("automation", {}).get("morning_wake_time", "07:30"))
        status = get_resident_status() if include_live_status else {}
        if include_live_status:
            wake_time = str(status.get("wake_time") or wake_time)
        label = "manana" if day == now.date() + timedelta(days=1) else "hoy" if day == now.date() else self._format_date_spanish(day)
        live = ""
        if include_live_status:
            live = (
                f" Autoarranque {status.get('startup', 'desconocido')}, "
                f"tarea programada {status.get('task', 'desconocido')}, "
                f"proxima ejecucion {status.get('next_run', 'desconocido')}."
            )
        return (
            f"Autoarranque y rutina de la manana: hora configurada {wake_time}. "
            f"Para {label}, la rutina matutina se inicia cuando Windows ejecute la tarea programada "
            f"Viernes Morning Wake a esa hora.{live} "
            "Para que funcione, la laptop debe quedar en suspension y Windows debe permitir temporizadores de reactivacion."
        )

    def capabilities_summary(self) -> str:
        return (
            "Puedo ofrecerle un informe del dia, revisar el clima (wttr u Open-Meteo si configura weather_lat/lon), "
            "consultar su agenda completa "
            "o solo lo de hoy, agregar, modificar y eliminar eventos o recordatorios, "
            "gestionar pendientes y compromisos con fechas, prioridades, completado y posposicion, "
            "gestionar clases por dia, confirmar llegada y bano, abrir aplicaciones compatibles, "
            "administrar su presupuesto con ingresos, gastos, correcciones, eliminaciones, categorias y limites, "
            "ver y modificar rutinas por voz o texto, "
            "leer noticias desde varias fuentes RSS con cache local, buscar en linea y guardar investigaciones utiles, "
            "usar NLU local para mapear frases naturales a comandos y un cerebro contextual para peticiones ambiguas, "
            "aprender de sus habitos de uso, recomendar ajustes y activar o desactivar la voz, "
            "sugerir alias para comandos repetidos, "
            "dar sugerencias proactivas operativas sin ejecutar cambios automaticamente, "
            "mostrar acciones recientes y deshacer el ultimo plan confirmado, "
            "crear planes de agente para objetivos complejos, enrutar herramientas con permisos, "
            "cargar plugins locales, mantener memoria persistente en runtime/memory, "
            "hacer auto-mejora controlada solo mediante propuestas y pruebas, "
            "monitorear seguridad de forma pasiva con recomendaciones, "
            "calcular expresiones matematicas de forma segura (calcula/cuanto es/resuelve), enviar Wake-on-LAN (wol ...), "
            "y ejecutar un diagnostico de sintaxis del proyecto."
        )

    def _jarvis_extended_commands(self, low: str, original: str) -> Optional[str]:
        """Capacidades integradas desde jarvis_os_v5: calculo seguro, WOL, diagnostico AST."""
        if low.startswith("calcula ") or low.startswith("calcular "):
            if safe_eval_math is None:
                return self._emit("El modulo de calculo seguro (jarvis_os_v5) no esta disponible.")
            expr = re.sub(r"^(calcula|calcular)\s+", "", original, count=1, flags=re.IGNORECASE).strip()
            try:
                val = safe_eval_math(expr)
                return self._emit(f"Resultado: {val}")
            except Exception as e:
                return self._emit(f"No pude calcular: {e}")

        wol_triggers = (
            "wake on lan",
            "despierta otro equipo",
            "magic packet",
            "enviar wol",
            "encender otro pc",
        )
        if low in wol_triggers or low.startswith("wol "):
            mac = str(self.config.get("wol_mac") or "").strip()
            if low.startswith("wol "):
                parts = original.strip().split(None, 1)
                if len(parts) > 1 and parts[1].strip():
                    mac = parts[1].strip().split()[0]
            hex_clean = mac.replace(":", "").replace("-", "").lower()
            if len(hex_clean) != 12 or not all(c in "0123456789abcdef" for c in hex_clean):
                return self._emit(
                    "Configure wol_mac en viernes_config.json o diga: wol AA:BB:CC:DD:EE:FF"
                )
            ok = wake_on_lan(mac)
            return self._emit("Paquete magico enviado por la red local." if ok else "No pude enviar Wake-on-LAN.")

        if low in {"diagnostico sintaxis", "auditar sintaxis proyecto", "syntax check"}:
            if run_startup_ast_check is None:
                return self._emit("Diagnostico AST no disponible.")
            errs = run_startup_ast_check([ROOT_DIR])
            if not errs:
                return self._emit("Diagnostico AST: sin errores de sintaxis detectados en paquetes locales.")
            preview = "; ".join(errs[:12])
            more = f" ({len(errs)} en total)" if len(errs) > 12 else ""
            return self._emit(f"Diagnostico AST: {preview}{more}")

        return None

    def _parse_relative_date(self, text: str, now: datetime) -> date:
        low = normalize_text(text)
        match = re.search(r"\b(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)?\s*(\d{1,2})\s+de\s+([a-z]+)(?:\s+de\s+(\d{4}))?\b", low)
        if match:
            day_num = int(match.group(1))
            month_num = MONTHS.get(match.group(2))
            year = int(match.group(3)) if match.group(3) else now.year
            if month_num:
                try:
                    candidate = date(year, month_num, day_num)
                    if not match.group(3) and candidate < now.date():
                        candidate = date(year + 1, month_num, day_num)
                    return candidate
                except ValueError:
                    pass
        match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", low)
        if match:
            day_num = int(match.group(1))
            month_num = int(match.group(2))
            raw_year = match.group(3)
            year = now.year if not raw_year else int(raw_year) + (2000 if len(raw_year) == 2 else 0)
            try:
                candidate = date(year, month_num, day_num)
                if not raw_year and candidate < now.date():
                    candidate = date(year + 1, month_num, day_num)
                return candidate
            except ValueError:
                pass
        mapping = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
        for name, idx in mapping.items():
            if name in low:
                return now.date() + timedelta(days=(idx - now.weekday()) % 7)
        date_low = re.sub(r"\b(de|por|en)\s+la\s+manana\b", " ", low)
        if "manana" in date_low:
            return now.date() + timedelta(days=1)
        return now.date()

    def _parse_time(self, text: str) -> Optional[str]:
        raw = text.lower().strip()
        match = re.search(r"\b(\d{1,2})[:.](\d{2})\b", raw)
        if match:
            hh, mm = int(match.group(1)), int(match.group(2))
            if 0 <= hh <= 23 and 0 <= mm <= 59:
                return f"{hh:02d}:{mm:02d}"
        low = normalize_text(text)
        match = re.search(r"\ba las (\d{1,2})\b", low)
        if match:
            hh = int(match.group(1))
            if ("pm" in low or "tarde" in low or "noche" in low) and hh < 12:
                hh += 12
            return f"{hh:02d}:00"
        return None

    def _strip_date_and_time_phrases(self, text: str) -> str:
        low = normalize_text(text)
        low = re.sub(r"\b(de|por|en)\s+la\s+(manana|tarde|noche)\b", " ", low)
        low = re.sub(r"\b(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+\d{1,2}\s+de\s+[a-z]+(?:\s+de\s+\d{4})?\b", " ", low)
        low = re.sub(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", " ", low)
        low = re.sub(r"\bmanana\b|\bhoy\b|\b(es|para|el|este|esta)\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", " ", low)
        low = re.sub(r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", " ", low)
        low = re.sub(r"\ba las\s+\d{1,2}(?::\d{2})?\b", " ", low)
        low = re.sub(r"\ben\s+\d+\s*(minutos|minuto|horas|hora)\b", " ", low)
        low = re.sub(r"\b(?:el|dia|de|la|que|tengo)\b", " ", low)
        return re.sub(r"\s+", " ", low).strip(" ,.-") or "Evento"

    def _parse_relative_reminder(self, text: str, now: datetime) -> tuple[Optional[str], Optional[datetime], str]:
        low = normalize_text(text)
        if re.search(r"\b(cada\s+(dia|dias)|todos\s+los\s+dias)\b", low):
            hhmm = self._parse_time(low) or "09:00"
            target = datetime.combine(now.date(), parse_hhmm(hhmm))
            if target < now:
                target += timedelta(days=1)
            topic = re.sub(r"\b(cada\s+(dia|dias)|todos\s+los\s+dias)\b", " ", low)
            topic = re.sub(r"\ba las\s+\d{1,2}(?::\d{2})?\b", " ", topic)
            topic = re.sub(r"^recuerdame\b", "", topic).strip(" ,.-") or "Recordatorio"
            return topic, target, "daily"
        match = re.search(r"\bcada\s+((?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)(?:\s+y\s+(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo))+)\b", low)
        if match:
            names = re.findall(r"lunes|martes|miercoles|jueves|viernes|sabado|domingo", match.group(1))
            keys = [weekday_name_to_key(name) for name in names]
            hhmm = self._parse_time(low) or "09:00"
            topic = re.sub(r"\bcada\s+((?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)(?:\s+y\s+(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo))+)\b", " ", low)
            topic = re.sub(r"\ba las\s+\d{1,2}(?::\d{2})?\b", " ", topic)
            topic = re.sub(r"^recuerdame\b", "", topic).strip(" ,.-") or "Recordatorio"
            return f"{topic}||{','.join(keys)}", datetime.combine(now.date(), parse_hhmm(hhmm)), "weekly_multi"
        match = re.search(r"\bcada\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", low)
        if match:
            idx = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}[match.group(1)]
            hhmm = self._parse_time(low) or "09:00"
            target_day = now.date() + timedelta(days=(idx - now.weekday()) % 7)
            target = datetime.combine(target_day, parse_hhmm(hhmm))
            if target < now:
                target += timedelta(days=7)
            topic = re.sub(r"\bcada\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", " ", low)
            topic = re.sub(r"\ba las\s+\d{1,2}(?::\d{2})?\b", " ", topic)
            topic = re.sub(r"^recuerdame\b", "", topic).strip(" ,.-") or "Recordatorio"
            return topic, target, "weekly"
        if re.search(rf"\b(?:el\s+dia|dia|el|este|esta|para|proximo|proxima)?\s*{WEEKDAY_RE}\b", low):
            target_date = self._parse_relative_date(low, now)
            hhmm = self._parse_time(low) or "09:00"
            topic = self._strip_date_and_time_phrases(low.replace("recuerdame", "", 1))
            target = datetime.combine(target_date, parse_hhmm(hhmm))
            if target < now:
                target += timedelta(days=7)
            return topic, target, ""
        match = re.search(r"\ben\s+(\d+)\s*(minutos|minuto|horas|hora)\b", low)
        if match:
            amount = int(match.group(1))
            target = now + (timedelta(hours=amount) if "hora" in match.group(2) else timedelta(minutes=amount))
            topic = re.sub(r"\ben\s+\d+\s*(minutos|minuto|horas|hora)\b", " ", low)
            topic = re.sub(r"^recuerdame\b", "", topic).strip(" ,.-") or "Recordatorio"
            return topic, target, ""
        if "manana" in low or re.search(r"\bel\s+\d{1,2}\b", low) or "/" in low:
            target_date = self._parse_relative_date(low, now)
            hhmm = self._parse_time(low) or "09:00"
            return self._strip_date_and_time_phrases(low.replace("recuerdame", "", 1)), datetime.combine(target_date, parse_hhmm(hhmm)), ""
        return None, None, ""

    def _add_agenda_item(self, title: str, day: date, hhmm: str, category: str = "evento", recurring: str = "", weekdays: Optional[list[str]] = None) -> None:
        self.agenda.setdefault("items", []).append(
            {
                "id": str(uuid.uuid4()),
                "title": title.strip(),
                "date": iso_day(day),
                "time": hhmm,
                "category": category,
                "recurring": recurring,
                "weekday": weekday_key(day) if recurring == "weekly" else "",
                "weekdays": list(weekdays or []),
                "paused": False,
            }
        )
        self._save_agenda()

    def _add_timed_reminder(self, title: str, when: datetime, recurring: str = "") -> None:
        weekdays: list[str] = []
        clean_title = title
        if recurring == "weekly_multi" and "||" in title:
            clean_title, raw_days = title.split("||", 1)
            weekdays = [x.strip() for x in raw_days.split(",") if x.strip()]
        self._add_agenda_item(clean_title, when.date(), when.strftime("%H:%M"), category="recordatorio", recurring=recurring, weekdays=weekdays)

    def _find_agenda_matches(self, query: str) -> list[dict[str, Any]]:
        q = normalize_text(query)
        matches: list[dict[str, Any]] = []
        for item in self.agenda.get("items", []):
            title = normalize_text(str(item.get("title", "")))
            item_day = normalize_text(str(item.get("date", "")))
            if q and (q in title or title in q or q in item_day):
                matches.append(item)
        return matches

    def _delete_agenda_item(self, item_id: str) -> None:
        self.agenda["items"] = [item for item in self.agenda.get("items", []) if str(item.get("id")) != item_id]
        self._save_agenda()

    def _set_agenda_paused(self, item_id: str, paused: bool) -> None:
        for item in self.agenda.get("items", []):
            if str(item.get("id")) == item_id:
                item["paused"] = paused
                break
        self._save_agenda()

    def _update_agenda_item(
        self,
        item: dict[str, Any],
        *,
        title: Optional[str] = None,
        day: Optional[date] = None,
        hhmm: Optional[str] = None,
    ) -> None:
        if title and title.strip():
            item["title"] = title.strip()
        if day is not None:
            item["date"] = iso_day(day)
            if item.get("recurring") == "weekly":
                item["weekday"] = weekday_key(day)
        if hhmm:
            item["time"] = hhmm
        self._save_agenda()

    def _event_query_before_schedule(self, text: str) -> str:
        markers = [" a las ", " para ", " el ", " hoy", " manana", " lunes", " martes", " miercoles", " jueves", " viernes", " sabado", " domingo"]
        cut = len(text)
        for marker in markers:
            idx = text.find(marker)
            if idx > 0:
                cut = min(cut, idx)
        return text[:cut].strip(" ,.-") or text.strip(" ,.-")

    def _agenda_edit_command(self, low: str, original: str, now: datetime) -> Optional[str]:
        if low in {"modificar evento", "editar evento", "cambiar evento"}:
            self._start_dialog("edit_agenda", {})
            return self._emit("Que evento desea modificar?")

        if low.startswith(("renombrar evento ", "renombra evento ", "cambiar nombre evento ", "cambia nombre evento ")):
            body = re.sub(r"^(renombrar evento|renombra evento|cambiar nombre evento|cambia nombre evento)\s+", "", low).strip()
            parts = re.split(r"\s+a\s+|\s+como\s+", body, maxsplit=1)
            if len(parts) < 2:
                return self._emit("Diga por ejemplo: renombra evento junta a reunion de equipo.")
            matches = self._find_agenda_matches(parts[0])
            if not matches:
                return self._emit("No encontre ese evento en la agenda.")
            self._update_agenda_item(matches[0], title=parts[1])
            return self._emit(f"Listo. Ahora se llama: {parts[1]}.")

        if low.startswith(("cambiar hora evento ", "cambia hora evento ", "mover evento ", "mueve evento ", "modificar evento ", "edita evento ")):
            prefix = r"^(cambiar hora evento|cambia hora evento|mover evento|mueve evento|modificar evento|edita evento)\s+"
            body_low = re.sub(prefix, "", low).strip()
            query = self._event_query_before_schedule(body_low)
            matches = self._find_agenda_matches(query)
            if not matches:
                return self._emit("No encontre ese evento en la agenda.")
            hhmm = self._parse_time(original)
            target_day = self._parse_relative_date(body_low, now) if any(
                marker in body_low for marker in ("hoy", "manana", "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo", "/", " de ")
            ) else None
            if hhmm is None and target_day is None:
                self._start_dialog("edit_agenda", {"item_id": str(matches[0].get("id", ""))})
                return self._emit("Que desea cambiar? Puede decir nuevo nombre, nuevo dia u hora.")
            self._update_agenda_item(matches[0], day=target_day, hhmm=hhmm)
            return self._emit(
                f"Evento actualizado: {matches[0].get('title', 'Evento')} "
                f"el {matches[0].get('date', '--')} a las {matches[0].get('time', '--:--')}."
            )

        return None

    def _agenda_add_natural_command(self, low: str, original: str, now: datetime) -> Optional[str]:
        add_words = ("agrega ", "agregar ", "anade ", "añade ", "registrar ", "registra ", "pon ")
        if not low.startswith(add_words):
            return None
        if any(word in low for word in (" presupuesto", " ingreso", " gasto", " clase", " clases")):
            return None
        if not any(word in low for word in ("agenda", "evento", "recordatorio", "tengo ")):
            return None

        hhmm = self._parse_time(original)
        body = re.sub(
            r"^(agrega|agregar|anade|añade|registrar|registra|pon)\s+",
            "",
            low,
            count=1,
        ).strip()
        body = re.sub(r"^(a\s+)?(la\s+)?(agenda|evento|recordatorio)\s*", " ", body).strip()
        body = re.sub(r"^(que\s+)?tengo\s+", " ", body).strip()
        body = re.sub(r"^(un|una)\s+", " ", body).strip()

        title = self._strip_date_and_time_phrases(body)
        title = re.sub(r"\b(un|una)\b", " ", title).strip(" ,.-") or "Evento"
        target_day = self._parse_relative_date(body, now)

        if hhmm is None:
            self._start_dialog("agenda", {"title": title, "date": iso_day(target_day)})
            return self._emit(f"Entendi el evento '{title}'. Solo me falta la hora.")

        self._add_agenda_item(title, target_day, hhmm)
        return self._emit(f"Quedo agendado: {title} el {iso_day(target_day)} a las {hhmm}.")

    def _is_greeting_command(self, low: str) -> bool:
        if low in {
            "hola",
            "hey",
            "buenas",
            "buenos dias",
            "buenas tardes",
            "buenas noches",
            "que tal",
            "como estas",
            "hola como estas",
            "hola viernes",
            "como estas viernes",
            "que tal viernes",
            "voy a viernes",
            "voy viernes",
        }:
            return True
        return bool(
            re.fullmatch(
                r"(hola|hey|buenas|buenos dias|buenas tardes|buenas noches|que tal|como estas|como andas|como va)(\s+viernes)?",
                low,
            )
        )

    def _strip_wake_word_prefix(self, original: str, low: str) -> tuple[str, str, bool]:
        configured = str(self.config.get("wake_word", "viernes") or "viernes").strip()
        wake = normalize_text(configured) or "viernes"
        if low == wake:
            return original, low, True
        prefix = wake + " "
        if not low.startswith(prefix):
            return original, low, False
        words = str(original or "").strip().split(maxsplit=1)
        stripped_original = words[1].strip() if len(words) > 1 else ""
        stripped_low = normalize_text(stripped_original)
        return stripped_original, stripped_low, False

    def _should_bypass_pending_dialog(self, low: str) -> bool:
        if not self.pending_dialog:
            return False
        if low in {"cancelar", "olvida", "salir"}:
            return False
        if self._is_greeting_command(low):
            return True
        kind = str(self.pending_dialog.get("kind", ""))
        if kind == "clarify_action" and low in {
            "1",
            "2",
            "3",
            "4",
            "uno",
            "dos",
            "tres",
            "cuatro",
            "pendiente",
            "tarea",
            "compromiso",
            "agenda",
            "evento",
            "calendario",
            "recordatorio",
            "recuerdame",
            "nota",
            "nota diaria",
        }:
            return False
        if low in {
            "detente",
            "para",
            "stop",
            "callate",
            "viernes detente",
            "viernes para",
            "viernes stop",
            "ayuda",
            "lista",
            "que puedes hacer",
        }:
            return True
        new_command_prefixes = (
            "que ",
            "como ",
            "cuentame ",
            "cuenta ",
            "dime ",
            "hablame ",
            "sorprendeme",
            "abre ",
            "abrir ",
            "busca ",
            "buscar ",
            "investiga ",
            "consulta ",
            "calcula ",
            "calcular ",
            "cuanto es ",
            "resuelve ",
            "agenda",
            "clases",
            "horario",
            "presupuesto",
            "balance",
            "noticias",
            "clima",
            "rutina",
            "agrega ",
            "agregar ",
            "anade ",
            "registrar ",
            "registra ",
            "pon ",
            "recuerdame ",
            "recordatorio ",
            "activar ",
            "desactivar ",
            "pausar ",
            "reactivar ",
        )
        return low.startswith(new_command_prefixes)

    def _start_dialog(self, kind: str, data: Optional[dict[str, Any]] = None) -> None:
        self.pending_dialog = {"kind": kind, "data": dict(data or {})}

    def _finish_dialog(self) -> None:
        self.pending_dialog = None

    def _past_agenda_items(self, today: date) -> list[dict[str, Any]]:
        past_items: list[dict[str, Any]] = []
        for item in self.agenda.get("items", []):
            if item.get("recurring"):
                continue
            try:
                item_date = date.fromisoformat(str(item.get("date")))
            except Exception:
                continue
            if item_date < today:
                past_items.append(item)
        return past_items

    def _confirm_cleanup_past_events(self, now: datetime) -> str:
        count = len(self._past_agenda_items(now.date()))
        if not count:
            return self._emit("No hay eventos pasados para limpiar.")
        self._start_dialog("confirm_destructive", {"action": "cleanup_past_events"})
        return self._emit(
            f"Voy a eliminar {count} evento(s) pasado(s) de la agenda. "
            "Diga 'confirmar' para continuar o 'cancelar' para no borrar nada."
        )

    def _effective_proactivity_config(self) -> dict[str, Any]:
        cfg = dict(DEFAULT_PROACTIVITY_CONFIG)
        raw = self.config.get("proactivity", {})
        if isinstance(raw, dict):
            cfg.update(raw)
        return cfg

    def _build_proactive_context(
        self,
        now: datetime,
        daily: dict[str, Any],
        *,
        suppress_notified_past: bool = False,
    ) -> ProactiveContext:
        override = self._current_override(now.date())
        classes = [] if override.get("free_day") or override.get("classes_cancelled") else self._classes_for_day(now.date())
        past_items = self._past_agenda_items(now.date())
        if suppress_notified_past:
            notified = set(str(item_id) for item_id in daily.get("past_events_notified", []))
            past_items = [item for item in past_items if str(item.get("id", "")) not in notified]
        alias_count = 0
        try:
            alias_count = len(HabitTracker.suggest_aliases(days=14, limit=1, now=now))
        except Exception:
            alias_count = 0
        try:
            memory_facts_count = len(self._memory_store().load_profile().facts)
        except Exception:
            memory_facts_count = 0
        try:
            activity_block_count = len(self._activity_calendar_for_day(now.date(), now).blocks)
        except Exception:
            activity_block_count = 0
        try:
            personal_rules = [rule.to_dict() for rule in self._memory_store().rules_for_day(now.date())]
        except Exception:
            personal_rules = []
        next_rule = self._next_personal_rule(now, personal_rules)
        try:
            due_tasks = self._task_store().tasks_for_day(now.date())
            next_task = self._task_store().next_task(now)
            next_pending_task = next_task.to_dict() if next_task is not None else None
        except Exception:
            due_tasks = []
            next_pending_task = None
        return ProactiveContext(
            now=now,
            daily=daily,
            config=self.config,
            agenda_today=self._agenda_items_for_day(now.date()),
            classes_today=classes,
            leave_time=self._configured_leave_time_for_day(now.date()),
            past_events_count=len(past_items),
            nlu_miss_count=int(daily.get("nlu_miss_count", 0) or 0),
            alias_suggestions_count=alias_count,
            activity_block_count=activity_block_count,
            memory_facts_count=memory_facts_count,
            personal_rules_count=len(personal_rules),
            next_personal_rule=next_rule,
            pending_due_count=len(due_tasks),
            next_pending_task=next_pending_task,
        )

    def _proactive_suggestions(
        self,
        now: datetime,
        daily: dict[str, Any],
        *,
        suppress_notified_past: bool = False,
    ) -> list[ProactiveSuggestion]:
        engine = getattr(self, "proactivity", None)
        if engine is None:
            engine = ProactiveEngine()
            self.proactivity = engine
        context = self._build_proactive_context(now, daily, suppress_notified_past=suppress_notified_past)
        suggestions = engine.evaluate(context)
        paused = set(str(item) for item in self.state.get("proactivity_paused_categories", []))
        feedback = self.state.get("proactivity_feedback", {})
        adapted: list[ProactiveSuggestion] = []
        for item in suggestions:
            if item.category in paused:
                continue
            category_feedback = feedback.get(item.category, {}) if isinstance(feedback, dict) else {}
            positive = int(category_feedback.get("positive", 0) or 0) if isinstance(category_feedback, dict) else 0
            negative = int(category_feedback.get("negative", 0) or 0) if isinstance(category_feedback, dict) else 0
            priority = item.priority + min(positive, 3) * 2 - min(negative, 3) * 5
            if priority < 30:
                continue
            adapted.append(
                ProactiveSuggestion(
                    id=item.id,
                    message=item.message,
                    category=item.category,
                    priority=priority,
                    reason=item.reason,
                )
            )
        adapted.sort(key=lambda item: (-item.priority, item.category, item.id))
        return adapted

    def _format_proactive_suggestions(self, suggestions: list[ProactiveSuggestion], limit: int = 3) -> str:
        if not suggestions:
            return "No veo sugerencias operativas importantes ahora mismo."
        parts = [f"{index}. {item.message}" for index, item in enumerate(suggestions[:limit], start=1)]
        return "Sugerencias operativas: " + " ".join(parts)

    def _proactive_suggestions_command(self, now: datetime, daily: dict[str, Any]) -> str:
        suggestions = self._proactive_suggestions(now, daily)
        return self._emit(self._format_proactive_suggestions(suggestions, limit=3))

    def _set_proactivity_mode(self, mode: str) -> str:
        cfg = self.config.setdefault("proactivity", {})
        if not isinstance(cfg, dict):
            cfg = {}
            self.config["proactivity"] = cfg
        if mode == "off":
            cfg["enabled"] = False
            self.save_config()
            return self._emit("Modo proactivo apagado. No enviare sugerencias operativas automaticas.")
        if mode == "normal":
            cfg.update({"enabled": True, "mode": "normal", "interval_minutes": 60, "lookahead_minutes": 180, "max_per_tick": 1})
            self.save_config()
            return self._emit("Modo proactivo normal activado. Revisare oportunidades utiles con mas frecuencia.")
        if mode == "conservative":
            cfg.update(
                {
                    "enabled": True,
                    "mode": "conservative",
                    "interval_minutes": 120,
                    "lookahead_minutes": 120,
                    "max_per_tick": 1,
                }
            )
            self.save_config()
            return self._emit("Modo proactivo conservador activado.")
        cfg.setdefault("mode", "conservative")
        cfg.setdefault("interval_minutes", 120)
        cfg.setdefault("lookahead_minutes", 120)
        cfg.setdefault("max_per_tick", 1)
        cfg["enabled"] = True
        self.save_config()
        return self._emit(f"Modo proactivo activo en nivel {cfg.get('mode', 'conservative')}.")

    def _proactive_mode_from_text(self, low: str) -> Optional[str]:
        if "apagado" in low or "desactiva" in low or "desactivar" in low:
            return "off"
        if "normal" in low:
            return "normal"
        if "conservador" in low or "conservadora" in low:
            return "conservative"
        if "activo" in low or "activa" in low or "activar" in low or "enciende" in low:
            return "on"
        return None

    def _proactive_command(self, low: str, now: datetime, daily: dict[str, Any]) -> Optional[str]:
        if low in {"sugerencias ahora", "que sugieres", "que me sugieres", "revisa contexto", "revisar contexto"}:
            return self._proactive_suggestions_command(now, daily)
        if low.startswith("modo proactivo") or re.search(r"\b(activa|activar|desactiva|desactivar|enciende)\b.*\bproactivo\b", low):
            mode = self._proactive_mode_from_text(low)
            if mode:
                return self._set_proactivity_mode(mode)
        return None

    def _proactive_events(self, now: datetime, daily: dict[str, Any]) -> list[ReminderEvent]:
        cfg = self._effective_proactivity_config()
        if cfg.get("enabled") is False:
            return []
        last_raw = str(daily.get("last_proactive_at", "") or "").strip()
        interval = max(30, int(cfg.get("interval_minutes", 120) or 120))
        if last_raw:
            try:
                if now - datetime.fromisoformat(last_raw) < timedelta(minutes=interval):
                    return []
            except ValueError:
                pass
        max_per_tick = max(1, int(cfg.get("max_per_tick", 1) or 1))
        sent = set(daily.get("sent", []))
        events: list[ReminderEvent] = []
        for suggestion in self._proactive_suggestions(now, daily, suppress_notified_past=True):
            event_id = f"proactive:{suggestion.id}"
            if event_id in sent:
                continue
            events.append(ReminderEvent(event_id, suggestion.message, "proactive"))
            daily["pending_proactive_suggestion"] = suggestion.to_dict()
            if len(events) >= max_per_tick:
                break
        return events

    def _memory_store(self) -> PersonalMemoryStore:
        store = getattr(self, "memory_store", None)
        if store is None:
            store = PersonalMemoryStore()
            self.memory_store = store
        return store

    def _sync_fact_to_agent_memory(self, text: str, *, kind: str = "personal_fact", now: datetime | None = None) -> None:
        manager = getattr(self, "agent_memory", None)
        if manager is None:
            return
        try:
            manager.remember_long_term(
                text,
                kind=kind,
                metadata={"source": "personal_memory", "synced_at": (now or datetime.now()).isoformat(timespec="seconds")},
            )
        except Exception:
            pass

    def _sync_preference_to_agent_memory(self, key: str, value: str, *, now: datetime | None = None) -> None:
        manager = getattr(self, "agent_memory", None)
        if manager is None:
            return
        try:
            manager.set_preference(key, value)
            manager.remember_long_term(
                f"Preferencia del usuario - {key}: {value}",
                kind="personal_preference",
                metadata={"source": "personal_memory", "synced_at": (now or datetime.now()).isoformat(timespec="seconds")},
            )
        except Exception:
            pass

    def _forget_agent_memory(self, query: str) -> int:
        manager = getattr(self, "agent_memory", None)
        if manager is None:
            return 0
        try:
            return int(manager.forget(query))
        except Exception:
            return 0

    def _memory_search_summary(self, query: str) -> str:
        clean_query = query.strip()
        if not clean_query:
            return "Diga que tema quiere buscar en memoria."
        personal_matches = self._memory_store().search(clean_query, max_items=6)
        agent_matches = []
        manager = getattr(self, "agent_memory", None)
        if manager is not None:
            try:
                agent_matches = manager.retrieve_context(clean_query, limit=6)
            except Exception:
                agent_matches = []
        lines: list[str] = []
        for item in personal_matches:
            if isinstance(item, MemoryFact):
                lines.append(f"dato: {item.text}")
            elif isinstance(item, Preference):
                lines.append(f"preferencia: {item.key}: {item.value}")
            elif isinstance(item, PersonalRule):
                lines.append(f"regla: {item.action_text}")
        known = {line.lower() for line in lines}
        for item in agent_matches:
            text = str(getattr(item, "text", "") or "").strip()
            if text and text.lower() not in known:
                lines.append(f"contexto: {text}")
                known.add(text.lower())
        if not lines:
            return f"No encontre memoria sobre '{clean_query}'."
        return f"Recuerdo sobre '{clean_query}': " + " | ".join(lines[:8])

    def _task_store(self) -> PendingTaskStore:
        store = getattr(self, "pending_tasks", None)
        if store is None:
            store = PendingTaskStore()
            self.pending_tasks = store
        return store

    def _history_store(self) -> ActionHistoryStore:
        store = getattr(self, "action_history", None)
        if store is None:
            store = ActionHistoryStore()
            self.action_history = store
        return store

    def _activity_builder(self) -> ActivityCalendarBuilder:
        builder = getattr(self, "activity_calendar_builder", None)
        if builder is None:
            builder = ActivityCalendarBuilder()
            self.activity_calendar_builder = builder
        return builder

    def _planner(self) -> ActionPlanner:
        planner = getattr(self, "action_planner", None)
        if planner is None:
            planner = ActionPlanner()
            self.action_planner = planner
        return planner

    def _executor(self) -> ActionExecutor:
        executor = getattr(self, "action_executor", None)
        if executor is None:
            executor = ActionExecutor()
            self.action_executor = executor
        return executor

    def _clarifier(self) -> ClarificationEngine:
        clarifier = getattr(self, "clarification_engine", None)
        if clarifier is None:
            clarifier = ClarificationEngine()
            self.clarification_engine = clarifier
        return clarifier

    def _tool_registry(self) -> ToolRegistry:
        registry = getattr(self, "tool_registry", None)
        if not isinstance(registry, ToolRegistry):
            registry = ToolRegistry()
            self.tool_registry = registry
        return registry

    def _game_engine(self) -> GameEngine:
        engine = getattr(self, "game_engine", None)
        if not isinstance(engine, GameEngine):
            engine = GameEngine()
            self.game_engine = engine
        return engine

    def _intent_arbiter(self) -> IntentArbiter:
        return IntentArbiter(
            nlu=getattr(self, "nlu", None),
            planner=self._planner(),
            clarifier=self._clarifier(),
            wake_query_detector=self._looks_like_wake_schedule_query,
            greeting_detector=self._is_greeting_command,
            normalizer=normalize_text,
        )

    def _simulation_engine(self) -> SimulationEngine:
        engine = getattr(self, "simulation_engine", None)
        if not isinstance(engine, SimulationEngine):
            engine = SimulationEngine()
            self.simulation_engine = engine
        return engine

    def _report_builder(self) -> ReportBuilder:
        builder = getattr(self, "report_builder", None)
        if not isinstance(builder, ReportBuilder):
            builder = ReportBuilder()
            self.report_builder = builder
        return builder

    def _research_table_builder(self) -> ResearchTableBuilder:
        builder = getattr(self, "research_table_builder", None)
        if not isinstance(builder, ResearchTableBuilder):
            builder = ResearchTableBuilder()
            self.research_table_builder = builder
        return builder

    def _analysis_reports_dir(self) -> Path:
        return RUNTIME_DIR / "reports"

    def _memory_command(self, low: str, original: str, now: datetime) -> Optional[str]:
        if low.startswith(("que recuerdas sobre ", "que recuerdas de ", "busca en memoria ", "buscar en memoria ", "memoria sobre ")):
            query = re.sub(r"^(que recuerdas sobre|que recuerdas de|busca en memoria|buscar en memoria|memoria sobre)\s+", "", low).strip()
            return self._emit(self._memory_search_summary(query))
        if low in {"mis preferencias", "preferencias personales", "que preferencias sabes", "que preferencias tienes"}:
            return self._emit(self._memory_store().preferences_summary())
        if (
            low.startswith(("actualiza mi preferencia de ", "guarda mi preferencia de "))
            or re.match(r"^mi\s+preferencia\s+de\s+.+\s+es\s+.+$", low)
            or low.startswith("prefiero ")
        ):
            key, value = self._parse_preference_command(low)
            if not key or not value:
                return self._emit("No entendi la preferencia. Diga por ejemplo: actualiza mi preferencia de respuesta a breve.")
            pref = self._memory_store().set_preference(key, value, now=now)
            self._sync_preference_to_agent_memory(pref.key, pref.value, now=now)
            return self._emit(f"Preferencia actualizada: {pref.key}: {pref.value}.")
        if re.match(r"^(olvida|borra|elimina)\s+(mi\s+)?preferencia\s+", low):
            query = re.sub(r"^(olvida|borra|elimina)\s+(mi\s+)?preferencia\s+", "", low).strip()
            removed = self._memory_store().forget_preference(query)
            removed += self._forget_agent_memory(query)
            if removed:
                return self._emit(f"Listo. Olvide {removed} preferencia(s) que coincidian.")
            return self._emit("No encontre preferencias que coincidan con eso.")
        if low.startswith("recuerda esto como regla"):
            rule_text = re.sub(r"^recuerda\s+esto\s+como\s+regla\s*:?", "", original, flags=re.IGNORECASE).strip()
            if not rule_text:
                return self._emit("Digame la regla. Ejemplo: recuerda esto como regla: cuando sea viernes recuerdame revisar maleta.")
            try:
                rule = self._memory_store().add_personal_rule(rule_text, now=now)
                self._sync_fact_to_agent_memory(rule.text, kind="personal_rule", now=now)
                return self._emit(f"Regla personal guardada: {rule.action_text}.")
            except ValueError:
                fact = self._memory_store().remember(rule_text, category="rule_note", now=now)
                self._sync_fact_to_agent_memory(fact.text, kind="rule_note", now=now)
                return self._emit(f"Guarde esa regla como nota de memoria: {fact.text}.")
        if self._looks_like_personal_rule(low):
            try:
                rule = self._memory_store().add_personal_rule(original, now=now)
            except ValueError:
                return self._emit("Entendi que quiere una regla personal, pero necesito dia u hora mas claros.")
            self._sync_fact_to_agent_memory(rule.text, kind="personal_rule", now=now)
            when = WEEKDAY_LABELS.get(rule.weekday, rule.weekday or "cualquier dia")
            relation = "antes de" if rule.relation == "before" else "a las"
            time_part = f" {relation} {rule.time}" if rule.time else ""
            return self._emit(f"Regla personal guardada: {when}{time_part}, {rule.action_text}.")
        if low in {"reglas personales", "mis reglas", "ver reglas personales"}:
            return self._emit(self._memory_store().rules_summary())
        if low.startswith(("olvida regla ", "borra regla ", "elimina regla ")):
            query = re.sub(r"^(olvida regla|borra regla|elimina regla)\s+", "", low).strip()
            removed = self._memory_store().forget_rule(query)
            removed += self._forget_agent_memory(query)
            if removed:
                return self._emit(f"Listo. Elimine {removed} regla(s) personales.")
            return self._emit("No encontre reglas personales que coincidan con eso.")
        if low.startswith(("recuerda que ", "recuerdame que ", "aprende que ", "guarda en memoria que ", "memoriza que ", "recuerda esto:")):
            fact_text = re.sub(
                r"^\s*(recuerda|recuerdame|aprende|guarda\s+en\s+memoria|memoriza)\s+que\s+",
                "",
                original,
                flags=re.IGNORECASE,
            ).strip()
            fact_text = re.sub(r"^\s*recuerda\s+esto\s*:?\s*", "", fact_text, flags=re.IGNORECASE).strip()
            if not fact_text:
                return self._emit("Que debo recordar?")
            fact = self._memory_store().remember(fact_text, now=now)
            self._sync_fact_to_agent_memory(fact.text, now=now)
            return self._emit(f"Lo recuerdo: {fact.text}.")
        if low in {"que sabes de mi", "mi perfil", "perfil personal", "memoria personal"}:
            return self._emit(self._memory_store().summary())
        if low.startswith(("olvida que ", "borra de memoria ", "olvida de mi ")):
            query = re.sub(r"^(olvida que|borra de memoria|olvida de mi)\s+", "", low).strip()
            removed = self._memory_store().forget(query)
            removed += self._forget_agent_memory(query)
            if removed:
                return self._emit(f"Listo. Olvide {removed} dato(s) que coincidian con eso.")
            return self._emit("No encontre datos de memoria que coincidan con eso.")
        if low in {"actualiza mi perfil", "actualiza perfil", "actualiza memoria personal"}:
            profile = build_adaptive_profile(14)
            added = self._memory_store().update_from_adaptive_profile(profile, now=now)
            if added:
                return self._emit(f"Perfil personal actualizado con {added} patron(es) de actividad.")
            return self._emit("Perfil personal revisado. No encontre patrones nuevos importantes.")
        return None

    def _parse_preference_command(self, low: str) -> tuple[str, str]:
        patterns = (
            r"^actualiza\s+mi\s+preferencia\s+de\s+(.+?)\s+a\s+(.+)$",
            r"^guarda\s+mi\s+preferencia\s+de\s+(.+?)\s+(?:a|como)\s+(.+)$",
            r"^mi\s+preferencia\s+de\s+(.+?)\s+es\s+(.+)$",
            r"^prefiero\s+que\s+me\s+respondas\s+(.+)$",
            r"^prefiero\s+respuestas?\s+(.+)$",
        )
        for pattern in patterns:
            match = re.match(pattern, low)
            if match:
                if len(match.groups()) == 1:
                    return "respuesta", match.group(1).strip(" ,-")
                return match.group(1).strip(" ,-"), match.group(2).strip(" ,-")
        match = re.match(r"^prefiero\s+(.+)$", low)
        if match:
            return "general", match.group(1).strip(" ,-")
        return "", ""

    def _looks_like_personal_rule(self, low: str) -> bool:
        return (
            ("recuerdame" in low or "recuerda" in low)
            and (
                low.startswith(("cuando ", "cuando sea ", "si es ", "los ", "el "))
                or re.search(r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", low)
            )
        )

    def _activity_calendar_for_day(self, target_day: date, now: datetime) -> ActivityCalendar:
        day_key = iso_day(target_day)
        daily = dict(self.state.setdefault("daily", {}).get(day_key, {}))
        if target_day == now.date():
            daily.update(self._ensure_daily_state(now))
        override = self._current_override(target_day)
        classes = [] if override.get("free_day") or override.get("classes_cancelled") else self._classes_for_day(target_day)
        return self._activity_builder().build_day(
            target_day,
            agenda_items=self._agenda_items_for_day(target_day),
            classes=classes,
            leave_time=self._configured_leave_time_for_day(target_day),
            override=override,
            daily=daily,
            personal_rules=[rule.to_dict() for rule in self._memory_store().rules_for_day(target_day)],
        )

    def _activity_calendar_for_range(self, start_day: date, now: datetime, days: int = 7) -> ActivityWeek:
        count = min(max(1, days), 14)
        calendars = [self._activity_calendar_for_day(start_day + timedelta(days=index), now) for index in range(count)]
        return ActivityWeek(start_day=iso_day(start_day), calendars=calendars)

    def _next_personal_rule(self, now: datetime, rules: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
        upcoming: list[tuple[datetime, dict[str, Any]]] = []
        for rule in rules:
            hhmm = str(rule.get("time", "") or "").strip()
            if not re.fullmatch(r"\d{2}:\d{2}", hhmm):
                continue
            try:
                hour, minute = [int(part) for part in hhmm.split(":", 1)]
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            except Exception:
                continue
            if target >= now:
                upcoming.append((target, rule))
        if not upcoming:
            return None
        upcoming.sort(key=lambda item: item[0])
        return upcoming[0][1]

    def _activity_calendar_command(self, low: str, now: datetime) -> Optional[str]:
        target_day = now.date() + timedelta(days=1) if "manana" in low else now.date()
        if low in {"objetivos de la semana", "metas semanales", "que objetivos tengo"}:
            return self._emit(self._weekly_goals_summary(now))
        if low in {"avance de hoy", "como voy hoy", "progreso del dia"}:
            return self._emit(self._day_progress_summary(now))
        if low in {"cerrar mi dia", "cierra mi dia", "prepara mi cierre"}:
            return self._start_day_close_plan(now)
        if low in {"prepara manana", "preparar manana", "prepara mi manana", "prepara el dia de manana"}:
            return self._start_prepare_tomorrow_plan(now)
        if low in {
            "plan semanal",
            "mi semana",
            "calendario semanal",
            "semana operativa",
            "plan de la semana",
            "proximos dias",
            "proximos 7 dias",
        }:
            week = self._activity_calendar_for_range(now.date(), now, days=7)
            return self._emit(week.summary())
        if low in {"plan de hoy", "mi calendario", "calendario", "calendario de hoy", "actividad de hoy"} or low.startswith(
            ("plan de manana", "calendario de manana")
        ):
            calendar = self._activity_calendar_for_day(target_day, now)
            return self._emit(calendar.summary())
        if low in {"que toca despues", "que sigue despues", "siguiente bloque", "proxima actividad"}:
            calendar = self._activity_calendar_for_day(now.date(), now)
            block = calendar.next_block(now)
            if block is None:
                return self._emit("No veo mas bloques operativos para hoy.")
            return self._emit(f"Lo siguiente es {block.title} de {block.start} a {block.end}.")
        if self._looks_like_day_reorganization_request(low):
            return self._reorganize_day_command(low, now)
        return None

    def _weekly_goals_summary(self, now: datetime) -> str:
        week = self._activity_calendar_for_range(now.date(), now, days=7)
        upcoming_tasks = self._task_store().upcoming(now, days=7, limit=6)
        agenda_count = sum(len(self._agenda_items_for_day(now.date() + timedelta(days=index))) for index in range(7))
        class_days = [
            self._format_date_spanish(now.date() + timedelta(days=index))
            for index in range(7)
            if self._classes_for_day(now.date() + timedelta(days=index))
        ]
        parts = [week.summary(blocks_per_day=2)]
        if upcoming_tasks:
            parts.append("Pendientes clave: " + "; ".join(task.title for task in upcoming_tasks[:4]))
        if class_days:
            parts.append("Dias con clases: " + ", ".join(class_days[:5]))
        parts.append(f"Eventos de agenda esta semana: {agenda_count}.")
        return "Objetivos de la semana: " + " ".join(parts)

    def _day_progress_summary(self, now: datetime) -> str:
        daily = self._ensure_daily_state(now)
        pending_today = self._task_store().tasks_for_day(now.date())
        agenda_today = self._agenda_items_for_day(now.date())
        done_flags = []
        if daily.get("bath_done"):
            done_flags.append("bano")
        if daily.get("left_home"):
            done_flags.append("salida")
        if daily.get("arrived"):
            done_flags.append("llegada")
        done = ", ".join(done_flags) if done_flags else "sin marcas de rutina completadas"
        return (
            f"Avance de hoy: {done}. Agenda: {len(agenda_today)} evento(s). "
            f"Pendientes para hoy: {len(pending_today)}. "
            + self._next_commitment_summary(now)
        )

    def _start_day_close_plan(self, now: datetime) -> str:
        plan = ActionPlan(
            id=uuid.uuid4().hex[:10],
            summary="cerrar el dia con nota de revision y preparacion de manana.",
            risk="medium",
            steps=[
                PlanStep(
                    id="close_day_note",
                    description="Guardar nota de cierre del dia.",
                    action="add_daily_note",
                    payload={"date": iso_day(now.date()), "note": "Cierre del dia: revisar pendientes, agenda y preparacion de manana."},
                    mutates=True,
                ),
                PlanStep(
                    id="tomorrow_review_reminder",
                    description="Crear recordatorio para preparar manana.",
                    action="create_reminder",
                    payload={"date": iso_day(now.date()), "time": "21:00", "title": "Preparar manana y revisar pendientes"},
                    mutates=True,
                ),
            ],
            requires_confirmation=True,
            created_at=now.isoformat(timespec="seconds"),
            intent="day_close",
        )
        self._start_dialog("confirm_action_plan", {"plan": plan.to_dict()})
        return self._emit(self._describe_action_plan(plan))

    def _start_prepare_tomorrow_plan(self, now: datetime) -> str:
        target_day = now.date() + timedelta(days=1)
        classes = self._classes_for_day(target_day)
        leave_time = self._configured_leave_time_for_day(target_day)
        steps = [
            PlanStep(
                id="review_tomorrow",
                description="Revisar calendario operativo de manana.",
                action="show_activity_calendar",
                payload={"date": iso_day(target_day)},
                mutates=False,
            ),
            PlanStep(
                id="prepare_tomorrow_note",
                description="Guardar nota de preparacion para manana.",
                action="add_daily_note",
                payload={"date": iso_day(target_day), "note": "Preparacion previa: revisar mochila, clases, agenda y pendientes."},
                mutates=True,
            ),
        ]
        if classes and leave_time:
            prep_time = self._safe_reorganization_time(target_day, self._add_minutes_to_hhmm(target_day, leave_time, -45), now)
            steps.append(
                PlanStep(
                    id="tomorrow_leave_prep",
                    description=f"Crear recordatorio de preparacion para salida de manana a las {prep_time}.",
                    action="create_reminder",
                    payload={"date": iso_day(target_day), "time": prep_time, "title": "Preparar salida de manana"},
                    mutates=True,
                )
            )
        plan = ActionPlan(
            id=uuid.uuid4().hex[:10],
            summary="preparar manana usando clases, salida y calendario operativo.",
            risk="medium",
            steps=steps,
            requires_confirmation=True,
            created_at=now.isoformat(timespec="seconds"),
            intent="prepare_tomorrow",
        )
        self._start_dialog("confirm_action_plan", {"plan": plan.to_dict()})
        return self._emit(self._describe_action_plan(plan))

    def _looks_like_day_reorganization_request(self, low: str) -> bool:
        return bool(
            re.search(
                r"\b(reorganiza|organiza|acomoda|planifica|reordena)\b.*\b(mi\s+)?(dia|agenda|calendario)\b",
                low,
            )
            or re.search(r"\b(reorganiza|organiza|acomoda|planifica|reordena)\s+(hoy|manana)\b", low)
        )

    def _reorganize_day_command(self, low: str, now: datetime) -> str:
        target_day = self._parse_relative_date(low, now)
        plan = self._build_day_reorganization_plan(target_day, now)
        self._start_dialog("confirm_action_plan", {"plan": plan.to_dict()})
        return self._emit(self._describe_action_plan(plan))

    def _build_day_reorganization_plan(self, target_day: date, now: datetime) -> ActionPlan:
        target_key = iso_day(target_day)
        target_label = "hoy" if target_day == now.date() else "manana" if target_day == now.date() + timedelta(days=1) else self._format_date_spanish(target_day)
        calendar = self._activity_calendar_for_day(target_day, now)
        steps: list[PlanStep] = [
            PlanStep(
                id="review_context",
                description=f"Revisar calendario operativo de {target_label}.",
                action="show_activity_calendar",
                payload={"date": target_key},
                mutates=False,
            )
        ]

        due_tasks = self._task_store().tasks_for_day(target_day)
        undated_tasks = [task for task in self._task_store().upcoming(now, days=7, limit=5) if not task.due_date]
        task_candidates = (due_tasks + undated_tasks)[:3]
        reminder_times = self._suggest_reorganization_times(target_day, now, max(1, len(task_candidates)))
        for task, hhmm in zip(task_candidates[:3], reminder_times):
            steps.append(
                PlanStep(
                    id=f"remind_task_{task.id}",
                    description=f"Crear recordatorio para avanzar el pendiente '{task.title}' a las {hhmm}.",
                    action="create_reminder",
                    payload={"title": f"Avanzar pendiente: {task.title}", "date": target_key, "time": hhmm},
                    mutates=True,
                )
            )

        override = self._current_override(target_day)
        classes = [] if override.get("free_day") or override.get("classes_cancelled") else self._classes_for_day(target_day)
        leave_time = self._configured_leave_time_for_day(target_day)
        if classes and leave_time:
            prep_time = self._safe_reorganization_time(target_day, self._add_minutes_to_hhmm(target_day, leave_time, -30), now)
            steps.append(
                PlanStep(
                    id="prepare_leave_reminder",
                    description=f"Crear recordatorio de preparacion para salir a las {prep_time}.",
                    action="create_reminder",
                    payload={"title": "Preparar salida, mochila y pendientes", "date": target_key, "time": prep_time},
                    mutates=True,
                )
            )

        agenda_count = len(self._agenda_items_for_day(target_day))
        notes = []
        if task_candidates:
            notes.append(f"{len(task_candidates)} pendiente(s) priorizados")
        if classes:
            notes.append("clases consideradas")
        if agenda_count:
            notes.append(f"{agenda_count} evento(s) revisados")
        if not notes:
            notes.append("dia ligero con revision nocturna")
        steps.append(
            PlanStep(
                id="reorganization_note",
                description="Guardar una nota breve del plan reorganizado.",
                action="add_daily_note",
                payload={"date": target_key, "note": f"Reorganizacion de {target_label}: " + ", ".join(notes) + "."},
                mutates=True,
            )
        )

        if not task_candidates and not classes and not agenda_count:
            review_time = self._safe_reorganization_time(target_day, "21:00", now)
            steps.append(
                PlanStep(
                    id="night_review_reminder",
                    description=f"Crear recordatorio de revision del dia a las {review_time}.",
                    action="create_reminder",
                    payload={"title": "Revision nocturna y preparacion de manana", "date": target_key, "time": review_time},
                    mutates=True,
                )
            )

        return ActionPlan(
            id=uuid.uuid4().hex[:10],
            summary=(
                f"reorganizar {target_label} con base en calendario, clases, salida y pendientes. "
                f"Detecte {len(calendar.blocks)} bloque(s) operativos."
            ),
            risk="medium",
            steps=steps,
            requires_confirmation=True,
            created_at=now.isoformat(timespec="seconds"),
            intent="day_reorganization",
        )

    def _suggest_reorganization_times(self, target_day: date, now: datetime, count: int) -> list[str]:
        slots = ["10:00", "12:00", "16:00", "17:30", "19:00", "20:30"]
        suggestions = [self._safe_reorganization_time(target_day, slot, now) for slot in slots]
        unique: list[str] = []
        for hhmm in suggestions:
            if hhmm not in unique:
                unique.append(hhmm)
        while len(unique) < count:
            candidate = now + timedelta(minutes=45 + len(unique) * 60)
            if target_day != now.date():
                candidate = datetime.combine(target_day, parse_hhmm("10:00")) + timedelta(minutes=len(unique) * 75)
            hhmm = candidate.strftime("%H:%M")
            if hhmm not in unique:
                unique.append(hhmm)
        return unique[:count]

    def _safe_reorganization_time(self, target_day: date, hhmm: str, now: datetime) -> str:
        try:
            candidate = datetime.combine(target_day, parse_hhmm(hhmm))
        except Exception:
            candidate = datetime.combine(target_day, parse_hhmm("09:00"))
        if target_day == now.date() and candidate <= now + timedelta(minutes=10):
            candidate = now + timedelta(minutes=30)
            minute = 0 if candidate.minute < 30 else 30
            if candidate.minute > minute:
                candidate = candidate.replace(minute=minute, second=0, microsecond=0) + timedelta(minutes=30)
            else:
                candidate = candidate.replace(minute=minute, second=0, microsecond=0)
        return candidate.strftime("%H:%M")

    def _add_minutes_to_hhmm(self, target_day: date, hhmm: str, minutes: int) -> str:
        try:
            value = datetime.combine(target_day, parse_hhmm(hhmm)) + timedelta(minutes=minutes)
            return value.strftime("%H:%M")
        except Exception:
            return hhmm

    def _pending_tasks_command(self, low: str, now: datetime) -> Optional[str]:
        if low in {
            "que tengo pendiente",
            "que tengo pendientes",
            "pendientes",
            "mis pendientes",
            "lista pendientes",
            "listar pendientes",
            "tareas pendientes",
            "compromisos pendientes",
        } or re.search(r"\b(lista|listar|muestra|mostrar|ver|consulta)\s+(mis\s+)?(pendientes|tareas|compromisos)\b", low):
            return self._emit(self._task_store().summary())
        if low in {"pendientes de hoy", "tareas de hoy", "compromisos de hoy", "pendientes para hoy", "tareas para hoy", "compromisos para hoy"}:
            return self._emit(self._task_store().summary_for_day(now.date()))
        if low in {"pendientes de manana", "tareas de manana", "compromisos de manana", "pendientes para manana", "tareas para manana", "compromisos para manana"}:
            return self._emit(self._task_store().summary_for_day(now.date() + timedelta(days=1)))
        if low.startswith(("pendientes de ", "tareas de ", "compromisos de ", "pendientes para ", "tareas para ", "compromisos para ")):
            target_day = self._parse_relative_date(low, now)
            return self._emit(self._task_store().summary_for_day(target_day))
        return None

    def _proactive_feedback_command(self, low: str, now: datetime, daily: dict[str, Any]) -> Optional[str]:
        if low == "estado proactivo":
            cfg = self._effective_proactivity_config()
            paused = ", ".join(self.state.get("proactivity_paused_categories", [])) or "ninguna"
            last = daily.get("last_proactive_suggestion") or self.state.get("last_proactive_suggestion") or {}
            last_text = str(last.get("category", "sin sugerencias recientes"))
            return self._emit(
                f"Proactividad: {'activa' if cfg.get('enabled') else 'apagada'}, modo {cfg.get('mode')}, "
                f"cooldown {cfg.get('interval_minutes')} minutos, categorias pausadas: {paused}. "
                f"Ultima sugerencia: {last_text}."
            )
        feedback_map = {
            "buena sugerencia": "positive",
            "muy buena sugerencia": "positive",
            "esa sugerencia sirve": "positive",
            "no me recuerdes eso": "pause",
            "no sugieras esto": "pause",
            "no me sugieras esto": "pause",
            "esa sugerencia no sirve": "negative",
            "mala sugerencia": "negative",
            "recuerdame esto mas seguido": "more",
            "sugiere mas de esto": "more",
        }
        kind = feedback_map.get(low)
        if not kind:
            return None
        last = daily.get("last_proactive_suggestion") or self.state.get("last_proactive_suggestion") or {}
        category = str(last.get("category") or "general")
        feedback = self.state.setdefault("proactivity_feedback", {}).setdefault(category, {"positive": 0, "negative": 0})
        if kind == "positive":
            feedback["positive"] = int(feedback.get("positive", 0) or 0) + 1
            self._save_state()
            return self._emit("Anotado. Tomare ese tipo de sugerencia como util.")
        if kind == "negative":
            feedback["negative"] = int(feedback.get("negative", 0) or 0) + 1
            self._save_state()
            return self._emit("Anotado. Bajare prioridad a ese tipo de sugerencia.")
        if kind == "pause":
            paused = self.state.setdefault("proactivity_paused_categories", [])
            if category not in paused:
                paused.append(category)
            feedback["negative"] = int(feedback.get("negative", 0) or 0) + 1
            self._save_state()
            return self._emit(f"Entendido. Pauso sugerencias de categoria {category}.")
        cfg = self.config.setdefault("proactivity", {})
        if not isinstance(cfg, dict):
            cfg = {}
            self.config["proactivity"] = cfg
        current = int(cfg.get("interval_minutes", 120) or 120)
        cfg["interval_minutes"] = max(30, current - 30)
        self.save_config()
        return self._emit(f"Listo. Intentare sugerir con mas frecuencia. Nuevo cooldown: {cfg['interval_minutes']} minutos.")

    def _proactive_explanation_command(self, now: datetime, daily: dict[str, Any]) -> str:
        last = daily.get("last_proactive_suggestion") or self.state.get("last_proactive_suggestion") or {}
        if not isinstance(last, dict) or not last:
            suggestions = self._proactive_suggestions(now, daily)
            if not suggestions:
                return self._emit("No tengo una sugerencia proactiva reciente para explicar.")
            last = suggestions[0].to_dict()
        return self._emit(
            "Sugerencia explicada: "
            f"categoria {last.get('category', 'general')}, razon: {last.get('reason', 'sin razon registrada')}. "
            f"Mensaje: {last.get('message', '')}"
        )

    def _intelligent_status_command(self, now: datetime, daily: dict[str, Any]) -> str:
        calendar = self._activity_calendar_for_day(now.date(), now)
        suggestions = self._proactive_suggestions(now, daily)
        memory = self._memory_store().summary(max_items=4)
        pending = self._task_store().summary(limit=4)
        return self._emit(
            "Estado inteligente: "
            + memory
            + " "
            + calendar.summary(limit=5)
            + " "
            + pending
            + " "
            + self._format_proactive_suggestions(suggestions, limit=2)
        )

    def _describe_action_plan(self, plan: ActionPlan) -> str:
        steps = " ".join(f"{index}. {step.description}" for index, step in enumerate(plan.steps, start=1))
        suffix = " Diga 'confirmar' para aplicarlo o 'cancelar' para no cambiar nada." if plan.requires_confirmation else ""
        return f"Propongo este plan: {plan.summary} {steps}{suffix}"

    def _plan_unprogrammed_action(self, low: str, original: str, now: datetime, daily: dict[str, Any]) -> Optional[str]:
        plan = self._planner().create_plan(original, now)
        if plan is None:
            return None
        if plan.requires_confirmation:
            self._start_dialog("confirm_action_plan", {"plan": plan.to_dict()})
            return self._emit(self._describe_action_plan(plan))
        return self._execute_action_plan(plan, now, confirmed=False)

    def _execute_action_plan(self, plan: ActionPlan, now: datetime, *, confirmed: bool = False) -> str:
        before = self._runtime_snapshot()
        result = self._executor().execute(plan, self, now, confirmed=confirmed)
        after = self._runtime_snapshot()
        changed = self._changed_domains(before, after)
        plan_mutates = any(step.mutates for step in plan.steps)
        evidence = self._evidence_for_action_result(plan, result.message, changed)
        errors: list[str] = []
        if result.blocked:
            errors.append(result.message or "ejecucion bloqueada")
        if plan_mutates and not changed and not evidence:
            errors.append("no se detectaron cambios ni evidencia externa despues de ejecutar el plan")
        success = not errors and (not plan_mutates or bool(changed or evidence))
        status = "verified" if success else "blocked" if result.blocked else "failed"
        receipt = ExecutionReceipt.make(
            requested_action=plan.summary,
            executed_action=", ".join(step.action for step in plan.steps),
            status=status,
            success=success,
            now=now,
            evidence=evidence,
            changed_domains=changed,
            errors=errors,
            rollback_available=bool(changed),
            plan_id=plan.id,
            result_message=result.message,
        )
        self._record_execution_receipt(receipt)
        if success:
            return self._emit("Plan aplicado y verificado. " + result.message)
        if result.blocked:
            return self._emit(result.message)
        return self._emit("No pude confirmar que el plan se haya aplicado correctamente. " + result.message)

    def _json_clone(self, value: Any) -> Any:
        return json.loads(json.dumps(value, ensure_ascii=False))

    def _runtime_snapshot(self) -> dict[str, Any]:
        return {
            "state": self._json_clone(self.state),
            "agenda": self._json_clone(self.agenda),
            "memory": self._memory_store().load_profile().to_dict(),
            "pending_tasks": self._task_store().load_board().to_dict(),
        }

    def _changed_domains(self, before: dict[str, Any], after: dict[str, Any]) -> list[str]:
        domains: list[str] = []
        for key in ("state", "agenda", "memory", "pending_tasks"):
            if before.get(key) != after.get(key):
                domains.append(key)
        return domains

    def _evidence_for_action_result(
        self,
        plan: ActionPlan,
        message: str,
        changed_domains: list[str],
    ) -> list[VerificationEvidence]:
        evidence = [VerificationEvidence("state_diff", f"cambio confirmado en {domain}") for domain in changed_domains]
        low = normalize_text(message)
        if "notificacion enviada por telegram" in low:
            evidence.append(VerificationEvidence("telegram", "Telegram confirmo envio"))
        if "investigue" in low and "no pude" not in low:
            evidence.append(VerificationEvidence("research", "investigacion devolvio resultado"))
        if "abri" in low or "abierto" in low:
            evidence.append(VerificationEvidence("app", "servicio de apps respondio"))
        if not evidence and not any(step.mutates for step in plan.steps) and message:
            evidence.append(VerificationEvidence("response", "respuesta generada sin cambios"))
        return evidence

    def _begin_action_history(self, plan: ActionPlan, now: datetime) -> dict[str, Any]:
        return {
            "snapshots": self._runtime_snapshot(),
            "created_at": now.isoformat(timespec="seconds"),
            "plan_id": plan.id,
        }

    def _commit_action_history(self, context: Optional[dict[str, Any]], plan: ActionPlan, now: datetime, result: str) -> None:
        if not context:
            return
        self._history_store().record(
            summary=plan.summary or "Plan aplicado",
            plan_id=plan.id,
            steps=[step.description for step in plan.steps if step.mutates],
            snapshots=dict(context.get("snapshots") or {}),
            result=result,
            source=plan.intent or "action_plan",
            now=now,
        )

    def _restore_runtime_snapshot(self, snapshots: dict[str, Any]) -> None:
        state_snapshot = snapshots.get("state")
        agenda_snapshot = snapshots.get("agenda")
        memory_snapshot = snapshots.get("memory")
        pending_snapshot = snapshots.get("pending_tasks")
        if isinstance(state_snapshot, dict):
            self.state = self._json_clone(state_snapshot)
            self._save_state()
        if isinstance(agenda_snapshot, dict):
            self.agenda = self._json_clone(agenda_snapshot)
            self._save_agenda()
        if isinstance(memory_snapshot, dict):
            self._memory_store().save_profile(UserProfile.from_dict(memory_snapshot))
        if isinstance(pending_snapshot, dict):
            self._task_store().save_board(PendingTaskBoard.from_dict(pending_snapshot))

    def _undo_last_action(self, now: datetime) -> str:
        entry = self._history_store().latest_undoable()
        if entry is None:
            return self._emit("No hay acciones recientes que pueda deshacer.")
        self._restore_runtime_snapshot(entry.snapshots)
        self._history_store().mark_undone(entry.id, now=now)
        return self._emit(f"Listo. Reverti la ultima accion: {entry.summary}.")

    def _action_history_command(self, low: str, now: datetime) -> Optional[str]:
        if low in {
            "deshaz eso",
            "deshacer",
            "deshaz ultimo",
            "deshaz lo ultimo",
            "revierte ultimo plan",
            "revierte la ultima accion",
            "revertir ultimo plan",
            "undo",
        }:
            return self._undo_last_action(now)
        if low in {
            "que cambiaste",
            "que cambios hiciste",
            "acciones recientes",
            "historial de acciones",
            "muestrame acciones recientes",
            "mostrar acciones recientes",
        }:
            return self._emit(self._history_store().summary(limit=6))
        return None

    def _clarify_ambiguous_action(self, low: str, original: str, now: datetime) -> Optional[str]:
        request = self._clarifier().evaluate(original, now)
        if request is None:
            return None
        self._start_dialog("clarify_action", {"request": request.to_dict()})
        return self._emit(request.prompt())

    def _resolve_clarified_action(self, data: dict[str, Any], low: str, now: datetime) -> str:
        request = ClarificationRequest.from_dict(dict(data.get("request", {})))
        plan = self._clarifier().plan_from_choice(request, low, now)
        if plan is None:
            options = ", ".join(option.label for option in request.options)
            return self._emit(f"Necesito elegir una opcion: {options}. Tambien puede decir 'cancelar'.")
        self._start_dialog("confirm_action_plan", {"plan": plan.to_dict()})
        return self._emit("Entendido. " + self._describe_action_plan(plan))

    def _set_day_override(self, day: date, key: str, value: Any) -> None:
        self.state.setdefault("day_overrides", {}).setdefault(iso_day(day), {})[key] = value
        self._save_state()

    def _mark_bath_done(self, now: datetime) -> str:
        daily = self._ensure_daily_state(now)
        daily["bath_done"] = True
        self._remember_habit("bath_done", now)
        self._save_state()
        return self._emit("Perfecto. Marco que ya se bano.")

    def _mark_arrival(self, now: datetime) -> str:
        daily = self._ensure_daily_state(now)
        daily["arrived"] = True
        self._remember_habit("arrived", now)
        if weekday_key(now.date()) == "monday":
            daily["attendance_done"] = True
        self._save_state()
        if weekday_key(now.date()) == "monday":
            return self._emit(self._compose_morning_brief(now, arrived_monday=True))
        return self._emit("Entendido. Marco su llegada.")

    def _mark_left_home(self, now: datetime) -> str:
        daily = self._ensure_daily_state(now)
        daily["left_home"] = True
        self._remember_habit("left_home", now)
        self._save_state()
        return self._emit("Entendido. Marco que ya salio.")

    def _is_awake_window(self, now: datetime) -> bool:
        cfg = self.config.get("ambient_companion", {})
        return combine_today(now, str(cfg.get("wake_time", "07:30"))) <= now <= combine_today(now, str(cfg.get("sleep_time", "22:30")))

    def _estimate_home_presence(self, now: datetime, daily: dict[str, Any]) -> bool:
        if not self._is_awake_window(now):
            return False
        routines = self.config.get("weekly_routines", {})
        today_key = weekday_key(now.date())
        if daily.get("arrived"):
            return True
        if daily.get("left_home"):
            return False
        if today_key == "monday":
            monday_cfg = routines.get("monday", {})
            leave_time = combine_today(
                now,
                self._leave_override_for_day(now.date()) or str(monday_cfg.get("leave_time", "16:50")),
            )
            arrival_window = monday_cfg.get("expected_arrival_window", ["17:00", "17:30"])
            return now < leave_time or now >= combine_today(now, str(arrival_window[-1]))
        if today_key == "thursday":
            leave_time = combine_today(
                now,
                self._leave_override_for_day(now.date())
                or str(routines.get("thursday", {}).get("leave_time", "11:00")),
            )
            return now < leave_time or now >= combine_today(now, "19:30")
        if today_key == "friday":
            leave_override = self._leave_override_for_day(now.date())
            if leave_override:
                return now < combine_today(now, leave_override)
            stop_time = combine_today(now, str(routines.get("friday", {}).get("stop_all_after", "16:45")))
            return now < stop_time
        if today_key in {"tuesday", "wednesday"}:
            leave_override = self._leave_override_for_day(now.date())
            day_cfg = resolve_day_cfg(routines, today_key)
            default_leave = "12:00"
            for item in list(day_cfg.get("reminders", [])):
                item_id = str(item.get("id", "") or "")
                if "leave" in item_id.lower():
                    default_leave = str(item.get("time", default_leave) or default_leave)
                    break
            leave_time = leave_override or default_leave
            return now < combine_today(now, leave_time) or now >= combine_today(now, "19:30")
        return False

    def _next_agenda_item_today(self, now: datetime) -> Optional[dict[str, Any]]:
        for item in self._agenda_items_for_day(now.date()):
            hhmm = str(item.get("time", "") or "")
            if hhmm and combine_today(now, hhmm) >= now:
                return item
        return None

    def _ambient_message_for_context(self, now: datetime, daily: dict[str, Any]) -> tuple[str, str]:
        next_item = self._next_agenda_item_today(now)
        if next_item:
            remind_agenda = True
            try:
                event_time = combine_today(now, str(next_item.get("time", "") or ""))
                minutes_until = (event_time - now).total_seconds() / 60
                remind_agenda = minutes_until <= 120 or random.random() < 0.35
            except Exception:
                remind_agenda = True
            if not remind_agenda:
                next_item = None
        if next_item:
            options = [
                f"Senor, lo siguiente en su agenda es {next_item.get('title', 'un evento')} a las {next_item.get('time', '--:--')}.",
                f"Tiene pendiente {next_item.get('title', 'un evento')} a las {next_item.get('time', '--:--')}.",
                f"Le recuerdo que su proximo evento es {next_item.get('title', 'un evento')} a las {next_item.get('time', '--:--')}.",
            ]
            return self._pick_phrase("agenda_heads_up", options, daily=daily), "ambient"
        today_key = weekday_key(now.date())
        if today_key in {"tuesday", "wednesday"} and now < combine_today(now, "11:00"):
            return self._pick_phrase(
                "prep_university",
                [
                    "Senor, se acerca la hora de prepararse. Si quiere, le repaso lo que debe llevar.",
                    "Conviene irse preparando con calma. Si desea, le enumero lo necesario antes de salir.",
                    "Ya se aproxima la preparacion para salir. Puedo recordarle su lista cuando quiera.",
                    "Podemos dejar lista la salida por partes: mochila, pendientes y tiempo de traslado.",
                ],
                daily=daily,
            ), "ambient"
        if today_key == "thursday" and now < combine_today(now, "10:00"):
            return self._pick_phrase(
                "prep_thursday",
                [
                    "Senor, hoy sale temprano por ingles. Si quiere, le recuerdo lo que necesita antes de las once.",
                    "Hoy toca salir mas temprano por ingles. Puedo repasar su preparacion en cualquier momento.",
                    "Recuerde que hoy la salida es anticipada por su clase de ingles.",
                    "Hoy conviene cuidar el margen antes de ingles para que no se junte todo al final.",
                ],
                daily=daily,
            ), "ambient"
        if today_key == "friday" and now < combine_today(now, "11:00"):
            return self._pick_phrase(
                "prep_friday",
                [
                    "Senor, hoy es viernes. Si quiere, puedo repasar su preparacion y la maleta para regresar.",
                    "Hoy es viernes. Conviene tener presente la maleta y lo necesario para volver a casa.",
                    "Si gusta, puedo repasar la preparacion de hoy y lo que debe llevar para regresar.",
                    "Viernes pide dos revisiones: lo de hoy y lo que no debe quedarse olvidado para el lunes.",
                ],
                daily=daily,
            ), "ambient"
        if today_key == "monday" and now >= combine_today(now, "17:00") and not daily.get("arrived"):
            return self._pick_phrase(
                "arrival_monday",
                [
                    "Senor, cuando llegue aviseme para registrar su llegada y hacer el pase de lista.",
                    "En cuanto llegue, digamelo y hago el pase de lista correspondiente.",
                    "Recuerde avisarme cuando llegue para registrar la llegada de hoy.",
                    "Cuando este en casa, me avisa y cierro el registro de llegada del lunes.",
                ],
                daily=daily,
            ), "ambient"
        allow_news = int(daily.get("ambient_news_count", 0)) < int(daily.get("ambient_news_cap", 3))
        if self.config.get("conversation", {}).get("proactive_topics_enabled", True):
            return self._natural_topic_response(daily, allow_news=allow_news)
        fallback_messages = list(self.config.get("ambient_companion", {}).get("messages", []))
        if fallback_messages:
            return self._pick_phrase(
                "ambient",
                [str(x) for x in fallback_messages if str(x).strip()],
                daily=daily,
            ), "ambient"
        return "Senor, sigo atento. Si quiere, puedo revisar su agenda, clases o presupuesto.", "ambient"

    def _ambient_companion_event(self, now: datetime, daily: dict[str, Any]) -> list[ReminderEvent]:
        cfg = self.config.get("ambient_companion", {})
        if not bool(cfg.get("enabled", True)):
            return []
        if not self._estimate_home_presence(now, daily):
            return []
        last_raw = str(daily.get("last_companion_chat", "") or "").strip()
        interval = max(30, int(cfg.get("interval_minutes", 90) or 90))
        if last_raw:
            try:
                if now - datetime.fromisoformat(last_raw) < timedelta(minutes=interval):
                    return []
            except ValueError:
                pass
        message, level = self._ambient_message_for_context(now, daily)
        return [ReminderEvent(f"ambient:{iso_day(now.date())}:{now.hour:02d}{now.minute:02d}", message, level)]

    def _events_from_reminders(self, now: datetime, daily: dict[str, Any], reminders: list[dict[str, Any]], prefix: str) -> list[ReminderEvent]:
        sent = set(daily.get("sent", []))
        grace = int(self.config.get("event_grace_minutes", 12) or 12)
        events: list[ReminderEvent] = []
        for item in reminders:
            event_id = f"{prefix}:{item.get('id', uuid.uuid4())}"
            item_id = str(item.get("id", "") or "")
            hhmm = str(item.get("time", "00:00"))
            message = str(item.get("message", "") or "").strip()
            if item_id in {"wake_up", "thursday_wake", "friday_wake"} or "wake" in item_id.lower():
                message = self._compose_morning_brief(now)
            if not message:
                continue
            if combine_today(now, hhmm) <= now <= combine_today(now, hhmm) + timedelta(minutes=grace) and event_id not in sent:
                events.append(ReminderEvent(event_id, message))
        return events

    def _wake_event_ids_for_day(self, day: date) -> list[str]:
        today_key = weekday_key(day)
        if today_key == "friday":
            return ["friday:friday_wake"]
        if today_key == "thursday":
            return ["thursday:thursday_wake"]
        if today_key in {"tuesday", "wednesday"}:
            scope = routine_scope_for_day(today_key)
            wake_ids = [f"{scope}:wake_up"]
            for item in resolve_day_cfg(self.config.get("weekly_routines", {}), today_key).get("reminders", []):
                item_id = str(item.get("id", "") or "")
                if "wake" in item_id.lower():
                    wake_ids = [f"{scope}:{item_id}"]
                    break
            return wake_ids
        return []

    def _friday_extra_reminders(self, friday_cfg: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "id": "friday_packing",
                "time": str(friday_cfg.get("packing_time") or "14:30"),
                "message": str(
                    friday_cfg.get("packing_message")
                    or "Recuerde preparar la maleta para regresar a casa y revisar lo pendiente del lunes."
                ),
            },
            {
                "id": "friday_chores",
                "time": str(friday_cfg.get("chores_time") or "15:15"),
                "message": str(
                    friday_cfg.get("chores_message")
                    or "Antes de cerrar el dia, revise deberes, cargador, ropa y pendientes importantes."
                ),
            },
        ]

    def _bath_events(self, now: datetime, daily: dict[str, Any], cfg: dict[str, Any], prefix: str) -> list[ReminderEvent]:
        if daily.get("bath_done"):
            return []
        start = combine_today(now, str(cfg.get("start", "19:35")))
        stop = combine_today(now, str(cfg.get("stop", "22:30")))
        if now < start or now > stop:
            return []
        slot = int((now - start).total_seconds() // (int(cfg.get("repeat_minutes", 20) or 20) * 60))
        event_id = f"{prefix}:{slot}"
        if event_id in set(daily.get("sent", [])):
            return []
        return [ReminderEvent(event_id, str(cfg.get("message", "Recuerde banarse.")), "warning")]

    def _due_agenda_reminders(self, now: datetime, daily: dict[str, Any]) -> list[ReminderEvent]:
        sent = set(daily.get("sent", []))
        grace = int(self.config.get("event_grace_minutes", 12) or 12)
        events: list[ReminderEvent] = []
        for item in self._agenda_items_for_day(now.date()):
            hhmm = str(item.get("time", "") or "")
            if not hhmm:
                continue
            event_id = f"agenda:{item.get('id')}:{iso_day(now.date())}"
            if combine_today(now, hhmm) <= now <= combine_today(now, hhmm) + timedelta(minutes=grace) and event_id not in sent:
                events.append(ReminderEvent(event_id, f"Agenda: {item.get('title', 'Evento')} ahora.", "agenda"))
        return events

    def _built_in_events(self, now: datetime, daily: dict[str, Any]) -> list[ReminderEvent]:
        events: list[ReminderEvent] = []
        sent = set(daily.get("sent", []))
        today_key = weekday_key(now.date())
        override = self._current_override(now.date())
        routines = migrate_legacy_routines(self.config.get("weekly_routines", {}))
        monday_cfg = routines.get("monday", {})
        thursday_cfg = routines.get("thursday", {})
        friday_cfg = routines.get("friday", {})
        if today_key == "friday":
            if friday_cfg.get("enabled", True) is False:
                return events
            if now >= combine_today(now, str(friday_cfg.get("stop_all_after", "16:45"))):
                daily["day_closed"] = True
                self._save_state()
                return events
            friday_reminders = self._reminders_with_leave_override(now.date(), list(friday_cfg.get("reminders", [])))
            events.extend(self._events_from_reminders(now, daily, friday_reminders, "friday"))
            events.extend(self._events_from_reminders(now, daily, self._friday_extra_reminders(friday_cfg), "friday"))
        if daily.get("day_closed"):
            return events
        if today_key == "monday":
            if monday_cfg.get("enabled", True) is False:
                return events
            if monday_cfg.get("attendance_on_arrival") and not daily.get("arrived") and "monday_attendance_hint" not in sent:
                window = monday_cfg.get("expected_arrival_window", ["17:00", "17:30"])
                if now >= combine_today(now, str(window[0])):
                    events.append(ReminderEvent("monday_attendance_hint", str(monday_cfg.get("arrival_message", "Cuando llegue, avise para hacer el pase de lista."))))
            events.extend(self._bath_events(now, daily, monday_cfg.get("bath_followup", {}), "monday_bath"))
            return events
        if today_key == "thursday":
            if thursday_cfg.get("enabled", True) is False:
                return events
            thursday_reminders = self._reminders_with_leave_override(now.date(), list(thursday_cfg.get("reminders", [])))
            events.extend(self._events_from_reminders(now, daily, thursday_reminders, "thursday"))
            events.extend(self._bath_events(now, daily, thursday_cfg.get("bath_followup", {}), "thursday_bath"))
            return events
        if override.get("free_day") or override.get("classes_cancelled"):
            return events
        if today_key in ROUTINE_WEEKDAY_KEYS and today_key not in {"monday", "thursday", "friday"}:
            if not day_routine_enabled(routines, today_key):
                return events
            day_cfg = resolve_day_cfg(routines, today_key)
            if day_cfg.get("skip_recurring_reminders"):
                events.extend(self._bath_events(now, daily, day_cfg.get("bath_followup", {}), f"{today_key}_bath"))
                return events
            if day_cfg.get("skip_morning_routine"):
                events.extend(self._bath_events(now, daily, day_cfg.get("bath_followup", {}), f"{today_key}_bath"))
                return events
            scope = routine_scope_for_day(today_key)
            day_reminders = self._reminders_with_leave_override(now.date(), list(day_cfg.get("reminders", [])))
            events.extend(self._events_from_reminders(now, daily, day_reminders, scope))
            events.extend(self._bath_events(now, daily, day_cfg.get("bath_followup", {}), f"{today_key}_bath"))
        return events

    def _set_weekday_classes(self, weekday: str, classes: list[str]) -> str:
        schedule = dict(self.config.get("class_schedule", {}))
        schedule[weekday] = classes
        result = self.apply_gui_config_patch({"class_schedule": schedule})
        if not result.valid:
            return self._emit("No pude guardar clases: " + " ".join(result.errors))
        return self._emit(f"Perfecto. Ya guarde las clases del {WEEKDAY_LABELS[weekday]}.")

    def _set_date_classes(self, target_date: date, classes: list[str]) -> str:
        self.state.setdefault("classes_by_date", {})[iso_day(target_date)] = classes
        self._save_state()
        return self._emit(f"Perfecto. Ya guarde las clases del {iso_day(target_date)}.")

    def _classes_overview(self) -> str:
        return service_classes_overview(self.state, self.config, WEEKDAY_LABELS)

    def _weekday_in_text(self, text: str) -> Optional[str]:
        for name in ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"):
            if name in normalize_text(text).split():
                return weekday_name_to_key(name)
        return None

    def _strip_weekday_words(self, text: str) -> str:
        low = normalize_text(text)
        low = re.sub(r"\b(al|a|el|del|de|para|en)\b", " ", low)
        low = re.sub(r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", " ", low)
        return re.sub(r"\s+", " ", low).strip(" ,.-")

    def _class_names_from_text(self, text: str) -> list[str]:
        clean = normalize_text(text)
        clean = re.sub(r"\b(clase|clases|materia|materias|horario|la|el|las|los)\b", " ", clean)
        clean = re.sub(r"\b(hoy|manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", " ", clean)
        clean = re.sub(r"\s+", " ", clean).strip(" ,.-")
        return [item.strip() for item in re.split(r"[,;]| y ", clean) if item.strip()]

    def _add_class_to_weekday(self, weekday: str, class_name: str) -> str:
        classes = list(self.config.setdefault("class_schedule", {}).get(weekday, []))
        clean = class_name.strip()
        if not clean:
            return self._emit("No entendi el nombre de la clase.")
        if all(normalize_text(clean) != normalize_text(existing) for existing in classes):
            classes.append(clean)
        return self._set_weekday_classes(weekday, classes)

    def _remove_class_from_weekday(self, weekday: str, class_name: str) -> str:
        classes = list(self.config.setdefault("class_schedule", {}).get(weekday, []))
        target = normalize_text(class_name)
        remaining = [item for item in classes if target not in normalize_text(item) and normalize_text(item) not in target]
        if len(remaining) == len(classes):
            return self._emit("No encontre esa clase en ese dia.")
        return self._set_weekday_classes(weekday, remaining)

    def _classes_command(self, low: str, original: str, now: datetime) -> Optional[str]:
        if low.startswith(("agregar clase ", "agrega clase ", "anadir clase ", "añadir clase ")):
            body = re.sub(r"^(agregar clase|agrega clase|anadir clase|añadir clase)\s+", "", low).strip()
            weekday = self._weekday_in_text(body) or weekday_key(now.date())
            class_name = self._strip_weekday_words(body)
            return self._add_class_to_weekday(weekday, class_name)

        if low.startswith(("quitar clase ", "quita clase ", "eliminar clase ", "elimina clase ", "borrar clase ", "borra clase ")):
            body = re.sub(r"^(quitar clase|quita clase|eliminar clase|elimina clase|borrar clase|borra clase)\s+", "", low).strip()
            weekday = self._weekday_in_text(body) or weekday_key(now.date())
            class_name = self._strip_weekday_words(body)
            return self._remove_class_from_weekday(weekday, class_name)

        match = re.match(r"^(?:reemplazar|reemplaza|cambiar|cambia|modificar|modifica)\s+clases\s+(?:del|de|para|el)?\s*(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+(?:por|a)\s+(.+)$", low)
        if match:
            weekday = weekday_name_to_key(match.group(1))
            classes = [x.strip() for x in re.split(r"[,;]| y ", match.group(2)) if x.strip()]
            return self._set_weekday_classes(weekday, classes)

        if re.search(
            r"\b(cambia|cambiar|modifica|modificar|reemplaza|reemplazar|actualiza|actualizar|pon|poner)\b",
            low,
        ) and re.search(r"\b(horario\s+de\s+clases|clase|clases|materia|materias)\b", low):
            weekday = self._weekday_in_text(low)
            split = re.split(r"\s+(?:por|a|como)\s+", low, maxsplit=1)
            classes = self._class_names_from_text(split[1]) if len(split) > 1 else []
            explicit_date = self._parse_relative_date(low, now) if re.search(r"\b(hoy|manana)\b|\b\d{1,2}/\d{1,2}\b", low) else None
            if classes and weekday:
                return self._set_weekday_classes(weekday, classes)
            if classes and explicit_date is not None:
                return self._set_date_classes(explicit_date, classes)
            if weekday:
                self._start_dialog("classes", {"weekday": weekday})
                return self._emit(f"Digame las clases del {WEEKDAY_LABELS[weekday]} separadas por coma.")
            if explicit_date is not None:
                self._start_dialog("classes", {"date": iso_day(explicit_date)})
                return self._emit(f"Digame las clases del {iso_day(explicit_date)} separadas por coma.")
            return self._emit("Para cambiar clases, digame el dia y la lista. Ejemplo: cambia clases viernes a Ingles, POO.")

        match = re.match(r"^(?:limpiar|limpia|borrar|borra|quitar|quita|eliminar|elimina)\s+clases\s+(?:del|de|para|el)?\s*(lunes|martes|miercoles|jueves|viernes|sabado|domingo)$", low)
        if match:
            return self._set_weekday_classes(weekday_name_to_key(match.group(1)), [])

        match = re.match(r"^sin\s+clases\s+(?:el\s+)?(lunes|martes|miercoles|jueves|viernes|sabado|domingo)$", low)
        if match:
            return self._set_weekday_classes(weekday_name_to_key(match.group(1)), [])

        return None

    def _routine_scope_from_text(self, text: str) -> tuple[str, str]:
        low = normalize_text(text)
        if "jueves" in low:
            return "thursday", "jueves"
        if "viernes" in low:
            return "friday", "viernes"
        if "lunes" in low:
            return "monday", "lunes"
        if "martes" in low:
            return "tuesday", "martes"
        if "miercoles" in low:
            return "wednesday", "miercoles"
        if "sabado" in low:
            return "saturday", "sabado"
        if "domingo" in low:
            return "sunday", "domingo"
        return "tuesday", "martes"

    def _routine_slot_from_text(self, text: str) -> str:
        low = normalize_text(text)
        if any(word in low for word in ("despertar", "levantarse", "wake")):
            return "wake"
        if "desayuno" in low or "desayunar" in low:
            return "breakfast"
        if any(word in low for word in ("preparacion", "prepararse", "prep")):
            return "prep"
        if any(word in low for word in ("salida", "salir", "leave")):
            return "leave"
        if any(word in low for word in ("bano", "banarse", "baño", "bañarse")):
            return "bath"
        if "maleta" in low:
            return "packing"
        if any(word in low for word in ("deberes", "pendientes", "tareas")):
            return "chores"
        return ""

    def _routine_cfg(self, scope: str) -> dict[str, Any]:
        return self.config.setdefault("weekly_routines", {}).setdefault(scope, {})

    def _routine_find_reminder(self, cfg: dict[str, Any], slot: str) -> Optional[dict[str, Any]]:
        reminders = cfg.setdefault("reminders", [])
        if not isinstance(reminders, list):
            cfg["reminders"] = []
            reminders = cfg["reminders"]
        slot_tokens = {
            "wake": ("wake",),
            "breakfast": ("breakfast",),
            "prep": ("prep", "warning"),
            "leave": ("leave", "salida"),
        }.get(slot, ())
        if slot == "leave":
            for item in reminders:
                item_id = normalize_text(str(item.get("id", "")))
                if "leave_checklist" in item_id or "thursday_leave" in item_id:
                    return item
        for item in reminders:
            item_id = normalize_text(str(item.get("id", "")))
            message = normalize_text(str(item.get("message", "")))
            if any(token in item_id or token in message for token in slot_tokens):
                return item
        return None

    def _routine_slot_summary(self, scope: str, label: str, slot: str) -> str:
        cfg = self._routine_cfg(scope)
        if slot == "bath":
            bath = cfg.get("bath_followup", {})
            hhmm = str(bath.get("start", "") or "").strip()
            if hhmm:
                return self._emit(f"Rutina de {label}: bano configurado a las {hhmm}.")
            return self._emit(f"No encontre hora de bano configurada para {label}.")
        if scope == "friday" and slot in {"packing", "chores"}:
            prefix = "packing" if slot == "packing" else "chores"
            hhmm = str(cfg.get(f"{prefix}_time", "") or "").strip()
            if hhmm:
                return self._emit(f"Rutina de {label}: {slot} configurado a las {hhmm}.")
            return self._emit(f"No encontre hora de {slot} configurada para {label}.")
        reminder = self._routine_find_reminder(cfg, slot)
        if reminder is None:
            return self._emit("No encontre ese recordatorio de rutina.")
        return self._emit(
            f"Rutina de {label}: {slot} configurado a las {reminder.get('time', '--:--')}. "
            f"Mensaje: {reminder.get('message', 'sin mensaje')}."
        )

    def _set_routine_enabled(self, day_name: str, enabled: bool) -> str:
        day_key = weekday_name_to_key(day_name)
        routines = migrate_legacy_routines(self.config.setdefault("weekly_routines", {}))
        if day_key not in ROUTINE_WEEKDAY_KEYS:
            return self._emit("Ese dia no tiene una rutina recurrente configurada.")
        cfg = routines.setdefault(day_key, resolve_day_cfg(routines, day_key) or {})
        cfg["enabled"] = enabled
        routines[day_key] = cfg
        routines.pop("default_university_day", None)
        self.config["weekly_routines"] = routines
        self.save_config()
        self.reload()
        return self._emit(("Active" if enabled else "Desactive") + f" la rutina del {day_name}.")

    def _set_routine_slot(
        self,
        scope: str,
        slot: str,
        *,
        hhmm: Optional[str] = None,
        message: Optional[str] = None,
        clear: bool = False,
    ) -> bool:
        cfg = self._routine_cfg(scope)
        if slot == "bath":
            bath = cfg.setdefault("bath_followup", {})
            if hhmm:
                bath["start"] = hhmm
            if message is not None:
                bath["message"] = "" if clear else message.strip()
            return True
        if scope == "friday" and slot in {"packing", "chores"}:
            prefix = "packing" if slot == "packing" else "chores"
            if hhmm:
                cfg[f"{prefix}_time"] = hhmm
            if message is not None:
                cfg[f"{prefix}_message"] = "" if clear else message.strip()
            return True
        reminder = self._routine_find_reminder(cfg, slot)
        if reminder is None:
            return False
        if hhmm:
            reminder["time"] = hhmm
        if message is not None:
            reminder["message"] = "" if clear else message.strip()
        return True

    def _add_routine_reminder(self, scope: str, hhmm: str, message: str) -> str:
        cfg = self._routine_cfg(scope)
        reminders = cfg.setdefault("reminders", [])
        if not isinstance(reminders, list):
            cfg["reminders"] = []
            reminders = cfg["reminders"]
        reminders.append({"id": f"custom_{uuid.uuid4().hex[:8]}", "time": hhmm, "message": message.strip()})
        self.save_config()
        self.reload()
        return self._emit(f"Recordatorio de rutina agregado a las {hhmm}: {message.strip()}.")

    def _natural_routine_slot_query_command(self, low: str) -> Optional[str]:
        if "rutina de la manana" in low or "rutina matutina" in low:
            return None
        if not re.search(r"\b(a\s+que\s+hora|hora|horario)\b", low) or "rutina" not in low:
            return None
        slot = self._routine_slot_from_text(low)
        if not slot:
            return None
        scope, label = self._routine_scope_from_text(low)
        return self._routine_slot_summary(scope, label, slot)

    def _natural_routine_slot_change_command(self, low: str, original: str) -> Optional[str]:
        if "rutina de la manana" in low or "rutina matutina" in low:
            return None
        if "rutina" not in low or not re.search(
            r"\b(cambia|cambiar|modifica|modificar|ajusta|ajustar|mueve|mover|pon|poner|actualiza|actualizar)\b",
            low,
        ):
            return None
        slot = self._routine_slot_from_text(low)
        if not slot:
            return None
        hhmm = self._parse_time(original)
        if hhmm is None:
            return self._emit("No entendi la nueva hora. Diga por ejemplo: cambia la rutina jueves desayuno a las 8.")
        scope, label = self._routine_scope_from_text(low)
        if not self._set_routine_slot(scope, slot, hhmm=hhmm):
            return self._emit("No encontre ese recordatorio de rutina.")
        self.save_config()
        self.reload()
        return self._emit(f"Rutina de {label} actualizada: {slot} a las {hhmm}.")

    def _mentions_leave_time(self, low: str) -> bool:
        return (
            "salida" in low
            or "leave" in low
            or bool(
                re.search(
                    r"\b(horario|hora)\b.*\b(salir|salgo|salga|sales|salimos)\b|"
                    r"\b(salir|salgo|salga|sales|salimos)\b.*\b(horario|hora)\b",
                    low,
                )
            )
        )

    def _configured_leave_time_for_day(self, target_day: date) -> Optional[str]:
        override = self._leave_override_for_day(target_day)
        if override:
            return override
        routines = migrate_legacy_routines(self.config.get("weekly_routines", {}))
        target_weekday = weekday_key(target_day)
        if target_weekday == "monday":
            return str(routines.get("monday", {}).get("leave_time", "16:50")).strip() or None
        if target_weekday == "thursday":
            return str(routines.get("thursday", {}).get("leave_time", "11:00")).strip() or None
        if target_weekday == "friday":
            leave_time = str(routines.get("friday", {}).get("leave_time", "") or "").strip()
            if leave_time:
                return leave_time

        day_cfg = resolve_day_cfg(routines, target_weekday)
        for item in list(day_cfg.get("reminders", [])):
            item_id = str(item.get("id", "") or "")
            if "leave" in item_id.lower():
                return str(item.get("time", "")).strip() or None
        if target_weekday in {"tuesday", "wednesday"}:
            return "12:00"
        return None

    def _set_temporary_leave_time(self, target_day: date, hhmm: str, now: datetime) -> str:
        self.state.setdefault("day_overrides", {}).setdefault(iso_day(target_day), {})["leave_time"] = hhmm
        daily = self.state.setdefault("daily", {}).get(iso_day(target_day))
        if isinstance(daily, dict):
            leave_event_ids = {
                "default:leave_checklist",
                "default:leave_checklist_followup",
                "tuesday:leave_checklist",
                "tuesday:leave_checklist_followup",
                "wednesday:leave_checklist",
                "wednesday:leave_checklist_followup",
                "thursday:thursday_leave",
                "friday:friday_leave_checklist",
            }
            daily["sent"] = [
                event_id for event_id in list(daily.get("sent", [])) if event_id not in leave_event_ids
            ]
            daily["day_closed"] = False
        self._save_state()
        label = "hoy" if target_day == now.date() else self._format_date_spanish(target_day)
        return self._emit(f"Entendido. Cambie la salida de {label} a las {hhmm}. La rutina semanal queda igual.")

    def _natural_leave_time_query_command(self, low: str, now: datetime) -> Optional[str]:
        if not self._mentions_leave_time(low):
            return None
        if re.search(
            (
                r"\b(cambia|cambiar|cambiale|modifica|modificar|ajusta|ajustar|mueve|mover|pon|poner|"
                r"deja|dejar|actualiza|actualizar)\b"
            ),
            low,
        ):
            return None
        query_like = low.startswith(("que ", "cual ", "cuando ", "a que hora ", "horario", "mi horario"))
        if not query_like and "horario de salida" not in low:
            return None
        target_day = self._parse_relative_date(low, now)
        hhmm = self._configured_leave_time_for_day(target_day)
        if not hhmm:
            return self._emit("No tengo una salida registrada para ese dia.")
        label = "hoy" if target_day == now.date() else self._format_date_spanish(target_day)
        suffix = " temporal" if self._leave_override_for_day(target_day) else ""
        return self._emit(f"Salida{suffix} de {label}: {hhmm}.")

    def _natural_leave_time_change_command(self, low: str, original: str, now: datetime) -> Optional[str]:
        if any(word in low for word in ("recuerdame", "recordatorio", "agenda", "evento")):
            return None
        if not self._mentions_leave_time(low):
            return None
        if not re.search(
            (
                r"\b(cambia|cambiar|cambiale|modifica|modificar|ajusta|ajustar|mueve|mover|pon|poner|"
                r"deja|dejar|actualiza|actualizar)\b"
            ),
            low,
        ):
            return None
        hhmm = self._parse_time(original)
        if hhmm is None:
            return self._emit("No entendi la nueva hora de salida. Diga por ejemplo: salida a las 12 solo para hoy.")
        target_day = self._parse_relative_date(low, now)
        return self._set_temporary_leave_time(target_day, hhmm, now)

    def _routine_command(self, low: str, original: str, now: datetime) -> Optional[str]:
        if low in {"rutina", "ver rutina", "rutina semanal", "linea de rutina", "linea de tiempo rutina"}:
            return self._emit(self.get_routine_timeline())

        routine_change = self._natural_routine_slot_change_command(low, original)
        if routine_change is not None:
            return routine_change

        routine_query = self._natural_routine_slot_query_command(low)
        if routine_query is not None:
            return routine_query

        leave_query = self._natural_leave_time_query_command(low, now)
        if leave_query is not None:
            return leave_query

        match = re.match(r"^(activar|activa|desactivar|desactiva)\s+rutina\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)$", low)
        if match:
            return self._set_routine_enabled(match.group(2), match.group(1).startswith("act"))

        if low.startswith(("agregar recordatorio rutina ", "agrega recordatorio rutina ", "anadir recordatorio rutina ")):
            hhmm = self._parse_time(original)
            if not hhmm:
                return self._emit("No entendi la hora del recordatorio de rutina.")
            scope, _label = self._routine_scope_from_text(low)
            message = re.sub(
                r"^(agregar|agrega|anadir)\s+recordatorio\s+rutina\s+",
                "",
                low,
                flags=re.IGNORECASE,
            )
            message = re.sub(r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", " ", message)
            message = re.sub(r"\ba\s+las\s+\d{1,2}(?::\d{2})?\b", " ", message).strip(" ,.-")
            message = message or "Recordatorio de rutina"
            return self._add_routine_reminder(scope, hhmm, message)

        if low.startswith(("eliminar recordatorio rutina ", "elimina recordatorio rutina ", "borrar recordatorio rutina ", "borra recordatorio rutina ")):
            scope, label = self._routine_scope_from_text(low)
            slot = self._routine_slot_from_text(low)
            if not slot:
                return self._emit("No entendi que recordatorio de rutina desea eliminar.")
            if not self._set_routine_slot(scope, slot, message="", clear=True):
                return self._emit("No encontre ese recordatorio de rutina.")
            self.save_config()
            self.reload()
            return self._emit(f"Elimine el mensaje de rutina {slot} para {label}.")

        if low.startswith(("cambiar mensaje rutina ", "cambia mensaje rutina ", "modificar mensaje rutina ", "modifica mensaje rutina ")):
            scope, label = self._routine_scope_from_text(low)
            slot = self._routine_slot_from_text(low)
            parts = re.split(r"\s+a\s+|\s+por\s+|\s+como\s+", low, maxsplit=1)
            if not slot or len(parts) < 2:
                return self._emit("Diga por ejemplo: cambia mensaje rutina jueves desayuno a recuerde desayunar temprano.")
            if not self._set_routine_slot(scope, slot, message=parts[1]):
                return self._emit("No encontre ese recordatorio de rutina.")
            self.save_config()
            self.reload()
            return self._emit(f"Mensaje de rutina actualizado para {label}.")

        if any(word in low for word in ("hoy", "manana", "solo", "solamente", "por hoy")):
            temporary_leave = self._natural_leave_time_change_command(low, original, now)
            if temporary_leave is not None:
                return temporary_leave

        if low.startswith(("cambiar rutina ", "cambia rutina ", "modificar rutina ", "modifica rutina ")):
            scope, label = self._routine_scope_from_text(low)
            slot = self._routine_slot_from_text(low)
            hhmm = self._parse_time(original)
            if not slot:
                return self._emit("No entendi que parte de la rutina desea modificar.")
            if hhmm is None:
                return self._emit("No entendi la nueva hora. Diga por ejemplo: cambia rutina jueves desayuno a las 8.")
            if not self._set_routine_slot(scope, slot, hhmm=hhmm):
                return self._emit("No encontre ese recordatorio de rutina.")
            self.save_config()
            self.reload()
            return self._emit(f"Rutina de {label} actualizada: {slot} a las {hhmm}.")

        natural_leave = self._natural_leave_time_change_command(low, original, now)
        if natural_leave is not None:
            return natural_leave

        return None

    def _app_command(self, low: str, original: str) -> Optional[str]:
        if low in {"aplicaciones", "aplicaciones disponibles", "que aplicaciones puedes abrir", "que puedes abrir"}:
            available = list_available_apps()
            sample = ", ".join(available[:12])
            return self._emit(f"Puedo abrir aplicaciones y accesos como: {sample}.")
        prefixes = (
            "abre ",
            "abrir ",
            "inicia ",
            "ejecuta ",
            "lanza ",
            "pon ",
            "quiero abrir ",
            "necesito abrir ",
            "abre la app ",
            "abre la aplicacion ",
            "abre el programa ",
        )
        if low.startswith(prefixes):
            app_name = re.sub(
                r"^(abre|abrir|inicia|ejecuta|lanza|pon|quiero abrir|necesito abrir|abre la app|abre la aplicacion|abre el programa)\s+",
                "",
                low,
                flags=re.IGNORECASE,
            ).strip()
            ok, message = open_application(app_name)
            return self._emit(message if ok else message)
        return None

    def _conversation_command(self, low: str, daily: dict[str, Any]) -> Optional[str]:
        if low in {
            "dime algo",
            "cuentame algo",
            "di algo",
            "hablame de algo",
            "hablame de cualquier cosa",
            "sorprendeme",
            "saca tema",
            "inicia conversacion",
            "empieza a hablar",
            "cuentame algo diferente",
            "otro tema",
            "de que quieres hablar",
        }:
            message, _level = self._natural_topic_response(daily, allow_news=True)
            return self._emit(message)
        if low in {"dato curioso", "dame un dato curioso", "cuentame algo curioso"}:
            return self._emit(
                self._topic_phrase("facts", daily=daily)
            )
        if low in {"dame un consejo", "consejo", "consejo breve"}:
            return self._emit(
                self._topic_phrase("tips", daily=daily)
            )
        if low in {"cuentame una historia", "cuenta una historia", "dime una historia", "historia", "otra historia"}:
            return self._emit(
                self._topic_phrase("stories", daily=daily)
            )
        if low in {"cuentame un chiste", "dime un chiste", "chiste", "otro chiste"}:
            return self._emit(
                self._topic_phrase("jokes", daily=daily)
            )
        if low in {"cuentame un chiste", "dime un chiste", "chiste", "otro chiste"}:
            return self._emit(
                self._pick_phrase(
                    "jokes",
                    [
                        "¿Cual es el colmo de un programador? Tener problemas de relacion por falta de conexion.",
                        "¿Por que la computadora fue al medico? Porque tenia un virus y muy poca memoria para descansar.",
                        "Le iba a contar un chiste de bits, pero estaba demasiado corto.",
                        "¿Por que el teclado no duerme? Porque siempre tiene una tecla pendiente.",
                    ],
                )
            )
        if low in {"frase del dia", "dame una frase", "inspirame"}:
            return self._emit(
                self._topic_phrase("quotes", daily=daily)
            )
        return None

    def _normalize_math_expression(self, expression: str) -> str:
        expr = unicodedata.normalize("NFKD", expression.lower().strip())
        expr = "".join(ch for ch in expr if not unicodedata.combining(ch))
        expr = re.sub(r"[Â¿?Â¡!;:\"']", " ", expr)
        expr = expr.replace("×", "*").replace("÷", "/")
        replacements = {
            " elevado a ": " ** ",
            " potencia ": " ** ",
            " por ciento": " / 100",
            " entre ": " / ",
            " dividido entre ": " / ",
            " dividido por ": " / ",
            " por ": " * ",
            " x ": " * ",
            " mas ": " + ",
            " menos ": " - ",
        }
        expr = f" {expr} "
        for src, dst in replacements.items():
            expr = expr.replace(src, dst)
        expr = expr.replace("^", "**").replace(",", ".")
        return expr.strip()

    def _looks_like_math(self, expression: str) -> bool:
        expr = self._normalize_math_expression(expression)
        has_number = bool(re.search(r"\d", expr))
        has_operator = bool(re.search(r"(\*\*|[+\-*/%()])", expr))
        has_function = bool(re.search(r"\b(sqrt|sin|cos|tan|log|log10|radians|degrees|pi|e)\b", expr))
        return has_number and (has_operator or has_function)

    def _math_command(self, low: str, original: str) -> Optional[str]:
        prefixes = (
            "calcula ",
            "calcular ",
            "cuanto es ",
            "cuanto da ",
            "resuelve ",
            "resolver ",
            "operacion ",
            "haz la cuenta ",
        )
        expression = ""
        for prefix in prefixes:
            if low.startswith(prefix):
                expression = re.sub(
                    r"^(calcula|calcular|cuanto es|cuanto da|resuelve|resolver|operacion|haz la cuenta)\s+",
                    "",
                    original,
                    count=1,
                    flags=re.IGNORECASE,
                ).strip()
                break
        if not expression and self._looks_like_math(original):
            expression = original
        if not expression:
            return None
        if not self._looks_like_math(expression):
            return None
        return self._emit(calculate(self._normalize_math_expression(expression)))

    def _research_and_learn(self, query: str, now: Optional[datetime] = None) -> str:
        clean_query = re.sub(
            r"^(investiga|investigar|busca|buscar|busca en la web|buscar en la web|busca en internet|buscar en internet|investiga en la web|consulta|consulta en internet|aprende sobre|resuelve|resolver)\s+",
            "",
            query.strip(),
            count=1,
            flags=re.IGNORECASE,
        ).strip()
        if not clean_query:
            return self._emit("Indiqueme que tema desea investigar.")
        result = search_web(clean_query)
        if not result or normalize_text(result).startswith("no encontre resultados"):
            return self._emit(f"No pude investigar {clean_query} en la web ahora mismo.")
        learned = self.state.setdefault("learned_web", [])
        if isinstance(learned, list):
            learned.append(
                {
                    "query": clean_query,
                    "summary": result,
                    "timestamp": (now or datetime.now()).isoformat(timespec="seconds"),
                }
            )
            self.state["learned_web"] = learned[-80:]
            self._save_state()
        try:
            log_user_action(normalize_text(clean_query)[:50], category="web")
        except Exception:
            pass
        safety_note = ""
        if any(word in normalize_text(clean_query) for word in ("suicidio", "suicida", "suicidarse")):
            safety_note = (
                " Si esta investigacion tiene que ver con usted o alguien cercano en riesgo, "
                "no lo deje solo y contacte emergencias locales o una linea de crisis."
            )
        return self._emit(f"Investigue y lo guarde para contexto: {clean_query}. Resumen: {result}{safety_note}")

    def _should_auto_research(self, low: str) -> bool:
        if len(low.split()) < 3:
            return False
        question_prefixes = (
            "que es ",
            "quien es ",
            "como funciona ",
            "como se ",
            "por que ",
            "cuando ",
            "donde ",
            "cual es ",
            "explica ",
            "dime sobre ",
        )
        return low.startswith(question_prefixes)

    def _web_command(self, low: str, original: str) -> Optional[str]:
        if low in {"noticias", "ultimas noticias", "resumen de noticias"}:
            return self._emit(self._news_summary(max_items=5))
        if low in {"investiga", "buscar en la web", "busca en la web", "investigar en la web", "consulta en internet"}:
            return self._emit("Que tema desea que investigue?")
        web_prefixes = (
            "investiga ",
            "investigar ",
            "busca ",
            "buscar ",
            "busca en la web ",
            "buscar en la web ",
            "busca en internet ",
            "buscar en internet ",
            "investiga en la web ",
            "consulta ",
            "consulta en internet ",
            "aprende sobre ",
            "resuelve ",
            "resolver ",
        )
        if low.startswith(web_prefixes):
            query = re.sub(
                r"^(investiga|investigar|busca|buscar|busca en la web|buscar en la web|busca en internet|buscar en internet|investiga en la web|consulta|consulta en internet|aprende sobre|resuelve|resolver)\s+",
                "",
                low,
                flags=re.IGNORECASE,
            ).strip()
            if not query:
                return self._emit("Indiqueme que tema desea investigar.")
            return self._research_and_learn(query)
        return None

    def _budget_command(self, low: str, original: str) -> Optional[str]:
        response = handle_budget_command(low, original)
        return self._emit(response) if response is not None else None

    def _wake_command(self, low: str, original: str) -> Optional[str]:
        wake_change = self._wake_schedule_change_command(low, original, datetime.now())
        if wake_change is not None:
            return wake_change
        if self._looks_like_wake_schedule_query(low):
            return self._emit(self._wake_schedule_summary(datetime.now(), target_day=self._parse_relative_date(low, datetime.now())))
        if low in {"diagnostico energia", "diagnostico de energia", "diagnostico energia y bloqueo", "estado energia", "energia y bloqueo"}:
            return self._emit(self._format_energy_diagnostics(get_energy_diagnostics()))
        if low in {"reparar despertar", "reparar autoarranque", "reparar energia", "reparar despertar seguro"}:
            wake_time = str(self.config.get("automation", {}).get("morning_wake_time", "07:30"))
            ok, message = repair_wake_configuration(wake_time)
            if ok:
                self.reload()
            return self._emit(message)
        if low in {"probar despertar en 2 minutos", "probar despertar dos minutos", "prueba despertar en 2 minutos"}:
            ok, message = schedule_wake_test(2)
            suffix = " Deje la laptop en suspension para probar reactivacion." if ok else ""
            return self._emit(message + suffix)
        if low in {"activar modo residente", "modo residente", "activar residente", "instalar viernes en la laptop"}:
            ok, message = install_resident_mode()
            if ok:
                self.reload()
                return self._emit(
                    "Inicio de sesion y rutina matutina activados y verificados. "
                    "Viernes se abre al iniciar sesion; la tarea solo puede intentar reactivar una suspension compatible. "
                    "No puede encender un equipo apagado ni desbloquear Windows."
                )
            return self._emit(message)
        if low in {"desactivar modo residente", "quitar modo residente", "desactivar residente"}:
            ok, message = remove_resident_mode()
            if ok:
                return self._emit("Modo residente desactivado. Viernes ya no iniciara automaticamente.")
            return self._emit(message)
        if low in {"verificar despertar", "estado del despertar", "estado residente", "diagnostico de despertar"}:
            status = get_resident_status()
            return self._emit(
                "Estado actual: "
                f"inicio de sesion {status['startup']}, "
                f"tarea programada {status['task']}, "
                f"hora configurada {status['wake_time']}, "
                f"proxima ejecucion {status.get('next_run', 'desconocido')}, "
                f"ultimo resultado {status.get('last_result_hex') or status.get('last_result', 'desconocido')}: "
                f"{status.get('last_result_message', 'sin datos')}. "
                "La reactivacion requiere suspension compatible y temporizadores permitidos; no hay desbloqueo automatico."
            )
        if low in {"probar despertar", "probar rutina matutina", "probar rutina de la manana", "probar el despertar", "probar la rutina de la manana"}:
            brief = self._compose_morning_brief(datetime.now())
            return self._emit(
                "Prueba de despertar completada. "
                "Esto es lo que Viernes ejecutaria en la rutina de la manana: "
                + brief
            )
        if low in {"despertar", "activar despertar"}:
            wake_time = str(self.config.get("automation", {}).get("morning_wake_time", "07:30"))
            ok = setup_morning_wake(wake_time)
            if ok:
                self.reload()
                return self._emit(f"Listo. La rutina matutina queda activa a las {wake_time}. Solo intentara reactivar desde suspension compatible; no arranca ni desbloquea Windows.")
            return self._emit("Windows no confirmo la tarea de rutina; la configuracion no se marco como activa.")
        if low.startswith("despertar a las ") or low.startswith("programar despertar a las "):
            hhmm = self._parse_time(original)
            if not hhmm:
                return self._emit("No entendi la hora. Diga por ejemplo: despertar a las 8 o despertar a las 07:30.")
            ok = setup_morning_wake(hhmm)
            if ok:
                self.reload()
                return self._emit(f"Listo. La rutina matutina ahora queda programada a las {hhmm}.")
            return self._emit("Windows no confirmo la nueva hora de rutina.")
        if low in {"cancelar despertar", "desactivar despertar"}:
            ok = remove_scheduled_task("Viernes Morning Wake")
            if ok:
                return self._emit("Listo. Se cancelo el despertar automatico.")
            return self._emit("No pude cancelar el despertar automatico desde aqui.")
        return None

    def _format_energy_diagnostics(self, diagnostics: dict[str, Any]) -> str:
        resident = diagnostics.get("resident", {}) if isinstance(diagnostics.get("resident", {}), dict) else {}
        timers = diagnostics.get("wake_timers", {}) if isinstance(diagnostics.get("wake_timers", {}), dict) else {}
        policy = diagnostics.get("timer_policy", {}) if isinstance(diagnostics.get("timer_policy", {}), dict) else {}
        power = diagnostics.get("power", {}) if isinstance(diagnostics.get("power", {}), dict) else {}
        ac_policy = self._format_enabled_state(policy.get("ac_enabled"))
        dc_policy = self._format_enabled_state(policy.get("dc_enabled"))
        active_timers = "si" if timers.get("has_timers") else "no"
        timer_status = active_timers if timers.get("available", True) else "no verificable"
        session = str(diagnostics.get("session", "desconocida"))
        return (
            "Diagnostico de energia: "
            f"tarea {resident.get('task', 'desconocida')}, "
            f"proxima ejecucion {resident.get('next_run', 'desconocida')}, "
            f"wake timers activos: {timer_status}, "
            f"temporizadores AC {ac_policy}, bateria {dc_policy}, "
            f"bateria detectada {power.get('battery_present', 'desconocido')}, "
            f"carga {power.get('battery_charge', '') or 'desconocida'}, "
            f"sesion {session}. "
            + (f"Consulta de timers: {timers.get('error')}. " if timers.get("error") else "")
            + "Limite real: solo puede intentar reactivar desde suspension compatible; no enciende un equipo apagado y no desbloquea Windows."
        )

    def _format_enabled_state(self, value: Any) -> str:
        if value is True:
            return "permitidos"
        if value is False:
            return "bloqueados"
        return "desconocidos"

    def _wake_schedule_change_command(self, low: str, original: str, now: datetime) -> Optional[str]:
        if not self._looks_like_wake_schedule_change(low):
            return None
        hhmm = self._parse_time(original) or self._parse_time(low)
        if not hhmm:
            return self._emit("No entendi la nueva hora. Diga por ejemplo: cambia la rutina de la manana a las 8:30.")
        ok = setup_morning_wake(hhmm)
        if ok:
            self.config.setdefault("automation", {})["morning_wake_time"] = hhmm
            self.config["morning_wake_enabled"] = True
            self.save_config()
            self.reload()
            target_day = self._parse_relative_date(low, now)
            label = "manana" if target_day == now.date() + timedelta(days=1) else "hoy" if target_day == now.date() else self._format_date_spanish(target_day)
            return self._emit(
                f"Listo. La rutina de la manana queda programada a las {hhmm}. "
                f"Para {label}, Windows intentara ejecutar Viernes Morning Wake si la laptop queda en suspension compatible. "
                "No enciende un equipo apagado ni desbloquea la sesion."
            )
        return self._emit("Windows no confirmo la nueva hora de rutina; no la marque como activa.")

    def _looks_like_wake_schedule_change(self, low: str) -> bool:
        wake_terms = ("autoarranque", "despertar", "rutina de la manana", "rutina matutina")
        if not any(term in low for term in wake_terms):
            return False
        change_terms = (
            r"\b(cambia|cambiar|cambiale|modifica|modificar|ajusta|ajustar|mueve|mover|"
            r"programa|programar|pon|poner|deja|dejar|actualiza|actualizar)\b"
        )
        if not re.search(change_terms, low):
            return False
        return bool(self._parse_time(low) or re.search(r"\b(hora|horario|a\s+las)\b", low))

    def _looks_like_wake_schedule_query(self, low: str) -> bool:
        if self._looks_like_wake_schedule_change(low):
            return False
        wake_terms = ("autoarranque", "despertar", "rutina de la manana", "rutina matutina")
        schedule_terms = ("a que hora", "hora", "horario", "configurado", "iniciara", "inicia", "ejecutara", "programado")
        return any(term in low for term in wake_terms) and any(term in low for term in schedule_terms)

    def _voice_command(self, low: str) -> Optional[str]:
        if low in {"activar voz", "enciende voz", "habilitar voz", "activa modulo de voz", "activar modulo de voz"}:
            self.config["voice_enabled"] = True
            self.voice.enabled = True
            self.save_config()
            extra = " El microfono esta disponible." if speech_input_available() else " El microfono no esta disponible; puede seguir escribiendo."
            return self._emit("Voz activada. Viernes volvera a responder hablando." + extra)
        if low in {"desactivar voz", "apagar voz", "silenciar voz", "mute", "modo silencio"}:
            self.config["voice_enabled"] = False
            self.voice.enabled = False
            self.save_config()
            return self._emit("Voz desactivada. Sigo disponible por texto.")
        if low in {"estado de voz", "modulo de voz", "voz", "microfono"}:
            voice_state = "activa" if self.voice.enabled else "desactivada"
            mic_state = "disponible" if speech_input_available() else "no disponible"
            return self._emit(
                f"Voz de salida: {voice_state}. Entrada por microfono: {mic_state}. "
                "Puede pulsar Alt-Izq para escuchar desde la GUI o usar el boton Hablar."
            )
        if low in {"escuchar", "empieza a escuchar", "activar escucha", "alt izq", "alt izquierda"}:
            mic_state = "disponible" if speech_input_available() else "no disponible"
            return self._emit(
                f"Escucha por Alt-Izq configurada. Microfono: {mic_state}. "
                "Si Windows no permite el atajo global, funciona cuando la ventana de Viernes esta enfocada."
            )
        return None

    def _telegram_notifier(self) -> TelegramNotifier:
        cfg = self.config.get("telegram", {})
        if not isinstance(cfg, dict):
            cfg = {}
        enabled = bool(cfg.get("enabled", False))
        token = str(cfg.get("token", "") or "").strip() if enabled else ""
        chat_id = str(cfg.get("chat_id", "") or "").strip() if enabled else ""
        return TelegramNotifier(token, chat_id)

    def _analysis_config(self) -> dict[str, Any]:
        cfg = self.config.get("analysis", {})
        if not isinstance(cfg, dict) or not cfg:
            cfg = self.config.get("analysis_beta", {})
        if not isinstance(cfg, dict):
            cfg = {}
        return {
            "enabled": bool(cfg.get("enabled", True)),
            "save_reports": bool(cfg.get("save_reports", True)),
            "allow_web_research": bool(cfg.get("allow_web_research", True)),
            "max_rows": int(cfg.get("max_rows", 20) or 20),
            "chart_backend": str(cfg.get("chart_backend", "matplotlib") or "matplotlib"),
        }

    def _analysis_context(self, now: datetime) -> dict[str, Any]:
        return {
            "budget": get_balance(),
            "budget_categories": get_expenses_by_category(),
            "recent_transactions": get_recent_transactions()[:10],
            "agenda_today": self._agenda_items_for_day(now.date()),
            "classes_today": self._classes_for_day(now.date()),
            "pending_tasks": [task.to_dict() for task in self._task_store().upcoming(now, days=7, limit=10)],
            "leave_time": self._configured_leave_time_for_day(now.date()),
            "activity_calendar": self._activity_calendar_for_day(now.date(), now).to_dict(),
        }

    def _analysis_result_response(self, result: SimulationResult, now: datetime, slug: str) -> str:
        cfg = self._analysis_config()
        if result.chart is not None:
            rendered = render_chart(result.chart, self._analysis_reports_dir(), slug)
            result = replace(result, chart=rendered)
            if not rendered.path or not Path(rendered.path).exists():
                result = replace(
                    result,
                    risks=list(result.risks) + ["no se confirmo la generacion del archivo de grafica"],
                )
        report_path = ""
        if cfg.get("save_reports", True):
            try:
                saved_report = self._report_builder().save_report(result, self._analysis_reports_dir(), slug=slug)
                if saved_report.exists():
                    report_path = str(saved_report)
                else:
                    result = replace(result, risks=list(result.risks) + ["no se confirmo el guardado del reporte"])
            except Exception as exc:
                result = replace(result, risks=list(result.risks) + [f"no pude guardar el reporte: {exc}"])
        payload = result.to_dict()
        payload["timestamp"] = now.isoformat(timespec="seconds")
        payload["report_path"] = report_path
        self.state["last_analysis"] = payload
        self.state["last_analysis_beta"] = payload
        reports = self.state.setdefault("analysis_reports", [])
        if not isinstance(reports, list):
            reports = []
        if report_path:
            reports.insert(0, {"path": report_path, "title": result.title, "timestamp": payload["timestamp"]})
        self.state["analysis_reports"] = reports[:20]
        evidence = [VerificationEvidence("analysis", f"resultado estructurado: {result.title}")]
        errors: list[str] = []
        if report_path and Path(report_path).exists():
            evidence.append(VerificationEvidence("file", f"reporte guardado: {report_path}"))
        elif cfg.get("save_reports", True):
            errors.append("no se confirmo archivo de reporte")
        chart_path = str(result.chart.path if result.chart is not None else "")
        if chart_path:
            if Path(chart_path).exists():
                evidence.append(VerificationEvidence("file", f"grafica guardada: {chart_path}"))
            else:
                errors.append("no se confirmo archivo de grafica")
        for risk in result.risks:
            if str(risk).startswith("no se confirmo") or str(risk).startswith("no pude"):
                errors.append(str(risk))
        receipt = ExecutionReceipt.make(
            requested_action=slug,
            executed_action="analysis",
            status="verified" if not errors else "partial",
            success=not errors,
            now=now,
            evidence=evidence,
            changed_domains=["analysis_reports"] if report_path else ["analysis_state"],
            errors=errors,
            rollback_available=False,
            result_message=result.summary,
        )
        self._record_execution_receipt(receipt)
        return self._emit(self._report_builder().format_result(result))

    def _analysis_command(self, low: str, original: str, now: datetime, intent: str = "") -> Optional[str]:
        cfg = self._analysis_config()
        if not cfg.get("enabled", True):
            return self._emit("Analisis esta apagado en la configuracion.")
        detected = intent or self._analysis_intent_from_text(low)
        if not detected:
            return None
        if detected == "research_table":
            if not cfg.get("allow_web_research", True):
                return self._emit("La investigacion web para Analisis esta apagada.")
            query = self._analysis_query_from_text(low, original, detected)
            research = self._research_table_builder().build(query, search_web, max_rows=int(cfg.get("max_rows", 20)))
            return self._analysis_result_response(research.to_simulation_result(), now, "investigacion-tabla")
        query = self._analysis_query_from_text(low, original, detected)
        kind = "chart" if detected == "chart_request" else "report" if detected == "analysis_report" else "simulation"
        request = SimulationRequest(text=query or original, kind=kind)
        result = self._simulation_engine().evaluate(request, self._analysis_context(now), now)
        return self._analysis_result_response(result, now, kind)

    def _analysis_intent_from_text(self, low: str) -> str:
        if re.match(r"^(simula|simular|analiza\s+escenario|escenario)\s+\S+", low) or re.match(r"^que\s+pasaria\s+si\s+\S+", low):
            return "simulation_request"
        if re.match(r"^(dame|dime|genera|propone|propon|sugiere)\s+(tus\s+propias\s+)?ideas?\b", low):
            return "simulation_request"
        if re.search(r"\b(grafica|grafico|chart)\b", low):
            return "chart_request"
        if re.search(r"\btabla\b", low) and (
            re.search(r"\b(investiga|investigar|busca|buscar|consulta|haz|hacer|crea|crear|genera|generar|compara|comparar)\b", low)
            or re.match(r"^tabla\s+(de|sobre)\s+\S+", low)
        ):
            return "research_table"
        if re.match(r"^(reporte|informe|analisis)\s+(de|del|sobre)\s+\S+", low):
            return "analysis_report"
        return ""

    def _analysis_query_from_text(self, low: str, original: str, intent: str) -> str:
        text = original.strip()
        if intent == "simulation_request":
            return re.sub(r"^(simula|simular|analiza\s+escenario|escenario|que\s+pasaria\s+si)\s+", "", text, flags=re.IGNORECASE).strip()
        if intent == "research_table":
            query = re.sub(r"^(investiga|investigar|busca|buscar|consulta)(\s+en\s+internet)?\s+", "", text, flags=re.IGNORECASE).strip()
            query = re.sub(r"^(haz|hacer|crea|crear|genera|generar)\s+(una\s+)?tabla\s+(de|sobre)?\s*", "", query, flags=re.IGNORECASE).strip()
            query = re.sub(r"^tabla\s+(de|sobre)?\s*", "", query, flags=re.IGNORECASE).strip()
            query = re.sub(r"\b(y\s+)?(haz|hacer|crea|crear|genera|generar)\s+(una\s+)?tabla\b", " ", query, flags=re.IGNORECASE)
            query = re.sub(r"\b(en\s+)?tabla\b", " ", query, flags=re.IGNORECASE)
            return re.sub(r"\s+", " ", query).strip(" ,-")
        if intent == "chart_request":
            query = re.sub(r"^(haz|hacer|crea|crear|genera|generar|muestra|mostrar)\s+(una\s+)?(grafica|grafico|chart)\s+(de|sobre)?\s*", "", text, flags=re.IGNORECASE).strip()
            return query or original
        if intent == "analysis_report":
            return re.sub(r"^(reporte|informe|analisis)\s+(de|del|sobre)?\s*", "", text, flags=re.IGNORECASE).strip() or original
        return original

    def _remote_control_service(self) -> RemoteControlService:
        cfg = self.config.get("telegram", {})
        token = str(cfg.get("token", "") or "").strip() if isinstance(cfg, dict) else ""
        return RemoteControlService(
            self.config,
            self.state,
            decision_resolver=lambda command, moment: self._decide_command(command, moment),
            command_runner=lambda command, moment, confirmed: self._run_remote_command(command, moment, confirmed),
            client=TelegramClient(token) if token else None,
        )

    def _send_remote_telegram(self, chat_id: str, message: str) -> bool:
        cfg = self.config.get("telegram", {})
        if not isinstance(cfg, dict):
            return False
        token = str(cfg.get("token", "") or "").strip()
        if not token or not chat_id:
            return False
        result = TelegramClient(token).send_message(str(chat_id), message)
        return result.ok

    def _run_remote_command(self, command: str, now: datetime, confirmed: bool) -> str:
        response = self.process_command(command, now=now)
        if confirmed and isinstance(self.pending_dialog, dict):
            kind = str(self.pending_dialog.get("kind", ""))
            if kind in {"confirm_action_plan", "confirm_destructive"}:
                response = self.process_command("confirmar", now=now)
                if isinstance(self.pending_dialog, dict):
                    response += " Advertencia: la confirmacion remota no cerro el dialogo pendiente."
        return response

    def _remote_control_snapshot(self) -> dict[str, Any]:
        cfg = self.config.get("remote_control", {})
        if not isinstance(cfg, dict):
            cfg = {}
        state = self.state.get("remote_control", {})
        if not isinstance(state, dict):
            state = {}
        pending = state.get("pending_confirmations", {})
        history = state.get("history", [])
        if not isinstance(history, list):
            history = []
        status = get_remote_resident_status()
        return {
            "enabled": bool(cfg.get("enabled", False)),
            "allowed_chat_ids": len(cfg.get("allowed_chat_ids", []) if isinstance(cfg.get("allowed_chat_ids", []), list) else []),
            "owner_chat_ids": len(cfg.get("owner_chat_ids", []) if isinstance(cfg.get("owner_chat_ids", []), list) else []),
            "trusted_chat_ids": len(cfg.get("trusted_chat_ids", []) if isinstance(cfg.get("trusted_chat_ids", []), list) else []),
            "read_only_chat_ids": len(cfg.get("read_only_chat_ids", []) if isinstance(cfg.get("read_only_chat_ids", []), list) else []),
            "pending_confirmations": len(pending) if isinstance(pending, dict) else 0,
            "update_offset": int(state.get("update_offset", 0) or 0),
            "last_poll_at": str(state.get("last_poll_at", "") or ""),
            "last_error": str(state.get("last_error", "") or ""),
            "history": history[:10],
            "resident": status,
            "calls_enabled": bool(self.config.get("remote_calls", {}).get("enabled", False)) if isinstance(self.config.get("remote_calls", {}), dict) else False,
        }

    def _remote_control_command(self, low: str, original: str, now: datetime) -> Optional[str]:
        if low in {"estado control remoto", "estatus control remoto"}:
            return self._emit(self._remote_control_service().status())
        if low in {"estado remoto residente", "estatus remoto residente", "estado control remoto residente"}:
            status = get_remote_resident_status()
            return self._emit(f"Remoto residente: {status.get('task', 'desconocido')}. {status.get('detail', '')[:400]}")
        if low in {"activar remoto residente", "activa remoto residente", "activar control remoto residente"}:
            seconds = int(self.config.get("remote_control", {}).get("poll_interval_seconds", 5) or 5) if isinstance(self.config.get("remote_control", {}), dict) else 5
            ok, message = install_remote_resident_mode(seconds)
            return self._emit(message if ok else "No pude activar remoto residente: " + message)
        if low in {"desactivar remoto residente", "desactiva remoto residente", "quitar remoto residente", "desactivar control remoto residente"}:
            ok, message = remove_remote_resident_mode()
            return self._emit(message if ok else "No pude desactivar remoto residente: " + message)
        if low in {"probar polling remoto", "probar polling telegram", "probar recepcion telegram"}:
            results = self.remote_control_tick(now)
            errors = [err for result in results for err in getattr(result, "errors", [])]
            if errors:
                return self._emit("Polling remoto ejecutado con errores: " + "; ".join(errors[:3]))
            return self._emit(f"Polling remoto ejecutado. Actualizaciones procesadas: {len(results)}.")
        if low in {"limpiar historial remoto", "limpia historial remoto"}:
            remote = self.state.setdefault("remote_control", {})
            if isinstance(remote, dict):
                remote["history"] = []
                self._save_state()
            return self._emit("Historial remoto limpiado.")
        if low in {"reenviar ultimo resultado remoto", "reenviar ultima respuesta remota"}:
            snapshot = self._remote_control_snapshot()
            history = snapshot.get("history", []) if isinstance(snapshot.get("history", []), list) else []
            last_out = next((item for item in history if isinstance(item, dict) and item.get("direction") == "out"), None)
            if not last_out:
                return self._emit("No hay respuesta remota reciente para reenviar.")
            cfg = self.config.get("telegram", {})
            chat_id = str(last_out.get("chat_id") or (cfg.get("chat_id", "") if isinstance(cfg, dict) else "")).strip()
            if not chat_id:
                return self._emit("No encontre chat_id para reenviar.")
            sent = self._send_remote_telegram(chat_id, str(last_out.get("text", "")))
            return self._emit("Ultimo resultado remoto reenviado." if sent else "No pude reenviar el ultimo resultado remoto.")
        if low in {"probar control remoto", "prueba control remoto"}:
            cfg = self.config.get("telegram", {})
            if not isinstance(cfg, dict) or not cfg.get("enabled") or not str(cfg.get("token", "") or "").strip():
                return self._emit("Control remoto requiere Telegram activo con token y chat_id.")
            remote_cfg = self.config.get("remote_control", {}) if isinstance(self.config.get("remote_control", {}), dict) else {}
            allowed = remote_cfg.get("allowed_chat_ids", [])
            chat_id = str((allowed[0] if isinstance(allowed, list) and allowed else cfg.get("chat_id", "")) or "").strip()
            if not chat_id:
                return self._emit("Control remoto no tiene chats permitidos.")
            sent = self._send_remote_telegram(chat_id, "Viernes: prueba de control remoto segura.")
            return self._emit("Prueba de control remoto enviada." if sent else "No pude enviar la prueba de control remoto.")
        if low in {"activar control remoto telegram", "activa control remoto telegram", "activar control remoto", "activa control remoto"}:
            cfg = self.config.get("telegram", {})
            if not isinstance(cfg, dict) or not str(cfg.get("token", "") or "").strip() or not str(cfg.get("chat_id", "") or "").strip():
                return self._emit("Para activar control remoto, configure primero telegram.token y telegram.chat_id.")
            cfg["enabled"] = True
            self.config["telegram"] = cfg
            remote_cfg = self.config.setdefault("remote_control", {})
            if not isinstance(remote_cfg, dict):
                remote_cfg = {}
                self.config["remote_control"] = remote_cfg
            remote_cfg["enabled"] = True
            if not remote_cfg.get("allowed_chat_ids"):
                remote_cfg["allowed_chat_ids"] = [str(cfg.get("chat_id", "")).strip()]
            if not remote_cfg.get("owner_chat_ids"):
                remote_cfg["owner_chat_ids"] = [str(cfg.get("chat_id", "")).strip()]
            self.save_config()
            return self._emit("Control remoto por Telegram activado con confirmacion obligatoria para cambios.")
        return None

    def _game_command(self, low: str, original: str, now: datetime) -> Optional[str]:
        games_state = self.state.setdefault("games", {})
        if not isinstance(games_state, dict):
            games_state = {}
            self.state["games"] = games_state
        before = self._json_clone(games_state)
        result = self._game_engine().handle(original, games_state, now)
        if result is None:
            return None
        changed = before != games_state
        if changed or result.mutated:
            self._save_state()
        evidence = []
        if changed:
            evidence.append(VerificationEvidence("game_state", f"estado de juego actualizado: {result.game or games_state.get('active', 'juego')}"))
        elif result.message:
            evidence.append(VerificationEvidence("game_response", "respuesta de juego generada"))
        if result.game:
            executed_action = "game_move" if before.get("active") == result.game else "game_start"
        else:
            executed_action = "game_query"
        receipt_status = "verified"
        if result.status == "failed":
            receipt_status = "failed"
        elif result.status == "invalid":
            receipt_status = "rejected"
        receipt = ExecutionReceipt.make(
            requested_action=original,
            executed_action=executed_action,
            status=receipt_status,
            success=receipt_status == "verified",
            now=now,
            evidence=evidence,
            changed_domains=["games"] if changed else [],
            errors=[] if receipt_status == "verified" else [result.message],
            rollback_available=changed,
            result_message=result.message,
        )
        self._record_execution_receipt(receipt)
        if result.game:
            try:
                self._personal_activity_service().record_internal_game(
                    result.game,
                    executed_action,
                    status=result.status,
                    when=now,
                )
            except Exception:
                pass
        return self._emit(result.message)

    def _poll_remote_control(self, now: datetime) -> list[Any]:
        cfg = self.config.get("remote_control", {})
        telegram = self.config.get("telegram", {})
        if not isinstance(cfg, dict) or not isinstance(telegram, dict):
            return []
        if not cfg.get("enabled", False) or not telegram.get("enabled", False):
            return []
        token = str(telegram.get("token", "") or "").strip()
        if not token:
            return []
        results = self._remote_control_service().poll_telegram(token, now)
        self._save_state()
        return results

    def remote_control_tick(self, now: Optional[datetime] = None) -> list[Any]:
        when = now or datetime.now()
        self.reload()
        return self._poll_remote_control(when)

    def _telegram_command(self, low: str, original: str, now: datetime) -> Optional[str]:
        cfg = self.config.setdefault("telegram", {})
        if not isinstance(cfg, dict):
            cfg = {}
            self.config["telegram"] = cfg
        if low in {"activar telegram", "activa telegram", "configurar telegram"}:
            token = str(cfg.get("token", "") or "").strip()
            chat_id = str(cfg.get("chat_id", "") or "").strip()
            if not token or not chat_id:
                return self._emit("Para activar Telegram, agregue telegram.token y telegram.chat_id en la configuracion y luego diga 'activar telegram'.")
            cfg["enabled"] = True
            self.save_config()
            return self._emit("Telegram activado para notificaciones de Viernes.")
        if low in {"probar telegram", "prueba telegram"}:
            notifier = self._telegram_notifier()
            if not notifier.is_enabled():
                return self._emit("Telegram no esta configurado. Agregue token/chat_id y diga 'activar telegram'.")
            sent = notifier.send("Viernes: prueba de notificacion correcta.")
            return self._emit("Telegram respondio correctamente." if sent else "No pude enviar la prueba de Telegram.")
        if low.startswith(("notificarme por telegram", "avisame por telegram")):
            notifier = self._telegram_notifier()
            if not notifier.is_enabled():
                return self._emit("Telegram no esta configurado. Agregue token/chat_id y diga 'activar telegram'.")
            message = re.sub(r"^(notificarme por telegram|avisame por telegram)\s*", "", original, flags=re.IGNORECASE).strip()
            if not message:
                message = self._compose_smart_daily_brief(now)
            sent = notifier.send(message)
            return self._emit("Notificacion enviada por Telegram." if sent else "No pude enviar la notificacion por Telegram.")
        return None

    def _nlu_signal_tags(self, low: str) -> list[str]:
        checks = (
            ("question", r"^(que|cual|cuando|como|donde|por que|quien)\b"),
            ("time", r"\ba\s+las\b|\b\d{1,2}(?::\d{2})?\b"),
            ("date", rf"\b(hoy|manana|{WEEKDAY_RE})\b|\b\d{{1,2}}/\d{{1,2}}(?:/\d{{2,4}})?\b"),
            ("money", r"\$|\b(pesos|dinero|gasto|ingreso|presupuesto|balance)\b"),
            ("change", r"\b(cambia|cambiar|modifica|ajusta|mueve|pon|registra|agrega|anade)\b"),
            ("delete", r"\b(borra|borrar|elimina|quitar|quita|limpia|cancelar|cancela)\b"),
            ("appish", r"\b(abre|abrir|app|aplicacion|programa|ejecuta|inicia|lanza)\b"),
            ("webish", r"\b(busca|buscar|internet|investiga|consulta|web)\b"),
            ("school", r"\b(clase|clases|materia|materias|horario|universidad|uni|escuela)\b"),
            ("routine", r"\b(rutina|salida|salir|despertar|bano|banar|llegue|llegada)\b"),
            ("voice", r"\b(voz|microfono|escucha|hablar)\b"),
        )
        return [tag for tag, pattern in checks if re.search(pattern, low)]

    def _record_nlu_miss(
        self,
        low: str,
        now: datetime,
        handled_by: str,
        inferred_intent: str = "",
    ) -> None:
        if self.config.get("nlu_telemetry_enabled", True) is False:
            return
        clean = normalize_text(low)
        if not clean:
            return
        salt = str(self.state.setdefault("nlu_telemetry_salt", uuid.uuid4().hex))
        digest = hashlib.sha256(f"{salt}\n{clean}".encode("utf-8")).hexdigest()[:16]
        entry = {
            "timestamp": now.isoformat(timespec="seconds"),
            "handled_by": handled_by,
            "inferred_intent": inferred_intent,
            "text_hash": digest,
            "char_count": len(clean),
            "token_count": len(clean.split()),
            "signals": self._nlu_signal_tags(clean),
        }
        telemetry = self.state.setdefault("nlu_telemetry", [])
        if not isinstance(telemetry, list):
            telemetry = []
        telemetry.append(entry)
        self.state["nlu_telemetry"] = telemetry[-120:]
        daily = self.state.setdefault("daily", {}).setdefault(iso_day(now.date()), {})
        daily["nlu_miss_count"] = int(daily.get("nlu_miss_count", 0) or 0) + 1
        daily["last_nlu_miss"] = {
            "handled_by": handled_by,
            "inferred_intent": inferred_intent,
            "text_hash": digest,
            "signals": list(entry["signals"]),
            "timestamp": entry["timestamp"],
        }
        self._save_state()

    def _nlu_command(self, low: str, original: str, now: datetime, daily: dict[str, Any]) -> Optional[str]:
        nlu = getattr(self, "nlu", None)
        if nlu is None:
            return None
        result = nlu.classify(original)
        if result is None:
            return None
        response = self._dispatch_nlu_intent(result, low, original, now, daily)
        if response is None:
            return None
        daily["last_nlu_intent"] = {
            "intent": result.intent,
            "confidence": result.confidence,
            "reason": result.reason,
            "slots": dict(result.slots),
            "text": low[:120],
            "timestamp": now.isoformat(timespec="seconds"),
        }
        self._save_state()
        return response

    def _dispatch_nlu_intent(
        self,
        result: IntentResult,
        low: str,
        original: str,
        now: datetime,
        daily: dict[str, Any],
    ) -> Optional[str]:
        intent = result.intent
        if intent == "help":
            return self._emit(self.capabilities_summary())
        if intent == "history":
            recent = self._get_recent_history(10)
            if not recent:
                return self._emit("No tengo historial de conversaciones guardado aun.")
            lines = [f"{'Kaiser' if m.get('role') == 'user' else 'Viernes'}: {m.get('text', '')[:80]}" for m in recent]
            return self._emit("Ultimas conversaciones: " + " | ".join(lines))
        if intent == "today_status":
            return self._emit(self._build_today_status(now))
        if intent == "next_commitment":
            return self._emit(self._next_commitment_summary(now))
        if intent == "smart_daily_brief":
            target_day = now.date() + timedelta(days=1) if "manana" in low else now.date()
            return self._emit(self._compose_smart_daily_brief(now, target_day=target_day))
        if intent == "morning_brief":
            return self._emit(self._compose_morning_brief(now))
        if intent == "agenda_full":
            return self._emit(self.full_agenda_summary())
        if intent == "cleanup_past_events":
            return self._confirm_cleanup_past_events(now)
        if intent == "weather":
            return self._emit(self._weather_summary())
        if intent == "news":
            return self._emit(self._news_summary(max_items=5))
        if intent == "budget_summary":
            return self._budget_command("presupuesto", "presupuesto")
        if intent == "habits_stats":
            return self._emit(get_user_stats(7))
        if intent == "habits_recommendations":
            return self._emit(self._habit_recommendation_message())
        if intent == "habits_update":
            return self._update_adaptive_model(now)
        if intent == "alias_suggestions":
            return self._emit(get_alias_suggestions(14))
        if intent == "proactive_suggestions":
            return self._proactive_suggestions_command(now, daily)
        if intent == "proactive_mode":
            mode = result.slots.get("mode", "") or self._proactive_mode_from_text(low)
            if mode:
                return self._set_proactivity_mode(mode)
            return self._emit("Puede decir: modo proactivo conservador, normal, activo o apagado.")
        if intent in {
            "memory_remember",
            "memory_search",
            "memory_query",
            "memory_forget",
            "memory_update",
            "memory_preferences_query",
            "memory_preference_set",
            "memory_preference_forget",
            "personal_rule_create",
            "personal_rule_list",
            "personal_rule_forget",
        }:
            return self._memory_command(low, original, now)
        if intent in {"activity_week", "activity_calendar", "activity_next", "activity_reorganize", "weekly_goals", "day_progress", "day_close", "prepare_tomorrow"}:
            return self._activity_calendar_command(low, now)
        if intent in {"pending_tasks_list", "pending_tasks_today"}:
            return self._pending_tasks_command(low, now)
        if intent in {"action_history", "action_undo"}:
            return self._action_history_command(low, now)
        if intent == "proactive_feedback":
            return self._proactive_feedback_command(low, now, daily)
        if intent == "proactive_status":
            return self._proactive_feedback_command("estado proactivo", now, daily)
        if intent == "proactive_explain":
            return self._proactive_explanation_command(now, daily)
        if intent == "intelligent_status":
            return self._intelligent_status_command(now, daily)
        if intent == "decision_explain":
            return self._explain_last_decision()
        if intent == "command_dry_run":
            return self._dry_run_command(original, now)
        if intent == "command_audit":
            return self._audit_commands(now)
        if intent in {"simulation_request", "research_table", "chart_request", "analysis_report"}:
            return self._analysis_command(low, original, now, intent=intent)
        if intent in {"remote_control_status", "remote_control_test", "remote_control_activate"}:
            return self._remote_control_command(low, original, now)
        if intent == "game_command":
            return self._game_command(low, original, now)
        if intent == "action_plan":
            return self._plan_unprogrammed_action(low, original, now, daily)
        if intent == "clarify_action":
            return self._clarify_ambiguous_action(low, original, now)
        if intent == "classes_today":
            return self._emit(self._classes_summary_for_day(now.date()))
        if intent == "classes_overview":
            return self._emit(self._classes_overview())
        if intent == "classes_cancelled_today":
            self._set_day_override(now.date(), "classes_cancelled", True)
            return self._emit("Entendido. Hoy quedan marcadas las clases como canceladas.")
        if intent == "free_day_today":
            self._set_day_override(now.date(), "free_day", True)
            return self._emit("Entendido. Hoy queda marcado como dia libre.")
        if intent == "classes_change":
            return self._classes_command(low, original, now)
        if intent == "mark_arrival":
            return self._mark_arrival(now)
        if intent == "mark_left_home":
            return self._mark_left_home(now)
        if intent == "mark_bath_done":
            return self._mark_bath_done(now)
        if intent == "routine_timeline":
            return self._emit(self.get_routine_timeline())
        if intent in {"routine_slot_change", "routine_slot_query"}:
            return self._routine_command(low, original, now)
        if intent in {"leave_time_query", "leave_time_change"}:
            return self._routine_command(low, original, now)
        if intent == "voice_status":
            return self._voice_command("estado de voz")
        if intent in {"telegram_activate", "telegram_test", "telegram_notify"}:
            return self._telegram_command(low, original, now)
        if intent == "wake_schedule_change":
            return self._wake_schedule_change_command(low, original, now)
        if intent == "wake_schedule_query":
            return self._emit(self._wake_schedule_summary(now, target_day=self._parse_relative_date(low, now)))
        if intent in {"wake_energy_diagnostic", "wake_test_schedule", "wake_repair"}:
            return self._wake_command(low, original)
        if intent == "wake_status":
            return self._wake_command("diagnostico de despertar", original)
        if intent == "open_app":
            app_name = result.slots.get("app", "").strip()
            if app_name:
                _ok, message = open_application(app_name)
                return self._emit(message)
            return self._app_command(low, original)
        if intent == "math":
            expression = result.slots.get("expression", "").strip()
            if expression and self._looks_like_math(expression):
                return self._emit(calculate(self._normalize_math_expression(expression)))
            return self._math_command(low, original)
        if intent == "research":
            query = result.slots.get("query", "").strip()
            if query:
                return self._research_and_learn(query, now=now)
            return self._web_command(low, original) or self._research_and_learn(low, now=now)
        return None

    def _handle_pending_dialog(self, text: str, now: datetime) -> Optional[str]:
        if not self.pending_dialog:
            return None
        low = normalize_text(text)
        if low in {"cancelar", "olvida", "salir"}:
            self._finish_dialog()
            return self._emit("Entendido. Cancelo esa accion.")
        kind = str(self.pending_dialog.get("kind", ""))
        data = self.pending_dialog.setdefault("data", {})
        if kind == "confirm_destructive":
            if low in {"confirmar", "confirmo", "si", "adelante", "hazlo", "aceptar", "acepto"}:
                action = str(data.get("action", ""))
                self._finish_dialog()
                if action == "cleanup_past_events":
                    return self._handle_cleanup_past(now)
                return self._emit("No reconozco esa accion pendiente. No hice cambios.")
            return self._emit("Necesito confirmacion explicita. Diga 'confirmar' para continuar o 'cancelar' para no hacer cambios.")
        if kind == "confirm_action_plan":
            if low in {"confirmar", "confirmo", "si", "adelante", "hazlo", "aceptar", "acepto"}:
                plan = ActionPlan.from_dict(dict(data.get("plan", {})))
                self._finish_dialog()
                return self._execute_action_plan(plan, now, confirmed=True)
            return self._emit("Necesito confirmacion explicita. Diga 'confirmar' para aplicar el plan o 'cancelar' para no cambiar nada.")
        if kind == "clarify_action":
            return self._resolve_clarified_action(data, low, now)
        if kind == "agenda":
            if "title" not in data:
                data["title"] = text.strip()
                return self._emit("Que dia sera? Puede decir hoy, manana o un dia de la semana.")
            if "date" not in data:
                data["date"] = iso_day(self._parse_relative_date(text, now))
                return self._emit("A que hora?")
            if "time" not in data:
                hhmm = self._parse_time(text)
                if not hhmm:
                    return self._emit("No entendi la hora. Diga por ejemplo: a las 12 o 14:30.")
                self._add_agenda_item(data["title"], date.fromisoformat(data["date"]), hhmm)
                self._finish_dialog()
                return self._emit(f"Quedo agendado: {data['title']} el {data['date']} a las {hhmm}.")
        if kind == "delete_agenda":
            matches = self._find_agenda_matches(text)
            if not matches:
                return self._emit("No encontre un evento que coincida. Digame el nombre tal como aparece en agenda.")
            item = matches[0]
            self._delete_agenda_item(str(item.get("id", "")))
            self._finish_dialog()
            return self._emit(f"Elimine de la agenda: {item.get('title', 'Evento')}.")
        if kind == "edit_agenda":
            if "item_id" not in data:
                matches = self._find_agenda_matches(text)
                if not matches:
                    return self._emit("No encontre ese evento. Digame el nombre tal como aparece en agenda.")
                data["item_id"] = str(matches[0].get("id", ""))
                return self._emit("Que desea cambiar? Puede decir nuevo nombre, nuevo dia u hora.")
            item = next((x for x in self.agenda.get("items", []) if str(x.get("id")) == str(data["item_id"])), None)
            if item is None:
                self._finish_dialog()
                return self._emit("Ese evento ya no existe en la agenda.")
            hhmm = self._parse_time(text)
            has_date = any(marker in low for marker in ("hoy", "manana", "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo", "/", " de "))
            target_day = self._parse_relative_date(text, now) if has_date else None
            title = ""
            if low.startswith(("nombre ", "titulo ", "renombrar ", "renombra ", "se llama ")):
                title = re.sub(r"^(nombre|titulo|renombrar|renombra|se llama)\s+", "", low).strip()
            if not title and hhmm is None and target_day is None:
                title = text.strip()
            if not title and hhmm is None and target_day is None:
                return self._emit("No entendi el cambio. Diga por ejemplo: a las 18:00, manana a las 9, o nombre reunion.")
            self._update_agenda_item(item, title=title or None, day=target_day, hhmm=hhmm)
            self._finish_dialog()
            return self._emit(
                f"Evento actualizado: {item.get('title', 'Evento')} el {item.get('date', '--')} a las {item.get('time', '--:--')}."
            )
        if kind == "relative_reminder":
            saved_topic = str(data.get("topic", "") or "").strip()
            reminder_text = f"recuerdame {saved_topic} {text}".strip() if saved_topic else f"recuerdame {text}"
            topic, target, recurring = self._parse_relative_reminder(reminder_text, now)
            if target is None:
                return self._emit("Diga el tiempo asi: en 20 minutos, manana a las 8, el lunes 13 de abril a las 7, o cada viernes a las 6.")
            self._add_timed_reminder(topic or "Recordatorio", target, recurring=recurring)
            self._finish_dialog()
            if recurring == "daily":
                return self._emit(f"Listo. Le recordare {topic} todos los dias a las {target.strftime('%H:%M')}.")
            return self._emit(f"Listo. Le recordare {topic} a las {target.strftime('%H:%M')}.")
        if kind == "pause_agenda":
            matches = self._find_agenda_matches(text)
            if not matches:
                return self._emit("No encontre un recordatorio recurrente con ese nombre.")
            self._set_agenda_paused(str(matches[0].get("id", "")), True)
            self._finish_dialog()
            return self._emit(f"Pausado: {matches[0].get('title', 'Recordatorio')}.")
        if kind == "resume_agenda":
            matches = self._find_agenda_matches(text)
            if not matches:
                return self._emit("No encontre un recordatorio para reactivar.")
            self._set_agenda_paused(str(matches[0].get("id", "")), False)
            self._finish_dialog()
            return self._emit(f"Reactivado: {matches[0].get('title', 'Recordatorio')}.")
        if kind == "classes":
            classes = [x.strip() for x in re.split(r"[,;]", text) if x.strip()]
            target_date = data.get("date")
            target_weekday = data.get("weekday")
            self._finish_dialog()
            if target_date:
                return self._set_date_classes(date.fromisoformat(target_date), classes)
            if target_weekday:
                return self._set_weekday_classes(str(target_weekday), classes)
        return None

    def _agent_planner(self) -> AgentPlanner:
        planner = getattr(self, "agent_planner", None)
        if not isinstance(planner, AgentPlanner):
            planner = AgentPlanner()
            self.agent_planner = planner
        return planner

    def _agent_memory_manager(self) -> PersistentMemoryManager:
        manager = getattr(self, "agent_memory", None)
        if not isinstance(manager, PersistentMemoryManager):
            manager = PersistentMemoryManager()
            self.agent_memory = manager
        return manager

    def _permission_manager(self) -> PermissionManager:
        manager = getattr(self, "permission_manager", None)
        if not isinstance(manager, PermissionManager):
            manager = PermissionManager.from_config(self.config)
            self.permission_manager = manager
        return manager

    def _tool_router(self) -> ToolRouter:
        router = getattr(self, "tool_router", None)
        if not isinstance(router, ToolRouter):
            router = ToolRouter(self._permission_manager())
            self.tool_router = router
        return router

    def _plugin_manager(self) -> PluginManager:
        manager = getattr(self, "plugin_manager", None)
        if not isinstance(manager, PluginManager):
            plugin_cfg = self.config.get("plugins", {})
            manager = PluginManager(REPO_ROOT / "viernes_app" / "plugins", plugin_cfg if isinstance(plugin_cfg, dict) else {})
            self.plugin_manager = manager
        return manager

    def _security_monitor(self) -> SecurityMonitor:
        monitor = getattr(self, "security_monitor", None)
        if not isinstance(monitor, SecurityMonitor):
            monitor = SecurityMonitor()
            monitor.establish_baseline()
            self.security_monitor = monitor
        return monitor

    def _personal_activity_service(self) -> PersonalActivityService:
        service = getattr(self, "personal_activity", None)
        if not isinstance(service, PersonalActivityService):
            cfg = self.config.get("personal_activity", {})
            service = PersonalActivityService(cfg if isinstance(cfg, dict) else {})
            self.personal_activity = service
        return service

    def _shutdown_personal_activity(self) -> None:
        service = getattr(self, "personal_activity", None)
        if isinstance(service, PersonalActivityService):
            try:
                service.stop()
            except Exception:
                pass

    def _user_permission_level(self) -> int:
        security_cfg = self.config.get("security", {})
        if not isinstance(security_cfg, dict):
            return 1
        try:
            return int(security_cfg.get("user_level", security_cfg.get("level", 1)) or 1)
        except (TypeError, ValueError):
            return 1

    def _agent_system_command(self, low: str, original: str, now: datetime) -> Optional[str]:
        if low in {"estado agentes", "estado del sistema de agentes", "agentes"}:
            memory = self._agent_memory_manager().snapshot()
            permissions = self._permission_manager().summary()
            plugins = self._plugin_manager().summary()
            tools = self._tool_router().list_tools()
            return self._emit(
                "Sistema de agentes: "
                f"memoria short={memory['short_term_count']} long={memory['long_term_count']}, "
                f"nivel permisos={permissions['current_level']}, "
                f"herramientas={len(tools)}, plugins={plugins['loaded']}."
            )

        if low in {"permisos", "estado permisos", "seguridad permisos"}:
            summary = self._permission_manager().summary()
            return self._emit(
                "Permisos: nivel actual "
                f"{summary['current_level']}. Raices autorizadas: {', '.join(summary['allowed_roots'][:4])}. "
                f"Scripts autorizados: {', '.join(summary.get('allowed_scripts', [])[:3])}."
            )

        if low in {"herramientas registradas", "estado herramientas agente", "herramientas agente"}:
            tools = self._tool_router().list_tools()
            preview = ", ".join(f"{tool['name']}:{tool['action']}" for tool in tools[:12])
            return self._emit(f"Herramientas registradas ({len(tools)}): {preview}.")

        if low in {"plugins", "estado plugins", "plugins activos"}:
            summary = self._plugin_manager().summary()
            names = [item.get("name", "") for item in summary.get("plugins", []) if not item.get("error")]
            errors = [item.get("name", "") for item in summary.get("errors", [])]
            detail = f"Plugins activos: {', '.join(names) if names else 'ninguno'}."
            if errors:
                detail += f" Con errores: {', '.join(errors)}."
            return self._emit(detail)

        if low in {"monitor seguridad", "estado monitor seguridad", "revisar seguridad"}:
            summary = self._security_monitor().summary()
            alerts = summary.get("alerts", [])
            if not alerts:
                return self._emit("Diagnostico pasivo basico: sin alertas en archivos vigilados y comprobaciones configuradas. No inspecciona todo el sistema ni bloquea acciones.")
            preview = " | ".join(f"{item.get('severity')}: {item.get('message')}" for item in alerts[:4])
            return self._emit(f"Diagnostico pasivo basico: {len(alerts)} alerta(s). {preview}")

        if low in {"estado monitoreo personal", "monitoreo personal", "estado actividad personal"}:
            return self._emit(self._personal_activity_service().status_message())

        if low in {"activar monitoreo personal", "activar cuidado personal", "activar actividad personal"}:
            cfg = self.config.setdefault("personal_activity", {})
            if not isinstance(cfg, dict):
                cfg = {}
                self.config["personal_activity"] = cfg
            cfg.setdefault("privacy_mode", "app_category")
            cfg.setdefault("poll_interval_seconds", 60)
            cfg.setdefault("retention", {"raw_days": 14, "session_days": 60, "aggregate_days": 365})
            cfg["enabled"] = True
            self.save_config()
            self.personal_activity = PersonalActivityService(cfg)
            started = self.personal_activity.start()
            return self._emit(
                "Monitoreo personal activado. "
                "Guardare proceso/categoria/huellas de ventana, no titulos completos ni URLs. "
                + ("Servicio en segundo plano iniciado." if started else "Quedo configurado para iniciar en el proximo arranque.")
            )

        if low in {"desactivar monitoreo personal", "desactivar cuidado personal", "desactivar actividad personal"}:
            service = self._personal_activity_service()
            service.stop()
            cfg = self.config.setdefault("personal_activity", {})
            if isinstance(cfg, dict):
                cfg["enabled"] = False
            self.save_config()
            self.personal_activity = PersonalActivityService(cfg if isinstance(cfg, dict) else {})
            return self._emit("Monitoreo personal desactivado. Los datos existentes se conservan hasta que pida borrarlos o depurarlos.")

        if low in {"resumen actividad personal", "resumen de actividad", "cuidado personal", "reporte actividad personal"}:
            return self._emit(self._personal_activity_service().summary_message(days=7))

        if low in {"depurar actividad personal", "compactar actividad personal", "mantenimiento actividad personal"}:
            result = self._personal_activity_service().run_maintenance()
            return self._emit(
                "Mantenimiento de actividad personal: "
                f"sesiones agregadas={result.get('aggregated_sessions', 0)}, "
                f"eventos borrados={result.get('deleted_events', 0)}, "
                f"sesiones borradas={result.get('deleted_sessions', 0)}, "
                f"agregados borrados={result.get('deleted_aggregates', 0)}."
            )

        if low in {"muestrear actividad personal", "probar monitoreo personal", "probar actividad personal"}:
            result = self._personal_activity_service().poll_once(now)
            if result.get("ok"):
                return self._emit(f"Muestreo correcto: {result.get('app_key')} ({result.get('category')}).")
            return self._emit(f"No pude muestrear actividad ahora: {result.get('reason', 'sin detalle')}.")

        if low in {"borrar actividad personal", "eliminar actividad personal", "limpiar actividad personal"}:
            return self._emit("Esta accion borra eventos, sesiones y agregados de actividad personal. Para confirmar diga: borrar actividad personal confirmado.")

        if low in {"borrar actividad personal confirmado", "eliminar actividad personal confirmado", "confirmado borrar actividad personal"}:
            removed = self._personal_activity_service().purge_all()
            return self._emit(
                "Actividad personal borrada: "
                f"eventos={removed.get('events', 0)}, sesiones={removed.get('sessions', 0)}, agregados={removed.get('aggregates', 0)}."
            )

        if low in {"memoria agente", "memoria persistente", "estado memoria"}:
            snapshot = self._agent_memory_manager().snapshot()
            return self._emit(
                "Memoria persistente: "
                f"{snapshot['short_term_count']} corto plazo, {snapshot['long_term_count']} largo plazo, "
                f"{snapshot['conversation_count']} conversaciones, "
                f"preferencias={len(snapshot['preferences'])}, proyectos={len(snapshot['projects'])}."
            )

        if low.startswith(("recuerda permanente ", "guardar memoria permanente ", "memoria guarda ")):
            text = re.sub(r"^(recuerda permanente|guardar memoria permanente|memoria guarda)\s+", "", original, flags=re.IGNORECASE).strip()
            if not text:
                return self._emit("Diga que debo guardar en memoria persistente.")
            self._agent_memory_manager().remember_long_term(text, kind="user_fact", metadata={"source": "command"})
            return self._emit("Memoria persistente guardada.")

        if low.startswith(("preferencia agente ", "guardar preferencia agente ")):
            body = re.sub(r"^(preferencia agente|guardar preferencia agente)\s+", "", original, flags=re.IGNORECASE).strip()
            key, sep, value = body.partition(":")
            if not sep:
                key, sep, value = body.partition("=")
            if not key.strip() or not value.strip():
                return self._emit("Use: preferencia agente clave: valor.")
            self._agent_memory_manager().set_preference(key, value)
            return self._emit(f"Preferencia persistente guardada: {key.strip()}.")

        if low.startswith(("proyecto activo ", "guardar proyecto activo ")):
            name = re.sub(r"^(proyecto activo|guardar proyecto activo)\s+", "", original, flags=re.IGNORECASE).strip()
            if not name:
                return self._emit("Diga el nombre del proyecto activo.")
            self._agent_memory_manager().set_project(name, {"source": "command", "updated_by": "Viernes"})
            return self._emit(f"Proyecto activo registrado: {name}.")

        if low.startswith(("plan agente ", "planifica ", "crear plan agente ", "planificar ")):
            objective = re.sub(r"^(plan agente|planifica|crear plan agente|planificar)\s+", "", original, flags=re.IGNORECASE).strip()
            if not objective:
                return self._emit("Diga el objetivo a planificar.")
            plan = self._agent_planner().create_plan(objective, now=now)
            self.state["last_agent_plan"] = plan.to_dict()
            self._save_state()
            return self._emit(self._agent_planner().format_plan(plan))

        if low in {
            "ejecutar ultimo plan agente",
            "ejecuta ultimo plan agente",
            "ejecutar plan agente",
            "ejecutar ultimo plan agente confirmado",
            "ejecutar plan agente confirmado",
            "aprobar plan agente",
        }:
            raw_plan = self.state.get("last_agent_plan")
            if not isinstance(raw_plan, dict):
                return self._emit("No tengo un plan agente reciente para ejecutar.")
            plan = AgentPlan.from_dict(raw_plan)
            confirmed = low in {
                "ejecutar ultimo plan agente confirmado",
                "ejecutar plan agente confirmado",
                "aprobar plan agente",
            }
            report = self._agent_planner().execute_sequential(
                plan,
                lambda step: self._tool_router().execute_plan_step(
                    step,
                    self,
                    user_level=self._user_permission_level(),
                    confirmed=confirmed,
                    dry_run=not confirmed,
                ),
                approvals={"all": True} if confirmed else {},
                dry_run=not confirmed,
            )
            self.state["last_agent_execution"] = report.to_dict()
            self._save_state()
            return self._emit(
                f"Ejecucion de plan agente: {report.status}. "
                f"Completados={report.completed_steps}, bloqueados={report.blocked_steps}. "
                + " | ".join(report.messages[:5])
            )

        if low.startswith(("herramienta ", "usar herramienta ", "router herramienta ")):
            body = re.sub(r"^(herramienta|usar herramienta|router herramienta)\s+", "", original, flags=re.IGNORECASE).strip()
            if not body:
                return self._emit("Diga que herramienta o accion quiere enrutar.")
            request = self._tool_router().route(body, user_level=self._user_permission_level())
            result = self._tool_router().execute(request, self)
            return self._emit(result.message)

        if low.startswith(("mejora controlada ", "auto mejora ", "automejora ")):
            objective = re.sub(r"^(mejora controlada|auto mejora|automejora)\s+", "", original, flags=re.IGNORECASE).strip()
            if not objective:
                return self._emit("Diga que mejora quiere analizar.")
            analyzer = getattr(self, "improvement_analyzer", ImprovementAnalyzer())
            coder = getattr(self, "improvement_coder", ImprovementCoder())
            tester = getattr(self, "improvement_tester", ImprovementTester())
            reviewer = getattr(self, "improvement_reviewer", ImprovementReviewer())
            analysis = analyzer.analyze(objective)
            proposal = coder.draft_proposal(analysis)
            tests = tester.run_unit_tests(timeout=120)
            review = reviewer.review(proposal, tests)
            proposal_path = coder.save_proposal(proposal, analysis=analysis, tests=tests, review=review)
            self.state["last_self_improvement_proposal"] = {
                "analysis": analysis.to_dict(),
                "proposal": proposal.to_dict(),
                "tests": tests.to_dict(),
                "review": review.to_dict(),
                "path": str(proposal_path),
            }
            self._save_state()
            return self._emit(
                "Auto-mejora controlada: genere una propuesta, ejecute pruebas y no modifique archivos. "
                f"Archivos a revisar: {', '.join(proposal.files_to_review[:5]) or 'ninguno'}. "
                f"Tests={'pasaron' if tests.passed else 'fallaron'}. "
                f"Propuesta: {proposal_path}."
            )

        if low in {"estado mejora controlada", "ultima mejora controlada", "estado automejora"}:
            last = self.state.get("last_self_improvement_proposal")
            if not isinstance(last, dict):
                return self._emit("No hay propuestas de auto-mejora registradas.")
            proposal = last.get("proposal", {}) if isinstance(last.get("proposal", {}), dict) else {}
            tests = last.get("tests", {}) if isinstance(last.get("tests", {}), dict) else {}
            review = last.get("review", {}) if isinstance(last.get("review", {}), dict) else {}
            return self._emit(
                "Ultima auto-mejora: "
                f"{proposal.get('id', 'sin-id')} para {proposal.get('objective', 'sin objetivo')}. "
                f"Tests={'pasaron' if tests.get('passed') else 'no pasaron'}. "
                f"Revision: {review.get('summary', 'sin revision')}."
            )

        if low in {"estado voz continua", "voz continua"}:
            controller = getattr(self, "continuous_conversation", None)
            if controller is None:
                return self._emit("Conversacion continua no inicializada.")
            status = controller.status()
            return self._emit(
                f"Voz continua: {'activa' if status.running else 'apagada'}, "
                f"wake word '{status.wake_word}', microfono {'disponible' if status.speech_available else 'no disponible'}."
            )

        if low in {"estado voz", "perfiles de voz", "perfil de voz"}:
            profiles = getattr(self, "voice_profiles", VoiceProfileManager())
            names = profiles.names()
            active = str(self.config.get("voice_profile", "default") or "default")
            interrupted = self.interruption_detector.state().interrupted if hasattr(self, "interruption_detector") else False
            return self._emit(
                f"Voz: perfil activo {active}, perfiles={', '.join(names)}, "
                f"interrupcion={'activa' if interrupted else 'inactiva'}."
            )

        if low.startswith(("usar perfil de voz ", "perfil de voz ")):
            name = re.sub(r"^(usar perfil de voz|perfil de voz)\s+", "", original, flags=re.IGNORECASE).strip()
            if not name:
                return self._emit("Diga el nombre del perfil de voz.")
            profile = self.voice_profiles.get(name)
            self.config["voice_profile"] = profile.name
            self.config["wake_word"] = profile.wake_word
            self.save_config()
            self.voice.apply_profile(profile)
            self.wake_word_detector = WakeWordDetector(profile.wake_word)
            controller = getattr(self, "continuous_conversation", None)
            if controller is not None:
                controller.configure_wake_word(profile.wake_word)
            return self._emit(f"Perfil de voz activo: {profile.name}.")

        if low in {"interrumpir voz", "cortar voz", "silenciar voz"}:
            self.interruption_detector.interrupt("command")
            self.voice.stop()
            return self._emit("Voz interrumpida.")

        if low in {"activar conversacion continua", "activar voz continua"}:
            controller = getattr(self, "continuous_conversation", None)
            if controller is None:
                return self._emit("Conversacion continua no inicializada.")
            started = controller.start()
            return self._emit("Conversacion continua activada." if started else "No pude activar conversacion continua; revise microfono/backend.")

        if low in {"desactivar conversacion continua", "desactivar voz continua"}:
            controller = getattr(self, "continuous_conversation", None)
            if controller is not None:
                controller.stop()
            return self._emit("Conversacion continua desactivada.")

        if low.startswith(("wake word ", "palabra de activacion ")):
            word = re.sub(r"^(wake word|palabra de activacion)\s+", "", original, flags=re.IGNORECASE).strip()
            if not word:
                return self._emit("Diga la palabra de activacion.")
            self.config["wake_word"] = word
            self.save_config()
            self.wake_word_detector = WakeWordDetector(word)
            controller = getattr(self, "continuous_conversation", None)
            if controller is not None:
                controller.configure_wake_word(word)
            return self._emit(f"Wake word configurada: {word}.")

        if low in {"estado interfaz", "interfaz", "ui"}:
            ui_cfg = self.config.get("ui", {}) if isinstance(self.config.get("ui", {}), dict) else {}
            mode = str(ui_cfg.get("mode", "classic") or "classic")
            return self._emit(f"Interfaz configurada: {mode}. La UI moderna es opt-in.")

        if low in {"activar interfaz moderna", "usar interfaz moderna", "ui moderna"}:
            result = self.apply_gui_config_patch({"ui": {"mode": "modern"}})
            if not result.valid:
                return self._emit("No pude activar interfaz moderna: " + " ".join(result.errors))
            return self._emit("Interfaz moderna activada. Se aplicara al abrir la GUI de nuevo.")

        if low in {"activar interfaz clasica", "usar interfaz clasica", "ui clasica"}:
            result = self.apply_gui_config_patch({"ui": {"mode": "classic"}})
            if not result.valid:
                return self._emit("No pude activar interfaz clasica: " + " ".join(result.errors))
            return self._emit("Interfaz clasica activada. Se aplicara al abrir la GUI de nuevo.")

        return None

    def process_command(self, text: str, now: Optional[datetime] = None) -> str:
        # Permitir ejecución de comandos dinámicos
        if text.startswith("/cmd "):
            parts = text[5:].split()
            cmd = parts[0]
            args = parts[1:]
            try:
                result = self.command_registry.execute(cmd, *args)
                return self._emit(f"Comando '{cmd}' ejecutado: {result}")
            except Exception as e:
                return self._emit(f"Error al ejecutar comando '{cmd}': {e}")
        # Notificar actividad al monitor si está activo
        if hasattr(self, '_activity_monitor') and self._activity_monitor:
            self._activity_monitor.notify_activity()
        with self._lock:
            when = now or datetime.now()
            self.reload()
            daily = self._ensure_daily_state(when)
            text = str(text or "").strip()
            low = normalize_text(text)
            if not low:
                return self._emit("No alcance a escuchar una instruccion clara. Intente de nuevo con la frase completa.")
            text, low, wake_only = self._strip_wake_word_prefix(text, low)
            if wake_only:
                return self._emit("Te escucho. Diga la instruccion completa despues de la palabra de activacion.")
            if not low:
                return self._emit("Te escucho. Diga la instruccion completa.")
            self._log_user(text)
            agent_response = self._agent_system_command(low, text, when)
            if agent_response is not None:
                return agent_response
            if low in {"detente", "para", "stop", "callate", "viernes detente", "viernes para", "viernes stop"}:
                self._finish_dialog()
                return self.force_stop(when)
            if low in {"reanuda", "reanudar", "continua", "continuar", "reanuda recordatorios", "reanudar recordatorios", "activar recordatorios"}:
                return self.resume_scheduler(when)
            if low in {"explica por que entendiste eso", "por que entendiste eso", "que entendiste del comando"}:
                return self._explain_last_decision()
            execution_response = self._execution_status_command(low)
            if execution_response is not None:
                return execution_response
            game_response = self._game_command(low, text, when)
            if game_response is not None:
                return game_response
            if low.startswith(("probar comando ", "simula comando ", "prueba sin ejecutar ")):
                return self._dry_run_command(text, when)
            if low in {"audita comandos", "auditoria de comandos", "revisa entendimiento de comandos", "audita comandos criticos", "audita comandos críticos"}:
                return self._audit_commands(when)
            self._store_last_decision(self._decide_command(text, when), text, when)
            if self._should_bypass_pending_dialog(low):
                self._finish_dialog()
            pending_result = self._handle_pending_dialog(text, when)
            if pending_result is not None:
                return pending_result
            if low in {"limpiar agenda", "limpia agenda", "borrar eventos pasados", "eliminar eventos pasados", "limpiar eventos pasados"}:
                return self._confirm_cleanup_past_events(when)
            if low in {"estado inteligente", "dashboard inteligente", "modo inteligente"}:
                return self._intelligent_status_command(when, daily)
            memory_response = self._memory_command(low, text, when)
            if memory_response is not None:
                return memory_response
            calendar_response = self._activity_calendar_command(low, when)
            if calendar_response is not None:
                return calendar_response
            pending_tasks_response = self._pending_tasks_command(low, when)
            if pending_tasks_response is not None:
                return pending_tasks_response
            action_history_response = self._action_history_command(low, when)
            if action_history_response is not None:
                return action_history_response
            feedback_response = self._proactive_feedback_command(low, when, daily)
            if feedback_response is not None:
                return feedback_response
            proactive_response = self._proactive_command(low, when, daily)
            if proactive_response is not None:
                return proactive_response
            remote_response = self._remote_control_command(low, text, when)
            if remote_response is not None:
                return remote_response
            game_response = self._game_command(low, text, when)
            if game_response is not None:
                return game_response
            analysis_response = self._analysis_command(low, text, when)
            if analysis_response is not None:
                return analysis_response
            # Saludos y conversacion basica
            if self._is_greeting_command(low):
                return self._emit(self._greeting_response(when))
            if low in {"gracias", "muchas gracias", "gracias viernes"}:
                return self._emit("De nada, Senor. Para eso estoy.")
            if low in {"adios", "hasta luego", "nos vemos", "chao", "bye"}:
                return self._emit("Hasta luego, Senor. Aqui estare cuando me necesite.")
            if low in {"mis estadisticas", "estadisticas", "que tanto me usas", "mis habitos", "habitos"}:
                return self._emit(get_user_stats(7))
            if low in {
                "mis recomendaciones",
                "recomendaciones",
                "recomendaciones de habitos",
                "corrige mis habitos",
                "ayudame con mis habitos",
                "que habitos debo mejorar",
            }:
                return self._emit(self._habit_recommendation_message())
            if low in {
                "alias sugeridos",
                "atajos sugeridos",
                "sugerencias de alias",
                "sugerencias de atajos",
                "comandos frecuentes",
                "frases frecuentes",
            }:
                return self._emit(get_alias_suggestions(14))
            if low in {
                "actualiza red neuronal",
                "entrena red neuronal",
                "mejora tu cerebro",
                "actualiza tu cerebro",
                "autoactualizate",
                "aprende de mis habitos",
            }:
                return self._update_adaptive_model(when)
            if low in {"historial", "que hemos hablado", "conversaciones anteriores", "ultimo historial"}:
                recent = self._get_recent_history(10)
                if not recent:
                    return self._emit("No tengo historial de conversaciones guardado aun.")
                lines = [f"{'Kaiser' if m.get('role') == 'user' else 'Viernes'}: {m.get('text', '')[:80]}" for m in recent]
                return self._emit("Ultimas conversaciones: " + " | ".join(lines))
            if low in {"lista", "que puedes hacer", "que puede hacer", "ayuda", "mostrar capacidades", "que sabes hacer"}:
                return self._emit(self.capabilities_summary())
            voice_response = self._voice_command(low)
            if voice_response is not None:
                return voice_response
            wake_change_response = self._wake_schedule_change_command(low, text, when)
            if wake_change_response is not None:
                return wake_change_response
            if self._looks_like_wake_schedule_query(low):
                return self._emit(self._wake_schedule_summary(when, target_day=self._parse_relative_date(low, when)))
            routine_response = self._routine_command(low, text, when)
            if routine_response is not None:
                return routine_response
            day_query_response = self._day_query_command(low, text, when)
            if day_query_response is not None:
                return day_query_response
            if low in {"que tengo hoy", "agenda de hoy", "hoy", "estado del dia", "resumen del dia", "informe del dia"}:
                return self._emit(self._build_today_status(when))
            if low in {"mi agenda", "toda mi agenda", "ver agenda", "agenda completa", "mostrar agenda completa"}:
                return self._emit(self.full_agenda_summary())
            if low in {"clima", "clima de hoy", "como esta el clima", "pronostico", "pronostico de hoy"}:
                return self._emit(self._weather_summary())
            if low in {"briefing", "informe matutino", "resumen matutino", "rutina de la manana"}:
                return self._emit(self._compose_morning_brief(when))
            if low in {"que sigue", "siguiente pendiente", "proximo evento", "que sigue hoy"}:
                return self._emit(self._next_commitment_summary(when))
            budget_response = self._budget_command(low, text)
            if budget_response is not None:
                return budget_response
            agenda_edit_response = self._agenda_edit_command(low, text, when)
            if agenda_edit_response is not None:
                return agenda_edit_response
            agenda_add_response = self._agenda_add_natural_command(low, text, when)
            if agenda_add_response is not None:
                return agenda_add_response
            if low in {"agregar a la agenda", "agrega a la agenda"}:
                self._start_dialog("agenda", {})
                return self._emit("Que desea agregar a la agenda?")
            if low.startswith("agregar a la agenda ") or low.startswith("agrega a la agenda "):
                body = re.sub(r"^agreg(?:ar|a)\s+a\s+la\s+agenda\s+", "", low).strip()
                hhmm = self._parse_time(body)
                target_day = self._parse_relative_date(body, when)
                title = self._strip_date_and_time_phrases(body)
                if hhmm:
                    self._add_agenda_item(title, target_day, hhmm)
                    return self._emit(f"Quedo agendado: {title} el {iso_day(target_day)} a las {hhmm}.")
                self._start_dialog("agenda", {"title": title, "date": iso_day(target_day)})
                return self._emit("Solo me falta la hora.")
            if low in {"borrar evento", "eliminar evento", "borra de la agenda", "elimina de la agenda"}:
                self._start_dialog("delete_agenda", {})
                return self._emit("¿Qué evento desea borrar? Puede decir el nombre o el ID.")
            if low.startswith("borrar evento ") or low.startswith("eliminar evento ") or low.startswith("borra de la agenda ") or low.startswith("elimina de la agenda "):
                query = re.sub(r"^(borrar evento|eliminar evento|borra de la agenda|elimina de la agenda)\s+", "", low).strip()
                # Permitir borrar por ID o nombre
                matches = [x for x in self.agenda.get("items", []) if query in str(x.get("id", "")) or query in str(x.get("title", "")).lower()]
                if not matches:
                    return self._emit("No encontre un evento con ese nombre o ID.")
                self._delete_agenda_item(str(matches[0].get("id", "")))
                return self._emit(f"Elimine de la agenda: {matches[0].get('title', 'Evento')}.")
            if low in {"recuerdame", "recordatorio"}:
                self._start_dialog("relative_reminder", {})
                return self._emit("Que debo recordarle y en cuanto tiempo?")
            if low.startswith("recuerdame "):
                topic, target, recurring = self._parse_relative_reminder(low, when)
                if target is not None:
                    self._add_timed_reminder(topic or "Recordatorio", target, recurring=recurring)
                    return self._emit(f"Listo. Le recordare {topic} a las {target.strftime('%H:%M')}.")
                topic_guess = re.sub(r"^recuerdame\s+", "", low).strip(" ,.-")
                self._start_dialog("relative_reminder", {"topic": topic_guess} if topic_guess else {})
                return self._emit("Que debo recordarle y en cuanto tiempo?")
            if low in {"pausar recordatorio", "desactivar recordatorio"}:
                self._start_dialog("pause_agenda", {})
                return self._emit("Que recordatorio desea pausar?")
            if low.startswith("pausar recordatorio ") or low.startswith("desactivar recordatorio "):
                query = re.sub(r"^(pausar recordatorio|desactivar recordatorio)\s+", "", low).strip()
                matches = self._find_agenda_matches(query)
                if not matches:
                    return self._emit("No encontre un recordatorio con ese nombre.")
                self._set_agenda_paused(str(matches[0].get("id", "")), True)
                return self._emit(f"Pausado: {matches[0].get('title', 'Recordatorio')}.")
            if low in {"reactivar recordatorio", "activar recordatorio"}:
                self._start_dialog("resume_agenda", {})
                return self._emit("Que recordatorio desea reactivar?")
            if low.startswith("reactivar recordatorio ") or low.startswith("activar recordatorio "):
                query = re.sub(r"^(reactivar recordatorio|activar recordatorio)\s+", "", low).strip()
                matches = self._find_agenda_matches(query)
                if not matches:
                    return self._emit("No encontre un recordatorio para reactivar.")
                self._set_agenda_paused(str(matches[0].get("id", "")), False)
                return self._emit(f"Reactivado: {matches[0].get('title', 'Recordatorio')}.")
            if low in {"llegue", "ya llegue", "ya llegue a la casa", "ya llegue al cuarto"}:
                return self._mark_arrival(when)
            if low in {"ya sali", "ya me fui", "voy saliendo", "ya salgo"}:
                return self._mark_left_home(when)
            if low in {"ya me bane", "ya me banie", "ya me banne"}:
                return self._mark_bath_done(when)
            if low in {"dia libre hoy", "hoy tengo dia libre"}:
                self._set_day_override(when.date(), "free_day", True)
                return self._emit("Entendido. Hoy queda marcado como dia libre.")
            if low in {"me cancelaron las clases hoy", "hoy me cancelaron las clases", "hoy ya no hay clases"}:
                self._set_day_override(when.date(), "classes_cancelled", True)
                return self._emit("Entendido. Hoy quedan marcadas las clases como canceladas.")
            classes_response = self._classes_command(low, text, when)
            if classes_response is not None:
                return classes_response
            if low in {"que clases tengo hoy", "clases de hoy"}:
                return self._emit(self._classes_summary_for_day(when.date()))
            if low in {"mis clases", "ver clases", "que clases tengo"}:
                return self._emit(self._classes_overview())
            if low in {"horario de hoy", "mi horario de hoy"}:
                return self._emit(self._classes_summary_for_day(when.date()))
            if low in {"tengo clases", "registrar clases"}:
                self._start_dialog("classes", {"weekday": weekday_key(when.date())})
                return self._emit("Diga las clases separadas por coma.")
            match = re.match(r"^(?:tengo clases|clases del?|clases para)\s+(lunes|martes|miercoles|jueves|viernes)(?::|\s+de)?\s*(.*)$", low)
            if match:
                weekday = weekday_name_to_key(match.group(1))
                rest = match.group(2).strip()
                if not rest:
                    self._start_dialog("classes", {"weekday": weekday})
                    return self._emit(f"Digame las clases del {match.group(1)} separadas por coma.")
                return self._set_weekday_classes(weekday, [x.strip() for x in re.split(r"[,;]", rest) if x.strip()])
            if low.startswith("tengo clases el ") or low.startswith("clases el "):
                target_date = self._parse_relative_date(low, when)
                rest = re.sub(r"^(tengo clases el|clases el)\s+", "", low).strip()
                rest = self._strip_date_and_time_phrases(rest)
                classes = [x.strip() for x in re.split(r"[,;]", rest) if x.strip() and x.strip() != "evento"]
                if not classes:
                    self._start_dialog("classes", {"date": iso_day(target_date)})
                    return self._emit("Digame las clases separadas por coma.")
                return self._set_date_classes(target_date, classes)
            nlu_response = self._nlu_command(low, text, when, daily)
            if nlu_response is not None:
                return nlu_response
            plan_response = self._plan_unprogrammed_action(low, text, when, daily)
            if plan_response is not None:
                return plan_response
            clarification_response = self._clarify_ambiguous_action(low, text, when)
            if clarification_response is not None:
                return clarification_response

            def after_nlu_miss(response: str, handled_by: str, inferred_intent: str = "") -> str:
                self._record_nlu_miss(low, when, handled_by, inferred_intent)
                return response

            if low.startswith("saluda a ") or low.startswith("viernes saluda a "):
                target = re.sub(r"^.*?\bsaluda a\s+", "", text, flags=re.IGNORECASE).strip() or "esa persona"
                return self._emit(f"Hola, {target}. Viernes le manda un saludo de parte de Kaiser.")
            conversation_response = self._conversation_command(low, daily)
            if conversation_response is not None:
                return conversation_response
            math_response = self._math_command(low, text)
            if math_response is not None:
                return math_response
            app_response = self._app_command(low, text)
            if app_response is not None:
                return app_response
            web_response = self._web_command(low, text)
            if web_response is not None:
                return web_response
            wake_response = self._wake_command(low, text)
            if wake_response is not None:
                return wake_response
            jarvis_response = self._jarvis_extended_commands(low, text)
            if jarvis_response is not None:
                return jarvis_response
            if low in {"resumen de hoy", "estado de hoy"}:
                return self._emit(self._build_today_status(when))
            # Comandos nuevos integrados de forma compatible
            if low.startswith("auditar archivo ") and self._auditor is not None:
                target = low.replace("auditar archivo ", "", 1).strip()
                result = self._auditor.analyze_file(target)
                return self._emit(f"Auditoria de {target}: complejidad={result.get('complexity')} issues={len(result.get('bad_practices',[]))}")
            if low.startswith("ollama:") and self._ollama is not None:
                prompt = text.split(":", 1)[1].strip()
                if hasattr(self._ollama, 'chat'):
                    resp = self._ollama.chat("Eres Viernes, asistente personal.", prompt)
                elif hasattr(self._ollama, 'generate'):
                    resp = self._ollama.generate(prompt)
                else:
                    resp = None
                return self._emit(resp or "No obtuve respuesta de Ollama.")
            if low in {"mlp demo", "mlp: demo"}:
                return self._emit(
                    "La demo MLP fue retirada del flujo del asistente: solo entrenaba XOR en memoria y no aprendia de usted. "
                    "Use 'actualiza habitos' para un resumen local verificable."
                )
            brain_decision = self.brain.classify(text)
            if brain_decision is not None:
                if brain_decision.intent == "agenda":
                    return after_nlu_miss(self._emit(self._build_today_status(when)), "brain", "agenda")
                if brain_decision.intent == "morning_brief":
                    return after_nlu_miss(self._emit(self._compose_morning_brief(when)), "brain", "morning_brief")
                if brain_decision.intent == "news":
                    return after_nlu_miss(self._emit(self._news_summary(max_items=3)), "brain", "news")
                if brain_decision.intent == "weather":
                    return after_nlu_miss(self._emit(self._weather_summary()), "brain", "weather")
                if brain_decision.intent == "classes":
                    return after_nlu_miss(self._emit(self._classes_summary_for_day(when.date())), "brain", "classes")
                if brain_decision.intent == "budget":
                    budget_response = self._budget_command("presupuesto", "presupuesto")
                    if budget_response:
                        return after_nlu_miss(budget_response, "brain", "budget")
                if brain_decision.intent == "apps":
                    app_response = self._app_command(low, text)
                    if app_response:
                        return after_nlu_miss(app_response, "brain", "apps")
                if brain_decision.intent == "math":
                    math_response = self._math_command(low, text)
                    if math_response:
                        return after_nlu_miss(math_response, "brain", "math")
                if brain_decision.intent == "research":
                    return after_nlu_miss(self._research_and_learn(low, now=when), "brain", "research")
                if brain_decision.intent == "habits":
                    return after_nlu_miss(self._emit(self._habit_recommendation_message()), "brain", "habits")
                if brain_decision.intent == "routine":
                    routine_response = self._routine_command(low, text, when)
                    if routine_response:
                        return after_nlu_miss(routine_response, "brain", "routine")
                if brain_decision.intent == "wake":
                    status = get_resident_status()
                    return after_nlu_miss(
                        self._emit(
                            "Diagnostico de despertar: "
                            f"autoarranque {status['startup']}, tarea {status['task']}, "
                            f"hora {status['wake_time']}, proxima ejecucion {status.get('next_run', 'desconocido')}."
                        ),
                        "brain",
                        "wake",
                    )
            # Intentar con el router semantico primero
            routed = self._route_semantic(text)
            if routed == "agenda":
                return after_nlu_miss(self._emit(self._build_today_status(when)), "semantic_router", "agenda")
            if routed == "clima":
                return after_nlu_miss(self._emit(self._weather_summary()), "semantic_router", "clima")
            if routed == "clases":
                return after_nlu_miss(
                    self._emit(self._classes_summary_for_day(when.date())),
                    "semantic_router",
                    "clases",
                )
            if routed == "presupuesto":
                budget_response = self._budget_command("presupuesto", "presupuesto")
                if budget_response:
                    return after_nlu_miss(budget_response, "semantic_router", "presupuesto")
            if routed == "noticias":
                return after_nlu_miss(self._emit(self._news_summary()), "semantic_router", "noticias")
            if routed == "app":
                app_response = self._app_command(low, text)
                if app_response:
                    return after_nlu_miss(app_response, "semantic_router", "app")
            if routed == "math":
                math_response = self._math_command(low, text)
                if math_response:
                    return after_nlu_miss(math_response, "semantic_router", "math")
            if routed == "habits":
                return after_nlu_miss(self._emit(self._habit_recommendation_message()), "semantic_router", "habits")
            if routed == "research":
                return after_nlu_miss(self._research_and_learn(low, now=when), "semantic_router", "research")
            # Fallback: usar Ollama para entender lenguaje natural
            ollama_response = self._ollama_fallback(text, when)
            if ollama_response is not None:
                return after_nlu_miss(ollama_response, "ollama", "natural_language")
            if self._should_auto_research(low):
                return after_nlu_miss(self._research_and_learn(low, now=when), "auto_research", "research")
            return after_nlu_miss(
                self._emit(
                    "Comprendi su mensaje, pero no estoy seguro de como ayudarle con eso. "
                    "Puede pedirme: agenda, clima, clases, presupuesto, noticias, recordatorios, "
                    "abrir aplicaciones, o diga 'lista' para ver todo lo que puedo hacer."
                    + (" Ollama no esta activo; si lo activa podre entender mejor." if self._ollama is None else "")
                ),
                "unhandled",
            )

    def _scheduler_pause_until(self, daily: dict[str, Any]) -> Optional[datetime]:
        raw = str(daily.get("scheduler_suppressed_until") or "").strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            daily.pop("scheduler_suppressed_until", None)
            daily.pop("scheduler_suppressed_reason", None)
            return None

    def _scheduler_is_paused(self, daily: dict[str, Any], now: datetime) -> bool:
        until = self._scheduler_pause_until(daily)
        if until is None:
            return False
        if now < until:
            return True
        daily.pop("scheduler_suppressed_until", None)
        daily.pop("scheduler_suppressed_reason", None)
        return False

    def _mark_current_due_events_sent(self, now: datetime, daily: dict[str, Any]) -> list[str]:
        sent = daily.setdefault("sent", [])
        marked: list[str] = []
        for item in self._built_in_events(now, daily) + self._due_agenda_reminders(now, daily):
            if item.event_id not in sent:
                sent.append(item.event_id)
                marked.append(item.event_id)
        return marked

    def _scheduler_message_was_recently_emitted(self, daily: dict[str, Any], message: str, now: datetime) -> bool:
        key = hashlib.sha1(normalize_text(message).encode("utf-8")).hexdigest()[:16]
        window = timedelta(minutes=int(self.config.get("scheduler_duplicate_window_minutes", 15) or 15))
        recent_raw = daily.get("recent_scheduler_emissions", [])
        recent: list[dict[str, str]] = []
        duplicate = False
        for item in recent_raw if isinstance(recent_raw, list) else []:
            if not isinstance(item, dict):
                continue
            try:
                emitted_at = datetime.fromisoformat(str(item.get("timestamp", "")))
            except ValueError:
                continue
            if now - emitted_at <= window:
                item_key = str(item.get("key", ""))
                recent.append({"key": item_key, "timestamp": emitted_at.isoformat(timespec="seconds")})
                duplicate = duplicate or item_key == key
        if duplicate:
            daily["recent_scheduler_emissions"] = recent[-20:]
            return True
        recent.append({"key": key, "timestamp": now.isoformat(timespec="seconds")})
        daily["recent_scheduler_emissions"] = recent[-20:]
        return False

    def force_stop(self, now: Optional[datetime] = None) -> str:
        """Detiene cualquier accion en curso y pausa temporalmente recordatorios del scheduler."""
        when = now or datetime.now()
        self._finish_dialog()
        try:
            while True:
                self.messages.get_nowait()
        except queue.Empty:
            pass
        self.voice.stop()
        daily = self._ensure_daily_state(when)
        self._mark_current_due_events_sent(when, daily)
        pause_minutes = int(self.config.get("scheduler_stop_pause_minutes", 10) or 10)
        pause_minutes = max(1, min(pause_minutes, 120))
        until = when + timedelta(minutes=pause_minutes)
        daily["scheduler_suppressed_until"] = until.isoformat(timespec="seconds")
        daily["scheduler_suppressed_reason"] = "manual_stop"
        daily["last_manual_stop_at"] = when.isoformat(timespec="seconds")
        self._save_state()
        return self._emit(
            f"Entendido. Me detengo y pauso recordatorios por {pause_minutes} minutos. "
            "Estoy listo para su siguiente instruccion."
        )

    def resume_scheduler(self, now: Optional[datetime] = None) -> str:
        when = now or datetime.now()
        daily = self._ensure_daily_state(when)
        daily.pop("scheduler_suppressed_until", None)
        daily.pop("scheduler_suppressed_reason", None)
        daily["last_scheduler_resume_at"] = when.isoformat(timespec="seconds")
        self._save_state()
        return self._emit("Listo. Reanude los recordatorios y el scheduler.")

    def _cleanup_past_events_once(self, today: date, daily: dict[str, Any]) -> None:
        """Notifica UNA sola vez sobre eventos pasados y ofrece limpiarlos."""
        notified_key = "past_events_notified"
        already = set(daily.get(notified_key, []))
        past_items = []
        for item in list(self.agenda.get("items", [])):
            if item.get("recurring"):
                continue
            try:
                item_date = date.fromisoformat(str(item.get("date")))
            except Exception:
                continue
            item_id = str(item.get("id", ""))
            if item_date < today and item_id not in already:
                past_items.append(item)
                already.add(item_id)
        if past_items:
            daily[notified_key] = list(already)
            self._save_state()
            names = ", ".join(f"'{item.get('title','Evento')}' ({item.get('date')})" for item in past_items[:5])
            extra = f" y {len(past_items)-5} mas" if len(past_items) > 5 else ""
            self._emit(
                f"Tiene {len(past_items)} evento(s) pasado(s): {names}{extra}. "
                "Diga 'limpiar agenda' para eliminarlos, o puede borrarlos desde el editor de Agenda."
            )

    def _handle_cleanup_past(self, now: datetime) -> str:
        """Elimina todos los eventos no-recurrentes cuya fecha ya paso."""
        today = now.date()
        removed = []
        remaining = []
        for item in self.agenda.get("items", []):
            if item.get("recurring"):
                remaining.append(item)
                continue
            try:
                item_date = date.fromisoformat(str(item.get("date")))
            except Exception:
                remaining.append(item)
                continue
            if item_date < today:
                removed.append(item.get("title", "Evento"))
            else:
                remaining.append(item)
        self.agenda["items"] = remaining
        self._save_agenda()
        if removed:
            return self._emit(f"Listo. Elimine {len(removed)} evento(s) pasado(s): {', '.join(removed[:8])}.")
        return self._emit("No hay eventos pasados para limpiar.")

    def scheduler_tick(self, now: Optional[datetime] = None) -> list[str]:
        when = now or datetime.now()
        try:
            self._poll_remote_control(when)
        except Exception:
            pass
        with self._lock:
            self.reload()
            daily = self._ensure_daily_state(when)
            had_scheduler_pause = bool(daily.get("scheduler_suppressed_until"))
            if self._scheduler_is_paused(daily, when):
                return []
            if had_scheduler_pause and not daily.get("scheduler_suppressed_until"):
                self._save_state()
            self._cleanup_past_events_once(when.date(), daily)
            due = self._built_in_events(when, daily) + self._due_agenda_reminders(when, daily)
            if not due:
                due = self._proactive_events(when, daily)
            if not due:
                due = self._ambient_companion_event(when, daily)
            if not due:
                return []
            sent = daily.setdefault("sent", [])
            emitted: list[str] = []
            wake_event_ids = set(self._wake_event_ids_for_day(when.date()))
            for item in due:
                if item.event_id in sent:
                    continue
                sent.append(item.event_id)
                if item.event_id in wake_event_ids:
                    self._record_wake_run(when, item.message, session_lock_state())
                if item.level == "ambient":
                    daily["last_companion_chat"] = when.isoformat(timespec="minutes")
                elif item.level == "ambient_news":
                    daily["last_companion_chat"] = when.isoformat(timespec="minutes")
                    daily["ambient_news_count"] = int(daily.get("ambient_news_count", 0)) + 1
                elif item.level == "proactive":
                    daily["last_proactive_at"] = when.isoformat(timespec="minutes")
                    suggestion = daily.pop("pending_proactive_suggestion", {})
                    if suggestion:
                        daily["last_proactive_suggestion"] = suggestion
                        self.state["last_proactive_suggestion"] = suggestion
                duplicate_message = self._scheduler_message_was_recently_emitted(daily, item.message, when)
                self._save_state()
                if duplicate_message:
                    continue
                emitted.append(self._emit(item.message))
            self._save_state()
            return emitted

    def today_dashboard(self, now: Optional[datetime] = None) -> dict[str, Any]:
        when = now or datetime.now()
        daily = self._ensure_daily_state(when)
        agenda = self._agenda_items_for_day(when.date())
        classes = self._classes_for_day(when.date())
        proactive = self._proactive_suggestions(when, daily)
        activity_calendar = self._activity_calendar_for_day(when.date(), when)
        activity_week = self._activity_calendar_for_range(when.date(), when, days=7)
        pending_today = self._task_store().tasks_for_day(when.date())
        pending_upcoming = self._task_store().upcoming(when, days=7, limit=8)
        suggestions = [item.to_dict() for item in proactive[:3]]
        last_decision = self.state.get("last_intent_decision", {})
        if not isinstance(last_decision, dict):
            last_decision = {}
        next_action = self._next_commitment_summary(when)
        return {
            "today": iso_day(when.date()),
            "weekday": WEEKDAY_LABELS[weekday_key(when.date())],
            "agenda": agenda,
            "override": self._current_override(when.date()),
            "daily_state": daily,
            "classes": classes,
            "habits": self.state.get("habit_history", [])[-10:],
            "habit_recommendations": build_adaptive_profile(7).get("recommendations", []),
            "budget": get_balance(),
            "focus": self.brain.daily_focus(when, agenda, classes, daily),
            "next_action": next_action,
            "risks": self._dashboard_risks(when, agenda, classes, pending_today),
            "critical_pending": [task.to_dict() for task in pending_today if task.priority == "high"],
            "proactive_suggestions": suggestions,
            "activity_calendar": activity_calendar.to_dict(),
            "activity_week": activity_week.to_dict(),
            "memory_summary": self._memory_store().summary(max_items=4),
            "memory_relevant": self._memory_store().preferences_summary(max_items=4),
            "pending_tasks_today": [task.to_dict() for task in pending_today],
            "pending_tasks": [task.to_dict() for task in pending_upcoming],
            "action_history": [entry.to_dict() for entry in self._history_store().recent(limit=5)],
            "understanding": {
                "last_decision": last_decision,
                "pending_dialog": dict(self.pending_dialog or {}),
                "last_nlu_intent": daily.get("last_nlu_intent", {}),
                "last_execution_receipt": dict(self.state.get("last_execution_receipt", {}))
                if isinstance(self.state.get("last_execution_receipt", {}), dict)
                else {},
            },
            "tool_capabilities": self._tool_capabilities_snapshot(),
            "executions": {
                "last_receipt": dict(self.state.get("last_execution_receipt", {}))
                if isinstance(self.state.get("last_execution_receipt", {}), dict)
                else {},
                "recent": list(self.state.get("execution_receipts", [])[:5])
                if isinstance(self.state.get("execution_receipts", []), list)
                else [],
            },
            "telegram": {
                "enabled": bool(self.config.get("telegram", {}).get("enabled", False)) if isinstance(self.config.get("telegram", {}), dict) else False,
            },
            "analysis": {
                "enabled": self._analysis_config().get("enabled", True),
                "last_result": dict(self.state.get("last_analysis", self.state.get("last_analysis_beta", {})))
                if isinstance(self.state.get("last_analysis", self.state.get("last_analysis_beta", {})), dict)
                else {},
                "reports": self._report_builder().list_reports(self._analysis_reports_dir(), limit=5),
            },
            "analysis_beta": {
                "enabled": self._analysis_config().get("enabled", True),
                "last_result": dict(self.state.get("last_analysis", self.state.get("last_analysis_beta", {})))
                if isinstance(self.state.get("last_analysis", self.state.get("last_analysis_beta", {})), dict)
                else {},
                "reports": self._report_builder().list_reports(self._analysis_reports_dir(), limit=5),
            },
            "remote_control": self._remote_control_snapshot(),
            "games": self._game_engine().active_summary(self.state.get("games", {}) if isinstance(self.state.get("games", {}), dict) else {}),
            "personal_activity": self._personal_activity_service().summary(days=7, now=when),
            "agent_system": {
                "memory": self._agent_memory_manager().snapshot(),
                "permissions": self._permission_manager().summary(),
                "tools": self._tool_router().list_tools(),
                "plugins": self._plugin_manager().summary(),
                "security_monitor": self._security_monitor().summary(),
                "last_plan": dict(self.state.get("last_agent_plan", {}))
                if isinstance(self.state.get("last_agent_plan", {}), dict)
                else {},
                "last_self_improvement": dict(self.state.get("last_self_improvement_proposal", {}))
                if isinstance(self.state.get("last_self_improvement_proposal", {}), dict)
                else {},
            },
            "config_active": self._config_active_summary(),
        }

    def _config_active_summary(self) -> dict[str, Any]:
        proactivity = self._effective_proactivity_config()
        telegram_cfg = self.config.get("telegram", {})
        if not isinstance(telegram_cfg, dict):
            telegram_cfg = {}
        automation = self.config.get("automation", {})
        if not isinstance(automation, dict):
            automation = {}
        personal_activity = self.config.get("personal_activity", {})
        if not isinstance(personal_activity, dict):
            personal_activity = {}
        validation = self.state.get("last_config_validation", {})
        if not isinstance(validation, dict):
            validation = {}
        last_wake = self.state.get("last_wake_attempt", {})
        if not isinstance(last_wake, dict):
            last_wake = {}
        return {
            "voice_enabled": bool(self.config.get("voice_enabled", True)),
            "tts_rate": int(self.config.get("tts_rate", 165) or 165),
            "telegram_enabled": bool(telegram_cfg.get("enabled", False)),
            "analysis_enabled": bool(self._analysis_config().get("enabled", True)),
            "analysis_beta_enabled": bool(self._analysis_config().get("enabled", True)),
            "remote_control_enabled": bool(self._remote_control_snapshot().get("enabled", False)),
            "personal_activity_enabled": bool(personal_activity.get("enabled", False)),
            "personal_activity_privacy_mode": str(personal_activity.get("privacy_mode", "app_category")),
            "personal_activity_poll_interval_seconds": int(personal_activity.get("poll_interval_seconds", 60) or 60),
            "permission_level": int(self._permission_manager().summary().get("current_level", 1)),
            "plugins_loaded": int(self._plugin_manager().summary().get("loaded", 0)),
            "proactivity_enabled": bool(proactivity.get("enabled", True)),
            "proactivity_mode": str(proactivity.get("mode", "conservative")),
            "ambient_enabled": bool(self.config.get("ambient_companion", {}).get("enabled", True))
            if isinstance(self.config.get("ambient_companion", {}), dict)
            else False,
            "wake_time": str(automation.get("morning_wake_time", "07:30")),
            "startup_enabled": bool(automation.get("startup_enabled", True)),
            "last_validation": validation,
            "last_wake_attempt": last_wake,
            "pending_morning_interaction": bool(self.state.get("pending_morning_interaction")),
        }

    def _dashboard_risks(
        self,
        now: datetime,
        agenda: list[dict[str, Any]],
        classes: list[str],
        pending_today: list[Any],
    ) -> list[str]:
        risks: list[str] = []
        if len(pending_today) >= 3:
            risks.append(f"{len(pending_today)} pendientes vencen hoy")
        if any(getattr(task, "priority", "") == "high" for task in pending_today):
            risks.append("hay pendientes de prioridad alta")
        if classes and not self._configured_leave_time_for_day(now.date()):
            risks.append("hay clases sin salida configurada")
        if len(agenda) >= 4:
            risks.append("agenda cargada")
        past = len(self._past_agenda_items(now.date()))
        if past:
            risks.append(f"{past} evento(s) pasado(s) por limpiar")
        return risks

    def morning_brief(self, now: Optional[datetime] = None) -> str:
        when = now or datetime.now()
        self.reload()
        daily = self._ensure_daily_state(when)
        sent = daily.setdefault("sent", [])
        for event_id in self._wake_event_ids_for_day(when.date()):
            if event_id not in sent:
                sent.append(event_id)
        brief = self._compose_morning_brief(when)
        self._record_wake_run(when, brief, session_lock_state())
        self._save_state()
        return self._emit(brief)

    def _record_wake_run(self, when: datetime, brief: str, session_state: str) -> None:
        record = {
            "timestamp": when.isoformat(timespec="seconds"),
            "session_state": session_state,
            "brief": brief,
            "safe_unlock_policy": "no_bypass",
        }
        self.state["last_wake_attempt"] = record
        self.state["last_wake_success"] = True
        history = self.state.setdefault("wake_run_history", [])
        if not isinstance(history, list):
            history = []
        history.append({key: value for key, value in record.items() if key != "brief"})
        self.state["wake_run_history"] = history[-20:]
        if session_state == "bloqueada":
            self.state["pending_morning_interaction"] = {
                "created_at": record["timestamp"],
                "brief": brief,
                "reason": "session_locked",
                "delivered": False,
            }

    def consume_pending_morning_interaction(self, *, require_interactive: bool = False) -> str:
        pending = self.state.get("pending_morning_interaction")
        if not isinstance(pending, dict) or bool(pending.get("delivered", False)):
            return ""
        if require_interactive and session_lock_state() == "bloqueada":
            return ""
        brief = str(pending.get("brief", "") or "").strip()
        if not brief:
            self.state.pop("pending_morning_interaction", None)
            self._save_state()
            return ""
        self.state.pop("pending_morning_interaction", None)
        self._save_state()
        return "Rutina matutina pendiente: la laptop desperto con Windows bloqueado. " + brief

    def get_routine_snapshot(self) -> dict[str, Any]:
        self.reload()
        routines = migrate_legacy_routines(self.config.get("weekly_routines", {}))
        snapshot: dict[str, Any] = {}
        for day_key in ROUTINE_WEEKDAY_KEYS:
            day_cfg = dict(resolve_day_cfg(routines, day_key))
            day_cfg["enabled"] = day_routine_enabled(routines, day_key)
            snapshot[day_key] = day_cfg
        return snapshot

    def get_routine_timeline(self) -> str:
        self.reload()
        routines = migrate_legacy_routines(self.config.get("weekly_routines", {}))

        def lines(items: list[dict[str, Any]]) -> list[str]:
            return [
                f"{item.get('time', '--:--')} - {str(item.get('message', '')).strip()}"
                for item in items
                if str(item.get("message", "")).strip() and str(item.get("time", "")).strip()
            ]

        parts: list[str] = []
        for day_key in ROUTINE_WEEKDAY_KEYS:
            day_cfg = resolve_day_cfg(routines, day_key)
            if not day_cfg and day_key not in {"monday", "tuesday", "wednesday", "thursday", "friday"}:
                continue
            label = ROUTINE_WEEKDAY_LABELS.get(day_key, day_key)
            enabled = "activa" if day_routine_enabled(routines, day_key) else "desactivada"
            parts.append(f"{label} ({enabled}):")
            if day_key == "monday" and day_cfg.get("skip_morning_routine", True):
                parts.append("Sin rutina recurrente por la manana.")
            parts.extend(lines(list(day_cfg.get("reminders", []))))
            if day_key == "monday":
                parts.append(f"{day_cfg.get('leave_time', '16:50')} - salida estimada")
                window = day_cfg.get("expected_arrival_window", ["17:00", "17:30"])
                parts.append(f"{window[0]} - empieza ventana para recordar pase de lista al llegar")
            if day_key == "friday":
                parts.append(f"{day_cfg.get('stop_all_after', '16:45')} - fin de rutinas del viernes")
            bath = day_cfg.get("bath_followup", {})
            if isinstance(bath, dict) and bath.get("start"):
                parts.append(f"{bath.get('start', '19:35')} - inicia insistencia del bano")
                parts.append(
                    f"cada {bath.get('repeat_minutes', 20)} minutos hasta {bath.get('stop', '22:30')}"
                )
            parts.append("")
        return "\n".join(parts).strip()

    def update_routines_from_editor(self, payload: dict[str, Any]) -> str:
        self.reload()
        original_routines = json.loads(
            json.dumps(self.config.get("weekly_routines", {}), ensure_ascii=False)
        )
        routines = migrate_legacy_routines(
            json.loads(json.dumps(original_routines, ensure_ascii=False))
        )
        errors: list[str] = []
        days_payload = payload.get("days", payload)
        if not isinstance(days_payload, dict):
            return self._emit("No guarde rutinas: formato invalido.")
        for day_key, day_payload in days_payload.items():
            if day_key not in ROUTINE_WEEKDAY_KEYS or not isinstance(day_payload, dict):
                continue
            errors.extend(validate_day_payload(day_key, day_payload))
        if errors:
            return self._emit("No guarde rutinas: " + " ".join(errors))
        for day_key, day_payload in days_payload.items():
            if day_key not in ROUTINE_WEEKDAY_KEYS or not isinstance(day_payload, dict):
                continue
            routines[day_key] = normalize_day_payload(day_key, day_payload)
        routines.pop("default_university_day", None)
        changed_ids = self._changed_routine_ids(original_routines, routines)
        result = self.apply_gui_config_patch({"weekly_routines": routines})
        if not result.valid:
            return self._emit("No guarde rutinas: " + " ".join(result.errors))
        self.reset_sent_for_changed_routines(changed_ids, [datetime.now().date()])
        return self._emit("Rutinas actualizadas. Ya guarde los cambios de Viernes.")

    def update_routines_from_form(self, payload: dict[str, str]) -> str:
        """Compatibilidad con formularios planos legacy."""
        if isinstance(payload, dict) and "days" in payload:
            return self.update_routines_from_editor(payload)
        return self._emit("Use el editor de rutinas actualizado para guardar cambios.")

    def _changed_routine_ids(self, before: dict[str, Any], after: dict[str, Any]) -> list[str]:
        changed: set[str] = set()

        def reminder_map(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
            reminders = cfg.get("reminders", []) if isinstance(cfg, dict) else []
            if not isinstance(reminders, list):
                return {}
            return {
                str(item.get("id", "") or ""): dict(item)
                for item in reminders
                if isinstance(item, dict) and str(item.get("id", "") or "").strip()
            }

        for scope in ROUTINE_WEEKDAY_KEYS:
            old_cfg = before.get(scope, {}) if isinstance(before.get(scope, {}), dict) else {}
            new_cfg = after.get(scope, {}) if isinstance(after.get(scope, {}), dict) else {}
            old_reminders = reminder_map(old_cfg)
            new_reminders = reminder_map(new_cfg)
            for reminder_id in set(old_reminders) | set(new_reminders):
                if old_reminders.get(reminder_id) != new_reminders.get(reminder_id):
                    changed.add(reminder_id)
            if old_cfg.get("bath_followup", {}) != new_cfg.get("bath_followup", {}):
                changed.add(f"{scope}_bath")
        legacy_before = before.get("default_university_day", {})
        legacy_after = after.get("default_university_day", {})
        if legacy_before != legacy_after:
            changed.add("legacy_university_day")

        old_monday = before.get("monday", {}) if isinstance(before.get("monday", {}), dict) else {}
        new_monday = after.get("monday", {}) if isinstance(after.get("monday", {}), dict) else {}
        if old_monday.get("arrival_message") != new_monday.get("arrival_message") or old_monday.get("expected_arrival_window") != new_monday.get("expected_arrival_window"):
            changed.add("monday_attendance_hint")
        if old_monday.get("bath_followup", {}) != new_monday.get("bath_followup", {}):
            changed.add("monday_bath")

        old_friday = before.get("friday", {}) if isinstance(before.get("friday", {}), dict) else {}
        new_friday = after.get("friday", {}) if isinstance(after.get("friday", {}), dict) else {}
        for key, reminder_id in (
            ("packing_time", "friday_packing"),
            ("packing_message", "friday_packing"),
            ("chores_time", "friday_chores"),
            ("chores_message", "friday_chores"),
        ):
            if old_friday.get(key) != new_friday.get(key):
                changed.add(reminder_id)
        return sorted(changed)
