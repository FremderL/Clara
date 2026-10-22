import hashlib
import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"
SPEC = importlib.util.spec_from_file_location("clara_app_under_test", APP_PATH)
APP = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = APP
SPEC.loader.exec_module(APP)


class Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self, _limit):
        return self.body


class HelperTests(unittest.TestCase):
    def test_legacy_chat_speaker_displays_as_clara_without_changing_other_speakers(self):
        self.assertEqual(APP.display_chat_speaker("Luma"), "Clara")
        self.assertEqual(APP.display_chat_speaker("Tú"), "Tú")
        self.assertEqual(APP.display_chat_speaker("Clara"), "Clara")

    def allow_temp_container_ancestors(self, selected_root):
        """Ignore Windows Temp's AppData/hidden attributes, never fixture descendants."""
        selected = Path(selected_root).absolute()
        temp_base = Path(tempfile.gettempdir()).absolute()
        container = next((part for part in (selected, *selected.parents) if part.parent == temp_base), None)
        if container is None:
            return patch.object(APP, "_path_has_hidden_system_or_reparse", wraps=APP._path_has_hidden_system_or_reparse)
        original = APP._path_has_hidden_system_or_reparse

        def check(path, stat_result=None):
            candidate = Path(path).absolute()
            try:
                container.relative_to(candidate)
            except ValueError:
                return original(path, stat_result)
            # candidate is the TemporaryDirectory itself or one of its ancestors.
            return False

        return patch.object(APP, "_path_has_hidden_system_or_reparse", side_effect=check)

    def scan_fixture(self, *args, **kwargs):
        # Windows temp folders commonly live under AppData and may have the
        # hidden attribute. Bypass only their ancestors; fixture entries retain checks.
        safe_names = set(APP.PROTECTED_FOLDER_NAMES) - {"appdata"}
        with patch.object(APP, "PROTECTED_FOLDER_NAMES", safe_names), self.allow_temp_container_ancestors(args[0]):
            return APP.scan_local_documents(*args, **kwargs)

    def validate_open_fixture(self, *args, **kwargs):
        safe_names = set(APP.PROTECTED_FOLDER_NAMES) - {"appdata"}
        with patch.object(APP, "PROTECTED_FOLDER_NAMES", safe_names), self.allow_temp_container_ancestors(args[0]):
            return APP.validate_local_document_for_open(*args, **kwargs)

    def prepare_move_fixture(self, *args, **kwargs):
        safe_names = set(APP.PROTECTED_FOLDER_NAMES) - {"appdata"}
        with patch.object(APP, "PROTECTED_FOLDER_NAMES", safe_names), self.allow_temp_container_ancestors(args[0]):
            return APP.prepare_local_move(*args, **kwargs)

    def test_allowed_app_list_validation_and_pe_gui_filter(self):
        self.assertEqual(APP.normalize_allowed_applications("not json"), "[]")
        self.assertEqual(APP.load_allowed_applications({"allowed_applications": "[]"}), [])
        with tempfile.TemporaryDirectory() as directory:
            gui = Path(directory) / "sample.exe"
            image = bytearray(0x80 + 24 + 70)
            image[:2] = b"MZ"
            APP.struct.pack_into("<I", image, 0x3C, 0x80)
            image[0x80:0x84] = b"PE\0\0"
            APP.struct.pack_into("<H", image, 0x80 + 4 + 16, 70)
            APP.struct.pack_into("<H", image, 0x80 + 24, 0x10B)
            APP.struct.pack_into("<H", image, 0x80 + 24 + 68, 2)
            gui.write_bytes(image)
            self.assertTrue(APP.is_windows_gui_executable(gui))
            APP.struct.pack_into("<H", image, 0x80 + 24 + 68, 3)
            gui.write_bytes(image)
            self.assertFalse(APP.is_windows_gui_executable(gui))

    def test_allowed_app_launch_uses_exact_exe_no_shell_no_args(self):
        record = {"path": r"C:\\Program Files\\Example\\example.exe", "name": "example.exe", "size": 1, "mtime_ns": 2, "file_id": (3, 4)}
        process = object()
        current = dict(record)
        with patch.object(APP, "validate_local_application", return_value=current) as validate, patch.object(APP.subprocess, "Popen", return_value=process) as popen:
            result = APP.launch_allowed_application(record, platform_name="win32")
        validate.assert_called_once_with(record["path"], "win32")
        popen.assert_called_once_with([record["path"]], shell=False, cwd=str(Path(record["path"]).parent), close_fds=True)
        self.assertIs(result, process)
        with patch.object(APP, "validate_local_application", return_value={**record, "size": 2}), patch.object(APP.subprocess, "Popen") as popen:
            with self.assertRaisesRegex(ValueError, "cambió"):
                APP.launch_allowed_application(record, platform_name="win32")
            popen.assert_not_called()

    def test_activity_log_records_category_without_path(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = sqlite3.connect(Path(directory) / "events.db")
            connection.execute("CREATE TABLE action_events (id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT, outcome TEXT, created_at TEXT)")
            fake_app = SimpleNamespace(db=connection)
            saved = APP.AssistantApp._record_private_action_event(fake_app, "Mover documento permitido", "Confirmado; nombre/rutas omitidos")
            row = connection.execute("SELECT action, outcome FROM action_events").fetchone()
            self.assertTrue(saved)
            self.assertEqual(row[0], "Mover documento permitido")
            self.assertNotIn("/home/", row[1])
            self.assertNotIn("\\\\", row[1])
            connection.close()

    def test_action_history_csv_contains_only_saved_generic_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            connection = sqlite3.connect(Path(directory) / "events.db")
            connection.execute("CREATE TABLE action_events (id INTEGER PRIMARY KEY, created_at TEXT, action TEXT, outcome TEXT)")
            connection.execute("INSERT INTO action_events VALUES (1, '2026-10-17T12:00:00', 'Iniciar aplicación autorizada', 'Inicio solicitado; nombre/ruta omitidos')")
            destination = Path(directory) / "activity.csv"
            self.assertEqual(APP.export_action_history_csv(connection, destination), 1)
            content = destination.read_text(encoding="utf-8-sig")
            self.assertIn("Fecha,Acción,Resultado", content)
            self.assertIn("Iniciar aplicación autorizada", content)
            self.assertNotIn("/home/", content)
            connection.close()

    def test_backup_extractor_accepts_only_expected_members_and_respects_limits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive_path = root / "good.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("asistente.db", b"sqlite snapshot")
                archive.writestr("settings.json", b"{}")
            target = root / "extract"
            db_path, settings_path = APP.extract_validated_backup(archive_path, target)
            self.assertEqual(db_path.read_bytes(), b"sqlite snapshot")
            self.assertEqual(settings_path.read_bytes(), b"{}")
            with self.assertRaisesRegex(ValueError, "demasiado grande"):
                APP.extract_validated_backup(archive_path, root / "small", max_database_bytes=4)
            with self.assertRaisesRegex(ValueError, "límite de tamaño"):
                APP.extract_validated_backup(archive_path, root / "total", max_total_bytes=4)

    def test_backup_extractor_rejects_extra_duplicate_and_missing_members(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            traversal = root / "traversal.zip"
            with zipfile.ZipFile(traversal, "w") as archive:
                archive.writestr("asistente.db", b"db")
                archive.writestr("../outside.txt", b"no")
            with self.assertRaisesRegex(ValueError, "formato"):
                APP.extract_validated_backup(traversal, root / "out1")
            missing = root / "missing.zip"
            with zipfile.ZipFile(missing, "w") as archive:
                archive.writestr("settings.json", b"{}")
            with self.assertRaisesRegex(ValueError, "formato"):
                APP.extract_validated_backup(missing, root / "out2")
            duplicate = root / "duplicate.zip"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with zipfile.ZipFile(duplicate, "w") as archive:
                    archive.writestr("asistente.db", b"db1")
                    archive.writestr("asistente.db", b"db2")
            with self.assertRaisesRegex(ValueError, "formato"):
                APP.extract_validated_backup(duplicate, root / "out3")

    def test_sha256_is_local_stream_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.bin"
            path.write_bytes(b"abc")
            digest, size = APP.hash_file_sha256(path)
        self.assertEqual(digest, hashlib.sha256(b"abc").hexdigest())
        self.assertEqual(size, 3)

    def test_chat_intent_validation_is_closed_schema_and_never_accepts_paths(self):
        valid_general = APP.validate_chat_intent(json.dumps({"intent": "general", "response": "Hola"}))
        self.assertEqual(valid_general, {"intent": "general", "response": "Hola"})
        task = APP.validate_chat_intent(json.dumps({"intent": "task_draft", "title": "Leer capítulo", "subject": "Biología", "due_date": "2026-10-20", "due_time": None, "description": None}))
        self.assertEqual(task["due_date"], "2026-10-20")
        block = APP.validate_chat_intent(json.dumps({"intent": "block_draft", "title": "Estudiar", "block_date": "2026-10-20", "start_time": "15:00", "end_time": "16:00", "notes": None}))
        self.assertEqual(block["intent"], "block_draft")
        self.assertIsNone(APP.validate_chat_intent(json.dumps({"intent": "block_draft", "title": "Estudiar", "block_date": "2026-10-20", "start_time": "16:00", "end_time": "15:00", "notes": None})))
        self.assertIsNone(APP.validate_chat_intent(json.dumps({"intent": "file_search", "query": "C:\\\\Users\\\\Ada\\\\notes", "extension": ".pdf"})))
        self.assertIsNone(APP.validate_chat_intent(json.dumps({"intent": "file_search", "query": "notes", "extension": ".exe"})))
        self.assertIsNone(APP.validate_chat_intent(json.dumps({"intent": "general", "response": "No action", "path": "C:\\\\secret"})))
        self.assertIsNone(APP.validate_chat_intent("not json"))

    def test_file_intent_only_opens_existing_manual_tool(self):
        opened = []
        spoken = []
        fake_app = SimpleNamespace(
            append_chat=lambda *_args, **_kwargs: None,
            open_local_file_tools=lambda **kwargs: opened.append(kwargs),
            settings={"auto_speak_responses": "false"},
            _start_tts=lambda *args, **kwargs: spoken.append(args),
        )
        intent = {"intent": "file_move", "query": "biology", "extension": ".pdf"}
        answer = APP.AssistantApp.apply_chat_intent(fake_app, "mueve el PDF de biología", intent)
        self.assertIn("confirmación individual", answer)
        self.assertEqual(opened, [{"intent": intent}])
        self.assertEqual(spoken, [])

    def test_virustotal_uses_get_hash_and_key_header(self):
        digest = "a" * 64
        body = json.dumps({"data": {"attributes": {
            "last_analysis_stats": {"malicious": 1},
            "last_analysis_results": {"TestEngine": {"category": "malicious", "result": "Example"}},
        }}}).encode()

        class Opener:
            def open(self, request, timeout):
                self_request = request
                self.assertions = (
                    self_request.get_method() == "GET"
                    and self_request.full_url.endswith("/" + digest)
                    and self_request.get_header("X-apikey") == "fake-key"
                    and timeout == 20
                )
                return Response(body)

        opener = Opener()
        with patch.object(APP.urllib.request, "build_opener", return_value=opener):
            result = APP.virustotal_lookup(digest, "fake-key")
        self.assertTrue(opener.assertions)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["detections"], [("TestEngine", "malicious", "Example")])

    def test_virustotal_404_has_no_automatic_retry(self):
        digest = "b" * 64

        class Opener:
            calls = 0

            def open(self, _request, timeout):
                self.calls += 1
                raise HTTPError("https://www.virustotal.com", 404, "not found", {}, None)

        opener = Opener()
        with patch.object(APP.urllib.request, "build_opener", return_value=opener):
            result = APP.virustotal_lookup(digest, "fake-key")
        self.assertEqual(result["status"], "not_found")
        self.assertEqual(opener.calls, 1)

    def test_rss_source_link_limit_and_xml_defenses(self):
        xml = b"<rss><channel><item><title>Headline</title><source>Publisher</source><link>https://example.test/a</link></item></channel></rss>"
        parsed = APP.parse_news_feed(xml, "Fallback", 3)
        self.assertEqual(parsed, [{"title": "Headline", "source": "Publisher", "link": "https://example.test/a"}])
        with self.assertRaises(ValueError):
            APP.parse_news_feed(b"<rss>" + b" " * 5000 + b"<!DOCTYPE x><item/></rss>", "Feed", 5)
        with self.assertRaises(ValueError):
            APP.parse_news_feed(b"x" * (2 * 1024 * 1024 + 1), "Feed", 5)

    def test_task_parser_relative_dates_and_incomplete_title_stay_drafts(self):
        fake_app = SimpleNamespace(db=SimpleNamespace(execute=lambda *_args, **_kwargs: []))
        parse = APP.AssistantApp.parse_task_proposal
        result = parse(fake_app, "hacer ejercicios dentro de 3 días", today=APP.date(2026, 10, 17))
        self.assertEqual(result["due_date"], "2026-10-20")
        self.assertEqual(result["title"], "ejercicios")
        incomplete = parse(fake_app, "me dejaron una tarea para entregar el 5 de noviembre a las 6 pm", today=APP.date(2026, 10, 17))
        self.assertEqual(incomplete["title"], "Tarea nueva")
        self.assertEqual(incomplete["due_date"], "2026-11-05")
        self.assertEqual(incomplete["due_time"], "18:00")

    def test_local_search_is_recursive_name_type_only_and_excludes_hidden_and_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "biology.pdf").write_bytes(b"not parsed or opened")
            sub = root / "week 1"
            sub.mkdir()
            (sub / "Biology notes.DOCX").write_bytes(b"not parsed")
            (sub / "run.ps1").write_text("should never be listed", encoding="utf-8")
            hidden = root / ".hidden"
            hidden.mkdir()
            (hidden / "biology.txt").write_text("excluded", encoding="utf-8")
            results = self.scan_fixture(root, "biology", recursive=True)
            self.assertEqual({row["name"] for row in results["results"]}, {"biology.pdf", "Biology notes.DOCX"})
            self.assertTrue(all(row["kind"] in {"PDF", "DOCX"} for row in results["results"]))
            filtered = self.scan_fixture(root, "biology", extension=".pdf", recursive=True)
            self.assertEqual([row["name"] for row in filtered["results"]], ["biology.pdf"])

    def test_folder_inventory_lists_metadata_not_contents_and_can_be_recursive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "readme.txt").write_text("secret text must not appear", encoding="utf-8")
            sub = root / "subfolder"
            sub.mkdir()
            (sub / "notes.md").write_text("also not read", encoding="utf-8")
            (root / "tool.exe").write_bytes(b"binary")
            immediate = self.scan_fixture(root, inventory=True, recursive=False)
            self.assertEqual({row["name"] for row in immediate["results"]}, {"readme.txt", "subfolder"})
            recursive = self.scan_fixture(root, inventory=True, recursive=True)
            self.assertEqual({row["name"] for row in recursive["results"]}, {"readme.txt", "subfolder", "notes.md"})
            self.assertTrue(all("path" in row and "modified" in row for row in recursive["results"]))
            self.assertNotIn("secret text", str(recursive["results"]))

    def test_open_preflight_rejects_changed_or_unsupported_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = root / "notes.pdf"
            document.write_bytes(b"example")
            scanned = self.scan_fixture(root)
            row = scanned["results"][0]
            current_stat = document.stat(follow_symlinks=False)
            self.assertEqual(row["file_id"], (current_stat.st_dev, current_stat.st_ino))
            self.assertNotEqual(row["file_id"], (0, 0))
            self.assertEqual(self.validate_open_fixture(root, document, row["size"], row["mtime_ns"], row["file_id"]), document.resolve())
            # Windows DirEntry.stat can return an unusable (0, 0) identity; it must not reject a stable file.
            self.assertEqual(self.validate_open_fixture(root, document, row["size"], row["mtime_ns"], (0, 0)), document.resolve())
            document.write_bytes(b"changed since search")
            changed = document.stat()
            APP.os.utime(document, ns=(changed.st_atime_ns, max(changed.st_mtime_ns, row["mtime_ns"]) + 2_000_000_000))
            with self.assertRaisesRegex(ValueError, "cambió"):
                self.validate_open_fixture(root, document, row["size"], row["mtime_ns"], row["file_id"])
            executable = root / "tool.exe"
            executable.write_bytes(b"not allowed")
            info = executable.stat()
            with self.assertRaises(ValueError):
                self.validate_open_fixture(root, executable, info.st_size, info.st_mtime_ns, (info.st_dev, info.st_ino))
            outside = root.parent / "outside.pdf"
            outside.write_bytes(b"outside")
            outside_info = outside.stat()
            with self.assertRaisesRegex(ValueError, "dentro"):
                self.validate_open_fixture(root, outside, outside_info.st_size, outside_info.st_mtime_ns, (outside_info.st_dev, outside_info.st_ino))
            link = root / "alias.pdf"
            try:
                link.symlink_to(document)
            except (OSError, NotImplementedError):
                return
            current = document.stat()
            with self.assertRaises(ValueError):
                self.validate_open_fixture(root, link, current.st_size, current.st_mtime_ns, (current.st_dev, current.st_ino))

    def test_move_preview_is_single_file_same_volume_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_root = root / "source"
            destination = root / "destination"
            source_root.mkdir()
            destination.mkdir()
            document = source_root / "notes.pdf"
            document.write_bytes(b"do not read")
            row = self.scan_fixture(source_root)["results"][0]
            plan = self.prepare_move_fixture(source_root, document, destination, row["size"], row["mtime_ns"], row["file_id"])
            self.assertEqual(Path(plan["source"]), document)
            self.assertEqual(Path(plan["destination"]), destination / document.name)
            self.assertTrue(document.exists())  # planning alone must never move
            with self.assertRaises(OSError):
                APP.execute_local_move(plan, platform_name="linux")
            self.assertTrue(document.exists())
            (destination / document.name).write_bytes(b"do not overwrite")
            with self.assertRaises(FileExistsError):
                self.prepare_move_fixture(source_root, document, destination, row["size"], row["mtime_ns"], row["file_id"])
            with self.assertRaises(ValueError):
                self.prepare_move_fixture(source_root, document, source_root, row["size"], row["mtime_ns"], row["file_id"])

    def test_local_search_bounds_cancel_and_reject_unsupported_filter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.pdf").write_bytes(b"a")
            (root / "b.pdf").write_bytes(b"b")
            cancelled = APP.threading.Event()
            cancelled.set()
            result = self.scan_fixture(root, cancel_event=cancelled)
            self.assertEqual(result["status"], "cancelled")
            limited = self.scan_fixture(root, max_entries=1)
            self.assertEqual(limited["status"], "entry_limit")
            with self.assertRaises(ValueError):
                self.scan_fixture(root, extension=".exe")

    def test_selected_root_rejects_symlink_and_system_folder_names(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            link = root / "link"
            target = root / "target"
            target.mkdir()
            try:
                link.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks are unavailable in this environment")
            safe_names = set(APP.PROTECTED_FOLDER_NAMES) - {"appdata"}
            with patch.object(APP, "PROTECTED_FOLDER_NAMES", safe_names), self.allow_temp_container_ancestors(root):
                with self.assertRaises(ValueError):
                    APP.validate_local_search_root(link)
                protected = root / "Windows"
                protected.mkdir()
                with self.assertRaises(ValueError):
                    APP.validate_local_search_root(protected)
                hidden_parent = root / ".private"
                hidden_child = hidden_parent / "visible-name"
                hidden_child.mkdir(parents=True)
                with self.assertRaises(ValueError):
                    APP.validate_local_search_root(hidden_child)
                alias_parent = root / "directory-alias"
                (target / "child").mkdir()
                try:
                    alias_parent.symlink_to(target, target_is_directory=True)
                    with self.assertRaises(ValueError):
                        APP.validate_local_search_root(alias_parent / "child")
                except (OSError, NotImplementedError):
                    pass
                cloud = root / "OneDrive - Personal"
                cloud.mkdir()
                with self.assertRaises(ValueError):
                    APP.validate_local_search_root(cloud)
                with patch.dict(APP.os.environ, {"USERPROFILE": str(root)}):
                    with self.assertRaises(ValueError):
                        APP.validate_local_search_root(root)

    def test_folder_scope_and_mocked_windows_launcher(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "selected"
            folder.mkdir()
            file = root / "not-a-folder"
            file.write_text("x", encoding="utf-8")
            self.assertEqual(APP.validate_selected_folder(folder), folder.resolve())
            with self.assertRaises(ValueError):
                APP.validate_selected_folder(file)
            with patch.object(APP.sys, "platform", "win32"), patch.object(APP.os, "startfile", create=True) as start:
                APP.launch_selected_folder(folder)
                start.assert_called_once_with(str(folder.resolve()))

    def test_optional_chat_history_is_off_and_records_only_direct_turns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            previous = (APP.DATA_DIR, APP.DB_PATH, APP.SETTINGS_PATH)
            APP.DATA_DIR, APP.DB_PATH, APP.SETTINGS_PATH = root, root / "db.sqlite", root / "settings.json"
            try:
                loaded_settings = APP.load_settings()
                self.assertEqual(loaded_settings["chat_history_enabled"], "false")
                self.assertEqual(loaded_settings["auto_speak_responses"], "true")
                db = APP.connect_db()
                class TextSink:
                    def configure(self, **_kwargs): pass
                    def insert(self, *_args): pass
                    def see(self, *_args): pass
                spoken = []
                fake_app = SimpleNamespace(
                    chat_log=TextSink(), settings={"chat_history_enabled": "true", "auto_speak_responses": "true"}, db=db,
                    last_assistant_response="", ollama_status=SimpleNamespace(configure=lambda **_kwargs: None),
                    _start_tts=lambda text, manual=False: spoken.append(text),
                )
                APP.AssistantApp.append_chat(fake_app, "Tú", "hola")
                APP.AssistantApp.append_chat(fake_app, "Asistente", "respuesta")
                APP.AssistantApp.append_chat(fake_app, "Sistema", "estado no persistido")
                self.assertEqual(db.execute("SELECT COUNT(*) FROM chat_history").fetchone()[0], 2)
                self.assertEqual(spoken, ["respuesta"])
                db.close()
            finally:
                APP.DATA_DIR, APP.DB_PATH, APP.SETTINGS_PATH = previous

    def test_reminder_pause_expires_and_settings_never_load_api_key(self):
        base = APP.datetime(2026, 10, 17, 18, 0)
        self.assertTrue(APP.reminder_pause_active({"reminders_paused_until": "2026-10-17T19:00:00"}, base))
        self.assertFalse(APP.reminder_pause_active({"reminders_paused_until": "2026-10-17T17:00:00"}, base))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = (APP.DATA_DIR, APP.SETTINGS_PATH)
            APP.DATA_DIR, APP.SETTINGS_PATH = root, root / "settings.json"
            try:
                APP.SETTINGS_PATH.write_text(json.dumps({"virustotal_api_key": "not-a-setting"}), encoding="utf-8")
                settings = APP.load_settings()
                self.assertNotIn("virustotal_api_key", settings)
                self.assertNotIn("virustotal_api_key", APP.DEFAULT_SETTINGS)
            finally:
                APP.DATA_DIR, APP.SETTINGS_PATH = old


if __name__ == "__main__":
    unittest.main()
