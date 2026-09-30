"""API FastAPI : endpoints métier + health + métriques Prometheus."""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.requests import Request

from app import db
from app.metrics import (
    GIT_SHA,
    APP_VERSION,
    http_request_duration_seconds,
    http_requests_total,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield
    db.close_db()


app = FastAPI(title="DevOps Eval API", version=APP_VERSION, lifespan=lifespan)


@app.middleware("http")
async def instrument_requests(request: Request, call_next):
    """Mesure chaque requête : compteur labellisé + latence par route."""
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    route = request.scope.get("route")
    endpoint = route.path if route is not None else request.url.path

    http_requests_total.labels(endpoint=endpoint, code=str(response.status_code)).inc()
    http_request_duration_seconds.labels(route=endpoint).observe(duration)
    return response


@app.get("/health")
def health() -> dict:
    """Healthcheck : reflète l'état réel (connectivité PostgreSQL incluse)."""
    if not db.database_ready():
        return Response(status_code=503, content='{"status":"unhealthy"}')
    return {"status": "ok", "database": "up", "sha": GIT_SHA}


@app.post("/api/visits")
def create_visit() -> dict:
    """Enregistre une visite en base et retourne le total."""
    total = db.record_visit()
    return {"visits": total}


@app.get("/api/visits")
def get_visits() -> dict:
    return {"visits": db.count_visits()}


@app.get("/metrics")
def metrics() -> Response:
    """Exposition des métriques au format texte Prometheus."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
