# Etapa 4 — Interfaz Gráfica Adaptativa, Escalado Windows, Esfera Visual y Parada de Emergencia

**Rama de trabajo:** `arena/e0545502-clara`  
**Estado:** Completada, auditada y verificada con pruebas unitarias (`40/40 OK`)  
**Archivos principales:** `CLARA_Unificada/app.py` y `CLARA_Unificada/tests/test_unified_clara.py`

---

## 1. Objetivo de la Etapa 4 y cumplimiento de restricciones

En la **Etapa 4** se diseñó, auditó y blindó la interfaz gráfica principal de **CLARA Unificada** para garantizar que todos los controles críticos sean visibles y accesibles en cualquier resolución o escalado de Windows, que la esfera visual solo se expanda mientras el asistente habla y que la parada de emergencia sea inmediata y honesta sobre su alcance:

1. **Visibilidad garantizada en pantallas pequeñas y con escalado de Windows (100 %, 125 %, 150 %):**
   - El campo de entrada del chat (`self.chat_input`), el botón **`Enviar`** (`self.send_button`), los tres controles de voz (**`🎙 Pulsar para hablar`**, **`🔊 Repetir última respuesta`**, **`🩺 Diagnóstico de voz`**) y el botón **`⛔ DETENER AHORA · Esc`** (`self.stop_button`) permanecen siempre visibles dentro del área de trabajo útil.
   - Se declara conciencia de DPI del sistema en Windows (`SetProcessDpiAwareness(1)` / `SetProcessDPIAware()`) y se calculan dimensiones adaptativas mediante `compute_adaptive_window_geometry(screen_width, screen_height)`.
2. **Esfera visual reactiva exclusivamente al habla (`ClaraSphere` y `sphere_radius_for_state`):**
   - La esfera se mantiene compacta (`radius = 22.4 px` en el lienzo base de `150×112`, `is_expanded == False`) tanto en reposo (`"idle"`) como durante la captura manual de micrófono (`"listening"`).
   - Se expande (`radius = 32.48 px`, `is_expanded == True`, con rotación de órbitas y núcleo brillante `#d7ffff`) **únicamente** cuando `state == "speaking"`.
3. **Parada de emergencia accesible y honesta (`emergency_stop`, botón `⛔ DETENER AHORA · Esc` y tecla global `<Escape>`):**
   - Cancela de forma cooperativa la generación de Ollama (`self.cancel_event.set()` + cierre de `self.active_response`), apaga el micrófono (`self.voice_stop.set()`), detiene la síntesis de voz (`self.tts_cancel_event.set()`), señala cancelación a búsquedas locales de archivos (`self.local_scan_cancel_event.set()`), ignora resultados pendientes de VirusTotal (`self.vt_cancel_event.set()`) y devuelve la esfera a `"idle"`.
   - Informa con total transparencia que **no revierte tareas o datos ya guardados en SQLite**, **no retira peticiones ya enviadas a un servidor remoto** y que **una llamada bloqueante del sistema de archivos coopera con la cancelación y puede tardar un instante en ceder**.

---

## 2. Arquitectura e Implementación en `CLARA_Unificada/app.py`

### 2.1 Conciencia de DPI y Geometría Adaptativa (`compute_adaptive_window_geometry`, líneas 1315–1334 y `_apply_adaptive_geometry`)

```python
def compute_adaptive_window_geometry(screen_width: int, screen_height: int) -> dict[str, int | str]:
    """Compute safe window dimensions and minsize that fit small screens and 125%/150% Windows DPI scaling."""
    sw = max(680, int(screen_width or 1280))
    sh = max(440, int(screen_height or 820))
    min_w = min(680, max(560, sw - 40))
    min_h = min(440, max(380, sh - 60))
    width = min(1280, max(min_w, sw - 48))
    height = min(820, max(min_h, sh - 72))
    x = max(0, (sw - width) // 2)
    y = max(0, (sh - height) // 3)
    return {
        "width": width, "height": height, "x": x, "y": y,
        "min_width": min_w, "min_height": min_h,
        "geometry": f"{width}x{height}+{x}+{y}",
    }
```

