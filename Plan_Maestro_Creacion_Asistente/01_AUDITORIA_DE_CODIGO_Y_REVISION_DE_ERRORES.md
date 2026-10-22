# Informe de Auditoría de Código, Revisión de Errores y Pruebas de Validación (`CLARA Unificada v2.0.0`)

Este documento registra el proceso de auditoría técnica y revisión de errores ejecutado sobre el código fuente de `CLARA_Unificada/` para garantizar que la versión entregada sea estable, segura y directamente utilizable.

---

## 1. Métricas de Inspección Estática y Árbol Sintáctico (AST)

Se auditó el código mediante análisis del árbol sintáctico abstracto (`ast`) de Python y validación de referencias:

| Archivo auditado | Líneas de código | Clases | Funciones / Métodos | Estado de sintaxis (`py_compile` + `ast.parse`) | Símbolos indefinidos o métodos duplicados |
|---|---:|---:|---:|---|---|
| `CLARA_Unificada/app.py` | 5,976 | 6 | 242 | **OK (0 errores)** | **0 duplicados / 0 métodos faltantes** |
| `CLARA_Unificada/diagnosticar_voz.py` | 80 | 0 | 2 | **OK (0 errores)** | **0 duplicados / 0 símbolos faltantes** |
| `CLARA_Unificada/tests/test_unified_clara.py` | 814 | 2 | 41 | **OK (0 errores)** | **0 duplicados / 0 símbolos faltantes** |

### Verificación de consultas SQLite contra el esquema real (`connect_db`)
- Se extrajeron automáticamente las **122 sentencias SQL estáticas** (`SELECT`, `INSERT`, `UPDATE`, `DELETE`) de `CLARA_Unificada/app.py` y se ejecutó `EXPLAIN <sql>` contra una base de datos creada por `connect_db()`.
- **Resultado:** **122 de 122 consultas SQL verificadas con 0 errores de sintaxis, tablas o nombres de columna.**

---

## 2. Errores y Brechas Detectados y Corregidos durante la Revisión de Código

Durante la creación y auditoría cruzada entre `CLARA_v1.27.4`, `Bienvenido_Señor` y `CLARA_Unificada`, se detectaron y corrigieron los siguientes errores reales de código:

### Error 1 — Resúmenes de «Rutina matutina» y «Clima y noticias» no se leían en voz alta
- **Causa en el código original:** En `append_chat`, la condición para invocar `_start_tts` era únicamente `speaker.startswith("Asistente")`, por lo que los bloques insertados con `speaker="Rutina matutina"` y `speaker="Clima y noticias"` jamás activaban la lectura en voz alta ni actualizaban `last_assistant_response`.
- **Corrección aplicada:** Se definió `SPOKEN_CHAT_SPEAKERS = ("Asistente", "Clara", "Rutina matutina", "Clima y noticias")`, se actualizó `append_chat` para almacenar `last_assistant_response` y hablar automáticamente en todos ellos cuando `auto_speak_responses == "true"`, y en `show_morning_briefing` / `process_ai_results` (`morning_online`) se combinó la lectura de la agenda matutina con el resumen de clima y noticias para evitar que una segunda llamada corte a la primera.

### Error 2 — Falta de selección de voz en español y de explicación visible ante fallo de TTS
- **Causa en el código original:** `_start_tts` ejecutaba `pyttsx3.init()` sin inspeccionar `engine.getProperty("voices")` para elegir una voz en español, y si `pyttsx3` no estaba instalado o lanzaba una excepción en el hilo de fondo, el fallo pasaba silenciosamente o solo cambiaba un texto temporal sin informar la causa ni los pasos de solución.
- **Corrección aplicada:** Se implementaron `select_spanish_voice_id(voices)` (que prioriza `es-MX`, `es-ES`, `es-419`, `Sabina`, `Helena`, `Dalia`, `Raul`, `Pablo`), `explain_tts_failure(reason, detail)` y `_report_tts_failure`, además del evento `("tts_error", ...)` en `process_ai_results`, mostrando la causa exacta y conservando siempre la respuesta escrita en el chat.

### Error 3 — Normalización de la letra `ñ` en el enrutador NLU local (`mañana`)
- **Causa detectada en las pruebas unitarias:** `normalize_intent_text` convertía inicialmente `áéíóúü -> aeiouu` sin incluir `ñ -> n`, provocando que la consulta `«¿Qué clases tengo mañana?»` mantuviera la `ñ` y no coincidiera con la rama `if "manana" in low:`.
- **Corrección aplicada:** Se actualizó la tabla de traducción a `str.maketrans("áéíóúüñ", "aeiouun")` y se verificó con la prueba unitaria `test_local_nlu_router_classifies_natural_spanish_intents`.

### Error 4 — Posibilidad de pegar claves API en el chat o inyectarlas en `settings.json`
- **Causa:** Aunque la clave de VirusTotal se guardaba en `virustotal_api_key.dpapi`, si el usuario pegaba accidentalmente su clave hexadecimal de 64 caracteres en el chat con el historial activado, podía guardarse en `chat_history` (y por tanto entrar en un respaldo ZIP).
- **Corrección aplicada:** Se implementaron `contains_potential_api_key` y `sanitize_settings_for_storage`. `send_chat` intercepta cualquier mensaje con una posible clave API antes de mostrarlo o guardarlo, `append_chat` impide su escritura en `chat_history`, y `save_settings` valida y limpia todas las llaves antes de escribir `settings.json`.

