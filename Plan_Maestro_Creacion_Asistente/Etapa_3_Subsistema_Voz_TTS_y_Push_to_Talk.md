# Etapa 3 — Subsistema de Voz Bidireccional Seguro (TTS en Español + Diagnóstico + Push-to-Talk Manual)

**Rama de trabajo:** `arena/e0545502-clara`  
**Estado:** Completada, auditada y verificada con pruebas unitarias (`39/39 OK`)  
**Archivos principales:** `CLARA_Unificada/app.py`, `CLARA_Unificada/diagnosticar_voz.py` y `CLARA_Unificada/tests/test_unified_clara.py`

---

## 1. Objetivo de la Etapa 3 y cumplimiento de restricciones

En la **Etapa 3** se construyó, auditó y blindó el subsistema completo de entrada y salida de voz local de **CLARA Unificada**, combinando la experiencia conversacional hablada de *Viernes* con los controles de privacidad, diagnóstico y parada de emergencia de *CLARA*:

1. **Lectura en voz alta de respuestas y resúmenes (`append_chat`, `show_morning_briefing`, `fetch_and_present_weather`, `fetch_and_present_news`):**
   - Cuando la preferencia `auto_speak_responses` está activa (`"true"` por defecto), el asistente lee en voz alta tanto las respuestas conversacionales de `Clara` como los resúmenes matutinos de agenda, clima y noticias (`speak_summary=True`).
   - La función `prepare_text_for_speech(text)` limpia las líneas `Enlace: https://...` y las URLs crudas antes de pasar el texto a `pyttsx3`, evitando que el sintetizador deletree direcciones web largas y manteniendo **100 % intactos** los enlaces y el formato en el chat escrito.
2. **Botón claro para repetir la última respuesta (`🔊 Repetir última respuesta` / `speak_last_response`):**
   - Visible siempre en la fila de controles del panel de conversación (`self.repeat_voice_button`), incluso en pantallas pequeñas o con escalado de Windows (125 %–150 %).
   - Almacena cada respuesta o resumen en `self.last_assistant_response` aunque la lectura automática esté desactivada, permitiendo escuchar o repetir bajo demanda la última intervención.
3. **Manejo explícito de fallos de voz conservando siempre el texto escrito (`explain_tts_failure` + `_report_tts_failure`):**
   - Si falta `pyttsx3`, si el sistema no reporta voces instaladas (`no_voices`) o si el motor de audio falla en tiempo de ejecución, Clara muestra una explicación clara en español con la causa y cómo solucionarlo, contrae la esfera a `"idle"` y **conserva íntegra la respuesta escrita** en el historial del chat.
4. **Diagnóstico de voz integrado y por CLI (`🩺 Diagnóstico de voz` / `collect_voice_diagnostics` / `diagnosticar_voz.py`):**
   - Verifica de forma 100 % local el estado de `pyttsx3`, las voces instaladas en el sistema, la voz en español seleccionada, la presencia de `vosk`, `sounddevice` y la carpeta `models/vosk-model-small-es-0.42`, además de mostrar las fichas de recursos opcionales verificados (`OFFICIAL_OPTIONAL_RESOURCES`).
   - **Nunca enciende el micrófono ni realiza conexiones a internet** durante el diagnóstico.
5. **Micrófono apagado por defecto y Push-to-Talk manual con transcripción editable (`toggle_voice`, `_voice_worker`, `process_ai_results`):**
   - La aplicación inicia siempre con `self.voice_active = False` y el indicador `"Micrófono apagado"`.
   - No existe ningún bucle de escucha continua ni palabra de activación (*wake word*).
   - El micrófono solo se abre cuando el usuario pulsa manualmente `🎙 Pulsar para hablar`, procesa bloques PCM a 16 kHz en memoria con `vosk.KaldiRecognizer` sin guardar audio en disco y, al detenerse, coloca la transcripción en la caja de texto editable (`self.chat_input`) con foco activo para que el usuario la revise o modifique antes de pulsar `Enviar`.
6. **Esfera visual reactiva solo al hablar (`set_sphere_state` / `animate_sphere`):**
   - La esfera central permanece en estado `"idle"` (radio base `0.78`) en reposo, mientras se escribe o mientras el usuario usa el micrófono, y pasa a `"speaking"` (expansión `1.07 + 0.10 * sin(...)` con ondas concéntricas) **únicamente** tras recibir el evento `"tts_started"` mientras el asistente habla.

---

## 2. Arquitectura e Implementación en `CLARA_Unificada/app.py` y `diagnosticar_voz.py`

### 2.1 Selección determinista de voz en español (`select_spanish_voice_id`, líneas 555–577)

