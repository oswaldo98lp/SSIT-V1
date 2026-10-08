"""Inventory models: EquipmentModel, InventoryItem and InventoryMovement (Kárdex)."""
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class EquipmentModel(TimeStampedModel):
    """Modelo / catálogo de equipos y refacciones."""
    name = models.CharField(max_length=255, verbose_name="Nombre del artículo")
    brand = models.CharField(max_length=128, blank=True, default="", verbose_name="Marca")
    model = models.CharField(max_length=128, blank=True, default="", verbose_name="Modelo")
    category = models.ForeignKey(
        "catalog.CatalogValue",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="equipment_models",
        limit_choices_to={"catalog": "MATERIAL_CATEGORY"},
        verbose_name="Categoría de material",
    )
    is_inventoriable = models.BooleanField(
        default=True,
        verbose_name="¿Es inventariable?",
        help_text="Indica si requiere control de número de serie individual.",
    )

    class Meta:
        db_table = "inventory_equipment_model"
        verbose_name = "Modelo de equipo"
        verbose_name_plural = "Modelos de equipo"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.brand} {self.model})".strip()


class InventoryItem(TimeStampedModel):
    """
    Pieza física individual surtida, con número de serie y asignación.
    """
    class Condition(models.TextChoices):
        NUEVO = "NUEVO", "Nuevo"
        RECUPERADO = "RECUPERADO", "Recuperado"

    class Warehouse(models.TextChoices):
        STOCK = "STOCK", "Stock"
        PROYECTOS = "PROYECTOS", "Proyectos"

    class InsightTag(models.TextChoices):
        SI = "SI", "Sí"
        NO = "NO", "No"

    voucher = models.ForeignKey(
        "vouchers.Voucher",
        on_delete=models.PROTECT,
        related_name="items",
        verbose_name="Vale de origen",
    )
    line = models.ForeignKey(
        "vouchers.VoucherLine",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="items",
        verbose_name="Línea de vale",
    )
    equipment_model = models.ForeignKey(
        EquipmentModel,
        on_delete=models.PROTECT,
        related_name="items",
        verbose_name="Modelo de equipo",
    )
    serial_number = models.CharField(
        max_length=128,
        db_index=True,
        verbose_name="Número de serie",
    )
    condition = models.CharField(
        max_length=20,
        choices=Condition.choices,
        default=Condition.RECUPERADO,
        verbose_name="Condición",
    )
    warehouse = models.CharField(
        max_length=20,
        choices=Warehouse.choices,
        default=Warehouse.STOCK,
        verbose_name="Almacén",
    )
    quantity = models.IntegerField(default=1, verbose_name="Cantidad")
    region = models.ForeignKey(
        "org.Region",
        on_delete=models.PROTECT,
        related_name="inventory_items",
        verbose_name="Región",
    )
    confirm_responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="confirmed_items",
        verbose_name="Responsable de confirmación",
    )
    insight_tag_confirmed = models.CharField(
        max_length=10,
        choices=InsightTag.choices,
        null=True,
        blank=True,
        verbose_name="Insight Tag confirmado",
    )
    insight_note = models.ForeignKey(
        "catalog.CatalogValue",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="item_insight_notes",
        verbose_name="Nota Insight",
    )
    dispatched_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de surtido")
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de cancelación")
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cancelled_items",
        verbose_name="Cancelado por",
    )
    cancel_note = models.TextField(blank=True, default="", verbose_name="Nota de cancelación")

    class Meta:
        db_table = "inventory_item"
        verbose_name = "Pieza de inventario"
        verbose_name_plural = "Piezas de inventario"
        indexes = [
            models.Index(fields=["serial_number"]),
            models.Index(fields=["region", "dispatched_at"]),
        ]

    def __str__(self):
        return f"{self.equipment_model.name} (S/N: {self.serial_number})"


class InventoryMovement(TimeStampedModel):
    """
    Movimientos de entrada y salida para el cálculo del Kárdex.
    Solo modificado a través de transiciones de negocio.
    """
    class MovementType(models.TextChoices):
        ENTRADA = "ENTRADA", "Entrada"
        SALIDA = "SALIDA", "Salida"

    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
        verbose_name="Tipo de movimiento",
    )
    equipment_model = models.ForeignKey(
        EquipmentModel,
        on_delete=models.PROTECT,
        related_name="movements",
        verbose_name="Modelo de equipo",
    )
    serial_number = models.CharField(
        max_length=128,
        blank=True,
        default="",
        db_index=True,
        verbose_name="Número de serie",
    )
    condition = models.CharField(
        max_length=20,
        choices=InventoryItem.Condition.choices,
        verbose_name="Condición",
    )
    warehouse = models.CharField(
        max_length=20,
        choices=InventoryItem.Warehouse.choices,
        verbose_name="Almacén",
    )
    region = models.ForeignKey(
        "org.Region",
        on_delete=models.PROTECT,
        related_name="movements",
        verbose_name="Región",
    )
    quantity = models.IntegerField(default=1, verbose_name="Cantidad")
    moved_at = models.DateTimeField(verbose_name="Fecha del movimiento")
    transfer_folio = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name="Folio de traspaso / referencia",
    )
    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movements",
        verbose_name="Pieza relacionada",
    )
    case = models.ForeignKey(
        "cases.EquipmentCase",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movements",
        verbose_name="Caso relacionado",
    )
    confirmed = models.BooleanField(default=True, verbose_name="¿Confirmado?")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="created_movements",
        verbose_name="Creado por",
    )

    class Meta:
        db_table = "inventory_movement"
        verbose_name = "Movimiento de kárdex"
        verbose_name_plural = "Movimientos de kárdex"
        ordering = ["-moved_at"]
        indexes = [
            models.Index(fields=["region", "moved_at"]),
            models.Index(fields=["equipment_model", "warehouse", "condition"]),
        ]

    def __str__(self):
        return f"{self.movement_type} - {self.equipment_model.name} ({self.quantity}) [{self.region.code}]"
