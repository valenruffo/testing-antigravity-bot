# DIRECTIVA: Integración de Cal.com como Motor de Agenda

> **Script Asociado:** `scripts/tools.py` (funciones `obtener_link_agenda`, `obtener_slots_disponibles`, `agendar_cita_calcom`)
> **Estado:** ACTIVO

---

## 1. Objetivo y Alcance

Reemplazar la integración directa con Google Calendar API por **Cal.com self-hosted** como fuente única de verdad para la disponibilidad del broker. Cal.com actúa como intermediario inteligente: sincroniza con Google Calendar, aplica reglas de negocio (buffers entre reuniones, aviso mínimo, zona horaria) y expone una API limpia al bot.

**Criterio de Éxito:** El bot puede consultar slots reales disponibles vía Cal.com API y crear reservas que aparezcan automáticamente en Google Calendar, sin leer el calendario directamente.

---

## 2. Arquitectura

```
Cliente (WhatsApp)
       ↓
Ricardo (Bot LangGraph / FastAPI)
       ↓ API v2 REST
Cal.com (contenedor calcom_app en VPS)
       ↓ sync bidireccional
Google Calendar del Broker
```

**Ventajas sobre la integración directa:**
- Los eventos privados de Google Calendar bloquean slots sin que el bot los vea
- Cal.com aplica buffers entre reuniones y tiempo mínimo de aviso
- Manejo correcto de zonas horarias a nivel de Unix timestamps

---

## 3. Variables de Entorno Requeridas

| Variable | Descripción | Quién la genera |
|---|---|---|
| `CALCOM_URL` | URL pública de Cal.com (ej: `https://cal.remon.com.ar`) | Cloudflare tunnel |
| `CALCOM_USERNAME` | Usuario del broker en Cal.com | Setup wizard |
| `CALCOM_EVENT_TYPE_ID` | ID del Tipo de Evento "Asesoría 30min" | Visible en URL al editar |
| `CALCOM_API_KEY` | Clave de API generada en Cal.com | Cal.com → Configuración → API Keys |
| `CALCOM_DATABASE_URL` | Postgres interno del contenedor | No modificar |
| `CALCOM_NEXTAUTH_SECRET` | Secreto de sesión (`openssl rand -base64 32`) | Generar una sola vez |
| `CALCOM_ENCRYPTION_KEY` | Cifrado (`openssl rand -base64 24`) | Generar una sola vez |

---

## 4. Setup Manual (Primera Vez)

### Paso 1: Generar secretos
Ejecutar en el VPS:
```bash
openssl rand -base64 32   # → pegar en CALCOM_NEXTAUTH_SECRET
openssl rand -base64 24   # → pegar en CALCOM_ENCRYPTION_KEY
```

### Paso 2: Configurar Cloudflare
1. Ir a Cloudflare Zero Trust → Networks → Tunnels → Seleccionar el túnel existente
2. Pestaña **"Public Hostname"** → Agregar:
   - Subdominio: `cal` | Dominio: `remon.com.ar`
   - Tipo: HTTP | URL: `calcom_app:3000`

### Paso 3: Arrancar Cal.com
```bash
docker compose up -d calcom_postgres calcom_app
docker logs calcom_app -f  # Esperar a que levante (~2-3 minutos)
```

### Paso 4: Setup Wizard
1. Entrar a `https://cal.remon.com.ar`
2. Crear usuario admin (broker)
3. **Configuración → Calendarios** → Conectar Google Calendar
4. Crear Tipo de Evento:
   - Nombre: `Asesoría Inmobiliaria`
   - Duración: 30 minutos
   - Añadir disponibilidad (ej: Lunes-Viernes 09:00-15:00/18:00)
   - Añadir buffer entre reuniones (opcional, recomendado: 15 min)
5. **Configuración → API Keys** → Generar nueva clave → copiar al `.env` como `CALCOM_API_KEY`
6. Editar el Tipo de Evento → notar el ID en la URL → copiar al `.env` como `CALCOM_EVENT_TYPE_ID`

### Paso 5: Actualizar .env y redesplegar
```bash
# Editar .env con los valores reales
# Luego redesplegar solo el bot (no Cal.com, que ya está corriendo):
docker compose up -d --no-deps app
```

---

## 5. Herramientas del Bot

### `obtener_link_agenda()`
- **Cuándo usar:** El cliente prefiere elegir su horario de forma autónoma
- **Retorna:** URL directa al formulario de reserva de Cal.com
- **Configuración:** Usa `CALCOM_URL` + `CALCOM_USERNAME`

### `obtener_slots_disponibles(fecha_inicio_iso, fecha_fin_iso)`
- **Cuándo usar:** Antes de `agendar_cita_calcom` cuando el bot agenda directo
- **Endpoint:** `GET {CALCOM_URL}/api/v2/slots/available`
- **Parámetros:** `eventTypeId`, `startTime` (UTC), `endTime` (UTC)
- **Retorna:** Lista de horarios libres convertidos a GMT-3

### `agendar_cita_calcom(fecha_hora_utc, nombre, email, zona_horaria, motivo)`
- **Cuándo usar:** Después de confirmar un slot con el cliente
- **Endpoint:** `POST {CALCOM_URL}/api/v2/bookings`
- **⚠️ CRÍTICO:** `fecha_hora_utc` SIEMPRE en UTC. Si el cliente eligió 09:00 (GMT-3), el valor es `T12:00:00Z`
- **Headers:** `Authorization: Bearer {CALCOM_API_KEY}`, `cal-api-version: 2024-08-13`
- **Retorna:** ID de reserva + link de videollamada + confirmación de email enviado

---

## 6. Restricciones y Casos Límite

- **CALCOM_API_KEY vacía:** Las herramientas devuelven un error descriptivo sin crashear el bot.
- **Slot ya ocupado:** Cal.com retorna HTTP 409 o un error en el cuerpo. La función `agendar_cita_calcom` convierte el error en texto legible para el LLM.
- **Cal.com caído:** La herramienta retorna error de timeout. El bot debe informar al cliente e intentar más tarde.
- **Zona horaria del cliente fuera de Argentina:** El parámetro `zona_horaria_cliente` acepta cualquier zona IANA (ej: `Europe/Madrid`). Cal.com maneja la conversión automáticamente.
- **Primera vez sin API Key:** Si `CALCOM_API_KEY` aún dice `COMPLETAR_DESPUES_DEL_SETUP`, las herramientas retornan un mensaje de error al LLM pidiendo configuración admin.

---

## 7. Historial de Aprendizajes

| Fecha | Error | Causa | Solución |
|---|---|---|---|
| 03/03/26 | Integración directa Google Calendar aceptaba cualquier hora | Validación solo era soft constraint en el LLM | Se migró a Cal.com como filtro de disponibilidad real |
