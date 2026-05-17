"""PTB-XL manifest adapter."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.normalization.adapters.common import DATA_DIR, json_dumps, json_list, normalize_sex, rel


DATASET = "ptb-xl"
ROOT = DATA_DIR / DATASET
QUALITY_COLUMNS = [
    "baseline_drift",
    "static_noise",
    "burst_noise",
    "electrodes_problems",
    "extra_beats",
    "pacemaker",
]


def _parse_wfdb_header(path: Path) -> tuple[int, int, int, str]:
    lines = path.read_text(errors="ignore").splitlines()
    first = lines[0].split()
    num_leads = int(first[1])
    sampling_rate_hz = int(float(first[2]))
    num_samples = int(first[3])
    lead_order = [line.split()[-1] for line in lines[1 : 1 + num_leads]]
    return num_leads, sampling_rate_hz, num_samples, "|".join(lead_order)


def _split_from_fold(value: Any) -> str:
    fold = int(str(value))
    if 1 <= fold <= 8:
        return "train"
    if fold == 9:
        return "val"
    if fold == 10:
        return "test"
    raise ValueError(f"Unexpected PTB-XL strat_fold={value!r}")


def _quality_flags(item: dict[str, Any]) -> str | None:
    flags = {column: str(item[column]).strip() for column in QUALITY_COLUMNS if str(item[column]).strip()}
    age = _age_at_recording(item["age"])
    if item["age"] and age is None:
        flags["age_out_of_schema_range"] = item["age"]
    return json_dumps(flags) if flags else None


def _age_at_recording(value: Any) -> float | None:
    if not str(value).strip():
        return None
    age = float(value)
    if age < 0 or age > 130:
        return None
    return age


def build_rows() -> list[dict[str, Any]]:
    metadata = pd.read_csv(ROOT / "ptbxl_database.csv", dtype=str).fillna("")
    rows: list[dict[str, Any]] = []
    for item in metadata.to_dict("records"):
        filename_hr = item["filename_hr"]
        base = ROOT / filename_hr
        header_path = base.with_suffix(".hea")
        signal_path = base.with_suffix(".dat")
        num_leads, sampling_rate_hz, num_samples, lead_order = _parse_wfdb_header(header_path)
        raw_labels = ast.literal_eval(item["scp_codes"])

        rows.append(
            {
                "original_source_dataset": DATASET,
                "record_id": str(item["ecg_id"]),
                "original_patient_id": str(item["patient_id"]),
                "patient_id_source": "source_column",
                "source_path": rel(base),
                "source_header_path": rel(header_path),
                "source_signal_path": rel(signal_path),
                "source_format": "wfdb-dat",
                "signal_key": None,
                "sampling_rate_hz": sampling_rate_hz,
                "num_leads": num_leads,
                "num_samples": num_samples,
                "duration_sec": num_samples / sampling_rate_hz,
                "lead_order": lead_order,
                "lead_order_source": "wfdb_header",
                "age_at_recording": _age_at_recording(item["age"]),
                "sex": normalize_sex(item["sex"]),
                "recorded_at": item["recording_date"] or None,
                "raw_labels": json_dumps(raw_labels),
                "raw_label_system": "scp-ecg",
                "label_provenance": "ptbxl_database.scp_codes joined through label_mapping.csv",
                "quality_flags": _quality_flags(item),
                "split": _split_from_fold(item["strat_fold"]),
                "split_source": "ptbxl_strat_fold",
            }
        )
    return rows
