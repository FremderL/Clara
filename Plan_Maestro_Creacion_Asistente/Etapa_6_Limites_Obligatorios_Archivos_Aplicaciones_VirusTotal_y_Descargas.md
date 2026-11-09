# Etapa 6 — Límites Obligatorios de Archivos, Aplicaciones GUI, VirusTotal y Descargas

**Rama de trabajo:** `arena/e0545502-clara`  
**Estado:** Completada, auditada y verificada con pruebas unitarias (`42/42 OK`)  
**Archivos principales:** `CLARA_Unificada/app.py` y `CLARA_Unificada/tests/test_unified_clara.py`

---

## 1. Objetivo de la Etapa 6 y cumplimiento de restricciones

En la **Etapa 6** se implementaron, auditaron y verificaron mediante pruebas automatizadas (sin ejecutar aperturas reales, movimientos reales ni aplicaciones reales) todos los límites obligatorios sobre el sistema de archivos, las aplicaciones locales, las consultas opcionales a VirusTotal y la política de descargas:

1. **Búsquedas e inventarios únicamente dentro de una carpeta elegida por el usuario cada vez (`validate_local_search_root`, `scan_local_documents`, `open_local_file_tools`):**
   - La carpeta raíz se solicita en cada operación con `filedialog.askdirectory(...)` y **jamás se persiste** en `settings.json` ni en SQLite.
   - Búsqueda exclusivamente por nombre y extensión; **nunca se indexa en segundo plano ni se lee el contenido de los archivos** para inventarios o búsquedas.
   - Se permiten únicamente 6 tipos de documento: **PDF (`.pdf`), DOCX (`.docx`), XLSX (`.xlsx`), PPTX (`.pptx`), TXT (`.txt`) y Markdown (`.md`, `.markdown`)** (`LOCAL_DOCUMENT_EXTENSIONS`). Se excluyen scripts, ejecutables, archivos ocultos/del sistema, enlaces simbólicos/junctions y carpetas de nube o del sistema.
2. **Apertura de documentos permitidos solo tras advertencia y confirmación individual (`validate_local_document_for_open`, `open_selected_document`):**
   - Muestra advertencia explícita con nombre, ruta relativa y tamaño antes de abrir con la asociación predeterminada de Windows (`os.startfile`).
   - Revalida identidad TOCTOU (`size`, `mtime_ns`, `file_id`, ausencia de symlinks/junctions en cada segmento de la ruta) antes y después de la confirmación.
3. **Movimiento de un solo archivo por vez, con confirmación, sin sobrescritura ni lotes, y deshacer en sesión (`prepare_local_move`, `execute_local_move`, `undo_last_move`):**
   - `prepare_local_move` y `execute_local_move` operan sobre **un único documento permitido por vez** (`selectmode="browse"`), dentro del mismo volumen local (`st_dev` y unidad idénticos), rechazando cualquier colisión (`os.path.lexists(destination)` → `FileExistsError`) y prohibiendo mover carpetas.
   - El botón **«Deshacer último movimiento»** utiliza `move_history` exclusivamente en la memoria de la sesión actual de la ventana y solo revierte el movimiento si el archivo sigue intacto (`size`, `mtime_ns`, `file_id`) y la ubicación original está libre.
4. **Etapa 7 de carpeta — Abrir carpeta existente en el Explorador (`validate_selected_folder`, `launch_selected_folder`, `open_selected_folder`):**
   - Limitada a abrir en el Explorador de Windows una carpeta local existente seleccionada y confirmada en cada ocasión, rechazando enlaces simbólicos, junctions y rutas de red UNC (`\\`), **sin leer, listar ni modificar su contenido**.
5. **Autorizar como máximo 10 aplicaciones GUI explícitas (`MAX_ALLOWED_APPLICATIONS = 10`, `validate_local_application`, `normalize_allowed_applications`, `launch_allowed_application`):**
   - Solo acepta ejecutables `.exe` con cabecera PE de subsistema gráfico (`subsystem == 2` en `is_windows_gui_executable`) ubicados bajo `Program Files`, `Program Files (x86)` o `LocalAppData\Programs`.
   - Bloquea consolas/intérpretes (`cmd.exe`, `powershell.exe`, `pwsh.exe`, `python.exe`, `wscript.exe`, `mshta.exe`, `rundll32.exe`, `regedit.exe`, etc.) e instaladores/actualizadores (`setup`, `installer`, `uninstall`, `updater`, `update`, `patch`).
   - Exige confirmación al añadir a la lista y confirmación individual en cada inicio, lanzando el proceso con `subprocess.Popen([current["path"]], shell=False, close_fds=True)` sin argumentos ni elevación.
