"""URL configuration for Cases App (Returns, Diagnosis, Repair Folios, Workshop)."""
from django.urls import path
from . import views

app_name = "cases"

urlpatterns = [
    # Pantalla 5: Consulta y Alta de Devoluciones
    path("", views.case_list_view, name="case_list"),
    path("create/", views.case_return_create_view, name="case_create"),
    path("<int:pk>/", views.case_detail_view, name="case_detail"),

    # Pantalla 6: Dictamen de Almacén
    path("warehouse/inbox/", views.warehouse_inbox_view, name="warehouse_inbox"),
    path("<int:pk>/dictamen/", views.warehouse_dictamen_view, name="warehouse_dictamen"),
    path("<int:pk>/review-request/", views.request_return_review_view, name="request_review"),

    # Pantalla 7: Folios de Reparación (Oficina)
    path("office/folios/", views.repair_folio_inbox_view, name="repair_folio_inbox"),
    path("<int:pk>/assign-folio/", views.assign_repair_folio_view, name="assign_repair_folio"),

    # Pantallas 8 y 9: Taller Habilitado y Reparaciones
    path("workshop/inbox/", views.workshop_inbox_view, name="workshop_inbox"),
    path("<int:pk>/assign-engineer/", views.assign_engineer_view, name="assign_engineer"),
    path("<int:pk>/technical-diagnosis/", views.technical_diagnosis_view, name="technical_diagnosis"),
    path("<int:pk>/boss-confirm/", views.boss_confirm_view, name="boss_confirm"),
    path("<int:pk>/warehouse-confirm-entry/", views.warehouse_confirm_entry_view, name="warehouse_confirm_entry"),

    # Pantalla 8: Huesario / Scrap
    path("huesario/", views.huesario_inbox_view, name="huesario_inbox"),
    path("<int:pk>/confirm-scrap/", views.confirm_scrap_view, name="confirm_scrap"),
    path("<int:pk>/deliver-scrap/", views.deliver_scrap_view, name="deliver_scrap"),
    path("<int:pk>/return-scrap/", views.return_scrap_to_repair_view, name="return_scrap"),

    # Flujo D: Taller Habilitado Traslados
    path("<int:pk>/send-to-workshop/", views.send_to_workshop_view, name="send_to_workshop"),
    path("<int:pk>/cancel-workshop-send/", views.cancel_workshop_send_view, name="cancel_workshop_send"),
    path("<int:pk>/workshop-confirm-entry/", views.workshop_confirm_entry_view, name="workshop_confirm_entry"),
    path("<int:pk>/workshop-request-review/", views.workshop_request_review_view, name="workshop_request_review"),
    path("<int:pk>/workshop-wait-parts/", views.workshop_wait_parts_view, name="workshop_wait_parts"),

    # Cancelaciones de Devolución en Centro
    path("<int:pk>/cancel-return/", views.cancel_return_view, name="cancel_return"),
    path("<int:pk>/manager-confirm-cancellation/", views.manager_confirm_cancellation_view, name="manager_confirm_cancellation"),
    path("<int:pk>/warehouse-receive-cancelled/", views.warehouse_receive_cancelled_view, name="warehouse_receive_cancelled"),
]

