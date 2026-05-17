import json
import logging
import re
import resource
import time
from typing import Any

from pydantic import ValidationError

from backend.schemas.doctor_note_screening import (
    DemoDoctorNoteRecord,
    DoctorNoteExtractionOutput,
    DoctorNoteScreeningInsight,
    DoctorNoteScreeningRequest,
    DoctorNoteScreeningResponse,
)
from backend.schemas.screening import PostnatalFollowupRequest, PrenatalExpandedRequest
from functools import lru_cache

from backend.services.agents import VenusAgentRuntime, create_venus_agent_runtime
from backend.services.agents.config import load_agent_runtime_settings
from backend.services.agents.types import AgentInvocation, AgentMessage, AgentRuntimeContext
from backend.services.maternal_screening import (
    predict_postnatal_followup_from_payload,
    predict_prenatal_expanded_from_payload,
)

logger = logging.getLogger(__name__)

EXTRACTION_FAILED_SAFETY_NOTE = (
    "The note could not be converted into a validated screening input. Please review it with a clinician."
)
NO_CONTEXT_SAFETY_NOTE = "No prenatal or postnatal screening model was run for this note."
SCREENING_SAFETY_NOTE = (
    "This is a follow-up prioritization aid, not a diagnosis. Clinical judgment should guide care decisions."
)
DOCTOR_NOTE_SCREENING_AGENT_MODEL = "x-ai/grok-4.3"


@lru_cache(maxsize=1)
def get_doctor_note_screening_runtime() -> VenusAgentRuntime:
    settings = load_agent_runtime_settings().model_copy(
        update={"agent_model": DOCTOR_NOTE_SCREENING_AGENT_MODEL}
    )
    return create_venus_agent_runtime(settings=settings)


def _elapsed_ms(started_at: float) -> int:
    return round((time.perf_counter() - started_at) * 1000)


def _max_rss_raw() -> int:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def _dict_keys(value: dict[str, Any] | None) -> list[str]:
    return sorted(value.keys()) if value else []


class DoctorNoteScreeningUnavailableError(RuntimeError):
    pass


class DoctorNoteExtractionFailedError(RuntimeError):
    pass


def _json_from_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped).strip()

    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if not match:
            raise DoctorNoteExtractionFailedError("Agent response did not contain JSON.")
        value = json.loads(match.group(0))

    if not isinstance(value, dict):
        raise DoctorNoteExtractionFailedError("Agent response JSON must be an object.")
    return value


def _record_context(record: DemoDoctorNoteRecord) -> dict[str, Any]:
    return record.model_dump(by_alias=True)


def _build_extraction_prompt(record: DemoDoctorNoteRecord) -> str:
    payload = {
        "selectedDemoRecord": {
            "demoId": record.demo_id,
            "patientId": record.patient_id,
            "visitOccurrenceId": record.visit_occurrence_id,
            "age": record.age,
            "noteDate": record.note_date,
            "noteTitle": record.note_title,
            "englishDemoNote": record.english_demo_note,
        },
        "disallowedExtractionShortcuts": [
            "Do not decide eligibility from group.",
            "Do not decide eligibility from category.",
            "Do not set disease flags from conditionCodes alone.",
            "Do not infer risk tier from demoId or CSV row order.",
        ],
    }
    return (
        "Use the doctor-note-screening-extractor subagent and its allowed tools. "
        "Classify the selected englishDemoNote as prenatal, postnatal, or none. "
        "Extract only values supported by the English translated note text or explicit age/date/title metadata. "
        "Use null for missing or uncertain clinical values. Return strict JSON only with keys: "
        "screening_context, evidence, summary, prenatal_expanded_input, postnatal_followup_input, "
        f"missing_or_uncertain_fields. Payload: {json.dumps(payload, sort_keys=True)}"
    )


def _missing_from_model_result(result: dict[str, Any]) -> list[str]:
    missing = result.get("missing_inputs")
    if isinstance(missing, list):
        return [str(value) for value in missing]
    return []


def _risk_label(result: dict[str, Any]) -> str:
    current_signal = result.get("current_composite_signal")
    if isinstance(current_signal, dict) and current_signal.get("tier"):
        return str(current_signal["tier"]).upper()

    for key in (
        "risk_tier",
        "overall_followup_priority",
        "recommended_followup_priority",
        "routing_method",
    ):
        value = result.get(key)
        if value:
            return str(value).upper()
    return "INFO"


def _recommended_followup(result: dict[str, Any]) -> str:
    for key in ("recommended_followup_priority", "tier_interpretation", "overall_followup_priority"):
        value = result.get(key)
        if value:
            return str(value)
    return "Review the model output with a clinician for personalized guidance."


