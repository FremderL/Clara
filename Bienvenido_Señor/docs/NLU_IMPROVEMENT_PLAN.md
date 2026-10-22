# Plan de mejora NLU para Viernes

## Objetivo

Hacer que Viernes entienda frases naturales de alta frecuencia sin depender de
comandos exactos ni del fallback de IA local. La prioridad es ejecutar acciones
seguras y conocidas cuando la intencion sea clara, y dejar los casos ambiguos al
cerebro contextual, al router semantico o a Ollama.

## Arquitectura propuesta

1. Normalizacion unica de texto para intenciones.
   - Minusculas, acentos removidos y puntuacion limpia.
   - Evita que variantes como "solo", "solamente", "banie" o signos cambien la ruta.

2. Router NLU local de alta confianza.
   - Archivo: `viernes_app/core/nlu.py`.
   - Devuelve `IntentResult` con `intent`, `confidence`, `reason` y `slots`.
   - Solo debe capturar intenciones claras; si hay duda, retorna `None`.

3. Parsers especificos siguen ejecutando.
   - El NLU no reemplaza `_agenda_add_natural_command`, `_routine_command`,
     `_budget_command`, etc.
   - El NLU detecta la intencion y reutiliza esos handlers para hacer el trabajo.

4. Orden de resolucion recomendado.
   - Comandos criticos: detener, dialogos pendientes y comandos exactos.
   - Parsers especificos: voz, rutina, dia, agenda, recordatorios, clases.
   - NLU local: frases naturales claras.
   - Cerebro contextual y router semantico.
   - Ollama / investigacion web / mensaje de ayuda.

## Intenciones cubiertas ahora

- Ayuda/capacidades.
- Historial conversacional.
- Estado del dia y siguiente pendiente.
- Briefing matutino.
- Agenda completa y limpieza de eventos pasados.
- Clima, noticias y presupuesto.
- Estadisticas y recomendaciones de habitos.
- Clases de hoy, clases semanales y clases canceladas.
- Dia libre.
- Llegada, salida y bano terminado.
- Rutina, horario de salida y cambio temporal de salida.
- Estado de voz y despertar/residente.
- Abrir aplicaciones, calculos e investigacion.

## Reglas de seguridad semantica

- `horario de salida` nunca debe clasificarse como clases.
- `horario de hoy` puede seguir siendo clases si no menciona salida.
- Frases con `hoy` no deben secuestrarse por si solas; solo `hoy` exacto o
  patrones claros.
- Cambios de salida con `solo para hoy` se guardan como override diario, no como
  rutina semanal.

## Pruebas de regresion

Las pruebas estan en `tests/test_nlu.py` y cubren:

- Separacion entre horario de salida y horario de clases.
- Estados diarios: llegada, dia libre, clases canceladas.
- Acciones comunes: clima, abrir app, matematica, investigacion.
- Evitar capturas equivocadas con frases casuales que contienen `hoy`.

## Siguientes mejoras recomendadas

1. Hecho: agregar `slots` reales para tema de busqueda, app, fecha y hora.
2. Hecho: registrar telemetria anonima local de intenciones fallidas para mejorar reglas.
3. Hecho: convertir comandos frecuentes aprendidos en alias sugeridos.
4. Hecho: agregar pruebas de `process_command` con dobles de voz/estado.
5. Hecho: permitir confirmacion cuando una accion destructiva se detecte por NLU.

## Slots implementados

- `app`: nombre limpio de la app en comandos como `abre discord`.
- `query`: tema limpio para busqueda/investigacion.
- `expression`: expresion matematica sin prefijo conversacional.
- `time`: hora normalizada en formato `HH:MM`.
- `date_ref`: referencia textual como `hoy`, `manana` o una fecha escrita.
- `weekday`: dia de la semana mencionado.

## Telemetria NLU implementada

Cuando el NLU no captura una frase y el flujo termina en `brain`,
`semantic_router`, Ollama, auto-investigacion o el fallback final, Viernes guarda
una entrada local en `state["nlu_telemetry"]`.

La entrada no guarda el texto original. Guarda:

- `text_hash`: hash corto con sal local para deduplicar sin texto plano.
- `handled_by`: capa que resolvio o recibio el mensaje.
- `inferred_intent`: intencion inferida por la capa posterior, si existe.
- `char_count` y `token_count`.
- `signals`: etiquetas como `question`, `time`, `school`, `routine`, `webish`.

El historial se limita a 120 entradas y puede desactivarse con
`nlu_telemetry_enabled: false` en la configuracion.

## Alias sugeridos implementados

Viernes analiza `viernes_habits.json` y propone atajos para comandos repetidos
con `alias sugeridos`, `atajos sugeridos` o `comandos frecuentes`.

No crea alias automaticamente ni cambia comportamiento. Solo sugiere frases mas
cortas que ya encajan con comandos existentes, por ejemplo:

- `agenda viernes` para abreviar consultas repetidas de agenda de viernes.
- `historia` para abreviar `cuentame una historia`.
- `hoy` para abreviar `informe del dia`.

Se omiten eventos de monitoreo, saludos y confirmaciones que ya son cortas.

## Pruebas de `process_command` implementadas

Las pruebas construyen un asistente con dobles de voz, estado, historial y
persistencia para ejecutar `process_command` sin abrir GUI, microfono, monitor
ni archivos reales.

Cubren:

- Cambio temporal de salida por lenguaje natural.
- Uso de slots NLU en busquedas.
- Consulta de alias sugeridos con datos simulados.

## Confirmacion destructiva implementada

La limpieza de eventos pasados ya no elimina datos en el primer mensaje cuando
viene de lenguaje natural, por ejemplo `limpia eventos pasados`. Viernes crea un
dialogo pendiente `confirm_destructive` y pide una confirmacion explicita.

El mismo candado se aplica al comando directo `limpiar agenda` para mantener un
comportamiento consistente.

Flujo esperado:

- `limpia eventos pasados`: informa cuantos eventos se eliminarian y espera.
- `confirmar`: ejecuta la limpieza.
- `cancelar`: abandona la accion sin modificar la agenda.

Las pruebas de `process_command` validan que la agenda no cambia antes de
confirmar, que `confirmar` borra solo eventos pasados no recurrentes y que
`cancelar` conserva los datos.
