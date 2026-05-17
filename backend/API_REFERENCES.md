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
- Allowed headers: `Content-Type`, `X-Request-ID`
- Credentials: not enabled

## Live backend routes

The following backend routes are currently implemented:

- `GET /health`
- `POST /api/agents/chat`
- `POST /api/agents/doctor-note-screening`
- `POST /api/ecg/apple-watch/infer`
- `POST /api/screening/prenatal-cvd`
- `POST /api/screening/prenatal-expanded` (backend-only; not wired to frontend UI yet)
- `POST /api/screening/postnatal-followup` (wired to the frontend postpartum risk profile flow)

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

## `POST /api/agents/chat`

Invokes the service-owned LangChain/deepagents maternal companion runtime. The doctor-note UI uses this route for follow-up questions after the current OCR summary is shown. Models are not autodiscovered from `/v1/models`; `AGENT_MODEL` remains the selected model, currently configured locally as `deepseek/deepseek-v4-flash`.

Source files:

- Route: `backend/routers/agents.py`
- Request/response schema: `backend/schemas/agent_chat.py`
- Service wrapper: `backend/services/agent_chat.py`
- Agent runtime: `backend/services/agents/`

### Request body

```json
{
  "sessionId": "doctor-note-session-1",
  "surface": "general_health_companion",
  "doctorNote": {
    "condition": "Hypertension",
    "region": "Left Ventricle",
    "risk": "HIGH",
    "description": "Blood pressure is elevated during pregnancy.",
    "doctorScript": "I want to discuss my blood pressure and heart health.",
    "questions": ["What range is safe?"]
  },
  "doctorNoteScreening": {
    "status": "processed",
    "screeningContext": "prenatal",
    "extractedInput": {"mother_age": 31, "prepregnancy_hypertension": true},
    "riskResult": {"risk_tier": "high"},
    "evidence": ["pregnant patient with chronic hypertension"],
    "missingOrUncertainFields": ["mother_bmi"],
    "insight": {
      "title": "Prenatal screening signal",
      "riskLabel": "HIGH",
      "summary": "The note supports prenatal screening.",
      "recommendedFollowup": "High-priority prenatal follow-up",
      "safetyNote": "Screening aid, not a diagnosis."
    }
  },
  "messages": [
    {"role": "user", "content": "What does this mean?"}
  ]
}
```

Fields:

| Field | Type | Notes |
| --- | --- | --- |
| `sessionId` | string | Required non-blank client session ID; used to build the runtime thread ID. |
| `surface` | string | Optional; defaults to `general_health_companion`. Supported values are `general_health_companion` and `maternal_risk`. |
| `doctorNote` | object | Optional current doctor-note OCR summary; the service formats it as backend-owned runtime context. |
| `doctorNoteScreening` | object | Optional processed doctor-note screening result; used as backend-owned context for follow-up questions. |
| `messages` | array | Required non-empty user/assistant chat messages. Frontend callers cannot send system messages. |

Unknown extra fields are ignored by the request schema (`extra="ignore"`).

### Response `200`

```json
{
  "assistantText": "Please review this with your OB or clinician.",
  "messageCount": 2,
  "threadId": "vh:agent:general_health_companion:doctor-note-session-1"
}
```

### Error responses

- `422`: invalid request body, blank session ID, blank message, unsupported surface, or unsupported message role.
- `503`: agent provider configuration or runtime invocation unavailable.

Runtime unavailable response:

```json
{
  "detail": "Agent chat service is unavailable."
}
```

## `POST /api/agents/doctor-note-screening`

Uses the existing Venus agent runtime to classify the selected translated demo doctor note as prenatal, postnatal, or none, extract supported model inputs from `englishDemoNote`, validate them with backend schemas, and run deterministic maternal screening services when appropriate. It must not infer eligibility, disease flags, or risk output from demo IDs, CSV order, `group`, `category`, or `conditionCodes`.

Source files:

- Route: `backend/routers/agents.py`
- Request/response schema: `backend/schemas/doctor_note_screening.py`
- Service wrapper: `backend/services/doctor_note_screening.py`
- Agent tools/subagents: `backend/services/agents/`

### Request body

```json
{
  "sessionId": "doctor-note-session-1",
  "record": {
    "demoId": "cv_001",
    "patientId": "patient-1",
    "visitOccurrenceId": "visit-1",
    "group": "cv_risk",
    "category": "hypertension",
    "age": "31",
    "conditionCodes": "O10",
    "noteDate": "2026-05-17",
    "noteTitle": "Translated prenatal note",
    "englishDemoNote": "31-year-old pregnant patient with chronic hypertension.",
    "extractedFactors": "hypertension",
    "summary": "Pregnant patient with hypertension.",
    "doctorQuestions": "What follow-up do I need?"
  }
}
```

