from django.contrib import admin

from .models import CatalogValue


@admin.register(CatalogValue)
class CatalogValueAdmin(admin.ModelAdmin):
    list_display = ("catalog", "code", "label", "sort", "is_active")
    list_filter = ("catalog", "is_active")
    search_fields = ("code", "label")
    ordering = ("catalog", "sort", "label")
