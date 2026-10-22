from __future__ import annotations

import json
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time as dt_time
from pathlib import Path
from typing import Any

from viernes_app.paths import PENDING_TASKS_PATH


def _now_iso(now: datetime | None = None) -> str:
    return (now or datetime.now()).isoformat(timespec="seconds")


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.lower().strip())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[¿?¡!.,;:\"'()]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _clean(text: str, limit: int = 180) -> str:
    return re.sub(r"\s+", " ", text).strip(" .,\t\r\n")[:limit]


@dataclass
class PendingTask:
    id: str
    title: str
    source: str = "manual"
    due_date: str = ""
    due_time: str = ""
    priority: str = "normal"
    state: str = "open"
    category: str = "general"
    next_action: str = ""
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    completed_at: str = ""
    cancelled_at: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PendingTask":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:10]),
            title=str(data.get("title") or "Pendiente"),
            source=str(data.get("source") or "manual"),
            due_date=str(data.get("due_date") or ""),
            due_time=str(data.get("due_time") or ""),
            priority=str(data.get("priority") or "normal"),
            state=str(data.get("state") or "open"),
            category=str(data.get("category") or "general"),
            next_action=str(data.get("next_action") or ""),
            created_at=str(data.get("created_at") or _now_iso()),
            updated_at=str(data.get("updated_at") or data.get("created_at") or _now_iso()),
            completed_at=str(data.get("completed_at") or ""),
            cancelled_at=str(data.get("cancelled_at") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "source": self.source,
            "due_date": self.due_date,
            "due_time": self.due_time,
            "priority": self.priority,
            "state": self.state,
            "category": self.category,
            "next_action": self.next_action,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "cancelled_at": self.cancelled_at,
        }

    def is_open(self) -> bool:
        return self.state == "open"


@dataclass
class PendingTaskBoard:
    tasks: list[PendingTask] = field(default_factory=list)
    version: str = "pending-tasks-v1"
    updated_at: str = field(default_factory=_now_iso)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PendingTaskBoard":
        return cls(
            tasks=[PendingTask.from_dict(item) for item in list(data.get("tasks", [])) if isinstance(item, dict)],
            version=str(data.get("version") or "pending-tasks-v1"),
            updated_at=str(data.get("updated_at") or _now_iso()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "tasks": [task.to_dict() for task in self.tasks[-300:]],
        }


class PendingTaskStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or PENDING_TASKS_PATH

    def load_board(self) -> PendingTaskBoard:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return PendingTaskBoard.from_dict(data)
        except FileNotFoundError:
            pass
        except Exception:
            pass
        return PendingTaskBoard()

    def save_board(self, board: PendingTaskBoard) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        board.updated_at = _now_iso()
        self.path.write_text(json.dumps(board.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def add_task(
        self,
        title: str,
        *,
        due_date: str = "",
        due_time: str = "",
        priority: str = "normal",
        category: str = "general",
        next_action: str = "",
        source: str = "manual",
        now: datetime | None = None,
    ) -> PendingTask:
        clean_title = _clean(title)
        if not clean_title:
            raise ValueError("empty pending task")
        board = self.load_board()
        duplicate = self._find_duplicate(board, clean_title, due_date)
        if duplicate is not None:
            duplicate.updated_at = _now_iso(now)
            duplicate.state = "open"
            duplicate.cancelled_at = ""
            duplicate.completed_at = ""
            if due_time:
                duplicate.due_time = due_time
            if next_action:
                duplicate.next_action = _clean(next_action)
            self.save_board(board)
            return duplicate
        task = PendingTask(
            id=uuid.uuid4().hex[:10],
            title=clean_title,
            source=source,
            due_date=self._valid_date_or_empty(due_date),
            due_time=self._valid_time_or_empty(due_time),
            priority=self._priority(priority),
            category=_clean(category or "general", limit=40) or "general",
            next_action=_clean(next_action),
            created_at=_now_iso(now),
            updated_at=_now_iso(now),
        )
        board.tasks.append(task)
        board.tasks = board.tasks[-300:]
        self.save_board(board)
        return task

    def open_tasks(self) -> list[PendingTask]:
        return self._sort_tasks([task for task in self.load_board().tasks if task.is_open()])

    def tasks_for_day(self, target_day: date) -> list[PendingTask]:
        key = target_day.isoformat()
        return self._sort_tasks([task for task in self.open_tasks() if task.due_date == key])

    def upcoming(self, now: datetime, *, days: int = 7, limit: int = 5) -> list[PendingTask]:
        end = now.date().toordinal() + max(0, days)
        tasks: list[PendingTask] = []
        for task in self.open_tasks():
            if not task.due_date:
                tasks.append(task)
                continue
            try:
                ordinal = date.fromisoformat(task.due_date).toordinal()
            except ValueError:
                continue
            if ordinal <= end:
                tasks.append(task)
        return self._sort_tasks(tasks)[:limit]

    def next_task(self, now: datetime) -> PendingTask | None:
        tasks = self.upcoming(now, days=14, limit=1)
        return tasks[0] if tasks else None

    def complete_task(self, query: str = "", *, now: datetime | None = None) -> PendingTask | None:
        return self._transition(query, "done", now=now)

    def cancel_task(self, query: str = "", *, now: datetime | None = None) -> PendingTask | None:
        return self._transition(query, "cancelled", now=now)

    def postpone_task(
        self,
        query: str,
        *,
        due_date: str,
        due_time: str = "",
        now: datetime | None = None,
    ) -> PendingTask | None:
        board = self.load_board()
        task = self._find_open_match(board, query)
        if task is None:
            return None
        task.due_date = self._valid_date_or_empty(due_date)
        if due_time:
            task.due_time = self._valid_time_or_empty(due_time)
        task.updated_at = _now_iso(now)
        self.save_board(board)
        return task

    def summary(self, *, limit: int = 6) -> str:
        tasks = self.open_tasks()
        if not tasks:
            return "No hay pendientes abiertos."
        return "Pendientes abiertos: " + " ".join(
            f"{index}. {self._task_label(task)}" for index, task in enumerate(tasks[:limit], start=1)
        )

    def summary_for_day(self, target_day: date, *, limit: int = 6) -> str:
        tasks = self.tasks_for_day(target_day)
        if not tasks:
            return f"No hay pendientes para {target_day.isoformat()}."
        return f"Pendientes de {target_day.isoformat()}: " + " ".join(
            f"{index}. {self._task_label(task)}" for index, task in enumerate(tasks[:limit], start=1)
        )

    def _transition(self, query: str, state: str, *, now: datetime | None = None) -> PendingTask | None:
        board = self.load_board()
        task = self._find_open_match(board, query)
        if task is None:
            return None
        stamp = _now_iso(now)
        task.state = state
        task.updated_at = stamp
        if state == "done":
            task.completed_at = stamp
        elif state == "cancelled":
            task.cancelled_at = stamp
        self.save_board(board)
        return task

    def _find_duplicate(self, board: PendingTaskBoard, title: str, due_date: str) -> PendingTask | None:
        normalized = _normalize(title)
        for task in board.tasks:
            if task.is_open() and _normalize(task.title) == normalized and str(task.due_date or "") == str(due_date or ""):
                return task
        return None

    def _find_open_match(self, board: PendingTaskBoard, query: str) -> PendingTask | None:
        open_tasks = self._sort_tasks([task for task in board.tasks if task.is_open()])
        if not open_tasks:
            return None
        normalized = _normalize(query)
        if not normalized or normalized in {"eso", "esto", "lo", "la", "ultimo", "ultima", "siguiente"}:
            return open_tasks[0]
        for task in open_tasks:
            if task.id.startswith(normalized):
                return task
        for task in open_tasks:
            haystack = _normalize(" ".join([task.title, task.next_action, task.category]))
            if normalized in haystack:
                return task
        tokens = [token for token in normalized.split() if len(token) > 2]
        if tokens:
            for task in open_tasks:
                haystack = _normalize(" ".join([task.title, task.next_action, task.category]))
                if all(token in haystack for token in tokens):
                    return task
        return None

    def _sort_tasks(self, tasks: list[PendingTask]) -> list[PendingTask]:
        priority_rank = {"high": 0, "normal": 1, "low": 2}

        def key(task: PendingTask) -> tuple[int, str, str, int, str]:
            due_missing = 1 if not task.due_date else 0
            due_date = task.due_date or "9999-12-31"
            due_time = task.due_time or "23:59"
            return (due_missing, due_date, due_time, priority_rank.get(task.priority, 1), task.created_at)

        return sorted(tasks, key=key)

    def _task_label(self, task: PendingTask) -> str:
        parts = [task.title]
        if task.due_date:
            due = f"vence {task.due_date}"
            if task.due_time:
                due += f" {task.due_time}"
            parts.append(due)
        if task.priority == "high":
            parts.append("prioridad alta")
        if task.next_action:
            parts.append(f"siguiente: {task.next_action}")
        if len(parts) == 1:
            return parts[0]
        return f"{parts[0]} ({', '.join(parts[1:])})"

    def _valid_date_or_empty(self, value: str) -> str:
        try:
            return date.fromisoformat(str(value)).isoformat()
        except Exception:
            return ""

    def _valid_time_or_empty(self, value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            return ""
        try:
            hour, minute = [int(part) for part in raw.split(":", 1)]
            dt_time(hour=hour, minute=minute)
            return f"{hour:02d}:{minute:02d}"
        except Exception:
            return ""

    def _priority(self, value: str) -> str:
        low = _normalize(value)
        if low in {"alta", "high", "urgente", "importante"}:
            return "high"
        if low in {"baja", "low"}:
            return "low"
        return "normal"
