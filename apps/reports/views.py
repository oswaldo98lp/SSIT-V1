"""Views for Kárdex, Stock Balances, Logs, and Excel Exports."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.accounts.permissions import has_permission
from apps.cases.models import EquipmentCase
from apps.inventory.models import EquipmentModel, InventoryMovement
from apps.org.models import Region, Zone
from apps.org.selectors import get_user_allowed_regions
from apps.reports.forms import (
    KardexFilterForm,
    StockBalanceFilterForm,
    VoucherReportFilterForm,
    WorkshopReportFilterForm,
    ZoneReportFilterForm,
)
from apps.reports.services import (
    export_queryset_to_xlsx,
    get_kardex_report_data,
    get_stock_balances_summary,
    get_vouchers_report_data,
    get_workshop_cases_report_data,
)
from apps.vouchers.models import Voucher


@login_required
def report_dashboard_view(request: HttpRequest) -> HttpResponse:
    """Pantalla 10: Centro de Bitácoras y Reportes."""
    if not (
        has_permission(request.user, "view_zone_reports")
        or has_permission(request.user, "export_reports")
        or has_permission(request.user, "view_case")
    ):
        messages.error(request, "No tiene permisos para acceder al módulo de reportes.")
        return redirect("core:dashboard")

    return render(request, "reports/report_dashboard.html")


@login_required
def kardex_list_view(request: HttpRequest) -> HttpResponse:
    """Pantalla 9: Consulta y Exportación de Movimientos de Kárdex."""
    if not has_permission(request.user, "view_case"):
        messages.error(request, "No tiene permisos para consultar el Kárdex.")
        return redirect("core:dashboard")

    form = KardexFilterForm(request.GET)
    qs = get_kardex_report_data(
        user=request.user,
        start_date=request.GET.get("start_date") or None,
        end_date=request.GET.get("end_date") or None,
        region_id=request.GET.get("region") or None,
        warehouse=request.GET.get("warehouse") or None,
        condition=request.GET.get("condition") or None,
        model_id=request.GET.get("model") or None,
        serial_number=request.GET.get("serial_number") or None,
    )

    # Exportación XLSX
    if request.GET.get("export") == "xlsx":
        if not has_permission(request.user, "export_reports"):
            messages.error(request, "No tiene permisos para exportar reportes.")
            return redirect("reports:kardex_list")

        rows = []
        for m in qs:
            rows.append({
                "id": m.id,
                "moved_at": m.moved_at,
                "movement_type": m.get_movement_type_display(),
                "model": m.equipment_model.name,
                "brand": m.equipment_model.brand,
                "serial_number": m.serial_number,
                "quantity": m.quantity,
                "warehouse": m.get_warehouse_display(),
                "condition": m.get_condition_display(),
                "region": m.region.code,
                "folio": m.transfer_folio,
                "user": m.created_by.get_full_name() if m.created_by else "",
            })

        columns = [
            ("id", "ID"),
            ("moved_at", "Fecha y Hora"),
            ("movement_type", "Tipo Movimiento"),
            ("model", "Artículo / Modelo"),
            ("brand", "Marca"),
            ("serial_number", "Número de Serie"),
            ("quantity", "Cantidad"),
            ("warehouse", "Almacén"),
            ("condition", "Condición"),
            ("region", "Región"),
            ("folio", "Folio / Referencia"),
            ("user", "Registrado Por"),
        ]

        buffer = export_queryset_to_xlsx(rows, columns, sheet_title="Kardex")
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="kardex_movimientos.xlsx"'
        return response

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "reports/kardex_list.html", {
        "form": form,
        "page_obj": page_obj,
    })


@login_required
def stock_balance_view(request: HttpRequest) -> HttpResponse:
    """Pantalla 9: Existencias y saldos consolidados por almacén."""
    if not has_permission(request.user, "view_case"):
        messages.error(request, "No tiene permisos para consultar existencias.")
        return redirect("core:dashboard")

    form = StockBalanceFilterForm(request.GET)
    region_id = request.GET.get("region") or None
    warehouse = request.GET.get("warehouse") or None

    balances = get_stock_balances_summary(request.user, region_id=region_id, warehouse=warehouse)

    # Exportación XLSX
    if request.GET.get("export") == "xlsx":
        if not has_permission(request.user, "export_reports"):
            messages.error(request, "No tiene permisos para exportar reportes.")
            return redirect("reports:stock_balance")

        rows = []
        for b in balances:
            rows.append({
                "region": f"{b['region__name']} ({b['region__code']})",
                "model": b["equipment_model__name"],
                "brand": b["equipment_model__brand"],
                "warehouse": b["warehouse"],
                "condition": b["condition"],
                "balance": b["total_balance"],
            })

        columns = [
            ("region", "Región"),
            ("model", "Modelo / Artículo"),
            ("brand", "Marca"),
            ("warehouse", "Almacén"),
            ("condition", "Condición"),
            ("balance", "Existencia Actual"),
        ]

        buffer = export_queryset_to_xlsx(rows, columns, sheet_title="Existencias")
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="existencias_almacen.xlsx"'
        return response

    paginator = Paginator(balances, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "reports/stock_balance.html", {
        "form": form,
        "page_obj": page_obj,
    })


@login_required
def vouchers_report_view(request: HttpRequest) -> HttpResponse:
    """Pantalla 10: Bitácora histórica de Vales de Salida."""
    if not has_permission(request.user, "view_case"):
        messages.error(request, "No tiene permisos para consultar reportes.")
        return redirect("core:dashboard")

    form = VoucherReportFilterForm(request.GET)
    qs = get_vouchers_report_data(
        user=request.user,
        start_date=request.GET.get("start_date") or None,
        end_date=request.GET.get("end_date") or None,
        region_id=request.GET.get("region") or None,
        status=request.GET.get("status") or None,
        origin_type=request.GET.get("origin_type") or None,
    )

    if request.GET.get("export") == "xlsx":
        if not has_permission(request.user, "export_reports"):
            messages.error(request, "No tiene permisos de exportación.")
            return redirect("reports:vouchers_report")

        rows = []
        for v in qs:
            rows.append({
                "id": v.id,
                "created_at": v.created_at,
                "origin_type": v.get_origin_type_display(),
                "report_folio": v.report_folio,
                "region": v.region.code,
                "center": v.destination_center.name if v.destination_center else "",
                "status": v.get_status_display(),
                "requested_by": v.requested_by.get_full_name() if v.requested_by else "",
                "authorized_at": v.authorized_at,
                "delivered_at": v.delivered_at,
            })

        columns = [
            ("id", "ID Vale"),
            ("created_at", "Fecha Creación"),
            ("origin_type", "Tipo Origen"),
            ("report_folio", "Folio Reporte"),
            ("region", "Región"),
            ("center", "Centro Destino"),
            ("status", "Estatus"),
            ("requested_by", "Solicitado Por"),
            ("authorized_at", "Fecha Autorización"),
            ("delivered_at", "Fecha Surtido / Entrega"),
        ]

        buffer = export_queryset_to_xlsx(rows, columns, sheet_title="Historico_Vales")
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="historico_vales.xlsx"'
        return response

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "reports/voucher_report.html", {"form": form, "page_obj": page_obj})


@login_required
def workshop_report_view(request: HttpRequest) -> HttpResponse:
    """Pantalla 10: Bitácora de Taller Habilitado y Diagnósticos Técnicos."""
    if not has_permission(request.user, "view_case"):
        messages.error(request, "No tiene permisos para consultar bitácora de taller.")
        return redirect("core:dashboard")

    form = WorkshopReportFilterForm(request.GET)
    qs = get_workshop_cases_report_data(
        user=request.user,
        start_date=request.GET.get("start_date") or None,
        end_date=request.GET.get("end_date") or None,
        workshop_region_id=request.GET.get("workshop_region") or None,
        stage=request.GET.get("stage") or None,
    )

    if request.GET.get("export") == "xlsx":
        if not has_permission(request.user, "export_reports"):
            messages.error(request, "No tiene permisos para exportar reportes.")
            return redirect("reports:workshop_report")

        rows = []
        for c in qs:
            rows.append({
                "id": c.id,
                "created_at": c.created_at,
                "origin_region": c.origin_region.code,
                "workshop_region": c.workshop_region.code if c.workshop_region else "",
                "model": c.returned_model.name if c.returned_model else c.returned_model_text,
                "serial_number": c.returned_serial,
                "stage": c.stage,
                "definition": c.get_definition_display() if c.definition else "",
                "engineer": c.assigned_engineer.get_full_name() if c.assigned_engineer else "",
                "repaired_at": c.repaired_at,
                "repair_folio": c.repair_folio,
            })

        columns = [
            ("id", "Caso ID"),
            ("created_at", "Fecha Registro"),
            ("origin_region", "Región Origen"),
            ("workshop_region", "Taller Asignado"),
            ("model", "Artículo Devuelto"),
            ("serial_number", "Número de Serie"),
            ("stage", "Etapa Actual"),
            ("definition", "Definición Técnica"),
            ("engineer", "Técnico Asignado"),
            ("repaired_at", "Fecha Definición"),
            ("repair_folio", "Folio Reparación"),
        ]

        buffer = export_queryset_to_xlsx(rows, columns, sheet_title="Bitacora_Taller")
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="bitacora_taller.xlsx"'
        return response

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "reports/workshop_report.html", {"form": form, "page_obj": page_obj})


@login_required
def zone_summary_report_view(request: HttpRequest) -> HttpResponse:
    """Pantalla 10: Resumen Consolidado de Zona."""
    if not (has_permission(request.user, "view_zone_reports") or request.user.has_global_scope):
        messages.error(request, "No tiene permisos para consultar reportes de zona.")
        return redirect("reports:dashboard")

    form = ZoneReportFilterForm(request.GET)
    zone_id = request.GET.get("zone")

    zones_qs = Zone.objects.all().prefetch_related("regions")
    if zone_id:
        zones_qs = zones_qs.filter(id=zone_id)

    # Consolidar métricas por zona
    zone_metrics = []
    for zone in zones_qs:
        reg_ids = list(zone.regions.values_list("id", flat=True))
        vouchers_count = Voucher.objects.filter(region_id__in=reg_ids).count()
        vouchers_supplied = Voucher.objects.filter(region_id__in=reg_ids, status=Voucher.Status.SURTIDO).count()
        cases_count = EquipmentCase.objects.filter(origin_region_id__in=reg_ids).count()
        cases_scrap = EquipmentCase.objects.filter(origin_region_id__in=reg_ids, stage__in=["FINALIZADO_HUESARIO", "HUESARIO_CONFIRMADO"]).count()
        cases_repaired = EquipmentCase.objects.filter(origin_region_id__in=reg_ids, stage="FINALIZADO", definition=EquipmentCase.Definition.REPARADO).count()

        zone_metrics.append({
            "zone_name": zone.name,
            "regions_count": len(reg_ids),
            "vouchers_count": vouchers_count,
            "vouchers_supplied": vouchers_supplied,
            "cases_count": cases_count,
            "cases_repaired": cases_repaired,
            "cases_scrap": cases_scrap,
        })

    if request.GET.get("export") == "xlsx":
        if not has_permission(request.user, "export_reports"):
            messages.error(request, "No tiene permisos para exportar.")
            return redirect("reports:zone_summary")

        columns = [
            ("zone_name", "Zona Operativa"),
            ("regions_count", "Total Regiones"),
            ("vouchers_count", "Total Vales"),
            ("vouchers_supplied", "Vales Surtidos"),
            ("cases_count", "Total Casos Devolución"),
            ("cases_repaired", "Equipos Reparados"),
            ("cases_scrap", "Equipos a Huesario"),
        ]

        buffer = export_queryset_to_xlsx(zone_metrics, columns, sheet_title="Resumen_Zona")
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="resumen_zonas.xlsx"'
        return response

    return render(request, "reports/zone_summary.html", {"form": form, "zone_metrics": zone_metrics})


@login_required
def coupa_report_view(request: HttpRequest) -> HttpResponse:
    """Pantalla 10: Bitácora de Consumo Coupa."""
    if not has_permission(request.user, "view_coupa_consumption"):
        messages.error(request, "No tiene permisos para consultar consumos Coupa.")
        return redirect("core:dashboard")

    qs = Voucher.objects.filter(origin_type=Voucher.OriginType.COUPA).select_related(
        "requested_by", "region", "destination_center"
    ).prefetch_related("items").order_by("-created_at")

    if request.GET.get("export") == "xlsx":
        rows = []
        for v in qs:
            rows.append({
                "id": v.id,
                "coupa_id": v.report_folio,
                "created_at": v.created_at,
                "region": v.region.code,
                "center": v.destination_center.name if v.destination_center else "",
                "status": v.get_status_display(),
                "items_count": v.items.count(),
            })

        columns = [
            ("id", "ID"),
            ("coupa_id", "ID / Folio Coupa"),
            ("created_at", "Fecha Registro"),
            ("region", "Región"),
            ("center", "Centro Destino"),
            ("status", "Estatus"),
            ("items_count", "Piezas Surtidas"),
        ]

        buffer = export_queryset_to_xlsx(rows, columns, sheet_title="Consumo_Coupa")
        response = HttpResponse(
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="consumo_coupa.xlsx"'
        return response

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "reports/coupa_report.html", {"page_obj": page_obj})


@login_required
def inventory_reconciliation_view(request: HttpRequest) -> HttpResponse:
    """Pantalla de Conciliación de Inventario Físico vs Kárdex."""
    if not (has_permission(request.user, "export_reports") or request.user.has_global_scope):
        messages.error(request, "No tiene permisos para ejecutar conciliación de inventario.")
        return redirect("core:dashboard")

    import csv
    from apps.core.etl_services import generate_reconciliation_xlsx, reconcile_inventory_balances

    reconciliation_results = None

    if request.method == "POST" and request.FILES.get("physical_file"):
        uploaded_file = request.FILES["physical_file"]
        try:
            decoded_file = uploaded_file.read().decode("utf-8-sig").splitlines()
            reader = csv.DictReader(decoded_file)
            rows = list(reader)
            reconciliation_results = reconcile_inventory_balances(rows)

            if request.POST.get("action") == "export_xlsx":
                buffer = generate_reconciliation_xlsx(reconciliation_results)
                response = HttpResponse(
                    buffer.getvalue(),
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                response["Content-Disposition"] = 'attachment; filename="conciliacion_inventario.xlsx"'
                return response

            messages.success(
                request,
                f"Conciliación completada: {reconciliation_results['summary']['total_lines']} registros analizados con {reconciliation_results['summary']['match_rate']}% de concordancia."
            )
        except Exception as exc:
            messages.error(request, f"Error al procesar el archivo CSV: {str(exc)}")

    return render(request, "reports/reconciliation.html", {"results": reconciliation_results})

