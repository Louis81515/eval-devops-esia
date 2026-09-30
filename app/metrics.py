"""Instrumentation Prometheus de l'application."""

import os

from prometheus_client import Counter, Gauge, Histogram

GIT_SHA = os.getenv("GIT_SHA", "dev")
APP_VERSION = os.getenv("APP_VERSION", "0.0.0")

# Compteur de requêtes reçues, labellisé par endpoint et code HTTP de retour.
http_requests_total = Counter(
    "http_requests_total",
    "Nombre total de requêtes HTTP reçues",
    ["endpoint", "code"],
)

# Histogramme de latence par route : permet de calculer p95 / p99
# via histogram_quantile() côté Prometheus.
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "Durée des requêtes HTTP en secondes",
    ["route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# Jauge exposant la version / le SHA actuellement déployé (valeur fixée à 1,
# l'information est portée par les labels).
app_build_info = Gauge(
    "app_build_info",
    "Informations de build de l'application (version et SHA du commit)",
    ["version", "sha"],
)
app_build_info.labels(version=APP_VERSION, sha=GIT_SHA).set(1)
