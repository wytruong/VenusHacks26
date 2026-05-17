#!/usr/bin/env python3
"""Train the fixed prenatal expanded screening v3.1 timing-safe profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
import warnings
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
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.maternal.train_prenatal_cvd_model_a import expected_calibration_error, numeric, to_binary

warnings.filterwarnings("ignore", message="X does not have valid feature names.*", category=UserWarning)

DEFAULT_CONFIG_PATH = ROOT / "configs/maternal/prenatal_model_a_v1.yaml"
DEFAULT_OUTPUT_DIR = ROOT / "models/cdc-natality/prenatal_expanded_screening_v3_1_timing_safe"
MODEL_NAME = "prenatal_expanded_screening_v3_1_timing_safe"
MODEL_VERSION = "2026-05-expanded-v3.1-timing-safe"
SAFETY_NOTE = "This is a risk-prioritization aid, not a diagnosis."
TARGET_RECALL = 0.85
CARE_PLANNING_ONLY_FIELDS = [
    "prenatal_visits",
    "month_prenatal_care_began",
    "cigarettes_trimester_3",
]

HEADS = {
    "maternal_cv_metabolic_signal": "T1_maternal_cv_metabolic_proxy",
    "obstetric_neonatal_signal": "T5_obstetric_neonatal_proxy",
    "current_composite_signal": "T0_current_composite_reference",
}

LIGHTGBM_CONFIG = {
    "objective": "binary",
    "n_estimators": 500,
    "learning_rate": 0.03,
    "num_leaves": 15,
    "max_depth": 3,
    "min_child_samples": 100,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "class_weight": "balanced",
    "random_state": 42,
    "verbosity": -1,
}

CURRENT_A2_FEATURES = [
    "mother_age",
    "mother_bmi",
    "prepregnancy_hypertension",
    "prepregnancy_diabetes",
    "prior_adverse_pregnancy_history",
    "prior_live_births",
    "smoking_before_or_during_pregnancy",
    "multiple_gestation_known_or_suspected",
]
EXPANDED_SCREENING_FEATURES = [
    "mother_height_inches",
    "prepregnancy_weight_lb",
    "prior_dead_births",
    "prior_terminations",
    "previous_preterm_birth",
    "previous_cesarean",
    "previous_cesarean_count",
    "interval_last_live_birth_recode",
    "interval_last_pregnancy_recode",
    "cigarettes_before_pregnancy",
    "cigarettes_trimester_1",
    "cigarettes_trimester_2",
    "risk_factor_infertility_treatment",
]
DERIVED_FEATURES = [
    "bmi_from_height_weight",
    "bmi_missing_flag",
    "age_under_25",
    "bmi_under_18_5",
    "bmi_18_5_to_24_9",
    "low_or_normal_bmi",
    "young_low_or_normal_bmi",
    "age_x_bmi",
    "hypertension_or_diabetes",
    "prior_preterm_or_dead_birth",
    "prior_cesarean_history",
    "smoking_any",
    "smoking_intensity_before_pregnancy",
    "smoking_intensity_latest_available_trimester",
]
FEATURES = list(dict.fromkeys(CURRENT_A2_FEATURES + EXPANDED_SCREENING_FEATURES + DERIVED_FEATURES))
NUMERIC_FEATURES = [
    "mother_age",
    "mother_bmi",
    "prior_live_births",
    "mother_height_inches",
    "prepregnancy_weight_lb",
    "prior_dead_births",
    "prior_terminations",
    "previous_cesarean_count",
    "interval_last_live_birth_recode",
    "interval_last_pregnancy_recode",
    "cigarettes_before_pregnancy",
    "cigarettes_trimester_1",
    "cigarettes_trimester_2",
    "bmi_from_height_weight",
    "age_x_bmi",
    "smoking_intensity_before_pregnancy",
    "smoking_intensity_latest_available_trimester",
]
BINARY_FEATURES = [feature for feature in FEATURES if feature not in NUMERIC_FEATURES]

FORBIDDEN_INPUTS = {
    "pregnancy_cvd_risk_proxy",
    "prenatal_cvd_followup_proxy_v1",
    "T0_current_composite_reference",
    "T1_maternal_cv_metabolic_proxy",
    "T5_obstetric_neonatal_proxy",
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
    "birth_month",
    "delivery_weight_lb",
    "weight_gain_lb",
    "weight_gain_recode",
    "presentation_at_delivery_code",
    "delivery_route_code",
    "trial_of_labor_attempted",
}
SENSITIVE_SOCIAL_INPUTS = {
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
AUDIT_COLUMNS = [
    "mother_race_6_code",
    "mother_hispanic_origin_recode",
    "mother_education_code",
    "marital_status_code",
    "payment_source_recode",
    "wic_received",
    "mother_age",
]
RAW_COLUMNS = list(
    dict.fromkeys(
        FEATURES
        + CARE_PLANNING_ONLY_FIELDS
        + AUDIT_COLUMNS
        + [
            "plurality",
            "gestational_hypertension",
            "eclampsia",
            "gestational_diabetes",
            "severe_maternal_morbidity_proxy",
            "maternal_transfusion",
            "ruptured_uterus",
            "unplanned_hysterectomy",
            "maternal_icu",
            "obstetric_estimate_gestation_weeks",
            "birth_weight_grams",
        ]
    )
)
REQUIRED_ARTIFACTS = [
    "v3_1_decision_summary.md",
    "questionnaire_mapping.md",
    "expanded_feature_config.yaml",
    "target_definitions.json",
    "model_registry.csv",
    "metrics_validation.json",
    "metrics_test.json",
    "threshold_strategy_summary.csv",
    "subgroup_performance_v3_1.csv",
    "feature_importance.csv",
    "feature_missingness.csv",
    "feature_distributions.csv",
    "fairness_report.csv",
    "sample_predictions.csv",
    "score_distribution_report.csv",
    "tier_outcomes.csv",
    "leakage_audit.json",
    "model_card.md",
    "artifact_manifest.json",
    "combined_pipeline.joblib",
    "preprocessor.joblib",
    "calibrator.joblib",
    "model.joblib",
]


@dataclass
class HeadResult:
    head_name: str
    target_name: str
    train_df: pd.DataFrame
    valid_df: pd.DataFrame
    test_df: pd.DataFrame
    y_train: pd.Series
    y_valid: pd.Series
    y_test: pd.Series
    preprocessor: ColumnTransformer
    model: Any
    calibrator: CalibratedClassifierCV
    valid_prob: np.ndarray
    test_prob: np.ndarray
    thresholds: dict[str, Any]
    validation_metrics: dict[str, Any]
    test_metrics: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--data-path", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-rows", type=int)
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return "data/cdc-natality/derived/natality_2024_structured.csv"


def current_git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short=7", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return None


def load_config(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return yaml.safe_load(fh)


def resolve_data_path(config: dict[str, Any], data_path: Path | None) -> Path:
    if data_path:
        return data_path
    configured = ROOT / config["data_path"]
    if configured.exists():
        return configured
    fallback = Path("/Users/benj/Documents/Coding/cardiac_mvp/data/cdc-natality/derived/natality_2024_structured.csv")
    if fallback.exists():
        return fallback
    return ROOT / config["fallback_data_path"]


def load_source_data(config: dict[str, Any], data_path: Path | None, max_rows: int | None) -> tuple[pd.DataFrame, Path]:
    source = resolve_data_path(config, data_path)
    if not source.exists():
        raise FileNotFoundError(source)
    columns = set(RAW_COLUMNS)
    df = pd.read_csv(source, usecols=lambda column: column in columns, nrows=max_rows, low_memory=False)
    derived_or_recomputed = set(DERIVED_FEATURES) | {
        "prior_adverse_pregnancy_history",
        "smoking_before_or_during_pregnancy",
        "multiple_gestation_known_or_suspected",
    }
    missing = sorted((set(RAW_COLUMNS) - derived_or_recomputed) - set(df.columns))
    if missing:
        raise ValueError(f"Missing raw columns: {missing}")
    return df, source


def clean_and_derive_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for column in [
        "mother_age",
        "mother_bmi",
        "mother_height_inches",
        "prepregnancy_weight_lb",
        "prior_live_births",
        "prior_dead_births",
        "prior_terminations",
        "previous_cesarean_count",
        "interval_last_live_birth_recode",
        "interval_last_pregnancy_recode",
        "month_prenatal_care_began",
        "prenatal_visits",
        "cigarettes_before_pregnancy",
        "cigarettes_trimester_1",
        "cigarettes_trimester_2",
        "cigarettes_trimester_3",
        "obstetric_estimate_gestation_weeks",
        "birth_weight_grams",
    ]:
        if column in df:
            df[column] = numeric(df[column])
    df.loc[(df["mother_age"] < 10) | (df["mother_age"] > 60), "mother_age"] = np.nan
    df.loc[(df["mother_bmi"] < 12) | (df["mother_bmi"] > 80), "mother_bmi"] = np.nan
    df.loc[(df["mother_height_inches"] < 48) | (df["mother_height_inches"] > 78), "mother_height_inches"] = np.nan
    df.loc[(df["prepregnancy_weight_lb"] < 70) | (df["prepregnancy_weight_lb"] > 500), "prepregnancy_weight_lb"] = np.nan
    df["bmi_from_height_weight"] = 703 * df["prepregnancy_weight_lb"] / (df["mother_height_inches"] ** 2)
    df.loc[(df["bmi_from_height_weight"] < 12) | (df["bmi_from_height_weight"] > 80), "bmi_from_height_weight"] = np.nan
    df["bmi_missing_flag"] = df["mother_bmi"].isna().astype(int)
    df["mother_bmi"] = df["mother_bmi"].where(df["mother_bmi"].notna(), df["bmi_from_height_weight"])
    df["age_under_25"] = (df["mother_age"] < 25).astype(int)
    df["bmi_under_18_5"] = (df["mother_bmi"] < 18.5).astype(int)
    df["bmi_18_5_to_24_9"] = ((df["mother_bmi"] >= 18.5) & (df["mother_bmi"] <= 24.9)).astype(int)
    df["low_or_normal_bmi"] = (df["mother_bmi"] < 25).astype(int)
    df["young_low_or_normal_bmi"] = ((df["mother_age"] < 25) & (df["mother_bmi"] < 25)).astype(int)
    df["age_x_bmi"] = df["mother_age"] * df["mother_bmi"]

    for column in [
        "prepregnancy_hypertension",
        "prepregnancy_diabetes",
        "previous_preterm_birth",
        "previous_cesarean",
        "risk_factor_infertility_treatment",
        "gestational_hypertension",
        "eclampsia",
        "gestational_diabetes",
        "severe_maternal_morbidity_proxy",
        "maternal_transfusion",
        "ruptured_uterus",
        "unplanned_hysterectomy",
        "maternal_icu",
    ]:
        if column in df:
            df[column] = to_binary(df[column])

    df["prior_adverse_pregnancy_history"] = (
        (df["previous_preterm_birth"] == 1) | (df["prior_dead_births"] > 0)
    ).astype(int)
    cigarette_columns = ["cigarettes_before_pregnancy", "cigarettes_trimester_1", "cigarettes_trimester_2"]
    df["smoking_before_or_during_pregnancy"] = (df[cigarette_columns].fillna(0) > 0).any(axis=1).astype(int)
    df["smoking_any"] = df["smoking_before_or_during_pregnancy"]
    df["smoking_intensity_before_pregnancy"] = df["cigarettes_before_pregnancy"]
    df["smoking_intensity_latest_available_trimester"] = df[
        ["cigarettes_trimester_2", "cigarettes_trimester_1", "cigarettes_before_pregnancy"]
    ].bfill(axis=1).iloc[:, 0]
    df["multiple_gestation_known_or_suspected"] = (numeric(df["plurality"]) > 1).astype(int)
    df["hypertension_or_diabetes"] = ((df["prepregnancy_hypertension"] == 1) | (df["prepregnancy_diabetes"] == 1)).astype(int)
    df["prior_preterm_or_dead_birth"] = ((df["previous_preterm_birth"] == 1) | (df["prior_dead_births"] > 0)).astype(int)
    df["prior_cesarean_history"] = ((df["previous_cesarean"] == 1) | (df["previous_cesarean_count"] > 0)).astype(int)
    return df


def build_targets(df: pd.DataFrame) -> pd.DataFrame:
    t1 = (
        (df["gestational_hypertension"] == 1)
        | (df["eclampsia"] == 1)
        | (df["gestational_diabetes"] == 1)
        | (df["severe_maternal_morbidity_proxy"] == 1)
    ).astype(int)
    t5 = ((df["obstetric_estimate_gestation_weeks"] < 37) | (df["birth_weight_grams"] < 2500)).astype(int)
    t0 = ((t1 == 1) | (t5 == 1)).astype(int)
    return pd.DataFrame(
        {
            "T1_maternal_cv_metabolic_proxy": t1,
            "T5_obstetric_neonatal_proxy": t5,
            "T0_current_composite_reference": t0,
        },
        index=df.index,
    )


def build_preprocessor() -> ColumnTransformer:
    numeric_pipe = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())])
    binary_pipe = Pipeline([("imputer", SimpleImputer(strategy="most_frequent"))])
    return ColumnTransformer(
        [("numeric", numeric_pipe, NUMERIC_FEATURES), ("binary", binary_pipe, BINARY_FEATURES)],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def t1_sample_weight(train_df: pd.DataFrame, y_train: pd.Series) -> np.ndarray:
    weights = np.ones(len(train_df), dtype=float)
    positive = np.asarray(y_train) == 1
    young_positive = positive & (numeric(train_df["mother_age"]).to_numpy() < 25)
    low_normal_bmi_positive = positive & (numeric(train_df["mother_bmi"]).to_numpy() < 25)
    weights[young_positive | low_normal_bmi_positive] = 2.0
    weights[young_positive & low_normal_bmi_positive] = 3.0
    return weights


def threshold_for_recall(y_true: pd.Series, y_prob: np.ndarray, target_recall: float = TARGET_RECALL) -> float:
    positive_probs = np.asarray(y_prob)[np.asarray(y_true) == 1]
    if len(positive_probs) == 0:
        return 0.99
    return float(np.quantile(positive_probs, max(0, 1 - target_recall), method="lower"))


def tiers(y_prob: np.ndarray, thresholds: dict[str, float]) -> np.ndarray:
    prob = np.asarray(y_prob)
    return np.where(prob < thresholds["low"], "low", np.where(prob < thresholds["high"], "medium", "high"))


def calibration_slope_intercept(y_true: pd.Series, y_prob: np.ndarray) -> tuple[float, float]:
    if len(np.unique(y_true)) < 2:
        return math.nan, math.nan
    clipped = np.clip(y_prob, 1e-6, 1 - 1e-6)
    logits = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    model = LogisticRegression(solver="lbfgs")
    model.fit(logits, y_true)
    return float(model.coef_[0][0]), float(model.intercept_[0])


def metrics(y_true: pd.Series, y_prob: np.ndarray, thresholds: dict[str, float]) -> dict[str, Any]:
    y_array = np.asarray(y_true)
    pred = (y_prob >= thresholds["low"]).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_array, pred, labels=[0, 1]).ravel()
    slope, intercept = calibration_slope_intercept(y_true, y_prob)
    tier_values = tiers(y_prob, thresholds)
    high = tier_values == "high"
    low = tier_values == "low"
    return {
        "sample_size": int(len(y_array)),
        "target_prevalence": float(y_array.mean()),
        "recall": float(recall_score(y_array, pred, zero_division=0)),
        "false_negative_rate": float(1 - recall_score(y_array, pred, zero_division=0)),
        "precision": float(precision_score(y_array, pred, zero_division=0)),
        "f1": float(f1_score(y_array, pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_array, y_prob)),
        "pr_auc": float(average_precision_score(y_array, y_prob)),
        "brier_score": float(brier_score_loss(y_array, y_prob)),
        "expected_calibration_error": expected_calibration_error(pd.Series(y_array), y_prob),
        "calibration_slope": slope,
        "calibration_intercept": intercept,
        "low_count": int((tier_values == "low").sum()),
        "medium_count": int((tier_values == "medium").sum()),
        "high_count": int(high.sum()),
        "low_pct": float((tier_values == "low").mean()),
        "medium_pct": float((tier_values == "medium").mean()),
        "high_pct": float(high.mean()),
        "high_tier_precision": float(y_array[high].mean()) if high.any() else 0.0,
        "low_tier_observed_rate": float(y_array[low].mean()) if low.any() else 0.0,
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
    }


def train_head(head_name: str, target_name: str, df: pd.DataFrame, y: pd.Series) -> HeadResult:
    train_df, temp_df, y_train, y_temp = train_test_split(
        df, y, test_size=0.30, stratify=y, random_state=42
    )
    valid_df, test_df, y_valid, y_test = train_test_split(
        temp_df, y_temp, test_size=0.50, stratify=y_temp, random_state=42
    )
    preprocessor = build_preprocessor()
    x_train = preprocessor.fit_transform(train_df[FEATURES])
    x_valid = preprocessor.transform(valid_df[FEATURES])
    x_test = preprocessor.transform(test_df[FEATURES])
    from lightgbm import LGBMClassifier

    model = LGBMClassifier(**LIGHTGBM_CONFIG)
    sample_weight = t1_sample_weight(train_df, y_train) if target_name == "T1_maternal_cv_metabolic_proxy" else None
    model.fit(x_train, y_train, sample_weight=sample_weight)
    calibrator = CalibratedClassifierCV(FrozenEstimator(model), method="sigmoid")
    calibrator.fit(x_valid, y_valid)
    valid_prob = calibrator.predict_proba(x_valid)[:, 1]
    low = threshold_for_recall(y_valid, valid_prob)
    high = float(np.quantile(valid_prob, 0.85))
    if high <= low:
        high = min(0.99, low + 0.05)
    thresholds = {
        "low": float(low),
        "high": high,
        "target_recall": TARGET_RECALL,
        "threshold_selection": "validation_only",
        "high_threshold_strategy": "top_15_pct_validation",
    }
    test_prob = calibrator.predict_proba(x_test)[:, 1]
    return HeadResult(
        head_name=head_name,
        target_name=target_name,
        train_df=train_df,
        valid_df=valid_df,
        test_df=test_df,
        y_train=y_train,
        y_valid=y_valid,
        y_test=y_test,
        preprocessor=preprocessor,
        model=model,
        calibrator=calibrator,
        valid_prob=valid_prob,
        test_prob=test_prob,
        thresholds=thresholds,
        validation_metrics=metrics(y_valid, valid_prob, thresholds),
        test_metrics=metrics(y_test, test_prob, thresholds),
    )


def feature_importance(results: dict[str, HeadResult]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for result in results.values():
        names = list(result.preprocessor.get_feature_names_out())
        importances = getattr(result.model, "feature_importances_", np.zeros(len(names)))
        total = float(np.sum(importances)) or 1.0
        for name, importance in zip(names, importances, strict=True):
            rows.append(
                {
                    "head_name": result.head_name,
                    "target_name": result.target_name,
                    "feature": name,
                    "importance": float(importance),
                    "importance_share": float(importance / total),
                }
            )
    return pd.DataFrame(rows).sort_values(["head_name", "importance"], ascending=[True, False])


def feature_missingness(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "feature": FEATURES,
            "missing_rate": [float(df[feature].isna().mean()) for feature in FEATURES],
            "non_missing_count": [int(df[feature].notna().sum()) for feature in FEATURES],
        }
    )


def feature_distributions(df: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for target_name in targets.columns:
        for feature in FEATURES:
            values = numeric(df[feature])
            for target_value, group in pd.DataFrame({"value": values, "target": targets[target_name]}).groupby("target"):
                rows.append(
                    {
                        "target_name": target_name,
                        "feature": feature,
                        "target_value": int(target_value),
                        "missing_rate": float(group["value"].isna().mean()),
                        "mean": float(group["value"].mean()) if group["value"].notna().any() else math.nan,
                        "median": float(group["value"].median()) if group["value"].notna().any() else math.nan,
                        "p25": float(group["value"].quantile(0.25)) if group["value"].notna().any() else math.nan,
                        "p75": float(group["value"].quantile(0.75)) if group["value"].notna().any() else math.nan,
                    }
                )
    return pd.DataFrame(rows)


def score_distribution(result: HeadResult) -> pd.DataFrame:
    frame = pd.DataFrame({"y": np.asarray(result.y_test), "probability": result.test_prob})
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
    report["head_name"] = result.head_name
    report["target_name"] = result.target_name
    report["negatives"] = report["sample_size"] - report["positives"]
    report["score_bin"] = report["score_bin"].astype(str)
    return report[
        ["head_name", "target_name", "score_bin", "sample_size", "mean_predicted_risk", "observed_target_rate", "positives", "negatives"]
    ]


def tier_outcomes(result: HeadResult) -> pd.DataFrame:
    y = np.asarray(result.y_test)
    tier_values = tiers(result.test_prob, result.thresholds)
    total_pos = max(int(y.sum()), 1)
    rows = []
    for tier in ["low", "medium", "high"]:
        mask = tier_values == tier
        rows.append(
            {
                "head_name": result.head_name,
                "target_name": result.target_name,
                "tier": tier,
                "count": int(mask.sum()),
                "pct": float(mask.mean()),
                "observed_target_rate": float(y[mask].mean()) if mask.any() else 0.0,
                "positive_cases_captured_pct": float(y[mask].sum() / total_pos),
            }
        )
    return pd.DataFrame(rows)


def add_bands(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    frame["age_band"] = pd.cut(numeric(frame["mother_age"]), [0, 24, 29, 34, 39, 120], labels=["<25", "25-29", "30-34", "35-39", "40+"], include_lowest=True).astype("string")
    frame["bmi_band"] = pd.cut(numeric(frame["mother_bmi"]), [0, 18.5, 24.9, 29.9, 34.9, 39.9, 120], labels=["<18.5", "18.5-24.9", "25-29.9", "30-34.9", "35-39.9", "40+"], include_lowest=True).astype("string")
    return frame


def subgroup_rows(result: HeadResult) -> list[dict[str, Any]]:
    frame = add_bands(result.test_df)
    frame["y"] = np.asarray(result.y_test)
    frame["prob"] = result.test_prob
    frame["pred"] = (result.test_prob >= result.thresholds["low"]).astype(int)
    frame["tier"] = tiers(result.test_prob, result.thresholds)
    frame["feature_missingness"] = result.test_df[FEATURES].isna().mean(axis=1).to_numpy()
    rows: list[dict[str, Any]] = []
    for column in ["age_band", "bmi_band", "mother_race_6_code", "mother_hispanic_origin_recode", "payment_source_recode", "wic_received"]:
        for value, group in frame.groupby(column, observed=False, dropna=False):
            if len(group) < 20:
                continue
            tn, fp, fn, tp = confusion_matrix(group["y"], group["pred"], labels=[0, 1]).ravel()
            high = group[group["tier"] == "high"]
            low = group[group["tier"] == "low"]
            rows.append(
                {
                    "head_name": result.head_name,
                    "target_name": result.target_name,
                    "subgroup_column": column,
                    "subgroup_value": str(value),
                    "sample_size": int(len(group)),
                    "target_prevalence": float(group["y"].mean()),
                    "recall": float(recall_score(group["y"], group["pred"], zero_division=0)),
                    "false_negative_rate": float(fn / (fn + tp)) if (fn + tp) else 0.0,
                    "precision": float(precision_score(group["y"], group["pred"], zero_division=0)),
                    "false_positive_rate": float(fp / (fp + tn)) if (fp + tn) else 0.0,
                    "brier": float(brier_score_loss(group["y"], group["prob"])),
                    "low_pct": float((group["tier"] == "low").mean()),
                    "medium_pct": float((group["tier"] == "medium").mean()),
                    "high_pct": float((group["tier"] == "high").mean()),
                    "high_tier_observed_rate": float(high["y"].mean()) if not high.empty else 0.0,
                    "low_tier_observed_rate": float(low["y"].mean()) if not low.empty else 0.0,
                    "missingness": float(group["feature_missingness"].mean()),
                }
            )
    return rows


def explanation_factors(row: pd.Series) -> list[str]:
    factors: list[str] = []
    if row.get("prepregnancy_hypertension") == 1:
        factors.append("pre-pregnancy hypertension")
    if row.get("prepregnancy_diabetes") == 1:
        factors.append("pre-pregnancy diabetes")
    if pd.notna(row.get("mother_bmi")) and float(row["mother_bmi"]) >= 30:
        factors.append("higher pre-pregnancy BMI")
    if row.get("previous_preterm_birth") == 1:
        factors.append("previous preterm birth")
    if pd.notna(row.get("prior_dead_births")) and float(row["prior_dead_births"]) > 0:
        factors.append("prior dead birth")
    if row.get("previous_cesarean") == 1 or (pd.notna(row.get("previous_cesarean_count")) and float(row["previous_cesarean_count"]) > 0):
        factors.append("prior cesarean history")
    if row.get("smoking_before_or_during_pregnancy") == 1:
        factors.append("smoking before or during pregnancy")
    if row.get("multiple_gestation_known_or_suspected") == 1:
        factors.append("multiple gestation")
    if row.get("risk_factor_infertility_treatment") == 1:
        factors.append("infertility treatment")
    return factors[:4] or ["No single dominant factor identified; score reflects the combined entered profile."]


def sample_predictions(results: dict[str, HeadResult]) -> pd.DataFrame:
    first = next(iter(results.values()))
    rows = first.test_df[FEATURES].head(20).copy()
    rows["main_factors"] = [json.dumps(explanation_factors(row)) for _, row in rows.iterrows()]
    for result in results.values():
        probs = result.test_prob[: len(rows)]
        rows[f"{result.head_name}_probability"] = [f"{prob:.5f}" for prob in probs]
        rows[f"{result.head_name}_tier"] = tiers(probs, result.thresholds)
        rows[f"{result.head_name}_true_target"] = np.asarray(result.y_test.head(len(rows)))
    medium_high_cols = [column for column in rows.columns if column.endswith("_tier")]
    bad = rows[[*medium_high_cols, "main_factors"]]
    if bad[medium_high_cols].isin(["medium", "high"]).any(axis=1).any() and bad["main_factors"].fillna("").str.strip().isin(["", "[]"]).any():
        raise AssertionError("medium/high prediction has empty explanation")
    return rows


def threshold_summary(results: dict[str, HeadResult]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "head_name": result.head_name,
                "target_name": result.target_name,
                "low_threshold": result.thresholds["low"],
                "high_threshold": result.thresholds["high"],
                "target_recall": TARGET_RECALL,
                "threshold_selection_data": "validation_only",
                "high_threshold_strategy": "top_15_pct_validation",
            }
            for result in results.values()
        ]
    )


def metrics_payload(results: dict[str, HeadResult], split: str) -> dict[str, Any]:
    return {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "split": split,
        "heads": {
            name: {
                "target_name": result.target_name,
                **(result.validation_metrics if split == "validation" else result.test_metrics),
            }
            for name, result in results.items()
        },
    }


def leakage_audit() -> dict[str, Any]:
    forbidden_hits = sorted(set(FEATURES) & FORBIDDEN_INPUTS)
    sensitive_hits = sorted(set(FEATURES) & SENSITIVE_SOCIAL_INPUTS)
    care_planning_hits = sorted(set(FEATURES) & set(CARE_PLANNING_ONLY_FIELDS))
    return {
        "passed": not forbidden_hits and not sensitive_hits and not care_planning_hits,
        "forbidden_hits": forbidden_hits,
        "sensitive_or_social_proxy_hits": sensitive_hits,
        "care_access_or_timing_input_hits": care_planning_hits,
        "threshold_selection_data": "validation_only",
    }


def write_docs(output_dir: Path, source_path: Path, results: dict[str, HeadResult], importance: pd.DataFrame, subgroup: pd.DataFrame) -> None:
    top_features = (
        importance.groupby("feature")["importance"].sum().sort_values(ascending=False).head(12).reset_index()
    )
    t1 = results["maternal_cv_metabolic_signal"].test_metrics
    t5 = results["obstetric_neonatal_signal"].test_metrics
    t0 = results["current_composite_signal"].test_metrics
    weak = subgroup[
        subgroup["subgroup_column"].isin(["age_band", "bmi_band"])
        & subgroup["subgroup_value"].isin(["<25", "<18.5", "18.5-24.9"])
    ][["head_name", "subgroup_column", "subgroup_value", "recall", "false_negative_rate"]]
    a2_subgroup_comparison = compare_a2_subgroups(subgroup)
    v3_t1_subgroup_comparison = compare_v3_t1_subgroups(subgroup)
    decision = [
        "# Timing-Safe Expanded Screening v3.1 Decision Summary",
        "",
        "This package trains the fixed long-form prenatal expanded screening v3.1 timing-safe profile. It is not a diagnosis and not true long-term CVD prediction.",
        "",
        "## Answers",
        "1. v3.1 is the timing-safe long-form candidate. It removes prenatal visits, month prenatal care began, and third-trimester cigarettes from model inputs while keeping them for care planning only.",
        f"2. T1 test metrics: recall `{t1['recall']:.4f}`, FNR `{t1['false_negative_rate']:.4f}`, precision `{t1['precision']:.4f}`, PR-AUC `{t1['pr_auc']:.4f}`, Brier `{t1['brier_score']:.4f}`. T5 test metrics: recall `{t5['recall']:.4f}`, FNR `{t5['false_negative_rate']:.4f}`, precision `{t5['precision']:.4f}`, PR-AUC `{t5['pr_auc']:.4f}`, Brier `{t5['brier_score']:.4f}`.",
        f"3. The model uses `{len(FEATURES)}` model features versus A2's 8 questions. Care-planning-only fields are collected but excluded from prediction.",
        "4. Top global features by summed LightGBM importance:",
        *[f"   - `{row.feature}`: `{row.importance:.0f}`" for row in top_features.itertuples()],
        "5. T1 subgroup recall comparison against v3 is shown below for age <25, BMI <18.5, and BMI 18.5-24.9.",
        "6. Keep A2 as short-form default. Use the acceptance table below to decide whether v3.1 should replace current v3 as the long-form profile.",
        "",
        "## A2 Baseline",
        "- A2 test recall: `0.8663`",
        "- A2 FNR: `0.1337`",
        "- A2 precision: `0.2989`",
        "- A2 PR-AUC: `0.4447`",
        "- A2 Brier: `0.1856`",
        "- A2 questions: `8`",
        "",
        "## Composite Reference",
        f"T0 reference test metrics: recall `{t0['recall']:.4f}`, precision `{t0['precision']:.4f}`, PR-AUC `{t0['pr_auc']:.4f}`, Brier `{t0['brier_score']:.4f}`. This is continuity/reference only and must not be presented as CVD probability.",
        "",
        "## Timing-Safe Input Exclusions",
        *[f"- `{field}` is questionnaire/care-planning only and is not a model feature." for field in CARE_PLANNING_ONLY_FIELDS],
        "",
        "## Weak Subgroup Rows",
        markdown_table(weak.head(30)),
        "",
        "## v3 vs v3.1 T1 Subgroup Recall",
        markdown_table(v3_t1_subgroup_comparison),
        "",
        "## A2 vs v3.1 Composite Subgroup Recall",
        markdown_table(a2_subgroup_comparison),
    ]
    (output_dir / "v3_1_decision_summary.md").write_text("\n".join(decision) + "\n")

    questions = [
        ("mother_age", "Mother's age in years"),
        ("mother_bmi", "Pre-pregnancy BMI, or calculate from height and pre-pregnancy weight if unknown"),
        ("prepregnancy_hypertension", "Hypertension before pregnancy?"),
        ("prepregnancy_diabetes", "Diabetes before pregnancy?"),
        ("prior_live_births", "Number of prior live births"),
        ("prior_dead_births", "Number of prior live births now dead/stillbirth history as recorded"),
        ("prior_terminations", "Number of prior pregnancy terminations/losses as recorded"),
        ("previous_preterm_birth", "Previous preterm birth?"),
        ("previous_cesarean", "Previous cesarean delivery?"),
        ("previous_cesarean_count", "Number of previous cesarean deliveries"),
        ("interval_last_live_birth_recode", "Interval since last live birth, CDC recode"),
        ("interval_last_pregnancy_recode", "Interval since last pregnancy, CDC recode"),
        ("month_prenatal_care_began", "Month prenatal care began; care-planning only, not a model input"),
        ("prenatal_visits", "Number of prenatal visits so far / as recorded; care-planning only, not a model input"),
        ("cigarettes_before_pregnancy", "Average cigarettes per day before pregnancy"),
        ("cigarettes_trimester_1", "Average cigarettes per day in trimester 1"),
        ("cigarettes_trimester_2", "Average cigarettes per day in trimester 2"),
        ("cigarettes_trimester_3", "Average cigarettes per day in trimester 3, if available; care-planning only, not a model input"),
        ("risk_factor_infertility_treatment", "Infertility treatment used?"),
        ("multiple_gestation_known_or_suspected", "Multiple gestation known or suspected?"),
    ]
    q_lines = ["# Expanded Screening v3 Questionnaire Mapping", ""]
    for feature, question in questions:
        q_lines.append(f"- `{feature}`: {question}")
    q_lines.extend(
        [
            "",
            "Derived fields are computed from the timing-safe answers above. Race, ethnicity, education, payment, WIC, marital status, paternal fields, delivery fields, outcome fields, and the care-planning-only fields are not model inputs.",
        ]
    )
    (output_dir / "questionnaire_mapping.md").write_text("\n".join(q_lines) + "\n")

    card = [
        f"# {MODEL_NAME}",
        "",
        f"- Model version: `{MODEL_VERSION}`",
        "- Mode: `prenatal_expanded_screening`",
        "- Framing: prenatal follow-up prioritization profile, not diagnosis and not true long-term CVD prediction.",
        f"- Training source: `{relative_display_path(source_path)}`",
        "- Timing-safe change: prenatal visits, month prenatal care began, and third-trimester cigarettes are excluded from model features.",
        "- T1 mitigation: positive training cases with age <25 or BMI <25 receive sample weights, capped at 3.0 when both apply.",
        "",
        "## Signals",
        "- `maternal_cv_metabolic_signal`: gestational hypertension, eclampsia, gestational diabetes, or severe maternal morbidity proxy.",
        "- `obstetric_neonatal_signal`: preterm birth or low birth weight.",
        "- `current_composite_signal`: reference only.",
        "",
        "## Features",
        *[f"- `{feature}`" for feature in FEATURES],
        "",
        "## Safety",
        SAFETY_NOTE,
    ]
    (output_dir / "model_card.md").write_text("\n".join(card) + "\n")


def compare_a2_subgroups(subgroup: pd.DataFrame) -> pd.DataFrame:
    a2_path = ROOT / "models/cdc-natality/default/fairness_report.csv"
    rows: list[dict[str, Any]] = []
    if not a2_path.exists():
        return pd.DataFrame(rows)
    a2 = pd.read_csv(a2_path)
    v3 = subgroup[
        (subgroup["head_name"] == "current_composite_signal")
        & subgroup["subgroup_column"].isin(["age_band", "bmi_band"])
        & subgroup["subgroup_value"].isin(["<25", "18.5-24.9", "<18.5"])
    ]
    for _, row in v3.iterrows():
        baseline = a2[
            (a2["subgroup_column"] == row["subgroup_column"])
            & (a2["subgroup_value"].astype(str) == str(row["subgroup_value"]))
        ]
        if baseline.empty:
            continue
        a2_recall = float(baseline.iloc[0]["positive_recall"])
        v3_recall = float(row["recall"])
        rows.append(
            {
                "subgroup_column": row["subgroup_column"],
                "subgroup_value": row["subgroup_value"],
                "a2_composite_recall": a2_recall,
                "v3_1_composite_reference_recall": v3_recall,
                "recall_delta": v3_recall - a2_recall,
            }
        )
    return pd.DataFrame(rows).sort_values(["subgroup_column", "subgroup_value"])


def compare_v3_t1_subgroups(subgroup: pd.DataFrame) -> pd.DataFrame:
    v3_path = ROOT / "models/cdc-natality/prenatal_expanded_screening_v3/subgroup_performance_v3.csv"
    rows: list[dict[str, Any]] = []
    if not v3_path.exists():
        return pd.DataFrame(rows)
    v3 = pd.read_csv(v3_path)
    v3_1 = subgroup[
        (subgroup["head_name"] == "maternal_cv_metabolic_signal")
        & subgroup["subgroup_column"].isin(["age_band", "bmi_band"])
        & subgroup["subgroup_value"].isin(["<25", "18.5-24.9", "<18.5"])
    ]
    for _, row in v3_1.iterrows():
        baseline = v3[
            (v3["head_name"] == "maternal_cv_metabolic_signal")
            & (v3["subgroup_column"] == row["subgroup_column"])
            & (v3["subgroup_value"].astype(str) == str(row["subgroup_value"]))
        ]
        if baseline.empty:
            continue
        v3_recall = float(baseline.iloc[0]["recall"])
        v3_1_recall = float(row["recall"])
        rows.append(
            {
                "subgroup_column": row["subgroup_column"],
                "subgroup_value": row["subgroup_value"],
                "v3_t1_recall": v3_recall,
                "v3_1_t1_recall": v3_1_recall,
                "recall_delta": v3_1_recall - v3_recall,
                "improved": bool(v3_1_recall > v3_recall),
            }
        )
    return pd.DataFrame(rows).sort_values(["subgroup_column", "subgroup_value"])


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


def artifact_manifest(output_dir: Path, source_path: Path) -> dict[str, Any]:
    artifacts = sorted(path for path in output_dir.iterdir() if path.is_file() and path.name != "artifact_manifest.json")
    return {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "artifact_timestamp": datetime.now(UTC).isoformat(),
        "git_commit": current_git_commit(),
        "training_data_path": relative_display_path(source_path),
        "feature_list": FEATURES,
        "heads": HEADS,
        "artifact_sha256": {path.name: sha256(path) for path in artifacts},
    }


def validate_outputs(output_dir: Path) -> None:
    missing = [name for name in REQUIRED_ARTIFACTS if not (output_dir / name).exists()]
    if missing:
        raise AssertionError(f"Missing artifacts: {missing}")
    leakage = json.loads((output_dir / "leakage_audit.json").read_text())
    if not leakage["passed"]:
        raise AssertionError("leakage audit failed")
    config = yaml.safe_load((output_dir / "expanded_feature_config.yaml").read_text())
    if config["model_name"] != MODEL_NAME:
        raise AssertionError("config model name mismatch")
    if set(config["features"]) & FORBIDDEN_INPUTS:
        raise AssertionError("forbidden feature used")
    if set(config["features"]) & SENSITIVE_SOCIAL_INPUTS:
        raise AssertionError("sensitive/social feature used")
    if set(config["features"]) & set(CARE_PLANNING_ONLY_FIELDS):
        raise AssertionError("care-access/timing field used as model input")
    for metrics_name in ["metrics_validation.json", "metrics_test.json"]:
        payload = json.loads((output_dir / metrics_name).read_text())
        if payload["model_name"] != MODEL_NAME:
            raise AssertionError(f"{metrics_name} model name mismatch")
    test_payload = json.loads((output_dir / "metrics_test.json").read_text())
    if test_payload["heads"]["maternal_cv_metabolic_signal"]["recall"] < TARGET_RECALL:
        raise AssertionError("T1 recall below acceptance floor")
    if test_payload["heads"]["obstetric_neonatal_signal"]["recall"] < TARGET_RECALL:
        raise AssertionError("T5 recall below acceptance floor")
    subgroup = pd.read_csv(output_dir / "subgroup_performance_v3_1.csv")
    subgroup_compare = compare_v3_t1_subgroups(subgroup)
    if not subgroup_compare.empty and not subgroup_compare["improved"].all():
        failed = subgroup_compare.loc[~subgroup_compare["improved"], ["subgroup_column", "subgroup_value", "v3_t1_recall", "v3_1_t1_recall"]]
        raise AssertionError(f"T1 subgroup recall did not improve versus v3: {failed.to_dict(orient='records')}")
    thresholds = pd.read_csv(output_dir / "threshold_strategy_summary.csv")
    if not (thresholds["threshold_selection_data"] == "validation_only").all():
        raise AssertionError("threshold selection used non-validation data")
    score = pd.read_csv(output_dir / "score_distribution_report.csv")
    test_metrics = json.loads((output_dir / "metrics_test.json").read_text())["heads"]
    for head_name, group in score.groupby("head_name"):
        observed = float((group["observed_target_rate"].fillna(0) * group["sample_size"]).sum() / group["sample_size"].sum())
        expected = float(test_metrics[head_name]["target_prevalence"])
        if abs(observed - expected) > 1e-9:
            raise AssertionError(f"score distribution mismatch for {head_name}")
    sample = pd.read_csv(output_dir / "sample_predictions.csv")
    tier_cols = [column for column in sample.columns if column.endswith("_tier")]
    if sample[tier_cols].isin(["medium", "high"]).any(axis=1).any() and sample["main_factors"].fillna("").str.strip().isin(["", "[]"]).any():
        raise AssertionError("empty medium/high explanations")
    text = (output_dir / "model_card.md").read_text() + (output_dir / "v3_1_decision_summary.md").read_text()
    if "/Users/" in text:
        raise AssertionError("local absolute path exposed in public artifact")


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if args.check_only:
        validate_outputs(output_dir)
        print(f"checked_expanded_screening_v3_1_timing_safe={output_dir}")
        return

    config = load_config(args.config)
    df_raw, source_path = load_source_data(config, args.data_path, args.max_rows)
    df = clean_and_derive_features(df_raw)
    targets = build_targets(df)
    audit = leakage_audit()
    if not audit["passed"]:
        raise ValueError(audit)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: dict[str, HeadResult] = {}
    for head_name, target_name in HEADS.items():
        result = train_head(head_name, target_name, df, targets[target_name])
        results[head_name] = result
        print(
            "HEAD",
            head_name,
            f"target={target_name}",
            f"test_recall={result.test_metrics['recall']:.4f}",
            f"test_pr_auc={result.test_metrics['pr_auc']:.4f}",
        )

    models = {head: result.model for head, result in results.items()}
    preprocessors = {head: result.preprocessor for head, result in results.items()}
    calibrators = {head: result.calibrator for head, result in results.items()}
    pipelines = {
        head: Pipeline([("preprocessor", result.preprocessor), ("calibrator", result.calibrator)])
        for head, result in results.items()
    }
    joblib.dump(models, output_dir / "model.joblib")
    joblib.dump(preprocessors, output_dir / "preprocessor.joblib")
    joblib.dump(calibrators, output_dir / "calibrator.joblib")
    joblib.dump(pipelines, output_dir / "combined_pipeline.joblib")
    for head, result in results.items():
        joblib.dump(result.model, output_dir / f"model_{head}.joblib")
        joblib.dump(result.calibrator, output_dir / f"calibrator_{head}.joblib")
        joblib.dump(result.preprocessor, output_dir / f"preprocessor_{head}.joblib")

    expanded_config = {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "model_mode": "prenatal_expanded_screening",
        "artifact_dir": "models/cdc-natality/prenatal_expanded_screening_v3_1_timing_safe",
        "features": FEATURES,
        "numeric_features": NUMERIC_FEATURES,
        "binary_features": BINARY_FEATURES,
        "care_planning_only_fields": CARE_PLANNING_ONLY_FIELDS,
        "t1_sample_weighting": {
            "positive_age_under_25": 2.0,
            "positive_bmi_under_25": 2.0,
            "positive_both_cap": 3.0,
        },
        "heads": HEADS,
        "lightgbm": LIGHTGBM_CONFIG,
        "threshold_selection": "validation_only",
        "overall_followup_priority_rule": "high if either T1 or T5 high; medium if either T1 or T5 medium; low only if both T1 and T5 low",
        "audit_only_columns": AUDIT_COLUMNS,
        "forbidden_input_columns": sorted(FORBIDDEN_INPUTS),
        "sensitive_social_paternal_exclude": sorted(SENSITIVE_SOCIAL_INPUTS),
    }
    (output_dir / "expanded_feature_config.yaml").write_text(yaml.safe_dump(expanded_config, sort_keys=False))
    write_json(output_dir / "target_definitions.json", {
        name: {
            "head_name": head,
            "positive_definition": (
                "gestational hypertension, eclampsia, gestational diabetes, or severe maternal morbidity proxy"
                if name == "T1_maternal_cv_metabolic_proxy"
                else "preterm birth or low birth weight"
                if name == "T5_obstetric_neonatal_proxy"
                else "T1 or T5 positive; reference only"
            ),
            "prevalence": float(targets[name].mean()),
            "positive_count": int(targets[name].sum()),
        }
        for head, name in HEADS.items()
    })
    write_json(output_dir / "metrics_validation.json", metrics_payload(results, "validation"))
    write_json(output_dir / "metrics_test.json", metrics_payload(results, "test"))
    write_json(output_dir / "leakage_audit.json", audit)
    pd.DataFrame(
        [
            {
                "model_name": MODEL_NAME,
                "model_version": MODEL_VERSION,
                "head_name": head,
                "target_name": result.target_name,
                "feature_count": len(FEATURES),
                "model_family": "calibrated_shallow_lightgbm",
                **result.test_metrics,
            }
            for head, result in results.items()
        ]
    ).to_csv(output_dir / "model_registry.csv", index=False)
    threshold_summary(results).to_csv(output_dir / "threshold_strategy_summary.csv", index=False)
    importance = feature_importance(results)
    importance.to_csv(output_dir / "feature_importance.csv", index=False)
    feature_missingness(df).to_csv(output_dir / "feature_missingness.csv", index=False)
    feature_distributions(df, targets).to_csv(output_dir / "feature_distributions.csv", index=False)
    subgroup = pd.DataFrame([row for result in results.values() for row in subgroup_rows(result)])
    subgroup.to_csv(output_dir / "subgroup_performance_v3_1.csv", index=False)
    subgroup.to_csv(output_dir / "fairness_report.csv", index=False)
    sample_predictions(results).to_csv(output_dir / "sample_predictions.csv", index=False)
    pd.concat([score_distribution(result) for result in results.values()], ignore_index=True).to_csv(
        output_dir / "score_distribution_report.csv", index=False
    )
    pd.concat([tier_outcomes(result) for result in results.values()], ignore_index=True).to_csv(
        output_dir / "tier_outcomes.csv", index=False
    )
    write_docs(output_dir, source_path, results, importance, subgroup)
    write_json(output_dir / "artifact_manifest.json", artifact_manifest(output_dir, source_path))
    validate_outputs(output_dir)
    print(f"expanded_screening_v3_1_timing_safe_dir={output_dir}")


if __name__ == "__main__":
    main()
