import ParticleLayer from '../features/landing/ParticleLayer'
import type { Particle } from '../features/landing/particles'

type LandingRouteProps = {
  showParticles: boolean
  particles: Particle[]
  cx: number
  cy: number
}

export function LandingRoute({ showParticles, particles, cx, cy }: LandingRouteProps) {
  return <ParticleLayer show={showParticles} particles={particles} cx={cx} cy={cy} />
}
