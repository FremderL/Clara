from __future__ import annotations

import copy
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from viernes_app.paths import CONFIG_PATH, RUNTIME_DIR


Validator = Callable[[Any], str | None]


@dataclass(frozen=True)
class ConfigField:
    path: str
    value_type: type | tuple[type, ...]
    default: Any
    label: str
    validator: Validator | None = None

    @property
    def parts(self) -> tuple[str, ...]:
        return tuple(part for part in self.path.split(".") if part)


@dataclass(frozen=True)
class ConfigValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    normalized: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "normalized": copy.deepcopy(self.normalized),
        }


DEFAULT_CONFIG: dict[str, Any] = {
    "assistant_name": "Viernes",
    "timezone": "America/Mexico_City",
    "voice_enabled": True,
    "push_to_talk_hotkey": "left alt",
    "habit_monitor_timeout_seconds": 600,
    "tts_type": "edge",
    "tts_rate": 165,
    "event_grace_minutes": 12,
    "scheduler_stop_pause_minutes": 10,
    "scheduler_duplicate_window_minutes": 15,
    "ai_enabled": True,
    "ai_base_url": "http://localhost:11434",
    "ai_model": "llama3.2",
    "ui": {"mode": "classic"},
    "voice_profile": "default",
    "wake_word": "viernes",
    "security": {
        "user_level": 1,
        "allowed_roots": [],
        "allowed_scripts": [],
        "password_hash": "",
    },
    "plugins": {
        "enabled": True,
        "enabled_plugins": [],
        "disabled": [],
    },
    "automation": {
        "startup_enabled": False,
        "morning_wake_time": "07:30",
        "auto_login_warning_acknowledged": False,
    },
    "morning_wake_enabled": False,
    "ambient_companion": {
        "enabled": True,
        "interval_minutes": 90,
        "wake_time": "07:30",
        "sleep_time": "22:30",
        "messages": [],
    },
    "conversation": {
        "proactive_topics_enabled": True,
        "small_talk": [],
        "facts": [],
        "tips": [],
        "jokes": [],
        "quotes": [],
    },
    "proactivity": {
        "enabled": True,
        "mode": "conservative",
        "interval_minutes": 120,
        "lookahead_minutes": 120,
        "max_per_tick": 1,
    },
    "news_preferences": {"preferred_topic": "world"},
    "default_city": "Colima, Colima, Mexico",
    "weather_lat": 19.2454,
    "weather_lon": -103.7246,
    "class_schedule": {},
    "weekly_routines": {},
    "quick_actions": [],
    "telegram": {"enabled": False, "token": "", "chat_id": ""},
    "analysis": {
        "enabled": True,
        "save_reports": True,
        "allow_web_research": True,
        "max_rows": 20,
        "chart_backend": "matplotlib",
    },
    "analysis_beta": {
        "enabled": True,
        "save_reports": True,
        "allow_web_research": True,
        "max_rows": 20,
        "chart_backend": "matplotlib",
    },
    "remote_control": {
        "enabled": False,
        "allowed_chat_ids": [],
        "owner_chat_ids": [],
        "trusted_chat_ids": [],
        "read_only_chat_ids": [],
        "require_confirmation": True,
        "send_artifacts": True,
        "history_limit": 100,
        "poll_interval_seconds": 5,
        "drop_pending_on_start": True,
        "blocked_intents": ["shutdown", "restart", "suspend", "delete", "cleanup_past_events"],
    },
    "remote_calls": {"enabled": False},
    "personal_activity": {
        "enabled": False,
        "privacy_mode": "app_category",
        "poll_interval_seconds": 60,
        "retention": {
            "raw_days": 14,
            "session_days": 60,
            "aggregate_days": 365,
        },
    },
    "wol_mac": "",
}


def _is_hhmm(value: Any) -> bool:
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}", value.strip()):
        return False
    hour, minute = [int(part) for part in value.split(":", 1)]
    return 0 <= hour <= 23 and 0 <= minute <= 59


