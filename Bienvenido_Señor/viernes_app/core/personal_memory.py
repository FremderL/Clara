from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from viernes_app.paths import PERSONAL_MEMORY_PATH


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now()).isoformat(timespec="seconds")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _clean_fact(text: str) -> str:
    value = re.sub(r"\s+", " ", text).strip(" .,\t\r\n")
    return value[:300]


@dataclass
class MemoryFact:
    id: str
    text: str
    category: str = "general"
    source: str = "explicit"
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    weight: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryFact":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:12]),
            text=str(data.get("text") or ""),
            category=str(data.get("category") or "general"),
            source=str(data.get("source") or "explicit"),
            created_at=str(data.get("created_at") or _now_iso()),
            updated_at=str(data.get("updated_at") or data.get("created_at") or _now_iso()),
            weight=int(data.get("weight", 1) or 1),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "category": self.category,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "weight": self.weight,
        }


@dataclass
class Preference:
    key: str
    value: str
    category: str = "general"
    source: str = "explicit"
    confidence: float = 0.7
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Preference":
        return cls(
            key=str(data.get("key") or ""),
            value=str(data.get("value") or ""),
            category=str(data.get("category") or "general"),
            source=str(data.get("source") or "explicit"),
            confidence=float(data.get("confidence", 0.7) or 0.7),
            created_at=str(data.get("created_at") or data.get("updated_at") or _now_iso()),
            updated_at=str(data.get("updated_at") or _now_iso()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "source": self.source,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class PersonalRule:
    id: str
    text: str
    action_text: str
    weekday: str = ""
    time: str = ""
    relation: str = "at"
    active: bool = True
    created_at: str = field(default_factory=_now_iso)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PersonalRule":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:12]),
            text=str(data.get("text") or ""),
            action_text=str(data.get("action_text") or ""),
            weekday=str(data.get("weekday") or ""),
            time=str(data.get("time") or ""),
            relation=str(data.get("relation") or "at"),
            active=bool(data.get("active", True)),
            created_at=str(data.get("created_at") or _now_iso()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "action_text": self.action_text,
            "weekday": self.weekday,
            "time": self.time,
            "relation": self.relation,
            "active": self.active,
            "created_at": self.created_at,
        }


@dataclass
class UserProfile:
    facts: list[MemoryFact] = field(default_factory=list)
    preferences: list[Preference] = field(default_factory=list)
    rules: list[PersonalRule] = field(default_factory=list)
    activity_patterns: list[str] = field(default_factory=list)
    updated_at: str = field(default_factory=_now_iso)
    version: str = "personal-memory-v1"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserProfile":
        return cls(
            facts=[MemoryFact.from_dict(item) for item in list(data.get("facts", [])) if isinstance(item, dict)],
            preferences=[
                Preference.from_dict(item) for item in list(data.get("preferences", [])) if isinstance(item, dict)
            ],
            rules=[PersonalRule.from_dict(item) for item in list(data.get("rules", [])) if isinstance(item, dict)],
            activity_patterns=[str(item) for item in list(data.get("activity_patterns", [])) if str(item).strip()],
            updated_at=str(data.get("updated_at") or _now_iso()),
            version=str(data.get("version") or "personal-memory-v1"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "facts": [item.to_dict() for item in self.facts],
            "preferences": [item.to_dict() for item in self.preferences],
            "rules": [item.to_dict() for item in self.rules],
            "activity_patterns": list(self.activity_patterns[-20:]),
        }


class PersonalMemoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or PERSONAL_MEMORY_PATH

    def load_profile(self) -> UserProfile:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return UserProfile.from_dict(data)
        except FileNotFoundError:
            pass
        except Exception:
            pass
        return UserProfile()

    def save_profile(self, profile: UserProfile) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        profile.updated_at = _now_iso()
        self.path.write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def remember(
        self,
        text: str,
        *,
        category: str = "general",
        source: str = "explicit",
        now: datetime | None = None,
    ) -> MemoryFact:
        fact_text = _clean_fact(text)
        if not fact_text:
            raise ValueError("empty memory fact")
        profile = self.load_profile()
        normalized = _normalize(fact_text)
        for fact in profile.facts:
            if _normalize(fact.text) == normalized:
                fact.weight += 1
                fact.updated_at = _now_iso(now)
                self.save_profile(profile)
                return fact
        fact = MemoryFact(
            id=uuid.uuid4().hex[:12],
            text=fact_text,
            category=category,
            source=source,
            created_at=_now_iso(now),
            updated_at=_now_iso(now),
        )
        profile.facts.append(fact)
        profile.facts = profile.facts[-120:]
        self.save_profile(profile)
        return fact

    def forget(self, query: str) -> int:
        target = _normalize(query)
        if not target:
            return 0
        profile = self.load_profile()
        before = len(profile.facts)
        profile.facts = [fact for fact in profile.facts if target not in _normalize(fact.text)]
        removed = before - len(profile.facts)
        if removed:
            self.save_profile(profile)
        return removed

    def search(self, query: str, *, max_items: int = 8) -> list[MemoryFact | Preference | PersonalRule]:
        target_tokens = set(_normalize(query).split())
        if not target_tokens:
            return []
        profile = self.load_profile()
        scored: list[tuple[int, int, MemoryFact | Preference | PersonalRule]] = []

        def score_text(text: str) -> int:
            text_tokens = set(_normalize(text).split())
            return len(target_tokens.intersection(text_tokens))

        for index, fact in enumerate(profile.facts):
            score = score_text(fact.text)
            if score:
                scored.append((score, index, fact))
        offset = len(profile.facts)
        for index, pref in enumerate(profile.preferences):
            score = score_text(f"{pref.key} {pref.value}")
            if score:
                scored.append((score, offset + index, pref))
        offset += len(profile.preferences)
        for index, rule in enumerate(profile.rules):
            score = score_text(f"{rule.text} {rule.action_text}")
            if score:
                scored.append((score, offset + index, rule))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item for _score, _index, item in scored[:max_items]]

    def set_preference(
        self,
        key: str,
        value: str,
        *,
        category: str = "general",
        source: str = "explicit",
        confidence: float = 0.85,
        now: datetime | None = None,
    ) -> Preference:
        clean_key = _clean_fact(key).lower()
        clean_value = _clean_fact(value)
        if not clean_key or not clean_value:
            raise ValueError("empty preference")
        profile = self.load_profile()
        normalized = _normalize(clean_key)
        for pref in profile.preferences:
            if _normalize(pref.key) == normalized:
                pref.value = clean_value
                pref.category = category or pref.category
                pref.source = source or pref.source
                pref.confidence = confidence
                pref.updated_at = _now_iso(now)
                self.save_profile(profile)
                return pref
        pref = Preference(
            key=clean_key,
            value=clean_value,
            category=category,
            source=source,
            confidence=confidence,
            created_at=_now_iso(now),
            updated_at=_now_iso(now),
        )
        profile.preferences.append(pref)
        profile.preferences = profile.preferences[-120:]
        self.save_profile(profile)
        return pref

    def forget_preference(self, query: str) -> int:
        target = _normalize(query)
        if not target:
            return 0
        profile = self.load_profile()
        before = len(profile.preferences)
        profile.preferences = [
            pref
            for pref in profile.preferences
            if target not in _normalize(pref.key) and target not in _normalize(pref.value)
        ]
        removed = before - len(profile.preferences)
        if removed:
            self.save_profile(profile)
        return removed

    def preferences_summary(self, max_items: int = 12) -> str:
        profile = self.load_profile()
        if not profile.preferences:
            return "No tengo preferencias personales guardadas."
        prefs = profile.preferences[-max_items:]
        return "Preferencias: " + " | ".join(f"{pref.key}: {pref.value}" for pref in prefs)

    def add_personal_rule(self, text: str, now: datetime | None = None) -> PersonalRule:
        rule_text = _clean_fact(text)
        parsed = self._parse_rule(rule_text)
        if parsed is None:
            raise ValueError("unsupported personal rule")
        profile = self.load_profile()
        normalized = _normalize(rule_text)
        for rule in profile.rules:
            if _normalize(rule.text) == normalized:
                rule.active = True
                self.save_profile(profile)
                return rule
        rule = PersonalRule(
            id=uuid.uuid4().hex[:12],
            text=rule_text,
            action_text=parsed["action_text"],
            weekday=parsed["weekday"],
            time=parsed["time"],
            relation=parsed["relation"],
            created_at=_now_iso(now),
        )
        profile.rules.append(rule)
        profile.rules = profile.rules[-80:]
        self.save_profile(profile)
        return rule

    def forget_rule(self, query: str) -> int:
        target = _normalize(query)
        if not target:
            return 0
        profile = self.load_profile()
        before = len(profile.rules)
        profile.rules = [
            rule
            for rule in profile.rules
            if target not in _normalize(rule.text)
            and target not in _normalize(rule.action_text)
            and target != _normalize(rule.id)
        ]
        removed = before - len(profile.rules)
        if removed:
            self.save_profile(profile)
        return removed

    def rules_for_day(self, target_day: date) -> list[PersonalRule]:
        weekday = _weekday_key(target_day)
        profile = self.load_profile()
        return [
            rule
            for rule in profile.rules
            if rule.active and (not rule.weekday or rule.weekday == weekday)
        ]

    def rules_summary(self) -> str:
        profile = self.load_profile()
        active = [rule for rule in profile.rules if rule.active]
        if not active:
            return "No hay reglas personales activas."
        parts = []
        for index, rule in enumerate(active[-8:], start=1):
            when = rule.weekday or "cualquier dia"
            relation = "antes de" if rule.relation == "before" else "a las"
            time = f" {relation} {rule.time}" if rule.time else ""
            parts.append(f"{index}. {when}{time}: {rule.action_text}")
        return "Reglas personales: " + " | ".join(parts)

    def update_from_adaptive_profile(self, adaptive_profile: dict[str, Any], now: datetime | None = None) -> int:
        profile = self.load_profile()
        recommendations = [str(item) for item in list(adaptive_profile.get("recommendations", [])) if str(item).strip()]
        added = 0
        for text in recommendations[:4]:
            if text not in profile.activity_patterns:
                profile.activity_patterns.append(text)
                added += 1
        profile.activity_patterns = profile.activity_patterns[-20:]
        if added:
            profile.updated_at = _now_iso(now)
            self.save_profile(profile)
        return added

    def summary(self, max_items: int = 8) -> str:
        profile = self.load_profile()
        parts: list[str] = []
        if profile.facts:
            facts = "; ".join(fact.text for fact in profile.facts[-max_items:])
            parts.append("Datos recordados: " + facts)
        if profile.preferences:
            prefs = "; ".join(f"{pref.key}: {pref.value}" for pref in profile.preferences[-max_items:])
            parts.append("Preferencias: " + prefs)
        if profile.activity_patterns:
            patterns = "; ".join(profile.activity_patterns[-3:])
            parts.append("Patrones recientes: " + patterns)
        if profile.rules:
            parts.append(f"Reglas personales activas: {len([rule for rule in profile.rules if rule.active])}.")
        if not parts:
            return "Aun no tengo memoria personal guardada sobre usted."
        return " ".join(parts)

    def _parse_rule(self, text: str) -> dict[str, str] | None:
        low = _normalize(text)
        if "recuerdame" not in low and "recuerda" not in low:
            return None
        weekday = _extract_weekday(low)
        time_value, relation = _extract_rule_time(low)
        match = re.search(r"\brecuerdame\s+(.+)$", low)
        if not match:
            match = re.search(r"\brecuerda\s+(.+)$", low)
        action_text = _clean_fact(match.group(1) if match else "")
        if not action_text:
            return None
        return {
            "weekday": weekday,
            "time": time_value,
            "relation": relation,
            "action_text": action_text,
        }


WEEKDAY_BY_NAME = {
    "lunes": "monday",
    "martes": "tuesday",
    "miercoles": "wednesday",
    "jueves": "thursday",
    "viernes": "friday",
    "sabado": "saturday",
    "domingo": "sunday",
}


def _extract_weekday(low: str) -> str:
    for name, key in WEEKDAY_BY_NAME.items():
        if re.search(rf"\b{name}\b", low):
            return key
    return ""


def _extract_rule_time(low: str) -> tuple[str, str]:
    relation = "before" if "antes de" in low else "at"
    match = re.search(r"\b(?:antes\s+de\s+las|a\s+las|antes\s+de|a\s+la)\s+(\d{1,2})(?::(\d{2}))?\b", low)
    if not match:
        return "", relation
    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    if ("tarde" in low or "noche" in low or "pm" in low) and hour < 12:
        hour += 12
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return f"{hour:02d}:{minute:02d}", relation
    return "", relation


def _weekday_key(target_day: date) -> str:
    return ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][
        target_day.weekday()
    ]
