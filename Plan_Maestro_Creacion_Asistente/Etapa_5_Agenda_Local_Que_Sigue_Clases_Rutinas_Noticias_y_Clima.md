# Etapa 5 — Agenda Local, «¿Qué sigue?», Clases, Rutinas, Noticias y Clima con Caché Local

**Rama de trabajo:** `arena/e0545502-clara`  
**Estado:** Completada, auditada y verificada con pruebas unitarias (`41/41 OK`)  
**Archivos principales:** `CLARA_Unificada/app.py` y `CLARA_Unificada/tests/test_unified_clara.py`

---

## 1. Objetivo de la Etapa 5 y cumplimiento de restricciones

En la **Etapa 5** se unificó la organización escolar y personal 100 % local de *CLARA* con la capacidad de consulta operativa inmediata (*«¿Qué sigue?»*) y el resumen hablado de noticias y clima de *Viernes*, respetando estrictamente todos los límites de privacidad y operación local:

1. **Local-first para tareas, clases, rutinas y agenda; internet únicamente para noticias y clima:**
   - Toda la gestión de tareas (`tasks`), horario semanal (`classes`), excepciones escolares (`class_exceptions`), bloques de tiempo (`plan_blocks`), rutinas (`routines`), memoria (`memories`) y recordatorios (`reminder_events`, `reminder_actions`) opera sobre SQLite local sin tráfico de red.
   - Internet solo se utiliza bajo demanda explícita (botón `☀ Rutina de mañana` o consultas de noticias/clima) hacia Open-Meteo (`geocoding-api.open-meteo.com`, `api.open-meteo.com`) y los feeds RSS configurados (`Google News`, `BBC Mundo`, `DW Español`).
2. **Cálculo en tiempo real de «¿Qué sigue?» (`build_next_commitment_summary`, botón `⏭ ¿Qué sigue?`):**
   - Cruza el horario efectivo de clases de hoy (`classes_for_date` + `day_off_for`), los bloques locales (`plan_blocks`) y las tareas con o sin hora (`tasks`) para informar:
     - Qué clase o bloque está **en curso ahora mismo** (`start_time < ahora < end_time`).
     - Cuál es el **próximo compromiso con hora** y cuántos minutos/horas faltan.
     - Qué **tareas pendientes sin hora futura** quedan para hoy.
3. **Rutinas recurrentes sin inferencia silenciosa ni duplicados (`apply_routines`, `find_routine_pattern_candidates`, `toggle_task_completion`):**
   - Las rutinas nunca se infieren automáticamente; incluso el analizador opcional de patrones (`find_routine_pattern_candidates`) está desactivado por defecto (`pattern_suggestions = "false"`), exige 3 semanas distintas de coincidencias exactas en tareas manuales completadas y requiere confirmación individual para crear una rutina.
   - `apply_routines(day)` comprueba tanto `routine_id` como coincidencia de `(title, subject, due_date)` para no duplicar tareas aunque el usuario ya haya registrado manualmente la misma tarea hoy.
   - `toggle_task_completion` genera como máximo **una** ocurrencia futura pendiente por serie (`repeat_series_id`).
4. **Calendario 100 % local (`.ics`) sin conexión a proveedores externos:**
   - No se conecta ningún servicio externo de calendario (la preferencia `external_calendar_provider` permanece deshabilitada hasta que el usuario elija proveedor y autorice alcance).
   - `read_linked_ics_events` rechaza cualquier ruta remota (`http://`, `https://`, `webcal://`, `\\`) y archivos mayores de 5 MB; `parse_ical_events` ignora reglas de recurrencia (`RRULE`/`RECURRENCE-ID`) y eventos propios exportados por CLARA (`PRODID` con `ASISTENTE PERSONAL`).
5. **Noticias RSS seguras con limpieza HTML, validación de esquemas y caché local offline (`parse_news_feed`, `save_news_cache`, `load_news_cache`):**
   - Rechaza feeds XML mayores de 2 MB o que contengan `<!DOCTYPE` / `<!ENTITY` (protección contra XXE/Billion Laughs).
   - Limpia etiquetas HTML y entidades (`clean_rss_text`), acepta únicamente enlaces `http://` o `https://` y los muestra como texto sin abrirlos automáticamente.
   - Guarda los últimos titulares válidos en `%USERPROFILE%\AsistentePersonal\news_cache.json` y los presenta automáticamente como respaldo local si falla la conexión a internet.

