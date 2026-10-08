"""Reports and XLSX Export Services for SSIT 2.0."""
import io
from datetime import datetime
from typing import Any, Iterable

from django.db.models import Case, F, IntegerField, Q, QuerySet, Sum, Value, When
from django.utils import timezone
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from apps.cases.models import EquipmentCase
from apps.inventory.models import EquipmentModel, InventoryItem, InventoryMovement
from apps.vouchers.models import Voucher, VoucherLine


def export_queryset_to_xlsx(
    rows: Iterable[dict[str, Any]],
    columns: list[tuple[str, str]],  # List of (field_key, column_header)
    sheet_title: str = "Reporte",
) -> io.BytesIO:
    """
    Generates a professionally styled Excel workbook in-memory and returns BytesIO buffer.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]

    # Styles
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")  # Dark Slate Blue
    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Arial", size=10)
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    # 1. Write Header Row
    for col_idx, (_, header_label) in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header_label)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = thin_border
    ws.row_dimensions[1].height = 26

    # 2. Write Data Rows
    for row_idx, item in enumerate(rows, start=2):
        ws.row_dimensions[row_idx].height = 20
        for col_idx, (field_key, _) in enumerate(columns, start=1):
            val = item.get(field_key, "")
            if isinstance(val, datetime):
                val = val.strftime("%d/%m/%Y %H:%M")
            elif val is None:
                val = ""

            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = data_font
            cell.border = thin_border
            if isinstance(val, (int, float)):
                cell.alignment = Alignment(horizontal="right", vertical="center")
            else:
                cell.alignment = left_align

    # 3. Auto-adjust column widths
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            max_len = max(max_len, len(val_str))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def get_kardex_report_data(
    user,
    start_date=None,
    end_date=None,
    region_id=None,
    warehouse=None,
    condition=None,
    model_id=None,
    serial_number=None,
) -> QuerySet[InventoryMovement]:
    """Retrieves scoped and filtered Kardex movements."""
    if not user or not user.is_authenticated:
        return InventoryMovement.objects.none()

    qs = InventoryMovement.objects.select_related(
        "equipment_model", "region", "created_by", "item", "case"
    )

    if not (user.is_superuser or getattr(user, "has_global_scope", False)):
        allowed_regions = user.allowed_regions()
        qs = qs.filter(region__in=allowed_regions)

    if region_id:
        qs = qs.filter(region_id=region_id)
    if start_date:
        qs = qs.filter(moved_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(moved_at__date__lte=end_date)
    if warehouse:
        qs = qs.filter(warehouse=warehouse)
    if condition:
        qs = qs.filter(condition=condition)
    if model_id:
        qs = qs.filter(equipment_model_id=model_id)
    if serial_number:
        qs = qs.filter(serial_number__icontains=serial_number.strip())

    return qs.order_by("-moved_at")


def get_stock_balances_summary(user, region_id=None, warehouse=None) -> list[dict[str, Any]]:
    """
    Consolidates stock balances grouped by (equipment_model, region, warehouse, condition).
    """
    if not user or not user.is_authenticated:
        return []

    qs = InventoryMovement.objects.filter(confirmed=True).select_related("equipment_model", "region")

    if not (user.is_superuser or getattr(user, "has_global_scope", False)):
        allowed_regions = user.allowed_regions()
        qs = qs.filter(region__in=allowed_regions)

    if region_id:
        qs = qs.filter(region_id=region_id)
    if warehouse:
        qs = qs.filter(warehouse=warehouse)

    grouped = qs.values(
        "equipment_model__id",
        "equipment_model__name",
        "equipment_model__brand",
        "equipment_model__model",
        "region__id",
        "region__code",
        "region__name",
        "warehouse",
        "condition",
    ).annotate(
        total_balance=Sum(
            Case(
                When(movement_type=InventoryMovement.MovementType.ENTRADA, then="quantity"),
                When(movement_type=InventoryMovement.MovementType.SALIDA, then=-1 * F("quantity")),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
    ).order_by("region__code", "equipment_model__name")

    return list(grouped)


def get_vouchers_report_data(
    user,
    start_date=None,
    end_date=None,
    region_id=None,
    status=None,
    origin_type=None,
) -> QuerySet[Voucher]:
    """Retrieves scoped and filtered vouchers for history reporting."""
    if not user or not user.is_authenticated:
        return Voucher.objects.none()

    qs = Voucher.objects.select_related(
        "requested_by", "region", "destination_center", "reason", "material_category"
    ).prefetch_related("lines", "items")

    if not (user.is_superuser or getattr(user, "has_global_scope", False)):
        allowed_regions = user.allowed_regions()
        qs = qs.filter(region__in=allowed_regions)

    if region_id:
        qs = qs.filter(region_id=region_id)
    if start_date:
        qs = qs.filter(created_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__date__lte=end_date)
    if status:
        qs = qs.filter(status=status)
    if origin_type:
        qs = qs.filter(origin_type=origin_type)

    return qs.order_by("-created_at")


def get_workshop_cases_report_data(
    user,
    start_date=None,
    end_date=None,
    workshop_region_id=None,
    stage=None,
    engineer_id=None,
) -> QuerySet[EquipmentCase]:
    """Retrieves scoped workshop cases with performance metrics."""
    if not user or not user.is_authenticated:
        return EquipmentCase.objects.none()

    qs = EquipmentCase.objects.select_related(
        "origin_region", "workshop_region", "returned_model", "assigned_engineer", "received_by"
    )

    if not (user.is_superuser or getattr(user, "has_global_scope", False)):
        allowed_regions = user.allowed_regions()
        qs = qs.filter(Q(origin_region__in=allowed_regions) | Q(workshop_region__in=allowed_regions))

    if workshop_region_id:
        qs = qs.filter(workshop_region_id=workshop_region_id)
    if start_date:
        qs = qs.filter(created_at__date__gte=start_date)
    if end_date:
        qs = qs.filter(created_at__date__lte=end_date)
    if stage:
        qs = qs.filter(stage=stage)
    if engineer_id:
        qs = qs.filter(assigned_engineer_id=engineer_id)

    return qs.order_by("-created_at")
