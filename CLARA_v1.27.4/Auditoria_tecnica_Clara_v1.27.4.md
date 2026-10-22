# Auditoría técnica breve — CLARA v1.27.4

**Fecha:** 17 de octubre de 2026  
**Alcance:** mejora de visibilidad del chat, diagnóstico de salida de voz y corrección de pruebas temporales en Windows.

## Resultado de esta actualización

- Marca visible y artefactos activos actualizados a **CLARA — Centro Local de Asistencia, Rutinas y Agenda**.
- Se actualizó la versión de la aplicación y el nombre del ZIP portable generado en Windows a **v1.27.4**.
- Se reforzó la validación de la raíz de búsqueda: ahora revisa los componentes de la ruta de forma léxica y rechaza raíces dentro de ancestros ocultos o enlazados, además de los controles existentes sobre la carpeta final.
- Se endureció la extracción de respaldos: solo acepta `asistente.db` y `settings.json`, rechaza miembros adicionales/duplicados y aplica límites al tamaño declarado y al flujo descomprimido.
- Se reorganizó el panel de chat con `grid` para reservar espacio a la entrada de texto y controles de voz; el historial puede encogerse en pantallas con poco alto. Se redujo el tamaño mínimo de ventana.
- Se añadió `diagnosticar_voz.bat`/`.py` para probar manualmente `pyttsx3` y listar las voces disponibles, sin micrófono ni red. El constructor Windows incorpora `pyttsx3` en el paquete portable.
- Se alinearon el launcher de terminal (`iniciar_clara_terminal.bat`), el script de pruebas (`probar_clara.bat`), referencias de documentación, prototipos y scripts.
- Se conserva `%USERPROFILE%\\AsistentePersonal` como directorio de datos. No se movió, recreó ni borró la base de datos ni las preferencias existentes. El nombre fijo de las tareas del Programador de tareas se mantiene para evitar crear una segunda tarea bajo un identificador nuevo.
- El historial persistido es compatible: entradas antiguas cuyo autor se llamaba `Luma` se presentan como `Clara` en el chat, la vista previa y el CSV exportado; no se migra ni modifica la fila guardada original.

## Pruebas ejecutadas aquí

- `python -m py_compile app.py tests/test_app_helpers.py` — aprobado.
- `python -m unittest discover -s tests -v` — **23 pruebas aprobadas**.
- Añadida prueba de compatibilidad del nombre de autor del historial anterior.
- Añadidas pruebas de raíz seleccionada bajo ancestro oculto y ruta de enlace.
- Añadidas pruebas del extractor de respaldos: miembro inesperado, duplicado, ausente y límites de tamaño.
- Creada `Pruebas_aceptacion_Windows_etapas_8-12.md`, con casos manuales para las etapas 8–12; no ejecutada aún.
- Corregidos los fixtures de pruebas para Windows: como `%TEMP%` suele estar bajo `AppData` y puede heredar atributos ocultos, los tests ahora ignoran únicamente esos ancestros del directorio temporal desechable; siguen aplicando controles a la raíz y a todo elemento dentro del fixture. Esto no relaja la validación de la aplicación.

## Aún requiere Windows/Ollama reales

- Construir y ejecutar el EXE con `build_windows.bat` en Windows. No se afirma que se haya generado ni validado un EXE Windows en este entorno.
- Verificar visualmente en Windows que el campo “Escribe un mensaje para Clara” y los controles inferiores estén visibles con la resolución/escala de la usuaria.
- Ejecutar `diagnosticar_voz.bat`, verificar voces/dispositivo de salida y confirmar que una respuesta conversacional se reproduce si la opción está activada. La rutina de noticias/estados no se lee como respuesta de chat.
- Verificar launcher, notificaciones, Programador de tareas y comportamiento de preferencias/DPAPI en una cuenta de prueba. La sesión debe estar iniciada para notificaciones programadas.
- Probar la conexión local real con Ollama y el modelo, la interpretación de intents, push-to-talk y diálogos de confirmación.
- Confirmar que los datos reales de la usuaria permanecen intactos: aquí se verificó el código y la ruta configurada, no se abrió ni modificó su carpeta de datos local.

Las pruebas unitarias no certifican seguridad ni sustituyen pruebas de integración en Windows.
