import { motion } from 'framer-motion'
import { easeSoftOut } from '../../shared/animation'
import { glassPillButton } from '../../shared/styles'

type LandingCtaProps = {
  show: boolean
  onOpenEcg: () => void
  onOpenDoctorNote: () => void
}

export default function LandingCta({ show, onOpenEcg, onOpenDoctorNote }: LandingCtaProps) {
  return (
    <>
      <motion.div
        className="pointer-events-none fixed inset-x-0 bottom-0 z-30 flex justify-center pb-28 pt-24 md:pb-32 md:pt-28"
        initial={{ opacity: 0 }}
        animate={{ opacity: show ? 1 : 0 }}
        transition={{ duration: 1.15, ease: easeSoftOut }}
      >
        <div className="flex max-w-lg flex-col items-center gap-8 px-6 text-center">
          <div className="flex flex-col items-center gap-2">
            <p className="text-[0.625rem] font-normal leading-snug tracking-[0.06em] text-[#9B7B7B] md:text-[0.6875rem] md:tracking-[0.08em]">
              Cardiac health, explained for you.
            </p>
            <p className="max-w-[22rem] text-[0.9375rem] font-normal leading-relaxed tracking-[0.06em] text-[#FDF0F0] md:max-w-none md:text-base md:tracking-[0.08em]">
              Let&apos;s help you understand your heart.
            </p>
          </div>
          <div className="pointer-events-auto flex flex-row flex-wrap items-center justify-center gap-4">
            <button type="button" className={glassPillButton} onClick={onOpenEcg}>
              I have an Apple Watch
            </button>
            <button type="button" className={glassPillButton} onClick={onOpenDoctorNote}>
              I have a doctor&apos;s note
            </button>
          </div>
        </div>
      </motion.div>

      <motion.p
        className="pointer-events-none fixed inset-x-0 bottom-6 z-30 px-6 text-center text-[0.5625rem] font-normal leading-snug tracking-[0.06em] text-[#9B7B7B] md:bottom-8 md:text-[0.625rem]"
        initial={{ opacity: 0 }}
        animate={{ opacity: show ? 1 : 0 }}
        transition={{ duration: 1.15, ease: easeSoftOut }}
      >
        Your data never leaves your device.
      </motion.p>
    </>
  )
}
