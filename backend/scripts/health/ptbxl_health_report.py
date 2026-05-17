#!/usr/bin/env python3
"""Generate PTB-XL health reports for 500 Hz normalization readiness."""

from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import wfdb
from rich.console import Console
from rich.table import Table


REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_ROOT = REPO_ROOT / "data" / "ptb-xl"
DERIVED_DIR = DATASET_ROOT / "derived"

EXPECTED_LEADS = [
    "I",
    "II",
    "III",
    "AVR",
    "AVL",
    "AVF",
    "V1",
    "V2",
    "V3",
    "V4",
    "V5",
    "V6",
]
QUALITY_COLUMNS = [
    "baseline_drift",
    "static_noise",
    "burst_noise",
    "electrodes_problems",
    "extra_beats",
    "pacemaker",
]


@dataclass
class HealthReport:
    dataset: str = "ptb-xl"
    safe_for_500hz_normalization: bool = True
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    records_expected: int = 0
    unique_ecg_ids: int = 0
    unique_patient_ids: int = 0
    records500_headers: int = 0
    records500_dat_files: int = 0
    records100_archived: bool = False
    label_count: int = 0
    taxonomy_label_count: int = 0
    folds_present: list[int] = field(default_factory=list)

    def add_blocker(self, message: str) -> None:
        self.blocking_issues.append(message)
        self.safe_for_500hz_normalization = False

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


