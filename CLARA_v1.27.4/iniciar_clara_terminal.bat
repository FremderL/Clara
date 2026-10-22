@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title CLARA - Inicio desde terminal

echo ==============================================
echo  CLARA - Centro Local de Asistencia, Rutinas y Agenda
echo  Preparando Ollama y la aplicación...
echo ==============================================

echo [1/4] Buscando Ollama...
set "OLLAMA_EXE="
for /f "delims=" %%I in ('where ollama.exe 2^>nul') do if not defined OLLAMA_EXE set "OLLAMA_EXE=%%I"
if not defined OLLAMA_EXE if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"

if not defined OLLAMA_EXE (
  echo AVISO: No encontre ollama.exe en PATH ni en la carpeta de instalacion habitual.
  echo Instala Ollama o abre su servicio manualmente. Clara se iniciara sin chat local.
  goto :launch_clara
)

echo Ollama encontrado: "%OLLAMA_EXE%"
echo [2/4] Comprobando el servicio local en 127.0.0.1:11434...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ok=$false; for($i=0;$i -lt 20;$i++){ try{$null=Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2; $ok=$true; break}catch{Start-Sleep -Seconds 1} }; if($ok){exit 0}else{exit 1}"
if not errorlevel 1 goto :check_model

echo El servicio local no respondio. Intentando iniciar `ollama serve`...
start "Ollama local" /min "%OLLAMA_EXE%" serve
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ok=$false; for($i=0;$i -lt 25;$i++){ try{$null=Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2; $ok=$true; break}catch{Start-Sleep -Seconds 1} }; if($ok){exit 0}else{exit 1}"
if errorlevel 1 (
  echo AVISO: Ollama no respondio en 25 segundos. Clara se abrira, pero el chat local puede estar desconectado.
  goto :launch_clara
)

:check_model
echo [3/4] Revisando modelos instalados...
"%OLLAMA_EXE%" list
if errorlevel 1 (
  echo AVISO: No pude enumerar los modelos. Clara aun se iniciara.
  goto :launch_clara
)
"%OLLAMA_EXE%" list | findstr /i "qwen3:4b" >nul
if not errorlevel 1 goto :check_tts

echo No detecte un modelo recomendado qwen3:4b.
echo Descargarlo requiere internet y aproximadamente 2.5 GB de espacio.
choice /c SN /n /m "¿Descargar ahora? S=Si, N=No: "
if errorlevel 2 goto :check_tts
"%OLLAMA_EXE%" pull qwen3:4b
if errorlevel 1 echo AVISO: No se pudo descargar el modelo. Clara se iniciara sin el modelo recomendado.

:check_tts
echo [4/4] Revisando voz de salida opcional...
py -3 -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('pyttsx3') else 1)" >nul 2>nul
if not errorlevel 1 goto :launch_clara
echo pyttsx3 no esta instalado; Clara seguira respondiendo por texto.
choice /c SN /n /m "¿Instalar ahora la voz opcional? Requiere internet. S=Si, N=No: "
if errorlevel 2 goto :launch_clara
py -3 -m pip install pyttsx3
if errorlevel 1 echo AVISO: No se instalo pyttsx3. Clara seguira respondiendo por texto.

:launch_clara
echo.
echo Iniciando Clara. La ventana grafica se abrira; esta terminal queda disponible para mensajes de inicio.
where py >nul 2>nul
if not errorlevel 1 (
  py -3 app.py
  goto :finished
)
if exist "dist\Clara\Clara.exe" (
  echo Python no esta disponible; iniciando el ejecutable portable existente.
  "dist\Clara\Clara.exe"
  goto :finished
)
echo ERROR: No se encontro Python 3 ni dist\Clara\Clara.exe.
echo Instala Python 3.10 o posterior con Tcl/Tk, o construye el paquete en Windows.
exit /b 1

:finished
echo.
echo Clara se cerro. Puedes cerrar esta terminal.
pause
