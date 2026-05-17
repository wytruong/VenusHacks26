import {
  type PrenatalCvdRequest,
  type PrenatalCvdResponse,
  ScreeningApiError,
} from '../types/screening'

const DEFAULT_API_BASE_URL = 'http://127.0.0.1:45261'
const API_BASE_URL =
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

export async function submitPrenatalCvdScreening(
  payload: PrenatalCvdRequest,
): Promise<PrenatalCvdResponse> {
  let response: Response

  try {
    response = await fetch(`${API_BASE_URL}/api/screening/prenatal-cvd`, {
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
    throw new ScreeningApiError(
      'validation',
      'Some answers are missing or invalid. Please review your risk profile and try again.',
    )
  }

  if (response.status === 503) {
    throw new ScreeningApiError(
      'unavailable',
      'Prenatal screening is temporarily unavailable. Please try again later or contact your care team.',
    )
  }

  if (!response.ok) {
    throw new ScreeningApiError(
      'unexpected',
      'We could not complete your screening right now. Please try again shortly.',
    )
  }

  const data: unknown = await response.json()

  if (!isPrenatalCvdResponse(data)) {
    throw new ScreeningApiError(
      'unexpected',
      'We received an unexpected response. Please try again later.',
    )
  }

  return data
}
