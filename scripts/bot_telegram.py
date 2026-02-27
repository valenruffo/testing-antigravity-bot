import os
import asyncio
import random
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from langchain_core.messages import HumanMessage

from main import graph

# 1. Cargar las credenciales
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Diccionario simple en memoria para llevar los historiales por chat_id
# En prod, se recomienda SQLiteBase o Redis usando el Checkpointer de LangGraph
MEMORY_STORAGE = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador para el comando /start"""
    chat_id = update.effective_chat.id
    # Reset del estado para este chat_id
    MEMORY_STORAGE[chat_id] = {
        "historial_mensajes": [],
        "datos_recolectados": {},
        "fase_venta": "Nueva",
        "buffer_mensajes": []
    }
    await update.message.reply_text("Hola, soy Ricardo. ¿En qué te puedo ayudar hoy?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejador de mensajes de texto"""
    chat_id = update.effective_chat.id
    user_text = update.message.text
    
    # Iniciar estado si es la primera vez que escribe sin /start
    if chat_id not in MEMORY_STORAGE:
        MEMORY_STORAGE[chat_id] = {
            "historial_mensajes": [],
            "datos_recolectados": {},
            "fase_venta": "Nueva",
            "buffer_mensajes": []
        }
        
    estado_actual = MEMORY_STORAGE[chat_id]
    
    # 1. Agregar el mensaje del humano
    estado_actual["historial_mensajes"].append(HumanMessage(content=user_text))
    
    # 2. Ejecutar el grafo de LangGraph
    # Usamos configuración vacía ya que gestionamos la memoria manualmente acá para algo simple
    config = {"configurable": {"thread_id": str(chat_id)}}
    
    # .invoke() corre hasta alcanzar END
    nuevo_estado = graph.invoke(estado_actual, config)
    
    # Actualizamos nuestra memoria
    MEMORY_STORAGE[chat_id] = nuevo_estado
    
    # 3. Leer el buffer_mensajes y enviar a Telegram humanizado
    buffer = nuevo_estado.get("buffer_mensajes", [])
    for msg in buffer:
        if msg.strip():
            # Acción "Typing..."
            await context.bot.send_chat_action(chat_id=chat_id, action="typing")
            
            # Retraso aleatorio (1 a 3 segundos)
            delay = random.uniform(1.0, 3.0)
            await asyncio.sleep(delay)
            
            # Enviar la "burbuja" con formato de Markdown
            # Telegram Original usa *asterisco simple* para negritas, así que traducimos los del LLM (**)
            msg_formateado = msg.replace('**', '*')
            try:
                await update.message.reply_text(msg_formateado, parse_mode='Markdown')
            except Exception:
                # Si falla el parseo estricto del markdown por error humano del LLM, fallback a texto plano seguro
                await update.message.reply_text(msg)

if __name__ == '__main__':
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: Por favor provee TELEGRAM_BOT_TOKEN en el archivo .env")
        exit(1)
        
    print("Iniciando a Ricardo (Telegram Bot)...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    app.run_polling()
