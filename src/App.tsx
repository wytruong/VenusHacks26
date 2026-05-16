import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type CSSProperties,
} from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import HeartModel, {
  LEFT_VENTRICLE_GLOW_MESH_NAMES,
  type MeshSelectPayload,
} from './components/HeartModel'

const BG = '#1a0a0a'
const PARTICLE_DURATION_S = 2.5
const HEART_FADE_DURATION_S = 1
const CTA_DELAY_AFTER_HEART_S = 1
const ONBOARDING_EXIT_DURATION_S = 0.5
const DOCTOR_NOTE_READING_MS = 2500

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

const doctorNoteUploadZoneStyle: CSSProperties = {
  width: '100%',
  maxWidth: 400,
  height: 250,
  borderRadius: 16,
  border: '1px dashed #F4C2C2',
  backdropFilter: 'blur(12px)',
  WebkitBackdropFilter: 'blur(12px)',
  backgroundColor: 'rgba(255,255,255,0.05)',
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

export type DoctorNoteOcrResult = {
  condition: string
  region: string
  risk: string
  description: string
  doctorScript: string
  questions: readonly string[]
}

const MOCK_DOCTOR_NOTE_OCR: DoctorNoteOcrResult = {
  condition: 'Hypertension',
  region: 'Left Ventricle',
  risk: 'HIGH',
  description:
    'Your doctor noted high blood pressure. During pregnancy this puts extra strain on the left side of your heart which has to work harder to pump blood for both you and your baby.',
  doctorScript:
    'My blood pressure has been high. I want to discuss what this means for my heart health during my pregnancy and what warning signs I should watch for.',
  questions: [
    'What blood pressure range is safe during my pregnancy?',
    'Should I be monitoring my heart rate at home?',
    'Could this affect my baby?',
  ],
}

function ReadingNoteEllipsis() {
  const [phase, setPhase] = useState(0)
  useEffect(() => {
    const id = window.setInterval(() => setPhase((p) => (p + 1) % 4), 420)
    return () => window.clearInterval(id)
  }, [])
  return (
    <span className="inline-block min-w-[1.25em] text-left" aria-hidden>
      {'.'.repeat(phase)}
    </span>
  )
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
  const [showDoctorNoteUpload, setShowDoctorNoteUpload] = useState(false)
  const [doctorNotePreviewUrl, setDoctorNotePreviewUrl] = useState<
    string | null
  >(null)
  const doctorNoteFileInputRef = useRef<HTMLInputElement>(null)
  const readDoctorNoteTimerRef = useRef(0)

  const [doctorNoteOcrLoading, setDoctorNoteOcrLoading] = useState(false)
  const [doctorNoteOcrResult, setDoctorNoteOcrResult] =
    useState<DoctorNoteOcrResult | null>(null)

  const revokeDoctorNotePreview = useCallback(() => {
    setDoctorNotePreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    const input = doctorNoteFileInputRef.current
    if (input) input.value = ''
  }, [])

  useEffect(() => {
    return () => {
      if (doctorNotePreviewUrl) URL.revokeObjectURL(doctorNotePreviewUrl)
    }
  }, [doctorNotePreviewUrl])

  useEffect(() => {
    return () => {
      if (readDoctorNoteTimerRef.current) {
        window.clearTimeout(readDoctorNoteTimerRef.current)
      }
    }
  }, [])

  const onDoctorNoteFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file?.type.startsWith('image/')) return
    setDoctorNotePreviewUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return URL.createObjectURL(file)
    })
  }

  const skipDoctorNoteToHeart = () => {
    setShowDoctorNoteUpload(false)
    revokeDoctorNotePreview()
  }

  const handleReadDoctorNote = () => {
    setMeshInfo(null)
    setShowDoctorNoteUpload(false)
    setDoctorNoteOcrLoading(true)
    setDoctorNoteOcrResult(null)
    if (readDoctorNoteTimerRef.current) {
      window.clearTimeout(readDoctorNoteTimerRef.current)
    }
    readDoctorNoteTimerRef.current = window.setTimeout(() => {
      readDoctorNoteTimerRef.current = 0
      setDoctorNoteOcrLoading(false)
      setDoctorNoteOcrResult(MOCK_DOCTOR_NOTE_OCR)
    }, DOCTOR_NOTE_READING_MS)
  }

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
    setShowDoctorNoteUpload(false)
    revokeDoctorNotePreview()
    setDoctorNoteOcrLoading(false)
    setDoctorNoteOcrResult(null)
    if (readDoctorNoteTimerRef.current) {
      window.clearTimeout(readDoctorNoteTimerRef.current)
      readDoctorNoteTimerRef.current = 0
    }
  }

  const showEditProfileButton =
    heartReveal && !showPregnancyOnboarding

  const showLandingCta =
    showCta &&
    !showDoctorNoteUpload &&
    !doctorNoteOcrLoading &&
    doctorNoteOcrResult === null

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
        style={{
          pointerEvents:
            heartInteractive && !doctorNoteOcrLoading ? 'auto' : 'none',
        }}
      >
        <motion.div
          className="h-full w-full"
          animate={{
            opacity: doctorNoteOcrLoading ? [0.3, 0.36, 0.3] : 1,
          }}
          transition={{
            duration: doctorNoteOcrLoading ? 2.8 : 0.5,
            repeat: doctorNoteOcrLoading ? Infinity : 0,
            ease: 'easeInOut',
          }}
        >
          <HeartModel
            onSelect={setMeshInfo}
            forcedGlowMeshNames={
              doctorNoteOcrResult ? LEFT_VENTRICLE_GLOW_MESH_NAMES : null
            }
          />
        </motion.div>
      </motion.div>

      <AnimatePresence>
        {doctorNoteOcrLoading ? (
          <motion.div
            key="reading-note"
            className="pointer-events-none fixed inset-x-0 bottom-[20%] z-[44] flex justify-center px-6 md:bottom-[24%]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4, ease: easeSoftOut }}
          >
            <p
              className="flex items-baseline justify-center gap-0 font-normal tracking-[0.02em] text-[#9B7B7B]"
              style={{ fontFamily: dmSans, fontSize: 12 }}
            >
              <span>Reading your note</span>
              <ReadingNoteEllipsis />
            </p>
          </motion.div>
        ) : null}
      </AnimatePresence>

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
        {showDoctorNoteUpload ? (
          <motion.div
            key="doctor-note-upload"
            className="fixed inset-0 z-[42] flex flex-col items-center justify-center overflow-y-auto px-6 py-16"
            style={{ backgroundColor: '#1A0A0A' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.45, ease: easeSoftOut }}
          >
            <motion.h2
              className="mb-8 text-center font-normal leading-snug text-[#FDF0F0]"
              style={{ fontFamily: dmSans, fontSize: 16 }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.55, ease: easeSoftOut, delay: 0.08 }}
            >
              Upload your doctor&apos;s note.
            </motion.h2>

            <input
              ref={doctorNoteFileInputRef}
              type="file"
              accept="image/*"
              className="sr-only"
              aria-hidden
              tabIndex={-1}
              onChange={onDoctorNoteFileChange}
            />

            <div
              role="button"
              tabIndex={0}
              aria-label="Choose doctor note image"
              className="flex cursor-pointer flex-col items-center justify-center px-4 outline-none transition-[opacity] duration-300 focus-visible:ring-2 focus-visible:ring-[#F4C2C2]/60"
              style={doctorNoteUploadZoneStyle}
              onClick={() => doctorNoteFileInputRef.current?.click()}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  doctorNoteFileInputRef.current?.click()
                }
              }}
            >
              {doctorNotePreviewUrl ? (
                <img
                  src={doctorNotePreviewUrl}
                  alt="Doctor note preview"
                  className="max-h-[210px] max-w-full rounded-lg object-contain"
                  draggable={false}
                />
              ) : (
                <>
                  <span className="mb-2 text-2xl" aria-hidden>
                    📷
                  </span>
                  <p
                    className="max-w-[260px] text-center font-normal leading-snug text-[#9B7B7B]"
                    style={{ fontFamily: dmSans, fontSize: 12 }}
                  >
                    Take a photo or upload your note
                  </p>
                </>
              )}
            </div>

            <button
              type="button"
              disabled={!doctorNotePreviewUrl}
              className={`${glassPillButton} mt-8 ${!doctorNotePreviewUrl ? 'pointer-events-none opacity-35' : 'opacity-100'}`}
              style={{ fontFamily: dmSans }}
              onClick={handleReadDoctorNote}
            >
              Read my note →
            </button>

            <button
              type="button"
              className="mt-6 cursor-pointer border-none bg-transparent p-0 text-[12px] font-normal text-[#9B7B7B] underline underline-offset-2"
              style={{ fontFamily: dmSans }}
              onClick={skipDoctorNoteToHeart}
            >
              Skip for now
            </button>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {doctorNoteOcrResult ? (
          <motion.div
            key="doctor-note-ocr-insight"
            className="pointer-events-none fixed top-1/2 z-[45] max-h-[88vh] -translate-y-1/2 overflow-y-auto"
            style={{ right: 24, width: 'min(300px, calc(100vw - 48px))' }}
            initial={{ opacity: 0, x: 14 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 10 }}
            transition={{ duration: 0.65, ease: easeSoftOut }}
          >
            <div
              className="pointer-events-auto"
              style={{
                padding: '20px 22px',
                borderRadius: 16,
                backdropFilter: 'blur(12px)',
                WebkitBackdropFilter: 'blur(12px)',
                backgroundColor: 'rgba(255,255,255,0.08)',
                border: '1px solid rgba(255,255,255,0.2)',
                fontFamily: dmSans,
                textAlign: 'left',
              }}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span
                  style={{
                    color: '#FDF0F0',
                    fontSize: 14,
                    fontWeight: 600,
                  }}
                >
                  {doctorNoteOcrResult.condition}
                </span>
                <span
                  className="rounded-full border border-red-400/40 bg-red-500/[0.16] px-2 py-0.5 text-[9px] font-semibold uppercase tracking-[0.1em] text-[#e8a0a0]"
                  style={{ fontFamily: dmSans }}
                >
                  {doctorNoteOcrResult.risk}
                </span>
              </div>
              <p
                className="mt-1 font-normal leading-snug text-[#9B7B7B]"
                style={{ fontFamily: dmSans, fontSize: 10 }}
              >
                {doctorNoteOcrResult.region}
              </p>
              <p
                className="mt-3 font-normal leading-snug text-[#9B7B7B]"
                style={{ fontFamily: dmSans, fontSize: 11, lineHeight: 1.45 }}
              >
                {doctorNoteOcrResult.description}
              </p>

              <div
                className="mt-4"
                style={{
                  padding: '12px 14px',
                  borderRadius: 12,
                  backgroundColor: 'rgba(232, 128, 128, 0.14)',
                  border: '1px solid rgba(232, 128, 128, 0.42)',
                }}
              >
                <div
                  className="font-semibold uppercase tracking-[0.06em] text-[#E88080]"
                  style={{ fontFamily: dmSans, fontSize: 10 }}
                >
                  What to say to your doctor:
                </div>
                <p
                  className="mt-2 font-normal leading-snug text-[#FDF0F0]"
                  style={{ fontFamily: dmSans, fontSize: 11, lineHeight: 1.45 }}
                >
                  {doctorNoteOcrResult.doctorScript}
                </p>
              </div>

              <div
                style={{
                  marginTop: 14,
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
                {doctorNoteOcrResult.questions.map((q) => (
                  <li key={q} style={{ marginBottom: 6 }}>
                    {q}
                  </li>
                ))}
              </ul>
            </div>
          </motion.div>
        ) : meshInfo ? (
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
        animate={{
          opacity: showLandingCta ? 1 : 0,
        }}
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
            <button
              type="button"
              className={glassPillButton}
              onClick={() => setShowDoctorNoteUpload(true)}
            >
              I have a doctor&apos;s note
            </button>
          </div>
        </div>
      </motion.div>

      <motion.p
        className="pointer-events-none fixed inset-x-0 bottom-6 z-30 px-6 text-center text-[0.5625rem] font-normal leading-snug tracking-[0.06em] text-[#9B7B7B] md:bottom-8 md:text-[0.625rem]"
        initial={{ opacity: 0 }}
        animate={{
          opacity: showLandingCta ? 1 : 0,
        }}
        transition={{ duration: 1.15, ease: easeSoftOut }}
      >
        Your data never leaves your device.
      </motion.p>
    </div>
  )
}
