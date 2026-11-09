from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
import csv
import hashlib
import json
import os
import sqlite3
import struct
import sys
import tempfile
import threading
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app
import diagnosticar_voz


def create_test_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(
        """CREATE TABLE tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        due_date TEXT,
        priority TEXT NOT NULL DEFAULT 'Normal',
        done INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        due_time TEXT,
        reminded INTEGER NOT NULL DEFAULT 0,
        subject TEXT,
        routine_id INTEGER,
        external_uid TEXT,
        repeat_rule TEXT NOT NULL DEFAULT 'none',
        repeat_series_id INTEGER,
        completed_at TEXT
    )"""
    )
    db.execute(
        """CREATE TABLE classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        weekday INTEGER NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT,
        location TEXT,
        reminded_on TEXT
    )"""
    )
    db.execute(
        """CREATE TABLE class_exceptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        exception_date TEXT NOT NULL,
        class_id INTEGER,
        class_name TEXT,
        action TEXT NOT NULL,
        name TEXT,
        start_time TEXT,
        end_time TEXT,
        location TEXT,
        note TEXT,
        reminded_on TEXT
    )"""
    )
    db.execute(
        """CREATE TABLE memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        label TEXT NOT NULL,
        content TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'Preferencia',
        created_at TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'Entrada manual del usuario',
        expires_on TEXT
    )"""
    )
    db.execute(
        """CREATE TABLE routines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        subject TEXT,
        weekdays TEXT NOT NULL,
        reminder_time TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'Rutina configurada manualmente por el usuario'
    )"""
    )
    db.execute(
        """CREATE TABLE reminder_events (
        alert_key TEXT PRIMARY KEY,
        source_type TEXT NOT NULL,
        source_id INTEGER,
        title TEXT NOT NULL,
        due_at_local TEXT NOT NULL,
        state TEXT NOT NULL DEFAULT 'pending',
        snooze_until TEXT,
        next_notify_at TEXT NOT NULL,
        delivery_count INTEGER NOT NULL DEFAULT 0,
        last_delivered_at TEXT
    )"""
    )
    db.execute(
        """CREATE TABLE reminder_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_key TEXT NOT NULL,
        action TEXT NOT NULL,
        action_at TEXT NOT NULL,
        details TEXT
    )"""
    )
    db.execute(
        """CREATE TABLE plan_blocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        block_date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        notes TEXT,
        created_at TEXT NOT NULL
    )"""
    )
    db.execute(
        """CREATE TABLE action_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT NOT NULL,
        outcome TEXT NOT NULL,
        created_at TEXT NOT NULL
    )"""
    )
    db.commit()
    return db


def write_minimal_pe(path: Path, subsystem: int = 2) -> None:
    dos = bytearray(0x80)
    dos[:2] = b"MZ"
    struct.pack_into("<I", dos, 0x3C, 0x80)
    coff = bytearray(20)
    struct.pack_into("<H", coff, 16, 96)
    optional = bytearray(96)
    struct.pack_into("<H", optional, 0, 0x20B)
    struct.pack_into("<H", optional, 68, subsystem)
    path.write_bytes(bytes(dos) + b"PE\0\0" + bytes(coff) + bytes(optional))


