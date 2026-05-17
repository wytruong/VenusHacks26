from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AgentSurface = Literal["maternal_risk", "general_health_companion"]
AgentMessageRole = Literal["assistant", "system", "user"]


class AgentMessage(BaseModel):
    role: AgentMessageRole
    content: str = Field(min_length=1)


class AgentRuntimeContext(BaseModel):
    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(min_length=1)
    surface: AgentSurface
    user_id: str | None = None
    prenatal_risk_result: dict[str, Any] | None = None


class AgentInvocation(BaseModel):
    context: AgentRuntimeContext
    messages: list[AgentMessage] = Field(min_length=1)


class AgentRuntimeProfile(BaseModel):
    model: str
    provider: str
    subagent_names: list[str]
    subagent_tool_names: dict[str, list[str]]
    tool_names: list[str]


class AgentInvocationResult(BaseModel):
    assistant_text: str | None
    message_count: int
    profile: AgentRuntimeProfile
    thread_id: str
    raw: dict[str, Any] = Field(default_factory=dict)


def build_agent_thread_id(context: AgentRuntimeContext) -> str:
    principal_segment = f":user:{context.user_id}" if context.user_id else ""
    return f"vh:agent:{context.surface}:{context.session_id}{principal_segment}"
