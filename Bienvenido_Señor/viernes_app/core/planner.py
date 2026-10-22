from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from viernes_app.paths import RUNTIME_DIR


PLAN_STORE_PATH = RUNTIME_DIR / "agent_plans" / "plans.json"


@dataclass(frozen=True)
class AgentPlanStep:
    id: str
    title: str
    description: str
    tool_hint: str = ""
    priority: int = 50
    mutates: bool = False
    requires_confirmation: bool = False
    status: str = "pending"
    dependencies: list[str] = field(default_factory=list)
    rollback_hint: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "tool_hint": self.tool_hint,
            "priority": self.priority,
            "mutates": self.mutates,
            "requires_confirmation": self.requires_confirmation,
            "status": self.status,
            "dependencies": list(self.dependencies),
            "rollback_hint": self.rollback_hint,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentPlanStep":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:8]),
            title=str(data.get("title") or "Paso"),
            description=str(data.get("description") or ""),
            tool_hint=str(data.get("tool_hint") or ""),
            priority=int(data.get("priority", 50) or 50),
            mutates=bool(data.get("mutates", False)),
            requires_confirmation=bool(data.get("requires_confirmation", False)),
            status=str(data.get("status") or "pending"),
            dependencies=[str(item) for item in data.get("dependencies", []) if str(item).strip()]
            if isinstance(data.get("dependencies", []), list)
            else [],
            rollback_hint=str(data.get("rollback_hint") or ""),
            payload=dict(data.get("payload") or {}),
        )


@dataclass(frozen=True)
class AgentPlan:
    id: str
    objective: str
    summary: str
    steps: list[AgentPlanStep]
    created_at: str
    status: str = "draft"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def requires_confirmation(self) -> bool:
        return any(step.requires_confirmation or step.mutates for step in self.steps)

    def ordered_steps(self) -> list[AgentPlanStep]:
        return sorted(self.steps, key=lambda step: (step.priority, step.id))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "objective": self.objective,
            "summary": self.summary,
            "status": self.status,
            "created_at": self.created_at,
            "requires_confirmation": self.requires_confirmation,
            "metadata": dict(self.metadata),
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentPlan":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex[:10]),
            objective=str(data.get("objective") or ""),
            summary=str(data.get("summary") or ""),
            status=str(data.get("status") or "draft"),
            created_at=str(data.get("created_at") or datetime.now().isoformat(timespec="seconds")),
            metadata=dict(data.get("metadata") or {}),
            steps=[
                AgentPlanStep.from_dict(item)
                for item in list(data.get("steps", []))
                if isinstance(item, dict)
            ],
        )


@dataclass(frozen=True)
class AgentExecutionReport:
    plan_id: str
    status: str
    messages: list[str] = field(default_factory=list)
    completed_steps: int = 0
    blocked_steps: int = 0
    dry_run: bool = True
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "status": self.status,
            "messages": list(self.messages),
            "completed_steps": self.completed_steps,
            "blocked_steps": self.blocked_steps,
            "dry_run": self.dry_run,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


PlanStepExecutor = Callable[[AgentPlanStep], str]


