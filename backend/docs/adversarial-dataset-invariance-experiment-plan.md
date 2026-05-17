# Adversarial Dataset-Invariance Experiment Plan

## Summary

Build an experiment track that tests whether adversarial dataset-invariant learning improves ECG abnormal and rhythm detection across the three unified datasets. Train both Lead I and 12-lead versions, then compare baseline models against adversarial models using the existing patient-level train, validation, and test split plus cross-dataset holdout evaluation.

The goal is to reduce source-dataset shortcut learning while preserving or improving abnormal detection recall.

## Key Changes

- Add a training experiment module that reads `data/normalized/derived/unified_manifest.csv`.
- Filter to `include_for_training = true`.
- Build two dataloaders:
  - Lead I input: `(1, 5000)`, using only rows with confirmed `lead_order_source = wfdb_header` and Lead I present.
  - 12-lead input: `(12, 5000)`, using rows with usable 12-lead tensors and known or acceptable lead handling.
- Add disease targets from `normalized_labels`, starting with this compact hackathon target set:
  - `normal_or_sinus_reference`
  - `atrial_fibrillation_or_flutter`
  - `bradycardia_or_tachycardia`
  - `other_abnormal_needs_review`
- Add dataset targets from `original_source_dataset`:
  - `ptb-xl`
  - `ecg-arrhythmia`
  - `sph-ecg`
- Add model variants:
  - Baseline encoder plus disease head.
  - Adversarial encoder plus disease head plus gradient-reversal dataset head.
  - Run both variants for Lead I and 12-lead inputs.
- Use a lambda schedule for adversarial loss:
  - Epochs 1-3: `lambda = 0.0`
  - Later epochs: ramp to `0.05`
  - Cap at `0.1` only if validation disease recall does not drop.
- Track outputs under `data/experiments/dataset_invariance/`, including:
  - metrics CSV
  - config JSON
  - model checkpoints

## Evaluation

### Standard Patient Split

- Use the existing `split` column from the unified manifest.
- Train on `train`.
- Tune on `val`.
- Report final metrics on `test`.
- Do not tune on test.

### Cross-Dataset Holdout

- Train on two datasets.
- Validate from validation rows belonging to the training-source datasets.
- Test on the held-out dataset.
- Run three holdouts:
  - hold out PTB-XL
  - hold out ECG Arrhythmia
  - hold out SPH-ECG

### Required Metrics

- Disease AUROC
- Macro F1
- Abnormal recall
- Abnormal false-negative rate
- Dataset-head accuracy for adversarial models

The success target is that disease metrics improve or stay stable while dataset-head accuracy moves closer to chance level, roughly `33%`.

## QA Plan

### Round 1: Implementation And Data Correctness

Use multiple specialized reviews:

- Data agent: verify split usage, patient isolation, manifest filtering, Lead I extraction, SPH lead-order handling, and waveform tensor shapes.
- ML architecture agent: verify gradient reversal math, lambda schedule, loss wiring, model variants, and disease/dataset heads.
- Metrics agent: verify target construction, class imbalance handling, metric definitions, and threshold selection only on validation.

Patch all confirmed issues from Round 1 before running full experiments.

### Round 2: Experiment Validity And Result Integrity

Use multiple specialized reviews:

- Leakage agent: verify no patient overlap, no test tuning, no train/test file contamination, and cross-dataset holdout correctness.
- Robustness agent: compare baseline against adversarial runs, check whether invariance hurts abnormal recall, and flag over-strong lambda.
- Reporting agent: verify result tables include all model variants, all datasets, all splits, and clear pass/fail interpretation.

Patch confirmed issues from Round 2, rerun affected experiments, and regenerate reports.

## Assumptions

- Lead I v1 excludes SPH until SPH lead order is verified.
- SPH can still participate in 12-lead experiments only if the experiment treats its channel order as dataset-native and does not claim named lead semantics.
- The first objective is abnormal and rhythm triage, not exact disease diagnosis.
- Adversarial dataset-invariance is an ablation, not automatically the final model.
- The adversarial model wins only if validation and test disease performance stays stable or improves.
- Existing unified manifest and patient-level splits remain the source of truth.
