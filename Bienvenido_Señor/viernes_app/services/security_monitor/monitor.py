from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from viernes_app.paths import (
    AGENDA_PATH,
    BUDGET_PATH,
    CONFIG_PATH,
    REPO_ROOT,
    RUNTIME_DIR,
    STATE_PATH,
)


BASELINE_PATH = RUNTIME_DIR / "security_monitor" / "baseline.json"


@dataclass(frozen=True)
class SecurityAlert:
    kind: str
    severity: str
    message: str
    recommendation: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "message": self.message,
            "recommendation": self.recommendation,
            "metadata": dict(self.metadata),
        }


class SecurityMonitor:
    """Monitor pasivo: observa y recomienda; no bloquea acciones."""

    def __init__(
        self,
        critical_files: list[Path] | None = None,
        *,
        baseline_path: Path | None = None,
        cache_seconds: int = 30,
    ) -> None:
        self.critical_files = critical_files or [CONFIG_PATH, STATE_PATH, AGENDA_PATH, BUDGET_PATH]
        self.baseline_path = Path(baseline_path or BASELINE_PATH)
        self.cache_seconds = max(1, int(cache_seconds or 30))
        self._baseline: dict[str, str] = self._load_baseline()
        self._last_summary: dict[str, Any] | None = None
        self._last_scan_monotonic = 0.0

    def snapshot_files(self) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        for path in self.critical_files:
            try:
                if path.exists() and path.is_file():
                    snapshot[str(path.resolve())] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                continue
        return snapshot

    def establish_baseline(self) -> dict[str, str]:
        self._baseline = self.snapshot_files()
        self._save_baseline(self._baseline)
        return dict(self._baseline)

    def scan(self, *, include_network: bool = True) -> list[SecurityAlert]:
        alerts: list[SecurityAlert] = []
        alerts.extend(self._file_alerts())
        alerts.extend(self._process_alerts())
        if include_network:
            alerts.extend(self._connection_alerts())
        return alerts

    def summary(self, *, max_age_seconds: int | None = None) -> dict[str, Any]:
        ttl = self.cache_seconds if max_age_seconds is None else max(0, int(max_age_seconds))
        now = time.monotonic()
        if self._last_summary is not None and now - self._last_scan_monotonic <= ttl:
            return dict(self._last_summary)
        alerts = self.scan(include_network=True)
        summary = {
            "critical_files": [str(path) for path in self.critical_files],
            "baseline_path": str(self.baseline_path),
            "alert_count": len(alerts),
            "alerts": [alert.to_dict() for alert in alerts],
            "mode": "passive_recommendation",
        }
        self._last_summary = summary
        self._last_scan_monotonic = now
        return dict(summary)

    def _file_alerts(self) -> list[SecurityAlert]:
        alerts: list[SecurityAlert] = []
        current = self.snapshot_files()
        for path in self.critical_files:
            if not path.exists():
                alerts.append(
                    SecurityAlert(
                        "critical_file_missing",
                        "high",
                        f"Archivo critico ausente: {path.name}",
                        "Restaure desde respaldo o valide que la migracion sea intencional.",
                        {"path": str(path)},
                    )
                )
        if not self._baseline:
            self._baseline = dict(current)
            self._save_baseline(self._baseline)
            return alerts
        for path, digest in current.items():
            if self._baseline.get(path) and self._baseline[path] != digest:
                alerts.append(
                    SecurityAlert(
                        "critical_file_changed",
                        "medium",
                        f"Archivo critico modificado: {Path(path).name}",
                        "Revise si el cambio fue esperado y conserve respaldo antes de seguir.",
                        {"path": path},
                    )
                )
        return alerts

    def _process_alerts(self) -> list[SecurityAlert]:
        try:
            result = subprocess.run(["tasklist"], capture_output=True, text=True, timeout=3)
            output = (result.stdout or "").lower()
        except Exception:
            return []
        suspicious = []
        for name in ("powershell.exe", "cmd.exe", "wscript.exe", "cscript.exe"):
            if output.count(name) > 5:
                suspicious.append(name)
        if not suspicious:
            return []
        return [
            SecurityAlert(
                "process_activity",
                "low",
                "Actividad elevada de procesos de scripting: " + ", ".join(suspicious),
                "Revise si corresponde a tareas de Viernes, instaladores o automatizacion esperada.",
                {"processes": suspicious},
            )
        ]

    def _connection_alerts(self) -> list[SecurityAlert]:
        alerts: list[SecurityAlert] = []
        for host, port, kind, message, recommendation in (
            (
                "api.telegram.org",
                443,
                "network_reachability",
                "Telegram no parece accesible ahora mismo.",
                "Si usa control remoto, verifique red/firewall antes de diagnosticar la app.",
            ),
            (
                "127.0.0.1",
                11434,
                "local_ai_unavailable",
                "Ollama local no responde en 127.0.0.1:11434.",
                "Active Ollama si quiere contexto enriquecido por IA local.",
            ),
        ):
            try:
                socket.create_connection((host, port), timeout=0.6).close()
            except Exception:
                alerts.append(SecurityAlert(kind, "info", message, recommendation, {"host": host, "port": port}))
        return alerts

    def _load_baseline(self) -> dict[str, str]:
        try:
            if self.baseline_path.exists():
                data = json.loads(self.baseline_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return {str(key): str(value) for key, value in data.items()}
        except (OSError, json.JSONDecodeError):
            return {}
        return {}

    def _save_baseline(self, data: dict[str, str]) -> None:
        self.baseline_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.baseline_path.with_suffix(self.baseline_path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.baseline_path)


def default_critical_files() -> list[Path]:
    return [REPO_ROOT / name for name in ("viernes_config.json", "viernes_state.json", "viernes_agenda.json", "viernes_budget.json")]