def normalize_patient_id(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if text.endswith(".0"):
        return text[:-2]
    return text


def is_nonempty(value: Any) -> bool:
    if value is None or pd.isna(value):
        return False
    return bool(str(value).strip())


def read_metadata(report: HealthReport) -> pd.DataFrame | None:
    path = DATASET_ROOT / "ptbxl_database.csv"
    if not path.exists():
        report.add_blocker(f"Missing metadata file: {path}")
        return None
    return pd.read_csv(path)


def read_taxonomy(report: HealthReport) -> pd.DataFrame | None:
    path = DATASET_ROOT / "scp_statements.csv"
    if not path.exists():
        report.add_blocker(f"Missing taxonomy file: {path}")
        return None
    return pd.read_csv(path, index_col=0)


def file_inventory(report: HealthReport) -> pd.DataFrame:
    checks = [
        ("ptbxl_database_csv", DATASET_ROOT / "ptbxl_database.csv", "file"),
        ("scp_statements_csv", DATASET_ROOT / "scp_statements.csv", "file"),
        ("records500_dir", DATASET_ROOT / "records500", "dir"),
        ("records100_archive_dir", DATASET_ROOT / ".archive" / "records100", "dir"),
    ]

    rows: list[dict[str, Any]] = []
    for name, path, expected_type in checks:
        exists = path.exists()
        ok_type = path.is_file() if expected_type == "file" else path.is_dir()
        rows.append(
            {
                "check": name,
                "path": str(path.relative_to(REPO_ROOT)),
                "expected_type": expected_type,
                "exists": exists,
                "ok": exists and ok_type,
            }
        )
        if not exists or not ok_type:
            severity = report.add_warning if name == "records100_archive_dir" else report.add_blocker
            severity(f"File inventory check failed: {name} at {path}")

    records500 = DATASET_ROOT / "records500"
    header_count = len(list(records500.rglob("*.hea"))) if records500.exists() else 0
    dat_count = len(list(records500.rglob("*.dat"))) if records500.exists() else 0
    report.records500_headers = header_count
    report.records500_dat_files = dat_count
    report.records100_archived = (DATASET_ROOT / ".archive" / "records100").is_dir()

    rows.extend(
        [
            {
                "check": "records500_hea_count",
                "path": "data/ptb-xl/records500",
                "expected_type": "count",
                "exists": records500.exists(),
                "ok": True,
                "count": header_count,
            },
            {
                "check": "records500_dat_count",
                "path": "data/ptb-xl/records500",
                "expected_type": "count",
                "exists": records500.exists(),
                "ok": True,
                "count": dat_count,
            },
        ]
    )
    return pd.DataFrame(rows)


def metadata_summary(df: pd.DataFrame, report: HealthReport) -> pd.DataFrame:
    report.records_expected = len(df)
    report.unique_ecg_ids = df["ecg_id"].nunique(dropna=True)
    report.unique_patient_ids = df["patient_id"].nunique(dropna=True)

    duplicate_ecg = int(df["ecg_id"].duplicated().sum())
    missing_patient = int(df["patient_id"].isna().sum())
    missing_filename_hr = int(df["filename_hr"].isna().sum() + (df["filename_hr"].astype(str).str.strip() == "").sum())
    malformed_patient = int(
        df["patient_id"].dropna().map(lambda value: not str(value).strip().replace(".0", "").isdigit()).sum()
    )

    if duplicate_ecg:
        report.add_blocker(f"Duplicate ecg_id rows: {duplicate_ecg}")
    if missing_patient:
        report.add_blocker(f"Missing patient_id rows: {missing_patient}")
    if missing_filename_hr:
        report.add_blocker(f"Missing filename_hr rows: {missing_filename_hr}")
    if malformed_patient:
        report.add_warning(f"Malformed patient_id-like values: {malformed_patient}")

    rows = [
        ("metadata_rows", len(df)),
        ("unique_ecg_id", report.unique_ecg_ids),
        ("unique_patient_id", report.unique_patient_ids),
        ("duplicate_ecg_id_rows", duplicate_ecg),
        ("missing_patient_id_rows", missing_patient),
        ("missing_filename_hr_rows", missing_filename_hr),
        ("malformed_patient_id_rows", malformed_patient),
        ("float_like_patient_id_rows", int(df["patient_id"].dropna().map(lambda value: str(value).strip().endswith(".0")).sum())),
    ]
    return pd.DataFrame(rows, columns=["metric", "value"])


def path_issues(df: pd.DataFrame, report: HealthReport) -> pd.DataFrame:
    issues: list[dict[str, Any]] = []
    for row in df.itertuples(index=False):
        filename_hr = str(getattr(row, "filename_hr", "")).strip()
        ecg_id = getattr(row, "ecg_id", "")
        if not filename_hr or filename_hr == "nan":
            issues.append({"ecg_id": ecg_id, "issue": "missing_filename_hr", "filename_hr": filename_hr})
            continue
        if not filename_hr.startswith("records500/"):
            issues.append({"ecg_id": ecg_id, "issue": "filename_hr_not_records500", "filename_hr": filename_hr})
        if filename_hr.startswith("records100/") or "_lr" in filename_hr:
            issues.append({"ecg_id": ecg_id, "issue": "filename_hr_points_to_low_rate_record", "filename_hr": filename_hr})

        base = DATASET_ROOT / filename_hr
        if not base.with_suffix(".hea").exists():
            issues.append({"ecg_id": ecg_id, "issue": "missing_hea", "filename_hr": filename_hr})
        if not base.with_suffix(".dat").exists():
            issues.append({"ecg_id": ecg_id, "issue": "missing_dat", "filename_hr": filename_hr})

    if issues:
        report.add_blocker(f"500 Hz path issues found: {len(issues)}")
    return pd.DataFrame(issues, columns=["ecg_id", "issue", "filename_hr"])


def header_issues(df: pd.DataFrame, report: HealthReport) -> pd.DataFrame:
    issues: list[dict[str, Any]] = []
    checked = 0
    for row in df.itertuples(index=False):
        filename_hr = str(getattr(row, "filename_hr", "")).strip()
        if not filename_hr or filename_hr == "nan":
            continue
        record_path = DATASET_ROOT / filename_hr
        if not record_path.with_suffix(".hea").exists():
            continue
        checked += 1
        try:
            header = wfdb.rdheader(str(record_path))
        except Exception as exc:  # noqa: BLE001 - report exact data issue.
            issues.append({"ecg_id": getattr(row, "ecg_id", ""), "filename_hr": filename_hr, "issue": "rdheader_failed", "value": repr(exc)})
            continue

        checks = [
            ("n_sig", header.n_sig, 12),
            ("fs", int(header.fs), 500),
            ("sig_len", header.sig_len, 5000),
        ]
        for field_name, actual, expected in checks:
            if actual != expected:
                issues.append(
                    {
                        "ecg_id": getattr(row, "ecg_id", ""),
                        "filename_hr": filename_hr,
                        "issue": f"unexpected_{field_name}",
                        "value": actual,
                        "expected": expected,
                    }
                )
        sig_name = list(header.sig_name or [])
        if sig_name != EXPECTED_LEADS:
            issues.append(
                {
                    "ecg_id": getattr(row, "ecg_id", ""),
                    "filename_hr": filename_hr,
                    "issue": "unexpected_lead_order",
                    "value": "|".join(sig_name),
                    "expected": "|".join(EXPECTED_LEADS),
                }
            )

    if checked != len(df):
        report.add_warning(f"Checked {checked} WFDB headers for {len(df)} metadata rows")
    if issues:
        report.add_blocker(f"WFDB header issues found: {len(issues)}")
    return pd.DataFrame(issues, columns=["ecg_id", "filename_hr", "issue", "value", "expected"])


def label_inventory(df: pd.DataFrame, taxonomy: pd.DataFrame, report: HealthReport) -> pd.DataFrame:
    label_counts: dict[str, int] = {}
    parse_errors: list[dict[str, Any]] = []
    for row in df.itertuples(index=False):
        raw = getattr(row, "scp_codes", "")
        try:
            labels = ast.literal_eval(raw)
        except Exception as exc:  # noqa: BLE001 - report exact data issue.
            parse_errors.append({"ecg_id": getattr(row, "ecg_id", ""), "scp_codes": raw, "error": repr(exc)})
            continue
        if not isinstance(labels, dict):
            parse_errors.append({"ecg_id": getattr(row, "ecg_id", ""), "scp_codes": raw, "error": "not_a_dict"})
            continue
        for label in labels:
            label_counts[label] = label_counts.get(label, 0) + 1

    if parse_errors:
        report.add_blocker(f"scp_codes parse errors found: {len(parse_errors)}")
        pd.DataFrame(parse_errors).to_csv(DERIVED_DIR / "label_parse_issues.csv", index=False)

    taxonomy_codes = set(taxonomy.index.astype(str))
    missing_taxonomy = sorted(set(label_counts) - taxonomy_codes)
    if missing_taxonomy:
        report.add_blocker(f"Labels missing from scp_statements.csv: {len(missing_taxonomy)}")

    report.label_count = len(label_counts)
    report.taxonomy_label_count = len(taxonomy)

    rows: list[dict[str, Any]] = []
    for label, count in sorted(label_counts.items(), key=lambda item: (-item[1], item[0])):
        tax = taxonomy.loc[label] if label in taxonomy.index else pd.Series(dtype=object)
        rows.append(
            {
                "label": label,
                "record_count": count,
                "taxonomy_present": label in taxonomy.index,
                "description": tax.get("description", np.nan),
                "diagnostic": tax.get("diagnostic", np.nan),
                "form": tax.get("form", np.nan),
                "rhythm": tax.get("rhythm", np.nan),
                "diagnostic_class": tax.get("diagnostic_class", np.nan),
                "diagnostic_subclass": tax.get("diagnostic_subclass", np.nan),
            }
        )
    return pd.DataFrame(rows)


def fold_summary(df: pd.DataFrame, report: HealthReport) -> pd.DataFrame:
    fold_values = sorted(int(value) for value in df["strat_fold"].dropna().unique())
    report.folds_present = fold_values
    invalid = sorted(set(fold_values) - set(range(1, 11)))
    if invalid:
        report.add_blocker(f"Invalid strat_fold values: {invalid}")

    rows: list[dict[str, Any]] = []
    for fold, group in df.groupby("strat_fold", dropna=False):
        split = "train" if fold in range(1, 9) else "val" if fold == 9 else "test" if fold == 10 else "invalid"
        rows.append(
            {
                "strat_fold": fold,
                "split": split,
                "record_count": len(group),
                "unique_patient_count": group["patient_id"].nunique(dropna=True),
            }
        )

    fold_patients: dict[int, set[str]] = {}
    for fold, group in df.groupby("strat_fold"):
        fold_patients[int(fold)] = {str(value) for value in group["patient_id"].dropna()}
    overlaps: list[dict[str, Any]] = []
    for left in sorted(fold_patients):
        for right in sorted(fold_patients):
            if left >= right:
                continue
            overlap = fold_patients[left] & fold_patients[right]
            if overlap:
                overlaps.append({"left_fold": left, "right_fold": right, "overlap_patient_count": len(overlap)})
    if overlaps:
        report.add_blocker(f"Patient overlap across strat_fold values: {len(overlaps)} fold pairs")
        pd.DataFrame(overlaps).to_csv(DERIVED_DIR / "fold_patient_overlap.csv", index=False)

    return pd.DataFrame(rows).sort_values("strat_fold")


def quality_metadata_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in QUALITY_COLUMNS:
        if column not in df:
            rows.append({"column": column, "present": False, "missing_count": np.nan, "nonempty_count": np.nan, "unique_nonempty_values": np.nan})
            continue
        values = df[column]
        nonempty = values.map(is_nonempty)
        rows.append(
            {
                "column": column,
                "present": True,
                "missing_count": int(values.isna().sum()),
                "nonempty_count": int(nonempty.sum()),
                "unique_nonempty_values": int(values[nonempty].nunique(dropna=True)),
            }
        )
    return pd.DataFrame(rows)


def write_json_report(report: HealthReport) -> None:
    path = DERIVED_DIR / "health_report.json"
    path.write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")


def print_summary(report: HealthReport) -> None:
    console = Console()
    status = "PASS" if report.safe_for_500hz_normalization else "FAIL"
    table = Table(title=f"PTB-XL 500 Hz Health Report: {status}")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("safe_for_500hz_normalization", str(report.safe_for_500hz_normalization))
    table.add_row("records_expected", str(report.records_expected))
    table.add_row("unique_ecg_ids", str(report.unique_ecg_ids))
    table.add_row("unique_patient_ids", str(report.unique_patient_ids))
    table.add_row("records500_headers", str(report.records500_headers))
    table.add_row("records500_dat_files", str(report.records500_dat_files))
    table.add_row("records100_archived", str(report.records100_archived))
    table.add_row("label_count", str(report.label_count))
    table.add_row("taxonomy_label_count", str(report.taxonomy_label_count))
    table.add_row("folds_present", ",".join(map(str, report.folds_present)))
    console.print(table)

    if report.blocking_issues:
        issue_table = Table(title="Blocking Issues")
        issue_table.add_column("Issue")
        for issue in report.blocking_issues:
            issue_table.add_row(issue)
        console.print(issue_table)

    if report.warnings:
        warning_table = Table(title="Warnings")
        warning_table.add_column("Warning")
        for warning in report.warnings:
            warning_table.add_row(warning)
        console.print(warning_table)


def main() -> int:
    DERIVED_DIR.mkdir(parents=True, exist_ok=True)
    report = HealthReport()

    inventory = file_inventory(report)
    inventory.to_csv(DERIVED_DIR / "file_inventory.csv", index=False)

    metadata = read_metadata(report)
    taxonomy = read_taxonomy(report)
    if metadata is None or taxonomy is None:
        write_json_report(report)
        print_summary(report)
        return 1

    metadata_summary(metadata, report).to_csv(DERIVED_DIR / "metadata_summary.csv", index=False)
    path_issues(metadata, report).to_csv(DERIVED_DIR / "path_issues.csv", index=False)
    header_issues(metadata, report).to_csv(DERIVED_DIR / "header_issues.csv", index=False)
    label_inventory(metadata, taxonomy, report).to_csv(DERIVED_DIR / "label_inventory.csv", index=False)
    fold_summary(metadata, report).to_csv(DERIVED_DIR / "fold_summary.csv", index=False)
    quality_metadata_summary(metadata).to_csv(DERIVED_DIR / "quality_metadata_summary.csv", index=False)

    write_json_report(report)
    print_summary(report)
    return 0 if report.safe_for_500hz_normalization else 1


if __name__ == "__main__":
    raise SystemExit(main())