| Escenario de pantalla / Escalado Windows | Resolución lógica (`sw × sh`) | Ventana calculada (`width × height`) | `minsize` aplicado | ¿Cabe sobre barra de tareas? |
|---|---|---|---|---|
| Monitor Full HD (1920×1080 @ 100 %) | `1920 × 1080` | `1280 × 820` | `680 × 440` | Sí (+260 px de margen vertical) |
| Laptop HD (1366×768 @ 100 %) | `1366 × 768` | `1280 × 696` | `680 × 440` | Sí (+72 px para barra de tareas) |
| Laptop HD con escalado 125 % (1366×768 @ 125 %) | `1092 × 614` | `1044 × 542` | `680 × 440` | Sí (+72 px para barra de tareas) |
| Laptop HD con escalado 150 % (1366×768 @ 150 %) | `910 × 512` | `862 × 440` | `680 × 440` | Sí (+72 px para barra de tareas) |

Además, en Windows (`sys.platform == "win32"`), tras configurar la geometría adaptativa de respaldo para el estado restaurado, se aplica `self.state("zoomed")` para aprovechar toda el área de trabajo desde el primer arranque.

### 2.2 Disposición anti-recorte del panel de chat y controles inferiores (`_build_ui`, líneas 2365–2458)

1. **Prioridad de empaquetado vertical en `root`:**
   - `header` (con el título y el botón rojo `⛔ DETENER AHORA · Esc`) y `toolbar` se empaquetan arriba (`side="top", fill="x"`).
   - `footer` se empaqueta **antes** que `body` con `footer.pack(side="bottom", fill="x", pady=(8, 0))` y `body.pack(side="top", fill="both", expand=True)`. Así, cuando la altura disponible disminuye, el algoritmo de empaquetado de Tkinter reduce únicamente `body` y jamás empuja los controles inferiores fuera de la ventana.
2. **Reserva de filas en el panel derecho (`right.grid_rowconfigure(4, weight=1, minsize=72)`):**
   - La fila `4` (`self.chat_log`) es la única con `weight=1` y tiene `height=3` como altura base mínima. En pantallas grandes se estira para ocupar todo el espacio libre; en pantallas pequeñas o al 150 % de escalado se comprime hasta 3 líneas para que las filas `5` a `8` (`voice_row`, `voice_status`, `chat_prompt_label`, `entry_row` con `self.chat_input` y `self.send_button`) permanezcan **siempre visibles**.
3. **Rejilla elástica de 3 columnas en `voice_row`:**
   - `voice_row.grid_columnconfigure((0, 1, 2), weight=1)` reparte equitativamente el ancho entre `🎙 Pulsar para hablar`, `🔊 Repetir última respuesta` y `🩺 Diagnóstico de voz` para evitar que el tercer botón quede truncado en ventanas estrechas.

### 2.3 Esfera Visual Reactiva (`sphere_radius_for_state` y `ClaraSphere`, líneas 1337–1418)

| Estado (`state`) | `is_expanded` | Radio (`150×112`) | Color del núcleo | Etiqueta en `sphere_state_label` |
|---|---|---|---|---|
| `"idle"` | `False` | `22.4 px` (compacta) | `#143b50` | `"En espera · esfera compacta"` |
| `"listening"` | `False` | `22.4 px` (compacta) | `#143b50` | `"Entrada manual activa · esfera compacta"` |
| `"speaking"` | `True` | `32.48 px` (expandida) | `#d7ffff` | `"Clara responde en voz · esfera expandida"` |

### 2.4 Parada de Emergencia (`emergency_stop`, líneas 5960–5995)

