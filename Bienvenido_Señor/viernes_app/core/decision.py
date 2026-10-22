from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    confidence: float
    risk: str
    handler: str
    reason: str
    slots: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    mutates: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "risk": self.risk,
            "handler": self.handler,
            "reason": self.reason,
            "slots": dict(self.slots),
            "requires_confirmation": self.requires_confirmation,
            "mutates": self.mutates,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentDecision":
        return cls(
            intent=str(data.get("intent") or "unknown"),
            confidence=float(data.get("confidence", 0.0) or 0.0),
            risk=str(data.get("risk") or "low"),
            handler=str(data.get("handler") or "unhandled"),
            reason=str(data.get("reason") or ""),
            slots=dict(data.get("slots") or {}),
            requires_confirmation=bool(data.get("requires_confirmation", False)),
            mutates=bool(data.get("mutates", False)),
        )


@dataclass(frozen=True)
class CommandDryRun:
    command: str
    decision: IntentDecision
    predicted_changes: list[str] = field(default_factory=list)
    response_preview: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "decision": self.decision.to_dict(),
            "predicted_changes": list(self.predicted_changes),
            "response_preview": self.response_preview,
        }


@dataclass(frozen=True)
class ToolCapability:
    action: str
    risk: str
    mutates: bool
    requires_confirmation: bool
    description: str
    preconditions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "risk": self.risk,
            "mutates": self.mutates,
            "requires_confirmation": self.requires_confirmation,
            "description": self.description,
            "preconditions": list(self.preconditions),
        }


MUTATING_INTENTS: set[str] = {
    "cleanup_past_events",
    "proactive_mode",
    "memory_remember",
    "memory_forget",
    "memory_update",
    "memory_preference_set",
    "memory_preference_forget",
    "personal_rule_create",
    "personal_rule_forget",
    "activity_reorganize",
    "action_plan",
    "classes_cancelled_today",
    "classes_change",
    "free_day_today",
    "mark_arrival",
    "mark_left_home",
    "mark_bath_done",
    "routine_slot_change",
    "leave_time_change",
    "wake_schedule_change",
    "wake_test_schedule",
    "wake_repair",
    "telegram_activate",
    "telegram_notify",
    "day_close",
    "prepare_tomorrow",
    "remote_control_activate",
}

HIGH_RISK_INTENTS: set[str] = {
    "cleanup_past_events",
}


def decision_for_intent(
    *,
    intent: str,
    confidence: float,
    reason: str,
    slots: dict[str, Any] | None = None,
    handler: str = "",
) -> IntentDecision:
    mutates = intent in MUTATING_INTENTS
    risk = "high" if intent in HIGH_RISK_INTENTS else "medium" if mutates else "low"
    return IntentDecision(
        intent=intent,
        confidence=confidence,
        risk=risk,
        handler=handler or _default_handler(intent),
        reason=reason,
        slots=dict(slots or {}),
        requires_confirmation=mutates,
        mutates=mutates,
    )


def _default_handler(intent: str) -> str:
    if intent.startswith("memory_") or intent.startswith("personal_rule_"):
        return "_memory_command"
    if intent.startswith("activity_") or intent in {"weekly_goals", "day_progress", "day_close", "prepare_tomorrow"}:
        return "_activity_calendar_command"
    if intent.startswith("proactive_"):
        return "_proactive_feedback_command"
    if intent.startswith("classes_") or intent == "free_day_today":
        return "_classes_command"
    if intent.startswith("routine_") or intent.startswith("leave_time_"):
        return "_routine_command"
    if intent.startswith("wake_"):
        return "_wake_command"
    if intent.startswith("telegram_"):
        return "_telegram_command"
    if intent.startswith("remote_control_"):
        return "_remote_control_command"
    if intent == "game_command":
        return "_game_command"
    if intent in {"simulation_request", "research_table", "chart_request", "analysis_report"}:
        return "_analysis_command"
    if intent == "action_plan":
        return "_plan_unprogrammed_action"
    return f"intent:{intent}"


TOOL_CAPABILITIES: tuple[ToolCapability, ...] = (
    ToolCapability("show_activity_calendar", "low", False, False, "Leer calendario operativo."),
    ToolCapability("show_activity_week", "low", False, False, "Leer calendario semanal."),
    ToolCapability("add_daily_note", "medium", True, True, "Guardar una nota diaria."),
    ToolCapability("set_temporary_leave_time", "medium", True, True, "Ajustar salida temporal."),
    ToolCapability("create_agenda_event", "medium", True, True, "Crear evento en agenda."),
    ToolCapability("create_reminder", "medium", True, True, "Crear recordatorio."),
    ToolCapability("create_personal_rule", "medium", True, True, "Crear regla personal."),
    ToolCapability("remember_fact", "medium", True, True, "Guardar dato en memoria personal."),
    ToolCapability("set_preference", "medium", True, True, "Actualizar preferencia personal."),
    ToolCapability("create_task", "medium", True, True, "Crear pendiente."),
    ToolCapability("complete_task", "medium", True, True, "Completar pendiente."),
    ToolCapability("postpone_task", "medium", True, True, "Posponer pendiente."),
    ToolCapability("cancel_task", "high", True, True, "Cancelar pendiente."),
    ToolCapability("research_topic", "low", False, False, "Investigar en web."),
    ToolCapability("open_app", "low", False, False, "Abrir aplicacion local."),
    ToolCapability("send_telegram_notification", "medium", False, True, "Enviar notificacion por Telegram.", ("telegram activo",)),
    ToolCapability("game_query", "low", False, False, "Consultar juegos locales."),
    ToolCapability("game_start", "low", True, False, "Iniciar partida local."),
    ToolCapability("game_move", "low", True, False, "Jugar turno en partida local."),
)


CAPABILITY_BY_ACTION: dict[str, ToolCapability] = {capability.action: capability for capability in TOOL_CAPABILITIES}


def capability_for_action(action: str) -> ToolCapability | None:
    return CAPABILITY_BY_ACTION.get(action)


COMMAND_AUDIT_MATRIX: tuple[tuple[str, str], ...] = (
    ("cambia la hora de la rutina de la manana a las 8:30 am", "wake_schedule_change"),
    ("a que hora esta configurado el autoarranque y la rutina de la manana", "wake_schedule_query"),
    ("cambia de horario de salida a las 12 de hoy solo para hoy", "leave_time_change"),
    ("cual es mi horario de salida hoy", "leave_time_query"),
    ("cambia horario de clases", "classes_change"),
    ("que clases tengo hoy", "classes_today"),
    ("cambia la clase de manana a ingles", "classes_change"),
    ("cambia la hora de mi rutina de jueves desayuno a las 8", "routine_slot_change"),
    ("a que hora es mi rutina de jueves desayuno", "routine_slot_query"),
    ("recuerda que prefiero salir temprano", "memory_remember"),
    ("mis preferencias", "memory_preferences_query"),
    ("ayudame a guardar en memoria que mi proyecto principal es viernes", "action_plan"),
    ("prepara un aviso por telegram para que revise mochila", "action_plan"),
    ("que me sugieres ahora", "proactive_suggestions"),
    ("probar comando cambia salida a las 12 hoy", "command_dry_run"),
    ("simula si gasto 200 pesos diarios esta semana", "simulation_request"),
    ("investiga modelos de laptop y haz tabla", "research_table"),
    ("haz una grafica de mis gastos", "chart_request"),
    ("jugar gato", "game_command"),
    ("jugar batalla naval", "game_command"),
    ("estado juego", "game_command"),
)
