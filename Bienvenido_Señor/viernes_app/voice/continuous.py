from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from viernes_app.voice.speech_input import recognize_once, speech_input_available
from viernes_app.voice.wake_word import WakeWordDetector


@dataclass(frozen=True)
class ContinuousConversationStatus:
    running: bool
    wake_word: str
    speech_available: bool


class ContinuousConversationController:
    def __init__(self, on_command: Callable[[str], str], *, wake_word: str = "viernes", interruption_detector: Any = None) -> None:
        self.on_command = on_command
        self.detector = WakeWordDetector(wake_word)
        self.interruption_detector = interruption_detector
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        if self._running or not speech_input_available():
            return False
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._running = False

    def status(self) -> ContinuousConversationStatus:
        return ContinuousConversationStatus(self._running, self.detector.wake_word, speech_input_available())

    def configure_wake_word(self, wake_word: str) -> None:
        self.detector = WakeWordDetector(wake_word)

    def _loop(self) -> None:
        while self._running:
            try:
                text = recognize_once(timeout=5, phrase_time_limit=8)
                result = self.detector.detect(text)
                if result.detected and result.command:
                    if result.command.lower().strip() in {"detente", "para", "stop", "callate"} and self.interruption_detector is not None:
                        self.interruption_detector.interrupt("voice_command")
                    self.on_command(result.command)
            except Exception:
                time.sleep(0.4)
