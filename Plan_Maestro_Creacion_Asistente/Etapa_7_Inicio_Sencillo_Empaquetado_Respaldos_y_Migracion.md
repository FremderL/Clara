# Etapa 7 — Inicio Sencillo, Empaquetado Opcional, Respaldos y Migración Reversible

**Rama de trabajo:** `arena/e0545502-clara`  
**Estado:** Completada, auditada y verificada con pruebas unitarias (`43/43 OK`)  
**Archivos principales:** `CLARA_Unificada/iniciar.bat`, `CLARA_Unificada/iniciar_clara_terminal.bat`, `CLARA_Unificada/programar_rutina.ps1`, `CLARA_Unificada/build_windows.bat`, `CLARA_Unificada/app.py` y `CLARA_Unificada/tests/test_unified_clara.py`

---

## 1. Objetivo de la Etapa 7 y cumplimiento de restricciones

En la **Etapa 7** se diseñaron, auditaron y verificaron los lanzadores de inicio rápido, las herramientas de programación de rutina en Windows, el constructor opcional portable y el sistema de respaldos y vista previa de migración reversible:

1. **Inicio sencillo con comando y lanzador documentados, sin ejecuciones ocultas ni instalaciones silenciosas (`iniciar.bat`, `iniciar_clara_terminal.bat`, `py -3 app.py`):**
   - Verifican únicamente la presencia de Python 3.10+ y Tkinter (`Tcl/Tk`) e inician `py -3 app.py`.
   - **No ejecutan comandos arbitrarios, ni scripts recibidos del chat, ni elevación de privilegios (`RunAs`), ni `pip install`, ni `ollama pull`, ni descargas en segundo plano.**
   - `iniciar_clara_terminal.bat` añade un resumen diagnóstico de 4 pasos de solo lectura (versión de Python, comprobación de lectura de `127.0.0.1:11434/api/tags`, presencia de `pyttsx3` sin encender el micrófono y apertura de la interfaz).
2. **Instaladores opcionales separados con consentimiento explícito (`instalar_voz.bat`, `instalar_opciones_windows.bat`, `build_windows.bat`):**
   - Muestran primero la ficha de cada recurso opcional (fuente oficial PyPI / Alpha Cephei, recurso, versión, tamaño aproximado y licencia) y exigen confirmación manual (`choice /c SN`) antes de ejecutar cualquier instalación.
3. **Programación de rutina matutina a las `07:00` editable (`programar_rutina.bat` / `programar_rutina.ps1` y `quitar_rutina.bat` / `quitar_rutina.ps1`):**
   - Lee `morning_time` desde `%USERPROFILE%\AsistentePersonal\settings.json` (con respaldo en `07:00`), valida el formato `HH:mm` y registra en el Programador de tareas de Windows `AsistentePersonal-Manana` (lunes a viernes) y `AsistentePersonal-Recordatorios` (cada 5 minutos con sesión iniciada), sin solicitar elevación de administrador.
4. **Respaldos locales sanitizados y restauración transaccional con respaldo previo automático (`_write_backup`, `export_backup`, `extract_validated_backup`, `import_backup`):**
   - Exportan exclusivamente `asistente.db` (mediante `sqlite3.Connection.backup`) y `settings.json` sanitizado con `sanitize_settings_for_storage`, advirtiendo explícitamente que el archivo ZIP **no está cifrado** y excluyendo siempre `virustotal_api_key.dpapi` y `news_cache.json`.
   - Al restaurar (`import_backup`), se bloquea la operación si hay IA, voz o escaneo activos, se valida el ZIP con `extract_validated_backup` (solo miembros permitidos y límites de tamaño), se verifica `PRAGMA integrity_check`, se sanitizan las preferencias importadas contra inyección de claves API y se guarda antes una copia automática en `%USERPROFILE%\AsistentePersonal\backups_before_restore\antes_de_restaurar_YYYYMMDD_HHMMSS.zip` con reversión automática (`rollback`) si algo falla.
5. **Preservación intacta de datos de CLARA y vista previa de migración reversible desde Viernes (`preview_viernes_migration`, `open_viernes_migration_preview`):**
   - La ubicación `%USERPROFILE%\AsistentePersonal` y los datos existentes de CLARA permanecen intactos sin migración automática.
   - `preview_viernes_migration` inspecciona `viernes_agenda.json` y `viernes_config.json` en modo **100 % solo lectura** (`writes_performed: 0`, `reversible: True`), omitiendo duplicados y descartando reglas recurrentes (`skipped_recurring`) para no inferir rutinas silenciosamente.

---

## 2. Catálogo de Lanzadores y Scripts de Windows en `CLARA_Unificada/`

