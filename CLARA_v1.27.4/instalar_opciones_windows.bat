@echo off
setlocal
cd /d "%~dp0"
py -m pip install --upgrade winotify pystray Pillow
if errorlevel 1 (
  echo No se pudieron instalar los complementos opcionales.
  echo Clara seguira funcionando con recordatorios dentro de la aplicacion.
  pause
  exit /b 1
)
echo Complementos listos: notificaciones nativas opcionales y bandeja del sistema.
echo Activalos desde Preferencias; ambos permanecen desactivados por defecto.
pause
