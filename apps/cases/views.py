"""Views for Equipment Cases: Returns, Diagnosis, Office Folios, and Workshop."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.permissions import has_permission
from apps.cases.forms import (
    AssignEngineerForm,
    CancelReturnForm,
    CaseReturnForm,
    ManagerCancellationForm,
    RepairFolioAssignForm,
    ReturnReviewRequestForm,
    ScrapActionForm,
    TechnicalDiagnosisForm,
    WarehouseDiagnosisForm,
    WarehouseEntryConfirmForm,
    WorkshopEntryConfirmForm,
    WorkshopReviewRequestForm,
    WorkshopSendForm,
    WorkshopWaitPartsForm,
)
from apps.cases.models import EquipmentCase
from apps.cases.selectors import get_cases_for_user, get_workshop_cases_for_user
from apps.cases.services import legacy_status
from apps.core.models import CoreEvent
from apps.documents.services import generate_return_pdf
from apps.org.selectors import get_user_allowed_regions
from apps.transitions.services import apply_transition


@login_required
def case_list_view(request: HttpRequest) -> HttpResponse:
    """Pantalla 5: Consulta general de casos de devolución."""
    if not has_permission(request.user, "view_case"):
        messages.error(request, "No tiene permisos para consultar casos de devolución.")
        return redirect("core:dashboard")

    qs = get_cases_for_user(request.user)

    stage_filter = request.GET.get("stage")
    region_filter = request.GET.get("region")
    location_filter = request.GET.get("location")
    route_filter = request.GET.get("route")
    search_query = request.GET.get("q", "").strip()

    if stage_filter:
        qs = qs.filter(stage=stage_filter)
    if region_filter:
        qs = qs.filter(origin_region_id=region_filter)
    if location_filter:
        qs = qs.filter(location=location_filter)
    if route_filter:
        qs = qs.filter(route=route_filter)
    if search_query:
        qs = qs.filter(
            Q(returned_serial__icontains=search_query)
            | Q(shipping_folio__icontains=search_query)
            | Q(repair_folio__icontains=search_query)
            | Q(returned_model__name__icontains=search_query)
        )

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "regions": get_user_allowed_regions(request.user),
        "stage_filter": stage_filter,
        "region_filter": region_filter,
        "location_filter": location_filter,
        "route_filter": route_filter,
        "search_query": search_query,
        "stages": [
            ("PENDIENTE_CONFIRMAR", "Pendiente de Confirmar"),
            ("EN_REVISION", "En Revisión"),
            ("CONFIRMADO", "Confirmado (Almacén)"),
            ("POR_REPARAR", "Por Reparar (Taller)"),
            ("DEFINIDO", "Definido por Técnico"),
            ("CONFIRMADO_JEFE", "Confirmado por Jefe"),
            ("FINALIZADO", "Finalizado (En Almacén)"),
            ("SIN_DEVOLUCION", "Sin Devolución (N/A)"),
        ],
    }
    return render(request, "cases/case_list.html", context)


@login_required
def case_return_create_view(request: HttpRequest) -> HttpResponse:
    """Pantalla 5: Registro de devolución desde centro o almacén."""
    if not has_permission(request.user, "register_return"):
        messages.error(request, "No tiene permisos para registrar devoluciones.")
        return redirect("cases:case_list")

    if request.method == "POST":
        form = CaseReturnForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                data = {
                    "origin_region_id": form.cleaned_data["origin_region"].id,
                    "returned_model_id": form.cleaned_data["returned_model"].id,
                    "returned_serial": form.cleaned_data["returned_serial"],
                    "returned_brand": form.cleaned_data.get("returned_brand", ""),
                    "route": form.cleaned_data["route"],
                    "shipping_type": form.cleaned_data["shipping_type"],
                    "shipping_folio": form.cleaned_data.get("shipping_folio", ""),
                    "stock_direct_reason_id": form.cleaned_data["stock_direct_reason"].id if form.cleaned_data.get("stock_direct_reason") else None,
                    "applies_workshop_entry": form.cleaned_data.get("applies_workshop_entry", False),
                    "applies_reason_id": form.cleaned_data["applies_reason"].id if form.cleaned_data.get("applies_reason") else None,
                    "failure": form.cleaned_data.get("failure", ""),
                    "item_id": form.cleaned_data.get("item_id"),
                }
                event = apply_transition(
                    user=request.user,
                    entity_instance=None,
                    transition_code="register_return",
                    data=data,
                )
                case = EquipmentCase.objects.get(id=event.entity_id)

                # Generar PDF y QR oficial
                generate_return_pdf(case, requesting_user=request.user)

                messages.success(request, f"Devolución #{case.id} registrada exitosamente (Serie: {case.returned_serial}).")
                return redirect("cases:case_detail", pk=case.id)
            except Exception as e:
                messages.error(request, f"Error al procesar la devolución: {str(e)}")
    else:
        form = CaseReturnForm(user=request.user)

    return render(request, "cases/case_create.html", {"form": form})


@login_required
def case_detail_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Detalle completo del caso, línea de tiempo de auditoría y acciones disponibles."""
    qs = get_cases_for_user(request.user)
    case = get_object_or_404(qs, pk=pk)

    events = CoreEvent.objects.filter(entity_type="EquipmentCase", entity_id=case.id).select_related("user").order_by("created_at")

    can_dictamen = has_permission(request.user, "confirm_return") and case.stage == "PENDIENTE_CONFIRMAR"
    can_assign_folio = has_permission(request.user, "assign_repair_folio") and case.stage == "CONFIRMADO"
    can_assign_engineer = has_permission(request.user, "assign_engineer") and case.stage in ("CONFIRMADO", "EN_TALLER", "ASIGNADO")
    can_define = has_permission(request.user, "define_equipment") and case.stage in ("POR_REPARAR", "ASIGNADO", "EN_ESPERA_REFACCION")
    can_boss_confirm = has_permission(request.user, "review_definition_boss") and case.stage == "DEFINIDO"
    can_warehouse_entry = has_permission(request.user, "review_definition_warehouse") and case.stage in ("CONFIRMADO_JEFE", "DEFINIDO")
    can_confirm_scrap = has_permission(request.user, "manage_scrap") and case.stage == "DEFINIDO" and case.definition == "HUESARIO"
    can_deliver_scrap = has_permission(request.user, "manage_scrap") and case.stage == "HUESARIO_CONFIRMADO"
    can_send_workshop = has_permission(request.user, "confirm_return") and case.stage in ("CONFIRMADO", "PENDIENTE_CONFIRMAR") and case.location != "TALLER"
    can_cancel_workshop_send = has_permission(request.user, "confirm_return") and case.stage == "EN_TRANSITO_TALLER"
    can_cancel_return = has_permission(request.user, "register_return") and case.stage == "PENDIENTE_CONFIRMAR"
    can_manager_cancellation = has_permission(request.user, "authorize_voucher") and case.stage == "CANCELADA"
    can_warehouse_receive_cancelled = has_permission(request.user, "confirm_return") and case.stage in ("CANCELACION_CONFIRMADA", "CANCELADA")

    context = {
        "case": case,
        "events": events,
        "can_dictamen": can_dictamen,
        "can_assign_folio": can_assign_folio,
        "can_assign_engineer": can_assign_engineer,
        "can_define": can_define,
        "can_boss_confirm": can_boss_confirm,
        "can_warehouse_entry": can_warehouse_entry,
        "can_confirm_scrap": can_confirm_scrap,
        "can_deliver_scrap": can_deliver_scrap,
        "can_send_workshop": can_send_workshop,
        "can_cancel_workshop_send": can_cancel_workshop_send,
        "can_cancel_return": can_cancel_return,
        "can_manager_cancellation": can_manager_cancellation,
        "can_warehouse_receive_cancelled": can_warehouse_receive_cancelled,
    }
    return render(request, "cases/case_detail.html", context)


