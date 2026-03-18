"""
Punto de entrada de la aplicación FastAPI.
Configura CORS, middleware, rate limiting, y monta los routers.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.router import api_v1_router
from app.config import get_settings
from app.database import engine
from app.rate_limit import limiter

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Lifecycle ────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Eventos de inicio y cierre de la aplicación."""
    # Startup — warmup del pool de conexiones y verificación de DB
    logger.info("%s iniciando en modo %s", settings.APP_NAME, settings.APP_ENV)
    async with engine.connect() as conn:
        await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    logger.info("Conexión a base de datos verificada")
    yield
    # Shutdown — cerrar pool de conexiones limpiamente
    logger.info("%s cerrando...", settings.APP_NAME)
    await engine.dispose()
    logger.info("Pool de conexiones cerrado")


# ── App ──────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    description="API para SaaS de Gestión de Clínicas Especializadas",
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── Rate Limiting ────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# ── Global Exception Handler ────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Captura excepciones no manejadas para evitar exponer detalles internos."""
    if settings.DEBUG:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc), "type": type(exc).__name__},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Error interno del servidor"},
    )


# ── Routers ──────────────────────────────────────────
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


# ── Health Check ─────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    """Endpoint de health check que verifica conectividad a la DB."""
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_status = "connected"
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "app": settings.APP_NAME,
                "database": "disconnected",
            },
        )
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "environment": settings.APP_ENV,
        "database": db_status,
    }
