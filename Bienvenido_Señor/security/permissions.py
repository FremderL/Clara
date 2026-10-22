from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from security.audit import SecurityAuditLog
from security.user_levels import UserLevel, coerce_user_level
from viernes_app.paths import REPO_ROOT, RUNTIME_DIR


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    action: str
    required_level: int
    current_level: int
    reason: str
    requires_confirmation: bool = False
    correlation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "action": self.action,
            "required_level": self.required_level,
            "current_level": self.current_level,
            "reason": self.reason,
            "requires_confirmation": self.requires_confirmation,
            "correlation_id": self.correlation_id,
        }


@dataclass(frozen=True)
class PermissionRule:
    action: str
    required_level: UserLevel
    description: str
    mutates: bool = False
    requires_confirmation: bool = False


DEFAULT_RULES: dict[str, PermissionRule] = {
    "conversation": PermissionRule("conversation", UserLevel.CONVERSATION, "Responder sin herramientas."),
    "auto_route": PermissionRule("auto_route", UserLevel.BASIC_TOOLS, "Seleccionar herramienta segura."),
    "open_program": PermissionRule("open_program", UserLevel.BASIC_TOOLS, "Abrir aplicaciones registradas."),
    "read_file": PermissionRule("read_file", UserLevel.BASIC_TOOLS, "Leer archivos dentro de recursos autorizados."),
    "list_resources": PermissionRule("list_resources", UserLevel.BASIC_TOOLS, "Listar recursos autorizados."),
    "classify_resources": PermissionRule("classify_resources", UserLevel.BASIC_TOOLS, "Clasificar recursos sin mutar."),
    "write_report": PermissionRule("write_report", UserLevel.BASIC_TOOLS, "Generar reportes en runtime."),
    "agenda_read": PermissionRule("agenda_read", UserLevel.BASIC_TOOLS, "Consultar agenda."),
    "budget_read": PermissionRule("budget_read", UserLevel.BASIC_TOOLS, "Consultar presupuesto."),
    "memory_read": PermissionRule("memory_read", UserLevel.BASIC_TOOLS, "Consultar memoria."),
    "memory_write": PermissionRule("memory_write", UserLevel.BASIC_TOOLS, "Guardar memoria de usuario.", True, False),
    "personal_activity_read": PermissionRule("personal_activity_read", UserLevel.BASIC_TOOLS, "Consultar actividad personal local."),
    "personal_activity_write": PermissionRule("personal_activity_write", UserLevel.MUTATION, "Modificar o borrar actividad personal.", True, True),
    "security_monitor": PermissionRule("security_monitor", UserLevel.BASIC_TOOLS, "Consultar monitor pasivo."),
    "voice_control": PermissionRule("voice_control", UserLevel.BASIC_TOOLS, "Controlar voz y wake word.", True, False),
    "ui_control": PermissionRule("ui_control", UserLevel.BASIC_TOOLS, "Cambiar modo de interfaz.", True, False),
    "plugin_tool": PermissionRule("plugin_tool", UserLevel.BASIC_TOOLS, "Ejecutar herramienta de plugin."),
    "self_improvement_analyze": PermissionRule("self_improvement_analyze", UserLevel.BASIC_TOOLS, "Analizar codigo sin cambios."),
    "self_improvement_propose": PermissionRule("self_improvement_propose", UserLevel.BASIC_TOOLS, "Generar propuesta sin cambios."),
    "security_review": PermissionRule("security_review", UserLevel.BASIC_TOOLS, "Revisar riesgos."),
    "run_tests": PermissionRule("run_tests", UserLevel.BASIC_TOOLS, "Ejecutar pruebas."),
    "approval_request": PermissionRule("approval_request", UserLevel.BASIC_TOOLS, "Solicitar aprobacion."),
    "write_file": PermissionRule("write_file", UserLevel.MUTATION, "Modificar archivos autorizados.", True, True),
    "agenda_write": PermissionRule("agenda_write", UserLevel.MUTATION, "Modificar agenda.", True, True),
    "execute_script": PermissionRule("execute_script", UserLevel.MUTATION, "Ejecutar scripts autorizados.", True, True),
    "admin_control": PermissionRule("admin_control", UserLevel.ADMIN, "Control administrativo completo.", True, True),
}


@dataclass
class PermissionPolicy:
    current_level: UserLevel = UserLevel.BASIC_TOOLS
    allowed_roots: list[Path] = field(default_factory=lambda: [REPO_ROOT, RUNTIME_DIR, Path.home() / "Documents"])
    allowed_scripts: list[Path] = field(default_factory=lambda: [REPO_ROOT / "scripts", RUNTIME_DIR / "scripts"])
    rules: dict[str, PermissionRule] = field(default_factory=lambda: dict(DEFAULT_RULES))


