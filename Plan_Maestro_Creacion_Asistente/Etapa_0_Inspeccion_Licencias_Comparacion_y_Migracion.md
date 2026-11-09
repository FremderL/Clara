# Etapa 0 — Inspección Estática, Auditoría de Licencias, Comparación Técnica, Discrepancias y Plan de Preservación/Migración

> **Estado de la Etapa 0:** **COMPLETADA Y VERIFICADA**  
> **Regla cumplida:** Durante esta inspección se utilizó únicamente lectura estática de archivos (`read_file`). **No se ejecutaron binarios, instaladores, workflows, comandos de descarga ni código de ninguno de los dos proyectos.**  
> **Rama activa:** `arena/e0545502-clara` (`main`, `CLARA_v1.27.4/` y `Bienvenido_Señor/` permanecen 100 % intactos).

---

## 1. Estructura Real de Ambos Repositorios

### 1.1 `CLARA_v1.27.4/` (Centro Local de Asistencia, Rutinas y Agenda)
- **Módulo principal:** `CLARA_v1.27.4/app.py` (5,023 líneas) — aplicación monolítica en Python 3.10+ (`tkinter`/`ttk` + `sqlite3` + `urllib`) que implementa las Etapas 1 a 12 de seguridad y agenda local.
- **Diagnóstico de voz:** `CLARA_v1.27.4/diagnosticar_voz.py` y `diagnosticar_voz.bat`.
- **Lanzadores e instaladores Windows:** `iniciar.bat`, `iniciar_clara_terminal.bat`, `instalar_voz.bat`, `instalar_opciones_windows.bat`, `programar_rutina.bat`, `programar_rutina.ps1`, `quitar_rutina.bat`, `quitar_rutina.ps1`, `build_windows.bat`, `probar_clara.bat`.
- **Pruebas unitarias existentes:** `CLARA_v1.27.4/tests/test_app_helpers.py` (480 líneas, 23 pruebas unitarias).
- **Documentación:** `README.md`, `LEEME_INSTALACION.md`, `Auditoria_tecnica_Clara_v1.27.4.md`, `Diseño_intenciones_naturales_Clara_v1.27.md`, `Futuras_etapas_Clara.md`, `Pruebas_aceptacion_Windows_etapas_8-12.md`.

### 1.2 `Bienvenido_Señor/` (Viernes — Asistente Personal con IA)
- **Puntos de entrada:** `viernes.py`, `viernes_gui.py`, `viernes_core.py` y paquete modular `viernes_app/`:
  - `viernes_app/core/`: `assistant.py`, `nlu.py` (`NaturalLanguageRouter`), `planner.py`, `tool_router.py`.
  - `viernes_app/voice/`: `tts.py` (`ViernesTTS`), `voice.py` (`ViernesVoice`), `speech_input.py` (`ViernesSpeechInput`), `continuous.py` (`ContinuousVoiceListener`), `interruption.py`.
  - `viernes_app/services/`: `agenda_service.py`, `classes_service.py`, `tools.py`, `apps.py`, `routines.py`, `budget.py`, `reminders.py`, `system_status.py`.
  - `viernes_app/ui/`: `gui.py` (`ViernesGUI`, 2,104 líneas), `modern.py`, `avatar.py` (`HoloAvatar`).
  - `security/permissions.py`: `PermissionManager`.
- **Pruebas existentes:** `tests/test_agent_system.py` y `tests/test_analysis_beta.py`.
- **Artefactos de datos reales commiteados en el repo (riesgo de privacidad detectado):** `viernes_data.db`, `data/activity.sqlite3`, `viernes_history.json`, `viernes_agenda.json`, `viernes_notes.json`, `viernes_reminders.json`, `viernes_budget.json`, `viernes_config.json`.

---

## 2. Comprobación de Licencias antes de Copiar o Adaptar Código

1. **Código propio del repositorio (`FremderL/Clara`):**
   - Tanto `CLARA_v1.27.4` como `Bienvenido_Señor` son código propio dentro del mismo repositorio del usuario y no contienen cabeceras `LICENSE` ni restricciones de terceros que prohíban combinarlos en `CLARA_Unificada/`.
