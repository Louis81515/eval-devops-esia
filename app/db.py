"""Accès PostgreSQL : pool de connexions et requêtes."""

import os

import psycopg
from psycopg_pool import ConnectionPool, PoolTimeout

DEFAULT_DATABASE_URL = "postgresql://app:app@localhost:5432/appdb"


def database_url() -> str:
    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


_pool: ConnectionPool | None = None


def init_db() -> None:
    """Initialise le pool et crée la table si nécessaire.

    La création de table est best-effort : si la base est injoignable au
    démarrage, l'app démarre quand même et /health rapportera l'erreur.
    """
    global _pool
    _pool = ConnectionPool(database_url(), min_size=1, max_size=5, timeout=2, open=True)
    try:
        with _pool.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS visits (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
    except (psycopg.Error, PoolTimeout, OSError) as exc:
        print(f"[db] base indisponible au démarrage : {exc}")


def close_db() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError("Base de données non initialisée")
    return _pool


def ping() -> bool:
    """Vrai si la base répond à un SELECT 1."""
    with pool().connection() as conn:
        return conn.execute("SELECT 1").fetchone() is not None


def record_visit() -> int:
    """Insère une visite et retourne le total en base."""
    with pool().connection() as conn:
        row = conn.execute(
            "INSERT INTO visits (created_at) VALUES (now()) RETURNING id"
        ).fetchone()
        if row is None:
            raise RuntimeError("Insertion de visite impossible")
        total = conn.execute("SELECT count(*) FROM visits").fetchone()
        return total[0]


def count_visits() -> int:
    with pool().connection() as conn:
        row = conn.execute("SELECT count(*) FROM visits").fetchone()
        return row[0]


def database_ready() -> bool:
    """Ping tolérant aux erreurs, utilisé par /health."""
    try:
        return ping()
    except (psycopg.Error, PoolTimeout, OSError):
        return False
