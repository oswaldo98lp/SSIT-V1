"""Tests verifying Production Settings and Security Hardening."""
import pytest
from django.conf import settings
from config.settings import production


def test_production_security_settings():
    assert production.DEBUG is False
    assert production.SECURE_BROWSER_XSS_FILTER is True
    assert production.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert production.X_FRAME_OPTIONS == "DENY"
    assert production.SESSION_COOKIE_HTTPONLY is True
    assert production.CSRF_COOKIE_HTTPONLY is True
    assert production.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert production.SECURE_HSTS_PRELOAD is True
    assert production.STATICFILES_STORAGE == "whitenoise.storage.CompressedManifestStaticFilesStorage"
    assert "django.log" in str(production.LOGGING["handlers"]["file"]["filename"])
