@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo No se encontro el lanzador de Python ^(py^).
  echo Instala Python 3.10 o posterior con Tcl/Tk desde https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
py -3 -c "import sys, tkinter; raise SystemExit(0 if sys.version_info >= (3, 10) else 2)" >nul 2>nul
if errorlevel 2 (
  echo Se requiere Python 3.10 o posterior.
  py -3 --version
  pause
  exit /b 1
)
if errorlevel 1 (
  echo Python no incluye Tkinter ^(Tcl/Tk^). Repara la instalacion de Python y marca Tcl/Tk and IDLE.
  pause
  exit /b 1
)
rem Inicio sencillo y directo: no realiza descargas, instalaciones silenciosas ni elevacion.
py -3 app.py
if errorlevel 1 (
  echo.
  echo Clara se cerro con un error. Revisa el mensaje anterior o ejecuta probar_clara.bat.
  pause
)