def _processed_response(
    *,
    context: str,
    extraction: DoctorNoteExtractionOutput,
    extracted_input: dict[str, Any],
    risk_result: dict[str, Any],
) -> DoctorNoteScreeningResponse:
    missing = [*extraction.missing_or_uncertain_fields, *_missing_from_model_result(risk_result)]
    return DoctorNoteScreeningResponse(
        status="processed",
        screeningContext=context,
        extractedInput=extracted_input,
        riskResult=risk_result,
        evidence=extraction.evidence,
        missingOrUncertainFields=list(dict.fromkeys(missing)),
        insight=DoctorNoteScreeningInsight(
            title=f"{context.title()} screening signal",
            riskLabel=_risk_label(risk_result),
            summary=extraction.summary
            or "The selected note contained enough context to run maternal screening.",
            recommendedFollowup=_recommended_followup(risk_result),
            safetyNote=str(risk_result.get("safety_note") or SCREENING_SAFETY_NOTE),
        ),
    )


def _no_context_response(extraction: DoctorNoteExtractionOutput) -> DoctorNoteScreeningResponse:
    return DoctorNoteScreeningResponse(
        status="no_screening_context",
        screeningContext="none",
        extractedInput=None,
        riskResult=None,
        evidence=extraction.evidence,
        missingOrUncertainFields=extraction.missing_or_uncertain_fields,
        insight=DoctorNoteScreeningInsight(
            title="No maternal screening context detected",
            riskLabel="INFO",
            summary=extraction.summary
            or "The translated note did not contain enough prenatal or postnatal context to run screening.",
            recommendedFollowup="Use the note summary and ask your clinician for personalized guidance.",
            safetyNote=NO_CONTEXT_SAFETY_NOTE,
        ),
    )


def _extraction_failed_response(message: str) -> DoctorNoteScreeningResponse:
    return DoctorNoteScreeningResponse(
        status="extraction_failed",
        screeningContext="none",
        extractedInput=None,
        riskResult=None,
        evidence=[],
        missingOrUncertainFields=[],
        insight=DoctorNoteScreeningInsight(
            title="Doctor-note screening unavailable",
            riskLabel="INFO",
            summary=message,
            recommendedFollowup="Review the note with a clinician or try another demo record.",
            safetyNote=EXTRACTION_FAILED_SAFETY_NOTE,
        ),
    )