@login_required
def warehouse_inbox_view(request: HttpRequest) -> HttpResponse:
    """Pantalla 6: Bandeja de recepción y dictamen de almacén."""
    if not has_permission(request.user, "confirm_return"):
        messages.error(request, "No tiene permisos de Almacén para dictaminar devoluciones.")
        return redirect("core:dashboard")

    pending_cases = get_cases_for_user(request.user, stage="PENDIENTE_CONFIRMAR")
    paginator = Paginator(pending_cases, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "cases/warehouse_inbox.html", {"page_obj": page_obj})


@login_required
def warehouse_dictamen_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Pantalla 6: Emitir dictamen de almacén sobre un caso devuelto."""
    if not has_permission(request.user, "confirm_return"):
        messages.error(request, "No tiene permisos para emitir dictamen de almacén.")
        return redirect("cases:case_list")

    qs = get_cases_for_user(request.user, stage="PENDIENTE_CONFIRMAR")
    case = get_object_or_404(qs, pk=pk)

    if request.method == "POST":
        form = WarehouseDiagnosisForm(request.POST)
        if form.is_valid():
            try:
                apply_transition(
                    user=request.user,
                    entity_instance=case,
                    transition_code="confirm_return",
                    data={
                        "ruling_id": form.cleaned_data["ruling"].id,
                        "returned_model_id": form.cleaned_data["returned_model"].id if form.cleaned_data.get("returned_model") else case.returned_model_id,
                        "comments": form.cleaned_data.get("comments", ""),
                    },
                )
                messages.success(request, f"Dictamen registrado exitosamente para el Caso #{case.id}.")
                return redirect("cases:warehouse_inbox")
            except Exception as e:
                messages.error(request, f"Error al emitir dictamen: {str(e)}")
    else:
        form = WarehouseDiagnosisForm(initial={"returned_model": case.returned_model})

    return render(request, "cases/warehouse_dictamen.html", {"case": case, "form": form})


@login_required
def request_return_review_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Pantalla 6: Solicitar revisión de una devolución en almacén."""
    if not has_permission(request.user, "confirm_return"):
        messages.error(request, "No tiene permisos para solicitar revisión.")
        return redirect("cases:case_list")

    qs = get_cases_for_user(request.user, stage="PENDIENTE_CONFIRMAR")
    case = get_object_or_404(qs, pk=pk)

    if request.method == "POST":
        form = ReturnReviewRequestForm(request.POST)
        if form.is_valid():
            try:
                apply_transition(
                    user=request.user,
                    entity_instance=case,
                    transition_code="request_return_review",
                    data={"review_reason": form.cleaned_data["review_reason"]},
                )
                messages.warning(request, f"Caso #{case.id} enviado a revisión exitosamente.")
                return redirect("cases:warehouse_inbox")
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
    else:
        form = ReturnReviewRequestForm()

    return render(request, "cases/return_review_request.html", {"case": case, "form": form})


