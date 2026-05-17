# API References

## Base App

FastAPI app entrypoint:

```bash
uvicorn backend.main:app --reload --port 45261
```

Run from `/Users/benj/Documents/Coding/VenusHacks26/backend` with the required Python 3.12 virtual environment active.

## Local CORS policy

For local frontend integration, CORS is intentionally restricted to Vite dev origins.
This supports the current frontend risk API integration while keeping local origins explicit.

- Allowed origins: `http://localhost:45260`, `http://127.0.0.1:45260`
- Allowed methods: `GET`, `POST`, `OPTIONS`
- Allowed headers: `Content-Type`
- Credentials: not enabled

## Live backend routes

The following backend routes are currently implemented:

- `GET /health`
- `POST /api/screening/prenatal-cvd`
- `POST /api/screening/prenatal-expanded` (backend-only; not wired to frontend UI yet)
- `POST /api/screening/postnatal-followup` (backend-only; not wired to frontend UI yet)

## `GET /health`

Health check for the backend service.

### Response `200`

```json
{
  "status": "ok",
  "service": "venus-hacks-backend"
}
```

Source: `backend/main.py`.

## `POST /api/screening/prenatal-cvd`

Runs the shipped prenatal CVD follow-up prioritization model. This is a follow-up priority signal, not a cardiovascular disease diagnosis or direct disease probability.

Source files:

- Route: `backend/routers/screening.py`
- Request schema: `backend/schemas/screening.py`
- Mapping/service wrapper: `backend/services/prenatal_cvd.py`
- Core inference: `scripts/maternal/prenatal_cvd_model_a.py`
- Default artifacts: `models/cdc-natality/default/`

### Request body

The endpoint accepts the current frontend-shaped payload:

```json
{
  "pregnancyMode": "prenatal",
  "age": 35,
  "prepregnancyBmi": 32.0,
  "chronicHypertension": true,
  "diabetes": false,
  "priorPretermOrStillbirth": true,
  "liveBirthsCount": 1,
  "smokedPregnancy": false,
  "multipleGestation": false
}
```

Fields:

| Field | Type | Notes |
| --- | --- | --- |
| `pregnancyMode` | string | Must be `"prenatal"`. `"postpartum"` is not supported by this endpoint. |
| `age` | number or numeric string | Maps to `mother_age`. |
| `prepregnancyBmi` | number or numeric string | Maps to `mother_bmi`. |
| `chronicHypertension` | boolean | Maps to `prepregnancy_hypertension` as `0`/`1`. |
| `diabetes` | boolean | Maps to `prepregnancy_diabetes` as `0`/`1`. |
| `priorPretermOrStillbirth` | boolean | Maps to `prior_adverse_pregnancy_history` as `0`/`1`. |
| `liveBirthsCount` | integer or numeric string | Maps to `prior_live_births`. |
| `smokedPregnancy` | boolean | Maps to `smoking_before_or_during_pregnancy` as `0`/`1`. |
| `multipleGestation` | boolean | Maps to `multiple_gestation_known_or_suspected` as `0`/`1`. |

Unknown extra fields are ignored by the request schema (`extra="ignore"`).

Validation behavior:

- `pregnancyMode` must be `"prenatal"`.
- `age`, `prepregnancyBmi`, and `liveBirthsCount` accept numbers or numeric strings.
- Empty strings for numeric fields fail validation (`422`).
- Non-numeric strings for numeric fields fail validation (`422`).
- Boolean fields use strict booleans (`true`/`false` only). `null` fails validation (`422`).

### Response `200`

The response preserves the shipped model output and adds a frontend-compatible probability alias.

Important fields:

```json
{
  "model_mode": "prenatal_after_ultrasound",
  "model_name": "prenatal_after_ultrasound_minimal8",
  "model_version": "2026-05-16",
  "overall_followup_priority": "high",
  "tier_interpretation": "Prioritized pregnancy follow-up risk review and postpartum planning.",
  "current_composite_signal": {
    "probability": 0.55112,
    "tier": "high",
    "use": "MVP default proxy follow-up priority only; not a cardiovascular disease probability."
  },
  "risk_tier_note": "Risk tier is based on the unrounded model score.",
  "risk_tier": "high",
  "recommended_followup_priority": "Prioritized pregnancy follow-up risk review and postpartum planning.",
  "main_contributing_factors": [
    "pre-pregnancy hypertension",
    "higher pre-pregnancy BMI",
    "advanced maternal age",
    "prior adverse pregnancy history"
  ],
  "missing_inputs": [],
  "data_quality_warnings": [],
  "safety_note": "This is a risk-prioritization aid, not a diagnosis. Clinical judgment should guide care decisions.",
  "disclaimer": "This is a risk-prioritization aid, not a diagnosis. Clinical judgment should guide care decisions.",
  "prenatal_cvd_followup_proxy_probability": 0.55112
}
```

