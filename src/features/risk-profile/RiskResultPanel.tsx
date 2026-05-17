import { motion } from 'framer-motion'
import { easeSoftOut } from '../../shared/animation'
import { dmSans } from '../../shared/styles'
import { riskTierBadgeClass } from './riskProfileStyles'
import type { PregnancyRiskResult } from './riskProfile.types'

type RiskResultPanelProps = {
  result: PregnancyRiskResult | null
}

export default function RiskResultPanel({ result }: RiskResultPanelProps) {
  if (!result) return null

  const probability =
    result.prenatal_cvd_followup_proxy_probability ??
    result.current_composite_signal?.probability

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
          <span style={{ color: '#FDF0F0', fontSize: 18, fontWeight: 700 }}>Your risk profile</span>
          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em] ${riskTierBadgeClass(result.risk_tier)}`} style={{ fontFamily: dmSans }}>
            {result.risk_tier.toUpperCase()}
          </span>
        </div>
        <p className="mt-1 font-normal text-[#E8D5D5]" style={{ fontFamily: dmSans, fontSize: 13, lineHeight: 1.6 }}>
          Assessment mode: {result.model_mode}
        </p>
        {typeof probability === 'number' ? (
          <p className="mt-2 font-normal text-[#E8D5D5]" style={{ fontFamily: dmSans, fontSize: 13, lineHeight: 1.6 }}>
            Follow-up relevance index: {Math.round(probability * 100)}%
          </p>
        ) : null}

        <div style={{ marginTop: 16, color: '#F4C2C2', fontSize: 13, fontWeight: 600, letterSpacing: '0.02em' }}>
          Main contributing factors
        </div>
        <ul style={{ margin: '8px 0 0', paddingLeft: 18, color: '#D4B8B8', fontSize: 12, fontWeight: 400, lineHeight: 1.5 }}>
          {result.main_contributing_factors.length ? result.main_contributing_factors.map((f) => (
            <li key={f} style={{ marginBottom: 6 }}>
              {f}
            </li>
          )) : <li>No major contributing factors were highlighted.</li>}
        </ul>

        <div className="mt-4" style={{ padding: '12px 14px', borderRadius: 12, backgroundColor: 'rgba(232, 128, 128, 0.14)', border: '1px solid rgba(232, 128, 128, 0.42)' }}>
          <div className="font-semibold uppercase tracking-[0.06em] text-[#E88080]" style={{ fontFamily: dmSans, fontSize: 10 }}>
            Recommended next step
          </div>
          <p className="mt-2 font-normal leading-snug text-[#FDF0F0]" style={{ fontFamily: dmSans, fontSize: 12, lineHeight: 1.5 }}>
            {result.recommended_followup_priority}
          </p>
        </div>

        {result.disclaimer || result.safety_note ? (
          <p className="mt-3 font-normal text-[#BFA2A2]" style={{ fontFamily: dmSans, fontSize: 11, lineHeight: 1.5 }}>
            {result.disclaimer ?? result.safety_note}
          </p>
        ) : null}
      </div>
    </motion.div>
  )
}
