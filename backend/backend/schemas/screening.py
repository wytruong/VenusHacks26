from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator


def _reject_blank_numeric_string(value: object) -> object:
    if isinstance(value, str) and not value.strip():
        raise ValueError("value must be numeric")
    return value


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
        return _reject_blank_numeric_string(value)


class PrenatalExpandedRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    mother_age: float | None = None
    mother_bmi: float | None = None
    mother_height_inches: float | None = None
    prepregnancy_weight_lb: float | None = None
    prior_live_births: float | None = None
    prior_dead_births: float | None = None
    prior_terminations: float | None = None
    previous_cesarean_count: float | None = None
    interval_last_live_birth_recode: float | None = None
    interval_last_pregnancy_recode: float | None = None
    cigarettes_before_pregnancy: float | None = None
    cigarettes_trimester_1: float | None = None
    cigarettes_trimester_2: float | None = None
    plurality: float | None = None
    month_prenatal_care_began: float | None = None
    prenatal_visits: float | None = None
    cigarettes_trimester_3: float | None = None

    prepregnancy_hypertension: StrictBool | None = None
    prepregnancy_diabetes: StrictBool | None = None
    previous_preterm_birth: StrictBool | None = None
    previous_cesarean: StrictBool | None = None
    risk_factor_infertility_treatment: StrictBool | None = None
    multiple_gestation_known_or_suspected: StrictBool | None = None

    @field_validator(
        "mother_age",
        "mother_bmi",
        "mother_height_inches",
        "prepregnancy_weight_lb",
        "prior_live_births",
        "prior_dead_births",
        "prior_terminations",
        "previous_cesarean_count",
        "interval_last_live_birth_recode",
        "interval_last_pregnancy_recode",
        "cigarettes_before_pregnancy",
        "cigarettes_trimester_1",
        "cigarettes_trimester_2",
        "plurality",
        "month_prenatal_care_began",
        "prenatal_visits",
        "cigarettes_trimester_3",
        mode="before",
    )
    @classmethod
    def parse_numeric_fields(cls, value: object) -> object:
        return _reject_blank_numeric_string(value)


class PostnatalFollowupRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    mother_age: float | None = None
    mother_bmi: float | None = None
    mother_height_inches: float | None = None
    prepregnancy_weight_lb: float | None = None
    prior_live_births: float | None = None
    prior_dead_births: float | None = None
    prior_terminations: float | None = None
    previous_cesarean_count: float | None = None
    interval_last_live_birth_recode: float | None = None
    interval_last_other_pregnancy_recode: float | None = None
    interval_last_pregnancy_recode: float | None = None
    cigarettes_before_pregnancy: float | None = None
    cigarettes_trimester_1: float | None = None
    cigarettes_trimester_2: float | None = None
    delivery_route_code: float | None = None
    delivery_weight_lb: float | None = None
    weight_gain_lb: float | None = None
    weight_gain_recode: float | None = None
    plurality: float | None = None
    obstetric_estimate_gestation_weeks: float | None = None
    gestation_recode_3: float | None = None
    birth_weight_grams: float | None = None
    birth_weight_recode_14: float | None = None
    birth_weight_recode_4: float | None = None
    apgar_5_min: float | None = None
    apgar_10_min: float | None = None
    month_prenatal_care_began: float | None = None
    prenatal_care_began_recode: float | None = None
    prenatal_visits: float | None = None
    prenatal_visits_recode: float | None = None
    cigarettes_trimester_3: float | None = None

    prepregnancy_hypertension: StrictBool | None = None
    prepregnancy_diabetes: StrictBool | None = None
    previous_preterm_birth: StrictBool | None = None
    previous_cesarean: StrictBool | None = None
    risk_factor_infertility_treatment: StrictBool | None = None
    multiple_gestation_known_or_suspected: StrictBool | None = None
    gestational_hypertension: StrictBool | None = None
    eclampsia: StrictBool | None = None
    gestational_diabetes: StrictBool | None = None
    maternal_transfusion: StrictBool | None = None
    perineal_laceration: StrictBool | None = None
    ruptured_uterus: StrictBool | None = None
    unplanned_hysterectomy: StrictBool | None = None
    maternal_icu: StrictBool | None = None
    trial_of_labor_attempted: StrictBool | None = None
    abnormal_condition_nicu: StrictBool | None = None
    breastfed_at_discharge: StrictBool | None = None

    @field_validator(
        "mother_age",
        "mother_bmi",
        "mother_height_inches",
        "prepregnancy_weight_lb",
        "prior_live_births",
        "prior_dead_births",
        "prior_terminations",
        "previous_cesarean_count",
        "interval_last_live_birth_recode",
        "interval_last_other_pregnancy_recode",
        "interval_last_pregnancy_recode",
        "cigarettes_before_pregnancy",
        "cigarettes_trimester_1",
        "cigarettes_trimester_2",
        "delivery_route_code",
        "delivery_weight_lb",
        "weight_gain_lb",
        "weight_gain_recode",
        "plurality",
        "obstetric_estimate_gestation_weeks",
        "gestation_recode_3",
        "birth_weight_grams",
        "birth_weight_recode_14",
        "birth_weight_recode_4",
        "apgar_5_min",
        "apgar_10_min",
        "month_prenatal_care_began",
        "prenatal_care_began_recode",
        "prenatal_visits",
        "prenatal_visits_recode",
        "cigarettes_trimester_3",
        mode="before",
    )
    @classmethod
    def parse_numeric_fields(cls, value: object) -> object:
        return _reject_blank_numeric_string(value)