```python
def select_spanish_voice_id(voices: list) -> str | None:
    """Return the best matching Spanish voice ID from a pyttsx3 voices list, or the first available voice."""
```
- Recorre las voces reportadas por `pyttsx3` (SAPI5 en Windows) inspeccionando `name`, `id` y `languages`.
- Aplica tres niveles de prioridad para elegir la mejor voz en español:
  1. Español de México: `es_mx`, `es-mx`, `mexico`, `méxico`, `sabina`, `dalia`, `raúl`, `raul`.
  2. Español de España: `es_es`, `es-es`, `spain`, `españa`, `helena`, `pablo`, `laura`.
  3. Cualquier variante de español: `spanish`, `español`, `espanol`, `es_`, `es-`.
- Si el sistema solo tiene voces en otro idioma, usa de respaldo la primera voz disponible; si no hay ninguna voz instalada, lanza `RuntimeError("no_voices")` para activar la explicación guiada.

### 2.2 Limpieza fonética sin alterar el texto escrito (`prepare_text_for_speech`, líneas 580–588)

```python
def prepare_text_for_speech(text: str) -> str:
    """Clean bullet symbols and raw URLs for natural Spanish TTS playback while keeping written chat links intact."""
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""
    cleaned = re.sub(r"(?im)^\s*Enlace:\s*https?://\S+\s*$", "", cleaned)
    cleaned = re.sub(r"https?://\S+", "enlace en pantalla", cleaned)
    cleaned = cleaned.replace("•", " ").replace("·", ", ")
    return re.sub(r"\s+", " ", cleaned).strip()
```
- Cuando Clara presenta un resumen de noticias (`fetch_and_present_news`), cada titular incluye `Enlace: https://...` en el chat para que el usuario pueda consultarlo.
- `prepare_text_for_speech()` retira las líneas `Enlace: https://...` y reemplaza cualquier URL en línea por `"enlace en pantalla"` exclusivamente en la cadena enviada a `engine.say(...)`, logrando una lectura fluida en español sin tocar el texto mostrado en `self.chat_log`.

### 2.3 Explicación ante fallos de TTS y conservación de la respuesta (`explain_tts_failure` y `_report_tts_failure`)

| Código / motivo detectado | Causa explicada al usuario | Solución propuesta en español | ¿Conserva respuesta escrita? |
|---|---|---|---|
| `no_pyttsx3` / `No module named 'pyttsx3'` | El paquete opcional `pyttsx3` no está instalado en este entorno Python. | Instalarlo manualmente con `instalar_voz.bat` o seguir usando Clara por texto. | Sí (`chat_log` intacto) |
| `no_voices` / `ninguna voz` | Windows o el sistema actual no reportó ninguna voz instalada para síntesis local. | En Windows, abrir *Configuración > Hora e idioma > Voz* e instalar *Español (México)* o *Español (España)*. | Sí (`chat_log` intacto) |
| Error del motor / audio ocupado | El motor de voz del sistema reportó un error o dispositivo de audio no disponible. | Abrir `🩺 Diagnóstico de voz` o ejecutar `diagnosticar_voz.bat` para revisar el audio y las voces instaladas. | Sí (`chat_log` intacto) |

### 2.4 Ciclo de vida seguro de TTS (`_start_tts`, líneas 4240–4312) y Parada de Emergencia

- Verifica que el micrófono no esté activo (`if self.voice_active:`) para no mezclar lectura sintética con la captura Push-to-Talk.
- Ejecuta `pyttsx3` en un hilo de trabajo (`daemon=True`) con bucle no bloqueante (`engine.startLoop(False)` + `engine.iterate()` cada `0.03 s`), permitiendo que el botón `DETENER AHORA` o la tecla `Esc` (`emergency_stop`) detengan la voz inmediatamente mediante `self.tts_cancel_event.set()`.
- Garantiza en el bloque `finally` que, si `loop_started` quedó activo tras una excepción intermedia, se invoque `engine.endLoop()` de forma segura y se liberen `self.current_tts_engine = None` y `self.tts_active = False`.

### 2.5 Push-to-Talk manual con transcripción editable (`toggle_voice`, `_voice_worker`, `process_ai_results`)

```
[Estado inicial: voice_active = False ("Micrófono apagado")]
       │
       ▼ (Usuario pulsa manualmente "🎙 Pulsar para hablar")
[toggle_voice()] ──► Verifica que TTS no esté hablando + presencia de vosk, sounddevice y modelo local
       │
       ▼
[_voice_worker()] ──► Captura PCM 16 kHz mono en RAM (sin guardar archivos .wav) hasta pulsar "■ Detener micrófono"
       │
       ▼
[process_ai_results(): "voice_transcript"]
       ├── Muestra en chat: "Transcripción para revisar: <texto>"
       ├── Coloca el texto en self.chat_input (delete + insert + focus_set)
       └── NO llama a send_chat(): el usuario revisa/edita el texto y pulsa "Enviar" cuando lo decide
```

