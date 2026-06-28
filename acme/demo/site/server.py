"""Erebor open intelligence platform — ASGI entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import API_TITLE, API_VERSION
from api.db import close_db, init_db
from api.routes import health, intelligence


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(title=API_TITLE, version=API_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(health.router, prefix="/api")
app.include_router(intelligence.router, prefix="/api")
