"""
PriceCompare API — FastAPI application entrypoint.
OpenTelemetry is initialised before any imports that would create spans.
"""
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.telemetry.otel import setup_telemetry, instrument_sqlalchemy_engine

# ── Bootstrap telemetry first ───────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

setup_telemetry(app)

from app.core.database import engine  # import AFTER otel is up
instrument_sqlalchemy_engine(engine.sync_engine)

from app.api import api_router

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

# ── Middleware ───────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_timing(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start
    response.headers["X-Process-Time"] = f"{duration:.4f}s"
    return response


# ── Startup / Shutdown ───────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    from app.core.database import engine, Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("%s started — environment: %s", settings.app_name, settings.otel_environment)


@app.on_event("shutdown")
async def shutdown():
    from app.core.database import engine
    await engine.dispose()
    logger.info("%s shutting down", settings.app_name)


# ── Routes ───────────────────────────────────────────────────────────────────
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health", tags=["ops"])
async def health():
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@app.get("/metrics-info", tags=["ops"])
async def metrics_info():
    """Prometheus metrics are exposed on port 9090."""
    return {"prometheus_url": "http://localhost:9090/metrics"}


# ── Global exception handler ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