| Script / Archivo | Función | ¿Descarga o instala paquetes? | ¿Pide confirmación manual (`choice /c SN`)? | ¿Requiere elevación UAC? |
|---|---|---|---|---|
| `iniciar.bat` | Lanzador principal directo (`py -3 app.py`) tras comprobar Python 3.10+ y Tkinter. | **No** | No aplica (solo inicia la app) | **No** |
| `iniciar_clara_terminal.bat` | Lanzador con consola informativa de 4 pasos (Python, Ollama opcional, TTS opcional, inicio). | **No** | No aplica (solo lectura + inicio) | **No** |
| `diagnosticar_voz.bat` | Ejecuta `py -3 diagnosticar_voz.py` sin encender el micrófono ni usar internet. | **No** | Sí, antes de emitir prueba audible | **No** |
| `probar_clara.bat` | Ejecuta `py_compile` y la suite completa de pruebas unitarias seguras (`unittest`). | **No** | No aplica (solo pruebas locales) | **No** |
| `programar_rutina.bat` / `.ps1` | Registra las 2 tareas del usuario actual en el Programador de tareas de Windows (`07:00` o `morning_time`). | **No** | Ejecución manual por el usuario | **No** |
| `quitar_rutina.bat` / `.ps1` | Elimina las 2 tareas programadas sin borrar la base de datos ni las preferencias. | **No** | Ejecución manual por el usuario | **No** |
| `instalar_voz.bat` | Instala manualmente `pyttsx3`, `vosk` y `sounddevice` desde PyPI tras mostrar fuente, versión, tamaño y licencia. | Sí (solo si el usuario elige `S`) | **Sí (`choice /c SN`)** | **No** |
| `instalar_opciones_windows.bat` | Instala manualmente `winotify`, `pystray` y `Pillow` desde PyPI tras mostrar fuente, versión, tamaño y licencia. | Sí (solo si el usuario elige `S`) | **Sí (`choice /c SN`)** | **No** |
| `build_windows.bat` | Construye opcionalmente el ejecutable portable `dist\Clara\Clara.exe` con PyInstaller tras pasar pruebas unitarias. | Sí (solo si el usuario elige `S`) | **Sí (`choice /c SN`)** | **No** |

---

## 3. Revisión de Errores y Mejoras Aplicadas en la Auditoría de la Etapa 7

Durante la auditoría de código de la Etapa 7 en `CLARA_Unificada/app.py` y los scripts `.bat`, se identificaron y corrigieron **4 detalles de seguridad y robustez**:

1. **Bloqueo de restauración mientras existan operaciones en segundo plano (`import_backup`):**
   - *Problema previo:* A diferencia de `erase_all_data()`, `import_backup()` no verificaba si `self.ai_busy`, `self.voice_active`, `self.tts_active`, `self.local_scan_running` o `self.vt_busy` estaban activos antes de cerrar `self.db` y reemplazar `asistente.db`.
   - *Corrección:* Se añadió al inicio de `import_backup()` la guardia explícita que impide iniciar una restauración mientras haya cualquier operación de IA, voz, escaneo o VirusTotal en curso.
2. **Sanitización contra claves API en `settings.json` dentro de respaldos importados (`import_backup`):**
   - *Problema previo:* `import_backup()` copiaba las cadenas de `raw_settings` de un archivo ZIP importado sin pasarlas antes por `sanitize_settings_for_storage`, por lo que un respaldo manipulado externamente requería esperar hasta `save_settings` para fallar.
   - *Corrección:* `import_backup()` aplica `sanitize_settings_for_storage` y valida todos los interruptores booleanos (`chat_history_enabled`, `native_notifications_enabled`, `minimize_to_tray`, `pattern_suggestions`, `auto_speak_responses`) antes de pedir confirmación de reemplazo.
3. **Creación garantizada de `DATA_DIR` antes de abrir directorios temporales en `_write_backup` e `import_backup`:**
   - *Problema previo:* `tempfile.TemporaryDirectory(dir=DATA_DIR)` asumía que `DATA_DIR` ya existía en disco; si la carpeta acababa de limpiarse, podía lanzar `FileNotFoundError`.
   - *Corrección:* Tanto `_write_backup` como `import_backup` ejecutan `DATA_DIR.mkdir(parents=True, exist_ok=True)` antes de crear el directorio temporal.
4. **Etiqueta explícita de `Licencia` en la divulgación previa de `build_windows.bat`:**
   - *Corrección:* Se uniformó el encabezado de divulgación en `build_windows.bat` para indicar explícitamente `fuente oficial PyPI, Version, Tamano y Licencia` junto al detalle de cada paquete de `requirements-build.txt`.

---

## 4. Verificación Automatizada de la Etapa 7

Se ejecutaron `py_compile` y la suite completa de **43 pruebas unitarias** en `CLARA_Unificada/tests/test_unified_clara.py` (incluyendo `test_backup_extractor_enforces_expected_members_and_size_limits`, `test_preview_viernes_migration_is_read_only_and_never_infers_routines` y `test_etapa7_launchers_backup_roundtrip_and_reversible_migration_preview`):

```text
python3 -m py_compile CLARA_Unificada/app.py CLARA_Unificada/diagnosticar_voz.py CLARA_Unificada/tests/test_unified_clara.py
python3 -m unittest discover -s CLARA_Unificada/tests -p "test_*.py" -v
Ran 43 tests in 0.089s — OK
```
