"""API integration tests over an ASGI httpx client."""

from datetime import date, timedelta

import pytest

pytestmark = pytest.mark.asyncio


async def test_health(client):
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_create_list_resolve_stats_happy_path(empty_client):
    resolve_by = (date.today() + timedelta(days=30)).isoformat()
    create = await empty_client.post(
        "/api/v1/predictions",
        json={"claim": "It will rain tomorrow", "probability": 70,
              "resolve_by": resolve_by, "category": "weather"},
    )
    assert create.status_code == 201
    body = create.json()
    pred_id = body["id"]
    assert body["probability"] == pytest.approx(0.7)
    assert body["status"] == "open"

    listing = await empty_client.get("/api/v1/predictions")
    assert listing.status_code == 200
    assert [p["id"] for p in listing.json()] == [pred_id]

    resolve = await empty_client.patch(
        f"/api/v1/predictions/{pred_id}/resolve", json={"outcome": True}
    )
    assert resolve.status_code == 200
    assert resolve.json()["status"] == "resolved"
    assert resolve.json()["outcome"] == 1

    stats = await empty_client.get("/api/v1/stats")
    s = stats.json()
    assert s["count_resolved"] == 1
    assert s["count_open"] == 0
    # single (0.7, 1) → (0.7-1)^2 = 0.09
    assert s["brier"] == pytest.approx(0.09)
    assert s["label"] == "sharp"


@pytest.mark.parametrize("value", [70, 0.7])
async def test_probability_normalization(empty_client, value):
    resolve_by = (date.today() + timedelta(days=10)).isoformat()
    resp = await empty_client.post(
        "/api/v1/predictions",
        json={"claim": "x", "probability": value, "resolve_by": resolve_by},
    )
    assert resp.status_code == 201
    assert resp.json()["probability"] == pytest.approx(0.7)


async def test_probability_out_of_range_rejected(empty_client):
    resolve_by = (date.today() + timedelta(days=10)).isoformat()
    resp = await empty_client.post(
        "/api/v1/predictions",
        json={"claim": "x", "probability": 150, "resolve_by": resolve_by},
    )
    assert resp.status_code == 422


async def test_due_flag(empty_client):
    past = (date.today() - timedelta(days=1)).isoformat()
    resp = await empty_client.post(
        "/api/v1/predictions",
        json={"claim": "overdue", "probability": 0.5, "resolve_by": past},
    )
    assert resp.json()["due"] is True

    future = (date.today() + timedelta(days=5)).isoformat()
    resp2 = await empty_client.post(
        "/api/v1/predictions",
        json={"claim": "later", "probability": 0.5, "resolve_by": future},
    )
    assert resp2.json()["due"] is False

    stats = (await empty_client.get("/api/v1/stats")).json()
    assert stats["count_open"] == 2
    assert stats["count_due"] == 1


async def test_delete(empty_client):
    resolve_by = (date.today() + timedelta(days=10)).isoformat()
    pred_id = (await empty_client.post(
        "/api/v1/predictions",
        json={"claim": "x", "probability": 0.5, "resolve_by": resolve_by},
    )).json()["id"]

    deleted = await empty_client.delete(f"/api/v1/predictions/{pred_id}")
    assert deleted.status_code == 204
    missing = await empty_client.get(f"/api/v1/predictions/{pred_id}")
    assert missing.status_code == 404
    again = await empty_client.delete(f"/api/v1/predictions/{pred_id}")
    assert again.status_code == 404


async def test_seed_stats_non_null(client):
    stats = (await client.get("/api/v1/stats")).json()
    assert stats["brier"] is not None
    assert stats["count_resolved"] == 14
    assert stats["count_open"] == 3
    assert stats["count_due"] >= 1
    assert len(stats["calibration"]) > 1


async def test_list_filter_and_due_in_seed(client):
    due = (await client.get("/api/v1/predictions?status=open")).json()
    assert any(p["due"] for p in due)
    # newest first ordering preserved.
    ids = [p["id"] for p in (await client.get("/api/v1/predictions")).json()]
    assert ids == sorted(ids, reverse=True)
