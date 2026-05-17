from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ScreeningContext = Literal["prenatal", "postnatal", "none"]
ScreeningStatus = Literal[
    "processed",
    "no_screening_context",
    "extraction_failed",
    "screening_unavailable",
]


class DemoDoctorNoteRecord(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    demo_id: str = Field(alias="demoId", min_length=1)
    patient_id: str = Field(alias="patientId", min_length=1)
    visit_occurrence_id: str = Field(alias="visitOccurrenceId", min_length=1)
    group: str = Field(min_length=1)
    category: str = Field(min_length=1)
    age: str | None = None
    condition_codes: str | None = Field(default=None, alias="conditionCodes")
    note_date: str | None = Field(default=None, alias="noteDate")
    note_title: str | None = Field(default=None, alias="noteTitle")
    english_demo_note: str = Field(alias="englishDemoNote", min_length=1)
    extracted_factors: str | None = Field(default=None, alias="extractedFactors")
    summary: str | None = None
    doctor_questions: str | None = Field(default=None, alias="doctorQuestions")

    @field_validator("english_demo_note")
    @classmethod
    def reject_blank_english_note(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("englishDemoNote must not be blank")
        return value


class DoctorNoteScreeningRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    session_id: str = Field(alias="sessionId", min_length=1)
    record: DemoDoctorNoteRecord

    @field_validator("session_id")
    @classmethod
    def reject_blank_session_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("sessionId must not be blank")
        return value


class DoctorNoteScreeningInsight(BaseModel):
    title: str
    risk_label: str = Field(alias="riskLabel")
    summary: str
    recommended_followup: str = Field(alias="recommendedFollowup")
    safety_note: str | None = Field(default=None, alias="safetyNote")


class DoctorNoteScreeningResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: ScreeningStatus
    screening_context: ScreeningContext = Field(alias="screeningContext")
    extracted_input: dict[str, Any] | None = Field(default=None, alias="extractedInput")
    risk_result: dict[str, Any] | None = Field(default=None, alias="riskResult")
    evidence: list[str] = Field(default_factory=list)
    missing_or_uncertain_fields: list[str] = Field(default_factory=list, alias="missingOrUncertainFields")
    insight: DoctorNoteScreeningInsight


class DoctorNoteExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    screening_context: ScreeningContext
    evidence: list[str] = Field(default_factory=list)
    summary: str | None = None
    prenatal_expanded_input: dict[str, Any] | None = None
    postnatal_followup_input: dict[str, Any] | None = None
    missing_or_uncertain_fields: list[str] = Field(default_factory=list)
