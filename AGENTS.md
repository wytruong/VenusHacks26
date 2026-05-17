# AGENTS.md

## Project Identity

This repo is the VenusHacks 2026 **Hear Your Heart** prototype: a maternal cardiac health companion with a React/Vite frontend, a FastAPI backend, a shipped prenatal screening model package, and supporting ECG/data normalization scripts.

Use this file for durable repo-wide context only. Do not add task history, temporary plans, branch-specific notes, or one-off debugging steps here.

## High-Signal Source Map

Frontend:

- `src/main.tsx` — React mount/root entrypoint.
- `src/App.tsx` — main stateful app flow, onboarding, upload placeholders, risk-form flow, and insight panels.
- `src/components/HeartModel.tsx` — 3D heart model loading, mesh selection, callouts, and interaction optimizations.
- `src/index.css` — global styling and Tailwind import.
- `vite.config.ts` — Vite config and fixed frontend dev port.
- `package.json` — frontend scripts and dependencies.

Backend API:

- `backend/backend/main.py` — FastAPI app entrypoint.
- `backend/backend/routers/` — API route modules.
- `backend/backend/schemas/` — Pydantic request/response schemas.
- `backend/backend/services/` — model input mapping, inference wrappers, and service-owned runtime modules.
- `backend/backend/services/agents/` — route-free LangChain/deepagents runtime, provider selection, tools, and subagents.
- `backend/backend/routers/screening.py` — screening routes.
- `backend/backend/schemas/screening.py` — Pydantic API request schema.
- `backend/backend/services/prenatal_cvd.py` — frontend-payload to model-input mapping and inference wrapper.
- `backend/tests/test_agent_runtime.py` — deterministic agent runtime/provider/tool/subagent coverage.
- `backend/tests/test_prenatal_cvd_api.py` — current backend API test coverage.
- `backend/API_REFERENCES.md` — detailed request/response contract.

Models, data, and scripts:

- `backend/scripts/maternal/prenatal_cvd_model_a.py` — core prenatal model inference helper.
- `backend/models/cdc-natality/default/` — runtime model package loaded by the API.
- `backend/models/cdc-natality/default/model_card.md` — shipped model limitations and intended-use notes.
- `backend/models/cdc-natality/default/feature_config.yaml` — runtime feature list.
- `backend/docs/normalization-pipeline.md` — ECG/data normalization design.
- `backend/docs/unified-schema-contract.json` — machine-readable normalization schema contract.
- `backend/configs/maternal/prenatal_model_a_v1.yaml` — prenatal model training/config reference.

Project docs:

- `README.md` — centralized project overview and run/test quickstart.
- `backend/README.md` — backend-specific notes.
- `backend/API_REFERENCES.md` — API details.
- `backend/AGENTS.md` — backend-local instructions; keep it aligned with this root file when backend rules change.

When docs conflict, trust executable code and tests first, then `backend/API_REFERENCES.md` for runtime API contracts, then `README.md` / `backend/README.md` for setup guidance, then this file for durable agent guardrails.

## Frontend Context

Tech stack:

- React 19 + TypeScript + Vite 8.
- Tailwind CSS v4 through `@tailwindcss/vite`.
- Framer Motion for transitions.
- Three.js + React Three Fiber + Drei for the 3D heart experience.

Runtime:

```bash
npm install
npm run dev
```

The frontend dev server is pinned to `http://localhost:45260` with `strictPort: true`.

Checks:

```bash
npm run lint
npm run build
```

Important UI behavior:

- The frontend keeps state orchestration in `src/App.tsx` and route ownership in `src/routes/*`.
- User flow routes: `/` particle intro → `/onboarding` → `/risk-profile` (prenatal form) → `/heart` with right-side insight panels.
- Upload entry routes: `/uploads/ecg` and `/uploads/doctor-note`.
- Doctor-note OCR and ECG analysis are currently placeholder/mock flows in the frontend.
- Prenatal risk submission/result rendering is integrated with `POST /api/screening/prenatal-cvd` through the typed frontend client in `src/api/screening.ts` and submit flow in `src/App.tsx`.
- Postpartum risk fields remain a frontend backlog path; do not assume a postpartum backend endpoint exists.

3D asset guardrails:

- Active heart model asset: `public/heart-model/scene.quality.glb`.
- Heart model files are large; do not replace or rename them casually.
- `public/heart-model/scene.bin` is intentionally ignored because it exceeds GitHub's normal file-size limit.
- Mesh/callout behavior depends on model node names in `HeartModel.tsx`; if model assets change, verify mesh mappings and interactions in-browser.
- Keep existing accessibility affordances such as keyboard-triggered upload zones and focus-visible rings.

