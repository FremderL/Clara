@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul
cd /d "%~dp0"
title CLARA-V · Descarga con reanudacion automatica de llama3.2 + modulo ollama
echo ============================================================================
echo  CLARA-V (Clara Viernes) · Modelo conversacional llama3.2 + modulo ollama
echo ============================================================================
echo.
echo Se instalaran/descargaran los siguientes recursos oficiales bajo tu autorizacion:
echo.
echo  1. Paquete Python "ollama" (conexion directa Python -^> Ollama local)
echo     Fuente oficial: https://pypi.org/project/ollama/
echo     Licencia: MIT  ^|  Tamano aprox.: ~25 KB
echo.
echo  2. Modelo conversacional "llama3.2" (el modelo usado en Viernes)
echo     Fuente oficial: https://ollama.com/library/llama3.2
echo     Licencia: Meta Llama 3.2 Community License  ^|  Tamano aprox.: ~2.0 GB
echo     Modo anti-timeout TLS: GODEBUG=http2client=0 + reanudacion automatica
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
echo [2/2] Configurando modo anti-timeout TLS (HTTP/1.1) para Cloudflare R2...
set "GODEBUG=http2client=0"
set "OLLAMA_NOPRUNE=1"

set "OLLAMA_EXE="
where ollama >nul 2>nul
if %errorlevel% equ 0 (
    set "OLLAMA_EXE=ollama"
) else if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
)

if "%OLLAMA_EXE%"=="" (
    echo [AVISO] No se encontro ollama.exe instalado en la ruta predeterminada de Windows.
    echo Instala primero Ollama desde https://ollama.com/download y vuelve a ejecutar este archivo.
    pause
    exit /b 1
)

REM Reiniciar el servidor local de Ollama con GODEBUG=http2client=0 para evitar TLS handshake timeout en Cloudflare R2
taskkill /F /IM ollama.exe >nul 2>nul
taskkill /F /IM "ollama app.exe" >nul 2>nul
timeout /t 1 /nobreak >nul
start "" /B "%OLLAMA_EXE%" serve >nul 2>nul
timeout /t 2 /nobreak >nul

echo.
echo Descargando "llama3.2" con reanudacion automatica si Cloudflare R2 corta la conexion...
for /L %%i in (1,1,15) do (
    echo.
    echo --- Intento %%i de 15 ^(el progreso descargado se conserva automaticamente^) ---
    "%OLLAMA_EXE%" pull llama3.2
    if !errorlevel! equ 0 (
        echo.
        echo ============================================================================
        echo  [LISTO] El modulo Python "ollama" y el modelo "llama3.2" quedaron listos.
        echo  Abre CLARA-V y veras "llama3.2" activo automaticamente.
        echo ============================================================================
        pause
        exit /b 0
    )
    echo [AVISO] Corte temporal de red/TLS con Cloudflare R2. Reanudando desde donde se quedo en 3 segundos...
    timeout /t 3 /nobreak >nul
)

echo.
echo [AVISO] Si tu proveedor de internet sigue bloqueando el archivo de 2.0 GB de Cloudflare R2,
echo puedes probar la version ligera de Llama 3.2 ^(1.3 GB^) ejecutando:
echo    ollama pull llama3.2:1b
pause
exit /b 1
