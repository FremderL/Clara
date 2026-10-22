# Clara · Propuesta de etapas futuras y capacidades locales

**Versión del plan:** 0.9 · **Fecha:** 17 de octubre de 2026  
**Estado:** Etapas 8–11 tienen primeros pases en Clara v1.21–1.24; Etapa 12 parcial en v1.25–1.26 incluye exportar/borrar historial. En v1.27.0 se integra un primer clasificador JSON para intents naturales, incluido el acceso a flujos de archivos con confirmaciones; falta prueba real en Windows/Ollama. En v1.27.2 se refuerza el rechazo de raíces de búsqueda dentro de ancestros ocultos/enlazados y se amplían sus pruebas unitarias; en v1.27.3 se endurece la extracción de respaldos y se añaden pruebas de rechazo de ZIP inválidos. Sigue pendiente validación Windows.

## Punto de partida

Clara v1.26 conserva la Etapa 7 como un único piloto: abrir en el Explorador una carpeta existente que la usuaria selecciona, con confirmación cada vez y registro local que omite la ruta. También contiene primeros pases de Etapas 8–11: búsqueda/inventario, apertura confirmada, movimiento individual y allowlist GUI. Etapa 12 tiene un centro parcial de permisos/actividad y el historial de acciones se puede exportar/borrar. La UI debe validarse en Windows; no se configuró una fuente verificada de actualizaciones.

## Principios para acciones sobre archivos y aplicaciones

1. **Alcance local y explícito:** comenzar solo en carpetas que la usuaria elija con el selector de Windows. No recorrer `Windows`, `Program Files`, `AppData`, perfiles completos, unidades de red, unidades extraíbles o carpetas sincronizadas en nube, salvo que una futura decisión las incluya expresamente.
2. **Nada oculto o continuo:** no vigilar cambios, indexar todo el equipo al arrancar ni mantener un servicio residente. La búsqueda comienza solo por acción manual.
3. **Vista previa antes de efectos:** mostrar qué coincidió y qué acción se propone. Abrir o mover requiere consentimiento visible para el elemento concreto; cancelar debe dejarlo intacto.
4. **Sin comandos arbitrarios:** no usar `shell=True`, PowerShell, argumentos de línea de comandos proporcionados por el chat ni permisos de administrador. El asistente no ejecutará scripts, instaladores, macros ni contenido activo.
5. **Parada realista:** DETENER debe cancelar búsquedas cooperativas y evitar iniciar acciones aún no ejecutadas. Una aplicación ya abierta o un movimiento ya completado no se puede deshacer instantáneamente por el botón.
6. **Auditoría mínima y controlable:** no registrar consultas de búsqueda por defecto. Para movimientos, solo si se acuerda, conservar un registro local acotado de ruta original/destino para poder revertir; ofrecer borrado y explicar que esa ruta es información sensible.
7. **Aislamiento de la IA:** el modelo conversacional nunca recibe una lista de archivos ni puede llamar por sí solo a funciones del sistema. Clara interpreta la petición, prepara una propuesta y la interfaz determinista verifica el alcance y pide aprobación.
8. **Sin uploads:** no enviar nombres, rutas, contenido ni hashes de documentos a Ollama remoto o a servicios externos. El uso de Ollama local continúa siendo explícito; no adjunta archivos automáticamente.

## Etapa 8 — Buscar documentos locales

### Primer pase implementado en v1.21 (validación Windows pendiente)

- Ventana manual **Buscar documentos / ver carpeta**; cada búsqueda o inventario abre el selector de carpeta. No conserva la ruta después de la operación.
- Búsqueda por nombre/tipo y recorrido recursivo; inventario inmediato por defecto o recursivo al marcar la opción.
- Límite actual: 20.000 entradas, 5.000 resultados o 20 segundos; exclusiones, cancelación cooperativa y resultados marcados incompletos ante límite.
- Lista nombre, tipo, fecha/tamaño y ruta relativa. No lee contenido, no guarda consulta/resultados, no abre ni modifica archivos.

### Alcance acordado

