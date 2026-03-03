# Arquitectura Integral: Agente Inmobiliario Autónomo (Omnicanal)

Esta documentación proporciona una visión técnica, funcional y de infraestructura de extremo a extremo de cómo opera el bot inteligente para Bienes Raíces. El sistema conecta **WhatsApp Oficial (Meta)** con un CRM Omnicanal (**Chatwoot**), orquestando las respuestas mediante un agente neuro-lingüístico (**LangGraph / OpenAI**) capaz de agendar eventos (Google Calendar) y salvar métricas (Google Sheets), todo sobre un VPS seguro aislado mediante Docker y Cloudflare.

---

## 1. El Flujo de Vida de un Mensaje (Paso a Paso)

Para entender cómo funciona tu bot, imagina el recorrido de un mensaje desde que un Lead (Cliente potencial) agarra su celular:

1. **📱 El Cliente Escribe en WhatsApp:** El lead envía un "Hola" a tu número de WhatsApp Business Oficial.
2. **🌐 Meta (Facebook) Intercepta:** Al ser la API Cloud de WhatsApp oficial, los servidores de Meta reciben el mensaje y disparan un `Webhook` (una alerta web).
3. **💬 Chatwoot lo Atrapa:** El Webhook de Meta viaja hasta tu servidor y entra a la bandeja de `Chatwoot`. Chatwoot renderiza el mensaje visualmente en tu pantalla (como si fuera WhatsApp Web).
4. **🧠 Chatwoot Activa el Cerebro:** Instantáneamente, Chatwoot se da cuenta de que recibió un mensaje nuevo y dispara *su propio Webhook* hacia nuestro microservicio en Python (FastAPI).
5. **⚙️ FastAPI Procesa:** Nuestro endpoint (`POST /webhook`) en Python recibe el paquete de Chatwoot. Revisa el parámetro `bot_status` de la conversación:
   - Si está en `off` (apagado), el bot ignora el mensaje silenciosamente.
   - Si está en `on` (o vacío), le pasa el ID de la conversación y el texto al motor heurístico: **LangGraph**.
6. **🤖 LangGraph y OpenAI Analizan:**
   - LangGraph busca en su memoria qué se habló antes en esta conversación.
   - Le envía todo a GPT-4o-mini (OpenAI) junto con las instrucciones maestras del Vendedor (System Prompt).
   - OpenAI devuelve una respuesta o bien decide **usar una Herramienta** (Google Calendar, Google Sheets o "Transferir a Humano").
   - LangGraph ejecuta las herramientas de manera autónoma iterando los resultados.
7. **📤 El Bot Responde:** LangGraph le pide a Python que envíe la respuesta final de regreso usando la **API interna de Chatwoot** (endpoints ocultos). 
8. **🔄 Bucle Reverso de Entrega:** Chatwoot recibe la petición de Python, la guarda en su base de datos visual para que tú leas lo que dijo el bot, y finalmente, se lo reenvía a Meta para que aparezca en el WhatsApp real del cliente.

¡Todo esto ocurre en apenas 2 a 4 segundos!

---

## 2. Tecnologías y "El Por Qué"

- **LangGraph (LangChain):** No es un simple script de chat. LangGraph permite crear "Agentes" que pueden entrar en bucles de razonamiento (`Razonar -> Actuar (Tools) -> Observar -> Responder`). Es la columna vertebral que le da el libre albedrío estructurado al bot para interactuar con hojas de cálculo y calendarios sin hardcodear comandos fijos.
- **FastAPI (Python):** El servidor que atrapa los mensajes en milisegundos. Se eligió por ser extremadamente ligero, asíncrono y robusto para tráfico alto de webhooks.
- **Chatwoot (Ruby on Rails + Sidekiq + Postgres):** Es tu interfaz gráfica de usuario. Actúa como el muro fronterizo entre Meta y tú. Permite una vista omnicanal. Elegimos usar Chatwoot como "puente" y no Meta directo en Python, porque te permite leer los chats en tiempo real sin romper los flujos de la API y contar con un panel de analíticas empresarial. Sus procesos en segundo plano (Sidekiq) son los responsables del envío asíncrono de mensajes.
- **Docker & Docker Compose:** Todo el bot y las piezas pesadas de Chatwoot (bases de datos Redis, Postgres, procesos en segundo plano) conviven en cajas selladas. Así garantizamos que funcione hoy y en 5 años de la misma manera, levantándose todo con 1 solo comando.
- **Cloudflare Zero Trust (Túneles):** Tu VPS está protegido en un búnker. Literalmente no abriste ningún puerto de internet para recibir WhatsApp. Cloudflare instaló un "Túnel" persistente `whatsapp_bot_tunnel` que conecta tu contenedor directo a los servidores perimetrales globales de Cloudflare, traduciendo tus `.com.ar` hacia los contenedores correspondientes de forma invulnerable a DDoS.

