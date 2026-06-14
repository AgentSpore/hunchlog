"""Stats + health routes (mounted under /api/v1)."""

import aiosqlite
from fastapi import APIRouter, Depends

from hunchlog.api.predictions import db_conn
from hunchlog.schemas.prediction import StatsResponse
from hunchlog.services import prediction_service

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsResponse)
async def stats(conn: aiosqlite.Connection = Depends(db_conn)) -> StatsResponse:
    return await prediction_service.compute_stats(conn)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
