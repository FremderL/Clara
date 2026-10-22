from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class InterruptionState:
    interrupted: bool
    reason: str = ""


class InterruptionDetector:
    def __init__(self) -> None:
        self._event = threading.Event()
        self._reason = ""

    def interrupt(self, reason: str = "usuario") -> None:
        self._reason = reason
        self._event.set()

    def clear(self) -> None:
        self._reason = ""
        self._event.clear()

    def state(self) -> InterruptionState:
        return InterruptionState(self._event.is_set(), self._reason)
