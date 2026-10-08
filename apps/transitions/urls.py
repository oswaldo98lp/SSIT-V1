"""Transitions app URL configuration."""
from django.urls import path

from . import views

app_name = "transitions"

urlpatterns = [
    path("inbox/", views.PendingInboxView.as_view(), name="inbox"),
    path(
        "modal/<str:entity_type>/<int:entity_id>/<str:transition_code>/",
        views.transition_modal_view,
        name="transition_modal",
    ),
]
