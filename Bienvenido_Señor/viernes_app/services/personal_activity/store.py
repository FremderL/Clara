from __future__ import annotations

import hashlib
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from viernes_app.paths import RUNTIME_DIR
from viernes_app.services.personal_activity.protection import LocalDataProtector


ACTIVITY_ROOT = RUNTIME_DIR / "personal_activity"
ACTIVITY_DB_PATH = ACTIVITY_ROOT / "activity.sqlite3"


@dataclass(frozen=True)
class RetentionPolicy:
    raw_days: int = 14
    session_days: int = 60
    aggregate_days: int = 365

    @classmethod
    def from_config(cls, config: dict[str, Any] | None = None) -> "RetentionPolicy":
        cfg = config or {}
        return cls(
            raw_days=_bounded_int(cfg.get("raw_days", 14), 1, 90),
            session_days=_bounded_int(cfg.get("session_days", 60), 7, 730),
            aggregate_days=_bounded_int(cfg.get("aggregate_days", 365), 30, 3650),
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "raw_days": self.raw_days,
            "session_days": self.session_days,
            "aggregate_days": self.aggregate_days,
        }


class PersonalActivityStore:
    """Base local protegida para actividad personal y compactacion."""

    def __init__(
        self,
        db_path: Path | None = None,
        *,
        protector: LocalDataProtector | None = None,
        retention: RetentionPolicy | None = None,
    ) -> None:
        self.db_path = Path(db_path or ACTIVITY_DB_PATH)
        self.protector = protector or LocalDataProtector()
        self.retention = retention or RetentionPolicy()
        self._lock = threading.RLock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def record_event(
        self,
        kind: str,
        *,
        category: str = "system",
        payload: dict[str, Any] | None = None,
        when: datetime | None = None,
    ) -> str:
        stamp = when or datetime.now()
        event_id = uuid.uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO events(id, kind, timestamp, category, protected_payload)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    _safe_text(kind, "event", 80),
                    _iso(stamp),
                    _safe_text(category, "system", 60),
                    self.protector.protect_json(dict(payload or {})),
                ),
            )
        return event_id

    def start_session(
        self,
        *,
        process_name: str,
        app_key: str,
        category: str,
        title_fingerprint: str = "",
        payload: dict[str, Any] | None = None,
        source: str = "foreground",
        when: datetime | None = None,
    ) -> str:
        stamp = when or datetime.now()
        session_id = uuid.uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO app_sessions(
                    id, start_at, end_at, duration_seconds, process_name, app_key,
                    category, title_fingerprint, protected_payload, source, close_reason,
                    aggregated_at
                )
                VALUES (?, ?, NULL, 0, ?, ?, ?, ?, ?, ?, '', NULL)
                """,
                (
                    session_id,
                    _iso(stamp),
                    _safe_text(process_name, "unknown", 120),
                    _safe_text(app_key, "unknown", 120),
                    _safe_text(category, "other", 60),
                    _safe_text(title_fingerprint, "", 96),
                    self.protector.protect_json(dict(payload or {})),
                    _safe_text(source, "foreground", 60),
                ),
            )
            conn.execute("UPDATE meta SET value=? WHERE key='active_session_id'", (session_id,))
            if conn.total_changes == 1:
                conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('active_session_id', ?)", (session_id,))
        return session_id

    def close_session(self, session_id: str, *, when: datetime | None = None, reason: str = "changed") -> int:
        clean_id = str(session_id or "").strip()
        if not clean_id:
            return 0
        stamp = when or datetime.now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, start_at, end_at, app_key, category FROM app_sessions WHERE id=?",
                (clean_id,),
            ).fetchone()
            if row is None or row["end_at"]:
                return 0
            start = _parse_dt(row["start_at"]) or stamp
            duration = max(0, int((stamp - start).total_seconds()))
            conn.execute(
                """
                UPDATE app_sessions
                SET end_at=?, duration_seconds=?, close_reason=?
                WHERE id=? AND end_at IS NULL
                """,
                (_iso(stamp), duration, _safe_text(reason, "closed", 80), clean_id),
            )
            self._aggregate_session(conn, clean_id)
            active = self.get_meta("active_session_id")
            if active == clean_id:
                conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('active_session_id', '')")
            return duration

    def close_matching_open_session(
        self,
        *,
        app_key: str,
        source: str = "",
        when: datetime | None = None,
        reason: str = "closed",
    ) -> int:
        query = "SELECT id FROM app_sessions WHERE end_at IS NULL AND app_key=?"
        params: list[Any] = [_safe_text(app_key, "unknown", 120)]
        if source:
            query += " AND source=?"
            params.append(_safe_text(source, "foreground", 60))
        query += " ORDER BY start_at DESC LIMIT 1"
        with self._connect() as conn:
            row = conn.execute(query, tuple(params)).fetchone()
        if row is None:
            return 0
        return self.close_session(str(row["id"]), when=when, reason=reason)

    def get_open_session(self) -> dict[str, Any] | None:
        session_id = self.get_meta("active_session_id")
        if not session_id:
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM app_sessions WHERE id=? AND end_at IS NULL", (session_id,)).fetchone()
        return dict(row) if row is not None else None

    def set_meta(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", (_safe_text(key, "key", 80), str(value or "")))

    def get_meta(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key=?", (_safe_text(key, "key", 80),)).fetchone()
        return str(row["value"]) if row is not None else default

    def fingerprint(self, text: str) -> str:
        salt = self.get_meta("fingerprint_salt")
        if not salt:
            salt = uuid.uuid4().hex
            self.set_meta("fingerprint_salt", salt)
        return hashlib.sha256(f"{salt}:{text or ''}".encode("utf-8")).hexdigest()[:32]

    def heartbeat(self, when: datetime | None = None) -> None:
        self.set_meta("last_heartbeat_at", _iso(when or datetime.now()))

    def recover_open_sessions(self, when: datetime | None = None) -> int:
        stamp = when or datetime.now()
        last_raw = self.get_meta("last_heartbeat_at")
        recovered_end = _parse_dt(last_raw) or stamp
        if recovered_end > stamp:
            recovered_end = stamp
        closed = 0
        with self._connect() as conn:
            rows = conn.execute("SELECT id FROM app_sessions WHERE end_at IS NULL").fetchall()
        for row in rows:
            self.close_session(str(row["id"]), when=recovered_end, reason="recovered_after_restart")
            closed += 1
        return closed

    def maintain(self, when: datetime | None = None) -> dict[str, int]:
        stamp = when or datetime.now()
        event_cutoff = _iso(stamp - timedelta(days=self.retention.raw_days))
        session_cutoff = _iso(stamp - timedelta(days=self.retention.session_days))
        aggregate_cutoff = _iso(stamp - timedelta(days=self.retention.aggregate_days))
        stale_cutoff = stamp - timedelta(hours=18)
        closed_stale = 0
        with self._connect() as conn:
            stale_rows = conn.execute(
                "SELECT id FROM app_sessions WHERE end_at IS NULL AND start_at < ?",
                (_iso(stale_cutoff),),
            ).fetchall()
        for row in stale_rows:
            self.close_session(str(row["id"]), when=stale_cutoff, reason="stale_open_session")
            closed_stale += 1
        with self._connect() as conn:
            old_sessions = conn.execute(
                "SELECT id FROM app_sessions WHERE end_at IS NOT NULL AND start_at < ? AND aggregated_at IS NULL",
                (session_cutoff,),
            ).fetchall()
            for row in old_sessions:
                self._aggregate_session(conn, str(row["id"]))
            deleted_events = conn.execute("DELETE FROM events WHERE timestamp < ?", (event_cutoff,)).rowcount
            deleted_sessions = conn.execute(
                "DELETE FROM app_sessions WHERE end_at IS NOT NULL AND start_at < ?",
                (session_cutoff,),
            ).rowcount
            deleted_aggregates = conn.execute("DELETE FROM aggregates WHERE bucket < ?", (aggregate_cutoff[:10],)).rowcount
        return {
            "closed_stale_sessions": closed_stale,
            "deleted_events": int(deleted_events or 0),
            "deleted_sessions": int(deleted_sessions or 0),
            "deleted_aggregates": int(deleted_aggregates or 0),
            "aggregated_sessions": len(old_sessions),
        }

    def summary(self, *, days: int = 7, now: datetime | None = None) -> dict[str, Any]:
        stamp = now or datetime.now()
        cutoff = _iso(stamp - timedelta(days=max(1, days)))
        with self._connect() as conn:
            sessions = conn.execute(
                """
                SELECT app_key, category, source, COUNT(*) AS sessions, SUM(duration_seconds) AS seconds,
                       MIN(start_at) AS first_seen, MAX(COALESCE(end_at, start_at)) AS last_seen
                FROM app_sessions
                WHERE start_at >= ?
                GROUP BY app_key, category, source
                ORDER BY seconds DESC
                """,
                (cutoff,),
            ).fetchall()
            events = conn.execute(
                """
                SELECT kind, category, COUNT(*) AS count, MIN(timestamp) AS first_seen, MAX(timestamp) AS last_seen
                FROM events
                WHERE timestamp >= ?
                GROUP BY kind, category
                ORDER BY count DESC
                """,
                (cutoff,),
            ).fetchall()
            open_rows = conn.execute("SELECT * FROM app_sessions WHERE end_at IS NULL ORDER BY start_at DESC").fetchall()
        session_rows = [dict(row) for row in sessions]
        event_rows = [dict(row) for row in events]
        total_seconds = sum(int(row.get("seconds") or 0) for row in session_rows)
        youtube_seconds = sum(int(row.get("seconds") or 0) for row in session_rows if row.get("app_key") == "youtube")
        game_rows = [row for row in session_rows if str(row.get("category")) == "game"]
        recommendations = _recommendations(session_rows, event_rows, days=days)
        return {
            "enabled": True,
            "db_path": str(self.db_path),
            "protection_mode": self.protector.mode,
            "retention": self.retention.to_dict(),
            "days": days,
            "total_seconds": total_seconds,
            "youtube_seconds": youtube_seconds,
            "top_sessions": session_rows[:8],
            "events": event_rows[:8],
            "game_sessions": game_rows[:5],
            "open_sessions": [dict(row) for row in open_rows],
            "recommendations": recommendations,
            "counts": self.counts(),
        }

    def counts(self) -> dict[str, int]:
        with self._connect() as conn:
            return {
                "events": int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]),
                "sessions": int(conn.execute("SELECT COUNT(*) FROM app_sessions").fetchone()[0]),
                "open_sessions": int(conn.execute("SELECT COUNT(*) FROM app_sessions WHERE end_at IS NULL").fetchone()[0]),
                "aggregates": int(conn.execute("SELECT COUNT(*) FROM aggregates").fetchone()[0]),
            }

    def purge_all(self) -> dict[str, int]:
        with self._connect() as conn:
            events = conn.execute("DELETE FROM events").rowcount
            sessions = conn.execute("DELETE FROM app_sessions").rowcount
            aggregates = conn.execute("DELETE FROM aggregates").rowcount
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('active_session_id', '')")
        return {"events": int(events or 0), "sessions": int(sessions or 0), "aggregates": int(aggregates or 0)}

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return _LockedConnection(conn, self._lock)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events(
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    category TEXT NOT NULL,
                    protected_payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
                CREATE TABLE IF NOT EXISTS app_sessions(
                    id TEXT PRIMARY KEY,
                    start_at TEXT NOT NULL,
                    end_at TEXT,
                    duration_seconds INTEGER NOT NULL DEFAULT 0,
                    process_name TEXT NOT NULL,
                    app_key TEXT NOT NULL,
                    category TEXT NOT NULL,
                    title_fingerprint TEXT NOT NULL,
                    protected_payload TEXT NOT NULL,
                    source TEXT NOT NULL,
                    close_reason TEXT NOT NULL DEFAULT '',
                    aggregated_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_start ON app_sessions(start_at);
                CREATE INDEX IF NOT EXISTS idx_sessions_open ON app_sessions(end_at);
                CREATE TABLE IF NOT EXISTS aggregates(
                    id TEXT PRIMARY KEY,
                    period TEXT NOT NULL,
                    bucket TEXT NOT NULL,
                    app_key TEXT NOT NULL,
                    category TEXT NOT NULL,
                    total_seconds INTEGER NOT NULL DEFAULT 0,
                    sessions INTEGER NOT NULL DEFAULT 0,
                    event_count INTEGER NOT NULL DEFAULT 0,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(period, bucket, app_key, category)
                );
                CREATE INDEX IF NOT EXISTS idx_aggregates_bucket ON aggregates(bucket);
                """
            )
            conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES('active_session_id', '')")
            conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', '1')")

    def _aggregate_session(self, conn: sqlite3.Connection, session_id: str) -> None:
        row = conn.execute(
            """
            SELECT id, start_at, end_at, duration_seconds, app_key, category, aggregated_at
            FROM app_sessions
            WHERE id=?
            """,
            (session_id,),
        ).fetchone()
        if row is None or row["aggregated_at"] or not row["end_at"]:
            return
        start = _parse_dt(row["start_at"])
        if start is None:
            return
        seconds = int(row["duration_seconds"] or 0)
        for period, bucket in (("day", start.date().isoformat()), ("month", start.strftime("%Y-%m"))):
            conn.execute(
                """
                INSERT INTO aggregates(
                    id, period, bucket, app_key, category, total_seconds, sessions,
                    event_count, first_seen, last_seen, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?)
                ON CONFLICT(period, bucket, app_key, category) DO UPDATE SET
                    total_seconds=total_seconds + excluded.total_seconds,
                    sessions=sessions + 1,
                    first_seen=MIN(first_seen, excluded.first_seen),
                    last_seen=MAX(last_seen, excluded.last_seen),
                    updated_at=excluded.updated_at
                """,
                (
                    uuid.uuid4().hex[:12],
                    period,
                    bucket,
                    row["app_key"],
                    row["category"],
                    seconds,
                    row["start_at"],
                    row["end_at"],
                    _iso(datetime.now()),
                ),
            )
        conn.execute("UPDATE app_sessions SET aggregated_at=? WHERE id=?", (_iso(datetime.now()), session_id))


