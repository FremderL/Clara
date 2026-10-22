from __future__ import annotations

from datetime import date
from typing import Any, Callable


def classes_for_day(
    state: dict[str, Any],
    config: dict[str, Any],
    target_day: date,
    iso_day_fn: Callable[[date], str],
    weekday_key_fn: Callable[[date], str],
) -> list[str]:
    explicit = state.get("classes_by_date", {}).get(iso_day_fn(target_day), [])
    if explicit:
        return list(explicit)
    weekly = config.setdefault("class_schedule", {})
    return list(weekly.get(weekday_key_fn(target_day), []))


def classes_summary_for_day(
    state: dict[str, Any],
    config: dict[str, Any],
    target_day: date,
    iso_day_fn: Callable[[date], str],
    weekday_key_fn: Callable[[date], str],
) -> str:
    classes = classes_for_day(state, config, target_day, iso_day_fn, weekday_key_fn)
    if not classes:
        return "No hay clases registradas para hoy."
    return "Clases de hoy: " + ", ".join(classes)


def classes_overview(
    state: dict[str, Any],
    config: dict[str, Any],
    weekday_labels: dict[str, str],
) -> str:
    parts: list[str] = []
    for key in ["monday", "tuesday", "wednesday", "thursday", "friday"]:
        classes = list(config.get("class_schedule", {}).get(key, []))
        if classes:
            parts.append(f"{weekday_labels[key]}: {', '.join(classes)}")
    for day, classes in sorted(state.get("classes_by_date", {}).items()):
        if classes:
            parts.append(f"{day}: {', '.join(classes)}")
    return "Clases registradas: " + " | ".join(parts) if parts else "No hay clases registradas."
