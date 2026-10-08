"""Management command to synchronize declarative transitions into TransitionRule table."""
from django.core.management.base import BaseCommand

from apps.transitions.services import sync_transitions_to_db


class Command(BaseCommand):
    help = "Synchronizes declarative TRANSITIONS_REGISTRY into the database."

    def handle(self, *args, **options):
        self.stdout.write("--- Sincronizando Reglas de Transicion ---")
        count = sync_transitions_to_db()
        self.stdout.write(self.style.SUCCESS(f"[OK] {count} reglas de transicion sincronizadas en la base de datos."))
