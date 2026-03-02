#!/bin/bash

# Este script automatiza la instalación inicial de los certificados SSL antes de levantar Nginx
# Úsalo en el servidor Oracle solo una vez.

domains=(example.com) # 🔴 REEMPLAZA ESTO
email="tu_email@gmail.com" # 🔴 REEMPLAZA ESTO
data_path="./certbot"

# Iniciar un contenedor dummy para obtener el certificado
docker compose run --rm --entrypoint "\
  certbot certonly --webroot -w /var/www/certbot \
    -d ${domains[0]} \
    --email $email \
    --rsa-key-size 4096 \
    --agree-tos \
    --force-renewal" certbot

echo "### Recargando Nginx ###"
docker compose exec nginx nginx -s reload
