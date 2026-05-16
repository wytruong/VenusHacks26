import { useEffect, useState, type CSSProperties } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import HeartModel, { type MeshSelectPayload } from './components/HeartModel'

const BG = '#1a0a0a'
const PARTICLE_DURATION_S = 2.5
const HEART_FADE_DURATION_S = 1
const CTA_DELAY_AFTER_HEART_S = 1
const ONBOARDING_EXIT_DURATION_S = 0.5

const easeCinematic = [0.33, 0.02, 0.25, 1] as const
const easeSoftOut = [0.22, 1, 0.36, 1] as const

const glassPillButton =
  'rounded-full border border-white/20 bg-white/[0.08] px-6 py-3 text-sm font-normal text-[#FDF0F0] shadow-[0_4px_24px_rgba(255,255,255,0.06)] backdrop-blur-[12px] transition-[background-color,box-shadow] duration-700 ease-out hover:bg-white/[0.15] hover:shadow-[0_4px_24px_rgba(255,255,255,0.06),0_0_32px_rgba(255,255,255,0.14)] md:text-[0.9375rem]'

const editProfilePillButton =
  'rounded-full border border-[#F4C2C2] bg-white/[0.08] px-3 py-1.5 text-[11px] font-normal text-[#9B7B7B] shadow-[0_4px_24px_rgba(255,255,255,0.06)] backdrop-blur-[12px] transition-[background-color,box-shadow] duration-300 hover:bg-white/[0.12]'

type Particle = {
  id: number
  x: number
  y: number
  size: number
  color: string
}

export type PregnancyData = {
  age: string
  restingHeartRate: string
  systolicBp: string
  gestationalDiabetes: boolean | null
}

const pregnancyDataInitial: PregnancyData = {
  age: '',
  restingHeartRate: '',
  systolicBp: '',
  gestationalDiabetes: null,
}

const dmSans = '"DM Sans", system-ui, sans-serif'

const glassFieldCardStyle: CSSProperties = {
  backdropFilter: 'blur(12px)',
  WebkitBackdropFilter: 'blur(12px)',
  backgroundColor: 'rgba(255,255,255,0.08)',
  border: '1px solid #F4C2C2',
  borderRadius: 12,
}

const glassNumberInputStyle: CSSProperties = {
  marginTop: 8,
  width: '100%',
  border: 'none',
  outline: 'none',
  background: 'transparent',
  color: '#FDF0F0',
  fontFamily: dmSans,
  fontSize: 15,
}

function generateParticles(w: number, h: number): Particle[] {
  const colors = ['#ffffff', '#ffffff', '#FCE7EB', '#FFD6DC', '#FFB3B3']
  return Array.from({ length: 200 }, (_, i) => ({
    id: i,
    x: Math.random() * w,
    y: Math.random() * h,
    size: 2 + Math.random() * 2,
    color: colors[Math.floor(Math.random() * colors.length)] ?? '#ffffff',
  }))
}

