"""Concurrency tests: double authorization and double dispatch prevention."""
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command

from apps.inventory.models import EquipmentModel
from apps.org.models import Region
from apps.transitions.services import apply_transition, sync_transitions_to_db
from apps.vouchers.models import Voucher, VoucherLine

User = get_user_model()


@pytest.fixture(autouse=True)
def setup_data():
    call_command("seed_roles")
    call_command("seed_catalogs")
    call_command("seed_org")
    call_command("seed_demo")
    sync_transitions_to_db()


@pytest.mark.django_db(transaction=True)
class TestConcurrencyProtection:
    def test_prevent_double_authorization(self):
        user_jefe = User.objects.get(email="jefe.oaxc@test-ssit.local")
        user_soporte = User.objects.get(email="soporte.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")

        voucher = Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            requested_by=user_soporte,
            region=reg_oaxc,
            status=Voucher.Status.PENDIENTE_SURTIDO,
        )

        # Primera autorización tiene éxito
        apply_transition(user_jefe, voucher, "authorize_voucher")
        voucher.refresh_from_db()
        assert voucher.authorized_at is not None

        # Segundo intento consecutivo / concurrente debe ser rechazado inmediatamente
        with pytest.raises(ValidationError, match="ha sido autorizado previamente"):
            apply_transition(user_jefe, voucher, "authorize_voucher")

    def test_prevent_double_dispatch_on_same_voucher(self):
        user_jefe = User.objects.get(email="jefe.oaxc@test-ssit.local")
        user_almacen = User.objects.get(email="almacen.oaxc@test-ssit.local")
        user_soporte = User.objects.get(email="soporte.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model = EquipmentModel.objects.first()

        voucher = Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            requested_by=user_soporte,
            region=reg_oaxc,
            status=Voucher.Status.PENDIENTE_SURTIDO,
        )
        line = VoucherLine.objects.create(
            voucher=voucher,
            equipment_model=model,
            quantity=1,
        )

        # Autorizar primero
        apply_transition(user_jefe, voucher, "authorize_voucher")

        # Primer surtido
        apply_transition(
            user_almacen,
            voucher,
            "dispatch_voucher",
            {
                "received_by_id": user_soporte.id,
                "items_data": [{"line_id": line.id, "model_id": model.id, "serial_number": "CONCUR-SER-001"}],
            },
        )
        voucher.refresh_from_db()
        assert voucher.status == Voucher.Status.SURTIDO

        # Segundo surtido concurrente sobre el mismo vale debe fallar por etapa inválida
        with pytest.raises(ValidationError, match="no permite la acción"):
            apply_transition(
                user_almacen,
                voucher,
                "dispatch_voucher",
                {
                    "received_by_id": user_soporte.id,
                    "items_data": [{"line_id": line.id, "model_id": model.id, "serial_number": "CONCUR-SER-001"}],
                },
            )
