# Lista de Aceptación Manual en Windows — CLARA Unificada v2.0.0

> **Importante antes de empezar:**
> - Realiza estas pruebas manuales en Windows 10/11 usando **datos ficticios** (archivos de prueba `.txt`/`.pdf` sin información sensible).
> - Para las pruebas de **restauración y eliminación total de datos (Sección 8)**, utiliza **una cuenta de usuario de Windows de prueba** o respalda primero tu carpeta `%USERPROFILE%\AsistentePersonal` en otra ubicación segura.

---

## 1. Interfaz, escalado de Windows y esfera visual

- [ ] **Inicio sencillo:** ejecuta `iniciar.bat`. Verifica que la ventana abre sin pedir permisos de administrador ni descargar paquetes en segundo plano.
- [ ] **Visibilidad en pantallas pequeñas y escalado (100 %, 125 %, 150 %):**
  - Redimensiona la ventana hasta su tamaño mínimo (`680x440`) y prueba con escalado de pantalla de Windows al 125 % o 150 %.
  - Verifica que siguen visibles y accesibles:
    1. El botón rojo **`⛔ DETENER AHORA · Esc`** arriba a la derecha.
    2. Los botones de voz: **`🎙 Pulsar para hablar`**, **`🔊 Repetir última respuesta`** y **`🩺 Diagnóstico de voz`**.
    3. El campo de entrada de chat inferior y el botón **`Enviar`**.
- [ ] **Comportamiento de la esfera visual (`ClaraSphere`):**
  - En reposo: verifica que la etiqueta indica `En espera · esfera compacta` y la esfera no se expande.
  - Durante captura manual de micrófono (`🎙 Pulsar para hablar`): verifica que la etiqueta indica `Entrada manual activa · esfera compacta` y la esfera **no se expande**.
  - Durante lectura en voz alta: verifica que la esfera **se expande y anima únicamente mientras Clara habla**, y vuelve al estado compacto al terminar o al pulsar `DETENER AHORA · Esc`.

---

## 2. Voz: respuestas habladas, resúmenes, repetición, diagnóstico y Push-to-Talk

- [ ] **Diagnóstico de voz sin micrófono ni internet:**
  - Pulsa **`🩺 Diagnóstico de voz`** (y prueba también `diagnosticar_voz.bat`).
  - Verifica que informa el estado de `pyttsx3`, las voces instaladas (indicando cuál voz en español se seleccionó), `vosk`, `sounddevice` y la carpeta `models/vosk-model-small-es-0.42`, confirmando que el micrófono sigue apagado.
- [ ] **Lectura automática de respuestas y resúmenes:**
  - Con `Leer automáticamente en voz alta las respuestas y resúmenes de noticias/agenda` activado en **Preferencias**, envía `¿qué sigue?` o pulsa **`☀ Rutina de mañana`**.
  - Verifica que Clara lee en voz alta tanto la respuesta del chat como el resumen de agenda, clima y noticias.
- [ ] **Botón `🔊 Repetir última respuesta`:**
  - Pulsa **`🔊 Repetir última respuesta`** o escribe `repite la última respuesta`.
  - Verifica que vuelve a leer el último mensaje o resumen generado.
- [ ] **Fallo controlado de voz:**
  - En un entorno sin `pyttsx3` o sin voces de sistema, envía un mensaje al chat y pulsa `🔊 Repetir última respuesta`.
  - Verifica que Clara muestra el aviso explicando por qué falló la voz y **conserva íntegra la respuesta escrita** en el chat.
- [ ] **Push-to-Talk manual y transcripción editable:**
  - Verifica que al abrir la app el estado dice `Micrófono apagado`.
  - Pulsa **`🎙 Pulsar para hablar`**, di una frase corta y pulsa **`■ Detener micrófono`**.
  - Verifica que el texto aparece en el campo de entrada inferior para que puedas **editarlo manualmente** y que **no se envía solo** hasta que pulses **`Enviar`**.

---

## 3. Conversación natural (sin Ollama y con Ollama local)

- [ ] **Consultas naturales sin Ollama (modo 100 % local):**
  - Con Ollama cerrado, prueba en el chat:
    - `¿qué sigue?` → muestra el próximo compromiso de hoy (clase, bloque o tarea con hora) y el tiempo restante.
    - `¿qué tengo hoy?` y `¿qué tengo mañana?` → muestra el resumen diario.
    - `mis clases` y `mis rutinas` → lista tu horario y rutinas manuales.
    - `me dejaron una tarea de Química para mañana a las 18:00` → abre el formulario de tarea con los datos precargados sin guardar automáticamente.
    - `ayúdame a organizar la tarde` → abre el borrador de bloques de 45 min sin guardar sin confirmación.
    - `no busques archivos` y `¿cómo se mueve un archivo?` → responde informativamente sin abrir ventanas de archivos ni ejecutar acciones.
    - `ejecuta cmd.exe` o `corre un script powershell` → rechaza la acción explicando el límite de seguridad.
- [ ] **Con Ollama local conectado:**
  - Inicia Ollama con un modelo local (p. ej. `qwen3:4b`), pulsa **`Detectar Ollama`** y conversa libremente.
  - Verifica que durante una respuesta larga, pulsar **`⛔ DETENER AHORA · Esc`** interrumpe la generación.

---

## 4. Ubicación por defecto, rutina de 7:00 a. m., noticias y clima

