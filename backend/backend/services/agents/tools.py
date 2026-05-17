import json
from typing import Any

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from backend.services.agents.types import AgentRuntimeContext

PRENATAL_MODEL_SAFETY_NOTE = (
    "The prenatal model is a follow-up prioritization aid, not a diagnosis or a direct "
    "cardiovascular disease probability. Clinical judgment should guide care decisions."
)


class RiskSummaryInput(BaseModel):
    max_factors: int = Field(default=5, ge=1, le=10)


def _as_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True)


def create_agent_tools(context: AgentRuntimeContext) -> list[BaseTool]:
    @tool
    def get_prenatal_model_context() -> str:
        """Read intended-use and safety context for the shipped prenatal screening model."""
        return _as_json(
            {
                "supportedModes": ["prenatal"],
                "unsupportedModes": ["postpartum"],
                "safetyNote": PRENATAL_MODEL_SAFETY_NOTE,
                "runtimeSurface": context.surface,
            }
        )

    @tool(args_schema=RiskSummaryInput)
    def summarize_prenatal_risk_result(max_factors: int = 5) -> str:
        """Summarize an already-computed prenatal screening result supplied to the runtime."""
        result = context.prenatal_risk_result
        if not result:
            return _as_json({"available": False, "summary": "No prenatal screening result was supplied."})

        factors = result.get("main_contributing_factors")
        if not isinstance(factors, list):
            factors = []

        return _as_json(
            {
                "available": True,
                "riskTier": result.get("risk_tier") or result.get("overall_followup_priority"),
                "recommendedFollowupPriority": result.get("recommended_followup_priority")
                or result.get("tier_interpretation"),
                "mainContributingFactors": factors[:max_factors],
                "safetyNote": result.get("safety_note") or PRENATAL_MODEL_SAFETY_NOTE,
            }
        )

    @tool
    def get_supported_backend_capabilities() -> str:
        """Read currently supported backend capabilities for the VenusHacks prototype."""
        return _as_json(
            {
                "publicApi": ["GET /health", "POST /api/screening/prenatal-cvd"],
                "implementedModelModes": ["prenatal"],
                "placeholderFlows": ["postpartum screening", "ECG upload analysis", "doctor-note OCR"],
            }
        )

    return [
        get_prenatal_model_context,
        summarize_prenatal_risk_result,
        get_supported_backend_capabilities,
    ]
