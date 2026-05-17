import logging
import time
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
logger = logging.getLogger(__name__)


def _elapsed_ms(started_at: float) -> int:
    return round((time.perf_counter() - started_at) * 1000)


SYSTEM_PROMPT = (
    "You are the VenusHacks maternal cardiac health companion runtime. Use only the registered "
    "tools and subagents. Treat maternal screening models as follow-up prioritization aids, not "
    "diagnoses. Do not invent unsupported backend capabilities or extract clinical values without "
    "evidence from the supplied note context."
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
        started_at = time.perf_counter()
        settings_started_at = time.perf_counter()
        settings = self._settings or load_agent_runtime_settings()
        settings_elapsed_ms = _elapsed_ms(settings_started_at)

        model_started_at = time.perf_counter()
        model = self._model if self._model is not None else create_agent_model(settings)
        model_elapsed_ms = _elapsed_ms(model_started_at)

        tools_started_at = time.perf_counter()
        tools = create_agent_tools(invocation.context)
        subagents = create_agent_subagents(tools)
        thread_id = build_agent_thread_id(invocation.context)
        tools_elapsed_ms = _elapsed_ms(tools_started_at)

        logger.info(
            "agent_runtime.invoke.prepare surface=%s session_id=%s provider=%s model=%s messages=%s tools=%s subagents=%s timings_ms=settings:%s,model:%s,tools:%s",
            invocation.context.surface,
            invocation.context.session_id,
            settings.agent_model_provider,
            settings.agent_model,
            len(invocation.messages),
            len(tools),
            len(subagents),
            settings_elapsed_ms,
            model_elapsed_ms,
            tools_elapsed_ms,
        )

        agent_started_at = time.perf_counter()
        agent = self._agent_factory(
            backend=StateBackend(),
            checkpointer=self._checkpointer,
            model=model,
            name=f"venus-{invocation.context.surface}",
            store=self._store,
            subagents=subagents,
            system_prompt=SYSTEM_PROMPT,
            tools=tools,
        )
        agent_elapsed_ms = _elapsed_ms(agent_started_at)

        langchain_messages_started_at = time.perf_counter()
        langchain_messages = _to_langchain_messages(invocation.messages)
        langchain_messages_elapsed_ms = _elapsed_ms(langchain_messages_started_at)

        invoke_started_at = time.perf_counter()
        result = agent.invoke(
            {"messages": langchain_messages},
            {"configurable": {"thread_id": thread_id}},
        )
        invoke_elapsed_ms = _elapsed_ms(invoke_started_at)
        raw_messages = result.get("messages", []) if isinstance(result, dict) else []
        assistant_text = _message_text(raw_messages[-1] if raw_messages else None)
        message_types = [type(message).__name__ for message in raw_messages]
        logger.info(
            "agent_runtime.invoke.complete surface=%s session_id=%s thread_id=%s timings_ms=agent_create:%s,message_convert:%s,llm_graph:%s,total:%s raw_messages=%s message_types=%s assistant_chars=%s",
            invocation.context.surface,
            invocation.context.session_id,
            thread_id,
            agent_elapsed_ms,
            langchain_messages_elapsed_ms,
            invoke_elapsed_ms,
            _elapsed_ms(started_at),
            len(raw_messages),
            message_types,
            len(assistant_text or ""),
        )
        profile = AgentRuntimeProfile(
            model=settings.agent_model,
            provider=settings.agent_model_provider,
            subagent_names=[subagent["name"] for subagent in subagents],
            subagent_tool_names=profile_subagent_tool_names(subagents),
            tool_names=[registered_tool.name for registered_tool in tools],
        )

        return AgentInvocationResult(
            assistant_text=assistant_text,
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
            backend=StateBackend(),
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
