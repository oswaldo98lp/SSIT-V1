#!/bin/sh
set -e

echo "=== Iniciando Admón Almacén SSIT 2.0 en Producción ==="

# 1. Esperar a que la base de datos esté lista
echo "Esperando conexión con la base de datos MariaDB..."
python -c '
import time, os, sys
from django.db import connections
from django.db.utils import OperationalError

for _ in range(30):
    try:
        conn = connections["default"]
        conn.cursor()
        print("¡Conexión exitosa a MariaDB!")
        sys.exit(0)
    except OperationalError:
        print("Base de datos no disponible aún, esperando 2 segundos...")
        time.sleep(2)
sys.exit(1)
'

# 2. Aplicar migraciones
echo "Aplicando migraciones de base de datos..."
python manage.py migrate --noinput

# 3. Inicializar roles, catálogos y organización si no existen
echo "Sincronizando catálogos, roles y estructura organizacional..."
python manage.py seed_roles
python manage.py seed_catalogs
python manage.py seed_org

# 4. Recolectar archivos estáticos
echo "Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

# 5. Iniciar servidor Gunicorn
echo "Iniciando Gunicorn..."
exec "$@"
