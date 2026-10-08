from django.contrib import admin

from .models import TransitionRule


@admin.register(TransitionRule)
class TransitionRuleAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "entity", "to_stage", "permission", "scope_rule", "kardex_effect", "is_bulk", "is_active")
    list_filter = ("entity", "scope_rule", "kardex_effect", "is_active")
    search_fields = ("code", "label", "to_stage", "permission")
