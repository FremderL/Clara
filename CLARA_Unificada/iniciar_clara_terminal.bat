@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title CLARA-V (Clara Viernes) - Lanzador de terminal

echo ==============================================================
echo  CLARA-V (Clara Viernes) v2.0.0 - Asistente Personal Local-First
echo  Inicio seguro: sin descargas ni instalaciones automaticas
echo ==============================================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] No se encontro el lanzador de Python ^(py^).
  echo Instala Python 3.10+ desde https://www.python.org/downloads/windows/
  pause
  exit /b 1
)

for /f "delims=" %%V in ('py -3 --version 2^>^&1') do set "PY_VER=%%V"
echo [1/4] Python detectado: %PY_VER%
py -3 -c "import sys, tkinter; raise SystemExit(0 if sys.version_info >= (3, 10) else 2)" >nul 2>nul
if errorlevel 2 (
  echo [ERROR] Se requiere Python 3.10 o superior.
  pause
  exit /b 1
)
if errorlevel 1 (
  echo [ERROR] Falta Tkinter ^(Tcl/Tk^) en esta instalacion de Python.
  pause
  exit /b 1
)

echo [2/4] Comprobando estado de Ollama local ^(opcional, solo lectura^)...
powershell -NoProfile -Command "try { $null = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>nul
if errorlevel 1 (
  echo       [OPCIONAL] Ollama no responde en 127.0.0.1:11434.
  echo       Agenda, "¿que sigue?", tareas, clases, rutinas, noticias y clima funcionan sin Ollama.
) else (
  echo       [OK] Servidor local de Ollama activo en 127.0.0.1:11434.
)

echo [3/4] Comprobando modulos de voz locales ^(opcional, sin encender microfono^)...
py -3 -c "import importlib.util, sys; raise SystemExit(0 if importlib.util.find_spec('pyttsx3') else 1)" >nul 2>nul
if errorlevel 1 (
  echo       [OPCIONAL] pyttsx3 no instalado. Las respuestas escritas funcionan siempre.
  echo       Si deseas instalar voz local manualmente, ejecuta instalar_voz.bat.
) else (
  echo       [OK] pyttsx3 disponible para respuestas habladas.
)

echo [4/4] Abriendo la ventana principal de CLARA Unificada...
echo.
py -3 app.py
if errorlevel 1 (
  echo.
  echo [ERROR] CLARA se cerro con un error.
  pause
  exit /b 1
)
exit /b 0
