"""CLARA Unificada 2.0.0: asistente local-first que combina lo mejor de CLARA y Viernes."""
from __future__ import annotations

import ast
import base64
import hashlib
import hmac
import ctypes
import csv
from ctypes import wintypes
import html
import importlib.util
import json
import math
import operator
import platform
import time
import os
import queue
import re
import shutil
import sqlite3
import stat
import struct
import subprocess
import tempfile
import zipfile
import sys
import threading
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    TKINTER_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - entorno Linux headless sin python3-tk
    TKINTER_AVAILABLE = False

    class _TkStubBase:
        def __init__(self, *args, **kwargs) -> None:
            raise RuntimeError("Tkinter (Tcl/Tk) no está instalado en este entorno Python. En Windows instala Python 3.10+ marcando 'Tcl/Tk and IDLE'.")

    class _TkModuleStub:
        Tk = _TkStubBase
        Toplevel = _TkStubBase
        Canvas = _TkStubBase
        Frame = _TkStubBase
        Text = _TkStubBase
        Listbox = _TkStubBase
        StringVar = _TkStubBase
        BooleanVar = _TkStubBase
        IntVar = _TkStubBase
        TclError = RuntimeError
        showinfo = staticmethod(_TkStubBase)
        showwarning = staticmethod(_TkStubBase)
        showerror = staticmethod(_TkStubBase)
        askyesno = staticmethod(_TkStubBase)
        askopenfilename = staticmethod(_TkStubBase)
        asksaveasfilename = staticmethod(_TkStubBase)
        askdirectory = staticmethod(_TkStubBase)

    tk = _TkModuleStub()  # type: ignore[assignment]
    filedialog = _TkModuleStub()  # type: ignore[assignment]
    messagebox = _TkModuleStub()  # type: ignore[assignment]
    ttk = _TkModuleStub()  # type: ignore[assignment]

try:
    import ollama as ollama_sdk  # type: ignore[import-not-found]
    OLLAMA_PYTHON_MODULE_AVAILABLE = True
except ModuleNotFoundError:
    ollama_sdk = None  # type: ignore[assignment]
    OLLAMA_PYTHON_MODULE_AVAILABLE = False

APP_NAME = "CLARA-V (Clara Viernes) · Asistente Personal Unificada"
APP_VERSION = "2.0.0"
APP_BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
DATA_DIR = Path.home() / "AsistentePersonal"
DB_PATH = DATA_DIR / "asistente.db"
SETTINGS_PATH = DATA_DIR / "settings.json"
NEWS_CACHE_PATH = DATA_DIR / "news_cache.json"  # Caché local de titulares para modo sin conexión; fuera de Git y respaldos
VT_KEY_PATH = DATA_DIR / "virustotal_api_key.dpapi"  # DPAPI; deliberately excluded from settings and backups
DEFAULT_SETTINGS = {"morning_time": "07:00", "weather_location": "Colima, Colima, México", "news_topic": "General", "news_source": "Google News México", "news_count": "5", "chat_history_enabled": "false", "auto_speak_responses": "true", "native_notifications_enabled": "false", "minimize_to_tray": "false", "reminders_paused_until": "", "pattern_suggestions": "false", "calendar_ics_path": "", "allowed_applications": "[]"}
SPOKEN_CHAT_SPEAKERS = ("Asistente", "Clara", "Rutina matutina", "Clima y noticias")
PREFERRED_OLLAMA_MODELS = ("llama3.2", "llama3.2:latest", "llama3.2:3b", "llama3.2:1b", "qwen3:4b", "llama3.1", "llama3")
AUTO_DOWNLOADS_ENABLED = False  # Prohibido descargar o instalar recursos automáticamente sin autorización explícita
OFFICIAL_RESOURCES = {
    "vosk-model-small-es-0.42": {
        "source": "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip",
        "resource": "Modelo de reconocimiento de voz local en español (vosk-model-small-es-0.42)",
        "version": "0.42",
        "size": "39 MB (ZIP comprimido)",
        "license": "Apache-2.0",
        "sha256": None,
    },
    "pyttsx3": {
        "source": "https://pypi.org/project/pyttsx3/",
        "resource": "Motor local de síntesis de voz SAPI5 (pyttsx3)",
        "version": ">=2.90",
        "size": "~50 KB (más dependencias comtypes/pywin32 en Windows)",
        "license": "MPL-2.0 / MIT",
        "sha256": None,
    },
    "vosk": {
        "source": "https://pypi.org/project/vosk/",
        "resource": "Reconocimiento de voz offline Kaldi/Vosk (vosk)",
        "version": ">=0.3.45",
        "size": "~15 MB (wheel Windows x64)",
        "license": "Apache-2.0",
        "sha256": None,
    },
    "sounddevice": {
        "source": "https://pypi.org/project/sounddevice/",
        "resource": "Captura local de micrófono PortAudio (sounddevice)",
        "version": ">=0.4.6",
        "size": "~1.5 MB",
        "license": "MIT",
        "sha256": None,
    },
    "winotify": {
        "source": "https://pypi.org/project/winotify/",
        "resource": "Notificaciones nativas de Windows (winotify)",
        "version": ">=1.1.0",
        "size": "~25 KB",
        "license": "MIT",
        "sha256": None,
    },
    "pystray": {
        "source": "https://pypi.org/project/pystray/",
        "resource": "Icono opcional en bandeja del sistema (pystray + Pillow)",
        "version": ">=0.19.5",
        "size": "~3.5 MB (incluyendo Pillow)",
        "license": "LGPL-3.0 / HPND",
        "sha256": None,
    },
    "ollama": {
        "source": "https://pypi.org/project/ollama/",
        "resource": "Módulo oficial de Python para conversar directamente con Ollama local (ollama)",
        "version": ">=0.4.0",
        "size": "~25 KB",
        "license": "MIT",
        "sha256": None,
    },
    "llama3.2": {
        "source": "https://ollama.com/library/llama3.2",
        "resource": "Modelo conversacional local Llama 3.2 (el modelo predeterminado usado en Viernes)",
        "version": "3B (latest)",
        "size": "~2.0 GB",
        "license": "Llama 3.2 Community License",
        "sha256": None,
    },
}
NEWS_TOPICS = ("General", "Tecnología", "Ciencia", "Educación", "Deportes")
NEWS_SOURCE_FEEDS = {
    "Google News México": "google",
    "BBC News Mundo": "https://feeds.bbci.co.uk/mundo/rss.xml",
    "DW Español": "https://rss.dw.com/rdf/rss-sp-top",
}
NEWS_COUNTS = ("3", "5", "8", "10")
MAX_ALLOWED_APPLICATIONS = 10
BLOCKED_APPLICATION_NAMES = {
    "cmd.exe", "powershell.exe", "pwsh.exe", "python.exe", "pythonw.exe", "wscript.exe", "cscript.exe",
    "mshta.exe", "rundll32.exe", "regsvr32.exe", "msiexec.exe", "winget.exe", "wsl.exe", "bash.exe",
    "sh.exe", "node.exe", "java.exe", "javaw.exe", "ruby.exe", "perl.exe", "git.exe", "schtasks.exe", "taskkill.exe", "reg.exe", "diskpart.exe", "bcdedit.exe", "format.com",
    "installutil.exe", "setup.exe", "installer.exe", "uninstaller.exe", "uninstall.exe", "unins000.exe", "update.exe", "updater.exe", "updatehelper.exe", "selfupdate.exe", "patch.exe", "git-bash.exe", "wt.exe", "windowsterminal.exe", "openconsole.exe",
}


def display_chat_speaker(speaker: str) -> str:
    """Display the former assistant name as CLARA without rewriting stored history."""
    return "Clara" if speaker == "Luma" else speaker


def normalize_allowed_applications(raw_value: str) -> str:
    """Keep a small, structurally valid allowlist; validate executables again at launch."""
    try:
        value = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        value = []
    if not isinstance(value, list):
        value = []
    cleaned: list[dict] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        size, mtime_ns, file_id = item.get("size"), item.get("mtime_ns"), item.get("file_id")
        if not isinstance(path, str) or not Path(path).is_absolute():
            continue
        candidate_path = Path(path)
        if candidate_path.suffix.casefold() != ".exe":
            continue
        if candidate_path.name.casefold() in BLOCKED_APPLICATION_NAMES or any(
            token in candidate_path.stem.casefold() for token in ("setup", "installer", "uninstall", "updater", "update", "patch")
        ):
            continue
        if not isinstance(size, int) or not isinstance(mtime_ns, int) or not isinstance(file_id, (list, tuple)) or len(file_id) != 2 or not all(isinstance(v, int) for v in file_id):
            continue
        canonical = os.path.normcase(os.path.abspath(path))
        if canonical in seen:
            continue
        seen.add(canonical)
        cleaned.append({"name": Path(path).name, "path": path, "size": size, "mtime_ns": mtime_ns, "file_id": [int(file_id[0]), int(file_id[1])]})
        if len(cleaned) >= MAX_ALLOWED_APPLICATIONS:
            break
    return json.dumps(cleaned, ensure_ascii=False)


def load_allowed_applications(settings: dict[str, str]) -> list[dict]:
    return json.loads(normalize_allowed_applications(settings.get("allowed_applications", "[]")))


def export_action_history_csv(db: sqlite3.Connection, destination: str | Path) -> int:
    """Export action category/outcome only; no paths, file names or search queries."""
    rows = db.execute("SELECT created_at, action, outcome FROM action_events ORDER BY id DESC").fetchall()
    path = Path(destination)
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.writer(output)
        writer.writerow(("Fecha", "Acción", "Resultado"))
        writer.writerows(tuple(row) for row in rows)
    return len(rows)


def extract_validated_backup(
    archive_path: str | Path,
    destination_dir: str | Path,
    *,
    max_total_bytes: int = 300 * 1024 * 1024,
    max_database_bytes: int = 256 * 1024 * 1024,
    max_settings_bytes: int = 128 * 1024,
) -> tuple[Path, Path | None]:
    """Extract only the two known backup members, enforcing declared and streamed size limits."""
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "r") as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)) or set(names) - {"asistente.db", "settings.json"} or "asistente.db" not in names:
            raise ValueError("El archivo no tiene el formato de respaldo esperado.")
        if sum(info.file_size for info in infos) > max_total_bytes:
            raise ValueError("El respaldo supera el límite de tamaño permitido.")
        paths = {"asistente.db": destination / "asistente.db", "settings.json": destination / "settings.json"}
        limits = {"asistente.db": max_database_bytes, "settings.json": max_settings_bytes}
        total_read = 0
        for info in infos:
            limit = limits[info.filename]
            if info.file_size > limit:
                raise ValueError("Uno de los archivos del respaldo es demasiado grande.")
            count = 0
            with archive.open(info, "r") as source, paths[info.filename].open("xb") as target:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    count += len(chunk)
                    total_read += len(chunk)
                    if count > limit or total_read > max_total_bytes:
                        raise ValueError("El contenido descomprimido supera el límite de tamaño permitido.")
                    target.write(chunk)
            if count != info.file_size:
                raise ValueError("El tamaño real de un elemento no coincide con el índice del respaldo.")
    return paths["asistente.db"], paths["settings.json"] if (destination / "settings.json").exists() else None


def load_settings() -> dict[str, str]:

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as file:
            stored = json.load(file)
    except (OSError, json.JSONDecodeError):
        stored = {}
    if not isinstance(stored, dict):
        stored = {}
    result = dict(DEFAULT_SETTINGS)
    for key in result:
        raw_val = stored.get(key)
        if isinstance(raw_val, str) and raw_val.strip():
            if key != "allowed_applications" and contains_potential_api_key(raw_val):
                continue
            result[key] = raw_val.strip()
    result["weather_location"] = result["weather_location"][:100] or DEFAULT_SETTINGS["weather_location"]
    result["allowed_applications"] = normalize_allowed_applications(result.get("allowed_applications", "[]"))
    if result["news_topic"] not in NEWS_TOPICS:
        result["news_topic"] = "General"
    if result.get("news_source") not in NEWS_SOURCE_FEEDS:
        result["news_source"] = DEFAULT_SETTINGS["news_source"]
    if result.get("news_count") not in NEWS_COUNTS:
        result["news_count"] = DEFAULT_SETTINGS["news_count"]
    if result.get("chat_history_enabled") not in ("true", "false"):
        result["chat_history_enabled"] = "false"
    if result.get("auto_speak_responses") not in ("true", "false"):
        result["auto_speak_responses"] = "true"
    if result.get("native_notifications_enabled") not in ("true", "false"):
        result["native_notifications_enabled"] = "false"
    if result.get("minimize_to_tray") not in ("true", "false"):
        result["minimize_to_tray"] = "false"
    if result.get("pattern_suggestions") not in ("true", "false"):
        result["pattern_suggestions"] = "false"
    try:
        datetime.strptime(result["morning_time"], "%H:%M")
    except ValueError:
        result["morning_time"] = DEFAULT_SETTINGS["morning_time"]
    return result


def contains_potential_api_key(text: str) -> bool:
    """Detect VirusTotal 64-hex API keys or explicit API key/token assignments to prevent leaks in chats/settings."""
    if not isinstance(text, str) or not text.strip():
        return False
    normalized = text.strip()
    if re.search(r"\b[0-9a-fA-F]{64}\b", normalized):
        low = normalized.casefold()
        if any(token in low for token in ("virustotal", "api", "key", "clave", "token", "x-apikey")) or len(normalized) == 64:
            return True
    if re.search(r"\b(?:virustotal_api_key|vt_api_key|x-apikey|api[_-]?key)\s*[:=]\s*\S{12,}", normalized, re.IGNORECASE):
        return True
    return False


def sanitize_settings_for_storage(settings: dict[str, str]) -> dict[str, str]:
    """Keep only known preference keys and reject any secret/API-key fields before writing settings or backups."""
    cleaned = dict(DEFAULT_SETTINGS)
    if not isinstance(settings, dict):
        return cleaned
    for key in DEFAULT_SETTINGS:
        raw = settings.get(key)
        if isinstance(raw, str):
            if key != "allowed_applications" and contains_potential_api_key(raw):
                raise ValueError("No se permite guardar claves API ni tokens dentro de las preferencias.")
            cleaned[key] = raw.strip() if raw.strip() else DEFAULT_SETTINGS[key]
    cleaned["allowed_applications"] = normalize_allowed_applications(cleaned.get("allowed_applications", "[]"))
    return cleaned


def save_settings(settings: dict[str, str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    safe_settings = sanitize_settings_for_storage(settings)
    temp_path = SETTINGS_PATH.with_suffix(".tmp")
    temp_path.write_text(json.dumps(safe_settings, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(SETTINGS_PATH)


def format_resource_disclosure(resource_key: str) -> str:
    """Return mandatory pre-download disclosure (official source, resource, version, size, license, hash)."""
    if not isinstance(resource_key, str) or resource_key not in OFFICIAL_RESOURCES:
        raise ValueError("Recurso no reconocido en el catálogo oficial verificado; no se admiten URLs arbitrarias.")
    meta = OFFICIAL_RESOURCES[resource_key]
    hash_line = meta.get("sha256") or "Verificación TLS desde fuente oficial (PyPI / Alpha Cephei); valida SHA-256 si descargas un archivo fijo."
    return (
        f"Fuente oficial: {meta['source']}\n"
        f"Recurso: {meta['resource']}\n"
        f"Versión: {meta['version']}\n"
        f"Tamaño aproximado: {meta['size']}\n"
        f"Licencia: {meta['license']}\n"
        f"Integridad / Hash: {hash_line}\n"
        "Descargas automáticas: DESACTIVADAS (requiere tu autorización manual explícita; no se ejecuta ni instala nada automáticamente)."
    )


def verify_resource_sha256(path: str | Path, expected_sha256: str) -> bool:
    """Verify a downloaded file against an official SHA-256 digest before any manual use."""
    if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256.strip()):
        raise ValueError("El hash SHA-256 esperado debe ser una cadena hexadecimal de 64 caracteres.")
    actual_sha256, _size = hash_file_sha256(path)
    if actual_sha256.casefold() != expected_sha256.strip().casefold():
        raise ValueError("El hash SHA-256 del archivo no coincide con el hash oficial esperado.")
    return True


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi(data: bytes, protect: bool) -> bytes:
    if os.name != "nt":
        raise OSError("El almacenamiento protegido de la clave está disponible solo en Windows.")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    source = ctypes.create_string_buffer(data)
    source_blob = _DataBlob(len(data), ctypes.cast(source, ctypes.POINTER(ctypes.c_ubyte)))
    result_blob = _DataBlob()
    common = [ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DataBlob)]
    if protect:
        fn = crypt32.CryptProtectData
        fn.argtypes = [ctypes.POINTER(_DataBlob), wintypes.LPCWSTR, ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DataBlob)]
        fn.restype = wintypes.BOOL
        ok = fn(ctypes.byref(source_blob), "Clara VirusTotal API key", None, None, None, 0, ctypes.byref(result_blob))
    else:
        fn = crypt32.CryptUnprotectData
        fn.argtypes = [ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(_DataBlob)]
        fn.restype = wintypes.BOOL
        ok = fn(ctypes.byref(source_blob), None, None, None, None, 0, ctypes.byref(result_blob))
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(result_blob.pbData, result_blob.cbData)
    finally:
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        kernel32.LocalFree(ctypes.cast(result_blob.pbData, ctypes.c_void_p))


def save_vt_api_key(key: str) -> None:
    if not key.strip() or len(key) > 4096:
        raise ValueError("La clave está vacía o excede el límite permitido.")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    encrypted = _dpapi(key.strip().encode("utf-8"), True)
    temp = VT_KEY_PATH.with_suffix(".tmp")
    temp.write_bytes(encrypted)
    os.replace(temp, VT_KEY_PATH)


def load_vt_api_key() -> str:
    if not VT_KEY_PATH.is_file():
        return ""
    return _dpapi(VT_KEY_PATH.read_bytes(), False).decode("utf-8")


def delete_vt_api_key() -> None:
    VT_KEY_PATH.unlink(missing_ok=True)


def hash_file_sha256(path: str | Path) -> tuple[str, int]:
    file_path = Path(path)
    before = file_path.stat()
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    after = file_path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise OSError("El archivo cambió mientras se calculaba el hash; no se consultó.")
    return digest.hexdigest(), before.st_size


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def virustotal_lookup(sha256: str, api_key: str) -> dict:
    if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", sha256.strip()):
        raise ValueError("La consulta a VirusTotal admite únicamente un hash SHA-256 hexadecimal de 64 caracteres.")
    clean_hash = sha256.strip().casefold()
    request = urllib.request.Request(
        f"https://www.virustotal.com/api/v3/files/{clean_hash}",
        headers={"x-apikey": api_key, "Accept": "application/json", "User-Agent": "Clara-Personal/2.0.0"},
        method="GET",
    )
    try:
        opener = urllib.request.build_opener(_NoRedirect)
        with opener.open(request, timeout=20) as response:
            data = json.loads(response.read(2 * 1024 * 1024).decode("utf-8"))
        attrs = data.get("data", {}).get("attributes", {})
        stats = attrs.get("last_analysis_stats", {})
        engines = attrs.get("last_analysis_results", {})
        detections = []
        for engine, result in engines.items():
            category = result.get("category", "")
            if category in ("malicious", "suspicious"):
                detections.append((engine, category, result.get("result") or "sin detalle"))
        return {"status": "ok", "stats": stats, "detections": detections[:50], "analysis_date": attrs.get("last_analysis_date"), "reputation": attrs.get("reputation")}
    except urllib.error.HTTPError as exc:
        try:
            if exc.code == 404:
                return {"status": "not_found"}
            if exc.code == 401:
                return {"status": "unauthorized"}
            if exc.code == 403:
                return {"status": "forbidden"}
            if exc.code == 429:
                return {"status": "rate_limited"}
            return {"status": "http_error", "code": exc.code}
        finally:
            # HTTPError also owns the response stream; close it to avoid leaking sockets/resources.
            exc.close()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return {"status": "network_error", "detail": str(exc)[:240]}


def clean_rss_text(raw: str) -> str:
    """Strip residual HTML tags and unescape entities from RSS titles/sources."""
    if not raw:
        return ""
    unescaped = html.unescape(str(raw))
    without_tags = re.sub(r"<[^>]+>", " ", unescaped)
    return re.sub(r"\s+", " ", without_tags).strip()


def truncate_at_sentence_boundary(text: str, max_chars: int = 2600) -> str:
    """Return text up to max_chars, cutting only at a complete sentence or word boundary so words/ideas are never cut mid-way."""
    clean = str(text or "").strip()
    if not clean or len(clean) <= max_chars:
        return clean
    window = clean[: max_chars + 1]
    # Look for the last sentence-ending punctuation (. ! ? ;) followed by whitespace or end of window
    min_pos = max(120, int(max_chars * 0.45))
    best_end = -1
    for match in re.finditer(r"[.!?](?=\s|$)", window):
        pos = match.end()
        if pos >= min_pos and pos <= max_chars:
            best_end = pos
    if best_end != -1:
        return window[:best_end].strip()
    # Fallback: cut at the last space before max_chars so we never slice a word in half
    last_space = window[:max_chars].rfind(" ")
    if last_space > min_pos:
        clipped = window[:last_space].rstrip(" ,;:-")
        return clipped + ("." if not clipped.endswith((".", "!", "?")) else "")
    return window[:max_chars].strip()


def extract_news_item_summary(raw_description: str, main_title: str, source_name: str = "") -> str:
    """Extract an informative, readable summary from RSS <description> (handling both article abstracts and Google News HTML lists)."""
    if not raw_description:
        return ""
    unescaped = html.unescape(str(raw_description))
    # Remove any raw URLs embedded in the description text
    unescaped = re.sub(r"https?://\S+", " ", unescaped)
    clean_main = re.sub(r"\s+-\s+[^-]+$", "", main_title or "").strip().casefold()

    # Google News RSS often encodes multiple related coverage angles inside <li>...</li>
    li_matches = re.findall(r"<li[^>]*>(.*?)</li>", unescaped, flags=re.IGNORECASE | re.DOTALL)
    if li_matches:
        angles: list[str] = []
        for li_html in li_matches:
            txt = clean_rss_text(li_html)
            txt = re.sub(r"\s*https?://\S+", "", txt).strip(" -·.,;:")
            if not txt:
                continue
            txt_core = re.sub(r"\s+-\s+[^-]+$", "", txt).strip().casefold()
            if clean_main and (txt_core == clean_main or clean_main in txt_core and len(txt_core) < len(clean_main) + 18):
                continue
            if txt not in angles:
                angles.append(txt)
        if angles:
            return truncate_at_sentence_boundary(" · ".join(angles[:4]), max_chars=750)

    text = clean_rss_text(unescaped)
    text = re.sub(r"\s*https?://\S+", "", text).strip(" -·")
    if not text:
        return ""
    # Avoid repeating the exact headline if the RSS feed merely copied <title> into <description>
    text_core = re.sub(r"\s+-\s+[^-]+$", "", text).strip().casefold()
    if clean_main and (text_core == clean_main or text.casefold() == (main_title or "").strip().casefold()):
        return ""
    if source_name and text.endswith(source_name):
        text = text[: -len(source_name)].rstrip(" -·")
    return truncate_at_sentence_boundary(text, max_chars=750)


def format_rich_news_digest(
    items: list[dict[str, str]],
    source_name: str,
    topic: str = "General",
    *,
    is_google: bool = True,
    cached_stamp: str | None = None,
) -> str:
    """Format news items with rich context/summaries and zero invasive URLs."""
    topic_note = f" · sección {topic}" if is_google and topic else ""
    if cached_stamp:
        header = f"📰 Resumen de noticias guardado localmente ({cached_stamp} · {source_name}{topic_note}):"
    else:
        header = f"📰 Resumen informativo de noticias · {source_name}{topic_note}:"
    if not items:
        return f"{header}\nNo se encontraron noticias disponibles en este momento."

    blocks: list[str] = [header]
    for idx, item in enumerate(items, start=1):
        raw_title = str(item.get("title") or "").strip()
        source = str(item.get("source") or source_name).strip()
        # Strip redundant ' - Medio' suffix from Google News titles when source is already displayed
        clean_title = raw_title
        if source and clean_title.endswith(f" - {source}"):
            clean_title = clean_title[: -len(f" - {source}")].strip()
        elif " - " in clean_title:
            parts = clean_title.rsplit(" - ", 1)
            if len(parts[1]) <= 35 and (not source or source == source_name):
                clean_title, source = parts[0].strip(), parts[1].strip()

        summary = str(item.get("summary") or "").strip()
        published = str(item.get("published") or "").strip()
        meta_line = f"   🏛️ Fuente: {source}" + (f" · 🕒 {published}" if published else "")
        if summary:
            detail_line = f"   📝 Resumen: {summary}"
        else:
            detail_line = (
                f"   📝 Contexto: Nota destacada publicada por {source} sobre «{clean_title}». "
                "Puedes decirme «investiga en internet sobre este tema» si quieres que profundice en los antecedentes."
            )
        blocks.append(f"{idx}. {clean_title}\n{meta_line}\n{detail_line}")
    return "\n\n".join(blocks)


def parse_news_feed(
    xml_data: bytes,
    source_label: str,
    limit: int,
    *,
    include_details: bool = False,
) -> list[dict[str, str]]:
    if len(xml_data) > 2 * 1024 * 1024:
        raise ValueError("El feed RSS supera el límite de 2 MB.")
    upper = xml_data.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise ValueError("El feed contiene una declaración XML no admitida.")
    root = ET.fromstring(xml_data)
    items = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1].lower() == "item"]
    result: list[dict[str, str]] = []
    def child_value(item, name: str) -> str:
        for node in item:
            if node.tag.rsplit("}", 1)[-1].lower() == name:
                value = (node.text or "").strip()
                if value:
                    return value
                if name == "link":
                    return next((str(v) for k, v in node.attrib.items() if k.rsplit("}", 1)[-1].lower() == "resource"), "")
        return ""
    for item in items[:max(1, min(10, int(limit)))]:
        title = clean_rss_text(child_value(item, "title"))[:400]
        raw_link = child_value(item, "link").strip()[:1200]
        link = raw_link if raw_link.casefold().startswith(("https://", "http://")) else ""
        source = clean_rss_text(child_value(item, "source"))[:120] or source_label
        if title:
            entry: dict[str, str] = {"title": title, "source": source, "link": link}
            if include_details:
                raw_desc = (
                    child_value(item, "description")
                    or child_value(item, "encoded")
                    or child_value(item, "summary")
                )
                summary = extract_news_item_summary(raw_desc, title, source)
                if summary:
                    entry["summary"] = summary
                raw_pub = clean_rss_text(child_value(item, "pubdate") or child_value(item, "date"))[:40]
                if raw_pub:
                    entry["published"] = raw_pub[:22]
            result.append(entry)
    return result


def save_news_cache(
    items: list[dict[str, str]],
    source_name: str,
    topic: str,
    cache_path: Path | None = None,
    now: datetime | None = None,
) -> None:
    """Persist last valid headlines locally (outside backups/git) for offline fallback."""
    if not items:
        return
    target = Path(cache_path) if cache_path is not None else NEWS_CACHE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).isoformat(timespec="seconds")
    payload = {
        "saved_at": stamp,
        "source": str(source_name)[:120],
        "topic": str(topic)[:80],
        "items": [
            {
                "title": str(item.get("title", ""))[:400],
                "source": str(item.get("source", ""))[:120],
                "link": str(item.get("link", ""))[:1200],
                **(
                    {"summary": str(item.get("summary", ""))[:460]}
                    if item.get("summary")
                    else {}
                ),
            }
            for item in items[:10]
            if item.get("title")
        ],
    }
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)


def load_news_cache(
    cache_path: Path | None = None,
    max_age_hours: float = 24.0,
    now: datetime | None = None,
) -> dict | None:
    """Read cached headlines if present and within max_age_hours; return None otherwise."""
    target = Path(cache_path) if cache_path is not None else NEWS_CACHE_PATH
    if not target.is_file():
        return None
    try:
        if target.stat().st_size > 256 * 1024:
            return None
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        saved_at = datetime.fromisoformat(str(data.get("saved_at", "")))
        current = now or datetime.now()
        if saved_at.tzinfo is not None:
            saved_at = saved_at.astimezone().replace(tzinfo=None)
        age_hours = (current - saved_at).total_seconds() / 3600.0
        if age_hours > max_age_hours or age_hours < -1.0:
            return None
        raw_items = data.get("items")
        if not isinstance(raw_items, list) or not raw_items:
            return None
        items = [
            {
                "title": str(entry.get("title", "")).strip()[:400],
                "source": str(entry.get("source", "")).strip()[:120],
                "link": str(entry.get("link", "")).strip()[:1200],
            }
            for entry in raw_items[:10]
            if isinstance(entry, dict) and str(entry.get("title", "")).strip()
        ]
        if not items:
            return None
        return {
            "saved_at": saved_at.strftime("%d/%m/%Y %H:%M"),
            "source": str(data.get("source") or "Fuente local"),
            "topic": str(data.get("topic") or "General"),
            "items": items,
        }
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def select_spanish_voice_id(voices: list) -> str | None:
    """Pick the best available Spanish voice from pyttsx3 voice descriptors."""
    if not voices:
        return None
    mx_tokens = ("es-mx", "es_mx", "mexico", "méxico", "sabina", "raul", "raúl", "dalia", "jorge")
    es_tokens = ("spanish", "español", "espanol", "es-es", "es_es", "es-419", "helena", "pablo", "laura")
    for preferred in (mx_tokens, es_tokens):
        for voice in voices:
            haystack = " ".join(
                (
                    str(getattr(voice, "id", "") or ""),
                    str(getattr(voice, "name", "") or ""),
                    str(getattr(voice, "languages", "") or ""),
                )
            ).casefold()
            if any(token in haystack for token in preferred):
                voice_id = getattr(voice, "id", None)
                if voice_id:
                    return str(voice_id)
    first_id = getattr(voices[0], "id", None)
    return str(first_id) if first_id else None


def prepare_text_for_speech(text: str) -> str:
    """Clean bullet symbols and raw URLs for natural Spanish TTS playback while keeping written chat links intact."""
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    cleaned = re.sub(r"(?im)^\s*Enlace:\s*https?://\S+\s*$", "", cleaned)
    cleaned = re.sub(r"https?://\S+", "enlace en pantalla", cleaned)
    cleaned = cleaned.replace("•", " ").replace("·", ", ")
    return re.sub(r"\s+", " ", cleaned).strip()


def explain_tts_failure(reason: str) -> str:
    """Explain why spoken output failed while reassuring the user that the written reply is preserved."""
    detail = str(reason or "").strip()
    low = detail.casefold()
    if "no_pyttsx3" in low or "pyttsx3" in low and "no module" in low:
        cause = "El paquete opcional pyttsx3 no está instalado en este entorno Python."
        fix = "Puedes instalarlo manualmente con instalar_voz.bat o seguir usando Clara por texto."
    elif "no_voices" in low or "ninguna voz" in low:
        cause = "Windows o el sistema actual no reportó ninguna voz instalada para síntesis local."
        fix = "En Windows, abre Configuración > Hora e idioma > Voz e instala el paquete de voz Español (México) o Español (España)."
    else:
        cause = f"El motor de voz del sistema reportó un error ({detail[:180] or 'dispositivo de audio no disponible'})."
        fix = "Abre 🩺 Diagnóstico de voz o ejecuta diagnosticar_voz.bat para revisar el audio y las voces instaladas."
    return f"No pude leer la respuesta en voz alta: {cause} Tu respuesta escrita se conserva íntegra en el chat. {fix}"


def collect_voice_diagnostics(base_dir: Path | None = None) -> dict:
    """Inspect local TTS and STT readiness without activating the microphone or contacting the internet."""
    root = Path(base_dir) if base_dir is not None else APP_BASE_DIR
    model_path = root / "models" / "vosk-model-small-es-0.42"
    tts_installed = importlib.util.find_spec("pyttsx3") is not None
    vosk_installed = importlib.util.find_spec("vosk") is not None
    sounddevice_installed = importlib.util.find_spec("sounddevice") is not None
    model_present = model_path.is_dir()
    voices_info: list[dict[str, str]] = []
    spanish_voice_id: str | None = None
    tts_error: str | None = None
    if tts_installed:
        try:
            import pyttsx3
            engine = pyttsx3.init()
            raw_voices = list(engine.getProperty("voices") or [])
            spanish_voice_id = select_spanish_voice_id(raw_voices)
            for item in raw_voices[:20]:
                voices_info.append(
                    {
                        "id": str(getattr(item, "id", "") or ""),
                        "name": str(getattr(item, "name", "") or "Voz sin nombre"),
                    }
                )
        except Exception as exc:
            tts_error = str(exc)[:200]
    tts_ready = bool(tts_installed and voices_info and not tts_error)
    stt_ready = bool(vosk_installed and sounddevice_installed and model_present)
    return {
        "tts_installed": tts_installed,
        "tts_ready": tts_ready,
        "tts_error": tts_error,
        "voices": voices_info,
        "spanish_voice_id": spanish_voice_id,
        "vosk_installed": vosk_installed,
        "sounddevice_installed": sounddevice_installed,
        "model_present": model_present,
        "model_path": str(model_path),
        "stt_ready": stt_ready,
        "microphone_activated": False,
    }


def preview_viernes_migration(
    agenda_path: str | Path | None,
    config_path: str | Path | None,
    db: sqlite3.Connection,
) -> dict:
    """Read-only preview of legacy Viernes JSON files; never writes to SQLite or infers routines."""
    candidate_tasks: list[dict[str, str | None]] = []
    skipped_duplicates = 0
    skipped_recurring = 0
    informational_classes: list[dict[str, object]] = []

    if agenda_path and Path(agenda_path).is_file():
        raw_agenda = json.loads(Path(agenda_path).read_text(encoding="utf-8"))
        events = raw_agenda.get("events", []) if isinstance(raw_agenda, dict) else []
        for entry in events:
            if not isinstance(entry, dict):
                continue
            recurrence = str(entry.get("recurrence") or "once").strip().casefold()
            # Never infer or auto-import recurring rules as routines.
            if recurrence not in ("", "once", "none"):
                skipped_recurring += 1
                continue
            title = str(entry.get("title") or "").strip()[:200]
            due_date = str(entry.get("date") or "").strip()
            due_time = str(entry.get("time") or "").strip() or None
            if not title or not due_date:
                continue
            try:
                date.fromisoformat(due_date)
                if due_time:
                    datetime.strptime(due_time, "%H:%M")
            except ValueError:
                continue
            exists = db.execute(
                "SELECT 1 FROM tasks WHERE title=? AND due_date=? AND COALESCE(due_time,'')=COALESCE(?,'') LIMIT 1",
                (title, due_date, due_time),
            ).fetchone()
            if exists:
                skipped_duplicates += 1
                continue
            candidate_tasks.append(
                {
                    "title": title,
                    "due_date": due_date,
                    "due_time": due_time,
                    "external_uid": f"viernes-migration-{entry.get('id', hashlib.sha256((title + due_date).encode('utf-8')).hexdigest()[:10])}",
                }
            )

    if config_path and Path(config_path).is_file():
        raw_config = json.loads(Path(config_path).read_text(encoding="utf-8"))
        schedule = raw_config.get("class_schedule", {}) if isinstance(raw_config, dict) else {}
        if isinstance(schedule, dict):
            for day_key, subjects in schedule.items():
                if isinstance(subjects, list) and subjects:
                    informational_classes.append(
                        {"day": str(day_key), "subjects": [str(s) for s in subjects if str(s).strip()]}
                    )

    return {
        "candidate_tasks": candidate_tasks,
        "skipped_duplicates": skipped_duplicates,
        "skipped_recurring": skipped_recurring,
        "informational_classes": informational_classes,
        "writes_performed": 0,
        "reversible": True,
    }


def parse_ical_datetime(value: str, params: dict[str, str] | None = None, fallback_tzid: str | None = None) -> tuple[datetime, str | None]:
    params = params or {}
    raw = value.strip()
    raw = re.sub(r"([+-]\d{2}):(\d{2})$", r"\1\2", raw)
    if len(raw) == 8 and "T" not in raw:
        return datetime.strptime(raw, "%Y%m%d"), None
    fmt = "%Y%m%dT%H%M%S" if len(raw) >= 15 else "%Y%m%dT%H%M"
    core = raw[:15] if len(raw) >= 15 else raw
    if raw.endswith("Z"):
        utc_format = "%Y%m%dT%H%M%SZ" if len(raw) >= 16 else "%Y%m%dT%H%MZ"
        dt = datetime.strptime(raw, utc_format).replace(tzinfo=timezone.utc)
        return dt.astimezone().replace(tzinfo=None), None
    if re.search(r"[+-]\d{4}$", raw):
        fmt_offset = "%Y%m%dT%H%M%S%z" if len(raw) >= 19 else "%Y%m%dT%H%M%z"
        dt = datetime.strptime(raw, fmt_offset)
        return dt.astimezone().replace(tzinfo=None), None
    dt = datetime.strptime(core, fmt)
    tzid = params.get("TZID") or fallback_tzid
    if tzid:
        try:
            return dt.replace(tzinfo=ZoneInfo(tzid)).astimezone().replace(tzinfo=None), None
        except ZoneInfoNotFoundError:
            return dt, f"Zona TZID no disponible en este Python ({tzid}); se mostró como hora local flotante."
    return dt, None


def parse_ical_events(text: str) -> tuple[list[dict[str, str | None]], int, int]:
    """Read a safe subset of iCalendar: standalone VEVENTs with DTSTART/SUMMARY."""
    unfolded: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    prodid = next((line.split(":", 1)[1] for line in unfolded if line.upper().startswith("PRODID:")), "")

    def unescape(value: str) -> str:
        return value.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")

    events: list[dict[str, str | None]] = []
    skipped_recurring = 0
    skipped_own_events = 0
    current: dict[str, object] | None = None
    for line in unfolded:
        upper = line.upper()
        if upper == "BEGIN:VEVENT":
            current = {}
            continue
        if upper == "END:VEVENT" and current is not None:
            if current.get("RRULE") or current.get("RECURRENCE-ID") or str(current.get("STATUS", "")).upper() == "CANCELLED":
                skipped_recurring += 1
            elif "ASISTENTE PERSONAL" in prodid.upper() and (str(current.get("SUMMARY", "")).startswith("Clase:") or str(current.get("SUMMARY", "")).startswith("Día sin clases") or str(current.get("SUMMARY", "")).startswith("Bloque local:")): 
                skipped_own_events += 1
            else:
                raw_start = str(current.get("DTSTART", ""))
                params = current.get("DTSTART_PARAMS", {})
                summary = unescape(str(current.get("SUMMARY", "")).strip())
                uid = unescape(str(current.get("UID", "")).strip())
                try:
                    if not raw_start or not summary:
                        raise ValueError("Falta inicio o título")
                    if ("VALUE" in params and params["VALUE"].upper() == "DATE") or len(raw_start) == 8:
                        day = datetime.strptime(raw_start[:8], "%Y%m%d").date()
                        time_value = None
                        end_time = None
                        timezone_warning = None
                    else:
                        start_dt, timezone_warning = parse_ical_datetime(raw_start, params)
                        day, time_value = start_dt.date(), start_dt.strftime("%H:%M")
                        end_time = None
                        raw_end = str(current.get("DTEND", ""))
                        if raw_end and len(raw_end) != 8:
                            end_params = current.get("DTEND_PARAMS", {})
                            end_dt, end_warning = parse_ical_datetime(raw_end, end_params, params.get("TZID"))
                            if end_dt.date() == day:
                                end_time = end_dt.strftime("%H:%M")
                            timezone_warning = timezone_warning or end_warning
                    if not uid:
                        uid = hashlib.sha256(f"{summary}|{day}|{time_value}".encode("utf-8")).hexdigest() + "@import.local"
                    events.append({"uid": uid, "title": summary[:250], "due_date": day.isoformat(), "due_time": time_value, "end_time": end_time, "timezone_warning": timezone_warning})
                except (ValueError, OverflowError):
                    pass
            current = None
            continue
        if current is None or ":" not in line:
            continue
        left, value = line.split(":", 1)
        parts = left.split(";")
        key = parts[0].upper()
        if key in ("SUMMARY", "UID", "RRULE", "RECURRENCE-ID", "STATUS"):
            current[key] = value
        elif key in ("DTSTART", "DTEND"):
            current[key] = value
            current[key + "_PARAMS"] = {part.split("=", 1)[0].upper(): part.split("=", 1)[1].strip('"') for part in parts[1:] if "=" in part}
        if len(events) > 500:
            raise ValueError("El archivo contiene más de 500 eventos; divide el calendario antes de importar.")
    return events, skipped_recurring, skipped_own_events


def read_linked_ics_events(path_text: str, start_day: date, end_day: date) -> tuple[list[dict[str, str | None]], str]:
    """Read one user-selected local ICS snapshot on demand; never fetch or write a feed."""
    if not path_text:
        return [], "No hay archivo ICS local vinculado."
    if path_text.casefold().startswith(("http://", "https://", "webcal://", "\\\\")):
        return [], "Solo se admiten archivos locales; no se consultan URL ni calendarios de red."
    path = Path(path_text).expanduser()
    try:
        size = path.stat().st_size
        if size > 5 * 1024 * 1024:
            return [], "El archivo ICS supera el límite de 5 MB."
        text = path.read_text(encoding="utf-8-sig")
        events, skipped_recurring, _skipped_own = parse_ical_events(text)
    except (OSError, UnicodeError, ValueError) as exc:
        return [], f"No se pudo leer el archivo ICS local: {exc}"
    visible = [event for event in events if event["due_date"] and start_day.isoformat() <= str(event["due_date"]) <= end_day.isoformat()]
    warnings = sorted({str(event["timezone_warning"]) for event in visible if event.get("timezone_warning")})
    status = f"ICS local · {path.name} · solo lectura · {len(visible)} evento(s) en el rango · {skipped_recurring} recurrente(s)/cancelado(s) omitido(s)."
    if warnings:
        status += " Aviso: " + " ".join(warnings)
    return visible, status


def linked_event_conflicts(db: sqlite3.Connection, event: dict[str, str | None]) -> list[str]:
    """Compare a timed read-only calendar event with local classes and saved blocks."""
    if not event.get("due_date") or not event.get("due_time") or not event.get("end_time"):
        return []
    day=date.fromisoformat(str(event["due_date"]))
    start=datetime.combine(day,datetime.strptime(str(event["due_time"]),"%H:%M").time())
    end=datetime.combine(day,datetime.strptime(str(event["end_time"]),"%H:%M").time())
    if end<=start:return []
    conflicts=[]
    for meeting in classes_for_date(db,day):
        other_start=datetime.combine(day,datetime.strptime(str(meeting["start_time"]),"%H:%M").time())
        other_end=datetime.combine(day,datetime.strptime(str(meeting["end_time"]),"%H:%M").time()) if meeting["end_time"] else other_start+timedelta(hours=1)
        if start<other_end and end>other_start:conflicts.append(f"Clase: {meeting['name']}")
    for block in db.execute("SELECT title,start_time,end_time FROM plan_blocks WHERE block_date=?",(day.isoformat(),)):
        other_start=datetime.combine(day,datetime.strptime(block["start_time"],"%H:%M").time())
        other_end=datetime.combine(day,datetime.strptime(block["end_time"],"%H:%M").time())
        if start<other_end and end>other_start:conflicts.append(f"Bloque local: {block['title']}")
    return conflicts


def validate_selected_folder(path: str | Path) -> Path:
    """Resolve only a user-selected existing directory; this helper does not open or modify it."""
    raw = str(path or "").strip()
    if not raw:
        raise ValueError("Selecciona una carpeta existente.")
    if raw.startswith("\\\\"):
        raise ValueError("Solo se permite abrir carpetas locales existentes, no rutas de red.")
    candidate = Path(raw).expanduser()
    if not candidate.exists() or not candidate.is_dir():
        raise ValueError("La selección ya no es una carpeta existente.")
    if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
        raise ValueError("Por seguridad, no se permite abrir enlaces simbólicos ni junctions.")
    folder = candidate.resolve(strict=True)
    if not folder.is_dir():
        raise ValueError("La selección ya no es una carpeta existente.")
    return folder


def launch_selected_folder(path: str | Path) -> Path:
    """Open only a validated existing folder in Windows Explorer; no shell command or file writes."""
    folder = validate_selected_folder(path)
    if sys.platform != "win32":
        raise OSError("Esta acción piloto está disponible únicamente en Windows.")
    os.startfile(str(folder))
    return folder


def connect_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        due_date TEXT,
        priority TEXT NOT NULL DEFAULT 'Normal',
        done INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        due_time TEXT,
        reminded INTEGER NOT NULL DEFAULT 0,
        subject TEXT,
        routine_id INTEGER,
        external_uid TEXT,
        repeat_rule TEXT NOT NULL DEFAULT 'none',
        repeat_series_id INTEGER,
        completed_at TEXT
    )""")
    # Migración segura para la base creada por la versión 0.1.
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
    if "description" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN description TEXT")
    if "due_time" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN due_time TEXT")
    if "reminded" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN reminded INTEGER NOT NULL DEFAULT 0")
    if "subject" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN subject TEXT")
    if "routine_id" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN routine_id INTEGER")
    if "external_uid" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN external_uid TEXT")
    if "repeat_rule" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN repeat_rule TEXT NOT NULL DEFAULT 'none'")
    if "repeat_series_id" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN repeat_series_id INTEGER")
    if "completed_at" not in columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN completed_at TEXT")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_external_uid ON tasks(external_uid) WHERE external_uid IS NOT NULL")
    conn.execute("""CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        weekday INTEGER NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT,
        location TEXT,
        reminded_on TEXT
    )""")
    class_columns = {row["name"] for row in conn.execute("PRAGMA table_info(classes)")}
    if "reminded_on" not in class_columns:
        conn.execute("ALTER TABLE classes ADD COLUMN reminded_on TEXT")
    conn.execute("""CREATE TABLE IF NOT EXISTS class_exceptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exception_date TEXT NOT NULL,
        class_id INTEGER,
        class_name TEXT,
        action TEXT NOT NULL,
        name TEXT,
        start_time TEXT,
        end_time TEXT,
        location TEXT,
        note TEXT,
        reminded_on TEXT
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_class_exceptions_date ON class_exceptions(exception_date)")
    conn.execute("""CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT NOT NULL,
        content TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'Preferencia',
        created_at TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'Entrada manual del usuario',
        expires_on TEXT
    )""")
    memory_columns = {row["name"] for row in conn.execute("PRAGMA table_info(memories)")}
    if "source" not in memory_columns:
        conn.execute("ALTER TABLE memories ADD COLUMN source TEXT NOT NULL DEFAULT 'Entrada manual del usuario'")
    if "expires_on" not in memory_columns:
        conn.execute("ALTER TABLE memories ADD COLUMN expires_on TEXT")
    conn.execute("""CREATE TABLE IF NOT EXISTS security_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        summary TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS action_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL,
        outcome TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        speaker TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_history_created ON chat_history(id)")
    conn.execute("""CREATE TABLE IF NOT EXISTS routines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        subject TEXT,
        weekdays TEXT NOT NULL,
        reminder_time TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'Rutina configurada manualmente por el usuario'
    )""")
    routine_columns = {row["name"] for row in conn.execute("PRAGMA table_info(routines)")}
    if "source" not in routine_columns:
        conn.execute("ALTER TABLE routines ADD COLUMN source TEXT NOT NULL DEFAULT 'Rutina configurada manualmente por el usuario'")
    conn.execute("""CREATE TABLE IF NOT EXISTS reminder_events (
        alert_key TEXT PRIMARY KEY,
        source_type TEXT NOT NULL,
        source_id INTEGER,
        title TEXT NOT NULL,
        due_at_local TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'pending',
        snooze_until TEXT,
        next_notify_at TEXT NOT NULL,
        delivery_count INTEGER NOT NULL DEFAULT 0,
        last_delivered_at TEXT
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS reminder_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_key TEXT NOT NULL,
        action TEXT NOT NULL,
        action_at TEXT NOT NULL,
        details TEXT
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_reminder_actions_key ON reminder_actions(alert_key,id)")
    conn.execute("""CREATE TABLE IF NOT EXISTS plan_blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        block_date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        notes TEXT,
        created_at TEXT NOT NULL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_blocks_date_time ON plan_blocks(block_date,start_time)")
    ensure_security_tables(conn)
    ensure_subject_notebook_tables(conn)
    repair_legacy_class_locations(conn)
    conn.commit()
    return conn


def ensure_subject_notebook_tables(conn: sqlite3.Connection) -> None:
    """Create tables for quick subject notes and linked subject folders if they do not exist."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS subject_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_subject_notes_subject ON subject_notes(subject)")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS subject_folders (
            subject TEXT PRIMARY KEY,
            folder_path TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )"""
    )


SECURITY_LEVEL_SPECS: dict[int, dict[str, str]] = {
    0: {
        "name": "nivel de acceso invitado",
        "short": "Nivel 0 · Invitado",
        "capabilities": "Conversar con Clara, consultar qué sigue hoy, horario de clases, clima, noticias y ayuda (sin modificar agenda, archivos ni secretos)",
    },
    1: {
        "name": "nivel de acceso estándar",
        "short": "Nivel 1 · Estándar",
        "capabilities": "Agregar y marcar clases, tareas, bloques de estudio y rutinas, además de consultas generales",
    },
    2: {
        "name": "nivel de acceso avanzado",
        "short": "Nivel 2 · Avanzado",
        "capabilities": "Revisar, buscar, abrir y mover carpetas y archivos permitidos, iniciar aplicaciones autorizadas y eliminar clases o tareas individuales",
    },
    3: {
        "name": "nivel de acceso prioritario",
        "short": "Nivel 3 · Prioritario",
        "capabilities": "Borrar a Clara o restablecer sus datos, ver contraseñas guardadas y secretos encriptados, revisar carpetas y archivos, administrar usuarios y control total",
    },
}

ACTION_REQUIRED_LEVELS: dict[str, tuple[int, str]] = {
    "conversation": (0, "Conversación y consultas de agenda, clima o noticias"),
    "modify_agenda": (1, "Agregar o modificar clases, tareas, bloques y rutinas"),
    "delete_agenda_item": (2, "Eliminar clases, tareas o rutinas de la agenda"),
    "file_operations": (2, "Revisar, buscar, abrir o mover carpetas y archivos"),
    "manage_apps": (2, "Abrir o gestionar aplicaciones autorizadas"),
    "view_secrets": (3, "Ver contraseñas guardadas y secretos encriptados"),
    "save_secret": (3, "Guardar o eliminar secretos en la bóveda encriptada"),
    "manage_users": (3, "Administrar usuarios y niveles de seguridad"),
    "restore_backup": (3, "Restaurar copia de seguridad"),
    "clear_chat_history": (3, "Borrar historial de conversación"),
    "delete_clara_data": (3, "Borrar a Clara o restablecer todos sus datos"),
}


def ensure_security_tables(db: sqlite3.Connection) -> None:
    """Ensure multi-user access level, security audit, and encrypted secrets vault tables exist."""
    db.execute(
        """CREATE TABLE IF NOT EXISTS security_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS security_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            access_level INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS encrypted_secrets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_username TEXT NOT NULL,
            secret_label TEXT NOT NULL,
            encrypted_payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )


def coerce_security_level(value: int | str | None, default: int = 1) -> int:
    """Normalize a security level into the valid 0..3 range."""
    if isinstance(value, str):
        low = value.strip().casefold()
        if any(tok in low for tok in ("prioritario", "admin", "propietario", "total", "3")):
            return 3
        if any(tok in low for tok in ("avanzado", "archivo", "carpeta", "2")):
            return 2
        if any(tok in low for tok in ("estandar", "estándar", "agenda", "1")):
            return 1
        if any(tok in low for tok in ("invitado", "visitante", "basico", "básico", "0")):
            return 0
    try:
        lvl = int(value) if value is not None else int(default)
    except (TypeError, ValueError):
        lvl = int(default)
    return max(0, min(3, lvl))


def hash_user_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    """Hash a user password using PBKDF2-HMAC-SHA256 (120,000 iterations)."""
    clean_pw = str(password or "").strip()
    if not clean_pw:
        raise ValueError("La contraseña no puede estar vacía.")
    salt_bytes = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", clean_pw.encode("utf-8"), salt_bytes, 120_000)
    return salt_bytes.hex(), digest.hex()


def verify_user_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    """Verify a password in constant time against a stored PBKDF2-HMAC-SHA256 hash."""
    if not password or not salt_hex or not expected_hash_hex:
        return False
    try:
        _, candidate_hex = hash_user_password(password, salt_hex=salt_hex)
        return hmac.compare_digest(candidate_hex, str(expected_hash_hex))
    except Exception:
        return False


def _derive_vault_keys(passphrase: str, salt: bytes) -> tuple[bytes, bytes]:
    dk = hashlib.pbkdf2_hmac("sha256", str(passphrase or "").encode("utf-8"), salt, 120_000, dklen=64)
    return dk[:32], dk[32:]


def _xor_keystream(data: bytes, enc_key: bytes, nonce: bytes) -> bytes:
    out = bytearray(len(data))
    counter = 0
    offset = 0
    while offset < len(data):
        block = hashlib.sha256(enc_key + nonce + struct.pack(">I", counter)).digest()
        chunk = data[offset : offset + 32]
        for i, b in enumerate(chunk):
            out[offset + i] = b ^ block[i]
        offset += 32
        counter += 1
    return bytes(out)


def encrypt_vault_secret(plaintext: str, passphrase: str) -> str:
    """Encrypt a secret using PBKDF2-HMAC-SHA256 key derivation + stream cipher + HMAC-SHA256 authentication."""
    raw = str(plaintext or "").encode("utf-8")
    if not raw:
        raise ValueError("El secreto no puede estar vacío.")
    if not str(passphrase or "").strip():
        raise ValueError("Se requiere la contraseña del usuario prioritario para cifrar la bóveda.")
    salt = os.urandom(16)
    nonce = os.urandom(16)
    enc_key, mac_key = _derive_vault_keys(passphrase.strip(), salt)
    ciphertext = _xor_keystream(raw, enc_key, nonce)
    tag = hmac.new(mac_key, salt + nonce + ciphertext, hashlib.sha256).digest()
    packed = base64.urlsafe_b64encode(salt + nonce + tag + ciphertext).decode("ascii")
    return f"CLARA-VAULT-V1:{packed}"


def decrypt_vault_secret(token: str, passphrase: str) -> str:
    """Verify HMAC-SHA256 and decrypt a vault secret using the user's passphrase."""
    clean_token = str(token or "").strip()
    if not clean_token.startswith("CLARA-VAULT-V1:"):
        raise ValueError("Formato de secreto encriptado no válido.")
    raw = base64.urlsafe_b64decode(clean_token.split(":", 1)[1].encode("ascii"))
    if len(raw) < 64:
        raise ValueError("Datos encriptados incompletos.")
    salt, nonce, tag, ciphertext = raw[:16], raw[16:32], raw[32:64], raw[64:]
    enc_key, mac_key = _derive_vault_keys(str(passphrase or "").strip(), salt)
    expected_tag = hmac.new(mac_key, salt + nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("Contraseña incorrecta para desencriptar este secreto.")
    plaintext_bytes = _xor_keystream(ciphertext, enc_key, nonce)
    return plaintext_bytes.decode("utf-8")


def register_security_user(
    db: sqlite3.Connection,
    username: str,
    password: str,
    access_level: int | str = 3,
) -> dict[str, object]:
    """Create or update a security user with hashed password and access level (0..3)."""
    ensure_security_tables(db)
    clean_user = re.sub(r"\s+", " ", str(username or "").strip())
    clean_pw = str(password or "").strip()
    if not clean_user or len(clean_user) < 2 or len(clean_user) > 40:
        raise ValueError("El nombre de usuario debe tener entre 2 y 40 caracteres.")
    if len(clean_pw) < 4:
        raise ValueError("La contraseña debe tener al menos 4 caracteres.")
    lvl = coerce_security_level(access_level, default=3)
    salt_hex, hash_hex = hash_user_password(clean_pw)
    now_iso = datetime.now().isoformat(timespec="seconds")
    existing = db.execute("SELECT id FROM security_users WHERE LOWER(username)=LOWER(?)", (clean_user,)).fetchone()
    if existing:
        db.execute(
            "UPDATE security_users SET username=?, password_salt=?, password_hash=?, access_level=? WHERE id=?",
            (clean_user, salt_hex, hash_hex, lvl, int(existing["id"])),
        )
    else:
        db.execute(
            "INSERT INTO security_users(username, password_salt, password_hash, access_level, created_at) VALUES(?,?,?,?,?)",
            (clean_user, salt_hex, hash_hex, lvl, now_iso),
        )
    spec = SECURITY_LEVEL_SPECS[lvl]
    db.execute(
        "INSERT INTO security_events(source, summary, created_at) VALUES(?,?,?)",
        ("Control de acceso", f"Usuario registrado/actualizado: {clean_user} ({spec['short']})", now_iso),
    )
    db.commit()
    return {
        "username": clean_user,
        "access_level": lvl,
        "level_name": spec["name"],
        "short_level": spec["short"],
        "capabilities": spec["capabilities"],
        "message": (
            f"Usuario y contraseñas confirmadas: {clean_user}, {spec['name']} "
            f"(Cosas que puede hacer: {spec['capabilities']})."
        ),
    }


def update_security_user_level(
    db: sqlite3.Connection,
    target_username: str,
    new_level: int | str | None = None,
    *,
    increment: bool = False,
    authorized_by: str | None = None,
) -> dict[str, object]:
    """Allow a Nivel 3 (Prioritario) user to authorize or increase/change another user's access level without resetting their password."""
    ensure_security_tables(db)
    clean_user = re.sub(r"\s+", " ", str(target_username or "").strip(" .,;:"))
    if not clean_user:
        raise ValueError("Indica el nombre del usuario cuyo nivel de acceso deseas autorizar o cambiar.")
    row = db.execute(
        "SELECT id, username, access_level FROM security_users WHERE LOWER(username)=LOWER(?) LIMIT 1",
        (clean_user,),
    ).fetchone()
    if row is None:
        return {
            "updated": False,
            "user_exists": False,
            "username": clean_user,
            "access_level": 0,
            "message": (
                f"No encontré al usuario «{clean_user}» registrado. Puedes registrarlo diciendo:\n"
                f"«registrar usuario {clean_user} <contraseña> nivel 2» o desde el botón 🔐 Niveles y Bóveda."
            ),
        }
    prev_lvl = coerce_security_level(row["access_level"], default=1)
    if increment and new_level is None:
        lvl = min(3, prev_lvl + 1)
    else:
        lvl = coerce_security_level(new_level, default=min(3, prev_lvl + 1))
    db.execute(
        "UPDATE security_users SET access_level=? WHERE id=?",
        (lvl, int(row["id"])),
    )
    prev_spec = SECURITY_LEVEL_SPECS[prev_lvl]
    spec = SECURITY_LEVEL_SPECS[lvl]
    authorizer = str(authorized_by or "Propietario (Nivel 3)").strip()
    now_iso = datetime.now().isoformat(timespec="seconds")
    db.execute(
        "INSERT INTO security_events(source, summary, created_at) VALUES(?,?,?)",
        (
            "Control de acceso",
            f"Nivel de {row['username']} autorizado/cambiado de {prev_spec['short']} a {spec['short']} por {authorizer}",
            now_iso,
        ),
    )
    db.commit()
    return {
        "updated": True,
        "user_exists": True,
        "username": str(row["username"]),
        "previous_level": prev_lvl,
        "access_level": lvl,
        "level_name": spec["name"],
        "short_level": spec["short"],
        "capabilities": spec["capabilities"],
        "message": (
            f"✅ Nivel de acceso autorizado por {authorizer}: el usuario «{row['username']}» ahora tiene "
            f"{spec['short']} ({spec['name']}; antes {prev_spec['short']}).\n"
            f"Permisos activos para {row['username']}: {spec['capabilities']}."
        ),
    }


def authenticate_security_user(db: sqlite3.Connection, username: str, password: str) -> dict[str, object]:
    """Authenticate a user by username and password (typed or spoken) and return their clearance."""
    ensure_security_tables(db)
    clean_user = str(username or "").strip()
    clean_pw = str(password or "").strip()
    row = db.execute(
        "SELECT id, username, password_salt, password_hash, access_level FROM security_users WHERE LOWER(username)=LOWER(?) LIMIT 1",
        (clean_user,),
    ).fetchone()
    now_iso = datetime.now().isoformat(timespec="seconds")
    if row is None:
        return {
            "authenticated": False,
            "user_exists": False,
            "username": clean_user,
            "access_level": 0,
            "message": f"No encontré un usuario registrado llamado «{clean_user}».",
        }
    ok = verify_user_password(clean_pw, str(row["password_salt"]), str(row["password_hash"]))
    if not ok:
        db.execute(
            "INSERT INTO security_events(source, summary, created_at) VALUES(?,?,?)",
            ("Control de acceso", f"Intento fallido de contraseña para usuario {row['username']}", now_iso),
        )
        db.commit()
        return {
            "authenticated": False,
            "user_exists": True,
            "username": str(row["username"]),
            "access_level": 0,
            "message": f"Contraseña incorrecta para el usuario {row['username']}. Se mantiene el nivel de acceso actual.",
        }
    lvl = coerce_security_level(row["access_level"], default=1)
    spec = SECURITY_LEVEL_SPECS[lvl]
    db.execute(
        "INSERT INTO security_events(source, summary, created_at) VALUES(?,?,?)",
        ("Control de acceso", f"Sesión autenticada: {row['username']} ({spec['short']})", now_iso),
    )
    db.commit()
    return {
        "authenticated": True,
        "user_exists": True,
        "username": str(row["username"]),
        "access_level": lvl,
        "level_name": spec["name"],
        "short_level": spec["short"],
        "capabilities": spec["capabilities"],
        "message": (
            f"Usuario y contraseñas confirmadas: {row['username']}, {spec['name']} "
            f"(Cosas que puede hacer: {spec['capabilities']})."
        ),
    }


def save_encrypted_secret(
    db: sqlite3.Connection,
    owner_username: str,
    secret_label: str,
    secret_value: str,
    passphrase: str,
) -> dict[str, str]:
    """Encrypt and save a password or secret into the local SQLite vault."""
    ensure_security_tables(db)
    label = str(secret_label or "").strip()[:120]
    owner = str(owner_username or "Propietario").strip()[:40]
    if not label:
        raise ValueError("Indica un nombre o etiqueta para el secreto (por ejemplo: Correo, Banco, WiFi).")
    token = encrypt_vault_secret(secret_value, passphrase)
    now_iso = datetime.now().isoformat(timespec="seconds")
    existing = db.execute(
        "SELECT id FROM encrypted_secrets WHERE LOWER(owner_username)=LOWER(?) AND LOWER(secret_label)=LOWER(?) LIMIT 1",
        (owner, label),
    ).fetchone()
    if existing:
        db.execute(
            "UPDATE encrypted_secrets SET encrypted_payload=?, created_at=? WHERE id=?",
            (token, now_iso, int(existing["id"])),
        )
    else:
        db.execute(
            "INSERT INTO encrypted_secrets(owner_username, secret_label, encrypted_payload, created_at) VALUES(?,?,?,?)",
            (owner, label, token, now_iso),
        )
    db.execute(
        "INSERT INTO security_events(source, summary, created_at) VALUES(?,?,?)",
        ("Bóveda encriptada", f"Secreto cifrado guardado/actualizado: «{label}» por {owner}", now_iso),
    )
    db.commit()
    return {"owner": owner, "label": label, "created_at": now_iso}


def list_decrypted_secrets(
    db: sqlite3.Connection,
    passphrase: str,
    owner_username: str | None = None,
) -> list[dict[str, str]]:
    """Decrypt and return stored secrets for an authenticated Nivel 3 user."""
    ensure_security_tables(db)
    rows = db.execute(
        "SELECT id, owner_username, secret_label, encrypted_payload, created_at FROM encrypted_secrets ORDER BY id DESC"
    ).fetchall()
    output: list[dict[str, str]] = []
    for row in rows:
        try:
            decrypted = decrypt_vault_secret(str(row["encrypted_payload"]), passphrase)
        except Exception:
            decrypted = "[Cifrado con otra contraseña de propietario]"
        output.append(
            {
                "id": str(row["id"]),
                "owner_username": str(row["owner_username"]),
                "secret_label": str(row["secret_label"]),
                "value": decrypted,
                "created_at": str(row["created_at"]),
            }
        )
    return output


def reset_clara_all_data(db: sqlite3.Connection, *, include_vault: bool = False) -> str:
    """Wipe local agenda, tasks, classes, routines, memories, and chat history (Nivel 3 Prioritario only)."""
    ensure_security_tables(db)
    for table in (
        "tasks",
        "classes",
        "class_exceptions",
        "plan_blocks",
        "routines",
        "memories",
        "reminder_events",
        "reminder_actions",
        "chat_history",
    ):
        db.execute(f"DELETE FROM {table}")
    if include_vault:
        db.execute("DELETE FROM encrypted_secrets")
    now_iso = datetime.now().isoformat(timespec="seconds")
    db.execute(
        "INSERT INTO security_events(source, summary, created_at) VALUES(?,?,?)",
        ("Control prioritario", "Restablecimiento de datos locales de CLARA-V autorizado por nivel prioritario", now_iso),
    )
    db.commit()
    return (
        "Se borraron y restablecieron todos los datos operativos de CLARA-V "
        "(clases, tareas, bloques, rutinas, recuerdos e historial de chat)."
    )


def check_action_permission(
    db: sqlite3.Connection,
    action_key: str,
    current_user: str | None,
    current_level: int,
) -> dict[str, object]:
    """Verify if the active session has clearance for action_key; demand credentials if insufficient."""
    ensure_security_tables(db)
    req_level, action_label = ACTION_REQUIRED_LEVELS.get(action_key, (1, action_key))
    user_count = int(db.execute("SELECT COUNT(*) FROM security_users").fetchone()[0])
    # If no users are registered yet, Nivel 1-2 daily operations remain unlocked,
    # whereas Nivel 3 operations (secrets vault, wiping Clara, user management) always require credentials.
    effective_level = current_level if (user_count > 0 or req_level >= 3 or current_user) else 2
    if effective_level >= req_level:
        return {
            "allowed": True,
            "action_key": action_key,
            "action_label": action_label,
            "required_level": req_level,
            "current_level": effective_level,
            "message": "",
        }
    req_spec = SECURITY_LEVEL_SPECS[req_level]
    cur_spec = SECURITY_LEVEL_SPECS.get(current_level, SECURITY_LEVEL_SPECS[0])
    who = f"{current_user} ({cur_spec['short']})" if current_user else f"Invitado ({cur_spec['short']})"
    prompt = (
        f"🔐 Orden detenida por seguridad: la acción «{action_label}» es sensible o destructiva y requiere "
        f"{req_spec['name']} ({req_spec['short']}). Sesión actual: {who}.\n"
        "¿De quién es la orden? Escribe o dicta tu nombre de usuario y contraseña "
        "(por ejemplo: «Luis ju89yt56rf») para verificar si tienes los permisos."
    )
    return {
        "allowed": False,
        "action_key": action_key,
        "action_label": action_label,
        "required_level": req_level,
        "current_level": current_level,
        "message": prompt,
    }


_NON_USERNAME_FIRST_WORDS = {
    "hola", "buenos", "buenas", "buen", "clara", "clara-v", "viernes", "que", "cual", "cuales", "como",
    "cuando", "donde", "por", "para", "quien", "agrega", "agregar", "anade", "anadir", "crea", "crear",
    "registra", "registrar", "elimina", "eliminar", "borra", "borrar", "quita", "quitar", "marca", "marcar",
    "completa", "completar", "termina", "terminar", "reserva", "reservar", "bloquea", "bloquear", "busca",
    "buscar", "abre", "abrir", "mueve", "mover", "inventaria", "inventariar", "noticias", "clima", "ayuda",
    "mis", "mi", "tengo", "me", "nos", "no", "si", "gracias", "adios", "hasta", "repite", "repetir",
    "diagnostico", "resumen", "rutina", "rutinas", "clases", "tareas", "agenda", "horario", "guardar",
    "guarda", "ver", "mostrar", "revisar", "modo", "cerrar", "cambiar", "restablecer", "formatear",
}


def parse_security_chat_command(
    db: sqlite3.Connection,
    text: str,
    *,
    awaiting_credentials: bool = False,
) -> dict[str, object] | None:
    """Detect user/password authentication, user registration, vault queries, or destructive commands in chat/voice."""
    ensure_security_tables(db)
    raw = str(text or "").strip()
    if not raw:
        return None
    low = normalize_intent_text(raw)

    # 1. Explicit user registration: "registrar usuario Luis ju89yt56rf [nivel prioritario]"
    reg_match = re.match(
        r"^(?:registra(?:r)?|crea(?:r)?|alta\s+de|nuevo)\s+usuario\s+([A-Za-zÁÉÍÓÚáéíóúñÑ0-9_.-]{2,30})\s+(?:contrase[nñ]a\s+|clave\s+)?(\S{4,80})(?:\s+nivel\s+(.+))?$",
        raw,
        flags=re.IGNORECASE,
    )
    if reg_match:
        uname, upass, raw_lvl = reg_match.group(1), reg_match.group(2), reg_match.group(3)
        lvl = coerce_security_level(raw_lvl, default=3)
        return {"kind": "register_user", "username": uname, "password": upass, "access_level": lvl}

    # 1b. Nivel 3 user authorization / promotion of another user's access level without requiring their password:
    # e.g. "aumenta el nivel de Ana a 2", "sube el nivel de Ana a nivel avanzado", "cambia el nivel de Ana a 3",
    # "autoriza a Ana con nivel 2", "autoriza al usuario Ana a nivel prioritario", "dale nivel 2 a Ana", "aumenta el nivel de Ana"
    lvl_change_m1 = re.match(
        r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:aumenta(?:r)?|sube|subir|eleva(?:r)?|incrementa(?:r)?|cambia(?:r)?|modifica(?:r)?|actualiza(?:r)?|promueve|promover|baja(?:r)?|asigna(?:r)?|pon(?:er)?)\s+(?:el\s+)?nivel(?:\s+de\s+acceso|\s+de\s+seguridad)?\s+(?:de(?:l\s+usuario)?|a(?:l\s+usuario)?|para)\s+([A-Za-zÁÉÍÓÚáéíóúñÑ0-9_.-]{2,30})(?:\s+(?:a|en|como|al)\s+(?:el\s+)?(?:nivel\s+)?(.+))?$",
        raw,
        flags=re.IGNORECASE,
    )
    if lvl_change_m1:
        uname = lvl_change_m1.group(1).strip(" .,;:")
        raw_target_lvl = (lvl_change_m1.group(2) or "").strip(" .,;:")
        if raw_target_lvl:
            return {
                "kind": "change_user_level",
                "username": uname,
                "access_level": coerce_security_level(raw_target_lvl, default=2),
                "increment": False,
            }
        return {
            "kind": "change_user_level",
            "username": uname,
            "access_level": None,
            "increment": True,
        }

    lvl_change_m2 = re.match(
        r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:autoriza(?:r)?|sube|subir|eleva(?:r)?|promueve|promover|pasa(?:r)?|pon(?:er)?|cambia(?:r)?)\s+(?:a(?:l\s+usuario)?\s+|el\s+usuario\s+)([A-Za-zÁÉÍÓÚáéíóúñÑ0-9_.-]{2,30})\s+(?:a|con|en|al|como)\s+(?:el\s+)?nivel(?:\s+de\s+acceso)?\s+(.+)$",
        raw,
        flags=re.IGNORECASE,
    )
    if lvl_change_m2:
        uname = lvl_change_m2.group(1).strip(" .,;:")
        raw_target_lvl = lvl_change_m2.group(2).strip(" .,;:")
        return {
            "kind": "change_user_level",
            "username": uname,
            "access_level": coerce_security_level(raw_target_lvl, default=2),
            "increment": False,
        }

    lvl_change_m3 = re.match(
        r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:dale|da(?:r)?|asigna(?:r)?|otorga(?:r)?|concede(?:r)?)\s+(?:el\s+)?nivel(?:\s+de\s+acceso)?\s+(.+?)\s+(?:a(?:l\s+usuario)?|para)\s+([A-Za-zÁÉÍÓÚáéíóúñÑ0-9_.-]{2,30})$",
        raw,
        flags=re.IGNORECASE,
    )
    if lvl_change_m3:
        raw_target_lvl = lvl_change_m3.group(1).strip(" .,;:")
        uname = lvl_change_m3.group(2).strip(" .,;:")
        return {
            "kind": "change_user_level",
            "username": uname,
            "access_level": coerce_security_level(raw_target_lvl, default=2),
            "increment": False,
        }

    # 2. Explicit prefixed authentication: "usuario Luis contraseña ju89yt56rf" / "soy Luis clave ju89yt56rf" / "orden de Luis ju89yt56rf"
    auth_prefix_match = re.match(
        r"^(?:soy|usuario|mi\s+usuario\s+es|acceso|login|identificar(?:me)?|orden\s+de|autoriza)\s+([A-Za-zÁÉÍÓÚáéíóúñÑ0-9_.-]{2,30})\s+(?:contrase[nñ]a\s+|clave\s+|pass\s+)?(\S{4,80})$",
        raw,
        flags=re.IGNORECASE,
    )
    if auth_prefix_match:
        return {
            "kind": "login",
            "username": auth_prefix_match.group(1),
            "password": auth_prefix_match.group(2),
        }

    # 3. Direct "<Username> <Password>" (e.g., "Luis ju89yt56rf") typed or spoken:
    tokens = raw.split()
    if len(tokens) == 2:
        cand_user, cand_pass = tokens[0].strip(" ,.:;"), tokens[1].strip()
        cand_user_norm = normalize_intent_text(cand_user)
        if cand_user and cand_pass and len(cand_pass) >= 4:
            existing_user = db.execute(
                "SELECT username FROM security_users WHERE LOWER(username)=LOWER(?) LIMIT 1",
                (cand_user,),
            ).fetchone()
            if existing_user is not None:
                return {"kind": "login", "username": str(existing_user["username"]), "password": cand_pass}
            # Also match if Clara just asked "¿De quién es la orden?" OR if password contains digits and first word isn't a normal command verb
            has_digit_and_alpha = any(c.isdigit() for c in cand_pass) and any(c.isalpha() for c in cand_pass)
            if (
                cand_user_norm not in _NON_USERNAME_FIRST_WORDS
                and re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóúñÑ][A-Za-zÁÉÍÓÚáéíóúñÑ0-9_.-]{1,29}", cand_user)
                and (awaiting_credentials or has_digit_and_alpha)
            ):
                return {"kind": "login", "username": cand_user, "password": cand_pass}

    # 4. Session lock / guest mode / status query
    if low in (
        "bloquear sesion", "bloquea sesion", "cerrar sesion", "cierra sesion",
        "modo invitado", "pasar a invitado", "cambiar a invitado", "salir de mi sesion",
    ):
        return {"kind": "lock_session"}

    if low in (
        "mi nivel de acceso", "que nivel de acceso tengo", "cual es mi nivel de acceso",
        "quien esta conectado", "estado de seguridad", "niveles de seguridad", "permisos actuales",
    ):
        return {"kind": "security_status"}

    # 5. Encrypted secrets vault commands
    save_secret_match = re.match(
        r"^(?:guarda(?:r)?|registra(?:r)?|agrega(?:r)?|anota(?:r)?)\s+(?:el\s+|mi\s+|un\s+)?(?:secreto(?:\s+encriptado)?|contrase[nñ]a(?:\s+guardada|\s+de)?|clave\s+de)\s+([^:]+?)(?:\s*[:=]\s*|\s+es\s+)(.+)$",
        raw,
        flags=re.IGNORECASE,
    )
    if save_secret_match:
        return {
            "kind": "save_secret",
            "label": save_secret_match.group(1).strip(" .,;-"),
            "value": save_secret_match.group(2).strip(),
        }

    if any(
        phrase in low
        for phrase in (
            "ver contrasenas", "ver mis contrasenas", "contrasenas guardadas",
            "ver secretos", "secretos encriptados", "revisar secretos",
            "mostrar secretos", "abrir boveda", "mostrar boveda", "ver boveda",
        )
    ):
        return {"kind": "view_secrets"}

    # 6. Destructive reset / delete Clara command
    if any(
        phrase in low
        for phrase in (
            "borrar a clara", "borra a clara", "borrar datos de clara", "borrar todos los datos de clara",
            "restablecer a clara", "restablece a clara", "formatear a clara", "eliminar a clara",
        )
    ):
        return {"kind": "delete_clara_data"}

    return None


def build_ollama_unavailable_message(detail: str = "") -> str:
    """Return a clear, user-friendly Spanish notice when local Ollama cannot be used for open questions."""
    base = (
        "En este momento mi motor neuronal local (Ollama) no está disponible, por lo que mis capacidades "
        "se encuentran en modo local esencial y no puedo responder a todas las preguntas abiertas o de conocimiento general.\n"
        "Aun así, siguen activas todas mis funciones locales integradas: puedo agregar y consultar tus clases, tareas, bloques "
        "y rutinas, decirte qué sigue hoy, revisar el clima y titulares, explorar carpetas/archivos permitidos y gestionar "
        "tus niveles de seguridad y bóveda encriptada."
    )
    clean_detail = str(detail or "").strip()
    if clean_detail and "not found" in clean_detail.casefold():
        base += "\n\n💡 Nota: Parece que el modelo «llama3.2» aún no termina de instalarse en Ollama. Pulsa el botón «⬇ Descargar llama3.2…» o dime «descargar modelo llama3.2»."
    return base


def select_preferred_ollama_model(models: list[str], current: str = "") -> str:
    """Choose the best available local Ollama model, prioritizing 'llama3.2' (used in Viernes)."""
    clean_models = [str(m).strip() for m in (models or []) if str(m).strip()]
    if not clean_models:
        return ""
    if current and current in clean_models:
        return current
    for pref in PREFERRED_OLLAMA_MODELS:
        exact = next((m for m in clean_models if m.casefold() == pref.casefold()), None)
        if exact:
            return exact
        prefix = next((m for m in clean_models if m.casefold().startswith(pref.casefold())), None)
        if prefix:
            return prefix
    return clean_models[0]


def list_local_ollama_models(host: str = "http://127.0.0.1:11434") -> list[str]:
    """List installed local Ollama models using the Python 'ollama' module directly (with HTTP fallback)."""
    if OLLAMA_PYTHON_MODULE_AVAILABLE and ollama_sdk is not None:
        try:
            client = ollama_sdk.Client(host=host)
            raw = client.list()
            items = getattr(raw, "models", None)
            if items is None and isinstance(raw, dict):
                items = raw.get("models", [])
            names: list[str] = []
            for item in items or []:
                name = getattr(item, "model", None) or getattr(item, "name", None)
                if not name and isinstance(item, dict):
                    name = item.get("model") or item.get("name")
                if name:
                    names.append(str(name))
            if names:
                return names
        except Exception:
            pass
    last_exc: Exception | None = None
    for candidate_host in (host, "http://localhost:11434", "http://127.0.0.1:11434"):
        try:
            req = urllib.request.Request(
                f"{candidate_host.rstrip('/')}/api/tags",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=6.0) as resp:
                raw_models = json.loads(resp.read().decode("utf-8")).get("models", [])
            return [str(m.get("name", "")) for m in raw_models if m.get("name")]
        except Exception as exc:
            last_exc = exc
    if last_exc is not None:
        raise last_exc
    return []


def _consolidate_ollama_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Combine multiple system messages into a single initial system message (compatible with llama3.2 in Viernes)."""
    sys_parts: list[str] = []
    other_msgs: list[dict[str, str]] = []
    for msg in messages or []:
        role = str(msg.get("role") or "user")
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        if role == "system":
            sys_parts.append(content)
        else:
            other_msgs.append({"role": role, "content": content})
    consolidated: list[dict[str, str]] = []
    if sys_parts:
        consolidated.append({"role": "system", "content": "\n\n".join(sys_parts)})
    consolidated.extend(other_msgs)
    return consolidated


def _model_supports_think_parameter(model: str) -> bool:
    """Return True only for models that accept Ollama's 'think' parameter (llama3.2 rejects 'think' with HTTP 400)."""
    low_m = str(model or "").casefold()
    return any(tok in low_m for tok in ("qwen3", "deepseek-r1", "qwq"))


def stream_ollama_chat_direct(
    model: str,
    messages: list[dict[str, str]],
    *,
    options: dict[str, object] | None = None,
    cancel_event: threading.Event | None = None,
    host: str = "http://127.0.0.1:11434",
    on_http_response=None,
):
    """Stream conversational responses via ollama.Client.chat or HTTP /api/chat (with Viernes non-stream fallback)."""
    opts = options or {"temperature": 0.45, "num_ctx": 4096, "num_predict": 900}
    clean_messages = _consolidate_ollama_messages(messages)
    use_think = _model_supports_think_parameter(model)

    if OLLAMA_PYTHON_MODULE_AVAILABLE and ollama_sdk is not None:
        try:
            client = ollama_sdk.Client(host=host)
            chat_kwargs: dict[str, object] = {
                "model": model,
                "messages": clean_messages,
                "stream": True,
                "options": opts,
            }
            if use_think:
                chat_kwargs["think"] = False
            try:
                stream = client.chat(**chat_kwargs)
            except Exception:
                chat_kwargs.pop("think", None)
                stream = client.chat(**chat_kwargs)
            if callable(on_http_response):
                on_http_response(stream)
            for chunk in stream:
                if cancel_event is not None and cancel_event.is_set():
                    break
                msg_obj = getattr(chunk, "message", None)
                if msg_obj is not None:
                    content = getattr(msg_obj, "content", "") or ""
                elif isinstance(chunk, dict):
                    content = chunk.get("message", {}).get("content", "") or ""
                else:
                    content = ""
                done_flag = getattr(chunk, "done", None)
                if done_flag is None and isinstance(chunk, dict):
                    done_flag = bool(chunk.get("done"))
                yield str(content), bool(done_flag)
            return
        except Exception:
            if cancel_event is not None and cancel_event.is_set():
                return
            # Fall back to local HTTP endpoint if the SDK raised a transport/version mismatch

    payload_dict: dict[str, object] = {
        "model": model,
        "messages": clean_messages,
        "stream": True,
        "options": opts,
    }
    if use_think:
        payload_dict["think"] = False

    try:
        body = json.dumps(payload_dict).encode("utf-8")
        request = urllib.request.Request(
            f"{host.rstrip('/')}/api/chat",
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        response = urllib.request.urlopen(request, timeout=120)
        if callable(on_http_response):
            on_http_response(response)
        try:
            for raw_line in response:
                if cancel_event is not None and cancel_event.is_set():
                    break
                if not raw_line.strip():
                    continue
                data = json.loads(raw_line.decode("utf-8"))
                fragment = str(data.get("message", {}).get("content", "") or "")
                done_flag = bool(data.get("done"))
                yield fragment, done_flag
                if done_flag:
                    break
            return
        finally:
            try:
                response.close()
            except Exception:
                pass
    except Exception:
        if cancel_event is not None and cancel_event.is_set():
            return
        # Fallback to Viernes's exact non-streaming /api/chat request (Bienvenido_Señor/viernes_app/integrations/ai.py)
        fallback_payload = {
            "model": model,
            "messages": clean_messages,
            "stream": False,
            "options": opts,
        }
        req_fb = urllib.request.Request(
            f"{host.rstrip('/')}/api/chat",
            data=json.dumps(fallback_payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_fb, timeout=120) as resp_fb:
            result_fb = json.loads(resp_fb.read().decode("utf-8"))
            text_fb = str(result_fb.get("message", {}).get("content", "") or "").strip()
            yield text_fb, True


def _is_transient_ollama_pull_error(err_text: str) -> bool:
    low = str(err_text or "").casefold()
    return any(
        token in low
        for token in (
            "tls handshake timeout",
            "max retries exceeded",
            "i/o timeout",
            "connection reset",
            "unexpected eof",
            "eof",
            "temporary failure",
            "cloudflarestorage",
            "timed out",
        )
    )


def pull_ollama_model_direct(
    model_name: str,
    *,
    progress_callback=None,
    host: str = "http://127.0.0.1:11434",
    max_attempts: int = 8,
    retry_delay: float = 2.0,
) -> tuple[bool, str]:
    """Download/pull a local Ollama model (such as 'llama3.2') with automatic resume on Cloudflare R2 TLS timeouts."""
    clean_model = re.sub(r"[^A-Za-z0-9_.:/-]", "", str(model_name or "").strip())
    if not clean_model:
        return (False, "Indica un nombre de modelo válido (por ejemplo: llama3.2).")
    ensure_local_ollama_running()

    # Check if the requested model is already downloaded locally in Ollama (e.g. from Viernes)
    try:
        installed = list_local_ollama_models(host=host)
        already_match = next(
            (
                m for m in installed
                if m.casefold() == clean_model.casefold()
                or m.casefold() == f"{clean_model.casefold()}:latest"
            ),
            None,
        )
        if already_match:
            if callable(progress_callback):
                progress_callback(f"Modelo «{already_match}» ya detectado localmente en este equipo.")
            return (
                True,
                f"✅ El modelo «{already_match}» ya se encontraba instalado en tu Ollama local (de Viernes) y quedó activo de inmediato.",
            )
    except Exception:
        pass

    if callable(progress_callback):
        progress_callback(f"Iniciando descarga del modelo «{clean_model}» en Ollama local…")

    last_error = ""
    total_attempts = max(1, int(max_attempts))

    for attempt in range(1, total_attempts + 1):
        attempt_error = ""

        # 1. Primary path: Python 'ollama' module (ollama.Client.pull)
        if OLLAMA_PYTHON_MODULE_AVAILABLE and ollama_sdk is not None:
            try:
                client = ollama_sdk.Client(host=host)
                for part in client.pull(model=clean_model, stream=True):
                    err_val = getattr(part, "error", None) or (part.get("error") if isinstance(part, dict) else None)
                    if err_val:
                        raise RuntimeError(str(err_val))
                    status = getattr(part, "status", None) or (part.get("status") if isinstance(part, dict) else "") or "descargando"
                    completed = getattr(part, "completed", None) or (part.get("completed") if isinstance(part, dict) else 0) or 0
                    total = getattr(part, "total", None) or (part.get("total") if isinstance(part, dict) else 0) or 0
                    if callable(progress_callback):
                        if total and completed:
                            pct = min(100, int((int(completed) * 100) / max(1, int(total))))
                            progress_callback(f"Descargando «{clean_model}» (intento {attempt}/{total_attempts}): {status} ({pct}%)")
                        else:
                            progress_callback(f"Descargando «{clean_model}» (intento {attempt}/{total_attempts}): {status}")
                return (True, f"✅ Modelo «{clean_model}» descargado y listo en Ollama local.")
            except Exception as sdk_exc:
                attempt_error = str(sdk_exc)

        # 2. Fallback path: Local Ollama HTTP API (/api/pull)
        if not attempt_error:
            try:
                body = json.dumps({"name": clean_model, "stream": True}).encode("utf-8")
                req = urllib.request.Request(
                    f"{host.rstrip('/')}/api/pull",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=600) as resp:
                    for raw_line in resp:
                        if not raw_line.strip():
                            continue
                        data = json.loads(raw_line.decode("utf-8"))
                        if data.get("error"):
                            raise RuntimeError(str(data["error"]))
                        status = str(data.get("status") or "descargando")
                        completed = int(data.get("completed") or 0)
                        total = int(data.get("total") or 0)
                        if callable(progress_callback):
                            if total > 0 and completed >= 0:
                                pct = min(100, int((completed * 100) / total))
                                progress_callback(f"Descargando «{clean_model}» (intento {attempt}/{total_attempts}): {status} ({pct}%)")
                            else:
                                progress_callback(f"Descargando «{clean_model}» (intento {attempt}/{total_attempts}): {status}")
                return (True, f"✅ Modelo «{clean_model}» descargado y listo en Ollama local.")
            except Exception as http_exc:
                attempt_error = str(http_exc)

        last_error = attempt_error

        # 3. If Cloudflare R2 had a TLS handshake timeout, also try local CLI with GODEBUG=http2client=0
        exe = find_installed_ollama_executable()
        if exe is not None and _is_transient_ollama_pull_error(attempt_error):
            try:
                if callable(progress_callback):
                    progress_callback(
                        f"Reintentando «{clean_model}» en modo HTTP/1.1 anti-timeout TLS ({attempt}/{total_attempts})…"
                    )
                cli_env = dict(os.environ)
                cli_env["GODEBUG"] = "http2client=0"
                cli_env["OLLAMA_NOPRUNE"] = "1"
                proc = subprocess.run(
                    [str(exe), "pull", clean_model],
                    capture_output=True,
                    text=True,
                    timeout=600,
                    shell=False,
                    env=cli_env,
                )
                if proc.returncode == 0:
                    return (True, f"✅ Modelo «{clean_model}» descargado y reanudado con éxito en Ollama local.")
                last_error = (proc.stderr or proc.stdout or attempt_error).strip()
            except Exception as cli_exc:
                last_error = str(cli_exc)

        if attempt < total_attempts and _is_transient_ollama_pull_error(last_error):
            if callable(progress_callback):
                progress_callback(
                    f"Corte TLS temporal de Cloudflare R2; reanudando descarga parcial de «{clean_model}» ({attempt + 1}/{total_attempts})…"
                )
            if retry_delay > 0:
                time.sleep(retry_delay)
            continue
        break

    return (
        False,
        f"Ollama reportó un corte de red/TLS con Cloudflare R2 al descargar «{clean_model}»: {last_error}\n"
        "💡 El avance descargado NO se pierde (Ollama guarda los bloques parciales). "
        "Ejecuta `descargar_llama3.2.bat` (que fuerza modo HTTP/1.1 `GODEBUG=http2client=0` y reanuda en bucle hasta terminar) "
        "o vuelve a pulsar «⬇ Descargar llama3.2…» para continuar desde donde se quedó.",
    )



def inclusive_dates(start: date, end: date | None = None, max_days: int = 730) -> list[date]:
    """Return an inclusive calendar range with a defensive maximum length."""
    end = end or start
    if end < start:
        raise ValueError("La fecha final debe ser igual o posterior a la inicial.")
    if (end - start).days > max_days:
        raise ValueError("El rango supera el máximo permitido.")
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def next_repeat_date(current_due: date, rule: str, today: date) -> date:
    """Compute the next daily/weekly occurrence in the PC's local calendar."""
    if rule == "daily":
        return max(current_due, today) + timedelta(days=1)
    if rule == "weekly":
        if current_due >= today:
            return current_due + timedelta(days=7)
        days_ahead = (current_due.weekday() - today.weekday()) % 7
        return today + timedelta(days=days_ahead or 7)
    raise ValueError(f"Regla de repetición no compatible: {rule}")


def active_memories_for(db: sqlite3.Connection, today: date | None = None) -> list[sqlite3.Row]:
    """Return only unexpired memories permitted for local-model context."""
    today = today or date.today()
    return db.execute("SELECT label,category,content,source,created_at,expires_on FROM memories WHERE expires_on IS NULL OR expires_on>=? ORDER BY id DESC LIMIT 20", (today.isoformat(),)).fetchall()


def find_routine_pattern_candidates(db: sqlite3.Connection, today: date | None = None) -> list[dict[str, object]]:
    """Find exact repeats in completed, manually created tasks from the last 90 days."""
    today = today or date.today()
    cutoff = (today - timedelta(days=90)).isoformat()
    rows = db.execute("SELECT title,subject,due_date,due_time FROM tasks WHERE done=1 AND completed_at IS NOT NULL AND completed_at>=? AND routine_id IS NULL AND repeat_series_id IS NULL AND external_uid IS NULL AND (repeat_rule IS NULL OR repeat_rule='none') AND due_date BETWEEN ? AND ? ORDER BY due_date", (cutoff, cutoff, today.isoformat())).fetchall()
    groups: dict[tuple[str,str,str|None,int],dict[str,object]] = {}
    for row in rows:
        try:
            occurred = date.fromisoformat(row["due_date"])
        except (TypeError,ValueError):
            continue
        normalized_title = re.sub(r"\s+"," ",str(row["title"] or "").strip()).casefold()
        if not normalized_title:
            continue
        subject = (str(row["subject"]).strip() if row["subject"] else None)
        key=(normalized_title,(subject or "").casefold(),row["due_time"],occurred.weekday())
        item=groups.setdefault(key,{"title":str(row["title"]).strip(),"subject":subject,"due_time":row["due_time"],"weekday":occurred.weekday(),"dates":set()})
        item["dates"].add(occurred)
    existing=list(db.execute("SELECT title,subject,weekdays,reminder_time FROM routines"))
    suggestions=[]
    for item in groups.values():
        dates=item["dates"]
        weeks={(d.isocalendar().year,d.isocalendar().week) for d in dates}
        if len(dates)<3 or len(weeks)<3:
            continue
        weekdays=str(item["weekday"])
        if any(str(r["title"]).strip().casefold()==str(item["title"]).casefold() and str(r["subject"] or "").strip().casefold()==str(item["subject"] or "").casefold() and weekdays in str(r["weekdays"]).split(",") and r["reminder_time"]==item["due_time"] for r in existing):
            continue
        suggestions.append({"title":item["title"],"subject":item["subject"],"weekdays":weekdays,"reminder_time":item["due_time"],"occurrences":len(dates),"last_seen":max(dates).isoformat()})
    return sorted(suggestions,key=lambda item:(-int(item["occurrences"]),str(item["title"]).casefold()))


def local_timezone_label(now: datetime | None = None) -> str:
    local = (now or datetime.now()).astimezone()
    offset = local.utcoffset() or timedelta(0)
    minutes = int(offset.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    hours, remainder = divmod(abs(minutes), 60)
    return f"{local.tzname() or 'local'} · UTC{sign}{hours:02d}:{remainder:02d}"


def toggle_task_completion(db: sqlite3.Connection, task_id: int, now: datetime | None = None) -> str | None:
    """Mark a task done/reopen it and create at most one future recurring copy."""
    now = now or datetime.now()
    task = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        return None
    if task["done"]:
        db.execute("UPDATE tasks SET done=0,reminded=0,completed_at=NULL WHERE id=?", (task_id,))
        message = f"Reabrí “{task['title']}”."
    else:
        db.execute("UPDATE tasks SET done=1,reminded=0,completed_at=? WHERE id=?", (now.isoformat(timespec="seconds"),task_id))
        message = f"Marcada como hecha: “{task['title']}”."
        rule = task["repeat_rule"] or "none"
        if rule in ("daily", "weekly") and task["due_date"]:
            series_id = task["repeat_series_id"] or task_id
            db.execute("UPDATE tasks SET repeat_series_id=? WHERE id=?", (series_id, task_id))
            pending_successor = db.execute("SELECT 1 FROM tasks WHERE repeat_series_id=? AND done=0 AND id<>? AND due_date>? LIMIT 1", (series_id, task_id, task["due_date"])).fetchone()
            if not pending_successor:
                next_date = next_repeat_date(date.fromisoformat(task["due_date"]), rule, now.date())
                db.execute("INSERT INTO tasks(title,description,due_date,priority,done,created_at,due_time,subject,repeat_rule,repeat_series_id) VALUES(?,?,?,?,?,?,?,?,?,?)", (task["title"], task["description"], next_date.isoformat(), task["priority"], 0, now.isoformat(timespec="seconds"), task["due_time"], task["subject"], rule, series_id))
                message += f" Próxima ocurrencia: {next_date.strftime('%d/%m/%Y')}."
            else:
                message += " Ya existe una próxima ocurrencia pendiente; no dupliqué la serie."
    db.commit()
    return message


def day_off_for(db: sqlite3.Connection, target: date) -> sqlite3.Row | None:
    return db.execute("SELECT * FROM class_exceptions WHERE exception_date=? AND action='no_classes' ORDER BY id DESC LIMIT 1", (target.isoformat(),)).fetchone()


def classes_for_date(db: sqlite3.Connection, target: date) -> list[dict[str, object]]:
    """Resolve a weekly schedule against explicit one-day school-calendar exceptions."""
    closed = day_off_for(db, target) is not None
    meetings: list[dict[str, object]] = []
    if not closed:
        base = db.execute("SELECT * FROM classes WHERE weekday=? ORDER BY start_time,name", (target.weekday(),)).fetchall()
        for row in base:
            exception = db.execute("SELECT * FROM class_exceptions WHERE exception_date=? AND class_id=? AND action IN ('cancel','override') ORDER BY id DESC LIMIT 1", (target.isoformat(), row["id"])).fetchone()
            if exception and exception["action"] == "cancel":
                continue
            meetings.append({"id": row["id"], "name": exception["name"] if exception and exception["name"] else row["name"],
                "start_time": exception["start_time"] if exception and exception["start_time"] else row["start_time"],
                "end_time": exception["end_time"] if exception and exception["end_time"] else row["end_time"],
                "location": exception["location"] if exception and exception["location"] else row["location"],
                "reminded_on": row["reminded_on"], "source": "class", "uid": f"class-{row['id']}"})
    specials = db.execute("SELECT * FROM class_exceptions WHERE exception_date=? AND action='extra' ORDER BY start_time,name", (target.isoformat(),)).fetchall()
    for row in specials:
        meetings.append({"id": None, "name": row["name"] or row["class_name"] or "Clase especial", "start_time": row["start_time"],
            "end_time": row["end_time"], "location": row["location"], "reminded_on": row["reminded_on"],
            "source": "exception", "exception_id": row["id"], "uid": f"exception-{row['id']}"})
    return sorted(meetings, key=lambda row: str(row["start_time"] or "23:59"))


def build_afternoon_draft(db: sqlite3.Connection, target_day: date, now: datetime, limit: int = 4) -> tuple[list[dict[str, str]], int]:
    """Propose editable 45-minute local blocks without writing anything to SQLite."""
    horizon = target_day + timedelta(days=7)
    tasks = db.execute("SELECT id,title,due_date,due_time,priority FROM tasks WHERE done=0 AND (due_date IS NULL OR due_date<=?)", (horizon.isoformat(),)).fetchall()
    priority_order = {"Alta": 0, "Normal": 1, "Baja": 2}
    tasks = sorted(tasks, key=lambda row: (0 if row["due_date"] and row["due_date"] <= target_day.isoformat() else 1 if row["due_date"] else 2, row["due_date"] or "9999-12-31", priority_order.get(row["priority"], 1), row["due_time"] or "99:99", row["id"]))
    omitted = max(0, len(tasks) - limit)
    tasks = tasks[:limit]
    if not tasks:
        return [], 0
    occupied: list[tuple[datetime, datetime]] = []
    for meeting in classes_for_date(db, target_day):
        start = datetime.combine(target_day, datetime.strptime(str(meeting["start_time"]), "%H:%M").time())
        end_value = str(meeting["end_time"] or "")
        end = datetime.combine(target_day, datetime.strptime(end_value, "%H:%M").time()) if end_value else start + timedelta(hours=1)
        if end <= start:
            end = start + timedelta(hours=1)
        occupied.append((start, end))
    for row in db.execute("SELECT start_time,end_time FROM plan_blocks WHERE block_date=?", (target_day.isoformat(),)):
        start = datetime.combine(target_day, datetime.strptime(row["start_time"], "%H:%M").time())
        end = datetime.combine(target_day, datetime.strptime(row["end_time"], "%H:%M").time())
        occupied.append((start, end))
    earliest = datetime.combine(target_day, datetime.strptime("13:00", "%H:%M").time())
    earliest = max(earliest, now + timedelta(minutes=10))
    minute_of_day = earliest.hour * 60 + earliest.minute
    minute_of_day = ((minute_of_day + 14) // 15) * 15
    cursor = datetime.combine(target_day, datetime.min.time()) + timedelta(minutes=minute_of_day)
    work_end = datetime.combine(target_day, datetime.strptime("20:00", "%H:%M").time())
    drafts: list[dict[str, str]] = []
    for task in tasks:
        while cursor + timedelta(minutes=45) <= work_end:
            end = cursor + timedelta(minutes=45)
            conflict = next(((start, stop) for start, stop in occupied if cursor < stop and end > start), None)
            if conflict:
                cursor = conflict[1] + timedelta(minutes=15)
                minute = cursor.hour * 60 + cursor.minute
                cursor = datetime.combine(target_day, datetime.min.time()) + timedelta(minutes=((minute + 14) // 15) * 15)
                continue
            break
        else:
            break
        drafts.append({"title": str(task["title"]), "block_date": target_day.isoformat(), "start_time": cursor.strftime("%H:%M"), "end_time": end.strftime("%H:%M"), "notes": "Propuesta local revisable · duración sugerida de 45 min."})
        occupied.append((cursor, end))
        cursor = end + timedelta(minutes=15)
    return drafts, omitted + max(0, len(tasks) - len(drafts))


def collect_due_alerts(db: sqlite3.Connection, now: datetime) -> list[dict[str, str]]:
    """Return due local-time alerts while preserving per-occurrence delivery state."""
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")
    today = now.date().isoformat()
    db.execute("BEGIN IMMEDIATE")
    candidates: list[dict[str, str]] = []
    tasks = db.execute("SELECT id,title,subject,due_date,due_time FROM tasks WHERE done=0 AND due_date IS NOT NULL AND due_time IS NOT NULL AND due_date || ' ' || due_time <= ? ORDER BY due_date,due_time", (now.strftime("%Y-%m-%d %H:%M"),)).fetchall()
    for task in tasks:
        label = f"Tarea: {task['title']}" + (f" ({task['subject']})" if task["subject"] else "")
        due = f"{task['due_date']} {task['due_time']}"
        candidates.append({"alert_key": f"task:{task['id']}:{due}", "source_type": "task", "source_id": str(task["id"]), "title": label, "due_at_local": due, "message": f"{label} · programada {due}"})
    weekday_names = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    for meeting in classes_for_date(db, now.date()):
        if meeting["reminded_on"] == today:
            continue
        start_text = str(meeting["start_time"])
        start = datetime.combine(now.date(), datetime.strptime(start_text, "%H:%M").time())
        seconds_until = (start - now).total_seconds()
        if seconds_until > 15 * 60:
            continue
        if meeting["source"] == "class":
            source_id = int(meeting["id"])
            key = f"class:{source_id}:{today}"
        else:
            source_id = int(meeting["exception_id"])
            key = f"class_exception:{source_id}:{today}"
        place = f" · {meeting['location']}" if meeting["location"] else ""
        if seconds_until >= 0:
            minutes = max(0, int((seconds_until + 59) // 60))
            message = f"Clase en {minutes} min: {meeting['name']} ({weekday_names[now.weekday()]} {start_text}){place}"
        else:
            message = f"Clase que inició a las {start_text}: {meeting['name']} ({weekday_names[now.weekday()]}){place} · aviso tardío tras reanudar la comprobación"
        candidates.append({"alert_key": key, "source_type": "class", "source_id": str(source_id), "title": str(meeting["name"]), "due_at_local": f"{today} {start_text}", "message": message})
    ready: list[dict[str, str]] = []
    for candidate in candidates:
        row = db.execute("SELECT * FROM reminder_events WHERE alert_key=?", (candidate["alert_key"],)).fetchone()
        if row is None:
            db.execute("INSERT INTO reminder_events(alert_key,source_type,source_id,title,due_at_local,state,next_notify_at) VALUES(?,?,?,?,?,'pending',?)", (candidate["alert_key"], candidate["source_type"], candidate["source_id"], candidate["title"], candidate["due_at_local"], now_text))
            db.execute("INSERT INTO reminder_actions(alert_key,action,action_at,details) VALUES(?,?,?,?)", (candidate["alert_key"], "created", now_text, "Aviso local detectado"))
            row = db.execute("SELECT * FROM reminder_events WHERE alert_key=?", (candidate["alert_key"],)).fetchone()
        if row["state"] == "dismissed":
            continue
        if row["state"] == "snoozed" and row["snooze_until"] and row["snooze_until"] > now_text:
            continue
        if row["next_notify_at"] <= now_text:
            next_notify = (now + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
            updated = db.execute("UPDATE reminder_events SET state='pending',snooze_until=NULL,delivery_count=delivery_count+1,last_delivered_at=?,next_notify_at=? WHERE alert_key=? AND state!='dismissed' AND next_notify_at<=?", (now_text, next_notify, candidate["alert_key"], now_text))
            if updated.rowcount:
                db.execute("INSERT INTO reminder_actions(alert_key,action,action_at,details) VALUES(?,?,?,?)", (candidate["alert_key"], "delivered", now_text, candidate["message"]))
                ready.append(candidate)
                break
    db.commit()
    return ready


def record_alert_action(db: sqlite3.Connection, alert_key: str, action: str, now: datetime, minutes: int = 10) -> None:
    now_text = now.strftime("%Y-%m-%d %H:%M:%S")
    if action == "snoozed":
        until = (now + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        db.execute("UPDATE reminder_events SET state='snoozed',snooze_until=?,next_notify_at=? WHERE alert_key=?", (until, until, alert_key))
        details = f"Pospuesto {minutes} minutos, hasta {until} (hora local del equipo)"
    else:
        db.execute("UPDATE reminder_events SET state='dismissed',snooze_until=NULL WHERE alert_key=?", (alert_key,))
        details = "Descartado por el usuario"
        action = "dismissed"
    db.execute("INSERT INTO reminder_actions(alert_key,action,action_at,details) VALUES(?,?,?,?)", (alert_key, action, now_text, details))
    db.commit()


def reminder_pause_active(settings: dict[str, str], now: datetime | None = None) -> bool:
    raw = settings.get("reminders_paused_until", "")
    if not raw:
        return False
    try:
        until = datetime.fromisoformat(raw)
    except ValueError:
        return False
    current = now or datetime.now()
    if until.tzinfo is not None:
        until = until.astimezone().replace(tzinfo=None)
    return until > current


def show_windows_private_toast() -> bool:
    """Best-effort generic Windows toast; never includes task or class titles."""
    if sys.platform != "win32":
        return False
    try:
        from winotify import Notification
        toast = Notification(app_id="Clara.AsistentePersonal", title="Clara tiene un recordatorio", msg="Abre Clara para revisar los detalles y posponer o descartar el aviso.", duration="short")
        toast.show()
        return True
    except Exception:
        return False


def present_reminder(
    parent: tk.Misc,
    alert: dict[str, str],
    db: sqlite3.Connection,
    close_callback=None,
    open_app_callback=None,
) -> tk.Toplevel:
    window = tk.Toplevel(parent)
    window.title("Recordatorio local · CLARA-V")
    window.transient(parent)
    window.resizable(False, False)
    frame = ttk.Frame(window, padding=18)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Recordatorio · CLARA-V", style="CardTitle.TLabel").pack(anchor="w")
    ttk.Label(frame, text=alert["message"], wraplength=430, justify="left").pack(anchor="w", pady=(10, 8))
    ttk.Label(frame, text=f"Hora local del equipo · {local_timezone_label()} · si se cierra sin descartar, volverá a avisar.", wraplength=430, foreground="#91aabd").pack(anchor="w", pady=(0, 14))

    def finish(action: str | None = None, launch_full_app: bool = False) -> None:
        if action:
            record_alert_action(db, alert["alert_key"], action, datetime.now())
        window.destroy()
        if launch_full_app and open_app_callback:
            open_app_callback()
        elif close_callback:
            close_callback()

    ttk.Button(frame, text="Posponer 10 min", command=lambda: finish("snoozed")).pack(side="left")
    ttk.Button(frame, text="Descartar este aviso", command=lambda: finish("dismissed")).pack(side="left", padx=8)
    if open_app_callback is not None:
        ttk.Button(frame, text="Abrir CLARA-V", command=lambda: finish(None, launch_full_app=True)).pack(side="left")
    window.protocol("WM_DELETE_WINDOW", lambda: finish(None))
    window.grab_set()
    return window


def compute_adaptive_window_geometry(screen_width: int, screen_height: int) -> dict[str, int | str]:
    """Compute safe window dimensions and minsize that fit small screens and 125%/150% Windows DPI scaling."""
    sw = max(680, int(screen_width or 1280))
    sh = max(440, int(screen_height or 820))
    min_w = min(680, max(560, sw - 40))
    min_h = min(440, max(380, sh - 60))
    width = min(1280, max(min_w, sw - 48))
    height = min(820, max(min_h, sh - 72))
    x = max(0, (sw - width) // 2)
    y = max(0, (sh - height) // 3)
    return {
        "width": width,
        "height": height,
        "x": x,
        "y": y,
        "min_width": min_w,
        "min_height": min_h,
        "geometry": f"{width}x{height}+{x}+{y}",
    }


def sphere_radius_for_state(state: str, width: float = 150.0, height: float = 112.0) -> float:
    """Compute sphere radius; expands only when state == 'speaking'."""
    expanded = state == "speaking"
    radius = min(width * (0.22 if expanded else 0.15), height * (0.29 if expanded else 0.20))
    return max(18.0, float(radius))


class ClaraSphere(tk.Canvas):
    """Compact data-sphere indicator; it expands only for spoken output."""
    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, highlightthickness=0, bd=0, **kwargs)
        self.state = "idle"
        self.phase = 0.0
        self._animation_id = None
        self.bind("<Configure>", lambda _event: self.draw())
        self.draw()

    @property
    def is_expanded(self) -> bool:
        return self.state == "speaking"

    def compute_radius(self, width: float = 150.0, height: float = 112.0) -> float:
        return sphere_radius_for_state(self.state, width, height)

    def set_state(self, state: str) -> None:
        if state not in ("idle", "listening", "speaking"):
            state = "idle"
        if self._animation_id is not None:
            try:
                self.after_cancel(self._animation_id)
            except tk.TclError:
                pass
            self._animation_id = None
        self.state = state
        self.phase = 0.0
        if state == "speaking":
            self._tick()
        else:
            self.draw()

    def _tick(self) -> None:
        if self.state != "speaking":
            self._animation_id = None
            return
        self.phase += 0.075
        self.draw()
        self._animation_id = self.after(65, self._tick)

    def draw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), self.winfo_reqwidth(), 130)
        height = max(self.winfo_height(), self.winfo_reqheight(), 112)
        cx, cy = width / 2, height * 0.50
        radius = self.compute_radius(width, height)
        active = self.is_expanded
        core_fill = "#d7ffff" if active else "#143b50"
        ring_color = "#58e5e3" if active else "#419dac"
        blue_color = "#78adff" if active else "#456c89"
        self.create_oval(cx-radius*1.65, cy-radius*1.65, cx+radius*1.65, cy+radius*1.65, fill="#0a1c2b", outline="")
        self.create_oval(cx-radius*1.27, cy-radius*1.27, cx+radius*1.27, cy+radius*1.27, fill="#10283b", outline="")
        for index, (rx_factor, ry_factor, angle, color) in enumerate(((1.9, .78, .08, ring_color), (1.45, 1.52, .88, blue_color), (1.55, 1.05, 1.7, "#c5a66b"))):
            rx, ry = radius * rx_factor, radius * ry_factor
            rotation = self.phase * (1.0 if index % 2 == 0 else -0.72) + angle
            points = []
            for step in range(65):
                theta = 2 * math.pi * step / 64
                x, y = rx * math.cos(theta), ry * math.sin(theta)
                points.extend((cx + x * math.cos(rotation) - y * math.sin(rotation), cy + x * math.sin(rotation) + y * math.cos(rotation)))
            self.create_line(*points, fill=color, width=1.4 if active else 1.0, smooth=True)
        self.create_oval(cx-radius, cy-radius, cx+radius, cy+radius, fill=core_fill, outline=ring_color, width=2 if active else 1)
        for scale, color in ((.55, "#6cbec7"), (.30, "#77aeca")):
            rr = radius * scale
            self.create_oval(cx-rr, cy-radius*.72, cx+rr, cy+radius*.72, outline=color, width=1)
        self.create_oval(cx-radius*.86, cy-radius*.3, cx+radius*.86, cy+radius*.3, outline="#70b9c1", width=1)
        for index in range(9):
            theta = 2 * math.pi * index / 9 + self.phase * (0.85 if active else 0.15)
            rr = radius * (1.85 if active else 1.5)
            x, y = cx + rr * math.cos(theta), cy + rr * .68 * math.sin(theta)
            dot = 3 if active and index % 3 == 0 else 2
            self.create_oval(x-dot, y-dot, x+dot, y+dot, fill="#41bec5" if index % 2 else "#d1a85f", outline="")
        self.create_text(cx, cy, text="CLARA-V", fill="#062b38" if active else "#d4f9ff", font=("Segoe UI", 8, "bold"), tags="label")


LOCAL_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".markdown"}
LOCAL_SCAN_MAX_ENTRIES = 20000
LOCAL_SCAN_MAX_RESULTS = 5000
LOCAL_SCAN_MAX_SECONDS = 20.0
PROTECTED_FOLDER_NAMES = {"windows", "program files", "program files (x86)", "appdata", "$recycle.bin", "system volume information", "onedrive", "dropbox", "google drive", "icloud drive", "iclouddrive"}
CLOUD_FOLDER_PREFIXES = ("onedrive", "dropbox", "google drive", "icloud")


def _is_protected_folder_name(name: str) -> bool:
    normalized = name.strip().casefold()
    return normalized in PROTECTED_FOLDER_NAMES or any(normalized.startswith(prefix + " ") for prefix in CLOUD_FOLDER_PREFIXES)


def _path_has_hidden_system_or_reparse(path: Path, stat_result=None) -> bool:
    """Conservatively skip hidden/system/reparse paths without following links."""
    if path.name.startswith("."):
        return True
    try:
        info = stat_result if stat_result is not None else path.stat(follow_symlinks=False)
    except OSError:
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    # Win32 FILE_ATTRIBUTE_HIDDEN, SYSTEM and REPARSE_POINT.
    if attributes & (0x2 | 0x4 | 0x400):
        return True
    if os.path.islink(path):
        return True
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction):
        try:
            if is_junction():
                return True
        except OSError:
            return True
    return False


def validate_local_search_root(path: str | Path, platform_name: str | None = None) -> Path:
    """Validate one user-selected, fixed local directory; never persist it."""
    candidate = Path(path).expanduser()
    platform_name = platform_name or sys.platform
    if not candidate.exists() or not candidate.is_dir():
        raise ValueError("La carpeta seleccionada no existe o no es una carpeta.")
    if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
        raise ValueError("Por seguridad, no se permiten enlaces simbólicos ni junctions como raíz.")
    # Check the lexical path as well as the resolved leaf: a normal-looking
    # subfolder beneath a hidden directory or junction must not bypass scope rules.
    lexical = Path(os.path.abspath(candidate))
    current = Path(lexical.anchor)
    for part in lexical.parts[1:]:
        current = current / part
        try:
            ancestor_info = current.stat(follow_symlinks=False)
        except OSError as exc:
            raise ValueError("No se pudo verificar la ruta completa de la carpeta seleccionada.") from exc
        if _path_has_hidden_system_or_reparse(current, ancestor_info):
            raise ValueError("No se permiten raíces dentro de carpetas ocultas, del sistema o enlazadas.")
    resolved = candidate.resolve(strict=True)
    if _path_has_hidden_system_or_reparse(resolved):
        raise ValueError("No se permiten carpetas ocultas, del sistema o de tipo enlace.")
    if any(_is_protected_folder_name(part) for part in resolved.parts):
        raise ValueError("No se permiten carpetas de Windows, perfiles de aplicación/sistema ni ubicaciones de nube conocidas.")
    profile_root = Path(os.environ.get("USERPROFILE", str(Path.home()))).expanduser()
    try:
        if resolved == profile_root.resolve(strict=True):
            raise ValueError("Selecciona una carpeta concreta dentro del perfil, no el perfil completo.")
    except OSError:
        pass
    if platform_name == "win32":
        raw_text = str(candidate)
        drive, _tail = os.path.splitdrive(raw_text)
        if raw_text.startswith("\\\\") or drive.startswith("\\\\"):
            raise ValueError("La primera versión solo permite carpetas en discos locales fijos, no rutas de red.")
        if not drive:
            raise ValueError("No pude determinar la unidad local de la carpeta seleccionada.")
        drive_root = drive + "\\"
        if os.path.normcase(str(resolved)) == os.path.normcase(drive_root):
            raise ValueError("Selecciona una carpeta concreta, no la raíz completa de una unidad.")
        try:
            drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive_root)
        except (AttributeError, OSError):
            raise ValueError("No pude verificar que la unidad sea local y fija.")
        if drive_type != 3:  # DRIVE_FIXED
            raise ValueError("La primera versión solo permite discos locales fijos; se excluyen red y unidades extraíbles.")
    return resolved


def prepare_local_move(
    source_root: str | Path, source_path: str | Path, destination_root: str | Path,
    expected_size: int, expected_mtime_ns: int, expected_file_id: tuple[int, int],
) -> dict[str, str | int | tuple[int, int]]:
    """Build a same-volume, no-overwrite move plan for one indexed document."""
    source_root_path = validate_local_search_root(source_root)
    destination_root_path = validate_local_search_root(destination_root)
    source = validate_local_document_for_open(source_root_path, source_path, expected_size, expected_mtime_ns, expected_file_id)
    if os.path.normcase(os.path.abspath(source.parent)) == os.path.normcase(os.path.abspath(destination_root_path)):
        raise ValueError("El documento ya está en esa carpeta; elige otro destino.")
    source_info = source.stat(follow_symlinks=False)
    destination_info = destination_root_path.stat(follow_symlinks=False)
    if source_info.st_dev != destination_info.st_dev:
        raise ValueError("Solo se permiten movimientos dentro del mismo volumen; no se copiará ni borrará entre discos.")
    source_drive, _ = os.path.splitdrive(str(source))
    destination_drive, _ = os.path.splitdrive(str(destination_root_path))
    if source_drive and destination_drive and os.path.normcase(source_drive) != os.path.normcase(destination_drive):
        raise ValueError("El origen y el destino deben estar en la misma unidad.")
    destination = destination_root_path / source.name
    if os.path.lexists(destination):
        raise FileExistsError("Ya existe un elemento con ese nombre en el destino. No se sobrescribió nada; elige otra carpeta.")
    return {
        "source_root": str(source_root_path), "source": str(source),
        "destination_root": str(destination_root_path), "destination": str(destination),
        "size": int(source_info.st_size), "mtime_ns": int(source_info.st_mtime_ns),
        "file_id": (int(source_info.st_dev), int(source_info.st_ino)),
    }


def execute_local_move(plan: dict, platform_name: str | None = None) -> Path:
    """Perform a single same-volume rename, refusing non-Windows and collisions."""
    platform_name = platform_name or sys.platform
    if platform_name != "win32":
        raise OSError("El movimiento está habilitado únicamente en Windows.")
    source_root = validate_local_search_root(plan["source_root"], platform_name)
    destination_root = validate_local_search_root(plan["destination_root"], platform_name)
    source = validate_local_document_for_open(source_root, plan["source"], plan["size"], plan["mtime_ns"], tuple(plan["file_id"]))
    destination = destination_root / source.name
    if os.path.normcase(os.path.abspath(destination)) != os.path.normcase(os.path.abspath(plan["destination"])):
        raise ValueError("El destino cambió desde la vista previa.")
    if source.stat(follow_symlinks=False).st_dev != destination_root.stat(follow_symlinks=False).st_dev:
        raise ValueError("El origen y destino ya no están en el mismo volumen.")
    if os.path.lexists(destination):
        raise FileExistsError("El destino ya existe; no se sobrescribió nada.")
    # os.rename is same-volume and fails rather than replacing an existing path on Windows.
    os.rename(source, destination)
    return destination


def _is_known_cloud_path(path: Path) -> bool:
    return any(any(part.casefold() == prefix or part.casefold().startswith(prefix + " ") for prefix in CLOUD_FOLDER_PREFIXES) for part in path.parts)


def is_windows_gui_executable(path: str | Path) -> bool:
    """Inspect a small PE header only; accept GUI-subsystem executables, not console scripts."""
    try:
        with Path(path).open("rb") as file:
            dos_header = file.read(64)
            if len(dos_header) < 64 or dos_header[:2] != b"MZ":
                return False
            pe_offset = struct.unpack_from("<I", dos_header, 0x3C)[0]
            if pe_offset > 1024 * 1024:
                return False
            file.seek(pe_offset)
            if file.read(4) != b"PE\0\0":
                return False
            coff = file.read(20)
            if len(coff) < 20:
                return False
            optional_size = struct.unpack_from("<H", coff, 16)[0]
            if optional_size < 70:
                return False
            optional = file.read(min(optional_size, 256))
            if len(optional) < 70:
                return False
            magic = struct.unpack_from("<H", optional, 0)[0]
            subsystem = struct.unpack_from("<H", optional, 68)[0]
            return magic in (0x10B, 0x20B) and subsystem == 2
    except (OSError, ValueError, struct.error):
        return False


def validate_local_application(path: str | Path, platform_name: str | None = None) -> dict:
    """Validate a directly selected GUI .exe under standard per-machine/user install roots."""
    platform_name = platform_name or sys.platform
    if platform_name != "win32":
        raise ValueError("El inicio de aplicaciones solo está habilitado en Windows.")
    candidate = Path(path).expanduser()
    if not candidate.is_absolute() or candidate.suffix.casefold() != ".exe":
        raise ValueError("Selecciona el archivo ejecutable .exe de una aplicación; no se admiten accesos directos ni scripts.")
    executable_name = candidate.name.casefold()
    executable_stem = candidate.stem.casefold()
    if executable_name in BLOCKED_APPLICATION_NAMES or any(token in executable_stem for token in ("setup", "installer", "uninstall", "updater", "update", "patch")):
        raise ValueError("Este nombre corresponde a un intérprete, instalador, actualizador o herramienta de sistema bloqueada.")
    if not candidate.exists() or not candidate.is_file() or candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
        raise ValueError("La aplicación seleccionada no es un archivo normal disponible.")
    resolved = candidate.resolve(strict=True)
    drive, _ = os.path.splitdrive(str(resolved))
    if not drive or str(resolved).startswith("\\\\"):
        raise ValueError("Solo se permiten aplicaciones en una unidad local fija.")
    try:
        drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive + "\\")
    except (AttributeError, OSError):
        raise ValueError("No pude verificar la unidad local de la aplicación.")
    if drive_type != 3:
        raise ValueError("No se permiten aplicaciones en unidades de red o extraíbles.")
    candidates = [
        os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
        os.environ.get("ProgramW6432"),
    ]
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        candidates.append(str(Path(local_appdata) / "Programs"))
    allowed_root = None
    for raw_root in candidates:
        if not raw_root:
            continue
        try:
            root = Path(raw_root).resolve(strict=True)
            if root.is_dir() and not _is_known_cloud_path(root):
                relative = resolved.relative_to(root)
                if relative.parts:
                    allowed_root = root
                    break
        except (OSError, ValueError):
            continue
    if allowed_root is None:
        raise ValueError("El .exe debe estar bajo Program Files o el directorio estándar LocalAppData\\Programs.")
    if _is_known_cloud_path(resolved):
        raise ValueError("No se permiten aplicaciones ubicadas en una carpeta de nube conocida.")
    current = allowed_root
    relative = resolved.relative_to(allowed_root)
    for part in relative.parts:
        current = current / part
        try:
            info_part = current.stat(follow_symlinks=False)
        except OSError as exc:
            raise ValueError("No pude comprobar una parte de la ruta de la aplicación.") from exc
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)() or getattr(info_part, "st_file_attributes", 0) & 0x400:
            raise ValueError("No se permiten symlinks o junctions en la ruta de una aplicación.")
    info = resolved.stat(follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x2:
        raise ValueError("La aplicación no es un ejecutable normal visible.")
    if not is_windows_gui_executable(resolved):
        raise ValueError("Solo se permiten ejecutables PE de interfaz gráfica; se rechazan scripts y utilidades de consola.")
    return {
        "name": resolved.name, "path": str(resolved), "size": int(info.st_size),
        "mtime_ns": int(info.st_mtime_ns), "file_id": (int(info.st_dev), int(info.st_ino)),
    }


def launch_allowed_application(record: dict, platform_name: str | None = None, popen=None):
    """Launch one unchanged allow-listed GUI application with no shell or arguments."""
    platform_name = platform_name or sys.platform
    if platform_name != "win32":
        raise OSError("El inicio de aplicaciones solo está habilitado en Windows.")
    current = validate_local_application(record["path"], platform_name)
    if any(current[key] != record.get(key) for key in ("path", "size", "mtime_ns")) or tuple(current["file_id"]) != tuple(record.get("file_id", ())):
        raise ValueError("La aplicación cambió desde que la autorizaste. Retírala y vuelve a añadirla si aún confías en ella.")
    start_process = popen or subprocess.Popen
    return start_process([current["path"]], shell=False, cwd=str(Path(current["path"]).parent), close_fds=True)


def scan_local_documents(
    root: str | Path, query: str = "", extension: str = "Todos", *, inventory: bool = False,
    recursive: bool = True, cancel_event: threading.Event | None = None,
    max_entries: int = LOCAL_SCAN_MAX_ENTRIES, max_results: int = LOCAL_SCAN_MAX_RESULTS,
    max_seconds: float = LOCAL_SCAN_MAX_SECONDS, progress_callback=None,
) -> dict:
    """List names/metadata only beneath a selected root; never open/read file contents."""
    root_path = validate_local_search_root(root)
    cancel_event = cancel_event or threading.Event()
    needle = query.strip().casefold()
    selected_ext = extension.casefold()
    if selected_ext != "todos" and selected_ext not in LOCAL_DOCUMENT_EXTENSIONS:
        raise ValueError("El filtro de tipo de archivo no está permitido.")
    started = time.monotonic()
    stack = [root_path]
    results: list[dict[str, str | int]] = []
    visited = 0
    inaccessible = 0
    status = "complete"
    while stack:
        if cancel_event.is_set():
            status = "cancelled"
            break
        if time.monotonic() - started >= max_seconds:
            status = "time_limit"
            break
        folder = stack.pop()
        try:
            with os.scandir(folder) as iterator:
                for entry in iterator:
                    if cancel_event.is_set():
                        status = "cancelled"
                        break
                    if time.monotonic() - started >= max_seconds:
                        status = "time_limit"
                        break
                    if visited >= max_entries:
                        status = "entry_limit"
                        break
                    visited += 1
                    if progress_callback and visited % 250 == 0:
                        progress_callback(visited, len(results))
                    path = Path(entry.path)
                    try:
                        info = entry.stat(follow_symlinks=False)
                        if _path_has_hidden_system_or_reparse(path, info):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if _is_protected_folder_name(entry.name):
                                continue
                            if inventory:
                                results.append({
                                    "name": entry.name, "kind": "Carpeta", "extension": "",
                                    "size": "", "modified": datetime.fromtimestamp(info.st_mtime).strftime("%d/%m/%Y %H:%M"),
                                    "relative": str(path.relative_to(root_path)), "path": str(path),
                                })
                                if len(results) >= max_results:
                                    status = "result_limit"
                                    break
                            if recursive:
                                stack.append(path)
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        suffix = path.suffix.casefold()
                        if suffix not in LOCAL_DOCUMENT_EXTENSIONS:
                            continue
                        if selected_ext != "todos" and suffix != selected_ext:
                            continue
                        if not inventory and needle not in entry.name.casefold():
                            continue
                        # On Windows, DirEntry.stat(follow_symlinks=False) may report st_dev/st_ino as zero.
                        # Path.stat performs a fresh OS stat and supplies the file identity used by later revalidation.
                        file_info = path.stat(follow_symlinks=False)
                        if _path_has_hidden_system_or_reparse(path, file_info) or not stat.S_ISREG(file_info.st_mode):
                            continue
                        results.append({
                            "name": entry.name, "kind": suffix.upper().lstrip("."), "extension": suffix,
                            "size": int(file_info.st_size), "modified": datetime.fromtimestamp(file_info.st_mtime).strftime("%d/%m/%Y %H:%M"),
                            "mtime_ns": int(file_info.st_mtime_ns), "file_id": (int(file_info.st_dev), int(file_info.st_ino)),
                            "relative": str(path.relative_to(root_path)), "path": str(path),
                        })
                        if len(results) >= max_results:
                            status = "result_limit"
                            break
                    except (OSError, PermissionError):
                        inaccessible += 1
                        continue
                if status != "complete":
                    break
        except (OSError, PermissionError):
            inaccessible += 1
    if progress_callback:
        progress_callback(visited, len(results))
    results.sort(key=lambda item: (str(item["relative"]).casefold(), str(item["kind"])))
    return {"status": status, "results": results, "visited": visited, "inaccessible": inaccessible}


def validate_local_document_for_open(
    root: str | Path, path: str | Path, expected_size: int, expected_mtime_ns: int,
    expected_file_id: tuple[int, int] | None = None,
) -> Path:
    """Revalidate a selected search result before a separately confirmed OS open."""
    root_path = validate_local_search_root(root)
    candidate = Path(path)
    lexical = Path(os.path.abspath(candidate))
    try:
        lexical_relative = lexical.relative_to(root_path)
    except ValueError as exc:
        raise ValueError("El archivo ya no está dentro de la carpeta que elegiste.") from exc
    if candidate.is_symlink() or getattr(candidate, "is_junction", lambda: False)():
        raise ValueError("El archivo seleccionado ahora es un enlace; no se abrirá.")
    current = root_path
    for part in lexical_relative.parts[:-1]:
        current = current / part
        if _is_protected_folder_name(part) or _path_has_hidden_system_or_reparse(current):
            raise ValueError("La ruta contiene una carpeta oculta, de sistema, de nube conocida o un enlace.")
    resolved = candidate.resolve(strict=True)
    try:
        relative = resolved.relative_to(root_path)
    except ValueError as exc:
        raise ValueError("El archivo ya no está dentro de la carpeta que elegiste.") from exc
    if resolved.suffix.casefold() not in LOCAL_DOCUMENT_EXTENSIONS:
        raise ValueError("El tipo de archivo no está permitido para apertura.")
    info = resolved.stat(follow_symlinks=False)
    if _path_has_hidden_system_or_reparse(resolved, info) or not stat.S_ISREG(info.st_mode):
        raise ValueError("El elemento ya no es un archivo normal permitido.")
    current_file_id = (int(info.st_dev), int(info.st_ino))
    expected_identity = tuple(expected_file_id) if expected_file_id is not None else None
    # Some Windows DirEntry.stat results contain (st_dev, st_ino) == (0, 0), which is not a usable identity.
    identity_changed = bool(expected_identity and expected_identity != (0, 0) and current_file_id != (0, 0) and current_file_id != expected_identity)
    if (
        int(info.st_size) != int(expected_size)
        or int(info.st_mtime_ns) != int(expected_mtime_ns)
        or identity_changed
    ):
        raise ValueError("El archivo cambió desde la búsqueda. Vuelve a buscar y revisa sus datos antes de abrirlo.")
    return resolved


CHAT_FILE_EXTENSIONS = {"Todos", ".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".markdown"}
CHAT_INTENT_FIELDS = {
    "general": {"intent", "response"},
    "clarify": {"intent", "question"},
    "task_draft": {"intent", "title", "subject", "due_date", "due_time", "description"},
    "block_draft": {"intent", "title", "block_date", "start_time", "end_time", "notes"},
    "class_draft": {"intent", "name", "weekday", "start_time", "end_time", "location"},
    "agenda_query": {"intent", "date"},
    "afternoon_plan": {"intent"},
    "next_commitment": {"intent"},
    "morning_brief": {"intent"},
    "news_query": {"intent", "topic"},
    "weather_query": {"intent"},
    "classes_query": {"intent"},
    "routines_query": {"intent"},
    "help": {"intent"},
    "file_search": {"intent", "query", "extension"},
    "file_inventory": {"intent", "recursive"},
    "file_open": {"intent", "query", "extension"},
    "file_move": {"intent", "query", "extension"},
}


def _chat_text(value, *, required=False, limit=2000):
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise ValueError("Tipo de texto inválido.")
    result = value.strip()
    if required and not result:
        raise ValueError("Falta texto requerido.")
    if len(result) > limit:
        raise ValueError("Texto excede el límite.")
    return result or None


def _chat_iso_date(value, *, required=False):
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise ValueError("Fecha no textual.")
    parsed = datetime.strptime(value, "%Y-%m-%d").date()
    if parsed.isoformat() != value:
        raise ValueError("Fecha no ISO.")
    return value


def _chat_time(value, *, required=False):
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise ValueError("Hora no textual.")
    parsed = datetime.strptime(value, "%H:%M").time()
    if parsed.strftime("%H:%M") != value:
        raise ValueError("Hora no HH:MM.")
    return value


def validate_chat_intent(raw: str) -> dict | None:
    """Strictly validate Ollama's JSON proposal; it never executes actions."""
    try:
        cleaned = re.sub(r"^\s*<think>.*?</think>\s*", "", str(raw or ""), flags=re.DOTALL).strip()
        payload = json.loads(cleaned)
        if not isinstance(payload, dict):
            return None
        intent = payload.get("intent")
        expected = CHAT_INTENT_FIELDS.get(intent)
        if intent == "classes_query" and set(payload) in ({"intent"}, {"intent", "date"}):
            expected = set(payload)
        if expected is None or set(payload) != expected:
            return None
        result = {"intent": intent}
        if intent == "general":
            result["response"] = _chat_text(payload["response"], required=True, limit=8000)
        elif intent == "clarify":
            result["question"] = _chat_text(payload["question"], required=True, limit=1000)
        elif intent == "task_draft":
            result.update({
                "title": _chat_text(payload["title"], limit=200) or "Tarea nueva",
                "subject": _chat_text(payload["subject"], limit=100),
                "due_date": _chat_iso_date(payload["due_date"]),
                "due_time": _chat_time(payload["due_time"]),
                "description": _chat_text(payload["description"], limit=600),
            })
            if result["due_time"] and not result["due_date"]:
                return None
        elif intent == "block_draft":
            result.update({
                "title": _chat_text(payload["title"], required=True, limit=200),
                "block_date": _chat_iso_date(payload["block_date"], required=True),
                "start_time": _chat_time(payload["start_time"], required=True),
                "end_time": _chat_time(payload["end_time"], required=True),
                "notes": _chat_text(payload["notes"], limit=600),
            })
            if result["end_time"] <= result["start_time"]:
                return None
        elif intent == "class_draft":
            weekday_val = payload.get("weekday")
            if isinstance(weekday_val, bool) or not isinstance(weekday_val, int) or not (0 <= weekday_val <= 6):
                return None
            start_t = _chat_time(payload["start_time"], required=True)
            end_t = _chat_time(payload.get("end_time"), required=False)
            if end_t and end_t <= start_t:
                return None
            result.update({
                "name": _chat_text(payload["name"], required=True, limit=140),
                "weekday": weekday_val,
                "start_time": start_t,
                "end_time": end_t,
                "location": _chat_text(payload.get("location"), required=False, limit=120),
            })
        elif intent == "agenda_query":
            result["date"] = _chat_iso_date(payload["date"], required=True)
        elif intent == "classes_query":
            result["date"] = _chat_iso_date(payload.get("date"), required=False)
        elif intent == "news_query":
            topic = payload.get("topic")
            if topic is not None and topic not in NEWS_TOPICS:
                return None
            result["topic"] = topic
        elif intent == "file_inventory":
            if not isinstance(payload["recursive"], bool):
                return None
            result["recursive"] = payload["recursive"]
        elif intent in ("file_search", "file_open", "file_move"):
            query = _chat_text(payload["query"], required=True, limit=120)
            # Never accept a filesystem path or traversal token from the model, even as a purported search term.
            if any(mark in query for mark in ("/", "\\")) or ".." in query or re.match(r"^[A-Za-z]:", query):
                return None
            extension = payload["extension"]
            if extension not in CHAT_FILE_EXTENSIONS:
                return None
            result.update({"query": query, "extension": extension})
        return result
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None


def normalize_intent_text(text: str) -> str:
    """Normalize Spanish user text (accent-insensitive, punctuation-trimmed) for local NLU routing."""
    raw = str(text or "").strip().casefold()
    raw = raw.translate(str.maketrans("áéíóúüñ", "aeiouun"))
    raw = re.sub(r"[¿?¡!]", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()


def is_negated_or_informational_query(text: str) -> bool:
    """Detect negated commands ('no busques...') or 'how-to' questions ('¿cómo se mueve...?') so they never trigger actions."""
    low = normalize_intent_text(text)
    if not low:
        return False
    negation_patterns = (
        r"^(?:por favor\s+)?(?:no|nunca|jamas|tampoco)\s+(?:busques|buscar|abras|abrir|muevas|mover|agregues|agregar|anadas|anadir|crees|crear|inventaries|inventariar|ejecutes|ejecutar|borres|borrar|elimines|eliminar|guardes|guardar)\b",
        r"\bno\s+quiero\s+que\s+(?:busques|abras|muevas|agregues|crees|ejecutes|guardes)\b",
    )
    if any(re.search(pat, low) for pat in negation_patterns):
        return True
    informational_patterns = (
        r"^(?:como|de que manera|explicame como)\s+(?:se\s+)?(?:busca|busco|buscar|abre|abro|abrir|mueve|muevo|mover|inventaria|inventariar|agrega|agregar|programa|programar|funciona)\b",
        r"^(?:que\s+formatos\s+permites|cuales\s+son\s+los\s+limites)\b",
    )
    return any(re.search(pat, low) for pat in informational_patterns)


def is_blocked_unsafe_request(text: str) -> str | None:
    """Refuse requests to execute commands, scripts, installers, system power actions, or arbitrary downloads."""
    low = normalize_intent_text(text)
    if not low:
        return None
    if re.search(r"\b(?:ejecuta|ejecutar|corre|correr|abre|abrir|lanza|lanzar)\b.*\b(?:cmd|powershell|pwsh|terminal|bash|wsl|regedit|mshta|rundll32|wscript|cscript|script|\.ps1|\.bat|\.cmd|\.vbs|\.sh)\b", low):
        return (
            "Por seguridad, Clara no ejecuta comandos de consola (cmd/PowerShell), scripts (.ps1, .bat, .py) ni código recibido del chat. "
            "Solo puedes iniciar hasta 10 aplicaciones gráficas (.exe) previamente autorizadas desde “Aplicaciones autorizadas”, con confirmación en cada inicio."
        )
    if re.search(r"\b(?:apaga|apagar|reinicia|reiniciar|suspende|suspender|bloquea|bloquear)\s+(?:la\s+|el\s+|mi\s+)?(?:pc|computadora|equipo|sistema|windows)\b", low):
        return "Clara no ejecuta apagados, reinicios ni bloqueos del sistema operativo."
    if re.search(r"\b(?:instala|instalar|descarga\s+e\s+instala|ejecuta\s+instalador|setup\.exe|installer\.exe|msiexec|winget)\b", low):
        if not re.search(r"\b(?:modelo|llama\s*3|qwen|mistral|gemma|vosk)\b", low):
            return (
                "Clara no realiza descargas ni instalaciones automáticas o silenciosas. "
                "Cualquier complemento opcional muestra primero su fuente oficial, recurso, versión, tamaño y licencia, y requiere tu acción manual."
            )
    return None


def build_next_commitment_summary(db: sqlite3.Connection, now: datetime | None = None) -> str:
    """Compute the next upcoming class, local block, or timed task for today (inspired by Viernes's '¿Qué sigue?')."""
    current = now or datetime.now()
    today = current.date()
    now_hm = current.strftime("%H:%M")
    closure = day_off_for(db, today)
    in_progress: list[tuple[str, str, str]] = []
    upcoming: list[tuple[str, str, str]] = []

    for meeting in classes_for_date(db, today):
        start_str = str(meeting["start_time"] or "")
        end_val = str(meeting.get("end_time") or "")
        end_str = f"–{end_val}" if end_val else ""
        place = f" ({meeting['location']})" if meeting.get("location") else ""
        if start_str and start_str >= now_hm:
            upcoming.append((start_str, "Clase", f"{meeting['name']} a las {start_str}{end_str}{place}"))
        elif start_str and end_val and start_str < now_hm < end_val:
            in_progress.append((start_str, "Clase", f"{meeting['name']} ({start_str}–{end_val}){place}"))

    for block in db.execute(
        "SELECT title,start_time,end_time FROM plan_blocks WHERE block_date=? ORDER BY start_time",
        (today.isoformat(),),
    ):
        if block["start_time"] >= now_hm:
            upcoming.append(
                (block["start_time"], "Bloque local", f"{block['title']} ({block['start_time']}–{block['end_time']})")
            )
        elif block["start_time"] < now_hm < block["end_time"]:
            in_progress.append(
                (block["start_time"], "Bloque local", f"{block['title']} ({block['start_time']}–{block['end_time']})")
            )

    for task in db.execute(
        "SELECT title,subject,due_date,due_time,priority FROM tasks WHERE done=0 AND due_date=? AND due_time IS NOT NULL ORDER BY due_time",
        (today.isoformat(),),
    ):
        if task["due_time"] >= now_hm:
            subj = f" [{task['subject']}]" if task["subject"] else ""
            upcoming.append(
                (task["due_time"], "Tarea con hora", f"{task['title']}{subj} a las {task['due_time']} (prioridad {task['priority']})")
            )

    upcoming.sort(key=lambda item: item[0])
    unscheduled_today = db.execute(
        "SELECT title,subject,priority FROM tasks WHERE done=0 AND (due_date IS NULL OR due_date<=?) AND (due_date<>? OR due_time IS NULL) ORDER BY CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date LIMIT 5",
        (today.isoformat(), today.isoformat()),
    ).fetchall()

    lines: list[str] = []
    if closure:
        lines.append("Hoy figura como día sin clases" + (f" ({closure['note']})." if closure["note"] else "."))
    if in_progress:
        for _t, kind, desc in in_progress:
            lines.append(f"En curso ahora: {kind} · {desc}.")
    if upcoming:
        next_time, next_kind, next_desc = upcoming[0]
        target_dt = datetime.combine(today, datetime.strptime(next_time, "%H:%M").time())
        mins = max(0, int((target_dt - current).total_seconds() // 60))
        if mins == 0:
            eta = "comienza ahora mismo"
        elif mins < 60:
            eta = f"en {mins} min"
        else:
            hours, rem = divmod(mins, 60)
            eta = f"en {hours} h {rem} min" if rem else f"en {hours} h"
        lines.append(f"Lo que sigue hoy ({eta}): {next_kind} · {next_desc}.")
        if len(upcoming) > 1:
            lines.append("Más adelante hoy:")
            for _t, kind, desc in upcoming[1:4]:
                lines.append(f"• {kind}: {desc}")
    else:
        lines.append("Ya no quedan clases, bloques ni tareas con hora posterior para hoy.")

    if unscheduled_today:
        lines.append("Tareas pendientes sin hora futura hoy:")
        for row in unscheduled_today[:4]:
            subj = f" [{row['subject']}]" if row["subject"] else ""
            lines.append(f"• {row['title']}{subj} (prioridad {row['priority']})")
    return "\n".join(lines)


def build_classes_summary(db: sqlite3.Connection, target_day: date | None = None) -> str:
    """Summarize classes for a specific date or the full weekly schedule."""
    days = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    if target_day is not None:
        closure = day_off_for(db, target_day)
        meetings = classes_for_date(db, target_day)
        header = f"Clases para {days[target_day.weekday()]} {target_day.strftime('%d/%m/%Y')}:"
        if closure and not meetings:
            return f"{header}\n• Día sin clases" + (f" ({closure['note']})" if closure["note"] else "")
        if not meetings:
            return f"{header}\n• No tienes clases registradas para ese día."
        lines = [header]
        for row in meetings:
            slot = f"{row['start_time']}" + (f"–{row['end_time']}" if row.get("end_time") else "")
            place = f" · {row['location']}" if row.get("location") else ""
            lines.append(f"• {slot} — {row['name']}{place}")
        return "\n".join(lines)

    rows = db.execute("SELECT name,weekday,start_time,end_time,location FROM classes ORDER BY weekday,start_time,name").fetchall()
    if not rows:
        return "Aún no tienes clases registradas en tu horario semanal. Puedes agregarlas desde “📚 Mis clases · agregar / editar”."
    lines = ["Tu horario semanal de clases:"]
    for row in rows:
        slot = f"{row['start_time']}" + (f"–{row['end_time']}" if row["end_time"] else "")
        place = f" ({row['location']})" if row["location"] else ""
        lines.append(f"• {days[int(row['weekday'])]} {slot}: {row['name']}{place}")
    return "\n".join(lines)


def build_routines_summary(db: sqlite3.Connection) -> str:
    """Summarize configured manual routines without inferring or modifying anything."""
    day_names = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
    rows = db.execute("SELECT title,subject,weekdays,reminder_time,active FROM routines ORDER BY title").fetchall()
    if not rows:
        return "No tienes rutinas recurrentes configuradas. Puedes crearlas manualmente desde el botón “Rutinas” (Clara nunca infiere ni duplica rutinas automáticamente)."
    lines = ["Tus rutinas configuradas manualmente:"]
    for row in rows:
        days = ", ".join(day_names[int(d)] for d in str(row["weekdays"]).split(",") if d.isdigit() and 0 <= int(d) < 7)
        state = "Activa" if row["active"] else "Pausada"
        subj = f" [{row['subject']}]" if row["subject"] else ""
        rem = f" · aviso {row['reminder_time']}" if row["reminder_time"] else ""
        lines.append(f"• {row['title']}{subj} ({days}{rem}) — {state}")
    return "\n".join(lines)


def build_help_summary() -> str:
    """Explain Clara Unificada's local-first capabilities and safety boundaries."""
    return (
        "Soy CLARA-V (Clara Viernes · Edición Unificada local-first). Esto puedo hacer directamente por ti:\n"
        "• Agenda y día operativo: pregúntame “¿qué tengo hoy?”, “¿qué tengo mañana?”, “¿qué sigue?”, “agenda semanal”, “mis clases” o “mis rutinas”.\n"
        "• Clases, tareas, bloques y rutinas por chat: dime “agrega mi clase de Cálculo los lunes y miércoles de 08:00 a 10:00 en Aula 4”, “agrega tarea de Biología entregar reporte mañana a las 16:00”, “marca como hecha la tarea entregar reporte”, “reserva de 17:00 a 18:00 hoy para estudiar” o “agrega rutina repasar inglés lunes y miércoles a las 19:00”.\n"
        "• Niveles de seguridad y bóveda encriptada: autentícate escribiendo o hablando tu usuario y contraseña (ej. “Luis ju89yt56rf”), guarda o consulta contraseñas encriptadas (“guardar secreto Correo: mi_clave”, “ver secretos encriptados”) y bloquea tu sesión en modo invitado (“bloquear sesión”).\n"
        "• Conversación general con Ollama: respondo preguntas abiertas en tiempo real usando tu modelo local de Ollama (o te aviso claramente cuando opero en modo local esencial si Ollama no está activo).\n"
        "• Noticias, clima y voz segura: dime “noticias”, “clima”, usa “🎙 Pulsar para hablar”, “🔊 Repetir última respuesta” y “🩺 Diagnóstico de voz”.\n"
        "• Documentos y apps con límites estrictos: busca por nombre/tipo (PDF, DOCX, XLSX, PPTX, TXT, Markdown) eligiendo carpeta cada vez, abre o mueve 1 archivo con confirmación individual y gestiona hasta 10 aplicaciones GUI autorizadas."
    )


def _normalize_hour_token(hour_str: str, minute_str: str | None = None) -> str | None:
    try:
        h = int(hour_str)
        m = int(minute_str) if minute_str else 0
        if not (0 <= h <= 23 and 0 <= m <= 59):
            return None
        return f"{h:02d}:{m:02d}"
    except ValueError:
        return None


_CLASS_LOCATION_NOUN_PATTERN = (
    r"(?:aula|sal[oó]n|salon|laboratorio|lab|auditorio|taller|edificio|cub[ií]culo|sala|"
    r"centro(?:\s+de\s+c[oó]mputo)?|cancha|gimnasio|biblioteca|anfiteatro|foro|campus|"
    r"zoom|teams|meet|l[ií]nea|linea|virtual)"
)


def repair_legacy_class_locations(db: sqlite3.Connection) -> int:
    """Split any class name that accidentally absorbed trailing 'en <Lugar>' (e.g. 'en Auditorio 2') into name + location."""
    try:
        rows = db.execute(
            "SELECT id, name, weekday, start_time, end_time, location FROM classes WHERE location IS NULL OR TRIM(location)=''"
        ).fetchall()
    except sqlite3.Error:
        return 0
    repaired = 0
    tail_re = re.compile(
        rf"^(?P<cname>.+?)\s+(?:en\s+el\s+|en\s+la\s+|en\s+)(?P<loc>{_CLASS_LOCATION_NOUN_PATTERN}(?:\s+[A-Za-z0-9ÁÉÍÓÚáéíóúñÑ._-]+){{0,3}})\s*$",
        flags=re.IGNORECASE,
    )
    for row in rows:
        raw_name = str(row["name"] or "").strip()
        m = tail_re.match(raw_name)
        if not m:
            continue
        clean_name = m.group("cname").strip(" ,.;:-")
        extracted_loc = m.group("loc").strip(" ,.;:-")
        if not clean_name or not extracted_loc:
            continue
        dup = db.execute(
            "SELECT id FROM classes WHERE id<>? AND LOWER(TRIM(name))=LOWER(TRIM(?)) AND weekday=? AND start_time=? LIMIT 1",
            (int(row["id"]), clean_name, int(row["weekday"]), str(row["start_time"])),
        ).fetchone()
        if dup:
            db.execute(
                "UPDATE classes SET location=COALESCE(NULLIF(TRIM(location),''), ?), end_time=COALESCE(end_time, ?) WHERE id=?",
                (extracted_loc, row["end_time"], int(dup["id"])),
            )
            db.execute("DELETE FROM classes WHERE id=?", (int(row["id"]),))
        else:
            db.execute(
                "UPDATE classes SET name=?, location=? WHERE id=?",
                (clean_name, extracted_loc, int(row["id"])),
            )
        repaired += 1
    if repaired:
        db.commit()
    return repaired


def parse_class_proposal(text: str) -> dict | None:
    """Extract class name, weekday(s), start_time, optional end_time, and optional location from natural Spanish."""
    raw = str(text or "").strip()
    if not raw:
        return None
    low = normalize_intent_text(raw)
    weekday_map = {
        "lunes": 0,
        "martes": 1,
        "miercoles": 2,
        "jueves": 3,
        "viernes": 4,
        "sabado": 5,
        "domingo": 6,
    }
    weekdays: list[int] = []
    if re.search(r"\blunes\s+a\s+viernes\b|\btodos\s+los\s+dias\b|\bdiario\b", low):
        weekdays = [0, 1, 2, 3, 4]
    elif re.search(r"\blunes\s+a\s+jueves\b", low):
        weekdays = [0, 1, 2, 3]
    else:
        for day_word, idx in weekday_map.items():
            if re.search(r"\b" + day_word + r"\b", low) and idx not in weekdays:
                weekdays.append(idx)

    start_time: str | None = None
    end_time: str | None = None
    single_time_match = None
    time_span_match = re.search(
        r"\b(?:de\s+(?:las\s+)?)?(\d{1,2})(?::(\d{2}))?\s*(?:a(?:\s+las)?|-|–|hasta(?:\s+las)?)\s*(\d{1,2})(?::(\d{2}))?\b",
        raw,
        re.IGNORECASE,
    )
    if time_span_match:
        h1, m1, h2, m2 = time_span_match.groups()
        start_time = _normalize_hour_token(h1, m1)
        end_time = _normalize_hour_token(h2, m2)
        if start_time and end_time and end_time <= start_time:
            try:
                eh = int(h2)
                if 1 <= eh <= 9 and int(h1) >= 7:
                    end_time = _normalize_hour_token(str(eh + 12), m2)
            except ValueError:
                pass
    else:
        single_time_match = re.search(r"\b(?:a\s+las\s+)(\d{1,2})(?::(\d{2}))?\b|\b(\d{1,2}):(\d{2})\b", raw, re.IGNORECASE)
        if single_time_match:
            h_s = single_time_match.group(1) or single_time_match.group(3)
            m_s = single_time_match.group(2) or single_time_match.group(4)
            start_time = _normalize_hour_token(h_s, m_s)

    location: str | None = None
    loc_match = re.search(
        rf"\b(?:en\s+el\s+|en\s+la\s+|en\s+)?({_CLASS_LOCATION_NOUN_PATTERN}(?:\s+[A-Za-z0-9ÁÉÍÓÚáéíóúñÑ._-]+){{0,3}})",
        raw,
        re.IGNORECASE,
    )
    if loc_match:
        location = loc_match.group(1).strip(" .,;:")
    else:
        # Also detect any trailing "en <Lugar>" placed after the time expression (e.g. "... de 13:00 a 15:00 en C-104")
        active_time_match = time_span_match or single_time_match
        if active_time_match is not None:
            after_time = raw[active_time_match.end():]
            trailing_loc = re.search(
                r"^\s*(?:en\s+el\s+|en\s+la\s+|en\s+)([A-Za-z0-9ÁÉÍÓÚáéíóúñÑ][A-Za-z0-9ÁÉÍÓÚáéíóúñÑ\s._-]{0,40}?)\s*[.,;:]*$",
                after_time,
                re.IGNORECASE,
            )
            if trailing_loc:
                location = trailing_loc.group(1).strip(" .,;:")

    candidate = raw
    if loc_match:
        candidate = candidate[:loc_match.start()] + " " + candidate[loc_match.end():]
    elif location and (time_span_match or single_time_match):
        active_time_match = time_span_match or single_time_match
        if active_time_match is not None:
            candidate = candidate[:active_time_match.end()]
    if time_span_match:
        candidate = candidate.replace(time_span_match.group(0), " ")
    elif single_time_match:
        candidate = candidate.replace(single_time_match.group(0), " ")

    # Strip any natural conversational intro up to "clase(s)/materia(s)/curso(s)/asignatura(s) de/llamada"
    if re.search(r"^.*?\b(?:clases?|materias?|cursos?|asignaturas?)\s+(?:de\s+|llamad[ao]\s+)", candidate, flags=re.IGNORECASE):
        candidate = re.sub(
            r"^.*?\b(?:clases?|materias?|cursos?|asignaturas?)\s+(?:de\s+|llamad[ao]\s+)",
            " ",
            candidate,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        candidate = re.sub(
            r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:clara(?:-v|\s+v)?[,.;:\s-]*)?"
            r"(?:(?:quiero|puedes)\s+)?(?:agrega(?:r)?|a[nñ]ad(?:e|ir)|registra(?:r)?|crea(?:r)?|anota(?:r)?|pon(?:er|me)?|guarda(?:r)?|apunta(?:r)?|incluir|incluye|mete(?:r)?|tengo|llevo)"
            r"(?:\s+que)?(?:\s+(?:tengo|llevo|curso|hay))?(?:\s+(?:mi|mis|una|un|la|el|las|los))?(?:\s+nueva)?\s*(?:clases?|materias?|cursos?|asignaturas?)?(?:\s+de|\s+llamad[ao])?\b",
            " ",
            candidate,
            count=1,
            flags=re.IGNORECASE,
        )

    # Remove weekday phrases (including preceding articles "los/el/las") without stripping "de/del/las/los" inside subject names like "Bases de Datos"
    day_token = r"(?:lunes|martes|mi[eé]rcoles|miercoles|jueves|viernes|s[aá]bado|sabado|domingo)"
    candidate = re.sub(
        rf"\b(?:(?:los|el|las)\s+)?(?:d[ií]as\s+)?(?:de\s+lunes\s+a\s+viernes|lunes\s+a\s+viernes|lunes\s+a\s+jueves|todos\s+los\s+d[ií]as|diario|(?:{day_token}(?:\s*(?:,|y|e)\s*|\s+(?:los|el)\s+|\s+)+)*{day_token})\b",
        " ",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(
        r"\b(?:en\s+horario|con\s+horario|a\s+las|de\s+las|por\s+la\s+ma[nñ]ana|por\s+la\s+tarde|por\s+la\s+noche)\b",
        " ",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(r"^\s*(?:es|son|de|la|el)\b\s*", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"\s+\b(?:es|son|en|en\s+el|en\s+la)\s*$", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"\s+", " ", candidate).strip(" :,-.;")
    if candidate.casefold() in ("", "clase", "clases", "mis clases", "una clase", "materia", "mi clase", "materias"):
        candidate = ""
    elif candidate and candidate[0].islower():
        candidate = candidate[0].upper() + candidate[1:]
    return {
        "name": candidate[:140] or None,
        "weekdays": weekdays,
        "start_time": start_time,
        "end_time": end_time if (start_time and end_time and end_time > start_time) else None,
        "location": location[:120] if location else None,
    }


def _time_to_minutes(hhmm: str | None) -> int | None:
    if not hhmm:
        return None
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", str(hhmm))
    if not m:
        return None
    h, mins = int(m.group(1)), int(m.group(2))
    if not (0 <= h <= 23 and 0 <= mins <= 59):
        return None
    return h * 60 + mins


def _minutes_to_time(total_mins: int) -> str:
    clamped = max(0, min(23 * 60 + 59, int(total_mins)))
    return f"{clamped // 60:02d}:{clamped % 60:02d}"


def detect_class_schedule_conflicts(
    db: sqlite3.Connection,
    weekdays: list[int],
    start_time: str | None,
    end_time: str | None = None,
    *,
    exclude_class_ids: set[int] | None = None,
    exclude_class_name: str | None = None,
) -> list[dict[str, object]]:
    """Detect time overlaps against existing weekly classes on the given weekday(s)."""
    start_min = _time_to_minutes(start_time)
    if start_min is None or not weekdays:
        return []
    end_min = _time_to_minutes(end_time)
    if end_min is None or end_min <= start_min:
        end_min = min(23 * 60 + 59, start_min + 60)
    days_labels = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    excluded_ids = {int(x) for x in (exclude_class_ids or set())}
    excl_name_norm = normalize_intent_text(exclude_class_name) if exclude_class_name else ""
    conflicts: list[dict[str, object]] = []
    for wd in sorted({int(d) for d in weekdays if 0 <= int(d) <= 6}):
        rows = db.execute(
            "SELECT id, name, weekday, start_time, end_time, location FROM classes WHERE weekday=? ORDER BY start_time, id",
            (wd,),
        ).fetchall()
        for row in rows:
            rid = int(row["id"])
            if rid in excluded_ids:
                continue
            rname = str(row["name"] or "").strip()
            if excl_name_norm and normalize_intent_text(rname) == excl_name_norm:
                continue
            other_start = _time_to_minutes(row["start_time"])
            if other_start is None:
                continue
            other_end = _time_to_minutes(row["end_time"])
            if other_end is None or other_end <= other_start:
                other_end = min(23 * 60 + 59, other_start + 60)
            ov_start = max(start_min, other_start)
            ov_end = min(end_min, other_end)
            if ov_start < ov_end:
                conflicts.append(
                    {
                        "id": rid,
                        "weekday": wd,
                        "day_label": days_labels[wd],
                        "name": rname,
                        "start_time": str(row["start_time"]),
                        "end_time": str(row["end_time"] or _minutes_to_time(other_end)),
                        "location": str(row["location"] or "").strip(),
                        "overlap_start": _minutes_to_time(ov_start),
                        "overlap_end": _minutes_to_time(ov_end),
                    }
                )
    return conflicts


def format_schedule_conflict_warning(conflicts: list[dict[str, object]]) -> str:
    """Build a friendly Spanish warning describing all detected class schedule overlaps."""
    if not conflicts:
        return ""
    parts: list[str] = []
    for item in conflicts:
        loc_part = f", {item['location']}" if item.get("location") else ""
        parts.append(
            f"{item['day_label']} de {item['overlap_start']} a {item['overlap_end']} con tu clase «{item['name']}» ({item['start_time']}–{item['end_time']}{loc_part})"
        )
    joined = "; ".join(parts)
    return (
        f"⚠️ Atención: se empalma el {joined}. "
        "¿Quieres cambiarla de hora o eliminar la anterior?"
    )


def detect_date_schedule_conflicts(
    db: sqlite3.Connection,
    target_date: date,
    start_time: str,
    end_time: str,
    *,
    exclude_block_id: int | None = None,
) -> list[str]:
    """Detect overlaps on a specific calendar date against effective classes and study blocks."""
    start_min = _time_to_minutes(start_time)
    end_min = _time_to_minutes(end_time)
    if start_min is None or end_min is None or end_min <= start_min:
        return []
    conflicts: list[str] = []
    for meeting in classes_for_date(db, target_date):
        m_start = _time_to_minutes(str(meeting.get("start_time") or ""))
        if m_start is None:
            continue
        m_end = _time_to_minutes(str(meeting.get("end_time") or ""))
        if m_end is None or m_end <= m_start:
            m_end = min(23 * 60 + 59, m_start + 60)
        ov_s = max(start_min, m_start)
        ov_e = min(end_min, m_end)
        if ov_s < ov_e:
            loc = f", {meeting['location']}" if meeting.get("location") else ""
            conflicts.append(
                f"de {_minutes_to_time(ov_s)} a {_minutes_to_time(ov_e)} con tu clase «{meeting['name']}» ({meeting['start_time']}–{meeting.get('end_time') or _minutes_to_time(m_end)}{loc})"
            )
    rows = db.execute(
        "SELECT id, title, start_time, end_time FROM plan_blocks WHERE block_date=? ORDER BY start_time",
        (target_date.isoformat(),),
    ).fetchall()
    for row in rows:
        if exclude_block_id is not None and int(row["id"]) == int(exclude_block_id):
            continue
        b_start = _time_to_minutes(row["start_time"])
        b_end = _time_to_minutes(row["end_time"])
        if b_start is None or b_end is None or b_end <= b_start:
            continue
        ov_s = max(start_min, b_start)
        ov_e = min(end_min, b_end)
        if ov_s < ov_e:
            conflicts.append(
                f"de {_minutes_to_time(ov_s)} a {_minutes_to_time(ov_e)} con tu bloque «{row['title']}» ({row['start_time']}–{row['end_time']})"
            )
    return conflicts


def audit_all_schedule_conflicts(db: sqlite3.Connection, ref_date: date | None = None) -> list[str]:
    """Audit the entire weekly class schedule and upcoming 7 days of study blocks for overlaps."""
    repair_legacy_class_locations(db)
    ref_date = ref_date or date.today()
    days_labels = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    issues: list[str] = []
    for wd in range(7):
        rows = db.execute(
            "SELECT id, name, start_time, end_time, location FROM classes WHERE weekday=? ORDER BY start_time, id",
            (wd,),
        ).fetchall()
        for i in range(len(rows)):
            s1 = _time_to_minutes(rows[i]["start_time"])
            if s1 is None:
                continue
            e1 = _time_to_minutes(rows[i]["end_time"])
            if e1 is None or e1 <= s1:
                e1 = min(23 * 60 + 59, s1 + 60)
            for j in range(i + 1, len(rows)):
                s2 = _time_to_minutes(rows[j]["start_time"])
                if s2 is None:
                    continue
                e2 = _time_to_minutes(rows[j]["end_time"])
                if e2 is None or e2 <= s2:
                    e2 = min(23 * 60 + 59, s2 + 60)
                ov_s = max(s1, s2)
                ov_e = min(e1, e2)
                if ov_s < ov_e:
                    loc1 = f" ({rows[i]['location']})" if rows[i]["location"] else ""
                    loc2 = f" ({rows[j]['location']})" if rows[j]["location"] else ""
                    issues.append(
                        f"{days_labels[wd]} {_minutes_to_time(ov_s)}–{_minutes_to_time(ov_e)}: «{rows[i]['name']}»{loc1} se empalma con «{rows[j]['name']}»{loc2}"
                    )
    for offset in range(7):
        d = ref_date + timedelta(days=offset)
        blocks = db.execute(
            "SELECT id, title, start_time, end_time FROM plan_blocks WHERE block_date=? ORDER BY start_time",
            (d.isoformat(),),
        ).fetchall()
        for b in blocks:
            b_conflicts = detect_date_schedule_conflicts(
                db, d, str(b["start_time"]), str(b["end_time"]), exclude_block_id=int(b["id"])
            )
            for desc in b_conflicts:
                entry = f"{days_labels[d.weekday()]} {d.isoformat()}: el bloque «{b['title']}» ({b['start_time']}–{b['end_time']}) se empalma {desc}"
                if entry not in issues:
                    issues.append(entry)
    return issues


def build_schedule_conflicts_report(db: sqlite3.Connection, ref_date: date | None = None) -> str:
    """Return a user-facing summary of any schedule overlaps across weekly classes and study blocks."""
    issues = audit_all_schedule_conflicts(db, ref_date=ref_date)
    if not issues:
        return "✅ Revisé tu horario semanal de clases y tus bloques de estudio: no tienes ningún choque ni empalme de horario."
    return (
        "⚠️ Detecté los siguientes choques de horario (empalmes) en tu agenda:\n"
        + "\n".join(f"• {item}" for item in issues)
        + "\n¿Quieres que cambie alguna clase o bloque de hora?"
    )


def execute_add_class_from_chat(db: sqlite3.Connection, proposal: dict) -> tuple[bool, str]:
    """Save a class directly into SQLite (avoiding duplicates) when name, weekday(s), and start_time are provided."""
    repair_legacy_class_locations(db)
    days_labels = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    name = str(proposal.get("name") or "").strip()
    weekdays = proposal.get("weekdays")
    if weekdays is None and proposal.get("weekday") is not None:
        weekdays = [int(proposal["weekday"])]
    weekdays = [int(d) for d in (weekdays or []) if isinstance(d, int) and 0 <= int(d) <= 6]
    start_time = str(proposal.get("start_time") or "").strip() or None
    end_time = str(proposal.get("end_time") or "").strip() or None
    location = str(proposal.get("location") or "").strip() or None

    if not name or not weekdays or not start_time:
        missing = []
        if not name:
            missing.append("nombre de la materia")
        if not weekdays:
            missing.append("día de la semana (ej. lunes, martes…)")
        if not start_time:
            missing.append("hora de inicio (ej. 08:00)")
        return (
            False,
            f"Para guardar tu clase directamente necesito {', '.join(missing)}. "
            "Puedes decírmelo así: «agrega clase de Cálculo los lunes y miércoles de 08:00 a 10:00 en Aula 4», "
            "o usar la ventana de Mis clases que acabo de abrirte.",
        )

    conflicts = detect_class_schedule_conflicts(
        db,
        weekdays,
        start_time,
        end_time,
        exclude_class_name=name,
    )

    saved_days: list[str] = []
    for wd in weekdays:
        existing = db.execute(
            "SELECT id FROM classes WHERE LOWER(TRIM(name))=LOWER(TRIM(?)) AND weekday=? AND start_time=? LIMIT 1",
            (name, wd, start_time),
        ).fetchone()
        if existing:
            db.execute(
                "UPDATE classes SET end_time=COALESCE(?, end_time), location=COALESCE(?, location), reminded_on=NULL WHERE id=?",
                (end_time, location, existing["id"]),
            )
        else:
            db.execute(
                "INSERT INTO classes(name, weekday, start_time, end_time, location) VALUES(?,?,?,?,?)",
                (name, wd, start_time, end_time, location),
            )
        saved_days.append(days_labels[wd])
    db.commit()
    slot = start_time + (f"–{end_time}" if end_time else "")
    loc_text = f" ({location})" if location else ""
    base_msg = f"¡Listo! Guardé tu clase «{name}» para {', '.join(saved_days)} en horario {slot}{loc_text}."
    warning_msg = format_schedule_conflict_warning(conflicts)
    if warning_msg:
        base_msg = f"{base_msg}\n{warning_msg}"
    return (True, base_msg)


def execute_edit_class_from_chat(db: sqlite3.Connection, raw_text: str) -> tuple[bool, str]:
    """Modify an existing class's location, schedule time, or weekday(s) from natural Spanish without duplicating rows."""
    repair_legacy_class_locations(db)
    raw = str(raw_text or "").strip()
    low = normalize_intent_text(raw)
    days_labels = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    weekday_map = {
        "lunes": 0,
        "martes": 1,
        "miercoles": 2,
        "jueves": 3,
        "viernes": 4,
        "sabado": 5,
        "domingo": 6,
    }

    all_classes = db.execute("SELECT id, name, weekday, start_time, end_time, location FROM classes ORDER BY id").fetchall()
    if not all_classes:
        return (False, "Aún no tienes clases registradas en tu horario semanal para editar.")

    # 1. Identify which existing class subject the user is referring to
    distinct_names = sorted({str(r["name"]).strip() for r in all_classes if r["name"]}, key=len, reverse=True)
    matched_name: str | None = None
    for cname in distinct_names:
        cname_norm = normalize_intent_text(cname)
        if cname_norm and cname_norm in low:
            matched_name = cname
            break

    if not matched_name:
        # Try extracting candidate subject name after "clase de" / "materia de" / "salón de" / "horario de"
        m_sub = re.search(
            r"\b(?:clase|clases|materia|asignatura|curso|horario|sal[oó]n|aula|lugar)\s+de\s+([A-Za-zÁÉÍÓÚáéíóúñÑ0-9 ]{2,60})",
            raw,
            flags=re.IGNORECASE,
        )
        if m_sub:
            cand = m_sub.group(1)
            cand = re.sub(
                rf"\b(?:al|a\s+la|a\s+el|en\s+el|en\s+la|en|a|del|de\s+los|los|el|para|de\s+\d{{1,2}}|\d{{1,2}}:\d{{2}}|{_CLASS_LOCATION_NOUN_PATTERN}|lunes|martes|mi[eé]rcoles|miercoles|jueves|viernes|s[aá]bado|sabado|domingo)\b.*$",
                "",
                cand,
                flags=re.IGNORECASE,
            ).strip(" .,;:")
            cand_norm = normalize_intent_text(cand)
            if cand_norm:
                for cname in distinct_names:
                    if cand_norm in normalize_intent_text(cname) or normalize_intent_text(cname) in cand_norm:
                        matched_name = cname
                        break

    if not matched_name:
        return (
            False,
            "No identifiqué qué materia quieres modificar. Dime el nombre de la clase, por ejemplo: "
            "«cambia mi clase de Matematicas Discretas al Laboratorio 3» o «cambia el horario de Bases de Datos de 14:00 a 16:00».",
        )

    target_rows = [r for r in all_classes if normalize_intent_text(str(r["name"])) == normalize_intent_text(matched_name)]

    # 2. Extract new location if requested
    new_location: str | None = None
    loc_match = re.search(
        rf"\b(?:al|a\s+la|a\s+el|a|en\s+el|en\s+la|en)\s+({_CLASS_LOCATION_NOUN_PATTERN}(?:\s+[A-Za-z0-9ÁÉÍÓÚáéíóúñÑ._-]+){{0,3}})",
        raw,
        flags=re.IGNORECASE,
    )
    if loc_match:
        new_location = loc_match.group(1).strip(" .,;:")
    else:
        explicit_room = re.search(
            r"\b(?:sal[oó]n|aula|lugar|ubicaci[oó]n|auditorio|laboratorio)\b.*?\b(?:a|al|en|por)\s+([A-Za-z0-9ÁÉÍÓÚáéíóúñÑ][A-Za-z0-9ÁÉÍÓÚáéíóúñÑ\s._-]{0,35}?)\s*[.,;:]*$",
            raw,
            flags=re.IGNORECASE,
        )
        if explicit_room:
            new_location = explicit_room.group(1).strip(" .,;:")

    # 3. Extract new time range or start_time if requested
    new_start_time: str | None = None
    new_end_time: str | None = None
    time_span_match = re.search(
        r"\b(?:de\s+(?:las\s+)?|a\s+las\s+)?(\d{1,2})(?::(\d{2}))?\s*(?:a(?:\s+las)?|-|–|hasta(?:\s+las)?)\s*(\d{1,2})(?::(\d{2}))?\b",
        raw,
        re.IGNORECASE,
    )
    if time_span_match:
        h1, m1, h2, m2 = time_span_match.groups()
        new_start_time = _normalize_hour_token(h1, m1)
        new_end_time = _normalize_hour_token(h2, m2)
        if new_start_time and new_end_time and new_end_time <= new_start_time:
            try:
                eh = int(h2)
                if 1 <= eh <= 9 and int(h1) >= 7:
                    new_end_time = _normalize_hour_token(str(eh + 12), m2)
            except ValueError:
                pass
    else:
        single_time_match = re.search(r"\b(?:a\s+las\s+)(\d{1,2})(?::(\d{2}))?\b|\b(\d{1,2}):(\d{2})\b", raw, re.IGNORECASE)
        if single_time_match:
            h_s = single_time_match.group(1) or single_time_match.group(3)
            m_s = single_time_match.group(2) or single_time_match.group(4)
            new_start_time = _normalize_hour_token(h_s, m_s)

    # 4. Extract weekday transitions ("del viernes al jueves") or weekday filters ("de los viernes")
    day_move_match = re.search(
        r"\b(?:del|de\s+los|de\s+el|de)\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\s+(?:al|a\s+los|a\s+el|a|para\s+el|para\s+los)\s+(lunes|martes|miercoles|jueves|viernes|sabado|domingo)\b",
        low,
    )
    from_weekday: int | None = None
    to_weekday: int | None = None
    filter_weekdays: list[int] = []
    if day_move_match:
        from_weekday = weekday_map[day_move_match.group(1)]
        to_weekday = weekday_map[day_move_match.group(2)]
    else:
        for d_word, d_idx in weekday_map.items():
            if re.search(r"\b" + d_word + r"\b", low) and d_idx not in filter_weekdays:
                filter_weekdays.append(d_idx)

    if not any((new_location, new_start_time, from_weekday is not None, filter_weekdays)):
        return (
            False,
            f"Indica qué cambio quieres hacer en «{matched_name}» (por ejemplo: «cambia mi clase de {matched_name} al Laboratorio 3» o «mueve {matched_name} de 15:00 a 17:00»).",
        )

    rows_to_update = list(target_rows)
    if from_weekday is not None:
        subset = [r for r in target_rows if int(r["weekday"]) == from_weekday]
        if subset:
            rows_to_update = subset
    elif filter_weekdays and (new_location or new_start_time):
        subset = [r for r in target_rows if int(r["weekday"]) in filter_weekdays]
        if subset:
            rows_to_update = subset
        elif len(target_rows) == 1:
            to_weekday = filter_weekdays[0]
    elif filter_weekdays and not new_location and not new_start_time and len(filter_weekdays) == 1 and len(target_rows) == 1:
        to_weekday = filter_weekdays[0]

    updated_ids: set[int] = set()
    updated_weekdays: list[int] = []
    final_start = new_start_time or str(rows_to_update[0]["start_time"])
    final_end = new_end_time or (str(rows_to_update[0]["end_time"]) if rows_to_update[0]["end_time"] else None)
    final_loc = new_location or (str(rows_to_update[0]["location"]) if rows_to_update[0]["location"] else None)

    for r in rows_to_update:
        rid = int(r["id"])
        updated_ids.add(rid)
        wd = to_weekday if to_weekday is not None else int(r["weekday"])
        st = new_start_time or str(r["start_time"])
        et = new_end_time if new_start_time else (new_end_time or r["end_time"])
        if new_start_time and not new_end_time and r["end_time"]:
            old_s = _time_to_minutes(r["start_time"])
            old_e = _time_to_minutes(r["end_time"])
            new_s = _time_to_minutes(new_start_time)
            if old_s is not None and old_e is not None and old_e > old_s and new_s is not None:
                et = _minutes_to_time(new_s + (old_e - old_s))
        loc = new_location if new_location is not None else r["location"]
        db.execute(
            "UPDATE classes SET weekday=?, start_time=?, end_time=?, location=?, reminded_on=NULL WHERE id=?",
            (wd, st, et, loc, rid),
        )
        updated_weekdays.append(wd)
        final_start, final_end, final_loc = st, et, loc

    db.commit()
    conflicts = detect_class_schedule_conflicts(
        db,
        updated_weekdays,
        final_start,
        final_end,
        exclude_class_ids=updated_ids,
        exclude_class_name=matched_name,
    )
    days_str = ", ".join(days_labels[d] for d in sorted(set(updated_weekdays)))
    slot_str = final_start + (f"–{final_end}" if final_end else "")
    loc_str = f" en {final_loc}" if final_loc else ""
    msg = f"¡Listo! Actualicé tu clase «{matched_name}»: ahora queda en {days_str} de {slot_str}{loc_str}."
    warn = format_schedule_conflict_warning(conflicts)
    if warn:
        msg = f"{msg}\n{warn}"
    return (True, msg)


def execute_edit_task_from_chat(
    db: sqlite3.Connection,
    raw_text: str,
    today: date | None = None,
) -> tuple[bool, str]:
    """Reschedule or edit an existing pending task (due_date, due_time) from natural Spanish."""
    today = today or date.today()
    raw = str(raw_text or "").strip()
    low = normalize_intent_text(raw)

    rows = db.execute(
        "SELECT id, title, subject, due_date, due_time, priority, done FROM tasks ORDER BY done ASC, id DESC"
    ).fetchall()
    if not rows:
        return (False, "No tienes tareas registradas en tu lista para modificar.")

    # Parse target date and time from the command using a lightweight helper
    dummy = SimpleNamespace(db=db)
    parsed = AssistantApp.parse_task_proposal(dummy, raw, today=today)
    new_date = parsed.get("due_date")
    new_time = parsed.get("due_time")

    # Match the task by title or subject
    matched_row = None
    for r in rows:
        t_norm = normalize_intent_text(str(r["title"] or ""))
        s_norm = normalize_intent_text(str(r["subject"] or ""))
        if (t_norm and len(t_norm) >= 3 and t_norm in low) or (s_norm and len(s_norm) >= 3 and s_norm in low):
            matched_row = r
            break

    if matched_row is None and parsed.get("subject"):
        subj_norm = normalize_intent_text(str(parsed["subject"]))
        for r in rows:
            if normalize_intent_text(str(r["subject"] or "")) == subj_norm or subj_norm in normalize_intent_text(str(r["title"] or "")):
                matched_row = r
                break

    if matched_row is None:
        # Fallback: if there is only 1 pending task, or match significant words
        pending = [r for r in rows if not r["done"]]
        for r in pending:
            words = [w for w in normalize_intent_text(str(r["title"] or "")).split() if len(w) >= 4]
            if words and any(w in low for w in words):
                matched_row = r
                break
        if matched_row is None and len(pending) == 1:
            matched_row = pending[0]

    if matched_row is None:
        return (
            False,
            "No encontré qué tarea quieres reprogramar. Dime el nombre o la materia de la tarea, por ejemplo: "
            "«pasa la tarea de Bases de Datos para el viernes a las 18:00».",
        )

    if not new_date and not new_time:
        return (
            False,
            f"Indica para qué fecha u hora quieres mover la tarea «{matched_row['title']}» (por ejemplo: «mañana a las 18:00» o «el viernes a las 16:00»).",
        )

    final_date = new_date or matched_row["due_date"]
    final_time = new_time or matched_row["due_time"]
    db.execute(
        "UPDATE tasks SET due_date=?, due_time=?, reminded=0 WHERE id=?",
        (final_date, final_time, int(matched_row["id"])),
    )
    db.commit()
    subj_info = f" ({matched_row['subject']})" if matched_row["subject"] else ""
    when_parts = []
    if final_date:
        when_parts.append(f"fecha {final_date}")
    if final_time:
        when_parts.append(f"a las {final_time}")
    when_str = " ".join(when_parts) if when_parts else "sin fecha fija"
    return (
        True,
        f"¡Listo! Reprogramé tu tarea «{matched_row['title']}»{subj_info} para {when_str}.",
    )


def execute_edit_routine_from_chat(db: sqlite3.Connection, raw_text: str) -> tuple[bool, str]:
    """Modify an existing routine's reminder_time or weekdays from natural chat."""
    raw = str(raw_text or "").strip()
    low = normalize_intent_text(raw)
    rows = db.execute("SELECT id, title, subject, weekdays, reminder_time, active FROM routines ORDER BY id DESC").fetchall()
    if not rows:
        return (False, "No tienes rutinas registradas para editar.")

    matched = None
    for r in rows:
        t_norm = normalize_intent_text(str(r["title"] or ""))
        if t_norm and t_norm in low:
            matched = r
            break
    if matched is None:
        for r in rows:
            words = [w for w in normalize_intent_text(str(r["title"] or "")).split() if len(w) >= 4]
            if words and any(w in low for w in words):
                matched = r
                break
    if matched is None and len(rows) == 1:
        matched = rows[0]
    if matched is None:
        return (False, "No encontré qué rutina quieres cambiar. Indica su nombre, por ejemplo: «cambia la rutina de repasar inglés a las 20:00».")

    weekday_map = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
    new_days: list[int] = []
    if re.search(r"\blunes\s+a\s+viernes\b|\btodos\s+los\s+dias\b|\bdiario\b", low):
        new_days = [0, 1, 2, 3, 4]
    else:
        for w_name, idx in weekday_map.items():
            if re.search(r"\b" + w_name + r"\b", low) and idx not in new_days:
                new_days.append(idx)

    new_time: str | None = None
    t_match = re.search(r"\b(?:a\s+las\s+)?(\d{1,2})(?::(\d{2}))\b|\ba\s+las\s+(\d{1,2})\b", raw, re.IGNORECASE)
    if t_match:
        new_time = _normalize_hour_token(t_match.group(1) or t_match.group(3), t_match.group(2))

    if not new_days and not new_time:
        return (False, f"Dime la nueva hora o días para la rutina «{matched['title']}» (por ejemplo: «a las 20:00»).")

    final_weekdays = ",".join(str(d) for d in sorted(new_days)) if new_days else str(matched["weekdays"])
    final_time = new_time if new_time is not None else matched["reminder_time"]
    db.execute(
        "UPDATE routines SET weekdays=?, reminder_time=?, active=1 WHERE id=?",
        (final_weekdays, final_time, int(matched["id"])),
    )
    db.commit()
    day_names = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
    days_label = ", ".join(day_names[int(d)] for d in final_weekdays.split(",") if d.isdigit() and 0 <= int(d) < 7)
    rem_label = f" a las {final_time}" if final_time else ""
    return (True, f"¡Listo! Actualicé tu rutina «{matched['title']}» ({days_label}{rem_label}).")


def execute_edit_block_from_chat(
    db: sqlite3.Connection,
    raw_text: str,
    today: date | None = None,
) -> tuple[bool, str]:
    """Move or edit an existing study block in plan_blocks from natural chat, checking for overlaps."""
    today = today or date.today()
    raw = str(raw_text or "").strip()
    low = normalize_intent_text(raw)
    rows = db.execute("SELECT id, title, block_date, start_time, end_time, notes FROM plan_blocks ORDER BY block_date DESC, id DESC").fetchall()
    if not rows:
        return (False, "No tienes bloques de estudio agendados para modificar.")

    matched = None
    for r in rows:
        t_norm = normalize_intent_text(str(r["title"] or ""))
        if t_norm and t_norm in low:
            matched = r
            break
    if matched is None:
        for r in rows:
            words = [w for w in normalize_intent_text(str(r["title"] or "")).split() if len(w) >= 4]
            if words and any(w in low for w in words):
                matched = r
                break
    if matched is None and len(rows) == 1:
        matched = rows[0]
    if matched is None:
        return (False, "No identifiqué qué bloque de estudio quieres mover. Indica su título, por ejemplo: «mueve el bloque de estudiar Física de 17:00 a 18:00».")

    range_match = re.search(
        r"\b(?:de\s+(?:las\s+)?)?([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:a(?:\s+las)?|hasta(?:\s+las)?|[-–])\s*([01]?\d|2[0-3])(?::([0-5]\d))?\b",
        raw,
        re.IGNORECASE,
    )
    new_start = _normalize_hour_token(range_match.group(1), range_match.group(2)) if range_match else None
    new_end = _normalize_hour_token(range_match.group(3), range_match.group(4)) if range_match else None

    target_day = None
    iso_match = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", raw)
    if iso_match:
        try:
            target_day = date.fromisoformat(iso_match.group())
        except ValueError:
            target_day = None
    elif "pasado manana" in low:
        target_day = today + timedelta(days=2)
    elif "manana" in low:
        target_day = today + timedelta(days=1)
    elif "hoy" in low:
        target_day = today

    final_date = target_day.isoformat() if target_day else str(matched["block_date"])
    final_start = new_start or str(matched["start_time"])
    final_end = new_end or str(matched["end_time"])
    if not (final_start and final_end and final_end > final_start):
        return (False, "Indica un rango de horas válido de inicio y fin (por ejemplo: «de 17:00 a 18:30»).")

    db.execute(
        "UPDATE plan_blocks SET block_date=?, start_time=?, end_time=? WHERE id=?",
        (final_date, final_start, final_end, int(matched["id"])),
    )
    db.commit()
    conflicts = detect_date_schedule_conflicts(
        db,
        date.fromisoformat(final_date),
        final_start,
        final_end,
        exclude_block_id=int(matched["id"]),
    )
    msg = f"¡Listo! Actualicé el bloque «{matched['title']}» para el {final_date} de {final_start} a {final_end}."
    if conflicts:
        msg += f"\n⚠️ Atención: se empalma {'; '.join(conflicts)}. ¿Quieres moverlo a otra hora?"
    return (True, msg)


def execute_delete_class_from_chat(db: sqlite3.Connection, query_text: str) -> tuple[bool, str]:
    """Delete a class from the weekly schedule when explicitly requested by the user in chat."""
    clean = re.sub(
        r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:elimina(?:r)?|borra(?:r)?|quita(?:r)?)\s+(?:mi\s+|la\s+|las\s+)?(?:clase|clases|materia)\s*(?:de\s+)?",
        "",
        str(query_text or "").strip(),
        flags=re.IGNORECASE,
    ).strip(" .,;:")
    if not clean:
        return (False, "Indica el nombre de la clase que deseas quitar, por ejemplo: «elimina la clase de Cálculo».")
    rows = db.execute(
        "SELECT id, name FROM classes WHERE LOWER(TRIM(name))=LOWER(TRIM(?)) OR LOWER(name) LIKE ?",
        (clean, f"%{clean.casefold()}%"),
    ).fetchall()
    if not rows:
        return (False, f"No encontré ninguna clase llamada «{clean}» en tu horario.")
    removed_names = sorted({str(r["name"]) for r in rows})
    for r in rows:
        db.execute("DELETE FROM class_exceptions WHERE class_id=?", (int(r["id"]),))
        db.execute("DELETE FROM classes WHERE id=?", (int(r["id"]),))
    db.commit()
    return (True, f"¡Listo! Eliminé de tu horario semanal: {', '.join(removed_names)}.")


def execute_add_task_from_chat(db: sqlite3.Connection, proposal: dict) -> tuple[bool, str]:
    """Save a task directly into SQLite (avoiding duplicate active tasks) when the user requests it in chat."""
    title = str(proposal.get("title") or "").strip()
    if not title or title == "Tarea nueva":
        return (False, "")
    subject = str(proposal.get("subject") or "").strip() or None
    due_date = str(proposal.get("due_date") or "").strip() or None
    due_time = str(proposal.get("due_time") or "").strip() or None
    description = str(proposal.get("description") or "").strip() or None

    existing = db.execute(
        "SELECT id FROM tasks WHERE done=0 AND LOWER(TRIM(title))=LOWER(TRIM(?)) "
        "AND COALESCE(due_date,'')=COALESCE(?,'') AND COALESCE(due_time,'')=COALESCE(?,'') LIMIT 1",
        (title, due_date, due_time),
    ).fetchone()
    if not existing:
        db.execute(
            "INSERT INTO tasks(title, description, due_date, priority, done, created_at, due_time, subject) VALUES(?,?,?,?,0,?,?,?)",
            (title, description, due_date, "Normal", datetime.now().isoformat(timespec="seconds"), due_time, subject),
        )
        db.commit()
    details = [f"«{title}»"]
    if subject:
        details.append(f"materia {subject}")
    if due_date:
        details.append(f"fecha {due_date}" + (f" a las {due_time}" if due_time else ""))
    return (True, "¡Listo! Guardé la tarea " + " · ".join(details) + " en tu lista de pendientes.")


_TASK_NOISE_WORDS = {
    "hola", "clara", "clara-v", "viernes", "por", "favor", "oye", "puedes", "podrias", "quiero",
    "que", "me", "ayudes", "a", "marca", "marcar", "marcala", "marcalas", "marcalo", "marcalos",
    "marcame", "pon", "poner", "ponla", "ponlas", "ponlo", "ponme", "da", "dar", "dala", "dalas",
    "deja", "dejar", "dejala", "completa", "completar", "completala", "completalas", "complete",
    "termina", "terminar", "terminala", "terminalas", "termine", "finaliza", "finalizar", "finalizala",
    "acaba", "acabar", "acabe", "tacha", "tachar", "tachala", "palomea", "palomear", "check",
    "ya", "hice", "entregue", "realice", "cumpli", "quedo", "lista", "listas", "listo", "listos",
    "hecha", "hechas", "hecho", "hechos", "completada", "completadas", "completado", "completados",
    "terminada", "terminadas", "terminado", "terminados", "entregada", "entregadas", "entregado",
    "finalizada", "finalizadas", "finalizado", "resuelta", "resueltas", "resuelto", "como",
    "elimina", "eliminar", "borra", "borrar", "quita", "quitar", "suprime", "suprimir",
    "desmarca", "desmarcar", "reabre", "reabrir", "pendiente", "pendientes", "entrega", "prioridad",
    "normal", "alta", "baja", "sin", "fecha", "limite", "hoy", "manana", "ayer", "el", "la",
    "los", "las", "un", "una", "unos", "unas", "mi", "mis", "tu", "tus", "su", "sus", "lo",
    "de", "del", "al", "en", "para", "con", "sobre", "materia", "clase", "asignatura",
}


def _strip_task_command_wrappers(raw_text: str) -> tuple[str, str]:
    """Return (clean_phrase_preserving_task_word, core_tokens_without_generic_words) from a natural Spanish task command."""
    s = str(raw_text or "").strip()
    # Remove copy-pasted RAG metadata like "· entrega: 2026-10-23", "(prioridad Normal)", "(COMPLETADA)"
    s = re.sub(r"·\s*entrega:\s*\S+", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\(\s*(?:prioridad\s+\w+|completad[oa]s?|hech[oa]s?|terminad[oa]s?|pendiente)\s*\)", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\b20\d{2}-\d{2}-\d{2}\b", " ", s)
    s = re.sub(r"[\[\]•·\"'«»“”]", " ", s)
    # Remove leading/trailing status clauses ("como completada", "por terminada", "como hecha", etc.) anywhere in the text
    s = re.sub(
        r"\b(?:como|por)\s+(?:hech[oa]s?|completad[oa]s?|terminad[oa]s?|list[oa]s?|entregad[oa]s?|finalizad[oa]s?|resuelt[oa]s?|pendientes?)\b",
        " ",
        s,
        flags=re.IGNORECASE,
    )
    # Remove leading command verbs
    s = re.sub(
        r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:clara(?:-v|\s+v)?[,.;:\s-]*)?"
        r"(?:(?:me\s+)?(?:puedes|podr[ií]as)|quiero(?:\s+que)?|le\s+ped[ií]\s+que)?\s*"
        r"(?:marca(?:r|la|las|lo|los|me|ra)?|pon(?:er|la|las|lo|me|ga)?|da(?:r|la|las)?|deja(?:r|la)?|"
        r"completa(?:r|la|las)?|termina(?:r|la|las)?|finaliza(?:r|la)?|acaba(?:r)?|tacha(?:r|la)?|palomea(?:r)?|"
        r"ya\s+(?:hice|termin[eé]|acab[eé]|entregu[eé]|complet[eé]|realic[eé]|qued[oó])|listo\s+con|"
        r"elimina(?:r|la)?|borra(?:r|la)?|quita(?:r|la)?|reabre|reabrir|desmarca(?:r)?)\s+",
        " ",
        s,
        flags=re.IGNORECASE,
    )
    # Remove trailing isolated status words ("... completada", "... hecha")
    s = re.sub(
        r"\s+\b(?:completad[oa]s?|hech[oa]s?|terminad[oa]s?|finalizad[oa]s?|entregad[oa]s?)\s*$",
        " ",
        s,
        flags=re.IGNORECASE,
    )
    clean_phrase = re.sub(r"\s+", " ", s).strip(" -.,;:?¿!¡")
    # Also build a version without generic wrapper "la tarea (de)", "mi pendiente (de)"
    core = re.sub(
        r"^(?:(?:una|la|el|mi|mis|las|los)\s+)?(?:tarea|pendiente|entrega|trabajo|encargo|actividad)\s+(?:de\s+|sobre\s+|para\s+)?",
        "",
        clean_phrase,
        flags=re.IGNORECASE,
    ).strip(" -.,;:")
    return (clean_phrase, core or clean_phrase)


def find_best_matching_task(
    db: sqlite3.Connection,
    raw_text: str,
    *,
    prefer_pending: bool = True,
) -> sqlite3.Row | None:
    """Find the best matching task in SQLite using title, subject, and token-overlap scoring."""
    rows = db.execute("SELECT * FROM tasks ORDER BY done ASC, id DESC").fetchall()
    if not rows:
        return None
    low_full = normalize_intent_text(raw_text)
    clean_phrase, clean_core = _strip_task_command_wrappers(raw_text)
    norm_phrase = normalize_intent_text(clean_phrase)
    norm_core = normalize_intent_text(clean_core)

    # Extract meaningful user tokens (keeping numbers like '3' and words not in noise list)
    user_tokens = [
        tok for tok in re.findall(r"[a-z0-9]+", norm_phrase)
        if (tok.isdigit() or (len(tok) >= 3 and tok not in _TASK_NOISE_WORDS))
    ]
    # Note: if a task's title actually contains the word "tarea" or "tareas" (like "3 tareas"), allow "tarea"/"tareas" in title tokens
    best_row: sqlite3.Row | None = None
    best_score = 0

    for r in rows:
        t_norm = normalize_intent_text(str(r["title"] or ""))
        s_norm = normalize_intent_text(str(r["subject"] or ""))
        combined = f"{t_norm} {s_norm}".strip()
        if not combined:
            continue
        score = 0

        # 1. Exact matches on title, subject, or "title subject"
        if t_norm and (t_norm == norm_phrase or t_norm == norm_core):
            score += 130
        if combined and (combined == norm_phrase or combined == norm_core):
            score += 150
        if s_norm and (s_norm == norm_core or s_norm == norm_phrase):
            score += 95

        # 2. Substring presence in user's normalized utterance
        if t_norm and len(t_norm) >= 3 and (t_norm in norm_phrase or t_norm in low_full):
            score += 90
        if s_norm and len(s_norm) >= 3 and (s_norm in norm_phrase or s_norm in low_full):
            score += 80

        # 3. Token overlap between user tokens and task (title + subject)
        row_tokens = set(re.findall(r"[a-z0-9]+", combined))
        title_tokens = [tok for tok in re.findall(r"[a-z0-9]+", t_norm) if tok.isdigit() or len(tok) >= 3]
        matched_user_tokens = [tok for tok in user_tokens if tok in row_tokens]
        if matched_user_tokens:
            score += len(matched_user_tokens) * 30
        if title_tokens and all(tok in re.findall(r"[a-z0-9]+", low_full) for tok in title_tokens):
            score += 55
        if t_norm and s_norm and (t_norm in low_full) and (s_norm in low_full):
            score += 70

        if score > 0 and prefer_pending and int(r["done"] or 0) == 0:
            score += 35

        if score > best_score:
            best_score = score
            best_row = r

    if best_row is not None and best_score >= 30:
        return best_row

    # Fallback: if there is only 1 pending task in the entire database and the user said "marca mi tarea como completada"
    pending_rows = [r for r in rows if int(r["done"] or 0) == 0]
    if prefer_pending and len(pending_rows) == 1 and re.search(r"\b(?:tarea|pendiente|entrega)\b", low_full):
        return pending_rows[0]
    return None


def execute_complete_or_delete_task_from_chat(db: sqlite3.Connection, raw_text: str, *, delete: bool = False) -> tuple[bool, str]:
    """Complete, reopen, or delete a task matched by title/subject/tokens when commanded in natural Spanish."""
    clean_phrase, clean_core = _strip_task_command_wrappers(raw_text)
    low = normalize_intent_text(raw_text)
    want_reopen = bool(re.search(r"\b(?:reabre|reabrir|desmarca(?:r)?|volver\s+a\s+pendiente)\b", low))

    row = find_best_matching_task(db, raw_text, prefer_pending=(not delete and not want_reopen))
    if not row:
        label = clean_core or clean_phrase or str(raw_text or "").strip()
        return (False, f"No encontré ninguna tarea que coincida con «{label}».")
    subj_suffix = f" [{row['subject']}]" if row["subject"] else ""
    if delete:
        db.execute("DELETE FROM tasks WHERE id=?", (int(row["id"]),))
        db.commit()
        return (True, f"¡Listo! Eliminé la tarea «{row['title']}»{subj_suffix}.")

    is_done = bool(int(row["done"] or 0))
    if want_reopen:
        if is_done:
            msg = toggle_task_completion(db, int(row["id"])) or f"Reabrí «{row['title']}»."
            return (True, f"¡Listo! {msg}")
        return (True, f"La tarea «{row['title']}»{subj_suffix} ya estaba marcada como pendiente.")

    # Completing the task: ensure it transitions to done=1 (never accidentally reopen an already completed task)
    if not is_done:
        msg = toggle_task_completion(db, int(row["id"])) or f"Marcada como hecha: «{row['title']}»."
        return (True, f"¡Listo! {msg}")
    return (True, f"¡Listo! La tarea «{row['title']}»{subj_suffix} ya se encontraba marcada como completada.")


def sync_ollama_implied_task_actions(
    db: sqlite3.Connection,
    user_text: str,
    assistant_text: str,
) -> str | None:
    """If an indirect user request reached Ollama and Ollama marked a pending task as (COMPLETADA) / completada, persist done=1 in SQLite."""
    u_low = normalize_intent_text(str(user_text or ""))
    a_low = normalize_intent_text(str(assistant_text or ""))
    user_wants_complete = bool(
        re.search(
            r"\b(?:completad[oa]s?|hech[oa]s?|terminad[oa]s?|list[oa]s?|entregad[oa]s?|finalizad[oa]s?|"
            r"marca(?:r|la|las)?|completa(?:r|la|las)?|termina(?:r|la|las)?|tacha(?:r|la)?|"
            r"ya\s+(?:hice|termine|acabe|entregue|complete|realice|quedo))\b",
            u_low,
        )
    )
    ollama_claimed_complete = bool(
        re.search(
            r"(?:\(\s*(?:completad[oa]s?|hech[oa]s?|terminad[oa]s?)\s*\)|"
            r"marcad[oa]s?\s+como\s+(?:completad[oa]s?|hech[oa]s?|terminad[oa]s?))",
            a_low,
        )
    )
    if not (user_wants_complete and ollama_claimed_complete):
        return None
    row = find_best_matching_task(db, f"{user_text} {assistant_text}", prefer_pending=True)
    if row is not None and int(row["done"] or 0) == 0:
        toggle_task_completion(db, int(row["id"]))
        subj_suffix = f" [{row['subject']}]" if row["subject"] else ""
        return f"✅ Sincronizado en tu base de datos local: «{row['title']}»{subj_suffix} quedó marcada como completada."
    return None


def execute_add_block_from_chat(db: sqlite3.Connection, block: dict) -> tuple[bool, str]:
    """Save a study/agenda block directly into SQLite plan_blocks (avoiding exact duplicates) and warn on overlaps."""
    title = str(block.get("title") or "").strip()
    block_date = str(block.get("block_date") or "").strip()
    start_time = str(block.get("start_time") or "").strip()
    end_time = str(block.get("end_time") or "").strip()
    notes = str(block.get("notes") or "").strip() or None
    if not (title and block_date and start_time and end_time and end_time > start_time):
        return (False, "Para agendar el bloque necesito título, fecha y horas de inicio y fin (por ejemplo: «reserva de 15:00 a 16:00 mañana para estudiar Física»).")
    existing = db.execute(
        "SELECT id FROM plan_blocks WHERE block_date=? AND start_time=? AND end_time=? AND LOWER(TRIM(title))=LOWER(TRIM(?)) LIMIT 1",
        (block_date, start_time, end_time, title),
    ).fetchone()
    if existing:
        block_id = int(existing["id"])
    else:
        cur = db.execute(
            "INSERT INTO plan_blocks(title, block_date, start_time, end_time, notes, created_at) VALUES(?,?,?,?,?,?)",
            (title, block_date, start_time, end_time, notes, datetime.now().isoformat(timespec="seconds")),
        )
        db.commit()
        block_id = int(cur.lastrowid or 0)
    msg = f"¡Listo! Agendé el bloque «{title}» para el {block_date} de {start_time} a {end_time}."
    try:
        conflicts = detect_date_schedule_conflicts(
            db,
            date.fromisoformat(block_date),
            start_time,
            end_time,
            exclude_block_id=block_id,
        )
        if conflicts:
            msg += f"\n⚠️ Atención: se empalma {'; '.join(conflicts)}. ¿Quieres cambiarlo de hora?"
    except Exception:
        pass
    return (True, msg)


def parse_routine_proposal(text: str) -> dict | None:
    """Parse an explicit user request to create a recurring routine."""
    raw = str(text or "").strip()
    low = normalize_intent_text(raw)
    weekday_map = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
    weekdays: list[int] = []
    if re.search(r"\blunes\s+a\s+viernes\b|\btodos\s+los\s+dias\b|\bdiario\b", low):
        weekdays = [0, 1, 2, 3, 4]
    else:
        for w_name, idx in weekday_map.items():
            if re.search(r"\b" + w_name + r"\b", low) and idx not in weekdays:
                weekdays.append(idx)
    if not weekdays:
        weekdays = [0, 1, 2, 3, 4]
    reminder_time: str | None = None
    t_match = re.search(r"\b(?:a\s+las\s+)?(\d{1,2})(?::(\d{2}))\b|\ba\s+las\s+(\d{1,2})\b", raw, re.IGNORECASE)
    if t_match:
        h_s = t_match.group(1) or t_match.group(3)
        m_s = t_match.group(2)
        reminder_time = _normalize_hour_token(h_s, m_s)
    candidate = raw
    if t_match:
        candidate = candidate.replace(t_match.group(0), " ")
    if re.search(r"^.*?\brutinas?\s+(?:para\s+|de\s+|llamad[ao]\s+)", candidate, flags=re.IGNORECASE):
        candidate = re.sub(
            r"^.*?\brutinas?\s+(?:para\s+|de\s+|llamad[ao]\s+)",
            " ",
            candidate,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        candidate = re.sub(
            r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:clara(?:-v|\s+v)?[,.;:\s-]*)?"
            r"(?:(?:quiero|puedes)\s+)?(?:agrega(?:r)?|a[nñ]ad(?:e|ir)|crea(?:r)?|registra(?:r)?|pon(?:er|me)?|guarda(?:r)?|nueva|configura(?:r)?|tengo)"
            r"(?:\s+que)?(?:\s+tengo)?(?:\s+(?:una|mi|la))?\s*rutinas?(?:\s+para|\s+de)?\b",
            " ",
            candidate,
            count=1,
            flags=re.IGNORECASE,
        )
    day_token = r"(?:lunes|martes|mi[eé]rcoles|miercoles|jueves|viernes|s[aá]bado|sabado|domingo)"
    candidate = re.sub(
        rf"\b(?:(?:los|el|las)\s+)?(?:d[ií]as\s+)?(?:todos\s+los\s+d[ií]as|diario|de\s+lunes\s+a\s+viernes|lunes\s+a\s+viernes|(?:{day_token}(?:\s*(?:,|y|e)\s*|\s+(?:los|el)\s+|\s+)+)*{day_token})\b",
        " ",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(r"\s+", " ", candidate).strip(" :,-.;")
    if candidate and candidate[0].islower():
        candidate = candidate[0].upper() + candidate[1:]
    return {"title": candidate[:160] or None, "weekdays": ",".join(str(d) for d in sorted(weekdays)), "reminder_time": reminder_time}


def execute_add_routine_from_chat(db: sqlite3.Connection, proposal: dict) -> tuple[bool, str]:
    """Save an explicitly requested routine into SQLite (never inferred, no duplicates)."""
    title = str(proposal.get("title") or "").strip()
    weekdays = str(proposal.get("weekdays") or "0,1,2,3,4").strip()
    reminder_time = str(proposal.get("reminder_time") or "").strip() or None
    if not title:
        return (False, "Indica qué rutina deseas agregar, por ejemplo: «agrega rutina repasar inglés lunes y miércoles a las 19:00».")
    dup = db.execute(
        "SELECT id FROM routines WHERE LOWER(TRIM(title))=LOWER(TRIM(?)) AND weekdays=? AND COALESCE(reminder_time,'')=COALESCE(?,'') LIMIT 1",
        (title, weekdays, reminder_time),
    ).fetchone()
    if not dup:
        db.execute(
            "INSERT INTO routines(title, subject, weekdays, reminder_time, active, created_at, source) VALUES(?,NULL,?,?,1,?,?)",
            (title, weekdays, reminder_time, datetime.now().isoformat(timespec="seconds"), "Creada explícitamente por el usuario en chat"),
        )
        db.commit()
    day_names = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
    days_label = ", ".join(day_names[int(d)] for d in weekdays.split(",") if d.isdigit() and 0 <= int(d) < 7)
    rem_label = f" a las {reminder_time}" if reminder_time else ""
    return (True, f"¡Listo! Guardé tu rutina «{title}» ({days_label}{rem_label}).")


def execute_delete_routine_from_chat(db: sqlite3.Connection, raw_text: str) -> tuple[bool, str]:
    """Delete a recurring routine when explicitly commanded in chat."""
    clean = re.sub(
        r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:elimina(?:r)?|borra(?:r)?|quita(?:r)?|desactiva(?:r)?)\s+(?:la\s+|mi\s+)?rutina(?:\s+de|\s+para)?\s*",
        "",
        str(raw_text or "").strip(),
        flags=re.IGNORECASE,
    ).strip(" .,;:")
    if not clean:
        return (False, "Dime el nombre de la rutina que deseas eliminar, por ejemplo: «elimina la rutina de repasar inglés».")
    row = db.execute(
        "SELECT id, title FROM routines WHERE LOWER(TRIM(title))=LOWER(TRIM(?)) OR LOWER(title) LIKE ? LIMIT 1",
        (clean, f"%{clean.casefold()}%"),
    ).fetchone()
    if not row:
        return (False, f"No encontré ninguna rutina que coincida con «{clean}».")
    db.execute("DELETE FROM routines WHERE id=?", (int(row["id"]),))
    db.commit()
    return (True, f"¡Listo! Eliminé la rutina «{row['title']}».")


def parse_and_execute_calendar_exception_from_chat(
    db: sqlite3.Connection,
    raw_text: str,
    today: date | None = None,
) -> tuple[bool, str] | None:
    """Detect and record a school-calendar exception ('mañana no hay clases', 'cancela mi clase de X hoy') from natural chat."""
    raw = str(raw_text or "").strip()
    low = normalize_intent_text(raw)
    today = today or date.today()

    is_no_classes = bool(
        re.search(
            r"\b(?:no\s+hay\s+clases|no\s+tengo\s+clases|no\s+tendremos\s+clases|dia\s+sin\s+clases|sin\s+clases|suspension\s+de\s+clases)\b",
            low,
        )
        and not low.startswith(("hay ", "tengo ", "que "))
    )
    cancel_class_match = re.search(
        r"\b(?:cancela(?:r)?|se\s+cancel[oó]|suspende(?:r)?|no\s+habra)\s+(?:la\s+|mi\s+)?(?:clase|materia)\s+de\s+([A-Za-zÁÉÍÓÚáéíóúñÑ0-9 ]+)",
        raw,
        flags=re.IGNORECASE,
    )
    if not is_no_classes and not cancel_class_match:
        return None

    target_day = today
    iso_m = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", raw)
    if iso_m:
        try:
            target_day = date.fromisoformat(iso_m.group(1))
        except ValueError:
            target_day = today
    elif "pasado manana" in low:
        target_day = today + timedelta(days=2)
    elif "manana" in low:
        target_day = today + timedelta(days=1)
    else:
        wmap = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
        for wname, widx in wmap.items():
            if re.search(r"\b" + wname + r"\b", low):
                delta = (widx - today.weekday()) % 7
                target_day = today + timedelta(days=delta)
                break

    if is_no_classes:
        note_m = re.search(r"\bpor\s+(.+)$", raw, flags=re.IGNORECASE)
        note = note_m.group(1).strip(" .,;:") if note_m else "Registrado desde el chat"
        existing = db.execute(
            "SELECT id FROM class_exceptions WHERE exception_date=? AND action='no_classes' LIMIT 1",
            (target_day.isoformat(),),
        ).fetchone()
        if not existing:
            db.execute(
                "INSERT INTO class_exceptions(exception_date, action, note) VALUES(?,?,?)",
                (target_day.isoformat(), "no_classes", note[:180]),
            )
            db.commit()
        return (True, f"¡Listo! Registré el {target_day.isoformat()} como día sin clases ({note}).")

    cname = cancel_class_match.group(1).strip()
    cname = re.sub(r"\b(?:hoy|ma[nñ]ana|pasado\s+ma[nñ]ana|el\s+lunes|el\s+martes|el\s+mi[eé]rcoles|el\s+jueves|el\s+viernes)\b.*$", "", cname, flags=re.IGNORECASE).strip(" .,;:")
    row = db.execute(
        "SELECT id, name FROM classes WHERE LOWER(TRIM(name))=LOWER(TRIM(?)) OR LOWER(name) LIKE ? LIMIT 1",
        (cname, f"%{cname.casefold()}%"),
    ).fetchone()
    if not row:
        return (False, f"No encontré la clase «{cname}» en tu horario para cancelarla en esa fecha.")
    db.execute(
        "INSERT INTO class_exceptions(exception_date, class_id, action, class_name, note) VALUES(?,?,?,?,?)",
        (target_day.isoformat(), int(row["id"]), "cancel", str(row["name"]), "Cancelada por un día desde el chat"),
    )
    db.commit()
    return (True, f"¡Listo! Cancelé solo por el {target_day.isoformat()} tu clase de «{row['name']}».")


def parse_and_execute_memory_from_chat(db: sqlite3.Connection, raw_text: str) -> tuple[bool, str] | None:
    """Allow adding, listing, or deleting assistant memories directly via natural chat."""
    raw = str(raw_text or "").strip()
    low = normalize_intent_text(raw)

    if any(
        phrase in low
        for phrase in (
            "que recuerdos tienes", "cuales son mis recuerdos", "ver mi memoria", "ver memoria",
            "mostrar recuerdos", "mostrar memoria", "que tienes en tu memoria", "mis recuerdos guardados",
        )
    ):
        rows = active_memories_for(db)
        if not rows:
            return (True, "Aún no tienes recuerdos guardados en mi memoria local. Puedes decirme: «recuerda que prefiero estudiar por la tarde» o «guarda en tu memoria que mi profesor de Cálculo es el Dr. Rivera».")
        lines = ["Recuerdos activos en tu memoria local:"]
        for r in rows:
            lines.append(f"• {r['label']} [{r['category']}]: {r['content']}")
        return (True, "\n".join(lines))

    del_match = re.match(
        r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:olvida(?:\s+que)?|borra(?:r)?\s+(?:el\s+)?recuerdo(?:\s+de)?|elimina(?:r)?\s+(?:de\s+tu\s+memoria|el\s+recuerdo(?:\s+de)?))\s+(.+)$",
        raw,
        flags=re.IGNORECASE,
    )
    if del_match:
        target = del_match.group(1).strip(" .,;:")
        row = db.execute(
            "SELECT id, label FROM memories WHERE LOWER(label) LIKE ? OR LOWER(content) LIKE ? LIMIT 1",
            (f"%{target.casefold()}%", f"%{target.casefold()}%"),
        ).fetchone()
        if not row:
            return (False, f"No encontré ningún recuerdo que coincida con «{target}».")
        db.execute("DELETE FROM memories WHERE id=?", (int(row["id"]),))
        db.commit()
        return (True, f"¡Listo! Borré de mi memoria el recuerdo «{row['label']}».")

    add_match = re.match(
        r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:guarda(?:r)?\s+en\s+(?:tu\s+|mi\s+)?memoria(?:\s+que)?|agrega(?:r)?\s+(?:un\s+)?recuerdo(?:\s*[:,-]|\s+de\s+que|\s+que)?|memoriza(?:\s+que)?|recuerda\s+que)\s+(.+)$",
        raw,
        flags=re.IGNORECASE,
    )
    if add_match:
        content = add_match.group(1).strip(" .,;:")
        if not content:
            return None
        words = content.split()
        label = " ".join(words[:5]).capitalize()[:60]
        existing = db.execute("SELECT id FROM memories WHERE LOWER(TRIM(content))=LOWER(TRIM(?)) LIMIT 1", (content,)).fetchone()
        if not existing:
            db.execute(
                "INSERT INTO memories(label, content, category, created_at, source, expires_on) VALUES(?,?,?,?,?,NULL)",
                (label, content[:1500], "Preferencia", datetime.now().isoformat(timespec="seconds"), "Guardado desde el chat"),
            )
            db.commit()
        return (True, f"¡Listo! Guardé ese recuerdo en mi memoria local: «{content}».")
    return None


def parse_and_execute_settings_from_chat(settings: dict[str, str], raw_text: str) -> tuple[bool, str] | None:
    """Allow updating assistant preferences (weather city, morning routine hour, news topic, voice toggle) via natural chat."""
    raw = str(raw_text or "").strip()
    low = normalize_intent_text(raw)

    weather_m = re.search(
        r"\b(?:cambia(?:r)?|pon(?:er)?|configura(?:r)?|actualiza(?:r)?)\s+(?:la\s+|mi\s+)?(?:ubicaci[oó]n|ciudad|lugar)\s+del\s+clima\s+(?:a|en)\s+(.+)$",
        raw,
        flags=re.IGNORECASE,
    )
    if weather_m:
        loc = weather_m.group(1).strip(" .,;:")[:100]
        if loc and not contains_potential_api_key(loc):
            settings["weather_location"] = loc
            save_settings(settings)
            return (True, f"¡Listo! Actualicé la ubicación del clima en tus preferencias a «{loc}».")

    morning_m = re.search(
        r"\b(?:cambia(?:r)?|pon(?:er)?|configura(?:r)?)\s+(?:la\s+hora\s+de\s+)?(?:la\s+|mi\s+)?rutina\s+(?:matutina|de\s+ma[nñ]ana)\s+a\s+las\s+(\d{1,2})(?::(\d{2}))?\b",
        raw,
        flags=re.IGNORECASE,
    )
    if morning_m:
        hm = _normalize_hour_token(morning_m.group(1), morning_m.group(2))
        if hm:
            settings["morning_time"] = hm
            save_settings(settings)
            return (True, f"¡Listo! Cambié la hora de tu rutina matutina a las {hm} en Preferencias.")

    if any(p in low for p in ("desactiva la voz automatica", "silencia la voz automatica", "apaga la voz automatica")):
        settings["auto_speak_responses"] = "false"
        save_settings(settings)
        return (True, "¡Listo! Desactivé la lectura automática en voz alta en tus preferencias.")
    if any(p in low for p in ("activa la voz automatica", "enciende la voz automatica")):
        settings["auto_speak_responses"] = "true"
        save_settings(settings)
        return (True, "¡Listo! Activé la lectura automática en voz alta en tus preferencias.")

    return None


_EDIT_AGENDA_VERB_PATTERN = (
    r"\b(?:cambia(?:r)?|modifica(?:r)?|actualiza(?:r)?|mueve|mover|pasa(?:r)?|"
    r"reprograma(?:r)?|edita(?:r)?|corrige|corregir|pospon(?:er)?|aplaza(?:r)?|recorre(?:r)?)\b"
)


def is_schedule_conflict_query(low_text: str) -> bool:
    """Return True if the user is asking whether any classes or blocks overlap."""
    if not low_text:
        return False
    return bool(
        re.search(
            r"\b(?:choque(?:s)?(?:\s+de\s+horario)?|empalme(?:s)?|se\s+empalma(?:n)?|"
            r"se\s+cruza(?:n)?\s+(?:mis\s+)?(?:clases|materias|horarios)|"
            r"traslape(?:s)?|se\s+traslapa(?:n)?|conflicto(?:s)?\s+de\s+horario)\b",
            low_text,
        )
    )


def is_analytical_schedule_question(low_text: str) -> bool:
    """Return True for analytical/strategic questions about the user's schedule, free time, or tasks that should go to llama3.2 + RAG."""
    if not low_text:
        return False
    if re.search(
        r"\b(?:mas\s+libre|menos\s+ocupad[oa]|mas\s+despejad[oa]|horas?\s+libres?|tiempo\s+libre|"
        r"huecos?\s+(?:libres?|para\s+estudiar)|estrategia|plan\s+de\s+estudio|"
        r"sacar\s+adelante\s+(?:mis\s+)?tareas|como\s+me\s+recomiendas|que\s+me\s+recomiendas|"
        r"segun\s+mi\s+horario|segun\s+mis\s+clases|cuando\s+puedo\s+estudiar|"
        r"que\s+dia\s+.*?\b(?:libre|estudiar)|en\s+que\s+horario\s+puedo\s+estudiar)\b",
        low_text,
    ):
        return True
    return False


def compute_weekly_free_windows(
    db: sqlite3.Connection,
    day_start_hour: int = 8,
    day_end_hour: int = 20,
) -> dict[int, dict[str, object]]:
    """Compute occupied hours and free study windows (08:00–20:00) for each weekday (0=Monday..6=Sunday)."""
    repair_legacy_class_locations(db)
    days_labels = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    win_start = day_start_hour * 60
    win_end = day_end_hour * 60
    result: dict[int, dict[str, object]] = {}
    for wd in range(7):
        rows = db.execute(
            "SELECT name, start_time, end_time, location FROM classes WHERE weekday=? ORDER BY start_time, id",
            (wd,),
        ).fetchall()
        intervals: list[tuple[int, int]] = []
        classes_list: list[str] = []
        for r in rows:
            s_min = _time_to_minutes(r["start_time"])
            if s_min is None:
                continue
            e_min = _time_to_minutes(r["end_time"])
            if e_min is None or e_min <= s_min:
                e_min = min(23 * 60 + 59, s_min + 60)
            loc = f" ({r['location']})" if r["location"] else ""
            classes_list.append(f"{r['start_time']}–{_minutes_to_time(e_min)} {r['name']}{loc}")
            cs = max(win_start, s_min)
            ce = min(win_end, e_min)
            if cs < ce:
                intervals.append((cs, ce))
        intervals.sort()
        merged: list[tuple[int, int]] = []
        for s_iv, e_iv in intervals:
            if not merged or s_iv > merged[-1][1]:
                merged.append((s_iv, e_iv))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e_iv))
        occupied_mins = sum(e_iv - s_iv for s_iv, e_iv in merged)
        free_mins = max(0, (win_end - win_start) - occupied_mins)
        free_slots: list[str] = []
        cursor = win_start
        for s_iv, e_iv in merged:
            if s_iv > cursor:
                free_slots.append(f"{_minutes_to_time(cursor)}–{_minutes_to_time(s_iv)}")
            cursor = max(cursor, e_iv)
        if cursor < win_end:
            free_slots.append(f"{_minutes_to_time(cursor)}–{_minutes_to_time(win_end)}")
        result[wd] = {
            "weekday": wd,
            "day_label": days_labels[wd],
            "classes": classes_list,
            "occupied_hours": round(occupied_mins / 60.0, 1),
            "free_hours": round(free_mins / 60.0, 1),
            "free_slots": free_slots,
        }
    return result


def build_private_agenda_rag_context(
    db: sqlite3.Connection,
    today: date | None = None,
    now: datetime | None = None,
) -> str:
    """Build a compact 100% local RAG context of classes, free windows, conflicts, tasks, blocks, and routines for llama3.2.
    Never accesses security_secrets, security_users, or API keys.
    """
    today = today or date.today()
    now = now or datetime.now()
    days_labels = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    weekly = compute_weekly_free_windows(db)

    lines: list[str] = [
        f"CONTEXTO REAL DE LA AGENDA LOCAL DEL USUARIO (Fecha actual: {days_labels[today.weekday()]} {today.isoformat()}, hora: {now.strftime('%H:%M')}):",
        "1) Horario semanal de clases y huecos libres (08:00 a 20:00):",
    ]
    any_classes = any(bool(weekly[wd]["classes"]) for wd in range(7))
    if not any_classes:
        lines.append("   - El usuario aún no tiene clases registradas en su horario semanal.")
    else:
        for wd in range(7):
            info = weekly[wd]
            if not info["classes"] and wd >= 5:
                continue
            cls_str = "; ".join(info["classes"]) if info["classes"] else "Sin clases"
            slots_str = ", ".join(info["free_slots"]) if info["free_slots"] else "Sin huecos"
            lines.append(
                f"   - {info['day_label']}: Clases=[{cls_str}] · Libre={info['free_hours']}h (huecos: {slots_str})"
            )
        weekday_free_ranking = sorted(
            (weekly[wd] for wd in range(5)),
            key=lambda item: (-float(item["free_hours"]), int(item["weekday"])),
        )
        best_days = [
            f"{item['day_label']} ({item['free_hours']}h libres)"
            for item in weekday_free_ranking
            if float(item["free_hours"]) == float(weekday_free_ranking[0]["free_hours"])
        ]
        lines.append(f"   - Día(s) entre semana (Lunes–Viernes) con más tiempo libre: {', '.join(best_days)}.")

    conflicts = audit_all_schedule_conflicts(db, ref_date=today)
    if conflicts:
        lines.append("2) Choques de horario detectados:")
        for c in conflicts[:6]:
            lines.append(f"   - ⚠️ {c}")
    else:
        lines.append("2) Choques de horario: Ninguno (horario sin empalmes).")

    pending_tasks = db.execute(
        "SELECT title, subject, due_date, due_time, priority FROM tasks WHERE done=0 ORDER BY COALESCE(due_date,'9999-12-31'), COALESCE(due_time,'23:59'), id LIMIT 15"
    ).fetchall()
    lines.append("3) Tareas pendientes (done=0):")
    if not pending_tasks:
        lines.append("   - No hay tareas pendientes registradas.")
    else:
        for t in pending_tasks:
            subj = f" [{t['subject']}]" if t["subject"] else ""
            when = f" · entrega: {t['due_date']}" + (f" a las {t['due_time']}" if t["due_time"] else "") if t["due_date"] else " · sin fecha límite"
            prio = f" (Prioridad: {t['priority']})" if t["priority"] and t["priority"] != "Normal" else ""
            lines.append(f"   - {t['title']}{subj}{when}{prio}")

    upcoming_blocks = db.execute(
        "SELECT title, block_date, start_time, end_time FROM plan_blocks WHERE block_date>=? ORDER BY block_date, start_time LIMIT 10",
        (today.isoformat(),),
    ).fetchall()
    if upcoming_blocks:
        lines.append("4) Bloques de estudio programados:")
        for b in upcoming_blocks:
            lines.append(f"   - {b['block_date']} {b['start_time']}–{b['end_time']}: {b['title']}")

    active_routines = db.execute(
        "SELECT title, subject, weekdays, reminder_time FROM routines WHERE active=1 ORDER BY title LIMIT 10"
    ).fetchall()
    if active_routines:
        day_short = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
        lines.append("5) Rutinas activas:")
        for r in active_routines:
            d_str = ", ".join(day_short[int(d)] for d in str(r["weekdays"]).split(",") if d.isdigit() and 0 <= int(d) < 7)
            t_str = f" a las {r['reminder_time']}" if r["reminder_time"] else ""
            lines.append(f"   - {r['title']} ({d_str}{t_str})")

    try:
        ensure_subject_notebook_tables(db)
        notes_rows = db.execute(
            "SELECT subject, title, content FROM subject_notes ORDER BY id DESC LIMIT 10"
        ).fetchall()
        if notes_rows:
            lines.append("6) Apuntes rápidos por materia:")
            for nr in notes_rows:
                lines.append(f"   - [{nr['subject']}] {nr['title']}: {nr['content'][:160]}")
    except Exception:
        pass

    safe_lines = [ln for ln in lines if not contains_potential_api_key(ln)]
    return "\n".join(safe_lines)[:3400]


def add_subject_note(
    db: sqlite3.Connection,
    subject: str,
    content: str,
    title: str | None = None,
) -> dict[str, object]:
    """Save a quick note linked to a specific subject."""
    ensure_subject_notebook_tables(db)
    clean_subj = str(subject or "General").strip(" .,;:-")[:120] or "General"
    clean_content = str(content or "").strip(" .,;:-")[:2000]
    if not clean_content:
        raise ValueError("El contenido del apunte no puede estar vacío.")
    if title and str(title).strip():
        clean_title = str(title).strip()[:120]
    else:
        words = clean_content.split()
        clean_title = " ".join(words[:6]).capitalize()[:80]
    now_iso = datetime.now().isoformat(timespec="seconds")
    cur = db.execute(
        "INSERT INTO subject_notes(subject, title, content, created_at) VALUES(?,?,?,?)",
        (clean_subj, clean_title, clean_content, now_iso),
    )
    db.commit()
    return {
        "id": int(cur.lastrowid or 0),
        "subject": clean_subj,
        "title": clean_title,
        "content": clean_content,
        "created_at": now_iso,
    }


def update_subject_note(
    db: sqlite3.Connection,
    note_id: int,
    subject: str,
    title: str,
    content: str,
) -> bool:
    """Update an existing subject note."""
    ensure_subject_notebook_tables(db)
    clean_subj = str(subject or "General").strip()[:120] or "General"
    clean_title = str(title or "Apunte").strip()[:120] or "Apunte"
    clean_content = str(content or "").strip()[:2000]
    if not clean_content:
        return False
    cur = db.execute(
        "UPDATE subject_notes SET subject=?, title=?, content=? WHERE id=?",
        (clean_subj, clean_title, clean_content, int(note_id)),
    )
    db.commit()
    return cur.rowcount > 0


def delete_subject_note(db: sqlite3.Connection, note_id: int) -> bool:
    """Delete a subject note by ID."""
    ensure_subject_notebook_tables(db)
    cur = db.execute("DELETE FROM subject_notes WHERE id=?", (int(note_id),))
    db.commit()
    return cur.rowcount > 0


def list_subject_notes(db: sqlite3.Connection, subject: str | None = None) -> list[sqlite3.Row]:
    """List subject notes optionally filtered by subject name."""
    ensure_subject_notebook_tables(db)
    if subject and str(subject).strip() and str(subject).strip().casefold() != "todas las materias":
        s_norm = normalize_intent_text(subject)
        rows = db.execute("SELECT * FROM subject_notes ORDER BY id DESC").fetchall()
        return [r for r in rows if s_norm in normalize_intent_text(str(r["subject"]))]
    return db.execute("SELECT * FROM subject_notes ORDER BY subject, id DESC").fetchall()


def set_subject_folder(db: sqlite3.Connection, subject: str, folder_path: str | Path) -> str:
    """Link an existing local directory to a specific subject."""
    ensure_subject_notebook_tables(db)
    clean_subj = str(subject or "").strip(" .,;:-")[:120]
    if not clean_subj:
        raise ValueError("Indica el nombre de la materia para vincular su carpeta.")
    validated = validate_selected_folder(folder_path)
    now_iso = datetime.now().isoformat(timespec="seconds")
    db.execute(
        "INSERT INTO subject_folders(subject, folder_path, updated_at) VALUES(?,?,?) "
        "ON CONFLICT(subject) DO UPDATE SET folder_path=excluded.folder_path, updated_at=excluded.updated_at",
        (clean_subj, str(validated), now_iso),
    )
    db.commit()
    return str(validated)


def get_subject_folder(db: sqlite3.Connection, subject: str) -> str | None:
    """Retrieve the linked local folder path for a subject (accent/case-insensitive)."""
    ensure_subject_notebook_tables(db)
    s_norm = normalize_intent_text(str(subject or ""))
    if not s_norm:
        return None
    rows = db.execute("SELECT subject, folder_path FROM subject_folders").fetchall()
    for r in rows:
        if normalize_intent_text(str(r["subject"])) == s_norm or s_norm in normalize_intent_text(str(r["subject"])):
            return str(r["folder_path"])
    return None


def _match_known_subject_in_text(db: sqlite3.Connection, raw_text: str) -> str | None:
    """Find a known subject name from classes or subject_notes inside raw_text."""
    ensure_subject_notebook_tables(db)
    low = normalize_intent_text(raw_text)
    known = [str(r[0]).strip() for r in db.execute("SELECT DISTINCT name FROM classes WHERE name IS NOT NULL").fetchall()]
    known += [str(r[0]).strip() for r in db.execute("SELECT DISTINCT subject FROM subject_notes WHERE subject IS NOT NULL").fetchall()]
    known += [str(r[0]).strip() for r in db.execute("SELECT DISTINCT subject FROM subject_folders WHERE subject IS NOT NULL").fetchall()]
    unique = sorted({k for k in known if k}, key=len, reverse=True)
    for name in unique:
        n_norm = normalize_intent_text(name)
        if n_norm and len(n_norm) >= 3 and n_norm in low:
            return name
    return None


def parse_and_execute_subject_notebook_from_chat(
    db: sqlite3.Connection,
    raw_text: str,
    app_instance=None,
) -> tuple[bool, str] | None:
    """Handle natural chat commands for subject notes ('apunta en X que...', 'qué apuntes tengo de X') and linked subject folders."""
    ensure_subject_notebook_tables(db)
    raw = str(raw_text or "").strip()
    if not raw:
        return None
    low = normalize_intent_text(raw)

    # 1. Open or link a subject's folder
    open_folder_m = re.match(
        r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:abre|abrir|muestrame|mostrar|ver)\s+(?:mi\s+|la\s+)?carpeta\s+(?:de\s+(?:la\s+materia\s+|la\s+clase\s+)?)(.+)$",
        raw,
        flags=re.IGNORECASE,
    )
    if open_folder_m:
        subj_cand = open_folder_m.group(1).strip(" .,;:")
        matched_subj = _match_known_subject_in_text(db, subj_cand) or subj_cand
        folder = get_subject_folder(db, matched_subj)
        if not folder:
            if app_instance is not None and hasattr(app_instance, "open_subject_notebook"):
                app_instance.open_subject_notebook(initial_subject=matched_subj)
            return (
                False,
                f"Aún no tienes una carpeta local vinculada a «{matched_subj}». "
                "Puedes vincularla diciendo «vincula la carpeta de "
                f"{matched_subj} a C:\\Ruta\\Carpeta» o desde el botón «📁 Vincular carpeta de materia…» en el Cuaderno de apuntes.",
            )
        if sys.platform == "win32":
            try:
                launch_selected_folder(Path(folder))
                return (True, f"¡Listo! Abrí en el Explorador tu carpeta vinculada de «{matched_subj}»: {folder}")
            except Exception as exc:
                return (False, f"Encontré la carpeta vinculada de «{matched_subj}» ({folder}), pero no pude abrirla: {exc}")
        return (True, f"Carpeta vinculada de «{matched_subj}»: {folder}")

    link_folder_m = re.match(
        r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:vincula(?:r)?|asocia(?:r)?|asigna(?:r)?|conecta(?:r)?)\s+(?:la\s+|mi\s+)?carpeta\s+(?:de\s+(?:la\s+materia\s+)?)?(.+?)\s+(?:a|con|en)\s+(.+)$",
        raw,
        flags=re.IGNORECASE,
    )
    if link_folder_m:
        subj_cand = link_folder_m.group(1).strip(" .,;:")
        path_cand = link_folder_m.group(2).strip(" \"'.,;:")
        matched_subj = _match_known_subject_in_text(db, subj_cand) or subj_cand
        try:
            saved_path = set_subject_folder(db, matched_subj, path_cand)
            return (True, f"¡Listo! Vinculé la materia «{matched_subj}» con la carpeta local: {saved_path}")
        except Exception as exc:
            return (False, f"No pude vincular la carpeta para «{matched_subj}»: {exc}")

    # 2. Query notes for a subject or all notes
    if re.search(
        r"\b(?:que\s+apuntes\s+tengo|cuales\s+son\s+mis\s+apuntes|ver\s+(?:mis\s+)?apuntes|"
        r"mostrar\s+(?:mis\s+)?apuntes|muestrame\s+(?:mis\s+)?apuntes|mis\s+apuntes\s+de|"
        r"que\s+notas\s+tengo\s+(?:en|de)|ver\s+cuaderno(?:\s+de\s+apuntes)?|abrir\s+cuaderno(?:\s+de\s+apuntes)?)\b",
        low,
    ):
        matched_subj = _match_known_subject_in_text(db, raw)
        if not matched_subj:
            m_de = re.search(r"\b(?:apuntes|notas|cuaderno)\s+de\s+([A-Za-zÁÉÍÓÚáéíóúñÑ0-9 ]+)$", raw, flags=re.IGNORECASE)
            if m_de:
                cand = m_de.group(1).strip(" .,;:?¿")
                if cand.casefold() not in ("apuntes", "clase", "clases", "materias", "mi", "mis"):
                    matched_subj = cand
        rows = list_subject_notes(db, matched_subj)
        if not rows:
            if matched_subj:
                return (
                    True,
                    f"No tienes apuntes guardados todavía para «{matched_subj}». "
                    f"Puedes decirme: «apunta en {matched_subj} que el examen viene hasta el tema 3».",
                )
            return (
                True,
                "Tu cuaderno de apuntes por materia está vacío. "
                "Puedes decirme: «apunta en Matemáticas Discretas que el examen parcial viene hasta grafos bipartitos».",
            )
        header = f"📓 Apuntes de «{matched_subj}»:" if matched_subj else "📓 Tus apuntes rápidos por materia:"
        lines = [header]
        for r in rows[:15]:
            lines.append(f"• [{r['subject']}] {r['title']}: {r['content']}")
        folder = get_subject_folder(db, matched_subj) if matched_subj else None
        if folder:
            lines.append(f"📁 Carpeta vinculada: {folder}")
        return (True, "\n".join(lines))

    # 3. Delete a subject note
    del_note_m = re.match(
        r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:borra(?:r)?|elimina(?:r)?|quita(?:r)?)\s+(?:el\s+|mi\s+)?apunte(?:\s+de|\s+sobre|\s+en)?\s+(.+)$",
        raw,
        flags=re.IGNORECASE,
    )
    if del_note_m:
        query_str = del_note_m.group(1).strip(" .,;:")
        q_norm = normalize_intent_text(query_str)
        all_notes = db.execute("SELECT id, subject, title, content FROM subject_notes ORDER BY id DESC").fetchall()
        target = None
        for r in all_notes:
            blob = normalize_intent_text(f"{r['subject']} {r['title']} {r['content']}")
            if q_norm in blob or any(w in blob for w in q_norm.split() if len(w) >= 4):
                target = r
                break
        if target is None:
            return (False, f"No encontré ningún apunte que coincida con «{query_str}».")
        delete_subject_note(db, int(target["id"]))
        return (True, f"¡Listo! Eliminé el apunte «{target['title']}» de «{target['subject']}».")

    # 4. Add a quick note to a subject ("apunta en X que Y", "anota en mi cuaderno de X que Y", "guarda un apunte de X: Y")
    add_note_patterns = (
        r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:apunta(?:r)?|anota(?:r)?|escribe|escribir)\s+(?:en\s+(?:mi\s+|el\s+)?(?:cuaderno\s+de\s+|la\s+materia\s+de\s+|la\s+clase\s+de\s+)?)(?P<subj>.+?)\s+(?:que\s+|:\s*|-+\s*)(?P<body_text>.+)$",
        r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:guarda(?:r)?|agrega(?:r)?|crea(?:r)?|nuevo)\s+(?:un\s+)?apunte\s+(?:en|de|para)\s+(?P<subj>.+?)(?:\s+que\s+|\s*[:,-]\s*)(?P<body_text>.+)$",
    )
    for pat in add_note_patterns:
        m = re.match(pat, raw, flags=re.IGNORECASE)
        if m:
            raw_subj = m.group("subj").strip(" .,;:")
            body_text = m.group("body_text").strip(" .,;:")
            if not body_text:
                continue
            matched_subj = _match_known_subject_in_text(db, raw_subj) or raw_subj
            note = add_subject_note(db, matched_subj, body_text)
            return (
                True,
                f"¡Listo! Guardé tu apunte en el cuaderno de «{note['subject']}»: «{note['content']}».",
            )

    return None


def parse_pomodoro_command(raw_text: str, db: sqlite3.Connection | None = None) -> dict[str, object] | None:
    """Parse natural Spanish requests to start, pause, resume, stop, or query a Pomodoro / Focus timer."""
    raw = str(raw_text or "").strip()
    if not raw:
        return None
    low = normalize_intent_text(raw)

    # Status query
    if re.search(
        r"\b(?:cuanto\s+(?:tiempo\s+)?(?:falta|queda)\s+del?\s+(?:pomodoro|temporizador|cronometro)|"
        r"estado\s+del?\s+(?:pomodoro|temporizador|cronometro)|como\s+va\s+el\s+pomodoro)\b",
        low,
    ):
        return {"action": "status"}

    # Pause
    if re.search(r"\b(?:pausa(?:r)?|deten\s+temporalmente)\s+(?:el\s+|mi\s+)?(?:pomodoro|temporizador|cronometro)\b", low):
        return {"action": "pause"}

    # Resume
    if re.search(r"\b(?:reanuda(?:r)?|continua(?:r)?|sigue\s+con)\s+(?:el\s+|mi\s+)?(?:pomodoro|temporizador|cronometro)\b", low):
        return {"action": "resume"}

    # Stop / Cancel
    if re.search(
        r"\b(?:cancela(?:r)?|deten(?:er)?|apaga(?:r)?|termina(?:r)?|para(?:r)?)\s+(?:el\s+|mi\s+)?(?:pomodoro|temporizador|cronometro)\b",
        low,
    ):
        return {"action": "stop"}

    # Start Pomodoro / Timer / Countdown ("pon un pomodoro de 25 minutos para estudiar X", "avísame en 15 minutos")
    has_pomo_word = bool(re.search(r"\b(?:pomodoro|temporizador|cronometro|cuenta\s+regresiva)\b", low))
    avisame_m = re.search(r"\b(?:avisame|recuerdame)\s+en\s+(\d{1,3})\s*(?:minutos?|min|m)\b", low)
    if not has_pomo_word and not avisame_m:
        return None

    mins = 25
    min_m = re.search(r"\b(\d{1,3})\s*(?:minutos?|mins?|m)\b", low)
    if min_m:
        mins = max(1, min(240, int(min_m.group(1))))
    elif avisame_m:
        mins = max(1, min(240, int(avisame_m.group(1))))

    matched_subj = _match_known_subject_in_text(db, raw) if db is not None else None
    purpose_m = re.search(r"\b(?:para\s+(?:estudiar\s+|repasar\s+|avanzar\s+)?|de\s+|sobre\s+)(.+)$", raw, flags=re.IGNORECASE)
    label = matched_subj or ""
    if not label and purpose_m:
        cand = purpose_m.group(1)
        cand = re.sub(r"\b\d{1,3}\s*(?:minutos?|mins?|m)\b", "", cand, flags=re.IGNORECASE).strip(" .,;:")
        if cand and cand.casefold() not in ("pomodoro", "temporizador", "cronómetro", "cronometro"):
            label = cand[:80]
    if not label:
        label = f"Enfoque Pomodoro ({mins} min)"

    return {
        "action": "start",
        "minutes": mins,
        "subject": matched_subj,
        "label": label,
    }


def is_weekly_grid_query(low_text: str) -> bool:
    """Return True if the user is asking for the visual weekly schedule grid."""
    if not low_text:
        return False
    return bool(
        re.search(
            r"\b(?:cuadricula(?:\s+semanal|\s+de\s+horario)?|horario\s+en\s+cuadricula|"
            r"vista\s+semanal\s+(?:visual|en\s+cuadricula)|tabla\s+visual\s+de\s+horario|"
            r"ver\s+horario\s+semanal\s+en\s+cuadricula|mostrar\s+cuadricula)\b",
            low_text,
        )
    )


# --- Incremento 10: Reporte de Estado del Equipo en Tiempo Real (Disco, RAM, CPU, Batería y Subsistemas) ---

def _read_system_memory_gb() -> tuple[float, float, float]:
    """Return (total_gb, avail_gb, used_percent) using Windows GlobalMemoryStatusEx or /proc/meminfo without external deps."""
    if sys.platform == "win32":
        try:
            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = _MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_gb = round(stat.ullTotalPhys / (1024 ** 3), 2)
                avail_gb = round(stat.ullAvailPhys / (1024 ** 3), 2)
                used_pct = float(stat.dwMemoryLoad)
                return (total_gb, avail_gb, used_pct)
        except Exception:
            pass
    try:
        meminfo = Path("/proc/meminfo")
        if meminfo.is_file():
            raw = meminfo.read_text(encoding="utf-8", errors="replace")
            vals: dict[str, int] = {}
            for line in raw.splitlines():
                parts = line.split(":")
                if len(parts) == 2:
                    num_m = re.search(r"(\d+)", parts[1])
                    if num_m:
                        vals[parts[0].strip()] = int(num_m.group(1))
            total_kb = vals.get("MemTotal", 0)
            avail_kb = vals.get("MemAvailable") or (
                vals.get("MemFree", 0) + vals.get("Buffers", 0) + vals.get("Cached", 0)
            )
            if total_kb > 0:
                total_gb = round(total_kb / (1024 ** 2), 2)
                avail_gb = round(avail_kb / (1024 ** 2), 2)
                used_pct = round(((total_kb - avail_kb) * 100.0) / total_kb, 1)
                return (total_gb, avail_gb, used_pct)
    except Exception:
        pass
    return (0.0, 0.0, 0.0)


def _read_battery_status() -> str:
    """Return battery percentage and AC power status using Windows GetSystemPowerStatus or /sys/class/power_supply."""
    if sys.platform == "win32":
        try:
            class _SYSTEM_POWER_STATUS(ctypes.Structure):
                _fields_ = [
                    ("ACLineStatus", ctypes.c_byte),
                    ("BatteryFlag", ctypes.c_byte),
                    ("BatteryLifePercent", ctypes.c_byte),
                    ("SystemStatusFlag", ctypes.c_byte),
                    ("BatteryLifeTime", ctypes.c_ulong),
                    ("BatteryFullLifeTime", ctypes.c_ulong),
                ]

            pwr = _SYSTEM_POWER_STATUS()
            if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(pwr)):
                if pwr.BatteryFlag == 128 or pwr.BatteryLifePercent == 255:
                    return "Equipo conectado a corriente alterna (sin batería o PC de escritorio)"
                pct = int(pwr.BatteryLifePercent)
                ac_str = "conectado a corriente (cargando)" if pwr.ACLineStatus == 1 else "usando batería"
                return f"Batería al {pct}% ({ac_str})"
        except Exception:
            pass
    try:
        for bat_dir in Path("/sys/class/power_supply").glob("BAT*"):
            cap_file = bat_dir / "capacity"
            stat_file = bat_dir / "status"
            if cap_file.is_file():
                cap = cap_file.read_text(encoding="utf-8").strip()
                st = stat_file.read_text(encoding="utf-8").strip() if stat_file.is_file() else ""
                return f"Batería al {cap}%" + (f" ({st})" if st else "")
    except Exception:
        pass
    return "Conectado a corriente continua / equipo de escritorio"


def collect_realtime_pc_status(
    db: sqlite3.Connection | None = None,
    target_path: Path | None = None,
) -> dict[str, object]:
    """Collect real-time disk, RAM, CPU, power, local SQLite counts, and voice/Ollama readiness."""
    probe_dir = target_path or (DATA_DIR if DATA_DIR.exists() else Path.cwd())
    try:
        usage = shutil.disk_usage(probe_dir)
        disk_total_gb = round(usage.total / (1024 ** 3), 2)
        disk_used_gb = round(usage.used / (1024 ** 3), 2)
        disk_free_gb = round(usage.free / (1024 ** 3), 2)
        disk_used_pct = round((usage.used * 100.0) / max(1, usage.total), 1)
    except Exception:
        disk_total_gb = disk_used_gb = disk_free_gb = disk_used_pct = 0.0

    ram_total_gb, ram_avail_gb, ram_used_pct = _read_system_memory_gb()
    battery_info = _read_battery_status()
    cpu_cores = os.cpu_count() or 1
    os_label = f"{platform.system()} {platform.release()} ({platform.machine() or 'x64'})"
    py_ver = sys.version.split()[0]

    pending_tasks = classes_count = blocks_count = notes_count = routines_count = 0
    if db is not None:
        try:
            ensure_subject_notebook_tables(db)
            pending_tasks = int(db.execute("SELECT COUNT(*) FROM tasks WHERE done=0").fetchone()[0])
            classes_count = int(db.execute("SELECT COUNT(*) FROM classes").fetchone()[0])
            blocks_count = int(db.execute("SELECT COUNT(*) FROM plan_blocks").fetchone()[0])
            notes_count = int(db.execute("SELECT COUNT(*) FROM subject_notes").fetchone()[0])
            routines_count = int(db.execute("SELECT COUNT(*) FROM routines WHERE active=1").fetchone()[0])
        except Exception:
            pass

    ollama_exe = find_installed_ollama_executable()
    ollama_ready = ollama_exe is not None
    voice_diag = collect_voice_diagnostics(APP_BASE_DIR)

    return {
        "disk_path": str(probe_dir),
        "disk_total_gb": disk_total_gb,
        "disk_used_gb": disk_used_gb,
        "disk_free_gb": disk_free_gb,
        "disk_used_percent": disk_used_pct,
        "ram_total_gb": ram_total_gb,
        "ram_avail_gb": ram_avail_gb,
        "ram_used_percent": ram_used_pct,
        "battery_status": battery_info,
        "cpu_cores": cpu_cores,
        "os_label": os_label,
        "python_version": py_ver,
        "pending_tasks": pending_tasks,
        "classes_count": classes_count,
        "blocks_count": blocks_count,
        "notes_count": notes_count,
        "routines_count": routines_count,
        "ollama_installed": ollama_ready,
        "tts_ready": bool(voice_diag.get("tts_ready")),
        "ptt_ready": bool(voice_diag.get("ptt_ready")),
    }


def format_realtime_pc_status_report(snapshot: dict[str, object]) -> str:
    """Format a complete, human-friendly Spanish report of PC hardware and CLARA-V subsystems."""
    disk_free = float(snapshot.get("disk_free_gb") or 0.0)
    disk_total = float(snapshot.get("disk_total_gb") or 0.0)
    disk_pct = float(snapshot.get("disk_used_percent") or 0.0)
    ram_avail = float(snapshot.get("ram_avail_gb") or 0.0)
    ram_total = float(snapshot.get("ram_total_gb") or 0.0)
    ram_pct = float(snapshot.get("ram_used_percent") or 0.0)
    ram_line = (
        f"{ram_avail:.2f} GB disponibles de {ram_total:.2f} GB totales ({ram_pct:.1f}% en uso)."
        if ram_total > 0
        else "Información de RAM física gestionada por el sistema operativo."
    )
    ollama_txt = "instalado localmente" if snapshot.get("ollama_installed") else "modo local esencial (ejecutable no detectado en ruta estándar)"
    tts_txt = "voz activa" if snapshot.get("tts_ready") else "voz pendiente de configurar"
    ptt_txt = "micrófono Push-to-Talk listo" if snapshot.get("ptt_ready") else "Push-to-Talk opcional"

    lines = [
        "💻 Estado de tu equipo y subsistemas de CLARA-V en tiempo real:",
        f"• Almacenamiento en disco: {disk_free:.2f} GB libres de {disk_total:.2f} GB totales ({disk_pct:.1f}% en uso).",
        f"• Memoria RAM: {ram_line}",
        f"• Procesador y sistema: {snapshot.get('os_label')} · {snapshot.get('cpu_cores')} núcleos lógicos · Python {snapshot.get('python_version')}.",
        f"• Energía / batería: {snapshot.get('battery_status')}.",
        (
            f"• Agenda y cuaderno local: {snapshot.get('pending_tasks')} tarea(s) pendiente(s), "
            f"{snapshot.get('classes_count')} clase(s) semanal(es), {snapshot.get('notes_count')} apunte(s) guardado(s), "
            f"{snapshot.get('blocks_count')} bloque(s) de estudio y {snapshot.get('routines_count')} rutina(s) activa(s)."
        ),
        f"• Subsistemas de IA y Voz: Ollama ({ollama_txt}) · {tts_txt} · {ptt_txt}.",
    ]
    return "\n".join(lines)


def is_system_status_query(low_text: str) -> bool:
    """Return True if the user is asking about their computer's status, free disk space, RAM, battery, or system health."""
    if not low_text:
        return False
    return bool(
        re.search(
            r"\b(?:como\s+(?:esta|anda|va)\s+(?:mi\s+|la\s+|el\s+)?(?:computadora|pc|equipo|sistema|laptop|ordenador)|"
            r"estado\s+de(?:l)?\s+(?:mi\s+)?(?:sistema|equipo|computadora|pc|laptop|hardware)|"
            r"reporte\s+de(?:l)?\s+(?:mi\s+)?(?:sistema|equipo|computadora|pc)|"
            r"recursos\s+de(?:l)?\s+(?:sistema|equipo|mi\s+pc)|"
            r"cuanto\s+espacio\s+(?:libre\s+)?(?:tengo|queda|hay)|"
            r"espacio\s+(?:libre\s+)?en\s+(?:el\s+)?disco|"
            r"almacenamiento\s+(?:libre|disponible)|"
            r"cuanta\s+(?:memoria\s+)?ram\s+(?:libre\s+|disponible\s+)?(?:tengo|queda|hay)|"
            r"uso\s+de\s+(?:memoria\s+)?ram|memoria\s+ram\s+(?:libre|disponible)|"
            r"cuanta\s+bateria\s+(?:tengo|me\s+queda)|nivel\s+de\s+bateria)\b",
            low_text,
        )
    )


# --- Incremento 9: Modo Estudio Activo (Generador de Preguntas de Examen y Flashcards desde tus Apuntes) ---

def _build_question_from_note_sentence(subject: str, title: str, sentence: str, idx: int) -> dict[str, str]:
    """Transform a study note sentence into an active-recall exam question + hint + full answer."""
    clean_s = str(sentence or "").strip(" .•-")
    subj = str(subject or "General").strip()
    note_title = str(title or f"Apunte {idx}").strip()

    # 1. Detect definition / law / concept patterns: "X es/consiste en/establece que/calcula/determina Y"
    def_m = re.match(
        r"^(.{4,85}?)\s+(es|son|consiste\s+en|establece\s+que|define\s+como|se\s+define\s+como|"
        r"calcula|determina|permite|representa|describe|ocurri[oó]\s+en|fue)\s+(.{10,})$",
        clean_s,
        flags=re.IGNORECASE,
    )
    if def_m:
        concept = def_m.group(1).strip(" ,;:-«»\"'")
        verb = def_m.group(2).strip()
        explanation = def_m.group(3).strip()
        # Avoid turning tiny pronouns into the concept
        if len(concept.split()) <= 10 and concept.casefold() not in ("esto", "eso", "el", "la", "este", "esta"):
            q_text = f"[{subj}] Según tus apuntes («{note_title}»), ¿qué {verb} {concept}?"
            hint_words = " ".join(explanation.split()[:4]) + "…"
            return {
                "subject": subj,
                "title": note_title,
                "question": q_text,
                "hint": f"Empieza por: «{hint_words}»",
                "answer": clean_s + ".",
            }

    # 2. Detect exam / topic scope notes ("El examen viene hasta...", "Temas del parcial: ...")
    if re.search(r"\b(?:examen|parcial|evaluaci[oó]n|temario|f[oó]rmula|teorema|ley)\b", clean_s, flags=re.IGNORECASE):
        return {
            "subject": subj,
            "title": note_title,
            "question": f"[{subj}] ¿Qué detalle clave registraste en tus apuntes sobre «{note_title}»?",
            "hint": f"Relacionado con {subj} ({len(clean_s.split())} palabras clave).",
            "answer": clean_s + ".",
        }

    # 3. General active-recall question from note title & content
    words = [w.strip(".,;:()«»\"'") for w in clean_s.split() if len(w.strip(".,;:()«»\"'")) >= 5]
    clue = ", ".join(words[:3]) if words else subj
    return {
        "subject": subj,
        "title": note_title,
        "question": f"[{subj}] Explica el concepto o apunte «{note_title}» con tus propias palabras.",
        "hint": f"Conceptos clave involucrados: {clue}",
        "answer": clean_s + ".",
    }


def generate_active_study_quiz(
    db: sqlite3.Connection,
    subject: str | None = None,
    count: int = 5,
) -> dict[str, object]:
    """Generate active-recall exam questions and flashcards from the user's subject_notes (and pending tasks)."""
    ensure_subject_notebook_tables(db)
    max_cards = max(1, min(15, int(count or 5)))
    matched_subj = _match_known_subject_in_text(db, subject) if subject else None
    target_subj = matched_subj or (str(subject).strip() if subject else None)
    if target_subj and target_subj.casefold() in ("todas", "todas las materias", "general", "mis apuntes", "apuntes"):
        target_subj = None

    notes = list_subject_notes(db, target_subj)
    # If a specific subject had no exact match, try substring search across subject_notes
    if not notes and target_subj:
        t_norm = normalize_intent_text(target_subj)
        all_notes = list_subject_notes(db, None)
        notes = [
            r for r in all_notes
            if t_norm in normalize_intent_text(str(r["subject"]))
            or t_norm in normalize_intent_text(str(r["title"]))
            or t_norm in normalize_intent_text(str(r["content"]))
        ]

    cards: list[dict[str, str]] = []
    seen_answers: set[str] = set()

    for row in notes:
        subj_name = str(row["subject"] or "General").strip()
        note_title = str(row["title"] or "Apunte").strip()
        raw_content = str(row["content"] or "").strip()
        if not raw_content:
            continue
        # Split multi-sentence notes into individual study facts when sentences are substantive
        sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+|\n+", raw_content)
            if len(s.strip()) >= 18
        ]
        if not sentences:
            sentences = [raw_content]
        for sent in sentences:
            norm_a = sent.casefold()
            if norm_a in seen_answers:
                continue
            seen_answers.add(norm_a)
            card = _build_question_from_note_sentence(subj_name, note_title, sent, len(cards) + 1)
            cards.append(card)
            if len(cards) >= max_cards:
                break
        if len(cards) >= max_cards:
            break

    # Supplement with pending tasks/deliverables of that subject if fewer cards than requested
    if len(cards) < max_cards:
        if target_subj:
            task_rows = db.execute(
                "SELECT title, subject, due_date, due_time FROM tasks WHERE done=0 AND LOWER(COALESCE(subject,''))=LOWER(?) ORDER BY COALESCE(due_date,'9999-12-31') LIMIT 5",
                (target_subj,),
            ).fetchall()
        else:
            task_rows = db.execute(
                "SELECT title, subject, due_date, due_time FROM tasks WHERE done=0 AND subject IS NOT NULL ORDER BY COALESCE(due_date,'9999-12-31') LIMIT 5"
            ).fetchall()
        for t_row in task_rows:
            if len(cards) >= max_cards:
                break
            t_subj = str(t_row["subject"] or target_subj or "Agenda").strip()
            t_title = str(t_row["title"] or "").strip()
            due_str = f"Fecha límite: {t_row['due_date']}" + (f" a las {t_row['due_time']}" if t_row["due_time"] else "") if t_row["due_date"] else "Sin fecha límite asignada"
            ans_str = f"Entrega pendiente de {t_subj}: «{t_title}» ({due_str})."
            if ans_str.casefold() not in seen_answers:
                seen_answers.add(ans_str.casefold())
                cards.append(
                    {
                        "subject": t_subj,
                        "title": f"Pendiente: {t_title}",
                        "question": f"[{t_subj}] ¿Qué entrega o actividad pendiente tienes registrada para esta materia y cuándo vence?",
                        "hint": f"Revisa tus pendientes de {t_subj}.",
                        "answer": ans_str,
                    }
                )

    return {
        "subject": target_subj or "Todas tus materias",
        "cards": cards,
        "total": len(cards),
    }


def format_active_study_quiz_chat(quiz_data: dict[str, object], mode: str = "quiz") -> str:
    """Format generated study cards either as an exam (questions + hints first) or as complete flashcards."""
    subj_label = str(quiz_data.get("subject") or "Todas tus materias")
    cards = list(quiz_data.get("cards") or [])
    if not cards:
        return (
            f"🧠 Aún no encontré apuntes guardados para «{subj_label}».\n"
            "Primero agrega apuntes diciendo por ejemplo:\n"
            "• «apunta en Redes que el protocolo TCP garantiza la entrega ordenada de paquetes»\n"
            "• O abre el botón «📓 Apuntes» en la barra superior."
        )
    if mode == "flashcards":
        lines = [f"🧠 Tarjetas de repaso activo (Flashcards) · {subj_label} ({len(cards)} tarjeta(s)):"]
        for idx, c in enumerate(cards, 1):
            lines.append(
                f"\n🗂 Tarjeta {idx} ({c['title']}):\n"
                f"   ❓ Pregunta: {c['question']}\n"
                f"   💡 Pista: {c['hint']}\n"
                f"   ✅ Respuesta: {c['answer']}"
            )
        return "\n".join(lines)

    lines = [
        f"🧠 Examen rápido de estudio activo · {subj_label} ({len(cards)} pregunta(s)):",
        "Intenta responderlas mentalmente o en el chat. Cuando quieras revisar tus aciertos, dime «ver respuestas del examen» o abre «🧠 Modo Estudio»:",
    ]
    for idx, c in enumerate(cards, 1):
        lines.append(f"\n{idx}. ❓ {c['question']}\n   💡 Pista: {c['hint']}")
    return "\n".join(lines)


def format_active_study_answers_chat(quiz_data: dict[str, object] | None) -> str:
    """Format the answer key for the most recent active study quiz."""
    if not quiz_data or not quiz_data.get("cards"):
        return "No hay un examen rápido activo en este momento. Dime por ejemplo: «hazme un examen rápido de mis apuntes» o «crea tarjetas de repaso»."
    subj_label = str(quiz_data.get("subject") or "Todas tus materias")
    cards = list(quiz_data.get("cards") or [])
    lines = [f"✅ Hoja de respuestas de tu examen rápido · {subj_label}:"]
    for idx, c in enumerate(cards, 1):
        lines.append(f"\n{idx}. {c['question']}\n   ✔ Respuesta en tus apuntes: {c['answer']}")
    return "\n".join(lines)


def parse_active_study_command(raw_text: str, db: sqlite3.Connection | None = None) -> dict[str, object] | None:
    """Detect natural Spanish commands for active study quizzes, flashcards, or revealing exam answers."""
    raw = str(raw_text or "").strip()
    if not raw:
        return None
    low = normalize_intent_text(raw)

    # 1. Reveal answers of the last quiz
    if re.search(
        r"\b(?:ver\s+(?:las\s+)?respuestas(?:\s+del\s+examen|\s+del\s+cuestionario|\s+de\s+repaso)?|"
        r"mostrar\s+(?:las\s+)?respuestas|muestrame\s+(?:las\s+)?respuestas|"
        r"revela(?:r)?\s+(?:las\s+)?respuestas|cuales\s+son\s+las\s+respuestas|"
        r"califica(?:r)?\s+(?:el\s+|mi\s+)?examen|hoja\s+de\s+respuestas)\b",
        low,
    ):
        return {"action": "reveal_answers"}

    # 2. Start quiz or flashcards
    has_study_trigger = bool(
        re.search(
            r"\b(?:hazme\s+(?:un\s+)?(?:examen|test|cuestionario|quiz)|"
            r"hazme\s+(?:\d+\s+)?preguntas?\s+(?:sobre|de)|"
            r"preguntame\s+(?:sobre|de)\s+(?:mis\s+apuntes|la\s+materia|la\s+clase)|"
            r"ponme\s+a\s+prueba|"
            r"crea(?:r)?\s+(?:unas?\s+|\d+\s+)?(?:tarjetas?\s+de\s+(?:repaso|estudio)|flashcards?)|"
            r"genera(?:r)?\s+(?:unas?\s+|\d+\s+)?(?:tarjetas?\s+de\s+(?:repaso|estudio)|flashcards?|preguntas?\s+de\s+examen)|"
            r"tarjetas?\s+de\s+(?:repaso|estudio)|flashcards?|"
            r"modo\s+estudio(?:\s+activo)?|examen\s+rapido(?:\s+de)?)\b",
            low,
        )
    )
    if not has_study_trigger:
        return None

    mode = "flashcards" if re.search(r"\b(?:tarjeta|tarjetas|flashcard|flashcards)\b", low) else "quiz"
    count = 5
    cnt_m = re.search(r"\b(\d{1,2})\s*(?:preguntas?|tarjetas?|flashcards?|reactivos?)\b", low)
    if cnt_m:
        count = max(1, min(15, int(cnt_m.group(1))))

    matched_subj = _match_known_subject_in_text(db, raw) if db is not None else None
    if not matched_subj:
        subj_m = re.search(
            r"\b(?:apuntes\s+de|examen(?:\s+r[aá]pido)?\s+de|repaso\s+de|estudio\s+de|flashcards?\s+de|prueba\s+(?:en|de)|preguntas?\s+(?:sobre|de))\s+([A-Za-zÁÉÍÓÚáéíóúñÑ0-9 ]+)$",
            raw,
            flags=re.IGNORECASE,
        )
        if subj_m:
            cand = subj_m.group(1).strip(" ?¿!¡.,;:")
            cand = re.sub(r"^(?:mis\s+apuntes\s+de\s+|mis\s+apuntes|la\s+materia\s+de\s+|la\s+clase\s+de\s+)", "", cand, flags=re.IGNORECASE).strip()
            if cand and cand.casefold() not in ("mis apuntes", "apuntes", "hoy", "todo", "todas"):
                matched_subj = cand

    return {
        "action": "start_study",
        "mode": mode,
        "count": count,
        "subject": matched_subj,
    }


def build_weekly_grid_data(db: sqlite3.Connection, ref_date: date | None = None) -> dict[str, object]:
    """Assemble weekly classes, current-week study blocks, and timed routines with overlap flags for Monday–Sunday."""
    repair_legacy_class_locations(db)
    ref_date = ref_date or date.today()
    monday = ref_date - timedelta(days=ref_date.weekday())
    days_labels = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    cells_by_day: dict[int, list[dict[str, object]]] = {wd: [] for wd in range(7)}

    # 1. Weekly classes
    class_rows = db.execute(
        "SELECT id, name, weekday, start_time, end_time, location FROM classes ORDER BY weekday, start_time, id"
    ).fetchall()
    for r in class_rows:
        wd = int(r["weekday"])
        if not (0 <= wd <= 6):
            continue
        s_min = _time_to_minutes(r["start_time"])
        if s_min is None:
            continue
        e_min = _time_to_minutes(r["end_time"])
        if e_min is None or e_min <= s_min:
            e_min = min(23 * 60 + 59, s_min + 60)
        cells_by_day[wd].append(
            {
                "kind": "class",
                "title": str(r["name"]),
                "subtitle": str(r["location"] or ""),
                "start_time": str(r["start_time"]),
                "end_time": _minutes_to_time(e_min),
                "start_min": s_min,
                "end_min": e_min,
                "has_conflict": False,
            }
        )

    # 2. Study blocks falling in the current week
    for wd in range(7):
        d_iso = (monday + timedelta(days=wd)).isoformat()
        b_rows = db.execute(
            "SELECT id, title, start_time, end_time, notes FROM plan_blocks WHERE block_date=? ORDER BY start_time",
            (d_iso,),
        ).fetchall()
        for b in b_rows:
            s_min = _time_to_minutes(b["start_time"])
            e_min = _time_to_minutes(b["end_time"])
            if s_min is None or e_min is None or e_min <= s_min:
                continue
            cells_by_day[wd].append(
                {
                    "kind": "block",
                    "title": str(b["title"]),
                    "subtitle": "Bloque de estudio",
                    "start_time": str(b["start_time"]),
                    "end_time": str(b["end_time"]),
                    "start_min": s_min,
                    "end_min": e_min,
                    "has_conflict": False,
                }
            )

    # 3. Active routines with reminder_time
    r_rows = db.execute(
        "SELECT id, title, subject, weekdays, reminder_time FROM routines WHERE active=1 AND reminder_time IS NOT NULL"
    ).fetchall()
    for r in r_rows:
        s_min = _time_to_minutes(r["reminder_time"])
        if s_min is None:
            continue
        e_min = min(23 * 60 + 59, s_min + 30)
        for d_tok in str(r["weekdays"] or "").split(","):
            if d_tok.strip().isdigit():
                wd = int(d_tok.strip())
                if 0 <= wd <= 6:
                    cells_by_day[wd].append(
                        {
                            "kind": "routine",
                            "title": str(r["title"]),
                            "subtitle": str(r["subject"] or "Rutina"),
                            "start_time": str(r["reminder_time"]),
                            "end_time": _minutes_to_time(e_min),
                            "start_min": s_min,
                            "end_min": e_min,
                            "has_conflict": False,
                        }
                    )

    # Mark conflicts on each day (among classes and study blocks)
    conflict_count = 0
    for wd in range(7):
        day_items = cells_by_day[wd]
        day_items.sort(key=lambda item: (int(item["start_min"]), int(item["end_min"])))
        for i in range(len(day_items)):
            if day_items[i]["kind"] not in ("class", "block"):
                continue
            for j in range(i + 1, len(day_items)):
                if day_items[j]["kind"] not in ("class", "block"):
                    continue
                if int(day_items[i]["start_min"]) < int(day_items[j]["end_min"]) and int(day_items[j]["start_min"]) < int(day_items[i]["end_min"]):
                    day_items[i]["has_conflict"] = True
                    day_items[j]["has_conflict"] = True
                    conflict_count += 1

    return {
        "monday": monday.isoformat(),
        "days_labels": days_labels,
        "cells_by_day": cells_by_day,
        "conflict_count": conflict_count,
    }


def build_weekly_grid_summary(db: sqlite3.Connection, ref_date: date | None = None) -> str:
    """Format a structured weekly grid summary (Lunes–Sábado/Domingo) for chat and voice."""
    grid = build_weekly_grid_data(db, ref_date=ref_date)
    days_labels = grid["days_labels"]
    cells_by_day = grid["cells_by_day"]
    lines = ["🗓 Vista semanal en cuadrícula (Lunes a Sábado):"]
    any_entry = False
    for wd in range(7):
        items = cells_by_day[wd]
        if not items and wd == 6:
            continue
        if not items:
            lines.append(f"• {days_labels[wd]}: Libre (sin clases ni bloques)")
            continue
        any_entry = True
        slots = []
        for it in items:
            tag = "CLASE" if it["kind"] == "class" else "BLOQUE" if it["kind"] == "block" else "RUTINA"
            if it["has_conflict"]:
                tag = "⚠️ EMPALME · " + tag
            sub = f" ({it['subtitle']})" if it["subtitle"] else ""
            slots.append(f"[{tag}] {it['start_time']}–{it['end_time']} {it['title']}{sub}")
        lines.append(f"• {days_labels[wd]}: " + "  |  ".join(slots))
    if not any_entry:
        lines.append("Aún no tienes clases ni bloques registrados en la cuadrícula semanal.")
    return "\n".join(lines)


# --- Calculadora matemática segura (AST sin eval) e Investigación en Internet (Viernes + Wikipedia) ---

_SAFE_MATH_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}
_SAFE_MATH_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_SAFE_MATH_FUNCS: dict[str, object] = {
    "sqrt": math.sqrt,
    "raiz": math.sqrt,
    "cbrt": lambda x: math.copysign(abs(float(x)) ** (1.0 / 3.0), float(x)),
    "sin": math.sin,
    "sen": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "log": math.log,
    "ln": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "abs": abs,
    "round": round,
    "ceil": math.ceil,
    "floor": math.floor,
    "radians": math.radians,
    "degrees": math.degrees,
    "factorial": lambda n: math.factorial(int(n)) if 0 <= int(n) <= 170 else (_ for _ in ()).throw(ValueError("Factorial fuera de rango seguro (0–170).")),
    "gcd": lambda a, b: math.gcd(int(a), int(b)),
}
_SAFE_MATH_CONSTS: dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}


def normalize_spanish_math_expression(raw_expr: str) -> str:
    """Convert natural Spanish math expressions ('raíz cuadrada de 144', '15% de 840', '25 por 4') into AST-valid formulas."""
    expr = normalize_intent_text(str(raw_expr or ""))
    expr = re.sub(
        r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:clara(?:-v|\s+v)?[,.;:\s-]*)?"
        r"(?:calcula(?:r)?|cuanto\s+es|cuanto\s+da|resuelve|resolver|operacion|haz\s+la\s+cuenta(?:\s+de)?|dime\s+cuanto\s+es)\s+",
        "",
        expr,
        count=1,
    ).strip(" ?=.,;:")
    expr = expr.replace("×", "*").replace("÷", "/").replace("^", "**")
    # Convert decimal commas like 3,14 -> 3.14 when surrounded by digits
    expr = re.sub(r"(?<=\d),(?=\d)", ".", expr)
    # "el 15% de 840" / "15 por ciento de 840" -> "((15 / 100) * 840)"
    expr = re.sub(
        r"(?:el\s+)?(\d+(?:\.\d+)?)\s*(?:%|por\s+ciento)\s+de\s+(\d+(?:\.\d+)?)",
        r"((\1 / 100) * \2)",
        expr,
    )
    # "15%" -> "(15 / 100)"
    expr = re.sub(r"(\d+(?:\.\d+)?)\s*(?:%|por\s+ciento)\b", r"(\1 / 100)", expr)
    # "raiz cuadrada de X" -> "sqrt(X)"
    expr = re.sub(r"\b(?:la\s+)?raiz\s+cuadrada\s+de\s+(\d+(?:\.\d+)?|\([^)]+\))", r"sqrt(\1)", expr)
    expr = re.sub(r"\b(?:la\s+)?raiz\s+cubica\s+de\s+(\d+(?:\.\d+)?|\([^)]+\))", r"cbrt(\1)", expr)
    expr = re.sub(r"\b(?:la\s+)?raiz\s+de\s+(\d+(?:\.\d+)?|\([^)]+\))", r"sqrt(\1)", expr)
    replacements = (
        (" elevado a la ", " ** "),
        (" elevado a ", " ** "),
        (" a la potencia ", " ** "),
        (" al cuadrado", " ** 2"),
        (" al cubo", " ** 3"),
        (" dividido entre ", " / "),
        (" dividido por ", " / "),
        (" entre ", " / "),
        (" multiplicado por ", " * "),
        (" por ", " * "),
        (" mas ", " + "),
        (" menos ", " - "),
    )
    padded = f" {expr} "
    for src, dst in replacements:
        padded = padded.replace(src, dst)
    # Only replace standalone 'x' between numbers/parens as multiplication
    padded = re.sub(r"(?<=[\d)])\s+x\s+(?=[\d(])", " * ", padded)
    padded = re.sub(r"\b(?:el|la|del|de)\b", " ", padded)
    return re.sub(r"\s+", " ", padded).strip()


def evaluate_safe_math_expression(raw_expr: str) -> float | int:
    """Safely evaluate a mathematical expression via AST whitelist without eval()."""
    norm = normalize_spanish_math_expression(raw_expr)
    if not norm or len(norm) > 240:
        raise ValueError("Expresión matemática vacía o demasiado larga.")
    tree = ast.parse(norm, mode="eval")

    def _eval_node(node: ast.AST) -> float | int:
        if isinstance(node, ast.Expression):
            return _eval_node(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_MATH_UNARY_OPS:
            return _SAFE_MATH_UNARY_OPS[type(node.op)](_eval_node(node.operand))
        if isinstance(node, ast.BinOp):
            left = _eval_node(node.left)
            right = _eval_node(node.right)
            if isinstance(node.op, ast.Pow):
                if abs(float(right)) > 1000 or (abs(float(left)) > 1e6 and abs(float(right)) > 20):
                    raise ValueError("Exponente demasiado grande para evaluación segura.")
                return left ** right
            if type(node.op) in _SAFE_MATH_BIN_OPS:
                return _SAFE_MATH_BIN_OPS[type(node.op)](left, right)
            raise ValueError("Operador no permitido.")
        if isinstance(node, ast.Name):
            if node.id in _SAFE_MATH_CONSTS:
                return _SAFE_MATH_CONSTS[node.id]
            raise ValueError(f"Constante desconocida: {node.id}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            fname = node.func.id.casefold()
            fn = _SAFE_MATH_FUNCS.get(fname)
            if fn is None or node.keywords:
                raise ValueError(f"Función no permitida: {fname}")
            args = [_eval_node(a) for a in node.args]
            return fn(*args)  # type: ignore[misc]
        raise ValueError("Elemento de expresión no permitido.")

    val = _eval_node(tree)
    if isinstance(val, float) and val.is_integer() and abs(val) < 1e15:
        return int(val)
    if isinstance(val, float):
        return round(val, 8)
    return val


def parse_and_execute_math_from_chat(raw_text: str) -> tuple[bool, str] | None:
    """Detect and solve mathematical calculations directly and safely without requiring Ollama."""
    raw = str(raw_text or "").strip()
    if not raw:
        return None
    low = normalize_intent_text(raw)
    # Avoid intercepting agenda/time/date/pomodoro commands
    if re.search(
        r"\b(?:clase|clases|materia|tarea|pendiente|rutina|bloque|pomodoro|temporizador|"
        r"cronometro|carpeta|archivo|documento|apunte|secreto|usuario|nivel|alarma|recordatorio|"
        r"lunes|martes|miercoles|jueves|viernes|sabado|domingo|manana|hoy|ayer|enero|febrero|"
        r"marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b",
        low,
    ):
        return None
    if re.search(r"\b\d{1,2}:\d{2}\b", low) or re.search(r"\b20\d{2}-\d{2}-\d{2}\b", low):
        return None

    has_math_prefix = bool(
        re.match(
            r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:clara(?:-v|\s+v)?[,.;:\s-]*)?"
            r"(?:calcula(?:r)?|cuanto\s+es|cuanto\s+da|resuelve|resolver|haz\s+la\s+cuenta(?:\s+de)?|dime\s+cuanto\s+es)\b",
            low,
        )
    )
    norm_expr = normalize_spanish_math_expression(raw)
    has_digit = bool(re.search(r"\d", norm_expr))
    has_op_or_fn = bool(
        re.search(r"(\*\*|[+\-*/%])", norm_expr)
        or re.search(r"\b(?:sqrt|cbrt|sin|sen|cos|tan|log|ln|log10|exp|factorial|gcd|pi)\b", norm_expr)
    )
    if not (has_digit and has_op_or_fn):
        return None
    # If there is no explicit math prefix, require the normalized expression to consist strictly of math tokens
    if not has_math_prefix:
        stripped_tokens = re.sub(
            r"\b(?:sqrt|cbrt|sin|sen|cos|tan|asin|acos|atan|log|ln|log10|exp|abs|round|ceil|floor|radians|degrees|factorial|gcd|pi|e|tau)\b",
            "",
            norm_expr,
        )
        if re.search(r"[a-zA-Z]", stripped_tokens):
            return None
    try:
        result = evaluate_safe_math_expression(raw)
        return (True, f"🧮 Resultado de `{norm_expr}` = **{result}**")
    except ZeroDivisionError:
        return (False, "🧮 No se puede dividir entre cero.")
    except Exception as exc:
        if has_math_prefix:
            return (False, f"🧮 No pude resolver esa expresión matemática ({exc}). Ejemplo válido: «calcula (120 + 80) / 5» o «cuánto es la raíz cuadrada de 144».")
        return None


def _clean_web_search_text(value: str) -> str:
    value = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", str(value or ""), flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r"<[^>]+>", " ", value)
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip(" -\t\r\n")


def _wikipedia_es_summary(query: str, urlopen=None) -> str | None:
    """Query Spanish Wikipedia REST/Extracts API for a complete, multi-sentence encyclopedia summary without mid-word truncation."""
    opener = urlopen or urllib.request.urlopen
    clean_q = re.sub(r"\s+", " ", str(query or "")).strip(" ?¿!¡.,;:")
    if not clean_q:
        return None
    search_url = (
        "https://es.wikipedia.org/w/api.php?action=query&list=search&srsearch="
        + urllib.parse.quote_plus(clean_q)
        + "&utf8=1&format=json&srlimit=3"
    )
    req = urllib.request.Request(search_url, headers={"User-Agent": "CLARA-V/2.0 (+local-assistant)"})
    with opener(req, timeout=8) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    hits = data.get("query", {}).get("search", [])
    if not hits:
        return None
    top_title = str(hits[0].get("title") or "").strip()
    if not top_title:
        return None

    extract = ""
    try:
        sum_url = "https://es.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(top_title.replace(" ", "_"))
        req_sum = urllib.request.Request(sum_url, headers={"User-Agent": "CLARA-V/2.0 (+local-assistant)"})
        with opener(req_sum, timeout=8) as resp_sum:
            sum_data = json.loads(resp_sum.read().decode("utf-8", errors="replace"))
        extract = _clean_web_search_text(str(sum_data.get("extract") or ""))
    except Exception:
        extract = ""

    # Also query MediaWiki extracts API to obtain the complete multi-paragraph explanation when available
    try:
        ext_url = (
            "https://es.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&exsectionformat=plain&exchars=3200&titles="
            + urllib.parse.quote_plus(top_title)
            + "&utf8=1&format=json"
        )
        req_ext = urllib.request.Request(ext_url, headers={"User-Agent": "CLARA-V/2.0 (+local-assistant)"})
        with opener(req_ext, timeout=8) as resp_ext:
            ext_data = json.loads(resp_ext.read().decode("utf-8", errors="replace"))
        pages = ext_data.get("query", {}).get("pages", {})
        if isinstance(pages, dict):
            for page_obj in pages.values():
                if isinstance(page_obj, dict) and page_obj.get("extract"):
                    full_ext = _clean_web_search_text(str(page_obj.get("extract") or ""))
                    if len(full_ext) > len(extract):
                        extract = full_ext
                    break
    except Exception:
        pass

    if extract:
        complete_extract = truncate_at_sentence_boundary(extract, max_chars=2800)
        return f"Wikipedia ({top_title}): {complete_extract}"
    snippet = _clean_web_search_text(str(hits[0].get("snippet") or ""))
    if snippet:
        return f"Wikipedia ({top_title}): {truncate_at_sentence_boundary(snippet, max_chars=900)}"
    return None


def _duckduckgo_instant_and_html(query: str, urlopen=None) -> list[str]:
    """Query DuckDuckGo Instant Answer JSON + HTML snippets (ported from Viernes services/tools.py)."""
    opener = urlopen or urllib.request.urlopen
    q_enc = urllib.parse.quote_plus(str(query or "").strip())
    results: list[str] = []
    if not q_enc:
        return results
    try:
        ia_url = f"https://api.duckduckgo.com/?q={q_enc}&format=json&no_redirect=1&no_html=1&kl=mx-es"
        req = urllib.request.Request(ia_url, headers={"User-Agent": "CLARA-V/2.0 (+local-assistant)"})
        with opener(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        abstract = _clean_web_search_text(str(data.get("AbstractText") or ""))
        heading = _clean_web_search_text(str(data.get("Heading") or ""))
        if abstract:
            results.append(
                f"{heading + ': ' if heading else ''}{truncate_at_sentence_boundary(abstract, max_chars=1400)}"
            )
        for item in (data.get("RelatedTopics") or [])[:3]:
            if isinstance(item, dict) and item.get("Text"):
                results.append(truncate_at_sentence_boundary(_clean_web_search_text(str(item["Text"])), max_chars=800))
    except Exception:
        pass
    if len(results) < 2:
        try:
            html_url = f"https://html.duckduckgo.com/html/?q={q_enc}"
            req_h = urllib.request.Request(html_url, headers={"User-Agent": "CLARA-V/2.0 (+local-assistant)"})
            with opener(req_h, timeout=9) as resp_h:
                raw_html = resp_h.read().decode("utf-8", errors="replace")
            pattern = re.compile(
                r'<a[^>]+class="[^"]*result__a[^"]*"[^>]*>(.*?)</a>'
                r'.{0,2500}?'
                r'(?:<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>|'
                r'<div[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</div>)',
                flags=re.IGNORECASE | re.DOTALL,
            )
            seen = {r.casefold() for r in results}
            for m in pattern.finditer(raw_html):
                title = _clean_web_search_text(m.group(1))
                snip = _clean_web_search_text(m.group(2) or m.group(3) or "")
                if not snip:
                    continue
                entry = f"{title}: {snip}" if title else snip
                if entry.casefold() not in seen:
                    seen.add(entry.casefold())
                    results.append(truncate_at_sentence_boundary(entry, max_chars=850))
                if len(results) >= 3:
                    break
        except Exception:
            pass
    return results


def search_web_summary(query: str, urlopen=None) -> str:
    """Research a topic on the internet using Spanish Wikipedia + DuckDuckGo (from Viernes) without mid-sentence truncation."""
    clean_q = re.sub(
        r"^(?:que\s+es(?:\s+un|\s+una|\s+el|\s+la)?|quien\s+(?:es|fue)|cual\s+es|como\s+funciona|definicion\s+de|significado\s+de)\s+",
        "",
        str(query or "").strip(" ?¿!¡.,;:"),
        count=1,
        flags=re.IGNORECASE,
    ).strip() or str(query or "").strip(" ?¿!¡.,;:")
    if not clean_q:
        return "Indica qué tema deseas que investigue en internet."
    sections: list[str] = []
    try:
        wiki = _wikipedia_es_summary(clean_q, urlopen=urlopen)
        if wiki:
            sections.append(wiki)
    except Exception:
        pass
    try:
        ddg = _duckduckgo_instant_and_html(clean_q, urlopen=urlopen)
        for item in ddg:
            if item and all(item[:60].casefold() not in s.casefold() for s in sections):
                sections.append(item)
    except Exception:
        pass
    if not sections:
        return f"🌐 Busqué «{clean_q}» en internet, pero no obtuve fragmentos directos en este momento. Verifica tu conexión o intenta con términos más específicos."
    bullets = "\n\n".join(f"• {sec}" for sec in sections[:4])
    return f"🌐 Investigación en internet sobre «{clean_q}»:\n\n{bullets}"


def extract_web_research_query(raw_text: str) -> str | None:
    """If the user is explicitly asking to search/research on the internet/web/Wikipedia, return the query."""
    raw = str(raw_text or "").strip()
    if not raw:
        return None
    low = normalize_intent_text(raw)
    # Do not confuse with local file search ("busca mi archivo pdf...")
    if re.search(r"\b(?:mi|mis)\s+(?:documento|documentos|archivo|archivos|carpeta|clase|tarea|apunte)\b", low):
        return None
    if re.search(r"\.(?:pdf|docx|xlsx|pptx|txt|md)\b", low):
        return None
    m = re.match(
        r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:clara(?:-v|\s+v)?[,.;:\s-]*)?"
        r"(?:investiga(?:r)?(?:\s+en\s+(?:internet|la\s+web|linea|wikipedia))?(?:\s+sobre|\s+acerca\s+de|\s+que\s+es)?|"
        r"busca(?:r)?\s+en\s+(?:internet|la\s+web|google|duckduckgo|wikipedia|linea)(?:\s+sobre|\s+acerca\s+de)?|"
        r"consulta(?:r)?\s+en\s+(?:internet|la\s+web|wikipedia)(?:\s+sobre)?|"
        r"que\s+dice\s+(?:internet|wikipedia|la\s+web)\s+(?:sobre|acerca\s+de|de))\s+(.+)$",
        raw,
        flags=re.IGNORECASE,
    )
    if m:
        q = m.group(1).strip(" ?¿!¡.,;:")
        return q if q else None
    return None


def build_local_analytical_schedule_answer(
    db: sqlite3.Connection,
    query_text: str,
    today: date | None = None,
) -> str:
    """Provide a deterministic local schedule & task strategy analysis when Ollama is offline or for direct verification."""
    today = today or date.today()
    weekly = compute_weekly_free_windows(db)
    ranking = sorted(
        (weekly[wd] for wd in range(5)),
        key=lambda item: (-float(item["free_hours"]), int(item["weekday"])),
    )
    top_day = ranking[0]
    top_days = [
        str(item["day_label"])
        for item in ranking
        if float(item["free_hours"]) == float(top_day["free_hours"])
    ]
    busy_days = [
        f"{ weekly[wd]['day_label'] } ({ ', '.join(weekly[wd]['classes']) })"
        for wd in range(5)
        if weekly[wd]["classes"]
    ]
    pending_tasks = db.execute(
        "SELECT title, subject, due_date, due_time FROM tasks WHERE done=0 ORDER BY COALESCE(due_date,'9999-12-31'), COALESCE(due_time,'23:59'), id LIMIT 8"
    ).fetchall()

    out = [
        "📊 Análisis local de tu horario y tareas pendientes:",
        f"• Día(s) más libre(s) entre semana (08:00–20:00): {', '.join(top_days)} con {top_day['free_hours']} h disponibles (huecos: {', '.join(top_day['free_slots'])}).",
    ]
    if busy_days:
        out.append("• Días con clases registradas: " + " | ".join(busy_days) + ".")
    for wd in range(5):
        info = weekly[wd]
        if info["classes"]:
            out.append(
                f"  - {info['day_label']}: {info['free_hours']} h libres → ventanas recomendadas para estudiar: {', '.join(info['free_slots'])}."
            )
    if pending_tasks:
        out.append("• Estrategia sugerida para tus tareas pendientes (ordenadas por entrega más próxima):")
        for idx, t in enumerate(pending_tasks, 1):
            subj = f" ({t['subject']})" if t["subject"] else ""
            due = f" — vence el {t['due_date']}" + (f" a las {t['due_time']}" if t["due_time"] else "") if t["due_date"] else ""
            rec_day = top_days[(idx - 1) % len(top_days)]
            rec_slot = weekly[next(w for w in range(5) if weekly[w]["day_label"] == rec_day)]["free_slots"][0]
            out.append(f"  {idx}. «{t['title']}»{subj}{due} → te recomiendo avanzar el {rec_day} en el hueco {rec_slot}.")
    conflicts = audit_all_schedule_conflicts(db, ref_date=today)
    if conflicts:
        out.append("⚠️ Choques de horario detectados: " + "; ".join(conflicts))
    return "\n".join(out)


_SPANISH_TIME_NUMBER_WORDS: dict[str, int] = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "diez": 10, "quince": 15, "veinte": 20, "veinticinco": 25,
    "treinta": 30, "cuarenta": 40, "cuarenta y cinco": 45, "cincuenta": 50,
    "sesenta": 60, "noventa": 90,
}


def _parse_relative_offset_minutes(low_text: str) -> tuple[str, int] | None:
    """Extract ('before' | 'after', offset_minutes) from natural Spanish relative time expressions around classes."""
    anchor_rel = r"(?:antes|previo|despues|luego|al\s+terminar|al\s+salir|saliendo)"
    if not re.search(rf"\b{anchor_rel}\s+(?:de|a|del|al)\s+(?:mi\s+|la\s+|las\s+|mis\s+|entrar\s+a\s+|salir\s+de\s+)?(?:primera\s+|ultima\s+|1ra\s+|1a\s+)?clases?\b", low_text):
        return None

    direction = "after" if re.search(r"\b(?:despues|luego|al\s+terminar|al\s+salir|saliendo)\s+(?:de|a|del|al)\b", low_text) else "before"

    # Special fractional phrases: "hora y media", "media hora", "un cuarto de hora"
    if re.search(r"\b(?:una?\s+|1\s+)?hora\s+y\s+media\s+(?:antes|previo|despues|luego)\b", low_text):
        return (direction, 90)
    if re.search(r"\bmedia\s+hora\s+(?:antes|previo|despues|luego)\b", low_text):
        return (direction, 30)
    if re.search(r"\b(?:un\s+)?cuarto\s+de\s+hora\s+(?:antes|previo|despues|luego)\b", low_text):
        return (direction, 15)

    # Numeric or word-number + horas/minutos: "una hora antes", "2 horas antes", "30 minutos antes", "quince minutos antes"
    num_m = re.search(
        r"\b(\d{1,3}|cuarenta\s+y\s+cinco|veinticinco|UN|una|uno|dos|tres|cuatro|cinco|diez|quince|veinte|treinta|cuarenta|cincuenta|sesenta|noventa)\s*"
        r"(horas?|hrs?|h|minutos?|mins?|m)\s+(?:antes|previo|despues|luego)\b",
        low_text,
        flags=re.IGNORECASE,
    )
    if num_m:
        raw_num = num_m.group(1).strip().casefold()
        unit = num_m.group(2).strip().casefold()
        val = int(raw_num) if raw_num.isdigit() else _SPANISH_TIME_NUMBER_WORDS.get(raw_num, 1)
        mins = val * 60 if unit.startswith("h") else val
        return (direction, max(5, min(360, mins)))

    if re.search(r"\b(?:al\s+terminar|al\s+salir|saliendo\s+de)\b", low_text):
        return ("after", 0)
    return (direction, 60)


def parse_and_execute_relative_schedule_command(
    db: sqlite3.Connection,
    raw_text: str,
    today: date | None = None,
) -> tuple[bool, str] | None:
    """Resolve and schedule activities expressed relative to the user's classes (e.g. 'Agrega Ir a la Universidad una hora antes a mi primera clase del día en todos los días')."""
    raw = str(raw_text or "").strip()
    if not raw:
        return None
    low = normalize_intent_text(raw)
    today = today or date.today()

    # Must start with or contain an add/schedule verb
    if not re.search(
        r"\b(?:agrega(?:r)?|anad(?:e|ir)|pon(?:er|me)?|programa(?:r)?|reserva(?:r)?|crea(?:r)?|"
        r"registra(?:r)?|guarda(?:r)?|anota(?:r)?|apunta(?:r)?|configura(?:r)?|prepara(?:r|me)?)\b",
        low,
    ):
        return None

    rel_info = _parse_relative_offset_minutes(low)
    if rel_info is None:
        return None
    direction, offset_mins = rel_info

    # Determine anchor type: first class of the day, last class of the day, or a specific subject class
    if re.search(r"\b(?:primera|1ra|1a)\s+clase\b|\bentrar\s+a\s+clases?\b", low):
        anchor_kind = "first_class"
    elif re.search(r"\b(?:ultima)\s+clase\b|\bsalir\s+de\s+clases?\b", low):
        anchor_kind = "last_class"
    else:
        anchor_kind = "specific_class"

    # Extract the activity title by removing leading verb and the relative time + day clauses
    title_cand = re.sub(
        r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:clara(?:-v|\s+v)?[,.;:\s-]*)?"
        r"(?:(?:me\s+)?(?:puedes|podr[ií]as)\s+)?"
        r"(?:agrega(?:r)?|a[nñ]ad(?:e|ir)|pon(?:er|me)?|programa(?:r)?|reserva(?:r)?|crea(?:r)?|"
        r"registra(?:r)?|guarda(?:r)?|anota(?:r)?|apunta(?:r)?|configura(?:r)?|prepara(?:r|me)?)"
        r"(?:\s+(?:una?\s+|la\s+|mi\s+|un\s+)?(?:rutina|bloque|actividad|recordatorio|evento)(?:\s+de|\s+para)?)?\s+",
        "",
        raw,
        count=1,
        flags=re.IGNORECASE,
    )
    # Strip from the relative offset expression onward
    title_cand = re.sub(
        r"\s+\b(?:\d{1,3}|una?\s+hora\s+y\s+media|media\s+hora|(?:un\s+)?cuarto\s+de\s+hora|"
        r"cuarenta\s+y\s+cinco|veinticinco|un|una|uno|dos|tres|cuatro|cinco|diez|quince|veinte|treinta|cuarenta|cincuenta|sesenta|noventa)"
        r"(?:\s*(?:horas?|hrs?|h|minutos?|mins?|m))?\s+(?:antes|previo|despu[eé]s|luego)\s+(?:de|a|del|al)\b.*$",
        "",
        title_cand,
        flags=re.IGNORECASE,
    )
    title_cand = re.sub(
        r"\s+\b(?:justo\s+)?(?:antes|previo|despu[eé]s|luego|al\s+terminar|al\s+salir|saliendo)\s+(?:de|a|del|al)\s+(?:mi\s+|la\s+|las\s+|mis\s+)?(?:primera\s+|última\s+|ultima\s+)?clases?\b.*$",
        "",
        title_cand,
        flags=re.IGNORECASE,
    )
    title_cand = re.sub(
        r"\s+\b(?:en\s+todos\s+los\s+d[ií]as|todos\s+los\s+d[ií]as|cada\s+d[ií]a|diario|de\s+lunes\s+a\s+viernes)\b.*$",
        "",
        title_cand,
        flags=re.IGNORECASE,
    )
    title_cand = re.sub(r"\s+", " ", title_cand).strip(" :,-.;\"'«»")
    if not title_cand:
        title_cand = "Ir a la Universidad" if direction == "before" else "Actividad después de clases"
    elif title_cand[0].islower():
        title_cand = title_cand[0].upper() + title_cand[1:]

    repair_legacy_class_locations(db)
    all_classes = db.execute(
        "SELECT id, name, weekday, start_time, end_time, location FROM classes ORDER BY weekday, start_time, id"
    ).fetchall()
    if not all_classes:
        return (
            False,
            f"Quise programar «{title_cand}» en relación con tus clases, pero aún no tienes clases registradas en tu horario semanal.",
        )

    # Determine target weekdays
    weekday_map = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
    explicit_days = [idx for w_name, idx in weekday_map.items() if re.search(r"\b" + w_name + r"\b", low)]
    if not explicit_days and not re.search(r"\b(?:todos\s+los\s+dias|cada\s+dia|diario|lunes\s+a\s+viernes)\b", low):
        if "pasado manana" in low:
            explicit_days = [(today + timedelta(days=2)).weekday()]
        elif "manana" in low and "por la manana" not in low and "de la manana" not in low:
            explicit_days = [(today + timedelta(days=1)).weekday()]
        elif re.search(r"\bhoy\b", low):
            explicit_days = [today.weekday()]

    matched_subj = _match_known_subject_in_text(db, raw) if anchor_kind == "specific_class" else None

    by_weekday: dict[int, list[sqlite3.Row]] = {}
    for c_row in all_classes:
        wd = int(c_row["weekday"])
        if explicit_days and wd not in explicit_days:
            continue
        if anchor_kind == "specific_class" and matched_subj:
            if normalize_intent_text(str(c_row["name"])) != normalize_intent_text(matched_subj):
                continue
        by_weekday.setdefault(wd, []).append(c_row)

    if not by_weekday:
        return (
            False,
            f"No encontré clases registradas en esos días para calcular el horario de «{title_cand}».",
        )

    days_labels = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
    scheduled_items: list[dict[str, object]] = []

    for wd in sorted(by_weekday.keys()):
        day_classes = sorted(by_weekday[wd], key=lambda r: _time_to_minutes(r["start_time"]) or 0)
        anchor_cls = day_classes[-1] if anchor_kind == "last_class" else day_classes[0]
        cls_start = _time_to_minutes(anchor_cls["start_time"]) or (8 * 60)
        cls_end = _time_to_minutes(anchor_cls["end_time"]) or min(23 * 60 + 59, cls_start + 60)

        if direction == "before":
            dur = max(15, offset_mins)
            start_min = max(0, cls_start - offset_mins)
            end_min = min(cls_start, start_min + dur)
            ref_desc = f"antes de {anchor_cls['name']} ({anchor_cls['start_time']})"
        else:
            dur = offset_mins if offset_mins > 0 else 60
            start_min = min(23 * 60, cls_end + (0 if offset_mins == 0 else offset_mins))
            end_min = min(23 * 60 + 59, start_min + dur)
            ref_desc = f"después de {anchor_cls['name']} ({_minutes_to_time(cls_end)})"

        scheduled_items.append(
            {
                "weekday": wd,
                "day_label": days_labels[wd],
                "start_time": _minutes_to_time(start_min),
                "end_time": _minutes_to_time(end_min),
                "ref_desc": ref_desc,
            }
        )

    # 1. Group by start_time to persist clean recurring routines in `routines`
    time_to_days: dict[str, list[int]] = {}
    for item in scheduled_items:
        time_to_days.setdefault(str(item["start_time"]), []).append(int(item["weekday"]))

    now_iso = datetime.now().isoformat(timespec="seconds")
    for rem_time, wds in time_to_days.items():
        weekdays_csv = ",".join(str(d) for d in sorted(set(wds)))
        dup = db.execute(
            "SELECT id FROM routines WHERE LOWER(TRIM(title))=LOWER(TRIM(?)) AND weekdays=? AND COALESCE(reminder_time,'')=COALESCE(?,'') LIMIT 1",
            (title_cand, weekdays_csv, rem_time),
        ).fetchone()
        if not dup:
            db.execute(
                "INSERT INTO routines(title, subject, weekdays, reminder_time, active, created_at, source) VALUES(?,NULL,?,?,1,?,?)",
                (title_cand, weekdays_csv, rem_time, now_iso, "Programada relativamente al horario de clases desde el chat"),
            )

    # 2. Also create concrete plan_blocks for each matching day in the current 7-day window so it shows in Agenda, Grid & ¿Qué sigue?
    for item in scheduled_items:
        wd = int(item["weekday"])
        delta = (wd - today.weekday()) % 7
        target_date_str = (today + timedelta(days=delta)).isoformat()
        s_t = str(item["start_time"])
        e_t = str(item["end_time"])
        existing_blk = db.execute(
            "SELECT id FROM plan_blocks WHERE block_date=? AND start_time=? AND LOWER(TRIM(title))=LOWER(TRIM(?)) LIMIT 1",
            (target_date_str, s_t, title_cand),
        ).fetchone()
        if not existing_blk:
            db.execute(
                "INSERT INTO plan_blocks(title, block_date, start_time, end_time, notes, created_at) VALUES(?,?,?,?,?,?)",
                (title_cand, target_date_str, s_t, e_t, f"Calculado automáticamente ({item['ref_desc']})", now_iso),
            )
    db.commit()

    rel_label = (
        f"{offset_mins} min {'antes' if direction == 'before' else 'después'}"
        if offset_mins % 60 != 0
        else f"{offset_mins // 60} hora(s) {'antes' if direction == 'before' else 'después'}"
        if offset_mins > 0
        else "al terminar"
    )
    anchor_label = (
        "tu primera clase de cada día"
        if anchor_kind == "first_class"
        else "tu última clase de cada día"
        if anchor_kind == "last_class"
        else f"tu clase de {matched_subj or 'la materia'}"
    )
    lines = [f"¡Listo! Calculé y programé «{title_cand}» ({rel_label} de {anchor_label}):"]
    for item in scheduled_items:
        lines.append(f"• {item['day_label']}: {item['start_time']}–{item['end_time']} ({item['ref_desc']})")
    lines.append("Quedó guardado en tus rutinas semanales y en los bloques de tu agenda.")
    return (True, "\n".join(lines))


def is_class_delete_command(low_text: str) -> bool:
    """Return True if the normalized text is a request to remove a class/subject from the weekly schedule."""
    return bool(
        re.search(r"\b(?:elimina(?:r)?|borra(?:r)?|quita(?:r)?|suprime|suprimir)\b", low_text)
        and re.search(r"\b(?:clase|clases|materia|materias|asignatura|curso)\b", low_text)
    )


def is_class_edit_command(low_text: str, db: sqlite3.Connection | None = None) -> bool:
    """Return True if the user is asking to modify/move/reschedule an existing class or change its classroom."""
    if not low_text or is_class_delete_command(low_text):
        return False
    if re.search(r"\b(?:no\s+hay\s+clases|sin\s+clases|no\s+tengo\s+clases|cancela(?:r)?\s+(?:la\s+|mi\s+)?clase|se\s+cancelo\s+la\s+clase)\b", low_text):
        return False
    if re.search(r"\b(?:modelo|llama|ollama|qwen|clima|nivel\s+de|rutina|tarea|entrega|bloque|documento|archivo|pdf|docx)\b", low_text):
        return False
    has_edit_verb = bool(re.search(_EDIT_AGENDA_VERB_PATTERN, low_text))
    has_class_noun = bool(
        re.search(
            r"\b(?:clase|clases|materia|materias|asignatura|curso|sal[oó]n\s+de|aula\s+de|horario\s+de)\b",
            low_text,
        )
    )
    if has_edit_verb and has_class_noun:
        return True
    if re.search(r"\b(?:clase|materia)\s+de\s+.+\s+ahora\s+(?:es|sera|esta)\s+en\b", low_text):
        return True
    if has_edit_verb and db is not None:
        try:
            names = [normalize_intent_text(str(r[0])) for r in db.execute("SELECT DISTINCT name FROM classes").fetchall() if r[0]]
            if any(n and len(n) >= 4 and n in low_text for n in names):
                return True
        except Exception:
            pass
    return False


def is_class_add_command(low_text: str) -> bool:
    """Return True for any natural Spanish phrasing requesting to add/register/schedule a class or subject."""
    if not low_text or is_class_delete_command(low_text) or is_class_edit_command(low_text):
        return False
    if _parse_relative_offset_minutes(low_text) is not None:
        return False
    if re.search(r"\b(?:no\s+hay\s+clases|sin\s+clases|no\s+tengo\s+clases|cancela(?:r)?\s+(?:la\s+|mi\s+)?clase|se\s+cancelo\s+la\s+clase)\b", low_text):
        return False
    if not re.search(r"\b(?:clase|clases|materia|materias|asignatura|curso)\b", low_text):
        return False
    # Exclude pure read or analytical queries
    if re.match(r"^(?:que|cuales|cual|como|cuando|donde|a\s+que\s+hora|ver|mostrar|muestrame|dime|consulta(?:r)?|revisa(?:r)?|mis|mi\s+horario|hazme)\b", low_text):
        return False
    if is_analytical_schedule_question(low_text) or is_schedule_conflict_query(low_text):
        return False
    has_add_verb = bool(
        re.search(
            r"\b(?:agrega(?:r)?|anad(?:e|ir)|registra(?:r)?|crea(?:r)?|anota(?:r)?|pon(?:er|me)?|guarda(?:r)?|apunta(?:r)?|incluir|incluye|mete(?:r)?|programa(?:r)?|prepara(?:r|me)?|prepare|arma(?:r)?|planifica(?:r)?)\b",
            low_text,
        )
    )
    has_day_or_time = bool(
        re.search(r"\b(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo|diario|\d{1,2}:\d{2}|de\s+\d{1,2}\s+a\s+\d{1,2})\b", low_text)
    )
    has_have_verb = bool(re.search(r"\b(?:tengo|llevo|curso|mi\s+clase|mis\s+clases|nueva\s+clase|nueva\s+materia)\b", low_text))
    return has_add_verb or (has_have_verb and has_day_or_time)


def is_task_complete_command(low_text: str, db: sqlite3.Connection | None = None) -> bool:
    """Return True for any natural Spanish phrasing requesting to mark a task as completed/done (regardless of word order)."""
    if not low_text:
        return False
    # Exclude pure questions about completed tasks ("qué tareas ya completé", "cuáles tareas están hechas")
    if re.match(r"^(?:que|cuales|cual|cuantas|como\s+van|ver|mostrar|muestrame|dime)\s+(?:las\s+|mis\s+)?tareas\b", low_text):
        return False

    status_token = r"(?:hech[oa]s?|completad[oa]s?|terminad[oa]s?|list[oa]s?|entregad[oa]s?|finalizad[oa]s?|resuelt[oa]s?)"
    # 1. "marca ... como completada/hecha/terminada" or "pon ... como completada" or "da ... por terminada" (any word order!)
    if (
        re.search(r"\b(?:marca(?:r|la|las|lo|los|me)?|pon(?:er|la|las|lo|me)?|da(?:r|la|las)?|deja(?:r|la)?|pasa(?:r)?|cambia(?:r)?)\b", low_text)
        and re.search(rf"\b(?:como|por|a)\s+{status_token}\b", low_text)
    ):
        return True

    # 2. Direct completion verbs ("completa la tarea...", "completa 3 tareas...", "termina las tareas...", "tacha la tarea...", "ya hice...", "ya terminé...", "ya entregué...")
    if re.search(
        r"\b(?:completa(?:r|la|las)?|termina(?:r|la|las)?|finaliza(?:r|la|las)?|acaba(?:r)?|tacha(?:r|la|las)?|palomea(?:r)?|"
        r"ya\s+(?:hice|termine|acabe|entregue|complete|realice|cumpli|quedo)|listo\s+con)\b",
        low_text,
    ):
        if re.search(r"\b(?:tarea|tareas|pendiente|pendientes|entrega|entregas|trabajo|encargo|actividad|practica|ejercicio|lo\s+de)\b", low_text):
            return True
        if db is not None and find_best_matching_task(db, low_text, prefer_pending=True) is not None:
            return True

    # 3. Copy-pasted task line with "(completada)" or trailing "completada" / "hecha" + matching task in DB
    if re.search(rf"(?:\(\s*{status_token}\s*\)|\bcomo\s+{status_token}\b|\btarea\s+{status_token}\b)", low_text):
        if db is not None and find_best_matching_task(db, low_text, prefer_pending=True) is not None:
            return True
        if re.search(r"\b(?:tarea|tareas|entrega|pendiente)\b", low_text):
            return True

    # 4. Reopen task ("reabre la tarea...", "desmarca la tarea...")
    if re.search(r"\b(?:reabre|reabrir|desmarca(?:r)?)\b.*\b(?:tarea|tareas|pendiente|entrega)\b", low_text):
        return True

    return False


def is_task_delete_command(low_text: str, db: sqlite3.Connection | None = None) -> bool:
    if not low_text or is_task_complete_command(low_text, db=db):
        return False
    if re.search(r"\b(?:clase|clases|materia|rutina|bloque|apunte|recuerdo)\b", low_text) and not re.search(r"\b(?:tarea|tareas|pendiente|entrega|encargo)\b", low_text):
        return False
    has_del = bool(re.search(r"\b(?:elimina(?:r|la|las)?|borra(?:r|la|las)?|quita(?:r|la|las)?|suprime|suprimir|descarta(?:r)?)\b", low_text))
    if not has_del:
        return False
    if re.search(r"\b(?:tarea|tareas|pendiente|pendientes|entrega|encargo|actividad)\b", low_text):
        return True
    return bool(db is not None and find_best_matching_task(db, low_text, prefer_pending=False) is not None)


def is_task_edit_command(low_text: str, db: sqlite3.Connection | None = None) -> bool:
    """Return True if the user is asking to reschedule/postpone/modify an existing task."""
    if not low_text or is_task_complete_command(low_text, db=db) or is_task_delete_command(low_text, db=db):
        return False
    if re.search(r"\b(?:clase|clases|rutina|bloque|documento|archivo|pdf|docx)\b", low_text):
        return False
    return bool(
        re.search(_EDIT_AGENDA_VERB_PATTERN, low_text)
        and re.search(r"\b(?:tarea|tareas|pendiente|entrega|proyecto|trabajo|encargo|actividad)\b", low_text)
    )


def is_task_add_command(low_text: str) -> bool:
    if not low_text or is_task_complete_command(low_text) or is_task_delete_command(low_text) or is_task_edit_command(low_text) or is_class_add_command(low_text):
        return False
    if re.match(r"^(?:que|cuales|cual|como|ver|mostrar|muestrame|dime|mis\s+tareas|hazme)\b", low_text):
        return False
    if is_analytical_schedule_question(low_text):
        return False
    if re.search(
        r"\b(?:agrega(?:r)?|anad(?:e|ir)|registra(?:r)?|crea(?:r)?|anota(?:r)?|pon(?:er|me)?|guarda(?:r)?|apunta(?:r)?|mete(?:r)?|prepara(?:r|me)?|prepare|arma(?:r)?|planifica(?:r)?)\b.*\b(?:tarea|tareas|pendiente|entrega|trabajo|encargo|actividad)\b",
        low_text,
    ):
        return True
    if re.search(
        r"\b(?:agrega(?:r)?|anad(?:e|ir)|registra(?:r)?|anota(?:r)?|pon(?:er|me)?|guarda(?:r)?|prepara(?:r|me)?)\s+que\s+(?:tengo\s+que|debo|hay\s+que|me\s+dejaron)\b",
        low_text,
    ):
        return True
    return bool(
        re.match(
            r"^(?:recuerdame|me\s+dejaron|nos\s+dejaron|me\s+acaban\s+de\s+dejar|me\s+encargaron|tengo\s+que\s+entregar|debo\s+entregar|tengo\s+pendiente|tengo\s+una\s+tarea|nueva\s+tarea|tarea\s+de|trabajo\s+de)\b",
            low_text,
        )
    )


def is_routine_delete_command(low_text: str) -> bool:
    return bool(
        re.search(r"\b(?:elimina(?:r)?|borra(?:r)?|quita(?:r)?|desactiva(?:r)?)\b", low_text)
        and re.search(r"\brutinas?\b", low_text)
    )


def is_routine_edit_command(low_text: str) -> bool:
    """Return True if the user is asking to edit/change an existing recurring routine."""
    if not low_text or is_routine_delete_command(low_text):
        return False
    if re.search(r"\brutina\s+(?:matutina|de\s+manana)\b", low_text):
        return False
    return bool(
        re.search(_EDIT_AGENDA_VERB_PATTERN, low_text)
        and re.search(r"\brutinas?\b", low_text)
    )


def is_routine_add_command(low_text: str) -> bool:
    if not low_text or is_routine_delete_command(low_text) or is_routine_edit_command(low_text):
        return False
    if re.match(r"^(?:que|cuales|ver|mostrar|mis\s+rutinas|rutina\s+matutina|rutina\s+de\s+manana)\b", low_text):
        return False
    if re.search(r"\brutina\s+(?:matutina|de\s+manana)\b", low_text):
        return False
    return bool(
        re.search(
            r"\b(?:agrega(?:r)?|anad(?:e|ir)|crea(?:r)?|registra(?:r)?|pon(?:er|me)?|guarda(?:r)?|configura(?:r)?|anota(?:r)?|prepara(?:r|me)?|prepare|arma(?:r)?|nueva|tengo)\b.*\brutinas?\b",
            low_text,
        )
    )


def is_block_edit_command(low_text: str) -> bool:
    """Return True if the user is asking to move/reschedule an existing study block."""
    if not low_text or is_class_edit_command(low_text):
        return False
    if re.search(r"\b(?:documento|archivo|pdf|docx)\b", low_text):
        return False
    return bool(
        re.search(_EDIT_AGENDA_VERB_PATTERN, low_text)
        and re.search(r"\b(?:bloque|bloques|tiempo\s+de\s+estudio|espacio\s+de\s+estudio)\b", low_text)
    )


def is_block_add_command(low_text: str) -> bool:
    if not low_text or is_class_add_command(low_text) or is_block_edit_command(low_text):
        return False
    if re.match(r"^(?:reserva(?:r)?|bloquea(?:r)?|aparta(?:r)?|nuevo\s+bloque|bloque\s+de\s+estudio)\b", low_text):
        return True
    return bool(
        re.search(
            r"\b(?:agrega(?:r)?|anad(?:e|ir)|crea(?:r)?|registra(?:r)?|pon(?:er|me)?|agenda(?:r)?|programa(?:r)?|reserva(?:r)?|prepara(?:r|me)?|prepare|arma(?:r)?|planifica(?:r)?|haz(?:me)?|hacer)\b.*\b(?:bloque|bloques|tiempo\s+de\s+estudio|espacio\s+de\s+estudio)\b",
            low_text,
        )
    )



def _extract_file_query_and_extension(text: str, action_prefix_pattern: str) -> tuple[str, str] | None:
    """Extract safe search term and allowed extension for manual file tool prefill; reject paths and forbidden types."""
    cleaned = re.sub(action_prefix_pattern, " ", text.strip(), count=1, flags=re.IGNORECASE).strip()
    if not cleaned:
        return None
    if any(mark in cleaned for mark in ("/", "\\")) or ".." in cleaned or re.search(r"\b[A-Za-z]:", cleaned):
        return None
    forbidden_ext = re.search(r"\.(?:exe|bat|cmd|ps1|vbs|js|py|msi|scr|com|sh|dll)\b", cleaned, re.IGNORECASE)
    if forbidden_ext:
        return ("__FORBIDDEN_EXT__", forbidden_ext.group(0).casefold())
    ext_map = {
        "pdf": ".pdf",
        ".pdf": ".pdf",
        "docx": ".docx",
        ".docx": ".docx",
        "word": ".docx",
        "xlsx": ".xlsx",
        ".xlsx": ".xlsx",
        "excel": ".xlsx",
        "pptx": ".pptx",
        ".pptx": ".pptx",
        "powerpoint": ".pptx",
        "txt": ".txt",
        ".txt": ".txt",
        "texto": ".txt",
        "markdown": ".md",
        ".markdown": ".markdown",
        "md": ".md",
        ".md": ".md",
    }
    chosen_ext = "Todos"
    for token, mapped in ext_map.items():
        if re.search(r"(?:^|\b)" + re.escape(token) + r"(?:\b|$)", cleaned, re.IGNORECASE):
            chosen_ext = mapped
            cleaned = re.sub(r"(?:^|\b)" + re.escape(token) + r"(?:\b|$)", " ", cleaned, count=1, flags=re.IGNORECASE)
            break
    cleaned = re.sub(
        r"\b(?:mi|mis|el|la|los|las|un|una|documento|documentos|archivo|archivos|llamado|llamada|sobre|de|del|en|carpeta)\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-'\"“”")
    if not cleaned and chosen_ext != "Todos":
        cleaned = chosen_ext.lstrip(".")
    if not cleaned:
        return None
    return (cleaned[:120], chosen_ext)


def classify_local_natural_intent(text: str, today: date | None = None) -> dict | None:
    """Deterministic local Spanish NLU router combining Viernes's natural queries with CLARA's safe drafts."""
    today = today or date.today()
    raw = str(text or "").strip()
    if not raw:
        return None
    low = normalize_intent_text(raw)
    low_words = re.sub(r"[.,;:]+", " ", low)
    low_words = re.sub(r"\s+", " ", low_words).strip()

    blocked_reason = is_blocked_unsafe_request(raw)
    if blocked_reason:
        return {"intent": "blocked_unsafe", "response": blocked_reason}

    if is_negated_or_informational_query(raw):
        return {
            "intent": "informational",
            "response": (
                "Entendido: no inicié ninguna búsqueda, apertura, movimiento ni guardado. "
                "En Clara todas las acciones sobre archivos eligen carpeta cada vez, solo admiten PDF, DOCX, XLSX, PPTX, TXT y Markdown, "
                "y piden confirmación individual antes de abrir o mover un archivo."
            ),
        }

    if low_words in ("repite", "repetir", "repite eso", "repite la ultima respuesta", "repetir ultima respuesta", "leer ultima respuesta", "leelo en voz alta"):
        return {"intent": "repeat_last"}

    if any(phrase in low_words for phrase in ("diagnostico de voz", "diagnosticar voz", "probar voz", "prueba de voz", "estado de la voz", "estado de voz")):
        return {"intent": "voice_diagnostics"}

    if any(phrase in low_words for phrase in ("que puedes hacer", "que sabes hacer", "ayuda", "comandos", "funciones disponibles", "como te uso")):
        return {"intent": "help"}

    if any(phrase in low_words for phrase in ("que sigue", "siguiente pendiente", "proximo compromiso", "proxima clase", "siguiente clase", "que toca ahora", "que tengo ahora")):
        return {"intent": "next_commitment"}

    if (
        is_analytical_schedule_question(low_words)
        or is_schedule_conflict_query(low_words)
        or is_weekly_grid_query(low_words)
        or parse_pomodoro_command(raw) is not None
        or parse_and_execute_math_from_chat(raw) is not None
        or extract_web_research_query(raw) is not None
    ):
        return None

    is_mutation_verb = bool(
        re.search(
            r"\b(?:agrega|agregar|anade|anadir|crea|crear|edita|editar|registra|registrar|elimina|eliminar|borra|borrar|quita|quitar|nueva|nuevo|configura|configurar|modificar|modifica|cambiar|cambia|mueve|mover|pasa|pasar|pospon|posponer|aplaza|aplazar|reprograma|reprogramar|actualiza|actualizar|corrige|corregir|pon|poner|ponme|guarda|guardar|anota|anotar|apunta|apuntar|recuerda|memoriza|olvida|autoriza|autorizar)\b",
            low_words,
        )
    )

    if not is_mutation_verb and (
        any(phrase in low_words for phrase in ("rutina de manana", "rutina matutina", "resumen matutino", "arranca mi dia", "buenos dias clara", "buen dia clara"))
        or low_words == "buenos dias"
    ):
        return {"intent": "morning_brief"}

    if any(phrase in low_words for phrase in ("organiza la tarde", "organizar la tarde", "organiza mi tarde", "organizar mi tarde", "planifica la tarde", "planificar la tarde", "ayudame a organizar la tarde", "ayudame a planear la tarde")):
        return {"intent": "afternoon_plan"}

    if not is_mutation_verb and any(word in low_words for word in ("noticias", "titulares", "que hay de nuevo en las noticias", "ultimas noticias")):
        topic = None
        topic_keywords = {
            "Tecnología": ("tecnologia", "tech", "informatica", "computacion", "ia"),
            "Ciencia": ("ciencia", "cientifica", "espacio", "medicina"),
            "Educación": ("educacion", "universidad", "escuela"),
            "Deportes": ("deportes", "deporte", "futbol"),
            "General": ("general",),
        }
        for topic_label, keywords in topic_keywords.items():
            if any(re.search(r"\b" + kw + r"\b", low_words) for kw in keywords):
                topic = topic_label
                break
        return {"intent": "news_query", "topic": topic}

    if not is_mutation_verb and any(phrase in low_words for phrase in ("clima", "como esta el tiempo", "como esta el clima", "temperatura", "va a llover", "pronostico del tiempo")):
        return {"intent": "weather_query"}

    if not is_mutation_verb and any(phrase in low_words for phrase in ("mis rutinas", "rutinas activas", "que rutinas tengo", "ver rutinas")):
        return {"intent": "routines_query"}

    if not is_mutation_verb and any(phrase in low_words for phrase in ("mis clases", "horario de clases", "que clases tengo", "cuales son mis clases")):
        target = None
        if "manana" in low_words:
            target = (today + timedelta(days=1)).isoformat()
        elif "hoy" in low_words:
            target = today.isoformat()
        return {"intent": "classes_query", "date": target}

    low_no_greeting = re.sub(
        r"^(?:hola(?:\s+clara(?:-v|\s+v)?)?|buenos\s+dias|buen\s+dia|buenas(?:\s+tardes|\s+noches)?|oye\s+clara|clara(?:-v|\s+v)?)[,.;:\s-]+",
        "",
        low,
    ).strip()
    raw_no_greeting = re.sub(
        r"^(?:hola(?:\s+clara(?:-v|\s+v)?)?|buenos\s+d[ií]as|buen\s+d[ií]a|buenas(?:\s+tardes|\s+noches)?|oye\s+clara|clara(?:-v|\s+v)?)[,.;:\s-]+",
        "",
        raw,
        flags=re.IGNORECASE,
    ).strip() or raw

    if re.search(r"^(?:inventaria|inventariar|inventario de|ver archivos y carpetas|explorar documentos de)\b", low_no_greeting):
        return {"intent": "file_inventory", "recursive": "recursiv" in low_no_greeting}

    file_action_patterns = (
        ("file_search", r"^(?:por favor\s+)?(?:busca|buscar|encuentra|encontrar|localiza|localizar)\s+(?:mi|mis|el|la|un|una)?\s*(?:documento|archivo|pdf|docx|word|xlsx|excel|pptx|txt|markdown|md)\b"),
        ("file_open", r"^(?:por favor\s+)?(?:abre|abrir)\s+(?:mi|mis|el|la|un|una)?\s*(?:documento|archivo|pdf|docx|word|xlsx|excel|pptx|txt|markdown|md)\b"),
        ("file_move", r"^(?:por favor\s+)?(?:mueve|mover)\s+(?:mi|mis|el|la|un|una)?\s*(?:documento|archivo|pdf|docx|word|xlsx|excel|pptx|txt|markdown|md)\b"),
    )
    for intent_name, pat in file_action_patterns:
        if re.search(pat, low_no_greeting):
            extracted = _extract_file_query_and_extension(raw_no_greeting, pat)
            if extracted is not None:
                query, ext = extracted
                if query == "__FORBIDDEN_EXT__":
                    return {
                        "intent": "blocked_unsafe",
                        "response": f"El formato {ext} no está permitido. Clara solo busca, abre o mueve documentos PDF, DOCX, XLSX, PPTX, TXT y Markdown, excluyendo scripts y ejecutables.",
                    }
                return {"intent": intent_name, "query": query, "extension": ext}

    if "semana" in low_words and any(word in low_words for word in ("agenda", "horario", "que tengo", "pendientes")):
        return {"intent": "week_agenda"}

    if any(phrase in low_words for phrase in ("como va mi dia", "resumen del dia", "informe del dia", "estado del dia")):
        return {"intent": "agenda_query", "date": today.isoformat()}

    # Conversación natural local e inmediata (saludos, estado, identidad, fecha/hora, agradecimientos y despedidas)
    if low_words in (
        "quien eres", "que eres", "como te llamas", "cual es tu nombre",
        "hola quien eres", "dime quien eres", "presentate",
    ):
        return {
            "intent": "general",
            "response": (
                "Soy CLARA-V (Clara Viernes), tu asistente personal local-first en español. "
                "Organizo tu agenda, clases, tareas y rutinas localmente en tu equipo, leo resúmenes en voz alta y solo uso Internet para titulares RSS y clima."
            ),
        }

    if low_words in ("que hora es", "dime la hora", "hora actual", "tienes la hora", "me dices la hora", "que hora tienes"):
        return {
            "intent": "general",
            "response": f"Son las {datetime.now().strftime('%H:%M')} (hora local de tu equipo).",
        }

    if low_words in ("que dia es hoy", "que fecha es hoy", "fecha de hoy", "cual es la fecha de hoy", "en que dia estamos", "hoy que dia es"):
        weekday_label = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")[today.weekday()]
        return {
            "intent": "general",
            "response": f"Hoy es {weekday_label}, {today.strftime('%d/%m/%Y')} ({today.isoformat()}).",
        }

    if low_words in (
        "hola", "hola clara", "hola clara v", "hola clara-v", "hola viernes",
        "hola que haces", "hola clara que haces", "que haces", "que estas haciendo", "en que estas",
        "hola como estas", "hola que tal", "como estas", "que tal", "como vas", "como te va", "todo bien",
        "buenas", "buenas tardes", "buenas noches", "hola buenas", "hola buenas tardes", "hola buenas noches",
        "buenas tardes clara", "buenas noches clara",
    ):
        if any(phrase in low_words for phrase in ("que haces", "que estas haciendo", "en que estas")):
            return {
                "intent": "general",
                "response": (
                    "¡Hola! Estoy activa y lista en modo local-first en tu equipo. "
                    "Puedo decirte qué sigue hoy, revisar tu agenda, clases, tareas o rutinas, consultar el clima de Colima y titulares, "
                    "o buscar documentos con tu confirmación. ¿En qué te ayudo?"
                ),
            }
        return {
            "intent": "general",
            "response": (
                "¡Hola! Soy CLARA-V y estoy lista en tu equipo. "
                "Puedes preguntarme “¿qué sigue?”, “¿qué tengo hoy?”, “mis clases”, “clima”, “noticias” o pedirme que prepare una tarea o bloque. ¿Qué necesitas hoy?"
            ),
        }

    if low_words in ("gracias", "muchas gracias", "mil gracias", "te lo agradezco", "perfecto gracias", "ok gracias", "vale gracias", "listo gracias", "gracias clara"):
        return {
            "intent": "general",
            "response": "¡Con gusto! Aquí sigo al pendiente en tu equipo por si necesitas revisar tu agenda, tareas o cualquier otra consulta.",
        }

    if low_words in ("adios", "hasta luego", "nos vemos", "hasta manana", "chao", "bye", "hasta pronto", "adios clara"):
        return {
            "intent": "general",
            "response": "¡Hasta luego! Tus tareas, clases y agenda quedan resguardadas localmente en tu equipo.",
        }

    return None


def resolve_vosk_model_path(base_dir: Path | None = None) -> Path:
    """Locate the local Spanish Vosk model across CLARA_Unificada, Bienvenido_Señor, or CLARA_v1.27.4."""
    base = Path(base_dir or APP_BASE_DIR)
    candidates = (
        base / "models" / "vosk-model-small-es-0.42",
        base / "vosk-model-small-es-0.42",
        base.parent / "Bienvenido_Señor" / "models" / "vosk-model-small-es-0.42",
        base.parent / "Bienvenido_Señor" / "vosk-model-small-es-0.42",
        base.parent / "CLARA_v1.27.4" / "models" / "vosk-model-small-es-0.42",
    )
    for cand in candidates:
        try:
            if cand.is_dir():
                return cand
        except OSError:
            continue
    return base / "models" / "vosk-model-small-es-0.42"


def _boost_pcm16_gain(
    raw_pcm: bytes,
    target_peak: int = 24000,
    max_gain: float = 12.0,
) -> tuple[bytes, int, float]:
    """Normalize quiet 16-bit mono PCM audio in RAM so low-volume Windows microphones are recognized accurately."""
    if not raw_pcm or len(raw_pcm) < 4:
        return (raw_pcm, 0, 1.0)
    usable_len = len(raw_pcm) - (len(raw_pcm) % 2)
    count = usable_len // 2
    samples = struct.unpack(f"<{count}h", raw_pcm[:usable_len])
    peak = max((abs(s) for s in samples), default=0)
    if peak <= 30 or peak >= 18000:
        return (raw_pcm[:usable_len], peak, 1.0)
    gain = min(float(max_gain), float(target_peak) / float(peak))
    if gain <= 1.05:
        return (raw_pcm[:usable_len], peak, 1.0)
    boosted = [max(-32767, min(32767, int(round(s * gain)))) for s in samples]
    return (struct.pack(f"<{count}h", *boosted), peak, round(gain, 2))


def _downsample_pcm16_mono(raw_pcm: bytes, src_rate: int, dst_rate: int = 16000) -> bytes:
    """Resample 16-bit signed mono PCM from src_rate (e.g. 44100/48000 Hz) to dst_rate (16000 Hz)."""
    if not raw_pcm or src_rate <= 0 or dst_rate <= 0 or int(src_rate) == int(dst_rate):
        return raw_pcm
    usable_len = len(raw_pcm) - (len(raw_pcm) % 2)
    in_count = usable_len // 2
    if in_count < 2:
        return raw_pcm[:usable_len]
    in_samples = struct.unpack(f"<{in_count}h", raw_pcm[:usable_len])
    ratio = float(src_rate) / float(dst_rate)
    out_count = max(1, int(in_count / ratio))
    out_samples = []
    for i in range(out_count):
        src_pos = i * ratio
        idx = int(src_pos)
        if idx >= in_count - 1:
            out_samples.append(in_samples[-1])
        else:
            frac = src_pos - idx
            val = int(round(in_samples[idx] * (1.0 - frac) + in_samples[idx + 1] * frac))
            out_samples.append(max(-32767, min(32767, val)))
    return struct.pack(f"<{len(out_samples)}h", *out_samples)


def accumulate_vosk_stream_chunk(
    recognizer,
    chunk: bytes,
    segments: list[str],
    last_partial_holder: list[str],
) -> str | None:
    """Feed a PCM chunk into Vosk and preserve every utterance Result() across pauses plus live PartialResult()."""
    if not chunk:
        return None
    if recognizer.AcceptWaveform(chunk):
        try:
            data = json.loads(recognizer.Result() or "{}")
        except Exception:
            data = {}
        seg = str(data.get("text") or "").strip()
        if seg:
            segments.append(seg)
            if last_partial_holder:
                last_partial_holder[0] = ""
            return seg
        return None
    try:
        pdata = json.loads(recognizer.PartialResult() or "{}")
    except Exception:
        pdata = {}
    part = str(pdata.get("partial") or "").strip()
    if part:
        if last_partial_holder:
            last_partial_holder[0] = part
        return part
    return None


def finalize_vosk_recognition(
    recognizer,
    segments: list[str],
    last_partial: str = "",
) -> str:
    """Combine all accumulated utterance Results with FinalResult() and fallback to PartialResult() if stopped mid-word."""
    try:
        fdata = json.loads(recognizer.FinalResult() or "{}")
    except Exception:
        fdata = {}
    final_seg = str(fdata.get("text") or "").strip()
    if final_seg:
        segments.append(final_seg)
    elif last_partial and last_partial.strip():
        clean_part = last_partial.strip()
        if not segments or clean_part.casefold() != segments[-1].strip().casefold():
            segments.append(clean_part)
    return " ".join(s.strip() for s in segments if s and s.strip()).strip()


def recognize_pcm_with_vosk_second_pass(
    vosk_model,
    raw_pcm: bytes,
    sample_rate: int = 16000,
    recognizer_cls=None,
) -> str:
    """Re-run Vosk over gain-boosted PCM with trailing silence when the first live pass returned empty."""
    if not raw_pcm or len(raw_pcm) < 800 or vosk_model is None:
        return ""
    boosted_pcm, _peak, _gain = _boost_pcm16_gain(raw_pcm)
    padded_pcm = boosted_pcm + (b"\x00\x00" * int(sample_rate * 0.45))
    if recognizer_cls is None:
        from vosk import KaldiRecognizer as recognizer_cls
    rec2 = recognizer_cls(vosk_model, sample_rate)
    segs2: list[str] = []
    partial2 = [""]
    step = 4000
    for offset in range(0, len(padded_pcm), step):
        accumulate_vosk_stream_chunk(rec2, padded_pcm[offset : offset + step], segs2, partial2)
    return finalize_vosk_recognition(rec2, segs2, partial2[0])


def recognize_pcm_with_viernes_backends(
    raw_pcm: bytes,
    sample_rate: int = 16000,
    sr_module=None,
) -> str:
    """Fallback speech recognition from Viernes (speech_input.py: Whisper -> Vosk -> Google es-MX) over captured PCM."""
    if not raw_pcm or len(raw_pcm) < 800:
        return ""
    if sr_module is None:
        if importlib.util.find_spec("speech_recognition") is None:
            return ""
        import speech_recognition as sr_module
    boosted_pcm, _peak, _gain = _boost_pcm16_gain(raw_pcm)
    try:
        recognizer = sr_module.Recognizer()
        audio_data = sr_module.AudioData(boosted_pcm, int(sample_rate), 2)
    except Exception:
        return ""
    for method_name, kwargs in (
        ("recognize_whisper", {"language": "spanish"}),
        ("recognize_vosk", {"language": "es"}),
        ("recognize_google", {"language": "es-MX"}),
    ):
        fn = getattr(recognizer, method_name, None)
        if not callable(fn):
            continue
        try:
            res = fn(audio_data, **kwargs)
            if isinstance(res, str) and res.startswith("{"):
                try:
                    res = json.loads(res).get("text", "")
                except Exception:
                    pass
            clean = str(res or "").strip()
            if clean:
                return clean
        except Exception:
            continue
    return ""


class AssistantApp(tk.Tk):
    def __init__(self) -> None:
        if sys.platform == "win32":
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass
        super().__init__()
        self.title(APP_NAME)
        self._apply_adaptive_geometry()
        self.configure(bg="#07111f")
        self.db = connect_db()
        self.settings = load_settings()
        self.ai_results: queue.Queue = queue.Queue()
        self.vt_busy = False
        self.local_scan_cancel_event: threading.Event | None = None
        self.local_scan_running = False
        self.vt_cancel_event = threading.Event()
        self.vt_last_request = 0.0
        self.tray_icon = None
        self.reminders_paused = reminder_pause_active(self.settings)
        self._force_quit = False
        self.ai_history: list[dict[str, str]] = []
        self.ai_busy = False
        self.ollama_request_id = 0
        self.cancel_event = threading.Event()
        self.active_response = None
        self.response_lock = threading.Lock()
        self.stream_text = ""
        self.stream_user_text = ""
        self.stream_started = False
        self.structured_intent_mode = False
        self.tts_active = False
        self.tts_cancel_event = threading.Event()
        self.voice_active = False
        self.voice_stop = threading.Event()
        self.vosk_model = None
        self.last_assistant_response = ""
        self._pending_morning_speech = ""
        self.current_auth_user: str | None = None
        self.current_auth_level: int = 0
        self._active_vault_passphrase: str = ""
        self._pending_protected_action: dict[str, object] | None = None
        self.pomodoro_active: bool = False
        self.pomodoro_paused: bool = False
        self.pomodoro_remaining_seconds: int = 0
        self.pomodoro_total_minutes: int = 0
        self.pomodoro_label: str = ""
        self.pomodoro_subject: str | None = None
        self._setup_style()
        self._build_ui()
        if sys.platform == "win32":
            # Start maximized on Windows so the chat composer and lower task controls are visible at common DPI scales.
            try:
                self.state("zoomed")
            except tk.TclError:
                pass
        self._start_tray_icon_if_enabled()
        self.bind_all("<Escape>", lambda _event: self.emergency_stop())
        self.refresh_tasks()
        self.load_chat_history()
        self.append_chat("Asistente", "¡Hola! Soy CLARA-V (Clara Viernes). Puedo organizar tu agenda, clases, tareas y rutinas localmente, decirte qué sigue hoy, leer resúmenes de noticias/agenda en voz alta y conversar con Ollama local cuando esté conectado (sin ejecutar acciones automáticas).", speak=False)
        self.after(1500, self.check_reminders)
        self.after(200, self.process_ai_results)
        self.after(600, self.refresh_ollama_models)

    def _apply_adaptive_geometry(self) -> None:
        try:
            sw = int(self.winfo_screenwidth())
            sh = int(self.winfo_screenheight())
        except Exception:
            sw, sh = 1280, 820
        spec = compute_adaptive_window_geometry(sw, sh)
        self.minsize(int(spec["min_width"]), int(spec["min_height"]))
        self.geometry(str(spec["geometry"]))

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        # The clam theme honors the palette consistently on Windows and in tests.
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        bg, card, panel = "#07111f", "#0d1b2d", "#10243a"
        text, muted, line = "#eff8ff", "#91aabd", "#29445a"
        style.configure("TFrame", background=bg)
        style.configure("Card.TFrame", background=card)
        style.configure("TLabel", background=bg, foreground=text, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=bg, font=("Segoe UI", 23, "bold"), foreground=text)
        style.configure("Subtitle.TLabel", background=bg, font=("Segoe UI", 10), foreground=muted)
        style.configure("CardTitle.TLabel", background=card, font=("Segoe UI", 13, "bold"), foreground=text)
        style.configure("Accent.TButton", background="#1b7c8c", foreground="#ffffff", bordercolor="#58d6d8", font=("Segoe UI", 10, "bold"), padding=(12, 8), focuscolor="#60e2df")
        style.map("Accent.TButton", background=[("disabled", "#253b4b"), ("pressed", "#145866"), ("active", "#286f9f")], foreground=[("disabled", "#91aabd")])
        style.configure("TButton", background="#13283d", foreground=text, bordercolor=line, font=("Segoe UI", 10), padding=(10, 7), focuscolor="#60e2df")
        style.map("TButton", background=[("disabled", "#102033"), ("pressed", "#10243a"), ("active", "#1a3850")], foreground=[("disabled", "#748b9d")])
        style.configure("Danger.TButton", background="#9f2f3b", foreground="#ffffff", bordercolor="#e05b62", padding=(10, 7))
        style.map("Danger.TButton", background=[("active", "#c43b47"), ("pressed", "#7f202c")])
        style.configure("TEntry", fieldbackground="#081624", background="#081624", foreground=text, bordercolor=line, lightcolor=line, darkcolor=line, padding=7)
        style.map("TEntry", bordercolor=[("focus", "#60e2df")], lightcolor=[("focus", "#60e2df")], darkcolor=[("focus", "#60e2df")])
        style.configure("TCombobox", fieldbackground="#081624", background=panel, foreground=text, arrowcolor=text, bordercolor=line, lightcolor=line, darkcolor=line, padding=5)
        style.map("TCombobox", fieldbackground=[("readonly", "#081624"), ("disabled", "#102033")], foreground=[("readonly", text), ("disabled", muted)], selectbackground=[("readonly", "#1b4961")], selectforeground=[("readonly", text)])
        style.configure("Treeview", rowheight=32, font=("Segoe UI", 10), background=card, fieldbackground=card, foreground=text, bordercolor=line, lightcolor=line, darkcolor=line)
        style.map("Treeview", background=[("selected", "#1b4961")], foreground=[("selected", "#ffffff")])
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background=panel, foreground=muted, relief="flat", padding=(8, 7))
        style.map("Treeview.Heading", background=[("active", "#1b3850")], foreground=[("active", text)])
        style.configure("TLabelframe", background=bg, foreground=text, bordercolor=line)
        style.configure("TLabelframe.Label", background=bg, foreground="#60e2df", font=("Segoe UI", 10, "bold"))
        style.configure("TCheckbutton", background=bg, foreground=text, focuscolor="#60e2df")
        style.map("TCheckbutton", background=[("active", bg)], foreground=[("disabled", muted)])
        style.configure("TSeparator", background=line)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=18)
        root.pack(fill="both", expand=True)
        header = ttk.Frame(root)
        header.pack(fill="x", pady=(0, 10))
        brand = ttk.Frame(header)
        brand.pack(side="left", fill="x", expand=True)
        ttk.Label(brand, text="CLARA-V · Clara Viernes · tu espacio personal", style="Title.TLabel").pack(anchor="w")
        ttk.Label(brand, text="Centro Local de Asistencia, Rutinas y Agenda · Edición Viernes", style="Subtitle.TLabel").pack(anchor="w", pady=(1, 0))
        ttk.Label(brand, text=f"{date.today().strftime('%d/%m/%Y')}  ·  Datos guardados localmente en esta computadora", style="Subtitle.TLabel").pack(anchor="w", pady=(1, 0))
        self.auth_status_label = ttk.Label(
            brand,
            text="🔐 Nivel de acceso: Invitado (Nivel 0) · escribe o dicta «Usuario Contraseña» para elevar permisos",
            style="Subtitle.TLabel",
        )
        self.auth_status_label.pack(anchor="w", pady=(1, 0))
        self.stop_button = tk.Button(header, text="⛔ DETENER AHORA  ·  Esc", command=self.emergency_stop, bg="#b42318", fg="white", activebackground="#912018", activeforeground="white", relief="flat", font=("Segoe UI", 10, "bold"), padx=14, pady=8, takefocus=True, highlightthickness=2, highlightbackground="#e05b62", highlightcolor="#ffffff")
        self.stop_button.pack(side="right", anchor="ne", padx=(12, 0), pady=(4, 4))
        toolbar = ttk.Frame(root)
        toolbar.pack(fill="x", pady=(0, 10))
        toolbar_actions = (
            # Fila 1: Agenda, Estudio y Utilidades Diarias
            ("☀ Rutina de mañana", self.show_morning_briefing, "Accent.TButton"),
            ("⏭ ¿Qué sigue?", self.show_next_commitment, "TButton"),
            ("📅 Agenda semanal", self.open_week_agenda, "TButton"),
            ("🗓 Cuadrícula semanal", self.open_weekly_grid_schedule, "TButton"),
            ("⏱ Pomodoro", self.open_pomodoro_dialog, "TButton"),
            ("📓 Apuntes", self.open_subject_notebook, "TButton"),
            ("🧮 Calculadora / 🌐 Web", self.open_math_and_web_tools, "TButton"),
            # Fila 2: Seguridad, Sistema y Configuración
            ("🔐 Niveles y Bóveda", self.open_security_levels_vault, "TButton"),
            ("🔒 Bloquear sesión", self.lock_security_session, "TButton"),
            ("🔔 Historial de avisos", self.open_reminder_history, "TButton"),
            ("🩺 Diagnóstico", self.open_diagnostics, "TButton"),
            ("🛡 Seguridad", self.open_security, "TButton"),
            ("⚙ Preferencias", self.open_settings, "TButton"),
            ("💾 Copias de seguridad", self.open_backup_tools, "TButton"),
        )
        toolbar_buttons: list[ttk.Button] = []
        for label, command, style_name in toolbar_actions:
            btn = ttk.Button(toolbar, text=label, command=command, style=style_name)
            toolbar_buttons.append(btn)

        self._toolbar_cols = 0

        def _reflow_toolbar(event=None) -> None:
            avail_w = int(getattr(event, "width", 0) or toolbar.winfo_width() or 1220)
            cols = max(3, min(7, avail_w // 168))
            if cols == getattr(self, "_toolbar_cols", 0):
                return
            self._toolbar_cols = cols
            for c_idx in range(8):
                toolbar.grid_columnconfigure(c_idx, weight=1 if c_idx < cols else 0)
            for idx, btn_widget in enumerate(toolbar_buttons):
                r_idx, c_idx = divmod(idx, cols)
                btn_widget.grid(row=r_idx, column=c_idx, sticky="ew", padx=3, pady=3)

        _reflow_toolbar()
        toolbar.bind("<Configure>", _reflow_toolbar)

        footer = ttk.Frame(root)
        footer.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Label(footer, text="Avisos de tareas/clases programados con Windows; sesión de usuario iniciada requerida.", style="Subtitle.TLabel").pack(anchor="w")

        body = ttk.Frame(root)
        body.pack(side="top", fill="both", expand=True)
        left = ttk.Frame(body, style="Card.TFrame", padding=14)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right = ttk.Frame(body, style="Card.TFrame", padding=14)
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))

        left_heading = ttk.Frame(left, style="Card.TFrame")
        left_heading.pack(fill="x")
        ttk.Label(left_heading, text="Mis tareas", style="CardTitle.TLabel").pack(side="left", anchor="w")
        ttk.Button(left_heading, text="📚 Mis clases · agregar / editar", command=self.open_classes).pack(side="right", padx=(8, 0))
        ttk.Label(left, text="Organiza pendientes y fechas importantes.", background="#0d1b2d", foreground="#91aabd").pack(anchor="w", pady=(4, 6))
        local_tools_row = ttk.Frame(left, style="Card.TFrame")
        local_tools_row.pack(fill="x", pady=(0, 8))
        local_tools_row.grid_columnconfigure((0, 1, 2), weight=1)
        ttk.Button(local_tools_row, text="📂 Documentos / carpeta", command=self.open_local_file_tools).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(local_tools_row, text="🚀 Apps autorizadas", command=self.open_application_manager).grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Button(local_tools_row, text="🛡 Privacidad y permisos", command=self.open_privacy_center).grid(row=0, column=2, sticky="ew", padx=(4, 0))
        self.task_tree = ttk.Treeview(left, columns=("task", "due", "priority", "status"), show="headings", selectmode="browse")
        for key, label, width, anchor in (("task", "Tarea", 220, "w"), ("due", "Fecha / hora", 130, "center"), ("priority", "Prioridad", 85, "center"), ("status", "Estado", 80, "center")):
            self.task_tree.heading(key, text=label)
            self.task_tree.column(key, width=width, anchor=anchor)
        self.task_tree.bind("<Double-1>", lambda _event: self.toggle_selected())
        buttons = ttk.Frame(left, style="Card.TFrame")
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="+ Agregar tarea", style="Accent.TButton", command=self.add_task).pack(side="left")
        ttk.Button(buttons, text="Rutinas", command=self.open_routines).pack(side="left", padx=8)
        ttk.Button(buttons, text="Memoria", command=self.open_memories).pack(side="left")
        task_actions = ttk.Frame(left, style="Card.TFrame")
        task_actions.pack(fill="x", pady=(8, 0))
        ttk.Button(task_actions, text="Detalles", command=self.show_task_details).pack(side="left", padx=(0, 8))
        ttk.Button(task_actions, text="Editar", command=self.edit_selected).pack(side="left")
        ttk.Button(task_actions, text="Marcar / reabrir", command=self.toggle_selected).pack(side="left", padx=8)
        ttk.Button(task_actions, text="Posponer 10 min", command=self.snooze_selected).pack(side="left")
        ttk.Button(task_actions, text="Eliminar", command=self.delete_selected).pack(side="left", padx=8)
        # Pin task controls above the expanding list so they remain visible at short heights and high DPI.
        self.task_tree.pack(fill="both", expand=True, pady=(10, 0))

        # Grid reserves rows for the voice controls and text composer. The growing
        # transcript can shrink instead of pushing the input below the screen edge.
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(4, weight=1, minsize=72)
        chat_banner = ttk.Frame(right, style="Card.TFrame")
        chat_banner.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        chat_banner_text = ttk.Frame(chat_banner, style="Card.TFrame")
        chat_banner_text.pack(side="left", fill="x", expand=True, anchor="w")
        ttk.Label(chat_banner_text, text="Chat de texto con Clara", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(chat_banner_text, text="Escribe en el campo inferior y pulsa Enviar. Ollama conversa localmente; no recibe tus tareas o clases automáticamente.", background="#0d1b2d", foreground="#91aabd", wraplength=320).pack(anchor="w", pady=(4, 8))
        self.sphere_visual = ClaraSphere(chat_banner, width=150, height=112, bg="#071521")
        self.sphere_visual.pack(side="right", padx=(6, 0), anchor="e")
        self.sphere_state_label = ttk.Label(right, text="En espera · esfera compacta", background="#0d1b2d", foreground="#91aabd")
        self.sphere_state_label.grid(row=1, column=0, sticky="w", pady=(0, 6))
        model_row = ttk.Frame(right, style="Card.TFrame")
        model_row.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(model_row, text="Modelo:", background="#0d1b2d").pack(side="left", padx=(0, 6))
        self.model_var = tk.StringVar(value="")
        self.model_combo = ttk.Combobox(model_row, textvariable=self.model_var, values=(), state="readonly", width=20)
        self.model_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(model_row, text="Detectar Ollama", command=self.refresh_ollama_models).pack(side="left", padx=(8, 0))
        ttk.Button(model_row, text="⬇ Descargar llama3.2…", style="Accent.TButton", command=self.open_ollama_model_downloader).pack(side="left", padx=(6, 0))
        self.ollama_status = ttk.Label(right, text="IA local inactiva · tareas y recordatorios siguen funcionando", background="#0d1b2d", foreground="#91aabd")
        self.ollama_status.grid(row=3, column=0, sticky="w", pady=(0, 6))
        self.chat_log = tk.Text(right, height=3, wrap="word", state="disabled", relief="flat", bg="#081624", fg="#eff8ff", insertbackground="#eff8ff", selectbackground="#1b4961", selectforeground="#ffffff", padx=12, pady=10, font=("Segoe UI", 10))
        self.chat_log.grid(row=4, column=0, sticky="nsew")
        self.chat_log.tag_configure("speaker", font=("Segoe UI", 9, "bold"), foreground="#60e2df", spacing1=8)
        voice_row = ttk.Frame(right, style="Card.TFrame")
        voice_row.grid(row=5, column=0, sticky="ew", pady=(8, 0))
        voice_row.grid_columnconfigure((0, 1, 2), weight=1)
        self.voice_button = ttk.Button(voice_row, text="🎙 Pulsar para hablar", command=self.toggle_voice)
        self.voice_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.repeat_voice_button = ttk.Button(voice_row, text="🔊 Repetir última respuesta", command=self.speak_last_response)
        self.repeat_voice_button.grid(row=0, column=1, sticky="ew", padx=4)
        self.voice_diag_button = ttk.Button(voice_row, text="🩺 Diagnóstico de voz", command=self.open_voice_diagnostics)
        self.voice_diag_button.grid(row=0, column=2, sticky="ew", padx=(4, 0))
        self.voice_status = ttk.Label(right, text="Micrófono apagado", background="#0d1b2d", foreground="#91aabd")
        self.voice_status.grid(row=6, column=0, sticky="w", pady=(3, 0))
        self.chat_prompt_label = ttk.Label(right, text="Escribe un mensaje para Clara:", background="#0d1b2d", foreground="#eff8ff")
        self.chat_prompt_label.grid(row=7, column=0, sticky="w", pady=(6, 3))
        entry_row = ttk.Frame(right, style="Card.TFrame")
        entry_row.grid(row=8, column=0, sticky="ew")
        self.chat_input = ttk.Entry(entry_row)
        self.chat_input.pack(side="left", fill="x", expand=True, ipady=7)
        self.chat_input.bind("<Return>", lambda _event: self.send_chat())
        self.send_button = ttk.Button(entry_row, text="Enviar", style="Accent.TButton", command=self.send_chat)
        self.send_button.pack(side="left", padx=(8, 0))

    def _update_auth_status_label(self) -> None:
        user = getattr(self, "current_auth_user", None)
        lvl = coerce_security_level(getattr(self, "current_auth_level", 0), default=0)
        spec = SECURITY_LEVEL_SPECS[lvl]
        if user:
            text = f"🔓 Sesión activa: {user} · {spec['short']} ({spec['name']})"
        else:
            text = "🔐 Nivel de acceso: Invitado (Nivel 0) · escribe o dicta «Usuario Contraseña» para elevar permisos"
        label_widget = getattr(self, "auth_status_label", None)
        if label_widget is not None:
            try:
                label_widget.configure(text=text)
            except Exception:
                pass

    def lock_security_session(self) -> None:
        """Lock the active session back to Guest Level 0 and clear in-memory vault keys."""
        self.current_auth_user = None
        self.current_auth_level = 0
        self._active_vault_passphrase = ""
        self._pending_protected_action = None
        self._update_auth_status_label()
        self.append_chat(
            "Asistente",
            "🔒 Sesión bloqueada en modo Invitado (Nivel 0). Para revisar secretos encriptados, explorar carpetas/archivos o ejecutar acciones destructivas, Clara solicitará de quién es la orden (usuario y contraseña).",
        )

    def require_permission(self, action_key: str, pending_callable=None) -> bool:
        """Check if current session has clearance for action_key; if not, ask who is giving the order."""
        user = getattr(self, "current_auth_user", None)
        lvl = coerce_security_level(getattr(self, "current_auth_level", 0), default=0)
        decision = check_action_permission(self.db, action_key, user, lvl)
        if decision["allowed"]:
            return True
        self._pending_protected_action = {
            "action_key": action_key,
            "action_label": decision["action_label"],
            "required_level": decision["required_level"],
            "callback": pending_callable,
        }
        self.append_chat("Asistente", str(decision["message"]))
        return False

    def _present_decrypted_secrets_in_chat(self) -> str:
        passphrase = getattr(self, "_active_vault_passphrase", "") or "clara-vault"
        secrets_list = list_decrypted_secrets(self.db, passphrase, getattr(self, "current_auth_user", None))
        if not secrets_list:
            msg = (
                "La bóveda encriptada está vacía por ahora. Puedes guardar una contraseña o secreto diciendo:\n"
                "«guardar secreto Correo: mi_clave_123» o desde el botón 🔐 Niveles y Bóveda."
            )
            self.append_chat("Asistente", msg, persist=False)
            return msg
        lines = [
            f"🔐 Bóveda de secretos encriptados (acceso prioritario verificado para {getattr(self, 'current_auth_user', 'Propietario')}):"
        ]
        for item in secrets_list:
            lines.append(f"• {item['secret_label']}: {item['value']} (registrado por {item['owner_username']})")
        msg = "\n".join(lines)
        self.append_chat("Asistente", msg, persist=False, speak=False)
        return msg

    def _execute_reset_clara_with_confirmation(self) -> str:
        if TKINTER_AVAILABLE and getattr(self, "tk", None) is not None:
            if not messagebox.askyesno(
                "Confirmar restablecimiento prioritario de CLARA-V",
                "Nivel de acceso prioritario verificado.\n\n"
                "¿Estás seguro de que deseas borrar todas las clases, tareas, bloques, rutinas, recuerdos e historial de CLARA-V?",
                parent=self,
            ):
                msg = "Cancelé el borrado de datos de CLARA-V; tu información se mantiene intacta."
                self.append_chat("Asistente", msg)
                return msg
        msg = reset_clara_all_data(self.db, include_vault=False)
        if hasattr(self, "refresh_tasks"):
            try:
                self.refresh_tasks()
            except Exception:
                pass
        self.append_chat("Asistente", msg)
        return msg

    def handle_security_chat_command(self, sec_cmd: dict[str, object]) -> str:
        """Execute a parsed authentication, registration, vault, or reset command."""
        kind = str(sec_cmd.get("kind") or "")
        ensure_security_tables(self.db)
        user_count = int(self.db.execute("SELECT COUNT(*) FROM security_users").fetchone()[0])

        if kind == "register_user":
            uname = str(sec_cmd.get("username") or "").strip()
            upass = str(sec_cmd.get("password") or "").strip()
            lvl = coerce_security_level(sec_cmd.get("access_level"), default=3)
            if user_count > 0 and getattr(self, "current_auth_level", 0) < 3:
                self.require_permission(
                    "manage_users",
                    pending_callable=lambda: self.handle_security_chat_command(sec_cmd),
                )
                return "Se solicitó autorización de nivel prioritario para registrar usuarios."
            res = register_security_user(self.db, uname, upass, access_level=lvl)
            self.current_auth_user = str(res["username"])
            self.current_auth_level = int(res["access_level"])
            self._active_vault_passphrase = upass
            self._update_auth_status_label()
            msg = str(res["message"])
            self.append_chat("Asistente", msg)
            return msg

        if kind == "change_user_level":
            uname = str(sec_cmd.get("username") or "").strip()
            if not self.require_permission(
                "manage_users",
                pending_callable=lambda: self.handle_security_chat_command(sec_cmd),
            ):
                return "Se solicitó autorización de Nivel 3 (Prioritario) para autorizar o aumentar el nivel de otro usuario."
            res = update_security_user_level(
                self.db,
                uname,
                sec_cmd.get("access_level"),
                increment=bool(sec_cmd.get("increment", False)),
                authorized_by=getattr(self, "current_auth_user", None) or "Propietario (Nivel 3)",
            )
            if res.get("updated") and str(res.get("username", "")).casefold() == str(getattr(self, "current_auth_user", "") or "").casefold():
                self.current_auth_level = int(res["access_level"])
                self._update_auth_status_label()
            msg = str(res["message"])
            self.append_chat("Asistente", msg)
            return msg

        if kind == "login":
            uname = str(sec_cmd.get("username") or "").strip()
            upass = str(sec_cmd.get("password") or "").strip()
            if user_count == 0:
                res = register_security_user(self.db, uname, upass, access_level=3)
                auth = {
                    "authenticated": True,
                    "username": res["username"],
                    "access_level": res["access_level"],
                    "short_level": res["short_level"],
                    "message": res["message"],
                }
            else:
                auth = authenticate_security_user(self.db, uname, upass)
            if not auth.get("authenticated"):
                msg = str(auth.get("message") or "Credenciales inválidas.")
                self.append_chat("Asistente", msg)
                return msg
            self.current_auth_user = str(auth["username"])
            self.current_auth_level = int(auth["access_level"])
            self._active_vault_passphrase = upass
            self._update_auth_status_label()
            pending = getattr(self, "_pending_protected_action", None)
            self._pending_protected_action = None
            base_msg = str(auth["message"])
            if pending is not None:
                req_lvl = int(pending.get("required_level", 3))
                act_label = str(pending.get("action_label", "acción protegida"))
                if self.current_auth_level >= req_lvl:
                    full_msg = f"{base_msg}\n✅ Permisos verificados para «{act_label}». Ejecutando orden…"
                    self.append_chat("Asistente", full_msg)
                    cb = pending.get("callback")
                    if callable(cb):
                        cb()
                    return full_msg
                denied_msg = (
                    f"{base_msg}\n⛔ Orden rechazada: el usuario {self.current_auth_user} tiene "
                    f"{SECURITY_LEVEL_SPECS[self.current_auth_level]['short']}, pero «{act_label}» requiere "
                    f"{SECURITY_LEVEL_SPECS[req_lvl]['short']} ({SECURITY_LEVEL_SPECS[req_lvl]['name']})."
                )
                self.append_chat("Asistente", denied_msg)
                return denied_msg
            self.append_chat("Asistente", base_msg)
            return base_msg

        if kind == "lock_session":
            self.lock_security_session()
            return "Sesión bloqueada en modo Invitado (Nivel 0)."

        if kind == "security_status":
            cur_user = getattr(self, "current_auth_user", None) or "Invitado (sin autenticar)"
            cur_lvl = coerce_security_level(getattr(self, "current_auth_level", 0), default=0)
            cur_spec = SECURITY_LEVEL_SPECS[cur_lvl]
            lines = [
                f"🔐 Estado de seguridad actual: Usuario «{cur_user}» · {cur_spec['short']} ({cur_spec['name']}).",
                f"Permisos actuales: {cur_spec['capabilities']}.",
                "Niveles disponibles en CLARA-V:",
            ]
            for lvl_num, spec in SECURITY_LEVEL_SPECS.items():
                lines.append(f"• {spec['short']} ({spec['name']}): {spec['capabilities']}.")
            lines.append("Para cambiar de usuario o elevar permisos, escribe o dicta: «Nombre Contraseña» (ej. «Luis ju89yt56rf»).")
            msg = "\n".join(lines)
            self.append_chat("Asistente", msg)
            return msg

        if kind == "save_secret":
            label = str(sec_cmd.get("label") or "").strip()
            value = str(sec_cmd.get("value") or "").strip()
            if not self.require_permission(
                "save_secret",
                pending_callable=lambda: self.handle_security_chat_command(sec_cmd),
            ):
                return "Se solicitó autenticación de nivel prioritario para guardar el secreto."
            passphrase = getattr(self, "_active_vault_passphrase", "") or "clara-vault"
            saved = save_encrypted_secret(
                self.db,
                getattr(self, "current_auth_user", None) or "Propietario",
                label,
                value,
                passphrase,
            )
            msg = (
                f"🔐 ¡Listo! Guardé el secreto «{saved['label']}» cifrado con PBKDF2-HMAC-SHA256 en tu bóveda local "
                f"(propietario: {saved['owner']}). Solo usuarios con nivel de acceso prioritario pueden consultarlo."
            )
            self.append_chat("Asistente", msg, persist=False)
            return msg

        if kind == "view_secrets":
            if not self.require_permission(
                "view_secrets",
                pending_callable=self._present_decrypted_secrets_in_chat,
            ):
                return "Se solicitó autenticación de nivel prioritario para ver secretos encriptados."
            return self._present_decrypted_secrets_in_chat()

        if kind == "delete_clara_data":
            if not self.require_permission(
                "delete_clara_data",
                pending_callable=self._execute_reset_clara_with_confirmation,
            ):
                return "Se solicitó autenticación de nivel prioritario para borrar los datos de CLARA-V."
            return self._execute_reset_clara_with_confirmation()

        return ""

    def open_security_levels_vault(self) -> None:
        """Open the Multi-Level User Security & Encrypted Secrets Vault dialog."""
        ensure_security_tables(self.db)
        window = tk.Toplevel(self)
        window.title("Niveles de seguridad y bóveda encriptada · CLARA-V")
        window.geometry("920x640")
        window.minsize(760, 520)
        window.transient(self)
        frame = ttk.Frame(window, padding=16)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Niveles de seguridad (Usuario/Contraseña) y Bóveda Encriptada", style="CardTitle.TLabel").pack(anchor="w")
        session_var = tk.StringVar()

        def update_banner() -> None:
            u = getattr(self, "current_auth_user", None) or "Invitado"
            lvl = coerce_security_level(getattr(self, "current_auth_level", 0), default=0)
            spec = SECURITY_LEVEL_SPECS[lvl]
            session_var.set(f"Sesión activa: {u} · {spec['short']} ({spec['name']}) — Permisos: {spec['capabilities']}")
            self._update_auth_status_label()

        update_banner()
        ttk.Label(frame, textvariable=session_var, wraplength=860, foreground="#60e2df").pack(anchor="w", pady=(4, 10))

        # Top bar: Login / Register User / Lock Session
        auth_box = ttk.LabelFrame(frame, text="1. Iniciar sesión o registrar usuario (también puedes escribir o hablar «Usuario Contraseña» en el chat)", padding=10)
        auth_box.pack(fill="x", pady=(0, 10))
        row1 = ttk.Frame(auth_box)
        row1.pack(fill="x")
        ttk.Label(row1, text="Usuario:").pack(side="left")
        user_var = tk.StringVar(value=getattr(self, "current_auth_user", "") or "")
        ttk.Entry(row1, textvariable=user_var, width=18).pack(side="left", padx=(6, 12))
        ttk.Label(row1, text="Contraseña:").pack(side="left")
        pass_var = tk.StringVar()
        ttk.Entry(row1, textvariable=pass_var, show="*", width=20).pack(side="left", padx=(6, 12))
        ttk.Label(row1, text="Nivel (al registrar):").pack(side="left")
        level_choices = (
            "3 - Prioritario (Control total, bóveda y borrado)",
            "2 - Avanzado (Carpetas, archivos y apps)",
            "1 - Estándar (Agenda, clases y tareas)",
            "0 - Invitado (Solo conversación y consultas)",
        )
        level_var = tk.StringVar(value=level_choices[0])
        ttk.Combobox(row1, textvariable=level_var, values=level_choices, state="readonly", width=36).pack(side="left", padx=(6, 0))

        btn_row = ttk.Frame(auth_box)
        btn_row.pack(fill="x", pady=(8, 0))

        users_tree = ttk.Treeview(frame, columns=("username", "level", "capabilities", "created"), show="headings", height=5)
        for col, title, width in (
            ("username", "Usuario", 140),
            ("level", "Nivel de acceso", 170),
            ("capabilities", "Permisos asignados", 420),
            ("created", "Registrado", 140),
        ):
            users_tree.heading(col, text=title)
            users_tree.column(col, width=width, anchor="w")

        vault_tree = ttk.Treeview(frame, columns=("id", "label", "owner", "created"), show="headings", height=5)
        for col, title, width in (
            ("id", "ID", 50),
            ("label", "Etiqueta del secreto / contraseña", 340),
            ("owner", "Propietario", 180),
            ("created", "Fecha cifrado", 180),
        ):
            vault_tree.heading(col, text=title)
            vault_tree.column(col, width=width, anchor="w")

        def refresh_tables() -> None:
            update_banner()
            users_tree.delete(*users_tree.get_children())
            for r in self.db.execute("SELECT username, access_level, created_at FROM security_users ORDER BY access_level DESC, username"):
                lvl = coerce_security_level(r["access_level"], default=1)
                spec = SECURITY_LEVEL_SPECS[lvl]
                users_tree.insert("", "end", values=(r["username"], spec["short"], spec["capabilities"], str(r["created_at"])[:16]))
            vault_tree.delete(*vault_tree.get_children())
            for r in self.db.execute("SELECT id, secret_label, owner_username, created_at FROM encrypted_secrets ORDER BY id DESC"):
                vault_tree.insert("", "end", iid=str(r["id"]), values=(r["id"], r["secret_label"], r["owner_username"], str(r["created_at"])[:16]))

        def do_login() -> None:
            res = self.handle_security_chat_command({"kind": "login", "username": user_var.get(), "password": pass_var.get()})
            pass_var.set("")
            refresh_tables()
            messagebox.showinfo("Verificación de acceso", res, parent=window)

        def do_register() -> None:
            count = int(self.db.execute("SELECT COUNT(*) FROM security_users").fetchone()[0])
            if count > 0 and getattr(self, "current_auth_level", 0) < 3:
                messagebox.showwarning(
                    "Permiso insuficiente",
                    "Ya existe un propietario registrado. Inicia sesión primero con un usuario de Nivel 3 (Prioritario) para agregar o modificar usuarios.",
                    parent=window,
                )
                return
            try:
                res = register_security_user(self.db, user_var.get(), pass_var.get(), access_level=level_var.get()[0])
            except ValueError as exc:
                messagebox.showerror("Datos incompletos", str(exc), parent=window)
                return
            self.current_auth_user = str(res["username"])
            self.current_auth_level = int(res["access_level"])
            self._active_vault_passphrase = pass_var.get().strip()
            pass_var.set("")
            refresh_tables()
            self.append_chat("Asistente", str(res["message"]))
            messagebox.showinfo("Usuario guardado", str(res["message"]), parent=window)

        def on_select_user(_event=None) -> None:
            sel = users_tree.selection()
            if not sel:
                return
            vals = users_tree.item(sel[0], "values")
            if vals:
                user_var.set(str(vals[0]))
                lvl_text = str(vals[1] or "")
                for ch in level_choices:
                    if f"Nivel {ch[0]}" in lvl_text:
                        level_var.set(ch)
                        break

        users_tree.bind("<<TreeviewSelect>>", on_select_user)

        def do_change_user_level() -> None:
            if getattr(self, "current_auth_level", 0) < 3:
                messagebox.showwarning(
                    "Nivel prioritario requerido",
                    "Solo un usuario autenticado con Nivel 3 (Prioritario) puede autorizar o aumentar el nivel de otros usuarios.",
                    parent=window,
                )
                return
            sel = users_tree.selection()
            target_user = str(users_tree.item(sel[0], "values")[0]) if sel else user_var.get().strip()
            if not target_user:
                messagebox.showinfo(
                    "Selecciona un usuario",
                    "Selecciona un usuario de la tabla inferior (o escribe su nombre en Usuario) y elige el nuevo nivel en el desplegable.",
                    parent=window,
                )
                return
            res = update_security_user_level(
                self.db,
                target_user,
                level_var.get()[0],
                authorized_by=getattr(self, "current_auth_user", None) or "Propietario (Nivel 3)",
            )
            if not res.get("updated"):
                messagebox.showwarning("Usuario no encontrado", str(res["message"]), parent=window)
                return
            if str(res.get("username", "")).casefold() == str(getattr(self, "current_auth_user", "") or "").casefold():
                self.current_auth_level = int(res["access_level"])
            refresh_tables()
            self.append_chat("Asistente", str(res["message"]))
            messagebox.showinfo("Nivel de usuario autorizado", str(res["message"]), parent=window)

        def do_delete_user() -> None:
            if getattr(self, "current_auth_level", 0) < 3:
                messagebox.showwarning("Nivel prioritario requerido", "Solo un usuario con Nivel 3 (Prioritario) puede eliminar cuentas.", parent=window)
                return
            sel = users_tree.selection()
            if not sel:
                messagebox.showinfo("Selecciona un usuario", "Elige un usuario en la tabla para eliminarlo.", parent=window)
                return
            uname = str(users_tree.item(sel[0], "values")[0])
            if messagebox.askyesno("Eliminar usuario", f"¿Eliminar al usuario «{uname}»?", parent=window):
                self.db.execute("DELETE FROM security_users WHERE LOWER(username)=LOWER(?)", (uname,))
                self.db.commit()
                refresh_tables()

        ttk.Button(btn_row, text="🔓 Verificar e iniciar sesión", style="Accent.TButton", command=do_login).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="➕ Registrar / actualizar usuario", command=do_register).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="⬆ Autorizar / cambiar nivel", command=do_change_user_level).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="🔒 Bloquear sesión (Modo Invitado)", command=lambda: (self.lock_security_session(), refresh_tables())).pack(side="left", padx=(0, 8))
        ttk.Button(btn_row, text="🗑 Eliminar usuario", command=do_delete_user).pack(side="left")

        ttk.Label(frame, text="Usuarios registrados y sus niveles:", background="#07111f", foreground="#91aabd").pack(anchor="w", pady=(2, 4))
        users_tree.pack(fill="x", pady=(0, 10))

        # Encrypted Vault Section (Level 3 Prioritario)
        vault_box = ttk.LabelFrame(frame, text="2. Bóveda de contraseñas y secretos encriptados (Exclusivo Nivel 3 · Prioritario)", padding=10)
        vault_box.pack(fill="both", expand=True)
        v_top = ttk.Frame(vault_box)
        v_top.pack(fill="x", pady=(0, 8))
        ttk.Label(v_top, text="Etiqueta (ej. Correo, WiFi):").pack(side="left")
        sec_label_var = tk.StringVar()
        ttk.Entry(v_top, textvariable=sec_label_var, width=22).pack(side="left", padx=(6, 12))
        ttk.Label(v_top, text="Secreto / Contraseña:").pack(side="left")
        sec_val_var = tk.StringVar()
        ttk.Entry(v_top, textvariable=sec_val_var, show="*", width=28).pack(side="left", padx=(6, 12))

        def add_secret_ui() -> None:
            if getattr(self, "current_auth_level", 0) < 3:
                messagebox.showwarning("Nivel prioritario requerido", "Inicia sesión con un usuario de Nivel 3 (Prioritario) para guardar secretos encriptados.", parent=window)
                return
            try:
                save_encrypted_secret(
                    self.db,
                    getattr(self, "current_auth_user", None) or "Propietario",
                    sec_label_var.get(),
                    sec_val_var.get(),
                    getattr(self, "_active_vault_passphrase", "") or "clara-vault",
                )
            except ValueError as exc:
                messagebox.showerror("No se pudo guardar", str(exc), parent=window)
                return
            sec_label_var.set("")
            sec_val_var.set("")
            refresh_tables()
            messagebox.showinfo("Secreto encriptado", "El secreto se cifró con PBKDF2-HMAC-SHA256 y se guardó en la bóveda.", parent=window)

        def reveal_secret_ui() -> None:
            if getattr(self, "current_auth_level", 0) < 3:
                messagebox.showwarning("Nivel prioritario requerido", "Se requiere Nivel 3 (Prioritario) para desencriptar y ver contraseñas guardadas.", parent=window)
                return
            sel = vault_tree.selection()
            if not sel:
                messagebox.showinfo("Selecciona un secreto", "Selecciona primero un registro de la bóveda.", parent=window)
                return
            row = self.db.execute("SELECT secret_label, encrypted_payload FROM encrypted_secrets WHERE id=?", (int(sel[0]),)).fetchone()
            if not row:
                return
            try:
                plain = decrypt_vault_secret(str(row["encrypted_payload"]), getattr(self, "_active_vault_passphrase", "") or "clara-vault")
                messagebox.showinfo(f"Secreto desencriptado · {row['secret_label']}", f"Etiqueta: {row['secret_label']}\nValor desencriptado:\n\n{plain}", parent=window)
            except ValueError as exc:
                messagebox.showerror("No se pudo desencriptar", str(exc), parent=window)

        def delete_secret_ui() -> None:
            if getattr(self, "current_auth_level", 0) < 3:
                messagebox.showwarning("Nivel prioritario requerido", "Se requiere Nivel 3 (Prioritario) para eliminar secretos de la bóveda.", parent=window)
                return
            sel = vault_tree.selection()
            if not sel:
                return
            self.db.execute("DELETE FROM encrypted_secrets WHERE id=?", (int(sel[0]),))
            self.db.commit()
            refresh_tables()

        v_btns = ttk.Frame(vault_box)
        v_btns.pack(fill="x", pady=(0, 8))
        ttk.Button(v_btns, text="🔐 Guardar secreto encriptado", style="Accent.TButton", command=add_secret_ui).pack(side="left", padx=(0, 8))
        ttk.Button(v_btns, text="👁 Ver secreto seleccionado", command=reveal_secret_ui).pack(side="left", padx=(0, 8))
        ttk.Button(v_btns, text="🗑 Eliminar secreto", command=delete_secret_ui).pack(side="left", padx=(0, 8))
        ttk.Button(v_btns, text="⚠ Restablecer datos de CLARA-V", style="Danger.TButton", command=lambda: self.handle_security_chat_command({"kind": "delete_clara_data"})).pack(side="right")

        vault_tree.pack(fill="both", expand=True)
        refresh_tables()

    def open_local_file_tools(self, intent: dict | None = None) -> None:
        """Open a manual, non-persistent search/inventory tool; intent only prefills a safe workflow."""
        if not self.require_permission("file_operations", pending_callable=lambda: self.open_local_file_tools(intent=intent)):
            return
        if self.local_scan_running:
            messagebox.showinfo("Búsqueda local activa", "Espera a que termine o cancela la operación actual antes de iniciar otra.", parent=self)
            return
        window = tk.Toplevel(self)
        window.title("Buscar documentos / ver contenido de carpeta")
        window.geometry("1040x650")
        window.minsize(820, 520)
        window.transient(self)
        outer = ttk.Frame(window, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Archivos locales · Etapa 8", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Cada operación te pedirá elegir una carpeta. Clara solo lista nombres y metadatos; no lee ni modifica archivos. Abrir un documento requiere seleccionarlo y confirmar una advertencia; Windows lo entrega a la aplicación predeterminada. Elige una carpeta local no sincronizada; se bloquean nombres comunes de nube, aunque no se pueden detectar todos los clientes con nombres personalizados.",
            wraplength=930,
        ).pack(anchor="w", pady=(5, 10))
        query_row = ttk.Frame(outer)
        query_row.pack(fill="x", pady=(0, 8))
        ttk.Label(query_row, text="Nombre contiene:").pack(side="left")
        query_var = tk.StringVar(value=str((intent or {}).get("query") or ""))
        query_entry = ttk.Entry(query_row, textvariable=query_var, width=34)
        query_entry.pack(side="left", padx=(8, 16))
        ttk.Label(query_row, text="Tipo:").pack(side="left")
        type_values = ("Todos", ".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".markdown")
        requested_extension = str((intent or {}).get("extension") or "Todos")
        type_var = tk.StringVar(value=requested_extension if requested_extension in type_values else "Todos")
        type_combo = ttk.Combobox(query_row, textvariable=type_var, values=type_values, state="readonly", width=13)
        type_combo.pack(side="left", padx=8)
        inventory_recursive = tk.BooleanVar(value=bool((intent or {}).get("recursive", False)))
        ttk.Checkbutton(query_row, text="Inventario recursivo de carpetas", variable=inventory_recursive).pack(side="left", padx=(10, 0))

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(0, 4))
        file_actions = ttk.Frame(outer)
        file_actions.pack(fill="x", pady=(0, 8))
        status_var = tk.StringVar(value="Listo · elige una operación; la carpeta no se recuerda.")
        search_button = ttk.Button(buttons, text="Buscar documentos…", style="Accent.TButton")
        inventory_button = ttk.Button(buttons, text="Ver archivos y carpetas…")
        stop_button = ttk.Button(buttons, text="DETENER", style="Danger.TButton", state="disabled")
        clear_button = ttk.Button(buttons, text="Limpiar resultados")
        open_button = ttk.Button(file_actions, text="Abrir seleccionado…", state="disabled")
        move_button = ttk.Button(file_actions, text="Mover seleccionado…", state="disabled")
        undo_button = ttk.Button(file_actions, text="Deshacer último movimiento", state="disabled")
        search_button.pack(side="left", padx=(0, 8))
        inventory_button.pack(side="left", padx=(0, 8))
        stop_button.pack(side="left", padx=(0, 8))
        clear_button.pack(side="left")
        open_button.pack(side="left", padx=(0, 8))
        move_button.pack(side="left", padx=(0, 8))
        undo_button.pack(side="left")
        ttk.Label(outer, text="Mover requiere confirmar cada archivo; no hay lotes ni sobrescritura. El deshacer solo dura mientras esta ventana permanece abierta y el archivo no cambia.", wraplength=930).pack(anchor="w", pady=(0, 5))
        ttk.Label(outer, textvariable=status_var, wraplength=930).pack(anchor="w", pady=(0, 7))
        tree_frame = ttk.Frame(outer)
        tree_frame.pack(fill="both", expand=True)
        columns = ("name", "kind", "modified", "size", "relative")
        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col, title, width, anchor in (
            ("name", "Nombre", 260, "w"), ("kind", "Tipo", 90, "center"),
            ("modified", "Modificado", 135, "center"), ("size", "Tamaño", 105, "e"),
            ("relative", "Ubicación relativa", 330, "w"),
        ):
            tree.heading(col, text=title)
            tree.column(col, width=width, anchor=anchor, stretch=(col in ("name", "relative")))
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        ttk.Label(outer, text="Tipos listados: PDF, DOCX, XLSX, PPTX, TXT y Markdown. Se excluyen elementos ocultos/sistema, symlinks/junctions, scripts y ejecutables.", wraplength=930).pack(anchor="w", pady=(8, 0))

        operation_queue: queue.Queue = queue.Queue()
        result_map: dict[str, dict] = {}
        move_history: list[dict] = []  # session-memory only; never persisted to the database
        state = {"thread": None, "cancel": None, "poll_id": None, "closing": False}

        def clear_results() -> None:
            for item in tree.get_children():
                tree.delete(item)
            result_map.clear()
            open_button.configure(state="disabled")
            move_button.configure(state="disabled")
            status_var.set("Resultados limpiados. No se modificó ningún archivo.")

        def open_selected_document() -> None:
            if sys.platform != "win32" or not callable(getattr(os, "startfile", None)):
                messagebox.showinfo("Apertura no disponible", "La apertura con asociaciones del sistema solo está habilitada en Windows.", parent=window)
                return
            selection = tree.selection()
            record = result_map.get(selection[0]) if selection else None
            if not record:
                messagebox.showinfo("Selecciona un documento", "Elige un archivo de los tipos permitidos; las carpetas no se abren desde esta ventana.", parent=window)
                return
            try:
                path = validate_local_document_for_open(record["root"], record["path"], record["size"], record["mtime_ns"], record["file_id"])
            except (OSError, ValueError) as exc:
                messagebox.showwarning("No se puede abrir", str(exc), parent=window)
                return
            extension = path.suffix.casefold()
            size_label = f"{record['size']:,} bytes"
            prompt = (
                f"Windows intentará abrir este archivo con la aplicación predeterminada para {extension}.\n\n"
                f"Archivo: {record['name']}\nUbicación dentro de la carpeta elegida: {record['relative']}\nTamaño: {size_label}\n\n"
                "Abrirlo fuera de Clara puede activar enlaces, contenido dinámico o vulnerabilidades del programa receptor. "
                "Clara no puede forzar ni verificar el modo protegido. Continúa solo si confías en el archivo.\n\n¿Abrirlo ahora?"
            )
            if not messagebox.askyesno("Confirmar apertura de documento", prompt, icon="warning", parent=window):
                status_var.set("Apertura cancelada; no se inició ninguna aplicación.")
                return
            try:
                confirmed_path = validate_local_document_for_open(record["root"], record["path"], record["size"], record["mtime_ns"], record["file_id"])
                getattr(os, "startfile")(str(confirmed_path))
                logged = self._record_private_action_event("Abrir documento permitido", "Windows recibió la solicitud; nombre/ruta omitidos")
                status_var.set("Windows recibió la solicitud de apertura. Clara no controla la aplicación después de iniciarla." + (" El registro local no pudo guardarse." if not logged else ""))
            except (OSError, ValueError) as exc:
                messagebox.showwarning("No se abrió", str(exc), parent=window)

        def move_selected_document() -> None:
            if sys.platform != "win32":
                messagebox.showinfo("Movimiento no disponible", "El movimiento está habilitado únicamente en Windows.", parent=window)
                return
            selection = tree.selection()
            item_id = selection[0] if selection else ""
            record = result_map.get(item_id)
            if not record:
                messagebox.showinfo("Selecciona un documento", "Elige un archivo permitido; no se mueven carpetas ni lotes.", parent=window)
                return
            destination_choice = filedialog.askdirectory(parent=window, title="Elige una carpeta local de destino", mustexist=True)
            if not destination_choice:
                status_var.set("Movimiento cancelado al elegir el destino; no se cambió ningún archivo.")
                return
            try:
                plan = prepare_local_move(record["root"], record["path"], destination_choice, record["size"], record["mtime_ns"], record["file_id"])
            except (OSError, ValueError) as exc:
                messagebox.showwarning("No se puede preparar el movimiento", str(exc), parent=window)
                return
            prompt = (
                f"Se moverá un archivo.\n\nOrigen: {plan['source']}\nDestino: {plan['destination']}\n\n"
                "El origen dejará de contenerlo. No se sobrescribe, no se hacen copias entre discos y no se mueven carpetas/lotes. "
                "El último movimiento puede deshacerse solo mientras esta ventana siga abierta y el archivo permanezca sin cambios.\n\n¿Confirmas este movimiento?"
            )
            if not messagebox.askyesno("Confirmar movimiento de archivo", prompt, icon="warning", parent=window):
                status_var.set("Movimiento cancelado; el archivo permanece en el origen.")
                return
            try:
                checked = prepare_local_move(record["root"], record["path"], destination_choice, record["size"], record["mtime_ns"], record["file_id"])
                if any(checked[key] != plan[key] for key in ("source", "destination", "size", "mtime_ns", "file_id")):
                    raise ValueError("El origen o destino cambió después de la vista previa; no se movió nada.")
                execute_local_move(checked)
            except (OSError, ValueError) as exc:
                messagebox.showwarning("No se movió el archivo", str(exc), parent=window)
                return
            move_history.append({**checked, "original_record": record})
            logged = self._record_private_action_event("Mover documento permitido", "Confirmado y realizado; nombre/rutas omitidos")
            result_map.pop(item_id, None)
            tree.delete(item_id)
            open_button.configure(state="disabled")
            move_button.configure(state="disabled")
            undo_button.configure(state="normal")
            status_var.set("Movimiento completado por Windows. El último movimiento puede deshacerse desde esta ventana si el archivo no cambia." + (" El registro local no pudo guardarse." if not logged else ""))

        def undo_last_move() -> None:
            if not move_history:
                undo_button.configure(state="disabled")
                return
            previous = move_history[-1]
            destination_back = Path(previous["source"]).parent
            try:
                plan = prepare_local_move(
                    previous["destination_root"], previous["destination"], destination_back,
                    previous["size"], previous["mtime_ns"], tuple(previous["file_id"]),
                )
            except (OSError, ValueError) as exc:
                messagebox.showwarning("No se puede deshacer", str(exc), parent=window)
                return
            prompt = f"Se devolverá el archivo:\n{plan['source']}\n\nA su ubicación original:\n{plan['destination']}\n\nNo se sobrescribirá nada. ¿Confirmas el deshacer?"
            if not messagebox.askyesno("Confirmar deshacer", prompt, icon="warning", parent=window):
                return
            try:
                checked = prepare_local_move(
                    previous["destination_root"], previous["destination"], destination_back,
                    previous["size"], previous["mtime_ns"], tuple(previous["file_id"]),
                )
                execute_local_move(checked)
            except (OSError, ValueError) as exc:
                messagebox.showwarning("No se pudo deshacer", str(exc), parent=window)
                return
            move_history.pop()
            undo_button.configure(state="normal" if move_history else "disabled")
            logged = self._record_private_action_event("Deshacer movimiento de documento", "Confirmado; nombre/rutas omitidos")
            status_var.set("Movimiento revertido. Vuelve a buscar para actualizar la lista; no se conservó historial al cerrar la ventana." + (" El registro local no pudo guardarse." if not logged else ""))

        def selection_changed(_event=None) -> None:
            selection = tree.selection()
            can_open = bool(selection and selection[0] in result_map and not self.local_scan_running)
            open_button.configure(state="normal" if can_open else "disabled")
            move_button.configure(state="normal" if can_open and sys.platform == "win32" else "disabled")

        def stop_scan() -> None:
            cancel = state.get("cancel")
            if cancel is not None:
                cancel.set()
                status_var.set("Detención solicitada · se detendrá cooperativamente; una llamada bloqueante del disco puede tardar.")

        def poll_results() -> None:
            if state["closing"] or not window.winfo_exists():
                return
            try:
                while True:
                    message = operation_queue.get_nowait()
                    kind = message[0]
                    if kind == "progress":
                        status_var.set(f"Revisando nombres y metadatos… {message[1]:,} elementos; {message[2]:,} coincidencias")
                    elif kind == "error":
                        self.local_scan_running = False
                        self.local_scan_cancel_event = None
                        state["thread"] = None
                        state["cancel"] = None
                        search_button.configure(state="normal")
                        inventory_button.configure(state="normal")
                        stop_button.configure(state="disabled")
                        status_var.set("No se pudo completar la consulta.")
                        messagebox.showerror("Búsqueda local", message[1], parent=window)
                    elif kind == "done":
                        result = message[1]
                        for item in tree.get_children():
                            tree.delete(item)
                        result_map.clear()
                        open_button.configure(state="disabled")
                        move_button.configure(state="disabled")
                        for row in result["results"]:
                            size = row["size"]
                            size_label = "" if size == "" else (f"{int(size):,} bytes" if int(size) < 1024 * 1024 else f"{int(size) / (1024 * 1024):.1f} MB")
                            item_id = tree.insert("", "end", values=(row["name"], row["kind"], row["modified"], size_label, row["relative"]))
                            if row["kind"] != "Carpeta" and "mtime_ns" in row:
                                result_map[item_id] = {**row, "root": state["root"]}
                        self.local_scan_running = False
                        self.local_scan_cancel_event = None
                        state["thread"] = None
                        state["cancel"] = None
                        search_button.configure(state="normal")
                        inventory_button.configure(state="normal")
                        stop_button.configure(state="disabled")
                        labels = {
                            "complete": "Completado",
                            "cancelled": "Detenido",
                            "entry_limit": "Límite de elementos alcanzado",
                            "result_limit": "Límite de resultados alcanzado",
                            "time_limit": "Límite de tiempo alcanzado",
                        }
                        detail = f"{labels.get(result['status'], 'Completado')} · {len(result['results']):,} elemento(s) · {result['visited']:,} entradas revisadas."
                        if result["inaccessible"]:
                            detail += f" {result['inaccessible']:,} elemento(s) no se pudieron consultar por permisos/errores."
                        if result["status"] != "complete":
                            detail += " Los resultados pueden estar incompletos."
                        elif not result["results"]:
                            detail += " No hubo coincidencias. Comprueba la carpeta elegida, el texto y el filtro; se admiten PDF, DOCX, XLSX, PPTX, TXT y Markdown. La búsqueda solo examina nombres y metadatos."
                        status_var.set(detail)
            except queue.Empty:
                pass
            if state.get("thread") is not None:
                state["poll_id"] = window.after(100, poll_results)

        def begin_scan(inventory: bool) -> None:
            if state.get("thread") is not None:
                return
            chosen = filedialog.askdirectory(parent=window, title="Elige una carpeta local para esta operación", mustexist=True)
            if not chosen:
                status_var.set("Operación cancelada; no se exploró ninguna carpeta.")
                return
            try:
                root_path = validate_local_search_root(chosen)
            except (OSError, ValueError) as exc:
                messagebox.showwarning("Carpeta no permitida", str(exc), parent=window)
                status_var.set("Carpeta rechazada; no se inició el recorrido.")
                return
            recursive = inventory_recursive.get() if inventory else True
            query = query_var.get().strip() if not inventory else ""
            extension = type_var.get() if not inventory else "Todos"
            cancel = threading.Event()
            state["cancel"] = cancel
            state["root"] = str(root_path)
            state["thread"] = True
            self.local_scan_cancel_event = cancel
            self.local_scan_running = True
            search_button.configure(state="disabled")
            inventory_button.configure(state="disabled")
            stop_button.configure(state="normal")
            for item in tree.get_children():
                tree.delete(item)
            result_map.clear()
            open_button.configure(state="disabled")
            move_button.configure(state="disabled")
            operation_name = "Inventariando" if inventory else "Buscando"
            status_var.set(f"{operation_name} en la carpeta elegida · solo nombres/metadatos; no se leen contenidos…")

            def report_progress(visited: int, found: int) -> None:
                operation_queue.put(("progress", visited, found))

            def worker() -> None:
                try:
                    result = scan_local_documents(
                        root_path, query, extension, inventory=inventory, recursive=recursive,
                        cancel_event=cancel, max_entries=LOCAL_SCAN_MAX_ENTRIES,
                        max_results=LOCAL_SCAN_MAX_RESULTS, max_seconds=LOCAL_SCAN_MAX_SECONDS,
                        progress_callback=report_progress,
                    )
                    operation_queue.put(("done", result))
                except Exception as exc:
                    # Do not echo the selected path or exception internals into logs/chat.
                    operation_queue.put(("error", f"Error de lectura de directorio: {type(exc).__name__}. Puedes elegir otra carpeta o revisar sus permisos."))
                finally:
                    if self.local_scan_cancel_event is cancel:
                        self.local_scan_cancel_event = None
                        self.local_scan_running = False

            state["thread"] = threading.Thread(target=worker, name="clara-local-scan", daemon=True)
            state["thread"].start()
            state["poll_id"] = window.after(100, poll_results)

        search_button.configure(command=lambda: begin_scan(False))
        inventory_button.configure(command=lambda: begin_scan(True))
        open_button.configure(command=open_selected_document)
        move_button.configure(command=move_selected_document)
        undo_button.configure(command=undo_last_move)
        stop_button.configure(command=stop_scan)
        clear_button.configure(command=clear_results)
        tree.bind("<<TreeviewSelect>>", selection_changed)
        query_entry.bind("<Return>", lambda _event: begin_scan(False))
        if intent:
            requested_mode = str(intent.get("intent", ""))
            if requested_mode in ("file_search", "file_open", "file_move", "file_inventory"):
                window.after(350, lambda: begin_scan(requested_mode == "file_inventory"))

        def close_window() -> None:
            state["closing"] = True
            cancel = state.get("cancel")
            if cancel is not None:
                cancel.set()
            if state.get("poll_id") is not None:
                try:
                    window.after_cancel(state["poll_id"])
                except tk.TclError:
                    pass
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", close_window)
        query_entry.focus_set()

    def open_privacy_center(self) -> None:
        """Summarize permissions, retention and local activity without exposing saved paths."""
        window = tk.Toplevel(self)
        window.title("Privacidad, permisos y actividad")
        window.geometry("920x610")
        window.minsize(760, 480)
        window.transient(self)
        outer = ttk.Frame(window, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Privacidad y permisos", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Resumen de controles de Clara. Las rutas de aplicaciones autorizadas y el vínculo iCalendar se guardan en preferencias locales; no se muestran aquí. La búsqueda no guarda la carpeta elegida. El historial de actividad omite nombres y rutas.",
            wraplength=860,
        ).pack(anchor="w", pady=(5, 8))
        actions = ttk.Frame(outer)
        actions.pack(side="top", fill="x", pady=(0, 8))
        version_var = tk.StringVar(value=f"Clara Unificada {APP_VERSION} · descargas y actualizaciones automáticas desactivadas")
        ttk.Label(outer, textvariable=version_var, wraplength=860).pack(side="bottom", anchor="w", pady=(8, 0))
        tree_frame = ttk.Frame(outer)
        tree_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(tree_frame, columns=("control", "state"), show="headings", selectmode="browse", height=7)
        tree.heading("control", text="Control")
        tree.heading("state", text="Estado actual")
        tree.column("control", width=205, anchor="w", stretch=False)
        tree.column("state", width=630, anchor="w", stretch=True)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        ttk.Button(actions, text="🚀 Aplicaciones autorizadas…", style="Accent.TButton", command=self.open_application_manager).pack(side="left", padx=(0, 7))
        ttk.Button(actions, text="⚙ Preferencias…", command=self.open_settings).pack(side="left", padx=(0, 7))
        ttk.Button(actions, text="🔐 Niveles y Bóveda…", command=self.open_security_levels_vault).pack(side="left", padx=(0, 7))
        ttk.Button(actions, text="🛡 Seguridad / VirusTotal…", command=self.open_security).pack(side="left", padx=(0, 7))
        ttk.Button(actions, text="Historial de actividad…", command=lambda: self.show_action_history(window)).pack(side="left", padx=(0, 7))
        ttk.Button(actions, text="Respaldos / datos…", command=self.open_backup_tools).pack(side="left", padx=(0, 7))
        ttk.Button(actions, text="Actualizar", command=lambda: refresh()).pack(side="right")

        def refresh() -> None:
            tree.delete(*tree.get_children())
            allowed_apps = load_allowed_applications(self.settings)
            chat_count = self.db.execute("SELECT COUNT(*) FROM chat_history").fetchone()[0]
            action_count = self.db.execute("SELECT COUNT(*) FROM action_events").fetchone()[0]
            report_count = self.db.execute("SELECT COUNT(*) FROM security_events").fetchone()[0]
            ics_path = self.settings.get("calendar_ics_path", "").strip()
            ics_state = "Sin vínculo" if not ics_path else f"Vinculado: {Path(ics_path).name} (solo lectura; quita el vínculo desde Agenda)"
            values = (
                ("Micrófono", "Push-to-talk manual; apagado por defecto; transcripción editable antes de enviar."),
                ("Búsqueda de carpetas", "Se elige una raíz por operación; solo nombre/tipo (PDF, DOCX, XLSX, PPTX, TXT, MD); no se lee contenido."),
                ("Archivos", "Abrir/mover requiere confirmación por elemento; un archivo por vez; sin lotes ni sobrescritura."),
                ("Aplicaciones", f"{len(allowed_apps)} de {MAX_ALLOWED_APPLICATIONS} rutas GUI autorizadas; cada inicio pide confirmación; sin shell ni argumentos."),
                ("Historial de chat", f"{'Activado' if self.settings.get('chat_history_enabled') == 'true' else 'Desactivado'} · {chat_count} turno(s) local(es); se puede borrar/exportar desde Preferencias."),
                ("Sugerencias de rutina", "Activadas" if self.settings.get("pattern_suggestions") == "true" else "Desactivadas; no se infieren rutinas ni se crean duplicados silenciosamente."),
                ("Notificaciones nativas", "Activadas" if self.settings.get("native_notifications_enabled") == "true" else "Desactivadas; dependen de Windows y de una sesión iniciada."),
                ("Bandeja del sistema", "Activada" if self.settings.get("minimize_to_tray") == "true" else "Desactivada"),
                ("Agenda iCalendar", ics_state + " · sin conexión a calendarios externos."),
                ("Clave VirusTotal", "Configurada en almacenamiento Windows DPAPI" if VT_KEY_PATH.is_file() else "No configurada; consultas manuales hash-only; clave excluida de chats, preferencias y respaldos."),
                ("Actividad local", f"{action_count} evento(s) sin nombres/rutas; los puedes revisar y borrar."),
                ("Notas de seguridad", f"{report_count} nota(s) manual(es); se pueden revisar/borrar en Seguridad."),
                ("Respaldos", "Los ZIP de respaldo NO están cifrados; incluyen base y preferencias, pero excluyen la clave de VirusTotal."),
                ("Migración Viernes", "Datos de CLARA conservados intactos en %USERPROFILE%\\AsistentePersonal; sin migración automática."),
                ("Descargas y actualizaciones", "Desactivadas por defecto; cada recurso opcional muestra fuente oficial, versión, tamaño, licencia y hash."),
            )
            for control, state in values:
                tree.insert("", "end", values=(control, state))
            version_var.set(f"Clara Unificada {APP_VERSION} · actualización y descarga automática desactivadas; revisa recursos solo desde fuentes oficiales verificadas.")

        refresh()

    def open_application_manager(self, auto_prompt_add: bool = False) -> None:
        """Manage a small persistent GUI-app allowlist; every launch is reconfirmed."""
        if not AssistantApp.require_permission(self, "manage_apps", pending_callable=lambda: self.open_application_manager(auto_prompt_add=auto_prompt_add)):
            return
        if sys.platform != "win32":
            messagebox.showinfo("Solo Windows", "El inicio de aplicaciones está disponible únicamente en Windows.", parent=self)
            return
        window = tk.Toplevel(self)
        window.title("Aplicaciones autorizadas · agregar e iniciar")
        window.geometry("920x560")
        window.minsize(740, 420)
        window.transient(self)
        outer = ttk.Frame(window, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Aplicaciones autorizadas (máximo 10)", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Usa el botón «+ Añadir .exe autorizado…» o «🔍 Elegir de apps instaladas…» aquí arriba para autorizar programas gráficos de Program Files o LocalAppData\\Programs. También puedes pedirle a Clara en el chat: «abre la aplicación <nombre>».",
            wraplength=860,
        ).pack(anchor="w", pady=(4, 8))
        actions = ttk.Frame(outer)
        actions.pack(side="top", fill="x", pady=(0, 8))
        add_button = ttk.Button(actions, text="➕ Añadir .exe autorizado…", style="Accent.TButton")
        scan_button = ttk.Button(actions, text="🔍 Elegir de apps instaladas…")
        launch_button = ttk.Button(actions, text="▶ Iniciar seleccionada…", state="disabled")
        remove_button = ttk.Button(actions, text="🗑 Retirar autorización", state="disabled")
        add_button.pack(side="left", padx=(0, 8))
        scan_button.pack(side="left", padx=(0, 8))
        launch_button.pack(side="left", padx=(0, 8))
        remove_button.pack(side="left")
        status_var = tk.StringVar(value="No se inicia ninguna aplicación al añadirla.")
        ttk.Label(outer, textvariable=status_var, wraplength=860, foreground="#60e2df").pack(side="top", anchor="w", pady=(0, 6))
        tree_frame = ttk.Frame(outer)
        tree_frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(tree_frame, columns=("name", "path"), show="headings", selectmode="browse", height=6)
        tree.heading("name", text="Aplicación")
        tree.heading("path", text="Ruta autorizada")
        tree.column("name", width=220, anchor="w", stretch=False)
        tree.column("path", width=620, anchor="w", stretch=True)
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        records_by_id: dict[str, dict] = {}

        def current_records() -> list[dict]:
            return load_allowed_applications(self.settings)

        def persist_records(records: list[dict]) -> bool:
            old_value = self.settings.get("allowed_applications", "[]")
            self.settings["allowed_applications"] = normalize_allowed_applications(json.dumps(records, ensure_ascii=False))
            try:
                save_settings(self.settings)
                return True
            except OSError as exc:
                self.settings["allowed_applications"] = old_value
                messagebox.showerror("No se guardó la lista", "No pude guardar la lista autorizada en preferencias locales. No se cambió el permiso.\n" + str(exc), parent=window)
                return False

        def refresh_list() -> None:
            for item in tree.get_children():
                tree.delete(item)
            records_by_id.clear()
            for record in current_records():
                item_id = tree.insert("", "end", values=(record["name"], record["path"]))
                records_by_id[item_id] = record
            launch_button.configure(state="disabled")
            remove_button.configure(state="disabled")
            status_var.set(f"{len(records_by_id)} de {MAX_ALLOWED_APPLICATIONS} aplicaciones autorizadas. Ninguna se inicia automáticamente.")

        def _authorize_candidate_path(chosen: str) -> None:
            try:
                record = validate_local_application(chosen)
            except (OSError, ValueError) as exc:
                messagebox.showwarning("Aplicación no permitida", str(exc), parent=window)
                return
            records = current_records()
            canonical = os.path.normcase(os.path.abspath(record["path"]))
            if any(os.path.normcase(os.path.abspath(item["path"])) == canonical for item in records):
                messagebox.showinfo("Ya autorizada", "Esa ruta ya aparece en la lista.", parent=window)
                return
            prompt = (
                f"¿Autorizar esta aplicación para que aparezca en tu lista?\n\n{record['name']}\n{record['path']}\n\n"
                "Esto guarda la ruta y su identidad básica en preferencias locales. "
                "No la inicia ahora. Cada inicio futuro te volverá a pedir confirmación.\n\n¿Autorizar esta ruta exacta?"
            )
            if not messagebox.askyesno("Autorizar aplicación", prompt, icon="warning", parent=window):
                return
            records.append(record)
            if persist_records(records):
                logged = self._record_private_action_event("Autorizar aplicación", "Permiso agregado; ruta omitida")
                refresh_list()
                status_var.set(f"Autorizada: {record['name']}. Usa «▶ Iniciar seleccionada…» o pídele a Clara «abre la aplicación {record['name']}»." + (" No se pudo guardar el evento de actividad." if not logged else ""))

        def add_application() -> None:
            if len(current_records()) >= MAX_ALLOWED_APPLICATIONS:
                messagebox.showinfo("Límite alcanzado", f"La lista admite hasta {MAX_ALLOWED_APPLICATIONS} aplicaciones.", parent=window)
                return
            initial_dir = os.environ.get("ProgramFiles") or os.environ.get("LOCALAPPDATA") or str(Path.home())
            chosen = filedialog.askopenfilename(
                parent=window, title="Selecciona el .exe de una aplicación instalada", initialdir=initial_dir,
                filetypes=(("Aplicaciones Windows (*.exe)", "*.exe"),),
            )
            if not chosen:
                return
            _authorize_candidate_path(chosen)

        def pick_from_installed_apps() -> None:
            if len(current_records()) >= MAX_ALLOWED_APPLICATIONS:
                messagebox.showinfo("Límite alcanzado", f"La lista admite hasta {MAX_ALLOWED_APPLICATIONS} aplicaciones.", parent=window)
                return
            roots = []
            for env_k in ("ProgramFiles", "ProgramFiles(x86)"):
                val = os.environ.get(env_k)
                if val and Path(val).is_dir():
                    roots.append(Path(val))
            local_app = os.environ.get("LOCALAPPDATA")
            if local_app and (Path(local_app) / "Programs").is_dir():
                roots.append(Path(local_app) / "Programs")
            found: list[tuple[str, str]] = []
            seen_paths: set[str] = set()
            for r in roots:
                try:
                    for sub in r.iterdir():
                        if not sub.is_dir():
                            continue
                        for exe in sub.glob("*.exe"):
                            low_n = exe.name.casefold()
                            if low_n in BLOCKED_APPLICATION_NAMES or any(tok in exe.stem.casefold() for tok in ("unins", "setup", "install", "update", "crash", "helper")):
                                continue
                            norm_p = os.path.normcase(str(exe))
                            if norm_p not in seen_paths and is_windows_gui_executable(exe):
                                seen_paths.add(norm_p)
                                found.append((exe.name, str(exe)))
                        if len(found) >= 120:
                            break
                except OSError:
                    continue
            found.sort(key=lambda item: item[0].casefold())
            if not found:
                messagebox.showinfo("Sin resultados automáticos", "Usa «➕ Añadir .exe autorizado…» para buscar manualmente el ejecutable.", parent=window)
                return
            picker = tk.Toplevel(window)
            picker.title("Elegir aplicación instalada detectada")
            picker.geometry("760x420")
            picker.transient(window)
            picker.grab_set()
            p_frame = ttk.Frame(picker, padding=14)
            p_frame.pack(fill="both", expand=True)
            ttk.Label(p_frame, text="Selecciona una aplicación detectada en Program Files / LocalAppData\\Programs:", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))
            p_btns = ttk.Frame(p_frame)
            p_btns.pack(side="top", fill="x", pady=(0, 8))
            p_tree = ttk.Treeview(p_frame, columns=("name", "path"), show="headings", selectmode="browse", height=7)
            p_tree.heading("name", text="Aplicación")
            p_tree.heading("path", text="Ruta")
            p_tree.column("name", width=190, anchor="w")
            p_tree.column("path", width=520, anchor="w")
            p_tree.pack(fill="both", expand=True)
            for idx, (n_str, p_str) in enumerate(found):
                p_tree.insert("", "end", iid=str(idx), values=(n_str, p_str))

            def confirm_pick() -> None:
                sel = p_tree.selection()
                if not sel:
                    messagebox.showinfo("Selecciona una aplicación", "Elige una fila de la lista primero.", parent=picker)
                    return
                chosen_path = found[int(sel[0])][1]
                picker.destroy()
                _authorize_candidate_path(chosen_path)

            ttk.Button(p_btns, text="✅ Autorizar aplicación seleccionada", style="Accent.TButton", command=confirm_pick).pack(side="left", padx=(0, 8))
            ttk.Button(p_btns, text="Cancelar", command=picker.destroy).pack(side="left")

        def launch_application() -> None:
            selection = tree.selection()
            record = records_by_id.get(selection[0]) if selection else None
            if not record:
                return
            try:
                current = validate_local_application(record["path"])
                if any(current[key] != record.get(key) for key in ("path", "size", "mtime_ns")) or tuple(current["file_id"]) != tuple(record["file_id"]):
                    raise ValueError("La aplicación cambió desde que la autorizaste. Retírala y vuelve a añadirla si aún confías en ella.")
            except (OSError, ValueError) as exc:
                messagebox.showwarning("No se puede iniciar", str(exc), parent=window)
                return
            prompt = (
                f"Se iniciará solo este ejecutable, sin argumentos ni elevación:\n{record['path']}\n\n"
                "La aplicación queda fuera del control de Clara; podría abrir archivos, cambiar datos o conectarse a internet. "
                "Solo continúa si confías en el editor y la ruta. ¿Iniciarla ahora?"
            )
            if not messagebox.askyesno("Confirmar inicio", prompt, icon="warning", parent=window):
                status_var.set("Inicio cancelado; no se lanzó la aplicación.")
                return
            try:
                launch_allowed_application(record)
                logged = self._record_private_action_event("Iniciar aplicación autorizada", "Inicio solicitado; nombre/ruta omitidos")
                status_var.set("Windows recibió el inicio. Clara no puede detener ni controlar la aplicación después de lanzarla." + (" El registro local no pudo guardarse." if not logged else ""))
            except (OSError, ValueError) as exc:
                messagebox.showwarning("No se inició", str(exc), parent=window)

        def remove_application() -> None:
            selection = tree.selection()
            record = records_by_id.get(selection[0]) if selection else None
            if not record:
                return
            if not messagebox.askyesno("Retirar autorización", f"¿Retirar esta ruta de la lista?\n{record['path']}\n\nEsto no cerrará una aplicación que ya esté abierta.", parent=window):
                return
            records = [item for item in current_records() if os.path.normcase(os.path.abspath(item["path"])) != os.path.normcase(os.path.abspath(record["path"]))]
            if persist_records(records):
                logged = self._record_private_action_event("Retirar autorización de aplicación", "Permiso retirado; ruta omitida")
                refresh_list()
                status_var.set("Autorización retirada. No se cerró ninguna aplicación ya iniciada." + (" No se pudo guardar el evento de actividad." if not logged else ""))

        def update_selection(_event=None) -> None:
            selected = bool(tree.selection())
            launch_button.configure(state="normal" if selected else "disabled")
            remove_button.configure(state="normal" if selected else "disabled")

        add_button.configure(command=add_application)
        scan_button.configure(command=pick_from_installed_apps)
        launch_button.configure(command=launch_application)
        remove_button.configure(command=remove_application)
        tree.bind("<<TreeviewSelect>>", update_selection)
        refresh_list()
        if auto_prompt_add:
            window.after(200, add_application)

    def open_week_agenda(self) -> None:
        window = tk.Toplevel(self)
        window.title("Agenda semanal")
        window.geometry("1040x580")
        window.minsize(820, 440)
        window.transient(self)
        outer = ttk.Frame(window, padding=18)
        outer.pack(fill="both", expand=True)
        start_day = date.today()
        end_day = start_day + timedelta(days=6)
        ttk.Label(outer, text=f"Agenda · {start_day.strftime('%d/%m/%Y')} a {end_day.strftime('%d/%m/%Y')}", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Vista local de tareas, clases y bloques; los archivos .ics vinculados son solo lectura y no se sincronizan.").pack(anchor="w", pady=(4, 5))
        linked_status = ttk.Label(outer, text="")
        linked_status.pack(anchor="w", pady=(0, 6))
        actions = ttk.Frame(outer)
        actions.pack(side="top", fill="x", pady=(0, 8))
        tree = ttk.Treeview(outer, columns=("date", "time", "kind", "title", "subject"), show="headings", height=7)
        for col, label, width in (("date", "Fecha", 105), ("time", "Hora", 75), ("kind", "Tipo", 95), ("title", "Actividad", 390), ("subject", "Materia / lugar", 180)):
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor="w" if col in ("title", "subject") else "center")
        tree.pack(fill="both", expand=True)

        def refresh() -> None:
            tree.delete(*tree.get_children())
            events = []
            for offset in range(7):
                day = start_day + timedelta(days=offset)
                closure = day_off_for(self.db, day)
                if closure:
                    events.append((day, "23:59", "Calendario", "Día sin clases", closure["note"] or "", None))
                meetings = classes_for_date(self.db, day)
                for meeting in meetings:
                    events.append((day, str(meeting["start_time"]), "Clase especial" if meeting["source"] == "exception" else "Clase", str(meeting["name"]), meeting["location"] or "", None))
                tasks = self.db.execute("SELECT title,subject,due_time,done FROM tasks WHERE due_date=?", (day.isoformat(),)).fetchall()
                for task in tasks:
                    events.append((day, task["due_time"] or "23:59", "Tarea hecha" if task["done"] else "Tarea", task["title"], task["subject"] or "", None))
                blocks = self.db.execute("SELECT id,title,start_time,end_time,notes FROM plan_blocks WHERE block_date=?", (day.isoformat(),)).fetchall()
                for block in blocks:
                    events.append((day, block["start_time"], "Bloque local", block["title"], block["notes"] or "", f"block-{block['id']}"))
            linked_events, link_status = read_linked_ics_events(self.settings.get("calendar_ics_path", ""), start_day, end_day)
            linked_status.configure(text=link_status)
            for index,event in enumerate(linked_events):
                day=date.fromisoformat(str(event["due_date"]))
                event_time=str(event["due_time"] or "23:59")
                duplicate=self.db.execute("SELECT 1 FROM tasks WHERE external_uid=? AND due_date=? LIMIT 1",(event["uid"],event["due_date"])).fetchone()
                if not duplicate:
                    duplicate=self.db.execute("SELECT 1 FROM tasks WHERE done=0 AND title=? AND due_date=? AND COALESCE(due_time,'')=COALESCE(?,'') LIMIT 1",(event["title"],event["due_date"],event["due_time"])).fetchone()
                conflict=bool(linked_event_conflicts(self.db,event))
                kind="ICS · TRASLAPE" if conflict else "ICS · coincide" if duplicate else "ICS · solo lectura"
                subject="Conflicto con agenda local" if conflict else "Coincide con tarea local" if duplicate else ("Todo el día" if not event["due_time"] else "Duración desconocida" if not event["end_time"] else "")
                events.append((day,event_time,kind,str(event["title"]),subject,f"ics-{index}"))
            events.sort(key=lambda e: (e[0], e[1], e[2]))
            for index, (day, time_value, kind, title, subject, block_iid) in enumerate(events):
                tree.insert("", "end", iid=block_iid or f"event-{index}", values=(day.strftime("%a %d/%m"), "Todo el día" if time_value == "23:59" else time_value, kind, title, subject))
            undated = self.db.execute("SELECT COUNT(*) FROM tasks WHERE done=0 AND due_date IS NULL").fetchone()[0]
            window.title(f"Agenda semanal · {undated} tarea(s) sin fecha")

        def link_local_ics() -> None:
            selected=filedialog.askopenfilename(parent=window,title="Vincular archivo local iCalendar",filetypes=(("Calendario iCalendar","*.ics"),))
            if not selected:return
            local_path=str(Path(selected).resolve())
            _preview,status=read_linked_ics_events(local_path,start_day,end_day)
            if status.startswith(("Solo se admiten", "El archivo ICS supera", "No se pudo leer")):
                messagebox.showerror("No se pudo vincular",status,parent=window);return
            if not messagebox.askyesno("Vincular calendario local",f"Clara leerá este archivo local cada vez que actualices la agenda. No modificará el archivo, no copiará los eventos a tus tareas y no enviará datos a un servicio. El vínculo (ruta local) se guarda en preferencias y respaldos.\n\n{Path(local_path).name}\n\nLas recurrencias se omiten; puedes quitar el vínculo después. ¿Continuar?",parent=window):return
            self.settings["calendar_ics_path"]=local_path
            save_settings(self.settings)
            refresh()

        def unlink_local_ics() -> None:
            current=self.settings.get("calendar_ics_path","")
            if not current:
                messagebox.showinfo("Sin vínculo","No hay un archivo ICS vinculado.",parent=window);return
            if messagebox.askyesno("Quitar vínculo",f"¿Dejar de leer “{Path(current).name}”? El archivo no se borrará.",parent=window):
                self.settings["calendar_ics_path"]=""
                save_settings(self.settings)
                refresh()

        ttk.Button(actions, text="Actualizar", command=refresh).pack(side="left")
        ttk.Button(actions, text="+ Bloque local", style="Accent.TButton", command=lambda: self.open_plan_block_form(window, on_saved=refresh)).pack(side="left", padx=6)
        ttk.Button(actions, text="Editar bloque", command=lambda: self.edit_plan_block_from_agenda(tree, refresh)).pack(side="left", padx=6)
        ttk.Button(actions, text="Eliminar bloque", command=lambda: self.delete_plan_block_from_agenda(tree, refresh)).pack(side="left")
        ttk.Button(actions, text="Vincular .ics local…", command=link_local_ics).pack(side="left", padx=(10,0))
        ttk.Button(actions, text="Quitar vínculo", command=unlink_local_ics).pack(side="left", padx=6)
        ttk.Button(actions, text="Importar .ics…", command=self.import_ical).pack(side="right", padx=8)
        ttk.Button(actions, text="Exportar .ics…", command=self.export_ical).pack(side="right")
        refresh()

    def _block_conflicts(self, block_date: date, start_time: str, end_time: str, exclude_id: int | None = None) -> list[str]:
        start = datetime.combine(block_date, datetime.strptime(start_time, "%H:%M").time())
        end = datetime.combine(block_date, datetime.strptime(end_time, "%H:%M").time())
        conflicts = []
        for meeting in classes_for_date(self.db, block_date):
            other_start = datetime.combine(block_date, datetime.strptime(str(meeting["start_time"]), "%H:%M").time())
            other_end = datetime.combine(block_date, datetime.strptime(str(meeting["end_time"]), "%H:%M").time()) if meeting["end_time"] else other_start + timedelta(hours=1)
            if start < other_end and end > other_start:
                conflicts.append(f"clase “{meeting['name']}” {meeting['start_time']}–{meeting['end_time'] or ' +1 h'}")
        rows = self.db.execute("SELECT id,title,start_time,end_time FROM plan_blocks WHERE block_date=?", (block_date.isoformat(),)).fetchall()
        for row in rows:
            if row["id"] == exclude_id:
                continue
            other_start = datetime.combine(block_date, datetime.strptime(row["start_time"], "%H:%M").time())
            other_end = datetime.combine(block_date, datetime.strptime(row["end_time"], "%H:%M").time())
            if start < other_end and end > other_start:
                conflicts.append(f"bloque “{row['title']}” {row['start_time']}–{row['end_time']}")
        return conflicts

    def open_plan_block_form(self, parent=None, existing=None, prefill=None, on_saved=None) -> None:
        prefill = prefill or {}
        parent = parent or self
        window = tk.Toplevel(parent)
        window.title("Editar bloque local" if existing else "Nuevo bloque local")
        window.transient(parent)
        window.grab_set()
        window.resizable(False, False)
        box = ttk.Frame(window, padding=18)
        box.pack(fill="both", expand=True)
        ttk.Label(box, text="Bloque de agenda local", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        title_var = tk.StringVar(value=(existing["title"] if existing else str(prefill.get("title") or "")))
        date_var = tk.StringVar(value=(existing["block_date"] if existing else str(prefill.get("block_date") or "")))
        start_var = tk.StringVar(value=(existing["start_time"] if existing else str(prefill.get("start_time") or "")))
        end_var = tk.StringVar(value=(existing["end_time"] if existing else str(prefill.get("end_time") or "")))
        notes_var = tk.StringVar(value=(existing["notes"] or "") if existing else str(prefill.get("notes") or ""))
        for row, label, variable, width in ((1,"Título",title_var,42),(3,"Fecha (AAAA-MM-DD)",date_var,18),(5,"Inicio (HH:MM)",start_var,12),(7,"Fin (HH:MM)",end_var,12),(9,"Notas (opcional)",notes_var,42)):
            ttk.Label(box, text=label).grid(row=row, column=0, sticky="w", pady=(0, 3))
            ttk.Entry(box, textvariable=variable, width=width).grid(row=row+1, column=0, sticky="w", pady=(0, 8))
        ttk.Label(box, text="Este bloque se guarda solo en la agenda local y puede editarse o borrarse después.", wraplength=420, foreground="#91aabd").grid(row=11, column=0, columnspan=2, sticky="w", pady=(0, 10))

        def save() -> None:
            title = title_var.get().strip()
            try:
                block_date = date.fromisoformat(date_var.get().strip())
                start = datetime.strptime(start_var.get().strip(), "%H:%M")
                end = datetime.strptime(end_var.get().strip(), "%H:%M")
            except ValueError:
                messagebox.showwarning("Revisa fecha y hora", "Usa AAAA-MM-DD para la fecha y HH:MM en formato de 24 horas.", parent=window)
                return
            if not title:
                messagebox.showwarning("Falta el título", "Escribe el nombre del bloque.", parent=window)
                return
            if end <= start:
                messagebox.showwarning("Duración no válida", "La hora final debe ser posterior a la hora inicial, dentro del mismo día.", parent=window)
                return
            conflicts = self._block_conflicts(block_date, start.strftime("%H:%M"), end.strftime("%H:%M"), existing["id"] if existing else None)
            if conflicts and not messagebox.askyesno("Hay un traslape", "Este horario coincide con " + ", ".join(conflicts) + ". ¿Guardar de todos modos?", parent=window):
                return
            values = (title, block_date.isoformat(), start.strftime("%H:%M"), end.strftime("%H:%M"), notes_var.get().strip() or None)
            if existing:
                self.db.execute("UPDATE plan_blocks SET title=?,block_date=?,start_time=?,end_time=?,notes=? WHERE id=?", (*values, existing["id"]))
            else:
                self.db.execute("INSERT INTO plan_blocks(title,block_date,start_time,end_time,notes,created_at) VALUES(?,?,?,?,?,?)", (*values, datetime.now().isoformat(timespec="seconds")))
            self.db.commit()
            window.destroy()
            if on_saved:
                on_saved()

        controls = ttk.Frame(box)
        controls.grid(row=12, column=0, columnspan=2, sticky="e")
        ttk.Button(controls, text="Cancelar", command=window.destroy).pack(side="left", padx=6)
        ttk.Button(controls, text="Guardar bloque", style="Accent.TButton", command=save).pack(side="left")

    def edit_plan_block_from_agenda(self, tree, refresh) -> None:
        selected = tree.selection()
        if not selected or not selected[0].startswith("block-"):
            messagebox.showinfo("Selecciona un bloque", "Selecciona un bloque local de la agenda para editarlo.", parent=tree.winfo_toplevel())
            return
        block_id = int(selected[0].split("-", 1)[1])
        row = self.db.execute("SELECT * FROM plan_blocks WHERE id=?", (block_id,)).fetchone()
        if row:
            self.open_plan_block_form(tree.winfo_toplevel(), dict(row), on_saved=refresh)

    def delete_plan_block_from_agenda(self, tree, refresh) -> None:
        selected = tree.selection()
        if not selected or not selected[0].startswith("block-"):
            messagebox.showinfo("Selecciona un bloque", "Selecciona un bloque local de la agenda para eliminarlo.", parent=tree.winfo_toplevel())
            return
        block_id = int(selected[0].split("-", 1)[1])
        row = self.db.execute("SELECT title FROM plan_blocks WHERE id=?", (block_id,)).fetchone()
        if row and messagebox.askyesno("Eliminar bloque", f"¿Eliminar el bloque “{row['title']}” de la agenda local?", parent=tree.winfo_toplevel()):
            self.db.execute("DELETE FROM plan_blocks WHERE id=?", (block_id,))
            self.db.commit()
            refresh()

    def start_afternoon_plan(self) -> None:
        target_day = date.today()
        drafts, omitted = build_afternoon_draft(self.db, target_day, datetime.now())
        if not drafts:
            self.append_chat("Asistente", "No encontré tareas pendientes con espacio libre suficiente para proponer bloques esta tarde. No cambié tu agenda. Puedes decirme qué tarea quieres incluir o revisar las clases y bloques existentes en Agenda semanal.")
            return
        preview = "\n".join(f"• {item['start_time']}–{item['end_time']} · {item['title']}" for item in drafts)
        note = " Son propuestas de 45 minutos, separadas por 15 minutos, y puedes editarlas antes de guardar." 
        if omitted:
            note += f" Dejé {omitted} tarea(s) fuera del borrador por el límite de cuatro bloques o por falta de espacio."
        self.append_chat("Asistente", "Borrador local para esta tarde (no guardado):\n" + preview + "\n" + note + " Revisa el editor; solo se añadirán a la agenda si confirmas.")
        self.open_plan_draft_dialog(drafts, omitted)

    def open_plan_draft_dialog(self, drafts: list[dict[str, str]], omitted: int = 0) -> None:
        window = tk.Toplevel(self)
        window.title("Revisar plan de la tarde")
        window.geometry("790x430")
        window.transient(self)
        outer = ttk.Frame(window, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Borrador de planificación · aún no guardado", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Duración base sugerida: 45 min; pausa propuesta: 15 min. Puedes editar o quitar cada bloque. Se respetaron clases y bloques ya guardados; no se modifican tareas.", wraplength=730).pack(anchor="w", pady=(4, 8))
        actions=ttk.Frame(outer);actions.pack(side="top",fill="x",pady=(0,8))
        tree = ttk.Treeview(outer, columns=("date","start","end","title"), show="headings", selectmode="browse", height=5)
        for key,label,width in (("date","Fecha",105),("start","Inicio",80),("end","Fin",80),("title","Tarea / actividad",450)):
            tree.heading(key,text=label); tree.column(key,width=width,anchor="w")
        tree.pack(fill="both",expand=True)
        def render() -> None:
            tree.delete(*tree.get_children())
            for index,item in enumerate(drafts):
                tree.insert("","end",iid=str(index),values=(item["block_date"],item["start_time"],item["end_time"],item["title"]))
        render()

        def edit_selected() -> None:
            selected=tree.selection()
            if not selected:
                messagebox.showinfo("Selecciona un bloque","Elige un bloque del borrador para editarlo.",parent=window); return
            index=int(selected[0]); item=drafts[index]
            editor=tk.Toplevel(window); editor.title("Editar borrador"); editor.transient(window); editor.grab_set(); editor.resizable(False,False)
            box=ttk.Frame(editor,padding=16); box.pack(fill="both",expand=True)
            fields=("title","block_date","start_time","end_time"); labels=("Título","Fecha (AAAA-MM-DD)","Inicio (HH:MM)","Fin (HH:MM)")
            vars_=[]
            for row,(key,label) in enumerate(zip(fields,labels)):
                ttk.Label(box,text=label).grid(row=row*2,column=0,sticky="w",pady=(0,3))
                var=tk.StringVar(value=item[key]); vars_.append(var)
                ttk.Entry(box,textvariable=var,width=44 if row==0 else 20).grid(row=row*2+1,column=0,sticky="w",pady=(0,8))
            def save_edit() -> None:
                title,date_text,start_text,end_text=(var.get().strip() for var in vars_)
                try:
                    date.fromisoformat(date_text); start=datetime.strptime(start_text,"%H:%M"); end=datetime.strptime(end_text,"%H:%M")
                except ValueError:
                    messagebox.showwarning("Revisa los datos","Usa AAAA-MM-DD y HH:MM en formato de 24 horas.",parent=editor); return
                if not title or end<=start:
                    messagebox.showwarning("Datos no válidos","Escribe un título y una hora final posterior a la inicial.",parent=editor); return
                item.update({"title":title,"block_date":date_text,"start_time":start.strftime("%H:%M"),"end_time":end.strftime("%H:%M")})
                render(); editor.destroy()
            buttons=ttk.Frame(box);buttons.grid(row=8,column=0,sticky="e")
            ttk.Button(buttons,text="Cancelar",command=editor.destroy).pack(side="left",padx=5)
            ttk.Button(buttons,text="Aplicar al borrador",command=save_edit).pack(side="left")

        def remove_selected() -> None:
            selected=tree.selection()
            if not selected: return
            drafts.pop(int(selected[0])); render()

        def confirm_save() -> None:
            if not drafts:
                messagebox.showinfo("Borrador vacío","No hay bloques para guardar.",parent=window); return
            overlap_notes=[]
            seen=[]
            for item in drafts:
                block_day=date.fromisoformat(item["block_date"])
                conflicts=self._block_conflicts(block_day,item["start_time"],item["end_time"])
                if conflicts: overlap_notes.append(f"{item['title']}: " + ", ".join(conflicts))
                start=datetime.strptime(item["start_time"],"%H:%M"); end=datetime.strptime(item["end_time"],"%H:%M")
                for prior_day,prior_start,prior_end,prior_title in seen:
                    if prior_day==block_day and start<prior_end and end>prior_start:
                        overlap_notes.append(f"{item['title']} coincide con “{prior_title}” del mismo borrador")
                seen.append((block_day,start,end,item["title"]))
            details="\n".join(f"• {item['block_date']} {item['start_time']}–{item['end_time']} · {item['title']}" for item in drafts)
            if overlap_notes:
                details += "\n\nAdvertencia de traslapes (puedes volver y editar):\n" + "\n".join("• "+note for note in overlap_notes)
            if not messagebox.askyesno("Confirmar y guardar bloques", "Se añadirán estos bloques a tu agenda local. No se crearán ni modificarán tareas.\n\n"+details+"\n\n¿Confirmas?",parent=window): return
            try:
                with self.db:
                    for item in drafts:
                        self.db.execute("INSERT INTO plan_blocks(title,block_date,start_time,end_time,notes,created_at) VALUES(?,?,?,?,?,?)",(item["title"],item["block_date"],item["start_time"],item["end_time"],item.get("notes"),datetime.now().isoformat(timespec="seconds")))
            except Exception as exc:
                messagebox.showerror("No se guardó el plan",f"No pude guardar los bloques: {exc}",parent=window); return
            count=len(drafts); window.destroy()
            self.append_chat("Asistente",f"Guardé {count} bloque(s) en la agenda local. Puedes revisarlos, editarlos o borrarlos en Agenda semanal.")

        ttk.Button(actions,text="Confirmar y guardar…",style="Accent.TButton",command=confirm_save).pack(side="left")
        ttk.Button(actions,text="Editar seleccionado…",command=edit_selected).pack(side="left",padx=8)
        ttk.Button(actions,text="Quitar del borrador",command=remove_selected).pack(side="left")
        ttk.Button(actions,text="Cancelar",command=window.destroy).pack(side="right")

    def import_ical(self) -> None:
        source = filedialog.askopenfilename(parent=self, title="Importar eventos iCalendar", filetypes=(("iCalendar", "*.ics"),))
        if not source:
            return
        try:
            path = Path(source)
            if path.stat().st_size > 5 * 1024 * 1024:
                raise ValueError("El archivo supera el límite de 5 MB.")
            text = path.read_text(encoding="utf-8-sig")
            events, skipped_recurring, skipped_own_events = parse_ical_events(text)
            today = date.today()
            deadline = today + timedelta(days=365)
            candidates = [event for event in events if today.isoformat() <= str(event["due_date"]) <= deadline.isoformat()]
            seen: set[str] = set()
            pending = []
            for event in candidates:
                uid = str(event["uid"])
                if uid in seen:
                    continue
                seen.add(uid)
                by_uid = self.db.execute("SELECT 1 FROM tasks WHERE external_uid=? LIMIT 1", (uid,)).fetchone()
                by_title_date = self.db.execute("SELECT 1 FROM tasks WHERE done=0 AND title=? AND due_date=? LIMIT 1", (event["title"], event["due_date"])).fetchone()
                if not by_uid and not by_title_date:
                    pending.append(event)
            if not pending:
                messagebox.showinfo("No hay eventos nuevos", f"No encontré eventos nuevos dentro del próximo año. Se omitieron {skipped_recurring} eventos recurrentes/cancelados y {skipped_own_events} eventos/bloques de agenda de esta aplicación.", parent=self)
                return
            preview = "\n".join(f"• {event['due_date']} {event['due_time'] or 'todo el día'} — {event['title']}" for event in pending[:8])
            if len(pending) > 8:
                preview += f"\\n… y {len(pending) - 8} evento(s) más."
            details = (f"Se añadirán {len(pending)} eventos como tareas. Solo se importan eventos no recurrentes del próximo año; no se importa la descripción ni se sincronizan cambios.\n\n" + preview + f"\n\nOmitidos: {skipped_recurring} recurrentes/cancelados y {skipped_own_events} eventos/bloques de agenda de esta aplicación.")
            if not messagebox.askyesno("Confirmar importación", details, parent=self):
                return
            added = 0
            try:
                self.db.execute("BEGIN IMMEDIATE")
                for event in pending:
                    try:
                        self.db.execute("INSERT INTO tasks(title,due_date,priority,done,created_at,due_time,external_uid) VALUES(?,?,?,?,?,?,?)", (event["title"], event["due_date"], "Normal", 0, datetime.now().isoformat(timespec="seconds"), event["due_time"], event["uid"]))
                        added += 1
                    except sqlite3.IntegrityError:
                        continue
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
            self.refresh_tasks()
            self.append_chat("Asistente", f"Importé {added} evento(s) de calendario como tareas. Revisa fechas y avisos.")
            messagebox.showinfo("Importación terminada", f"Se añadieron {added} tareas. Revisa la lista y edita cualquier fecha u hora.", parent=self)
        except (OSError, UnicodeError, ValueError, zipfile.BadZipFile) as exc:
            messagebox.showerror("No se pudo importar", f"El archivo no es válido o no se pudo leer: {exc}", parent=self)
        except Exception as exc:
            messagebox.showerror("Error de importación", f"No se pudo completar la importación; revisa la base local: {exc}", parent=self)

    def export_ical(self) -> None:
        destination = filedialog.asksaveasfilename(parent=self, title="Exportar agenda", defaultextension=".ics", filetypes=(("Calendario iCalendar", "*.ics"),))
        if not destination:
            return
        if not messagebox.askyesno("Exportar datos personales", "El archivo incluirá tareas con fecha, bloques locales y clases para las próximas 12 semanas. Las tareas sin fecha no se exportan; las reglas repetitivas se incluyen solo como texto en la ocurrencia. ¿Continuar?", parent=self):
            return
        def escape(value: str) -> str:
            return str(value).replace("\\", "\\\\").replace("\r\n", "\n").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Asistente Personal//Agenda ES", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
        events_count = 0
        today = date.today()
        tasks = self.db.execute("SELECT * FROM tasks WHERE done=0 AND due_date IS NOT NULL AND due_date>=? ORDER BY due_date", (today.isoformat(),)).fetchall()
        for task in tasks:
            due = date.fromisoformat(task["due_date"])
            uid = f"task-{task['id']}-{due.strftime('%Y%m%d')}@asistente.local"
            description = f"Prioridad: {task['priority']}"
            if task["subject"]:
                description += f"\nMateria: {task['subject']}"
            if task["description"]:
                description += f"\nNotas: {task['description']}"
            if task["repeat_rule"] in ("daily", "weekly"):
                recurrence_name = "diaria" if task["repeat_rule"] == "daily" else "semanal"
                description += f"\nRecurrencia local: {recurrence_name}. iCalendar incluye solo esta ocurrencia."
            if task["due_time"]:
                description += f"\nHora de aviso: {task['due_time']}"
            lines.extend(("BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}", f"DTSTART;VALUE=DATE:{due.strftime('%Y%m%d')}", f"DTEND;VALUE=DATE:{(due + timedelta(days=1)).strftime('%Y%m%d')}", f"SUMMARY:{escape(task['title'])}", f"DESCRIPTION:{escape(description)}", "END:VEVENT"))
            events_count += 1
        block_deadline = today + timedelta(days=12 * 7)
        for block in self.db.execute("SELECT * FROM plan_blocks WHERE block_date BETWEEN ? AND ? ORDER BY block_date,start_time", (today.isoformat(), block_deadline.isoformat())):
            day = date.fromisoformat(block["block_date"])
            start_dt = datetime.combine(day, datetime.strptime(block["start_time"], "%H:%M").time())
            end_dt = datetime.combine(day, datetime.strptime(block["end_time"], "%H:%M").time())
            lines.extend(("BEGIN:VEVENT", f"UID:plan-block-{block['id']}@asistente.local", f"DTSTAMP:{stamp}", f"DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}", f"DTEND:{end_dt.strftime('%Y%m%dT%H%M%S')}", f"SUMMARY:{escape('Bloque local: ' + block['title'])}", f"DESCRIPTION:{escape(block['notes'] or 'Bloque local guardado desde la agenda de Clara.')}", "END:VEVENT"))
            events_count += 1
        monday = today - timedelta(days=today.weekday())
        for offset in range(12 * 7):
            day = monday + timedelta(days=offset)
            closure = day_off_for(self.db, day)
            if closure and day >= today:
                summary = "Día sin clases" + (f": {closure['note']}" if closure["note"] else "")
                lines.extend(("BEGIN:VEVENT", f"UID:school-closure-{day.strftime('%Y%m%d')}@asistente.local", f"DTSTAMP:{stamp}", f"DTSTART;VALUE=DATE:{day.strftime('%Y%m%d')}", f"DTEND;VALUE=DATE:{(day + timedelta(days=1)).strftime('%Y%m%d')}", f"SUMMARY:{escape(summary)}", "END:VEVENT"))
                events_count += 1
            for meeting in classes_for_date(self.db, day):
                if day < today or (day == today and str(meeting["start_time"]) < datetime.now().strftime("%H:%M")):
                    continue
                start_value = datetime.strptime(str(meeting["start_time"]), "%H:%M").time()
                start_dt = datetime.combine(day, start_value)
                uid = f"{meeting['uid']}-{day.strftime('%Y%m%d')}@asistente.local"
                summary = f"Clase: {meeting['name']}"
                description = "Horario de clase exportado desde Asistente Personal."
                if meeting["source"] == "exception":
                    description += "\nClase especial de una sola fecha."
                if not meeting["end_time"]:
                    description += "\nDuración de 1 hora asumida porque no se indicó hora de fin."
                end_line = f"DTEND:{datetime.combine(day, datetime.strptime(str(meeting['end_time']), '%H:%M').time()).strftime('%Y%m%dT%H%M%S')}" if meeting["end_time"] else "DURATION:PT1H"
                lines.extend(("BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}", f"DTSTART:{start_dt.strftime('%Y%m%dT%H%M%S')}", end_line, f"SUMMARY:{escape(summary)}", f"DESCRIPTION:{escape(description)}"))
                if meeting["location"]:
                    lines.append(f"LOCATION:{escape(str(meeting['location']))}")
                lines.append("END:VEVENT")
                events_count += 1
        lines.append("END:VCALENDAR")
        try:
            Path(destination).write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))
            messagebox.showinfo("Agenda exportada", f"Se exportaron {events_count} evento(s) a:\n{destination}", parent=self)
        except Exception as exc:
            messagebox.showerror("No se pudo exportar", str(exc), parent=self)

    def open_diagnostics(self) -> None:
        window = tk.Toplevel(self)
        window.title("Diagnóstico del asistente y estado del equipo")
        window.geometry("860x540")
        window.transient(self)
        outer = ttk.Frame(window, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Revisión guiada de componentes y estado del equipo en tiempo real", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Comprueba disco, memoria RAM, batería y configuración local. No escanea archivos personales, no enciende el micrófono ni envía tareas/clases a internet.", wraplength=800).pack(anchor="w", pady=(4, 8))
        top_bar = ttk.Frame(outer)
        top_bar.pack(side="top", fill="x", pady=(0, 8))
        run_button = ttk.Button(top_bar, text="🔄 Revisar ahora", style="Accent.TButton")
        run_button.pack(side="left", padx=(0, 10))
        ttk.Button(
            top_bar,
            text="💻 Enviar reporte del equipo al chat",
            command=lambda: self.append_chat("Asistente", format_realtime_pc_status_report(collect_realtime_pc_status(self.db))),
        ).pack(side="left", padx=(0, 10))
        status = ttk.Label(top_bar, text="Pulsa para iniciar los chequeos.")
        status.pack(side="left")
        tree = ttk.Treeview(outer, columns=("state", "item", "detail"), show="headings", height=9)
        for col, label, width in (("state", "Estado", 105), ("item", "Componente", 190), ("detail", "Detalle / siguiente paso", 510)):
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor="w")
        tree.pack(fill="both", expand=True)
        self.diagnostic_tree = tree
        self.diagnostic_status = status
        self.diagnostic_run_button = run_button

        def run() -> None:
            tree.delete(*tree.get_children())
            status.configure(text="Revisando configuración local y recursos del equipo…")
            run_button.configure(state="disabled")
            threading.Thread(target=lambda: self.ai_results.put(("diagnostics", self.collect_diagnostics())), daemon=True).start()

        run_button.configure(command=run)
        run()

    def collect_diagnostics(self) -> list[tuple[str, str, str]]:
        results: list[tuple[str, str, str]] = []
        def add(state: str, component: str, detail: str) -> None:
            results.append((state, component, detail))

        pc_snap = collect_realtime_pc_status()
        add(
            "OK" if float(pc_snap.get("disk_free_gb") or 0.0) >= 2.0 else "Aviso",
            "Disco local",
            f"{pc_snap.get('disk_free_gb')} GB libres de {pc_snap.get('disk_total_gb')} GB ({pc_snap.get('disk_used_percent')}% en uso)",
        )
        if float(pc_snap.get("ram_total_gb") or 0.0) > 0:
            add(
                "OK" if float(pc_snap.get("ram_avail_gb") or 0.0) >= 1.0 else "Aviso",
                "Memoria RAM",
                f"{pc_snap.get('ram_avail_gb')} GB disponibles de {pc_snap.get('ram_total_gb')} GB ({pc_snap.get('ram_used_percent')}% en uso)",
            )
        add("OK", "Energía / CPU", f"{pc_snap.get('battery_status')} · {pc_snap.get('cpu_cores')} núcleos lógicos")
        add("OK" if sys.version_info >= (3, 10) else "Aviso", "Python", f"{sys.version.split()[0]}" + (" · compatible" if sys.version_info >= (3, 10) else " · se recomienda Python 3.10 o posterior"))
        add("OK", "Interfaz", f"Tkinter {tk.TkVersion}")
        try:
            db = sqlite3.connect(DB_PATH)
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            counts = {}
            for table in ("tasks", "classes", "class_exceptions", "routines", "memories", "security_events"): 
                counts[table] = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] if table in tables else 0
            db.close()
            add("OK", "Base de datos", f"Lectura correcta · {counts['tasks']} tareas, {counts['classes']} clases, {counts['class_exceptions']} excepciones escolares, {counts['routines']} rutinas, {counts['memories']} recuerdos")
        except Exception as exc:
            add("Error", "Base de datos", f"No se pudo leer {DB_PATH}: {exc}")
        try:
            settings = load_settings()
            add("OK", "Preferencias", f"Rutina {settings['morning_time']} · {settings['weather_location']} · titulares {settings['news_topic']}")
        except Exception as exc:
            add("Aviso", "Preferencias", str(exc))
        try:
            with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2) as response:
                model_names = [m.get("name") for m in json.loads(response.read().decode("utf-8")).get("models", [])]
            add("OK" if model_names else "Aviso", "Ollama", (", ".join(model_names) if model_names else "Servidor local activo, pero no hay modelos descargados; instala uno con ollama pull.") )
        except Exception:
            add("Opcional", "Ollama", "No está activo en localhost:11434. Las tareas y rutinas siguen funcionando; abre Ollama y pulsa Detectar Ollama si quieres el chat.")
        toast_ok = importlib.util.find_spec("winotify") is not None
        tray_ok = importlib.util.find_spec("pystray") is not None and importlib.util.find_spec("PIL") is not None
        if sys.platform == "win32":
            add("OK" if toast_ok else "Opcional", "Avisos nativos", "winotify disponible; la entrega depende de la configuración de Windows." if toast_ok else "Instala los complementos opcionales para habilitar toast nativo; el popup de Clara sigue disponible.")
            add("OK" if tray_ok else "Opcional", "Bandeja del sistema", "pystray/Pillow disponibles." if tray_ok else "Instala pystray y Pillow para minimizar a la bandeja; si no están, Clara cierra normalmente.")
        vosk_ok = importlib.util.find_spec("vosk") is not None
        audio_ok = importlib.util.find_spec("sounddevice") is not None
        model_path = APP_BASE_DIR / "models" / "vosk-model-small-es-0.42"
        if vosk_ok and audio_ok and model_path.is_dir():
            add("OK", "Voz de entrada", "Paquetes y modelo local encontrados. El micrófono no se ha activado durante este diagnóstico.")
        else:
            add("Opcional", "Voz de entrada", "Para habilitarla, instala vosk/sounddevice y coloca el modelo español en models/vosk-model-small-es-0.42.")
        tts_ok = importlib.util.find_spec("pyttsx3") is not None
        add("OK" if tts_ok else "Opcional", "Voz de salida", "pyttsx3 instalado; depende de una voz del sistema." if tts_ok else "Instala pyttsx3 y una voz española de Windows para leer respuestas.")
        if os.name == "nt":
            command = "@('AsistentePersonal-Manana','AsistentePersonal-Recordatorios') | ForEach-Object {$t=Get-ScheduledTask -TaskName $_ -ErrorAction SilentlyContinue; if($t){$t.TaskName + ':' + $t.State}}"
            try:
                result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True, text=True, timeout=8, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
                found = result.stdout.strip().splitlines()
                expected = {"AsistentePersonal-Manana", "AsistentePersonal-Recordatorios"}
                present = {line.split(":", 1)[0] for line in found}
                missing = expected - present
                if not missing:
                    add("OK", "Tareas de Windows", "Resumen matutino y comprobación de recordatorios aparecen en el Programador de tareas.")
                else:
                    add("Aviso", "Tareas de Windows", "Faltan " + ", ".join(sorted(missing)) + "; ejecuta programar_rutina.bat para instalarlas o actualizarlas.")
            except Exception as exc:
                add("Aviso", "Tareas de Windows", f"No se pudieron comprobar: {exc}")
            add("Manual", "Microsoft Defender", "Abre Seguridad y alertas para una consulta separada, de solo lectura.")
        else:
            add("No comprobable", "Windows", "Este chequeo se ejecuta fuera de Windows; prueba Programador de tareas y Defender en tu PC.")
        add("Manual", "Internet", "Noticias y clima se consultan al abrir la rutina matutina; este diagnóstico no contacta esos servicios.")
        return results

    def open_backup_tools(self) -> None:
        window = tk.Toplevel(self)
        window.title("Copias de seguridad")
        window.transient(self)
        outer = ttk.Frame(window, padding=22)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Respaldar o restaurar tus datos", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(outer, text="El respaldo incluye tareas, clases, excepciones escolares, bloques de agenda, rutinas, recuerdos, notas, historial de recordatorios/acciones y preferencias; también incluye turnos de conversación si activaste su guardado. El archivo NO está cifrado; guárdalo en un lugar privado. La API key de VirusTotal se cifra por separado con DPAPI y nunca se incluye en el respaldo.", wraplength=480).pack(anchor="w", pady=(8, 16))
        ttk.Button(outer, text="Exportar respaldo…", style="Accent.TButton", command=self.export_backup).pack(anchor="w", pady=4)
        ttk.Button(outer, text="Restaurar respaldo…", command=self.import_backup).pack(anchor="w", pady=4)
        ttk.Button(outer, text="🔍 Vista previa migración Viernes (solo lectura)…", command=lambda: self.open_viernes_migration_preview(window)).pack(anchor="w", pady=4)
        ttk.Label(outer, text="Restaurar reemplaza los datos actuales. Antes se guarda automáticamente una copia local de seguridad. La vista previa de Viernes es de solo lectura y no modifica tu base de datos.", wraplength=480, foreground="#f2c77b").pack(anchor="w", pady=(12, 0))
        ttk.Separator(outer).pack(fill="x", pady=14)
        ttk.Button(outer, text="Eliminar todos mis datos locales…", command=self.erase_all_data).pack(anchor="w", pady=4)
        ttk.Label(outer, text="La eliminación no borra ZIP que exportaste a otras carpetas; tendrás que eliminarlos por separado.", wraplength=480, foreground="#f2c77b").pack(anchor="w", pady=(4, 0))

    def open_viernes_migration_preview(self, parent: tk.Misc | None = None) -> None:
        """Show a read-only preview of Viernes JSON data without writing anything to SQLite."""
        default_dir = APP_BASE_DIR.parent / "Bienvenido_Señor"
        agenda_path = default_dir / "viernes_agenda.json"
        config_path = default_dir / "viernes_config.json"
        if not agenda_path.is_file() and not config_path.is_file():
            selected = filedialog.askopenfilename(
                parent=parent or self,
                title="Selecciona viernes_agenda.json para vista previa (solo lectura)",
                filetypes=[("JSON de Viernes", "*.json")],
            )
            if not selected:
                return
            agenda_path = Path(selected)
            config_path = agenda_path.parent / "viernes_config.json"
        try:
            preview = preview_viernes_migration(agenda_path, config_path if config_path.is_file() else None, self.db)
        except Exception as exc:
            messagebox.showerror("Error en vista previa", f"No se pudo leer el archivo JSON de Viernes: {exc}", parent=parent or self)
            return
        lines = [
            "Vista previa de migración desde Viernes (100 % SOLO LECTURA):",
            f"• Escrituras realizadas en tu base de datos: {preview['writes_performed']} (ningún dato fue alterado)",
            f"• Tareas únicas con fecha candidatas a importar: {len(preview['candidate_tasks'])}",
            f"• Duplicados omitidos (ya existen en Clara): {preview['skipped_duplicates']}",
            f"• Eventos recurrentes omitidos (Clara nunca infiere rutinas automáticamente): {preview['skipped_recurring']}",
            f"• Días con materias en viernes_config.json (solo informativo): {len(preview['informational_classes'])}",
        ]
        for item in preview["candidate_tasks"][:5]:
            lines.append(f"  - {item['title']} ({item['due_date']}" + (f" {item['due_time']})" if item.get("due_time") else ")"))
        messagebox.showinfo("Vista previa de migración (solo lectura)", "\n".join(lines), parent=parent or self)

    def erase_all_data(self) -> None:
        if self.ai_busy or self.voice_active or self.tts_active:
            messagebox.showwarning("Operación activa", "Primero detén la generación o voz con DETENER AHORA · Esc y vuelve a intentarlo.", parent=self)
            return
        tables = ("tasks", "classes", "class_exceptions", "routines", "memories", "security_events", "action_events", "chat_history", "reminder_events", "reminder_actions", "plan_blocks")
        counts = {table: self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
        summary = (f"Tareas: {counts['tasks']}\nClases: {counts['classes']}\nExcepciones escolares: {counts['class_exceptions']}\n"
                   f"Rutinas: {counts['routines']}\nBloques de agenda: {counts['plan_blocks']}\nRecuerdos: {counts['memories']}\nNotas de seguridad: {counts['security_events']}\nHistorial de acciones: {counts['action_events']}\nTurnos de chat guardados: {counts['chat_history']}\nAvisos registrados: {counts['reminder_actions']}")
        auto_dir = DATA_DIR / "backups_before_restore"
        existing_auto = list(auto_dir.glob("*.zip")) if auto_dir.is_dir() else []
        dialog = tk.Toplevel(self)
        dialog.title("Eliminar todos los datos locales")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)
        box = ttk.Frame(dialog, padding=20)
        box.pack(fill="both", expand=True)
        ttk.Label(box, text="Esta acción no se puede deshacer desde Clara", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(box, text="Se borrarán los registros de la base local, la clave cifrada de VirusTotal y se restablecerán las preferencias predeterminadas. Esto no garantiza un borrado forense de los bytes en el disco.", wraplength=500).pack(anchor="w", pady=(6, 10))
        ttk.Label(box, text=summary, justify="left").pack(anchor="w", pady=(0, 10))
        remove_auto_var = tk.BooleanVar(value=bool(existing_auto))
        ttk.Checkbutton(box, text=f"Eliminar también copias automáticas de restauración ({len(existing_auto)})", variable=remove_auto_var, state="normal" if existing_auto else "disabled").pack(anchor="w", pady=(0, 8))
        ttk.Label(box, text="ZIP exportados en otras carpetas no se detectan ni se borran; elimínalos manualmente si también quieres quitarlos.", wraplength=500, foreground="#f2c77b").pack(anchor="w", pady=(0, 10))
        ttk.Label(box, text="Escribe BORRAR para habilitar la confirmación:").pack(anchor="w")
        phrase_var = tk.StringVar()
        phrase_entry = ttk.Entry(box, textvariable=phrase_var, width=24)
        phrase_entry.pack(anchor="w", pady=(4, 12))
        controls = ttk.Frame(box)
        controls.pack(fill="x")
        erase_button = ttk.Button(controls, text="Eliminar datos", state="disabled")
        erase_button.pack(side="right")
        ttk.Button(controls, text="Cancelar", command=dialog.destroy).pack(side="right", padx=8)

        def update_button(*_args) -> None:
            erase_button.configure(state="normal" if phrase_var.get().strip().upper() == "BORRAR" else "disabled")

        def erase() -> None:
            if phrase_var.get().strip().upper() != "BORRAR":
                return
            if not messagebox.askyesno("Confirmación final", "¿Eliminar ahora los datos mostrados? No se creará un respaldo automático porque eso conservaría una copia de los datos.", parent=dialog):
                return
            key_warning = ""
            try:
                self.db.execute("PRAGMA secure_delete=ON")
                with self.db:
                    for table in tables:
                        self.db.execute(f"DELETE FROM {table}")
                    self.db.execute("DELETE FROM sqlite_sequence WHERE name IN ('tasks','classes','class_exceptions','routines','memories','security_events','reminder_actions','plan_blocks','action_events','chat_history')")
                self.db.execute("VACUUM")
                self.settings = dict(DEFAULT_SETTINGS)
                save_settings(self.settings)
            except Exception as exc:
                messagebox.showerror("No se completó", f"No pude borrar todos los datos locales: {exc}", parent=dialog)
                return
            try:
                delete_vt_api_key()
            except OSError as exc:
                key_warning = f"\nNo pude eliminar la clave cifrada de VirusTotal: {exc}"
            backup_warning = key_warning
            if remove_auto_var.get() and auto_dir.exists():
                try:
                    shutil.rmtree(auto_dir)
                except OSError as exc:
                    backup_warning = f"\nNo pude eliminar la carpeta de copias automáticas: {exc}"
            self.ai_history.clear()
            self.last_assistant_response = ""
            self.stream_text = ""
            self.refresh_tasks()
            self.set_sphere_state("idle")
            self.voice_status.configure(text="Micrófono apagado · datos locales borrados")
            self.chat_log.configure(state="normal")
            self.chat_log.delete("1.0", "end")
            self.chat_log.configure(state="disabled")
            self.chat_input.delete(0, "end")
            self.ollama_status.configure(text="Datos locales borrados · IA local inactiva")
            dialog.destroy()
            self.append_chat("Sistema", "Se borraron los datos locales seleccionados; las preferencias volvieron a sus valores predeterminados." + backup_warning)
            messagebox.showinfo("Datos eliminados", "Se borraron los registros locales y se restablecieron las preferencias. Revisa la carpeta de respaldos exportados fuera de Clara si quieres quitarlos también." + backup_warning, parent=self)

        phrase_var.trace_add("write", update_button)
        erase_button.configure(command=erase)
        phrase_entry.focus_set()

    def _write_backup(self, destination: Path) -> None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=DATA_DIR) as temp_dir:
            temp = Path(temp_dir)
            snapshot = temp / "asistente.db"
            backup_db = sqlite3.connect(snapshot)
            self.db.backup(backup_db)
            backup_db.close()
            settings_file = temp / "settings.json"
            safe_backup_settings = sanitize_settings_for_storage(self.settings)
            settings_file.write_text(json.dumps(safe_backup_settings, ensure_ascii=False, indent=2), encoding="utf-8")
            partial = destination.with_name(destination.name + ".tmp")
            try:
                with zipfile.ZipFile(partial, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    archive.write(snapshot, "asistente.db")
                    archive.write(settings_file, "settings.json")
                os.replace(partial, destination)
            finally:
                if partial.exists():
                    partial.unlink()

    def export_backup(self) -> None:
        destination = filedialog.asksaveasfilename(parent=self, title="Guardar respaldo", defaultextension=".zip", filetypes=(("Respaldo ZIP", "*.zip"),))
        if not destination:
            return
        if not messagebox.askyesno("Datos personales (ZIP no cifrado)", "El archivo ZIP contiene tus datos locales y preferencias; podría incluir turnos de conversación si activaste su guardado. Este respaldo NO está cifrado y excluye la clave de VirusTotal. ¿Quieres guardarlo?", parent=self):
            return
        try:
            self._write_backup(Path(destination))
            messagebox.showinfo("Respaldo creado (no cifrado)", f"Se guardó el respaldo local (sin cifrar y sin clave de VirusTotal) en:\n{destination}", parent=self)
        except Exception as exc:
            messagebox.showerror("No se pudo crear", f"Error al crear el respaldo: {exc}", parent=self)

    def import_backup(self) -> None:
        if self.ai_busy or self.voice_active or self.tts_active or self.local_scan_running or self.vt_busy:
            messagebox.showwarning("Operación activa", "Primero detén la generación, voz o búsqueda activa con DETENER AHORA · Esc antes de restaurar un respaldo.", parent=self)
            return
        source = filedialog.askopenfilename(parent=self, title="Seleccionar respaldo", filetypes=(("Respaldo ZIP", "*.zip"),))
        if not source:
            return
        temp_dir = None
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            temp_dir = tempfile.TemporaryDirectory(dir=DATA_DIR)
            temp = Path(temp_dir.name)
            imported_db, extracted_settings_path = extract_validated_backup(source, temp)
            settings_path = extracted_settings_path
            check = sqlite3.connect(imported_db)
            integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
            tables = {row[0] for row in check.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            check.close()
            required = {"tasks", "classes", "routines", "memories", "security_events"}
            if integrity != "ok" or not required.issubset(tables):
                raise ValueError("La base de datos está dañada o no es un respaldo compatible.")
            imported_settings = dict(DEFAULT_SETTINGS)
            if settings_path is not None and settings_path.exists():
                raw_settings = json.loads(settings_path.read_text(encoding="utf-8"))
                if not isinstance(raw_settings, dict):
                    raise ValueError("Las preferencias del respaldo no tienen un formato válido.")
                imported_settings = sanitize_settings_for_storage(
                    {k: str(v) for k, v in raw_settings.items() if k in DEFAULT_SETTINGS and isinstance(v, str)}
                )
                try:
                    datetime.strptime(imported_settings["morning_time"], "%H:%M")
                except ValueError:
                    imported_settings["morning_time"] = DEFAULT_SETTINGS["morning_time"]
                if imported_settings["news_topic"] not in NEWS_TOPICS:
                    imported_settings["news_topic"] = DEFAULT_SETTINGS["news_topic"]
                if imported_settings.get("news_source") not in NEWS_SOURCE_FEEDS:
                    imported_settings["news_source"] = DEFAULT_SETTINGS["news_source"]
                if imported_settings.get("news_count") not in NEWS_COUNTS:
                    imported_settings["news_count"] = DEFAULT_SETTINGS["news_count"]
                for setting in ("chat_history_enabled", "native_notifications_enabled", "minimize_to_tray", "pattern_suggestions"):
                    if imported_settings.get(setting) not in ("true", "false"):
                        imported_settings[setting] = "false"
                if imported_settings.get("auto_speak_responses") not in ("true", "false"):
                    imported_settings["auto_speak_responses"] = "true"
                try:
                    pause_until = datetime.fromisoformat(imported_settings.get("reminders_paused_until", ""))
                    if pause_until.tzinfo is not None: pause_until = pause_until.astimezone().replace(tzinfo=None)
                    if pause_until <= datetime.now(): imported_settings["reminders_paused_until"] = ""
                except ValueError:
                    imported_settings["reminders_paused_until"] = ""
                if len(imported_settings["weather_location"]) > 100:
                    imported_settings["weather_location"] = DEFAULT_SETTINGS["weather_location"]
            if not messagebox.askyesno("Reemplazar datos", "Restaurar reemplazará tareas, clases, excepciones escolares, bloques, rutinas, recuerdos, notas e historiales actuales (incluido chat si estaba respaldado). Antes guardaré una copia automática local. ¿Continuar?", parent=self):
                return
            auto_dir = DATA_DIR / "backups_before_restore"
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            auto_path = auto_dir / f"antes_de_restaurar_{stamp}.zip"
            self._write_backup(auto_path)
            old_settings = dict(self.settings)
            old_snapshot = temp / "old_current.db"
            old_db = sqlite3.connect(old_snapshot)
            self.db.backup(old_db)
            old_db.close()
            stage = DB_PATH.with_name("asistente.restore.tmp")
            self.db.close()
            try:
                shutil.copy2(imported_db, stage)
                os.replace(stage, DB_PATH)
                save_settings(imported_settings)
                self.db = connect_db()
                self.settings = load_settings()
                if self.settings.get("minimize_to_tray") == "true":
                    self._start_tray_icon_if_enabled()
                else:
                    self._stop_tray_icon()
                self.refresh_tasks()
            except Exception:
                try:
                    if hasattr(self, "db"):
                        self.db.close()
                except Exception:
                    pass
                shutil.copy2(old_snapshot, stage)
                os.replace(stage, DB_PATH)
                save_settings(old_settings)
                self.db = connect_db()
                self.settings = load_settings()
                raise
            messagebox.showinfo("Respaldo restaurado", f"Datos restaurados. La copia anterior está en:\n{auto_path}", parent=self)
        except Exception as exc:
            messagebox.showerror("No se pudo restaurar", f"El respaldo no se aplicó: {exc}", parent=self)
        finally:
            if temp_dir is not None:
                temp_dir.cleanup()

    def open_settings(self) -> None:
        window = tk.Toplevel(self)
        window.title("Preferencias del asistente")
        window.geometry("700x580")
        window.minsize(560, 420)
        window.transient(self)
        window.resizable(True, True)
        outer = ttk.Frame(window, padding=14)
        outer.pack(fill="both", expand=True)

        top_bar = ttk.Frame(outer)
        top_bar.pack(side="top", fill="x", pady=(0, 8))
        ttk.Label(top_bar, text="Preferencias · usa la rueda del ratón o la barra lateral para bajar", style="CardTitle.TLabel").pack(side="left")

        scroll_container = ttk.Frame(outer)
        scroll_container.pack(fill="both", expand=True)
        canvas = tk.Canvas(scroll_container, bg="#07111f", highlightthickness=0)
        v_scroll = ttk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=v_scroll.set)
        v_scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        form = ttk.Frame(canvas, padding=18)
        canvas_window = canvas.create_window((0, 0), window=form, anchor="nw")

        def _on_form_configure(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event) -> None:
            try:
                canvas.itemconfigure(canvas_window, width=event.width)
            except Exception:
                pass

        def _on_mousewheel(event) -> None:
            delta = getattr(event, "delta", 0)
            if delta:
                canvas.yview_scroll(int(-1 * (delta / 120)), "units")

        form.bind("<Configure>", _on_form_configure)
        canvas.bind("<Configure>", _on_canvas_configure)
        window.bind("<MouseWheel>", _on_mousewheel)

        ttk.Label(form, text="Rutina, noticias y privacidad", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        ttk.Label(form, text="Hora de la rutina (24 horas, HH:MM)").grid(row=1, column=0, sticky="w")
        time_var = tk.StringVar(value=self.settings["morning_time"])
        ttk.Entry(form, textvariable=time_var, width=12).grid(row=2, column=0, sticky="w", pady=(4, 10))
        ttk.Label(form, text="Ubicación del clima (ciudad, estado/región, país)").grid(row=3, column=0, sticky="w")
        location_var = tk.StringVar(value=self.settings["weather_location"])
        ttk.Entry(form, textvariable=location_var, width=48).grid(row=4, column=0, sticky="ew", pady=(4, 10))
        ttk.Label(form, text="Tema de titulares (aplicado en Google News)").grid(row=5, column=0, sticky="w")
        topic_var = tk.StringVar(value=self.settings["news_topic"])
        ttk.Combobox(form, textvariable=topic_var, values=NEWS_TOPICS, state="readonly", width=24).grid(row=6, column=0, sticky="w", pady=(4, 10))
        ttk.Label(form, text="Fuente RSS permitida").grid(row=7, column=0, sticky="w")
        source_var = tk.StringVar(value=self.settings["news_source"])
        ttk.Combobox(form, textvariable=source_var, values=tuple(NEWS_SOURCE_FEEDS), state="readonly", width=30).grid(row=8, column=0, sticky="w", pady=(4, 10))
        ttk.Label(form, text="Cantidad máxima de titulares (3–10)").grid(row=9, column=0, sticky="w")
        count_var = tk.StringVar(value=self.settings["news_count"])
        ttk.Combobox(form, textvariable=count_var, values=NEWS_COUNTS, state="readonly", width=10).grid(row=10, column=0, sticky="w", pady=(4, 10))
        auto_speak_var = tk.BooleanVar(value=self.settings.get("auto_speak_responses", "true") == "true")
        ttk.Checkbutton(form, text="Leer automáticamente en voz alta las respuestas y resúmenes de noticias/agenda", variable=auto_speak_var).grid(row=11, column=0, sticky="w", pady=(3, 2))
        ttk.Label(form, text="Requiere pyttsx3 y una voz disponible en Windows. Si la voz falla, Clara muestra una explicación y conserva la respuesta escrita. El micrófono sigue apagado hasta que pulses para hablar; DETENER AHORA o Esc interrumpe la lectura.", wraplength=540, foreground="#91aabd").grid(row=12, column=0, sticky="w", pady=(0, 7))
        history_var = tk.BooleanVar(value=self.settings.get("chat_history_enabled", "false") == "true")
        ttk.Checkbutton(form, text="Guardar opcionalmente los turnos de conversación", variable=history_var).grid(row=13, column=0, sticky="w", pady=(3, 2))
        ttk.Label(form, text="Desactivado por defecto. Si lo activas, se guardan solo tus mensajes y los de Clara (máximo 1000; se muestran los últimos 200 al iniciar). Puede incluir datos personales que escribas; los respaldos ZIP no están cifrados.", wraplength=540, foreground="#f2c77b").grid(row=14, column=0, sticky="w", pady=(0, 7))
        history_buttons = ttk.Frame(form)
        history_buttons.grid(row=15, column=0, sticky="w", pady=(0, 10))
        ttk.Button(history_buttons, text="Ver / exportar / borrar historial…", command=self.open_chat_history_tools).pack(side="left")
        native_var = tk.BooleanVar(value=self.settings.get("native_notifications_enabled", "false") == "true")
        ttk.Checkbutton(form, text="Avisos nativos de Windows al estar minimizada (opcional)", variable=native_var).grid(row=16, column=0, sticky="w", pady=(2, 2))
        tray_var = tk.BooleanVar(value=self.settings.get("minimize_to_tray", "false") == "true")
        ttk.Checkbutton(form, text="Al cerrar con la X, minimizar a la bandeja (opcional)", variable=tray_var).grid(row=17, column=0, sticky="w", pady=(2, 2))
        ttk.Label(form, text="Requiere paquetes opcionales y Windows. Los avisos dependen de la sesión y de la configuración del Centro de notificaciones; los toasts ocultan el título del pendiente.", wraplength=540, foreground="#f2c77b").grid(row=18, column=0, sticky="w", pady=(0, 8))
        ttk.Label(form, text="Los feeds se descargan al pedir la rutina matutina. Google News usa el tema elegido; BBC Mundo y DW Español muestran su selección general. Se envían al servicio solo la petición de noticias y la ubicación del clima, no tareas ni clases.", wraplength=540, foreground="#91aabd").grid(row=19, column=0, sticky="w", pady=(0, 10))
        ttk.Label(form, text="La rutina se programa de lunes a viernes. Cambiar la hora aquí no actualiza Windows automáticamente; vuelve a ejecutar programar_rutina.bat.", wraplength=540, foreground="#91aabd").grid(row=20, column=0, sticky="w", pady=(0, 12))

        def save() -> None:
            time_value = time_var.get().strip()
            location = location_var.get().strip()
            try:
                datetime.strptime(time_value, "%H:%M")
            except ValueError:
                messagebox.showwarning("Formato de hora", "Escribe la hora como HH:MM en formato de 24 horas, por ejemplo 06:45.", parent=window)
                return
            if not location or len(location) > 100:
                messagebox.showwarning("Ubicación", "Escribe una ubicación de hasta 100 caracteres.", parent=window)
                return
            if contains_potential_api_key(location):
                messagebox.showwarning("Seguridad", "No pegues claves API ni tokens dentro de las preferencias. Configura la clave de VirusTotal únicamente en Seguridad → Configurar clave (cifrada con Windows DPAPI).", parent=window)
                return
            if source_var.get() not in NEWS_SOURCE_FEEDS or count_var.get() not in NEWS_COUNTS:
                messagebox.showwarning("Noticias", "Elige una fuente y una cantidad válidas.", parent=window)
                return
            self.settings.update({"morning_time": time_value, "weather_location": location, "news_topic": topic_var.get(), "news_source": source_var.get(), "news_count": count_var.get(), "chat_history_enabled": "true" if history_var.get() else "false", "auto_speak_responses": "true" if auto_speak_var.get() else "false", "native_notifications_enabled": "true" if native_var.get() else "false", "minimize_to_tray": "true" if tray_var.get() else "false"})
            self.settings.setdefault("pattern_suggestions", "false")
            save_settings(self.settings)
            if tray_var.get():
                self._start_tray_icon_if_enabled()
            else:
                self._stop_tray_icon()
            window.destroy()
            messagebox.showinfo("Preferencias guardadas", "La voz automática se aplicará a las próximas respuestas si pyttsx3 está instalado. Para noticias y ubicación, el cambio aplica al próximo resumen. Cambiar la hora programada requiere volver a ejecutar programar_rutina.bat.", parent=self)

        ttk.Button(top_bar, text="💾 Guardar preferencias", style="Accent.TButton", command=save).pack(side="right")
        ttk.Button(top_bar, text="Cancelar", command=window.destroy).pack(side="right", padx=6)

        buttons = ttk.Frame(form)
        buttons.grid(row=21, column=0, sticky="e")
        ttk.Button(buttons, text="Cancelar", command=window.destroy).pack(side="left", padx=6)
        ttk.Button(buttons, text="Guardar", style="Accent.TButton", command=save).pack(side="left")

    def open_security(self) -> None:
        window = tk.Toplevel(self)
        window.title("Seguridad y alertas")
        window.geometry("860x680")
        window.minsize(740, 520)
        window.transient(self)
        outer = ttk.Frame(window, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Centro de seguridad (informativo)", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Este asistente no es un antivirus y no escanea archivos. No diagnostica infecciones ni cambia la configuración de seguridad.", wraplength=740, foreground="#f2c77b").pack(anchor="w", pady=(4, 8))
        ttk.Button(outer, text="Consultar estado de Microsoft Defender (solo lectura)", command=self.check_defender_status).pack(anchor="w", pady=(0, 8))
        action_box = ttk.LabelFrame(outer, text="Etapa 7 · piloto de acción local acotada", padding=8)
        action_box.pack(fill="x", pady=(0, 8))
        ttk.Label(action_box, text="Única acción piloto: abrir en el Explorador una carpeta existente que tú selecciones. No lee su contenido mediante Clara ni modifica archivos. Se pide confirmación en cada intento.", wraplength=720).pack(anchor="w")
        action_buttons = ttk.Frame(action_box); action_buttons.pack(fill="x", pady=(6, 0))
        ttk.Button(action_buttons, text="Elegir y abrir carpeta…", command=lambda: self.open_selected_folder(window)).pack(side="left")
        ttk.Button(action_buttons, text="Ver historial de acciones…", command=lambda: self.show_action_history(window)).pack(side="left", padx=8)
        vt_box = ttk.LabelFrame(outer, text="Consulta manual VirusTotal · solo hash", padding=8)
        vt_box.pack(fill="x", pady=(0, 8))
        ttk.Label(vt_box, text="Calcula SHA-256 localmente y, tras tu confirmación por consulta, envía hash + API key por HTTPS. Nunca envía archivo, nombre o ruta; no automatiza consultas ni actúa sobre veredictos.", wraplength=720).pack(anchor="w")
        vt_key_status = ttk.Label(vt_box, text="Clave: protegida localmente" if VT_KEY_PATH.is_file() else "Clave: no configurada")
        vt_key_status.pack(anchor="w", pady=(4, 4))
        vt_actions = ttk.Frame(vt_box)
        vt_actions.pack(anchor="w")
        ttk.Button(vt_actions, text="Configurar / reemplazar clave…", command=lambda: self.configure_vt_key(vt_key_status, window)).pack(side="left")
        ttk.Button(vt_actions, text="Eliminar clave", command=lambda: self.remove_vt_key(vt_key_status, window)).pack(side="left", padx=6)
        ttk.Button(vt_actions, text="Consultar archivo por hash…", style="Accent.TButton", command=lambda: self.query_vt_file(window)).pack(side="left", padx=6)
        guide = tk.Text(outer, height=5, wrap="word", relief="flat", bg="#081624", fg="#eff8ff", insertbackground="#eff8ff", selectbackground="#1b4961", selectforeground="#ffffff", padx=8, pady=6)
        guide.pack(fill="x", pady=(0, 8))
        guide.insert("1.0", "Si algo parece extraño:\n1. No abras el archivo ni compartas contraseñas.\n2. Revisa la notificación en Seguridad de Windows; confirma qué producto la emitió y el nombre exacto de la detección.\n3. Sigue las instrucciones del propio antivirus para poner en cuarentena o analizar; no borres archivos del sistema manualmente.\n4. Si una alerta solicita pago o credenciales, no uses el enlace de esa alerta: abre Seguridad de Windows desde el menú Inicio.\n5. Si se trata de un equipo administrado por escuela/trabajo o hay posible robo de cuentas, contacta soporte técnico de confianza.")
        guide.configure(state="disabled")
        obs_header = ttk.Frame(outer)
        obs_header.pack(side="top", fill="x", pady=(0, 6))
        ttk.Label(obs_header, text="Tus reportes manuales (se guardan solo en esta computadora):", style="CardTitle.TLabel").pack(side="left")
        actions = ttk.Frame(obs_header)
        actions.pack(side="right")
        tree = ttk.Treeview(outer, columns=("date", "source", "summary"), show="headings", selectmode="browse", height=5)
        for col, label, width in (("date", "Fecha", 145), ("source", "Fuente", 150), ("summary", "Observación", 440)):
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor="w")
        tree.pack(fill="both", expand=True)

        def refresh() -> None:
            tree.delete(*tree.get_children())
            for row in self.db.execute("SELECT * FROM security_events ORDER BY id DESC"):
                tree.insert("", "end", iid=str(row["id"]), values=(row["created_at"].replace("T", " "), row["source"], row["summary"]))

        def report() -> None:
            dialog = tk.Toplevel(window)
            dialog.title("Registrar una observación")
            dialog.transient(window)
            dialog.grab_set()
            form = ttk.Frame(dialog, padding=18)
            form.pack(fill="both", expand=True)
            source_var = tk.StringVar(value="Seguridad de Windows")
            ttk.Label(form, text="¿Dónde apareció la alerta?").grid(row=0, column=0, sticky="w")
            ttk.Combobox(form, textvariable=source_var, values=("Seguridad de Windows", "Ollama / aplicación", "Correo o navegador", "Otro"), state="readonly", width=28).grid(row=1, column=0, sticky="w", pady=(4, 10))
            ttk.Label(form, text="Describe lo que viste (máximo 1000 caracteres). No adjuntes archivos ni contraseñas.").grid(row=2, column=0, sticky="w")
            note = tk.Text(form, width=70, height=6, wrap="word", bg="#081624", fg="#eff8ff", insertbackground="#eff8ff", selectbackground="#1b4961", selectforeground="#ffffff")
            note.grid(row=3, column=0, pady=(4, 10))

            def save_report() -> None:
                text = note.get("1.0", "end-1c").strip()
                if not text:
                    messagebox.showwarning("Falta la descripción", "Escribe una observación breve.", parent=dialog)
                    return
                if len(text) > 1000:
                    messagebox.showwarning("Texto demasiado largo", "Usa 1000 caracteres o menos.", parent=dialog)
                    return
                self.db.execute("INSERT INTO security_events(source, summary, created_at) VALUES(?,?,?)", (source_var.get(), text, datetime.now().isoformat(timespec="seconds")))
                self.db.commit()
                refresh()
                dialog.destroy()

            ttk.Button(form, text="Guardar reporte", style="Accent.TButton", command=save_report).grid(row=4, column=0, sticky="e")

        def delete_report() -> None:
            choice = tree.selection()
            if not choice:
                messagebox.showinfo("Selecciona un reporte", "Elige un reporte para borrarlo.", parent=window)
                return
            if messagebox.askyesno("Borrar reporte", "¿Eliminar esta nota local?", parent=window):
                self.db.execute("DELETE FROM security_events WHERE id=?", (int(choice[0]),))
                self.db.commit()
                refresh()

        ttk.Button(actions, text="+ Registrar observación", style="Accent.TButton", command=report).pack(side="left")
        ttk.Button(actions, text="Eliminar seleccionada", command=delete_report).pack(side="left", padx=8)
        refresh()

    def _record_private_action_event(self, action: str, outcome: str) -> bool:
        """Persist only the action category/outcome; callers must never pass paths or filenames."""
        try:
            self.db.execute("INSERT INTO action_events(action,outcome,created_at) VALUES(?,?,?)", (action, outcome, datetime.now().isoformat(timespec="seconds")))
            self.db.commit()
            return True
        except sqlite3.Error:
            return False

    def _record_action_event(self, outcome: str) -> int:
        cursor = self.db.execute("INSERT INTO action_events(action,outcome,created_at) VALUES(?,?,?)", (
            "Abrir carpeta seleccionada en Explorador", outcome, datetime.now().isoformat(timespec="seconds")))
        self.db.commit()
        return int(cursor.lastrowid)

    def _update_action_event(self, event_id: int, outcome: str) -> None:
        self.db.execute("UPDATE action_events SET outcome=? WHERE id=?", (outcome, event_id))
        self.db.commit()

    def open_selected_folder(self, parent) -> None:
        path = filedialog.askdirectory(parent=parent, title="Seleccionar carpeta existente", mustexist=True)
        if not path:
            return
        try:
            folder = validate_selected_folder(path)
        except (OSError, ValueError) as exc:
            self._record_action_event("No ejecutada · selección inválida")
            messagebox.showerror("Carpeta no disponible", str(exc), parent=parent)
            return
        if sys.platform != "win32":
            self._record_action_event("No ejecutada · plataforma no compatible")
            messagebox.showinfo("Solo Windows", "Este piloto abre carpetas con el Explorador de Windows y solo está habilitado en Windows.", parent=parent)
            return
        confirmed = messagebox.askyesno(
            "Confirmar acción local",
            "Clara abrirá esta carpeta existente en el Explorador de Windows:\n\n"
            f"{folder}\n\nNo se leerán ni cambiarán sus archivos desde Clara. Una vez iniciado el Explorador, DETENER AHORA no puede garantizar que lo cierre. ¿Continuar?",
            parent=parent)
        if not confirmed:
            self._record_action_event("Cancelada por el usuario · no se abrió")
            return
        try:
            event_id = self._record_action_event("Confirmada · inicio solicitado; resultado pendiente")
        except Exception as exc:
            messagebox.showerror("No se ejecutó", f"No pude guardar el registro local, así que no iniciaré la acción: {exc}", parent=parent)
            return
        try:
            launch_selected_folder(folder)
            self._update_action_event(event_id, "Windows aceptó la solicitud de apertura")
            self.append_chat("Registro de acción", "Se solicitó abrir en el Explorador una carpeta seleccionada por ti. Clara no leyó ni modificó su contenido.")
        except Exception as exc:
            try:
                self._update_action_event(event_id, "Error al iniciar · " + type(exc).__name__)
            except Exception:
                pass
            messagebox.showerror("No se pudo abrir", f"Windows no pudo abrir la carpeta seleccionada: {exc}", parent=parent)

    def show_action_history(self, parent) -> None:
        window = tk.Toplevel(parent)
        window.title("Historial de acciones locales")
        window.geometry("700x380")
        window.transient(parent)
        frame = ttk.Frame(window, padding=14); frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Registro local · no almacena las rutas de las carpetas", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 8))
        controls = ttk.Frame(frame); controls.pack(side="top", fill="x", pady=(0, 8))
        tree = ttk.Treeview(frame, columns=("when", "action", "outcome"), show="headings", selectmode="browse", height=6)
        for col, label, width in (("when", "Fecha", 155), ("action", "Acción", 255), ("outcome", "Resultado", 250)):
            tree.heading(col, text=label); tree.column(col, width=width, anchor="w")
        tree.pack(fill="both", expand=True)
        def refresh() -> None:
            tree.delete(*tree.get_children())
            for row in self.db.execute("SELECT * FROM action_events ORDER BY id DESC"):
                tree.insert("", "end", iid=str(row["id"]), values=(row["created_at"].replace("T", " "), row["action"], row["outcome"]))
        def delete_selected() -> None:
            selection = tree.selection()
            if not selection:
                messagebox.showinfo("Selecciona un registro", "Elige un registro que quieras borrar.", parent=window); return
            if messagebox.askyesno("Borrar registro", "¿Eliminar este elemento del historial local?", parent=window):
                self.db.execute("DELETE FROM action_events WHERE id=?", (int(selection[0]),)); self.db.commit(); refresh()
        def export_history() -> None:
            count = self.db.execute("SELECT COUNT(*) FROM action_events").fetchone()[0]
            if not count:
                messagebox.showinfo("Historial vacío", "No hay eventos para exportar.", parent=window); return
            destination = filedialog.asksaveasfilename(parent=window, title="Exportar historial local", defaultextension=".csv", initialfile="historial_acciones.csv", filetypes=(("CSV", "*.csv"),))
            if not destination:
                return
            if not messagebox.askyesno("Confirmar exportación", "Se exportarán fecha, categoría de acción y resultado; no nombres de archivos ni rutas. El CSV quedará sin cifrar en la ubicación elegida. ¿Continuar?", parent=window):
                return
            try:
                exported = export_action_history_csv(self.db, destination)
            except OSError as exc:
                messagebox.showerror("No se exportó", f"No pude escribir el CSV: {exc}", parent=window); return
            messagebox.showinfo("Historial exportado", f"Se exportaron {exported} evento(s). El archivo CSV no está cifrado.", parent=window)
        def delete_all() -> None:
            count = self.db.execute("SELECT COUNT(*) FROM action_events").fetchone()[0]
            if not count:
                messagebox.showinfo("Historial vacío", "No hay eventos para borrar.", parent=window); return
            if messagebox.askyesno("Borrar todo el historial", f"Se borrarán {count} eventos locales de acción. Esto no borra tareas ni notas de seguridad y no se puede deshacer desde Clara. Puedes exportarlos antes. ¿Continuar?", icon="warning", parent=window):
                self.db.execute("DELETE FROM action_events"); self.db.commit(); refresh()
        ttk.Button(controls, text="Exportar CSV…", command=export_history).pack(side="left")
        ttk.Button(controls, text="Borrar todo…", command=delete_all).pack(side="left", padx=8)
        ttk.Button(controls, text="Eliminar seleccionado", command=delete_selected).pack(side="right")
        refresh()

    def configure_vt_key(self, status_label, parent) -> None:
        dialog = tk.Toplevel(parent)
        dialog.title("Clave personal de VirusTotal")
        dialog.transient(parent)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Obtén tu API key desde tu cuenta de VirusTotal y pégala aquí. No la envíes por chat.", wraplength=480).pack(anchor="w")
        ttk.Label(frame, text="Clara la cifra con Windows DPAPI para tu usuario; no se guarda en preferencias ni respaldos, y solo se lee al iniciar una consulta manual.", wraplength=480).pack(anchor="w", pady=(8, 10))
        entry = ttk.Entry(frame, show="*", width=58)
        entry.pack(fill="x", pady=(0, 10))
        def save() -> None:
            try:
                save_vt_api_key(entry.get())
            except Exception as exc:
                messagebox.showerror("No se guardó la clave", str(exc), parent=dialog)
                return
            status_label.configure(text="Clave: protegida localmente con DPAPI")
            entry.delete(0, "end")
            dialog.destroy()
            messagebox.showinfo("Clave guardada", "La clave se guarda cifrada para tu usuario de Windows. No se ha validado ni enviado.", parent=parent)
        controls = ttk.Frame(frame); controls.pack(fill="x")
        ttk.Button(controls, text="Guardar cifrada", style="Accent.TButton", command=save).pack(side="right")
        ttk.Button(controls, text="Cancelar", command=dialog.destroy).pack(side="right", padx=8)
        entry.focus_set()

    def remove_vt_key(self, status_label, parent) -> None:
        if not VT_KEY_PATH.exists():
            messagebox.showinfo("Sin clave", "No hay una clave local configurada.", parent=parent); return
        if messagebox.askyesno("Eliminar clave", "¿Eliminar la clave cifrada de VirusTotal de este perfil de Windows?", parent=parent):
            try:
                delete_vt_api_key()
                status_label.configure(text="Clave: no configurada")
            except OSError as exc:
                messagebox.showerror("No se pudo eliminar", str(exc), parent=parent)

    def query_vt_file(self, parent) -> None:
        path = filedialog.askopenfilename(parent=parent, title="Elegir archivo · solo se calculará el hash")
        if not path:
            return
        if not VT_KEY_PATH.is_file():
            messagebox.showinfo("Falta configurar la clave", "Configura primero tu API key propia en esta computadora.", parent=parent)
            return
        try:
            sha256, size = hash_file_sha256(path)
        except OSError as exc:
            messagebox.showerror("No se pudo calcular", str(exc), parent=parent)
            return
        consent = (f"Consulta manual de VirusTotal\n\nSe enviará únicamente este SHA-256:\n{sha256}\n\n"
                   "La petición HTTPS incluye el hash y tu API key de autenticación; no se envían el archivo, nombre ni ruta. VirusTotal puede incorporar el indicador consultado a su conjunto de datos compartido y recibe metadatos normales de conexión.\n\n"
                   f"Tamaño local: {size:,} bytes. ¿Enviar el hash ahora?")
        if not messagebox.askyesno("Confirmar consulta externa", consent, parent=parent):
            return
        if self.vt_busy:
            messagebox.showinfo("Consulta en curso", "Espera a que termine la consulta actual.", parent=parent)
            return
        remaining = 16 - (time.monotonic() - self.vt_last_request)
        if remaining > 0:
            messagebox.showinfo("Límite de frecuencia", f"Espera {remaining:.0f} segundos antes de otra consulta manual (límite público aproximado: 4 por minuto).", parent=parent)
            return
        try:
            key = load_vt_api_key()
        except Exception as exc:
            messagebox.showerror("No se pudo leer la clave", f"La clave local no pudo descifrarse: {exc}", parent=parent)
            return
        if not key:
            messagebox.showinfo("Falta configurar la clave", "Configura tu API key personal antes de consultar.", parent=parent)
            return
        self.vt_busy = True
        self.vt_cancel_event.clear()
        self.vt_last_request = time.monotonic()
        self.append_chat("Sistema", "Consulta VirusTotal iniciada por solicitud manual; se envía solo el SHA-256, no el archivo.")
        filename = Path(path).name
        def worker() -> None:
            if self.vt_cancel_event.is_set():
                self.ai_results.put(("vt_cancelled", None))
                return
            try:
                result = virustotal_lookup(sha256, key)
            except Exception:
                result = {"status": "network_error", "detail": "error inesperado durante la consulta"}
            self.ai_results.put(("vt_result", {"result": result, "sha256": sha256, "filename": filename, "size": size, "checked_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")}))
        threading.Thread(target=worker, daemon=True).start()

    def show_vt_result(self, payload: dict) -> None:
        self.vt_busy = False
        if self.vt_cancel_event.is_set():
            self.append_chat("Control de emergencia", "Se ignoró el resultado tardío de VirusTotal. Si la petición ya había salido, Clara no puede retirarla del servidor remoto.")
            return
        result = payload["result"]
        if result["status"] == "ok":
            stats = result.get("stats") or {}
            text = (f"Resultado de VirusTotal · consulta de hash\nArchivo local (no enviado): {payload['filename']}\nTamaño: {payload['size']:,} bytes\n"
                    f"SHA-256 consultado: {payload['sha256']}\nHora local: {payload['checked_at']}\n\n"
                    f"Último informe disponible: malicioso {stats.get('malicious', 0)}, sospechoso {stats.get('suspicious', 0)}, inofensivo {stats.get('harmless', 0)}, sin detección {stats.get('undetected', 0)}.\n"
                    "Esto no es un escaneo local ni una garantía de seguridad; los motores pueden discrepar y los informes pueden estar incompletos o desactualizados.")
            if result.get("analysis_date"):
                text += f"\nFecha del análisis reportada (Unix): {result['analysis_date']}"
            if result.get("detections"):
                text += "\n\nDetecciones reportadas:\n" + "\n".join(f"• {engine}: {verdict} ({detail})" for engine, verdict, detail in result["detections"])
        else:
            explanations = {"not_found": "VirusTotal no tiene un informe disponible para este hash. Eso no significa que el archivo sea seguro.", "unauthorized": "VirusTotal rechazó la clave; revisa tu API key.", "forbidden": "La clave o el plan no permite esta consulta.", "rate_limited": "VirusTotal aplicó un límite de frecuencia o cuota; no se reintentó automáticamente.", "network_error": "No se pudo completar la consulta HTTPS: " + result.get("detail", "error de red"), "http_error": f"VirusTotal respondió con HTTP {result.get('code')}."}
            text = explanations.get(result["status"], "Consulta no disponible.") + f"\n\nSHA-256: {payload['sha256']}\nHora local: {payload['checked_at']}\nNo se subió ningún archivo."
        self.append_chat("VirusTotal · consulta hash", text)
        messagebox.showinfo("Resultado de consulta hash", text, parent=self)

    def check_defender_status(self) -> None:
        self.append_chat("Sistema", "Consultando Microsoft Defender mediante una consulta local de solo lectura.")
        command = "$s=Get-MpComputerStatus; [pscustomobject]@{AntivirusEnabled=$s.AntivirusEnabled;RealTimeProtectionEnabled=$s.RealTimeProtectionEnabled;SignatureLastUpdated=$s.AntivirusSignatureLastUpdated;QuickScanAge=$s.QuickScanAge;AMRunningMode=$s.AMRunningMode}|ConvertTo-Json -Compress"

        def worker() -> None:
            try:
                result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True, text=True, timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), check=False)
                if result.returncode != 0 or not result.stdout.strip():
                    detail = result.stderr.strip() or "Windows no devolvió estado de Defender. Puede no estar disponible o ser otro antivirus el principal."
                    self.ai_results.put(("defender_status", detail))
                    return
                data = json.loads(result.stdout.strip())
                enabled = "Sí" if data.get("AntivirusEnabled") else "No / no reportado"
                realtime = "Sí" if data.get("RealTimeProtectionEnabled") else "No / no reportado"
                answer = (f"Microsoft Defender informa (instantánea de solo lectura):\nAntivirusEnabled: {enabled}\nProtección en tiempo real: {realtime}\n" + f"Modo: {data.get('AMRunningMode', 'no reportado')}\nÚltima actualización de firmas: {data.get('SignatureLastUpdated', 'no reportada')}\nAntigüedad del último análisis rápido (días): {data.get('QuickScanAge', 'no reportada')}\n\nEsto no es un análisis del equipo ni demuestra que esté limpio. Si tienes otro antivirus, Defender puede estar en modo pasivo.")
                self.ai_results.put(("defender_status", answer))
            except Exception as exc:
                self.ai_results.put(("defender_status", "No pude consultar el estado de Defender. Abre Seguridad de Windows manualmente. Detalle: " + str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def install_vosk_model_with_consent(self, parent_window=None) -> None:
        """Create models/ folder and download/extract vosk-model-small-es-0.42 after explicit user authorization."""
        target_parent = parent_window or self
        model_dir = APP_BASE_DIR / "models" / "vosk-model-small-es-0.42"
        if model_dir.is_dir():
            messagebox.showinfo(
                "Modelo ya instalado",
                f"El modelo de voz en español ya está listo en:\n{model_dir}",
                parent=target_parent,
            )
            return
        disclosure = (
            "No necesitas crear la carpeta manualmente: CLARA-V puede crearla e instalar el modelo por ti.\n\n"
            + format_resource_disclosure("vosk-model-small-es-0.42")
            + f"\n\nDestino local:\n{model_dir}\n\n"
            "¿Autorizas crear la carpeta 'models' y descargar/extraer ahora mismo el modelo oficial (39 MB)?"
        )
        if not messagebox.askyesno("Instalar modelo local de micrófono (Vosk)", disclosure, parent=target_parent):
            return
        self.voice_status.configure(text="Descargando e instalando vosk-model-small-es-0.42 (39 MB)…")
        self.append_chat("Sistema", "Iniciando descarga autorizada de vosk-model-small-es-0.42 desde alphacephei.com…", persist=False, speak=False)

        def worker() -> None:
            models_root = APP_BASE_DIR / "models"
            zip_tmp = models_root / "vosk-model-small-es-0.42.zip.part"
            try:
                models_root.mkdir(parents=True, exist_ok=True)
                url = OFFICIAL_RESOURCES["vosk-model-small-es-0.42"]["source"]
                req = urllib.request.Request(url, headers={"User-Agent": "CLARA-V/2.0"})
                with urllib.request.urlopen(req, timeout=120) as resp, open(zip_tmp, "wb") as out_f:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        out_f.write(chunk)
                with zipfile.ZipFile(zip_tmp, "r") as zf:
                    for member in zf.infolist():
                        member_path = (models_root / member.filename).resolve()
                        if not str(member_path).startswith(str(models_root.resolve())):
                            raise ValueError("Ruta inválida dentro del archivo ZIP.")
                    zf.extractall(models_root)
                try:
                    zip_tmp.unlink(missing_ok=True)
                except OSError:
                    pass
                self.ai_results.put(("voice_status", "¡Modelo Vosk instalado! Ya puedes usar “🎙 Pulsar para hablar”."))
            except Exception as exc:
                try:
                    zip_tmp.unlink(missing_ok=True)
                except OSError:
                    pass
                self.ai_results.put(("voice_error", f"No se pudo descargar/extraer el modelo Vosk: {exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def toggle_voice(self) -> None:
        if self.tts_active:
            messagebox.showinfo("Voz ocupada", "Detén la lectura de Clara antes de activar el micrófono.", parent=self)
            return
        if self.voice_active:
            self.voice_stop.set()
            self.voice_status.configure(text="Deteniendo y preparando la transcripción…")
            return
        missing = [name for name in ("vosk", "sounddevice") if importlib.util.find_spec(name) is None]
        has_sr = importlib.util.find_spec("speech_recognition") is not None
        model_path = resolve_vosk_model_path(APP_BASE_DIR)
        if missing and not has_sr:
            messagebox.showinfo(
                "Voz opcional no instalada",
                "Para activar el micrófono ejecuta primero .\\instalar_voz.bat para instalar vosk, sounddevice y SpeechRecognition. La escritura sigue funcionando.",
            )
            return
        if not model_path.is_dir() and not has_sr:
            self.install_vosk_model_with_consent(parent_window=self)
            return
        self.voice_active = True
        self.voice_stop = threading.Event()
        self.set_sphere_state("listening")
        self.voice_button.configure(text="■ Detener micrófono")
        self.voice_status.configure(text="Iniciando reconocimiento de voz…")
        threading.Thread(target=self._voice_worker, args=(self.voice_stop, model_path), daemon=True).start()

    def _voice_worker(self, stop_event: threading.Event, model_path: Path) -> None:
        try:
            has_vosk = importlib.util.find_spec("vosk") is not None and importlib.util.find_spec("sounddevice") is not None and model_path.is_dir()
            if has_vosk:
                import sounddevice as sd
                from vosk import KaldiRecognizer, Model

                if self.vosk_model is None:
                    self.ai_results.put(("voice_status", "Cargando modelo de español local…"))
                    self.vosk_model = Model(str(model_path))
                target_rate = 16000
                device_rate = target_rate
                try:
                    sd.check_input_settings(samplerate=target_rate, channels=1, dtype="int16")
                except Exception:
                    try:
                        dev_info = sd.query_devices(kind="input")
                        device_rate = int(dev_info.get("default_samplerate") or 44100)
                    except Exception:
                        device_rate = 44100

                recognizer = KaldiRecognizer(self.vosk_model, target_rate)
                try:
                    recognizer.SetWords(True)
                except Exception:
                    pass
                audio_queue: queue.Queue[bytes] = queue.Queue()
                raw_pcm_chunks: list[bytes] = []
                segments: list[str] = []
                last_partial_holder = [""]

                def audio_callback(indata, _frames, _time, status):
                    if status:
                        self.ai_results.put(("voice_status", f"Audio: {status}"))
                    audio_queue.put(bytes(indata))

                def drain_queue() -> None:
                    while True:
                        try:
                            chunk = audio_queue.get_nowait()
                        except queue.Empty:
                            break
                        if device_rate != target_rate:
                            chunk = _downsample_pcm16_mono(chunk, device_rate, target_rate)
                        raw_pcm_chunks.append(chunk)
                        live_text = accumulate_vosk_stream_chunk(recognizer, chunk, segments, last_partial_holder)
                        if live_text:
                            preview = (" ".join(segments + ([last_partial_holder[0]] if last_partial_holder[0] else []))).strip()
                            if preview:
                                self.ai_results.put(("voice_status", f"🎙 Escuchando: «{preview[-72:]}» (pulsa Detener al terminar)"))

                self.ai_results.put(("voice_status", "🎙 Micrófono activo · habla con naturalidad y pulsa Detener al terminar."))
                block_frames = max(2000, int(device_rate * 0.25))
                with sd.RawInputStream(samplerate=device_rate, blocksize=block_frames, dtype="int16", channels=1, callback=audio_callback):
                    while not stop_event.wait(0.08):
                        drain_queue()
                drain_queue()

                text = finalize_vosk_recognition(recognizer, segments, last_partial_holder[0])
                raw_pcm = b"".join(raw_pcm_chunks)

                # Pass 2: Automatic Gain Boost + trailing silence (fixes quiet microphones in Windows)
                if not text and raw_pcm:
                    self.ai_results.put(("voice_status", "Optimizando volumen de voz y reintentando reconocimiento…"))
                    text = recognize_pcm_with_vosk_second_pass(self.vosk_model, raw_pcm, target_rate)

                # Pass 3: Viernes multi-engine fallback (Whisper / Vosk / Google es-MX from speech_input.py)
                if not text and raw_pcm:
                    text = recognize_pcm_with_viernes_backends(raw_pcm, target_rate)

                if text:
                    self.ai_results.put(("voice_transcript", text))
                else:
                    _b, peak_amp, _g = _boost_pcm16_gain(raw_pcm)
                    if peak_amp <= 30:
                        self.ai_results.put(
                            (
                                "voice_empty",
                                "El micrófono no recibió señal de audio (volumen en 0 o micrófono silenciado en Windows). Revisa tu dispositivo de entrada.",
                            )
                        )
                    else:
                        self.ai_results.put(("voice_empty", "No alcancé a reconocer palabras; puedes intentarlo otra vez o escribir."))
                return

            # Direct Viernes SpeechRecognition mode when Vosk is not yet installed
            import speech_recognition as sr

            r = sr.Recognizer()
            r.dynamic_energy_threshold = True
            self.ai_results.put(("voice_status", "🎙 Micrófono activo (modo Viernes SpeechRecognition)… habla ahora."))
            with sr.Microphone() as source:
                r.adjust_for_ambient_noise(source, duration=0.4)
                audio = r.listen(source, timeout=6, phrase_time_limit=12)
            raw_16k = audio.get_raw_data(convert_rate=16000, convert_width=2)
            text = recognize_pcm_with_viernes_backends(raw_16k, 16000, sr_module=sr)
            if text:
                self.ai_results.put(("voice_transcript", text))
            else:
                self.ai_results.put(("voice_empty", "No alcancé a reconocer palabras; puedes intentarlo otra vez o escribir."))
        except Exception as exc:
            self.ai_results.put(("voice_error", str(exc)))
        finally:
            self.ai_results.put(("voice_stopped", "Micrófono apagado"))

    def speak_last_response(self) -> None:
        if not self.last_assistant_response:
            messagebox.showinfo("No hay respuesta", "Primero conversa con el asistente o abre un resumen de agenda/noticias para que haya una respuesta que repetir.")
            return
        self._start_tts(self.last_assistant_response, manual=True)

    def _report_tts_failure(self, reason: str, manual: bool = False) -> None:
        explanation = explain_tts_failure(reason)
        self.set_sphere_state("idle")
        self.voice_status.configure(text="Voz no disponible · respuesta escrita conservada (abre 🩺 Diagnóstico de voz)")
        self.chat_log.configure(state="normal")
        self.chat_log.insert("end", "Aviso de voz\n", "speaker")
        self.chat_log.insert("end", explanation + "\n")
        self.chat_log.see("end")
        self.chat_log.configure(state="disabled")
        if manual:
            messagebox.showwarning("Voz de salida no disponible", explanation, parent=self)

    def _start_tts(self, text: str, manual: bool = False) -> None:
        spoken_text = prepare_text_for_speech(text)
        if not spoken_text:
            return
        if self.voice_active:
            self.voice_status.configure(text="La voz automática espera a que termine la captura manual del micrófono.")
            if manual:
                messagebox.showinfo("Micrófono activo", "Detén la captura manual antes de reproducir la voz de Clara.", parent=self)
            return
        if self.tts_active:
            if manual:
                self.voice_status.configure(text="Ya se está leyendo; pulsa DETENER AHORA o Esc para parar.")
            return
        if importlib.util.find_spec("pyttsx3") is None:
            self._report_tts_failure("no_pyttsx3", manual=manual)
            return
        self.tts_active = True
        self.tts_cancel_event = threading.Event()
        cancel_event = self.tts_cancel_event
        self.set_sphere_state("idle")
        self.voice_status.configure(text="Clara está preparando la respuesta hablada · DETENER AHORA o Esc para parar.")

        def worker() -> None:
            engine = None
            loop_started = False
            try:
                import pyttsx3
                engine = pyttsx3.init()
                voices = list(engine.getProperty("voices") or [])
                if not voices:
                    raise RuntimeError("no_voices")
                spanish_id = select_spanish_voice_id(voices)
                if spanish_id:
                    try:
                        engine.setProperty("voice", spanish_id)
                    except Exception:
                        pass
                self.current_tts_engine = engine
                engine.say(spoken_text)
                engine.startLoop(False)
                loop_started = True
                if not cancel_event.is_set():
                    self.ai_results.put(("tts_started", ""))
                while engine.isBusy() and not cancel_event.is_set():
                    engine.iterate()
                    cancel_event.wait(0.03)
                if cancel_event.is_set():
                    engine.stop()
                    status = "Lectura detenida por el usuario."
                else:
                    status = "Lectura terminada."
                engine.endLoop()
                loop_started = False
                self.ai_results.put(("tts_status", status))
            except Exception as exc:
                self.ai_results.put(("tts_error", (str(exc), manual)))
            finally:
                if loop_started and engine is not None:
                    try:
                        engine.endLoop()
                    except Exception:
                        pass
                self.current_tts_engine = None
                self.tts_active = False

        threading.Thread(target=worker, daemon=True).start()

    def open_voice_diagnostics(self) -> None:
        """Open in-app voice diagnostic dialog (does not activate microphone or contact internet)."""
        diag = collect_voice_diagnostics(APP_BASE_DIR)
        window = tk.Toplevel(self)
        window.title("Diagnóstico de voz · Entrada y salida local")
        window.geometry("820x540")
        window.minsize(680, 420)
        window.transient(self)
        outer = ttk.Frame(window, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Diagnóstico local de voz (TTS y Push-to-Talk)", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Esta comprobación es 100 % local: no enciende el micrófono ni usa internet. Si la voz falla, Clara explica el motivo y conserva siempre la respuesta escrita.",
            wraplength=760,
        ).pack(anchor="w", pady=(4, 10))
        actions = ttk.Frame(outer)
        actions.pack(side="bottom", fill="x", pady=(10, 0))
        ttk.Button(
            actions,
            text="🔊 Probar frase en voz alta",
            style="Accent.TButton",
            command=lambda: self._start_tts("Hola, esta es una prueba manual de la voz local de Clara.", manual=True),
        ).pack(side="left")
        ttk.Button(
            actions,
            text="⬇ Descargar modelo Vosk (39 MB)…",
            command=lambda: self.install_vosk_model_with_consent(parent_window=window),
        ).pack(side="left", padx=8)
        ttk.Button(actions, text="Cerrar", command=window.destroy).pack(side="right")
        report = tk.Text(outer, height=12, wrap="word", relief="flat", bg="#081624", fg="#eff8ff", padx=12, pady=12, font=("Segoe UI", 10))
        report.pack(fill="both", expand=True)
        lines = [
            f"1. Síntesis de voz (TTS · pyttsx3): {'INSTALADO' if diag['tts_installed'] else 'NO INSTALADO'}",
            f"   Estado operativo: {'LISTO' if diag['tts_ready'] else 'NO DISPONIBLE'}",
        ]
        if diag["tts_error"]:
            lines.append(f"   Detalle del error: {diag['tts_error']}")
        if diag["voices"]:
            lines.append(f"   Voces detectadas ({len(diag['voices'])}):")
            for v in diag["voices"][:8]:
                marker = " [Seleccionada para español]" if v["id"] == diag["spanish_voice_id"] else ""
                lines.append(f"   • {v['name']} ({v['id']}){marker}")
        else:
            lines.append("   • No se detectaron voces del sistema. En Windows instala Español (México) o Español (España) en Configuración > Hora e idioma > Voz.")
        lines.extend(
            [
                "",
                f"2. Reconocimiento Push-to-Talk local (Vosk): {'INSTALADO' if diag['vosk_installed'] else 'NO INSTALADO'}",
                f"   Captura de audio (sounddevice): {'INSTALADO' if diag['sounddevice_installed'] else 'NO INSTALADO'}",
                f"   Modelo local en español ({diag['model_path']}): {'ENCONTRADO' if diag['model_present'] else 'NO ENCONTRADO (pulsa “⬇ Descargar modelo Vosk” abajo para que CLARA-V cree la carpeta e instale el modelo)'}",
                "   Estado del micrófono durante este diagnóstico: APAGADO (solo se activa manualmente con “🎙 Pulsar para hablar”).",
                "",
                "3. Recursos opcionales verificados (descargas automáticas desactivadas):",
                format_resource_disclosure("pyttsx3"),
                "",
                format_resource_disclosure("vosk-model-small-es-0.42"),
            ]
        )
        report.insert("1.0", "\n".join(lines))
        report.configure(state="disabled")

    def open_routines(self) -> None:
        window = tk.Toplevel(self)
        window.title("Rutinas recurrentes")
        window.geometry("940x500")
        window.transient(self)
        outer = ttk.Frame(window, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Rutinas que tú configuras", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Cada mañana, las rutinas activas del día se agregan como tareas. No se infieren ni se crean sin tu autorización previa.").pack(anchor="w", pady=(4, 8))
        pattern_row=ttk.Frame(outer); pattern_row.pack(fill="x",pady=(0,8))
        pattern_var=tk.BooleanVar(value=self.settings.get("pattern_suggestions","false")=="true")
        pattern_button=ttk.Button(pattern_row,text="Analizar patrones ahora…",command=lambda:self.suggest_routine_patterns(window,refresh),state="normal" if pattern_var.get() else "disabled")
        def toggle_patterns() -> None:
            enabled=bool(pattern_var.get())
            self.settings["pattern_suggestions"]="true" if enabled else "false"
            save_settings(self.settings)
            pattern_button.configure(state="normal" if enabled else "disabled")
        ttk.Checkbutton(pattern_row,text="Permitir análisis local solo cuando yo lo solicite",variable=pattern_var,command=toggle_patterns).pack(side="left")
        pattern_button.pack(side="left",padx=10)
        actions = ttk.Frame(outer)
        actions.pack(side="top", fill="x", pady=(0, 8))
        tree = ttk.Treeview(outer, columns=("title", "subject", "days", "time", "active", "source"), show="headings", selectmode="browse", height=6)
        for col, label, width in (("title", "Rutina", 170), ("subject", "Materia", 110), ("days", "Días", 170), ("time", "Aviso", 75), ("active", "Estado", 70), ("source", "Origen", 250)):
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor="w" if col in ("title", "subject", "days", "source") else "center")
        tree.pack(fill="both", expand=True)
        day_names = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")

        def refresh() -> None:
            tree.delete(*tree.get_children())
            for item in self.db.execute("SELECT * FROM routines ORDER BY title"):
                selected_days = [day_names[int(d)] for d in item["weekdays"].split(",") if d.isdigit() and 0 <= int(d) < 7]
                tree.insert("", "end", iid=str(item["id"]), values=(item["title"], item["subject"] or "—", ", ".join(selected_days), item["reminder_time"] or "—", "Activa" if item["active"] else "Pausada", item["source"] or "Origen no registrado"))

        def edit(routine_id: int | None = None) -> None:
            existing = self.db.execute("SELECT * FROM routines WHERE id=?", (routine_id,)).fetchone() if routine_id else None
            dialog = tk.Toplevel(window)
            dialog.title("Editar rutina" if existing else "Agregar rutina")
            dialog.transient(window)
            dialog.grab_set()
            form = ttk.Frame(dialog, padding=18)
            form.pack(fill="both", expand=True)
            title_var = tk.StringVar(value=existing["title"] if existing else "")
            subject_var = tk.StringVar(value=(existing["subject"] or "") if existing else "")
            time_var = tk.StringVar(value=(existing["reminder_time"] or "") if existing else "")
            active_var = tk.BooleanVar(value=bool(existing["active"]) if existing else True)
            ttk.Label(form, text="¿Qué quieres que se repita?").grid(row=0, column=0, sticky="w")
            ttk.Entry(form, textvariable=title_var, width=52).grid(row=1, column=0, columnspan=4, sticky="ew", pady=(3, 10))
            ttk.Label(form, text="Materia opcional").grid(row=2, column=0, sticky="w")
            ttk.Entry(form, textvariable=subject_var, width=25).grid(row=3, column=0, sticky="w", pady=(3, 10))
            ttk.Label(form, text="Hora de aviso opcional (HH:MM)").grid(row=4, column=0, sticky="w")
            ttk.Entry(form, textvariable=time_var, width=12).grid(row=5, column=0, sticky="w", pady=(3, 10))
            ttk.Label(form, text="Repetir estos días").grid(row=6, column=0, sticky="w", pady=(0, 4))
            old_days = set(existing["weekdays"].split(",")) if existing else {"0", "1", "2", "3", "4"}
            day_vars = [tk.BooleanVar(value=str(index) in old_days) for index in range(7)]
            for index, (name, variable) in enumerate(zip(("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"), day_vars)):
                ttk.Checkbutton(form, text=name, variable=variable).grid(row=7 + index // 4, column=index % 4, sticky="w", padx=(0, 12), pady=3)
            ttk.Checkbutton(form, text="Rutina activa", variable=active_var).grid(row=9, column=0, sticky="w", pady=(8, 12))

            def save() -> None:
                title = title_var.get().strip()
                reminder = time_var.get().strip()
                weekdays = [str(i) for i, variable in enumerate(day_vars) if variable.get()]
                if not title or not weekdays:
                    messagebox.showwarning("Faltan datos", "Escribe el nombre de la rutina y selecciona al menos un día.", parent=dialog)
                    return
                if reminder:
                    try:
                        datetime.strptime(reminder, "%H:%M")
                    except ValueError:
                        messagebox.showwarning("Formato de hora", "Usa HH:MM, por ejemplo 18:00.", parent=dialog)
                        return
                values = (title, subject_var.get().strip() or None, ",".join(weekdays), reminder or None, int(active_var.get()))
                dup_query = (
                    "SELECT id FROM routines WHERE LOWER(TRIM(title))=LOWER(TRIM(?)) "
                    "AND COALESCE(LOWER(TRIM(subject)),'')=COALESCE(LOWER(TRIM(?)),'') "
                    "AND weekdays=? AND COALESCE(reminder_time,'')=COALESCE(?,'') "
                    "AND (? IS NULL OR id<>?) LIMIT 1"
                )
                if self.db.execute(dup_query, (values[0], values[1], values[2], values[3], routine_id, routine_id)).fetchone():
                    messagebox.showinfo("Rutina ya existente", "Ya existe una rutina idéntica configurada; no se creó un duplicado.", parent=dialog)
                    return
                if existing:
                    self.db.execute("UPDATE routines SET title=?, subject=?, weekdays=?, reminder_time=?, active=? WHERE id=?", (*values, routine_id))
                else:
                    self.db.execute("INSERT INTO routines(title, subject, weekdays, reminder_time, active, created_at) VALUES(?,?,?,?,?,?)", (*values, datetime.now().isoformat(timespec="seconds")))
                self.db.commit()
                refresh()
                dialog.destroy()

            ttk.Button(form, text="Guardar rutina", style="Accent.TButton", command=save).grid(row=10, column=3, sticky="e")

        def edit_selected() -> None:
            choice = tree.selection()
            if not choice:
                messagebox.showinfo("Selecciona una rutina", "Elige una rutina para editarla.", parent=window)
                return
            edit(int(choice[0]))

        def delete_selected() -> None:
            choice = tree.selection()
            if not choice:
                messagebox.showinfo("Selecciona una rutina", "Elige una rutina para eliminarla.", parent=window)
                return
            if messagebox.askyesno("Eliminar rutina", "¿Eliminar la repetición futura? Las tareas ya creadas no se borrarán.", parent=window):
                self.db.execute("DELETE FROM routines WHERE id=?", (int(choice[0]),))
                self.db.commit()
                refresh()

        tree.bind("<Double-1>", lambda _event: edit_selected())
        ttk.Button(actions, text="+ Agregar rutina", style="Accent.TButton", command=edit).pack(side="left")
        ttk.Button(actions, text="✏ Editar seleccionado", command=edit_selected).pack(side="left", padx=8)
        ttk.Button(actions, text="Eliminar", command=delete_selected).pack(side="left")
        refresh()

    def suggest_routine_patterns(self, parent, refresh) -> None:
        if self.settings.get("pattern_suggestions","false")!="true":
            messagebox.showinfo("Análisis desactivado","Activa primero “Permitir análisis local solo cuando yo lo solicite”.",parent=parent)
            return
        if not messagebox.askyesno("Revisar patrones locales","Voy a revisar solo tareas completadas manualmente en los últimos 90 días que tengan fecha de finalización registrada. El historial de versiones anteriores puede no incluirse. No se envía nada a Ollama ni se guarda nada con este análisis. ¿Continuar?",parent=parent):
            return
        suggestions=find_routine_pattern_candidates(self.db)
        if not suggestions:
            messagebox.showinfo("Sin patrones claros","No encontré tres o más tareas manuales con el mismo título, materia, día y hora en semanas distintas. No se creó ninguna rutina.",parent=parent)
            return
        window=tk.Toplevel(parent);window.title("Sugerencias de rutina · revisión manual");window.geometry("760x390");window.transient(parent)
        outer=ttk.Frame(window,padding=18);outer.pack(fill="both",expand=True)
        ttk.Label(outer,text="Patrones observados · no guardados",style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(outer,text="Son coincidencias exactas en tareas completadas, no inferencias sobre tu vida. Elige una y confirma por separado para crear la rutina.",wraplength=700).pack(anchor="w",pady=(4,8))
        top_actions=ttk.Frame(outer);top_actions.pack(side="top",fill="x",pady=(0,8))
        tree=ttk.Treeview(outer,columns=("title","subject","day","time","count","last"),show="headings",selectmode="browse",height=5)
        day_names=("Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo")
        for key,label,width in (("title","Tarea repetida",180),("subject","Materia",110),("day","Día",90),("time","Hora",75),("count","Veces",65),("last","Última fecha",100)):
            tree.heading(key,text=label);tree.column(key,width=width,anchor="w")
        tree.pack(fill="both",expand=True)
        for index,item in enumerate(suggestions):
            tree.insert("","end",iid=str(index),values=(item["title"],item["subject"] or "—",day_names[int(item["weekdays"])],item["reminder_time"] or "—",item["occurrences"],item["last_seen"]))
        def save_selected() -> None:
            selected=tree.selection()
            if not selected:
                messagebox.showinfo("Selecciona una sugerencia","Elige un patrón primero.",parent=window);return
            item=suggestions[int(selected[0])]
            day_text=day_names[int(item["weekdays"])]
            if not messagebox.askyesno("Confirmar nueva rutina",f"Crear rutina semanal “{item['title']}” para {day_text}"+(f" a las {item['reminder_time']}" if item["reminder_time"] else "")+"?\n\nSe añadirá a Rutinas y podrá generar tareas en adelante. Las tareas históricas no se cambiarán.",parent=window):return
            try:
                self.db.execute("INSERT INTO routines(title,subject,weekdays,reminder_time,active,created_at,source) VALUES(?,?,?,?,1,?,?)",(item["title"],item["subject"],item["weekdays"],item["reminder_time"],datetime.now().isoformat(timespec="seconds"),"Patrón local · confirmado por el usuario"))
                self.db.commit()
            except sqlite3.IntegrityError as exc:
                messagebox.showerror("No se creó la rutina",str(exc),parent=window);return
            refresh();window.destroy()
            messagebox.showinfo("Rutina creada","La rutina quedó guardada. Puedes editarla o eliminarla desde Rutinas.",parent=parent)
        ttk.Button(top_actions,text="+ Crear rutina seleccionada…",style="Accent.TButton",command=save_selected).pack(side="left")

    def apply_routines(self, day: date) -> int:
        weekday = str(day.weekday())
        routines = self.db.execute("SELECT * FROM routines WHERE active=1").fetchall()
        added = 0
        for item in routines:
            if weekday not in item["weekdays"].split(","):
                continue
            exists = self.db.execute(
                "SELECT 1 FROM tasks WHERE due_date=? AND (routine_id=? OR (LOWER(TRIM(title))=LOWER(TRIM(?)) AND COALESCE(LOWER(TRIM(subject)),'')=COALESCE(LOWER(TRIM(?)),''))) LIMIT 1",
                (day.isoformat(), item["id"], item["title"], item["subject"]),
            ).fetchone()
            if exists:
                continue
            self.db.execute("INSERT INTO tasks(title,due_date,priority,done,created_at,due_time,subject,routine_id) VALUES(?,?,?,?,?,?,?,?)", (item["title"], day.isoformat(), "Normal", 0, datetime.now().isoformat(timespec="seconds"), item["reminder_time"], item["subject"], item["id"]))
            added += 1
        if added:
            self.db.commit()
            self.refresh_tasks()
        return added

    def open_memories(self) -> None:
        window = tk.Toplevel(self)
        window.title("Memoria del asistente")
        window.geometry("980x470")
        window.transient(self)
        outer = ttk.Frame(window, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Recuerdos que tú autorizas", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Solo guarda recuerdos que agregues aquí. Se incluyen en solicitudes a Ollama local mientras estén vigentes. Puedes revisar el origen, poner fecha de caducidad y borrarlos; no guardes contraseñas, claves ni datos bancarios.", wraplength=930).pack(anchor="w", pady=(4, 10))
        actions = ttk.Frame(outer)
        actions.pack(side="top", fill="x", pady=(0, 8))
        tree = ttk.Treeview(outer, columns=("label", "category", "source", "expires", "content"), show="headings", selectmode="browse", height=6)
        for col, label, width in (("label", "Recuerdo", 135), ("category", "Categoría", 105), ("source", "Origen · creado", 190), ("expires", "Caduca", 100), ("content", "Detalle", 430)):
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor="w")
        tree.pack(fill="both", expand=True)

        def refresh() -> None:
            tree.delete(*tree.get_children())
            for item in self.db.execute("SELECT * FROM memories ORDER BY category, label"):
                expiry = item["expires_on"] or "No caduca"
                if item["expires_on"] and item["expires_on"] < date.today().isoformat():
                    expiry = "CADUCADO · " + item["expires_on"]
                created = str(item["created_at"] or "")[:10]
                source = str(item["source"] or "Origen no registrado") + (f" · {created}" if created else "")
                tree.insert("", "end", iid=str(item["id"]), values=(item["label"], item["category"], source, expiry, item["content"].replace("\n", " ")))

        def edit(memory_id: int | None = None) -> None:
            existing = self.db.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone() if memory_id else None
            dialog = tk.Toplevel(window)
            dialog.title("Editar recuerdo" if existing else "Agregar recuerdo")
            dialog.transient(window)
            dialog.grab_set()
            dialog.resizable(False, False)
            form = ttk.Frame(dialog, padding=18)
            form.pack(fill="both", expand=True)
            label_var = tk.StringVar(value=existing["label"] if existing else "")
            category_var = tk.StringVar(value=existing["category"] if existing else "Preferencia")
            expiry_var = tk.StringVar(value=(existing["expires_on"] or "") if existing else "")
            source = (existing["source"] or "Origen no registrado") if existing else "Entrada manual del usuario"
            ttk.Label(form, text="Nombre corto (por ejemplo, “Horario de estudio”)").grid(row=0, column=0, sticky="w")
            ttk.Entry(form, textvariable=label_var, width=58).grid(row=1, column=0, sticky="ew", pady=(3, 9))
            ttk.Label(form, text="Categoría").grid(row=2, column=0, sticky="w")
            ttk.Combobox(form, textvariable=category_var, values=("Preferencia", "Rutina", "Estudio", "Otra"), state="readonly", width=18).grid(row=3, column=0, sticky="w", pady=(3, 9))
            ttk.Label(form, text="Caduca el (AAAA-MM-DD; vacío significa sin caducidad)").grid(row=4, column=0, sticky="w")
            ttk.Entry(form, textvariable=expiry_var, width=18).grid(row=5, column=0, sticky="w", pady=(3, 9))
            ttk.Label(form, text=f"Origen: {source} · creado {str(existing['created_at'])[:10] if existing else date.today().isoformat()}", foreground="#91aabd").grid(row=6, column=0, sticky="w", pady=(0, 9))
            ttk.Label(form, text="Detalle (máximo 1500 caracteres)").grid(row=7, column=0, sticky="w")
            content = tk.Text(form, width=58, height=6, wrap="word", bg="#081624", fg="#eff8ff", insertbackground="#eff8ff", selectbackground="#1b4961", selectforeground="#ffffff")
            content.grid(row=8, column=0, sticky="nsew", pady=(3, 10))
            if existing:
                content.insert("1.0", existing["content"])

            def save() -> None:
                label = label_var.get().strip()
                text = content.get("1.0", "end-1c").strip()
                expiry_text = expiry_var.get().strip()
                if not label or not text:
                    messagebox.showwarning("Falta información", "Escribe el nombre y el detalle del recuerdo.", parent=dialog)
                    return
                if len(text) > 1500:
                    messagebox.showwarning("Texto demasiado largo", "El recuerdo debe tener 1500 caracteres o menos.", parent=dialog)
                    return
                if expiry_text:
                    try:
                        expiry_text = date.fromisoformat(expiry_text).isoformat()
                    except ValueError:
                        messagebox.showwarning("Formato de fecha", "Usa AAAA-MM-DD para la caducidad o deja el campo vacío.", parent=dialog)
                        return
                if existing:
                    self.db.execute("UPDATE memories SET label=?,content=?,category=?,expires_on=? WHERE id=?", (label,text,category_var.get(),expiry_text or None,memory_id))
                else:
                    self.db.execute("INSERT INTO memories(label,content,category,created_at,source,expires_on) VALUES(?,?,?,?,?,?)", (label,text,category_var.get(),datetime.now().isoformat(timespec="seconds"),source,expiry_text or None))
                self.db.commit()
                refresh()
                dialog.destroy()

            ttk.Button(form, text="Guardar recuerdo", style="Accent.TButton", command=save).grid(row=9, column=0, sticky="e")

        def edit_selected() -> None:
            choice = tree.selection()
            if not choice:
                messagebox.showinfo("Selecciona un recuerdo", "Elige un recuerdo para editarlo.", parent=window)
                return
            edit(int(choice[0]))

        def delete_selected() -> None:
            choice = tree.selection()
            if not choice:
                messagebox.showinfo("Selecciona un recuerdo", "Elige un recuerdo para borrarlo.", parent=window)
                return
            if messagebox.askyesno("Borrar recuerdo", "¿Eliminar permanentemente este recuerdo?", parent=window):
                self.db.execute("DELETE FROM memories WHERE id=?", (int(choice[0]),))
                self.db.commit()
                refresh()

        tree.bind("<Double-1>", lambda _event: edit_selected())
        ttk.Button(actions, text="+ Agregar recuerdo", style="Accent.TButton", command=edit).pack(side="left")
        ttk.Button(actions, text="✏ Editar seleccionado", command=edit_selected).pack(side="left", padx=8)
        ttk.Button(actions, text="Eliminar", command=delete_selected).pack(side="left")
        refresh()

    def open_classes(self) -> None:
        window = tk.Toplevel(self)
        window.title("Mis clases y materias · horario semanal")
        window.geometry("820x560")
        window.minsize(680, 440)
        window.transient(self)
        outer = ttk.Frame(window, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Agrega o edita tus materias y horarios", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Cada clase se repite semanalmente. Puedes agregarla rápido aquí arriba, con el botón “+ Agregar clase”, o diciéndoselo a CLARA-V en el chat.", wraplength=760).pack(anchor="w", pady=(4, 8))
        days = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")

        actions = ttk.Frame(outer)
        actions.pack(side="top", fill="x", pady=(0, 8))

        quick_bar = ttk.Frame(outer, style="Card.TFrame", padding=10)
        quick_bar.pack(side="top", fill="x", pady=(0, 10))
        q_name_var = tk.StringVar(value="")
        q_day_var = tk.StringVar(value=days[0])
        q_start_var = tk.StringVar(value="08:00")
        q_end_var = tk.StringVar(value="10:00")
        q_place_var = tk.StringVar(value="")
        ttk.Label(quick_bar, text="Materia:").grid(row=0, column=0, sticky="w")
        ttk.Entry(quick_bar, textvariable=q_name_var, width=20).grid(row=0, column=1, padx=(4, 10))
        ttk.Label(quick_bar, text="Día:").grid(row=0, column=2, sticky="w")
        ttk.Combobox(quick_bar, textvariable=q_day_var, values=days, state="readonly", width=11).grid(row=0, column=3, padx=(4, 10))
        ttk.Label(quick_bar, text="Inicio:").grid(row=0, column=4, sticky="w")
        ttk.Entry(quick_bar, textvariable=q_start_var, width=7).grid(row=0, column=5, padx=(4, 8))
        ttk.Label(quick_bar, text="Fin:").grid(row=0, column=6, sticky="w")
        ttk.Entry(quick_bar, textvariable=q_end_var, width=7).grid(row=0, column=7, padx=(4, 8))
        ttk.Label(quick_bar, text="Aula:").grid(row=0, column=8, sticky="w")
        ttk.Entry(quick_bar, textvariable=q_place_var, width=10).grid(row=0, column=9, padx=(4, 8))

        tree = ttk.Treeview(outer, columns=("day", "class", "time", "place"), show="headings", selectmode="browse", height=6)
        for col, label, width in (("day", "Día", 105), ("class", "Clase", 210), ("time", "Horario", 120), ("place", "Aula / lugar", 150)):
            tree.heading(col, text=label)
            tree.column(col, width=width)
        tree.pack(fill="both", expand=True)

        def refresh() -> None:
            tree.delete(*tree.get_children())
            records = self.db.execute("SELECT * FROM classes ORDER BY weekday, start_time, name").fetchall()
            for record in records:
                slot = record["start_time"] + ("–" + record["end_time"] if record["end_time"] else "")
                tree.insert("", "end", iid=str(record["id"]), values=(days[record["weekday"]], record["name"], slot, record["location"] or "—"))

        def quick_save() -> None:
            name, start, end = q_name_var.get().strip(), q_start_var.get().strip(), q_end_var.get().strip()
            if not name:
                messagebox.showwarning("Falta el nombre", "Escribe el nombre de la materia arriba.", parent=window)
                return
            try:
                datetime.strptime(start, "%H:%M")
                if end:
                    datetime.strptime(end, "%H:%M")
                    if end <= start:
                        messagebox.showwarning("Horario inválido", "La hora de fin debe ser posterior a la de inicio.", parent=window)
                        return
            except ValueError:
                messagebox.showwarning("Formato de hora", "Usa HH:MM, por ejemplo 08:00.", parent=window)
                return
            _ok, q_msg = execute_add_class_from_chat(
                self.db,
                {
                    "name": name,
                    "weekdays": [days.index(q_day_var.get())],
                    "start_time": start,
                    "end_time": end or None,
                    "location": q_place_var.get().strip() or None,
                },
            )
            q_name_var.set("")
            q_place_var.set("")
            refresh()
            if "⚠️ Atención:" in q_msg:
                messagebox.showwarning("Choque de horario detectado", q_msg, parent=window)

        ttk.Button(quick_bar, text="+ Guardar rápido", style="Accent.TButton", command=quick_save).grid(row=0, column=10, padx=(4, 0))

        def add(class_id: int | None = None) -> None:
            existing = self.db.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone() if class_id else None
            dialog = tk.Toplevel(window)
            dialog.title("Editar clase" if existing else "Agregar clase")
            dialog.transient(window)
            dialog.grab_set()
            form = ttk.Frame(dialog, padding=18)
            form.pack(fill="both", expand=True)
            name_var = tk.StringVar(value=existing["name"] if existing else "")
            day_var = tk.StringVar(value=days[existing["weekday"]] if existing else days[0])
            start_var = tk.StringVar(value=existing["start_time"] if existing else "")
            end_var = tk.StringVar(value=(existing["end_time"] or "") if existing else "")
            place_var = tk.StringVar(value=(existing["location"] or "") if existing else "")
            ttk.Label(form, text="Nombre de la clase").grid(row=0, column=0, sticky="w")
            ttk.Entry(form, textvariable=name_var, width=36).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(3, 10))
            ttk.Label(form, text="Día").grid(row=2, column=0, sticky="w")
            ttk.Combobox(form, textvariable=day_var, values=days, state="readonly", width=18).grid(row=3, column=0, sticky="w", pady=(3, 10))
            ttk.Label(form, text="Inicio (HH:MM)").grid(row=4, column=0, sticky="w")
            ttk.Entry(form, textvariable=start_var, width=12).grid(row=5, column=0, sticky="w", pady=(3, 10))
            ttk.Label(form, text="Fin (opcional)").grid(row=4, column=1, sticky="w", padx=(12, 0))
            ttk.Entry(form, textvariable=end_var, width=12).grid(row=5, column=1, sticky="w", padx=(12, 0), pady=(3, 10))
            ttk.Label(form, text="Aula o lugar (opcional)").grid(row=6, column=0, sticky="w")
            ttk.Entry(form, textvariable=place_var, width=36).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(3, 12))

            def save() -> None:
                name, start, end = name_var.get().strip(), start_var.get().strip(), end_var.get().strip()
                if not name:
                    messagebox.showwarning("Falta el nombre", "Escribe el nombre de la clase.", parent=dialog)
                    return
                try:
                    datetime.strptime(start, "%H:%M")
                    if end:
                        datetime.strptime(end, "%H:%M")
                        if end <= start:
                            messagebox.showwarning("Horario inválido", "La hora de fin debe ser posterior a la de inicio.", parent=dialog)
                            return
                except ValueError:
                    messagebox.showwarning("Formato de hora", "Usa HH:MM, por ejemplo 08:30.", parent=dialog)
                    return
                wd_idx = days.index(day_var.get())
                conflicts = detect_class_schedule_conflicts(
                    self.db,
                    [wd_idx],
                    start,
                    end or None,
                    exclude_class_ids={int(class_id)} if class_id else None,
                    exclude_class_name=name,
                )
                values = (name, wd_idx, start, end or None, place_var.get().strip() or None)
                if existing:
                    self.db.execute("UPDATE classes SET name=?, weekday=?, start_time=?, end_time=?, location=?, reminded_on=NULL WHERE id=?", (*values, class_id))
                    self.db.execute("UPDATE class_exceptions SET class_name=? WHERE class_id=?", (name, class_id))
                else:
                    self.db.execute("INSERT INTO classes(name, weekday, start_time, end_time, location) VALUES(?,?,?,?,?)", values)
                self.db.commit()
                refresh()
                dialog.destroy()
                if conflicts:
                    messagebox.showwarning(
                        "Choque de horario detectado",
                        format_schedule_conflict_warning(conflicts),
                        parent=window,
                    )

            ttk.Button(form, text="Guardar clase", style="Accent.TButton", command=save).grid(row=8, column=1, sticky="e")

        def edit_selected() -> None:
            chosen = tree.selection()
            if not chosen:
                messagebox.showinfo("Selecciona una clase", "Elige una clase para editarla.", parent=window)
                return
            add(int(chosen[0]))

        tree.bind("<Double-1>", lambda _event: edit_selected())

        def delete() -> None:
            chosen = tree.selection()
            if not chosen:
                messagebox.showinfo("Selecciona una clase", "Elige una clase para quitarla del horario.", parent=window)
                return
            if messagebox.askyesno("Eliminar clase", "¿Quitar esta clase y sus excepciones puntuales del horario? Las tareas ya creadas no se borrarán.", parent=window):
                self.db.execute("DELETE FROM class_exceptions WHERE class_id=?", (int(chosen[0]),))
                self.db.execute("DELETE FROM classes WHERE id=?", (int(chosen[0]),))
                self.db.commit()
                refresh()

        def check_conflicts_ui() -> None:
            report_text = build_schedule_conflicts_report(self.db)
            messagebox.showinfo("Revisión de empalmes de horario", report_text, parent=window)

        ttk.Button(actions, text="+ Agregar clase", style="Accent.TButton", command=add).pack(side="left")
        ttk.Button(actions, text="✏ Editar seleccionado", command=edit_selected).pack(side="left", padx=8)
        ttk.Button(actions, text="Eliminar", command=delete).pack(side="left")
        ttk.Button(actions, text="🔍 Revisar empalmes", command=check_conflicts_ui).pack(side="left", padx=8)
        ttk.Button(actions, text="🗓 Cuadrícula semanal", command=self.open_weekly_grid_schedule).pack(side="left")
        ttk.Button(actions, text="📓 Apuntes", command=self.open_subject_notebook).pack(side="left", padx=6)
        ttk.Button(actions, text="Calendario escolar…", command=self.open_calendar_exceptions).pack(side="right")
        refresh()

    # --- Punto 4: Temporizador Pomodoro y Cronómetro de Enfoque en la Esfera Viva ---

    def start_pomodoro_timer(
        self,
        minutes: int = 25,
        label: str = "Enfoque Pomodoro",
        subject: str | None = None,
    ) -> str:
        """Start a countdown Pomodoro / Focus session integrated with the Living Sphere."""
        mins = max(1, min(240, int(minutes or 25)))
        clean_label = str(label or subject or f"Enfoque Pomodoro ({mins} min)").strip()[:90]
        self.pomodoro_active = True
        self.pomodoro_paused = False
        self.pomodoro_total_minutes = mins
        self.pomodoro_remaining_seconds = mins * 60
        self.pomodoro_label = clean_label
        self.pomodoro_subject = str(subject).strip() if subject else None
        self.set_sphere_state("listening")
        if hasattr(self, "sphere_state_label") and self.sphere_state_label is not None:
            try:
                self.sphere_state_label.configure(
                    text=f"⏱ Pomodoro en curso: {mins:02d}:00 · {clean_label}"
                )
            except Exception:
                pass
        if hasattr(self, "after"):
            try:
                self.after(1000, self._tick_pomodoro)
            except Exception:
                pass
        return (
            f"⏱ ¡Pomodoro iniciado! Cuenta regresiva de {mins} minuto(s) para «{clean_label}». "
            "Verás el tiempo restante junto a la esfera viva y te avisaré por voz y en pantalla en cuanto termine."
        )

    def pause_pomodoro_timer(self) -> str:
        if not getattr(self, "pomodoro_active", False):
            return "No hay ningún temporizador Pomodoro activo en este momento."
        if getattr(self, "pomodoro_paused", False):
            return "El temporizador Pomodoro ya está en pausa."
        self.pomodoro_paused = True
        rem = max(0, int(getattr(self, "pomodoro_remaining_seconds", 0)))
        mm, ss = divmod(rem, 60)
        lbl = str(getattr(self, "pomodoro_label", "Enfoque"))
        if hasattr(self, "sphere_state_label") and self.sphere_state_label is not None:
            try:
                self.sphere_state_label.configure(text=f"⏸ Pomodoro en pausa: {mm:02d}:{ss:02d} · {lbl}")
            except Exception:
                pass
        return f"⏸ Puse en pausa tu Pomodoro de «{lbl}» con {mm:02d}:{ss:02d} restantes."

    def resume_pomodoro_timer(self) -> str:
        if not getattr(self, "pomodoro_active", False):
            return "No hay ningún temporizador Pomodoro activo para reanudar."
        if not getattr(self, "pomodoro_paused", False):
            return "Tu Pomodoro ya está corriendo."
        self.pomodoro_paused = False
        rem = max(0, int(getattr(self, "pomodoro_remaining_seconds", 0)))
        mm, ss = divmod(rem, 60)
        lbl = str(getattr(self, "pomodoro_label", "Enfoque"))
        if hasattr(self, "after"):
            try:
                self.after(1000, self._tick_pomodoro)
            except Exception:
                pass
        return f"▶ Reanudé tu Pomodoro de «{lbl}» ({mm:02d}:{ss:02d} restantes)."

    def stop_pomodoro_timer(self) -> str:
        if not getattr(self, "pomodoro_active", False):
            return "No hay ningún temporizador Pomodoro activo."
        lbl = str(getattr(self, "pomodoro_label", "Enfoque"))
        self.pomodoro_active = False
        self.pomodoro_paused = False
        self.pomodoro_remaining_seconds = 0
        self.set_sphere_state("idle")
        return f"⏹ Detuve y cancelé el temporizador Pomodoro de «{lbl}»."

    def pomodoro_status_summary(self) -> str:
        if not getattr(self, "pomodoro_active", False):
            return "No tienes ningún Pomodoro activo ahora mismo. Puedes decirme «pon un Pomodoro de 25 minutos para estudiar Matemáticas»."
        rem = max(0, int(getattr(self, "pomodoro_remaining_seconds", 0)))
        mm, ss = divmod(rem, 60)
        lbl = str(getattr(self, "pomodoro_label", "Enfoque"))
        state_str = "en pausa" if getattr(self, "pomodoro_paused", False) else "en curso"
        return f"⏱ Tu Pomodoro de «{lbl}» está {state_str}: quedan {mm:02d}:{ss:02d} (de {getattr(self, 'pomodoro_total_minutes', 25)} min)."

    def _tick_pomodoro(self) -> None:
        if not getattr(self, "pomodoro_active", False) or getattr(self, "pomodoro_paused", False):
            return
        rem = max(0, int(getattr(self, "pomodoro_remaining_seconds", 0)) - 1)
        self.pomodoro_remaining_seconds = rem
        lbl = str(getattr(self, "pomodoro_label", "Enfoque Pomodoro"))
        mm, ss = divmod(rem, 60)
        if rem > 0:
            if hasattr(self, "sphere_state_label") and self.sphere_state_label is not None:
                try:
                    self.sphere_state_label.configure(
                        text=f"⏱ Pomodoro en curso: {mm:02d}:{ss:02d} · {lbl}"
                    )
                except Exception:
                    pass
            if hasattr(self, "after"):
                try:
                    self.after(1000, self._tick_pomodoro)
                except Exception:
                    pass
            return
        # Completed!
        self.pomodoro_active = False
        self.pomodoro_paused = False
        mins = int(getattr(self, "pomodoro_total_minutes", 25) or 25)
        try:
            self.db.execute(
                "INSERT INTO action_events(action,outcome,created_at) VALUES(?,?,?)",
                ("Sesión Pomodoro completada", f"{mins} min · {lbl}"[:120], datetime.now().isoformat(timespec="seconds")),
            )
            self.db.commit()
        except Exception:
            pass
        self.set_sphere_state("idle")
        done_msg = (
            f"⏱ ¡Tiempo cumplido! Terminaste tu sesión de enfoque de {mins} minuto(s) sobre «{lbl}». "
            "Tómate 5 minutos de descanso para estirar y despejar la mente."
        )
        self.append_chat("Asistente", done_msg)

    def open_pomodoro_dialog(self) -> None:
        window = tk.Toplevel(self)
        window.title("⏱ Temporizador Pomodoro y Enfoque")
        window.geometry("620x360")
        window.transient(self)
        outer = ttk.Frame(window, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="⏱ Temporizador Pomodoro y sesiones de enfoque", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Inicia bloques de concentración con cuenta regresiva en vivo junto a la esfera de CLARA-V y aviso hablado al terminar. También puedes pedirlo por voz o chat: «pon un Pomodoro de 25 minutos para estudiar Matemáticas».",
            wraplength=570,
        ).pack(anchor="w", pady=(4, 10))

        top_actions = ttk.Frame(outer)
        top_actions.pack(side="top", fill="x", pady=(0, 12))

        form = ttk.Frame(outer, style="Card.TFrame", padding=12)
        form.pack(fill="x", pady=(0, 12))
        subjects = [str(r[0]) for r in self.db.execute("SELECT DISTINCT name FROM classes ORDER BY name").fetchall()]
        subj_var = tk.StringVar(value=getattr(self, "pomodoro_label", "") or (subjects[0] if subjects else "Estudio enfocado"))
        mins_var = tk.StringVar(value=str(getattr(self, "pomodoro_total_minutes", 25) or 25))
        ttk.Label(form, text="Materia o actividad:").grid(row=0, column=0, sticky="w")
        ttk.Combobox(form, textvariable=subj_var, values=tuple(subjects) if subjects else ("Estudio enfocado",), width=30).grid(row=0, column=1, padx=(8, 14), sticky="w")
        ttk.Label(form, text="Minutos:").grid(row=0, column=2, sticky="w")
        ttk.Entry(form, textvariable=mins_var, width=8).grid(row=0, column=3, padx=(6, 0), sticky="w")

        status_lbl = ttk.Label(outer, text=self.pomodoro_status_summary(), font=("Segoe UI", 11, "bold"))
        status_lbl.pack(anchor="w", pady=(4, 8))

        def refresh_status() -> None:
            try:
                status_lbl.configure(text=self.pomodoro_status_summary())
            except Exception:
                return

        def start_custom(preset_mins: int | None = None, preset_label: str | None = None) -> None:
            try:
                m_val = preset_mins if preset_mins is not None else int(mins_var.get().strip())
            except ValueError:
                messagebox.showwarning("Minutos inválidos", "Escribe un número de minutos entre 1 y 240.", parent=window)
                return
            lbl_val = preset_label or subj_var.get().strip() or f"Enfoque ({m_val} min)"
            msg = self.start_pomodoro_timer(minutes=m_val, label=lbl_val)
            refresh_status()
            self.append_chat("Asistente", msg)

        def toggle_pause() -> None:
            if getattr(self, "pomodoro_paused", False):
                msg = self.resume_pomodoro_timer()
            else:
                msg = self.pause_pomodoro_timer()
            refresh_status()
            self.append_chat("Asistente", msg)

        def stop_now() -> None:
            msg = self.stop_pomodoro_timer()
            refresh_status()
            self.append_chat("Asistente", msg)

        ttk.Button(top_actions, text="▶ Pomodoro 25 min", style="Accent.TButton", command=lambda: start_custom(25)).pack(side="left")
        ttk.Button(top_actions, text="☕ Descanso 5 min", command=lambda: start_custom(5, "Descanso corto")).pack(side="left", padx=6)
        ttk.Button(top_actions, text="▶ Iniciar personalizado", command=lambda: start_custom()).pack(side="left")
        ttk.Button(top_actions, text="⏸ Pausar / Reanudar", command=toggle_pause).pack(side="left", padx=6)
        ttk.Button(top_actions, text="⏹ Detener", command=stop_now).pack(side="left")

    # --- Punto 5: Cuaderno de apuntes rápidos y carpeta vinculada por Materia ---

    def open_subject_notebook(self, initial_subject: str | None = None) -> None:
        ensure_subject_notebook_tables(self.db)
        window = tk.Toplevel(self)
        window.title("📓 Cuaderno de apuntes rápidos y carpetas por materia")
        window.geometry("940x540")
        window.minsize(760, 420)
        window.transient(self)
        outer = ttk.Frame(window, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="📓 Cuaderno de apuntes y carpetas por materia", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Guarda apuntes rápidos de clase, vincúlalos con la carpeta local de cada materia y consúltalos desde el chat o con Llama 3.2 («apunta en Matemáticas Discretas que el examen viene hasta grafos»).",
            wraplength=880,
        ).pack(anchor="w", pady=(4, 8))

        actions = ttk.Frame(outer)
        actions.pack(side="top", fill="x", pady=(0, 8))

        filter_bar = ttk.Frame(outer, style="Card.TFrame", padding=10)
        filter_bar.pack(side="top", fill="x", pady=(0, 8))
        all_subjects = sorted(
            {
                str(r[0]).strip()
                for r in (
                    list(self.db.execute("SELECT DISTINCT name FROM classes WHERE name IS NOT NULL").fetchall())
                    + list(self.db.execute("SELECT DISTINCT subject FROM subject_notes WHERE subject IS NOT NULL").fetchall())
                    + list(self.db.execute("SELECT DISTINCT subject FROM subject_folders WHERE subject IS NOT NULL").fetchall())
                )
                if str(r[0]).strip()
            }
        )
        filter_values = ("Todas las materias", *all_subjects)
        filter_var = tk.StringVar(value=initial_subject if initial_subject in all_subjects else "Todas las materias")
        folder_status_var = tk.StringVar(value="📁 Selecciona una materia para ver o abrir su carpeta vinculada.")
        ttk.Label(filter_bar, text="Filtrar por materia:").pack(side="left")
        filter_combo = ttk.Combobox(filter_bar, textvariable=filter_var, values=filter_values, state="readonly", width=28)
        filter_combo.pack(side="left", padx=(8, 14))
        ttk.Label(filter_bar, textvariable=folder_status_var, foreground="#91aabd").pack(side="left", fill="x", expand=True)

        tree = ttk.Treeview(outer, columns=("subject", "title", "created", "content"), show="headings", selectmode="browse", height=8)
        for col, label, width in (("subject", "Materia", 170), ("title", "Título", 190), ("created", "Fecha", 115), ("content", "Apunte", 410)):
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor="w")
        tree.pack(fill="both", expand=True)

        def refresh(*_args) -> None:
            tree.delete(*tree.get_children())
            chosen_subj = filter_var.get().strip()
            rows = list_subject_notes(self.db, None if chosen_subj == "Todas las materias" else chosen_subj)
            for row in rows:
                tree.insert(
                    "",
                    "end",
                    iid=str(row["id"]),
                    values=(row["subject"], row["title"], str(row["created_at"])[:16].replace("T", " "), str(row["content"]).replace("\n", " ")),
                )
            if chosen_subj and chosen_subj != "Todas las materias":
                linked = get_subject_folder(self.db, chosen_subj)
                folder_status_var.set(f"📁 Carpeta de «{chosen_subj}»: {linked}" if linked else f"📁 «{chosen_subj}» aún no tiene carpeta vinculada.")
            else:
                folder_status_var.set("📁 Elige una materia o un apunte para vincular o abrir su carpeta local.")

        def edit_note(note_id: int | None = None) -> None:
            existing = self.db.execute("SELECT * FROM subject_notes WHERE id=?", (note_id,)).fetchone() if note_id else None
            dialog = tk.Toplevel(window)
            dialog.title("Editar apunte" if existing else "Nuevo apunte de materia")
            dialog.transient(window)
            dialog.grab_set()
            form = ttk.Frame(dialog, padding=18)
            form.pack(fill="both", expand=True)
            default_subj = existing["subject"] if existing else (filter_var.get() if filter_var.get() != "Todas las materias" else (all_subjects[0] if all_subjects else "General"))
            s_var = tk.StringVar(value=default_subj)
            t_var = tk.StringVar(value=existing["title"] if existing else "")
            ttk.Label(form, text="Materia").grid(row=0, column=0, sticky="w")
            ttk.Combobox(form, textvariable=s_var, values=tuple(all_subjects) if all_subjects else ("General",), width=36).grid(row=1, column=0, sticky="ew", pady=(3, 9))
            ttk.Label(form, text="Título corto (opcional)").grid(row=2, column=0, sticky="w")
            ttk.Entry(form, textvariable=t_var, width=48).grid(row=3, column=0, sticky="ew", pady=(3, 9))
            ttk.Label(form, text="Contenido del apunte").grid(row=4, column=0, sticky="w")
            body_box = tk.Text(form, width=56, height=6, wrap="word", bg="#081624", fg="#eff8ff", insertbackground="#eff8ff")
            body_box.grid(row=5, column=0, sticky="nsew", pady=(3, 10))
            if existing:
                body_box.insert("1.0", existing["content"])

            def save_note() -> None:
                subj_txt = s_var.get().strip() or "General"
                title_txt = t_var.get().strip()
                content_txt = body_box.get("1.0", "end-1c").strip()
                if not content_txt:
                    messagebox.showwarning("Falta el apunte", "Escribe el contenido del apunte.", parent=dialog)
                    return
                if existing:
                    update_subject_note(self.db, int(note_id), subj_txt, title_txt or existing["title"], content_txt)
                else:
                    add_subject_note(self.db, subj_txt, content_txt, title=title_txt or None)
                refresh()
                dialog.destroy()

            ttk.Button(form, text="Guardar apunte", style="Accent.TButton", command=save_note).grid(row=6, column=0, sticky="e")

        def edit_selected() -> None:
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Selecciona un apunte", "Elige un apunte de la lista para editarlo.", parent=window)
                return
            edit_note(int(sel[0]))

        def delete_selected() -> None:
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Selecciona un apunte", "Elige un apunte para eliminarlo.", parent=window)
                return
            if messagebox.askyesno("Eliminar apunte", "¿Eliminar este apunte del cuaderno?", parent=window):
                delete_subject_note(self.db, int(sel[0]))
                refresh()

        def _active_subject_for_folder() -> str | None:
            sel = tree.selection()
            if sel:
                row = self.db.execute("SELECT subject FROM subject_notes WHERE id=?", (int(sel[0]),)).fetchone()
                if row and row["subject"]:
                    return str(row["subject"])
            if filter_var.get() and filter_var.get() != "Todas las materias":
                return filter_var.get()
            return all_subjects[0] if all_subjects else None

        def link_folder_ui() -> None:
            subj = _active_subject_for_folder()
            if not subj:
                messagebox.showinfo("Materia requerida", "Primero registra una materia o un apunte para vincularle una carpeta.", parent=window)
                return
            chosen_dir = filedialog.askdirectory(parent=window, title=f"Selecciona la carpeta local para {subj}", mustexist=True)
            if not chosen_dir:
                return
            try:
                saved = set_subject_folder(self.db, subj, chosen_dir)
                refresh()
                messagebox.showinfo("Carpeta vinculada", f"La materia «{subj}» quedó vinculada con:\n{saved}", parent=window)
            except Exception as exc:
                messagebox.showerror("Error al vincular carpeta", str(exc), parent=window)

        def open_folder_ui() -> None:
            subj = _active_subject_for_folder()
            if not subj:
                messagebox.showinfo("Selecciona una materia", "Elige una materia en el filtro o selecciona un apunte.", parent=window)
                return
            folder = get_subject_folder(self.db, subj)
            if not folder:
                messagebox.showinfo("Sin carpeta vinculada", f"La materia «{subj}» aún no tiene carpeta vinculada. Usa «📁 Vincular carpeta de materia…».", parent=window)
                return
            if sys.platform == "win32":
                try:
                    launch_selected_folder(Path(folder))
                except Exception as exc:
                    messagebox.showerror("No se pudo abrir", str(exc), parent=window)
            else:
                messagebox.showinfo("Carpeta vinculada", f"Carpeta de «{subj}»:\n{folder}", parent=window)

        filter_combo.bind("<<ComboboxSelected>>", refresh)
        tree.bind("<Double-1>", lambda _event: edit_selected())
        ttk.Button(actions, text="➕ Nuevo apunte", style="Accent.TButton", command=lambda: edit_note(None)).pack(side="left")
        ttk.Button(actions, text="✏ Editar seleccionado", command=edit_selected).pack(side="left", padx=8)
        ttk.Button(actions, text="🗑 Eliminar", command=delete_selected).pack(side="left")
        ttk.Button(actions, text="📁 Vincular carpeta de materia…", command=link_folder_ui).pack(side="left", padx=8)
        ttk.Button(actions, text="📂 Abrir carpeta vinculada", command=open_folder_ui).pack(side="left")
        ttk.Button(
            actions,
            text="🧠 Modo Estudio / Examen…",
            style="Accent.TButton",
            command=lambda: self.open_active_study_dialog(initial_subject=_active_subject_for_folder()),
        ).pack(side="left", padx=(8, 0))
        refresh()

    # --- Incremento 9: Ventana interactiva de Modo Estudio Activo (Flashcards y Examen Rápido) ---

    def open_active_study_dialog(self, initial_subject: str | None = None) -> None:
        ensure_subject_notebook_tables(self.db)
        window = tk.Toplevel(self)
        window.title("🧠 Modo Estudio Activo · Flashcards y Examen Rápido desde tus Apuntes")
        window.geometry("880x560")
        window.minsize(720, 440)
        window.transient(self)
        outer = ttk.Frame(window, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="🧠 Modo Estudio Activo · Repaso con Flashcards y Examen Rápido", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Genera tarjetas de autoevaluación y preguntas de examen directamente desde tus apuntes y tareas locales (o dime en el chat: «hazme un examen rápido de Redes» o «crea tarjetas de repaso de Cálculo»).",
            wraplength=820,
        ).pack(anchor="w", pady=(4, 10))

        all_subjects = sorted(
            {
                str(r[0]).strip()
                for r in (
                    list(self.db.execute("SELECT DISTINCT name FROM classes WHERE name IS NOT NULL").fetchall())
                    + list(self.db.execute("SELECT DISTINCT subject FROM subject_notes WHERE subject IS NOT NULL").fetchall())
                )
                if str(r[0]).strip()
            }
        )
        subj_options = ("Todas las materias", *all_subjects)
        subj_var = tk.StringVar(value=initial_subject if initial_subject in all_subjects else "Todas las materias")
        count_var = tk.StringVar(value="5")

        top_bar = ttk.Frame(outer, style="Card.TFrame", padding=10)
        top_bar.pack(fill="x", pady=(0, 10))
        ttk.Label(top_bar, text="Materia:").pack(side="left")
        subj_combo = ttk.Combobox(top_bar, textvariable=subj_var, values=subj_options, state="readonly", width=26)
        subj_combo.pack(side="left", padx=(6, 12))
        ttk.Label(top_bar, text="Preguntas:").pack(side="left")
        cnt_combo = ttk.Combobox(top_bar, textvariable=count_var, values=("3", "5", "8", "10"), state="readonly", width=5)
        cnt_combo.pack(side="left", padx=(6, 12))

        state: dict[str, object] = {
            "cards": [],
            "idx": 0,
            "show_answer": False,
            "known": set(),
            "subject": "Todas tus materias",
        }

        progress_var = tk.StringVar(value="Pulsa «Generar tarjetas» para comenzar tu sesión de estudio.")
        ttk.Label(outer, textvariable=progress_var, foreground="#60e2df", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))

        card_box = tk.Text(
            outer,
            height=11,
            wrap="word",
            bg="#081624",
            fg="#eff8ff",
            insertbackground="#eff8ff",
            font=("Segoe UI", 11),
            padx=14,
            pady=12,
        )
        card_box.pack(fill="both", expand=True, pady=(0, 10))
        card_box.configure(state="disabled")

        def _render_current() -> None:
            cards = list(state.get("cards") or [])
            card_box.configure(state="normal")
            card_box.delete("1.0", "end")
            if not cards:
                progress_var.set("No hay apuntes registrados para esa materia todavía.")
                card_box.insert(
                    "1.0",
                    "Aún no tienes apuntes guardados en esta materia.\n\n"
                    "Ve a «📓 Apuntes» o escribe en el chat:\n"
                    "«apunta en Cálculo que la derivada de sen(x) es cos(x)».",
                )
                card_box.configure(state="disabled")
                return
            idx = max(0, min(len(cards) - 1, int(state.get("idx") or 0)))
            state["idx"] = idx
            c = cards[idx]
            known_set = state.get("known") or set()
            progress_var.set(
                f"Tarjeta {idx + 1} de {len(cards)}  ·  Materia: {c['subject']}  ·  Dominadas: {len(known_set)}/{len(cards)}"
            )
            status_badge = " [✅ DOMINADA]" if idx in known_set else ""
            body = (
                f"📌 Tema: {c['title']}{status_badge}\n\n"
                f"❓ PREGUNTA:\n{c['question']}\n\n"
                f"💡 PISTA:\n{c['hint']}\n"
            )
            if state.get("show_answer"):
                body += f"\n✅ RESPUESTA SEGÚN TUS APUNTES:\n{c['answer']}\n"
            else:
                body += "\n(Pulsa «👁 Mostrar / Ocultar respuesta» para verificar tu respuesta)"
            card_box.insert("1.0", body)
            card_box.configure(state="disabled")

        def _generate(*_a) -> None:
            chosen = subj_var.get().strip()
            try:
                cnt = int(count_var.get() or "5")
            except ValueError:
                cnt = 5
            quiz = generate_active_study_quiz(self.db, None if chosen == "Todas las materias" else chosen, count=cnt)
            state["cards"] = list(quiz.get("cards") or [])
            state["subject"] = str(quiz.get("subject") or chosen)
            state["idx"] = 0
            state["show_answer"] = False
            state["known"] = set()
            self.active_study_session = quiz
            _render_current()

        def _toggle_answer() -> None:
            state["show_answer"] = not bool(state.get("show_answer"))
            _render_current()

        def _prev_card() -> None:
            cards = list(state.get("cards") or [])
            if cards:
                state["idx"] = (int(state.get("idx") or 0) - 1) % len(cards)
                state["show_answer"] = False
                _render_current()

        def _next_card() -> None:
            cards = list(state.get("cards") or [])
            if cards:
                state["idx"] = (int(state.get("idx") or 0) + 1) % len(cards)
                state["show_answer"] = False
                _render_current()

        def _mark_known() -> None:
            cards = list(state.get("cards") or [])
            if not cards:
                return
            known_set = set(state.get("known") or set())
            known_set.add(int(state.get("idx") or 0))
            state["known"] = known_set
            _render_current()

        def _send_to_chat() -> None:
            quiz = {"subject": state.get("subject"), "cards": state.get("cards")}
            self.active_study_session = quiz
            self.append_chat("Asistente", format_active_study_quiz_chat(quiz, mode="quiz"))

        ttk.Button(top_bar, text="🔄 Generar tarjetas", style="Accent.TButton", command=_generate).pack(side="left", padx=(0, 8))
        ttk.Button(top_bar, text="📤 Enviar examen al chat", command=_send_to_chat).pack(side="left")

        nav_bar = ttk.Frame(outer)
        nav_bar.pack(fill="x")
        ttk.Button(nav_bar, text="⬅ Anterior", command=_prev_card).pack(side="left")
        ttk.Button(nav_bar, text="👁 Mostrar / Ocultar respuesta", style="Accent.TButton", command=_toggle_answer).pack(side="left", padx=8)
        ttk.Button(nav_bar, text="Siguiente ➡", command=_next_card).pack(side="left")
        ttk.Button(nav_bar, text="✅ Ya me la sé", command=_mark_known).pack(side="left", padx=12)

        subj_combo.bind("<<ComboboxSelected>>", _generate)
        cnt_combo.bind("<<ComboboxSelected>>", _generate)
        _generate()

    # --- Punto 6: Vista semanal visual en cuadrícula (Horario Lunes–Sábado con colores y empalmes en rojo) ---

    def open_weekly_grid_schedule(self) -> None:
        window = tk.Toplevel(self)
        window.title("🗓 Horario semanal en cuadrícula · Lunes a Sábado")
        window.geometry("1080x660")
        window.minsize(820, 480)
        window.transient(self)
        outer = ttk.Frame(window, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="🗓 Vista semanal en cuadrícula (07:00 – 21:00)", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="🟦 Clase semanal   ·   🟩 Bloque de estudio   ·   🟪 Rutina con hora   ·   🟥 ⚠️ Empalme / choque de horario",
            foreground="#60e2df",
        ).pack(anchor="w", pady=(2, 8))

        top_actions = ttk.Frame(outer)
        top_actions.pack(side="top", fill="x", pady=(0, 8))

        canvas_frame = ttk.Frame(outer)
        canvas_frame.pack(fill="both", expand=True)
        canvas = tk.Canvas(canvas_frame, bg="#07111f", highlightthickness=0)
        v_scroll = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        h_scroll = ttk.Scrollbar(canvas_frame, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        canvas.pack(side="left", fill="both", expand=True)

        def draw_grid() -> None:
            canvas.delete("all")
            grid = build_weekly_grid_data(self.db)
            days_labels = grid["days_labels"]
            cells_by_day = grid["cells_by_day"]
            show_days = 7 if cells_by_day.get(6) else 6
            left_margin = 68
            top_margin = 38
            col_w = 152
            hour_h = 42
            start_hour = 7
            end_hour = 21
            total_w = left_margin + show_days * col_w + 24
            total_h = top_margin + (end_hour - start_hour) * hour_h + 28

            # Header background & day labels
            canvas.create_rectangle(0, 0, total_w, top_margin, fill="#10243a", outline="#29445a")
            canvas.create_text(left_margin // 2, top_margin // 2, text="Hora", fill="#91aabd", font=("Segoe UI", 9, "bold"))
            for wd in range(show_days):
                x0 = left_margin + wd * col_w
                canvas.create_line(x0, 0, x0, total_h, fill="#29445a")
                canvas.create_text(x0 + col_w // 2, top_margin // 2, text=days_labels[wd], fill="#eff8ff", font=("Segoe UI", 10, "bold"))

            # Hour rows (07:00 to 21:00)
            for hr in range(start_hour, end_hour + 1):
                y = top_margin + (hr - start_hour) * hour_h
                canvas.create_line(0, y, total_w, y, fill="#1b3348")
                if hr < end_hour:
                    canvas.create_text(left_margin // 2, y + 12, text=f"{hr:02d}:00", fill="#91aabd", font=("Segoe UI", 9))

            # Render blocks per day
            palette = {
                "class": ("#154c68", "#58d6d8"),
                "block": ("#1b5e3c", "#66e39a"),
                "routine": ("#46306b", "#b99aff"),
                "conflict": ("#7a1c24", "#ff5c6c"),
            }
            for wd in range(show_days):
                x0 = left_margin + wd * col_w + 4
                x1 = left_margin + (wd + 1) * col_w - 4
                for item in cells_by_day.get(wd, []):
                    s_min = max(start_hour * 60, min(end_hour * 60, int(item["start_min"])))
                    e_min = max(s_min + 25, min(end_hour * 60, int(item["end_min"])))
                    y0 = top_margin + ((s_min - start_hour * 60) / 60.0) * hour_h + 1
                    y1 = top_margin + ((e_min - start_hour * 60) / 60.0) * hour_h - 1
                    fill_col, border_col = palette["conflict"] if item["has_conflict"] else palette.get(str(item["kind"]), palette["class"])
                    canvas.create_rectangle(x0, y0, x1, y1, fill=fill_col, outline=border_col, width=2)
                    prefix = "⚠️ " if item["has_conflict"] else ""
                    sub = f"\n{item['subtitle']}" if item["subtitle"] else ""
                    label_txt = f"{prefix}{item['start_time']}–{item['end_time']}\n{item['title'][:22]}{sub[:24]}"
                    canvas.create_text(
                        x0 + 6,
                        y0 + 4,
                        anchor="nw",
                        text=label_txt,
                        fill="#ffffff",
                        font=("Segoe UI", 8, "bold"),
                        width=col_w - 16,
                    )

            canvas.configure(scrollregion=(0, 0, total_w, total_h))

        ttk.Button(top_actions, text="🔄 Actualizar cuadrícula", style="Accent.TButton", command=draw_grid).pack(side="left")
        ttk.Button(top_actions, text="📚 Mis clases…", command=self.open_classes).pack(side="left", padx=8)
        ttk.Button(top_actions, text="➕ Agenda / bloques…", command=self.open_week_agenda).pack(side="left")
        ttk.Button(
            top_actions,
            text="🔍 Revisar empalmes",
            command=lambda: messagebox.showinfo("Revisión de empalmes", build_schedule_conflicts_report(self.db), parent=window),
        ).pack(side="left", padx=8)
        draw_grid()

    def run_web_research_async(self, query: str) -> None:
        """Run internet research (Wikipedia ES + DuckDuckGo) in a background thread and post results to chat."""
        clean_q = str(query or "").strip()
        if not clean_q:
            return
        self.append_chat("Asistente", f"🌐 Investigando en internet sobre «{clean_q}»…", speak=False)

        def _worker() -> None:
            summary = search_web_summary(clean_q)
            self.ai_results.put(("online_summary", ("Asistente", summary)))

        threading.Thread(target=_worker, daemon=True).start()

    def open_math_and_web_tools(self) -> None:
        window = tk.Toplevel(self)
        window.title("🧮 Calculadora Matemática y 🌐 Buscador en Internet")
        window.geometry("760x480")
        window.minsize(640, 380)
        window.transient(self)
        outer = ttk.Frame(window, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="🧮 Calculadora Científica Segura y 🌐 Investigación en Internet", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Resuelve operaciones matemáticas al instante sin conexión (raíces, potencias, porcentajes, trigonometría) o investiga cualquier tema en Wikipedia y DuckDuckGo.",
            wraplength=710,
        ).pack(anchor="w", pady=(4, 10))

        top_actions = ttk.Frame(outer)
        top_actions.pack(side="top", fill="x", pady=(0, 10))

        input_frame = ttk.Frame(outer, style="Card.TFrame", padding=12)
        input_frame.pack(fill="x", pady=(0, 10))
        query_var = tk.StringVar(value="")
        ttk.Label(input_frame, text="Operación o tema a investigar:").pack(anchor="w")
        entry = ttk.Entry(input_frame, textvariable=query_var, width=72)
        entry.pack(fill="x", pady=(4, 0))

        output_box = tk.Text(outer, height=11, wrap="word", bg="#081624", fg="#eff8ff", insertbackground="#eff8ff", padx=10, pady=8, font=("Segoe UI", 10))
        output_box.pack(fill="both", expand=True)

        def _write_result(txt: str) -> None:
            output_box.configure(state="normal")
            output_box.delete("1.0", "end")
            output_box.insert("1.0", txt)
            output_box.configure(state="disabled")

        def do_math() -> None:
            raw = query_var.get().strip()
            if not raw:
                messagebox.showinfo("Escribe una expresión", "Ejemplo: (120 + 80) / 5, sqrt(144) + 18, o 15% de 840", parent=window)
                return
            try:
                val = evaluate_safe_math_expression(raw)
                msg = f"🧮 Expresión: {normalize_spanish_math_expression(raw)}\nResultado exacto: {val}"
                _write_result(msg)
                self.append_chat("Asistente", f"🧮 Resultado de `{normalize_spanish_math_expression(raw)}` = **{val}**")
            except Exception as exc:
                _write_result(f"No pude calcular la expresión: {exc}")

        def do_web() -> None:
            raw = query_var.get().strip()
            if not raw:
                messagebox.showinfo("Escribe un tema", "Ejemplo: Algoritmo de Dijkstra, Ley de Ohm, o Historia de Colima", parent=window)
                return
            _write_result(f"🌐 Investigando «{raw}» en Wikipedia y DuckDuckGo…")
            def _bg() -> None:
                res = search_web_summary(raw)
                self.ai_results.put(("online_summary", ("Asistente", res)))
                try:
                    window.after(0, lambda: _write_result(res))
                except Exception:
                    pass
            threading.Thread(target=_bg, daemon=True).start()

        ttk.Button(top_actions, text="🧮 Calcular operación", style="Accent.TButton", command=do_math).pack(side="left")
        ttk.Button(top_actions, text="🌐 Investigar en Internet", command=do_web).pack(side="left", padx=8)
        ttk.Button(top_actions, text="🧹 Limpiar", command=lambda: (query_var.set(""), _write_result(""))).pack(side="left")
        entry.focus_set()

    def open_calendar_exceptions(self) -> None:
        window = tk.Toplevel(self)
        window.title("Calendario escolar · excepciones")
        window.geometry("850x470")
        window.transient(self)
        outer = ttk.Frame(window, padding=16)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Excepciones de una sola fecha", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(outer, text="Vacaciones, cancelaciones y cambios puntuales no alteran tu horario semanal. Un día sin clases oculta las clases normales; las clases especiales que añadas para esa fecha sí aparecen.", wraplength=810).pack(anchor="w", pady=(3, 9))
        buttons = ttk.Frame(outer)
        buttons.pack(side="top", fill="x", pady=(0, 8))
        tree = ttk.Treeview(outer, columns=("date", "type", "class", "details"), show="headings", selectmode="browse", height=6)
        for col, label, width in (("date", "Fecha", 105), ("type", "Excepción", 180), ("class", "Clase / materia", 190), ("details", "Cambio / nota", 320)):
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor="w")
        tree.pack(fill="both", expand=True)
        labels = {"no_classes":"Día sin clases", "cancel":"Cancelar clase", "override":"Cambiar clase", "extra":"Clase especial"}

        def refresh() -> None:
            tree.delete(*tree.get_children())
            records = self.db.execute("SELECT * FROM class_exceptions ORDER BY exception_date, id").fetchall()
            for row in records:
                class_name = row["class_name"] or row["name"] or "—"
                details = row["note"] or ""
                if row["action"] == "override":
                    changes = " · ".join(part for part in (row["start_time"], row["end_time"], row["location"], row["name"]) if part)
                    details = (changes + (" · " if changes and details else "") + details)
                elif row["action"] == "extra":
                    details = " · ".join(part for part in (row["start_time"], row["end_time"], row["location"], row["note"]) if part)
                tree.insert("", "end", iid=str(row["id"]), values=(row["exception_date"], labels.get(row["action"], row["action"]), class_name, details or "—"))

        def edit(exception_id: int | None = None) -> None:
            existing = self.db.execute("SELECT * FROM class_exceptions WHERE id=?", (exception_id,)).fetchone() if exception_id else None
            dialog = tk.Toplevel(window)
            dialog.title("Editar excepción" if existing else "Nueva excepción escolar")
            dialog.transient(window)
            dialog.grab_set()
            form = ttk.Frame(dialog, padding=16)
            form.pack(fill="both", expand=True)
            type_values = ("Día sin clases", "Cancelar clase", "Cambiar clase", "Clase especial")
            to_action = dict(zip(type_values, ("no_classes", "cancel", "override", "extra")))
            action_to_label = {value:key for key,value in to_action.items()}
            selected_action = existing["action"] if existing else "no_classes"
            date_var = tk.StringVar(value=existing["exception_date"] if existing else date.today().isoformat())
            type_var = tk.StringVar(value=action_to_label.get(selected_action, type_values[0]))
            class_rows = self.db.execute("SELECT id,name FROM classes ORDER BY name,weekday,start_time").fetchall()
            class_choices = {f"{row['id']} · {row['name']}": row["id"] for row in class_rows}
            selected_class = next((key for key,value in class_choices.items() if existing and value == existing["class_id"]), "")
            class_var = tk.StringVar(value=selected_class)
            name_var = tk.StringVar(value=(existing["name"] or "") if existing else "")
            start_var = tk.StringVar(value=(existing["start_time"] or "") if existing else "")
            end_var = tk.StringVar(value=(existing["end_time"] or "") if existing else "")
            place_var = tk.StringVar(value=(existing["location"] or "") if existing else "")
            note_var = tk.StringVar(value=(existing["note"] or "") if existing else "")
            until_var = tk.StringVar(value="")
            ttk.Label(form, text="Fecha (AAAA-MM-DD)").grid(row=0, column=0, sticky="w")
            ttk.Entry(form, textvariable=date_var, width=18).grid(row=1, column=0, sticky="w", pady=(3, 9))
            ttk.Label(form, text="Tipo de excepción").grid(row=0, column=1, sticky="w", padx=(12, 0))
            ttk.Combobox(form, textvariable=type_var, values=type_values, state="readonly", width=28).grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(3, 9))
            ttk.Label(form, text="Clase semanal (cancelar/cambiar)").grid(row=2, column=0, sticky="w")
            ttk.Combobox(form, textvariable=class_var, values=tuple(class_choices), state="readonly", width=34).grid(row=3, column=0, columnspan=2, sticky="w", pady=(3, 9))
            ttk.Label(form, text="Nombre (cambio o clase especial)").grid(row=4, column=0, sticky="w")
            ttk.Entry(form, textvariable=name_var, width=39).grid(row=5, column=0, columnspan=2, sticky="w", pady=(3, 9))
            ttk.Label(form, text="Inicio HH:MM (obligatorio para clase especial)").grid(row=6, column=0, sticky="w")
            ttk.Entry(form, textvariable=start_var, width=15).grid(row=7, column=0, sticky="w", pady=(3, 9))
            ttk.Label(form, text="Fin HH:MM (opcional)").grid(row=6, column=1, sticky="w", padx=(12, 0))
            ttk.Entry(form, textvariable=end_var, width=15).grid(row=7, column=1, sticky="w", padx=(12, 0), pady=(3, 9))
            ttk.Label(form, text="Aula/lugar o nueva ubicación").grid(row=8, column=0, sticky="w")
            ttk.Entry(form, textvariable=place_var, width=39).grid(row=9, column=0, columnspan=2, sticky="w", pady=(3, 9))
            ttk.Label(form, text="Nota opcional (por ejemplo, vacaciones/examen)").grid(row=10, column=0, sticky="w")
            ttk.Entry(form, textvariable=note_var, width=58).grid(row=11, column=0, columnspan=2, sticky="ew", pady=(3, 8))
            ttk.Label(form, text="Hasta inclusive (opcional; rango de días sin clases)").grid(row=12, column=0, sticky="w")
            ttk.Entry(form, textvariable=until_var, width=18).grid(row=13, column=0, sticky="w", pady=(3, 9))

            def save() -> None:
                try:
                    exception_day = datetime.strptime(date_var.get().strip(), "%Y-%m-%d").date()
                except ValueError:
                    messagebox.showwarning("Fecha inválida", "Usa una fecha real con formato AAAA-MM-DD.", parent=dialog)
                    return
                action = to_action[type_var.get()]
                if until_var.get().strip() and action != "no_classes":
                    messagebox.showwarning("Rango no aplicable", "La fecha “Hasta” solo se usa para un rango de días sin clases; déjala vacía para los demás tipos.", parent=dialog)
                    return
                try:
                    until_day = datetime.strptime(until_var.get().strip(), "%Y-%m-%d").date() if action == "no_classes" and until_var.get().strip() else exception_day
                    exception_dates = inclusive_dates(exception_day, until_day)
                except ValueError as exc:
                    messagebox.showwarning("Rango inválido", f"Usa fechas AAAA-MM-DD y un rango de hasta dos años: {exc}", parent=dialog)
                    return
                class_id = class_choices.get(class_var.get()) if action in ("cancel", "override") else None
                if action in ("cancel", "override") and class_id is None:
                    messagebox.showwarning("Elige una clase", "Selecciona la clase semanal que se verá afectada.", parent=dialog)
                    return
                if class_id:
                    scheduled = self.db.execute("SELECT weekday FROM classes WHERE id=?", (class_id,)).fetchone()
                    if scheduled and scheduled["weekday"] != exception_day.weekday():
                        messagebox.showwarning("La clase no corresponde a esa fecha", "Esta clase semanal no ocurre en ese día. Usa “Clase especial” para añadir una sesión en otra fecha.", parent=dialog)
                        return
                if action == "extra" and (not name_var.get().strip() or not start_var.get().strip()):
                    messagebox.showwarning("Falta información", "Una clase especial necesita nombre y hora de inicio.", parent=dialog)
                    return
                for value in (start_var.get().strip(), end_var.get().strip()):
                    if value:
                        try:
                            datetime.strptime(value, "%H:%M")
                        except ValueError:
                            messagebox.showwarning("Hora inválida", "Usa el formato HH:MM, por ejemplo 13:30.", parent=dialog)
                            return
                if action == "extra" or action == "override":
                    start_value = start_var.get().strip()
                    end_value = end_var.get().strip()
                    base = self.db.execute("SELECT start_time,end_time FROM classes WHERE id=?", (class_id,)).fetchone() if class_id else None
                    effective_start = start_value or (base["start_time"] if base else None)
                    effective_end = end_value or (base["end_time"] if base else None)
                    if effective_start and effective_end and effective_end <= effective_start:
                        messagebox.showwarning("Horario inválido", "La hora de fin debe ser posterior al inicio.", parent=dialog)
                        return
                if action == "override" and not any((name_var.get().strip(), start_var.get().strip(), end_var.get().strip(), place_var.get().strip())):
                    messagebox.showwarning("Sin cambios", "Indica al menos un cambio de nombre, hora o aula.", parent=dialog)
                    return
                class_row = self.db.execute("SELECT name FROM classes WHERE id=?", (class_id,)).fetchone() if class_id else None
                class_name = class_row["name"] if class_row else (name_var.get().strip() or (existing["class_name"] if existing and existing["action"] == "extra" else None))
                with self.db:
                    for index, one_day in enumerate(exception_dates):
                        values = (one_day.isoformat(), class_id, class_name, action, name_var.get().strip() or None, start_var.get().strip() or None, end_var.get().strip() or None, place_var.get().strip() or None, note_var.get().strip() or None)
                        target_id = exception_id if index == 0 else None
                        if not target_id and action == "no_classes":
                            duplicate = self.db.execute("SELECT id FROM class_exceptions WHERE exception_date=? AND action='no_classes' ORDER BY id DESC LIMIT 1", (values[0],)).fetchone()
                            target_id = duplicate["id"] if duplicate else None
                        if not target_id and class_id and action in ("cancel", "override"):
                            duplicate = self.db.execute("SELECT id FROM class_exceptions WHERE exception_date=? AND class_id=? AND action IN ('cancel','override') ORDER BY id DESC LIMIT 1", (values[0], class_id)).fetchone()
                            target_id = duplicate["id"] if duplicate else None
                        if target_id:
                            self.db.execute("UPDATE class_exceptions SET exception_date=?,class_id=?,class_name=?,action=?,name=?,start_time=?,end_time=?,location=?,note=?,reminded_on=NULL WHERE id=?", (*values, target_id))
                        else:
                            self.db.execute("INSERT INTO class_exceptions(exception_date,class_id,class_name,action,name,start_time,end_time,location,note) VALUES(?,?,?,?,?,?,?,?,?)", values)
                    if class_id:
                        self.db.execute("UPDATE classes SET reminded_on=NULL WHERE id=?", (class_id,))
                refresh()
                dialog.destroy()

            ttk.Button(form, text="Guardar excepción", style="Accent.TButton", command=save).grid(row=13, column=1, sticky="e")

        def selected_id() -> int | None:
            chosen = tree.selection()
            return int(chosen[0]) if chosen else None

        def edit_selected() -> None:
            chosen = selected_id()
            if chosen is None:
                messagebox.showinfo("Selecciona una excepción", "Elige una excepción para editarla.", parent=window)
            else:
                edit(chosen)

        def delete_selected() -> None:
            chosen = selected_id()
            if chosen is None:
                messagebox.showinfo("Selecciona una excepción", "Elige una excepción para eliminarla.", parent=window)
            elif messagebox.askyesno("Eliminar excepción", "¿Quitar esta excepción? El horario semanal base no cambiará.", parent=window):
                self.db.execute("DELETE FROM class_exceptions WHERE id=?", (chosen,))
                self.db.commit()
                refresh()

        tree.bind("<Double-1>", lambda _event: edit_selected())
        ttk.Button(buttons, text="+ Agregar excepción", style="Accent.TButton", command=edit).pack(side="left")
        ttk.Button(buttons, text="✏ Editar seleccionado", command=edit_selected).pack(side="left", padx=8)
        ttk.Button(buttons, text="Eliminar", command=delete_selected).pack(side="left")
        refresh()

    def prompt_new_assignment(self) -> None:
        if messagebox.askyesno("¿Nueva tarea?", "¿Te dejaron una tarea nueva que quieras anotar ahora?", parent=self):
            self.add_task()

    def show_next_commitment(self) -> None:
        summary = build_next_commitment_summary(self.db, datetime.now())
        self.append_chat("Asistente", summary)

    def _fetch_weather_text(self) -> str:
        location_parts = [part.strip() for part in self.settings["weather_location"].split(",")]
        city = location_parts[0]
        region = location_parts[1] if len(location_parts) > 1 else ""
        try:
            q = urllib.parse.urlencode({"name": city, "count": 5, "language": "es", "format": "json"})
            with urllib.request.urlopen("https://geocoding-api.open-meteo.com/v1/search?" + q, timeout=12) as response:
                places = json.loads(response.read().decode("utf-8")).get("results", [])
            place = next((p for p in places if region and region.lower() in p.get("admin1", "").lower()), places[0] if places else None)
            if not place:
                raise ValueError("No se encontró la ciudad configurada")
            params = urllib.parse.urlencode({"latitude": place["latitude"], "longitude": place["longitude"], "current": "temperature_2m,precipitation", "daily": "precipitation_probability_max,temperature_2m_max,temperature_2m_min", "timezone": "auto", "forecast_days": 1})
            with urllib.request.urlopen("https://api.open-meteo.com/v1/forecast?" + params, timeout=12) as response:
                weather = json.loads(response.read().decode("utf-8"))
            current = weather.get("current", {})
            daily = weather.get("daily", {})
            rain = (daily.get("precipitation_probability_max") or [None])[0]
            tmax = (daily.get("temperature_2m_max") or [None])[0]
            tmin = (daily.get("temperature_2m_min") or [None])[0]
            return f"Clima {place.get('name', city)}: {current.get('temperature_2m', '—')}°C ahora; máxima {tmax}°C, mínima {tmin}°C; probabilidad máxima de lluvia {rain if rain is not None else 'sin dato'}%."
        except Exception:
            return "No pude consultar el clima. Revisa la conexión a internet e inténtalo de nuevo."

    def _fetch_news_text(self, topic_override: str | None = None) -> str:
        topic = topic_override if topic_override in NEWS_TOPICS else self.settings["news_topic"]
        source_name = self.settings.get("news_source", DEFAULT_SETTINGS["news_source"])
        source_spec = NEWS_SOURCE_FEEDS.get(source_name, "google")
        try:
            news_count = int(self.settings.get("news_count", "5"))
        except ValueError:
            news_count = 5
        news_count = max(1, min(10, news_count))
        topic_query = {"General": "", "Tecnología": "tecnología", "Ciencia": "ciencia", "Educación": "educación", "Deportes": "deportes"}[topic]
        try:
            if source_spec == "google":
                news_params = {"hl": "es-419", "gl": "MX", "ceid": "MX:es-419"}
                if topic_query:
                    news_params["q"] = topic_query
                feed_url = "https://news.google.com/rss?" + urllib.parse.urlencode(news_params)
            else:
                feed_url = source_spec
            request = urllib.request.Request(
                feed_url,
                headers={"User-Agent": "Clara-Personal/2.0.0", "Accept": "application/rss+xml, application/xml, text/xml"},
            )
            with urllib.request.urlopen(request, timeout=12) as response:
                feed_bytes = response.read(2 * 1024 * 1024 + 1)
            items = parse_news_feed(feed_bytes, source_name, news_count, include_details=True)
            # Enrich items that lack an article summary (e.g. single-item Google News RSS entries)
            enriched_count = 0
            for item in items:
                if not item.get("summary") and enriched_count < 3:
                    raw_t = re.sub(r"\s+-\s+[^-]+$", "", str(item.get("title") or "")).strip()
                    if raw_t:
                        snippets = _duckduckgo_instant_and_html(raw_t)
                        if snippets:
                            item["summary"] = snippets[0][:420]
                            enriched_count += 1
            if items:
                try:
                    save_news_cache(items, source_name, topic)
                except OSError:
                    pass
            return format_rich_news_digest(items, source_name, topic, is_google=(source_spec == "google"))
        except Exception:
            cached = load_news_cache()
            if cached and cached.get("items"):
                return format_rich_news_digest(
                    cached["items"][:news_count],
                    str(cached.get("source") or source_name),
                    topic,
                    is_google=(source_spec == "google"),
                    cached_stamp=str(cached.get("saved_at") or ""),
                )
            return f"No pude descargar titulares de {source_name} en este momento y no hay caché local reciente."

    def fetch_and_present_weather(self) -> None:
        self.ollama_status.configure(text=f"Consultando clima para {self.settings['weather_location']}…")
        threading.Thread(
            target=lambda: self.ai_results.put(("online_summary", ("Clima y noticias", self._fetch_weather_text()))),
            daemon=True,
        ).start()

    def fetch_and_present_news(self, topic_override: str | None = None) -> None:
        self.ollama_status.configure(text="Consultando titulares RSS…")
        threading.Thread(
            target=lambda: self.ai_results.put(("online_summary", ("Clima y noticias", self._fetch_news_text(topic_override)))),
            daemon=True,
        ).start()

    def show_morning_briefing(self) -> None:
        today = date.today()
        added_routines = self.apply_routines(today)
        days = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
        closure = day_off_for(self.db, today)
        classes = classes_for_date(self.db, today)
        tasks = self.db.execute("SELECT title, subject, due_date, due_time, priority FROM tasks WHERE done=0 AND (due_date IS NULL OR due_date<=?) ORDER BY CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date, due_time LIMIT 12", (today.isoformat(),)).fetchall()
        lines = [f"Rutina de mañana · {days[today.weekday()]} {today.strftime('%d/%m/%Y')}"]
        if added_routines:
            lines.append(f"Se añadieron {added_routines} tarea(s) de tus rutinas configuradas.")
        lines.append("Clases de hoy:")
        if closure:
            lines.append("• Día sin clases" + (f" — {closure['note']}" if closure["note"] else ""))
        lines.extend([f"• {row['start_time']}{('–' + row['end_time']) if row['end_time'] else ''} — {row['name']}" + (f" ({row['location']})" if row["location"] else "") for row in classes] or ([] if closure else ["• No hay clases guardadas para hoy."]))
        lines.append("Tareas pendientes o vencidas:")
        lines.extend([f"• {row['title']}" + (f" [{row['subject']}]" if row["subject"] else "") + f" — {row['due_date'] or 'sin fecha'}" + (f" {row['due_time']}" if row['due_time'] else "") + f" · prioridad {row['priority']}" for row in tasks] or ["• No hay tareas pendientes registradas."])
        morning_summary = "\n".join(lines)
        self._pending_morning_speech = morning_summary
        self.append_chat("Rutina matutina", morning_summary, speak=False)
        self.ollama_status.configure(text="Consultando clima y titulares…")

        def fetch_online() -> None:
            weather_line = self._fetch_weather_text()
            news_text = self._fetch_news_text()
            self.ai_results.put(("morning_online", weather_line + "\n\n" + news_text))

        threading.Thread(target=fetch_online, daemon=True).start()

    def refresh_tasks(self) -> None:
        for item in self.task_tree.get_children():
            self.task_tree.delete(item)
        rows = self.db.execute("SELECT * FROM tasks ORDER BY done, CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date, due_time, id DESC").fetchall()
        for row in rows:
            subject = f"[{row['subject']}] " if row["subject"] else ""
            repeat_mark = "↻ " if (row["repeat_rule"] or "none") != "none" else ""
            title = ("✓  " if row["done"] else "") + repeat_mark + subject + row["title"]
            when = row["due_date"] or "Sin fecha"
            if row["due_time"]:
                when += " " + row["due_time"]
            self.task_tree.insert("", "end", iid=str(row["id"]), values=(title, when, row["priority"], "Hecha" if row["done"] else "Pendiente"))

    def add_task(self, preset: str = "", task_id: int | None = None, prefill: dict[str, str | None] | None = None) -> None:
        existing = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone() if task_id else None
        prefill = prefill or {}
        dialog = tk.Toplevel(self)
        dialog.title("Editar tarea" if existing else "Agregar tarea")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(True, True)
        box = ttk.Frame(dialog, padding=18)
        box.pack(fill="both", expand=True)
        top_controls = ttk.Frame(box)
        top_controls.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(top_controls, text="¿Qué necesitas hacer?", style="CardTitle.TLabel").pack(side="left")
        title_var = tk.StringVar(value=existing["title"] if existing else str(prefill.get("title") or preset))
        title_entry = ttk.Entry(box, textvariable=title_var, width=44)
        title_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        ttk.Label(box, text="Fecha (AAAA-MM-DD, opcional)").grid(row=2, column=0, sticky="w", pady=(0, 4))
        due_var = tk.StringVar(value=existing["due_date"] or "" if existing else str(prefill.get("due_date") or ""))
        ttk.Entry(box, textvariable=due_var, width=20).grid(row=3, column=0, sticky="w", pady=(0, 8))
        ttk.Label(box, text="Hora del recordatorio (HH:MM, opcional)").grid(row=4, column=0, sticky="w", pady=(0, 4))
        time_var = tk.StringVar(value=(existing["due_time"] or "") if existing else str(prefill.get("due_time") or ""))
        ttk.Entry(box, textvariable=time_var, width=12).grid(row=5, column=0, sticky="w", pady=(0, 8))
        ttk.Label(box, text="Prioridad").grid(row=6, column=0, sticky="w", pady=(0, 4))
        priority_var = tk.StringVar(value=existing["priority"] if existing else "Normal")
        ttk.Combobox(box, textvariable=priority_var, values=("Baja", "Normal", "Alta"), state="readonly", width=16).grid(row=7, column=0, sticky="w", pady=(0, 8))
        ttk.Label(box, text="Materia (opcional)").grid(row=8, column=0, sticky="w", pady=(0, 4))
        subject_var = tk.StringVar(value=(existing["subject"] or "") if existing else str(prefill.get("subject") or ""))
        ttk.Entry(box, textvariable=subject_var, width=30).grid(row=9, column=0, sticky="w", pady=(0, 8))
        ttk.Label(box, text="Descripción o notas (opcional)").grid(row=10, column=0, sticky="w", pady=(0, 4))
        description_text = tk.Text(box, width=44, height=3, wrap="word", relief="solid", borderwidth=1, bg="#081624", fg="#eff8ff", insertbackground="#eff8ff", selectbackground="#1b4961", selectforeground="#ffffff")
        description_text.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        initial_description = (existing["description"] or "") if existing else str(prefill.get("description") or "")
        if initial_description:
            description_text.insert("1.0", initial_description)
        ttk.Label(box, text="Repetición (requiere fecha)").grid(row=12, column=0, sticky="w", pady=(0, 4))
        repeat_labels = {"none": "No repetir", "daily": "Diaria", "weekly": "Semanal"}
        repeat_values = {value: key for key, value in repeat_labels.items()}
        initial_rule = (existing["repeat_rule"] or "none") if existing else "none"
        repeat_display = tk.StringVar(value=repeat_labels.get(initial_rule, "No repetir"))
        repeat_combo = ttk.Combobox(box, textvariable=repeat_display, values=tuple(repeat_labels.values()), state="readonly", width=16)
        repeat_combo.grid(row=13, column=0, sticky="w", pady=(0, 8))

        def save() -> None:
            title, due, due_time = title_var.get().strip(), due_var.get().strip(), time_var.get().strip()
            subject = subject_var.get().strip()
            description = description_text.get("1.0", "end-1c").strip()
            repeat_rule = repeat_values.get(repeat_display.get(), "none")
            if not title:
                messagebox.showwarning("Falta la tarea", "Escribe una descripción para la tarea.", parent=dialog)
                return
            if due:
                try:
                    datetime.strptime(due, "%Y-%m-%d")
                except ValueError:
                    messagebox.showwarning("Formato de fecha", "Usa AAAA-MM-DD, por ejemplo 2026-10-25.", parent=dialog)
                    return
            if repeat_rule != "none" and not due:
                messagebox.showwarning("Falta la fecha", "Una tarea recurrente requiere una fecha de inicio.", parent=dialog)
                return
            if due_time:
                try:
                    datetime.strptime(due_time, "%H:%M")
                except ValueError:
                    messagebox.showwarning("Formato de hora", "Usa HH:MM en formato de 24 horas, por ejemplo 09:30.", parent=dialog)
                    return
                if not due:
                    messagebox.showwarning("Falta la fecha", "Para programar un recordatorio, indica también la fecha.", parent=dialog)
                    return
            if existing:
                self.db.execute("UPDATE tasks SET title=?, description=?, due_date=?, priority=?, due_time=?, subject=?, reminded=0, repeat_rule=?, repeat_series_id=CASE WHEN ?='none' THEN NULL ELSE COALESCE(repeat_series_id,id) END WHERE id=?", (title, description or None, due or None, priority_var.get(), due_time or None, subject or None, repeat_rule, repeat_rule, task_id))
            else:
                cursor = self.db.execute("INSERT INTO tasks(title, description, due_date, priority, created_at, due_time, subject, repeat_rule) VALUES(?,?,?,?,?,?,?,?)", (title, description or None, due or None, priority_var.get(), datetime.now().isoformat(timespec="seconds"), due_time or None, subject or None, repeat_rule))
                if repeat_rule != "none":
                    self.db.execute("UPDATE tasks SET repeat_series_id=? WHERE id=?", (cursor.lastrowid, cursor.lastrowid))
            self.db.commit()
            self.refresh_tasks()
            dialog.destroy()
            action = "actualizada" if existing else "guardada"
            self.append_chat("Asistente", f"Tarea {action} localmente." + (f" El aviso está programado para las {due_time} del {due}." if due_time else ""))

        ttk.Button(top_controls, text="💾 Guardar", style="Accent.TButton", command=save).pack(side="right")
        ttk.Button(top_controls, text="Cancelar", command=dialog.destroy).pack(side="right", padx=6)
        controls = ttk.Frame(box)
        controls.grid(row=14, column=0, columnspan=2, sticky="e")
        ttk.Button(controls, text="Cancelar", command=dialog.destroy).pack(side="left", padx=6)
        ttk.Button(controls, text="Guardar", style="Accent.TButton", command=save).pack(side="left")
        title_entry.focus_set()
        dialog.bind("<Return>", lambda _event: save())

    def _selected_id(self) -> int | None:
        selected = self.task_tree.selection()
        return int(selected[0]) if selected else None

    def show_task_details(self) -> None:
        task_id = self._selected_id()
        if task_id is None:
            messagebox.showinfo("Selecciona una tarea", "Elige una tarea para consultar sus detalles.", parent=self)
            return
        row = self.db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return
        due = row["due_date"] or "Sin fecha"
        if row["due_time"]:
            due += " · " + row["due_time"]
        recurrence = {"daily": "Diaria", "weekly": "Semanal"}.get(row["repeat_rule"] or "none", "No repetir")
        details = (f"Tarea: {row['title']}\nMateria: {row['subject'] or 'Sin materia'}\nFecha/hora: {due}\nPrioridad: {row['priority']}\nEstado: {'Hecha' if row['done'] else 'Pendiente'}\nRepetición: {recurrence}\n\nDescripción:\n{row['description'] or 'Sin descripción.'}")
        messagebox.showinfo("Detalles de tarea", details, parent=self)

    def edit_selected(self) -> None:
        task_id = self._selected_id()
        if task_id is None:
            messagebox.showinfo("Selecciona una tarea", "Elige una tarea para editarla.")
            return
        self.add_task(task_id=task_id)

    def snooze_selected(self) -> None:
        task_id = self._selected_id()
        if task_id is None:
            messagebox.showinfo("Selecciona una tarea", "Elige una tarea primero.")
            return
        row = self.db.execute("SELECT title FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            return
        if not messagebox.askyesno("Posponer tarea", f"¿Mover “{row['title']}” a dentro de 10 minutos? Se actualizarán su fecha y hora."):
            return
        new_time = datetime.now().replace(second=0, microsecond=0)
        new_time = new_time + timedelta(minutes=10)
        self.db.execute("UPDATE tasks SET due_date=?, due_time=?, reminded=0 WHERE id=?", (new_time.strftime("%Y-%m-%d"), new_time.strftime("%H:%M"), task_id))
        self.db.commit()
        self.refresh_tasks()
        self.append_chat("Asistente", f"Pospuse “{row['title']}” hasta las {new_time.strftime('%H:%M')}.")

    def toggle_selected(self) -> None:
        task_id = self._selected_id()
        if task_id is None:
            messagebox.showinfo("Selecciona una tarea", "Elige una tarea de la lista primero.")
            return
        status_message = toggle_task_completion(self.db, task_id)
        if status_message is None:
            return
        self.refresh_tasks()
        self.append_chat("Sistema", status_message)

    def delete_selected(self) -> None:
        task_id = self._selected_id()
        if task_id is None:
            messagebox.showinfo("Selecciona una tarea", "Elige una tarea de la lista primero.")
            return
        if messagebox.askyesno("Eliminar tarea", "¿Quieres eliminar esta tarea? Esta acción no se puede deshacer."):
            self.db.execute("DELETE FROM tasks WHERE id=?", (task_id,))
            self.db.commit()
            self.refresh_tasks()

    def check_reminders(self) -> None:
        active = getattr(self, "active_reminder", None)
        self.reminders_paused = reminder_pause_active(self.settings)
        if self.reminders_paused:
            self.after(15000, self.check_reminders)
            return
        if active is None or not active.winfo_exists():
            alerts = collect_due_alerts(self.db, datetime.now())
            if alerts:
                hidden = self.state() in ("iconic", "withdrawn")
                if hidden and self.settings.get("native_notifications_enabled") == "true" and self._show_private_toast():
                    # The OS toast is intentionally generic; detailed task/class text stays in Clara.
                    pass
                else:
                    if hidden:
                        self.deiconify()
                        self.state("normal")
                        self.lift()
                    def cleared() -> None:
                        self.active_reminder = None
                    self.active_reminder = present_reminder(self, alerts[0], self.db, close_callback=cleared)
        self.after(15000, self.check_reminders)

    def _show_private_toast(self) -> bool:
        return show_windows_private_toast()

    def _start_tray_icon_if_enabled(self) -> None:
        if self.settings.get("minimize_to_tray") != "true" or sys.platform != "win32" or self.tray_icon is not None:
            return
        try:
            import pystray
            from PIL import Image, ImageDraw
            image = Image.new("RGBA", (64, 64), (7, 17, 31, 0))
            draw = ImageDraw.Draw(image)
            draw.ellipse((6, 6, 58, 58), fill="#0d6e83", outline="#60e2df", width=3)
            draw.ellipse((18, 18, 46, 46), fill="#d7ffff", outline="#60e2df", width=2)
            draw.text((26, 24), "L", fill="#07111f")
            menu = pystray.Menu(
                pystray.MenuItem("Mostrar Clara", lambda _icon, _item: self.ai_results.put(("tray_show", None)), default=True),
                pystray.MenuItem(lambda _item: "Reanudar avisos" if self.reminders_paused else "Pausar avisos · 8 h", lambda _icon, _item: self.ai_results.put(("tray_toggle_pause", None))),
                pystray.MenuItem("Salir de Clara", lambda _icon, _item: self.ai_results.put(("tray_quit", None))),
            )
            icon = pystray.Icon("ClaraAsistentePersonal", image, "Clara · Asistente Personal", menu)
            self.tray_icon = icon
            threading.Thread(target=icon.run, daemon=True, name="Clara system tray").start()
        except Exception:
            self.tray_icon = None
            try:
                self.settings["minimize_to_tray"] = "false"
                save_settings(self.settings)
            except OSError:
                pass
            messagebox.showwarning("Bandeja no disponible", "Instala las dependencias opcionales indicadas en README.md. La ventana se cerrará normalmente mientras falte el icono de bandeja.", parent=self)

    def _stop_tray_icon(self) -> None:
        icon, self.tray_icon = self.tray_icon, None
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass

    def open_reminder_history(self) -> None:
        window = tk.Toplevel(self)
        window.title("Historial de recordatorios")
        window.geometry("760x420")
        window.transient(self)
        outer = ttk.Frame(window, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Registro local de avisos", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(outer, text=f"Hora local del equipo: {local_timezone_label()} · Historial almacenado en SQLite local.").pack(anchor="w", pady=(4, 10))
        tree = ttk.Treeview(outer, columns=("time", "title", "action", "detail"), show="headings")
        for key, label, width in (("time", "Fecha/hora", 145), ("title", "Aviso", 180), ("action", "Acción", 105), ("detail", "Detalle", 280)):
            tree.heading(key, text=label)
            tree.column(key, width=width, anchor="w")
        tree.pack(fill="both", expand=True)
        action_labels = {"created": "Detectado", "delivered": "Mostrado", "snoozed": "Pospuesto", "dismissed": "Descartado"}
        rows = self.db.execute("SELECT a.action_at,e.title,a.action,a.details FROM reminder_actions a LEFT JOIN reminder_events e ON e.alert_key=a.alert_key ORDER BY a.id DESC LIMIT 200").fetchall()
        for row in rows:
            tree.insert("", "end", values=(row["action_at"], row["title"] or "Aviso eliminado", action_labels.get(row["action"], row["action"]), row["details"] or ""))

    def load_chat_history(self) -> None:
        if self.settings.get("chat_history_enabled") != "true":
            return
        rows = self.db.execute("SELECT speaker,content FROM chat_history ORDER BY id DESC LIMIT 200").fetchall()
        for row in reversed(rows):
            # Keep old persisted turns visible after the Luma-to-CLARA brand change.
            speaker = display_chat_speaker(row["speaker"])
            self.append_chat(speaker, row["content"], persist=False, speak=False)
        if rows:
            self.append_chat("Historial", f"Se cargaron {len(rows)} turnos recientes del historial local opcional.", persist=False)

    def append_chat(self, speaker: str, text: str, persist: bool = True, speak: bool = True) -> None:
        is_spoken_output = speaker.startswith("Asistente") or speaker in SPOKEN_CHAT_SPEAKERS
        if is_spoken_output:
            self.last_assistant_response = text
        if speaker.startswith("Asistente"):
            speaker = speaker.replace("Asistente", "Clara", 1)
        self.chat_log.configure(state="normal")
        self.chat_log.insert("end", speaker + "\n", "speaker")
        self.chat_log.insert("end", text + "\n")
        self.chat_log.see("end")
        self.chat_log.configure(state="disabled")
        # Deliberately retain only direct user/Clara turns, never status, security, action messages, or potential API keys.
        if persist and self.settings.get("chat_history_enabled") == "true" and speaker in ("Tú", "Clara") and not contains_potential_api_key(text):
            stored = text if len(text) <= 20000 else text[:20000] + "\n[Mensaje truncado en el historial local]"
            try:
                self.db.execute("INSERT INTO chat_history(speaker,content,created_at) VALUES(?,?,?)", (speaker, stored, datetime.now().isoformat(timespec="seconds")))
                self.db.execute("DELETE FROM chat_history WHERE id NOT IN (SELECT id FROM chat_history ORDER BY id DESC LIMIT 1000)")
                self.db.commit()
            except sqlite3.Error:
                try:
                    self.ollama_status.configure(text="El chat sigue disponible, pero no se pudo guardar el historial opcional.")
                except (AttributeError, tk.TclError):
                    pass
        if is_spoken_output and speak and self.settings.get("auto_speak_responses", "true") == "true":
            self._start_tts(text)

    def open_chat_history_tools(self) -> None:
        window = tk.Toplevel(self)
        window.title("Historial opcional de conversación")
        window.geometry("860x540")
        window.transient(self)
        frame = ttk.Frame(window, padding=16); frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Turnos de conversación guardados en este equipo", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Solo tus mensajes y las respuestas de Clara. Estado del sistema, acciones y reportes de seguridad quedan fuera. Se guardan hasta 1000 turnos; la exportación es texto sin cifrar.", wraplength=800, foreground="#f2c77b").pack(anchor="w", pady=(4, 8))
        controls = ttk.Frame(frame); controls.pack(side="top", fill="x", pady=(0, 8))
        tree = ttk.Treeview(frame, columns=("time", "speaker", "excerpt"), show="headings", selectmode="browse", height=6)
        for col, label, width in (("time", "Fecha/hora", 160), ("speaker", "Autor", 90), ("excerpt", "Vista previa", 560)):
            tree.heading(col, text=label); tree.column(col, width=width, anchor="w")
        tree.pack(fill="both", expand=True)
        rows = self.db.execute("SELECT id,speaker,content,created_at FROM chat_history ORDER BY id DESC LIMIT 200").fetchall()
        self._chat_history_rows = {int(row["id"]): row for row in rows}
        for row in rows:
            excerpt = " ".join(row["content"].split())
            display_speaker = display_chat_speaker(row["speaker"])
            tree.insert("", "end", iid=str(row["id"]), values=(row["created_at"].replace("T", " "), display_speaker, excerpt[:180]))
        preview = tk.Text(frame, height=5, wrap="word", bg="#081624", fg="#eff8ff", insertbackground="#eff8ff", selectbackground="#1b4961", selectforeground="#ffffff")
        preview.pack(fill="x", pady=(8, 0))
        preview.configure(state="disabled")
        def show_selected(_event=None) -> None:
            selected = tree.selection()
            if not selected: return
            row = self._chat_history_rows.get(int(selected[0]))
            if not row: return
            preview.configure(state="normal"); preview.delete("1.0", "end")
            preview.insert("1.0", (display_chat_speaker(row["speaker"])) + " · " + row["created_at"] + "\n\n" + row["content"])
            preview.configure(state="disabled")
        tree.bind("<<TreeviewSelect>>", show_selected)
        def export_history() -> None:
            all_rows = self.db.execute("SELECT speaker,content,created_at FROM chat_history ORDER BY id").fetchall()
            if not all_rows:
                messagebox.showinfo("Sin historial", "No hay turnos guardados para exportar.", parent=window); return
            if not messagebox.askyesno("Exportar conversación", "El archivo de texto no estará cifrado y puede contener información personal. ¿Continuar?", parent=window): return
            destination = filedialog.asksaveasfilename(parent=window, title="Exportar historial de conversación", defaultextension=".csv", filetypes=(("CSV UTF-8", "*.csv"),))
            if not destination: return
            try:
                with open(destination, "w", encoding="utf-8-sig", newline="") as output:
                    writer = csv.writer(output); writer.writerow(("fecha_hora", "autor", "mensaje"))
                    writer.writerows((row["created_at"], display_chat_speaker(row["speaker"]), row["content"]) for row in all_rows)
                messagebox.showinfo("Exportación lista", f"Se exportaron {len(all_rows)} turnos a:\n{destination}", parent=window)
            except OSError as exc:
                messagebox.showerror("No se pudo exportar", str(exc), parent=window)
        def clear_history() -> None:
            count = self.db.execute("SELECT COUNT(*) FROM chat_history").fetchone()[0]
            if not count:
                messagebox.showinfo("Sin historial", "No hay turnos guardados que borrar.", parent=window); return
            if not messagebox.askyesno("Borrar historial guardado", f"¿Eliminar los {count} turnos guardados? La operación no se puede deshacer desde Clara.", parent=window): return
            try:
                self.db.execute("PRAGMA secure_delete=ON")
                self.db.execute("DELETE FROM chat_history"); self.db.commit(); self.db.execute("VACUUM")
            except sqlite3.Error as exc:
                messagebox.showerror("No se pudo borrar", str(exc), parent=window); return
            tree.delete(*tree.get_children()); self._chat_history_rows = {}
            messagebox.showinfo("Historial borrado", "Se borraron los turnos guardados. Los mensajes de la sesión actual permanecen visibles hasta cerrar Clara.", parent=window)
        ttk.Button(controls, text="Exportar CSV…", command=export_history).pack(side="left")
        ttk.Button(controls, text="Borrar historial guardado…", command=clear_history).pack(side="left", padx=8)

    def refresh_ollama_models(self) -> None:
        self.ollama_status.configure(text="Buscando o iniciando servidor local de Ollama…")

        def _fetch_models() -> list[str]:
            return list_local_ollama_models()

        def worker() -> None:
            try:
                self.ai_results.put(("models", _fetch_models()))
                return
            except Exception as first_exc:
                started = ensure_local_ollama_running()
                if not started:
                    self.ai_results.put(("models_error", str(first_exc)))
                    return
                last_exc: Exception = first_exc
                for _attempt in range(10):
                    time.sleep(0.6)
                    try:
                        self.ai_results.put(("models", _fetch_models()))
                        return
                    except Exception as retry_exc:
                        last_exc = retry_exc
                self.ai_results.put(("models_error", str(last_exc)))

        threading.Thread(target=worker, daemon=True).start()

    def start_ollama_model_pull(self, model_name: str = "llama3.2", *, confirm_first: bool = True) -> None:
        """Download and activate a local Ollama model (default 'llama3.2', used in Viernes) after explicit user consent."""
        clean_model = re.sub(r"[^A-Za-z0-9_.:/-]", "", str(model_name or "llama3.2").strip()) or "llama3.2"
        if confirm_first and TKINTER_AVAILABLE and getattr(self, "tk", None) is not None:
            disclosure = (
                f"¿Deseas descargar y activar el modelo «{clean_model}» en tu Ollama local?\n\n"
                "• Fuente oficial: https://ollama.com/library/llama3.2\n"
                "• Modelo: llama3.2 (el modelo conversacional predeterminado de Viernes)\n"
                "• Tamaño aprox.: ~2.0 GB\n"
                "• Licencia: Meta Llama 3.2 Community License\n\n"
                "La descarga se realizará en segundo plano y se seleccionará automáticamente al terminar."
            )
            if not messagebox.askyesno("Confirmar descarga de modelo en Ollama local", disclosure, parent=self):
                self.append_chat("Asistente", f"Cancelé la descarga del modelo «{clean_model}».")
                return
        self.ollama_status.configure(text=f"Iniciando descarga del modelo «{clean_model}» en Ollama local…")
        self.append_chat(
            "Asistente",
            f"⬇ Iniciando descarga del modelo «{clean_model}» en tu Ollama local (en segundo plano). Te avisaré aquí en cuanto quede listo y activo.",
        )

        def _worker() -> None:
            ok, msg = pull_ollama_model_direct(
                clean_model,
                progress_callback=lambda st: self.ai_results.put(("model_pull_progress", st)),
            )
            if ok:
                self.ai_results.put(("model_pull_done", (clean_model, msg)))
            else:
                self.ai_results.put(("model_pull_error", (clean_model, msg)))

        threading.Thread(target=_worker, daemon=True).start()

    def open_ollama_model_downloader(self, initial_model: str = "llama3.2") -> None:
        """Open a dialog with top action buttons to download or switch local Ollama models (defaulting to Viernes's llama3.2)."""
        window = tk.Toplevel(self)
        window.title("Modelos locales de Ollama · Descargar o cambiar (llama3.2)")
        window.geometry("680x380")
        window.minsize(580, 320)
        window.transient(self)
        frame = ttk.Frame(window, padding=18)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Modelos conversacionales de Ollama (llama3.2 de Viernes)", style="CardTitle.TLabel").pack(anchor="w")
        sdk_state = "Activo (import ollama directo)" if OLLAMA_PYTHON_MODULE_AVAILABLE else "Modo API local directa (instala `pip install ollama` si deseas el paquete Python)"
        ttk.Label(
            frame,
            text=(
                f"En Viernes el modelo configurado era «llama3.2» (ligero, rápido y conversacional en español).\n"
                f"Estado del módulo Python ollama: {sdk_state}.\n"
                "Elige un modelo de la lista o escribe su nombre y usa los botones superiores para descargarlo o activarlo."
            ),
            wraplength=630,
            justify="left",
        ).pack(anchor="w", pady=(6, 12))

        top_btns = ttk.Frame(frame)
        top_btns.pack(side="top", fill="x", pady=(0, 12))

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(0, 10))
        ttk.Label(row, text="Modelo de Ollama:").pack(side="left")
        suggested_models = ("llama3.2", "llama3.2:1b", "qwen3:4b", "llama3.1", "mistral", "gemma2")
        chosen_var = tk.StringVar(value=initial_model or "llama3.2")
        combo = ttk.Combobox(row, textvariable=chosen_var, values=suggested_models, width=28)
        combo.pack(side="left", padx=(8, 0))

        info_label = ttk.Label(
            frame,
            text=(
                "Nota: «llama3.2» (~2.0 GB) es el modelo estándar de 3B parámetros usado en Viernes. "
                "Si tu equipo tiene poca RAM puedes elegir «llama3.2:1b» (~1.3 GB).\n"
                "También puedes descargarlo desde el chat diciendo: «descargar modelo llama3.2» o ejecutando `descargar_llama3.2.bat`."
            ),
            wraplength=630,
            foreground="#91aabd",
            justify="left",
        )
        info_label.pack(anchor="w", pady=(4, 8))

        def _download_now() -> None:
            target_m = chosen_var.get().strip() or "llama3.2"
            window.destroy()
            self.start_ollama_model_pull(target_m, confirm_first=True)

        def _use_existing() -> None:
            target_m = chosen_var.get().strip() or "llama3.2"
            self.model_var.set(target_m)
            warmup_local_ollama_model(target_m)
            self.ollama_status.configure(text=f"Modelo activo seleccionado: {target_m}")
            self.append_chat("Asistente", f"¡Listo! Seleccioné el modelo «{target_m}» para conversar con Ollama.")
            window.destroy()

        ttk.Button(top_btns, text="⬇ Descargar y activar en Ollama", style="Accent.TButton", command=_download_now).pack(side="left", padx=(0, 8))
        ttk.Button(top_btns, text="✓ Usar modelo (si ya está descargado)", command=_use_existing).pack(side="left", padx=(0, 8))
        ttk.Button(top_btns, text="Cerrar", command=window.destroy).pack(side="left")
        window.grab_set()

    def process_ai_results(self) -> None:
        try:
            while True:
                kind, payload = self.ai_results.get_nowait()
                if kind == "tray_show":
                    self.deiconify(); self.state("normal"); self.lift(); self.focus_force()
                elif kind == "tray_toggle_pause":
                    self.reminders_paused = not self.reminders_paused
                    self.settings["reminders_paused_until"] = (datetime.now() + timedelta(hours=8)).isoformat(timespec="seconds") if self.reminders_paused else ""
                    save_settings(self.settings)
                    if self.tray_icon is not None:
                        try: self.tray_icon.update_menu()
                        except Exception: pass
                    self.append_chat("Sistema", "Avisos pausados durante un máximo de 8 horas en Clara y las tareas programadas; después se reanudan automáticamente." if self.reminders_paused else "Avisos reanudados desde la bandeja.")
                elif kind == "tray_quit":
                    self._force_quit = True
                    self.after(0, self.on_close)
                    return
                elif kind == "diagnostics":
                    try:
                        if self.diagnostic_tree.winfo_exists():
                            self.diagnostic_tree.delete(*self.diagnostic_tree.get_children())
                            for state, component, detail in payload:
                                self.diagnostic_tree.insert("", "end", values=(state, component, detail))
                            self.diagnostic_status.configure(text=f"Revisión terminada: {len(payload)} comprobaciones. Los elementos ‘manuales’ requieren verificación o configuración adicional.")
                            self.diagnostic_run_button.configure(state="normal")
                    except (AttributeError, tk.TclError):
                        pass
                elif kind == "vt_result":
                    self.show_vt_result(payload)
                elif kind == "vt_cancelled":
                    self.vt_busy = False
                elif kind == "defender_status":
                    self.append_chat("Estado de seguridad · Defender", payload)
                    messagebox.showinfo("Estado reportado por Defender", payload, parent=self)
                elif kind == "voice_status":
                    self.voice_status.configure(text=payload)
                    if str(payload).startswith("Micrófono activo") and self.voice_active and not self.voice_stop.is_set():
                        self.set_sphere_state("listening")
                elif kind == "voice_transcript":
                    self.chat_input.delete(0, "end")
                    self.chat_input.insert(0, payload)
                    self.chat_input.focus_set()
                    self.append_chat("Transcripción para revisar", payload)
                    self.voice_status.configure(text="Revisa el texto y pulsa Enviar cuando estés conforme.")
                elif kind == "voice_empty":
                    self.voice_status.configure(text=payload)
                elif kind == "voice_error":
                    self.voice_status.configure(text="No se pudo usar el micrófono o el modelo local.")
                    self.append_chat("Sistema", "Error de voz local: " + payload)
                elif kind == "voice_stopped":
                    self.voice_active = False
                    self.set_sphere_state("idle")
                    self.voice_button.configure(text="🎙 Pulsar para hablar")
                    current_status = self.voice_status.cget("text")
                    if current_status.startswith(("Micrófono activo", "Deteniendo", "Iniciando", "Cargando", "🎙", "Optimizando")):
                        self.voice_status.configure(text=payload)
                elif kind == "tts_started":
                    if self.tts_active and not self.tts_cancel_event.is_set():
                        self.set_sphere_state("speaking")
                        self.voice_status.configure(text="Clara está respondiendo en voz · pulsa DETENER AHORA o Esc para parar.")
                elif kind == "tts_status":
                    self.voice_status.configure(text=payload)
                    self.set_sphere_state("idle")
                elif kind == "tts_error":
                    if isinstance(payload, tuple) and len(payload) == 2:
                        reason, is_manual = payload
                    else:
                        reason, is_manual = str(payload), False
                    self._report_tts_failure(reason, manual=bool(is_manual))
                elif kind == "morning_online":
                    self.append_chat("Clima y noticias", payload, speak=False)
                    combined = (self._pending_morning_speech + "\n\n" + payload).strip() if self._pending_morning_speech else payload
                    self._pending_morning_speech = ""
                    self.last_assistant_response = combined
                    self.ollama_status.configure(text="Resumen matutino actualizado")
                    if self.settings.get("auto_speak_responses", "true") == "true":
                        self._start_tts(combined)
                elif kind == "online_summary":
                    speaker_label, summary_text = payload
                    self.append_chat(speaker_label, summary_text, speak=True)
                    self.ollama_status.configure(text="Consulta completada")
                elif kind == "models":
                    models = payload
                    self.model_combo.configure(values=models)
                    if models:
                        current = self.model_var.get()
                        selected = select_preferred_ollama_model(models, current)
                        self.model_var.set(selected)
                        sdk_tag = "módulo ollama" if OLLAMA_PYTHON_MODULE_AVAILABLE else "API local"
                        self.ollama_status.configure(text=f"Ollama conectado ({sdk_tag}) · {len(models)} modelo(s) · activo: {selected}")
                        self.append_chat("Sistema", "Modelos detectados: " + ", ".join(models))
                        warmup_local_ollama_model(selected)
                    else:
                        self.model_var.set("")
                        self.ollama_status.configure(text="Ollama responde, pero no hay modelos descargados (pulsa «⬇ Descargar llama3.2…»).")
                elif kind == "models_error":
                    self.ollama_status.configure(text="No se encontró Ollama activo en este equipo.")
                elif kind == "model_pull_progress":
                    self.ollama_status.configure(text=str(payload))
                elif kind == "model_pull_done":
                    pulled_model, done_msg = payload if isinstance(payload, tuple) else ("llama3.2", str(payload))
                    self.model_var.set(pulled_model)
                    self.ollama_status.configure(text=f"Modelo «{pulled_model}» descargado y activo en Ollama")
                    self.append_chat(
                        "Asistente",
                        f"{done_msg}\nYa quedó seleccionado «{pulled_model}» (el modelo de Viernes) como tu modelo activo en CLARA-V.",
                    )
                    self.refresh_ollama_models()
                    warmup_local_ollama_model(pulled_model)
                elif kind == "model_pull_error":
                    _pulled_model, err_msg = payload if isinstance(payload, tuple) else ("llama3.2", str(payload))
                    self.ollama_status.configure(text="No se pudo completar la descarga del modelo en Ollama.")
                    self.append_chat("Asistente", str(err_msg))
                elif kind == "answer_start":
                    self.stream_text = ""
                    self.stream_started = True
                    if not self.structured_intent_mode:
                        self.chat_log.configure(state="normal")
                        self.chat_log.insert("end", "Clara · modelo local\n", "speaker")
                        self.chat_log.see("end")
                        self.chat_log.configure(state="disabled")
                elif kind == "answer_chunk":
                    self.stream_text += payload
                    if not self.structured_intent_mode:
                        self.chat_log.configure(state="normal")
                        self.chat_log.insert("end", payload)
                        self.chat_log.see("end")
                        self.chat_log.configure(state="disabled")
                elif kind == "answer_done":
                    raw_output = re.sub(r"<think>.*?</think>", "", self.stream_text, flags=re.DOTALL).strip()
                    is_structured = self.structured_intent_mode
                    self.ai_busy = False
                    self.stream_started = False
                    self.structured_intent_mode = False
                    self.ollama_status.configure(text=f"Ollama listo · {self.model_var.get()}")
                    if is_structured:
                        parsed_intent = validate_chat_intent(raw_output)
                        if parsed_intent is None:
                            answer = "No pude validar la interpretación del modelo; no realicé ninguna acción. Prueba reformular la petición o usa los controles de Clara."
                            self.append_chat("Asistente", answer)
                        else:
                            answer = self.apply_chat_intent(payload, parsed_intent)
                        self.ai_history.extend(({"role": "user", "content": payload}, {"role": "assistant", "content": answer}))
                        self.ai_history = self.ai_history[-12:]
                    else:
                        answer = raw_output or "No recibí texto del modelo."
                        sync_note = None
                        try:
                            sync_note = sync_ollama_implied_task_actions(self.db, str(payload), answer)
                            if sync_note and hasattr(self, "refresh_tasks"):
                                self.refresh_tasks()
                        except Exception:
                            sync_note = None
                        if sync_note:
                            answer = f"{answer}\n\n{sync_note}"
                        self.ai_history.extend(({"role": "user", "content": payload}, {"role": "assistant", "content": answer}))
                        self.ai_history = self.ai_history[-12:]
                        self.last_assistant_response = answer
                        self.chat_log.configure(state="normal")
                        if not raw_output:
                            self.chat_log.insert("end", answer)
                        elif sync_note:
                            self.chat_log.insert("end", f"\n{sync_note}")
                        self.chat_log.insert("end", "\n")
                        self.chat_log.see("end")
                        self.chat_log.configure(state="disabled")
                        if self.settings.get("auto_speak_responses", "true") == "true":
                            self._start_tts(answer)
                elif kind == "answer_cancelled":
                    self.ai_busy = False
                    if self.stream_started:
                        self.chat_log.configure(state="normal")
                        self.chat_log.insert("end", "\n[Generación interrumpida por el usuario.]\n")
                        self.chat_log.see("end")
                        self.chat_log.configure(state="disabled")
                    else:
                        self.append_chat("Sistema", "La generación se canceló antes de iniciar la respuesta.")
                    self.stream_started = False
                    self.structured_intent_mode = False
                    self.ollama_status.configure(text="Generación detenida por el usuario.")
                elif kind == "answer_error":
                    self.ai_busy = False
                    self.ollama_status.configure(text="Ollama no disponible · operando en modo local esencial.")
                    if self.stream_started:
                        self.chat_log.configure(state="normal")
                        self.chat_log.insert("end", f"\n[Respuesta incompleta: {payload}]\n")
                        self.chat_log.see("end")
                        self.chat_log.configure(state="disabled")
                    else:
                        user_q = str(getattr(self, "stream_user_text", "") or "")
                        if is_analytical_schedule_question(normalize_intent_text(user_q)):
                            local_analysis = build_local_analytical_schedule_answer(self.db, user_q)
                            self.append_chat(
                                "Asistente",
                                f"{local_analysis}\n\n{build_ollama_unavailable_message(str(payload))}",
                            )
                        else:
                            self.append_chat("Asistente", build_ollama_unavailable_message(str(payload)))
                    self.stream_started = False
                    self.structured_intent_mode = False
        except queue.Empty:
            pass
        self.after(200, self.process_ai_results)

    def _cancel_pending_ollama_for_new_message(self) -> None:
        """Cancel an in-flight Ollama request so a new user message is never blocked."""
        self.ollama_request_id = getattr(self, "ollama_request_id", 0) + 1
        if getattr(self, "cancel_event", None) is not None:
            self.cancel_event.set()
        lock = getattr(self, "response_lock", None)
        if lock is not None:
            with lock:
                response = getattr(self, "active_response", None)
                self.active_response = None
        else:
            response = getattr(self, "active_response", None)
            self.active_response = None
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
        queue_obj = getattr(self, "ai_results", None)
        if queue_obj is not None:
            retained = []
            try:
                while True:
                    item = queue_obj.get_nowait()
                    if not (isinstance(item, tuple) and len(item) == 2 and str(item[0]).startswith("answer_")):
                        retained.append(item)
            except queue.Empty:
                pass
            for item in retained:
                queue_obj.put(item)
        self.ai_busy = False
        self.stream_started = False
        self.structured_intent_mode = False
        try:
            self.ollama_status.configure(text="Consulta anterior cancelada para procesar tu nuevo mensaje.")
        except Exception:
            pass

    def ask_ollama(self, text: str) -> None:
        model = self.model_var.get().strip()
        self.ollama_request_id = getattr(self, "ollama_request_id", 0) + 1
        request_id = self.ollama_request_id
        self.ai_busy = True
        self.cancel_event = threading.Event()
        cancel_event = self.cancel_event
        self.stream_text = ""
        self.stream_user_text = text
        self.stream_started = False
        self.structured_intent_mode = False
        status_model = model or "buscando modelo local…"
        self.ollama_status.configure(text=f"Respondiendo con Ollama ({status_model}) · puedes enviar otro mensaje o pulsar Esc para cancelar…")
        system_prompt = (
            f"Eres CLARA-V (Clara Viernes), asistente personal local en español (fecha local: {date.today().isoformat()}). "
            "Responde siempre en español de forma clara, natural, útil y directa. "
            "Tienes acceso al contexto real y actualizado de la agenda local del usuario (clases semanales, huecos libres, tareas pendientes, bloques y rutinas): úsalo cuando el usuario te haga preguntas sobre sus materias, días libres o estrategias de estudio. "
            "No afirmes haber ejecutado acciones sobre archivos o sistema por tu cuenta."
        )
        messages = [{"role": "system", "content": system_prompt}]
        try:
            agenda_rag = build_private_agenda_rag_context(self.db)
            if agenda_rag:
                messages.append({"role": "system", "content": agenda_rag})
        except Exception:
            pass
        memories = active_memories_for(self.db)
        if memories:
            memory_text = "Preferencias y recuerdos autorizados por el usuario:\n" + "\n".join(
                f"- {item['label']}: {item['content']}" for item in memories[:8]
            )
            messages.append({"role": "system", "content": memory_text[:1800]})
        messages.extend(self.ai_history[-4:])
        messages.append({"role": "user", "content": text})

        def _put_if_current(kind: str, payload_value) -> None:
            if getattr(self, "ollama_request_id", request_id) == request_id:
                self.ai_results.put((kind, payload_value))

        def _resolve_active_model() -> str:
            if model:
                return model
            for attempt in range(3):
                try:
                    names = list_local_ollama_models()
                    if names:
                        _put_if_current("models", names)
                        return select_preferred_ollama_model(names)
                    return "llama3.2"
                except Exception:
                    if attempt == 0:
                        ensure_local_ollama_running()
                    time.sleep(1.0)
            return "llama3.2"

        def worker() -> None:
            response = None
            try:
                chosen_model = _resolve_active_model()
                if not chosen_model:
                    _put_if_current("answer_error", "No hay un modelo de Ollama activo o descargado en este equipo.")
                    return

                def _register_stream(handle) -> None:
                    nonlocal response
                    response = handle
                    with self.response_lock:
                        self.active_response = handle

                if cancel_event.is_set():
                    _put_if_current("answer_cancelled", None)
                    return

                started_ui = False
                completed = False
                in_think_block = False
                for fragment, is_done in stream_ollama_chat_direct(
                    chosen_model,
                    messages,
                    options={"temperature": 0.4, "num_ctx": 4096, "num_predict": 900},
                    cancel_event=cancel_event,
                    on_http_response=_register_stream,
                ):
                    if cancel_event.is_set():
                        break
                    if not started_ui:
                        _put_if_current("answer_start", text)
                        started_ui = True
                    if fragment:
                        if "<think>" in fragment:
                            in_think_block = True
                            fragment = fragment.split("<think>", 1)[0]
                        if in_think_block:
                            if "</think>" in fragment:
                                in_think_block = False
                                fragment = fragment.split("</think>", 1)[1]
                            else:
                                fragment = ""
                        if fragment:
                            _put_if_current("answer_chunk", fragment)
                    if is_done:
                        completed = True
                        break
                if cancel_event.is_set():
                    _put_if_current("answer_cancelled", None)
                elif completed or started_ui:
                    _put_if_current("answer_done", text)
                else:
                    _put_if_current("answer_error", "La respuesta terminó antes de recibir el cierre normal.")
            except Exception as exc:
                if cancel_event.is_set():
                    _put_if_current("answer_cancelled", None)
                else:
                    _put_if_current("answer_error", str(exc))
            finally:
                with self.response_lock:
                    if self.active_response is response:
                        self.active_response = None
                if response is not None and hasattr(response, "close"):
                    try:
                        response.close()
                    except Exception:
                        pass

        threading.Thread(target=worker, daemon=True).start()

    def parse_task_proposal(self, text: str, today: date | None = None) -> dict[str, str | None]:
        """Heuristic Spanish task parser; supports flexible natural phrasing."""
        today = today or date.today()
        candidate = text.strip()
        candidate = re.sub(
            r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:clara(?:-v|\s+v)?[,.;:\s-]*)?"
            r"(?:(?:quiero|puedes)\s+)?(?:(?:agrega(?:r)?|a[nñ]ad(?:e|ir)|registra(?:r)?|crea(?:r)?|anota(?:r)?|pon(?:er|me)?|guarda(?:r)?|apunta(?:r)?|mete(?:r)?|prepara(?:r|me)?|prepare|arma(?:r)?|planifica(?:r)?)"
            r"(?:\s+que)?(?:\s+(?:tengo(?:\s+que)?|debo|hay\s+que|me\s+dejaron|nos\s+dejaron))?(?:\s+(?:una|un|la|el|mi))?(?:\s+nueva)?(?:\s+(?:tarea|pendiente|entrega|actividad|trabajo|encargo))?(?:\s+de|\s+para|\s+que)?"
            r"|recu[eé]rdame(?:\s+que)?|me\s+dejaron(?:\s+una)?(?:\s+tarea)?|nos\s+dejaron(?:\s+una)?(?:\s+tarea)?|me\s+acaban\s+de\s+dejar|me\s+encargaron|tengo\s+que\s+entregar|debo\s+entregar|tengo\s+pendiente|tengo\s+una\s+tarea(?:\s+de)?|nueva\s+tarea(?:\s+de)?|tarea\s+de|trabajo\s+de)\b\s*",
            "",
            candidate,
            count=1,
            flags=re.IGNORECASE,
        ).strip(" :,-")

        due_date = None
        date_match = re.search(r"\b20\d{2}-\d{1,2}-\d{1,2}\b", candidate)
        if date_match:
            try:
                due_date = datetime.strptime(date_match.group(), "%Y-%m-%d").date()
            except ValueError:
                due_date = None
        if due_date is None:
            date_match = re.search(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", candidate)
            if date_match:
                day_num, month_num = int(date_match.group(1)), int(date_match.group(2))
                year_num = int(date_match.group(3)) if date_match.group(3) else today.year
                if year_num < 100:
                    year_num += 2000
                try:
                    due_date = date(year_num, month_num, day_num)
                    if not date_match.group(3) and due_date < today:
                        due_date = date(year_num + 1, month_num, day_num)
                except ValueError:
                    due_date = None
        if due_date is None:
            months = {"enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,"julio":7,"agosto":8,"septiembre":9,"setiembre":9,"octubre":10,"noviembre":11,"diciembre":12}
            date_match = re.search(r"\b(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)(?:\s+de\s+(\d{4}))?\b", candidate, re.IGNORECASE)
            if date_match:
                month_num = months[date_match.group(2).casefold()]
                year_num = int(date_match.group(3)) if date_match.group(3) else today.year
                try:
                    due_date = date(year_num, month_num, int(date_match.group(1)))
                    if not date_match.group(3) and due_date < today:
                        due_date = date(year_num + 1, month_num, int(date_match.group(1)))
                except ValueError:
                    due_date = None
        if due_date is None:
            relative_span = re.search(r"\b(?:dentro\s+de|en)\s+(\d{1,3})\s+(día|días|dias|semana|semanas)\b", candidate, re.IGNORECASE)
            if relative_span:
                quantity = int(relative_span.group(1))
                day_count = quantity * (7 if relative_span.group(2).casefold().startswith("sem") else 1)
                if 1 <= day_count <= 730:
                    due_date = today + timedelta(days=day_count)
                    date_match = relative_span
        if due_date is None:
            relative = re.search(r"\bpasado\s+mañana\b|\bmañana\b|\bhoy\b", candidate, re.IGNORECASE)
            if relative:
                word = relative.group().casefold()
                due_date = today + timedelta(days=2 if word.startswith("pasado") else 1 if word == "mañana" else 0)
                date_match = relative
        if due_date is None:
            weekday_pattern = r"\b(lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)\b"
            date_match = re.search(weekday_pattern, candidate, re.IGNORECASE)
            if date_match:
                normalized_days = {"lunes":0,"martes":1,"miércoles":2,"miercoles":2,"jueves":3,"viernes":4,"sábado":5,"sabado":5,"domingo":6}
                target_day = normalized_days[date_match.group(1).casefold()]
                delta = (target_day - today.weekday()) % 7
                before = candidate[max(0, date_match.start()-18):date_match.start()].casefold()
                if delta == 0 and any(word in before for word in ("próximo", "proximo", "siguiente")):
                    delta = 7
                elif delta == 0 and date_match.start() > 0 and candidate[max(0,date_match.start()-5):date_match.start()].casefold().strip().startswith("el"):
                    delta = 7
                due_date = today + timedelta(days=delta)
        if due_date and date_match:
            candidate = candidate[:date_match.start()] + " " + candidate[date_match.end():]

        due_time = None
        time_match = re.search(r"\b(?:a\s+las?\s+)?(1[0-2]|0?[1-9])(?::([0-5]\d))?\s*(a\.?m\.?|p\.?m\.?)\b", candidate, re.IGNORECASE)
        if time_match:
            hour = int(time_match.group(1)) % 12
            if time_match.group(3).casefold().startswith("p"):
                hour += 12
            due_time = f"{hour:02d}:{int(time_match.group(2) or 0):02d}"
        else:
            time_match = re.search(r"\b(?:a\s+las?\s+)?([01]?\d|2[0-3]):([0-5]\d)\b", candidate)
            if time_match:
                due_time = f"{int(time_match.group(1)):02d}:{time_match.group(2)}"
        if due_time and time_match:
            candidate = candidate[:time_match.start()] + " " + candidate[time_match.end():]

        known_subjects = [row[0] for row in self.db.execute("SELECT DISTINCT name FROM classes")]
        known_subjects += [row[0] for row in self.db.execute("SELECT DISTINCT subject FROM tasks WHERE subject IS NOT NULL")]
        unique_subjects = sorted({name.strip() for name in known_subjects if name and name.strip()}, key=len, reverse=True)
        subject = next((name for name in unique_subjects if name.casefold() in candidate.casefold()), None)
        if subject:
            candidate = re.sub(r"\b(?:de|para|en)\s+" + re.escape(subject) + r"\b", " ", candidate, count=1, flags=re.IGNORECASE)
            candidate = re.sub(re.escape(subject), " ", candidate, count=1, flags=re.IGNORECASE)
        candidate = re.sub(r"^\s*(?:(?:una?|el|la)\s+)?(?:tarea|actividad|trabajo|encargo|asignación|pendiente)\b\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"^\s*(?:de|para|el|la|un|una|que|entregar|hacer)\b\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"^\s*(?:de|para|el|la|un|una)\b\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\s+", " ", candidate).strip(" :,-.;")
        candidate = re.sub(r"\b(?:para|el|la|de|a las?)\s*$", "", candidate, flags=re.IGNORECASE).strip(" :,-.;")
        if candidate.casefold() in ("entregar", "hacer", "completar", "realizar"):
            candidate = ""
        title = candidate or (f"Tarea de {subject}" if subject else "Tarea nueva")
        return {"title": title[:200], "subject": subject, "due_date": due_date.isoformat() if due_date else None, "due_time": due_time}

    def parse_block_request(self, text: str) -> dict[str, str] | None:
        range_match = re.search(
            r"\b(?:de\s+(?:las\s+)?)?([01]?\d|2[0-3])(?::([0-5]\d))?\s*(?:a(?:\s+las)?|hasta(?:\s+las)?|[-–])\s*([01]?\d|2[0-3])(?::([0-5]\d))?\b",
            text,
            re.IGNORECASE,
        )
        target_day = None
        iso_match = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text)
        if iso_match:
            try:
                target_day = date.fromisoformat(iso_match.group())
            except ValueError:
                return None
        if target_day is None:
            relative = re.search(r"\bpasado mañana\b|\bmañana\b|\bhoy\b", text, re.IGNORECASE)
            if relative:
                word=relative.group().casefold(); target_day=date.today()+timedelta(days=2 if word.startswith("pasado") else 1 if word=="mañana" else 0)
        if target_day is None:
            days={"lunes":0,"martes":1,"miércoles":2,"miercoles":2,"jueves":3,"viernes":4,"sábado":5,"sabado":5,"domingo":6}
            day_match=re.search(r"\b(lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)\b",text,re.IGNORECASE)
            if day_match:
                delta=(days[day_match.group().casefold()]-date.today().weekday())%7
                target_day=date.today()+timedelta(days=delta or 7)
        if not range_match or not target_day:
            return None
        start = _normalize_hour_token(range_match.group(1), range_match.group(2))
        end = _normalize_hour_token(range_match.group(3), range_match.group(4))
        if not start or not end or end <= start:
            return None
        title=text[:range_match.start()]+" "+text[range_match.end():]
        title=re.sub(r"^\s*(?:agrega(?:r)?|a[nñ]ad(?:e|ir)|pon(?:er|me)?|reserva|reservar|bloquea|bloquear|aparta(?:r)?|agenda(?:r)?|programa(?:r)?|crea(?:r)?|prepara(?:r|me)?|prepare|arma(?:r)?|planifica(?:r)?|haz(?:me)?|hacer)\s+(?:(?:un|una|mi|el)\s+)?(?:bloque(?:\s+local|\s+de\s+estudio)?|tiempo|espacio)?\s*", "", title, flags=re.IGNORECASE)
        if iso_match:
            title=title.replace(iso_match.group()," ")
        title=re.sub(r"\b(?:pasado\s+mañana|mañana|hoy|lunes|martes|miércoles|miercoles|jueves|viernes|sábado|sabado|domingo)\b", " ", title, flags=re.IGNORECASE)
        title=re.sub(r"^\s*(?:(?:el|para|de|del|a|la|las|los|una|un)\s+)+", "", title, flags=re.IGNORECASE)
        title=re.sub(r"\s+", " ", title).strip(" ,.;:-")
        if not title:
            return None
        return {"title":title,"block_date":target_day.isoformat(),"start_time":start,"end_time":end,"notes":"Guardado desde chat."}

    def handle_app_command_from_chat(self, raw_text: str) -> bool:
        """Allow listing, authorizing, or launching authorized GUI applications directly from natural chat."""
        raw = str(raw_text or "").strip()
        low = normalize_intent_text(raw)
        if any(
            p in low
            for p in (
                "mis aplicaciones autorizadas", "que aplicaciones tienes autorizadas",
                "lista de aplicaciones autorizadas", "que aplicaciones puedes abrir",
                "ver aplicaciones autorizadas",
            )
        ):
            apps = load_allowed_applications(self.settings)
            if not apps:
                self.append_chat(
                    "Asistente",
                    "Aún no tienes aplicaciones autorizadas en tu lista (0 de 10). Puedes decirme «agregar aplicación autorizada» o pulsar «🚀 Aplicaciones autorizadas» y luego el botón superior «➕ Añadir .exe autorizado…».",
                )
            else:
                lines = [f"Tienes {len(apps)} de {MAX_ALLOWED_APPLICATIONS} aplicaciones autorizadas:"]
                for item in apps:
                    lines.append(f"• {item['name']} ({item['path']})")
                lines.append("Puedes decirme «abre la aplicación <nombre>» para iniciarla con confirmación.")
                self.append_chat("Asistente", "\n".join(lines))
            return True

        if any(
            p in low
            for p in (
                "agregar aplicacion autorizada", "agrega aplicacion autorizada", "agrega una aplicacion autorizada",
                "anadir aplicacion autorizada", "autorizar aplicacion", "autoriza una aplicacion",
                "autorizar una aplicacion", "autorizar programa", "agregar programa autorizado",
                "abrir aplicaciones autorizadas",
            )
        ):
            self.append_chat(
                "Asistente",
                "Abro el gestor de Aplicaciones autorizadas y el selector para que elijas el archivo .exe (o uses «🔍 Elegir de apps instaladas…» en la parte superior).",
            )
            self.open_application_manager(auto_prompt_add=True)
            return True

        launch_m = re.match(
            r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:abre|abrir|inicia|iniciar|ejecuta|ejecutar|lanza|lanzar)\s+(?:la\s+|mi\s+|el\s+)?(?:aplicaci[oó]n|programa|app)\s+(.+)$",
            raw,
            flags=re.IGNORECASE,
        )
        if launch_m:
            app_query = launch_m.group(1).strip(" .,;:")
            if not AssistantApp.require_permission(self, "manage_apps", pending_callable=lambda: self.handle_app_command_from_chat(raw_text)):
                return True
            apps = load_allowed_applications(self.settings)
            match = next(
                (
                    item for item in apps
                    if app_query.casefold() in item["name"].casefold()
                    or item["name"].casefold().replace(".exe", "") in app_query.casefold()
                ),
                None,
            )
            if not match:
                self.append_chat(
                    "Asistente",
                    f"No encontré «{app_query}» en tu lista de aplicaciones autorizadas. Te abro la ventana de Aplicaciones autorizadas para que la añadas con el botón «➕ Añadir .exe autorizado…» o «🔍 Elegir de apps instaladas…».",
                )
                self.open_application_manager(auto_prompt_add=False)
                return True
            if sys.platform != "win32":
                self.append_chat("Asistente", f"Encontrada en tu lista: «{match['name']}». El inicio de ejecutables .exe solo está disponible en Windows.")
                return True
            if messagebox.askyesno(
                "Confirmar inicio de aplicación autorizada",
                f"¿Iniciar ahora la aplicación autorizada?\n\n{match['name']}\n{match['path']}",
                icon="warning",
                parent=self,
            ):
                try:
                    launch_allowed_application(match)
                    self._record_private_action_event("Iniciar aplicación autorizada", "Inicio confirmado desde el chat")
                    self.append_chat("Asistente", f"¡Listo! Windows recibió la orden de iniciar «{match['name']}».")
                except Exception as exc:
                    self.append_chat("Asistente", f"No pude iniciar «{match['name']}»: {exc}")
            else:
                self.append_chat("Asistente", f"Cancelé el inicio de «{match['name']}».")
            return True
        return False

    def handle_ollama_model_command_from_chat(self, raw_text: str) -> bool:
        """Allow querying, switching, or downloading local Ollama models (such as 'llama3.2' from Viernes) via natural chat."""
        raw = str(raw_text or "").strip()
        low = normalize_intent_text(raw)

        if any(
            p in low
            for p in (
                "que modelo usas", "que modelo de ollama usas", "que modelo tienes activo",
                "cual es el modelo activo", "modelos de ollama", "que modelo usaba viernes",
            )
        ):
            cur = self.model_var.get().strip() or "ninguno detectado aún (se prefiere llama3.2 por defecto)"
            sdk_info = "módulo Python `ollama` directo" if OLLAMA_PYTHON_MODULE_AVAILABLE else "API local de Ollama (127.0.0.1:11434)"
            self.append_chat(
                "Asistente",
                f"Modelo activo actual: «{cur}» (conectado mediante {sdk_info}).\n"
                "En Viernes el modelo configurado era «llama3.2». Puedes decirme «descargar modelo llama3.2» o «usar modelo llama3.2», "
                "o pulsar el botón «⬇ Descargar llama3.2…» junto al selector de modelo.",
            )
            return True

        dl_m = re.match(
            r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:quiero\s+)?(?:descarga(?:r)?|baja(?:r)?|instala(?:r)?|obtener|pull)\s+(?:el\s+|otro\s+)?(?:modelo(?:\s+de\s+ollama)?\s+)?(llama\s*3(?:\.\d+)?(?::\S+)?|qwen\S*|mistral\S*|gemma\S*|deepseek\S*|phi\S*)$",
            raw,
            flags=re.IGNORECASE,
        )
        if dl_m:
            target_model = re.sub(r"\s+", "", dl_m.group(1).strip(" .,;:"))
            if hasattr(self, "start_ollama_model_pull"):
                self.start_ollama_model_pull(target_model, confirm_first=True)
            else:
                AssistantApp.start_ollama_model_pull(self, target_model, confirm_first=True)
            return True

        use_m = re.match(
            r"^(?:hola[,.;:\s-]*)?(?:por\s+favor\s+)?(?:usa(?:r)?|cambia(?:r)?(?:\s+a(?:l)?|\s+el\s+modelo\s+a)?|pon(?:er)?|selecciona(?:r)?|activa(?:r)?)\s+(?:el\s+)?(?:modelo(?:\s+de\s+ollama)?\s+)?(llama\s*3(?:\.\d+)?(?::\S+)?|qwen\S*|mistral\S*|gemma\S*|deepseek\S*|phi\S*)$",
            raw,
            flags=re.IGNORECASE,
        )
        if use_m:
            target_model = re.sub(r"\s+", "", use_m.group(1).strip(" .,;:"))
            if hasattr(self.model_var, "set"):
                self.model_var.set(target_model)
            warmup_local_ollama_model(target_model)
            self.append_chat(
                "Asistente",
                f"¡Listo! Cambié el modelo activo de Ollama a «{target_model}». Si aún no lo tienes descargado, dime «descargar modelo {target_model}» o pulsa «⬇ Descargar llama3.2…».",
            )
            return True
        return False

    def day_agenda_summary(self, target: date) -> str:
        today=date.today()
        day_label="hoy" if target==today else "mañana" if target==today+timedelta(days=1) else target.strftime("%A %d/%m/%Y")
        events=[]
        for meeting in classes_for_date(self.db,target):
            time_label=str(meeting["start_time"])
            if meeting["end_time"]: time_label += "–"+str(meeting["end_time"])
            text=f"Clase {time_label}: {meeting['name']}"+(f" · {meeting['location']}" if meeting["location"] else "")
            events.append((str(meeting["start_time"]),text))
        for task in self.db.execute("SELECT title,subject,due_date,due_time FROM tasks WHERE done=0 AND due_date<=? ORDER BY due_date,due_time LIMIT 30",(target.isoformat(),)):
            kind="Tarea vencida" if task["due_date"]<target.isoformat() else "Tarea"
            when=task["due_time"] or "sin hora"
            text=f"{kind} {when}: {task['title']}"+(f" · {task['subject']}" if task["subject"] else "")
            events.append((task["due_time"] or "23:59",text))
        for block in self.db.execute("SELECT title,start_time,end_time FROM plan_blocks WHERE block_date=? ORDER BY start_time",(target.isoformat(),)):
            events.append((block["start_time"],f"Bloque {block['start_time']}–{block['end_time']}: {block['title']}"))
        linked,link_status=read_linked_ics_events(self.settings.get("calendar_ics_path",""),target,target)
        for event in linked:
            label=f"Calendario ICS (solo lectura) {event['due_time'] or 'todo el día'}: {event['title']}"
            if event.get("timezone_warning"): label += " · " + str(event["timezone_warning"])
            events.append((event["due_time"] or "23:59",label))
        events.sort(key=lambda item:item[0])
        summary=(f"No hay clases, tareas con fecha ni bloques locales para {day_label}." if not events else f"Esto tienes registrado para {day_label} ({target.isoformat()}):\n"+"\n".join("• "+item[1] for item in events))
        if self.settings.get("calendar_ics_path"):
            summary += "\n\n" + link_status
        return summary


    def apply_chat_intent(self, user_text: str, intent: dict) -> str:
        """Apply only validated intents by opening existing read-only or confirm-before-save UI."""
        kind = intent["intent"]
        if kind in ("general", "informational", "blocked_unsafe"):
            answer = intent["response"]
            self.append_chat("Asistente", answer)
            return answer
        if kind == "clarify":
            answer = intent["question"]
            self.append_chat("Asistente", answer)
            return answer
        if kind == "repeat_last":
            self.speak_last_response()
            return self.last_assistant_response or "No hay respuesta previa para repetir."
        if kind == "voice_diagnostics":
            self.open_voice_diagnostics()
            answer = "Abrí el diagnóstico local de voz (TTS y Push-to-Talk). El micrófono permanece apagado."
            self.append_chat("Asistente", answer)
            return answer
        if kind == "help":
            answer = build_help_summary()
            self.append_chat("Asistente", answer)
            return answer
        if kind == "next_commitment":
            answer = build_next_commitment_summary(self.db, datetime.now())
            self.append_chat("Asistente", answer)
            return answer
        if kind == "morning_brief":
            self.show_morning_briefing()
            return "Iniciando resumen de rutina matutina, clima y titulares."
        if kind == "news_query":
            self.fetch_and_present_news(topic_override=intent.get("topic"))
            return "Consultando titulares de fuentes RSS permitidas…"
        if kind == "weather_query":
            self.fetch_and_present_weather()
            return f"Consultando clima para {self.settings['weather_location']}…"
        if kind == "classes_query":
            target_day = date.fromisoformat(intent["date"]) if intent.get("date") else None
            answer = build_classes_summary(self.db, target_day)
            self.append_chat("Asistente", answer)
            return answer
        if kind == "routines_query":
            answer = build_routines_summary(self.db)
            self.append_chat("Asistente", answer)
            return answer
        if kind == "week_agenda":
            answer = "Abro tu agenda semanal local. No la sincronizo con calendarios externos."
            self.append_chat("Asistente", answer)
            self.open_week_agenda()
            return answer
        if kind == "task_draft":
            if not AssistantApp.require_permission(self, "modify_agenda", pending_callable=lambda: AssistantApp.apply_chat_intent(self, user_text, intent)):
                return "Se solicitó autenticación para modificar la agenda."
            saved, summary = execute_add_task_from_chat(self.db, intent)
            if saved:
                if hasattr(self, "refresh_tasks"):
                    self.refresh_tasks()
                self.append_chat("Asistente", summary)
                return summary
            summary = f"Preparé un borrador de tarea: {intent['title']}."
            self.append_chat("Asistente", summary)
            self.add_task(preset=intent["title"], prefill={key: intent.get(key) for key in ("title", "subject", "due_date", "due_time", "description")})
            return summary
        if kind == "block_draft":
            if not AssistantApp.require_permission(self, "modify_agenda", pending_callable=lambda: AssistantApp.apply_chat_intent(self, user_text, intent)):
                return "Se solicitó autenticación para modificar la agenda."
            saved, summary = execute_add_block_from_chat(self.db, intent)
            if saved:
                self.append_chat("Asistente", summary)
                return summary
            summary = f"Preparé el bloque “{intent['title']}”, {intent['block_date']} de {intent['start_time']} a {intent['end_time']}."
            self.append_chat("Asistente", summary)
            self.open_plan_block_form(self, prefill={key: intent.get(key) for key in ("title", "block_date", "start_time", "end_time", "notes")})
            return summary
        if kind == "class_draft":
            if not AssistantApp.require_permission(self, "modify_agenda", pending_callable=lambda: AssistantApp.apply_chat_intent(self, user_text, intent)):
                return "Se solicitó autenticación para modificar la agenda."
            saved, summary = execute_add_class_from_chat(self.db, intent)
            self.append_chat("Asistente", summary)
            if not saved and hasattr(self, "open_classes"):
                self.open_classes()
            return summary
        if kind == "agenda_query":
            answer = self.day_agenda_summary(date.fromisoformat(intent["date"]))
            self.append_chat("Asistente", answer)
            return answer
        if kind == "afternoon_plan":
            self.start_afternoon_plan()
            return "Preparé una propuesta local de organización de la tarde para que la revises; no se guarda hasta confirmar."
        if kind in ("file_search", "file_inventory", "file_open", "file_move"):
            if not AssistantApp.require_permission(self, "file_operations", pending_callable=lambda: AssistantApp.apply_chat_intent(self, user_text, intent)):
                return "Se solicitó autenticación para explorar o abrir carpetas y archivos."
            if kind == "file_inventory":
                summary = "Elegí inventariar una carpeta. Elige tú la raíz; Clara mostrará nombres y metadatos, no leerá contenidos."
            elif kind == "file_search":
                summary = f"Buscaré “{intent['query']}” ({intent['extension']}) después de que elijas la carpeta raíz."
            elif kind == "file_open":
                summary = f"Buscaré “{intent['query']}” ({intent['extension']}). Tú eliges la raíz y el resultado; abrir requiere selección y confirmación individual."
            else:
                summary = f"Buscaré “{intent['query']}” ({intent['extension']}). Tú eliges la raíz y el archivo; mover requiere destino y confirmación individual."
            self.append_chat("Asistente", summary)
            self.open_local_file_tools(intent=intent)
            return summary
        answer = "No pude validar esa petición; no hice ningún cambio. Reformúlala o usa los controles de Clara."
        self.append_chat("Asistente", answer)
        return answer

    def send_chat(self) -> None:
        text = self.chat_input.get().strip()
        if not text:
            return
        if self.ai_busy:
            self._cancel_pending_ollama_for_new_message()
            self.append_chat(
                "Sistema",
                "Se canceló la espera anterior de Ollama para enviar tu nuevo mensaje de inmediato.",
                persist=False,
                speak=False,
            )
        self.chat_input.delete(0, "end")
        if contains_potential_api_key(text):
            self.append_chat("Tú", "[Mensaje ocultado por contener una posible clave o token]", persist=False, speak=False)
            self.append_chat(
                "Asistente",
                "Por seguridad, no envíes ni pegues claves API o tokens en el chat. Las claves de VirusTotal nunca se guardan en chats, preferencias ni respaldos; configúrala únicamente en Seguridad → Configurar clave (cifrada con Windows DPAPI).",
                persist=False,
            )
            return
        sec_cmd = parse_security_chat_command(
            self.db,
            text,
            awaiting_credentials=bool(getattr(self, "_pending_protected_action", None)),
        )
        if sec_cmd is not None:
            if sec_cmd.get("kind") in ("login", "register_user"):
                self.append_chat("Tú", f"{sec_cmd.get('username')} [contraseña oculta por seguridad]", persist=False, speak=False)
            elif sec_cmd.get("kind") == "save_secret":
                self.append_chat("Tú", f"Guardar secreto «{sec_cmd.get('label')}»: [valor encriptado oculto]", persist=False, speak=False)
            else:
                self.append_chat("Tú", text)
            AssistantApp.handle_security_chat_command(self, sec_cmd)
            return
        self.append_chat("Tú", text)
        low = normalize_intent_text(text)

        local_intent = classify_local_natural_intent(text)
        if local_intent is not None:
            self.apply_chat_intent(text, local_intent)
            return

        low_action = re.sub(
            r"^(?:hola(?:\s+clara(?:-v|\s+v)?)?|buenos\s+dias|buen\s+dia|buenas(?:\s+tardes|\s+noches)?|oye\s+clara|clara(?:-v|\s+v)?)[,.;:\s-]+",
            "",
            low,
        ).strip()
        text_action = re.sub(
            r"^(?:hola(?:\s+clara(?:-v|\s+v)?)?|buenos\s+d[ií]as|buen\s+d[ií]a|buenas(?:\s+tardes|\s+noches)?|oye\s+clara|clara(?:-v|\s+v)?)[,.;:\s-]+",
            "",
            text.strip(),
            flags=re.IGNORECASE,
        ).strip() or text

        if hasattr(self, "handle_ollama_model_command_from_chat") and self.handle_ollama_model_command_from_chat(text_action):
            return
        if not hasattr(self, "handle_ollama_model_command_from_chat") and AssistantApp.handle_ollama_model_command_from_chat(self, text_action):
            return

        if hasattr(self, "handle_app_command_from_chat") and self.handle_app_command_from_chat(text_action):
            return

        settings_res = parse_and_execute_settings_from_chat(self.settings, text_action)
        if settings_res is not None:
            self.append_chat("Asistente", settings_res[1])
            return

        cal_exc_res = parse_and_execute_calendar_exception_from_chat(self.db, text_action)
        if cal_exc_res is not None:
            def _do_cal_exc() -> None:
                res = parse_and_execute_calendar_exception_from_chat(self.db, text_action)
                if res is not None:
                    self.append_chat("Asistente", res[1])
            if AssistantApp.require_permission(self, "modify_agenda", pending_callable=_do_cal_exc):
                self.append_chat("Asistente", cal_exc_res[1])
            return

        if is_schedule_conflict_query(low_action):
            self.append_chat("Asistente", build_schedule_conflicts_report(self.db))
            return

        if is_system_status_query(low_action):
            pc_snap = collect_realtime_pc_status(self.db)
            self.append_chat("Asistente", format_realtime_pc_status_report(pc_snap))
            return

        study_cmd = parse_active_study_command(text_action, db=self.db)
        if study_cmd is not None:
            if study_cmd.get("action") == "reveal_answers":
                last_quiz = getattr(self, "active_study_session", None)
                self.append_chat("Asistente", format_active_study_answers_chat(last_quiz))
                return
            quiz_data = generate_active_study_quiz(
                self.db,
                subject=str(study_cmd.get("subject")) if study_cmd.get("subject") else None,
                count=int(study_cmd.get("count") or 5),
            )
            self.active_study_session = quiz_data
            mode_str = str(study_cmd.get("mode") or "quiz")
            self.append_chat("Asistente", format_active_study_quiz_chat(quiz_data, mode=mode_str))
            return

        if is_weekly_grid_query(low_action):
            self.append_chat("Asistente", build_weekly_grid_summary(self.db))
            if hasattr(self, "open_weekly_grid_schedule") and getattr(self, "tk", None) is not None:
                self.open_weekly_grid_schedule()
            return

        pomo_cmd = parse_pomodoro_command(text_action, db=self.db)
        if pomo_cmd is not None:
            action = str(pomo_cmd.get("action") or "status")
            if action == "start":
                msg = AssistantApp.start_pomodoro_timer(
                    self,
                    minutes=int(pomo_cmd.get("minutes") or 25),
                    label=str(pomo_cmd.get("label") or "Enfoque Pomodoro"),
                    subject=str(pomo_cmd.get("subject")) if pomo_cmd.get("subject") else None,
                )
            elif action == "pause":
                msg = AssistantApp.pause_pomodoro_timer(self)
            elif action == "resume":
                msg = AssistantApp.resume_pomodoro_timer(self)
            elif action == "stop":
                msg = AssistantApp.stop_pomodoro_timer(self)
            else:
                msg = AssistantApp.pomodoro_status_summary(self)
            self.append_chat("Asistente", msg)
            return

        notebook_res = parse_and_execute_subject_notebook_from_chat(self.db, text_action, app_instance=self)
        if notebook_res is not None:
            self.append_chat("Asistente", notebook_res[1])
            return

        math_res = parse_and_execute_math_from_chat(text_action)
        if math_res is not None:
            self.append_chat("Asistente", math_res[1])
            return

        web_q = extract_web_research_query(text_action)
        if web_q is not None:
            if hasattr(self, "run_web_research_async") and getattr(self, "tk", None) is not None:
                self.run_web_research_async(web_q)
            else:
                self.append_chat("Asistente", search_web_summary(web_q))
            return

        if _parse_relative_offset_minutes(low_action) is not None:
            def _do_rel_schedule() -> None:
                rel_res = parse_and_execute_relative_schedule_command(self.db, text_action)
                if rel_res is not None:
                    saved, msg = rel_res
                    if saved and hasattr(self, "apply_routines"):
                        self.apply_routines(date.today())
                    self.append_chat("Asistente", msg)
            if AssistantApp.require_permission(self, "modify_agenda", pending_callable=_do_rel_schedule):
                _do_rel_schedule()
            return

        if is_class_delete_command(low_action):
            def _do_del_class() -> None:
                _ok, msg = execute_delete_class_from_chat(self.db, text_action)
                self.append_chat("Asistente", msg)
            if AssistantApp.require_permission(self, "delete_agenda_item", pending_callable=_do_del_class):
                _do_del_class()
            return
        if is_class_edit_command(low_action, self.db):
            def _do_edit_class() -> None:
                _ok, msg = execute_edit_class_from_chat(self.db, text_action)
                self.append_chat("Asistente", msg)
            if AssistantApp.require_permission(self, "modify_agenda", pending_callable=_do_edit_class):
                _do_edit_class()
            return
        if is_class_add_command(low_action):
            def _do_add_class() -> None:
                class_prop = parse_class_proposal(text_action) or {}
                saved, msg = execute_add_class_from_chat(self.db, class_prop)
                self.append_chat("Asistente", msg)
                if not saved and hasattr(self, "open_classes"):
                    self.open_classes()
            if AssistantApp.require_permission(self, "modify_agenda", pending_callable=_do_add_class):
                _do_add_class()
            return
        if is_task_complete_command(low_action, self.db):
            def _do_complete_task() -> None:
                ok, msg = execute_complete_or_delete_task_from_chat(self.db, text_action, delete=False)
                if ok and hasattr(self, "refresh_tasks"):
                    self.refresh_tasks()
                self.append_chat("Asistente", msg)
            if AssistantApp.require_permission(self, "modify_agenda", pending_callable=_do_complete_task):
                _do_complete_task()
            return
        if is_task_delete_command(low_action, self.db):
            def _do_delete_task() -> None:
                ok, msg = execute_complete_or_delete_task_from_chat(self.db, text_action, delete=True)
                if ok and hasattr(self, "refresh_tasks"):
                    self.refresh_tasks()
                self.append_chat("Asistente", msg)
            if AssistantApp.require_permission(self, "delete_agenda_item", pending_callable=_do_delete_task):
                _do_delete_task()
            return
        if is_task_edit_command(low_action, self.db):
            def _do_edit_task() -> None:
                ok, msg = execute_edit_task_from_chat(self.db, text_action)
                if ok and hasattr(self, "refresh_tasks"):
                    self.refresh_tasks()
                self.append_chat("Asistente", msg)
            if AssistantApp.require_permission(self, "modify_agenda", pending_callable=_do_edit_task):
                _do_edit_task()
            return
        if is_routine_delete_command(low_action):
            def _do_del_routine() -> None:
                _ok, msg = execute_delete_routine_from_chat(self.db, text_action)
                self.append_chat("Asistente", msg)
            if AssistantApp.require_permission(self, "delete_agenda_item", pending_callable=_do_del_routine):
                _do_del_routine()
            return
        if is_routine_edit_command(low_action):
            def _do_edit_routine() -> None:
                _ok, msg = execute_edit_routine_from_chat(self.db, text_action)
                self.append_chat("Asistente", msg)
            if AssistantApp.require_permission(self, "modify_agenda", pending_callable=_do_edit_routine):
                _do_edit_routine()
            return
        if is_routine_add_command(low_action):
            def _do_add_routine() -> None:
                routine_prop = parse_routine_proposal(text_action) or {}
                saved, msg = execute_add_routine_from_chat(self.db, routine_prop)
                if saved and hasattr(self, "apply_routines"):
                    self.apply_routines(date.today())
                self.append_chat("Asistente", msg)
                if not saved and hasattr(self, "open_routines"):
                    self.open_routines()
            if AssistantApp.require_permission(self, "modify_agenda", pending_callable=_do_add_routine):
                _do_add_routine()
            return
        if is_task_add_command(low_action):
            def _do_add_task() -> None:
                proposal = AssistantApp.parse_task_proposal(self, text_action)
                if proposal["title"] == "Tarea nueva":
                    self.append_chat("Asistente", "Dime el nombre de la tarea (por ejemplo: «agrega tarea de Química entregar práctica mañana a las 16:00») o escríbela en el formulario que acabo de abrir.")
                    if hasattr(self, "add_task"):
                        self.add_task()
                    return
                saved, summary = execute_add_task_from_chat(self.db, proposal)
                if saved:
                    if hasattr(self, "refresh_tasks"):
                        self.refresh_tasks()
                    self.append_chat("Asistente", summary)
                elif hasattr(self, "add_task"):
                    self.add_task(preset=str(proposal["title"] or ""), prefill=proposal)
            if AssistantApp.require_permission(self, "modify_agenda", pending_callable=_do_add_task):
                _do_add_task()
            return
        if is_block_edit_command(low_action):
            def _do_edit_block() -> None:
                _ok, msg = execute_edit_block_from_chat(self.db, text_action)
                self.append_chat("Asistente", msg)
            if AssistantApp.require_permission(self, "modify_agenda", pending_callable=_do_edit_block):
                _do_edit_block()
            return
        if is_block_add_command(low_action):
            def _do_add_block() -> None:
                block = AssistantApp.parse_block_request(self, text_action)
                if block:
                    saved, summary = execute_add_block_from_chat(self.db, block)
                    if saved:
                        self.append_chat("Asistente", summary)
                    elif hasattr(self, "open_plan_block_form"):
                        self.open_plan_block_form(self, prefill=block)
                else:
                    if hasattr(self, "open_plan_block_form") and getattr(self, "tk", None) is not None:
                        self.open_plan_block_form(self)
                    self.append_chat(
                        "Asistente",
                        "Para agendar un bloque dime el título, la fecha y las horas de inicio y fin (o llénalo en la ventana que acabo de abrir). Ejemplo: “reserva de 15:00 a 16:00 mañana para estudiar Física”.",
                    )
            if AssistantApp.require_permission(self, "modify_agenda", pending_callable=_do_add_block):
                _do_add_block()
            return

        mem_res = parse_and_execute_memory_from_chat(self.db, text_action)
        if mem_res is not None:
            self.append_chat("Asistente", mem_res[1])
            return

        starts_with_mutation = bool(
            re.match(
                r"^(?:agrega(?:r)?|anad(?:e|ir)|crea(?:r)?|registra(?:r)?|anota(?:r)?|pon(?:er|me)?|guarda(?:r)?|elimina(?:r)?|borra(?:r)?|quita(?:r)?|cambia(?:r)?|modifica(?:r)?|actualiza(?:r)?|mueve|mover|pasa(?:r)?|pospon(?:er)?|reprograma(?:r)?|configura(?:r)?|autoriza(?:r)?)\b",
                low_action,
            )
        )
        is_analytical_q = is_analytical_schedule_question(low)
        if not starts_with_mutation and not is_analytical_q and ("agenda" in low or "horario" in low or "que tengo" in low or "que hay" in low or "mis tareas pendientes" in low):
            target=None
            if "manana" in low: target=date.today()+timedelta(days=1)
            elif "hoy" in low or "que tengo" in low or "que hay" in low or "mis tareas pendientes" in low: target=date.today()
            else:
                weekdays={"lunes":0,"martes":1,"miercoles":2,"jueves":3,"viernes":4,"sabado":5,"domingo":6}
                day_name=next((name for name in weekdays if name in low),None)
                if day_name:
                    delta=(weekdays[day_name]-date.today().weekday())%7
                    target=date.today()+timedelta(days=delta)
            if target:
                self.append_chat("Asistente",self.day_agenda_summary(target))
            else:
                self.append_chat("Asistente","¿Quieres consultar hoy, mañana o abrir la agenda semanal? No he cambiado ningún dato.")
                self.open_week_agenda()
        elif self.model_var.get().strip() or hasattr(self, "ask_ollama"):
            self.ask_ollama(text)
        elif is_analytical_q:
            local_analysis = build_local_analytical_schedule_answer(self.db, text)
            self.append_chat("Asistente", f"{local_analysis}\n\n{build_ollama_unavailable_message()}")
        else:
            self.append_chat("Asistente", build_ollama_unavailable_message())

    def set_sphere_state(self, state: str) -> None:
        """Reflect audio state; the orb expands only while Clara speaks aloud."""
        labels = {
            "idle": "En espera · esfera compacta",
            "listening": "Entrada manual activa · esfera compacta",
            "speaking": "Clara responde en voz · esfera expandida",
        }
        try:
            if self.sphere_visual.winfo_exists():
                self.sphere_visual.set_state(state)
                self.sphere_state_label.configure(text=labels.get(state, labels["idle"]))
        except (AttributeError, tk.TclError):
            pass

    def emergency_stop(self) -> None:
        active = False
        self.set_sphere_state("idle")
        if self.vt_busy:
            active = True
            self.vt_cancel_event.set()
        if self.local_scan_cancel_event is not None:
            active = True
            self.local_scan_cancel_event.set()
        if self.ai_busy:
            active = True
            self.cancel_event.set()
            with self.response_lock:
                response = self.active_response
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            self.ollama_status.configure(text="Parada solicitada; cancelando generación local…")
        if self.voice_active:
            active = True
            self.voice_stop.set()
            self.set_sphere_state("idle")
            self.voice_status.configure(text="Parada solicitada; apagando micrófono…")
        if self.tts_active:
            active = True
            self.tts_cancel_event.set()
            self.set_sphere_state("idle")
            self.voice_status.configure(text="Deteniendo lectura de voz…")
        if active:
            self.append_chat("Control de emergencia", "Detención solicitada. Se cancelan generación, micrófono, lectura de voz y búsqueda local activos, y se ignora el resultado de VirusTotal. La búsqueda coopera con la cancelación; una llamada bloqueante del sistema de archivos puede tardar. Una petición ya enviada no puede retirarse del servidor remoto y las tareas ya guardadas no se revierten.")
        else:
            self.voice_status.configure(text="Micrófono apagado · no había una operación de voz activa.")
            self.ollama_status.configure(text="No había generación de IA activa.")

    def on_close(self) -> None:
        if self.tray_icon is not None and self.settings.get("minimize_to_tray") == "true" and not self._force_quit:
            self.withdraw()
            return
        self.emergency_stop()
        self._stop_tray_icon()
        self.db.close()
        self.destroy()


def find_installed_ollama_executable(platform_name: str | None = None) -> Path | None:
    """Locate an already-installed local Ollama binary without downloading or installing anything."""
    platform_name = platform_name or sys.platform
    candidates: list[Path] = []
    which_path = shutil.which("ollama")
    if which_path:
        candidates.append(Path(which_path))
    if platform_name == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            candidates.append(Path(local_appdata) / "Programs" / "Ollama" / "ollama.exe")
        for env_key in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
            prog = os.environ.get(env_key, "")
            if prog:
                candidates.append(Path(prog) / "Ollama" / "ollama.exe")
    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file() and not candidate.is_symlink():
                return candidate.resolve(strict=True)
        except OSError:
            continue
    return None


def ensure_local_ollama_running(platform_name: str | None = None, popen=None) -> bool:
    """Start local 'ollama serve' in background if Ollama is installed on the machine."""
    exe = find_installed_ollama_executable(platform_name=platform_name)
    if exe is None:
        return False
    start_proc = popen or subprocess.Popen
    proc_env = dict(os.environ)
    proc_env.setdefault("GODEBUG", "http2client=0")
    proc_env.setdefault("OLLAMA_NOPRUNE", "1")
    kwargs: dict = {
        "shell": False,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
        "env": proc_env,
    }
    if (platform_name or sys.platform) == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        start_proc([str(exe), "serve"], **kwargs)
        return True
    except OSError:
        return False


def warmup_local_ollama_model(model_name: str) -> None:
    """Preload the selected local Ollama model into RAM/VRAM in a background thread so the first query is fast."""
    clean_model = str(model_name or "").strip()
    if not clean_model:
        return

    def _warm() -> None:
        try:
            payload = json.dumps({"model": clean_model, "messages": [], "keep_alive": "30m"}).encode("utf-8")
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read(256)
        except Exception:
            pass

    threading.Thread(target=_warm, daemon=True).start()


def run_reminder_check() -> None:
    """Scheduled-task entry point; requires an interactive signed-in Windows session."""
    db = connect_db()
    open_full_app = False
    try:
        alerts = collect_due_alerts(db, datetime.now())
        if not alerts:
            return
        settings = load_settings()
        if reminder_pause_active(settings):
            return
        if settings.get("native_notifications_enabled") == "true" and show_windows_private_toast():
            return
        alert = alerts[0]
        if settings.get("auto_speak_responses", "true") == "true":
            def _speak_alert() -> None:
                try:
                    import pyttsx3
                    engine = pyttsx3.init()
                    voices = list(engine.getProperty("voices") or [])
                    voice_id = select_spanish_voice_id(voices)
                    if voice_id:
                        engine.setProperty("voice", voice_id)
                    engine.setProperty("rate", 172)
                    engine.say(prepare_text_for_speech("Recordatorio de CLARA-V: " + str(alert.get("message", ""))))
                    engine.runAndWait()
                except Exception:
                    pass
            threading.Thread(target=_speak_alert, daemon=True).start()
        root = tk.Tk()
        root.withdraw()

        def _request_open_app() -> None:
            nonlocal open_full_app
            open_full_app = True
            root.quit()

        present_reminder(root, alert, db, close_callback=root.quit, open_app_callback=_request_open_app)
        root.mainloop()
        root.destroy()
    finally:
        db.close()
    if open_full_app:
        full_app = AssistantApp()
        full_app.protocol("WM_DELETE_WINDOW", full_app.on_close)
        full_app.mainloop()


if __name__ == "__main__":
    if "--check-reminders" in sys.argv:
        run_reminder_check()
        raise SystemExit(0)
    app = AssistantApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    if "--briefing" in sys.argv:
        app.after(700, app.show_morning_briefing)
        app.after(2200, app.prompt_new_assignment)
    app.mainloop()
