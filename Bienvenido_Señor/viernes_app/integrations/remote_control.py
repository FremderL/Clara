from __future__ import annotations

import random
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from viernes_app.core.decision import IntentDecision
from viernes_app.integrations.telegram import TelegramClient, TelegramSendResult, TelegramUpdate
from viernes_app.paths import REPO_ROOT, RUNTIME_DIR


CommandRunner = Callable[[str, datetime, bool], str]
DecisionResolver = Callable[[str, datetime], IntentDecision]
MessageSender = Callable[[str, str], bool]

REMOTE_TASK_NAME = "Viernes Remote Control"


@dataclass(frozen=True)
class RemoteOutgoingResponse:
    chat_id: str
    kind: str = "message"
    text: str = ""
    file_path: str = ""
    caption: str = ""
    reply_markup: dict[str, Any] | None = None


@dataclass(frozen=True)
class RemoteHistoryEntry:
    timestamp: str
    chat_id: str
    direction: str
    text: str
    status: str
    detail: str = ""
    permission: str = ""
    update_id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "chat_id": self.chat_id,
            "direction": self.direction,
            "text": self.text,
            "status": self.status,
            "detail": self.detail,
            "permission": self.permission,
            "update_id": self.update_id,
        }


@dataclass(frozen=True)
class RemoteCommandResult:
    accepted: bool
    message: str
    requires_confirmation: bool = False
    executed: bool = False
    permission: str = ""
    outgoing: list[RemoteOutgoingResponse] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class RemoteCallAdapter:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def handle(self, text: str) -> str:
        if not self.enabled:
            return "El adaptador de llamadas esta apagado por seguridad. No hice llamadas reales."
        return "El adaptador de llamadas aun no tiene proveedor configurado."


