import {
  type PostnatalFollowupRequest,
  type PostnatalFollowupResponse,
  type PostnatalFollowupSignal,
  type PrenatalCvdRequest,
  type PrenatalCvdResponse,
  ScreeningApiError,
} from '../types/screening'

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:45261'
export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ||
  DEFAULT_API_BASE_URL

function isPrenatalCvdResponse(data: unknown): data is PrenatalCvdResponse {
  if (!data || typeof data !== 'object') return false
  const candidate = data as Record<string, unknown>

  const riskTierValid =
    candidate.risk_tier === 'low' ||
    candidate.risk_tier === 'medium' ||
    candidate.risk_tier === 'high'

  const factorsValid =
    Array.isArray(candidate.main_contributing_factors) &&
    candidate.main_contributing_factors.every((factor) => typeof factor === 'string')

  const proxyProbabilityValid =
    candidate.prenatal_cvd_followup_proxy_probability === undefined ||
    typeof candidate.prenatal_cvd_followup_proxy_probability === 'number'

  const compositeProbability =
    candidate.current_composite_signal &&
    typeof candidate.current_composite_signal === 'object'
      ? (candidate.current_composite_signal as Record<string, unknown>).probability
      : undefined

  const compositeProbabilityValid =
    compositeProbability === undefined || typeof compositeProbability === 'number'

  return (
    typeof candidate.model_mode === 'string' &&
    riskTierValid &&
    typeof candidate.recommended_followup_priority === 'string' &&
    factorsValid &&
    proxyProbabilityValid &&
    compositeProbabilityValid
  )
}

function isPostnatalSignal(data: unknown): data is PostnatalFollowupSignal {
  if (data === undefined) return true
  if (!data || typeof data !== 'object') return false

  const candidate = data as Record<string, unknown>
  const mainFactors = candidate.main_factors

  return (
    (candidate.present === undefined || typeof candidate.present === 'boolean') &&
    (candidate.tier === undefined || typeof candidate.tier === 'string') &&
    (mainFactors === undefined ||
      (Array.isArray(mainFactors) && mainFactors.every((factor) => typeof factor === 'string')))
  )
}

function isStringArray(data: unknown): data is string[] {
  return Array.isArray(data) && data.every((item) => typeof item === 'string')
}

function isPostnatalFollowupResponse(data: unknown): data is PostnatalFollowupResponse {
  if (!data || typeof data !== 'object') return false
  const candidate = data as Record<string, unknown>

  return (
    typeof candidate.model_mode === 'string' &&
    typeof candidate.overall_followup_priority === 'string' &&
    isPostnatalSignal(candidate.hypertension_followup_signal) &&
    isPostnatalSignal(candidate.diabetes_followup_signal) &&
    isPostnatalSignal(candidate.maternal_cv_metabolic_followup_signal) &&
    isPostnatalSignal(candidate.obstetric_neonatal_context_signal) &&
    isPostnatalSignal(candidate.severe_maternal_morbidity_followup_signal) &&
    (candidate.missing_inputs === undefined || isStringArray(candidate.missing_inputs)) &&
    (candidate.data_quality_warnings === undefined || isStringArray(candidate.data_quality_warnings)) &&
    (candidate.safety_note === undefined || typeof candidate.safety_note === 'string')
  )
}

async function postScreeningRequest<TResponse>(
  endpoint: string,
  payload: unknown,
  isExpectedResponse: (data: unknown) => data is TResponse,
  messages: {
    validation: string
    unavailable: string
  },
): Promise<TResponse> {
  let response: Response

  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })
  } catch {
    throw new ScreeningApiError(
      'network',
      'We could not connect right now. Please check your connection and try again.',
    )
  }

  if (response.status === 422) {
    throw new ScreeningApiError('validation', messages.validation)
  }

  if (response.status === 503) {
    throw new ScreeningApiError('unavailable', messages.unavailable)
  }

  if (!response.ok) {
    throw new ScreeningApiError(
      'unexpected',
      'We could not complete your screening right now. Please try again shortly.',
    )
  }

  const data: unknown = await response.json()

  if (!isExpectedResponse(data)) {
    throw new ScreeningApiError(
      'unexpected',
      'We received an unexpected response. Please try again later.',
    )
  }

  return data
}

export async function submitPrenatalCvdScreening(
  payload: PrenatalCvdRequest,
): Promise<PrenatalCvdResponse> {
  return postScreeningRequest(
    '/api/screening/prenatal-cvd',
    payload,
    isPrenatalCvdResponse,
    {
      validation: 'Some answers are missing or invalid. Please review your risk profile and try again.',
      unavailable:
        'Prenatal screening is temporarily unavailable. Please try again later or contact your care team.',
    },
  )
}

export async function submitPostnatalFollowupScreening(
  payload: PostnatalFollowupRequest,
): Promise<PostnatalFollowupResponse> {
  return postScreeningRequest(
    '/api/screening/postnatal-followup',
    payload,
    isPostnatalFollowupResponse,
    {
      validation: 'Some postpartum answers are missing or invalid. Please review your risk profile and try again.',
      unavailable:
        'Postnatal follow-up screening is temporarily unavailable. Please try again later or contact your care team.',
    },
  )
}
