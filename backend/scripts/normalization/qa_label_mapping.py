"""Run QA rounds against the shared ECG label mapping artifact."""

from __future__ import annotations

import ast
import json
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "normalized" / "derived"
MAPPING_PATH = OUT_DIR / "label_mapping.csv"
REPORT_PATH = OUT_DIR / "label_mapping_qa_report.json"
COVERAGE_PATH = OUT_DIR / "label_mapping_coverage_qa.csv"
TEXT_ANOMALIES_PATH = OUT_DIR / "label_mapping_text_anomalies.csv"
MAPPING_FLAGS_PATH = OUT_DIR / "label_mapping_quality_flags.csv"

PTBXL_ROOT = ROOT / "data" / "ptb-xl"
ECG_ARRHYTHMIA_ROOT = ROOT / "data" / "ecg-arrhythmia"
SPH_ROOT = ROOT / "data" / "sph-ecg"

ALLOWED_NORMALIZED_LABELS = {
    "normal",
    "sinus_rhythm",
    "sinus_arrhythmia",
    "atrial_fibrillation_or_flutter",
    "bradycardia",
    "tachycardia",
    "supraventricular_arrhythmia",
    "ventricular_arrhythmia",
    "ectopic_beats",
    "conduction_abnormality",
    "bundle_branch_block",
    "st_t_abnormality",
    "ischemia_or_injury_pattern",
    "myocardial_infarction_pattern",
    "hypertrophy_or_enlargement",
    "p_wave_abnormality",
    "axis_or_voltage_abnormality",
    "interval_abnormality",
    "paced_rhythm",
    "preexcitation",
    "early_repolarization",
    "brugada_pattern",
}

KNOWN_ODD_TEXT_TERMS = [
    "colockwise",
    "countercolockwise",
    "infgraction",
    "infraction",
    "atriventricalualr",
    "interior differences conduction",
    "s t changes",
    "left back bundle",
    "left front bundle",
]


def parse_json_list(value: str) -> list[str]:
    if not value or pd.isna(value):
        return []
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise TypeError(f"Expected JSON list, got {type(parsed).__name__}: {value}")
    return [str(item) for item in parsed]


def read_mapping() -> pd.DataFrame:
    if not MAPPING_PATH.exists():
        raise FileNotFoundError(f"Missing label mapping: {MAPPING_PATH}")
    mapping = pd.read_csv(MAPPING_PATH, dtype=str).fillna("")
    mapping["normalized_label_list"] = mapping["normalized_labels"].map(parse_json_list)
    mapping["review_flag_list"] = mapping["review_flags"].map(parse_json_list)
    mapping["validation_source_list"] = mapping["validation_sources"].map(parse_json_list)
    mapping["mapping_fields_dict"] = mapping["source_mapping_fields"].map(lambda value: json.loads(value) if value else {})
    return mapping


def ptbxl_raw_labels() -> Counter[str]:
    metadata = pd.read_csv(PTBXL_ROOT / "ptbxl_database.csv", usecols=["scp_codes"], dtype=str)
    counts: Counter[str] = Counter()
    for raw in metadata["scp_codes"].dropna():
        labels = ast.literal_eval(raw)
        for label in labels:
            counts[str(label)] += 1
    return counts


def parse_ecg_header_dx(path: Path) -> list[str]:
    for line in path.read_text(errors="ignore").splitlines():
        if line.startswith("#Dx:"):
            return [code.strip() for code in line.split(":", 1)[1].split(",") if code.strip()]
    return []


def ecg_arrhythmia_raw_labels() -> Counter[str]:
    counts: Counter[str] = Counter()
    for header in sorted((ECG_ARRHYTHMIA_ROOT / "WFDBRecords").rglob("*.hea")):
        for code in parse_ecg_header_dx(header):
            counts[code] += 1
    return counts


def parse_aha_atoms(value: Any) -> list[str]:
    atoms: list[str] = []
    for part in str(value).split(";"):
        for atom in part.split("+"):
            atom = atom.strip()
            if atom:
                atoms.append(atom)
    return atoms


def sph_raw_labels() -> Counter[str]:
    metadata = pd.read_csv(SPH_ROOT / "metadata.csv", usecols=["AHA_Code"], dtype=str)
    counts: Counter[str] = Counter()
    for raw in metadata["AHA_Code"].dropna():
        for atom in parse_aha_atoms(raw):
            counts[atom] += 1
    return counts


