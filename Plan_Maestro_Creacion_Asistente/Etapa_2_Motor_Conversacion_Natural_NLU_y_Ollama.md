# Etapa 2 — Motor de Conversación Natural en Español (NLU Local Determinista + Integración Segura con Ollama bajo Esquema JSON Cerrado)

> **Estado de la Etapa 2:** **INICIADA, COMPLETADA, AUDITADA Y PROBADA (38/38 pruebas unitarias en verde)**  
> **Archivos principales:** `CLARA_Unificada/app.py`, `CLARA_Unificada/tests/test_unified_clara.py`  
> **Rama activa:** `arena/e0545502-clara` (`main`, `CLARA_v1.27.4/` y `Bienvenido_Señor/` permanecen intactos).

---

## 1. Objetivos Cumplidos en la Etapa 2

1. **Conversación Natural 100 % Local sin Depender de Ollama ni de Internet:**
   - Se unificó la cobertura de lenguaje natural de `NaturalLanguageRouter` (Viernes) con los borradores seguros de `CLARA_v1.27.4` dentro de `classify_local_natural_intent(text, today)` y `send_chat()`.
   - Incluso cuando Ollama está apagado o no instalado, el asistente entiende y resuelve en español consultas de agenda, *«¿qué sigue?»*, clases, rutinas, noticias por tema, clima, ayuda, repetición de voz, diagnóstico de voz, organización de la tarde, borradores de tareas/bloques y prellenado seguro de búsqueda/inventario de documentos.
2. **Defensas Semánticas contra Negaciones, Preguntas Informativas y Comandos Peligrosos:**
   - **Negaciones (`is_negated_or_informational_query`):** frases como *«no busques mi pdf»*, *«por favor no abras ningún archivo»* o *«no quiero que muevas documentos»* nunca abren ventanas de acción ni modifican datos; devuelven una confirmación informativa (`intent = "informational"`).
   - **Preguntas de ayuda o funcionamiento:** frases como *«¿cómo se mueve un archivo?»* o *«¿cómo busco documentos PDF?»* responden explicando el flujo manual seguro sin disparar la acción.
   - **Rechazo de peticiones inseguras (`is_blocked_unsafe_request`):** intentos de ejecutar `cmd`, `powershell`, `bash`, scripts (`.ps1`, `.bat`, `.cmd`, `.py`, `.vbs`), instaladores (`setup.exe`, `winget`, `msiexec`), apagar/reiniciar/bloquear el PC o buscar archivos ejecutables (`.exe`) son bloqueados de inmediato (`intent = "blocked_unsafe"`).
3. **Esquema JSON Cerrado para Ollama Local (`CHAT_INTENT_FIELDS` y `validate_chat_intent`):**
   - Cuando Ollama local (`http://127.0.0.1:11434/api/chat`) está conectado, el modelo actúa únicamente como clasificador conversacional bajo un esquema JSON cerrado de 17 intenciones.
   - El modelo **no recibe tu lista de tareas ni tus archivos**; únicamente recibe el prompt del sistema, los últimos turnos de la sesión y las memorias locales vigentes autorizadas manualmente (`active_memories_for`).
   - Ninguna intención devuelta por Ollama o por el NLU local guarda tareas, bloques ni toca archivos automáticamente: solo responde en lectura o abre el formulario/diálogo correspondiente para que el usuario revise y confirme.

---

## 2. Arquitectura del Enrutador Conversacional (`send_chat` → `classify_local_natural_intent` → `apply_chat_intent`)

### Orden de evaluación en `AssistantApp.send_chat()` (`CLARA_Unificada/app.py`, líneas 5785–5855)

```text
Mensaje del usuario en chat_input
  │
  ├─► 1. ¿Contiene una posible clave API / token (`contains_potential_api_key`)?
  │      └─► SÍ: Oculta el texto, NO lo guarda en SQLite (`persist=False`) y muestra advertencia de seguridad.
  │
  ├─► 2. ¿Coincide con una regla determinista (`classify_local_natural_intent`)?
  │      ├─► `blocked_unsafe`: Rechaza comandos de consola, scripts, instaladores, apagado de PC o `.exe`.
  │      ├─► `informational`: Responde a negaciones ("no busques...") o dudas ("¿cómo se mueve...?") sin actuar.
  │      ├─► `repeat_last` / `voice_diagnostics` / `help`: Ejecuta acción local de voz o muestra ayuda.
  │      ├─► `next_commitment`: Calcula y responde «¿Qué sigue?» hoy (`build_next_commitment_summary`).
  │      ├─► `morning_brief` / `news_query` / `weather_query`: Consulta rutina matutina, titulares RSS o clima.
  │      ├─► `classes_query` / `routines_query` / `week_agenda` / `agenda_query`: Resumen local de clases, rutinas o agenda.
  │      ├─► `afternoon_plan`: Abre propuesta revisable de bloques de 45 min (`start_afternoon_plan`).
  │      └─► `file_inventory` / `file_search` / `file_open` / `file_move`: Abre herramienta manual (el usuario elige carpeta raíz cada vez).
  │
  ├─► 3. ¿Es una propuesta de tarea (`parse_task_proposal`) o de bloque (`parse_block_request`)?
  │      └─► SÍ: Extrae título, materia, fecha relativa/explícita y hora, y abre el formulario prellenado SIN guardar automáticamente.
  │
  ├─► 4. ¿Es una consulta de agenda por día de la semana (`lunes`..`domingo`, `hoy`, `mañana`)?
  │      └─► SÍ: Muestra `day_agenda_summary(target)`.
  │
  └─► 5. ¿Hay un modelo de Ollama seleccionado en `model_var`?
         ├─► SÍ: Envía a `ask_ollama(text)` → valida salida con `validate_chat_intent(raw)` → aplica con `apply_chat_intent()`.
         └─► NO: Informa cómo conectar Ollama y recuerda todas las consultas locales disponibles sin conexión.
```

