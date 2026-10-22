@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: Instala Python 3.10 o posterior con el lanzador py.
  pause
  exit /b 1
)
echo Comprobando sintaxis...
py -3 -m py_compile app.py tests\test_app_helpers.py
if errorlevel 1 goto :fail
echo Ejecutando pruebas unitarias...
py -3 -m unittest discover -s tests -v
if errorlevel 1 goto :fail
echo.
echo Correcto: sintaxis y pruebas unitarias pasaron.
echo Esto no sustituye la prueba de la interfaz en Windows.
pause
exit /b 0
:fail
echo.
echo ERROR: una comprobacion fallo.
pause
exit /b 1
