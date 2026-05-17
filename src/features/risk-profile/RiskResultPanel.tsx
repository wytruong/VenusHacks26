import { motion } from 'framer-motion'
import { easeSoftOut } from '../../shared/animation'
import { dmSans } from '../../shared/styles'
import { normalizeRiskTier, riskTierBadgeClass } from './riskProfileStyles'
import type { PregnancyRiskResult } from './riskProfile.types'
import type { PostnatalFollowupResponse, PrenatalCvdResponse } from '../../types/screening'

type RiskResultPanelProps = {
  result: PregnancyRiskResult | null
}

type RiskResultDisplay = {
  title: string
  tier: string
  mode: string
  probability?: number
  factors: string[]
  priority: string
  safetyCopy?: string
  context: string[]
}

function isPrenatalCvdResponse(result: PregnancyRiskResult): result is PrenatalCvdResponse {
  return 'risk_tier' in result
}

function collectPostnatalFactors(result: PostnatalFollowupResponse): string[] {
  const signals = [
    ['Hypertension follow-up', result.hypertension_followup_signal],
    ['Diabetes follow-up', result.diabetes_followup_signal],
    ['Maternal cardiovascular/metabolic follow-up', result.maternal_cv_metabolic_followup_signal],
    ['Obstetric/neonatal context', result.obstetric_neonatal_context_signal],
    ['Severe maternal morbidity follow-up', result.severe_maternal_morbidity_followup_signal],
  ] as const

  return signals.flatMap(([label, signal]) => {
    if (!signal) return []
    const tier = normalizeRiskTier(signal.tier)
    const factors = signal.main_factors ?? []
    if (!signal.present && tier === 'low' && factors.length === 0) return []
    if (factors.length > 0) return factors.map((factor) => `${label}: ${factor}`)
    return [`${label}: ${signal.tier ?? 'present'}`]
  })
}

function toDisplay(result: PregnancyRiskResult): RiskResultDisplay {
  if (isPrenatalCvdResponse(result)) {
    return {
      title: 'Your prenatal risk profile',
      tier: result.risk_tier,
      mode: result.model_mode,
      probability:
        result.prenatal_cvd_followup_proxy_probability ??
        result.current_composite_signal?.probability,
      factors: result.main_contributing_factors,
      priority: result.recommended_followup_priority,
      safetyCopy: result.disclaimer ?? result.safety_note,
      context: [],
    }
  }

  return {
    title: 'Your postnatal follow-up profile',
    tier: result.overall_followup_priority,
    mode: result.model_mode,
    factors: collectPostnatalFactors(result),
    priority: result.overall_followup_priority,
    safetyCopy: result.safety_note,
    context: [...(result.data_quality_warnings ?? []), ...(result.missing_inputs ?? [])],
  }
}

export default function RiskResultPanel({ result }: RiskResultPanelProps) {
  if (!result) return null

  const display = toDisplay(result)

  return (
    <motion.div
      key="pregnancy-risk-insight"
      className="pointer-events-none fixed top-1/2 z-[45] max-h-[88vh] -translate-y-1/2 overflow-y-auto"
      style={{ right: 24, width: 'max(280px, min(380px, calc(100vw - 48px)))' }}
      initial={{ opacity: 0, x: 14 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 10 }}
      transition={{ duration: 0.65, ease: easeSoftOut }}
    >
      <div className="pointer-events-auto" style={{ padding: '24px 28px', borderRadius: 16, backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)', backgroundColor: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.2)', fontFamily: dmSans, textAlign: 'left' }}>
        <div className="flex flex-wrap items-center gap-2">
          <span style={{ color: '#FDF0F0', fontSize: 18, fontWeight: 700 }}>{display.title}</span>
          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em] ${riskTierBadgeClass(display.tier)}`} style={{ fontFamily: dmSans }}>
            {normalizeRiskTier(display.tier).toUpperCase()}
          </span>
        </div>
        <p className="mt-1 font-normal text-[#E8D5D5]" style={{ fontFamily: dmSans, fontSize: 13, lineHeight: 1.6 }}>
          Assessment mode: {display.mode}
        </p>
        {typeof display.probability === 'number' ? (
          <p className="mt-2 font-normal text-[#E8D5D5]" style={{ fontFamily: dmSans, fontSize: 13, lineHeight: 1.6 }}>
            Follow-up relevance index: {Math.round(display.probability * 100)}%
          </p>
        ) : null}

        <div style={{ marginTop: 16, color: '#F4C2C2', fontSize: 13, fontWeight: 600, letterSpacing: '0.02em' }}>
          Main contributing factors
        </div>
        <ul style={{ margin: '8px 0 0', paddingLeft: 18, color: '#D4B8B8', fontSize: 12, fontWeight: 400, lineHeight: 1.5 }}>
          {display.factors.length ? display.factors.map((factor) => (
            <li key={factor} style={{ marginBottom: 6 }}>
              {factor}
            </li>
          )) : <li>No major contributing factors were highlighted.</li>}
        </ul>

        <div className="mt-4" style={{ padding: '12px 14px', borderRadius: 12, backgroundColor: 'rgba(232, 128, 128, 0.14)', border: '1px solid rgba(232, 128, 128, 0.42)' }}>
          <div className="font-semibold uppercase tracking-[0.06em] text-[#E88080]" style={{ fontFamily: dmSans, fontSize: 10 }}>
            Recommended next step
          </div>
          <p className="mt-2 font-normal leading-snug text-[#FDF0F0]" style={{ fontFamily: dmSans, fontSize: 12, lineHeight: 1.5 }}>
            {display.priority}
          </p>
        </div>

        {display.context.length ? (
          <div className="mt-3" style={{ color: '#BFA2A2', fontSize: 11, lineHeight: 1.5 }}>
            <span className="font-semibold text-[#D4B8B8]">Model context: </span>
            {display.context.join('; ')}
          </div>
        ) : null}

        {display.safetyCopy ? (
          <p className="mt-3 font-normal text-[#BFA2A2]" style={{ fontFamily: dmSans, fontSize: 11, lineHeight: 1.5 }}>
            {display.safetyCopy}
          </p>
        ) : null}
      </div>
    </motion.div>
  )
}
