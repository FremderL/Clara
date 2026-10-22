from __future__ import annotations

import json
import os
import re
import socket
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from viernes_app.paths import CONFIG_PATH as CONFIG_PATH_REF
from viernes_app.paths import REPO_ROOT

CONFIG_PATH = CONFIG_PATH_REF
ROOT_DIR = REPO_ROOT
DEFAULT_TASK_NAME = "Viernes Morning Wake"
STARTUP_CMD_PATH = REPO_ROOT / "viernes_start.cmd"
MORNING_CMD_PATH = REPO_ROOT / "viernes_morning.cmd"
INSTALL_SCRIPT_PATH = REPO_ROOT / "scripts" / "windows" / "install_viernes_autostart.ps1"
REMOVE_SCRIPT_PATH = REPO_ROOT / "scripts" / "windows" / "remove_viernes_autostart.ps1"


def _ps_quote(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _run_powershell(command: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _write_launcher_scripts() -> None:
    scripts = {
        STARTUP_CMD_PATH: "gui",
        MORNING_CMD_PATH: "morning",
    }
    for path, mode in scripts.items():
        path.write_text(
            "\r\n".join(
                [
                    "@echo off",
                    "setlocal",
                    'pushd "%~dp0" || exit /b 1',
                    f'py "%~dp0viernes.py" --mode {mode}',
                    "popd",
                    "",
                ]
            ),
            encoding="utf-8",
        )


def _is_hhmm(value: str) -> bool:
    try:
        datetime.strptime(str(value).strip(), "%H:%M")
        return True
    except ValueError:
        return False


def _update_wake_config(*, enabled: bool | None, wake_time: str | None = None, startup_enabled: bool | None = None) -> bool:
    """Persist only the state that Windows has already confirmed."""
    try:
        cfg: dict[str, Any] = {}
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, encoding="utf-8") as handle:
                loaded = json.load(handle)
                if isinstance(loaded, dict):
                    cfg = loaded
        automation = cfg.setdefault("automation", {})
        if not isinstance(automation, dict):
            automation = {}
            cfg["automation"] = automation
        if wake_time and _is_hhmm(wake_time):
            automation["morning_wake_time"] = wake_time
        if startup_enabled is not None:
            automation["startup_enabled"] = bool(startup_enabled)
        if enabled is not None:
            cfg["morning_wake_enabled"] = bool(enabled)
        temp_path = CONFIG_PATH.with_suffix(CONFIG_PATH.suffix + ".tmp")
        temp_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, CONFIG_PATH)
        return True
    except Exception:
        return False


def _configured_wake_time() -> str:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        return str(cfg.get("automation", {}).get("morning_wake_time", "07:30"))
    except Exception:
        return "07:30"


def wake_on_lan(mac_address: str) -> bool:
    mac = mac_address.replace(":", "-").replace("-", "")
    if len(mac) != 12:
        return False

    try:
        mac_bytes = bytes.fromhex(mac)
        magic_packet = b"\xff" * 6 + mac_bytes * 16

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic_packet, ("255.255.255.255", 9))
        sock.close()
        return True
    except Exception:
        return False