def _validate_hhmm(value: Any) -> str | None:
    return None if _is_hhmm(value) else "debe usar formato HH:MM"


def _validate_positive_int(value: Any) -> str | None:
    return None if isinstance(value, int) and value > 0 else "debe ser un entero positivo"


def _validate_tts_rate(value: Any) -> str | None:
    return None if isinstance(value, int) and 80 <= value <= 260 else "debe estar entre 80 y 260"


def _validate_lat(value: Any) -> str | None:
    return None if isinstance(value, (int, float)) and -90 <= float(value) <= 90 else "debe estar entre -90 y 90"


def _validate_lon(value: Any) -> str | None:
    return None if isinstance(value, (int, float)) and -180 <= float(value) <= 180 else "debe estar entre -180 y 180"


def _validate_proactive_mode(value: Any) -> str | None:
    return None if value in {"conservative", "normal", "active", "off"} else "debe ser conservative, normal, active u off"


def _validate_chart_backend(value: Any) -> str | None:
    return None if value in {"matplotlib", "auto"} else "debe ser matplotlib o auto"


def _validate_ui_mode(value: Any) -> str | None:
    return None if value in {"classic", "modern"} else "debe ser classic o modern"


def _validate_security_level(value: Any) -> str | None:
    return None if isinstance(value, int) and 0 <= value <= 3 else "debe estar entre 0 y 3"


def _validate_privacy_mode(value: Any) -> str | None:
    return None if value in {"app_category"} else "debe ser app_category"


