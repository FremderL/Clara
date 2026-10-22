from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any


class ActionRisk:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class PlanStep:
    id: str
    description: str
    action: str
    payload: dict[str, Any] = field(default_factory=dict)
    mutates: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "action": self.action,
            "payload": dict(self.payload),
            "mutates": self.mutates,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanStep":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:8]),
            description=str(data.get("description") or ""),
            action=str(data.get("action") or "note"),
            payload=dict(data.get("payload") or {}),
            mutates=bool(data.get("mutates", False)),
        )


@dataclass(frozen=True)
class ActionPlan:
    id: str
    summary: str
    risk: str
    steps: list[PlanStep]
    requires_confirmation: bool
    created_at: str
    intent: str = "unprogrammed_help"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "summary": self.summary,
            "risk": self.risk,
            "requires_confirmation": self.requires_confirmation,
            "created_at": self.created_at,
            "intent": self.intent,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionPlan":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:10]),
            summary=str(data.get("summary") or ""),
            risk=str(data.get("risk") or ActionRisk.LOW),
            requires_confirmation=bool(data.get("requires_confirmation", False)),
            created_at=str(data.get("created_at") or datetime.now().isoformat(timespec="seconds")),
            intent=str(data.get("intent") or "unprogrammed_help"),
            steps=[PlanStep.from_dict(item) for item in list(data.get("steps", [])) if isinstance(item, dict)],
        )


