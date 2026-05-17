import demoDoctorNotesCsv from '../../../backend/data/external/mendeley-obstetric-maternal-ehr/demo_doctor_notes_50_translated.csv?raw'
import type { DoctorNoteOcrResult } from './doctorNote.types'

export type DemoDoctorNoteRecord = {
  demoId: string
  patientId: string
  visitOccurrenceId: string
  group: string
  category: string
  age: string
  conditionCodes: string
  noteDate: string
  noteTitle: string
  englishDemoNote: string
  extractedFactors: string
  summary: string
  doctorQuestions: string
}

const CSV_COLUMNS = [
  'demo_id',
  'patient_id',
  'visit_occurrence_id',
  'group',
  'category',
  'age',
  'condition_codes',
  'note_date',
  'note_title',
  'original_language',
  'original_spanish_note_excerpt',
  'english_demo_note',
  'extracted_factors',
  'summary',
  'doctor_questions',
] as const

function parseCsvLine(line: string) {
  const values: string[] = []
  let current = ''
  let quoted = false

  for (let i = 0; i < line.length; i += 1) {
    const character = line[i]
    const nextCharacter = line[i + 1]

    if (character === '"' && quoted && nextCharacter === '"') {
      current += '"'
      i += 1
    } else if (character === '"') {
      quoted = !quoted
    } else if (character === ',' && !quoted) {
      values.push(current)
      current = ''
    } else {
      current += character
    }
  }

  values.push(current)
  return values
}

function parseCsvRows(csv: string) {
  const rows: string[][] = []
  let current = ''
  let quoted = false

  for (let i = 0; i < csv.length; i += 1) {
    const character = csv[i]
    const nextCharacter = csv[i + 1]

    if (character === '"' && quoted && nextCharacter === '"') {
      current += '"'
      i += 1
    } else if (character === '"') {
      quoted = !quoted
      current += character
    } else if ((character === '\n' || character === '\r') && !quoted) {
      if (current.trim()) rows.push(parseCsvLine(current))
      current = ''
      if (character === '\r' && nextCharacter === '\n') i += 1
    } else {
      current += character
    }
  }

  if (current.trim()) rows.push(parseCsvLine(current))
  return rows
}

function humanize(value: string) {
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(' ')
}

function getValue(row: Record<string, string>, key: (typeof CSV_COLUMNS)[number]) {
  return row[key]?.trim() ?? ''
}

export const DEMO_DOCTOR_NOTE_RECORDS: DemoDoctorNoteRecord[] = parseCsvRows(demoDoctorNotesCsv)
  .slice(1)
  .map((values) => {
    const row = Object.fromEntries(CSV_COLUMNS.map((column, index) => [column, values[index] ?? '']))
    return {
      demoId: getValue(row, 'demo_id'),
      patientId: getValue(row, 'patient_id'),
      visitOccurrenceId: getValue(row, 'visit_occurrence_id'),
      group: getValue(row, 'group'),
      category: getValue(row, 'category'),
      age: getValue(row, 'age'),
      conditionCodes: getValue(row, 'condition_codes'),
      noteDate: getValue(row, 'note_date'),
      noteTitle: getValue(row, 'note_title'),
      englishDemoNote: getValue(row, 'english_demo_note'),
      extractedFactors: getValue(row, 'extracted_factors'),
      summary: getValue(row, 'summary'),
      doctorQuestions: getValue(row, 'doctor_questions'),
    }
  })

export function toDoctorNoteOcrResult(record: DemoDoctorNoteRecord): DoctorNoteOcrResult {
  return {
    condition: humanize(record.category),
    region: 'Translated demo note awaiting screening',
    risk: 'PENDING',
    description: record.summary,
    doctorScript: record.englishDemoNote,
    questions: record.doctorQuestions
      .split('|')
      .map((question) => question.trim())
      .filter(Boolean),
  }
}
