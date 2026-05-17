from pathlib import Path
from typing import Any

from backend.schemas.screening import PostnatalFollowupRequest, PrenatalExpandedRequest

_PRENATAL_EXPANDED_ARTIFACT_DIR = (
    Path(__file__).resolve().parents[2]
    / "models"
    / "cdc-natality"
    / "prenatal_expanded_screening_v3_1_timing_safe"
)
_POSTNATAL_FOLLOWUP_ARTIFACT_DIR = (
    Path(__file__).resolve().parents[2]
    / "models"
    / "cdc-natality"
    / "postnatal_followup_v1"
)


def predict_prenatal_expanded_from_payload(
    payload: PrenatalExpandedRequest,
) -> dict[str, Any]:
    from scripts.maternal.prenatal_expanded_screening_v3_1_timing_safe import (
        predict_prenatal_expanded_screening_v3_1_timing_safe,
    )

    patient_input = payload.model_dump(exclude_none=True, by_alias=False)
    return predict_prenatal_expanded_screening_v3_1_timing_safe(
        patient_input,
        str(_PRENATAL_EXPANDED_ARTIFACT_DIR),
    )


def predict_postnatal_followup_from_payload(
    payload: PostnatalFollowupRequest,
) -> dict[str, Any]:
    from scripts.maternal.postnatal_followup_v1 import predict_postnatal_followup

    patient_input = payload.model_dump(exclude_none=True, by_alias=False)
    return predict_postnatal_followup(
        patient_input,
        str(_POSTNATAL_FOLLOWUP_ARTIFACT_DIR),
    )