- La usuaria elige una carpeta raíz **cada vez**; no se conserva una lista autorizada por defecto. Cada búsqueda es manual y termina al cerrar/cancelar.
- Buscar por **nombre/tipo primero**, recorriendo subcarpetas bajo esa raíz. Incluir PDF, DOCX, XLSX, PPTX, TXT y Markdown; excluir scripts y ejecutables. La búsqueda dentro del contenido queda como opción separada para el futuro, apagada hasta aprobación.
- No abrir ni leer contenidos de documentos ni crear índice persistente. Omitir carpetas ocultas/de sistema, symlinks/junctions y rutas fuera de la raíz aprobada.
- Mostrar resultados limitados, ordenados con nombre, tipo, ubicación y fecha. Límite de cantidad/tiempo configurable y botón DETENER; informar de `access denied`, carpeta vacía o cancelación. La cancelación es cooperativa entre carpetas y no garantiza cortar instantáneamente una operación bloqueante.
- **Nueva capacidad solicitada: inventario de una carpeta.** Después de elegir la carpeta, Clara podrá proponer una lista de las carpetas y archivos permitidos que contiene. Por defecto mostrar solo elementos inmediatos; permitir pedir inventario recursivo dentro de la misma raíz con límites y botón detener. Mostrar nombre, tipo y metadatos básicos, no texto/contenido. Omitir ocultos, sistema, symlinks/junctions y scripts/ejecutables; no abrir, modificar ni mover nada.
- La consulta y el listado no se guardan por defecto ni se envían por internet. La usuaria podrá seleccionar un resultado o copiar su ruta; abrirlo requerirá Etapa 9 y confirmación explícita.

### Criterios de salida

- Búsqueda e inventario quedan dentro de la carpeta elegida; no cambian, abren ni leen contenido de archivos.
- La query y los resultados no se guardan por defecto y nunca se envían por internet.
- Pruebas con nombres Unicode, extensiones mixtas, carpetas grandes, symlinks, ocultas/sistema, permisos insuficientes, acceso cancelado y rutas inexistentes.

### Extensión opcional futura: buscar dentro del texto

Es una decisión separada de mayor sensibilidad. Antes se deberían definir carpetas, formatos, límites de tamaño, extracción local, retención y forma de borrar cualquier índice/caché. De inicio, no extraer ni indexar DOC/DOCX/PDF/hojas de cálculo por defecto. No enviar contenido a servicios ni al modelo. La opción debe estar apagada hasta aprobación expresa.

## Etapa 9 — Abrir un documento elegido

### Primer pase implementado en v1.22 (validación Windows pendiente)

- Desde los resultados, el botón **Abrir seleccionado** solo se habilita para archivos permitidos, nunca para carpetas ni en modo lote.
- Se muestra nombre, ubicación relativa, extensión, tamaño, la asociación predeterminada de Windows que se intentará usar y una advertencia de que el documento se abrirá fuera de Clara.
- Confirma cada archivo por separado. Antes y después de confirmar, Clara revalida la raíz, que el elemento siga dentro de ella, que sea archivo documental permitido, no sea enlace y no haya cambiado desde el escaneo.
- En Windows llama solo al manejador predeterminado por asociación del sistema; no arma comandos ni argumentos. Excluye `.exe`, scripts, accesos directos desconocidos y extensiones no permitidas. El mensaje advierte que la aplicación puede procesar vínculos/contenido activo; Clara no puede forzar ni verificar Protected View ni controlar la aplicación después de iniciarla.
- No dar al modelo control sobre aplicaciones ya abiertas, teclado, ratón, macros, extensiones o contenido.

**Pruebas pendientes:** documento existente/ausente, asociación desconocida, permisos, nombre engañoso/extensión doble, cancelación, cambio entre búsqueda y apertura, protección real de Windows/Protected View y comprobación de que Clara no lanza tipos ejecutables. El entorno de desarrollo no ha llamado a `os.startfile` ni abrió archivos reales.

## Etapa 10 — Mover documentos con confirmación

### Primer pase implementado en v1.23 (movimiento real pendiente de validación Windows)

