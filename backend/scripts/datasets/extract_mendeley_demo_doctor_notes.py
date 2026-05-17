from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import duckdb

DATASET_DIR = Path("data/external/mendeley-obstetric-maternal-ehr")
OUTPUT_JSON = DATASET_DIR / "demo_doctor_notes_50.json"
OUTPUT_CSV = DATASET_DIR / "demo_doctor_notes_50.csv"
QA_JSON = DATASET_DIR / "demo_doctor_notes_50_qa.json"

RISK_TARGET = 35
CONTROL_TARGET = 15
EXCERPT_LIMIT = 900

RISK_QUOTAS = {
    "preeclampsia_eclampsia": 10,
    "maternal_hypertension": 13,
    "diabetes_in_pregnancy": 8,
    "edema_proteinuria": 2,
    "chronic_metabolic_risk": 2,
}

CONTROL_QUOTAS = {
    "normal_delivery": 4,
    "cesarean_delivery": 4,
    "false_labor": 3,
    "rupture_or_bleeding": 4,
}

RISK_CODE_PREFIXES = (
    "O10",
    "O11",
    "O12",
    "O13",
    "O14",
    "O15",
    "O16",
    "O24",
    "I10",
    "I11",
    "I12",
    "I13",
    "I14",
    "I15",
    "E10",
    "E11",
    "E12",
    "E13",
    "E14",
)

CONTROL_CODE_PREFIXES = ("O80", "O82", "O47", "O42", "O20")
PREGNANCY_RE = re.compile(
    r"embaraz|gesta|gestaci|prenat|parto|postpart|pospart|puerper|obstetr|ces[áa]rea|materna|feto|fetal|semanas|\bsem\b|preeclamp",
    re.IGNORECASE,
)
LOW_VALUE_TITLE_RE = re.compile(
    r"observaciones a ordenes|plan de enfermer[ií]a|administrativas|medicamentos no-pbs|adminstraci[oó]n de mezclas",
    re.IGNORECASE,
)

CATEGORY_FACTORS = {
    "preeclampsia_eclampsia": ["preeclampsia/eclampsia spectrum", "pregnancy-related hypertensive disorder", "maternal cardiovascular risk"],
    "maternal_hypertension": ["maternal hypertension", "elevated blood pressure risk", "pregnancy-related cardiovascular risk"],
    "diabetes_in_pregnancy": ["diabetes in pregnancy", "cardiometabolic risk", "postpartum follow-up priority"],
    "edema_proteinuria": ["gestational edema or proteinuria", "preeclampsia warning context", "maternal cardiovascular risk"],
    "chronic_metabolic_risk": ["chronic hypertension or diabetes", "cardiometabolic risk", "pregnancy/postpartum follow-up priority"],
    "normal_delivery": ["routine obstetric delivery context", "comparison case", "pregnancy/postpartum care"],
    "cesarean_delivery": ["cesarean delivery context", "comparison case", "postpartum recovery"],
    "false_labor": ["false labor context", "comparison case", "pregnancy care"],
    "rupture_or_bleeding": ["obstetric membrane or bleeding context", "comparison case", "pregnancy care"],
}

CATEGORY_QUESTIONS = {
    "preeclampsia_eclampsia": [
        "What blood pressure symptoms should I watch for before my next visit?",
        "Do I need earlier postpartum blood pressure follow-up?",
        "When should headache, swelling, or vision symptoms become urgent?",
    ],
    "maternal_hypertension": [
        "How often should I check my blood pressure at home?",
        "What blood pressure range should prompt me to call?",
        "Should my postpartum heart-health follow-up be sooner?",
    ],
    "diabetes_in_pregnancy": [
        "How does diabetes in pregnancy affect my heart-health follow-up?",
        "Do I need postpartum glucose or blood pressure monitoring?",
        "What warning signs should I track after delivery?",
    ],
    "edema_proteinuria": [
        "Could this swelling or protein finding relate to blood pressure risk?",
        "What symptoms should make me seek urgent care?",
        "Should we repeat blood pressure or urine testing?",
    ],
    "chronic_metabolic_risk": [
        "How do my chronic risk factors change pregnancy or postpartum follow-up?",
        "Should I see primary care or cardiology after delivery?",
        "What numbers should I track at home?",
    ],
    "normal_delivery": [
        "What symptoms are normal after delivery, and what should I report?",
        "When should I schedule routine postpartum follow-up?",
        "Are there any heart-health warning signs I should know?",
    ],
    "cesarean_delivery": [
        "What symptoms after cesarean should prompt urgent care?",
        "How should I monitor recovery and swelling?",
        "When should I follow up after discharge?",
    ],
    "false_labor": [
        "What signs mean I should return for evaluation?",
        "How do I distinguish false labor from urgent symptoms?",
        "What should I monitor at home?",
    ],
    "rupture_or_bleeding": [
        "What bleeding or fluid changes should I report urgently?",
        "Does this change my follow-up schedule?",
        "What symptoms should I monitor at home?",
    ],
}


