# Backend Code Rules

These rules apply to the FastAPI backend, prenatal model service, backend scripts, model contracts, and backend tests in this repository.

Use these rules with `AGENTS.md`, `backend/README.md`, and `backend/API_REFERENCES.md`. When those documents conflict with executable code or tests, trust code and tests first, then update the stale docs.

## Rule Index

1. Keep Backend Docs, Tests, and Contracts Aligned
2. Use the Required Python 3.12 Backend Environment
3. Keep Routers Thin and Services Responsible
4. Preserve the Prenatal Screening API Contract
5. Keep Request Validation in Schemas
6. Return Safe Error Responses
7. Protect Shipped Model Artifacts
8. Keep Model Mapping Explicit and Tested
9. Do Not Add Unsupported Clinical Modes
10. Keep Data and Research Artifacts Out of Commits
11. Keep Normalization Contracts Synchronized
12. Name Backend Files by Ownership
13. Test Public API Behavior Through FastAPI
14. Keep Agent Runtime Orchestration Service-Owned

## 1. Keep Backend Docs, Tests, and Contracts Aligned

- When backend API behavior, request fields, response fields, ports, model artifacts, or runtime commands change, update the owning code, tests, and docs in the same change.
- API contract changes must keep these files aligned when applicable:
  - `backend/backend/routers/`
  - `backend/backend/schemas/`
  - `backend/backend/services/`
  - `backend/tests/test_prenatal_cvd_api.py`
  - `backend/API_REFERENCES.md`
  - `backend/README.md`
  - `README.md`
- Update root `AGENTS.md` only for durable repo-wide context changes, such as default ports, major file moves, new runtime services, or cross-cutting guardrails.
- Remove copied rules that do not map to current VenusHacks files, scripts, services, or documented workflows.

## 2. Use the Required Python 3.12 Backend Environment

- Before running backend Python, pytest, scripts, or dependency commands, use the Python 3.12 environment with `backend/requirements.txt` installed.
- In this local workspace, activate:

```bash
source /Users/benj/Documents/Coding/cardiac_mvp/.venv/bin/activate
cd /Users/benj/Documents/Coding/VenusHacks26/backend
python --version
```

- Expected major/minor version: `Python 3.12`.
- Do not use system Python for backend work unless the user explicitly asks.

## 3. Keep Routers Thin and Services Responsible

- Route modules in `backend/backend/routers/` should validate routing concerns, call schemas/services, and serialize responses.
- Request shape belongs in `backend/backend/schemas/`.
- Frontend-payload to model-feature mapping and inference wrapping belong in `backend/backend/services/prenatal_cvd.py`.
- Core model inference belongs in `backend/scripts/maternal/prenatal_cvd_model_a.py`.
- Do not duplicate model feature mapping, thresholds, artifact loading, or response shaping across routers and scripts.
- Agent orchestration belongs in `backend/backend/services/agents/`; route modules should not own provider selection, tool registration, subagent allowlists, or runtime state wiring.
- Apple Watch ECG parsing, preprocessing, checkpoint loading, and inference belong in `backend/backend/services/apple_watch_ecg.py` and `backend/backend/services/lead1_ecg_runtime.py`, not in route handlers.

## 4. Preserve the Prenatal Screening API Contract

- Current public backend API surface:
  - `GET /health`
  - `POST /api/agents/chat`
  - `POST /api/ecg/apple-watch/infer`
  - `POST /api/screening/prenatal-cvd`
  - `POST /api/screening/prenatal-expanded` (backend-only; not wired to frontend UI yet)
  - `POST /api/screening/postnatal-followup` (wired to the frontend postpartum risk profile flow)
- `POST /api/agents/chat` invokes the service-owned agent runtime and must keep provider errors generic.
- `POST /api/ecg/apple-watch/infer` invokes the service-owned Apple Watch Lead I ECG prototype runtime and must keep model errors generic.
- `POST /api/screening/prenatal-cvd` accepts frontend-shaped camelCase fields.
- Preserve the frontend-compatible `prenatal_cvd_followup_proxy_probability` response alias unless the frontend contract and API docs change in the same update.
- Preserve response safety language that the model is a risk-prioritization aid, not a diagnosis or direct cardiovascular disease probability.
- Keep `model_version`, response examples, and documented artifact expectations consistent with the shipped model package.
- Keep the Apple Watch ECG caveat exactly as `Predictions are experimental and not clinically validated.` and do not return or log raw `voltageMeasurements`.

