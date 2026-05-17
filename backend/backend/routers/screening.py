from typing import Any

from fastapi import APIRouter, HTTPException, status

from backend.schemas.screening import PrenatalCvdRequest
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
