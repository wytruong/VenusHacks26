# Hear Your Heart

> Cardiac health, explained for you.

Built at VenusHacks 2026 — Track 3: Heart Health at Warp Speed  
Sponsored by the California Office of the Surgeon General

## Deployed link:
 heartwise-venushacks26.netlify.app

## The Problem

Heart disease is the #1 killer of women in California. Pregnant and postpartum women are the most vulnerable and the least likely to receive proper cardiac screening. When they do receive a diagnosis, medical terminology creates a gap between what the doctor said and what the patient understood. That gap costs lives.

$60 billion is spent annually on maternal and newborn care in the United States. A significant portion comes from complications we could have caught earlier.

## What We Built

Hear Your Heart is a maternal cardiac health companion that helps pregnant and postpartum women understand their heart health in plain English.

Three entry points, one destination:

- **Apple Watch ECG** — upload ECG export data for experimental Lead I prototype probabilities.
- **Doctor's Note** — photograph a handwritten note and translate it into patient-friendly language.
- **Risk Profile** — enter prenatal or postpartum maternal health factors and receive a follow-up priority signal from the backend model APIs.

All three paths lead to an immersive 3D heart visualization with plain-language explanations, doctor questions, and scripts for what to say at the next appointment.

## Features

- Immersive 3D anatomical heart visualization with interactive region exploration.
- Particle landing animation and adaptive interface.
- Pregnancy onboarding with prenatal and postpartum modes.
- Maternal cardiac risk factor form with calculated BMI and model-aligned prenatal/postpartum inputs.
- FastAPI prenatal and postnatal screening endpoints backed by shipped model artifacts.
- FastAPI Apple Watch Lead I ECG prototype endpoint backed by a copied research checkpoint.
- Typed frontend screening and ECG API clients (`src/api/screening.ts`, `src/api/ecg.ts`) with user-safe error handling.
- Apple Watch ECG upload flow with experimental, non-clinically-validated prototype probabilities.
- Doctor note upload placeholder flow with mocked OCR-style result.
- Personalized patient profile with photo, medications, allergies, and doctor visit notes.
- Risk tier output — low, medium, high — with contributing factors and recommended next steps.
- Doctor script for patient-provider follow-up conversations.
- Route-owned frontend flow: `/`, `/onboarding`, `/risk-profile`, `/heart`, `/uploads/ecg`, `/uploads/doctor-note`.

## Tech Stack

Frontend:

- React 19 + TypeScript + Vite
- Three.js + React Three Fiber + Drei
- Framer Motion
- Tailwind CSS

Backend:

- FastAPI + Pydantic
- Python 3.12
- pandas, NumPy, scikit-learn, LightGBM, PyTorch
- Shipped CDC natality prenatal screening model artifacts
- Shipped Apple Watch Lead I ECG prototype checkpoint

## Project Layout

```text
.
├── src/                         React app source
├── public/heart-model/          3D heart model assets
├── backend/
│   ├── backend/                 FastAPI app, routes, schemas, services
│   ├── models/cdc-natality/     Shipped prenatal model package
│   ├── models/lead1_dataset_invariance/
│   │                             Apple Watch ECG prototype checkpoint
│   ├── scripts/                 Model, data, health, and normalization scripts
│   ├── tests/                   Backend API tests
│   ├── API_REFERENCES.md        Detailed backend API contract
│   └── README.md                Backend-specific notes
├── package.json                 Frontend scripts and dependencies
└── README.md                    Central project overview
```

## Quick Start

### 1. Install frontend dependencies

```bash
npm install
```

### 2. Start the frontend dev server

```bash
npm run dev
```

The Vite dev server is pinned to `http://localhost:45260` to avoid common local port conflicts.

### 3. Start the backend API server

Use the Python 3.12 virtual environment that contains the backend runtime stack:

```bash
source /Users/benj/Documents/Coding/cardiac_mvp/.venv/bin/activate
cd /Users/benj/Documents/Coding/VenusHacks26/backend
python -m pip install -r requirements.txt
uvicorn backend.main:app --reload --port 45261
```

Health check:

```bash
curl http://127.0.0.1:45261/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "venus-hacks-backend"
}
```

## Backend API

### Live backend routes

- `GET /health`
- `POST /api/agents/chat`
- `POST /api/ecg/apple-watch/infer`
- `POST /api/screening/prenatal-cvd`
- `POST /api/screening/prenatal-expanded` *(backend-only; not wired to frontend UI yet)*
- `POST /api/screening/postnatal-followup` *(wired to the frontend postpartum risk profile flow)*

### `POST /api/ecg/apple-watch/infer`

