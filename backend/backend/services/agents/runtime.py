from collections.abc import Callable
from typing import Any

from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from backend.services.agents.config import AgentRuntimeSettings, load_agent_runtime_settings
from backend.services.agents.providers import create_agent_model
from backend.services.agents.subagents import create_agent_subagents, profile_subagent_tool_names
from backend.services.agents.tools import create_agent_tools
from backend.services.agents.types import (
    AgentInvocation,
    AgentInvocationResult,
    AgentMessage,
    AgentRuntimeProfile,
    build_agent_thread_id,
)

AgentFactory = Callable[..., Any]

SYSTEM_PROMPT = (
    "You are the VenusHacks maternal cardiac health companion runtime. Use only the registered "
    "tools and subagents. Treat the prenatal model as a follow-up prioritization aid, not a "
    "diagnosis. Do not add postpartum model behavior or invent unsupported backend capabilities."
)


def _to_langchain_messages(messages: list[AgentMessage]) -> list[BaseMessage]:
    converted: list[BaseMessage] = []
    for message in messages:
        if message.role == "assistant":
            converted.append(AIMessage(content=message.content))
        elif message.role == "system":
            converted.append(SystemMessage(content=message.content))
        else:
            converted.append(HumanMessage(content=message.content))
    return converted


def _message_text(message: BaseMessage | None) -> str | None:
    if message is None:
        return None
    content = message.content
    if isinstance(content, str):
        return content or None
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        text = "\n".join(part for part in parts if part).strip()
        return text or None
    return None


class VenusAgentRuntime:
    def __init__(
        self,
        *,
        agent_factory: AgentFactory = create_deep_agent,
        checkpointer: Any | None = None,
        model: Any | None = None,
        settings: AgentRuntimeSettings | None = None,
        store: Any | None = None,
    ) -> None:
        self._agent_factory = agent_factory
        self._checkpointer = checkpointer if checkpointer is not None else InMemorySaver()
        self._model = model
        self._settings = settings
        self._store = store if store is not None else InMemoryStore()

    def invoke(self, invocation: AgentInvocation) -> AgentInvocationResult:
        settings = self._settings or load_agent_runtime_settings()
        model = self._model if self._model is not None else create_agent_model(settings)
        tools = create_agent_tools(invocation.context)
        subagents = create_agent_subagents(tools)
        thread_id = build_agent_thread_id(invocation.context)

        agent = self._agent_factory(
            backend=lambda _runtime: StateBackend(),
            checkpointer=self._checkpointer,
            model=model,
            name=f"venus-{invocation.context.surface}",
            store=self._store,
            subagents=subagents,
            system_prompt=SYSTEM_PROMPT,
            tools=tools,
        )
        result = agent.invoke(
            {"messages": _to_langchain_messages(invocation.messages)},
            {"configurable": {"thread_id": thread_id}},
        )
        raw_messages = result.get("messages", []) if isinstance(result, dict) else []
        profile = AgentRuntimeProfile(
            model=settings.agent_model,
            provider=settings.agent_model_provider,
            subagent_names=[subagent["name"] for subagent in subagents],
            subagent_tool_names=profile_subagent_tool_names(subagents),
            tool_names=[registered_tool.name for registered_tool in tools],
        )

        return AgentInvocationResult(
            assistant_text=_message_text(raw_messages[-1] if raw_messages else None),
            message_count=len(raw_messages),
            profile=profile,
            raw={"messages": raw_messages},
            thread_id=thread_id,
        )

    def stream(self, invocation: AgentInvocation, stream_mode: str = "updates") -> Any:
        settings = self._settings or load_agent_runtime_settings()
        model = self._model if self._model is not None else create_agent_model(settings)
        tools = create_agent_tools(invocation.context)
        subagents = create_agent_subagents(tools)
        thread_id = build_agent_thread_id(invocation.context)
        agent = self._agent_factory(
            backend=lambda _runtime: StateBackend(),
            checkpointer=self._checkpointer,
            model=model,
            name=f"venus-{invocation.context.surface}",
            store=self._store,
            subagents=subagents,
            system_prompt=SYSTEM_PROMPT,
            tools=tools,
        )
        return agent.stream(
            {"messages": _to_langchain_messages(invocation.messages)},
            {"configurable": {"thread_id": thread_id}},
            stream_mode=stream_mode,
            subgraphs=True,
        )


def create_venus_agent_runtime(**kwargs: Any) -> VenusAgentRuntime:
    return VenusAgentRuntime(**kwargs)