class AgentPlanner:
    """Planificador de alto nivel para solicitudes complejas.

    Convierte objetivos abiertos en planes inspeccionables y persistidos. La
    ejecucion real queda delegada a herramientas registradas; los pasos que
    mutan estado se bloquean en dry-run o sin aprobacion explicita.
    """

    def __init__(self, store_path: Path | None = None) -> None:
        self.store_path = Path(store_path or PLAN_STORE_PATH)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def create_plan(
        self,
        objective: str,
        context: dict[str, Any] | None = None,
        *,
        now: datetime | None = None,
    ) -> AgentPlan:
        stamp = now or datetime.now()
        clean = _clean(objective)
        context = dict(context or {})
        steps = self._steps_for_objective(clean, context)
        plan = AgentPlan(
            id=uuid.uuid4().hex[:10],
            objective=str(objective or "").strip(),
            summary=self._summary(clean, steps),
            steps=steps,
            created_at=stamp.isoformat(timespec="seconds"),
            status="draft",
            metadata={
                "planner": "agent-planner-v2",
                "complexity": self._complexity(clean, steps),
                "context_keys": sorted(context.keys()),
            },
        )
        self.save_plan(plan)
        return plan

    def save_plan(self, plan: AgentPlan) -> None:
        plans = self._load_store()
        plans[plan.id] = plan.to_dict()
        self._save_store(plans)

    def get_plan(self, plan_id: str) -> AgentPlan | None:
        raw = self._load_store().get(str(plan_id or ""))
        return AgentPlan.from_dict(raw) if isinstance(raw, dict) else None

    def execute_plan(
        self,
        plan_id: str,
        executor: PlanStepExecutor | None = None,
        *,
        approvals: dict[str, bool] | None = None,
        dry_run: bool = True,
    ) -> AgentExecutionReport:
        plan = self.get_plan(plan_id)
        if plan is None:
            now = datetime.now().isoformat(timespec="seconds")
            return AgentExecutionReport(plan_id, "missing", ["Plan no encontrado."], 0, 1, dry_run, now, now)
        return self.execute_sequential(plan, executor or _preview_executor, approvals=approvals, dry_run=dry_run)

    def execute_sequential(
        self,
        plan: AgentPlan,
        executor: PlanStepExecutor,
        *,
        approvals: dict[str, bool] | None = None,
        dry_run: bool = True,
    ) -> AgentExecutionReport:
        approvals = dict(approvals or {})
        started = datetime.now().isoformat(timespec="seconds")
        messages: list[str] = []
        completed = 0
        blocked = 0
        completed_ids = {step.id for step in plan.steps if step.status == "completed"}

        for step in plan.ordered_steps():
            missing_dependencies = [dep for dep in step.dependencies if dep not in completed_ids]
            if missing_dependencies:
                blocked += 1
                messages.append(f"Bloqueado: {step.title} espera dependencias {', '.join(missing_dependencies)}.")
                continue
            if step.status == "completed":
                completed += 1
                completed_ids.add(step.id)
                continue
            if step.mutates or step.requires_confirmation:
                approved = bool(approvals.get(step.id) or approvals.get("all"))
                if dry_run:
                    blocked += 1
                    messages.append(f"Dry-run: {step.title} no se ejecuto porque muta estado.")
                    continue
                if not approved:
                    blocked += 1
                    messages.append(f"Bloqueado: {step.title} requiere aprobacion explicita.")
                    continue
            try:
                result = executor(step)
            except Exception as exc:
                blocked += 1
                messages.append(f"Error en {step.title}: {exc}")
                continue
            completed += 1
            completed_ids.add(step.id)
            messages.append(result or f"Completado: {step.title}")

        status = "completed" if blocked == 0 else "blocked"
        finished = datetime.now().isoformat(timespec="seconds")
        return AgentExecutionReport(plan.id, status, messages, completed, blocked, dry_run, started, finished)

    def mark_step(self, plan: AgentPlan, step_id: str, status: str) -> AgentPlan:
        steps = [replace(step, status=status) if step.id == step_id else step for step in plan.steps]
        updated = replace(plan, steps=steps)
        self.save_plan(updated)
        return updated

    def format_plan(self, plan: AgentPlan) -> str:
        lines = [f"Plan agente {plan.id}: {plan.summary}"]
        for index, step in enumerate(plan.ordered_steps(), start=1):
            marker = "requiere confirmacion" if step.requires_confirmation or step.mutates else "lectura/analisis"
            deps = f"; depende de {', '.join(step.dependencies)}" if step.dependencies else ""
            lines.append(f"{index}. {step.title}: {step.description} ({marker}{deps}).")
        if plan.requires_confirmation:
            lines.append("Ejecucion segura: primero dry-run; use aprobacion explicita para pasos que mutan estado.")
        return "\n".join(lines)

    def _steps_for_objective(self, clean: str, context: dict[str, Any]) -> list[AgentPlanStep]:
        if self._looks_like_document_organization(clean):
            root = str(context.get("path") or context.get("root") or "")
            first = _step(
                "Analizar carpetas",
                "Revisar carpetas candidatas y listar archivos sin mover nada.",
                "document_organizer_preview",
                10,
                payload={"path": root} if root else {},
            )
            second = _step(
                "Detectar categorias",
                "Inferir categorias por extension, nombre y ubicacion.",
                "classify_resources",
                20,
                dependencies=[first.id],
                payload={"path": root} if root else {},
            )
            third = _step(
                "Proponer estructura",
                "Disenar directorios destino antes de tocar archivos.",
                "write_report",
                30,
                dependencies=[second.id],
                payload={"title": "Propuesta de organizacion de documentos"},
            )
            fourth = _step(
                "Crear directorios",
                "Crear solo directorios aprobados por el usuario.",
                "document_organizer_apply",
                40,
                mutates=True,
                dependencies=[third.id],
                rollback_hint="Eliminar directorios creados si quedaron vacios.",
                payload={"path": root, "operation": "create_dirs"} if root else {"operation": "create_dirs"},
            )
            fifth = _step(
                "Mover archivos",
                "Mover archivos segun la clasificacion aprobada.",
                "document_organizer_apply",
                50,
                mutates=True,
                dependencies=[fourth.id],
                rollback_hint="Usar el informe de movimientos para devolver archivos a su origen.",
                payload={"path": root, "operation": "move_files"} if root else {"operation": "move_files"},
            )
            sixth = _step(
                "Generar informe",
                "Guardar un informe de cambios, omitidos y pendientes.",
                "write_report",
                60,
                dependencies=[fifth.id],
                payload={"title": "Informe de organizacion de documentos"},
            )
            return [first, second, third, fourth, fifth, sixth]
        if self._looks_like_code_improvement(clean):
            return [
                _step("Analizar codigo", "Detectar modulos afectados y riesgos de cambio.", "self_improvement_analyze", 10),
                _step("Disenar propuesta", "Generar una propuesta de parche sin modificar archivos.", "self_improvement_propose", 20),
                _step("Revisar seguridad", "Comprobar permisos, datos sensibles y alcance.", "security_review", 30),
                _step("Ejecutar pruebas", "Correr pruebas relevantes antes de aplicar cambios.", "run_tests", 40),
                _step("Solicitar aprobacion", "Esperar confirmacion explicita del usuario.", "approval_request", 50),
            ]
        if self._looks_like_research(clean):
            return [
                _step("Definir pregunta", "Convertir el objetivo en una pregunta verificable.", "memory_context", 10),
                _step("Buscar informacion", "Consultar herramientas internas o web segun permisos.", "search", 20),
                _step("Contrastar datos", "Separar hallazgos, incertidumbre y fuentes.", "analyze", 30),
                _step("Generar resumen", "Entregar respuesta accionable y guardar contexto util.", "write_report", 40),
            ]
        pieces = [piece for piece in re.split(r"\s+y\s+|[,;]", clean) if piece.strip()]
        if len(pieces) >= 2:
            return [
                _step(
                    f"Resolver parte {index}",
                    piece.strip().capitalize(),
                    "auto_route",
                    index * 10,
                    mutates=_may_mutate(piece),
                )
                for index, piece in enumerate(pieces, start=1)
            ]
        return [
            _step("Entender objetivo", "Identificar intencion, restricciones y datos faltantes.", "memory_context", 10),
            _step("Elegir herramienta", "Seleccionar herramienta segura segun la intencion.", "auto_route", 20),
            _step("Ejecutar o responder", "Ejecutar si es seguro; si no, pedir confirmacion.", "auto_route", 30),
        ]

    def _summary(self, clean: str, steps: list[AgentPlanStep]) -> str:
        if self._looks_like_document_organization(clean):
            return "organizar documentos con analisis previo, propuesta y cambios confirmables"
        if self._looks_like_code_improvement(clean):
            return "mejorar el proyecto mediante propuesta, pruebas y aprobacion"
        if self._looks_like_research(clean):
            return "investigar, contrastar y resumir informacion"
        return f"dividir el objetivo en {len(steps)} paso(s) secuenciales"

    def _complexity(self, clean: str, steps: list[AgentPlanStep]) -> str:
        if any(step.mutates for step in steps):
            return "high"
        if len(clean.split()) > 12 or len(steps) > 3:
            return "medium"
        return "low"

    def _looks_like_document_organization(self, clean: str) -> bool:
        return any(word in clean for word in ("documentos", "archivos", "carpetas")) and any(
            word in clean for word in ("organiza", "ordenar", "clasifica", "acomoda", "reorganiza")
        )

    def _looks_like_code_improvement(self, clean: str) -> bool:
        return any(word in clean for word in ("mejora", "refactor", "corrige", "optimiza")) and any(
            word in clean for word in ("codigo", "proyecto", "viernes", "modulo")
        )

    def _looks_like_research(self, clean: str) -> bool:
        return clean.startswith(("investiga", "busca", "analiza", "compara")) or "reporte" in clean

    def _load_store(self) -> dict[str, dict[str, Any]]:
        try:
            if self.store_path.exists():
                data = json.loads(self.store_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return {str(key): value for key, value in data.items() if isinstance(value, dict)}
        except (OSError, json.JSONDecodeError):
            return {}
        return {}

    def _save_store(self, data: dict[str, dict[str, Any]]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.store_path.with_suffix(self.store_path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.store_path)


def _step(
    title: str,
    description: str,
    tool_hint: str,
    priority: int,
    *,
    mutates: bool = False,
    dependencies: list[str] | None = None,
    rollback_hint: str = "",
    payload: dict[str, Any] | None = None,
) -> AgentPlanStep:
    return AgentPlanStep(
        id=uuid.uuid4().hex[:8],
        title=title,
        description=description,
        tool_hint=tool_hint,
        priority=priority,
        mutates=mutates,
        requires_confirmation=mutates,
        dependencies=list(dependencies or []),
        rollback_hint=rollback_hint,
        payload=dict(payload or {}),
    )


def _preview_executor(step: AgentPlanStep) -> str:
    return f"Previsualizado: {step.title}"


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _may_mutate(text: str) -> bool:
    return bool(re.search(r"\b(crea|crear|mueve|mover|borra|borrar|modifica|ejecuta|instala)\b", text))
