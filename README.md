# devops-eval-api — Évaluation DevOps (ESIEA)

Petite API FastAPI + PostgreSQL servant de support à un pipeline complet :
Docker, CI/CD GitHub Actions, registry ghcr.io, déploiement automatisé et
métriques Prometheus.

## Endpoints

| Endpoint        | Description                                                        |
| --------------- | ------------------------------------------------------------------ |
| `GET /health`   | Healthcheck réel : renvoie 200 si l'API **et** PostgreSQL répondent, 503 sinon |
| `POST /api/visits` | Enregistre une visite en base et retourne le total                 |
| `GET /api/visits`  | Retourne le nombre de visites en base                             |
| `GET /metrics`  | Métriques au format texte Prometheus                               |

## Lancer le projet en local

Prérequis : Docker et Docker Compose v2.

```bash
# Lancer l'application + PostgreSQL en une commande :
docker compose up -d --build

# Vérifier :
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/visits
curl http://localhost:8000/metrics

# Arrêter :
docker compose down
```

Pour lancer les tests en local (Python 3.11/3.12 + PostgreSQL accessible sur
`localhost:5432`) :

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
DATABASE_URL=postgresql://app:app@localhost:5432/appdb .venv/bin/pytest tests/
```

## Docker

- **Dockerfile** : build multi-stage (builder → image finale), base
  `python:3.12-slim-bookworm` (tag précis, pas de `latest`), `HEALTHCHECK`
  interrogeant réellement `/health`, exécution en utilisateur non-root
  (`app`, uid 1000), `GIT_SHA` injecté au build via build-arg.
- **.dockerignore** : exclut au minimum `.git`, `.venv`, `tests`, etc.
- **docker-compose.yml** : deux services (`app` + `db` PostgreSQL 16),
  port `8000` exposé et mappé, healthchecks cohérents des deux côtés.

## CI (`.github/workflows/ci.yml`)

Déclenchée sur chaque `pull_request` et `push` sur `main`. Cinq jobs :

1. **lint** — `ruff check` + `ruff format --check`.
2. **lint-yaml** — `yamllint` sur tous les YAML du dépôt.
3. **test** — `strategy.matrix` Python 3.11 / 3.12. Un service PostgreSQL
   (container `postgres:16-alpine`) est démarré et **réellement utilisé** :
   les tests écrivent/lisent la table `visits` et contre-vérifient en base.
   Rapports JUnit + coverage uploadés via `upload-artifact`.
4. **tests-report** — télécharge les artifacts des deux matrices
   (`download-artifact`) et vérifie leur présence.
5. **build** — build de l'image Docker multi-stage.
6. **ci-ok** — job agrégateur : il est **vert uniquement si tous les autres
   jobs sont verts**. C'est lui qui doit être déclaré *required* dans les
   règles de protection de la branche `main` → le merge est bloqué si la CI
   n'est pas entièrement verte.

Le cache pip (natif `actions/setup-python`) est utilisé via l'action locale
composite : un second run sur la même branche affiche `pip cache hit` dans
les logs du step "Setup Python avec cache pip".

Chaque job a un `timeout-minutes`, et les permissions du workflow sont
réduites à `contents: read` (moindre privilège).

## CD (`.github/workflows/cd.yml`)

- Déclenchée **uniquement après une CI verte sur `main`** (via
  `workflow_run` sur le workflow CI, `conclusion == success`), ou
  manuellement via `workflow_dispatch` avec l'input `environment`
  (`production`).
- **build-push** : build de l'image et push sur **ghcr.io** (GitHub Registry)
  avec trois tags : `latest`, SHA court du commit, et semver auto
  (`0.1.<run_number>`). Authentification par `GITHUB_TOKEN` via stdin (le
  token n'apparaît jamais dans les logs).
- **deploy** : tourne sur un **runner self-hosted** (labels
  `self-hosted, production`) installé sur la machine cible — déploiement
  réel avec `docker compose pull` + `up -d`. Condition :
  `github.ref == 'refs/heads/main'` **ou** `workflow_dispatch`.
- **Vérification post-déploiement** : `curl --retry 3 --retry-delay 5
  --retry-connrefused` sur `http://localhost:8000/health`. Si le healthcheck
  échoue, le job échoue et un **rollback** est exécuté : re-pull de l'image
  du SHA précédent (mémorisé dans `~/.devops-eval-deployed-sha` sur le
  runner) puis `docker compose up -d` sur ce tag.

## Action composite réutilisable

`.github/actions/setup-python/action.yml` : setup du runtime Python **avec
cache pip natif** + installation des dépendances (2 steps). Les workflows
CI et CD l'appellent ; ce bloc n'est jamais dupliqué.

## Métriques (endpoint `/metrics`)

- `http_requests_total{endpoint, code}` — compteur de requêtes reçues,
  labellisé par route et code de statut HTTP.
- `http_request_duration_seconds_bucket{route}` — histogramme de latence
  par route (permet `histogram_quantile()` pour les p95/p99).
- `app_build_info{version, sha}` — jauge (valeur 1) exposant la version et
  le SHA du commit actuellement déployé.

Instrumentation réalisée par un middleware ASGI (`app/main.py`), déclaré
dans `app/metrics.py`.

## Règles d'alerte (`prometheus/alerts.yml`)

1. **HighErrorRate5xx** — `sum(rate(http_requests_total{code=~"5.."}[5m])) /
   sum(rate(http_requests_total[5m])) > 0.05`, `for: 5m`, severity
   `critical`. Seuil de 5 % : au-delà, une part significative des
   utilisateurs est impactée. `for: 5m` : une pointe brève (redémarrage)
   ne doit pas paginer ; 5 minutes consécutives = vrai incident.
2. **HighLatencyP95** — `histogram_quantile(0.95, rate(..._bucket[5m]) by
   (le, route)) > 0.5`, `for: 10m`, severity `warning`. Seuil 0,5 s : p95
   attendu < 100 ms pour cette API, 0,5 s traduit une dégradation franche
   tout en restant sous le seuil perceptible utilisateur (~1 s).
   `for: 10m` : la latence est volatile (GC, pics de trafic), 10 min évitent
   les faux positifs.

Pour les tester avec un vrai Prometheus :

```yaml
# prometheus.yml
scrape_configs:
  - job_name: devops-eval-api
    static_configs:
      - targets: ["localhost:8000"]
rule_files:
  - prometheus/alerts.yml
```

## Sécurité

- Permissions explicites en tête de chaque workflow (moindre privilège) :
  CI `contents: read` ; CD `contents: read` + `packages: write`.
- Authentification registry par `GITHUB_TOKEN` passé par stdin —
  jamais affiché dans les logs.
- L'application tourne en utilisateur non-root dans le conteneur.
- Aucun secret n'est stocké dans le dépôt.
