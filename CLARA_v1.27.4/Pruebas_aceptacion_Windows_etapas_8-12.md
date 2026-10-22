# Pruebas de aceptación en Windows — CLARA, etapas 8–12

**Objetivo:** cerrar las verificaciones que no pueden certificarse con pruebas unitarias en otro sistema. Esta lista valida solo el alcance ya acordado; no autoriza capacidades nuevas.

## Reglas antes de probar

- Usar un equipo/cuenta de prueba de Windows 10/11 y el paquete fuente actual. No probar primero con documentos o datos personales.
- Elegir manualmente una carpeta local fija, no sincronizada, concreta y desechable; no usar `Windows`, `Program Files`, `AppData`, el perfil completo, red ni unidades extraíbles. Si la ruta está redirigida a nube, detenerse y elegir otra.
- Crear únicamente archivos ficticios como `prueba.txt`, `subcarpeta\nota.md` y un duplicado inocuo. No usar archivos descargados, macros, documentos reales, scripts ni ejecutables de prueba.
- La búsqueda debe seguir siendo por nombre/tipo y no leer contenido. No probar con carpetas personales.
- No restaurar ni borrar datos en el perfil principal. Las pruebas de restauración/borrado requieren una cuenta de prueba vacía o una copia aislada. Los ZIP exportados no están cifrados: guardarlos localmente y eliminarlos manualmente al terminar si ya no hacen falta.
- Registrar resultado y mensaje observado; detenerse ante cualquier acción inesperada. No continuar tras una sobrescritura, apertura/movimiento no confirmado, alcance fuera de la raíz o proceso inesperado.

**Versión probada:** ________  **Windows / compilación:** ________  **Fecha:** ________  **Cuenta de prueba:** ________

Estados: `Pendiente` / `Aprobado` / `Falló` / `Bloqueado`. Anotar versión, mensaje y condiciones; no marcar aprobado por una prueba simulada.

## Preparación

- [ ] **W00 · Construcción:** ejecutar `build_windows.bat`; confirmar que compile, ejecute la suite y produzca `dist\Clara\Clara.exe` y `dist\CLARA-v1.27.3-Windows-portable.zip`.
- [ ] **W01 · Inicio:** abrir `Clara.exe`; comprobar título CLARA, chat textual claramente identificado, controles inferiores visibles y **DETENER AHORA** accesible. Cerrar normalmente.
- [ ] **W02 · Datos:** verificar que no se haya creado/movido ninguna carpeta de usuario inesperada. La carpeta de datos prevista sigue siendo `%USERPROFILE%\AsistentePersonal`; no usar el perfil principal para pruebas destructivas.
- [ ] **W03 · Voz base:** ejecutar `diagnosticar_voz.bat`. Debe indicar si `pyttsx3` inicia, listar las voces detectadas e intentar decir una frase. Si no se oye aquí, resolver primero la salida de audio/voz de Windows; este diagnóstico no activa el micrófono ni usa internet.

## Etapa 8 — Búsqueda e inventario

Preparar, en una carpeta de prueba local, un `prueba.txt`, un `subcarpeta\nota.md`, un `no_listar.ps1` ficticio y un elemento dentro de una carpeta oculta. Confirmar que el contenido de los documentos es texto señuelo que no contiene datos personales.

- [ ] **8.1 · Alcance y filtro:** elegir esa carpeta en el selector y buscar por nombre/tipo. Deben aparecer solo coincidencias permitidas dentro de la raíz. No debe pedirse ni guardarse una raíz autorizada para búsquedas futuras.
- [ ] **8.2 · Inventario inmediato/recursivo:** inventario inmediato lista metadatos de elementos directos; recursivo incluye la subcarpeta dentro de límites. Ninguna vista previa debe mostrar el texto interno de `prueba.txt`.
- [ ] **8.3 · Exclusiones:** confirmar que se omitan el script, carpeta oculta y cualquier enlace/junction. Intentar seleccionar una raíz dentro de una carpeta oculta o enlazada: debe rechazarse con explicación.
- [ ] **8.4 · Límites/DETENER:** con una carpeta de prueba poblada solo con elementos ficticios, comprobar progreso, límites y botón **DETENER**. Debe informar si se canceló o llegó a un límite; una llamada bloqueante del sistema de archivos podría tardar en responder.
- [ ] **8.5 · Cero resultados / acceso denegado:** buscar un nombre inexistente y una carpeta de prueba sin permiso de lectura. Debe mostrar cero resultados o advertencia; no bloquear la interfaz ni ampliar el alcance.

## Etapa 9 — Abrir documento elegido

- [ ] **9.1 · Cancelación:** seleccionar `prueba.txt`, leer la advertencia de que se abre fuera de CLARA y cancelar. No debe iniciarse ninguna aplicación.
- [ ] **9.2 · Confirmación individual:** con una asociación de Windows disponible, abrir únicamente el TXT ficticio tras confirmar. Debe usar la aplicación predeterminada; CLARA no promete modo protegido ni controla la aplicación después de abrirla.
- [ ] **9.3 · Revalidación:** volver a buscar, cambiar el TXT de prueba y luego intentar abrir el resultado antiguo. CLARA debe rechazarlo como cambiado y pedir una búsqueda nueva.
- [ ] **9.4 · Tipo no permitido / salida de raíz:** probar mediante el flujo normal solo una selección ficticia no permitida o fuera de la raíz si el UI lo deja seleccionar. Debe impedir abrirla; no se debe invocar manualmente el handler del sistema para forzar la prueba.

