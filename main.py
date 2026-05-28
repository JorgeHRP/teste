from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.exceptions import (
    ExternalAPIError,
    EquipmentNotFoundError,
    AuthenticationError,
    UnsupportedBrandError,
)
from app.api.v1 import equipment, clients, auth_johndeere, auth

settings = get_settings()
logger = get_logger(__name__)

_is_dev = settings.APP_ENV == "development"

app = FastAPI(
    title="Moviter Equipment API",
    description="API de telemetria de equipamentos — Moviter App",
    version="1.0.0",
    docs_url="/docs" if _is_dev else None,
    redoc_url="/redoc" if _is_dev else None,
)

# CORS — ajustar origins em produção
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.APP_ENV == "development" else ["https://moviter.pt"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1")
app.include_router(equipment.router, prefix="/api/v1")
app.include_router(clients.router, prefix="/api/v1")
app.include_router(auth_johndeere.router, prefix="/api/v1")


# ── Exception handlers ────────────────────────────────────────────────────────
@app.exception_handler(EquipmentNotFoundError)
async def equipment_not_found_handler(req: Request, exc: EquipmentNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(AuthenticationError)
async def auth_error_handler(req: Request, exc: AuthenticationError):
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(ExternalAPIError)
async def external_api_handler(req: Request, exc: ExternalAPIError):
    return JSONResponse(status_code=502, content={"detail": str(exc), "provider": exc.provider})


@app.exception_handler(UnsupportedBrandError)
async def unsupported_brand_handler(req: Request, exc: UnsupportedBrandError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "env": settings.APP_ENV}


@app.get("/", tags=["Health"])
async def root():
    return {"message": "Moviter Equipment API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.APP_PORT, reload=True)
