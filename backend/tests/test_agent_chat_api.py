import time
from typing import Any

from fastapi.testclient import TestClient

from backend.main import app
from backend.services.agents.types import AgentInvocation, AgentInvocationResult, AgentRuntimeProfile

client = TestClient(app)


VALID_PAYLOAD = {
    "sessionId": "doctor-note-session-1",
    "surface": "general_health_companion",
    "doctorNote": {
        "condition": "Hypertension",
        "region": "Left Ventricle",
        "risk": "HIGH",
        "description": "Blood pressure is elevated during pregnancy.",
        "doctorScript": "I want to discuss my blood pressure and heart health.",
        "questions": ["What range is safe?"],
    },
    "messages": [{"role": "user", "content": "What does this mean?"}],
}


class FakeRuntime:
    last_invocation: AgentInvocation | None = None

    def invoke(self, invocation: AgentInvocation) -> AgentInvocationResult:
        FakeRuntime.last_invocation = invocation
        return AgentInvocationResult(
            assistant_text="Please review this with your OB or clinician.",
            message_count=2,
            profile=AgentRuntimeProfile(
                model="fake-model",
                provider="openrouter",
                subagent_names=[],
                subagent_tool_names={},
                tool_names=[],
            ),
            raw={},
            thread_id="vh:agent:general_health_companion:doctor-note-session-1",
        )


def test_agent_chat_route_invokes_runtime_with_doctor_note_context(monkeypatch: Any) -> None:
    runtime = FakeRuntime()
    monkeypatch.setattr("backend.services.agent_chat.get_agent_chat_runtime", lambda: runtime)

    response = client.post("/api/agents/chat", json=VALID_PAYLOAD)

    assert response.status_code == 200
    assert response.json() == {
        "assistantText": "Please review this with your OB or clinician.",
        "messageCount": 2,
        "threadId": "vh:agent:general_health_companion:doctor-note-session-1",
    }
    assert FakeRuntime.last_invocation is not None
    assert FakeRuntime.last_invocation.context.surface == "general_health_companion"
    assert FakeRuntime.last_invocation.context.session_id == "doctor-note-session-1"
    assert FakeRuntime.last_invocation.messages[0].role == "system"
    assert "Hypertension" in FakeRuntime.last_invocation.messages[0].content
    assert FakeRuntime.last_invocation.messages[1].role == "user"
    assert FakeRuntime.last_invocation.messages[1].content == "What does this mean?"


def test_agent_chat_rejects_blank_message() -> None:
    response = client.post(
        "/api/agents/chat",
        json={**VALID_PAYLOAD, "messages": [{"role": "user", "content": "   "}]},
    )

    assert response.status_code == 422


def test_agent_chat_timeout_returns_controlled_error(monkeypatch: Any) -> None:
    def slow_chat(payload: Any, request_id: str = "missing") -> None:
        time.sleep(0.1)

    monkeypatch.setattr("backend.routers.agents.AGENT_CHAT_ROUTE_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr("backend.routers.agents.chat_with_agent", slow_chat)

    response = client.post("/api/agents/chat", json=VALID_PAYLOAD)

    assert response.status_code == 503
    assert response.json() == {"detail": "Agent chat service is unavailable."}



def test_agent_chat_runtime_failure_returns_controlled_error(monkeypatch: Any) -> None:
    class FailingRuntime:
        def invoke(self, invocation: AgentInvocation) -> AgentInvocationResult:
            raise RuntimeError("/private/provider/config failed")

    monkeypatch.setattr("backend.services.agent_chat.get_agent_chat_runtime", lambda: FailingRuntime())

    response = client.post("/api/agents/chat", json=VALID_PAYLOAD)

    assert response.status_code == 503
    assert response.json() == {"detail": "Agent chat service is unavailable."}
