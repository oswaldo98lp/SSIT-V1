"""URLs for reports app."""
from django.urls import path
from apps.reports import views

app_name = "reports"

urlpatterns = [
    path("", views.report_dashboard_view, name="dashboard"),
    path("kardex/", views.kardex_list_view, name="kardex_list"),
    path("stock/", views.stock_balance_view, name="stock_balance"),
    path("vouchers/", views.vouchers_report_view, name="vouchers_report"),
    path("workshop/", views.workshop_report_view, name="workshop_report"),
    path("zones/", views.zone_summary_report_view, name="zone_summary"),
    path("coupa/", views.coupa_report_view, name="coupa_report"),
    path("reconciliation/", views.inventory_reconciliation_view, name="reconciliation"),
]
