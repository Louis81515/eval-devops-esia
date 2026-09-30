# ---------- Étape 1 : builder ----------
# Image de base précise (pas de latest), variante slim.
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Étape 2 : image finale ----------
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# GIT_SHA est passé en build-arg par la CI/CD et exposé via /metrics.
ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}
ARG APP_VERSION=0.0.0
ENV APP_VERSION=${APP_VERSION}

# Utilisateur non-root : l'application ne tourne jamais en root.
RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=app:app app ./app

USER app
EXPOSE 8000

# Healthcheck réel : interroge l'endpoint /health qui vérifie PostgreSQL.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import sys,urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2); sys.exit(0 if r.status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
