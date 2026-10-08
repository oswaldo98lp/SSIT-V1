"""Tests for Phase 8: ETL, Legacy Migration and Inventory Physical Reconciliation."""
import csv
import io
import os
import tempfile
import openpyxl
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.cases.models import EquipmentCase
from apps.core.etl_services import (
    generate_reconciliation_xlsx,
    import_legacy_cases_from_data,
    import_legacy_inventory_items_from_data,
    import_legacy_vouchers_from_data,
    reconcile_inventory_balances,
)
from apps.inventory.models import EquipmentModel, InventoryItem, InventoryMovement
from apps.org.models import Center, Region
from apps.transitions.services import sync_transitions_to_db
from apps.vouchers.models import Voucher

User = get_user_model()


@pytest.fixture(autouse=True)
def setup_etl_data(db):
    call_command("seed_roles")
    call_command("seed_catalogs")
    call_command("seed_org")
    call_command("seed_demo")
    sync_transitions_to_db()


@pytest.mark.django_db
class TestETLServices:
    def test_import_legacy_vouchers_idempotent_and_dry_run(self):
        reg = Region.objects.first()
        center = Center.objects.filter(region=reg).first()
        user = User.objects.first()

        rows = [
            {
                "legacy_id": "LEG-V-001",
                "region_code": reg.code,
                "center_number": str(center.number) if center else "1",
                "user_email": user.email,
                "origin_type": "VALE",
                "status": "SURTIDO",
                "report_folio": "FOL-V-100",
                "comments": "Vale legacy 1",
            },
            {
                "legacy_id": "LEG-V-002",
                "region_code": reg.code,
                "center_number": str(center.number) if center else "1",
                "user_email": user.email,
                "origin_type": "COUPA",
                "coupa_id": "COUPA-LEG-99",
                "status": "PENDIENTE",
                "report_folio": "FOL-V-101",
                "comments": "Vale legacy 2",
            },
            {
                # Fila inválida sin legacy_id
                "legacy_id": "",
                "region_code": reg.code,
            },
        ]

        # 1. Simulación Dry-Run
        stats_dry = import_legacy_vouchers_from_data(rows, dry_run=True)
        assert stats_dry["total"] == 3
        assert stats_dry["created"] == 2
        assert stats_dry["skipped"] == 1
        assert Voucher.objects.filter(legacy_id__in=["LEG-V-001", "LEG-V-002"]).count() == 0

        # 2. Inserción Real
        stats_real = import_legacy_vouchers_from_data(rows, dry_run=False)
        assert stats_real["created"] == 2
        assert Voucher.objects.filter(legacy_id__in=["LEG-V-001", "LEG-V-002"]).count() == 2

        # 3. Re-ejecución idempotente (actualización)
        stats_re = import_legacy_vouchers_from_data(rows, dry_run=False)
        assert stats_re["created"] == 0
        assert stats_re["updated"] == 2
        assert Voucher.objects.filter(legacy_id__in=["LEG-V-001", "LEG-V-002"]).count() == 2

    def test_import_legacy_cases_idempotent(self):
        reg_oaxc = Region.objects.get(code="OAXC")
        user = User.objects.first()
        model = EquipmentModel.objects.first()

        rows = [
            {
                "legacy_id": "LEG-CASE-01",
                "origin_region_code": "OAXC",
                "returned_model_name": model.name,
                "returned_serial": "SN-LEG-C1",
                "stage": "FINALIZADO",
                "definition": "REPARADO",
                "repair_folio": "FOL-REP-101",
                "received_by_email": user.email,
            },
            {
                "legacy_id": "LEG-CASE-02",
                "origin_region_code": "OAXC",
                "returned_model_name": "Equipo Desconocido Texto",
                "returned_serial": "SN-LEG-C2",
                "stage": "FINALIZADO_HUESARIO",
                "definition": "HUESARIO",
                "repair_folio": "",
                "received_by_email": user.email,
            },
            {
                "legacy_id": "",  # Inválido
                "origin_region_code": "OAXC",
            },
        ]

        stats = import_legacy_cases_from_data(rows, dry_run=False)
        assert stats["created"] == 2
        assert stats["skipped"] == 1

        case1 = EquipmentCase.objects.get(legacy_id="LEG-CASE-01")
        assert case1.returned_model == model
        assert case1.definition == EquipmentCase.Definition.REPARADO

        case2 = EquipmentCase.objects.get(legacy_id="LEG-CASE-02")
        assert case2.returned_model_text == "Equipo Desconocido Texto"
        assert case2.definition == EquipmentCase.Definition.HUESARIO

        # Idempotencia
        stats_re = import_legacy_cases_from_data(rows, dry_run=False)
        assert stats_re["updated"] == 2
        assert stats_re["created"] == 0

    def test_import_legacy_inventory_items_and_kardex(self):
        reg_oaxc = Region.objects.get(code="OAXC")
        model = EquipmentModel.objects.first()

        rows = [
            {
                "serial_number": "SN-MIGRA-001",
                "model_name": model.name,
                "region_code": "OAXC",
                "condition": "NUEVO",
                "warehouse": "STOCK",
            },
            {
                "serial_number": "SN-MIGRA-002",
                "model_name": "Nuevo Modelo Migrado",
                "brand": "Cisco",
                "region_code": "OAXC",
                "condition": "RECUPERADO",
                "warehouse": "PROYECTOS",
            },
            {
                # Inválido
                "serial_number": "",
                "model_name": model.name,
            },
        ]

        stats = import_legacy_inventory_items_from_data(rows, dry_run=False)
        assert stats["created"] == 2
        assert stats["skipped"] == 1

        # Verificar creación de items y movimientos de Kárdex
        item1 = InventoryItem.objects.get(serial_number="SN-MIGRA-001")
        assert item1.condition == InventoryItem.Condition.NUEVO
        assert item1.warehouse == InventoryItem.Warehouse.STOCK

        movement1 = InventoryMovement.objects.filter(serial_number="SN-MIGRA-001").first()
        assert movement1 is not None
        assert movement1.movement_type == InventoryMovement.MovementType.ENTRADA
        assert movement1.quantity == 1

        # Re-ejecutar sin duplicar movimientos
        stats_re = import_legacy_inventory_items_from_data(rows, dry_run=False)
        assert stats_re["updated"] == 2
        assert stats_re["created"] == 0
        assert InventoryMovement.objects.filter(serial_number="SN-MIGRA-001").count() == 1


