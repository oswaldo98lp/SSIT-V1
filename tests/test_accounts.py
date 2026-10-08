"""Unit tests for custom User model and accounts app."""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps.org.models import Region, Zone

User = get_user_model()


@pytest.mark.django_db
class TestUserModel:
    def test_create_user_with_email_success(self):
        user = User.objects.create_user(
            email="tech.engineer@test-ssit.local",
            password="SecureTestPassword123!",
            full_name="Ingeniero de Prueba",
            employee_number="EMP-001",
        )
        assert user.email == "tech.engineer@test-ssit.local"
        assert user.full_name == "Ingeniero de Prueba"
        assert user.employee_number == "EMP-001"
        assert user.is_active is True
        assert user.is_staff is False
        assert user.is_superuser is False
        assert user.has_global_scope is False
        assert user.check_password("SecureTestPassword123!") is True

    def test_create_user_without_email_raises_error(self):
        with pytest.raises(ValueError, match="El correo electrónico es obligatorio"):
            User.objects.create_user(email="", password="SomePassword123")

    def test_create_superuser(self):
        admin = User.objects.create_superuser(
            email="admin.ssit@test-ssit.local",
            password="AdminPassword123!",
            full_name="Administrador del Sistema",
        )
        assert admin.is_staff is True
        assert admin.is_superuser is True
        assert admin.has_global_scope is True

    def test_allowed_regions_for_regular_user(self):
        zone = Zone.objects.create(name="Zona 1")
        reg1 = Region.objects.create(code="OAXC", name="Oaxaca", zone=zone)
        Region.objects.create(code="CRDB", name="Córdoba", zone=zone)

        user = User.objects.create_user(
            email="user.reg1@test-ssit.local",
            password="Password123!",
            full_name="Usuario Región 1",
            region=reg1,
        )
        allowed = list(user.allowed_regions())
        assert len(allowed) == 1
        assert allowed[0].code == "OAXC"

    def test_allowed_regions_with_extra_regions(self):
        zone = Zone.objects.create(name="Zona 1")
        reg1 = Region.objects.create(code="OAXC", name="Oaxaca", zone=zone)
        reg2 = Region.objects.create(code="CRDB", name="Córdoba", zone=zone)

        user = User.objects.create_user(
            email="user.extra@test-ssit.local",
            password="Password123!",
            full_name="Usuario con región extra",
            region=reg1,
        )
        user.extra_regions.add(reg2)

        allowed = list(user.allowed_regions().order_by("code"))
        assert len(allowed) == 2
        assert [r.code for r in allowed] == ["CRDB", "OAXC"]

    def test_allowed_regions_for_zone_manager(self):
        zone1 = Zone.objects.create(name="Zona 1")
        zone2 = Zone.objects.create(name="Zona 2")
        reg1 = Region.objects.create(code="OAXC", name="Oaxaca", zone=zone1)
        Region.objects.create(code="CRDB", name="Córdoba", zone=zone1)
        reg3 = Region.objects.create(code="AZCP", name="Azcapotzalco", zone=zone2)

        zone_group, _ = Group.objects.get_or_create(name="GERENTE_ZONA")
        user = User.objects.create_user(
            email="manager.zone1@test-ssit.local",
            password="Password123!",
            full_name="Gerente de Zona 1",
            region=reg1,
        )
        user.groups.add(zone_group)

        allowed = list(user.allowed_regions().order_by("code"))
        assert len(allowed) == 2
        assert [r.code for r in allowed] == ["CRDB", "OAXC"]
        assert reg3 not in allowed

    def test_allowed_regions_for_global_scope_user(self):
        zone = Zone.objects.create(name="Zona 1")
        Region.objects.create(code="OAXC", name="Oaxaca", zone=zone)
        Region.objects.create(code="CRDB", name="Córdoba", zone=zone)

        user = User.objects.create_user(
            email="global.manager@test-ssit.local",
            password="Password123!",
            full_name="Gerente Nacional",
            has_global_scope=True,
        )
        allowed = list(user.allowed_regions())
        assert len(allowed) == 2
