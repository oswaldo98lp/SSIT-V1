"""Custom Permissions declarations for SSIT 2.0 Business Actions."""
from django.db import models


class BusinessPermission(models.Model):
    """
    Virtual model used to declare custom business permissions in Django.
    These permissions represent action families mapped to transition rules.
    """
    class Meta:
        managed = False  # No table is created in database
        default_permissions = ()
        permissions = [
            # Vouchers & Dispatches
            ("create_voucher", "Puede crear vales de salida"),
            ("authorize_voucher", "Puede autorizar vales de salida"),
            ("cancel_voucher", "Puede cancelar vales y líneas de vale"),
            ("dispatch_voucher", "Puede surtir vales con número de serie"),
            ("cancel_dispatched_item", "Puede cancelar piezas surtidas (dentro de 120h)"),

            # Returns, Repair & Workshop
            ("register_return", "Puede registrar devolución de equipo desde centro"),
            ("confirm_return", "Puede confirmar devolución y emitir dictamen de almacén"),
            ("assign_repair_folio", "Puede asignar folio de reparación de oficina"),
            ("assign_engineer", "Puede asignar ingeniero para reparación"),
            ("define_equipment", "Puede definir equipo técnico (reparado/huesario/garantía)"),
            ("review_definition_boss", "Puede confirmar o rechazar definición técnica (Jefe)"),
            ("review_definition_warehouse", "Puede confirmar definición técnica en almacén"),
            ("manage_scrap", "Puede gestionar flujo de entrega a huesario/scrap"),
            ("manage_workshop", "Puede gestionar traslados a taller habilitado"),
            ("assign_workshop_repair", "Puede asignar reparación dentro de taller"),
            ("define_workshop_equipment", "Puede dictaminar y definir equipo en taller"),

            # Special & Reports Permissions
            ("view_coupa_consumption", "Puede consultar y registrar consumos Coupa"),
            ("register_return_without_dispatch", "Puede registrar devolución sin salida previa"),
            ("view_zone_reports", "Puede consultar bitácoras y reportes a nivel zona"),
            ("export_reports", "Puede exportar reportes y kárdex a formato Excel/XLSX"),
            ("view_case", "Puede consultar casos de devolución"),
        ]


def has_permission(user, permission_code: str) -> bool:
    """Checks whether the user possesses the business permission, by superuser, global scope, or group."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, "has_global_scope", False):
        return True
    return user.has_perm(f"accounts.{permission_code}")

