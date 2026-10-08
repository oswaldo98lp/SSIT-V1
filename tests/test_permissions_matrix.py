"""Tests validating the Business Permission matrix across all 8 active roles."""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

User = get_user_model()


@pytest.fixture(autouse=True)
def setup_roles():
    call_command("seed_roles")
    call_command("seed_catalogs")
    call_command("seed_org")
    call_command("seed_demo")


@pytest.mark.django_db
class TestPermissionsMatrix:
    def test_soporte_ti_permissions(self):
        user = User.objects.get(email="soporte.oaxc@test-ssit.local")
        assert user.has_perm("accounts.create_voucher")
        assert user.has_perm("accounts.register_return")
        assert user.has_perm("accounts.define_equipment")
        # No debe poder autorizar ni despachar
        assert not user.has_perm("accounts.authorize_voucher")
        assert not user.has_perm("accounts.dispatch_voucher")

    def test_jefe_soporte_permissions(self):
        user = User.objects.get(email="jefe.oaxc@test-ssit.local")
        assert user.has_perm("accounts.authorize_voucher")
        assert user.has_perm("accounts.cancel_voucher")
        assert user.has_perm("accounts.assign_engineer")
        assert user.has_perm("accounts.review_definition_boss")
        assert user.has_perm("accounts.view_zone_reports")
        # No debe poder surtir en almacén
        assert not user.has_perm("accounts.dispatch_voucher")

    def test_almacen_permissions(self):
        user = User.objects.get(email="almacen.oaxc@test-ssit.local")
        assert user.has_perm("accounts.dispatch_voucher")
        assert user.has_perm("accounts.cancel_dispatched_item")
        assert user.has_perm("accounts.confirm_return")
        assert user.has_perm("accounts.review_definition_warehouse")
        assert user.has_perm("accounts.manage_scrap")
        # No debe poder autorizar vales
        assert not user.has_perm("accounts.authorize_voucher")

    def test_oficina_permissions(self):
        user = User.objects.get(email="oficina.central@test-ssit.local")
        assert user.has_perm("accounts.assign_repair_folio")
        assert user.has_perm("accounts.export_reports")
        # No debe poder surtir
        assert not user.has_perm("accounts.dispatch_voucher")

    def test_jefe_taller_permissions(self):
        user = User.objects.get(email="jefe.taller@test-ssit.local")
        assert user.has_perm("accounts.authorize_voucher")
        assert user.has_perm("accounts.manage_workshop")
        assert user.has_perm("accounts.assign_workshop_repair")
        assert user.has_perm("accounts.review_definition_boss")

    def test_soporte_taller_permissions(self):
        user = User.objects.get(email="soporte.taller@test-ssit.local")
        assert user.has_perm("accounts.define_workshop_equipment")
        # No debe poder autorizar
        assert not user.has_perm("accounts.authorize_voucher")

    def test_gerente_ssit_global_permissions(self):
        user = User.objects.get(email="gerente.ssit@test-ssit.local")
        assert user.has_perm("accounts.create_voucher")
        assert user.has_perm("accounts.authorize_voucher")
        assert user.has_perm("accounts.dispatch_voucher")
        assert user.has_perm("accounts.register_return")
        assert user.has_perm("accounts.manage_workshop")
        assert user.has_perm("accounts.view_coupa_consumption")
