"""Build the schema-complete unified ECG manifest."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT_FOR_IMPORTS = Path(__file__).resolve().parents[2]
if str(ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(ROOT_FOR_IMPORTS))

from scripts.normalization.adapters import ecg_arrhythmia, ptbxl, sph_ecg
from scripts.normalization.adapters.common import (
    NORMALIZED_DERIVED_DIR,
    ROOT,
    PatientIdMap,
    add_label_audit_fields,
    assign_ecg_arrhythmia_splits,
    assign_sph_splits,
    attach_patient_fields,
    build_label_prevalence,
    build_split_balance_report,
    load_label_audit,
    load_schema,
    schema_fieldnames,
    validate_rows,
    write_csv,
)


UNIFIED_MANIFEST_PATH = NORMALIZED_DERIVED_DIR / "unified_manifest.csv"
SUMMARY_PATH = NORMALIZED_DERIVED_DIR / "unified_manifest_summary.json"
LABEL_PREVALENCE_PATH = NORMALIZED_DERIVED_DIR / "label_prevalence_by_dataset.csv"
SPLIT_BALANCE_PATH = NORMALIZED_DERIVED_DIR / "split_balance_report.csv"


def _normalize_rows(rows: list[dict[str, Any]], fieldnames: list[str]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append({field: row.get(field) for field in fieldnames})
    return normalized


def _adapter_extra_field_errors(rows: list[dict[str, Any]], fieldnames: list[str]) -> list[str]:
    allowed = set(fieldnames)
    errors: list[str] = []
    for index, row in enumerate(rows, start=1):
        extra = sorted(set(row) - allowed)
        if extra:
            errors.append(f"row {index}: adapter emitted unexpected fields before normalization: {extra}")
            if len(errors) >= 50:
                errors.append("adapter extra field error limit reached")
                break
    return errors


def _source_paths_exist(rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for index, row in enumerate(rows, start=1):
        for field in ("source_header_path", "source_signal_path"):
            value = row.get(field)
            if value and not (ROOT / value).exists():
                errors.append(f"row {index}: {field} does not exist: {value}")
        source_path = row.get("source_path")
        if row["source_format"] == "hdf5" and source_path and not (ROOT / source_path).exists():
            errors.append(f"row {index}: source_path does not exist: {source_path}")
    return errors


def _patient_overlap_errors(rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    patient_splits: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        patient_splits[(row["original_source_dataset"], row["split_group_id"])].add(row["split"])
    for (source_dataset, patient_id), splits in sorted(patient_splits.items()):
        if len(splits) > 1:
            errors.append(f"{source_dataset} patient {patient_id} appears in multiple splits: {sorted(splits)}")
            if len(errors) >= 20:
                errors.append("patient overlap error limit reached")
                break
    return errors


def _dataset_policy_errors(rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for row in rows:
        source_dataset = row["original_source_dataset"]
        if source_dataset == "ptb-xl":
            if "records100" in row["source_path"] or "records100" in str(row["source_header_path"]):
                errors.append(f"PTB-XL row uses records100: {row['record_id']}")
            if row["source_format"] != "wfdb-dat":
                errors.append(f"PTB-XL row has wrong source_format: {row['record_id']}")
        elif source_dataset == "ecg-arrhythmia":
            if str(row["source_path"]).endswith(".hea") or str(row["source_path"]).endswith(".mat"):
                errors.append(f"ECG Arrhythmia source_path must be extensionless: {row['record_id']}")
        elif source_dataset == "sph-ecg":
            if row["signal_key"] != "/ecg":
                errors.append(f"SPH row has wrong signal_key: {row['record_id']}")
            if row["include_for_training"] is True and int(row["num_samples"]) > 6000:
                errors.append(f"SPH included row exceeds 12 seconds: {row['record_id']}")
    return errors


def _build_summary(rows: list[dict[str, Any]], validation_errors: list[str]) -> dict[str, Any]:
    by_dataset = Counter(row["original_source_dataset"] for row in rows)
    included_by_dataset = Counter(row["original_source_dataset"] for row in rows if row["include_for_training"] is True)
    excluded_by_dataset = Counter(row["original_source_dataset"] for row in rows if row["include_for_training"] is False)
    split_counts = Counter((row["original_source_dataset"], row["split"]) for row in rows)

    datasets: dict[str, dict[str, Any]] = {}
    for dataset in sorted(by_dataset):
        datasets[dataset] = {
            "total_records": by_dataset[dataset],
            "included_records": included_by_dataset[dataset],
            "excluded_records": excluded_by_dataset[dataset],
            "splits": {
                split: split_counts[(dataset, split)]
                for split in ("train", "val", "test")
            },
        }

    return {
        "unified_manifest": str(UNIFIED_MANIFEST_PATH.relative_to(ROOT)),
        "patient_id_map": str((NORMALIZED_DERIVED_DIR / "patient_id_map.csv").relative_to(ROOT)),
        "label_prevalence_by_dataset": str(LABEL_PREVALENCE_PATH.relative_to(ROOT)),
        "split_balance_report": str(SPLIT_BALANCE_PATH.relative_to(ROOT)),
        "total_records": len(rows),
        "included_records": sum(1 for row in rows if row["include_for_training"] is True),
        "excluded_records": sum(1 for row in rows if row["include_for_training"] is False),
        "datasets": datasets,
        "validation_error_count": len(validation_errors),
        "validation_errors": validation_errors[:50],
    }


def build_manifest() -> list[dict[str, Any]]:
    label_audit = load_label_audit()
    patient_map = PatientIdMap()

    ptb_rows = ptbxl.build_rows()
    ecg_rows = ecg_arrhythmia.build_rows()
    sph_rows = sph_ecg.build_rows()
    rows = ptb_rows + ecg_rows + sph_rows

    add_label_audit_fields(rows, label_audit)
    attach_patient_fields(rows, patient_map)
    assign_ecg_arrhythmia_splits(ecg_rows)
    assign_sph_splits(sph_rows)

    schema = load_schema()
    fieldnames = schema_fieldnames(schema)
    extra_field_errors = _adapter_extra_field_errors(rows, fieldnames)
    if extra_field_errors:
        raise RuntimeError("Unified manifest adapter field validation failed:\n" + "\n".join(extra_field_errors))
    rows = _normalize_rows(rows, fieldnames)

    validation_errors = []
    validation_errors.extend(validate_rows(rows, schema))
    validation_errors.extend(_source_paths_exist(rows))
    validation_errors.extend(_patient_overlap_errors(rows))
    validation_errors.extend(_dataset_policy_errors(rows))
    if validation_errors:
        raise RuntimeError("Unified manifest validation failed:\n" + "\n".join(validation_errors[:100]))

    patient_map.save()
    write_csv(UNIFIED_MANIFEST_PATH, rows, fieldnames)
    write_csv(
        LABEL_PREVALENCE_PATH,
        build_label_prevalence(rows),
        ["original_source_dataset", "split", "normalized_label", "record_count", "included_records", "record_fraction"],
    )
    write_csv(
        SPLIT_BALANCE_PATH,
        build_split_balance_report(rows),
        ["original_source_dataset", "split", "split_balance_group", "record_count", "included_records", "record_fraction"],
    )
    SUMMARY_PATH.write_text(json.dumps(_build_summary(rows, validation_errors), indent=2) + "\n")
    return rows


def main() -> None:
    rows = build_manifest()
    print(f"Wrote {UNIFIED_MANIFEST_PATH.relative_to(ROOT)} ({len(rows):,} rows)")
    print(f"Wrote {SUMMARY_PATH.relative_to(ROOT)}")
    print(f"Wrote {LABEL_PREVALENCE_PATH.relative_to(ROOT)}")
    print(f"Wrote {SPLIT_BALANCE_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