def round_1_coverage(mapping: pd.DataFrame) -> tuple[list[dict[str, Any]], list[str]]:
    dataset_specs = [
        ("ptb-xl", "scp-ecg", ptbxl_raw_labels()),
        ("ecg-arrhythmia", "snomed-ct", ecg_arrhythmia_raw_labels()),
        ("sph-ecg", "aha", sph_raw_labels()),
    ]
    rows: list[dict[str, Any]] = []
    failures: list[str] = []

    for dataset, system, raw_counts in dataset_specs:
        mapped = mapping[
            (mapping["source_dataset"] == dataset)
            & (mapping["source_label_system"] == system)
        ].copy()
        mapped_codes = set(mapped["source_label_code"])
        raw_codes = set(raw_counts)
        missing = sorted(raw_codes - mapped_codes)
        extra = sorted(mapped_codes - raw_codes)
        duplicate_rows = int(mapped["source_label_code"].duplicated().sum())
        count_mismatches = []
        mapped_counts = mapped.set_index("source_label_code")["source_record_count"].to_dict()
        for code, count in raw_counts.items():
            mapped_count = mapped_counts.get(code)
            if mapped_count is not None and str(count) != str(mapped_count):
                count_mismatches.append({"code": code, "raw_count": count, "mapping_count": mapped_count})

        if missing:
            failures.append(f"{dataset}: {len(missing)} raw labels missing from label_mapping.csv")
        if duplicate_rows:
            failures.append(f"{dataset}: {duplicate_rows} duplicate mapping rows")
        if count_mismatches:
            failures.append(f"{dataset}: {len(count_mismatches)} source_record_count mismatches")

        rows.append(
            {
                "round": "round_1_coverage",
                "source_dataset": dataset,
                "source_label_system": system,
                "raw_unique_label_count": len(raw_codes),
                "mapping_label_count": len(mapped_codes),
                "covered_label_count": len(raw_codes & mapped_codes),
                "missing_label_count": len(missing),
                "extra_mapping_label_count": len(extra),
                "duplicate_mapping_rows": duplicate_rows,
                "source_record_count_mismatches": len(count_mismatches),
                "missing_labels": json.dumps(missing, separators=(",", ":")),
                "extra_mapping_labels": json.dumps(extra, separators=(",", ":")),
                "count_mismatches": json.dumps(count_mismatches, separators=(",", ":")),
            }
        )
    return rows, failures


def normalized_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = re.sub(r"\s+", " ", value).strip().lower()
    value = value.removeprefix("ecg:").strip()
    return value


def add_text_anomaly(
    anomalies: list[dict[str, str]],
    row: pd.Series,
    field: str,
    value: str,
    anomaly: str,
    detail: str = "",
) -> None:
    anomalies.append(
        {
            "source_dataset": row["source_dataset"],
            "source_label_system": row["source_label_system"],
            "source_label_code": row["source_label_code"],
            "field": field,
            "value": value,
            "anomaly": anomaly,
            "detail": detail,
        }
    )


def round_2_text_anomalies(mapping: pd.DataFrame) -> list[dict[str, str]]:
    anomalies: list[dict[str, str]] = []
    text_fields = ["source_label_name", "source_label_abbreviation", "source_label_category"]
    for _, row in mapping.iterrows():
        for field in text_fields:
            value = str(row[field])
            if not value:
                continue
            if value != value.strip():
                add_text_anomaly(anomalies, row, field, value, "leading_or_trailing_space")
            if "\u00a0" in value:
                add_text_anomaly(anomalies, row, field, value, "contains_non_breaking_space")
            if re.search(r" {2,}", value):
                add_text_anomaly(anomalies, row, field, value, "contains_repeated_spaces")
            if "|" in value:
                add_text_anomaly(anomalies, row, field, value, "contains_pipe_joined_synonyms")
            if any(ord(char) > 127 for char in value):
                chars = sorted({char for char in value if ord(char) > 127})
                add_text_anomaly(anomalies, row, field, value, "contains_non_ascii", "".join(chars))
            lowered = value.lower()
            for term in KNOWN_ODD_TEXT_TERMS:
                if term in lowered:
                    add_text_anomaly(anomalies, row, field, value, "known_odd_or_broken_term", term)

        fields = row["mapping_fields_dict"]
        lookup_display = str(fields.get("snomed_lookup_display", ""))
        if row["source_label_system"] == "snomed-ct" and lookup_display:
            source = normalized_text(str(row["source_label_name"]))
            lookup = normalized_text(lookup_display)
            ratio = SequenceMatcher(None, source, lookup).ratio()
            if source != lookup and ratio < 0.82:
                add_text_anomaly(
                    anomalies,
                    row,
                    "source_label_name",
                    str(row["source_label_name"]),
                    "snomed_source_name_differs_from_lookup",
                    f"lookup={lookup_display}; similarity={ratio:.2f}",
                )
    return anomalies


