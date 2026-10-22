@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0programar_rutina.ps1"
if errorlevel 1 (
  echo.
  echo No se pudo programar. Revisa que Python y el Programador de tareas de Windows esten disponibles.
  pause
) else (
  echo.
  echo Rutinas configuradas correctamente ^(requieren sesion de Windows iniciada^).
  pause
)
