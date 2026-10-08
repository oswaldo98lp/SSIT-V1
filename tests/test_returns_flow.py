"""Tests for Phase 5 - Flujo B: Devoluciones, Dictamen de Almacén, Folios y PDF con QR."""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse

from apps.cases.models import EquipmentCase
from apps.catalog.models import CatalogValue
from apps.core.models import CoreEvent
from apps.documents.services import generate_return_pdf
from apps.inventory.models import EquipmentModel
from apps.org.models import Region
from apps.transitions.services import sync_transitions_to_db

User = get_user_model()


@pytest.fixture(autouse=True)
def setup_flow_b_data():
    call_command("seed_roles")
    call_command("seed_catalogs")
    call_command("seed_org")
    call_command("seed_demo")
    sync_transitions_to_db()


@pytest.mark.django_db
class TestReturnsAndWarehouseFlow:
    """Test suite for returns creation, warehouse ruling, review request and repair folios."""

    def test_case_return_creation_flow(self, client):
        user_soporte = User.objects.get(email="soporte.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model_lap = EquipmentModel.objects.first()

        client.force_login(user_soporte)

        url = reverse("cases:case_create")
        payload = {
            "origin_region": reg_oaxc.id,
            "returned_model": model_lap.id,
            "returned_serial": "sn-ret-1001",
            "returned_brand": "Lenovo",
            "route": EquipmentCase.Route.EVALUACION_CENTRO,
            "shipping_type": EquipmentCase.ShippingType.FISICO,
            "shipping_folio": "EM-2026-0099",
            "failure": "Falla en tarjeta madre no enciende",
        }

        response = client.post(url, payload, follow=True)
        assert response.status_code == 200

        case = EquipmentCase.objects.get(returned_serial="SN-RET-1001")
        assert case.stage == "PENDIENTE_CONFIRMAR"
        assert case.origin_region == reg_oaxc
        assert case.shipping_folio == "EM-2026-0099"
        assert case.return_pdf is not None
        assert case.return_qr is not None

        # Verify CoreEvent audit
        event = CoreEvent.objects.filter(entity_type="EquipmentCase", entity_id=case.id).first()
        assert event is not None
        assert event.action_code == "register_return"
        assert event.to_stage == "PENDIENTE_CONFIRMAR"

    def test_warehouse_diagnosis_confirmation_flow(self, client):
        user_almacen = User.objects.get(email="almacen.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model_lap = EquipmentModel.objects.first()
        ruling_rep = CatalogValue.objects.filter(catalog="RULING").first()

        # Crear caso inicial
        case = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            returned_model=model_lap,
            returned_serial="SN-RET-1002",
            route=EquipmentCase.Route.EVALUACION_CENTRO,
            stage="PENDIENTE_CONFIRMAR",
        )

        client.force_login(user_almacen)
        dictamen_url = reverse("cases:warehouse_dictamen", kwargs={"pk": case.id})
        payload = {
            "ruling": ruling_rep.id,
            "returned_model": model_lap.id,
            "comments": "Equipo recibido con daño físico, enviado a taller.",
        }

        response = client.post(dictamen_url, payload, follow=True)
        assert response.status_code == 200

        case.refresh_from_db()
        assert case.stage == "CONFIRMADO"
        assert case.ruling == ruling_rep
        assert case.received_by == user_almacen
        assert case.return_status == "CONFIRMADO"

    def test_request_return_review_flow(self, client):
        user_almacen = User.objects.get(email="almacen.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model_lap = EquipmentModel.objects.first()

        case = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            returned_model=model_lap,
            returned_serial="SN-RET-1003",
            route=EquipmentCase.Route.EVALUACION_CENTRO,
            stage="PENDIENTE_CONFIRMAR",
        )

        client.force_login(user_almacen)
        review_url = reverse("cases:request_review", kwargs={"pk": case.id})
        payload = {
            "review_reason": "Serie no coincide con el número de parte físico recibido.",
        }

        response = client.post(review_url, payload, follow=True)
        assert response.status_code == 200

        case.refresh_from_db()
        assert case.stage == "EN_REVISION"
        assert case.return_status == "EN_REVISION"
        assert "Serie no coincide" in case.review_reason

    def test_assign_repair_folio_flow(self, client):
        user_oficina = User.objects.get(email="oficina.central@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model_lap = EquipmentModel.objects.first()
        ruling_rep = CatalogValue.objects.filter(catalog="RULING").first()

        case = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            returned_model=model_lap,
            returned_serial="SN-RET-1004",
            ruling=ruling_rep,
            stage="CONFIRMADO",
        )

        client.force_login(user_oficina)
        folio_url = reverse("cases:assign_repair_folio", kwargs={"pk": case.id})
        payload = {
            "repair_folio": "FOL-REP-2026-088",
            "folio_date": "2026-10-15",
        }

        response = client.post(folio_url, payload, follow=True)
        assert response.status_code == 200

        case.refresh_from_db()
        assert case.repair_folio == "FOL-REP-2026-088"
        assert str(case.folio_date) == "2026-10-15"

    def test_generate_return_pdf_service(self):
        user_almacen = User.objects.get(email="almacen.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model_lap = EquipmentModel.objects.first()

        case = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            returned_model=model_lap,
            returned_serial="SN-RET-1005",
            shipping_folio="EM-2026-0055",
            stage="CONFIRMADO",
        )

        doc = generate_return_pdf(case, requesting_user=user_almacen)
        case.refresh_from_db()

        assert doc is not None
        assert case.return_pdf is not None
        assert case.return_qr is not None
        assert doc.file == case.return_pdf
