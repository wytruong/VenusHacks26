# Hear Your Heart

> Cardiac health, explained for you.

Built at VenusHacks 2026 — Track 3: Heart Health at Warp Speed  
Sponsored by the California Office of the Surgeon General

## The Problem

Heart disease is the #1 killer of women in California. Pregnant and postpartum women are the most vulnerable and the least likely to receive proper cardiac screening. When they do receive a diagnosis, medical terminology creates a gap between what the doctor said and what the patient understood. That gap costs lives.

$60 billion is spent annually on maternal and newborn care in the United States. A significant portion comes from complications we could have caught earlier.

## What We Built

Hear Your Heart is a maternal cardiac health companion that helps pregnant and postpartum women understand their heart health in plain English.

Three entry points, one destination:

- **Apple Watch ECG** — upload an ECG export placeholder flow for cardiac rhythm review.
- **Doctor's Note** — photograph a handwritten note and translate it into patient-friendly language.
- **Risk Profile** — enter maternal health factors and receive a prenatal follow-up priority signal from the backend model API.

All three paths lead to an immersive 3D heart visualization with plain-language explanations, doctor questions, and scripts for what to say at the next appointment.

## Features

- Immersive 3D anatomical heart visualization with interactive region exploration.
- Particle landing animation and adaptive interface.
- Pregnancy onboarding with prenatal and postpartum modes.
- Maternal cardiac risk factor form with 8 prenatal inputs and 5 postpartum clinical flags.
- FastAPI prenatal screening endpoint backed by shipped model artifacts.
- Apple Watch ECG upload placeholder flow.
- Doctor note upload placeholder flow with mocked OCR-style result.
- Personalized patient profile with photo, medications, allergies, and doctor visit notes.
- Risk tier output — low, medium, high — with contributing factors and recommended next steps.
- Doctor script for patient-provider follow-up conversations.

## Tech Stack

Frontend:

- React 19 + TypeScript + Vite
- Three.js + React Three Fiber + Drei
- Framer Motion
- Tailwind CSS

Backend:

- FastAPI + Pydantic
- Python 3.12
- pandas, NumPy, scikit-learn, LightGBM
- Shipped CDC natality prenatal screening model artifacts

## Project Layout

```text
.
├── src/                         React app source
├── public/heart-model/          3D heart model assets
├── backend/
│   ├── backend/                 FastAPI app, routes, schemas, services
│   ├── models/cdc-natality/     Shipped prenatal model package
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

Vite will print the local frontend URL in the terminal.

### 3. Start the backend API server

Use the Python 3.12 virtual environment that contains the backend runtime stack:

```bash
source /Users/benj/Documents/Coding/cardiac_mvp/.venv/bin/activate
cd /Users/benj/Documents/Coding/VenusHacks26/backend
python -m pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "venus-hacks-backend"
}
```

## Backend API

### `POST /api/screening/prenatal-cvd`

Runs the shipped prenatal CVD follow-up prioritization model. The endpoint accepts frontend-shaped prenatal risk form fields and maps them to the model's internal feature names.

Example request:

```bash
curl -X POST http://127.0.0.1:8000/api/screening/prenatal-cvd \
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

The current backend endpoint supports `pregnancyMode: "prenatal"` only. Postpartum UI fields exist, but a postpartum model endpoint has not been implemented yet.

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
python -m pytest tests/test_prenatal_cvd_api.py
```

## The Science

Risk factors tracked by the prenatal model include advanced maternal age, pre-pregnancy BMI, pre-pregnancy hypertension, pre-pregnancy diabetes, prior adverse pregnancy history, prior live births, smoking before or during pregnancy, and known or suspected multiple gestation.

The shipped prenatal backend model is a follow-up prioritization aid trained from CDC natality-derived features. It outputs a calibrated proxy signal and a low/medium/high follow-up tier.

Important clinical limitation: the model output is not a diagnosis and is not a direct cardiovascular disease probability. Clinical judgment should guide care decisions.

Postpartum risk profiling is currently represented in the UI as collected form fields and is not yet connected to a backend model endpoint.

## Research Foundation

- Virtual and Augmented Reality in Cardiac Surgery — Brazilian Journal of Cardiovascular Surgery 2022
- Real-time Visualization of Retrograde Cardioplegia Delivery — Harvard/Brigham and Women's Hospital 2008
- The Reliability of the Apple Watch ECG — Cureus 2023
- MVKT-ECG: Efficient single-lead ECG classification — Tsinghua University, Computers in Biology and Medicine 2023

## Notes for Contributors

- Do not commit raw local datasets or temporary backend outputs.
- `backend/data/`, `backend/tmp/`, generated archives, Python caches, and non-default model outputs are ignored.
- The runtime prenatal model package is kept under `backend/models/cdc-natality/default/`.
- Keep frontend integration and backend API behavior aligned with `backend/API_REFERENCES.md`.

## Team

My Truong · Mary Nguyen · Harry Tran · Ben Nguyen

VenusHacks 2026 — University of California, Irvine
