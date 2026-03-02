import os.path
from datetime import datetime, timedelta
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

def agendar_cita(fecha_hora_inicio_iso: str, nombre_cliente: str, correo_cliente: str, motivo: str = "Asesoría Inmobiliaria") -> str:
    """Crea un evento en Google Calendar y genera un link de Google Meet.
       Args:
           fecha_hora_inicio_iso: Fecha y hora en formato ISO 8601 (ej: '2026-03-01T15:00:00-03:00')
           nombre_cliente: El nombre del lead/cliente.
           correo_cliente: Correo electrónico del cliente (OBLIGATORIO para enviar la invitación).
           motivo: Zona o propiedad de interés para anotar en el título del evento.
    """
    try:
        _, calendar_service = get_google_services()
        
        # Parseamos la fecha y sumamos 30 mins para el fin
        start_time = datetime.fromisoformat(fecha_hora_inicio_iso)
        end_time = start_time + timedelta(minutes=30)
        
        event = {
            'summary': f'{motivo} - {nombre_cliente}',
            'description': f'Llamada de perfilación y presentación de opciones exclusivas.\nCliente: {nombre_cliente}\nContacto/Correo: {correo_cliente}',
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'America/Argentina/Buenos_Aires',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'America/Argentina/Buenos_Aires',
            },
            'attendees': [
                {'email': correo_cliente},
            ],
            'conferenceData': {
                'createRequest': {
                    'requestId': f"ricardo_meet_{start_time.strftime('%Y%m%d%H%M%S')}",
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                }
            }
        }

        # Inserta el evento invocando al API. conferenceDataVersion=1 es requerido para crear el Meet.
        event_result = calendar_service.events().insert(
            calendarId='primary', 
            body=event, 
            conferenceDataVersion=1
        ).execute()
        
        meet_link = event_result.get('hangoutLink')
        
        return f"Cita agendada para el {start_time.strftime('%Y-%m-%d %H:%M')}. Link de Meet: {meet_link}"
    except Exception as e:
        return f"Error al intentar agendar la cita en Calendar: {str(e)}. Intenta confirmar el formato de la fecha."

def obtener_horarios_disponibles(fecha_iso: str) -> str:
    """Obtiene los eventos del calendario para un día específico y deduce qué horarios están ocupados.
       Args:
           fecha_iso: Fecha en formato ISO 8601 correspondientes al inicio del día a consultar (ej: '2026-03-01T00:00:00-03:00')
    """
    try:
        _, calendar_service = get_google_services()
        
        start_time = datetime.fromisoformat(fecha_iso).replace(hour=0, minute=0, second=0)
        end_time = start_time + timedelta(days=1)
        
        # Validación de Fines de Semana
        if start_time.weekday() >= 5: # 5 es Sábado, 6 es Domingo
            return f"El día {start_time.strftime('%Y-%m-%d')} es FIN DE SEMANA. El broker NO TRABAJA los fines de semana. Dile al cliente que solo atiendes de lunes a viernes e indícale que te sugiera un día hábil."

        # Definición hardcodeada de la disponibilidad de la Página de Reservas del Broker
        horarios_trabajo = {
            0: "Lunes: de 09:00 a 15:00",
            1: "Martes: de 09:00 a 18:00",
            2: "Miércoles: de 09:00 a 18:00",
            3: "Jueves: de 09:00 a 15:00",
            4: "Viernes: de 09:00 a 15:00"
        }
        
        dia_semana = start_time.weekday()
        horario_hoy = horarios_trabajo.get(dia_semana, "09:00 a 18:00")
        
        events_result = calendar_service.events().list(
            calendarId='primary', timeMin=start_time.isoformat(), timeMax=end_time.isoformat(),
            singleEvents=True, orderBy='startTime', timeZone='America/Argentina/Buenos_Aires'
        ).execute()
        events = events_result.get('items', [])

        if not events:
            return f"Ese día ({start_time.strftime('%Y-%m-%d')}) NO hay reuniones que bloqueen la agenda. Tu horario de atención hoy es {horario_hoy} (GMT-3).\n\n🚨 REGLAS ESTRICTAS DE AGENDA:\n1. Las citas duran EXACTAMENTE 30 minutos.\n2. El último turno agendable comienza 30 minutos antes del cierre (Ej. Si cierras a las 18:00, solo puedes agendar hasta las 17:30).\n3. NUNCA le envíes al cliente la lista gigante de horarios. Pregúntale si prefiere mañana o tarde y dale SOLO 2 O 3 opciones concretas."
        
        ocupados = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            ocupados.append(f"De {start} a {end}")
            
        return f"Para el día {start_time.strftime('%Y-%m-%d')}, la agenda ya está OCUPADA en los siguientes horarios por otras reuniones:\n" + "\n".join(ocupados) + f"\n\n🚨 REGLAS ESTRICTAS DE AGENDA:\n1. Tu horario de trabajo hoy es {horario_hoy} (GMT-3).\n2. Las citas duran EXACTAMENTE 30 minutos.\n3. El último turno agendable comienza 30 minutos antes del cierre.\n4. NUNCA listes todos los horarios libres. Pregunta preferencia (mañana/tarde) y ofrece SOLO 2 O 3 opciones puntuales que NO se superpongan con las reuniones ocupadas."
    except Exception as e:
        return f"Error al consultar horarios: {str(e)}"

