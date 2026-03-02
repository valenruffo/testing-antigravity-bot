# Directiva: Configuración de Cloudflare Zero Trust (Webhooks Meta)

Esta directiva documenta el proceso estandarizado para reemplazar puertos abiertos e IPs expuestas en nuestro VPS de Oracle con túneles seguros privados de Cloudflare. Esto es indispensable para pasar la validación TLS estricta de **Meta Developers**.

## Requisitos de la Tarea
- Acceso al panel de control de [Cloudflare Zero Trust](https://one.dash.cloudflare.com/).
- El dominio registrado de la Inmobiliaria administrado a través de los servidores de nombres (DNS) de Cloudflare.

## Pasos de Configuración en el Dashboard

1. Ingresar en **Cloudflare Zero Trust** → Networks → Tunnels.
2. Hacer click en **Create a tunnel**. Seleccionar opción **Cloudflared**.
3. Nombrar el túnel (Ej: `bot-whatsapp-ricardo`).
4. **🔴 OBTENCIÓN DEL TOKEN:** Copiar el token de la sección _"Install and run a connector"_. Es una cadena extremadamente larga en Base64.
5. Pegar ese token crudo (sin los comandos de linux) dentro del archivo `.env` del servidor Oracle bajo el nombre `CLOUDFLARE_TOKEN="..."`.

## Configuración de Ruteo Inverso (Public Hostname)

Una vez enrutado, Cloudflare te preguntará qué URL pública quieres conectar con qué servicio interno.
- **Subdomain:** Elige la URL elegida (ej. `api` o `bot`).
- **Domain:** Selecciona tu dominio en Cloudflare.
- **Path:** Vacío.
- **Service Type:** `HTTP`
- **URL:** `app:8000` *(este es el nombre interno del contenedor Docker en nuestro compose)*.

## Trampas / Casos Borde
- **Fallo SSL en Webhook:** Si eliges `HTTPS` en `Service Type`, Cloudflare reportará error "Bad Gateway", porque nuestra aplicación interna (FastAPI) levanta en HTTP puro. La desencriptación SSL ocurre en los servidores frontales de Cloudflare, la comunicación interna dentro de la red Docker es `HTTP`.
- **Modificación en Docker:** Si el token no está validado como variable de sistema, el contenedor de `cloudflared` fallará al iniciar y en el log arrojará error de token inexistente. El comando a usar SIEMPRE es el nativo de Docker Compose: `CLOUDFLARE_TOKEN="tu-token" docker compose up -d`.
