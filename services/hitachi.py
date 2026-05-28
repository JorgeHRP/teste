import time
import httpx
from base64 import b64encode
from typing import Any

from core.config import get_settings
from core.logging import get_logger
from core.exceptions import ExternalAPIError, AuthenticationError

logger = get_logger(__name__)
settings = get_settings()

BRAND = "HITACHI"

# In-memory token cache: {access_token, expires_at}
_token_cache: dict = {}


def _basic_auth_header() -> str:
    return b64encode(
        f"{settings.HITACHI_CLIENT_ID}:{settings.HITACHI_CLIENT_SECRET}".encode()
    ).decode()


async def _get_token() -> str:
    """Obtém ou reutiliza token Cognito (client_credentials)."""
    now = time.time()
    if _token_cache.get("access_token") and _token_cache.get("expires_at", 0) > now + 60:
        return _token_cache["access_token"]

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            settings.HITACHI_TOKEN_URL,
            data={"grant_type": "client_credentials"},
            headers={
                "Authorization": f"Basic {_basic_auth_header()}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

    if resp.status_code == 401:
        raise AuthenticationError(BRAND)
    if not resp.is_success:
        raise ExternalAPIError(BRAND, f"token HTTP {resp.status_code}", resp.status_code)

    result = resp.json()
    _token_cache["access_token"] = result["access_token"]
    _token_cache["expires_at"] = now + result.get("expires_in", 3600)
    return _token_cache["access_token"]


async def get_location_info() -> list[dict]:
    """GET /location_info — posição GPS e dados de identificação de todas as máquinas."""
    token = await _get_token()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{settings.HITACHI_BASE_URL}/location_info",
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code == 401:
        raise AuthenticationError(BRAND)
    if not resp.is_success:
        raise ExternalAPIError(BRAND, f"location_info HTTP {resp.status_code}", resp.status_code)
    return resp.json()


async def get_daily_report() -> list[dict]:
    """GET /daily_report — relatório diário de horas e consumo de todas as máquinas."""
    token = await _get_token()
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{settings.HITACHI_BASE_URL}/daily_report",
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code == 401:
        raise AuthenticationError(BRAND)
    if not resp.is_success:
        raise ExternalAPIError(BRAND, f"daily_report HTTP {resp.status_code}", resp.status_code)
    return resp.json()


def location_by_serial(locations: list[dict]) -> dict[str, dict]:
    """Indexa location_info por serial_no e pin_no para lookup O(1)."""
    index: dict[str, dict] = {}
    for loc in locations:
        if loc.get("serial_no"):
            index[loc["serial_no"]] = loc
        if loc.get("pin_no"):
            index[loc["pin_no"]] = loc
    return index


def daily_by_serial(reports: list[dict]) -> dict[str, dict]:
    """Indexa daily_report por serial_no e pin_no — mantém o mais recente por máquina."""
    index: dict[str, dict] = {}
    for rep in reports:
        serial = rep.get("serial_no")
        pin = rep.get("pin_no")
        # Guarda o mais recente (a API já devolve ordenado por data desc normalmente)
        for key in [k for k in [serial, pin] if k]:
            existing = index.get(key)
            if not existing or rep.get("generated_day", "") >= existing.get("generated_day", ""):
                index[key] = rep
    return index
