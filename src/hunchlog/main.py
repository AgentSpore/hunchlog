"""HunchLog FastAPI app: API + static frontend in a single uvicorn process."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from hunchlog.api import predictions, stats
from hunchlog.core.config import settings
from hunchlog.core.db import init_db, seed_predictions


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize the schema and seed demo data on startup."""
    await init_db()
    await seed_predictions()
    yield


app = FastAPI(title="HunchLog", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(predictions.router)
api_router.include_router(stats.router)
app.include_router(api_router)

# Mount the static frontend LAST so it never shadows /api routes. Guard on the
# directory existing — the backend ships without a frontend bundle.
if os.path.isdir(settings.frontend_dir):
    app.mount(
        "/",
        StaticFiles(directory=settings.frontend_dir, html=True),
        name="frontend",
    )
    logger.info("mounted static frontend from {}", settings.frontend_dir)
else:
    logger.info("frontend dir {} absent — serving API only", settings.frontend_dir)
