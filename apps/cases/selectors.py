"""Scoped query selectors for Equipment Cases and Workshop tracking."""
from django.db.models import Q, QuerySet

from .models import EquipmentCase


def get_cases_for_user(
    user,
    location: str | None = None,
    stage: str | None = None,
    allow_global: bool = False,
) -> QuerySet[EquipmentCase]:
    """
    Returns cases filtered by user scope (either origin_region or workshop_region).
    If allow_global is True and user has global scope (e.g. OFICINA), returns global cases.
    """
    if not user or not user.is_authenticated:
        return EquipmentCase.objects.none()

    qs = EquipmentCase.objects.select_related(
        "origin_region", "workshop_region", "returned_model", "assigned_engineer", "received_by"
    )

    if not (user.is_superuser or getattr(user, "has_global_scope", False) or (allow_global and user.groups.filter(name="OFICINA").exists())):
        allowed_regions = user.allowed_regions()
        # El usuario puede ver casos donde su región sea el origen o el taller asignado
        qs = qs.filter(Q(origin_region__in=allowed_regions) | Q(workshop_region__in=allowed_regions))

    if location:
        qs = qs.filter(location=location)

    if stage:
        qs = qs.filter(stage=stage)

    return qs


def get_workshop_cases_for_user(user) -> QuerySet[EquipmentCase]:
    """Returns workshop cases (location=TALLER) accessible within user scope."""
    return get_cases_for_user(user, location=EquipmentCase.Location.TALLER)


def get_center_cases_for_user(user) -> QuerySet[EquipmentCase]:
    """Returns field/center cases (location=CENTRO) accessible within user scope."""
    return get_cases_for_user(user, location=EquipmentCase.Location.CENTRO)