## 5. Keep Request Validation in Schemas

- Pydantic schemas own request validation for required fields, type coercion, null booleans, numeric fields, and supported `pregnancyMode` values.
- Unknown extra fields are currently ignored by the request schema; do not change that behavior without updating `backend/API_REFERENCES.md` and tests.
- Validation failures should remain FastAPI/Pydantic `422` responses.

## 6. Return Safe Error Responses

- Model-layer or artifact-loading failures should return `503` with a safe generic detail message.
- Do not expose local filesystem paths, raw artifact internals, stack traces, dependency errors, or training details in API responses.
- Log or debug detailed failures locally only when doing so does not leak through public responses.

## 7. Protect Shipped Model Artifacts

- Prenatal runtime inference loads from `backend/models/cdc-natality/default/`.
- Apple Watch Lead I ECG prototype inference loads from `backend/models/lead1_dataset_invariance/best_kept_adversarial.pt`.
- Required prenatal runtime artifacts include:
  - `preprocessor.joblib`
  - `calibrator.joblib`
  - `thresholds.json`
  - `feature_config.yaml`
- Do not edit shipped model artifacts unless the user explicitly asks.
- Treat other non-default model folders as research artifacts unless explicitly asked to update or ship them.

## 8. Keep Model Mapping Explicit and Tested

- Frontend field mapping to model features must remain explicit in `backend/backend/services/prenatal_cvd.py`.
- Mapping changes must update focused backend tests and `backend/API_REFERENCES.md`.
- Do not hide clinical or model assumptions in route handlers, broad helper modules, or generated artifacts.

## 9. Do Not Add Unsupported Clinical Modes

- The prenatal endpoint supports `pregnancyMode: "prenatal"` only.
- Do not add postpartum behavior, alternate model modes, or new screening endpoints without a model contract and updated tests/docs.
- If a user-facing clinical mode is only a frontend placeholder, document it honestly as a placeholder until real backend support exists.

## 10. Keep Data and Research Artifacts Out of Commits

- Raw/local datasets are not part of normal commits.
- Keep `backend/data/`, `backend/tmp/`, `backend/archived/`, Python caches, virtual environments, and generated local artifacts out of commits.
- Do not commit regenerated research outputs unless the user explicitly asks and the output is intended to be shipped.

## 11. Keep Normalization Contracts Synchronized

- When changing ECG/data normalization behavior, keep `backend/docs/normalization-pipeline.md` and `backend/docs/unified-schema-contract.json` aligned.
- Preserve patient-level split and leakage-prevention rules in normalization/modeling work.
- Prefer existing configs and schema contracts over ad hoc field changes.

## 12. Name Backend Files by Ownership

- New backend files should make their ownership obvious from the filename and package location.
- Avoid broad junk-drawer modules such as `utils.py`, `helpers.py`, or `misc.py` for domain logic.
- Prefer concrete names that describe the owned behavior, such as `prenatal_cvd.py`, `screening.py`, or `ptbxl_health_report.py`.

## 13. Test Public API Behavior Through FastAPI

- Public route behavior must be tested through the FastAPI app, not only through lower-level helpers.
- Keep `backend/tests/test_prenatal_cvd_api.py` current for prenatal request validation, successful responses, and model-unavailable behavior.
- Add focused backend tests when changing schemas, service mapping, model error handling, or API response fields.

## 14. Keep Agent Runtime Orchestration Service-Owned

- `backend/backend/services/agents/` owns LangChain/deepagents runtime setup, provider selection, tools, subagents, thread IDs, and runtime profile metadata.
- Provider switching must remain environment-driven and support only explicit providers: OpenRouter, OpenAI, and configured OpenAI-compatible HTTPS base URLs or local HTTP loopback base URLs.
- Agent tools and subagents must be deterministic and allowlisted; do not add broad filesystem, shell, network, mutation, or live-provider behavior without a route contract and tests.
- Do not duplicate prenatal model feature mapping or artifact loading in agent tools; call or summarize service-owned outputs instead.
