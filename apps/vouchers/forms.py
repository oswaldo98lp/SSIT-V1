"""Forms for Voucher creation, line formsets, dispatching and Coupa consumption."""
from django import forms
from django.forms import inlineformset_factory

from apps.catalog.models import CatalogValue
from apps.inventory.models import EquipmentModel
from apps.vouchers.models import Voucher, VoucherLine


class VoucherCreateForm(forms.ModelForm):
    """Formulario para alta de vale de salida."""
    class Meta:
        model = Voucher
        fields = [
            "report_folio",
            "destination_center",
            "reason",
            "material_category",
            "shipping_type",
            "project_name",
            "comments",
        ]
        widgets = {
            "report_folio": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. TICKET-9921"}),
            "destination_center": forms.Select(attrs={"class": "form-select"}),
            "reason": forms.Select(attrs={"class": "form-select"}),
            "material_category": forms.Select(attrs={"class": "form-select"}),
            "shipping_type": forms.Select(attrs={"class": "form-select"}),
            "project_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Opcional..."}),
            "comments": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Observaciones adicionales..."}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            # Filtrar centros con el alcance del usuario
            from apps.org.selectors import get_user_allowed_centers
            self.fields["destination_center"].queryset = get_user_allowed_centers(user)

        self.fields["reason"].queryset = CatalogValue.objects.filter(catalog="REQUEST_REASON", is_active=True)
        self.fields["material_category"].queryset = CatalogValue.objects.filter(catalog="MATERIAL_CATEGORY", is_active=True)


class VoucherLineForm(forms.ModelForm):
    """Formulario para cada línea de artículo solicitada."""
    class Meta:
        model = VoucherLine
        fields = ["equipment_model", "requested_text", "quantity", "comments"]
        widgets = {
            "equipment_model": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "requested_text": forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "Descripción libre si no está en catálogo"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control form-control-sm", "min": 1, "value": 1}),
            "comments": forms.TextInput(attrs={"class": "form-control form-control-sm", "placeholder": "Notas de la partida"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["equipment_model"].queryset = EquipmentModel.objects.filter(is_inventoriable=True).order_by("name")
        self.fields["equipment_model"].required = False


VoucherLineFormSet = inlineformset_factory(
    Voucher,
    VoucherLine,
    form=VoucherLineForm,
    extra=1,
    can_delete=True,
)


class CoupaConsumptionForm(forms.ModelForm):
    """Formulario para registro de consumo Coupa directo sin vale previo."""
    class Meta:
        model = Voucher
        fields = [
            "coupa_id",
            "destination_center",
            "shipping_type",
            "project_name",
            "comments",
        ]
        widgets = {
            "coupa_id": forms.TextInput(attrs={"class": "form-control", "placeholder": "ID de orden o requisición Coupa (requerido)"}),
            "destination_center": forms.Select(attrs={"class": "form-select"}),
            "shipping_type": forms.Select(attrs={"class": "form-select"}),
            "project_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre del proyecto Coupa"}),
            "comments": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            from apps.org.selectors import get_user_allowed_centers
            self.fields["destination_center"].queryset = get_user_allowed_centers(user)
        self.fields["coupa_id"].required = True
