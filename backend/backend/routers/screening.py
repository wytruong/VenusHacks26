from typing import Any

from fastapi import APIRouter, HTTPException, status

from backend.schemas.screening import (
    PostnatalFollowupRequest,
    PrenatalCvdRequest,
    PrenatalExpandedRequest,
)
from backend.services.maternal_screening import (
    predict_postnatal_followup_from_payload,
    predict_prenatal_expanded_from_payload,
)
from backend.services.prenatal_cvd import predict_from_frontend_payload

router = APIRouter(prefix="/api/screening", tags=["screening"])


@router.post("/prenatal-cvd")
def screen_prenatal_cvd(payload: PrenatalCvdRequest) -> dict[str, Any]:
    try:
        return predict_from_frontend_payload(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prenatal screening model is unavailable.",
        ) from exc


@router.post("/prenatal-expanded")
def screen_prenatal_expanded(payload: PrenatalExpandedRequest) -> dict[str, Any]:
    try:
        return predict_prenatal_expanded_from_payload(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prenatal expanded screening model is unavailable.",
        ) from exc


@router.post("/postnatal-followup")
def screen_postnatal_followup(payload: PostnatalFollowupRequest) -> dict[str, Any]:
    try:
        return predict_postnatal_followup_from_payload(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Postnatal follow-up model is unavailable.",
        ) from exc
