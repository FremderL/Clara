# Plan Maestro Completo: Creación del Nuevo Asistente (`CLARA Unificada v2.0.0`) desde 0 hasta su Versión Final Auditada

Este documento define la hoja de ruta integral, paso a paso, seguida para diseñar, construir desde cero la arquitectura unificada, auditar el código, corregir errores y validar hasta su versión final utilizable a partir de lo mejor de **`CLARA_v1.27.4`** y **`Bienvenido_Señor` (Viernes)**.

- **Carpeta independiente del nuevo asistente:** `CLARA_Unificada/`
- **Carpeta independiente de este Plan Maestro y Auditoría:** `Plan_Maestro_Creacion_Asistente/`
- **Rama de trabajo aislada:** `arena/e0545502-clara` (`main`, `CLARA_v1.27.4/` y `Bienvenido_Señor/` permanecen 100 % intactos).

---

## Visión General de las 8 Etapas (De 0 a Versión Final Utilizable)

```text
[Etapa 0] Inspección estática, auditoría de licencias y plan de preservación/migración
   │
   ▼
[Etapa 1] Núcleo Local-First, esquema SQLite (11 tablas), preferencias y blindaje de secretos/DPAPI
   │
   ▼
[Etapa 2] Motor de Conversación Natural en Español (NLU local determinista + Ollama JSON cerrado)
   │
   ▼
[Etapa 3] Subsistema de Voz Bidireccional Seguro (TTS Español + Repetir + Diagnóstico + Push-to-Talk manual)
   │
   ▼
[Etapa 4] Interfaz Gráfica Adaptativa (Escalado DPI, minsize 680x440, ClaraSphere solo al hablar, DETENER AHORA)
   │
   ▼
[Etapa 5] Agenda Local, «¿Qué sigue?», Clases/Excepciones, Rutinas, Clima y Noticias RSS con Caché Offline
   │
   ▼
[Etapa 6] Límites Estrictos de Archivos (Etapas 7–10), Apps GUI (Etapa 11), VirusTotal (Etapa 6) y Descargas
   │
   ▼
[Etapa 7] Inicio Sencillo (.bat), Respaldos ZIP Validados y Vista Previa Reversible de Viernes
   │
   ▼
[Etapa 8] Auditoría Estática/Dinámica de Código, Revisión de Errores, 36 Pruebas Unitarias y Checklist Windows
```

---

## Etapa 0 — Inspección sin Ejecución, Licencias y Preservación de Datos

### Objetivo
Analizar el código real de ambos repositorios sin ejecutar binarios ni instaladores, verificar licencias y garantizar que ningún dato existente del usuario se pierda o altere sin autorización.

### Acciones de ingeniería
1. **Inspección estática completa:**
   - Lectura línea por línea de `CLARA_v1.27.4/app.py`, `diagnosticar_voz.py`, scripts `.bat`/`.ps1` y `tests/test_app_helpers.py`.
   - Lectura línea por línea de `Bienvenido_Señor/` (`viernes_app/core/nlu.py`, `tool_router.py`, `planner.py`, `assistant.py`, `voice/tts.py`, `voice/voice.py`, `voice/speech_input.py`, `voice/continuous.py`, `services/agenda_service.py`, `services/classes_service.py`, `services/tools.py`, `services/apps.py`, `ui/gui.py`, `ui/avatar.py`).
2. **Verificación de licencias:**
   - Confirmar que solo se emplean bibliotecas permisivas o estándar (`PSF-2.0`, `MPL-2.0`, `Apache-2.0`, `MIT`, `HPND`, `LGPL-3.0` opcional).
   - Descartar dependencias intrusivas o de nube (`SpeechRecognition`, `keyboard`, `PyAudio`, `psutil`).
