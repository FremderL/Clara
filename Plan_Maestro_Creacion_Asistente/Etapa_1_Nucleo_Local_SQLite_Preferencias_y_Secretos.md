# Etapa 1 — Núcleo Local-First, Esquema SQLite (11 Tablas), Preferencias Editables y Blindaje de Secretos/DPAPI

> **Estado de la Etapa 1:** **INICIADA, COMPLETADA, AUDITADA Y PROBADA (37/37 pruebas unitarias en verde)**  
> **Archivos principales:** `CLARA_Unificada/app.py`, `CLARA_Unificada/tests/test_unified_clara.py`, `.gitignore`  
> **Rama activa:** `arena/e0545502-clara` (`main`, `CLARA_v1.27.4/` y `Bienvenido_Señor/` permanecen intactos).

---

## 1. Objetivos Cumplidos en la Etapa 1

1. **Arquitectura 100 % Local-First y Preservación de Datos:**
   - Todos los datos de agenda, tareas, clases, excepciones escolares, bloques, rutinas, recuerdos, historial de acciones y preferencias residen localmente en `%USERPROFILE%\AsistentePersonal` (`DATA_DIR`).
   - El esquema de `asistente.db` (`DB_PATH`) conserva compatibilidad total con `CLARA_v1.27.4` sin migraciones destructivas ni pérdida de registros.
2. **Valores por Defecto Exactos y Editables (`DEFAULT_SETTINGS`):**
   - Ubicación por defecto del clima: **`"Colima, Colima, México"`**.
   - Hora por defecto de la rutina matutina: **`"07:00"`** (7:00 a. m.).
   - Lectura en voz alta automática: **`"true"`**.
   - Guardado opcional de historial de chat: **`"false"`** (desactivado por defecto).
   - Vínculo iCalendar local: **`""`** (sin conexiones a calendarios externos).
   - Descargas automáticas: **`AUTO_DOWNLOADS_ENABLED = False`**.
3. **Blindaje de Claves API, Preferencias y Respaldos:**
   - Las claves de VirusTotal se cifran exclusivamente con **Windows DPAPI** (`CryptProtectData` / `CryptUnprotectData`) en `virustotal_api_key.dpapi` (`VT_KEY_PATH`), separado de `settings.json` y de `asistente.db`.
   - `contains_potential_api_key(text)` detecta claves hexadecimales de 64 caracteres y patrones `api_key=...` / `token=...`.
   - `sanitize_settings_for_storage(settings)` filtra cualquier llave ajena a `DEFAULT_SETTINGS` y rechaza guardar cualquier preferencia que contenga una clave API.
   - `load_settings()` descarta valores manipulados manualmente en disco que contengan una clave API o formato de hora inválido, restableciendo el valor seguro por defecto.
   - `_write_backup()` y `export_backup()` declaran explícitamente que los archivos ZIP de respaldo **no están cifrados** y garantizan que `settings.json` dentro del ZIP pase por `sanitize_settings_for_storage` y que `virustotal_api_key.dpapi` quede excluido.
4. **Protección contra Subida de Datos Personales a GitHub (`.gitignore`):**
   - Exclusión estricta de `*.db`, `*.sqlite`, `*.sqlite3`, `*.dpapi`, `.env*`, `settings.json`, `news_cache.json`, `*.zip`, `models/`, `build/` y `dist/`.

---

## 2. Detalle Técnico de las 11 Tablas SQLite (`connect_db`)

La función `connect_db()` (`CLARA_Unificada/app.py`, líneas 860–1015) inicializa y migra de forma idempotente las **11 tablas locales**:

