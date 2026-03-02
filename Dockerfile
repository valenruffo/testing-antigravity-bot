FROM python:3.13-slim

# Evitar que Python genere archivos pyc y no bufferice la salida estándar
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copiar requerimientos e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente
COPY . .

# Establecer el directorio de trabajo donde están los scripts para que los imports locales funcionen
WORKDIR /app/scripts

# Exponer el puerto de Uvicorn
EXPOSE 8000

# Comando de inicio
CMD ["uvicorn", "bot_whatsapp:app", "--host", "0.0.0.0", "--port", "8000"]