@login_required
def repair_folio_inbox_view(request: HttpRequest) -> HttpResponse:
    """Pantalla 7: Bandeja de Oficina para asignación de folios de reparación."""
    if not has_permission(request.user, "assign_repair_folio"):
        messages.error(request, "No tiene permisos de Oficina para asignar folios de reparación.")
        return redirect("core:dashboard")

    cases_qs = get_cases_for_user(request.user, stage="CONFIRMADO", allow_global=True)
    paginator = Paginator(cases_qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "cases/repair_folio_inbox.html", {"page_obj": page_obj})


@login_required
def assign_repair_folio_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Pantalla 7: Asignar folio de reparación y fecha a un caso."""
    if not has_permission(request.user, "assign_repair_folio"):
        messages.error(request, "No tiene permisos para asignar folios de reparación.")
        return redirect("cases:repair_folio_inbox")

    qs = get_cases_for_user(request.user, stage="CONFIRMADO", allow_global=True)
    case = get_object_or_404(qs, pk=pk)

    if request.method == "POST":
        form = RepairFolioAssignForm(request.POST)
        if form.is_valid():
            try:
                apply_transition(
                    user=request.user,
                    entity_instance=case,
                    transition_code="assign_repair_folio",
                    data={
                        "repair_folio": form.cleaned_data["repair_folio"],
                        "folio_date": form.cleaned_data["folio_date"],
                        "insight_note_id": form.cleaned_data["insight_note"].id if form.cleaned_data.get("insight_note") else None,
                    },
                )
                messages.success(request, f"Folio de reparación {form.cleaned_data['repair_folio']} asignado al Caso #{case.id}.")
                return redirect("cases:repair_folio_inbox")
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
    else:
        form = RepairFolioAssignForm()

    return render(request, "cases/assign_repair_folio.html", {"case": case, "form": form})


@login_required
def workshop_inbox_view(request: HttpRequest) -> HttpResponse:
    """Pantallas 8 y 9: Bandeja de trabajo en Taller Habilitado."""
    if not (has_permission(request.user, "assign_engineer") or has_permission(request.user, "define_equipment")):
        messages.error(request, "No tiene permisos para acceder al módulo de Taller.")
        return redirect("core:dashboard")

    stage_filter = request.GET.get("stage", "POR_REPARAR")
    cases_qs = get_workshop_cases_for_user(request.user)

    if stage_filter:
        cases_qs = cases_qs.filter(stage=stage_filter)

    # Si es técnico, filtrar preferentemente sus asignados
    if request.user.groups.filter(name="SOPORTE_TALLER").exists() and not request.GET.get("all"):
        cases_qs = cases_qs.filter(assigned_engineer=request.user)

    paginator = Paginator(cases_qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "cases/workshop_inbox.html", {"page_obj": page_obj, "stage_filter": stage_filter})


@login_required
def assign_engineer_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Pantallas 8 y 9: Asignar ingeniero de taller al caso."""
    if not (has_permission(request.user, "assign_engineer") or has_permission(request.user, "assign_workshop_repair")):
        messages.error(request, "No tiene permisos para asignar ingenieros.")
        return redirect("cases:workshop_inbox")

    case = get_object_or_404(EquipmentCase, pk=pk, stage__in=["CONFIRMADO", "EN_TALLER", "EN_REVISION_TALLER"])

    if request.method == "POST":
        form = AssignEngineerForm(request.POST)
        if form.is_valid():
            try:
                transition_code = "workshop_assign_engineer" if case.location == "TALLER" else "assign_engineer"
                apply_transition(
                    user=request.user,
                    entity_instance=case,
                    transition_code=transition_code,
                    data={"assigned_engineer_id": form.cleaned_data["assigned_engineer"].id},
                )
                messages.success(request, f"Caso #{case.id} asignado a {form.cleaned_data['assigned_engineer'].get_full_name()}.")
                return redirect("cases:workshop_inbox")
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
    else:
        form = AssignEngineerForm()

    return render(request, "cases/assign_engineer.html", {"case": case, "form": form})


