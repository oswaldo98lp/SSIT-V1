# Guía de Despliegue en Producción — Admón Almacén SSIT 2.0

Esta guía describe los pasos necesarios para desplegar y operar el sistema **Admón Almacén SSIT 2.0** en un entorno de producción basado en **Docker, MariaDB 11, Gunicorn y Nginx**.

---

## 1. Requisitos Previos

- Servidor Linux (Debian 12 / Ubuntu 22.04 LTS o superior).
- Docker Engine 24.0+ y Docker Compose V2.
- Dominio o FQDN configurado (ej. `almacen.ssit.internal`).
- Certificados SSL/TLS (Let's Encrypt o corporativos) colocados en `deploy/ssl/` (`fullchain.pem` y `privkey.pem`).

---

## 2. Preparación de Variables de Entorno

Copie la plantilla de variables de entorno y configure los secretos:

```bash
cp .env.example .env
nano .env
```

Genere una `SECRET_KEY` segura:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

---

## 3. Despliegue con Docker Compose

1. **Construir y levantar los contenedores**:
   ```bash
   docker compose up -d --build
   ```

2. **Verificar el estado de los servicios**:
   ```bash
   docker compose ps
   ```

3. **Revisar los logs de inicialización**:
   ```bash
   docker compose logs -f web
   ```

El script `entrypoint.sh` se encarga automáticamente de:
- Esperar a que MariaDB esté lista.
- Ejecutar migraciones (`python manage.py migrate`).
- Cargar roles, catálogos y estructura organizacional (`seed_roles`, `seed_catalogs`, `seed_org`).
- Recolectar estáticos (`python manage.py collectstatic`).
- Levantar Gunicorn con el número óptimo de workers.

---

## 4. Creación del Superusuario Inicial

Para crear el primer administrador:
```bash
docker compose exec web python manage.py createsuperuser
```

---

## 5. Migración de Datos Históricos (ETL)

Si dispone de archivos CSV legacy exportados desde AppSheet:

```bash
# 1. Simulación sin guardar cambios (Dry-Run)
docker compose exec web python manage.py import_legacy_data \
    --vouchers-csv /ruta/vales.csv \
    --cases-csv /ruta/casos.csv \
    --items-csv /ruta/inventario.csv \
    --dry-run

# 2. Importación definitiva
docker compose exec web python manage.py import_legacy_data \
    --vouchers-csv /ruta/vales.csv \
    --cases-csv /ruta/casos.csv \
    --items-csv /ruta/inventario.csv
```

---

## 6. Conciliación de Inventario Físico

Para contrastar el inventario físico contra el Kárdex en producción:

```bash
docker compose exec web python manage.py reconcile_inventory \
    --physical-csv /ruta/conteo_fisico.csv \
    --export-xlsx /app/media/reporte_conciliacion.xlsx
```

O bien, utilizar la interfaz web en `https://almacen.ssit.internal/reports/reconciliation/`.

---

## 7. Estrategia de Respaldos (Backups)

### Respaldo de Base de Datos MariaDB
```bash
docker compose exec db mysqldump -u ssit_user -p --single-transaction --quick ssit_db > backup_ssit_$(date +%Y%m%d_%H%M%S).sql
```

### Respaldo de Documentos y Firmas (Media)
```bash
tar -czvf backup_media_$(date +%Y%m%d).tar.gz /var/lib/docker/volumes/ssit_media_volume/_data
```

---

## 8. Monitoreo y Mantenimiento

- **Logs de Django y Seguridad**: `logs/django.log`
- **Logs de Nginx**: `docker compose logs nginx`
- **Reinicio del Servicio**: `docker compose restart web`
