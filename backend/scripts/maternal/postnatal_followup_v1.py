"""Inference helper for postnatal follow-up routing v1."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_DIR = ROOT / "models/cdc-natality/postnatal_followup_v1"
DEFAULT_CONFIG_PATH = ROOT / "configs/maternal/postnatal_followup_v1.yaml"
MODEL_MODE = "postnatal_followup"
ROUTING_METHOD = "deterministic_rule_router"
MODEL_NAME = "postnatal_followup_v1"
MODEL_VERSION = "2026-05-postnatal-v1.0"
SAFETY_NOTE = "This is a follow-up prioritization aid, not a diagnosis."
NO_DOMINANT_FACTOR = "No single dominant factor identified; signal reflects the combined entered profile."


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, float) and math.isnan(value)


def _num(patient_input: dict[str, Any], field: str) -> float | None:
    value = patient_input.get(field)
    if _is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(patient_input: dict[str, Any], field: str) -> bool:
    value = patient_input.get(field)
    if _is_missing(value):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def load_config(artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR) -> dict[str, Any]:
    artifact_dir = Path(artifact_dir)
    config_path = artifact_dir / "postnatal_feature_config.yaml"
    if config_path.exists():
        return yaml.safe_load(config_path.read_text())
    return yaml.safe_load(DEFAULT_CONFIG_PATH.read_text())


def find_missing_inputs(patient_input: dict[str, Any], config: dict[str, Any]) -> list[str]:
    required = (
        config["history_inputs"]
        + config["postnatal_clinical_facts"]
        + config["obstetric_neonatal_context"]
        + config["care_planning_only_fields"]
    )
    missing = [field for field in required if field not in patient_input or _is_missing(patient_input.get(field))]
    if not _is_missing(patient_input.get("mother_bmi")):
        missing = [field for field in missing if field not in {"mother_height_inches", "prepregnancy_weight_lb"}]
    elif not _is_missing(patient_input.get("mother_height_inches")) and not _is_missing(patient_input.get("prepregnancy_weight_lb")):
        missing = [field for field in missing if field != "mother_bmi"]
    if not _is_missing(patient_input.get("multiple_gestation_known_or_suspected")):
        missing = [field for field in missing if field != "plurality"]
    return missing


def find_data_quality_warnings(patient_input: dict[str, Any]) -> list[str]:
    ranges = [
        ("mother_age", 10, 60),
        ("mother_bmi", 12, 80),
        ("mother_height_inches", 48, 78),
        ("prepregnancy_weight_lb", 70, 500),
        ("delivery_weight_lb", 70, 700),
        ("weight_gain_lb", -50, 150),
        ("prior_live_births", 0, 20),
        ("prior_dead_births", 0, 20),
        ("prior_terminations", 0, 20),
        ("previous_cesarean_count", 0, 20),
        ("cigarettes_before_pregnancy", 0, 98),
        ("cigarettes_trimester_1", 0, 98),
        ("cigarettes_trimester_2", 0, 98),
        ("cigarettes_trimester_3", 0, 98),
        ("obstetric_estimate_gestation_weeks", 17, 47),
        ("birth_weight_grams", 100, 9000),
        ("apgar_5_min", 0, 10),
        ("apgar_10_min", 0, 10),
        ("prenatal_visits", 0, 60),
        ("month_prenatal_care_began", 0, 10),
    ]
    warnings: list[str] = []
    for field, low, high in ranges:
        value = _num(patient_input, field)
        if value is not None and not low <= value <= high:
            warnings.append(f"{field} is outside the supported data range")
    return warnings


def _bmi(patient_input: dict[str, Any]) -> float | None:
    bmi = _num(patient_input, "mother_bmi")
    if bmi is not None:
        return bmi
    height = _num(patient_input, "mother_height_inches")
    weight = _num(patient_input, "prepregnancy_weight_lb")
    if height and weight:
        return 703 * weight / (height**2)
    return None


def derived_context(patient_input: dict[str, Any]) -> dict[str, Any]:
    bmi = _bmi(patient_input)
    smoking_values = [
        _num(patient_input, "cigarettes_before_pregnancy") or 0,
        _num(patient_input, "cigarettes_trimester_1") or 0,
        _num(patient_input, "cigarettes_trimester_2") or 0,
        _num(patient_input, "cigarettes_trimester_3") or 0,
    ]
    prior_dead = _num(patient_input, "prior_dead_births") or 0
    plurality = _num(patient_input, "plurality")
    multiple = _bool(patient_input, "multiple_gestation_known_or_suspected") or bool(plurality and plurality > 1)
    return {
        "bmi_from_height_weight": bmi,
        "bmi_missing_flag": _is_missing(patient_input.get("mother_bmi")),
        "smoking_any": any(value > 0 for value in smoking_values),
        "smoking_intensity_latest_available_trimester": next((value for value in reversed(smoking_values) if value > 0), 0),
        "prior_adverse_pregnancy_history": _bool(patient_input, "previous_preterm_birth") or prior_dead > 0,
        "prior_preterm_or_dead_birth": _bool(patient_input, "previous_preterm_birth") or prior_dead > 0,
        "prior_cesarean_history": _bool(patient_input, "previous_cesarean") or (_num(patient_input, "previous_cesarean_count") or 0) > 0,
        "multiple_gestation": multiple,
        "low_or_normal_bmi": bmi is not None and bmi < 25,
    }


def signal_factors(patient_input: dict[str, Any], signal_name: str) -> list[str]:
    factors: list[str] = []
    labels = {
        "prepregnancy_hypertension": "pre-pregnancy hypertension",
        "gestational_hypertension": "gestational hypertension",
        "eclampsia": "eclampsia",
        "prepregnancy_diabetes": "pre-pregnancy diabetes",
        "gestational_diabetes": "gestational diabetes",
        "maternal_transfusion": "maternal transfusion",
        "ruptured_uterus": "ruptured uterus",
        "unplanned_hysterectomy": "unplanned hysterectomy",
        "maternal_icu": "maternal ICU admission",
        "abnormal_condition_nicu": "infant NICU admission",
        "previous_preterm_birth": "previous preterm birth",
        "previous_cesarean": "prior cesarean history",
        "risk_factor_infertility_treatment": "infertility treatment",
    }
    if signal_name in {"hypertension_followup_signal", "maternal_cv_metabolic_followup_signal"}:
        for field in ["prepregnancy_hypertension", "gestational_hypertension", "eclampsia"]:
            if _bool(patient_input, field):
                factors.append(labels[field])
    if signal_name in {"diabetes_followup_signal", "maternal_cv_metabolic_followup_signal"}:
        for field in ["prepregnancy_diabetes", "gestational_diabetes"]:
            if _bool(patient_input, field):
                factors.append(labels[field])
    if signal_name in {"severe_maternal_morbidity_followup_signal", "maternal_cv_metabolic_followup_signal"}:
        for field in ["maternal_transfusion", "ruptured_uterus", "unplanned_hysterectomy", "maternal_icu"]:
            if _bool(patient_input, field):
                factors.append(labels[field])
    if signal_name == "obstetric_neonatal_context_signal":
        gestation = _num(patient_input, "obstetric_estimate_gestation_weeks")
        birth_weight = _num(patient_input, "birth_weight_grams")
        if gestation is not None and gestation < 37:
            factors.append("preterm birth")
        if birth_weight is not None and birth_weight < 2500:
            factors.append("low birth weight")
        if _bool(patient_input, "abnormal_condition_nicu"):
            factors.append(labels["abnormal_condition_nicu"])
    return list(dict.fromkeys(factors))[:5] or [NO_DOMINANT_FACTOR]


def signal_payload(active: bool, patient_input: dict[str, Any], signal_name: str) -> dict[str, Any]:
    tier = "high" if active else "low"
    return {
        "present": bool(active),
        "tier": tier,
        "main_factors": signal_factors(patient_input, signal_name) if active else [],
    }


def predict_postnatal_followup(
    patient_input: dict[str, Any],
    artifact_dir: str | Path = DEFAULT_ARTIFACT_DIR,
) -> dict[str, Any]:
    config = load_config(artifact_dir)
    hypertension = _bool(patient_input, "prepregnancy_hypertension") or _bool(patient_input, "gestational_hypertension") or _bool(patient_input, "eclampsia")
    diabetes = _bool(patient_input, "prepregnancy_diabetes") or _bool(patient_input, "gestational_diabetes")
    severe = any(_bool(patient_input, field) for field in ["maternal_transfusion", "ruptured_uterus", "unplanned_hysterectomy", "maternal_icu"])
    gestation = _num(patient_input, "obstetric_estimate_gestation_weeks")
    birth_weight = _num(patient_input, "birth_weight_grams")
    neonatal = (gestation is not None and gestation < 37) or (birth_weight is not None and birth_weight < 2500) or _bool(patient_input, "abnormal_condition_nicu")
    maternal = hypertension or diabetes or severe
    context = derived_context(patient_input)
    medium_context = any(
        [
            context["prior_adverse_pregnancy_history"],
            context["prior_cesarean_history"],
            context["smoking_any"],
            context["multiple_gestation"],
            _bool(patient_input, "perineal_laceration"),
            _bool(patient_input, "risk_factor_infertility_treatment"),
        ]
    )
    if maternal or neonatal:
        overall = "high"
    elif medium_context:
        overall = "medium"
    else:
        overall = "low"
    return {
        "model_mode": MODEL_MODE,
        "model_name": config.get("model_name", MODEL_NAME),
        "model_version": config.get("model_version", MODEL_VERSION),
        "routing_method": ROUTING_METHOD,
        "overall_followup_priority": overall,
        "hypertension_followup_signal": signal_payload(hypertension, patient_input, "hypertension_followup_signal"),
        "diabetes_followup_signal": signal_payload(diabetes, patient_input, "diabetes_followup_signal"),
        "maternal_cv_metabolic_followup_signal": signal_payload(maternal, patient_input, "maternal_cv_metabolic_followup_signal"),
        "obstetric_neonatal_context_signal": signal_payload(neonatal, patient_input, "obstetric_neonatal_context_signal"),
        "severe_maternal_morbidity_followup_signal": signal_payload(severe, patient_input, "severe_maternal_morbidity_followup_signal"),
        "auxiliary_ml_scores": {
            "use": "diagnostic_only",
            "method": "auxiliary_lightgbm_ranking",
            "runtime_decision_logic": "not_used",
        },
        "context_flags": context,
        "missing_inputs": find_missing_inputs(patient_input, config),
        "data_quality_warnings": find_data_quality_warnings(patient_input),
        "safety_note": SAFETY_NOTE,
    }
