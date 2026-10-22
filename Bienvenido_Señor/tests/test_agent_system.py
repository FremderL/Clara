from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from security.audit import SecurityAuditLog
from security.permissions import PermissionManager, PermissionPolicy
from security.user_levels import UserLevel
from viernes_app.core.memory_manager import PersistentMemoryManager
from viernes_app.core.assistant import ViernesAssistant, normalize_text
from viernes_app.core.planner import AgentPlanner
from viernes_app.core.self_improvement.coder import ImprovementCoder
from viernes_app.core.self_improvement.analyzer import ImprovementAnalysis
from viernes_app.core.tool_router import ToolRequest, ToolRouter
from viernes_app.plugins.manager import PluginManager
from viernes_app.services.security_monitor import SecurityMonitor
from viernes_app.ui.modern import should_use_modern_ui
from viernes_app.voice.profiles import VoiceProfile, VoiceProfileManager
from viernes_app.voice.voice import ViernesVoice
from viernes_app.voice.wake_word import WakeWordDetector


class AgentPlannerTests(unittest.TestCase):
    def test_document_request_creates_structured_confirmable_plan(self) -> None:
        plan = AgentPlanner().create_plan("Organiza mis documentos")

        titles = [step.title for step in plan.ordered_steps()]
        self.assertEqual("Analizar carpetas", titles[0])
        self.assertIn("Mover archivos", titles)
        self.assertTrue(plan.requires_confirmation)

    def test_execute_plan_dry_run_blocks_mutating_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            planner = AgentPlanner(Path(tmp) / "plans.json")
            plan = planner.create_plan("Organiza mis documentos", context={"path": tmp})
            report = planner.execute_plan(plan.id)

        self.assertEqual("blocked", report.status)
        self.assertGreaterEqual(report.blocked_steps, 1)
        self.assertTrue(report.dry_run)


class AssistantWakeWordTests(unittest.TestCase):
    def test_wake_word_alone_is_not_greeting(self) -> None:
        assistant = ViernesAssistant.__new__(ViernesAssistant)
        assistant.config = {"wake_word": "viernes"}

        _original, low, wake_only = assistant._strip_wake_word_prefix("Viernes", normalize_text("Viernes"))

        self.assertEqual("viernes", low)
        self.assertTrue(wake_only)

    def test_wake_word_prefix_is_removed_for_one_shot_voice(self) -> None:
        assistant = ViernesAssistant.__new__(ViernesAssistant)
        assistant.config = {"wake_word": "viernes"}

        original, low, wake_only = assistant._strip_wake_word_prefix(
            "Viernes abre calendario",
            normalize_text("Viernes abre calendario"),
        )

        self.assertEqual("abre calendario", low)
        self.assertEqual("abre calendario", original)
        self.assertFalse(wake_only)