2. **Auditoría de licencias de dependencias (`CLARA_v1.27.4/requirements-build.txt` y `Bienvenido_Señor/requirements.txt`):**

| Paquete | Proyecto de origen | Licencia verificada | ¿Se permite uso en `CLARA_Unificada`? | Decisión arquitectónica |
|---|---|---|---|---|
| Biblioteca estándar de Python (`tkinter`, `sqlite3`, `urllib`, `xml`, `zipfile`, `ctypes`) | Ambos | **PSF-2.0** | Sí | Base obligatoria del núcleo local-first. |
| `pyttsx3` (`>=2.90`) | Ambos | **MPL-2.0 / MIT** | Sí (sin modificar archivos internos de `pyttsx3`) | Conservado como dependencia opcional para lectura en voz alta SAPI5. |
| `vosk` (`>=0.3.45`) + `vosk-model-small-es-0.42` | Ambos | **Apache-2.0** | Sí | Conservado como dependencia opcional para Push-to-Talk 100 % offline. |
| `sounddevice` (`>=0.4.6`) | Ambos | **MIT** | Sí | Conservado como dependencia opcional para captura manual de micrófono. |
| `winotify` (`>=1.1.0`) | CLARA | **MIT** | Sí | Conservado como complemento opcional de avisos nativos en Windows. |
| `Pillow` (`>=10.0`) | CLARA | **HPND (permisiva)** | Sí | Conservado como complemento opcional para icono de bandeja. |
| `pystray` (`>=0.19.5`) | CLARA | **LGPL-3.0** | Sí (importación dinámica opcional sin enlazar estáticamente) | Opcional y desactivado por defecto. |
| `pyinstaller` (`>=6.0`) | CLARA | **GPLv2 con excepción de bootloader** | Sí (solo herramienta opcional de empaquetado) | Opcional en `build_windows.bat`. |
| `SpeechRecognition` (`>=3.10.0`) | Viernes | BSD-3-Clause | **DESCARTADO** | En `viernes_app/voice/speech_input.py` envía audio a Google Cloud (`recognize_google`). Prohibido por diseño local-first. |
| `keyboard` (`>=0.13.5`) | Viernes | MIT | **DESCARTADO** | En `utils/push_to_talk.py` instala un hook global de teclado (`left alt`) a nivel de sistema. |
| `customtkinter`, `matplotlib`, `numpy` | Viernes | MIT / PSF / BSD | **DESCARTADOS** | Innecesarios; `tkinter`/`ttk` nativo evita dependencias pesadas en el arranque. |

---

## 3. Tabla Comparativa Detallada: `CLARA_v1.27.4` vs. `Bienvenido_Señor` (Viernes)

