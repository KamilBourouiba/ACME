import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from acme import __version__
from acme.api.routes import router
from acme.api.demo_routes import router as demo_router
from acme.api.chat_routes import router as chat_router
from acme.api.quant_routes import router as quant_router
from acme.config import settings
from acme.db.session import init_db
from acme.graph.neo4j_client import neo4j_client
from acme.middleware.tenant import TenantMiddleware

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("acme")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ACME v%s", __version__)
    await init_db()
    await neo4j_client.connect()

    if settings.chat_clean_legacy_demo_on_start:
        from acme.chat.cleanup import purge_legacy_demo_data

        try:
            await purge_legacy_demo_data()
        except Exception:
            logger.exception("Legacy demo cleanup failed")

    if settings.demo_enabled:
        from acme.demo.service import demo_service

        await demo_service.start()
    if settings.quant_demo_enabled:
        from acme.quant.service import quant_service

        await quant_service.start()
    yield
    if settings.demo_enabled:
        from acme.demo.service import demo_service

        await demo_service.stop()
    if settings.quant_demo_enabled:
        from acme.quant.service import quant_service

        await quant_service.stop()
    await neo4j_client.close()
    logger.info("ACME shutdown complete")


app = FastAPI(
    title="ACME — Adaptive Cognitive Memory Engine",
    description="Persistent, evolving knowledge system powered by Ollama",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(TenantMiddleware)

app.include_router(router, prefix="/api/v1", tags=["acme"])
app.include_router(demo_router, prefix="/api/v1", tags=["demo"])
app.include_router(chat_router, prefix="/api/v1", tags=["chat"])
app.include_router(quant_router, prefix="/api/v1", tags=["quant"])


@app.get("/")
async def root():
    if settings.chat_demo_enabled:
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url="/api/v1/chat/")
    return {
        "name": "ACME",
        "version": __version__,
        "docs": "/docs",
        "health": "/api/v1/health",
    }