class _LockedConnection:
    def __init__(self, conn: sqlite3.Connection, lock: threading.RLock) -> None:
        self.conn = conn
        self.lock = lock

    def __enter__(self) -> sqlite3.Connection:
        self.lock.acquire()
        return self.conn

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        try:
            if exc_type is None:
                self.conn.commit()
            else:
                self.conn.rollback()
        finally:
            self.conn.close()
            self.lock.release()


def _recommendations(session_rows: list[dict[str, Any]], event_rows: list[dict[str, Any]], *, days: int) -> list[str]:
    recs: list[str] = []
    youtube_seconds = sum(int(row.get("seconds") or 0) for row in session_rows if row.get("app_key") == "youtube")
    game_seconds = sum(int(row.get("seconds") or 0) for row in session_rows if row.get("category") == "game")
    total_seconds = sum(int(row.get("seconds") or 0) for row in session_rows)
    avg_youtube_minutes = youtube_seconds / 60 / max(1, days)
    avg_game_minutes = game_seconds / 60 / max(1, days)
    if avg_youtube_minutes >= 90:
        recs.append("YouTube supera 90 min/dia en promedio; conviene proponer bloques con pausa o limite suave.")
    elif avg_youtube_minutes >= 45:
        recs.append("YouTube aparece como actividad relevante; Viernes puede sugerir cierre de sesion si hay pendientes.")
    if avg_game_minutes >= 60:
        recs.append("Hay sesiones de juego largas; conviene relacionarlas con horario de descanso y pendientes.")
    if total_seconds == 0:
        recs.append("Aun no hay sesiones suficientes para recomendaciones confiables.")
    if any(row.get("kind") == "runtime_recovered" for row in event_rows):
        recs.append("Se recuperaron sesiones tras reinicio; el sistema seguira cerrandolas con el ultimo heartbeat.")
    if not recs:
        recs.append("Actividad sin alertas fuertes; mantener compactacion automatica y revisar tendencias semanales.")
    return recs[:4]


def _bounded_int(value: Any, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = low
    return max(low, min(high, number))


def _safe_text(value: Any, default: str, limit: int) -> str:
    text = str(value or default).strip() or default
    return text[:limit]


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _parse_dt(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value or ""))
    except ValueError:
        return None
