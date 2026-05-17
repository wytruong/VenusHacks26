import type { PostnatalFollowupRequest, PrenatalCvdRequest } from '../../types/screening'
import type { PostnatalRiskFactors, PrenatalRiskFactors, RiskFactors } from './riskProfile.types'

const BMI_DECIMAL_PLACES = 1

function sharedRiskFactorDefaults<TMode extends 'prenatal' | 'postpartum'>(mode: TMode) {
  return {
    pregnancyMode: mode,
    age: '',
    prepregnancyHeightFeet: '',
    prepregnancyHeightInches: '',
    prepregnancyWeightLb: '',
    chronicHypertension: null,
    diabetes: null,
  }
}

export function createEmptyRiskFactors(mode: 'prenatal'): PrenatalRiskFactors
export function createEmptyRiskFactors(mode: 'postpartum'): PostnatalRiskFactors
export function createEmptyRiskFactors(mode: 'prenatal' | 'postpartum'): RiskFactors
export function createEmptyRiskFactors(mode: 'prenatal' | 'postpartum'): RiskFactors {
  if (mode === 'postpartum') {
    return {
      ...sharedRiskFactorDefaults(mode),
      priorLiveBirths: '',
      priorDeadBirths: '',
      previousPretermBirth: null,
      previousCesarean: null,
      previousCesareanCount: '',
      gestationalHypertension: null,
      eclampsia: null,
      gestationalDiabetes: null,
      maternalTransfusion: null,
      rupturedUterus: null,
      unplannedHysterectomy: null,
      maternalIcu: null,
      gestationalAgeWeeks: '',
      birthWeightGrams: '',
      abnormalConditionNicu: null,
      apgar5Min: '',
      apgar10Min: '',
    }
  }

  return {
    ...sharedRiskFactorDefaults(mode),
    priorPretermOrStillbirth: null,
    liveBirthsCount: '',
    smokedPregnancy: null,
    multipleGestation: null,
  }
}

