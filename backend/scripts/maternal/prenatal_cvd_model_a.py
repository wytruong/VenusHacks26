"""Inference helpers for Prenatal CV-Risk Prioritization Model A."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_DIR = ROOT / "models/cdc-natality/default"
DEFAULT_FEATURES = [
    "mother_age",
    "mother_bmi",
    "prepregnancy_hypertension",
    "prepregnancy_diabetes",
    "prior_adverse_pregnancy_history",
    "prior_live_births",
    "smoking_before_or_during_pregnancy",
    "multiple_gestation_known_or_suspected",
]
FOLLOWUP_PRIORITY = {
    "low": "Routine prenatal health education.",
    "medium": "Enhanced counseling and follow-up planning signal.",
    "high": "Prioritized pregnancy follow-up risk review and postpartum planning.",
}
DISCLAIMER = (
    "This is a risk-prioritization aid, not a diagnosis. Clinical judgment should guide care decisions."
)
NO_DOMINANT_FACTOR = "No single dominant factor identified; score reflects the combined entered profile."


def load_artifacts(artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR) -> dict[str, Any]:
    artifact_dir = Path(artifact_dir)
    config_path = artifact_dir / "feature_config.yaml"
    config = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
    return {
        "preprocessor": joblib.load(artifact_dir / "preprocessor.joblib"),
        "calibrator": joblib.load(artifact_dir / "calibrator.joblib"),
        "thresholds": json.loads((artifact_dir / "thresholds.json").read_text()),
        "features": config.get("features", DEFAULT_FEATURES),
        "model_name": config.get("model_name", artifact_dir.name),
        "model_version": config.get("model_version", "unknown"),
    }


def risk_tier(probability: float, thresholds: dict[str, float]) -> str:
    if probability < thresholds["low"]:
        return "low"
    if probability < thresholds["high"]:
        return "medium"
    return "high"


def find_missing_inputs(patient_input: dict[str, Any], features: list[str] | None = None) -> list[str]:
    features = features or DEFAULT_FEATURES
    missing = []
    for feature in features:
        value = patient_input.get(feature)
        if value is None or (isinstance(value, float) and np.isnan(value)):
            missing.append(feature)
    return missing


def find_data_quality_warnings(patient_input: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    age = patient_input.get("mother_age")
    bmi = patient_input.get("mother_bmi")
    prior_live_births = patient_input.get("prior_live_births")
    if age is not None and not 10 <= float(age) <= 60:
        warnings.append("mother_age is outside the supported training range")
    if bmi is not None and not 12 <= float(bmi) <= 80:
        warnings.append("mother_bmi is outside the supported training range")
    if prior_live_births is not None and not 0 <= float(prior_live_births) <= 20:
        warnings.append("prior_live_births is outside the supported training range")
    return warnings


def explain_prediction(patient_input: dict[str, Any]) -> list[str]:
    factors: list[str] = []
    if patient_input.get("prepregnancy_hypertension"):
        factors.append("pre-pregnancy hypertension")
    if patient_input.get("prepregnancy_diabetes"):
        factors.append("pre-pregnancy diabetes")
    if patient_input.get("mother_bmi") is not None and float(patient_input["mother_bmi"]) >= 30:
        factors.append("higher pre-pregnancy BMI")
    if patient_input.get("mother_age") is not None and float(patient_input["mother_age"]) >= 35:
        factors.append("advanced maternal age")
    if patient_input.get("prior_adverse_pregnancy_history"):
        factors.append("prior adverse pregnancy history")
    if patient_input.get("smoking_before_or_during_pregnancy"):
        factors.append("smoking before or during pregnancy")
    if patient_input.get("multiple_gestation_known_or_suspected"):
        factors.append("multiple gestation")
    return factors[:4] or [NO_DOMINANT_FACTOR]


def predict_prenatal_cvd_risk(
    patient_input: dict[str, Any],
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
) -> dict[str, Any]:
    artifacts = load_artifacts(artifact_dir)
    features = artifacts["features"]
    x = pd.DataFrame([{feature: patient_input.get(feature) for feature in features}])
    transformed = artifacts["preprocessor"].transform(x)
    probability = float(artifacts["calibrator"].predict_proba(transformed)[0, 1])
    tier = risk_tier(probability, artifacts["thresholds"])
    factors = explain_prediction(patient_input)
    tier_interpretation = FOLLOWUP_PRIORITY[tier]
    return {
        "model_mode": "prenatal_after_ultrasound",
        "model_name": artifacts["model_name"],
        "model_version": artifacts["model_version"],
        "overall_followup_priority": tier,
        "tier_interpretation": tier_interpretation,
        "current_composite_signal": {
            "probability": round(probability, 5),
            "tier": tier,
            "use": "MVP default proxy follow-up priority only; not a cardiovascular disease probability.",
        },
        "risk_tier_note": "Risk tier is based on the unrounded model score.",
        "risk_tier": tier,
        "recommended_followup_priority": tier_interpretation,
        "main_contributing_factors": factors,
        "missing_inputs": find_missing_inputs(patient_input, features),
        "data_quality_warnings": find_data_quality_warnings(patient_input),
        "safety_note": DISCLAIMER,
        "disclaimer": DISCLAIMER,
    }
