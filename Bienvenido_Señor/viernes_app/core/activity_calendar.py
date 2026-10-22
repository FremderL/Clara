from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any


@dataclass(frozen=True)
class ActivityBlock:
    start: str
    end: str
    title: str
    category: str
    source: str
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "title": self.title,
            "category": self.category,
            "source": self.source,
            "details": self.details,
        }


@dataclass(frozen=True)
class ActivityCalendar:
    day: str
    blocks: list[ActivityBlock]
    notes: list[str]

    def next_block(self, now: datetime) -> ActivityBlock | None:
        for block in self.blocks:
            start = _combine(now.date(), block.start)
            if start >= now:
                return block
        return None

    def summary(self, limit: int = 8) -> str:
        if not self.blocks:
            note = " ".join(self.notes)
            return f"Calendario de {self.day}: sin bloques operativos." + (f" {note}" if note else "")
        parts = [
            f"{block.start}-{block.end} {block.title}"
            for block in self.blocks[:limit]
        ]
        suffix = f" y {len(self.blocks) - limit} mas" if len(self.blocks) > limit else ""
        return f"Calendario de {self.day}: " + " | ".join(parts) + suffix

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day,
            "blocks": [block.to_dict() for block in self.blocks],
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ActivityWeek:
    start_day: str
    calendars: list[ActivityCalendar]

    def summary(self, blocks_per_day: int = 3) -> str:
        if not self.calendars:
            return f"Semana operativa desde {self.start_day}: sin datos."
        parts: list[str] = []
        for calendar in self.calendars:
            if calendar.blocks:
                blocks = ", ".join(f"{block.start} {block.title}" for block in calendar.blocks[:blocks_per_day])
                extra = f" (+{len(calendar.blocks) - blocks_per_day})" if len(calendar.blocks) > blocks_per_day else ""
                parts.append(f"{calendar.day}: {blocks}{extra}")
            else:
                note = " ".join(calendar.notes[:2])
                parts.append(f"{calendar.day}: sin bloques" + (f" ({note})" if note else ""))
        return f"Semana operativa desde {self.start_day}: " + " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_day": self.start_day,
            "calendars": [calendar.to_dict() for calendar in self.calendars],
        }


class ActivityCalendarBuilder:
    def build_day(
        self,
        target_day: date,
        *,
        agenda_items: list[dict[str, Any]],
        classes: list[str],
        leave_time: str | None,
        override: dict[str, Any] | None = None,
        daily: dict[str, Any] | None = None,
        personal_rules: list[dict[str, Any]] | None = None,
    ) -> ActivityCalendar:
        override = override or {}
        daily = daily or {}
        notes: list[str] = []
        blocks: list[ActivityBlock] = []

        if override.get("free_day"):
            notes.append("Dia libre marcado.")
        if override.get("classes_cancelled"):
            notes.append("Clases canceladas.")
        for note in list(daily.get("notes", []))[-4:]:
            if str(note).strip():
                notes.append(str(note).strip())

        for item in agenda_items:
            hhmm = str(item.get("time", "") or "").strip()
            if not _valid_hhmm(hhmm):
                continue
            blocks.append(
                ActivityBlock(
                    start=hhmm,
                    end=_add_minutes(target_day, hhmm, 30),
                    title=str(item.get("title", "Evento") or "Evento"),
                    category="agenda",
                    source="agenda",
                )
            )

        has_classes = bool(classes) and not override.get("free_day") and not override.get("classes_cancelled")
        if has_classes and leave_time and _valid_hhmm(leave_time):
            prep_start = _add_minutes(target_day, leave_time, -60)
            blocks.append(
                ActivityBlock(
                    start=prep_start,
                    end=leave_time,
                    title="Preparacion para salir",
                    category="routine",
                    source="routine",
                    details="Mochila, pendientes, higiene y margen de salida.",
                )
            )
            blocks.append(
                ActivityBlock(
                    start=leave_time,
                    end=_add_minutes(target_day, leave_time, 20),
                    title="Salida",
                    category="routine",
                    source="routine",
                    details="Hora de salida configurada para este dia.",
                )
            )
            blocks.append(
                ActivityBlock(
                    start=_add_minutes(target_day, leave_time, 30),
                    end=_add_minutes(target_day, leave_time, 180),
                    title="Clases: " + ", ".join(classes[:4]),
                    category="classes",
                    source="classes",
                )
            )
        elif has_classes:
            blocks.append(
                ActivityBlock(
                    start="12:00",
                    end="15:00",
                    title="Clases: " + ", ".join(classes[:4]),
                    category="classes",
                    source="classes",
                    details="No hay hora de salida configurada.",
                )
            )

        for rule in personal_rules or []:
            hhmm = str(rule.get("time", "") or "").strip()
            if not _valid_hhmm(hhmm):
                continue
            relation = str(rule.get("relation", "at") or "at")
            start = _add_minutes(target_day, hhmm, -30) if relation == "before" else hhmm
            end = hhmm if relation == "before" else _add_minutes(target_day, hhmm, 15)
            action = str(rule.get("action_text", "Regla personal") or "Regla personal")
            blocks.append(
                ActivityBlock(
                    start=start,
                    end=end,
                    title=f"Regla personal: {action}",
                    category="personal_rule",
                    source="memory_rule",
                    details=str(rule.get("text", "") or ""),
                )
            )

        if not daily.get("day_closed"):
            blocks.append(
                ActivityBlock(
                    start="21:00",
                    end="21:20",
                    title="Revision nocturna",
                    category="review",
                    source="system",
                    details="Revisar agenda, pendientes y preparacion de manana.",
                )
            )

        blocks = sorted(blocks, key=lambda block: (block.start, block.end, block.title))
        return ActivityCalendar(day=target_day.isoformat(), blocks=blocks, notes=notes)


def _valid_hhmm(value: str) -> bool:
    try:
        hour_raw, minute_raw = value.split(":", 1)
        hour, minute = int(hour_raw), int(minute_raw)
    except Exception:
        return False
    return 0 <= hour <= 23 and 0 <= minute <= 59


def _combine(day: date, hhmm: str) -> datetime:
    hour_raw, minute_raw = hhmm.split(":", 1)
    return datetime.combine(day, datetime.min.time()).replace(hour=int(hour_raw), minute=int(minute_raw))


def _add_minutes(day: date, hhmm: str, minutes: int) -> str:
    value = _combine(day, hhmm) + timedelta(minutes=minutes)
    return value.strftime("%H:%M")
