from app.db.supabase import get_supabase
from app.core.logging import get_logger

logger = get_logger(__name__)

# Marcas cobertas por cada integração
BRAND_PROVIDER = {
    "HITACHI":     "hitachi",
    "HAMM":        "trackunit",   # Wirtgen Group via Trackunit
    "VOGELE":      "trackunit",
    "WIRTGEN":     "trackunit",
    "JOHN DEERE":  "johndeere",
    "JOHN DEERE F":"johndeere",
    "GEHL":        "trackunit",   # Trackunit também cobre GEHL
}


async def get_machines_by_client(cod_cliente: str) -> list[dict]:
    """Devolve todas as máquinas de um cliente."""
    db = get_supabase()
    resp = (
        db.table("machines")
        .select("*")
        .eq("cod_cliente", cod_cliente)
        .execute()
    )
    return resp.data or []


async def get_all_machines() -> list[dict]:
    """Devolve todas as máquinas."""
    db = get_supabase()
    resp = db.table("machines").select("*").execute()
    return resp.data or []


async def get_machine_by_chassis(chassis: str) -> dict | None:
    """Devolve uma máquina pelo número de chassis/série."""
    db = get_supabase()
    resp = (
        db.table("machines")
        .select("*")
        .eq("chassis", chassis)
        .single()
        .execute()
    )
    return resp.data


async def get_machine_by_num(num_maquina: str) -> dict | None:
    """Devolve uma máquina pelo num_maquina."""
    db = get_supabase()
    resp = (
        db.table("machines")
        .select("*")
        .eq("num_maquina", num_maquina)
        .single()
        .execute()
    )
    return resp.data


async def get_clients() -> list[dict]:
    """Devolve lista distinta de clientes."""
    db = get_supabase()
    resp = (
        db.table("machines")
        .select("cod_cliente, nome_cliente, email, telefone1")
        .execute()
    )
    seen = set()
    clients = []
    for row in (resp.data or []):
        cid = row["cod_cliente"]
        if cid not in seen:
            seen.add(cid)
            clients.append(row)
    return clients


def provider_for_brand(brand: str) -> str | None:
    """Devolve o provider de telemetria para uma marca."""
    return BRAND_PROVIDER.get(brand.upper().strip())
