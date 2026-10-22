$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $ScriptRoot "..\..")).Path
$StartupFolder = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupFolder "Viernes.lnk"
$StartupCmd = Join-Path $ProjectRoot "viernes_start.cmd"
$MorningCmd = Join-Path $ProjectRoot "viernes_morning.cmd"
$TaskName = "Viernes Morning Wake"

if (Test-Path $ShortcutPath) {
    Remove-Item -LiteralPath $ShortcutPath -Force
}

if (Test-Path $StartupCmd) {
    Remove-Item -LiteralPath $StartupCmd -Force
}

if (Test-Path $MorningCmd) {
    Remove-Item -LiteralPath $MorningCmd -Force
}

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Task) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false | Out-Null
}

Write-Host "Se elimino el inicio de sesion y la tarea de rutina matutina de Viernes."