3. **Selección crítica de componentes (qué conservar vs. qué descartar):**
   - **De CLARA se conserva:** base SQLite local-first, etapas de seguridad 6 a 12, Push-to-Talk manual con transcripción editable, `ClaraSphere` y parada de emergencia.
   - **De Viernes se adapta y rehace con seguridad:** catálogo de intenciones naturales en español (`¿qué sigue?`, `¿cómo va mi día?`, noticias por tema, clima, clases, ayuda), cálculo operativo del próximo compromiso del día y caché local de titulares (`news_cache.json`) para modo sin conexión.
   - **De Viernes se descarta por inseguro:** escucha continua (`continuous.py`), envío de audio a Google (`speech_input.py`), auto-envío de dictado sin editar (`_listen_once`), interpolación de voz en PowerShell (`ViernesVoice`), movimiento masivo de hasta 500 archivos, lectura/escritura de archivos desde el modelo y ejecución de scripts `.ps1`/`.bat`/`.py` o apagado del sistema.
4. **Plan de preservación y migración reversible:**
   - Mantener intacta la ruta `%USERPROFILE%\AsistentePersonal` (`asistente.db`, `settings.json`, `virustotal_api_key.dpapi`).
   - Prohibir cualquier migración automática en el arranque y ofrecer una herramienta 100 % de solo lectura (`preview_viernes_migration`) para previsualizar tareas únicas de `viernes_agenda.json` sin inferir rutinas ni tocar la base de datos.

---

## Etapa 1 — Núcleo Local-First, Base de Datos SQLite y Blindaje de Preferencias/Claves

### Objetivo
Construir la capa de almacenamiento local y configuración con valores por defecto exactos y garantías de que ninguna clave API o archivo sensible se filtre a chats, preferencias, respaldos ni GitHub.

### Acciones de ingeniería
1. **Configuración por defecto editable (`DEFAULT_SETTINGS`):**
   - `weather_location`: **`"Colima, Colima, México"`**.
   - `morning_time`: **`"07:00"`** (7:00 a. m.).
   - `auto_speak_responses`: **`"true"`**.
   - `chat_history_enabled`: **`"false"`** (desactivado por defecto por privacidad).
   - `calendar_ics_path`: **`""`** (sin calendarios externos conectados).
2. **Esquema SQLite transaccional (`connect_db`):**
   - 11 tablas locales con migraciones idempotentes: `tasks`, `classes`, `class_exceptions`, `routines`, `plan_blocks`, `memories`, `reminder_events`, `reminder_actions`, `security_events`, `action_events`, `chat_history`.
3. **Blindaje contra fugas de claves API (`contains_potential_api_key` y `sanitize_settings_for_storage`):**
   - Detectar cadenas hexadecimales de 64 caracteres (formato VirusTotal) y asignaciones `api_key`/`token`/`x-apikey`.
   - Bloquear su envío en el chat (`send_chat`) y su persistencia en `chat_history` (`append_chat`).
   - Filtrar y validar `settings.json` antes de cada escritura (`save_settings`) para garantizar que `virustotal_api_key` jamás entre a `settings.json` ni a los respaldos ZIP.
   - Cifrar la clave de VirusTotal exclusivamente mediante Windows DPAPI (`CryptProtectData` / `CryptUnprotectData` en `virustotal_api_key.dpapi`).
4. **Protección de repositorio (`.gitignore`):**
   - Excluir `*.db`, `*.sqlite*`, `*.dpapi`, `.env*`, `settings.json`, `news_cache.json`, `*.zip`, `models/`, `build/` y `dist/`.

---

## Etapa 2 — Motor de Conversación Natural en Español (Local-First + Ollama Opcional)

### Objetivo
Lograr que el usuario converse con naturalidad en español tanto **sin Ollama** (modo 100 % local determinista) como **con Ollama local** (`http://127.0.0.1:11434`), sin que el asistente ejecute acciones destructivas ni malinterprete negaciones.

### Acciones de ingeniería
1. **Normalización y defensas semánticas (`normalize_intent_text`, `is_negated_or_informational_query`, `is_blocked_unsafe_request`):**
   - Normalizar tildes, eñes (`ñ -> n`) y signos (`¿?¡!`).
   - Si el mensaje contiene una negación (`"no busques..."`, `"no abras..."`, `"no quiero que muevas..."`) o una pregunta informativa (`"¿cómo se mueve un archivo?"`), devolver siempre una respuesta explicativa (`intent = "informational"`) sin abrir diálogos de acción.
   - Si el mensaje pide ejecutar consolas (`cmd`, `powershell`, `bash`), scripts (`.ps1`, `.bat`, `.py`), instaladores (`setup.exe`, `winget`), apagar/reiniciar el PC o buscar ejecutables (`.exe`), rechazarlo inmediatamente (`intent = "blocked_unsafe"`) explicando el límite de seguridad.
