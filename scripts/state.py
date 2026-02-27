from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class DatosLead(TypedDict):
    nombre: str | None
    contacto: str | None
    presupuesto: str | None
    zona: str | None
    urgencia: str | None

class AgentState(TypedDict):
    """
    Representa el estado del grafo en LangGraph.
    """
    # Memoria de mensajes para LangChain. Usamos add_messages para concatenar el historial.
    historial_mensajes: Annotated[list[BaseMessage], add_messages]
    
    # Diccionario con la información extraída del lead
    datos_recolectados: DatosLead
    
    # "Nueva", "Calificando", "Lista_Cierre", "Agendada"
    fase_venta: str
    
    # Lista de strings con el mensaje final dividido para simular fluidez humana en Telegram
    buffer_mensajes: list[str]
