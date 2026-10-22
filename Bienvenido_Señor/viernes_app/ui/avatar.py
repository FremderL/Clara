from __future__ import annotations

import time
import tkinter as tk


class HoloAvatar(tk.Canvas):
    def __init__(
        self,
        parent: tk.Widget,
        *,
        width: int = 280,
        height: int = 280,
        bg_color: str = "#0f1b28",
        accent: str = "#53c0ff",
        accent2: str = "#2dd4bf",
    ) -> None:
        super().__init__(parent, width=width, height=height, bg=bg_color, highlightthickness=0)
        self.width = width
        self.height = height
        self.center_x = width // 2
        self.center_y = height // 2
        self.bg_color = bg_color
        self.accent = accent
        self.accent2 = accent2
        self.phase = 0.0
        self.speaking_until = 0.0
        self.listening_until = 0.0
        self.after(40, self._animate)

    def pulse_speaking(self) -> None:
        self.speaking_until = time.time() + 1.2

    def pulse_listening(self) -> None:
        self.listening_until = time.time() + 0.8

    def _animate(self) -> None:
        if not self.winfo_exists():
            return
        try:
            self.delete("all")
            self.phase += 0.05
            speaking = time.time() < self.speaking_until
            listening = time.time() < self.listening_until
            glow = 8 if speaking else 0
            ring_color = self.accent if speaking else (self.accent2 if listening else "#2aa2d6")
            state_text = "HABLANDO" if speaking else ("ESCUCHANDO" if listening else "MODO ESPERA")

            for i, (radius, dash, width) in enumerate(((118, (6, 8), 1), (98, (2, 6), 2), (72, (), 2))):
                offset = (i + 1) * self.phase * 20
                self.create_oval(
                    self.center_x - radius - glow,
                    self.center_y - radius - glow,
                    self.center_x + radius + glow,
                    self.center_y + radius + glow,
                    outline=ring_color,
                    width=width,
                    dash=dash,
                )
                if dash:
                    self.create_arc(
                        self.center_x - radius,
                        self.center_y - radius,
                        self.center_x + radius,
                        self.center_y + radius,
                        start=int(offset) % 360,
                        extent=70,
                        style="arc",
                        outline="#93c5fd",
                        width=2,
                    )

            core_r = 42 + (4 if speaking else 0)
            self.create_oval(
                self.center_x - core_r,
                self.center_y - core_r,
                self.center_x + core_r,
                self.center_y + core_r,
                fill="#0d1b28",
                outline=ring_color,
                width=2,
            )
            self.create_text(
                self.center_x,
                self.center_y - 6,
                text="V",
                fill="#d8f6ff",
                font=("Segoe UI Semibold", 30),
            )
            self.create_text(
                self.center_x,
                self.center_y + 28,
                text=state_text,
                fill=ring_color,
                font=("Consolas", 9, "bold"),
            )
            self.after(40, self._animate)
        except tk.TclError:
            return
