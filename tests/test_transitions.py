"""Unit and integration tests for the Business Transition Engine."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.utils import timezone

from apps.cases.models import EquipmentCase
from apps.catalog.models import CatalogValue
from apps.core.models import CoreEvent
from apps.inventory.models import EquipmentModel, InventoryItem, InventoryMovement
from apps.org.models import Center, Region
from apps.transitions.services import (
    apply_transition,
    sync_transitions_to_db,
)
from apps.vouchers.models import Voucher, VoucherLine

User = get_user_model()


@pytest.fixture(autouse=True)
def setup_data():
    call_command("seed_roles")
    call_command("seed_catalogs")
    call_command("seed_org")
    call_command("seed_demo")
    sync_transitions_to_db()


@pytest.mark.django_db
class TestTransitionsEngine:
    def test_voucher_full_lifecycle_and_kardex(self):
        # 1. Crear vale con líneas (Soporte TI)
        user_soporte = User.objects.get(email="soporte.oaxc@test-ssit.local")
        user_jefe = User.objects.get(email="jefe.oaxc@test-ssit.local")
        user_almacen = User.objects.get(email="almacen.oaxc@test-ssit.local")

        reg_oaxc = Region.objects.get(code="OAXC")
        center_oaxc = Center.objects.filter(region=reg_oaxc).first()
        model_epson = EquipmentModel.objects.first()
        reason = CatalogValue.objects.filter(catalog="REQUEST_REASON").first()

        voucher = Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            report_folio="REP-OAX-777",
            destination_center=center_oaxc,
            reason=reason,
            requested_by=user_soporte,
            region=reg_oaxc,
            status=Voucher.Status.PENDIENTE_SURTIDO,
        )
        line = VoucherLine.objects.create(
            voucher=voucher,
            equipment_model=model_epson,
            quantity=1,
            status=VoucherLine.LineStatus.PENDIENTE,
        )

        # 2. Intento de surtir sin autorizar debe fallar
        with pytest.raises(ValidationError, match="previamente autorizado"):
            apply_transition(
                user_almacen,
                voucher,
                "dispatch_voucher",
                {
                    "received_by_id": user_soporte.id,
                    "items_data": [{"line_id": line.id, "serial_number": "EPSON-SER-001"}],
                },
            )

        # 3. Autorizar vale (Jefe de Soporte)
        event_auth = apply_transition(
            user_jefe,
            voucher,
            "authorize_voucher",
            {"comments": "Autorizado para cambio urgente."},
        )
        voucher.refresh_from_db()
        assert voucher.authorized_at is not None
        assert voucher.authorized_by == user_jefe
        assert event_auth.action_code == "authorize_voucher"
        assert event_auth.outcome == CoreEvent.Outcome.CONFIRMED

        # 4. Surtir vale (Almacén)
        event_disp = apply_transition(
            user_almacen,
            voucher,
            "dispatch_voucher",
            {
                "received_by_id": user_soporte.id,
                "items_data": [
                    {
                        "line_id": line.id,
                        "model_id": model_epson.id,
                        "serial_number": "EPSON-SER-001",
                        "condition": InventoryItem.Condition.RECUPERADO,
                        "warehouse": InventoryItem.Warehouse.STOCK,
                    }
                ],
            },
        )
        voucher.refresh_from_db()
        line.refresh_from_db()
        assert voucher.status == Voucher.Status.SURTIDO
        assert line.status == VoucherLine.LineStatus.SURTIDO
        assert event_disp.action_code == "dispatch_voucher"

        # Verificar creación de InventoryItem con serie
        item = InventoryItem.objects.get(serial_number="EPSON-SER-001")
        assert item.voucher == voucher
        assert item.region == reg_oaxc

        # Verificar movimiento de SALIDA en Kardex
        movement = InventoryMovement.objects.get(serial_number="EPSON-SER-001")
        assert movement.movement_type == InventoryMovement.MovementType.SALIDA
        assert movement.quantity == 1
        assert movement.confirmed is True

    def test_cancel_dispatched_item_within_120_hours(self):
        user_soporte = User.objects.get(email="soporte.oaxc@test-ssit.local")
        user_almacen = User.objects.get(email="almacen.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model = EquipmentModel.objects.first()

        voucher = Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            requested_by=user_soporte,
            region=reg_oaxc,
            status=Voucher.Status.SURTIDO,
        )
        item = InventoryItem.objects.create(
            voucher=voucher,
            equipment_model=model,
            serial_number="CANCEL-SER-888",
            condition=InventoryItem.Condition.RECUPERADO,
            warehouse=InventoryItem.Warehouse.STOCK,
            region=reg_oaxc,
            dispatched_at=timezone.now() - timedelta(hours=50),  # Menos de 120 horas
        )

        apply_transition(
            user_almacen,
            item,
            "cancel_dispatched_item",
            {"cancel_note": "Cancelación solicitada por error en tienda."},
        )
        item.refresh_from_db()
        assert item.cancelled_at is not None
        assert item.cancelled_by == user_almacen

        # Debe generar movimiento de ENTRADA
        entry_movement = InventoryMovement.objects.filter(
            serial_number="CANCEL-SER-888",
            movement_type=InventoryMovement.MovementType.ENTRADA,
        ).first()
        assert entry_movement is not None
        assert entry_movement.quantity == 1

    def test_cancel_dispatched_item_exceeding_120_hours_fails(self):
        user_soporte = User.objects.get(email="soporte.oaxc@test-ssit.local")
        user_almacen = User.objects.get(email="almacen.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model = EquipmentModel.objects.first()

        voucher = Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            requested_by=user_soporte,
            region=reg_oaxc,
            status=Voucher.Status.SURTIDO,
        )
        item = InventoryItem.objects.create(
            voucher=voucher,
            equipment_model=model,
            serial_number="EXPIRED-SER-999",
            condition=InventoryItem.Condition.RECUPERADO,
            warehouse=InventoryItem.Warehouse.STOCK,
            region=reg_oaxc,
            dispatched_at=timezone.now() - timedelta(hours=125),  # Más de 120 horas
        )

        with pytest.raises(ValidationError, match="120 horas"):
            apply_transition(
                user_almacen,
                item,
                "cancel_dispatched_item",
                {"cancel_note": "Intento tardío de cancelación."},
            )

    def test_return_case_and_warehouse_entry_lifecycle(self):
        user_soporte = User.objects.get(email="soporte.oaxc@test-ssit.local")
        user_almacen = User.objects.get(email="almacen.oaxc@test-ssit.local")
        user_jefe = User.objects.get(email="jefe.oaxc@test-ssit.local")
        model = EquipmentModel.objects.first()

        # 1. Registrar devolución en centro
        apply_transition(
            user_soporte,
            None,
            "register_return",
            {
                "returned_model_id": model.id,
                "returned_serial": "DEV-OAX-404",
                "route": EquipmentCase.Route.EVALUACION_CENTRO,
                "failure": "No enciende tras descarga eléctrica.",
            },
        )
        case = EquipmentCase.objects.get(returned_serial="DEV-OAX-404")
        assert case.stage == "PENDIENTE_CONFIRMAR"

        # 2. Confirmar devolución y dictaminar (Almacén)
        ruling = CatalogValue.objects.filter(catalog="RULING", code="REPARACION").first()
        apply_transition(
            user_almacen,
            case,
            "confirm_return",
            {"ruling_id": ruling.id, "returned_model_id": model.id},
        )
        case.refresh_from_db()
        assert case.stage == "CONFIRMADO"

        # 3. Asignar Ingeniero (Jefe)
        apply_transition(
            user_jefe,
            case,
            "assign_engineer",
            {"assigned_engineer_id": user_soporte.id},
        )
        case.refresh_from_db()
        assert case.stage == "POR_REPARAR"
        assert case.assigned_engineer == user_soporte

        # 4. Definir equipo (Ingeniero Asignado)
        apply_transition(
            user_soporte,
            case,
            "define_equipment",
            {
                "definition": EquipmentCase.Definition.REPARADO,
                "repair_comments": "Se reemplazó fusible y se calibró.",
            },
        )
        case.refresh_from_db()
        assert case.stage == "DEFINIDO"

        # 5. Entrada a Almacén final (Almacén)
        apply_transition(
            user_almacen,
            case,
            "warehouse_confirm_definition",
            {"destination_warehouse": "STOCK"},
        )
        case.refresh_from_db()
        assert case.stage == "FINALIZADO"

        # Verificar movimiento de ENTRADA en Kardex generado por el cierre del caso
        entry = InventoryMovement.objects.filter(
            case=case,
            movement_type=InventoryMovement.MovementType.ENTRADA,
        ).first()
        assert entry is not None
        assert entry.quantity == 1

    def test_permission_denied_when_user_lacks_role(self):
        user_soporte = User.objects.get(email="soporte.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        voucher = Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            requested_by=user_soporte,
            region=reg_oaxc,
            status=Voucher.Status.PENDIENTE_SURTIDO,
        )

        # Soporte no tiene permiso authorize_voucher
        with pytest.raises(PermissionDenied, match="No tienes el permiso"):
            apply_transition(user_soporte, voucher, "authorize_voucher")

    def test_cross_region_scope_denial(self):
        from django.contrib.auth.models import Group
        reg_oaxc = Region.objects.get(code="OAXC")
        reg_azcp = Region.objects.get(code="AZCP")
        user_soporte = User.objects.get(email="soporte.oaxc@test-ssit.local")

        # Jefe de soporte asignado exclusivamente a AZCP
        user_jefe_azcp = User.objects.create_user(
            email="jefe.azcp@test-ssit.local",
            password="Password123!",
            full_name="Jefe Azcapotzalco",
            region=reg_azcp,
        )
        jefe_group = Group.objects.get(name="JEFE_SOPORTE")
        user_jefe_azcp.groups.add(jefe_group)

        voucher_oaxc = Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            requested_by=user_soporte,
            region=reg_oaxc,
            status=Voucher.Status.PENDIENTE_SURTIDO,
        )

        # Jefe de AZCP tiene el permiso authorize_voucher pero está fuera del alcance de OAXC
        with pytest.raises(PermissionDenied, match="alcance asignado"):
            apply_transition(user_jefe_azcp, voucher_oaxc, "authorize_voucher")
