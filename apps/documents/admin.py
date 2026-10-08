from django.contrib import admin

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "related_type", "related_id", "created_by", "created_at")
    list_filter = ("kind", "related_type")
    search_fields = ("related_id",)
