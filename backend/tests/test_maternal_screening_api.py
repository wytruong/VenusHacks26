from typing import Any

from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas.screening import PostnatalFollowupRequest, PrenatalExpandedRequest

client = TestClient(app)


VALID_PRENATAL_EXPANDED_PAYLOAD = {
    "mother_age": "31",
    "mother_bmi": "28.4",
    "prior_live_births": "1",
    "previous_cesarean_count": 0,
    "prenatal_visits": "8",
    "prepregnancy_hypertension": True,
    "prepregnancy_diabetes": False,
    "previous_preterm_birth": False,
    "multiple_gestation_known_or_suspected": False,
}


VALID_POSTNATAL_FOLLOWUP_PAYLOAD = {
    "mother_age": "32",
    "mother_bmi": "29.1",
    "prior_live_births": "1",
    "obstetric_estimate_gestation_weeks": "39",
    "birth_weight_grams": "3200",
    "apgar_5_min": 8,
    "prenatal_visits": "10",
    "prepregnancy_hypertension": True,
    "prepregnancy_diabetes": False,
    "gestational_hypertension": False,
    "gestational_diabetes": False,
    "maternal_icu": False,
    "breastfed_at_discharge": True,
}


def test_prenatal_expanded_success(monkeypatch: Any) -> None:
    def fake_predict(payload: PrenatalExpandedRequest) -> dict[str, Any]:
        return {
            "model_mode": "prenatal_expanded",
            "model_name": "maternal_screening_prenatal_expanded",
            "model_version": "test-v1",
            "overall_followup_priority": "routine",
            "maternal_cv_metabolic_signal": {"score": 0.42, "tier": "moderate"},
            "obstetric_neonatal_signal": {"score": 0.31, "tier": "low"},
            "current_composite_signal": {"score": 0.38, "tier": "moderate"},
            "missing_inputs": [],
            "data_quality_warnings": [],
            "safety_note": "Model output is support-only.",
        }

    monkeypatch.setattr("backend.routers.screening.predict_prenatal_expanded_from_payload", fake_predict)

    response = client.post("/api/screening/prenatal-expanded", json=VALID_PRENATAL_EXPANDED_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) >= {
        "model_mode",
        "model_name",
        "model_version",
        "overall_followup_priority",
        "maternal_cv_metabolic_signal",
        "obstetric_neonatal_signal",
        "current_composite_signal",
        "missing_inputs",
        "data_quality_warnings",
        "safety_note",
    }


def test_postnatal_followup_success(monkeypatch: Any) -> None:
    def fake_predict(payload: PostnatalFollowupRequest) -> dict[str, Any]:
        return {
            "model_mode": "postnatal_followup",
            "model_name": "maternal_screening_postnatal_followup",
            "model_version": "test-v1",
            "routing_method": "rule_plus_ml",
            "overall_followup_priority": "high",
            "hypertension_followup_signal": {"score": 0.72, "tier": "high"},
            "diabetes_followup_signal": {"score": 0.25, "tier": "low"},
            "maternal_cv_metabolic_followup_signal": {"score": 0.68, "tier": "high"},
            "obstetric_neonatal_context_signal": {"score": 0.33, "tier": "moderate"},
            "severe_maternal_morbidity_followup_signal": {"score": 0.12, "tier": "low"},
            "auxiliary_ml_scores": {"xgb": 0.66},
            "context_flags": {"recent_delivery": True},
            "missing_inputs": [],
            "data_quality_warnings": [],
            "safety_note": "Model output is support-only.",
        }

    monkeypatch.setattr("backend.routers.screening.predict_postnatal_followup_from_payload", fake_predict)

    response = client.post("/api/screening/postnatal-followup", json=VALID_POSTNATAL_FOLLOWUP_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) >= {
        "model_mode",
        "model_name",
        "model_version",
        "routing_method",
        "overall_followup_priority",
        "hypertension_followup_signal",
        "diabetes_followup_signal",
        "maternal_cv_metabolic_followup_signal",
        "obstetric_neonatal_context_signal",
        "severe_maternal_morbidity_followup_signal",
        "auxiliary_ml_scores",
        "context_flags",
        "missing_inputs",
        "data_quality_warnings",
        "safety_note",
    }


