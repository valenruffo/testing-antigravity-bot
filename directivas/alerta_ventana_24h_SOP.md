# SOP: Ventana de 24 Horas en WhatsApp Cloud API

> **OBJETIVO:** Protocolo estricto para gestionar la restricción de 24 horas de la API de Cloud de WhatsApp, implementando alertas preventivas y bloqueos de seguridad en el Agente de LangGraph.

## 🕒 El Problema: La Ventana de Sesión
Cuando un cliente envía un mensaje a través de WhatsApp, la API de Meta abre una "Ventana de Sesión" que dura exactamente **24 horas**. Durante este tiempo, el bot (o el agente humano) puede responder con mensajes de texto plano ilimitadamente.
Si la ventana se cierra (es decir, el cliente no ha enviado un mensaje en las últimas 24 horas), cualquier intento de enviar un texto plano resultará en un error bloqueante por parte de Meta y Chatwoot.

## 🛑 Arquitectura del Guardrail (Ingeniería Compuesta)

### 1. Monitoreo Activo y Retroactivo (>= 23 Horas)
El sistema debe monitorear constantemente la última actividad del cliente (`last_incoming_at`) directamente desde la fuente de verdad (la base de datos PostgreSQL de Chatwoot, tabla `messages` en el schema `chatwoot_production`). 
Cuando falte exactamente 1 hora para el cierre de la ventana (es decir, han pasado 23 horas), o incluso si han pasado **MÁS** de 24 horas (lógica retroactiva `horas >= 23.0`), el Bot generará una **Private Note** visible solo para los agentes dentro de Chatwoot.
**Mensaje de Alerta:**
`"⚠️ La ventana de 24hs de WhatsApp está por expirar. El Bot pasará a modo inactivo. Usá una plantilla paga para continuar la conversacion o espera la respuesta."`

### 2. Bloqueo de Emisión (24 Horas)
Si por algún motivo el Agente de LangGraph es invocado (por ejemplo, mediante una Tool asíncrona que tarda en resolverse, o por un error lógico) e intenta enviar un mensaje a Chatwoot después de pasadas las 24 horas exactas desde `last_incoming_at`:
- El bot **TIENE PROHIBIDO** hacer el POST a Chatwoot.
- La ejecución del envío se cortará en seco.
- Se registrará un log en consola indicando: *"Bloqueo de seguridad: Ventana de 24hs expirada, mensaje descartado."*

### 3. Consideraciones Técnicas Obligatorias
- **No depender de memoria RAM volátil:** La validación debe leerse siempre desde PostgreSQL, ya que los procesos de FastAPI pueden reiniciarse, perdiendo timers asíncronos en memoria.
- **Acceso a la BD de Chatwoot:** Se asume conexión de sólo lectura a la base `chatwoot_production` instanciada dentro de la red de Docker (no en la base default `chatwoot`).
- **Múltiples alertas (Throttling):** Se implementará un mecanismo local en RAM (`alertas_enviadas = set()`) para no inundar de notas repetidas la misma conversación una vez que la alerta de 23h ya fue emitida. Se limpia si el cliente vuelve a escribir.
- **Race Condition al Arranque:** Si el bot se despacha por Docker Compose junto con Chatwoot, Chatwoot Rails tardará unos ~40s en escuchar HTTP. Si el bot tira la Private Note de inmediato, Cloudflare responderá `502 Bad Gateway`. Se debe implementar un chequeo de error (`response.raise_for_status()`) en el bloque `try/except` para no dar la nota por enviada erróneamente en caso de fallo transitorio.
