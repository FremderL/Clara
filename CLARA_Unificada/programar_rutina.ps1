$ErrorActionPreference = 'Stop'
$base = Split-Path -Parent $MyInvocation.MyCommand.Path
$exePath = Join-Path $base 'Clara.exe'
$appPath = Join-Path $base 'app.py'
$settingsPath = Join-Path $env:USERPROFILE 'AsistentePersonal\settings.json'
$morningTime = '07:00'

if (Test-Path $settingsPath) {
  try {
    $cfg = Get-Content $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($cfg.morning_time) { $morningTime = [string]$cfg.morning_time }
  } catch {
    Write-Host 'No se pudo leer settings.json; usare las 07:00 por defecto.' -ForegroundColor Yellow
  }
}

try {
  $parsed = [datetime]::ParseExact($morningTime, 'HH:mm', $null)
} catch {
  throw "La hora '$morningTime' no es valida. Abre Preferencias en la aplicacion y guardala como HH:MM."
}

if (Test-Path $exePath) {
  $runner = $exePath
  $morningArguments = '--briefing'
  $reminderArguments = '--check-reminders'
} else {
  $pythonCmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
  if (-not $pythonCmd) { $pythonCmd = Get-Command py.exe -ErrorAction SilentlyContinue }
  if (-not $pythonCmd) { throw 'No se encontro Clara.exe ni Python para ejecutar el asistente.' }
  $runner = $pythonCmd.Source
  $prefix = if ($runner.ToLower().EndsWith('py.exe')) { '-3 ' } else { '' }
  $morningArguments = "$prefix`"$appPath`" --briefing"
  $reminderArguments = "$prefix`"$appPath`" --check-reminders"
}

$morningAction = New-ScheduledTaskAction -Execute $runner -Argument $morningArguments -WorkingDirectory $base
$morningTrigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At $parsed
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'AsistentePersonal-Manana' -Action $morningAction -Trigger $morningTrigger -Settings $settings -Description 'Resumen matutino de clases, tareas, clima y noticias (requiere sesion iniciada)' -Force | Out-Null

$reminderAction = New-ScheduledTaskAction -Execute $runner -Argument $reminderArguments -WorkingDirectory $base
$once = (Get-Date).Date.AddMinutes(1)
$reminderTrigger = New-ScheduledTaskTrigger -Once -At $once -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
Register-ScheduledTask -TaskName 'AsistentePersonal-Recordatorios' -Action $reminderAction -Trigger $reminderTrigger -Settings $settings -Description 'Revisa tareas y clases proximas cada 5 minutos mientras haya sesion iniciada' -Force | Out-Null

Write-Host "Listo: rutina de lunes a viernes programada a las $morningTime y avisos cada 5 minutos (dependen de Windows y de una sesion iniciada)." -ForegroundColor Green
