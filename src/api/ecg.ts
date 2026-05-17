import { API_BASE_URL } from './screening'
import {
  AppleWatchEcgApiError,
  type AppleWatchEcgInferRequest,
  type AppleWatchEcgInferResponse,
  type AppleWatchEcgPrediction,
} from '../types/ecg'

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string')
}

function isNumberRecord(value: unknown): value is Record<string, number> {
  return isRecord(value) && Object.values(value).every((item) => typeof item === 'number')
}

function isPrediction(value: unknown): value is AppleWatchEcgPrediction {
  if (!isRecord(value)) return false

  return (
    typeof value.window_index === 'number' &&
    typeof value.window_start_sample === 'number' &&
    typeof value.window_end_sample === 'number' &&
    typeof value.window_duration_sec === 'number' &&
    typeof value.window_target_samples === 'number' &&
    typeof value.prob_any_abnormal === 'number' &&
    typeof value.pred_any_abnormal === 'boolean' &&
    isStringArray(value.labels_above_threshold) &&
    isNumberRecord(value.probabilities)
  )
}

function isAppleWatchEcgInferResponse(data: unknown): data is AppleWatchEcgInferResponse {
  if (!isRecord(data)) return false

  return (
    typeof data.record_index === 'number' &&
    isRecord(data.record_metadata) &&
    typeof data.window_policy === 'string' &&
    typeof data.threshold === 'number' &&
    typeof data.target_samples === 'number' &&
    typeof data.checkpoint_sampling_rate_hz === 'number' &&
    typeof data.duration_sec === 'number' &&
    isStringArray(data.target_names) &&
    Array.isArray(data.predictions) &&
    data.predictions.every(isPrediction) &&
    typeof data.caveat === 'string'
  )
}

export async function submitAppleWatchEcgInference(
  payload: AppleWatchEcgInferRequest,
): Promise<AppleWatchEcgInferResponse> {
  let response: Response

  try {
    response = await fetch(`${API_BASE_URL}/api/ecg/apple-watch/infer`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })
  } catch {
    throw new AppleWatchEcgApiError(
      'network',
      'We could not connect to the ECG analysis service. Please check your connection and try again.',
    )
  }

  if (response.status === 422) {
    throw new AppleWatchEcgApiError(
      'validation',
      'This JSON does not look like a valid Apple Watch ECG export. Please review the file and try again.',
    )
  }

  if (response.status === 413) {
    throw new AppleWatchEcgApiError(
      'too_large',
      'This ECG JSON file is too large for the demo upload. Please choose a smaller export.',
    )
  }

  if (response.status === 503) {
    throw new AppleWatchEcgApiError(
      'unavailable',
      'Apple Watch ECG model analysis is temporarily unavailable. Please try again later.',
    )
  }

  if (!response.ok) {
    throw new AppleWatchEcgApiError(
      'unexpected',
      'We could not analyze this ECG file right now. Please try again shortly.',
    )
  }

  const data: unknown = await response.json()

  if (!isAppleWatchEcgInferResponse(data)) {
    throw new AppleWatchEcgApiError(
      'unexpected',
      'We received an unexpected ECG model response. Please try again later.',
    )
  }

  return data
}
