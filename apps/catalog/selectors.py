"""Query selectors for System Catalogs."""
from django.db.models import QuerySet

from .models import CatalogValue


def get_catalog_values(catalog_name: str, active_only: bool = True) -> QuerySet[CatalogValue]:
    """Returns sorted catalog values for a given catalog type."""
    qs = CatalogValue.objects.filter(catalog=catalog_name)
    if active_only:
        qs = qs.filter(is_active=True)
    return qs.order_by("sort", "label")


def get_catalog_choices(catalog_name: str) -> list[tuple[str, str]]:
    """Returns a list of (code, label) tuples suitable for form dropdowns."""
    values = get_catalog_values(catalog_name, active_only=True)
    return [(item.code, item.label) for item in values]
