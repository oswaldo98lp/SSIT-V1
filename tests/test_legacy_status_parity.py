"""Tests verifying parity of legacy_status(case) across all consolidation branches."""
import pytest
from apps.cases.models import EquipmentCase
from apps.cases.services import legacy_status
from apps.org.models import Region


@pytest.mark.django_db
class TestLegacyStatusParity:
    def test_finalizado_con_entrada(self):
        case = EquipmentCase(stage="FINALIZADO", definition="REPARADO")
        assert legacy_status(case) == "FINALIZADO CON ENTRADA A ALMACÉN"

    def test_finalizado_con_envio_huesario(self):
        case = EquipmentCase(stage="FINALIZADO", definition="HUESARIO")
        assert legacy_status(case) == "FINALIZADO CON ENVÍO A HUESARIO"

        case2 = EquipmentCase(stage="FINALIZADO_HUESARIO")
        assert legacy_status(case2) == "FINALIZADO CON ENVÍO A HUESARIO"

    def test_finalizado_sin_devolucion(self):
        case = EquipmentCase(stage="SIN_DEVOLUCION")
        assert legacy_status(case) == "FINALIZADO SIN DEVOLUCIÓN"

    def test_cancelaciones_status(self):
        case_canc = EquipmentCase(stage="CANCELADA")
        assert legacy_status(case_canc) == "CANCELADO PENDIENTE DE CONFIRMAR POR GERENTE"

        case_conf = EquipmentCase(stage="CANCELACION_CONFIRMADA")
        assert legacy_status(case_conf) == "CANCELADO PENDIENTE DE CONFIRMAR ENTRADA A ALMACÉN"

        case_fin = EquipmentCase(stage="FINALIZADO_CANCELADO")
        assert legacy_status(case_fin) == "CANCELADO FINALIZADO CON ENTRADA"

    def test_taller_habilitado_status(self):
        case_trans = EquipmentCase(stage="EN_TRANSITO_TALLER")
        assert legacy_status(case_trans) == "EN TRÁNSITO A TALLER"

        case_rev = EquipmentCase(stage="EN_REVISION_TALLER")
        assert legacy_status(case_rev) == "EN REVISIÓN EN TALLER"

        case_wait = EquipmentCase(stage="EN_ESPERA_REFACCION")
        assert legacy_status(case_wait) == "EN ESPERA DE REFACCIÓN"

    def test_huesario_status(self):
        case_scrap = EquipmentCase(stage="HUESARIO_CONFIRMADO")
        assert legacy_status(case_scrap) == "HUESARIO PENDIENTE DE RECIBIR POR ALMACÉN"

    def test_garantia_status(self):
        case_gar = EquipmentCase(stage="ENVIADO_GARANTIA")
        assert legacy_status(case_gar) == "EQUIPO ENVIADO A GARANTÍA NO CONFIRMADO POR JEFE"

        case_def_gar = EquipmentCase(stage="DEFINIDO", definition="GARANTIA", warranty_solution=None)
        assert legacy_status(case_def_gar) == "EQUIPO ENVIADO A GARANTÍA SIN SOLUCIÓN"

    def test_confirmacion_jefe_status(self):
        case_rep = EquipmentCase(stage="CONFIRMADO_JEFE", definition="REPARADO")
        assert legacy_status(case_rep) == "REPARADO PENDIENTE DE ENTRAR A ALMACÉN"

        case_hues = EquipmentCase(stage="CONFIRMADO_JEFE", definition="HUESARIO")
        assert legacy_status(case_hues) == "HUESARIO PENDIENTE DE RECIBIR POR ALMACÉN"

        case_other = EquipmentCase(stage="CONFIRMADO_JEFE", definition=None)
        assert legacy_status(case_other) == "CONFIRMADO POR JEFE"

    def test_center_and_office_pending_status(self):
        case_init = EquipmentCase(stage="PENDIENTE_CONFIRMAR")
        assert legacy_status(case_init) == "PENDIENTE CONFIRMAR DEVOLUCIÓN"

        case_rev = EquipmentCase(stage="EN_REVISION")
        assert legacy_status(case_rev) == "DEVOLUCIÓN EN REVISIÓN"

        # Confirmado sin folio
        case_no_folio = EquipmentCase(stage="CONFIRMADO", repair_folio="")
        assert legacy_status(case_no_folio) == "PENDIENTE DE GENERAR FOLIO DE REPARACIÓN"

        # Confirmado con folio pero sin ingeniero
        case_no_eng = EquipmentCase(stage="CONFIRMADO", repair_folio="FOL-123", assigned_engineer=None)
        assert legacy_status(case_no_eng) == "PENDIENTE DE ASIGNAR REPARACIÓN A INGENIERO"

        # Por reparar / Asignado
        case_rep = EquipmentCase(stage="POR_REPARAR")
        assert legacy_status(case_rep) == "PENDIENTE DE DEFINIR"

        # Definido general
        case_def = EquipmentCase(stage="DEFINIDO", definition="REPARADO")
        assert legacy_status(case_def) == "PENDIENTE CONFIRMAR DEFINICIÓN"

        # Desconocido
        case_unk = EquipmentCase(stage="UNKNOWN_STAGE")
        assert legacy_status(case_unk) == "UNKNOWN_STAGE"