export default function App() {
  const [{ dims, particles }] = useState(() => {
    const w = typeof window !== 'undefined' ? window.innerWidth : 1920
    const h = typeof window !== 'undefined' ? window.innerHeight : 1080
    return {
      dims: { w, h },
      particles: generateParticles(w, h),
    }
  })

  const [showParticlesLayer, setShowParticlesLayer] = useState(true)
  const [showPregnancyOnboarding, setShowPregnancyOnboarding] =
    useState(false)
  const [onboardingSubStep, setOnboardingSubStep] = useState<
    'question' | 'pregnancyDetails'
  >('question')
  const [dismissPregnancyOnboarding, setDismissPregnancyOnboarding] =
    useState(false)
  const [heartReveal, setHeartReveal] = useState(false)
  const [heartInteractive, setHeartInteractive] = useState(false)
  const [showCta, setShowCta] = useState(false)
  const [meshInfo, setMeshInfo] = useState<MeshSelectPayload | null>(null)
  const [pregnancyData, setPregnancyData] = useState<PregnancyData>(
    pregnancyDataInitial,
  )

  useEffect(() => {
    const particleEndMs = PARTICLE_DURATION_S * 1000
    const tParticlesDone = window.setTimeout(() => {
      setShowParticlesLayer(false)
      setOnboardingSubStep('question')
      setShowPregnancyOnboarding(true)
    }, particleEndMs)

    return () => {
      window.clearTimeout(tParticlesDone)
    }
  }, [])

  useEffect(() => {
    if (!dismissPregnancyOnboarding) return
    const t = window.setTimeout(() => {
      setHeartReveal(true)
      setShowPregnancyOnboarding(false)
      setOnboardingSubStep('question')
      setDismissPregnancyOnboarding(false)
    }, ONBOARDING_EXIT_DURATION_S * 1000)
    return () => window.clearTimeout(t)
  }, [dismissPregnancyOnboarding])

  useEffect(() => {
    if (!heartReveal) return
    const ctaMs =
      (HEART_FADE_DURATION_S + CTA_DELAY_AFTER_HEART_S) * 1000
    const tCta = window.setTimeout(() => setShowCta(true), ctaMs)
    return () => window.clearTimeout(tCta)
  }, [heartReveal])

  useEffect(() => {
    if (!heartReveal) return
    const t = window.setTimeout(
      () => setHeartInteractive(true),
      HEART_FADE_DURATION_S * 1000,
    )
    return () => window.clearTimeout(t)
  }, [heartReveal])

  const cx = dims.w / 2
  const cy = dims.h / 2

  const resetToPregnancyOnboarding = () => {
    setHeartReveal(false)
    setHeartInteractive(false)
    setShowCta(false)
    setMeshInfo(null)
    setDismissPregnancyOnboarding(false)
    setPregnancyData({ ...pregnancyDataInitial })
    setOnboardingSubStep('question')
    setShowPregnancyOnboarding(true)
  }

  const showEditProfileButton =
    heartReveal && !showPregnancyOnboarding

  return (
    <div
      className="relative min-h-screen overflow-hidden"
      style={{ backgroundColor: BG }}
    >
      <div className="pointer-events-none fixed left-6 top-6 z-40 select-none md:left-8 md:top-8">
        <span className="text-sm font-light tracking-[0.14em] text-[#F4C2C2]">
          heartwise
        </span>
      </div>

      {showEditProfileButton ? (
        <button
          type="button"
          className={`${editProfilePillButton} fixed right-6 top-6 z-[41] md:right-8`}
          style={{ fontFamily: dmSans }}
          onClick={resetToPregnancyOnboarding}
        >
          Edit profile
        </button>
      ) : null}

      <motion.div
        className="fixed inset-0 z-0"
        initial={{ opacity: 0 }}
        animate={{ opacity: heartReveal ? 1 : 0 }}
        transition={{
          duration: HEART_FADE_DURATION_S,
          ease: easeSoftOut,
        }}
        style={{ pointerEvents: heartInteractive ? 'auto' : 'none' }}
      >
        <HeartModel onSelect={setMeshInfo} />
      </motion.div>

      <AnimatePresence>
        {showPregnancyOnboarding ? (
          <motion.div
            key="pregnancy-onboarding"
            className="fixed inset-0 z-[38] flex flex-col items-center justify-center overflow-y-auto px-6 py-12"
            style={{ backgroundColor: BG }}
            initial={{ opacity: 0 }}
            animate={{ opacity: dismissPregnancyOnboarding ? 0 : 1 }}
            transition={{
              duration: dismissPregnancyOnboarding
                ? ONBOARDING_EXIT_DURATION_S
                : 0.55,
              ease: easeSoftOut,
            }}
          >
            {onboardingSubStep === 'question' ? (
              <>
                <p
                  className="mb-10 max-w-xl text-center font-normal leading-snug text-[#FDF0F0]"
                  style={{ fontFamily: dmSans, fontSize: 18 }}
                >
                  Are you currently pregnant or postpartum?
                </p>
                <div className="flex flex-row flex-wrap items-center justify-center gap-4">
                  <button
                    type="button"
                    className={glassPillButton}
                    onClick={() => {
                      setPregnancyData({ ...pregnancyDataInitial })
                      setOnboardingSubStep('pregnancyDetails')
                    }}
                  >
                    Yes, I am
                  </button>
                  <button
                    type="button"
                    className={glassPillButton}
                    onClick={() => {
                      setDismissPregnancyOnboarding(true)
                    }}
                  >
                    No, continue
                  </button>
                </div>
                <button
                  type="button"
                  className="mt-8 cursor-pointer border-none bg-transparent p-0 text-[0.6875rem] font-normal text-[#9B7B7B] underline-offset-2 hover:underline"
                  style={{ fontFamily: dmSans }}
                  onClick={() => {
                    setDismissPregnancyOnboarding(true)
                  }}
                >
                  Prefer not to say
                </button>
              </>
            ) : (
              <motion.div
                key="pregnancy-details"
                className="flex w-full max-w-md flex-col items-center"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.55, ease: easeSoftOut }}
              >
                <motion.h2
                  className="mb-8 text-center font-normal leading-snug text-[#FDF0F0]"
                  style={{ fontFamily: dmSans, fontSize: 16 }}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.5, ease: easeSoftOut, delay: 0.06 }}
                >
                  Let&apos;s understand your heart better.
                </motion.h2>

                <div className="flex w-full flex-col gap-4">
                  <div className="px-4 py-3" style={glassFieldCardStyle}>
                    <label
                      className="block text-sm font-normal text-[#FDF0F0]"
                      style={{ fontFamily: dmSans }}
                      htmlFor="pregnancy-age"
                    >
                      How old are you?
                    </label>
                    <input
                      id="pregnancy-age"
                      type="number"
                      inputMode="numeric"
                      min={0}
                      className="tabular-nums"
                      style={glassNumberInputStyle}
                      value={pregnancyData.age}
                      onChange={(e) =>
                        setPregnancyData((d) => ({
                          ...d,
                          age: e.target.value,
                        }))
                      }
                    />
                  </div>

                  <div className="px-4 py-3" style={glassFieldCardStyle}>
                    <label
                      className="block text-sm font-normal text-[#FDF0F0]"
                      style={{ fontFamily: dmSans }}
                      htmlFor="pregnancy-hr"
                    >
                      What&apos;s your resting heart rate?
                    </label>
                    <input
                      id="pregnancy-hr"
                      type="number"
                      inputMode="numeric"
                      min={0}
                      className="tabular-nums"
                      style={glassNumberInputStyle}
                      value={pregnancyData.restingHeartRate}
                      onChange={(e) =>
                        setPregnancyData((d) => ({
                          ...d,
                          restingHeartRate: e.target.value,
                        }))
                      }
                    />
                    <p
                      className="mt-2 text-[11px] font-normal leading-snug text-[#9B7B7B]"
                      style={{ fontFamily: dmSans }}
                    >
                      Check your Apple Watch or wearable
                    </p>
                  </div>

                  <div className="px-4 py-3" style={glassFieldCardStyle}>
                    <label
                      className="block text-sm font-normal text-[#FDF0F0]"
                      style={{ fontFamily: dmSans }}
                      htmlFor="pregnancy-bp"
                    >
                      What&apos;s your systolic blood pressure?
                    </label>
                    <input
                      id="pregnancy-bp"
                      type="number"
                      inputMode="numeric"
                      min={0}
                      className="tabular-nums"
                      style={glassNumberInputStyle}
                      value={pregnancyData.systolicBp}
                      onChange={(e) =>
                        setPregnancyData((d) => ({
                          ...d,
                          systolicBp: e.target.value,
                        }))
                      }
                    />
                    <p
                      className="mt-2 text-[11px] font-normal leading-snug text-[#9B7B7B]"
                      style={{ fontFamily: dmSans }}
                    >
                      The top number, e.g. 120
                    </p>
                  </div>

                  <div className="px-4 py-3" style={glassFieldCardStyle}>
                    <span
                      className="block text-sm font-normal text-[#FDF0F0]"
                      style={{ fontFamily: dmSans }}
                    >
                      Do you have gestational diabetes?
                    </span>
                    <div className="mt-3 flex flex-row gap-3">
                      <button
                        type="button"
                        className={`rounded-full border border-[#F4C2C2] px-5 py-2 text-xs font-normal text-[#FDF0F0] shadow-[0_4px_24px_rgba(255,255,255,0.06)] backdrop-blur-[12px] transition-[background-color] duration-300 ${
                          pregnancyData.gestationalDiabetes === true
                            ? 'bg-white/[0.15]'
                            : 'bg-white/[0.08]'
                        }`}
                        style={{ fontFamily: dmSans }}
                        onClick={() =>
                          setPregnancyData((d) => ({
                            ...d,
                            gestationalDiabetes: true,
                          }))
                        }
                      >
                        Yes
                      </button>
                      <button
                        type="button"
                        className={`rounded-full border border-[#F4C2C2] px-5 py-2 text-xs font-normal text-[#FDF0F0] shadow-[0_4px_24px_rgba(255,255,255,0.06)] backdrop-blur-[12px] transition-[background-color] duration-300 ${
                          pregnancyData.gestationalDiabetes === false
                            ? 'bg-white/[0.15]'
                            : 'bg-white/[0.08]'
                        }`}
                        style={{ fontFamily: dmSans }}
                        onClick={() =>
                          setPregnancyData((d) => ({
                            ...d,
                            gestationalDiabetes: false,
                          }))
                        }
                      >
                        No
                      </button>
                    </div>
                  </div>
                </div>

                <button
                  type="button"
                  className={`${glassPillButton} mt-8`}
                  onClick={() => setDismissPregnancyOnboarding(true)}
                >
                  See my heart →
                </button>
                <button
                  type="button"
                  className="mt-6 cursor-pointer border-none bg-transparent p-0 text-[0.6875rem] font-normal text-[#9B7B7B] underline-offset-2 hover:underline"
                  style={{ fontFamily: dmSans }}
                  onClick={() => setDismissPregnancyOnboarding(true)}
                >
                  Skip for now.
                </button>
              </motion.div>
            )}
          </motion.div>
        ) : null}
      </AnimatePresence>

      <AnimatePresence>
        {meshInfo ? (
          <motion.div
            key={`${meshInfo.label}-${meshInfo.description}-${meshInfo.doctorQuestions[0]}`}
            className="pointer-events-none fixed top-1/2 z-[45] -translate-y-1/2"
            style={{ right: 32 }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.45, ease: easeSoftOut }}
          >
            <div
              style={{
                maxWidth: 280,
                padding: '20px 24px',
                borderRadius: 16,
                backdropFilter: 'blur(12px)',
                WebkitBackdropFilter: 'blur(12px)',
                backgroundColor: 'rgba(255,255,255,0.08)',
                border: '1px solid rgba(255,255,255,0.2)',
                fontFamily: '"DM Sans", system-ui, sans-serif',
                textAlign: 'left',
              }}
            >
              <div
                style={{
                  color: '#FDF0F0',
                  fontSize: 14,
                  fontWeight: 600,
                }}
              >
                {meshInfo.label}
              </div>
              <div
                style={{
                  marginTop: 6,
                  color: '#9B7B7B',
                  fontSize: 11,
                  fontWeight: 400,
                  lineHeight: 1.45,
                }}
              >
                {meshInfo.description}
              </div>
              <div
                style={{
                  marginTop: 12,
                  color: '#FDF0F0',
                  fontSize: 11,
                  fontWeight: 600,
                  letterSpacing: '0.02em',
                }}
              >
                Questions for your doctor
              </div>
              <ul
                style={{
                  margin: '6px 0 0',
                  paddingLeft: 18,
                  color: '#9B7B7B',
                  fontSize: 11,
                  fontWeight: 400,
                  lineHeight: 1.45,
                }}
              >
                {meshInfo.doctorQuestions.map((q) => (
                  <li key={q} style={{ marginBottom: 6 }}>
                    {q}
                  </li>
                ))}
              </ul>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      {showParticlesLayer ? (
        <div
          className="pointer-events-none fixed inset-0 z-20 overflow-hidden"
          aria-hidden
        >
          {particles.map((p) => (
            <motion.div
              key={p.id}
              className="absolute rounded-full"
              style={{
                width: p.size,
                height: p.size,
                backgroundColor: p.color,
                boxShadow: `0 0 ${p.size}px ${p.color}33`,
              }}
              initial={{
                left: p.x,
                top: p.y,
                marginLeft: -p.size / 2,
                marginTop: -p.size / 2,
                opacity: 1,
              }}
              animate={{
                left: cx,
                top: cy,
                opacity: 0,
              }}
              transition={{
                duration: PARTICLE_DURATION_S,
                ease: easeCinematic,
              }}
            />
          ))}
        </div>
      ) : null}

      <motion.div
        className="pointer-events-none fixed inset-x-0 bottom-0 z-30 flex justify-center pb-28 pt-24 md:pb-32 md:pt-28"
        initial={{ opacity: 0 }}
        animate={{ opacity: showCta ? 1 : 0 }}
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
            <button type="button" className={glassPillButton}>
              I have an Apple Watch
            </button>
            <button type="button" className={glassPillButton}>
              I have a doctor&apos;s note
            </button>
          </div>
        </div>
      </motion.div>

      <motion.p
        className="pointer-events-none fixed inset-x-0 bottom-6 z-30 px-6 text-center text-[0.5625rem] font-normal leading-snug tracking-[0.06em] text-[#9B7B7B] md:bottom-8 md:text-[0.625rem]"
        initial={{ opacity: 0 }}
        animate={{ opacity: showCta ? 1 : 0 }}
        transition={{ duration: 1.15, ease: easeSoftOut }}
      >
        Your data never leaves your device.
      </motion.p>
    </div>
  )
}
