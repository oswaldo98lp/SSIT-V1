"""Custom template tags and filters for SSIT 2.0 UI components."""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# 21 Reglas de formato visual / Badges de color según especificación de AppSheet
BADGE_STYLES = {
    # Vales & Líneas
    "PENDIENTE_SURTIDO": ("bg-amber-soft text-amber-900 border-amber-300", "bi-clock-history", "Pendiente de Surtir"),
    "SURTIDO": ("bg-emerald-soft text-emerald-900 border-emerald-300", "bi-check2-circle", "Surtido"),
    "CANCELADO": ("bg-rose-soft text-rose-900 border-rose-300", "bi-x-circle", "Cancelado"),
    "EQUIPO_CANCELADO": ("bg-rose-soft text-rose-900 border-rose-300", "bi-dash-circle", "Equipo Cancelado"),

    # Dictámenes
    "REPARACION": ("bg-blue-soft text-blue-900 border-blue-300", "bi-tools", "Reparación"),
    "TELECOM": ("bg-indigo-soft text-indigo-900 border-indigo-300", "bi-router", "Telecom"),
    "TELECOMUNICACIONES": ("bg-indigo-soft text-indigo-900 border-indigo-300", "bi-router", "Telecomunicaciones"),
    "OBSOLETO": ("bg-stone-soft text-stone-900 border-stone-300", "bi-archive", "Obsoleto"),
    "HUESARIO_DIRECTO": ("bg-orange-soft text-orange-900 border-orange-300", "bi-recycle", "Huesario Directo"),
    "HUESARIO": ("bg-orange-soft text-orange-900 border-orange-300", "bi-recycle", "Huesario"),

    # Garantía
    "GARANTIA": ("bg-purple-soft text-purple-900 border-purple-300", "bi-shield-check", "Garantía"),
    "GARANTIA_NUEVO": ("bg-purple-soft text-purple-900 border-purple-300", "bi-box-seam", "Garantía - Nuevo"),
    "GARANTIA_RECUPERADO": ("bg-purple-soft text-purple-900 border-purple-300", "bi-arrow-repeat", "Garantía - Recuperado"),

    # Taller & Tránsito
    "EN_TRANSITO": ("bg-cyan-soft text-cyan-900 border-cyan-300", "bi-truck", "En Tránsito"),
    "EN_TRANSITO_TALLER": ("bg-cyan-soft text-cyan-900 border-cyan-300", "bi-truck", "En Tránsito a Taller"),
    "EN_TALLER": ("bg-sky-soft text-sky-900 border-sky-300", "bi-wrench-adjustable", "En Taller"),
    "EN_REVISION": ("bg-yellow-soft text-yellow-900 border-yellow-300", "bi-search", "En Revisión"),
    "EN_REVISION_TALLER": ("bg-yellow-soft text-yellow-900 border-yellow-300", "bi-search", "En Revisión de Taller"),
    "EN_ESPERA_REFACCION": ("bg-amber-soft text-amber-900 border-amber-300", "bi-hourglass-split", "En Espera de Refacción"),

    # Confirmaciones & Finalización
    "CONFIRMADO_JEFE": ("bg-teal-soft text-teal-900 border-teal-300", "bi-person-check", "Confirmado por Jefe"),
    "CONFIRMADO": ("bg-emerald-soft text-emerald-900 border-emerald-300", "bi-check-all", "Confirmado"),
    "FINALIZADO": ("bg-slate-soft text-slate-900 border-slate-300", "bi-flag-fill", "Finalizado"),
    "PENDIENTE": ("bg-amber-soft text-amber-900 border-amber-300", "bi-clock", "Pendiente"),
}


@register.simple_tag
def status_badge(status_code, label=None):
    """
    Renders a stylized status badge implementing the 21 format rules from AppSheet.
    """
    if not status_code:
        return mark_safe('<span class="badge bg-secondary">Sin estado</span>')

    code = str(status_code).strip().upper()
    style_class, icon, default_label = BADGE_STYLES.get(
        code,
        ("bg-secondary-soft text-secondary border-secondary", "bi-dot", str(status_code)),
    )
    display_text = label or default_label

    html = f"""
    <span class="ssit-badge {style_class}">
        <i class="bi {icon} me-1"></i>
        <span>{display_text}</span>
    </span>
    """
    return mark_safe(html.strip())
