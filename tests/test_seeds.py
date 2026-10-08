"""Tests verifying the idempotency and correctness of all management seed commands."""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command

from apps.catalog.models import CatalogValue
from apps.inventory.models import EquipmentModel
from apps.org.models import Center, Region, Zone

User = get_user_model()


@pytest.mark.django_db
class TestSeedCommands:
    def test_seed_roles_idempotency(self):
        # Primera ejecución
        call_command("seed_roles")
        role_count_1 = Group.objects.count()
        soporte_group = Group.objects.get(name="SOPORTE_TI")
        assert soporte_group.permissions.filter(codename="create_voucher").exists()

        # Segunda ejecución (no debe duplicar ni alterar)
        call_command("seed_roles")
        role_count_2 = Group.objects.count()
        assert role_count_1 == role_count_2

    def test_seed_catalogs_idempotency(self):
        call_command("seed_catalogs")
        count_1 = CatalogValue.objects.count()
        assert count_1 >= 40

        call_command("seed_catalogs")
        count_2 = CatalogValue.objects.count()
        assert count_1 == count_2

    def test_seed_org_idempotency(self):
        call_command("seed_org")
        zones_1 = Zone.objects.count()
        regions_1 = Region.objects.count()
        centers_1 = Center.objects.count()
        assert zones_1 == 6
        assert regions_1 >= 47

        call_command("seed_org")
        assert Zone.objects.count() == zones_1
        assert Region.objects.count() == regions_1
        assert Center.objects.count() == centers_1

    def test_seed_demo_idempotency(self):
        call_command("seed_org")
        call_command("seed_roles")
        call_command("seed_catalogs")
        call_command("seed_demo")

        demo_users_count_1 = User.objects.filter(email__endswith="@test-ssit.local").count()
        equipment_count_1 = EquipmentModel.objects.count()
        assert demo_users_count_1 == 8
        assert equipment_count_1 >= 5

        # Segunda corrida
        call_command("seed_demo")
        assert User.objects.filter(email__endswith="@test-ssit.local").count() == demo_users_count_1
        assert EquipmentModel.objects.count() == equipment_count_1
