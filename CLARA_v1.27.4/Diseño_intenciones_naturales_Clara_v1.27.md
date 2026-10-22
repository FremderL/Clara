# Clara v1.27 · Contrato de intenciones en lenguaje natural

**Estado:** primer pase integrado en Clara v1.27.0 y probado con tests unitarios de validador/enrutamiento. El flujo Ollama real y GUI Windows aún requieren validación.

## Objetivo

Permitir peticiones naturales para funciones existentes sin dar a Ollama capacidad de ejecutar herramientas. Ollama solo devuelve una propuesta estructurada. La app valida los campos y decide qué interfaz segura abrir. Respuesta inválida, incompleta, ambigua o fuera de alcance: ninguna acción; mostrar una aclaración o respuesta conversacional.

## Intenciones permitidas

- `general`: respuesta conversacional sin acceso a datos o acciones.
- `task_draft`: borrador de tarea; abrir formulario editable, guardar solo tras pulsar Guardar.
- `block_draft`: borrador de bloque; abrir formulario editable, guardar solo tras confirmación.
- `agenda_query`: consulta de agenda local para una fecha validada; lectura únicamente.
- `afternoon_plan`: producir borrador usando agenda local; no persistir hasta Confirmar y guardar.
- `file_search`, `file_inventory`, `file_open`, `file_move`: abrir la herramienta existente con consulta/tipo propuestos. La persona elige la raíz en cada operación; después inicia búsqueda/inventario, elige cada documento y confirma abrir o mover en su diálogo actual. Nunca seleccionar una raíz, documento o destino por inferencia del modelo.

No se admiten intents para ejecución de comandos, lectura de contenido de archivos, shell, lanzar aplicaciones, instalación, sincronización externa, consulta de VirusTotal o acciones de seguridad.

## Protocolo de datos

Ollama debe responder en JSON con una clave `intent` y campos específicos. Rechazar claves desconocidas, tipos inesperados, fechas/horas inválidas, extensiones fuera de PDF/DOCX/XLSX/PPTX/TXT/Markdown y cadenas excesivamente largas. No confiar en que el modelo respete el esquema: validar localmente todos los campos. Nunca aceptar rutas del modelo.

El clasificador recibe el mensaje escrito, hasta los últimos turnos y los recuerdos explícitos vigentes ya autorizados para Ollama local. No recibe tareas, clases, inventarios, rutas reales ni contenido de archivos. Los recuerdos se etiquetan como contexto, no como instrucciones.

## Barreras de ejecución

- La detección/clasificación jamás escribe en SQLite ni llama directamente operaciones de archivos.
- Tarea y bloque: formulario editable; Guardar requiere acto explícito del usuario.
- Agenda: consulta local de solo lectura.
- Archivos: raíz escogida cada vez, consulta de nombre/tipo, límites y DETENER cooperativo. Apertura y movimiento exigen selección/confirmación individual en el diálogo ya implementado; movimiento no permite lote ni sobrescritura y conserva destino elegido por operación.
- Una salida JSON no válida o incierta no debe intentar otra intención alternativa ni ejecutar nada.
- Mantener generación cancelable y no registrar el texto como evento de actividad. Historial de conversación continúa apagado por defecto.

## Pruebas necesarias antes de llamar la funcionalidad implementada

1. Validación del esquema: JSON malformado, intent desconocido, claves extra, tipos inválidos, inyección en campos, fechas/horas inválidas y límites de texto.
2. Casos ambiguos/negados: “no busques”, “quizá debería mover”, “¿cómo se mueven archivos?” no deben iniciar operaciones.
3. Intenciones válidas: consultas y borradores generan solo la vista prevista; no hay commits ni apertura/movimiento automáticos.
4. Archivos: el modelo no suministra raíz, archivo ni destino; cada raíz se elige manualmente; selección y confirmaciones existentes se mantienen.
5. Error/cancelación: Ollama apagado, timeout, respuesta inválida, cancelación y cambio de modelo no producen efectos secundarios.
6. Prueba manual en Windows para diálogos Tk, apertura por asociación y movimiento/deshacer; las pruebas simuladas no sustituyen esa validación.

## Secuencia

1. Implementar validador y pruebas unitarias puras.
2. Integrar clasificación en el flujo del chat con salida general y generación cancelable.
3. Conectar solo los intents existentes y verificar que la app mantiene sus diálogos de confirmación.
4. Añadir acceso natural a búsqueda/inventario y, después, apertura/movimiento como preparación de la herramienta actual; nunca como ejecución del modelo.
5. Validar visualmente en Windows antes de afirmar que la función está completa.