### Error responses

- `422`: invalid request body, unsupported `pregnancyMode`, null/non-boolean flags, empty numeric strings, or non-numeric numeric fields.
- `503`: model layer unavailable.

Model unavailable response:

```json
{
  "detail": "Prenatal screening model is unavailable."
}
```

## `POST /api/screening/prenatal-expanded`

Runs the backend prenatal-expanded maternal screening contract. This route is currently backend-only and is not wired to frontend UI flows yet.

Source files:

- Route: `backend/routers/screening.py`
- Request schema: `backend/schemas/screening.py`
- Service wrapper: `backend/services/maternal_screening.py`
- Runtime helper: `scripts/maternal/prenatal_expanded_screening_v3_1_timing_safe.py`
- Artifact directory: `models/cdc-natality/prenatal_expanded_screening_v3_1_timing_safe/`

### Request body

Numeric fields accept JSON numbers or numeric strings.

Boolean clinical flags require strict JSON booleans (`true`/`false`).

Unknown extra fields are ignored by the schema.

Invalid payloads return `422`.

Validation specifics:

- Empty strings for numeric fields return `422`.
- Non-numeric strings for numeric fields return `422`.
- String booleans like `"true"`/`"false"` return `422`.

### Response `200` (top-level fields)

- `model_mode`
- `model_name`
- `model_version`
- `overall_followup_priority`
- `maternal_cv_metabolic_signal`
- `obstetric_neonatal_signal`
- `current_composite_signal`
- `missing_inputs`
- `data_quality_warnings`
- `safety_note`

Safety note semantics: outputs are prioritization/follow-up aids, not diagnoses.

### Error responses

- `422`: request validation failure.
- `503`: model unavailable.

Model unavailable response:

```json
{
  "detail": "Prenatal expanded screening model is unavailable."
}
```

## `POST /api/screening/postnatal-followup`

Runs the backend postnatal-followup maternal screening contract. This route is currently backend-only and is not wired to frontend UI flows yet.

Source files:

- Route: `backend/routers/screening.py`
- Request schema: `backend/schemas/screening.py`
- Service wrapper: `backend/services/maternal_screening.py`
- Runtime helper: `scripts/maternal/postnatal_followup_v1.py`
- Artifact directory: `models/cdc-natality/postnatal_followup_v1/`

### Request body

Numeric fields accept JSON numbers or numeric strings.

Boolean clinical flags require strict JSON booleans (`true`/`false`).

Unknown extra fields are ignored by the schema.

Invalid payloads return `422`.

Validation specifics:

- Empty strings for numeric fields return `422`.
- Non-numeric strings for numeric fields return `422`.
- String booleans like `"true"`/`"false"` return `422`.

### Response `200` (top-level fields)

- `model_mode`
- `model_name`
- `model_version`
- `routing_method`
- `overall_followup_priority`
- `hypertension_followup_signal`
- `diabetes_followup_signal`
- `maternal_cv_metabolic_followup_signal`
- `obstetric_neonatal_context_signal`
- `severe_maternal_morbidity_followup_signal`
- `auxiliary_ml_scores`
- `context_flags`
- `missing_inputs`
- `data_quality_warnings`
- `safety_note`

Safety note semantics: outputs are prioritization/follow-up aids, not diagnoses.

### Error responses

- `422`: request validation failure.
- `503`: model unavailable.

Model unavailable response:

```json
{
  "detail": "Postnatal follow-up model is unavailable."
}
```

`POST /api/screening/prenatal-cvd` remains a prenatal-only, frontend-shaped minimal contract and does not support postnatal submissions.

### Smoke test

```bash
curl -X POST http://127.0.0.1:45261/api/screening/prenatal-cvd \
  -H 'Content-Type: application/json' \
  -d '{"pregnancyMode":"prenatal","age":35,"prepregnancyBmi":32.0,"chronicHypertension":true,"diabetes":false,"priorPretermOrStillbirth":true,"liveBirthsCount":1,"smokedPregnancy":false,"multipleGestation":false}'
```

## Focused backend API tests

```bash
python -m pytest tests/test_prenatal_cvd_api.py
python -m pytest tests/test_maternal_screening_api.py
```

## Model Reference

Core Python entrypoint:

```python
from scripts.maternal.prenatal_cvd_model_a import predict_prenatal_cvd_risk
```

Default artifact directory:

```text
models/cdc-natality/default/
```

The shipped model uses the features listed in `models/cdc-natality/default/feature_config.yaml` and loads `preprocessor.joblib`, `calibrator.joblib`, and `thresholds.json` at inference time.