| Área / Función | Implementación real en `CLARA_v1.27.4` | Implementación real en `Bienvenido_Señor` (Viernes) | Pruebas existentes | Riesgos detectados | Qué conservar o rehacer en `CLARA_Unificada` |
|---|---|---|---|---|---|
| **1. Conversación natural y clasificación de intenciones** | `send_chat` (`app.py:4878-4932`) reconoce prefijos fijos para tareas, bloques y agenda hoy/mañana; con Ollama activo usa `ask_ollama` (`app.py:4580-4615`) y valida con `validate_chat_intent` (`app.py:1375-1435`). | `NaturalLanguageRouter.interpret` (`viernes_app/core/nlu.py:70-480`) clasifica frases naturales en español (`today_status`, `next_commitment`, `morning_brief`, `weather`, `news`, `classes`, `help`), pero `ToolRouter` (`viernes_app/core/tool_router.py`) ejecuta herramientas directamente. | CLARA prueba `validate_chat_intent` y `parse_task_proposal`. Viernes **no tiene** el `tests/test_nlu.py` que promete su documentación. | En CLARA, sin Ollama no se entienden consultas naturales de *«¿qué sigue?»*, noticias, clima, clases o rutinas. En Viernes, el agente puede disparar acciones sobre archivos o sistema sin formulario previo. | **Conservar** `validate_chat_intent` de CLARA y **rehacer/integrar** un enrutador determinista en español (`classify_local_natural_intent`) que funcione sin Ollama y respete negaciones (`no busques...`) y preguntas informativas (`¿cómo se mueve...?`). |
| **2. Respuestas habladas (TTS), resúmenes, botón repetir y diagnóstico** | `_start_tts` (`app.py:2177-2222`), `speak_last_response` (`app.py:2170-2175`) y `diagnosticar_voz.py`. **Brecha:** `append_chat` (`app.py:4489-4505`) solo llama `_start_tts` si `speaker.startswith("Asistente")`, por lo que `"Rutina matutina"` y `"Clima y noticias"` no se leen en voz alta. | `ViernesTTS` (`viernes_app/voice/tts.py:18-95`) busca voces en español (`es-mx`/`es-es`), pero `ViernesVoice` (`viernes_app/voice/voice.py:40-98`) ejecuta PowerShell interpolando el texto en `SAPI.SpVoice`. | CLARA tiene 1 prueba de `append_chat` para `"Asistente"`. Viernes no tiene pruebas de voz. | En Viernes, interpolar texto dentro de comandos de PowerShell es inseguro. En CLARA, los resúmenes matutinos/noticias no se leen en voz alta, no se prioriza voz en español y falta un botón de diagnóstico en la ventana principal. | **Mejorar sobre CLARA:** hablar en `SPOKEN_CHAT_SPEAKERS` (`Asistente`, `Clara`, `Rutina matutina`, `Clima y noticias`), seleccionar voz en español (`select_spanish_voice_id`), añadir botones **`🔊 Repetir última respuesta`** y **`🩺 Diagnóstico de voz`** en la barra principal, y mostrar explicación clara (`explain_tts_failure`) si falla la voz conservando el texto. |
| **3. Micrófono y Push-to-Talk** | `toggle_voice_input` y `_record_and_transcribe_once` (`app.py:2225-2320`): micrófono apagado al iniciar (`voice_active = False`), captura manual con `vosk` + `sounddevice`, e inserta la transcripción en `chat_input` para edición manual antes de pulsar `Enviar`. | 4 implementaciones contradictorias: `continuous.py` (escucha continua en segundo plano), `speech_input.py` (envía audio a Google Cloud con `recognize_google`), `push_to_talk.py` (hook global `left alt`) y `_listen_once` en `gui.py` (envía inmediatamente sin permitir editar). | Ninguno automatiza hardware de audio, pero CLARA documenta la prueba manual. | Los 4 módulos de Viernes violan la prohibición de escucha continua, uso de nube para voz y auto-envío sin edición previa. | **Conservar exclusivamente el Push-to-Talk manual de CLARA** y descartar los 4 módulos de entrada de voz de Viernes. |
| **4. Interfaz, pantallas pequeñas, escalado y esfera visual** | `ClaraSphere` (`app.py:1318-1370`) se expande **únicamente** cuando `state == "speaking"`. Cabecera con `⛔ DETENER AHORA · Esc`. Faltaba ajuste explícito de DPI y botón directo para *«¿Qué sigue?»*. | `HoloAvatar` (`viernes_app/ui/avatar.py:45-160`) anima ondas tanto en `pulse_speaking()` como en `pulse_listening()` (`gui.py:2076-2079`) y con temporizadores automáticos. | Sin pruebas unitarias de geometría de la esfera en ninguno de los dos. | `HoloAvatar` de Viernes viola la regla de que la esfera solo debe expandirse mientras el asistente habla. | **Conservar `ClaraSphere` de CLARA**, añadir `sphere_radius_for_state` con prueba unitaria, activar escalado DPI de Windows y `minsize(680, 440)` con filas fijas para chat, `Enviar`, controles de voz y `DETENER AHORA`. |
| **5. Ubicación (`Colima, Colima, México`), rutina `07:00`, clima y noticias** | `DEFAULT_SETTINGS` (`app.py:55-68`) define `morning_time="07:00"` y `weather_location="Colima, Colima, México"`, ambos editables. `parse_news_feed` (`app.py:410-455`) limita RSS a 2 MB y rechaza `<!DOCTYPE`/`<!ENTITY`. Sin caché offline. | `viernes_config.json` usa `"Ciudad de México"` por defecto. `get_news` (`viernes_app/services/tools.py:300-338`) guarda caché local en `news_cache.json` por 18 h, pero no valida `<!DOCTYPE`/`<!ENTITY` ni límite de bytes. | CLARA prueba `parse_news_feed` (límites y defensas XML). | Viernes carece de defensas XML y usa otra ubicación por defecto; CLARA carece de respaldo offline si falla internet. | **Combinar lo mejor de ambos:** valores por defecto `Colima, Colima, México` y `07:00` editables + `parse_news_feed` seguro de CLARA + limpieza HTML (`clean_rss_text`) + caché local (`save_news_cache`/`load_news_cache` en `news_cache.json`) cuando falla la conexión. |
| **6. Organización de agenda, clases, rutinas y «¿Qué sigue?»** | SQLite local (`asistente.db`): tareas con recurrencia controlada (`toggle_task_completion`), clases con excepciones escolares (`classes_for_date`), bloques de tarde (`build_afternoon_draft`), rutinas manuales sin inferencia automática e `.ics` 100 % local. | `AgendaService.get_today_operational_summary` (`viernes_app/services/agenda_service.py:185-250`) calcula el siguiente compromiso del día y el tiempo restante, pero almacena en JSON plano (`viernes_agenda.json`). | CLARA tiene 9 pruebas unitarias para agenda, recurrencia, excepciones escolares, bloques e `.ics` local. | El JSON plano de Viernes no soporta transacciones ni excepciones escolares; a CLARA le faltaba el cálculo directo de *«¿Qué sigue?»*. | **Conservar SQLite e `.ics` local de CLARA** y añadir `build_next_commitment_summary` (*«¿Qué sigue?»*) sobre la base SQLite. |
| **7. Búsqueda, apertura y movimiento de archivos, apps GUI y VirusTotal** | Etapas 6 a 12 en `CLARA_v1.27.4/app.py`: carpeta elegida cada vez, solo `.pdf`/`.docx`/`.xlsx`/`.pptx`/`.txt`/`.md`, confirmación + revalidación TOCTOU al abrir o mover 1 archivo (sin sobrescribir, deshacer en sesión), máx. 10 apps GUI `.exe` (`subsystem == 2`, `shell=False`), VirusTotal manual por hash SHA-256 con clave en DPAPI. | `tool_router.py` y `tools.py` permiten leer contenido de archivos, escribir archivos, mover lotes de hasta 500 archivos, ejecutar `.py`/`.ps1`/`.bat`/`.cmd` (`apps.py:25-70`) y apagar/reiniciar el PC (`tools.py:352-378`). | CLARA tiene 10 pruebas unitarias para escaneo, apertura, movimiento, lista blanca PE y VirusTotal. | Los módulos de archivos y aplicaciones de Viernes incumplen todos los límites obligatorios de seguridad. | **Conservar íntegras las Etapas 6 a 12 de CLARA**, descartar `tools.py`/`apps.py` de Viernes y añadir detección de claves API en chat y preferencias (`contains_potential_api_key`, `sanitize_settings_for_storage`). |
| **8. Inicio sencillo y descargas de recursos** | `iniciar.bat` lanza `py -3 app.py`, pero `iniciar_clara_terminal.bat` (`líneas 49-60`) ejecuta `ollama pull qwen3:4b` y `pip install pyttsx3`. | `install_dependencies.bat` instala todo `requirements.txt` sin mostrar versión, tamaño, licencia ni hash. | Sin pruebas de divulgación de recursos ni verificación SHA-256. | Ejecutar descargas o instalaciones desde el lanzador de inicio o sin mostrar fuente/versión/tamaño/licencia/hash incumple las reglas de descarga. | **Rehacer `iniciar_clara_terminal.bat`** (solo lectura, cero descargas), fijar `AUTO_DOWNLOADS_ENABLED = False` y añadir `OFFICIAL_RESOURCES`, `format_resource_disclosure` y `verify_resource_sha256`. |

