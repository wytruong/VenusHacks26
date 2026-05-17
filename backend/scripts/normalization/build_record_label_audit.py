"""Build record-level label audit and clean label manifest artifacts.

This step joins every ECG record's raw label atoms to label_mapping.csv,
marks hard label-quality exclusions, and writes both clean and excluded views.
"""

from __future__ import annotations

import ast
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "normalized" / "derived"
LABEL_MAPPING_PATH = OUT_DIR / "label_mapping.csv"
RECORD_AUDIT_PATH = OUT_DIR / "record_label_audit.csv"
CLEAN_MANIFEST_PATH = OUT_DIR / "clean_label_manifest.csv"
EXCLUDED_RECORDS_PATH = OUT_DIR / "excluded_label_records.csv"
IMPACT_PATH = OUT_DIR / "label_exclusion_impact.csv"
SUMMARY_PATH = OUT_DIR / "label_exclusion_summary.json"

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


def json_list(values: list[str]) -> str:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            output.append(text)
    return json.dumps(output, separators=(",", ":"))


def parse_json_list(value: Any) -> list[str]:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return []
    parsed = json.loads(str(value))
    if not isinstance(parsed, list):
        raise TypeError(f"Expected JSON list, got {type(parsed).__name__}: {value}")
    return [str(item) for item in parsed]


def load_mapping() -> dict[tuple[str, str], dict[str, Any]]:
    mapping = pd.read_csv(LABEL_MAPPING_PATH, dtype=str).fillna("")
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for item in mapping.to_dict("records"):
        try:
            normalized_labels = parse_json_list(item["normalized_labels"])
            review_flags = parse_json_list(item.get("review_flags", "[]"))
        except Exception as exc:  # noqa: BLE001 - preserve exact row problem.
            normalized_labels = []
            review_flags = ["invalid_mapping_payload"]
            item["mapping_notes"] = f"{item.get('mapping_notes', '')} JSON parse error: {exc}".strip()

        item["_normalized_labels"] = normalized_labels
        item["_review_flags"] = review_flags
        rows[(item["source_dataset"], item["source_label_code"])] = item
    return rows


def ptbxl_records() -> list[dict[str, Any]]:
    metadata = pd.read_csv(
        PTBXL_ROOT / "ptbxl_database.csv",
        dtype=str,
        usecols=["ecg_id", "patient_id", "scp_codes", "filename_hr"],
    ).fillna("")
    rows: list[dict[str, Any]] = []
    for item in metadata.to_dict("records"):
        labels = ast.literal_eval(item["scp_codes"])
        rows.append(
            {
                "dataset": "ptb-xl",
                "record_id": item["ecg_id"],
                "original_patient_id": item["patient_id"],
                "raw_labels": item["scp_codes"],
                "raw_label_system": "scp-ecg",
                "source_label_atoms": [str(label) for label in labels.keys()],
                "source_path": item["filename_hr"],
                "num_samples": "5000",
                "duration_sec": "10.0",
                "duration_policy": "exact_10_seconds",
                "preprocessing_policy": "use_as_is",
            }
        )
    return rows


