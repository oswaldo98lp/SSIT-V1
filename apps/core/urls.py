"""Core application URLs."""
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("components-preview/", views.ComponentsPreviewView.as_view(), name="components_preview"),
    path("htmx/modal-demo/", views.htmx_modal_demo, name="htmx_modal_demo"),
]
