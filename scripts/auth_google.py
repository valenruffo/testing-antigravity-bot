import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Los SCOPES determinan los permisos que tendrá el bot
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/calendar.events'
]

def main():
    creds = None
    
    # El archivo token.json almacena los tokens de acceso y actualización 
    # y se crea automáticamente cuando el flujo de autorización se completa por primera vez.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
    # Si no hay credenciales (válidas) disponibles, el usuario inicia sesión.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
        # Guarda las credenciales de la próxima ejecución
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    print("¡Autenticación exitosa! El archivo token.json ha sido creado.")
    
if __name__ == '__main__':
    main()
