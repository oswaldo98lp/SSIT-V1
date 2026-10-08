from django.contrib import admin

from .models import Center, Region, Zone


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name",)


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "zone", "is_workshop", "workshop_name")
    list_filter = ("zone", "is_workshop")
    search_fields = ("code", "name", "workshop_name")
    ordering = ("code",)


@admin.register(Center)
class CenterAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "region", "is_active")
    list_filter = ("region__zone", "region", "is_active")
    search_fields = ("number", "name", "label")
    ordering = ("number",)
