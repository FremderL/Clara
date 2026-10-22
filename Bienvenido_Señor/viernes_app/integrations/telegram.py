from __future__ import annotations

import json
import mimetypes
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TelegramSendResult:
    ok: bool
    description: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    status_code: int = 0


@dataclass(frozen=True)
class TelegramUpdate:
    update_id: int
    message: dict[str, Any] = field(default_factory=dict)
    callback_query: dict[str, Any] = field(default_factory=dict)


class TelegramClient:
    def __init__(self, token: str = "") -> None:
        self.token = str(token or "").strip()

    def is_configured(self) -> bool:
        return bool(self.token)

    def send_message(
        self,
        chat_id: str,
        text: str,
        *,
        reply_markup: dict[str, Any] | None = None,
        parse_mode: str | None = None,
    ) -> TelegramSendResult:
        payload: dict[str, Any] = {"chat_id": str(chat_id), "text": _limit_text(text)}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return self._post_json("sendMessage", payload)

    def send_photo(self, chat_id: str, file_path: str | Path, *, caption: str = "") -> TelegramSendResult:
        return self._post_file("sendPhoto", chat_id, "photo", file_path, caption=caption)

    def send_document(self, chat_id: str, file_path: str | Path, *, caption: str = "") -> TelegramSendResult:
        return self._post_file("sendDocument", chat_id, "document", file_path, caption=caption)

    def answer_callback_query(self, callback_query_id: str, text: str = "") -> TelegramSendResult:
        payload = {"callback_query_id": str(callback_query_id)}
        if text:
            payload["text"] = _limit_text(text, limit=200)
        return self._post_json("answerCallbackQuery", payload)

    def get_updates(self, offset: int = 0, *, timeout: int = 2) -> tuple[TelegramSendResult, list[TelegramUpdate]]:
        if not self.token:
            return TelegramSendResult(False, "Telegram token vacio."), []
        params = urllib.parse.urlencode({"timeout": int(timeout), "offset": int(offset)})
        req = urllib.request.Request(f"https://api.telegram.org/bot{self.token}/getUpdates?{params}")
        try:
            with urllib.request.urlopen(req, timeout=max(5, int(timeout) + 3)) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            ok = bool(payload.get("ok", False))
            if not ok:
                return TelegramSendResult(False, str(payload.get("description", "Telegram rechazo getUpdates.")), payload), []
            updates = []
            for item in payload.get("result", []):
                if isinstance(item, dict):
                    updates.append(
                        TelegramUpdate(
                            update_id=int(item.get("update_id", 0) or 0),
                            message=item.get("message", {}) if isinstance(item.get("message", {}), dict) else {},
                            callback_query=item.get("callback_query", {}) if isinstance(item.get("callback_query", {}), dict) else {},
                        )
                    )
            return TelegramSendResult(True, "OK", payload), updates
        except Exception as exc:
            return TelegramSendResult(False, f"No pude consultar Telegram: {exc}"), []

    def _post_json(self, method: str, payload: dict[str, Any]) -> TelegramSendResult:
        if not self.token:
            return TelegramSendResult(False, "Telegram token vacio.")
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{self.token}/{method}",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        return _read_telegram_response(req)

    def _post_file(
        self,
        method: str,
        chat_id: str,
        field_name: str,
        file_path: str | Path,
        *,
        caption: str = "",
    ) -> TelegramSendResult:
        if not self.token:
            return TelegramSendResult(False, "Telegram token vacio.")
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return TelegramSendResult(False, f"Archivo no existe: {path}")
        fields = {"chat_id": str(chat_id)}
        if caption:
            fields["caption"] = _limit_text(caption, limit=1024)
        body, content_type = _multipart_body(fields, field_name, path)
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{self.token}/{method}",
            data=body,
            headers={"Content-Type": content_type},
        )
        return _read_telegram_response(req)


class TelegramNotifier:
    def __init__(self, token: str = "", chat_id: str = "") -> None:
        self.token = str(token or "").strip()
        self.chat_id = str(chat_id or "").strip()
        self.client = TelegramClient(self.token)
        self._enabled = bool(self.token and self.chat_id)

    def is_enabled(self) -> bool:
        return self._enabled

    def send_result(self, message: str) -> TelegramSendResult:
        if not self._enabled:
            return TelegramSendResult(False, "Telegram no configurado.")
        return self.client.send_message(self.chat_id, message)

    def send(self, message: str) -> bool:
        return self.send_result(message).ok

    def send_async(self, message: str) -> None:
        if not self._enabled:
            return
        threading.Thread(target=self.send, args=(message,), daemon=True).start()


def setup_telegram_bot() -> tuple[str, str]:
    print("\n" + "=" * 50)
    print("CONFIGURACION DE TELEGRAM PARA VIERNES")
    print("=" * 50)
    print("\nPasos para configurar:")
    print("1. Abre Telegram y busca @BotFather")
    print("2. Envia /newbot para crear un nuevo bot")
    print("3. Sigue las instrucciones y obten el TOKEN")
    print("4. Envia un mensaje al bot y consulta getUpdates para obtener tu CHAT_ID")
    print("\n" + "=" * 50 + "\n")
    token = input("Ingresa el TOKEN del bot: ").strip()
    chat_id = input("Ingresa tu CHAT_ID: ").strip()
    return token, chat_id


def test_telegram(token: str, chat_id: str) -> bool:
    notifier = TelegramNotifier(token, chat_id)
    return notifier.send("Viernes conectado correctamente a Telegram.")


def _read_telegram_response(req: urllib.request.Request) -> TelegramSendResult:
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = int(getattr(resp, "status", 200) or 200)
            payload = json.loads(resp.read().decode("utf-8"))
        ok = bool(payload.get("ok", False))
        return TelegramSendResult(ok, str(payload.get("description", "OK" if ok else "Telegram rechazo la solicitud.")), payload, status)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            detail = str(exc)
        return TelegramSendResult(False, detail or str(exc), {}, int(getattr(exc, "code", 0) or 0))
    except Exception as exc:
        return TelegramSendResult(False, str(exc))


def _multipart_body(fields: dict[str, str], file_field: str, file_path: Path) -> tuple[bytes, str]:
    boundary = "----ViernesTelegramBoundary"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    chunks.extend(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="{file_field}"; filename="{file_path.name}"\r\n'
                f"Content-Type: {mime_type}\r\n\r\n"
            ).encode("utf-8"),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _limit_text(text: str, limit: int = 3900) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value or "Sin respuesta."
    return value[: limit - 40].rstrip() + "\n\n[respuesta recortada por limite de Telegram]"


if __name__ == "__main__":
    token, chat_id = setup_telegram_bot()
    if test_telegram(token, chat_id):
        print("\nTelegram configurado correctamente.")
        print(f"Token: {token}")
        print(f"Chat ID: {chat_id}")
    else:
        print("\nError al conectar. Verifica el token y chat ID.")
