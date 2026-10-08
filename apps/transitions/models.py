"""TransitionRule model mapping declarative transitions to database rules."""
from django.db import models

from apps.core.models import TimeStampedModel


class TransitionRule(TimeStampedModel):
    """
    Regla de transición de estado ejecutable por el motor de transiciones.
    """
    class Entity(models.TextChoices):
        VOUCHER = "VOUCHER", "Vale"
        LINE = "LINE", "Línea de Vale"
        ITEM = "ITEM", "Pieza de Inventario"
        CASE = "CASE", "Caso de Equipo"

    class ScopeRule(models.TextChoices):
        REGION = "REGION", "Por Región del Usuario"
        ZONE = "ZONE", "Por Zona del Usuario"
        OWN = "OWN", "Registros Propios del Usuario"
        ASSIGNED = "ASSIGNED", "Registros Asignados al Usuario"
        GLOBAL = "GLOBAL", "Alcance Global"

    class KardexEffect(models.TextChoices):
        NONE = "NONE", "Sin Efecto en Kárdex"
        SALIDA = "SALIDA", "Movimiento de Salida"
        ENTRADA = "ENTRADA", "Movimiento de Entrada"

    code = models.CharField(max_length=64, unique=True, verbose_name="Código único de transición")
    label = models.CharField(max_length=128, verbose_name="Etiqueta / Nombre de acción")
    entity = models.CharField(max_length=20, choices=Entity.choices, verbose_name="Entidad")
    from_stages = models.JSONField(default=list, verbose_name="Etapas de origen permitidas")
    to_stage = models.CharField(max_length=64, verbose_name="Etapa destino")
    permission = models.CharField(max_length=64, verbose_name="Permiso requerido")
    scope_rule = models.CharField(
        max_length=20,
        choices=ScopeRule.choices,
        default=ScopeRule.REGION,
        verbose_name="Regla de alcance",
    )
    inputs_schema = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Esquema de campos de captura (JSON)",
    )
    conditions = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Condiciones de validación adicionales (JSON)",
    )
    kardex_effect = models.CharField(
        max_length=20,
        choices=KardexEffect.choices,
        default=KardexEffect.NONE,
        verbose_name="Efecto en Kárdex",
    )
    is_bulk = models.BooleanField(default=False, verbose_name="¿Permite ejecución en lote?")
    is_active = models.BooleanField(default=True, verbose_name="¿Activa?")

    class Meta:
        db_table = "transitions_rule"
        verbose_name = "Regla de transición"
        verbose_name_plural = "Reglas de transición"
        ordering = ["entity", "code"]

    def __str__(self):
        return f"{self.code} ({self.entity}: {self.from_stages} -> {self.to_stage})"
