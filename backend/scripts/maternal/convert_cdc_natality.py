"""Convert CDC/NCHS Natality fixed-width records into structured CSV.

The CDC natality public-use file is not delimited text. Each row is a
fixed-width birth record, and the official UserGuide2024.pdf defines the
1-based character positions for every field. This adapter extracts a focused
maternal cardiovascular-risk subset for the hackathon prototype.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data/cdc-natality/raw/Nat2024PublicUS.c20250512.r20250708.txt"
DEFAULT_OUTPUT = ROOT / "data/cdc-natality/derived/natality_2024_structured.csv"
DEFAULT_SCHEMA_OUTPUT = ROOT / "data/cdc-natality/derived/natality_2024_schema.csv"
DEFAULT_SUMMARY_OUTPUT = ROOT / "data/cdc-natality/derived/natality_2024_summary.json"
EXPECTED_RECORD_LENGTH = 1345


@dataclass(frozen=True)
class Field:
    output_name: str
    raw_name: str
    start: int
    end: int
    description: str
    transform: str = "string"

    @property
    def colspec(self) -> tuple[int, int]:
        return (self.start - 1, self.end)


FIELDS: list[Field] = [
    Field("birth_year", "DOB_YY", 9, 12, "Birth year", "int"),
    Field("birth_month", "DOB_MM", 13, 14, "Birth month", "int"),
    Field("birth_weekday_code", "DOB_WK", 23, 23, "Birth day of week code", "int"),
    Field("birth_facility_code", "BFACIL", 32, 32, "Birth place / facility code", "code"),
    Field("birth_facility_recode", "BFACIL3", 50, 50, "Birth facility recode", "code"),
    Field("mother_age", "MAGER", 75, 76, "Mother age in years", "int"),
    Field("mother_age_recode_14", "MAGER14", 77, 78, "Mother age 14-group recode", "code"),
    Field("mother_age_recode_9", "MAGER9", 79, 79, "Mother age 9-group recode", "code"),
    Field("mother_birth_state_recode", "MBSTATE_REC", 84, 84, "Mother nativity recode", "code"),
    Field("resident_status_code", "RESTATUS", 104, 104, "Resident status code", "code"),
    Field("mother_race_31_code", "MRACE31", 105, 106, "Mother race 31-code recode", "code"),
    Field("mother_race_6_code", "MRACE6", 107, 107, "Mother race 6-code recode", "code"),
    Field("mother_race_15_code", "MRACE15", 108, 109, "Mother race 15-code recode", "code"),
    Field("mother_hispanic_origin_code", "MHISPX", 112, 112, "Mother Hispanic origin detail code", "code"),
    Field("mother_hispanic_origin_recode", "MHISP_R", 115, 115, "Mother Hispanic origin recode", "code"),
    Field("mother_education_code", "MEDUC", 124, 124, "Mother education code", "code"),
    Field("father_age", "FAGECOMB", 147, 148, "Father age in years", "int_unknown_99"),
    Field("marital_status_code", "DMAR", 120, 120, "Mother marital status code", "code"),
    Field("father_education_code", "FEDUC", 163, 163, "Father education code", "code"),
    Field("prior_live_births", "PRIORLIVE", 171, 172, "Prior live births now living", "int_unknown_99"),
    Field("prior_dead_births", "PRIORDEAD", 173, 174, "Prior live births now dead", "int_unknown_99"),
    Field("prior_terminations", "PRIORTERM", 175, 176, "Prior pregnancy terminations", "int_unknown_99"),
    Field("live_birth_order_recode", "LBO_REC", 179, 179, "Live birth order recode", "code"),
    Field("total_birth_order_recode", "TBO_REC", 182, 182, "Total birth order recode", "code"),
    Field("interval_last_live_birth_recode", "ILLB_R", 198, 200, "Interval since last live birth recode", "code"),
    Field("interval_last_other_pregnancy_recode", "ILOP_R", 206, 208, "Interval since last other pregnancy recode", "code"),
    Field("interval_last_pregnancy_recode", "ILP_R", 214, 216, "Interval since last pregnancy recode", "code"),
    Field("month_prenatal_care_began", "PRECARE", 224, 225, "Month prenatal care began", "int_unknown_99"),
    Field("prenatal_care_began_recode", "PRECARE5", 227, 227, "Month prenatal care began 5-group recode", "code"),
    Field("prenatal_visits", "PREVIS", 238, 239, "Number of prenatal visits", "int_unknown_99"),
    Field("prenatal_visits_recode", "PREVIS_REC", 242, 243, "Prenatal visits recode", "code"),
    Field("wic_received", "WIC", 251, 251, "WIC received during pregnancy", "yes_no_unknown"),
    Field("cigarettes_before_pregnancy", "CIG_0", 253, 254, "Average cigarettes per day before pregnancy", "int_unknown_99"),
    Field("cigarettes_trimester_1", "CIG_1", 255, 256, "Average cigarettes per day trimester 1", "int_unknown_99"),
    Field("cigarettes_trimester_2", "CIG_2", 257, 258, "Average cigarettes per day trimester 2", "int_unknown_99"),
    Field("cigarettes_trimester_3", "CIG_3", 259, 260, "Average cigarettes per day trimester 3", "int_unknown_99"),
    Field("cigarette_recode", "CIG_REC", 269, 269, "Cigarette use recode", "code"),
    Field("mother_height_inches", "M_HT_IN", 280, 281, "Mother height in inches", "int_unknown_99"),
    Field("mother_bmi", "BMI", 283, 286, "Mother pre-pregnancy BMI", "float_unknown_99_9"),
    Field("mother_bmi_recode", "BMI_R", 287, 287, "Mother BMI recode", "code"),
    Field("prepregnancy_weight_lb", "PWGT_R", 292, 294, "Mother pre-pregnancy weight in pounds", "int_unknown_999"),
    Field("delivery_weight_lb", "DWGT_R", 299, 301, "Mother delivery weight in pounds", "int_unknown_999"),
    Field("weight_gain_lb", "WTGAIN", 304, 305, "Mother pregnancy weight gain in pounds", "int_unknown_99"),
    Field("weight_gain_recode", "WTGAIN_REC", 306, 306, "Weight gain recode", "code"),
    Field("prepregnancy_diabetes", "RF_PDIAB", 313, 313, "Pre-pregnancy diabetes", "yes_no_unknown"),
    Field("gestational_diabetes", "RF_GDIAB", 314, 314, "Gestational diabetes", "yes_no_unknown"),
    Field("prepregnancy_hypertension", "RF_PHYPE", 315, 315, "Pre-pregnancy hypertension", "yes_no_unknown"),
    Field("gestational_hypertension", "RF_GHYPE", 316, 316, "Gestational hypertension", "yes_no_unknown"),
    Field("eclampsia", "RF_EHYPE", 317, 317, "Eclampsia", "yes_no_unknown"),
    Field("previous_preterm_birth", "RF_PPTERM", 318, 318, "Previous preterm birth", "yes_no_unknown"),
    Field("risk_factor_infertility_treatment", "RF_INFTR", 325, 325, "Infertility treatment", "yes_no_unknown"),
    Field("risk_factor_fertility_enhancing_drugs", "RF_FEDRG", 326, 326, "Fertility-enhancing drugs", "yes_no_unknown"),
    Field("risk_factor_assisted_reproductive_technology", "RF_ARTEC", 327, 327, "Assisted reproductive technology", "yes_no_unknown"),
    Field("previous_cesarean", "RF_CESAR", 331, 331, "Previous cesarean delivery", "yes_no_unknown"),
    Field("previous_cesarean_count", "RF_CESARN", 332, 333, "Number of previous cesarean deliveries", "int_unknown_99"),
    Field("maternal_transfusion", "MM_MTR", 415, 415, "Maternal transfusion", "yes_no_unknown"),
    Field("perineal_laceration", "MM_PLAC", 416, 416, "Third/fourth degree perineal laceration", "yes_no_unknown"),
    Field("ruptured_uterus", "MM_RUPT", 417, 417, "Ruptured uterus", "yes_no_unknown"),
    Field("unplanned_hysterectomy", "MM_UHYST", 418, 418, "Unplanned hysterectomy", "yes_no_unknown"),
    Field("maternal_icu", "MM_AICU", 419, 419, "Maternal ICU admission", "yes_no_unknown"),
    Field("no_maternal_morbidity_reported", "NO_MMORB", 427, 427, "No maternal morbidity reported", "one_zero_unknown"),
    Field("presentation_at_delivery_code", "ME_PRES", 401, 401, "Fetal presentation at delivery code", "code"),
    Field("delivery_route_code", "ME_ROUT", 402, 402, "Final route and method of delivery code", "code"),
    Field("trial_of_labor_attempted", "ME_TRIAL", 403, 403, "Trial of labor attempted if cesarean", "yes_no_unknown"),
    Field("payment_source_recode", "PAY_REC", 436, 436, "Payment source recode", "code"),
    Field("apgar_5_min", "APGAR5", 444, 445, "5-minute Apgar score", "int_unknown_88_99"),
    Field("apgar_10_min", "APGAR10", 448, 449, "10-minute Apgar score", "int_unknown_88_99"),
    Field("infant_sex", "SEX", 475, 475, "Infant sex", "infant_sex"),
    Field("plurality", "DPLURAL", 454, 454, "Plurality recode", "code"),
    Field("obstetric_estimate_gestation_weeks", "OEGEST_COMB", 499, 500, "Obstetric estimate gestation in weeks", "int_unknown_99"),
    Field("gestation_recode_3", "OEGEST_R3", 503, 503, "Gestation 3-group recode", "code"),
    Field("birth_weight_grams", "DBWT", 504, 507, "Infant birth weight in grams", "int_unknown_9999"),
    Field("birth_weight_recode_14", "BWTR14", 509, 510, "Birth weight 14-group recode", "code"),
    Field("birth_weight_recode_4", "BWTR4", 511, 511, "Birth weight 4-group recode", "code"),
    Field("abnormal_condition_nicu", "AB_NICU", 528, 528, "Infant admitted to NICU", "yes_no_unknown"),
    Field("breastfed_at_discharge", "BFED", 568, 568, "Infant breastfed at discharge", "yes_no_unknown"),
]


YES_NO_UNKNOWN = {"Y": "true", "N": "false", "U": ""}
ONE_ZERO_UNKNOWN = {"1": "true", "0": "false", "9": ""}
INFANT_SEX = {"M": "male", "F": "female"}


def _blank_unknown(value: Any, unknowns: set[str]) -> str:
    text = "" if pd.isna(value) else str(value).strip()
    if text == "" or text in unknowns:
        return ""
    return text


def _as_int(value: Any, unknowns: set[str] | None = None) -> str:
    text = _blank_unknown(value, unknowns or set())
    if text == "":
        return ""
    try:
        return str(int(text))
    except ValueError:
        return ""


def _as_float(value: Any, unknowns: set[str] | None = None) -> str:
    text = _blank_unknown(value, unknowns or set())
    if text == "":
        return ""
    try:
        return str(float(text))
    except ValueError:
        return ""


def _transform_series(series: pd.Series, transform: str) -> pd.Series:
    if transform == "string":
        return series.fillna("").astype(str).str.strip()
    if transform == "code":
        return series.fillna("").astype(str).str.strip()
    if transform == "int":
        return series.map(lambda value: _as_int(value))
    if transform == "int_unknown_99":
        return series.map(lambda value: _as_int(value, {"99"}))
    if transform == "int_unknown_999":
        return series.map(lambda value: _as_int(value, {"999"}))
    if transform == "int_unknown_9999":
        return series.map(lambda value: _as_int(value, {"9999"}))
    if transform == "int_unknown_88_99":
        return series.map(lambda value: _as_int(value, {"88", "99"}))
    if transform == "float_unknown_99_9":
        return series.map(lambda value: _as_float(value, {"99.9"}))
    if transform == "yes_no_unknown":
        return series.fillna("").astype(str).str.strip().map(lambda value: YES_NO_UNKNOWN.get(value, ""))
    if transform == "one_zero_unknown":
        return series.fillna("").astype(str).str.strip().map(lambda value: ONE_ZERO_UNKNOWN.get(value, ""))
    if transform == "infant_sex":
        return series.fillna("").astype(str).str.strip().map(lambda value: INFANT_SEX.get(value, "unknown" if value else ""))
    raise ValueError(f"Unknown transform: {transform}")


def _to_boolish(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    diabetes = df["prepregnancy_diabetes"].map(_to_boolish) | df["gestational_diabetes"].map(_to_boolish)
    hypertensive = (
        df["prepregnancy_hypertension"].map(_to_boolish)
        | df["gestational_hypertension"].map(_to_boolish)
        | df["eclampsia"].map(_to_boolish)
    )
    severe_maternal_morbidity = (
        df["maternal_transfusion"].map(_to_boolish)
        | df["ruptured_uterus"].map(_to_boolish)
        | df["unplanned_hysterectomy"].map(_to_boolish)
        | df["maternal_icu"].map(_to_boolish)
    )
    smoked_during_pregnancy = (
        pd.to_numeric(df["cigarettes_trimester_1"], errors="coerce").fillna(0).gt(0)
        | pd.to_numeric(df["cigarettes_trimester_2"], errors="coerce").fillna(0).gt(0)
        | pd.to_numeric(df["cigarettes_trimester_3"], errors="coerce").fillna(0).gt(0)
    )
    preterm = pd.to_numeric(df["obstetric_estimate_gestation_weeks"], errors="coerce").lt(37)
    low_birth_weight = pd.to_numeric(df["birth_weight_grams"], errors="coerce").lt(2500)

    df["any_diabetes"] = diabetes.map({True: "true", False: "false"})
    df["any_hypertensive_disorder"] = hypertensive.map({True: "true", False: "false"})
    df["severe_maternal_morbidity_proxy"] = severe_maternal_morbidity.map({True: "true", False: "false"})
    df["smoked_during_pregnancy"] = smoked_during_pregnancy.map({True: "true", False: "false"})
    df["preterm_birth"] = preterm.map({True: "true", False: "false"})
    df["low_birth_weight"] = low_birth_weight.map({True: "true", False: "false"})

    df["pregnancy_cvd_risk_proxy"] = (
        hypertensive | diabetes | severe_maternal_morbidity | preterm | low_birth_weight
    ).map({True: "true", False: "false"})
    return df


def _output_columns() -> list[str]:
    return ["source_row_number"] + [field.output_name for field in FIELDS] + [
        "any_diabetes",
        "any_hypertensive_disorder",
        "severe_maternal_morbidity_proxy",
        "smoked_during_pregnancy",
        "preterm_birth",
        "low_birth_weight",
        "pregnancy_cvd_risk_proxy",
    ]


def _write_schema(path: Path) -> None:
    rows = [
        {
            "output_name": field.output_name,
            "raw_name": field.raw_name,
            "start": field.start,
            "end": field.end,
            "width": field.end - field.start + 1,
            "transform": field.transform,
            "description": field.description,
        }
        for field in FIELDS
    ]
    rows.extend(
        [
            {
                "output_name": "any_diabetes",
                "raw_name": "derived",
                "start": "",
                "end": "",
                "width": "",
                "transform": "boolean_or",
                "description": "Pre-pregnancy diabetes or gestational diabetes",
            },
            {
                "output_name": "any_hypertensive_disorder",
                "raw_name": "derived",
                "start": "",
                "end": "",
                "width": "",
                "transform": "boolean_or",
                "description": "Pre-pregnancy hypertension, gestational hypertension, or eclampsia",
            },
            {
                "output_name": "severe_maternal_morbidity_proxy",
                "raw_name": "derived",
                "start": "",
                "end": "",
                "width": "",
                "transform": "boolean_or",
                "description": "Transfusion, ruptured uterus, unplanned hysterectomy, or ICU admission",
            },
            {
                "output_name": "pregnancy_cvd_risk_proxy",
                "raw_name": "derived",
                "start": "",
                "end": "",
                "width": "",
                "transform": "boolean_or",
                "description": "Hackathon proxy: hypertensive disorder, diabetes, severe morbidity, preterm, or low birth weight",
            },
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _record_length_counts(input_path: Path, sample_rows: int = 10000) -> dict[str, int]:
    counts: dict[str, int] = {}
    with input_path.open("rb") as handle:
        for index, line in enumerate(handle):
            if index >= sample_rows:
                break
            length = len(line.rstrip(b"\r\n"))
            counts[str(length)] = counts.get(str(length), 0) + 1
    return counts


def convert(
    input_path: Path,
    output_path: Path,
    schema_output_path: Path,
    summary_output_path: Path,
    chunksize: int,
    limit: int | None,
) -> dict[str, Any]:
    input_path = input_path.resolve()
    output_path = output_path.resolve()
    schema_output_path = schema_output_path.resolve()
    summary_output_path = summary_output_path.resolve()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_schema(schema_output_path)

    colspecs = [field.colspec for field in FIELDS]
    names = [field.output_name for field in FIELDS]
    output_columns = _output_columns()
    rows_written = 0
    risk_counts = {
        "any_diabetes": 0,
        "any_hypertensive_disorder": 0,
        "severe_maternal_morbidity_proxy": 0,
        "preterm_birth": 0,
        "low_birth_weight": 0,
        "pregnancy_cvd_risk_proxy": 0,
    }

    reader = pd.read_fwf(
        input_path,
        colspecs=colspecs,
        names=names,
        dtype=str,
        chunksize=chunksize,
    )
    first_chunk = True
    for chunk in reader:
        if limit is not None:
            remaining = limit - rows_written
            if remaining <= 0:
                break
            chunk = chunk.head(remaining)

        chunk = chunk.reset_index(drop=True)
        chunk_rows = len(chunk)
        source_row_start = rows_written + 1
        cleaned = pd.DataFrame({"source_row_number": range(source_row_start, source_row_start + chunk_rows)})
        for field in FIELDS:
            cleaned[field.output_name] = _transform_series(chunk[field.output_name], field.transform)
        cleaned = _add_derived_columns(cleaned)
        cleaned = cleaned[output_columns]
        cleaned.to_csv(output_path, index=False, mode="w" if first_chunk else "a", header=first_chunk)
        first_chunk = False
        rows_written += chunk_rows

        for column in risk_counts:
            risk_counts[column] += int(cleaned[column].eq("true").sum())

    summary = {
        "input_path": str(input_path.relative_to(ROOT)),
        "output_path": str(output_path.relative_to(ROOT)),
        "schema_output_path": str(schema_output_path.relative_to(ROOT)),
        "rows_written": rows_written,
        "columns_written": len(output_columns),
        "chunksize": chunksize,
        "limit": limit,
        "expected_record_length": EXPECTED_RECORD_LENGTH,
        "sample_record_length_counts": _record_length_counts(input_path),
        "risk_proxy_counts": risk_counts,
    }
    summary_output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_output_path.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--schema-output", type=Path, default=DEFAULT_SCHEMA_OUTPUT)
    parser.add_argument("--summary-output", type=Path, default=DEFAULT_SUMMARY_OUTPUT)
    parser.add_argument("--chunksize", type=int, default=100_000)
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit for smoke tests.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = convert(
        input_path=args.input,
        output_path=args.output,
        schema_output_path=args.schema_output,
        summary_output_path=args.summary_output,
        chunksize=args.chunksize,
        limit=args.limit,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
