import json
from typing import Any

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.agents.types import AgentInvocation, AgentInvocationResult, AgentRuntimeProfile

client = TestClient(app)

VALID_RECORD = {
    "demoId": "cv_001",
    "patientId": "patient-1",
    "visitOccurrenceId": "visit-1",
    "group": "cv_risk",
    "category": "hypertension",
    "age": "31",
    "conditionCodes": "O10",
    "noteDate": "2026-05-17",
    "noteTitle": "Translated prenatal note",
    "englishDemoNote": "31-year-old pregnant patient with chronic hypertension.",
    "extractedFactors": "hypertension",
    "summary": "Pregnant patient with hypertension.",
    "doctorQuestions": "What follow-up do I need?",
}


def make_payload(record: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"sessionId": "doctor-note-session-1", "record": record or VALID_RECORD}


class FakeRuntime:
    last_invocation: AgentInvocation | None = None

    def __init__(self, assistant_text: str) -> None:
        self.assistant_text = assistant_text

    def invoke(self, invocation: AgentInvocation) -> AgentInvocationResult:
        FakeRuntime.last_invocation = invocation
        return AgentInvocationResult(
            assistant_text=self.assistant_text,
            message_count=2,
            profile=AgentRuntimeProfile(
                model="fake-model",
                provider="openrouter",
                subagent_names=["doctor-note-screening-extractor"],
                subagent_tool_names={},
                tool_names=[],
            ),
            raw={},
            thread_id="vh:agent:doctor_note_screening:doctor-note-session-1",
        )


def extraction_json(**overrides: Any) -> str:
    payload: dict[str, Any] = {
        "screening_context": "none",
        "evidence": ["translated note evidence"],
        "summary": "No screening context found.",
        "prenatal_expanded_input": None,
        "postnatal_followup_input": None,
        "missing_or_uncertain_fields": [],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_prenatal_extraction_runs_validated_prenatal_screening(monkeypatch: Any) -> None:
    runtime = FakeRuntime(
        extraction_json(
            screening_context="prenatal",
            summary="Prenatal hypertension context.",
            prenatal_expanded_input={
                "mother_age": "31",
                "prepregnancy_hypertension": True,
            },
            missing_or_uncertain_fields=["mother_bmi"],
        )
    )
    captured_payload: dict[str, Any] = {}

    def fake_prenatal(payload: Any) -> dict[str, Any]:
        captured_payload.update(payload.model_dump(exclude_none=True, by_alias=False))
        return {
            "risk_tier": "high",
            "recommended_followup_priority": "High-priority prenatal follow-up",
            "missing_inputs": ["mother_bmi"],
        }

    monkeypatch.setattr("backend.services.doctor_note_screening.get_doctor_note_screening_runtime", lambda: runtime)
    monkeypatch.setattr(
        "backend.services.doctor_note_screening.predict_prenatal_expanded_from_payload",
        fake_prenatal,
    )

    response = client.post("/api/agents/doctor-note-screening", json=make_payload())

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["screeningContext"] == "prenatal"
    assert data["extractedInput"] == {
        "mother_age": 31.0,
        "prepregnancy_hypertension": True,
    }
    assert data["insight"]["riskLabel"] == "HIGH"
    assert captured_payload == data["extractedInput"]
    assert FakeRuntime.last_invocation is not None
    assert FakeRuntime.last_invocation.context.surface == "doctor_note_screening"
    assert FakeRuntime.last_invocation.context.doctor_note is not None
    assert "englishDemoNote" in FakeRuntime.last_invocation.context.doctor_note


def test_postnatal_extraction_runs_validated_postnatal_screening(monkeypatch: Any) -> None:
    runtime = FakeRuntime(
        extraction_json(
            screening_context="postnatal",
            summary="Postnatal delivery context.",
            postnatal_followup_input={
                "mother_age": "32",
                "gestational_hypertension": True,
                "birth_weight_grams": 2800,
            },
        )
    )
    captured_payload: dict[str, Any] = {}

    def fake_postnatal(payload: Any) -> dict[str, Any]:
        captured_payload.update(payload.model_dump(exclude_none=True, by_alias=False))
        return {
            "overall_followup_priority": "medium",
            "recommended_followup_priority": "Schedule postpartum follow-up",
        }

    monkeypatch.setattr("backend.services.doctor_note_screening.get_doctor_note_screening_runtime", lambda: runtime)
    monkeypatch.setattr(
        "backend.services.doctor_note_screening.predict_postnatal_followup_from_payload",
        fake_postnatal,
    )

    response = client.post("/api/agents/doctor-note-screening", json=make_payload())

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["screeningContext"] == "postnatal"
    assert data["extractedInput"] == {
        "mother_age": 32.0,
        "birth_weight_grams": 2800.0,
        "gestational_hypertension": True,
    }
    assert captured_payload == data["extractedInput"]


def test_no_context_does_not_run_screening_even_for_cv_group(monkeypatch: Any) -> None:
    runtime = FakeRuntime(
        extraction_json(
            screening_context="none",
            summary="The note does not mention prenatal or postnatal screening context.",
        )
    )

    def fail_screening(_payload: Any) -> dict[str, Any]:
        raise AssertionError("screening should not run")

    monkeypatch.setattr("backend.services.doctor_note_screening.get_doctor_note_screening_runtime", lambda: runtime)
    monkeypatch.setattr(
        "backend.services.doctor_note_screening.predict_prenatal_expanded_from_payload",
        fail_screening,
    )
    monkeypatch.setattr(
        "backend.services.doctor_note_screening.predict_postnatal_followup_from_payload",
        fail_screening,
    )

    response = client.post("/api/agents/doctor-note-screening", json=make_payload())

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "no_screening_context"
    assert data["screeningContext"] == "none"
    assert data["riskResult"] is None


def test_invalid_agent_json_returns_extraction_failed(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        "backend.services.doctor_note_screening.get_doctor_note_screening_runtime",
        lambda: FakeRuntime("not-json"),
    )

    response = client.post("/api/agents/doctor-note-screening", json=make_payload())

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "extraction_failed"
    assert data["insight"]["summary"] == "The agent could not extract a validated screening payload from this note."


def test_runtime_failure_returns_controlled_error(monkeypatch: Any) -> None:
    class FailingRuntime:
        def invoke(self, invocation: AgentInvocation) -> AgentInvocationResult:
            raise RuntimeError("/private/provider/config failed")

    monkeypatch.setattr("backend.services.doctor_note_screening.get_doctor_note_screening_runtime", lambda: FailingRuntime())

    response = client.post("/api/agents/doctor-note-screening", json=make_payload())

    assert response.status_code == 503
    assert response.json() == {"detail": "Doctor-note screening service is unavailable."}


def test_blank_session_or_note_returns_validation_error() -> None:
    assert client.post(
        "/api/agents/doctor-note-screening",
        json={**make_payload(), "sessionId": "   "},
    ).status_code == 422

    record = {**VALID_RECORD, "englishDemoNote": ""}
    assert client.post(
        "/api/agents/doctor-note-screening",
        json=make_payload(record),
    ).status_code == 422
