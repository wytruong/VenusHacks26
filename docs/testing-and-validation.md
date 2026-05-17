# Testing and Validation

This is the source of truth for current validation commands and test expectations in the VenusHacks 2026 Hear Your Heart prototype.

For mandatory test design rules, also read `docs/testing-code-rules.md` before adding, removing, or changing tests.

## Frontend checks

Run from the repository root:

```bash
npm run lint
npm run build
```

Run the frontend locally:

```bash
npm run dev
```

The Vite dev server is pinned to `http://localhost:45260` with `strictPort: true`.

For UI changes, use the running app in a browser and verify the changed user flow. Automated lint/build checks do not prove the 3D heart, onboarding flow, upload interactions, or panel behavior works for users.

## Backend checks

Before backend validation, activate the required Python 3.12 environment and enter the backend directory:

```bash
source /Users/benj/Documents/Coding/cardiac_mvp/.venv/bin/activate
cd /Users/benj/Documents/Coding/VenusHacks26/backend
python --version
```

Expected major/minor version: `Python 3.12`.

Run all backend tests:

```bash
python -m pytest
```

Run the focused agent runtime tests:

```bash
python -m pytest tests/test_agent_runtime.py
```

Run the focused prenatal API tests:

```bash
python -m pytest tests/test_prenatal_cvd_api.py
```

Run the backend API locally:

```bash
uvicorn backend.main:app --reload --port 45261
```

Health check:

```bash
curl http://127.0.0.1:45261/health
```

Prenatal screening smoke request:

```bash
curl -X POST http://127.0.0.1:45261/api/screening/prenatal-cvd \
  -H 'Content-Type: application/json' \
  -d '{"pregnancyMode":"prenatal","age":"35","prepregnancyBmi":"32.0","chronicHypertension":true,"diabetes":false,"priorPretermOrStillbirth":true,"liveBirthsCount":"1","smokedPregnancy":false,"multipleGestation":false}'
```

## Current test surface

Backend tests currently live under `backend/tests/`.

Primary backend coverage:

- `backend/tests/test_agent_runtime.py` — deterministic provider selection, thread ID, tool allowlist, subagent allowlist, and runtime profile coverage without live LLM calls.
- `backend/tests/test_prenatal_cvd_api.py` — FastAPI health check, prenatal screening success path, validation failures, and model-unavailable behavior.

Frontend automated tests are not currently defined in `package.json`; use `npm run lint` and `npm run build` as the current automated frontend checks.

## Change-based validation matrix

| Change surface | Required validation |
| --- | --- |
| Frontend UI, styling, 3D heart, onboarding, upload, or insight panel changes | `npm run lint`, `npm run build`, and browser smoke of the changed flow when possible |
| Frontend prenatal API wiring | Frontend checks, browser smoke, and backend prenatal API tests |
| Backend route/schema/service changes | Relevant focused tests, such as `python -m pytest tests/test_prenatal_cvd_api.py` or `python -m pytest tests/test_agent_runtime.py` |
| Backend API contract changes | Focused backend tests plus `backend/API_REFERENCES.md` update |
| Model mapping or model-error behavior changes | Focused backend tests covering success, validation, and `503` behavior |
| Normalization/data contract changes | Relevant backend script checks plus updates to `backend/docs/normalization-pipeline.md` and `backend/docs/unified-schema-contract.json` |
| Broad full-stack or release-prep changes | `npm run lint`, `npm run build`, and `python -m pytest` |

## API contract validation expectations

- `GET /health` should return service health metadata.
- `POST /api/screening/prenatal-cvd` should support `pregnancyMode: "prenatal"` only.
- Invalid request bodies should return FastAPI/Pydantic `422` responses.
- Model-layer failures should return `503` with a safe generic detail message.
- Public responses must not expose local filesystem paths, raw artifact internals, or stack traces.
- Keep route code, schemas, services, tests, and `backend/API_REFERENCES.md` aligned for any behavior change.

## Manual UI smoke checklist

For frontend UI changes, verify the relevant items in-browser when possible:

1. Particle intro loads and advances as expected.
2. Pregnancy onboarding remains readable and keyboard-accessible.
3. Pregnancy risk profile form handles valid input and validation/error states.
4. Heart reveal and right-side insight panels render without layout overlap.
5. Doctor-note and ECG upload placeholders remain clearly labeled as placeholder/mock behavior unless real services are wired.
6. 3D heart callouts, pointer interactions, and focus states still work after heart model or layout changes.
7. Desktop and small viewport spacing stays balanced, with no large dead zones, cramped form groups, inconsistent section gaps, or alignment jumps.
8. Small viewport behavior remains usable.

## Documentation alignment

Update this document when validation commands, test locations, dev ports, or required smoke checks change.

Do not add validation rules for nonexistent paths, scripts, services, providers, auth systems, test harnesses, or workflows. Rewrite inherited rules against current VenusHacks files and commands before keeping them.
