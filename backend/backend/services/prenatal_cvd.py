from typing import Any

from backend.schemas.screening import PrenatalCvdRequest


def to_model_input(payload: PrenatalCvdRequest) -> dict[str, Any]:
    return {
        "mother_age": payload.age,
        "mother_bmi": payload.prepregnancy_bmi,
        "prepregnancy_hypertension": int(payload.chronic_hypertension),
        "prepregnancy_diabetes": int(payload.diabetes),
        "prior_adverse_pregnancy_history": int(payload.prior_preterm_or_stillbirth),
        "prior_live_births": payload.live_births_count,
        "smoking_before_or_during_pregnancy": int(payload.smoked_pregnancy),
        "multiple_gestation_known_or_suspected": int(payload.multiple_gestation),
    }


def predict_from_frontend_payload(payload: PrenatalCvdRequest) -> dict[str, Any]:
    from scripts.maternal.prenatal_cvd_model_a import predict_prenatal_cvd_risk

    result = predict_prenatal_cvd_risk(to_model_input(payload))
    probability = result.get("current_composite_signal", {}).get("probability")
    return {**result, "prenatal_cvd_followup_proxy_probability": probability}
