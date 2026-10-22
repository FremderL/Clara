from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.lower())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


@dataclass(frozen=True)
class BrainDecision:
    intent: str
    confidence: float
    reason: str


class ViernesBrain:
    """Capa ligera de razonamiento local para decidir antes de acudir a Ollama."""

    _examples: dict[str, tuple[str, ...]] = {
        "agenda": (
            "que tengo hoy",
            "revisa mi agenda",
            "que sigue",
            "mis eventos",
            "pendientes de hoy",
        ),
        "morning_brief": (
            "rutina de la manana",
            "informe matutino",
            "briefing",
            "despertar",
            "como va mi dia",
        ),
        "news": (
            "noticias",
            "titulares",
            "ultimas noticias",
            "que esta pasando",
            "novedades",
        ),
        "weather": (
            "clima",
            "temperatura",
            "va a llover",
            "pronostico",
        ),
        "classes": (
            "clases de hoy",
            "horario de clases",
            "materias",
            "que clase tengo",
            "que clases me tocan",
        ),
        "budget": (
            "presupuesto",
            "balance",
            "gastos",
            "dinero",
            "cuanto tengo",
        ),
        "apps": (
            "abre",
            "abrir aplicacion",
            "ejecuta",
            "inicia chrome",
            "spotify",
            "pon youtube",
            "lanza calculadora",
            "abre discord",
        ),
        "math": (
            "calcula",
            "cuanto es",
            "resuelve esta operacion",
            "haz la cuenta",
        ),
        "research": (
            "investiga",
            "busca en internet",
            "consulta",
            "aprende sobre",
        ),
        "habits": (
            "mis habitos",
            "recomendaciones de habitos",
            "corrige mis habitos",
            "aprende de mis habitos",
            "actualiza habitos",
        ),
        "wake": (
            "autoinicio",
            "despertar automatico",
            "modo residente",
            "verificar despertar",
            "tarea programada",
        ),
    }

    def __init__(self) -> None:
        self._vectors = {
            intent: [set(_normalize(example).split()) for example in examples]
            for intent, examples in self._examples.items()
        }

    def classify(self, text: str) -> BrainDecision | None:
        tokens = set(_normalize(text).split())
        if not tokens:
            return None
        if {"horario", "salida"} <= tokens or ({"hora", "salir"} <= tokens):
            return BrainDecision("routine", 0.9, "consulta o cambio de salida")
        best_intent = ""
        best_score = 0.0
        best_reason = ""
        for intent, examples in self._vectors.items():
            for example_tokens in examples:
                overlap = len(tokens & example_tokens)
                if not overlap:
                    continue
                coverage = overlap / max(1, len(example_tokens))
                precision = overlap / max(1, len(tokens))
                score = (coverage * 0.65) + (precision * 0.35)
                if example_tokens <= tokens:
                    score += 0.12
                if score > best_score:
                    best_intent = intent
                    best_score = min(score, 1.0)
                    best_reason = "coincidencia contextual"
        if best_score < 0.58:
            return None
        return BrainDecision(best_intent, round(best_score, 2), best_reason)

    def daily_focus(
        self,
        now: datetime,
        agenda_items: list[dict[str, Any]],
        classes: list[str],
        daily: dict[str, Any],
    ) -> list[str]:
        suggestions: list[str] = []
        if agenda_items:
            next_item = agenda_items[0]
            suggestions.append(f"Siguiente agenda: {next_item.get('time', '--:--')} {next_item.get('title', 'Evento')}")
        if classes:
            suggestions.append("Clases: " + ", ".join(classes[:3]))
        if not daily.get("bath_done") and now.hour >= 17:
            suggestions.append("Pendiente: registrar bano cuando este hecho")
        if now.weekday() == 4 and now.hour < 16:
            suggestions.append("Viernes: preparar regreso, maleta y pendientes del lunes")
        if not suggestions:
            suggestions.append("Sin urgencias detectadas; conviene revisar agenda y presupuesto")
        return suggestions[:4]

    def context_line(
        self,
        now: datetime,
        agenda_items: list[dict[str, Any]],
        classes: list[str],
        daily: dict[str, Any],
    ) -> str:
        focus = self.daily_focus(now, agenda_items, classes, daily)
        return "Foco operativo: " + " | ".join(focus)
