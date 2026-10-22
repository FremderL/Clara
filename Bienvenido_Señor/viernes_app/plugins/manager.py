from __future__ import annotations

import importlib.util
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class PluginManifest:
    name: str
    version: str
    description: str = ""
    enabled: bool = True
    trust_level: str = "local"
    required_level: int = 1
    capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "enabled": self.enabled,
            "trust_level": self.trust_level,
            "required_level": self.required_level,
            "capabilities": list(self.capabilities),
        }


@dataclass(frozen=True)
class PluginRecord:
    name: str
    version: str
    path: str
    enabled: bool
    tools: list[str] = field(default_factory=list)
    error: str = ""
    description: str = ""
    trust_level: str = "local"
    required_level: int = 1
    capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "path": self.path,
            "enabled": self.enabled,
            "tools": list(self.tools),
            "error": self.error,
            "description": self.description,
            "trust_level": self.trust_level,
            "required_level": self.required_level,
            "capabilities": list(self.capabilities),
        }


class PluginAPI:
    def __init__(self, *, tool_router: Any = None, assistant: Any = None, manifest: PluginManifest | None = None) -> None:
        self.tool_router = tool_router
        self.assistant = assistant
        self.manifest = manifest
        self.registered_tools: list[str] = []

    def register_tool(
        self,
        name: str,
        action: str,
        description: str,
        handler: Callable[..., Any],
        *,
        mutates: bool = False,
        requires_confirmation: bool | None = None,
        input_schema: dict[str, Any] | None = None,
    ) -> None:
        if self.tool_router is None:
            raise RuntimeError("No hay ToolRouter disponible para registrar herramientas.")
        clean_name = _tool_name(name)
        if not clean_name:
            raise ValueError("Nombre de herramienta invalido.")

        def wrapped(request: Any, runtime: Any) -> Any:
            result = handler(request, runtime)
            if hasattr(result, "ok") and hasattr(result, "message"):
                return result
            from viernes_app.core.tool_router import ToolResult

            return ToolResult(True, str(result))

        self.tool_router.register_tool(
            clean_name,
            action or "plugin_tool",
            description,
            wrapped,
            mutates=mutates,
            requires_confirmation=requires_confirmation,
            input_schema=input_schema,
            source=f"plugin:{self.manifest.name}" if self.manifest else "plugin",
        )
        self.registered_tools.append(clean_name)