def normalize_text(value: str | None, limit: int = EXCERPT_LIMIT) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text[:limit].rstrip()


def classify_code(code: str) -> tuple[str | None, int]:
    code = code.upper().strip()
    if code.startswith(("O11", "O14", "O15")):
        return "preeclampsia_eclampsia", 1
    if code.startswith(("O10", "O13", "O16")):
        return "maternal_hypertension", 2
    if code.startswith("O12"):
        return "edema_proteinuria", 3
    if code.startswith("O24"):
        return "diabetes_in_pregnancy", 4
    if code.startswith(("I10", "I11", "I12", "I13", "I14", "I15", "E10", "E11", "E12", "E13", "E14")):
        return "chronic_metabolic_risk", 5
    if code.startswith("O80"):
        return "normal_delivery", 20
    if code.startswith("O82"):
        return "cesarean_delivery", 21
    if code.startswith("O47"):
        return "false_labor", 22
    if code.startswith(("O42", "O20")):
        return "rupture_or_bleeding", 23
    return None, 99


def best_category(codes: str, allowed: dict[str, int]) -> str:
    best_name = ""
    best_rank = 999
    for code in codes.split(","):
        category, rank = classify_code(code)
        if category in allowed and rank < best_rank:
            best_name = category or ""
            best_rank = rank
    return best_name


def synthetic_note(category: str, title: str, codes: str) -> str:
    readable = category.replace("_", " ")
    if category in RISK_QUOTAS:
        return (
            f"Pregnancy/postpartum clinical note pattern with {readable}. "
            f"The source visit includes diagnosis code evidence ({codes}) and a Spanish clinical note titled '{title}'. "
            "This synthetic English demo note is for explaining maternal cardiovascular follow-up factors, not diagnosis."
        )
    return (
        f"Pregnancy/postpartum comparison note pattern with {readable}. "
        f"The source visit includes obstetric code evidence ({codes}) and a Spanish clinical note titled '{title}'. "
        "This synthetic English demo note is for demonstrating note review without a dominant cardiovascular-risk code."
    )


def summary_for(category: str, group: str, codes: str) -> str:
    readable = category.replace("_", " ")
    if group == "cv_risk":
        return f"This note is useful for the demo because the same maternal visit has {readable} code evidence ({codes}), which should trigger cardiovascular follow-up education."
    return f"This note is useful as a comparison maternal case: it is pregnancy/postpartum related, but the same visit does not carry the selected cardiovascular-risk code families."


def build_record(row: dict[str, Any], group: str, category: str, index: int) -> dict[str, Any]:
    title = row["note_title"] or "Clinical note"
    codes = row["evidence_codes"] or ""
    excerpt = normalize_text(row["note_text"])
    return {
        "demo_id": f"{'cv' if group == 'cv_risk' else 'ctrl'}_{index:03d}",
        "patient_id": row["person_id"],
        "visit_occurrence_id": row["visit_occurrence_id"],
        "group": group,
        "category": category,
        "age": row.get("age"),
        "condition_codes": [code for code in codes.split(",") if code],
        "note_date": row.get("note_date"),
        "note_title": title,
        "original_language": "es",
        "original_spanish_note_excerpt": excerpt,
        "english_demo_note": synthetic_note(category, title, codes),
        "extracted_factors": CATEGORY_FACTORS[category],
        "summary": summary_for(category, group, codes),
        "doctor_questions": CATEGORY_QUESTIONS[category],
    }


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("SET memory_limit='8GB'")
    con.execute("SET threads=1")
    con.execute("SET preserve_insertion_order=false")
    return con


