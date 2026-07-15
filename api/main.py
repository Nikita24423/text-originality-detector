from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routes import analytics, corpus, files, tasks
from api.schemas import HealthResponse
from config import get_settings
from database import check_db, close_pool, init_schema, pgvector_available
from scripts.create_db import ensure_database_exists
from services.qdrant_store import QdrantStore

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_ok, db_msg = check_db()
    if not db_ok:
        if "does not exist" in db_msg.lower() or "не существует" in db_msg.lower():
            created, cmsg = ensure_database_exists()
            print(f"[DB] {cmsg}")
            if created:
                db_ok, db_msg = check_db()
    if db_ok:
        print(f"[DB] {db_msg}")
        try:
            schema = init_schema()
            print(f"[DB] Схема: core=OK, pgvector={'да' if schema['pgvector'] else 'нет'}")
        except Exception as exc:
            print(f"[WARN] init_schema: {exc}")
    else:
        print(f"[FATAL] PostgreSQL: {db_msg}")
        print("[FATAL] Проверьте DATABASE_URL в .env (база nikita2, порт 5436)")
    yield
    close_pool()


app = FastAPI(
    title="Анализ оригинальности текста",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(analytics.router)
app.include_router(tasks.router)
app.include_router(corpus.router)
app.include_router(files.router)


@app.get("/health", response_model=HealthResponse)
async def health():
    settings = get_settings()
    qdrant = QdrantStore(
        settings.qdrant_url,
        settings.qdrant_collection,
        settings.rubert_collection,
        enabled=settings.qdrant_enabled,
    )
    db_ok, db_msg = check_db()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        database=db_ok,
        database_message=db_msg,
        pgvector=pgvector_available(),
        qdrant=qdrant.available,
        ml_workers_hint=settings.ml_workers,
    )


@app.get("/")
async def index():
    return FileResponse(TEMPLATES / "index.html")


@app.get("/style.css")
async def style():
    return FileResponse(TEMPLATES / "style.css", media_type="text/css")


@app.get("/app.js")
async def script():
    return FileResponse(TEMPLATES / "app.js", media_type="application/javascript")