@login_required
def technical_diagnosis_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Pantallas 8 y 9: Dictamen técnico y definición del equipo."""
    if not (has_permission(request.user, "define_equipment") or has_permission(request.user, "define_workshop_equipment")):
        messages.error(request, "No tiene permisos para definir diagnósticos técnicos.")
        return redirect("cases:workshop_inbox")

    case = get_object_or_404(EquipmentCase, pk=pk, stage__in=["POR_REPARAR", "ASIGNADO", "EN_ESPERA_REFACCION"])

    if request.method == "POST":
        form = TechnicalDiagnosisForm(request.POST)
        if form.is_valid():
            try:
                transition_code = "workshop_define_equipment" if case.location == "TALLER" else "define_equipment"
                apply_transition(
                    user=request.user,
                    entity_instance=case,
                    transition_code=transition_code,
                    data={
                        "definition": form.cleaned_data["definition"],
                        "repair_comments": form.cleaned_data["repair_comments"],
                        "warranty_solution": form.cleaned_data.get("warranty_solution"),
                        "new_serial": form.cleaned_data.get("new_serial"),
                        "insight_repair_confirmed": form.cleaned_data.get("insight_repair_confirmed", False),
                    },
                )
                messages.success(request, f"Definición técnica guardada para el Caso #{case.id} ({form.cleaned_data['definition']}).")
                return redirect("cases:workshop_inbox")
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
    else:
        form = TechnicalDiagnosisForm()

    return render(request, "cases/technical_diagnosis.html", {"case": case, "form": form})


@login_required
@require_POST
def boss_confirm_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Pantallas 8 y 9: Validación y confirmación del Jefe de Taller."""
    if not has_permission(request.user, "review_definition_boss"):
        messages.error(request, "No tiene permisos de Jefe de Taller para validar definiciones.")
        return redirect("cases:workshop_inbox")

    case = get_object_or_404(EquipmentCase, pk=pk, stage="DEFINIDO")
    try:
        apply_transition(
            user=request.user,
            entity_instance=case,
            transition_code="boss_confirm_definition",
            data={"comments": request.POST.get("comments", "")},
        )
        messages.success(request, f"Definición técnica del Caso #{case.id} confirmada por el Jefe de Taller.")
    except Exception as e:
        messages.error(request, f"Error al confirmar: {str(e)}")

    return redirect("cases:case_detail", pk=case.id)


