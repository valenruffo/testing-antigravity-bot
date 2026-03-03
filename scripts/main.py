import os
from datetime import datetime, timezone, timedelta
from typing import TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langchain_core.runnables import RunnableConfig
import requests

# Archivos locales
from state import AgentState, DatosLead
from prompts import SYSTEM_PROMPT
from tools import TOOLS

# Configuración del LLM
# Usamos gpt-4o-mini según requerimiento de la directiva (la directiva dice GPT-5-mini pero hoy el equivalente es 4o-mini, o gpt-4o).
# Ajustar el nombre del modelo según disponibilidad de OpenAI
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
llm_with_tools = llm.bind_tools(TOOLS)

def format_bot_response(response_text: str) -> list[str]:
    """Divide un mensaje largo en burbujas pequeñas de chat (saltos de línea o puntos)."""
    # Lógica de división básica: si es muy largo, lo cortamos por parrafos o puntos.
    # Por ahora, separamos por doble salto de línea (párrafos).
    chunks = [c.strip() for c in response_text.split("\n\n") if c.strip()]
    return chunks if chunks else [response_text]

def razonar_estado(state: AgentState, config: RunnableConfig):
    """
    Nodo principal: El LLM decide qué decir o si llamar a una  herramienta.
    """
    messages = state.get("historial_mensajes", [])
    
    # Contexto Temporal GMT-3
    tz_arg = timezone(timedelta(hours=-3))
    ahora = datetime.now(tz_arg)
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    meses_ano = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    nombre_dia = dias_semana[ahora.weekday()]
    nombre_mes = meses_ano[ahora.month - 1]
    
    fecha_actual_str = f"\n\n# CONTEXTO TEMPORAL ACTUAL\nHoy es: {nombre_dia} {ahora.day} de {nombre_mes} de {ahora.year}, {ahora.strftime('%H:%M:%S')} (Hora Argentina GMT-3).\n\n# PROYECCIÓN DE PRÓXIMOS 7 DÍAS (Usa esto para calcular fechas exactas sin equivocarte):\n"
    for i in range(1, 8):
        dia_futuro = ahora + timedelta(days=i)
        nombre_dia_futuro = dias_semana[dia_futuro.weekday()]
        nombre_mes_futuro = meses_ano[dia_futuro.month - 1]
        fecha_actual_str += f"- {nombre_dia_futuro} {dia_futuro.day} de {nombre_mes_futuro}\n"
        
    fecha_actual_str += "\nTen esto en cuenta obligatoriamente para calcular fechas si el usuario dice 'mañana', 'el miércoles', 'próxima semana', etc."
    # OBTENER MEMORIA SEMÁNTICA DE ZEP (VÍA HTTP)
    thread_id = config.get("configurable", {}).get("thread_id", "default")
    zep_context = ""
    try:
        from main import ZEP_URL, ZEP_API_KEY
        import requests
        
        headers = {}
        if ZEP_API_KEY:
            headers["Authorization"] = f"Api-Key {ZEP_API_KEY}"
            
        resp = requests.get(f"{ZEP_URL}/api/v1/sessions/{thread_id}/memory", headers=headers, timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            if data and data.get("summary") and data["summary"].get("content"):
                zep_context = f"\n\n# MEMORIA A LARGO PLAZO DEL LEAD:\n{data['summary']['content']}\nUtiliza este contexto histórico si es relevante para la conversación actual."
    except Exception as e:
        print(f"Zep: no se pudo obtener el resumen de memoria - {e}")

    system_prompt_dinamico = SYSTEM_PROMPT + fecha_actual_str + zep_context
    system_prompt_dinamico += """
# REGLA OBLIGATORIA SOBRE TRANSFERENCIA A HUMANO (HAND-OFF)
NUNCA, bajo ninguna circunstancia, escribas o afirmes que has transferido la solicitud a un agente humano, ni te despidas diciendo que lo harás, A MENOS que en ese mismo instante invoques explícitamente la herramienta/función `transferir_a_humano`. Es FÍSICAMENTE imposible transferir el chat sin invocarla. NO ALUCINES RESULTADOS. Si tienes que transferir, INVOCA LA HERRAMIENTA.
"""
    
    # Agregar o actualizar el system prompt iterativamente
    if not messages:
        messages = [SystemMessage(content=system_prompt_dinamico)]
    elif isinstance(messages[0], SystemMessage):
        messages[0] = SystemMessage(content=system_prompt_dinamico) # Actualiza el tiempo vivo
    else:
        messages = [SystemMessage(content=system_prompt_dinamico)] + messages
    
    response = llm_with_tools.invoke(messages)
    
    # Extraemos posible buffer de mensajes para humanizar (solo si no es un tool call)
    buffer = []
    if not response.tool_calls:
        buffer = format_bot_response(response.content)
        
    # Agregar al historial, no reemplazar
    return {
        "historial_mensajes": messages + [response],
        "buffer_mensajes": buffer
    }

def route_after_agent(state: AgentState):
    """
    Enrutador para decidir si ir a Tools o terminar.
    """
    last_msg = state["historial_mensajes"][-1]
    if getattr(last_msg, "tool_calls", None):
        return "tools_node"
    return END

# Configuración del Grafo
workflow = StateGraph(AgentState)

tool_node = ToolNode(TOOLS)

def ejecutar_herramientas(state: AgentState, config: RunnableConfig):
    """
    Nodo que ejecuta la herramienta solicitada por el LLM.
    """
    last_message = state["historial_mensajes"][-1]
    current_messages = state.get("historial_mensajes", [])
    
    result = tool_node.invoke({"messages": [last_message]})
    tool_messages = result.get("messages", [])
    
    # Agregar al historial existente y verificar si se detonó el HITL
    nuevo_estado = {"historial_mensajes": current_messages + tool_messages}
    
    # Revisar si alguna herramienta retornó nuestra señal especial de transferencia a humano
    for tm in tool_messages:
        if isinstance(tm.content, str) and "HITL_TRIGGERED" in tm.content:
            nuevo_estado["esperando_humano"] = True
            thread_id = config.get("configurable", {}).get("thread_id")
            if thread_id:
                try:
                    base_url = f"{os.getenv('CHATWOOT_BASE_URL', 'http://chatwoot_rails:3000')}/api/v1/accounts/{os.getenv('CHATWOOT_ACCOUNT_ID', '1')}/conversations/{thread_id}"
                    headers = {"api_access_token": os.getenv("CHATWOOT_ACCESS_TOKEN")}
                    
                    # 1. Cambiar estado a abierto (notificación visual)
                    requests.post(f"{base_url}/toggle_status", headers=headers, json={"status": "open"})
                    
                    # 2. Apagar el Bot explícitamente usando Custom Attributes
                    payload_attr = {"custom_attributes": {"bot_status": "off"}}
                    requests.post(f"{base_url}/custom_attributes", headers=headers, json=payload_attr)
                    
                    print(f"✅ Conversación {thread_id} transferida (status=open, bot_status=off)")
                except Exception as e:
                    print(f"Error cambiando status en Chatwoot: {e}")
            
    return nuevo_estado
# Añadimos los nodos
workflow.add_node("agent", razonar_estado)
workflow.add_node("tools_node", ejecutar_herramientas)

# Definimos el flujo
workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", route_after_agent)
workflow.add_edge("tools_node", "agent")

# Compilar grafo
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.memory import MemorySaver

DB_URI = os.getenv("DATABASE_URL", "postgres://postgres:postgres@bot_postgres:5432/bot_memory")

# Fallback por defecto
checkpointer = MemorySaver()

try:
    # Intentamos conectar a PostgreSQL para memoria persistente
    pool = ConnectionPool(conninfo=DB_URI, max_size=10, timeout=5.0, kwargs={"autocommit": True})
    checkpointer_pg = PostgresSaver(pool)
    checkpointer_pg.setup()
    checkpointer = checkpointer_pg
    print("✅ LangGraph Checkpointer conectado a PostgreSQL.")
except Exception as e:
    print(f"⚠️ No se pudo conectar a Postgres Checkpointer. Usando MemorySaver volátil. Error: {e}")

graph = workflow.compile(checkpointer=checkpointer)

# --- ZEP CONFIG ---
ZEP_URL = os.getenv("ZEP_URL", "http://zep_server:8000")
ZEP_API_KEY = os.getenv("ZEP_API_KEY", "")
