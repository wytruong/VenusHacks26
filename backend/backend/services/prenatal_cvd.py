import logging
from pathlib import Path
from typing import Any

from backend.schemas.screening import PrenatalCvdRequest

logger = logging.getLogger(__name__)

_PRENATAL_EXPANDED_ARTIFACT_DIR = (
    Path(__file__).resolve().parents[2]
    / "models"
    / "cdc-natality"
    / "prenatal_expanded_screening_v3_1_timing_safe"
)

FOLLOWUP_PRIORITY = {
    "low": "Routine prenatal health education.",
    "medium": "Enhanced counseling and follow-up planning signal.",
    "high": "Prioritized pregnancy follow-up risk review and postpartum planning.",
}


def to_model_input(payload: PrenatalCvdRequest) -> dict[str, Any]:
    prior_adverse_history = int(payload.prior_preterm_or_stillbirth)

    return {
        "mother_age": payload.age,
        "mother_bmi": payload.prepregnancy_bmi,
        "prepregnancy_hypertension": int(payload.chronic_hypertension),
        "prepregnancy_diabetes": int(payload.diabetes),
        "prior_adverse_pregnancy_history": prior_adverse_history,
        "prior_live_births": payload.live_births_count,
        "smoking_before_or_during_pregnancy": int(payload.smoked_pregnancy),
        "multiple_gestation_known_or_suspected": int(payload.multiple_gestation),
        "previous_preterm_birth": prior_adverse_history,
    }


def _main_factors(result: dict[str, Any]) -> list[str]:
    factors: list[str] = []
    for signal_name in ("maternal_cv_metabolic_signal", "obstetric_neonatal_signal"):
        signal = result.get(signal_name)
        if not isinstance(signal, dict):
            continue
        signal_factors = signal.get("main_factors")
        if isinstance(signal_factors, list):
            factors.extend(factor for factor in signal_factors if isinstance(factor, str))
    return list(dict.fromkeys(factors))


def predict_from_frontend_payload(payload: PrenatalCvdRequest) -> dict[str, Any]:
    from scripts.maternal.prenatal_expanded_screening_v3_1_timing_safe import (
        predict_prenatal_expanded_screening_v3_1_timing_safe,
    )

    logger.info(
        "Running prenatal CVD adapter with v3.1 expanded model artifacts at %s",
        _PRENATAL_EXPANDED_ARTIFACT_DIR,
    )
    result = predict_prenatal_expanded_screening_v3_1_timing_safe(
        to_model_input(payload),
        str(_PRENATAL_EXPANDED_ARTIFACT_DIR),
    )
    current_signal = result.get("current_composite_signal")
    probability = current_signal.get("probability") if isinstance(current_signal, dict) else None
    risk_tier = str(result.get("overall_followup_priority") or result.get("risk_tier") or "medium")
    factors = _main_factors(result)
    logger.info(
        "Prenatal CVD adapter completed with model_mode=%s model_version=%s risk_tier=%s probability=%s factor_count=%s",
        result.get("model_mode"),
        result.get("model_version"),
        risk_tier,
        probability,
        len(factors),
    )

    return {
        **result,
        "risk_tier": risk_tier,
        "recommended_followup_priority": FOLLOWUP_PRIORITY.get(risk_tier, FOLLOWUP_PRIORITY["medium"]),
        "main_contributing_factors": factors,
        "prenatal_cvd_followup_proxy_probability": probability,
        "disclaimer": result.get("safety_note"),
    }
