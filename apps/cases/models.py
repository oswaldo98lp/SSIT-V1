"""EquipmentCase model representing the full return, repair, workshop and scrap lifecycle."""
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class EquipmentCase(TimeStampedModel):
    """
    Caso de equipo: devolución, dictamen, reparación en centro o taller,
    garantía, huesario y reingreso a almacén.
    """
    class Location(models.TextChoices):
        CENTRO = "CENTRO", "Centro / En Campo"
        TALLER = "TALLER", "Taller Habilitado"

    class Route(models.TextChoices):
        EVALUACION_CENTRO = "EVALUACION_CENTRO", "Evaluación en Centro"
        TALLER_HABILITADO = "TALLER_HABILITADO", "Taller Habilitado"
        STOCK_DIRECTO = "STOCK_DIRECTO", "Stock Directo"

    class ShippingType(models.TextChoices):
        FISICO = "FISICO", "Físico"
        DISTRIBUCION = "DISTRIBUCION", "Distribución"

    class Definition(models.TextChoices):
        REPARADO = "REPARADO", "Reparado"
        HUESARIO = "HUESARIO", "Huesario / Scrap"
        GARANTIA = "GARANTIA", "Garantía"

    class WarrantySolution(models.TextChoices):
        NUEVO = "NUEVO", "Nuevo"
        RECUPERADO = "RECUPERADO", "Recuperado"

    class ScrapStatus(models.TextChoices):
        CONFIRMADO = "CONFIRMADO", "Confirmado para Huesario"
        ENVIADO = "ENVIADO", "Enviado a Huesario"

    # Relación con pieza original surtida (opcional si es devolución sin salida previa)
    item = models.ForeignKey(
        "inventory.InventoryItem",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cases",
        verbose_name="Pieza surtida original",
    )
    location = models.CharField(
        max_length=20,
        choices=Location.choices,
        default=Location.CENTRO,
        verbose_name="Ubicación operativa",
    )
    workshop_region = models.ForeignKey(
        "org.Region",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="workshop_cases",
        verbose_name="Región de taller asignado",
    )
    origin_region = models.ForeignKey(
        "org.Region",
        on_delete=models.PROTECT,
        related_name="origin_cases",
        verbose_name="Región de origen",
    )
    route = models.CharField(
        max_length=32,
        choices=Route.choices,
        default=Route.EVALUACION_CENTRO,
        verbose_name="Ruta de atención",
    )
    applies_workshop_entry = models.BooleanField(
        default=False,
        verbose_name="¿Aplica entrada a taller?",
    )
    applies_reason = models.ForeignKey(
        "catalog.CatalogValue",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="case_applies_reasons",
        limit_choices_to={"catalog": "APPLIES_REASON"},
        verbose_name="Motivo por el que aplica a taller",
    )
    returned_model = models.ForeignKey(
        "inventory.EquipmentModel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="case_returns",
        verbose_name="Modelo identificado",
    )
    returned_brand = models.CharField(max_length=128, blank=True, default="", verbose_name="Marca")
    returned_model_text = models.CharField(max_length=128, blank=True, default="", verbose_name="Modelo devuelto (texto)")
    returned_serial = models.CharField(max_length=128, db_index=True, verbose_name="Número de serie devuelto")
    shipping_type = models.CharField(
        max_length=32,
        choices=ShippingType.choices,
        default=ShippingType.FISICO,
        verbose_name="Tipo de envío",
    )
    shipping_folio = models.CharField(max_length=64, blank=True, default="", verbose_name="Folio de envío (EM o SA)")
    stock_direct_reason = models.ForeignKey(
        "catalog.CatalogValue",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="case_stock_direct_reasons",
        limit_choices_to={"catalog": "STOCK_DIRECT_REASON"},
        verbose_name="Motivo de stock directo",
    )
    return_status = models.CharField(max_length=64, blank=True, default="PENDIENTE_CONFIRMAR", verbose_name="Estatus de devolución")
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="received_cases",
        verbose_name="Recibido en almacén por",
    )
    ruling = models.ForeignKey(
        "catalog.CatalogValue",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="case_rulings",
        limit_choices_to={"catalog": "RULING"},
        verbose_name="Dictamen de almacén",
    )
    predefinition = models.ForeignKey(
        "catalog.CatalogValue",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="case_predefinitions",
        limit_choices_to={"catalog": "PREDEFINITION"},
        verbose_name="Predefinición de falla",
    )
    failure = models.TextField(blank=True, default="", verbose_name="Descripción de la falla")
    return_pdf = models.FileField(upload_to="docs/returns/%Y/%m/", null=True, blank=True, verbose_name="PDF de regreso")
    return_qr = models.ImageField(upload_to="qr/returns/%Y/%m/", null=True, blank=True, verbose_name="QR de regreso")
    repair_folio = models.CharField(max_length=64, blank=True, default="", verbose_name="Folio de reparación")
    folio_date = models.DateField(null=True, blank=True, verbose_name="Fecha de folio")
    attention_folio = models.CharField(max_length=64, blank=True, default="", verbose_name="Folio de atención")
    assigned_engineer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_cases",
        verbose_name="Ingeniero asignado",
    )
    assigned_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de asignación")
    definition = models.CharField(
        max_length=32,
        choices=Definition.choices,
        null=True,
        blank=True,
        verbose_name="Definición técnica",
    )
    repair_comments = models.TextField(blank=True, default="", verbose_name="Comentarios de reparación")
    repaired_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de reparación/definición")

    # Insight flags
    insight_repair_confirmed = models.BooleanField(default=False, verbose_name="Insight reparación confirmado")
    insight_repair_note = models.ForeignKey(
        "catalog.CatalogValue",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="repair_insight_notes",
        verbose_name="Nota Insight reparación",
    )
    insight_entry_confirmed = models.BooleanField(default=False, verbose_name="Insight entrada confirmado")
    insight_entry_note = models.ForeignKey(
        "catalog.CatalogValue",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="entry_insight_notes",
        verbose_name="Nota Insight entrada",
    )

    destination_warehouse = models.CharField(max_length=32, blank=True, default="STOCK", verbose_name="Almacén destino")
    warranty_solution = models.CharField(
        max_length=32,
        choices=WarrantySolution.choices,
        null=True,
        blank=True,
        verbose_name="Solución de garantía",
    )
    new_serial = models.CharField(max_length=128, blank=True, default="", verbose_name="Nueva serie (garantía nuevo)")
    review_reason = models.TextField(blank=True, default="", verbose_name="Motivo de revisión")
    scrap_status = models.CharField(
        max_length=32,
        choices=ScrapStatus.choices,
        null=True,
        blank=True,
        verbose_name="Estatus de huesario",
    )
    stage = models.CharField(
        max_length=64,
        default="PENDIENTE_CONFIRMAR",
        db_index=True,
        verbose_name="Etapa actual del caso",
    )

    class Meta:
        db_table = "cases_equipment_case"
        verbose_name = "Caso de equipo"
        verbose_name_plural = "Casos de equipo"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["origin_region", "stage"]),
            models.Index(fields=["returned_serial"]),
            models.Index(fields=["location", "stage"]),
        ]

    def __str__(self):
        return f"Caso #{self.id} (S/N: {self.returned_serial}) [{self.stage}]"
