"""Diagnóstico manual de voz de salida; no activa el micrófono ni usa internet."""
from __future__ import annotations

import sys

TEST_TEXT = "Prueba de voz de CLARA. Si puedes oír esta frase, la salida de voz de Windows funciona."


def main() -> int:
    try:
        import pyttsx3
    except ImportError:
        print("No está instalado pyttsx3 para este Python.")
        print("En esta carpeta puedes instalarlo con: py -3 -m pip install pyttsx3")
        return 1

    try:
        engine = pyttsx3.init()
        voices = engine.getProperty("voices") or []
        print(f"Motor de voz iniciado. Voces detectadas: {len(voices)}")
        spanish = None
        for voice in voices:
            details = f"{getattr(voice, 'name', '')} {getattr(voice, 'id', '')} {getattr(voice, 'languages', '')}"
            print("- " + details)
            normalized = details.casefold()
            if spanish is None and any(token in normalized for token in ("spanish", "es-es", "es-mx", "_es_", "español")):
                spanish = voice
        if spanish is not None:
            engine.setProperty("voice", spanish.id)
            print("Usaré la voz que parece ser de español.")
        else:
            print("No detecté una voz identificada como español; se probará la voz predeterminada de Windows.")
        engine.say(TEST_TEXT)
        engine.runAndWait()
        engine.stop()
        print("El motor terminó la prueba. Si no escuchaste nada, revisa volumen/dispositivo de salida y las voces instaladas en Windows.")
        return 0
    except Exception as exc:
        print(f"Falló la prueba local de voz: {type(exc).__name__}: {exc}")
        print("La prueba no utilizó micrófono ni internet.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
