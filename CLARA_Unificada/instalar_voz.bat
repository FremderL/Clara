@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ======================================================================
echo  Instalacion manual de paquetes opcionales de voz para CLARA-V
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
echo  4. Modelo local de espanol para el microfono Vosk:
echo     Recurso:        vosk-model-small-es-0.42.zip
echo     Fuente oficial: https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip
echo     Version:        0.42  ^|  Tamano: 39 MB  ^|  Licencia: Apache-2.0
echo     Destino local:  %~dp0models\vosk-model-small-es-0.42
echo.
choice /c SN /m "¿Autorizas instalar los paquetes de voz y que este instalador cree la carpeta 'models' e instale vosk-model-small-es-0.42?"
if errorlevel 2 (
  echo Operacion cancelada por el usuario. No se descargo ni instalo nada.
  pause
  exit /b 0
)

py -3 -m pip install "vosk>=0.3.45" "sounddevice>=0.4.6" "pyttsx3>=2.90"
if errorlevel 1 (
  echo.
  echo La instalacion opcional de paquetes de voz fallo. Clara seguira funcionando por texto.
  pause
  exit /b 1
)

if exist "%~dp0models\vosk-model-small-es-0.42" (
  echo.
  echo [OK] El modelo vosk-model-small-es-0.42 ya existe en models\vosk-model-small-es-0.42.
) else (
  echo.
  echo Creando carpeta 'models' y descargando/extrayendo vosk-model-small-es-0.42 ^(39 MB^)...
  py -3 -c "import pathlib, urllib.request, zipfile; root = pathlib.Path('models'); root.mkdir(parents=True, exist_ok=True); zpath = root / 'vosk-model-small-es-0.42.zip'; req = urllib.request.Request('https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip', headers={'User-Agent':'CLARA-V/2.0'}); resp = urllib.request.urlopen(req, timeout=120); zpath.write_bytes(resp.read()); resp.close(); zf = zipfile.ZipFile(zpath, 'r'); zf.extractall(root); zf.close(); zpath.unlink(missing_ok=True); print('[OK] Modelo extraido en:', (root / 'vosk-model-small-es-0.42').resolve())"
  if errorlevel 1 (
    echo [AVISO] No se pudo completar la descarga del modelo Vosk. Puedes instalarlo tambien desde CLARA-V en Diagnostico de voz.
  )
)

echo.
echo Listo: voz hablada ^(TTS^) y dictado Push-to-Talk ^(Vosk^) configurados en CLARA-V.
pause
exit /b 0
