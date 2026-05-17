export type DoctorNoteScreeningInsight = {
  title: string
  riskLabel: string
  summary: string
  recommendedFollowup: string
  safetyNote?: string | null
}

export type DoctorNoteScreeningResult = {
  status: 'processed' | 'no_screening_context' | 'extraction_failed' | 'screening_unavailable'
  screeningContext: 'prenatal' | 'postnatal' | 'none'
  extractedInput: Record<string, unknown> | null
  riskResult: Record<string, unknown> | null
  evidence: string[]
  missingOrUncertainFields: string[]
  insight: DoctorNoteScreeningInsight
}

export type DoctorNoteOcrResult = {
  condition: string
  region: string
  risk: string
  description: string
  doctorScript: string
  questions: readonly string[]
  screening?: DoctorNoteScreeningResult | null
}
