import { motion } from 'framer-motion'
import { PARTICLE_DURATION_S, easeCinematic } from '../../shared/animation'

type Particle = {
  id: number
  x: number
  y: number
  size: number
  color: string
}

type ParticleLayerProps = {
  show: boolean
  particles: Particle[]
  cx: number
  cy: number
}

export default function ParticleLayer({ show, particles, cx, cy }: ParticleLayerProps) {
  if (!show) return null

  return (
    <div className="pointer-events-none fixed inset-0 z-20 overflow-hidden" aria-hidden>
      {particles.map((p) => (
        <motion.div
          key={p.id}
          className="absolute rounded-full"
          style={{ width: p.size, height: p.size, backgroundColor: p.color, boxShadow: `0 0 ${p.size}px ${p.color}33` }}
          initial={{ left: p.x, top: p.y, marginLeft: -p.size / 2, marginTop: -p.size / 2, opacity: 1 }}
          animate={{ left: cx, top: cy, opacity: 0 }}
          transition={{ duration: PARTICLE_DURATION_S, ease: easeCinematic }}
        />
      ))}
    </div>
  )
}
