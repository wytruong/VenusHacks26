import asyncio
import logging
import time

from fastapi import APIRouter, Header, HTTPException, status
from starlette.concurrency import run_in_threadpool

from backend.schemas.agent_chat import AgentChatRequest, AgentChatResponse
from backend.schemas.doctor_note_screening import DoctorNoteScreeningRequest, DoctorNoteScreeningResponse
from backend.services.agent_chat import AgentChatUnavailableError, chat_with_agent
from backend.services.doctor_note_screening import (
    DoctorNoteScreeningUnavailableError,
    process_doctor_note_screening,
)

AGENT_CHAT_ROUTE_TIMEOUT_SECONDS = 45
DOCTOR_NOTE_SCREENING_ROUTE_TIMEOUT_SECONDS = 150
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("/chat", response_model=AgentChatResponse)
async def chat(
    payload: AgentChatRequest,
    x_request_id: str | None = Header(default=None),
) -> AgentChatResponse:
    request_id = x_request_id or "missing"
    started_at = time.perf_counter()
    logger.info(
        "agent_chat.route.start request_id=%s session_id=%s surface=%s messages=%s has_doctor_note=%s",
        request_id,
        payload.session_id,
        payload.surface,
        len(payload.messages),
        payload.doctor_note is not None,
    )

    try:
        response = await asyncio.wait_for(
            run_in_threadpool(chat_with_agent, payload, request_id),
            timeout=AGENT_CHAT_ROUTE_TIMEOUT_SECONDS,
        )
    except (AgentChatUnavailableError, asyncio.TimeoutError) as exc:
        logger.exception(
            "agent_chat.route.error request_id=%s elapsed_ms=%s",
            request_id,
            round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent chat service is unavailable.",
        ) from exc

    logger.info(
        "agent_chat.route.success request_id=%s status=200 elapsed_ms=%s thread_id=%s",
        request_id,
        round((time.perf_counter() - started_at) * 1000),
        response.thread_id,
    )
    return response


@router.post("/doctor-note-screening", response_model=DoctorNoteScreeningResponse)
async def doctor_note_screening(
    payload: DoctorNoteScreeningRequest,
    x_request_id: str | None = Header(default=None),
) -> DoctorNoteScreeningResponse:
    request_id = x_request_id or "missing"
    started_at = time.perf_counter()
    logger.info(
        "doctor_note_screening.route.start request_id=%s session_id=%s demo_id=%s timeout_seconds=%s note_chars=%s",
        request_id,
        payload.session_id,
        payload.record.demo_id,
        DOCTOR_NOTE_SCREENING_ROUTE_TIMEOUT_SECONDS,
        len(payload.record.english_demo_note),
    )

    try:
        response = await asyncio.wait_for(
            run_in_threadpool(process_doctor_note_screening, payload, request_id),
            timeout=DOCTOR_NOTE_SCREENING_ROUTE_TIMEOUT_SECONDS,
        )
    except (DoctorNoteScreeningUnavailableError, asyncio.TimeoutError) as exc:
        logger.exception(
            "doctor_note_screening.route.error request_id=%s elapsed_ms=%s timeout_seconds=%s error_type=%s",
            request_id,
            round((time.perf_counter() - started_at) * 1000),
            DOCTOR_NOTE_SCREENING_ROUTE_TIMEOUT_SECONDS,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Doctor-note screening service is unavailable.",
        ) from exc

    logger.info(
        "doctor_note_screening.route.success request_id=%s status=200 elapsed_ms=%s response_status=%s",
        request_id,
        round((time.perf_counter() - started_at) * 1000),
        response.status,
    )
    return response
