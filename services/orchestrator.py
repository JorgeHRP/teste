"""
Equipment Orchestrator
Ponto central que, dado um registo da BD, sabe qual API chamar,
busca os dados e usa o adapter para normalizar.
"""
import asyncio
from app.services import machines_db, hitachi, trackunit, johndeere
from app.adapters import equipment_adapter as adapter
from app.models.equipment import EquipmentModel
from app.db.cache import cache_get, cache_set
from app.core.logging import get_logger
from app.core.exceptions import UnsupportedBrandError

logger = get_logger(__name__)

# Tokens John Deere por cliente — em produção guardar no Supabase
_jd_tokens: dict[str, dict] = {}


def set_jd_token(cod_cliente: str, token_data: dict):
    _jd_tokens[cod_cliente] = token_data


def get_jd_token(cod_cliente: str) -> dict | None:
    return _jd_tokens.get(cod_cliente)


async def get_equipment(machine_db: dict, jd_access_token: str = None) -> EquipmentModel:
    """Devolve EquipmentModel completo para uma máquina."""
    cache_key = f"equipment:{machine_db['num_maquina']}"
    cached = await cache_get(cache_key)
    if cached:
        return EquipmentModel(**cached)

    brand = (machine_db.get("marca") or "").upper().strip()
    provider = machines_db.provider_for_brand(brand)
    serial = machine_db.get("chassis", "")

    try:
        if provider == "hitachi":
            result = await _get_hitachi(machine_db, serial)
        elif provider == "trackunit":
            result = await _get_trackunit(machine_db, serial)
        elif provider == "johndeere":
            result = await _get_johndeere(machine_db, serial, jd_access_token)
        else:
            logger.info(f"Sem telemetria para marca '{brand}' — devolvendo dados da BD.")
            result = adapter.from_db_only(machine_db)
    except Exception as e:
        logger.error(f"Erro ao buscar telemetria para {serial}: {e}")
        result = adapter.from_db_only(machine_db)

    await cache_set(cache_key, result.model_dump())
    return result


async def _get_hitachi(machine_db: dict, serial: str) -> EquipmentModel:
    locations, daily_reports = await asyncio.gather(
        hitachi.get_location_info(),
        hitachi.get_daily_report(),
    )
    loc_index = hitachi.location_by_serial(locations)
    daily_index = hitachi.daily_by_serial(daily_reports)

    chassis = machine_db.get("chassis", "")
    location = loc_index.get(chassis) or loc_index.get(serial) or {}
    daily = daily_index.get(chassis) or daily_index.get(serial) or {}

    return adapter.from_hitachi(machine_db, location, daily)


async def _get_trackunit(machine_db: dict, serial: str) -> EquipmentModel:
    assets = await trackunit.get_all_assets()
    index = trackunit.assets_by_serial(assets)
    asset = index.get(serial)

    if not asset:
        logger.warning(f"[TRACKUNIT] Ativo não encontrado para serial {serial}")
        return adapter.from_db_only(machine_db)

    asset_id = asset["id"]
    aemp, location, alerts, can_faults = await asyncio.gather(
        trackunit.get_asset_aemp(asset_id),
        trackunit.get_location(asset_id),
        trackunit.get_active_alerts(asset_id),
        trackunit.get_can_faults(asset_id),
    )
    return adapter.from_trackunit(machine_db, asset, aemp, location, alerts, can_faults)


async def _get_johndeere(machine_db: dict, serial: str, access_token: str | None) -> EquipmentModel:
    if not access_token:
        logger.warning(f"[JOHN DEERE] Sem token para {serial} — devolvendo dados da BD.")
        return adapter.from_db_only(machine_db)

    orgs = await johndeere.get_organizations(access_token)
    if not orgs:
        return adapter.from_db_only(machine_db)

    org_id = orgs[0]["id"]
    equipments = await johndeere.get_equipment(access_token, org_id)

    # Encontra o equipamento pelo serialNumber
    eq = next((e for e in equipments if e.get("serialNumber") == serial), None)
    if not eq:
        return adapter.from_db_only(machine_db)

    principal_id = eq["id"]
    alerts, engine_hours, breadcrumbs = await asyncio.gather(
        johndeere.get_machine_alerts(access_token, principal_id),
        johndeere.get_engine_hours(access_token, principal_id),
        johndeere.get_location_breadcrumbs(access_token, principal_id),
    )
    return adapter.from_johndeere(machine_db, eq, alerts, engine_hours, breadcrumbs)


async def get_equipment_list_for_client(cod_cliente: str, jd_access_token: str = None) -> list[EquipmentModel]:
    """Devolve todos os equipamentos de um cliente em paralelo."""
    machines = await machines_db.get_machines_by_client(cod_cliente)
    tasks = [get_equipment(m, jd_access_token) for m in machines]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    equipment_list = []
    for m, r in zip(machines, results):
        if isinstance(r, Exception):
            logger.error(f"Erro para {m.get('num_maquina')}: {r}")
            equipment_list.append(adapter.from_db_only(m))
        else:
            equipment_list.append(r)

    return equipment_list
