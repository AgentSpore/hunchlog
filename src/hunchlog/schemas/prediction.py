"""Pydantic v2 schemas for predictions, resolution, and stats."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class PredictionCreate(BaseModel):
    """Incoming payload to create a prediction.

    `probability` accepts either a 0..1 fraction or a 0..100 percent; the
    service normalizes to 0..1. Values outside 0..100 are rejected.
    """

    claim: str = Field(min_length=1)
    probability: float
    resolve_by: date
    category: str | None = None

    @field_validator("probability")
    @classmethod
    def _check_range(cls, v: float) -> float:
        if not 0.0 <= v <= 100.0:
            raise ValueError("probability must be within 0..1 or 0..100")
        return v


class PredictionRead(BaseModel):
    """A prediction row as returned by the API."""

    id: int
    claim: str
    probability: float
    resolve_by: date
    category: str | None
    status: Literal["open", "resolved"]
    outcome: int | None
    created_at: datetime
    resolved_at: datetime | None
    due: bool


class ResolveBody(BaseModel):
    """Body for resolving a prediction."""

    outcome: bool


class CalibrationPoint(BaseModel):
    """One non-empty calibration decile bucket."""

    bucket: str
    mean_prob: float
    hit_rate: float
    n: int


class StatsResponse(BaseModel):
    """Aggregate calibration stats."""

    brier: float | None
    label: str | None
    count_resolved: int
    count_open: int
    count_due: int
    calibration: list[CalibrationPoint]
