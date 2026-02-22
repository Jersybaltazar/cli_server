"""
Punto de entrada de la aplicación FastAPI.
Configura CORS, middleware, y monta los routers.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_v1_router
from app.config import get_settings

settings = get_settings()


# ── Lifecycle ────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Eventos de inicio y cierre de la aplicación."""
    # Startup
    print(f"🚀 {settings.APP_NAME} iniciando en modo {settings.APP_ENV}")
    yield
    # Shutdown
    print(f"🛑 {settings.APP_NAME} cerrando...")


# ── App ──────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    description="API para SaaS de Gestión de Clínicas Especializadas",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global Exception Handler ────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Captura excepciones no manejadas para evitar exponer detalles internos."""
    if settings.DEBUG:
        # En desarrollo, mostrar detalles
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
    """Endpoint de health check para monitoreo."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "environment": settings.APP_ENV,
    }