function parseNumber(value: string): number | null {
  if (!value.trim()) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function isWholeNumber(value: string): boolean {
  const parsed = parseNumber(value)
  return parsed !== null && Number.isInteger(parsed) && parsed >= 0
}

function hasAnswered(value: boolean | null): value is boolean {
  return value !== null
}

function getResolvedAge(riskFactors: RiskFactors, profileAge: string): string {
  return profileAge.trim() || riskFactors.age.trim()
}

function validateAge(riskFactors: RiskFactors, profileAge: string): string | null {
  const resolvedAge = getResolvedAge(riskFactors, profileAge)
  const parsedAge = parseNumber(resolvedAge)

  if (parsedAge === null || parsedAge < 0) {
    return 'Please enter a valid age before continuing.'
  }

  return null
}

function validateBmiInputs(riskFactors: RiskFactors): string | null {
  const feet = parseNumber(riskFactors.prepregnancyHeightFeet)
  const inches = parseNumber(riskFactors.prepregnancyHeightInches)
  const weight = parseNumber(riskFactors.prepregnancyWeightLb)

  if (feet === null || !Number.isInteger(feet) || feet < 0) {
    return 'Please enter your pre-pregnancy height in feet.'
  }

  if (inches === null || inches < 0 || inches >= 12) {
    return 'Please enter height inches from 0 to 11.'
  }

  if (weight === null || weight <= 0) {
    return 'Please enter a valid pre-pregnancy weight.'
  }

  if (feet * 12 + inches <= 0) {
    return 'Please enter a valid pre-pregnancy height.'
  }

  return null
}

export function calculatePrepregnancyBmi(riskFactors: RiskFactors): number | null {
  if (validateBmiInputs(riskFactors)) return null

  const feet = Number(riskFactors.prepregnancyHeightFeet)
  const inches = Number(riskFactors.prepregnancyHeightInches)
  const weight = Number(riskFactors.prepregnancyWeightLb)
  const totalHeightInches = feet * 12 + inches

  return weight / (totalHeightInches * totalHeightInches) * 703
}

export function formatCalculatedBmi(bmi: number | null): string | null {
  if (bmi === null || !Number.isFinite(bmi)) return null
  return bmi.toFixed(BMI_DECIMAL_PLACES)
}

function requireYesNo(value: boolean | null, message: string): string | null {
  return hasAnswered(value) ? null : message
}

export function validatePrenatalRiskFactors(
  riskFactors: RiskFactors,
  profileAge: string,
): string | null {
  if (riskFactors.pregnancyMode !== 'prenatal') return null

  return (
    validateAge(riskFactors, profileAge) ??
    validateBmiInputs(riskFactors) ??
    requireYesNo(
      riskFactors.chronicHypertension,
      'Please answer whether you had chronic high blood pressure before pregnancy.',
    ) ??
    requireYesNo(
      riskFactors.diabetes,
      'Please answer whether you had diabetes before pregnancy.',
    ) ??
    requireYesNo(
      riskFactors.priorPretermOrStillbirth,
      'Please answer whether you had a preterm birth or stillbirth before.',
    ) ??
    (!isWholeNumber(riskFactors.liveBirthsCount)
      ? 'Please enter a whole number for live births count.'
      : null) ??
    requireYesNo(
      riskFactors.smokedPregnancy,
      'Please answer whether you smoked before or during pregnancy.',
    ) ??
    requireYesNo(
      riskFactors.multipleGestation,
      'Please answer whether you are carrying more than one baby.',
    )
  )
}

export function validatePostnatalRiskFactors(
  riskFactors: RiskFactors,
  profileAge: string,
): string | null {
  if (riskFactors.pregnancyMode !== 'postpartum') return null

  return (
    validateAge(riskFactors, profileAge) ??
    validateBmiInputs(riskFactors) ??
    requireYesNo(
      riskFactors.chronicHypertension,
      'Please answer whether you had chronic high blood pressure before pregnancy.',
    ) ??
    requireYesNo(
      riskFactors.diabetes,
      'Please answer whether you had diabetes before pregnancy.',
    ) ??
    (!isWholeNumber(riskFactors.priorLiveBirths)
      ? 'Please enter a whole number for prior live births.'
      : null) ??
    (!isWholeNumber(riskFactors.priorDeadBirths)
      ? 'Please enter a whole number for prior stillbirths or fetal losses.'
      : null) ??
    requireYesNo(
      riskFactors.previousPretermBirth,
      'Please answer whether you previously had a preterm birth.',
    ) ??
    requireYesNo(
      riskFactors.previousCesarean,
      'Please answer whether you previously had a cesarean delivery.',
    ) ??
    (!isWholeNumber(riskFactors.previousCesareanCount)
      ? 'Please enter a whole number for previous cesarean count.'
      : null) ??
    requireYesNo(
      riskFactors.gestationalHypertension,
      'Please answer whether you developed high blood pressure during pregnancy.',
    ) ??
    requireYesNo(
      riskFactors.eclampsia,
      'Please answer whether you had eclampsia.',
    ) ??
    requireYesNo(
      riskFactors.gestationalDiabetes,
      'Please answer whether you developed gestational diabetes.',
    ) ??
    requireYesNo(
      riskFactors.maternalTransfusion,
      'Please answer whether you had a maternal blood transfusion.',
    ) ??
    requireYesNo(
      riskFactors.rupturedUterus,
      'Please answer whether you had a ruptured uterus.',
    ) ??
    requireYesNo(
      riskFactors.unplannedHysterectomy,
      'Please answer whether you had an unplanned hysterectomy.',
    ) ??
    requireYesNo(
      riskFactors.maternalIcu,
      'Please answer whether you needed ICU care.',
    ) ??
    (parseNumber(riskFactors.gestationalAgeWeeks) === null
      ? 'Please enter gestational age at delivery in weeks.'
      : null) ??
    (parseNumber(riskFactors.birthWeightGrams) === null
      ? 'Please enter birth weight in grams.'
      : null) ??
    requireYesNo(
      riskFactors.abnormalConditionNicu,
      'Please answer whether there was a NICU abnormal condition.',
    ) ??
    (parseNumber(riskFactors.apgar5Min) === null
      ? 'Please enter the 5-minute Apgar score.'
      : null) ??
    (parseNumber(riskFactors.apgar10Min) === null
      ? 'Please enter the 10-minute Apgar score.'
      : null)
  )
}

export function toPrenatalCvdRequest(
  riskFactors: PrenatalRiskFactors,
  profileAge: string,
): PrenatalCvdRequest {
  const bmi = formatCalculatedBmi(calculatePrepregnancyBmi(riskFactors)) ?? ''

  return {
    pregnancyMode: 'prenatal',
    age: getResolvedAge(riskFactors, profileAge),
    prepregnancyBmi: bmi,
    chronicHypertension: riskFactors.chronicHypertension as boolean,
    diabetes: riskFactors.diabetes as boolean,
    priorPretermOrStillbirth: riskFactors.priorPretermOrStillbirth as boolean,
    liveBirthsCount: riskFactors.liveBirthsCount.trim(),
    smokedPregnancy: riskFactors.smokedPregnancy as boolean,
    multipleGestation: riskFactors.multipleGestation as boolean,
  }
}

export function toPostnatalFollowupRequest(
  riskFactors: PostnatalRiskFactors,
  profileAge: string,
): PostnatalFollowupRequest {
  const bmi = formatCalculatedBmi(calculatePrepregnancyBmi(riskFactors)) ?? ''

  return {
    mother_age: getResolvedAge(riskFactors, profileAge),
    mother_bmi: bmi,
    prepregnancy_hypertension: riskFactors.chronicHypertension as boolean,
    prepregnancy_diabetes: riskFactors.diabetes as boolean,
    prior_live_births: riskFactors.priorLiveBirths.trim(),
    prior_dead_births: riskFactors.priorDeadBirths.trim(),
    previous_preterm_birth: riskFactors.previousPretermBirth as boolean,
    previous_cesarean: riskFactors.previousCesarean as boolean,
    previous_cesarean_count: riskFactors.previousCesareanCount.trim(),
    gestational_hypertension: riskFactors.gestationalHypertension as boolean,
    eclampsia: riskFactors.eclampsia as boolean,
    gestational_diabetes: riskFactors.gestationalDiabetes as boolean,
    maternal_transfusion: riskFactors.maternalTransfusion as boolean,
    ruptured_uterus: riskFactors.rupturedUterus as boolean,
    unplanned_hysterectomy: riskFactors.unplannedHysterectomy as boolean,
    maternal_icu: riskFactors.maternalIcu as boolean,
    obstetric_estimate_gestation_weeks: riskFactors.gestationalAgeWeeks.trim(),
    birth_weight_grams: riskFactors.birthWeightGrams.trim(),
    abnormal_condition_nicu: riskFactors.abnormalConditionNicu as boolean,
    apgar_5_min: riskFactors.apgar5Min.trim(),
    apgar_10_min: riskFactors.apgar10Min.trim(),
  }
}
