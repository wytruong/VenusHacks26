export type Particle = {
  id: number
  x: number
  y: number
  size: number
  color: string
}

export function generateParticles(w: number, h: number): Particle[] {
  const colors = ['#ffffff', '#ffffff', '#FCE7EB', '#FFD6DC', '#FFB3B3']
  return Array.from({ length: 200 }, (_, i) => ({
    id: i,
    x: Math.random() * w,
    y: Math.random() * h,
    size: 2 + Math.random() * 2,
    color: colors[Math.floor(Math.random() * colors.length)] ?? '#ffffff',
  }))
}
