from __future__ import annotations

import asyncio
import os
import subprocess
import threading
from typing import Optional

from viernes_app.paths import RUNTIME_DIR

TTS_CACHE = RUNTIME_DIR / "tts_cache"


class EdgeTTS:
    VOICES = {
        "es-MX": {
            "male": "es-MX-DaliaNeural",
            "female": "es-MX-AngelaNeural",
        },
        "default": "es-MX-DaliaNeural",
    }

    def __init__(self, voice: str = "es-MX-DaliaNeural", rate: str = "+0%", pitch: str = "+0Hz") -> None:
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self._enabled = True

    async def _speak_async(self, text: str) -> Optional[str]:
        try:
            import edge_tts
        except ImportError:
            return None

        TTS_CACHE.mkdir(exist_ok=True)
        output_file = TTS_CACHE / f"tts_{id(text)}.mp3"

        communicate = edge_tts.Communicate(text, self.voice, rate=self.rate, pitch=self.pitch)
        await communicate.save(str(output_file))

        if output_file.exists():
            return str(output_file)
        return None

    def speak(self, text: str) -> None:
        if not self._enabled:
            return
        threading.Thread(target=self._speak_worker, args=(text,), daemon=True).start()

    def _speak_worker(self, text: str) -> None:
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            audio_file = loop.run_until_complete(self._speak_async(text))
            loop.close()

            if audio_file and os.path.exists(audio_file):
                subprocess.run(
                    ["powershell", "-Command", f"(New-Object System.Media.SoundPlayer '{audio_file}').PlaySync()"],
                    capture_output=True,
                    timeout=30,
                )
                try:
                    os.remove(audio_file)
                except Exception:
                    pass
        except Exception:
            pass


class WindowsTTS:
    def __init__(self, rate: int = 165, enabled: bool = True) -> None:
        self.rate = rate
        self.enabled = enabled

    def speak(self, text: str) -> None:
        print(f"[Viernes] {text}")
        if not self.enabled:
            return
        threading.Thread(target=self._worker, args=(text,), daemon=True).start()

    def _worker(self, text: str) -> None:
        import time
        time.sleep(0.15)
        
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            rate_val = max(-10, min(10, int(round((self.rate - 160) / 12))))
            speaker.Rate = rate_val
            speaker.Speak(text)
        except Exception:
            try:
                import subprocess
                safe = text.replace("'", "''").replace('"', '\\"')
                rate_val = max(-10, min(10, int(round((self.rate - 160) / 12))))
                script = f'Add-Type -AssemblyName System.Speech; $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; $speak.Rate = {rate_val}; $speak.Speak("{safe}")'
                subprocess.run(["powershell", "-Command", script], capture_output=True, timeout=15)
            except Exception:
                pass


class FridayVoice:
    def __init__(self, tts_type: str = "edge", rate: int = 165, enabled: bool = True) -> None:
        self.enabled = enabled
        self.tts_type = tts_type
        self._tts: Optional[EdgeTTS | WindowsTTS] = None

        if tts_type == "edge":
            try:
                self._tts = EdgeTTS(rate=rate)
            except Exception:
                self._tts = WindowsTTS(rate=rate, enabled=enabled)
        else:
            self._tts = WindowsTTS(rate=rate, enabled=enabled)

    def speak(self, text: str) -> None:
        print(f"[Viernes] {text}")
        if self.enabled and self._tts:
            self._tts.speak(text)
