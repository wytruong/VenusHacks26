"""SPH-ECG manifest adapter."""

from __future__ import annotations

from typing import Any

import pandas as pd

from scripts.normalization.adapters.common import DATA_DIR, json_dumps, normalize_sex, rel


DATASET = "sph-ecg"
ROOT = DATA_DIR / DATASET


def _aha_atoms(value: Any) -> list[str]:
    atoms: list[str] = []
    for part in str(value).split(";"):
        for atom in part.split("+"):
            atom = atom.strip()
            if atom:
                atoms.append(atom)
    return atoms


def _duration_policy(num_samples: int) -> tuple[str, str]:
    if num_samples == 5000:
        return "exact_10_seconds", "use_as_is"
    if 5000 < num_samples <= 6000:
        return "crop_first_10_seconds", "crop_first_10_seconds"
    if num_samples >= 6500:
        return "exclude_duration_ge_13_sec", "defer_for_windowing"
    return "invalid_duration_lt_10_sec", "exclude"


def build_rows() -> list[dict[str, Any]]:
    metadata = pd.read_csv(ROOT / "metadata.csv", dtype=str).fillna("")
    rows: list[dict[str, Any]] = []
    for item in metadata.to_dict("records"):
        record_id = item["ECG_ID"]
        signal_path = ROOT / "records" / f"{record_id}.h5"
        num_samples = int(item["N"])
        sampling_rate_hz = 500
        duration_policy, preprocessing_policy = _duration_policy(num_samples)
        atoms = _aha_atoms(item["AHA_Code"])

        rows.append(
            {
                "original_source_dataset": DATASET,
                "record_id": record_id,
                "original_patient_id": item["Patient_ID"],
                "patient_id_source": "source_column",
                "source_path": rel(signal_path),
                "source_header_path": None,
                "source_signal_path": rel(signal_path),
                "source_format": "hdf5",
                "signal_key": "/ecg",
                "sampling_rate_hz": sampling_rate_hz,
                "num_leads": 12,
                "num_samples": num_samples,
                "duration_sec": num_samples / sampling_rate_hz,
                "lead_order": None,
                "lead_order_source": None,
                "age_at_recording": float(item["Age"]) if item["Age"] else None,
                "sex": normalize_sex(item["Sex"]),
                "recorded_at": item["Date"] or None,
                "raw_labels": json_dumps({"AHA_Code": item["AHA_Code"], "atoms": atoms}),
                "raw_label_system": "aha",
                "label_provenance": "sph_metadata.AHA_Code joined through label_mapping.csv",
                "quality_flags": json_dumps(
                    {
                        "duration_policy": duration_policy,
                        "preprocessing_policy": preprocessing_policy,
                    }
                ),
                "split": "train",
                "split_source": None,
            }
        )
    return rows
