from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any


DEFAULT_PROACTIVITY_CONFIG: dict[str, Any] = {
    "enabled": True,
    "mode": "conservative",
    "interval_minutes": 120,
    "lookahead_minutes": 120,
    "max_per_tick": 1,
}


@dataclass(frozen=True)
class ProactiveSuggestion:
    id: str
    message: str
    category: str
    priority: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "message": self.message,
            "category": self.category,
            "priority": self.priority,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ProactiveContext:
    now: datetime
    daily: dict[str, Any]
    config: dict[str, Any]
    agenda_today: list[dict[str, Any]]
    classes_today: list[str]
    leave_time: str | None
    past_events_count: int
    nlu_miss_count: int
    alias_suggestions_count: int = 0
    activity_block_count: int = 0
    memory_facts_count: int = 0
    personal_rules_count: int = 0
    next_personal_rule: dict[str, Any] | None = None
    pending_due_count: int = 0
    next_pending_task: dict[str, Any] | None = None


class ProactiveEngine:
    """Reglas locales de sugerencias operativas, sin ejecutar acciones."""

    def evaluate(self, context: ProactiveContext) -> list[ProactiveSuggestion]:
        cfg = self._config(context.config)
        if cfg.get("enabled") is False:
            return []

        suggestions: list[ProactiveSuggestion] = []
        leave = self._leave_suggestion(context)
        if leave is not None:
            suggestions.append(leave)
        agenda = self._agenda_suggestion(context, int(cfg.get("lookahead_minutes", 120) or 120))
        if agenda is not None:
            suggestions.append(agenda)
        cleanup = self._cleanup_suggestion(context)
        if cleanup is not None:
            suggestions.append(cleanup)
        nlu = self._nlu_suggestion(context)
        if nlu is not None:
            suggestions.append(nlu)
        alias = self._alias_suggestion(context)
        if alias is not None:
            suggestions.append(alias)
        calendar = self._calendar_suggestion(context)
        if calendar is not None:
            suggestions.append(calendar)
        memory = self._memory_suggestion(context)
        if memory is not None:
            suggestions.append(memory)
        personal_rule = self._personal_rule_suggestion(context)
        if personal_rule is not None:
            suggestions.append(personal_rule)
        pending = self._pending_task_suggestion(context)
        if pending is not None:
            suggestions.append(pending)

        suggestions.sort(key=lambda item: (-item.priority, item.category, item.id))
        return suggestions

    def _config(self, config: dict[str, Any]) -> dict[str, Any]:
        raw = config.get("proactivity", {}) if isinstance(config, dict) else {}
        merged = dict(DEFAULT_PROACTIVITY_CONFIG)
        if isinstance(raw, dict):
            merged.update(raw)
        return merged

    def _leave_suggestion(self, context: ProactiveContext) -> ProactiveSuggestion | None:
        if not context.classes_today or not context.leave_time:
            return None
        if context.daily.get("left_home") or context.daily.get("day_closed"):
            return None
        minutes = self._minutes_until(context.now, context.leave_time)
        if minutes is None or minutes < 15 or minutes > 90:
            return None
        label = self._minutes_label(minutes)
        classes = ", ".join(context.classes_today[:3])
        return ProactiveSuggestion(
            id=f"leave:{context.now.date().isoformat()}:{context.leave_time}",
            category="routine",
            priority=90,
            reason="salida proxima con clases registradas",
            message=(
                f"Senor, tiene clases hoy ({classes}) y faltan {label} para su salida de "
                f"{context.leave_time}. Conviene preparar lo esencial; si cambio el plan, diga "
                "'cambia salida a las HH:MM solo para hoy'."
            ),
        )

    def _agenda_suggestion(
        self,
        context: ProactiveContext,
        lookahead_minutes: int,
    ) -> ProactiveSuggestion | None:
        for item in context.agenda_today:
            hhmm = str(item.get("time", "") or "").strip()
            minutes = self._minutes_until(context.now, hhmm)
            if minutes is None or minutes < 30 or minutes > max(30, lookahead_minutes):
                continue
            title = str(item.get("title", "Evento") or "Evento")
            event_id = str(item.get("id", "") or self._compact_key(f"{hhmm}:{title}"))
            return ProactiveSuggestion(
                id=f"agenda:{context.now.date().isoformat()}:{event_id}",
                category="agenda",
                priority=80,
                reason="evento proximo en agenda",
                message=(
                    f"Senor, en {self._minutes_label(minutes)} tiene en agenda: {title} "
                    f"a las {hhmm}. Puede decir 'que sigue' si quiere revisar el contexto."
                ),
            )
        return None

    def _cleanup_suggestion(self, context: ProactiveContext) -> ProactiveSuggestion | None:
        if context.past_events_count <= 0:
            return None
        return ProactiveSuggestion(
            id=f"cleanup_past:{context.now.date().isoformat()}",
            category="maintenance",
            priority=70,
            reason="eventos pasados pendientes",
            message=(
                f"Veo {context.past_events_count} evento(s) pasado(s). Si quiere depurarlos, "
                "diga 'limpiar agenda'; le pedire confirmacion antes de borrar."
            ),
        )

    def _nlu_suggestion(self, context: ProactiveContext) -> ProactiveSuggestion | None:
        if context.nlu_miss_count < 2:
            return None
        return ProactiveSuggestion(
            id=f"nlu_help:{context.now.date().isoformat()}",
            category="nlu",
            priority=60,
            reason="varios mensajes no capturados por NLU",
            message=(
                "He tenido dificultad entendiendo algunas frases de hoy. Puede decir 'lista' "
                "para ver comandos disponibles, o pedirme la accion con palabras mas directas."
            ),
        )

    def _alias_suggestion(self, context: ProactiveContext) -> ProactiveSuggestion | None:
        if context.alias_suggestions_count <= 0:
            return None
        return ProactiveSuggestion(
            id=f"alias:{context.now.date().isoformat()}",
            category="learning",
            priority=50,
            reason="hay comandos repetidos que pueden abreviarse",
            message=(
                "Detecte comandos repetidos que podrian tener atajos. Diga 'alias sugeridos' "
                "para ver opciones."
            ),
        )

    def _calendar_suggestion(self, context: ProactiveContext) -> ProactiveSuggestion | None:
        if context.activity_block_count < 4:
            return None
        return ProactiveSuggestion(
            id=f"calendar_review:{context.now.date().isoformat()}",
            category="calendar",
            priority=45,
            reason="calendario operativo con varios bloques",
            message=(
                "Ya tengo armado un calendario operativo para hoy. Diga 'plan de hoy' "
                "si quiere revisarlo antes de que se cargue el dia."
            ),
        )

    def _memory_suggestion(self, context: ProactiveContext) -> ProactiveSuggestion | None:
        if context.memory_facts_count > 0 or context.nlu_miss_count == 0:
            return None
        return ProactiveSuggestion(
            id=f"memory_seed:{context.now.date().isoformat()}",
            category="memory",
            priority=35,
            reason="poca memoria personal disponible",
            message=(
                "Puedo ser mas preciso si me da datos estables. Por ejemplo: "
                "'recuerda que prefiero salir con 20 minutos de margen'."
            ),
        )

    def _personal_rule_suggestion(self, context: ProactiveContext) -> ProactiveSuggestion | None:
        rule = context.next_personal_rule or {}
        hhmm = str(rule.get("time", "") or "").strip()
        minutes = self._minutes_until(context.now, hhmm)
        if minutes is None or minutes > 120:
            return None
        action = str(rule.get("action_text", "revisar regla personal") or "revisar regla personal")
        relation = "antes de" if str(rule.get("relation", "")) == "before" else "a las"
        return ProactiveSuggestion(
            id=f"personal_rule:{context.now.date().isoformat()}:{rule.get('id', action)}",
            category="personal_rule",
            priority=85,
            reason="regla personal activa para hoy",
            message=f"Regla personal para hoy: {action} {relation} {hhmm}.",
        )

    def _pending_task_suggestion(self, context: ProactiveContext) -> ProactiveSuggestion | None:
        task = context.next_pending_task or {}
        title = str(task.get("title", "") or "").strip()
        if not title:
            return None
        due_date = str(task.get("due_date", "") or "").strip()
        due_time = str(task.get("due_time", "") or "").strip()
        priority = 83 if due_date == context.now.date().isoformat() else 62
        if str(task.get("priority", "")) == "high":
            priority += 8
        when = "hoy" if due_date == context.now.date().isoformat() else f"para {due_date}" if due_date else "sin fecha"
        if due_time:
            when += f" a las {due_time}"
        return ProactiveSuggestion(
            id=f"pending_task:{task.get('id', self._compact_key(title))}",
            category="pending",
            priority=priority,
            reason="pendiente abierto proximo",
            message=(
                f"Pendiente abierto {when}: {title}. Diga 'que tengo pendiente' para revisarlo "
                "o 'ya hice eso' si ya quedo listo."
            ),
        )

    def _minutes_until(self, now: datetime, hhmm: str) -> float | None:
        try:
            hour_raw, minute_raw = hhmm.split(":", 1)
            target = now.replace(hour=int(hour_raw), minute=int(minute_raw), second=0, microsecond=0)
        except Exception:
            return None
        delta = target - now
        if delta < timedelta(0):
            return None
        return delta.total_seconds() / 60

    def _minutes_label(self, minutes: float) -> str:
        rounded = int(round(minutes))
        if rounded == 1:
            return "1 minuto"
        return f"{rounded} minutos"

    def _compact_key(self, value: str) -> str:
        return "".join(ch.lower() if ch.isalnum() else "_" for ch in value).strip("_")[:40] or "evento"
