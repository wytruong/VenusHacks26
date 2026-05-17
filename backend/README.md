# VenusHacks Backend

This backend contains the Python services, scripts, model artifacts, and tests used by the VenusHacks cardiac screening prototype.

Current backend capabilities include:

- FastAPI screening API under `backend/`.
- Prenatal CVD follow-up prioritization inference under `scripts/maternal/`.
- Shipped CDC natality model artifacts under `models/cdc-natality/default/`.
- ECG/data normalization scripts and references under `scripts/` and `docs/`.
- Backend API tests under `tests/`.

## Required Environment

Use the Python 3.12 virtual environment that contains the backend runtime stack:

```bash
source /Users/benj/Documents/Coding/cardiac_mvp/.venv/bin/activate
cd /Users/benj/Documents/Coding/VenusHacks26/backend
python --version
```

Expected major/minor version: `Python 3.12`.

Install or refresh backend dependencies with:

```bash
python -m pip install -r requirements.txt
```

## Project Layout

```text
backend/
  main.py                         FastAPI app entrypoint
  routers/                        API route modules
  schemas/                        Pydantic request schemas
  services/                       Model mapping and service wrappers
models/
  cdc-natality/default/           Shipped prenatal-cvd model artifacts
  cdc-natality/prenatal_expanded_screening_v3_1_timing_safe/
                                  Prenatal-expanded model artifacts
  cdc-natality/postnatal_followup_v1/
                                  Postnatal-followup model artifacts
scripts/
  maternal/                       Maternal screening runtime helpers
  health/                         Dataset health report scripts
  normalization/                  Data normalization adapters
tests/
  test_prenatal_cvd_api.py        Prenatal-cvd API route and validation tests
  test_maternal_screening_api.py  Prenatal-expanded and postnatal-followup API tests
docs/
  normalization-pipeline.md       ECG normalization design
  unified-schema-contract.json    Shared normalization schema contract
API_REFERENCES.md                 Runtime API contract reference
requirements.txt                  Backend Python dependencies
```

## Running the API

From `/Users/benj/Documents/Coding/VenusHacks26/backend` with the required venv active:

```bash
uvicorn backend.main:app --reload --port 45261
```

Health check:

```bash
curl http://127.0.0.1:45261/health
```

Live backend routes:

```text
GET  /health
POST /api/screening/prenatal-cvd
POST /api/screening/prenatal-expanded
POST /api/screening/postnatal-followup
```

`/api/screening/prenatal-expanded` and `/api/screening/postnatal-followup` are backend-only routes and are not wired to the frontend UI yet.

See `API_REFERENCES.md` for request and response examples.

## Prenatal CVD Screening Model

The API endpoint `POST /api/screening/prenatal-cvd` accepts frontend-shaped prenatal form fields and maps them to the shipped model inputs before calling:

```python
from scripts.maternal.prenatal_cvd_model_a import predict_prenatal_cvd_risk
```

Default artifacts load from:

```text
models/cdc-natality/default/
```

The output is a prenatal follow-up priority signal, not a diagnosis and not a direct cardiovascular disease probability. Clinical judgment should guide care decisions.

Validation and error behavior:

- `pregnancyMode` must be `"prenatal"`.
- Numeric inputs (`age`, `prepregnancyBmi`, `liveBirthsCount`) accept numbers or numeric strings; empty/non-numeric strings return `422`.
- Boolean inputs are strict booleans (`true`/`false`); `null` returns `422`.
- Backend model unavailability returns `503` with `{"detail": "Prenatal screening model is unavailable."}`.

## Backend-only Maternal Screening Routes

The following routes are implemented and tested in the backend, but not wired to frontend UI flows yet:

- `POST /api/screening/prenatal-expanded`
- `POST /api/screening/postnatal-followup`

Source files:

- Route: `backend/routers/screening.py`
- Schemas: `backend/schemas/screening.py`
- Service wrappers: `backend/services/maternal_screening.py`
- Runtime helpers:
  - `scripts/maternal/prenatal_expanded_screening_v3_1_timing_safe.py`
  - `scripts/maternal/postnatal_followup_v1.py`
- Artifact directories:
  - `models/cdc-natality/prenatal_expanded_screening_v3_1_timing_safe/`
  - `models/cdc-natality/postnatal_followup_v1/`

Behavior summary:

- Numeric fields accept JSON numbers or numeric strings.
- Empty/non-numeric strings for numeric fields return `422`.
- Boolean clinical flags require strict JSON booleans (`true`/`false`); string booleans like `"true"`/`"false"` return `422`.
- Unknown extra request fields are ignored.
- Invalid request payloads return `422`.
- Model unavailability returns safe generic `503` errors:
  - `{"detail": "Prenatal expanded screening model is unavailable."}`
  - `{"detail": "Postnatal follow-up model is unavailable."}`
- Outputs are follow-up/prioritization aids, not diagnoses.

See `API_REFERENCES.md` for full request/response contracts.

## Running Tests

From the backend directory with the required venv active:

```bash
python -m pytest
```

Focused API tests:

```bash
python -m pytest tests/test_prenatal_cvd_api.py
python -m pytest tests/test_maternal_screening_api.py
```

## Dataset Health Checks

Generate the PTB-XL 500 Hz normalization health report:

```bash
python scripts/health/ptbxl_health_report.py
```

Generate the ECG Arrhythmia / Chapman-Ningbo health report:

```bash
python scripts/health/ecg_arrhythmia_health_report.py
```

Generate the SPH-ECG health report:

```bash
python scripts/health/sph_ecg_health_report.py
```

The scripts write derived reports under each dataset's `derived/` folder:

```text
data/<dataset>/derived/
```

## Guardrails

- Do not edit shipped model artifacts unless explicitly requested.
- Do not add postpartum endpoint behavior without a postpartum model contract.
- Do not expose local filesystem paths, raw artifact internals, or stack traces in API responses.
- Keep raw datasets, virtual environments, caches, and generated bytecode out of commits.