@login_required
def warehouse_confirm_entry_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Pantallas 8 y 9: Confirmación final de entrada a almacén e impacto en Kárdex."""
    if not has_permission(request.user, "review_definition_warehouse"):
        messages.error(request, "No tiene permisos de Almacén para confirmar reingreso.")
        return redirect("cases:case_list")

    case = get_object_or_404(EquipmentCase, pk=pk, stage__in=["CONFIRMADO_JEFE", "DEFINIDO"])

    if request.method == "POST":
        form = WarehouseEntryConfirmForm(request.POST)
        if form.is_valid():
            try:
                apply_transition(
                    user=request.user,
                    entity_instance=case,
                    transition_code="warehouse_confirm_definition",
                    data={
                        "destination_warehouse": form.cleaned_data["destination_warehouse"],
                        "comments": form.cleaned_data.get("comments", ""),
                    },
                )
                messages.success(request, f"Equipo del Caso #{case.id} reingresado a {form.cleaned_data['destination_warehouse']} con movimiento de Kárdex.")
                return redirect("cases:case_detail", pk=case.id)
            except Exception as e:
                messages.error(request, f"Error al confirmar entrada: {str(e)}")
    else:
        form = WarehouseEntryConfirmForm()

    return render(request, "cases/warehouse_confirm_entry.html", {"case": case, "form": form})


# =============================================================================
# PANTALLA 8: HUESARIO / SCRAP Y REUTILIZACIÓN (FLUJO C)
# =============================================================================

@login_required
def huesario_inbox_view(request: HttpRequest) -> HttpResponse:
    """Pantalla 8: Bandeja de Huesario (pendientes, confirmados y entregados)."""
    if not (has_permission(request.user, "manage_scrap") or has_permission(request.user, "view_case")):
        messages.error(request, "No tiene permisos para acceder al módulo de Huesario.")
        return redirect("core:dashboard")

    tab = request.GET.get("tab", "pending")
    qs = get_cases_for_user(request.user)

    if tab == "pending":
        # Casos definidos como HUESARIO pendientes de confirmación por jefe
        cases_qs = qs.filter(definition="HUESARIO", stage="DEFINIDO")
    elif tab == "confirmed":
        # Casos con envío a huesario confirmado pendientes de entrega física
        cases_qs = qs.filter(stage="HUESARIO_CONFIRMADO")
    elif tab == "delivered":
        # Casos finalizados en huesario
        cases_qs = qs.filter(stage="FINALIZADO_HUESARIO")
    else:
        cases_qs = qs.filter(Q(definition="HUESARIO") | Q(scrap_status__isnull=False))

    paginator = Paginator(cases_qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "cases/huesario_inbox.html", {"page_obj": page_obj, "tab": tab})


@login_required
def confirm_scrap_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Pantalla 8: Jefe confirma destino a Huesario."""
    if not (has_permission(request.user, "review_definition_boss") or has_permission(request.user, "manage_scrap")):
        messages.error(request, "No tiene permisos para confirmar huesario.")
        return redirect("cases:huesario_inbox")

    case = get_object_or_404(EquipmentCase, pk=pk, stage="DEFINIDO")

    if request.method == "POST":
        form = ScrapActionForm(request.POST)
        if form.is_valid():
            try:
                apply_transition(
                    user=request.user,
                    entity_instance=case,
                    transition_code="confirm_scrap_boss",
                    data={"comments": form.cleaned_data.get("comments", "")},
                )
                messages.success(request, f"Caso #{case.id} confirmado para Huesario / Scrap.")
                return redirect("cases:huesario_inbox")
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
    else:
        form = ScrapActionForm()

    return render(request, "cases/scrap_action.html", {
        "case": case,
        "form": form,
        "title": "Confirmar Envío a Huesario",
        "btn_label": "Confirmar Huesario",
        "btn_class": "btn-warning",
    })