def round_3_mapping_quality(mapping: pd.DataFrame) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    for _, row in mapping.iterrows():
        labels = row["normalized_label_list"]
        fields = row["mapping_fields_dict"]
        status = row["mapping_status"]
        review_flags = row["review_flag_list"]

        def flag(flag_type: str, detail: str = "") -> None:
            flags.append(
                {
                    "source_dataset": row["source_dataset"],
                    "source_label_system": row["source_label_system"],
                    "source_label_code": row["source_label_code"],
                    "source_label_name": row["source_label_name"],
                    "normalized_labels": row["normalized_labels"],
                    "mapping_status": status,
                    "flag": flag_type,
                    "detail": detail,
                }
            )

        unknown = sorted(set(labels) - ALLOWED_NORMALIZED_LABELS)
        if unknown:
            flag("unknown_normalized_label", json.dumps(unknown, separators=(",", ":")))
        if status not in {"mapped", "mapped_with_warnings", "needs_review", "modifier_only"}:
            flag("unknown_mapping_status", status)
        if status in {"mapped", "mapped_with_warnings"} and not labels:
            flag("mapped_status_without_normalized_labels")
        if status == "needs_review":
            flag("needs_review_mapping_status")
        if status == "mapped_with_warnings" and not review_flags:
            flag("warning_status_without_review_flags")
        if status == "mapped" and review_flags:
            flag("mapped_status_has_review_flags", json.dumps(review_flags, separators=(",", ":")))
        if status == "modifier_only" and labels:
            flag("modifier_only_has_normalized_labels")
        if "normal" in labels and len(labels) > 1:
            flag("normal_combined_with_abnormal_label")
        if len(labels) > 1:
            flag("multi_target_mapping", "Review whether this should be one broad target or multiple labels.")
        if str(fields.get("snomed_lookup_inactive", "")).lower() == "true":
            flag("inactive_snomed_concept", str(fields.get("snomed_lookup_display", "")))
            if row.get("snomed_active", "") != "false":
                flag("inactive_snomed_missing_top_level_state")
        for source in row["validation_source_list"]:
            if not (ROOT / source).exists():
                flag("validation_source_missing", source)
        if row["source_label_system"] == "snomed-ct" and not fields.get("snomed_lookup_display"):
            flag("missing_snomed_lookup_display")
        if row["source_label_system"] == "aha" and status == "modifier_only":
            flag("modifier_context_only", "Apply with its primary AHA code; do not train as standalone class.")
    return flags


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mapping = read_mapping()

    coverage_rows, coverage_failures = round_1_coverage(mapping)
    text_anomalies = round_2_text_anomalies(mapping)
    mapping_flags = round_3_mapping_quality(mapping)

    pd.DataFrame(coverage_rows).to_csv(COVERAGE_PATH, index=False)
    pd.DataFrame(
        text_anomalies,
        columns=["source_dataset", "source_label_system", "source_label_code", "field", "value", "anomaly", "detail"],
    ).to_csv(TEXT_ANOMALIES_PATH, index=False)
    pd.DataFrame(
        mapping_flags,
        columns=[
            "source_dataset",
            "source_label_system",
            "source_label_code",
            "source_label_name",
            "normalized_labels",
            "mapping_status",
            "flag",
            "detail",
        ],
    ).to_csv(MAPPING_FLAGS_PATH, index=False)

    report = {
        "round_1_coverage": {
            "status": "pass" if not coverage_failures else "fail",
            "failures": coverage_failures,
            "artifact": str(COVERAGE_PATH.relative_to(ROOT)),
        },
        "round_2_text_quality": {
            "status": "review" if text_anomalies else "pass",
            "anomaly_count": len(text_anomalies),
            "artifact": str(TEXT_ANOMALIES_PATH.relative_to(ROOT)),
        },
        "round_3_mapping_quality": {
            "status": "review" if mapping_flags else "pass",
            "flag_count": len(mapping_flags),
            "artifact": str(MAPPING_FLAGS_PATH.relative_to(ROOT)),
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n")

    print(f"Wrote {REPORT_PATH.relative_to(ROOT)}")
    print(f"Wrote {COVERAGE_PATH.relative_to(ROOT)}")
    print(f"Wrote {TEXT_ANOMALIES_PATH.relative_to(ROOT)}")
    print(f"Wrote {MAPPING_FLAGS_PATH.relative_to(ROOT)}")
    print(json.dumps(report, indent=2))
    return 1 if coverage_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
