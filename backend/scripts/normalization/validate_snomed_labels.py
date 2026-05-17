"""Validate ECG Arrhythmia SNOMED CT labels through a FHIR terminology lookup.

This script does not decide the ML taxonomy. It only records terminology-server
metadata for the SNOMED CT source codes used by the ECG Arrhythmia dataset.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[2]
INPUT_PATH = ROOT / "data" / "ecg-arrhythmia" / "derived" / "label_inventory.csv"
OUT_PATH = ROOT / "data" / "ecg-arrhythmia" / "derived" / "snomed_lookup_validation.csv"
LOOKUP_URL = "https://r4.ontoserver.csiro.au/fhir/CodeSystem/$lookup"
SNOMED_SYSTEM = "http://snomed.info/sct"


def parameter_value(parameter: list[dict[str, Any]], name: str) -> str:
    for item in parameter:
        if item.get("name") != name:
            continue
        for key in ("valueString", "valueCode", "valueUri", "valueBoolean"):
            if key in item:
                return str(item[key])
    return ""


def property_value(parameter: list[dict[str, Any]], code: str) -> str:
    for item in parameter:
        if item.get("name") != "property":
            continue
        parts = item.get("part", [])
        prop_code = parameter_value(parts, "code")
        if prop_code != code:
            continue
        for part in parts:
            if part.get("name") == "value":
                for value_key in ("valueString", "valueCode", "valueUri", "valueBoolean"):
                    if value_key in part:
                        return str(part[value_key])
    return ""


def lookup_code(code: str) -> dict[str, str]:
    response = requests.get(
        LOOKUP_URL,
        params={"system": SNOMED_SYSTEM, "code": code},
        headers={"Accept": "application/fhir+json"},
        timeout=20,
    )
    row = {
        "snomed_ct_code": code,
        "lookup_status": str(response.status_code),
        "lookup_display": "",
        "lookup_name": "",
        "lookup_system": "",
        "lookup_version": "",
        "lookup_inactive": "",
        "lookup_error": "",
    }
    if response.status_code != 200:
        row["lookup_error"] = response.text[:500].replace("\n", " ")
        return row

    payload = response.json()
    parameters = payload.get("parameter", [])
    row["lookup_display"] = parameter_value(parameters, "display")
    row["lookup_name"] = parameter_value(parameters, "name")
    row["lookup_system"] = parameter_value(parameters, "system")
    row["lookup_version"] = parameter_value(parameters, "version")
    row["lookup_inactive"] = property_value(parameters, "inactive")
    return row


def main() -> None:
    labels = pd.read_csv(INPUT_PATH, dtype=str).fillna("")
    rows = []
    for code in labels["snomed_ct_code"].tolist():
        rows.append(lookup_code(code))
        time.sleep(0.05)

    with OUT_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
