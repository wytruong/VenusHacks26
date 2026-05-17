import { type ChangeEvent, type Dispatch, type RefObject, type SetStateAction } from 'react'
import OnboardingFlow from '../features/onboarding/OnboardingFlow'
import type { RiskFactors } from '../features/risk-profile/riskProfile.types'

type OnboardingSubStep = 'question' | 'pregnancyStage' | 'profileDetails' | 'riskFactors'

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
  profileAvatarInputRef: RefObject<HTMLInputElement | null>
  profileAvatarUrl: string | null
  onProfileAvatarChange: (event: ChangeEvent<HTMLInputElement>) => void
  profileDisplayName: string
  setProfileDisplayName: (value: string) => void
  profileAge: string
  setProfileAge: (value: string) => void
  profileWeeksPregnant: string
  setProfileWeeksPregnant: (value: string) => void
  profileWeeksPostpartum: string
  setProfileWeeksPostpartum: (value: string) => void
  profileMedications: string
  setProfileMedications: (value: string) => void
  profileAllergies: string
  setProfileAllergies: (value: string) => void
  profileLatestVisit: string
  setProfileLatestVisit: (value: string) => void
}

export function OnboardingRoute(props: OnboardingRouteProps) {
  return <OnboardingFlow {...props} show />
}
