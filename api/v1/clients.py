from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.services.machines_db import get_clients
from app.core.security import get_current_user
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/clients", tags=["Clients"])


class ClientItem(BaseModel):
    cod_cliente: str
    nome_cliente: str
    email: str | None
    telefone1: str | None


@router.get("", response_model=list[ClientItem])
async def list_clients(_: dict = Depends(get_current_user)):
    """Lista todos os clientes disponíveis. Requer autenticação."""
    try:
        return await get_clients()
    except Exception as e:
        logger.error(f"Erro ao listar clientes: {e}")
        raise HTTPException(status_code=500, detail=str(e))
