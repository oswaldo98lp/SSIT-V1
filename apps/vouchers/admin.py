from django.contrib import admin

from .models import Voucher, VoucherLine


class VoucherLineInline(admin.TabularInline):
    model = VoucherLine
    extra = 0


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    list_display = ("id", "origin_type", "report_folio", "destination_center", "region", "status", "created_at")
    list_filter = ("origin_type", "status", "region")
    search_fields = ("id", "report_folio", "coupa_id", "project_name")
    inlines = [VoucherLineInline]
