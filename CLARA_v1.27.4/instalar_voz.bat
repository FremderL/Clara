@echo off
py -3 -m pip install vosk sounddevice pyttsx3
if errorlevel 1 (
  echo.
  echo La instalacion opcional de voz fallo. La app seguira funcionando con texto.
  pause
  exit /b 1
)
echo Paquetes de voz instalados. Falta descargar y extraer el modelo espanol segun README.md.
pause
