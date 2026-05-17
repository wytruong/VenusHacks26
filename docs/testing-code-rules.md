# Testing Code Rules

These rules apply to tests, validation workflows, and test documentation for the VenusHacks 2026 Hear Your Heart prototype.

Use these rules with `docs/testing-and-validation.md`, `docs/backend-code-rules.md`, `docs/frontend-code-rules.md`, and `AGENTS.md`.

## Rule Index

1. Match Test Coverage to the Changed Surface
2. Keep Backend Tests on the Required Python 3.12 Environment
3. Test Public API Behavior Through FastAPI
4. Preserve Prenatal API Contract Coverage
5. Keep Model Failure Tests Safe and Generic
6. Keep Frontend Validation Honest
7. Do Not Add Live or External Calls to Deterministic Tests
8. Keep Test Data Minimal and Non-Sensitive
9. Update Test Docs With Test Workflow Changes
10. Remove Stale Donor-Project Test Rules
11. Keep Agent Runtime Tests Deterministic

## 1. Match Test Coverage to the Changed Surface

- Add or update tests for behavior changes, not for test count.
- Backend route, schema, service mapping, and model-error changes require backend API tests.
- Frontend UI changes require lint/build, plus browser smoke when possible; if browser smoke cannot be performed, report that limitation explicitly.
- Add automated tests when a stable frontend test harness exists or when the change introduces testable logic.
- Normalization or data-contract changes require focused checks for the affected script/schema and docs alignment.
- Do not approve behavior changes that lack a matching validation path.

## 2. Keep Backend Tests on the Required Python 3.12 Environment

- Backend tests must run from `/Users/benj/Documents/Coding/VenusHacks26/backend` with the required Python 3.12 environment active:

```bash
source /Users/benj/Documents/Coding/cardiac_mvp/.venv/bin/activate
cd /Users/benj/Documents/Coding/VenusHacks26/backend
python -m pytest
```

- Focused agent runtime tests:

```bash
python -m pytest tests/test_agent_runtime.py
```

- Focused prenatal API tests:

```bash
python -m pytest tests/test_prenatal_cvd_api.py
```

- Do not use system Python or bare `pytest`. In this local workspace, use the documented Python 3.12 environment unless the user explicitly asks to change backend environment setup.

## 3. Test Public API Behavior Through FastAPI

- Public API behavior must be tested through the FastAPI app/client path.
- Helper-only tests are not enough for request validation, HTTP status codes, response fields, or safe error bodies.
- Keep health and prenatal screening route coverage current when public API behavior changes.

## 4. Preserve Prenatal API Contract Coverage

Tests for `POST /api/screening/prenatal-cvd` should cover applicable behavior when changed:

- successful prenatal request with frontend-shaped camelCase fields
- unsupported `pregnancyMode`
- null booleans
- non-numeric numeric fields
- required response fields and safety/disclaimer fields
- `prenatal_cvd_followup_proxy_probability` alias
- model-unavailable `503` behavior

When the request or response contract changes, update `backend/API_REFERENCES.md` in the same change.

## 5. Keep Model Failure Tests Safe and Generic

- Tests should assert that model-layer failures return a safe `503` response.
- Do not assert or document local filesystem paths, artifact internals, raw exception strings, or stack traces as public API behavior.
- Failure tests should verify generic user-safe details such as `Prenatal screening model is unavailable.`

## 6. Keep Frontend Validation Honest

- `npm run lint` and `npm run build` are the current automated frontend checks.
- These checks do not prove user-visible flow behavior; browser smoke is required for UI changes when possible.
- Do not claim frontend unit or browser e2e coverage exists unless the corresponding scripts/specs exist in the repo.
- If a UI change cannot be browser-tested, report that limitation explicitly.

## 7. Do Not Add Live or External Calls to Deterministic Tests

- Deterministic tests must not depend on live clinical systems, external APIs, provider credentials, live LLM providers, or local raw datasets.
- Use small fixtures, monkeypatching, fake runtime factories, or FastAPI test clients for backend behavior.
- Any future live validation must be explicitly opt-in, documented with its required environment variables, and excluded from normal local test commands.

## 8. Keep Test Data Minimal and Non-Sensitive

- Test fixtures should be synthetic, minimal, and safe to commit.
- Do not commit real patient data, raw datasets, credentials, or generated local artifacts.
- Keep model-artifact tests focused on the shipped default artifacts unless the user explicitly asks to test research artifacts.

## 9. Update Test Docs With Test Workflow Changes

- When adding a test command, moving tests, adding a frontend test harness, or changing required validation, update `docs/testing-and-validation.md`.
- Keep README and AGENTS validation guidance aligned when commands or ports change.
- Remove stale commands instead of leaving them as active workflow instructions.

## 10. Remove Stale Donor-Project Test Rules

- Do not add active test rules for nonexistent paths, scripts, services, providers, auth systems, generated inventories, test harnesses, or workflows.
- If an inherited rule has a useful principle, rewrite it to current VenusHacks files and commands before keeping it.
- If a rule cannot be validated against current code, tests, or docs, remove it from active test rules.

## 11. Keep Agent Runtime Tests Deterministic

- `backend/tests/test_agent_runtime.py` should cover provider selection, safe configuration errors, thread IDs, tool allowlists, subagent allowlists, and runtime profile metadata.
- Agent runtime tests must use monkeypatching, fake models, or fake agent factories instead of live OpenRouter, OpenAI, or OpenAI-compatible provider calls.
- Live provider smoke checks must be opt-in, skipped by default, and documented with required environment variables before they are added.
