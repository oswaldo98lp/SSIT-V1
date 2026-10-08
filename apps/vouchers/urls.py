"""Vouchers application URL patterns."""
from django.urls import path

from . import views

app_name = "vouchers"

urlpatterns = [
    path("", views.VoucherListView.as_view(), name="list"),
    path("create/", views.VoucherCreateView.as_view(), name="create"),
    path("<int:pk>/", views.VoucherDetailView.as_view(), name="detail"),
    path("<int:pk>/dispatch/", views.VoucherDispatchView.as_view(), name="dispatch"),
    path("<int:pk>/pdf/", views.VoucherPdfDownloadView.as_view(), name="pdf_download"),
    path("coupa/create/", views.CoupaConsumptionCreateView.as_view(), name="coupa_create"),
]
