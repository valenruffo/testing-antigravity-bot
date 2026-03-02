# Integración de Chatwoot como Bandeja de Entrada + Agent Bot

## Objetivo
Implementar Chatwoot (plataforma open-source de atención al cliente) en el VPS de Producción para proveer una interfaz gráfica a los operadores humanos. El bot de LangGraph actual dejará de conectarse directamente a Meta y pasará a ser un **Agent Bot** dentro de Chatwoot.

## El Problema Actual
Al usar la API Cloud oficial de WhatsApp, el número de teléfono se desconecta de la aplicación del celular (WhatsApp Business). Esto deja al dueño sin una herramienta cómoda para leer o interceptar los mensajes manualmente, forzándolo a depender de Meta Business Suite o interfaces rústicas.

## La Solución: Arquitectura Chatwoot
La nueva topología de red será:
`WhatsApp Cloud API <---> Chatwoot (VPS) <---> Bot FastAPI (LangGraph)`

1. **Recepción:** El cliente escribe por WhatsApp. Meta manda el Webhook a **Chatwoot**.
2. **Delegación Inicial:** Chatwoot crea la conversación y la asigna automáticamente a nuestro **Agente Bot** (FastAPI).
3. **Procesamiento:** Chatwoot le manda un Webhook a `bot_whatsapp.py`. LangGraph procesa y responde enviando el mensaje a la **API de Chatwoot** (no a Meta). Chatwoot se encarga de retransmitirlo a WhatsApp.
4. **Human in the Loop (HITL):** Cuando LangGraph decide transferir a un humano, usa la API de Chatwoot para cambiar el estado de la conversación de `bot` a `open`. 
5. **Silencio del Bot:** Al estar en estado `open`, Chatwoot notifica al humano en su pantalla y **deja de mandarle Webhooks al Bot**. El Bot calla automáticamente, y el humano toma el control desde la hermosa interfaz de Chatwoot.

## Restricciones y Casos Borde (El Bucle de Memoria)
- **Recursos del VPS:** Chatwoot consume alrededor de 2GB de RAM (necesita Postgres, Redis y Sidekiq). Si el VPS tiene menos recursos, requerirá configuración de Swap.
- **Cambio de Endpoints:** Nuestro script de FastAPI ya no recibirá el JSON de Meta, sino el JSON de Chatwoot (que tiene otro formato). Habrá que adaptar `bot_whatsapp.py`.
- **Envíos de Mensajes:** La función `send_whatsapp_message` desaparecerá. Ahora usaremos la API de Chatwoot (`/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages`) para responder.

## Plan de Ejecución
1. **Despliegue de Chatwoot:** Añadir los servicios de Chatwoot al `docker-compose.yml` del cliente.
2. **Configuración Inicial:** El usuario deberá entrar a Chatwoot, crear una Bandeja de Entrada (Inbox) de API o de WhatsApp Cloud, y crear un **Agent Bot**.
3. **Refactorización del Bot:** Modificar `bot_whatsapp.py` para parsear los payloads de Chatwoot.
4. **Refactorización de HITL:** Modificar la Tool `transferir_a_humano` para que haga un POST a Chatwoot y cambie el assignee/estado del ticket.
