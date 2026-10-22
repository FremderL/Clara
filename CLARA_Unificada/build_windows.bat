@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo ==============================================================
echo  Constructor opcional del paquete portable de CLARA Unificada
echo  Requiere Windows 10/11 y Python 3.10+ con Tkinter
echo ==============================================================
echo.
echo Recursos de compilacion incluidos en requirements-build.txt ^(fuente oficial PyPI, Version, Tamano y Licencia^):
echo   - pyinstaller==6.19.0 ^(GPLv2 con excepcion de bootloader, ~15 MB^)
echo   - pyttsx3==2.99       ^(MPL-2.0 / MIT, ~50 KB^)
echo   - winotify==1.1.0     ^(MIT, ~25 KB^)
echo   - pystray==0.19.5     ^(LGPL-3.0, ~100 KB^)
echo   - Pillow==12.2.0      ^(HPND, ~3.5 MB^)
echo.
choice /c SN /m "¿Confirmas instalar dependencias de compilacion desde PyPI y construir el paquete?"
if errorlevel 2 (
  echo Cancelado por el usuario. Puedes usar CLARA directamente con iniciar.bat sin compilar.
  pause
  exit /b 0
)

where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: No se encontro el lanzador de Python ^(py^).
  pause
  exit /b 1
)

echo [1/5] Instalando dependencias de compilacion...
py -3 -m pip install -r requirements-build.txt
if errorlevel 1 goto :fail

echo [2/5] Comprobando sintaxis y pruebas unitarias...
py -3 -m py_compile app.py diagnosticar_voz.py tests\test_unified_clara.py
if errorlevel 1 goto :fail
py -3 -m unittest discover -s tests -p "test_*.py" -v
if errorlevel 1 goto :fail

echo [3/5] Construyendo carpeta portable con PyInstaller...
if exist build rmdir /s /q build
if exist dist\Clara rmdir /s /q dist\Clara
py -3 -m PyInstaller --noconfirm --clean --windowed --onedir --name Clara --hidden-import pyttsx3 --hidden-import pyttsx3.drivers.sapi5 --hidden-import winotify --hidden-import pystray --hidden-import PIL --collect-all pyttsx3 --collect-all comtypes --collect-all winotify --collect-all pystray --collect-all PIL app.py
if errorlevel 1 goto :fail

echo [4/5] Copiando instrucciones y utilidades...
copy /Y README.md dist\Clara\README.md >nul
copy /Y Pruebas_aceptacion_Windows_Unificada.md dist\Clara\Pruebas_aceptacion_Windows_Unificada.md >nul
copy /Y diagnosticar_voz.bat dist\Clara\diagnosticar_voz.bat >nul
copy /Y diagnosticar_voz.py dist\Clara\diagnosticar_voz.py >nul
for %%F in (programar_rutina.bat programar_rutina.ps1 quitar_rutina.bat quitar_rutina.ps1) do if exist "%%F" copy /Y "%%F" dist\Clara\ >nul
if not exist dist\Clara\Clara.exe (
  echo ERROR: PyInstaller no produjo dist\Clara\Clara.exe
  goto :fail
)

echo [5/5] Creando ZIP portable...
if not exist dist mkdir dist
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\Clara\*' -DestinationPath 'dist\CLARA-Unificada-v2.0.0-Windows-portable.zip' -Force"
if errorlevel 1 goto :fail

echo.
echo LISTO:
echo   Carpeta ejecutable: dist\Clara\Clara.exe
echo   ZIP portable:       dist\CLARA-Unificada-v2.0.0-Windows-portable.zip
pause
exit /b 0

:fail
echo.
echo ERROR: Fallo el proceso. Revisa el error anterior.
pause
exit /b 1
