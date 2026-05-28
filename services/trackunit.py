import httpx
import asyncio
from typing import Any
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.exceptions import ExternalAPIError, AuthenticationError

logger = get_logger(__name__)
settings = get_settings()

BRAND = "TRACKUNIT"


def _auth_header() -> dict:
    return {"Authorization": f"Bearer {settings.TRACKUNIT_API_TOKEN}"}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def get_assets(page: int = 0, size: int = 100) -> dict:
    """GET /asset/v1/assets — lista paginada de ativos."""
    url = f"{settings.TRACKUNIT_BASE_URL}/asset/v1/assets"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            url,
            params={"page": page, "size": size},
            headers=_auth_header(),
        )
    if resp.status_code == 401:
        raise AuthenticationError(BRAND)
    if not resp.is_success:
        raise ExternalAPIError(BRAND, f"assets HTTP {resp.status_code}", resp.status_code)
    return resp.json()


async def get_all_assets() -> list[dict]:
    """Percorre todas as páginas e devolve todos os ativos."""
    first = await get_assets(page=0)
    total_pages = first.get("totalPages", 1)
    items = first.get("content", [])

    if total_pages > 1:
        tasks = [get_assets(page=p) for p in range(1, total_pages)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"[{BRAND}] Erro ao buscar página: {r}")
            else:
                items.extend(r.get("content", []))

    return items


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def get_asset_aemp(asset_id: str) -> dict:
    """GET /public/api/machine/machines/{id}/extended-information — dados AEMP."""
    url = f"{settings.TRACKUNIT_BASE_URL}/public/api/machine/machines/{asset_id}/extended-information"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=_auth_header())
    if not resp.is_success:
        logger.warning(f"[{BRAND}] extended-info HTTP {resp.status_code} para {asset_id}")
        return {}
    return resp.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
async def get_location(asset_id: str) -> dict | None:
    """GET /location/v1/locations — localização GeoJSON.
    NOTA: Rate limit de 1 req/s — chamadas individuais por máquina.
    ATENÇÃO: GeoJSON usa [longitude, latitude] — ordem inversa!
    """
    url = f"{settings.TRACKUNIT_BASE_URL}/location/v1/locations"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            url,
            params={"assetId": asset_id},
            headers=_auth_header(),
        )
    if not resp.is_success:
        return None
    data = resp.json()
    features = data.get("features", [])
    return features[0] if features else None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def get_active_alerts(asset_id: str) -> list[dict]:
    """GET /asset/v1/assets/{id}/alerts — alertas activos."""
    url = f"{settings.TRACKUNIT_BASE_URL}/asset/v1/assets/{asset_id}/alerts"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            url,
            params={"status": "ACTIVE"},
            headers=_auth_header(),
        )
    if not resp.is_success:
        logger.warning(f"[{BRAND}] alerts HTTP {resp.status_code} para {asset_id}")
        return []
    data = resp.json()
    return data.get("content", [])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def get_can_faults(asset_id: str) -> list[dict]:
    """POST /can-faults/v1/faults — falhas CAN bus recentes (últimas 24h)."""
    from datetime import datetime, timedelta, timezone
    url = f"{settings.TRACKUNIT_BASE_URL}/can-faults/v1/faults"
    now = datetime.now(timezone.utc)
    payload = {
        "machineIds": [asset_id],
        "startDate": (now - timedelta(hours=24)).isoformat(),
        "endDate": now.isoformat(),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=_auth_header())
    if not resp.is_success:
        logger.warning(f"[{BRAND}] can-faults HTTP {resp.status_code} para {asset_id}")
        return []
    data = resp.json()
    return data.get("faults", [])


def assets_by_serial(assets: list[dict]) -> dict[str, dict]:
    """Indexa ativos pelo serialNumber para lookup O(1)."""
    return {a["serialNumber"]: a for a in assets if a.get("serialNumber")}
