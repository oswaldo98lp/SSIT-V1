"""Root URL Configuration."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("transitions/", include("apps.transitions.urls")),
    path("vouchers/", include("apps.vouchers.urls")),
    path("cases/", include("apps.cases.urls")),
    path("reports/", include("apps.reports.urls", namespace="reports")),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
