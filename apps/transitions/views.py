"""Views for Generic Pending Inbox and Transition Modal Execution."""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.generic import TemplateView

from apps.cases.models import EquipmentCase
from apps.cases.selectors import get_cases_for_user
from apps.org.selectors import get_user_allowed_regions
from apps.transitions.registry import TRANSITIONS_REGISTRY
from apps.transitions.services import (
    apply_transition,
    get_available_transitions,
)
from apps.vouchers.models import Voucher
from apps.vouchers.selectors import get_vouchers_for_user


class PendingInboxView(LoginRequiredMixin, TemplateView):
    """
    Pantalla 2: Bandeja de pendientes genérica alimentada por transitions_rule,
    con filtros por etapa, región, folio y serie.
    """
    template_name = "transitions/pending_inbox.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Parámetros de filtrado
        selected_stage = self.request.GET.get("stage", "").strip()
        selected_region = self.request.GET.get("region", "").strip()
        folio_search = self.request.GET.get("folio", "").strip()
        serial_search = self.request.GET.get("serial", "").strip()
        entity_type = self.request.GET.get("entity_type", "ALL")

        allowed_regions = get_user_allowed_regions(user)
        pending_items = []

        # 1. Consultar Vales pendientes con alcance
        if entity_type in ["ALL", "VOUCHER"]:
            vouchers_qs = get_vouchers_for_user(user)
            if selected_region:
                vouchers_qs = vouchers_qs.filter(region__code=selected_region)
            if selected_stage:
                vouchers_qs = vouchers_qs.filter(status=selected_stage)
            if folio_search:
                vouchers_qs = vouchers_qs.filter(report_folio__icontains=folio_search)

            for voucher in vouchers_qs[:50]:
                transitions = get_available_transitions(user, voucher)
                pending_items.append({
                    "entity_type": "Vale",
                    "id": voucher.id,
                    "reference": voucher.report_folio or f"VALE-{voucher.id}",
                    "region": voucher.region.code,
                    "stage": voucher.status,
                    "stage_label": voucher.get_status_display(),
                    "requested_by": voucher.requested_by.full_name or voucher.requested_by.email,
                    "destination": str(voucher.destination_center) if voucher.destination_center else "N/A",
                    "created_at": voucher.created_at,
                    "available_transitions": transitions,
                    "entity_instance": voucher,
                })

        # 2. Consultar Casos de equipo pendientes con alcance
        if entity_type in ["ALL", "CASE"]:
            cases_qs = get_cases_for_user(user)
            if selected_region:
                cases_qs = cases_qs.filter(origin_region__code=selected_region)
            if selected_stage:
                cases_qs = cases_qs.filter(stage=selected_stage)
            if folio_search:
                cases_qs = cases_qs.filter(repair_folio__icontains=folio_search)
            if serial_search:
                cases_qs = cases_qs.filter(returned_serial__icontains=serial_search)

            for case in cases_qs[:50]:
                transitions = get_available_transitions(user, case)
                pending_items.append({
                    "entity_type": "Caso de Devolución",
                    "id": case.id,
                    "reference": f"S/N: {case.returned_serial}",
                    "region": case.origin_region.code,
                    "stage": case.stage,
                    "stage_label": case.stage,
                    "requested_by": case.returned_model.name if case.returned_model else case.returned_model_text,
                    "destination": case.location,
                    "created_at": case.created_at,
                    "available_transitions": transitions,
                    "entity_instance": case,
                })

        # Ordenar por fecha reciente
        pending_items.sort(key=lambda x: x["created_at"], reverse=True)

        context.update({
            "pending_items": pending_items,
            "allowed_regions": allowed_regions,
            "selected_stage": selected_stage,
            "selected_region": selected_region,
            "folio_search": folio_search,
            "serial_search": serial_search,
            "entity_type": entity_type,
            "total_pending": len(pending_items),
        })
        return context


def transition_modal_view(request, entity_type: str, entity_id: int, transition_code: str):
    """
    Renders an HTMX modal with input fields defined in the transition inputs_schema.
    """
    rule = TRANSITIONS_REGISTRY.get(transition_code)
    if not rule:
        return HttpResponse("Transición no encontrada.", status=404)

    # Cargar entidad
    if entity_type.upper() == "VOUCHER":
        entity_instance = get_object_or_404(Voucher, id=entity_id)
    elif entity_type.upper() in ["CASE", "EQUIPMENTCASE"]:
        entity_instance = get_object_or_404(EquipmentCase, id=entity_id)
    else:
        return HttpResponse("Tipo de entidad inválido.", status=400)

    if request.method == "POST":
        data = request.POST.dict()
        try:
            apply_transition(request.user, entity_instance, transition_code, data)
            response = HttpResponse(
                '<div class="alert alert-success p-3">Acción ejecutada correctamente. Recargando...</div>'
            )
            response["HX-Refresh"] = "true"
            return response
        except Exception as exc:
            return render(
                request,
                "transitions/modal_form.html",
                {
                    "rule": rule,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "entity_instance": entity_instance,
                    "error_message": str(exc),
                },
            )

    return render(
        request,
        "transitions/modal_form.html",
        {
            "rule": rule,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_instance": entity_instance,
        },
    )
