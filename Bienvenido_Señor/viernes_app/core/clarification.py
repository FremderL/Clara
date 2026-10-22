from __future__ import annotations

import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from viernes_app.core.action_planner import ActionPlan, ActionRisk, PlanStep


@dataclass(frozen=True)
class ClarificationOption:
    id: str
    label: str
    description: str
    step: PlanStep

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "step": self.step.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClarificationOption":
        return cls(
            id=str(data.get("id") or ""),
            label=str(data.get("label") or ""),
            description=str(data.get("description") or ""),
            step=PlanStep.from_dict(dict(data.get("step") or {})),
        )


@dataclass(frozen=True)
class ClarificationRequest:
    id: str
    original_text: str
    subject: str
    target_date: str
    target_time: str
    options: list[ClarificationOption]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "original_text": self.original_text,
            "subject": self.subject,
            "target_date": self.target_date,
            "target_time": self.target_time,
            "created_at": self.created_at,
            "options": [option.to_dict() for option in self.options],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClarificationRequest":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:10]),
            original_text=str(data.get("original_text") or ""),
            subject=str(data.get("subject") or "asunto"),
            target_date=str(data.get("target_date") or ""),
            target_time=str(data.get("target_time") or ""),
            created_at=str(data.get("created_at") or datetime.now().isoformat(timespec="seconds")),
            options=[
                ClarificationOption.from_dict(item)
                for item in list(data.get("options", []))
                if isinstance(item, dict)
            ],
        )

    def prompt(self) -> str:
        option_text = " ".join(
            f"{index}. {option.label}: {option.description}"
            for index, option in enumerate(self.options, start=1)
        )
        return f"Entendi el asunto '{self.subject}', pero necesito una decision: {option_text}"


