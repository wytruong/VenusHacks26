#!/usr/bin/env python3
"""Run the prenatal Model A optimization/diagnostic v2 experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.maternal.acceptance_followup_prenatal_model_a import contributing_factors
from scripts.maternal.train_prenatal_cvd_model_a import (
    build_prenatal_features,
    clean_values,
    expected_calibration_error,
    feature_distributions,
    feature_missingness,
    load_config,
    load_data,
    numeric,
    split_data,
    to_binary,
    validate_no_leakage,
)


DEFAULT_CONFIG_PATH = ROOT / "configs/maternal/prenatal_model_a_v1.yaml"
DEFAULT_OUTPUT_DIR = ROOT / "models/cdc-natality/prenatal_model_a_optimization_v2"
MODEL_VERSION = "2026-05-16-optimization-v2"
ACCEPTED_A2_DIR = ROOT / "models/cdc-natality/prenatal_after_ultrasound_minimal8"
ACCEPTED_A1_DIR = ROOT / "models/cdc-natality/prenatal_early_minimal7"
NO_DOMINANT_FACTOR = "No single dominant factor identified; score reflects the combined entered profile."
SAFETY_NOTE = "This is a risk-prioritization aid, not a diagnosis."
TARGET_RECALL = 0.85
MIN_T4_POSITIVES = 500
MIN_T4_PREVALENCE = 0.002

BASE_FEATURES = [
    "mother_age",
    "mother_bmi",
    "prepregnancy_hypertension",
    "prepregnancy_diabetes",
    "prior_adverse_pregnancy_history",
    "prior_live_births",
    "smoking_before_or_during_pregnancy",
    "multiple_gestation_known_or_suspected",
]
NO_MULTIPLE_FEATURES = [feature for feature in BASE_FEATURES if feature != "multiple_gestation_known_or_suspected"]
INTERACTION_FEATURES = [
    "age_x_bmi",
    "young_and_normal_bmi",
    "young_and_low_bmi",
    "bmi_missing_flag",
    "hypertension_or_diabetes",
    "prior_adverse_or_smoking",
    "age_under25_x_bmi_normal",
    "age_under25_x_bmi_low",
    "multiple_gestation_x_bmi_low",
    "multiple_gestation_x_bmi_normal",
    "multiple_gestation_x_bmi_high",
    "multiple_gestation_x_age_under25",
    "multiple_gestation_x_age_35_plus",
]
SENSITIVE_SOCIAL_FIELDS = {
    "mother_race_6_code",
    "mother_hispanic_origin_recode",
    "mother_education_code",
    "father_education_code",
    "marital_status_code",
    "payment_source_recode",
    "wic_received",
    "father_age",
    "birth_year",
}
REQUIRED_SUMMARY_FILES = [
    "optimization_readme.md",
    "optimization_decision_summary.md",
    "target_definitions.json",
    "model_registry.csv",
    "target_component_model_comparison.csv",
    "threshold_strategy_comparison.csv",
    "subgroup_performance_v2.csv",
    "subgroup_false_negative_analysis_v2.csv",
    "subgroup_threshold_diagnostics_v2.csv",
    "mitigation_experiment_summary.csv",
    "multiple_gestation_dominance_report.csv",
    "recommended_profile_architecture.md",
]
REQUIRED_PACKAGE_FILES = [
    "model.joblib",
    "preprocessor.joblib",
    "calibrator.joblib",
    "combined_pipeline.joblib",
    "feature_config.yaml",
    "thresholds.json",
    "metrics_validation.json",
    "metrics_test.json",
    "leakage_audit.json",
    "fairness_report.csv",
    "feature_missingness.csv",
    "feature_distributions.csv",
    "sample_predictions.csv",
    "score_distribution_report.csv",
    "tier_outcomes.csv",
    "model_card.md",
    "artifact_manifest.json",
]


@dataclass(frozen=True)
class TargetSpec:
    name: str
    description: str
    purpose: str
    series: pd.Series


@dataclass(frozen=True)
class CandidateSpec:
    target_name: str
    model_name: str
    model_family: str
    features: list[str]
    class_weight: str | None = "balanced"
    c_value: float = 1.0
    sample_weight_multiplier: float | None = None
    calibration_method: str = "sigmoid"
    notes: str = ""


@dataclass
class CandidateResult:
    spec: CandidateSpec
    preprocessor: ColumnTransformer
    model: Any
    calibrator: CalibratedClassifierCV
    thresholds: dict[str, Any]
    validation_metrics: dict[str, Any]
    test_metrics: dict[str, Any]
    validation_probabilities: np.ndarray
    test_probabilities: np.ndarray
    train_df: pd.DataFrame
    valid_df: pd.DataFrame
    test_df: pd.DataFrame
    y_train: pd.Series
    y_valid: pd.Series
    y_test: pd.Series


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--data-path", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-rows", type=int)
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def current_git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short=7", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return None


def slug(value: str) -> str:
    return value.lower().replace(" ", "_").replace("/", "_").replace(".", "_")


def build_target_components(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "gestational_hypertension": (to_binary(df["gestational_hypertension"]) == 1).astype(int),
            "eclampsia": (to_binary(df["eclampsia"]) == 1).astype(int),
            "gestational_diabetes": (to_binary(df["gestational_diabetes"]) == 1).astype(int),
            "severe_maternal_morbidity_proxy": (to_binary(df["severe_maternal_morbidity_proxy"]) == 1).astype(int),
            "preterm_birth": (numeric(df["obstetric_estimate_gestation_weeks"]) < 37).astype(int),
            "low_birth_weight": (numeric(df["birth_weight_grams"]) < 2500).astype(int),
        },
        index=df.index,
    )


def build_targets(df: pd.DataFrame) -> dict[str, TargetSpec]:
    components = build_target_components(df)
    severe = components["severe_maternal_morbidity_proxy"].astype(int)
    target_map = {
        "T0_current_composite": TargetSpec(
            "T0_current_composite",
            "Current prenatal_cvd_followup_proxy_v1 composite target.",
            "Continuity baseline for the accepted A2 package.",
            (components.sum(axis=1) > 0).astype(int),
        ),
        "T1_maternal_cv_metabolic_proxy": TargetSpec(
            "T1_maternal_cv_metabolic_proxy",
            "Gestational hypertension, eclampsia, gestational diabetes, or severe maternal morbidity proxy.",
            "Closer maternal cardiometabolic/pregnancy morbidity follow-up signal without preterm or low-birth-weight components.",
            (
                (components["gestational_hypertension"] == 1)
                | (components["eclampsia"] == 1)
                | (components["gestational_diabetes"] == 1)
                | (components["severe_maternal_morbidity_proxy"] == 1)
            ).astype(int),
        ),
        "T2_hypertensive_proxy": TargetSpec(
            "T2_hypertensive_proxy",
            "Gestational hypertension or eclampsia.",
            "Specific hypertension-focused pregnancy risk signal.",
            ((components["gestational_hypertension"] == 1) | (components["eclampsia"] == 1)).astype(int),
        ),
        "T3_diabetes_proxy": TargetSpec(
            "T3_diabetes_proxy",
            "Gestational diabetes.",
            "Specific metabolic pregnancy risk signal.",
            (components["gestational_diabetes"] == 1).astype(int),
        ),
        "T4_severe_maternal_morbidity_proxy_only": TargetSpec(
            "T4_severe_maternal_morbidity_proxy_only",
            "Severe maternal morbidity proxy only.",
            "High-severity maternal outcome feasibility check.",
            severe,
        ),
        "T5_obstetric_neonatal_proxy": TargetSpec(
            "T5_obstetric_neonatal_proxy",
            "Preterm birth or low birth weight.",
            "Separated obstetric/neonatal adverse-outcome signal.",
            ((components["preterm_birth"] == 1) | (components["low_birth_weight"] == 1)).astype(int),
        ),
    }
    return target_map


def add_interaction_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    age = numeric(df["mother_age"])
    bmi = numeric(df["mother_bmi"])
    bmi_low = bmi < 18.5
    bmi_normal = (bmi >= 18.5) & (bmi <= 24.9)
    bmi_high = bmi >= 30
    young = age < 25
    age_35_plus = age >= 35
    multiple = df["multiple_gestation_known_or_suspected"].fillna(0).astype(float) == 1
    df["age_x_bmi"] = age * bmi
    df["young_and_normal_bmi"] = (young & bmi_normal).astype(int)
    df["young_and_low_bmi"] = (young & bmi_low).astype(int)
    df["bmi_missing_flag"] = bmi.isna().astype(int)
    df["hypertension_or_diabetes"] = (
        (df["prepregnancy_hypertension"].fillna(0).astype(float) == 1)
        | (df["prepregnancy_diabetes"].fillna(0).astype(float) == 1)
    ).astype(int)
    df["prior_adverse_or_smoking"] = (
        (df["prior_adverse_pregnancy_history"].fillna(0).astype(float) == 1)
        | (df["smoking_before_or_during_pregnancy"].fillna(0).astype(float) == 1)
    ).astype(int)
    df["age_under25_x_bmi_normal"] = (young & bmi_normal).astype(int)
    df["age_under25_x_bmi_low"] = (young & bmi_low).astype(int)
    df["multiple_gestation_x_bmi_low"] = (multiple & bmi_low).astype(int)
    df["multiple_gestation_x_bmi_normal"] = (multiple & bmi_normal).astype(int)
    df["multiple_gestation_x_bmi_high"] = (multiple & bmi_high).astype(int)
    df["multiple_gestation_x_age_under25"] = (multiple & young).astype(int)
    df["multiple_gestation_x_age_35_plus"] = (multiple & age_35_plus).astype(int)
    return df


def feature_splits(features: list[str]) -> tuple[list[str], list[str]]:
    numeric_features = [feature for feature in ["mother_age", "mother_bmi", "prior_live_births", "age_x_bmi"] if feature in features]
    binary_features = [feature for feature in features if feature not in numeric_features]
    return numeric_features, binary_features


def build_preprocessor(numeric_features: list[str], binary_features: list[str]) -> ColumnTransformer:
    numeric_pipe = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())])
    binary_pipe = Pipeline([("imputer", SimpleImputer(strategy="most_frequent"))])
    return ColumnTransformer(
        [("numeric", numeric_pipe, numeric_features), ("binary", binary_pipe, binary_features)],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def candidate_specs(targets: dict[str, TargetSpec]) -> list[CandidateSpec]:
    specs: list[CandidateSpec] = [
        CandidateSpec("T0_current_composite", "M0_current_A2_logistic_balanced", "logistic", BASE_FEATURES, "balanced", 1.0, notes="Accepted A2 structure retrained as continuity baseline."),
        CandidateSpec("T0_current_composite", "M1_A2_without_multiple_logistic_balanced", "logistic", NO_MULTIPLE_FEATURES, "balanced", 1.0, notes="A1-style feature set against current composite target."),
        CandidateSpec("T0_current_composite", "M0_current_A2_logistic_unbalanced", "logistic", BASE_FEATURES, None, 1.0, notes="Unbalanced logistic comparison."),
        CandidateSpec("T0_current_composite", "T0_interactions_logistic_balanced", "logistic", BASE_FEATURES + INTERACTION_FEATURES, "balanced", 1.0, notes="Non-sensitive interaction feature mitigation."),
        CandidateSpec("T0_current_composite", "T0_reweighted_1_25_logistic_balanced", "logistic", BASE_FEATURES, "balanced", 1.0, 1.25, notes="Diagnostic moderate sample weighting for under-recalled age/BMI groups."),
        CandidateSpec("T0_current_composite", "T0_reweighted_1_5_logistic_balanced", "logistic", BASE_FEATURES, "balanced", 1.0, 1.5, notes="Diagnostic moderate sample weighting for under-recalled age/BMI groups."),
        CandidateSpec("T0_current_composite", "T0_reweighted_2_0_logistic_balanced", "logistic", BASE_FEATURES, "balanced", 1.0, 2.0, notes="Diagnostic stronger sample weighting for under-recalled age/BMI groups."),
        CandidateSpec("T0_current_composite", "T0_lightgbm_shallow_calibrated", "lightgbm", BASE_FEATURES, "balanced", notes="Shallow calibrated LightGBM comparison."),
        CandidateSpec("T0_current_composite", "T0_hist_gradient_shallow_calibrated", "hist_gradient_boosting", BASE_FEATURES, "balanced", notes="Sklearn shallow additive-tree style comparison."),
    ]
    for c_value in [0.5, 0.2, 0.1, 0.05]:
        specs.append(
            CandidateSpec(
                "T0_current_composite",
                f"M2_A2_with_multiple_regularized_C_{str(c_value).replace('.', '_')}",
                "logistic",
                BASE_FEATURES,
                "balanced",
                c_value,
                notes="Regularization sweep to reduce single-feature dominance.",
            )
        )
    for target_name in ["T1_maternal_cv_metabolic_proxy", "T2_hypertensive_proxy", "T3_diabetes_proxy", "T5_obstetric_neonatal_proxy"]:
        specs.extend(
            [
                CandidateSpec(target_name, f"{target_name}_logistic_balanced", "logistic", BASE_FEATURES, "balanced", 1.0, notes="Target-decomposition logistic baseline."),
                CandidateSpec(target_name, f"{target_name}_logistic_interactions", "logistic", BASE_FEATURES + INTERACTION_FEATURES, "balanced", 1.0, notes="Target-decomposition interaction mitigation."),
            ]
        )
    specs.extend(
        [
            CandidateSpec("T1_maternal_cv_metabolic_proxy", "M4_maternal_only_target_T1_logistic", "logistic", BASE_FEATURES, "balanced", 1.0, notes="Maternal-only target test for multiple-gestation dominance."),
            CandidateSpec("T1_maternal_cv_metabolic_proxy", "T1_lightgbm_shallow_calibrated", "lightgbm", BASE_FEATURES, "balanced", notes="Shallow calibrated LightGBM for maternal target."),
            CandidateSpec("T5_obstetric_neonatal_proxy", "T5_lightgbm_shallow_calibrated", "lightgbm", BASE_FEATURES, "balanced", notes="Shallow calibrated LightGBM for obstetric/neonatal target."),
        ]
    )
    t4 = targets["T4_severe_maternal_morbidity_proxy_only"].series
    if int(t4.sum()) >= MIN_T4_POSITIVES and float(t4.mean()) >= MIN_T4_PREVALENCE:
        specs.append(CandidateSpec("T4_severe_maternal_morbidity_proxy_only", "T4_logistic_feasibility", "logistic", BASE_FEATURES, "balanced", 1.0, notes="Trained because T4 positive count met feasibility floor."))
    return specs


def train_model(spec: CandidateSpec, x_train: np.ndarray, y_train: pd.Series, train_df: pd.DataFrame, config: dict[str, Any]) -> Any:
    sample_weight = None
    if spec.sample_weight_multiplier:
        age = numeric(train_df["mother_age"])
        bmi = numeric(train_df["mother_bmi"])
        under_recalled = (age < 25) | (bmi < 18.5) | ((bmi >= 18.5) & (bmi <= 24.9))
        sample_weight = np.ones(len(train_df), dtype=float)
        sample_weight[under_recalled.to_numpy()] = float(spec.sample_weight_multiplier)

    if spec.model_family == "logistic":
        model = LogisticRegression(
            max_iter=1000,
            class_weight=spec.class_weight,
            C=float(spec.c_value),
            solver="saga",
            random_state=42,
        )
        model.fit(x_train, y_train, sample_weight=sample_weight)
        return model
    if spec.model_family == "lightgbm":
        from lightgbm import LGBMClassifier

        params = dict(config["lightgbm"])
        params.update({"n_estimators": min(int(params.get("n_estimators", 300)), 300), "max_depth": 3, "num_leaves": 15})
        model = LGBMClassifier(**params)
        model.fit(x_train, y_train, sample_weight=sample_weight)
        return model
    if spec.model_family == "hist_gradient_boosting":
        model = HistGradientBoostingClassifier(max_iter=160, max_leaf_nodes=15, l2_regularization=0.1, random_state=42)
        model.fit(x_train, y_train, sample_weight=sample_weight)
        return model
    raise ValueError(f"Unsupported model family: {spec.model_family}")


def threshold_for_recall(y_true: pd.Series, y_prob: np.ndarray, target_recall: float = TARGET_RECALL) -> float:
    y_array = np.asarray(y_true)
    prob_array = np.asarray(y_prob)
    positive_probs = prob_array[y_array == 1]
    if len(positive_probs) == 0:
        return 0.99
    threshold = float(np.quantile(positive_probs, max(0.0, 1.0 - target_recall), method="lower"))
    return min(max(threshold, 0.0), 0.99)


def select_thresholds(y_valid: pd.Series, valid_prob: np.ndarray) -> dict[str, Any]:
    low = threshold_for_recall(y_valid, valid_prob, TARGET_RECALL)
    high = float(np.quantile(valid_prob, 0.85))
    if high <= low:
        high = min(0.99, low + 0.05)
    return {
        "low": float(low),
        "high": float(high),
        "target_recall": TARGET_RECALL,
        "threshold_selection": "validation_only",
        "high_threshold_strategy": "top_15_pct_validation",
    }


def tiers(y_prob: np.ndarray, thresholds: dict[str, Any]) -> np.ndarray:
    probs = np.asarray(y_prob)
    return np.where(probs < thresholds["low"], "low", np.where(probs < thresholds["high"], "medium", "high"))


def classification_metrics(y_true: pd.Series, y_prob: np.ndarray, thresholds: dict[str, Any]) -> dict[str, Any]:
    y_array = np.asarray(y_true)
    y_pred = (y_prob >= thresholds["low"]).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_array, y_pred, labels=[0, 1]).ravel()
    tier_values = pd.Series(tiers(y_prob, thresholds))
    recall = recall_score(y_array, y_pred, zero_division=0)
    return {
        "sample_size": int(len(y_array)),
        "target_prevalence": float(np.mean(y_array)),
        "positive_recall": float(recall),
        "false_negative_rate": float(1.0 - recall),
        "precision": float(precision_score(y_array, y_pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y_array, y_prob)),
        "roc_auc": float(roc_auc_score(y_array, y_prob)) if len(np.unique(y_array)) > 1 else math.nan,
        "brier_score": float(brier_score_loss(y_array, y_prob)),
        "expected_calibration_error": expected_calibration_error(pd.Series(y_array), y_prob),
        "threshold": float(thresholds["low"]),
        "high_threshold": float(thresholds["high"]),
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
        "risk_low_count": int((tier_values == "low").sum()),
        "risk_medium_count": int((tier_values == "medium").sum()),
        "risk_high_count": int((tier_values == "high").sum()),
        "risk_low_pct": float((tier_values == "low").mean()),
        "risk_medium_pct": float((tier_values == "medium").mean()),
        "risk_high_pct": float((tier_values == "high").mean()),
    }


def train_candidate(config: dict[str, Any], df: pd.DataFrame, spec: CandidateSpec, target: TargetSpec) -> CandidateResult:
    features = list(spec.features)
    validate_no_leakage(config, features)
    if set(features) & SENSITIVE_SOCIAL_FIELDS:
        raise ValueError(f"Sensitive/social feature in candidate {spec.model_name}: {set(features) & SENSITIVE_SOCIAL_FIELDS}")
    train_df, valid_df, test_df, y_train, y_valid, y_test = split_data(df, target.series, config)
    numeric_features, binary_features = feature_splits(features)
    preprocessor = build_preprocessor(numeric_features, binary_features)
    x_train = preprocessor.fit_transform(train_df[features])
    x_valid = preprocessor.transform(valid_df[features])
    x_test = preprocessor.transform(test_df[features])
    model = train_model(spec, x_train, y_train, train_df, config)
    calibrator = CalibratedClassifierCV(FrozenEstimator(model), method=spec.calibration_method)
    calibrator.fit(x_valid, y_valid)
    valid_prob = calibrator.predict_proba(x_valid)[:, 1]
    test_prob = calibrator.predict_proba(x_test)[:, 1]
    thresholds = select_thresholds(y_valid, valid_prob)
    return CandidateResult(
        spec=spec,
        preprocessor=preprocessor,
        model=model,
        calibrator=calibrator,
        thresholds=thresholds,
        validation_metrics=classification_metrics(y_valid, valid_prob, thresholds),
        test_metrics=classification_metrics(y_test, test_prob, thresholds),
        validation_probabilities=valid_prob,
        test_probabilities=test_prob,
        train_df=train_df,
        valid_df=valid_df,
        test_df=test_df,
        y_train=y_train,
        y_valid=y_valid,
        y_test=y_test,
    )


def feature_effects(result: CandidateResult) -> pd.DataFrame:
    features = list(result.preprocessor.get_feature_names_out())
    if hasattr(result.model, "coef_"):
        coef = result.model.coef_[0]
        return (
            pd.DataFrame(
                {
                    "feature": features,
                    "standardized_coefficient": coef,
                    "odds_ratio": np.exp(coef),
                    "absolute_effect": np.abs(coef),
                    "direction": np.where(coef >= 0, "positive", "negative"),
                }
            )
            .sort_values("absolute_effect", ascending=False)
            .assign(abs_rank=lambda frame: np.arange(1, len(frame) + 1))
        )
    if hasattr(result.model, "feature_importances_"):
        importance = result.model.feature_importances_
    else:
        importance = np.zeros(len(features))
    return (
        pd.DataFrame(
            {
                "feature": features,
                "standardized_coefficient": np.nan,
                "odds_ratio": np.nan,
                "absolute_effect": importance,
                "direction": "importance",
            }
        )
        .sort_values("absolute_effect", ascending=False)
        .assign(abs_rank=lambda frame: np.arange(1, len(frame) + 1))
    )


def score_distribution_report(y_true: pd.Series, y_prob: np.ndarray) -> pd.DataFrame:
    frame = pd.DataFrame({"y": np.asarray(y_true), "probability": y_prob})
    frame["score_bin"] = pd.cut(frame["probability"], bins=np.linspace(0, 1, 11), include_lowest=True)
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
    return report[["score_bin", "sample_size", "mean_predicted_risk", "observed_target_rate", "positives", "negatives"]]


def tier_outcomes(result: CandidateResult) -> pd.DataFrame:
    y = np.asarray(result.y_test)
    tier_values = tiers(result.test_probabilities, result.thresholds)
    positive_total = max(int(y.sum()), 1)
    rows = []
    for tier in ["low", "medium", "high"]:
        mask = tier_values == tier
        positives = int(y[mask].sum())
        rows.append(
            {
                "target_name": result.spec.target_name,
                "model_name": result.spec.model_name,
                "tier": tier,
                "count": int(mask.sum()),
                "pct": float(mask.mean()),
                "observed_target_prevalence": float(y[mask].mean()) if mask.any() else 0.0,
                "positive_cases_captured": positives,
                "positive_cases_captured_pct": float(positives / positive_total),
            }
        )
    return pd.DataFrame(rows)


def sample_predictions(result: CandidateResult) -> pd.DataFrame:
    rows = result.test_df[result.spec.features].head(20).copy()
    probs = result.test_probabilities[: len(rows)]
    rows["true_target"] = np.asarray(result.y_test.head(len(rows)))
    rows["proxy_probability"] = [f"{prob:.5f}" for prob in probs]
    rows["risk_tier"] = tiers(probs, result.thresholds)
    rows["risk_tier_note"] = "Risk tier is based on the unrounded model score."
    rows["top_3_contributing_factors"] = [json.dumps(contributing_factors(row) or [NO_DOMINANT_FACTOR]) for _, row in rows.iterrows()]
    bad = rows[rows["risk_tier"].isin(["medium", "high"]) & rows["top_3_contributing_factors"].fillna("").eq("[]")]
    if not bad.empty:
        raise AssertionError(f"{result.spec.model_name} has empty medium/high explanations")
    return rows


def group_columns(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = frame.copy()
    grouped["age_band"] = pd.cut(numeric(grouped["mother_age"]), [0, 24, 29, 34, 39, 120], labels=["<25", "25-29", "30-34", "35-39", "40+"], include_lowest=True).astype("string")
    grouped["bmi_band"] = pd.cut(numeric(grouped["mother_bmi"]), [0, 18.5, 24.9, 29.9, 34.9, 39.9, 120], labels=["<18.5", "18.5-24.9", "25-29.9", "30-34.9", "35-39.9", "40+"], include_lowest=True).astype("string")
    return grouped


def subgroup_performance_rows(result: CandidateResult) -> list[dict[str, Any]]:
    frame = group_columns(result.test_df.copy())
    frame["y"] = np.asarray(result.y_test)
    frame["prob"] = result.test_probabilities
    frame["pred"] = (result.test_probabilities >= result.thresholds["low"]).astype(int)
    frame["tier"] = tiers(result.test_probabilities, result.thresholds)
    frame["feature_missingness_rate"] = result.test_df[result.spec.features].isna().mean(axis=1).to_numpy()
    rows = []
    for column in ["age_band", "bmi_band", "mother_race_6_code", "mother_hispanic_origin_recode", "payment_source_recode", "wic_received"]:
        for value, group in frame.groupby(column, observed=False, dropna=False):
            if len(group) < 20:
                continue
            tn, fp, fn, tp = confusion_matrix(group["y"], group["pred"], labels=[0, 1]).ravel()
            high = group[group["tier"] == "high"]
            low = group[group["tier"] == "low"]
            slope = math.nan
            intercept = math.nan
            if group["y"].nunique() > 1 and len(group) >= 50:
                clipped = np.clip(group["prob"].to_numpy(), 1e-6, 1 - 1e-6)
                logits = np.log(clipped / (1 - clipped)).reshape(-1, 1)
                cal = LogisticRegression(solver="lbfgs")
                cal.fit(logits, group["y"])
                slope = float(cal.coef_[0][0])
                intercept = float(cal.intercept_[0])
            rows.append(
                {
                    "target_name": result.spec.target_name,
                    "model_name": result.spec.model_name,
                    "subgroup_column": column,
                    "subgroup_value": str(value),
                    "sample_size": int(len(group)),
                    "target_prevalence": float(group["y"].mean()),
                    "mean_predicted_probability": float(group["prob"].mean()),
                    "recall": float(recall_score(group["y"], group["pred"], zero_division=0)),
                    "false_negative_rate": float(fn / (fn + tp)) if (fn + tp) else 0.0,
                    "precision": float(precision_score(group["y"], group["pred"], zero_division=0)),
                    "false_positive_rate": float(fp / (fp + tn)) if (fp + tn) else 0.0,
                    "brier": float(brier_score_loss(group["y"], group["prob"])),
                    "calibration_intercept": intercept,
                    "calibration_slope": slope,
                    "ece": expected_calibration_error(group["y"], group["prob"].to_numpy()),
                    "missingness_rate": float(group["feature_missingness_rate"].mean()),
                    "low_pct": float((group["tier"] == "low").mean()),
                    "medium_pct": float((group["tier"] == "medium").mean()),
                    "high_pct": float((group["tier"] == "high").mean()),
                    "high_tier_observed_rate": float(high["y"].mean()) if not high.empty else 0.0,
                    "low_tier_observed_rate": float(low["y"].mean()) if not low.empty else 0.0,
                }
            )
    return rows


def threshold_strategy_rows(result: CandidateResult) -> list[dict[str, Any]]:
    strategies: list[tuple[str, float, float, str]] = [
        ("current_recall_first", result.thresholds["low"], result.thresholds["high"], "Validation recall >= 0.85 plus top 15 pct high tier."),
    ]
    low = result.thresholds["low"]
    for capacity in [0.05, 0.10, 0.15, 0.20]:
        high = float(np.quantile(result.validation_probabilities, 1.0 - capacity))
        strategies.append((f"fixed_high_top_{int(capacity * 100)}pct", low, max(high, low + 1e-6), "High threshold selected on validation capacity."))
    for precision_target in [0.40, 0.45, 0.50]:
        candidates = []
        for threshold in np.linspace(0.01, 0.99, 99):
            pred = (result.validation_probabilities >= threshold).astype(int)
            precision = precision_score(result.y_valid, pred, zero_division=0)
            if precision >= precision_target and pred.sum() > 0:
                candidates.append((float(threshold), int(pred.sum()), precision))
        if candidates:
            high = min(candidates, key=lambda item: item[0])[0]
            strategies.append((f"precision_high_ge_{precision_target:.2f}", low, max(high, low + 1e-6), "High threshold selected on validation precision floor."))
        else:
            strategies.append((f"precision_high_ge_{precision_target:.2f}", low, 1.0, "Precision floor not achievable on validation."))
    baseline = float(np.mean(result.y_valid))
    safety_candidates = []
    for threshold in np.linspace(0.01, 0.99, 99):
        low_mask = result.validation_probabilities < threshold
        if low_mask.sum() < 100:
            continue
        low_rate = float(np.asarray(result.y_valid)[low_mask].mean())
        recall = recall_score(result.y_valid, (result.validation_probabilities >= threshold).astype(int), zero_division=0)
        if low_rate < baseline and recall >= 0.80:
            safety_candidates.append((float(threshold), int(low_mask.sum()), low_rate, recall))
    if safety_candidates:
        safety_low = max(safety_candidates, key=lambda item: (item[1], -item[2]))[0]
        strategies.append(("low_tier_safety", safety_low, max(result.thresholds["high"], safety_low + 1e-6), "Low threshold selected on validation for below-baseline low-tier observed rate."))

    rows = []
    y = np.asarray(result.y_test)
    positives = max(int(y.sum()), 1)
    for name, low_threshold, high_threshold, notes in strategies:
        threshold_payload = {"low": low_threshold, "high": high_threshold}
        tier_values = tiers(result.test_probabilities, threshold_payload)
        low_mask = tier_values == "low"
        med_mask = tier_values == "medium"
        high_mask = tier_values == "high"
        medium_high = ~low_mask
        rows.append(
            {
                "target_name": result.spec.target_name,
                "model_name": result.spec.model_name,
                "threshold_strategy": name,
                "low_threshold": low_threshold,
                "high_threshold": high_threshold,
                "low_count": int(low_mask.sum()),
                "medium_count": int(med_mask.sum()),
                "high_count": int(high_mask.sum()),
                "low_pct": float(low_mask.mean()),
                "medium_pct": float(med_mask.mean()),
                "high_pct": float(high_mask.mean()),
                "low_observed_rate": float(y[low_mask].mean()) if low_mask.any() else 0.0,
                "medium_observed_rate": float(y[med_mask].mean()) if med_mask.any() else 0.0,
                "high_observed_rate": float(y[high_mask].mean()) if high_mask.any() else 0.0,
                "positives_captured_high_pct": float(y[high_mask].sum() / positives),
                "positives_captured_medium_high_pct": float(y[medium_high].sum() / positives),
                "precision_high": float(y[high_mask].mean()) if high_mask.any() else 0.0,
                "precision_medium_high": float(y[medium_high].mean()) if medium_high.any() else 0.0,
                "recall_medium_high": float(y[medium_high].sum() / positives),
                "false_negative_rate_low": float(y[low_mask].sum() / positives),
                "notes": notes,
            }
        )
    return rows


def subgroup_threshold_rows(result: CandidateResult) -> list[dict[str, Any]]:
    frame = group_columns(result.valid_df.copy())
    frame["y"] = np.asarray(result.y_valid)
    frame["prob"] = result.validation_probabilities
    rows = []
    for column in ["age_band", "bmi_band", "mother_race_6_code", "mother_hispanic_origin_recode", "payment_source_recode", "wic_received"]:
        for value, group in frame.groupby(column, observed=False, dropna=False):
            if len(group) < 20 or group["y"].sum() == 0:
                continue
            global_recall = recall_score(group["y"], (group["prob"] >= result.thresholds["low"]).astype(int), zero_division=0)
            subgroup_threshold = threshold_for_recall(group["y"], group["prob"].to_numpy(), TARGET_RECALL)
            rows.append(
                {
                    "target_name": result.spec.target_name,
                    "model_name": result.spec.model_name,
                    "subgroup_column": column,
                    "subgroup_value": str(value),
                    "sample_size": int(len(group)),
                    "target_prevalence": float(group["y"].mean()),
                    "global_threshold": result.thresholds["low"],
                    "global_threshold_recall": float(global_recall),
                    "threshold_required_for_recall_0_85": float(subgroup_threshold),
                    "diagnostic_only": True,
                }
            )
    return rows


def false_negative_rows(result: CandidateResult, components: pd.DataFrame) -> list[dict[str, Any]]:
    test_components = components.loc[result.test_df.index]
    frame = group_columns(result.test_df.copy())
    frame["y"] = np.asarray(result.y_test)
    frame["pred"] = (result.test_probabilities >= result.thresholds["low"]).astype(int)
    rows = []
    subgroup_masks = {
        "age_band=<25": frame["age_band"] == "<25",
        "bmi_band=<18.5": frame["bmi_band"] == "<18.5",
        "bmi_band=18.5-24.9": frame["bmi_band"] == "18.5-24.9",
    }
    for subgroup, subgroup_mask in subgroup_masks.items():
        for cohort_name, mask in {
            "false_negative": subgroup_mask & (frame["y"] == 1) & (frame["pred"] == 0),
            "caught_true_positive": subgroup_mask & (frame["y"] == 1) & (frame["pred"] == 1),
        }.items():
            comp = test_components.loc[mask[mask].index]
            row = {
                "target_name": result.spec.target_name,
                "model_name": result.spec.model_name,
                "subgroup": subgroup,
                "cohort": cohort_name,
                "count": int(len(comp)),
            }
            for column in [
                "gestational_hypertension",
                "eclampsia",
                "gestational_diabetes",
                "severe_maternal_morbidity_proxy",
                "preterm_birth",
                "low_birth_weight",
            ]:
                row[f"{column}_rate"] = float(comp[column].mean()) if len(comp) else 0.0
            rows.append(row)
    return rows


def multiple_gestation_row(result: CandidateResult) -> dict[str, Any]:
    effects = feature_effects(result)
    match = effects[effects["feature"] == "multiple_gestation_known_or_suspected"]
    if match.empty:
        return {
            "target_name": result.spec.target_name,
            "model_name": result.spec.model_name,
            "model_family": result.spec.model_family,
            "has_multiple_gestation_feature": False,
            "multiple_gestation_effect": math.nan,
            "multiple_gestation_odds_ratio": math.nan,
            "multiple_gestation_abs_rank": math.nan,
            "pr_auc": result.test_metrics["pr_auc"],
            "roc_auc": result.test_metrics["roc_auc"],
            "brier": result.test_metrics["brier_score"],
            "recall": result.test_metrics["positive_recall"],
            "false_negative_rate": result.test_metrics["false_negative_rate"],
        }
    row = match.iloc[0]
    return {
        "target_name": result.spec.target_name,
        "model_name": result.spec.model_name,
        "model_family": result.spec.model_family,
        "has_multiple_gestation_feature": True,
        "multiple_gestation_effect": float(row["standardized_coefficient"]) if pd.notna(row["standardized_coefficient"]) else float(row["absolute_effect"]),
        "multiple_gestation_odds_ratio": float(row["odds_ratio"]) if pd.notna(row["odds_ratio"]) else math.nan,
        "multiple_gestation_abs_rank": int(row["abs_rank"]),
        "pr_auc": result.test_metrics["pr_auc"],
        "roc_auc": result.test_metrics["roc_auc"],
        "brier": result.test_metrics["brier_score"],
        "recall": result.test_metrics["positive_recall"],
        "false_negative_rate": result.test_metrics["false_negative_rate"],
    }


def export_package(output_dir: Path, config: dict[str, Any], source_path: Path, target: TargetSpec, result: CandidateResult, full_df: pd.DataFrame, full_y: pd.Series) -> Path:
    package_dir = output_dir / slug(result.spec.target_name) / slug(result.spec.model_name)
    package_dir.mkdir(parents=True, exist_ok=True)
    leakage = validate_no_leakage(config, result.spec.features)
    combined = Pipeline([("preprocessor", result.preprocessor), ("calibrator", result.calibrator)])
    joblib.dump(result.model, package_dir / "model.joblib")
    joblib.dump(result.preprocessor, package_dir / "preprocessor.joblib")
    joblib.dump(result.calibrator, package_dir / "calibrator.joblib")
    joblib.dump(combined, package_dir / "combined_pipeline.joblib")
    feature_config = dict(config)
    feature_config.update(
        {
            "model_name": result.spec.model_name,
            "model_version": MODEL_VERSION,
            "target": result.spec.target_name,
            "target_definition": target.description,
            "artifact_dir": package_dir.relative_to(ROOT).as_posix(),
            "features": result.spec.features,
            "numeric_features": feature_splits(result.spec.features)[0],
            "binary_features": feature_splits(result.spec.features)[1],
            "threshold_selection_data": "validation_only",
        }
    )
    (package_dir / "feature_config.yaml").write_text(yaml.safe_dump(feature_config, sort_keys=False))
    write_json(package_dir / "thresholds.json", result.thresholds)
    write_json(package_dir / "metrics_validation.json", {"model_name": result.spec.model_name, "target_name": result.spec.target_name, **result.validation_metrics})
    write_json(package_dir / "metrics_test.json", {"model_name": result.spec.model_name, "target_name": result.spec.target_name, **result.test_metrics})
    write_json(package_dir / "leakage_audit.json", leakage)
    effects = feature_effects(result)
    if result.spec.model_family == "logistic":
        effects.to_csv(package_dir / "feature_coefficients.csv", index=False)
    else:
        effects.to_csv(package_dir / "feature_importance.csv", index=False)
    feature_missingness(full_df, result.spec.features).to_csv(package_dir / "feature_missingness.csv", index=False)
    feature_distributions(full_df, full_y, result.spec.features).to_csv(package_dir / "feature_distributions.csv", index=False)
    pd.DataFrame(subgroup_performance_rows(result)).to_csv(package_dir / "fairness_report.csv", index=False)
    sample_predictions(result).to_csv(package_dir / "sample_predictions.csv", index=False)
    score_distribution_report(result.y_test, result.test_probabilities).to_csv(package_dir / "score_distribution_report.csv", index=False)
    tier_outcomes(result).to_csv(package_dir / "tier_outcomes.csv", index=False)
    (package_dir / "model_card.md").write_text(model_card(target, result))
    manifest = artifact_manifest(package_dir, source_path, target, result)
    write_json(package_dir / "artifact_manifest.json", manifest)
    consistency_check_package(package_dir)
    return package_dir


def model_card(target: TargetSpec, result: CandidateResult) -> str:
    lines = [
        f"# {result.spec.model_name}",
        "",
        f"- Model version: `{MODEL_VERSION}`",
        f"- Target: `{target.name}`",
        f"- Target definition: {target.description}",
        f"- Target purpose: {target.purpose}",
        "",
        "## Proxy Warning",
        "This target is a pregnancy proxy signal. It is not true long-term cardiovascular disease and must not be described as diagnostic CVD probability.",
        "",
        "## Features",
        *[f"- `{feature}`" for feature in result.spec.features],
        "",
        "## Thresholds",
        f"- Low threshold: `{result.thresholds['low']:.6f}`",
        f"- High threshold: `{result.thresholds['high']:.6f}`",
        "- Thresholds were selected using validation data only.",
        "",
        "## Test Metrics",
        f"- Recall: `{result.test_metrics['positive_recall']:.4f}`",
        f"- FNR: `{result.test_metrics['false_negative_rate']:.4f}`",
        f"- Precision: `{result.test_metrics['precision']:.4f}`",
        f"- PR-AUC: `{result.test_metrics['pr_auc']:.4f}`",
        f"- ROC-AUC: `{result.test_metrics['roc_auc']:.4f}`",
        f"- Brier: `{result.test_metrics['brier_score']:.4f}`",
        "",
        "## Tier Interpretation",
        "- Low: no elevated signal from the limited prenatal model; routine education.",
        "- Medium: broad counseling and follow-up planning signal.",
        "- High: prioritized cardiovascular-risk review and postpartum follow-up planning.",
        "",
        "## Subgroup Limitations",
        "Age <25 and low/normal BMI groups require review. Subgroup-specific thresholds are diagnostic only and are not deployed.",
        "",
        "## Not Intended Uses",
        "- Diagnosis",
        "- Patient-facing standalone risk claims",
        "- Care denial",
        "- Insurance decisions",
        "- Medication changes",
        "",
        f"Clinical safety note: {SAFETY_NOTE}",
        "",
    ]
    return "\n".join(lines)


def artifact_manifest(package_dir: Path, source_path: Path, target: TargetSpec, result: CandidateResult) -> dict[str, Any]:
    artifacts = sorted(path for path in package_dir.iterdir() if path.is_file() and path.name != "artifact_manifest.json")
    return {
        "model_name": result.spec.model_name,
        "model_version": MODEL_VERSION,
        "target_name": target.name,
        "artifact_timestamp": datetime.now(UTC).isoformat(),
        "git_commit": current_git_commit(),
        "training_data_path": str(source_path),
        "feature_list": result.spec.features,
        "threshold_file": "thresholds.json",
        "metrics_files": ["metrics_validation.json", "metrics_test.json"],
        "artifact_sha256": {path.name: sha256(path) for path in artifacts},
    }


def consistency_check_package(package_dir: Path) -> None:
    missing = [name for name in REQUIRED_PACKAGE_FILES if not (package_dir / name).exists()]
    has_effect_file = (package_dir / "feature_coefficients.csv").exists() or (package_dir / "feature_importance.csv").exists()
    missing = [name for name in missing if name not in {"feature_coefficients.csv"}]
    if missing or not has_effect_file:
        raise AssertionError(f"{package_dir} missing required artifacts: {missing}")
    config = yaml.safe_load((package_dir / "feature_config.yaml").read_text())
    leakage = json.loads((package_dir / "leakage_audit.json").read_text())
    if not leakage["passed"]:
        raise AssertionError(f"{package_dir} leakage audit failed")
    if set(config["features"]) & SENSITIVE_SOCIAL_FIELDS:
        raise AssertionError(f"{package_dir} includes sensitive/social inputs")
    for metrics_name in ["metrics_validation.json", "metrics_test.json"]:
        metrics = json.loads((package_dir / metrics_name).read_text())
        if metrics["model_name"] != config["model_name"]:
            raise AssertionError(f"{package_dir} stale model name in {metrics_name}")
    sample = pd.read_csv(package_dir / "sample_predictions.csv")
    if not set(config["features"]).issubset(sample.columns):
        raise AssertionError(f"{package_dir} sample predictions missing features")
    bad = sample[sample["risk_tier"].isin(["medium", "high"]) & sample["top_3_contributing_factors"].fillna("").str.strip().isin(["", "[]"])]
    if not bad.empty:
        raise AssertionError(f"{package_dir} empty medium/high explanations")
    score = pd.read_csv(package_dir / "score_distribution_report.csv")
    metrics = json.loads((package_dir / "metrics_test.json").read_text())
    observed = float((score["observed_target_rate"].fillna(0) * score["sample_size"]).sum() / score["sample_size"].sum())
    if abs(observed - metrics["target_prevalence"]) > 1e-9:
        raise AssertionError(f"{package_dir} score distribution prevalence mismatch")
    card = (package_dir / "model_card.md").read_text()
    for phrase in ["Proxy Warning", "Subgroup Limitations", "not true long-term cardiovascular disease", "validation data only"]:
        if phrase not in card:
            raise AssertionError(f"{package_dir} model card missing {phrase}")


def registry_row(result: CandidateResult, package_dir: Path) -> dict[str, Any]:
    return {
        "target_name": result.spec.target_name,
        "model_name": result.spec.model_name,
        "model_family": result.spec.model_family,
        "package_dir": package_dir.relative_to(ROOT).as_posix(),
        "features": "|".join(result.spec.features),
        "feature_count": len(result.spec.features),
        "class_weight": result.spec.class_weight or "none",
        "c_value": result.spec.c_value,
        "sample_weight_multiplier": result.spec.sample_weight_multiplier or 1.0,
        "validation_recall": result.validation_metrics["positive_recall"],
        "test_recall": result.test_metrics["positive_recall"],
        "test_precision": result.test_metrics["precision"],
        "test_pr_auc": result.test_metrics["pr_auc"],
        "test_roc_auc": result.test_metrics["roc_auc"],
        "test_brier": result.test_metrics["brier_score"],
        "test_ece": result.test_metrics["expected_calibration_error"],
        "low_threshold": result.thresholds["low"],
        "high_threshold": result.thresholds["high"],
        "notes": result.spec.notes,
    }


def target_component_row(target: TargetSpec, result: CandidateResult) -> dict[str, Any]:
    multiple = multiple_gestation_row(result)
    return {
        "target_name": target.name,
        "target_description": target.description,
        "model_name": result.spec.model_name,
        "model_family": result.spec.model_family,
        "target_prevalence_test": result.test_metrics["target_prevalence"],
        "validation_recall": result.validation_metrics["positive_recall"],
        "test_recall": result.test_metrics["positive_recall"],
        "test_false_negative_rate": result.test_metrics["false_negative_rate"],
        "test_precision": result.test_metrics["precision"],
        "test_pr_auc": result.test_metrics["pr_auc"],
        "test_roc_auc": result.test_metrics["roc_auc"],
        "test_brier": result.test_metrics["brier_score"],
        "test_ece": result.test_metrics["expected_calibration_error"],
        "multiple_gestation_abs_rank": multiple["multiple_gestation_abs_rank"],
        "multiple_gestation_effect": multiple["multiple_gestation_effect"],
        "multiple_gestation_odds_ratio": multiple["multiple_gestation_odds_ratio"],
    }


def choose_target_representatives(results: list[CandidateResult]) -> dict[str, CandidateResult]:
    reps: dict[str, CandidateResult] = {}
    for target_name in sorted({result.spec.target_name for result in results}):
        target_results = [result for result in results if result.spec.target_name == target_name]
        viable = [result for result in target_results if result.validation_metrics["positive_recall"] >= TARGET_RECALL]
        pool = viable or target_results
        reps[target_name] = sorted(
            pool,
            key=lambda result: (
                result.validation_metrics["positive_recall"],
                -result.validation_metrics["brier_score"],
                -result.validation_metrics["expected_calibration_error"],
                result.validation_metrics["pr_auc"],
            ),
            reverse=True,
        )[0]
    return reps


def mitigation_summary_rows(results: list[CandidateResult], subgroup_frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    weak_filter = subgroup_frame[
        subgroup_frame["subgroup_column"].isin(["age_band", "bmi_band"])
        & subgroup_frame["subgroup_value"].isin(["<25", "<18.5", "18.5-24.9"])
    ]
    for result in results:
        weak = weak_filter[(weak_filter["target_name"] == result.spec.target_name) & (weak_filter["model_name"] == result.spec.model_name)]
        rows.append(
            {
                "target_name": result.spec.target_name,
                "model_name": result.spec.model_name,
                "experiment_type": (
                    "sample_reweighting"
                    if result.spec.sample_weight_multiplier
                    else "interaction_features"
                    if any(feature in result.spec.features for feature in INTERACTION_FEATURES)
                    else "regularization"
                    if result.spec.c_value != 1.0
                    else "target_decomposition"
                ),
                "overall_test_recall": result.test_metrics["positive_recall"],
                "overall_test_brier": result.test_metrics["brier_score"],
                "weak_group_min_recall": float(weak["recall"].min()) if not weak.empty else math.nan,
                "weak_group_mean_recall": float(weak["recall"].mean()) if not weak.empty else math.nan,
                "notes": result.spec.notes,
            }
        )
    return rows


def write_summary_docs(output_dir: Path, targets: dict[str, TargetSpec], reps: dict[str, CandidateResult], registry: pd.DataFrame, threshold_rows: pd.DataFrame, multi: pd.DataFrame) -> None:
    t1 = reps.get("T1_maternal_cv_metabolic_proxy")
    t5 = reps.get("T5_obstetric_neonatal_proxy")
    t0 = reps.get("T0_current_composite")
    recommendation = "Option 4: move from a single composite model to a two-headed risk profile with maternal CV/metabolic and obstetric/neonatal signals."
    if t1 is None or t5 is None:
        recommendation = "Option 5: keep A2 as MVP but mark it as not ready for broader patient-facing deployment."
    lines = [
        "# Prenatal Model A Optimization v2",
        "",
        "This experiment preserves the accepted A1/A2 packages and writes only experimental candidates under this directory.",
        "",
        "## Recommendation",
        recommendation,
        "",
        "## Why",
        "The current composite target is a proxy follow-up signal, not true cardiovascular disease. Multiple gestation is most clinically interpretable when separated into an obstetric/neonatal adverse-outcome signal rather than hidden inside one blended CVD-labeled probability.",
        "",
        "## Representative Models",
    ]
    for name, result in reps.items():
        lines.append(f"- `{name}`: `{result.spec.model_name}` recall `{result.test_metrics['positive_recall']:.4f}`, PR-AUC `{result.test_metrics['pr_auc']:.4f}`, Brier `{result.test_metrics['brier_score']:.4f}`.")
    (output_dir / "optimization_readme.md").write_text("\n".join(lines) + "\n")

    selected_thresholds = threshold_rows[
        threshold_rows["threshold_strategy"].isin(["fixed_high_top_10pct", "low_tier_safety"])
        & threshold_rows["target_name"].isin(["T1_maternal_cv_metabolic_proxy", "T5_obstetric_neonatal_proxy", "T0_current_composite"])
    ]
    decision = [
        "# Optimization Decision Summary",
        "",
        f"Selected recommendation: {recommendation}",
        "",
        "## Selected Architecture",
        "- Use T1 `maternal_cv_metabolic_proxy` and T5 `obstetric_neonatal_proxy` as separate heads for a risk profile.",
        "- Keep T0 current composite as continuity/reference only.",
        "- Do not replace the accepted A2 package yet; this is an experimental package requiring clinical review.",
        "",
        "## Inference Output Shape",
        "Return `maternal_cv_metabolic_signal`, `obstetric_neonatal_signal`, and `current_composite_signal` rather than one fake CVD probability.",
        "",
        "## Threshold Note",
        "High-tier capacity thresholds at 10-15 percent are more operationally useful than broad medium+high binary classification. Final deployment thresholds still need clinical capacity input.",
        "",
        "## Threshold Rows To Review",
        markdown_table(selected_thresholds) if not selected_thresholds.empty else "_No threshold rows._",
        "",
        "## Data Needed Next",
        "- Real longitudinal maternal cardiovascular outcomes.",
        "- Prospective clinical validation data with prenatal timing stamps.",
        "- Explicit care-capacity constraints for high-tier review.",
        "- External validation by site, race/ethnicity, insurance/payment proxy, and age/BMI strata.",
    ]
    (output_dir / "optimization_decision_summary.md").write_text("\n".join(decision) + "\n")

    architecture = [
        "# Recommended Profile Architecture",
        "",
        "## Recommended Strategy",
        recommendation,
        "",
        "## Output Contract",
        "```json",
        json.dumps(
            {
                "model_mode": "prenatal_after_ultrasound",
                "model_name": "prenatal_model_a_optimization_v2_profile",
                "model_version": MODEL_VERSION,
                "overall_followup_priority": "low|medium|high",
                "tier_interpretation": "workflow priority, not diagnosis",
                "maternal_cv_metabolic_signal": {"probability": 0.0, "tier": "low|medium|high", "main_factors": []},
                "obstetric_neonatal_signal": {"probability": 0.0, "tier": "low|medium|high", "main_factors": []},
                "current_composite_signal": {"probability": 0.0, "tier": "low|medium|high", "use": "continuity/reference only"},
                "main_contributing_factors": [],
                "missing_inputs": [],
                "data_quality_warnings": [],
                "safety_note": SAFETY_NOTE,
            },
            indent=2,
        ),
        "```",
        "",
        "## Multiple-Gestation Interpretation",
        "If multiple gestation ranks high for T0/T5 but not T1, interpret it as an obstetric/neonatal adverse-outcome driver, not as standalone maternal cardiovascular disease evidence.",
    ]
    (output_dir / "recommended_profile_architecture.md").write_text("\n".join(architecture) + "\n")


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    rows = frame.copy()
    for column in rows.columns:
        if pd.api.types.is_float_dtype(rows[column]):
            rows[column] = rows[column].map(lambda value: f"{value:.4f}")
        else:
            rows[column] = rows[column].astype(str)
    header = "| " + " | ".join(rows.columns) + " |"
    divider = "| " + " | ".join(["---"] * len(rows.columns)) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows.to_numpy(dtype=str)]
    return "\n".join([header, divider, *body])


def check_output(output_dir: Path) -> None:
    missing = [name for name in REQUIRED_SUMMARY_FILES if not (output_dir / name).exists()]
    if missing:
        raise AssertionError(f"Missing summary files: {missing}")
    for accepted_dir in [ACCEPTED_A1_DIR, ACCEPTED_A2_DIR]:
        if not accepted_dir.exists():
            raise AssertionError(f"Accepted package missing: {accepted_dir}")
    for package_dir in sorted(path for path in output_dir.glob("*/*") if path.is_dir()):
        consistency_check_package(package_dir)


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if args.check_only:
        check_output(output_dir)
        print(f"checked_optimization_dir={output_dir}")
        return

    config = load_config(args.config.resolve())
    df_raw, source_path = load_data(config, args.data_path, args.max_rows)
    df = clean_values(build_prenatal_features(df_raw))
    df = add_interaction_features(df)
    components = build_target_components(df_raw)
    targets = build_targets(df_raw)
    target_defs = {
        name: {
            "description": target.description,
            "purpose": target.purpose,
            "prevalence": float(target.series.mean()),
            "positive_count": int(target.series.sum()),
            "sample_size": int(len(target.series)),
        }
        for name, target in targets.items()
    }

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "target_definitions.json", target_defs)

    specs = candidate_specs(targets)
    results: list[CandidateResult] = []
    package_dirs: dict[str, Path] = {}
    for spec in specs:
        target = targets[spec.target_name]
        result = train_candidate(config, df, spec, target)
        package_dir = export_package(output_dir, config, source_path, target, result, df, target.series)
        results.append(result)
        package_dirs[f"{result.spec.target_name}/{result.spec.model_name}"] = package_dir
        print(
            "MODEL",
            result.spec.target_name,
            result.spec.model_name,
            f"validation_recall={result.validation_metrics['positive_recall']:.4f}",
            f"test_recall={result.test_metrics['positive_recall']:.4f}",
            f"test_pr_auc={result.test_metrics['pr_auc']:.4f}",
        )

    registry_rows = [registry_row(result, package_dirs[f"{result.spec.target_name}/{result.spec.model_name}"]) for result in results]
    registry = pd.DataFrame(registry_rows)
    registry.to_csv(output_dir / "model_registry.csv", index=False)

    reps = choose_target_representatives(results)
    pd.DataFrame([target_component_row(targets[result.spec.target_name], result) for result in results]).to_csv(
        output_dir / "target_component_model_comparison.csv", index=False
    )
    threshold_frame = pd.DataFrame([row for result in results for row in threshold_strategy_rows(result)])
    threshold_frame.to_csv(output_dir / "threshold_strategy_comparison.csv", index=False)
    subgroup_frame = pd.DataFrame([row for result in results for row in subgroup_performance_rows(result)])
    subgroup_frame.to_csv(output_dir / "subgroup_performance_v2.csv", index=False)
    pd.DataFrame([row for result in reps.values() for row in false_negative_rows(result, components)]).to_csv(
        output_dir / "subgroup_false_negative_analysis_v2.csv", index=False
    )
    pd.DataFrame([row for result in results for row in subgroup_threshold_rows(result)]).to_csv(
        output_dir / "subgroup_threshold_diagnostics_v2.csv", index=False
    )
    pd.DataFrame(mitigation_summary_rows(results, subgroup_frame)).to_csv(
        output_dir / "mitigation_experiment_summary.csv", index=False
    )
    multi = pd.DataFrame([multiple_gestation_row(result) for result in results])
    multi.to_csv(output_dir / "multiple_gestation_dominance_report.csv", index=False)
    write_summary_docs(output_dir, targets, reps, registry, threshold_frame, multi)
    check_output(output_dir)

    t1 = reps.get("T1_maternal_cv_metabolic_proxy")
    t5 = reps.get("T5_obstetric_neonatal_proxy")
    t0 = reps.get("T0_current_composite")
    if t0:
        print(f"METRIC t0_test_recall={t0.test_metrics['positive_recall']:.10f}")
    if t1:
        print(f"METRIC t1_test_recall={t1.test_metrics['positive_recall']:.10f}")
    if t5:
        print(f"METRIC t5_test_recall={t5.test_metrics['positive_recall']:.10f}")
    print(f"optimization_dir={output_dir}")


if __name__ == "__main__":
    main()
