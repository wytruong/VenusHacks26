import type { PregnancyRiskTier, PrenatalCvdResponse } from '../../types/screening'

export type RiskFactors = {
  pregnancyMode: 'prenatal' | 'postpartum'
  age: string
  prepregnancyBmi: string
  chronicHypertension: boolean | null
  diabetes: boolean | null
  priorPretermOrStillbirth: boolean | null
  liveBirthsCount: string
  smokedPregnancy: boolean | null
  multipleGestation: boolean | null
  gestationalHypertension: boolean | null
  gestationalDiabetes: boolean | null
  severeComplications: boolean | null
  birthBefore37Weeks: boolean | null
  birthUnder5_5lbs: boolean | null
}

export type PregnancyRiskResult = PrenatalCvdResponse
export type { PregnancyRiskTier }