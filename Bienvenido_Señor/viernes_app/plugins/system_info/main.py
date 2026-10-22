from __future__ import annotations


def register(api) -> None:
    from viernes_app.core.tool_router import ToolResult

    def plugin_status(_request, runtime):
        loaded = []
        manager = getattr(runtime, "plugin_manager", None)
        if manager is not None:
            loaded = [item.name for item in getattr(manager, "records", []) if not item.error]
        return ToolResult(True, "Plugins activos: " + (", ".join(loaded) if loaded else "ninguno"))

    api.register_tool("plugin_status", "memory_read", "Muestra plugins activos.", plugin_status)
