from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from viernes_app.paths import RUNTIME_DIR


AUDIT_PATH = RUNTIME_DIR / "security_audit.json"


@dataclass(frozen=True)
class AuditEntry:
    id: str
    timestamp: str
    action: str
    decision: str
    level: int
    detail: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    actor: str = "local"
    target: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "action": self.action,
            "decision": self.decision,
            "level": self.level,
            "detail": self.detail,
            "metadata": dict(self.metadata),
            "correlation_id": self.correlation_id,
            "actor": self.actor,
            "target": self.target,
        }


class SecurityAuditLog:
    def __init__(self, path: Path | None = None, *, limit: int = 500) -> None:
        self.path = Path(path or AUDIT_PATH)
        self.limit = max(50, int(limit or 500))

    def record(
        self,
        action: str,
        decision: str,
        *,
        level: int,
        detail: str = "",
        metadata: dict[str, Any] | None = None,
        correlation_id: str = "",
        actor: str = "local",
        target: str = "",
    ) -> AuditEntry:
        clean_correlation = str(correlation_id or uuid.uuid4().hex[:12])
        entry = AuditEntry(
            id=clean_correlation,
            timestamp=datetime.now().isoformat(timespec="seconds"),
            action=str(action or ""),
            decision=str(decision or ""),
            level=int(level),
            detail=str(detail or ""),
            metadata=dict(metadata or {}),
            correlation_id=clean_correlation,
            actor=str(actor or "local"),
            target=str(target or ""),
        )
        entries = self.recent(limit=self.limit)
        entries.insert(0, entry.to_dict())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(entries[: self.limit], ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
        return entry

    def recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return [item for item in data[:limit] if isinstance(item, dict)]
        except (OSError, json.JSONDecodeError):
            return []
        return []
