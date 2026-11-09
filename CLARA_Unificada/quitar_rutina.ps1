$ErrorActionPreference = 'Continue'
Unregister-ScheduledTask -TaskName 'AsistentePersonal-Manana' -Confirm:$false -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName 'AsistentePersonal-Recordatorios' -Confirm:$false -ErrorAction SilentlyContinue
Write-Host 'Se quitaron las tareas programadas. Tus clases y pendientes guardados no se borraron.' -ForegroundColor Green
