# CLARA · Asistente Personal — app v1.27.4 (Etapas 1–5 integradas; Etapas 8–11 en primer pase; Centro de privacidad parcial)

Aplicación gráfica local para Windows con tareas académicas, horario de clases, rutinas recurrentes, recordatorios, rutina matutina configurable, memoria editable, voz opcional y un panel informativo de seguridad. **CLARA** significa ahora **Centro Local de Asistencia, Rutinas y Agenda**: una expansión descriptiva acordada para el proyecto, no el nombre del modelo local. Este paquete reúne el código actual y pruebas para evaluación. El ZIP de código fuente no contiene el ejecutable; `build_windows.bat` debe ejecutarse en Windows para producir la carpeta portable con PyInstaller.

**v1.27.4 — interfaz y voz:** además de conservar la marca CLARA, esta versión fija el panel de chat para mantener visibles el campo de texto y los controles inferiores en ventanas bajas, e incluye una prueba manual de la salida de voz. También mantiene las validaciones de rutas y respaldos reforzadas. Se conserva `%USERPROFILE%\AsistentePersonal` para mantener preferencias, tareas e historial. Los turnos antiguos que guardaban el nombre anterior del asistente se muestran como Clara; no se reescribe ni borra la base de datos.

## U5 · primer pase de lenguaje visual para Tkinter (v1.19)

La ventana principal adopta el lenguaje oscuro de la maqueta U1/U3 (azul profundo, cian/azul y acento dorado), estilos comunes para botones, campos y tablas, estados de foco/selección con contraste, y una barra de acciones en dos niveles. **DETENER AHORA · Esc** se conserva visible en la cabecera. Las pantallas secundarias usan la misma paleta en sus controles principales. Es una primera pasada del sistema visual, no una certificación de accesibilidad; proporciones, escalado, contraste y navegación por teclado requieren revisión visual en Windows.

## Etapa 1 global: tareas, agenda manual y datos locales

El formulario de tareas admite descripción/notas opcionales, guardadas localmente en SQLite; las bases existentes se migran añadiendo la columna sin reemplazar registros. **Detalles** permite consultar esa descripción. La exportación iCalendar incluye las notas y la fecha de la ocurrencia de tarea; no exporta una regla de repetición completa. Las herramientas de respaldo permiten exportar/restaurar ZIP y borrar explícitamente los registros locales y restablecer preferencias. El borrado requiere escribir `BORRAR` y una confirmación final; las copias automáticas de restauración pueden borrarse desde el mismo diálogo. Se aplica borrado lógico de SQLite y compactación, pero no se garantiza un borrado forense de la memoria física. Los ZIP exportados a otras ubicaciones no se detectan ni eliminan. Los respaldos ZIP no están cifrados. La API key de VirusTotal, si está configurada, se cifra por separado con DPAPI y nunca se incluye en respaldos.

La agenda sigue siendo manual/local; esta etapa no añade sincronización externa. La migración y la compilación se verifican en este entorno, pero la interfaz, el flujo de borrado y el almacenamiento deben probarse en Windows real antes de distribuir el paquete.

## Etapa 2: avisos repetibles y tareas recurrentes

Las tareas con fecha pueden configurarse para repetirse **diariamente o semanalmente**. Al marcar una ocurrencia como hecha, Clara crea la siguiente y conserva la ocurrencia completada; solo mantiene una próxima ocurrencia pendiente por serie. No hay repetición mensual ni creación automática de tareas recurrentes sin marcar como hecha.

Los avisos de tareas vencidas y clases (15 minutos antes) se presentan en una ventana de Clara con **Posponer 10 min** o **Descartar este aviso**. Si la ventana se cierra sin descartar, el aviso vuelve a presentarse cada 15 minutos. El historial local registra detección, presentación, posposición y descarte; los avisos se deduplican por evento/fecha.

Las fechas y horas se interpretan según el reloj y la zona horaria local de Windows; no se configura una zona distinta por tarea. Tras reanudar o iniciar sesión, se recuperan tareas vencidas y avisos de clases pendientes del mismo día. Las notificaciones dependen de que el PC esté encendido y haya una sesión interactiva; no pueden mostrarse mientras el equipo está apagado o sin sesión. El Programador de tareas y los cambios de zona/horario siguen pendientes de validación en Windows real.