- Mover **un documento seleccionado a la vez**, desde un resultado de la búsqueda, a una carpeta local que la usuaria elige en cada intento. No mueve carpetas ni lotes.
- Presenta origen/destino completos y pide confirmación. La confirmación no se recuerda. Si se cancela el selector o diálogo, no hay movimiento.
- Rechaza destino igual al origen, conflicto de nombre (no sobrescribe ni renombra), redes/unidades removibles conocidas, raíces protegidas, carpeta de nube conocida, symlink/junction y volúmenes distintos. Solo documento en la lista permitida; la función se habilita en Windows.
- Revalida raíz, tamaño, fecha de modificación e identidad del archivo tras confirmación. Usa `os.rename` en el mismo volumen, sin fallback a copiar y borrar. En Windows, `os.rename` debe fallar si aparece un destino existente; las carreras con otros procesos no se pueden eliminar totalmente.
- **Deshacer último movimiento** pide confirmación y solo funciona mientras la ventana permanezca abierta, si el archivo conserva ID/tamaño/fecha y el origen original está libre. Historial de ruta únicamente en memoria del proceso, no persistente; cerrar la ventana/app lo pierde. Si no se puede revertir con seguridad, Clara no fuerza el cambio.

### Criterios de salida pendientes

- Probar primero en Windows con archivos/carpetas ficticios: destino existente, misma/distinta unidad, unidad extraíble/red, permisos, archivo abierto/bloqueado, cambios concurrentes, cancelar, deshacer y cierre de ventana.
- Verificar el comportamiento real de `os.rename` y `st_dev` en Windows, no sobrescritura bajo carrera, actualizaciones de la lista y pérdida deliberada del deshacer al cerrar.
- No probar primero con documentos reales. No afirmar que deshacer funciona después de cambios externos o de cerrar la ventana.

## Etapa 11 — Abrir aplicaciones aprobadas

### Primer pase implementado en v1.24 (validación Windows pendiente)

- Desde **Aplicaciones autorizadas**, la usuaria elige directamente un `.exe` gráfico instalado bajo Program Files o `LocalAppData/Programs`; no se admiten `.lnk`, parámetros ni texto libre. Máximo 10 rutas.
- Rechaza nombres conocidos de intérpretes, shells, instaladores/utilidades; inspecciona la cabecera PE y permite solo subsistema Windows GUI. Exige unidad fija y excluye rutas de nube conocidas. No verifica firma digital, reputación o seguridad del editor.
- Añadir requiere confirmación y almacena ruta, tamaño, fecha de modificación e identidad básica en preferencias locales; esas rutas pueden incluirse en un ZIP de respaldo sin cifrar. Añadir no inicia el proceso; existe función visible para retirar la autorización.
- Cada inicio requiere confirmación mostrando la ruta; valida de nuevo identidad/metadata. Usa `subprocess.Popen([ruta], shell=False, cwd=carpeta_del_exe, close_fds=True)`: sin argumentos, `cmd`, PowerShell ni elevación.
- La app abierta sale del control de Clara; puede modificar archivos o conectarse a internet. Retirar su autorización no cierra procesos ya lanzados. Clara no mata procesos ni garantiza que DETENER interrumpa la apertura.

**Pruebas pendientes:** seleccionar una app GUI conocida en Windows, probar PE/rutas y lista persistente, retirar autorización, app actualizada/cambiada, error de proceso y verificación de que no se lanza ninguna aplicación durante el alta. La prueba de Popen de este entorno usa un mock; no arrancó un `.exe` real.

## Etapa 12 — Centro de permisos, actividad y mantenimiento

### Primer pase parcial implementado en v1.25–v1.26

- Centro de **Privacidad y permisos** resume: push-to-talk, búsqueda no persistente, apps autorizadas, historial opt-in, sugerencias de rutinas, toast/tray, vínculo ICS, estado VirusTotal, conteos de actividad/notas y respaldos.
- Incluye accesos a preferencias, administrador de apps (retirar permisos), Seguridad/VirusTotal, historial y respaldos/datos. No se conserva una lista de raíces de búsqueda; cada búsqueda pide una carpeta.
- Historial de acciones permite exportar CSV (fecha/categoría/resultado, sin nombres/rutas guardados por el sistema) y borrar uno o todos con confirmación. CSV sin cifrar. Eventos de apertura, movimiento, deshacer y apps no registran nombres/rutas; la búsqueda no deja registro. Los registros se guardan localmente en SQLite y pueden formar parte de los ZIP de respaldo no cifrados.
- El resumen muestra que no existe fuente/URL verificada de distribución. No hay comprobación automática, descarga ni instalación de actualizaciones; no se añadieron enlaces inventados.

