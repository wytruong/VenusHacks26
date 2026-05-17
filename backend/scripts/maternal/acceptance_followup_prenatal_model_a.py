#!/usr/bin/env python3
"""Acceptance follow-up diagnostics for prenatal Model A."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.maternal.train_prenatal_cvd_model_a import (
    CandidateResult,
    build_prenatal_features,
    build_prenatal_target,
    calibration_report,
    clean_values,
    evaluate_variant,
    feature_coefficients,
    load_config,
    load_data,
    numeric,
    resolve_path,
    risk_tier,
    split_data,
    variants_to_run,
    write_json,
)


DEFAULT_CONFIG_PATH = ROOT / "configs/maternal/prenatal_model_a_v1.yaml"
DEFAULT_ARTIFACT_DIR = ROOT / "models/cdc-natality/prenatal_model_a_v1"
A2_ARTIFACT_DIR = ROOT / "models/cdc-natality/prenatal_after_ultrasound_minimal8"
TARGET_RECALLS = [0.85, 0.871, 0.90]
NO_DOMINANT_FACTOR = "No single dominant factor identified; score reflects the combined entered profile."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--data-path", type=Path)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--a2-artifact-dir", type=Path, default=A2_ARTIFACT_DIR)
    parser.add_argument("--max-rows", type=int)
    return parser.parse_args()


def prediction_metrics(y_true: pd.Series, y_prob: np.ndarray, threshold: float) -> dict[str, Any]:
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    recall = recall_score(y_true, y_pred, zero_division=0)
    flagged = int(y_pred.sum())
    return {
        "threshold": float(threshold),
        "recall": float(recall),
        "false_negative_rate": float(1.0 - recall),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "false_positive_rate": float(fp / (fp + tn)) if (fp + tn) else 0.0,
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "brier_score": float(brier_score_loss(y_true, y_prob)),
        "flagged_positive_count": flagged,
        "flagged_positive_pct": float(flagged / len(y_true)),
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
    }


def threshold_for_target_recall(y_true: pd.Series, y_prob: np.ndarray, target_recall: float) -> float:
    y_array = np.asarray(y_true)
    positive_scores = np.sort(y_prob[y_array == 1])[::-1]
    if len(positive_scores) == 0:
        return 0.0
    required_positive_count = int(np.ceil(target_recall * len(positive_scores)))
    required_positive_count = min(max(required_positive_count, 1), len(positive_scores))
    return float(positive_scores[required_positive_count - 1])


def equal_recall_comparison(results: list[CandidateResult], y_valid: pd.Series, y_test: pd.Series) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for result in results:
        for target_recall in TARGET_RECALLS:
            threshold = threshold_for_target_recall(y_valid, result.validation_probabilities, target_recall)
            for split, y_true, y_prob in (
                ("validation", y_valid, result.validation_probabilities),
                ("test", y_test, result.test_probabilities),
            ):
                rows.append(
                    {
                        "model": result.name,
                        "model_family": result.model_family,
                        "target_recall_operating_point": target_recall,
                        "split": split,
                        **prediction_metrics(y_true, y_prob, threshold),
                    }
                )
    return pd.DataFrame(rows)


def tier_outcomes(results: list[CandidateResult], y_test: pd.Series) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    y_array = np.asarray(y_test)
    for result in results:
        tiers = np.array([risk_tier(float(prob), result.thresholds) for prob in result.test_probabilities])
        positive_total = int(y_array.sum())
        medium_high_mask = tiers != "low"
        high_mask = tiers == "high"
        for tier in ("low", "medium", "high"):
            mask = tiers == tier
            positives = int(y_array[mask].sum())
            rows.append(
                {
                    "model": result.name,
                    "tier": tier,
                    "count": int(mask.sum()),
                    "pct": float(mask.mean()),
                    "observed_target_prevalence": float(y_array[mask].mean()) if mask.any() else 0.0,
                    "positive_cases_captured": positives,
                    "positive_cases_captured_pct": float(positives / positive_total) if positive_total else 0.0,
                    "false_negative_count_in_low_tier": positives if tier == "low" else 0,
                    "precision_high_tier": float(y_array[high_mask].mean()) if high_mask.any() else 0.0,
                    "precision_medium_high_combined": (
                        float(y_array[medium_high_mask].mean()) if medium_high_mask.any() else 0.0
                    ),
                }
            )
    return pd.DataFrame(rows)


def add_subgroup_bands(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["age_band"] = pd.cut(
        numeric(out["mother_age"]),
        bins=[0, 24, 29, 34, 39, 120],
        labels=["<25", "25-29", "30-34", "35-39", "40+"],
        include_lowest=True,
    ).astype("string")
    out["bmi_band"] = pd.cut(
        numeric(out["mother_bmi"]),
        bins=[0, 18.5, 24.9, 29.9, 34.9, 39.9, 120],
        labels=["<18.5", "18.5-24.9", "25-29.9", "30-34.9", "35-39.9", "40+"],
        include_lowest=True,
    ).astype("string")
    return out


def subgroup_threshold_diagnostics(
    selected: CandidateResult,
    test_df: pd.DataFrame,
    y_test: pd.Series,
) -> pd.DataFrame:
    frame = add_subgroup_bands(test_df)
    frame["y_true"] = np.asarray(y_test)
    frame["y_prob"] = selected.test_probabilities
    frame["y_pred"] = (selected.test_probabilities >= selected.thresholds["low"]).astype(int)
    group_columns = [
        "age_band",
        "bmi_band",
        "mother_race_6_code",
        "mother_hispanic_origin_recode",
        "payment_source_recode",
        "wic_received",
    ]
    rows: list[dict[str, Any]] = []
    for column in group_columns:
        for value, group in frame.groupby(column, dropna=False, observed=False):
            if len(group) < 20 or group["y_true"].sum() == 0:
                continue
            recall = recall_score(group["y_true"], group["y_pred"], zero_division=0)
            required = threshold_for_target_recall(group["y_true"], group["y_prob"].to_numpy(), 0.85)
            rows.append(
                {
                    "subgroup_column": column,
                    "subgroup_value": str(value),
                    "sample_size": int(len(group)),
                    "target_positive_count": int(group["y_true"].sum()),
                    "current_threshold": selected.thresholds["low"],
                    "current_recall": float(recall),
                    "current_false_negative_rate": float(1.0 - recall),
                    "threshold_required_for_recall_0_85": required,
                    "diagnostic_basis": "test_set",
                }
            )
    return pd.DataFrame(rows)


def target_components(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "gestational_hypertension": (df["gestational_hypertension"] == True) | (df["gestational_hypertension"] == 1),
            "eclampsia": (df["eclampsia"] == True) | (df["eclampsia"] == 1),
            "gestational_diabetes": (df["gestational_diabetes"] == True) | (df["gestational_diabetes"] == 1),
            "severe_maternal_morbidity_proxy": (df["severe_maternal_morbidity_proxy"] == True)
            | (df["severe_maternal_morbidity_proxy"] == 1),
            "preterm_birth": numeric(df["obstetric_estimate_gestation_weeks"]) < 37,
            "low_birth_weight": numeric(df["birth_weight_grams"]) < 2500,
        }
    )


def summarize_group(
    group_name: str,
    cohort_name: str,
    df: pd.DataFrame,
    y_prob: np.ndarray,
    components: pd.DataFrame,
    features: list[str],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "analysis_group": group_name,
        "cohort": cohort_name,
        "count": int(len(df)),
        "predicted_probability_mean": float(np.mean(y_prob)) if len(y_prob) else np.nan,
        "predicted_probability_p25": float(np.quantile(y_prob, 0.25)) if len(y_prob) else np.nan,
        "predicted_probability_median": float(np.quantile(y_prob, 0.50)) if len(y_prob) else np.nan,
        "predicted_probability_p75": float(np.quantile(y_prob, 0.75)) if len(y_prob) else np.nan,
    }
    for component in components.columns:
        row[f"component_{component}_rate"] = float(components[component].mean()) if len(components) else np.nan
    for feature in features:
        values = numeric(df[feature])
        row[f"feature_{feature}_mean"] = float(values.mean()) if values.notna().any() else np.nan
        row[f"feature_{feature}_median"] = float(values.median()) if values.notna().any() else np.nan
    return row


def false_negative_analysis(
    selected: CandidateResult,
    test_df: pd.DataFrame,
    y_test: pd.Series,
) -> pd.DataFrame:
    frame = add_subgroup_bands(test_df).copy()
    y_array = np.asarray(y_test)
    y_pred = (selected.test_probabilities >= selected.thresholds["low"]).astype(int)
    components = target_components(test_df).reset_index(drop=True)
    frame = frame.reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    masks = {
        "bmi_lt_18_5": (frame["bmi_band"] == "<18.5").fillna(False),
        "bmi_18_5_to_24_9": (frame["bmi_band"] == "18.5-24.9").fillna(False),
        "age_lt_25": (frame["age_band"] == "<25").fillna(False),
    }
    for group_name, base_mask in masks.items():
        base = base_mask.to_numpy()
        fn_mask = base & (y_array == 1) & (y_pred == 0)
        caught_tp_mask = base & (y_array == 1) & (y_pred == 1)
        rows.append(
            summarize_group(
                group_name,
                "false_negative",
                frame.loc[fn_mask, selected.features],
                selected.test_probabilities[fn_mask],
                components.loc[fn_mask],
                selected.features,
            )
        )
        rows.append(
            summarize_group(
                group_name,
                "caught_true_positive",
                frame.loc[caught_tp_mask, selected.features],
                selected.test_probabilities[caught_tp_mask],
                components.loc[caught_tp_mask],
                selected.features,
            )
        )
    return pd.DataFrame(rows)


def contributing_factors(row: pd.Series) -> list[str]:
    factors: list[str] = []
    if row.get("prepregnancy_hypertension") == 1:
        factors.append("pre-pregnancy hypertension")
    if row.get("prepregnancy_diabetes") == 1:
        factors.append("pre-pregnancy diabetes")
    if pd.notna(row.get("mother_bmi")) and float(row["mother_bmi"]) >= 30:
        factors.append("higher pre-pregnancy BMI")
    if pd.notna(row.get("mother_age")) and float(row["mother_age"]) >= 35:
        factors.append("advanced maternal age")
    if row.get("prior_adverse_pregnancy_history") == 1:
        factors.append("prior adverse pregnancy history")
    if row.get("smoking_before_or_during_pregnancy") == 1:
        factors.append("smoking before or during pregnancy")
    if row.get("multiple_gestation_known_or_suspected") == 1:
        factors.append("multiple gestation")
    return factors[:3] or [NO_DOMINANT_FACTOR]


def updated_sample_predictions(selected: CandidateResult, test_df: pd.DataFrame, y_test: pd.Series) -> pd.DataFrame:
    rows = test_df[selected.features].head(20).copy()
    probs = selected.test_probabilities[: len(rows)]
    rows["true_target"] = np.asarray(y_test.head(len(rows)))
    rows["prenatal_cvd_followup_probability"] = [f"{prob:.5f}" for prob in probs]
    rows["risk_tier"] = [risk_tier(float(prob), selected.thresholds) for prob in probs]
    rows["risk_tier_note"] = "Risk tier is based on the unrounded model score."
    rows["top_3_contributing_factors"] = [json.dumps(contributing_factors(row)) for _, row in rows.iterrows()]
    return rows


def save_a2_artifact(config: dict[str, Any], source_path: Path, result: CandidateResult, artifact_dir: Path) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(result.model, artifact_dir / "model.joblib")
    joblib.dump(result.preprocessor, artifact_dir / "preprocessor.joblib")
    joblib.dump(result.calibrator, artifact_dir / "calibrator.joblib")
    a2_config = dict(config)
    a2_config["model_name"] = "prenatal_after_ultrasound_minimal8"
    a2_config["artifact_dir"] = artifact_dir.relative_to(ROOT).as_posix()
    a2_config["features"] = result.features
    a2_config["numeric_features"] = result.numeric_features
    a2_config["binary_features"] = result.binary_features
    (artifact_dir / "feature_config.yaml").write_text(yaml.safe_dump(a2_config, sort_keys=False))
    write_json(artifact_dir / "thresholds.json", result.thresholds)
    write_json(artifact_dir / "metrics_validation.json", result.validation_metrics)
    write_json(artifact_dir / "metrics_test.json", result.test_metrics)
    calibration_report(pd.Series(np.zeros(len(result.test_probabilities))), result.test_probabilities).to_csv(
        artifact_dir / "score_distribution_report.csv", index=False
    )
    lines = [
        "# prenatal_after_ultrasound_minimal8",
        "",
        "## Intended Use",
        "Model A2 is the after-ultrasound prenatal variant for cases where multiple gestation status is known or suspected.",
        "",
        "## Source",
        f"- Training data: `{source_path}`",
        "- Base target: `prenatal_cvd_followup_proxy_v1`",
        "",
        "## Features",
        *[f"- `{feature}`" for feature in result.features],
        "",
        "## Limitation",
        "Use Model A1 minimal7 when multiple gestation status is unavailable or clinically inappropriate for timing.",
        "",
    ]
    (artifact_dir / "model_card.md").write_text("\n".join(lines))


def updated_model_card(selected: CandidateResult, source_path: Path) -> str:
    return "\n".join(
        [
            "# Updated Model Card: Prenatal CV-Risk Prioritization Model A1",
            "",
            "## Selected Artifact",
            f"`{selected.name}`",
            "",
            "## Intended Use",
            "Counseling, monitoring, and postpartum follow-up planning support before delivery.",
            "",
            "## Not Intended Use",
            "Diagnosis, care denial, insurance decisions, medication changes, or replacement for clinician judgment.",
            "",
            "## Training Data",
            f"`{source_path}`",
            "",
            "## Known Limitations",
            "- Proxy target, not confirmed long-term cardiovascular disease.",
            "- Low/normal BMI subgroup recall is weak.",
            "- Age <25 recall is weak.",
            "- Medium tier is broad and should not be treated as urgent.",
            "- Low tier does not mean no clinical risk.",
            "- Model should support counseling/follow-up planning only, not diagnosis or care denial.",
            "",
            "## Tier Interpretation",
            "- Low: routine education; not a guarantee of no clinical risk.",
            "- Medium: broad follow-up planning signal; not urgent by itself.",
            "- High: prioritized cardiovascular-risk review and postpartum follow-up planning.",
            "",
            "## Safety Text",
            "This is a risk-prioritization aid, not a diagnosis. Clinical judgment should guide care decisions.",
            "",
        ]
    )


def main() -> None:
    args = parse_args()
    config = load_config(args.config.resolve())
    df, source_path = load_data(config, args.data_path, args.max_rows)
    df[config["target"]] = build_prenatal_target(df)
    df = clean_values(build_prenatal_features(df))
    train_df, valid_df, test_df, y_train, y_valid, y_test = split_data(df, df[config["target"]], config)
    results = [
        evaluate_variant(config, variant, train_df, valid_df, test_df, y_train, y_valid, y_test, "sigmoid")
        for variant in variants_to_run(config, "both")
    ]
    selected = next(result for result in results if result.name == "minimal7_no_multiple_calibrated_logistic_regression")
    minimal8_logistic = next(result for result in results if result.name == "minimal8_calibrated_logistic_regression")

    artifact_dir = args.artifact_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)
    equal_recall_comparison(results, y_valid, y_test).to_csv(
        artifact_dir / "model_comparison_equal_recall.csv", index=False
    )
    tier_outcomes(results, y_test).to_csv(artifact_dir / "tier_outcomes.csv", index=False)
    subgroup_threshold_diagnostics(selected, test_df, y_test).to_csv(
        artifact_dir / "subgroup_threshold_diagnostics.csv", index=False
    )
    false_negative_analysis(selected, test_df, y_test).to_csv(
        artifact_dir / "false_negative_analysis_bmi_age.csv", index=False
    )
    updated_sample_predictions(selected, test_df, y_test).to_csv(
        artifact_dir / "updated_sample_predictions.csv", index=False
    )
    (artifact_dir / "updated_model_card.md").write_text(updated_model_card(selected, source_path))

    metrics_test = json.loads((artifact_dir / "metrics_test.json").read_text())
    metrics_test["acceptance_followup"] = {
        "equal_recall_report": "model_comparison_equal_recall.csv",
        "tier_outcomes_report": "tier_outcomes.csv",
        "subgroup_threshold_diagnostics": "subgroup_threshold_diagnostics.csv",
        "false_negative_analysis": "false_negative_analysis_bmi_age.csv",
        "a2_artifact_dir": args.a2_artifact_dir.relative_to(ROOT).as_posix(),
    }
    write_json(artifact_dir / "metrics_test.json", metrics_test)

    save_a2_artifact(config, source_path, minimal8_logistic, args.a2_artifact_dir)
    print(f"artifact_dir={artifact_dir}")
    print(f"a2_artifact_dir={args.a2_artifact_dir}")
    print(f"METRIC validation_positive_recall={selected.validation_metrics['positive_recall']:.10f}")
    print(f"METRIC test_positive_recall={selected.test_metrics['positive_recall']:.10f}")


if __name__ == "__main__":
    main()
