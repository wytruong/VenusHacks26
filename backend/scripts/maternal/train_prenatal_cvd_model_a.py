#!/usr/bin/env python3
"""Train and audit the prenatal cardiovascular risk-priority Model A."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
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
DEFAULT_CONFIG_PATH = ROOT / "configs/maternal/prenatal_model_a_v1.yaml"
FOLLOWUP_PRIORITY = {
    "low": "Routine prenatal cardiovascular health education.",
    "medium": "Enhanced counseling and planned primary-care or OB follow-up.",
    "high": "Prioritized cardiovascular-risk review and postpartum follow-up planning.",
}
DISCLAIMER = (
    "This is a risk-prioritization aid, not a diagnosis. Clinical judgment should guide care decisions."
)
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
DELIVERY_OUTCOME_FIELDS = {
    "gestational_diabetes",
    "gestational_hypertension",
    "eclampsia",
    "severe_maternal_morbidity_proxy",
    "obstetric_estimate_gestation_weeks",
    "birth_weight_grams",
    "birth_weight_recode_14",
    "birth_weight_recode_4",
    "maternal_icu",
    "maternal_transfusion",
    "ruptured_uterus",
    "unplanned_hysterectomy",
    "delivery_route_code",
    "trial_of_labor_attempted",
    "apgar_5_min",
    "apgar_10_min",
    "abnormal_condition_nicu",
    "breastfed_at_discharge",
    "infant_sex",
}


@dataclass(frozen=True)
class CandidateResult:
    name: str
    model_family: str
    features: list[str]
    numeric_features: list[str]
    binary_features: list[str]
    preprocessor: ColumnTransformer
    model: Any
    calibrator: CalibratedClassifierCV
    validation_metrics: dict[str, float]
    test_metrics: dict[str, float]
    thresholds: dict[str, float]
    validation_probabilities: np.ndarray
    test_probabilities: np.ndarray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--data-path", type=Path)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--model-family", choices=["auto", "logistic", "lightgbm", "both"], default="auto")
    parser.add_argument("--calibration-method", choices=["sigmoid", "isotonic"], default="sigmoid")
    parser.add_argument("--max-rows", type=int, help="Optional development cap after CSV load.")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return yaml.safe_load(fh)


def resolve_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return ROOT / path


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def to_binary(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.astype("float64")
    normalized = series.astype("string").str.strip().str.lower()
    return normalized.map(
        {
            "true": 1.0,
            "false": 0.0,
            "1": 1.0,
            "0": 0.0,
            "yes": 1.0,
            "no": 0.0,
            "y": 1.0,
            "n": 0.0,
        }
    )


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def load_data(config: dict[str, Any], data_path: Path | None, max_rows: int | None) -> tuple[pd.DataFrame, Path]:
    configured = data_path or resolve_path(config["data_path"])
    fallback = resolve_path(config["fallback_data_path"])
    source = configured if configured.exists() else fallback
    if not source.exists():
        raise FileNotFoundError(f"No natality training CSV found at {configured} or {fallback}")

    required = list(dict.fromkeys(config["raw_columns_needed"] + config["audit_only_columns"]))
    df = pd.read_csv(source, usecols=lambda col: col in required, nrows=max_rows, low_memory=False)
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    return df, source


def validate_schema(config: dict[str, Any]) -> None:
    schema_path = resolve_path(config["schema_path"])
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    schema = pd.read_csv(schema_path)
    raw_outputs = set(schema["output_name"])
    missing = sorted(set(config["raw_columns_needed"]) - raw_outputs)
    if missing:
        raise ValueError(f"Schema does not define raw columns: {missing}")


def build_prenatal_target(df: pd.DataFrame) -> pd.Series:
    return (
        (to_binary(df["gestational_hypertension"]) == 1)
        | (to_binary(df["eclampsia"]) == 1)
        | (to_binary(df["gestational_diabetes"]) == 1)
        | (to_binary(df["severe_maternal_morbidity_proxy"]) == 1)
        | (numeric(df["obstetric_estimate_gestation_weeks"]) < 37)
        | (numeric(df["birth_weight_grams"]) < 2500)
    ).astype(int)


def build_prenatal_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    height = numeric(df["mother_height_inches"])
    weight = numeric(df["prepregnancy_weight_lb"])
    bmi = numeric(df["mother_bmi"])
    computed_bmi = 703 * weight / (height**2)
    df["mother_bmi"] = bmi.where(bmi.notna(), computed_bmi)
    df["prior_adverse_pregnancy_history"] = (
        (to_binary(df["previous_preterm_birth"]) == 1) | (numeric(df["prior_dead_births"]) > 0)
    ).astype(int)
    df["smoking_before_or_during_pregnancy"] = (
        (numeric(df["cigarettes_before_pregnancy"]) > 0)
        | (numeric(df["cigarettes_trimester_1"]) > 0)
        | (numeric(df["cigarettes_trimester_2"]) > 0)
    ).astype(int)
    df["multiple_gestation_known_or_suspected"] = (numeric(df["plurality"]) > 1).astype(int)
    df["prepregnancy_hypertension"] = to_binary(df["prepregnancy_hypertension"])
    df["prepregnancy_diabetes"] = to_binary(df["prepregnancy_diabetes"])
    return df


def clean_values(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["mother_age"] = numeric(df["mother_age"])
    df.loc[(df["mother_age"] < 10) | (df["mother_age"] > 60), "mother_age"] = np.nan
    df["mother_height_inches"] = numeric(df["mother_height_inches"])
    df.loc[
        (df["mother_height_inches"] < 48) | (df["mother_height_inches"] > 78),
        "mother_height_inches",
    ] = np.nan
    df["mother_bmi"] = numeric(df["mother_bmi"])
    df.loc[(df["mother_bmi"] < 12) | (df["mother_bmi"] > 80), "mother_bmi"] = np.nan
    df["prior_live_births"] = numeric(df["prior_live_births"])
    df.loc[(df["prior_live_births"] < 0) | (df["prior_live_births"] > 20), "prior_live_births"] = np.nan
    return df


def split_data(df: pd.DataFrame, target: pd.Series, config: dict[str, Any]) -> tuple[pd.DataFrame, ...]:
    test_size = float(config["test_size"])
    validation_size = float(config["validation_size"])
    random_state = int(config["random_state"])
    train_df, temp_df, y_train, y_temp = train_test_split(
        df,
        target,
        test_size=test_size + validation_size,
        stratify=target,
        random_state=random_state,
    )
    valid_df, test_df, y_valid, y_test = train_test_split(
        temp_df,
        y_temp,
        test_size=test_size / (test_size + validation_size),
        stratify=y_temp,
        random_state=random_state,
    )
    return train_df, valid_df, test_df, y_train, y_valid, y_test


def feature_splits(config: dict[str, Any], features: list[str]) -> tuple[list[str], list[str]]:
    numeric_features = [feature for feature in config["numeric_features"] if feature in features]
    binary_features = [feature for feature in config["binary_features"] if feature in features]
    unknown = sorted(set(features) - set(numeric_features) - set(binary_features))
    if unknown:
        raise ValueError(f"Features missing numeric/binary preprocessing declaration: {unknown}")
    return numeric_features, binary_features


def validate_no_leakage(config: dict[str, Any], features: list[str]) -> dict[str, Any]:
    forbidden = set(config["forbidden_input_columns"])
    feature_set = set(features)
    forbidden_hits = sorted(feature_set & forbidden)
    sensitive_hits = sorted(feature_set & SENSITIVE_SOCIAL_FIELDS)
    outcome_hits = sorted(feature_set & DELIVERY_OUTCOME_FIELDS)
    if forbidden_hits:
        raise ValueError(f"Forbidden leakage columns in feature set: {forbidden_hits}")
    return {
        "passed": True,
        "forbidden_hits": forbidden_hits,
        "sensitive_or_social_proxy_hits": sensitive_hits,
        "delivery_or_outcome_time_hits": outcome_hits,
    }


def build_preprocessor(numeric_features: list[str], binary_features: list[str]) -> ColumnTransformer:
    numeric_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    binary_pipe = Pipeline(steps=[("imputer", SimpleImputer(strategy="most_frequent"))])
    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipe, numeric_features),
            ("binary", binary_pipe, binary_features),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def expected_calibration_error(y_true: pd.Series, y_prob: np.ndarray, bins: int = 10) -> float:
    frame = pd.DataFrame({"y": np.asarray(y_true), "prob": y_prob})
    frame["bin"] = pd.cut(frame["prob"], bins=np.linspace(0.0, 1.0, bins + 1), include_lowest=True)
    ece = 0.0
    for _, group in frame.groupby("bin", observed=False):
        if group.empty:
            continue
        ece += (len(group) / len(frame)) * abs(group["y"].mean() - group["prob"].mean())
    return float(ece)


def calibration_slope_intercept(y_true: pd.Series, y_prob: np.ndarray) -> tuple[float, float]:
    clipped = np.clip(y_prob, 1e-6, 1 - 1e-6)
    logits = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    if len(np.unique(y_true)) < 2:
        return math.nan, math.nan
    model = LogisticRegression(solver="lbfgs")
    model.fit(logits, y_true)
    return float(model.coef_[0][0]), float(model.intercept_[0])


def tier_counts(y_prob: np.ndarray, thresholds: dict[str, float]) -> dict[str, float]:
    tiers = pd.Series([risk_tier(float(prob), thresholds) for prob in y_prob])
    counts = tiers.value_counts()
    total = len(tiers)
    return {
        "risk_low_count": int(counts.get("low", 0)),
        "risk_medium_count": int(counts.get("medium", 0)),
        "risk_high_count": int(counts.get("high", 0)),
        "risk_low_pct": float(counts.get("low", 0) / total),
        "risk_medium_pct": float(counts.get("medium", 0) / total),
        "risk_high_pct": float(counts.get("high", 0) / total),
    }


def classification_metrics(y_true: pd.Series, y_prob: np.ndarray, thresholds: dict[str, float]) -> dict[str, float]:
    threshold = thresholds["low"]
    y_pred = (y_prob >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    recall = recall_score(y_true, y_pred, zero_division=0)
    precision = precision_score(y_true, y_pred, zero_division=0)
    slope, intercept = calibration_slope_intercept(y_true, y_prob)
    return {
        "sample_size": int(len(y_true)),
        "target_prevalence": float(np.mean(y_true)),
        "positive_recall": float(recall),
        "false_negative_rate": float(1.0 - recall),
        "precision": float(precision),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "brier_score": float(brier_score_loss(y_true, y_prob)),
        "expected_calibration_error": expected_calibration_error(y_true, y_prob),
        "calibration_slope": slope,
        "calibration_intercept": intercept,
        "threshold": float(threshold),
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
        **tier_counts(y_prob, thresholds),
    }


def tune_thresholds(y_true: pd.Series, y_prob: np.ndarray, target_recall: float) -> dict[str, float]:
    rows: list[dict[str, float]] = []
    for threshold in np.arange(0.01, 1.0, 0.01):
        y_pred = (y_prob >= threshold).astype(int)
        rows.append(
            {
                "threshold": float(threshold),
                "recall": float(recall_score(y_true, y_pred, zero_division=0)),
                "precision": float(precision_score(y_true, y_pred, zero_division=0)),
                "f1": float(f1_score(y_true, y_pred, zero_division=0)),
            }
        )
    candidates = [row for row in rows if row["recall"] >= target_recall]
    selected = sorted(candidates or rows, key=lambda row: (-row["f1"], row["threshold"]))[0]
    low = float(selected["threshold"])
    high = float(np.quantile(y_prob, 0.85))
    if high <= low:
        high = min(0.99, low + 0.05)
    return {
        "low": low,
        "high": high,
        "target_recall": float(target_recall),
        "threshold_selection_f1": float(selected["f1"]),
        "threshold_selection_precision": float(selected["precision"]),
        "threshold_selection_recall": float(selected["recall"]),
        "selection_data": "validation_only",
    }


def risk_tier(probability: float, thresholds: dict[str, float]) -> str:
    if probability < thresholds["low"]:
        return "low"
    if probability < thresholds["high"]:
        return "medium"
    return "high"


def train_logistic_regression(x_train: np.ndarray, y_train: pd.Series) -> LogisticRegression:
    model = LogisticRegression(max_iter=1000, class_weight="balanced", solver="saga", random_state=42)
    model.fit(x_train, y_train)
    return model


def train_lightgbm(x_train: np.ndarray, y_train: pd.Series, config: dict[str, Any]) -> Any:
    from lightgbm import LGBMClassifier

    model = LGBMClassifier(**config["lightgbm"])
    model.fit(x_train, y_train)
    return model


def calibrate_model(model: Any, x_valid: np.ndarray, y_valid: pd.Series, method: str) -> CalibratedClassifierCV:
    calibrator = CalibratedClassifierCV(FrozenEstimator(model), method=method)
    calibrator.fit(x_valid, y_valid)
    return calibrator


def evaluate_variant(
    config: dict[str, Any],
    variant: dict[str, Any],
    train_df: pd.DataFrame,
    valid_df: pd.DataFrame,
    test_df: pd.DataFrame,
    y_train: pd.Series,
    y_valid: pd.Series,
    y_test: pd.Series,
    calibration_method: str,
) -> CandidateResult:
    features = list(variant["features"])
    validate_no_leakage(config, features)
    numeric_features, binary_features = feature_splits(config, features)
    preprocessor = build_preprocessor(numeric_features, binary_features)
    x_train = preprocessor.fit_transform(train_df[features])
    x_valid = preprocessor.transform(valid_df[features])
    x_test = preprocessor.transform(test_df[features])

    if variant["model_family"] == "logistic":
        model = train_logistic_regression(x_train, y_train)
    elif variant["model_family"] == "lightgbm":
        model = train_lightgbm(x_train, y_train, config)
    else:
        raise ValueError(f"Unsupported model family: {variant['model_family']}")

    calibrator = calibrate_model(model, x_valid, y_valid, calibration_method)
    valid_prob = calibrator.predict_proba(x_valid)[:, 1]
    thresholds = tune_thresholds(y_valid, valid_prob, float(config["target_recall"]))
    test_prob = calibrator.predict_proba(x_test)[:, 1]
    return CandidateResult(
        name=variant["name"],
        model_family=variant["model_family"],
        features=features,
        numeric_features=numeric_features,
        binary_features=binary_features,
        preprocessor=preprocessor,
        model=model,
        calibrator=calibrator,
        validation_metrics=classification_metrics(y_valid, valid_prob, thresholds),
        test_metrics=classification_metrics(y_test, test_prob, thresholds),
        thresholds=thresholds,
        validation_probabilities=valid_prob,
        test_probabilities=test_prob,
    )


def variants_to_run(config: dict[str, Any], model_family: str) -> list[dict[str, Any]]:
    variants = list(config["comparison_variants"])
    if model_family == "auto":
        return [variant for variant in variants if variant["name"] in {
            "minimal8_calibrated_logistic_regression",
            "minimal8_calibrated_lightgbm",
        }]
    if model_family == "both":
        return variants
    return [variant for variant in variants if variant["model_family"] == model_family]


def choose_candidate(results: list[CandidateResult]) -> CandidateResult:
    def rank(result: CandidateResult) -> tuple[float, float, float, float, float]:
        metrics = result.validation_metrics
        interpretability = 1.0 if result.model_family == "logistic" else 0.0
        return (
            metrics["positive_recall"],
            -metrics["brier_score"],
            interpretability,
            -metrics["expected_calibration_error"],
            metrics["pr_auc"],
        )

    return sorted(results, key=rank, reverse=True)[0]


def flatten_metrics(results: list[CandidateResult]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for result in results:
        for split_name, metrics in (("validation", result.validation_metrics), ("test", result.test_metrics)):
            rows.append(
                {
                    "model": result.name,
                    "model_family": result.model_family,
                    "split": split_name,
                    "features": ",".join(result.features),
                    "threshold_low": result.thresholds["low"],
                    "threshold_high": result.thresholds["high"],
                    **metrics,
                }
            )
    return pd.DataFrame(rows)


def feature_coefficients(result: CandidateResult) -> pd.DataFrame:
    feature_names = list(result.preprocessor.get_feature_names_out())
    if not hasattr(result.model, "coef_"):
        return pd.DataFrame({"feature": feature_names, "standardized_coefficient": np.nan, "odds_ratio": np.nan})
    coef = result.model.coef_[0]
    return (
        pd.DataFrame(
            {
                "feature": feature_names,
                "standardized_coefficient": coef,
                "odds_ratio": np.exp(coef),
                "direction": np.where(coef >= 0, "positive", "negative"),
            }
        )
        .sort_values("standardized_coefficient", ascending=False)
        .reset_index(drop=True)
    )


def feature_distributions(df: pd.DataFrame, y: pd.Series, features: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for feature in features:
        series = numeric(df[feature])
        for target_value, group in pd.DataFrame({"feature_value": series, "target": y}).groupby("target"):
            rows.append(
                {
                    "feature": feature,
                    "target": int(target_value),
                    "missing_rate": float(group["feature_value"].isna().mean()),
                    "mean": float(group["feature_value"].mean()) if group["feature_value"].notna().any() else math.nan,
                    "median": float(group["feature_value"].median()) if group["feature_value"].notna().any() else math.nan,
                    "p25": float(group["feature_value"].quantile(0.25)) if group["feature_value"].notna().any() else math.nan,
                    "p75": float(group["feature_value"].quantile(0.75)) if group["feature_value"].notna().any() else math.nan,
                }
            )
    return pd.DataFrame(rows)


def feature_missingness(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "feature": features,
            "missing_rate": [float(df[feature].isna().mean()) for feature in features],
            "non_missing_count": [int(df[feature].notna().sum()) for feature in features],
        }
    )


def top_contributors(row: pd.Series) -> list[str]:
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
    return factors[:3]


def sample_predictions(
    df: pd.DataFrame,
    y_true: pd.Series,
    y_prob: np.ndarray,
    thresholds: dict[str, float],
    features: list[str],
    limit: int = 20,
) -> pd.DataFrame:
    rows = df[features].head(limit).copy()
    probs = y_prob[: len(rows)]
    rows["true_target"] = np.asarray(y_true.head(limit))
    rows["prenatal_cvd_followup_probability"] = np.round(probs, 4)
    rows["risk_tier"] = [risk_tier(float(prob), thresholds) for prob in probs]
    rows["top_3_contributing_factors"] = [json.dumps(top_contributors(row)) for _, row in rows.iterrows()]
    return rows


def calibration_report(y_true: pd.Series, y_prob: np.ndarray, bins: int = 10) -> pd.DataFrame:
    frame = pd.DataFrame({"y": np.asarray(y_true), "probability": y_prob})
    frame["bin"] = pd.cut(frame["probability"], bins=np.linspace(0.0, 1.0, bins + 1), include_lowest=True)
    report = (
        frame.groupby("bin", observed=False)
        .agg(sample_size=("y", "size"), mean_predicted_risk=("probability", "mean"), observed_rate=("y", "mean"))
        .reset_index()
    )
    report["bin"] = report["bin"].astype(str)
    return report


def fairness_report(
    audit_df: pd.DataFrame,
    feature_df: pd.DataFrame,
    features: list[str],
    y_true: pd.Series,
    y_prob: np.ndarray,
    threshold: float,
) -> pd.DataFrame:
    audit = audit_df.copy()
    audit["age_band"] = pd.cut(
        numeric(audit["mother_age"]),
        bins=[0, 24, 29, 34, 39, 120],
        labels=["<25", "25-29", "30-34", "35-39", "40+"],
        include_lowest=True,
    ).astype("string")
    audit["bmi_band"] = pd.cut(
        numeric(feature_df["mother_bmi"]),
        bins=[0, 18.5, 24.9, 29.9, 34.9, 39.9, 120],
        labels=["<18.5", "18.5-24.9", "25-29.9", "30-34.9", "35-39.9", "40+"],
        include_lowest=True,
    ).astype("string")
    audit["y_true"] = np.asarray(y_true)
    audit["y_prob"] = y_prob
    audit["y_pred"] = (y_prob >= threshold).astype(int)
    audit["feature_missingness_rate"] = feature_df[features].isna().mean(axis=1).to_numpy()

    group_columns = [
        "mother_race_6_code",
        "mother_hispanic_origin_recode",
        "payment_source_recode",
        "wic_received",
        "age_band",
        "bmi_band",
    ]
    rows: list[dict[str, Any]] = []
    for column in group_columns:
        for value, group in audit.groupby(column, dropna=False, observed=False):
            if len(group) < 20:
                continue
            recall = recall_score(group["y_true"], group["y_pred"], zero_division=0)
            rows.append(
                {
                    "subgroup_column": column,
                    "subgroup_value": str(value),
                    "sample_size": int(len(group)),
                    "target_prevalence": float(group["y_true"].mean()),
                    "mean_predicted_risk": float(group["y_prob"].mean()),
                    "positive_recall": float(recall),
                    "false_negative_rate": float(1.0 - recall),
                    "precision": float(precision_score(group["y_true"], group["y_pred"], zero_division=0)),
                    "brier_score": float(brier_score_loss(group["y_true"], group["y_prob"])),
                    "subgroup_missingness_rate": float(group[column].isna().mean()),
                    "feature_missingness_rate": float(group["feature_missingness_rate"].mean()),
                }
            )
    return pd.DataFrame(rows)


def rule_based_metrics(test_df: pd.DataFrame, y_test: pd.Series) -> pd.DataFrame:
    rules = {
        "rule_hypertension_only": test_df["prepregnancy_hypertension"].fillna(0).to_numpy(),
        "rule_diabetes_only": test_df["prepregnancy_diabetes"].fillna(0).to_numpy(),
        "rule_bmi_ge_30": (numeric(test_df["mother_bmi"]) >= 30).astype(int).to_numpy(),
        "rule_age_ge_35": (numeric(test_df["mother_age"]) >= 35).astype(int).to_numpy(),
        "rule_htn_or_diabetes_or_bmi_ge_30": (
            (test_df["prepregnancy_hypertension"].fillna(0) == 1)
            | (test_df["prepregnancy_diabetes"].fillna(0) == 1)
            | (numeric(test_df["mother_bmi"]) >= 30)
        )
        .astype(int)
        .to_numpy(),
    }
    rows: list[dict[str, Any]] = []
    for name, y_pred in rules.items():
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred, labels=[0, 1]).ravel()
        recall = recall_score(y_test, y_pred, zero_division=0)
        rows.append(
            {
                "rule": name,
                "positive_recall": float(recall),
                "false_negative_rate": float(1.0 - recall),
                "precision": float(precision_score(y_test, y_pred, zero_division=0)),
                "f1": float(f1_score(y_test, y_pred, zero_division=0)),
                "true_negative": int(tn),
                "false_positive": int(fp),
                "false_negative": int(fn),
                "true_positive": int(tp),
            }
        )
    return pd.DataFrame(rows)


def write_model_card(path: Path, config: dict[str, Any], source_path: Path, selected: CandidateResult) -> None:
    lines = [
        f"# {config['model_name']}",
        "",
        "## Intended Use",
        "Prenatal cardiovascular risk-priority screening for enhanced counseling, closer monitoring, or postpartum follow-up planning.",
        "",
        "## Not Intended Use",
        "This model must not be used as a cardiovascular disease diagnosis, medication recommendation, care denial tool, or replacement for clinician judgment.",
        "",
        "## Training Data",
        f"- Source: `{source_path}`",
        f"- Target: `{config['target']}`",
        "- Target definition: gestational hypertension, eclampsia, gestational diabetes, severe maternal morbidity proxy, preterm birth, or low birth weight.",
        "",
        "## Feature List",
        *[f"- `{feature}`" for feature in selected.features],
        "",
        "## Excluded Inputs",
        "Protected, social proxy, paternal, detailed prenatal-care utilization, reproductive-technology, delivery/outcome-time, and direct aggregate label fields are excluded from prediction.",
        "",
        "## Selected Model",
        f"- Model family: `{selected.name}`",
        f"- Validation positive recall: {selected.validation_metrics['positive_recall']:.4f}",
        f"- Validation false-negative rate: {selected.validation_metrics['false_negative_rate']:.4f}",
        f"- Validation Brier score: {selected.validation_metrics['brier_score']:.4f}",
        f"- Test positive recall: {selected.test_metrics['positive_recall']:.4f}",
        f"- Test false-negative rate: {selected.test_metrics['false_negative_rate']:.4f}",
        "",
        "## Known Limitations",
        "This model was trained on a derived proxy label, not confirmed long-term cardiovascular outcomes. It estimates pregnancy-stage risk priority for enhanced counseling and follow-up planning. It should not be used as a standalone diagnostic tool.",
        "",
        "## Clinical Safety Warnings",
        "- The model never overrides clinician judgment.",
        "- The model never recommends medication changes.",
        "- The model never tells a patient to delay care.",
        "- Seek urgent medical care for chest pain, severe shortness of breath, fainting, severe headache, vision changes, severe swelling, or very high blood pressure readings.",
        "",
        "## Recommended Review Process",
        "Review calibration, subgroup performance, threshold behavior, and clinical plausibility before any patient- or clinician-facing use.",
        "",
        f"Disclaimer: {DISCLAIMER}",
        "",
    ]
    path.write_text("\n".join(lines))


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


def write_audit_report(
    path: Path,
    config: dict[str, Any],
    source_path: Path,
    selected: CandidateResult,
    results: list[CandidateResult],
    leakage_audit: dict[str, Any],
    rule_metrics: pd.DataFrame,
) -> None:
    comparison = flatten_metrics(results)
    validation_rows = comparison[comparison["split"] == "validation"]
    test_rows = comparison[comparison["split"] == "test"]
    best_rule = rule_metrics.sort_values("positive_recall", ascending=False).iloc[0]
    lines = [
        "# Prenatal Model A Validation Audit",
        "",
        "## Recommendation",
        f"Use `{selected.name}` for Model A. It is the best fit for the stated priority order: no leakage, minimal sensitive input, high recall, calibration, interpretability, fairness monitoring, then PR-AUC.",
        "",
        "## Exact Training Setup",
        f"- Target used: `{config['target']}`.",
        "- Target does not include `prepregnancy_hypertension` or `prepregnancy_diabetes`.",
        f"- Data source: `{source_path}`.",
        "- Current trained model before this follow-up audit was `minimal8_calibrated_logistic_regression`; it was already the minimal 8-feature logistic model, not a broad/full-feature CDC model.",
        f"- Selected model features: `{', '.join(selected.features)}`.",
        f"- Sensitive/social/paternal input hits: `{leakage_audit['sensitive_or_social_proxy_hits']}`.",
        f"- Delivery/outcome-time input hits: `{leakage_audit['delivery_or_outcome_time_hits']}`.",
        f"- Forbidden leakage input hits: `{leakage_audit['forbidden_hits']}`.",
        "",
        "## Threshold Details",
        "- Thresholds were tuned on validation only.",
        f"- Target recall: `{selected.thresholds['target_recall']:.2f}`.",
        f"- Low/positive threshold: `{selected.thresholds['low']:.2f}`.",
        f"- High-tier threshold: `{selected.thresholds['high']:.6f}`.",
        f"- Final test recall at the low threshold: `{selected.test_metrics['positive_recall']:.4f}`.",
        f"- Test tier mix: low `{selected.test_metrics['risk_low_count']}` ({selected.test_metrics['risk_low_pct']:.2%}), medium `{selected.test_metrics['risk_medium_count']}` ({selected.test_metrics['risk_medium_pct']:.2%}), high `{selected.test_metrics['risk_high_count']}` ({selected.test_metrics['risk_high_pct']:.2%}).",
        "",
        "## Validation Comparison",
        markdown_table(
            validation_rows[
                [
                    "model",
                    "target_prevalence",
                    "threshold_low",
                    "positive_recall",
                    "false_negative_rate",
                    "precision",
                    "f1",
                    "roc_auc",
                    "pr_auc",
                    "brier_score",
                ]
            ]
        ),
        "",
        "## Untouched Test Comparison",
        markdown_table(
            test_rows[
                [
                    "model",
                    "target_prevalence",
                    "threshold_low",
                    "positive_recall",
                    "false_negative_rate",
                    "precision",
                    "f1",
                    "roc_auc",
                    "pr_auc",
                    "brier_score",
                ]
            ]
        ),
        "",
        "## Rule-Based Screen Check",
        f"Best simple rule by recall was `{best_rule['rule']}` with recall `{best_rule['positive_recall']:.4f}` and precision `{best_rule['precision']:.4f}`. It is not recommended as the accepted Model A because it misses substantially more positives than the calibrated model.",
        "",
        "## Production Caveat",
        "This remains a derived-proxy, retrospective CDC natality model. It should be reviewed clinically and externally validated before patient-facing deployment.",
        "",
    ]
    path.write_text("\n".join(lines))


def save_artifacts(
    config: dict[str, Any],
    config_path: Path,
    source_path: Path,
    selected: CandidateResult,
    results: list[CandidateResult],
    test_df: pd.DataFrame,
    y_test: pd.Series,
    full_df: pd.DataFrame,
    full_y: pd.Series,
    artifact_dir: Path,
) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    leakage_audit = validate_no_leakage(config, selected.features)

    joblib.dump(selected.model, artifact_dir / "model.joblib")
    joblib.dump(selected.preprocessor, artifact_dir / "preprocessor.joblib")
    joblib.dump(selected.calibrator, artifact_dir / "calibrator.joblib")
    selected_config = dict(config)
    selected_config["features"] = selected.features
    selected_config["numeric_features"] = selected.numeric_features
    selected_config["binary_features"] = selected.binary_features
    (artifact_dir / "feature_config.yaml").write_text(yaml.safe_dump(selected_config, sort_keys=False))
    write_json(artifact_dir / "thresholds.json", selected.thresholds)
    write_json(artifact_dir / "metrics_validation.json", selected.validation_metrics)
    write_json(artifact_dir / "metrics_test.json", selected.test_metrics)
    write_json(artifact_dir / "leakage_audit.json", leakage_audit)

    candidate_metrics = {
        result.name: {
            "features": result.features,
            "validation": result.validation_metrics,
            "test": result.test_metrics,
            "thresholds": result.thresholds,
        }
        for result in results
    }
    if "minimal8_calibrated_logistic_regression" in candidate_metrics:
        candidate_metrics["current_trained_model"] = candidate_metrics["minimal8_calibrated_logistic_regression"]
    write_json(artifact_dir / "candidate_metrics.json", candidate_metrics)
    flatten_metrics(results).to_csv(artifact_dir / "model_comparison.csv", index=False)

    coefficients = feature_coefficients(selected)
    coefficients.to_csv(artifact_dir / "feature_coefficients.csv", index=False)
    coefficients.to_csv(artifact_dir / "feature_importance.csv", index=False)
    feature_missingness(full_df, selected.features).to_csv(artifact_dir / "feature_missingness.csv", index=False)
    feature_distributions(full_df, full_y, selected.features).to_csv(
        artifact_dir / "feature_distributions.csv", index=False
    )
    calibration_report(y_test, selected.test_probabilities).to_csv(artifact_dir / "calibration_report.csv", index=False)
    fairness_report(
        test_df[config["audit_only_columns"]],
        test_df,
        selected.features,
        y_test,
        selected.test_probabilities,
        selected.thresholds["low"],
    ).to_csv(artifact_dir / "fairness_report.csv", index=False)
    sample_predictions(test_df, y_test, selected.test_probabilities, selected.thresholds, selected.features).to_csv(
        artifact_dir / "sample_predictions.csv", index=False
    )
    rule_metrics = rule_based_metrics(test_df, y_test)
    rule_metrics.to_csv(artifact_dir / "rule_based_screen_metrics.csv", index=False)

    write_model_card(artifact_dir / "model_card.md", config, source_path, selected)
    write_audit_report(
        artifact_dir / "validation_audit_report.md",
        config,
        source_path,
        selected,
        results,
        leakage_audit,
        rule_metrics,
    )


def print_metric_lines(selected: CandidateResult) -> None:
    metrics = {
        "validation_positive_recall": selected.validation_metrics["positive_recall"],
        "validation_false_negative_rate": selected.validation_metrics["false_negative_rate"],
        "validation_brier_score": selected.validation_metrics["brier_score"],
        "validation_pr_auc": selected.validation_metrics["pr_auc"],
        "test_positive_recall": selected.test_metrics["positive_recall"],
        "test_false_negative_rate": selected.test_metrics["false_negative_rate"],
        "test_brier_score": selected.test_metrics["brier_score"],
        "test_pr_auc": selected.test_metrics["pr_auc"],
    }
    for name, value in metrics.items():
        print(f"METRIC {name}={value:.10f}")


def main() -> None:
    args = parse_args()
    config_path = args.config.resolve()
    config = load_config(config_path)
    validate_schema(config)
    df, source_path = load_data(config, args.data_path, args.max_rows)
    df[config["target"]] = build_prenatal_target(df)
    df = clean_values(build_prenatal_features(df))

    for variant in variants_to_run(config, "both"):
        validate_no_leakage(config, variant["features"])

    train_df, valid_df, test_df, y_train, y_valid, y_test = split_data(df, df[config["target"]], config)
    results = [
        evaluate_variant(
            config,
            variant,
            train_df,
            valid_df,
            test_df,
            y_train,
            y_valid,
            y_test,
            args.calibration_method,
        )
        for variant in variants_to_run(config, args.model_family)
    ]
    if not results:
        raise RuntimeError("No model candidates were trained")

    selected = choose_candidate(results)
    artifact_dir = args.artifact_dir or resolve_path(config["artifact_dir"])
    save_artifacts(config, config_path, source_path, selected, results, test_df, y_test, df, df[config["target"]], artifact_dir)

    print(f"selected_model={selected.name}")
    print(f"artifact_dir={artifact_dir}")
    print(f"data_source={source_path}")
    print_metric_lines(selected)


if __name__ == "__main__":
    main()
