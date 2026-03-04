# DIRECTIVA: Integración de Cal.com como Motor de Agenda

> **Script Asociado:** `scripts/tools.py` (funciones `obtener_link_agenda`, `obtener_slots_disponibles`, `agendar_cita_calcom`)
> **Estado:** ACTIVO — Usando Cal.com Cloud (plan free en cal.com)

---

## 1. Objetivo y Alcance

Usar **Cal.com cloud** ([cal.com](https://cal.com)) como fuente única de verdad para la disponibilidad del broker. Cal.com sincroniza con Google Calendar, aplica reglas de negocio (buffers, zona horaria, aviso mínimo) y expone una API limpia al bot.

> **Nota:** Se descartó el self-hosting en el VPS Oracle ARM64 porque la imagen Docker oficial de Cal.com es solo AMD64 y Node.js crashea bajo emulación QEMU.

---

## 2. Arquitectura

```
Cliente (WhatsApp)
       ↓
Ricardo (Bot LangGraph / FastAPI) — en el VPS
       ↓ API v2 REST (HTTPS)
Cal.com Cloud (cal.com)
       ↓ sync bidireccional
Google Calendar del Broker
```

---

## 3. Variables de Entorno Requeridas

| Variable | Valor | Quién la provee |
|---|---|---|
| `CALCOM_URL` | `https://api.cal.com` | Fijo, NO cambiar |
| `CALCOM_USERNAME` | Tu usuario en cal.com | Cal.com signup |
| `CALCOM_EVENT_TYPE_ID` | ID numérico del evento | URL al editar el evento |
| `CALCOM_API_KEY` | `cal_live_xxxxx` | Cal.com → Settings → API Keys |

---

## 4. Setup (Solo la Primera Vez)

1. Crear cuenta en [cal.com](https://cal.com) (plan free)
2. **Settings → Calendars** → conectar Google Calendar del broker
3. Crear Tipo de Evento:
   - Nombre: `Asesoría Inmobiliaria`
   - Duración: 30 minutos
   - Configurar disponibilidad semanal
   - (Opcional) buffer entre reuniones: 15 min
4. **Settings → API Keys** → generar nueva clave → copiar como `CALCOM_API_KEY` en `.env`
5. Editar el Tipo de Evento → el número en la URL es el ID → copiar como `CALCOM_EVENT_TYPE_ID` en `.env`
6. Actualizar `CALCOM_USERNAME` en `.env` con tu nombre de usuario de cal.com
7. Redesplegar el bot: `powershell -ExecutionPolicy Bypass -File .tmp\deploy_vps_docker.ps1`

---

## 5. Herramientas del Bot

### `obtener_link_agenda()`
- **Cuándo usar:** El cliente quiere elegir su horario de forma autónoma
- **Retorna:** `https://cal.com/{CALCOM_USERNAME}/asesoria-inmobiliaria`

### `obtener_slots_disponibles(fecha_inicio_iso, fecha_fin_iso)`
- **Endpoint:** `GET https://api.cal.com/v2/slots`
- **Parámetros:** `eventTypeId`, `start`, `end`, `timeZone`
- **Retorna:** Lista de horarios libres convertidos a GMT-3
- **Precaución:** Siempre usar ANTES de `agendar_cita_calcom`

### `agendar_cita_calcom(fecha_hora_utc, nombre, email, zona_horaria, motivo)`
- **Endpoint:** `POST https://api.cal.com/v2/bookings`
- **⚠️ CRÍTICO:** `fecha_hora_utc` SIEMPRE en UTC. Si el cliente eligió 09:00 (GMT-3), pasar `T12:00:00Z`.
- **Retorna:** ID reserva + link videollamada + email de confirmación automático al cliente

---

## 6. Restricciones y Casos Límite

- **CALCOM_API_KEY vacía / placeholder:** Las herramientas devuelven error descriptivo sin crashear.
- **Slot ya ocupado:** Cal.com retorna HTTP 409. La función lo convierte en texto legible para el LLM.
- **Cal.com cloud caído:** Timeout de 10 segundos, el bot informa al cliente e intenta más tarde.
- **Primera vez sin configurar:** Si `CALCOM_API_KEY` dice `COMPLETAR_DESPUES_DEL_SETUP`, las herramientas devuelven mensaje de error admin.

---

## 7. Historial de Decisiones

| Fecha | Decisión | Motivo |
|---|---|---|
| 03/03/26 | Migración de Google Calendar directo → Cal.com | Calendar aceptaba cualquier hora; Cal.com filtra disponibilidad real |
| 03/03/26 | Self-hosted → Cal.com Cloud | VPS Oracle ARM64 incompatible con imágenes Docker AMD64 de Cal.com |
