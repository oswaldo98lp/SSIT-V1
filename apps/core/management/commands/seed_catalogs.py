"""Idempotent seed command for System Catalogs from AppSheet specification."""
from django.core.management.base import BaseCommand

from apps.catalog.models import CatalogValue

CATALOGS_DATA = {
    # 1. Motivos de Solicitud de Vales (11 motivos)
    "REQUEST_REASON": [
        ("FALLA_EQUIPO", "Falla de equipo en punto de atención"),
        ("NUEVA_APERTURA", "Apertura de nuevo centro o sucursal"),
        ("RENOVACION_TECNOLOGICA", "Renovación tecnológica programada"),
        ("REASIGNACION", "Reasignación de equipo a usuario"),
        ("PROYECTO_ESPECIAL", "Proyecto especial o temporal"),
        ("PRESTAMO", "Préstamo provisional"),
        ("EXPANSION_CAPACIDAD", "Expansión de capacidad operativa"),
        ("RESPALDO_LOCAL", "Equipo de respaldo local"),
        ("DANO_ACCIDENTAL", "Daño accidental / Siniestro"),
        ("MIGRACION_SISTEMA", "Migración de sistema operativo"),
        ("OTRO", "Otro motivo justificado"),
    ],

    # 2. Tipos / Categorías de Material (5 categorías)
    "MATERIAL_CATEGORY": [
        ("EQUIPO_COMPUTO", "Equipo de Cómputo (PC, Laptop, All-in-One)"),
        ("IMPRESION_SCANNER", "Impresión y Escáner (Térmica, Láser, Escáner)"),
        ("REDES_COMUNICACIONES", "Redes y Telecomunicaciones (Switch, Router, AP)"),
        ("PERIFERICOS_ACCESORIOS", "Periféricos y Accesorios (Teclado, Mouse, Lector)"),
        ("REFACCIONES_PARTES", "Refacciones y Componentes Internos"),
    ],

    # 3. Motivos de Cancelación de Vale (6 motivos)
    "VOUCHER_CANCEL_REASON": [
        ("SOLICITUD_DUPLICADA", "Solicitud duplicada por error"),
        ("CANCELADO_POR_USUARIO", "Cancelado a petición del solicitante"),
        ("EQUIPO_NO_REQUERIDO", "Equipo ya no requerido en centro"),
        ("ERROR_DATOS_CENTRO", "Error en centro o datos de destino"),
        ("SIN_EXISTENCIA_ALMACEN", "Sin existencia disponible en almacén"),
        ("OTRO_CANCELACION", "Otro motivo de cancelación"),
    ],

    # 4. Motivos de Cancelación de Gerente (5 motivos)
    "MANAGER_CANCEL_REASON": [
        ("RECHAZO_POR_PRESUPUESTO", "Rechazado por restricciones presupuestales"),
        ("EQUIPO_EXISTENTE_EN_CENTRO", "Centro cuenta con equipo funcional"),
        ("NO_PROCEDE_DEVOLUCION", "No procede solicitud de devolución"),
        ("ERROR_EN_FOLIO", "Folio o datos incorrectos"),
        ("GERENTE_OTRO", "Otro criterio gerencial"),
    ],

    # 5. Motivos de Envío a Stock Directo (3 motivos)
    "STOCK_DIRECT_REASON": [
        ("EQUIPO_NUEVO_SIN_USO", "Equipo nuevo sin uso en empaque original"),
        ("SOBRANTE_PROYECTO", "Sobrante de proyecto en perfecto estado"),
        ("EQUIPO_OPERATIVO_LIBERADO", "Equipo operativo liberado por centro"),
    ],

    # 6. Dictámenes de Almacén (Dictámenes)
    "RULING": [
        ("REPARACION", "Pasa a Taller / Reparación"),
        ("TELECOMUNICACIONES", "Pasa a Telecomunicaciones"),
        ("OBSOLETO", "Equipo Obsoleto"),
        ("HUESARIO_DIRECTO", "Huesario Directo / Scrap"),
    ],

    # 7. Predefinición de Falla (3 predefiniciones)
    "PREDEFINITION": [
        ("FALLA_HARDWARE", "Falla de Hardware"),
        ("FALLA_SOFTWARE", "Falla de Software o Configuración"),
        ("OTRO", "Otro tipo de falla"),
    ],

    # 8. Motivos de Aplica Entrada a Taller
    "APPLIES_REASON": [
        ("DIAGNOSTICO_COMPLEJO", "Requiere diagnóstico especializado en taller"),
        ("CAMBIO_COMPONENTES", "Requiere reemplazo de componentes internos"),
        ("MANTENIMIENTO_MAYOR", "Mantenimiento preventivo mayor"),
    ],

    # 9. Notas de Insight
    "INSIGHT_NOTE": [
        ("ACTUALIZACION_SERIE", "Número de serie actualizado en Insight"),
        ("BAJA_ACTIVO_INSIGHT", "Baja de activo procesada en Insight"),
        ("ALTA_ACTIVO_INSIGHT", "Alta de nuevo activo registrada en Insight"),
        ("TRANSFERENCIA_INSIGHT", "Transferencia de custodia en Insight"),
    ],
}


class Command(BaseCommand):
    help = "Seeds standard system catalog values idempotently."

    def handle(self, *args, **options):
        self.stdout.write("--- Inicializando Catálogos del Sistema ---")
        total_created = 0
        total_updated = 0

        for catalog_key, items in CATALOGS_DATA.items():
            for idx, (code, label) in enumerate(items, start=1):
                obj, created = CatalogValue.objects.update_or_create(
                    catalog=catalog_key,
                    code=code,
                    defaults={
                        "label": label,
                        "sort": idx,
                        "is_active": True,
                    },
                )
                if created:
                    total_created += 1
                else:
                    total_updated += 1

            self.stdout.write(f"Catálogo '{catalog_key}': {len(items)} registros procesados.")

        self.stdout.write(
            self.style.SUCCESS(f"[OK] Catalogos listos: {total_created} creados, {total_updated} actualizados.")
        )
