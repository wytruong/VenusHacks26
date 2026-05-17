export type PregnancyRiskTier = 'low' | 'medium' | 'high'

export type PrenatalCvdRequest = {
  pregnancyMode: 'prenatal'
  age: string
  prepregnancyBmi: string
  chronicHypertension: boolean
  diabetes: boolean
  priorPretermOrStillbirth: boolean
  liveBirthsCount: string
  smokedPregnancy: boolean
  multipleGestation: boolean
}

export type PrenatalCvdResponse = {
  model_mode: string
  risk_tier: PregnancyRiskTier
  recommended_followup_priority: string
  main_contributing_factors: string[]
  prenatal_cvd_followup_proxy_probability?: number
  current_composite_signal?: {
    probability?: number
    tier?: string
    use?: string
  }
  safety_note?: string
  disclaimer?: string
}

export type ScreeningApiErrorCode =
  | 'network'
  | 'validation'
  | 'unavailable'
  | 'unexpected'

export class ScreeningApiError extends Error {
  readonly code: ScreeningApiErrorCode
  readonly userMessage: string

  constructor(code: ScreeningApiErrorCode, userMessage: string) {
    super(userMessage)
    this.code = code
    this.userMessage = userMessage
  }
}
