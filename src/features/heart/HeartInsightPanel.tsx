import { motion } from 'framer-motion'
import type { MeshSelectPayload } from '../../components/HeartModel'
import { easeSoftOut } from '../../shared/animation'

type HeartInsightPanelProps = {
  meshInfo: MeshSelectPayload | null
}

export default function HeartInsightPanel({ meshInfo }: HeartInsightPanelProps) {
  if (!meshInfo) return null

  return (
    <motion.div
      key={`${meshInfo.label}-${meshInfo.description}-${meshInfo.doctorQuestions[0]}`}
      className="pointer-events-none fixed top-1/2 z-[45] max-h-[88vh] -translate-y-1/2 overflow-y-auto"
      style={{ right: 24, width: 'max(280px, min(380px, calc(100vw - 48px)))' }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.45, ease: easeSoftOut }}
    >
      <div className="pointer-events-auto" style={{ padding: '24px 28px', borderRadius: 16, backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)', backgroundColor: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.2)', fontFamily: 'DM Sans, sans-serif', textAlign: 'left' }}>
        <div style={{ color: '#FDF0F0', fontSize: 18, fontWeight: 700 }}>{meshInfo.label}</div>
        <div style={{ marginTop: 8, color: '#E8D5D5', fontSize: 13, fontWeight: 400, lineHeight: 1.6 }}>{meshInfo.description}</div>
        <div style={{ marginTop: 16, color: '#F4C2C2', fontSize: 13, fontWeight: 600, letterSpacing: '0.02em' }}>Questions for your doctor</div>
        <ul style={{ margin: '8px 0 0', paddingLeft: 18, color: '#D4B8B8', fontSize: 12, fontWeight: 400, lineHeight: 1.5 }}>
          {meshInfo.doctorQuestions.map((q) => (
            <li key={q} style={{ marginBottom: 6 }}>
              {q}
            </li>
          ))}
        </ul>
      </div>
    </motion.div>
  )
}
