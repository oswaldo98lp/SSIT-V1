"""Tests for Flow C: Huesario, Scrap, Warranty Solutions and Returns Cancellation."""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from apps.cases.models import EquipmentCase
from apps.catalog.models import CatalogValue
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
class TestScrapAndCancellationsFlow:
    def test_scrap_confirmation_and_delivery_flow(self):
        """Flujo C: Definición Huesario -> Confirmación de Jefe -> Entrega Final en Almacén."""
        client = Client()
        boss_user = User.objects.get(email="jefe.oaxc@test-ssit.local")
        wh_user = User.objects.get(email="almacen.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model = EquipmentModel.objects.first()

        # Caso definido como HUESARIO
        case = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            returned_model=model,
            returned_serial="SCRAP-CASE-001",
            location=EquipmentCase.Location.CENTRO,
            stage="DEFINIDO",
            definition=EquipmentCase.Definition.HUESARIO,
            repair_comments="Tarjeta madre quemada, irreparable",
        )

        # 1. Jefe confirma envío a Huesario
        client.force_login(boss_user)
        resp_confirm = client.post(
            reverse("cases:confirm_scrap", kwargs={"pk": case.id}),
            {"comments": "Aprobado para scrap y rescate de componentes"},
        )
        assert resp_confirm.status_code == 302
        case.refresh_from_db()
        assert case.stage == "HUESARIO_CONFIRMADO"
        assert case.scrap_status == EquipmentCase.ScrapStatus.CONFIRMADO

        # 2. Almacén registra entrega física a Huesario
        client.force_login(wh_user)
        resp_deliver = client.post(
            reverse("cases:deliver_scrap", kwargs={"pk": case.id}),
            {"comments": "Depositado en jaula de scrap #4"},
        )
        assert resp_deliver.status_code == 302
        case.refresh_from_db()
        assert case.stage == "FINALIZADO_HUESARIO"
        assert case.scrap_status == EquipmentCase.ScrapStatus.ENVIADO

    def test_scrap_reversion_to_repair(self):
        """Flujo C: Reversión de Huesario de regreso a Reparación."""
        client = Client()
        boss_user = User.objects.get(email="jefe.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model = EquipmentModel.objects.first()

        case = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            returned_model=model,
            returned_serial="SCRAP-REV-002",
            stage="HUESARIO_CONFIRMADO",
            definition=EquipmentCase.Definition.HUESARIO,
            scrap_status=EquipmentCase.ScrapStatus.CONFIRMADO,
        )

        client.force_login(boss_user)
        resp = client.post(
            reverse("cases:return_scrap", kwargs={"pk": case.id}),
            {"comments": "Se consiguieron refacciones, reintentar reparación"},
        )
        assert resp.status_code == 302
        case.refresh_from_db()
        assert case.stage == "POR_REPARAR"
        assert case.scrap_status is None
        assert case.definition is None

    def test_warranty_solution_with_new_serial_flow(self):
        """Flujo C: Definición GARANTIA con solución NUEVO y serie nueva."""
        client = Client()
        tech_user = User.objects.get(email="soporte.oaxc@test-ssit.local")
        wh_user = User.objects.get(email="almacen.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model = EquipmentModel.objects.first()

        case = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            returned_model=model,
            returned_serial="GARANTIA-OLD-999",
            assigned_engineer=tech_user,
            location=EquipmentCase.Location.CENTRO,
            stage="POR_REPARAR",
        )

        # 1. Técnico define GARANTIA con solución NUEVO
        client.force_login(tech_user)
        resp_diag = client.post(
            reverse("cases:technical_diagnosis", kwargs={"pk": case.id}),
            {
                "definition": "GARANTIA",
                "repair_comments": "Aplica garantía con fabricante",
                "warranty_solution": "NUEVO",
                "new_serial": "GARANTIA-NEW-111",
                "insight_repair_confirmed": True,
            },
        )
        assert resp_diag.status_code == 302
        case.refresh_from_db()
        assert case.stage == "DEFINIDO"
        assert case.warranty_solution == "NUEVO"
        assert case.new_serial == "GARANTIA-NEW-111"

        # 2. Almacén confirma entrada y genera movimiento en Kárdex con la nueva serie
        client.force_login(wh_user)
        resp_entry = client.post(
            reverse("cases:warehouse_confirm_entry", kwargs={"pk": case.id}),
            {"destination_warehouse": "STOCK", "comments": "Equipo nuevo recibido por garantía"},
        )
        assert resp_entry.status_code == 302
        case.refresh_from_db()
        assert case.stage == "FINALIZADO"

        # Verificar Kárdex
        mvt = InventoryMovement.objects.filter(case=case).first()
        assert mvt is not None
        assert mvt.movement_type == InventoryMovement.MovementType.ENTRADA
        assert mvt.serial_number == "GARANTIA-NEW-111"
        assert mvt.condition == "NUEVO"

    def test_return_cancellation_and_manager_flow(self):
        """Flujo C: Centro cancela devolución -> Gerente confirma -> Almacén recibe."""
        client = Client()
        tech_user = User.objects.get(email="soporte.oaxc@test-ssit.local")
        manager_user = User.objects.get(email="gerente.zona1@test-ssit.local")
        wh_user = User.objects.get(email="almacen.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model = EquipmentModel.objects.first()

        case = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            returned_model=model,
            returned_serial="CANCEL-TEST-003",
            stage="PENDIENTE_CONFIRMAR",
        )

        # 1. Centro cancela devolución
        client.force_login(tech_user)
        resp_cancel = client.post(
            reverse("cases:cancel_return", kwargs={"pk": case.id}),
            {"cancel_reason": "Equipo se reasignó en centro operativo"},
        )
        assert resp_cancel.status_code == 302
        case.refresh_from_db()
        assert case.stage == "CANCELADA"

        # 2. Gerente valida y confirma cancelación
        client.force_login(manager_user)
        reason_val = CatalogValue.objects.filter(catalog="MANAGER_CANCEL_REASON").first()
        resp_mgr = client.post(
            reverse("cases:manager_confirm_cancellation", kwargs={"pk": case.id}),
            {"cancel_reason": reason_val.id if reason_val else "", "comments": "Autorizada cancelación"},
        )
        assert resp_mgr.status_code == 302
        case.refresh_from_db()
        assert case.stage == "CANCELACION_CONFIRMADA"

        # 3. Almacén confirma recepción del cancelado con Kárdex
        client.force_login(wh_user)
        resp_wh = client.get(
            reverse("cases:warehouse_receive_cancelled", kwargs={"pk": case.id})
        )
        assert resp_wh.status_code == 302
        case.refresh_from_db()
        assert case.stage == "FINALIZADO_CANCELADO"

        mvt = InventoryMovement.objects.filter(case=case).first()
        assert mvt is not None
        assert mvt.movement_type == InventoryMovement.MovementType.ENTRADA

    def test_cellular_workshop_and_boss_rejections_flow(self):
        """Flujo C: Taller Celular y Rechazos Técnicos / de Almacén."""
        boss_user = User.objects.get(email="jefe.oaxc@test-ssit.local")
        tech_user = User.objects.get(email="soporte.oaxc@test-ssit.local")
        wh_user = User.objects.get(email="almacen.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model = EquipmentModel.objects.first()

        case = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            returned_model=model,
            returned_serial="CEL-TEST-404",
            stage="POR_REPARAR",
            assigned_engineer=tech_user,
        )

        from apps.transitions.services import apply_transition

        # 1. Enviar a taller celular
        apply_transition(tech_user, case, "send_to_cellular_workshop", {"comments": "Enviado a taller de celulares"})
        case.refresh_from_db()
        assert case.stage == "ENVIADO_GARANTIA"
        assert case.definition == "GARANTIA"

        # 2. Definición técnica y rechazo de jefe
        case.stage = "DEFINIDO"
        case.save()
        apply_transition(boss_user, case, "boss_reject_definition", {"comments": "Pruebas incompletas"})
        case.refresh_from_db()
        assert case.stage == "POR_REPARAR"

        # 3. Rechazo de almacén
        case.stage = "DEFINIDO"
        case.save()
        apply_transition(wh_user, case, "warehouse_reject_definition", {"comments": "Falta accesorio para entrada"})
        case.refresh_from_db()
        assert case.stage == "POR_REPARAR"

        # 4. Equipo no utilizado: confirmación y rechazo
        case2 = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            returned_model=model,
            returned_serial="UNUSED-505",
            stage="PENDIENTE_CONFIRMAR",
        )
        apply_transition(boss_user, case2, "confirm_unused_equipment", {"comments": "Equipo intacto"})
        case2.refresh_from_db()
        assert case2.stage == "CONFIRMADO"