## Etapa 3: consultas locales y borradores confirmables

El chat responde localmente a “¿qué tengo hoy/mañana?” con clases, tareas vencidas o del día y bloques guardados; esas consultas no se envían a Ollama. “Ayúdame a organizar la tarde” produce un borrador usando la agenda local, evita clases y bloques existentes y propone bloques de 45 minutos con pausas de 15 minutos. Puedes editar o quitar propuestas; solo **Confirmar y guardar** crea bloques en la agenda local. No modifica tareas ni clases.

También puedes pedir un bloque con título, fecha y rango de 24 horas (por ejemplo, “reserva de 15:00 a 16:00 mañana para estudiar”). Si faltan datos, Clara pregunta; cuando están disponibles abre el formulario para revisar. Los bloques pueden editarse/eliminarse en Agenda semanal y se incluyen en respaldo y exportación iCalendar. Un traslape se señala para confirmación explícita.

Los borradores se calculan desde datos locales; la IA conversacional no recibe tareas/clases automáticamente y no guarda acciones por su cuenta. Aun así, revisa el horario antes de confirmar: las duraciones son solo una sugerencia heurística.

### Qué entiende el chat en lenguaje natural hoy

Ollama funciona como **conversador local y clasificador de intenciones acotado**, no como un agente con acceso directo al sistema. En v1.27, las peticiones que no reconocen primero las reglas existentes se envían a Ollama local en modo JSON. La app acepta solo una lista cerrada de intents, valida campos/fechas/horas y nunca ejecuta instrucciones del modelo. El texto del usuario, hasta los últimos turnos en memoria y recuerdos explícitos vigentes pueden formar parte del contexto; no se adjuntan automáticamente tareas, clases, agenda, nombres de resultados ni contenido de archivos. El historial persistente sigue siendo opt-in y apagado por defecto.

Las acciones admitidas son propuestas o consultas controladas: conversación general; borrador de tarea o bloque (formulario editable, sin guardar hasta confirmación); consulta local de agenda; propuesta de tarde; búsqueda/inventario de archivos; y preparación de abrir/mover un documento. En archivos, Ollama solo propone términos y tipo. La app abre su ventana, solicita que tú elijas la raíz cada vez y no manda resultados/contenido al modelo. Para abrir o mover, tú seleccionas el elemento y confirmas individualmente; mover conserva el destino elegido por operación, sin lotes ni sobrescrituras. La app no da al modelo acceso a funciones del sistema.

Ejemplos del alcance actual:
- “¿Qué tengo hoy?” → resumen local de agenda.
- “Ayúdame a organizar la tarde” → borrador local; no se guarda hasta confirmar.
- “Me dejaron una tarea de biología para el viernes” → propone campos y abre formulario editable.
- “Busca mi PDF de biología” → propone consulta/tipo y pide elegir la carpeta raíz; busca nombre/metadatos, no el contenido.
- “Abre el PDF de biología” → prepara búsqueda; después debes seleccionar el archivo y confirmar su apertura.
- “Explícame la fotosíntesis” → respuesta general de Ollama, sin navegar la web.

No puede por conversación leer contenido de documentos, ejecutar comandos, lanzar aplicaciones, controlar Windows, consultar VirusTotal, enviar mensajes ni navegar internet. Clima/noticias siguen sus controles separados. El clasificador puede equivocarse o devolver un JSON que la app rechace; en ese caso no se realiza acción. Reformula y revisa todos los formularios. La interfaz y el flujo de Ollama necesitan pruebas manuales en Windows con el modelo instalado.

## Etapa 4: memoria y rutinas bajo control del usuario

Los recuerdos siguen siendo entradas manuales; la lista muestra su origen y fecha de creación. Puedes asignar una fecha opcional de caducidad y borrar cada recuerdo. Al caducar, deja de incluirse en el contexto de Ollama local, pero permanece en SQLite hasta que lo elimines. Las rutinas muestran su origen y pueden editarse, pausarse o borrarse.

