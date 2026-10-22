from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from viernes_app.paths import REPO_ROOT

HABITS_FILE = REPO_ROOT / "viernes_habits.json"
PREFERENCES_FILE = REPO_ROOT / "viernes_preferences.json"


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text).lower().strip())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[\u00bf?\u00a1!.,;:\"'()]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


class HabitTracker:
    @staticmethod
    def load() -> dict[str, Any]:
        try:
            if HABITS_FILE.exists():
                with open(HABITS_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("daily", {})
                    data.setdefault("categories", {})
                    data.setdefault("hourly", {})
                    data.setdefault("recent", [])
                    return data
        except Exception:
            pass
        return {"daily": {}, "categories": {}, "hourly": {}, "recent": []}

    @staticmethod
    def save(habits: dict[str, Any]) -> None:
        with open(HABITS_FILE, "w", encoding="utf-8") as f:
            json.dump(habits, f, ensure_ascii=False, indent=2)

    @staticmethod
    def log_action(action: str, category: str = "general", when: datetime | None = None) -> None:
        stamp = when or datetime.now()
        action_key = (action or "accion").strip()[:80] or "accion"
        category_key = (category or "general").strip()[:40] or "general"
        day_key = stamp.date().isoformat()
        hour_key = f"{stamp.hour:02d}"

        habits = HabitTracker.load()
        habits.setdefault("daily", {}).setdefault(day_key, {})
        habits["daily"][day_key][action_key] = habits["daily"][day_key].get(action_key, 0) + 1

        habits.setdefault("categories", {}).setdefault(day_key, {})
        habits["categories"][day_key][category_key] = habits["categories"][day_key].get(category_key, 0) + 1

        habits.setdefault("hourly", {}).setdefault(hour_key, 0)
        habits["hourly"][hour_key] += 1

        recent = habits.setdefault("recent", [])
        recent.append(
            {
                "action": action_key,
                "category": category_key,
                "timestamp": stamp.isoformat(timespec="seconds"),
            }
        )
        habits["recent"] = recent[-120:]
        habits["last_updated"] = stamp.isoformat(timespec="seconds")
        HabitTracker.save(habits)

    @staticmethod
    def get_stats(days: int = 7) -> str:
        habits = HabitTracker.load()
        daily = habits.get("daily", {})
        categories = habits.get("categories", {})
        hourly = habits.get("hourly", {})
        today = datetime.now().date()

        action_counts: Counter[str] = Counter()
        category_counts: Counter[str] = Counter()
        total_actions = 0
        active_days = 0

        for i in range(max(1, days)):
            date_key = (today - timedelta(days=i)).isoformat()
            day_actions = daily.get(date_key, {})
            day_categories = categories.get(date_key, {})
            if day_actions:
                active_days += 1
            for action, count in day_actions.items():
                total_actions += int(count)
                action_counts[str(action)] += int(count)
            for category, count in day_categories.items():
                category_counts[str(category)] += int(count)

        if not action_counts:
            return f"Sin datos de habitos en los ultimos {days} dias."

        top_actions = ", ".join(f"{name} ({count})" for name, count in action_counts.most_common(5))
        top_categories = ", ".join(f"{name} ({count})" for name, count in category_counts.most_common(4)) or "sin categorias"
        best_hour = "sin horario claro"
        if isinstance(hourly, dict) and hourly:
            hour, count = max(hourly.items(), key=lambda item: int(item[1]))
            best_hour = f"{hour}:00 ({count} usos)"

        return (
            f"Habitos de los ultimos {days} dias: {total_actions} acciones en {active_days} dia(s). "
            f"Mas frecuente: {top_actions}. Categorias: {top_categories}. "
            f"Horario donde mas me usa: {best_hour}."
        )

    @staticmethod
    def _recent_entries(habits: dict[str, Any], days: int = 7, now: datetime | None = None) -> list[dict[str, Any]]:
        current = now or datetime.now()
        cutoff = current - timedelta(days=max(1, days))
        entries: list[dict[str, Any]] = []
        for item in habits.get("recent", []):
            if not isinstance(item, dict):
                continue
            try:
                stamp = datetime.fromisoformat(str(item.get("timestamp", "")))
            except ValueError:
                continue
            if stamp >= cutoff:
                entries.append(item)
        return entries

    @staticmethod
    def build_profile(days: int = 7, now: datetime | None = None) -> dict[str, Any]:
        habits = HabitTracker.load()
        entries = HabitTracker._recent_entries(habits, days, now)
        categories: Counter[str] = Counter()
        actions: Counter[str] = Counter()
        hours: Counter[str] = Counter()
        active_days: set[str] = set()

        for item in entries:
            action = str(item.get("action", "accion") or "accion")
            category = str(item.get("category", "general") or "general")
            try:
                stamp = datetime.fromisoformat(str(item.get("timestamp", "")))
            except ValueError:
                continue
            actions[action] += 1
            categories[category] += 1
            hours[f"{stamp.hour:02d}"] += 1
            active_days.add(stamp.date().isoformat())

        best_hour = ""
        if hours:
            best_hour = max(hours.items(), key=lambda item: item[1])[0]
        top_category = categories.most_common(1)[0][0] if categories else ""
        repeated_action = actions.most_common(1)[0] if actions else ("", 0)

        profile = {
            "days": max(1, days),
            "total_actions": sum(actions.values()),
            "active_days": len(active_days),
            "top_category": top_category,
            "top_categories": categories.most_common(6),
            "top_actions": actions.most_common(8),
            "best_hour": best_hour,
            "repeated_action": repeated_action,
            "idle_events": categories.get("monitoreo", 0),
        }
        profile["recommendations"] = HabitTracker._recommendations_from_profile(profile)
        return profile

    @staticmethod
    def _recommendations_from_profile(profile: dict[str, Any]) -> list[str]:
        recommendations: list[str] = []
        total = int(profile.get("total_actions", 0) or 0)
        top_category = str(profile.get("top_category", "") or "")
        best_hour = str(profile.get("best_hour", "") or "")
        repeated_name, repeated_count = profile.get("repeated_action", ("", 0))
        idle_events = int(profile.get("idle_events", 0) or 0)

        if total < 4:
            recommendations.append(
                "Todavia tengo pocos datos. Use Viernes unos dias mas y registrare patrones mas confiables."
            )
        if idle_events >= 2:
            recommendations.append(
                "Detecte varios periodos de inactividad. Conviene separar descansos reales de pausas accidentales."
            )
        if top_category == "agenda":
            recommendations.append(
                "Usa mucho la agenda; le conviene revisar el siguiente compromiso antes de cambiar de actividad."
            )
        elif top_category == "apps":
            recommendations.append(
                "Abre apps con frecuencia; puedo ayudarle a crear una rutina de arranque con sus herramientas habituales."
            )
        elif top_category == "web":
            recommendations.append(
                "Ha investigado varios temas; conviene guardar conclusiones breves para no repetir busquedas."
            )
        elif top_category == "math":
            recommendations.append(
                "Ha resuelto calculos con Viernes; puede pedirme que revise pasos si una operacion no sale clara."
            )
        elif top_category == "conversation":
            recommendations.append(
                "Esta usando conversacion libre; puedo proponer temas cortos para mantener ritmo sin saturarlo."
            )
        if best_hour:
            recommendations.append(f"Su horario mas activo conmigo es cerca de las {best_hour}:00; es buena ventana para planear.")
        try:
            repeated_count = int(repeated_count)
        except (TypeError, ValueError):
            repeated_count = 0
        if repeated_name and repeated_count >= 3:
            recommendations.append(
                f"Repitio varias veces '{repeated_name}'. Si es una rutina, puedo convertirlo en acceso rapido o recordatorio."
            )
        if not recommendations:
            recommendations.append(
                "No veo un problema fuerte de habitos. Mantenga una revision breve de agenda y prioridades al iniciar."
            )
        return recommendations[:4]

    @staticmethod
    def get_recommendations(days: int = 7) -> str:
        profile = HabitTracker.build_profile(days)
        recs = profile.get("recommendations", [])
        if not recs:
            return "Aun no tengo recomendaciones de habitos."
        return "Recomendaciones de habitos: " + " ".join(
            f"{idx}. {text}" for idx, text in enumerate(recs, start=1)
        )

    @staticmethod
    def suggest_aliases(
        days: int = 14,
        min_count: int = 2,
        limit: int = 6,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        habits = HabitTracker.load()
        current = now or datetime.now()
        action_counts: Counter[str] = Counter()
        category_by_action: dict[str, str] = {}

        for index in range(max(1, days)):
            date_key = (current.date() - timedelta(days=index)).isoformat()
            for action, count in dict(habits.get("daily", {}).get(date_key, {})).items():
                try:
                    action_counts[str(action)] += int(count)
                except (TypeError, ValueError):
                    continue

        for item in habits.get("recent", []):
            if not isinstance(item, dict):
                continue
            action = str(item.get("action", "") or "")
            if action:
                category_by_action[action] = str(item.get("category", "") or "")

        suggestions: list[dict[str, Any]] = []
        seen_aliases: set[str] = set()
        for action, count in action_counts.most_common():
            if count < min_count or HabitTracker._skip_alias_source(action, category_by_action.get(action, "")):
                continue
            alias = HabitTracker._alias_for_action(action, category_by_action.get(action, ""))
            if not alias:
                continue
            normalized_alias = _normalize(alias)
            normalized_action = _normalize(action)
            if normalized_alias == normalized_action or normalized_alias in seen_aliases:
                continue
            if len(normalized_alias) >= len(normalized_action):
                continue
            seen_aliases.add(normalized_alias)
            suggestions.append(
                {
                    "alias": alias,
                    "command": action,
                    "count": count,
                    "category": category_by_action.get(action, ""),
                    "reason": "comando repetido",
                }
            )
            if len(suggestions) >= limit:
                break
        return suggestions

    @staticmethod
    def alias_suggestions_message(days: int = 14) -> str:
        suggestions = HabitTracker.suggest_aliases(days=days)
        if not suggestions:
            return "No veo suficientes comandos repetidos para sugerir alias todavia."
        parts = []
        for index, item in enumerate(suggestions, start=1):
            parts.append(
                f"{index}. Diga '{item['alias']}' para abreviar '{item['command']}' "
                f"({item['count']} veces)."
            )
        return "Alias sugeridos: " + " ".join(parts)

    @staticmethod
    def _skip_alias_source(action: str, category: str = "") -> bool:
        low = _normalize(action)
        if not low:
            return True
        if category == "monitoreo":
            return True
        if low in {
            "hola",
            "hola viernes",
            "voy a viernes",
            "voy viernes",
            "buenas noches",
            "muchas gracias",
            "gracias",
            "inactividad detectada",
            "actividad retomada",
        }:
            return True
        if low.startswith(("como estas", "que tal", "buenas", "ya me bane", "ya me banie")):
            return True
        return len(low.split()) <= 2

    @staticmethod
    def _alias_for_action(action: str, category: str = "") -> str:
        low = _normalize(action)
        weekday = HabitTracker._weekday_in_action(low)
        if weekday and ("agenda" in low or low.startswith(("que tengo", "que hay"))):
            return f"agenda {weekday}"
        if weekday and ("clase" in low or "clases" in low or "materia" in low):
            return f"clases {weekday}"
        if "horario" in low and "salida" in low:
            hour = HabitTracker._hour_alias(low)
            return f"salida {hour}".strip()
        if low.startswith(("clima de hoy", "como esta el clima", "pronostico de hoy")):
            return "clima"
        if low.startswith(("informe del dia", "resumen del dia", "estado del dia")):
            return "hoy"
        if "historia" in low and any(word in low for word in ("cuentame", "cuenta", "dime")):
            return "historia"
        if "presupuesto" in low and any(word in low for word in ("reinicia", "reiniciar", "reset", "limpiar")):
            return "reiniciar presupuesto"
        if low.startswith("recuerdame "):
            return HabitTracker._compact_alias(low, keep_prefix="recuerdame")
        if low.startswith(("agrega ", "agregar ", "anade ", "registrar ", "registra ")):
            return HabitTracker._compact_alias(low)
        if low.startswith("investiga que es "):
            return "investiga " + low.replace("investiga que es ", "", 1).strip()
        if low.startswith("que es "):
            return "investiga " + low
        return HabitTracker._compact_alias(low)

    @staticmethod
    def _weekday_in_action(low: str) -> str:
        match = re.search(r"\b(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b", low)
        return match.group(1) if match else ""

    @staticmethod
    def _hour_alias(low: str) -> str:
        match = re.search(r"\b(\d{1,2})(?::\d{2})?\b", low)
        if not match:
            return ""
        return f"a las {int(match.group(1))}"

    @staticmethod
    def _compact_alias(low: str, keep_prefix: str = "") -> str:
        stopwords = {
            "a",
            "al",
            "como",
            "con",
            "de",
            "del",
            "dia",
            "el",
            "en",
            "es",
            "la",
            "las",
            "lo",
            "me",
            "mi",
            "para",
            "por",
            "que",
            "solo",
            "un",
            "una",
        }
        tokens = [token for token in low.split() if token not in stopwords]
        if keep_prefix:
            tokens = [token for token in tokens if token != keep_prefix]
            tokens.insert(0, keep_prefix)
        return " ".join(tokens[:5]).strip()


class PreferencesManager:
    @staticmethod
    def load() -> dict[str, Any]:
        try:
            if PREFERENCES_FILE.exists():
                with open(PREFERENCES_FILE, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {
            "favorite_apps": [],
            "greeting": "Hola",
            "morning_message": "Buenos dias",
            "night_message": "Buenas noches",
            "tts_rate": 165,
            "city": "Colima, Colima, Mexico",
        }

    @staticmethod
    def save(prefs: dict[str, Any]) -> None:
        with open(PREFERENCES_FILE, "w", encoding="utf-8") as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)

    @staticmethod
    def set(key: str, value: str) -> None:
        prefs = PreferencesManager.load()
        prefs[key] = value
        PreferencesManager.save(prefs)

    @staticmethod
    def get(key: str) -> str:
        return str(PreferencesManager.load().get(key, ""))


def log_user_action(action: str, category: str = "general") -> None:
    HabitTracker.log_action(action, category)


def get_user_stats(days: int = 7) -> str:
    return HabitTracker.get_stats(days)


def get_habit_recommendations(days: int = 7) -> str:
    return HabitTracker.get_recommendations(days)


def build_adaptive_profile(days: int = 7) -> dict[str, Any]:
    return HabitTracker.build_profile(days)


def get_alias_suggestions(days: int = 14) -> str:
    return HabitTracker.alias_suggestions_message(days)
