"""Tests for Phase 5 - Workshop, Technical Diagnosis, Boss Confirmation, and Kardex Entry."""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse

from apps.cases.models import EquipmentCase
from apps.catalog.models import CatalogValue
from apps.inventory.models import EquipmentModel, InventoryMovement
from apps.org.models import Region
from apps.transitions.services import sync_transitions_to_db

User = get_user_model()


@pytest.fixture(autouse=True)
def setup_workshop_flow_data():
    call_command("seed_roles")
    call_command("seed_catalogs")
    call_command("seed_org")
    call_command("seed_demo")
    sync_transitions_to_db()


@pytest.mark.django_db
class TestWorkshopFlow:
    """Test suite for workshop engineer assignment, technical diagnosis, boss confirmation and warehouse entry."""

    def test_assign_engineer_flow(self, client):
        user_jefe_taller = User.objects.get(email="jefe.taller@test-ssit.local")
        user_soporte_taller = User.objects.get(email="soporte.taller@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model_switch = EquipmentModel.objects.first()
        ruling_rep = CatalogValue.objects.filter(catalog="RULING").first()

        case = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            workshop_region=reg_oaxc,
            location=EquipmentCase.Location.CENTRO,
            returned_model=model_switch,
            returned_serial="SN-WS-2001",
            ruling=ruling_rep,
            stage="CONFIRMADO",
        )

        client.force_login(user_jefe_taller)
        assign_url = reverse("cases:assign_engineer", kwargs={"pk": case.id})
        payload = {
            "assigned_engineer": user_soporte_taller.id,
        }

        response = client.post(assign_url, payload, follow=True)
        assert response.status_code == 200

        case.refresh_from_db()
        assert case.stage == "POR_REPARAR"
        assert case.assigned_engineer == user_soporte_taller
        assert case.assigned_at is not None

    def test_technical_diagnosis_repaired_flow(self, client):
        user_soporte_taller = User.objects.get(email="soporte.taller@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model_switch = EquipmentModel.objects.first()

        case = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            workshop_region=reg_oaxc,
            location=EquipmentCase.Location.TALLER,
            returned_model=model_switch,
            returned_serial="SN-WS-2002",
            assigned_engineer=user_soporte_taller,
            stage="POR_REPARAR",
        )

        client.force_login(user_soporte_taller)
        diag_url = reverse("cases:technical_diagnosis", kwargs={"pk": case.id})
        payload = {
            "definition": EquipmentCase.Definition.REPARADO,
            "repair_comments": "Se reemplazó fuente de poder interna y se verificaron puertos.",
            "insight_repair_confirmed": True,
        }

        response = client.post(diag_url, payload, follow=True)
        assert response.status_code == 200

        case.refresh_from_db()
        assert case.stage == "DEFINIDO"
        assert case.definition == EquipmentCase.Definition.REPARADO
        assert case.repaired_at is not None
        assert "fuente de poder" in case.repair_comments

    def test_boss_confirmation_flow(self, client):
        user_jefe_taller = User.objects.get(email="jefe.taller@test-ssit.local")
        user_soporte_taller = User.objects.get(email="soporte.taller@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model_switch = EquipmentModel.objects.first()

        case = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            workshop_region=reg_oaxc,
            location=EquipmentCase.Location.TALLER,
            returned_model=model_switch,
            returned_serial="SN-WS-2003",
            assigned_engineer=user_soporte_taller,
            definition=EquipmentCase.Definition.REPARADO,
            stage="DEFINIDO",
        )

        client.force_login(user_jefe_taller)
        boss_url = reverse("cases:boss_confirm", kwargs={"pk": case.id})

        response = client.post(boss_url, {"comments": "Validado en banco de pruebas."}, follow=True)
        assert response.status_code == 200

        case.refresh_from_db()
        assert case.stage == "CONFIRMADO_JEFE"

    def test_warehouse_confirm_entry_generates_kardex(self, client):
        user_almacen = User.objects.get(email="almacen.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model_switch = EquipmentModel.objects.first()

        case = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            workshop_region=reg_oaxc,
            location=EquipmentCase.Location.TALLER,
            returned_model=model_switch,
            returned_serial="SN-WS-2004",
            definition=EquipmentCase.Definition.REPARADO,
            stage="CONFIRMADO_JEFE",
        )

        client.force_login(user_almacen)
        entry_url = reverse("cases:warehouse_confirm_entry", kwargs={"pk": case.id})
        payload = {
            "destination_warehouse": "STOCK",
            "comments": "Reingreso al almacén en stock disponible.",
        }

        response = client.post(entry_url, payload, follow=True)
        assert response.status_code == 200

        case.refresh_from_db()
        assert case.stage == "FINALIZADO"
        assert case.destination_warehouse == "STOCK"

        # Verify Kardex Movement ENTRADA
        mov = InventoryMovement.objects.filter(case=case).first()
        assert mov is not None
        assert mov.movement_type == InventoryMovement.MovementType.ENTRADA
        assert mov.serial_number == "SN-WS-2004"
        assert mov.warehouse == "STOCK"
        assert mov.quantity == 1
        assert mov.confirmed is True
