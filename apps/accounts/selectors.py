"""Scoped query selectors for accounts and users."""
from django.contrib.auth import get_user_model
from django.db.models import QuerySet

User = get_user_model()


def get_users_for_scope(user, active_only: bool = True) -> QuerySet:
    """Returns users operating within the requesting user's allowed regions."""
    if not user or not user.is_authenticated:
        return User.objects.none()

    qs = User.objects.all()
    if active_only:
        qs = qs.filter(is_active=True)

    if user.is_superuser or getattr(user, "has_global_scope", False):
        return qs

    allowed_regions = user.allowed_regions()
    return qs.filter(region__in=allowed_regions)


def get_engineers_for_assignment(user) -> QuerySet:
    """Returns TI engineers available for case/repair assignment within user scope."""
    qs = get_users_for_scope(user, active_only=True)
    return qs.filter(groups__name__in=["SOPORTE_TI", "SOPORTE_TALLER"])
