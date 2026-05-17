import type {
  PregnancyRiskTier,
  PostnatalFollowupResponse,
  PrenatalCvdResponse,
} from '../../types/screening'

type SharedRiskFactorFields = {
  age: string
  prepregnancyHeightFeet: string
  prepregnancyHeightInches: string
  prepregnancyWeightLb: string
  chronicHypertension: boolean | null
  diabetes: boolean | null
}

export type PrenatalRiskFactors = SharedRiskFactorFields & {
  pregnancyMode: 'prenatal'
  priorPretermOrStillbirth: boolean | null
  liveBirthsCount: string
  smokedPregnancy: boolean | null
  multipleGestation: boolean | null
}

export type PostnatalRiskFactors = SharedRiskFactorFields & {
  pregnancyMode: 'postpartum'
  priorLiveBirths: string
  priorDeadBirths: string
  previousPretermBirth: boolean | null
  previousCesarean: boolean | null
  previousCesareanCount: string
  gestationalHypertension: boolean | null
  eclampsia: boolean | null
  gestationalDiabetes: boolean | null
  maternalTransfusion: boolean | null
  rupturedUterus: boolean | null
  unplannedHysterectomy: boolean | null
  maternalIcu: boolean | null
  gestationalAgeWeeks: string
  birthWeightGrams: string
  abnormalConditionNicu: boolean | null
  apgar5Min: string
  apgar10Min: string
}

export type RiskFactors = PrenatalRiskFactors | PostnatalRiskFactors
export type PregnancyRiskResult = PrenatalCvdResponse | PostnatalFollowupResponse
export type { PregnancyRiskTier }
