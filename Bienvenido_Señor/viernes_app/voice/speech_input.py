from __future__ import annotations

import json
import queue
import time
from pathlib import Path
from typing import Callable

try:
    import speech_recognition as sr
except Exception:  # pragma: no cover - optional dependency
    sr = None

try:
    import sounddevice as sd
except Exception:  # pragma: no cover - optional dependency
    sd = None

try:
    import vosk
except Exception:  # pragma: no cover - optional dependency
    vosk = None

from viernes_app.paths import REPO_ROOT


VOSK_MODEL_DIRS = (
    REPO_ROOT / "vosk-model-small-es-0.42",
    REPO_ROOT / "models" / "vosk-model-small-es-0.42",
)


def _sr_microphone_available() -> bool:
    if sr is None:
        return False
    try:
        sr.Microphone.list_microphone_names()
        return True
    except Exception:
        return False


def _vosk_model_path() -> Path | None:
    if vosk is None or sd is None:
        return None
    for path in VOSK_MODEL_DIRS:
        if path.exists():
            return path
    return None

def speech_input_available() -> bool:
    return _sr_microphone_available() or _vosk_model_path() is not None


def _recognize_with_vosk(
    *,
    on_status: Callable[[str], None] | None = None,
    timeout: int = 6,
    phrase_time_limit: int = 8,
) -> str:
    model_path = _vosk_model_path()
    if model_path is None:
        raise RuntimeError("No hay microfono compatible ni modelo Vosk en el proyecto.")

    if on_status is not None:
        on_status("Preparando Vosk...")

    audio_queue: "queue.Queue[bytes]" = queue.Queue()

    def callback(indata, _frames, _time_info, status) -> None:
        if status and on_status is not None:
            on_status(str(status))
        audio_queue.put(bytes(indata))

    model = vosk.Model(str(model_path))
    recognizer = vosk.KaldiRecognizer(model, 16000)
    started = time.monotonic()
    deadline = started + max(1, phrase_time_limit)

    with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype="int16", channels=1, callback=callback):
        if on_status is not None:
            on_status("Escuchando...")
        while time.monotonic() < deadline:
            try:
                data = audio_queue.get(timeout=max(0.2, min(timeout, 1)))
            except queue.Empty:
                if time.monotonic() - started > timeout:
                    break
                continue
            if recognizer.AcceptWaveform(data):
                payload = json.loads(recognizer.Result() or "{}")
                text = str(payload.get("text", "")).strip()
                if text:
                    return text
        payload = json.loads(recognizer.FinalResult() or "{}")
        text = str(payload.get("text", "")).strip()
        if text:
            return text

    raise RuntimeError("No detecte una frase clara.")


def recognize_once(
    *,
    on_status: Callable[[str], None] | None = None,
    timeout: int = 6,
    phrase_time_limit: int = 8,
) -> str:
    if not _sr_microphone_available():
        return _recognize_with_vosk(on_status=on_status, timeout=timeout, phrase_time_limit=phrase_time_limit)

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True

    if on_status is not None:
        on_status("Preparando microfono...")

    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            if on_status is not None:
                on_status("Escuchando...")
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
    except Exception:
        return _recognize_with_vosk(on_status=on_status, timeout=timeout, phrase_time_limit=phrase_time_limit)

    attempts: list[Callable[[], str]] = []
    if hasattr(recognizer, "recognize_whisper"):
        attempts.append(lambda: recognizer.recognize_whisper(audio, language="spanish"))
    if hasattr(recognizer, "recognize_vosk"):
        attempts.append(lambda: recognizer.recognize_vosk(audio, language="es"))
    if hasattr(recognizer, "recognize_google"):
        attempts.append(lambda: recognizer.recognize_google(audio, language="es-MX"))

    last_error: Exception | None = None
    for attempt in attempts:
        try:
            text = attempt()
            if isinstance(text, str) and text.strip():
                return text.strip()
        except Exception as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise last_error
    raise RuntimeError("No hay un backend de reconocimiento disponible.")