def create_candidate_tables(con: duckdb.DuckDBPyConnection, dataset_dir: Path) -> None:
    condition_path = dataset_dir / "04_Condition.csv"
    visit_path = dataset_dir / "02_Visit.csv"
    note_path = dataset_dir / "06_Note.csv"

    con.execute(
        f"""
        CREATE TEMP TABLE condition_codes AS
        SELECT
            trim(visit_occurrence_id) AS visit_occurrence_id,
            upper(trim(condition_source_value)) AS condition_source_value
        FROM read_csv('{condition_path}', header=true, all_varchar=true)
        WHERE visit_occurrence_id IS NOT NULL
          AND condition_source_value IS NOT NULL
          AND trim(condition_source_value) <> ''
        """
    )
    con.execute(
        """
        CREATE TEMP TABLE visit_code_summary AS
        SELECT
            visit_occurrence_id,
            string_agg(DISTINCT condition_source_value, ',' ORDER BY condition_source_value) AS all_codes,
            bool_or(condition_source_value LIKE 'O%') AS has_obstetric_code,
            bool_or(
                condition_source_value LIKE 'O10%' OR condition_source_value LIKE 'O11%' OR
                condition_source_value LIKE 'O12%' OR condition_source_value LIKE 'O13%' OR
                condition_source_value LIKE 'O14%' OR condition_source_value LIKE 'O15%' OR
                condition_source_value LIKE 'O16%' OR condition_source_value LIKE 'O24%' OR
                regexp_matches(condition_source_value, '^(I1[0-5]|E1[0-4])')
            ) AS has_cv_risk_code,
            bool_or(
                condition_source_value LIKE 'O80%' OR condition_source_value LIKE 'O82%' OR
                condition_source_value LIKE 'O47%' OR condition_source_value LIKE 'O42%' OR
                condition_source_value LIKE 'O20%'
            ) AS has_control_code,
            string_agg(
                DISTINCT CASE
                    WHEN condition_source_value LIKE 'O10%' OR condition_source_value LIKE 'O11%' OR
                         condition_source_value LIKE 'O12%' OR condition_source_value LIKE 'O13%' OR
                         condition_source_value LIKE 'O14%' OR condition_source_value LIKE 'O15%' OR
                         condition_source_value LIKE 'O16%' OR condition_source_value LIKE 'O24%' OR
                         regexp_matches(condition_source_value, '^(I1[0-5]|E1[0-4])')
                    THEN condition_source_value
                    ELSE NULL
                END,
                ',' ORDER BY CASE
                    WHEN condition_source_value LIKE 'O10%' OR condition_source_value LIKE 'O11%' OR
                         condition_source_value LIKE 'O12%' OR condition_source_value LIKE 'O13%' OR
                         condition_source_value LIKE 'O14%' OR condition_source_value LIKE 'O15%' OR
                         condition_source_value LIKE 'O16%' OR condition_source_value LIKE 'O24%' OR
                         regexp_matches(condition_source_value, '^(I1[0-5]|E1[0-4])')
                    THEN condition_source_value
                    ELSE NULL
                END
            ) AS cv_codes,
            string_agg(
                DISTINCT CASE
                    WHEN condition_source_value LIKE 'O80%' OR condition_source_value LIKE 'O82%' OR
                         condition_source_value LIKE 'O47%' OR condition_source_value LIKE 'O42%' OR
                         condition_source_value LIKE 'O20%'
                    THEN condition_source_value
                    ELSE NULL
                END,
                ',' ORDER BY CASE
                    WHEN condition_source_value LIKE 'O80%' OR condition_source_value LIKE 'O82%' OR
                         condition_source_value LIKE 'O47%' OR condition_source_value LIKE 'O42%' OR
                         condition_source_value LIKE 'O20%'
                    THEN condition_source_value
                    ELSE NULL
                END
            ) AS control_codes
        FROM condition_codes
        GROUP BY visit_occurrence_id
        HAVING has_obstetric_code
        """
    )
    con.execute(
        f"""
        CREATE TEMP TABLE visits AS
        SELECT
            trim(visit_occurrence_id) AS visit_occurrence_id,
            trim(person_id) AS person_id,
            trim(age) AS age
        FROM read_csv('{visit_path}', header=true, all_varchar=true)
        WHERE visit_occurrence_id IS NOT NULL AND person_id IS NOT NULL
        """
    )
    con.execute(
        """
        CREATE TEMP TABLE eligible_visits AS
        SELECT
            v.person_id,
            v.visit_occurrence_id,
            v.age,
            s.all_codes,
            s.cv_codes,
            s.control_codes,
            s.has_cv_risk_code,
            s.has_control_code
        FROM visits v
        JOIN visit_code_summary s USING (visit_occurrence_id)
        WHERE v.person_id IS NOT NULL AND v.person_id <> ''
        """
    )
    con.execute(
        f"""
        CREATE TEMP TABLE candidate_notes AS
        SELECT
            n.person_id,
            n.visit_occurrence_id,
            e.age,
            n.note_date,
            n.note_title,
            n.note_text,
            length(n.note_text) AS note_length,
            e.all_codes,
            e.cv_codes,
            e.control_codes,
            e.has_cv_risk_code,
            e.has_control_code,
            CASE
                WHEN regexp_matches(lower(n.note_title), 'enfermedad actual|motivo de consulta') THEN 1
                WHEN regexp_matches(lower(n.note_title), 'evoluci') AND regexp_matches(lower(n.note_title), 'subjetivo|análisis|analisis') THEN 2
                WHEN regexp_matches(lower(n.note_title), 'examen f') THEN 3
                WHEN regexp_matches(lower(n.note_title), 'egreso|salida') THEN 4
                WHEN regexp_matches(lower(n.note_title), 'trabajo de parto|obstetric') THEN 5
                ELSE 9
            END AS title_rank
        FROM read_csv(
            '{note_path}',
            header=true,
            all_varchar=true,
            quote='"',
            escape='"',
            parallel=false
        ) n
        JOIN eligible_visits e
          ON trim(n.visit_occurrence_id) = e.visit_occurrence_id
         AND trim(n.person_id) = e.person_id
        WHERE n.note_text IS NOT NULL
          AND n.note_title IS NOT NULL
          AND length(trim(n.note_text)) BETWEEN 180 AND 3000
          AND NOT regexp_matches(lower(n.note_title), 'observaciones a ordenes|plan de enfermer|administrativas|medicamentos no-pbs|adminstraci')
          AND regexp_matches(lower(coalesce(n.note_title, '') || ' ' || coalesce(n.note_text, '')), 'embaraz|gesta|gestaci|prenat|parto|postpart|pospart|puerper|obstetr|cesárea|cesarea|materna|feto|fetal|semanas|\\bsem\\b|preeclamp')
        """
    )


