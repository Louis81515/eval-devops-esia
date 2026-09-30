import os

import psycopg
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://app:app@localhost:5432/appdb")

from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def clean_visits():
    url = os.environ["DATABASE_URL"]
    with psycopg.connect(url) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS visits (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.execute("TRUNCATE visits RESTART IDENTITY")
        conn.commit()
    yield