---

## 3. Human-In-The-Loop (HITL): Control Total Manual y Automático

El Agente neuro-lingüístico tiene la orden secreta de avisarte (con una Tool llamada `transferir_a_humano()`) cuando detecta que:
- El cliente pierde la paciencia.
- El cliente pide un asesor real.
- Hay un trámite hipotecario crítico donde el Bot prefiere no hacerse responsable.

### ¿Qué hace el Bot cuando transfiere?
1. Se conecta a la API de Chatwoot silenciosamente.
2. Inyecta la directiva visual de cambiar la conversación a estado **Abierto** para que te salte la campanita `Status = open`.
3. Inyecta el "Custom Attribute" o Atributo Personalizado de Conversación `bot_status = off`.
4. A partir de esa décima de segundo, el bot de FastAPI recibe los mensajes pero dice *"Ignorando mensaje, el Agente apagó el bot"*.
5. Tú entras, lees, respondes como un humano. Cuando terminas, si quieres que el bot siga lidiando por ti para las próximas interacciones (ejemplo, que confirme una cita mañanera), **simplemente devuelves el menú derecho `Estado del Bot` hacia `on`**.

---

## 4. Estructura de Proyecto en el VPS

El corazón del proyecto alojado dentro del VPS se compone de:

```text
/home/ubuntu/testing-antigravity-bot
├── 📁 directivas/          - Tu "Cerebro Organizacional". Archivos .md donde defines los flujos y guías para el desarrollo evolutivo del bot y tu equipo IT.
├── 📁 scripts/             - El corazón lógico en Python puro.
│   ├── bot_whatsapp.py     - Recibe webhooks de Chatwoot y reescribe los payload en texto limpio.
│   ├── main.py             - La tubería LangGraph. Invoca OpenAI, y contiene la Tool que te pasa el chat.
│   ├── prompts.py          - Las instrucciones verbales y personalidad (System Prompt) de la Inmobiliaria.
│   ├── state.py            - Tipados estrictos. "La memoria de trabajo del Bot".
│   └── tools.py            - Herramientas conectadas a la civilización (Escribir Sheets, Crear Citas, etc).
├── docker-compose.yml      - "El Mapa Urbano". Aquí se levantan 5 componentes de Chatwoot y tu contenedor App Python.
├── .env                    - Credenciales maestras. Todos los IDs de Chatwoot, los Tokens de Facebook y OpenAI.
├── .tmp/deploy_vps_*.ps1   - Automatismos tuyos para traer código limpio al Servidor y redesplegarlo sin sudar.
└── README.md               - Este mismo documento integrador.
```

---

## 5. Mantenimiento y Extensibilidad

* **Si necesitas agregar una Herramienta nueva (ej. Mandar un PDF):** Lo haces creando una nueva función con decoración `@tool` dentro de `scripts/tools.py` y pasándola a LangGraph en `main.py`.
* **Si falla Chatwoot:** Chatwoot es una aplicación Ruby on Rails grande con procesos en segundo plano (`Sidekiq`). Siempre revisa sus registros ejecutando `docker logs chatwoot_sidekiq -f`.
* **Si falla el Bot Local:** Monitorea el contenedor `whatsapp_bot_app` usando el comando `docker logs whatsapp_bot_app -f`. Verás cómo entra cada POST de Chatwoot y qué decisiones lógicas toma Python antes de derivar el output al LLM.

FIN DEL PROTOCOLO DE CONOCIMIENTO.
