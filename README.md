# 🤖 AI Autonomous Business Broker (Boilerplate)

![Python](https://img.shields.io/badge/Python-3.13-blue?style=for-the-badge&logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Agentic_AI-orange?style=for-the-badge)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?style=for-the-badge&logo=openai&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot_API-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white)
![Google Workspace](https://img.shields.io/badge/Google_Workspace-APIs-34A853?style=for-the-badge&logo=google&logoColor=white)

Un Agente de Inteligencia Artificial Autónomo diseñado para actuar como un **Vendedor de Alto Nivel**. Construido sobre **LangGraph** y **LangChain**, este agente no es un simple chatbot de preguntas y respuestas; es un gestor de ventas capaz de mantener conversaciones orgánicas "paso a paso", calificar leads, hacer *upselling*, leer bases de datos en tiempo real y gestionar agendamientos complejos directamente en Google Calendar.

---

## 🚀 Arquitectura y Capacidades Core

El núcleo de este proyecto es una arquitectura de grafos de estado (StateGraph) donde el LLM (GPT-4o-mini) actúa como el cerebro que razona qué herramienta usar o qué decirle al usuario basándose en el historial de la conversación y reglas estrictas de ventas.

### 🌟 Funcionalidades Principales

1. **Gestión de Interacciones (WhatsApp Cloud API):** Interfaz humana y conversacional. Incluye retrasos aleatorios para imitar el comportamiento de un humano y renderizado multimedia nativo de imágenes.
2. **Embudo de Ventas Paso a Paso:** El Agente tiene estrictamente prohibido abrumar al usuario con bloques de texto masivos. Conduce la conversación secuencialmente.
3. **Escaneo de Base de Datos (Google Sheets):** Lee dinámicamente un inventario de propiedades exclusivas, filtra por zona y utiliza estrategias de *upselling* si el presupuesto del cliente es menor al costo de la propiedad.
4. **CRM Integrado (Google Sheets):** Registra a los leads interesados en una base de datos de seguimiento, incluyendo una "Nota de IA" donde el modelo deja sus impresiones sobre el poder adquisitivo y el perfil del cliente.
5. **Agendamiento Bidireccional Complejo (Google Calendar):**
   - **Manejo de Timezones:** Motor de inyección de husos horarios (GMT-3) que le otorga al LLM consciencia temporal del "Aquí y Ahora" para evitar alucinaciones con fechas relativas ("el próximo miércoles").
   - **Lectura Matemática de Disponibilidad:** Escanea la agenda real del broker, excluye fines de semana, ajusta por horarios comerciales variables y prohíbe solapamientos. Solo ofrece rangos de 30 minutos estrictamente libres.
   - **Creación, Reagendamiento y Cancelación:** Modifica el calendario en la nube y genera automáticamente enlaces de Google Meet con la información nominal del lead capturada durante la conversación.

---

## 🛠️ Tecnologías Utilizadas

- **Framework Agentic:** `langchain`, `langgraph`, `langchain-openai`
- **Interfaces Cloud:** `google-api-python-client`, `google-auth`
- **Mensajería:** FastAPI, WhatsApp Cloud API
- **Entorno & Tipado:** `python-dotenv`, `pydantic`, `typing`

---

## 📂 Estructura del Proyecto

```text
.
├── directivas/                 # Core System de Instrucciones y SOPs (Memoria a Largo Plazo)
│   ├── cliente_prompt.md       # Reglas de negocio y personalidad del Agente
│   └── guia_despliegue...      # Guías técnicas y manuales de arquitectura
├── scripts/                    # Lógica de Ejecución Interactiva
│   ├── main.py                 # Grafo de estados, inyección de tiempo e inicialización del Agente
│   ├── bot_whatsapp.py         # Entrypoint del bot en FastAPI y renderizado visual
│   ├── tools.py                # Definición de herramientas conectadas a APIs externas
│   ├── prompts.py              # System Prompts, RAG y modelado de Embudo de Ventas
│   ├── state.py                # Tipado estricto del estado de memoria del Agente
│   └── auth_google.py          # Módulo de refresh tokens y OAuth2
├── .env                        # Variables de entorno y API Keys (no trackeado)
├── credentials.json            # Oauth Client ID de Google Cloud (no trackeado)
├── token.json                  # Tokens de refresco autorizados (no trackeado)
└── requirements.txt            # Dependencias del proyecto
```

---

## ⚙️ Instalación y Configuración (Paso a Paso)

Si deseas clonar este repositorio y desplegar tu propio Broker, sigue estos pasos:

### 1. Clonar el repositorio
```bash
git clone https://github.com/valenruffo/testing-antigravity-bot.git
cd testing-antigravity-bot
```

### 2. Configurar el Entorno Virtual
```bash
python -m venv venv
# Activar en Windows
venv\Scripts\activate
# Activar en macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Variables de Entorno (`.env`)
Crea un archivo llamado `.env` en la raíz del proyecto y añade:
```env
OPENAI_API_KEY="sk-tu-clave-aqui"
WHATSAPP_TOKEN="tu-token-temporal-meta"
WHATSAPP_PHONE_ID="tu-phone-id-meta"
WHATSAPP_VERIFY_TOKEN="my_secure_webhook_token_2026"
CLOUDFLARE_TOKEN="tu-token-de-tunel"
```

### 4. Credenciales de Google Workspace
El Agente requiere acceso a Google Sheets (CRM/Inventario) y Google Calendar.
1. Ve a [Google Cloud Console](https://console.cloud.google.com/).
2. Habilita **Google Sheets API** y **Google Calendar API**.
3. Ve a Credenciales > Crear Credenciales > ID de cliente de OAuth.
4. Descarga el archivo, renómbralo a `credentials.json` y colócalo en la raíz del proyecto.
5. Asegúrate de tener los ID de tus plantillas de Google Sheets configurados en `tools.py`.

### 5. Primera Ejecución (Autorización)
Para generar el token persistente de Google, ejecuta primero el script principal. Se abrirá una pestaña en tu navegador para que autorices el acceso a tu calendario y hojas de cálculo.

```bash
docker compose up -d --build
```
*Si todo está correcto, el panel de Docker mostrará la App y el Túnel de Cloudflare en verde.*

---

## 📈 Futuras Mejoras (Roadmap)
- [ ] **Migración a Base de Datos Persistente:** Reemplazar el diccionario `MEMORY_STORAGE` de la memoria volatil del bot por un Checkpointer de SQLite o Postgres (vía `langgraph.checkpoint.sqlite`).
- [ ] **Webhook Serverless:** Transicionar del modelo `run_polling()` a Webhooks en FastAPI para despliegues serverless masivos.
- [ ] **Integración RAG de Documentos PDF:** Permitirle al Agente enviar y analizar folletos técnicos de productos directamente en WhatsApp.

---

> *"Desarrollado como prueba de concepto de interacciones humano-computadora guiadas por lógica de grafos y modelos fundacionales".*
