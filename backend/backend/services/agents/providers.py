from dataclasses import dataclass

from langchain_openai import ChatOpenAI

from backend.services.agents.config import AgentConfigurationError, AgentRuntimeSettings

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENAI_BASE_URL = "https://api.openai.com/v1"


@dataclass(frozen=True)
class AgentProviderConfig:
    api_key: str
    base_url: str | None
    model: str
    provider: str
    timeout_seconds: float


def resolve_agent_provider_config(settings: AgentRuntimeSettings) -> AgentProviderConfig:
    provider = settings.agent_model_provider

    if provider == "openai":
        if not settings.openai_api_key:
            raise AgentConfigurationError("OPENAI_API_KEY is required for agent model provider.")
        return AgentProviderConfig(
            api_key=settings.openai_api_key,
            base_url=OPENAI_BASE_URL,
            model=settings.agent_model,
            provider=provider,
            timeout_seconds=settings.timeout_seconds,
        )

    if provider == "openrouter":
        if not settings.openrouter_api_key:
            raise AgentConfigurationError("OPENROUTER_API_KEY is required for agent model provider.")
        return AgentProviderConfig(
            api_key=settings.openrouter_api_key,
            base_url=OPENROUTER_BASE_URL,
            model=settings.agent_model,
            provider=provider,
            timeout_seconds=settings.timeout_seconds,
        )

    if provider == "openai_compatible":
        if not settings.agent_openai_compatible_api_key:
            raise AgentConfigurationError(
                "AGENT_OPENAI_COMPATIBLE_API_KEY is required for agent model provider."
            )
        if not settings.agent_openai_compatible_base_url:
            raise AgentConfigurationError(
                "AGENT_OPENAI_COMPATIBLE_BASE_URL is required for agent model provider."
            )
        base_url = str(settings.agent_openai_compatible_base_url).rstrip("/")
        if not base_url.startswith("https://"):
            raise AgentConfigurationError(
                "AGENT_OPENAI_COMPATIBLE_BASE_URL must use https."
            )
        return AgentProviderConfig(
            api_key=settings.agent_openai_compatible_api_key,
            base_url=base_url,
            model=settings.agent_model,
            provider=provider,
            timeout_seconds=settings.timeout_seconds,
        )

    raise AgentConfigurationError("Unsupported agent model provider.")


def create_agent_model(settings: AgentRuntimeSettings) -> ChatOpenAI:
    provider_config = resolve_agent_provider_config(settings)

    return ChatOpenAI(
        api_key=provider_config.api_key,
        base_url=provider_config.base_url,
        model=provider_config.model,
        temperature=0,
        timeout=provider_config.timeout_seconds,
    )
