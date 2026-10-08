"""Core views for Dashboard and UI Component catalog."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import TemplateView


class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Pantalla 1: Inicio con panel por rol, tarjetas con contadores de pendientes,
    y enlace configurable a Traspasos.
    """
    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Métrica de alcance del usuario
        allowed_regions = user.allowed_regions() if hasattr(user, "allowed_regions") else []

        context.update({
            "user_roles": user.groups.values_list("name", flat=True) if user.is_authenticated else [],
            "allowed_regions_count": len(allowed_regions),
            "pending_vouchers_count": 0,
            "pending_returns_count": 0,
            "pending_workshop_count": 0,
            "pending_scrap_count": 0,
        })
        return context


class ComponentsPreviewView(TemplateView):
    """Developer preview showcase for UI components, badges, and responsive tables."""
    template_name = "core/components_preview.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.core.templatetags.core_tags import BADGE_STYLES
        context["badge_keys"] = list(BADGE_STYLES.keys())
        return context


def htmx_modal_demo(request):
    """Example endpoint returning an HTMX-driven modal dialog."""
    return render(request, "components/modal_demo_content.html", {})