class ClarificationEngine:
    """Convierte frases utiles pero ambiguas en opciones explicitas."""

    def evaluate(self, text: str, now: datetime) -> ClarificationRequest | None:
        low = _normalize(text)
        if not low or self._has_explicit_action(low) or not self._looks_ambiguous(low):
            return None
        target_day = self._target_day(low, now.date())
        if target_day is None:
            return None
        subject = self._subject(low)
        if not subject:
            return None
        target_date = target_day.isoformat()
        target_time = self._extract_time(low)
        priority = "high" if any(word in low for word in ("importante", "urgente", "prioridad alta")) else "normal"
        category = self._category(low)
        options = self._options(subject, target_date, target_time, priority, category)
        return ClarificationRequest(
            id=uuid.uuid4().hex[:10],
            original_text=text.strip(),
            subject=subject,
            target_date=target_date,
            target_time=target_time,
            options=options,
            created_at=now.isoformat(timespec="seconds"),
        )

    def plan_from_choice(self, request: ClarificationRequest, choice: str, now: datetime) -> ActionPlan | None:
        option = self.option_from_choice(request, choice)
        if option is None:
            return None
        steps = [
            PlanStep(
                id="review_context",
                description=f"Revisar calendario operativo de {request.target_date}.",
                action="show_activity_calendar",
                payload={"date": request.target_date},
                mutates=False,
            ),
            option.step,
        ]
        return ActionPlan(
            id=uuid.uuid4().hex[:10],
            summary=f"Plan aclarado para '{request.subject}'.",
            risk=ActionRisk.MEDIUM,
            steps=steps,
            requires_confirmation=True,
            created_at=now.isoformat(timespec="seconds"),
            intent="clarified_action",
        )

    def option_from_choice(self, request: ClarificationRequest, choice: str) -> ClarificationOption | None:
        low = _normalize(choice)
        if not low:
            return None
        if low.isdigit():
            index = int(low) - 1
            if 0 <= index < len(request.options):
                return request.options[index]
        aliases = {
            "task": {"pendiente", "tarea", "compromiso", "lista", "1", "uno"},
            "agenda": {"agenda", "evento", "calendario", "2", "dos"},
            "reminder": {"recordatorio", "recuerdame", "alarma", "3", "tres"},
            "note": {"nota", "nota diaria", "apunte", "4", "cuatro"},
        }
        for option in request.options:
            terms = aliases.get(option.id, {option.id})
            if low in terms or any(term in low for term in terms):
                return option
        return None

    def _options(
        self,
        subject: str,
        target_date: str,
        target_time: str,
        priority: str,
        category: str,
    ) -> list[ClarificationOption]:
        agenda_time = target_time or "09:00"
        note = f"Revisar {subject}."
        return [
            ClarificationOption(
                id="task",
                label="pendiente",
                description="guardarlo como pendiente con seguimiento",
                step=PlanStep(
                    id="create_task",
                    description=f"Crear pendiente '{subject}' para {target_date}.",
                    action="create_task",
                    payload={
                        "title": subject,
                        "due_date": target_date,
                        "due_time": target_time,
                        "priority": priority,
                        "category": category,
                        "next_action": f"Revisar {subject}",
                        "source": "clarification",
                    },
                    mutates=True,
                ),
            ),
            ClarificationOption(
                id="agenda",
                label="agenda",
                description=f"agendarlo como evento a las {agenda_time}",
                step=PlanStep(
                    id="create_agenda_event",
                    description=f"Crear evento '{subject}' el {target_date} a las {agenda_time}.",
                    action="create_agenda_event",
                    payload={"title": subject, "date": target_date, "time": agenda_time, "category": "evento"},
                    mutates=True,
                ),
            ),
            ClarificationOption(
                id="reminder",
                label="recordatorio",
                description=f"recordarlo a las {agenda_time}",
                step=PlanStep(
                    id="create_reminder",
                    description=f"Crear recordatorio '{subject}' el {target_date} a las {agenda_time}.",
                    action="create_reminder",
                    payload={"title": subject, "date": target_date, "time": agenda_time},
                    mutates=True,
                ),
            ),
            ClarificationOption(
                id="note",
                label="nota",
                description="dejarlo como nota diaria sin hora",
                step=PlanStep(
                    id="add_daily_note",
                    description=f"Guardar nota diaria sobre '{subject}' para {target_date}.",
                    action="add_daily_note",
                    payload={"date": target_date, "note": note},
                    mutates=True,
                ),
            ),
        ]

    def _looks_ambiguous(self, low: str) -> bool:
        if not self._has_date_ref(low):
            return False
        domain_words = (
            "ingles",
            "poo",
            "clase",
            "clases",
            "entrega",
            "examen",
            "tarea",
            "proyecto",
            "trabajo",
            "reunion",
            "cita",
            "importante",
            "pendiente",
        )
        if not any(word in low for word in domain_words):
            return False
        return bool(re.search(r"\b(tengo|hay|me toca|se viene|algo|lo de)\b", low))

    def _has_explicit_action(self, low: str) -> bool:
        return bool(
            re.search(
                r"\b(tengo\s+que|hay\s+que|debo|recuerdame|agenda|agendame|agrega|agregar|crea|crear|anota|apunta|pospon|cancela|ya\s+hice|ya\s+termine)\b",
                low,
            )
        )

    def _target_day(self, low: str, today: date) -> date | None:
        if "hoy" in low:
            return today
        if "manana" in low:
            return today + timedelta(days=1)
        weekday = self._extract_weekday(low)
        if weekday is not None:
            delta = (weekday - today.weekday()) % 7
            return today + timedelta(days=delta or 7)
        return None

    def _subject(self, low: str) -> str:
        value = re.sub(r"\ba\s+las\s+\d{1,2}(?::\d{2})?\b", " ", low)
        value = re.sub(r"\b(hoy|manana|lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", " ", value)
        value = re.sub(r"\b(tengo|hay|me toca|se viene|para|el|la|los|las|un|una)\b", " ", value)
        value = re.sub(r"\s+", " ", value).strip(" ,-")
        return value[:120] or "asunto"

    def _category(self, low: str) -> str:
        if any(word in low for word in ("ingles", "poo", "clase", "clases", "entrega", "examen", "tarea", "proyecto")):
            return "escuela"
        if any(word in low for word in ("reunion", "trabajo")):
            return "trabajo"
        return "general"

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
        if ("pm" in low or "tarde" in low or "noche" in low) and hour < 12:
            hour += 12
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
        return ""

    def _has_date_ref(self, low: str) -> bool:
        return bool(
            "hoy" in low
            or "manana" in low
            or self._extract_weekday(low) is not None
            or re.search(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b", low)
        )

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


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.lower().strip())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[¿?¡!.,;:\"'()]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()