def fetch_ranked_candidates(con: duckdb.DuckDBPyConnection, group: str) -> list[dict[str, Any]]:
    if group == "cv_risk":
        where = "has_cv_risk_code"
        evidence = "cv_codes"
        category_expr = "cv_codes"
    else:
        where = "has_control_code AND NOT has_cv_risk_code"
        evidence = "control_codes"
        category_expr = "control_codes"

    rows = con.execute(
        f"""
        WITH ranked AS (
            SELECT
                person_id,
                visit_occurrence_id,
                age,
                note_date,
                note_title,
                note_text,
                note_length,
                all_codes,
                {evidence} AS evidence_codes,
                title_rank,
                row_number() OVER (
                    PARTITION BY person_id
                    ORDER BY title_rank, note_length DESC, note_date, visit_occurrence_id
                ) AS person_note_rank
            FROM candidate_notes
            WHERE {where}
              AND {evidence} IS NOT NULL
              AND trim({evidence}) <> ''
        )
        SELECT * FROM ranked
        WHERE person_note_rank = 1
        ORDER BY title_rank, note_length DESC, person_id
        """
    ).fetchall()
    columns = [desc[0] for desc in con.description]
    result = []
    for row in rows:
        item = dict(zip(columns, row, strict=True))
        category = best_category(item["evidence_codes"], RISK_QUOTAS if group == "cv_risk" else CONTROL_QUOTAS)
        if category:
            item["category"] = category
            result.append(item)
    return result


def choose_with_quotas(candidates: list[dict[str, Any]], quotas: dict[str, int], target: int) -> list[dict[str, Any]]:
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        by_category[row["category"]].append(row)

    selected: list[dict[str, Any]] = []
    selected_people: set[str] = set()
    for category, quota in quotas.items():
        for row in by_category.get(category, []):
            if len([item for item in selected if item["category"] == category]) >= quota:
                break
            if row["person_id"] in selected_people:
                continue
            selected.append(row)
            selected_people.add(row["person_id"])

    if len(selected) < target:
        for row in candidates:
            if len(selected) >= target:
                break
            if row["person_id"] in selected_people:
                continue
            selected.append(row)
            selected_people.add(row["person_id"])

    return selected[:target]


