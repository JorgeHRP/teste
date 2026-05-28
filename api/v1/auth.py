import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.security import create_token, get_current_user
from app.db.supabase import get_supabase
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    name: str | None
    cod_cliente: str


class MeResponse(BaseModel):
    user_id: str
    email: str
    name: str | None
    cod_cliente: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    db = get_supabase()
    resp = (
        db.table("users")
        .select("id, email, password_hash, name, cod_cliente")
        .eq("email", body.email.lower().strip())
        .single()
        .execute()
    )

    user = resp.data
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas.")

    if not bcrypt.checkpw(body.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas.")

    token = create_token(
        user_id=user["id"],
        email=user["email"],
        cod_cliente=user["cod_cliente"],
    )

    logger.info(f"Login: {user['email']}")
    return LoginResponse(
        access_token=token,
        user_id=user["id"],
        email=user["email"],
        name=user["name"],
        cod_cliente=user["cod_cliente"],
    )


@router.get("/me", response_model=MeResponse)
async def me(current_user: dict = Depends(get_current_user)):
    return MeResponse(
        user_id=current_user["sub"],
        email=current_user["email"],
        name=None,
        cod_cliente=current_user["cod_cliente"],
    )
