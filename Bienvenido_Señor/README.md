# Viernes - Asistente Personal Inteligente

Viernes es un asistente personal local para agenda, rutinas, clases,
presupuesto, noticias, voz y aprendizaje de habitos.

## Arranque

```powershell
py viernes.py
```

Modos disponibles:

```powershell
py viernes.py --mode gui
py viernes.py --mode morning
py viernes.py --mode scheduler
```

## Voz y texto

- Chat escrito: campo inferior de la GUI, boton `Enviar` o tecla Enter.
- Voz por microfono: boton `Hablar` en la GUI.
- Push-to-talk: Alt izquierda, si el backend de microfono esta disponible.
- Comandos utiles: `activar voz`, `desactivar voz`, `estado de voz`.

Si el reconocimiento de voz no esta instalado, Viernes sigue funcionando por
texto y lo dira en el panel de Sistema.

## Aprendizaje

Viernes registra patrones de uso en `viernes_habits.json`: comandos frecuentes,
categorias, horarios de uso y actividad reciente. Puede consultar eso con:

```text
mis habitos
mis estadisticas
```

## Estructura

Ver [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

Resumen rapido:

- `viernes.py`: entrada publica.
- `viernes_app/`: codigo principal.
- `scripts/windows/`: instaladores y utilidades de Windows.
- `scripts/tools/`: herramientas de desarrollo.
- `docs/`: documentacion.
- `runtime/`: cache y archivos generados nuevos.
- `legacy/jarvis/`: version monolitica vieja conservada fuera del arranque.
- `viernes_config.json`, `viernes_state.json`, `viernes_agenda.json`,
  `viernes_budget.json`: datos vivos conservados en raiz por compatibilidad.

## Autoinicio

Desde Viernes:

```text
activar modo residente
verificar despertar
probar despertar
```

Manual:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\windows\install_viernes_autostart.ps1
```

La tarea programada ejecuta `viernes_morning.cmd` a la hora configurada en
`viernes_config.json`.

## Dependencias

```powershell
pip install -r requirements.txt
```

Instalador auxiliar:

```powershell
scripts\windows\install_dependencies.bat
```
