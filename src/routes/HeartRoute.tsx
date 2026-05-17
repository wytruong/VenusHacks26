import LandingCta from '../features/landing/LandingCta'

type HeartRouteProps = {
  showLandingCta: boolean
  onOpenEcg: () => void
  onOpenDoctorNote: () => void
}

export function HeartRoute({ showLandingCta, onOpenEcg, onOpenDoctorNote }: HeartRouteProps) {
  return (
    <LandingCta
      show={showLandingCta}
      onOpenEcg={onOpenEcg}
      onOpenDoctorNote={onOpenDoctorNote}
    />
  )
}
