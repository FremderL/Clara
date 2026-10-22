# Probar Clara en Windows

## Paquete portable de código fuente

El paquete de código fuente de CLARA v1.27.4 contiene el código y necesita **Windows 10/11, Python 3.10 o posterior con Tcl/Tk**. No modifica el registro ni instala un servicio.

1. Descarga y extrae todo el ZIP a una carpeta normal de tu usuario. No ejecutes la app directamente desde dentro del ZIP.
2. Para revisar el código y sus pruebas, haz doble clic en `probar_clara.bat`. El pase de pruebas no abre la GUI.
3. Para iniciar Clara, haz doble clic en `iniciar.bat`. Las tareas y clases locales funcionan sin Ollama; para chat local instala Ollama y descarga por separado un modelo compatible.
4. Para que la terminal compruebe/inicie Ollama, verifique Qwen3 y ofrezca instalar pyttsx3, ejecuta `iniciar_clara_terminal.bat`. Las descargas e instalación opcional piden confirmación; el micrófono no se activa automáticamente. Clara abre su interfaz gráfica y la terminal queda abierta para mostrar mensajes.
5. Los datos de la app se guardan en `%USERPROFILE%\\AsistentePersonal`, separados de la carpeta del programa. La ruta se mantiene igual que en versiones previas para conservar datos. Haz una copia de seguridad antes de probar restauración o borrado.

## Ejecutable portable generado en Windows

Para construir `dist\\Clara\\Clara.exe`, ejecuta `build_windows.bat` en Windows con conexión para instalar PyInstaller y sus dependencias. El script prueba sintaxis y tests antes de empaquetar. Al terminar crea `dist\\CLARA-v1.27.4-Windows-portable.zip`.

No es un instalador MSI: se extrae la carpeta/ZIP y se ejecuta `Clara.exe`. El ejecutable no está firmado digitalmente. No es posible validar SmartScreen, asociaciones, DPAPI, notificaciones, Programador de tareas ni acciones reales de archivos desde este entorno; haz una prueba inicial en una cuenta o equipo de prueba y conserva tus datos importantes.

## Opcionales

- `instalar_opciones_windows.bat`: instala paquetes opcionales de bandeja/toasts. Las funciones siguen apagadas hasta activarlas en Preferencias.
- `instalar_voz.bat`: instala dependencias de voz. También se debe descargar manualmente el modelo Vosk de español descrito en README. El micrófono sigue siendo push-to-talk y no se activa continuamente.
- `diagnosticar_voz.bat`: prueba manualmente la voz de salida y enumera voces de Windows; no usa el micrófono ni internet.
- Los modelos Ollama no se incluyen por tamaño/licencia; se instalan aparte desde la fuente oficial de Ollama. Las consultas del chat usan el servidor local configurado por la aplicación.

## Limitaciones del paquete de prueba

- El ZIP adjunto a esta versión es un paquete de código fuente, no contiene `Clara.exe`.
- El ejecutable debe construirse en Windows. PyInstaller no puede producir desde este entorno Linux un `.exe` Windows fiable.
- Las pruebas unitarias simuladas no certifican la interfaz ni operaciones reales Windows. Usa `Pruebas_aceptacion_Windows_etapas_8-12.md` como lista de aceptación, con carpetas y datos ficticios; no pruebes restauración/borrado en tu perfil principal.
- El primer pase del clasificador descrito en `Diseño_intenciones_naturales_Clara_v1.27.md` está integrado. Su comportamiento real con Ollama/modelo y los diálogos de Windows aún debe probarse.
