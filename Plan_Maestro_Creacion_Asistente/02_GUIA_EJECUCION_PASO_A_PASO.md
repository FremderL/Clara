# Guía de Ejecución Paso a Paso: De 0 a Versión Final Utilizable en Windows

Esta guía resume el orden exacto de ejecución y verificación en tu equipo Windows 10/11 para poner en marcha `CLARA_Unificada` o auditar cada una de sus capas desde cero.

---

## Paso 1 — Verificación de integridad y pruebas unitarias seguras (sin tocar tus datos ni archivos)

Desde la carpeta `CLARA_Unificada`, haz doble clic en:
```bat
probar_clara.bat
```
o ejecuta en PowerShell / CMD:
```powershell
cd CLARA_Unificada
py -3 -m py_compile app.py diagnosticar_voz.py tests\test_unified_clara.py
py -3 -m unittest discover -s tests -p "test_*.py" -v
```
- **Qué comprueba:** sintaxis completa de los 3 módulos Python y las **36 pruebas unitarias** (agenda, tareas recurrentes, excepciones escolares, enrutador NLU en español, rechazo de negaciones y comandos inseguros, esfera visual, voz, RSS + caché, límites de archivos/apps, respaldos ZIP y vista previa de migración de Viernes).

---

## Paso 2 — Diagnóstico estático y audible de voz local (sin micrófono ni internet)

```powershell
cd CLARA_Unificada
py -3 diagnosticar_voz.py --check-only
```
Para escuchar la frase de prueba en voz alta en Windows:
```bat
diagnosticar_voz.bat
```
- **Qué comprueba:** disponibilidad de `pyttsx3`, detección de voz en español (`es-MX` / `es-ES`), presencia opcional de `vosk`, `sounddevice` y del modelo offline `models\vosk-model-small-es-0.42`.

---

## Paso 3 — Inicio sencillo de la versión final utilizable

Haz doble clic en:
```bat
iniciar.bat
```
o si deseas ver el chequeo de entorno en consola antes de abrir la interfaz:
```bat
iniciar_clara_terminal.bat
```
- **Qué hace:** abre la ventana principal de **CLARA Unificada v2.0.0** conectada a tu carpeta local `%USERPROFILE%\AsistentePersonal`, conservando intactas todas tus tareas, clases, rutinas y preferencias previas.

---

## Paso 4 — Lista de aceptación manual en Windows

Sigue el documento **`CLARA_Unificada/Pruebas_aceptacion_Windows_Unificada.md`** para validar manualmente con datos ficticios (y en una cuenta de prueba para restauración/eliminación):
1. Escalado DPI de Windows (100 %, 125 %, 150 %), ventana compacta (`680x440`) y expansión de la esfera visual únicamente mientras Clara habla.
2. Lectura en voz alta de respuestas y resúmenes de noticias/agenda, botón `🔊 Repetir última respuesta`, botón `🩺 Diagnóstico de voz` y dictado Push-to-Talk con transcripción editable.
3. Consultas naturales en español con y sin Ollama (`¿qué sigue?`, `¿qué tengo hoy?`, `mis clases`, `mis rutinas`, `noticias`, `clima`, `ayuda`).
4. Búsqueda/inventario en carpeta elegida cada vez, apertura/movimiento individual confirmado con deshacer en sesión, aplicaciones GUI autorizadas (máx. 10), VirusTotal manual por hash y respaldos ZIP.
