"""Case services: legacy status parity calculator and workflow helpers."""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import EquipmentCase


def legacy_status(case: "EquipmentCase") -> str:
    """
    Pure function porting the legacy consolidated formula for the column 'ESTÁTUS'.
    Evaluates branch by branch against the case attributes and stage.
    """
    stage = case.stage or ""

    # 1. Finalizados
    if stage == "FINALIZADO":
        if case.definition == "HUESARIO" or getattr(case, "scrap_status", None) == "ENVIADO":
            return "FINALIZADO CON ENVÍO A HUESARIO"
        return "FINALIZADO CON ENTRADA A ALMACÉN"

    if stage == "FINALIZADO_HUESARIO":
        return "FINALIZADO CON ENVÍO A HUESARIO"

    if stage in ["SIN_DEVOLUCION", "FINALIZADO_SIN_DEVOLUCION"]:
        return "FINALIZADO SIN DEVOLUCIÓN"

    if stage == "FINALIZADO_CANCELADO":
        return "CANCELADO FINALIZADO CON ENTRADA"

    # 2. Cancelaciones
    if stage == "CANCELADA":
        return "CANCELADO PENDIENTE DE CONFIRMAR POR GERENTE"

    if stage == "CANCELACION_CONFIRMADA":
        return "CANCELADO PENDIENTE DE CONFIRMAR ENTRADA A ALMACÉN"

    # 3. Devolución en centro
    if stage == "PENDIENTE_CONFIRMAR":
        return "PENDIENTE CONFIRMAR DEVOLUCIÓN"

    if stage == "EN_REVISION":
        return "DEVOLUCIÓN EN REVISIÓN"

    # 4. Taller Habilitado
    if stage == "EN_TRANSITO_TALLER":
        return "EN TRÁNSITO A TALLER"

    if stage == "EN_REVISION_TALLER":
        return "EN REVISIÓN EN TALLER"

    if stage == "EN_ESPERA_REFACCION":
        return "EN ESPERA DE REFACCIÓN"

    # 5. Huesario
    if stage == "HUESARIO_CONFIRMADO":
        return "HUESARIO PENDIENTE DE RECIBIR POR ALMACÉN"

    # 6. Confirmado por almacén / Pendientes de oficina o asignación
    if stage == "CONFIRMADO":
        if not getattr(case, "repair_folio", None):
            return "PENDIENTE DE GENERAR FOLIO DE REPARACIÓN"
        if not getattr(case, "assigned_engineer", None):
            return "PENDIENTE DE ASIGNAR REPARACIÓN A INGENIERO"
        return "CONFIRMADO PARA REPARACIÓN"

    # 7. Asignado / Por Reparar
    if stage in ["POR_REPARAR", "ASIGNADO", "EN_TALLER"]:
        return "PENDIENTE DE DEFINIR"

    # 8. Garantías
    if stage == "ENVIADO_GARANTIA":
        return "EQUIPO ENVIADO A GARANTÍA NO CONFIRMADO POR JEFE"

    # 9. Definido
    if stage == "DEFINIDO":
        if getattr(case, "definition", None) == "GARANTIA" and not getattr(case, "warranty_solution", None):
            return "EQUIPO ENVIADO A GARANTÍA SIN SOLUCIÓN"
        return "PENDIENTE CONFIRMAR DEFINICIÓN"

    # 10. Confirmado por Jefe
    if stage == "CONFIRMADO_JEFE":
        if getattr(case, "definition", None) == "REPARADO":
            return "REPARADO PENDIENTE DE ENTRAR A ALMACÉN"
        if getattr(case, "definition", None) == "HUESARIO":
            return "HUESARIO PENDIENTE DE RECIBIR POR ALMACÉN"
        return "CONFIRMADO POR JEFE"

    return stage
