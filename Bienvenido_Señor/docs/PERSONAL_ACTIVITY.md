# Monitoreo personal protegido

Viernes incluye un subsistema opt-in para observar actividad local de la computadora sin depender solo de teclado, mouse o comandos.

## Activacion

El monitoreo profundo no inicia por defecto. Puede activarse con:

```text
activar monitoreo personal
```

Comandos utiles:

- `estado monitoreo personal`
- `resumen actividad personal`
- `depurar actividad personal`
- `borrar actividad personal`
- `borrar actividad personal confirmado`

## Datos registrados

Modo actual: `app_category`.

Viernes registra sesiones con:

- proceso activo
- categoria de actividad
- clave de app, por ejemplo `youtube`, `code`, `chrome`
- huella hash del titulo de ventana
- eventos de arranque/parada del runtime
- juegos internos iniciados desde Viernes

No guarda titulos completos de ventana ni URLs. Los detalles sensibles se guardan en un payload protegido con DPAPI en Windows y fallback base64 fuera de Windows.

## Retencion y compactacion

Politica balanceada:

- eventos crudos: 14 dias
- sesiones: 60 dias
- agregados diarios/mensuales: 365 dias

Antes de borrar sesiones antiguas, Viernes las agrega por dia/mes, app y categoria. Esto permite conservar tendencias sin guardar historial granular indefinidamente.

## Uso inteligente

El resumen de actividad alimenta dashboard y recomendaciones:

- tiempo aproximado en YouTube
- sesiones de juego
- apps/categorias dominantes
- sesiones recuperadas tras reinicio
- sugerencias de cuidado cuando una categoria domina demasiado

El sistema es pasivo: recomienda y resume; no bloquea acciones automaticamente.
