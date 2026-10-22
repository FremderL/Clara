@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ======================================================================
echo  Complementos opcionales de Windows ^(notificaciones y bandeja^)
echo  ^(Descargas automaticas desactivadas por defecto^)
echo ======================================================================
echo.
echo Antes de descargar, revisa la informacion oficial de los recursos:
echo.
echo  1. Recurso:        winotify ^(notificaciones nativas de Windows^)
echo     Fuente oficial: https://pypi.org/project/winotify/
echo     Version:        ^>=1.1.0  ^|  Tamano aprox.: ~25 KB  ^|  Licencia: MIT
echo.
echo  2. Recurso:        pystray + Pillow ^(icono opcional en bandeja del sistema^)
echo     Fuente oficial: https://pypi.org/project/pystray/ y https://pypi.org/project/pillow/
echo     Version:        pystray^>=0.19.5, Pillow^>=10.0  ^|  Tamano aprox.: ~3.5 MB
echo     Licencia:       LGPL-3.0 / HPND
echo.
choice /c SN /m "¿Autorizas descargar e instalar estos complementos desde PyPI oficial?"
if errorlevel 2 (
  echo Operacion cancelada por el usuario. No se descargo ni instalo nada.
  pause
  exit /b 0
)

py -3 -m pip install "winotify>=1.1.0" "pystray>=0.19.5" "Pillow>=10.0.0"
if errorlevel 1 (
  echo No se pudieron instalar los complementos opcionales.
  echo Clara seguira funcionando con recordatorios dentro de la aplicacion.
  pause
  exit /b 1
)
echo Complementos listos: notificaciones nativas opcionales y bandeja del sistema.
echo Activalos desde Preferencias; ambos permanecen desactivados por defecto.
pause
exit /b 0