---

## 4. Discrepancias Verificadas entre la Documentación y el Código Real

### En `CLARA_v1.27.4`
1. **Lectura en voz alta prometida para resúmenes matutinos y noticias vs. filtro real en `append_chat`:**
   - **Documentación (`README.md`):** indica que Clara lee en voz alta sus respuestas y el resumen matutino cuando la lectura automática está activada.
   - **Código real (`CLARA_v1.27.4/app.py`, línea 4503):** `append_chat` solo llama a `self._start_tts(message)` cuando `speaker.startswith("Asistente")`. Como `show_morning_briefing` publica con `speaker="Rutina matutina"` y `speaker="Clima y noticias"`, **ninguno de esos dos resúmenes era leído en voz alta ni podía repetirse con el botón de repetir**.
2. **Política de no descargar ni instalar recursos automáticamente vs. `iniciar_clara_terminal.bat`:**
   - **Documentación (`README.md`):** afirma que Clara no descarga ni instala componentes automáticamente.
   - **Código real (`CLARA_v1.27.4/iniciar_clara_terminal.bat`, líneas 49 y 58):** el script de inicio ejecuta `"%OLLAMA_EXE%" pull qwen3:4b` y `py -3 -m pip install pyttsx3` sin mostrar previamente la ficha completa de fuente oficial, versión, tamaño, licencia y hash.

