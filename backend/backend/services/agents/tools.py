import json
from typing import Any

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from backend.services.agents.types import AgentRuntimeContext

PRENATAL_MODEL_SAFETY_NOTE = (
    "The prenatal model is a follow-up prioritization aid, not a diagnosis or a direct "
    "cardiovascular disease probability. Clinical judgment should guide care decisions."
)
MATERNAL_SCREENING_SAFETY_NOTE = (
    "Maternal screening outputs are follow-up prioritization aids, not diagnoses. Clinical "
    "judgment should guide care decisions."
)


class RiskSummaryInput(BaseModel):
    max_factors: int = Field(default=5, ge=1, le=10)


def _as_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True)


def _doctor_note_payload(context: AgentRuntimeContext) -> dict[str, Any]:
    record = context.doctor_note or {}
    return {
        "demoId": record.get("demoId"),
        "patientId": record.get("patientId"),
        "visitOccurrenceId": record.get("visitOccurrenceId"),
        "age": record.get("age"),
        "noteDate": record.get("noteDate"),
        "noteTitle": record.get("noteTitle"),
        "englishDemoNote": record.get("englishDemoNote"),
    }


def create_agent_tools(context: AgentRuntimeContext) -> list[BaseTool]:
    @tool
    def get_prenatal_model_context() -> str:
        """Read intended-use and safety context for the shipped prenatal screening model."""
        return _as_json(
            {
                "supportedModes": ["prenatal"],
                "unsupportedModes": [],
                "safetyNote": PRENATAL_MODEL_SAFETY_NOTE,
                "runtimeSurface": context.surface,
            }
        )

    @tool(args_schema=RiskSummaryInput)
    def summarize_prenatal_risk_result(max_factors: int = 5) -> str:
        """Summarize an already-computed prenatal screening result supplied to the runtime."""
        result = context.prenatal_risk_result or context.maternal_screening_result
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
    def get_doctor_note_screening_contract() -> str:
        """Read extraction rules and allowed fields for doctor-note screening."""
        return _as_json(
            {
                "allowedScreeningContexts": ["prenatal", "postnatal", "none"],
                "decisionSource": "Use englishDemoNote text and explicit metadata only.",
                "disallowedShortcuts": [
                    "Do not classify eligibility from demoId.",
                    "Do not classify eligibility from group.",
                    "Do not classify eligibility from category.",
                    "Do not set disease flags from conditionCodes alone.",
                ],
                "unknownFieldRule": "Use null for every absent or uncertain clinical value.",
                "prenatalExpandedInputFields": [
                    "mother_age",
                    "mother_bmi",
                    "mother_height_inches",
                    "prepregnancy_weight_lb",
                    "prior_live_births",
                    "prior_dead_births",
                    "prior_terminations",
                    "previous_cesarean_count",
                    "interval_last_live_birth_recode",
                    "interval_last_pregnancy_recode",
                    "cigarettes_before_pregnancy",
                    "cigarettes_trimester_1",
                    "cigarettes_trimester_2",
                    "plurality",
                    "month_prenatal_care_began",
                    "prenatal_visits",
                    "cigarettes_trimester_3",
                    "prepregnancy_hypertension",
                    "prepregnancy_diabetes",
                    "previous_preterm_birth",
                    "previous_cesarean",
                    "risk_factor_infertility_treatment",
                    "multiple_gestation_known_or_suspected",
                ],
                "postnatalFollowupInputFields": [
                    "mother_age",
                    "mother_bmi",
                    "mother_height_inches",
                    "prepregnancy_weight_lb",
                    "prior_live_births",
                    "prior_dead_births",
                    "prior_terminations",
                    "previous_cesarean_count",
                    "delivery_route_code",
                    "delivery_weight_lb",
                    "weight_gain_lb",
                    "plurality",
                    "obstetric_estimate_gestation_weeks",
                    "birth_weight_grams",
                    "apgar_5_min",
                    "apgar_10_min",
                    "prenatal_visits",
                    "prepregnancy_hypertension",
                    "prepregnancy_diabetes",
                    "previous_preterm_birth",
                    "previous_cesarean",
                    "gestational_hypertension",
                    "eclampsia",
                    "gestational_diabetes",
                    "maternal_transfusion",
                    "perineal_laceration",
                    "ruptured_uterus",
                    "unplanned_hysterectomy",
                    "maternal_icu",
                    "trial_of_labor_attempted",
                    "abnormal_condition_nicu",
                    "breastfed_at_discharge",
                ],
                "requiredJsonShape": {
                    "screening_context": "prenatal | postnatal | none",
                    "evidence": ["English note quote supporting context"],
                    "summary": "Short extraction summary",
                    "prenatal_expanded_input": "object or null",
                    "postnatal_followup_input": "object or null",
                    "missing_or_uncertain_fields": ["field_name"],
                },
            }
        )

    @tool
    def get_maternal_screening_model_context() -> str:
        """Read safety context for maternal screening model outputs."""
        return _as_json(
            {
                "supportedModes": ["prenatal_expanded", "postnatal_followup"],
                "safetyNote": MATERNAL_SCREENING_SAFETY_NOTE,
                "notDiagnosis": True,
                "runtimeSurface": context.surface,
            }
        )

    @tool
    def prepare_doctor_note_extraction_payload() -> str:
        """Read the selected translated doctor-note payload for screening extraction."""
        return _as_json(
            {
                "record": _doctor_note_payload(context),
                "instructions": [
                    "Use only englishDemoNote plus explicit age/date/title metadata.",
                    "Do not use group, category, conditionCodes, or demoId to classify eligibility.",
                    "Return null for missing or uncertain clinical fields.",
                ],
            }
        )

    @tool
    def get_supported_backend_capabilities() -> str:
        """Read currently supported backend capabilities for the VenusHacks prototype."""
        return _as_json(
            {
                "publicApi": [
                    "GET /health",
                    "POST /api/agents/chat",
                    "POST /api/agents/doctor-note-screening",
                    "POST /api/screening/prenatal-cvd",
                    "POST /api/screening/prenatal-expanded",
                    "POST /api/screening/postnatal-followup",
                ],
                "implementedModelModes": ["prenatal", "prenatal_expanded", "postnatal_followup"],
                "placeholderFlows": ["doctor-note OCR image extraction"],
            }
        )

    return [
        get_prenatal_model_context,
        summarize_prenatal_risk_result,
        get_doctor_note_screening_contract,
        get_maternal_screening_model_context,
        prepare_doctor_note_extraction_payload,
        get_supported_backend_capabilities,
    ]
