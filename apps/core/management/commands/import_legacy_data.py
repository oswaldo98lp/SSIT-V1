"""Django management command to import legacy AppSheet CSV data into MariaDB."""
import csv
import os
from django.core.management.base import BaseCommand, CommandError
from apps.core.etl_services import (
    import_legacy_cases_from_data,
    import_legacy_inventory_items_from_data,
    import_legacy_vouchers_from_data,
)


class Command(BaseCommand):
    help = "Importa datos históricos de AppSheet (Vales, Casos de Devolución, Series de Inventario) de forma idempotente."

    def add_arguments(self, parser):
        parser.add_argument("--vouchers-csv", type=str, help="Ruta al archivo CSV de Vales Legacy")
        parser.add_argument("--cases-csv", type=str, help="Ruta al archivo CSV de Casos de Devolución Legacy")
        parser.add_argument("--items-csv", type=str, help="Ruta al archivo CSV de Piezas de Inventario / Series")
        parser.add_argument("--dry-run", action="store_true", help="Simula la importación sin guardar cambios")

    def _read_csv(self, filepath: str) -> list[dict]:
        if not os.path.exists(filepath):
            raise CommandError(f"El archivo '{filepath}' no existe.")
        with open(filepath, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            return list(reader)

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("--- MODO DE SIMULACIÓN (DRY-RUN) ACTIVO ---"))

        # 1. Vales
        if options["vouchers_csv"]:
            self.stdout.write(f"Procesando vales desde: {options['vouchers_csv']}...")
            rows = self._read_csv(options["vouchers_csv"])
            stats = import_legacy_vouchers_from_data(rows, dry_run=dry_run)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[Vales] Total: {stats['total']}, Creados: {stats['created']}, Actualizados: {stats['updated']}, Omitidos: {stats['skipped']}"
                )
            )
            for err in stats["errors"][:5]:
                self.stdout.write(self.style.ERROR(f"  - {err}"))

        # 2. Casos
        if options["cases_csv"]:
            self.stdout.write(f"Procesando casos desde: {options['cases_csv']}...")
            rows = self._read_csv(options["cases_csv"])
            stats = import_legacy_cases_from_data(rows, dry_run=dry_run)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[Casos] Total: {stats['total']}, Creados: {stats['created']}, Actualizados: {stats['updated']}, Omitidos: {stats['skipped']}"
                )
            )
            for err in stats["errors"][:5]:
                self.stdout.write(self.style.ERROR(f"  - {err}"))

        # 3. Piezas de Inventario
        if options["items_csv"]:
            self.stdout.write(f"Procesando piezas de inventario desde: {options['items_csv']}...")
            rows = self._read_csv(options["items_csv"])
            stats = import_legacy_inventory_items_from_data(rows, dry_run=dry_run)
            self.stdout.write(
                self.style.SUCCESS(
                    f"[Inventario] Total: {stats['total']}, Creados: {stats['created']}, Actualizados: {stats['updated']}, Omitidos: {stats['skipped']}"
                )
            )
            for err in stats["errors"][:5]:
                self.stdout.write(self.style.ERROR(f"  - {err}"))

        self.stdout.write(self.style.SUCCESS("Proceso de importación legacy completado."))
