"""System Catalogs Model."""
from django.db import models

from apps.core.models import TimeStampedModel


class CatalogValue(TimeStampedModel):
    """
    Catálogo unificado para listas desplegables del sistema.
    """
    class CatalogType(models.TextChoices):
        REQUEST_REASON = "REQUEST_REASON", "Motivo de Solicitud de Vale"
        MATERIAL_CATEGORY = "MATERIAL_CATEGORY", "Categoría de Material"
        VOUCHER_CANCEL_REASON = "VOUCHER_CANCEL_REASON", "Motivo de Cancelación de Vale"
        MANAGER_CANCEL_REASON = "MANAGER_CANCEL_REASON", "Motivo de Cancelación de Gerente"
        STOCK_DIRECT_REASON = "STOCK_DIRECT_REASON", "Motivo de Envío a Stock Directo"
        APPLIES_REASON = "APPLIES_REASON", "Motivo de Aplica Entrada a Taller"
        PREDEFINITION = "PREDEFINITION", "Predefinición de Falla"
        RULING = "RULING", "Dictamen de Almacén"
        INSIGHT_NOTE = "INSIGHT_NOTE", "Notas de Insight"

    catalog = models.CharField(max_length=64, db_index=True, verbose_name="Tipo de catálogo")
    code = models.CharField(max_length=64, verbose_name="Código")
    label = models.CharField(max_length=255, verbose_name="Etiqueta / Descripción")
    sort = models.IntegerField(default=0, verbose_name="Orden de visualización")
    is_active = models.BooleanField(default=True, verbose_name="¿Activo?")

    class Meta:
        db_table = "catalog_value"
        verbose_name = "Valor de catálogo"
        verbose_name_plural = "Valores de catálogo"
        ordering = ["catalog", "sort", "label"]
        constraints = [
            models.UniqueConstraint(
                fields=["catalog", "code"],
                name="unique_catalog_code",
            )
        ]

    def __str__(self):
        return f"[{self.catalog}] {self.label}"
