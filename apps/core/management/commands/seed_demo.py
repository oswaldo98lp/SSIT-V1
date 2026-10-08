"""Idempotent seed command for Demo test users across all 8 business roles."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from apps.catalog.models import CatalogValue
from apps.inventory.models import EquipmentModel
from apps.org.models import Center, Region

User = get_user_model()

DEMO_USERS = [
    {
        "email": "soporte.oaxc@test-ssit.local",
        "full_name": "Ingeniero Soporte TI Sintético",
        "employee_number": "EMP-1001",
        "position": "Ingeniero de Soporte TI en Campo",
        "region_code": "OAXC",
        "roles": ["SOPORTE_TI"],
        "has_global_scope": False,
        "is_staff": False,
    },
    {
        "email": "jefe.oaxc@test-ssit.local",
        "full_name": "Jefe Soporte Oaxaca Sintético",
        "employee_number": "EMP-1002",
        "position": "Jefe de Soporte Regional",
        "region_code": "OAXC",
        "roles": ["JEFE_SOPORTE"],
        "has_global_scope": False,
        "is_staff": False,
    },
    {
        "email": "gerente.ssit@test-ssit.local",
        "full_name": "Gerente Nacional SSIT Sintético",
        "employee_number": "EMP-1003",
        "position": "Gerente Nacional de SSIT",
        "region_code": "AZCP",
        "roles": ["GERENTE_SSIT"],
        "has_global_scope": True,
        "is_staff": True,
    },
    {
        "email": "gerente.zona1@test-ssit.local",
        "full_name": "Gerente Zona 1 Sintético",
        "employee_number": "EMP-1004",
        "position": "Gerente Operativo de Zona 1",
        "region_code": "OAXC",
        "roles": ["GERENTE_ZONA"],
        "has_global_scope": False,
        "is_staff": False,
    },
    {
        "email": "almacen.oaxc@test-ssit.local",
        "full_name": "Encargado Almacén Oaxaca Sintético",
        "employee_number": "EMP-1005",
        "position": "Encargado de Almacén y Surtido",
        "region_code": "OAXC",
        "roles": ["ALMACEN"],
        "has_global_scope": False,
        "is_staff": False,
    },
    {
        "email": "oficina.central@test-ssit.local",
        "full_name": "Oficina Central de Folios Sintético",
        "employee_number": "EMP-1006",
        "position": "Analista de Oficina de Soporte",
        "region_code": "AZCP",
        "roles": ["OFICINA"],
        "has_global_scope": False,
        "is_staff": False,
    },
    {
        "email": "jefe.taller@test-ssit.local",
        "full_name": "Jefe Taller Oaxaca Sintético",
        "employee_number": "EMP-1007",
        "position": "Jefe de Taller Habilitado",
        "region_code": "OAXC",
        "roles": ["JEFE_TALLER"],
        "has_global_scope": False,
        "is_staff": False,
    },
    {
        "email": "soporte.taller@test-ssit.local",
        "full_name": "Técnico Taller Oaxaca Sintético",
        "employee_number": "EMP-1008",
        "position": "Técnico Especialista de Taller",
        "region_code": "OAXC",
        "roles": ["SOPORTE_TALLER"],
        "has_global_scope": False,
        "is_staff": False,
    },
]

DEMO_EQUIPMENT = [
    {"name": "Impresora Térmica POS 80mm", "brand": "Epson", "model": "TM-T88VI", "category_code": "IMPRESION_SCANNER"},
    {"name": "Laptop Corporativa Core i5", "brand": "Dell", "model": "Latitude 3420", "category_code": "EQUIPO_COMPUTO"},
    {"name": "Switch Administrable 24 Puertos Gigabit", "brand": "Cisco", "model": "Catalyst 1000", "category_code": "REDES_COMUNICACIONES"},
    {"name": "Lector Código de Barras 2D Inalámbrico", "brand": "Zebra", "model": "DS2278", "category_code": "PERIFERICOS_ACCESORIOS"},
    {"name": "Fuente de Poder 500W Certificada", "brand": "EVGA", "model": "500 W1", "category_code": "REFACCIONES_PARTES"},
]


class Command(BaseCommand):
    help = "Seeds standard demo test users and sample equipment models."

    def handle(self, *args, **options):
        self.stdout.write("--- Inicializando Usuarios Demo y Equipos de Muestra ---")
        default_password = "PasswordDemo123!"

        for user_data in DEMO_USERS:
            region = Region.objects.filter(code=user_data["region_code"]).first()
            center = Center.objects.filter(region=region).first() if region else None

            user, created = User.objects.update_or_create(
                email=user_data["email"],
                defaults={
                    "full_name": user_data["full_name"],
                    "employee_number": user_data["employee_number"],
                    "position": user_data["position"],
                    "region": region,
                    "center": center,
                    "has_global_scope": user_data["has_global_scope"],
                    "is_staff": user_data["is_staff"],
                    "is_active": True,
                },
            )
            user.set_password(default_password)
            user.save()

            # Asignar grupos de roles
            for role_name in user_data["roles"]:
                group = Group.objects.filter(name=role_name).first()
                if group:
                    user.groups.add(group)

            status_str = "Creado" if created else "Actualizado"
            self.stdout.write(f"[{status_str}] Usuario '{user.email}' (Rol: {', '.join(user_data['roles'])})")

        # Equipos de muestra
        for eq in DEMO_EQUIPMENT:
            cat = CatalogValue.objects.filter(catalog="MATERIAL_CATEGORY", code=eq["category_code"]).first()
            EquipmentModel.objects.update_or_create(
                name=eq["name"],
                defaults={
                    "brand": eq["brand"],
                    "model": eq["model"],
                    "category": cat,
                    "is_inventoriable": True,
                },
            )

        self.stdout.write(self.style.SUCCESS("[OK] Usuarios de prueba y catalogo de equipos listos."))
