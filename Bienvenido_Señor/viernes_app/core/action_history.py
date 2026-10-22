from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from viernes_app.paths import ACTION_HISTORY_PATH


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now()).isoformat(timespec="seconds")


def _json_clone(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


@dataclass
class ActionHistoryEntry:
    id: str
    created_at: str
    summary: str
    source: str = "action_plan"
    status: str = "active"
    plan_id: str = ""
    steps: list[str] = field(default_factory=list)
    result: str = ""
    snapshots: dict[str, Any] = field(default_factory=dict)
    undone_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionHistoryEntry":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:10]),
            created_at=str(data.get("created_at") or _now_iso()),
            summary=str(data.get("summary") or "Accion"),
            source=str(data.get("source") or "action_plan"),
            status=str(data.get("status") or "active"),
            plan_id=str(data.get("plan_id") or ""),
            steps=[str(item) for item in list(data.get("steps", []))],
            result=str(data.get("result") or ""),
            snapshots=dict(data.get("snapshots") or {}),
            undone_at=str(data.get("undone_at") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "summary": self.summary,
            "source": self.source,
            "status": self.status,
            "plan_id": self.plan_id,
            "steps": list(self.steps),
            "result": self.result,
            "snapshots": _json_clone(self.snapshots),
            "undone_at": self.undone_at,
        }


@dataclass
class ActionHistoryLog:
    entries: list[ActionHistoryEntry] = field(default_factory=list)
    version: str = "action-history-v1"
    updated_at: str = field(default_factory=_now_iso)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionHistoryLog":
        return cls(
            entries=[
                ActionHistoryEntry.from_dict(item)
                for item in list(data.get("entries", []))
                if isinstance(item, dict)
            ],
            version=str(data.get("version") or "action-history-v1"),
            updated_at=str(data.get("updated_at") or _now_iso()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "entries": [entry.to_dict() for entry in self.entries[-80:]],
        }


class ActionHistoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or ACTION_HISTORY_PATH

    def load_log(self) -> ActionHistoryLog:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return ActionHistoryLog.from_dict(data)
        except FileNotFoundError:
            pass
        except Exception:
            pass
        return ActionHistoryLog()

    def save_log(self, log: ActionHistoryLog) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        log.updated_at = _now_iso()
        self.path.write_text(json.dumps(log.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def record(
        self,
        *,
        summary: str,
        plan_id: str,
        steps: list[str],
        snapshots: dict[str, Any],
        result: str,
        source: str = "action_plan",
        now: datetime | None = None,
    ) -> ActionHistoryEntry:
        log = self.load_log()
        entry = ActionHistoryEntry(
            id=uuid.uuid4().hex[:10],
            created_at=_now_iso(now),
            summary=summary,
            source=source,
            status="active",
            plan_id=plan_id,
            steps=list(steps),
            result=result,
            snapshots=_json_clone(snapshots),
        )
        log.entries.append(entry)
        log.entries = log.entries[-80:]
        self.save_log(log)
        return entry

    def recent(self, limit: int = 6) -> list[ActionHistoryEntry]:
        entries = list(reversed(self.load_log().entries))
        return entries[: max(1, limit)]

    def latest_undoable(self) -> ActionHistoryEntry | None:
        for entry in reversed(self.load_log().entries):
            if entry.status == "active" and entry.snapshots:
                return entry
        return None

    def mark_undone(self, entry_id: str, *, now: datetime | None = None) -> ActionHistoryEntry | None:
        log = self.load_log()
        updated: ActionHistoryEntry | None = None
        for entry in log.entries:
            if entry.id == entry_id:
                entry.status = "undone"
                entry.undone_at = _now_iso(now)
                updated = entry
                break
        if updated is not None:
            self.save_log(log)
        return updated

    def summary(self, limit: int = 6) -> str:
        entries = self.recent(limit)
        if not entries:
            return "No hay acciones registradas todavia."
        parts = []
        for index, entry in enumerate(entries, start=1):
            status = "revertida" if entry.status == "undone" else "activa"
            parts.append(f"{index}. {entry.summary} ({entry.created_at}, {status})")
        return "Acciones recientes: " + " ".join(parts)
