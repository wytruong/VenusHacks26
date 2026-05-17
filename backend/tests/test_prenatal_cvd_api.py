from typing import Any

from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas.screening import PrenatalCvdRequest
from backend.services.prenatal_cvd import to_model_input

client = TestClient(app)


VALID_PAYLOAD = {
    "pregnancyMode": "prenatal",
    "age": "35",
    "prepregnancyBmi": "32.0",
    "chronicHypertension": True,
    "diabetes": False,
    "priorPretermOrStillbirth": True,
    "liveBirthsCount": "1",
    "smokedPregnancy": False,
    "multipleGestation": False,
}


def test_health_route() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "venus-hacks-backend"}


def test_frontend_payload_maps_to_model_input() -> None:
    payload = PrenatalCvdRequest.model_validate(VALID_PAYLOAD)

    assert to_model_input(payload) == {
        "mother_age": 35.0,
        "mother_bmi": 32.0,
        "prepregnancy_hypertension": 1,
        "prepregnancy_diabetes": 0,
        "prior_adverse_pregnancy_history": 1,
        "prior_live_births": 1,
        "smoking_before_or_during_pregnancy": 0,
        "multiple_gestation_known_or_suspected": 0,
        "previous_preterm_birth": 1,
    }


def test_prenatal_endpoint_returns_model_shape(monkeypatch: Any) -> None:
    def fake_predict(payload: PrenatalCvdRequest) -> dict[str, Any]:
        return {
            "model_mode": "prenatal_after_ultrasound",
            "risk_tier": "high",
            "recommended_followup_priority": "Prioritized pregnancy follow-up risk review and postpartum planning.",
            "main_contributing_factors": ["pre-pregnancy hypertension"],
            "current_composite_signal": {"probability": 0.81234, "tier": "high"},
            "prenatal_cvd_followup_proxy_probability": 0.81234,
        }

    monkeypatch.setattr("backend.routers.screening.predict_from_frontend_payload", fake_predict)

    response = client.post("/api/screening/prenatal-cvd", json=VALID_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["risk_tier"] == "high"
    assert body["recommended_followup_priority"]
    assert body["main_contributing_factors"] == ["pre-pregnancy hypertension"]
    assert body["current_composite_signal"]["probability"] == 0.81234
    assert body["prenatal_cvd_followup_proxy_probability"] == 0.81234


def test_postpartum_mode_is_rejected() -> None:
    response = client.post(
        "/api/screening/prenatal-cvd",
        json={**VALID_PAYLOAD, "pregnancyMode": "postpartum"},
    )

    assert response.status_code == 422


def test_null_boolean_is_rejected() -> None:
    response = client.post(
        "/api/screening/prenatal-cvd",
        json={**VALID_PAYLOAD, "chronicHypertension": None},
    )

    assert response.status_code == 422


def test_non_numeric_input_is_rejected() -> None:
    response = client.post(
        "/api/screening/prenatal-cvd",
        json={**VALID_PAYLOAD, "age": "not-a-number"},
    )

    assert response.status_code == 422


def test_model_failure_returns_controlled_error(monkeypatch: Any) -> None:
    def fake_predict(payload: PrenatalCvdRequest) -> dict[str, Any]:
        raise RuntimeError("/private/model/path failed")

    monkeypatch.setattr("backend.routers.screening.predict_from_frontend_payload", fake_predict)

    response = client.post("/api/screening/prenatal-cvd", json=VALID_PAYLOAD)

    assert response.status_code == 503
    assert response.json() == {"detail": "Prenatal screening model is unavailable."}


def test_cors_preflight_allows_local_vite_origin() -> None:
    response = client.options(
        "/api/screening/prenatal-cvd",
        headers={
            "Origin": "http://localhost:45260",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, X-Request-ID",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:45260"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "Content-Type" in response.headers["access-control-allow-headers"]
    assert "X-Request-ID" in response.headers["access-control-allow-headers"]


def test_cors_preflight_rejects_unapproved_origin() -> None:
    response = client.options(
        "/api/screening/prenatal-cvd",
        headers={
            "Origin": "http://127.0.0.1:45261",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, X-Request-ID",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