### Pendiente

- Revisión de UX/accesibilidad en Windows; comprobar rutas de permiso, revoque de apps, actividad sin nombres/rutas y advertencias de respaldo.
- Definir y autorizar un canal oficial verificable (sitio o tienda) antes de añadir un comprobador de versión o enlace. Cualquier aviso sería manual/no descargable hasta que la usuaria decida distinto; no se instalará automáticamente.
- Compatibilidad de esquema y validación de backup/restauración en Windows.

## Otras mejoras de producto propuestas

- **Accesibilidad U5:** probar Windows a 100/125/150 % de escala, tamaños de ventana, navegación solo con teclado, foco visible, contraste, lectores de pantalla y movimiento reducido.
- **Instalación:** construir `.exe` reproducible en Windows, revisar SmartScreen/firma y voz opcional; no distribuir hasta validar tarea programada, DPAPI y datos en una cuenta estándar.
- **Diagnóstico local:** incluir versiones y disponibilidad de tray/feeds, pruebas simuladas y enlace al procedimiento manual; nunca activar cámara/micrófono/red durante un diagnóstico sin consentimiento.
- **Noticias:** mantener RSS curados y mostrar medio/enlace; no añadir URL arbitraria sin protección y confirmación.
- **Calendario:** conexión Google/Outlook solo después de que la usuaria elija proveedor, alcance mínimo de permisos y flujo de revocación. No inferir esa autorización del pedido general de futuras mejoras.
- **Búsqueda en lenguaje natural:** aceptar “busca mi PDF de biología” solo como consulta a carpetas seleccionadas; mostrar qué criterio se usó y preguntar si hay varias coincidencias. No abrir/mover por inferencia.

## Decisiones registradas y pendientes

Respuestas de la usuaria para orientar el diseño:

1. **Búsqueda:** nombre/tipo primero; búsqueda de contenido no incluida en el primer alcance.
2. **Carpeta raíz:** elegirla cada vez, sin lista persistente de carpetas autorizadas en la primera versión.
3. **Tipos para buscar:** PDF, DOCX, XLSX, PPTX, TXT y Markdown; excluir scripts/ejecutables.
4. **Subcarpetas:** recorrerlas dentro de la raíz elegida; excluir ocultas/sistema y symlinks; aplicar límites y ofrecer botón DETENER.
5. **Abrir/mover:** confirmación individual; sin lotes ni sobrescrituras. Etapas 9–10 tienen primeros pases en v1.22–1.23; ningún archivo real se ha abierto/movido en pruebas aquí. Cada acción exige consentimiento en la interfaz y revalidación.
6. **Inventario de carpeta:** permitir preguntar qué archivos/carpetas contiene; nombres y metadatos básicos, sin leer contenido; inventario inmediato por defecto y opción recursiva dentro de la misma raíz con los mismos límites. Implementado en primer pase v1.21; falta validación Windows.
7. **Aplicaciones:** selección explícita de `.exe` GUI, allowlist pequeña, confirmación al añadir y en cada lanzamiento; implementado en primer pase v1.24. Ningún proceso real se ha lanzado en pruebas.

Pendiente para aceptar Etapas 8–11: construir/probar la interfaz en Windows; probar búsqueda/inventario, apertura y movimiento/deshacer con archivos ficticios, y allowlist/lanzamiento mockeado con una app GUI conocida; revisar límites, permisos, asociaciones, volumen, colisiones, cancelación, navegación con teclado y rutas de nube/removibles. Los valores de búsqueda son 20.000 entradas, 5.000 resultados y 20 segundos; podrán ajustarse tras la prueba. La búsqueda por contenido y carpetas recordadas quedan fuera de estos pases.

**Criterio común para comenzar una etapa:** alcance escrito, amenazas y datos explicados, pruebas simuladas, confirmación UI, registro/borrado definido, validación en Windows y consentimiento específico. No se incorporan nuevas acciones de sistema hasta que la usuaria confirme expresamente el inicio de esa etapa.
