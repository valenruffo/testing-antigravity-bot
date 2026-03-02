# Arquitectura del Servidor VPS (Oracle Cloud)

Este documento explica cómo está estructurado actualmente el servidor VPS en Oracle Cloud y cuál es la estrategia recomendada para escalar y alojar a múltiples clientes en el futuro.

---

## 🏗️ 1. Estado Actual: ¿Qué hay en tu Servidor?

Tu máquina virtual de Oracle corre **Ubuntu Linux**. Adentro de ella, no instalamos Python ni librerías regadas por todas partes. En su lugar, instalamos el motor de **Docker**.

Docker actúa como una empresa de bienes raíces que administra diferentes "casas" (contenedores). Cada casa es completamente independiente, tiene su propia versión de Linux, su propio Python y sus propias reglas, y no puede espiar lo que pasa en la casa del vecino.

Actualmente tienes una sola "Propiedad" funcionando en `~/testing-antigravity-bot/`. Adentro de esa carpeta vive un archivo maestro llamado `docker-compose.yml` que orquesta **dos contenedores trabajando en equipo**:

1.  **Contenedor App (`ricardo_bot_app`)**: Es el cerebro. Escucha en el puerto `8000`, tiene LangGraph, OpenAI y los scripts de Python.
2.  **Contenedor Tunnel (`ricardo_bot_tunnel`)**: Es el escudo de seguridad. Este contenedor levanta el Túnel de Cloudflare, se pega a la puerta `8000` de la App, la encripta y la saca a Internet (recibiendo los webhooks de Meta).

> **Aislamiento Total**: Toda tu aplicación actual existe y respira aisaldamente adentro de la carpeta `~/testing-antigravity-bot/`. Si borras esa carpeta, borras tu sistema.

---

## 🏘️ 2. Estrategia Multi-Cliente (Multi-Tenant)

Has preguntado: *"¿Por cada cliente crearé un container nuevo docker o un mismo container y ahí carpetas separadas?"*

**La Única Respuesta Profesional:** Debes crear **un ecosistema Docker (2 contenedores) NUEVO por cada cliente, alojando cada cliente en una carpeta separada.**

Nunca metas el código y los tokens de diferentes clientes dentro del mismo contenedor o bot. Eso es un desastre de seguridad, privacidad y mantenimiento.

### ¿Cómo se verá tu servidor en el futuro?

Imagina que consigues 3 clientes (Ricardo Inmobiliaria, Pizzeria Mamma Mia, y Abogados Smith). Tu servidor Oracle por dentro debería verse así:

```text
/home/ubuntu/
├── cliente_ricardo_inmobiliaria/
│   ├── .env                    (Tokens de Ricardo)
│   ├── docker-compose.yml      (Orquestador de Ricardo)
│   └── scripts/                (Lógica de Ricardo)
│
├── cliente_pizzeria_mammamia/
│   ├── .env                    (Tokens de La Pizzería)
│   ├── docker-compose.yml      (Orquestador de La Pizzería)
│   └── scripts/                (Lógica de La Pizzería)
│
└── cliente_abogados_smith/
    ├── .env                    (Tokens de Los Abogados)
    ├── docker-compose.yml      (Orquestador de Los Abogados)
    └── scripts/                (Lógica de Los Abogados)
```

### El Flujo para dar de alta un Nuevo Cliente

Cuando firmes un nuevo contrato, seguirás los siguientes pasos:

1.  **Copiar y Pegar**: Agarras la carpeta limpia de tu Bot base (`testing-antigravity-bot`) y haces una copia renombrándola (Ej: `cliente_pizzeria`).
2.  **Modificar Nombres en `docker-compose.yml`**: Abre el archivo del nuevo cliente y cambia los nombres para que no choquen con Ricardo.
    *   `container_name: ricardo_bot_app` 👉 `container_name: pizzeria_bot_app`
    *   `container_name: ricardo_bot_tunnel` 👉 `container_name: pizzeria_bot_tunnel`
3.  **Inyectar Secretos Nuevos**: Modificas su archivo `.env` para pegarle:
    *   Su propio Nuevo Token de WhatsApp Meta (del negocio del cliente).
    *   Su propio Nuevo Token de Cloudflare (creas un túnel nuevo en Cloudflare).
    *   Tus propios Tokens de OpenAI (tú pagas las llamadas LLM del cliente con tu API Key).
4.  **Adaptar Prompts**: Cambias el `prompts.py` y el `main.py` de su carpeta para enseñarle a ser vendedor de pizzas en vez de Broker.
5.  **Desplegar**: Te metes a su carpeta específica en el servidor (`cd cliente_pizzeria`) y ejecutas `docker compose up -d`.

### Ventajas de este Modelo Aislado (Microservicios)

*   **Seguridad y Privacidad Estricta**: Si el contenedor de Pizzeria es hackeado o quiebra y da un error 500 fatal en Python porque metiste un parche mal codificado... ¡El Bot de la inmobiliaria Ricardo seguirá funcionando perfectamente! Ni se enterará.
*   **Gestión Cero Puertos**: Gracias a que _cada cliente_ tiene su propio Túnel de Cloudflare en su `docker-compose.yml`, todos los Bots de Python pueden fingir usar el mismo puerto local `8000` internamente (porque Docker los aísla mágicamente de la red pública). No tienes que estar abriendo puertos raros como el `8001`, `8002`, `8003` en el Servidor (Nginx / Firewall). Cloudflare se traga todo el tráfico molesto y lo redirige limpiamente.

---

## 📚 Conclusión del Sistema Base

El repositorio base que tienes ahora mismo en tu PC (`C:\Users\valen\Desktop\test_bot`) lo debes tratar como la **Plantilla Madre (Boilerplate)**.

Cuando quieras innovar o arreglar un error central, editas este repositorio, subes las mejoras a GitHub, y luego bajas la actualización (git pull) a las carpetas de los distintos clientes que tengas alojados en Oracle o en otros servidores que arriendes a futuro.
