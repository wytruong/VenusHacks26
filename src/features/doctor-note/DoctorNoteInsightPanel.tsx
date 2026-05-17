import type { FormEvent } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { easeSoftOut } from '../../shared/animation'
import { dmSans } from '../../shared/styles'
import type { DoctorNoteOcrResult } from './doctorNote.types'

type DoctorNoteInsightPanelProps = {
  result: DoctorNoteOcrResult | null
  draft: string
  response: string | null
  error: string | null
  isLoading: boolean
  setDraft: (v: string) => void
  onSubmitFollowUp: (e?: FormEvent<HTMLFormElement>) => void
}

export default function DoctorNoteInsightPanel({ result, draft, response, error, isLoading, setDraft, onSubmitFollowUp }: DoctorNoteInsightPanelProps) {
  if (!result) return null

  return (
    <motion.div
      key="doctor-note-ocr-insight"
      className="pointer-events-none fixed top-1/2 z-[45] max-h-[88vh] -translate-y-1/2 overflow-y-auto"
      style={{ right: 24, width: 'max(280px, min(380px, calc(100vw - 48px)))' }}
      initial={{ opacity: 0, x: 14 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 10 }}
      transition={{ duration: 0.65, ease: easeSoftOut }}
    >
      <div className="pointer-events-auto" style={{ padding: '24px 28px', borderRadius: 16, backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)', backgroundColor: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.2)', fontFamily: dmSans, textAlign: 'left' }}>
        <div className="flex flex-wrap items-center gap-2">
          <span style={{ color: '#FDF0F0', fontSize: 18, fontWeight: 700 }}>{result.condition}</span>
          <span className="rounded-full border border-red-400/40 bg-red-500/[0.16] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-[#e8a0a0]" style={{ fontFamily: dmSans }}>
            {result.risk}
          </span>
        </div>
        <p className="mt-1 font-bold leading-snug text-[#FDF0F0]" style={{ fontFamily: dmSans, fontSize: 18 }}>
          {result.region}
        </p>
        <p className="mt-3 font-normal text-[#E8D5D5]" style={{ fontFamily: dmSans, fontSize: 13, lineHeight: 1.6 }}>
          {result.description}
        </p>

        <div className="mt-4" style={{ padding: '12px 14px', borderRadius: 12, backgroundColor: 'rgba(232, 128, 128, 0.14)', border: '1px solid rgba(232, 128, 128, 0.42)' }}>
          <div className="font-semibold uppercase tracking-[0.06em] text-[#E88080]" style={{ fontFamily: dmSans, fontSize: 10 }}>
            What to say to your doctor:
          </div>
          <p className="mt-2 font-normal leading-snug text-[#FDF0F0]" style={{ fontFamily: dmSans, fontSize: 12, lineHeight: 1.5 }}>
            {result.doctorScript}
          </p>
        </div>

        <div style={{ marginTop: 16, color: '#F4C2C2', fontSize: 13, fontWeight: 600, letterSpacing: '0.02em' }}>Questions for your doctor</div>
        <ul style={{ margin: '8px 0 0', paddingLeft: 18, color: '#D4B8B8', fontSize: 12, fontWeight: 400, lineHeight: 1.5 }}>
          {result.questions.map((q) => (
            <li key={q} style={{ marginBottom: 6 }}>
              {q}
            </li>
          ))}
        </ul>

        <div className="mt-4 border-t border-white/10 pt-4">
          <div className="mb-2 font-normal text-[#9B7B7B]" style={{ fontFamily: dmSans, fontSize: 11 }}>
            Ask a follow-up question
          </div>

          <AnimatePresence>
            {isLoading || response || error ? (
              <motion.div key="doctor-note-followup-response" className="mb-3" initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 4 }} transition={{ duration: 0.35, ease: easeSoftOut }} style={{ padding: '10px 12px', borderRadius: 12, backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)', backgroundColor: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.2)' }}>
                <p className="m-0 font-normal leading-snug text-[#D4B8B8]" style={{ fontFamily: dmSans, fontSize: 11 }}>
                  {isLoading ? 'Thinking…' : error || response}
                </p>
              </motion.div>
            ) : null}
          </AnimatePresence>

          <form className="flex w-full min-w-0 items-stretch gap-2" onSubmit={onSubmitFollowUp}>
            <input
              type="text"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="e.g. What does this mean for my baby?"
              autoComplete="off"
              disabled={isLoading}
              className="min-w-0 flex-1 border-none outline-none placeholder:text-[#9B7B7B]/55"
              style={{ padding: '8px 14px', borderRadius: 20, backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)', backgroundColor: 'rgba(255,255,255,0.08)', border: '1px solid #F4C2C2', color: '#FDF0F0', fontFamily: dmSans, fontSize: 12 }}
            />
            <button type="submit" disabled={isLoading || !draft.trim()} className="flex shrink-0 cursor-pointer items-center justify-center rounded-full border border-white/20 bg-white/[0.08] px-3.5 py-2 shadow-[0_4px_24px_rgba(255,255,255,0.06)] backdrop-blur-[12px] transition-[background-color] duration-300 hover:bg-white/[0.12] disabled:cursor-not-allowed disabled:opacity-45" aria-label="Send follow-up question">
              <span className="leading-none" style={{ color: '#F4C2C2', fontSize: 15, fontFamily: dmSans }}>→</span>
            </button>
          </form>
        </div>
      </div>
    </motion.div>
  )
}
