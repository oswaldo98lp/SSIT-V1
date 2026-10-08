"""Documents model for PDFs, signatures, QR codes and evidence photos."""
from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Document(TimeStampedModel):
    """Repositorio documental para evidencias, PDFs generados y firmas."""
    class Kind(models.TextChoices):
        VALE_PDF = "VALE_PDF", "PDF de Vale de Salida"
        REGRESO_PDF = "REGRESO_PDF", "PDF de Regreso / Caso"
        FIRMA = "FIRMA", "Firma Digitalizada"
        FOTO_TALLER = "FOTO_TALLER", "Foto / Evidencia de Taller"
        QR = "QR", "Código QR"

    kind = models.CharField(
        max_length=32,
        choices=Kind.choices,
        verbose_name="Tipo de documento",
    )
    related_type = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name="Tipo de entidad relacionada",
    )
    related_id = models.BigIntegerField(
        db_index=True,
        verbose_name="ID de entidad relacionada",
    )
    file = models.FileField(
        upload_to="documents/%Y/%m/",
        verbose_name="Archivo",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="uploaded_documents",
        verbose_name="Subido por",
    )

    class Meta:
        db_table = "documents_document"
        verbose_name = "Documento"
        verbose_name_plural = "Documentos"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["related_type", "related_id"]),
            models.Index(fields=["kind", "created_at"]),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} ({self.related_type} #{self.related_id})"
