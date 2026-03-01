# Guía de Configuración: API de WhatsApp Cloud (Meta)

Para lograr que Ricardo opere sobre la red oficial de WhatsApp y no dependas de tu teléfono celular personal prendido 24/7, usaremos la **API Cloud de Meta** (la misma que usan las grandes empresas).

Es 100% gratuita para desarrollo, pero requiere que configures tu "App" en el panel de Meta. Sigue estos pasos exactos:

## 1. Crear tu cuenta de Desarrollador
1. Ve a [Meta for Developers](https://developers.facebook.com/) y haz log in con tu cuenta personal normal de Facebook.
2. Ve a la sección de **"Mis Apps"** (My Apps) arriba a la derecha.
3. Haz click en el botón verde **"Crear App"** (Create App).
4. Elige **"Otro"** (Other) -> **"Negocios"** (Business) como tipo de aplicación.
5. Ponle un nombre como `RicardoBrokerBot` y añade tu correo de contacto principal.

## 2. Añadir el producto WhatsApp
1. En el panel de control de tu nueva App, desplázate hacia abajo y busca el recuadro que dice **"WhatsApp"** y haz click en "Configurar" (Set up).
2. Te pedirá afiliar o crear una "Cuenta Comercial de Meta" (Meta Business Account). Sigue los pasos por defecto para enlazarlo a tu empresa o nombre personal.

## 3. Obtener tus Llaves de Desarrollo (IMPORTANTE)
Una vez dentro del panel de WhatsApp, ve al menú izquierdo -> **API Setup** (Configuración de API).
Verás una pantalla con 3 datos CRÍTICOS que necesitas inyectar en tu archivo `.env`:

1. **Token de Acceso Temporal (Temporary Access Token):** Es una cadena gigante de letras. Vence cada 24 horas (se usa solo para desarrollo). Copia y pega esto en tu `.env` como `WHATSAPP_TOKEN`.
2. **Identificador del Número de Teléfono (Phone Number ID):** Copia los números y guárdalos en tu `.env` como `WHATSAPP_PHONE_ID`.
3. Meta te da un número de prueba (Test number) en formato USA. Para empezar enviarte o enviarle mensajes a ese número para probar debes agregar DEBAJO de esa sección tu número telefónico personal en "To" para autorizarte como "Destinatario de Pruebas". Verificará tu número mandándote un código por WhatsApp real.

## 4. Configurar tu `.env`
Tu archivo final escondido (que nunca subes a GitHub) deberá verse así:
```env
OPENAI_API_KEY="sk-tu-clave-aqui"
WHATSAPP_TOKEN="EAADXXXX......."
WHATSAPP_PHONE_ID="1234567890"
WHATSAPP_VERIFY_TOKEN="cualquier_palabra_secreta_aqui" 
```
> *(Nota: El `WHATSAPP_VERIFY_TOKEN` lo inventas tú en el `.env`, es una contraseña segura cualquiera, ej: `secreto_agente_inmobiliario2026`).*

## 5. Levantar Ngrok (Para recibir Mensajes)
Como Meta necesita una "URL pública" para avisarte cuando te escriben, debes usar Ngrok en otra terminal mientras desarrollas en tu PC:
```bash
ngrok http 8000
```
Te dará un enlace como `https://<url-rara>.ngrok.io`. 

Copia ese enlace, vuelve a **Meta Developers** -> **Configuración -> Webhooks**. Pega tu URL de Ngrok añadiéndole `/webhook` al final, y pega la misma contraseña secreta de `WHATSAPP_VERIFY_TOKEN` que inventaste. Meta verificará que tu servidor FastAPI está vivo.