class RemoteControlService:
    def __init__(
        self,
        config: dict[str, Any],
        state: dict[str, Any],
        decision_resolver: DecisionResolver,
        command_runner: CommandRunner,
        sender: MessageSender | None = None,
        client: TelegramClient | None = None,
    ) -> None:
        self.config = config if isinstance(config, dict) else {}
        self.state = state
        self.decision_resolver = decision_resolver
        self.command_runner = command_runner
        self.sender = sender
        self.client = client
        calls_cfg = self.config.get("remote_calls", {})
        self.call_adapter = RemoteCallAdapter(bool(calls_cfg.get("enabled", False)) if isinstance(calls_cfg, dict) else False)

    def status(self) -> str:
        remote_cfg = self._remote_cfg()
        enabled = bool(remote_cfg.get("enabled", False))
        pending = self._remote_state().get("pending_confirmations", {})
        return (
            f"Control remoto Telegram: {'activo' if enabled else 'apagado'}. "
            f"Owners: {len(self._owner_chats())}. Trusted: {len(self._trusted_chats())}. "
            f"Solo lectura: {len(self._read_only_chats())}. Pendientes: {len(pending) if isinstance(pending, dict) else 0}. "
            f"Confirmacion para cambios: {'si' if remote_cfg.get('require_confirmation', True) else 'no'}."
        )

    def handle_text(self, chat_id: str, text: str, now: datetime, *, user_id: str = "", username: str = "") -> RemoteCommandResult:
        chat = str(chat_id).strip()
        clean = (text or "").strip()
        permission = self._permission(chat, user_id)
        self._append_history(now, chat, "in", clean, "received", permission=permission)
        if permission == "none":
            message = "Chat no autorizado para control remoto."
            self._append_history(now, chat, "out", message, "rejected", permission=permission)
            return RemoteCommandResult(False, message, permission=permission)
        if not clean:
            return self._result(now, chat, "Mensaje remoto vacio.", permission=permission)
        low = _normalize(clean)
        if re.search(r"\b(llama|llamar|telefono|llamada)\b", low):
            return self._result(now, chat, self.call_adapter.handle(clean), permission=permission)
        token = self._extract_confirmation_token(low)
        if token:
            return self._confirm_token(token, now, chat, permission)
        if low in {"cancelar", "cancelar confirmacion", "cancela confirmacion"}:
            return self._cancel_latest(now, chat, permission)
        if self._is_artifact_request(low):
            return self._artifact_request(now, chat, low, permission)
        if self._is_blocked_text(low):
            return self._result(now, chat, "Comando remoto bloqueado por seguridad.", permission=permission)

        decision = self.decision_resolver(clean, now)
        if not self._is_actionable_remote_decision(decision):
            self._append_history(now, chat, "out", f"ignorado: {decision.intent}", "ignored", permission=permission)
            return RemoteCommandResult(False, "", permission=permission)
        if self._is_blocked_intent(decision.intent):
            return self._result(now, chat, f"Intencion remota bloqueada: {decision.intent}.", permission=permission)
        if self._requires_confirmation(decision):
            if permission == "read_only":
                return self._result(now, chat, "Este chat es solo lectura; no puede confirmar ni ejecutar cambios.", permission=permission)
            token = self._store_confirmation(clean, decision, now, requester_chat=chat, requester_permission=permission)
            prompt = (
                f"Confirmacion requerida para ejecutar: {clean}. "
                f"Entendi {decision.intent}, riesgo {decision.risk}."
            )
            markup = _confirmation_markup(token)
            if permission == "trusted":
                owners = sorted(self._owner_chats())
                if not owners:
                    return self._result(now, chat, "No hay owner configurado para confirmar esta accion.", permission=permission)
                outgoing = [
                    RemoteOutgoingResponse(owner, text=prompt, reply_markup=markup)
                    for owner in owners
                ]
                self._append_history(now, chat, "out", "Pedi confirmacion al owner.", "pending", permission=permission)
                return RemoteCommandResult(
                    True,
                    "Pedi confirmacion al owner. La accion no se ejecutara hasta que se apruebe.",
                    requires_confirmation=True,
                    permission=permission,
                    outgoing=[RemoteOutgoingResponse(chat, text="Pedi confirmacion al owner. La accion no se ejecutara hasta que se apruebe.")] + outgoing,
                )
            message = prompt + f" Tambien puede responder: confirmar {token}"
            self._append_history(now, chat, "out", message, "pending", permission=permission)
            return RemoteCommandResult(
                True,
                message,
                requires_confirmation=True,
                permission=permission,
                outgoing=[RemoteOutgoingResponse(chat, text=message, reply_markup=markup)],
            )

        try:
            response = self.command_runner(clean, now, False)
        except Exception as exc:
            return self._result(now, chat, f"No pude ejecutar el comando remoto: {exc}", permission=permission)
        return self._executed_result(now, chat, clean, response, decision.intent, permission)

    def handle_callback(self, callback_query: dict[str, Any], now: datetime) -> RemoteCommandResult:
        callback_id = str(callback_query.get("id", "") or "")
        data = str(callback_query.get("data", "") or "")
        message = callback_query.get("message", {})
        chat = message.get("chat", {}) if isinstance(message, dict) else {}
        from_user = callback_query.get("from", {})
        chat_id = str(chat.get("id", "") if isinstance(chat, dict) else "")
        user_id = str(from_user.get("id", "") if isinstance(from_user, dict) else "")
        permission = self._permission(chat_id, user_id)
        self._append_history(now, chat_id, "in", data, "callback", permission=permission)
        if callback_id and self.client is not None:
            self.client.answer_callback_query(callback_id, "Procesando...")
        if permission != "owner":
            result = self._result(now, chat_id, "Solo un owner puede aprobar o cancelar acciones remotas.", permission=permission)
            if callback_id and self.client is not None:
                self.client.answer_callback_query(callback_id, "No autorizado.")
            return result
        match = re.match(r"^remote:(confirm|cancel):(\d{4,8})$", data)
        if not match:
            return self._result(now, chat_id, "Callback remoto no reconocido.", permission=permission)
        action, token = match.groups()
        if action == "cancel":
            result = self._cancel_token(token, now, chat_id, permission)
        else:
            result = self._confirm_token(token, now, chat_id, permission)
        if callback_id and self.client is not None:
            self.client.answer_callback_query(callback_id, "Listo." if result.accepted else "No se pudo.")
        return result

    def process_update(self, update: TelegramUpdate, now: datetime) -> list[RemoteCommandResult]:
        if update.message:
            chat = update.message.get("chat", {})
            from_user = update.message.get("from", {})
            if isinstance(from_user, dict) and bool(from_user.get("is_bot", False)):
                self._append_history(now, str(chat.get("id", "") if isinstance(chat, dict) else ""), "in", "mensaje de bot ignorado", "ignored")
                return []
            text = str(update.message.get("text", "") or "")
            if not text:
                self._append_history(now, str(chat.get("id", "") if isinstance(chat, dict) else ""), "in", "mensaje sin texto ignorado", "ignored")
                return []
            result = self.handle_text(
                str(chat.get("id", "") if isinstance(chat, dict) else ""),
                text,
                now,
                user_id=str(from_user.get("id", "") if isinstance(from_user, dict) else ""),
                username=str(from_user.get("username", "") if isinstance(from_user, dict) else ""),
            )
            result = self._send_result(now, result)
            return [result]
        if update.callback_query:
            result = self.handle_callback(update.callback_query, now)
            result = self._send_result(now, result)
            return [result]
        return []

    def poll_telegram(self, token: str, now: datetime) -> list[RemoteCommandResult]:
        client = self.client or TelegramClient(token)
        remote_state = self._remote_state()
        offset = int(remote_state.get("update_offset", 0) or 0)
        poll_timeout = int(self._remote_cfg().get("poll_timeout_seconds", 2) or 2)
        status, updates = client.get_updates(offset, timeout=poll_timeout)
        remote_state["last_poll_at"] = now.isoformat(timespec="seconds")
        if not status.ok:
            remote_state["last_error"] = status.description
            self._append_history(now, "", "system", "getUpdates", "error", detail=status.description)
            return [RemoteCommandResult(False, status.description, errors=[status.description])]
        remote_state["last_error"] = ""
        if offset <= 0 and updates and self._remote_cfg().get("drop_pending_on_start", True):
            newest = max(update.update_id for update in updates)
            remote_state["update_offset"] = newest + 1
            self._append_history(
                now,
                "",
                "system",
                f"ignore backlog inicial: {len(updates)} update(s)",
                "ignored",
                detail="Se descartaron mensajes previos para evitar spam al iniciar polling.",
            )
            return []
        results: list[RemoteCommandResult] = []
        for update in updates:
            remote_state["update_offset"] = max(int(remote_state.get("update_offset", 0) or 0), update.update_id + 1)
            try:
                results.extend(self.process_update(update, now))
            except Exception as exc:
                message = f"No pude procesar una actualizacion remota: {exc}"
                remote_state["last_error"] = message
                self._append_history(now, "", "system", "process_update", "error", detail=message, update_id=update.update_id)
                results.append(RemoteCommandResult(False, message, errors=[message]))
        return results

    def _send_result(self, now: datetime, result: RemoteCommandResult) -> RemoteCommandResult:
        sent_errors: list[str] = list(result.errors)
        sent_any = False
        outgoing = list(result.outgoing)
        if result.message and not outgoing:
            outgoing = [RemoteOutgoingResponse("", text=result.message)]
        for item in outgoing:
            chat_id = item.chat_id or self._last_incoming_chat()
            send_result = self._send_outgoing(item if item.chat_id else RemoteOutgoingResponse(chat_id, item.kind, item.text, item.file_path, item.caption, item.reply_markup))
            sent_any = sent_any or send_result.ok
            status = "sent" if send_result.ok else "error"
            detail = send_result.description
            label = item.text or item.caption or item.file_path
            self._append_history(now, chat_id, "out", label, status, detail=detail, permission=result.permission)
            if not send_result.ok:
                sent_errors.append(detail)
        if sent_errors:
            return RemoteCommandResult(
                result.accepted,
                result.message,
                result.requires_confirmation,
                result.executed,
                result.permission,
                result.outgoing,
                sent_errors,
            )
        return result

    def _send_outgoing(self, item: RemoteOutgoingResponse) -> TelegramSendResult:
        if self.client is not None:
            if item.kind == "photo":
                return self.client.send_photo(item.chat_id, item.file_path, caption=item.caption)
            if item.kind == "document":
                return self.client.send_document(item.chat_id, item.file_path, caption=item.caption)
            return self.client.send_message(item.chat_id, item.text, reply_markup=item.reply_markup)
        if self.sender is not None and item.kind == "message":
            ok = self.sender(item.chat_id, item.text)
            return TelegramSendResult(ok, "OK" if ok else "sender retorno false")
        return TelegramSendResult(False, "No hay cliente Telegram para enviar la respuesta.")

    def _executed_result(self, now: datetime, chat_id: str, command: str, response: str, intent: str, permission: str) -> RemoteCommandResult:
        outgoing = [RemoteOutgoingResponse(chat_id, text=response)] + self._artifact_responses(chat_id, command, intent)
        self._append_history(now, chat_id, "out", response, "executed", permission=permission)
        return RemoteCommandResult(True, response, executed=True, permission=permission, outgoing=outgoing)

    def _result(self, now: datetime, chat_id: str, message: str, *, permission: str) -> RemoteCommandResult:
        self._append_history(now, chat_id, "out", message, "ok", permission=permission)
        return RemoteCommandResult(True, message, permission=permission, outgoing=[RemoteOutgoingResponse(chat_id, text=message)])

    def _artifact_request(self, now: datetime, chat_id: str, low: str, permission: str) -> RemoteCommandResult:
        outgoing = self._artifact_responses(chat_id, low, "artifact_request", force=True)
        if not outgoing:
            return self._result(now, chat_id, "No encontre reporte o grafica reciente para enviar.", permission=permission)
        message = "Enviando archivo solicitado."
        self._append_history(now, chat_id, "out", message, "artifact", permission=permission)
        return RemoteCommandResult(True, message, executed=True, permission=permission, outgoing=[RemoteOutgoingResponse(chat_id, text=message)] + outgoing)

    def _artifact_responses(self, chat_id: str, command: str, intent: str, *, force: bool = False) -> list[RemoteOutgoingResponse]:
        if not self._remote_cfg().get("send_artifacts", True):
            return []
        low = _normalize(command)
        analysis_intents = {"simulation_request", "research_table", "chart_request", "analysis_report", "artifact_request"}
        if not force and intent not in analysis_intents:
            return []
        analysis = self.state.get("last_analysis", self.state.get("last_analysis_beta", {}))
        if not isinstance(analysis, dict):
            return []
        responses: list[RemoteOutgoingResponse] = []
        chart = analysis.get("chart", {}) if isinstance(analysis.get("chart", {}), dict) else {}
        chart_path = str(chart.get("path", "") or "")
        report_path = str(analysis.get("report_path", "") or "")
        wants_graph = "grafica" in low or "grafico" in low or intent == "chart_request"
        wants_report = "reporte" in low or "informe" in low or intent in {"analysis_report", "research_table", "simulation_request", "chart_request"}
        if (force or wants_graph) and chart_path and _is_allowed_report_file(chart_path):
            responses.append(RemoteOutgoingResponse(chat_id, kind="photo", file_path=chart_path, caption="Grafica generada por Viernes."))
        if (force or wants_report) and report_path and _is_allowed_report_file(report_path):
            responses.append(RemoteOutgoingResponse(chat_id, kind="document", file_path=report_path, caption="Reporte generado por Viernes."))
        return responses

    def _requires_confirmation(self, decision: IntentDecision) -> bool:
        if not self._remote_cfg().get("require_confirmation", True):
            return False
        return bool(decision.mutates or decision.requires_confirmation or decision.risk in {"medium", "high"})

    def _is_blocked_intent(self, intent: str) -> bool:
        blocked = _string_set(self._remote_cfg().get("blocked_intents", []))
        return intent in blocked

    def _is_blocked_text(self, low: str) -> bool:
        return bool(re.search(r"\b(apaga|apagar|reinicia|reiniciar|suspende|suspender|formatea|borra todo|cmd|powershell|terminal)\b", low))

    def _is_actionable_remote_decision(self, decision: IntentDecision) -> bool:
        if decision.intent in {"unknown", "greeting", "clarify_action"}:
            return False
        if decision.handler in {"fallback", "_ollama_fallback"}:
            return False
        if decision.confidence < 0.70:
            return False
        return True

    def _is_artifact_request(self, low: str) -> bool:
        return bool(re.search(r"\b(enviame|manda|mandame|envia|reenviar|reenvia)\b.*\b(ultimo|ultima)?\s*(reporte|grafica|grafico|png|archivo)\b", low))

    def _store_confirmation(self, command: str, decision: IntentDecision, now: datetime, *, requester_chat: str, requester_permission: str) -> str:
        token = f"{random.randint(1000, 9999)}"
        pending = self._remote_state().setdefault("pending_confirmations", {})
        pending[token] = {
            "command": command,
            "decision": decision.to_dict(),
            "requester_chat": requester_chat,
            "requester_permission": requester_permission,
            "expires_at": (now + timedelta(minutes=10)).isoformat(timespec="seconds"),
        }
        return token

    def _confirm_token(self, token: str, now: datetime, chat_id: str, permission: str) -> RemoteCommandResult:
        if permission != "owner":
            return self._result(now, chat_id, "Solo un owner puede confirmar acciones remotas.", permission=permission)
        pending = self._remote_state().setdefault("pending_confirmations", {})
        item = pending.pop(token, None)
        if not isinstance(item, dict):
            return self._result(now, chat_id, "No encontre una confirmacion remota vigente con ese token.", permission=permission)
        expires_at = _parse_datetime(str(item.get("expires_at", "") or ""), now)
        if expires_at < now:
            return self._result(now, chat_id, "La confirmacion remota expiro. Vuelva a enviar el comando.", permission=permission)
        command = str(item.get("command", "") or "")
        if not command:
            return self._result(now, chat_id, "La confirmacion remota no tenia comando asociado.", permission=permission)
        try:
            response = self.command_runner(command, now, True)
        except Exception as exc:
            return self._result(now, chat_id, f"No pude ejecutar la confirmacion remota: {exc}", permission=permission)
        decision = item.get("decision", {}) if isinstance(item.get("decision", {}), dict) else {}
        intent = str(decision.get("intent", "") or "")
        requester_chat = str(item.get("requester_chat", "") or chat_id)
        outgoing = [RemoteOutgoingResponse(chat_id, text=response)] + self._artifact_responses(chat_id, command, intent)
        if requester_chat and requester_chat != chat_id:
            outgoing.append(RemoteOutgoingResponse(requester_chat, text="El owner aprobo la accion. Resultado: " + response))
        self._append_history(now, chat_id, "out", response, "confirmed", permission=permission)
        return RemoteCommandResult(True, response, executed=True, permission=permission, outgoing=outgoing)

    def _cancel_latest(self, now: datetime, chat_id: str, permission: str) -> RemoteCommandResult:
        pending = self._remote_state().setdefault("pending_confirmations", {})
        if not isinstance(pending, dict) or not pending:
            return self._result(now, chat_id, "No hay confirmaciones remotas pendientes.", permission=permission)
        token = next(reversed(pending))
        return self._cancel_token(str(token), now, chat_id, permission)

    def _cancel_token(self, token: str, now: datetime, chat_id: str, permission: str) -> RemoteCommandResult:
        if permission not in {"owner", "trusted"}:
            return self._result(now, chat_id, "Este chat no puede cancelar confirmaciones remotas.", permission=permission)
        pending = self._remote_state().setdefault("pending_confirmations", {})
        item = pending.pop(token, None)
        if not isinstance(item, dict):
            return self._result(now, chat_id, "No encontre esa confirmacion remota.", permission=permission)
        return self._result(now, chat_id, "Confirmacion remota cancelada. No ejecute cambios.", permission=permission)

    def _extract_confirmation_token(self, low: str) -> str:
        match = re.search(r"^confirmar\s+(\d{4,8})$", low)
        return match.group(1) if match else ""

    def _permission(self, chat_id: str, user_id: str = "") -> str:
        chat = str(chat_id).strip()
        user = str(user_id).strip()
        if _matches_identity(chat, user, self._owner_chats()):
            return "owner"
        if _matches_identity(chat, user, self._trusted_chats()):
            return "trusted"
        if _matches_identity(chat, user, self._read_only_chats()):
            return "read_only"
        legacy = self._legacy_allowed_chats()
        if _matches_identity(chat, user, legacy):
            return "owner"
        return "none"

    def _owner_chats(self) -> set[str]:
        cfg = self._remote_cfg()
        owners = _string_set(cfg.get("owner_chat_ids", []))
        telegram = self.config.get("telegram", {})
        default_chat = str(telegram.get("chat_id", "") if isinstance(telegram, dict) else "").strip()
        if default_chat:
            owners.add(default_chat)
        if not owners:
            owners.update(self._legacy_allowed_chats())
        return owners

    def _trusted_chats(self) -> set[str]:
        return _string_set(self._remote_cfg().get("trusted_chat_ids", []))

    def _read_only_chats(self) -> set[str]:
        return _string_set(self._remote_cfg().get("read_only_chat_ids", []))

    def _legacy_allowed_chats(self) -> set[str]:
        return _string_set(self._remote_cfg().get("allowed_chat_ids", []))

    def _remote_cfg(self) -> dict[str, Any]:
        cfg = self.config.get("remote_control", {})
        return cfg if isinstance(cfg, dict) else {}

    def _remote_state(self) -> dict[str, Any]:
        remote = self.state.setdefault("remote_control", {})
        if not isinstance(remote, dict):
            remote = {}
            self.state["remote_control"] = remote
        remote.setdefault("pending_confirmations", {})
        remote.setdefault("history", [])
        return remote

    def _append_history(
        self,
        now: datetime,
        chat_id: str,
        direction: str,
        text: str,
        status: str,
        *,
        detail: str = "",
        permission: str = "",
        update_id: int = 0,
    ) -> None:
        remote = self._remote_state()
        remote["last_activity_at"] = now.isoformat(timespec="seconds")
        if status == "error":
            remote["last_error"] = detail or text
        history = remote.setdefault("history", [])
        if not isinstance(history, list):
            history = []
        entry = RemoteHistoryEntry(
            timestamp=now.isoformat(timespec="seconds"),
            chat_id=str(chat_id),
            direction=direction,
            text=_truncate(text, 500),
            status=status,
            detail=_truncate(detail, 500),
            permission=permission,
            update_id=update_id,
        )
        history.insert(0, entry.to_dict())
        limit = int(self._remote_cfg().get("history_limit", 100) or 100)
        remote["history"] = history[: max(10, min(500, limit))]

    def _last_incoming_chat(self) -> str:
        history = self._remote_state().get("history", [])
        if isinstance(history, list):
            for item in history:
                if isinstance(item, dict) and item.get("direction") == "in":
                    return str(item.get("chat_id", "") or "")
        return ""