FIELDS: tuple[ConfigField, ...] = (
    ConfigField("assistant_name", str, "Viernes", "Nombre del asistente"),
    ConfigField("timezone", str, "America/Mexico_City", "Zona horaria"),
    ConfigField("default_city", str, "Colima, Colima, Mexico", "Ciudad"),
    ConfigField("weather_lat", (int, float), 19.2454, "Latitud", _validate_lat),
    ConfigField("weather_lon", (int, float), -103.7246, "Longitud", _validate_lon),
    ConfigField("event_grace_minutes", int, 12, "Ventana de recordatorios", _validate_positive_int),
    ConfigField("scheduler_stop_pause_minutes", int, 10, "Pausa al detener scheduler", _validate_positive_int),
    ConfigField("scheduler_duplicate_window_minutes", int, 15, "Ventana anti-duplicados scheduler", _validate_positive_int),
    ConfigField("voice_enabled", bool, True, "Voz activa"),
    ConfigField("tts_type", str, "edge", "Tipo de TTS"),
    ConfigField("tts_rate", int, 165, "Velocidad TTS", _validate_tts_rate),
    ConfigField("push_to_talk_hotkey", str, "left alt", "Atajo de voz"),
    ConfigField("habit_monitor_timeout_seconds", int, 600, "Timeout de actividad", _validate_positive_int),
    ConfigField("ai_enabled", bool, True, "IA local activa"),
    ConfigField("ai_base_url", str, "http://localhost:11434", "URL de IA local"),
    ConfigField("ai_model", str, "llama3.2", "Modelo de IA"),
    ConfigField("ui.mode", str, "classic", "Modo de interfaz", _validate_ui_mode),
    ConfigField("voice_profile", str, "default", "Perfil de voz"),
    ConfigField("wake_word", str, "viernes", "Palabra de activacion"),
    ConfigField("security.user_level", int, 1, "Nivel de seguridad", _validate_security_level),
    ConfigField("security.allowed_roots", list, [], "Raices autorizadas"),
    ConfigField("security.allowed_scripts", list, [], "Scripts autorizados"),
    ConfigField("security.password_hash", str, "", "Hash de seguridad"),
    ConfigField("plugins.enabled", bool, True, "Plugins activos"),
    ConfigField("plugins.enabled_plugins", list, [], "Plugins permitidos"),
    ConfigField("plugins.disabled", list, [], "Plugins desactivados"),
    ConfigField("automation.startup_enabled", bool, False, "Inicio de sesion activo"),
    ConfigField("automation.morning_wake_time", str, "07:30", "Hora de rutina matutina", _validate_hhmm),
    ConfigField("automation.auto_login_warning_acknowledged", bool, False, "Advertencia de desbloqueo aceptada"),
    ConfigField("morning_wake_enabled", bool, False, "Rutina matutina activa"),
    ConfigField("ambient_companion.enabled", bool, True, "Conversacion ambiental"),
    ConfigField("ambient_companion.interval_minutes", int, 90, "Intervalo ambiental", _validate_positive_int),
    ConfigField("ambient_companion.wake_time", str, "07:30", "Inicio ambiental", _validate_hhmm),
    ConfigField("ambient_companion.sleep_time", str, "22:30", "Fin ambiental", _validate_hhmm),
    ConfigField("conversation.proactive_topics_enabled", bool, True, "Temas proactivos"),
    ConfigField("proactivity.enabled", bool, True, "Proactividad activa"),
    ConfigField("proactivity.mode", str, "conservative", "Modo proactivo", _validate_proactive_mode),
    ConfigField("proactivity.interval_minutes", int, 120, "Cooldown proactivo", _validate_positive_int),
    ConfigField("proactivity.lookahead_minutes", int, 120, "Ventana proactiva", _validate_positive_int),
    ConfigField("proactivity.max_per_tick", int, 1, "Max sugerencias por tick", _validate_positive_int),
    ConfigField("news_preferences.preferred_topic", str, "world", "Tema de noticias"),
    ConfigField("telegram.enabled", bool, False, "Telegram activo"),
    ConfigField("telegram.token", str, "", "Token Telegram"),
    ConfigField("telegram.chat_id", str, "", "Chat ID Telegram"),
    ConfigField("analysis.enabled", bool, True, "Analisis activo"),
    ConfigField("analysis.save_reports", bool, True, "Guardar reportes"),
    ConfigField("analysis.allow_web_research", bool, True, "Investigacion web"),
    ConfigField("analysis.max_rows", int, 20, "Filas maximas de analisis", _validate_positive_int),
    ConfigField("analysis.chart_backend", str, "matplotlib", "Motor de graficas", _validate_chart_backend),
    ConfigField("analysis_beta.enabled", bool, True, "Analisis legado activo"),
    ConfigField("analysis_beta.save_reports", bool, True, "Guardar reportes legado"),
    ConfigField("analysis_beta.allow_web_research", bool, True, "Investigacion web legado"),
    ConfigField("analysis_beta.max_rows", int, 20, "Filas maximas de analisis legado", _validate_positive_int),
    ConfigField("analysis_beta.chart_backend", str, "matplotlib", "Motor de graficas legado", _validate_chart_backend),
    ConfigField("remote_control.enabled", bool, False, "Control remoto activo"),
    ConfigField("remote_control.allowed_chat_ids", list, [], "Chats remotos permitidos"),
    ConfigField("remote_control.owner_chat_ids", list, [], "Owners remotos"),
    ConfigField("remote_control.trusted_chat_ids", list, [], "Chats remotos confiables"),
    ConfigField("remote_control.read_only_chat_ids", list, [], "Chats remotos solo lectura"),
    ConfigField("remote_control.require_confirmation", bool, True, "Confirmacion remota obligatoria"),
    ConfigField("remote_control.send_artifacts", bool, True, "Enviar archivos por Telegram"),
    ConfigField("remote_control.history_limit", int, 100, "Historial remoto", _validate_positive_int),
    ConfigField("remote_control.poll_interval_seconds", int, 5, "Intervalo remoto", _validate_positive_int),
    ConfigField("remote_control.drop_pending_on_start", bool, True, "Ignorar backlog remoto al iniciar"),
    ConfigField("remote_control.blocked_intents", list, ["shutdown", "restart", "suspend", "delete", "cleanup_past_events"], "Intenciones remotas bloqueadas"),
    ConfigField("remote_calls.enabled", bool, False, "Llamadas remotas activas"),
    ConfigField("personal_activity.enabled", bool, False, "Monitoreo personal profundo"),
    ConfigField("personal_activity.privacy_mode", str, "app_category", "Privacidad actividad", _validate_privacy_mode),
    ConfigField("personal_activity.poll_interval_seconds", int, 60, "Intervalo actividad personal", _validate_positive_int),
    ConfigField("personal_activity.retention.raw_days", int, 14, "Retencion crudos actividad", _validate_positive_int),
    ConfigField("personal_activity.retention.session_days", int, 60, "Retencion sesiones actividad", _validate_positive_int),
    ConfigField("personal_activity.retention.aggregate_days", int, 365, "Retencion agregados actividad", _validate_positive_int),
    ConfigField("wol_mac", str, "", "MAC Wake-on-LAN"),
    ConfigField("quick_actions", list, [], "Acciones rapidas"),
)


