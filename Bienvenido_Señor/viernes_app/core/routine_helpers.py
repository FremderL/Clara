"""Helpers para rutinas semanales con soporte por día independiente."""
from __future__ import annotations

import copy
import re
import uuid
from typing import Any

WEEKDAY_KEYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

WEEKDAY_LABELS = {
    "monday": "Lunes",
    "tuesday": "Martes",
    "wednesday": "Miercoles",
    "thursday": "Jueves",
    "friday": "Viernes",
    "saturday": "Sabado",
    "sunday": "Domingo",
}

_LEGACY_UNIVERSITY_KEY = "default_university_day"

_HHMM_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


def is_valid_hhmm(value: str) -> bool:
    return bool(_HHMM_RE.match(str(value or "").strip()))


def migrate_legacy_routines(routines: dict[str, Any]) -> dict[str, Any]:
    """Convierte default_university_day fusionado en rutinas tuesday/wednesday."""
    if not isinstance(routines, dict):
        return {}
    result = copy.deepcopy(routines)
    legacy = result.get(_LEGACY_UNIVERSITY_KEY)
    if not isinstance(legacy, dict):
        return result
    enabled_days = {
        str(day).strip().lower()
        for day in legacy.get("enabled_weekdays", ["tuesday", "wednesday"])
        if str(day).strip()
    }
    for day in ("tuesday", "wednesday"):
        if day in result and isinstance(result.get(day), dict) and result[day].get("reminders"):
            continue
        day_cfg = copy.deepcopy(legacy)
        day_cfg.pop("enabled_weekdays", None)
        day_cfg["enabled"] = day in enabled_days if enabled_days else True
        result[day] = day_cfg
    return result


def resolve_day_cfg(routines: dict[str, Any], day_key: str) -> dict[str, Any]:
    """Obtiene la configuración de rutina para un día, con fallback legacy."""
    if not isinstance(routines, dict):
        return {}
    migrated = migrate_legacy_routines(routines)
    direct = migrated.get(day_key)
    if isinstance(direct, dict):
        return direct
    if day_key in {"tuesday", "wednesday"}:
        legacy = migrated.get(_LEGACY_UNIVERSITY_KEY, {})
        if isinstance(legacy, dict):
            enabled_days = set(legacy.get("enabled_weekdays", ["tuesday", "wednesday"]))
            if day_key in enabled_days or legacy.get("enabled", True) is not False:
                cfg = copy.deepcopy(legacy)
                cfg.pop("enabled_weekdays", None)
                return cfg
    return {}


def day_routine_enabled(routines: dict[str, Any], day_key: str) -> bool:
    cfg = resolve_day_cfg(routines, day_key)
    if not cfg:
        return False
    if day_key in {"tuesday", "wednesday"}:
        legacy = routines.get(_LEGACY_UNIVERSITY_KEY, {})
        if isinstance(legacy, dict) and "enabled_weekdays" in legacy:
            return day_key in set(legacy.get("enabled_weekdays", []))
    return cfg.get("enabled", True) is not False


def routine_scope_for_day(day_key: str) -> str:
    """Clave de scope usada en event_id y comandos de voz."""
    if day_key in WEEKDAY_KEYS:
        return day_key
    return _LEGACY_UNIVERSITY_KEY


def normalize_reminders(reminders: Any) -> list[dict[str, str]]:
    if not isinstance(reminders, list):
        return []
    normalized: list[dict[str, str]] = []
    for index, item in enumerate(reminders):
        if not isinstance(item, dict):
            continue
        reminder_id = str(item.get("id", "") or "").strip() or f"reminder_{index + 1}"
        time_value = str(item.get("time", "") or "").strip()
        message = str(item.get("message", "") or "")
        normalized.append({"id": reminder_id, "time": time_value, "message": message})
    return normalized


def normalize_bath_followup(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    repeat_raw = value.get("repeat_minutes", 20)
    try:
        repeat_minutes = max(1, int(repeat_raw))
    except (TypeError, ValueError):
        repeat_minutes = 20
    return {
        "start": str(value.get("start", "") or "").strip(),
        "stop": str(value.get("stop", "") or "").strip(),
        "repeat_minutes": repeat_minutes,
        "message": str(value.get("message", "") or ""),
    }


def normalize_day_payload(day_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Normaliza el payload del editor para un día."""
    cfg: dict[str, Any] = {
        "enabled": bool(payload.get("enabled", True)),
        "reminders": normalize_reminders(payload.get("reminders", [])),
    }
    bath = normalize_bath_followup(payload.get("bath_followup", {}))
    if any(bath.get(key) for key in ("start", "stop", "message")):
        cfg["bath_followup"] = bath

    if day_key == "monday":
        cfg["skip_morning_routine"] = bool(payload.get("skip_morning_routine", True))
        cfg["skip_recurring_reminders"] = bool(payload.get("skip_recurring_reminders", True))
        cfg["attendance_on_arrival"] = bool(payload.get("attendance_on_arrival", True))
        leave_time = str(payload.get("leave_time", "") or "").strip()
        if leave_time:
            cfg["leave_time"] = leave_time
        arrival = str(payload.get("arrival_message", "") or "")
        if arrival:
            cfg["arrival_message"] = arrival
        window = payload.get("expected_arrival_window", [])
        if isinstance(window, list) and window:
            cfg["expected_arrival_window"] = [str(item).strip() for item in window if str(item).strip()]

    if day_key == "thursday":
        leave_time = str(payload.get("leave_time", "") or "").strip()
        if leave_time:
            cfg["leave_time"] = leave_time

    if day_key == "friday":
        leave_time = str(payload.get("leave_time", "") or "").strip()
        if leave_time:
            cfg["leave_time"] = leave_time
        for key in ("packing_time", "packing_message", "chores_time", "chores_message", "stop_all_after"):
            value = str(payload.get(key, "") or "").strip()
            if value:
                cfg[key] = value

    return cfg


def new_reminder_id() -> str:
    return f"custom_{uuid.uuid4().hex[:8]}"


def validate_day_payload(day_key: str, payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    label = WEEKDAY_LABELS.get(day_key, day_key)
    for item in normalize_reminders(payload.get("reminders", [])):
        hhmm = item.get("time", "")
        if hhmm and not is_valid_hhmm(hhmm):
            errors.append(f"{label}/{item.get('id', 'recordatorio')}: hora invalida.")
    bath = normalize_bath_followup(payload.get("bath_followup", {}))
    for key in ("start", "stop"):
        value = bath.get(key, "")
        if value and not is_valid_hhmm(value):
            errors.append(f"{label}/bano {key}: hora invalida.")
    for key in ("leave_time", "packing_time", "chores_time", "stop_all_after"):
        value = str(payload.get(key, "") or "").strip()
        if value and not is_valid_hhmm(value):
            errors.append(f"{label}/{key}: hora invalida.")
    window = payload.get("expected_arrival_window", [])
    if isinstance(window, list):
        for item in window:
            value = str(item or "").strip()
            if value and not is_valid_hhmm(value):
                errors.append(f"{label}/ventana llegada: hora invalida.")
    return errors
