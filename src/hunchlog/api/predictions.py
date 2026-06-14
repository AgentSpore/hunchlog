"""Prediction CRUD + resolve routes (mounted under /api/v1/predictions)."""

from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query, status

import aiosqlite

from hunchlog.core.db import get_connection
from hunchlog.schemas.prediction import (
    PredictionCreate,
    PredictionRead,
    ResolveBody,
)
from hunchlog.services import prediction_service

router = APIRouter(prefix="/predictions", tags=["predictions"])


async def db_conn() -> AsyncIterator[aiosqlite.Connection]:
    """Dependency yielding a request-scoped sqlite connection."""
    async with get_connection() as conn:
        yield conn


@router.post("", response_model=PredictionRead, status_code=status.HTTP_201_CREATED)
async def create(
    payload: PredictionCreate,
    conn: aiosqlite.Connection = Depends(db_conn),
) -> PredictionRead:
    return await prediction_service.create_prediction(conn, payload)


@router.get("", response_model=list[PredictionRead])
async def list_all(
    status_filter: str | None = Query(default=None, alias="status"),
    category: str | None = Query(default=None),
    conn: aiosqlite.Connection = Depends(db_conn),
) -> list[PredictionRead]:
    return await prediction_service.list_predictions(conn, status_filter, category)


@router.get("/{prediction_id}", response_model=PredictionRead)
async def get_one(
    prediction_id: int,
    conn: aiosqlite.Connection = Depends(db_conn),
) -> PredictionRead:
    pred = await prediction_service.get_prediction(conn, prediction_id)
    if pred is None:
        raise HTTPException(status_code=404, detail="prediction not found")
    return pred


@router.patch("/{prediction_id}/resolve", response_model=PredictionRead)
async def resolve(
    prediction_id: int,
    body: ResolveBody,
    conn: aiosqlite.Connection = Depends(db_conn),
) -> PredictionRead:
    pred = await prediction_service.resolve_prediction(
        conn, prediction_id, body.outcome
    )
    if pred is None:
        raise HTTPException(status_code=404, detail="prediction not found")
    return pred


@router.delete("/{prediction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    prediction_id: int,
    conn: aiosqlite.Connection = Depends(db_conn),
) -> None:
    removed = await prediction_service.delete_prediction(conn, prediction_id)
    if not removed:
        raise HTTPException(status_code=404, detail="prediction not found")
