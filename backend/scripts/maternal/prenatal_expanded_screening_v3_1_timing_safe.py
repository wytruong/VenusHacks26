"""Inference helpers for prenatal expanded screening v3.1 timing-safe."""

from __future__ import annotations

import math
import warnings
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import yaml

from scripts.maternal.train_prenatal_expanded_screening_v3_1_timing_safe import (
    CARE_PLANNING_ONLY_FIELDS,
    DEFAULT_OUTPUT_DIR,
    FEATURES,
    HEADS,
    MODEL_NAME,
    MODEL_VERSION,
    SAFETY_NOTE,
    clean_and_derive_features,
)

warnings.filterwarnings("ignore", message="X does not have valid feature names.*", category=UserWarning)


MODEL_MODE = "prenatal_expanded_screening"
REFERENCE_HEAD = "current_composite_signal"
PRIMARY_HEADS = ["maternal_cv_metabolic_signal", "obstetric_neonatal_signal"]
NO_DOMINANT_FACTOR = "No single dominant factor identified; score reflects the combined entered profile."

DIRECT_SCREENING_INPUTS = [
    "mother_age",
    "mother_bmi",
    "mother_height_inches",
    "prepregnancy_weight_lb",
    "prepregnancy_hypertension",
    "prepregnancy_diabetes",
    "prior_live_births",
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
    "multiple_gestation_known_or_suspected",
]
CARE_PLANNING_INPUTS = CARE_PLANNING_ONLY_FIELDS


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return False


