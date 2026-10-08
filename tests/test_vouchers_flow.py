"""Comprehensive tests for Flow A: Vouchers, Dispatching, Coupa, Kardex, PDF and Signatures."""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import CatalogValue
from apps.documents.models import Document
from apps.inventory.models import EquipmentModel, InventoryItem, InventoryMovement
from apps.org.models import Center, Region
from apps.transitions.services import sync_transitions_to_db
from apps.vouchers.models import Voucher, VoucherLine

User = get_user_model()

# Dummy base64 1x1 PNG image data URL
DUMMY_SIGNATURE_DATA_URL = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@pytest.fixture(autouse=True)
def setup_flow_a_data():
    call_command("seed_roles")
    call_command("seed_catalogs")
    call_command("seed_org")
    call_command("seed_demo")
    sync_transitions_to_db()


@pytest.mark.django_db
class TestVouchersFlowA:
    def test_voucher_list_view_and_filtering(self, client):
        user_soporte = User.objects.get(email="soporte.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")

        Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            report_folio="FOLIO-A1",
            requested_by=user_soporte,
            region=reg_oaxc,
            status=Voucher.Status.PENDIENTE_SURTIDO,
        )
        Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            report_folio="FOLIO-A2",
            requested_by=user_soporte,
            region=reg_oaxc,
            status=Voucher.Status.SURTIDO,
        )

        client.force_login(user_soporte)
        url = reverse("vouchers:list")

        # Sin filtros
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "FOLIO-A1" in content
        assert "FOLIO-A2" in content

        # Filtrado por estatus
        response_filtered = client.get(url, {"status": "SURTIDO"})
        assert response_filtered.status_code == 200
        content_filtered = response_filtered.content.decode("utf-8")
        assert "FOLIO-A2" in content_filtered
        assert "FOLIO-A1" not in content_filtered

    def test_voucher_create_view_with_lines_and_duplicate_warning(self, client):
        user_soporte = User.objects.get(email="soporte.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        center_oaxc = Center.objects.filter(region=reg_oaxc).first()
        reason = CatalogValue.objects.filter(catalog="REQUEST_REASON").first()
        model_pos = EquipmentModel.objects.first()

        client.force_login(user_soporte)
        create_url = reverse("vouchers:create")

        # 1. Crear primer vale con folio "TICKET-100"
        post_data_1 = {
            "report_folio": "TICKET-100",
            "destination_center": center_oaxc.id,
            "reason": reason.id,
            "shipping_type": "FISICO",
            "lines-TOTAL_FORMS": "2",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-equipment_model": model_pos.id,
            "lines-0-quantity": "1",
            "lines-1-requested_text": "Cable de red blindado 10m",
            "lines-1-quantity": "2",
        }
        response_1 = client.post(create_url, post_data_1, follow=True)
        assert response_1.status_code == 200
        v1 = Voucher.objects.get(report_folio="TICKET-100")
        assert v1.lines.count() == 2
        assert v1.status == Voucher.Status.PENDIENTE_SURTIDO

        # 2. Crear segundo vale con el MISMO folio "TICKET-100" para verificar la advertencia no bloqueante
        post_data_2 = {
            "report_folio": "TICKET-100",
            "destination_center": center_oaxc.id,
            "reason": reason.id,
            "shipping_type": "FISICO",
            "lines-TOTAL_FORMS": "1",
            "lines-INITIAL_FORMS": "0",
            "lines-MIN_NUM_FORMS": "0",
            "lines-MAX_NUM_FORMS": "1000",
            "lines-0-equipment_model": model_pos.id,
            "lines-0-quantity": "1",
        }
        response_2 = client.post(create_url, post_data_2, follow=True)
        assert response_2.status_code == 200
        # Debe crearse el segundo vale exitosamente (no bloqueante) y mostrar el mensaje de advertencia
        assert Voucher.objects.filter(report_folio="TICKET-100").count() == 2
        content_2 = response_2.content.decode("utf-8")
        assert "Aviso: El folio de reporte" in content_2

    def test_voucher_dispatch_flow_with_signature_and_pdf(self, client):
        user_soporte = User.objects.get(email="soporte.oaxc@test-ssit.local")
        user_jefe = User.objects.get(email="jefe.oaxc@test-ssit.local")
        user_almacen = User.objects.get(email="almacen.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        center_oaxc = Center.objects.filter(region=reg_oaxc).first()
        model_pos = EquipmentModel.objects.first()

        voucher = Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            report_folio="TICKET-DISPATCH-99",
            destination_center=center_oaxc,
            requested_by=user_soporte,
            region=reg_oaxc,
            status=Voucher.Status.PENDIENTE_SURTIDO,
            authorized_by=user_jefe,
            authorized_at=timezone.now(),
        )
        line = VoucherLine.objects.create(
            voucher=voucher,
            equipment_model=model_pos,
            quantity=1,
            status=VoucherLine.LineStatus.PENDIENTE,
        )

        client.force_login(user_almacen)
        dispatch_url = reverse("vouchers:dispatch", kwargs={"pk": voucher.id})

        # GET dispatch form
        response_get = client.get(dispatch_url)
        assert response_get.status_code == 200
        assert "Surtido de Material" in response_get.content.decode("utf-8")

        # POST dispatch with serial and signature
        post_data = {
            f"serial_number_{line.id}": "EPSON-SER-99001",
            f"condition_{line.id}": "NUEVO",
            f"warehouse_{line.id}": "STOCK",
            "received_by_id": user_soporte.id,
            "signature_data": DUMMY_SIGNATURE_DATA_URL,
            "comments": "Surtido completo en ventanilla.",
        }
        response_post = client.post(dispatch_url, post_data, follow=True)
        assert response_post.status_code == 200

        voucher.refresh_from_db()
        assert voucher.status == Voucher.Status.SURTIDO
        assert voucher.delivered_by == user_almacen
        assert voucher.received_by == user_soporte
        assert voucher.signature_image is not None
        assert voucher.pdf_file is not None

        # Verificar InventoryItem y Kárdex
        item = InventoryItem.objects.get(serial_number="EPSON-SER-99001")
        assert item.condition == "NUEVO"
        assert item.region == reg_oaxc

        kardex = InventoryMovement.objects.get(serial_number="EPSON-SER-99001")
        assert kardex.movement_type == InventoryMovement.MovementType.SALIDA
        assert kardex.quantity == 1

        # Verificar repositorio Document
        doc = Document.objects.filter(related_type="Voucher", related_id=voucher.id).first()
        assert doc is not None
        assert doc.kind == Document.Kind.VALE_PDF

    def test_coupa_consumption_create_flow(self, client):
        user_almacen = User.objects.get(email="almacen.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        center_oaxc = Center.objects.filter(region=reg_oaxc).first()
        model_pos = EquipmentModel.objects.first()

        client.force_login(user_almacen)
        coupa_url = reverse("vouchers:coupa_create")

        post_data = {
            "coupa_id": "COUPA-REQ-8877",
            "destination_center": center_oaxc.id,
            "shipping_type": "DISTRIBUCION",
            "project_name": "Renovación Cajas 2026",
            "comments": "Entrega por requisición corporativa Coupa",
            "model_ids[]": [str(model_pos.id)],
            "serial_numbers[]": ["COUPA-SER-7744"],
        }
        response = client.post(coupa_url, post_data, follow=True)
        assert response.status_code == 200

        voucher = Voucher.objects.get(coupa_id="COUPA-REQ-8877")
        assert voucher.origin_type == Voucher.OriginType.COUPA
        assert voucher.status == Voucher.Status.SURTIDO

        # Kárdex de salida verificado
        kardex = InventoryMovement.objects.filter(serial_number="COUPA-SER-7744").first()
        assert kardex is not None
        assert kardex.movement_type == InventoryMovement.MovementType.SALIDA

    def test_voucher_pdf_download_view(self, client):
        user_soporte = User.objects.get(email="soporte.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")

        voucher = Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            report_folio="REP-PDF-DOWNLOAD",
            requested_by=user_soporte,
            region=reg_oaxc,
            status=Voucher.Status.SURTIDO,
        )

        client.force_login(user_soporte)
        pdf_url = reverse("vouchers:pdf_download", kwargs={"pk": voucher.id})
        response = client.get(pdf_url)
        assert response.status_code == 200
        assert response.has_header("Content-Type")
