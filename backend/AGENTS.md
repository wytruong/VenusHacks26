# AGENTS.md

## Environment Requirement

Before running Python, installing packages, inspecting data with scripts, or executing backend commands, use the Python 3.12 virtual environment that contains this project's runtime stack:

```bash
source /Users/benj/Documents/Coding/cardiac_mvp/.venv/bin/activate
cd /Users/benj/Documents/Coding/VenusHacks26/backend
python --version
```

Expected major/minor version: `Python 3.12`.

Do not use the system Python for backend commands unless the user explicitly asks.

## Project Context

This backend contains:

- A FastAPI screening API under `backend/`.
- Prenatal CVD follow-up prioritization inference code under `scripts/maternal/`.
- Shipped model artifacts under `models/cdc-natality/default/`.
- ECG/data normalization scripts and docs under `scripts/health/`, `scripts/normalization/`, and `docs/`.
- Backend API tests under `tests/`.

The FastAPI app entrypoint is `backend.main:app`.

## API Code Organization

- Routes live in `backend/routers/`.
- Pydantic request schemas live in `backend/schemas/`.
- Model input mapping and service wrappers live in `backend/services/`.
- API tests live in `tests/test_prenatal_cvd_api.py`.

Current runtime endpoints:

- `GET /health`
- `POST /api/screening/prenatal-cvd`

The prenatal endpoint accepts frontend-shaped camelCase fields and maps them to the shipped model's internal feature names before calling `scripts.maternal.prenatal_cvd_model_a.predict_prenatal_cvd_risk`.

## Running the API

From the backend directory with the required venv active:

```bash
uvicorn backend.main:app --reload
```

Then check:

```bash
curl http://127.0.0.1:8000/health
```

## Running Tests

From the backend directory with the required venv active:

```bash
python -m pytest
```

For the API test file only:

```bash
python -m pytest tests/test_prenatal_cvd_api.py
```

## API Guardrails

- Keep model artifacts under `models/cdc-natality/default/` unchanged unless the user explicitly asks to update shipped artifacts.
- The prenatal endpoint supports `pregnancyMode: "prenatal"` only; do not add postpartum behavior without a model contract.
- Validation failures should return FastAPI/Pydantic `422` responses.
- Model-layer failures should return `503` with a safe generic detail message.
- Do not expose local filesystem paths, raw artifact internals, or stack traces in API responses.

## Git Workflow

This repository uses a normal Git worktree at `/Users/benj/Documents/Coding/VenusHacks26`. Use standard Git commands from the repository root unless the user gives different instructions.

Do not commit raw datasets, virtual environments, caches, or generated Python bytecode.
