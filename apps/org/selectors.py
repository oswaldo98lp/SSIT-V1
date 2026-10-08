"""Scoped query selectors for Org models (Zone, Region, Center)."""
from django.db.models import QuerySet

from .models import Center, Region, Zone


def get_user_allowed_regions(user) -> QuerySet[Region]:
    """Returns the queryset of regions accessible to the user based on their scope."""
    if not user or not user.is_authenticated:
        return Region.objects.none()
    return user.allowed_regions()


get_regions_for_user = get_user_allowed_regions



def get_user_allowed_centers(user) -> QuerySet[Center]:
    """Returns centers belonging to the user's allowed regions."""
    if not user or not user.is_authenticated:
        return Center.objects.none()

    if user.is_superuser or getattr(user, "has_global_scope", False):
        return Center.objects.filter(is_active=True)

    allowed_regions = get_user_allowed_regions(user)
    return Center.objects.filter(region__in=allowed_regions, is_active=True)


def get_user_allowed_zones(user) -> QuerySet[Zone]:
    """Returns zones covered by the user's allowed regions."""
    if not user or not user.is_authenticated:
        return Zone.objects.none()

    if user.is_superuser or getattr(user, "has_global_scope", False):
        return Zone.objects.all()

    allowed_regions = get_user_allowed_regions(user)
    return Zone.objects.filter(regions__in=allowed_regions).distinct()
