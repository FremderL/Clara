from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from typing import Any


class LocalDataProtector:
    """Proteccion local sin prompt.

    En Windows usa DPAPI ligado al usuario actual. En otros entornos o si DPAPI
    falla, usa base64 como degradacion explicita para conservar funcionalidad.
    """

    def __init__(self) -> None:
        self.mode = "dpapi" if os.name == "nt" else "base64_fallback"

    def protect_json(self, data: dict[str, Any]) -> str:
        raw = json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return self.protect(raw)

    def unprotect_json(self, token: str) -> dict[str, Any]:
        raw = self.unprotect(token)
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}

    def protect(self, data: bytes) -> str:
        if not data:
            return ""
        protected = self._dpapi_protect(data)
        if protected:
            self.mode = "dpapi"
            return "dpapi:" + base64.b64encode(protected).decode("ascii")
        self.mode = "base64_fallback"
        return "b64:" + base64.b64encode(data).decode("ascii")

    def unprotect(self, token: str) -> bytes:
        value = str(token or "")
        if not value:
            return b""
        if value.startswith("dpapi:"):
            raw = _b64decode(value[6:])
            data = self._dpapi_unprotect(raw)
            return data or b""
        if value.startswith("b64:"):
            return _b64decode(value[4:])
        return b""

    def _dpapi_protect(self, data: bytes) -> bytes:
        if os.name != "nt":
            return b""
        try:
            return _crypt_protect_data(data)
        except Exception:
            return b""

    def _dpapi_unprotect(self, data: bytes) -> bytes:
        if os.name != "nt":
            return b""
        try:
            return _crypt_unprotect_data(data)
        except Exception:
            return b""


def _b64decode(value: str) -> bytes:
    try:
        return base64.b64decode(value.encode("ascii"))
    except Exception:
        return b""


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob_from_bytes(data: bytes) -> tuple[_DataBlob, Any]:
    buffer = ctypes.create_string_buffer(data)
    blob = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
    return blob, buffer


def _bytes_from_blob(blob: _DataBlob) -> bytes:
    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        if blob.pbData:
            ctypes.windll.kernel32.LocalFree(blob.pbData)


def _crypt_protect_data(data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    in_blob, _buffer = _blob_from_bytes(data)
    out_blob = _DataBlob()
    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        return b""
    return _bytes_from_blob(out_blob)


def _crypt_unprotect_data(data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    in_blob, _buffer = _blob_from_bytes(data)
    out_blob = _DataBlob()
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        return b""
    return _bytes_from_blob(out_blob)
