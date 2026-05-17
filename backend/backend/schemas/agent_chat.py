from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.schemas.doctor_note_screening import DoctorNoteScreeningResponse


AgentChatSurface = Literal["maternal_risk", "general_health_companion"]
AgentChatMessageRole = Literal["assistant", "user"]


class AgentChatMessage(BaseModel):
    role: AgentChatMessageRole
    content: str = Field(min_length=1)

    @field_validator("content")
    @classmethod
    def reject_blank_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value


class DoctorNoteChatContext(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    condition: str = Field(min_length=1)
    region: str = Field(min_length=1)
    risk: str = Field(min_length=1)
    description: str = Field(min_length=1)
    doctor_script: str = Field(alias="doctorScript", min_length=1)
    questions: list[str] = Field(default_factory=list)


class AgentChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    session_id: str = Field(alias="sessionId", min_length=1)
    surface: AgentChatSurface = "general_health_companion"
    messages: list[AgentChatMessage] = Field(min_length=1)
    user_id: str | None = Field(default=None, alias="userId")
    prenatal_risk_result: dict[str, Any] | None = Field(default=None, alias="prenatalRiskResult")
    doctor_note: DoctorNoteChatContext | None = Field(default=None, alias="doctorNote")
    doctor_note_screening: DoctorNoteScreeningResponse | None = Field(
        default=None,
        alias="doctorNoteScreening",
    )

    @field_validator("session_id")
    @classmethod
    def reject_blank_session_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("sessionId must not be blank")
        return value


class AgentChatResponse(BaseModel):
    assistant_text: str = Field(alias="assistantText")
    message_count: int = Field(alias="messageCount")
    thread_id: str = Field(alias="threadId")
