@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ==============================================
echo  Constructor del paquete portable de Clara
 echo Requiere Windows 10/11 y Python 3 con Tkinter
 echo ==============================================
where py >nul 2>nul
if errorlevel 1 (
  echo ERROR: No se encontro el lanzador de Python ^(py^).
  echo Instala Python 3 desde python.org y marca la opcion para instalar el Python Launcher.
  pause
  exit /b 1
)
py -3 --version
if errorlevel 1 (
  echo ERROR: No se encontro una instalacion Python 3 utilizable.
  pause
  exit /b 1
)

echo [1/5] Instalando dependencias de compilacion...
py -3 -m pip install -r requirements-build.txt
if errorlevel 1 goto :fail

echo [2/5] Comprobando sintaxis y pruebas...
py -3 -m py_compile app.py tests\test_app_helpers.py
if errorlevel 1 goto :fail
py -3 -m unittest discover -s tests -v
if errorlevel 1 goto :fail

echo [3/5] Construyendo carpeta portable con PyInstaller...
if exist build rmdir /s /q build
if exist dist\Clara rmdir /s /q dist\Clara
py -3 -m PyInstaller --noconfirm --clean --windowed --onedir --name Clara --hidden-import pyttsx3 --hidden-import pyttsx3.drivers.sapi5 --hidden-import winotify --hidden-import pystray --hidden-import PIL --collect-all pyttsx3 --collect-all comtypes --collect-all winotify --collect-all pystray --collect-all PIL app.py
if errorlevel 1 goto :fail

echo [4/5] Copiando instrucciones y utilidades...
copy /Y README.md dist\Clara\README.md >nul
copy /Y Pruebas_aceptacion_Windows_etapas_8-12.md dist\Clara\Pruebas_aceptacion_Windows_etapas_8-12.md >nul
copy /Y diagnosticar_voz.bat dist\Clara\diagnosticar_voz.bat >nul
copy /Y diagnosticar_voz.py dist\Clara\diagnosticar_voz.py >nul
for %%F in (programar_rutina.bat programar_rutina.ps1 quitar_rutina.bat quitar_rutina.ps1) do if exist "%%F" copy /Y "%%F" dist\Clara\ >nul
if not exist dist\Clara\Clara.exe (
  echo ERROR: PyInstaller no produjo dist\Clara\Clara.exe
  goto :fail
)

echo [5/5] Creando ZIP portable...
if not exist dist mkdir dist
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\Clara\*' -DestinationPath 'dist\CLARA-v1.27.4-Windows-portable.zip' -Force"
if errorlevel 1 goto :fail

echo.
echo LISTO:
echo   Carpeta ejecutable: dist\Clara\Clara.exe
echo   ZIP portable:       dist\CLARA-v1.27.4-Windows-portable.zip
echo Este build no es un instalador MSI y no esta firmado digitalmente.
echo Pruebalo primero en una cuenta Windows de prueba. Ollama y los modelos son opcionales y se instalan aparte.
pause
exit /b 0

:fail
echo.
echo ERROR: Fallo el proceso. Revisa el error anterior; no se genero un paquete fiable.
pause
exit /b 1
