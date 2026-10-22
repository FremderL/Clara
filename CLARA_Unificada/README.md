# CLARA Unificada v2.0.0 — Centro Local de Asistencia, Rutinas y Agenda

**CLARA Unificada** combina la arquitectura local-first y los controles de seguridad de **CLARA v1.27.4** con las mejores capacidades operativas de **Viernes (`Bienvenido_Señor`)**: conversación natural en español sin depender de la nube, cálculo de **«¿Qué sigue?»** en el día, lectura en voz alta de respuestas y resúmenes de noticias/agenda, botón de repetición de última respuesta, diagnóstico local de voz y respaldo de titulares en caché cuando falla internet.

Los directorios originales `CLARA_v1.27.4/` y `Bienvenido_Señor/` permanecen **100 % intactos**, al igual que tus datos actuales en `%USERPROFILE%\AsistentePersonal`.

---

## 1. Inicio sencillo y documentado

### Opción A — Inicio directo (recomendado)
En Windows 10/11 con Python 3.10 o superior (con Tcl/Tk incluido), haz doble clic en:
```bat
iniciar.bat
```
o ejecuta desde una terminal dentro de `CLARA_Unificada`:
```powershell
py -3 app.py
```

### Opción B — Inicio con comprobación visual en terminal
Haz doble clic en:
```bat
iniciar_clara_terminal.bat
```
Comprueba Python, el estado local de Ollama (`127.0.0.1:11434`) y la disponibilidad de voz **sin realizar descargas automáticas, sin instalar paquetes silenciosamente, sin ejecutar scripts arbitrarios ni pedir elevación de administrador**.

---

## 2. Funciones principales (Local-First)

1. **Conversación natural local y con Ollama opcional:**
   - Aun con Ollama apagado o sin conexión a internet, puedes escribir en el chat:
     - `¿qué sigue?` / `siguiente pendiente` / `¿qué toca ahora?` (calcula la siguiente clase, bloque local o tarea del día y el tiempo restante).
     - `¿qué tengo hoy?` / `¿cómo va mi día?` / `¿qué tengo mañana?` / `agenda semanal`.
     - `mis clases` / `mis rutinas` / `ayuda`.
     - `me dejaron una tarea de Biología para mañana a las 16:00` (abre borrador editable; no guarda sin tu confirmación).
     - `reserva de 17:00 a 18:00 hoy para estudiar` o `ayúdame a organizar la tarde` (propone bloques locales de 45 min respetando clases y bloques existentes).
     - `busca mi PDF de biología` o `inventaría una carpeta` (abre la herramienta manual con el filtro precargado; tú eliges la carpeta raíz en cada ocasión).
     - `repite la última respuesta` o `diagnóstico de voz`.
   - Con **Ollama local** activo (`http://127.0.0.1:11434`), el modelo conversa y clasifica intenciones bajo un esquema JSON cerrado (`validate_chat_intent`). El modelo nunca ejecuta comandos ni recibe tus archivos ni tu lista de tareas automáticamente.
   - Las preguntas informativas (`¿cómo se mueve un archivo?`) y las negaciones (`no busques nada`, `no abras archivos`) nunca disparan acciones.

2. **Voz de salida (TTS), resúmenes hablados, repetición y diagnóstico:**
   - Cuando **«Leer automáticamente en voz alta las respuestas y resúmenes de noticias/agenda»** está activado en Preferencias (`true` por defecto), CLARA lee en voz alta tanto sus respuestas conversacionales como los resúmenes de **Rutina de mañana**, **Clima** y **Noticias**.
   - Selecciona automáticamente una voz en español (`es-MX` / `es-ES`) si está instalada en el sistema.
   - Incluye en la barra de voz:
     - **`🔊 Repetir última respuesta`**: vuelve a leer la última respuesta o resumen generado.
     - **`🩺 Diagnóstico de voz`**: revisa `pyttsx3`, voces instaladas, `vosk`, `sounddevice` y el modelo local sin encender el micrófono ni usar internet (también disponible ejecutando `diagnosticar_voz.bat`).
   - **Si la voz falla** (por falta de `pyttsx3`, falta de voz del sistema o error de audio), CLARA muestra una explicación clara de la causa y conserva siempre la respuesta escrita en el chat.

3. **Micrófono apagado por defecto y Push-to-Talk manual:**
   - El micrófono permanece **apagado por defecto**.
   - Solo escucha tras pulsar manualmente **`🎙 Pulsar para hablar`** y se detiene al volver a pulsarlo (o con **`⛔ DETENER AHORA · Esc`**).
   - **Nunca escucha continuamente** ni usa palabras de activación en segundo plano.
   - La transcripción se coloca en el campo de texto inferior para que puedas **revisarla y editarla antes de pulsar `Enviar`**.

