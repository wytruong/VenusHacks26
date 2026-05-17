from typing import Any

import pytest
from langchain_core.messages import AIMessage

from backend.services.agents.config import AgentConfigurationError, AgentRuntimeSettings
from backend.services.agents.providers import (
    OPENAI_BASE_URL,
    OPENROUTER_BASE_URL,
    create_agent_model,
    resolve_agent_provider_config,
)
from backend.services.agents.runtime import create_venus_agent_runtime
from backend.services.agents.subagents import create_agent_subagents, profile_subagent_tool_names
from backend.services.agents.tools import create_agent_tools
from backend.services.agents.types import (
    AgentInvocation,
    AgentMessage,
    AgentRuntimeContext,
    build_agent_thread_id,
)


def make_settings(**overrides: Any) -> AgentRuntimeSettings:
    defaults: dict[str, Any] = {
        "agent_model": "test-model",
        "agent_model_provider": "openrouter",
        "agent_timeout_ms": 12_000,
        "openrouter_api_key": "openrouter-key",
    }
    defaults.update(overrides)
    return AgentRuntimeSettings(**defaults)


def test_openrouter_provider_config_resolves_base_url() -> None:
    config = resolve_agent_provider_config(make_settings())

    assert config.provider == "openrouter"
    assert config.model == "test-model"
    assert config.api_key == "openrouter-key"
    assert config.base_url == OPENROUTER_BASE_URL
    assert config.timeout_seconds == 12


def test_openai_provider_config_resolves_base_url() -> None:
    config = resolve_agent_provider_config(
        make_settings(
            agent_model_provider="openai",
            openai_api_key="openai-key",
            openrouter_api_key=None,
        )
    )

    assert config.provider == "openai"
    assert config.api_key == "openai-key"
    assert config.base_url == OPENAI_BASE_URL


def test_openai_compatible_provider_config_requires_https_base_url() -> None:
    config = resolve_agent_provider_config(
        make_settings(
            agent_model_provider="openai_compatible",
            agent_openai_compatible_api_key="compatible-key",
            agent_openai_compatible_base_url="https://llm.example.test/v1",
            openrouter_api_key=None,
        )
    )

    assert config.provider == "openai_compatible"
    assert config.api_key == "compatible-key"
    assert config.base_url == "https://llm.example.test/v1"


def test_missing_provider_secret_raises_safe_configuration_error() -> None:
    with pytest.raises(AgentConfigurationError, match="OPENROUTER_API_KEY is required"):
        resolve_agent_provider_config(make_settings(openrouter_api_key=None))


def test_model_factory_passes_provider_settings_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class FakeChatOpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("backend.services.agents.providers.ChatOpenAI", FakeChatOpenAI)

    model = create_agent_model(make_settings(agent_model="provider-model", agent_timeout_ms=45_000))

    assert isinstance(model, FakeChatOpenAI)
    assert captured == {
        "api_key": "openrouter-key",
        "base_url": OPENROUTER_BASE_URL,
        "model": "provider-model",
        "temperature": 0,
        "timeout": 45,
    }


def test_thread_id_is_deterministic_and_omits_missing_user() -> None:
    assert (
        build_agent_thread_id(
            AgentRuntimeContext(session_id="session-1", surface="maternal_risk", user_id="user-1")
        )
        == "vh:agent:maternal_risk:session-1:user:user-1"
    )
    assert (
        build_agent_thread_id(
            AgentRuntimeContext(session_id="session-1", surface="general_health_companion")
        )
        == "vh:agent:general_health_companion:session-1"
    )


def test_tool_registry_exposes_safe_non_mutating_tools() -> None:
    tools = create_agent_tools(AgentRuntimeContext(session_id="session-1", surface="maternal_risk"))

    assert [registered_tool.name for registered_tool in tools] == [
        "get_prenatal_model_context",
        "summarize_prenatal_risk_result",
        "get_supported_backend_capabilities",
    ]
    assert not any(name.startswith(("run_", "submit_", "delete_")) for name in [tool.name for tool in tools])


def test_subagent_allowlists_are_exact() -> None:
    tools = create_agent_tools(AgentRuntimeContext(session_id="session-1", surface="maternal_risk"))
    subagents = create_agent_subagents(tools)

    assert [subagent["name"] for subagent in subagents] == [
        "prenatal-risk-explainer",
        "care-navigation-guide",
    ]
    assert profile_subagent_tool_names(subagents) == {
        "prenatal-risk-explainer": [
            "get_prenatal_model_context",
            "summarize_prenatal_risk_result",
        ],
        "care-navigation-guide": [
            "get_supported_backend_capabilities",
            "get_prenatal_model_context",
        ],
    }


class FakeAgent:
    last_config: dict[str, Any] | None = None
    last_input: dict[str, Any] | None = None

    def invoke(self, input_payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        FakeAgent.last_input = input_payload
        FakeAgent.last_config = config
        return {"messages": [*input_payload["messages"], AIMessage(content="Runtime ready.")]}


def test_runtime_invocation_reports_profile_and_thread_id() -> None:
    factory_kwargs: dict[str, Any] = {}

    def fake_agent_factory(**kwargs: Any) -> FakeAgent:
        factory_kwargs.update(kwargs)
        return FakeAgent()

    runtime = create_venus_agent_runtime(
        agent_factory=fake_agent_factory,
        model=object(),
        settings=make_settings(agent_model="fake-model"),
    )
    result = runtime.invoke(
        AgentInvocation(
            context=AgentRuntimeContext(
                session_id="session-runtime",
                surface="maternal_risk",
                prenatal_risk_result={
                    "risk_tier": "high",
                    "main_contributing_factors": ["pre-pregnancy hypertension"],
                },
            ),
            messages=[AgentMessage(role="user", content="Explain the result.")],
        )
    )

    assert result.assistant_text == "Runtime ready."
    assert result.message_count == 2
    assert result.thread_id == "vh:agent:maternal_risk:session-runtime"
    assert FakeAgent.last_config == {"configurable": {"thread_id": result.thread_id}}
    assert factory_kwargs["name"] == "venus-maternal_risk"
    assert result.profile.provider == "openrouter"
    assert result.profile.model == "fake-model"
    assert result.profile.tool_names == [
        "get_prenatal_model_context",
        "summarize_prenatal_risk_result",
        "get_supported_backend_capabilities",
    ]
    assert result.profile.subagent_names == [
        "prenatal-risk-explainer",
        "care-navigation-guide",
    ]