## Backend Context

Environment requirement:

Before running Python, installing packages, inspecting data with scripts, or executing backend commands, use a Python 3.12 environment with `backend/requirements.txt` installed. In this local workspace, the expected environment is:

```bash
source /Users/benj/Documents/Coding/cardiac_mvp/.venv/bin/activate
cd /Users/benj/Documents/Coding/VenusHacks26/backend
python --version
```

Expected major/minor version: `Python 3.12`. Do not use system Python for backend work unless the user explicitly asks.

Run the API:

```bash
cd /Users/benj/Documents/Coding/VenusHacks26/backend
uvicorn backend.main:app --reload --port 45261
```

Health check:

```bash
curl http://127.0.0.1:45261/health
```

Run backend tests:

```bash
cd /Users/benj/Documents/Coding/VenusHacks26/backend
python -m pytest
python -m pytest tests/test_agent_runtime.py
python -m pytest tests/test_prenatal_cvd_api.py
```

Current API surface:

- `GET /health`
- `POST /api/screening/prenatal-cvd`

Agent runtime guardrails:

- `backend/backend/services/agents/` is a service-layer runtime package only; do not wire public routes there.
- Provider selection is environment-driven via `AGENT_MODEL_PROVIDER`, `AGENT_MODEL`, provider API keys, and the optional OpenAI-compatible base URL settings.
- Agent tools and subagents must remain explicitly allowlisted, deterministic tests must not call live LLM providers by default, and postpartum-specific behavior requires a model contract.

Prenatal endpoint guardrails:

- Supports `pregnancyMode: "prenatal"` only.
- Do not add postpartum endpoint behavior without a model contract.
- Validation failures should remain FastAPI/Pydantic `422` responses.
- Model-layer failures should return `503` with a safe generic detail message.
- Backend CORS should remain least-privilege and limited to local Vite origins (`localhost`/`127.0.0.1` on the configured frontend dev port).
- Do not expose local filesystem paths, raw artifact internals, or stack traces in API responses.
- Keep `backend/API_REFERENCES.md`, route/schema/service code, and API tests aligned when changing API behavior.
- Update this root `AGENTS.md` only when durable repo-wide context changes, such as major file moves, new runtime services, changed default ports, or changed cross-cutting guardrails.

Frontend-to-model mapping:

- The endpoint accepts frontend-shaped camelCase fields.
- `backend/backend/services/prenatal_cvd.py` maps those fields to model features before calling `predict_prenatal_cvd_risk`.
- Preserve the `prenatal_cvd_followup_proxy_probability` alias for frontend compatibility unless the frontend contract is updated at the same time.

Model artifact expectations:

- Runtime inference loads from `backend/models/cdc-natality/default/`.
- Required runtime artifacts include `preprocessor.joblib`, `calibrator.joblib`, `thresholds.json`, and `feature_config.yaml`.
- The model output is a follow-up prioritization aid, not a diagnosis and not a direct cardiovascular disease probability.
- Treat non-default model folders as research artifacts unless explicitly asked to update or ship them.
- Do not edit shipped model artifacts unless the user explicitly asks.

## Data, Normalization, and Research Guardrails

- Raw/local datasets are not part of normal commits.
- `backend/data/`, `backend/tmp/`, `backend/archived/`, Python caches, and non-default model outputs are ignored.
- Keep `backend/docs/normalization-pipeline.md` and `backend/docs/unified-schema-contract.json` aligned when changing normalization behavior.
- Preserve patient-level split and leakage-prevention rules in normalization/modeling work.
- Prefer existing configs and contracts over ad hoc field changes.

## Git and Commit Guidance

- Work from repository root `/Users/benj/Documents/Coding/VenusHacks26` unless a command must run inside `backend/`.
- Use normal Git commands; this repo has a standard `.git` directory.
- Do not commit `node_modules/`, `dist/`, `.env`, `graphify-out/`, Python caches, raw datasets, temp outputs, or generated local artifacts.
- Before committing backend changes, run the relevant backend tests. Before committing frontend changes, run `npm run build` and any relevant lint/check command.

## What Not to Put Here

Do not add:

- Current task progress or TODOs.
- Branch-specific notes.
- Temporary debugging commands.
- Long experiment results that belong in model cards or docs.
- Copies of full API schemas that belong in `backend/API_REFERENCES.md`.
