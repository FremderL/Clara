from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from security.permissions import PermissionManager
from viernes_app.paths import REPO_ROOT, RUNTIME_DIR
from viernes_app.services.apps import open_application
from viernes_app.services.budget_service import handle_budget_command


ToolCallable = Callable[["ToolRequest", Any], "ToolResult"]


@dataclass(frozen=True)
class ToolRequest:
    name: str
    action: str
    text: str
    payload: dict[str, Any] = field(default_factory=dict)
    user_level: int | None = None
    confirmed: bool = False
    dry_run: bool = False
    correlation_id: str = ""


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    permission: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "message": self.message,
            "data": dict(self.data),
            "permission": dict(self.permission),
        }


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    action: str
    description: str
    handler: ToolCallable
    mutates: bool = False
    requires_confirmation: bool = False
    input_schema: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 60
    source: str = "builtin"


RegisteredTool = ToolDefinition


class ToolRouter:
    """Router dinamico de herramientas con validacion de permisos y auditoria."""

    def __init__(self, permissions: PermissionManager) -> None:
        self.permissions = permissions
        self._tools: dict[str, ToolDefinition] = {}
        self._register_builtin_tools()

    def register_tool(
        self,
        name: str,
        action: str,
        description: str,
        handler: ToolCallable,
        *,
        mutates: bool = False,
        requires_confirmation: bool | None = None,
        input_schema: dict[str, Any] | None = None,
        timeout_seconds: int = 60,
        source: str = "builtin",
    ) -> None:
        clean_name = _tool_name(name)
        if not clean_name:
            raise ValueError("La herramienta necesita nombre.")
        self._tools[clean_name] = ToolDefinition(
            clean_name,
            str(action or "plugin_tool"),
            str(description or ""),
            handler,
            bool(mutates),
            bool(mutates if requires_confirmation is None else requires_confirmation),
            dict(input_schema or {}),
            max(1, int(timeout_seconds or 60)),
            str(source or "builtin"),
        )

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "action": tool.action,
                "description": tool.description,
                "mutates": tool.mutates,
                "requires_confirmation": tool.requires_confirmation,
                "source": tool.source,
            }
            for tool in sorted(self._tools.values(), key=lambda item: item.name)
        ]

    def route(self, text: str, *, user_level: int | None = None) -> ToolRequest:
        original = str(text or "").strip()
        low = _normalize(original)
        confirmed = False
        dry_run = False
        if low.startswith(("confirmado ", "confirmada ", "aprobar ")):
            original = re.sub(r"^(confirmado|confirmada|aprobar)\s+", "", original, flags=re.IGNORECASE).strip()
            low = _normalize(original)
            confirmed = True
        if low.startswith(("dry run ", "previsualizar ", "simular ")):
            original = re.sub(r"^(dry run|previsualizar|simular)\s+", "", original, flags=re.IGNORECASE).strip()
            low = _normalize(original)
            dry_run = True

        direct = self._direct_tool_request(low, original, user_level, confirmed, dry_run)
        if direct is not None:
            return direct
        if _looks_like_document_organization(low):
            path = _extract_path_argument(original)
            return ToolRequest(
                "document_organizer_preview",
                "list_resources",
                original,
                {"path": path} if path else {},
                user_level,
                confirmed,
                dry_run,
            )
        if low.startswith(("clasificar recursos", "clasificar archivos", "detectar categorias")):
            path = re.sub(r"^(clasificar recursos|clasificar archivos|detectar categorias)\s*", "", original, flags=re.IGNORECASE).strip()
            return ToolRequest("classify_resources", "classify_resources", original, {"path": path}, user_level, confirmed, dry_run)
        if low.startswith(("aplicar organizacion documentos", "mover documentos organizados")):
            path = re.sub(r"^(aplicar organizacion documentos|mover documentos organizados)\s*", "", original, flags=re.IGNORECASE).strip()
            return ToolRequest("document_organizer_apply", "write_file", original, {"path": path}, user_level, confirmed, dry_run)
        if low.startswith(("abre ", "abrir ", "ejecuta programa ", "inicia ")):
            app = re.sub(r"^(abre|abrir|ejecuta programa|inicia)\s+", "", original, flags=re.IGNORECASE).strip()
            return ToolRequest("open_program", "open_program", original, {"app": app}, user_level, confirmed, dry_run)
        if low.startswith(("leer archivo ", "lee archivo ", "mostrar archivo ")):
            path = re.sub(r"^(leer archivo|lee archivo|mostrar archivo)\s+", "", original, flags=re.IGNORECASE).strip()
            return ToolRequest("read_file", "read_file", original, {"path": path}, user_level, confirmed, dry_run)
        if low.startswith(("listar recursos", "listar archivos", "analizar carpetas")):
            path = re.sub(r"^(listar recursos|listar archivos|analizar carpetas)\s*", "", original, flags=re.IGNORECASE).strip()
            return ToolRequest("list_resources", "list_resources", original, {"path": path or str(REPO_ROOT)}, user_level, confirmed, dry_run)
        if low.startswith(("escribir archivo ", "guardar archivo ")):
            body = re.sub(r"^(escribir archivo|guardar archivo)\s+", "", original, flags=re.IGNORECASE).strip()
            path, _, content = body.rpartition(":")
            return ToolRequest("write_file", "write_file", original, {"path": path.strip(), "content": content.strip()}, user_level, confirmed, dry_run)
        if low.startswith(("ejecutar script ", "corre script ")):
            path = re.sub(r"^(ejecutar script|corre script)\s+", "", original, flags=re.IGNORECASE).strip()
            return ToolRequest("execute_script", "execute_script", original, {"path": path}, user_level, confirmed, dry_run)
        if low.startswith(("generar informe ", "guardar informe ")):
            title = re.sub(r"^(generar informe|guardar informe)\s+", "", original, flags=re.IGNORECASE).strip()
            return ToolRequest("write_report", "write_report", original, {"title": title, "content": original}, user_level, confirmed, dry_run)
        if "agenda" in low:
            return ToolRequest("agenda_summary", "agenda_read", original, {}, user_level, confirmed, dry_run)
        if "presupuesto" in low or "balance" in low:
            return ToolRequest("budget_summary", "budget_read", original, {}, user_level, confirmed, dry_run)
        if "monitor seguridad" in low or "seguridad" in low:
            return ToolRequest("security_monitor", "security_monitor", original, {}, user_level, confirmed, dry_run)
        if "actividad personal" in low or "monitoreo personal" in low or "cuidado personal" in low:
            return ToolRequest("personal_activity_summary", "personal_activity_read", original, {}, user_level, confirmed, dry_run)
        if "memoria" in low:
            return ToolRequest("memory_context", "memory_read", original, {"query": original}, user_level, confirmed, dry_run)
        return ToolRequest("conversation", "conversation", original, {}, user_level, confirmed, dry_run)

    def execute(self, request: ToolRequest, runtime: Any = None) -> ToolResult:
        tool = self._tools.get(_tool_name(request.name))
        correlation_id = request.correlation_id or uuid.uuid4().hex[:12]
        if tool is None:
            return ToolResult(
                False,
                f"Herramienta no registrada: {request.name}. Siguiente paso: use 'herramientas registradas' y reintente con una herramienta disponible.",
                {"correlation_id": correlation_id, "next_step": "listar_herramientas"},
            )
        target = _target_from_payload(request.payload)
        confirmed = bool(request.confirmed or request.payload.get("confirmed"))
        decision = self.permissions.check(
            tool.action,
            target=target,
            level=request.user_level,
            confirmed=confirmed,
            correlation_id=correlation_id,
        )
        if not decision.allowed:
            return ToolResult(
                False,
                f"Permiso denegado para {tool.name}: {decision.reason}. Siguiente paso: revise permisos, ruta autorizada o nivel requerido.",
                {"correlation_id": correlation_id, "next_step": "revisar_permisos"},
                decision.to_dict(),
            )
        if (decision.requires_confirmation or tool.requires_confirmation) and not confirmed:
            return ToolResult(
                False,
                f"La herramienta {tool.name} requiere confirmacion explicita antes de ejecutar.",
                {
                    "requires_confirmation": True,
                    "tool": tool.name,
                    "correlation_id": correlation_id,
                    "next_step": f"confirmado {request.text}",
                },
                decision.to_dict(),
            )
        if request.dry_run and tool.mutates:
            return ToolResult(
                False,
                f"Dry-run: {tool.name} no se ejecuto porque muta estado.",
                {"dry_run": True, "tool": tool.name, "correlation_id": correlation_id, "next_step": "confirmar_si_es_correcto"},
                decision.to_dict(),
            )
        try:
            result = tool.handler(request, runtime)
            if not isinstance(result, ToolResult):
                result = ToolResult(True, str(result))
        except Exception as exc:
            return ToolResult(
                False,
                f"Error en herramienta {tool.name}: {exc}. Siguiente paso: revise entrada, permisos y estado del modulo; el router sigue activo.",
                {"correlation_id": correlation_id, "tool": tool.name, "next_step": "diagnosticar_herramienta"},
                decision.to_dict(),
            )
        data = dict(result.data)
        data.setdefault("correlation_id", correlation_id)
        if not result.ok:
            data.setdefault("next_step", _next_step_for_failure(tool.name, result.message))
        return ToolResult(result.ok, result.message, data, decision.to_dict())

    def execute_plan_step(
        self,
        step: Any,
        runtime: Any = None,
        *,
        user_level: int | None = None,
        confirmed: bool = False,
        dry_run: bool = False,
    ) -> str:
        text = getattr(step, "description", "") or getattr(step, "title", "")
        hint = _tool_name(str(getattr(step, "tool_hint", "") or ""))
        name = hint if hint in self._tools else "conversation"
        request = ToolRequest(
            name,
            self._tools.get(name, self._tools["conversation"]).action,
            text,
            dict(getattr(step, "payload", {}) or {}),
            user_level,
            confirmed,
            dry_run,
        )
        result = self.execute(request, runtime)
        return result.message

    def _register_builtin_tools(self) -> None:
        self.register_tool("conversation", "conversation", "Responder sin herramientas externas.", self._conversation)
        self.register_tool("open_program", "open_program", "Abrir aplicaciones registradas.", self._open_program)
        self.register_tool("read_file", "read_file", "Leer archivo autorizado.", self._read_file)
        self.register_tool("list_resources", "list_resources", "Listar archivos autorizados.", self._list_resources)
        self.register_tool("classify_resources", "classify_resources", "Clasificar archivos por tipo.", self._classify_resources)
        self.register_tool("document_organizer_preview", "list_resources", "Previsualizar organizacion de documentos.", self._document_organizer_preview)
        self.register_tool(
            "document_organizer_apply",
            "write_file",
            "Aplicar organizacion de documentos aprobada.",
            self._document_organizer_apply,
            mutates=True,
            requires_confirmation=True,
        )
        self.register_tool("write_report", "write_report", "Generar informe en runtime/reports.", self._write_report)
        self.register_tool("write_file", "write_file", "Escribir archivo autorizado.", self._write_file, mutates=True)
        self.register_tool("execute_script", "execute_script", "Ejecutar script autorizado.", self._execute_script, mutates=True)
        self.register_tool("agenda_summary", "agenda_read", "Consultar agenda de Viernes.", self._agenda_summary)
        self.register_tool("budget_summary", "budget_read", "Consultar presupuesto de Viernes.", self._budget_summary)
        self.register_tool("memory_context", "memory_read", "Recuperar memoria contextual.", self._memory_context)
        self.register_tool("security_monitor", "security_monitor", "Consultar diagnostico pasivo basico de seguridad.", self._security_monitor)
        self.register_tool("personal_activity_summary", "personal_activity_read", "Consultar actividad personal protegida.", self._personal_activity_summary)

    def _conversation(self, request: ToolRequest, runtime: Any) -> ToolResult:
        return ToolResult(True, "No hace falta herramienta externa; puedo responder en conversacion.")

    def _open_program(self, request: ToolRequest, runtime: Any) -> ToolResult:
        ok, message = open_application(str(request.payload.get("app", "") or request.text))
        return ToolResult(ok, message)

    def _read_file(self, request: ToolRequest, runtime: Any) -> ToolResult:
        path = _resolve_path(str(request.payload.get("path", "")))
        if not path.is_file():
            return ToolResult(False, f"No existe el archivo: {path}")
        text = path.read_text(encoding="utf-8", errors="replace")
        return ToolResult(True, text[:4000], {"path": str(path), "truncated": len(text) > 4000})

    def _list_resources(self, request: ToolRequest, runtime: Any) -> ToolResult:
        path = _resolve_path(str(request.payload.get("path") or REPO_ROOT))
        if not path.exists():
            return ToolResult(False, f"No existe la ruta: {path}")
        items = sorted(path.glob("*"), key=lambda item: (item.is_file(), item.name.lower()))
        names = [str(item.relative_to(path) if _is_relative_to(item, path) else item) for item in items[:80]]
        return ToolResult(True, "Recursos encontrados: " + (", ".join(names[:40]) or "ninguno"), {"path": str(path), "count": len(items)})

    def _classify_resources(self, request: ToolRequest, runtime: Any) -> ToolResult:
        path = _resolve_path(str(request.payload.get("path") or _default_documents_dir()))
        if not path.exists():
            return ToolResult(False, f"No existe la ruta: {path}")
        files = _candidate_files(path)
        counts: dict[str, int] = {}
        for item in files:
            category = _category_for(item)
            counts[category] = counts.get(category, 0) + 1
        message = "Categorias detectadas: " + (", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "ninguna")
        return ToolResult(True, message, {"path": str(path), "counts": counts, "sample_count": len(files)})

    def _document_organizer_preview(self, request: ToolRequest, runtime: Any) -> ToolResult:
        path = _resolve_path(str(request.payload.get("path") or _default_documents_dir()))
        if not path.exists():
            return ToolResult(False, f"No existe la ruta: {path}")
        plan = _organizer_plan(path)
        counts: dict[str, int] = {}
        for item in plan:
            counts[item["category"]] = counts.get(item["category"], 0) + 1
        preview = [f"{Path(item['source']).name} -> {Path(item['target']).parent.name}/" for item in plan[:12]]
        message = (
            f"Previsualizacion de organizacion en {path}: {len(plan)} archivo(s), "
            + (", ".join(f"{key}={value}" for key, value in sorted(counts.items())) or "sin movimientos")
        )
        if preview:
            message += ". Ejemplos: " + "; ".join(preview)
        return ToolResult(True, message, {"path": str(path), "plan": plan, "counts": counts, "dry_run": True})

    def _document_organizer_apply(self, request: ToolRequest, runtime: Any) -> ToolResult:
        path = _resolve_path(str(request.payload.get("path") or _default_documents_dir()))
        if not path.exists():
            return ToolResult(False, f"No existe la ruta: {path}")
        plan = request.payload.get("plan")
        if not isinstance(plan, list):
            plan = _organizer_plan(path)
        created_dirs: set[str] = set()
        moved: list[dict[str, str]] = []
        skipped: list[str] = []
        operation = str(request.payload.get("operation") or "all")
        for item in plan:
            if not isinstance(item, dict):
                continue
            source = Path(str(item.get("source", ""))).resolve()
            target = Path(str(item.get("target", ""))).resolve()
            if not source.is_file() or source == target:
                skipped.append(str(source))
                continue
            if not _is_relative_to(source, path) or not _is_relative_to(target, path):
                skipped.append(str(source))
                continue
            if operation in {"all", "create_dirs"}:
                target.parent.mkdir(parents=True, exist_ok=True)
                created_dirs.add(str(target.parent))
            if operation in {"all", "move_files"}:
                target.parent.mkdir(parents=True, exist_ok=True)
                final_target = _unique_target(target)
                shutil.move(str(source), str(final_target))
                moved.append({"source": str(source), "target": str(final_target)})
        report = {
            "created_dirs": sorted(created_dirs),
            "moved": moved,
            "skipped": skipped[:100],
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        report_result = self._write_report(
            ToolRequest(
                "write_report",
                "write_report",
                request.text,
                {"title": "Informe de organizacion de documentos", "content": json.dumps(report, ensure_ascii=False, indent=2)},
                request.user_level,
                True,
                False,
            ),
            runtime,
        )
        return ToolResult(
            True,
            f"Organizacion aplicada: {len(created_dirs)} directorio(s), {len(moved)} archivo(s). {report_result.message}",
            report,
        )

    def _write_report(self, request: ToolRequest, runtime: Any) -> ToolResult:
        title = str(request.payload.get("title") or "Informe de agente").strip() or "Informe de agente"
        content = str(request.payload.get("content") or request.text or "").strip()
        reports_dir = RUNTIME_DIR / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = reports_dir / f"agent_report_{stamp}.md"
        body = f"# {title}\n\nGenerado: {datetime.now().isoformat(timespec='seconds')}\n\n{content}\n"
        path.write_text(body, encoding="utf-8")
        return ToolResult(True, f"Informe generado: {path}", {"path": str(path)})

    def _write_file(self, request: ToolRequest, runtime: Any) -> ToolResult:
        path = _resolve_path(str(request.payload.get("path", "")))
        content = str(request.payload.get("content", ""))
        if not content:
            return ToolResult(False, "No escribi el archivo porque el contenido esta vacio.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ToolResult(True, f"Archivo escrito: {path}", {"path": str(path)})

    def _execute_script(self, request: ToolRequest, runtime: Any) -> ToolResult:
        path = _resolve_path(str(request.payload.get("path", "")))
        if not path.is_file():
            return ToolResult(False, f"No existe el script: {path}")
        if path.suffix.lower() not in {".bat", ".cmd", ".ps1", ".py"}:
            return ToolResult(False, "Solo ejecuto scripts .py, .ps1, .bat o .cmd autorizados.")
        if path.suffix.lower() == ".py":
            cmd = [sys.executable, str(path)]
        elif path.suffix.lower() == ".ps1":
            cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)]
        else:
            cmd = [str(path)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        output = (result.stdout or result.stderr or "").strip()
        ok = result.returncode == 0
        return ToolResult(ok, output[:3000] or f"Script terminado con codigo {result.returncode}.")

    def _agenda_summary(self, request: ToolRequest, runtime: Any) -> ToolResult:
        if runtime is not None and hasattr(runtime, "full_agenda_summary"):
            return ToolResult(True, runtime.full_agenda_summary())
        return ToolResult(False, "No hay runtime de agenda disponible.")

    def _budget_summary(self, request: ToolRequest, runtime: Any) -> ToolResult:
        response = handle_budget_command("presupuesto", "presupuesto")
        return ToolResult(bool(response), response or "No pude consultar presupuesto.")

    def _memory_context(self, request: ToolRequest, runtime: Any) -> ToolResult:
        manager = getattr(runtime, "agent_memory", None)
        if manager is None:
            return ToolResult(False, "La memoria persistente no esta disponible.")
        context = manager.build_ollama_context(str(request.payload.get("query", request.text)), 1200)
        return ToolResult(True, context or "Memoria sin contexto relevante.", manager.snapshot())

    def _security_monitor(self, request: ToolRequest, runtime: Any) -> ToolResult:
        monitor = getattr(runtime, "security_monitor", None)
        if monitor is None:
            return ToolResult(False, "Diagnostico pasivo de seguridad no disponible.")
        summary = monitor.summary()
        alerts = summary.get("alerts", [])
        if not alerts:
            return ToolResult(True, "Diagnostico pasivo basico: sin alertas activas en archivos vigilados y comprobaciones configuradas.", summary)
        preview = " | ".join(f"{item.get('severity')}: {item.get('message')}" for item in alerts[:4])
        return ToolResult(True, f"Diagnostico pasivo basico: {len(alerts)} alerta(s). {preview}", summary)

    def _personal_activity_summary(self, request: ToolRequest, runtime: Any) -> ToolResult:
        service = getattr(runtime, "personal_activity", None)
        if service is None:
            return ToolResult(False, "Monitoreo personal no disponible.")
        summary = service.summary(days=7)
        message = service.summary_message(days=7) if hasattr(service, "summary_message") else "Actividad personal consultada."
        return ToolResult(True, message, summary)

    def _direct_tool_request(
        self,
        low: str,
        original: str,
        user_level: int | None,
        confirmed: bool,
        dry_run: bool,
    ) -> ToolRequest | None:
        for name, tool in self._tools.items():
            label = name.replace("_", " ")
            if low == name or low == label:
                return ToolRequest(name, tool.action, original, {}, user_level, confirmed, dry_run)
            if low.startswith(name + " ") or low.startswith(label + " "):
                remainder = original[len(name):].strip() if low.startswith(name + " ") else original[len(label):].strip()
                return ToolRequest(name, tool.action, original, {"text": remainder}, user_level, confirmed, dry_run)
        return None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower().strip())


def _tool_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", str(name or "").strip().lower()).strip("_")


def _resolve_path(raw: str) -> Path:
    value = str(raw or "").strip().strip('"')
    if not value:
        return REPO_ROOT.resolve()
    path = Path(value)
    if not path.is_absolute():
        path = REPO_ROOT / value
    return path.resolve()


def _target_from_payload(payload: dict[str, Any]) -> str:
    for key in ("path", "target", "script"):
        value = payload.get(key)
        if value:
            return str(_resolve_path(str(value)))
    return ""


def _extract_path_argument(text: str) -> str:
    match = re.search(r"\b(?:en|de)\s+(.+)$", text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _looks_like_document_organization(low: str) -> bool:
    return any(word in low for word in ("documentos", "archivos", "carpetas")) and any(
        word in low for word in ("organiza", "ordenar", "clasifica", "acomoda", "reorganiza")
    )


def _default_documents_dir() -> Path:
    docs = Path.home() / "Documents"
    return docs if docs.exists() else REPO_ROOT


def _candidate_files(path: Path, *, limit: int = 500) -> list[Path]:
    if path.is_file():
        return [path]
    files: list[Path] = []
    for item in path.rglob("*"):
        if len(files) >= limit:
            break
        try:
            if item.is_file() and not any(part.startswith(".") for part in item.relative_to(path).parts):
                files.append(item)
        except OSError:
            continue
    return files


def _category_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".pdf"}:
        return "PDF"
    if suffix in {".doc", ".docx", ".txt", ".rtf", ".odt", ".md"}:
        return "Documentos"
    if suffix in {".xls", ".xlsx", ".csv", ".tsv", ".ods"}:
        return "Hojas_de_calculo"
    if suffix in {".ppt", ".pptx", ".odp"}:
        return "Presentaciones"
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}:
        return "Imagenes"
    if suffix in {".mp3", ".wav", ".m4a", ".flac", ".ogg"}:
        return "Audio"
    if suffix in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
        return "Video"
    if suffix in {".zip", ".rar", ".7z", ".tar", ".gz"}:
        return "Comprimidos"
    if suffix in {".py", ".js", ".ts", ".tsx", ".html", ".css", ".json", ".yaml", ".yml"}:
        return "Codigo"
    return "Otros"


def _organizer_plan(path: Path) -> list[dict[str, str]]:
    plan: list[dict[str, str]] = []
    for source in _candidate_files(path):
        category = _category_for(source)
        if source.parent.name == category:
            continue
        target = path / category / source.name
        plan.append({"source": str(source), "target": str(target), "category": category})
    return plan


def _unique_target(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    for index in range(1, 1000):
        candidate = parent / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
    return parent / f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _next_step_for_failure(tool_name: str, message: str) -> str:
    low = _normalize(message)
    if "no existe" in low:
        return "verificar_ruta"
    if "contenido esta vacio" in low:
        return "agregar_contenido"
    if "no disponible" in low:
        return "revisar_servicio"
    if "autoriz" in low or "allowlist" in low:
        return "revisar_permisos"
    if tool_name == "open_program":
        return "verificar_alias_app"
    return "reintentar_con_mas_detalle"
