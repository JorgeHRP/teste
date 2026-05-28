"""
Equipment Adapter
Converte respostas brutas de cada API externa para o schema EquipmentModel
que a app mobile espera. É aqui que vive toda a lógica de mapeamento.
"""
from datetime import datetime, timezone
from typing import Any

from app.models.equipment import (
    EquipmentModel,
    EquipmentListItem,
    EquipmentStatus,
    AlertInfo,
    ErrorCode,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

# URL de placeholder quando não há imagem disponível
_PLACEHOLDER_IMAGE = "https://moviter.pt/wp-content/uploads/placeholder-machine.jpg"

# Mapa de imagens por modelo (pode crescer)
_MODEL_IMAGES: dict[str, str] = {
    "ZX135US-7B": "https://moviter.pt/wp-content/uploads/2017/06/Hitachi_ZX135-7-600x600.jpg",
}


def _image_for(brand: str, model: str) -> str:
    return _MODEL_IMAGES.get(model, _PLACEHOLDER_IMAGE)


def _time_ago(dt: datetime) -> str:
    """Transforma datetime em texto relativo — ex: 'Há 2h'."""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "Agora mesmo"
    if seconds < 3600:
        m = seconds // 60
        return f"Há {m}min"
    if seconds < 86400:
        h = seconds // 3600
        return f"Há {h}h"
    d = seconds // 86400
    return f"Há {d}d"


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


# ─── HITACHI ──────────────────────────────────────────────────────────────────

def from_hitachi(machine_db: dict, location: dict, daily: dict) -> EquipmentModel:
    """Constrói EquipmentModel a partir de dados HCME Dealer API + registo da BD.

    location — registo de location_info (GPS, modelo, data última comunicação)
    daily    — registo mais recente de daily_report (horas, combustível)
    """
    has_telemetry = bool(location or daily)

    brand = machine_db.get("marca", "HITACHI")
    model = location.get("model_name") or machine_db.get("modelo") or machine_db.get("designacao", "")
    serial = location.get("pin_no") or daily.get("pin_no") or machine_db.get("chassis", "")

    # Horas totais acumuladas (body_hour_meter em horas)
    hours = float(daily.get("body_hour_meter") or 0)

    # Consumo diário de combustível em litros
    daily_fuel_liters = float(daily.get("fuel_consumption") or 0) or None

    # GPS
    lat = float(location.get("latitude") or 0) or None
    lon = float(location.get("longitude") or 0) or None
    address = location.get("address") or machine_db.get("localidade", "")

    # Última comunicação — data da aquisição de dados ou do relatório diário
    last_comm_raw = (
        location.get("operation_information_acquisitiondate")
        or daily.get("generated_day")
    )
    if last_comm_raw and len(last_comm_raw) == 10:
        last_comm_iso = last_comm_raw + "T00:00:00+00:00"
    else:
        last_comm_iso = last_comm_raw or datetime.now(timezone.utc).isoformat()

    status = (
        EquipmentStatus.telemetry_no_alert if has_telemetry
        else EquipmentStatus.no_telemetry
    )

    return EquipmentModel(
        id=machine_db.get("num_maquina", serial),
        brand=brand,
        model=model,
        category=machine_db.get("familia", ""),
        serialNumber=serial,
        imageUrl=_image_for(brand, model),
        status=status,
        hasTelemetry=has_telemetry,
        hours=hours,
        fuelLevel=0.0,
        defLevel=0.0,
        lastCommunication=last_comm_iso,
        telemetryUrl="https://iot.hub.hitachicm-solutionlinkage.com/#/login?redirect=/dashboard",
        operatorManualUrl=None,
        location=address,
        latitude=lat,
        longitude=lon,
        nextRevisionDays=None,
        warrantyDays=None,
        tankCapacityLiters=None,
        avgFuelConsumption=daily_fuel_liters,
        avgAdBlueConsumption=None,
        weeklyAvgConsumption=None,
        peakConsumption=None,
        activeAlert=None,
        errorCodes=[],
    )


# ─── TRACKUNIT ────────────────────────────────────────────────────────────────

def from_trackunit(
    machine_db: dict,
    asset: dict,
    aemp: dict,
    location_feature: dict | None,
    alerts: list[dict],
    can_faults: list[dict],
) -> EquipmentModel:
    """Constrói EquipmentModel a partir de dados Trackunit + registo da BD."""
    brand = asset.get("brand") or machine_db.get("marca", "")
    model = asset.get("model") or machine_db.get("modelo") or machine_db.get("designacao", "")
    serial = asset.get("serialNumber") or machine_db.get("chassis", "")

    # Localização — GeoJSON usa [longitude, latitude]!
    lat, lon = None, None
    if location_feature:
        coords = location_feature.get("geometry", {}).get("coordinates", [])
        if len(coords) >= 2:
            lon, lat = coords[0], coords[1]

    props = location_feature.get("properties", {}) if location_feature else {}
    last_comm_raw = props.get("timestamp")
    last_comm_iso = last_comm_raw or datetime.now(timezone.utc).isoformat()
    last_comm_dt = _parse_iso(last_comm_raw)

    # Dados AEMP
    fuel_pct = float(aemp.get("FuelRemaining", {}).get("Percent", 0) or 0)
    def_pct = float(aemp.get("DEFRemaining", {}).get("Percent", 0) or 0)
    hours = float(aemp.get("CumulativeOperatingHours", {}).get("Hour", 0) or 0)
    tank_cap = float(aemp.get("FuelRemaining", {}).get("FuelTankCapacity", 0) or 0) or None

    # Alertas Trackunit
    active_alert = None
    critical = [a for a in alerts if a.get("severity") in ("CRITICAL", "HIGH")]
    if critical:
        a = critical[0]
        age = _parse_iso(a.get("triggeredAt"))
        active_alert = AlertInfo(
            title=a.get("alertType", "Alerta"),
            description=a.get("message", "Alerta activo."),
            timeAgo=_time_ago(age) if age else "Recentemente",
        )

    # Falhas CAN → ErrorCode[]
    error_codes = [
        ErrorCode(
            spn=str(f.get("spn", "")),
            fmi=str(f.get("fmi", "")),
            sourceAddress=str(f.get("sa", "")),
            description=f.get("description", ""),
        )
        for f in can_faults
    ]

    status = (
        EquipmentStatus.telemetry_with_alert if active_alert
        else EquipmentStatus.telemetry_no_alert if asset
        else EquipmentStatus.no_telemetry
    )

    return EquipmentModel(
        id=machine_db.get("num_maquina", serial),
        brand=brand,
        model=model,
        category=machine_db.get("familia", ""),
        serialNumber=serial,
        imageUrl=_image_for(brand, model),
        status=status,
        hasTelemetry=True,
        hours=hours,
        fuelLevel=fuel_pct,
        defLevel=def_pct,
        lastCommunication=last_comm_iso,
        telemetryUrl=None,
        operatorManualUrl=None,
        location=machine_db.get("localidade", ""),
        latitude=lat,
        longitude=lon,
        nextRevisionDays=None,
        warrantyDays=None,
        tankCapacityLiters=tank_cap,
        avgFuelConsumption=None,
        avgAdBlueConsumption=None,
        weeklyAvgConsumption=None,
        peakConsumption=None,
        activeAlert=active_alert,
        errorCodes=error_codes,
    )


# ─── JOHN DEERE ───────────────────────────────────────────────────────────────

def from_johndeere(
    machine_db: dict,
    equipment: dict,
    alerts: list[dict],
    engine_hours: dict,
    breadcrumbs: list[dict],
) -> EquipmentModel:
    """Constrói EquipmentModel a partir de dados John Deere + registo da BD."""
    brand = "John Deere"
    model = equipment.get("model") or machine_db.get("modelo") or machine_db.get("designacao", "")
    serial = equipment.get("serialNumber") or machine_db.get("chassis", "")

    # Horas
    hours = float(
        engine_hours.get("reading", {}).get("valueAsDouble", 0) or 0
    )

    # Localização — último breadcrumb
    lat, lon = None, None
    last_comm_iso = datetime.now(timezone.utc).isoformat()
    if breadcrumbs:
        last = breadcrumbs[-1]
        lat = last.get("lat")
        lon = last.get("lon")
        last_comm_iso = last.get("timestamp", last_comm_iso)
        fuel_snap = last.get("measurements", {})
    else:
        fuel_snap = {}

    fuel_pct = float(fuel_snap.get("fuelRemainingPercent", 0) or 0)

    # Alertas JD — severidade por cor
    active_alert = None
    red_alerts = [a for a in alerts if a.get("alertColor") == "RED"]
    if red_alerts:
        a = red_alerts[0]
        defn = a.get("definition", {})
        active_alert = AlertInfo(
            title=f"DTC {defn.get('suspectParameterName', '')}",
            description=f"FMI {defn.get('failureModeIndicator', '')} — {defn.get('sourceAddress', '')}",
            timeAgo="Recentemente",
        )

    # ErrorCodes JD
    error_codes = [
        ErrorCode(
            spn=str(a.get("definition", {}).get("suspectParameterName", "")),
            fmi=str(a.get("definition", {}).get("failureModeIndicator", "")),
            sourceAddress=str(a.get("definition", {}).get("sourceAddress", "")),
            description=a.get("alertColor", ""),
        )
        for a in alerts
        if a.get("definition")
    ]

    status = (
        EquipmentStatus.telemetry_with_alert if active_alert
        else EquipmentStatus.telemetry_no_alert if equipment
        else EquipmentStatus.no_telemetry
    )

    return EquipmentModel(
        id=machine_db.get("num_maquina", serial),
        brand=brand,
        model=model,
        category=machine_db.get("familia", ""),
        serialNumber=serial,
        imageUrl=_image_for(brand, model),
        status=status,
        hasTelemetry=True,
        hours=hours,
        fuelLevel=fuel_pct,
        defLevel=0.0,
        lastCommunication=last_comm_iso,
        telemetryUrl="https://operationscenter.deere.com",
        operatorManualUrl=None,
        location=machine_db.get("localidade", ""),
        latitude=lat,
        longitude=lon,
        nextRevisionDays=None,
        warrantyDays=None,
        tankCapacityLiters=None,
        avgFuelConsumption=None,
        avgAdBlueConsumption=None,
        weeklyAvgConsumption=None,
        peakConsumption=None,
        activeAlert=active_alert,
        errorCodes=error_codes,
    )


# ─── SEM TELEMETRIA ────────────────────────────────────────────────────────────

def from_db_only(machine_db: dict) -> EquipmentModel:
    """Máquina sem telemetria disponível — dados mínimos da BD."""
    brand = machine_db.get("marca", "")
    model = machine_db.get("modelo") or machine_db.get("designacao", "")
    return EquipmentModel(
        id=machine_db.get("num_maquina", machine_db.get("chassis", "")),
        brand=brand,
        model=model,
        category=machine_db.get("familia", ""),
        serialNumber=machine_db.get("chassis", ""),
        imageUrl=_image_for(brand, model),
        status=EquipmentStatus.no_telemetry,
        hasTelemetry=False,
        hours=0.0,
        fuelLevel=0.0,
        defLevel=0.0,
        lastCommunication=datetime.now(timezone.utc).isoformat(),
        telemetryUrl=None,
        operatorManualUrl=None,
        location=machine_db.get("localidade", ""),
        latitude=None,
        longitude=None,
        nextRevisionDays=None,
        warrantyDays=None,
        tankCapacityLiters=None,
        avgFuelConsumption=None,
        avgAdBlueConsumption=None,
        weeklyAvgConsumption=None,
        peakConsumption=None,
        activeAlert=None,
        errorCodes=[],
    )


# ─── HELPER: EquipmentModel → EquipmentListItem ────────────────────────────────

def to_list_item(eq: EquipmentModel) -> EquipmentListItem:
    return EquipmentListItem(
        id=eq.id,
        brand=eq.brand,
        model=eq.model,
        category=eq.category,
        serialNumber=eq.serialNumber,
        imageUrl=eq.imageUrl,
        status=eq.status,
        hasTelemetry=eq.hasTelemetry,
        hours=eq.hours,
        fuelLevel=eq.fuelLevel,
        defLevel=eq.defLevel,
        location=eq.location,
        activeAlert=eq.activeAlert,
    )