---

## 2. Arquitectura e Implementación en `CLARA_Unificada/app.py`

### 2.1 «¿Qué sigue?» y Planificación de la Tarde (`build_next_commitment_summary`, líneas 1978–2047 y `build_afternoon_draft`, líneas 1138–1187)

- **`build_next_commitment_summary(db, now)`:**
  - Evalúa primero si hoy es día sin clases (`day_off_for(db, today)`).
  - Clasifica las clases (`classes_for_date`) y bloques (`plan_blocks`) en dos listas: `in_progress` (`start_time < now_hm < end_time`) y `upcoming` (`start_time >= now_hm`), y añade a `upcoming` las tareas pendientes con `due_date == hoy` y `due_time >= now_hm`.
  - Calcula el tiempo restante exacto (`comienza ahora mismo`, `en X min`, `en X h Y min`) para el compromiso más cercano y lista las tareas pendientes sin hora programada.
- **`build_afternoon_draft(db, target_day, now, limit=4)`:**
  - Propone hasta 4 bloques editables de 45 minutos entre las `13:00` y las `20:00` (con 15 minutos de descanso entre bloques), esquivando automáticamente todas las clases efectivas del día (`classes_for_date`) y los bloques ya guardados (`plan_blocks`).
  - **No escribe nada en SQLite** hasta que el usuario revisa y confirma la propuesta en ventana.

### 2.2 Horario Escolar y Excepciones de Una Sola Fecha (`classes_for_date` y `day_off_for`, líneas 1114–1136)

| Tipo de excepción (`action`) | Efecto sobre el día indicado (`exception_date`) | ¿Altera el horario semanal base (`classes`)? |
|---|---|---|
| `no_classes` (Día sin clases) | Oculta todas las clases semanales regulares de esa fecha (o rango de fechas con `inclusive_dates`). | No |
| `cancel` (Cancelar clase) | Omite únicamente la clase semanal seleccionada en esa fecha. | No |
| `override` (Cambiar clase) | Sustituye puntualmente hora de inicio/fin, aula o nombre de la clase semanal en esa fecha. | No |
| `extra` (Clase especial) | Añade una sesión puntual en esa fecha (incluso si el día general está marcado como `no_classes`). | No |

### 2.3 Rutinas y Tareas Recurrentes sin Duplicados (`apply_routines`, `toggle_task_completion`, `find_routine_pattern_candidates`)

1. **Bloqueo de rutinas duplicadas al guardar (`open_routines` → `save()`):**
   - Antes de insertar o actualizar una rutina en `routines`, verifica mediante consulta SQL insensible a mayúsculas/espacios que no exista otra rutina con el mismo `(title, subject, weekdays, reminder_time)`.
2. **Generación diaria idempotente (`apply_routines(day)`):**
   - Comprueba si ya existe en `tasks` para `due_date = day.isoformat()` una tarea con el mismo `routine_id` **o** con el mismo `(title, subject)`, evitando duplicar tareas si el usuario ya anotó manualmente esa actividad hoy o si abre la rutina matutina varias veces.
3. **Sucesor único en tareas con repetición (`toggle_task_completion`):**
   - Cuando se marca como hecha una tarea con `repeat_rule IN ('daily', 'weekly')`, verifica `SELECT 1 FROM tasks WHERE repeat_series_id=? AND done=0 AND id<>? AND due_date>? LIMIT 1`; solo si no hay ya una próxima ocurrencia pendiente inserta la siguiente fecha calculada por `next_repeat_date`.

### 2.4 Noticias RSS Seguras y Caché Local Offline (`parse_news_feed`, `save_news_cache`, `load_news_cache`, líneas 436–550)

```
[Solicitud explícita del usuario: Rutina matutina / Noticias]
       │
       ▼
[_fetch_news_text()] ──► Descarga RSS (máx. 2 MB + 1 byte, timeout 12 s)
       │
       ├── Si hay conexión y XML válido:
       │     1. parse_news_feed(): rechaza >2 MB y <!DOCTYPE / <!ENTITY
       │     2. clean_rss_text(): elimina HTML residual y decodifica entidades
       │     3. Filtra enlaces: solo admite http:// o https:// (nunca abre enlaces automáticamente)
       │     4. save_news_cache(): escritura atómica (.tmp -> news_cache.json)
       │
       └── Si falla la red:
             load_news_cache(max_age_hours=24.0): muestra los últimos titulares guardados localmente
```