@login_required
def deliver_scrap_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Pantalla 8: Almacén entrega / finaliza equipo en Huesario."""
    if not has_permission(request.user, "manage_scrap"):
        messages.error(request, "No tiene permisos para entregar a huesario.")
        return redirect("cases:huesario_inbox")

    case = get_object_or_404(EquipmentCase, pk=pk, stage="HUESARIO_CONFIRMADO")

    if request.method == "POST":
        form = ScrapActionForm(request.POST)
        if form.is_valid():
            try:
                apply_transition(
                    user=request.user,
                    entity_instance=case,
                    transition_code="deliver_scrap",
                    data={"comments": form.cleaned_data.get("comments", "")},
                )
                messages.success(request, f"Equipo del Caso #{case.id} entregado a Huesario (Finalizado).")
                return redirect("cases:huesario_inbox")
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
    else:
        form = ScrapActionForm()

    return render(request, "cases/scrap_action.html", {
        "case": case,
        "form": form,
        "title": "Registrar Entrega Final a Huesario",
        "btn_label": "Registrar Entrega",
        "btn_class": "btn-danger",
    })


@login_required
def return_scrap_to_repair_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Pantalla 8: Revertir equipo de Huesario de regreso a Reparación."""
    if not (has_permission(request.user, "review_definition_boss") or has_permission(request.user, "manage_scrap")):
        messages.error(request, "No tiene permisos para revertir huesario.")
        return redirect("cases:huesario_inbox")

    case = get_object_or_404(EquipmentCase, pk=pk, stage__in=["HUESARIO_CONFIRMADO", "DEFINIDO"])

    if request.method == "POST":
        form = ScrapActionForm(request.POST)
        if form.is_valid():
            try:
                apply_transition(
                    user=request.user,
                    entity_instance=case,
                    transition_code="return_scrap_to_repair",
                    data={"comments": form.cleaned_data.get("comments", "")},
                )
                messages.warning(request, f"Caso #{case.id} revertido de Huesario a Reparación.")
                return redirect("cases:huesario_inbox")
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
    else:
        form = ScrapActionForm()

    return render(request, "cases/scrap_action.html", {
        "case": case,
        "form": form,
        "title": "Revertir Huesario a Reparación",
        "btn_label": "Revertir a Reparación",
        "btn_class": "btn-outline-primary",
    })


# =============================================================================
# FLUJO D: TALLER HABILITADO (LOCATION: TALLER)
# =============================================================================