@pytest.mark.django_db
class TestInventoryReconciliation:
    def test_reconcile_inventory_balances_match_surplus_and_shortage(self):
        reg = Region.objects.get(code="OAXC")
        user = User.objects.get(email="gerente.ssit@test-ssit.local")
        model = EquipmentModel.objects.first()
        now = timezone.now()

        # Generar saldo en sistema para model: 5 piezas en STOCK, NUEVO
        InventoryMovement.objects.create(
            equipment_model=model,
            movement_type=InventoryMovement.MovementType.ENTRADA,
            region=reg,
            warehouse=InventoryItem.Warehouse.STOCK,
            condition=InventoryItem.Condition.NUEVO,
            quantity=5,
            moved_at=now,
            confirmed=True,
            created_by=user,
        )

        physical_records = [
            # 1. Coincidencia exacta: 5 reportados vs 5 en sistema
            {
                "model_name": model.name,
                "region_code": "OAXC",
                "warehouse": "STOCK",
                "condition": "NUEVO",
                "physical_quantity": 5,
            },
            # 2. Sobrante: 8 reportados vs 0 en sistema
            {
                "model_name": model.name,
                "region_code": "OAXC",
                "warehouse": "PROYECTOS",
                "condition": "RECUPERADO",
                "physical_quantity": 8,
            },
            # 3. Faltante: 2 reportados vs 5 en sistema (con otra combinación)
            {
                "model_name": model.name,
                "region_code": "OAXC",
                "warehouse": "STOCK",
                "condition": "NUEVO",
                "physical_quantity": 2,
            },
        ]

        results = reconcile_inventory_balances(physical_records)
        summary = results["summary"]
        lines = results["lines"]

        assert summary["total_lines"] == 3
        assert summary["matched_count"] == 1
        assert summary["surplus_count"] == 1
        assert summary["shortage_count"] == 1
        assert lines[0]["status"] == "COINCIDE"
        assert lines[1]["status"] == "SOBRANTE"
        assert lines[2]["status"] == "FALTANTE"

        # Exportación a Excel
        buffer = generate_reconciliation_xlsx(results)
        assert isinstance(buffer, io.BytesIO)
        wb = openpyxl.load_workbook(buffer)
        assert "Conciliacion_Inventario" in wb.sheetnames
        ws = wb["Conciliacion_Inventario"]
        assert ws.cell(row=1, column=2).value == "Artículo / Modelo"
        assert ws.cell(row=2, column=10).value == "COINCIDE"


