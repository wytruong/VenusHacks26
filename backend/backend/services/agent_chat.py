import logging
import time
from functools import lru_cache

from backend.schemas.agent_chat import AgentChatRequest, AgentChatResponse, DoctorNoteChatContext
from backend.schemas.doctor_note_screening import DoctorNoteScreeningResponse
from backend.services.agents import VenusAgentRuntime, create_venus_agent_runtime
from backend.services.agents.types import AgentInvocation, AgentMessage, AgentRuntimeContext

logger = logging.getLogger(__name__)


class AgentChatUnavailableError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_agent_chat_runtime() -> VenusAgentRuntime:
    return create_venus_agent_runtime()


def _format_doctor_note_context(note: DoctorNoteChatContext) -> str:
    questions = "; ".join(question for question in note.questions if question.strip())
    question_context = f" Suggested doctor questions: {questions}." if questions else ""
    return (
        "The user is asking about a doctor-note OCR summary shown in the app. "
        f"Condition: {note.condition}. Region: {note.region}. Risk label: {note.risk}. "
        f"Summary: {note.description} Doctor script: {note.doctor_script}.{question_context} "
        "Provide supportive, non-diagnostic guidance and encourage clinician follow-up for personalized care."
    )


def _format_doctor_note_screening_context(screening: DoctorNoteScreeningResponse) -> str:
    missing = ", ".join(screening.missing_or_uncertain_fields)
    missing_context = f" Missing or uncertain fields: {missing}." if missing else ""
    extracted_keys = ", ".join((screening.extracted_input or {}).keys())
    extracted_context = f" Extracted input fields: {extracted_keys}." if extracted_keys else ""
    return (
        "The selected doctor note has been processed through the doctor-note screening workflow. "
        f"Workflow status: {screening.status}. Screening context: {screening.screening_context}. "
        f"Risk label: {screening.insight.risk_label}. Summary: {screening.insight.summary} "
        f"Recommended follow-up: {screening.insight.recommended_followup}."
        f"{missing_context}{extracted_context} "
        f"Safety note: {screening.insight.safety_note or 'Use clinical judgment for care decisions.'}"
    )


def _build_messages(payload: AgentChatRequest) -> list[AgentMessage]:
    messages: list[AgentMessage] = []
    if payload.doctor_note:
        messages.append(
            AgentMessage(role="system", content=_format_doctor_note_context(payload.doctor_note))
        )
    if payload.doctor_note_screening:
        messages.append(
            AgentMessage(
                role="system",
                content=_format_doctor_note_screening_context(payload.doctor_note_screening),
            )
        )

    messages.extend(
        AgentMessage(role=message.role, content=message.content.strip())
        for message in payload.messages
    )
    return messages


def chat_with_agent(payload: AgentChatRequest, request_id: str = "missing") -> AgentChatResponse:
    started_at = time.perf_counter()
    invocation = AgentInvocation(
        context=AgentRuntimeContext(
            session_id=payload.session_id.strip(),
            surface=payload.surface,
            user_id=payload.user_id.strip() if payload.user_id else None,
            prenatal_risk_result=payload.prenatal_risk_result,
            doctor_note=payload.doctor_note.model_dump(by_alias=True) if payload.doctor_note else None,
            maternal_screening_result=(
                payload.doctor_note_screening.risk_result if payload.doctor_note_screening else None
            ),
        ),
        messages=_build_messages(payload),
    )

    logger.info(
        "agent_chat.service.invoke_start request_id=%s session_id=%s surface=%s messages=%s",
        request_id,
        invocation.context.session_id,
        invocation.context.surface,
        len(invocation.messages),
    )

    try:
        result = get_agent_chat_runtime().invoke(invocation)
    except Exception as exc:
        logger.exception(
            "agent_chat.service.invoke_error request_id=%s elapsed_ms=%s error_type=%s",
            request_id,
            round((time.perf_counter() - started_at) * 1000),
            type(exc).__name__,
        )
        raise AgentChatUnavailableError("Agent chat service is unavailable.") from exc

    if not result.assistant_text:
        logger.error(
            "agent_chat.service.empty_response request_id=%s elapsed_ms=%s thread_id=%s",
            request_id,
            round((time.perf_counter() - started_at) * 1000),
            result.thread_id,
        )
        raise AgentChatUnavailableError("Agent chat service is unavailable.")

    logger.info(
        "agent_chat.service.invoke_success request_id=%s elapsed_ms=%s thread_id=%s message_count=%s",
        request_id,
        round((time.perf_counter() - started_at) * 1000),
        result.thread_id,
        result.message_count,
    )

    return AgentChatResponse(
        assistantText=result.assistant_text,
        messageCount=result.message_count,
        threadId=result.thread_id,
    )
