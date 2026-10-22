from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from viernes_app.paths import REPO_ROOT

HISTORY_FILE = REPO_ROOT / "viernes_history.json"
TODOS_FILE = REPO_ROOT / "viernes_todos.json"
SECRETS_FILE = REPO_ROOT / "viernes_secrets.json"
SETTINGS_FILE = REPO_ROOT / "viernes_settings.json"


class ChatHistory:
    @staticmethod
    def load() -> list:
        try:
            if HISTORY_FILE.exists():
                with open(HISTORY_FILE, encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return []

    @staticmethod
    def save(messages: list) -> None:
        data = messages[-500:]
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


class TodosManager:
    @staticmethod
    def load() -> list:
        try:
            if TODOS_FILE.exists():
                with open(TODOS_FILE, encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return []

    @staticmethod
    def save(todos: list) -> None:
        with open(TODOS_FILE, "w", encoding="utf-8") as f:
            json.dump(todos, f, ensure_ascii=False, indent=2)

    @staticmethod
    def add(text: str) -> None:
        todos = TodosManager.load()
        todos.append({"text": text, "done": False, "created": datetime.now().isoformat()})
        TodosManager.save(todos)

    @staticmethod
    def toggle(index: int) -> None:
        todos = TodosManager.load()
        if 0 <= index < len(todos):
            todos[index]["done"] = not todos[index]["done"]
            TodosManager.save(todos)

    @staticmethod
    def delete(index: int) -> None:
        todos = TodosManager.load()
        if 0 <= index < len(todos):
            todos.pop(index)
            TodosManager.save(todos)


class SecretsManager:
    @staticmethod
    def load() -> dict:
        try:
            if SECRETS_FILE.exists():
                with open(SECRETS_FILE, encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return {}

    @staticmethod
    def save(name: str, value: str) -> None:
        secrets = SecretsManager.load()
        secrets[name] = value
        with open(SECRETS_FILE, "w", encoding="utf-8") as f:
            json.dump(secrets, f)

    @staticmethod
    def get(name: str) -> Optional[str]:
        return SecretsManager.load().get(name)


class SettingsManager:
    @staticmethod
    def load() -> dict:
        try:
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return {"muted": False, "alpha": 0.95}

    @staticmethod
    def save(settings: dict) -> None:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)