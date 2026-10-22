from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class WakeWordResult:
    detected: bool
    command: str = ""


class WakeWordDetector:
    def __init__(self, wake_word: str = "viernes") -> None:
        self.wake_word = self._normalize(wake_word or "viernes")

    def detect(self, text: str) -> WakeWordResult:
        low = self._normalize(text)
        if not low:
            return WakeWordResult(False)
        if low == self.wake_word:
            return WakeWordResult(True, "")
        prefix = self.wake_word + " "
        if low.startswith(prefix):
            return WakeWordResult(True, text[len(prefix):].strip())
        return WakeWordResult(False)

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").lower().strip())