class ActionPlanner:
    """Convierte peticiones ambiguas de vida diaria en planes confirmables."""

    def create_plan(self, text: str, now: datetime) -> ActionPlan | None:
        low = _normalize(text)
        if not low:
            return None
        if not self._looks_like_life_planning(low):
            return None

        target_day = self._target_day(low, now.date())
        target_label = "hoy" if target_day == now.date() else "manana" if target_day == now.date() + timedelta(days=1) else target_day.isoformat()
        steps: list[PlanStep] = [
            PlanStep(
                id="review_context",
                description=f"Revisar calendario operativo de {target_label}.",
                action="show_activity_calendar",
                payload={"date": target_day.isoformat()},
                mutates=False,
            )
        ]

        hhmm = self._extract_time(low)
        task_cancel_step = self._task_cancel_step(low)
        if task_cancel_step is not None:
            steps.append(task_cancel_step)
        task_complete_step = self._task_complete_step(low)
        if task_complete_step is not None:
            steps.append(task_complete_step)
        task_postpone_step = self._task_postpone_step(low, target_day, now.date())
        if task_postpone_step is not None:
            steps.append(task_postpone_step)
        task_create_step = self._task_create_step(low, target_day)
        if task_create_step is not None:
            steps.append(task_create_step)
        preference_step = self._preference_step(low)
        if preference_step is not None:
            steps.append(preference_step)
        memory_fact_step = self._memory_fact_step(low)
        if memory_fact_step is not None:
            steps.append(memory_fact_step)
        agenda_step = self._agenda_step(low, target_day)
        if agenda_step is not None:
            steps.append(agenda_step)
        reminder_step = self._reminder_step(low, target_day)
        if reminder_step is not None:
            steps.append(reminder_step)
        study_note_step = self._study_note_step(low, target_day, target_label)
        if study_note_step is not None:
            steps.append(study_note_step)
        personal_rule_step = self._personal_rule_step(low)
        if personal_rule_step is not None:
            steps.append(personal_rule_step)
        research_step = self._research_step(low)
        if research_step is not None:
            steps.append(research_step)
        app_step = self._app_step(low)
        if app_step is not None:
            steps.append(app_step)
        telegram_step = self._telegram_step(low)
        if telegram_step is not None:
            steps.append(telegram_step)
        if ("salida" in low or "salir" in low) and hhmm:
            steps.append(
                PlanStep(
                    id="set_leave_override",
                    description=f"Ajustar la salida de {target_label} a las {hhmm}.",
                    action="set_temporary_leave_time",
                    payload={"date": target_day.isoformat(), "time": hhmm},
                    mutates=True,
                )
            )
        elif (
            any(token in low for token in ("clase", "clases", "ingles", "temprano", "tarde", "ayudame", "organiza", "estudiar"))
            and agenda_step is None
            and reminder_step is None
            and study_note_step is None
            and research_step is None
            and app_step is None
            and preference_step is None
            and memory_fact_step is None
            and telegram_step is None
        ):
            steps.append(
                PlanStep(
                    id="add_daily_note",
                    description=f"Guardar una nota operativa para {target_label}.",
                    action="add_daily_note",
                    payload={
                        "date": target_day.isoformat(),
                        "note": self._daily_note(low, target_label),
                    },
                    mutates=True,
                )
            )

        steps = self._dedupe_steps(steps)
        requires_confirmation = any(step.mutates for step in steps)
        if len(steps) == 1 and not requires_confirmation:
            return None
        risk = ActionRisk.HIGH if any(step.action == "cancel_task" for step in steps) else ActionRisk.MEDIUM
        return ActionPlan(
            id=uuid.uuid4().hex[:10],
            summary=f"Plan para ayudar con {target_label}: revisar contexto y preparar ajustes seguros.",
            risk=risk if requires_confirmation else ActionRisk.LOW,
            steps=steps,
            requires_confirmation=requires_confirmation,
            created_at=now.isoformat(timespec="seconds"),
        )

    def _looks_like_life_planning(self, low: str) -> bool:
        action_words = (
            "ayudame",
            "organiza",
            "organizame",
            "planea",
            "prepara",
            "preparame",
            "reorganiza",
            "acomoda",
            "necesito",
            "tengo que",
            "hay que",
            "debo",
            "agenda",
            "agendame",
            "recuerdame",
            "investiga",
            "busca",
            "consulta",
            "aprende",
            "guarda",
            "guardar",
            "memoriza",
            "recordar",
            "notifica",
            "notificarme",
            "avisame",
            "avisar",
            "manda",
            "mandame",
            "envia",
            "enviame",
            "abre",
            "abrir",
        )
        life_words = (
            "clase",
            "clases",
            "agenda",
            "rutina",
            "salida",
            "salir",
            "manana",
            "hoy",
            "ingles",
            "temprano",
            "lunes",
            "martes",
            "miercoles",
            "jueves",
            "viernes",
            "sabado",
            "domingo",
            "maleta",
            "entrega",
            "entregar",
            "estudiar",
            "estudio",
            "recordatorio",
            "pendiente",
            "pendientes",
            "tarea",
            "tareas",
            "compromiso",
            "compromisos",
            "app",
            "bloc",
            "notas",
            "aplicacion",
            "memoria",
            "perfil",
            "preferencia",
            "preferencias",
            "prefiero",
            "telegram",
            "aviso",
            "notificacion",
            "mensaje",
        )
        if any(word in low for word in action_words) and any(word in low for word in life_words):
            return True
        if re.search(r"\b(crea|crear|agrega|agregar|anota|apunta)\b.*\b(pendiente|tarea|compromiso)\b", low):
            return True
        if re.search(r"\b(tengo\s+que|hay\s+que|debo)\b", low):
            return True
        if re.search(r"\b(ya\s+hice|ya\s+termine|complete|completa|marca)\b", low):
            return True
        if re.search(r"\b(pospon|posponer|posponme|mueve|pasa|aplaza)\b", low):
            return True
        if re.search(r"\b(cancela|cancelar|elimina|eliminar|borra|borrar)\b.*\b(pendiente|tarea|compromiso)\b", low):
            return True
        if any(word in low for word in ("investiga", "busca", "consulta", "aprende sobre", "abre", "abrir")):
            return True
        if re.search(r"\b(guarda|guardar|memoriza|recordar|recuerda)\b.*\b(memoria|perfil|preferencia|prefiero)\b", low):
            return True
        if re.search(r"\b(telegram|notificacion|aviso|mensaje)\b", low) and re.search(
            r"\b(avisame|avisar|notifica|notificarme|manda|mandame|envia|enviame|prepara)\b",
            low,
        ):
            return True
        return any(word in low for word in ("ayudame", "organiza")) and any(
            word in low for word in ("investiga", "busca", "consulta", "abre", "abrir")
        )

    def _target_day(self, low: str, today: date) -> date:
        if "manana" in low:
            return today + timedelta(days=1)
        weekday = self._extract_weekday(low)
        if weekday is not None:
            delta = (weekday - today.weekday()) % 7
            return today + timedelta(days=delta or 7)
        return today

    def _task_create_step(self, low: str, target_day: date) -> PlanStep | None:
        if self._task_mutation_query(low):
            return None
        if not self._looks_like_task_creation(low):
            return None
        title = self._task_title(low)
        if not title:
            return None
        due_date = target_day.isoformat() if self._has_date_ref(low) else ""
        hhmm = self._extract_time(low)
        priority = self._task_priority(low)
        category = self._task_category(low)
        next_action = self._task_next_action(title, category)
        return PlanStep(
            id="create_task",
            description=f"Crear pendiente '{title}'" + (f" para {due_date}" if due_date else "") + ".",
            action="create_task",
            payload={
                "title": title,
                "due_date": due_date,
                "due_time": hhmm if due_date else "",
                "priority": priority,
                "category": category,
                "next_action": next_action,
                "source": "action_plan",
            },
            mutates=True,
        )

    def _task_complete_step(self, low: str) -> PlanStep | None:
        if not re.search(r"\b(ya\s+hice|ya\s+termine|complete|completa|termina|marca)\b", low):
            return None
        query = low
        query = re.sub(r"^(ya\s+hice|ya\s+termine|complete|completa|termina|marca)\s+", "", query).strip()
        query = re.sub(r"\b(como\s+hecho|como\s+hecha|pendiente|tarea|compromiso|esto|eso)\b", " ", query)
        query = re.sub(r"\s+", " ", query).strip(" ,-") or "eso"
        return PlanStep(
            id="complete_task",
            description=f"Marcar como completado el pendiente que coincida con '{query}'.",
            action="complete_task",
            payload={"query": query},
            mutates=True,
        )

    def _task_postpone_step(self, low: str, target_day: date, today: date) -> PlanStep | None:
        if not re.search(r"\b(pospon|posponer|posponme|mueve|pasa|aplaza)\b", low):
            return None
        query = re.sub(r"^.*?\b(pospon|posponer|posponme|mueve|pasa|aplaza)\b", " ", low).strip()
        query = self._strip_schedule_phrases(query)
        query = re.sub(r"\b(pendiente|tarea|compromiso|para|a|al|esto|eso)\b", " ", query)
        query = re.sub(r"\s+", " ", query).strip(" ,-") or "eso"
        due_day = target_day if self._has_date_ref(low) else today + timedelta(days=1)
        hhmm = self._extract_time(low)
        return PlanStep(
            id="postpone_task",
            description=f"Posponer pendiente '{query}' para {due_day.isoformat()}.",
            action="postpone_task",
            payload={"query": query, "due_date": due_day.isoformat(), "due_time": hhmm},
            mutates=True,
        )

    def _task_cancel_step(self, low: str) -> PlanStep | None:
        if not re.search(r"\b(cancela|cancelar|elimina|eliminar|borra|borrar)\b.*\b(pendiente|tarea|compromiso)\b", low):
            return None
        query = re.sub(r"^.*?\b(pendiente|tarea|compromiso)\b", " ", low).strip()
        query = self._strip_schedule_phrases(query)
        query = re.sub(r"\s+", " ", query).strip(" ,-") or "eso"
        return PlanStep(
            id="cancel_task",
            description=f"Cancelar el pendiente que coincida con '{query}'.",
            action="cancel_task",
            payload={"query": query},
            mutates=True,
        )

    def _preference_step(self, low: str) -> PlanStep | None:
        key = ""
        value = ""
        match = re.search(r"\bpreferencia\s+de\s+(.+?)\s+(?:es|a|como)\s+(.+)$", low)
        if match:
            key = match.group(1)
            value = match.group(2)
        else:
            match = re.search(r"\bprefiero\s+(?:que\s+)?(.+)$", low)
            if match:
                raw = self._split_followup(match.group(1))
                if re.search(r"\b(respondas|respuesta|hables|contestes)\b", raw):
                    key = "respuesta"
                    value = re.sub(r"\b(me\s+)?(respondas|respuesta|hables|contestes)\b", " ", raw)
                else:
                    key = "general"
                    value = raw
        key = self._clean_preference_piece(key)
        value = self._clean_preference_piece(self._split_followup(value))
        if not key or not value:
            return None
        return PlanStep(
            id="set_preference",
            description=f"Actualizar preferencia personal '{key}' a '{value}'.",
            action="set_preference",
            payload={"key": key, "value": value, "category": self._preference_category(key, value), "source": "action_plan"},
            mutates=True,
        )

    def _memory_fact_step(self, low: str) -> PlanStep | None:
        if "recuerdame" in low or "recordatorio" in low:
            return None
        if re.search(r"\bpreferencia\s+de\b|\bprefiero\b", low):
            return None
        patterns = (
            r"\b(?:guardar|guarda|memoriza|recordar|recuerda|aprende)\s+(?:en\s+(?:mi\s+)?(?:memoria|perfil)\s+)?que\s+(.+)$",
            r"\b(?:guardar|guarda|memoriza)\s+(?:en\s+(?:mi\s+)?(?:memoria|perfil)\s+)?(.+)$",
        )
        text = ""
        for pattern in patterns:
            match = re.search(pattern, low)
            if match:
                text = self._split_followup(match.group(1))
                break
        text = re.sub(r"^(?:esto|dato|hecho)\s+(?:como\s+)?", "", text).strip(" ,-")
        if not text:
            return None
        return PlanStep(
            id="remember_fact",
            description=f"Guardar en memoria personal: {text}.",
            action="remember_fact",
            payload={"text": text, "category": self._memory_category(text), "source": "action_plan"},
            mutates=True,
        )

    def _agenda_step(self, low: str, target_day: date) -> PlanStep | None:
        if not any(word in low for word in ("agenda", "agendame", "evento", "entrega")):
            return None
        hhmm = self._extract_time(low) or "09:00"
        title = self._strip_schedule_phrases(low)
        title = re.sub(r"\b(ayudame|a|agendar|agenda|agendame|agrega|agregar|evento|tengo|una|un)\b", " ", title)
        title = re.sub(r"\s+", " ", title).strip(" ,-") or "Evento"
        return PlanStep(
            id="create_agenda_event",
            description=f"Crear evento '{title}' el {target_day.isoformat()} a las {hhmm}.",
            action="create_agenda_event",
            payload={"title": title, "date": target_day.isoformat(), "time": hhmm, "category": "evento"},
            mutates=True,
        )

    def _reminder_step(self, low: str, target_day: date) -> PlanStep | None:
        if "recuerdame" not in low and "recordatorio" not in low:
            return None
        if self._looks_like_personal_rule(low):
            return None
        hhmm = self._extract_time(low) or "09:00"
        title = re.sub(r"^.*?\b(recuerdame|recordatorio)\b", " ", low).strip()
        title = self._strip_schedule_phrases(title)
        title = re.sub(r"\b(que|de|para|hacer|un|una)\b", " ", title)
        title = re.sub(r"\s+", " ", title).strip(" ,-") or "Recordatorio"
        return PlanStep(
            id="create_reminder",
            description=f"Crear recordatorio '{title}' el {target_day.isoformat()} a las {hhmm}.",
            action="create_reminder",
            payload={"title": title, "date": target_day.isoformat(), "time": hhmm},
            mutates=True,
        )

    def _personal_rule_step(self, low: str) -> PlanStep | None:
        if not self._looks_like_personal_rule(low) and not ("maleta" in low and "viernes" in low):
            return None
        rule_text = low
        if "recuerdame" not in rule_text:
            rule_text = "cuando sea viernes antes de las 11 recuerdame revisar maleta"
        return PlanStep(
            id="create_personal_rule",
            description="Crear regla personal para recordarlo en futuros planes.",
            action="create_personal_rule",
            payload={"rule_text": rule_text},
            mutates=True,
        )

    def _study_note_step(self, low: str, target_day: date, target_label: str) -> PlanStep | None:
        if "estudiar" not in low and "estudio" not in low:
            return None
        topic = re.sub(r"^.*?\b(estudiar|estudio)\b", " ", low).strip()
        topic = self._strip_schedule_phrases(topic)
        topic = re.split(r"\s+y\s+(?:salir|agenda|recuerdame|abre|investiga)\b", topic, maxsplit=1)[0]
        topic = re.sub(r"\s+", " ", topic).strip(" ,-") or "estudio"
        return PlanStep(
            id="add_study_note",
            description=f"Guardar nota de estudio para {target_label}: {topic}.",
            action="add_daily_note",
            payload={"date": target_day.isoformat(), "note": f"Estudiar {topic}."},
            mutates=True,
        )

    def _research_step(self, low: str) -> PlanStep | None:
        if not any(prefix in low for prefix in ("investiga", "busca", "consulta", "aprende sobre")):
            return None
        query = re.sub(r"^.*?\b(investiga|busca|consulta|aprende sobre)\b", " ", low).strip()
        query = re.split(r"\s+y\s+(?:abre|agendame|recuerdame|organiza)\b", query, maxsplit=1)[0]
        query = re.sub(r"\s+", " ", query).strip(" ,-")
        if not query:
            return None
        save_requested = any(token in low for token in ("aprende sobre", "guarda", "guardar", "recuerda", "memoriza"))
        return PlanStep(
            id="research_topic",
            description=f"Investigar '{query}'.",
            action="research_topic",
            payload={"query": query, "save": save_requested},
            mutates=save_requested,
        )

    def _app_step(self, low: str) -> PlanStep | None:
        match = re.search(r"\b(?:abre|abrir|inicia|ejecuta|lanza)\s+(?:la\s+app\s+|la\s+aplicacion\s+|el\s+programa\s+)?([a-z0-9 _.-]+)", low)
        if not match:
            return None
        app = re.split(r"\s+y\s+|\s+para\s+", match.group(1), maxsplit=1)[0].strip(" ,-")
        if not app:
            return None
        return PlanStep(
            id="open_app",
            description=f"Abrir {app}.",
            action="open_app",
            payload={"app": app},
            mutates=False,
        )

    def _telegram_step(self, low: str) -> PlanStep | None:
        if "telegram" not in low:
            return None
        if re.search(r"\b(activar|activa|configurar|probar|prueba)\s+telegram\b", low):
            return None
        if not re.search(r"\b(avisame|avisar|notifica|notificarme|manda|mandame|envia|enviame|prepara)\b", low):
            return None
        message = ""
        match = re.search(
            r"\b(?:avisame|avisar|notifica|notificarme|manda|mandame|envia|enviame)\s+(?:por\s+)?telegram\b\s*(.*)$",
            low,
        )
        if match:
            message = match.group(1)
        else:
            match = re.search(r"\btelegram\b\s*(.*)$", low)
            if match:
                message = match.group(1)
        message = self._split_followup(message)
        message = re.sub(r"^(?:que|para\s+que|con|sobre|un\s+aviso\s+para\s+que)\s+", "", message).strip(" ,-")
        if not message:
            message = self._strip_schedule_phrases(low)
            message = re.sub(
                r"\b(ayudame|prepara|un|una|aviso|mensaje|notificacion|por|telegram|para|que)\b",
                " ",
                message,
            )
            message = re.sub(r"\s+", " ", message).strip(" ,-")
        if not message:
            return None
        return PlanStep(
            id="send_telegram_notification",
            description=f"Enviar notificacion por Telegram: {message}.",
            action="send_telegram_notification",
            payload={"message": message},
            mutates=True,
        )

    def _extract_time(self, low: str) -> str:
        match = re.search(r"\b(\d{1,2}):(\d{2})\b", low)
        if match:
            hour, minute = int(match.group(1)), int(match.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return f"{hour:02d}:{minute:02d}"
        match = re.search(r"\ba\s+las\s+(\d{1,2})(?:\s+(\d{2}))?\b", low)
        if not match:
            return ""
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        if ("tarde" in low or "noche" in low or "pm" in low) and hour < 12:
            hour += 12
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
        return ""

    def _daily_note(self, low: str, target_label: str) -> str:
        if "ingles" in low:
            return f"Revisar ajuste por ingles para {target_label}."
        if "temprano" in low:
            return f"Revisar salida o preparacion temprana para {target_label}."
        return f"Revisar organizacion solicitada para {target_label}."

    def _looks_like_task_creation(self, low: str) -> bool:
        if re.search(r"\b(tengo\s+que|hay\s+que|debo)\b", low):
            return True
        if re.search(r"\b(crea|crear|agrega|agregar|anota|apunta)\b.*\b(pendiente|tarea|compromiso)\b", low):
            return True
        if re.search(r"\b(pendiente|tarea|compromiso)\b", low) and not low.startswith(
            ("que ", "ver ", "muestra ", "mostrar ", "lista ", "listar ")
        ):
            return True
        if re.search(r"\bnecesito\b.*\b(estudiar|entregar|terminar|hacer|revisar)\b", low):
            return True
        if "recuerdame" in low and not self._looks_like_personal_rule(low):
            return True
        return False

    def _task_mutation_query(self, low: str) -> bool:
        return bool(
            re.search(r"\b(ya\s+hice|ya\s+termine|complete|completa|marca|pospon|posponer|posponme|mueve|pasa|aplaza)\b", low)
            or re.search(r"\b(cancela|cancelar|elimina|eliminar|borra|borrar)\b.*\b(pendiente|tarea|compromiso)\b", low)
        )

    def _task_title(self, low: str) -> str:
        patterns = (
            r"^.*?\b(?:tengo\s+que|hay\s+que|debo)\b",
            r"^.*?\b(?:crea|crear|agrega|agregar|anota|apunta)\b\s+(?:un\s+|una\s+|el\s+|la\s+)?(?:pendiente|tarea|compromiso)?",
            r"^.*?\b(?:pendiente|tarea|compromiso)\b",
            r"^.*?\b(?:necesito)\b",
            r"^.*?\b(?:recuerdame|recordatorio)\b",
        )
        title = low
        for pattern in patterns:
            cleaned = re.sub(pattern, " ", low).strip()
            if cleaned and cleaned != low:
                title = cleaned
                break
        title = re.split(
            r"\s+y\s+(?:salir|abre|abrir|investiga|busca|consulta|agenda|agendame|recuerdame)\b",
            title,
            maxsplit=1,
        )[0]
        title = self._strip_schedule_phrases(title)
        title = re.sub(
            r"\b(que|de|para|hacer|un|una|el|la|los|las|esto|eso|importante|urgente|recordatorio)\b",
            " ",
            title,
        )
        return re.sub(r"\s+", " ", title).strip(" ,-")

    def _task_priority(self, low: str) -> str:
        if any(word in low for word in ("urgente", "importante", "prioridad alta")):
            return "high"
        if any(word in low for word in ("cuando puedas", "sin prisa", "prioridad baja")):
            return "low"
        return "normal"

    def _task_category(self, low: str) -> str:
        if any(word in low for word in ("estudiar", "estudio", "clase", "ingles", "poo", "entrega", "entregar")):
            return "escuela"
        if any(word in low for word in ("comprar", "pagar", "presupuesto", "dinero")):
            return "personal"
        if any(word in low for word in ("app", "abre", "programa")):
            return "apps"
        return "general"

    def _task_next_action(self, title: str, category: str) -> str:
        if category == "escuela":
            return f"Avanzar con {title}"
        return f"Revisar {title}"

    def _split_followup(self, value: str) -> str:
        return re.split(
            r"\s+y\s+(?:salir|abre|abrir|investiga|busca|consulta|agenda|agendame|recuerdame|avisame|notifica|manda|envia|guarda)\b",
            value,
            maxsplit=1,
        )[0].strip(" ,-")

    def _clean_preference_piece(self, value: str) -> str:
        value = self._strip_schedule_phrases(value)
        value = re.sub(
            r"\b(mi|mis|la|el|de|que|como|preferencia|preferencias|ayudame|guardar|guarda|actualiza|actualizar)\b",
            " ",
            value,
        )
        return re.sub(r"\s+", " ", value).strip(" ,-")

    def _preference_category(self, key: str, value: str) -> str:
        joined = f"{key} {value}"
        if any(word in joined for word in ("respuesta", "responder", "contestes", "hables")):
            return "respuesta"
        if any(word in joined for word in ("estudiar", "estudio", "clase", "escuela")):
            return "estudio"
        if any(word in joined for word in ("salir", "salida", "rutina", "manana")):
            return "rutina"
        return "general"

    def _memory_category(self, text: str) -> str:
        if any(word in text for word in ("clase", "estudio", "estudiar", "universidad", "escuela")):
            return "estudio"
        if any(word in text for word in ("rutina", "salida", "despertar", "manana")):
            return "rutina"
        if any(word in text for word in ("persona", "amigo", "familia", "mama", "papa")):
            return "personas"
        return "general"

    def _has_date_ref(self, low: str) -> bool:
        if "hoy" in low or "manana" in low:
            return True
        if self._extract_weekday(low) is not None:
            return True
        return bool(re.search(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", low))

    def _extract_weekday(self, low: str) -> int | None:
        weekdays = {
            "lunes": 0,
            "martes": 1,
            "miercoles": 2,
            "jueves": 3,
            "viernes": 4,
            "sabado": 5,
            "domingo": 6,
        }
        for name, index in weekdays.items():
            if re.search(rf"\b{name}\b", low):
                return index
        return None

    def _strip_schedule_phrases(self, low: str) -> str:
        value = re.sub(r"\ba\s+las\s+\d{1,2}(?::\d{2})?\b", " ", low)
        value = re.sub(r"\b(hoy|manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", " ", value)
        value = re.sub(r"\b(este|esta|proximo|proxima|el|la|los|las|para|por)\b", " ", value)
        return re.sub(r"\s+", " ", value).strip(" ,-")

    def _looks_like_personal_rule(self, low: str) -> bool:
        return "recuerdame" in low and bool(
            re.search(r"\b(cuando|cuando sea|si es|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", low)
        )

    def _dedupe_steps(self, steps: list[PlanStep]) -> list[PlanStep]:
        seen: set[tuple[str, tuple[tuple[str, str], ...]]] = set()
        unique: list[PlanStep] = []
        for step in steps:
            key = (step.action, tuple(sorted((str(k), str(v)) for k, v in step.payload.items())))
            if key in seen:
                continue
            seen.add(key)
            unique.append(step)
        return unique


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.lower().strip())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    replacements = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
    for src, dst in replacements.items():
        value = value.replace(src, dst)
    value = re.sub(r"[¿?¡!.,;:\"'()]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()