def qa_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(record["group"] for record in records)
    category_counts = Counter(record["category"] for record in records)
    patient_counts = Counter(record["patient_id"] for record in records)
    excerpt_counts = Counter(record["original_spanish_note_excerpt"] for record in records)

    missing_fields: dict[str, int] = {}
    required = [
        "demo_id",
        "patient_id",
        "visit_occurrence_id",
        "group",
        "category",
        "condition_codes",
        "note_title",
        "original_spanish_note_excerpt",
        "english_demo_note",
        "extracted_factors",
        "summary",
        "doctor_questions",
    ]
    for field in required:
        missing_fields[field] = sum(1 for record in records if not record.get(field))

    control_risk_leaks = []
    cv_without_codes = []
    pregnancy_relevance_misses = []
    short_or_generic_notes = []
    for record in records:
        codes = tuple(record["condition_codes"])
        if record["group"] == "control" and any(code.startswith(RISK_CODE_PREFIXES) for code in codes):
            control_risk_leaks.append(record["demo_id"])
        if record["group"] == "cv_risk" and not any(code.startswith(RISK_CODE_PREFIXES) for code in codes):
            cv_without_codes.append(record["demo_id"])
        joined_text = f"{record['note_title']} {record['original_spanish_note_excerpt']}"
        if not PREGNANCY_RE.search(joined_text):
            pregnancy_relevance_misses.append(record["demo_id"])
        excerpt = record["original_spanish_note_excerpt"]
        if len(excerpt.strip()) < 120 or LOW_VALUE_TITLE_RE.search(record["note_title"]):
            short_or_generic_notes.append(record["demo_id"])

    return {
        "row_count": len(records),
        "unique_patient_count": len(patient_counts),
        "group_counts": dict(counts),
        "category_counts": dict(category_counts),
        "duplicate_patients": {k: v for k, v in patient_counts.items() if v > 1},
        "duplicate_excerpts": {k[:80]: v for k, v in excerpt_counts.items() if v > 1},
        "missing_fields": missing_fields,
        "control_risk_leaks": control_risk_leaks,
        "cv_without_codes": cv_without_codes,
        "pregnancy_relevance_misses": pregnancy_relevance_misses,
        "short_or_generic_notes": short_or_generic_notes,
        "passes": (
            len(records) == 50
            and len(patient_counts) == 50
            and counts.get("cv_risk") == RISK_TARGET
            and counts.get("control") == CONTROL_TARGET
            and not any(missing_fields.values())
            and not control_risk_leaks
            and not cv_without_codes
            and not pregnancy_relevance_misses
            and not short_or_generic_notes
        ),
    }


def write_outputs(records: list[dict[str, Any]], qa: dict[str, Any], output_json: Path, output_csv: Path, qa_json: Path) -> None:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    qa_json.write_text(json.dumps(qa, indent=2, ensure_ascii=False), encoding="utf-8")
    with output_csv.open("w", newline="", encoding="utf-8") as f:
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
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            row = record.copy()
            row["condition_codes"] = "; ".join(row["condition_codes"])
            row["extracted_factors"] = "; ".join(row["extracted_factors"])
            row["doctor_questions"] = " | ".join(row["doctor_questions"])
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=DATASET_DIR)
    parser.add_argument("--output-json", type=Path, default=OUTPUT_JSON)
    parser.add_argument("--output-csv", type=Path, default=OUTPUT_CSV)
    parser.add_argument("--qa-json", type=Path, default=QA_JSON)
    args = parser.parse_args()

    con = connect()
    create_candidate_tables(con, args.dataset_dir)

    risk_candidates = fetch_ranked_candidates(con, "cv_risk")
    control_candidates = fetch_ranked_candidates(con, "control")
    risk_selected = choose_with_quotas(risk_candidates, RISK_QUOTAS, RISK_TARGET)
    control_selected = choose_with_quotas(control_candidates, CONTROL_QUOTAS, CONTROL_TARGET)

    records = []
    for index, row in enumerate(risk_selected, start=1):
        records.append(build_record(row, "cv_risk", row["category"], index))
    for index, row in enumerate(control_selected, start=1):
        records.append(build_record(row, "control", row["category"], index))

    qa = qa_records(records)
    output_digest = hashlib.sha256(json.dumps(records, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    qa["sha256"] = output_digest
    qa["candidate_counts"] = {
        "risk_candidates": len(risk_candidates),
        "control_candidates": len(control_candidates),
    }
    write_outputs(records, qa, args.output_json, args.output_csv, args.qa_json)

    print(json.dumps(qa, indent=2, ensure_ascii=False))
    if not qa["passes"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