2. **Clasificador NLU local en español (`classify_local_natural_intent`):**
   - `next_commitment`: *«¿qué sigue?»*, *«¿qué toca ahora?»*, *«siguiente pendiente»*.
   - `morning_brief`: *«rutina matutina»*, *«resumen matutino»*, *«buenos días clara resumen»*.
   - `agenda_query` / `week_agenda`: *«¿cómo va mi día?»*, *«¿qué tengo hoy/mañana?»*, *«agenda semanal»*.
   - `classes_query` y `routines_query`: *«mis clases»*, *«¿qué clases tengo mañana?»*, *«mis rutinas»*.
   - `news_query` (con detección de tema: General, México, Ciencia, Tecnología, Negocios, Deportes, Cultura, Salud) y `weather_query` (*«¿cómo está el clima?»*).
   - `afternoon_plan`: *«organiza mi tarde»*, *«planifica la tarde»*.
   - `file_inventory` y `file_search`: *«inventaría una carpeta»*, *«busca mi pdf de biología»* (precarga filtros, pero obliga a elegir carpeta manualmente).
   - `repeat_last`, `voice_diagnostics` y `help`.
3. **Validador JSON cerrado para Ollama (`CHAT_INTENT_FIELDS` y `validate_chat_intent`):**
   - Validar que el JSON devuelto por el modelo local contenga exactamente las llaves permitidas por intención, sin rutas (`/` o `\`), sin `..` y solo con extensiones permitidas.

---

## Etapa 3 — Subsistema de Voz Bidireccional Seguro (TTS Español + Push-to-Talk Manual)

### Objetivo
Hablar en voz alta respuestas y resúmenes de noticias/agenda cuando la lectura automática esté activa, ofrecer botón de repetición y diagnóstico de voz, explicar cualquier fallo conservando el texto escrito y mantener el micrófono apagado por defecto con Push-to-Talk manual y transcripción editable.

### Acciones de ingeniería
1. **Selección de voz en español (`select_spanish_voice_id`):**
   - Inspeccionar las voces SAPI5 devueltas por `pyttsx3` priorizando Español de México (`es-mx`, `sabina`, `dalia`, `raul`) y Español de España/Latinoamérica (`es-es`, `es-419`, `helena`, `pablo`) antes de caer en la voz predeterminada del sistema.
2. **Lectura automática de respuestas y resúmenes (`SPOKEN_CHAT_SPEAKERS` en `append_chat`):**
   - Activar lectura automática para `"Asistente"`, `"Clara"`, `"Rutina matutina"` y `"Clima y noticias"` cuando `auto_speak_responses == "true"`, y combinar en una sola lectura fluida el resumen matutino con el clima y titulares al concluir la descarga (`morning_online`).
3. **Botón `🔊 Repetir última respuesta` y degradación elegante (`explain_tts_failure`, `_report_tts_failure`):**
   - Si falta `pyttsx3`, no hay voces en Windows o falla el motor de audio, mostrar la explicación clara en la barra de estado y en el chat (cuando es manual o la primera vez en la sesión) **conservando íntegra la respuesta escrita**.
4. **Diagnóstico de voz integrado (`collect_voice_diagnostics`, `open_voice_diagnostics`, `diagnosticar_voz.py`):**
   - Botón **`🩺 Diagnóstico de voz`** en la barra principal + utilidad CLI `diagnosticar_voz.bat` (`--check-only` o con prueba audible), verificando `pyttsx3`, voces en español, `vosk`, `sounddevice` y `models/vosk-model-small-es-0.42` **sin activar nunca el micrófono (`microphone_activated = False`) ni usar internet**.
5. **Micrófono Push-to-Talk manual (`toggle_voice_input`, `_record_and_transcribe_once`):**
   - Micrófono apagado al iniciar (`self.voice_active = False`).
   - Solo graba tras pulsar manualmente **`🎙 Pulsar para hablar`** y coloca el texto reconocido en `self.chat_input` para edición manual antes de pulsar **`Enviar`**.

---

## Etapa 4 — Interfaz Gráfica Adaptativa, Escalado Windows, Esfera Visual y Parada de Emergencia

### Objetivo
Garantizar que en pantallas pequeñas o con escalado de Windows (100 %, 125 %, 150 %) se vean claramente el campo de chat, `Enviar`, los controles de voz y `DETENER AHORA`, y que la esfera visual solo se expanda mientras el asistente habla.

### Acciones de ingeniería
1. **Adaptación DPI y geometría responsiva (`_configure_dpi_scaling`, `_build_ui`):**
   - Invocar `SetProcessDpiAwareness(1)` en Windows y ajustar `tk. scaling`.
   - Configurar `minsize(680, 440)` y reservar la fila inferior del chat (`pack(side="bottom", fill="x")`) antes del área expandible del historial para que `chat_input` y `self.send_button` (`Enviar`) nunca queden ocultos.
2. **Esfera visual (`ClaraSphere` y `sphere_radius_for_state`):**
   - En `state == "idle"` y `state == "listening"`: radio compacto idéntico (`min(width, height) * 0.24`), sin expansión.
   - Únicamente en `state == "speaking"`: radio expandido (`min(width, height) * 0.34 + pulse`) con halos animados; regresa inmediatamente al radio compacto al terminar de hablar o al pulsar `DETENER AHORA`.
3. **Parada de emergencia honesta (`emergency_stop`):**
   - Botón rojo **`⛔ DETENER AHORA · Esc`** siempre visible en la cabecera y atajo global `<Escape>`.
   - Cancela generación de Ollama, apaga el micrófono, detiene la voz TTS, señala cancelación al escaneo local de archivos e ignora respuestas pendientes de VirusTotal, informando con honestidad que no revierte datos ya guardados en SQLite ni mata procesos externos ya abiertos.

---

## Etapa 5 — Agenda Local, «¿Qué sigue?», Clases, Rutinas, Noticias y Clima con Caché Local

### Objetivo
Unificar la organización escolar/personal 100 % local con el cálculo operativo de *«¿Qué sigue?»* y un sistema seguro de noticias y clima bajo demanda con respaldo offline.

### Acciones de ingeniería
1. **Cálculo de «¿Qué sigue?» (`build_next_commitment_summary`, botón `⏭ ¿Qué sigue?`):**
   - Cruzar en tiempo real las clases del día (resueltas con `classes_for_date` y `day_off_for`), los bloques locales (`plan_blocks`) y las tareas pendientes (`tasks`) para indicar cuál es el siguiente compromiso, cuántos minutos faltan y qué pendientes sin hora quedan hoy.
2. **Rutinas sin inferencia silenciosa ni duplicados:**
   - Las rutinas solo se crean mediante confirmación manual del usuario (`source = 'Rutina configurada manualmente por el usuario'`) y `ensure_daily_routines` inserta como máximo una tarea diaria por rutina activa.
3. **Calendario local (`.ics`):**
   - Importación manual de eventos únicos (omitiendo `RRULE` y eventos propios exportados), exportación `.ics` local y vínculo `.ics` local de solo lectura (`read_linked_ics_events` rechaza cualquier URL `http://`, `https://` o `webcal://`).
4. **Clima y noticias RSS seguras con caché local (`parse_news_feed`, `save_news_cache`, `load_news_cache`):**
   - Descarga solo cuando el usuario pide la rutina matutina, noticias o clima.
   - Rechazo de XML mayores de 2 MB o con `<!DOCTYPE` / `<!ENTITY`, limpieza de etiquetas HTML (`clean_rss_text`) y enlaces mostrados como texto sin apertura automática.
   - Guardado automático de los últimos titulares en `news_cache.json` y lectura desde caché si falla la red.

---

## Etapa 6 — Límites Obligatorios de Archivos, Aplicaciones GUI, VirusTotal y Descargas

### Objetivo
Asegurar por diseño y por código que ninguna operación de archivos, carpetas, aplicaciones o descargas exceda los límites de seguridad autorizados por el usuario.

### Acciones de ingeniería
1. **Búsqueda e inventario local (`validate_local_search_root`, `scan_local_documents`):**
   - El usuario elige la carpeta raíz en cada operación (no se persiste ni se indexa en segundo plano).
   - Se rechazan raíces del sistema (`C:\`, perfil completo, `Windows`, `Program Files`, `AppData`), carpetas de nube (`OneDrive`, `Dropbox`, `Google Drive`, `iCloud`), carpetas ocultas/sistema, enlaces simbólicos/junctions y unidades extraíbles o de red.
   - Búsqueda exclusivamente por nombre y extensión entre los 6 tipos permitidos: `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.txt`, `.md`/`.markdown`. Jamás se lee el contenido de los archivos.
2. **Abrir documento permitido (`validate_local_document_for_open`):**
   - Advertencia y confirmación individual mostrando nombre, ruta relativa y tamaño, seguida de revalidación TOCTOU (`size`, `mtime_ns`, `file_id`, ausencia de symlinks) justo antes de invocar `os.startfile`.
3. **Mover un archivo por vez y Deshacer en sesión (`prepare_local_move`, `execute_local_move`):**
   - Un solo archivo permitido por operación, dentro del mismo volumen local, prohibiendo sobrescribir (`FileExistsError` si el destino ya existe) y prohibiendo mover carpetas.
   - Botón **Deshacer último movimiento** disponible solo mientras la ventana permanezca abierta en la sesión actual y si el archivo movido sigue intacto.
4. **Etapa 7 — Abrir carpeta en el Explorador (`validate_selected_folder`, `launch_selected_folder`):**
   - Limitada a abrir en el Explorador de Windows una carpeta existente elegida y confirmada en cada ocasión, sin listar, leer ni modificar su contenido.
5. **Aplicaciones GUI autorizadas (`validate_local_application`, `launch_allowed_application`):**
   - Lista blanca de máximo 10 ejecutables `.exe` bajo `Program Files` o `LocalAppData\Programs`.
   - Verificación binaria de cabecera PE (`subsystem == 2` Windows GUI), rechazando consolas/intérpretes (`cmd`, `powershell`, `python`, `node`, `mshta`, `rundll32`, `regedit`) e instaladores (`setup`, `install`, `unins`, `update`).
   - Confirmación explícita al añadir a la lista y en cada inicio (`subprocess.Popen([exe], shell=False)` sin argumentos ni elevación).
6. **VirusTotal manual hash-only (`hash_file_sha256`):**
   - Cálculo local de SHA-256 y consentimiento individual antes de consultar `https://www.virustotal.com/api/v3/files/{sha256}`. Nunca sube archivos ni toma acciones automáticas según el veredicto.
7. **Descargas y recursos (`AUTO_DOWNLOADS_ENABLED = False`, `OFFICIAL_RESOURCES`, `format_resource_disclosure`, `verify_resource_sha256`):**
   - Ninguna descarga automática habilitada. Todo recurso opcional exhibe fuente oficial, recurso, versión, tamaño, licencia y verificación SHA-256.

---

## Etapa 7 — Inicio Sencillo, Empaquetado Opcional, Respaldos y Migración Reversible

### Objetivo
Entregar un arranque directo y transparente para el usuario diario, junto con herramientas de respaldo y restauración seguras.

### Acciones de ingeniería
1. **Lanzadores limpios (`iniciar.bat`, `iniciar_clara_terminal.bat`):**
   - Verifican Python 3.10+ y Tkinter e inician `py -3 app.py` directamente, sin ejecutar `pip install`, `ollama pull`, scripts del chat ni elevaciones UAC.
2. **Respaldos locales (`export_backup`, `extract_validated_backup`, `import_backup`):**
   - Exportan `asistente.db` y `settings.json` sanitizado (advirtiendo claramente que el ZIP **no está cifrado** y excluyendo siempre `virustotal_api_key.dpapi`).
   - Al restaurar, validan nombres y tamaños máximos del ZIP y crean primero un respaldo automático en `backups_before_restore/`.

---

## Etapa 8 — Auditoría de Código, Revisión de Errores y Validación Final

El detalle completo de la auditoría estática (AST, símbolos, 122 consultas SQL), los errores detectados y corregidos y el resultado de las 36 pruebas unitarias se documenta en:
👉 `Plan_Maestro_Creacion_Asistente/01_AUDITORIA_DE_CODIGO_Y_REVISION_DE_ERRORES.md`
