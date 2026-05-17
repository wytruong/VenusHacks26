#!/usr/bin/env python3
"""Export clean A1/A2 prenatal Model A artifact packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import brier_score_loss, precision_score, recall_score
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.maternal.acceptance_followup_prenatal_model_a import contributing_factors
from scripts.maternal.train_prenatal_cvd_model_a import (
    CandidateResult,
    build_prenatal_features,
    build_prenatal_target,
    calibration_report,
    clean_values,
    evaluate_variant,
    feature_coefficients,
    feature_distributions,
    feature_missingness,
    load_config,
    load_data,
    risk_tier,
    split_data,
    validate_no_leakage,
)


DEFAULT_CONFIG_PATH = ROOT / "configs/maternal/prenatal_model_a_v1.yaml"
DEFAULT_A1_DIR = ROOT / "models/cdc-natality/prenatal_early_minimal7"
DEFAULT_A2_DIR = ROOT / "models/cdc-natality/prenatal_after_ultrasound_minimal8"
MODEL_VERSION = "2026-05-16"
DISCLAIMER = "This is a risk-prioritization aid, not a diagnosis. Clinical judgment should guide care decisions."
NOTE = "Risk tier is based on the unrounded model score."
EXCLUDED_SENSITIVE = [
    "mother_race_6_code",
    "mother_hispanic_origin_recode",
    "mother_education_code",
    "father_education_code",
    "marital_status_code",
    "payment_source_recode",
    "wic_received",
    "father_age",
    "birth_year",
]
EXCLUDED_OUTCOMES = [
    "pregnancy_cvd_risk_proxy",
    "prenatal_cvd_followup_proxy_v1",
    "any_diabetes",
    "any_hypertensive_disorder",
    "severe_maternal_morbidity_proxy",
    "no_maternal_morbidity_reported",
    "gestational_diabetes",
    "gestational_hypertension",
    "eclampsia",
    "maternal_transfusion",
    "ruptured_uterus",
    "unplanned_hysterectomy",
    "maternal_icu",
    "obstetric_estimate_gestation_weeks",
    "gestation_recode_3",
    "birth_weight_grams",
    "birth_weight_recode_14",
    "birth_weight_recode_4",
    "abnormal_condition_nicu",
    "apgar_5_min",
    "apgar_10_min",
    "breastfed_at_discharge",
    "infant_sex",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--data-path", type=Path)
    parser.add_argument("--a1-dir", type=Path, default=DEFAULT_A1_DIR)
    parser.add_argument("--a2-dir", type=Path, default=DEFAULT_A2_DIR)
    parser.add_argument("--max-rows", type=int)
    return parser.parse_args()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def target_components(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "gestational_hypertension": (df["gestational_hypertension"] == True) | (df["gestational_hypertension"] == 1),
            "eclampsia": (df["eclampsia"] == True) | (df["eclampsia"] == 1),
            "gestational_diabetes": (df["gestational_diabetes"] == True) | (df["gestational_diabetes"] == 1),
            "severe_maternal_morbidity_proxy": (df["severe_maternal_morbidity_proxy"] == True)
            | (df["severe_maternal_morbidity_proxy"] == 1),
            "preterm_birth": pd.to_numeric(df["obstetric_estimate_gestation_weeks"], errors="coerce") < 37,
            "low_birth_weight": pd.to_numeric(df["birth_weight_grams"], errors="coerce") < 2500,
        }
    )


def score_distribution_report(y_true: pd.Series, y_prob: np.ndarray, bins: int = 10) -> pd.DataFrame:
    frame = pd.DataFrame({"y": np.asarray(y_true), "probability": y_prob})
    frame["score_bin"] = pd.cut(frame["probability"], bins=np.linspace(0.0, 1.0, bins + 1), include_lowest=True)
    report = (
        frame.groupby("score_bin", observed=False)
        .agg(
            sample_size=("y", "size"),
            mean_predicted_risk=("probability", "mean"),
            observed_target_rate=("y", "mean"),
            positives=("y", "sum"),
        )
        .reset_index()
    )
    report["negatives"] = report["sample_size"] - report["positives"]
    report["score_bin"] = report["score_bin"].astype(str)
    return report[
        ["score_bin", "sample_size", "mean_predicted_risk", "observed_target_rate", "positives", "negatives"]
    ]


def fairness_report(
    config: dict[str, Any],
    result: CandidateResult,
    test_df: pd.DataFrame,
    y_test: pd.Series,
) -> pd.DataFrame:
    frame = test_df[config["audit_only_columns"]].copy()
    frame["age_band"] = pd.cut(
        pd.to_numeric(test_df["mother_age"], errors="coerce"),
        bins=[0, 24, 29, 34, 39, 120],
        labels=["<25", "25-29", "30-34", "35-39", "40+"],
        include_lowest=True,
    ).astype("string")
    frame["bmi_band"] = pd.cut(
        pd.to_numeric(test_df["mother_bmi"], errors="coerce"),
        bins=[0, 18.5, 24.9, 29.9, 34.9, 39.9, 120],
        labels=["<18.5", "18.5-24.9", "25-29.9", "30-34.9", "35-39.9", "40+"],
        include_lowest=True,
    ).astype("string")
    frame["y_true"] = np.asarray(y_test)
    frame["y_pred"] = (result.test_probabilities >= result.thresholds["low"]).astype(int)
    frame["y_prob"] = result.test_probabilities
    rows: list[dict[str, Any]] = []
    for column in [
        "mother_race_6_code",
        "mother_hispanic_origin_recode",
        "payment_source_recode",
        "wic_received",
        "age_band",
        "bmi_band",
    ]:
        for value, group in frame.groupby(column, dropna=False, observed=False):
            if len(group) < 20:
                continue
            recall = recall_score(group["y_true"], group["y_pred"], zero_division=0)
            rows.append(
                {
                    "subgroup_column": column,
                    "subgroup_value": str(value),
                    "sample_size": int(len(group)),
                    "target_prevalence": float(group["y_true"].mean()),
                    "positive_recall": float(recall),
                    "false_negative_rate": float(1.0 - recall),
                    "precision": float(precision_score(group["y_true"], group["y_pred"], zero_division=0)),
                    "brier_score": float(brier_score_loss(group["y_true"], group["y_prob"])),
                }
            )
    return pd.DataFrame(rows)


def tier_outcomes(result: CandidateResult, y_test: pd.Series) -> pd.DataFrame:
    y_array = np.asarray(y_test)
    tiers = np.array([risk_tier(float(prob), result.thresholds) for prob in result.test_probabilities])
    medium_high = tiers != "low"
    high = tiers == "high"
    positive_total = int(y_array.sum())
    rows: list[dict[str, Any]] = []
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
                "precision_high_tier": float(y_array[high].mean()) if high.any() else 0.0,
                "precision_medium_high_combined": float(y_array[medium_high].mean()) if medium_high.any() else 0.0,
            }
        )
    return pd.DataFrame(rows)


def sample_predictions(result: CandidateResult, test_df: pd.DataFrame, y_test: pd.Series) -> pd.DataFrame:
    rows = test_df[result.features].head(20).copy()
    probs = result.test_probabilities[: len(rows)]
    rows["true_target"] = np.asarray(y_test.head(len(rows)))
    rows["prenatal_cvd_followup_probability"] = [f"{prob:.5f}" for prob in probs]
    rows["risk_tier"] = [risk_tier(float(prob), result.thresholds) for prob in probs]
    rows["risk_tier_note"] = NOTE
    rows["top_3_contributing_factors"] = [json.dumps(contributing_factors(row)) for _, row in rows.iterrows()]
    for _, row in rows.iterrows():
        if row["risk_tier"] in {"medium", "high"}:
            factors = json.loads(row["top_3_contributing_factors"])
            if not factors:
                raise AssertionError("medium/high prediction has no contributing factors")
    return rows


def metrics_payload(model_name: str, result: CandidateResult, split: str) -> dict[str, Any]:
    metrics = result.validation_metrics if split == "validation" else result.test_metrics
    return {
        "model_name": model_name,
        "selected_model": result.name,
        **metrics,
    }


def model_card(
    model_name: str,
    model_version: str,
    use_case: str,
    source_path: Path,
    result: CandidateResult,
) -> str:
    return "\n".join(
        [
            f"# {model_name}",
            "",
            f"- Model version: `{model_version}`",
            f"- Package role: {use_case}",
            "",
            "## A1 vs A2",
            "- A1 `prenatal_early_minimal7`: early-prenatal fallback when multiple gestation status is unavailable.",
            "- A2 `prenatal_after_ultrasound_minimal8`: accepted MVP default after ultrasound when multiple gestation is known or suspected.",
            "",
            "## Target Definition",
            "`prenatal_cvd_followup_proxy_v1` is positive if any of: gestational hypertension, eclampsia, gestational diabetes, severe maternal morbidity proxy, preterm birth, or low birth weight.",
            "",
            "## Proxy-Label Warning",
            "The target is a derived pregnancy follow-up proxy, not confirmed long-term cardiovascular disease.",
            "",
            "## Training Data",
            f"`{source_path}`",
            "",
            "## Feature List",
            *[f"- `{feature}`" for feature in result.features],
            "",
            "## Excluded Sensitive/Social Features",
            *[f"- `{feature}`" for feature in EXCLUDED_SENSITIVE],
            "",
            "## Excluded Leakage/Outcome Fields",
            *[f"- `{feature}`" for feature in EXCLUDED_OUTCOMES],
            "",
            "## Thresholds",
            f"- Low/positive threshold: `{result.thresholds['low']:.6f}`",
            f"- High threshold: `{result.thresholds['high']:.6f}`",
            "",
            "## Validation Metrics",
            f"- Recall: `{result.validation_metrics['positive_recall']:.4f}`",
            f"- FNR: `{result.validation_metrics['false_negative_rate']:.4f}`",
            f"- Precision: `{result.validation_metrics['precision']:.4f}`",
            f"- PR-AUC: `{result.validation_metrics['pr_auc']:.4f}`",
            f"- Brier: `{result.validation_metrics['brier_score']:.4f}`",
            "",
            "## Test Metrics",
            f"- Recall: `{result.test_metrics['positive_recall']:.4f}`",
            f"- FNR: `{result.test_metrics['false_negative_rate']:.4f}`",
            f"- Precision: `{result.test_metrics['precision']:.4f}`",
            f"- PR-AUC: `{result.test_metrics['pr_auc']:.4f}`",
            f"- Brier: `{result.test_metrics['brier_score']:.4f}`",
            "",
            "## Tier Interpretation",
            "- Low: routine education; low tier does not mean no clinical risk.",
            "- Medium: broad follow-up planning signal; should not be treated as urgent.",
            "- High: prioritized cardiovascular-risk review and postpartum follow-up planning.",
            "",
            "## Fairness/Subgroup Limitations",
            "- Low/normal BMI subgroup recall is weak.",
            "- Age <25 recall is weak.",
            "- Subgroup threshold diagnostics are diagnostic only; subgroup-specific thresholds are not implemented.",
            "",
            "## Not Intended Uses",
            "- Diagnosis",
            "- Care denial",
            "- Insurance decisions",
            "- Medication changes",
            "- Replacement for clinician judgment",
            "",
            "## Clinical Safety Disclaimer",
            f"{DISCLAIMER} This is not a diagnostic model.",
            "",
        ]
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def consistency_check(
    artifact_dir: Path,
    model_name: str,
    result: CandidateResult,
    leakage_audit: dict[str, Any],
) -> None:
    feature_config = yaml.safe_load((artifact_dir / "feature_config.yaml").read_text())
    if feature_config["model_name"] != model_name:
        raise AssertionError("feature_config model_name mismatch")
    if len(result.features) != len(result.preprocessor.get_feature_names_out()):
        raise AssertionError("model feature count does not match preprocessor feature count")
    coeffs = pd.read_csv(artifact_dir / "feature_coefficients.csv")
    if set(coeffs["feature"]) != set(result.preprocessor.get_feature_names_out()):
        raise AssertionError("feature_coefficients.csv does not match model features")
    sample = pd.read_csv(artifact_dir / "sample_predictions.csv")
    if not set(result.features).issubset(sample.columns):
        raise AssertionError("sample_predictions.csv missing model input features")
    for metrics_path in ("metrics_validation.json", "metrics_test.json"):
        metrics = json.loads((artifact_dir / metrics_path).read_text())
        if metrics["model_name"] != model_name:
            raise AssertionError(f"{metrics_path} model_name mismatch")
    card_first_line = (artifact_dir / "model_card.md").read_text().splitlines()[0].lstrip("# ")
    if card_first_line != model_name:
        raise AssertionError("model_card.md model name mismatch")
    score_report = pd.read_csv(artifact_dir / "score_distribution_report.csv")
    if (score_report["observed_target_rate"].fillna(0) == 0).all():
        raise AssertionError("score distribution observed rates are all zero")
    if not leakage_audit["passed"]:
        raise AssertionError("leakage audit failed")


def artifact_manifest(
    artifact_dir: Path,
    model_name: str,
    source_path: Path,
    result: CandidateResult,
    target: str,
) -> dict[str, Any]:
    artifacts = sorted(path for path in artifact_dir.iterdir() if path.is_file() and path.name != "artifact_manifest.json")
    return {
        "model_name": model_name,
        "model_version": MODEL_VERSION,
        "artifact_timestamp": datetime.now(UTC).isoformat(),
        "git_commit": current_git_commit(),
        "training_data_path": str(source_path),
        "feature_list": result.features,
        "target": target,
        "threshold_file": "thresholds.json",
        "metrics_files": ["metrics_validation.json", "metrics_test.json"],
        "artifact_sha256": {path.name: sha256(path) for path in artifacts},
    }


def current_git_commit() -> str | None:
    import subprocess

    try:
        return subprocess.check_output(["git", "rev-parse", "--short=7", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return None


def export_package(
    artifact_dir: Path,
    model_name: str,
    use_case: str,
    config: dict[str, Any],
    source_path: Path,
    result: CandidateResult,
    test_df: pd.DataFrame,
    y_test: pd.Series,
    full_df: pd.DataFrame,
    full_y: pd.Series,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    leakage_audit = validate_no_leakage(config, result.features)
    combined_pipeline = Pipeline([("preprocessor", result.preprocessor), ("calibrator", result.calibrator)])

    joblib.dump(result.model, artifact_dir / "model.joblib")
    joblib.dump(result.preprocessor, artifact_dir / "preprocessor.joblib")
    joblib.dump(result.calibrator, artifact_dir / "calibrator.joblib")
    joblib.dump(combined_pipeline, artifact_dir / "combined_pipeline.joblib")
    package_config = dict(config)
    package_config["model_name"] = model_name
    package_config["model_version"] = MODEL_VERSION
    package_config["artifact_dir"] = artifact_dir.relative_to(ROOT).as_posix()
    package_config["features"] = result.features
    package_config["numeric_features"] = result.numeric_features
    package_config["binary_features"] = result.binary_features
    (artifact_dir / "feature_config.yaml").write_text(yaml.safe_dump(package_config, sort_keys=False))
    write_json(artifact_dir / "thresholds.json", result.thresholds)
    write_json(artifact_dir / "metrics_validation.json", metrics_payload(model_name, result, "validation"))
    write_json(artifact_dir / "metrics_test.json", metrics_payload(model_name, result, "test"))
    write_json(artifact_dir / "leakage_audit.json", leakage_audit)
    feature_coefficients(result).to_csv(artifact_dir / "feature_coefficients.csv", index=False)
    feature_missingness(full_df, result.features).to_csv(artifact_dir / "feature_missingness.csv", index=False)
    feature_distributions(full_df, full_y, result.features).to_csv(artifact_dir / "feature_distributions.csv", index=False)
    fairness_report(config, result, test_df, y_test).to_csv(artifact_dir / "fairness_report.csv", index=False)
    sample_predictions(result, test_df, y_test).to_csv(artifact_dir / "sample_predictions.csv", index=False)
    score_distribution_report(y_test, result.test_probabilities).to_csv(
        artifact_dir / "score_distribution_report.csv", index=False
    )
    tier_outcomes(result, y_test).to_csv(artifact_dir / "tier_outcomes.csv", index=False)
    (artifact_dir / "model_card.md").write_text(model_card(model_name, MODEL_VERSION, use_case, source_path, result))

    consistency_check(artifact_dir, model_name, result, leakage_audit)
    write_json(artifact_dir / "artifact_manifest.json", artifact_manifest(artifact_dir, model_name, source_path, result, config["target"]))


def main() -> None:
    args = parse_args()
    config = load_config(args.config.resolve())
    df, source_path = load_data(config, args.data_path, args.max_rows)
    df[config["target"]] = build_prenatal_target(df)
    df = clean_values(build_prenatal_features(df))
    train_df, valid_df, test_df, y_train, y_valid, y_test = split_data(df, df[config["target"]], config)
    variants = {variant["name"]: variant for variant in config["comparison_variants"]}
    a1 = evaluate_variant(
        config,
        variants["minimal7_no_multiple_calibrated_logistic_regression"],
        train_df,
        valid_df,
        test_df,
        y_train,
        y_valid,
        y_test,
        "sigmoid",
    )
    a2 = evaluate_variant(
        config,
        variants["minimal8_calibrated_logistic_regression"],
        train_df,
        valid_df,
        test_df,
        y_train,
        y_valid,
        y_test,
        "sigmoid",
    )
    export_package(
        args.a1_dir,
        "prenatal_early_minimal7",
        "A1 early-prenatal fallback without multiple gestation status.",
        config,
        source_path,
        a1,
        test_df,
        y_test,
        df,
        df[config["target"]],
    )
    export_package(
        args.a2_dir,
        "prenatal_after_ultrasound_minimal8",
        "A2 after-ultrasound accepted MVP default with known/suspected multiple gestation.",
        config,
        source_path,
        a2,
        test_df,
        y_test,
        df,
        df[config["target"]],
    )
    print(f"a1_artifact_dir={args.a1_dir}")
    print(f"a2_artifact_dir={args.a2_dir}")
    print(f"METRIC a2_validation_positive_recall={a2.validation_metrics['positive_recall']:.10f}")
    print(f"METRIC a2_test_positive_recall={a2.test_metrics['positive_recall']:.10f}")


if __name__ == "__main__":
    main()