def is_computer_on() -> bool:
    try:
        result = _run_powershell("(Get-CimInstance Win32_ComputerSystem).Name", timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def _task_action_command(target: Path) -> str:
    # Task Scheduler is more reliable when it invokes cmd.exe itself instead of a .cmd directly.
    argument = f'/d /c ""{target}""'
    return (
        f"$action = New-ScheduledTaskAction -Execute $env:ComSpec "
        f"-Argument {_ps_quote(argument)} -WorkingDirectory {_ps_quote(REPO_ROOT)}"
    )


def create_scheduled_task(
    task_name: str = DEFAULT_TASK_NAME,
    script_path: str = "",
    *,
    wake_time: str | None = None,
) -> bool:
    target = Path(script_path) if script_path else MORNING_CMD_PATH
    try:
        _write_launcher_scripts()
        schedule_time = wake_time or _configured_wake_time()
        if not _is_hhmm(schedule_time):
            return False
        command = "\n".join(
            [
                _task_action_command(target),
                f"$trigger = New-ScheduledTaskTrigger -Daily -At {_ps_quote(schedule_time)}",
                "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun -StartWhenAvailable",
                f"Register-ScheduledTask -TaskName {_ps_quote(task_name)} -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null",
            ]
        )
        result = _run_powershell(command, timeout=30)
        return result.returncode == 0
    except Exception:
        return False


def setup_morning_wake(wake_time: str = "07:30") -> bool:
    clean_time = str(wake_time or "").strip()
    if not _is_hhmm(clean_time):
        return False
    if not create_scheduled_task(DEFAULT_TASK_NAME, "", wake_time=clean_time):
        return False
    return _update_wake_config(enabled=True, wake_time=clean_time)


def remove_scheduled_task(task_name: str = DEFAULT_TASK_NAME) -> bool:
    try:
        result = _run_powershell(
            "\n".join(
                [
                    f"$task = Get-ScheduledTask -TaskName {_ps_quote(task_name)} -ErrorAction SilentlyContinue",
                    "if ($task) { Unregister-ScheduledTask -TaskName $task.TaskName -Confirm:$false }",
                ]
            ),
            timeout=20,
        )
        ok = result.returncode == 0
        if ok and task_name == DEFAULT_TASK_NAME:
            _update_wake_config(enabled=False)
        return ok
    except Exception:
        return False


def parse_wake_timers_output(output: str) -> dict[str, Any]:
    text = (output or "").strip()
    lowered = text.lower()
    permission_markers = (
        "requiere privilegios",
        "privilegios de administrador",
        "access is denied",
        "acceso denegado",
        "administrator privileges",
    )
    if any(marker in lowered for marker in permission_markers):
        return {
            "raw": text,
            "available": False,
            "has_timers": False,
            "timers": [],
            "error": "Windows requiere privilegios para consultar temporizadores.",
        }
    no_timers_markers = (
        "there are no active wake timers",
        "no hay temporizadores",
        "no existen temporizadores",
    )
    has_timers = bool(text) and not any(marker in lowered for marker in no_timers_markers)
    timers: list[str] = []
    if has_timers:
        for line in text.splitlines():
            clean = line.strip()
            if clean:
                timers.append(clean)
    return {"raw": text, "available": bool(text), "has_timers": has_timers, "timers": timers, "error": ""}


def parse_wake_timer_policy_output(output: str) -> dict[str, Any]:
    text = output or ""
    ac = _parse_power_setting_index(text, "AC")
    dc = _parse_power_setting_index(text, "DC")
    return {
        "raw": text.strip(),
        "ac_enabled": _wake_policy_enabled(ac),
        "dc_enabled": _wake_policy_enabled(dc),
        "ac_index": ac,
        "dc_index": dc,
    }


def _parse_power_setting_index(text: str, power: str) -> int | None:
    match = re.search(rf"Current\s+{power}\s+Power\s+Setting\s+Index:\s+0x([0-9a-fA-F]+)", text)
    if match:
        return int(match.group(1), 16)
    spanish = "CA" if power == "AC" else "CC"
    match = re.search(rf"[Ii]ndice\s+de\s+configuraci[oó]n\s+de\s+energ[ií]a\s+{spanish}.*?:\s+0x([0-9a-fA-F]+)", text)
    if match:
        return int(match.group(1), 16)
    return None


def _wake_policy_enabled(value: int | None) -> bool | None:
    if value is None:
        return None
    return value > 0


def get_power_status() -> dict[str, str]:
    try:
        command = "\n".join(
            [
                "$b = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1",
                "if ($b) {",
                "  [PSCustomObject]@{Present='si'; Status=[string]$b.BatteryStatus; Charge=[string]$b.EstimatedChargeRemaining} | ConvertTo-Json -Compress",
                "} else {",
                "  [PSCustomObject]@{Present='no'; Status='sin bateria detectada'; Charge=''} | ConvertTo-Json -Compress",
                "}",
            ]
        )
        result = _run_powershell(command, timeout=10)
        raw = (result.stdout or "").strip()
        if result.returncode == 0 and raw:
            payload = json.loads(raw)
            return {
                "battery_present": str(payload.get("Present", "desconocido")),
                "battery_status": str(payload.get("Status", "desconocido")),
                "battery_charge": str(payload.get("Charge", "")),
            }
    except Exception:
        pass
    return {"battery_present": "desconocido", "battery_status": "desconocido", "battery_charge": ""}


def session_lock_state() -> str:
    """Best-effort: Windows no expone un estado universal simple para todos los escritorios."""
    try:
        command = "[bool](Get-Process LogonUI -ErrorAction SilentlyContinue)"
        result = _run_powershell(command, timeout=5)
        raw = (result.stdout or "").strip().lower()
        if result.returncode == 0:
            if raw == "true":
                return "bloqueada"
            if raw == "false":
                return "interactiva"
    except Exception:
        pass
    return "desconocida"


def get_energy_diagnostics() -> dict[str, Any]:
    status = get_resident_status()
    wake_timers = {"raw": "", "available": False, "has_timers": False, "timers": [], "error": "Sin datos."}
    timer_policy = {"raw": "", "ac_enabled": None, "dc_enabled": None, "ac_index": None, "dc_index": None}
    last_wake = "desconocido"
    try:
        result = _run_powershell("powercfg /waketimers", timeout=15)
        wake_timers = parse_wake_timers_output((result.stdout or result.stderr or "").strip())
    except Exception:
        pass
    try:
        result = _run_powershell("powercfg /query SCHEME_CURRENT SUB_SLEEP RTCWAKE", timeout=15)
        timer_policy = parse_wake_timer_policy_output((result.stdout or result.stderr or "").strip())
    except Exception:
        pass
    try:
        result = _run_powershell("powercfg /lastwake", timeout=15)
        raw = (result.stdout or result.stderr or "").strip()
        if raw:
            last_wake = raw
    except Exception:
        pass
    return {
        "resident": status,
        "wake_timers": wake_timers,
        "timer_policy": timer_policy,
        "last_wake": last_wake,
        "power": get_power_status(),
        "session": session_lock_state(),
        "safe_unlock_policy": "no_bypass",
    }


def schedule_wake_test(minutes: int = 2, task_name: str = "Viernes Wake Test") -> tuple[bool, str]:
    minutes = max(1, int(minutes or 2))
    target_time = datetime.now() + timedelta(minutes=minutes)
    try:
        _write_launcher_scripts()
        command = "\n".join(
            [
                _task_action_command(MORNING_CMD_PATH),
                f"$trigger = New-ScheduledTaskTrigger -Once -At {_ps_quote(target_time.strftime('%Y-%m-%d %H:%M'))}",
                "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun -StartWhenAvailable",
                f"Register-ScheduledTask -TaskName {_ps_quote(task_name)} -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null",
            ]
        )
        result = _run_powershell(command, timeout=30)
        if result.returncode == 0:
            return True, f"Prueba de despertar programada para {target_time.strftime('%H:%M')}."
        return False, (result.stderr or result.stdout or "No pude programar la prueba de despertar.").strip()
    except Exception as exc:
        return False, f"No pude programar la prueba de despertar: {exc}"


def set_startup_enabled(enabled: bool) -> bool:
    """Create or remove only the logon shortcut and verify the result."""
    try:
        if enabled:
            _write_launcher_scripts()
            command = "\n".join(
                [
                    "$folder = [Environment]::GetFolderPath('Startup')",
                    "$shortcutPath = Join-Path $folder 'Viernes.lnk'",
                    "$shell = New-Object -ComObject WScript.Shell",
                    "$shortcut = $shell.CreateShortcut($shortcutPath)",
                    "$shortcut.TargetPath = $env:ComSpec",
                    f"$shortcut.Arguments = {_ps_quote(f'/d /c \"\"{STARTUP_CMD_PATH}\"\"')}",
                    f"$shortcut.WorkingDirectory = {_ps_quote(REPO_ROOT)}",
                    "$shortcut.IconLocation = \"$env:SystemRoot\\System32\\shell32.dll,220\"",
                    "$shortcut.Save()",
                ]
            )
        else:
            command = "\n".join(
                [
                    "$folder = [Environment]::GetFolderPath('Startup')",
                    "$shortcutPath = Join-Path $folder 'Viernes.lnk'",
                    "if (Test-Path -LiteralPath $shortcutPath) { Remove-Item -LiteralPath $shortcutPath -Force }",
                ]
            )
        result = _run_powershell(command, timeout=30)
        if result.returncode != 0:
            return False
        status = get_resident_status()
        verified = status.get("startup") == "activo" if enabled else status.get("startup") != "activo"
        if verified:
            _update_wake_config(enabled=None, startup_enabled=enabled)
        return verified
    except Exception:
        return False


def repair_wake_configuration(wake_time: str | None = None) -> tuple[bool, str]:
    target_time = wake_time or _configured_wake_time()
    ok = setup_morning_wake(target_time)
    diagnostics = get_energy_diagnostics()
    status = diagnostics.get("resident", {})
    if ok:
        return True, (
            f"Despertar reparado a las {target_time}. "
            f"Tarea: {status.get('task', 'desconocida')}, proxima ejecucion: {status.get('next_run', 'desconocida')}."
        )
    return False, "No pude reparar la tarea de despertar. Revise permisos de Windows y ejecute la app como administrador si hace falta."


def send_wol_to_broadcast(mac: str) -> bool:
    return wake_on_lan(mac)


def install_resident_mode() -> tuple[bool, str]:
    wake_time = _configured_wake_time()
    startup_ok = set_startup_enabled(True)
    wake_ok = setup_morning_wake(wake_time)
    if startup_ok and wake_ok:
        return True, "Inicio de sesion y rutina matutina configurados y verificados."
    failed = []
    if not startup_ok:
        failed.append("acceso directo de inicio de sesion")
    if not wake_ok:
        failed.append("tarea de rutina matutina")
    return False, "Windows no confirmo: " + ", ".join(failed) + "."


def remove_resident_mode() -> tuple[bool, str]:
    startup_ok = set_startup_enabled(False)
    wake_ok = remove_scheduled_task(DEFAULT_TASK_NAME)
    status = get_resident_status()
    verified = startup_ok and wake_ok and status.get("startup") != "activo" and status.get("task") == "inexistente"
    if verified:
        _update_wake_config(enabled=False, startup_enabled=False)
        return True, "Se desactivo y verifico el inicio de sesion y la rutina matutina."
    return False, "Windows no confirmo que se quitaran el acceso directo y la tarea de rutina."


def get_resident_status() -> dict[str, str]:
    startup_enabled = "desconocido"
    task_status = "desconocido"
    wake_time = _configured_wake_time()
    next_run = "desconocido"
    action = "desconocida"
    last_result = "desconocido"
    last_result_hex = ""
    last_result_message = "sin ejecuciones registradas"
    wake_to_run = "desconocido"

    try:
        startup_folder = _run_powershell("[Environment]::GetFolderPath('Startup')", timeout=10)
        folder = (startup_folder.stdout or "").strip()
        if folder:
            shortcut = Path(folder) / "Viernes.lnk"
            startup_enabled = "activo" if shortcut.exists() else "inactivo"
    except Exception:
        pass

    try:
        command = "\n".join(
            [
                f"$t = Get-ScheduledTask -TaskName {_ps_quote(DEFAULT_TASK_NAME)} -ErrorAction SilentlyContinue",
                "if ($t) {",
                "  $info = $t | Get-ScheduledTaskInfo",
                "  [PSCustomObject]@{",
                "    State = [string]$t.State",
                "    NextRunTime = [string]$info.NextRunTime",
                "    LastTaskResult = [string]$info.LastTaskResult",
                "    LastRunTime = [string]$info.LastRunTime",
                "    Execute = [string]$t.Actions[0].Execute",
                "    Arguments = [string]$t.Actions[0].Arguments",
                "    WorkingDirectory = [string]$t.Actions[0].WorkingDirectory",
                "    WakeToRun = [string]$t.Settings.WakeToRun",
                "  } | ConvertTo-Json -Compress",
                "}",
            ]
        )
        result = _run_powershell(command, timeout=15)
        raw = (result.stdout or "").strip()
        if result.returncode != 0:
            task_status = "requiere permisos para verificar"
        elif raw:
            payload = json.loads(raw)
            task_status = str(payload.get("State", "desconocido")).lower()
            next_run = str(payload.get("NextRunTime", "") or "desconocido")
            last_result = str(payload.get("LastTaskResult", "") or "desconocido")
            try:
                result_code = int(last_result)
                last_result_hex = f"0x{result_code & 0xFFFFFFFF:08X}"
                last_result_message = _task_result_message(result_code)
                if result_code != 0 and str(payload.get("LastRunTime", "") or ""):
                    task_status = f"fallo ({last_result_hex})"
            except (TypeError, ValueError):
                last_result_message = "Resultado de la ultima ejecucion no interpretable."
            wake_value = str(payload.get("WakeToRun", "") or "").lower()
            wake_to_run = "activo" if wake_value == "true" else "inactivo" if wake_value == "false" else "desconocido"
            action = " ".join(
                part for part in [str(payload.get("Execute", "")), str(payload.get("Arguments", ""))] if part.strip()
            ).strip() or "desconocida"
        else:
            task_status = "inexistente"
    except Exception:
        pass

    return {
        "startup": startup_enabled,
        "task": task_status,
        "wake_time": wake_time,
        "next_run": next_run,
        "action": action,
        "last_result": last_result,
        "last_result_hex": last_result_hex,
        "last_result_message": last_result_message,
        "wake_to_run": wake_to_run,
        "limitations": "Solo intenta reactivar desde suspension compatible; no enciende un equipo apagado ni desbloquea Windows.",
    }


def _task_result_message(code: int) -> str:
    if code == 0:
        return "La ultima ejecucion termino correctamente."
    messages = {
        0x800710E0: "Windows rechazo la solicitud de ejecucion de la tarea.",
        0x8004131F: "La tarea aun no tiene una ejecucion registrada.",
        0x41301: "La tarea se esta ejecutando.",
    }
    return messages.get(code & 0xFFFFFFFF, "La tarea termino con un codigo de error de Windows.")
