"""Tests verifying the 14 fundamental data models of the SSIT 2.0 architecture."""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.cases.models import EquipmentCase
from apps.catalog.models import CatalogValue
from apps.core.models import CoreEvent
from apps.documents.models import Document
from apps.inventory.models import EquipmentModel, InventoryItem, InventoryMovement
from apps.org.models import Center, Region, Zone
from apps.transitions.models import TransitionRule
from apps.vouchers.models import Voucher, VoucherLine

User = get_user_model()


@pytest.mark.django_db
class TestModelArchitecture:
    def test_complete_data_model_creation(self):
        # 1. Org Zone & Region & Center
        zone = Zone.objects.create(name="Zona 1")
        region = Region.objects.create(code="OAXC", name="Oaxaca", zone=zone, is_workshop=False)
        center = Center.objects.create(number=101, name="Tienda Oaxaca Centro", region=region)
        assert center.label == "101 - Tienda Oaxaca Centro"

        # 2. User
        user = User.objects.create_user(
            email="tech.lead@test-ssit.local",
            password="Password123!",
            full_name="Líder Técnico",
            region=region,
            center=center,
        )

        # 3. Catalog Value
        cat_reason = CatalogValue.objects.create(
            catalog="REQUEST_REASON",
            code="FALLA_EQUIPO",
            label="Falla de equipo en punto de venta",
            sort=1,
        )

        # 4. Inventory Equipment Model
        model = EquipmentModel.objects.create(
            name="Impresora Térmica POS",
            brand="Epson",
            model="TM-T88VI",
            is_inventoriable=True,
        )

        # 5. Voucher & VoucherLine
        voucher = Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            report_folio="REP-10023",
            destination_center=center,
            reason=cat_reason,
            requested_by=user,
            region=region,
            status=Voucher.Status.PENDIENTE_SURTIDO,
        )
        line = VoucherLine.objects.create(
            voucher=voucher,
            equipment_model=model,
            quantity=1,
        )

        # 6. Inventory Item
        item = InventoryItem.objects.create(
            voucher=voucher,
            line=line,
            equipment_model=model,
            serial_number="EPS-998877",
            condition=InventoryItem.Condition.RECUPERADO,
            warehouse=InventoryItem.Warehouse.STOCK,
            region=region,
            dispatched_at=timezone.now(),
        )

        # 7. Inventory Movement (Kardex)
        movement = InventoryMovement.objects.create(
            movement_type=InventoryMovement.MovementType.SALIDA,
            equipment_model=model,
            serial_number=item.serial_number,
            condition=item.condition,
            warehouse=item.warehouse,
            region=region,
            quantity=1,
            moved_at=timezone.now(),
            item=item,
            created_by=user,
        )

        # 8. Equipment Case
        case = EquipmentCase.objects.create(
            item=item,
            origin_region=region,
            returned_model=model,
            returned_serial="EPS-998877",
            stage="PENDIENTE_CONFIRMAR",
        )

        # 9. Document
        doc = Document.objects.create(
            kind=Document.Kind.VALE_PDF,
            related_type="Voucher",
            related_id=voucher.id,
            file="dummy_vale.pdf",
            created_by=user,
        )

        # 10. Core Event (Audit Log)
        event = CoreEvent.objects.create(
            entity_type="Voucher",
            entity_id=voucher.id,
            action_code="create_voucher",
            from_stage="",
            to_stage="PENDIENTE_SURTIDO",
            outcome=CoreEvent.Outcome.CONFIRMED,
            user=user,
            comment="Creación inicial de prueba",
        )

        # 11. Transition Rule
        rule = TransitionRule.objects.create(
            code="dispatch_voucher",
            label="Surtir Vale",
            entity=TransitionRule.Entity.VOUCHER,
            from_stages=["PENDIENTE_SURTIDO"],
            to_stage="SURTIDO",
            permission="dispatch_voucher",
            kardex_effect=TransitionRule.KardexEffect.SALIDA,
        )

        assert zone.id is not None
        assert region.id is not None
        assert center.id is not None
        assert user.id is not None
        assert model.id is not None
        assert voucher.id is not None
        assert line.id is not None
        assert item.id is not None
        assert movement.id is not None
        assert case.id is not None
        assert doc.id is not None
        assert event.id is not None
        assert rule.id is not None
