"""Scoped query selectors for Inventory items and Kardex movements."""
from django.db.models import Case, IntegerField, QuerySet, Sum, Value, When

from .models import InventoryItem, InventoryMovement


def get_items_for_user(user, serial_number: str | None = None) -> QuerySet[InventoryItem]:
    """Returns inventory items belonging to the user's allowed regions."""
    if not user or not user.is_authenticated:
        return InventoryItem.objects.none()

    qs = InventoryItem.objects.select_related("equipment_model", "region", "voucher")
    if not (user.is_superuser or getattr(user, "has_global_scope", False)):
        allowed_regions = user.allowed_regions()
        qs = qs.filter(region__in=allowed_regions)

    if serial_number:
        qs = qs.filter(serial_number__iexact=serial_number.strip())

    return qs


def get_movements_for_user(user) -> QuerySet[InventoryMovement]:
    """Returns Kardex movements within user scope."""
    if not user or not user.is_authenticated:
        return InventoryMovement.objects.none()

    qs = InventoryMovement.objects.select_related("equipment_model", "region", "created_by")
    if not (user.is_superuser or getattr(user, "has_global_scope", False)):
        allowed_regions = user.allowed_regions()
        qs = qs.filter(region__in=allowed_regions)

    return qs.order_by("-moved_at")


def calculate_stock_balance(equipment_model_id: int, region_id: int, warehouse: str = "STOCK", condition: str = "RECUPERADO") -> int:
    """Calculates real-time on-hand balance from confirmed Kardex movements."""
    aggregates = InventoryMovement.objects.filter(
        equipment_model_id=equipment_model_id,
        region_id=region_id,
        warehouse=warehouse,
        condition=condition,
        confirmed=True,
    ).aggregate(
        total=Sum(
            Case(
                When(movement_type=InventoryMovement.MovementType.ENTRADA, then="quantity"),
                When(movement_type=InventoryMovement.MovementType.SALIDA, then=-1 * models_f("quantity")),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
    )
    return aggregates["total"] or 0


def models_f(name: str):
    from django.db.models import F
    return F(name)
