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
            "name": "doctor-note-screening-extractor",
            "description": "Extracts prenatal or postnatal screening input from a translated demo doctor note.",
            "system_prompt": (
                "Use get_doctor_note_screening_contract, get_maternal_screening_model_context, "
                "and prepare_doctor_note_extraction_payload. Inspect the selected englishDemoNote, "
                "decide whether the note is prenatal, postnatal, or none, and return strict JSON only. "
                "Do not invent clinical values, diagnose, or hardcode extraction from demo IDs, categories, "
                "groups, or condition codes. Use null for missing or uncertain fields."
            ),
            "tools": _pick_tools(
                tools,
                [
                    "get_doctor_note_screening_contract",
                    "get_maternal_screening_model_context",
                    "prepare_doctor_note_extraction_payload",
                ],
            ),
        },
        {
            "name": "care-navigation-guide",
            "description": "Explains supported prototype capabilities and honest backlog boundaries.",
            "system_prompt": (
                "Use get_supported_backend_capabilities and get_prenatal_model_context only. "
                "Describe unsupported ECG and OCR image extraction flows as placeholders unless a tool says otherwise."
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
