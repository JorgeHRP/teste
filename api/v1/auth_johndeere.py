from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
import secrets

from app.services import johndeere, orchestrator
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/auth/johndeere", tags=["Auth — John Deere"])

# Estado temporário anti-CSRF (em produção usar Redis)
_states: dict[str, str] = {}


@router.get("/login")
async def jd_login(cod_cliente: str = Query(...)):
    """
    Redireciona para a página de login John Deere.
    Passa cod_cliente no state para associar o token ao cliente.
    """
    state = secrets.token_urlsafe(16)
    _states[state] = cod_cliente
    url = johndeere.get_auth_url(state)
    return RedirectResponse(url)


@router.get("/callback")
async def jd_callback(
    code: str = Query(...),
    state: str = Query(...),
):
    """
    Callback OAuth — troca o code por token e guarda em memória.
    Em produção persistir no Supabase por cod_cliente.
    """
    cod_cliente = _states.pop(state, None)
    if not cod_cliente:
        raise HTTPException(status_code=400, detail="State inválido ou expirado.")

    try:
        token_data = await johndeere.exchange_code_for_token(code)
        orchestrator.set_jd_token(cod_cliente, token_data)
        logger.info(f"Token John Deere guardado para cliente {cod_cliente}.")
        return {"message": "Autenticação John Deere bem-sucedida.", "cod_cliente": cod_cliente}
    except Exception as e:
        logger.error(f"Erro no callback JD: {e}")
        raise HTTPException(status_code=400, detail=str(e))


class TokenRequest(BaseModel):
    cod_cliente: str
    access_token: str
    refresh_token: str | None = None
    expires_in: int = 3600


@router.post("/token")
async def set_jd_token_manual(body: TokenRequest):
    """
    Permite injectar um token John Deere manualmente (útil para testes).
    """
    import time
    token_data = body.model_dump()
    token_data["expires_at"] = time.time() + body.expires_in
    orchestrator.set_jd_token(body.cod_cliente, token_data)
    return {"message": "Token guardado.", "cod_cliente": body.cod_cliente}
