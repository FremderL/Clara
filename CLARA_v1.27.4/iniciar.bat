@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo No se encontro Python Launcher ^(py^).
  echo Para esta version de codigo fuente, instala Python 3.10 o posterior con Tcl/Tk desde python.org.
  echo Si solo quieres ejecutar la app, pide el paquete portable EXE generado en Windows.
  pause
  exit /b 1
)
py -3 app.py
if errorlevel 1 (
  echo.
  echo Clara no pudo iniciarse. Revisa que Python 3 incluya Tcl/Tk y consulta README.md.
  pause
  exit /b 1
)
