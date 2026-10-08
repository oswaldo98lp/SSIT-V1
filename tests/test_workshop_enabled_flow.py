"""Tests for Flow D: Taller Habilitado lifecycle (location=TALLER)."""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from apps.cases.models import EquipmentCase
from apps.inventory.models import EquipmentModel, InventoryMovement
from apps.org.models import Region

User = get_user_model()


@pytest.fixture(autouse=True)
def populate_database_seeds():
    call_command("seed_roles")
    call_command("seed_catalogs")
    call_command("seed_org")
    call_command("seed_demo")


@pytest.mark.django_db
class TestWorkshopEnabledFlow:
    def test_send_to_workshop_and_cancel_transfer_flow(self):
        """Flujo D: Enviar caso a Taller Habilitado y cancelar traslado."""
        client = Client()
        wh_user = User.objects.get(email="almacen.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        reg_azcp = Region.objects.get(code="AZCP")
        model = EquipmentModel.objects.first()

        case = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            returned_model=model,
            returned_serial="TRANS-TEST-101",
            location=EquipmentCase.Location.CENTRO,
            stage="CONFIRMADO",
        )

        # 1. Enviar a Taller Habilitado en AZCP
        client.force_login(wh_user)
        resp_send = client.post(
            reverse("cases:send_to_workshop", kwargs={"pk": case.id}),
            {
                "workshop_region": reg_azcp.id,
                "shipping_folio": "GUIA-DHL-8888",
                "comments": "Equipo requiere instrumental de laboratorio",
            },
        )
        assert resp_send.status_code == 302
        case.refresh_from_db()
        assert case.location == EquipmentCase.Location.TALLER
        assert case.workshop_region == reg_azcp
        assert case.stage == "EN_TRANSITO_TALLER"
        assert case.shipping_folio == "GUIA-DHL-8888"

        # 2. Cancelar envío a taller
        resp_cancel = client.get(
            reverse("cases:cancel_workshop_send", kwargs={"pk": case.id})
        )
        assert resp_cancel.status_code == 302
        case.refresh_from_db()
        assert case.location == EquipmentCase.Location.CENTRO
        assert case.workshop_region is None
        assert case.stage == "CONFIRMADO"

    def test_workshop_complete_lifecycle(self):
        """Flujo D: Envío -> Recepción -> Espera de Refacción -> Definición -> Entrada Almacén."""
        client = Client()
        wh_oaxc = User.objects.get(email="almacen.oaxc@test-ssit.local")
        chief_taller = User.objects.get(email="jefe.taller@test-ssit.local")
        tech_taller = User.objects.get(email="soporte.taller@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        reg_azcp = Region.objects.get(code="AZCP")
        model = EquipmentModel.objects.first()

        # Caso en tránsito hacia Taller AZCP
        case = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            workshop_region=reg_azcp,
            returned_model=model,
            returned_serial="TALLER-FULL-202",
            location=EquipmentCase.Location.TALLER,
            stage="EN_TRANSITO_TALLER",
        )

        # 1. Jefe de Taller confirma recepción física
        client.force_login(chief_taller)
        resp_entry = client.post(
            reverse("cases:workshop_confirm_entry", kwargs={"pk": case.id}),
            {"returned_model": model.id, "comments": "Equipo recibido en buen estado"},
        )
        assert resp_entry.status_code == 302
        case.refresh_from_db()
        assert case.stage == "EN_TALLER"

        # 2. Jefe de Taller asigna a técnico
        resp_assign = client.post(
            reverse("cases:assign_engineer", kwargs={"pk": case.id}),
            {"assigned_engineer": tech_taller.id},
        )
        assert resp_assign.status_code == 302
        case.refresh_from_db()
        assert case.stage == "ASIGNADO"
        assert case.assigned_engineer == tech_taller

        # 3. Pausar en espera de refacción
        resp_wait = client.post(
            reverse("cases:workshop_wait_parts", kwargs={"pk": case.id}),
            {"comments": "En espera de diodos y capacitores de potencia"},
        )
        assert resp_wait.status_code == 302
        case.refresh_from_db()
        assert case.stage == "EN_ESPERA_REFACCION"

        # 4. Técnico de Taller define equipo como REPARADO
        client.force_login(tech_taller)
        resp_define = client.post(
            reverse("cases:technical_diagnosis", kwargs={"pk": case.id}),
            {
                "definition": "REPARADO",
                "repair_comments": "Se reemplazaron capacitores y se realizaron pruebas de carga OK",
                "insight_repair_confirmed": True,
            },
        )
        assert resp_define.status_code == 302
        case.refresh_from_db()
        assert case.stage == "DEFINIDO"
        assert case.definition == "REPARADO"

        # 4. Almacén confirma entrada final y genera Kárdex
        client.force_login(wh_oaxc)
        resp_wh = client.post(
            reverse("cases:warehouse_confirm_entry", kwargs={"pk": case.id}),
            {"destination_warehouse": "STOCK", "comments": "Equipo reparado recibido en almacén central"},
        )
        assert resp_wh.status_code == 302
        case.refresh_from_db()
        assert case.stage == "FINALIZADO"

        # Kárdex verificado
        mvt = InventoryMovement.objects.filter(case=case).first()
        assert mvt is not None
        assert mvt.movement_type == InventoryMovement.MovementType.ENTRADA
        assert mvt.warehouse == "STOCK"

    def test_workshop_review_request_and_rereview(self):
        """Flujo D: Solicitud de revisión técnica en taller y re-revisión de jefe."""
        client = Client()
        chief_taller = User.objects.get(email="jefe.taller@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model = EquipmentModel.objects.first()

        case = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            workshop_region=reg_oaxc,
            returned_model=model,
            returned_serial="TALLER-REV-303",
            location=EquipmentCase.Location.TALLER,
            stage="EN_TALLER",
        )

        client.force_login(chief_taller)
        resp_rev = client.post(
            reverse("cases:workshop_request_review", kwargs={"pk": case.id}),
            {"review_reason": "Equipo presenta sellos de garantía violados"},
        )
        assert resp_rev.status_code == 302
        case.refresh_from_db()
        assert case.stage == "EN_REVISION_TALLER"
        assert "sellos de garantía" in case.review_reason