def process_doctor_note_screening(
    payload: DoctorNoteScreeningRequest,
    request_id: str = "missing",
) -> DoctorNoteScreeningResponse:
    started_at = time.perf_counter()
    record = payload.record
    invocation = AgentInvocation(
        context=AgentRuntimeContext(
            session_id=payload.session_id.strip(),
            surface="doctor_note_screening",
            doctor_note=_record_context(record),
        ),
        messages=[AgentMessage(role="user", content=_build_extraction_prompt(record))],
    )

    prompt_chars = len(invocation.messages[0].content)
    note_chars = len(record.english_demo_note)
    logger.info(
        "doctor_note_screening.service.invoke_start request_id=%s session_id=%s demo_id=%s note_chars=%s prompt_chars=%s rss_max_raw=%s",
        request_id,
        payload.session_id,
        record.demo_id,
        note_chars,
        prompt_chars,
        _max_rss_raw(),
    )

    try:
        agent_started_at = time.perf_counter()
        result = get_doctor_note_screening_runtime().invoke(invocation)
        logger.info(
            "doctor_note_screening.service.agent_complete request_id=%s agent_elapsed_ms=%s total_elapsed_ms=%s message_count=%s assistant_chars=%s thread_id=%s rss_max_raw=%s",
            request_id,
            _elapsed_ms(agent_started_at),
            _elapsed_ms(started_at),
            result.message_count,
            len(result.assistant_text or ""),
            result.thread_id,
            _max_rss_raw(),
        )
    except Exception as exc:
        logger.exception(
            "doctor_note_screening.service.invoke_error request_id=%s elapsed_ms=%s error_type=%s",
            request_id,
            _elapsed_ms(started_at),
            type(exc).__name__,
        )
        raise DoctorNoteScreeningUnavailableError("Doctor-note screening service is unavailable.") from exc

    if not result.assistant_text:
        return _extraction_failed_response("The agent did not return an extraction result.")

    try:
        extraction_started_at = time.perf_counter()
        extraction_payload = _json_from_text(result.assistant_text)
        json_parse_elapsed_ms = _elapsed_ms(extraction_started_at)
        validation_started_at = time.perf_counter()
        extraction = DoctorNoteExtractionOutput.model_validate(extraction_payload)
        logger.info(
            "doctor_note_screening.service.extraction_valid request_id=%s json_parse_elapsed_ms=%s schema_validation_elapsed_ms=%s total_elapsed_ms=%s context=%s evidence_count=%s missing_count=%s prenatal_keys=%s postnatal_keys=%s rss_max_raw=%s",
            request_id,
            json_parse_elapsed_ms,
            _elapsed_ms(validation_started_at),
            _elapsed_ms(started_at),
            extraction.screening_context,
            len(extraction.evidence),
            len(extraction.missing_or_uncertain_fields),
            _dict_keys(extraction.prenatal_expanded_input),
            _dict_keys(extraction.postnatal_followup_input),
            _max_rss_raw(),
        )
    except (DoctorNoteExtractionFailedError, ValidationError, json.JSONDecodeError) as exc:
        assistant_text = result.assistant_text or ""
        logger.warning(
            "doctor_note_screening.service.extraction_invalid request_id=%s elapsed_ms=%s error_type=%s assistant_chars=%s contains_json_object=%s starts_with_fence=%s rss_max_raw=%s",
            request_id,
            _elapsed_ms(started_at),
            type(exc).__name__,
            len(assistant_text),
            bool(re.search(r"\{.*\}", assistant_text, flags=re.DOTALL)),
            assistant_text.lstrip().startswith("```"),
            _max_rss_raw(),
        )
        return _extraction_failed_response("The agent could not extract a validated screening payload from this note.")

    try:
        if extraction.screening_context == "prenatal":
            payload_validation_started_at = time.perf_counter()
            screening_payload = PrenatalExpandedRequest.model_validate(
                extraction.prenatal_expanded_input or {}
            )
            extracted_input = screening_payload.model_dump(exclude_none=True, by_alias=False)
            logger.info(
                "doctor_note_screening.service.model_input_valid request_id=%s context=prenatal validation_elapsed_ms=%s extracted_keys=%s total_elapsed_ms=%s",
                request_id,
                _elapsed_ms(payload_validation_started_at),
                _dict_keys(extracted_input),
                _elapsed_ms(started_at),
            )
            model_started_at = time.perf_counter()
            risk_result = predict_prenatal_expanded_from_payload(screening_payload)
            logger.info(
                "doctor_note_screening.service.model_complete request_id=%s context=prenatal model_elapsed_ms=%s total_elapsed_ms=%s risk_keys=%s model_missing_count=%s rss_max_raw=%s",
                request_id,
                _elapsed_ms(model_started_at),
                _elapsed_ms(started_at),
                _dict_keys(risk_result),
                len(_missing_from_model_result(risk_result)),
                _max_rss_raw(),
            )
            response = _processed_response(
                context="prenatal",
                extraction=extraction,
                extracted_input=extracted_input,
                risk_result=risk_result,
            )
        elif extraction.screening_context == "postnatal":
            payload_validation_started_at = time.perf_counter()
            screening_payload = PostnatalFollowupRequest.model_validate(
                extraction.postnatal_followup_input or {}
            )
            extracted_input = screening_payload.model_dump(exclude_none=True, by_alias=False)
            logger.info(
                "doctor_note_screening.service.model_input_valid request_id=%s context=postnatal validation_elapsed_ms=%s extracted_keys=%s total_elapsed_ms=%s",
                request_id,
                _elapsed_ms(payload_validation_started_at),
                _dict_keys(extracted_input),
                _elapsed_ms(started_at),
            )
            model_started_at = time.perf_counter()
            risk_result = predict_postnatal_followup_from_payload(screening_payload)
            logger.info(
                "doctor_note_screening.service.model_complete request_id=%s context=postnatal model_elapsed_ms=%s total_elapsed_ms=%s risk_keys=%s model_missing_count=%s rss_max_raw=%s",
                request_id,
                _elapsed_ms(model_started_at),
                _elapsed_ms(started_at),
                _dict_keys(risk_result),
                len(_missing_from_model_result(risk_result)),
                _max_rss_raw(),
            )
            response = _processed_response(
                context="postnatal",
                extraction=extraction,
                extracted_input=extracted_input,
                risk_result=risk_result,
            )
        else:
            logger.info(
                "doctor_note_screening.service.no_model_run request_id=%s total_elapsed_ms=%s evidence_count=%s missing_count=%s rss_max_raw=%s",
                request_id,
                _elapsed_ms(started_at),
                len(extraction.evidence),
                len(extraction.missing_or_uncertain_fields),
                _max_rss_raw(),
            )
            response = _no_context_response(extraction)
    except ValidationError as exc:
        attempted_input = (
            extraction.prenatal_expanded_input
            if extraction.screening_context == "prenatal"
            else extraction.postnatal_followup_input
        )
        logger.warning(
            "doctor_note_screening.service.model_input_invalid request_id=%s context=%s total_elapsed_ms=%s input_keys=%s error_count=%s rss_max_raw=%s",
            request_id,
            extraction.screening_context,
            _elapsed_ms(started_at),
            _dict_keys(attempted_input),
            len(exc.errors()),
            _max_rss_raw(),
        )
        return _extraction_failed_response("The extracted screening fields did not match the model input contract.")
    except Exception as exc:
        logger.exception(
            "doctor_note_screening.service.screening_error request_id=%s elapsed_ms=%s error_type=%s",
            request_id,
            _elapsed_ms(started_at),
            type(exc).__name__,
        )
        raise DoctorNoteScreeningUnavailableError("Doctor-note screening service is unavailable.") from exc

    logger.info(
        "doctor_note_screening.service.success request_id=%s elapsed_ms=%s status=%s context=%s",
        request_id,
        _elapsed_ms(started_at),
        response.status,
        response.screening_context,
    )
    return response
