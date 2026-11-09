# Guía Rápida de Instalación y Actualización — CLARA Unificada v2.0.0

## 1. Preservación de datos existentes

- `CLARA_Unificada` utiliza la misma carpeta de datos que CLARA v1.27.4:
  `%USERPROFILE%\AsistentePersonal` (`asistente.db`, `settings.json`, `virustotal_api_key.dpapi`).
- **No necesitas migrar ni convertir tu base de datos de CLARA:** todas tus tareas, clases, excepciones escolares, bloques, rutinas, recuerdos y preferencias se conservan intactos.
- Las carpetas `CLARA_v1.27.4/` y `Bienvenido_Señor/` permanecen intactas.

## 2. Requisitos base

- **Sistema operativo:** Windows 10 o Windows 11 (64 bits).
- **Python:** Python 3.10 o superior desde la fuente oficial (`https://www.python.org/downloads/windows/`), marcando **Tcl/Tk and IDLE** y **py launcher**.
- **Sin dependencias obligatorias de terceros:** la agenda, tareas, clases, rutinas, bloques, «¿qué sigue?», búsqueda/apertura/movimiento de documentos, aplicaciones autorizadas, noticias y clima funcionan con la biblioteca estándar de Python.

## 3. Cómo iniciar CLARA Unificada

1. Abre la carpeta `CLARA_Unificada`.
2. Haz doble clic en **`iniciar.bat`** (o en **`iniciar_clara_terminal.bat`** si prefieres ver el resumen de diagnóstico previo en consola).

## 4. Complementos opcionales (descargas automáticas desactivadas)

Ningún recurso se descarga ni instala sin tu autorización manual. Antes de cualquier descarga, los scripts muestran **fuente oficial, recurso, versión, tamaño aproximado y licencia**:

- **Voz local (salida hablada `pyttsx3` y dictado Push-to-Talk `vosk` + `sounddevice`):**
  1. Ejecuta manualmente `instalar_voz.bat` y confirma la instalación desde PyPI oficial.
  2. Para reconocimiento de voz offline (Push-to-Talk), descarga manualmente `vosk-model-small-es-0.42.zip` (39 MB, licencia Apache-2.0) desde `https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip` y extráelo en:
     `CLARA_Unificada\models\vosk-model-small-es-0.42`
  3. Prueba la voz sin usar micrófono ni internet con el botón **`🩺 Diagnóstico de voz`** o ejecutando `diagnosticar_voz.bat`.

- **Notificaciones nativas y bandeja del sistema (`winotify`, `pystray`, `Pillow`):**
  - Ejecuta manualmente `instalar_opciones_windows.bat` y actívalas después en **Preferencias** si las deseas.

- **Conversación con IA local (Ollama):**
  - Instala Ollama desde su fuente oficial (`https://ollama.com`), inicia el servicio local y pulsa **«Detectar Ollama»** en la ventana de CLARA.

- **Rutina matutina programada en Windows (7:00 a. m. por defecto):**
  - Ejecuta `programar_rutina.bat` para registrar las tareas del Programador de tareas de Windows (`AsistentePersonal-Manana` y `AsistentePersonal-Recordatorios`). Requieren sesión de Windows iniciada. Para retirarlas sin borrar tus datos, ejecuta `quitar_rutina.bat`.
