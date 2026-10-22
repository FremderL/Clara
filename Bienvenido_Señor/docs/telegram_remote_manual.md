# Manual: conectar Viernes por Telegram

Este manual explica como conectar Viernes a Telegram para consultas, simulaciones, tablas, reportes y comandos remotos seguros.

## 1. Que necesitas

- Viernes ejecutandose en la laptop.
- Internet disponible.
- Una cuenta de Telegram.
- Un bot creado con BotFather.
- El `chat_id` autorizado.

Telegram funciona aqui por polling (`getUpdates`), no por webhook. Puede responder desde la GUI, desde el scheduler o desde el worker residente dedicado `--mode remote`.

Para evitar spam, cuando el polling remoto arranca por primera vez descarta mensajes viejos acumulados y solo responde a mensajes nuevos posteriores.

## 2. Crear el bot

1. En Telegram, abre `@BotFather`.
2. Envia `/newbot`.
3. Ponle nombre y usuario al bot.
4. Copia el token que entrega BotFather.

Guarda ese token con cuidado. Quien tenga el token puede intentar hablar con tu bot.

Referencia oficial: https://core.telegram.org/bots y https://core.telegram.org/bots/features#botfather

## 3. Obtener tu chat_id

1. Abre el chat con tu bot.
2. Envia cualquier mensaje, por ejemplo: `hola`.
3. En un navegador, abre:

   `https://api.telegram.org/bot<TOKEN>/getUpdates`

4. Busca `message.chat.id`.
5. Ese numero es tu `chat_id`.

Si no aparece nada, revisa que ya hayas enviado un mensaje al bot y que el token sea correcto.

Referencia oficial del Bot API: https://core.telegram.org/bots/api

## 4. Configurar Viernes

Desde la GUI:

1. Abre `Configurar`.
2. Entra a la seccion `Voz y Telegram`.
3. En `Telegram`, activa Telegram.
4. Pega el token en `Token nuevo`.
5. Pega tu `chat_id`.
6. Guarda.
7. Pulsa `Probar`.

Para control remoto seguro:

1. En la misma seccion, activa `Control remoto activo`.
2. En `Owners`, agrega tu `chat_id`.
3. Deja `Confirmar cambios` activado.
4. Deja `Enviar reportes/PNG` activo si quieres recibir archivos.
5. Guarda.
6. Pulsa `Activar remoto` o escribe:

   `activar control remoto telegram`

Para que funcione aunque la GUI este cerrada:

1. En la pestana `Control Remoto`, pulsa `Activar residente`, o escribe:

   `activar remoto residente`

2. Verifica con:

   `estado remoto residente`

3. Para detenerlo:

   `desactivar remoto residente`

Tambien puedes iniciar el worker manualmente:

`python viernes.py --mode remote --loop-seconds 5`

Despues de activar el worker, envia un mensaje nuevo al bot. Los mensajes anteriores al primer polling pueden ser ignorados a proposito.
5. Pulsa `Activar remoto` o escribe:

   `activar control remoto telegram`

## 5. Configuracion esperada

Viernes guarda la configuracion en `viernes_config.json` con esta forma:

```json
{
  "telegram": {
    "enabled": true,
    "token": "TOKEN_DEL_BOT",
    "chat_id": "TU_CHAT_ID"
  },
  "remote_control": {
    "enabled": true,
    "allowed_chat_ids": ["TU_CHAT_ID"],
    "owner_chat_ids": ["TU_CHAT_ID"],
    "trusted_chat_ids": [],
    "read_only_chat_ids": [],
    "require_confirmation": true,
    "send_artifacts": true,
    "history_limit": 100,
    "poll_interval_seconds": 5,
    "blocked_intents": ["shutdown", "restart", "suspend", "delete", "cleanup_past_events"]
  }
}
```

Preferiblemente usa la GUI para no romper el JSON.

## 6. Que puede hacer por Telegram

Consultas directas:

- `que tengo hoy`
- `que clases tengo hoy`
- `estado proactivo`
- `estado de ejecuciones`
- `estado juego`

Analisis y simulacion:

- `simula si gasto 200 pesos diarios esta semana`
- `que pasaria si salgo 30 minutos tarde`
- `simula un circuito con fuente de 9v y resistencia de 330 ohms`
- `dame tus propias ideas para mejorar mi estudio`

Investigacion y tablas:

- `investiga precios de laptops y haz tabla`
- `haz una tabla de paneles solares`
- `compara autos economicos en tabla con columnas precio, consumo y ventaja`

Reportes y graficas:

- `reporte de mi dia`
- `haz una grafica de mis gastos`
- `enviame ultimo reporte`
- `enviame ultima grafica`

Juegos:

- `jugar gato`
- `jugar batalla naval`
- `jugar adivina quien`

Si envias una frase ambigua que Viernes no puede clasificar con suficiente confianza, el canal remoto la ignora en silencio. Esto evita bucles conversacionales y respuestas repetidas esperando contexto.

## 7. Confirmacion para cambios

Si el comando puede modificar datos, Viernes no debe ejecutarlo de inmediato. Primero envia botones inline `Confirmar` y `Cancelar`, y tambien mantiene el token de texto como respaldo:

`Confirmacion requerida... Responda: confirmar 1234`

Para aprobar:

`confirmar 1234`

Tambien puedes tocar el boton `Confirmar` desde Telegram. Para cancelar, toca `Cancelar` o envia `cancelar`.

El token expira despues de unos minutos y solo se usa una vez.

Ejemplos de cambios que requieren confirmacion:

- cambiar horarios
- crear eventos
- guardar memoria
- modificar salida temporal
- completar o cancelar pendientes

## 8. Limitantes actuales

- Viernes no recibe mensajes si no esta corriendo la GUI, el scheduler o `python viernes.py --mode remote`.
- Usa polling, asi que puede haber unos segundos de retraso.
- Solo acepta chats configurados como `owner`, `trusted`, `read_only` o `allowed_chat_ids` legado.
- Los chats `read_only` no pueden ejecutar cambios.
- Los chats `trusted` pueden pedir acciones, pero un owner debe aprobarlas.
- No ejecuta llamadas telefonicas reales; el adaptador de llamadas esta apagado por defecto.
- No debe desbloquear Windows ni saltarse contrasenas.
- La investigacion web es best-effort: si una fuente no trae datos claros, la tabla marca `no disponible`.
- Las simulaciones no reemplazan mediciones reales, datasheets, calculos profesionales o decisiones de alto riesgo.
- Por seguridad, Viernes solo envia automaticamente archivos de analisis desde `runtime/reports/`.

## 9. Como mejorarlo

- Agregar un panel GUI para copiar automaticamente el `chat_id` desde `getUpdates`.
- Agregar resumen diario automatico por Telegram.
- Agregar filtros finos por comando para cada usuario o grupo.
- Agregar envio de imagenes generadas que no sean reportes, con confirmacion explicita.
- Conectar un proveedor de llamadas reales solo si se acepta el riesgo y se configuran permisos claros.
