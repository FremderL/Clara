from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any

from viernes_app.services.personal_activity.probe import ActivitySnapshot, WindowsActivityProbe
from viernes_app.services.personal_activity.store import PersonalActivityStore, RetentionPolicy


class PersonalActivityService:
    """Monitoreo personal opt-in de apps, sesiones y cuidado."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        *,
        store: PersonalActivityStore | None = None,
        probe: WindowsActivityProbe | None = None,
    ) -> None:
        self.config = config if isinstance(config, dict) else {}
        retention = RetentionPolicy.from_config(self.config.get("retention", {}) if isinstance(self.config.get("retention", {}), dict) else {})
        self.store = store or PersonalActivityStore(retention=retention)
        self.probe = probe or WindowsActivityProbe()
        self.poll_interval_seconds = _bounded_int(self.config.get("poll_interval_seconds", 60), 10, 900)
        self.enabled = bool(self.config.get("enabled", False))
        self.privacy_mode = str(self.config.get("privacy_mode", "app_category") or "app_category")
        self._thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.RLock()

    def start(self) -> bool:
        if not self.enabled:
            return False
        with self._lock:
            if self._running:
                return True
            self._running = True
            recovered = self.store.recover_open_sessions()
            if recovered:
                self.store.record_event("runtime_recovered", category="system", payload={"closed_sessions": recovered})
            self.store.record_event("runtime_start", category="system", payload={"privacy_mode": self.privacy_mode})
            self.store.maintain()
            self.store.heartbeat()
            self._thread = threading.Thread(target=self._run, name="ViernesPersonalActivity", daemon=True)
            self._thread.start()
            return True

    def stop(self) -> None:
        with self._lock:
            if not self._running and not self.enabled:
                return
            self._running = False
        now = datetime.now()
        open_session = self.store.get_open_session()
        if open_session:
            self.store.close_session(str(open_session.get("id", "")), when=now, reason="runtime_stop")
        self.store.record_event("runtime_stop", category="system", payload={})
        self.store.heartbeat(now)

    def poll_once(self, now: datetime | None = None) -> dict[str, Any]:
        stamp = now or datetime.now()
        if not self.enabled:
            return {"ok": False, "reason": "disabled"}
        snapshot = self.probe.snapshot(stamp)
        self.store.heartbeat(stamp)
        if snapshot is None:
            self.store.record_event("sample_unavailable", category="system", payload={"source": "foreground_window"}, when=stamp)
            return {"ok": False, "reason": "snapshot_unavailable"}
        changed = self._apply_snapshot(snapshot, stamp)
        return {"ok": True, "changed": changed, "app_key": snapshot.app_key, "category": snapshot.category}

    def record_internal_game(self, game: str, action: str, *, status: str = "", when: datetime | None = None) -> None:
        if not self.enabled:
            return
        stamp = when or datetime.now()
        app_key = "game:" + _safe_key(game or "unknown")
        self.store.record_event(
            "internal_game",
            category="game",
            payload={"game": game, "action": action, "status": status},
            when=stamp,
        )
        if action == "game_start":
            self.store.close_matching_open_session(app_key=app_key, source="viernes_game", when=stamp, reason="new_game_start")
            self.store.start_session(
                process_name="viernes_internal_game",
                app_key=app_key,
                category="game",
                title_fingerprint=self.store.fingerprint(app_key),
                payload={"game": game, "source": "viernes"},
                source="viernes_game",
                when=stamp,
            )
        elif status == "finished" or action in {"game_end", "game_finish"}:
            self.store.close_matching_open_session(app_key=app_key, source="viernes_game", when=stamp, reason="game_finished")
        self.store.maintain(stamp)

    def summary(self, *, days: int = 7, now: datetime | None = None) -> dict[str, Any]:
        if not self.enabled:
            data = self.store.summary(days=days, now=now)
            data["enabled"] = False
            data["recommendations"] = ["Monitoreo personal desactivado. Active solo si quiere registrar actividad local."]
            return data
        self.store.maintain(now)
        data = self.store.summary(days=days, now=now)
        data["enabled"] = True
        data["running"] = self._running
        data["poll_interval_seconds"] = self.poll_interval_seconds
        data["privacy_mode"] = self.privacy_mode
        return data

    def status_message(self) -> str:
        summary = self.summary(days=7)
        counts = summary.get("counts", {})
        state = "activo" if summary.get("enabled") else "desactivado"
        running = "corriendo" if summary.get("running") else "en espera"
        return (
            f"Monitoreo personal {state} ({running}). "
            f"DB: {summary.get('db_path')}. Proteccion: {summary.get('protection_mode')}. "
            f"Sesiones={counts.get('sessions', 0)}, eventos={counts.get('events', 0)}, agregados={counts.get('aggregates', 0)}."
        )

    def summary_message(self, *, days: int = 7) -> str:
        summary = self.summary(days=days)
        if not summary.get("enabled"):
            return "Monitoreo personal desactivado. Diga 'activar monitoreo personal' para habilitarlo."
        top = []
        for row in summary.get("top_sessions", [])[:4]:
            minutes = int(row.get("seconds") or 0) // 60
            if minutes:
                top.append(f"{row.get('app_key')} {minutes} min")
        youtube_minutes = int(summary.get("youtube_seconds") or 0) // 60
        games = summary.get("game_sessions", [])
        recs = " ".join(f"{idx}. {text}" for idx, text in enumerate(summary.get("recommendations", [])[:3], start=1))
        return (
            f"Actividad de {days} dia(s): "
            f"top={', '.join(top) if top else 'sin sesiones cerradas'}, "
            f"YouTube={youtube_minutes} min, juegos={len(games)} tipo(s). "
            f"Recomendaciones: {recs}"
        )

    def purge_all(self) -> dict[str, int]:
        return self.store.purge_all()

    def run_maintenance(self) -> dict[str, int]:
        return self.store.maintain()

    def _run(self) -> None:
        while self._running:
            try:
                self.poll_once()
            except Exception as exc:
                self.store.record_event("monitor_error", category="system", payload={"error": str(exc)[:220]})
            time.sleep(self.poll_interval_seconds)

    def _apply_snapshot(self, snapshot: ActivitySnapshot, when: datetime) -> bool:
        title_fingerprint = self.store.fingerprint(snapshot.title) if snapshot.title else ""
        open_session = self.store.get_open_session()
        same = False
        if open_session:
            same = (
                str(open_session.get("app_key")) == snapshot.app_key
                and str(open_session.get("category")) == snapshot.category
                and str(open_session.get("title_fingerprint")) == title_fingerprint
                and str(open_session.get("source")) == snapshot.source
            )
        if same:
            return False
        if open_session:
            self.store.close_session(str(open_session.get("id", "")), when=when, reason="activity_changed")
        self.store.start_session(
            process_name=snapshot.process_name,
            app_key=snapshot.app_key,
            category=snapshot.category,
            title_fingerprint=title_fingerprint,
            payload=snapshot.safe_payload(),
            source=snapshot.source,
            when=when,
        )
        self.store.record_event(
            "activity_changed",
            category=snapshot.category,
            payload={"app_key": snapshot.app_key, "category": snapshot.category, "source": snapshot.source},
            when=when,
        )
        self.store.maintain(when)
        return True


def _bounded_int(value: Any, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = low
    return max(low, min(high, number))


def _safe_key(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(value or "").lower()).strip("_") or "unknown"