### En `Bienvenido_Señor` (Viernes)
1. **Pruebas y módulos prometidos en la documentación que no existen en el repositorio:**
   - **Documentación (`docs/CHANGELOG_AGENT_SYSTEM.md` y `docs/NLU_IMPROVEMENT_PLAN.md`):** afirma que existen y pasan `tests/test_nlu.py`, `tests/test_vnext.py` y el módulo `jarvis_os_v5/core/safe_math.py`.
   - **Código real:** ninguno de esos archivos existe en `Bienvenido_Señor/`.
2. **Privacidad local prometida vs. envío de voz a Google y bases de datos personales en Git:**
   - **Documentación (`README.md`):** presenta el asistente como local y seguro.
   - **Código real:** `viernes_app/voice/speech_input.py` recurre a `recognizer.recognize_google(audio, language="es-MX")` (enviando audio a servidores de Google); `viernes_app/ui/gui.py` (`líneas 2075-2079`) pulsa el avatar tanto en mensajes del usuario como del asistente; y el repositorio incluye bases de datos e historiales reales (`viernes_data.db`, `data/activity.sqlite3`, `viernes_history.json`) y un `chat_id` de Telegram (`8028065392`) en `viernes_config.json`.

---

## 5. Plan de Preservación y Migración Reversible (Antes de Cualquier Cambio de Datos)

1. **Preservación 100 % intacta de la ubicación y datos de CLARA:**
   - La carpeta de datos del usuario en Windows (`%USERPROFILE%\AsistentePersonal\asistente.db`, `settings.json`, `virustotal_api_key.dpapi`) **se mantiene exactamente igual y sin modificaciones destructivas**.
   - `CLARA_Unificada` es 100 % compatible con el esquema SQLite existente de `CLARA_v1.27.4`, por lo que al abrir `CLARA_Unificada` el usuario conserva todas sus tareas, clases, excepciones escolares, bloques, rutinas, recuerdos y preferencias sin necesidad de migrar nada.
2. **Cero migración automática de Viernes y vista previa reversible de solo lectura:**
   - Los archivos JSON/SQLite dentro de `Bienvenido_Señor/` no se modifican ni se importan automáticamente.
   - Si en el futuro el usuario desea consultar qué tareas con fecha única de `Bienvenido_Señor/viernes_agenda.json` podrían llevarse a CLARA, cuenta con la función de **solo lectura** `preview_viernes_migration` (accesible desde *Copias de seguridad → `🔍 Vista previa migración Viernes (solo lectura)…`*), que:
     - realiza **0 escrituras (`writes_performed = 0`)** en `asistente.db`,
     - omite duplicados ya presentes en CLARA,
     - **omite todos los eventos recurrentes (`skipped_recurring`) para no inferir rutinas jamás**, y
     - muestra el horario de `viernes_config.json` únicamente como referencia informativa.
