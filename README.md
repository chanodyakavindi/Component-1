# Child Nutrition Intelligence Platform

**AI-Assisted Malnutrition Risk & Progress Monitoring**

Undergraduate research prototype (Component 1 · J26-IT-399).  
**AI-assisted decision support. Clinical review required.**  
When the demo adapter is active the UI shows **DEMO MODEL — NOT FOR CLINICAL USE**.

Product name lives in `packages/contracts/product.json`.

---

## Architecture

| Service | Role |
|---|---|
| `apps/web` | Next.js clinical / research UI |
| `services/api` | FastAPI domain API, auth, RBAC, audit |
| `services/inference` | Model adapters (demo / sklearn / pytorch / onnx) |
| `workers/alerts` | Celery beat + worker for missed follow-ups |
| `ml/` | Training, evaluation, calibration, trajectory projection |
| PostgreSQL + Redis | Persistence and queue |

See `docs/ARCHITECTURE.md` for data flow.

---

## Prerequisites

- Docker and Docker Compose (recommended), or
- Node.js 22, Python 3.12, PostgreSQL 16, Redis 7

---

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

- Web: http://localhost:3000
- API + OpenAPI: http://localhost:8000/docs
- Inference: http://localhost:8001/health

First boot runs `alembic upgrade head` and seeds demonstration data.

---

## Demo accounts (development only)

Password for all seed users: `DemoPass123!`

| Role | Email |
|---|---|
| System administrator | admin@demo.local |
| Facility administrator | clinic-admin@demo.local |
| Doctor | doctor@demo.local |
| PHM / health worker | phm@demo.local |
| Nutritionist | nutritionist@demo.local |
| Researcher | researcher@demo.local |

Never use these passwords in production.

Canonical demonstration child: **C-1042** (risk 82% → 61% → 59%, stagnating).

---

## Environment

Copy `.env.example`. Important keys:

- `DATABASE_URL`, `REDIS_URL`
- `JWT_SECRET`, `JWT_REFRESH_SECRET`
- `MODEL_MODE=demo` (or `pytorch` / `sklearn` / `onnx`)
- `MODEL_ARTIFACT_PATH`
- `FRONTEND_URL`
- `NOTIFICATION_PROVIDER=mock`

---

## Database

```bash
cd services/api
alembic upgrade head
python -m app.seed
```

---

## Tests

```bash
# API
cd services/api && pytest -q

# ML
cd ../.. && PYTHONPATH=. pytest -q ml/tests

# Frontend
cd apps/web && npm test && npm run build
```

---

## Train models

From the repository root:

```bash
python -m ml.data.make_synthetic
python -m ml.training.train_baselines
python -m ml.training.train_multimodal
python -m ml.evaluation.compare_models
python -m ml.trajectory.fit_projection
```

Configs: `ml/configs/baseline.yaml`, `multimodal.yaml`, `longitudinal.yaml`.

If no experiment has been run, research pages show **No experimental result available**. Metrics are never fabricated.

---

## Switch Demo → real model

1. Train and place an artifact under `MODEL_ARTIFACT_PATH`.
2. Set in `.env`:

```text
MODEL_MODE=pytorch
MODEL_ARTIFACT_PATH=/artifacts/active/multimodal.pt
```

3. Restart the inference service. The frontend does not need changes. Demo badge disappears only when `mode` is not `DEMO`.

---

## Production

See `docs/DEPLOYMENT.md` and `docker-compose.prod.yml`.
