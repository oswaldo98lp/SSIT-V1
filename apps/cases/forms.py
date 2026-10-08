"""Forms for Equipment Cases: Returns, Diagnosis, Workshop, and Repair Folios."""
from django import forms

from apps.catalog.models import CatalogValue
from apps.inventory.models import EquipmentModel, InventoryItem
from apps.org.models import Region
from apps.org.selectors import get_user_allowed_regions
from .models import EquipmentCase


class CaseReturnForm(forms.ModelForm):
    """Formulario para registro de devolución desde centro o almacén."""

    item_id = forms.IntegerField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = EquipmentCase
        fields = [
            "origin_region",
            "returned_model",
            "returned_brand",
            "returned_serial",
            "route",
            "shipping_type",
            "shipping_folio",
            "stock_direct_reason",
            "applies_workshop_entry",
            "applies_reason",
            "failure",
        ]
        widgets = {
            "origin_region": forms.Select(attrs={"class": "form-select"}),
            "returned_model": forms.Select(attrs={"class": "form-select"}),
            "returned_brand": forms.TextInput(attrs={"class": "form-control", "placeholder": "Marca del equipo"}),
            "returned_serial": forms.TextInput(attrs={"class": "form-control font-monospace", "placeholder": "Número de serie devuelto"}),
            "route": forms.Select(attrs={"class": "form-select"}),
            "shipping_type": forms.Select(attrs={"class": "form-select"}),
            "shipping_folio": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ej. EM-2026-001 o Guía de paquetería"}),
            "stock_direct_reason": forms.Select(attrs={"class": "form-select"}),
            "applies_workshop_entry": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "applies_reason": forms.Select(attrs={"class": "form-select"}),
            "failure": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Describa la falla u observación técnica..."}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            self.fields["origin_region"].queryset = get_user_allowed_regions(user)
            if user.region and not self.initial.get("origin_region"):
                self.initial["origin_region"] = user.region

        self.fields["returned_model"].queryset = EquipmentModel.objects.all().order_by("name")
        self.fields["stock_direct_reason"].queryset = CatalogValue.objects.filter(catalog="STOCK_DIRECT_REASON", is_active=True)
        self.fields["applies_reason"].queryset = CatalogValue.objects.filter(catalog="APPLIES_REASON", is_active=True)

    def clean_returned_serial(self):
        serial = self.cleaned_data.get("returned_serial", "").strip().upper()
        if not serial:
            raise forms.ValidationError("El número de serie es obligatorio.")
        return serial

    def clean(self):
        cleaned_data = super().clean()
        route = cleaned_data.get("route")
        stock_direct_reason = cleaned_data.get("stock_direct_reason")
        applies_workshop_entry = cleaned_data.get("applies_workshop_entry")
        applies_reason = cleaned_data.get("applies_reason")

        if route == EquipmentCase.Route.STOCK_DIRECTO and not stock_direct_reason:
            self.add_error("stock_direct_reason", "Debe indicar el motivo para ruta Stock Directo.")

        if applies_workshop_entry and not applies_reason:
            self.add_error("applies_reason", "Indique el motivo por el que aplica a taller.")

        return cleaned_data


class WarehouseDiagnosisForm(forms.Form):
    """Formulario para dictamen de devolución por parte de Almacén."""

    ruling = forms.ModelChoiceField(
        queryset=CatalogValue.objects.filter(catalog="RULING", is_active=True),
        label="Dictamen de Almacén",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    returned_model = forms.ModelChoiceField(
        queryset=EquipmentModel.objects.all().order_by("name"),
        label="Modelo Confirmado",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    comments = forms.CharField(
        label="Observaciones de recepción",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Comentarios de inspección física..."}),
    )


class ReturnReviewRequestForm(forms.Form):
    """Formulario para solicitar revisión / re-evaluación de devolución."""

    review_reason = forms.CharField(
        label="Motivo de la solicitud de revisión",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Especifique el motivo por el cual no coincide o requiere aclaración..."}),
    )


class RepairFolioAssignForm(forms.Form):
    """Formulario para asignación de folio de reparación en Oficina."""

    repair_folio = forms.CharField(
        max_length=64,
        label="Folio de Reparación",
        widget=forms.TextInput(attrs={"class": "form-control font-monospace", "placeholder": "Ej. FOL-REP-2026-0042"}),
    )
    folio_date = forms.DateField(
        label="Fecha del Folio",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    insight_note = forms.ModelChoiceField(
        queryset=CatalogValue.objects.filter(catalog="INSIGHT_NOTE", is_active=True),
        label="Nota Insight (Opcional)",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class AssignEngineerForm(forms.Form):
    """Formulario para asignar ingeniero técnico al caso."""

    assigned_engineer = forms.ModelChoiceField(
        queryset=None,
        label="Ingeniero de Taller Asignado",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        from apps.accounts.models import User
        super().__init__(*args, **kwargs)
        self.fields["assigned_engineer"].queryset = User.objects.filter(
            is_active=True, groups__name__in=["SOPORTE_TALLER", "JEFE_TALLER", "SOPORTE_TI"]
        ).order_by("full_name")


class TechnicalDiagnosisForm(forms.Form):
    """Formulario para dictamen y definición técnica en Taller."""

    definition = forms.ChoiceField(
        choices=EquipmentCase.Definition.choices,
        label="Definición Técnica",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    repair_comments = forms.CharField(
        label="Comentarios Técnicos / Trabajos Realizados",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Detalle de pruebas, cambio de componentes, etc."}),
    )
    warranty_solution = forms.ChoiceField(
        choices=[("", "--- Ninguna ---")] + EquipmentCase.WarrantySolution.choices,
        label="Solución de Garantía (si aplica)",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    new_serial = forms.CharField(
        max_length=128,
        label="Nueva Serie (si fue cambio de equipo)",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control font-monospace", "placeholder": "S/N del nuevo equipo"}),
    )
    insight_repair_confirmed = forms.BooleanField(
        label="Confirmar registro en Insight",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class WarehouseEntryConfirmForm(forms.Form):
    """Formulario para ingreso final a almacén tras reparación o dictamen."""

    destination_warehouse = forms.CharField(
        max_length=32,
        initial="STOCK",
        label="Almacén Destino",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "STOCK / HUESARIO / etc."}),
    )
    comments = forms.CharField(
        label="Comentarios de ingreso",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Notas de reingreso a almacén..."}),
    )


class ScrapActionForm(forms.Form):
    """Formulario para confirmación, entrega o reversión de Huesario."""

    comments = forms.CharField(
        label="Comentarios / Justificación",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Motivo o notas de la acción de huesario..."}),
    )


class WorkshopSendForm(forms.Form):
    """Formulario para enviar equipo a Taller Habilitado."""

    workshop_region = forms.ModelChoiceField(
        queryset=Region.objects.all().order_by("name"),
        label="Región del Taller Habilitado",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    shipping_folio = forms.CharField(
        max_length=64,
        label="Folio de Envío (Guía / EM / SA)",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "EM-12345 / Guía paquetería"}),
    )
    comments = forms.CharField(
        label="Comentarios de envío",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Instrucciones o notas para el taller..."}),
    )


class WorkshopEntryConfirmForm(forms.Form):
    """Formulario para que el Jefe de Taller confirme recepción física del equipo."""

    returned_model = forms.ModelChoiceField(
        queryset=EquipmentModel.objects.all().order_by("name"),
        label="Modelo Verificado en Taller",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    comments = forms.CharField(
        label="Notas de recepción",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Condiciones físicas de llegada..."}),
    )


class WorkshopReviewRequestForm(forms.Form):
    """Formulario para solicitar revisión técnica en taller."""

    review_reason = forms.CharField(
        label="Motivo de Revisión",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Detalle el motivo por el cual el equipo entra en revisión..."}),
    )


class WorkshopWaitPartsForm(forms.Form):
    """Formulario para pausar equipo en espera de refacciones."""

    comments = forms.CharField(
        label="Refacciones Faltantes / Notas",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Piezas solicitadas para continuar la reparación..."}),
    )


class CancelReturnForm(forms.Form):
    """Formulario para que el centro cancele una devolución."""

    cancel_reason = forms.CharField(
        label="Motivo de Cancelación",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Especifique el motivo por el cual se cancela la devolución..."}),
    )


class ManagerCancellationForm(forms.Form):
    """Formulario para que el Gerente valide o rechace cancelación."""

    cancel_reason = forms.ModelChoiceField(
        queryset=CatalogValue.objects.filter(catalog="MANAGER_CANCEL_REASON", is_active=True).order_by("sort"),
        label="Motivo de Validación Gerencial",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    comments = forms.CharField(
        label="Comentarios",
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )

