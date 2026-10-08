"""Organizational hierarchy models: Zone, Region, Center."""
from django.db import models

from apps.core.models import TimeStampedModel


class Zone(TimeStampedModel):
    """Zona geográfica (ej. Zona 1, Zona 2, etc.)."""
    name = models.CharField(max_length=64, unique=True, verbose_name="Nombre de la zona")

    class Meta:
        db_table = "org_zone"
        verbose_name = "Zona"
        verbose_name_plural = "Zonas"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Region(TimeStampedModel):
    """Región operativa (ej. OAXC, CRDB, MXLI, etc.)."""
    code = models.CharField(max_length=16, unique=True, verbose_name="Código de región")
    name = models.CharField(max_length=128, verbose_name="Nombre de la región")
    zone = models.ForeignKey(
        Zone,
        on_delete=models.PROTECT,
        related_name="regions",
        verbose_name="Zona",
    )
    is_workshop = models.BooleanField(
        default=False,
        verbose_name="¿Es taller habilitado?",
        help_text="Indica si esta región opera como taller de reparación.",
    )
    workshop_name = models.CharField(
        max_length=128,
        blank=True,
        default="",
        verbose_name="Nombre del taller",
    )

    class Meta:
        db_table = "org_region"
        verbose_name = "Región"
        verbose_name_plural = "Regiones"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Center(TimeStampedModel):
    """
    Centro de trabajo / Tienda / Almacén SSIT.
    Unifica CENTROS y SSIT de la base de datos de AppSheet.
    """
    number = models.IntegerField(unique=True, verbose_name="Número de centro")
    name = models.CharField(max_length=128, verbose_name="Nombre del centro")
    label = models.CharField(max_length=160, blank=True, default="", verbose_name="Etiqueta visible")
    region = models.ForeignKey(
        Region,
        on_delete=models.PROTECT,
        related_name="centers",
        verbose_name="Región",
    )
    address = models.TextField(blank=True, default="", verbose_name="Dirección")
    is_active = models.BooleanField(default=True, verbose_name="¿Activo?")

    class Meta:
        db_table = "org_center"
        verbose_name = "Centro"
        verbose_name_plural = "Centros"
        ordering = ["number"]

    def __str__(self):
        return self.label or f"{self.number} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.label:
            self.label = f"{self.number} - {self.name}"
        super().save(*args, **kwargs)
