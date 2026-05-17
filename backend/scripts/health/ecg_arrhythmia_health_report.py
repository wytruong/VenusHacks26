#!/usr/bin/env python3
"""Generate ECG Arrhythmia / Chapman-Ningbo health reports."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import wfdb
from rich.console import Console
from rich.table import Table


REPO_ROOT = Path(__file__).resolve().parents[2]
DATASET_ROOT = REPO_ROOT / "data" / "ecg-arrhythmia"
RECORDS_ROOT = DATASET_ROOT / "WFDBRecords"
DERIVED_DIR = DATASET_ROOT / "derived"
HEADER_OVERRIDES_PATH = DERIVED_DIR / "header_overrides.csv"

EXPECTED_LEADS = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
HEADER_COMMENT_FIELDS = ["Age", "Sex", "Dx", "Rx", "Hx", "Sx"]


@dataclass
class HealthReport:
    dataset: str = "ecg-arrhythmia"
    safe_for_normalization: bool = True
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    header_files: int = 0
    mat_files: int = 0
    unique_record_ids: int = 0
    unique_patient_ids: int = 0
    raw_label_count: int = 0
    complete_mapping_label_count: int = 0
    local_mapping_label_count: int = 0
    complete_mapping_coverage: str = "0/0"

    def add_blocker(self, message: str) -> None:
        self.blocking_issues.append(message)
        self.safe_for_normalization = False

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)


def read_csv_if_exists(path: Path, report: HealthReport, name: str, **kwargs: Any) -> pd.DataFrame | None:
    if not path.exists():
        report.add_blocker(f"Missing {name}: {path}")
        return None
    return pd.read_csv(path, **kwargs)


def file_inventory(report: HealthReport) -> pd.DataFrame:
    checks = [
        ("wfdb_records_dir", RECORDS_ROOT, "dir"),
        ("records_file", DATASET_ROOT / "RECORDS", "file"),
        ("original_condition_names", DATASET_ROOT / "ConditionNames_SNOMED-CT.csv", "file"),
        ("complete_condition_names", DERIVED_DIR / "ConditionNames_SNOMED-CT_complete.csv", "file"),
        ("header_overrides", HEADER_OVERRIDES_PATH, "file"),
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
        if not ok:
            report.add_blocker(f"File inventory check failed: {name} at {path}")

    hea_files = list(RECORDS_ROOT.rglob("*.hea")) if RECORDS_ROOT.exists() else []
    mat_files = list(RECORDS_ROOT.rglob("*.mat")) if RECORDS_ROOT.exists() else []
    report.header_files = len(hea_files)
    report.mat_files = len(mat_files)
    report.unique_record_ids = len({path.stem for path in hea_files})
    report.unique_patient_ids = report.unique_record_ids

    rows.extend(
        [
            {"check": "hea_count", "path": "data/ecg-arrhythmia/WFDBRecords", "expected_type": "count", "exists": RECORDS_ROOT.exists(), "ok": True, "count": report.header_files},
            {"check": "mat_count", "path": "data/ecg-arrhythmia/WFDBRecords", "expected_type": "count", "exists": RECORDS_ROOT.exists(), "ok": True, "count": report.mat_files},
            {"check": "unique_record_id_count", "path": "data/ecg-arrhythmia/WFDBRecords", "expected_type": "count", "exists": RECORDS_ROOT.exists(), "ok": True, "count": report.unique_record_ids},
        ]
    )
    if report.header_files != report.mat_files:
        report.add_blocker(f"Header/mat file count mismatch: {report.header_files} .hea vs {report.mat_files} .mat")
    return pd.DataFrame(rows)


def parse_header_comments(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in path.read_text(errors="ignore").splitlines():
        if not line.startswith("#") or ":" not in line:
            continue
        key, value = line[1:].split(":", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def metadata_and_path_checks(report: HealthReport) -> tuple[pd.DataFrame, pd.DataFrame]:
    hea_files = sorted(RECORDS_ROOT.rglob("*.hea"))
    mat_stems = {path.stem: path for path in RECORDS_ROOT.rglob("*.mat")}
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    for hea in hea_files:
        record_id = hea.stem
        comments = parse_header_comments(hea)
        mat = hea.with_suffix(".mat")
        if not mat.exists():
            issues.append({"record_id": record_id, "issue": "missing_mat", "path": str(mat.relative_to(REPO_ROOT))})
        for field_name in HEADER_COMMENT_FIELDS:
            if field_name not in comments:
                severity = "missing_dx" if field_name == "Dx" else f"missing_{field_name.lower()}"
                issues.append({"record_id": record_id, "issue": severity, "path": str(hea.relative_to(REPO_ROOT))})
        rows.append(
            {
                "record_id": record_id,
                "original_patient_id": f"ecg-arrhythmia:{record_id}",
                "hea_path": str(hea.relative_to(DATASET_ROOT)),
                "mat_path": str(mat.relative_to(DATASET_ROOT)),
                "age": comments.get("Age"),
                "sex": comments.get("Sex"),
                "dx": comments.get("Dx"),
                "rx": comments.get("Rx"),
                "hx": comments.get("Hx"),
                "sx": comments.get("Sx"),
            }
        )

    hea_stems = {path.stem for path in hea_files}
    for mat_stem, mat_path in mat_stems.items():
        if mat_stem not in hea_stems:
            issues.append({"record_id": mat_stem, "issue": "missing_hea", "path": str(mat_path.relative_to(REPO_ROOT))})

    duplicate_ids = len(hea_files) - len(hea_stems)
    if duplicate_ids:
        report.add_blocker(f"Duplicate header record IDs: {duplicate_ids}")
    missing_dx = sum(1 for issue in issues if issue["issue"] == "missing_dx")
    if missing_dx:
        report.add_blocker(f"Records missing #Dx: {missing_dx}")
    paired_issues = [issue for issue in issues if issue["issue"] in {"missing_mat", "missing_hea"}]
    if paired_issues:
        report.add_blocker(f"WFDB pair issues found: {len(paired_issues)}")

    return pd.DataFrame(rows), pd.DataFrame(issues, columns=["record_id", "issue", "path"])


def header_checks(metadata: pd.DataFrame, report: HealthReport) -> pd.DataFrame:
    issues: list[dict[str, Any]] = []
    override_ids: set[str] = set()
    if HEADER_OVERRIDES_PATH.exists():
        overrides = pd.read_csv(HEADER_OVERRIDES_PATH, dtype=str).fillna("")
        override_ids = set(overrides["record_id"].astype(str))
    for row in metadata.itertuples(index=False):
        if row.record_id in override_ids:
            continue
        record_base = DATASET_ROOT / str(row.hea_path).removesuffix(".hea")
        try:
            header = wfdb.rdheader(str(record_base))
        except Exception as exc:  # noqa: BLE001
            issues.append({"record_id": row.record_id, "issue": "rdheader_failed", "value": repr(exc), "expected": ""})
            continue

        checks = [
            ("n_sig", header.n_sig, 12),
            ("fs", int(header.fs), 500),
            ("sig_len", header.sig_len, 5000),
        ]
        for field_name, actual, expected in checks:
            if actual != expected:
                issues.append({"record_id": row.record_id, "issue": f"unexpected_{field_name}", "value": actual, "expected": expected})
        sig_name = list(header.sig_name or [])
        if sig_name != EXPECTED_LEADS:
            issues.append({"record_id": row.record_id, "issue": "unexpected_lead_order", "value": "|".join(sig_name), "expected": "|".join(EXPECTED_LEADS)})

    if issues:
        # Known malformed headers should remain visible. Any true signal-shape mismatch is blocking.
        signal_shape_issues = [issue for issue in issues if issue["issue"] in {"unexpected_n_sig", "unexpected_fs", "unexpected_sig_len"}]
        if signal_shape_issues:
            report.add_blocker(f"WFDB header signal issues found: {len(signal_shape_issues)}")
        else:
            report.add_warning(f"WFDB header non-blocking issues found: {len(issues)}")
    return pd.DataFrame(issues, columns=["record_id", "issue", "value", "expected"])


def label_inventory(metadata: pd.DataFrame, report: HealthReport) -> pd.DataFrame:
    local = read_csv_if_exists(DATASET_ROOT / "ConditionNames_SNOMED-CT.csv", report, "original condition mapping", encoding="utf-8-sig", dtype=str)
    complete = read_csv_if_exists(DERIVED_DIR / "ConditionNames_SNOMED-CT_complete.csv", report, "complete condition mapping", dtype=str)
    if local is None or complete is None:
        return pd.DataFrame()

    local["Snomed_CT"] = local["Snomed_CT"].astype(str).str.strip()
    complete["snomed_ct_code"] = complete["snomed_ct_code"].astype(str).str.strip()
    local_codes = set(local["Snomed_CT"])
    complete_codes = set(complete["snomed_ct_code"])
    report.local_mapping_label_count = len(local_codes)
    report.complete_mapping_label_count = len(complete_codes)

    counts: dict[str, int] = {}
    for dx in metadata["dx"].dropna():
        for code in str(dx).split(","):
            code = code.strip()
            if code:
                counts[code] = counts.get(code, 0) + 1
    report.raw_label_count = len(counts)

    missing_complete = sorted(set(counts) - complete_codes)
    if missing_complete:
        report.add_blocker(f"SNOMED codes missing from complete mapping: {len(missing_complete)}")
    report.complete_mapping_coverage = f"{len(set(counts) & complete_codes)}/{len(counts)}"

    complete_by_code = complete.set_index("snomed_ct_code", drop=False)
    rows: list[dict[str, Any]] = []
    for code, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        mapped = complete_by_code.loc[code] if code in complete_by_code.index else pd.Series(dtype=object)
        rows.append(
            {
                "snomed_ct_code": code,
                "record_count": count,
                "local_mapping_present": code in local_codes,
                "complete_mapping_present": code in complete_codes,
                "abbreviation": mapped.get("abbreviation", ""),
                "description": mapped.get("description", ""),
                "challenge_label_set": mapped.get("challenge_label_set", ""),
                "source": mapped.get("source", ""),
            }
        )
    return pd.DataFrame(rows)


def split_readiness(metadata: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"metric": "record_count", "value": len(metadata)},
            {"metric": "unique_original_patient_id", "value": metadata["original_patient_id"].nunique()},
            {"metric": "record_id_as_patient_id_ready", "value": metadata["record_id"].nunique() == len(metadata)},
            {"metric": "recommended_split_source", "value": "generated_patient_hash_split_from_record_id"},
        ]
    )


def write_json_report(report: HealthReport) -> None:
    (DERIVED_DIR / "health_report.json").write_text(json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")


def print_summary(report: HealthReport) -> None:
    console = Console()
    status = "PASS" if report.safe_for_normalization else "FAIL"
    table = Table(title=f"ECG Arrhythmia Health Report: {status}")
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
    metadata, path_issues = metadata_and_path_checks(report)
    metadata.to_csv(DERIVED_DIR / "metadata_summary.csv", index=False)
    path_issues.to_csv(DERIVED_DIR / "path_issues.csv", index=False)
    header_checks(metadata, report).to_csv(DERIVED_DIR / "header_or_signal_issues.csv", index=False)
    label_inventory(metadata, report).to_csv(DERIVED_DIR / "label_inventory.csv", index=False)
    split_readiness(metadata).to_csv(DERIVED_DIR / "split_readiness.csv", index=False)
    write_json_report(report)
    print_summary(report)
    return 0 if report.safe_for_normalization else 1


if __name__ == "__main__":
    raise SystemExit(main())
