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

# 1. Cargar las credenciales
load_dotenv()
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "my_secure_webhook_token_2026")

# Inicializar Servidor Web
app = FastAPI(title="WhatsApp Agent Webhook")

# Memoria local volatil (Igual que Telegram)
# En prod usar SQLiteBase o Checkpointer de LangGraph
MEMORY_STORAGE = {}

def send_whatsapp_message(to_number: str, text: str):
    """Envía un texto puro a WhatsApp mediante la API de Meta"""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        print("ERROR: Faltan credenciales de WhatsApp en .env")
        return

    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Buscar si LangGraph intentó enviar una imagen en formato Markdown o como un simple enlace [alt](url)
    match = re.search(r'!?\[(.*?)\]\((.*?)\)', text)
    
    is_image = False
    if match:
        image_url = match.group(2)
        # Verificar si el enlace apunta a un archivo multimedia
        if "image" in image_url.lower() or any(ext in image_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', "encrypted-tbn0"]):
            is_image = True
            
    if is_image:
        alt_text = match.group(1)
        
        # Eliminar el bloque de markdown del texto para que no se vea feo
        texto_limpio = text.replace(match.group(0), "").strip()
        texto_formateado = texto_limpio.replace('**', '*')
        
        # WhatsApp tiene un límite estricto de 1024 caracteres para los captions (pie de foto) de imágenes.
        if len(texto_formateado) > 1000:
            # Mandamos la imagen sola y después el texto aparte
            image_data = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "image",
                "image": {"link": image_url}
            }
            requests.post(url, headers=headers, json=image_data)
            
            # Recursivo para mandar el resto del texto como mensaje normal
            texto_formateado = texto_formateado[:4096] # Limite de texto normal
            return send_whatsapp_message(to_number, texto_formateado)
        else:
            # Mandamos la imagen con el texto como caption
            image_data = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "image",
                "image": {
                    "link": image_url,
                    "caption": texto_formateado
                }
            }
            response = requests.post(url, headers=headers, json=image_data)
            if response.status_code != 200:
                print(f"Error enviando imagen WhatsApp: {response.text}")
            return response

    # 2. FLUJO NORMAL: No hay imagen, se envía como texto puro
    text_formateado = text.replace('**', '*')
    
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text_formateado}
    }
    
    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        print(f"Error enviando mensaje WhatsApp: {response.text}")
    return response

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: int = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """
    Endpoint (GET) requerido por Meta para validar la autoría del Webhook.
    Se ejecuta una sola vez cuando el usuario configura la URL en el panel de Meta.
    """
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        print("WEBHOOK VERIFICADO EXITOSAMENTE POR META")
        return hub_challenge
    raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/webhook")
