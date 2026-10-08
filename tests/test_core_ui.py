"""Tests for core views, template tags, and UI components."""
import pytest
from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.urls import reverse

from apps.core.templatetags.core_tags import BADGE_STYLES

User = get_user_model()


@pytest.mark.django_db
class TestCoreUI:
    def test_dashboard_requires_login(self, client):
        url = reverse("core:dashboard")
        response = client.get(url)
        assert response.status_code == 302
        assert "/accounts/login/" in response.url

    def test_dashboard_renders_for_authenticated_user(self, client):
        user = User.objects.create_user(
            email="logged.user@test-ssit.local",
            password="Password123!",
            full_name="Usuario Autenticado",
        )
        client.force_login(user)
        response = client.get(reverse("core:dashboard"))
        assert response.status_code == 200
        assert "Panel de Control" in response.content.decode("utf-8")
        assert "Usuario Autenticado" in response.content.decode("utf-8")

    def test_components_preview_view(self, client):
        response = client.get(reverse("core:components_preview"))
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Catálogo de Componentes de Interfaz" in content
        assert "Badges de Estado" in content

    def test_htmx_modal_demo_endpoint(self, client):
        response = client.get(reverse("core:htmx_modal_demo"))
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Demostración de Modal HTMX" in content

    def test_status_badge_tag_all_21_styles(self):
        for badge_key in BADGE_STYLES:
            template_to_render = Template(
                f"{{% load core_tags %}}{{% status_badge '{badge_key}' %}}"
            )
            rendered = template_to_render.render(Context({}))
            assert "ssit-badge" in rendered
            style_class, icon, label = BADGE_STYLES[badge_key]
            assert icon in rendered

    def test_status_badge_unknown_fallback(self):
        template_to_render = Template(
            "{% load core_tags %}{% status_badge 'ESTADO_DESCONOCIDO' %}"
        )
        rendered = template_to_render.render(Context({}))
        assert "ssit-badge" in rendered

    def test_form_login_success(self, client):
        user = User.objects.create_user(
            email="test.login@test-ssit.local",
            password="Password123!",
            full_name="Usuario Login",
        )
        resp = client.post("/accounts/login/", {
            "login": "test.login@test-ssit.local",
            "password": "Password123!",
        })
        assert resp.status_code == 302
        assert resp.url in ["/", "/core/dashboard/", reverse("core:dashboard")]
