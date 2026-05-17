from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from openai import OpenAI

DATASET_DIR = Path("data/external/mendeley-obstetric-maternal-ehr")
INPUT_JSON = DATASET_DIR / "demo_doctor_notes_50.json"
OUTPUT_JSON = DATASET_DIR / "demo_doctor_notes_50_translated.json"
OUTPUT_CSV = DATASET_DIR / "demo_doctor_notes_50_translated.csv"
QA_JSON = DATASET_DIR / "demo_doctor_notes_50_translated_qa.json"
DEFAULT_MODEL = "x-ai/grok-4.3"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


def load_records(path: Path) -> list[dict[str, Any]]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("Input JSON must contain a list of records.")
    return records


def build_client(base_url: str, api_key_env: str, app_title: str | None, http_referer: str | None) -> OpenAI:
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(f"Set {api_key_env} before running translation.")

    default_headers = {}
    if app_title:
        default_headers["X-Title"] = app_title
    if http_referer:
        default_headers["HTTP-Referer"] = http_referer

    return OpenAI(
        base_url=base_url,
        api_key=api_key,
        default_headers=default_headers or None,
        timeout=90,
        max_retries=2,
    )


def translation_messages(spanish_note: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You translate Spanish obstetric clinical notes into clear English for a patient-facing demo. "
                "Translate only the provided note. Preserve bracketed de-identification placeholders exactly. "
                "Preserve clinical meaning, uncertainty, abbreviations when unclear, gestational ages, measurements, and medication names. "
                "Do not add diagnoses, advice, explanations, markdown, labels, or commentary."
            ),
        },
        {
            "role": "user",
            "content": f"Translate this Spanish clinical note excerpt into English:\n\n{spanish_note}",
        },
    ]


def translate_note(client: OpenAI, model: str, spanish_note: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=translation_messages(spanish_note),
        temperature=0,
        extra_body={"reasoning": {"enabled": True}},
    )
    translated = response.choices[0].message.content or ""
    translated = translated.strip()
    if not translated:
        raise RuntimeError("Model returned an empty translation.")
    return translated


def write_csv(records: list[dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "demo_id",
        "patient_id",
        "visit_occurrence_id",
        "group",
        "category",
        "age",
        "condition_codes",
        "note_date",
        "note_title",
        "original_language",
        "original_spanish_note_excerpt",
        "english_demo_note",
        "extracted_factors",
        "summary",
        "doctor_questions",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = record.copy()
            row["condition_codes"] = "; ".join(row.get("condition_codes") or [])
            row["extracted_factors"] = "; ".join(row.get("extracted_factors") or [])
            row["doctor_questions"] = " | ".join(row.get("doctor_questions") or [])
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_outputs(records: list[dict[str, Any]], qa: dict[str, Any], output_json: Path, output_csv: Path, qa_json: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    qa_json.write_text(json.dumps(qa, indent=2, ensure_ascii=False), encoding="utf-8")
    write_csv(records, output_csv)


def unchanged_field_violations(original: list[dict[str, Any]], translated: list[dict[str, Any]]) -> list[str]:
    violations = []
    for before, after in zip(original, translated, strict=True):
        before_copy = deepcopy(before)
        after_copy = deepcopy(after)
        before_copy.pop("english_demo_note", None)
        after_copy.pop("english_demo_note", None)
        if before_copy != after_copy:
            violations.append(str(before.get("demo_id", "unknown")))
    return violations


def build_qa(original: list[dict[str, Any]], translated: list[dict[str, Any]], model: str) -> dict[str, Any]:
    empty_translations = [
        str(record.get("demo_id", "unknown"))
        for record in translated
        if not str(record.get("english_demo_note", "")).strip()
    ]
    unchanged_translations = [
        str(after.get("demo_id", "unknown"))
        for before, after in zip(original, translated, strict=True)
        if before.get("english_demo_note") == after.get("english_demo_note")
    ]
    non_english_fields_changed = unchanged_field_violations(original, translated)
    digest = hashlib.sha256(json.dumps(translated, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {
        "row_count": len(translated),
        "model": model,
        "changed_field": "english_demo_note",
        "records_translated": len(translated) - len(unchanged_translations),
        "empty_translations": empty_translations,
        "unchanged_translations": unchanged_translations,
        "non_english_fields_changed": non_english_fields_changed,
        "passes": (
            len(translated) == 50
            and not empty_translations
            and not unchanged_translations
            and not non_english_fields_changed
        ),
        "sha256": digest,
    }


def translate_records(client: OpenAI, records: list[dict[str, Any]], model: str, sleep_seconds: float, limit: int | None) -> list[dict[str, Any]]:
    translated_records = deepcopy(records)
    target_count = len(translated_records) if limit is None else min(limit, len(translated_records))
    for index, record in enumerate(translated_records[:target_count], start=1):
        demo_id = record.get("demo_id", f"row_{index}")
        spanish_note = str(record.get("original_spanish_note_excerpt", "")).strip()
        if not spanish_note:
            raise ValueError(f"Record {demo_id} is missing original_spanish_note_excerpt.")
        record["english_demo_note"] = translate_note(client, model, spanish_note)
        print(f"TRANSLATED {index}/{target_count} {demo_id}")
        if sleep_seconds and index < target_count:
            time.sleep(sleep_seconds)
    return translated_records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-json", type=Path, default=INPUT_JSON)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    parser.add_argument("--qa-json", type=Path, default=QA_JSON)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key-env", default="OPENROUTER_API_KEY")
    parser.add_argument("--app-title", default="VenusHacks doctor note translation")
    parser.add_argument("--http-referer", default=None)
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--replace-input", action="store_true")
    args = parser.parse_args()

    output_json = args.input_json if args.replace_input else args.output_json
    output_csv = args.output_csv
    original_records = load_records(args.input_json)
    if len(original_records) != 50 and args.limit is None:
        raise ValueError(f"Expected 50 input records, found {len(original_records)}.")

    client = build_client(args.base_url, args.api_key_env, args.app_title, args.http_referer)
    translated_records = translate_records(client, original_records, args.model, args.sleep_seconds, args.limit)
    qa = build_qa(original_records, translated_records, args.model)
    if args.limit is not None:
        qa["passes"] = False
        qa["partial_run"] = True
        qa["limit"] = args.limit

    write_outputs(translated_records, qa, output_json, output_csv, args.qa_json)
    print(json.dumps(qa, indent=2, ensure_ascii=False))
    if not qa["passes"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
