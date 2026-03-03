# Configuración de Credenciales de Google (credentials.json)

Para que Ricardo pueda leer las propiedades y escribir leads automáticamente, y agendar citas en Calendar, necesitamos conectar el código con tu cuenta de Google.

Existen 2 métodos:
1. **Service Account (Ideal para bots/servidores):** Se crea un "usuario robot" en Google Cloud. Te dan un archivo de texto con claves (`credentials.json`). Debes invitar a ese "robot" compartiéndole tu Google Sheet (como si fuera una persona más).
2. **OAuth 2.0 (Para acceder a tu propio Calendar):** Como queremos agendar en *tu* Calendar personal, necesitamos OAuth. Esto abre una ventanita de Google en el navegador para que aceptes los permisos. Luego descarga un `credentials.json` y genera un `token.json` automáticamente.

## Paso a paso para conseguir el `credentials.json`:

1. Ve a la Consola de Google Cloud: [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un **Proyecto Nuevo** (Ej: "Bot Ricardo").
3. Ve a **"API y Servicios" > "Biblioteca"**.
4. Busca y **habilita** estas dos APIs:
   - *Google Sheets API*
   - *Google Calendar API*
5. Ve a **"API y Servicios" > "Pantalla de consentimiento de OAuth"**
   - Elige "Externo".
   - Rellena nombre de la app (Bot Ricardo) y tu correo de soporte.
   - Añade tu propio correo de Google a "Usuarios de prueba".
6. Ve a **"API y Servicios" > "Credenciales"**
   - Click arriba en **"+ CREAR CREDENCIALES"**.
   - Elige **"ID de cliente de OAuth"**.
   - Tipo de aplicación: **"App de escritorio"**.
   - Descarga el archivo JSON que te da Google.
7. Renombra ese archivo descargado como `credentials.json` (asegúrate de que no se llame `credentials.json.json`) y guárdalo en la carpeta `C:\Users\valen\Desktop\test_bot\`. 

Una vez me confirmes que está guardado, ejecutaré un script que abrirá tu navegador para que inicies sesión por única vez, y generaremos un archivo secreto `token.json` para que el bot tenga acceso permanente a tus Sheets y Calendar.
