"""
push_to_talk.py
Activa el reconocimiento de voz solo mientras se mantiene presionada la tecla Alt Izquierda.
"""
import threading
import time
import logging

try:
    import keyboard  # pip install keyboard
except ImportError:
    keyboard = None

from viernes_app.voice.speech_input import recognize_once, speech_input_available

logging.basicConfig(level=logging.INFO)

HOTKEY_ALIASES = {
    "alt-izq": "left alt",
    "alt izq": "left alt",
    "alt izquierda": "left alt",
    "alt izquierdo": "left alt",
    "alt left": "left alt",
    "alt_l": "left alt",
    "left alt": "left alt",
}


def _normalize_hotkey(value: str) -> str:
    return HOTKEY_ALIASES.get((value or "").strip().lower(), value or "left alt")


class PushToTalk:
    def __init__(self, on_recognized, hotkey="alt left"):
        self.on_recognized = on_recognized
        self.hotkey = _normalize_hotkey(hotkey)
        self._running = False
        self._thread = None
        self._listening = False

    def start(self):
        if keyboard is None:
            logging.debug("El modulo 'keyboard' no esta instalado. Push-to-talk no disponible.")
            return
        if not speech_input_available():
            logging.error("Reconocimiento de voz no disponible.")
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logging.info(f"Push-to-talk activo. Mantén '{self.hotkey}' para hablar.")

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            if not self._listening and keyboard.is_pressed(self.hotkey):
                self._listening = True
                logging.info("Escuchando (push-to-talk)...")
                try:
                    text = recognize_once(on_status=logging.info)
                    if text:
                        self.on_recognized(text)
                except Exception as e:
                    logging.error(f"Error en reconocimiento: {e}")
                finally:
                    # Esperar a que se suelte la tecla para evitar capturas repetidas.
                    while self._running and keyboard.is_pressed(self.hotkey):
                        time.sleep(0.08)
                    self._listening = False
            time.sleep(0.1)

# Ejemplo seguro de uso
if __name__ == "__main__":
    def on_text(text):
        print(f"Reconocido: {text}")
    ptt = PushToTalk(on_text)
    ptt.start()
    input("Pulsa Enter para salir...\n")
    ptt.stop()
