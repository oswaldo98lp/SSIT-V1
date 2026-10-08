"""Global template context processor."""
from django.conf import settings


def global_context(request):
    """Provides common business settings and navigation parameters to templates."""
    return {
        "APP_NAME": "Admón Almacén SSIT 2.0",
        "TRASPASOS_URL": getattr(settings, "TRASPASOS_URL", "#"),
        "STOCK_VALIDATION": getattr(settings, "STOCK_VALIDATION", False),
    }
