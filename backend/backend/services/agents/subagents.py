from collections.abc import Sequence
from typing import Any, cast

from langchain_core.tools import BaseTool


def _pick_tools(tools: Sequence[BaseTool], names: Sequence[str]) -> list[BaseTool]:
    tools_by_name = {registered_tool.name: registered_tool for registered_tool in tools}
    return [tools_by_name[name] for name in names if name in tools_by_name]


def create_agent_subagents(tools: Sequence[BaseTool]) -> list[dict[str, Any]]:
    return [
        {
            "name": "prenatal-risk-explainer",
            "description": "Explains supplied prenatal follow-up prioritization results without running inference.",
            "system_prompt": (
                "Use get_prenatal_model_context and summarize_prenatal_risk_result only. "
                "Do not diagnose, estimate direct cardiovascular disease probability, or invent missing results."
            ),
            "tools": _pick_tools(
                tools,
                ["get_prenatal_model_context", "summarize_prenatal_risk_result"],
            ),
        },
        {
            "name": "care-navigation-guide",
            "description": "Explains supported prototype capabilities and honest backlog boundaries.",
            "system_prompt": (
                "Use get_supported_backend_capabilities and get_prenatal_model_context only. "
                "Describe unsupported postpartum, ECG, and OCR flows as placeholders unless a tool says otherwise."
            ),
            "tools": _pick_tools(
                tools,
                ["get_supported_backend_capabilities", "get_prenatal_model_context"],
            ),
        },
    ]


def profile_subagent_tool_names(subagents: Sequence[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        cast(str, subagent["name"]): [tool.name for tool in subagent.get("tools", [])]
        for subagent in subagents
    }
