from math import isfinite
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class VoltageMeasurement(BaseModel):
    model_config = ConfigDict(extra="ignore")

    voltage: float


class AppleWatchEcgRecord(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    start: str | None = None
    end: str | None = None
    classification: str | None = None
    average_heart_rate: float | None = Field(default=None, alias="averageHeartRate")
    sampling_frequency: float = Field(alias="samplingFrequency")
    number_of_voltage_measurements: int | None = Field(default=None, alias="numberOfVoltageMeasurements")
    source: Any = None
    voltage_measurements: list[VoltageMeasurement] = Field(alias="voltageMeasurements", min_length=1)

    @field_validator("sampling_frequency")
    @classmethod
    def validate_sampling_frequency(cls, value: float) -> float:
        if not isfinite(value) or value <= 0:
            raise ValueError("samplingFrequency must be greater than 0")
        return value


class HealthExportData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ecg: list[AppleWatchEcgRecord] = Field(min_length=1)


class HealthExportPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    data: HealthExportData


class AppleWatchEcgInferRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    health_export: HealthExportPayload | None = Field(default=None, alias="healthExport")
    ecg_record: AppleWatchEcgRecord | None = Field(default=None, alias="ecgRecord")
    record_index: int | None = Field(default=None, alias="recordIndex")
    window_policy: Literal["first", "sliding"] = Field(default="first", alias="windowPolicy")
    threshold: float = 0.5

    @model_validator(mode="after")
    def validate_payload_source(self) -> "AppleWatchEcgInferRequest":
        has_health_export = self.health_export is not None
        has_ecg_record = self.ecg_record is not None
        if has_health_export == has_ecg_record:
            raise ValueError("Provide exactly one of healthExport or ecgRecord")
        if has_health_export:
            if self.record_index is None:
                raise ValueError("recordIndex is required when healthExport is provided")
            if self.record_index < 0:
                raise ValueError("recordIndex must be greater than or equal to 0")
        if not isfinite(self.threshold) or not 0 <= self.threshold <= 1:
            raise ValueError("threshold must be between 0 and 1")
        return self