def install_remote_resident_mode(loop_seconds: int = 5) -> tuple[bool, str]:
    task_action = f'"{sys.executable}" "{REPO_ROOT / "viernes.py"}" --mode remote --loop-seconds {max(5, int(loop_seconds))}'
    command = [
        "schtasks",
        "/Create",
        "/TN",
        REMOTE_TASK_NAME,
        "/SC",
        "ONLOGON",
        "/TR",
        task_action,
        "/F",
    ]
    return _run_task_command(command, "Control remoto residente activado.")


def remove_remote_resident_mode() -> tuple[bool, str]:
    return _run_task_command(["schtasks", "/Delete", "/TN", REMOTE_TASK_NAME, "/F"], "Control remoto residente desactivado.")


def get_remote_resident_status() -> dict[str, str]:
    try:
        result = subprocess.run(["schtasks", "/Query", "/TN", REMOTE_TASK_NAME, "/FO", "LIST"], capture_output=True, text=True, timeout=20)
        output = (result.stdout or result.stderr or "").strip()
        if result.returncode == 0:
            return {"task": "ready", "detail": output}
        return {"task": "missing", "detail": output}
    except Exception as exc:
        return {"task": "unknown", "detail": str(exc)}


def _run_task_command(command: list[str], success_message: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=45)
        output = (result.stdout or result.stderr or "").strip()
        if result.returncode == 0:
            return True, output or success_message
        return False, output or "No pude actualizar la tarea residente remota."
    except Exception as exc:
        return False, f"No pude actualizar la tarea residente remota: {exc}"


