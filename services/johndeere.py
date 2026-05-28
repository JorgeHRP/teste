import httpx
import time
from typing import Any
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import get_settings
from core.logging import get_logger
from core.exceptions import ExternalAPIError, AuthenticationError

logger = get_logger(__name__)
settings = get_settings()

BRAND = "JOHN DEERE"

# Token cache em memória — em produção guardar no Supabase por organização
_token_cache: dict[str, Any] = {}


async def exchange_code_for_token(code: str) -> dict:
    """Troca o authorization code por access + refresh token."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            settings.JOHN_DEERE_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.JOHN_DEERE_REDIRECT_URI,
                "client_id": settings.JOHN_DEERE_CLIENT_ID,
                "client_secret": settings.JOHN_DEERE_CLIENT_SECRET,
            },
        )
    if not resp.is_success:
        raise AuthenticationError(BRAND)
    token_data = resp.json()
    token_data["expires_at"] = time.time() + token_data.get("expires_in", 3600)
    return token_data


async def refresh_access_token(refresh_token: str) -> dict:
    """Renova o access token usando o refresh token."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            settings.JOHN_DEERE_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": settings.JOHN_DEERE_CLIENT_ID,
                "client_secret": settings.JOHN_DEERE_CLIENT_SECRET,
            },
        )
    if not resp.is_success:
        raise AuthenticationError(BRAND)
    token_data = resp.json()
    token_data["expires_at"] = time.time() + token_data.get("expires_in", 3600)
    return token_data


def get_auth_url(state: str) -> str:
    """Gera a URL de autorização OAuth para redirecionar o utilizador."""
    params = {
        "response_type": "code",
        "client_id": settings.JOHN_DEERE_CLIENT_ID,
        "redirect_uri": settings.JOHN_DEERE_REDIRECT_URI,
        "scope": settings.JOHN_DEERE_SCOPES,
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{settings.JOHN_DEERE_AUTH_URL}?{query}"


def _auth_header(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.deere.axiom.v3+json",
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def get_organizations(access_token: str) -> list[dict]:
    """GET /organizations — lista de organizações do utilizador."""
    url = f"{settings.JOHN_DEERE_BASE_URL}/organizations"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=_auth_header(access_token))
    if resp.status_code == 401:
        raise AuthenticationError(BRAND)
    if not resp.is_success:
        raise ExternalAPIError(BRAND, f"organizations HTTP {resp.status_code}", resp.status_code)
    data = resp.json()
    return data.get("values", [])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def get_equipment(access_token: str, org_id: str) -> list[dict]:
    """GET /organizations/{orgId}/equipment — equipamentos da organização."""
    url = f"{settings.JOHN_DEERE_BASE_URL}/organizations/{org_id}/equipment"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=_auth_header(access_token))
    if resp.status_code == 401:
        raise AuthenticationError(BRAND)
    if not resp.is_success:
        raise ExternalAPIError(BRAND, f"equipment HTTP {resp.status_code}", resp.status_code)
    data = resp.json()
    return data.get("values", [])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def get_machine_alerts(access_token: str, principal_id: str) -> list[dict]:
    """GET /machines/{principalId}/alerts — alertas DTC, geofence e manutenção."""
    url = f"{settings.JOHN_DEERE_BASE_URL}/machines/{principal_id}/alerts"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=_auth_header(access_token))
    if not resp.is_success:
        logger.warning(f"[{BRAND}] alerts HTTP {resp.status_code} para {principal_id}")
        return []
    data = resp.json()
    return data.get("values", [])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def get_engine_hours(access_token: str, principal_id: str) -> dict:
    """GET /machines/{principalId}/engineHours — horas de motor."""
    url = f"{settings.JOHN_DEERE_BASE_URL}/machines/{principal_id}/engineHours"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=_auth_header(access_token))
    if not resp.is_success:
        return {}
    return resp.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
async def get_location_breadcrumbs(access_token: str, principal_id: str) -> list[dict]:
    """GET /machines/{principalId}/locationHistory — histórico de localização."""
    url = f"{settings.JOHN_DEERE_BASE_URL}/machines/{principal_id}/locationHistory"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=_auth_header(access_token))
    if not resp.is_success:
        return []
    data = resp.json()
    return data.get("values", [])
