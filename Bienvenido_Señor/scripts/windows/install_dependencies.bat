@echo off
echo ========================================
echo   INSTALAR DEPEENCIAS DE VIERNES
echo ========================================
echo.
echo [1/4] Instalando speechrecognition...
python -m pip install speechrecognition --quiet

echo [2/4] Instalando pyaudio...
python -m pip install pyaudio --quiet

echo [3/4] Instalando edge-tts...
python -m pip install edge-tts --quiet

echo [4/4] Verificando modulos...
python -c "import speech_recognition; import pyaudio; print('OK')" 2>nul || echo " algunos modulos pueden fallar"

echo.
echo ========================================
echo   INSTALACION COMPLETA
echo ========================================
echo.
echo Ejecuta: python viernes.py
pause