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

export type PostnatalFollowupRequest = {
  mother_age: string
  mother_bmi: string
  prepregnancy_hypertension: boolean
  prepregnancy_diabetes: boolean
  prior_live_births: string
  prior_dead_births: string
  previous_preterm_birth: boolean
  previous_cesarean: boolean
  previous_cesarean_count: string
  gestational_hypertension: boolean
  eclampsia: boolean
  gestational_diabetes: boolean
  maternal_transfusion: boolean
  ruptured_uterus: boolean
  unplanned_hysterectomy: boolean
  maternal_icu: boolean
  obstetric_estimate_gestation_weeks: string
  birth_weight_grams: string
  abnormal_condition_nicu: boolean
  apgar_5_min: string
  apgar_10_min: string
}

export type PostnatalFollowupSignal = {
  present?: boolean
  tier?: string
  main_factors?: string[]
}

export type PostnatalFollowupResponse = {
  model_mode: string
  model_name?: string
  model_version?: string
  routing_method?: string
  overall_followup_priority: string
  hypertension_followup_signal?: PostnatalFollowupSignal
  diabetes_followup_signal?: PostnatalFollowupSignal
  maternal_cv_metabolic_followup_signal?: PostnatalFollowupSignal
  obstetric_neonatal_context_signal?: PostnatalFollowupSignal
  severe_maternal_morbidity_followup_signal?: PostnatalFollowupSignal
  auxiliary_ml_scores?: Record<string, unknown>
  context_flags?: string[]
  missing_inputs?: string[]
  data_quality_warnings?: string[]
  safety_note?: string
}

export type ScreeningResponse = PrenatalCvdResponse | PostnatalFollowupResponse

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
