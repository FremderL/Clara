from __future__ import annotations

import json
import threading
import time
import tkinter as tk
from tkinter import ttk

from viernes_app.services.budget_data import (
    add_expense,
    add_income,
    get_balance,
    get_expenses_by_category,
    get_recent_transactions,
    parse_amount,
    set_budget_limit,
)
from viernes_app.core.assistant import ViernesAssistant
from viernes_app.core.routine_helpers import WEEKDAY_KEYS, WEEKDAY_LABELS, new_reminder_id
from viernes_app.ui.avatar import HoloAvatar
from viernes_app.ui.modern import ModernShell, should_use_modern_ui
from viernes_app.voice.speech_input import recognize_once, speech_input_available


BG = "#081019"
PANEL = "#0f1b28"
TEXT = "#e9f4ff"
MUTED = "#95afc4"
ACCENT = "#53c0ff"
PANEL_ALT = "#122130"
ACCENT2 = "#2dd4bf"
LINE = "#1f3a52"
HEADER = "#0b1420"


class ViernesGUI:
    def __init__(self) -> None:
        self.assistant = ViernesAssistant()
        self._modern_shell: ModernShell | None = None
        if should_use_modern_ui(self.assistant.config):
            self._modern_shell = ModernShell(self.assistant)
            self.running = True
            return
        self.root = tk.Tk()
        self.root.title("Viernes")
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(1120, max(980, screen_w - 80))
        height = min(700, max(600, screen_h - 90))
        self.root.geometry(f"{width}x{height}+32+24")
        self.root.minsize(980, 600)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self.running = True
        self.routine_window: tk.Toplevel | None = None
        self.routine_entries: dict[str, tk.Entry] = {}
        self.classes_window: tk.Toplevel | None = None
        self.class_entries: dict[str, tk.Entry] = {}
        self.budget_window: tk.Toplevel | None = None
        self.agenda_window: tk.Toplevel | None = None
        self.config_window: tk.Toplevel | None = None
        self.config_vars: dict[str, tk.Variable] = {}
        self.config_texts: dict[str, tk.Text] = {}
        self.listen_button: tk.Button | None = None
        self.listening_in_progress = False
        self.pending_morning_shown = False
        self.analysis_image_ref: tk.PhotoImage | None = None

        self._build_ui_modern()
        self._bind_hotkeys()
        self.root.after(120, self._present_window)
        self._refresh_dashboard()
        self._poll_messages()
        self._start_scheduler_thread()

    def _present_window(self) -> None:
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(600, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        except tk.TclError:
            return

    def _bind_hotkeys(self) -> None:
        self.root.bind_all("<KeyPress-Alt_L>", self._listen_hotkey)
        self.root.bind_all("<Alt_L>", self._listen_hotkey)
        self.root.bind_all("<Escape>", lambda _event: self._force_stop())

    def _listen_hotkey(self, _event=None) -> str:
        self._listen_once()
        return "break"

    def _enable_mousewheel(self, canvas: tk.Canvas, target: tk.Widget) -> None:
        def _on_mousewheel(event) -> None:
            delta = 0
            if hasattr(event, "delta") and event.delta:
                delta = -1 * int(event.delta / 120)
            elif getattr(event, "num", None) == 4:
                delta = -1
            elif getattr(event, "num", None) == 5:
                delta = 1
            if delta:
                canvas.yview_scroll(delta, "units")

        def _bind_all(_event=None) -> None:
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", _on_mousewheel)
            canvas.bind_all("<Button-5>", _on_mousewheel)

        def _unbind_all(_event=None) -> None:
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        target.bind("<Enter>", _bind_all)
        target.bind("<Leave>", _unbind_all)
        for child in target.winfo_children():
            child.bind("<Enter>", _bind_all)
            child.bind("<Leave>", _unbind_all)

    def _panel(self, parent: tk.Widget, *, pady: tuple[int, int] = (0, 12), expand: bool = False) -> tk.Frame:
        shell = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        shell.pack(fill="both" if expand else "x", expand=expand, pady=pady)
        return shell

    def _metric_card(self, parent: tk.Widget, title: str, value: str) -> tk.Label:
        card = tk.Frame(parent, bg=PANEL_ALT, highlightthickness=1, highlightbackground=LINE)
        card.pack(side="left", fill="both", expand=True, padx=(0, 8))
        tk.Label(card, text=title, bg=PANEL_ALT, fg=MUTED, font=("Consolas", 8, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        value_label = tk.Label(card, text=value, bg=PANEL_ALT, fg=TEXT, font=("Segoe UI Semibold", 12))
        value_label.pack(anchor="w", padx=10, pady=(0, 10))
        return value_label

    def _build_ui(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, foreground=TEXT, fieldbackground=PANEL, rowheight=26)
        style.configure("Treeview.Heading", background=PANEL_ALT, foreground=TEXT)

        header = tk.Frame(self.root, bg=HEADER, highlightthickness=1, highlightbackground=LINE)
        header.pack(fill="x", padx=16, pady=(14, 10))
        header_inner = tk.Frame(header, bg=HEADER)
        header_inner.pack(fill="x", padx=16, pady=14)
        title_block = tk.Frame(header_inner, bg=HEADER)
        title_block.pack(side="left")
        tk.Label(title_block, text="VIERNES", bg=HEADER, fg=ACCENT, font=("Segoe UI Semibold", 22)).pack(anchor="w")
        tk.Label(
            title_block,
            text="ASISTENTE PERSONAL  •  RUTINAS  •  AGENDA  •  PRESUPUESTO",
            bg=HEADER,
            fg=MUTED,
            font=("Consolas", 9),
        ).pack(anchor="w", pady=(2, 0))
        self.status_label = tk.Label(header_inner, text="Sistema en linea", bg=HEADER, fg=ACCENT2, font=("Segoe UI", 10))
        self.status_label.pack(side="left", padx=(18, 0))

        actions = tk.Frame(header_inner, bg=HEADER)
        actions.pack(side="right")
        # Boton de parada de emergencia
        self.stop_button = tk.Button(
            actions,
            text="DETENER",
            command=self._force_stop,
            bg="#e74c3c",
            fg="#ffffff",
            activebackground="#c0392b",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            font=("Segoe UI Semibold", 10),
            padx=14,
            pady=8,
            cursor="hand2",
        )
        self.stop_button.pack(side="left", padx=(0, 14))
        for label, command, accent in [
            ("Agenda", self._open_agenda_editor, False),
            ("Clases", self._open_classes_editor, False),
            ("Presupuesto", self._open_budget_editor, False),
            ("Rutinas", self._open_routine_editor, True),
            ("Configurar", self._open_config_center, False),
            ("Residente", lambda: self._submit("activar modo residente"), False),
            ("Verificar", lambda: self._submit("verificar despertar"), False),
        ]:
            tk.Button(
                actions,
                text=label,
                command=command,
                bg=ACCENT if accent else PANEL,
                fg=BG if accent else TEXT,
                activebackground=PANEL_ALT,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                font=("Segoe UI Semibold" if accent else "Segoe UI", 10),
                padx=12,
                pady=8,
            ).pack(side="left", padx=(0, 8))

        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        left = tk.Frame(main, bg=BG)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(main, bg=BG, width=380)
        right.pack(side="right", fill="y", padx=(16, 0))
        right.pack_propagate(False)

        avatar_shell = tk.Frame(left, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        avatar_shell.pack(fill="x", pady=(0, 12))
        avatar_row = tk.Frame(avatar_shell, bg=PANEL)
        avatar_row.pack(fill="x", padx=16, pady=16)
        self.avatar = HoloAvatar(avatar_row, width=280, height=280)
        self.avatar.pack(side="left")
        avatar_info = tk.Frame(avatar_row, bg=PANEL)
        avatar_info.pack(side="left", fill="both", expand=True, padx=(16, 0))
        tk.Label(avatar_info, text="Centro Holografico", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 14)).pack(anchor="w")
        tk.Label(
            avatar_info,
            text="Asistente personal para rutina, clases, agenda y presupuesto.\nMantiene contexto del dia y habla cuando corresponde.",
            bg=PANEL,
            fg=MUTED,
            justify="left",
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(8, 10))
        quick_info = tk.Frame(avatar_info, bg=PANEL)
        quick_info.pack(fill="x", pady=(8, 0))
        for text, command_text in [
            ("Que tengo hoy", "que tengo hoy"),
            ("Mi agenda", "mi agenda"),
            ("Lista", "lista"),
            ("Presupuesto", "presupuesto"),
        ]:
            tk.Button(
                quick_info,
                text=text,
                command=lambda cmd=command_text: self._submit(cmd),
                bg=PANEL_ALT,
                fg=ACCENT,
                activebackground=LINE,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                font=("Consolas", 9),
                padx=8,
                pady=6,
                cursor="hand2",
            ).pack(anchor="w", pady=(0, 6))

        stats_row = tk.Frame(avatar_info, bg=PANEL)
        stats_row.pack(fill="x", pady=(10, 0))
        self.metric_agenda = self._metric_card(stats_row, "EVENTOS HOY", "0")
        self.metric_classes = self._metric_card(stats_row, "CLASES", "0")
        self.metric_budget = self._metric_card(stats_row, "BALANCE", "$0")

        self._build_command_bar(avatar_shell)

        convo_shell = tk.Frame(left, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        convo_shell.pack(fill="both", expand=True)
        tk.Label(convo_shell, text="Conversacion", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.log = tk.Text(convo_shell, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, wrap="word", font=("Consolas", 10))
        self.log.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.log.configure(state="disabled")
        self._build_right_panel(right)

    def _build_command_bar(self, parent: tk.Widget) -> None:
        footer = tk.Frame(parent, bg=HEADER, highlightthickness=1, highlightbackground=LINE)
        footer.pack(fill="x", padx=16, pady=(0, 16))

        quick_shell = tk.Frame(footer, bg=HEADER)
        quick_shell.pack(fill="x", padx=14, pady=(12, 8))
        for label in self.assistant.config.get("quick_actions", []):
            tk.Button(
                quick_shell,
                text=label,
                command=lambda cmd=label: self._submit(cmd),
                bg=PANEL,
                fg=TEXT,
                activebackground=PANEL_ALT,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                font=("Segoe UI", 9),
                padx=10,
                pady=8,
                cursor="hand2",
            ).pack(side="left", padx=(0, 6))

        entry_shell = tk.Frame(footer, bg=HEADER)
        entry_shell.pack(fill="x", padx=14, pady=(0, 14))
        tk.Label(entry_shell, text="Comando", bg=HEADER, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))

        row = tk.Frame(entry_shell, bg=HEADER)
        row.pack(fill="x")
        self.entry = tk.Entry(row, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, font=("Segoe UI", 12))
        self.entry.pack(side="left", fill="x", expand=True, ipady=10, padx=(0, 10))
        self.entry.bind("<Return>", lambda _e: self._submit())
        self.listen_button = tk.Button(
            row,
            text="Hablar",
            command=self._listen_once,
            bg=ACCENT2,
            fg=BG,
            activebackground=ACCENT,
            activeforeground=BG,
            relief="flat",
            bd=0,
            font=("Segoe UI Semibold", 10),
            padx=14,
            pady=10,
            cursor="hand2",
        )
        self.listen_button.pack(side="right", padx=(0, 10))
        tk.Button(
            row,
            text="Enviar",
            command=self._submit,
            bg=ACCENT,
            fg=BG,
            activebackground=ACCENT2,
            activeforeground=BG,
            relief="flat",
            bd=0,
            font=("Segoe UI Semibold", 10),
            padx=14,
            pady=10,
            cursor="hand2",
        ).pack(side="right")

    def _build_right_panel(self, parent: tk.Frame) -> None:
        overview_shell = self._panel(parent, pady=(0, 12))
        tk.Label(overview_shell, text="Resumen rapido", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.summary_text = tk.Label(
            overview_shell,
            text="Sistema listo para agenda, clases, rutinas y presupuesto.",
            justify="left",
            bg=PANEL,
            fg=MUTED,
            wraplength=330,
            font=("Segoe UI", 10),
        )
        self.summary_text.pack(fill="x", padx=12, pady=(0, 12))

        agenda_shell = self._panel(parent)
        tk.Label(agenda_shell, text="Agenda de hoy", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.agenda_tree = ttk.Treeview(agenda_shell, columns=("hora", "titulo"), show="headings", height=7)
        self.agenda_tree.heading("hora", text="Hora")
        self.agenda_tree.heading("titulo", text="Titulo")
        self.agenda_tree.column("hora", width=70, anchor="center")
        self.agenda_tree.column("titulo", width=260, anchor="w")
        self.agenda_tree.pack(fill="x", padx=12, pady=(0, 12))

        today_shell = self._panel(parent)
        tk.Label(today_shell, text="Estado del dia", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.today_text = tk.Label(today_shell, text="", justify="left", bg=PANEL, fg=MUTED, wraplength=330, font=("Segoe UI", 10))
        self.today_text.pack(fill="x", padx=12, pady=(0, 12))

        budget_shell = self._panel(parent)
        tk.Label(budget_shell, text="Presupuesto", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.budget_text = tk.Label(budget_shell, text="", justify="left", bg=PANEL, fg=MUTED, wraplength=330, font=("Segoe UI", 10))
        self.budget_text.pack(fill="x", padx=12, pady=(0, 12))

        system_shell = self._panel(parent)
        tk.Label(system_shell, text="Sistema", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.system_text = tk.Label(system_shell, text="", justify="left", bg=PANEL, fg=MUTED, wraplength=330, font=("Segoe UI", 10))
        self.system_text.pack(fill="x", padx=12, pady=(0, 10))
        system_actions = tk.Frame(system_shell, bg=PANEL)
        system_actions.pack(fill="x", padx=12, pady=(0, 12))
        for label, command_text in [
            ("Activar", "activar modo residente"),
            ("Desactivar", "desactivar modo residente"),
            ("Verificar", "verificar despertar"),
            ("Probar", "probar despertar"),
        ]:
            tk.Button(
                system_actions,
                text=label,
                command=lambda cmd=command_text: self._submit(cmd),
                bg=PANEL_ALT,
                fg=TEXT,
                activebackground=LINE,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                font=("Segoe UI", 9),
                padx=10,
                pady=7,
                cursor="hand2",
            ).pack(side="left", padx=(0, 6))

        classes_shell = self._panel(parent)
        tk.Label(classes_shell, text="Clases", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.classes_text = tk.Label(classes_shell, text="", justify="left", bg=PANEL, fg=MUTED, wraplength=330, font=("Segoe UI", 10))
        self.classes_text.pack(fill="x", padx=12, pady=(0, 12))

        routines_shell = self._panel(parent, pady=(0, 0), expand=True)
        tk.Label(routines_shell, text="Rutinas", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.routines_text = tk.Text(routines_shell, bg=PANEL, fg=MUTED, insertbackground=TEXT, relief="flat", bd=0, wrap="word", height=16, font=("Segoe UI", 9))
        self.routines_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.routines_text.configure(state="disabled")

    def _build_ui_modern(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, foreground=TEXT, fieldbackground=PANEL, rowheight=28, borderwidth=0)
        style.configure("Treeview.Heading", background=PANEL_ALT, foreground=TEXT, font=("Segoe UI Semibold", 9))
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL_ALT, foreground=MUTED, padding=(14, 8), font=("Segoe UI", 9))
        style.map("TNotebook.Tab", background=[("selected", PANEL)], foreground=[("selected", TEXT)])

        header = tk.Frame(self.root, bg=HEADER, highlightthickness=1, highlightbackground=LINE)
        header.pack(fill="x", padx=16, pady=(14, 10))
        header_inner = tk.Frame(header, bg=HEADER)
        header_inner.pack(fill="x", padx=18, pady=14)

        title_block = tk.Frame(header_inner, bg=HEADER)
        title_block.pack(side="left", fill="x", expand=True)
        tk.Label(title_block, text="VIERNES", bg=HEADER, fg=ACCENT, font=("Segoe UI Semibold", 23)).pack(anchor="w")
        self.status_label = tk.Label(title_block, text="Sistema en linea", bg=HEADER, fg=ACCENT2, font=("Segoe UI", 10))
        self.status_label.pack(anchor="w", pady=(2, 0))

        actions = tk.Frame(header_inner, bg=HEADER)
        actions.pack(side="right")
        self.stop_button = tk.Button(
            actions,
            text="DETENER",
            command=self._force_stop,
            bg="#c2413b",
            fg="#ffffff",
            activebackground="#9f312e",
            activeforeground="#ffffff",
            relief="flat",
            bd=0,
            font=("Segoe UI Semibold", 10),
            padx=14,
            pady=8,
            cursor="hand2",
        )
        self.stop_button.pack(side="left", padx=(0, 10))
        for label, command, accent in [
            ("Agenda", self._open_agenda_editor, False),
            ("Clases", self._open_classes_editor, False),
            ("Presupuesto", self._open_budget_editor, False),
            ("Rutinas", self._open_routine_editor, True),
            ("Configurar", self._open_config_center, False),
        ]:
            tk.Button(
                actions,
                text=label,
                command=command,
                bg=ACCENT if accent else PANEL,
                fg=BG if accent else TEXT,
                activebackground=PANEL_ALT,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                font=("Segoe UI Semibold" if accent else "Segoe UI", 10),
                padx=12,
                pady=8,
                cursor="hand2",
            ).pack(side="left", padx=(0, 8))

        main = tk.Frame(self.root, bg=BG)
        main.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        left = tk.Frame(main, bg=BG)
        left.pack(side="left", fill="both", expand=True)
        right = tk.Frame(main, bg=BG, width=420)
        right.pack(side="right", fill="both", padx=(16, 0))
        right.pack_propagate(False)

        avatar_shell = tk.Frame(left, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        avatar_shell.pack(fill="x", pady=(0, 12))
        avatar_row = tk.Frame(avatar_shell, bg=PANEL)
        avatar_row.pack(fill="x", padx=16, pady=16)
        self.avatar = HoloAvatar(avatar_row, width=220, height=220)
        self.avatar.pack(side="left")

        avatar_info = tk.Frame(avatar_row, bg=PANEL)
        avatar_info.pack(side="left", fill="both", expand=True, padx=(18, 0))
        tk.Label(avatar_info, text="Panel operativo", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 15)).pack(anchor="w")
        self.focus_text = tk.Label(
            avatar_info,
            text="Analizando agenda, rutinas y sistema.",
            bg=PANEL,
            fg=MUTED,
            justify="left",
            wraplength=470,
            font=("Segoe UI", 10),
        )
        self.focus_text.pack(anchor="w", fill="x", pady=(8, 12))

        quick_info = tk.Frame(avatar_info, bg=PANEL)
        quick_info.pack(fill="x", pady=(0, 10))
        for text, command_text in [
            ("Informe", "informe del dia"),
            ("Sigue", "que sigue"),
            ("Noticias", "noticias"),
            ("Clima", "clima de hoy"),
        ]:
            tk.Button(
                quick_info,
                text=text,
                command=lambda cmd=command_text: self._submit(cmd),
                bg=PANEL_ALT,
                fg=ACCENT,
                activebackground=LINE,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                font=("Segoe UI Semibold", 9),
                padx=11,
                pady=7,
                cursor="hand2",
            ).pack(side="left", padx=(0, 8))

        stats_row = tk.Frame(avatar_info, bg=PANEL)
        stats_row.pack(fill="x", pady=(2, 0))
        self.metric_agenda = self._metric_card(stats_row, "EVENTOS", "0")
        self.metric_classes = self._metric_card(stats_row, "CLASES", "0")
        self.metric_budget = self._metric_card(stats_row, "BALANCE", "$0")

        self._build_command_bar_modern(avatar_shell)

        convo_shell = tk.Frame(left, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        convo_shell.pack(fill="both", expand=True)
        tk.Label(convo_shell, text="Conversacion", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=14, pady=(12, 6))
        self.log = tk.Text(convo_shell, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, wrap="word", font=("Consolas", 10))
        self.log.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.log.configure(state="disabled")

        self._build_right_panel_modern(right)

    def _build_command_bar_modern(self, parent: tk.Widget) -> None:
        footer = tk.Frame(parent, bg=HEADER, highlightthickness=1, highlightbackground=LINE)
        footer.pack(fill="x", padx=16, pady=(0, 16))

        quick_shell = tk.Frame(footer, bg=HEADER)
        quick_shell.pack(fill="x", padx=12, pady=(10, 7))
        preferred = [
            "Informe del dia",
            "Que sigue",
            "Noticias",
            "Clima de hoy",
            "Mi agenda",
            "Presupuesto",
            "Verificar despertar",
            "Probar despertar",
        ]
        configured = [str(x) for x in self.assistant.config.get("quick_actions", []) if str(x).strip()]
        labels = [x for x in preferred if x in configured]
        labels.extend(x for x in configured if x not in labels)
        for col, label in enumerate(labels[:8]):
            btn = tk.Button(
                quick_shell,
                text=label,
                command=lambda cmd=label: self._submit(cmd),
                bg=PANEL,
                fg=TEXT,
                activebackground=PANEL_ALT,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                font=("Segoe UI", 9),
                padx=8,
                pady=6,
                cursor="hand2",
            )
            btn.grid(row=0, column=col, sticky="ew", padx=(0, 6))
            quick_shell.grid_columnconfigure(col, weight=1)

        entry_shell = tk.Frame(footer, bg=HEADER)
        entry_shell.pack(fill="x", padx=12, pady=(0, 12))
        row = tk.Frame(entry_shell, bg=HEADER)
        row.pack(fill="x")
        self.entry = tk.Entry(row, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, font=("Segoe UI", 12))
        self.entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 10))
        self.entry.bind("<Return>", lambda _e: self._submit())
        self.listen_button = tk.Button(
            row,
            text="Hablar",
            command=self._listen_once,
            bg=ACCENT2,
            fg=BG,
            activebackground=ACCENT,
            activeforeground=BG,
            relief="flat",
            bd=0,
            font=("Segoe UI Semibold", 10),
            padx=14,
            pady=8,
            cursor="hand2",
        )
        self.listen_button.pack(side="right", padx=(0, 10))
        tk.Button(
            row,
            text="Enviar",
            command=self._submit,
            bg=ACCENT,
            fg=BG,
            activebackground=ACCENT2,
            activeforeground=BG,
            relief="flat",
            bd=0,
            font=("Segoe UI Semibold", 10),
            padx=14,
            pady=8,
            cursor="hand2",
        ).pack(side="right")

    def _build_right_panel_modern(self, parent: tk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True)

        today_tab = tk.Frame(notebook, bg=BG)
        system_tab = tk.Frame(notebook, bg=BG)
        routines_tab = tk.Frame(notebook, bg=BG)
        understanding_tab = tk.Frame(notebook, bg=BG)
        analysis_tab = tk.Frame(notebook, bg=BG)
        executions_tab = tk.Frame(notebook, bg=BG)
        remote_tab = tk.Frame(notebook, bg=BG)
        notebook.add(today_tab, text="Hoy")
        notebook.add(system_tab, text="Sistema")
        notebook.add(routines_tab, text="Rutinas")
        notebook.add(understanding_tab, text="Entendimiento")
        notebook.add(analysis_tab, text="Analisis")
        notebook.add(executions_tab, text="Ejecuciones")
        notebook.add(remote_tab, text="Control Remoto")

        overview_shell = self._panel(today_tab, pady=(10, 12))
        tk.Label(overview_shell, text="Resumen", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.summary_text = tk.Label(
            overview_shell,
            text="Sistema listo para agenda, clases, rutinas y presupuesto.",
            justify="left",
            bg=PANEL,
            fg=MUTED,
            wraplength=365,
            font=("Segoe UI", 10),
        )
        self.summary_text.pack(fill="x", padx=12, pady=(0, 12))

        agenda_shell = self._panel(today_tab)
        tk.Label(agenda_shell, text="Agenda de hoy", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.agenda_tree = ttk.Treeview(agenda_shell, columns=("hora", "titulo"), show="headings", height=6)
        self.agenda_tree.heading("hora", text="Hora")
        self.agenda_tree.heading("titulo", text="Titulo")
        self.agenda_tree.column("hora", width=70, anchor="center")
        self.agenda_tree.column("titulo", width=285, anchor="w")
        self.agenda_tree.pack(fill="x", padx=12, pady=(0, 12))

        today_shell = self._panel(today_tab)
        tk.Label(today_shell, text="Estado", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.today_text = tk.Label(today_shell, text="", justify="left", bg=PANEL, fg=MUTED, wraplength=365, font=("Segoe UI", 10))
        self.today_text.pack(fill="x", padx=12, pady=(0, 12))

        classes_shell = self._panel(today_tab, pady=(0, 0))
        tk.Label(classes_shell, text="Clases", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.classes_text = tk.Label(classes_shell, text="", justify="left", bg=PANEL, fg=MUTED, wraplength=365, font=("Segoe UI", 10))
        self.classes_text.pack(fill="x", padx=12, pady=(0, 12))

        budget_shell = self._panel(system_tab, pady=(10, 12))
        tk.Label(budget_shell, text="Presupuesto", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.budget_text = tk.Label(budget_shell, text="", justify="left", bg=PANEL, fg=MUTED, wraplength=365, font=("Segoe UI", 10))
        self.budget_text.pack(fill="x", padx=12, pady=(0, 12))

        system_shell = self._panel(system_tab, pady=(0, 0), expand=True)
        tk.Label(system_shell, text="Autoinicio", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.system_text = tk.Label(system_shell, text="", justify="left", bg=PANEL, fg=MUTED, wraplength=365, font=("Segoe UI", 10))
        self.system_text.pack(fill="x", padx=12, pady=(0, 10))
        system_actions = tk.Frame(system_shell, bg=PANEL)
        system_actions.pack(fill="x", padx=12, pady=(0, 12))
        for label, command_text in [
            ("Activar", "activar modo residente"),
            ("Desactivar", "desactivar modo residente"),
            ("Verificar", "verificar despertar"),
            ("Probar", "probar despertar"),
        ]:
            tk.Button(
                system_actions,
                text=label,
                command=lambda cmd=command_text: self._submit(cmd),
                bg=PANEL_ALT,
                fg=TEXT,
                activebackground=LINE,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                font=("Segoe UI", 9),
                padx=10,
                pady=7,
                cursor="hand2",
            ).pack(side="left", padx=(0, 6))

        routines_shell = self._panel(routines_tab, pady=(10, 0), expand=True)
        tk.Label(routines_shell, text="Linea de tiempo", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.routines_text = tk.Text(routines_shell, bg=PANEL, fg=MUTED, insertbackground=TEXT, relief="flat", bd=0, wrap="word", height=16, font=("Segoe UI", 9))
        self.routines_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.routines_text.configure(state="disabled")

        understanding_shell = self._panel(understanding_tab, pady=(10, 0), expand=True)
        tk.Label(understanding_shell, text="Ultima decision", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.understanding_text = tk.Label(
            understanding_shell,
            text="Sin decisiones recientes.",
            justify="left",
            bg=PANEL,
            fg=MUTED,
            wraplength=365,
            font=("Segoe UI", 10),
        )
        self.understanding_text.pack(fill="x", padx=12, pady=(0, 12))

        analysis_shell = self._panel(analysis_tab, pady=(10, 0), expand=True)
        tk.Label(analysis_shell, text="Simulador inteligente", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.analysis_entry = tk.Entry(analysis_shell, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, font=("Segoe UI", 10))
        self.analysis_entry.pack(fill="x", padx=12, pady=(0, 8), ipady=7)
        analysis_buttons = tk.Frame(analysis_shell, bg=PANEL)
        analysis_buttons.pack(fill="x", padx=12, pady=(0, 10))
        for label, prefix in [("Simular", "simula"), ("Investigar tabla", "investiga"), ("Graficar", "haz grafica de"), ("Reporte", "reporte de")]:
            tk.Button(
                analysis_buttons,
                text=label,
                command=lambda p=prefix: self._run_analysis(p),
                bg=PANEL_ALT,
                fg=TEXT,
                activebackground=LINE,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                font=("Segoe UI", 9),
                padx=10,
                pady=7,
                cursor="hand2",
            ).pack(side="left", padx=(0, 6))
        self.analysis_output = tk.Text(analysis_shell, bg=PANEL, fg=MUTED, insertbackground=TEXT, relief="flat", bd=0, wrap="word", height=7, font=("Segoe UI", 9))
        self.analysis_output.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.analysis_output.configure(state="disabled")
        self.analysis_tree = ttk.Treeview(analysis_shell, columns=("c1", "c2", "c3"), show="headings", height=5)
        self.analysis_tree.pack(fill="x", padx=12, pady=(0, 10))
        self.analysis_chart_label = tk.Label(analysis_shell, text="Sin grafica reciente.", bg=PANEL, fg=MUTED, justify="left", font=("Segoe UI", 9))
        self.analysis_chart_label.pack(fill="x", padx=12, pady=(0, 10))
        self.analysis_reports_text = tk.Label(analysis_shell, text="", bg=PANEL, fg=MUTED, justify="left", wraplength=365, font=("Segoe UI", 9))
        self.analysis_reports_text.pack(fill="x", padx=12, pady=(0, 12))

        executions_shell = self._panel(executions_tab, pady=(10, 0), expand=True)
        tk.Label(executions_shell, text="Recibos y auditoria", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.execution_text = tk.Label(
            executions_shell,
            text="Sin ejecuciones verificadas.",
            justify="left",
            bg=PANEL,
            fg=MUTED,
            wraplength=365,
            font=("Segoe UI", 10),
        )
        self.execution_text.pack(fill="x", padx=12, pady=(0, 12))
        exec_buttons = tk.Frame(executions_shell, bg=PANEL)
        exec_buttons.pack(fill="x", padx=12, pady=(0, 12))
        for label, command_text in [
            ("Ver recibo", "ver recibo de la ultima accion"),
            ("Herramientas", "estado de herramientas"),
            ("Auditar", "audita comandos criticos"),
        ]:
            tk.Button(
                exec_buttons,
                text=label,
                command=lambda cmd=command_text: self._submit(cmd),
                bg=PANEL_ALT,
                fg=TEXT,
                activebackground=LINE,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                font=("Segoe UI", 9),
                padx=10,
                pady=7,
                cursor="hand2",
            ).pack(side="left", padx=(0, 6))

        remote_shell = self._panel(remote_tab, pady=(10, 0), expand=True)
        tk.Label(remote_shell, text="Telegram remoto", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 12)).pack(anchor="w", padx=12, pady=(10, 6))
        self.remote_text = tk.Text(remote_shell, bg=PANEL, fg=MUTED, insertbackground=TEXT, relief="flat", bd=0, wrap="word", height=15, font=("Segoe UI", 9))
        self.remote_text.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.remote_text.configure(state="disabled")
        remote_buttons = tk.Frame(remote_shell, bg=PANEL)
        remote_buttons.pack(fill="x", padx=12, pady=(0, 12))
        for label, command_text in [
            ("Probar Telegram", "probar telegram"),
            ("Probar polling", "probar polling remoto"),
            ("Activar residente", "activar remoto residente"),
            ("Reenviar", "reenviar ultimo resultado remoto"),
            ("Limpiar", "limpiar historial remoto"),
        ]:
            tk.Button(
                remote_buttons,
                text=label,
                command=lambda cmd=command_text: self._submit(cmd),
                bg=PANEL_ALT,
                fg=TEXT,
                activebackground=LINE,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                font=("Segoe UI", 9),
                padx=10,
                pady=7,
                cursor="hand2",
            ).pack(side="left", padx=(0, 6))

    def _config_value(self, path: str, default: object = "") -> object:
        cursor: object = self.assistant.config
        for part in path.split("."):
            if not isinstance(cursor, dict) or part not in cursor:
                return default
            cursor = cursor[part]
        return cursor

    def _add_config_entry(self, parent: tk.Widget, row: int, label: str, key: str, value: object = "") -> None:
        tk.Label(parent, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).grid(row=row, column=0, sticky="w", padx=10, pady=4)
        var = tk.StringVar(value=str(value))
        entry = tk.Entry(
            parent,
            textvariable=var,
            bg=BG,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI", 10),
            show="*" if "token" in key else "",
        )
        entry.grid(row=row, column=1, sticky="ew", padx=10, pady=4, ipady=6)
        self.config_vars[key] = var

    def _add_config_check(self, parent: tk.Widget, row: int, label: str, key: str, value: object = False) -> None:
        var = tk.BooleanVar(value=bool(value))
        check = tk.Checkbutton(
            parent,
            text=label,
            variable=var,
            bg=PANEL,
            fg=TEXT,
            selectcolor=BG,
            activebackground=PANEL,
            activeforeground=TEXT,
            font=("Segoe UI", 9),
        )
        check.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        self.config_vars[key] = var

    def _config_section(self, parent: tk.Widget, title: str) -> tk.Frame:
        shell = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        shell.pack(fill="x", padx=12, pady=(10, 0))
        shell.grid_columnconfigure(1, weight=1)
        tk.Label(shell, text=title, bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 11)).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 8))
        return shell

    def _scrollable_config_tab(self, parent: tk.Widget) -> tk.Frame:
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0)
        scroll = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas, bg=BG)
        window_id = canvas.create_window((0, 0), window=body, anchor="nw")

        def _update_scrollregion(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _fit_width(event) -> None:
            canvas.itemconfigure(window_id, width=max(1, event.width))

        def _on_mousewheel(event) -> None:
            delta = 0
            if hasattr(event, "delta") and event.delta:
                delta = -1 * int(event.delta / 120)
            elif getattr(event, "num", None) == 4:
                delta = -1
            elif getattr(event, "num", None) == 5:
                delta = 1
            if delta:
                canvas.yview_scroll(delta, "units")

        def _bind_wheel(_event=None) -> None:
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", _on_mousewheel)
            canvas.bind_all("<Button-5>", _on_mousewheel)

        def _unbind_wheel(_event=None) -> None:
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        body.bind("<Configure>", _update_scrollregion)
        canvas.bind("<Configure>", _fit_width)
        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)
        body.bind("<Enter>", _bind_wheel)
        body.bind("<Leave>", _unbind_wheel)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return body

    def _open_config_center(self) -> None:
        if self.config_window is not None and self.config_window.winfo_exists():
            self.config_window.lift()
            return
        self.config_vars = {}
        self.config_texts = {}
        win = tk.Toplevel(self.root)
        win.title("Centro de control de Viernes")
        win.geometry("980x760")
        win.configure(bg=BG)
        self.config_window = win

        header = tk.Frame(win, bg=HEADER, highlightthickness=1, highlightbackground=LINE)
        header.pack(fill="x", padx=14, pady=(14, 10))
        tk.Label(header, text="Centro de control", bg=HEADER, fg=ACCENT, font=("Segoe UI Semibold", 16)).pack(anchor="w", padx=14, pady=(12, 2))
        self.config_status_label = tk.Label(header, text="Edite, valide y guarde sin tocar JSON manualmente.", bg=HEADER, fg=MUTED, justify="left", font=("Segoe UI", 9))
        self.config_status_label.pack(anchor="w", fill="x", padx=14, pady=(0, 12))

        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=14)
        tab_shells = {name: tk.Frame(notebook, bg=BG) for name in ("General", "Sistema", "Inteligencia", "Voz y Telegram", "Avanzado")}
        for name, tab in tab_shells.items():
            notebook.add(tab, text=name)
        tabs = {name: self._scrollable_config_tab(tab) for name, tab in tab_shells.items()}

        self._build_config_general_tab(tabs["General"])
        self._build_config_system_tab(tabs["Sistema"])
        self._build_config_intelligence_tab(tabs["Inteligencia"])
        self._build_config_voice_telegram_tab(tabs["Voz y Telegram"])
        self._build_config_advanced_tab(tabs["Avanzado"])

        actions = tk.Frame(win, bg=BG)
        actions.pack(fill="x", padx=14, pady=14)
        tk.Button(actions, text="Guardar configuracion", command=self._save_config_center, bg=ACCENT, fg=BG, relief="flat", bd=0, font=("Segoe UI Semibold", 10), padx=14, pady=10).pack(side="left")
        tk.Button(actions, text="Validar sin guardar", command=self._validate_config_center, bg=PANEL, fg=TEXT, relief="flat", bd=0, font=("Segoe UI", 10), padx=14, pady=10).pack(side="left", padx=(10, 0))
        tk.Button(actions, text="Cerrar", command=win.destroy, bg=PANEL, fg=TEXT, relief="flat", bd=0, font=("Segoe UI", 10), padx=14, pady=10).pack(side="right")

    def _build_config_general_tab(self, tab: tk.Frame) -> None:
        section = self._config_section(tab, "General")
        self._add_config_entry(section, 1, "Nombre", "assistant_name", self._config_value("assistant_name", "Viernes"))
        self._add_config_entry(section, 2, "Zona horaria", "timezone", self._config_value("timezone", "America/Mexico_City"))
        self._add_config_entry(section, 3, "Ciudad", "default_city", self._config_value("default_city", "Colima, Colima, Mexico"))
        self._add_config_entry(section, 4, "Latitud clima", "weather_lat", self._config_value("weather_lat", ""))
        self._add_config_entry(section, 5, "Longitud clima", "weather_lon", self._config_value("weather_lon", ""))
        self._add_config_entry(section, 6, "Minutos de gracia", "event_grace_minutes", self._config_value("event_grace_minutes", 12))
        self._add_config_entry(section, 7, "Pausa al detener", "scheduler_stop_pause_minutes", self._config_value("scheduler_stop_pause_minutes", 10))
        self._add_config_entry(section, 8, "Anti-duplicados", "scheduler_duplicate_window_minutes", self._config_value("scheduler_duplicate_window_minutes", 15))

        quick = self._config_section(tab, "Acciones rapidas")
        quick_text = tk.Text(quick, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, height=9, wrap="word", font=("Segoe UI", 10))
        quick_text.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10))
        quick_text.insert("1.0", "\n".join(str(x) for x in self.assistant.config.get("quick_actions", [])))
        self.config_texts["quick_actions"] = quick_text

        budget = self._config_section(tab, "Presupuesto")
        self._add_config_entry(budget, 1, "Limite de presupuesto", "budget_limit", get_balance().get("budget_limit", 0))
        tk.Button(budget, text="Guardar limite", command=self._save_budget_limit_from_config, bg=PANEL_ALT, fg=TEXT, relief="flat", bd=0, padx=12, pady=8).grid(row=2, column=1, sticky="e", padx=10, pady=(4, 10))

    def _build_config_system_tab(self, tab: tk.Frame) -> None:
        section = self._config_section(tab, "Autoarranque y sistema")
        self._add_config_check(section, 1, "Iniciar Viernes al iniciar sesion", "automation.startup_enabled", self._config_value("automation.startup_enabled", True))
        self._add_config_check(section, 2, "Rutina matutina desde suspension", "morning_wake_enabled", self._config_value("morning_wake_enabled", True))
        self._add_config_entry(section, 3, "Hora de rutina matutina", "automation.morning_wake_time", self._config_value("automation.morning_wake_time", "07:30"))
        self._add_config_entry(section, 4, "MAC Wake-on-LAN", "wol_mac", self._config_value("wol_mac", ""))
        buttons = tk.Frame(section, bg=PANEL)
        buttons.grid(row=5, column=1, sticky="e", padx=10, pady=(6, 10))
        tk.Button(buttons, text="Guardar y reprogramar", command=self._save_wake_from_config, bg=ACCENT, fg=BG, relief="flat", bd=0, padx=12, pady=8).pack(side="left")
        tk.Button(buttons, text="Verificar", command=lambda: self._submit("verificar despertar"), bg=PANEL_ALT, fg=TEXT, relief="flat", bd=0, padx=12, pady=8).pack(side="left", padx=(8, 0))

        energy = self._config_section(tab, "Energia y bloqueo")
        status = self.assistant.system_status_snapshot()
        last_wake = self.assistant.state.get("last_wake_attempt", {}) if isinstance(self.assistant.state.get("last_wake_attempt", {}), dict) else {}
        pending = self.assistant.state.get("pending_morning_interaction", {}) if isinstance(self.assistant.state.get("pending_morning_interaction", {}), dict) else {}
        text = (
            f"Tarea: {status.get('task', 'desconocida')}\n"
            f"Proxima ejecucion: {status.get('next_run', 'desconocida')}\n"
            f"Ultimo despertar: {last_wake.get('timestamp', 'sin registro')}\n"
            f"Sesion ultimo despertar: {last_wake.get('session_state', 'desconocida')}\n"
            f"Rutina pendiente al desbloquear: {'si' if pending else 'no'}\n"
            "Modo seguro: Viernes puede despertar desde suspension, pero no desbloquea Windows ni guarda contrasenas."
        )
        tk.Label(energy, text=text, bg=PANEL, fg=MUTED, justify="left", wraplength=820, font=("Segoe UI", 9)).grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))
        energy_buttons = tk.Frame(energy, bg=PANEL)
        energy_buttons.grid(row=2, column=1, sticky="e", padx=10, pady=(4, 10))
        tk.Button(energy_buttons, text="Diagnostico energia", command=lambda: self._submit("diagnostico energia"), bg=PANEL_ALT, fg=TEXT, relief="flat", bd=0, padx=12, pady=8).pack(side="left")
        tk.Button(energy_buttons, text="Probar en 2 min", command=lambda: self._submit("probar despertar en 2 minutos"), bg=PANEL_ALT, fg=TEXT, relief="flat", bd=0, padx=12, pady=8).pack(side="left", padx=(8, 0))
        tk.Button(energy_buttons, text="Reparar", command=lambda: self._submit("reparar despertar"), bg=ACCENT, fg=BG, relief="flat", bd=0, padx=12, pady=8).pack(side="left", padx=(8, 0))

        classes = self._config_section(tab, "Clases semanales")
        schedule = dict(self.assistant.config.get("class_schedule", {}))
        weekdays = [("monday", "Lunes"), ("tuesday", "Martes"), ("wednesday", "Miercoles"), ("thursday", "Jueves"), ("friday", "Viernes"), ("saturday", "Sabado"), ("sunday", "Domingo")]
        for row, (day, label) in enumerate(weekdays, start=1):
            self._add_config_entry(classes, row, label, f"class_schedule.{day}", ", ".join(schedule.get(day, [])))

    def _build_config_intelligence_tab(self, tab: tk.Frame) -> None:
        ai = self._config_section(tab, "IA local")
        self._add_config_check(ai, 1, "IA local activa", "ai_enabled", self._config_value("ai_enabled", True))
        self._add_config_entry(ai, 2, "URL Ollama", "ai_base_url", self._config_value("ai_base_url", "http://localhost:11434"))
        self._add_config_entry(ai, 3, "Modelo", "ai_model", self._config_value("ai_model", "llama3.2"))

        proactive = self._config_section(tab, "Proactividad")
        self._add_config_check(proactive, 1, "Proactividad activa", "proactivity.enabled", self._config_value("proactivity.enabled", True))
        self._add_config_entry(proactive, 2, "Modo", "proactivity.mode", self._config_value("proactivity.mode", "conservative"))
        self._add_config_entry(proactive, 3, "Cooldown minutos", "proactivity.interval_minutes", self._config_value("proactivity.interval_minutes", 120))
        self._add_config_entry(proactive, 4, "Ventana minutos", "proactivity.lookahead_minutes", self._config_value("proactivity.lookahead_minutes", 120))
        self._add_config_entry(proactive, 5, "Max por tick", "proactivity.max_per_tick", self._config_value("proactivity.max_per_tick", 1))

        ambient = self._config_section(tab, "Conversacion ambiental")
        self._add_config_check(ambient, 1, "Conversacion ambiental activa", "ambient_companion.enabled", self._config_value("ambient_companion.enabled", True))
        self._add_config_entry(ambient, 2, "Intervalo minutos", "ambient_companion.interval_minutes", self._config_value("ambient_companion.interval_minutes", 90))
        self._add_config_entry(ambient, 3, "Inicio", "ambient_companion.wake_time", self._config_value("ambient_companion.wake_time", "07:30"))
        self._add_config_entry(ambient, 4, "Fin", "ambient_companion.sleep_time", self._config_value("ambient_companion.sleep_time", "22:30"))
        self._add_config_check(ambient, 5, "Temas proactivos de conversacion", "conversation.proactive_topics_enabled", self._config_value("conversation.proactive_topics_enabled", True))

        analysis = self._config_section(tab, "Analisis")
        self._add_config_check(analysis, 1, "Analisis activo", "analysis.enabled", self._config_value("analysis.enabled", True))
        self._add_config_check(analysis, 2, "Guardar reportes", "analysis.save_reports", self._config_value("analysis.save_reports", True))
        self._add_config_check(analysis, 3, "Permitir investigacion web", "analysis.allow_web_research", self._config_value("analysis.allow_web_research", True))
        self._add_config_entry(analysis, 4, "Max filas", "analysis.max_rows", self._config_value("analysis.max_rows", 20))
        self._add_config_entry(analysis, 5, "Motor graficas", "analysis.chart_backend", self._config_value("analysis.chart_backend", "matplotlib"))

    def _build_config_voice_telegram_tab(self, tab: tk.Frame) -> None:
        voice = self._config_section(tab, "Voz")
        self._add_config_check(voice, 1, "Voz activa", "voice_enabled", self._config_value("voice_enabled", True))
        self._add_config_entry(voice, 2, "Tipo TTS", "tts_type", self._config_value("tts_type", "edge"))
        self._add_config_entry(voice, 3, "Velocidad", "tts_rate", self._config_value("tts_rate", 165))
        self._add_config_entry(voice, 4, "Hotkey", "push_to_talk_hotkey", self._config_value("push_to_talk_hotkey", "left alt"))
        tk.Button(voice, text="Probar voz", command=self._test_voice_from_config, bg=PANEL_ALT, fg=TEXT, relief="flat", bd=0, padx=12, pady=8).grid(row=5, column=1, sticky="e", padx=10, pady=(4, 10))

        telegram = self._config_section(tab, "Telegram")
        cfg = self.assistant.config.get("telegram", {}) if isinstance(self.assistant.config.get("telegram", {}), dict) else {}
        self._add_config_check(telegram, 1, "Telegram activo", "telegram.enabled", cfg.get("enabled", False))
        self._add_config_entry(telegram, 2, "Token nuevo (dejar vacio para conservar)", "telegram.token", "")
        self._add_config_entry(telegram, 3, "Chat ID", "telegram.chat_id", cfg.get("chat_id", self.assistant.config.get("telegram_chat_id", "")))
        token_var = self.config_vars.get("telegram.token")
        if token_var is not None:
            # The token entry is intentionally blank; Tkinter masking is applied after creation by row lookup.
            pass
        buttons = tk.Frame(telegram, bg=PANEL)
        buttons.grid(row=4, column=1, sticky="e", padx=10, pady=(6, 10))
        tk.Button(buttons, text="Guardar Telegram", command=self._save_config_center, bg=ACCENT, fg=BG, relief="flat", bd=0, padx=12, pady=8).pack(side="left")
        tk.Button(buttons, text="Probar", command=self._test_telegram_from_config, bg=PANEL_ALT, fg=TEXT, relief="flat", bd=0, padx=12, pady=8).pack(side="left", padx=(8, 0))

        remote = self._config_section(tab, "Control remoto seguro")
        self._add_config_check(remote, 1, "Control remoto activo", "remote_control.enabled", self._config_value("remote_control.enabled", False))
        self._add_config_entry(remote, 2, "Chats permitidos", "remote_control.allowed_chat_ids", ", ".join(self._config_value("remote_control.allowed_chat_ids", [])))
        self._add_config_entry(remote, 3, "Owners", "remote_control.owner_chat_ids", ", ".join(self._config_value("remote_control.owner_chat_ids", [])))
        self._add_config_entry(remote, 4, "Trusted", "remote_control.trusted_chat_ids", ", ".join(self._config_value("remote_control.trusted_chat_ids", [])))
        self._add_config_entry(remote, 5, "Solo lectura", "remote_control.read_only_chat_ids", ", ".join(self._config_value("remote_control.read_only_chat_ids", [])))
        self._add_config_check(remote, 6, "Confirmar cambios", "remote_control.require_confirmation", self._config_value("remote_control.require_confirmation", True))
        self._add_config_check(remote, 7, "Enviar reportes/PNG", "remote_control.send_artifacts", self._config_value("remote_control.send_artifacts", True))
        self._add_config_entry(remote, 8, "Intervalo polling", "remote_control.poll_interval_seconds", self._config_value("remote_control.poll_interval_seconds", 5))
        self._add_config_entry(remote, 9, "Limite historial", "remote_control.history_limit", self._config_value("remote_control.history_limit", 100))
        self._add_config_check(remote, 10, "Ignorar backlog al iniciar", "remote_control.drop_pending_on_start", self._config_value("remote_control.drop_pending_on_start", True))
        self._add_config_entry(remote, 11, "Intenciones bloqueadas", "remote_control.blocked_intents", ", ".join(self._config_value("remote_control.blocked_intents", [])))
        self._add_config_check(remote, 12, "Adaptador de llamadas", "remote_calls.enabled", self._config_value("remote_calls.enabled", False))
        remote_buttons = tk.Frame(remote, bg=PANEL)
        remote_buttons.grid(row=13, column=1, sticky="e", padx=10, pady=(6, 10))
        tk.Button(remote_buttons, text="Activar remoto", command=lambda: self._submit("activar control remoto telegram"), bg=ACCENT, fg=BG, relief="flat", bd=0, padx=12, pady=8).pack(side="left")
        tk.Button(remote_buttons, text="Probar remoto", command=lambda: self._submit("probar control remoto"), bg=PANEL_ALT, fg=TEXT, relief="flat", bd=0, padx=12, pady=8).pack(side="left", padx=(8, 0))

    def _build_config_advanced_tab(self, tab: tk.Frame) -> None:
        section = self._config_section(tab, "JSON avanzado validado")
        text = tk.Text(section, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, height=25, wrap="none", font=("Consolas", 9))
        text.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=(0, 10))
        section.grid_rowconfigure(1, weight=1)
        text.insert("1.0", json.dumps(self.assistant.config_snapshot(), ensure_ascii=False, indent=2))
        self.config_texts["advanced_json"] = text
        tk.Button(section, text="Aplicar JSON validado", command=self._apply_advanced_config_json, bg=ACCENT, fg=BG, relief="flat", bd=0, padx=12, pady=8).grid(row=2, column=1, sticky="e", padx=10, pady=(0, 10))

    def _collect_config_patch(self) -> dict[str, object]:
        patch: dict[str, object] = {}

        def put(path: str, value: object) -> None:
            cursor = patch
            parts = path.split(".")
            for part in parts[:-1]:
                child = cursor.setdefault(part, {})
                if not isinstance(child, dict):
                    child = {}
                    cursor[part] = child
                cursor = child
            cursor[parts[-1]] = value

        for key, var in self.config_vars.items():
            if key == "budget_limit":
                continue
            value: object = var.get()
            if key == "telegram.token" and not str(value).strip():
                continue
            put(key, value)
        quick_text = self.config_texts.get("quick_actions")
        if quick_text is not None:
            put("quick_actions", quick_text.get("1.0", "end").strip().splitlines())
        return patch

    def _format_config_result(self, result) -> str:
        if result.valid:
            extra = (" Advertencias: " + " ".join(result.warnings)) if result.warnings else ""
            return "Configuracion valida." + extra
        return "Errores: " + " ".join(result.errors)

    def _validate_config_center(self) -> None:
        result = self.assistant._config_manager().validate_patch(self._collect_config_patch(), base_config=self.assistant.config)
        self.config_status_label.config(text=self._format_config_result(result), fg=ACCENT2 if result.valid else "#ff8a80")

    def _save_config_center(self) -> None:
        patch = self._collect_config_patch()
        automation = patch.get("automation", {}) if isinstance(patch.get("automation", {}), dict) else {}
        startup_enabled = bool(automation.get("startup_enabled", self.assistant.config.get("automation", {}).get("startup_enabled", False)))
        morning_enabled = bool(patch.get("morning_wake_enabled", self.assistant.config.get("morning_wake_enabled", False)))
        wake_time = str(automation.get("morning_wake_time", self.assistant.config.get("automation", {}).get("morning_wake_time", "07:30"))).strip()
        # These options have a Windows side effect. Let the verified integration persist them.
        automation.pop("startup_enabled", None)
        automation.pop("morning_wake_time", None)
        if automation:
            patch["automation"] = automation
        else:
            patch.pop("automation", None)
        patch.pop("morning_wake_enabled", None)
        result = self.assistant.apply_gui_config_patch(patch)
        self.config_status_label.config(text=self._format_config_result(result), fg=ACCENT2 if result.valid else "#ff8a80")
        if result.valid:
            system_message = self.assistant.apply_resident_config_from_gui(startup_enabled, morning_enabled, wake_time)
            self.config_status_label.config(text=system_message, fg=ACCENT2 if "verificados" in system_message else "#ffcc66")
            self._refresh_dashboard()

    def _save_wake_from_config(self) -> None:
        wake_time = str(self.config_vars["automation.morning_wake_time"].get()).strip()
        message = self.assistant.apply_wake_config_from_gui(wake_time)
        self.config_status_label.config(text=message, fg=ACCENT2 if "verificada" in message else "#ffcc66")
        self._refresh_dashboard()

    def _test_voice_from_config(self) -> None:
        self._save_config_center()
        try:
            self.assistant.voice.speak("Prueba de voz de Viernes.")
            self.config_status_label.config(text="Prueba de voz enviada.", fg=ACCENT2)
        except Exception as exc:
            self.config_status_label.config(text=f"No pude probar la voz: {exc}", fg="#ff8a80")

    def _test_telegram_from_config(self) -> None:
        self._save_config_center()
        self._submit("probar telegram")

    def _save_budget_limit_from_config(self) -> None:
        amount = parse_amount(str(self.config_vars.get("budget_limit").get()))
        if amount is None:
            self.config_status_label.config(text="Limite de presupuesto invalido.", fg="#ff8a80")
            return
        result = set_budget_limit(amount)
        self.assistant._emit(f"Limite de presupuesto guardado: ${result['budget_limit']:.2f}.")
        self._refresh_dashboard()

    def _apply_advanced_config_json(self) -> None:
        text = self.config_texts["advanced_json"].get("1.0", "end").strip()
        try:
            patch = json.loads(text)
        except json.JSONDecodeError as exc:
            self.config_status_label.config(text=f"JSON invalido: {exc}", fg="#ff8a80")
            return
        if isinstance(patch, dict) and isinstance(patch.get("telegram"), dict):
            token = str(patch["telegram"].get("token", "") or "")
            current_token = ""
            current_telegram = self.assistant.config.get("telegram", {})
            if isinstance(current_telegram, dict):
                current_token = str(current_telegram.get("token", "") or "")
            if "*" in token and current_token:
                patch["telegram"]["token"] = current_token
        result = self.assistant.apply_gui_config_patch(patch)
        self.config_status_label.config(text=self._format_config_result(result), fg=ACCENT2 if result.valid else "#ff8a80")
        if result.valid:
            self.assistant._emit("JSON avanzado aplicado con respaldo.")
            self._refresh_dashboard()

    def _routine_default_value(self, cfg: dict[str, object], index: int, key: str, default: str = "") -> str:
        reminders = list(cfg.get("reminders", [])) if isinstance(cfg.get("reminders", []), list) else []
        if index < len(reminders) and isinstance(reminders[index], dict):
            return str(reminders[index].get(key, default))
        return default

    def _add_routine_field(self, parent: tk.Widget, row: int, label: str, field_id: str, value: str) -> tk.Entry:
        tk.Label(parent, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).grid(row=row, column=0, sticky="w", padx=10, pady=4)
        entry = tk.Entry(parent, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, font=("Segoe UI", 10), width=44)
        entry.grid(row=row, column=1, sticky="ew", padx=10, pady=4, ipady=6)
        entry.insert(0, value)
        if not hasattr(self, "routine_entries"):
            self.routine_entries = {}
        self.routine_entries[field_id] = entry
        return entry

    def _build_routine_section(self, parent: tk.Widget, title: str) -> tk.Frame:
        shell = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground="#1f3a52")
        shell.pack(fill="x", padx=12, pady=(0, 12))
        shell.grid_columnconfigure(1, weight=1)
        tk.Label(shell, text=title, bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 11)).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(10, 8))
        return shell

    def _build_day_routine_panel(self, parent: tk.Frame, day_key: str, day_cfg: dict[str, object]) -> None:
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_columnconfigure(2, weight=3)
        enabled_var = tk.BooleanVar(value=bool(day_cfg.get("enabled", True)))
        tk.Checkbutton(
            parent,
            text="Rutina activa",
            variable=enabled_var,
            bg=BG,
            fg=TEXT,
            selectcolor=PANEL,
            activebackground=BG,
            activeforeground=TEXT,
            font=("Segoe UI", 10),
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=10, pady=(8, 6))

        tk.Label(parent, text="Hora", bg=BG, fg=MUTED, font=("Segoe UI Semibold", 9)).grid(row=1, column=0, sticky="w", padx=10)
        tk.Label(parent, text="Mensaje", bg=BG, fg=MUTED, font=("Segoe UI Semibold", 9)).grid(row=1, column=1, columnspan=2, sticky="w", padx=10)

        reminders_frame = tk.Frame(parent, bg=BG)
        reminders_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=8)
        reminders_frame.grid_columnconfigure(1, weight=1)

        reminder_rows: list[dict[str, object]] = []
        reminders = list(day_cfg.get("reminders", [])) if isinstance(day_cfg.get("reminders", []), list) else []
        if not reminders:
            reminders = [{"id": new_reminder_id(), "time": "", "message": ""}]

        def refresh_reminder_rows() -> None:
            for child in reminders_frame.winfo_children():
                child.destroy()
            reminder_rows.clear()
            for index, item in enumerate(reminders):
                if not isinstance(item, dict):
                    continue
                row_frame = tk.Frame(reminders_frame, bg=BG)
                row_frame.grid(row=index, column=0, columnspan=3, sticky="ew", pady=2)
                row_frame.grid_columnconfigure(1, weight=1)
                time_entry = tk.Entry(row_frame, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, font=("Segoe UI", 10), width=8)
                time_entry.grid(row=0, column=0, sticky="w", padx=(2, 8), ipady=5)
                time_entry.insert(0, str(item.get("time", "") or ""))
                message_entry = tk.Entry(row_frame, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, font=("Segoe UI", 10))
                message_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8), ipady=5)
                message_entry.insert(0, str(item.get("message", "") or ""))

                def remove_row(reminder_id: str = str(item.get("id", "") or "")) -> None:
                    reminders[:] = [row for row in reminders if str(row.get("id", "")) != reminder_id]
                    if not reminders:
                        reminders.append({"id": new_reminder_id(), "time": "", "message": ""})
                    refresh_reminder_rows()

                tk.Button(
                    row_frame,
                    text="Eliminar",
                    command=remove_row,
                    bg=PANEL,
                    fg=MUTED,
                    relief="flat",
                    bd=0,
                    font=("Segoe UI", 9),
                    padx=8,
                    pady=4,
                ).grid(row=0, column=2, sticky="e")
                reminder_rows.append(
                    {
                        "id": str(item.get("id", "") or new_reminder_id()),
                        "time_entry": time_entry,
                        "message_entry": message_entry,
                    }
                )

        def add_reminder_row() -> None:
            reminders.append({"id": new_reminder_id(), "time": "", "message": ""})
            refresh_reminder_rows()

        refresh_reminder_rows()
        tk.Button(
            parent,
            text="+ Agregar recordatorio",
            command=add_reminder_row,
            bg=PANEL,
            fg=ACCENT,
            relief="flat",
            bd=0,
            font=("Segoe UI", 9),
            padx=10,
            pady=6,
        ).grid(row=3, column=0, columnspan=3, sticky="w", padx=10, pady=(4, 8))

        extras = tk.Frame(parent, bg=PANEL, highlightthickness=1, highlightbackground="#1f3a52")
        extras.grid(row=4, column=0, columnspan=3, sticky="ew", padx=10, pady=(0, 10))
        extras.grid_columnconfigure(1, weight=1)
        row_offset = 0

        def add_extra_field(label: str, key: str, default: str = "") -> tk.Entry:
            nonlocal row_offset
            row_offset += 1
            value = default
            if key in day_cfg:
                value = str(day_cfg.get(key, "") or "")
            elif "." in key:
                section, subkey = key.split(".", 1)
                section_value = day_cfg.get(section, {})
                if isinstance(section_value, dict):
                    value = str(section_value.get(subkey, "") or "")
            return self._add_routine_field(extras, row_offset, label, f"{day_key}:{key}", value)

        bath = dict(day_cfg.get("bath_followup", {})) if isinstance(day_cfg.get("bath_followup", {}), dict) else {}
        add_extra_field("Bano desde", "bath_followup.start", str(bath.get("start", "")))
        add_extra_field("Bano hasta", "bath_followup.stop", str(bath.get("stop", "")))
        add_extra_field("Repetir cada minutos", "bath_followup.repeat_minutes", str(bath.get("repeat_minutes", 20)))
        add_extra_field("Mensaje bano", "bath_followup.message", str(bath.get("message", "")))

        if day_key == "monday":
            add_extra_field("Hora de salida", "leave_time", str(day_cfg.get("leave_time", "16:50")))
            add_extra_field("Mensaje al llegar", "arrival_message", str(day_cfg.get("arrival_message", "")))
            window = day_cfg.get("expected_arrival_window", ["17:00", "17:30"])
            if isinstance(window, list) and window:
                add_extra_field("Ventana llegada desde", "expected_arrival_window.0", str(window[0]))
                if len(window) > 1:
                    add_extra_field("Ventana llegada hasta", "expected_arrival_window.1", str(window[1]))
        if day_key == "thursday":
            add_extra_field("Hora real de salida", "leave_time", str(day_cfg.get("leave_time", "11:00")))
        if day_key == "friday":
            add_extra_field("Hora real de salida", "leave_time", str(day_cfg.get("leave_time", "16:45")))
            add_extra_field("Maleta", "packing_time", str(day_cfg.get("packing_time", "14:30")))
            add_extra_field("Mensaje maleta", "packing_message", str(day_cfg.get("packing_message", "")))
            add_extra_field("Deberes", "chores_time", str(day_cfg.get("chores_time", "15:15")))
            add_extra_field("Mensaje deberes", "chores_message", str(day_cfg.get("chores_message", "")))
            add_extra_field("Cortar despues de", "stop_all_after", str(day_cfg.get("stop_all_after", "16:45")))

        if not hasattr(self, "routine_day_panels"):
            self.routine_day_panels = {}
        self.routine_day_panels[day_key] = {
            "enabled_var": enabled_var,
            "reminder_rows": reminder_rows,
            "reminders": reminders,
            "refresh": refresh_reminder_rows,
        }

    def _open_routine_editor(self) -> None:
        if self.routine_window is not None and self.routine_window.winfo_exists():
            self.routine_window.lift()
            return

        snap = self.assistant.get_routine_snapshot()
        self.routine_entries = {}
        self.routine_day_panels = {}

        win = tk.Toplevel(self.root)
        win.title("Rutinas de Viernes")
        win.geometry("980x860")
        win.configure(bg=BG)
        self.routine_window = win

        outer = tk.Frame(win, bg=BG)
        outer.pack(fill="both", expand=True)
        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)

        style = ttk.Style()
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=TEXT, padding=[12, 6])
        style.map("TNotebook.Tab", background=[("selected", ACCENT)], foreground=[("selected", BG)])

        for day_key in WEEKDAY_KEYS:
            tab = tk.Frame(notebook, bg=BG)
            notebook.add(tab, text=WEEKDAY_LABELS.get(day_key, day_key))
            canvas = tk.Canvas(tab, bg=BG, highlightthickness=0)
            scroll = tk.Scrollbar(tab, orient="vertical", command=canvas.yview)
            body = tk.Frame(canvas, bg=BG)
            body.bind("<Configure>", lambda _e, c=canvas: c.configure(scrollregion=c.bbox("all")))
            canvas.create_window((0, 0), window=body, anchor="nw", width=900)
            canvas.configure(yscrollcommand=scroll.set)
            canvas.pack(side="left", fill="both", expand=True)
            scroll.pack(side="right", fill="y")
            self._build_day_routine_panel(body, day_key, snap.get(day_key, {}))

        actions = tk.Frame(win, bg=BG)
        actions.pack(fill="x", padx=12, pady=(0, 14))
        tk.Button(
            actions,
            text="Guardar rutina",
            command=self._save_routine_editor,
            bg=ACCENT,
            fg=BG,
            relief="flat",
            bd=0,
            font=("Segoe UI Semibold", 10),
            padx=14,
            pady=10,
        ).pack(side="left")
        tk.Button(
            actions,
            text="Cerrar",
            command=win.destroy,
            bg=PANEL,
            fg=TEXT,
            relief="flat",
            bd=0,
            font=("Segoe UI", 10),
            padx=14,
            pady=10,
        ).pack(side="left", padx=(10, 0))

    def _collect_routine_editor_payload(self) -> dict[str, dict[str, object]]:
        payload: dict[str, dict[str, object]] = {}
        for day_key, panel in getattr(self, "routine_day_panels", {}).items():
            day_payload: dict[str, object] = {
                "enabled": bool(panel["enabled_var"].get()),
                "reminders": [],
            }
            for row in panel["reminder_rows"]:
                day_payload["reminders"].append(
                    {
                        "id": row["id"],
                        "time": str(row["time_entry"].get()).strip(),
                        "message": str(row["message_entry"].get()).strip(),
                    }
                )
            prefix = f"{day_key}:"
            for field_id, entry in self.routine_entries.items():
                if not field_id.startswith(prefix):
                    continue
                raw_key = field_id[len(prefix):]
                value = entry.get().strip()
                if raw_key.startswith("bath_followup."):
                    bath = day_payload.setdefault("bath_followup", {})
                    if isinstance(bath, dict):
                        bath[raw_key.split(".", 1)[1]] = value
                elif raw_key.startswith("expected_arrival_window."):
                    window = day_payload.setdefault("expected_arrival_window", ["", ""])
                    if not isinstance(window, list):
                        window = ["", ""]
                    index = int(raw_key.split(".", 1)[1])
                    while len(window) <= index:
                        window.append("")
                    window[index] = value
                    day_payload["expected_arrival_window"] = window
                else:
                    day_payload[raw_key] = value
            bath = day_payload.get("bath_followup", {})
            if isinstance(bath, dict) and bath.get("repeat_minutes"):
                try:
                    bath["repeat_minutes"] = int(str(bath.get("repeat_minutes", "20") or "20"))
                except ValueError:
                    bath["repeat_minutes"] = 20
            if day_key == "monday":
                day_payload.setdefault("skip_morning_routine", True)
                day_payload.setdefault("skip_recurring_reminders", True)
                day_payload.setdefault("attendance_on_arrival", True)
            payload[day_key] = day_payload
        return payload

    def _save_routine_editor(self) -> None:
        payload = {"days": self._collect_routine_editor_payload()}
        self.assistant.update_routines_from_editor(payload)
        if self.routine_window is not None and self.routine_window.winfo_exists():
            self.routine_window.destroy()
            self.routine_window = None
        self._refresh_dashboard()

    def _open_agenda_editor(self) -> None:
        if self.agenda_window is not None and self.agenda_window.winfo_exists():
            self.agenda_window.lift()
            self._refresh_agenda_editor()
            return

        win = tk.Toplevel(self.root)
        win.title("Agenda")
        win.geometry("860x620")
        win.configure(bg=BG)
        self.agenda_window = win

        shell = tk.Frame(win, bg=BG)
        shell.pack(fill="both", expand=True, padx=16, pady=16)
        tk.Label(shell, text="Gestor de agenda", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(0, 10))

        form = tk.Frame(shell, bg=PANEL, highlightthickness=1, highlightbackground="#1f3a52")
        form.pack(fill="x")
        tk.Label(form, text="Titulo", bg=PANEL, fg=MUTED).grid(row=1, column=0, sticky="w", padx=10, pady=6)
        self.agenda_title_entry = tk.Entry(form, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0)
        self.agenda_title_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=6, ipady=6)
        tk.Label(form, text="Fecha (YYYY-MM-DD)", bg=PANEL, fg=MUTED).grid(row=2, column=0, sticky="w", padx=10, pady=6)
        self.agenda_date_entry = tk.Entry(form, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0)
        self.agenda_date_entry.grid(row=2, column=1, sticky="ew", padx=10, pady=6, ipady=6)
        tk.Label(form, text="Hora (HH:MM)", bg=PANEL, fg=MUTED).grid(row=3, column=0, sticky="w", padx=10, pady=6)
        self.agenda_time_entry = tk.Entry(form, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0)
        self.agenda_time_entry.grid(row=3, column=1, sticky="ew", padx=10, pady=6, ipady=6)
        tk.Button(form, text="Agregar evento", command=self._save_agenda_from_editor, bg=ACCENT, fg=BG, relief="flat", bd=0, padx=12, pady=8).grid(row=4, column=1, sticky="e", padx=10, pady=(8, 10))
        form.grid_columnconfigure(1, weight=1)

        list_shell = tk.Frame(shell, bg=PANEL, highlightthickness=1, highlightbackground="#1f3a52")
        list_shell.pack(fill="both", expand=True, pady=(12, 0))
        tk.Label(list_shell, text="Agenda completa", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=10, pady=(10, 6))
        self.agenda_full_tree = ttk.Treeview(list_shell, columns=("fecha", "hora", "titulo", "tipo", "estado", "id"), show="headings", height=12)
        for col, label, width in (("fecha", "Fecha", 95), ("hora", "Hora", 70), ("titulo", "Titulo", 250), ("tipo", "Tipo", 90), ("estado", "Estado", 90)):
            self.agenda_full_tree.heading(col, text=label)
            self.agenda_full_tree.column(col, width=width, anchor="w" if col == "titulo" else "center")
        self.agenda_full_tree.heading("id", text="id")
        self.agenda_full_tree.column("id", width=0, stretch=False)
        self.agenda_full_tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        actions = tk.Frame(shell, bg=BG)
        actions.pack(fill="x", pady=(12, 0))
        tk.Button(actions, text="Pausar", command=lambda: self._toggle_selected_agenda(True), bg=PANEL, fg=TEXT, relief="flat", bd=0, padx=14, pady=10).pack(side="left")
        tk.Button(actions, text="Reactivar", command=lambda: self._toggle_selected_agenda(False), bg=PANEL, fg=TEXT, relief="flat", bd=0, padx=14, pady=10).pack(side="left", padx=(10, 0))
        tk.Button(actions, text="Borrar", command=self._delete_selected_agenda, bg=PANEL, fg=TEXT, relief="flat", bd=0, padx=14, pady=10).pack(side="left", padx=(10, 0))
        tk.Button(actions, text="Actualizar", command=self._refresh_agenda_editor, bg=PANEL, fg=TEXT, relief="flat", bd=0, padx=14, pady=10).pack(side="left", padx=(10, 0))
        tk.Button(actions, text="Cerrar", command=win.destroy, bg=ACCENT, fg=BG, relief="flat", bd=0, padx=14, pady=10).pack(side="right")

        self._refresh_agenda_editor()

    def _refresh_agenda_editor(self) -> None:
        if self.agenda_window is None or not self.agenda_window.winfo_exists():
            return
        for item in self.agenda_full_tree.get_children():
            self.agenda_full_tree.delete(item)
        for row in self.assistant.get_all_agenda_items():
            recurring = str(row.get("recurring", "") or "")
            if recurring == "daily":
                kind = "diario"
            elif recurring == "weekly":
                kind = "semanal"
            elif recurring == "weekly_multi":
                kind = "multi"
            else:
                kind = str(row.get("category", "evento"))
            state = "pausado" if row.get("paused") else "activo"
            self.agenda_full_tree.insert("", "end", values=(row.get("date", ""), row.get("time", ""), row.get("title", ""), kind, state, row.get("id", "")))

    def _save_agenda_from_editor(self) -> None:
        title = self.agenda_title_entry.get().strip()
        date_text = self.agenda_date_entry.get().strip()
        time_text = self.agenda_time_entry.get().strip()
        if not title or not date_text or not time_text:
            self.assistant._emit("Complete titulo, fecha y hora para agregar a la agenda.")
            return
        try:
            self.assistant.gui_add_agenda_item(title, date_text, time_text)
        except Exception:
            self.assistant._emit("No pude agregar el evento. Use fecha YYYY-MM-DD y hora HH:MM.")
            return
        self.agenda_title_entry.delete(0, "end")
        self.agenda_date_entry.delete(0, "end")
        self.agenda_time_entry.delete(0, "end")
        self._refresh_agenda_editor()

    def _selected_agenda_id(self) -> str | None:
        selection = self.agenda_full_tree.selection()
        if not selection:
            self.assistant._emit("Seleccione primero un evento de la agenda.")
            return None
        values = self.agenda_full_tree.item(selection[0], "values")
        return str(values[5]) if len(values) > 5 else None

    def _toggle_selected_agenda(self, paused: bool) -> None:
        item_id = self._selected_agenda_id()
        if not item_id:
            return
        self.assistant.gui_set_agenda_paused(item_id, paused)
        self._refresh_agenda_editor()

    def _delete_selected_agenda(self) -> None:
        item_id = self._selected_agenda_id()
        if not item_id:
            return
        self.assistant.gui_delete_agenda_item(item_id)
        self._refresh_agenda_editor()

    def _open_classes_editor(self) -> None:
        if self.classes_window is not None and self.classes_window.winfo_exists():
            self.classes_window.lift()
            return
        self.class_entries = {}
        schedule = dict(self.assistant.config.get("class_schedule", {}))

        win = tk.Toplevel(self.root)
        win.title("Clases por dia")
        win.geometry("620x420")
        win.configure(bg=BG)
        self.classes_window = win

        shell = tk.Frame(win, bg=BG)
        shell.pack(fill="both", expand=True, padx=16, pady=16)
        tk.Label(shell, text="Registrar clases semanales", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(0, 10))

        form = tk.Frame(shell, bg=PANEL, highlightthickness=1, highlightbackground="#1f3a52")
        form.pack(fill="x")
        weekdays = [("monday", "Lunes"), ("tuesday", "Martes"), ("wednesday", "Miercoles"), ("thursday", "Jueves"), ("friday", "Viernes")]
        for row, (key, label) in enumerate(weekdays, start=1):
            tk.Label(form, text=label, bg=PANEL, fg=MUTED, font=("Segoe UI", 10)).grid(row=row, column=0, sticky="w", padx=10, pady=6)
            entry = tk.Entry(form, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0, font=("Segoe UI", 10), width=48)
            entry.grid(row=row, column=1, sticky="ew", padx=10, pady=6, ipady=6)
            entry.insert(0, ", ".join(schedule.get(key, [])))
            self.class_entries[key] = entry
        form.grid_columnconfigure(1, weight=1)

        help_text = "Escribe las clases separadas por coma. Ejemplo: algebra, ingles, programacion."
        tk.Label(shell, text=help_text, bg=BG, fg=MUTED, font=("Segoe UI", 9), wraplength=560, justify="left").pack(anchor="w", pady=(10, 12))

        actions = tk.Frame(shell, bg=BG)
        actions.pack(fill="x")
        tk.Button(actions, text="Guardar clases", command=self._save_classes_editor, bg=ACCENT, fg=BG, relief="flat", bd=0, font=("Segoe UI Semibold", 10), padx=14, pady=10).pack(side="left")
        tk.Button(actions, text="Cerrar", command=win.destroy, bg=PANEL, fg=TEXT, relief="flat", bd=0, font=("Segoe UI", 10), padx=14, pady=10).pack(side="left", padx=(10, 0))

    def _save_classes_editor(self) -> None:
        schedule = dict(self.assistant.config.get("class_schedule", {}))
        for key, entry in self.class_entries.items():
            classes = [x.strip() for x in entry.get().split(",") if x.strip()]
            schedule[key] = classes
        result = self.assistant.apply_gui_config_patch({"class_schedule": schedule})
        if result.valid:
            self.assistant._emit("Clases actualizadas. Ya guarde su horario semanal.")
        else:
            self.assistant._emit("No pude guardar clases: " + " ".join(result.errors))
            return
        if self.classes_window is not None and self.classes_window.winfo_exists():
            self.classes_window.destroy()
            self.classes_window = None

    def _open_budget_editor(self) -> None:
        if self.budget_window is not None and self.budget_window.winfo_exists():
            self.budget_window.lift()
            return

        win = tk.Toplevel(self.root)
        win.title("Gestor de presupuesto")
        win.geometry("780x680")
        win.configure(bg=BG)
        self.budget_window = win

        outer = tk.Frame(win, bg=BG)
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        scroll = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        shell = tk.Frame(canvas, bg=BG)
        shell.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=shell, anchor="nw", width=740)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(16, 0), pady=16)
        scroll.pack(side="right", fill="y", padx=(8, 16), pady=16)
        self._enable_mousewheel(canvas, shell)

        tk.Label(shell, text="Gestor de presupuesto", bg=BG, fg=TEXT, font=("Segoe UI Semibold", 14)).pack(anchor="w", pady=(0, 10))

        summary_frame = tk.Frame(shell, bg=PANEL_ALT, highlightthickness=1, highlightbackground="#1f3a52")
        summary_frame.pack(fill="x")
        self.budget_summary_editor = tk.Label(summary_frame, text="", justify="left", bg=PANEL_ALT, fg=MUTED, font=("Segoe UI", 10))
        self.budget_summary_editor.pack(fill="x", padx=12, pady=12)

        forms = tk.Frame(shell, bg=BG)
        forms.pack(fill="x", pady=(12, 0))

        income_frame = tk.Frame(forms, bg=PANEL, highlightthickness=1, highlightbackground="#1f3a52")
        income_frame.pack(fill="x", pady=(0, 10))
        tk.Label(income_frame, text="Agregar ingreso", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 11)).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 8))
        tk.Label(income_frame, text="Monto", bg=PANEL, fg=MUTED).grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.income_amount_entry = tk.Entry(income_frame, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0)
        self.income_amount_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=4, ipady=6)
        tk.Label(income_frame, text="Descripcion", bg=PANEL, fg=MUTED).grid(row=2, column=0, sticky="w", padx=10, pady=4)
        self.income_desc_entry = tk.Entry(income_frame, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0)
        self.income_desc_entry.grid(row=2, column=1, sticky="ew", padx=10, pady=4, ipady=6)
        tk.Button(income_frame, text="Guardar ingreso", command=self._save_income_from_editor, bg=ACCENT, fg=BG, relief="flat", bd=0, padx=12, pady=8).grid(row=3, column=1, sticky="e", padx=10, pady=(8, 10))
        income_frame.grid_columnconfigure(1, weight=1)

        expense_frame = tk.Frame(forms, bg=PANEL, highlightthickness=1, highlightbackground="#1f3a52")
        expense_frame.pack(fill="x", pady=(0, 10))
        tk.Label(expense_frame, text="Agregar gasto", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 11)).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 8))
        tk.Label(expense_frame, text="Monto", bg=PANEL, fg=MUTED).grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.expense_amount_entry = tk.Entry(expense_frame, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0)
        self.expense_amount_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=4, ipady=6)
        tk.Label(expense_frame, text="Descripcion", bg=PANEL, fg=MUTED).grid(row=2, column=0, sticky="w", padx=10, pady=4)
        self.expense_desc_entry = tk.Entry(expense_frame, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0)
        self.expense_desc_entry.grid(row=2, column=1, sticky="ew", padx=10, pady=4, ipady=6)
        tk.Button(expense_frame, text="Guardar gasto", command=self._save_expense_from_editor, bg=ACCENT, fg=BG, relief="flat", bd=0, padx=12, pady=8).grid(row=3, column=1, sticky="e", padx=10, pady=(8, 10))
        expense_frame.grid_columnconfigure(1, weight=1)

        limit_frame = tk.Frame(forms, bg=PANEL, highlightthickness=1, highlightbackground="#1f3a52")
        limit_frame.pack(fill="x", pady=(0, 10))
        tk.Label(limit_frame, text="Limite de presupuesto", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 11)).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 8))
        tk.Label(limit_frame, text="Limite", bg=PANEL, fg=MUTED).grid(row=1, column=0, sticky="w", padx=10, pady=4)
        self.limit_entry = tk.Entry(limit_frame, bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat", bd=0)
        self.limit_entry.grid(row=1, column=1, sticky="ew", padx=10, pady=4, ipady=6)
        tk.Button(limit_frame, text="Guardar limite", command=self._save_limit_from_editor, bg=ACCENT, fg=BG, relief="flat", bd=0, padx=12, pady=8).grid(row=2, column=1, sticky="e", padx=10, pady=(8, 10))
        limit_frame.grid_columnconfigure(1, weight=1)

        tx_frame = tk.Frame(shell, bg=PANEL, highlightthickness=1, highlightbackground="#1f3a52")
        tx_frame.pack(fill="both", expand=True)
        tk.Label(tx_frame, text="Movimientos recientes", bg=PANEL, fg=TEXT, font=("Segoe UI Semibold", 11)).pack(anchor="w", padx=10, pady=(10, 6))
        self.budget_tx_text = tk.Text(tx_frame, bg=PANEL, fg=MUTED, relief="flat", bd=0, wrap="word", height=12)
        self.budget_tx_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.budget_tx_text.configure(state="disabled")
        self._enable_mousewheel(canvas, self.budget_tx_text)

        actions = tk.Frame(shell, bg=BG)
        actions.pack(fill="x", pady=(12, 0))
        tk.Button(actions, text="Actualizar", command=self._refresh_budget_editor, bg=PANEL, fg=TEXT, relief="flat", bd=0, padx=14, pady=10).pack(side="left")
        tk.Button(actions, text="Cerrar", command=win.destroy, bg=ACCENT, fg=BG, relief="flat", bd=0, padx=14, pady=10).pack(side="right")

        self._refresh_budget_editor()

    def _refresh_budget_editor(self) -> None:
        balance = get_balance()
        categories = get_expenses_by_category()
        parts = [
            f"Balance: ${balance['balance']:.2f}",
            f"Ingresos: ${balance['total_income']:.2f}",
            f"Gastos: ${balance['total_expenses']:.2f}",
            f"Limite: ${balance.get('budget_limit', 0):.2f}",
            f"Restante: ${balance.get('remaining_budget', 0):.2f}",
        ]
        if categories:
            parts.append("Categorias: " + ", ".join(f"{k}: ${v:.0f}" for k, v in sorted(categories.items(), key=lambda x: -x[1])))
        self.budget_summary_editor.config(text="\n".join(parts))

        recent = get_recent_transactions()
        self.budget_tx_text.configure(state="normal")
        self.budget_tx_text.delete("1.0", "end")
        if recent:
            for item in recent:
                tx = item["transaction"]
                sign = "+" if item["type"] == "income" else "-"
                self.budget_tx_text.insert("end", f"{sign}${tx.get('amount', 0):.2f}  {tx.get('description', '')}\n")
        else:
            self.budget_tx_text.insert("1.0", "Sin movimientos recientes.")
        self.budget_tx_text.configure(state="disabled")

    def _save_income_from_editor(self) -> None:
        amount = parse_amount(self.income_amount_entry.get())
        if amount is None:
            self.assistant._emit("No pude entender el monto del ingreso.")
            return
        desc = self.income_desc_entry.get().strip() or "Ingreso"
        result = add_income(amount, desc)
        self.assistant._emit(f"Ingreso registrado. Balance actual: ${result['balance']:.2f}.")
        self.income_amount_entry.delete(0, "end")
        self.income_desc_entry.delete(0, "end")
        self._refresh_budget_editor()

    def _save_expense_from_editor(self) -> None:
        amount = parse_amount(self.expense_amount_entry.get())
        if amount is None:
            self.assistant._emit("No pude entender el monto del gasto.")
            return
        desc = self.expense_desc_entry.get().strip() or "Gasto"
        result = add_expense(amount, desc)
        self.assistant._emit(f"Gasto registrado en {result['category']}. Balance actual: ${result['balance']:.2f}.")
        self.expense_amount_entry.delete(0, "end")
        self.expense_desc_entry.delete(0, "end")
        self._refresh_budget_editor()

    def _save_limit_from_editor(self) -> None:
        amount = parse_amount(self.limit_entry.get())
        if amount is None:
            self.assistant._emit("No pude entender el limite del presupuesto.")
            return
        result = set_budget_limit(amount)
        self.assistant._emit(f"Listo. El limite de presupuesto ahora es ${result['budget_limit']:.2f}.")
        self.limit_entry.delete(0, "end")
        self._refresh_budget_editor()

    def _append_log(self, role: str, text: str) -> None:
        prefix = "Tu" if role == "user" else "Viernes"
        self.log.configure(state="normal")
        self.log.insert("end", f"{prefix}: {text}\n\n")
        self.log.configure(state="disabled")
        self.log.see("end")

    def _set_listen_button(self, text: str, enabled: bool) -> None:
        if self.listen_button is None or not self.listen_button.winfo_exists():
            return
        self.listen_button.config(text=text, state="normal" if enabled else "disabled")

    def _show_recognized_text(self, text: str) -> None:
        if hasattr(self, "entry") and self.entry.winfo_exists():
            self.entry.delete(0, "end")
            self.entry.insert(0, text)
        self.assistant.messages.put(("assistant", f"Le entendi: {text}"))

    def _listen_once(self) -> None:
        if self.listening_in_progress:
            return
        if not speech_input_available():
            self.assistant.messages.put(("assistant", "El reconocimiento de voz no esta disponible en esta instalacion."))
            return

        self.listening_in_progress = True
        self.avatar.pulse_listening()
        self._set_listen_button("Escuchando...", False)

        def worker() -> None:
            try:
                text = recognize_once(
                    on_status=lambda status: self.root.after(0, lambda captured=status: self._set_listen_button(captured, False))
                )
                try:
                    self.root.after(0, lambda captured=text: self._show_recognized_text(captured))
                except tk.TclError:
                    pass
                self.assistant.process_command(text)
            except Exception as exc:
                self.assistant.messages.put(("assistant", f"No pude escuchar bien esta vez: {exc}"))
            finally:
                self.listening_in_progress = False
                try:
                    self.root.after(0, lambda: self._set_listen_button("Hablar", True))
                except tk.TclError:
                    return

        threading.Thread(target=worker, daemon=True).start()

    def _force_stop(self) -> None:
        """Fuerza a Viernes a detenerse: cancela dialogos, limpia cola y detiene voz."""
        def worker() -> None:
            try:
                self.assistant.force_stop()
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _submit(self, preset: str | None = None) -> None:
        text = preset if preset is not None else self.entry.get().strip()
        if not text:
            return
        if preset is None:
            self.entry.delete(0, "end")
        self.avatar.pulse_listening()

        def worker() -> None:
            try:
                self.assistant.process_command(text)
            except Exception as exc:
                self.assistant.messages.put(("assistant", f"Se produjo un error al procesar el comando: {exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def _run_analysis(self, prefix: str) -> None:
        query = self.analysis_entry.get().strip() if hasattr(self, "analysis_entry") else ""
        if not query:
            query = "mi dia" if "reporte" in prefix else "mis gastos"
        if prefix == "investiga":
            command = f"investiga {query} y haz tabla"
        elif prefix == "simula":
            command = f"simula {query}"
        else:
            command = f"{prefix} {query}"
        self.avatar.pulse_listening()

        def worker() -> None:
            try:
                response = self.assistant.process_command(command)
                self.root.after(0, lambda captured=response: self._set_analysis_output(captured))
                self.root.after(0, self._refresh_dashboard)
            except Exception as exc:
                self.assistant.messages.put(("assistant", f"No pude ejecutar Analisis: {exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def _set_analysis_output(self, text: str) -> None:
        if not hasattr(self, "analysis_output"):
            return
        self.analysis_output.configure(state="normal")
        self.analysis_output.delete("1.0", "end")
        self.analysis_output.insert("1.0", text)
        self.analysis_output.configure(state="disabled")

    def _refresh_analysis_panel(self, data: dict[str, object]) -> None:
        if not hasattr(self, "analysis_output"):
            return
        analysis = data.get("analysis", {}) if isinstance(data.get("analysis", {}), dict) else {}
        if not analysis:
            analysis = data.get("analysis_beta", {}) if isinstance(data.get("analysis_beta", {}), dict) else {}
        last = analysis.get("last_result", {}) if isinstance(analysis.get("last_result", {}), dict) else {}
        if last:
            summary = str(last.get("summary", "") or "")
            title = str(last.get("title", "Analisis") or "Analisis")
            self._set_analysis_output(f"{title}\n{summary}")
            table = last.get("table", {}) if isinstance(last.get("table", {}), dict) else {}
            columns = [str(item) for item in table.get("columns", [])] if isinstance(table.get("columns", []), list) else []
            rows = table.get("rows", []) if isinstance(table.get("rows", []), list) else []
            self.analysis_tree.delete(*self.analysis_tree.get_children())
            if columns:
                tree_columns = [f"c{idx}" for idx in range(1, min(len(columns), 6) + 1)]
                self.analysis_tree.configure(columns=tree_columns)
                for key, heading in zip(tree_columns, columns):
                    self.analysis_tree.heading(key, text=heading[:22])
                    self.analysis_tree.column(key, width=max(90, 320 // max(1, len(tree_columns))), anchor="w")
                for row in rows[:20]:
                    values = [str(item) for item in list(row)[: len(tree_columns)]] if isinstance(row, list) else [str(row)]
                    self.analysis_tree.insert("", "end", values=values)
            chart = last.get("chart", {}) if isinstance(last.get("chart", {}), dict) else {}
            chart_path = str(chart.get("path", "") or "")
            if chart_path:
                try:
                    self.analysis_image_ref = tk.PhotoImage(file=chart_path)
                    self.analysis_chart_label.config(image=self.analysis_image_ref, text="")
                except tk.TclError:
                    self.analysis_chart_label.config(image="", text=f"Grafica guardada: {chart_path}")
            else:
                self.analysis_chart_label.config(image="", text="Sin grafica reciente.")
        reports = analysis.get("reports", []) if isinstance(analysis.get("reports", []), list) else []
        if reports:
            lines = ["Reportes recientes:"]
            for item in reports[:4]:
                if isinstance(item, dict):
                    lines.append(str(item.get("name") or item.get("path") or "reporte"))
            self.analysis_reports_text.config(text="\n".join(lines))
        else:
            self.analysis_reports_text.config(text="Sin reportes guardados aun.")

    def _refresh_remote_panel(self, data: dict[str, object]) -> None:
        if not hasattr(self, "remote_text"):
            return
        remote = data.get("remote_control", {}) if isinstance(data.get("remote_control", {}), dict) else {}
        resident = remote.get("resident", {}) if isinstance(remote.get("resident", {}), dict) else {}
        history = remote.get("history", []) if isinstance(remote.get("history", []), list) else []
        lines = [
            f"Control remoto: {'activo' if remote.get('enabled') else 'apagado'}",
            f"Residente: {resident.get('task', 'desconocido')}",
            f"Owners: {remote.get('owner_chat_ids', 0)} | Trusted: {remote.get('trusted_chat_ids', 0)} | Solo lectura: {remote.get('read_only_chat_ids', 0)}",
            f"Permitidos legado: {remote.get('allowed_chat_ids', 0)}",
            f"Offset: {remote.get('update_offset', 0)}",
            f"Ultimo polling: {remote.get('last_poll_at') or 'sin datos'}",
            f"Pendientes: {remote.get('pending_confirmations', 0)}",
            f"Ultimo error: {remote.get('last_error') or 'sin errores'}",
            "",
            "Historial:",
        ]
        for item in history[:8]:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"{item.get('timestamp', '')} [{item.get('direction', '?')}/{item.get('status', '?')}] "
                f"{item.get('permission', '')} {item.get('text', '')}"
            )
        self.remote_text.configure(state="normal")
        self.remote_text.delete("1.0", "end")
        self.remote_text.insert("1.0", "\n".join(lines))
        self.remote_text.configure(state="disabled")

    def _refresh_dashboard(self) -> None:
        self._show_pending_morning_interaction()
        data = self.assistant.today_dashboard()
        self.status_label.config(text=f"Hoy es {data['weekday']} {data['today']}")
        for item in self.agenda_tree.get_children():
            self.agenda_tree.delete(item)
        for row in data["agenda"]:
            self.agenda_tree.insert("", "end", values=(row.get("time", "--:--"), row.get("title", "Evento")))

        override = data["override"]
        daily = data["daily_state"]
        classes = data["classes"]
        today_parts = [
            f"Bano hecho: {'si' if daily.get('bath_done') else 'no'}",
            f"Llegada registrada: {'si' if daily.get('arrived') else 'no'}",
        ]
        if override.get("free_day"):
            today_parts.append("Dia libre activo")
        if override.get("classes_cancelled"):
            today_parts.append("Clases canceladas")
        self.today_text.config(text="\n".join(today_parts))

        self.classes_text.config(text=", ".join(classes) if classes else "No hay clases registradas para hoy.")
        self.metric_agenda.config(text=str(len(data["agenda"])))
        self.metric_classes.config(text=str(len(classes)))

        balance = data["budget"]
        categories = get_expenses_by_category()
        recent = get_recent_transactions()
        budget_parts = [
            f"Balance: ${balance['balance']:.2f}",
            f"Ingresos: ${balance['total_income']:.2f}",
            f"Gastos: ${balance['total_expenses']:.2f}",
        ]
        if balance.get("budget_limit", 0):
            budget_parts.append(f"Limite: ${balance['budget_limit']:.2f}")
        if categories:
            top = ", ".join(f"{k}: ${v:.0f}" for k, v in sorted(categories.items(), key=lambda x: -x[1])[:3])
            budget_parts.append("Categorias: " + top)
        if recent:
            tx = recent[0]["transaction"]
            sign = "+" if recent[0]["type"] == "income" else "-"
            budget_parts.append(f"Ultimo: {sign}${tx.get('amount', 0):.2f} {tx.get('description', '')}")
        self.budget_text.config(text="\n".join(budget_parts))
        self.metric_budget.config(text=f"${balance['balance']:.0f}")
        self.summary_text.config(
            text=" | ".join(
                [
                    f"{len(data['agenda'])} evento(s) hoy",
                    (f"{len(classes)} clase(s) registradas" if classes else "sin clases hoy"),
                    ("dia libre activo" if override.get("free_day") else "rutina normal"),
                ]
            )
        )
        if hasattr(self, "focus_text"):
            focus_items = list(data.get("focus", []))
            habit_items = [f"Habito: {item}" for item in data.get("habit_recommendations", [])[:2]]
            risk_items = [f"Riesgo: {item}" for item in data.get("risks", [])[:2]]
            next_action = data.get("next_action", "")
            action_items = [f"Siguiente: {next_action}"] if next_action else []
            self.focus_text.config(text="\n".join(action_items + focus_items + habit_items + risk_items))
        if hasattr(self, "understanding_text"):
            understanding = data.get("understanding", {})
            decision = understanding.get("last_decision", {}) if isinstance(understanding, dict) else {}
            pending = understanding.get("pending_dialog", {}) if isinstance(understanding, dict) else {}
            lines = [
                f"Intent: {decision.get('intent', 'sin datos')}",
                f"Handler: {decision.get('handler', 'sin datos')}",
                f"Riesgo: {decision.get('risk', 'sin datos')}",
                f"Confirmacion: {'si' if decision.get('requires_confirmation') else 'no'}",
                f"Dialogo pendiente: {pending.get('kind', 'ninguno') if pending else 'ninguno'}",
            ]
            self.understanding_text.config(text="\n".join(lines))
        if hasattr(self, "execution_text"):
            executions = data.get("executions", {}) if isinstance(data.get("executions", {}), dict) else {}
            receipt = executions.get("last_receipt", {}) if isinstance(executions.get("last_receipt", {}), dict) else {}
            evidence = receipt.get("evidence", []) if isinstance(receipt.get("evidence", []), list) else []
            evidence_text = ", ".join(str(item.get("detail", "")) for item in evidence[:2] if isinstance(item, dict) and item.get("detail")) or "sin evidencia"
            errors = receipt.get("errors", []) if isinstance(receipt.get("errors", []), list) else []
            lines = [
                f"Estado: {receipt.get('status', 'sin recibo')}",
                f"Exito: {'si' if receipt.get('success') else 'no'}",
                f"Accion: {receipt.get('executed_action', 'sin datos')}",
                f"Evidencia: {evidence_text}",
                f"Errores: {', '.join(str(item) for item in errors[:2]) if errors else 'sin errores'}",
            ]
            self.execution_text.config(text="\n".join(lines))
        self._refresh_analysis_panel(data)
        self._refresh_remote_panel(data)
        system = self.assistant.system_status_snapshot()
        active_config = data.get("config_active", {})
        validation = active_config.get("last_validation", {}) if isinstance(active_config, dict) else {}
        validation_line = "ok" if validation.get("valid", True) else "con errores"
        self.system_text.config(
            text=(
                f"Autoarranque: {system['startup']}\n"
                f"Despertar: {system['task']}\n"
                f"Hora programada: {system['wake_time']}\n"
                f"Proxima ejecucion: {system.get('next_run', 'desconocido')}\n"
                f"Voz: {system['voice']}\n"
                f"Microfono: {system.get('speech_input', 'desconocido')}\n"
                f"Telegram: {system.get('telegram', 'inactivo')}\n"
                f"Analisis: {'activo' if active_config.get('analysis_enabled', active_config.get('analysis_beta_enabled')) else 'apagado'}\n"
                f"Control remoto: {'activo' if active_config.get('remote_control_enabled') else 'apagado'}\n"
                f"Actividad personal: {'activa' if active_config.get('personal_activity_enabled') else 'apagada'}\n"
                f"Proactividad: {active_config.get('proactivity_mode', 'conservative')}\n"
                f"Ultima validacion: {validation_line}"
            )
        )

        timeline = self.assistant.get_routine_timeline()
        self.routines_text.configure(state="normal")
        self.routines_text.delete("1.0", "end")
        self.routines_text.insert("1.0", timeline)
        self.routines_text.configure(state="disabled")

        self.root.after(15000, self._refresh_dashboard)

    def _show_pending_morning_interaction(self) -> None:
        if self.pending_morning_shown:
            return
        message = self.assistant.consume_pending_morning_interaction(require_interactive=True)
        if not message:
            return
        self.pending_morning_shown = True
        self.assistant.messages.put(("assistant", message))

    def _poll_messages(self) -> None:
        for role, text in self.assistant.poll_messages():
            self._append_log(role, text)
            if role == "assistant":
                self.avatar.pulse_speaking()
            else:
                self.avatar.pulse_listening()
        self.root.after(150, self._poll_messages)

    def _start_scheduler_thread(self) -> None:
        def loop() -> None:
            while self.running:
                try:
                    self.assistant.scheduler_tick()
                except Exception as exc:
                    self.assistant.messages.put(("assistant", f"Error interno del scheduler: {exc}"))
                time.sleep(30)

        threading.Thread(target=loop, daemon=True).start()

    def _close(self) -> None:
        self.running = False
        self.root.destroy()

    def run(self) -> None:
        if self._modern_shell is not None:
            self._modern_shell.run()
            return
        self.root.mainloop()


if __name__ == "__main__":
    ViernesGUI().run()