def test_unknown_extra_fields_are_ignored_for_new_endpoints(monkeypatch: Any) -> None:
    def fake_prenatal(payload: PrenatalExpandedRequest) -> dict[str, Any]:
        return {"ok": True}

    def fake_postnatal(payload: PostnatalFollowupRequest) -> dict[str, Any]:
        return {"ok": True}

    monkeypatch.setattr("backend.routers.screening.predict_prenatal_expanded_from_payload", fake_prenatal)
    monkeypatch.setattr("backend.routers.screening.predict_postnatal_followup_from_payload", fake_postnatal)

    prenatal_response = client.post(
        "/api/screening/prenatal-expanded",
        json={**VALID_PRENATAL_EXPANDED_PAYLOAD, "unknown_field": "ignored"},
    )
    postnatal_response = client.post(
        "/api/screening/postnatal-followup",
        json={**VALID_POSTNATAL_FOLLOWUP_PAYLOAD, "another_unknown": 123},
    )

    assert prenatal_response.status_code == 200
    assert prenatal_response.json() == {"ok": True}
    assert postnatal_response.status_code == 200
    assert postnatal_response.json() == {"ok": True}


def test_invalid_numeric_field_returns_422_for_new_endpoints() -> None:
    prenatal_response = client.post(
        "/api/screening/prenatal-expanded",
        json={**VALID_PRENATAL_EXPANDED_PAYLOAD, "mother_age": "not-a-number"},
    )
    postnatal_response = client.post(
        "/api/screening/postnatal-followup",
        json={**VALID_POSTNATAL_FOLLOWUP_PAYLOAD, "birth_weight_grams": "abc"},
    )

    assert prenatal_response.status_code == 422
    assert postnatal_response.status_code == 422


def test_invalid_boolean_field_returns_422_for_new_endpoints() -> None:
    prenatal_response = client.post(
        "/api/screening/prenatal-expanded",
        json={**VALID_PRENATAL_EXPANDED_PAYLOAD, "prepregnancy_hypertension": "true"},
    )
    postnatal_response = client.post(
        "/api/screening/postnatal-followup",
        json={**VALID_POSTNATAL_FOLLOWUP_PAYLOAD, "gestational_diabetes": "false"},
    )

    assert prenatal_response.status_code == 422
    assert postnatal_response.status_code == 422


def test_prenatal_expanded_failure_returns_controlled_error(monkeypatch: Any) -> None:
    def fake_predict(payload: PrenatalExpandedRequest) -> dict[str, Any]:
        raise RuntimeError("/private/model/path failed")

    monkeypatch.setattr("backend.routers.screening.predict_prenatal_expanded_from_payload", fake_predict)

    response = client.post("/api/screening/prenatal-expanded", json=VALID_PRENATAL_EXPANDED_PAYLOAD)

    assert response.status_code == 503
    assert response.json() == {"detail": "Prenatal expanded screening model is unavailable."}
    assert "/private/model/path" not in response.text


def test_postnatal_followup_failure_returns_controlled_error(monkeypatch: Any) -> None:
    def fake_predict(payload: PostnatalFollowupRequest) -> dict[str, Any]:
        raise RuntimeError("/private/model/path failed")

    monkeypatch.setattr("backend.routers.screening.predict_postnatal_followup_from_payload", fake_predict)

    response = client.post("/api/screening/postnatal-followup", json=VALID_POSTNATAL_FOLLOWUP_PAYLOAD)

    assert response.status_code == 503
    assert response.json() == {"detail": "Postnatal follow-up model is unavailable."}
    assert "/private/model/path" not in response.text
