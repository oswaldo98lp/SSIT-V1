"""Transition Engine Services.

All business operations execute through apply_transition() inside transaction.atomic
with select_for_update() to prevent race conditions and guarantee full audit tracking.
"""
from datetime import timedelta
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.cases.models import EquipmentCase
from apps.core.models import CoreEvent
from apps.inventory.models import InventoryItem, InventoryMovement
from apps.transitions.models import TransitionRule
from apps.transitions.registry import TRANSITIONS_REGISTRY
from apps.vouchers.models import Voucher, VoucherLine


def sync_transitions_to_db() -> int:
    """Synchronizes declarative TRANSITIONS_REGISTRY definitions into transitions_rule table."""
    count = 0
    for code, config in TRANSITIONS_REGISTRY.items():
        TransitionRule.objects.update_or_create(
            code=code,
            defaults={
                "label": config["label"],
                "entity": config["entity"],
                "from_stages": config["from_stages"],
                "to_stage": config["to_stage"],
                "permission": config["permission"],
                "scope_rule": config["scope_rule"],
                "inputs_schema": config.get("inputs_schema", {}),
                "conditions": config.get("conditions", {}),
                "kardex_effect": config.get("kardex_effect", TransitionRule.KardexEffect.NONE),
                "is_bulk": config.get("is_bulk", False),
                "is_active": True,
            },
        )
        count += 1
    return count


