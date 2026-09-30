"""Tests de /health : vérifie un vrai comportement (code HTTP + contenu)."""

import psycopg
from fastapi.testclient import TestClient

from app.main import app


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "up"


def test_health_reflects_real_database_state():
    """/health doit renvoyer 503 quand PostgreSQL est injoignable."""
    import os

    os.environ["DATABASE_URL"] = "postgresql://app:app@localhost:59999/nope"
    try:
        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 503
    finally:
        os.environ["DATABASE_URL"] = "postgresql://app:app@localhost:5432/appdb"


def test_database_is_actually_used(client):
    """L'endpoint visites lit/écrit réellement dans PostgreSQL."""
    before = client.get("/api/visits").json()["visits"]
    client.post("/api/visits")
    after = client.get("/api/visits").json()["visits"]
    assert after == before + 1

    # Contre-vérification directement en base
    with psycopg.connect("postgresql://app:app@localhost:5432/appdb") as conn:
        row = conn.execute("SELECT count(*) FROM visits").fetchone()
    assert row[0] == after
