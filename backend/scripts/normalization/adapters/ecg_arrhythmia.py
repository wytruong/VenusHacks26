"""ECG Arrhythmia / Chapman-Ningbo manifest adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from scripts.normalization.adapters.common import DATA_DIR, json_dumps, normalize_sex, rel


DATASET = "ecg-arrhythmia"
ROOT = DATA_DIR / DATASET


def _parse_comments(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in path.read_text(errors="ignore").splitlines():
        if not line.startswith("#") or ":" not in line:
            continue
        key, value = line[1:].split(":", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _parse_wfdb_header(path: Path) -> tuple[int, int, int, str]:
    lines = path.read_text(errors="ignore").splitlines()
    first = lines[0].split()
    num_leads = int(first[1])
    sampling_rate_hz = int(float(first[2]))
    num_samples = int(first[3])
    lead_order = [line.split()[-1] for line in lines[1 : 1 + num_leads]]
    return num_leads, sampling_rate_hz, num_samples, "|".join(lead_order)


def _load_overrides() -> dict[str, dict[str, str]]:
    path = ROOT / "derived" / "header_overrides.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str).fillna("")
    return {str(item["record_id"]): item for item in df.to_dict("records")}


def _quality_flags(record_id: str, override: dict[str, str] | None) -> str | None:
    if override is None:
        return None
    return json_dumps(
        {
            "header_override": True,
            "override_issue": override["issue"],
            "override_notes": override["notes"],
        }
    )


def build_rows() -> list[dict[str, Any]]:
    overrides = _load_overrides()
    rows: list[dict[str, Any]] = []
    for header_path in sorted((ROOT / "WFDBRecords").rglob("*.hea")):
        record_id = header_path.stem
        signal_path = header_path.with_suffix(".mat")
        base_path = header_path.with_suffix("")
        comments = _parse_comments(header_path)
        override = overrides.get(record_id)

        if override is not None:
            num_leads = int(override["num_leads"])
            sampling_rate_hz = int(override["sampling_rate_hz"])
            num_samples = int(override["num_samples"])
            lead_order = override["lead_order"]
        else:
            num_leads, sampling_rate_hz, num_samples, lead_order = _parse_wfdb_header(header_path)

        dx = comments.get("Dx", "")
        dx_atoms = [atom.strip() for atom in dx.split(",") if atom.strip()]

        rows.append(
            {
                "original_source_dataset": DATASET,
                "record_id": record_id,
                "original_patient_id": f"ecg-arrhythmia:{record_id}",
                "patient_id_source": "record_id_matches_one_record_per_patient_dataset_description",
                "source_path": rel(base_path),
                "source_header_path": rel(header_path),
                "source_signal_path": rel(signal_path),
                "source_format": "wfdb-mat",
                "signal_key": None,
                "sampling_rate_hz": sampling_rate_hz,
                "num_leads": num_leads,
                "num_samples": num_samples,
                "duration_sec": num_samples / sampling_rate_hz,
                "lead_order": lead_order,
                "lead_order_source": "wfdb_header",
                "age_at_recording": float(comments["Age"]) if comments.get("Age", "").isdigit() else None,
                "sex": normalize_sex(comments.get("Sex", "")),
                "recorded_at": None,
                "raw_labels": json_dumps({"Dx": dx_atoms}),
                "raw_label_system": "snomed-ct",
                "label_provenance": "wfdb_header_dx joined through label_mapping.csv",
                "quality_flags": _quality_flags(record_id, override),
                "split": "train",
                "split_source": None,
            }
        )
    return rows
