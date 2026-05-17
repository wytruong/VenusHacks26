#!/usr/bin/env python3
"""Generate SPH-ECG health reports for normalization readiness."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table


REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_ROOT = REPO_ROOT / "data" / "sph-ecg"
RECORDS_ROOT = DATASET_ROOT / "records"
DERIVED_DIR = DATASET_ROOT / "derived"
SAMPLE_RATE_HZ = 500


@dataclass
class HealthReport:
    dataset: str = "sph-ecg"
    safe_for_normalization: bool = True
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata_rows: int = 0
    h5_files: int = 0
    unique_ecg_ids: int = 0
    unique_patient_ids: int = 0
    multi_record_patients: int = 0
    label_atom_count: int = 0
    taxonomy_label_count: int = 0
    label_mapping_coverage: str = "0/0"
    ten_second_records: int = 0
    variable_length_records: int = 0

    def add_blocker(self, message: str) -> None:
        self.blocking_issues.append(message)
        self.safe_for_normalization = False

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


def read_csv_if_exists(path: Path, report: HealthReport, name: str) -> pd.DataFrame | None:
    if not path.exists():
        report.add_blocker(f"Missing {name}: {path}")
        return None
    return pd.read_csv(path)


def file_inventory(report: HealthReport) -> pd.DataFrame:
    checks = [
        ("metadata_csv", DATASET_ROOT / "metadata.csv", "file"),
        ("code_csv", DATASET_ROOT / "code.csv", "file"),
        ("records_dir", RECORDS_ROOT, "dir"),
        ("example_code_pdf", DATASET_ROOT / "example-code.pdf", "file"),
        ("rule_pdf", DATASET_ROOT / "rule.pdf", "file"),
    ]
    rows: list[dict[str, Any]] = []
    for name, path, expected_type in checks:
        exists = path.exists()
        ok_type = path.is_file() if expected_type == "file" else path.is_dir()
        ok = exists and ok_type
        rows.append(
            {
                "check": name,
                "path": str(path.relative_to(REPO_ROOT)),
                "expected_type": expected_type,
                "exists": exists,
                "ok": ok,
            }
        )
        if not ok and name in {"metadata_csv", "code_csv", "records_dir"}:
            report.add_blocker(f"File inventory check failed: {name} at {path}")
        elif not ok:
            report.add_warning(f"Optional documentation file missing: {name} at {path}")
    report.h5_files = len(list(RECORDS_ROOT.glob("*.h5"))) if RECORDS_ROOT.exists() else 0
    rows.append({"check": "h5_count", "path": "data/sph-ecg/records", "expected_type": "count", "exists": RECORDS_ROOT.exists(), "ok": True, "count": report.h5_files})
    return pd.DataFrame(rows)


def metadata_summary(metadata: pd.DataFrame, report: HealthReport) -> pd.DataFrame:
    report.metadata_rows = len(metadata)
    report.unique_ecg_ids = metadata["ECG_ID"].nunique(dropna=True)
    report.unique_patient_ids = metadata["Patient_ID"].nunique(dropna=True)
    patient_counts = metadata["Patient_ID"].value_counts()
    report.multi_record_patients = int((patient_counts > 1).sum())
    duplicate_ecg = int(metadata["ECG_ID"].duplicated().sum())
    missing_patient = int(metadata["Patient_ID"].isna().sum())
    missing_label = int(metadata["AHA_Code"].isna().sum())
    missing_n = int(metadata["N"].isna().sum())

    for count, message in [
        (duplicate_ecg, "Duplicate ECG_ID rows"),
        (missing_patient, "Missing Patient_ID rows"),
        (missing_label, "Missing AHA_Code rows"),
        (missing_n, "Missing N rows"),
    ]:
        if count:
            report.add_blocker(f"{message}: {count}")

    rows = [
        ("metadata_rows", report.metadata_rows),
        ("unique_ecg_id", report.unique_ecg_ids),
        ("unique_patient_id", report.unique_patient_ids),
        ("duplicate_ecg_id_rows", duplicate_ecg),
        ("missing_patient_id_rows", missing_patient),
        ("missing_aha_code_rows", missing_label),
        ("missing_n_rows", missing_n),
        ("multi_record_patients", report.multi_record_patients),
        ("records_from_multi_record_patients", int(metadata["Patient_ID"].isin(patient_counts[patient_counts > 1].index).sum())),
    ]
    return pd.DataFrame(rows, columns=["metric", "value"])


def path_and_signal_checks(metadata: pd.DataFrame, report: HealthReport) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    h5_files = {path.stem: path for path in RECORDS_ROOT.glob("*.h5")} if RECORDS_ROOT.exists() else {}
    metadata_ids = set(metadata["ECG_ID"].astype(str))
    issues: list[dict[str, Any]] = []
    signal_rows: list[dict[str, Any]] = []

    for row in metadata.itertuples(index=False):
        ecg_id = str(row.ECG_ID)
        path = RECORDS_ROOT / f"{ecg_id}.h5"
        if not path.exists():
            issues.append({"ecg_id": ecg_id, "issue": "missing_h5", "path": str(path.relative_to(REPO_ROOT))})
            continue
        try:
            with h5py.File(path, "r") as handle:
                if "ecg" not in handle:
                    issues.append({"ecg_id": ecg_id, "issue": "missing_ecg_dataset", "path": str(path.relative_to(REPO_ROOT))})
                    continue
                dataset = handle["ecg"]
                shape = tuple(dataset.shape)
                dtype = str(dataset.dtype)
                compression = dataset.compression
        except Exception as exc:  # noqa: BLE001
            issues.append({"ecg_id": ecg_id, "issue": "h5_read_failed", "path": str(path.relative_to(REPO_ROOT)), "value": repr(exc)})
            continue

        expected_n = int(row.N)
        if len(shape) != 2 or shape[0] != 12:
            issues.append({"ecg_id": ecg_id, "issue": "unexpected_shape", "path": str(path.relative_to(REPO_ROOT)), "value": str(shape), "expected": f"(12, {expected_n})"})
        elif shape[1] != expected_n:
            issues.append({"ecg_id": ecg_id, "issue": "n_mismatch", "path": str(path.relative_to(REPO_ROOT)), "value": shape[1], "expected": expected_n})

        signal_rows.append(
            {
                "ecg_id": ecg_id,
                "path": str(path.relative_to(DATASET_ROOT)),
                "shape": str(shape),
                "dtype": dtype,
                "compression": compression,
                "metadata_n": expected_n,
                "duration_sec": expected_n / SAMPLE_RATE_HZ,
            }
        )

    for h5_id, h5_path in h5_files.items():
        if h5_id not in metadata_ids:
            issues.append({"ecg_id": h5_id, "issue": "h5_without_metadata", "path": str(h5_path.relative_to(REPO_ROOT))})

    if issues:
        blocking = [issue for issue in issues if issue["issue"] != "h5_without_metadata"]
        if blocking:
            report.add_blocker(f"HDF5 path/signal issues found: {len(blocking)}")
        extras = len(issues) - len(blocking)
        if extras:
            report.add_warning(f"HDF5 files without metadata rows: {extras}")

    signal_df = pd.DataFrame(signal_rows)
    if not signal_df.empty:
        durations = signal_df["duration_sec"].astype(float)
        report.ten_second_records = int((signal_df["metadata_n"].astype(int) == 5000).sum())
        report.variable_length_records = int((signal_df["metadata_n"].astype(int) != 5000).sum())
        duration_summary = pd.DataFrame(
            [
                ("min_duration_sec", float(durations.min())),
                ("median_duration_sec", float(durations.median())),
                ("max_duration_sec", float(durations.max())),
                ("ten_second_records", report.ten_second_records),
                ("variable_length_records", report.variable_length_records),
            ],
            columns=["metric", "value"],
        )
    else:
        duration_summary = pd.DataFrame(columns=["metric", "value"])
    return pd.DataFrame(issues, columns=["ecg_id", "issue", "path", "value", "expected"]), signal_df, duration_summary


def parse_aha_atoms(value: Any) -> tuple[list[str], list[str], list[str]]:
    raw_parts = [part.strip() for part in str(value).split(";") if part.strip()]
    primary: list[str] = []
    modifiers: list[str] = []
    atoms: list[str] = []
    for part in raw_parts:
        for atom in [piece.strip() for piece in part.split("+") if piece.strip()]:
            atoms.append(atom)
            try:
                numeric = int(atom)
            except ValueError:
                primary.append(atom)
                continue
            if 200 <= numeric < 500:
                modifiers.append(atom)
            else:
                primary.append(atom)
    return atoms, primary, modifiers


def label_inventory(metadata: pd.DataFrame, code: pd.DataFrame, report: HealthReport) -> pd.DataFrame:
    taxonomy_codes = set(code["Code"].astype(str).str.strip())
    code_by_id = code.assign(Code=code["Code"].astype(str).str.strip()).set_index("Code")
    counts: dict[str, int] = {}
    primary_counts: dict[str, int] = {}
    modifier_counts: dict[str, int] = {}
    full_counts = metadata["AHA_Code"].astype(str).value_counts()

    for raw in metadata["AHA_Code"]:
        atoms, primary, modifiers = parse_aha_atoms(raw)
        for atom in atoms:
            counts[atom] = counts.get(atom, 0) + 1
        for atom in primary:
            primary_counts[atom] = primary_counts.get(atom, 0) + 1
        for atom in modifiers:
            modifier_counts[atom] = modifier_counts.get(atom, 0) + 1

    report.label_atom_count = len(counts)
    report.taxonomy_label_count = len(taxonomy_codes)
    missing = sorted(set(counts) - taxonomy_codes)
    report.label_mapping_coverage = f"{len(set(counts) & taxonomy_codes)}/{len(counts)}"
    if missing:
        report.add_blocker(f"AHA label atoms missing from code.csv: {len(missing)}")

    rows: list[dict[str, Any]] = []
    for atom, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        mapped = code_by_id.loc[atom] if atom in code_by_id.index else pd.Series(dtype=object)
        rows.append(
            {
                "code": atom,
                "record_count": count,
                "taxonomy_present": atom in taxonomy_codes,
                "category": mapped.get("Category", ""),
                "description": mapped.get("Description", ""),
                "is_modifier": atom in modifier_counts,
                "primary_count": primary_counts.get(atom, 0),
                "modifier_count": modifier_counts.get(atom, 0),
            }
        )

    full_counts.rename_axis("raw_aha_code").reset_index(name="record_count").to_csv(DERIVED_DIR / "raw_label_combinations.csv", index=False)
    return pd.DataFrame(rows)


def split_readiness(metadata: pd.DataFrame) -> pd.DataFrame:
    patient_counts = metadata["Patient_ID"].value_counts()
    multi_patients = patient_counts[patient_counts > 1]
    return pd.DataFrame(
        [
            {"metric": "record_count", "value": len(metadata)},
            {"metric": "unique_patient_count", "value": metadata["Patient_ID"].nunique()},
            {"metric": "multi_record_patient_count", "value": len(multi_patients)},
            {"metric": "multi_record_patient_record_count", "value": int(metadata["Patient_ID"].isin(multi_patients.index).sum())},
            {"metric": "recommended_split_source", "value": "sph_example_code_patient_split"},
        ]
    )


def write_json_report(report: HealthReport) -> None:
    (DERIVED_DIR / "health_report.json").write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")


def print_summary(report: HealthReport) -> None:
    console = Console()
    status = "PASS" if report.safe_for_normalization else "FAIL"
    table = Table(title=f"SPH-ECG Health Report: {status}")
    table.add_column("Metric")
    table.add_column("Value")
    for key, value in asdict(report).items():
        if key in {"blocking_issues", "warnings"}:
            continue
        table.add_row(key, str(value))
    console.print(table)
    for title, items in [("Blocking Issues", report.blocking_issues), ("Warnings", report.warnings)]:
        if items:
            item_table = Table(title=title)
            item_table.add_column("Message")
            for item in items:
                item_table.add_row(item)
            console.print(item_table)


def main() -> int:
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    report = HealthReport()
    file_inventory(report).to_csv(DERIVED_DIR / "file_inventory.csv", index=False)
    metadata = read_csv_if_exists(DATASET_ROOT / "metadata.csv", report, "metadata.csv")
    code = read_csv_if_exists(DATASET_ROOT / "code.csv", report, "code.csv")
    if metadata is None or code is None:
        write_json_report(report)
        print_summary(report)
        return 1

    metadata_summary(metadata, report).to_csv(DERIVED_DIR / "metadata_summary.csv", index=False)
    signal_issues, signal_inventory, duration_summary = path_and_signal_checks(metadata, report)
    path_issue_types = {"missing_h5", "h5_without_metadata"}
    path_issues = signal_issues[signal_issues["issue"].isin(path_issue_types)] if not signal_issues.empty else pd.DataFrame(columns=signal_issues.columns)
    path_issues.to_csv(DERIVED_DIR / "path_issues.csv", index=False)
    signal_issues.to_csv(DERIVED_DIR / "header_or_signal_issues.csv", index=False)
    signal_inventory.to_csv(DERIVED_DIR / "signal_inventory.csv", index=False)
    duration_summary.to_csv(DERIVED_DIR / "duration_summary.csv", index=False)
    label_inventory(metadata, code, report).to_csv(DERIVED_DIR / "label_inventory.csv", index=False)
    split_readiness(metadata).to_csv(DERIVED_DIR / "split_readiness.csv", index=False)
    write_json_report(report)
    print_summary(report)
    return 0 if report.safe_for_normalization else 1


if __name__ == "__main__":
    raise SystemExit(main())
