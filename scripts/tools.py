import os
import os.path
import requests
from datetime import datetime, timedelta, timezone
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

load_dotenv()

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar.events'
]

SPREADSHEET_ID = '16_C-t632vZkq2c7AV1ryY3Tdiop3C6NmJdZKlup3yfE'

def get_google_services():
    """Autentica y devuelve los servicios de Sheets y Calendar."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    sheets_service = build('sheets', 'v4', credentials=creds)
    calendar_service = build('calendar', 'v3', credentials=creds)
    return sheets_service, calendar_service

def consultar_propiedades(zona: str = None, presupuesto_maximo: int = None) -> str:
    """Busca en la base de datos (Google Sheets) las propiedades disponibles."""
    try:
        sheets_service, _ = get_google_services()
        sheet = sheets_service.spreadsheets()

        # Obtenemos metadata para saber las hojas que existen
        sheet_metadata = sheet.get(spreadsheetId=SPREADSHEET_ID).execute()
        sheets = sheet_metadata.get('sheets', [])

        # Intentamos buscar especificamente la hoja que dice "propiedades"
        nombre_primera_hoja = "propiedades"
        for s in sheets:
            titulo = s.get("properties", {}).get("title", "")
            if "propiedades" in titulo.lower():
                nombre_primera_hoja = titulo
                break

        # Ajustamos el rango a A:G para incluir imágenes
        rango = f"'{nombre_primera_hoja}'!A:G"

        result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=rango).execute()
        values = result.get('values', [])

        if not values:
            return "No se encontraron propiedades en la base de datos."

        header = values[0]
        propiedades_encontradas = []

        # Ignora la fila 0 (headers)
        for row in values[1:]:
            # Padding por si las filas están incompletas
            row += [''] * (len(header) - len(row))
            id_prop = row[0] if len(row) > 0 else '0'
            nombre = row[1] if len(row) > 1 else 'N/A'
            zona_prop = row[2] if len(row) > 2 else 'N/A'
            precio_str = row[3] if len(row) > 3 else '0'
            desc = row[4] if len(row) > 4 else ''
            rentabilidad = row[5] if len(row) > 5 else ''
            imagenes = row[6] if len(row) > 6 else ''

            # Limpiar el precio asumiendo string tipo "USD 450,000" o "$5000000"
            precio_limpio = ''.join(c for c in str(precio_str) if c.isdigit())
            precio = int(precio_limpio) if precio_limpio else 0

            # Filtros básicos (case-insensitive para zona)
            match_zona = not zona or zona.lower() in str(zona_prop).lower()

            if match_zona:
                prop_info = f"- **[ID: {id_prop}] {nombre}** en {zona_prop} ({precio_str})\n  Detalle: {desc}\n  Rentabilidad: {rentabilidad}\n  Imágenes: {imagenes}\n"
                propiedades_encontradas.append(prop_info)

        if propiedades_encontradas:
            return "Aquí tienes las opciones en la base de datos para esa zona:\n" + "\n".join(propiedades_encontradas)
        else:
            return f"Actualmente no cuento con propiedades en {zona}."

    except Exception as e:
        print(f"\n\n🚨 GOOGLE API ERROR ---> {str(e)}\n\n")
        return f"Error al consultar la base de datos de propiedades: {str(e)}"

def registrar_lead(nombre: str, contacto: str, presupuesto: str, zona: str, urgencia: str) -> str:
    """Registra los datos del cliente calificado en la pestaña 'Leads' del Google Sheet."""
    try:
        sheets_service, _ = get_google_services()
        sheet = sheets_service.spreadsheets()

        # Obtenemos metadata para encontrar una hoja que contenga "lead" en el nombre
        sheet_metadata = sheet.get(spreadsheetId=SPREADSHEET_ID).execute()
        sheets_list = sheet_metadata.get('sheets', '')

        nombre_hoja_leads = None
        for s in sheets_list:
            titulo = s.get("properties", {}).get("title", "")
            if "lead" in titulo.lower():
                nombre_hoja_leads = titulo
                break

        # Si no hay hoja de leads específica, intentamos con la segunda hoja si existe
        if not nombre_hoja_leads and len(sheets_list) > 1:
            nombre_hoja_leads = sheets_list[1].get("properties", {}).get("title")
        elif not nombre_hoja_leads:
            return "Error: No se encontró una pestaña de 'Leads' en el Google Sheet."

        # Nombre | Teléfono | Interés | Presupuesto | Estado | Nota de la IA
        rango = f"'{nombre_hoja_leads}'!A:F"

        # En la directiva original urgencia formaba parte de esto, lo meteremos en la Nota de la IA.
        nota_ia = f"Urgencia/Plazo: {urgencia}. Zona de interés: {zona}."

        valores = [
            [nombre, contacto, zona, presupuesto, "Calificado - Agendando", nota_ia]
        ]
        body = {
            'values': valores
        }

        sheets_service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=rango,
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()

        return f"Lead ({nombre}) registrado exitosamente en el CRM."
    except Exception as e:
        return f"Error al registrar el lead: {str(e)}"

# =============================================================================
# HERRAMIENTAS DE AGENDA (Cal.com - Motor de Agenda Self-Hosted)
# Cal.com actúa como intermediario entre el bot y Google Calendar.
# Sincroniza automáticamente, aplica reglas de negocio y maneja zonas horarias.
# =============================================================================

def obtener_link_agenda() -> str:
    """Devuelve el link público de Cal.com para que el cliente elija su propio horario de forma autónoma.
    Úsalo cuando el cliente prefiera auto-agendarse en el horario que más le convenga.
    """
    # El link de reserva siempre usa cal.com (frontend público), no la URL de la API.
    calcom_username = os.environ.get("CALCOM_USERNAME", "broker")
    calcom_event_slug = os.environ.get("CALCOM_EVENT_SLUG", "30min")
    return f"Link de reserva: https://cal.com/{calcom_username}/{calcom_event_slug}"

def obtener_slots_disponibles(fecha_inicio: str, fecha_fin: str) -> str:
    """Consulta los horarios DISPONIBLES en Cal.com para un rango de fechas.
    Devuelve una lista real de slots libres, ya filtrados por disponibilidad real del calendario.
    SIEMPRE usa esta herramienta antes de agendar para no inventar horarios.
    Args:
        fecha_inicio: Fecha de inicio en formato YYYY-MM-DD (ej: '2026-03-10')
        fecha_fin: Fecha de fin en formato YYYY-MM-DD (ej: '2026-03-12')
    """
    try:
        calcom_url = os.environ.get("CALCOM_URL", "")
        api_key = os.environ.get("CALCOM_API_KEY", "")
        event_type_id = os.environ.get("CALCOM_EVENT_TYPE_ID", "1")

        if not calcom_url or not api_key or api_key == "COMPLETAR_DESPUES_DEL_SETUP":
            return "Error: Cal.com no configurado. El administrador debe completar CALCOM_API_KEY en el .env."

        headers = {
            "Authorization": f"Bearer {api_key}",
            "cal-api-version": "2024-09-04"
        }
        params = {
            "eventTypeId": event_type_id,
            "start": fecha_inicio,
            "end": fecha_fin,
            "timeZone": "America/Argentina/Buenos_Aires"
        }
        resp = requests.get(
            f"{calcom_url}/v2/slots",
            headers=headers, params=params, timeout=10
        )
        resp.raise_for_status()
        data = resp.json()

        # La respuesta tiene formato: {"data": {"2026-03-05": [{"time": "..."}]}, "status": "success"}
        slots_data = data.get("data", {})
        if not slots_data:
            return "No hay horarios disponibles para ese rango de fechas. Propón otro día al cliente."

        resultado = "HORARIOS DISPONIBLES (verificados y libres en la agenda real):\n"
        for fecha, slots in sorted(slots_data.items()):
            if slots:
                # Cal.com devuelve los tiempos ya en la timeZone solicitada
                horas = []
                for s in slots:
                    try:
                        t = s["start"]  # ej: "2026-03-06T09:00:00.000-03:00"
                        hora = t[11:16]  # extrae HH:MM
                        horas.append(hora)
                    except Exception:
                        pass
                if horas:
                    resultado += f"- {fecha}: {', '.join(horas)} (hora Argentina, GMT-3)\n"

        resultado += "\n🚨 REGLA DE PRESENTACIÓN: El cliente ya te indicó si prefiere mañana o tarde. Filtra mentalmente esta lista y ofrécele solo 2 o 3 opciones precisas que coincidan con su preferencia (para no abrumarlo). NO le muestres toda la lista. Si te pide un horario específico que está en la lista, confirmalo."
        return resultado
    except Exception as e:
        return f"Error consultando disponibilidad en Cal.com: {str(e)}"

def agendar_cita_calcom(fecha_hora_utc: str, nombre_cliente: str, email_cliente: str, zona_horaria_cliente: str = "America/Argentina/Buenos_Aires", motivo: str = "Asesoría Inmobiliaria") -> str:
    """Crea una reserva en Cal.com. Cal.com la sincroniza automáticamente con Google Calendar y genera el link de videollamada.
    ⚠️ La fecha/hora DEBE estar en formato UTC (ej: '2026-03-05T12:00:00Z').
    Si el cliente eligió las 09:00 (GMT-3), convierte a UTC sumando 3 horas: '2026-03-05T12:00:00Z'.
    Args:
        fecha_hora_utc: Fecha y hora de inicio en UTC estricto (ej: '2026-03-05T12:00:00Z').
        nombre_cliente: Nombre completo del cliente.
        email_cliente: Correo del cliente para enviarle la invitación y el link de Meet.
        zona_horaria_cliente: Zona horaria del cliente (default: 'America/Argentina/Buenos_Aires').
        motivo: Propiedad o zona de interés para incluir en el título de la cita.
    """
    try:
        calcom_url = os.environ.get("CALCOM_URL", "")
        api_key = os.environ.get("CALCOM_API_KEY", "")
        event_type_id = int(os.environ.get("CALCOM_EVENT_TYPE_ID", "1"))

        if not calcom_url or not api_key or api_key == "COMPLETAR_DESPUES_DEL_SETUP":
            return "Error: Cal.com no configurado. El administrador debe completar CALCOM_API_KEY en el .env."

        if not email_cliente or "@" not in email_cliente:
            return "ACCIÓN REQUERIDA: No tengo el correo del cliente. Debo pedírselo antes de poder agendar. Pregúntale su email."

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "cal-api-version": "2024-08-13"
        }
        body = {
            "start": fecha_hora_utc,
            "eventTypeId": event_type_id,
            "attendee": {
                "name": nombre_cliente,
                "email": email_cliente,
                "timeZone": zona_horaria_cliente,
                "language": "es"
            },
            "bookingFieldsResponses": {
                "notes": f"Interés en: {motivo}"
            }
        }
        resp = requests.post(
            f"{calcom_url}/v2/bookings",
            headers=headers, json=body, timeout=10
        )
        resp.raise_for_status()
        data = resp.json()

        booking = data.get("data", {})
        meet_link = booking.get("meetingUrl", "")
        booking_uid = booking.get("uid", "")

        return (
            f"¡Cita confirmada exitosamente! "
            f"ID de reserva: {booking_uid}. "
            f"Link de videollamada: {meet_link}. "
            f"Se enviará una invitación automática al correo {email_cliente}."
        )
    except Exception as e:
        return f"Error al crear la reserva en Cal.com: {str(e)}. Verifica que la hora esté en formato UTC y que el slot siga disponible."

def transferir_a_humano(motivo_transferencia: str) -> str:
    """Detiene la conversación con la IA y transfiere el caso a un Asesor Humano real.
       Usa esta herramienta DENTRO DEL GRAFO si el cliente se enoja, se atasca o lo pide explícitamente.
       Args:
           motivo_transferencia: Breve resumen para el humano de por qué estás abandonando el chat.
    """
    try:
        smtp_user = os.environ.get('SMTP_USER')
        smtp_pass = os.environ.get('SMTP_PASS')
        smtp_host = os.environ.get('SMTP_ADDRESS') or 'smtp.gmail.com'
        smtp_port = int(os.environ.get('SMTP_PORT') or 587)
        admin_email = os.environ.get('ADMIN_EMAIL') or smtp_user

        if smtp_user and smtp_pass:
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = admin_email
            msg['Subject'] = "🚨 ALERTA: Un Lead requiere Asistencia Humana (Chatwoot)"
            body = (
                f"El bot ha transferido una conversación.\n\n"
                f"Motivo que dio la IA: {motivo_transferencia}\n\n"
                f"Ingresa a Chatwoot para continuar la conversación y recuerda volver a encender el bot (bot_status=on) al terminar."
            )
            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            server.quit()
            print("Correo SMTP de Hand-off enviado correctamente.")
        else:
            print("No se envió correo por omisión de SMTP_USERNAME/PASSWORD en .env")
    except Exception as e:
        print(f"Error mandando SMTP: {e}")

    # Retornaremos un payload especial estructurado que `main.py` atrapará para
    # cambiar el AgentState y notificar a Chatwoot.
    return f"HITL_TRIGGERED||{motivo_transferencia}"

TOOLS = [consultar_propiedades, registrar_lead, obtener_link_agenda, obtener_slots_disponibles, agendar_cita_calcom, transferir_a_humano]
