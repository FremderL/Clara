from __future__ import annotations

import json
import re
import unicodedata
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from viernes_app.paths import RUNTIME_DIR


MEMORY_ROOT = RUNTIME_DIR / "memory"


@dataclass(frozen=True)
class MemoryItem:
    id: str
    kind: str
    text: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "text": self.text,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryItem":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:12]),
            kind=str(data.get("kind") or "memory"),
            text=str(data.get("text") or ""),
            created_at=str(data.get("created_at") or ""),
            metadata=dict(data.get("metadata") or {}),
        )


class PersistentMemoryManager:
    """Memoria persistente para agentes sin romper los JSON historicos.

    Los datos nuevos viven en runtime/memory. El contexto enviado a Ollama se
    compacta, se limita por caracteres y redacta secretos comunes.
    """

    def __init__(self, root: Path | None = None, *, short_term_limit: int = 80) -> None:
        self.root = Path(root or MEMORY_ROOT)
        self.short_term_limit = max(10, int(short_term_limit or 80))
        self.root.mkdir(parents=True, exist_ok=True)
        self.short_term_path = self.root / "short_term.json"
        self.long_term_path = self.root / "long_term.json"
        self.conversations_path = self.root / "conversations.json"
        self.preferences_path = self.root / "preferences.json"
        self.projects_path = self.root / "projects.json"
        self.schema_path = self.root / "schema.json"
        self._ensure_schema()

    def remember(
        self,
        scope: str,
        key: str,
        value: Any,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem | None:
        clean_scope = _safe_key(scope)
        clean_key = _safe_key(key)
        text = str(value or "").strip()
        if clean_scope in {"short", "short_term", "corto_plazo"}:
            return self.remember_short_term(text, kind=clean_key or "observation", metadata=metadata)
        if clean_scope in {"long", "long_term", "largo_plazo", "fact"}:
            return self.remember_long_term(text, kind=clean_key or "fact", metadata=metadata)
        if clean_scope in {"conversation", "conversations", "historial"}:
            return self.record_conversation(clean_key or "user", text, metadata=metadata)
        if clean_scope in {"preference", "preferences", "preferencia"}:
            self.set_preference(clean_key, text)
            return None
        if clean_scope in {"project", "projects", "proyecto"}:
            data = dict(metadata or {})
            if text:
                data["description"] = text
            self.set_project(key, data)
            return None
        return self.remember_long_term(text, kind=clean_scope or "memory", metadata=metadata)

    def remember_short_term(
        self,
        text: str,
        *,
        kind: str = "observation",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem:
        item = self._item(kind, text, metadata)
        entries = self._load_list(self.short_term_path)
        entries.append(item.to_dict())
        self._save_list(self.short_term_path, entries[-self.short_term_limit :])
        return item

    def remember_long_term(
        self,
        text: str,
        *,
        kind: str = "fact",
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem:
        item = self._item(kind, text, metadata)
        entries = self._load_list(self.long_term_path)
        if item.text and not _contains_text(entries, item.text):
            entries.append(item.to_dict())
            self._save_list(self.long_term_path, entries[-1000:])
        return item

    def record_conversation(
        self,
        role: str,
        text: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem:
        item = self._item(f"conversation:{role}", text, metadata)
        entries = self._load_list(self.conversations_path)
        entries.append(item.to_dict())
        self._save_list(self.conversations_path, entries[-500:])
        if role == "user":
            self.remember_short_term(text, kind="last_user_message")
        return item

    def set_preference(self, key: str, value: str) -> None:
        prefs = self._load_dict(self.preferences_path)
        clean_key = _safe_key(key)
        if clean_key:
            prefs[clean_key] = {
                "value": str(value).strip(),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
            self._save_dict(self.preferences_path, prefs)

    def set_project(self, name: str, data: dict[str, Any] | None = None) -> None:
        projects = self._load_dict(self.projects_path)
        clean_name = str(name or "").strip()
        if clean_name:
            projects[clean_name] = {
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "data": dict(data or {}),
            }
            self._save_dict(self.projects_path, projects)

    def retrieve_context(self, query: str = "", *, limit: int = 8) -> list[MemoryItem]:
        tokens = set(_tokens(query))
        candidates = [
            MemoryItem.from_dict(item)
            for item in self._load_list(self.long_term_path) + self._load_list(self.short_term_path)
            if isinstance(item, dict)
        ]
        if not tokens:
            return candidates[-limit:]
        scored: list[tuple[int, MemoryItem]] = []
        for item in candidates:
            score = len(tokens.intersection(_tokens(item.text)))
            if score:
                scored.append((score, item))
        scored.sort(key=lambda pair: (pair[0], pair[1].created_at), reverse=True)
        return [item for _score, item in scored[:limit]]

    def forget(self, query: str, *, scopes: list[str] | None = None) -> int:
        tokens = set(_tokens(query))
        if not tokens:
            return 0
        selected = {_safe_key(scope) for scope in scopes} if scopes else {"short_term", "long_term", "preferences", "projects"}
        removed = 0
        if "short_term" in selected:
            removed += self._forget_from_list(self.short_term_path, tokens)
        if "long_term" in selected:
            removed += self._forget_from_list(self.long_term_path, tokens)
        if "preferences" in selected:
            removed += self._forget_from_dict(self.preferences_path, tokens)
        if "projects" in selected:
            removed += self._forget_from_dict(self.projects_path, tokens)
        return removed

    def build_ollama_context(self, prompt: str = "", limit: int = 1200) -> str:
        parts: list[str] = []
        prefs = self._load_dict(self.preferences_path)
        if prefs:
            pref_lines = [
                f"{key}: {_redact(value.get('value', ''))}"
                for key, value in list(prefs.items())[:8]
                if isinstance(value, dict)
            ]
            if pref_lines:
                parts.append("Preferencias persistentes: " + "; ".join(pref_lines))
        projects = self._load_dict(self.projects_path)
        if projects:
            parts.append("Proyectos activos: " + ", ".join(list(projects.keys())[:8]))
        memories = self.retrieve_context(prompt, limit=8)
        if prompt:
            latest_long_term = [
                MemoryItem.from_dict(item)
                for item in self._load_list(self.long_term_path)[-4:]
                if isinstance(item, dict)
            ]
            known_ids = {item.id for item in memories}
            memories.extend(item for item in latest_long_term if item.id not in known_ids)
        if memories:
            parts.append("Memoria relevante: " + " | ".join(_redact(item.text)[:160] for item in memories if item.text))
        recent = [
            MemoryItem.from_dict(item)
            for item in self._load_list(self.conversations_path)[-6:]
            if isinstance(item, dict)
        ]
        if recent:
            parts.append(
                "Conversacion persistente reciente: "
                + " | ".join(f"{item.kind}: {_redact(item.text)[:120]}" for item in recent)
            )
        text = " ".join(part for part in parts if part.strip())
        return text[: max(200, int(limit or 1200))]

    def context_for_ollama(self, query: str = "", *, max_chars: int = 1200) -> str:
        return self.build_ollama_context(query, max_chars)

    def snapshot(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "short_term_count": len(self._load_list(self.short_term_path)),
            "long_term_count": len(self._load_list(self.long_term_path)),
            "conversation_count": len(self._load_list(self.conversations_path)),
            "preferences": list(self._load_dict(self.preferences_path).keys()),
            "projects": list(self._load_dict(self.projects_path).keys()),
            "schema": self._load_dict(self.schema_path),
        }

    def _item(self, kind: str, text: str, metadata: dict[str, Any] | None = None) -> MemoryItem:
        return MemoryItem(
            id=uuid.uuid4().hex[:12],
            kind=str(kind or "memory"),
            text=str(text or "").strip(),
            created_at=datetime.now().isoformat(timespec="seconds"),
            metadata=dict(metadata or {}),
        )

    def _ensure_schema(self) -> None:
        if self.schema_path.exists():
            return
        self._save_dict(
            self.schema_path,
            {
                "version": 1,
                "stores": {
                    "short_term": "list[MemoryItem]",
                    "long_term": "list[MemoryItem]",
                    "conversations": "list[MemoryItem]",
                    "preferences": "dict[key,value,updated_at]",
                    "projects": "dict[name,data,updated_at]",
                },
            },
        )

    def _load_list(self, path: Path) -> list[dict[str, Any]]:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []
        return []

    def _forget_from_list(self, path: Path, tokens: set[str]) -> int:
        entries = self._load_list(path)
        kept = [item for item in entries if not _matches_tokens(str(item.get("text", "")), tokens)]
        removed = len(entries) - len(kept)
        if removed:
            self._save_list(path, kept)
        return removed

    def _forget_from_dict(self, path: Path, tokens: set[str]) -> int:
        data = self._load_dict(path)
        kept = {
            key: value
            for key, value in data.items()
            if not _matches_tokens(f"{key} {json.dumps(value, ensure_ascii=False)}", tokens)
        }
        removed = len(data) - len(kept)
        if removed:
            self._save_dict(path, kept)
        return removed

    def _save_list(self, path: Path, data: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _load_dict(self, path: Path) -> dict[str, Any]:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}
        return {}

    def _save_dict(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)


def _tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", str(text or "").lower())
    plain = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.findall(r"[a-z0-9_]+", plain)


def _contains_text(entries: list[dict[str, Any]], text: str) -> bool:
    needle = re.sub(r"\s+", " ", text.strip().lower())
    return any(re.sub(r"\s+", " ", str(item.get("text", "")).strip().lower()) == needle for item in entries)


def _safe_key(key: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(key or "").strip().lower()).strip("_")


def _redact(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)\b(token|password|passwd|secret|api[_-]?key)\s*[:=]\s*\S+", r"\1=[redacted]", text)
    text = re.sub(r"(?i)\b(bearer)\s+[a-z0-9._~+/=-]+", r"\1 [redacted]", text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", "[email redacted]", text)
    text = re.sub(r"\b\d{12,19}\b", "[number redacted]", text)
    return text


def _matches_tokens(text: str, tokens: set[str]) -> bool:
    haystack = set(_tokens(text))
    return bool(tokens.intersection(haystack))