- **Accesibilidad:** Botón de alto contraste (`bg="#b42318"`, `fg="white"`, borde `#e05b62`) en la esquina superior derecha (`⛔ DETENER AHORA · Esc`) y atajo global `self.bind_all("<Escape>", lambda _event: self.emergency_stop())`.
- **Acciones que ejecuta de inmediato:**
  - `self.set_sphere_state("idle")` (contrae la esfera al instante).
  - Si `self.ai_busy`: activa `self.cancel_event.set()` y cierra el socket HTTP local (`self.active_response.close()`).
  - Si `self.voice_active`: activa `self.voice_stop.set()` para cerrar la captura de micrófono.
  - Si `self.tts_active`: activa `self.tts_cancel_event.set()` para detener el bucle `engine.iterate()` de `pyttsx3`.
  - Si `self.local_scan_cancel_event`: señala cancelación cooperativa al escaneo de documentos locales.
  - Si `self.vt_busy`: activa `self.vt_cancel_event.set()` para descartar el resultado pendiente de VirusTotal.
- **Honestidad operativa (mensaje en el chat):**
  > *"Detención solicitada. Se cancelan generación, micrófono, lectura de voz y búsqueda local activos, y se ignora el resultado de VirusTotal. La búsqueda coopera con la cancelación; una llamada bloqueante del sistema de archivos puede tardar. Una petición ya enviada no puede retirarse del servidor remoto y las tareas ya guardadas no se revierten."*

---

## 3. Revisión de Errores y Mejoras Aplicadas en la Auditoría de la Etapa 4

Durante la auditoría estática y de diseño responsivo de la Etapa 4 en `CLARA_Unificada/app.py`, se detectaron y corrigieron **4 detalles importantes**:

1. **Adaptación automática de geometría para pantallas con escalado 125 % / 150 % (`compute_adaptive_window_geometry`):**
   - *Problema previo:* `self.geometry("1280x820")` estaba fijado de forma estática; al restaurar la ventana en una pantalla 1366×768 con escalado de 125 % (`1092×614` px lógicos) o 150 % (`910×512` px lógicos), la ventana desbordaba verticalmente el área útil.
   - *Corrección:* Se implementó `compute_adaptive_window_geometry(sw, sh)` y `_apply_adaptive_geometry()`, ajustando automáticamente el tamaño inicial y el `minsize` dentro de la pantalla real.
2. **Empaquetado de `footer` con `side="bottom"` antes de `body` y reducción de altura mínima de `chat_log` (`height=3`):**
   - *Problema previo:* `footer` se empaquetaba después de `body` (`expand=True`) y `chat_log` exigía `height=8` líneas mínimas, lo que en alturas cercanas a `440–512 px` podía comprimir o desplazar la fila de entrada `entry_row` (`chat_input` y `Enviar`).
   - *Corrección:* `footer` se fijó con `side="bottom"` antes de `body`, y `chat_log` pasó a `height=3` con `right.grid_rowconfigure(4, weight=1, minsize=72)`.
3. **Distribución en rejilla elástica de los 3 botones de voz (`voice_row.grid_columnconfigure((0, 1, 2), weight=1)`):**
   - *Problema previo:* Con tres botones largos empaquetados con `pack(side="left")`, en anchos reducidos el botón `🩺 Diagnóstico de voz` podía recortarse por la derecha.
   - *Corrección:* Los tres botones se colocaron en columnas de peso igual (`sticky="ew"`), manteniéndose siempre visibles.
4. **Cancelación preventiva del temporizador de animación en `ClaraSphere.set_state`:**
   - *Problema previo:* Llamar a `set_state("speaking")` dos veces seguidas podía programar un segundo `after(65, self._tick)` sin cancelar el anterior.
   - *Corrección:* `set_state` cancela cualquier `self._animation_id` activo al inicio del método antes de iniciar o detener la animación.

---

## 4. Verificación Automatizada de la Etapa 4

Se ejecutaron `py_compile` y la suite completa de **40 pruebas unitarias** en `CLARA_Unificada/tests/test_unified_clara.py`, incluyendo `test_sphere_expands_only_while_speaking` y `test_etapa4_adaptive_geometry_sphere_states_and_honest_emergency_stop`:

```text
python3 -m py_compile CLARA_Unificada/app.py CLARA_Unificada/diagnosticar_voz.py CLARA_Unificada/tests/test_unified_clara.py
python3 -m unittest discover -s CLARA_Unificada/tests -p "test_*.py" -v
Ran 40 tests in 0.052s — OK
```