| # | Tabla | Propósito Local-First | Columnas e Índices Clave |
|---:|---|---|---|
| 1 | `tasks` | Tareas escolares/personales y recurrencia controlada | `id`, `title`, `description`, `due_date`, `due_time`, `priority`, `done`, `subject`, `routine_id`, `external_uid` (índice único parcial), `repeat_rule`, `repeat_series_id`, `completed_at` |
| 2 | `classes` | Horario semanal fijo de clases | `id`, `name`, `weekday` (0=Lunes..6=Domingo), `start_time`, `end_time`, `location`, `reminded_on` |
| 3 | `class_exceptions` | Excepciones del calendario escolar (sin tocar el horario base) | `id`, `exception_date` (indexado), `class_id`, `class_name`, `action` (`no_classes`, `cancel`, `override`, `extra`), `name`, `start_time`, `end_time`, `location`, `note` |
| 4 | `routines` | Rutinas configuradas manualmente por el usuario (nunca inferidas) | `id`, `title`, `subject`, `weekdays`, `reminder_time`, `active`, `created_at`, `source` |
| 5 | `plan_blocks` | Bloques de estudio/trabajo locales para organizar la tarde | `id`, `title`, `block_date`, `start_time`, `end_time`, `notes`, `created_at` (índice compuesto `block_date, start_time`) |
| 6 | `memories` | Notas/preferencias autorizadas manualmente con fecha de caducidad | `id`, `label`, `content`, `category`, `created_at`, `source`, `expires_on` |
| 7 | `reminder_events` | Estado del ciclo de vida de alertas locales | `alert_key` (PK), `source_type`, `source_id`, `title`, `due_at_local`, `state`, `snooze_until`, `next_notify_at`, `delivery_count` |
| 8 | `reminder_actions` | Bitácora auditable de avisos (`created`, `delivered`, `snoozed`, `dismissed`) | `id`, `alert_key`, `action`, `action_at`, `details` |
| 9 | `security_events` | Notas manuales de seguridad y resúmenes de consultas hash | `id`, `source`, `summary`, `created_at` |
| 10 | `action_events` | Historial de actividad local sin rutas ni nombres de archivo | `id`, `action`, `outcome`, `created_at` |
| 11 | `chat_history` | Historial opcional de conversación (desactivado por defecto) | `id`, `speaker`, `content`, `created_at` |

---

## 3. Funciones de Seguridad y Configuración Auditadas en la Etapa 1

1. **`load_settings()` y `save_settings(settings)` (`CLARA_Unificada/app.py`, líneas 233–305):**
   - Carga `settings.json` validando `morning_time` (`HH:MM`), `weather_location` (máx. 100 caracteres, por defecto `"Colima, Colima, México"`), `news_topic`, `news_source`, `news_count` y banderas booleanas.
   - Si algún campo en disco contiene una clave API (`contains_potential_api_key`), lo ignora y restaura el valor por defecto.
   - Al guardar, escribe primero en un archivo temporal (`settings.tmp`) con `sanitize_settings_for_storage(settings)` y reemplaza atómicamente `settings.json`.
2. **`contains_potential_api_key(text)` y `sanitize_settings_for_storage(settings)` (`CLARA_Unificada/app.py`, líneas 273–296):**
   - Impide que claves hexadecimales de 64 caracteres o tokens se guarden en preferencias, respaldos ZIP o en la tabla `chat_history`.
3. **Almacenamiento DPAPI (`save_vt_api_key`, `load_vt_api_key`, `delete_vt_api_key`) (`CLARA_Unificada/app.py`, líneas 335–405):**
   - Usa `CryptProtectData` y `CryptUnprotectData` de `Crypt32.dll` en Windows con `CRYPTPROTECT_UI_FORBIDDEN`.
4. **Extracción y exportación segura de respaldos (`extract_validated_backup`, `_write_backup`, `export_backup`) (`CLARA_Unificada/app.py`, líneas 186–231 y 3620–3655):**
   - Solo acepta los miembros `asistente.db` (máx. 256 MB) y `settings.json` (máx. 128 KB), bloqueando cualquier ruta `../` o archivo adicional en el ZIP.
5. **Vista previa reversible de Viernes (`preview_viernes_migration`) (`CLARA_Unificada/app.py`, líneas 625–700):**
   - Lee `viernes_agenda.json` y `viernes_config.json` en modo 100 % de solo lectura (`writes_performed = 0`), omite duplicados y omite eventos recurrentes (`skipped_recurring`) para no inferir rutinas jamás.

---

## 4. Pruebas Unitarias Ejecutadas para Validar la Etapa 1

Se ejecutaron las pruebas de compilación y unitarias (`CLARA_Unificada/tests/test_unified_clara.py`):

- `test_default_settings_colima_0700_and_auto_downloads_disabled` → **OK**
- `test_etapa1_connect_db_all_tables_and_settings_roundtrip_and_tamper_defense` → **OK**
- `test_api_key_leak_detection_and_settings_storage_rejection` → **OK**
- `test_append_chat_speaks_responses_and_summaries_and_blocks_api_keys` → **OK**
- `test_reminder_pause_expires_and_settings_never_load_api_key` / `test_virustotal_hash_helper_and_pause_window` → **OK**
- `test_backup_extractor_enforces_expected_members_and_size_limits` → **OK**
- `test_preview_viernes_migration_is_read_only_and_never_infers_routines` → **OK**

**Resultado global de la suite:** `Ran 37 tests in 0.066s — OK`.
