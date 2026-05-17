# prenatal_after_ultrasound_minimal8

- Model version: `2026-05-16`
- Package role: shipped MVP default copied from A2 after-ultrasound minimal8 with known/suspected multiple gestation.

## A1 vs A2
- A1 `prenatal_early_minimal7`: early-prenatal fallback when multiple gestation status is unavailable.
- A2 `prenatal_after_ultrasound_minimal8`: accepted MVP default after ultrasound when multiple gestation is known or suspected.

## Target Definition
`prenatal_cvd_followup_proxy_v1` is positive if any of: gestational hypertension, eclampsia, gestational diabetes, severe maternal morbidity proxy, preterm birth, or low birth weight.

## Proxy-Label Warning
The target is a derived pregnancy follow-up proxy, not confirmed long-term cardiovascular disease.
The model output is a follow-up priority signal, not one cardiovascular-risk probability.

## Training Data
`/Users/benj/Documents/Coding/cardiac_mvp/data/cdc-natality/derived/natality_2024_structured.csv`

## Feature List
- `mother_age`
- `mother_bmi`
- `prepregnancy_hypertension`
- `prepregnancy_diabetes`
- `prior_adverse_pregnancy_history`
- `prior_live_births`
- `smoking_before_or_during_pregnancy`
- `multiple_gestation_known_or_suspected`

## Excluded Sensitive/Social Features
- `mother_race_6_code`
- `mother_hispanic_origin_recode`
- `mother_education_code`
- `father_education_code`
- `marital_status_code`
- `payment_source_recode`
- `wic_received`
- `father_age`
- `birth_year`

## Excluded Leakage/Outcome Fields
- `pregnancy_cvd_risk_proxy`
- `prenatal_cvd_followup_proxy_v1`
- `any_diabetes`
- `any_hypertensive_disorder`
- `severe_maternal_morbidity_proxy`
- `no_maternal_morbidity_reported`
- `gestational_diabetes`
- `gestational_hypertension`
- `eclampsia`
- `maternal_transfusion`
- `ruptured_uterus`
- `unplanned_hysterectomy`
- `maternal_icu`
- `obstetric_estimate_gestation_weeks`
- `gestation_recode_3`
- `birth_weight_grams`
- `birth_weight_recode_14`
- `birth_weight_recode_4`
- `abnormal_condition_nicu`
- `apgar_5_min`
- `apgar_10_min`
- `breastfed_at_discharge`
- `infant_sex`

## Thresholds
- Low/positive threshold: `0.200000`
- High threshold: `0.349010`

## Validation Metrics
- Recall: `0.8659`
- FNR: `0.1341`
- Precision: `0.2990`
- PR-AUC: `0.4467`
- Brier: `0.1853`

## Test Metrics
- Recall: `0.8663`
- FNR: `0.1337`
- Precision: `0.2989`
- PR-AUC: `0.4447`
- Brier: `0.1856`

## Tier Interpretation
- Low: routine education; low tier does not mean no clinical risk.
- Medium: broad follow-up planning signal; should not be treated as urgent.
- High: prioritized pregnancy follow-up risk review and postpartum planning.

## Fairness/Subgroup Limitations
- Low/normal BMI subgroup recall is weak.
- Age <25 recall is weak.
- Subgroup threshold diagnostics are diagnostic only; subgroup-specific thresholds are not implemented.

## Not Intended Uses
- Diagnosis
- Care denial
- Insurance decisions
- Medication changes
- Replacement for clinician judgment

## Clinical Safety Disclaimer
This is a risk-prioritization aid, not a diagnosis. Clinical judgment should guide care decisions. This is not a diagnostic model.

## Next Version Direction
The next model version should move from a single composite proxy to a two-signal risk profile:
- maternal CV/metabolic follow-up signal
- obstetric/neonatal adverse-outcome signal

The current composite signal should remain continuity/reference-only once the two-signal profile is shipped.
