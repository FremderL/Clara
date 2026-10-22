$ErrorActionPreference = 'Stop'

$AppExe = Join-Path $PSScriptRoot 'Clara.exe'
$AppScript = Join-Path $PSScriptRoot 'app.py'
if (Test-Path $AppExe) {
    # Compiled onedir distribution: the scheduled task invokes only this executable.
    $TaskExe = $AppExe
    $BriefArgs = '--briefing'
    $ReminderArgs = '--check-reminders'
} else {
    if (-not (Test-Path $AppScript)) { throw "No encuentro app.py ni Clara.exe en $PSScriptRoot" }
    try {
        $PythonW = (& py -3 -c 'import sys; from pathlib import Path; print(Path(sys.executable).with_name("pythonw.exe"))' 2>$null | Select-Object -Last 1).Trim()
    } catch {
        $PythonW = $null
    }
    if (-not $PythonW -or -not (Test-Path $PythonW)) {
        $Command = Get-Command pythonw.exe -ErrorAction SilentlyContinue
        if ($Command) { $PythonW = $Command.Source }
    }
    if (-not $PythonW -or -not (Test-Path $PythonW)) {
        throw 'No pude encontrar pythonw.exe. Instala Python 3 y asegúrate de que el comando py esté disponible.'
    }
    $TaskExe = $PythonW
    $BriefArgs = '"{0}" --briefing' -f $AppScript
    $ReminderArgs = '"{0}" --check-reminders' -f $AppScript
}

$Identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Principal = New-ScheduledTaskPrincipal -UserId $Identity -LogonType Interactive -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew

$BriefAction = New-ScheduledTaskAction -Execute $TaskExe -Argument $BriefArgs -WorkingDirectory $PSScriptRoot
$MorningTime = '07:00'
$SettingsPath = Join-Path $env:USERPROFILE 'AsistentePersonal\settings.json'
if (Test-Path $SettingsPath) {
    try {
        $SavedSettings = Get-Content -Raw -Path $SettingsPath | ConvertFrom-Json
        if ($SavedSettings.morning_time -match '^([01][0-9]|2[0-3]):([0-5][0-9])$') { $MorningTime = $SavedSettings.morning_time }
    } catch { Write-Host 'No pude leer settings.json; usaré el horario predeterminado de 07:00.' -ForegroundColor Yellow }
}
$Hour, $Minute = $MorningTime.Split(':')
$NextBriefing = (Get-Date).Date.AddHours([int]$Hour).AddMinutes([int]$Minute)
while ($NextBriefing -le (Get-Date) -or $NextBriefing.DayOfWeek -in @([System.DayOfWeek]::Saturday, [System.DayOfWeek]::Sunday)) {
    $NextBriefing = $NextBriefing.AddDays(1)
    while ($NextBriefing.DayOfWeek -in @([System.DayOfWeek]::Saturday, [System.DayOfWeek]::Sunday)) { $NextBriefing = $NextBriefing.AddDays(1) }
}
$BriefTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $NextBriefing
Register-ScheduledTask -TaskName 'AsistentePersonal-Manana' -Action $BriefAction -Trigger $BriefTrigger -Principal $Principal -Settings $Settings -Description 'Abre el resumen matutino del asistente de lunes a viernes a las 7:00.' -Force | Out-Null

$ReminderAction = New-ScheduledTaskAction -Execute $TaskExe -Argument $ReminderArgs -WorkingDirectory $PSScriptRoot
# Repetición por un año (límite práctico del disparador repetitivo); vuelve a ejecutar este instalador al renovarlo.
$ReminderTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 365)
Register-ScheduledTask -TaskName 'AsistentePersonal-Recordatorios' -Action $ReminderAction -Trigger $ReminderTrigger -Principal $Principal -Settings $Settings -Description 'Comprueba recordatorios de tareas cada cinco minutos mientras el usuario está conectado.' -Force | Out-Null

Write-Host 'Rutinas programadas para este usuario:' -ForegroundColor Green
Write-Host "- Resumen matutino: lunes a viernes a las $MorningTime."
Write-Host '- Recordatorios: comprobación cada cinco minutos (vuelve a ejecutar este instalador al cabo de un año).'
Write-Host 'La aplicación puede mostrar ventanas emergentes; el usuario debe tener una sesión iniciada.'
