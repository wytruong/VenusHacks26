from typing import Any

from fastapi import APIRouter, HTTPException, status

from backend.schemas.ecg import AppleWatchEcgInferRequest

router = APIRouter(prefix="/api/ecg", tags=["ecg"])


def infer_apple_watch_ecg(payload: AppleWatchEcgInferRequest) -> dict[str, Any]:
    from backend.services.apple_watch_ecg import infer_apple_watch_ecg as infer

    return infer(payload)


@router.post("/apple-watch/infer")
def infer_apple_watch_ecg_route(payload: AppleWatchEcgInferRequest) -> dict[str, Any]:
    try:
        return infer_apple_watch_ecg(payload)
    except Exception as exc:
        from backend.services.apple_watch_ecg import (
            AppleWatchEcgInputError,
            AppleWatchEcgModelUnavailable,
        )

        if isinstance(exc, AppleWatchEcgInputError):
            raise HTTPException(
                status_code=422,
                detail=str(exc),
            ) from exc
        if isinstance(exc, AppleWatchEcgModelUnavailable):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Apple Watch ECG inference service is unavailable.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Apple Watch ECG inference service is unavailable.",
        ) from exc
