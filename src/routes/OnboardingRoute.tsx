import { type Dispatch, type SetStateAction } from 'react'
import OnboardingFlow from '../features/onboarding/OnboardingFlow'
import type { RiskFactors } from '../features/risk-profile/riskProfile.types'

type OnboardingSubStep = 'question' | 'pregnancyStage' | 'riskFactors'

type OnboardingRouteProps = {
  bg: string
  dismissing: boolean
  subStep: OnboardingSubStep
  pregnancyMode: 'prenatal' | 'postpartum' | null
  riskFactors: RiskFactors
  setSubStep: (step: OnboardingSubStep) => void
  setPregnancyMode: (mode: 'prenatal' | 'postpartum') => void
  setDismiss: (value: boolean) => void
  setRiskFactors: Dispatch<SetStateAction<RiskFactors>>
  createEmptyRiskFactors: (mode: 'prenatal' | 'postpartum') => RiskFactors
  onSubmitRisk: () => void
  riskSubmitMessage: string | null
}

export function OnboardingRoute(props: OnboardingRouteProps) {
  return <OnboardingFlow {...props} show />
}