class PermissionManager:
    def __init__(self, policy: PermissionPolicy | None = None, audit_log: SecurityAuditLog | None = None) -> None:
        self.policy = policy or PermissionPolicy()
        self.audit_log = audit_log or SecurityAuditLog()

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "PermissionManager":
        security_cfg = config.get("security", {}) if isinstance(config, dict) else {}
        if not isinstance(security_cfg, dict):
            security_cfg = {}
        level = coerce_user_level(security_cfg.get("user_level", security_cfg.get("level", 1)))
        roots = _paths_from_config(security_cfg.get("allowed_roots"), [REPO_ROOT, RUNTIME_DIR, Path.home() / "Documents"])
        scripts = _paths_from_config(security_cfg.get("allowed_scripts"), [REPO_ROOT / "scripts", RUNTIME_DIR / "scripts"])
        return cls(PermissionPolicy(current_level=level, allowed_roots=roots, allowed_scripts=scripts))

    def register_rule(self, rule: PermissionRule) -> None:
        self.policy.rules[rule.action] = rule

    def check(
        self,
        action: str,
        *,
        target: str | Path = "",
        level: int | UserLevel | None = None,
        confirmed: bool = False,
        actor: str = "local",
        correlation_id: str = "",
    ) -> PermissionDecision:
        clean_action = str(action or "").strip()
        cid = str(correlation_id or uuid.uuid4().hex[:12])
        current = coerce_user_level(level, self.policy.current_level)
        rule = self.policy.rules.get(clean_action)
        if rule is None:
            decision = PermissionDecision(False, clean_action, int(UserLevel.ADMIN), int(current), "accion no registrada", False, cid)
            self._audit(decision, target=target, actor=actor)
            return decision
        if current < rule.required_level:
            decision = PermissionDecision(False, clean_action, int(rule.required_level), int(current), "nivel insuficiente", rule.requires_confirmation, cid)
            self._audit(decision, target=target, actor=actor)
            return decision
        if target and clean_action in {"read_file", "write_file", "list_resources", "classify_resources"}:
            if not self.is_authorized_path(target):
                decision = PermissionDecision(False, clean_action, int(rule.required_level), int(current), "ruta fuera de recursos autorizados", rule.requires_confirmation, cid)
                self._audit(decision, target=target, actor=actor)
                return decision
        if target and clean_action == "execute_script":
            if not self.is_authorized_script(target):
                decision = PermissionDecision(False, clean_action, int(rule.required_level), int(current), "script fuera de allowlist", rule.requires_confirmation, cid)
                self._audit(decision, target=target, actor=actor)
                return decision
        requires_confirmation = bool(rule.requires_confirmation and not confirmed)
        decision = PermissionDecision(True, clean_action, int(rule.required_level), int(current), "permitido", requires_confirmation, cid)
        self._audit(decision, target=target, actor=actor)
        return decision

    def require(
        self,
        action: str,
        *,
        target: str | Path = "",
        level: int | UserLevel | None = None,
        confirmed: bool = False,
    ) -> None:
        decision = self.check(action, target=target, level=level, confirmed=confirmed)
        if not decision.allowed or decision.requires_confirmation:
            raise PermissionError(f"{action}: {decision.reason}")

    def is_authorized_path(self, target: str | Path) -> bool:
        return _is_under_any_root(target, self.policy.allowed_roots)

    def is_authorized_script(self, target: str | Path) -> bool:
        return _is_under_any_root(target, self.policy.allowed_scripts)

    def summary(self) -> dict[str, Any]:
        return {
            "current_level": int(self.policy.current_level),
            "allowed_roots": [str(root) for root in self.policy.allowed_roots],
            "allowed_scripts": [str(root) for root in self.policy.allowed_scripts],
            "rules": {name: int(rule.required_level) for name, rule in self.policy.rules.items()},
            "confirmation_required": [name for name, rule in self.policy.rules.items() if rule.requires_confirmation],
        }

    def _audit(self, decision: PermissionDecision, *, target: str | Path = "", actor: str = "local") -> None:
        self.audit_log.record(
            decision.action,
            "allowed" if decision.allowed else "denied",
            level=decision.current_level,
            detail=decision.reason,
            metadata={"requires_confirmation": decision.requires_confirmation},
            correlation_id=decision.correlation_id,
            actor=actor,
            target=str(target) if target else "",
        )


def _paths_from_config(value: Any, defaults: list[Path]) -> list[Path]:
    roots = [Path(item).resolve() for item in defaults]
    if not isinstance(value, list):
        return roots
    for raw in value:
        try:
            roots.append(Path(str(raw)).resolve())
        except OSError:
            continue
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root).lower()
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def _is_under_any_root(target: str | Path, roots: list[Path]) -> bool:
    try:
        resolved = Path(target).resolve()
        for root in roots:
            try:
                resolved.relative_to(Path(root).resolve())
                return True
            except ValueError:
                continue
    except OSError:
        return False
    return False
