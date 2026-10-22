from __future__ import annotations

from typing import Any


def sort_agenda_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = list(items)
    ordered.sort(key=lambda x: (str(x.get("date", "")), str(x.get("time", "")), str(x.get("title", ""))))
    return ordered


def full_agenda_summary(items: list[dict[str, Any]], weekday_labels: dict[str, str]) -> str:
    if not items:
        return "No hay eventos en la agenda."

    parts = []
    for item in sort_agenda_items(items):
        recurring = str(item.get("recurring", "") or "")
        paused = " pausado" if item.get("paused") else ""
        if recurring == "daily":
            when = f"todos los dias a las {item.get('time', '--:--')}"
        elif recurring == "weekly":
            when = f"cada {weekday_labels.get(str(item.get('weekday', '')), 'semana')} a las {item.get('time', '--:--')}"
        elif recurring == "weekly_multi":
            names = [weekday_labels.get(day, day) for day in item.get("weekdays", [])]
            when = f"cada {' y '.join(names)} a las {item.get('time', '--:--')}"
        else:
            when = f"{item.get('date', 'sin fecha')} a las {item.get('time', '--:--')}"
        parts.append(f"{item.get('title', 'Evento')} - {when}{paused}")
    return "Agenda completa: " + " | ".join(parts)
