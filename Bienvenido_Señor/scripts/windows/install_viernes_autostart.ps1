$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptRoot "..\..")).Path
$ConfigPath = Join-Path $ProjectRoot "viernes_config.json"
$PythonExe = Get-Command py -ErrorAction SilentlyContinue
if (-not $PythonExe) {
    throw "No encontre el lanzador 'py'. Instala Python y asegurate de que 'py' funcione en PowerShell."
}

$Config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$WakeTime = "07:30"
if ($Config.automation -and $Config.automation.morning_wake_time) {
    $WakeTime = [string]$Config.automation.morning_wake_time
}

$StartupFolder = [Environment]::GetFolderPath("Startup")
$StartupCmd = Join-Path $ProjectRoot "viernes_start.cmd"
$MorningCmd = Join-Path $ProjectRoot "viernes_morning.cmd"
$ShortcutPath = Join-Path $StartupFolder "Viernes.lnk"
$TaskName = "Viernes Morning Wake"

@"
@echo off
setlocal
pushd "%~dp0" || exit /b 1
py "%~dp0viernes.py" --mode gui
popd
"@ | Set-Content -LiteralPath $StartupCmd -Encoding ASCII

@"
@echo off
setlocal
pushd "%~dp0" || exit /b 1
py "%~dp0viernes.py" --mode morning
popd
"@ | Set-Content -LiteralPath $MorningCmd -Encoding ASCII

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $env:ComSpec
$Shortcut.Arguments = "/d /c `"`"$StartupCmd`"`""
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,220"
$Shortcut.Save()

$Action = New-ScheduledTaskAction -Execute $env:ComSpec -Argument "/d /c `"`"$MorningCmd`"`"" -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At $WakeTime
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -WakeToRun

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null

Write-Host "Viernes configurado."
Write-Host "Autoarranque GUI: $ShortcutPath"
Write-Host "Rutina matutina: $TaskName a las $WakeTime"
Write-Host "Importante: la tarea solo puede intentar reactivar una suspension compatible. No enciende un equipo apagado ni desbloquea Windows."