@login_required
def send_to_workshop_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Enviar equipo a Taller Habilitado."""
    if not has_permission(request.user, "confirm_return"):
        messages.error(request, "No tiene permisos para enviar a taller habilitado.")
        return redirect("cases:warehouse_inbox")

    case = get_object_or_404(EquipmentCase, pk=pk, stage__in=["CONFIRMADO", "PENDIENTE_CONFIRMAR"])

    if request.method == "POST":
        form = WorkshopSendForm(request.POST)
        if form.is_valid():
            try:
                apply_transition(
                    user=request.user,
                    entity_instance=case,
                    transition_code="send_to_workshop",
                    data={
                        "workshop_region_id": form.cleaned_data["workshop_region"].id,
                        "shipping_folio": form.cleaned_data.get("shipping_folio", ""),
                        "comments": form.cleaned_data.get("comments", ""),
                    },
                )
                messages.success(request, f"Caso #{case.id} enviado a Taller Habilitado ({form.cleaned_data['workshop_region'].name}).")
                return redirect("cases:case_detail", pk=case.id)
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
    else:
        form = WorkshopSendForm()

    return render(request, "cases/send_to_workshop.html", {"case": case, "form": form})


@login_required
def cancel_workshop_send_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Cancelar traslado a Taller Habilitado."""
    if not has_permission(request.user, "confirm_return"):
        messages.error(request, "No tiene permisos para cancelar envío a taller.")
        return redirect("cases:case_detail", pk=pk)

    case = get_object_or_404(EquipmentCase, pk=pk, stage="EN_TRANSITO_TALLER")
    try:
        apply_transition(
            user=request.user,
            entity_instance=case,
            transition_code="cancel_workshop_send",
            data={"comments": "Cancelación de traslado a taller"},
        )
        messages.warning(request, f"Traslado del Caso #{case.id} cancelado y revertido a Centro.")
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")

    return redirect("cases:case_detail", pk=case.id)


@login_required
def workshop_confirm_entry_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Jefe de Taller confirma recepción física del equipo en Taller Habilitado."""
    if not has_permission(request.user, "manage_workshop"):
        messages.error(request, "No tiene permisos de Jefe de Taller.")
        return redirect("cases:workshop_inbox")

    case = get_object_or_404(EquipmentCase, pk=pk, stage="EN_TRANSITO_TALLER")

    if request.method == "POST":
        form = WorkshopEntryConfirmForm(request.POST)
        if form.is_valid():
            try:
                apply_transition(
                    user=request.user,
                    entity_instance=case,
                    transition_code="workshop_confirm_entry",
                    data={
                        "returned_model_id": form.cleaned_data["returned_model"].id if form.cleaned_data.get("returned_model") else case.returned_model_id,
                        "comments": form.cleaned_data.get("comments", ""),
                    },
                )
                messages.success(request, f"Recepción física del Caso #{case.id} confirmada en Taller.")
                return redirect("cases:workshop_inbox")
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
    else:
        form = WorkshopEntryConfirmForm(initial={"returned_model": case.returned_model})

    return render(request, "cases/workshop_confirm_entry.html", {"case": case, "form": form})


@login_required
def workshop_request_review_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Solicitar revisión técnica en Taller Habilitado."""
    if not has_permission(request.user, "manage_workshop"):
        messages.error(request, "No tiene permisos para solicitar revisión en taller.")
        return redirect("cases:workshop_inbox")

    case = get_object_or_404(EquipmentCase, pk=pk, stage__in=["EN_TALLER", "EN_TRANSITO_TALLER"])

    if request.method == "POST":
        form = WorkshopReviewRequestForm(request.POST)
        if form.is_valid():
            try:
                apply_transition(
                    user=request.user,
                    entity_instance=case,
                    transition_code="workshop_request_review",
                    data={"review_reason": form.cleaned_data["review_reason"]},
                )
                messages.warning(request, f"Caso #{case.id} puesto en revisión técnica de taller.")
                return redirect("cases:workshop_inbox")
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
    else:
        form = WorkshopReviewRequestForm()

    return render(request, "cases/workshop_review_request.html", {"case": case, "form": form})