def parse_header_comments(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in path.read_text(errors="ignore").splitlines():
        if not line.startswith("#") or ":" not in line:
            continue
        key, value = line[1:].split(":", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def ecg_arrhythmia_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for header in sorted((ECG_ARRHYTHMIA_ROOT / "WFDBRecords").rglob("*.hea")):
        comments = parse_header_comments(header)
        dx = comments.get("Dx", "")
        atoms = [code.strip() for code in dx.split(",") if code.strip()]
        rows.append(
            {
                "dataset": "ecg-arrhythmia",
                "record_id": header.stem,
                "original_patient_id": f"ecg-arrhythmia:{header.stem}",
                "raw_labels": dx,
                "raw_label_system": "snomed-ct",
                "source_label_atoms": atoms,
                "source_path": str(header.relative_to(ECG_ARRHYTHMIA_ROOT)),
                "num_samples": "5000",
                "duration_sec": "10.0",
                "duration_policy": "exact_10_seconds",
                "preprocessing_policy": "use_as_is",
            }
        )
    return rows


def parse_aha_atoms(value: Any) -> list[str]:
    atoms: list[str] = []
    for part in str(value).split(";"):
        for atom in part.split("+"):
            atom = atom.strip()
            if atom:
                atoms.append(atom)
    return atoms


def sph_records() -> list[dict[str, Any]]:
    metadata = pd.read_csv(
        SPH_ROOT / "metadata.csv",
        dtype=str,
        usecols=["ECG_ID", "Patient_ID", "AHA_Code", "N"],
    ).fillna("")
    rows: list[dict[str, Any]] = []
    for item in metadata.to_dict("records"):
        num_samples = int(item["N"])
        duration_sec = num_samples / 500
        if num_samples == 5000:
            duration_policy = "exact_10_seconds"
            preprocessing_policy = "use_as_is"
        elif 5000 < num_samples <= 6000:
            duration_policy = "crop_first_10_seconds"
            preprocessing_policy = "crop_first_10_seconds"
        elif num_samples >= 6500:
            duration_policy = "exclude_duration_ge_13_sec"
            preprocessing_policy = "defer_for_windowing"
        else:
            duration_policy = "invalid_duration_lt_10_sec"
            preprocessing_policy = "exclude"
        rows.append(
            {
                "dataset": "sph-ecg",
                "record_id": item["ECG_ID"],
                "original_patient_id": item["Patient_ID"],
                "raw_labels": item["AHA_Code"],
                "raw_label_system": "aha",
                "source_label_atoms": parse_aha_atoms(item["AHA_Code"]),
                "source_path": f"records/{item['ECG_ID']}.h5",
                "num_samples": str(num_samples),
                "duration_sec": f"{duration_sec:.3f}",
                "duration_policy": duration_policy,
                "preprocessing_policy": preprocessing_policy,
            }
        )
    return rows


def audit_record(record: dict[str, Any], mapping: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    dataset = record["dataset"]
    atoms = record["source_label_atoms"]
    descriptions: list[str] = []
    normalized_labels: list[str] = []
    statuses: list[str] = []
    review_flags: list[str] = []
    exclusion_reasons: list[str] = []
    mapped_atoms: list[dict[str, Any]] = []
    usable_label_count = 0
    modifier_only_count = 0

    if not atoms:
        exclusion_reasons.append("no_source_labels")

    if dataset == "sph-ecg":
        num_samples = int(record.get("num_samples") or 0)
        if num_samples >= 6500:
            exclusion_reasons.append("sph_duration_ge_13_sec")
        elif num_samples < 5000:
            exclusion_reasons.append("sph_duration_lt_10_sec")

    for atom in atoms:
        mapping_row = mapping.get((dataset, atom))
        if mapping_row is None:
            exclusion_reasons.append("unmapped_label")
            mapped_atoms.append({"source_label_code": atom, "mapping_status": "missing"})
            continue

        label_list = mapping_row["_normalized_labels"]
        flag_list = mapping_row["_review_flags"]
        status = mapping_row["mapping_status"]
        descriptions.append(mapping_row["source_label_name"])
        statuses.append(status)
        review_flags.extend(flag_list)
        normalized_labels.extend(label_list)
        mapped_atoms.append(
            {
                "source_label_code": atom,
                "source_label_name": mapping_row["source_label_name"],
                "normalized_labels": label_list,
                "mapping_status": status,
                "review_flags": flag_list,
                "snomed_active": mapping_row.get("snomed_active", ""),
            }
        )

        if status == "modifier_only":
            modifier_only_count += 1
        elif label_list:
            usable_label_count += len(label_list)

        if status == "needs_review":
            exclusion_reasons.append("label_mapping_needs_review")
        if "inactive_snomed_concept" in flag_list or mapping_row.get("snomed_active", "").lower() == "false":
            exclusion_reasons.append("inactive_snomed_concept")
        if "invalid_mapping_payload" in flag_list:
            exclusion_reasons.append("invalid_mapping_payload")

        unknown_labels = sorted(set(label_list) - ALLOWED_NORMALIZED_LABELS)
        if unknown_labels:
            exclusion_reasons.append("unknown_normalized_label")

    if atoms and modifier_only_count == len(atoms):
        exclusion_reasons.append("modifier_only_without_primary_label")
    if usable_label_count == 0:
        exclusion_reasons.append("no_training_label")

    unique_exclusions = list(dict.fromkeys(exclusion_reasons))
    include = not unique_exclusions

    return {
        "dataset": dataset,
        "record_id": record["record_id"],
        "original_patient_id": record["original_patient_id"],
        "source_path": record["source_path"],
        "num_samples": record.get("num_samples", ""),
        "duration_sec": record.get("duration_sec", ""),
        "duration_policy": record.get("duration_policy", ""),
        "preprocessing_policy": record.get("preprocessing_policy", ""),
        "raw_label_system": record["raw_label_system"],
        "raw_labels": record["raw_labels"],
        "source_label_atoms": json_list(atoms),
        "source_label_descriptions": json_list(descriptions),
        "normalized_labels": json_list(normalized_labels),
        "label_mapping_statuses": json_list(statuses),
        "label_review_flags": json_list(review_flags),
        "mapped_label_atoms": json.dumps(mapped_atoms, separators=(",", ":")),
        "include_for_training": str(include).lower(),
        "exclusion_reason": "|".join(unique_exclusions),
    }


def build_impact(audit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_dataset = Counter(row["dataset"] for row in audit_rows)
    included_by_dataset = Counter(row["dataset"] for row in audit_rows if row["include_for_training"] == "true")
    excluded_by_dataset = Counter(row["dataset"] for row in audit_rows if row["include_for_training"] == "false")

    for dataset in sorted(by_dataset):
        total = by_dataset[dataset]
        included = included_by_dataset[dataset]
        excluded = excluded_by_dataset[dataset]
        rows.append(
            {
                "dataset": dataset,
                "exclusion_reason": "__all__",
                "record_count": excluded,
                "total_records": total,
                "included_records": included,
                "excluded_records": excluded,
                "excluded_fraction": excluded / total if total else 0,
            }
        )

        reason_counts: Counter[str] = Counter()
        for row in audit_rows:
            if row["dataset"] != dataset or row["include_for_training"] != "false":
                continue
            for reason in row["exclusion_reason"].split("|"):
                if reason:
                    reason_counts[reason] += 1
        for reason, count in sorted(reason_counts.items()):
            rows.append(
                {
                    "dataset": dataset,
                    "exclusion_reason": reason,
                    "record_count": count,
                    "total_records": total,
                    "included_records": included,
                    "excluded_records": excluded,
                    "excluded_fraction": count / total if total else 0,
                }
            )
    return rows


def build_summary(audit_rows: list[dict[str, Any]], impact_rows: list[dict[str, Any]]) -> dict[str, Any]:
    datasets: dict[str, dict[str, Any]] = {}
    for row in impact_rows:
        if row["exclusion_reason"] != "__all__":
            continue
        datasets[row["dataset"]] = {
            "total_records": row["total_records"],
            "included_records": row["included_records"],
            "excluded_records": row["excluded_records"],
            "excluded_fraction": row["excluded_fraction"],
        }
    return {
        "record_label_audit": str(RECORD_AUDIT_PATH.relative_to(ROOT)),
        "clean_label_manifest": str(CLEAN_MANIFEST_PATH.relative_to(ROOT)),
        "excluded_label_records": str(EXCLUDED_RECORDS_PATH.relative_to(ROOT)),
        "label_exclusion_impact": str(IMPACT_PATH.relative_to(ROOT)),
        "total_records": len(audit_rows),
        "included_records": sum(1 for row in audit_rows if row["include_for_training"] == "true"),
        "excluded_records": sum(1 for row in audit_rows if row["include_for_training"] == "false"),
        "datasets": datasets,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mapping = load_mapping()
    records = ptbxl_records() + ecg_arrhythmia_records() + sph_records()
    audit_rows = [audit_record(record, mapping) for record in records]
    clean_rows = [row for row in audit_rows if row["include_for_training"] == "true"]
    excluded_rows = [row for row in audit_rows if row["include_for_training"] == "false"]
    impact_rows = build_impact(audit_rows)

    write_csv(RECORD_AUDIT_PATH, audit_rows)
    write_csv(CLEAN_MANIFEST_PATH, clean_rows)
    write_csv(EXCLUDED_RECORDS_PATH, excluded_rows)
    write_csv(IMPACT_PATH, impact_rows)
    SUMMARY_PATH.write_text(json.dumps(build_summary(audit_rows, impact_rows), indent=2) + "\n")

    print(f"Wrote {RECORD_AUDIT_PATH.relative_to(ROOT)}")
    print(f"Wrote {CLEAN_MANIFEST_PATH.relative_to(ROOT)}")
    print(f"Wrote {EXCLUDED_RECORDS_PATH.relative_to(ROOT)}")
    print(f"Wrote {IMPACT_PATH.relative_to(ROOT)}")
    print(f"Wrote {SUMMARY_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
