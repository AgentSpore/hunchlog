"""SQLite (aiosqlite) connection helper, schema init, and idempotent seed."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone

import aiosqlite
from loguru import logger

from hunchlog.core.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS predictions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    claim       TEXT    NOT NULL,
    probability REAL    NOT NULL,
    resolve_by  TEXT    NOT NULL,
    category    TEXT,
    status      TEXT    NOT NULL DEFAULT 'open',
    outcome     INTEGER,
    created_at  TEXT    NOT NULL,
    resolved_at TEXT
);
"""


@asynccontextmanager
async def get_connection() -> AsyncIterator[aiosqlite.Connection]:
    """Yield a connection with row factory set; commit on clean exit."""
    conn = await aiosqlite.connect(settings.db_path)
    conn.row_factory = aiosqlite.Row
    try:
        await conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        await conn.commit()
    finally:
        await conn.close()


async def init_db() -> None:
    """Create the schema if it does not yet exist."""
    async with get_connection() as conn:
        await conn.executescript(_SCHEMA)
    logger.info("database schema initialized at {}", settings.db_path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def seed_predictions() -> None:
    """Seed a realistic, slightly over-confident dataset if the table is empty."""
    async with get_connection() as conn:
        cur = await conn.execute("SELECT COUNT(*) AS n FROM predictions")
        row = await cur.fetchone()
        if row is not None and row["n"] > 0:
            logger.info("seed skipped — {} predictions already present", row["n"])
            return

        today = date.today()
        created = _now_iso()
        resolved = _now_iso()

        # (claim, probability 0..1, outcome 1=hit/0=miss) — deliberately
        # over-confident: several high-probability claims that missed.
        resolved_rows = [
            ("Team A wins the local league final", 0.90, 0),
            ("My flight departs on time", 0.85, 1),
            ("The product launch ships this quarter", 0.88, 0),
            ("It rains this weekend", 0.80, 0),
            ("The PR gets merged by Friday", 0.82, 1),
            ("Stock X closes up on earnings day", 0.75, 0),
            ("The client renews the contract", 0.70, 1),
            ("I finish the book this month", 0.65, 0),
            ("The interview leads to an offer", 0.60, 1),
            ("The bug is a one-line fix", 0.55, 0),
            ("The coin flip lands heads", 0.50, 1),
            ("The dark-horse candidate wins", 0.30, 0),
            ("The startup raises a Series A this year", 0.25, 1),
            ("It snows in the city this week", 0.10, 0),
        ]
        for claim, prob, outcome in resolved_rows:
            await conn.execute(
                """INSERT INTO predictions
                   (claim, probability, resolve_by, category, status,
                    outcome, created_at, resolved_at)
                   VALUES (?, ?, ?, ?, 'resolved', ?, ?, ?)""",
                (
                    claim,
                    prob,
                    (today - timedelta(days=7)).isoformat(),
                    "general",
                    outcome,
                    created,
                    resolved,
                ),
            )

        open_rows = [
            # (claim, probability, resolve_by offset in days, category)
            ("Bitcoin closes above $100k by year end", 0.40, 45, "markets"),
            ("The next release passes QA on the first try", 0.55, 14, "work"),
            # Already due — drives the resolve loop on first visit.
            ("The contractor finishes the kitchen on schedule", 0.65, -2, "life"),
        ]
        for claim, prob, offset, category in open_rows:
            await conn.execute(
                """INSERT INTO predictions
                   (claim, probability, resolve_by, category, status,
                    outcome, created_at, resolved_at)
                   VALUES (?, ?, ?, ?, 'open', NULL, ?, NULL)""",
                (
                    claim,
                    prob,
                    (today + timedelta(days=offset)).isoformat(),
                    category,
                    created,
                ),
            )

        logger.info(
            "seeded {} resolved + {} open predictions",
            len(resolved_rows),
            len(open_rows),
        )
