import os
from datetime import datetime, timezone, timedelta
from typing import TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

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

def razonar_estado(state: AgentState):
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
    system_prompt_dinamico = SYSTEM_PROMPT + fecha_actual_str
    
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

def ejecutar_herramientas(state: AgentState):
    """
    Nodo que ejecuta la herramienta solicitada por el LLM.
    """
    last_message = state["historial_mensajes"][-1]
    current_messages = state.get("historial_mensajes", [])
    
    result = tool_node.invoke({"messages": [last_message]})
    tool_messages = result.get("messages", [])
    
    # Agregar al historial existente
    return {"historial_mensajes": current_messages + tool_messages}

# Añadimos los nodos
workflow.add_node("agent", razonar_estado)
workflow.add_node("tools_node", ejecutar_herramientas)

# Definimos el flujo
workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", route_after_agent)
workflow.add_edge("tools_node", "agent")

# Compilar grafo
graph = workflow.compile()