---

## 3. Revisión de Errores y Mejoras Aplicadas en la Auditoría de la Etapa 5

Durante la auditoría de código de la Etapa 5 en `CLARA_Unificada/app.py`, se identificaron y aplicaron **3 mejoras de exactitud y seguridad**:

1. **Detección de clases y bloques «En curso ahora» en `build_next_commitment_summary`:**
   - *Problema previo:* `build_next_commitment_summary` filtraba únicamente `start_time >= now_hm`. Si el usuario consultaba `¿Qué sigue?` a las `10:20` durante una clase de `10:00` a `11:00`, esa clase en curso no aparecía en el resumen.
   - *Corrección:* Ahora detecta todo compromiso con `start_time < now_hm < end_time` y lo reporta explícitamente bajo `En curso ahora: ...` antes de mostrar el siguiente compromiso futuro (`Lo que sigue hoy (...)`).
2. **Prevención de duplicados cruzados entre tareas manuales y rutinas (`apply_routines` y `open_routines`):**
   - *Problema previo:* `apply_routines(day)` solo verificaba `WHERE routine_id=? AND due_date=?`. Si el usuario había creado manualmente hoy una tarea con el mismo título y materia antes de ejecutar la rutina matutina, `apply_routines` insertaba una segunda tarea idéntica; además, el diálogo de nueva rutina permitía guardar dos rutinas idénticas.
   - *Corrección:* `apply_routines` ahora comprueba también coincidencia por `(title, subject, due_date)` y el formulario de `open_routines` impide guardar una rutina idéntica a una ya existente.
3. **Filtrado de esquemas de URL en `parse_news_feed`:**
   - *Problema previo:* Aunque Clara nunca abre enlaces automáticamente, `parse_news_feed` aceptaba cualquier cadena dentro de `<link>`, lo que permitiría que un feed malformado incluyera esquemas como `javascript:` o `file://`.
   - *Corrección:* `parse_news_feed` valida que `raw_link.casefold().startswith(("https://", "http://"))` y descarta cualquier otro esquema antes de mostrarlo o guardarlo en `news_cache.json`.

---

## 4. Verificación Automatizada de la Etapa 5

Se ejecutaron `py_compile` y la suite completa de **41 pruebas unitarias** en `CLARA_Unificada/tests/test_unified_clara.py` (incluyendo las 9 pruebas de agenda/clases/rutinas/ICS/RSS y `test_etapa5_next_commitment_in_progress_apply_routines_dedupe_and_rss_scheme_filter`):

- `test_school_calendar_exceptions_resolve_without_changing_weekly_classes`: verifica días sin clases (`no_classes`), cancelaciones (`cancel`), cambios (`override`) y clases especiales (`extra`) sin mutar `classes`.
- `test_recurring_completion_creates_at_most_one_pending_successor`: verifica que completar/reabrir una tarea recurrente nunca duplica la serie pendiente.
- `test_afternoon_draft_avoids_classes_and_existing_blocks_without_writing_db`: verifica que la propuesta de la tarde esquiva clases y bloques ocupados sin escribir en SQLite.
- `test_ical_parser_skips_recurrences_and_own_exported_schedule_items` y `test_linked_ics_rejects_remote_paths_and_detects_local_conflicts`: verifican el calendario `.ics` 100 % local y el rechazo de URLs remotas.
- `test_rss_parser_enforces_xml_and_size_defenses` y `test_news_feed_html_cleaning_and_offline_cache_roundtrip`: verifican la defensa contra XML maliciosos, la limpieza HTML y el respaldo en `news_cache.json`.
- `test_etapa5_next_commitment_in_progress_apply_routines_dedupe_and_rss_scheme_filter`: verifica compromisos en curso + siguientes en `build_next_commitment_summary`, no duplicación en `apply_routines` y filtrado de esquemas en `parse_news_feed`.

```text
python3 -m py_compile CLARA_Unificada/app.py CLARA_Unificada/diagnosticar_voz.py CLARA_Unificada/tests/test_unified_clara.py
python3 -m unittest discover -s CLARA_Unificada/tests -p "test_*.py" -v
Ran 41 tests in 0.069s — OK
```
