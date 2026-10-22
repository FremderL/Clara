from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from viernes_app.core.action_planner import ActionPlan, PlanStep
from viernes_app.core.decision import capability_for_action
from viernes_app.services.apps import open_application
from viernes_app.services.learning import log_user_action
from viernes_app.services.tools import search_web


@dataclass(frozen=True)
class ActionExecutionResult:
    message: str
    mutated: bool = False
    blocked: bool = False


class ActionExecutor:
    """Ejecuta planes usando las capacidades reales de Viernes con compuertas de seguridad."""

    def execute(self, plan: ActionPlan, runtime: Any, now: datetime, *, confirmed: bool = False) -> ActionExecutionResult:
        unsupported = [step.action for step in plan.steps if capability_for_action(step.action) is None]
        if unsupported:
            return ActionExecutionResult(
                "El plan contiene acciones no registradas: " + ", ".join(sorted(set(unsupported))) + ".",
                blocked=True,
            )
        needs_confirmation = any(self._step_requires_confirmation(step) for step in plan.steps)
        if needs_confirmation and not confirmed:
            return ActionExecutionResult(
                "El plan incluye cambios. Necesito confirmacion explicita antes de aplicarlo.",
                blocked=True,
            )

        history_context: Any = None
        if any(step.mutates for step in plan.steps) and confirmed:
            begin_history = getattr(runtime, "_begin_action_history", None)
            if callable(begin_history):
                history_context = begin_history(plan, now)

        messages: list[str] = []
        mutated = False
        for step in plan.steps:
            result = self._execute_step(step, runtime, now)
            if result.message:
                messages.append(result.message)
            mutated = mutated or result.mutated
        if mutated:
            try:
                runtime._save_state()
            except Exception:
                pass
            commit_history = getattr(runtime, "_commit_action_history", None)
            if callable(commit_history):
                commit_history(history_context, plan, now, " ".join(messages).strip())
        return ActionExecutionResult(" ".join(messages).strip() or "Plan ejecutado.", mutated=mutated)

    def _step_requires_confirmation(self, step: PlanStep) -> bool:
        capability = capability_for_action(step.action)
        return bool(step.mutates or (capability and capability.requires_confirmation))

    def _execute_step(self, step: PlanStep, runtime: Any, now: datetime) -> ActionExecutionResult:
        if step.action == "show_activity_calendar":
            target = self._parse_date(str(step.payload.get("date", now.date().isoformat())), now.date())
            return ActionExecutionResult(runtime._activity_calendar_for_day(target, now).summary(limit=4))
        if step.action == "show_activity_week":
            start = self._parse_date(str(step.payload.get("date", now.date().isoformat())), now.date())
            days = int(step.payload.get("days", 7) or 7)
            return ActionExecutionResult(runtime._activity_calendar_for_range(start, now, days=days).summary())
        if step.action == "add_daily_note":
            return self._add_daily_note(step, runtime, now)
        if step.action == "set_temporary_leave_time":
            return self._set_temporary_leave_time(step, runtime, now)
        if step.action == "create_agenda_event":
            return self._create_agenda_event(step, runtime, now)
        if step.action == "create_reminder":
            return self._create_reminder(step, runtime, now)
        if step.action == "create_personal_rule":
            return self._create_personal_rule(step, runtime, now)
        if step.action == "remember_fact":
            return self._remember_fact(step, runtime, now)
        if step.action == "set_preference":
            return self._set_preference(step, runtime, now)
        if step.action == "create_task":
            return self._create_task(step, runtime, now)
        if step.action == "complete_task":
            return self._complete_task(step, runtime, now)
        if step.action == "postpone_task":
            return self._postpone_task(step, runtime, now)
        if step.action == "cancel_task":
            return self._cancel_task(step, runtime, now)
        if step.action == "research_topic":
            return self._research_topic(step, runtime, now)
        if step.action == "open_app":
            return self._open_app(step)
        if step.action == "send_telegram_notification":
            return self._send_telegram_notification(step, runtime, now)
        return ActionExecutionResult(f"No reconozco el paso '{step.action}'.")

    def _add_daily_note(self, step: PlanStep, runtime: Any, now: datetime) -> ActionExecutionResult:
        target_key = str(step.payload.get("date", now.date().isoformat()))
        note = str(step.payload.get("note", "")).strip()
        if not note:
            return ActionExecutionResult("Nota omitida: venia vacia.")
        holder = runtime.state.setdefault("daily", {}).setdefault(target_key, {})
        holder.setdefault("notes", []).append(note)
        holder["notes"] = holder["notes"][-20:]
        return ActionExecutionResult(f"Nota guardada para {target_key}: {note}", mutated=True)

    def _set_temporary_leave_time(self, step: PlanStep, runtime: Any, now: datetime) -> ActionExecutionResult:
        target_key = str(step.payload.get("date", now.date().isoformat()))
        hhmm = str(step.payload.get("time", "")).strip()
        if not re.fullmatch(r"\d{2}:\d{2}", hhmm):
            return ActionExecutionResult("No aplique cambio de salida porque la hora no es valida.")
        runtime.state.setdefault("day_overrides", {}).setdefault(target_key, {})["leave_time"] = hhmm
        target_daily = runtime.state.setdefault("daily", {}).get(target_key)
        if isinstance(target_daily, dict):
            leave_event_ids = {
                "default:leave_checklist",
                "default:leave_checklist_followup",
                "thursday:thursday_leave",
                "friday:friday_leave_checklist",
            }
            target_daily["sent"] = [
                event_id for event_id in list(target_daily.get("sent", [])) if event_id not in leave_event_ids
            ]
            target_daily["day_closed"] = False
        return ActionExecutionResult(f"Salida temporal de {target_key} ajustada a {hhmm}.", mutated=True)

    def _create_agenda_event(self, step: PlanStep, runtime: Any, now: datetime) -> ActionExecutionResult:
        title = str(step.payload.get("title", "Evento") or "Evento").strip()
        target = self._parse_date(str(step.payload.get("date", now.date().isoformat())), now.date())
        hhmm = str(step.payload.get("time", "09:00") or "09:00").strip()
        category = str(step.payload.get("category", "evento") or "evento").strip()
        if not re.fullmatch(r"\d{2}:\d{2}", hhmm):
            hhmm = "09:00"
        runtime._add_agenda_item(title, target, hhmm, category=category)
        return ActionExecutionResult(f"Evento creado: {title} el {target.isoformat()} a las {hhmm}.", mutated=True)

    def _create_reminder(self, step: PlanStep, runtime: Any, now: datetime) -> ActionExecutionResult:
        title = str(step.payload.get("title", "Recordatorio") or "Recordatorio").strip()
        target = self._parse_date(str(step.payload.get("date", now.date().isoformat())), now.date())
        hhmm = str(step.payload.get("time", "09:00") or "09:00").strip()
        if not re.fullmatch(r"\d{2}:\d{2}", hhmm):
            hhmm = "09:00"
        hour, minute = [int(part) for part in hhmm.split(":", 1)]
        runtime._add_timed_reminder(title, datetime.combine(target, datetime.min.time()).replace(hour=hour, minute=minute))
        return ActionExecutionResult(f"Recordatorio creado: {title} el {target.isoformat()} a las {hhmm}.", mutated=True)

    def _create_personal_rule(self, step: PlanStep, runtime: Any, now: datetime) -> ActionExecutionResult:
        rule_text = str(step.payload.get("rule_text", "")).strip()
        if not rule_text:
            return ActionExecutionResult("No cree regla personal porque venia vacia.")
        rule = runtime._memory_store().add_personal_rule(rule_text, now=now)
        return ActionExecutionResult(f"Regla personal creada: {rule.action_text}.", mutated=True)

    def _remember_fact(self, step: PlanStep, runtime: Any, now: datetime) -> ActionExecutionResult:
        text = str(step.payload.get("text", "") or "").strip()
        if not text:
            return ActionExecutionResult("No guarde memoria porque venia vacia.")
        fact = runtime._memory_store().remember(
            text,
            category=str(step.payload.get("category", "general") or "general"),
            source=str(step.payload.get("source", "action_plan") or "action_plan"),
            now=now,
        )
        return ActionExecutionResult(f"Memoria guardada: {fact.text}.", mutated=True)

    def _set_preference(self, step: PlanStep, runtime: Any, now: datetime) -> ActionExecutionResult:
        key = str(step.payload.get("key", "") or "").strip()
        value = str(step.payload.get("value", "") or "").strip()
        if not key or not value:
            return ActionExecutionResult("No actualice preferencia porque faltaba clave o valor.")
        pref = runtime._memory_store().set_preference(
            key,
            value,
            category=str(step.payload.get("category", "general") or "general"),
            source=str(step.payload.get("source", "action_plan") or "action_plan"),
            now=now,
        )
        return ActionExecutionResult(f"Preferencia actualizada: {pref.key}: {pref.value}.", mutated=True)

    def _create_task(self, step: PlanStep, runtime: Any, now: datetime) -> ActionExecutionResult:
        title = str(step.payload.get("title", "") or "").strip()
        if not title:
            return ActionExecutionResult("No cree pendiente porque venia sin titulo.")
        task = runtime._task_store().add_task(
            title,
            due_date=str(step.payload.get("due_date", "") or ""),
            due_time=str(step.payload.get("due_time", "") or ""),
            priority=str(step.payload.get("priority", "normal") or "normal"),
            category=str(step.payload.get("category", "general") or "general"),
            next_action=str(step.payload.get("next_action", "") or ""),
            source=str(step.payload.get("source", "action_plan") or "action_plan"),
            now=now,
        )
        due = f" para {task.due_date}" if task.due_date else ""
        if task.due_time:
            due += f" a las {task.due_time}"
        return ActionExecutionResult(f"Pendiente creado: {task.title}{due}.", mutated=True)

    def _complete_task(self, step: PlanStep, runtime: Any, now: datetime) -> ActionExecutionResult:
        query = str(step.payload.get("query", "") or "").strip()
        task = runtime._task_store().complete_task(query, now=now)
        if task is None:
            return ActionExecutionResult("No encontre un pendiente abierto que coincida.")
        runtime.state["last_task_reference"] = task.id
        return ActionExecutionResult(f"Pendiente completado: {task.title}.", mutated=True)

    def _postpone_task(self, step: PlanStep, runtime: Any, now: datetime) -> ActionExecutionResult:
        query = str(step.payload.get("query", "") or "").strip()
        target = str(step.payload.get("due_date", "") or "").strip()
        task = runtime._task_store().postpone_task(
            query,
            due_date=target,
            due_time=str(step.payload.get("due_time", "") or ""),
            now=now,
        )
        if task is None:
            return ActionExecutionResult("No encontre un pendiente abierto para posponer.")
        runtime.state["last_task_reference"] = task.id
        due = f"{task.due_date}" if task.due_date else "sin fecha"
        if task.due_time:
            due += f" a las {task.due_time}"
        return ActionExecutionResult(f"Pendiente pospuesto: {task.title} para {due}.", mutated=True)

    def _cancel_task(self, step: PlanStep, runtime: Any, now: datetime) -> ActionExecutionResult:
        query = str(step.payload.get("query", "") or "").strip()
        task = runtime._task_store().cancel_task(query, now=now)
        if task is None:
            return ActionExecutionResult("No encontre un pendiente abierto para cancelar.")
        runtime.state["last_task_reference"] = task.id
        return ActionExecutionResult(f"Pendiente cancelado: {task.title}.", mutated=True)

    def _research_topic(self, step: PlanStep, runtime: Any, now: datetime) -> ActionExecutionResult:
        query = str(step.payload.get("query", "")).strip()
        if not query:
            return ActionExecutionResult("Investigacion omitida: no habia tema.")
        result = search_web(query)
        if not result or str(result).lower().startswith("no encontre resultados"):
            return ActionExecutionResult(f"No pude investigar {query} en la web ahora mismo.")
        save = bool(step.payload.get("save"))
        if save:
            learned = runtime.state.setdefault("learned_web", [])
            if isinstance(learned, list):
                learned.append({"query": query, "summary": result, "timestamp": now.isoformat(timespec="seconds")})
                runtime.state["learned_web"] = learned[-80:]
        try:
            log_user_action(query[:50], category="web")
        except Exception:
            pass
        if save:
            return ActionExecutionResult(f"Investigue y guarde contexto sobre {query}.", mutated=True)
        return ActionExecutionResult(f"Investigue {query}: {str(result).strip()[:240]}.")

    def _open_app(self, step: PlanStep) -> ActionExecutionResult:
        app = str(step.payload.get("app", "")).strip()
        if not app:
            return ActionExecutionResult("No abri aplicacion porque no se indico cual.")
        _ok, message = open_application(app)
        return ActionExecutionResult(message)

    def _send_telegram_notification(self, step: PlanStep, runtime: Any, now: datetime) -> ActionExecutionResult:
        message = str(step.payload.get("message", "") or "").strip()
        if not message:
            return ActionExecutionResult("No envie Telegram porque el mensaje venia vacio.")
        notifier = runtime._telegram_notifier()
        if not notifier.is_enabled():
            return ActionExecutionResult("No envie Telegram porque no esta configurado.")
        sent = notifier.send(message)
        return ActionExecutionResult("Notificacion enviada por Telegram." if sent else "No pude enviar la notificacion por Telegram.")

    def _parse_date(self, value: str, fallback: date) -> date:
        try:
            return date.fromisoformat(value)
        except Exception:
            return fallback
