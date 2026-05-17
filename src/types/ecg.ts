export type AppleWatchEcgWindowPolicy = 'first' | 'sliding'

export type AppleWatchEcgVoltageMeasurement = {
  voltage: number | string
  [key: string]: unknown
}

export type AppleWatchEcgRecord = {
  start?: string | null
  end?: string | null
  classification?: string | null
  averageHeartRate?: number | string | null
  samplingFrequency: number | string
  numberOfVoltageMeasurements?: number | string | null
  source?: unknown
  voltageMeasurements: AppleWatchEcgVoltageMeasurement[]
  [key: string]: unknown
}

export type AppleWatchHealthExportPayload = {
  data: {
    ecg: AppleWatchEcgRecord[]
    [key: string]: unknown
  }
  [key: string]: unknown
}

export type AppleWatchEcgInferRequest = {
  healthExport?: AppleWatchHealthExportPayload
  ecgRecord?: AppleWatchEcgRecord
  recordIndex?: number
  windowPolicy: AppleWatchEcgWindowPolicy
  threshold: number
}

export type AppleWatchEcgPrediction = {
  window_index: number
  window_start_sample: number
  window_end_sample: number
  window_duration_sec: number
  window_target_samples: number
  prob_any_abnormal: number
  pred_any_abnormal: boolean
  labels_above_threshold: string[]
  probabilities: Record<string, number>
}

export type AppleWatchEcgInferResponse = {
  record_index: number
  record_metadata: Record<string, unknown>
  window_policy: AppleWatchEcgWindowPolicy | string
  threshold: number
  target_samples: number
  checkpoint_sampling_rate_hz: number
  duration_sec: number
  target_names: string[]
  predictions: AppleWatchEcgPrediction[]
  caveat: string
}

export type AppleWatchEcgRecordSummary = {
  index: number
  start?: string
  end?: string
  classification?: string
  averageHeartRate?: string
  samplingFrequency?: string
  voltageMeasurementCount: number
}

export type ParsedAppleWatchEcgUpload =
  | {
      kind: 'healthExport'
      healthExport: AppleWatchHealthExportPayload
      recordSummaries: AppleWatchEcgRecordSummary[]
    }
  | {
      kind: 'ecgRecord'
      ecgRecord: AppleWatchEcgRecord
      recordSummaries: AppleWatchEcgRecordSummary[]
    }

export type AppleWatchEcgApiErrorCode =
  | 'network'
  | 'validation'
  | 'too_large'
  | 'unavailable'
  | 'unexpected'

export class AppleWatchEcgApiError extends Error {
  readonly code: AppleWatchEcgApiErrorCode
  readonly userMessage: string

  constructor(code: AppleWatchEcgApiErrorCode, userMessage: string) {
    super(userMessage)
    this.code = code
    this.userMessage = userMessage
  }
}
