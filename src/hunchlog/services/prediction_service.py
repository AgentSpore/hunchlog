"""Prediction CRUD and stats aggregation over the sqlite store."""

from datetime import date, datetime, timezone

import aiosqlite

from hunchlog.schemas.prediction import (
    PredictionCreate,
    PredictionRead,
    StatsResponse,
)
from hunchlog.services import scoring


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_probability(value: float) -> float:
    """Map a 0..1 fraction or 0..100 percent onto 0..1.

    Values in (1, 100] are treated as percent and divided by 100. Values in
    [0, 1] are kept as-is. The caller validates the 0..100 input range.
    """
    return value / 100.0 if value > 1.0 else value


def _row_to_read(row: aiosqlite.Row, today: date) -> PredictionRead:
    resolve_by = date.fromisoformat(row["resolve_by"])
    due = row["status"] == "open" and resolve_by <= today
    return PredictionRead(
        id=row["id"],
        claim=row["claim"],
        probability=row["probability"],
        resolve_by=resolve_by,
        category=row["category"],
        status=row["status"],
        outcome=row["outcome"],
        created_at=datetime.fromisoformat(row["created_at"]),
        resolved_at=(
            datetime.fromisoformat(row["resolved_at"])
            if row["resolved_at"]
            else None
        ),
        due=due,
    )


async def create_prediction(
    conn: aiosqlite.Connection, payload: PredictionCreate
) -> PredictionRead:
    """Insert a new open prediction with normalized probability."""
    prob = normalize_probability(payload.probability)
    cur = await conn.execute(
        """INSERT INTO predictions
           (claim, probability, resolve_by, category, status,
            outcome, created_at, resolved_at)
           VALUES (?, ?, ?, ?, 'open', NULL, ?, NULL)""",
        (
            payload.claim,
            prob,
            payload.resolve_by.isoformat(),
            payload.category,
            _now_iso(),
        ),
    )
    new_id = cur.lastrowid
    created = await get_prediction(conn, new_id)
    assert created is not None  # noqa: S101 — just inserted this row
    return created


async def list_predictions(
    conn: aiosqlite.Connection,
    status: str | None = None,
    category: str | None = None,
) -> list[PredictionRead]:
    """List predictions, newest first, optionally filtered."""
    clauses: list[str] = []
    params: list[object] = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if category:
        clauses.append("category = ?")
        params.append(category)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    cur = await conn.execute(
        f"SELECT * FROM predictions {where} ORDER BY created_at DESC, id DESC",
        params,
    )
    rows = await cur.fetchall()
    today = date.today()
    return [_row_to_read(r, today) for r in rows]


async def get_prediction(
    conn: aiosqlite.Connection, prediction_id: int
) -> PredictionRead | None:
    """Fetch a single prediction by id, or None."""
    cur = await conn.execute(
        "SELECT * FROM predictions WHERE id = ?", (prediction_id,)
    )
    row = await cur.fetchone()
    return _row_to_read(row, date.today()) if row else None


async def resolve_prediction(
    conn: aiosqlite.Connection, prediction_id: int, outcome: bool
) -> PredictionRead | None:
    """Mark a prediction resolved with the given outcome; None if missing."""
    cur = await conn.execute(
        """UPDATE predictions
           SET status = 'resolved', outcome = ?, resolved_at = ?
           WHERE id = ?""",
        (1 if outcome else 0, _now_iso(), prediction_id),
    )
    if cur.rowcount == 0:
        return None
    return await get_prediction(conn, prediction_id)


async def delete_prediction(
    conn: aiosqlite.Connection, prediction_id: int
) -> bool:
    """Delete a prediction; return True if a row was removed."""
    cur = await conn.execute(
        "DELETE FROM predictions WHERE id = ?", (prediction_id,)
    )
    return cur.rowcount > 0


async def compute_stats(conn: aiosqlite.Connection) -> StatsResponse:
    """Aggregate Brier score, calibration curve, and counts."""
    cur = await conn.execute(
        "SELECT probability, status, outcome, resolve_by FROM predictions"
    )
    rows = await cur.fetchall()
    today = date.today()

    resolved: list[tuple[float, int]] = []
    count_open = 0
    count_due = 0
    for row in rows:
        if row["status"] == "resolved" and row["outcome"] is not None:
            resolved.append((row["probability"], int(row["outcome"])))
        elif row["status"] == "open":
            count_open += 1
            if date.fromisoformat(row["resolve_by"]) <= today:
                count_due += 1

    brier = scoring.brier_score(resolved)
    return StatsResponse(
        brier=brier,
        label=scoring.brier_label(brier),
        count_resolved=len(resolved),
        count_open=count_open,
        count_due=count_due,
        calibration=scoring.calibration_curve(resolved),
    )
