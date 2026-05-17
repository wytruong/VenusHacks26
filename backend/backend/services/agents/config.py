from typing import Literal

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

AgentModelProvider = Literal["openrouter", "openai", "openai_compatible"]


class AgentConfigurationError(RuntimeError):
    pass


class AgentRuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", populate_by_name=True, env_file=".env")

    agent_model_provider: AgentModelProvider = Field(
        default="openrouter", validation_alias="AGENT_MODEL_PROVIDER"
    )
    agent_model: str = Field(default="gpt-4.1-mini", validation_alias="AGENT_MODEL")
    agent_timeout_ms: int = Field(default=30_000, validation_alias="AGENT_TIMEOUT_MS", gt=0)
    openrouter_api_key: str | None = Field(default=None, validation_alias="OPENROUTER_API_KEY")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    agent_openai_compatible_api_key: str | None = Field(
        default=None, validation_alias="AGENT_OPENAI_COMPATIBLE_API_KEY"
    )
    agent_openai_compatible_base_url: HttpUrl | None = Field(
        default=None, validation_alias="AGENT_OPENAI_COMPATIBLE_BASE_URL"
    )

    @property
    def timeout_seconds(self) -> float:
        return self.agent_timeout_ms / 1000


def load_agent_runtime_settings() -> AgentRuntimeSettings:
    return AgentRuntimeSettings()
