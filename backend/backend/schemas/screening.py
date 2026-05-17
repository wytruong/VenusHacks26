from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


class PrenatalCvdRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    pregnancy_mode: Literal["prenatal"] = Field(alias="pregnancyMode")
    age: float
    prepregnancy_bmi: float = Field(alias="prepregnancyBmi")
    chronic_hypertension: StrictBool = Field(alias="chronicHypertension")
    diabetes: StrictBool
    prior_preterm_or_stillbirth: StrictBool = Field(alias="priorPretermOrStillbirth")
    live_births_count: int = Field(alias="liveBirthsCount")
    smoked_pregnancy: StrictBool = Field(alias="smokedPregnancy")
    multiple_gestation: StrictBool = Field(alias="multipleGestation")

    @field_validator("age", "prepregnancy_bmi", "live_births_count", mode="before")
    @classmethod
    def parse_frontend_number(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            raise ValueError("value must be numeric")
        return value
