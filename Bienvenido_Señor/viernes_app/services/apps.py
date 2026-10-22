from __future__ import annotations

import os
import shlex
import subprocess
import webbrowser
from difflib import get_close_matches


APP_PATHS: dict[str, str] = {
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "navegador": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "microsoft edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "spotify": r"C:\Users\KAISER\AppData\Roaming\Spotify\Spotify.exe",
    "whatsapp": r"C:\Users\KAISER\AppData\Local\WhatsApp\WhatsApp.exe",
    "discord": r"C:\Users\KAISER\AppData\Local\Discord\Update.exe",
    "telegram": r"C:\Users\KAISER\AppData\Roaming\Telegram Desktop\Telegram.exe",
    "steam": r"C:\Program Files (x86)\Steam\steam.exe",
    "vscode": r"C:\Users\KAISER\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "visual studio": r"C:\Users\KAISER\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "notepad": "notepad.exe",
    "bloc de notas": "notepad.exe",
    "calculadora": "calc.exe",
    "calculadora de windows": "calc.exe",
    "explorador": "explorer.exe",
    "archivos": "explorer.exe",
    "word": r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    "excel": r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    "powerpoint": r"C:\Program Files\Microsoft Office\root\Office16\POWERPNT.EXE",
    "youtube": "chrome.exe https://youtube.com",
    "netflix": "chrome.exe https://netflix.com",
    "spotify web": "chrome.exe https://open.spotify.com",
    "whatsapp web": "chrome.exe https://web.whatsapp.com",
    "gmail": "chrome.exe https://mail.google.com",
    "classroom": "chrome.exe https://classroom.google.com",
    "meet": "chrome.exe https://meet.google.com",
}


def _clean_app_name(app_name: str) -> str:
    app_key = app_name.lower().strip()
    for prefix in ("la app de ", "la aplicacion de ", "aplicacion de ", "la ", "el "):
        if app_key.startswith(prefix):
            app_key = app_key[len(prefix):].strip()
    aliases = {
        "visual studio code": "vscode",
        "vs code": "vscode",
        "codigo": "vscode",
        "explorador de archivos": "explorador",
        "archivos": "explorador",
        "bloc": "bloc de notas",
        "notas": "bloc de notas",
        "mail": "gmail",
        "correo": "gmail",
        "google chrome": "chrome",
    }
    return aliases.get(app_key, app_key)


def _creation_flags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run_command(command: str) -> None:
    if command.startswith("chrome.exe "):
        url = command.split(" ", 1)[1].strip()
        chrome = APP_PATHS.get("chrome", "chrome.exe")
        if os.path.exists(chrome):
            subprocess.Popen([chrome, url], creationflags=_creation_flags())
        else:
            webbrowser.open(url)
        return

    if command.startswith(("http://", "https://")) or "://" in command:
        webbrowser.open(command)
        return

    if os.path.exists(command) or command.lower().endswith(".exe"):
        subprocess.Popen([command], creationflags=_creation_flags())
        return

    parts = shlex.split(command, posix=False)
    subprocess.Popen(parts or [command], creationflags=_creation_flags())


def open_application(app_name: str) -> tuple[bool, str]:
    app_key = _clean_app_name(app_name)

    if app_key in APP_PATHS:
        try:
            _run_command(APP_PATHS[app_key])
            return True, f"Abriendo {app_key}..."
        except Exception as e:
            return False, f"Error al abrir {app_key}: {str(e)}"

    suggestions = [k for k in APP_PATHS.keys() if app_key in k or k in app_key]
    if not suggestions:
        suggestions = get_close_matches(app_key, APP_PATHS.keys(), n=3, cutoff=0.55)
    if suggestions:
        return False, f"No encontre '{app_name}'. Quiza quiso decir: {', '.join(suggestions[:3])}."
    return False, (
        f"No tengo registrada la aplicacion '{app_name}'. "
        "Puedo abrir: chrome, firefox, spotify, discord, telegram, whatsapp, vscode, "
        "calculadora, bloc de notas, youtube, netflix, gmail, entre otras."
    )


def list_available_apps() -> list[str]:
    return sorted(set(k for k in APP_PATHS if not any(c.isdigit() for c in k)))
