"""Tests verifying the Scope Selectors criterion: each test user sees ONLY their allowed scope."""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.selectors import get_engineers_for_assignment, get_users_for_scope
from apps.cases.models import EquipmentCase
from apps.cases.selectors import (
    get_cases_for_user,
    get_center_cases_for_user,
    get_workshop_cases_for_user,
)
from apps.catalog.selectors import get_catalog_choices, get_catalog_values
from apps.inventory.models import EquipmentModel, InventoryItem, InventoryMovement
from apps.inventory.selectors import (
    calculate_stock_balance,
    get_items_for_user,
    get_movements_for_user,
)
from apps.org.models import Center, Region, Zone
from apps.org.selectors import (
    get_user_allowed_centers,
    get_user_allowed_regions,
    get_user_allowed_zones,
)
from apps.vouchers.models import Voucher, VoucherLine
from apps.vouchers.selectors import (
    get_pending_vouchers_for_user,
    get_voucher_lines_for_user,
    get_vouchers_for_user,
)

User = get_user_model()


@pytest.fixture(autouse=True)
def populate_database_seeds():
    call_command("seed_roles")
    call_command("seed_catalogs")
    call_command("seed_org")
    call_command("seed_demo")


@pytest.mark.django_db
class TestScopeIsolation:
    def test_support_engineer_sees_only_own_region(self):
        soporte_user = User.objects.get(email="soporte.oaxc@test-ssit.local")
        allowed_regions = get_user_allowed_regions(soporte_user)

        # Solo debe ver OAXC
        assert allowed_regions.count() == 1
        assert allowed_regions.first().code == "OAXC"

        # Solo centros de OAXC
        allowed_centers = get_user_allowed_centers(soporte_user)
        assert allowed_centers.count() > 0
        assert all(c.region.code == "OAXC" for c in allowed_centers)

        # Solo zonas que contengan su región
        allowed_zones = get_user_allowed_zones(soporte_user)
        assert allowed_zones.count() == 1
        assert allowed_zones.first().name == "Zona 1"

    def test_zone_manager_sees_all_regions_in_zone_and_not_other_zones(self):
        zone_manager = User.objects.get(email="gerente.zona1@test-ssit.local")
        allowed_regions = get_user_allowed_regions(zone_manager)
        region_codes = set(allowed_regions.values_list("code", flat=True))

        # Zona 1 tiene OAXC, CRDB, VRCZ, etc.
        assert "OAXC" in region_codes
        assert "CRDB" in region_codes
        assert "VRCZ" in region_codes

        # Regiones de Zona 2 (AZCP, TOLC) NO deben ser visibles
        assert "AZCP" not in region_codes
        assert "TOLC" not in region_codes

        # Centros visibles solo pertenecen a Zona 1
        allowed_centers = get_user_allowed_centers(zone_manager)
        assert all(c.region.zone.name == "Zona 1" for c in allowed_centers)

    def test_global_scope_user_sees_all_regions_and_centers(self):
        global_manager = User.objects.get(email="gerente.ssit@test-ssit.local")
        allowed_regions = get_user_allowed_regions(global_manager)
        total_regions = Region.objects.count()
        assert allowed_regions.count() == total_regions

        allowed_centers = get_user_allowed_centers(global_manager)
        total_centers = Center.objects.filter(is_active=True).count()
        assert allowed_centers.count() == total_centers

        allowed_zones = get_user_allowed_zones(global_manager)
        assert allowed_zones.count() == Zone.objects.count()

    def test_voucher_queries_are_strictly_scoped(self):
        user_oaxc = User.objects.get(email="soporte.oaxc@test-ssit.local")
        user_azcp = User.objects.get(email="oficina.central@test-ssit.local")
        global_user = User.objects.get(email="gerente.ssit@test-ssit.local")

        reg_oaxc = Region.objects.get(code="OAXC")
        reg_azcp = Region.objects.get(code="AZCP")
        model = EquipmentModel.objects.first()

        # Crear vale en OAXC y vale en AZCP
        voucher_oaxc = Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            report_folio="REP-OAXC-001",
            requested_by=user_oaxc,
            region=reg_oaxc,
            status=Voucher.Status.PENDIENTE_SURTIDO,
        )
        line_oaxc = VoucherLine.objects.create(
            voucher=voucher_oaxc,
            equipment_model=model,
            quantity=2,
        )

        voucher_azcp = Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            report_folio="REP-AZCP-001",
            requested_by=user_azcp,
            region=reg_azcp,
            status=Voucher.Status.PENDIENTE_SURTIDO,
        )

        # Usuario OAXC solo ve el de OAXC
        vouchers_seen_by_oaxc = list(get_vouchers_for_user(user_oaxc))
        assert voucher_oaxc in vouchers_seen_by_oaxc
        assert voucher_azcp not in vouchers_seen_by_oaxc

        pending_oaxc = list(get_pending_vouchers_for_user(user_oaxc))
        assert voucher_oaxc in pending_oaxc

        lines_oaxc = list(get_voucher_lines_for_user(user_oaxc, voucher_oaxc.id))
        assert line_oaxc in lines_oaxc

        # Usuario AZCP no tiene acceso a las líneas de OAXC
        lines_cross_scope = list(get_voucher_lines_for_user(user_azcp, voucher_oaxc.id))
        assert len(lines_cross_scope) == 0

        # Usuario AZCP solo ve el de AZCP
        vouchers_seen_by_azcp = list(get_vouchers_for_user(user_azcp))
        assert voucher_azcp in vouchers_seen_by_azcp
        assert voucher_oaxc not in vouchers_seen_by_azcp

        # Usuario global ve ambos
        vouchers_seen_by_global = list(get_vouchers_for_user(global_user))
        assert voucher_oaxc in vouchers_seen_by_global
        assert voucher_azcp in vouchers_seen_by_global

    def test_case_queries_are_strictly_scoped_by_origin_and_workshop(self):
        user_oaxc = User.objects.get(email="soporte.oaxc@test-ssit.local")
        user_azcp = User.objects.get(email="oficina.central@test-ssit.local")
        global_user = User.objects.get(email="gerente.ssit@test-ssit.local")

        reg_oaxc = Region.objects.get(code="OAXC")
        reg_azcp = Region.objects.get(code="AZCP")
        model = EquipmentModel.objects.first()

        # Caso 1: Origen OAXC (Centro)
        case_oaxc = EquipmentCase.objects.create(
            origin_region=reg_oaxc,
            returned_model=model,
            returned_serial="OAX-CASE-123",
            location=EquipmentCase.Location.CENTRO,
            stage="PENDIENTE_CONFIRMAR",
        )
        # Caso 2: Taller AZCP
        case_azcp = EquipmentCase.objects.create(
            origin_region=reg_azcp,
            workshop_region=reg_azcp,
            returned_model=model,
            returned_serial="AZCP-CASE-456",
            location=EquipmentCase.Location.TALLER,
            stage="EN_TALLER",
        )

        # Verificación de aislamiento
        cases_oaxc = list(get_cases_for_user(user_oaxc))
        assert case_oaxc in cases_oaxc
        assert case_azcp not in cases_oaxc

        center_cases = list(get_center_cases_for_user(user_oaxc))
        assert case_oaxc in center_cases

        workshop_cases = list(get_workshop_cases_for_user(user_azcp))
        assert case_azcp in workshop_cases

        cases_azcp = list(get_cases_for_user(user_azcp))
        assert case_azcp in cases_azcp
        assert case_oaxc not in cases_azcp

        cases_global = list(get_cases_for_user(global_user))
        assert case_oaxc in cases_global
        assert case_azcp in cases_global

    def test_inventory_and_kardex_selectors(self):
        user_oaxc = User.objects.get(email="soporte.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        model = EquipmentModel.objects.first()

        voucher = Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            report_folio="REP-INV-001",
            requested_by=user_oaxc,
            region=reg_oaxc,
            status=Voucher.Status.SURTIDO,
        )

        item = InventoryItem.objects.create(
            voucher=voucher,
            equipment_model=model,
            serial_number="SERIAL-INV-999",
            condition=InventoryItem.Condition.RECUPERADO,
            warehouse=InventoryItem.Warehouse.STOCK,
            region=reg_oaxc,
            dispatched_at=timezone.now(),
        )

        # Kardex movement: Entrada de 5 unidades, Salida de 2 unidades
        InventoryMovement.objects.create(
            movement_type=InventoryMovement.MovementType.ENTRADA,
            equipment_model=model,
            serial_number="SERIAL-INV-999",
            condition=InventoryItem.Condition.RECUPERADO,
            warehouse=InventoryItem.Warehouse.STOCK,
            region=reg_oaxc,
            quantity=5,
            moved_at=timezone.now(),
            item=item,
            confirmed=True,
            created_by=user_oaxc,
        )
        InventoryMovement.objects.create(
            movement_type=InventoryMovement.MovementType.SALIDA,
            equipment_model=model,
            serial_number="SERIAL-INV-999",
            condition=InventoryItem.Condition.RECUPERADO,
            warehouse=InventoryItem.Warehouse.STOCK,
            region=reg_oaxc,
            quantity=2,
            moved_at=timezone.now(),
            item=item,
            confirmed=True,
            created_by=user_oaxc,
        )

        items_oaxc = list(get_items_for_user(user_oaxc, serial_number="SERIAL-INV-999"))
        assert len(items_oaxc) == 1
        assert items_oaxc[0].serial_number == "SERIAL-INV-999"

        movements = list(get_movements_for_user(user_oaxc))
        assert len(movements) >= 2

        balance = calculate_stock_balance(model.id, reg_oaxc.id, warehouse="STOCK", condition="RECUPERADO")
        assert balance == 3  # 5 entrada - 2 salida = 3

    def test_catalog_selectors(self):
        values = get_catalog_values("REQUEST_REASON")
        assert values.count() == 11

        choices = get_catalog_choices("REQUEST_REASON")
        assert len(choices) == 11
        assert choices[0][0] == "FALLA_EQUIPO"

    def test_accounts_scoped_selectors(self):
        user_oaxc = User.objects.get(email="soporte.oaxc@test-ssit.local")
        users_in_scope = list(get_users_for_scope(user_oaxc))
        assert user_oaxc in users_in_scope
        assert all(u.region.code == "OAXC" for u in users_in_scope if u.region)

        engineers = list(get_engineers_for_assignment(user_oaxc))
        assert user_oaxc in engineers

    def test_unauthenticated_or_empty_user_receives_empty_queryset(self):
        assert get_user_allowed_regions(None).count() == 0
        assert get_user_allowed_centers(None).count() == 0
        assert get_user_allowed_zones(None).count() == 0
        assert get_vouchers_for_user(None).count() == 0
        assert get_cases_for_user(None).count() == 0
        assert get_items_for_user(None).count() == 0
        assert get_movements_for_user(None).count() == 0
        assert get_users_for_scope(None).count() == 0
