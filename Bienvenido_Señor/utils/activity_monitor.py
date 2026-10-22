"""
activity_monitor.py
Monitor de actividad: detecta inactividad del sistema (teclado/ratón) y del asistente.
"""
from __future__ import annotations

import ctypes
import logging
import os
import threading
import time
from typing import Callable, Optional

logging.basicConfig(level=logging.INFO)


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def windows_system_idle_seconds() -> float | None:
    """Segundos desde la última entrada de teclado/ratón en Windows."""
    if os.name != "nt":
        return None
    try:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return None
        tick = int(ctypes.windll.kernel32.GetTickCount())
        last_input = int(lii.dwTime)
        idle_ms = (tick - last_input) & 0xFFFFFFFF
        return max(0.0, idle_ms / 1000.0)
    except Exception:
        return None


class ActivityMonitor:
    def __init__(
        self,
        timeout_seconds: int = 300,
        on_inactive: Optional[Callable] = None,
        on_active: Optional[Callable] = None,
        system_idle_provider: Callable[[], float | None] | None = None,
    ):
        self.timeout = timeout_seconds
        self.on_inactive = on_inactive
        self.on_active = on_active
        self._system_idle_provider = system_idle_provider
        self._last_activity = time.time()
        self._away = False
        self._away_since: float | None = None
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._running = False

    def start(self):
        self._running = True
        if not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self):
        self._running = False

    def notify_activity(self):
        became_active = False
        idle_seconds = 0.0
        with self._lock:
            self._last_activity = time.time()
            if self._away:
                self._away = False
                became_active = True
                if self._away_since is not None:
                    idle_seconds = max(0.0, self._last_activity - self._away_since)
                self._away_since = None
                logging.info("Usuario activo de nuevo.")
        if became_active and self.on_active:
            try:
                self.on_active(idle_seconds)
            except TypeError:
                self.on_active()
            except Exception as e:
                logging.error(f"Error en callback de actividad: {e}")

    def is_away(self) -> bool:
        return self._away

    def effective_idle_seconds(self) -> float:
        app_idle = max(0.0, time.time() - self._last_activity)
        if self._system_idle_provider is None:
            return app_idle
        try:
            system_idle = self._system_idle_provider()
        except Exception:
            system_idle = None
        if system_idle is None:
            return app_idle
        return min(app_idle, system_idle)

    def _run(self):
        while self._running:
            time.sleep(2)
            inactive_callback = None
            active_callback = None
            idle_seconds = 0.0
            with self._lock:
                effective_idle = self.effective_idle_seconds()
                if not self._away and effective_idle > self.timeout:
                    self._away = True
                    self._away_since = time.time() - effective_idle
                    logging.info("Usuario inactivo. Activando modo away.")
                    inactive_callback = self.on_inactive
                elif self._away and effective_idle <= self.timeout:
                    if self._away_since is not None:
                        idle_seconds = max(0.0, time.time() - self._away_since)
                    self._away = False
                    self._away_since = None
                    logging.info("Usuario activo de nuevo (entrada del sistema).")
                    active_callback = self.on_active
            if inactive_callback:
                try:
                    inactive_callback()
                except Exception as e:
                    logging.error(f"Error en callback de inactividad: {e}")
            if active_callback:
                try:
                    active_callback(idle_seconds)
                except TypeError:
                    active_callback()
                except Exception as e:
                    logging.error(f"Error en callback de actividad: {e}")


if __name__ == "__main__":
    def alerta():
        print("Usuario inactivo detectado!")

    monitor = ActivityMonitor(
        timeout_seconds=5,
        on_inactive=alerta,
        system_idle_provider=windows_system_idle_seconds,
    )
    monitor.start()
    for i in range(10):
        time.sleep(1)
        if i == 2:
            monitor.notify_activity()
        print(f"Segundo {i}, away={monitor.is_away()}, idle={monitor.effective_idle_seconds():.1f}s")
    monitor.stop()
