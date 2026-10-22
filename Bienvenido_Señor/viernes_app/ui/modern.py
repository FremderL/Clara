from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk
from typing import Any

try:
    import customtkinter as ctk
except Exception:  # pragma: no cover - optional dependency
    ctk = None


PANEL_COMMANDS: dict[str, str] = {
    "Chat": "",
    "Dashboard": "estado agentes",
    "Memoria": "memoria agente",
    "Seguridad": "monitor seguridad",
    "Actividad": "resumen actividad personal",
    "Plugins": "plugins",
    "Herramientas": "herramientas registradas",
}

QUICK_ACTIONS: tuple[tuple[str, str], ...] = (
    ("Hoy", "plan de hoy"),
    ("Agenda", "mi agenda"),
    ("Pendientes", "que tengo pendiente"),
    ("Agentes", "estado agentes"),
    ("Seguridad", "monitor seguridad"),
)

CARD_COMMANDS: tuple[tuple[str, str], ...] = (
    ("Agentes", "estado agentes"),
    ("Memoria", "memoria agente"),
    ("Actividad", "estado monitoreo personal"),
    ("Seguridad", "monitor seguridad"),
)

COLORS = {
    "bg": "#0b1117",
    "surface": "#111a24",
    "surface_alt": "#162231",
    "line": "#26384a",
    "text": "#edf6ff",
    "muted": "#9fb1c3",
    "accent": "#28b8a9",
    "accent_alt": "#f6b44b",
    "danger": "#e35f6a",
}


def should_use_modern_ui(config: dict[str, Any]) -> bool:
    ui_cfg = config.get("ui", {}) if isinstance(config, dict) else {}
    if not isinstance(ui_cfg, dict):
        return False
    return str(ui_cfg.get("mode", "classic") or "classic").lower() == "modern"


