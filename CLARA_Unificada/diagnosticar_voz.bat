@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo No se encontro el lanzador de Python ^(py^).
  echo Instala Python 3.10 o posterior con Tcl/Tk desde python.org.
  pause
  exit /b 1
)
echo Prueba manual local de voz. No usa el microfono ni internet.
echo.
py -3 diagnosticar_voz.py
set "RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %RESULT%
