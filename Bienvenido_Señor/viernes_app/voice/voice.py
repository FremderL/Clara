from __future__ import annotations

import re
import sys
import subprocess
import threading
from typing import Any


class ViernesVoice:
    def __init__(self, rate: int = 165, enabled: bool = True, interruption_detector: Any = None) -> None:
        self.rate = rate
        self.enabled = enabled
        self.interruption_detector = interruption_detector
        self._speak_lock = threading.Lock()
        self._stop_event = threading.Event()

    def apply_profile(self, profile: Any) -> None:
        self.rate = int(getattr(profile, "rate", self.rate) or self.rate)
        self.enabled = bool(getattr(profile, "enabled", self.enabled)) if hasattr(profile, "enabled") else self.enabled

    def speak(self, text: str) -> None:
        self._safe_print(f"[Viernes] {text}")
        if not self.enabled:
            return
        self._stop_event.clear()
        if self.interruption_detector is not None:
            try:
                self.interruption_detector.clear()
            except Exception:
                pass
        threading.Thread(target=self._worker, args=(text,), daemon=True).start()

    def stop(self) -> None:
        """Detiene la voz actual matando cualquier proceso de TTS en curso."""
        self._stop_event.set()
        if self.interruption_detector is not None:
            try:
                self.interruption_detector.interrupt("manual_stop")
            except Exception:
                pass
        # Intentar matar procesos de powershell de TTS activos
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(New-Object -ComObject SAPI.SpVoice).Speak('', 3)"],
                capture_output=True, text=True, timeout=5,
            )
        except Exception:
            pass

    def _safe_print(self, text: str) -> None:
        try:
            print(text)
        except UnicodeEncodeError:
            safe = text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8", errors="replace")
            print(safe)

    def _split_text(self, text: str) -> list[str]:
        parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+|(?<=:)\s+|(?<=,)\s+| \| ", text) if part.strip()]
        if not parts:
            return [text.strip()]
        chunks: list[str] = []
        current = ""
        for part in parts:
            candidate = f"{current} {part}".strip() if current else part
            if len(candidate) <= 90:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = part
        if current:
            chunks.append(current)
        return chunks or [text.strip()]

    def _worker(self, text: str) -> None:
        with self._speak_lock:
            if self._stop_event.is_set():
                return
            chunks = self._split_text(text)
            for chunk in chunks:
                if self._stop_event.is_set() or self._is_interrupted():
                    return
                safe_chunk = chunk.replace("'", "''")
                script = (
                    "$v = New-Object -ComObject SAPI.SpVoice; "
                    f"$v.Rate = {max(-10, min(10, int(round((self.rate - 160) / 12))))}; "
                    f"$null = $v.Speak('{safe_chunk}'); "
                )
                try:
                    subprocess.run(
                        ["powershell", "-NoProfile", "-Command", script],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        timeout=60,
                    )
                except Exception:
                    pass

    def _is_interrupted(self) -> bool:
        if self.interruption_detector is None:
            return False
        try:
            return bool(self.interruption_detector.state().interrupted)
        except Exception:
            return False
