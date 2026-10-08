from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.accounts.permissions import BusinessPermission

# Matriz de roles activos y sus permisos asignados
ROLE_PERMISSIONS_MAP = {
    "SOPORTE_TI": [
        "create_voucher",
        "register_return",
        "define_equipment",
        "view_case",
    ],
    "JEFE_SOPORTE": [
        "authorize_voucher",
        "cancel_voucher",
        "assign_engineer",
        "review_definition_boss",
        "view_zone_reports",
        "view_case",
    ],
    "GERENTE_SSIT": [
        "create_voucher",
        "authorize_voucher",
        "cancel_voucher",
        "dispatch_voucher",
        "cancel_dispatched_item",
        "register_return",
        "confirm_return",
        "assign_repair_folio",
        "assign_engineer",
        "define_equipment",
        "review_definition_boss",
        "review_definition_warehouse",
        "manage_scrap",
        "manage_workshop",
        "assign_workshop_repair",
        "define_workshop_equipment",
        "view_coupa_consumption",
        "register_return_without_dispatch",
        "view_zone_reports",
        "export_reports",
        "view_case",
    ],
    "GERENTE_ZONA": [
        "authorize_voucher",
        "cancel_voucher",
        "assign_engineer",
        "review_definition_boss",
        "view_zone_reports",
        "export_reports",
        "view_case",
    ],
    "ALMACEN": [
        "dispatch_voucher",
        "cancel_dispatched_item",
        "confirm_return",
        "review_definition_warehouse",
        "manage_scrap",
        "export_reports",
        "view_case",
    ],
    "OFICINA": [
        "assign_repair_folio",
        "export_reports",
        "view_case",
    ],
    "JEFE_TALLER": [
        "authorize_voucher",
        "manage_workshop",
        "assign_engineer",
        "assign_workshop_repair",
        "review_definition_boss",
        "export_reports",
        "view_case",
    ],
    "SOPORTE_TALLER": [
        "define_equipment",
        "define_workshop_equipment",
        "view_case",
    ],
}

# Roles heredados que quedan creados pero desactivados
LEGACY_ROLES = ["EVENTUAL", "ENCARGADO_SOPORTE", "GERENTE_TITULAR"]


class Command(BaseCommand):
    help = "Seeds standard SSIT roles (Django Groups) and configures permissions idempotently."

    def handle(self, *args, **options):
        self.stdout.write("--- Inicializando Roles y Permisos de Negocio ---")

        # 0. Asegurar que los permisos personalizados de BusinessPermission existan en la BD
        content_type, _ = ContentType.objects.get_or_create(
            app_label="accounts",
            model="user",
        )
        for codename, name in BusinessPermission._meta.permissions:
            Permission.objects.get_or_create(
                codename=codename,
                content_type=content_type,
                defaults={"name": name},
            )

        # 1. Crear o actualizar roles activos con sus permisos
        for role_name, perm_codes in ROLE_PERMISSIONS_MAP.items():
            group, created = Group.objects.get_or_create(name=role_name)
            action = "Creado" if created else "Existente"

            # Asociar permisos
            permissions = Permission.objects.filter(codename__in=perm_codes)
            group.permissions.set(permissions)
            self.stdout.write(
                self.style.SUCCESS(f"[{action}] Rol activo '{role_name}' con {permissions.count()} permisos asignados.")
            )

        # 2. Crear roles heredados (sin permisos)
        for legacy_role in LEGACY_ROLES:
            group, created = Group.objects.get_or_create(name=legacy_role)
            action = "Creado" if created else "Existente"
            group.permissions.clear()
            self.stdout.write(
                self.style.WARNING(f"[{action}] Rol heredado '{legacy_role}' (desactivado / sin menu).")
            )

        self.stdout.write(self.style.SUCCESS("[OK] Proceso seed_roles finalizado correctamente."))