---

## 3. Revisión de Errores y Mejoras Aplicadas en la Auditoría de la Etapa 3

Durante la inspección estática y funcional del subsistema de voz en `CLARA_Unificada/app.py`, se detectaron y corrigieron **3 mejoras clave de robustez**:

1. **Limpieza de URLs en lectura hablada de resúmenes (`prepare_text_for_speech`):**
   - *Problema previo:* Al leer en voz alta el resumen de noticias (`fetch_and_present_news`), las líneas `Enlace: https://...` se pasaban literalmente a `engine.say(text)`, provocando que SAPI5 deletreara URLs completas carácter por carácter.
   - *Corrección:* Se implementó `prepare_text_for_speech(text)` y se integró al inicio de `_start_tts`, manteniendo los enlaces completos en el chat escrito pero omitiéndolos de la locución hablada.
2. **Cierre garantizado del bucle de `pyttsx3` ante excepciones (`loop_started` en `finally`):**
   - *Problema previo:* Si ocurría una excepción dentro del bucle `while engine.isBusy()` después de `engine.startLoop(False)`, el hilo saltaba al bloque `except` sin ejecutar `engine.endLoop()`, lo que podía dejar el motor de `pyttsx3` bloqueado con `RuntimeError("run loop already started")` en intentos posteriores.
   - *Corrección:* Se añadió la bandera `loop_started` y un bloque `finally` defensivo que asegura la llamada a `engine.endLoop()` incluso si `iterate()` o `stop()` lanzan una excepción.
3. **Propagación del indicador `manual` en errores asíncronos de TTS (`("tts_error", (str(exc), manual))`):**
   - *Problema previo:* Si el usuario pulsaba manualmente `🔊 Repetir última respuesta` o `🔊 Probar frase en voz alta` (`manual=True`) y el fallo ocurría dentro del hilo de trabajo (por ejemplo, `no_voices`), el evento `"tts_error"` se procesaba siempre con `manual=False`.
   - *Corrección:* Ahora `"tts_error"` envía la tupla `(str(exc), manual)` y `process_ai_results` la desempaqueta para mostrar también el cuadro de aviso cuando la acción fue iniciada manualmente por el usuario.

---

## 4. Verificación Automatizada de la Etapa 3

Se ejecutaron la compilación estática, la herramienta CLI de diagnóstico en modo `--check-only` y la suite completa de **39 pruebas unitarias** (incluyendo las 5 pruebas dedicadas a voz y `test_etapa3_voice_subsystem_tts_repeat_failure_and_push_to_talk_editable_transcript`):

- `test_spanish_voice_selection_and_tts_failure_explanations`: verifica la selección prioritaria de voz en español (`es-MX` → `es-ES` → respaldo) y los mensajes explicativos de `explain_tts_failure`.
- `test_voice_diagnostics_static_never_activates_microphone`: comprueba que `collect_voice_diagnostics()` inspecciona `pyttsx3`, `vosk`, `sounddevice` y el modelo local con `microphone_activated == False` y sin abrir `sd.RawInputStream`.
- `test_sphere_expands_only_while_speaking`: comprueba que la esfera solo adopta el estado `"speaking"` (radio expandido `> 1.0`) mientras el asistente habla y permanece contraída (`0.78`) en reposo.
- `test_append_chat_speaks_responses_and_summaries_and_blocks_api_keys`: verifica que `append_chat` activa TTS para respuestas de `Clara` y resúmenes con `speak_summary=True` cuando `auto_speak_responses == "true"`, pero bloquea cualquier texto que contenga patrones de claves API.
- `test_etapa3_voice_subsystem_tts_repeat_failure_and_push_to_talk_editable_transcript`: verifica de extremo a extremo la limpieza fonética de URLs (`prepare_text_for_speech`), el fallo controlado de `speak_last_response` conservando la respuesta escrita y la colocación de la transcripción Push-to-Talk en `chat_input` de forma editable sin auto-envío.

```text
python3 -m py_compile CLARA_Unificada/app.py CLARA_Unificada/diagnosticar_voz.py CLARA_Unificada/tests/test_unified_clara.py
python3 -m unittest discover -s CLARA_Unificada/tests -p "test_*.py" -v
Ran 39 tests in 0.053s — OK
```
