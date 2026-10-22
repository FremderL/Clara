from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from viernes_app.core.action_planner import ActionPlan
from viernes_app.core.decision import TOOL_CAPABILITIES, IntentDecision, ToolCapability, decision_for_intent


@dataclass(frozen=True)
class VerificationEvidence:
    kind: str
    detail: str
    confirmed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "detail": self.detail, "confirmed": self.confirmed}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VerificationEvidence":
        return cls(
            kind=str(data.get("kind") or "evidence"),
            detail=str(data.get("detail") or ""),
            confirmed=bool(data.get("confirmed", True)),
        )


@dataclass(frozen=True)
class ToolExecutionResult:
    action: str
    status: str
    message: str
    evidence: list[VerificationEvidence] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    changed_domains: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.status == "verified" and not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "status": self.status,
            "message": self.message,
            "success": self.success,
            "evidence": [item.to_dict() for item in self.evidence],
            "errors": list(self.errors),
            "changed_domains": list(self.changed_domains),
        }


@dataclass(frozen=True)
class ExecutionReceipt:
    id: str
    requested_action: str
    executed_action: str
    status: str
    success: bool
    timestamp: str
    evidence: list[VerificationEvidence] = field(default_factory=list)
    changed_domains: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    rollback_available: bool = False
    plan_id: str = ""
    result_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "requested_action": self.requested_action,
            "executed_action": self.executed_action,
            "status": self.status,
            "success": self.success,
            "timestamp": self.timestamp,
            "evidence": [item.to_dict() for item in self.evidence],
            "changed_domains": list(self.changed_domains),
            "errors": list(self.errors),
            "rollback_available": self.rollback_available,
            "plan_id": self.plan_id,
            "result_message": self.result_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionReceipt":
        return cls(
            id=str(data.get("id") or ""),
            requested_action=str(data.get("requested_action") or ""),
            executed_action=str(data.get("executed_action") or ""),
            status=str(data.get("status") or "unknown"),
            success=bool(data.get("success", False)),
            timestamp=str(data.get("timestamp") or ""),
            evidence=[
                VerificationEvidence.from_dict(item)
                for item in list(data.get("evidence", []))
                if isinstance(item, dict)
            ],
            changed_domains=[str(item) for item in list(data.get("changed_domains", []))],
            errors=[str(item) for item in list(data.get("errors", []))],
            rollback_available=bool(data.get("rollback_available", False)),
            plan_id=str(data.get("plan_id") or ""),
            result_message=str(data.get("result_message") or ""),
        )

    @classmethod
    def make(
        cls,
        *,
        requested_action: str,
        executed_action: str,
        status: str,
        success: bool,
        now: datetime,
        evidence: list[VerificationEvidence] | None = None,
        changed_domains: list[str] | None = None,
        errors: list[str] | None = None,
        rollback_available: bool = False,
        plan_id: str = "",
        result_message: str = "",
    ) -> "ExecutionReceipt":
        return cls(
            id=uuid.uuid4().hex[:12],
            requested_action=requested_action,
            executed_action=executed_action,
            status=status,
            success=success,
            timestamp=now.isoformat(timespec="seconds"),
            evidence=list(evidence or []),
            changed_domains=list(changed_domains or []),
            errors=list(errors or []),
            rollback_available=rollback_available,
            plan_id=plan_id,
            result_message=result_message,
        )


@dataclass(frozen=True)
class VerifiedActionPlan:
    plan: ActionPlan
    status: str = "draft"
    receipts: list[ExecutionReceipt] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.to_dict(),
            "status": self.status,
            "receipts": [receipt.to_dict() for receipt in self.receipts],
        }


class ToolRegistry:
    def __init__(self, capabilities: tuple[ToolCapability, ...] = TOOL_CAPABILITIES) -> None:
        self._capabilities = {capability.action: capability for capability in capabilities}

    def get(self, action: str) -> ToolCapability | None:
        return self._capabilities.get(action)

    def list_tools(self) -> list[dict[str, Any]]:
        return [capability.to_dict() for capability in self._capabilities.values()]

    def verification_requirements(self, action: str) -> list[str]:
        capability = self.get(action)
        if capability is None:
            return ["herramienta registrada"]
        if capability.mutates:
            return ["cambio persistido", "estado posterior distinto"]
        if action in {"research_topic"}:
            return ["resultado de investigacion no vacio"]
        if action == "open_app":
            return ["respuesta del sistema de apps"]
        if action == "send_telegram_notification":
            return ["confirmacion del API de Telegram"]
        return ["respuesta generada"]


class IntentArbiter:
    """Capa ligera que centraliza NLU, planificador y clarificador."""

    def __init__(
        self,
        *,
        nlu: Any,
        planner: Any,
        clarifier: Any,
        wake_query_detector: Callable[[str], bool],
        greeting_detector: Callable[[str], bool],
        normalizer: Callable[[str], str],
    ) -> None:
        self.nlu = nlu
        self.planner = planner
        self.clarifier = clarifier
        self.wake_query_detector = wake_query_detector
        self.greeting_detector = greeting_detector
        self.normalizer = normalizer

    def decide(self, original: str, now: datetime) -> IntentDecision:
        low = self.normalizer(original)
        if self.nlu is not None:
            result = self.nlu.classify(original)
            if result is not None:
                return decision_for_intent(
                    intent=result.intent,
                    confidence=result.confidence,
                    reason=result.reason,
                    slots=dict(result.slots),
                )
        plan = self.planner.create_plan(original, now) if self.planner is not None else None
        if plan is not None:
            return IntentDecision(
                intent=plan.intent or "action_plan",
                confidence=0.88,
                risk=plan.risk,
                handler="_plan_unprogrammed_action",
                reason="ActionPlanner genero un plan ejecutable",
                slots={"steps": len(plan.steps)},
                requires_confirmation=plan.requires_confirmation,
                mutates=any(step.mutates for step in plan.steps),
            )
        clarification = self.clarifier.evaluate(original, now) if self.clarifier is not None else None
        if clarification is not None:
            return IntentDecision(
                intent="clarify_action",
                confidence=0.74,
                risk="medium",
                handler="_clarify_ambiguous_action",
                reason="frase util pero ambigua; conviene pedir una opcion",
                slots={"subject": clarification.subject, "date": clarification.target_date},
                requires_confirmation=False,
                mutates=False,
            )
        if self.wake_query_detector(low):
            return decision_for_intent(
                intent="wake_schedule_query",
                confidence=0.91,
                reason="consulta natural de autoarranque/rutina matutina",
                slots={},
                handler="_wake_schedule_summary",
            )
        if self.greeting_detector(low):
            return decision_for_intent(intent="greeting", confidence=0.9, reason="saludo", handler="_greeting_response")
        return IntentDecision(
            intent="unknown",
            confidence=0.0,
            risk="low",
            handler="fallback",
            reason="sin regla local clara",
        )
