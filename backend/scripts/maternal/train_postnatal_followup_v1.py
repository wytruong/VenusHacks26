#!/usr/bin/env python3
"""Export and validate the postnatal follow-up screening v1 package."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys
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

from scripts.maternal.postnatal_followup_v1 import MODEL_NAME, MODEL_VERSION, ROUTING_METHOD, predict_postnatal_followup
from scripts.maternal.train_prenatal_cvd_model_a import numeric, to_binary

DEFAULT_CONFIG_PATH = ROOT / "configs/maternal/postnatal_followup_v1.yaml"
DEFAULT_OUTPUT_DIR = ROOT / "models/cdc-natality/postnatal_followup_v1"
MODEL_MODE = "postnatal_followup"
RULE_ROUTER_COMPONENT = "rule_followup_router"
AUXILIARY_COMPONENT = "auxiliary_lightgbm_ranking"
SAFETY_NOTE = "This is a follow-up prioritization aid, not a diagnosis."
SIGNALS = [
    "maternal_cv_metabolic_followup_signal",
    "hypertension_followup_signal",
    "diabetes_followup_signal",
    "severe_maternal_morbidity_followup_signal",
    "obstetric_neonatal_context_signal",
]
AUXILIARY_NUMERIC_FEATURES = [
    "mother_age",
    "mother_bmi",
    "mother_height_inches",
    "prepregnancy_weight_lb",
    "prior_live_births",
    "prior_dead_births",
    "prior_terminations",
    "previous_cesarean_count",
    "interval_last_live_birth_recode",
    "interval_last_other_pregnancy_recode",
    "interval_last_pregnancy_recode",
    "cigarettes_before_pregnancy",
    "cigarettes_trimester_1",
    "cigarettes_trimester_2",
]
AUXILIARY_BINARY_FEATURES = [
    "prepregnancy_hypertension",
    "prepregnancy_diabetes",
    "previous_preterm_birth",
    "previous_cesarean",
    "risk_factor_infertility_treatment",
    "multiple_gestation_known_or_suspected",
]
AUXILIARY_FEATURES = AUXILIARY_NUMERIC_FEATURES + AUXILIARY_BINARY_FEATURES
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
REQUIRED_ARTIFACTS = [
    "postnatal_v1_decision_summary.md",
    "postnatal_feature_config.yaml",
    "questionnaire_mapping.md",
    "target_definitions.json",
    "metrics_validation.json",
    "metrics_test.json",
    "split_summary.json",
    "subgroup_performance_postnatal_v1.csv",
    "feature_importance.csv",
    "calibration_curve.csv",
    "leakage_audit.json",
    "sample_predictions.csv",
    "tier_outcomes.csv",
    "model_card.md",
    "artifact_manifest.json",
    "combined_pipeline.joblib",
    "model.joblib",
    "preprocessor.joblib",
    "calibrator.joblib",
    "metrics_rule_validation.json",
    "metrics_rule_test.json",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--data-path", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-rows", type=int)
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return yaml.safe_load(fh)


def resolve_data_path(config: dict[str, Any], data_path: Path | None) -> Path:
    if data_path:
        return data_path
    configured = ROOT / config["data_path"]
    if configured.exists():
        return configured
    fallback_full = Path("/Users/benj/Documents/Coding/cardiac_mvp/data/cdc-natality/derived/natality_2024_structured.csv")
    if fallback_full.exists():
        return fallback_full
    return ROOT / config["fallback_data_path"]


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


def config_columns(config: dict[str, Any]) -> list[str]:
    columns = (
        config["history_inputs"]
        + config["postnatal_clinical_facts"]
        + config["obstetric_neonatal_context"]
        + config["care_planning_only_fields"]
        + config["audit_only_columns"]
    )
    return list(dict.fromkeys(columns))


def load_source_data(config: dict[str, Any], data_path: Path | None, max_rows: int | None) -> tuple[pd.DataFrame, Path]:
    source = resolve_data_path(config, data_path)
    if not source.exists():
        raise FileNotFoundError(source)
    wanted = set(config_columns(config))
    df = pd.read_csv(source, usecols=lambda column: column in wanted, nrows=max_rows, low_memory=False)
    derived_or_app_fields = {"multiple_gestation_known_or_suspected"}
    missing = sorted((wanted - derived_or_app_fields) - set(df.columns))
    if missing:
        raise ValueError(f"Missing source columns: {missing}")
    return df, source


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    numeric_columns = [
        "mother_age",
        "mother_bmi",
        "mother_height_inches",
        "prepregnancy_weight_lb",
        "delivery_weight_lb",
        "weight_gain_lb",
        "prior_live_births",
        "prior_dead_births",
        "prior_terminations",
        "previous_cesarean_count",
        "interval_last_live_birth_recode",
        "interval_last_other_pregnancy_recode",
        "interval_last_pregnancy_recode",
        "cigarettes_before_pregnancy",
        "cigarettes_trimester_1",
        "cigarettes_trimester_2",
        "cigarettes_trimester_3",
        "month_prenatal_care_began",
        "prenatal_visits",
        "plurality",
        "obstetric_estimate_gestation_weeks",
        "birth_weight_grams",
        "apgar_5_min",
        "apgar_10_min",
    ]
    for column in numeric_columns:
        if column in df:
            df[column] = numeric(df[column])
    for column in [
        "prepregnancy_hypertension",
        "prepregnancy_diabetes",
        "previous_preterm_birth",
        "risk_factor_infertility_treatment",
        "previous_cesarean",
        "gestational_hypertension",
        "eclampsia",
        "gestational_diabetes",
        "maternal_transfusion",
        "perineal_laceration",
        "ruptured_uterus",
        "unplanned_hysterectomy",
        "maternal_icu",
        "trial_of_labor_attempted",
        "abnormal_condition_nicu",
        "breastfed_at_discharge",
    ]:
        if column in df:
            df[column] = to_binary(df[column]).fillna(0).astype(int)
    if "multiple_gestation_known_or_suspected" not in df:
        df["multiple_gestation_known_or_suspected"] = (numeric(df["plurality"]) > 1).astype(int)
    df.loc[(df["mother_age"] < 10) | (df["mother_age"] > 60), "mother_age"] = np.nan
    df.loc[(df["mother_bmi"] < 12) | (df["mother_bmi"] > 80), "mother_bmi"] = np.nan
    df.loc[(df["mother_height_inches"] < 48) | (df["mother_height_inches"] > 78), "mother_height_inches"] = np.nan
    df.loc[(df["prepregnancy_weight_lb"] < 70) | (df["prepregnancy_weight_lb"] > 500), "prepregnancy_weight_lb"] = np.nan
    return df


def labels(df: pd.DataFrame) -> pd.DataFrame:
    hypertension = ((df["prepregnancy_hypertension"] == 1) | (df["gestational_hypertension"] == 1) | (df["eclampsia"] == 1)).astype(int)
    diabetes = ((df["prepregnancy_diabetes"] == 1) | (df["gestational_diabetes"] == 1)).astype(int)
    severe = (
        (df["maternal_transfusion"] == 1)
        | (df["ruptured_uterus"] == 1)
        | (df["unplanned_hysterectomy"] == 1)
        | (df["maternal_icu"] == 1)
    ).astype(int)
    neonatal = (
        (df["obstetric_estimate_gestation_weeks"] < 37)
        | (df["birth_weight_grams"] < 2500)
        | (df["abnormal_condition_nicu"] == 1)
    ).astype(int)
    maternal = ((hypertension == 1) | (diabetes == 1) | (severe == 1)).astype(int)
    return pd.DataFrame(
        {
            "maternal_cv_metabolic_followup_signal": maternal,
            "hypertension_followup_signal": hypertension,
            "diabetes_followup_signal": diabetes,
            "severe_maternal_morbidity_followup_signal": severe,
            "obstetric_neonatal_context_signal": neonatal,
        },
        index=df.index,
    )


def add_bands(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    frame["age_band"] = pd.cut(numeric(frame["mother_age"]), [0, 24, 29, 34, 39, 120], labels=["<25", "25-29", "30-34", "35-39", "40+"], include_lowest=True).astype("string")
    frame["bmi_band"] = pd.cut(numeric(frame["mother_bmi"]), [0, 18.5, 24.9, 29.9, 34.9, 39.9, 120], labels=["<18.5", "18.5-24.9", "25-29.9", "30-34.9", "35-39.9", "40+"], include_lowest=True).astype("string")
    return frame


def split_indices(stratify_label: pd.Series) -> tuple[pd.Index, pd.Index, pd.Index]:
    train_idx, temp_idx = train_test_split(
        stratify_label.index,
        test_size=0.30,
        stratify=stratify_label,
        random_state=42,
    )
    valid_idx, test_idx = train_test_split(
        temp_idx,
        test_size=0.50,
        stratify=stratify_label.loc[temp_idx],
        random_state=42,
    )
    return pd.Index(train_idx), pd.Index(valid_idx), pd.Index(test_idx)


def build_preprocessor() -> ColumnTransformer:
    numeric_pipe = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())])
    binary_pipe = Pipeline([("imputer", SimpleImputer(strategy="most_frequent"))])
    return ColumnTransformer(
        [
            ("numeric", numeric_pipe, AUXILIARY_NUMERIC_FEATURES),
            ("binary", binary_pipe, AUXILIARY_BINARY_FEATURES),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def threshold_for_recall(y_true: pd.Series, y_score: np.ndarray, target_recall: float = 0.85) -> float:
    positive_scores = np.asarray(y_score)[np.asarray(y_true) == 1]
    if len(positive_scores) == 0:
        return 0.99
    return float(np.quantile(positive_scores, max(0, 1 - target_recall), method="lower"))


def train_auxiliary_heads(
    df: pd.DataFrame,
    targets: pd.DataFrame,
    train_idx: pd.Index,
    valid_idx: pd.Index,
    test_idx: pd.Index,
) -> dict[str, dict[str, Any]]:
    from lightgbm import LGBMClassifier

    results: dict[str, dict[str, Any]] = {}
    for signal in SIGNALS:
        y_train = targets.loc[train_idx, signal]
        y_valid = targets.loc[valid_idx, signal]
        y_test = targets.loc[test_idx, signal]
        preprocessor = build_preprocessor()
        x_train = preprocessor.fit_transform(df.loc[train_idx, AUXILIARY_FEATURES])
        x_valid = preprocessor.transform(df.loc[valid_idx, AUXILIARY_FEATURES])
        x_test = preprocessor.transform(df.loc[test_idx, AUXILIARY_FEATURES])
        model = LGBMClassifier(**LIGHTGBM_CONFIG)
        model.fit(x_train, y_train)
        calibrator = CalibratedClassifierCV(FrozenEstimator(model), method="sigmoid")
        calibrator.fit(x_valid, y_valid)
        valid_score = calibrator.predict_proba(x_valid)[:, 1]
        test_score = calibrator.predict_proba(x_test)[:, 1]
        threshold = threshold_for_recall(y_valid, valid_score)
        high_threshold = float(np.quantile(valid_score, 0.85))
        if high_threshold <= threshold:
            high_threshold = min(0.99, threshold + 0.05)
        results[signal] = {
            "preprocessor": preprocessor,
            "model": model,
            "calibrator": calibrator,
            "validation_score": valid_score,
            "test_score": test_score,
            "threshold": threshold,
            "high_threshold": high_threshold,
        }
    return results


def calibration_slope_intercept(y_true: pd.Series, y_score: pd.Series) -> tuple[float, float]:
    y_array = np.asarray(y_true)
    if len(np.unique(y_array)) < 2:
        return math.nan, math.nan
    clipped = np.clip(np.asarray(y_score, dtype=float), 1e-6, 1 - 1e-6)
    logits = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    model = LogisticRegression(solver="lbfgs")
    model.fit(logits, y_array)
    return float(model.coef_[0][0]), float(model.intercept_[0])


def calibration_curve_rows(y_true: pd.Series, y_score: pd.Series, signal: str, split: str) -> list[dict[str, Any]]:
    frame = pd.DataFrame({"y": np.asarray(y_true), "score": np.asarray(y_score, dtype=float)})
    frame["score_bin"] = pd.cut(frame["score"], bins=np.linspace(0, 1, 11), include_lowest=True)
    rows: list[dict[str, Any]] = []
    for score_bin, group in frame.groupby("score_bin", observed=False):
        if group.empty:
            continue
        rows.append(
            {
                "split": split,
                "signal_name": signal,
                "score_bin": str(score_bin),
                "sample_size": int(len(group)),
                "mean_predicted_score": float(group["score"].mean()),
                "observed_signal_rate": float(group["y"].mean()),
                "positives": int(group["y"].sum()),
            }
        )
    return rows


def metrics_for(y_true: pd.Series, y_score: pd.Series | np.ndarray, threshold: float = 0.5, score_type: str = "probability") -> dict[str, Any]:
    y_pred = (np.asarray(y_score, dtype=float) >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    slope, intercept = calibration_slope_intercept(y_true, y_score)
    unique = np.unique(np.asarray(y_true))
    return {
        "sample_size": int(len(y_true)),
        "target_prevalence": float(y_true.mean()),
        "positive_recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "false_negative_rate": float(1 - recall_score(y_true, y_pred, zero_division=0)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y_true, y_score)) if len(unique) > 1 else math.nan,
        "roc_auc": float(roc_auc_score(y_true, y_score)) if len(unique) > 1 else math.nan,
        "brier_score": float(brier_score_loss(y_true, y_score)),
        "calibration_slope": slope,
        "calibration_intercept": intercept,
        "threshold": float(threshold),
        "score_type": score_type,
        "model_component": AUXILIARY_COMPONENT if score_type == "calibrated_auxiliary_lightgbm_probability" else RULE_ROUTER_COMPONENT,
        "runtime_use": "diagnostic_only" if score_type == "calibrated_auxiliary_lightgbm_probability" else "identity_audit_only",
        "true_negative": int(tn),
        "false_positive": int(fp),
        "false_negative": int(fn),
        "true_positive": int(tp),
    }


def metric_payload(
    targets: pd.DataFrame,
    indices: pd.Index,
    split: str,
    auxiliary: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if auxiliary is None:
        signals = {
            signal: metrics_for(
                targets.loc[indices, signal],
                targets.loc[indices, signal],
                0.5,
                "deterministic_rule_score_0_or_1",
            )
            for signal in SIGNALS
        }
    else:
        score_key = "validation_score" if split == "validation" else "test_score"
        signals = {
            signal: metrics_for(
                targets.loc[indices, signal],
                auxiliary[signal][score_key],
                auxiliary[signal]["threshold"],
                "calibrated_auxiliary_lightgbm_probability",
            )
            for signal in SIGNALS
        }
    return {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "model_mode": MODEL_MODE,
        "rule_followup_router": "runtime logic",
        "auxiliary_lightgbm_ranking": "diagnostic only",
        "split": split,
        "split_size": int(len(indices)),
        "split_note": "70/15/15 train/validation/test split stratified by any postnatal follow-up signal.",
        "signals": signals,
    }


def split_summary(stratify_label: pd.Series, train_idx: pd.Index, valid_idx: pd.Index, test_idx: pd.Index) -> dict[str, Any]:
    total = len(stratify_label)
    rows = {}
    for name, idx in [("train", train_idx), ("validation", valid_idx), ("test", test_idx)]:
        rows[name] = {
            "sample_size": int(len(idx)),
            "fraction": float(len(idx) / total),
            "stratify_positive_rate": float(stratify_label.loc[idx].mean()),
        }
    return {
        "strategy": "stratified 70/15/15 split",
        "stratify_label": "any postnatal follow-up signal",
        "total_sample_size": int(total),
        "splits": rows,
    }


def subgroup_performance(
    df: pd.DataFrame,
    targets: pd.DataFrame,
    test_idx: pd.Index,
    auxiliary: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    frame = add_bands(df.loc[test_idx])
    rows: list[dict[str, Any]] = []
    for signal in SIGNALS:
        frame["y"] = targets.loc[test_idx, signal].to_numpy()
        frame["pred"] = (auxiliary[signal]["test_score"] >= auxiliary[signal]["threshold"]).astype(int)
        for column in ["age_band", "bmi_band", "mother_race_6_code", "mother_hispanic_origin_recode", "payment_source_recode", "wic_received"]:
            for value, group in frame.groupby(column, observed=False, dropna=False):
                if len(group) < 20:
                    continue
                tn, fp, fn, tp = confusion_matrix(group["y"], group["pred"], labels=[0, 1]).ravel()
                recall = recall_score(group["y"], group["pred"], zero_division=0)
                rows.append(
                    {
                        "signal_name": signal,
                        "subgroup_column": column,
                        "subgroup_value": str(value),
                        "sample_size": int(len(group)),
                        "target_prevalence": float(group["y"].mean()),
                        "recall": float(recall),
                        "false_negative_rate": float(1 - recall),
                        "precision": float(precision_score(group["y"], group["pred"], zero_division=0)),
                        "true_negative": int(tn),
                        "false_positive": int(fp),
                        "false_negative": int(fn),
                        "true_positive": int(tp),
                    }
                )
    return pd.DataFrame(rows)


def feature_importance(config: dict[str, Any], auxiliary: dict[str, dict[str, Any]] | None = None) -> pd.DataFrame:
    if auxiliary:
        rows: list[dict[str, Any]] = []
        for signal, payload in auxiliary.items():
            names = list(payload["preprocessor"].get_feature_names_out())
            importances = getattr(payload["model"], "feature_importances_", np.zeros(len(names)))
            total = float(np.sum(importances)) or 1.0
            for name, importance in zip(names, importances, strict=True):
                rows.append(
                    {
                        "signal_name": signal,
                        "feature": name,
                        "group": "auxiliary_model_input",
                        "importance_type": "lightgbm_split_importance",
                        "importance": float(importance),
                        "importance_share": float(importance / total),
                    }
                )
        return pd.DataFrame(rows).sort_values(["signal_name", "importance"], ascending=[True, False])
    rows = []
    for group, fields in [
        ("history_input", config["history_inputs"]),
        ("postnatal_rule_input", config["postnatal_clinical_facts"]),
        ("obstetric_neonatal_context", config["obstetric_neonatal_context"]),
        ("care_planning_only", config["care_planning_only_fields"]),
    ]:
        for field in fields:
            rows.append({"signal_name": "rule_router", "feature": field, "group": group, "importance_type": "rule_or_context", "importance": 1.0 if group != "care_planning_only" else 0.0, "importance_share": math.nan})
    return pd.DataFrame(rows)


def tier_outcomes(targets: pd.DataFrame, test_idx: pd.Index) -> pd.DataFrame:
    rows = []
    for signal in SIGNALS:
        y = targets.loc[test_idx, signal]
        for tier, mask in {"high": y == 1, "low": y == 0}.items():
            rows.append(
                {
                    "signal_name": signal,
                    "tier": tier,
                    "count": int(mask.sum()),
                    "pct": float(mask.mean()),
                    "observed_signal_rate": float(y[mask].mean()) if mask.any() else 0.0,
                }
            )
    return pd.DataFrame(rows)


def calibration_report(targets: pd.DataFrame, valid_idx: pd.Index, test_idx: pd.Index, auxiliary: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for split, indices in [("validation", valid_idx), ("test", test_idx)]:
        for signal in SIGNALS:
            y = targets.loc[indices, signal]
            score = auxiliary[signal]["validation_score"] if split == "validation" else auxiliary[signal]["test_score"]
            rows.extend(calibration_curve_rows(y, score, signal, split))
    return pd.DataFrame(rows)


def sample_predictions(df: pd.DataFrame, test_idx: pd.Index, output_dir: Path) -> pd.DataFrame:
    rows = []
    for _, row in df.loc[test_idx].head(20).iterrows():
        payload = predict_postnatal_followup(row.dropna().to_dict(), output_dir)
        rows.append(
            {
                "overall_followup_priority": payload["overall_followup_priority"],
                "maternal_cv_metabolic_tier": payload["maternal_cv_metabolic_followup_signal"]["tier"],
                "hypertension_tier": payload["hypertension_followup_signal"]["tier"],
                "diabetes_tier": payload["diabetes_followup_signal"]["tier"],
                "severe_morbidity_tier": payload["severe_maternal_morbidity_followup_signal"]["tier"],
                "obstetric_neonatal_tier": payload["obstetric_neonatal_context_signal"]["tier"],
                "missing_inputs": json.dumps(payload["missing_inputs"]),
                "data_quality_warnings": json.dumps(payload["data_quality_warnings"]),
            }
        )
    return pd.DataFrame(rows)


def leakage_audit(config: dict[str, Any]) -> dict[str, Any]:
    scoring_fields = set(config["history_inputs"] + config["postnatal_clinical_facts"] + config["obstetric_neonatal_context"])
    sensitive_hits = sorted(scoring_fields & set(config["exclude_from_scoring"]))
    aggregate_hits = sorted(scoring_fields & set(config["never_use_as_inputs"]))
    return {
        "passed": not sensitive_hits and not aggregate_hits,
        "sensitive_social_paternal_hits": sensitive_hits,
        "aggregate_or_proxy_label_hits": aggregate_hits,
        "rule_followup_router": "runtime logic",
        "auxiliary_lightgbm_ranking": "diagnostic only",
        "metrics_rule_files": "rule identity audit only",
        "metrics_validation_test": "auxiliary model metrics only",
        "rule_target_self_prediction": "not_applicable_rule_routing_not_learned_prediction",
        "single_cvd_probability_output": False,
    }


def target_definitions() -> dict[str, Any]:
    return {
        "hypertension_followup_signal": "prepregnancy_hypertension OR gestational_hypertension OR eclampsia",
        "diabetes_followup_signal": "prepregnancy_diabetes OR gestational_diabetes",
        "severe_maternal_morbidity_followup_signal": "maternal_transfusion OR ruptured_uterus OR unplanned_hysterectomy OR maternal_icu",
        "obstetric_neonatal_context_signal": "obstetric_estimate_gestation_weeks < 37 OR birth_weight_grams < 2500 OR abnormal_condition_nicu",
        "maternal_cv_metabolic_followup_signal": "hypertension_followup_signal OR diabetes_followup_signal OR severe_maternal_morbidity_followup_signal",
    }


def write_docs(output_dir: Path, config: dict[str, Any], source_path: Path, metrics_test: dict[str, Any], subgroup: pd.DataFrame) -> None:
    lines = [
        "# Postnatal Follow-Up v1 Decision Summary",
        "",
        "This package is a postnatal follow-up prioritization profile. It is not a diagnosis and not true long-term CVD prediction.",
        "",
        "## Decision",
        "Use this as a separate postnatal workflow package. Do not replace prenatal v3.1/default with it.",
        "`rule_followup_router` is the runtime logic. It uses known postnatal facts directly and is not predicting future disease.",
        "`auxiliary_lightgbm_ranking` is diagnostic only for v1.0. It is not used by runtime inference and should not drive care.",
        "`metrics_rule_*` files are rule identity audits only. `metrics_validation.json` and `metrics_test.json` are auxiliary model metrics only.",
        "",
        "## Signals",
    ]
    for signal, row in metrics_test["signals"].items():
        lines.append(
            f"- `{signal}` prevalence `{row['target_prevalence']:.4f}` on test split; "
            f"positive recall `{row['positive_recall']:.4f}`, precision `{row['precision']:.4f}`, "
            f"F1 `{row['f1']:.4f}`, PR-AUC `{row['pr_auc']:.4f}`, ROC-AUC `{row['roc_auc']:.4f}`, "
            f"Brier `{row['brier_score']:.4f}`."
        )
    lines.extend(
        [
            "",
            "## Output Contract",
            "The output is multi-signal. It does not collapse follow-up into one combined risk score.",
            "Runtime inference uses deterministic rule routing only.",
            "Validation metrics are reported during development in `metrics_validation.json`; final untouched test metrics are reported in `metrics_test.json`. These are diagnostic-only auxiliary ML metrics.",
            "Calibration curves use auxiliary calibrated LightGBM probabilities, not deterministic rule scores. They should not drive care in v1.0.",
            "",
            "## Subgroup Audit",
            markdown_table(subgroup.head(30)),
        ]
    )
    (output_dir / "postnatal_v1_decision_summary.md").write_text("\n".join(lines) + "\n")

    q_lines = ["# Postnatal Follow-Up v1 Questionnaire Mapping", ""]
    for group_name in ["history_inputs", "postnatal_clinical_facts", "obstetric_neonatal_context", "care_planning_only_fields"]:
        q_lines.append(f"## {group_name}")
        q_lines.extend(f"- `{field}`" for field in config[group_name])
        q_lines.append("")
    q_lines.append("Sensitive, social, paternal, and aggregate proxy fields are excluded from scoring.")
    (output_dir / "questionnaire_mapping.md").write_text("\n".join(q_lines) + "\n")

    card = [
        "# postnatal_followup_v1",
        "",
        f"- Model version: `{MODEL_VERSION}`",
        f"- Mode: `{MODEL_MODE}`",
        f"- Training source: `{relative_display_path(source_path)}`",
        "- Framing: postnatal follow-up routing aid, not diagnosis.",
        "- Runtime method: `rule_followup_router` uses known postnatal facts directly.",
        "- It is not predicting future disease.",
        "- Auxiliary method: `auxiliary_lightgbm_ranking` is diagnostic only and is not used by runtime inference.",
        "- Split: 70% train, 15% validation, 15% test, stratified by any postnatal follow-up signal.",
        "- Rule metrics: `metrics_rule_validation.json` and `metrics_rule_test.json` are rule identity audits only. They are not learned-model performance.",
        "- Auxiliary ML metrics: `metrics_validation.json` and `metrics_test.json` report positive recall, FNR, precision, F1, PR-AUC, ROC-AUC, Brier score, calibration slope/intercept, and calibration curve bins for diagnostic-only auxiliary heads.",
        "- Auxiliary ML metrics should not drive care in v1.0.",
        "- Auxiliary model inputs exclude postnatal clinical facts, obstetric/neonatal outcome fields, and care-planning-only fields to avoid target self-prediction and timing-proxy metrics.",
        "- Severe maternal morbidity auxiliary head is weak because the event is rare; interpret its auxiliary ranking metrics with caution.",
        "",
        "## Safety",
        SAFETY_NOTE,
    ]
    (output_dir / "model_card.md").write_text("\n".join(card) + "\n")


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


def manifest(output_dir: Path, source_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    artifacts = sorted(path for path in output_dir.iterdir() if path.is_file() and path.name != "artifact_manifest.json")
    return {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "model_mode": MODEL_MODE,
        "runtime_component": RULE_ROUTER_COMPONENT,
        "diagnostic_component": AUXILIARY_COMPONENT,
        "artifact_timestamp": datetime.now(UTC).isoformat(),
        "git_commit": current_git_commit(),
        "training_data_path": relative_display_path(source_path),
        "artifact_sha256": {path.name: sha256(path) for path in artifacts},
        "feature_groups": {
            "history_inputs": config["history_inputs"],
            "postnatal_clinical_facts": config["postnatal_clinical_facts"],
            "obstetric_neonatal_context": config["obstetric_neonatal_context"],
            "care_planning_only_fields": config["care_planning_only_fields"],
        },
    }


def validate_outputs(output_dir: Path) -> None:
    missing = [name for name in REQUIRED_ARTIFACTS if not (output_dir / name).exists()]
    if missing:
        raise AssertionError(f"Missing artifacts: {missing}")
    audit = json.loads((output_dir / "leakage_audit.json").read_text())
    if not audit["passed"]:
        raise AssertionError("leakage audit failed")
    config = yaml.safe_load((output_dir / "postnatal_feature_config.yaml").read_text())
    if config["model_name"] != MODEL_NAME:
        raise AssertionError("model name mismatch")
    for metrics_name in ["metrics_validation.json", "metrics_test.json"]:
        payload = json.loads((output_dir / metrics_name).read_text())
        for signal, row in payload["signals"].items():
            for metric in [
                "positive_recall",
                "false_negative_rate",
                "precision",
                "f1",
                "pr_auc",
                "roc_auc",
                "brier_score",
                "calibration_slope",
                "calibration_intercept",
            ]:
                if metric not in row:
                    raise AssertionError(f"{metrics_name} missing {metric} for {signal}")
            if row.get("score_type") != "calibrated_auxiliary_lightgbm_probability":
                raise AssertionError(f"{metrics_name} uses non-auxiliary score for {signal}")
            if row.get("model_component") != AUXILIARY_COMPONENT or row.get("runtime_use") != "diagnostic_only":
                raise AssertionError(f"{metrics_name} is not labeled diagnostic-only auxiliary ML for {signal}")
    rule_payload = json.loads((output_dir / "metrics_rule_test.json").read_text())
    if not all(
        row.get("score_type") == "deterministic_rule_score_0_or_1"
        and row.get("model_component") == RULE_ROUTER_COMPONENT
        and row.get("runtime_use") == "identity_audit_only"
        for row in rule_payload["signals"].values()
    ):
        raise AssertionError("rule metrics are not marked as deterministic")
    for rule_name in ["metrics_rule_validation.json", "metrics_rule_test.json"]:
        if "calibrated_auxiliary_lightgbm_probability" in (output_dir / rule_name).read_text():
            raise AssertionError(f"{rule_name} mixes learned-model metrics into rule identity audit")
    calibration = pd.read_csv(output_dir / "calibration_curve.csv")
    if not {"validation", "test"}.issubset(set(calibration["split"])):
        raise AssertionError("calibration curve missing validation or test split")
    split = json.loads((output_dir / "split_summary.json").read_text())
    fractions = split["splits"]
    if not (abs(fractions["train"]["fraction"] - 0.70) < 0.001 and abs(fractions["validation"]["fraction"] - 0.15) < 0.001 and abs(fractions["test"]["fraction"] - 0.15) < 0.001):
        raise AssertionError("split fractions are not 70/15/15")
    scoring = set(config["history_inputs"] + config["postnatal_clinical_facts"] + config["obstetric_neonatal_context"])
    if scoring & set(config["exclude_from_scoring"]):
        raise AssertionError("sensitive/social/paternal field used for scoring")
    forbidden_auxiliary = set(config["postnatal_clinical_facts"] + config["obstetric_neonatal_context"] + config["care_planning_only_fields"] + config["never_use_as_inputs"])
    if set(AUXILIARY_FEATURES) & forbidden_auxiliary:
        raise AssertionError("auxiliary model uses postnatal outcome/target fields")
    if set(AUXILIARY_FEATURES) & set(config["exclude_from_scoring"]):
        raise AssertionError("auxiliary model uses sensitive/social/paternal fields")
    feature_importance = pd.read_csv(output_dir / "feature_importance.csv")
    if set(feature_importance["feature"]) & (forbidden_auxiliary | set(config["exclude_from_scoring"])):
        raise AssertionError("feature importance exposes forbidden auxiliary model input")
    text = (output_dir / "model_card.md").read_text() + (output_dir / "postnatal_v1_decision_summary.md").read_text()
    if "/Users/" in text:
        raise AssertionError("local absolute path exposed")
    if '"cardiovascular_risk_probability"' in text.lower() or '"cvd_probability"' in text.lower():
        raise AssertionError("fake single CVD probability wording found")
    required_card_phrases = [
        "rule_followup_router",
        "auxiliary_lightgbm_ranking",
        "not predicting future disease",
        "rule identity audits only",
        "diagnostic only",
        "should not drive care",
        "Severe maternal morbidity auxiliary head is weak",
    ]
    card_text = (output_dir / "model_card.md").read_text()
    missing_phrases = [phrase for phrase in required_card_phrases if phrase not in card_text]
    if missing_phrases:
        raise AssertionError(f"model card missing rule-vs-auxiliary distinction: {missing_phrases}")
    sample_output = predict_postnatal_followup(
        {
            "prepregnancy_hypertension": 0,
            "gestational_hypertension": 1,
            "eclampsia": 0,
            "prepregnancy_diabetes": 0,
            "gestational_diabetes": 0,
            "maternal_transfusion": 0,
            "ruptured_uterus": 0,
            "unplanned_hysterectomy": 0,
            "maternal_icu": 0,
            "obstetric_estimate_gestation_weeks": 39,
            "birth_weight_grams": 3200,
            "abnormal_condition_nicu": 0,
        },
        output_dir,
    )
    if sample_output.get("routing_method") != ROUTING_METHOD:
        raise AssertionError("runtime inference is not labeled as deterministic rule routing")
    if sample_output.get("hypertension_followup_signal", {}).get("tier") != "high":
        raise AssertionError("runtime rule router failed gestational hypertension scenario")
    if sample_output.get("auxiliary_ml_scores", {}).get("runtime_decision_logic") != "not_used":
        raise AssertionError("runtime inference appears to use auxiliary ML")
    if any(key in sample_output for key in ["cardiovascular_risk_probability", "cvd_probability"]):
        raise AssertionError("runtime output exposes fake single CVD probability")


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    if args.check_only:
        validate_outputs(output_dir)
        print(f"checked_postnatal_followup_v1={output_dir}")
        return
    config = load_config(args.config)
    df_raw, source_path = load_source_data(config, args.data_path, args.max_rows)
    df = clean(df_raw)
    targets = labels(df)
    stratify_label = targets.any(axis=1).astype(int)
    train_idx, valid_idx, test_idx = split_indices(stratify_label)
    auxiliary = train_auxiliary_heads(df, targets, train_idx, valid_idx, test_idx)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config_payload = dict(config)
    config_payload["model_name"] = MODEL_NAME
    config_payload["model_version"] = MODEL_VERSION
    config_payload["model_mode"] = MODEL_MODE
    (output_dir / "postnatal_feature_config.yaml").write_text(yaml.safe_dump(config_payload, sort_keys=False))
    write_json(output_dir / "target_definitions.json", target_definitions())
    metrics_validation = metric_payload(targets, valid_idx, "validation", auxiliary)
    metrics_test = metric_payload(targets, test_idx, "test", auxiliary)
    metrics_rule_validation = metric_payload(targets, valid_idx, "validation")
    metrics_rule_test = metric_payload(targets, test_idx, "test")
    write_json(output_dir / "metrics_validation.json", metrics_validation)
    write_json(output_dir / "metrics_test.json", metrics_test)
    write_json(output_dir / "metrics_rule_validation.json", metrics_rule_validation)
    write_json(output_dir / "metrics_rule_test.json", metrics_rule_test)
    write_json(output_dir / "split_summary.json", split_summary(stratify_label, train_idx, valid_idx, test_idx))
    write_json(output_dir / "leakage_audit.json", leakage_audit(config))
    subgroup = subgroup_performance(df, targets, test_idx, auxiliary)
    subgroup.to_csv(output_dir / "subgroup_performance_postnatal_v1.csv", index=False)
    feature_importance(config, auxiliary).to_csv(output_dir / "feature_importance.csv", index=False)
    tier_outcomes(targets, test_idx).to_csv(output_dir / "tier_outcomes.csv", index=False)
    calibration_report(targets, valid_idx, test_idx, auxiliary).to_csv(output_dir / "calibration_curve.csv", index=False)
    sample_predictions(df, test_idx, output_dir).to_csv(output_dir / "sample_predictions.csv", index=False)
    write_docs(output_dir, config, source_path, metrics_test, subgroup)
    joblib.dump({signal: payload["model"] for signal, payload in auxiliary.items()}, output_dir / "model.joblib")
    joblib.dump({signal: payload["preprocessor"] for signal, payload in auxiliary.items()}, output_dir / "preprocessor.joblib")
    joblib.dump({signal: payload["calibrator"] for signal, payload in auxiliary.items()}, output_dir / "calibrator.joblib")
    joblib.dump(
        {
            signal: Pipeline([("preprocessor", payload["preprocessor"]), ("calibrator", payload["calibrator"])])
            for signal, payload in auxiliary.items()
        },
        output_dir / "combined_pipeline.joblib",
    )
    write_json(output_dir / "artifact_manifest.json", manifest(output_dir, source_path, config))
    validate_outputs(output_dir)
    print(f"postnatal_followup_v1_dir={output_dir}")


if __name__ == "__main__":
    main()