@pytest.mark.django_db
class TestETLManagementCommands:
    def test_import_legacy_data_command(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            vouchers_csv = os.path.join(tmpdir, "vouchers.csv")
            with open(vouchers_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["legacy_id", "region_code", "origin_type", "report_folio"])
                writer.writeheader()
                writer.writerow({"legacy_id": "CMD-V-01", "region_code": "OAXC", "origin_type": "VALE", "report_folio": "REP-CMD-1"})

            # Dry-Run
            call_command("import_legacy_data", "--vouchers-csv", vouchers_csv, "--dry-run")
            assert Voucher.objects.filter(legacy_id="CMD-V-01").count() == 0

            # Real
            call_command("import_legacy_data", "--vouchers-csv", vouchers_csv)
            assert Voucher.objects.filter(legacy_id="CMD-V-01").count() == 1

    def test_reconcile_inventory_command(self):
        model = EquipmentModel.objects.first()
        with tempfile.TemporaryDirectory() as tmpdir:
            phys_csv = os.path.join(tmpdir, "physical.csv")
            out_xlsx = os.path.join(tmpdir, "report.xlsx")

            with open(phys_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["model_name", "region_code", "warehouse", "condition", "physical_quantity"])
                writer.writeheader()
                writer.writerow({
                    "model_name": model.name,
                    "region_code": "OAXC",
                    "warehouse": "STOCK",
                    "condition": "NUEVO",
                    "physical_quantity": "10",
                })

            call_command("reconcile_inventory", "--physical-csv", phys_csv, "--export-xlsx", out_xlsx)
            assert os.path.exists(out_xlsx)
            assert os.path.getsize(out_xlsx) > 0


@pytest.mark.django_db
class TestReconciliationWebView:
    def test_reconciliation_page_render_and_post(self, client):
        u_gerente = User.objects.get(email="gerente.ssit@test-ssit.local")
        model = EquipmentModel.objects.first()
        client.force_login(u_gerente)
        url = reverse("reports:reconciliation")

        # 1. GET
        resp = client.get(url)
        assert resp.status_code == 200
        assert "Conciliación de Inventario Físico vs Kárdex" in resp.content.decode("utf-8")

        # 2. POST CSV
        csv_content = (
            f"model_name,region_code,warehouse,condition,physical_quantity\n"
            f"{model.name},OAXC,STOCK,NUEVO,15\n"
        ).encode("utf-8")
        uploaded_file = SimpleUploadedFile("conteo.csv", csv_content, content_type="text/csv")

        resp_post = client.post(url, {"physical_file": uploaded_file, "action": "reconcile"})
        assert resp_post.status_code == 200
        assert "Conciliación completada" in resp_post.content.decode("utf-8")
        assert "15" in resp_post.content.decode("utf-8")

        # 3. POST Export XLSX
        uploaded_file.seek(0)
        resp_export = client.post(url, {"physical_file": uploaded_file, "action": "export_xlsx"})
        assert resp_export.status_code == 200
        assert resp_export["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert 'attachment; filename="conciliacion_inventario.xlsx"' in resp_export["Content-Disposition"]
