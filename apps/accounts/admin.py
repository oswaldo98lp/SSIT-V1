from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "full_name", "employee_number", "region", "has_global_scope", "is_active", "is_staff")
    list_filter = ("has_global_scope", "is_active", "is_staff", "groups", "region")
    search_fields = ("email", "full_name", "employee_number")
    ordering = ("email",)
    filter_horizontal = ("groups", "user_permissions", "extra_regions")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Información Personal", {"fields": ("full_name", "employee_number", "position")}),
        ("Ubicación y Alcance", {"fields": ("center", "region", "has_global_scope", "extra_regions")}),
        ("Permisos y Roles", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas Importantes", {"fields": ("last_login", "date_joined")}),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "employee_number", "password1", "password2"),
            },
        ),
    )