@login_required
def workshop_wait_parts_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Pausar reparación en espera de refacciones."""
    if not (has_permission(request.user, "manage_workshop") or has_permission(request.user, "define_workshop_equipment")):
        messages.error(request, "No tiene permisos para modificar estado de taller.")
        return redirect("cases:workshop_inbox")

    case = get_object_or_404(EquipmentCase, pk=pk, stage__in=["EN_TALLER", "ASIGNADO", "POR_REPARAR"])

    if request.method == "POST":
        form = WorkshopWaitPartsForm(request.POST)
        if form.is_valid():
            try:
                apply_transition(
                    user=request.user,
                    entity_instance=case,
                    transition_code="workshop_wait_parts",
                    data={"comments": form.cleaned_data["comments"]},
                )
                messages.info(request, f"Caso #{case.id} marcado en espera de refacciones.")
                return redirect("cases:workshop_inbox")
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
    else:
        form = WorkshopWaitPartsForm()

    return render(request, "cases/workshop_wait_parts.html", {"case": case, "form": form})


# =============================================================================
# CANCELACIONES DE DEVOLUCIÓN EN CENTRO
# =============================================================================

@login_required
def cancel_return_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Centro cancela una devolución antes de ser confirmada."""
    if not has_permission(request.user, "register_return"):
        messages.error(request, "No tiene permisos para cancelar devoluciones.")
        return redirect("cases:case_list")

    case = get_object_or_404(EquipmentCase, pk=pk, stage="PENDIENTE_CONFIRMAR")

    if request.method == "POST":
        form = CancelReturnForm(request.POST)
        if form.is_valid():
            try:
                apply_transition(
                    user=request.user,
                    entity_instance=case,
                    transition_code="cancel_return",
                    data={"cancel_reason": form.cleaned_data["cancel_reason"]},
                )
                messages.warning(request, f"Devolución del Caso #{case.id} cancelada.")
                return redirect("cases:case_detail", pk=case.id)
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
    else:
        form = CancelReturnForm()

    return render(request, "cases/cancel_return.html", {"case": case, "form": form})


@login_required
def manager_confirm_cancellation_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Gerente confirma cancelación de devolución."""
    if not has_permission(request.user, "authorize_voucher"):
        messages.error(request, "No tiene permisos de Gerente para confirmar cancelaciones.")
        return redirect("cases:case_list")

    case = get_object_or_404(EquipmentCase, pk=pk, stage="CANCELADA")

    if request.method == "POST":
        form = ManagerCancellationForm(request.POST)
        if form.is_valid():
            try:
                apply_transition(
                    user=request.user,
                    entity_instance=case,
                    transition_code="manager_confirm_cancellation",
                    data={
                        "cancel_reason_id": form.cleaned_data["cancel_reason"].id if form.cleaned_data.get("cancel_reason") else 1,
                        "comments": form.cleaned_data.get("comments", ""),
                    },
                )
                messages.success(request, f"Cancelación del Caso #{case.id} confirmada por Gerente.")
                return redirect("cases:case_detail", pk=case.id)
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
    else:
        form = ManagerCancellationForm()

    return render(request, "cases/manager_cancellation.html", {"case": case, "form": form, "action": "confirm"})


@login_required
def warehouse_receive_cancelled_view(request: HttpRequest, pk: int) -> HttpResponse:
    """Almacén confirma recepción física de equipo cancelado e ingresa al Kárdex."""
    if not has_permission(request.user, "confirm_return"):
        messages.error(request, "No tiene permisos de Almacén.")
        return redirect("cases:case_list")

    case = get_object_or_404(EquipmentCase, pk=pk, stage__in=["CANCELACION_CONFIRMADA", "CANCELADA"])
    try:
        apply_transition(
            user=request.user,
            entity_instance=case,
            transition_code="warehouse_receive_cancelled",
            data={"comments": "Recepción física de equipo cancelado en almacén"},
        )
        messages.success(request, f"Equipo cancelado del Caso #{case.id} ingresado a Almacén con movimiento en Kárdex.")
    except Exception as e:
        messages.error(request, f"Error: {str(e)}")

    return redirect("cases:case_detail", pk=case.id)