class ViernesConfigManager:
    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        try:
            if self.path.exists():
                with open(self.path, encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    data = raw
        except (OSError, json.JSONDecodeError):
            data = {}
        return self._normalize_config(data)

    def backup(self) -> Path | None:
        if not self.path.exists():
            return None
        try:
            use_repo_runtime = self.path.resolve() == CONFIG_PATH.resolve()
        except OSError:
            use_repo_runtime = False
        backup_root = RUNTIME_DIR if use_repo_runtime else self.path.parent / "runtime"
        backup_dir = backup_root / "config_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        target = backup_dir / f"{self.path.stem}.{stamp}{self.path.suffix}"
        shutil.copy2(self.path, target)
        return target

    def validate_patch(self, patch: dict[str, Any], base_config: dict[str, Any] | None = None) -> ConfigValidationResult:
        if not isinstance(patch, dict):
            return ConfigValidationResult(False, ["El parche de configuracion debe ser un objeto."], [], {})
        base = copy.deepcopy(base_config) if isinstance(base_config, dict) else self.load()
        incoming = copy.deepcopy(patch)
        if "analysis_beta" in incoming and "analysis" not in incoming:
            incoming["analysis"] = copy.deepcopy(incoming["analysis_beta"])
        merged = _deep_merge(base, incoming)
        normalized = self._normalize_config(merged)
        errors, warnings = self._validate_config(normalized)
        return ConfigValidationResult(not errors, errors, warnings, normalized)

    def apply_patch(self, patch: dict[str, Any], base_config: dict[str, Any] | None = None) -> ConfigValidationResult:
        result = self.validate_patch(patch, base_config=base_config)
        if not result.valid:
            return result
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.backup()
        tmp_path = self.path.with_name(f"{self.path.name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(result.normalized, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.path)
        return result

    def snapshot(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        data = self._normalize_config(copy.deepcopy(config) if isinstance(config, dict) else self.load())
        token = str(data.get("telegram", {}).get("token", "") or "")
        if token:
            data["telegram"]["token"] = self._mask_secret(token)
        return data

    def _normalize_config(self, config: dict[str, Any]) -> dict[str, Any]:
        has_stable_analysis = isinstance(config, dict) and isinstance(config.get("analysis"), dict)
        data = _deep_merge(DEFAULT_CONFIG, config if isinstance(config, dict) else {})
        telegram = data.get("telegram")
        if not isinstance(telegram, dict):
            telegram = {}
        legacy_token = str(data.get("telegram_token", "") or "").strip()
        legacy_chat = str(data.get("telegram_chat_id", "") or "").strip()
        telegram.setdefault("enabled", False)
        if legacy_token and not str(telegram.get("token", "") or "").strip():
            telegram["token"] = legacy_token
        if legacy_chat and not str(telegram.get("chat_id", "") or "").strip():
            telegram["chat_id"] = legacy_chat
        data["telegram"] = telegram

        analysis = data.get("analysis")
        if not isinstance(analysis, dict):
            analysis = {}
        legacy_analysis = data.get("analysis_beta")
        if isinstance(legacy_analysis, dict) and not has_stable_analysis:
            for key in ("enabled", "save_reports", "allow_web_research", "max_rows", "chart_backend"):
                if key not in analysis and key in legacy_analysis:
                    analysis[key] = legacy_analysis[key]
                elif key in legacy_analysis:
                    analysis[key] = legacy_analysis[key]
        data["analysis"] = analysis

        for field in FIELDS:
            value = _get_path(data, field.parts, copy.deepcopy(field.default))
            value = _coerce_value(value, field.value_type, field.default)
            _set_path(data, field.parts, value)

        data["analysis_beta"] = copy.deepcopy(data.get("analysis", {}))

        data["quick_actions"] = _normalize_string_list(data.get("quick_actions", []))
        data.setdefault("security", {})
        data["security"]["allowed_roots"] = _normalize_string_list(data["security"].get("allowed_roots", []))
        data["security"]["allowed_scripts"] = _normalize_string_list(data["security"].get("allowed_scripts", []))
        data.setdefault("plugins", {})
        data["plugins"]["enabled_plugins"] = _normalize_string_list(data["plugins"].get("enabled_plugins", []))
        data["plugins"]["disabled"] = _normalize_string_list(data["plugins"].get("disabled", []))
        data["class_schedule"] = _normalize_class_schedule(data.get("class_schedule", {}))
        data["weekly_routines"] = _normalize_routines(data.get("weekly_routines", {}))
        data.setdefault("conversation", {})
        for key in ("small_talk", "facts", "tips", "jokes", "quotes"):
            data["conversation"][key] = _normalize_string_list(data["conversation"].get(key, []))
        data.setdefault("ambient_companion", {})
        data["ambient_companion"]["messages"] = _normalize_string_list(data["ambient_companion"].get("messages", []))
        return data

    def _validate_config(self, config: dict[str, Any]) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        for field in FIELDS:
            value = _get_path(config, field.parts, None)
            if not isinstance(value, field.value_type):
                errors.append(f"{field.label}: tipo invalido.")
                continue
            if field.validator:
                message = field.validator(value)
                if message:
                    errors.append(f"{field.label}: {message}.")
        errors.extend(_validate_class_schedule(config.get("class_schedule", {})))
        errors.extend(_validate_routines(config.get("weekly_routines", {})))
        if config.get("telegram", {}).get("enabled"):
            if not str(config.get("telegram", {}).get("token", "") or "").strip():
                errors.append("Telegram: falta token para activarlo.")
            if not str(config.get("telegram", {}).get("chat_id", "") or "").strip():
                errors.append("Telegram: falta chat_id para activarlo.")
        if len(config.get("quick_actions", [])) > 30:
            warnings.append("Hay mas de 30 acciones rapidas; la barra puede verse saturada.")
        return errors, warnings

    def _mask_secret(self, value: str) -> str:
        if len(value) <= 6:
            return "*" * len(value)
        return value[:3] + "*" * max(3, len(value) - 6) + value[-3:]


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _get_path(data: dict[str, Any], parts: tuple[str, ...], default: Any = None) -> Any:
    cursor: Any = data
    for part in parts:
        if not isinstance(cursor, dict) or part not in cursor:
            return default
        cursor = cursor[part]
    return cursor


def _set_path(data: dict[str, Any], parts: tuple[str, ...], value: Any) -> None:
    cursor = data
    for part in parts[:-1]:
        child = cursor.get(part)
        if not isinstance(child, dict):
            child = {}
            cursor[part] = child
        cursor = child
    cursor[parts[-1]] = value


def _coerce_value(value: Any, value_type: type | tuple[type, ...], default: Any) -> Any:
    if value_type is bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "si", "yes", "on", "activo", "activa"}
        return bool(value)
    if value_type is int:
        if value is None or value == "":
            return int(default)
        if isinstance(value, bool):
            return int(default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if value_type == (int, float) or value_type == (float, int):
        if value is None or value == "":
            return float(default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    if value_type is list:
        return _normalize_string_list(value)
    if value_type is str:
        return str(value if value is not None else default).strip()
    return value if isinstance(value, value_type) else copy.deepcopy(default)


def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw = re.split(r"[\n,;]+", value)
    elif isinstance(value, list):
        raw = value
    else:
        raw = []
    result: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = str(item).strip()
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _normalize_class_schedule(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    schedule: dict[str, list[str]] = {}
    for day, classes in value.items():
        day_key = str(day).strip().lower()
        schedule[day_key] = _normalize_string_list(classes)
    return schedule


def _validate_class_schedule(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["Clases: debe ser un objeto por dia."]
    valid_days = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
    for day, classes in value.items():
        if str(day) not in valid_days:
            errors.append(f"Clases: dia invalido {day}.")
        if not isinstance(classes, list) or any(not isinstance(item, str) for item in classes):
            errors.append(f"Clases {day}: debe ser lista de textos.")
    return errors


def _normalize_routines(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    from viernes_app.core.routine_helpers import migrate_legacy_routines

    routines = migrate_legacy_routines(copy.deepcopy(value))
    for _scope, cfg in list(routines.items()):
        if not isinstance(cfg, dict):
            continue
        reminders = cfg.get("reminders", [])
        if isinstance(reminders, list):
            for item in reminders:
                if isinstance(item, dict):
                    item["id"] = str(item.get("id", "") or "").strip()
                    item["time"] = str(item.get("time", "") or "").strip()
                    item["message"] = str(item.get("message", "") or "")
        bath = cfg.get("bath_followup")
        if isinstance(bath, dict):
            bath["start"] = str(bath.get("start", "") or "").strip()
            bath["stop"] = str(bath.get("stop", "") or "").strip()
            bath["repeat_minutes"] = _coerce_value(bath.get("repeat_minutes", 20), int, 20)
            bath["message"] = str(bath.get("message", "") or "")
    return routines


def _validate_routines(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["Rutinas: debe ser un objeto."]
    for scope, cfg in value.items():
        if not isinstance(cfg, dict):
            errors.append(f"Rutina {scope}: debe ser objeto.")
            continue
        for item in cfg.get("reminders", []) if isinstance(cfg.get("reminders", []), list) else []:
            if not isinstance(item, dict):
                errors.append(f"Rutina {scope}: recordatorio invalido.")
                continue
            hhmm = str(item.get("time", "") or "").strip()
            if hhmm and not _is_hhmm(hhmm):
                errors.append(f"Rutina {scope}/{item.get('id', 'sin id')}: hora invalida.")
        for key in ("leave_time", "packing_time", "chores_time", "stop_all_after"):
            value_for_key = str(cfg.get(key, "") or "").strip()
            if value_for_key and not _is_hhmm(value_for_key):
                errors.append(f"Rutina {scope}/{key}: hora invalida.")
        bath = cfg.get("bath_followup", {})
        if isinstance(bath, dict):
            for key in ("start", "stop"):
                value_for_key = str(bath.get(key, "") or "").strip()
                if value_for_key and not _is_hhmm(value_for_key):
                    errors.append(f"Rutina {scope}/bano {key}: hora invalida.")
            if not isinstance(bath.get("repeat_minutes", 20), int) or int(bath.get("repeat_minutes", 20)) <= 0:
                errors.append(f"Rutina {scope}/bano: repeticion invalida.")
    return errors