### Response `200`

Processed response example:

```json
{
  "status": "processed",
  "screeningContext": "prenatal",
  "extractedInput": {"mother_age": 31, "prepregnancy_hypertension": true},
  "riskResult": {"risk_tier": "high"},
  "evidence": ["pregnant patient with chronic hypertension"],
  "missingOrUncertainFields": ["mother_bmi"],
  "insight": {
    "title": "Prenatal screening signal",
    "riskLabel": "HIGH",
    "summary": "The selected note contained enough context to run maternal screening.",
    "recommendedFollowup": "High-priority prenatal follow-up",
    "safetyNote": "This is a follow-up prioritization aid, not a diagnosis. Clinical judgment should guide care decisions."
  }
}
```

No-context and extraction-failed outcomes also return `200` with `status` set to `no_screening_context` or `extraction_failed` and no model execution.

### Error responses

- `422`: invalid request body, blank session ID, or blank `englishDemoNote`.
- `503`: agent provider configuration, runtime invocation, or screening runtime unavailable.

Runtime unavailable response:

```json
{
  "detail": "Doctor-note screening service is unavailable."
}
```

## `POST /api/ecg/apple-watch/infer`

Runs the Apple Watch Lead I ECG prototype checkpoint against uploaded ECG samples and returns model probabilities. Predictions are experimental and not clinically validated. This endpoint is not a diagnostic medical device and must not be used to conclude that a user's heart is normal or abnormal.

Source files:

- Route: `backend/routers/ecg.py`
- Request schema: `backend/schemas/ecg.py`
- Service wrapper: `backend/services/apple_watch_ecg.py`
- Runtime/model architecture: `backend/services/lead1_ecg_runtime.py`
- Checkpoint: `models/lead1_dataset_invariance/best_kept_adversarial.pt`

### Request body

The endpoint accepts either a full Health Auto Export-shaped payload:

```json
{
  "healthExport": {
    "data": {
      "ecg": [
        {
          "start": "2026-05-17T10:00:00Z",
          "end": "2026-05-17T10:00:30Z",
          "classification": "Sinus Rhythm",
          "averageHeartRate": 66,
          "samplingFrequency": 512,
          "numberOfVoltageMeasurements": 15360,
          "source": "ECG",
          "voltageMeasurements": [
            {"date": 0, "voltage": 0.0, "units": "mcV"}
          ]
        }
      ]
    }
  },
  "recordIndex": 0,
  "windowPolicy": "sliding",
  "threshold": 0.5
}
```

or a single ECG record:

```json
{
  "ecgRecord": {
    "start": "2026-05-17T10:00:00Z",
    "end": "2026-05-17T10:00:30Z",
    "classification": "Sinus Rhythm",
    "averageHeartRate": 66,
    "samplingFrequency": 512,
    "numberOfVoltageMeasurements": 15360,
    "source": "ECG",
    "voltageMeasurements": [
      {"date": 0, "voltage": 0.0, "units": "mcV"}
    ]
  },
  "windowPolicy": "sliding",
  "threshold": 0.5
}
```

Fields:

| Field | Type | Notes |
| --- | --- | --- |
| `healthExport` | object | Full Health Auto Export-style payload. Must contain non-empty `data.ecg`. Mutually exclusive with `ecgRecord`. |
| `ecgRecord` | object | Single ECG record object. Mutually exclusive with `healthExport`. |
| `recordIndex` | integer | Required with `healthExport`; selects the ECG record from `data.ecg`. |
| `windowPolicy` | string | Optional; `first` or `sliding`. Defaults to `first`. |
| `threshold` | number | Optional probability threshold between `0` and `1`. Defaults to `0.5`. |
| `voltageMeasurements` | array | Required non-empty ECG waveform samples. Raw values are processed but never returned. |

Preprocessing behavior:

- Converts `voltageMeasurements[*].voltage` to `float32`.
- Replaces non-finite waveform values with `0.0` before inference.
- Resamples from the source `samplingFrequency` to the checkpoint sampling rate, currently 500 Hz.
- Creates 10-second / 5000-sample windows from the resampled Lead I signal.
- Pads short windows with zeros.
- Normalizes each window by mean-centering and dividing by `std + 1e-6`.

### Response `200`

Raw waveform values are excluded from the response.

