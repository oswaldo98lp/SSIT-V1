from django.contrib import admin

from .models import EquipmentCase


@admin.register(EquipmentCase)
class EquipmentCaseAdmin(admin.ModelAdmin):
    list_display = ("id", "returned_serial", "returned_model", "origin_region", "location", "stage", "created_at")
    list_filter = ("location", "route", "stage", "origin_region")
    search_fields = ("id", "returned_serial", "repair_folio", "shipping_folio")