def check_user_scope_for_entity(user, entity_instance, scope_rule: str) -> bool:
    """Validates whether an entity is within the user's allowed geographical/organizational scope."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, "has_global_scope", False) or scope_rule == "GLOBAL":
        return True

    allowed_region_ids = set(user.allowed_regions().values_list("id", flat=True))

    if isinstance(entity_instance, Voucher):
        return entity_instance.region_id in allowed_region_ids
    elif isinstance(entity_instance, VoucherLine):
        return entity_instance.voucher.region_id in allowed_region_ids
    elif isinstance(entity_instance, InventoryItem):
        return entity_instance.region_id in allowed_region_ids
    elif isinstance(entity_instance, EquipmentCase):
        if scope_rule == "ASSIGNED":
            return entity_instance.assigned_engineer_id == user.id
        return (
            entity_instance.origin_region_id in allowed_region_ids
            or (entity_instance.workshop_region_id and entity_instance.workshop_region_id in allowed_region_ids)
        )
    return False


def get_available_transitions(user, entity_instance) -> list[dict[str, Any]]:
    """Returns list of transition rules available for the user on a specific entity instance."""
    if not user or not user.is_authenticated:
        return []

    available = []
    current_stage = getattr(entity_instance, "stage", None) or getattr(entity_instance, "status", "")

    for _code, config in TRANSITIONS_REGISTRY.items():
        # 1. Match entity type
        entity_name = entity_instance.__class__.__name__.upper()
        if entity_name == "VOUCHERLINE":
            entity_name = "LINE"
        elif entity_name == "EQUIPMENTCASE":
            entity_name = "CASE"
        elif entity_name == "INVENTORYITEM":
            entity_name = "ITEM"

        if config["entity"] != entity_name:
            continue

        # 2. Check permission
        from apps.accounts.permissions import has_permission
        if not has_permission(user, config["permission"]):
            continue

        # 3. Check stage
        if config["from_stages"] and current_stage not in config["from_stages"] and "" not in config["from_stages"]:
            continue

        # 4. Check scope
        if not check_user_scope_for_entity(user, entity_instance, config["scope_rule"]):
            continue

        available.append(config)
    return available


@transaction.atomic
def apply_transition(user, entity_instance: Any, transition_code: str, data: dict[str, Any] | None = None) -> CoreEvent:
    """
    Executes a transition on an entity inside transaction.atomic with select_for_update.
    Validates permission, scope, stage and conditions. Writes CoreEvent and Kardex movement.
    """
    data = data or {}
    rule = TRANSITIONS_REGISTRY.get(transition_code)
    if not rule:
        raise ValidationError(f"La transición '{transition_code}' no existe en el registro.")

    # 1. Permission check
    from apps.accounts.permissions import has_permission
    if not has_permission(user, rule["permission"]):
        raise PermissionDenied(f"No tienes el permiso '{rule['permission']}' requerido para ejecutar '{rule['label']}'.")

    # 2. Scope check (unless entity is None for creation transitions)
    if entity_instance is not None:
        # Lock record with select_for_update
        model_class = entity_instance.__class__
        entity_instance = model_class.objects.select_for_update().get(pk=entity_instance.pk)

        if not check_user_scope_for_entity(user, entity_instance, rule["scope_rule"]):
            raise PermissionDenied(f"El registro #{entity_instance.pk} está fuera de tu región o alcance asignado.")

    # 3. From stage check
    current_stage = getattr(entity_instance, "stage", None) or getattr(entity_instance, "status", "") if entity_instance else ""
    if rule["from_stages"] and current_stage not in rule["from_stages"] and "" not in rule["from_stages"]:
        raise ValidationError(
            f"Transición inválida: La etapa actual '{current_stage}' no permite la acción '{rule['label']}'."
        )

    # 4. Specific Business Logic & Conditions
    target_stage = rule["to_stage"]
    comments = data.get("comments", "")
    reason_code = str(data.get("reason_id", data.get("cancel_reason_id", data.get("ruling_id", ""))))

    # Dispatch logic
    if transition_code == "dispatch_voucher":
        if not entity_instance.authorized_at:
            raise ValidationError("El vale debe estar previamente autorizado para ser surtido.")

        entity_instance.status = Voucher.Status.SURTIDO
        entity_instance.delivered_by = user
        entity_instance.delivered_at = timezone.now()
        entity_instance.received_by_id = data.get("received_by_id")
        entity_instance.comments = comments or entity_instance.comments
        entity_instance.save()

        # Update lines and create items + kardex
        for item_info in data.get("items_data", []):
            line_id = item_info.get("line_id")
            line = VoucherLine.objects.filter(id=line_id, voucher=entity_instance).first()
            if line:
                line.status = VoucherLine.LineStatus.SURTIDO
                line.save()

            model_id = item_info.get("model_id") or (line.equipment_model_id if line else None)
            item = InventoryItem.objects.create(
                voucher=entity_instance,
                line=line,
                equipment_model_id=model_id,
                serial_number=item_info["serial_number"],
                condition=item_info.get("condition", InventoryItem.Condition.RECUPERADO),
                warehouse=item_info.get("warehouse", InventoryItem.Warehouse.STOCK),
                region_id=entity_instance.region_id,
                dispatched_at=timezone.now(),
            )

            # Kardex SALIDA
            InventoryMovement.objects.create(
                movement_type=InventoryMovement.MovementType.SALIDA,
                equipment_model_id=model_id,
                serial_number=item.serial_number,
                condition=item.condition,
                warehouse=item.warehouse,
                region_id=entity_instance.region_id,
                quantity=1,
                moved_at=timezone.now(),
                transfer_folio=entity_instance.report_folio or f"VALE-{entity_instance.id}",
                item=item,
                confirmed=True,
                created_by=user,
            )

    elif transition_code == "authorize_voucher":
        if entity_instance.authorized_at:
            raise ValidationError("El vale ya ha sido autorizado previamente.")
        entity_instance.authorized_by = user
        entity_instance.authorized_at = timezone.now()
        if comments:
            entity_instance.comments = (entity_instance.comments + "\n" + comments).strip()
        entity_instance.save()

    elif transition_code == "cancel_voucher":
        entity_instance.status = Voucher.Status.CANCELADO
        entity_instance.cancelled_by = user
        entity_instance.cancelled_at = timezone.now()
        entity_instance.cancel_reason_id = data.get("cancel_reason_id")
        entity_instance.comments = (entity_instance.comments + "\n" + comments).strip()
        entity_instance.lines.all().update(status=VoucherLine.LineStatus.CANCELADO)
        entity_instance.save()

    elif transition_code == "cancel_line":
        entity_instance.status = VoucherLine.LineStatus.CANCELADO
        entity_instance.cancel_reason_id = data.get("cancel_reason_id")
        entity_instance.comments = comments
        entity_instance.save()
        # Si todas las líneas quedaron canceladas, cancelar el vale
        parent_voucher = entity_instance.voucher
        if not parent_voucher.lines.exclude(status=VoucherLine.LineStatus.CANCELADO).exists():
            parent_voucher.status = Voucher.Status.CANCELADO
            parent_voucher.cancelled_by = user
            parent_voucher.cancelled_at = timezone.now()
            parent_voucher.save()

    elif transition_code == "cancel_dispatched_item":
        # Valida límite de 120 horas
        if entity_instance.dispatched_at:
            elapsed = timezone.now() - entity_instance.dispatched_at
            if elapsed > timedelta(hours=120):
                raise ValidationError("No es posible cancelar: han transcurrido más de 120 horas desde el surtido.")

        if entity_instance.cases.exists():
            raise ValidationError("No se puede cancelar una pieza que ya cuenta con un caso de devolución.")

        entity_instance.cancelled_at = timezone.now()
        entity_instance.cancelled_by = user
        entity_instance.cancel_note = data.get("cancel_note", "")
        entity_instance.save()

        # Genera movimiento de ENTRADA
        InventoryMovement.objects.create(
            movement_type=InventoryMovement.MovementType.ENTRADA,
            equipment_model=entity_instance.equipment_model,
            serial_number=entity_instance.serial_number,
            condition=entity_instance.condition,
            warehouse=entity_instance.warehouse,
            region=entity_instance.region,
            quantity=1,
            moved_at=timezone.now(),
            transfer_folio=f"CANCEL-ITEM-{entity_instance.id}",
            item=entity_instance,
            confirmed=True,
            created_by=user,
        )

    elif transition_code in ("register_return", "register_return_without_dispatch"):
        # Creation of new EquipmentCase
        returned_model_id = data.get("returned_model_id")
        returned_serial = data.get("returned_serial", "").strip()
        route = data.get("route", EquipmentCase.Route.EVALUACION_CENTRO)
        origin_region_id = data.get("origin_region_id") or user.region_id

        entity_instance = EquipmentCase.objects.create(
            item_id=data.get("item_id"),
            origin_region_id=origin_region_id,
            returned_model_id=returned_model_id,
            returned_serial=returned_serial,
            returned_brand=data.get("returned_brand", ""),
            route=route,
            shipping_type=data.get("shipping_type", EquipmentCase.ShippingType.FISICO),
            shipping_folio=data.get("shipping_folio", ""),
            failure=data.get("failure", ""),
            applies_workshop_entry=data.get("applies_workshop_entry", False),
            applies_reason_id=data.get("applies_reason_id"),
            stock_direct_reason_id=data.get("stock_direct_reason_id"),
            insight_entry_confirmed=data.get("insight_confirmed", False),
            stage=target_stage,
        )

    elif transition_code == "confirm_return":
        entity_instance.stage = target_stage
        entity_instance.ruling_id = data.get("ruling_id")
        entity_instance.received_by = user
        entity_instance.return_status = "CONFIRMADO"
        if data.get("returned_model_id"):
            entity_instance.returned_model_id = data.get("returned_model_id")
        entity_instance.save()

    elif transition_code == "confirm_na_return":
        entity_instance.stage = target_stage
        entity_instance.return_status = "SIN_DEVOLUCION"
        entity_instance.save()

    elif transition_code == "request_return_review":
        entity_instance.stage = target_stage
        entity_instance.return_status = "EN_REVISION"
        entity_instance.review_reason = data.get("review_reason", comments)
        entity_instance.save()

    elif transition_code == "assign_repair_folio":
        entity_instance.stage = target_stage
        entity_instance.repair_folio = data.get("repair_folio", "")
        if data.get("folio_date"):
            entity_instance.folio_date = data.get("folio_date")
        if data.get("insight_note_id"):
            entity_instance.insight_entry_note_id = data.get("insight_note_id")
        entity_instance.save()

    elif transition_code == "assign_engineer":
        entity_instance.stage = target_stage
        entity_instance.assigned_engineer_id = data.get("assigned_engineer_id")
        entity_instance.assigned_at = timezone.now()
        entity_instance.save()

    elif transition_code == "define_equipment":
        entity_instance.stage = target_stage
        entity_instance.definition = data.get("definition")
        entity_instance.repair_comments = data.get("repair_comments", "")
        entity_instance.repaired_at = timezone.now()
        if data.get("warranty_solution"):
            entity_instance.warranty_solution = data.get("warranty_solution")
        if data.get("new_serial"):
            entity_instance.new_serial = data.get("new_serial")
        entity_instance.save()

    elif transition_code == "boss_confirm_definition":
        entity_instance.stage = target_stage
        entity_instance.save()

    elif transition_code == "boss_reject_definition":
        entity_instance.stage = target_stage
        entity_instance.save()

    elif transition_code == "warehouse_confirm_definition":
        entity_instance.stage = target_stage
        entity_instance.destination_warehouse = data.get("destination_warehouse", "STOCK")
        entity_instance.save()

        # Entrada al Kárdex
        condition = (
            InventoryItem.Condition.NUEVO
            if entity_instance.warranty_solution == EquipmentCase.WarrantySolution.NUEVO
            else InventoryItem.Condition.RECUPERADO
        )
        serial = entity_instance.new_serial if entity_instance.new_serial else entity_instance.returned_serial

        InventoryMovement.objects.create(
            movement_type=InventoryMovement.MovementType.ENTRADA,
            equipment_model=entity_instance.returned_model,
            serial_number=serial,
            condition=condition,
            warehouse=entity_instance.destination_warehouse,
            region=entity_instance.origin_region,
            quantity=1,
            moved_at=timezone.now(),
            transfer_folio=f"CASO-ENTRADA-{entity_instance.id}",
            case=entity_instance,
            confirmed=True,
            created_by=user,
        )

    elif transition_code == "warehouse_reject_definition":
        entity_instance.stage = target_stage
        entity_instance.save()

    # --- Flujo C: Huesario, Scrap, Garantías y Cancelaciones ---
    elif transition_code == "confirm_scrap_boss":
        entity_instance.stage = target_stage
        entity_instance.scrap_status = EquipmentCase.ScrapStatus.CONFIRMADO
        entity_instance.save()

    elif transition_code == "deliver_scrap":
        entity_instance.stage = target_stage
        entity_instance.scrap_status = EquipmentCase.ScrapStatus.ENVIADO
        entity_instance.save()

    elif transition_code == "return_scrap_to_repair":
        entity_instance.stage = target_stage
        entity_instance.scrap_status = None
        entity_instance.definition = None
        entity_instance.save()

    elif transition_code == "set_warranty_solution":
        entity_instance.stage = target_stage
        entity_instance.warranty_solution = data.get("warranty_solution")
        if data.get("new_serial"):
            entity_instance.new_serial = data.get("new_serial")
        entity_instance.save()

    elif transition_code == "send_to_cellular_workshop":
        entity_instance.stage = target_stage
        entity_instance.definition = EquipmentCase.Definition.GARANTIA
        entity_instance.save()

    elif transition_code == "cancel_return":
        entity_instance.stage = target_stage
        entity_instance.review_reason = data.get("cancel_reason", "")
        entity_instance.save()

    elif transition_code == "manager_confirm_cancellation":
        entity_instance.stage = target_stage
        entity_instance.save()

    elif transition_code == "manager_reject_cancellation":
        entity_instance.stage = target_stage
        entity_instance.save()

    elif transition_code == "warehouse_receive_cancelled":
        entity_instance.stage = target_stage
        entity_instance.save()

        # Entrada al Kárdex por devolución cancelada
        InventoryMovement.objects.create(
            movement_type=InventoryMovement.MovementType.ENTRADA,
            equipment_model=entity_instance.returned_model,
            serial_number=entity_instance.returned_serial,
            condition=InventoryItem.Condition.RECUPERADO,
            warehouse=InventoryItem.Warehouse.STOCK,
            region=entity_instance.origin_region,
            quantity=1,
            moved_at=timezone.now(),
            transfer_folio=f"CANCEL-ENTRADA-{entity_instance.id}",
            case=entity_instance,
            confirmed=True,
            created_by=user,
        )

    elif transition_code == "confirm_unused_equipment":
        entity_instance.stage = target_stage
        entity_instance.save()

    elif transition_code == "reject_unused_equipment":
        entity_instance.stage = target_stage
        entity_instance.save()

    # --- Flujo D: Taller Habilitado (location: TALLER) ---
    elif transition_code == "send_to_workshop":
        entity_instance.stage = target_stage
        entity_instance.location = EquipmentCase.Location.TALLER
        entity_instance.workshop_region_id = data.get("workshop_region_id")
        if data.get("shipping_folio"):
            entity_instance.shipping_folio = data.get("shipping_folio")
        entity_instance.save()

    elif transition_code == "cancel_workshop_send":
        entity_instance.stage = target_stage
        entity_instance.location = EquipmentCase.Location.CENTRO
        entity_instance.workshop_region = None
        entity_instance.save()

    elif transition_code == "workshop_confirm_entry":
        entity_instance.stage = target_stage
        if data.get("returned_model_id"):
            entity_instance.returned_model_id = data.get("returned_model_id")
        entity_instance.save()

    elif transition_code == "workshop_request_review":
        entity_instance.stage = target_stage
        entity_instance.review_reason = data.get("review_reason", "")
        entity_instance.save()

    elif transition_code == "workshop_assign_engineer":
        entity_instance.stage = target_stage
        entity_instance.assigned_engineer_id = data.get("assigned_engineer_id")
        entity_instance.assigned_at = timezone.now()
        entity_instance.save()

    elif transition_code == "workshop_wait_parts":
        entity_instance.stage = target_stage
        entity_instance.save()

    elif transition_code == "workshop_define_equipment":
        entity_instance.stage = target_stage
        entity_instance.definition = data.get("definition")
        entity_instance.repair_comments = data.get("repair_comments", "")
        entity_instance.repaired_at = timezone.now()
        if data.get("warranty_solution"):
            entity_instance.warranty_solution = data.get("warranty_solution")
        if data.get("new_serial"):
            entity_instance.new_serial = data.get("new_serial")
        entity_instance.save()

    elif transition_code == "workshop_confirm_definition":
        entity_instance.stage = target_stage
        entity_instance.save()

    elif transition_code == "workshop_request_rereview":
        entity_instance.stage = target_stage
        entity_instance.save()

    elif transition_code == "workshop_warehouse_entry":
        entity_instance.stage = target_stage
        entity_instance.destination_warehouse = data.get("destination_warehouse", "STOCK")
        entity_instance.save()

        # Entrada al Kárdex
        condition = (
            InventoryItem.Condition.NUEVO
            if entity_instance.warranty_solution == EquipmentCase.WarrantySolution.NUEVO
            else InventoryItem.Condition.RECUPERADO
        )
        serial = entity_instance.new_serial if entity_instance.new_serial else entity_instance.returned_serial
        target_region = entity_instance.workshop_region or entity_instance.origin_region

        InventoryMovement.objects.create(
            movement_type=InventoryMovement.MovementType.ENTRADA,
            equipment_model=entity_instance.returned_model,
            serial_number=serial,
            condition=condition,
            warehouse=entity_instance.destination_warehouse,
            region=target_region,
            quantity=1,
            moved_at=timezone.now(),
            transfer_folio=f"TALLER-ENTRADA-{entity_instance.id}",
            case=entity_instance,
            confirmed=True,
            created_by=user,
        )

    # 5. Generar evento de auditoría en CoreEvent
    entity_type = entity_instance.__class__.__name__
    event = CoreEvent.objects.create(
        entity_type=entity_type,
        entity_id=entity_instance.id,
        action_code=transition_code,
        from_stage=current_stage,
        to_stage=target_stage,
        outcome=CoreEvent.Outcome.CONFIRMED,
        user=user,
        comment=comments,
        reason_code=reason_code,
        payload=data,
    )
    return event