Las sugerencias de patrones están **desactivadas por defecto**. Si activas el permiso en Rutinas, el análisis solo se ejecuta cuando pulsas “Analizar patrones ahora…” y confirmas. Revisa tareas completadas manualmente en los últimos 90 días que tengan fecha de finalización registrada por esta versión; el historial más antiguo puede quedar fuera. Requiere tres repeticiones exactas en semanas distintas. No consulta el micrófono, archivos ni calendario externo, no usa Ollama y no guarda una rutina automáticamente. Crear la rutina sugerida requiere una segunda confirmación; queda marcado su origen.

La validación de los diálogos y el recorrido en Windows real siguen pendientes antes de distribuir.

## Etapa 5: lectura local de un calendario iCalendar

En **Agenda semanal → Vincular .ics local…** puedes elegir un archivo del equipo. Clara lo vuelve a leer al actualizar la agenda; muestra sus eventos en modo **solo lectura**, marca coincidencias y traslapes con clases/bloques locales, y permite quitar el vínculo sin borrar el archivo. No importa automáticamente sus eventos a tareas, no los sincroniza ni modifica el archivo. La ruta local se guarda en preferencias y puede aparecer en un respaldo ZIP.

Se convierten horas UTC y desfases numéricos a la hora local; los `TZID` IANA se convierten si el Python de Windows tiene esa zona disponible. Las horas flotantes se interpretan como hora local; si falta la zona se muestra una advertencia. Se omiten eventos recurrentes y cancelados, y los eventos sin duración conocida no se usan para calcular traslapes. La importación manual .ics existente sigue siendo una acción separada y confirmada.

**No conecté Google Calendar, Outlook ni otra cuenta**, y no se consulta una URL/feed. La conexión con servicios/API externos y permisos de cuenta espera a que indiques el proveedor y autorices ese acceso explícitamente.

## Etapa 6: consulta manual de reputación por hash (VirusTotal)

