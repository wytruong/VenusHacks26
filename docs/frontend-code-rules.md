# Frontend Code Rules

These rules apply to the React/Vite frontend in this repository, including the single-page app flow, pregnancy risk form, upload placeholders, 3D heart model, insight panels, styling, and frontend/backend integration.

Use these rules with `AGENTS.md` and `README.md`. When docs conflict with executable code, verify the current code and update stale docs.

## Rule Index

1. Keep Frontend Docs and Runtime Commands Aligned
2. Preserve the Core App Flow Unless Redesigning It
3. Keep Placeholder Clinical Flows Honest
4. Keep API Integration Typed and User-Safe
5. Keep 3D Heart Asset Changes Deliberate
6. Protect 3D and Animation Performance
7. Preserve Accessibility Affordances
8. Keep Medical Safety Copy Clear
9. Keep State Ownership Understandable
10. Keep Styling Consistent With the Existing Design
11. Avoid Stale Donor-Project Rules and Vocabulary
12. Validate Frontend Changes With Real Browser Use When UI Changes

## 1. Keep Frontend Docs and Runtime Commands Aligned

- The frontend stack is React 19, TypeScript, Vite 8, Tailwind CSS v4, Framer Motion, Three.js, React Three Fiber, and Drei.
- Run frontend commands from the repository root:

```bash
npm run dev
npm run lint
npm run build
```

- The frontend dev server is pinned to `http://localhost:45260` with `strictPort: true` in `vite.config.ts`.
- When setup commands, ports, user-facing workflows, or frontend capabilities change, update `README.md` and any affected docs in the same change.
- Update root `AGENTS.md` only for durable repo-wide context changes, such as changed default ports, major file moves, new runtime services, or cross-cutting guardrails.
- Remove copied frontend rules that do not map to current VenusHacks files, scripts, services, or documented workflows.

## 2. Preserve the Core App Flow Unless Redesigning It

- The app keeps state in `src/App.tsx` while route ownership is explicit in `src/routes/*`.
- Preserve the expected user flow unless the task explicitly redesigns it:
  1. `/` particle intro
  2. `/onboarding` pregnancy onboarding
  3. `/risk-profile` prenatal risk form
  4. `/heart` heart reveal with right-side insight panels
- Upload entry routes are `/uploads/ecg` and `/uploads/doctor-note`.
- Keep direct route loads safe: initialize view state or redirect to an earlier safe route, never crash on missing in-memory state.

## 3. Keep Placeholder Clinical Flows Honest

- Doctor-note OCR and ECG analysis are currently placeholder/mock frontend flows.
- Prenatal risk submission is wired to the backend `POST /api/screening/prenatal-cvd` endpoint; postpartum risk remains a UI-only backlog state.
- Placeholder flows must not imply real diagnosis, real OCR, real ECG interpretation, or live backend analysis where no endpoint exists.
- When replacing a placeholder with real behavior, update UI copy, error states, loading states, docs, and tests/checks for that behavior.

## 4. Keep API Integration Typed and User-Safe

- The backend currently exposes `POST /api/screening/prenatal-cvd`; the frontend uses a typed API client in `src/api/screening.ts` and submits from `src/App.tsx`.
- Keep the frontend API base URL aligned with backend runtime (`VITE_API_BASE_URL`, default `http://127.0.0.1:45261`).
- Postpartum form submissions must not be sent to the prenatal endpoint.
- Additional API wiring should stay near the pregnancy risk submit/result state unless the app is refactored first.
- Keep frontend payload fields aligned with `backend/API_REFERENCES.md` and backend schemas.
- Handle loading, validation errors, backend unavailability, and empty/missing responses with user-safe messages.
- Do not expose backend stack traces, local paths, or model artifact details in the UI.

## 5. Keep 3D Heart Asset Changes Deliberate

- Active heart model asset: `public/heart-model/scene.quality.glb`.
- Heart model files are large; do not replace or rename them casually.
- `public/heart-model/scene.bin` is intentionally ignored because it exceeds GitHub's normal file-size limit.
- Mesh/callout behavior depends on model node names in `src/components/HeartModel.tsx`.
- If model assets change, verify mesh mappings, callouts, pointer interactions, and keyboard/focus behavior in-browser.

## 6. Protect 3D and Animation Performance

- Keep expensive work out of animation/render loops, pointer-move handlers, and frame callbacks.
- Avoid unnecessary React remounts of the 3D scene, material churn, geometry reprocessing, or full-scene resets for ordinary UI state changes.
- Prefer memoized assets, stable refs, lazy loading, and bounded animation work for Three.js/R3F behavior.
- Motion and particle effects should degrade gracefully on smaller screens or constrained GPUs.

## 7. Preserve Accessibility Affordances

- Keep keyboard-triggered upload zones, focus-visible rings, semantic controls, and readable labels.
- New forms or panels must provide clear labels, validation text, focus order, and keyboard access.
- Animated or 3D backgrounds must not reduce text contrast or make focus states hard to see.
- Consider reduced-motion behavior when adding Framer Motion, particle, or camera animation changes.

## 8. Keep Medical Safety Copy Clear

- Clinical-facing UI copy must describe the model as a screening or follow-up prioritization aid, not a diagnosis.
- Do not present risk scores as direct cardiovascular disease probabilities unless the backend contract explicitly says they are.
- Keep disclaimers and recommended follow-up language aligned with backend response fields and `backend/API_REFERENCES.md`.

## 9. Keep State Ownership Understandable

- `src/App.tsx` may own the main flow state while the app remains a single stateful flow.
- `src/components/HeartModel.tsx` should own 3D heart loading, mesh selection, callouts, and direct 3D interaction concerns.
- Extract components, hooks, or API helpers only when they clarify real ownership; do not add abstractions for hypothetical future routes or services.
- Keep risk payload/result state typed and close to the code that submits or renders it.

## 10. Keep Styling Consistent With the Existing Design

- Reuse existing visual language, spacing rhythm, motion style, and Tailwind patterns unless the task explicitly redesigns them.
- Avoid one-off hard-coded layout fixes that break the core responsive flow or right-side insight panel behavior.
- Reject UI changes with large dead zones, cramped form groups, inconsistent section gaps, or breakpoint-specific spacing jumps.
- Check mobile and desktop states when changing onboarding, upload zones, panels, or the heart model composition.

## 11. Avoid Stale Donor-Project Rules and Vocabulary

- Do not add active frontend rules for nonexistent paths, scripts, services, auth systems, providers, routes, or test harnesses.
- If a copied rule has a useful principle, rewrite it in VenusHacks terms before keeping it.
- If a rule cannot be tied to current code, docs, or near-term user-facing behavior, remove it from active rules.

## 12. Validate Frontend Changes With Real Browser Use When UI Changes

- For UI changes, start the dev server and exercise the changed flow in a browser when possible.
- Golden-path checks should cover the pregnancy onboarding/risk flow, heart reveal, insight panels, and any changed upload surface.
- Edge checks should cover validation errors, backend unavailable states if API wiring changes, keyboard interaction, and small viewport behavior.
- If browser validation cannot be performed, say so explicitly instead of claiming the UI was verified.
