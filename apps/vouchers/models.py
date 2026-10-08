"""Voucher and VoucherLine models."""
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Voucher(TimeStampedModel):
    """Vale de salida o consumo Coupa."""
    class OriginType(models.TextChoices):
        VALE = "VALE", "Vale Estándar"
        COUPA = "COUPA", "Consumo Coupa"

    class ShippingType(models.TextChoices):
        FISICO = "FISICO", "Físico / Entrega en mano"
        PAQUETERIA_EXTERNA = "PAQUETERIA_EXTERNA", "Paquetería Externa"
        DISTRIBUCION = "DISTRIBUCION", "Distribución Interna"

    class Status(models.TextChoices):
        PENDIENTE_SURTIDO = "PENDIENTE_SURTIDO", "Pendiente de Surtido"
        SURTIDO = "SURTIDO", "Surtido"
        CANCELADO = "CANCELADO", "Cancelado"

    origin_type = models.CharField(
        max_length=20,
        choices=OriginType.choices,
        default=OriginType.VALE,
        verbose_name="Tipo de origen",
    )
    coupa_id = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        verbose_name="ID de Coupa",
    )
    report_folio = models.CharField(
        max_length=64,
        db_index=True,
        blank=True,
        default="",
        verbose_name="Folio de reporte / ticket",
    )
    destination_center = models.ForeignKey(
        "org.Center",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="vouchers",
        verbose_name="Centro destino",
    )
    reason = models.ForeignKey(
        "catalog.CatalogValue",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="vouchers_by_reason",
        limit_choices_to={"catalog": "REQUEST_REASON"},
        verbose_name="Motivo de solicitud",
    )
    material_category = models.ForeignKey(
        "catalog.CatalogValue",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="vouchers_by_category",
        limit_choices_to={"catalog": "MATERIAL_CATEGORY"},
        verbose_name="Categoría de material",
    )
    shipping_type = models.CharField(
        max_length=32,
        choices=ShippingType.choices,
        default=ShippingType.FISICO,
        verbose_name="Tipo de envío",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_vouchers",
        verbose_name="Solicitado por",
    )
    region = models.ForeignKey(
        "org.Region",
        on_delete=models.PROTECT,
        related_name="vouchers",
        verbose_name="Región",
    )
    project_name = models.CharField(
        max_length=128,
        blank=True,
        default="",
        verbose_name="Nombre de proyecto",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDIENTE_SURTIDO,
        db_index=True,
        verbose_name="Estatus",
    )
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="authorized_vouchers",
        verbose_name="Autorizado por",
    )
    authorized_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de autorización")
    delivered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="delivered_vouchers",
        verbose_name="Entregado por (Almacén)",
    )
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de entrega / surtido")
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="received_vouchers",
        verbose_name="Recibido por",
    )
    signature_image = models.ImageField(
        upload_to="signatures/vouchers/%Y/%m/",
        null=True,
        blank=True,
        verbose_name="Firma de recepción",
    )
    pdf_file = models.FileField(
        upload_to="docs/vouchers/%Y/%m/",
        null=True,
        blank=True,
        verbose_name="PDF de vale de salida",
    )
    comments = models.TextField(blank=True, default="", verbose_name="Comentarios")
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cancelled_vouchers",
        verbose_name="Cancelado por",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de cancelación")
    cancel_reason = models.ForeignKey(
        "catalog.CatalogValue",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cancelled_vouchers_by_reason",
        limit_choices_to={"catalog": "VOUCHER_CANCEL_REASON"},
        verbose_name="Motivo de cancelación",
    )

    class Meta:
        db_table = "vouchers_voucher"
        verbose_name = "Vale"
        verbose_name_plural = "Vales"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["region", "status"]),
            models.Index(fields=["report_folio"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (models.Q(origin_type="VALE") & models.Q(coupa_id__isnull=True)) |
                    (models.Q(origin_type="COUPA") & models.Q(coupa_id__isnull=False))
                ),
                name="check_voucher_origin_coupa_integrity",
            )
        ]

    def __str__(self):
        return f"Vale #{self.id} [{self.status}] - {self.destination_center}"


class VoucherLine(TimeStampedModel):
    """Línea de artículo solicitada dentro de un vale."""
    class LineStatus(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        SURTIDO = "SURTIDO", "Surtido"
        CANCELADO = "CANCELADO", "Cancelado"

    voucher = models.ForeignKey(
        Voucher,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Vale",
    )
    equipment_model = models.ForeignKey(
        "inventory.EquipmentModel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="voucher_lines",
        verbose_name="Modelo de equipo",
    )
    requested_text = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Descripción solicitada (texto libre)",
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name="Cantidad solicitada")
    status = models.CharField(
        max_length=20,
        choices=LineStatus.choices,
        default=LineStatus.PENDIENTE,
        verbose_name="Estatus",
    )
    cancel_reason = models.ForeignKey(
        "catalog.CatalogValue",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cancelled_lines",
        verbose_name="Motivo de cancelación",
    )
    comments = models.TextField(blank=True, default="", verbose_name="Comentarios")

    class Meta:
        db_table = "vouchers_line"
        verbose_name = "Línea de vale"
        verbose_name_plural = "Líneas de vale"

    def __str__(self):
        desc = self.equipment_model.name if self.equipment_model else self.requested_text
        return f"{desc} x {self.quantity} [{self.status}]"
