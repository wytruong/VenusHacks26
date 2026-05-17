import { OnboardingRoute } from './OnboardingRoute'

type RiskProfileRouteProps = Omit<Parameters<typeof OnboardingRoute>[0], 'subStep'>

export function RiskProfileRoute(props: RiskProfileRouteProps) {
  return <OnboardingRoute {...props} subStep="riskFactors" />
}
