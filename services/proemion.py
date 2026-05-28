"""
Proemion DataPlatform — SOAP/XML
Usado para máquinas do grupo Wirtgen: HAMM, VOGELE, WIRTGEN.
Requer zeep para parsing SOAP.
"""
from typing import Any
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import get_settings
from core.logging import get_logger
from core.exceptions import ExternalAPIError, AuthenticationError

logger = get_logger(__name__)
settings = get_settings()

BRAND = "PROEMION"


def _get_client(service_path: str):
    """Cria um cliente zeep para o serviço SOAP indicado."""
    try:
        from zeep import Client
        from zeep.transports import Transport
        from requests import Session
        from requests.auth import HTTPBasicAuth

        wsdl_url = f"{settings.PROEMION_BASE_URL}{service_path}?wsdl"
        session = Session()
        session.auth = HTTPBasicAuth(settings.PROEMION_USERNAME, settings.PROEMION_PASSWORD)
        transport = Transport(session=session, timeout=30)
        return Client(wsdl=wsdl_url, transport=transport)
    except Exception as e:
        raise ExternalAPIError(BRAND, f"Erro ao criar cliente SOAP: {e}")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def get_all_machines() -> list[dict]:
    """MachineService.getAllMachines — lista todas as máquinas."""
    try:
        client = _get_client(settings.PROEMION_MACHINE_SERVICE_PATH)
        result = client.service.getAllMachines()
        machines = result if isinstance(result, list) else (result.get("return", []) if result else [])
        logger.info(f"[{BRAND}] {len(machines)} máquinas obtidas.")
        return [_zeep_to_dict(m) for m in machines]
    except Exception as e:
        if "401" in str(e) or "Unauthorized" in str(e):
            raise AuthenticationError(BRAND)
        raise ExternalAPIError(BRAND, f"getAllMachines: {e}")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def get_machine_details(machine_id: int) -> dict:
    """AdminMachineService.getMachineDetails — detalhes completos de uma máquina."""
    try:
        client = _get_client(settings.PROEMION_ADMIN_SERVICE_PATH)
        result = client.service.getMachineDetails(machineId=machine_id)
        return _zeep_to_dict(result) if result else {}
    except Exception as e:
        raise ExternalAPIError(BRAND, f"getMachineDetails({machine_id}): {e}")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def get_runtime_machines() -> list[dict]:
    """RuntimeEntitiesService.getAllVisibleRuntimeMachines — estado em tempo real."""
    try:
        client = _get_client(settings.PROEMION_RUNTIME_SERVICE_PATH)
        result = client.service.getAllVisibleRuntimeMachines()
        machines = result if isinstance(result, list) else []
        return [_zeep_to_dict(m) for m in machines]
    except Exception as e:
        raise ExternalAPIError(BRAND, f"getAllVisibleRuntimeMachines: {e}")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def get_data_for_machine(machine_id: int, signals: list[str] = None) -> dict:
    """DataService — dados de sinais CAN para uma máquina."""
    default_signals = signals or [
        "engineRPM", "fuelPressure", "coolantTemp", "oilPressure",
        "hydraulicPressure", "batteryVoltage", "engineLoad",
        "defConsumptionRate", "dpfSootLevel",
    ]
    try:
        client = _get_client(settings.PROEMION_DATA_SERVICE_PATH)
        result = client.service.getMachineData(
            machineId=machine_id,
            signals=default_signals,
        )
        return _zeep_to_dict(result) if result else {}
    except Exception as e:
        logger.warning(f"[{BRAND}] getMachineData({machine_id}): {e}")
        return {}


def _zeep_to_dict(obj: Any) -> dict:
    """Converte objectos zeep (SOAP) para dicionários Python."""
    if obj is None:
        return {}
    if hasattr(obj, "__dict__"):
        return {
            k: _zeep_to_dict(v)
            for k, v in obj.__dict__.items()
            if not k.startswith("_")
        }
    if isinstance(obj, list):
        return [_zeep_to_dict(i) for i in obj]
    return obj


def machines_by_serial(machines: list[dict]) -> dict[str, dict]:
    """Indexa máquinas pelo número de série para lookup O(1)."""
    index = {}
    for m in machines:
        serial = m.get("serialNumber") or m.get("chassisNumber") or m.get("vin")
        if serial:
            index[str(serial)] = m
    return index
