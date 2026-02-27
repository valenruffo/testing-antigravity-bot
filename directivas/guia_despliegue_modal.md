# Guía Completa: Cómo Desplegar Scripts en Modal

Esta guía te enseñará cómo convertir tus scripts de Python en aplicaciones serverless desplegadas en Modal.com, incluyendo manejo de secrets y autenticación OAuth con Google.

---

## 📋 Tabla de Contenidos

1. [Introducción a Modal](#introducción-a-modal)
2. [Prerrequisitos](#prerrequisitos)
3. [Estructura Básica de un Script Modal](#estructura-básica)
4. [Componentes Clave](#componentes-clave)
5. [Configuración de Secrets](#configuración-de-secrets)
6. [OAuth con Google APIs](#oauth-con-google-apis)
7. [Proceso de Despliegue](#proceso-de-despliegue)
8. [Testing y Debugging](#testing-y-debugging)
9. [Casos de Uso Completos](#casos-de-uso-completos)
10. [Troubleshooting](#troubleshooting)

---

## Introducción a Modal

**Modal** es una plataforma serverless que permite ejecutar código Python en la nube sin gestionar servidores. Es ideal para:

- APIs REST
- Procesamiento de datos en batch
- Machine Learning workflows
- Automatizaciones programadas

### Ventajas

- ✅ Sin gestión de infraestructura
- ✅ Escalamiento automático
- ✅ Pago por uso
- ✅ Fácil integración con Python
- ✅ Manejo seguro de secrets

---

## Prerrequisitos

### 1. Cuenta en Modal

```bash
# Crear cuenta en https://modal.com
```

### 2. Instalar Modal CLI

```bash
pip install modal
```

### 3. Autenticar

```bash
modal token new
```

Esto abrirá un navegador para conectar tu cuenta.

---

## Estructura Básica

Todo script Modal sigue esta estructura:

```python
import modal

# 1. Crear la aplicación
app = modal.App("nombre-app")

# 2. Definir la imagen (contenedor con dependencias)
image = modal.Image.debian_slim(python_version="3.13").pip_install(
    "requests==2.31.0",
    "openai==1.0.0"
)

# 3. Definir funciones serverless
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("mi-secret")],
    timeout=600
)
def mi_funcion(parametro: str):
    # Tu código aquí
    return "resultado"

# 4. Crear API endpoint (opcional)
@app.function(image=image)
@modal.asgi_app()
def api():
    from fastapi import FastAPI
    
    web_app = FastAPI()
    
    @web_app.post("/endpoint")
    async def endpoint(data: dict):
        result = mi_funcion.remote(data["param"])
        return {"result": result}
    
    return web_app

# 5. Entrypoint local para testing
@app.local_entrypoint()
def main():
    result = mi_funcion.remote("test")
    print(result)
```

---

## Componentes Clave

### 1. App

Define tu aplicación Modal:

```python
app = modal.App("mi-aplicacion")
```

**Naming conventions:**
- Usa kebab-case: `email-verifier`, `linkedin-generator`
- Sé descriptivo pero conciso

### 2. Image

La "imagen" es el contenedor Docker con todas tus dependencias:

```python
image = modal.Image.debian_slim(python_version="3.13").pip_install(
    "requests==2.31.0",
    "pandas==2.0.0"
)
```

**Aspectos importantes:**
- Especifica versiones exactas para reproducibilidad
- Modal cachea las imágenes (solo se reconstruye si cambian las deps)
- Construcción inicial toma ~10-15 segundos

**Ejemplo con múltiples dependencias:**

```python
image = modal.Image.debian_slim(python_version="3.13").pip_install(
    "apify-client==2.3.0",
    "google-genai==1.56.0",
    "google-api-python-client==2.154.0",
    "fastapi==0.115.6",
    "pydantic==2.12.5"
)
```

### 3. Funciones (@app.function)

Decora tus funciones para hacerlas serverless:

```python
@app.function(
    image=image,                                    # Imagen a usar
    secrets=[modal.Secret.from_name("mi-secret")], # Secrets
    timeout=600,                                    # Timeout en segundos
    retries=1                                       # Reintentos en caso de error
)
def procesar_datos(input_data: dict):
    # Tu lógica aquí
    return resultado
```

**Parámetros importantes:**
- `timeout`: Máximo tiempo de ejecución (default: 300s)
- `retries`: Número de reintentos si falla
- `secrets`: Lista de secrets a inyectar

### 4. API Endpoints (@modal.asgi_app)

Crea APIs REST con FastAPI:

```python
@app.function(image=image, secrets=[...])
@modal.asgi_app()
def api():
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    
    web_app = FastAPI(title="Mi API")
    
    class Request(BaseModel):
        parametro: str
    
    @web_app.post("/procesar")
    async def procesar(req: Request):
        try:
            result = mi_funcion.remote(req.parametro)
            return {"status": "success", "data": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @web_app.get("/health")
    async def health():
        return {"status": "healthy"}
    
    return web_app
```

### 5. Local Entrypoint (@app.local_entrypoint)

Para testing local antes de desplegar:

```python
@app.local_entrypoint()
def main():
    """
    Ejecuta con: modal run mi_script.py
    """
    resultado = mi_funcion.remote("datos de prueba")
    print(f"Resultado: {resultado}")
```

---

## Configuración de Secrets

Los secrets son variables de entorno cifradas que Modal inyecta en tus funciones.

### Crear Secret desde CLI

```bash
modal secret create mi-secret \
  API_KEY="sk_live_abc123..." \
  DATABASE_URL="postgresql://..."
```

### Crear Secret desde Web

1. Ve a https://modal.com/secrets
2. Click "Create Secret"
3. Nombre: `mi-secret`
4. Agrega variables:
   - Key: `API_KEY`
   - Value: `sk_live_abc123...`

### Usar Secrets en tu Script

```python
import os

@app.function(
    secrets=[modal.Secret.from_name("mi-secret")]
)
def mi_funcion():
    api_key = os.environ.get("API_KEY")
    # Usar la API key
```

### Best Practices para Secrets

✅ **DO:**
- Nombres descriptivos: `email-verifier-secrets`, `linkedin-generator-secrets`
- Agrupar secrets relacionados en un mismo secret
- Usar valores sin espacios ni saltos de línea

❌ **DON'T:**
- Hardcodear secrets en el código
- Versionar archivos con secrets
- Usar comillas extra al crear secrets

---

## OAuth con Google APIs

Este es el caso más complejo. Aquí está el proceso completo:

### Paso 1: Crear Credenciales en Google Cloud

1. Ve a [Google Cloud Console](https://console.cloud.google.com)
2. Crea un proyecto (o usa uno existente)
3. Habilita las APIs necesarias:
   - Google Sheets API
   - Google Docs API
   - Google Drive API (si es necesario)
4. Ve a "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Tipo: "Desktop app"
6. Descarga `credentials.json`

### Paso 2: Generar Token OAuth Localmente

Crea un script local con los scopes que necesitas:

```python
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import os

# ⚠️ CRÍTICO: Define TODOS los scopes que necesitarás
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive.file'
]

creds = None

if os.path.exists('token.pickle'):
    with open('token.pickle', 'rb') as token:
        creds = pickle.load(token)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
    
    with open('token.pickle', 'wb') as token:
        pickle.dump(creds, token)

print("✅ Token generado exitosamente")
```

**Ejecuta:**

```bash
python3 generar_token.py
```

Esto abrirá un navegador para autorizar. Se generará `token.pickle`.

### Paso 3: Convertir Token a JSON

Crea un script para convertir el pickle a JSON:

```python
import pickle
import json

with open('token.pickle', 'rb') as f:
    creds = pickle.load(f)

token_data = {
    "token": creds.token,
    "refresh_token": creds.refresh_token,
    "token_uri": creds.token_uri,
    "client_id": creds.client_id,
    "client_secret": creds.client_secret,
    "scopes": creds.scopes
}

token_json = json.dumps(token_data)
print(token_json)

# Guardar en archivo
with open('google_token.json', 'w') as f:
    json.dump(token_data, f, indent=2)
```

### Paso 4: Crear Secret en Modal con el Token

```bash
# Opción 1: CLI (una sola línea, sin saltos)
modal secret create mi-secret \
  API_KEY="..." \
  GOOGLE_TOKEN_JSON="$(cat google_token.json | tr -d '\n')"

# Opción 2: Web UI
# Ve a https://modal.com/secrets
# Crea el secret y pega el JSON completo en GOOGLE_TOKEN_JSON
```

⚠️ **MUY IMPORTANTE:**
- El JSON debe estar en **una sola línea** o ser JSON válido
- NO agregues comillas extra alrededor del JSON
- Copia TODO desde `{` hasta `}`

### Paso 5: Usar OAuth en Modal

```python
import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("mi-secret")]
)
def usar_google_api():
    # Obtener token desde secrets
    token_json = os.environ.get("GOOGLE_TOKEN_JSON")
    if not token_json:
        raise ValueError("GOOGLE_TOKEN_JSON no encontrado")
    
    # Parsear JSON
    token_data = json.loads(token_json)
    
    # Crear credenciales
    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes")
    )
    
    # Usar las credenciales
    service = build('sheets', 'v4', credentials=creds)
    # O: service = build('docs', 'v1', credentials=creds)
    
    # Tu lógica aquí
    return "éxito"
```

### Paso 6: Regenerar Token si Faltan Scopes

Si más tarde necesitas agregar scopes:

1. **Borra** `token.pickle` local
2. **Actualiza** SCOPES en tu script
3. **Regenera** el token (se abrirá el navegador)
4. **Convierte** a JSON nuevamente
5. **Actualiza** el secret en Modal
6. **Re-despliega** tu app

```bash
rm token.pickle
python3 generar_token.py
python3 convertir_a_json.py
modal secret delete mi-secret
modal secret create mi-secret GOOGLE_TOKEN_JSON="$(cat google_token.json | tr -d '\n')"
modal deploy mi_script.py
```

---

## Proceso de Despliegue

### 1. Preparar tu Script

Asegúrate de tener:
- ✅ Estructura Modal correcta
- ✅ Todas las dependencias en `image`
- ✅ Secrets configurados
- ✅ Funciones decoradas con `@app.function`

### 2. Verificar Secrets

```bash
modal secret list
```

Deberías ver tus secrets. Para verificar que existen los keys:

```bash
# No puedes ver los valores, pero puedes verificar la estructura
```

### 3. Deploy

```bash
modal deploy mi_script.py
```

**Salida esperada:**

```
Building image im-ABC123...
✓ Created objects.
├── 🔨 Created function mi_funcion
└── 🔨 Created web function api => https://usuario--app-api.modal.run
✓ App deployed in 12.3s! 🎉
```

### 4. Obtener URL del Endpoint

Modal te dará la URL del API:

```
https://tu-usuario--nombre-app-api.modal.run
```

Guárdala para hacer requests.

---

## Testing y Debugging

### Test Local (Antes de Desplegar)

```bash
modal run mi_script.py
```

Esto ejecuta el `@app.local_entrypoint()`.

### Test del API Desplegado

**Health Check:**

```bash
curl https://tu-usuario--app-api.modal.run/health
```

**POST Request:**

```bash
curl -X POST https://tu-usuario--app-api.modal.run/endpoint \
  -H "Content-Type: application/json" \
  -d '{"parametro": "valor"}'
```

### Ver Logs en Modal

1. Ve a https://modal.com/apps
2. Busca tu app
3. Click para ver logs en tiempo real

### Debugging Común

**Problema: Secret no encontrado**

```python
# Agregar debug
token = os.environ.get("MI_TOKEN")
print(f"🔍 Token length: {len(token) if token else 0}")
if not token:
    print("❌ MI_TOKEN no encontrado en secrets")
```

**Problema: JSON mal formateado**

```python
try:
    data = json.loads(token_json)
except json.JSONDecodeError as e:
    print(f"❌ Error parsing JSON: {e}")
    print(f"Primeros 100 chars: {token_json[:100]}")
    raise
```

---

## Casos de Uso Completos

### Caso 1: API Simple con Secret

```python
import modal
import os

app = modal.App("simple-api")

image = modal.Image.debian_slim(python_version="3.13").pip_install(
    "fastapi==0.115.6",
    "requests==2.31.0"
)

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("api-secrets")]
)
def llamar_api_externa(query: str):
    import requests
    
    api_key = os.environ.get("EXTERNAL_API_KEY")
    response = requests.get(
        "https://api.example.com/search",
        params={"q": query},
        headers={"Authorization": f"Bearer {api_key}"}
    )
    return response.json()

@app.function(image=image, secrets=[modal.Secret.from_name("api-secrets")])
@modal.asgi_app()
def api():
    from fastapi import FastAPI
    from pydantic import BaseModel
    
    web_app = FastAPI()
    
    class SearchRequest(BaseModel):
        query: str
    
    @web_app.post("/search")
    async def search(req: SearchRequest):
        result = llamar_api_externa.remote(req.query)
        return {"status": "success", "data": result}
    
    return web_app
```

**Deploy:**

```bash
modal secret create api-secrets EXTERNAL_API_KEY="sk_..."
modal deploy simple_api.py
```

### Caso 2: Procesamiento con Google Sheets

Ver `modal_verificador_correos.py` como ejemplo completo.

**Estructura:**

```python
import modal
import os
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

app = modal.App("sheets-processor")

image = modal.Image.debian_slim(python_version="3.13").pip_install(
    "google-api-python-client==2.154.0",
    "google-auth==2.45.0",
    "gspread==6.0.0"
)

def get_google_creds():
    token_json = os.environ.get("GOOGLE_TOKEN_JSON")
    token_data = json.loads(token_json)
    
    return Credentials(
        token=token_data["token"],
        refresh_token=token_data["refresh_token"],
        token_uri=token_data["token_uri"],
        client_id=token_data["client_id"],
        client_secret=token_data["client_secret"],
        scopes=token_data["scopes"]
    )

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("google-secrets")],
    timeout=600
)
def procesar_sheet(sheet_url: str):
    creds = get_google_creds()
    service = build('sheets', 'v4', credentials=creds)
    
    # Tu lógica aquí
    # ...
    
    return {"status": "success"}
```

### Caso 3: Multi-API Integration

Ver `modal_generador_posts_linkedin.py` como ejemplo.

**Combina:**
- Apify API
- Gemini AI
- Google Docs

```python
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("all-apis")],
    timeout=600
)
def pipeline_completo(input_url: str):
    # 1. Llamar Apify
    apify_result = llamar_apify(input_url)
    
    # 2. Procesar con Gemini
    ai_result = llamar_gemini(apify_result)
    
    # 3. Guardar en Google Docs
    doc_url = crear_google_doc(ai_result)
    
    return {
        "status": "success",
        "doc_url": doc_url
    }
```

---

## Troubleshooting

### Error: "Secret not found"

**Causa:** El secret no existe o el nombre es incorrecto.

**Solución:**

```bash
# Verificar secrets
modal secret list

# Recrear si es necesario
modal secret create mi-secret KEY="value"
```

### Error: "Illegal header value"

**Causa:** El secret contiene saltos de línea o caracteres inválidos.

**Solución:**

```bash
# Al crear el secret, elimina saltos de línea
modal secret create mi-secret \
  JSON_DATA="$(cat archivo.json | tr -d '\n')"
```

### Error: "Runner failed with exception: could not fetch task data"

**Causa:** El deployment anterior usa un secret que ya no existe.

**Solución:**

```bash
# Re-desplegar después de crear/actualizar secrets
modal deploy mi_script.py
```

### Error: "Request had insufficient authentication scopes"

**Causa:** El OAuth token no tiene los scopes necesarios.

**Solución:**

1. Borrar `token.pickle` local
2. Actualizar SCOPES en el script
3. Regenerar token (se abre navegador)
4. Convertir a JSON
5. Actualizar secret en Modal
6. Re-desplegar

```bash
rm token.pickle
python3 generar_token.py  # Con SCOPES actualizados
python3 convertir_token.py
modal secret delete mi-secret
modal secret create mi-secret GOOGLE_TOKEN_JSON="$(cat google_token.json | tr -d '\n')"
modal deploy mi_script.py
```

### Error: "No matching distribution found for package==X.X.X"

**Causa:** La versión especificada no existe en PyPI.

**Solución:**

```python
# Verificar versiones disponibles en PyPI
# Actualizar a versión correcta en image
image = modal.Image.debian_slim(...).pip_install(
    "package==VERSION_CORRECTA"
)
```

### Timeout en Requests

**Causa:** La función tarda más que el timeout configurado.

**Solución:**

```python
@app.function(
    timeout=1200,  # Aumentar timeout a 20 minutos
    # ...
)
```

---

## Checklist de Despliegue

Usa esta checklist antes de desplegar:

### Preparación

- [ ] Cuenta en Modal creada
- [ ] Modal CLI instalado (`pip install modal`)
- [ ] Autenticado (`modal token new`)
- [ ] Script funciona localmente

### Configuración del Script

- [ ] `app = modal.App("nombre")` definido
- [ ] `image` con todas las dependencias
- [ ] Funciones decoradas con `@app.function`
- [ ] API endpoint definido (si aplica)
- [ ] Local entrypoint para testing

### Secrets

- [ ] Todos los secrets creados en Modal
- [ ] Nombres de secrets coinciden en el código
- [ ] Variables sin saltos de línea ni espacios extra
- [ ] OAuth token (si aplica) con todos los scopes necesarios

### Deploy

- [ ] `modal deploy mi_script.py` ejecutado sin errores
- [ ] URL del endpoint guardada
- [ ] Health check funciona (`curl .../health`)
- [ ] Test con datos reales ejecutado

### Post-Deploy

- [ ] Logs revisados en Modal dashboard
- [ ] Documentación actualizada
- [ ] Equipo notificado de la nueva API

---

## Recursos Adicionales

- [Documentación Oficial de Modal](https://modal.com/docs)
- [Modal Examples](https://github.com/modal-labs/modal-examples)
- [Google OAuth Documentation](https://developers.google.com/identity/protocols/oauth2)
- [FastAPI Documentation](https://fastapi.tiangolo.com)

---

## Ejemplos de Referencia

En este proyecto tienes 3 ejemplos completos:

1. **[`modal_example.py`](file:///Users/joseangelesparzaresendiz/Documents/Agentic%20Workflows/Antigravity%20videos/Prueba%201/modal_example.py)** - Template básico
2. **[`modal_verificador_correos.py`](file:///Users/joseangelesparzaresendiz/Documents/Agentic%20Workflows/Antigravity%20videos/Prueba%201/modal_verificador_correos.py)** - Google Sheets + API externa
3. **[`modal_generador_posts_linkedin.py`](file:///Users/joseangelesparzaresendiz/Documents/Agentic%20Workflows/Antigravity%20videos/Prueba%201/modal_generador_posts_linkedin.py)** - Multi-API + Google Docs

Estudia estos ejemplos para entender patrones comunes.

---

## Conclusión

Desplegar en Modal es un proceso de 3 pasos:

1. **Preparar**: Script + imagen con dependencias
2. **Configurar**: Secrets en Modal
3. **Desplegar**: `modal deploy`

El caso de OAuth con Google es el más complejo, pero siguiendo este proceso funciona:

1. Generar token localmente con **TODOS** los scopes
2. Convertir a JSON
3. Crear secret en Modal
4. Usar en el código

**Recuerda:** Si necesitas agregar scopes después, debes regenerar el token completo.

¡Buena suerte con tus deployments! 🚀
