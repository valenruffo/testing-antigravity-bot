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
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "ricardo_broker_secreto_2026")

# Inicializar Servidor Web
app = FastAPI(title="Ricardo Broker - WhatsApp Webhook")

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
    
    # Buscar si LangGraph intentó enviar una imagen en formato Markdown ![alt](url)
    match = re.search(r'!\[(.*?)\]\((.*?)\)', text)
    
    if match:
        alt_text = match.group(1)
        image_url = match.group(2)
        
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
                        sender_phone = message.get("from") # El número de télefono del cliente
                        
                        # Parche WhatsApp API (Argentina): Los webhooks traen el "9" (549...) 
                        # pero la API de salida exige enviarlos sin el 9 (5411...).
                        if sender_phone.startswith("549") and len(sender_phone) == 13:
                            sender_phone = "54" + sender_phone[3:]
                            
                        msg_type = message.get("type")
                        
                        # Solo procesamos texto
                        if msg_type == "text":
                            user_text = message.get("text", {}).get("body", "")
                            
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
            "buffer_mensajes": []
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