El centro de seguridad ofrece una consulta manual de SHA-256. Clara calcula el hash leyendo el archivo en bloques locales y, antes de cada petición, muestra una confirmación con el hash exacto. Si aceptas, una petición HTTPS GET envía el hash en la URL y tu API key en un encabezado de autenticación; **no se sube el archivo ni se transmiten su nombre o ruta**. VirusTotal puede incorporar el indicador consultado a su conjunto de datos compartido; no consultes hashes que puedan revelar información confidencial, sensible o personal. Consulta la [documentación oficial de la API v3](https://docs.virustotal.com/reference/file-info) y su [nota sobre búsquedas de indicadores](https://docs.virustotal.com/reference/api-search).

Configura tu propia API key directamente en la app, nunca en el chat. En Windows se cifra con DPAPI para el usuario actual en un archivo local separado; no forma parte de `settings.json`, respaldos exportados ni respaldos automáticos. “Eliminar todos mis datos” también elimina ese archivo cifrado. Restaurar un ZIP no restaura ni reemplaza la clave. El borrado no garantiza eliminación forense de bytes. Si el archivo cambia durante el cálculo, se aborta la consulta.

La app solo pide el informe existente (`GET /api/v3/files/{sha256}`): no sube, escanea ni vuelve a analizar archivos, no consulta en segundo plano, no reintenta automáticamente y no toma decisiones ni elimina/bloquea nada según los resultados. Hay un límite local aproximado de una solicitud cada 16 segundos; VirusTotal puede aplicar cuotas y condiciones de uso propias. La falta de informe, cero detecciones o desacuerdo entre motores **no demuestra que el archivo sea seguro**; los informes pueden estar incompletos o desactualizados. Una consulta ya enviada no puede retirarse del servidor. La parada de emergencia ignora el resultado en la interfaz, pero no puede garantizar que interrumpa o revierta una petición HTTPS ya en curso.

La integración se verificó con pruebas simuladas, sin API key ni consulta real. El cifrado DPAPI y el recorrido visual deben validarse en Windows antes de distribuir; esta función no sustituye al antivirus.

## Etapa 7: piloto de apertura de carpeta local

En **Seguridad y alertas → Etapa 7**, el único piloto disponible es elegir una carpeta existente y, tras una confirmación que muestra su ruta y explica el efecto, solicitar a Windows que la abra en el Explorador. Clara no enumera, lee ni modifica sus archivos. No se aceptan rutas de comandos ni parámetros arbitrarios. Cada intento se registra localmente con hora, acción y resultado, pero sin guardar la ruta; puedes consultar y borrar registros en el historial. El registro forma parte de la base local y sus respaldos, y se elimina con “Eliminar todos mis datos”.

El piloto requiere Windows y no recuerda permisos: pide confirmación cada vez. Si cancelas, no intenta abrirla. El mensaje explica que la parada de emergencia no puede garantizar el cierre del Explorador una vez iniciado. La selección y el lanzador se probaron con simulación local, no en Windows real; valida la UI y el comportamiento de Explorer antes de depender de ello. No se ha habilitado ninguna otra acción del sistema.

## Novedades de preferencias, RSS, historial y bandeja (v1.19)

- **Noticias:** puedes elegir Google News México, BBC News Mundo o DW Español y pedir 3, 5, 8 o 10 titulares. Google aplica el tema configurado; los otros feeds muestran su selección general. Cada titular se acompaña de la fuente y la URL para que tú la revises; Clara no abre los enlaces automáticamente. La consulta ocurre al abrir la rutina matutina. RSS consultados: [BBC News Mundo](https://www.bbc.com/mundo/institucional/2011/03/000000_rss_gel) y [DW](https://corporate.dw.com/es/rss/a-68793660).
- **Historial de chat opcional:** está apagado por defecto. Si lo activas, conserva solo mensajes tuyos y respuestas de Clara, hasta 1000 registros, y carga los últimos 200 al iniciar. El estado del sistema, seguridad, reportes y registros de acciones quedan fuera. Puedes revisar, exportar como CSV sin cifrar o borrar lo guardado. El historial forma parte de la base SQLite y del ZIP de respaldo, que tampoco está cifrado.
- **Avisos y bandeja (opcionales):** `instalar_opciones_windows.bat` instala `winotify`, `pystray` y Pillow. En Preferencias puedes activar toasts genéricos solo cuando Clara está minimizada y minimizar a la bandeja al cerrar con X. El menú de bandeja permite mostrar Clara, pausar avisos durante 8 horas (también los revisores programados) y salir. Ambos controles están desactivados por defecto. Los toasts pueden ser bloqueados por Windows, asistencia de concentración o preferencias de notificaciones; dependen de sesión interactiva. La pausa temporal se guarda localmente y caduca automáticamente a las 8 horas.
- **Paquete portable:** `build_windows.bat` prepara `dist\\Clara` con PyInstaller, corre antes compilación y pruebas unitarias, y crea `dist\\CLARA-v1.27.4-Windows-portable.zip`. Es un constructor, no un MSI. El ZIP de código fuente del proyecto no contiene el `.exe`; el constructor debe ejecutarse en Windows. El ejecutable no está firmado; la GUI, el Programador de tareas y las funciones opcionales deben probarse en Windows antes de distribuir.

## Novedades 1.11: primera integración de la esfera en Tkinter (U4)

La cabecera del chat ya incorpora una esfera de datos dibujada con Tkinter Canvas. Permanece compacta en reposo y durante la captura manual; se expande y anima solo cuando comienza realmente la respuesta hablada de Clara. **DETENER AHORA · Esc** cancela la lectura y repliega el visualizador. La etiqueta textual del estado no depende solo del color. Para evitar captar la voz de salida, el programa no permite usar micrófono y TTS a la vez.

Es una integración inicial: el visor oscuro es un componente dentro de la UI clara existente; todavía no rediseña todas las pantallas ni cambia el tema completo. Hace falta comprobar el tamaño, contraste y animación en Windows con la voz instalada.

## Módulo UI/UX U1–U3: maqueta navegable

`Clara_UI_prototipo_U1.html` ofrece un primer recorrido por Inicio, Conversación, Agenda escolar, Tareas, Rutinas, Memoria, Seguridad y Preferencias. La navegación, las respuestas visuales y algunos borradores son demostrativos; los cambios no persisten al recargar.

La simulación de push-to-talk no abre el micrófono; presenta una transcripción ficticia editable. La esfera permanece compacta en la entrada manual y se expande solo durante la voz simulada de Clara. **DETENER AHORA · Esc** repliega la esfera y cancela el estado de la demo.

No se conecta a la base SQLite, Ollama, internet o al dispositivo de audio. Es un prototipo de diseño para revisar, no una actualización integrada de la interfaz Tkinter.

## Novedades 1.10: concepto de esfera de datos

El título de la ventana y el chat presentan el nombre **Clara**. La dirección visual acordada es una esfera holográfica abstracta que permanece compacta mientras el usuario habla y se expande solo mientras Clara responde en voz.

- `Clara_UI_concepto.html` es una demo interactiva de esa expansión y de la parada con Esc. Es simulada: **no activa el micrófono, no graba audio ni procesa voz**.
- `Clara_esfera_datos_concepto.svg` es el boceto estático actualizado. `Clara_cuerpo_concepto.svg` conserva una iteración anterior y ya no representa el rumbo actual.
- Los archivos SVG/HTML siguen siendo prototipos separados; su dirección de esfera se integró parcialmente como un Canvas en Tkinter (v1.11), sin trasladar aún toda la maqueta.
- La inspiración es holográfica/ciencia ficción general; el diseño no copia interfaz, logotipos ni utilería de la película.

## Novedades 1.8: calendario escolar y excepciones

Desde **Horario de clases → Calendario escolar…** puedes registrar días sin clases o un rango de vacaciones, cancelar una clase en una fecha, cambiar su hora/nombre/aula por un día o añadir una clase especial. Estas excepciones afectan la agenda semanal, el resumen matutino, los avisos y la instantánea iCalendar; no modifican tu horario recurrente. Un día sin clases suprime las clases normales, aunque puedes añadir sesiones especiales para esa fecha. Los rangos se aplican a cada fecha inclusive, hasta dos años. Las excepciones se capturan manualmente; no se consultan calendarios institucionales ni se infieren vacaciones.

## Novedades 1.26: gestión del historial local · Etapas 8–11 y Stage12 parcial

Desde **Buscar documentos / ver carpeta**, cada búsqueda o inventario abre el selector de carpetas y trabaja dentro de la raíz elegida para esa operación. La búsqueda recorre subcarpetas por nombre/tipo e incluye PDF, DOCX, XLSX, PPTX, TXT y Markdown; el inventario lista archivos permitidos y carpetas, inmediato o recursivo. Muestra nombre, tipo, fecha, tamaño y ruta relativa. No lee el contenido ni guarda la consulta/resultados. DETENER cancela cooperativamente; llamadas bloqueantes de disco pueden tardar. Se omiten carpetas ocultas/de sistema, symlinks/junctions y nombres comunes de nubes; solo se aceptan raíces locales fijas y concretas en Windows.

**Abrir seleccionado** solo aparece habilitado para un documento permitido de los resultados. Antes se muestra su ruta relativa, el tipo de aplicación predeterminada de Windows y una advertencia sobre contenido activo; requiere confirmación para cada archivo. Antes de abrir, Clara revalida que siga dentro de la carpeta elegida, que no haya cambiado y que no sea enlace o tipo no permitido. Se usa la asociación predeterminada de Windows; Clara no puede forzar ni verificar Protected View ni controlar la aplicación una vez abierta. No abre ejecutables ni scripts.

**Mover seleccionado** trabaja con un solo documento por operación, solo en Windows. Pide elegir destino y muestra las rutas antes de confirmar. Rechaza el mismo destino, colisiones, unidades distintas y ubicaciones no permitidas; no sobrescribe ni hace copia+borrado entre discos. **Deshacer último movimiento** es otra acción confirmada, disponible solo mientras la ventana siga abierta y si el archivo conserva identidad y metadatos esperados; el historial vive solo en memoria y se pierde al cerrar. No es garantía forense ni a prueba de cambios concurrentes.

**Aplicaciones autorizadas** abre un administrador separado: se añade una ruta `.exe` gráfica instalada bajo Program Files o `LocalAppData/Programs`, hasta 10. No admite accesos directos, argumentos, scripts, intérpretes, instaladores ni utilidades de consola; revisa la cabecera PE y la ruta, pero no verifica firma del editor. Añadir guarda ruta e identidad básica en preferencias locales (pueden entrar en un ZIP de respaldo no cifrado) y no inicia la app. Cada inicio exige confirmación, lanza solo el `.exe` exacto sin `shell` ni argumentos y no solicita elevación. La app lanzada puede conectarse a internet o modificar archivos; Clara no puede detenerla ni controlarla después. Retirar la autorización no cierra procesos ya iniciados.

**Privacidad y permisos** resume micrófono push-to-talk, historial de chat, sugerencias de rutinas, notificaciones, bandeja, vínculo ICS, clave VirusTotal y conteos de actividad. Desde ahí se abren los controles de aplicaciones, preferencias, Seguridad, historial y respaldos. El registro de aperturas/movimientos/lanzamientos guarda solo categoría y resultado, no nombres ni rutas; la búsqueda no se registra. El historial de acciones permite exportar CSV (sin cifrar), borrar un evento o borrar todos con confirmación. Las rutas de apps y el vínculo ICS sí están en preferencias, y los ZIP de respaldo no están cifrados. No se configuró una URL de distribución verificada: no hay comprobación, descarga ni instalación automática de actualizaciones.

Límites iniciales: 20.000 entradas, 5.000 resultados o 20 segundos por operación; al alcanzar un límite, los resultados se marcan incompletos. Desde v1.27 el chat puede preparar búsqueda/inventario/apertura/movimiento mediante intents; sigue siendo obligatorio elegir la carpeta raíz y confirmar acciones sobre cada archivo. Búsqueda, apertura, movimiento y lanzamiento de apps requieren validación en Windows.

## Novedades 1.7: borrador estructurado de encargos

Al escribir o dictar una petición reconocida por las reglas locales —por ejemplo, “me dejaron una tarea para el viernes”— el parser intenta separar título, materia y fecha/hora. Desde v1.27, otras formulaciones pueden pasar al clasificador estructurado de Ollama para proponer esos campos; si no se detecta título, deja “Tarea nueva”. En ambos casos abre un formulario editable y **debes revisar y pulsar Guardar**. El parser de fechas incluye “en 3 días”/“dentro de 2 semanas” hasta 730 días; fechas ambiguas pueden fallar. No se guarda automáticamente.

## Novedades 1.6: parada de emergencia

- El botón rojo **DETENER AHORA · Esc** está disponible en la ventana principal; `Esc` es un atajo adicional.
- Solicita cancelar la generación de Ollama mientras transmite tokens y cierra la respuesta HTTP local; también detiene la captura del micrófono y la lectura de voz.
- Marca la respuesta como interrumpida y no guarda un texto parcial como turno completo de conversación.
- No cierra la aplicación ni revierte tareas ya guardadas. La cancelación es cooperativa: si Windows, Tkinter o el propio proceso estuvieran congelados, el botón no puede garantizar un corte a nivel del sistema operativo. La X de la ventana sigue disponible como salida de emergencia.

## Novedades 1.5: importación iCalendar

- Desde **Agenda semanal** puedes importar un archivo `.ics`; se muestra una vista previa y se pide confirmación antes de añadir eventos como tareas.
- Solo importa eventos no recurrentes con fecha de inicio y título, dentro del próximo año. Se evitan duplicados por UID o por título/fecha; los eventos recurrentes y las clases del propio asistente exportadas desde la app se omiten.
- No importa descripciones, asistentes ni cambios futuros; no establece sincronización bidireccional. Los horarios con zona `TZID` se interpretan como la hora local escrita; verifica las horas después de importar. Las fechas UTC se convierten a la zona local del equipo.

## Novedades 1.4: agenda semanal e iCalendar

- **Agenda semanal** reúne tareas fechadas y clases recurrentes de los próximos siete días.
- **Exportar .ics** crea un archivo compatible con calendarios que admiten iCalendar. Exporta tareas futuras con fecha como eventos de día completo y genera una instantánea de 12 semanas de clases aplicando las excepciones registradas; también exporta los días sin clases. No sincroniza ni importa cambios de vuelta a la aplicación.
- Si una clase no tiene hora de fin, el archivo exportado le asigna una hora como duración provisional y lo indica en la descripción. Las horas se exportan como hora local flotante.

En **Agenda semanal** están los botones **Importar .ics…** y **Exportar .ics…**. La importación añade eventos a la lista de tareas; revisa la fecha y hora antes de usarlos como recordatorios.

## Novedades 1.3: diagnóstico guiado

El botón **Diagnóstico** comprueba versión de Python, base de datos, preferencias, conexión local a Ollama, dependencias/modelo de voz y, en Windows, si están registradas las tareas programadas. No enciende el micrófono, no escanea archivos ni consulta internet para noticias/clima. Cada aviso incluye el siguiente paso sugerido.

## Novedades 1.2: respaldos portables

- **Exportar respaldo** crea un ZIP con la base local y las preferencias.
- **Restaurar respaldo** valida el ZIP y la integridad de la base antes de reemplazar datos. Antes de la restauración, crea un respaldo automático local en `%USERPROFILE%\AsistentePersonal\backups_before_restore`.
- El respaldo incluye tareas, materias, clases, excepciones escolares, rutinas, memoria, reportes y preferencias. **No está cifrado**; guárdalo en un lugar privado y no lo envíes a terceros.

## Novedades 1.1: rutinas recurrentes

- **Rutinas recurrentes:** crea plantillas de tareas con materia, días de la semana y hora de aviso opcional. En la rutina matutina se generan las tareas de ese día, una sola vez. Puedes editarlas, pausarlas o eliminarlas. Eliminar una rutina no borra tareas ya generadas.
- Se mantienen las preferencias de hora de la mañana, ciudad meteorológica y tema de titulares. Guarda preferencias en `%USERPROFILE%\AsistentePersonal\settings.json`. Después de cambiar la hora, vuelve a ejecutar `programar_rutina.bat` para actualizar la tarea programada de Windows.

## Uso diario

- **Rutina de mañana:** clases de hoy, pendientes/vencidas, tareas recurrentes del día, clima y titulares.
- **Rutinas:** crea tareas repetibles por días de semana; se añaden de forma idempotente al resumen matutino.
- **Mis clases · agregar / editar:** botón visible junto a “Mis tareas” para registrar o cambiar materia/clase, día, hora de inicio y fin opcional; doble clic en una fila también abre edición. Los controles de tarea quedan encima de la lista para no ocultarse al reducir la altura. Windows inicia la ventana principal maximizada. **Calendario escolar…** administra excepciones de fecha única y rangos de vacaciones.
- **Agregar tarea:** materia, fecha límite, prioridad y hora de aviso. El asistente también abre el formulario al escribir/dictar “me dejaron una tarea”; revisa antes de guardar.
- **Chat de texto con Clara:** escribe en “Escribe un mensaje para Clara” debajo de la conversación y pulsa **Enviar** o Enter. Si Ollama no está disponible, las funciones deterministas de agenda y formularios siguen funcionando; el chat general necesita Ollama local.
- **Memoria:** agrega, revisa, edita y elimina preferencias manualmente. Si conversas con Ollama, las memorias explícitas se incluyen como contexto; tareas y clases no.
- **Voz opcional:** por defecto, Clara lee automáticamente respuestas de chat si `pyttsx3` y una voz de Windows están disponibles; actívala/desactívala en Preferencias. `Leer última respuesta` lee una respuesta de chat de Clara, no los avisos de estado ni el resumen de noticias. Si no se oye, ejecuta `diagnosticar_voz.bat` para probar el motor y revisar voces sin usar el micrófono ni internet. En el paquete fuente, si falta `pyttsx3`, instala con `py -3 -m pip install pyttsx3`; también se requiere salida de audio y una voz instalada en Windows. Para hablarle, pulsa el botón del micrófono, detén la captura, revisa la transcripción y envíala tú. El micrófono nunca se activa continuamente.
- **Seguridad y alertas:** guía informativa, notas manuales locales y consulta a Defender solo de lectura cuando tú la solicitas. No analiza archivos, detecta malware ni vigila el equipo.
- **Copias de seguridad:** exporta y restaura tus datos desde la interfaz; la restauración reemplaza los datos actuales después de confirmación y guarda una copia anterior.

## Ejecutar y programar

Requisitos: Windows 10/11, Python 3.10 o posterior y Tkinter. Descomprime el proyecto en una carpeta permanente y ejecuta `iniciar.bat`. Si quieres que el inicio se encargue de revisar/activar el servidor de Ollama, comprobar Qwen3 y ofrecer instalar la voz, ejecuta `iniciar_clara_terminal.bat`; las descargas y la instalación opcional requieren que aceptes la pregunta correspondiente. Clara sigue abriéndose en su ventana gráfica, con la terminal abierta para ver errores de arranque.

Para programar el resumen de lunes a viernes a la hora configurada y revisar recordatorios/clases cada cinco minutos, ejecuta `programar_rutina.bat`. La comprobación cada cinco minutos se programa por un año; vuelve a ejecutar el instalador al cumplirse ese plazo o si cambias la hora. `quitar_rutina.bat` elimina las tareas programadas sin borrar tus datos. Windows necesita que tu sesión esté iniciada para mostrar ventanas o toasts; el resumen abre la aplicación. Para habilitar opcionalmente bandeja/toasts, ejecuta `instalar_opciones_windows.bat`; las funciones quedan apagadas hasta activarlas en Preferencias.

## Voz (opcional)

1. Ejecuta `instalar_voz.bat` con internet.
2. Descarga [vosk-model-small-es-0.42.zip](https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip) del [catálogo oficial](https://alphacephei.com/vosk/models).
3. Extrae el modelo bajo `models/vosk-model-small-es-0.42/` junto a `app.py`.
4. Usa **Pulsar para hablar**; vuelve a pulsar para terminar y revisa el borrador.

El reconocimiento es local y el audio no se guarda. Puede equivocarse con ruido o nombres propios. La lectura depende de las voces disponibles en Windows.

## Seguridad

La consulta de Defender ejecuta `Get-MpComputerStatus` únicamente al pulsar el botón. Es un estado puntual, no un análisis ni una garantía de que el equipo esté limpio. VirusTotal solo consulta manualmente hashes SHA-256 con confirmación explícita por petición; la app nunca sube archivos. Sigue usando Seguridad de Windows o tu antivirus. No abras archivos sospechosos ni introduzcas claves en enlaces recibidos por alerta. [Documentación de Microsoft](https://learn.microsoft.com/en-us/defender-endpoint/use-powershell-cmdlets-microsoft-defender-antivirus).

## Internet y privacidad

Tareas, clases, recuerdos y reportes se guardan localmente en `%USERPROFILE%\AsistentePersonal\asistente.db`. El reconocimiento de voz y Ollama son locales. El chat envía al modelo local el texto conversacional y las memorias explícitas; no adjunta automáticamente tareas o clases. El historial persistente está apagado por defecto y guarda solo turnos directos de usuario/Clara si lo activas. Noticias y clima requieren internet: se envía la ciudad al servicio meteorológico y la petición de titulares a la fuente RSS elegida; no se mandan tareas ni clases. Las fuentes pueden estar fuera de servicio.

## Roadmap de búsqueda y acciones locales

Las etapas 8–11 tienen primeros pases de código; Etapa 12 incluye un centro parcial. Su alcance, límites y pruebas pendientes están en `Futuras_etapas_Clara.md`. Esto no equivale a validación Windows ni a una garantía de seguridad. Para ver qué está probado, incompleto o aún no existe, consulta `Auditoria_tecnica_Clara_v1.27.4.md`. El alcance de búsqueda es por nombre/tipo dentro de una raíz elegida cada vez; no indexa contenidos.

## Límites y pruebas

Horario semanal manual; no sincroniza vacaciones ni cambios de aula. No hay vigilancia automática del equipo ni antivirus integrado. VirusTotal es solo consulta manual de informes por hash, no un escáner. La interfaz, voz, PowerShell y tareas programadas deben probarse en una computadora Windows antes de depender de ellas. El código pasa `python -m py_compile app.py tests/test_app_helpers.py` y `python -m unittest discover -s tests -v` (23 pruebas locales con helpers, validación de intents, feeds, búsqueda/apertura, movimiento simulado, extracción de respaldos y lanzamiento mockeado; no se ejecutaron movimientos ni aplicaciones reales); falta ejecutar la interfaz y el launcher en Windows. La lista paso a paso para esa validación está en `Pruebas_aceptacion_Windows_etapas_8-12.md`.
