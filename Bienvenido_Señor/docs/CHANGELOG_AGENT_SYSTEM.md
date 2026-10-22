# Registro de Cambios: Sistema de Agentes

## Agregado

- Planificador de agentes persistido en `viernes_app/core/planner.py` con
  contexto, dependencias, dry-run y aprobacion de pasos mutables.
- Memoria persistente en `runtime/memory/` mediante `PersistentMemoryManager`,
  con API `remember(...)`, contexto para Ollama y redaccion basica de secretos.
- Router de herramientas con metadatos, permisos, origen, confirmacion,
  dry-run, reportes y flujo real de organizacion de documentos.
- Sistema de seguridad con niveles, autenticacion local ligera, deny-by-default,
  allowlist de rutas/scripts y auditoria con correlacion.
- Carga dinamica de plugins en `viernes_app/plugins/` con manifiestos
  validados, enable/disable y aislamiento de errores.
- Plugin base `system_info`.
- Auto-mejora controlada en `viernes_app/core/self_improvement/` con propuestas
  persistidas en `runtime/self_improvement/proposals/`.
- Voz extendida: perfiles, wake word configurable, interrupciones y
  conversacion continua opt-in.
- Shell moderno opcional con CustomTkinter y fallback Tkinter, activable por
  `ui.mode=modern`.
- Monitor pasivo de seguridad en `viernes_app/services/security_monitor/` con
  baseline persistente y cache de resumen.
- Monitoreo personal opt-in en `viernes_app/services/personal_activity/` con
  SQLite protegido, sesiones de apps/categorias, YouTube, juegos internos,
  eventos de runtime y retencion con agregados.
- Tests unitarios ampliados para planificador, memoria, permisos, tool router,
  plugins, auto-mejora, monitor, voz y UI opt-in.

## Integrado

- `ViernesAssistant` ahora inicializa agentes, memoria, permisos, plugins y monitor de seguridad.
- El contexto de Ollama se enriquece automaticamente con memoria persistente.
- El dashboard incluye estado de agentes, permisos, plugins, herramientas y monitor.
- Nuevos comandos: `estado agentes`, `plan agente ...`,
  `ejecutar ultimo plan agente`, `ejecutar ultimo plan agente confirmado`,
  `herramienta ...`, `memoria agente`, `monitor seguridad`, `plugins`,
  `permisos`, `mejora controlada ...`, `estado mejora controlada`,
  `activar conversacion continua`, `wake word ...`, `perfiles de voz`,
  `activar interfaz moderna`, `activar monitoreo personal`,
  `estado monitoreo personal`, `resumen actividad personal` y
  `depurar actividad personal`.

## Compatibilidad

- No se movio ni renombro `viernes.py`.
- No se agregaron archivos Python en la raiz.
- No se requiere migrar los JSON historicos.