6. **VirusTotal manual, hash-only, con consentimiento por consulta (`hash_file_sha256`, `virustotal_lookup`, `query_vt_file`):**
   - Calcula localmente el SHA-256 verificando que el archivo no cambie durante la lectura (`before == after`), pide consentimiento individual mostrando el hash exacto que se consultará y envía únicamente `GET https://www.virustotal.com/api/v3/files/{sha256}` sin redirecciones (`_NoRedirect`).
   - **Nunca sube archivos ni toma acciones automáticas** según el veredicto. La clave API se guarda cifrada con Windows DPAPI (`virustotal_api_key.dpapi`) y jamás entra en chats, preferencias ni respaldos.
7. **Descargas automáticas desactivadas y divulgación obligatoria (`AUTO_DOWNLOADS_ENABLED = False`, `OFFICIAL_RESOURCES`, `format_resource_disclosure`, `verify_resource_sha256`):**
   - Ninguna descarga automática ni silenciosa está permitida. Cada recurso opcional documentado muestra su fuente oficial, nombre del recurso, versión, tamaño, licencia y verificación SHA-256 (`verify_resource_sha256`).

---

## 2. Matriz de Controles y Barreras Técnicas en `CLARA_Unificada/app.py`

| Dominio | Función / Constante | Barrera técnica verificada en código |
|---|---|---|
| **Raíz de búsqueda local** | `validate_local_search_root` (líneas 1463–1512) | Rechaza raíces inexistentes, symlinks/junctions (tanto en la hoja como en cualquier ancestro léxico), carpetas ocultas/sistema (`0x2 \| 0x4 \| 0x400`), perfil completo (`%USERPROFILE%`), raíz de unidad (`C:\`), carpetas protegidas/nube (`Windows`, `Program Files`, `AppData`, `OneDrive`, `Dropbox`, `Google Drive`, `iCloud`) y unidades no fijas (`GetDriveTypeW != 3`). |
| **Escaneo / inventario** | `scan_local_documents` (líneas 1626–1720) | Usa `os.scandir` leyendo únicamente `entry.name` y `stat(follow_symlinks=False)`; filtra por `LOCAL_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".markdown"}`; aplica topes (`20,000` entradas, `5,000` resultados, `20 s`) y cancelación cooperativa (`cancel_event`). Jamás abre ni lee el contenido de ningún archivo. |
| **Apertura individual** | `validate_local_document_for_open` (líneas 1723–1764) | Comprueba pertenencia a `root_path`, ausencia de symlinks/junctions o carpetas protegidas intermedias, extensión permitida y coincidencia exacta de `st_size`, `st_mtime_ns` y `(st_dev, st_ino)` antes de `os.startfile`. |
| **Movimiento unitario y deshacer** | `prepare_local_move` / `execute_local_move` / `undo_last_move` (líneas 1515–1562, 2635–2706) | Un archivo por vez, mismo volumen (`st_dev` y unidad), fallo inmediato si `os.path.lexists(destination)` (`FileExistsError`), renombrado atómico `os.rename(source, destination)` y deshacer solo en memoria de la ventana actual (`move_history`) si el archivo no fue modificado. |
| **Abrir carpeta en Explorador** | `validate_selected_folder` / `launch_selected_folder` (líneas 843–866) | Rechaza cadena vacía, rutas de red UNC (`\\`), symlinks y junctions; pide confirmación explícita y abre la carpeta en el Explorador sin listar, leer ni modificar su contenido. |
| **Aplicaciones GUI (máx. 10)** | `is_windows_gui_executable` / `validate_local_application` / `launch_allowed_application` (líneas 1569–1623) | Tope duro `MAX_ALLOWED_APPLICATIONS = 10`; valida cabecera PE (`MZ` → `PE\0\0` → `subsystem == 2`); exige ubicación bajo `Program Files` o `LocalAppData\Programs`; rechaza `BLOCKED_APPLICATION_NAMES` e instaladores; ejecuta `subprocess.Popen([path], shell=False, close_fds=True)` sin argumentos. |
| **VirusTotal hash-only** | `hash_file_sha256` / `virustotal_lookup` (líneas 377–428) | Valida que `sha256` sea exactamente `[0-9a-fA-F]{64}`; usa `GET` sin cuerpo (`data=None`) y sin seguir redirecciones (`_NoRedirect`); pausa mínima de 16 s entre consultas; clave aislada en `VT_KEY_PATH` con DPAPI. |
| **Descargas y SHA-256** | `AUTO_DOWNLOADS_ENABLED = False` / `format_resource_disclosure` / `verify_resource_sha256` (líneas 69–118, 297–320) | `AUTO_DOWNLOADS_ENABLED` fijo en `False`; catálogo cerrado `OFFICIAL_RESOURCES` con fuente oficial, versión, tamaño y licencia; verificador `verify_resource_sha256(path, expected_sha256)`. |

---

## 3. Revisión de Errores y Mejoras Aplicadas en la Auditoría de la Etapa 6

Durante la auditoría de seguridad de la Etapa 6 en `CLARA_Unificada/app.py`, se aplicaron **3 refuerzos defensivos adicionales**:

1. **Bloqueo de enlaces simbólicos, junctions y rutas UNC en `validate_selected_folder`:**
   - *Problema previo:* `validate_selected_folder` llamaba directamente a `Path(path).resolve(strict=True)` sin comprobar antes si la carpeta seleccionada era un symlink, una junction de NTFS o una ruta de red UNC (`\\servidor\carpeta`).
   - *Corrección:* Ahora verifica que la ruta no esté vacía, que no comience con `\\` y que `candidate.is_symlink()` y `candidate.is_junction()` sean falsos antes de resolverla.
2. **Filtrado de nombres bloqueados y no-`.exe` al cargar `allowed_applications` (`normalize_allowed_applications`):**
   - *Problema previo:* Si alguien editaba manualmente `settings.json` en disco para inyectar `cmd.exe`, `powershell.exe`, un instalador (`setup.exe`) o un `.bat`, `normalize_allowed_applications` lo mantenía en la lista visible hasta que fallaba al pulsar *Iniciar*.
   - *Corrección:* `normalize_allowed_applications` ahora descarta de inmediato cualquier entrada cuya extensión no sea `.exe`, cuyo nombre esté en `BLOCKED_APPLICATION_NAMES` o cuyo nombre contenga tokens de instalador/actualizador (`setup`, `installer`, `uninstall`, `updater`, `update`, `patch`).
3. **Validación estricta de formato SHA-256 en `virustotal_lookup`:**
   - *Problema previo:* `virustotal_lookup(sha256, api_key)` interpolaba el parámetro `sha256` en la URL sin comprobar dentro de la propia función que fuera un hash hexadecimal de 64 caracteres.
   - *Corrección:* Se añadió `re.fullmatch(r"[0-9a-fA-F]{64}", sha256.strip())` al inicio de `virustotal_lookup`, garantizando por construcción que nunca pueda enviarse un nombre de archivo o ruta en la URL.

---

## 4. Verificación Automatizada de la Etapa 6 (Sin Efectos Secundarios Reales)

Todas las pruebas de la Etapa 6 se ejecutan en directorios temporales o con dobles de prueba (`mock.patch`), **sin mover archivos reales fuera de pruebas, sin abrir documentos reales (`os.startfile`) y sin lanzar aplicaciones reales (`subprocess.Popen`)**:

- `test_local_search_root_rejects_protected_or_hidden_paths`: verifica el rechazo de carpetas ocultas, symlinks, perfil completo y carpetas de nube/sistema.
- `test_local_document_scan_lists_only_allowed_metadata_and_respects_cancel`: verifica que solo se listan los 6 formatos permitidos sin leer contenidos y respetando `cancel_event`.
- `test_open_document_validation_checks_root_type_and_changes`: verifica la detección TOCTOU si el archivo cambia de tamaño, fecha de modificación o se convierte en symlink.
- `test_local_move_prepares_and_validates_without_executing_real_move`: verifica `prepare_local_move`, rechazo de sobrescritura (`FileExistsError`), rechazo de mismo directorio y bloqueo en plataformas no-Windows sin ejecutar movimientos reales.
- `test_selected_folder_validation_accepts_existing_dir_only`: verifica `validate_selected_folder`.
- `test_application_allowlist_accepts_only_gui_exe_under_standard_roots` y `test_normalize_allowed_applications_caps_and_deduplicates`: verifican la validación binaria PE (`subsystem == 2`), el tope de 10 apps y el rechazo de consolas/scripts/instaladores.
- `test_virustotal_hash_helper_and_pause_window`, `test_official_resource_disclosure_and_sha256_verification` y `test_etapa6_file_app_virustotal_and_download_guardrails_without_executing_side_effects`: verifican de extremo a extremo todas las defensas de la Etapa 6.

```text
python3 -m py_compile CLARA_Unificada/app.py CLARA_Unificada/diagnosticar_voz.py CLARA_Unificada/tests/test_unified_clara.py
python3 -m unittest discover -s CLARA_Unificada/tests -p "test_*.py" -v
Ran 42 tests in 0.064s — OK
```
