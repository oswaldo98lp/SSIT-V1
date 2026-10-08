"""Scoped query selectors for Vouchers and Lines."""
from django.db.models import QuerySet

from .models import Voucher, VoucherLine


def get_vouchers_for_user(user, status: str | None = None) -> QuerySet[Voucher]:
    """Returns vouchers filtered by the requesting user's allowed regions."""
    if not user or not user.is_authenticated:
        return Voucher.objects.none()

    qs = Voucher.objects.select_related("destination_center", "requested_by", "region", "reason")
    if not (user.is_superuser or getattr(user, "has_global_scope", False)):
        allowed_regions = user.allowed_regions()
        qs = qs.filter(region__in=allowed_regions)

    if status:
        qs = qs.filter(status=status)
    return qs


def get_pending_vouchers_for_user(user) -> QuerySet[Voucher]:
    """Returns vouchers pending dispatch within user's allowed regions."""
    return get_vouchers_for_user(user, status=Voucher.Status.PENDIENTE_SURTIDO)


def get_voucher_lines_for_user(user, voucher_id: int) -> QuerySet[VoucherLine]:
    """Returns lines for a specific voucher, validating scope on the parent voucher."""
    vouchers = get_vouchers_for_user(user)
    if not vouchers.filter(id=voucher_id).exists():
        return VoucherLine.objects.none()
    return VoucherLine.objects.filter(voucher_id=voucher_id).select_related("equipment_model")
