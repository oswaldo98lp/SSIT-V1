"""Django management command to perform inventory physical reconciliation against Kardex balances."""
import csv
import os
from django.core.management.base import BaseCommand, CommandError
from apps.core.etl_services import generate_reconciliation_xlsx, reconcile_inventory_balances


class Command(BaseCommand):
    help = "Ejecuta la conciliación de existencias físicas contra los movimientos de Kárdex y reporta discrepancias."

    def add_arguments(self, parser):
        parser.add_argument("--physical-csv", type=str, required=True, help="Ruta al archivo CSV con conteos físicos de inventario")
        parser.add_argument("--export-xlsx", type=str, help="Ruta destino para exportar el reporte XLSX con discrepancias")

    def handle(self, *args, **options):
        csv_path = options["physical_csv"]
        if not os.path.exists(csv_path):
            raise CommandError(f"El archivo '{csv_path}' no existe.")

        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

        self.stdout.write(f"Iniciando conciliación de {len(rows)} registros físicos...")
        results = reconcile_inventory_balances(rows)
        summary = results["summary"]

        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS("RESUMEN DE CONCILIACIÓN DE INVENTARIO"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"Líneas evaluadas:    {summary['total_lines']}")
        self.stdout.write(f"Coincidencias (OK):  {summary['matched_count']}")
        self.stdout.write(self.style.WARNING(f"Sobrantes (+):       {summary['surplus_count']}"))
        self.stdout.write(self.style.ERROR(f"Faltantes (-):       {summary['shortage_count']}"))
        self.stdout.write(f"Tasa de Concordancia: {summary['match_rate']}%")
        self.stdout.write("=" * 60)

        if options.get("export_xlsx"):
            export_path = options["export_xlsx"]
            buffer = generate_reconciliation_xlsx(results)
            with open(export_path, "wb") as out_f:
                out_f.write(buffer.getvalue())
            self.stdout.write(self.style.SUCCESS(f"Reporte de conciliación exportado exitosamente a: {export_path}"))
