# Doctor Note Demo Dataset Generation

This document explains how to generate the 50-patient doctor-note demo dataset from the downloaded Mendeley Obstetric/Maternal EHR dataset.

The generator is intended for demo data preparation only. The default extraction script does not train a model, call external services, translate raw notes with an LLM, or wire anything into the frontend UI. A separate opt-in translation script can translate the generated Spanish excerpts through OpenRouter/Grok after the 50-patient dataset has been generated.

## Source Dataset

Expected source files live under the backend data directory:

```text
backend/data/external/mendeley-obstetric-maternal-ehr/
  02_Visit.csv
  04_Condition.csv
  06_Note.csv
```

The script uses:

- `02_Visit.csv` for visit and patient linkage.
- `04_Condition.csv` for ICD-like source condition-code evidence.
- `06_Note.csv` for Spanish clinical note text.

The downloaded raw dataset and generated outputs are under `backend/data/`, which should remain ignored by git.

## Script Location

```text
backend/scripts/datasets/extract_mendeley_demo_doctor_notes.py
```

## What the Script Generates

By default, the script creates a deterministic 50-record demo cohort:

- 35 cardiovascular-risk-related maternal records.
- 15 control/comparison obstetric records.
- 50 unique patients.
- One selected note per patient.
- Spanish source-note excerpt retained for traceability.
- Synthetic English demo note and structured demo factors generated locally.

Default category targets:

```text
cv_risk:
  preeclampsia_eclampsia: 10
  maternal_hypertension: 13
  diabetes_in_pregnancy: 8
  edema_proteinuria: 2
  chronic_metabolic_risk: 2

control:
  normal_delivery: 4
  cesarean_delivery: 4
  false_labor: 3
  rupture_or_bleeding: 4
```

## Requirements

Use the backend Python 3.12 environment:

```bash
source /Users/benj/Documents/Coding/cardiac_mvp/.venv/bin/activate
cd /Users/benj/Documents/Coding/VenusHacks26/backend
python --version
```

Install or refresh dependencies if needed:

```bash
python -m pip install -r requirements.txt
```

The extractor requires DuckDB, currently pinned in `backend/requirements.txt` as:

```text
duckdb==1.5.2
```

## Generate the Dataset

Run from the backend root:

```bash
source /Users/benj/Documents/Coding/cardiac_mvp/.venv/bin/activate
cd /Users/benj/Documents/Coding/VenusHacks26/backend
python scripts/datasets/extract_mendeley_demo_doctor_notes.py
```

Default outputs:

```text
backend/data/external/mendeley-obstetric-maternal-ehr/demo_doctor_notes_50.json
backend/data/external/mendeley-obstetric-maternal-ehr/demo_doctor_notes_50.csv
backend/data/external/mendeley-obstetric-maternal-ehr/demo_doctor_notes_50_qa.json
```

The script exits with status code `1` if QA fails, even if output files were written. Inspect the QA JSON to understand the failure.

## Supported CLI Flags

The script supports these optional flags:

```bash
python scripts/datasets/extract_mendeley_demo_doctor_notes.py \
  --dataset-dir data/external/mendeley-obstetric-maternal-ehr \
  --output-json data/external/mendeley-obstetric-maternal-ehr/demo_doctor_notes_50.json \
  --output-csv data/external/mendeley-obstetric-maternal-ehr/demo_doctor_notes_50.csv \
  --qa-json data/external/mendeley-obstetric-maternal-ehr/demo_doctor_notes_50_qa.json
```

Flags:

- `--dataset-dir`: directory containing `02_Visit.csv`, `04_Condition.csv`, and `06_Note.csv`.
- `--output-json`: path for the generated JSON records.
- `--output-csv`: path for the generated CSV records.
- `--qa-json`: path for the QA summary JSON.

## Output Record Shape

Each generated record includes:

```text
demo_id
patient_id
visit_occurrence_id
group
category
age
condition_codes
note_date
note_title
original_language
original_spanish_note_excerpt
english_demo_note
extracted_factors
summary
doctor_questions
```

Notes:

- `original_language` is `es`.
- `original_spanish_note_excerpt` is a truncated Spanish source excerpt.
- `english_demo_note` is synthetic demo text generated locally from category/code evidence, not a direct translation.
- `condition_codes` are source condition codes from the same visit.

## Translate Spanish Excerpts with OpenRouter/Grok

After generating the 50-patient dataset, use the opt-in translation script to replace only `english_demo_note` with an English translation of `original_spanish_note_excerpt`.

Script location:

```text
backend/scripts/datasets/translate_mendeley_demo_doctor_notes.py
```

Set your OpenRouter key in the shell environment:

```bash
export OPENROUTER_API_KEY="your-key-here"
```

Run from the backend root:

