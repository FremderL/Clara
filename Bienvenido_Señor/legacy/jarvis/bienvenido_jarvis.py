"""
Asistente de voz tipo Jarvis: escucha continua, rutina matutina, comandos configurables
y niveles de seguridad por código. Incluye detección opcional de doble aplauso.

Dependencias (Windows / macOS / Linux):
    pip install -r requirements.txt

PyAudio no es obligatorio. Con Python 3.14 en Windows a menudo no hay wheel;
el micrófono para comandos de voz se captura con sounddevice (ya en requirements).
Opcional en 3.12/3.13: pip install PyAudio

speech_engine: "google" (Internet) o "vosk" (offline; pip install vosk + carpeta modelo small en el proyecto).

Variables de entorno opcionales:
    JARVIS_ACCESS_CODE  — sustituye el código sensible del JSON
    JARVIS_ADMIN_CODE   — sustituye el código de administración del JSON

Uso:
    python bienvenido_jarvis.py
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import numpy as np
import pyttsx3
import sounddevice as sd

try:
    import speech_recognition as sr
except ImportError:
    sr = None  # type: ignore


def _pyaudio_available() -> bool:
    try:
        import pyaudio  # noqa: F401

        return True
    except ImportError:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Rutas y constantes de audio (aplausos)
# ──────────────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "jarvis_config.json"
AGENDA_PATH = ROOT_DIR / "jarvis_agenda.json"
_agenda_lock = threading.Lock()

SAMPLE_RATE = 44100
BLOCK_SIZE = int(SAMPLE_RATE * 0.05)
# Micrófono para STT vía sounddevice (16 kHz es suficiente para Google STT)
VOICE_SD_RATE = 16000
DOUBLE_WINDOW = 2.0
COOLDOWN = 0.1

_clap_times: list[float] = []
_clap_triggered = False
_clap_lock = threading.Lock()
_clap_threshold = 0.2
_clap_enabled = True

# Estado de sesión
_last_morning_run: Optional[date] = None
_last_proactive: float = 0.0
_unlock_until: float = 0.0
_admin_unlock_until: float = 0.0
_pending_code_level: int = 0  # 0 ninguno, 1 acceso, 2 admin
_learning_state: Optional[dict[str, Any]] = None
# Diálogo multi-paso (agenda, recordatorio sin hora, búsqueda incompleta)
_pending_dialog: Optional[dict[str, Any]] = None

# Config activa para TTS cuando speak() no recibe cfg (p. ej. hilos en paralelo)
_current_cfg: Optional[dict[str, Any]] = None

_vosk_model_cache: Any = None
_vosk_model_path_loaded: Optional[str] = None


def _platform() -> str:
    if sys.platform == "darwin":
        return "darwin"
    if sys.platform.startswith("win"):
        return "windows"
    return "linux"


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.is_file():
        raise FileNotFoundError(f"No existe {CONFIG_PATH}")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg: dict[str, Any]) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def normalize_text(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[¿?¡!.,;:\"']+", " ", s)
    return re.sub(r"\s+", " ", s)


def contains_wake(text: str, names: list[str]) -> bool:
    t = normalize_text(text)
    for name in names:
        n = normalize_text(name)
        if not n:
            continue
        if re.search(rf"\b{re.escape(n)}\b", t):
            return True
    return False


def strip_wake(text: str, names: list[str]) -> str:
    t = normalize_text(text)
    for name in names:
        n = normalize_text(name)
        t = re.sub(rf"\b{re.escape(n)}\b", "", t)
    return normalize_text(t)


def get_access_code(cfg: dict[str, Any]) -> str:
    return os.environ.get("JARVIS_ACCESS_CODE") or cfg.get("security", {}).get("access_code", "")


def get_admin_code(cfg: dict[str, Any]) -> str:
    return os.environ.get("JARVIS_ADMIN_CODE") or cfg.get("security", {}).get("admin_code", "")


def code_ttl(cfg: dict[str, Any]) -> float:
    return float(cfg.get("security", {}).get("code_ttl_seconds", 120))


def is_unlocked(level: int, cfg: dict[str, Any]) -> bool:
    now = time.time()
    if level <= 0:
        return True
    if level == 1 and now < _unlock_until:
        return True
    if level == 2 and now < _admin_unlock_until:
        return True
    return False


def try_unlock_with_phrase(phrase: str, cfg: dict[str, Any]) -> tuple[bool, str]:
    global _unlock_until, _admin_unlock_until, _pending_code_level
    p = normalize_text(phrase)
    acc = normalize_text(get_access_code(cfg))
    adm = normalize_text(get_admin_code(cfg))
    ttl = code_ttl(cfg)
    now = time.time()

    if _pending_code_level == 1 and acc and acc in p:
        _unlock_until = now + ttl
        _pending_code_level = 0
        return True, "Código aceptado. Acceso autorizado por unos minutos."
    if _pending_code_level == 2 and adm and adm in p:
        _admin_unlock_until = now + ttl
        _pending_code_level = 0
        return True, "Código de administración aceptado."

    if acc and acc in p:
        _unlock_until = now + ttl
        _pending_code_level = 0
        return True, "Acceso autorizado."
    if adm and adm in p:
        _admin_unlock_until = now + ttl
        _pending_code_level = 0
        return True, "Modo administrador activado."

    _pending_code_level = 0
    return False, "Código incorrecto o no reconocido."


def needs_sensitive_unlock(text: str, cfg: dict[str, Any]) -> bool:
    t = normalize_text(text)
    for kw in cfg.get("sensitive_keywords", []):
        if normalize_text(kw) in t:
            return True
    return False


def _tts_section(cfg: dict[str, Any]) -> dict[str, Any]:
    t = cfg.get("tts")
    return t if isinstance(t, dict) else {}


def _pick_pyttsx3_voice_id(engine: Any, gender: str) -> Optional[str]:
    voices = engine.getProperty("voices") or []
    male_hints = (
        "male",
        "masculino",
        "hombre",
        "pablo",
        "jorge",
        "diego",
        "david",
        "juan",
        "carlos",
        "raul",
        "ricardo",
        "miguel",
        "alvaro",
        "ivan",
    )
    female_hints = (
        "female",
        "femenino",
        "mujer",
        "monica",
        "helena",
        "laura",
        "elena",
        "sofia",
        "maria",
    )

    def score_voice(vid: str, vname: str, want_male: bool) -> int:
        s = f"{vid} {vname}".lower()
        es = 1 if ("es" in s or "spanish" in s or "spa_" in s or "castellano" in s) else 0
        if want_male:
            m = 3 if any(h in s for h in male_hints) else 0
            dem = -2 if any(h in s for h in female_hints) else 0
        else:
            m = 3 if any(h in s for h in female_hints) else 0
            dem = -2 if any(h in s for h in male_hints) else 0
        return es * 2 + m + dem

    want_male = gender.lower() == "male"
    best_id: Optional[str] = None
    best_sc = -100
    for v in voices:
        vid = v.id or ""
        vname = getattr(v, "name", "") or ""
        sc = score_voice(vid, vname, want_male)
        if sc > best_sc:
            best_sc = sc
            best_id = vid
    return best_id


def speak(text: str, cfg: Optional[dict[str, Any]] = None) -> None:
    global _current_cfg
    c = cfg if cfg is not None else _current_cfg
    if c is None:
        c = {}
    tts = _tts_section(c)
    gender = str(tts.get("gender", "male")).lower()
    rate = int(tts.get("rate", 160))
    mac_voice = str(tts.get("macos_say_voice", "") or "").strip()

    print(f"[Jarvis] {text}")
    plat = _platform()
    if plat == "darwin":
        if mac_voice:
            r = subprocess.run(["say", "-v", mac_voice, text], capture_output=True)
            if r.returncode == 0:
                return
        if gender == "male":
            for v in ("Diego", "Jorge", "Juan", "Pablo"):
                r = subprocess.run(["say", "-v", v, text], capture_output=True)
                if r.returncode == 0:
                    return
        else:
            r = subprocess.run(["say", "-v", "Monica", text], capture_output=True)
            if r.returncode == 0:
                return
        subprocess.run(["say", text], capture_output=True)
        return
    try:
        engine = pyttsx3.init()
        vid = _pick_pyttsx3_voice_id(engine, "male" if gender == "male" else "female")
        if vid:
            engine.setProperty("voice", vid)
        engine.setProperty("rate", rate)
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        print(f"[Jarvis] (TTS error) {e}")


def open_url(url: str) -> None:
    webbrowser.open(url)
    time.sleep(0.8)


def search_web(query: str, cfg: dict[str, Any]) -> None:
    q = quote_plus(query)
    base = (cfg.get("search_engine_url") or "https://www.google.com/search?q=").strip()
    if "{q}" in base:
        url = base.replace("{q}", q)
    elif base.endswith("="):
        url = base + q
    elif "?" in base:
        url = base + ("&" if not base.endswith(("?", "&")) else "") + "q=" + q
    else:
        url = base + "?q=" + q
    open_url(url)


# ──────────────────────────────────────────────────────────────────────────────
#  Agenda (jarvis_agenda.json): items con categoría y recurrencia
# ──────────────────────────────────────────────────────────────────────────────
_DAYS_ES = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)
_MONTHS_ES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def _normalize_agenda_payload(data: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = list(data.get("items") or [])
    seen = {str(i.get("id")) for i in items if i.get("id")}
    for old in data.get("reminders") or []:
        oid = str(old.get("id") or uuid.uuid4().hex[:10])
        if oid in seen:
            continue
        items.append(
            {
                "id": oid,
                "title": str(old.get("text", "Recordatorio")),
                "category": "recordatorio",
                "when": old.get("when"),
                "done": bool(old.get("done")),
                "recurring": None,
            }
        )
        seen.add(oid)
    data["items"] = items
    return data


def load_agenda() -> dict[str, Any]:
    with _agenda_lock:
        if not AGENDA_PATH.is_file():
            return {"items": []}
        try:
            with open(AGENDA_PATH, encoding="utf-8") as f:
                data = json.load(f)
            return _normalize_agenda_payload(data)
        except (json.JSONDecodeError, OSError):
            return {"items": []}


def save_agenda(data: dict[str, Any]) -> None:
    with _agenda_lock:
        data = _normalize_agenda_payload(dict(data))
        out = {"items": data.get("items", [])}
        with open(AGENDA_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)


def _category_speak_label(cat: str) -> str:
    return {
        "tarea": "tarea",
        "cita": "cita",
        "reunion": "reunión",
        "evento": "evento",
        "recordatorio": "recordatorio",
    }.get(cat, cat)


def add_agenda_item(
    cfg: dict[str, Any],
    title: str,
    when: datetime,
    category: str,
    recurring: Optional[str],
) -> str:
    data = load_agenda()
    rid = uuid.uuid4().hex[:10]
    rec = recurring if recurring in ("daily", "weekly") else None
    data.setdefault("items", []).append(
        {
            "id": rid,
            "title": title.strip() or "Entrada",
            "category": category,
            "when": when.replace(microsecond=0).isoformat(timespec="seconds"),
            "done": False,
            "recurring": rec,
        }
    )
    save_agenda(data)
    return rid


def add_reminder(cfg: dict[str, Any], text: str, when: datetime) -> str:
    return add_agenda_item(cfg, text, when, "recordatorio", None)


def clear_done_reminders() -> int:
    data = load_agenda()
    items = data.get("items", [])
    before = len(items)
    data["items"] = [x for x in items if not x.get("done")]
    save_agenda(data)
    return before - len(data["items"])


def clear_all_reminders() -> None:
    save_agenda({"items": []})


def _agenda_pending_items() -> list[dict[str, Any]]:
    return [i for i in load_agenda().get("items", []) if not i.get("done")]


def _score_title_match(phrase: str, title: str) -> float:
    pn = normalize_text(phrase)
    tn = normalize_text(title)
    if not pn or not tn:
        return 0.0
    if pn == tn:
        return 200.0
    if pn in tn:
        return 120.0 + min(len(pn), 40)
    if tn in pn:
        return 100.0 + min(len(tn), 40)
    pw = set(pn.split())
    tw = set(tn.split())
    for w in ("la", "el", "los", "las", "de", "un", "una"):
        pw.discard(w)
        tw.discard(w)
    inter = pw & tw
    if not inter:
        return 0.0
    return 25.0 * len(inter) + min(len(pn), 30) * 0.1


def resolve_agenda_match(phrase: str) -> tuple[str, list[dict[str, Any]]]:
    """('unique'|'ambiguous'|'none', items) entre entradas pendientes."""
    items = _agenda_pending_items()
    if not items:
        return ("none", [])
    pn = normalize_text(phrase)
    if len(pn) < 2:
        return ("none", [])
    scored: list[tuple[float, dict[str, Any]]] = []
    for it in items:
        title = str(it.get("title", ""))
        sc = _score_title_match(phrase, title)
        if sc > 0:
            scored.append((sc, it))
    if not scored:
        return ("none", [])
    scored.sort(key=lambda x: -x[0])
    top_sc = scored[0][0]
    second = scored[1][0] if len(scored) > 1 else 0.0
    close = [x[1] for x in scored if x[0] >= top_sc * 0.92 and x[0] >= 22][:5]
    if len(close) == 1 and top_sc >= 22:
        return ("unique", close)
    if len(close) > 1 and (top_sc - second) < 15:
        return ("ambiguous", close[:4])
    if len(close) == 1:
        return ("unique", close)
    return ("ambiguous", close[:4])


def mark_agenda_item_done_by_id(cfg: dict[str, Any], item_id: str) -> bool:
    data = load_agenda()
    for it in data.get("items", []):
        if str(it.get("id")) == item_id:
            it["done"] = True
            it["recurring"] = None
            save_agenda(data)
            return True
    return False


def delete_agenda_item_by_id(cfg: dict[str, Any], item_id: str) -> bool:
    data = load_agenda()
    items = data.get("items", [])
    new_items = [x for x in items if str(x.get("id")) != item_id]
    if len(new_items) == len(items):
        return False
    data["items"] = new_items
    save_agenda(data)
    return True


def _apply_mark_or_delete_phrase(cfg: dict[str, Any], op: str, phrase: str) -> str:
    status, found = resolve_agenda_match(phrase)
    if status == "none":
        return "No encontré ninguna entrada pendiente que coincida, señor."
    if status == "ambiguous":
        titles = "; ".join(f"«{str(x.get('title', ''))}»" for x in found)
        return f"Hay varias posibles: {titles}. Diga el nombre con más detalle, señor."
    item = found[0]
    iid = str(item.get("id"))
    title = str(item.get("title", ""))
    if op == "delete":
        if delete_agenda_item_by_id(cfg, iid):
            return f"He borrado de la agenda: «{title}», señor."
        return "No pude borrar esa entrada, señor."
    if mark_agenda_item_done_by_id(cfg, iid):
        return f"Marcado como hecho: «{title}», señor."
    return "No pude marcar esa entrada, señor."


def _start_agenda_verb_dialog(op: str, cfg: dict[str, Any]) -> None:
    global _pending_dialog
    _pending_dialog = {"kind": "agenda_verb", "data": {"op": op}, "step": "await_phrase"}
    if op == "delete":
        speak("¿Qué entrada borro de la agenda, señor? Diga el título o palabras clave.", cfg)
    else:
        speak(
            "¿Qué entrada marco como hecha, señor? Diga el título o palabras clave.",
            cfg,
        )


def try_voice_mark_agenda_done(r: str, cfg: dict[str, Any]) -> Optional[str]:
    s = r.strip()
    patterns = (
        r"ya\s+complet[ée]\s+(.+)",
        r"ya\s+termine\s+(.+)",
        r"ya\s+termin[ée]\s+(.+)",
        r"marca\s+como\s+hecho\s+(.+)",
        r"marca\s+como\s+completad[oa]\s+(.+)",
        r"listo\s+(?:el|la|lo)\s+(.+)",
        r"cumpl[ií]\s+con\s+(.+)",
        r"ya\s+hice\s+(.+)",
        r"finalic[ée]\s+(.+)",
        r"acabe\s+con\s+(.+)",
        r"acab[ée]\s+con\s+(.+)",
    )
    empty_triggers = (
        r"^marca\s+como\s+hecho\s*$",
        r"^marca\s+como\s+completad[oa]\s*$",
        r"^ya\s+lo\s+complet[ée]\s*$",
        r"^ya\s+lo\s+hice\s*$",
    )
    low = normalize_text(s)
    for et in empty_triggers:
        if re.match(et, low, re.IGNORECASE):
            _start_agenda_verb_dialog("mark", cfg)
            return ""
    for pat in patterns:
        m = re.search(pat, s, re.IGNORECASE)
        if m:
            phrase = m.group(1).strip()
            if len(normalize_text(phrase)) < 2:
                _start_agenda_verb_dialog("mark", cfg)
                return ""
            return _apply_mark_or_delete_phrase(cfg, "mark", phrase)
    return None


def try_voice_delete_agenda_item(r: str, cfg: dict[str, Any]) -> Optional[str]:
    s = r.strip()
    patterns = (
        r"(?:borra|elimina|quita|saca)\s+(?:de\s+)?(?:la\s+|mi\s+)?agenda\s+(.+)",
        r"cancela\s+(?:de\s+)?(?:la\s+|mi\s+)?agenda\s+(.+)",
        r"borra\s+(?:la\s+|el\s+)?entrada\s+(.+)",
        r"elimina\s+(?:la\s+|el\s+)?entrada\s+(.+)",
    )
    empty_triggers = (
        r"^borra\s+de\s+la\s+agenda\s*$",
        r"^elimina\s+de\s+la\s+agenda\s*$",
        r"^quita\s+de\s+la\s+agenda\s*$",
    )
    low = normalize_text(s)
    for et in empty_triggers:
        if re.match(et, low, re.IGNORECASE):
            _start_agenda_verb_dialog("delete", cfg)
            return ""
    for pat in patterns:
        m = re.search(pat, s, re.IGNORECASE)
        if m:
            phrase = m.group(1).strip()
            if len(normalize_text(phrase)) < 2:
                _start_agenda_verb_dialog("delete", cfg)
                return ""
            return _apply_mark_or_delete_phrase(cfg, "delete", phrase)
    return None


def upcoming_reminders_text(cfg: dict[str, Any], limit: int = 8) -> str:
    now = datetime.now()
    rows: list[tuple[datetime, str, str]] = []
    for item in load_agenda().get("items", []):
        if item.get("done"):
            continue
        try:
            w = datetime.fromisoformat(str(item["when"]))
        except (ValueError, KeyError, TypeError):
            continue
        title = str(item.get("title", ""))
        cat = _category_speak_label(str(item.get("category", "evento")))
        rec = item.get("recurring")
        suf = " (recurrente)" if rec else ""
        rows.append((w, f"{title} [{cat}]{suf}", title))
    rows.sort(key=lambda x: x[0])
    lines = []
    for w, line, _ in rows[:limit]:
        day = "hoy" if w.date() == now.date() else w.strftime("%d/%m")
        lines.append(f"{day} a las {w.strftime('%H:%M')}: {line}")
    if not lines:
        return "No tiene nada pendiente en la agenda."
    return "Su agenda: " + "; ".join(lines)


def agenda_today_summary_text(cfg: dict[str, Any]) -> str:
    now = datetime.now()
    today = now.date()
    parts: list[str] = []
    for item in load_agenda().get("items", []):
        if item.get("done"):
            continue
        try:
            w = datetime.fromisoformat(str(item["when"]))
        except (ValueError, KeyError, TypeError):
            continue
        if w.date() != today:
            continue
        cat = _category_speak_label(str(item.get("category", "evento")))
        parts.append(f"{item.get('title', '')} ({cat}) a las {w.strftime('%H:%M')}")
    if not parts:
        return "No tiene eventos ni tareas anotados para hoy, señor."
    return "Para hoy: " + "; ".join(parts)


def maybe_fire_reminders(cfg: dict[str, Any]) -> None:
    now = datetime.now()
    with _agenda_lock:
        if not AGENDA_PATH.is_file():
            return
        try:
            with open(AGENDA_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return
        data = _normalize_agenda_payload(data)
        items = data.get("items", [])
        changed = False
        for item in items:
            if item.get("done"):
                continue
            try:
                w = datetime.fromisoformat(str(item["when"]))
            except (ValueError, KeyError, TypeError):
                continue
            if w > now:
                continue
            title = str(item.get("title", ""))
            cat = _category_speak_label(str(item.get("category", "recordatorio")))
            speak(f"Recordatorio, señor: {title}. Es una {cat}.", cfg)
            rec = item.get("recurring")
            if rec == "daily":
                nxt = w + timedelta(days=1)
                while nxt <= now:
                    nxt += timedelta(days=1)
                item["when"] = nxt.replace(microsecond=0).isoformat(timespec="seconds")
            elif rec == "weekly":
                nxt = w + timedelta(weeks=1)
                while nxt <= now:
                    nxt += timedelta(weeks=1)
                item["when"] = nxt.replace(microsecond=0).isoformat(timespec="seconds")
            else:
                item["done"] = True
            changed = True
        if changed:
            out = {"items": items}
            with open(AGENDA_PATH, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)


def fetch_weather_brief(cfg: dict[str, Any]) -> str:
    loc = (cfg.get("weather_location") or "").strip().replace(" ", "+")
    path = f"{loc}?format=j1&lang=es" if loc else "?format=j1&lang=es"
    url = f"https://wttr.in/{path}"
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (JarvisLocal/1.0)"})
    try:
        with urlopen(req, timeout=14) as resp:
            j = json.loads(resp.read().decode("utf-8", errors="replace"))
        cc = j["current_condition"][0]
        desc = cc["weatherDesc"][0]["value"]
        temp = cc["temp_C"]
        feels = cc.get("FeelsLikeC", [temp])[0]
        return f"{desc}, {temp} grados, sensación térmica {feels} grados."
    except Exception:
        return (
            "No pude obtener el clima. Compruebe la conexión o ponga su ciudad en "
            "weather_location en jarvis_config.json."
        )


def _format_date_es(dt: datetime) -> str:
    return (
        f"Hoy es {_DAYS_ES[dt.weekday()]}, {dt.day} de {_MONTHS_ES[dt.month - 1]} de {dt.year}."
    )


def run_morning_briefing(cfg: dict[str, Any]) -> None:
    speak("Buenos días, señor.", cfg)
    speak(_format_date_es(datetime.now()), cfg)
    speak(f"Clima: {fetch_weather_brief(cfg)}", cfg)
    speak(agenda_today_summary_text(cfg), cfg)


def _infer_category_from_title(title: str) -> Optional[str]:
    low = normalize_text(title)
    if "reunion" in low or "reunión" in title.lower():
        return "reunion"
    if "cita" in low:
        return "cita"
    if "tarea" in low:
        return "tarea"
    if "evento" in low:
        return "evento"
    return None


def _parse_category_from_speech(text: str) -> Optional[str]:
    low = normalize_text(text)
    if "reunion" in low or "reunión" in text.lower():
        return "reunion"
    if "cita" in low:
        return "cita"
    if "tarea" in low:
        return "tarea"
    if "evento" in low:
        return "evento"
    return None


def _parse_recurrence_from_speech(text: str) -> Optional[str]:
    low = normalize_text(text)
    if any(
        x in low
        for x in (
            "solo una vez",
            "una sola vez",
            "no recurrente",
            "no es recurrente",
            "solo eso",
            "nada mas",
            "nada más",
        )
    ):
        return "once"
    if any(
        x in low
        for x in (
            "cada dia",
            "cada día",
            "diario",
            "todos los dias",
            "todos los días",
            "diariamente",
        )
    ):
        return "daily"
    if any(x in low for x in ("cada semana", "semanal", "semanales", "una vez por semana")):
        return "weekly"
    return None


def _clear_pending_dialog() -> None:
    global _pending_dialog
    _pending_dialog = None


def _start_pending_dialog(kind: str, data: dict[str, Any], cfg: dict[str, Any]) -> None:
    global _pending_dialog
    _pending_dialog = {"kind": kind, "data": dict(data), "step": data.get("_step", "")}
    if kind == "reminder_time":
        _pending_dialog["step"] = "time"
    elif kind == "agenda_item":
        _pending_dialog["step"] = data.get("_step", "category")


def _finalize_agenda_from_dialog(cfg: dict[str, Any]) -> None:
    global _pending_dialog
    pd = _pending_dialog
    if not pd or pd["kind"] != "agenda_item":
        return
    d = pd["data"]
    title = str(d.get("title", "Entrada"))
    when = d.get("when")
    cat = str(d.get("category", "evento"))
    rec_raw = d.get("recurring")
    rec = rec_raw if rec_raw in ("daily", "weekly") else None
    if not isinstance(when, datetime):
        speak("Falta la hora; empecemos de nuevo cuando quiera, señor.", cfg)
        _clear_pending_dialog()
        return
    add_agenda_item(cfg, title, when, cat, rec)
    speak(
        f"Quedó en la agenda: «{title}», {_category_speak_label(cat)}, "
        f"el {when.strftime('%d/%m')} a las {when.strftime('%H:%M')}"
        f"{'; se repetirá según indicó.' if rec else '.'}",
        cfg,
    )
    _clear_pending_dialog()


def _continue_pending_dialog(text: str, cfg: dict[str, Any]) -> bool:
    global _pending_dialog
    pd = _pending_dialog
    if not pd:
        return False
    low = normalize_text(text)
    if any(x in low for x in ("cancelar", "olvida", "olvidalo", "déjalo", "dejalo", "no importa")):
        _clear_pending_dialog()
        speak("De acuerdo, cancelo eso, señor.", cfg)
        return True

    kind = pd["kind"]
    d = pd["data"]
    step = pd["step"]
    now = datetime.now()

    if kind == "search_query":
        q = text.strip()
        if len(q) < 2:
            speak("¿Qué tema busco exactamente, señor?", cfg)
            return True
        search_web(q, cfg)
        speak(f"Buscando: {q}", cfg)
        _clear_pending_dialog()
        return True

    if kind == "reminder_time":
        when = _parse_datetime_from_followup(text, now)
        if when is None:
            speak("No entendí la hora. Diga por ejemplo: a las 5, o en 20 minutos.", cfg)
            return True
        add_agenda_item(cfg, str(d.get("title", "Recordatorio")), when, "recordatorio", None)
        speak(
            f"Listo, señor: le recordaré «{d.get('title')}» el {when.strftime('%d/%m')} a las {when.strftime('%H:%M')}.",
            cfg,
        )
        _clear_pending_dialog()
        return True

    if kind == "agenda_verb":
        if step == "await_phrase":
            phrase = text.strip()
            if len(normalize_text(phrase)) < 2:
                speak("Diga el título o palabras clave de la entrada, señor.", cfg)
                return True
            op = str(d.get("op", "mark"))
            msg = _apply_mark_or_delete_phrase(cfg, op, phrase)
            speak(msg, cfg)
            _clear_pending_dialog()
            return True
        return True

    if kind != "agenda_item":
        _clear_pending_dialog()
        return False

    if step == "category":
        cat = _parse_category_from_speech(text)
        if not cat:
            speak(
                "¿Qué es, señor: ¿un evento, una tarea, una cita o una reunión?",
                cfg,
            )
            return True
        d["category"] = cat
        if d.get("when") is None:
            pd["step"] = "time"
            speak("¿A qué hora, señor? Puede decir a las cinco, mañana a las nueve, o en treinta minutos.", cfg)
        else:
            pd["step"] = "recurrence"
            speak("¿Es recurrente: cada día, cada semana, o solo una vez?", cfg)
        return True

    if step == "time":
        when = _parse_datetime_from_followup(text, now)
        if when is None:
            topic = str(d.get("title", ""))
            _, when2 = _parse_time_from_body(f"{topic} {text}", now, default_minutes=None)
            when = when2
        if when is None:
            speak("Repita la hora, por favor: a las 17, en 15 minutos, o mañana a las 10.", cfg)
            return True
        d["when"] = when
        pd["step"] = "recurrence"
        speak("¿Es recurrente cada día, cada semana, o solo una vez?", cfg)
        return True

    if step == "recurrence":
        rcode = _parse_recurrence_from_speech(text)
        if rcode is None:
            speak(
                "Diga: solo una vez, cada día, o cada semana, señor.",
                cfg,
            )
            return True
        d["recurring"] = None if rcode == "once" else rcode
        _finalize_agenda_from_dialog(cfg)
        return True

    return False


def _try_start_agenda_item_flow(r: str, cfg: dict[str, Any]) -> bool:
    global _pending_dialog
    m = re.search(
        r"(?:agreg|añad|pon|incorpor)\w*\s+(?:a\s+)?la\s+agenda\s+(.+)",
        r.strip(),
        re.IGNORECASE,
    )
    if not m:
        return False
    body = m.group(1).strip()
    now = datetime.now()
    topic, when = _parse_time_from_body(body, now, default_minutes=None)
    cat = _infer_category_from_title(topic)
    _pending_dialog = {
        "kind": "agenda_item",
        "data": {"title": topic, "when": when, "category": cat},
        "step": "",
    }
    if not cat:
        _pending_dialog["step"] = "category"
        speak(
            f"Entendido: «{topic}». ¿Qué es, señor: ¿un evento, una tarea, una cita o una reunión?",
            cfg,
        )
        return True
    if when is None:
        _pending_dialog["step"] = "time"
        speak(
            f"«{topic}», como {_category_speak_label(cat)}. ¿A qué hora, señor?",
            cfg,
        )
        return True
    _pending_dialog["step"] = "recurrence"
    speak(
        f"Anoto «{topic}» como {_category_speak_label(cat)} el {when.strftime('%d/%m')} a las {when.strftime('%H:%M')}. "
        "¿Es recurrente cada día, cada semana, o solo una vez?",
        cfg,
    )
    return True


def _extract_reminder_body(r: str) -> Optional[str]:
    """Texto tras el verbo de recordatorio (rest ya sin «jarvis»)."""
    patterns = (
        r"recuerda(?:me)?\s+(.+)",
        r"no olvidar\s+(.+)",
        r"recordatorio\s*:?\s*(.+)",
        r"quiero que me recuerdes\s+(.+)",
        r"anota que\s+(.+)",
        r"apunta que\s+(.+)",
        r"apunta\s+(.+)",
    )
    for pat in patterns:
        m = re.search(pat, r.strip(), re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _parse_time_from_body(
    body: str,
    now: datetime,
    default_minutes: Optional[int] = 30,
) -> tuple[str, Optional[datetime]]:
    """Separa tema y fecha/hora. Si default_minutes es None y no hay hora, devuelve (tema, None)."""
    b = body.strip()
    low = b.lower()

    m = re.search(r"\s+en\s+(\d+)\s+minutos?\s*$", low, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        topic = b[: m.start()].strip(" ,.;")
        return (topic or "Recordatorio", now + timedelta(minutes=n))

    m = re.search(r"\s+en\s+(\d+)\s+horas?\s*$", low, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        topic = b[: m.start()].strip(" ,.;")
        return (topic or "Recordatorio", now + timedelta(hours=n))

    m = re.search(
        r"\s+mañana\s+a las\s+(\d{1,2})(?::(\d{2}))?\s*$",
        low,
        re.IGNORECASE,
    )
    if m:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        topic = b[: m.start()].strip(" ,.;")
        target = (now + timedelta(days=1)).replace(hour=h, minute=mi, second=0, microsecond=0)
        return (topic or "Recordatorio", target)

    m = re.search(r"\s+a las\s+(\d{1,2})(?::(\d{2}))?\s*$", low, re.IGNORECASE)
    if m:
        h, mi = int(m.group(1)), int(m.group(2) or 0)
        if h < 24 and mi < 60:
            topic = b[: m.start()].strip(" ,.;")
            target = now.replace(hour=h, minute=mi, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            return (topic or "Recordatorio", target)

    if default_minutes is not None:
        return (b, now + timedelta(minutes=int(default_minutes)))
    return (b, None)


def _parse_datetime_from_followup(answer: str, now: datetime) -> Optional[datetime]:
    """Interpreta solo la respuesta a «¿a qué hora?» (sin tema)."""
    a = answer.strip()
    if not a:
        return None
    synthetic = f"x {a}"
    _, when = _parse_time_from_body(synthetic, now, default_minutes=None)
    if when is None:
        m = re.match(r"^en\s+(\d+)\s+minutos?\s*$", normalize_text(a), re.IGNORECASE)
        if m:
            return now + timedelta(minutes=int(m.group(1)))
        m = re.match(r"^en\s+(\d+)\s+horas?\s*$", normalize_text(a), re.IGNORECASE)
        if m:
            return now + timedelta(hours=int(m.group(1)))
    return when


def try_parse_and_add_reminder(r: str, cfg: dict[str, Any]) -> Optional[str]:
    """Recordatorio por voz; si falta la hora, inicia diálogo."""
    body = _extract_reminder_body(r)
    if not body:
        return None
    now = datetime.now()
    topic, when = _parse_time_from_body(body, now, default_minutes=None)
    if when is None:
        _start_pending_dialog(
            "reminder_time",
            {"title": topic or "Recordatorio"},
            cfg,
        )
        speak(
            "¿Cuándo debo recordarle, señor? Diga la hora, mañana a las…, o en cuántos minutos.",
            cfg,
        )
        return ""
    add_agenda_item(cfg, topic or "Recordatorio", when, "recordatorio", None)
    return (
        f"Anotado, señor: «{topic}» el {when.strftime('%d/%m')} a las {when.strftime('%H:%M')}."
    )


def _is_agenda_query(r: str) -> bool:
    x = normalize_text(r).strip()
    if not x:
        return False
    if x in ("agenda", "mi agenda", "la agenda"):
        return True
    needles = (
        "agenda del dia",
        "agenda del día",
        "que tengo pendiente",
        "qué tengo pendiente",
        "que tengo para hoy",
        "qué tengo para hoy",
        "proximos recordatorios",
        "próximos recordatorios",
        "lista de recordatorios",
        "mis recordatorios",
        "mis pendientes",
    )
    return any(n in x for n in needles) and len(x) < 100


_DEFAULT_HELP_CHUNKS = [
    "Agenda. Mi agenda para listar. Agregar a la agenda; ya completé o marca como hecho más palabras clave; borra de la agenda más texto. Si hay varias coincidencias, pida más detalle. Recuérdame sin hora pregunta cuándo. Cancelar abandona el diálogo.",
    "Rutina al despertar: saludo, fecha, clima y eventos de hoy. Opcional: más pasos en JSON con morning_run_sequence_after_briefing.",
    "Búsqueda. Búscame más tema; si falta el tema, lo pregunto.",
    "Ejecuta rutina matutina, aprende comando, códigos de seguridad y comandos del JSON como siempre.",
    "Diga dime algo o ayuda extendida.",
]


def try_search_intent(r: str, cfg: dict[str, Any]) -> bool:
    global _pending_dialog

    patterns = (
        r"^busca(?:me)?(?:\s+en (?:internet|la web|google))?\s+(.+)$",
        r"^buscar(?:me)?(?:\s+en (?:internet|la web|google))?\s+(.+)$",
        r"^búscame\s+(.+)$",
        r"^buscame\s+(.+)$",
        r"^googlea?\s+(.+)$",
        r"^haz(?:me)?\s+una\s+búsqueda\s+de\s+(.+)$",
        r"^haz(?:me)?\s+una\s+busqueda\s+de\s+(.+)$",
        r"^investiga\s+sobre\s+(.+)$",
        r"^busqueda\s+(.+)$",
        r"^búsqueda\s+(.+)$",
    )
    s = r.strip()
    for pat in patterns:
        m = re.match(pat, s, re.IGNORECASE)
        if m:
            q = m.group(1).strip()
            if len(q) < 2:
                _pending_dialog = {"kind": "search_query", "data": {}, "step": "query"}
                speak("¿Qué desea buscar en internet, señor?", cfg)
                return True
            search_web(q, cfg)
            speak(f"Buscando en la web: {q}", cfg)
            return True
    return False


def open_application(name: str, cfg: dict[str, Any]) -> None:
    plat = _platform()
    path_key = "new_project"
    extra = os.path.expanduser(cfg.get("paths", {}).get(path_key, "~/Desktop/nuevo_proyecto"))
    name_clean = name.strip()

    if name_clean.lower() == "cursor":
        if plat == "darwin":
            cursor = _find_cursor_mac()
            if cursor:
                subprocess.Popen([cursor, extra], start_new_session=True)
            else:
                subprocess.Popen(["open", "-a", "Cursor", extra], start_new_session=True)
        elif plat == "windows":
            cursor_exe = shutil.which("cursor")
            if cursor_exe:
                subprocess.Popen([cursor_exe, extra], shell=False)
            else:
                subprocess.Popen(
                    f'start "" cursor "{extra}"',
                    shell=True,
                )
        else:
            subprocess.Popen(["cursor", extra], start_new_session=True)
        return

    if plat == "darwin":
        subprocess.Popen(["open", "-a", name_clean], start_new_session=True)
    elif plat == "windows":
        subprocess.Popen(f'start "" "{name_clean}"', shell=True)
    else:
        subprocess.Popen([name_clean], start_new_session=True)


def _find_cursor_mac() -> Optional[str]:
    for p in (
        "/usr/local/bin/cursor",
        "/opt/homebrew/bin/cursor",
        os.path.expanduser("~/.cursor/bin/cursor"),
    ):
        if os.path.isfile(p):
            return p
    r = subprocess.run(["which", "cursor"], capture_output=True, text=True)
    if r.returncode == 0:
        return r.stdout.strip()
    return None


def run_morning_sequence(cfg: dict[str, Any]) -> None:
    speak("Iniciando su rutina matutina.", cfg)
    if cfg.get("morning_use_briefing", True):
        run_morning_briefing(cfg)
    if cfg.get("morning_run_sequence_after_briefing", False):
        for step in cfg.get("morning_sequence", []):
            typ = (step.get("type") or "").lower()
            val = step.get("value", "")
            if typ == "speak":
                speak(str(val), cfg)
            elif typ == "open_url":
                open_url(str(val))
            elif typ == "open_app":
                open_application(str(val), cfg)
            time.sleep(0.5)
    speak("Rutina matutina completada, señor.", cfg)


def maybe_run_morning(cfg: dict[str, Any]) -> None:
    global _last_morning_run
    mt = cfg.get("morning_time", "07:00")
    try:
        h, m = [int(x) for x in str(mt).split(":")[:2]]
    except ValueError:
        return
    now = datetime.now()
    if now.hour != h or now.minute != m:
        return
    today = now.date()
    if _last_morning_run == today:
        return
    _last_morning_run = today
    threading.Thread(target=lambda: run_morning_sequence(cfg), daemon=True).start()


def maybe_proactive(cfg: dict[str, Any]) -> None:
    global _last_proactive
    interval = float(cfg.get("proactive_interval_minutes", 0) or 0)
    if interval <= 0:
        return
    now = time.time()
    if now - _last_proactive < interval * 60:
        return
    prompts = list(cfg.get("proactive_prompts") or [])
    if cfg.get("proactive_mix_casual", True):
        prompts.extend(cfg.get("casual_phrases") or [])
    if not prompts:
        return
    _last_proactive = now
    msg = random.choice(prompts)
    speak(msg, cfg)


def execute_action(action: str, value: str, cfg: dict[str, Any]) -> None:
    a = action.lower()
    if a == "open_url":
        open_url(value)
    elif a == "open_app":
        open_application(value, cfg)
    elif a == "speak":
        speak(value, cfg)
    elif a == "search_web":
        search_web(value, cfg)
        speak(f"Buscando: {value}", cfg)
    else:
        speak(f"Acción no implementada: {action}", cfg)


def add_morning_step(cfg: dict[str, Any], typ: str, value: str) -> str:
    seq = cfg.setdefault("morning_sequence", [])
    seq.append({"type": typ, "value": value})
    save_config(cfg)
    return f"Paso añadido a la rutina matutina: {typ} → {value}"


def register_voice_command(cfg: dict[str, Any], phrase: str, action: str, value: str, level: int) -> str:
    cmds = cfg.setdefault("voice_commands", {})
    cmds[normalize_text(phrase)] = {"action": action, "value": value, "level": level}
    save_config(cfg)
    return f"Comando registrado: cuando diga «{phrase}», ejecutaré {action}."


def match_voice_command(rest: str, cfg: dict[str, Any]) -> Optional[tuple[dict[str, Any], str]]:
    r = normalize_text(rest)
    cmds = cfg.get("voice_commands") or {}
    best = None
    best_len = 0
    for phrase, spec in cmds.items():
        pn = normalize_text(str(phrase))
        if pn in r and len(pn) > best_len:
            best = spec
            best_len = len(pn)
    if best:
        return best, r
    return None


def _parse_add_to_morning_routine(r: str) -> Optional[tuple[str, str]]:
    """
    Interpreta frases del tipo «agrega a la rutina matutina …».
    Devuelve (tipo, valor) con tipo en speak | open_url | open_app.
    """
    rut = r"(?:a\s+la\s+rutina\s+matutina|a\s+la\s+rutina|a\s+mi\s+rutina)"
    verbo = r"(?:agreg|añad|adicion|anad|pon|incorpor|sum)\w*"

    m = re.search(
        rf"{verbo}\s+{rut}\s+"
        r"(?P<kind>hablar|decir|texto|frase|que\s+digas|url|enlace|link|aplicacion|aplicación|app)\s+"
        r"(?P<val>.+)",
        r,
        re.IGNORECASE,
    )
    if m:
        kind = re.sub(r"\s+", " ", m.group("kind").lower().strip())
        val = m.group("val").strip()
        if kind in ("url", "enlace", "link"):
            return ("open_url", val)
        if kind in ("aplicacion", "aplicación", "app"):
            return ("open_app", val)
        return ("speak", val)

    m_url = re.search(
        rf"{verbo}\s+{rut}\s+(?P<u>https?://\S+)",
        r,
        re.IGNORECASE,
    )
    if m_url:
        return ("open_url", m_url.group("u").strip())

    m_rest = re.search(rf"{verbo}\s+{rut}\s+(?P<rest>.+)", r, re.IGNORECASE)
    if not m_rest:
        return None
    rest = m_rest.group("rest").strip()
    low = rest.lower()
    if low.startswith("http://") or low.startswith("https://"):
        return ("open_url", rest)
    if low.startswith("abrir ") or low.startswith("abre "):
        app = re.sub(r"^(abrir|abre)\s+", "", rest, count=1, flags=re.IGNORECASE).strip()
        if app:
            return ("open_app", app)
    return ("speak", rest)


def _resolve_vosk_model_path(raw: str) -> str:
    """
    Acepta ruta absoluta o carpeta relativa al proyecto (p. ej. vosk-model-small-es-0.42).
    Si la ruta es relativa, se busca primero dentro de la misma carpeta que bienvenido_jarvis.py.
    """
    if not str(raw).strip():
        return ""
    p = os.path.expanduser(str(raw).strip())
    candidates: list[Path] = []
    if os.path.isabs(p):
        candidates.append(Path(p))
    else:
        candidates.append((ROOT_DIR / p).resolve())
        try:
            candidates.append(Path(p).resolve())
        except OSError:
            pass
    for c in candidates:
        try:
            if c.is_dir():
                return str(c)
        except OSError:
            continue
    return ""


def _load_vosk_model(model_path: str) -> Any:
    global _vosk_model_cache, _vosk_model_path_loaded
    path = _resolve_vosk_model_path(model_path)
    if not path:
        return None
    if _vosk_model_path_loaded == path and _vosk_model_cache is not None:
        return _vosk_model_cache
    try:
        from vosk import Model  # type: ignore
    except ImportError:
        return None
    _vosk_model_cache = Model(path)
    _vosk_model_path_loaded = path
    print(f"[Jarvis] Modelo Vosk cargado: {path}")
    return _vosk_model_cache


def recognize_from_audio(
    audio: "sr.AudioData",
    cfg: dict[str, Any],
    rec: "sr.Recognizer",
) -> str:
    engine = (cfg.get("speech_engine") or "google").strip().lower()
    if engine == "vosk":
        env_path = os.environ.get("JARVIS_VOSK_MODEL", "")
        mpath = str(cfg.get("vosk_model_path") or env_path or "")
        model = _load_vosk_model(mpath)
        if model is None:
            resolved = _resolve_vosk_model_path(mpath)
            hint_path = resolved or mpath or "(sin ruta en jarvis_config.json)"
            raise RuntimeError(
                f"Vosk no disponible. Ejecute: pip install vosk. "
                f"Descomprima el ZIP del modelo small español dentro de la carpeta del proyecto "
                f"para que exista la carpeta «vosk-model-small-es-0.42» con am, conf y graph dentro. "
                f"Config: vosk_model_path={mpath!r}; carpeta encontrada={bool(resolved)} ({hint_path!r}). "
                f"Modelos: https://alphacephei.com/vosk/models — o use speech_engine «google»."
            )
        try:
            from vosk import KaldiRecognizer  # type: ignore
        except ImportError as e:
            raise RuntimeError("Paquete vosk no instalado.") from e

        rate = audio.sample_rate
        krec = KaldiRecognizer(model, rate)
        data = audio.get_raw_data()
        if not data:
            raise sr.UnknownValueError("audio vacío")
        if len(data) > 8000:
            step = max(rate // 4, 4000)
            for i in range(0, len(data), step):
                krec.AcceptWaveform(data[i : i + step])
        else:
            krec.AcceptWaveform(data)
        payload = json.loads(krec.FinalResult())
        text = (payload.get("text") or "").strip()
        if not text:
            raise sr.UnknownValueError("Vosk no entendió audio")
        return text

    lang = cfg.get("language_recognition", "es-ES")
    return rec.recognize_google(audio, language=lang)


def handle_voice_intent(full_text: str, cfg: dict[str, Any]) -> None:
    global _pending_code_level, _learning_state, _pending_dialog

    names = [str(x) for x in cfg.get("wake_names", ["jarvis"])]
    had_wake = contains_wake(full_text, names)
    rest = strip_wake(full_text, names) if had_wake else full_text.strip()

    if _pending_dialog:
        chunk = rest if had_wake else full_text.strip()
        if _continue_pending_dialog(chunk, cfg):
            return
        if had_wake:
            _clear_pending_dialog()
        else:
            return

    if not had_wake:
        return

    t = normalize_text(full_text)
    r = rest

    if _pending_code_level:
        ok, msg = try_unlock_with_phrase(full_text, cfg)
        speak(msg, cfg)
        return

    if _learning_state:
        st = _learning_state
        step = st.get("step")
        if step == "phrase":
            st["phrase"] = full_text.strip()
            st["step"] = "action_type"
            speak("Indique el tipo de acción: abrir enlace, abrir aplicación, o hablar texto.", cfg)
            return
        if step == "action_type":
            low = normalize_text(full_text)
            if "enlace" in low or "url" in low or "página" in low:
                st["atype"] = "open_url"
            elif "aplic" in low or "programa" in low:
                st["atype"] = "open_app"
            else:
                st["atype"] = "speak"
            st["step"] = "action_value"
            speak("Diga el valor: la URL, el nombre de la aplicación o el texto a decir.", cfg)
            return
        if step == "action_value":
            st["value"] = full_text.strip()
            phrase = st.get("phrase", "")
            atype = st.get("atype", "speak")
            register_voice_command(cfg, normalize_text(phrase), atype, st["value"], 1)
            _learning_state = None
            speak("Comando aprendido y guardado.", cfg)
            return

    # Saludos y estado
    if any(x in r for x in ("estás despierto", "estas despierto", "despierto")):
        speak("Sí, Señor. Estoy en escucha y listo para ayudarle.", cfg)
        return
    if any(x in r for x in ("qué haces", "que haces", "que estas haciendo", "qué estás haciendo")):
        speak(
            "Estoy monitorizando el micrófono, la rutina matutina y sus comandos. "
            "Puede pedir ayuda diciendo: Jarvis, ayúdame con, seguido de la tarea.",
            cfg,
        )
        return
    if "ayúdame" in r or "ayudame" in t:
        topic = r
        for key in ("ayúdame con", "ayudame con", "ayúdame", "ayudame"):
            if key in topic:
                topic = topic.split(key, 1)[-1].strip()
                break
        if topic:
            speak(
                f"Entendido. Sobre «{topic}»: puedo buscar en internet, leer su agenda, "
                "crear recordatorios, abrir enlaces o apps, y gestionar la rutina matutina. "
                "Diga qué puede hacer o ayuda extendida para más detalle.",
                cfg,
            )
        else:
            speak("Diga: Jarvis, ayúdame con, y describa la tarea.", cfg)
        return

    if any(x in r for x in ("qué puedes hacer", "que puedes hacer", "comandos", "ayuda")):
        speak(
            "Resumen: agenda con tipos y recurrencia, recordatorios, búsqueda, rutina matutina con clima y fecha, "
            "comandos de voz y aplausos. Diga ayuda extendida para el detalle. "
            "Puede decir: agrega a la agenda…, ya completé…, borra de la agenda…, recuérdame…, búscame…, mi agenda, o dime algo.",
            cfg,
        )
        return

    if any(
        x in r
        for x in (
            "ayuda extendida",
            "lista completa de comandos",
            "todos los comandos",
            "comandos detallados",
            "lista detallada",
        )
    ):
        chunks = cfg.get("help_speech_chunks") or _DEFAULT_HELP_CHUNKS
        for part in chunks:
            if str(part).strip():
                speak(str(part).strip(), cfg)
                time.sleep(0.3)
        return

    if any(
        x in r
        for x in (
            "dime algo",
            "cuéntame algo",
            "cuentame algo",
            "hazme una pregunta",
            "dime una curiosidad",
            "sorpréndeme",
            "sorprendeme",
        )
    ):
        casual = cfg.get("casual_phrases") or []
        if casual:
            speak(random.choice(casual), cfg)
        else:
            speak(
                "Puede pedirme su agenda, una búsqueda, o decir recuérdame más un encargo y cuándo.",
                cfg,
            )
        return

    if try_search_intent(r, cfg):
        return

    if _is_agenda_query(r):
        speak(upcoming_reminders_text(cfg), cfg)
        return

    msg_mark = try_voice_mark_agenda_done(r, cfg)
    if msg_mark is not None:
        if msg_mark:
            speak(msg_mark, cfg)
        return

    msg_del = try_voice_delete_agenda_item(r, cfg)
    if msg_del is not None:
        if msg_del:
            speak(msg_del, cfg)
        return

    if any(
        x in normalize_text(r)
        for x in (
            "limpia recordatorios viejos",
            "borra recordatorios cumplidos",
            "archiva recordatorios hechos",
            "quita recordatorios hechos",
        )
    ):
        n = clear_done_reminders()
        speak(f"He eliminado del archivo {n} recordatorios ya cumplidos, señor.", cfg)
        return

    if any(
        x in r
        for x in (
            "limpia la agenda",
            "vacia la agenda",
            "vacía la agenda",
            "borra todos los recordatorios",
            "borrar todos los recordatorios",
            "elimina todos los recordatorios",
        )
    ):
        if not is_unlocked(2, cfg):
            _pending_code_level = 2
            speak("Para vaciar la agenda, indique el código de administración.", cfg)
            return
        clear_all_reminders()
        speak("He vaciado todos los recordatorios, señor.", cfg)
        return

    if _try_start_agenda_item_flow(r, cfg):
        return

    msg_rem = try_parse_and_add_reminder(r, cfg)
    if msg_rem is not None:
        if msg_rem:
            speak(msg_rem, cfg)
        return

    if "ejecuta rutina" in r or "rutina matutina ahora" in r:
        required = 1
        if not is_unlocked(required, cfg):
            _pending_code_level = required
            speak("Para ejecutar la rutina bajo demanda, indique el código de acceso.", cfg)
            return
        threading.Thread(target=lambda: run_morning_sequence(cfg), daemon=True).start()
        return

    # Añadir paso a rutina: "añade rutina hablar buenos días" / "añade rutina url https://..."
    m = re.match(
        r"añad(e|ir)\s+rutina\s+(hablar|url|enlace|aplicacion|aplicación)\s+(.+)",
        r,
        re.IGNORECASE,
    )
    if m:
        if not is_unlocked(2, cfg):
            _pending_code_level = 2
            speak("Modifique la rutina matutina con el código de administración.", cfg)
            return
        kind = m.group(2).lower()
        val = m.group(3).strip()
        if kind in ("url", "enlace"):
            msg = add_morning_step(cfg, "open_url", val)
        elif kind in ("aplicacion", "aplicación"):
            msg = add_morning_step(cfg, "open_app", val)
        else:
            msg = add_morning_step(cfg, "speak", val)
        speak(msg, cfg)
        return

    add_routine = _parse_add_to_morning_routine(r)
    if add_routine:
        if not is_unlocked(2, cfg):
            _pending_code_level = 2
            speak("Para agregar pasos a la rutina matutina, indique el código de administración.", cfg)
            return
        typ, val = add_routine
        speak(add_morning_step(cfg, typ, val), cfg)
        return

    if any(x in r for x in ("aprende comando", "registra comando", "nuevo comando", "aprende")):
        if not is_unlocked(2, cfg):
            _pending_code_level = 2
            speak("Para enseñar nuevos comandos, indique primero el código de administración.", cfg)
            return
        _learning_state = {"step": "phrase"}
        speak("De acuerdo. Diga la frase exacta que desea usar como comando.", cfg)
        return

    matched = match_voice_command(r, cfg)
    if matched:
        spec, _ = matched
        level = int(spec.get("level", 1))
        if not is_unlocked(level, cfg):
            _pending_code_level = min(level, 2) or 1
            speak("Ese comando requiere código de acceso. Dígalo ahora.", cfg)
            return
        execute_action(spec.get("action", ""), str(spec.get("value", "")), cfg)
        return

    if r.strip():
        speak(
            "Le escucho, Señor. Si necesita una acción concreta, pídala con claridad o diga qué puedes hacer.",
            cfg,
        )
    else:
        speak("¿En qué puedo ayudarle, Señor?", cfg)


def clap_callback(
    cfg_holder: dict[str, Any],
    indata,
    _frames,
    _time_info,
    _status,
) -> None:
    global _clap_triggered, _clap_times
    if not _clap_enabled or _clap_triggered:
        return
    rms = float(np.sqrt(np.mean(indata**2)))
    now = time.time()
    if rms <= _clap_threshold:
        return
    with _clap_lock:
        if _clap_times and (now - _clap_times[-1]) < COOLDOWN:
            return
        _clap_times.append(now)
        _clap_times = [x for x in _clap_times if now - x <= DOUBLE_WINDOW]
        if len(_clap_times) >= 2:
            _clap_triggered = True
            _clap_times = []
            cfg = cfg_holder.get("cfg") or load_config()

            def run():
                global _clap_triggered
                speak(
                    cfg.get("paths", {}).get("welcome_message") or "Bienvenido a casa, Señor.",
                    cfg,
                )
                yt = cfg.get("paths", {}).get("youtube_url", "https://www.youtube.com/")
                open_url(yt)
                if _platform() == "darwin":
                    subprocess.Popen(["open", "-a", "Claude"], start_new_session=True)
                    time.sleep(1.5)
                    open_application("Cursor", cfg)
                    time.sleep(1.0)
                    _tile_mac_windows(cfg)
                else:
                    open_application("Cursor", cfg)
                time.sleep(6)
                _clap_triggered = False
                print("[Jarvis] Listo para detectar de nuevo doble aplauso.")

            threading.Thread(target=run, daemon=True).start()


def _tile_mac_windows(cfg: dict[str, Any]) -> None:
    try:
        out = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "Finder" to get bounds of window of desktop',
            ],
            capture_output=True,
            text=True,
        ).stdout.strip()
        parts = [int(x.strip()) for x in out.split(",")]
        sw, sh = parts[2], parts[3]
        mitad = sw // 2
        script = f"""
        tell application "System Events"
            try
                tell process "Claude"
                    set frontmost to true
                    set position of window 1 to {{0, 0}}
                    set size of window 1 to {{{mitad}, {sh}}}
                end tell
            end try
            try
                tell process "Cursor"
                    set frontmost to true
                    set position of window 1 to {{{mitad}, 0}}
                    set size of window 1 to {{{mitad}, {sh}}}
                end tell
            end try
        end tell
        """
        subprocess.run(["osascript", "-e", script], capture_output=True)
    except Exception:
        pass


def _calibrate_sounddevice_mic(recognizer: "sr.Recognizer", duration: float = 1.0) -> None:
    """Ruido ambiente para umbrales VAD (solo sounddevice)."""
    n = int(duration * VOICE_SD_RATE)
    buf = sd.rec(n, samplerate=VOICE_SD_RATE, channels=1, dtype="float32")
    sd.wait()
    rms = float(np.sqrt(np.mean(np.square(buf))))
    recognizer.__dict__["_jarvis_ambient_rms"] = max(rms, 1e-6)


def _listen_sounddevice(
    recognizer: "sr.Recognizer",
    timeout: float,
    phrase_time_limit: float,
) -> "sr.AudioData":
    """Graba una frase sin PyAudio (útil en Python 3.14 / Windows sin wheel)."""
    rate = VOICE_SD_RATE
    block_dur = 0.05
    block = max(1, int(rate * block_dur))
    amb = float(getattr(recognizer, "_jarvis_ambient_rms", 0.02))
    thresh_on = max(amb * 4.0, 0.012)
    thresh_off = max(amb * 1.8, 0.006)
    pause_ms = int(recognizer.pause_threshold * 1000)
    block_ms = int(block_dur * 1000)

    start_deadline = time.time() + timeout
    while time.time() < start_deadline:
        chunk = sd.rec(block, samplerate=rate, channels=1, dtype="float32")
        sd.wait()
        rms = float(np.sqrt(np.mean(np.square(chunk))))
        if rms > thresh_on:
            parts: list[np.ndarray] = [chunk]
            total_ms = block_ms
            silence_ms = 0
            speech_deadline = time.time() + phrase_time_limit
            while time.time() < speech_deadline:
                chunk = sd.rec(block, samplerate=rate, channels=1, dtype="float32")
                sd.wait()
                rms = float(np.sqrt(np.mean(np.square(chunk))))
                parts.append(chunk)
                total_ms += block_ms
                if rms > thresh_off:
                    silence_ms = 0
                else:
                    silence_ms += block_ms
                if silence_ms >= pause_ms and total_ms > block_ms * 2:
                    break
            audio = np.concatenate(parts, axis=0).reshape(-1)
            audio_i16 = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
            return sr.AudioData(audio_i16.tobytes(), rate, 2)

    raise sr.WaitTimeoutError("listening timed out while waiting for phrase to start")


def recognition_loop(cfg_holder: dict[str, Any], stop_event: threading.Event) -> None:
    global _current_cfg

    if sr is None:
        print("[Jarvis] speech_recognition no instalado; solo aplausos y rutina por hora.")
        while not stop_event.is_set():
            time.sleep(1)
        return

    rec = sr.Recognizer()
    rec.energy_threshold = 300
    rec.dynamic_energy_threshold = True
    rec.pause_threshold = 0.8

    use_sounddevice_mic = not _pyaudio_available()
    if not use_sounddevice_mic:
        try:
            with sr.Microphone() as source:
                rec.adjust_for_ambient_noise(source, duration=1.2)
        except Exception as e:
            print(
                f"[Jarvis] PyAudio/micrófono no usable ({e!s}). "
                "Usando captura vía sounddevice (sin PyAudio)."
            )
            use_sounddevice_mic = True

    if use_sounddevice_mic:
        print(
            "[Jarvis] Micrófono: sounddevice (PyAudio no instalado o no compatible; "
            "normal en Python 3.14 en Windows)."
        )
        try:
            _calibrate_sounddevice_mic(rec, duration=1.0)
        except Exception as e:
            print(f"[Jarvis] Calibración de micrófono: {e} (se usan umbrales por defecto).")
            rec.__dict__["_jarvis_ambient_rms"] = 0.02
        if _clap_enabled:
            print(
                "[Jarvis] Aviso: aplausos y micrófono comparten el audio; "
                "si falla la captura, ponga clap_enabled en false en jarvis_config.json."
            )

    last_cfg_reload = 0.0
    recalibrate_at = time.time() + 120.0

    while not stop_event.is_set():
        try:
            now = time.time()
            if now - last_cfg_reload > 30:
                try:
                    cfg_holder["cfg"] = load_config()
                except OSError as e:
                    print(f"[Jarvis] No se pudo recargar config: {e}")
                last_cfg_reload = now

            cfg = cfg_holder.get("cfg")
            if cfg is None:
                cfg = load_config()
                cfg_holder["cfg"] = cfg
            _current_cfg = cfg

            maybe_run_morning(cfg)
            maybe_proactive(cfg)
            maybe_fire_reminders(cfg)

            if use_sounddevice_mic:
                if now > recalibrate_at:
                    try:
                        _calibrate_sounddevice_mic(rec, duration=0.6)
                    except OSError:
                        pass
                    recalibrate_at = now + 120.0
                audio = _listen_sounddevice(rec, timeout=1, phrase_time_limit=12)
            else:
                with sr.Microphone() as source:
                    audio = rec.listen(source, timeout=1, phrase_time_limit=12)

            text = recognize_from_audio(audio, cfg, rec)
            handle_voice_intent(text, cfg)
        except sr.WaitTimeoutError:
            continue
        except sr.UnknownValueError:
            continue
        except sr.RequestError as e:
            print(f"[Jarvis] Error del servicio de reconocimiento: {e}")
            time.sleep(3)
        except Exception as e:
            print(f"[Jarvis] Error en bucle de voz: {e}")
            time.sleep(1)


def main() -> None:
    global _clap_threshold, _clap_enabled, _current_cfg

    print("Jarvis — asistente local. Ctrl+C para salir.")
    cfg = load_config()
    _current_cfg = cfg
    cfg_holder: dict[str, Any] = {"cfg": cfg}
    _clap_threshold = float(cfg.get("clap_threshold", 0.2))
    _clap_enabled = bool(cfg.get("clap_enabled", True))

    stop_event = threading.Event()
    voice_thread = threading.Thread(
        target=recognition_loop,
        args=(cfg_holder, stop_event),
        daemon=True,
    )
    voice_thread.start()

    if _clap_enabled:
        print("[Jarvis] Doble aplauso: secuencia de bienvenida (macOS con ventanas; Windows abre Cursor y enlace).")

    try:
        if _clap_enabled:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                blocksize=BLOCK_SIZE,
                channels=1,
                dtype="float32",
                callback=lambda *a: clap_callback(cfg_holder, *a),
            ):
                while True:
                    time.sleep(0.2)
        else:
            while True:
                time.sleep(0.2)
                c = cfg_holder.get("cfg") or load_config()
                maybe_run_morning(c)
                maybe_proactive(c)
                maybe_fire_reminders(c)
    except KeyboardInterrupt:
        stop_event.set()
        print("\nHasta luego, Señor.")
        sys.exit(0)


if __name__ == "__main__":
    main()
