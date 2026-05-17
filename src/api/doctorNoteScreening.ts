import type { DemoDoctorNoteRecord } from '../features/doctor-note/demoDoctorNotes'
import type { DoctorNoteScreeningResult } from '../features/doctor-note/doctorNote.types'
import { API_BASE_URL } from './screening'

const DOCTOR_NOTE_SCREENING_TIMEOUT_MS = 160_000

export type DoctorNoteScreeningRequest = {
  sessionId: string
  record: DemoDoctorNoteRecord
}

export class DoctorNoteScreeningApiError extends Error {
  readonly userMessage: string

  constructor(userMessage: string) {
    super(userMessage)
    this.name = 'DoctorNoteScreeningApiError'
    this.userMessage = userMessage
  }
}

function createDoctorNoteScreeningRequestId() {
  return `doctor-note-screening-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function isRecordOrNull(value: unknown): value is Record<string, unknown> | null {
  return value === null || Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

function isDoctorNoteScreeningResult(data: unknown): data is DoctorNoteScreeningResult {
  if (!data || typeof data !== 'object') return false
  const candidate = data as Record<string, unknown>
  if (!candidate.insight || typeof candidate.insight !== 'object' || Array.isArray(candidate.insight)) {
    return false
  }
  const insight = candidate.insight as Record<string, unknown>

  return (
    (candidate.status === 'processed' ||
      candidate.status === 'no_screening_context' ||
      candidate.status === 'extraction_failed' ||
      candidate.status === 'screening_unavailable') &&
    (candidate.screeningContext === 'prenatal' ||
      candidate.screeningContext === 'postnatal' ||
      candidate.screeningContext === 'none') &&
    isRecordOrNull(candidate.extractedInput) &&
    isRecordOrNull(candidate.riskResult) &&
    isStringArray(candidate.evidence) &&
    isStringArray(candidate.missingOrUncertainFields) &&
    typeof insight.title === 'string' &&
    typeof insight.riskLabel === 'string' &&
    typeof insight.summary === 'string' &&
    typeof insight.recommendedFollowup === 'string' &&
    (insight.safetyNote === undefined ||
      insight.safetyNote === null ||
      typeof insight.safetyNote === 'string')
  )
}

export async function submitDoctorNoteScreening(
  payload: DoctorNoteScreeningRequest,
): Promise<DoctorNoteScreeningResult> {
  let response: Response
  const requestId = createDoctorNoteScreeningRequestId()
  const startedAt = performance.now()
  const url = `${API_BASE_URL}/api/agents/doctor-note-screening`
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), DOCTOR_NOTE_SCREENING_TIMEOUT_MS)

  console.info('[doctor-note-screening] request:start', {
    requestId,
    url,
    sessionId: payload.sessionId,
    demoId: payload.record.demoId,
  })

  try {
    response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Request-ID': requestId,
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
  } catch (error) {
    const elapsedMs = Math.round(performance.now() - startedAt)
    if (error instanceof DOMException && error.name === 'AbortError') {
      console.error('[doctor-note-screening] request:timeout', { requestId, elapsedMs })
      throw new DoctorNoteScreeningApiError(
        'Doctor-note screening is taking too long. You can still ask about the note summary.',
      )
    }

    console.error('[doctor-note-screening] request:network-error', { requestId, elapsedMs, error })
    throw new DoctorNoteScreeningApiError(
      'We could not connect to doctor-note screening. You can still ask about the note summary.',
    )
  } finally {
    window.clearTimeout(timeoutId)
  }

  console.info('[doctor-note-screening] request:response', {
    requestId,
    status: response.status,
    ok: response.ok,
    elapsedMs: Math.round(performance.now() - startedAt),
  })

  if (response.status === 422) {
    throw new DoctorNoteScreeningApiError('This demo note is missing required text for screening.')
  }

  if (response.status === 503) {
    throw new DoctorNoteScreeningApiError(
      'Doctor-note screening is temporarily unavailable. You can still ask about the note summary.',
    )
  }

  if (!response.ok) {
    throw new DoctorNoteScreeningApiError(
      'We could not process this note for screening right now. You can still ask about the note summary.',
    )
  }

  const data: unknown = await response.json()

  if (!isDoctorNoteScreeningResult(data)) {
    console.error('[doctor-note-screening] request:invalid-response', { requestId, data })
    throw new DoctorNoteScreeningApiError(
      'We received an unexpected screening response. You can still ask about the note summary.',
    )
  }

  console.info('[doctor-note-screening] request:success', {
    requestId,
    status: data.status,
    screeningContext: data.screeningContext,
    elapsedMs: Math.round(performance.now() - startedAt),
  })

  return data
}
