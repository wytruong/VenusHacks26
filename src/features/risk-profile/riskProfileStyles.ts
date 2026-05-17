import type { PregnancyRiskTier } from './riskProfile.types'

export function normalizeRiskTier(tier: string | undefined): PregnancyRiskTier {
  const normalized = tier?.toLowerCase()
  if (normalized === 'low' || normalized === 'medium' || normalized === 'high') {
    return normalized
  }
  if (normalized === 'moderate') return 'medium'
  return 'medium'
}

export function riskTierBadgeClass(tier: string | undefined): string {
  switch (normalizeRiskTier(tier)) {
    case 'low':
      return 'border-emerald-400/45 bg-emerald-500/[0.14] text-emerald-100'
    case 'medium':
      return 'border-amber-400/45 bg-amber-500/[0.14] text-amber-100'
    case 'high':
      return 'border-red-400/40 bg-red-500/[0.16] text-[#e8a0a0]'
  }
}