```bash
source /Users/benj/Documents/Coding/cardiac_mvp/.venv/bin/activate
cd /Users/benj/Documents/Coding/VenusHacks26/backend
python scripts/datasets/translate_mendeley_demo_doctor_notes.py
```

Default translated outputs:

```text
backend/data/external/mendeley-obstetric-maternal-ehr/demo_doctor_notes_50_translated.json
backend/data/external/mendeley-obstetric-maternal-ehr/demo_doctor_notes_50_translated.csv
backend/data/external/mendeley-obstetric-maternal-ehr/demo_doctor_notes_50_translated_qa.json
```

The translation script uses OpenRouter's OpenAI-compatible API with this default model:

```text
x-ai/grok-4.3
```

Supported translation flags:

```bash
python scripts/datasets/translate_mendeley_demo_doctor_notes.py \
  --input-json data/external/mendeley-obstetric-maternal-ehr/demo_doctor_notes_50.json \
  --output-json data/external/mendeley-obstetric-maternal-ehr/demo_doctor_notes_50_translated.json \
  --output-csv data/external/mendeley-obstetric-maternal-ehr/demo_doctor_notes_50_translated.csv \
  --qa-json data/external/mendeley-obstetric-maternal-ehr/demo_doctor_notes_50_translated_qa.json \
  --model x-ai/grok-4.3 \
  --base-url https://openrouter.ai/api/v1 \
  --api-key-env OPENROUTER_API_KEY \
  --sleep-seconds 0.2
```

Additional translation flags:

- `--app-title`: optional OpenRouter `X-Title` header value.
- `--http-referer`: optional OpenRouter `HTTP-Referer` header value.
- `--limit`: translate only the first N records for a partial test run. Partial runs intentionally fail QA.
- `--replace-input`: write translated JSON back to `--input-json` instead of the default translated JSON path. Use only when you intentionally want to replace the original synthetic English notes.

Translation QA checks verify:

- The translated output still has 50 records.
- `english_demo_note` is nonempty for every record.
- `english_demo_note` changed for every record.
- No field except `english_demo_note` changed.
- A SHA-256 digest is written for the translated output.

The translation script sends each `original_spanish_note_excerpt` to OpenRouter. Treat this as external processing of de-identified clinical text and only run it when that is acceptable for the demo.

## QA Checks

The extraction script writes a QA summary and fails if any required check fails.

Current QA checks include:

- Exactly 50 records.
- Exactly 50 unique patients.
- Exactly 35 `cv_risk` and 15 `control` records.
- Required category counts are met.
- Required output fields are nonempty.
- No duplicate patient IDs.
- No duplicate note excerpts.
- No selected cardiovascular-risk source-code families in controls.
- Every `cv_risk` record has cardiovascular-risk source-code evidence.
- Notes contain pregnancy/postpartum relevance signals.
- Notes are not too short and are not low-value administrative note types.
- A SHA-256 digest is written for repeatability checks.

A passing QA file should contain:

```json
"passes": true
```

The validated run produced this repeatable digest:

```text
eadc1e6e61f8c125136131db7234b5f575ee5a11eab91148927432649922403b
```

## Important Implementation Details

- The script uses DuckDB instead of Python row loops because `06_Note.csv` is large.
- `06_Note.csv` contains multiline quoted clinical text, so the script reads it with `parallel=false`.
- CSV fields are read with `all_varchar=true` to avoid brittle type inference over clinical free text.
- The DuckDB connection sets:

```text
memory_limit='8GB'
threads=1
preserve_insertion_order=false
```

- Candidate notes are joined to eligible visits by both `visit_occurrence_id` and `person_id`.
- Source condition codes are used as evidence because OMOP vocabulary mapping tables are not included in the downloaded Mendeley dataset.

## Data Handling Cautions

Treat the source Spanish notes as sensitive, even though the dataset is de-identified.

Do not:

- Commit raw dataset files or generated demo output files.
- Paste full raw notes into public tools, tickets, or documentation.
- Send raw note text to external LLMs or translation services without a clear compliance decision.
- Use unofficial mirrors for restricted datasets such as MIMIC-IV-Note or i2b2/n2c2.

For public demos, prefer using the generated synthetic English demo note and structured factors. Keep Spanish excerpts for local traceability and QA only unless explicitly approved for display.

## Troubleshooting

If DuckDB is missing:

```bash
python -m pip install -r requirements.txt
```

If the script fails with QA output:

1. Open `demo_doctor_notes_50_qa.json`.
2. Check arrays like `pregnancy_relevance_misses`, `control_risk_leaks`, `cv_without_codes`, and `short_or_generic_notes`.
3. Inspect the matching `demo_id` in `demo_doctor_notes_50.json`.
4. Patch selection or QA logic only if the record is clinically appropriate and the script is too strict or too loose.
5. Re-run the script and confirm the SHA-256 digest is stable across repeated runs.
