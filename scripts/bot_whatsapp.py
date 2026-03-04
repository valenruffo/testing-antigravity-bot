import os
import asyncio
import random
import requests
import re
from dotenv import load_dotenv

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage

from main import graph

# 1. Cargar las credenciales de Chatwoot
load_dotenv()
CHATWOOT_BASE_URL = os.getenv("CHATWOOT_BASE_URL", "http://chatwoot_rails:3000")
CHATWOOT_ACCOUNT_ID = os.getenv("CHATWOOT_ACCOUNT_ID", "1")
CHATWOOT_ACCESS_TOKEN = os.getenv("CHATWOOT_ACCESS_TOKEN")

# Inicializar Servidor Web
app = FastAPI(title="Chatwoot Agent Webhook")

# Memoria delegada completamente a Postgres Checkpointer
# MEMORY_STORAGE = {}

def send_chatwoot_message(conversation_id: str, text: str):
    """Envía un texto (o imagen) a la conversación en Chatwoot, quien lo retransmitirá al cliente"""
    if not CHATWOOT_ACCESS_TOKEN:
        print("ERROR: Falta CHATWOOT_ACCESS_TOKEN en .env")
        return

    url = f"{CHATWOOT_BASE_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conversation_id}/messages"
    headers = {
        "api_access_token": CHATWOOT_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }

    # Buscar si LangGraph intentó enviar una imagen en formato Markdown o como un simple enlace [alt](url)
    match = re.search(r'!?\[(.*?)\]\((.*?)\)', text)
    
    is_image = False
    image_url = ""
    if match:
        image_url = match.group(2)
        if "image" in image_url.lower() or any(ext in image_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', "encrypted-tbn0"]):
            is_image = True
            
    if is_image:
        texto_limpio = text.replace(match.group(0), "").strip()
        texto_formateado = texto_limpio.replace('**', '*')
        
        # Enviar el texto como mensaje normal
        if len(texto_formateado) > 0:
            requests.post(url, headers=headers, json={"content": texto_formateado, "message_type": "outgoing"})
            
        # Para enviar adjuntos por API en Chatwoot es más complejo (multipart/form-data o URL si lo soporta el provider)
        # Por ahora enviamos el link crudo para que WhatsApp lo parsee o lo enviamos como mensaje de texto
        data = {
            "content": image_url,
            "message_type": "outgoing"
        }
        response = requests.post(url, headers=headers, json=data)
        return response

    # 2. FLUJO NORMAL: No hay imagen, se envía como texto puro
    text_formateado = text.replace('**', '*')
    
    data = {
        "content": text_formateado,
        "message_type": "outgoing"
    }
    
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print(f"Error enviando mensaje a Chatwoot: {response.text}")
    return response

@app.get("/webhook")
async def verify_webhook():
    """Ruta GET simple por si algún servicio requiere healthcheck"""
    return {"status": "ok", "service": "Chatwoot LangGraph Bot"}

# Memoria temporal para rastrear las conversaciones que fueron transferidas a humanos
bot_off_conversations = set()

@app.post("/webhook")
async def handle_chatwoot_webhook(request: Request):
    """
    Endpoint (POST) que Chatwoot llamará cada vez que haya un evento en cualquier Inbox.
    """
    try:
        body = await request.json()
    except:
        return JSONResponse(content={"status": "error al procesar json"}, status_code=400)
    
    try:
        event = body.get("event")
        
        # Solo nos interesan los mensajes nuevos creados
        if event == "message_created":
            msg_type = body.get("message_type")
            
            # Solo procesamos mensajes "incoming" (del cliente). Ignoramos "outgoing" (nuestros o del humano)
            if msg_type != "incoming":
                return {"status": "ok"}
                
            # Extraer payload
            content = body.get("content", "")
            conversation = body.get("conversation", {})
            conversation_id = conversation.get("id")
            
            # Validar Custom Attribute: bot_status
            custom_attributes = conversation.get("custom_attributes", {})
            # Si bot_status visualmente no existe en Chatwoot (nuevo lead), lo forzamos a "on"
            bot_status_visual = custom_attributes.get("bot_status")
            bot_status = bot_status_visual or "on"
            
            if bot_status_visual is None:
                # Disparamos tarea en background para que Chatwoot actulice el Select de la UI al instante
                asyncio.create_task(fijar_estado_visual_on(conversation_id))
            
            # HITL Nativo de Chatwoot vía Custom Attribute
            if bot_status == "off":
                bot_off_conversations.add(conversation_id)
                print(f"🛑 [HITL] Mensaje en conversación {conversation_id} ignorado. El Agente apagó el Bot (bot_status=off).")
                return {"status": "ok"}
            
            # Si venimos de estar apagados y ahora estamos encendidos pero el evento fue un mensaje normal,
            # lo limpiaremos de la lista silenciosamente.
            if bot_status == "on" and conversation_id in bot_off_conversations:
                bot_off_conversations.discard(conversation_id)
            
            # Extra check para compatibilidad
            status = conversation.get("status")
            if status == "open" and bot_status != "on":
                # Respetamos el behavior viejo si está abierto pero NO explícitamente encendido
                print(f"🛑 [HITL] Mensaje ignorado. Estado OPEN sin override explícito.")
                return {"status": "ok"}
                
            # Si el mensaje no es de texto, ignoramos
            if not content:
                print("Mensaje vacío o es un adjunto sin texto.")
                return {"status": "ok"}
                
            # Pasar la carga al motor de LangGraph
            asyncio.create_task(procesar_langgraph(str(conversation_id), content))
                
        elif event == "conversation_updated":
            # Escuchamos exclusivamente actualizaciones de la conversación
            custom_attributes = body.get("custom_attributes", {})
            bot_status = custom_attributes.get("bot_status", "on")
            conversation_id = body.get("id")
            
            # Chequeamos si la conversación ya estaba off en nuestra RAM
            estaba_off = conversation_id in bot_off_conversations
            
            if bot_status == "off":
                if not estaba_off:
                    bot_off_conversations.add(conversation_id)
                    # Transición detectada de ON a OFF
                    print(f"🛑 [HITL] Conversación {conversation_id} asignada a humano manualmente. Enviando saludo temporal de transferencia.")
                    msg_despedida = "Te pondré en contacto con un agente humano. Por favor, aguarda un momento en línea."
                    asyncio.create_task(enviar_saludo_directo(conversation_id, msg_despedida))
                    
            elif bot_status == "on":
                if estaba_off:
                    bot_off_conversations.discard(conversation_id)
                    # Transición detectada de OFF a ON
                    print(f"🟢 [HITL] Conversación {conversation_id} devuelta a ON. Enviando saludo de reconexión.")
                    msg_bienvenida = "Mi compañero ha finalizado tu solicitud. ¡He regresado! Dime, ¿en qué más te puedo ayudar o qué dudas te quedaron sobre las propiedades?"
                    asyncio.create_task(enviar_saludo_directo(conversation_id, msg_bienvenida))
                            
    except Exception as e:
        print(f"Error procesando el webhook de Chatwoot: {e}")
        
    return {"status": "ok"}

async def fijar_estado_visual_on(conversation_id: int):
    """Fuerza a Chatwoot a mostrar 'on' en el dropdown de atributos de una conversación nueva"""
    import os
    import requests
    url = f"{os.environ.get('CHATWOOT_BASE_URL')}/api/v1/accounts/{os.environ.get('CHATWOOT_ACCOUNT_ID', '1')}/conversations/{conversation_id}/custom_attributes"
    headers = {"api_access_token": os.environ.get("CHATWOOT_ACCESS_TOKEN")}
    requests.post(url, headers=headers, json={"custom_attributes": {"bot_status": "on"}})

async def enviar_saludo_directo(conversation_id: int, mensaje: str):
    """
    Simplemente envía un mensaje desde el bot al inbox del usuario a través del API de Chatwoot,
    y empuja al LangGraph un SystemMessage para que recuerde que lo saludó, manteniendo las cosas sincronizadas.
    """
    send_chatwoot_message(str(conversation_id), mensaje)
    # Empujamos silenciosamente el update a LangGraph para que lo sepa si hace falta,
    # aunque con el system prompt tal vez no sea 100% necesario, enviar un mensaje con rol AI ayuda al historial.
    try:
        from main import graph
        from langchain_core.messages import AIMessage
        config = {"configurable": {"thread_id": str(conversation_id)}}
        # Esto inyecta el mensaje directo al estado como si el bot lo hubiese pensado.
        graph.update_state(config, {"historial_mensajes": [AIMessage(content=mensaje)]})
    except Exception as e:
        print(f"Error inyectando saludo de bienvenida a LangGraph: {e}")

async def procesar_langgraph(thread_id: str, user_text: str):
    """
    Función que inyecta el mensaje al Graph persistente, recupera la respuesta y empuja metadata a Zep.
    """
    from main import graph
    config = {"configurable": {"thread_id": thread_id}}
    
    # 1. Recuperar Snapshot guardado en PostgreSQL (Si existe)
    estado_previo = graph.get_state(config)
    
    # 2. Invocamos LangGraph
    if not estado_previo.values:
        # Inicialización en frío de variables obligatorias
        input_state = {
            "historial_mensajes": [HumanMessage(content=user_text)],
            "datos_recolectados": {},
            "fase_venta": "Nueva",
            "buffer_mensajes": [],
            "esperando_humano": False
        }
    else:
        # Solo inyectar el nuevo mensaje, Postgres se encarga de re-hidratar el resto
        input_state = {
            "historial_mensajes": [HumanMessage(content=user_text)]
        }
    
    nuevo_estado = graph.invoke(input_state, config)
    
    buffer = nuevo_estado.get("buffer_mensajes", [])
    bot_responses = [msg for msg in buffer if msg.strip()]
    
    # 2. Guardar en Zep para memoria semántica y summarization de largo plazo
    try:
        from main import ZEP_URL, ZEP_API_KEY
        import requests
        
        messages_payload = [{"role": "user", "role_type": "user", "content": user_text}]
        for br in bot_responses:
           messages_payload.append({"role": "ai", "role_type": "assistant", "content": br})
           
        headers = {}
        if ZEP_API_KEY:
            headers["Authorization"] = f"Api-Key {ZEP_API_KEY}"
            
        requests.post(f"{ZEP_URL}/api/v1/sessions/{thread_id}/memory", json={"messages": messages_payload}, headers=headers, timeout=3.0)
    except Exception as e:
        print(f"Error mandando datos a Zep (HTTP): {e}")
    
    # 3. Leer buffer y enviar a Chatwoot secuencialmente
    buffer = nuevo_estado.get("buffer_mensajes", [])
    for msg in buffer:
        if msg.strip():
            # Retraso aleatorio simulando escritura
            delay = random.uniform(1.0, 3.0)
            await asyncio.sleep(delay)
            
            send_chatwoot_message(thread_id, msg)

if __name__ == "__main__":
    import uvicorn
    print("Iniciando servidor de Webhooks para Chatwoot en el puerto 8000...")
    uvicorn.run("bot_whatsapp:app", host="0.0.0.0", port=8000, reload=True)
