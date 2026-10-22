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
echo Prueba manual de voz de salida. No usa el microfono ni internet.
echo Si se oye la frase, el motor y el dispositivo de audio pueden hablar.
echo.
py -3 diagnosticar_voz.py
set "RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %RESULT%