class PluginManager:
    """Carga plugins locales desde subcarpetas con plugin.json y main.py."""

    def __init__(self, plugins_dir: Path, config: dict[str, Any] | None = None) -> None:
        self.plugins_dir = Path(plugins_dir)
        self.config = dict(config or {})
        self.records: list[PluginRecord] = []

    def discover(self) -> list[PluginRecord]:
        records: list[PluginRecord] = []
        if not self.plugins_dir.exists():
            return records
        for folder in sorted(item for item in self.plugins_dir.iterdir() if item.is_dir()):
            manifest_path = folder / "plugin.json"
            main_path = folder / "main.py"
            if not manifest_path.is_file() or not main_path.is_file():
                records.append(PluginRecord(folder.name, "", str(folder), False, error="Faltan plugin.json o main.py."))
                continue
            try:
                manifest = self._read_manifest(folder)
                records.append(
                    PluginRecord(
                        manifest.name,
                        manifest.version,
                        str(folder),
                        manifest.enabled and self._is_enabled(manifest.name),
                        description=manifest.description,
                        trust_level=manifest.trust_level,
                        required_level=manifest.required_level,
                        capabilities=list(manifest.capabilities),
                    )
                )
            except Exception as exc:
                records.append(PluginRecord(folder.name, "", str(folder), False, error=str(exc)))
        return records

    def load_enabled(self, *, tool_router: Any = None, assistant: Any = None) -> list[PluginRecord]:
        self.records = []
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
            return []
        for folder in sorted(item for item in self.plugins_dir.iterdir() if item.is_dir()):
            record = self._load_one(folder, tool_router=tool_router, assistant=assistant)
            self.records.append(record)
        return list(self.records)

    def load_plugins(self, *, tool_router: Any = None, assistant: Any = None, enabled: bool = True) -> list[PluginRecord]:
        if not enabled:
            self.records = []
            return []
        return self.load_enabled(tool_router=tool_router, assistant=assistant)

    def registered_tools(self) -> list[str]:
        tools: list[str] = []
        for record in self.records:
            tools.extend(record.tools)
        return sorted(set(tools))

    def summary(self) -> dict[str, Any]:
        return {
            "plugins_dir": str(self.plugins_dir),
            "loaded": sum(1 for record in self.records if record.enabled and not record.error),
            "errors": [record.to_dict() for record in self.records if record.error],
            "plugins": [record.to_dict() for record in self.records],
            "registered_tools": self.registered_tools(),
        }

    def _load_one(self, folder: Path, *, tool_router: Any = None, assistant: Any = None) -> PluginRecord:
        manifest_path = folder / "plugin.json"
        main_path = folder / "main.py"
        if not manifest_path.is_file() or not main_path.is_file():
            return PluginRecord(folder.name, "", str(folder), False, error="Faltan plugin.json o main.py.")
        try:
            manifest = self._read_manifest(folder)
            enabled = manifest.enabled and self._is_enabled(manifest.name)
            if not enabled:
                return _record_from_manifest(manifest, folder, enabled=False)
            spec = importlib.util.spec_from_file_location(f"viernes_plugin_{folder.name}", main_path)
            if spec is None or spec.loader is None:
                raise RuntimeError("No pude crear spec de importacion.")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            api = PluginAPI(tool_router=tool_router, assistant=assistant, manifest=manifest)
            register = getattr(module, "register", None)
            if not callable(register):
                raise RuntimeError("El plugin debe exponer register(api).")
            register(api)
            return _record_from_manifest(manifest, folder, enabled=True, tools=list(api.registered_tools))
        except Exception as exc:
            return PluginRecord(folder.name, "", str(folder), False, error=str(exc))

    def _read_manifest(self, folder: Path) -> PluginManifest:
        manifest_path = folder / "plugin.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("plugin.json debe ser objeto JSON.")
        name = _tool_name(str(data.get("name") or folder.name))
        if not name:
            raise ValueError("plugin.json requiere name valido.")
        version = str(data.get("version") or "").strip()
        if not version:
            raise ValueError("plugin.json requiere version.")
        capabilities = data.get("capabilities", [])
        if not isinstance(capabilities, list):
            raise ValueError("capabilities debe ser lista.")
        required_level = int(data.get("required_level", 1) or 1)
        required_level = max(0, min(3, required_level))
        return PluginManifest(
            name=name,
            version=version,
            description=str(data.get("description") or ""),
            enabled=bool(data.get("enabled", True)),
            trust_level=str(data.get("trust_level") or "local"),
            required_level=required_level,
            capabilities=[str(item) for item in capabilities if str(item).strip()],
        )

    def _is_enabled(self, name: str) -> bool:
        disabled = self.config.get("disabled", [])
        enabled = self.config.get("enabled_plugins", None)
        if isinstance(disabled, list) and name in {str(item) for item in disabled}:
            return False
        if isinstance(enabled, list):
            return name in {str(item) for item in enabled}
        return True


def _record_from_manifest(
    manifest: PluginManifest,
    folder: Path,
    *,
    enabled: bool,
    tools: list[str] | None = None,
) -> PluginRecord:
    return PluginRecord(
        manifest.name,
        manifest.version,
        str(folder),
        enabled,
        tools=list(tools or []),
        description=manifest.description,
        trust_level=manifest.trust_level,
        required_level=manifest.required_level,
        capabilities=list(manifest.capabilities),
    )


def _tool_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(name or "").strip().lower()).strip("_")