Runs an Apple Watch Lead I ECG prototype checkpoint and returns model probabilities for uploaded ECG samples. The endpoint accepts either `healthExport.data.ecg` with `recordIndex` or a single `ecgRecord`, excludes raw waveform values from responses, and includes `Predictions are experimental and not clinically validated.` in every successful response.

This ECG route is a prototype only. It is not a diagnostic medical device and should not be described as clinically validated or used to conclude that a user's heart is normal or abnormal.

### `POST /api/screening/prenatal-cvd`

Runs the shipped prenatal CVD follow-up prioritization model. The endpoint accepts frontend-shaped prenatal risk form fields and maps them to the model's internal feature names. The frontend calculates `prepregnancyBmi` from pre-pregnancy height and weight before submitting.

Example request:

```bash
curl -X POST http://127.0.0.1:45261/api/screening/prenatal-cvd \
  -H 'Content-Type: application/json' \
  -d '{"pregnancyMode":"prenatal","age":"35","prepregnancyBmi":"32.0","chronicHypertension":true,"diabetes":false,"priorPretermOrStillbirth":true,"liveBirthsCount":"1","smokedPregnancy":false,"multipleGestation":false}'
```

Important response fields:

- `risk_tier`
- `recommended_followup_priority`
- `main_contributing_factors`
- `current_composite_signal.probability`
- `prenatal_cvd_followup_proxy_probability`
- `safety_note`
- `disclaimer`

The current `POST /api/screening/prenatal-cvd` endpoint supports `pregnancyMode: "prenatal"` only and does not accept postnatal/postpartum submissions. Postpartum submissions use `POST /api/screening/postnatal-followup`; `POST /api/screening/prenatal-expanded` remains backend-only.

Validation summary:

- Numeric fields accept numbers or numeric strings; empty/non-numeric values return `422`.
- Boolean fields are strict booleans; `null` returns `422`.
- Backend model unavailability returns `503` with a safe message (`Prenatal screening model is unavailable.`).

For local development, backend CORS is intentionally limited to the Vite dev origins on port `45260` (`localhost` and `127.0.0.1`).

See `backend/API_REFERENCES.md` for the complete API contract.

## Running Checks

Frontend:

```bash
npm run lint
npm run build
```

Backend:

```bash
source /Users/benj/Documents/Coding/cardiac_mvp/.venv/bin/activate
cd /Users/benj/Documents/Coding/VenusHacks26/backend
python -m pytest
```

Focused backend API tests:

```bash
python -m pytest tests/test_prenatal_cvd_api.py tests/test_maternal_screening_api.py
python -m pytest tests/test_apple_watch_ecg_api.py
```

## The Science

Risk factors tracked by the prenatal model include advanced maternal age, pre-pregnancy BMI, pre-pregnancy hypertension, pre-pregnancy diabetes, prior adverse pregnancy history, prior live births, smoking before or during pregnancy, and known or suspected multiple gestation.

The shipped prenatal backend model is a follow-up prioritization aid trained from CDC natality-derived features. It outputs a calibrated proxy signal and a low/medium/high follow-up tier.

The Apple Watch Lead I ECG backend route uses a prototype research checkpoint and outputs probabilities only. Predictions are experimental and not clinically validated.

Important clinical limitation: model output is not a diagnosis and is not a direct cardiovascular disease probability. Clinical judgment should guide care decisions.

Postpartum risk profiling is connected to the postnatal follow-up route and uses model-aligned delivery, maternal, and newborn context fields. The prenatal-expanded screening route remains backend-only.

## Research Foundation

- Virtual and Augmented Reality in Cardiac Surgery — Brazilian Journal of Cardiovascular Surgery 2022
- Real-time Visualization of Retrograde Cardioplegia Delivery — Harvard/Brigham and Women's Hospital 2008
- The Reliability of the Apple Watch ECG — Cureus 2023
- MVKT-ECG: Efficient single-lead ECG classification — Tsinghua University, Computers in Biology and Medicine 2023

## Notes for Contributors

- Do not commit raw local datasets or temporary backend outputs.
- `backend/data/`, `backend/tmp/`, generated archives, Python caches, and non-default model outputs are ignored.
- The runtime prenatal model package is kept under `backend/models/cdc-natality/default/`.
- The Apple Watch Lead I ECG prototype checkpoint is kept under `backend/models/lead1_dataset_invariance/`.
- Keep frontend integration and backend API behavior aligned with `backend/API_REFERENCES.md`.

## Team

My Truong · Mary Nguyen · Harry Tran · Ben Nguyen

VenusHacks 2026 — University of California, Irvine
