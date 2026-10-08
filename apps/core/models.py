"""Core models and audit event tracking."""
from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base model with timestamps and optional legacy_id."""
    legacy_id = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        verbose_name="ID de AppSheet original",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última modificación")

    class Meta:
        abstract = True


from django.core.serializers.json import DjangoJSONEncoder


class CoreEvent(models.Model):
    """
    Central audit log for all entity transitions, approvals and rejections.
    Replaces repeated confirmation columns from AppSheet.
    """
    class Outcome(models.TextChoices):
        CONFIRMED = "CONFIRMADO", "Confirmado"
        REJECTED = "RECHAZADO", "Rechazado"
        NA = "NA", "No Aplica"

    entity_type = models.CharField(max_length=64, db_index=True, verbose_name="Tipo de entidad")
    entity_id = models.BigIntegerField(db_index=True, verbose_name="ID de entidad")
    action_code = models.CharField(max_length=64, db_index=True, verbose_name="Código de acción")
    from_stage = models.CharField(max_length=64, blank=True, default="", verbose_name="Etapa anterior")
    to_stage = models.CharField(max_length=64, blank=True, default="", verbose_name="Etapa nueva")
    outcome = models.CharField(
        max_length=20,
        choices=Outcome.choices,
        default=Outcome.NA,
        verbose_name="Resultado",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="core_events",
        verbose_name="Usuario ejecutor",
    )
    comment = models.TextField(blank=True, default="", verbose_name="Comentarios")
    reason_code = models.CharField(max_length=64, blank=True, default="", verbose_name="Código de motivo")
    payload = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder, verbose_name="Datos complementarios")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Fecha y hora")

    class Meta:
        db_table = "core_event"
        verbose_name = "Evento de auditoría"
        verbose_name_plural = "Eventos de auditoría"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["action_code", "created_at"]),
        ]

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.entity_type}#{self.entity_id} -> {self.action_code} ({self.outcome})"
