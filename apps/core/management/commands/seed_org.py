"""Idempotent seed command for Zones, Regions and sample Centers."""
from django.core.management.base import BaseCommand

from apps.org.models import Center, Region, Zone

# Zonas y regiones según Sección 11 del Prompt Maestro
ZONES_REGIONS_DATA = {
    "Zona 1": [
        ("OAXC", "Oaxaca", True, "Taller Habilitado Oaxaca"),
        ("CRDB", "Córdoba", False, ""),
        ("PBLA I", "Puebla I", False, ""),
        ("PBLA II", "Puebla II", False, ""),
        ("PZRC", "Poza Rica", False, ""),
        ("SCRZ", "Salina Cruz", False, ""),
        ("TXCC", "Tehuacán", False, ""),
        ("TXTP", "Tuxtepec", False, ""),
        ("VRCZ", "Veracruz", True, "Taller Habilitado Veracruz"),
        ("XLPA", "Xalapa", False, ""),
    ],
    "Zona 2": [
        ("AZCP", "Azcapotzalco", True, "Taller Central Azcapotzalco"),
        ("CLYA", "Celaya", False, ""),
        ("CTLZ", "Cuautitlán Izcalli", False, ""),
        ("LCRS", "Lázaro Cárdenas", False, ""),
        ("MORL", "Morelia", False, ""),
        ("QRTO", "Querétaro", False, ""),
        ("TCMC", "Tecámac", False, ""),
        ("TOLC", "Toluca", False, ""),
    ],
    "Zona 3": [
        ("ACPO", "Acapulco", False, ""),
        ("CNCN", "Cancún", False, ""),
        ("IGLA", "Iguala", False, ""),
        ("IXTP", "Ixtepec", False, ""),
        ("IZTP", "Iztapalapa", False, ""),
        ("MRDA", "Mérida", True, "Taller Sureste Mérida"),
        ("TXGT", "Tuxtla Gutiérrez", False, ""),
        ("CTZC", "Coatzacoalcos", False, ""),
        ("VLLH", "Villahermosa", False, ""),
    ],
    "Zona 4": [
        ("CLCN", "Culiacán", False, ""),
        ("HLLO", "Hermosillo", True, "Taller Noroeste Hermosillo"),
        ("LMCH", "Los Mochis", False, ""),
        ("LPAZ", "La Paz", False, ""),
        ("MXLI", "Mexicali", False, ""),
        ("TJNA", "Tijuana", False, ""),
        ("MZTN", "Mazatlán", False, ""),
    ],
    "Zona 5": [
        ("CDJZ", "Ciudad Juárez", False, ""),
        ("CHUA", "Chihuahua", False, ""),
        ("GDLP", "Guadalupe", False, ""),
        ("GPLC", "Gómez Palacio", False, ""),
        ("MNCV", "Monclova", False, ""),
        ("MTRY", "Monterrey", True, "Taller Norte Monterrey"),
        ("TMPC", "Tampico", False, ""),
    ],
    "Zona 6": [
        ("AGCS", "Aguascalientes", False, ""),
        ("CLMA", "Colima", False, ""),
        ("GDLJ", "Guadalajara", True, "Taller Occidente Guadalajara"),
        ("LEON", "León", False, ""),
        ("SNLP", "San Luis Potosí", False, ""),
        ("TLQP", "Tlaquepaque", False, ""),
        ("TPIC", "Tepic", False, ""),
    ],
}


class Command(BaseCommand):
    help = "Seeds standard Zones (6), Regions (47) and sample Centers idempotently."

    def handle(self, *args, **options):
        self.stdout.write("--- Inicializando Estructura Organizacional (Zonas, Regiones, Centros) ---")

        total_zones = 0
        total_regions = 0
        total_centers = 0

        center_number_counter = 100

        for zone_name, regions_list in ZONES_REGIONS_DATA.items():
            zone, _ = Zone.objects.get_or_create(name=zone_name)
            total_zones += 1

            for code, reg_name, is_workshop, workshop_name in regions_list:
                region, _ = Region.objects.update_or_create(
                    code=code,
                    defaults={
                        "name": reg_name,
                        "zone": zone,
                        "is_workshop": is_workshop,
                        "workshop_name": workshop_name,
                    },
                )
                total_regions += 1

                # Crear 2 centros sintéticos de muestra por región (Tienda y Almacén SSIT)
                for suffix in ["Tienda Principal", "Almacén Regional"]:
                    center_number_counter += 1
                    c_name = f"{reg_name} {suffix}"
                    Center.objects.update_or_create(
                        number=center_number_counter,
                        defaults={
                            "name": c_name,
                            "label": f"{center_number_counter} - {c_name}",
                            "region": region,
                            "is_active": True,
                        },
                    )
                    total_centers += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"[OK] Estructura lista: {total_zones} zonas, {total_regions} regiones, {total_centers} centros procesados."
            )
        )
