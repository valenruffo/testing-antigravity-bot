# Protocolo Human-in-the-Loop (HITL) para WhatsApp Cloud API

Este documento define la arquitectura exacta de cómo el Agente interactúa y cede el control a un operador humano en un entorno de producción de WhatsApp.

---

## 🏗️ 1. Aislamiento por Chat Individual (La regla de Oro)

**Sí, el silencio es estrictamente por chat individual.**

El cerebro de LangGraph y la memoria de FastAPI (`MEMORY_STORAGE`) guardan el estado de cada número de teléfono de forma independiente. Si el Cliente A (ej: +54911...) pide hablar con un humano, el Bot **solamente** se pausará para el Cliente A. 

Si en ese mismo segundo el Cliente B escribe para pedir precios, el Bot le responderá al Cliente B con total normalidad.

## 🚨 2. ¿Cómo se entera el Humano de que debe intervenir?

Cuando el LLM decide usar la herramienta `transferir_a_humano()`, ocurren dos cosas en el backend casi al mismo tiempo:

1. **Mensaje al Cliente (Auto-Respuesta)**: El bot responde al cliente: *"Te entiendo perfectamente. Aguarda un momento en línea, estoy transfiriendo tu caso a uno de nuestros asesores para que te asista personalmente."*
2. **Notificación al Operador (La Alerta)**: El bot enviará una notificación asíncrona urgente. Como WhatsApp Cloud API no permite "mensajes a uno mismo" fácilmente, la mejor práctica en este sistema base es que **el Bot envíe un mensaje a un Grupo de Telegram privado del equipo de ventas**, o dispare un correo electrónico.
   * *Ejemplo de Alerta Interna:* 🚨 **¡Atención Humana Requerida!** El cliente +549112345678 ha solicitado hablar con un operador. El bot ha sido pausado para este número.

## 💬 3. ¿Cómo habla el humano con el cliente? 

El operador humano (tú o tu cliente, el dueño de la pizzería/inmobiliaria) simplemente abre la aplicación de **WhatsApp Business regular en su celular o WhatsApp Web** y busca el chat de esa persona.

A partir de ese momento, el humano chatea normalmente. Al estar la variable `esperando_humano = True` en la memoria del servidor de Oracle, cada vez que el cliente responda, FastAPI recibirá el webhook, pero dirá: *"Ah, este cliente está en modo manual, ignoro el mensaje"*. El LLM de OpenAI ni se entera.

## 🔄 4. El Comando de Reactivación (`/bot_resume`)

Una vez que el humano resolvió el problema del cliente, cerró la venta, o simplemente quiere devolverle el cliente a la Inteligencia Artificial, necesita una forma de decírselo al servidor.

El método más robusto y universal (sin requerir paneles web adicionales) es usar "Comandos Ocultos" directamente en el chat de WhatsApp.

> ⚠️ **Nota Histórica:** Este flujo fue el diseño original basado en WhatsApp Cloud API pura. En la arquitectura actual con Chatwoot, la reactivación del bot se hace simplemente cambiando el atributo `bot_status` a `on` desde el selector en el panel de Chatwoot. El comando `/bot_resume` ya no se usa.

**El Flujo de Reactivación:**
1. Tú (el humano), desde tu celular de WhatsApp Business, le envías un mensaje literal al cliente que diga: `/bot_resume`
2. El servidor de Oracle, que sigue escuchando *todos* los mensajes salientes y entrantes, detecta esa cadena de texto exacta proveniente de *tu* número de teléfono.
3. El servidor busca al cliente en memoria, cambia `esperando_humano = False`, y borra el `/bot_resume` para que no quede en la base de datos de Langchain.
4. (Opcional) El bot puede mandar un mensaje automático: *"Hola de nuevo! El asesor ha finalizado la asistencia. Sigo a tu disposición."*

*(Nota: En WhatsApp Cloud API, los mensajes salientes no siempre se disparan como webhooks normales. Por esto, la implementación real requiere que escuchemos el webhook `message_echoes` (mensajes enviados por la propia empresa).*