class ModernShell:
    """Shell moderno opcional con fallback Tkinter."""

    def __init__(self, assistant: Any) -> None:
        self.assistant = assistant
        self.active_panel = "Chat"
        self.last_refresh = 0.0
        self.root = ctk.CTk() if ctk is not None else tk.Tk()
        self.root.title("Viernes")
        self.root.geometry("1320x820")
        self.root.minsize(1060, 660)
        self.output: Any = None
        self.entry: Any = None
        self.status_label: Any = None
        self.context_box: Any = None
        self._nav_buttons: dict[str, Any] = {}
        self._metric_labels: dict[str, Any] = {}
        self._build()
        self._select_panel("Chat")
        self._refresh_side_status()

    @property
    def customtkinter_available(self) -> bool:
        return ctk is not None

    def _build(self) -> None:
        if ctk is not None:
            self._build_ctk()
            return
        self._build_tk()

    def _build_ctk(self) -> None:
        assert ctk is not None
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.root.configure(fg_color=COLORS["bg"])

        shell = ctk.CTkFrame(self.root, fg_color=COLORS["bg"], corner_radius=0)
        shell.pack(fill="both", expand=True)
        shell.grid_columnconfigure(0, weight=0, minsize=230)
        shell.grid_columnconfigure(1, weight=1, minsize=560)
        shell.grid_columnconfigure(2, weight=0, minsize=300)
        shell.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(shell, width=230, fg_color=COLORS["surface"], corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        main = ctk.CTkFrame(shell, fg_color=COLORS["bg"], corner_radius=0)
        main.grid(row=0, column=1, sticky="nsew", padx=14, pady=14)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        inspector = ctk.CTkFrame(shell, width=300, fg_color=COLORS["surface"], corner_radius=0)
        inspector.grid(row=0, column=2, sticky="nsew")
        inspector.grid_propagate(False)

        self._build_ctk_sidebar(sidebar)
        self._build_ctk_main(main)
        self._build_ctk_inspector(inspector)

    def _build_ctk_sidebar(self, parent: Any) -> None:
        assert ctk is not None
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(18, 12))
        ctk.CTkLabel(header, text="VIERNES", text_color=COLORS["accent"], font=("Segoe UI Semibold", 24)).pack(anchor="w")
        ctk.CTkLabel(header, text="Agentes locales", text_color=COLORS["muted"], font=("Segoe UI", 12)).pack(anchor="w", pady=(2, 0))

        for label in PANEL_COMMANDS:
            button = ctk.CTkButton(
                parent,
                text=label,
                anchor="w",
                height=38,
                corner_radius=6,
                fg_color=COLORS["surface_alt"],
                hover_color="#203246",
                command=lambda name=label: self._select_panel(name),
            )
            button.pack(fill="x", padx=14, pady=4)
            self._nav_buttons[label] = button

        ctk.CTkLabel(parent, text="Acciones", text_color=COLORS["muted"], font=("Segoe UI", 12, "bold")).pack(
            anchor="w",
            padx=18,
            pady=(22, 8),
        )
        for label, command in QUICK_ACTIONS:
            ctk.CTkButton(
                parent,
                text=label,
                height=32,
                corner_radius=6,
                fg_color="transparent",
                border_width=1,
                border_color=COLORS["line"],
                hover_color="#1e2c3a",
                command=lambda cmd=command: self._run_quick_command(cmd),
            ).pack(fill="x", padx=14, pady=3)

        self.status_label = ctk.CTkLabel(parent, text="", text_color=COLORS["muted"], wraplength=190, justify="left")
        self.status_label.pack(side="bottom", fill="x", padx=18, pady=18)

    def _build_ctk_main(self, parent: Any) -> None:
        assert ctk is not None
        header = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=8)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="Centro de conversacion",
            text_color=COLORS["text"],
            font=("Segoe UI Semibold", 18),
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 2))
        ctk.CTkLabel(
            header,
            text="Chat, planes, memoria y diagnostico en una sola vista",
            text_color=COLORS["muted"],
            font=("Segoe UI", 12),
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 12))
        ctk.CTkButton(
            header,
            text="Refrescar",
            width=96,
            height=32,
            corner_radius=6,
            fg_color=COLORS["accent"],
            hover_color="#209b90",
            command=self._refresh_active_panel,
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=16)

        self.output = ctk.CTkTextbox(
            parent,
            wrap="word",
            fg_color=COLORS["surface"],
            text_color=COLORS["text"],
            scrollbar_button_color=COLORS["line"],
            scrollbar_button_hover_color=COLORS["accent"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["line"],
            font=("Segoe UI", 13),
        )
        self.output.grid(row=1, column=0, sticky="nsew")

        composer = ctk.CTkFrame(parent, fg_color=COLORS["surface"], corner_radius=8)
        composer.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        composer.grid_columnconfigure(0, weight=1)
        self.entry = ctk.CTkEntry(composer, placeholder_text="Escriba una instruccion para Viernes", height=40)
        self.entry.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.entry.bind("<Return>", lambda _event: self._send_chat())
        ctk.CTkButton(
            composer,
            text="Enviar",
            width=96,
            height=40,
            corner_radius=6,
            fg_color=COLORS["accent"],
            hover_color="#209b90",
            command=self._send_chat,
        ).grid(row=0, column=1, sticky="e", padx=(0, 10), pady=10)

    def _build_ctk_inspector(self, parent: Any) -> None:
        assert ctk is not None
        ctk.CTkLabel(parent, text="Estado", text_color=COLORS["text"], font=("Segoe UI Semibold", 18)).pack(
            anchor="w",
            padx=16,
            pady=(18, 8),
        )
        for title, command in CARD_COMMANDS:
            card = ctk.CTkFrame(parent, fg_color=COLORS["surface_alt"], corner_radius=8, border_width=1, border_color=COLORS["line"])
            card.pack(fill="x", padx=14, pady=6)
            ctk.CTkLabel(card, text=title, text_color=COLORS["muted"], font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
            label = ctk.CTkLabel(card, text="Cargando...", text_color=COLORS["text"], wraplength=248, justify="left")
            label.pack(anchor="w", fill="x", padx=12, pady=(0, 10))
            self._metric_labels[command] = label

        ctk.CTkLabel(parent, text="Contexto", text_color=COLORS["text"], font=("Segoe UI Semibold", 16)).pack(
            anchor="w",
            padx=16,
            pady=(18, 8),
        )
        self.context_box = ctk.CTkTextbox(
            parent,
            height=190,
            wrap="word",
            fg_color=COLORS["bg"],
            text_color=COLORS["muted"],
            scrollbar_button_color=COLORS["line"],
            scrollbar_button_hover_color=COLORS["accent"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["line"],
            font=("Segoe UI", 12),
        )
        self.context_box.pack(fill="both", expand=True, padx=14, pady=(0, 14))

    def _build_tk(self) -> None:
        self.root.configure(bg=COLORS["bg"])
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Modern.TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["surface"])
        style.configure("Modern.TLabel", background=COLORS["surface"], foreground=COLORS["text"])
        style.configure("Muted.TLabel", background=COLORS["surface"], foreground=COLORS["muted"])
        style.configure("Modern.TButton", padding=(10, 8))

        shell = ttk.Frame(self.root, style="Modern.TFrame")
        shell.pack(fill="both", expand=True)
        shell.grid_columnconfigure(0, weight=0, minsize=220)
        shell.grid_columnconfigure(1, weight=1, minsize=560)
        shell.grid_columnconfigure(2, weight=0, minsize=290)
        shell.grid_rowconfigure(0, weight=1)

        sidebar = ttk.Frame(shell, style="Panel.TFrame")
        sidebar.grid(row=0, column=0, sticky="nsew")
        main = ttk.Frame(shell, style="Modern.TFrame")
        main.grid(row=0, column=1, sticky="nsew", padx=12, pady=12)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)
        inspector = ttk.Frame(shell, style="Panel.TFrame")
        inspector.grid(row=0, column=2, sticky="nsew")

        ttk.Label(sidebar, text="VIERNES", style="Modern.TLabel", font=("Segoe UI Semibold", 22)).pack(
            anchor="w",
            padx=16,
            pady=(18, 4),
        )
        ttk.Label(sidebar, text="Agentes locales", style="Muted.TLabel").pack(anchor="w", padx=16, pady=(0, 12))
        for label in PANEL_COMMANDS:
            button = ttk.Button(sidebar, text=label, style="Modern.TButton", command=lambda name=label: self._select_panel(name))
            button.pack(fill="x", padx=12, pady=4)
            self._nav_buttons[label] = button

        ttk.Label(sidebar, text="Acciones", style="Muted.TLabel").pack(anchor="w", padx=16, pady=(22, 8))
        for label, command in QUICK_ACTIONS:
            ttk.Button(sidebar, text=label, command=lambda cmd=command: self._run_quick_command(cmd)).pack(fill="x", padx=12, pady=3)
        self.status_label = ttk.Label(sidebar, text="", style="Muted.TLabel", wraplength=180, justify="left")
        self.status_label.pack(side="bottom", fill="x", padx=16, pady=18)

        header = ttk.Frame(main, style="Panel.TFrame")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        header.grid_columnconfigure(0, weight=1)
        ttk.Label(header, text="Centro de conversacion", style="Modern.TLabel", font=("Segoe UI Semibold", 16)).grid(
            row=0,
            column=0,
            sticky="w",
            padx=12,
            pady=(10, 0),
        )
        ttk.Label(header, text="Chat, planes, memoria y diagnostico", style="Muted.TLabel").grid(
            row=1,
            column=0,
            sticky="w",
            padx=12,
            pady=(0, 10),
        )
        ttk.Button(header, text="Refrescar", command=self._refresh_active_panel).grid(row=0, column=1, rowspan=2, padx=12)

        text_frame = ttk.Frame(main)
        text_frame.grid(row=1, column=0, sticky="nsew")
        text_frame.grid_columnconfigure(0, weight=1)
        text_frame.grid_rowconfigure(0, weight=1)
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.output = tk.Text(
            text_frame,
            wrap="word",
            bg=COLORS["surface"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            bd=0,
            yscrollcommand=scrollbar.set,
            font=("Segoe UI", 12),
            padx=12,
            pady=12,
        )
        self.output.grid(row=0, column=0, sticky="nsew")
        scrollbar.config(command=self.output.yview)

        composer = ttk.Frame(main, style="Panel.TFrame")
        composer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        composer.grid_columnconfigure(0, weight=1)
        self.entry = ttk.Entry(composer)
        self.entry.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        self.entry.bind("<Return>", lambda _event: self._send_chat())
        ttk.Button(composer, text="Enviar", command=self._send_chat).grid(row=0, column=1, padx=(0, 10), pady=10)

        ttk.Label(inspector, text="Estado", style="Modern.TLabel", font=("Segoe UI Semibold", 16)).pack(
            anchor="w",
            padx=16,
            pady=(18, 8),
        )
        for title, command in CARD_COMMANDS:
            frame = ttk.Frame(inspector, style="Panel.TFrame")
            frame.pack(fill="x", padx=12, pady=6)
            ttk.Label(frame, text=title, style="Muted.TLabel").pack(anchor="w", padx=8, pady=(8, 2))
            label = ttk.Label(frame, text="Cargando...", style="Modern.TLabel", wraplength=240, justify="left")
            label.pack(anchor="w", fill="x", padx=8, pady=(0, 8))
            self._metric_labels[command] = label
        ttk.Label(inspector, text="Contexto", style="Modern.TLabel", font=("Segoe UI Semibold", 14)).pack(
            anchor="w",
            padx=16,
            pady=(18, 8),
        )
        context_frame = ttk.Frame(inspector)
        context_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        context_scroll = ttk.Scrollbar(context_frame)
        context_scroll.pack(side="right", fill="y")
        self.context_box = tk.Text(
            context_frame,
            wrap="word",
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            relief="flat",
            bd=0,
            yscrollcommand=context_scroll.set,
            font=("Segoe UI", 10),
            padx=8,
            pady=8,
        )
        self.context_box.pack(side="left", fill="both", expand=True)
        context_scroll.config(command=self.context_box.yview)

    def _select_panel(self, name: str) -> None:
        self.active_panel = name
        self._mark_active_nav()
        command = PANEL_COMMANDS.get(name, "")
        if not command:
            self._set_output(self._chat_welcome())
            self._set_context("Panel activo: Chat\nEstado: listo")
            return
        response = self._assistant_command(command, panel=name)
        self._set_output(self._panel_text(name, response))
        self._set_context(f"Panel activo: {name}\nComando: {command}\nUltima carga: {self._clock()}")

    def _refresh_active_panel(self) -> None:
        self._select_panel(self.active_panel)
        self._refresh_side_status(force=True)

    def _run_quick_command(self, command: str) -> None:
        response = self._assistant_command(command, panel="Accion rapida")
        self.active_panel = "Chat"
        self._mark_active_nav()
        self._append_output(f"\nKaiser: {command}\nViernes: {response}\n")
        self._set_context(f"Ultima accion rapida: {command}\n{self._clock()}")
        self._refresh_side_status()

    def _send_chat(self) -> None:
        text = self._entry_value().strip()
        if not text:
            return
        self._entry_clear()
        self.active_panel = "Chat"
        self._mark_active_nav()
        self._append_output(f"\nKaiser: {text}\n")
        response = self._assistant_command(text, panel="Chat")
        self._append_output(f"Viernes: {response}\n")
        self._set_context(f"Ultimo mensaje: {text[:160]}\n{self._clock()}")
        self._refresh_side_status()

    def _assistant_command(self, command: str, *, panel: str = "") -> str:
        try:
            result = self.assistant.process_command(command)
        except Exception as exc:
            return self._recoverable_error(command, exc, panel=panel)
        text = str(result or "").strip()
        if text:
            return text
        return "La accion termino sin salida. Siguiente paso: revisar estado agentes o repetir con mas detalle."

    def _recoverable_error(self, command: str, exc: Exception, *, panel: str = "") -> str:
        kind = exc.__class__.__name__
        detail = str(exc).strip() or "sin detalle"
        return (
            f"No pude completar {panel or 'la accion'} sin ayuda adicional.\n"
            f"Comando: {command}\n"
            f"Causa detectada: {kind}: {detail}\n"
            "Siguiente intento: revise el panel Seguridad/Agentes y vuelva a ejecutar la accion. "
            "La conversacion sigue activa."
        )

    def _refresh_side_status(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self.last_refresh < 6:
            return
        self.last_refresh = now
        for command, label in self._metric_labels.items():
            response = self._assistant_command(command, panel="Estado")
            self._set_label_text(label, self._compact(response, 160))
        if self.status_label is not None:
            mode = "CustomTkinter" if self.customtkinter_available else "Tkinter fallback"
            self._set_label_text(self.status_label, f"{mode}\nActualizado: {self._clock()}")

    def _mark_active_nav(self) -> None:
        if ctk is not None:
            for label, button in self._nav_buttons.items():
                try:
                    button.configure(fg_color=COLORS["accent"] if label == self.active_panel else COLORS["surface_alt"])
                except Exception:
                    pass

    def _panel_text(self, name: str, response: str) -> str:
        return f"{name}\n{'=' * len(name)}\n\n{response}"

    def _chat_welcome(self) -> str:
        return (
            "Viernes listo.\n\n"
            "Puede conversar de forma natural, crear planes, consultar memoria, seguridad, plugins y herramientas."
        )

    def _set_output(self, value: str) -> None:
        self._text_delete(self.output)
        self._text_insert(self.output, value)

    def _append_output(self, value: str) -> None:
        self._text_insert(self.output, value, at_end=True)
        try:
            self.output.see("end")
        except Exception:
            try:
                self.output.see(tk.END)
            except Exception:
                pass

    def _set_context(self, value: str) -> None:
        if self.context_box is None:
            return
        self._text_delete(self.context_box)
        self._text_insert(self.context_box, value)

    def _text_delete(self, widget: Any) -> None:
        try:
            widget.delete("1.0", "end")
        except Exception:
            widget.delete("1.0", tk.END)

    def _text_insert(self, widget: Any, value: str, *, at_end: bool = False) -> None:
        index = "end" if at_end else "1.0"
        try:
            widget.insert(index, value)
        except Exception:
            widget.insert(tk.END if at_end else "1.0", value)

    def _set_label_text(self, label: Any, value: str) -> None:
        try:
            label.configure(text=value)
        except Exception:
            label["text"] = value

    def _entry_value(self) -> str:
        return str(self.entry.get())

    def _entry_clear(self) -> None:
        try:
            self.entry.delete(0, "end")
        except Exception:
            self.entry.delete(0, tk.END)

    def _compact(self, value: str, limit: int) -> str:
        clean = " ".join(str(value or "").split())
        if len(clean) <= limit:
            return clean
        return clean[: max(0, limit - 3)].rstrip() + "..."

    def _clock(self) -> str:
        return time.strftime("%H:%M:%S")

    def run(self) -> None:
        self.root.mainloop()