def load_artifacts(artifact_dir: str | Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    artifact_dir = Path(artifact_dir)
    config = yaml.safe_load((artifact_dir / "expanded_feature_config.yaml").read_text())
    thresholds = pd.read_csv(artifact_dir / "threshold_strategy_summary.csv").set_index("head_name").to_dict("index")
    return {
        "pipelines": joblib.load(artifact_dir / "combined_pipeline.joblib"),
        "thresholds": thresholds,
        "features": config["features"],
        "model_name": config.get("model_name", MODEL_NAME),
        "model_version": config.get("model_version", MODEL_VERSION),
    }


def risk_tier(probability: float, thresholds: dict[str, Any]) -> str:
    if probability < float(thresholds["low_threshold"]):
        return "low"
    if probability < float(thresholds["high_threshold"]):
        return "medium"
    return "high"


def overall_priority(signal_tiers: dict[str, str]) -> str:
    if any(signal_tiers[head] == "high" for head in PRIMARY_HEADS):
        return "high"
    if any(signal_tiers[head] == "medium" for head in PRIMARY_HEADS):
        return "medium"
    return "low"


def find_missing_inputs(patient_input: dict[str, Any]) -> list[str]:
    missing = [feature for feature in DIRECT_SCREENING_INPUTS if _is_missing(patient_input.get(feature))]
    if not _is_missing(patient_input.get("plurality")):
        missing = [feature for feature in missing if feature != "multiple_gestation_known_or_suspected"]
    if not _is_missing(patient_input.get("mother_bmi")):
        missing = [feature for feature in missing if feature not in {"mother_height_inches", "prepregnancy_weight_lb"}]
    elif not _is_missing(patient_input.get("mother_height_inches")) and not _is_missing(patient_input.get("prepregnancy_weight_lb")):
        missing = [feature for feature in missing if feature != "mother_bmi"]
    return missing


def find_data_quality_warnings(patient_input: dict[str, Any]) -> list[str]:
    checks = [
        ("mother_age", 10, 60),
        ("mother_bmi", 12, 80),
        ("mother_height_inches", 48, 78),
        ("prepregnancy_weight_lb", 70, 500),
        ("prior_live_births", 0, 20),
        ("prior_dead_births", 0, 20),
        ("previous_cesarean_count", 0, 20),
        ("cigarettes_before_pregnancy", 0, 98),
        ("cigarettes_trimester_1", 0, 98),
        ("cigarettes_trimester_2", 0, 98),
        ("month_prenatal_care_began", 0, 10),
        ("prenatal_visits", 0, 60),
        ("cigarettes_trimester_3", 0, 98),
    ]
    warnings: list[str] = []
    for feature, low, high in checks:
        value = patient_input.get(feature)
        if _is_missing(value):
            continue
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            warnings.append(f"{feature} is not numeric")
            continue
        if numeric_value < low or numeric_value > high:
            warnings.append(f"{feature} is outside the supported training range")
    return warnings


def _model_frame(patient_input: dict[str, Any]) -> pd.DataFrame:
    row = dict(patient_input)
    if "plurality" not in row and not _is_missing(row.get("multiple_gestation_known_or_suspected")):
        row["plurality"] = 2 if int(row["multiple_gestation_known_or_suspected"]) == 1 else 1
    for target_only in [
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
    ]:
        row.setdefault(target_only, np.nan)
    for feature in FEATURES:
        row.setdefault(feature, np.nan)
    row.setdefault("plurality", np.nan)
    derived = clean_and_derive_features(pd.DataFrame([row]))
    return derived[FEATURES]


def explain_signal(patient_input: dict[str, Any], signal_name: str) -> list[str]:
    factors: list[str] = []
    if patient_input.get("prepregnancy_hypertension"):
        factors.append("pre-pregnancy hypertension")
    if patient_input.get("prepregnancy_diabetes"):
        factors.append("pre-pregnancy diabetes")
    bmi = patient_input.get("mother_bmi")
    if _is_missing(bmi) and not _is_missing(patient_input.get("mother_height_inches")) and not _is_missing(patient_input.get("prepregnancy_weight_lb")):
        bmi = 703 * float(patient_input["prepregnancy_weight_lb"]) / (float(patient_input["mother_height_inches"]) ** 2)
    if not _is_missing(bmi) and float(bmi) >= 30:
        factors.append("higher pre-pregnancy BMI")
    if not _is_missing(patient_input.get("mother_age")) and float(patient_input["mother_age"]) >= 35:
        factors.append("maternal age 35 or older")
    if patient_input.get("previous_preterm_birth"):
        factors.append("previous preterm birth")
    if not _is_missing(patient_input.get("prior_dead_births")) and float(patient_input["prior_dead_births"]) > 0:
        factors.append("prior dead birth")
    if patient_input.get("previous_cesarean") or (
        not _is_missing(patient_input.get("previous_cesarean_count")) and float(patient_input["previous_cesarean_count"]) > 0
    ):
        factors.append("prior cesarean history")
    if any(float(patient_input.get(field) or 0) > 0 for field in ["cigarettes_before_pregnancy", "cigarettes_trimester_1", "cigarettes_trimester_2"]):
        factors.append("smoking before or during pregnancy")
    if patient_input.get("multiple_gestation_known_or_suspected") or float(patient_input.get("plurality") or 1) > 1:
        factors.append("multiple gestation")
    if patient_input.get("risk_factor_infertility_treatment"):
        factors.append("infertility treatment")
    if signal_name == "obstetric_neonatal_signal":
        preferred = ["previous preterm birth", "prior dead birth", "multiple gestation", "smoking before or during pregnancy"]
        factors = [factor for factor in factors if factor in preferred] + [factor for factor in factors if factor not in preferred]
    return list(dict.fromkeys(factors))[:4] or [NO_DOMINANT_FACTOR]


def predict_prenatal_expanded_screening(
    patient_input: dict[str, Any],
    artifact_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    artifacts = load_artifacts(artifact_dir)
    x = _model_frame(patient_input)
    signals: dict[str, dict[str, Any]] = {}
    tiers: dict[str, str] = {}
    for head_name in HEADS:
        probability = float(artifacts["pipelines"][head_name].predict_proba(x)[0, 1])
        tier = risk_tier(probability, artifacts["thresholds"][head_name])
        tiers[head_name] = tier
        signal = {"probability": round(probability, 5), "tier": tier}
        if head_name == REFERENCE_HEAD:
            signal["use"] = "reference only"
        else:
            signal["main_factors"] = explain_signal(patient_input, head_name)
        signals[head_name] = signal
    return {
        "model_mode": MODEL_MODE,
        "model_name": artifacts["model_name"],
        "model_version": artifacts["model_version"],
        "overall_followup_priority": overall_priority(tiers),
        "maternal_cv_metabolic_signal": signals["maternal_cv_metabolic_signal"],
        "obstetric_neonatal_signal": signals["obstetric_neonatal_signal"],
        "current_composite_signal": signals["current_composite_signal"],
        "missing_inputs": find_missing_inputs(patient_input),
        "data_quality_warnings": find_data_quality_warnings(patient_input),
        "safety_note": SAFETY_NOTE,
    }


def predict_prenatal_expanded_screening_v3_1_timing_safe(
    patient_input: dict[str, Any],
    artifact_dir: str | Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    return predict_prenatal_expanded_screening(patient_input, artifact_dir)
