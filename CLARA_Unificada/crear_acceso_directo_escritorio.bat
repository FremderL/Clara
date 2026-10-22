@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ================================================================
echo   CLARA-V (Clara Viernes) · Acceso directo en el Escritorio
echo ================================================================
echo.
echo Carpeta actual de CLARA-V:
echo   %~dp0
echo.
echo Se creará el acceso directo "CLARA-V (Clara Viernes).lnk" en tu
echo Escritorio apuntando a:
echo   %~dp0iniciar.bat
echo.
set /p CONFIRM="¿Deseas crear el acceso directo en el Escritorio? (S/N): "
if /I not "%CONFIRM%"=="S" (
    echo Operación cancelada por el usuario.
    pause
    exit /b 0
)

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desktop = [Environment]::GetFolderPath('Desktop'); $lnk = $ws.CreateShortcut((Join-Path $desktop 'CLARA-V (Clara Viernes).lnk')); $lnk.TargetPath = Join-Path '%~dp0' 'iniciar.bat'; $lnk.WorkingDirectory = '%~dp0'; $lnk.Description = 'Iniciar CLARA-V (Clara Viernes) · Asistente local-first'; $lnk.Save(); Write-Host 'Acceso directo creado en:' (Join-Path $desktop 'CLARA-V (Clara Viernes).lnk')"

echo.
pause
