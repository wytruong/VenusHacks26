import type { PrenatalCvdRequest } from '../../types/screening'
import type { RiskFactors } from './riskProfile.types'

export function createEmptyRiskFactors(
  mode: 'prenatal' | 'postpartum',
): RiskFactors {
  return {
    pregnancyMode: mode,
    age: '',
    prepregnancyBmi: '',
    chronicHypertension: null,
    diabetes: null,
    priorPretermOrStillbirth: null,
    liveBirthsCount: '',
    smokedPregnancy: null,
    multipleGestation: null,
    gestationalHypertension: null,
    gestationalDiabetes: null,
    severeComplications: null,
    birthBefore37Weeks: null,
    birthUnder5_5lbs: null,
  }
}

export function buildRiskFactorsPayload(rf: RiskFactors): Record<string, unknown> {
  const common = {
    pregnancyMode: rf.pregnancyMode,
    age: rf.age,
    prepregnancyBmi: rf.prepregnancyBmi,
    chronicHypertension: rf.chronicHypertension,
    diabetes: rf.diabetes,
    priorPretermOrStillbirth: rf.priorPretermOrStillbirth,
    liveBirthsCount: rf.liveBirthsCount,
    smokedPregnancy: rf.smokedPregnancy,
    multipleGestation: rf.multipleGestation,
  }
  if (rf.pregnancyMode === 'postpartum') {
    return {
      ...common,
      gestationalHypertension: rf.gestationalHypertension,
      gestationalDiabetes: rf.gestationalDiabetes,
      severeComplications: rf.severeComplications,
      birthBefore37Weeks: rf.birthBefore37Weeks,
      birthUnder5_5lbs: rf.birthUnder5_5lbs,
    }
  }
  return common
}

export function validatePrenatalRiskFactors(rf: RiskFactors): string | null {
  if (rf.pregnancyMode !== 'prenatal') {
    return 'Postpartum screening is coming soon.'
  }
  if (!rf.age.trim() || Number.isNaN(Number(rf.age))) {
    return 'Please enter your age.'
  }
  if (!rf.prepregnancyBmi.trim() || Number.isNaN(Number(rf.prepregnancyBmi))) {
    return 'Please enter your pre-pregnancy BMI.'
  }
  if (!rf.liveBirthsCount.trim() || Number.isNaN(Number(rf.liveBirthsCount))) {
    return 'Please enter your number of prior live births.'
  }
  if (rf.chronicHypertension === null) {
    return 'Please answer whether you have chronic high blood pressure.'
  }
  if (rf.diabetes === null) {
    return 'Please answer whether you have diabetes.'
  }
  if (rf.priorPretermOrStillbirth === null) {
    return 'Please answer whether you had a preterm birth or stillbirth before.'
  }
  if (rf.smokedPregnancy === null) {
    return 'Please answer whether you smoked before or during pregnancy.'
  }
  if (rf.multipleGestation === null) {
    return 'Please answer whether you are carrying more than one baby.'
  }
  return null
}

export function toPrenatalCvdRequest(rf: RiskFactors): PrenatalCvdRequest {
  return {
    pregnancyMode: 'prenatal',
    age: rf.age.trim(),
    prepregnancyBmi: rf.prepregnancyBmi.trim(),
    chronicHypertension: rf.chronicHypertension as boolean,
    diabetes: rf.diabetes as boolean,
    priorPretermOrStillbirth: rf.priorPretermOrStillbirth as boolean,
    liveBirthsCount: rf.liveBirthsCount.trim(),
    smokedPregnancy: rf.smokedPregnancy as boolean,
    multipleGestation: rf.multipleGestation as boolean,
  }
}
