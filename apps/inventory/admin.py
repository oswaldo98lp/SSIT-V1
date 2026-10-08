from django.contrib import admin

from .models import EquipmentModel, InventoryItem, InventoryMovement


@admin.register(EquipmentModel)
class EquipmentModelAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "model", "category", "is_inventoriable")
    list_filter = ("category", "is_inventoriable")
    search_fields = ("name", "brand", "model")


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("serial_number", "equipment_model", "condition", "warehouse", "region", "dispatched_at")
    list_filter = ("condition", "warehouse", "region")
    search_fields = ("serial_number", "equipment_model__name")


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ("moved_at", "movement_type", "equipment_model", "serial_number", "quantity", "warehouse", "region", "confirmed")
    list_filter = ("movement_type", "warehouse", "condition", "region", "confirmed")
    search_fields = ("serial_number", "equipment_model__name", "transfer_folio")