```json
{
  "record_index": 0,
  "record_metadata": {
    "start": "2026-05-17T10:00:00Z",
    "end": "2026-05-17T10:00:30Z",
    "classification": "Sinus Rhythm",
    "averageHeartRate": 66,
    "samplingFrequency": 512,
    "numberOfVoltageMeasurements": 15360,
    "source": "ECG"
  },
  "window_policy": "sliding",
  "threshold": 0.5,
  "target_samples": 5000,
  "checkpoint_sampling_rate_hz": 500.0,
  "duration_sec": 10.0,
  "target_names": [
    "normal_or_sinus_reference",
    "atrial_fibrillation_or_flutter",
    "bradycardia_or_tachycardia",
    "other_abnormal"
  ],
  "predictions": [
    {
      "window_index": 0,
      "window_start_sample": 0,
      "window_end_sample": 5000,
      "window_duration_sec": 10.0,
      "window_target_samples": 5000,
      "prob_any_abnormal": 0.543088,
      "pred_any_abnormal": true,
      "labels_above_threshold": ["normal_or_sinus_reference", "other_abnormal"],
      "probabilities": {
        "normal_or_sinus_reference": 0.543088,
        "atrial_fibrillation_or_flutter": 0.443086,
        "bradycardia_or_tachycardia": 0.478394,
        "other_abnormal": 0.508431
      }
    }
  ],
  "caveat": "Predictions are experimental and not clinically validated."
}
```

### Error responses

- `422`: invalid request body, missing/empty ECG data, missing/empty `voltageMeasurements`, invalid `recordIndex`, invalid `samplingFrequency`, unsupported `windowPolicy`, or invalid `threshold`.
- `413`: request body exceeds the ECG route size limit.
- `503`: checkpoint/model runtime unavailable.

Model unavailable response:

```json
{
  "detail": "Apple Watch ECG inference service is unavailable."
}
```

Oversized request response:

```json
{
  "detail": "Request body is too large."
}
```

## `POST /api/screening/prenatal-cvd`

Runs the shipped prenatal CVD follow-up prioritization model. This is a follow-up priority signal, not a cardiovascular disease diagnosis or direct disease probability.

Source files:

- Route: `backend/routers/screening.py`
- Request schema: `backend/schemas/screening.py`
- Mapping/service wrapper: `backend/services/prenatal_cvd.py`
- Core inference: `scripts/maternal/prenatal_cvd_model_a.py`
- Default artifacts: `models/cdc-natality/default/`

### Request body

The endpoint accepts the current frontend-shaped payload. The frontend collects pre-pregnancy height and weight, calculates BMI, displays it to the user, and submits the calculated value as `prepregnancyBmi`:

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

Runs the postnatal-followup maternal screening contract. The frontend postpartum risk profile flow collects model-aligned questions, calculates pre-pregnancy BMI from height and weight, and submits that BMI as `mother_bmi`.

Source files:

- Route: `backend/routers/screening.py`
- Request schema: `backend/schemas/screening.py`
- Service wrapper: `backend/services/maternal_screening.py`
- Runtime helper: `scripts/maternal/postnatal_followup_v1.py`
- Artifact directory: `models/cdc-natality/postnatal_followup_v1/`

### Request body

Representative frontend postpartum demo payload:

```json
{
  "mother_age": "36",
  "mother_bmi": "34.2",
  "prepregnancy_hypertension": true,
  "prepregnancy_diabetes": true,
  "prior_live_births": "1",
  "prior_dead_births": "0",
  "previous_preterm_birth": true,
  "previous_cesarean": true,
  "previous_cesarean_count": "1",
  "gestational_hypertension": true,
  "eclampsia": false,
  "gestational_diabetes": true,
  "maternal_transfusion": false,
  "ruptured_uterus": false,
  "unplanned_hysterectomy": false,
  "maternal_icu": true,
  "obstetric_estimate_gestation_weeks": "35",
  "birth_weight_grams": "2200",
  "abnormal_condition_nicu": true,
  "apgar_5_min": "7",
  "apgar_10_min": "8"
}
```

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

### Smoke tests

```bash
curl -X POST http://127.0.0.1:45261/api/screening/prenatal-cvd \
  -H 'Content-Type: application/json' \
  -d '{"pregnancyMode":"prenatal","age":"35","prepregnancyBmi":"32.0","chronicHypertension":true,"diabetes":false,"priorPretermOrStillbirth":true,"liveBirthsCount":"1","smokedPregnancy":false,"multipleGestation":false}'
```

```bash
curl -X POST http://127.0.0.1:45261/api/screening/postnatal-followup \
  -H 'Content-Type: application/json' \
  -d '{"mother_age":"36","mother_bmi":"34.2","prepregnancy_hypertension":true,"prepregnancy_diabetes":true,"prior_live_births":"1","prior_dead_births":"0","previous_preterm_birth":true,"previous_cesarean":true,"previous_cesarean_count":"1","gestational_hypertension":true,"eclampsia":false,"gestational_diabetes":true,"maternal_transfusion":false,"ruptured_uterus":false,"unplanned_hysterectomy":false,"maternal_icu":true,"obstetric_estimate_gestation_weeks":"35","birth_weight_grams":"2200","abnormal_condition_nicu":true,"apgar_5_min":"7","apgar_10_min":"8"}'
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
