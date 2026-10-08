"""Tests for the Generic Pending Inbox view (Screen 2) and HTMX transition modals."""
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse

from apps.org.models import Region
from apps.transitions.services import sync_transitions_to_db
from apps.vouchers.models import Voucher

User = get_user_model()


@pytest.fixture(autouse=True)
def setup_data():
    call_command("seed_roles")
    call_command("seed_catalogs")
    call_command("seed_org")
    call_command("seed_demo")
    sync_transitions_to_db()


@pytest.mark.django_db
class TestPendingInbox:
    def test_inbox_requires_login(self, client):
        response = client.get(reverse("transitions:inbox"))
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_inbox_renders_scoped_pending_items(self, client):
        user_jefe = User.objects.get(email="jefe.oaxc@test-ssit.local")
        user_soporte = User.objects.get(email="soporte.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")
        reg_azcp = Region.objects.get(code="AZCP")

        # Crear un vale en OAXC y uno en AZCP
        Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            report_folio="REP-INBOX-OAXC",
            requested_by=user_soporte,
            region=reg_oaxc,
            status=Voucher.Status.PENDIENTE_SURTIDO,
        )
        Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            report_folio="REP-INBOX-AZCP",
            requested_by=user_jefe,
            region=reg_azcp,
            status=Voucher.Status.PENDIENTE_SURTIDO,
        )

        client.force_login(user_jefe)
        response = client.get(reverse("transitions:inbox"))
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "REP-INBOX-OAXC" in content
        assert "REP-INBOX-AZCP" not in content  # AZCP queda fuera del alcance de jefe.oaxc

    def test_inbox_filtering_by_folio(self, client):
        user_jefe = User.objects.get(email="jefe.oaxc@test-ssit.local")
        user_soporte = User.objects.get(email="soporte.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")

        Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            report_folio="FOLIO-MATCH-123",
            requested_by=user_soporte,
            region=reg_oaxc,
            status=Voucher.Status.PENDIENTE_SURTIDO,
        )
        Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            report_folio="FOLIO-OTHER-999",
            requested_by=user_soporte,
            region=reg_oaxc,
            status=Voucher.Status.PENDIENTE_SURTIDO,
        )

        client.force_login(user_jefe)
        response = client.get(reverse("transitions:inbox"), {"folio": "MATCH-123"})
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "FOLIO-MATCH-123" in content
        assert "FOLIO-OTHER-999" not in content

    def test_transition_modal_view_render_and_post(self, client):
        user_jefe = User.objects.get(email="jefe.oaxc@test-ssit.local")
        user_soporte = User.objects.get(email="soporte.oaxc@test-ssit.local")
        reg_oaxc = Region.objects.get(code="OAXC")

        voucher = Voucher.objects.create(
            origin_type=Voucher.OriginType.VALE,
            report_folio="REP-MODAL-TEST",
            requested_by=user_soporte,
            region=reg_oaxc,
            status=Voucher.Status.PENDIENTE_SURTIDO,
        )

        client.force_login(user_jefe)
        url = reverse(
            "transitions:transition_modal",
            kwargs={
                "entity_type": "VOUCHER",
                "entity_id": voucher.id,
                "transition_code": "authorize_voucher",
            },
        )

        # GET modal
        response_get = client.get(url)
        assert response_get.status_code == 200
        assert "Autorizar Vale" in response_get.content.decode("utf-8")

        # POST modal
        response_post = client.post(url, {"comments": "Autorizado por modal HTMX."})
        assert response_post.status_code == 200
        assert response_post.headers.get("HX-Refresh") == "true"

        voucher.refresh_from_db()
        assert voucher.authorized_at is not None
