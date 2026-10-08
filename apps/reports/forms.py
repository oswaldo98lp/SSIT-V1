"""Filter forms for Kárdex, Balances, Vouchers, and Workshop Reports."""
from django import forms

from apps.catalog.models import CatalogValue
from apps.inventory.models import EquipmentModel, InventoryItem, InventoryMovement
from apps.org.models import Region, Zone
from apps.vouchers.models import Voucher


class KardexFilterForm(forms.Form):
    """Filtros para la consulta y exportación del Kárdex."""
    start_date = forms.DateField(
        label="Fecha Inicio",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    end_date = forms.DateField(
        label="Fecha Fin",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    region = forms.ModelChoiceField(
        queryset=Region.objects.all().order_by("name"),
        label="Región",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    warehouse = forms.ChoiceField(
        choices=[("", "--- Todos los Almacenes ---")] + InventoryItem.Warehouse.choices,
        label="Almacén",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    condition = forms.ChoiceField(
        choices=[("", "--- Todas las Condiciones ---")] + InventoryItem.Condition.choices,
        label="Condición",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    model = forms.ModelChoiceField(
        queryset=EquipmentModel.objects.all().order_by("name"),
        label="Modelo de Equipo",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    serial_number = forms.CharField(
        label="Número de Serie",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Buscar serie..."}),
    )


class StockBalanceFilterForm(forms.Form):
    """Filtro de existencias por región y almacén."""
    region = forms.ModelChoiceField(
        queryset=Region.objects.all().order_by("name"),
        label="Región",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    warehouse = forms.ChoiceField(
        choices=[("", "--- Todos los Almacenes ---")] + InventoryItem.Warehouse.choices,
        label="Almacén",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class VoucherReportFilterForm(forms.Form):
    """Filtros para bitácora histórica de vales."""
    start_date = forms.DateField(
        label="Fecha Inicio",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    end_date = forms.DateField(
        label="Fecha Fin",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    region = forms.ModelChoiceField(
        queryset=Region.objects.all().order_by("name"),
        label="Región",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    status = forms.ChoiceField(
        choices=[("", "--- Todos los Estatus ---")] + Voucher.Status.choices,
        label="Estatus de Vale",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    origin_type = forms.ChoiceField(
        choices=[("", "--- Todo Origen ---")] + Voucher.OriginType.choices,
        label="Tipo de Origen",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class WorkshopReportFilterForm(forms.Form):
    """Filtros para bitácora y reporte de taller habilitado."""
    start_date = forms.DateField(
        label="Fecha Inicio",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    end_date = forms.DateField(
        label="Fecha Fin",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    workshop_region = forms.ModelChoiceField(
        queryset=Region.objects.filter(is_workshop=True).order_by("name"),
        label="Taller Habilitado",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    stage = forms.ChoiceField(
        choices=[
            ("", "--- Todas las Etapas ---"),
            ("EN_TRANSITO_TALLER", "En Tránsito a Taller"),
            ("EN_TALLER", "En Taller"),
            ("ASIGNADO", "Asignado a Técnico"),
            ("EN_ESPERA_REFACCION", "En Espera de Refacción"),
            ("DEFINIDO", "Definido por Técnico"),
            ("CONFIRMADO_JEFE", "Confirmado por Jefe"),
            ("FINALIZADO", "Finalizado con Entrada a Almacén"),
        ],
        label="Etapa de Taller",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class ZoneReportFilterForm(forms.Form):
    """Filtro para consolidado de zona."""
    zone = forms.ModelChoiceField(
        queryset=Zone.objects.all().order_by("name"),
        label="Zona",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