async def handle_whatsapp_message(request: Request):
    """
    Endpoint (POST) que Meta llamará cada vez que un cliente te envíe un mensaje a tu número de WhatsApp.
    """
    try:
        body = await request.json()
    except:
        return JSONResponse(content={"status": "error parsing json"}, status_code=400)
    
    # Los webhooks de WA tienen una estructura anidada profunda que debemos parsear
    # Referencia: https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples
    try:
        if body.get("object") == "whatsapp_business_account":
            for entry in body.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    
                    # Ignorar status updates (read, delivered, sent)
                    if "messages" in value:
                        message = value["messages"][0]
                        sender_phone = message.get("from") # Quién envió el mensaje
                        
                        # Parche WhatsApp API (Argentina): Los webhooks traen el "9" (549...) 
                        # pero la API de salida exige enviarlos sin el 9 (5411...).
                        if sender_phone.startswith("549") and len(sender_phone) == 13:
                            sender_phone = "54" + sender_phone[3:]
                            
                        msg_type = message.get("type")
                        
                        # --- SHADOW COMMANDS (Reactivación por el Administrador) ---
                        # Meta permite Message Echoes (mensajes enviados por la propia empresa desde el celular).
                        is_echo = False
                        if "context" in message and message["context"].get("from") == WHATSAPP_PHONE_ID:
                            is_echo = True
                            
                        if sender_phone == WHATSAPP_PHONE_ID or is_echo:
                            if msg_type == "text":
                                texto_sombra = message.get("text", {}).get("body", "").strip()
                                
                                # Inferir a quién le escribimos
                                destino = message.get("to")
                                if destino and destino.startswith("549") and len(destino) == 13:
                                    destino = "54" + destino[3:]
                                    
                                if destino and texto_sombra == "/bot_resume":
                                    estado_usuario = MEMORY_STORAGE.get(destino, {})
                                    if estado_usuario and estado_usuario.get("esperando_humano"):
                                        estado_usuario["esperando_humano"] = False
                                        print(f"✅ [HITL] Agente RESUCITADO manualmente para el cliente {destino}.")
                                        send_whatsapp_message(destino, "Hola de nuevo. El administrador ha finalizado su sesión. Sigo a tu entera disposición.")
                                        
                            # Es un Echo nuestro, cortamos acá para no auto-respondernos
                            return {"status": "ok"}
                        # --- FIN SHADOW COMMANDS ---
                            
                        # Solo procesamos texto entrante de los clientes reales
                        if msg_type == "text":
                            user_text = message.get("text", {}).get("body", "")
                            
                            # HITL Check: Si el usuario está en modo Manual, bloqueamos a LangGraph
                            estado_usuario = MEMORY_STORAGE.get(sender_phone, {})
                            
                            # PARCHE DE PRUEBAS: Permitimos que el propio cliente despierte al bot si manda el comando
                            # Esto es útil dado que las Cuentas de Prueba de Meta no soportan message_echoes
                            if user_text.strip() == "/bot_resume" and estado_usuario.get("esperando_humano", False):
                                estado_usuario["esperando_humano"] = False
                                print(f"✅ [HITL] Agente RESUCITADO desde el lado del cliente (Modo Prueba) {sender_phone}.")
                                send_whatsapp_message(sender_phone, "Hola de nuevo. El administrador ha devuelto el control. Sigo a tu entera disposición.")
                                return {"status": "ok"}
                                
                            if estado_usuario.get("esperando_humano", False) == True:
                                print(f"🛑 [HITL] Mensaje de {sender_phone} ignorado. El chat está en modo manual o transferido.")
                                return {"status": "ok"}
                                
                            # Pasar la carga al motor de LangGraph asíncronamente para no bloquear el webhook que Meta espera en < 3 segs
                            asyncio.create_task(procesar_langgraph(sender_phone, user_text))
                            
    except Exception as e:
        print(f"Error procesando el payload de WA: {e}")
        
    # Siempre retornar 200 OK rápido a Meta para que no anulen el Webhook
    return {"status": "ok"}

async def procesar_langgraph(sender_phone: str, user_text: str):
    """
    Función que inyecta la memoria, llama a GPT/LangGraph y devuelve los mensajes fragmentados.
    """
    # Iniciar estado si es la primera vez que escribe
    if sender_phone not in MEMORY_STORAGE:
        MEMORY_STORAGE[sender_phone] = {
            "historial_mensajes": [],
            "datos_recolectados": {},
            "fase_venta": "Nueva",
            "buffer_mensajes": [],
            "esperando_humano": False
        }
        # El LLM de LangGraph será el único encargado de enviar el saludo inicial basándose en el prompt.
        
    estado_actual = MEMORY_STORAGE[sender_phone]
    
    # 1. Agregar el mensaje del humano
    estado_actual["historial_mensajes"].append(HumanMessage(content=user_text))
    
    # 2. Ejecutar el grafo de LangGraph
    config = {"configurable": {"thread_id": str(sender_phone)}}
    nuevo_estado = graph.invoke(estado_actual, config)
    
    # Actualizamos memoria
    MEMORY_STORAGE[sender_phone] = nuevo_estado
    
    # 3. Leer buffer y enviar a WhatsApp de a pedazos simulando velocidad de escritura
    buffer = nuevo_estado.get("buffer_mensajes", [])
    for msg in buffer:
        if msg.strip():
            # Retraso aleatorio (1 a 3 segundos) para simular escritura humana
            delay = random.uniform(1.0, 3.0)
            await asyncio.sleep(delay)
            
            # WhatsApp no tiene 'typing indicator' programático en la API,
            # así que el retraso solo nos ayuda a espaciar las notificaciones del lado del cliente.
            send_whatsapp_message(sender_phone, msg)

if __name__ == "__main__":
    import uvicorn
    # Corre el servidor localmente en el puerto 8000
    print("Iniciando servidor de Webhooks de WhatsApp en el puerto 8000...")
    uvicorn.run("bot_whatsapp:app", host="0.0.0.0", port=8000, reload=True)
