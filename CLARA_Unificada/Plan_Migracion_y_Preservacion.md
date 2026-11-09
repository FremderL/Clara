# Plan de Preservación de Datos y Migración Opcional Reversible

**Estado:** Preservación estricta activa (ninguna migración destructiva ni automática se ejecuta sin autorización explícita).

---

## 1. Preservación intacta de los proyectos y datos actuales

1. **Proyectos originales intactos:**
   - La carpeta `CLARA_v1.27.4/` y la carpeta `Bienvenido_Señor/` (Viernes) se conservan **100 % intactas**, sin modificar, mover ni eliminar ninguno de sus archivos.
   - La nueva versión unificada vive en su propio directorio independiente: `CLARA_Unificada/`.
2. **Ubicación y compatibilidad de datos de CLARA (`%USERPROFILE%\AsistentePersonal`):**
   - Se conserva intacta la ubicación de datos de CLARA: `%USERPROFILE%\AsistentePersonal` (`asistente.db`, `settings.json` y, si existe, `virustotal_api_key.dpapi`).
   - `CLARA_Unificada` utiliza exactamente el mismo esquema SQLite (`tasks`, `classes`, `class_exceptions`, `routines`, `memories`, `security_events`, `action_events`, `chat_history`, `reminder_events`, `reminder_actions`, `plan_blocks`) y las mismas claves de `settings.json` que `CLARA_v1.27.4`.
   - **No se borra, reescribe ni altera ningún registro existente** al abrir `CLARA_Unificada`. Si decides volver a abrir `CLARA_v1.27.4`, tu base de datos y preferencias seguirán funcionando sin pérdida de compatibilidad.
   - La caché opcional de titulares para lectura sin conexión se guarda en un archivo separado (`%USERPROFILE%\AsistentePersonal\news_cache.json`), excluido de Git y de los respaldos ZIP para no romper la validación estricta de respaldos (`asistente.db` + `settings.json`).

---

## 2. Plan de migración opcional y reversible desde Viernes (`Bienvenido_Señor`)

**Importante:** `CLARA_Unificada` **NO importa ni migra automáticamente** datos desde `Bienvenido_Señor/viernes_agenda.json` ni `Bienvenido_Señor/viernes_config.json` para evitar crear duplicados, inferir rutinas o alterar tu base de datos de CLARA sin tu permiso.

Si en el futuro deseas trasladar eventos puntuales de Viernes a CLARA, el flujo diseñado es **explícito, de solo lectura en su vista previa y totalmente reversible**:

### Paso 1 — Vista previa sin escritura (`preview_viernes_migration`)
- Función incluida en `CLARA_Unificada/app.py`: `preview_viernes_migration(viernes_agenda_path, viernes_config_path, db)`.
- Lee únicamente en memoria `viernes_agenda.json` y `viernes_config.json` sin modificar ningún archivo de Viernes ni escribir en `asistente.db`.
- Clasifica qué elementos podrían importarse y cuáles se omiten por seguridad:
  - **Eventos con fecha de `viernes_agenda.json`:** se proponen como borradores de tareas locales (`title`, `due_date`, `due_time`), omitiendo los que ya existan en `asistente.db` (deduplicación por título + fecha + hora).
  - **Eventos recurrentes o rutinas de `viernes_config.json`:** **no se infieren ni se importan automáticamente como rutinas**, cumpliendo la regla *"No inferir rutinas ni crear duplicados silenciosamente"*; solo se listan en el reporte informativo para que elijas manualmente si deseas crear alguno.
  - **Clases de `viernes_config.json` (`class_schedule`):** como Viernes guarda solo nombres de materias sin hora de inicio (`"Ingles"`, `"Bases de datos"`), no se insertan a ciegas en la tabla `classes` (que requiere hora `HH:MM`); se muestran como lista informativa para que asignes su horario real en **Mis clases**.

### Paso 2 — Respaldo automático previo (Reversibilidad garantizada)
- Antes de aplicar cualquier importación aprobada por el usuario, se genera una copia de seguridad completa (`asistente.db` + `settings.json`) en:
  `%USERPROFILE%\AsistentePersonal\backups_before_restore\antes_de_migrar_viernes_YYYYMMDD_HHMMSS.zip`

### Paso 3 — Confirmación explícita e inserción transaccional
- Solo tras mostrar el resumen exacto y recibir confirmación explícita del usuario, se insertan únicamente las tareas fechadas seleccionadas dentro de una transacción `BEGIN IMMEDIATE ... COMMIT` marcada con `external_uid = 'viernes-migration-<id>'`.

### Paso 4 — Reversión en un paso
- Si deseas revertir la migración:
  1. Puedes restaurar el ZIP creado en `backups_before_restore` desde **Copias de seguridad → Restaurar respaldo…**, o bien
  2. Eliminar únicamente los registros con `external_uid LIKE 'viernes-migration-%'` sin tocar ninguna tarea creada en CLARA.