def reagendar_cita(correo_cliente: str, nueva_fecha_hora_iso: str) -> str:
    """Busca una cita futura agendada con el correo del cliente y modifica la fecha y hora.
       Args:
           correo_cliente: Email usado para agendar la cita.
           nueva_fecha_hora_iso: Nueva fecha y hora en formato ISO 8601 (ej: '2026-03-02T16:00:00-03:00')
    """
    try:
        _, calendar_service = get_google_services()
        
        now = datetime.now().isoformat() + 'Z'  # 'Z' indica UTC
        events_result = calendar_service.events().list(
            calendarId='primary', timeMin=now, q=correo_cliente,
            singleEvents=True, orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        if not events:
            return "No se encontró ninguna cita futura con ese correo para modificar."
            
        event_to_update = events[0]
        event_id = event_to_update['id']
        
        new_start_time = datetime.fromisoformat(nueva_fecha_hora_iso)
        new_end_time = new_start_time + timedelta(minutes=30)
        
        event_to_update['start']['dateTime'] = new_start_time.isoformat()
        event_to_update['end']['dateTime'] = new_end_time.isoformat()
        event_to_update['start']['timeZone'] = 'America/Argentina/Buenos_Aires'
        event_to_update['end']['timeZone'] = 'America/Argentina/Buenos_Aires'
        
        updated_event = calendar_service.events().update(
            calendarId='primary', eventId=event_id, body=event_to_update
        ).execute()
        
        return f"La cita para {correo_cliente} fue exitosamente movida al {new_start_time.strftime('%Y-%m-%d %H:%M')}. Link: {updated_event.get('hangoutLink')}"
    except Exception as e:
        return f"Error al modificar la cita: {str(e)}"
        
def cancelar_cita(correo_cliente: str) -> str:
    """Busca una cita futura agendada con el correo del cliente y la elimina del Google Calendar.
       Args:
           correo_cliente: Email del asistente (el invitado a la llamada).
    """
    try:
        _, calendar_service = get_google_services()
        
        now = datetime.now().isoformat() + 'Z' 
        events_result = calendar_service.events().list(
            calendarId='primary', timeMin=now, q=correo_cliente,
            singleEvents=True, orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])

        if not events:
            return "No se encontró ninguna cita futura con ese correo para cancelar."
            
        event_id = events[0]['id']
        
        calendar_service.events().delete(
            calendarId='primary', eventId=event_id
        ).execute()
        
        return f"La cita futura bajo el correo {correo_cliente} fue cancelada y borrada silenciosamente."
    except Exception as e:
        return f"Error al cancelar la cita: {str(e)}"

TOOLS = [consultar_propiedades, registrar_lead, agendar_cita, obtener_horarios_disponibles, reagendar_cita, cancelar_cita]