## Etapa 10 — Movimiento individual y deshacer de sesión

Usar solo los archivos ficticios y dos subcarpetas locales en el mismo volumen.

- [ ] **10.1 · Cancelar:** cancelar el selector de destino y después cancelar el diálogo de confirmación. El archivo debe permanecer en origen.
- [ ] **10.2 · Colisión:** crear previamente un archivo ficticio con el mismo nombre en destino. CLARA debe rechazar el movimiento y preservar ambos contenidos, sin sobrescribir ni renombrar.
- [ ] **10.3 · Movimiento confirmado:** mover un solo TXT ficticio dentro del mismo volumen tras revisar origen/destino. Debe aparecer en destino y desaparecer del origen.
- [ ] **10.4 · Deshacer:** confirmar **Deshacer** en la misma ventana. Debe volver al origen si no cambió y el origen está libre; si hay conflicto/cambio, debe negarse sin forzar.
- [ ] **10.5 · Fin de sesión:** opcionalmente hacer otro movimiento ficticio y cerrar la ventana; confirmar que no se promete ni ofrece deshacer persistente tras cerrar.

## Etapa 11 — Aplicaciones aprobadas

Solo si existe ya una aplicación gráfica conocida, que la usuaria elija, instalada bajo `Program Files` o `LocalAppData\Programs`. No instalar una aplicación para completar la prueba. Si no hay una candidata segura permitida, marcar `Bloqueado`.

- [ ] **11.1 · Alta sin lanzamiento:** elegir la ruta del `.exe` gráfico existente y confirmar el alta. La aplicación no debe arrancar durante el alta.
- [ ] **11.2 · Confirmación de inicio:** pedir el inicio desde el administrador; cancelar la confirmación y verificar que no arranque. Volver a intentarlo y confirmar solo si la usuaria lo autoriza; comprobar que inicia el ejecutable exacto sin argumentos.
- [ ] **11.3 · Retirar permiso:** retirar la autorización y confirmar que ya no se ofrece como autorizada. Retirarla no cierra procesos que ya estuvieran abiertos.
- [ ] **11.4 · Rechazos:** verificar que no acepte accesos directos, intérpretes, consola, instaladores ni rutas fuera de las raíces permitidas. No probar ejecutando ningún archivo rechazado.

## Etapa 12 — Permisos, actividad, copias y mantenimiento

Las pruebas de restauración y borrado deben hacerse solo en una cuenta de Windows desechable sin datos personales.

- [ ] **12.1 · Centro y revocación:** abrir Privacidad y permisos; entrar a cada preferencia/administrador enlazado; retirar una app de prueba. Confirmar que la búsqueda no recuerda raíces y que el estado de micrófono refleja push-to-talk/apagado cuando no se solicita.
- [ ] **12.2 · Actividad mínima:** completar una acción confirmada de prueba y revisar el historial. Debe registrar categoría/resultado sin nombres de archivo, rutas ni consulta de búsqueda. Exportar CSV y revisar que conserva esa minimización; borrar el historial de prueba con confirmación.
- [ ] **12.3 · Exportación:** crear respaldo de los datos ficticios en una ubicación local privada. Confirmar que el ZIP no está cifrado y contiene solo `asistente.db` y `settings.json`; no contiene la clave DPAPI de VirusTotal. No compartir el ZIP.
- [ ] **12.4 · Restauración válida:** solo en la cuenta desechable, restaurar un respaldo ficticio, confirmar el aviso y verificar la copia automática previa y los datos restaurados.
- [ ] **12.5 · Rechazo/restauración fallida:** en la cuenta desechable, intentar restaurar un ZIP ficticio inválido o con miembro adicional/duplicado. Debe rechazarse sin reemplazar los datos de prueba actuales.
- [ ] **12.6 · Borrado:** solo con datos ficticios en cuenta desechable, comprobar que el borrado requiere escribir `BORRAR` y una confirmación final. No activar en el perfil principal.
- [ ] **12.7 · Fuente de actualización:** no hay aún un canal oficial verificado. Mantener “actualización automática desactivada”; no aprobar enlaces ni comprobaciones automáticas hasta que se defina expresamente una fuente oficial.

## Cierre

- [ ] Sin cambios inesperados en archivos/datos, sin llamadas fuera de las previstas y sin ampliación de permisos.
- [ ] Los fallos tienen incidencia reproducible, versión y pasos; corregir y repetir la prueba afectada más regresiones.
- [ ] El EXE/ZIP solo se considera candidato de entrega cuando no haya fallos críticos y las pruebas obligatorias estén marcadas como aprobadas o justificadamente bloqueadas.

**Resultado global:** ________  **Incidencias / pasos que fallaron:** __________________________________________
