from __future__ import annotations

import csv
import ctypes
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from typing import Any


@dataclass(frozen=True)
class ActivitySnapshot:
    timestamp: str
    process_name: str
    app_key: str
    category: str
    title: str = ""
    pid: int = 0
    confidence: float = 0.0
    source: str = "foreground_window"

    def safe_payload(self) -> dict[str, Any]:
        return {
            "pid": self.pid,
            "app_key": self.app_key,
            "category": self.category,
            "title_summary": _title_summary(self.title, self.category, self.app_key),
            "confidence": self.confidence,
            "source": self.source,
        }


class WindowsActivityProbe:
    """Lee la ventana activa en Windows sin dependencias externas."""

    def snapshot(self, now: datetime | None = None) -> ActivitySnapshot | None:
        stamp = now or datetime.now()
        if os.name != "nt":
            return None
        title, pid = _foreground_window()
        if not pid:
            return None
        process_name = _process_name(pid)
        if not process_name and not title:
            return None
        app_key, category, confidence = classify_activity(process_name, title)
        return ActivitySnapshot(
            timestamp=stamp.isoformat(timespec="seconds"),
            process_name=process_name or "unknown",
            app_key=app_key,
            category=category,
            title=title,
            pid=pid,
            confidence=confidence,
        )


def classify_activity(process_name: str, title: str = "") -> tuple[str, str, float]:
    process = str(process_name or "").lower().strip()
    title_low = _normalize(title)
    base = process.removesuffix(".exe") if process else "unknown"
    if _is_youtube(process, title_low):
        return "youtube", "video", 0.9
    if process in _GAME_PROCESSES or any(token in title_low for token in _GAME_TITLE_TOKENS):
        return base if base != "unknown" else "game", "game", 0.82
    if process in _BROWSERS:
        return base, "browser", 0.78
    if process in _CODE_APPS:
        return base, "code", 0.8
    if process in _COMM_APPS:
        return base, "communication", 0.78
    if process in _MEDIA_APPS:
        return base, "media", 0.76
    if process in _SYSTEM_APPS:
        return base, "system", 0.72
    if process:
        return base, "app", 0.62
    return "unknown", "unknown", 0.0


def _foreground_window() -> tuple[str, int]:
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "", 0
        length = user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(max(1, length + 1))
        user32.GetWindowTextW(hwnd, buffer, length + 1)
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return buffer.value or "", int(pid.value or 0)
    except Exception:
        return "", 0


def _process_name(pid: int) -> str:
    if pid <= 0:
        return ""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return ""
    output = (result.stdout or "").strip()
    if not output or "INFO:" in output.upper():
        return ""
    try:
        rows = list(csv.reader(StringIO(output)))
    except csv.Error:
        return ""
    if not rows or not rows[0]:
        return ""
    return rows[0][0].strip().lower()


def _is_youtube(process: str, title_low: str) -> bool:
    return process in _BROWSERS and any(token in title_low for token in ("youtube", "youtu be", "music.youtube"))


def _title_summary(title: str, category: str, app_key: str) -> str:
    title_low = _normalize(title)
    if app_key == "youtube":
        return "youtube_window"
    if category == "game":
        return "game_window"
    if category == "browser":
        return "browser_window"
    if category == "communication":
        return "communication_window"
    if not title_low:
        return "untitled"
    return "active_window"


def _normalize(value: str) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


_BROWSERS = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "brave.exe",
    "opera.exe",
    "opera_gx.exe",
    "vivaldi.exe",
}

_GAME_PROCESSES = {
    "steam.exe",
    "epicgameslauncher.exe",
    "riotclientservices.exe",
    "valorant.exe",
    "leagueclient.exe",
    "minecraftlauncher.exe",
    "minecraft.exe",
    "robloxplayerbeta.exe",
    "fortniteclient-win64-shipping.exe",
    "gta5.exe",
    "cs2.exe",
}

_GAME_TITLE_TOKENS = {
    "minecraft",
    "roblox",
    "valorant",
    "league of legends",
    "fortnite",
    "steam",
}

_CODE_APPS = {
    "code.exe",
    "pycharm64.exe",
    "devenv.exe",
    "cursor.exe",
    "notepad++.exe",
}

_COMM_APPS = {
    "discord.exe",
    "teams.exe",
    "zoom.exe",
    "telegram.exe",
    "whatsapp.exe",
}

_MEDIA_APPS = {
    "spotify.exe",
    "vlc.exe",
    "wmplayer.exe",
}

_SYSTEM_APPS = {
    "explorer.exe",
    "taskmgr.exe",
    "cmd.exe",
    "powershell.exe",
    "windowsterminal.exe",
}
