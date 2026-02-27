# Proyecto Ricardo - Broker de Lujo

## Objetivo
Desarrollar un ecosistema de agente autónomo ("Ricardo") usando LangGraph y LangChain para un bot de Telegram. Ricardo actúa como un broker inmobiliario de lujo en México. Su objetivo final es calificar leads (presupuesto, zona, urgencia) y agendar citas en Google Calendar, manteniendo una conversación natural, con alto estatus y no invasiva.

## Entradas Requeridas
- Tokens y APIs en `.env`:
  - `TELEGRAM_BOT_TOKEN`
  - `OPENAI_API_KEY`
- ID del Google Sheet Principal: `16_C-t632vZkq2c7AV1ryY3Tdiop3C6NmJdZKlup3yfE`
  - GID Propiedades: `0`
  - GID Leads: `1671406728`
- Archivo `credentials.json` en la raíz (usaremos Service Account para operaciones automáticas de Sheets, y guardaremos un archivo `token.json` si requerimos OAuth de usuario para Calendar).

## Salidas Esperadas
- Base de datos en Google Sheets actualizada con nuevos leads.
- Eventos en Google Calendar creados con links de Google Meet.
- Mensajes enviados al usuario a través de Telegram divididos en burbujas con estado `typing`.

## Lógica y Arquitectura (SOP)

### 1. Perfil y Prompting (`prompts.py`)
- **Rol:** Broker inmobiliario de lujo.
- **Tono:** Asertivo, alto estatus, profesional, cercano, con autoridad.
- **Reglas:** No repetir preguntas, comportamiento no invasivo.
- **Funcionalidad principal:** Calificar al lead (presupuesto, zona, urgencia).

### 2. Manejo de Estado (LangGraph)
Definiremos un `AgentState` (`TypedDict` o Pydantic):
- `historial_mensajes`: Lista de mensajes (memoria).
- `datos_recolectados`: Diccionario con `presupuesto`, `zona`, `urgencia`, `nombre`, `contacto`.
- `fase_venta`: Estado actual (`"Nueva"`, `"Calificando"`, `"Lista_Cierre"`, `"Agendada"`).
- `buffer_mensajes`: Lista de strings para dividir respuestas largas en Telegram.

**Nodos del Grafo:**
- `ingresar_mensaje`: Recibe input del usuario y actualiza el historial.
- `razonar_estado`: Llama a LLM para decidir si cambia de fase o invoca herramienta.
- `ejecutar_herramienta`: Ejecuta la tool elegida.
- `generar_respuesta`: Genera el texto final basado en el estado.
- `formatear_salida`: Divide el texto en partes y llena `buffer_mensajes`.

### 3. Herramientas (`tools.py`)
- `consultar_propiedades()`: Lee un Google Sheet (10 propiedades con fotos).
- `registrar_lead()`: Escribe datos del lead en otra pestaña del Sheet.
- `agendar_cita()`: Crea evento en Google Calendar (GMT-3) y devuelve link de Meet.
- `obtener_horarios_disponibles()`: Consulta agenda de Google Calendar en GMT-3 para un día dado y extrae los huecos libres.
- `reagendar_cita()`: Modifica la fecha/hora de un evento de Calendar buscándolo por correo del cliente.
- `cancelar_cita()`: Elimina un evento de Calendar buscándolo por correo del cliente.

### 4. Integración Telegram (`bot_telegram.py` & `main.py`)
- Usar `python-telegram-bot` (`ApplicationBuilder`).
- Lógica de envío:
  - Leer el `buffer_mensajes` producido por el grafo.
  - Interar sobre el buffer enviando una acción de `typing` (`bot.send_chat_action`).
  - Esperar `asyncio.sleep(random(1, 3))` segundos.
  - Enviar el fragmento del mensaje.

## Restricciones y Casos Borde (El Protocolo de Auto-Corrección)
- **Latencia de Telegram:** Si el LLM tarda demasiado, considerar enviar un mensaje de "interludio" (ej. "Déjame revisar mi portafolio..."). *Para monitorizar en desarrollo*.
- **Rate Limits de Google API:** Leer en lote si es posible. Por ahora, las sheets son pequeñas.
- **Manejo de estados con Telegram:** Hay que asegurar que cada `chat_id` tenga su propio `thread_id` en LangGraph para no mezclar leads.
- **Error ValueError: No message found in input (ToolNode)**: El `ToolNode` de prebuilt siempre asume que la llave de mensajes en el State de LangGraph se llama estrictamente `messages`. Como en esta implementación se llama `historial_mensajes`, falla. **Solución construida**: Se usa `ToolExecutor` para iterar y responder manualmente los ToolMessages.
- **Error Google Sheets `Unable to parse range`**: Significa que el código de la herramienta asume un nombre de pestaña fijo en el string de rango (ej. `'Propiedades!A:E'`) que no concuerda con lo que el cliente escribió. **Solución Construida**: Llamar a `get(spreadsheetId=ID).execute()` primero, leer `sheets[0]['properties']['title']` en el JSON y armar el string de rango dinámicamente.
- **Fallo Silencioso `No se encontraron propiedades` (Estructura de BD):** El agente no debe asumir la forma (columnas o headers) de la base de datos externa. Cuando falla asumiendo un orden de columnas (ej. cree que la columna 3 es el precio y evalúa la columna 3 que en realidad es la 'zona', arrojando 0 USD y descartando). **Solución:** Validar explícitamente el diseño o indexación provista por la tabla del cliente, adaptando el código Python a sus columnas literales (A, B, C...).
- **Lógica de Ventas / Upselling**: No filtrar de la base de datos de manera estricta por el `presupuesto_maximo` del cliente en el código en duro (`tools.py`). Se debe devolver todas las opciones de la zona solicitada y permitir que el LLM reciba toda la data para llevar a cabo estrategias de upselling si los precios no encajan textualmente (Ej. Cliente ofrece 350k, la propiedad cuesta 450k -> El broker la ofrece igual ensalzando su valor).
