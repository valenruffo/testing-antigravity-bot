# Memoria Maestra del Sistema (Cerebro Global)

> **PROPÓSITO:** Este documento actúa como la **memoria evolutiva y global** del ecosistema de bots y automatizaciones de la Inmobiliaria. Aquí se documentan los patrones arquitectónicos, trampas tecnológicas comprobadas y estándares que DEBEN heredarse entre proyectos o al construir nuevas integraciones.

---

## 🏗️ 1. Infraestructura y Despliegue (VPS Oracle ARM64)

### 1.1 Incompatibilidad de Arquitecturas Docker (ARM64 vs AMD64)
- **Problema:** Los VPS gratuitos de Oracle Cloud suelen usar procesadores Ampere (ARM64/aarch64). Muchas imágenes oficiales de Docker (como `calcom/cal.com`) solo están compiladas para `linux/amd64`.
- **Efecto visual:** El contenedor entra en un loop de reinicio (restarting) o crashea con error `exec format error`. Si se fuerza vía emulación (`--platform linux/amd64`), aplicaciones pesadas basadas en Node.js/Next.js (Prisma, V8) fallan con errores de segmentación de memoria (`SIGSEGV`).
- **Solución Definitiva:** 
  1. Si la imagen NO soporta ARM64 de forma nativa, **NO forzar emulación QEMU**.
  2. Buscar alternativas SaaS (ej: usar *Cal.com Cloud* plan Free mediante API, en lugar de renegar semanas intentando levantar el self-hosted).

### 1.2 Limpieza y Cache de Docker
- **Problema:** Al hacer deploy repetitivo, Docker en el VPS puede corromper el caché manifestando errores como `parent snapshot <id> does not exist`.
- **Solución:** Ejecutar `docker builder prune -fa` antes de reconstruir la imagen con `docker compose build --no-cache`.

### 1.3 Túneles de Cloudflare (Zero Trust)
- **Patrón Exitoso:** NUNCA exponer puertos HTTP(S) directamente en el VPS. Todo servicio web (como Chatwoot o el Webhook de FastAPI) debe exponerse a internet ÚNICAMENTE a través de un contenedor `cloudflared`. Esto nos protege de ataques DDoS masivos y nos da SSL gratis automágicamente sin configurar Nginx ni Certbot.

---

## 🤖 2. Diseño Core del Agente (LangGraph + FastAPI)

### 2.1 Tool Calling y Parámetros Obligatorios
- **Trampa Técnica:** Ocurre que la documentación de una API dice que un parámetro es opcional, pero en la práctica (ej. Cal.com bookings endpoint v2) la reserva fallará sin él (ej: el email del cliente `attendee.email`).
- **Mejor Práctica (Validación Temprana):** Nunca dejar que la herramienta de Python (`@tool` en LangGraph) haga la llamada a la API si faltan parámetros lógicos de negocio. La herramienta debe validar primero (ej. `if not email_cliente:`) y devolver un string en lenguaje natural al LLM: *"Falta el email del cliente. Pídele el email primero antes de volver a llamar esta herramienta"*. Esto saca al bot del loop de error técnico y le da instrucciones claras de qué hacer.

### 2.2 TimeZones y Manejo del Tiempo
- **Problema:** El LLM (GPT-4o / GPT-4o-mini) vive "fuera del tiempo" y si se le pide que agende, agendará en formato UTC sin darse cuenta de qué hora es del lado del usuario.
- **Solución:** 
  1. Inyectar siempre en el `system_prompt` un bloque dinámico calculando el "Hoy" y proyectando los próximos 7 días con fechas exactas (ej: "Hoy es Miércoles 4 de Marzo de 2026. Jueves 5 de Mar, Viernes 6 de Mar...").
  2. Cuando el LLM invoca herramientas de agenda (ej. `agendar_cita_calcom`), forzar que la herramienta reciba la hora local (que pensó el bot), pero *dentro* del script Python hacer la conversión `Timezone` explícita antes de tocar cualquier API externa.

### 2.3 Reglas de Presentación vs. Restricciones Verdaderas
- **Problema de "Alucinación por Ocultamiento":** Si en el prompt o en el retorno de una Tool pones una regla como *"Sólo ofrécele 3 opciones al cliente"*, el modelo puede llegar a creer que *esas 3 opciones son las ÚNICAS que existen en el calendario*, negando disponibilidad si luego el cliente pide una distinta.
- **Solución:** Escribir reglas explícitas de capa de presentación: *"REGLA DE PRESENTACIÓN: Muestra solo 3 opciones para no abrumar. PERO tú conoces toda esta lista interna. Si el cliente sugiere un horario válido de esta lista original, acéptalo sin problemas."*

---

## 🔌 3. Interacciones con Servicios de Terceros

### 3.1 Chatwoot (El Muro Fronterizo)
- **Patrón HITL (Human-in-the-Loop):** Para apagar el bot en un chat específico de WhatsApp, es mandatorio usar la API de **Custom Attributes** de Chatwoot (`bot_status = "off"`). No intentar crear sistemas de estado paralelos, Chatwoot es la fuente de verdad del estado de la conversación.

### 3.2 Cal.com API v2
- **Diferencia Crítica de Versiones:** La API v1 (`/api/v2/slots/available`?) no existe. En v2 el endpoint correcto de disponibilidad es `GET /v2/slots` y los parámetros son `start`, `end`, y `timeZone`.
- **Keys del objeto Slot:** Cada horario devuelto por `/v2/slots` se mapea usando la clave `s["start"]` (no `s["time"]`). Leer documentación y siempre probar un endpoint externo localmente mediante Postman o scripts crudos en Python antes de programar la integración completa en el bot.

### 3.3 Testeo vía SSH (El problema del Escaping)
- **Nota Operativa:** Ejecutar scripts al vuelo con `python3 -c "import requests, json... "` pasando JSONs complejos con comillas incrustadas a través de `plink.exe` hacia un servidor remoto es muy propenso a fallar por "escaping" de sintaxis (bash traga comillas).
- **Mejor Práctica:** Escribir el script Python de test localmente (`.tmp/test_api.py`), subirlo completo usando `pscp` (o `docker cp`), y ejecutarlo directamente dentro del contenedor remoto donde están las variables de entorno para evitar frustración.

### 3.4 Chatwoot y el Renderizado de Imágenes en WhatsApp
- **Problema:** Si el bot necesita enviar una foto (ej. sugerencia de Inmueble desde la BD) y envía un enlace HTTPS crudo (`{"content": "https://...", "message_type": "outgoing"}`), WhatsApp *puede o no* generar un link preview, pero **nunca** la tratará como una foto nativa en la burbuja de chat.
- **Patrón Exitoso:** Para forzar a Meta/WhatsApp a renderizar la foto como Media Message nativo, el bot intermedio (Python) debe:
  1. Detectar el markdown `![alt](url)`.
  2. Hacer un HTTP GET a la URL para descargar el binario a memoria RAM.
  3. POST a la API de Chatwoot (`/messages`) usando `multipart/form-data` pasando el archivo en `attachments[]` y el contenido de texto vacío. Chatwoot se encarga de retransmitir el media file a Meta.