- [ ] **Valores por defecto editables:**
  - Abre **Preferencias** en una instalación limpia y verifica que la hora es **`07:00`** y la ubicación es **`Colima, Colima, México`**, y que ambos campos se pueden editar y guardar.
- [ ] **Consulta de noticias y clima:**
  - Pulsa **`☀ Rutina de mañana`** o escribe `noticias` / `clima` en el chat.
  - Verifica que muestra el clima de la ubicación configurada y los titulares con fuente y enlace visible **sin abrir automáticamente el navegador**.
- [ ] **Respaldo sin conexión (caché local):**
  - Desconecta internet tras haber consultado noticias una vez y vuelve a escribir `noticias`.
  - Verifica que muestra los titulares guardados localmente indicando la fecha de la caché.

---

## 5. Búsqueda e inventario de documentos (Etapa 8)

- [ ] **Elección de carpeta en cada operación:**
  - Abre **Buscar documentos / ver carpeta** y pulsa **Buscar documentos…**.
  - Verifica que pide elegir carpeta raíz cada vez y rechaza raíces prohibidas (`C:\`, perfil completo, `Windows`, `Program Files`, `AppData`, `OneDrive`, unidades USB/red o enlaces simbólicos).
- [ ] **Formatos permitidos y exclusión de ejecutables/scripts:**
  - En una carpeta de prueba que contenga archivos `.pdf`, `.docx`, `.xlsx`, `.pptx`, `.txt`, `.md` junto con `.exe`, `.bat`, `.ps1` y `.py`, ejecuta una búsqueda o inventario.
  - Verifica que solo aparecen los 6 formatos de documento permitidos y sus metadatos (sin leer contenido).

---

## 6. Apertura y movimiento individual de documentos (Etapas 9 y 10 + Etapa 7)

- [ ] **Abrir documento permitido (Etapa 9):**
  - Selecciona un documento `.txt` o `.pdf` de prueba en los resultados y pulsa **Abrir seleccionado…**.
  - Verifica que muestra una advertencia individual con nombre, ubicación relativa y tamaño, y solo lo abre tras confirmar.
  - Modifica el archivo desde fuera antes de confirmar y verifica que detecta el cambio y bloquea la apertura.
- [ ] **Mover un archivo por vez y Deshacer en sesión (Etapa 10):**
  - Selecciona un archivo de prueba y pulsa **Mover seleccionado…**.
  - Elige una carpeta destino en el mismo disco donde ya exista un archivo con el mismo nombre: verifica que **rechaza sobrescribir**.
  - Elige una carpeta destino limpia en el mismo disco y confirma: verifica que mueve **ese único archivo**.
  - Pulsa **Deshacer último movimiento** en la misma ventana y confirma: verifica que el archivo regresa a su carpeta original.
  - Cierra la ventana y vuelve a abrirla: verifica que el botón de deshacer aparece deshabilitado (solo dura la sesión de la ventana).
- [ ] **Etapa 7 (Abrir carpeta en Explorador):**
  - En **Seguridad → Elegir y abrir carpeta…**, selecciona una carpeta y confirma: verifica que se abre en el Explorador de Windows sin listar ni tocar sus archivos.

---

## 7. Aplicaciones GUI autorizadas (Etapa 11) y VirusTotal (Etapa 6)

- [ ] **Aplicaciones GUI autorizadas (máximo 10):**
  - Abre **Aplicaciones autorizadas → Añadir .exe autorizado…**.
  - Intenta añadir `cmd.exe`, `powershell.exe`, `python.exe`, un instalador (`setup.exe`) o un `.exe` fuera de `Program Files` / `LocalAppData\Programs`: verifica que son rechazados.
  - Añade una aplicación GUI válida bajo `Program Files` (confirmando al añadir) y pulsa **Iniciar…** (confirmando de nuevo): verifica que se lanza sin argumentos ni consola.
- [ ] **VirusTotal manual por hash (Etapa 6):**
  - En **Seguridad → Consultar archivo por hash…**, selecciona un archivo de prueba.
  - Verifica que muestra el hash SHA-256 calculado localmente y pide consentimiento antes de enviar solo el hash.
  - Pega una cadena de 64 caracteres hexadecimales con la palabra `virustotal` en el chat: verifica que Clara oculta el mensaje, advierte que no se envíen claves por chat y no lo guarda en el historial.

---

## 8. Copias de seguridad, restauración y borrado (en cuenta de prueba con datos ficticios)

- [ ] **Exportar respaldo ZIP no cifrado:**
  - En **Copias de seguridad → Exportar respaldo…**, verifica que el aviso indica claramente que el ZIP **no está cifrado** y que la clave de VirusTotal queda excluida.
  - Abre el ZIP generado y comprueba que solo contiene `asistente.db` y `settings.json` (sin `virustotal_api_key.dpapi` ni claves en `settings.json`).
- [ ] **Restaurar respaldo (en cuenta de prueba):**
  - Agrega una tarea ficticia adicional, restaura el ZIP anterior y verifica que se crea primero una copia en `backups_before_restore` y que los datos vuelven al estado respaldado.
- [ ] **Eliminar todos los datos locales (en cuenta de prueba):**
  - Abre **Eliminar todos mis datos locales…**, verifica que el botón permanece deshabilitado hasta escribir `BORRAR`, confirma y comprueba que las tablas quedan vacías y las preferencias vuelven a `07:00` y `Colima, Colima, México`.