4. **Interfaz clara en pantallas pequeñas o con escalado de Windows y esfera visual:**
   - Compatible con escalado DPI de Windows (100 %, 125 %, 150 %) y ventanas compactas (`minsize 680x440`).
   - El botón **`⛔ DETENER AHORA · Esc`**, los controles de voz, el campo de chat y el botón **`Enviar`** tienen filas reservadas para no quedar ocultos.
   - La **esfera visual (`ClaraSphere`)** permanece compacta en espera y durante la escucha manual, y **solo se expande mientras el asistente habla**.

5. **Noticias y clima (solo usan internet cuando los solicitas):**
   - Ubicación por defecto: **`Colima, Colima, México`** y hora de rutina matutina: **`07:00`** (7:00 a. m.), ambos editables en **Preferencias**.
   - Puedes consultarlos con el botón **`☀ Rutina de mañana`** o escribiendo `noticias` / `clima` en el chat.
   - Los titulares provienen únicamente de fuentes RSS curadas (`Google News México`, `BBC News Mundo`, `DW Español`), con límite de 2 MB y rechazo de `<!DOCTYPE` / `<!ENTITY`. Los enlaces se muestran como texto y nunca se abren automáticamente.
   - Si falla la conexión a internet, CLARA puede mostrar los últimos titulares guardados en la caché local (`news_cache.json`) indicando claramente la fecha de guardado.

6. **Calendario 100 % local:**
   - Tareas, clases semanales, excepciones escolares (vacaciones, cancelaciones, cambios, clases especiales) y bloques de estudio se guardan localmente en SQLite.
   - Soporta importación/exportación manual de archivos `.ics` locales y vinculación de un archivo `.ics` local en modo de solo lectura.
   - **No conecta servicios de calendario externos** (Google Calendar, Outlook, webcal) hasta que el usuario elija un proveedor y autorice el alcance.

---

## 3. Límites obligatorios de archivos, aplicaciones y seguridad

- **Búsqueda e inventario local:** solo dentro de la carpeta que elijas manualmente en cada operación; busca por nombre y tipo antes que contenido; nunca lee ni indexa el contenido de los archivos.
- **Formatos permitidos:** únicamente `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.txt`, `.md` y `.markdown`. Se excluyen scripts, ejecutables, enlaces simbólicos/junctions y carpetas ocultas o del sistema.
- **Abrir documentos permitidos:** requiere advertencia y confirmación individual por archivo, revalidando ruta, extensión, tamaño, `mtime_ns` e identidad del archivo antes de entregarlo a Windows.
- **Mover archivos:** un solo archivo permitido por vez, dentro del mismo volumen, con confirmación individual; sin lotes, sin sobrescritura y sin mover carpetas. Incluye botón **Deshacer último movimiento** válido únicamente durante la sesión abierta y si el archivo sigue intacto.
- **Aplicaciones GUI autorizadas:** máximo 10 ejecutables `.exe` gráficos bajo `Program Files` o `LocalAppData\Programs` (verificando cabecera PE `subsystem == 2` y bloqueando intérpretes, consolas e instaladores). Pide confirmación al autorizar y en cada inicio (`shell=False`, sin argumentos ni elevación). Autorizar una aplicación no garantiza que sea segura.
- **Etapa 7 (Explorador de Windows):** limitada exclusivamente a abrir en el Explorador una carpeta existente seleccionada y confirmada en cada ocasión, sin listar, leer ni modificar su contenido.
- **Rutinas:** nunca infiere rutinas ni crea duplicados silenciosamente.
- **VirusTotal (opcional):** consulta manual únicamente por hash SHA-256 con consentimiento explícito en cada consulta; nunca sube archivos ni toma acciones automáticas según el veredicto. La clave API se guarda cifrada con Windows DPAPI (`virustotal_api_key.dpapi`), queda excluida de preferencias y respaldos ZIP, y si intentas pegarla en el chat es bloqueada para no guardarla en el historial. Ninguna consulta garantiza detección perfecta de malware.
- **Parada de emergencia (`⛔ DETENER AHORA · Esc`):** cancela generación de Ollama, micrófono, lectura de voz y recorrido local activo, e ignora respuestas pendientes de VirusTotal. No revierte acciones ya guardadas ni detiene instantáneamente operaciones bloqueadas en el sistema operativo o aplicaciones externas ya abiertas.
- **Notificaciones programadas:** dependen del Programador de tareas de Windows y requieren una sesión de usuario iniciada.
- **Respaldos locales:** los archivos ZIP de respaldo (`asistente.db` + `settings.json`) **NO están cifrados** y excluyen la clave de VirusTotal.