def _confirmation_markup(token: str) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "Confirmar", "callback_data": f"remote:confirm:{token}"},
                {"text": "Cancelar", "callback_data": f"remote:cancel:{token}"},
            ]
        ]
    }


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _string_set(value: Any) -> set[str]:
    if isinstance(value, str):
        raw = re.split(r"[\s,;]+", value)
    elif isinstance(value, list):
        raw = value
    else:
        raw = []
    return {str(item).strip() for item in raw if str(item).strip()}


def _matches_identity(chat_id: str, user_id: str, identities: set[str]) -> bool:
    return bool((chat_id and chat_id in identities) or (user_id and user_id in identities))


def _parse_datetime(raw: str, fallback: datetime) -> datetime:
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return fallback


def _is_allowed_report_file(path: str) -> bool:
    try:
        target = Path(path).resolve()
        reports_root = (RUNTIME_DIR / "reports").resolve()
        target.relative_to(reports_root)
        return target.exists() and target.is_file()
    except Exception:
        return False


def _truncate(text: str, limit: int) -> str:
    value = str(text or "")
    return value if len(value) <= limit else value[: limit - 3] + "..."


def _telegram_get_updates(token: str, offset: int) -> list[dict[str, Any]]:
    status, updates = TelegramClient(token).get_updates(offset)
    if not status.ok:
        return []
    return [
        {
            "update_id": update.update_id,
            "message": update.message,
            "callback_query": update.callback_query,
        }
        for update in updates
    ]