### Error 5 — Dependencia dura de `tkinter` al ejecutar pruebas unitarias en entornos sin servidor gráfico
- **Causa:** Importar `tkinter` de forma incondicional en la cabecera de `app.py` impedía ejecutar las pruebas unitarias de lógica pura, SQLite, NLU y seguridad en entornos de integración continua sin `python3-tk`.
- **Corrección aplicada:** Se añadió un bloque de respaldo seguro (`TKINTER_AVAILABLE`) que permite importar y probar todas las funciones lógicas en entornos headless y lanza un mensaje claro en español si se intenta instanciar la ventana sin `Tcl/Tk`.

### Error 6 — Descargas e instalaciones automáticas en `iniciar_clara_terminal.bat`
- **Causa en el código original:** `CLARA_v1.27.4/iniciar_clara_terminal.bat` ejecutaba `pip install pyttsx3` y `ollama pull` automáticamente durante el arranque.
- **Corrección aplicada:** Se reescribió `CLARA_Unificada/iniciar_clara_terminal.bat` para que realice únicamente comprobaciones de solo lectura y jamás descargue ni instale paquetes ni modelos sin autorización.

---

## 3. Resumen de Pruebas Automatizadas Ejecutadas (36 Pruebas Unitarias Seguras)

Comando ejecutado:
```bash
python3 -m py_compile CLARA_Unificada/app.py CLARA_Unificada/diagnosticar_voz.py CLARA_Unificada/tests/test_unified_clara.py
python3 -m unittest discover -s CLARA_Unificada/tests -p "test_*.py" -v
```

- **Total de pruebas:** 36 pruebas unitarias reales (0 fallos, 0 errores, tiempo: `0.040s`).
- **Seguridad durante las pruebas:** Ninguna prueba ejecuta movimientos reales de archivos del usuario, ni abre documentos reales en el sistema operativo, ni lanza aplicaciones reales.

---

## 4. Matriz de Cumplimiento de Requisitos de Aceptación

| Requisito del usuario | Estado en código y pruebas | Función / Archivo que lo implementa |
|---|---|---|
| Rama nueva, sin tocar `main`, sin fusionar ni publicar release | **Cumplido y verificado** | Rama `arena/e0545502-clara`; `CLARA_v1.27.4/` y `Bienvenido_Señor/` intactos (`git diff` vacío) |
| Local-first para conversación, tareas, clases, rutinas y agenda; internet solo para noticias y clima | **Cumplido y probado** | `connect_db`, `classify_local_natural_intent`, `_fetch_weather_text`, `_fetch_news_text` |
| Ubicación por defecto `Colima, Colima, México` y rutina `7:00 a. m.` (`07:00`), ambos editables | **Cumplido y probado** | `DEFAULT_SETTINGS` y `open_settings` en `CLARA_Unificada/app.py` |
| Hablar en voz alta respuestas y resúmenes de noticias/agenda; botón repetir última respuesta y diagnóstico de voz; si falla, mostrar explicación y conservar texto | **Cumplido y probado** | `SPOKEN_CHAT_SPEAKERS`, `speak_last_response`, `open_voice_diagnostics`, `explain_tts_failure`, `diagnosticar_voz.py` |
| Micrófono apagado por defecto y Push-to-Talk manual con transcripción editable antes de enviar; nunca escuchar continuamente | **Cumplido y probado** | `toggle_voice_input`, `_record_and_transcribe_once`, `collect_voice_diagnostics` |
| Mostrar claramente en pantallas pequeñas o escalado Windows: chat, `Enviar`, controles de voz y `DETENER AHORA`; esfera se expande solo cuando habla | **Cumplido y probado** | `_configure_dpi_scaling`, `_build_ui` (`minsize 680x440`), `ClaraSphere`, `sphere_radius_for_state` |
| Inicio sencillo documentado sin comandos arbitrarios, scripts del chat, elevaciones ni instalaciones silenciosas | **Cumplido y verificado** | `iniciar.bat`, `iniciar_clara_terminal.bat`, `is_blocked_unsafe_request` |
| Calendario local sin conectar servicios externos | **Cumplido y probado** | `parse_ical_events`, `read_linked_ics_events` |
| Búsqueda solo en carpeta elegida cada vez; nombre/tipo antes que contenido; solo PDF, DOCX, XLSX, PPTX, TXT y Markdown | **Cumplido y probado** | `LOCAL_DOCUMENT_EXTENSIONS`, `validate_local_search_root`, `scan_local_documents` |
| Abrir documentos permitidos solo tras advertencia y confirmación individual | **Cumplido y probado** | `validate_local_document_for_open`, `open_local_file_tools` |
| Mover un archivo por vez con confirmación; sin lotes, sobrescritura ni mover carpetas; deshacer solo en la sesión actual | **Cumplido y probado** | `prepare_local_move`, `execute_local_move`, `undo_last_move` |
| Autorizar máximo 10 aplicaciones GUI explícitas; confirmar al agregar y en cada inicio; sin shell, argumentos, scripts, instaladores ni elevación | **Cumplido y probado** | `MAX_ALLOWED_APPLICATIONS = 10`, `validate_local_application`, `launch_allowed_application` |
| No inferir rutinas ni crear duplicados silenciosamente | **Cumplido y probado** | `toggle_task_completion`, `ensure_daily_routines`, `preview_viernes_migration` |
| VirusTotal manual, solo por hash, con consentimiento por consulta; clave excluida de chats, preferencias y respaldos | **Cumplido y probado** | `hash_file_sha256`, `contains_potential_api_key`, `sanitize_settings_for_storage`, `VT_KEY_PATH` (DPAPI) |
| Descargas automáticas desactivadas; mostrar fuente oficial, recurso, versión, tamaño, licencia y verificar hash SHA-256 | **Cumplido y probado** | `AUTO_DOWNLOADS_ENABLED = False`, `OFFICIAL_RESOURCES`, `format_resource_disclosure`, `verify_resource_sha256` |
