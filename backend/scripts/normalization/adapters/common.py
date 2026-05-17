"""Shared helpers for unified ECG manifest adapters."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
from nanoid import generate


ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
NORMALIZED_DERIVED_DIR = DATA_DIR / "normalized" / "derived"
SCHEMA_PATH = ROOT / "docs" / "unified-schema-contract.json"
PATIENT_ID_MAP_PATH = NORMALIZED_DERIVED_DIR / "patient_id_map.csv"
RECORD_LABEL_AUDIT_PATH = NORMALIZED_DERIVED_DIR / "record_label_audit.csv"

NORMAL_REFERENCE_LABELS = {"normal", "sinus_rhythm", "sinus_arrhythmia"}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def json_list(values: list[Any]) -> str:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            output.append(text)
    return json_dumps(output)


def parse_json_list(value: Any) -> list[str]:
    if value is None or pd.isna(value) or str(value).strip() == "":
        return []
    parsed = json.loads(str(value))
    if not isinstance(parsed, list):
        raise ValueError(f"Expected JSON list, got {type(parsed).__name__}: {value}")
    return [str(item) for item in parsed]


def none_if_blank(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def float_or_none(value: Any) -> float | None:
    text = none_if_blank(value)
    if text is None:
        return None
    return float(text)


def normalize_sex(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"1", "m", "male"}:
        return "male"
    if text in {"0", "f", "female"}:
        return "female"
    return "unknown"


def stable_bucket(value: str, modulo: int = 10000) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % modulo


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text())


def schema_fieldnames(schema: dict[str, Any]) -> list[str]:
    return list(schema["properties"].keys())


def load_label_audit() -> dict[tuple[str, str], dict[str, Any]]:
    df = pd.read_csv(RECORD_LABEL_AUDIT_PATH, dtype=str).fillna("")
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for item in df.to_dict("records"):
        key = (item["dataset"], str(item["record_id"]))
        rows[key] = item
    return rows


class PatientIdMap:
    def __init__(self, path: Path = PATIENT_ID_MAP_PATH) -> None:
        self.path = path
        self.rows: dict[tuple[str, str], str] = {}
        self.used_ids: set[str] = set()
        if path.exists():
            df = pd.read_csv(path, dtype=str).fillna("")
            for item in df.to_dict("records"):
                key = (item["original_source_dataset"], item["original_patient_id"])
                patient_id = item["patient_id"]
                self.rows[key] = patient_id
                self.used_ids.add(patient_id)

    def get(self, original_source_dataset: str, original_patient_id: str) -> str:
        key = (original_source_dataset, original_patient_id)
        if key not in self.rows:
            patient_id = self._generate_unique_id()
            self.rows[key] = patient_id
            self.used_ids.add(patient_id)
        return self.rows[key]

    def _generate_unique_id(self) -> str:
        for _ in range(100):
            patient_id = generate(size=8)
            if patient_id not in self.used_ids:
                return patient_id
        raise RuntimeError("Unable to generate unique Nano ID after 100 attempts")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            {
                "original_source_dataset": dataset,
                "original_patient_id": original_patient_id,
                "patient_id": patient_id,
                "split_group_id": patient_id,
            }
            for (dataset, original_patient_id), patient_id in sorted(self.rows.items())
        ]
        write_csv(self.path, rows, ["original_source_dataset", "original_patient_id", "patient_id", "split_group_id"])


def derive_split_balance_group(normalized_labels_json: str) -> str:
    labels = set(parse_json_list(normalized_labels_json))
    normal = bool(labels & NORMAL_REFERENCE_LABELS)
    abnormal = bool(labels - NORMAL_REFERENCE_LABELS)
    if normal and abnormal:
        return "mixed_normal_and_abnormal"
    if abnormal:
        return "abnormal_or_cvd_positive"
    return "normal_or_sinus_reference"


def attach_patient_fields(rows: list[dict[str, Any]], patient_map: PatientIdMap) -> None:
    for row in rows:
        patient_id = patient_map.get(row["original_source_dataset"], row["original_patient_id"])
        row["patient_id"] = patient_id
        row["split_group_id"] = patient_id

    counts = Counter((row["original_source_dataset"], row["patient_id"]) for row in rows)
    for row in rows:
        count = counts[(row["original_source_dataset"], row["patient_id"])]
        row["patient_record_count"] = count
        row["is_multi_record_patient"] = count > 1


def add_label_audit_fields(rows: list[dict[str, Any]], audit_rows: dict[tuple[str, str], dict[str, Any]]) -> None:
    for row in rows:
        source_dataset = row["original_source_dataset"]
        audit = audit_rows.get((source_dataset, row["record_id"]))
        if audit is None:
            raise KeyError(f"Missing label audit row for {(source_dataset, row['record_id'])}")

        row["source_label_atoms"] = audit["source_label_atoms"]
        row["source_label_descriptions"] = audit["source_label_descriptions"] or None
        row["normalized_labels"] = audit["normalized_labels"]
        row["label_mapping_statuses"] = audit["label_mapping_statuses"]
        row["label_review_flags"] = audit["label_review_flags"]
        row["include_for_training"] = audit["include_for_training"].lower() == "true"
        row["exclusion_reason"] = audit["exclusion_reason"] or None
        row["split_balance_group"] = derive_split_balance_group(audit["normalized_labels"])


def assign_ecg_arrhythmia_splits(rows: list[dict[str, Any]]) -> None:
    patient_to_split: dict[str, str] = {}
    for row in rows:
        patient = row["split_group_id"]
        if patient not in patient_to_split:
            bucket = stable_bucket(row["original_patient_id"])
            if bucket < 8000:
                patient_to_split[patient] = "train"
            elif bucket < 9000:
                patient_to_split[patient] = "val"
            else:
                patient_to_split[patient] = "test"
        row["split"] = patient_to_split[patient]
        row["split_source"] = "generated_patient_hash_split_from_record_id"


def assign_sph_splits(rows: list[dict[str, Any]]) -> None:
    patient_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        patient_records[row["split_group_id"]].append(row)

    patients = sorted(patient_records)
    multi_record_patients = {patient for patient, items in patient_records.items() if len(items) > 1}
    target_test_count = round(len(patients) * 0.20)
    test_patients = set(multi_record_patients)

    single_patients = [patient for patient in patients if patient not in test_patients]
    single_patients.sort(key=lambda patient: stable_bucket(f"sph-test:{patient}"))
    for patient in single_patients:
        if len(test_patients) >= target_test_count:
            break
        test_patients.add(patient)

    remaining_patients = [patient for patient in patients if patient not in test_patients]
    target_val_count = round(len(patients) * 0.10)
    val_patients = set(sorted(remaining_patients, key=lambda patient: stable_bucket(f"sph-val:{patient}"))[:target_val_count])

    for row in rows:
        patient = row["split_group_id"]
        if patient in test_patients:
            row["split"] = "test"
        elif patient in val_patients:
            row["split"] = "val"
        else:
            row["split"] = "train"
        row["split_source"] = "sph_example_code_patient_split"


def validate_rows(rows: list[dict[str, Any]], schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    properties = schema["properties"]
    allowed_fields = set(properties)
    required = set(schema["required"])
    label_vocab = set(schema["$defs"]["normalized_labels"]["enum"])
    exclusion_vocab = set(schema["$defs"]["hard_exclusion_reasons"]["enum"])
    json_fields = {
        "raw_labels",
        "source_label_atoms",
        "source_label_descriptions",
        "normalized_labels",
        "label_mapping_statuses",
        "label_review_flags",
        "quality_flags",
    }

    for index, row in enumerate(rows, start=1):
        row_fields = set(row)
        missing = required - row_fields
        extra = row_fields - allowed_fields
        if missing:
            errors.append(f"row {index}: missing required fields {sorted(missing)}")
        if extra:
            errors.append(f"row {index}: unexpected fields {sorted(extra)}")

        for field, spec in properties.items():
            if field not in row:
                continue
            value = row[field]
            if "enum" in spec and value not in spec["enum"]:
                errors.append(f"row {index}: {field}={value!r} not in enum {spec['enum']}")
            if spec.get("const") is not None and value != spec["const"]:
                errors.append(f"row {index}: {field}={value!r} does not equal {spec['const']!r}")
            if isinstance(value, (int, float)):
                if "minimum" in spec and value < spec["minimum"]:
                    errors.append(f"row {index}: {field}={value!r} is below minimum {spec['minimum']}")
                if "maximum" in spec and value > spec["maximum"]:
                    errors.append(f"row {index}: {field}={value!r} is above maximum {spec['maximum']}")
                if "exclusiveMinimum" in spec and value <= spec["exclusiveMinimum"]:
                    errors.append(
                        f"row {index}: {field}={value!r} is not above exclusiveMinimum {spec['exclusiveMinimum']}"
                    )

        if row.get("split_group_id") != row.get("patient_id"):
            errors.append(f"row {index}: split_group_id must equal patient_id for v1")
        if row.get("is_multi_record_patient") != (row.get("patient_record_count", 0) > 1):
            errors.append(f"row {index}: is_multi_record_patient does not match patient_record_count")
        if row.get("include_for_training") is True and row.get("exclusion_reason"):
            errors.append(f"row {index}: included row has exclusion_reason")
        if row.get("include_for_training") is False and not row.get("exclusion_reason"):
            errors.append(f"row {index}: excluded row has no exclusion_reason")

        for field in json_fields:
            value = row.get(field)
            if value is None:
                continue
            try:
                json.loads(value)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"row {index}: {field} is not valid JSON: {exc}")

        labels = set(parse_json_list(row.get("normalized_labels", "[]")))
        unknown_labels = labels - label_vocab
        if unknown_labels:
            errors.append(f"row {index}: unknown normalized labels {sorted(unknown_labels)}")
        if row.get("include_for_training") is True and not labels:
            errors.append(f"row {index}: included row has no normalized_labels")

        if row.get("exclusion_reason"):
            unknown_reasons = set(str(row["exclusion_reason"]).split("|")) - exclusion_vocab
            if unknown_reasons:
                errors.append(f"row {index}: unknown exclusion reasons {sorted(unknown_reasons)}")

    return errors


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def build_label_prevalence(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str, str]] = Counter()
    totals: Counter[tuple[str, str]] = Counter()
    for row in rows:
        if row["include_for_training"] is not True:
            continue
        dataset_split = (row["original_source_dataset"], row["split"])
        totals[dataset_split] += 1
        for label in parse_json_list(row["normalized_labels"]):
            counts[(row["original_source_dataset"], row["split"], label)] += 1

    output: list[dict[str, Any]] = []
    for (source_dataset, split, label), count in sorted(counts.items()):
        total = totals[(source_dataset, split)]
        output.append(
            {
                "original_source_dataset": source_dataset,
                "split": split,
                "normalized_label": label,
                "record_count": count,
                "included_records": total,
                "record_fraction": count / total if total else 0,
            }
        )
    return output


def build_split_balance_report(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[tuple[str, str, str]] = Counter()
    totals: Counter[tuple[str, str]] = Counter()
    for row in rows:
        if row["include_for_training"] is not True:
            continue
        key = (row["original_source_dataset"], row["split"])
        totals[key] += 1
        counts[(row["original_source_dataset"], row["split"], row["split_balance_group"])] += 1

    groups = ["normal_or_sinus_reference", "abnormal_or_cvd_positive", "mixed_normal_and_abnormal"]
    output: list[dict[str, Any]] = []
    for source_dataset, split in sorted(totals):
        total = totals[(source_dataset, split)]
        for group in groups:
            count = counts[(source_dataset, split, group)]
            output.append(
                {
                    "original_source_dataset": source_dataset,
                    "split": split,
                    "split_balance_group": group,
                    "record_count": count,
                    "included_records": total,
                    "record_fraction": count / total if total else 0,
                }
            )
    return output