class PersistentMemoryTests(unittest.TestCase):
    def test_memory_persists_context_for_ollama(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = PersistentMemoryManager(Path(tmp))
            manager.remember_long_term("El proyecto principal es Viernes", kind="project")
            manager.set_preference("respuesta", "breve")
            manager.record_conversation("user", "recuerda revisar plugins")

            reloaded = PersistentMemoryManager(Path(tmp))
            context = reloaded.context_for_ollama("plugins")

        self.assertIn("Viernes", context)
        self.assertIn("respuesta", context)
        self.assertIn("plugins", context)

    def test_memory_public_api_redacts_ollama_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = PersistentMemoryManager(Path(tmp))
            manager.remember("long_term", "credential", "token: abc123 usuario demo@example.com")
            context = manager.build_ollama_context("credential", 500)

        self.assertIn("[redacted]", context)
        self.assertIn("[email redacted]", context)
        self.assertNotIn("abc123", context)


class PermissionAndToolRouterTests(unittest.TestCase):
    def test_tool_router_denies_write_without_level_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = PermissionPolicy(current_level=UserLevel.BASIC_TOOLS, allowed_roots=[root])
            router = ToolRouter(PermissionManager(policy))
            request = router.route(f"escribir archivo {root / 'x.txt'}: hola", user_level=1)
            result = router.execute(request)

        self.assertFalse(result.ok)
        self.assertIn("Permiso denegado", result.message)

    def test_tool_router_reads_authorized_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "nota.txt"
            target.write_text("hola viernes", encoding="utf-8")
            policy = PermissionPolicy(current_level=UserLevel.BASIC_TOOLS, allowed_roots=[root])
            router = ToolRouter(PermissionManager(policy))
            request = router.route(f"leer archivo {target}", user_level=1)
            result = router.execute(request)

        self.assertTrue(result.ok)
        self.assertIn("hola viernes", result.message)

    def test_unknown_permission_action_is_denied_by_default(self) -> None:
        decision = PermissionManager(PermissionPolicy(current_level=UserLevel.ADMIN)).check("unknown_tool")

        self.assertFalse(decision.allowed)
        self.assertEqual("accion no registrada", decision.reason)

    def test_tool_router_unknown_tool_is_recoverable(self) -> None:
        router = ToolRouter(PermissionManager(PermissionPolicy()))
        result = router.execute(ToolRequest("inventada", "plugin_tool", "herramienta inventada imposible"))

        self.assertFalse(result.ok)
        self.assertIn("Herramienta no registrada", result.message)
        self.assertEqual("listar_herramientas", result.data["next_step"])

    def test_tool_router_requires_confirmation_for_level_two_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = PermissionPolicy(current_level=UserLevel.MUTATION, allowed_roots=[root])
            router = ToolRouter(PermissionManager(policy))
            request = router.route(f"escribir archivo {root / 'x.txt'}: hola", user_level=2)
            result = router.execute(request)

        self.assertFalse(result.ok)
        self.assertIn("requiere confirmacion", result.message)

    def test_tool_router_confirmed_write_mutates_authorized_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "x.txt"
            policy = PermissionPolicy(current_level=UserLevel.MUTATION, allowed_roots=[root])
            router = ToolRouter(PermissionManager(policy))
            request = router.route(f"confirmado escribir archivo {target}: hola", user_level=2)
            result = router.execute(request)

            self.assertTrue(result.ok)
            self.assertEqual("hola", target.read_text(encoding="utf-8"))

    def test_document_organizer_preview_does_not_move_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "nota.pdf"
            source.write_text("pdf", encoding="utf-8")
            policy = PermissionPolicy(current_level=UserLevel.BASIC_TOOLS, allowed_roots=[root])
            router = ToolRouter(PermissionManager(policy))
            request = router.route(f"organiza documentos en {root}", user_level=1)
            result = router.execute(request)

            self.assertTrue(result.ok)
            self.assertTrue(source.exists())
            self.assertIn("plan", result.data)


class PluginManagerTests(unittest.TestCase):
    def test_plugin_registers_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugins = Path(tmp)
            plugin = plugins / "demo"
            plugin.mkdir()
            (plugin / "plugin.json").write_text('{"name":"demo","version":"1.0.0"}', encoding="utf-8")
            (plugin / "main.py").write_text(
                "def register(api):\n"
                "    from viernes_app.core.tool_router import ToolResult\n"
                "    api.register_tool('demo_tool', 'conversation', 'Demo', lambda request, runtime: ToolResult(True, 'ok'))\n",
                encoding="utf-8",
            )
            router = ToolRouter(PermissionManager(PermissionPolicy()))
            records = PluginManager(plugins).load_plugins(tool_router=router)

        self.assertEqual(1, len(records))
        self.assertFalse(records[0].error)
        self.assertIn("demo_tool", [tool["name"] for tool in router.list_tools()])

    def test_plugin_invalid_manifest_is_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plugins = Path(tmp)
            plugin = plugins / "bad"
            plugin.mkdir()
            (plugin / "plugin.json").write_text('{"name":"bad"}', encoding="utf-8")
            (plugin / "main.py").write_text("def register(api): pass\n", encoding="utf-8")
            records = PluginManager(plugins).load_plugins(tool_router=ToolRouter(PermissionManager(PermissionPolicy())))

        self.assertEqual(1, len(records))
        self.assertTrue(records[0].error)


class SelfImprovementTests(unittest.TestCase):
    def test_change_proposal_is_persisted_without_code_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            coder = ImprovementCoder()
            analysis = ImprovementAnalysis("mejora seguridad", [], ["viernes_app/core/tool_router.py"])
            proposal = coder.draft_proposal(analysis)
            path = coder.save_proposal(proposal, analysis=analysis, root=Path(tmp))
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertFalse(payload["policy"]["direct_code_mutation"])
        self.assertEqual(proposal.id, payload["proposal"]["id"])


class SecurityMonitorAndVoiceTests(unittest.TestCase):
    def test_security_monitor_reports_missing_critical_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.json"
            monitor = SecurityMonitor([missing])
            monitor.establish_baseline()
            alerts = monitor.scan()

        self.assertTrue(any(alert.kind == "critical_file_missing" for alert in alerts))

    def test_security_monitor_persists_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            critical = root / "config.json"
            critical.write_text("{}", encoding="utf-8")
            baseline = root / "baseline.json"
            monitor = SecurityMonitor([critical], baseline_path=baseline)
            first = monitor.establish_baseline()
            reloaded = SecurityMonitor([critical], baseline_path=baseline)

            self.assertEqual(first, reloaded.snapshot_files())

    def test_wake_word_detector_extracts_command(self) -> None:
        result = WakeWordDetector("viernes").detect("Viernes abre calendario")

        self.assertTrue(result.detected)
        self.assertEqual("abre calendario", result.command)

    def test_voice_profile_manager_and_voice_apply_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manager = VoiceProfileManager(Path(tmp) / "profiles.json")
            manager.save_profile(VoiceProfile("rapida", rate=190, wake_word="asistente"))
            profile = manager.get("rapida")
            voice = ViernesVoice(enabled=False)
            voice.apply_profile(profile)

            self.assertEqual(190, voice.rate)
            self.assertIn("rapida", manager.names())


class ModernUITests(unittest.TestCase):
    def test_modern_ui_is_opt_in(self) -> None:
        self.assertFalse(should_use_modern_ui({"ui": {"mode": "classic"}}))
        self.assertTrue(should_use_modern_ui({"ui": {"mode": "modern"}}))

    def test_modern_shell_formats_recoverable_errors(self) -> None:
        from viernes_app.ui.modern import ModernShell

        shell = ModernShell.__new__(ModernShell)
        message = shell._recoverable_error("estado agentes", RuntimeError("boom"), panel="Dashboard")

        self.assertIn("No pude completar Dashboard", message)
        self.assertIn("Siguiente intento", message)


if __name__ == "__main__":
    unittest.main()
