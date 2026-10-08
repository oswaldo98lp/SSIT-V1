"""Views for Voucher management, Dispatching, Coupa consumption and PDF downloads."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import CreateView, DetailView, ListView, View

from apps.core.models import CoreEvent
from apps.documents.services import generate_voucher_pdf, save_base64_signature
from apps.inventory.models import EquipmentModel, InventoryItem
from apps.org.selectors import get_user_allowed_regions
from apps.transitions.services import apply_transition, get_available_transitions
from apps.vouchers.forms import (
    CoupaConsumptionForm,
    VoucherCreateForm,
    VoucherLineFormSet,
)
from apps.vouchers.models import Voucher, VoucherLine
from apps.vouchers.selectors import get_vouchers_for_user

User = get_user_model()


class VoucherListView(LoginRequiredMixin, ListView):
    """
    Pantalla 3: Lista de vales con filtros por estatus, región, folio y solicitante.
    """
    model = Voucher
    template_name = "vouchers/voucher_list.html"
    context_object_name = "vouchers"
    paginate_by = 25

    def get_queryset(self):
        user = self.request.user
        qs = get_vouchers_for_user(user)

        # Filtros
        status = self.request.GET.get("status")
        region_code = self.request.GET.get("region")
        folio = self.request.GET.get("folio")
        origin_type = self.request.GET.get("origin_type")

        if status:
            qs = qs.filter(status=status)
        if region_code:
            qs = qs.filter(region__code=region_code)
        if folio:
            qs = qs.filter(report_folio__icontains=folio.strip())
        if origin_type:
            qs = qs.filter(origin_type=origin_type)

        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["allowed_regions"] = get_user_allowed_regions(self.request.user)
        context["selected_status"] = self.request.GET.get("status", "")
        context["selected_region"] = self.request.GET.get("region", "")
        context["selected_folio"] = self.request.GET.get("folio", "")
        context["selected_origin"] = self.request.GET.get("origin_type", "")
        return context


class VoucherCreateView(LoginRequiredMixin, CreateView):
    """
    Pantalla 3: Alta de vale de salida con partidas dinámicas.
    Emite advertencia no bloqueante si el folio de reporte ya existe.
    """
    model = Voucher
    form_class = VoucherCreateForm
    template_name = "vouchers/voucher_create.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context["lines_formset"] = VoucherLineFormSet(self.request.POST)
        else:
            context["lines_formset"] = VoucherLineFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        lines_formset = context["lines_formset"]

        if not lines_formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        report_folio = form.cleaned_data.get("report_folio", "").strip()

        # Advertencia no bloqueante si el folio de reporte ya existe
        if report_folio and Voucher.objects.filter(report_folio__iexact=report_folio).exists():
            messages.warning(
                self.request,
                f"Aviso: El folio de reporte '{report_folio}' ya se encuentra registrado en otro vale anterior.",
            )

        with transaction.atomic():
            voucher = form.save(commit=False)
            voucher.requested_by = self.request.user
            voucher.region = self.request.user.region or (
                voucher.destination_center.region if voucher.destination_center else None
            )
            voucher.status = Voucher.Status.PENDIENTE_SURTIDO
            voucher.save()

            lines_formset.instance = voucher
            lines_formset.save()

            # Registrar evento de auditoría inicial
            CoreEvent.objects.create(
                entity_type="Voucher",
                entity_id=voucher.id,
                action_code="create_voucher",
                from_stage="",
                to_stage="PENDIENTE_SURTIDO",
                outcome=CoreEvent.Outcome.CONFIRMED,
                user=self.request.user,
                comment=voucher.comments,
            )

        messages.success(self.request, f"¡Vale #{voucher.id} creado exitosamente!")
        return redirect("vouchers:detail", pk=voucher.id)


class VoucherDetailView(LoginRequiredMixin, DetailView):
    """
    Pantalla 3: Detalle de vale con línea de tiempo de eventos y acciones disponibles.
    """
    model = Voucher
    template_name = "vouchers/voucher_detail.html"
    context_object_name = "voucher"

    def get_queryset(self):
        return get_vouchers_for_user(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        voucher = self.object
        context["lines"] = voucher.lines.select_related("equipment_model").all()
        context["items"] = voucher.items.select_related("equipment_model").all()
        context["events"] = CoreEvent.objects.filter(
            entity_type="Voucher",
            entity_id=voucher.id,
        ).order_by("created_at")
        context["available_transitions"] = get_available_transitions(self.request.user, voucher)
        return context


class VoucherDispatchView(LoginRequiredMixin, View):
    """
    Pantalla 4: Surtido de vales en Almacén con captura de números de serie,
    condición, almacén, firma y generación de PDF.
    """
    template_name = "vouchers/voucher_dispatch.html"

    def get(self, request, pk):
        voucher = get_object_or_404(get_vouchers_for_user(request.user), pk=pk)

        if voucher.status != Voucher.Status.PENDIENTE_SURTIDO:
            messages.error(request, "Este vale no se encuentra en estado pendiente de surtido.")
            return redirect("vouchers:detail", pk=voucher.id)

        lines = voucher.lines.filter(status=VoucherLine.LineStatus.PENDIENTE).select_related("equipment_model")
        users = User.objects.filter(is_active=True).order_by("full_name")

        return render(
            request,
            self.template_name,
            {
                "voucher": voucher,
                "lines": lines,
                "users": users,
            },
        )

    def post(self, request, pk):
        voucher = get_object_or_404(get_vouchers_for_user(request.user), pk=pk)

        received_by_id = request.POST.get("received_by_id")
        signature_data = request.POST.get("signature_data", "")
        comments = request.POST.get("comments", "")

        # Recolectar datos de piezas y series capturadas
        items_data = []
        for key, val in request.POST.items():
            if key.startswith("serial_number_") and val.strip():
                line_id = key.replace("serial_number_", "")
                line = voucher.lines.filter(id=line_id).first()
                condition = request.POST.get(f"condition_{line_id}", InventoryItem.Condition.RECUPERADO)
                warehouse = request.POST.get(f"warehouse_{line_id}", InventoryItem.Warehouse.STOCK)
                items_data.append({
                    "line_id": int(line_id),
                    "model_id": line.equipment_model_id if line else None,
                    "serial_number": val.strip(),
                    "condition": condition,
                    "warehouse": warehouse,
                })

        if not items_data:
            messages.error(request, "Debes capturar al menos un número de serie para surtir el vale.")
            return redirect("vouchers:dispatch", pk=voucher.id)

        # 1. Guardar firma si fue capturada
        if signature_data:
            save_base64_signature(signature_data, voucher)

        # 2. Ejecutar la transición declarativa dispatch_voucher
        apply_transition(
            request.user,
            voucher,
            "dispatch_voucher",
            {
                "received_by_id": int(received_by_id) if received_by_id else request.user.id,
                "items_data": items_data,
                "comments": comments,
            },
        )

        # 3. Generar PDF de vale oficial
        generate_voucher_pdf(voucher, requesting_user=request.user)

        messages.success(
            request,
            f"¡Vale #{voucher.id} surtido con éxito! Se registraron {len(items_data)} piezas y se generó el PDF de salida.",
        )
        return redirect("vouchers:detail", pk=voucher.id)


class CoupaConsumptionCreateView(LoginRequiredMixin, CreateView):
    """
    Flujo Coupa: Registro directo de consumo Coupa con series y Kárdex.
    """
    model = Voucher
    form_class = CoupaConsumptionForm
    template_name = "vouchers/coupa_create.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["equipment_models"] = EquipmentModel.objects.filter(is_inventoriable=True).order_by("name")
        return context

    def form_valid(self, form):
        with transaction.atomic():
            voucher = form.save(commit=False)
            voucher.origin_type = Voucher.OriginType.COUPA
            voucher.requested_by = self.request.user
            voucher.region = self.request.user.region or voucher.destination_center.region
            voucher.status = Voucher.Status.SURTIDO
            voucher.authorized_by = self.request.user
            voucher.delivered_by = self.request.user
            voucher.save()

            # Capturar líneas y series
            serials = self.request.POST.getlist("serial_numbers[]")
            model_ids = self.request.POST.getlist("model_ids[]")

            for model_id, serial in zip(model_ids, serials, strict=False):
                if serial.strip() and model_id:
                    line = VoucherLine.objects.create(
                        voucher=voucher,
                        equipment_model_id=int(model_id),
                        quantity=1,
                        status=VoucherLine.LineStatus.SURTIDO,
                    )
                    item = InventoryItem.objects.create(
                        voucher=voucher,
                        line=line,
                        equipment_model_id=int(model_id),
                        serial_number=serial.strip(),
                        condition=InventoryItem.Condition.NUEVO,
                        warehouse=InventoryItem.Warehouse.STOCK,
                        region=voucher.region,
                    )
                    # Kárdex
                    from django.utils import timezone

                    from apps.inventory.models import InventoryMovement
                    InventoryMovement.objects.create(
                        movement_type=InventoryMovement.MovementType.SALIDA,
                        equipment_model_id=int(model_id),
                        serial_number=item.serial_number,
                        condition=item.condition,
                        warehouse=item.warehouse,
                        region=voucher.region,
                        quantity=1,
                        moved_at=timezone.now(),
                        transfer_folio=f"COUPA-{voucher.coupa_id}",
                        item=item,
                        confirmed=True,
                        created_by=self.request.user,
                    )

            # Generar PDF
            generate_voucher_pdf(voucher, requesting_user=self.request.user)

        messages.success(self.request, f"¡Consumo Coupa #{voucher.coupa_id} registrado y surtido correctamente!")
        return redirect("vouchers:detail", pk=voucher.id)


class VoucherPdfDownloadView(LoginRequiredMixin, View):
    """Permite visualizar o descargar el PDF generado de un vale."""
    def get(self, request, pk):
        voucher = get_object_or_404(get_vouchers_for_user(request.user), pk=pk)
        if not voucher.pdf_file:
            # Si aún no existe, generarlo bajo demanda
            generate_voucher_pdf(voucher, requesting_user=request.user)

        if not voucher.pdf_file:
            raise Http404("El archivo PDF del vale no está disponible.")

        return FileResponse(voucher.pdf_file.open("rb"), content_type="application/pdf")
