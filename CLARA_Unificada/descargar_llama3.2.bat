@echo off
chcp 65001 >nul
cd /d "%~dp0"
title CLARA-V · Descarga opcional de llama3.2 y modulo Python ollama
echo ============================================================================
echo  CLARA-V (Clara Viernes) · Modelo conversacional llama3.2 + modulo ollama
echo ============================================================================
echo.
echo Se instalaran/descargaran los siguientes recursos oficiales bajo tu autorizacion:
echo.
echo  1. Paquete Python "ollama" (conexion directa Python -> Ollama local)
echo     Fuente oficial: https://pypi.org/project/ollama/
echo     Licencia: MIT  ^|  Tamano aprox.: ~25 KB
echo.
echo  2. Modelo conversacional "llama3.2" (el modelo usado en Viernes)
echo     Fuente oficial: https://ollama.com/library/llama3.2
echo     Licencia: Meta Llama 3.2 Community License  ^|  Tamano aprox.: ~2.0 GB
echo.
choice /c SN /m "¿Autorizas instalar el modulo Python ollama y descargar llama3.2 ahora (S/N)?"
if errorlevel 2 (
    echo Operacion cancelada por el usuario. No se realizo ninguna descarga.
    pause
    exit /b 0
)

echo.
echo [1/2] Instalando modulo oficial de Python "ollama"...
py -3 -m pip install "ollama>=0.4.0"

echo.
echo [2/2] Iniciando servidor local de Ollama y descargando modelo "llama3.2"...
where ollama >nul 2>nul
if %errorlevel% equ 0 (
    start "" /B ollama serve >nul 2>nul
    timeout /t 2 /nobreak >nul
    ollama pull llama3.2
) else if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    start "" /B "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve >nul 2>nul
    timeout /t 2 /nobreak >nul
    "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" pull llama3.2
) else (
    echo [AVISO] No se encontro ollama.exe instalado en la ruta predeterminada de Windows.
    echo Instala primero Ollama desde https://ollama.com/download y vuelve a ejecutar este archivo.
    pause
    exit /b 1
)

echo.
echo [LISTO] El modulo Python "ollama" y el modelo "llama3.2" quedaron listos para CLARA-V.
pause