class UnifiedClaraTests(unittest.TestCase):
    # =========================================================================
    # 1. Pruebas heredadas de CLARA v1.27.4 (Etapas 1 a 12)
    # =========================================================================
    def test_inclusive_dates_validates_bounds(self) -> None:
        days = app.inclusive_dates(date(2026, 5, 1), date(2026, 5, 3))
        self.assertEqual([d.isoformat() for d in days], ["2026-05-01", "2026-05-02", "2026-05-03"])
        with self.assertRaises(ValueError):
            app.inclusive_dates(date(2026, 5, 4), date(2026, 5, 3))
        with self.assertRaises(ValueError):
            app.inclusive_dates(date(2026, 1, 1), date(2028, 2, 1))

    def test_recurring_completion_creates_at_most_one_pending_successor(self) -> None:
        db = create_test_db()
        db.execute(
            "INSERT INTO tasks(title,due_date,priority,done,created_at,repeat_rule) VALUES(?,?,?,?,?,?)",
            ("Repasar vocabulario", "2026-04-10", "Normal", 0, "2026-04-01T08:00:00", "daily"),
        )
        db.commit()
        first = app.toggle_task_completion(db, 1, datetime(2026, 4, 10, 9, 0))
        self.assertIn("11/04/2026", first or "")
        rows = db.execute("SELECT id, due_date, done, repeat_series_id FROM tasks ORDER BY id").fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0]["done"], rows[1]["due_date"], rows[1]["repeat_series_id"]), (1, "2026-04-11", 1))

        app.toggle_task_completion(db, 1, datetime(2026, 4, 10, 9, 5))
        second = app.toggle_task_completion(db, 1, datetime(2026, 4, 10, 9, 10))
        self.assertIn("no dupliqué", second or "")
        self.assertEqual(db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 2)

    def test_school_calendar_exceptions_resolve_without_changing_weekly_classes(self) -> None:
        db = create_test_db()
        monday = date(2026, 4, 13)
        db.execute("INSERT INTO classes(name,weekday,start_time,end_time,location) VALUES(?,?,?,?,?)", ("Matemáticas", 0, "08:00", "09:00", "A1"))
        db.execute("INSERT INTO classes(name,weekday,start_time,end_time,location) VALUES(?,?,?,?,?)", ("Historia", 0, "10:00", "11:00", "B2"))
        db.execute("INSERT INTO class_exceptions(exception_date,class_id,class_name,action) VALUES(?,?,?,?)", (monday.isoformat(), 1, "Matemáticas", "cancel"))
        db.execute("INSERT INTO class_exceptions(exception_date,class_id,class_name,action,start_time,location) VALUES(?,?,?,?,?,?)", (monday.isoformat(), 2, "Historia", "override", "11:00", "Lab"))
        db.execute("INSERT INTO class_exceptions(exception_date,action,name,start_time,location) VALUES(?,?,?,?,?)", (monday.isoformat(), "extra", "Tutoría", "12:00", "C3"))
        db.commit()

        resolved = app.classes_for_date(db, monday)
        self.assertEqual([(m["name"], m["start_time"], m["location"]) for m in resolved], [("Historia", "11:00", "Lab"), ("Tutoría", "12:00", "C3")])

        db.execute("INSERT INTO class_exceptions(exception_date,action,note) VALUES(?,?,?)", (monday.isoformat(), "no_classes", "Vacaciones"))
        db.commit()
        holiday = app.classes_for_date(db, monday)
        self.assertEqual([(m["name"], m["source"]) for m in holiday], [("Tutoría", "exception")])

    def test_memories_respect_expiration_and_routine_suggestions_require_three_weeks(self) -> None:
        db = create_test_db()
        db.execute("INSERT INTO memories(label,content,category,created_at,source,expires_on) VALUES(?,?,?,?,?,?)", ("Vigente", "Prefiere bloques cortos", "Estudio", "2026-04-01T10:00:00", "Entrada manual del usuario", "2026-04-30"))
        db.execute("INSERT INTO memories(label,content,category,created_at,source,expires_on) VALUES(?,?,?,?,?,?)", ("Caducado", "Dato viejo", "Otra", "2026-03-01T10:00:00", "Entrada manual del usuario", "2026-04-01"))
        for day in ("2026-03-23", "2026-03-30", "2026-04-06"):
            db.execute(
                "INSERT INTO tasks(title,subject,due_date,due_time,done,created_at,completed_at,repeat_rule) VALUES(?,?,?,?,1,?,?, 'none')",
                ("Entregar bitácora", "Biología", day, "18:00", day + "T08:00:00", day + "T19:00:00"),
            )
        db.commit()

        memories = app.active_memories_for(db, date(2026, 4, 13))
        self.assertEqual([row["label"] for row in memories], ["Vigente"])
        suggestions = app.find_routine_pattern_candidates(db, date(2026, 4, 13))
        self.assertEqual(len(suggestions), 1)
        self.assertEqual((suggestions[0]["title"], suggestions[0]["weekdays"], suggestions[0]["occurrences"]), ("Entregar bitácora", "0", 3))

    def test_reminder_lifecycle_dedupes_snoozes_and_dismisses(self) -> None:
        db = create_test_db()
        db.execute(
            "INSERT INTO tasks(title,due_date,due_time,priority,done,created_at) VALUES(?,?,?,?,0,?)",
            ("Subir práctica", "2026-04-13", "09:00", "Alta", "2026-04-13T07:00:00"),
        )
        db.commit()
        now = datetime(2026, 4, 13, 9, 5)
        first = app.collect_due_alerts(db, now)
        self.assertEqual(len(first), 1)
        self.assertEqual(app.collect_due_alerts(db, now + timedelta(minutes=1)), [])

        key = first[0]["alert_key"]
        app.record_alert_action(db, key, "snoozed", now, minutes=10)
        self.assertEqual(app.collect_due_alerts(db, now + timedelta(minutes=9)), [])
        again = app.collect_due_alerts(db, now + timedelta(minutes=11))
        self.assertEqual(len(again), 1)

        app.record_alert_action(db, key, "dismissed", now + timedelta(minutes=12))
        self.assertEqual(app.collect_due_alerts(db, now + timedelta(hours=2)), [])
        actions = [row["action"] for row in db.execute("SELECT action FROM reminder_actions WHERE alert_key=? ORDER BY id", (key,))]
        self.assertEqual(actions, ["created", "delivered", "snoozed", "delivered", "dismissed"])

    def test_ical_parser_skips_recurrences_and_own_exported_schedule_items(self) -> None:
        ics = """BEGIN:VCALENDAR\r
PRODID:-//Asistente Personal//Agenda ES\r
BEGIN:VEVENT\r
UID:own-class@asistente.local\r
DTSTART:20260414T080000\r
SUMMARY:Clase: Física\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:repeat@example.com\r
DTSTART:20260415T100000\r
RRULE:FREQ=WEEKLY\r
SUMMARY:Reunión semanal\r
END:VEVENT\r
BEGIN:VEVENT\r
UID:exam@example.com\r
DTSTART;TZID=Region/Inexistente:20260416T123000\r
DTEND;TZID=Region/Inexistente:20260416T140000\r
SUMMARY:Examen parcial\\, unidad 2\r
END:VEVENT\r
END:VCALENDAR\r
"""
        events, skipped_recurring, skipped_own = app.parse_ical_events(ics)
        self.assertEqual(( len(events), skipped_recurring, skipped_own ), (1, 1, 1))
        self.assertEqual(events[0]["title"], "Examen parcial, unidad 2")
        self.assertEqual((events[0]["due_date"], events[0]["due_time"], events[0]["end_time"]), ("2026-04-16", "12:30", "14:00"))
        self.assertIn("Zona TZID", str(events[0]["timezone_warning"]))

    def test_linked_ics_rejects_remote_paths_and_detects_local_conflicts(self) -> None:
        db = create_test_db()
        monday = date(2026, 4, 13)
        db.execute("INSERT INTO classes(name,weekday,start_time,end_time) VALUES(?,?,?,?)", ("Química", 0, "10:00", "11:00"))
        db.execute("INSERT INTO plan_blocks(title,block_date,start_time,end_time,created_at) VALUES(?,?,?,?,?)", ("Estudio", monday.isoformat(), "16:00", "17:00", "2026-04-13T08:00:00"))
        db.commit()
        events, status = app.read_linked_ics_events("https://example.com/cal.ics", monday, monday)
        self.assertEqual(events, [])
        self.assertIn("Solo se admiten archivos locales", status)
        clash = {"due_date": monday.isoformat(), "due_time": "10:30", "end_time": "11:30"}
        self.assertEqual(app.linked_event_conflicts(db, clash), ["Clase: Química"])

    def test_afternoon_draft_avoids_classes_and_existing_blocks_without_writing_db(self) -> None:
        db = create_test_db()
        monday = date(2026, 4, 13)
        db.execute("INSERT INTO classes(name,weekday,start_time,end_time) VALUES(?,?,?,?)", ("Laboratorio", 0, "13:00", "14:00"))
        db.execute("INSERT INTO plan_blocks(title,block_date,start_time,end_time,created_at) VALUES(?,?,?,?,?)", ("Lectura", monday.isoformat(), "14:15", "15:00", "2026-04-13T08:00:00"))
        db.execute("INSERT INTO tasks(title,due_date,priority,done,created_at) VALUES(?,?,?,0,?)", ("Resolver guía", monday.isoformat(), "Alta", "2026-04-13T08:00:00"))
        db.execute("INSERT INTO tasks(title,due_date,priority,done,created_at) VALUES(?,?,?,0,?)", ("Preparar resumen", None, "Normal", "2026-04-13T08:00:00"))
        db.commit()

        drafts, omitted = app.build_afternoon_draft(db, monday, datetime(2026, 4, 13, 12, 30))
        self.assertEqual(omitted, 0)
        self.assertEqual([(d["title"], d["start_time"], d["end_time"]) for d in drafts], [("Resolver guía", "15:15", "16:00"), ("Preparar resumen", "16:15", "17:00")])
        self.assertEqual(db.execute("SELECT COUNT(*) FROM plan_blocks").fetchone()[0], 1)

    def test_rss_parser_enforces_xml_and_size_defenses(self) -> None:
        rss = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel>
        <item><title>Titular uno</title><link>https://example.com/1</link><source>Medio A</source></item>
        <item><title>Titular dos</title><link>https://example.com/2</link></item>
        </channel></rss>"""
        items = app.parse_news_feed(rss, "Fuente", 1)
        self.assertEqual(items, [{"title": "Titular uno", "source": "Medio A", "link": "https://example.com/1"}])
        with self.assertRaises(ValueError):
            app.parse_news_feed(b"<!DOCTYPE rss><rss/>", "Fuente", 3)
        with self.assertRaises(ValueError):
            app.parse_news_feed(b"a" * (2 * 1024 * 1024 + 1), "Fuente", 3)

    def test_virustotal_hash_helper_and_pause_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "nota.txt"
            sample.write_text("contenido de prueba", encoding="utf-8")
            digest, size = app.hash_file_sha256(sample)
            self.assertEqual(len(digest), 64)
            self.assertGreater(size, 0)
        future = (datetime.now() + timedelta(minutes=30)).isoformat(timespec="seconds")
        past = (datetime.now() - timedelta(minutes=30)).isoformat(timespec="seconds")
        self.assertTrue(app.reminder_pause_active({"reminders_paused_until": future}))
        self.assertFalse(app.reminder_pause_active({"reminders_paused_until": past}))

    def test_selected_folder_validation_accepts_existing_dir_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.assertEqual(app.validate_selected_folder(folder), folder.resolve())
            file_path = folder / "archivo.txt"
            file_path.write_text("hola", encoding="utf-8")
            with self.assertRaises(ValueError):
                app.validate_selected_folder(file_path)
            with self.assertRaises((FileNotFoundError, ValueError)):
                app.validate_selected_folder(folder / "no_existe")

    def test_chat_speaker_display_renames_legacy_luma_without_mutating_others(self) -> None:
        self.assertEqual(app.display_chat_speaker("Luma"), "Clara")
        self.assertEqual(app.display_chat_speaker("Clara"), "Clara")
        self.assertEqual(app.display_chat_speaker("Tú"), "Tú")

    def test_task_proposal_extracts_spanish_date_time_and_subject_without_saving(self) -> None:
        db = create_test_db()
        db.execute("INSERT INTO classes(name,weekday,start_time) VALUES(?,?,?)", ("Biología", 1, "08:00"))
        db.commit()
        dummy = SimpleNamespace(db=db)
        proposal = app.AssistantApp.parse_task_proposal(
            dummy,
            "me dejaron una tarea de Biología entregar práctica de células el 25 de octubre a las 4:30 pm",
            today=date(2026, 10, 17),
        )
        self.assertEqual(proposal["subject"], "Biología")
        self.assertEqual(proposal["due_date"], "2026-10-25")
        self.assertEqual(proposal["due_time"], "16:30")
        self.assertEqual(proposal["title"], "práctica de células")
        self.assertEqual(db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 0)

    def test_task_proposal_supports_relative_days_and_next_same_weekday(self) -> None:
        db = create_test_db()
        dummy = SimpleNamespace(db=db)
        saturday = date(2026, 10, 17)
        in_three_days = app.AssistantApp.parse_task_proposal(dummy, "hacer ejercicios dentro de 3 días", today=saturday)
        sunday_task = app.AssistantApp.parse_task_proposal(dummy, "me dejaron exposición el domingo a las 09:00", today=saturday)
        self.assertEqual((in_three_days["title"], in_three_days["due_date"]), ("ejercicios", "2026-10-20"))
        self.assertEqual((sunday_task["title"], sunday_task["due_date"], sunday_task["due_time"]), ("exposición", "2026-10-18", "09:00"))

    def test_local_document_scan_lists_only_allowed_metadata_and_respects_cancel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "estudio"
            nested = root / "semestre"
            protected = root / "OneDrive"
            hidden = root / ".oculto"
            nested.mkdir(parents=True)
            protected.mkdir()
            hidden.mkdir()
            (root / "apuntes_biologia.pdf").write_bytes(b"%PDF-1.4 fake")
            (nested / "guia.md").write_text("# Guia", encoding="utf-8")
            (root / "script.py").write_text("print('no')", encoding="utf-8")
            (root / "instalador.exe").write_bytes(b"MZ")
            (protected / "nube.pdf").write_bytes(b"cloud")
            (hidden / "secreto.txt").write_text("hidden", encoding="utf-8")

            found = app.scan_local_documents(root, "biologia", ".pdf", inventory=False)
            self.assertEqual(found["status"], "complete")
            self.assertEqual([item["name"] for item in found["results"]], ["apuntes_biologia.pdf"])

            inventory = app.scan_local_documents(root, inventory=True, recursive=True)
            self.assertEqual([item["relative"] for item in inventory["results"]], ["apuntes_biologia.pdf", "semestre", str(Path("semestre") / "guia.md")])

            cancel = threading.Event()
            cancel.set()
            cancelled = app.scan_local_documents(root, inventory=True, cancel_event=cancel)
            self.assertEqual(cancelled["status"], "cancelled")

    def test_local_search_root_rejects_protected_or_hidden_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cloud = base / "Dropbox"
            cloud.mkdir()
            hidden = base / ".privado"
            hidden.mkdir()
            nested_under_hidden = hidden / "documentos"
            nested_under_hidden.mkdir()
            with self.assertRaises(ValueError):
                app.validate_local_search_root(cloud)
            with self.assertRaises(ValueError):
                app.validate_local_search_root(hidden)
            with self.assertRaises(ValueError):
                app.validate_local_search_root(nested_under_hidden)

    def test_open_document_validation_checks_root_type_and_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "tareas"
            outside = Path(tmp) / "afuera"
            root.mkdir()
            outside.mkdir()
            allowed = root / "lectura.pdf"
            blocked = root / "ejecutable.exe"
            external = outside / "otro.pdf"
            allowed.write_bytes(b"12345")
            blocked.write_bytes(b"MZ")
            external.write_bytes(b"12345")
            info = allowed.stat()
            file_id = (info.st_dev, info.st_ino)
            self.assertEqual(app.validate_local_document_for_open(root, allowed, info.st_size, info.st_mtime_ns, file_id), allowed.resolve())
            self.assertEqual(app.validate_local_document_for_open(root, allowed, info.st_size, info.st_mtime_ns, (0, 0)), allowed.resolve())
            with self.assertRaises(ValueError):
                app.validate_local_document_for_open(root, allowed, info.st_size + 1, info.st_mtime_ns, file_id)
            with self.assertRaises(ValueError):
                app.validate_local_document_for_open(root, blocked, blocked.stat().st_size, blocked.stat().st_mtime_ns)
            with self.assertRaises(ValueError):
                app.validate_local_document_for_open(root, external, external.stat().st_size, external.stat().st_mtime_ns)

    def test_local_move_prepares_and_validates_without_executing_real_move(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "origen"
            dest_root = Path(tmp) / "destino"
            source_root.mkdir()
            dest_root.mkdir()
            doc = source_root / "ensayo.docx"
            doc.write_bytes(b"contenido")
            info = doc.stat()

            plan = app.prepare_local_move(source_root, doc, dest_root, info.st_size, info.st_mtime_ns, (info.st_dev, info.st_ino))
            self.assertEqual(Path(plan["source"]), doc.resolve())
            self.assertEqual(Path(plan["destination"]), (dest_root / doc.name).resolve())
            self.assertTrue(doc.exists())  # No se ejecuta movimiento real durante pruebas automatizadas

            with self.assertRaises(OSError):
                app.execute_local_move(plan, platform_name="linux")
            self.assertTrue(doc.exists())

            collision = dest_root / doc.name
            collision.write_bytes(b"otro")
            fresh = doc.stat()
            with self.assertRaises(FileExistsError):
                app.prepare_local_move(source_root, doc, dest_root, fresh.st_size, fresh.st_mtime_ns, (fresh.st_dev, fresh.st_ino))
            with self.assertRaises(ValueError):
                app.prepare_local_move(source_root, doc, source_root, fresh.st_size, fresh.st_mtime_ns, (fresh.st_dev, fresh.st_ino))

    def test_application_allowlist_accepts_only_gui_exe_under_standard_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            programs = Path(tmp) / "Programs" / "MiApp"
            outside = Path(tmp) / "Descargas"
            programs.mkdir(parents=True)
            outside.mkdir()
            gui_exe = programs / "MiEditor.exe"
            console_exe = programs / "Consola.exe"
            blocked_exe = programs / "powershell.exe"
            installer_exe = programs / "MiAppSetup.exe"
            outside_exe = outside / "MiEditor.exe"
            write_minimal_pe(gui_exe, subsystem=2)
            write_minimal_pe(console_exe, subsystem=3)
            write_minimal_pe(blocked_exe, subsystem=2)
            write_minimal_pe(installer_exe, subsystem=2)
            write_minimal_pe(outside_exe, subsystem=2)

            with mock.patch.dict(os.environ, {"ProgramFiles": str(Path(tmp) / "Programs"), "ProgramFiles(x86)": "", "ProgramW6432": "", "LOCALAPPDATA": ""}):
                with mock.patch.object(app, "ctypes", SimpleNamespace(windll=SimpleNamespace(kernel32=SimpleNamespace(GetDriveTypeW=lambda _root: 3)))):
                    with mock.patch("os.path.splitdrive", return_value=("C:", "\\Programs\\MiApp\\MiEditor.exe")):
                        record = app.validate_local_application(gui_exe, platform_name="win32")
                        self.assertEqual(record["name"], "MiEditor.exe")
                        launched = []
                        app.launch_allowed_application(record, platform_name="win32", popen=lambda args, **kw: launched.append((args, kw)))
                        self.assertEqual(launched[0][0], [str(gui_exe.resolve())])
                        self.assertFalse(launched[0][1]["shell"])
                        for invalid in (console_exe, blocked_exe, installer_exe, outside_exe):
                            with self.assertRaises(ValueError):
                                app.validate_local_application(invalid, platform_name="win32")
                        write_minimal_pe(gui_exe, subsystem=2)
                        gui_exe.write_bytes(gui_exe.read_bytes() + b"\0")
                        with self.assertRaises(ValueError):
                            app.launch_allowed_application(record, platform_name="win32", popen=lambda *_a, **_k: None)

    def test_chat_intent_validator_enforces_closed_schema_and_safe_queries(self) -> None:
        valid_search = app.validate_chat_intent('{"intent":"file_search","query":"biologia","extension":".pdf"}')
        self.assertEqual(valid_search, {"intent": "file_search", "query": "biologia", "extension": ".pdf"})
        valid_task = app.validate_chat_intent('{"intent":"task_draft","title":"Leer capítulo","subject":"Historia","due_date":"2026-10-20","due_time":"17:00","description":null}')
        self.assertEqual(valid_task["title"], "Leer capítulo")
        for invalid in (
            '{"intent":"run_app","name":"notepad.exe"}',
            '{"intent":"file_search","query":"C:\\\\Users\\\\alumno\\\\secreto.pdf","extension":".pdf"}',
            '{"intent":"file_search","query":"../secreto","extension":".pdf"}',
            '{"intent":"file_open","query":"script","extension":".exe"}',
            '{"intent":"block_draft","title":"Estudio","block_date":"2026-10-20","start_time":"18:00","end_time":"17:00","notes":null}',
            '{"intent":"general","response":"hola","extra":1}',
            'no es json',
        ):
            self.assertIsNone(app.validate_chat_intent(invalid))

    def test_action_history_csv_exports_only_category_and_outcome(self) -> None:
        db = create_test_db()
        db.execute("INSERT INTO action_events(action,outcome,created_at) VALUES(?,?,?)", ("Abrir documento permitido", "Windows recibió la solicitud; nombre/ruta omitidos", "2026-10-18T12:00:00"))
        db.commit()
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "acciones.csv"
            self.assertEqual(app.export_action_history_csv(db, csv_path), 1)
            with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
            self.assertEqual(rows[0], ["Fecha", "Acción", "Resultado"])
            self.assertEqual(rows[1][1], "Abrir documento permitido")
            self.assertNotIn("C:\\", rows[1][2])

    def test_backup_extractor_enforces_expected_members_and_size_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            valid_zip = base / "valido.zip"
            with zipfile.ZipFile(valid_zip, "w") as archive:
                archive.writestr("asistente.db", b"sqlite-bytes")
                archive.writestr("settings.json", '{"morning_time":"07:00"}')
            db_path, settings_path = app.extract_validated_backup(valid_zip, base / "out_ok")
            self.assertEqual(db_path.read_bytes(), b"sqlite-bytes")
            self.assertTrue(settings_path and settings_path.exists())

            unexpected_zip = base / "extra.zip"
            with zipfile.ZipFile(unexpected_zip, "w") as archive:
                archive.writestr("asistente.db", b"sqlite-bytes")
                archive.writestr("../escape.txt", b"no")
            with self.assertRaises(ValueError):
                app.extract_validated_backup(unexpected_zip, base / "out_extra")

            oversized_zip = base / "grande.zip"
            with zipfile.ZipFile(oversized_zip, "w") as archive:
                archive.writestr("asistente.db", b"0123456789")
            with self.assertRaises(ValueError):
                app.extract_validated_backup(oversized_zip, base / "out_big", max_database_bytes=5)

    def test_normalize_allowed_applications_caps_and_deduplicates(self) -> None:
        entries = [
            {"name": f"App{i}.exe", "path": str(Path("/Programas") / f"App{i}.exe"), "size": 10 + i, "mtime_ns": 20 + i, "file_id": [1, i]}
            for i in range(15)
        ]
        entries.append(entries[0])
        entries.append({"path": "relativa.exe", "size": 1, "mtime_ns": 1, "file_id": [1, 1]})
        cleaned = json.loads(app.normalize_allowed_applications(json.dumps(entries)))
        self.assertEqual(len(cleaned), app.MAX_ALLOWED_APPLICATIONS)

    # =========================================================================
    # 2. Pruebas nuevas de CLARA Unificada v2.0.0 y rechazos de seguridad
    # =========================================================================
    def test_default_settings_colima_0700_and_auto_downloads_disabled(self) -> None:
        self.assertEqual(app.DEFAULT_SETTINGS["morning_time"], "07:00")
        self.assertEqual(app.DEFAULT_SETTINGS["weather_location"], "Colima, Colima, México")
        self.assertEqual(app.DEFAULT_SETTINGS["auto_speak_responses"], "true")
        self.assertEqual(app.DEFAULT_SETTINGS["chat_history_enabled"], "false")
        self.assertEqual(app.DEFAULT_SETTINGS["calendar_ics_path"], "")
        self.assertFalse(app.AUTO_DOWNLOADS_ENABLED)

    def test_api_key_leak_detection_and_settings_storage_rejection(self) -> None:
        fake_vt_key = "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0"
        self.assertEqual(len(fake_vt_key), 64)
        self.assertTrue(app.contains_potential_api_key(fake_vt_key))
        self.assertTrue(app.contains_potential_api_key(f"mi clave de virustotal es {fake_vt_key}"))
        self.assertTrue(app.contains_potential_api_key("virustotal_api_key = secret_token_1234567890"))
        self.assertFalse(app.contains_potential_api_key("¿qué tengo hoy en mi agenda de clases?"))

        with self.assertRaises(ValueError):
            app.sanitize_settings_for_storage({"weather_location": fake_vt_key})

        sanitized = app.sanitize_settings_for_storage(
            {
                "morning_time": "07:00",
                "weather_location": "Colima, Colima, México",
                "virustotal_api_key": fake_vt_key,
                "token_secreto": "12345",
            }
        )
        self.assertNotIn("virustotal_api_key", sanitized)
        self.assertNotIn("token_secreto", sanitized)
        self.assertEqual(set(sanitized.keys()), set(app.DEFAULT_SETTINGS.keys()))

    def test_official_resource_disclosure_and_sha256_verification(self) -> None:
        disclosure = app.format_resource_disclosure("vosk-model-small-es-0.42")
        self.assertIn("https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip", disclosure)
        self.assertIn("0.42", disclosure)
        self.assertIn("39 MB", disclosure)
        self.assertIn("Apache-2.0", disclosure)
        self.assertIn("DESACTIVADAS", disclosure)

        with self.assertRaises(ValueError):
            app.format_resource_disclosure("https://sitio-arbitrario.example.com/script.exe")

        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "recurso.bin"
            payload = b"contenido verificado por hash"
            artifact.write_bytes(payload)
            expected_hash = hashlib.sha256(payload).hexdigest()
            self.assertTrue(app.verify_resource_sha256(artifact, expected_hash))
            with self.assertRaises(ValueError):
                app.verify_resource_sha256(artifact, "0" * 64)
            with self.assertRaises(ValueError):
                app.verify_resource_sha256(artifact, "hash_invalido")

    def test_news_feed_html_cleaning_and_offline_cache_roundtrip(self) -> None:
        rss_with_html = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel>
        <item><title>&lt;b&gt;Avance&lt;/b&gt; en energ&amp;iacute;a solar</title><link>https://example.com/solar</link><source>Ciencia &amp;amp; Salud</source></item>
        </channel></rss>"""
        parsed = app.parse_news_feed(rss_with_html, "Fuente", 5)
        self.assertEqual(parsed, [{"title": "Avance en energía solar", "source": "Ciencia & Salud", "link": "https://example.com/solar"}])

        with tempfile.TemporaryDirectory() as tmp:
            cache_file = Path(tmp) / "news_cache.json"
            now = datetime(2026, 10, 22, 8, 0, 0)
            app.save_news_cache(parsed, "Google News México", "Ciencia", cache_path=cache_file, now=now)
            loaded = app.load_news_cache(cache_path=cache_file, max_age_hours=24.0, now=now + timedelta(hours=2))
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded["items"][0]["title"], "Avance en energía solar")
            expired = app.load_news_cache(cache_path=cache_file, max_age_hours=24.0, now=now + timedelta(hours=30))
            self.assertIsNone(expired)

    def test_spanish_voice_selection_and_tts_failure_explanations(self) -> None:
        voices = [
            SimpleNamespace(id="HKEY_EN_DAVID", name="Microsoft David Desktop - English (United States)", languages=["en_US"]),
            SimpleNamespace(id="HKEY_ES_HELENA", name="Microsoft Helena Desktop - Spanish (Spain)", languages=["es_ES"]),
            SimpleNamespace(id="HKEY_ES_SABINA", name="Microsoft Sabina Desktop - Spanish (Mexico)", languages=["es_MX"]),
        ]
        self.assertEqual(app.select_spanish_voice_id(voices), "HKEY_ES_SABINA")
        self.assertIsNone(app.select_spanish_voice_id([]))

        msg_missing = app.explain_tts_failure("no_pyttsx3")
        self.assertIn("pyttsx3", msg_missing)
        self.assertIn("respuesta escrita se conserva", msg_missing)

        msg_no_voices = app.explain_tts_failure("no_voices")
        self.assertIn("ninguna voz", msg_no_voices)
        self.assertIn("respuesta escrita se conserva", msg_no_voices)

    def test_voice_diagnostics_static_never_activates_microphone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            diag = app.collect_voice_diagnostics(Path(tmp))
            self.assertFalse(diag["microphone_activated"])
            self.assertFalse(diag["model_present"])
            model_dir = Path(tmp) / "models" / "vosk-model-small-es-0.42"
            model_dir.mkdir(parents=True)
            diag_with_model = app.collect_voice_diagnostics(Path(tmp))
            self.assertTrue(diag_with_model["model_present"])
            self.assertFalse(diag_with_model["microphone_activated"])

    def test_sphere_expands_only_while_speaking(self) -> None:
        idle_r = app.sphere_radius_for_state("idle", 150, 112)
        listening_r = app.sphere_radius_for_state("listening", 150, 112)
        speaking_r = app.sphere_radius_for_state("speaking", 150, 112)
        self.assertEqual(idle_r, listening_r)
        self.assertGreater(speaking_r, idle_r)
        self.assertGreater(speaking_r, listening_r)

    def test_local_nlu_router_classifies_natural_spanish_intents(self) -> None:
        today = date(2026, 10, 22)
        self.assertEqual(app.classify_local_natural_intent("¿Qué sigue hoy?", today), {"intent": "next_commitment"})
        self.assertEqual(app.classify_local_natural_intent("¿Cómo va mi día?", today), {"intent": "agenda_query", "date": "2026-10-22"})
        self.assertEqual(app.classify_local_natural_intent("Dame las noticias de ciencia", today), {"intent": "news_query", "topic": "Ciencia"})
        self.assertEqual(app.classify_local_natural_intent("¿Cómo está el clima?", today), {"intent": "weather_query"})
        self.assertEqual(app.classify_local_natural_intent("¿Qué clases tengo mañana?", today), {"intent": "classes_query", "date": "2026-10-23"})
        self.assertEqual(app.classify_local_natural_intent("Mis rutinas activas", today), {"intent": "routines_query"})
        self.assertEqual(app.classify_local_natural_intent("Repite la última respuesta", today), {"intent": "repeat_last"})
        self.assertEqual(app.classify_local_natural_intent("Diagnóstico de voz", today), {"intent": "voice_diagnostics"})
        self.assertEqual(app.classify_local_natural_intent("¿Qué puedes hacer?", today), {"intent": "help"})
        self.assertEqual(app.classify_local_natural_intent("Inventaría una carpeta recursivamente", today), {"intent": "file_inventory", "recursive": True})
        self.assertEqual(
            app.classify_local_natural_intent("Busca mi documento pdf de biología", today),
            {"intent": "file_search", "query": "biología", "extension": ".pdf"},
        )
        greeting_status = app.classify_local_natural_intent("hola, que haces.", today)
        self.assertIsNotNone(greeting_status)
        self.assertEqual(greeting_status["intent"], "general")
        self.assertIn("local-first", greeting_status["response"])
        identity = app.classify_local_natural_intent("¿Quién eres?", today)
        self.assertIsNotNone(identity)
        self.assertEqual(identity["intent"], "general")
        self.assertIn("CLARA-V", identity["response"])
        day_info = app.classify_local_natural_intent("¿Qué día es hoy?", today)
        self.assertIsNotNone(day_info)
        self.assertEqual(day_info["intent"], "general")
        self.assertIn("2026-10-22", day_info["response"])

    def test_local_nlu_router_rejects_negations_informational_and_unsafe_commands(self) -> None:
        today = date(2026, 10, 22)
        for negated_or_info in (
            "No busques mi pdf de biología",
            "Por favor no abras ningún archivo",
            "No quiero que muevas documentos",
            "¿Cómo se mueve un archivo en Clara?",
            "¿Cómo busco documentos PDF?",
        ):
            intent = app.classify_local_natural_intent(negated_or_info, today)
            self.assertIsNotNone(intent)
            self.assertEqual(intent["intent"], "informational")

        for unsafe_request in (
            "Ejecuta powershell.exe ahora",
            "Corre el script limpiar.bat",
            "Abre cmd y lanza un comando",
            "Apaga la computadora",
            "Descarga e instala setup.exe",
            "Busca mi archivo instalador.exe",
        ):
            intent = app.classify_local_natural_intent(unsafe_request, today)
            self.assertIsNotNone(intent)
            self.assertEqual(intent["intent"], "blocked_unsafe")

    def test_next_commitment_classes_and_routines_summaries(self) -> None:
        db = create_test_db()
        thursday = date(2026, 10, 22)  # weekday == 3
        db.execute("INSERT INTO classes(name,weekday,start_time,end_time,location) VALUES(?,?,?,?,?)", ("Física", 3, "10:00", "11:00", "Aula 4"))
        db.execute("INSERT INTO plan_blocks(title,block_date,start_time,end_time,created_at) VALUES(?,?,?,?,?)", ("Repaso cálculo", thursday.isoformat(), "12:00", "12:45", "2026-10-22T08:00:00"))
        db.execute("INSERT INTO tasks(title,subject,due_date,due_time,priority,done,created_at) VALUES(?,?,?,?,?,0,?)", ("Entregar reporte", "Física", thursday.isoformat(), "16:00", "Alta", "2026-10-22T08:00:00"))
        db.execute("INSERT INTO routines(title,subject,weekdays,reminder_time,active,created_at) VALUES(?,?,?,?,1,?)", ("Revisar apuntes", "Física", "0,2,3", "19:00", "2026-10-01T08:00:00"))
        db.commit()

        summary_morning = app.build_next_commitment_summary(db, datetime(2026, 10, 22, 9, 30))
        self.assertIn("en 30 min", summary_morning)
        self.assertIn("Física", summary_morning)
        self.assertIn("Repaso cálculo", summary_morning)

        classes_text = app.build_classes_summary(db, thursday)
        self.assertIn("10:00–11:00 — Física · Aula 4", classes_text)

        routines_text = app.build_routines_summary(db)
        self.assertIn("Revisar apuntes", routines_text)
        self.assertIn("Activa", routines_text)

    def test_preview_viernes_migration_is_read_only_and_never_infers_routines(self) -> None:
        db = create_test_db()
        db.execute(
            "INSERT INTO tasks(title,due_date,due_time,priority,done,created_at) VALUES(?,?,?,?,0,?)",
            ("Tarea ya existente", "2026-10-25", "10:00", "Normal", "2026-10-20T08:00:00"),
        )
        db.commit()

        with tempfile.TemporaryDirectory() as tmp:
            agenda_path = Path(tmp) / "viernes_agenda.json"
            config_path = Path(tmp) / "viernes_config.json"
            agenda_path.write_text(
                json.dumps(
                    {
                        "events": [
                            {"id": 1, "title": "Tarea ya existente", "date": "2026-10-25", "time": "10:00", "recurrence": "once"},
                            {"id": 2, "title": "Entregar proyecto final", "date": "2026-10-28", "time": "14:00", "recurrence": "once"},
                            {"id": 3, "title": "Rutina semanal de Viernes", "date": "2026-10-23", "time": "08:00", "recurrence": "weekly"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            config_path.write_text(
                json.dumps({"class_schedule": {"monday": ["Bases de datos", "Inglés"]}}),
                encoding="utf-8",
            )

            preview = app.preview_viernes_migration(agenda_path, config_path, db)
            self.assertEqual(preview["writes_performed"], 0)
            self.assertTrue(preview["reversible"])
            self.assertEqual(preview["skipped_duplicates"], 1)
            self.assertEqual(preview["skipped_recurring"], 1)
            self.assertEqual(len(preview["candidate_tasks"]), 1)
            self.assertEqual(preview["candidate_tasks"][0]["title"], "Entregar proyecto final")
            self.assertEqual(len(preview["informational_classes"]), 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM routines").fetchone()[0], 0)

    def test_validate_chat_intent_supports_unified_intents_and_rejects_invalid_topics(self) -> None:
        self.assertEqual(app.validate_chat_intent('{"intent":"next_commitment"}'), {"intent": "next_commitment"})
        self.assertEqual(app.validate_chat_intent('{"intent":"weather_query"}'), {"intent": "weather_query"})
        self.assertEqual(app.validate_chat_intent('{"intent":"news_query","topic":"Tecnología"}'), {"intent": "news_query", "topic": "Tecnología"})
        self.assertEqual(app.validate_chat_intent('{"intent":"news_query","topic":null}'), {"intent": "news_query", "topic": None})
        self.assertIsNone(app.validate_chat_intent('{"intent":"news_query","topic":"Criptomonedas"}'))

    def test_append_chat_speaks_responses_and_summaries_and_blocks_api_keys(self) -> None:
        db = create_test_db()
        db.execute(
            """CREATE TABLE chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            speaker TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
        )
        db.commit()

        class _TextSink:
            def configure(self, **_kwargs): pass
            def insert(self, *_args): pass
            def see(self, *_args): pass

        spoken: list[str] = []
        fake_app = SimpleNamespace(
            chat_log=_TextSink(),
            settings={"chat_history_enabled": "true", "auto_speak_responses": "true"},
            db=db,
            last_assistant_response="",
            ollama_status=SimpleNamespace(configure=lambda **_kwargs: None),
            _start_tts=lambda text, manual=False: spoken.append(text),
        )
        app.AssistantApp.append_chat(fake_app, "Tú", "hola")
        app.AssistantApp.append_chat(fake_app, "Asistente", "respuesta conversacional")
        app.AssistantApp.append_chat(fake_app, "Rutina matutina", "resumen de agenda de hoy")
        app.AssistantApp.append_chat(fake_app, "Clima y noticias", "resumen de clima y titulares")

        # Tanto respuestas como resúmenes de rutina/noticias se leen en voz alta cuando la lectura automática está activa
        self.assertEqual(spoken, ["respuesta conversacional", "resumen de agenda de hoy", "resumen de clima y titulares"])
        self.assertEqual(fake_app.last_assistant_response, "resumen de clima y titulares")

        # Una clave potencial de VirusTotal nunca se persiste en chat_history
        fake_vt_key = "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0"
        app.AssistantApp.append_chat(fake_app, "Tú", fake_vt_key)
        saved_messages = [row["content"] for row in db.execute("SELECT content FROM chat_history").fetchall()]
        self.assertEqual(saved_messages, ["hola", "respuesta conversacional"])
        self.assertNotIn(fake_vt_key, saved_messages)

    def test_etapa1_connect_db_all_tables_and_settings_roundtrip_and_tamper_defense(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prev = (app.DATA_DIR, app.DB_PATH, app.SETTINGS_PATH)
            app.DATA_DIR, app.DB_PATH, app.SETTINGS_PATH = root, root / "asistente.db", root / "settings.json"
            try:
                db = app.connect_db()
                tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                expected_tables = {
                    "tasks",
                    "classes",
                    "class_exceptions",
                    "memories",
                    "security_events",
                    "action_events",
                    "chat_history",
                    "routines",
                    "reminder_events",
                    "reminder_actions",
                    "plan_blocks",
                }
                self.assertTrue(expected_tables.issubset(tables))
                db.close()

                # Valores por defecto exactos en instalación limpia
                defaults = app.load_settings()
                self.assertEqual(defaults["morning_time"], "07:00")
                self.assertEqual(defaults["weather_location"], "Colima, Colima, México")

                # Edición válida de ubicación y hora
                edited = dict(defaults)
                edited["morning_time"] = "06:45"
                edited["weather_location"] = "Manzanillo, Colima, México"
                app.save_settings(edited)
                reloaded = app.load_settings()
                self.assertEqual(reloaded["morning_time"], "06:45")
                self.assertEqual(reloaded["weather_location"], "Manzanillo, Colima, México")

                # Defensa ante manipulación manual de settings.json en disco con claves API
                fake_vt_key = "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0"
                app.SETTINGS_PATH.write_text(
                    json.dumps({"weather_location": fake_vt_key, "virustotal_api_key": fake_vt_key, "morning_time": "99:99"}),
                    encoding="utf-8",
                )
                recovered = app.load_settings()
                self.assertEqual(recovered["weather_location"], "Colima, Colima, México")
                self.assertEqual(recovered["morning_time"], "07:00")
                self.assertNotIn("virustotal_api_key", recovered)
            finally:
                app.DATA_DIR, app.DB_PATH, app.SETTINGS_PATH = prev

    def test_etapa2_apply_chat_intent_and_send_chat_local_and_ollama_flows(self) -> None:
        db = create_test_db()
        db.execute("INSERT INTO classes(name,weekday,start_time,end_time,location) VALUES(?,?,?,?,?)", ("Química", 3, "18:00", "19:00", "Lab 2"))
        db.commit()

        chat_messages: list[tuple[str, str]] = []
        actions_called: list[tuple[str, object]] = []

        class _FakeEntry:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def delete(self, *_args) -> None:
                self.value = ""

        fake_app = SimpleNamespace(
            db=db,
            ai_busy=False,
            settings={"weather_location": "Colima, Colima, México", "auto_speak_responses": "false", "chat_history_enabled": "false"},
            last_assistant_response="Respuesta previa de prueba",
            chat_input=_FakeEntry(),
            model_var=SimpleNamespace(get=lambda: ""),
            append_chat=lambda speaker, msg, **_kw: chat_messages.append((speaker, msg)),
            speak_last_response=lambda: actions_called.append(("speak_last_response", None)),
            open_voice_diagnostics=lambda: actions_called.append(("open_voice_diagnostics", None)),
            show_morning_briefing=lambda: actions_called.append(("show_morning_briefing", None)),
            fetch_and_present_news=lambda topic_override=None: actions_called.append(("news", topic_override)),
            fetch_and_present_weather=lambda: actions_called.append(("weather", None)),
            open_week_agenda=lambda: actions_called.append(("week_agenda", None)),
            add_task=lambda preset="", prefill=None: actions_called.append(("add_task", prefill)),
            open_plan_block_form=lambda _parent, prefill=None: actions_called.append(("open_plan_block_form", prefill)),
            start_afternoon_plan=lambda: actions_called.append(("start_afternoon_plan", None)),
            open_local_file_tools=lambda intent=None: actions_called.append(("open_local_file_tools", intent)),
            day_agenda_summary=lambda d: f"Agenda para {d.isoformat()}",
            parse_task_proposal=lambda txt: app.AssistantApp.parse_task_proposal(SimpleNamespace(db=db), txt, today=date(2026, 10, 22)),
            parse_block_request=lambda txt: app.AssistantApp.parse_block_request(SimpleNamespace(db=db), txt),
        )
        fake_app.apply_chat_intent = lambda u, i: app.AssistantApp.apply_chat_intent(fake_app, u, i)

        # 1. Validación de classes_query con fecha y sin fecha en validate_chat_intent
        self.assertEqual(
            app.validate_chat_intent('{"intent":"classes_query","date":"2026-10-22"}'),
            {"intent": "classes_query", "date": "2026-10-22"},
        )
        self.assertEqual(
            app.validate_chat_intent('{"intent":"classes_query","date":null}'),
            {"intent": "classes_query", "date": None},
        )
        self.assertIsNone(app.validate_chat_intent('{"intent":"file_search","query":"..","extension":".pdf"}'))

        # 2. Ejecución de apply_chat_intent en modo lectura y modo borrador confirmable
        res_classes = fake_app.apply_chat_intent("mis clases", {"intent": "classes_query", "date": "2026-10-22"})
        self.assertIn("Química", res_classes)
        fake_app.apply_chat_intent("noticias", {"intent": "news_query", "topic": "Ciencia"})
        self.assertIn(("news", "Ciencia"), actions_called)
        fake_app.apply_chat_intent("clima", {"intent": "weather_query"})
        self.assertIn(("weather", None), actions_called)
        fake_app.apply_chat_intent("repite", {"intent": "repeat_last"})
        self.assertIn(("speak_last_response", None), actions_called)
        fake_app.apply_chat_intent("diagnóstico", {"intent": "voice_diagnostics"})
        self.assertIn(("open_voice_diagnostics", None), actions_called)

        # 3. Flujo completo de send_chat: bloqueo de clave API y ejecución directa de tareas, clases, bloques y rutinas
        fake_vt_key = "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0"
        fake_app.chat_input = _FakeEntry(f"mi clave virustotal es {fake_vt_key}")
        app.AssistantApp.send_chat(fake_app)
        self.assertTrue(any("no envíes ni pegues claves API" in msg for _spk, msg in chat_messages))

        fake_app.chat_input = _FakeEntry("me dejaron una tarea de Química entregar práctica mañana a las 16:00")
        app.AssistantApp.send_chat(fake_app)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM tasks WHERE done=0").fetchone()[0], 1)

        fake_app.chat_input = _FakeEntry("marca como hecha la tarea entregar práctica")
        app.AssistantApp.send_chat(fake_app)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM tasks WHERE done=1").fetchone()[0], 1)

        fake_app.chat_input = _FakeEntry("agrega mi clase de Cálculo los lunes y miércoles de 08:00 a 10:00 en Aula 4")
        app.AssistantApp.send_chat(fake_app)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM classes WHERE name='Cálculo'").fetchone()[0], 2)

        fake_app.chat_input = _FakeEntry("reserva de 15:00 a 16:00 mañana para estudiar Física")
        app.AssistantApp.send_chat(fake_app)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM plan_blocks").fetchone()[0], 1)

        fake_app.chat_input = _FakeEntry("agrega rutina repasar inglés lunes y miércoles a las 19:00")
        app.AssistantApp.send_chat(fake_app)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM routines").fetchone()[0], 1)

        # 4. Si Ollama está ocupado (ai_busy=True), enviar un nuevo mensaje cancela la espera previa y responde de inmediato
        fake_app.ai_busy = True
        fake_app.ollama_request_id = 1
        fake_app.cancel_event = threading.Event()
        fake_app.response_lock = threading.Lock()
        fake_app.active_response = None
        fake_app.ai_results = app.queue.Queue()
        fake_app.ai_results.put(("answer_chunk", "fragmento obsoleto"))
        fake_app.ollama_status = SimpleNamespace(configure=lambda **_kw: None)
        fake_app._cancel_pending_ollama_for_new_message = lambda: app.AssistantApp._cancel_pending_ollama_for_new_message(fake_app)
        fake_app.chat_input = _FakeEntry("hola, que haces.")
        app.AssistantApp.send_chat(fake_app)
        self.assertFalse(fake_app.ai_busy)
        self.assertTrue(fake_app.cancel_event.is_set())
        self.assertEqual(fake_app.ollama_request_id, 2)
        self.assertTrue(fake_app.ai_results.empty())
        self.assertTrue(any(spk == "Asistente" and "local-first" in msg for spk, msg in chat_messages))

    def test_etapa3_voice_subsystem_tts_repeat_failure_and_push_to_talk_editable_transcript(self) -> None:
        # 1. Limpieza de texto para TTS conservando intactos los enlaces escritos
        raw_summary = "• Avance científico\n  Fuente: BBC Mundo\n  Enlace: https://example.com/noticia-1"
        spoken_text = app.prepare_text_for_speech(raw_summary)
        self.assertIn("Avance científico", spoken_text)
        self.assertIn("Fuente: BBC Mundo", spoken_text)
        self.assertNotIn("https://example.com/noticia-1", spoken_text)

        # 2. Fallo controlado de TTS: muestra explicación y conserva la respuesta escrita
        chat_buffer: list[str] = []
        sphere_states: list[str] = []
        status_texts: list[str] = []

        class _LogRecorder:
            def configure(self, **_kw): pass
            def insert(self, _pos, txt, *_tags): chat_buffer.append(str(txt))
            def see(self, *_args): pass

        class _EditableEntry:
            def __init__(self) -> None:
                self.value = ""
                self.focused = False

            def delete(self, *_args) -> None:
                self.value = ""

            def insert(self, _idx, text: str) -> None:
                self.value = text

            def focus_set(self) -> None:
                self.focused = True

        entry_box = _EditableEntry()
        send_chat_called = []

        fake_app = SimpleNamespace(
            voice_active=False,
            tts_active=False,
            last_assistant_response="Resumen escrito que debe conservarse",
            chat_log=_LogRecorder(),
            chat_input=entry_box,
            ai_results=app.queue.Queue(),
            voice_stop=threading.Event(),
            tts_cancel_event=threading.Event(),
            set_sphere_state=lambda st: sphere_states.append(st),
            voice_status=SimpleNamespace(
                configure=lambda **kw: status_texts.append(kw.get("text", "")),
                cget=lambda _k: "Micrófono activo",
            ),
            voice_button=SimpleNamespace(configure=lambda **_kw: None),
            after=lambda *_args: None,
            process_ai_results=lambda: None,
            send_chat=lambda: send_chat_called.append(True),
            append_chat=lambda spk, txt, **_kw: chat_buffer.append(f"{spk}: {txt}\n"),
        )
        fake_app._report_tts_failure = lambda reason, manual=False: app.AssistantApp._report_tts_failure(fake_app, reason, manual=False)
        fake_app._start_tts = lambda txt, manual=False: app.AssistantApp._start_tts(fake_app, txt, manual=manual)

        with mock.patch("importlib.util.find_spec", return_value=None):
            app.AssistantApp.speak_last_response(fake_app)

        full_log = "".join(chat_buffer)
        self.assertIn("No pude leer la respuesta en voz alta", full_log)
        self.assertIn("Tu respuesta escrita se conserva íntegra", full_log)
        self.assertEqual(sphere_states[-1], "idle")

        # 3. Push-to-Talk coloca transcripción editable en chat_input y NUNCA auto-envía
        fake_app.voice_active = True
        fake_app.ai_results.put(("voice_transcript", "agregar tarea de matemáticas para mañana"))
        fake_app.ai_results.put(("voice_stopped", "Micrófono apagado"))
        app.AssistantApp.process_ai_results(fake_app)

        self.assertEqual(entry_box.value, "agregar tarea de matemáticas para mañana")
        self.assertTrue(entry_box.focused)
        self.assertEqual(send_chat_called, [])  # Nunca se envía sin pulsar Enviar manualmente
        self.assertFalse(fake_app.voice_active)  # Micrófono vuelve a quedar apagado

    def test_etapa4_adaptive_geometry_sphere_states_and_honest_emergency_stop(self) -> None:
        # 1. Geometría adaptativa en pantallas pequeñas y escalado Windows 100%, 125% y 150%
        for sw, sh in ((1920, 1080), (1366, 768), (1092, 614), (910, 512), (800, 480)):
            spec = app.compute_adaptive_window_geometry(sw, sh)
            self.assertLessEqual(int(spec["width"]), sw)
            self.assertLessEqual(int(spec["height"]), sh)
            self.assertLessEqual(int(spec["min_width"]), int(spec["width"]))
            self.assertLessEqual(int(spec["min_height"]), int(spec["height"]))
            self.assertIn(f"{spec['width']}x{spec['height']}+", str(spec["geometry"]))

        # 2. Esfera compacta en idle/listening y expandida únicamente en speaking
        r_idle = app.sphere_radius_for_state("idle", 150, 112)
        r_listening = app.sphere_radius_for_state("listening", 150, 112)
        r_speaking = app.sphere_radius_for_state("speaking", 150, 112)
        self.assertEqual(r_idle, r_listening)
        self.assertGreater(r_speaking, r_idle)

        # 3. Parada de emergencia honesta: cancela operaciones activas sin afirmar que revierte SQLite
        chat_messages: list[tuple[str, str]] = []
        sphere_states: list[str] = []
        closed_responses: list[bool] = []

        class _ClosableResponse:
            def close(self) -> None:
                closed_responses.append(True)

        scan_cancel = threading.Event()
        fake_app = SimpleNamespace(
            vt_busy=True,
            vt_cancel_event=threading.Event(),
            local_scan_cancel_event=scan_cancel,
            ai_busy=True,
            cancel_event=threading.Event(),
            response_lock=threading.Lock(),
            active_response=_ClosableResponse(),
            voice_active=True,
            voice_stop=threading.Event(),
            tts_active=True,
            tts_cancel_event=threading.Event(),
            ollama_status=SimpleNamespace(configure=lambda **_kw: None),
            voice_status=SimpleNamespace(configure=lambda **_kw: None),
            set_sphere_state=lambda st: sphere_states.append(st),
            append_chat=lambda spk, txt, **_kw: chat_messages.append((spk, txt)),
        )
        app.AssistantApp.emergency_stop(fake_app)

        self.assertTrue(fake_app.vt_cancel_event.is_set())
        self.assertTrue(scan_cancel.is_set())
        self.assertTrue(fake_app.cancel_event.is_set())
        self.assertTrue(fake_app.voice_stop.is_set())
        self.assertTrue(fake_app.tts_cancel_event.is_set())
        self.assertEqual(closed_responses, [True])
        self.assertEqual(sphere_states[-1], "idle")
        self.assertEqual(len(chat_messages), 1)
        speaker, msg = chat_messages[0]
        self.assertEqual(speaker, "Control de emergencia")
        self.assertIn("las tareas ya guardadas no se revierten", msg)
        self.assertIn("llamada bloqueante del sistema de archivos puede tardar", msg)

    def test_etapa5_next_commitment_in_progress_apply_routines_dedupe_and_rss_scheme_filter(self) -> None:
        db = create_test_db()
        target_day = date(2026, 10, 22)  # Jueves (weekday = 3)
        now = datetime(2026, 10, 22, 10, 20)

        # 1. Clase en curso (10:00-11:00) + Bloque próximo (11:30-12:15) + Tarea sin hora
        db.execute(
            "INSERT INTO classes(name,weekday,start_time,end_time,location) VALUES(?,?,?,?,?)",
            ("Física", 3, "10:00", "11:00", "Lab 2"),
        )
        db.execute(
            "INSERT INTO plan_blocks(title,block_date,start_time,end_time,notes,created_at) VALUES(?,?,?,?,?,?)",
            ("Repaso de Física", target_day.isoformat(), "11:30", "12:15", None, now.isoformat()),
        )
        db.execute(
            "INSERT INTO tasks(title,due_date,priority,done,created_at,subject) VALUES(?,?,?,?,?,?)",
            ("Leer capítulo 4", target_day.isoformat(), "Alta", 0, now.isoformat(), "Física"),
        )
        db.commit()

        summary = app.build_next_commitment_summary(db, now=now)
        self.assertIn("En curso ahora: Clase · Física (10:00–11:00) (Lab 2).", summary)
        self.assertIn("Lo que sigue hoy (en 1 h 10 min): Bloque local · Repaso de Física (11:30–12:15).", summary)
        self.assertIn("Leer capítulo 4 [Física]", summary)

        # 2. apply_routines no duplica si ya existe la tarea manual o si se ejecuta dos veces
        db.execute(
            "INSERT INTO routines(title,subject,weekdays,reminder_time,active,created_at) VALUES(?,?,?,?,1,?)",
            ("Leer capítulo 4", "Física", "3", "07:00", now.isoformat()),
        )
        db.execute(
            "INSERT INTO routines(title,subject,weekdays,reminder_time,active,created_at) VALUES(?,?,?,?,1,?)",
            ("Practicar problemas", "Matemáticas", "3", "18:00", now.isoformat()),
        )
        db.commit()

        fake_app = SimpleNamespace(db=db, refresh_tasks=lambda: None)
        added_first = app.AssistantApp.apply_routines(fake_app, target_day)
        added_second = app.AssistantApp.apply_routines(fake_app, target_day)
        self.assertEqual(added_first, 1)  # Solo "Practicar problemas"; "Leer capítulo 4" ya existía hoy
        self.assertEqual(added_second, 0)  # Segunda ejecución hoy no duplica nada

        # 3. parse_news_feed filtra esquemas peligrosos en <link> y conserva https://
        rss_xml = (
            b"<?xml version='1.0' encoding='UTF-8'?><rss version='2.0'><channel>"
            b"<item><title>Noticia segura</title><link>https://example.com/ok</link><source>Fuente A</source></item>"
            b"<item><title>Enlace peligroso</title><link>javascript:alert(1)</link><source>Fuente B</source></item>"
            b"</channel></rss>"
        )
        parsed = app.parse_news_feed(rss_xml, "Google News", 5)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["link"], "https://example.com/ok")
        self.assertEqual(parsed[1]["link"], "")

    def test_etapa6_file_app_virustotal_and_download_guardrails_without_executing_side_effects(self) -> None:
        # 1. validate_selected_folder rechaza rutas vacías, UNC y symlinks sin leer ni modificar la carpeta
        with tempfile.TemporaryDirectory() as tmp:
            real_dir = Path(tmp) / "CarpetaSegura"
            real_dir.mkdir()
            link_dir = Path(tmp) / "EnlaceCarpeta"
            link_dir.symlink_to(real_dir, target_is_directory=True)
            self.assertEqual(app.validate_selected_folder(real_dir), real_dir.resolve())
            with self.assertRaises(ValueError):
                app.validate_selected_folder("")
            with self.assertRaises(ValueError):
                app.validate_selected_folder(r"\\servidor\compartido")
            with self.assertRaises(ValueError):
                app.validate_selected_folder(link_dir)

        # 2. normalize_allowed_applications filtra cmd.exe, powershell.exe, instaladores y scripts inyectados
        tampered_list = [
            {"name": "cmd.exe", "path": "/opt/apps/cmd.exe", "size": 100, "mtime_ns": 1, "file_id": [1, 1]},
            {"name": "powershell.exe", "path": "/opt/apps/powershell.exe", "size": 100, "mtime_ns": 1, "file_id": [1, 2]},
            {"name": "mi_installer.exe", "path": "/opt/apps/mi_installer.exe", "size": 100, "mtime_ns": 1, "file_id": [1, 3]},
            {"name": "script.bat", "path": "/opt/apps/script.bat", "size": 100, "mtime_ns": 1, "file_id": [1, 4]},
            {"name": " MiAppGUI.exe", "path": "/opt/apps/MiAppGUI.exe", "size": 2048, "mtime_ns": 55, "file_id": [2, 9]},
        ]
        normalized = json.loads(app.normalize_allowed_applications(json.dumps(tampered_list)))
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["name"], "MiAppGUI.exe")

        # 3. virustotal_lookup exige SHA-256 de 64 hex y solo hace GET del hash (sin subir archivo)
        with self.assertRaises(ValueError):
            app.virustotal_lookup("documento_secreto.pdf", "api-key")

        valid_sha = "a" * 64
        captured_requests = []

        class _FakeHTTPResponse:
            def __enter__(self): return self
            def __exit__(self, *_a): pass
            def read(self, _n=-1):
                return json.dumps({
                    "data": {
                        "attributes": {
                            "last_analysis_stats": {"malicious": 0, "suspicious": 0, "harmless": 60, "undetected": 10},
                            "last_analysis_results": {},
                            "last_analysis_date": 1700000000,
                            "reputation": 0,
                        }
                    }
                }).encode("utf-8")

        class _FakeOpener:
            def open(self, req, timeout=20):
                captured_requests.append((req.get_method(), req.full_url, req.data))
                return _FakeHTTPResponse()

        with mock.patch("urllib.request.build_opener", return_value=_FakeOpener()):
            vt_res = app.virustotal_lookup(valid_sha, "fake-key")
        self.assertEqual(vt_res["status"], "ok")
        self.assertEqual(captured_requests, [("GET", f"https://www.virustotal.com/api/v3/files/{valid_sha}", None)])

        # 4. Descargas automáticas desactivadas y divulgación completa de todos los recursos oficiales
        self.assertFalse(app.AUTO_DOWNLOADS_ENABLED)
        for key in app.OFFICIAL_RESOURCES:
            disclosure = app.format_resource_disclosure(key)
            self.assertIn("Fuente oficial:", disclosure)
            self.assertIn("Licencia:", disclosure)
            self.assertIn("DESACTIVADAS", disclosure)

    def test_etapa7_launchers_backup_roundtrip_and_reversible_migration_preview(self) -> None:
        base_dir = Path(app.__file__).resolve().parent

        # 1. Lanzadores de inicio sencillo sin instalaciones silenciosas, descargas ni elevación
        for launcher_name in ("iniciar.bat", "iniciar_clara_terminal.bat"):
            content = (base_dir / launcher_name).read_text(encoding="utf-8")
            low = content.casefold()
            self.assertIn("py -3 app.py", low)
            self.assertIn("ollama serve", low)
            for forbidden in ("pip install", "ollama pull", "invoke-webrequest", "curl ", "wget ", "runas"):
                self.assertNotIn(forbidden, low)

        with tempfile.TemporaryDirectory() as tmp_ollama:
            fake_ollama = Path(tmp_ollama) / "ollama.exe"
            fake_ollama.write_bytes(b"MZ")
            launched_cmds = []
            with mock.patch.object(app, "find_installed_ollama_executable", return_value=fake_ollama):
                started = app.ensure_local_ollama_running(
                    platform_name="win32",
                    popen=lambda cmd, **kw: launched_cmds.append((cmd, kw.get("shell"))),
                )
            self.assertTrue(started)
            self.assertEqual(launched_cmds, [([str(fake_ollama), "serve"], False)])

        # Scripts de instalación opcional exigen confirmación manual (choice /c SN) y divulgan licencia/fuente
        for opt_script in ("instalar_voz.bat", "instalar_opciones_windows.bat", "build_windows.bat"):
            content = (base_dir / opt_script).read_text(encoding="utf-8")
            self.assertIn("choice /c SN", content)
            self.assertIn("Licencia", content)

        # 2. _write_backup e import_backup: bloqueo con operación activa y rechazo de clave API en respaldo
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prev = (app.DATA_DIR, app.DB_PATH, app.SETTINGS_PATH)
            try:
                app.DATA_DIR = tmp_path / "AsistentePersonal"
                app.DB_PATH = app.DATA_DIR / "asistente.db"
                app.SETTINGS_PATH = app.DATA_DIR / "settings.json"
                db = app.connect_db()
                db.execute(
                    "INSERT INTO tasks(title,due_date,priority,done,created_at) VALUES(?,?,?,?,?)",
                    ("Tarea respaldada", "2026-10-25", "Alta", 0, "2026-10-22T07:00:00"),
                )
                db.commit()

                zip_dest = tmp_path / "respaldo_etapa7.zip"
                fake_app = SimpleNamespace(
                    db=db,
                    settings=dict(app.DEFAULT_SETTINGS),
                    ai_busy=True,
                    voice_active=False,
                    tts_active=False,
                    local_scan_running=False,
                    vt_busy=False,
                )
                app.AssistantApp._write_backup(fake_app, zip_dest)
                with zipfile.ZipFile(zip_dest, "r") as zf:
                    self.assertEqual(set(zf.namelist()), {"asistente.db", "settings.json"})

                # Si hay operación activa (ai_busy=True), import_backup avisa y no cierra la base
                warned = []
                with mock.patch.object(app.messagebox, "showwarning", side_effect=lambda t, m, **_kw: warned.append((t, m))):
                    app.AssistantApp.import_backup(fake_app)
                self.assertEqual(len(warned), 1)
                self.assertIn("Operación activa", warned[0][0])
                db.close()
            finally:
                app.DATA_DIR, app.DB_PATH, app.SETTINGS_PATH = prev

    def test_etapa8_static_ast_sql_explain_and_repo_integrity_audit(self) -> None:
        import ast

        base_dir = Path(app.__file__).resolve().parent
        repo_root = base_dir.parent
        source_path = base_dir / "app.py"
        source = source_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(source_path))

        # 1. Cero funciones o métodos duplicados en CLARA_Unificada/app.py
        top_funcs: set[str] = set()
        duplicates: list[str] = []
        app_methods: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                if node.name in top_funcs:
                    duplicates.append(node.name)
                top_funcs.add(node.name)
            elif isinstance(node, ast.ClassDef):
                seen_methods: set[str] = set()
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        if item.name in seen_methods:
                            duplicates.append(f"{node.name}.{item.name}")
                        seen_methods.add(item.name)
                if node.name == "AssistantApp":
                    app_methods = seen_methods
        self.assertEqual(duplicates, [])

        # 2. Cero llamadas self.<metodo>() huérfanas en AssistantApp
        tk_base_methods = {
            "title", "configure", "bind_all", "after", "minsize", "geometry", "destroy",
            "withdraw", "state", "winfo_screenwidth", "winfo_screenheight", "deiconify",
            "lift", "focus_force", "protocol", "mainloop",
        }
        valid_app_attrs = app_methods | tk_base_methods | set(dir(app.AssistantApp))
        app_class_node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AssistantApp")
        missing_calls = []
        for sub in ast.walk(app_class_node):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                if isinstance(sub.func.value, ast.Name) and sub.func.value.id == "self":
                    if sub.func.attr not in valid_app_attrs:
                        missing_calls.append((sub.lineno, sub.func.attr))
        self.assertEqual(missing_calls, [])

        # 3. Todas las consultas estáticas SELECT/INSERT/UPDATE/DELETE pasan EXPLAIN contra connect_db()
        dml_queries = []
        for sub in ast.walk(tree):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == "execute":
                if sub.args and isinstance(sub.args[0], ast.Constant) and isinstance(sub.args[0].value, str):
                    sql = sub.args[0].value.strip()
                    if sql.upper().startswith(("SELECT", "INSERT", "UPDATE", "DELETE")):
                        dml_queries.append((sub.lineno, sql))
        self.assertGreaterEqual(len(dml_queries), 120)
        with tempfile.TemporaryDirectory() as tmp:
            prev = (app.DATA_DIR, app.DB_PATH, app.SETTINGS_PATH)
            try:
                app.DATA_DIR = Path(tmp) / "AsistentePersonal"
                app.DB_PATH = app.DATA_DIR / "asistente.db"
                app.SETTINGS_PATH = app.DATA_DIR / "settings.json"
                db = app.connect_db()
                for lineno, sql in dml_queries:
                    params = tuple([1] * sql.count("?"))
                    rows = db.execute("EXPLAIN " + sql, params).fetchall()
                    self.assertGreater(len(rows), 0, f"Fallo EXPLAIN en línea {lineno}: {sql}")
                db.close()
            finally:
                app.DATA_DIR, app.DB_PATH, app.SETTINGS_PATH = prev

        # 4. Proyectos originales intactos y .gitignore protege datos personales, claves y respaldos
        self.assertTrue((repo_root / "CLARA_v1.27.4" / "app.py").is_file())
        self.assertTrue((repo_root / "Bienvenido_Señor" / "viernes.py").is_file())
        gitignore_text = (repo_root / ".gitignore").read_text(encoding="utf-8")
        for required_rule in ("*.db", "settings.json", "*.dpapi", ".env", "news_cache.json", "backups_before_restore/"):
            self.assertIn(required_rule, gitignore_text)

    def test_security_levels_voice_or_text_auth_vault_and_ollama_fallback(self) -> None:
        db = create_test_db()
        app.ensure_security_tables(db)
        db.execute(
            "INSERT INTO classes(name,weekday,start_time,end_time,location) VALUES(?,?,?,?,?)",
            ("Química", 3, "18:00", "19:00", "Lab 2"),
        )
        db.commit()

        chat_messages: list[tuple[str, str]] = []

        class _FakeEntry:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def delete(self, *_args) -> None:
                self.value = ""

        fake_app = SimpleNamespace(
            db=db,
            tk=None,
            ai_busy=False,
            current_auth_user=None,
            current_auth_level=0,
            _active_vault_passphrase="",
            _pending_protected_action=None,
            settings={"weather_location": "Colima, Colima, México", "auto_speak_responses": "false", "chat_history_enabled": "false"},
            chat_input=_FakeEntry(),
            model_var=SimpleNamespace(get=lambda: ""),
            append_chat=lambda speaker, msg, **_kw: chat_messages.append((speaker, msg)),
            refresh_tasks=lambda: None,
            open_local_file_tools=lambda intent=None: None,
            _update_auth_status_label=lambda: None,
        )
        fake_app.require_permission = lambda act, pending_callable=None: app.AssistantApp.require_permission(fake_app, act, pending_callable=pending_callable)
        fake_app.lock_security_session = lambda: app.AssistantApp.lock_security_session(fake_app)
        fake_app._present_decrypted_secrets_in_chat = lambda: app.AssistantApp._present_decrypted_secrets_in_chat(fake_app)
        fake_app._execute_reset_clara_with_confirmation = lambda: app.AssistantApp._execute_reset_clara_with_confirmation(fake_app)
        fake_app.handle_security_chat_command = lambda cmd: app.AssistantApp.handle_security_chat_command(fake_app, cmd)
        fake_app.apply_chat_intent = lambda u, i: app.AssistantApp.apply_chat_intent(fake_app, u, i)

        # 1. Usuario escribe o dicta "Luis ju89yt56rf" -> confirma nivel de acceso prioritario y oculta contraseña
        fake_app.chat_input = _FakeEntry("Luis ju89yt56rf")
        app.AssistantApp.send_chat(fake_app)
        self.assertEqual(fake_app.current_auth_user, "Luis")
        self.assertEqual(fake_app.current_auth_level, 3)
        self.assertTrue(any(spk == "Tú" and "[contraseña oculta por seguridad]" in msg and "ju89yt56rf" not in msg for spk, msg in chat_messages))
        self.assertTrue(any(spk == "Asistente" and "Usuario y contraseñas confirmadas: Luis, nivel de acceso prioritario" in msg for spk, msg in chat_messages))

        # 2. Guardar secreto encriptado en la bóveda (solo Nivel 3 Prioritario) y verificar cifrado en SQLite
        fake_app.chat_input = _FakeEntry("guardar secreto Correo principal: ClaveSecreta987!")
        app.AssistantApp.send_chat(fake_app)
        raw_vault_row = db.execute("SELECT secret_label, encrypted_payload FROM encrypted_secrets").fetchone()
        self.assertIsNotNone(raw_vault_row)
        self.assertEqual(raw_vault_row["secret_label"], "Correo principal")
        self.assertTrue(str(raw_vault_row["encrypted_payload"]).startswith("CLARA-VAULT-V1:"))
        self.assertNotIn("ClaveSecreta987!", str(raw_vault_row["encrypted_payload"]))
        with self.assertRaises(ValueError):
            app.decrypt_vault_secret(str(raw_vault_row["encrypted_payload"]), "clave_incorrecta")

        # 3. Registrar un usuario estándar (Nivel 1: Ana) y bloquear la sesión a modo Invitado (Nivel 0)
        fake_app.chat_input = _FakeEntry("registrar usuario Ana claveAna12 nivel 1")
        app.AssistantApp.send_chat(fake_app)
        fake_app.chat_input = _FakeEntry("bloquear sesion")
        app.AssistantApp.send_chat(fake_app)
        self.assertEqual(fake_app.current_auth_level, 0)
        self.assertIsNone(fake_app.current_auth_user)

        # 4. Otro usuario usa el dispositivo e intenta ver contraseñas guardadas -> Clara pregunta "¿De quién es la orden?"
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("ver contraseñas guardadas")
        app.AssistantApp.send_chat(fake_app)
        self.assertTrue(any("¿De quién es la orden?" in msg for _spk, msg in chat_messages))
        self.assertFalse(any("ClaveSecreta987!" in msg for _spk, msg in chat_messages))

        # 5. Si responde Ana (Nivel 1 Estándar), Clara verifica su identidad pero rechaza la orden por falta de permisos
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("Ana claveAna12")
        app.AssistantApp.send_chat(fake_app)
        self.assertEqual(fake_app.current_auth_user, "Ana")
        self.assertEqual(fake_app.current_auth_level, 1)
        self.assertTrue(any("Orden rechazada" in msg for _spk, msg in chat_messages))
        self.assertFalse(any("ClaveSecreta987!" in msg for _spk, msg in chat_messages))

        # 6. Si Ana intenta eliminar una clase (requiere Nivel 2+) o ver secretos (Nivel 3) y luego autoriza Luis (Nivel 3), se ejecuta
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("ver secretos encriptados")
        app.AssistantApp.send_chat(fake_app)
        self.assertTrue(any("¿De quién es la orden?" in msg for _spk, msg in chat_messages))

        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("Luis ju89yt56rf")
        app.AssistantApp.send_chat(fake_app)
        self.assertEqual(fake_app.current_auth_user, "Luis")
        self.assertEqual(fake_app.current_auth_level, 3)
        self.assertTrue(any("Permisos verificados" in msg for _spk, msg in chat_messages))
        self.assertTrue(any("Correo principal: ClaveSecreta987!" in msg for _spk, msg in chat_messages))

        # 7. Cuando no se puede usar Ollama para una pregunta abierta, Clara informa claramente su modo local esencial
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("¿Cuál es la distancia de la Tierra a Júpiter?")
        app.AssistantApp.send_chat(fake_app)
        self.assertTrue(
            any(
                spk == "Asistente"
                and "motor neuronal local (Ollama) no está disponible" in msg
                and "modo local esencial" in msg
                for spk, msg in chat_messages
            )
        )

    def test_flexible_natural_phrasing_across_all_modules_and_scrollable_dialogs(self) -> None:
        db = create_test_db()
        db.execute(
            "CREATE TABLE IF NOT EXISTS memories ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT NOT NULL, content TEXT NOT NULL, "
            "category TEXT NOT NULL, created_at TEXT NOT NULL, source TEXT, expires_on TEXT)"
        )
        db.commit()
        chat_messages: list[tuple[str, str]] = []
        opened_app_manager: list[bool] = []

        class _FakeEntry:
            def __init__(self, text: str) -> None:
                self._text = text

            def get(self) -> str:
                return self._text

            def delete(self, _a: int, _b: str) -> None:
                self._text = ""

        fake_app = SimpleNamespace(
            db=db,
            settings=dict(app.DEFAULT_SETTINGS),
            ai_busy=False,
            model_var=SimpleNamespace(get=lambda: ""),
            current_auth_user=None,
            current_auth_level=0,
            _active_vault_passphrase="",
            _pending_protected_action=None,
            append_chat=lambda spk, txt, **_kw: chat_messages.append((spk, txt)),
            refresh_tasks=lambda: None,
            apply_routines=lambda d: app.AssistantApp.apply_routines(SimpleNamespace(db=db, refresh_tasks=lambda: None), d),
            parse_task_proposal=lambda t, today=None: app.AssistantApp.parse_task_proposal(SimpleNamespace(db=db), t, today=today),
            parse_block_request=lambda t: app.AssistantApp.parse_block_request(SimpleNamespace(db=db), t),
            day_agenda_summary=lambda d: app.AssistantApp.day_agenda_summary(SimpleNamespace(db=db, settings=dict(app.DEFAULT_SETTINGS)), d),
            open_classes=lambda: None,
            open_routines=lambda: None,
            add_task=lambda **_kw: None,
            open_plan_block_form=lambda *_a, **_kw: None,
            open_week_agenda=lambda: None,
            open_application_manager=lambda auto_prompt_add=False: opened_app_manager.append(auto_prompt_add),
        )
        fake_app.handle_app_command_from_chat = lambda raw: app.AssistantApp.handle_app_command_from_chat(fake_app, raw)

        # 1. Caso exacto reportado por el usuario: "Agrega que tengo clases de Bases de Datos los Martes y Jueves de 13:00 a 15:00."
        fake_app.chat_input = _FakeEntry("Agrega que tengo clases de Bases de Datos los Martes y Jueves de 13:00 a 15:00.")
        app.AssistantApp.send_chat(fake_app)
        bd_rows = db.execute("SELECT name, weekday, start_time, end_time FROM classes WHERE name='Bases de Datos' ORDER BY weekday").fetchall()
        self.assertEqual(len(bd_rows), 2)
        self.assertEqual([(r["weekday"], r["start_time"], r["end_time"]) for r in bd_rows], [(1, "13:00", "15:00"), (3, "13:00", "15:00")])
        self.assertTrue(any(spk == "Asistente" and "Guardé tu clase «Bases de Datos»" in msg for spk, msg in chat_messages))
        self.assertFalse(any("No hay clases, tareas con fecha ni bloques locales para hoy" in msg for _spk, msg in chat_messages))

        # 2. Otras formas naturales de agregar clase ("Tengo clases de...", "Ponme la materia de...", "en Auditorio 2")
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("Ponme la materia de Ingeniería de Software los lunes y miércoles de 09:00 a 11:00 en Aula 5")
        app.AssistantApp.send_chat(fake_app)
        is_rows = db.execute("SELECT name, weekday, location FROM classes WHERE name='Ingeniería de Software' ORDER BY weekday").fetchall()
        self.assertEqual(len(is_rows), 2)
        self.assertEqual(is_rows[0]["location"], "Aula 5")

        # Si existía un registro antiguo con "en Auditorio 2" pegado al nombre, se repara automáticamente al guardar o conectar
        db.execute(
            "INSERT INTO classes(name, weekday, start_time, end_time, location) VALUES(?,?,?,?,NULL)",
            ("Matematicas Discretas en Auditorio 2", 2, "13:00", "15:00"),
        )
        db.commit()
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("agrega mi clase de Matematicas Discretas los miércoles y viernes de 13:00 a 15:00 en Auditorio 2.")
        app.AssistantApp.send_chat(fake_app)
        md_rows = db.execute("SELECT name, weekday, start_time, end_time, location FROM classes WHERE name='Matematicas Discretas' ORDER BY weekday").fetchall()
        self.assertEqual(len(md_rows), 2)
        self.assertEqual([(r["weekday"], r["start_time"], r["end_time"], r["location"]) for r in md_rows], [(2, "13:00", "15:00", "Auditorio 2"), (4, "13:00", "15:00", "Auditorio 2")])
        self.assertEqual(db.execute("SELECT COUNT(*) FROM classes WHERE name LIKE '%en Auditorio%'").fetchone()[0], 0)
        self.assertTrue(any(spk == "Asistente" and "Guardé tu clase «Matematicas Discretas» para Miércoles, Viernes en horario 13:00–15:00 (Auditorio 2)." in msg for spk, msg in chat_messages))

        # 3. Formas naturales de agregar tarea con "que tengo que..."
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("Agrega que tengo que entregar el proyecto de Bases de Datos mañana a las 16:00")
        app.AssistantApp.send_chat(fake_app)
        t_row = db.execute("SELECT title, subject, due_time FROM tasks ORDER BY id DESC LIMIT 1").fetchone()
        self.assertIsNotNone(t_row)
        self.assertEqual(t_row["subject"], "Bases de Datos")
        self.assertEqual(t_row["due_time"], "16:00")

        # 4. Excepción de calendario escolar desde el chat ("mañana no hay clases por día festivo")
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("Mañana no hay clases por día festivo")
        app.AssistantApp.send_chat(fake_app)
        exc_row = db.execute("SELECT action, note FROM class_exceptions ORDER BY id DESC LIMIT 1").fetchone()
        self.assertIsNotNone(exc_row)
        self.assertEqual(exc_row["action"], "no_classes")
        self.assertIn("día festivo", exc_row["note"])

        # 5. Memoria del asistente desde el chat ("recuerda que...", "ver mi memoria", "olvida que...")
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("Recuerda que prefiero estudiar después de las 17:00")
        app.AssistantApp.send_chat(fake_app)
        mem_row = db.execute("SELECT content FROM memories ORDER BY id DESC LIMIT 1").fetchone()
        self.assertIsNotNone(mem_row)
        self.assertIn("prefiero estudiar después de las 17:00", mem_row["content"])

        # 6. Aplicaciones autorizadas desde el chat ("mis aplicaciones autorizadas", "agregar aplicación autorizada")
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("mis aplicaciones autorizadas")
        app.AssistantApp.send_chat(fake_app)
        self.assertTrue(any("0 de 10" in msg for _spk, msg in chat_messages))

        fake_app.chat_input = _FakeEntry("agregar aplicación autorizada")
        app.AssistantApp.send_chat(fake_app)
        self.assertEqual(opened_app_manager, [True])

    def test_level3_user_promotion_direct_ollama_sdk_and_llama32_model(self) -> None:
        db = create_test_db()
        app.ensure_security_tables(db)
        chat_messages: list[tuple[str, str]] = []
        pulled_models: list[str] = []

        class _FakeEntry:
            def __init__(self, text: str) -> None:
                self._text = text

            def get(self) -> str:
                return self._text

            def delete(self, _a: int, _b: str) -> None:
                self._text = ""

        class _FakeModelVar:
            def __init__(self, value: str = "") -> None:
                self.value = value

            def get(self) -> str:
                return self.value

            def set(self, value: str) -> None:
                self.value = value

        model_var = _FakeModelVar("")
        fake_app = SimpleNamespace(
            db=db,
            tk=None,
            ai_busy=False,
            current_auth_user=None,
            current_auth_level=0,
            _active_vault_passphrase="",
            _pending_protected_action=None,
            settings=dict(app.DEFAULT_SETTINGS),
            chat_input=_FakeEntry(""),
            model_var=model_var,
            append_chat=lambda spk, msg, **_kw: chat_messages.append((spk, msg)),
            refresh_tasks=lambda: None,
            _update_auth_status_label=lambda: None,
            start_ollama_model_pull=lambda m, confirm_first=True: pulled_models.append(m),
        )
        fake_app.require_permission = lambda act, pending_callable=None: app.AssistantApp.require_permission(fake_app, act, pending_callable=pending_callable)
        fake_app.lock_security_session = lambda: app.AssistantApp.lock_security_session(fake_app)
        fake_app.handle_security_chat_command = lambda cmd: app.AssistantApp.handle_security_chat_command(fake_app, cmd)
        fake_app.handle_ollama_model_command_from_chat = lambda raw: app.AssistantApp.handle_ollama_model_command_from_chat(fake_app, raw)

        # 1. Registrar propietario Nivel 3 (Luis) y usuario Nivel 1 (Ana)
        fake_app.chat_input = _FakeEntry("Luis ju89yt56rf")
        app.AssistantApp.send_chat(fake_app)
        fake_app.chat_input = _FakeEntry("registrar usuario Ana claveAna12 nivel 1")
        app.AssistantApp.send_chat(fake_app)
        self.assertEqual(db.execute("SELECT access_level FROM security_users WHERE username='Ana'").fetchone()["access_level"], 1)

        # 2. Nivel 3 (Luis) autoriza / aumenta el nivel de Ana sin necesitar saber ni escribir la contraseña de Ana
        fake_app.chat_input = _FakeEntry("Luis ju89yt56rf")
        app.AssistantApp.send_chat(fake_app)
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("aumenta el nivel de Ana a 2")
        app.AssistantApp.send_chat(fake_app)
        self.assertEqual(db.execute("SELECT access_level FROM security_users WHERE username='Ana'").fetchone()["access_level"], 2)
        self.assertTrue(any("Nivel de acceso autorizado por Luis" in msg and "Nivel 2" in msg for _spk, msg in chat_messages))

        # La contraseña original de Ana sigue funcionando intacta con su nuevo Nivel 2
        auth_ana = app.authenticate_security_user(db, "Ana", "claveAna12")
        self.assertTrue(auth_ana["authenticated"])
        self.assertEqual(auth_ana["access_level"], 2)

        # 3. Si Ana (Nivel 2) intenta aumentarse a sí misma a Nivel 3, Clara detiene la orden y pide autorización Nivel 3
        fake_app.chat_input = _FakeEntry("Ana claveAna12")
        app.AssistantApp.send_chat(fake_app)
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("autoriza a Ana con nivel 3")
        app.AssistantApp.send_chat(fake_app)
        self.assertEqual(db.execute("SELECT access_level FROM security_users WHERE username='Ana'").fetchone()["access_level"], 2)
        self.assertTrue(any("¿De quién es la orden?" in msg for _spk, msg in chat_messages))

        # Cuando Luis (Nivel 3) autoriza con su usuario y contraseña, Ana sube a Nivel 3 automáticamente
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("Luis ju89yt56rf")
        app.AssistantApp.send_chat(fake_app)
        self.assertEqual(db.execute("SELECT access_level FROM security_users WHERE username='Ana'").fetchone()["access_level"], 3)
        self.assertTrue(any("Nivel 3" in msg for _spk, msg in chat_messages))

        # 4. Prioridad de llama3.2 (el modelo de Viernes) y comandos de descarga/selección por chat
        self.assertEqual(app.select_preferred_ollama_model(["qwen3:4b", "llama3.2:latest"]), "llama3.2:latest")
        self.assertEqual(app.select_preferred_ollama_model(["mistral:latest", "llama3.2"]), "llama3.2")

        with mock.patch.object(app, "warmup_local_ollama_model", return_value=None):
            fake_app.chat_input = _FakeEntry("usar modelo llama3.2")
            app.AssistantApp.send_chat(fake_app)
        self.assertEqual(model_var.get(), "llama3.2")

        fake_app.chat_input = _FakeEntry("descargar modelo llama3.2")
        app.AssistantApp.send_chat(fake_app)
        self.assertEqual(pulled_models, ["llama3.2"])

        # 5. Uso directo del módulo Python `ollama` (ollama_sdk.Client) para listar modelos y conversar en streaming
        class _FakeSdkClient:
            def __init__(self, host: str = "") -> None:
                self.host = host

            def list(self):
                return {"models": [{"model": "llama3.2"}, {"model": "qwen3:4b"}]}

            def chat(self, model: str, messages: list, stream: bool = True, **_kw):
                return iter([
                    {"message": {"content": "Hola desde "}, "done": False},
                    {"message": {"content": model}, "done": True},
                ])

        fake_sdk = SimpleNamespace(Client=_FakeSdkClient)
        with mock.patch.object(app, "OLLAMA_PYTHON_MODULE_AVAILABLE", True), mock.patch.object(app, "ollama_sdk", fake_sdk):
            models = app.list_local_ollama_models()
            self.assertEqual(models, ["llama3.2", "qwen3:4b"])
            chunks = list(app.stream_ollama_chat_direct("llama3.2", [{"role": "user", "content": "hola"}]))
            self.assertEqual(chunks, [("Hola desde ", False), ("llama3.2", True)])

        # 6. Reanudación automática ante corte "net/http: TLS handshake timeout" de Cloudflare R2 al descargar llama3.2
        pull_calls = {"count": 0}
        progress_notes: list[str] = []

        class _FlakyR2SdkClient:
            def __init__(self, host: str = "") -> None:
                self.host = host

            def list(self):
                return {"models": []}

            def pull(self, model: str, stream: bool = True):
                pull_calls["count"] += 1
                if pull_calls["count"] == 1:
                    yield {"status": "pulling dde5aa3fc5ff", "completed": 500_000_000, "total": 2_000_000_000}
                    raise RuntimeError(
                        'max retries exceeded: Get "https://dd20bb891979d25aebc8bec07b2b3bbc.r2.cloudflarestorage.com/...": net/http: TLS handshake timeout'
                    )
                yield {"status": "pulling dde5aa3fc5ff", "completed": 2_000_000_000, "total": 2_000_000_000}
                yield {"status": "success"}

        flaky_sdk = SimpleNamespace(Client=_FlakyR2SdkClient)
        with (
            mock.patch.object(app, "OLLAMA_PYTHON_MODULE_AVAILABLE", True),
            mock.patch.object(app, "ollama_sdk", flaky_sdk),
            mock.patch.object(app, "ensure_local_ollama_running", return_value=False),
            mock.patch.object(app, "find_installed_ollama_executable", return_value=None),
        ):
            ok_pull, msg_pull = app.pull_ollama_model_direct(
                "llama3.2",
                progress_callback=progress_notes.append,
                max_attempts=3,
                retry_delay=0.0,
            )
        self.assertTrue(ok_pull)
        self.assertEqual(pull_calls["count"], 2)
        self.assertIn("llama3.2", msg_pull)
        self.assertTrue(any("Corte TLS temporal de Cloudflare R2; reanudando" in p for p in progress_notes))

    def test_natural_edit_reschedule_conflict_detection_and_private_rag_context(self) -> None:
        db = create_test_db()
        app.ensure_security_tables(db)
        chat_messages: list[tuple[str, str]] = []
        ollama_prompts: list[str] = []

        class _FakeEntry:
            def __init__(self, text: str = "") -> None:
                self._text = text

            def get(self) -> str:
                return self._text

            def delete(self, _a, _b=None) -> None:
                self._text = ""

        class _FakeVar:
            def __init__(self, value: str = "llama3.2") -> None:
                self._val = value

            def get(self) -> str:
                return self._val

            def set(self, value: str) -> None:
                self._val = value

        fake_app = SimpleNamespace(
            db=db,
            settings=dict(app.DEFAULT_SETTINGS),
            ai_busy=False,
            current_auth_user="Luis",
            current_auth_level=3,
            _pending_protected_action=None,
            chat_input=_FakeEntry(""),
            model_var=_FakeVar("llama3.2"),
            append_chat=lambda speaker, text, **_kw: chat_messages.append((speaker, text)),
            apply_chat_intent=lambda user_text, intent: app.AssistantApp.apply_chat_intent(fake_app, user_text, intent),
            parse_task_proposal=lambda text_in: app.AssistantApp.parse_task_proposal(fake_app, text_in),
            parse_block_request=lambda text_in: app.AssistantApp.parse_block_request(fake_app, text_in),
            refresh_tasks=lambda: None,
            apply_routines=lambda _day: 0,
            open_classes=lambda: None,
            open_routines=lambda: None,
            add_task=lambda **_kw: None,
            open_plan_block_form=lambda *_a, **_kw: None,
            day_agenda_summary=lambda target: app.AssistantApp.day_agenda_summary(fake_app, target),
            open_week_agenda=lambda: None,
            ask_ollama=lambda q: ollama_prompts.append(q),
        )

        # 1. Agregar clase base: Matematicas Discretas miércoles y viernes de 13:00 a 15:00 en Auditorio 2
        fake_app.chat_input = _FakeEntry("agrega mi clase de Matematicas Discretas los miércoles y viernes de 13:00 a 15:00 en Auditorio 2.")
        app.AssistantApp.send_chat(fake_app)

        # 2. Incremento 1: Editar aula/lugar por chat natural sin duplicar registros
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("Cambia mi clase de Matematicas Discretas al Laboratorio 3")
        app.AssistantApp.send_chat(fake_app)
        rows = db.execute("SELECT weekday, start_time, end_time, location FROM classes WHERE name='Matematicas Discretas' ORDER BY weekday").fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual([(r["weekday"], r["start_time"], r["end_time"], r["location"]) for r in rows], [(2, "13:00", "15:00", "Laboratorio 3"), (4, "13:00", "15:00", "Laboratorio 3")])
        self.assertTrue(any("Actualicé tu clase «Matematicas Discretas»" in msg and "Laboratorio 3" in msg for _s, msg in chat_messages))

        # 3. Incremento 1: Editar horario de un día específico (viernes de 15:00 a 17:00)
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("Cambia el horario de mi clase de Matematicas Discretas del viernes de 15:00 a 17:00")
        app.AssistantApp.send_chat(fake_app)
        rows = db.execute("SELECT weekday, start_time, end_time, location FROM classes WHERE name='Matematicas Discretas' ORDER BY weekday").fetchall()
        self.assertEqual([(r["weekday"], r["start_time"], r["end_time"]) for r in rows], [(2, "13:00", "15:00"), (4, "15:00", "17:00")])

        # 4. Incremento 2: Detector inteligente de choques de horario (Empalmes) al agregar una clase que se cruza
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("Agrega mi clase de Redes de Computadoras los miércoles de 14:00 a 16:00 en Aula 7")
        app.AssistantApp.send_chat(fake_app)
        self.assertTrue(any("⚠️ Atención: se empalma el Miércoles de 14:00 a 15:00 con tu clase «Matematicas Discretas»" in msg for _s, msg in chat_messages))

        # Consultar choques de horario por chat
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("¿Tengo algún choque de horario en mis clases?")
        app.AssistantApp.send_chat(fake_app)
        self.assertTrue(any("Miércoles 14:00–15:00: «Matematicas Discretas» (Laboratorio 3) se empalma con «Redes de Computadoras» (Aula 7)" in msg for _s, msg in chat_messages))

        # Resolver el choque moviendo Redes de Computadoras de 16:00 a 18:00 por chat
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("Mueve mi clase de Redes de Computadoras de 16:00 a 18:00")
        app.AssistantApp.send_chat(fake_app)
        self.assertFalse(any("⚠️ Atención:" in msg for _s, msg in chat_messages))

        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("¿Hay empalmes en mis clases?")
        app.AssistantApp.send_chat(fake_app)
        self.assertTrue(any("no tienes ningún choque ni empalme de horario" in msg for _s, msg in chat_messages))

        # 5. Incremento 1: Reprogramar tarea, rutina y bloque de estudio por chat natural
        fake_app.chat_input = _FakeEntry("Agrega tarea de Matematicas Discretas entregar guía de grafos hoy a las 14:00")
        app.AssistantApp.send_chat(fake_app)
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("Pasa la tarea de Matematicas Discretas para mañana a las 18:30")
        app.AssistantApp.send_chat(fake_app)
        t_row = db.execute("SELECT due_date, due_time FROM tasks ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(t_row["due_date"], (date.today() + timedelta(days=1)).isoformat())
        self.assertEqual(t_row["due_time"], "18:30")
        self.assertTrue(any("Reprogramé tu tarea" in msg and "18:30" in msg for _s, msg in chat_messages))

        fake_app.chat_input = _FakeEntry("Agrega rutina de repasar inglés los lunes y miércoles a las 19:00")
        app.AssistantApp.send_chat(fake_app)
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("Cambia la rutina de repasar inglés a las 20:30")
        app.AssistantApp.send_chat(fake_app)
        r_row = db.execute("SELECT reminder_time FROM routines ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual(r_row["reminder_time"], "20:30")

        fake_app.chat_input = _FakeEntry("Reserva de 10:00 a 11:00 mañana para estudiar grafos")
        app.AssistantApp.send_chat(fake_app)
        chat_messages.clear()
        fake_app.chat_input = _FakeEntry("Mueve el bloque de estudiar grafos de 11:30 a 13:00")
        app.AssistantApp.send_chat(fake_app)
        b_row = db.execute("SELECT start_time, end_time FROM plan_blocks ORDER BY id DESC LIMIT 1").fetchone()
        self.assertEqual((b_row["start_time"], b_row["end_time"]), ("11:30", "13:00"))

        # 6. Incremento 3: RAG Local Privado conectado a llama3.2 (sin exponer bóveda de secretos)
        app.save_encrypted_secret(db, "TokenPrivadoBanco", "ClaveUltraSecreta999", "ju89yt56rf", "Luis")
        rag_ctx = app.build_private_agenda_rag_context(db)
        self.assertIn("Matematicas Discretas", rag_ctx)
        self.assertIn("Laboratorio 3", rag_ctx)
        self.assertIn("Redes de Computadoras", rag_ctx)
        self.assertIn("guía de grafos", rag_ctx)
        self.assertIn("Día(s) entre semana (Lunes–Viernes) con más tiempo libre", rag_ctx)
        self.assertNotIn("ClaveUltraSecreta999", rag_ctx)
        self.assertNotIn("TokenPrivadoBanco", rag_ctx)

        # Pregunta analítica de estudio va a llama3.2 (con el contexto RAG) en vez de abrir solo una tabla estática
        ollama_prompts.clear()
        fake_app.chat_input = _FakeEntry("¿Qué día de mi semana tengo más libre para estudiar 2 horas de Matemáticas Discretas?")
        app.AssistantApp.send_chat(fake_app)
        self.assertEqual(len(ollama_prompts), 1)

        local_strategy = app.build_local_analytical_schedule_answer(
            db,
            "Hazme una estrategia para sacar adelante mis tareas pendientes de esta semana según mi horario",
        )
        self.assertIn("Día(s) más libre(s) entre semana", local_strategy)
        self.assertIn("guía de grafos", local_strategy)

        # 7. Verificar que ask_ollama inyecta el RAG Local Privado en los mensajes enviados a llama3.2
        captured_messages: list[list[dict]] = []

        def _fake_stream(model_name, msgs, **_kw):
            captured_messages.append(list(msgs))
            yield ("Te recomiendo estudiar el lunes de 08:00 a 10:00.", True)

        real_ask_app = SimpleNamespace(
            db=db,
            model_var=_FakeVar("llama3.2"),
            ollama_request_id=0,
            ai_busy=False,
            cancel_event=threading.Event(),
            stream_text="",
            stream_user_text="",
            stream_started=False,
            structured_intent_mode=False,
            ollama_status=SimpleNamespace(configure=lambda **_kw: None),
            ai_history=[],
            ai_results=app.queue.Queue(),
            response_lock=threading.Lock(),
            active_response=None,
        )
        with mock.patch.object(app, "stream_ollama_chat_direct", side_effect=_fake_stream):
            app.AssistantApp.ask_ollama(real_ask_app, "¿Qué día de mi semana tengo más libre para estudiar 2 horas de Matemáticas Discretas?")
            for _ in range(30):
                if captured_messages:
                    break
                app.time.sleep(0.02)
        self.assertEqual(len(captured_messages), 1)
        system_blobs = "\n".join(m["content"] for m in captured_messages[0] if m["role"] == "system")
        self.assertIn("CONTEXTO REAL DE LA AGENDA LOCAL DEL USUARIO", system_blobs)
        self.assertIn("Matematicas Discretas", system_blobs)
        self.assertIn("Laboratorio 3", system_blobs)
        self.assertNotIn("ClaveUltraSecreta999", system_blobs)

        # 8. Verificar que los diálogos muestran el botón "✏ Editar seleccionado" y "🔍 Revisar empalmes"
        import inspect
        for method in (
            app.AssistantApp.open_classes,
            app.AssistantApp.open_routines,
            app.AssistantApp.open_memories,
            app.AssistantApp.open_calendar_exceptions,
        ):
            src = inspect.getsource(method)
            self.assertIn("✏ Editar seleccionado", src)
        self.assertIn("🔍 Revisar empalmes", inspect.getsource(app.AssistantApp.open_classes))

    def test_voice_recognition_accumulates_utterances_boosts_gain_and_viernes_fallback(self) -> None:
        # 1. Reproducir el bug exacto reportado: el usuario habla una frase, hace una pausa antes de
        # pulsar "Detener micrófono" (AcceptWaveform devuelve True y vacía el buffer hacia Result(),
        # dejando FinalResult() vacío ""). Antes se perdía toda la frase; ahora se conserva íntegra.
        class _FakeKaldiPauseBeforeStop:
            def __init__(self) -> None:
                self._step = 0

            def AcceptWaveform(self, _chunk: bytes) -> bool:
                self._step += 1
                return self._step == 2

            def Result(self) -> str:
                return json.dumps({"text": "hola clara que clases tengo hoy"})

            def PartialResult(self) -> str:
                return json.dumps({"partial": "hola clara"} if self._step == 1 else {"partial": ""})

            def FinalResult(self) -> str:
                # Vacío porque la frase ya se cerró en Result() durante la pausa previa al clic en Detener
                return json.dumps({"text": ""})

        rec = _FakeKaldiPauseBeforeStop()
        segments: list[str] = []
        partial_holder = [""]
        p1 = app.accumulate_vosk_stream_chunk(rec, b"\x10\x00" * 400, segments, partial_holder)
        self.assertEqual(p1, "hola clara")
        self.assertEqual(partial_holder[0], "hola clara")
        p2 = app.accumulate_vosk_stream_chunk(rec, b"\x10\x00" * 400, segments, partial_holder)
        self.assertEqual(p2, "hola clara que clases tengo hoy")
        self.assertEqual(segments, ["hola clara que clases tengo hoy"])
        self.assertEqual(partial_holder[0], "")
        # Silencio mientras el usuario mueve el ratón al botón Detener
        app.accumulate_vosk_stream_chunk(rec, b"\x00\x00" * 400, segments, partial_holder)
        final_text = app.finalize_vosk_recognition(rec, segments, partial_holder[0])
        self.assertEqual(final_text, "hola clara que clases tengo hoy")

        # 2. Caso en que el usuario pulsa Detener a mitad de frase y FinalResult viene vacío:
        # debe rescatar last_partial en lugar de mostrar "No alcancé a reconocer palabras"
        class _FakeKaldiStoppedMidPhrase:
            def AcceptWaveform(self, _chunk: bytes) -> bool:
                return False

            def PartialResult(self) -> str:
                return json.dumps({"partial": "agrega tarea de bases de datos"})

            def FinalResult(self) -> str:
                return json.dumps({"text": ""})

        rec_mid = _FakeKaldiStoppedMidPhrase()
        segs_mid: list[str] = []
        part_mid = [""]
        app.accumulate_vosk_stream_chunk(rec_mid, b"\x20\x00" * 400, segs_mid, part_mid)
        rescued = app.finalize_vosk_recognition(rec_mid, segs_mid, part_mid[0])
        self.assertEqual(rescued, "agrega tarea de bases de datos")

        # 3. Normalización automática de ganancia (AGC) para micrófonos con volumen bajo en Windows
        import struct
        quiet_samples = [400, -400, 600, -600] * 300
        quiet_pcm = struct.pack(f"<{len(quiet_samples)}h", *quiet_samples)
        boosted_pcm, peak, gain = app._boost_pcm16_gain(quiet_pcm)
        self.assertEqual(peak, 600)
        self.assertGreater(gain, 5.0)
        boosted_samples = struct.unpack(f"<{len(quiet_samples)}h", boosted_pcm)
        self.assertGreater(max(abs(s) for s in boosted_samples), 6000)

        # 4. Segunda pasada Vosk con ganancia aumentada + silencio final y respaldo Viernes (SpeechRecognition)
        class _FakeSecondPassRecognizer:
            def __init__(self, _model, _rate: int) -> None:
                self._max_seen = 0

            def AcceptWaveform(self, chunk: bytes) -> bool:
                cnt = len(chunk) // 2
                if cnt:
                    vals = struct.unpack(f"<{cnt}h", chunk[: cnt * 2])
                    self._max_seen = max(self._max_seen, max(abs(v) for v in vals))
                return False

            def PartialResult(self) -> str:
                return json.dumps({"partial": ""})

            def FinalResult(self) -> str:
                return json.dumps({"text": "reconocido en segunda pasada" if self._max_seen > 5000 else ""})

        second_pass_txt = app.recognize_pcm_with_vosk_second_pass(
            object(),
            quiet_pcm,
            16000,
            recognizer_cls=_FakeSecondPassRecognizer,
        )
        self.assertEqual(second_pass_txt, "reconocido en segunda pasada")

        class _FakeSRModule:
            class AudioData:
                def __init__(self, raw: bytes, rate: int, width: int) -> None:
                    self.raw = raw
                    self.rate = rate
                    self.width = width

            class Recognizer:
                def recognize_google(self, _audio, language: str = "es-MX") -> str:
                    return f"transcrito por respaldo viernes ({language})"

        viernes_txt = app.recognize_pcm_with_viernes_backends(quiet_pcm, 16000, sr_module=_FakeSRModule)
        self.assertEqual(viernes_txt, "transcrito por respaldo viernes (es-MX)")

    def test_points_4_5_6_pomodoro_subject_notebook_and_weekly_grid(self) -> None:
        db = create_test_db()
        app.ensure_security_tables(db)
        app.ensure_subject_notebook_tables(db)
        messages: list[tuple[str, str]] = []
        sphere_labels: list[str] = []

        class _FakeEntry:
            def __init__(self, text: str = "") -> None:
                self.value = text
            def get(self) -> str:
                return self.value
            def delete(self, _start, _end) -> None:
                self.value = ""

        fake_app = SimpleNamespace(
            db=db,
            settings=dict(app.DEFAULT_SETTINGS),
            chat_input=_FakeEntry(),
            ai_busy=False,
            current_auth_user="LuisAdmin",
            current_auth_level=3,
            _active_vault_passphrase="",
            _pending_protected_action=None,
            pomodoro_active=False,
            pomodoro_paused=False,
            pomodoro_remaining_seconds=0,
            pomodoro_total_minutes=0,
            pomodoro_label="",
            pomodoro_subject=None,
            sphere_state_label=SimpleNamespace(configure=lambda **kw: sphere_labels.append(str(kw.get("text", "")))),
            set_sphere_state=lambda _st: None,
            append_chat=lambda speaker, text, **_kw: messages.append((speaker, text)),
            refresh_tasks=lambda: None,
            apply_chat_intent=lambda user_text, intent: app.AssistantApp.apply_chat_intent(fake_app, user_text, intent),
        )

        def send(msg: str) -> str:
            messages.clear()
            fake_app.chat_input.value = msg
            app.AssistantApp.send_chat(fake_app)
            self.assertTrue(messages, f"No hubo respuesta para: {msg}")
            return messages[-1][1]

        # Registrar materias primero
        send("agrega clase de Matematicas Discretas los lunes de 11:00 a 13:00 en el Salon B2")
        send("agrega clase de Bases de Datos los miercoles de 09:00 a 11:00 en el Laboratorio 1")

        # --- PUNTO 4: Temporizador Pomodoro y Enfoque en la Esfera Viva ---
        r_pomo_start = send("pon un Pomodoro de 25 minutos para estudiar Matematicas Discretas")
        self.assertIn("25 minuto(s)", r_pomo_start)
        self.assertIn("Matematicas Discretas", r_pomo_start)
        self.assertTrue(fake_app.pomodoro_active)
        self.assertEqual(fake_app.pomodoro_remaining_seconds, 25 * 60)
        self.assertTrue(any("25:00" in lbl for lbl in sphere_labels))

        r_pomo_status = send("¿cuánto falta del Pomodoro?")
        self.assertIn("25:00", r_pomo_status)

        r_pomo_pause = send("pausa el Pomodoro")
        self.assertIn("en pausa", r_pomo_pause)
        self.assertTrue(fake_app.pomodoro_paused)

        r_pomo_resume = send("reanuda el Pomodoro")
        self.assertIn("Reanudé", r_pomo_resume)
        self.assertFalse(fake_app.pomodoro_paused)

        # Simular el último segundo del Pomodoro para verificar el aviso y el registro en action_events
        fake_app.pomodoro_remaining_seconds = 1
        messages.clear()
        app.AssistantApp._tick_pomodoro(fake_app)
        self.assertFalse(fake_app.pomodoro_active)
        self.assertTrue(any("¡Tiempo cumplido!" in m[1] for m in messages))
        logged_pomo = db.execute("SELECT action, outcome FROM action_events WHERE action='Sesión Pomodoro completada'").fetchone()
        self.assertIsNotNone(logged_pomo)
        self.assertIn("Matematicas Discretas", logged_pomo["outcome"])

        # --- PUNTO 5: Cuaderno de apuntes rápidos y carpeta vinculada por Materia ---
        r_note_add = send("apunta en Matematicas Discretas que el examen parcial viene hasta grafos bipartitos")
        self.assertIn("Guardé tu apunte", r_note_add)
        self.assertIn("Matematicas Discretas", r_note_add)
        self.assertIn("grafos bipartitos", r_note_add)

        r_note_list = send("¿qué apuntes tengo de Matematicas Discretas?")
        self.assertIn("grafos bipartitos", r_note_list)

        # Verificar que el apunte forma parte del contexto privado RAG para Llama 3.2
        rag_ctx = app.build_private_agenda_rag_context(db)
        self.assertIn("Apuntes rápidos por materia:", rag_ctx)
        self.assertIn("grafos bipartitos", rag_ctx)

        # Vincular una carpeta real temporal a la materia
        with tempfile.TemporaryDirectory() as tmp_subj_dir:
            r_link = send(f"vincula la carpeta de Matematicas Discretas a {tmp_subj_dir}")
            self.assertIn("Vinculé la materia", r_link)
            self.assertEqual(
                Path(app.get_subject_folder(db, "Matematicas Discretas")).resolve(),
                Path(tmp_subj_dir).resolve(),
            )

        r_note_del = send("borra el apunte de grafos bipartitos")
        self.assertIn("Eliminé el apunte", r_note_del)
        self.assertEqual(len(app.list_subject_notes(db, "Matematicas Discretas")), 0)

        # --- PUNTO 6: Vista semanal visual en cuadrícula (Horario Lunes–Sábado con empalmes) ---
        # Agregar una clase que se empalme el lunes de 12:00 a 14:00 para probar el resaltado de conflicto en la cuadrícula
        send("agrega clase de Fisica los lunes de 12:00 a 14:00 en el Salon A1")
        r_grid = send("muéstrame mi horario en cuadrícula")
        self.assertIn("Vista semanal en cuadrícula", r_grid)
        self.assertIn("Matematicas Discretas", r_grid)
        self.assertIn("Fisica", r_grid)
        self.assertIn("⚠️ EMPALME", r_grid)
        grid_data = app.build_weekly_grid_data(db)
        self.assertGreaterEqual(int(grid_data["conflict_count"]), 1)
        monday_items = grid_data["cells_by_day"][0]
        self.assertTrue(any(item["has_conflict"] for item in monday_items))

        # --- Verificar "prepara un bloque" y compatibilidad de payload con llama3.2 (sin "think": False) ---
        r_prep_block = send("prepara un bloque")
        self.assertIn("Para agendar un bloque", r_prep_block)
        self.assertNotIn("motor neuronal local (Ollama) no está disponible", r_prep_block)

        r_prep_block_full = send("prepara un bloque mañana de 16:00 a 17:30 para repasar grafos")
        self.assertIn("Agendé el bloque", r_prep_block_full)
        self.assertIn("repasar grafos", r_prep_block_full)

        self.assertFalse(app._model_supports_think_parameter("llama3.2"))
        self.assertFalse(app._model_supports_think_parameter("llama3.2:latest"))
        self.assertTrue(app._model_supports_think_parameter("qwen3:4b"))
        consolidated = app._consolidate_ollama_messages(
            [
                {"role": "system", "content": "Prompt base"},
                {"role": "system", "content": "Contexto de agenda"},
                {"role": "user", "content": "Hola"},
            ]
        )
        self.assertEqual(len(consolidated), 2)
        self.assertEqual(consolidated[0]["role"], "system")
        self.assertIn("Prompt base\n\nContexto de agenda", consolidated[0]["content"])

        # --- Calculadora Matemática Segura (100% local sin Ollama) ---
        self.assertIn("118", send("¿cuánto es 25 por 4 más 18?"))
        self.assertIn("12", send("calcula la raíz cuadrada de 144"))
        self.assertIn("126", send("cuánto es el 15% de 840"))
        self.assertIn("1024", send("calcula 2 elevado a la 10"))
        self.assertIn("40", send("resuelve (120 + 80) entre 5"))
        self.assertIn("dividir entre cero", send("calcula 10 / 0"))
        with self.assertRaises(ValueError):
            app.evaluate_safe_math_expression("__import__('os').system('echo pwn')")

        # --- Investigación en Internet (Wikipedia ES + DuckDuckGo) ---
        def _fake_web_urlopen(req, timeout=8):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "w/api.php" in url:
                payload = {"query": {"search": [{"title": "Algoritmo de Dijkstra", "snippet": "Camino más corto en grafos"}]}}
            elif "page/summary" in url:
                payload = {"extract": "El algoritmo de Dijkstra determina el camino más corto desde un vértice origen hacia el resto de vértices en un grafo con pesos positivos."}
            else:
                payload = {"Heading": "Dijkstra", "AbstractText": "Algoritmo clásico de caminos mínimos en teoría de grafos.", "RelatedTopics": []}

            class _Resp:
                def __enter__(self_inner):
                    return self_inner
                def __exit__(self_inner, *_a):
                    return False
                def read(self_inner):
                    return json.dumps(payload).encode("utf-8")

            return _Resp()

        with mock.patch.object(app.urllib.request, "urlopen", side_effect=_fake_web_urlopen):
            r_web = send("investiga en internet sobre el algoritmo de Dijkstra")
        self.assertIn("Investigación en internet", r_web)
        self.assertIn("Algoritmo de Dijkstra", r_web)
        self.assertIn("camino más corto", r_web)

        # --- Formato informativo de noticias sin URLs invasivas y barra superior responsiva en filas ---
        rss_rich = b"""<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel>
        <item>
            <title>Avance en baterias de estado solido - Ciencia Hoy</title>
            <link>https://news.google.com/rss/articles/CBMipgFBVV95cUxNveryLongTrackingUrl1234567890</link>
            <source>Ciencia Hoy</source>
            <description>&lt;p&gt;Investigadores lograron duplicar la densidad energetica y reducir el tiempo de carga a 10 minutos en pruebas de laboratorio.&lt;/p&gt;</description>
        </item>
        </channel></rss>"""
        rich_items = app.parse_news_feed(rss_rich, "Google News México", 5, include_details=True)
        self.assertEqual(len(rich_items), 1)
        self.assertIn("duplicar la densidad energetica", rich_items[0].get("summary", ""))
        digest = app.format_rich_news_digest(rich_items, "Google News México", "Tecnología")
        self.assertIn("Avance en baterias de estado solido", digest)
        self.assertIn("🏛️ Fuente: Ciencia Hoy", digest)
        self.assertIn("📝 Resumen: Investigadores lograron duplicar la densidad energetica", digest)
        self.assertNotIn("https://", digest)
        self.assertNotIn("Enlace:", digest)

        import inspect
        ui_src = inspect.getsource(app.AssistantApp._build_ui)
        self.assertIn("_reflow_toolbar", ui_src)
        self.assertIn("divmod(idx, cols)", ui_src)

        # --- Investigación sin cortes a mitad de palabra ni de oración (caso RMS Titanic > 560 chars) ---
        titanic_extract = (
            "El hundimiento del RMS Titanic fue una catástrofe marítima ocurrida en la noche del 14 al 15 de abril de 1912, "
            "cuando el transatlántico británico RMS Titanic —de la White Star Line—, que realizaba su viaje inaugural de "
            "Southampton a Nueva York, colisionó con un iceberg en el norte del océano Atlántico frente a las costas de Terranova. "
            "La colisión se produjo en el lado de estribor a las 23:40 del 14 de abril, lo que provocó el hundimiento del barco "
            "en menos de tres horas, a las 02:20 del 15 de abril. Fallecieron unas 1500 personas por golpes diversos, caídas, "
            "ahogamiento o hipotermia debido a las aguas heladas, convirtiéndose en uno de los peores desastres marítimos en "
            "tiempo de paz de la historia y el más famoso. El barco carecía de botes salvavidas suficientes para todos los pasajeros "
            "y los pocos más de 700 supervivientes fueron rescatados horas después por el transatlántico RMS Carpathia."
        )

        def _fake_titanic_urlopen(req, timeout=8):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "list=search" in url:
                payload = {"query": {"search": [{"title": "Hundimiento del RMS Titanic", "snippet": "Catástrofe marítima"}]}}
            elif "prop=extracts" in url:
                payload = {"query": {"pages": {"1": {"extract": titanic_extract}}}}
            elif "page/summary" in url:
                payload = {"extract": titanic_extract}
            else:
                payload = {"Heading": "", "AbstractText": "", "RelatedTopics": []}

            class _Resp:
                def __enter__(self_inner):
                    return self_inner
                def __exit__(self_inner, *_a):
                    return False
                def read(self_inner):
                    return json.dumps(payload).encode("utf-8")

            return _Resp()

        with mock.patch.object(app.urllib.request, "urlopen", side_effect=_fake_titanic_urlopen):
            r_titanic = send("investiga como se hundio el titanic")
        self.assertIn("caídas, ahogamiento o hipotermia", r_titanic)
        self.assertIn("rescatados horas después por el transatlántico RMS Carpathia.", r_titanic)
        self.assertFalse(r_titanic.rstrip().endswith("caí"))

        # --- Incremento 10: Reporte de Estado del Equipo en Tiempo Real ---
        r_pc = send("¿cómo está mi computadora?")
        self.assertIn("Estado de tu equipo y subsistemas de CLARA-V en tiempo real", r_pc)
        self.assertIn("Almacenamiento en disco:", r_pc)
        self.assertIn("GB libres", r_pc)
        self.assertIn("Memoria RAM:", r_pc)
        self.assertIn("Agenda y cuaderno local:", r_pc)

        r_disk = send("cuánto espacio libre tengo en el disco")
        self.assertIn("Almacenamiento en disco:", r_disk)
        self.assertIn("GB libres", r_disk)

        # --- Incremento 9: Modo Estudio Activo (Examen rápido y Flashcards desde tus Apuntes) ---
        send("apunta en Matemáticas Discretas que el algoritmo de Kruskal permite construir un árbol recubridor mínimo ordenando las aristas por peso")
        send("apunta en Matemáticas Discretas que un grafo bipartito es un grafo cuyos vértices se pueden dividir en dos conjuntos disjuntos U y V")
        r_quiz = send("hazme un examen rápido de Matemáticas Discretas")
        self.assertIn("Examen rápido de estudio activo", r_quiz)
        self.assertIn("Discretas", r_quiz)
        self.assertIn("¿qué es un grafo bipartito?", r_quiz)
        self.assertIn("💡 Pista:", r_quiz)

        r_ans = send("ver respuestas del examen")
        self.assertIn("Hoja de respuestas de tu examen rápido", r_ans)
        self.assertIn("Kruskal", r_ans)
        self.assertIn("grafo bipartito", r_ans)

        r_flash = send("crea tarjetas de repaso de Matemáticas Discretas")
        self.assertIn("Tarjetas de repaso activo (Flashcards)", r_flash)
        self.assertIn("❓ Pregunta:", r_flash)
        self.assertIn("✅ Respuesta:", r_flash)
        self.assertIn("Kruskal", r_flash)

        # --- Comprensión flexible para completar tareas ("3 tareas [Ingles]") y sincronización real en SQLite ---
        db.execute(
            "INSERT INTO tasks(title, subject, due_date, priority, done, created_at) VALUES(?,?,?,?,0,?)",
            ("3 tareas", "Ingles", date.today().isoformat(), "Normal", datetime.now().isoformat(timespec="seconds")),
        )
        db.commit()
        r_comp1 = send("marca la tarea de inglés como completada")
        self.assertIn("Marcada como hecha", r_comp1)
        row_ing = db.execute("SELECT done FROM tasks WHERE title='3 tareas' AND subject='Ingles'").fetchone()
        self.assertEqual(int(row_ing["done"]), 1)

        # Reset done=0 and test with "marca 3 tareas [Ingles] como completada"
        db.execute("UPDATE tasks SET done=0 WHERE title='3 tareas' AND subject='Ingles'")
        db.commit()
        r_comp2 = send("marca 3 tareas [Ingles] · entrega: 2026-10-23 como completada")
        self.assertIn("Marcada como hecha", r_comp2)
        row_ing2 = db.execute("SELECT done FROM tasks WHERE title='3 tareas' AND subject='Ingles'").fetchone()
        self.assertEqual(int(row_ing2["done"]), 1)

        # Reset done=0 and test Ollama-implied completion sync safety net
        db.execute("UPDATE tasks SET done=0 WHERE title='3 tareas' AND subject='Ingles'")
        db.commit()
        sync_msg = app.sync_ollama_implied_task_actions(
            db,
            "marcame lo de ingles como completada",
            "- 3 tareas [Ingles] · entrega: 2026-10-23 (COMPLETADA)",
        )
        self.assertIsNotNone(sync_msg)
        row_ing3 = db.execute("SELECT done FROM tasks WHERE title='3 tareas' AND subject='Ingles'").fetchone()
        self.assertEqual(int(row_ing3["done"]), 1)

        # --- Programación relativa al horario real de clases ("una hora antes a mi primera clase del dia en todos los dias") ---
        r_rel = send("Agrega Ir a la Universidad una hora antes a mi primera clase del dia en todos los dias.")
        self.assertIn("Calculé y programé «Ir a la Universidad»", r_rel)
        self.assertIn("antes de", r_rel)
        routine_uni = db.execute("SELECT * FROM routines WHERE title='Ir a la Universidad'").fetchall()
        self.assertGreaterEqual(len(routine_uni), 1)
        blocks_uni = db.execute("SELECT * FROM plan_blocks WHERE title='Ir a la Universidad'").fetchall()
        self.assertGreaterEqual(len(blocks_uni), 1)

        r_rel_after = send("Agrega Regresar a casa media hora después de mi última clase en todos los días")
        self.assertIn("Calculé y programé «Regresar a casa»", r_rel_after)
        self.assertIn("30 min después", r_rel_after)


if __name__ == "__main__":
    unittest.main()



