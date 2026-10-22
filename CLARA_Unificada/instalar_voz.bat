@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ======================================================================
echo  Instalacion manual de paquetes opcionales de voz para CLARA Unificada
echo  ^(Descargas automaticas desactivadas por defecto^)
echo ======================================================================
echo.
echo Antes de descargar, revisa la informacion oficial de los recursos:
echo.
echo  1. Recurso:        pyttsx3 ^(sintesis de voz local SAPI5^)
echo     Fuente oficial: https://pypi.org/project/pyttsx3/
echo     Version:        ^>=2.90
echo     Tamano aprox.:  ~50 KB ^(mas comtypes/pywin32 en Windows^)
echo     Licencia:       MPL-2.0 / MIT
echo.
echo  2. Recurso:        vosk ^(reconocimiento de voz offline^)
echo     Fuente oficial: https://pypi.org/project/vosk/
echo     Version:        ^>=0.3.45
echo     Tamano aprox.:  ~15 MB
echo     Licencia:       Apache-2.0
echo.
echo  3. Recurso:        sounddevice ^(captura local de microfono PortAudio^)
echo     Fuente oficial: https://pypi.org/project/sounddevice/
echo     Version:        ^>=0.4.6
echo     Tamano aprox.:  ~1.5 MB
echo     Licencia:       MIT
echo.
echo  Nota sobre el modelo de espanol Vosk ^(no se descarga automaticamente aqui^):
echo     Recurso:        vosk-model-small-es-0.42.zip
echo     Fuente oficial: https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip
echo     Version:        0.42  ^|  Tamano: 39 MB  ^|  Licencia: Apache-2.0
echo     Extraccion manual en: models\vosk-model-small-es-0.42
echo.
choice /c SN /m "¿Autorizas descargar e instalar desde PyPI oficial (vosk, sounddevice, pyttsx3)?"
if errorlevel 2 (
  echo Operacion cancelada por el usuario. No se descargo ni instalo nada.
  pause
  exit /b 0
)

py -3 -m pip install "vosk>=0.3.45" "sounddevice>=0.4.6" "pyttsx3>=2.90"
if errorlevel 1 (
  echo.
  echo La instalacion opcional de voz fallo. Clara seguira funcionando por texto.
  pause
  exit /b 1
)
echo.
echo Paquetes de voz instalados. Si deseas dictado Push-to-Talk, descarga manualmente
echo vosk-model-small-es-0.42.zip desde https://alphacephei.com/vosk/models/ y extraelo en:
echo   models\vosk-model-small-es-0.42
pause
exit /b 0
