"""Build the shared ECG label mapping artifact.

The output is intentionally explicit: one row per source label atom from each
dataset. The mapping uses dataset-provided label inventories as the authority
and keeps rule provenance so medical review can tighten the taxonomy later.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "normalized" / "derived"
OUT_PATH = OUT_DIR / "label_mapping.csv"
SUMMARY_PATH = OUT_DIR / "label_mapping_summary.json"


NORMALIZED_LABELS = [
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
]


def text_has(text: str, *needles: str) -> bool:
    haystack = text.lower()
    return any(needle in haystack for needle in needles)


def regex_has(text: str, *patterns: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def compact_text(*parts: object) -> str:
    return " ".join(str(part) for part in parts if pd.notna(part)).lower()


def stable_json_list(values: list[str]) -> str:
    seen: set[str] = set()
    unique = []
    for value in values:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return json.dumps(unique, separators=(",", ":"))


def split_pipe_values(value: str) -> list[str]:
    return [part.strip() for part in str(value).split("|") if part.strip()]


def normalize_labels(
    *,
    source_dataset: str,
    source_label_code: str,
    source_label_name: str,
    source_label_abbreviation: str = "",
    source_label_category: str = "",
    diagnostic_class: str = "",
    is_modifier: bool = False,
) -> tuple[list[str], str, str]:
    text = compact_text(
        source_label_code,
        source_label_name,
        source_label_abbreviation,
        source_label_category,
        diagnostic_class,
    )
    code = source_label_code.strip().upper()
    labels: list[str] = []
    notes: list[str] = []

    if is_modifier:
        return [], "modifier_only", "AHA/SPH modifier; keep as label context, not standalone disease target."

    if diagnostic_class == "NORM" or text_has(text, "normal ecg"):
        labels.append("normal")

    if re.search(r"\bsinus rhythm\b", text):
        labels.append("sinus_rhythm")

    if text_has(text, "sinus arrhythmia", "sinus irregularity"):
        labels.append("sinus_arrhythmia")

    if text_has(text, "atrial fibrillation", "atrial flutter") or code in {"AFIB", "AFLT"}:
        labels.append("atrial_fibrillation_or_flutter")

    if text_has(text, "bradycardia"):
        labels.append("bradycardia")

    if text_has(text, "tachycardia", "tachy"):
        labels.append("tachycardia")

    if text_has(
        text,
        "supraventricular",
        "atrial arrhythmia",
        "atrial tachycardia",
        "atrial rhythm",
        "atrial escape",
        "atrioventricular tachycardia",
        "av nodal re-entry tachycardia",
        "av nodal reentrant tachycardia",
        "junctional rhythm",
        "junctional tachycardia",
        "junctional escape",
        "ectopic rhythm",
        "atrioventricular junctional",
        "atrioventricular reentrant",
        "atrioventricular re-entry",
        "atrioventricular  node reentrant",
    ):
        labels.append("supraventricular_arrhythmia")

    ventricular_tachycardia = regex_has(text, r"(?<!atrio)\bventricular tachycardia\b")
    if (
        ventricular_tachycardia
        or text_has(
            text,
            "ventricular fibrillation",
            "ventricular flutter",
            "ventricular escape",
            "idioventricular",
            "ventricular fusion",
        )
    ) and not text_has(
        text,
        "supraventricular tachycardia",
        "atrioventricular tachycardia",
        "atrioventricular reentrant tachycardia",
        "atrioventricular re-entry tachycardia",
    ):
        labels.append("ventricular_arrhythmia")

    if text_has(
        text,
        "premature",
        "pvc",
        "bigeminal",
        "bigeminy",
        "trigeminal",
        "trigeminy",
        "escape beat",
        "fusion beat",
        "fusion wave",
    ):
        labels.append("ectopic_beats")

    if diagnostic_class == "CD" or text_has(
        text,
        "atrioventricular block",
        "av block",
        "conduction",
        "fascicular block",
        "bundle branch block",
        "bundle-branch block",
        "sinoatrial block",
        "sinus arrest",
        "atrioventricular dissociation",
    ):
        labels.append("conduction_abnormality")

    if text_has(
        text,
        "bundle branch block",
        "right bundle branch block",
        "left bundle branch block",
        "right bundle-branch block",
        "left bundle-branch block",
        "fascicular block",
        "rbbb",
        "lbbb",
        "irbbb",
        "ilbbb",
        "crbbb",
        "clbbb",
        "lafb",
        "lpfb",
    ):
        labels.append("bundle_branch_block")

    is_interval_only = regex_has(text, r"\blong qt\b", r"\bqt interval\b", r"\bprolonged qt\b")
    if (diagnostic_class == "STTC" and not is_interval_only) or regex_has(
        text,
        r"\bst-t\b",
        r"\bst segment\b",
        r"\bst deviation\b",
        r"\bst depression\b",
        r"\bst elevation\b",
        r"\bst changes?\b",
        r"\bst extension\b",
        r"\bst tilt\b",
        r"\bst drop\b",
        r"\bst interval abnormal\b",
        r"\bt[- ]?wave\b",
        r"\bt[- ]?waves\b",
        r"\bu wave\b",
        r"\btu fusion\b",
        r"\bdigitalis\b",
        r"\belectrolytic\b",
    ):
        labels.append("st_t_abnormality")

    if text_has(text, "ischemic", "ischemia", "injury"):
        labels.append("ischemia_or_injury_pattern")

    if diagnostic_class == "MI" or text_has(
        text,
        "myocardial infarction",
        "myocardial infraction",
        "abnormal q wave",
        "q wave abnormal",
        "q waves",
        " mi",
    ):
        labels.append("myocardial_infarction_pattern")

    if diagnostic_class == "HYP" or text_has(
        text,
        "hypertrophy",
        "enlargement",
        "overload",
        "left ventricle hypertrophy",
        "right ventricle hypertrophy",
    ):
        labels.append("hypertrophy_or_enlargement")

    if text_has(text, "p wave", "p-wave"):
        labels.append("p_wave_abnormality")

    if text_has(
        text,
        "axis",
        "voltage",
        "low qrs",
        "high qrs",
        "poor r wave",
        "r wave - finding",
        "abnormal qrs",
        "clockwise",
        "countercolockwise",
        "rotation",
        "vectorcardiographic",
    ):
        labels.append("axis_or_voltage_abnormality")

    if text_has(text, "qt interval", "long qt", "shortened pr", "prolonged pr", "pr interval", "short pr"):
        labels.append("interval_abnormality")

    if text_has(text, "pacing rhythm", "artificial pacing") or (
        text_has(text, "pacemaker") and not text_has(text, "wandering atrial pacemaker")
    ):
        labels.append("paced_rhythm")

    if text_has(
        text,
        "preexcitation",
        "pre-excitation",
        "wpw",
        "wolff-parkinson-white",
        "wolff-parkinson",
        "wolf-parkinson-white",
        "wolf-parkinson",
    ):
        labels.append("preexcitation")

    if text_has(text, "early repolarization"):
        labels.append("early_repolarization")

    if text_has(text, "brugada"):
        labels.append("brugada_pattern")

    if text_has(text, "wandering") and text_has(text, "atrial", "atrium"):
        labels.append("supraventricular_arrhythmia")

    if not labels:
        return [], "needs_review", "No MVP normalized disease label assigned by current deterministic rules."

    if len(labels) > 1:
        notes.append("Multiple normalized labels assigned because the source label spans more than one broad group.")

    return labels, "mapped", " ".join(notes) if notes else "Mapped by deterministic ECG label keyword/class rules."


def base_row(
    *,
    source_dataset: str,
    source_label_system: str,
    source_label_code: str,
    source_label_name: str,
    source_label_abbreviation: str = "",
    source_label_abbreviations: list[str] | None = None,
    source_label_category: str = "",
    source_record_count: str = "",
    source_mapping_fields: dict[str, object] | None = None,
    validation_sources: list[str] | None = None,
    review_flags: list[str] | None = None,
    snomed_active: str = "",
    labels: list[str],
    status: str,
    notes: str,
) -> dict[str, object]:
    review_flags = review_flags or []
    if len(labels) > 1 and "multi_target_mapping" not in review_flags:
        review_flags.append("multi_target_mapping")
    if snomed_active.lower() == "false" and "inactive_snomed_concept" not in review_flags:
        review_flags.append("inactive_snomed_concept")
    if status == "mapped" and review_flags:
        status = "mapped_with_warnings"
    return {
        "source_dataset": source_dataset,
        "source_label_system": source_label_system,
        "source_label_code": source_label_code,
        "source_label_name": source_label_name,
        "source_label_abbreviation": source_label_abbreviation,
        "source_label_abbreviations": stable_json_list(source_label_abbreviations or split_pipe_values(source_label_abbreviation)),
        "source_label_category": source_label_category,
        "source_record_count": source_record_count,
        "normalized_labels": stable_json_list(labels),
        "mapping_status": status,
        "review_flags": stable_json_list(review_flags),
        "snomed_active": snomed_active,
        "mapping_notes": notes,
        "source_mapping_fields": json.dumps(source_mapping_fields or {}, sort_keys=True, separators=(",", ":")),
        "validation_sources": stable_json_list(validation_sources or []),
    }


def build_ptbxl_rows() -> list[dict[str, object]]:
    path = ROOT / "data" / "ptb-xl" / "derived" / "label_inventory.csv"
    df = pd.read_csv(path, dtype=str).fillna("")
    rows = []
    for item in df.to_dict("records"):
        source_label_name = item["description"]
        source_mapping_fields = {
            "original_description": item["description"],
            "diagnostic": item.get("diagnostic", ""),
            "form": item.get("form", ""),
            "rhythm": item.get("rhythm", ""),
            "diagnostic_class": item.get("diagnostic_class", ""),
            "diagnostic_subclass": item.get("diagnostic_subclass", ""),
        }
        if item["label"] == "WPW":
            source_label_name = "Wolff-Parkinson-White syndrome"
        labels, status, notes = normalize_labels(
            source_dataset="ptb-xl",
            source_label_code=item["label"],
            source_label_name=source_label_name,
            source_label_category=item.get("diagnostic_subclass", ""),
            diagnostic_class=item.get("diagnostic_class", ""),
        )
        if item["label"] == "QWAVE":
            labels = ["myocardial_infarction_pattern"]
            status = "mapped"
            notes = "Mapped by explicit QA-reviewed override; Q waves are not treated as axis/voltage abnormalities."
        if item["label"] == "WPW":
            labels = ["preexcitation"]
            status = "mapped"
            notes = "Mapped by explicit QA-reviewed override for cross-dataset preexcitation consistency."
        rows.append(
            base_row(
                source_dataset="ptb-xl",
                source_label_system="scp-ecg",
                source_label_code=item["label"],
                source_label_name=source_label_name,
                source_label_category=item.get("diagnostic_class", ""),
                source_record_count=item["record_count"],
                labels=labels,
                status=status,
                notes=notes,
                source_mapping_fields=source_mapping_fields,
                validation_sources=["data/ptb-xl/derived/label_inventory.csv", "data/ptb-xl/scp_statements.csv"],
            )
        )
    return rows


def build_ecg_arrhythmia_rows() -> list[dict[str, object]]:
    path = ROOT / "data" / "ecg-arrhythmia" / "derived" / "label_inventory.csv"
    df = pd.read_csv(path, dtype=str).fillna("")
    complete_path = ROOT / "data" / "ecg-arrhythmia" / "derived" / "ConditionNames_SNOMED-CT_complete.csv"
    complete_df = pd.read_csv(complete_path, dtype=str).fillna("")
    complete_by_code = {
        item["snomed_ct_code"]: item for item in complete_df.to_dict("records")
    }
    snomed_validation_path = ROOT / "data" / "ecg-arrhythmia" / "derived" / "snomed_lookup_validation.csv"
    snomed_validation: dict[str, dict[str, str]] = {}
    validation_sources = [
        "data/ecg-arrhythmia/derived/label_inventory.csv",
        "data/ecg-arrhythmia/derived/ConditionNames_SNOMED-CT_complete.csv",
    ]
    if snomed_validation_path.exists():
        validation_df = pd.read_csv(snomed_validation_path, dtype=str).fillna("")
        snomed_validation = {
            item["snomed_ct_code"]: item for item in validation_df.to_dict("records")
        }
        validation_sources.append("data/ecg-arrhythmia/derived/snomed_lookup_validation.csv")

    rows = []
    for item in df.to_dict("records"):
        complete_item = complete_by_code.get(item["snomed_ct_code"], {})
        lookup = snomed_validation.get(item["snomed_ct_code"], {})
        source_label_name = lookup.get("lookup_display") or item["description"]
        abbreviation_values = split_pipe_values(item.get("abbreviation", ""))
        source_label_abbreviation = abbreviation_values[0] if abbreviation_values else ""
        labels, status, notes = normalize_labels(
            source_dataset="ecg-arrhythmia",
            source_label_code=item["snomed_ct_code"],
            source_label_name=source_label_name,
            source_label_abbreviation=source_label_abbreviation,
        )
        if item["snomed_ct_code"] == "164942001":
            labels = []
            status = "needs_review"
            notes = "F wave present conflicts with local fQRS wording; do not map to axis/voltage until clinically reviewed."
        if lookup.get("lookup_inactive", "").lower() == "true":
            notes = f"{notes} SNOMED lookup marks this concept inactive; keep mapped but review before training."
        snomed_active = ""
        if lookup:
            snomed_active = "false" if lookup.get("lookup_inactive", "").lower() == "true" else "true"
        rows.append(
            base_row(
                source_dataset="ecg-arrhythmia",
                source_label_system="snomed-ct",
                source_label_code=item["snomed_ct_code"],
                source_label_name=source_label_name,
                source_label_abbreviation=source_label_abbreviation,
                source_label_abbreviations=abbreviation_values,
                source_label_category=item.get("challenge_label_set", ""),
                source_record_count=item["record_count"],
                labels=labels,
                status=status,
                notes=notes,
                snomed_active=snomed_active,
                source_mapping_fields={
                    "local_mapping_present": item.get("local_mapping_present", ""),
                    "complete_mapping_present": item.get("complete_mapping_present", ""),
                    "challenge_label_set": item.get("challenge_label_set", ""),
                    "source": item.get("source", ""),
                    "local_description": item.get("description", ""),
                    "local_acronyms": complete_item.get("local_acronyms", ""),
                    "local_full_names": complete_item.get("local_full_names", ""),
                    "challenge_abbreviation": complete_item.get("challenge_abbreviation", ""),
                    "challenge_description": complete_item.get("challenge_description", ""),
                    "challenge_chapman_shaoxing_count": complete_item.get("challenge_chapman_shaoxing_count", ""),
                    "challenge_ningbo_count": complete_item.get("challenge_ningbo_count", ""),
                    "snomed_lookup_display": lookup.get("lookup_display", ""),
                    "snomed_lookup_status": lookup.get("lookup_status", ""),
                    "snomed_lookup_inactive": lookup.get("lookup_inactive", ""),
                    "snomed_lookup_version": lookup.get("lookup_version", ""),
                },
                validation_sources=validation_sources,
            )
        )
    return rows


def build_sph_rows() -> list[dict[str, object]]:
    path = ROOT / "data" / "sph-ecg" / "derived" / "label_inventory.csv"
    df = pd.read_csv(path, dtype=str).fillna("")
    rows = []
    for item in df.to_dict("records"):
        is_modifier = item.get("is_modifier", "").lower() == "true"
        labels, status, notes = normalize_labels(
            source_dataset="sph-ecg",
            source_label_code=item["code"],
            source_label_name=item["description"],
            source_label_category=item.get("category", ""),
            is_modifier=is_modifier,
        )
        rows.append(
            base_row(
                source_dataset="sph-ecg",
                source_label_system="aha",
                source_label_code=item["code"],
                source_label_name=item["description"],
                source_label_category=item.get("category", ""),
                source_record_count=item["record_count"],
                labels=labels,
                status=status,
                notes=notes,
                source_mapping_fields={
                    "category": item.get("category", ""),
                    "is_modifier": item.get("is_modifier", ""),
                    "primary_count": item.get("primary_count", ""),
                    "modifier_count": item.get("modifier_count", ""),
                },
                validation_sources=["data/sph-ecg/derived/label_inventory.csv", "data/sph-ecg/code.csv"],
            )
        )
    return rows


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    by_dataset: dict[str, dict[str, int]] = {}
    by_label = {label: 0 for label in NORMALIZED_LABELS}
    for row in rows:
        dataset = str(row["source_dataset"])
        status = str(row["mapping_status"])
        by_dataset.setdefault(
            dataset,
            {"total": 0, "mapped": 0, "mapped_with_warnings": 0, "modifier_only": 0, "needs_review": 0},
        )
        by_dataset[dataset]["total"] += 1
        by_dataset[dataset][status] += 1
        for label in json.loads(str(row["normalized_labels"])):
            by_label[label] += 1
    return {
        "output": str(OUT_PATH.relative_to(ROOT)),
        "total_source_labels": len(rows),
        "datasets": by_dataset,
        "normalized_label_usage": by_label,
        "notes": [
            "This is a first-pass deterministic mapping and should receive clinical review before model training.",
            "SNOMED labels are validated against the local complete SNOMED mapping and enriched with terminology-server lookup results when available.",
            "SPH AHA modifiers are preserved as modifier_only rows and should be applied as context, not standalone disease labels.",
        ],
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_ptbxl_rows() + build_ecg_arrhythmia_rows() + build_sph_rows()
    rows = sorted(rows, key=lambda row: (str(row["source_dataset"]), str(row["source_label_code"])))
    with OUT_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    SUMMARY_PATH.write_text(json.dumps(summarize(rows), indent=2) + "\n")
    print(f"Wrote {OUT_PATH.relative_to(ROOT)}")
    print(f"Wrote {SUMMARY_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
