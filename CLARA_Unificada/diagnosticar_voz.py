"""Diagnóstico local de voz (TTS y Push-to-Talk) para CLARA Unificada. No usa micrófono ni internet."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

TEST_PHRASE = "Hola. Esta es una prueba manual de la voz local de Clara Unificada."


def _looks_spanish(voice) -> bool:
    haystack = " ".join(
        (
            str(getattr(voice, "id", "") or ""),
            str(getattr(voice, "name", "") or ""),
            str(getattr(voice, "languages", "") or ""),
        )
    ).casefold()
    return any(token in haystack for token in ("spanish", "español", "espanol", "es-mx", "es_mx", "es-es", "es_es", "es-419", "sabina", "helena", "pablo", "raul", "dalia"))


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    check_only = "--check-only" in args
    base_dir = Path(__file__).resolve().parent
    model_dir = base_dir / "models" / "vosk-model-small-es-0.42"

    print("=== Diagnóstico local de voz de CLARA Unificada ===")
    print("Nota: Esta utilidad NO enciende el micrófono ni realiza conexiones a internet.\n")

    vosk_ok = importlib.util.find_spec("vosk") is not None
    sd_ok = importlib.util.find_spec("sounddevice") is not None
    model_ok = model_dir.is_dir()
    print(f"[Entrada Push-to-Talk] vosk: {'OK' if vosk_ok else 'FALTA'} | sounddevice: {'OK' if sd_ok else 'FALTA'} | modelo local ({model_dir.name}): {'OK' if model_ok else 'FALTA'}")

    if importlib.util.find_spec("pyttsx3") is None:
        print("[Salida TTS] ERROR: pyttsx3 no está instalado en este Python.")
        print("Siguiente paso: ejecuta instalar_voz.bat si deseas habilitar respuestas habladas; las respuestas escritas siguen disponibles.")
        return 1

    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = list(engine.getProperty("voices") or [])
    except Exception as exc:
        print(f"[Salida TTS] ERROR: No se pudo iniciar el motor de voz del sistema: {exc}")
        return 2

    if not voices:
        print("[Salida TTS] ERROR: El sistema no devolvió ninguna voz instalada.")
        print("Siguiente paso: en Windows abre Configuración > Hora e idioma > Voz e instala Español (México) o Español (España).")
        return 3

    spanish_voice = next((voice for voice in voices if _looks_spanish(voice)), None)
    selected = spanish_voice or voices[0]
    voice_name = getattr(selected, "name", None) or getattr(selected, "id", "desconocida")
    print(f"[Salida TTS] Voces detectadas: {len(voices)}")
    print(f"[Salida TTS] Voz seleccionada: {voice_name}")
    if spanish_voice is None:
        print("[Salida TTS] AVISO: No se detectó una etiqueta explícita de español; se usará la voz predeterminada del sistema.")

    if check_only:
        print("Diagnóstico estático completado correctamente (--check-only).")
        return 0

    try:
        if getattr(selected, "id", None):
            engine.setProperty("voice", selected.id)
        print("Reproduciendo frase de prueba…")
        engine.say(TEST_PHRASE)
        engine.runAndWait()
        print("LISTO: La orden de lectura terminó sin errores.")
        return 0
    except Exception as exc:
        print(f"[Salida TTS] ERROR al reproducir la voz: {exc}")
        return 4


if __name__ == "__main__":
    raise SystemExit(main())