---

## 3. Catálogo de las 17 Intenciones Validadas (`CHAT_INTENT_FIELDS`)

| Intención | Campos permitidos en JSON | Acción en `apply_chat_intent` | ¿Modifica datos sin confirmación? |
|---|---|---|---|
| `general` | `{"intent", "response"}` | Muestra y lee en voz alta la respuesta en español | **No** |
| `clarify` | `{"intent", "question"}` | Formula pregunta breve de aclaración | **No** |
| `next_commitment` | `{"intent"}` | Calcula la próxima clase, bloque o tarea con hora de hoy y tiempo restante | **No (solo lectura)** |
| `morning_brief` | `{"intent"}` | Muestra y lee la rutina matutina local + clima + titulares | **No (solo lectura)** |
| `news_query` | `{"intent", "topic"}` | Consulta titulares RSS del tema (`General`, `Tecnología`, `Ciencia`, `Educación`, `Deportes` o `null`) o caché local | **No (solo lectura)** |
| `weather_query` | `{"intent"}` | Consulta clima actual para `weather_location` | **No (solo lectura)** |
| `classes_query` | `{"intent"}` o `{"intent", "date"}` | Muestra horario de clases del día `YYYY-MM-DD` o semanal completo | **No (solo lectura)** |
| `routines_query` | `{"intent"}` | Lista las rutinas manuales activas/pausadas | **No (solo lectura)** |
| `help` | `{"intent"}` | Muestra resumen de funciones y límites de seguridad | **No (solo lectura)** |
| `agenda_query` | `{"intent", "date"}` | Muestra clases, tareas, bloques y eventos `.ics` locales para `date` | **No (solo lectura)** |
| `afternoon_plan` | `{"intent"}` | Propone bloques de 45 min respetando clases y bloques existentes | **No (abre borrador)** |
| `task_draft` | `{"intent", "title", "subject", "due_date", "due_time", "description"}` | Abre formulario de nueva tarea con campos precargados | **No (requiere pulsar Guardar)** |
| `block_draft` | `{"intent", "title", "block_date", "start_time", "end_time", "notes"}` | Abre formulario de bloque local (`end_time > start_time`) | **No (requiere pulsar Guardar)** |
| `file_inventory` | `{"intent", "recursive"}` | Abre ventana de documentos en modo inventario; el usuario elige carpeta raíz | **No** |
| `file_search` | `{"intent", "query", "extension"}` | Precarga término (sin `/`, `\`, `..` ni `C:`) y extensión permitida; el usuario elige carpeta raíz | **No** |
| `file_open` | `{"intent", "query", "extension"}` | Igual que `file_search`; abrir exige selección y confirmación individual | **No** |
| `file_move` | `{"intent", "query", "extension"}` | Igual que `file_search`; mover exige carpeta destino y confirmación individual | **No** |

*(Además, el enrutador local maneja internamente `repeat_last`, `voice_diagnostics`, `week_agenda`, `informational` y `blocked_unsafe`).*

---

## 4. Revisión de Errores de Código Aplicada en la Etapa 2

1. **Unificación del esquema `classes_query` entre el NLU local y `validate_chat_intent`:**
   - Se detectó que `classify_local_natural_intent` devolvía `{"intent": "classes_query", "date": target}` mientras que `CHAT_INTENT_FIELDS["classes_query"]` solo admitía `{"intent"}`.
   - **Corrección:** `validate_chat_intent` ahora acepta `{"intent": "classes_query"}` y `{"intent": "classes_query", "date": "YYYY-MM-DD" | null}` validando la fecha con `_chat_iso_date`.
2. **Bloqueo explícito de secuencias `..` en términos de búsqueda de archivos:**
   - Tanto `validate_chat_intent` como `_extract_file_query_and_extension` rechazan explícitamente cualquier `query` que contenga `".."`, `"/"`, `"\\"` o prefijos de unidad (`C:`).
3. **Sincronización del `system_prompt` de `ask_ollama`:**
   - Se añadieron al prompt del sistema de Ollama las intenciones de solo lectura (`next_commitment`, `morning_brief`, `news_query`, `weather_query`, `classes_query`, `routines_query`, `help`) para que el modelo local también pueda invocarlas dentro del esquema cerrado.

---

## 5. Pruebas Unitarias Ejecutadas para Validar la Etapa 2

Se ejecutaron las pruebas de compilación y unitarias (`CLARA_Unificada/tests/test_unified_clara.py`):

- `test_local_nlu_router_classifies_natural_spanish_intents` → **OK**
- `test_local_nlu_router_rejects_negations_informational_and_unsafe_commands` → **OK**
- `test_chat_intent_validator_enforces_closed_schema_and_safe_queries` → **OK**
- `test_validate_chat_intent_supports_unified_intents_and_rejects_invalid_topics` → **OK**
- `test_task_proposal_extracts_spanish_date_time_and_subject_without_saving` → **OK**
- `test_task_proposal_supports_relative_days_and_next_same_weekday` → **OK**
- `test_etapa2_apply_chat_intent_and_send_chat_local_and_ollama_flows` → **OK**

**Resultado global de la suite:** `Ran 38 tests in 0.059s — OK`.
