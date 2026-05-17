import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
} from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useLocation, useNavigate } from 'react-router-dom'
import HeartModel, { type MeshSelectPayload } from './components/HeartModel'
import {
  CTA_DELAY_AFTER_HEART_S,
  DOCTOR_NOTE_READING_MS,
  ECG_READING_MS,
  HEART_FADE_DURATION_S,
  ONBOARDING_EXIT_DURATION_S,
  PARTICLE_DURATION_S,
  PREGNANCY_RISK_ANALYSIS_MS,
  easeSoftOut,
} from './shared/animation'
import { dmSans, editProfilePillButton } from './shared/styles'
import { generateParticles } from './features/landing/particles'
import { MOCK_DOCTOR_NOTE_OCR } from './features/doctor-note/doctorNote.mock'
import type { DoctorNoteOcrResult } from './features/doctor-note/doctorNote.types'
import DoctorNoteInsightPanel from './features/doctor-note/DoctorNoteInsightPanel'
import { createEmptyRiskFactors } from './features/risk-profile/riskProfilePayload'
import type { PregnancyRiskResult, RiskFactors } from './features/risk-profile/riskProfile.types'
import { submitPrenatalCvdScreening } from './api/screening'
import { ScreeningApiError, type PrenatalCvdRequest } from './types/screening'
import RiskResultPanel from './features/risk-profile/RiskResultPanel'
import HeartInsightPanel from './features/heart/HeartInsightPanel'
import { ProfilePanel } from './features/profile/ProfilePanel'
import { AppRoutes } from './routes/AppRoutes'
import { ROUTE_PATHS } from './routes/paths'
import { LandingRoute } from './routes/LandingRoute'
import { OnboardingRoute } from './routes/OnboardingRoute'
import { RiskProfileRoute } from './routes/RiskProfileRoute'
import { HeartRoute } from './routes/HeartRoute'
import { EcgRoute } from './routes/EcgRoute'
import { DoctorNoteRoute } from './routes/DoctorNoteRoute'

const BG = '#1a0a0a'


function EcgHeartGlyph({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      width={20}
      height={18}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden
    >
      <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
    </svg>
  )
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

function toPrenatalRequest(riskFactors: RiskFactors): PrenatalCvdRequest | null {
  const {
    age,
    prepregnancyBmi,
    liveBirthsCount,
    chronicHypertension,
    diabetes,
    priorPretermOrStillbirth,
    smokedPregnancy,
    multipleGestation,
  } = riskFactors

  if (
    riskFactors.pregnancyMode !== 'prenatal' ||
    !age.trim() ||
    !prepregnancyBmi.trim() ||
    !liveBirthsCount.trim() ||
    chronicHypertension === null ||
    diabetes === null ||
    priorPretermOrStillbirth === null ||
    smokedPregnancy === null ||
    multipleGestation === null
  ) {
    return null
  }

  return {
    pregnancyMode: 'prenatal',
    age,
    prepregnancyBmi,
    chronicHypertension,
    diabetes,
    priorPretermOrStillbirth,
    liveBirthsCount,
    smokedPregnancy,
    multipleGestation,
  }
}

function getPrenatalValidationMessage(riskFactors: RiskFactors): string | null {
  if (riskFactors.pregnancyMode !== 'prenatal') return null

  if (!riskFactors.age.trim() || Number.isNaN(Number(riskFactors.age))) {
    return 'Please enter a valid age before continuing.'
  }
  if (
    !riskFactors.prepregnancyBmi.trim() ||
    Number.isNaN(Number(riskFactors.prepregnancyBmi))
  ) {
    return 'Please enter a valid pre-pregnancy BMI before continuing.'
  }
  if (
    !riskFactors.liveBirthsCount.trim() ||
    !Number.isInteger(Number(riskFactors.liveBirthsCount))
  ) {
    return 'Please enter a whole number for live births count.'
  }

  const hasUnansweredYesNo = [
    riskFactors.chronicHypertension,
    riskFactors.diabetes,
    riskFactors.priorPretermOrStillbirth,
    riskFactors.smokedPregnancy,
    riskFactors.multipleGestation,
  ].some((value) => value === null)

  if (hasUnansweredYesNo) {
    return 'Please answer all yes/no questions before submitting.'
  }

  return null
}

export default function App() {
  const location = useLocation()
  const navigate = useNavigate()

  const isDirectFlowEntry = location.pathname !== ROUTE_PATHS.landing

  const [{ dims, particles }] = useState(() => {
    const w = typeof window !== 'undefined' ? window.innerWidth : 1920
    const h = typeof window !== 'undefined' ? window.innerHeight : 1080
    return {
      dims: { w, h },
      particles: generateParticles(w, h),
    }
  })

  const [landingIntroComplete, setLandingIntroComplete] = useState(isDirectFlowEntry)
  const [onboardingSubStep, setOnboardingSubStep] = useState<
    'question' | 'pregnancyStage' | 'riskFactors'
  >('question')
  const [pregnancyMode, setPregnancyMode] = useState<
    'prenatal' | 'postpartum' | null
  >(null)
  const [dismissPregnancyOnboarding, setDismissPregnancyOnboarding] =
    useState(false)
  const [heartReveal, setHeartReveal] = useState(isDirectFlowEntry)
  const [heartInteractive, setHeartInteractive] = useState(false)
  const [showCta, setShowCta] = useState(isDirectFlowEntry)
  const [meshInfo, setMeshInfo] = useState<MeshSelectPayload | null>(null)
  const [riskFactors, setRiskFactors] = useState<RiskFactors>(() =>
    createEmptyRiskFactors('prenatal'),
  )
  const [ecgFile, setEcgFile] = useState<File | null>(null)
  const [doctorNotePreviewUrl, setDoctorNotePreviewUrl] = useState<
    string | null
  >(null)
  const doctorNoteFileInputRef = useRef<HTMLInputElement>(null)
  const ecgFileInputRef = useRef<HTMLInputElement>(null)
  const readDoctorNoteTimerRef = useRef(0)
  const ecgReadTimerRef = useRef(0)
  const riskAnalysisTimerRef = useRef(0)

  const [pregnancyRiskAnalyzing, setPregnancyRiskAnalyzing] =
    useState(false)
  const [pregnancyRiskResult, setPregnancyRiskResult] =
    useState<PregnancyRiskResult | null>(null)
  const [pregnancyRiskSubmitMessage, setPregnancyRiskSubmitMessage] =
    useState<string | null>(null)

  const [doctorNoteOcrLoading, setDoctorNoteOcrLoading] = useState(false)
  const [doctorNoteOcrResult, setDoctorNoteOcrResult] =
    useState<DoctorNoteOcrResult | null>(null)
  const [doctorNoteFollowUpDraft, setDoctorNoteFollowUpDraft] = useState('')
  const [doctorNoteFollowUpShowPlaceholder, setDoctorNoteFollowUpShowPlaceholder] =
    useState(false)
  const [ecgReadingLoading, setEcgReadingLoading] = useState(false)

  const profileAvatarInputRef = useRef<HTMLInputElement>(null)
  const [profileAvatarUrl, setProfileAvatarUrl] = useState<string | null>(null)
  const [profileDisplayName, setProfileDisplayName] = useState('')
  const [profileAge, setProfileAge] = useState('')
  const [profileWeeksPregnant, setProfileWeeksPregnant] = useState('')
  const [profileWeeksPostpartum, setProfileWeeksPostpartum] = useState('')
  const [profileMedications, setProfileMedications] = useState('')
  const [profileAllergies, setProfileAllergies] = useState('')
  const [profileLatestVisit, setProfileLatestVisit] = useState('')

  const showParticlesLayer =
    location.pathname === ROUTE_PATHS.landing && !landingIntroComplete
  const isOnboardingSurface =
    location.pathname === ROUTE_PATHS.onboarding ||
    location.pathname === ROUTE_PATHS.riskProfile
  const showEcgUpload = location.pathname === ROUTE_PATHS.ecgUpload
  const showDoctorNoteUpload =
    location.pathname === ROUTE_PATHS.doctorNoteUpload
  const routeIsHeartSurface =
    location.pathname === ROUTE_PATHS.heart ||
    showEcgUpload ||
    showDoctorNoteUpload
  const heartVisible = heartReveal || routeIsHeartSurface

  const revokeProfileAvatar = useCallback(() => {
    setProfileAvatarUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return null
    })
    const input = profileAvatarInputRef.current
    if (input) input.value = ''
  }, [])

  useEffect(() => {
    return () => {
      if (profileAvatarUrl) URL.revokeObjectURL(profileAvatarUrl)
    }
  }, [profileAvatarUrl])

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
      if (ecgReadTimerRef.current) {
        window.clearTimeout(ecgReadTimerRef.current)
      }
      if (riskAnalysisTimerRef.current) {
        window.clearTimeout(riskAnalysisTimerRef.current)
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

  const onProfileAvatarChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file?.type.startsWith('image/')) return
    setProfileAvatarUrl((prev) => {
      if (prev) URL.revokeObjectURL(prev)
      return URL.createObjectURL(file)
    })
  }

  const onEcgFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    setEcgFile(e.target.files?.[0] ?? null)
  }

  const clearEcgSelection = () => {
    setEcgFile(null)
    const input = ecgFileInputRef.current
    if (input) input.value = ''
  }

  const skipEcgToHeart = () => {
    clearEcgSelection()
    navigate(ROUTE_PATHS.heart)
  }

  const handleAnalyzeEcg = () => {
    if (!ecgFile) return
    navigate(ROUTE_PATHS.heart)
    setEcgReadingLoading(true)
    setHeartInteractive(false)
    if (ecgReadTimerRef.current) {
      window.clearTimeout(ecgReadTimerRef.current)
    }
    ecgReadTimerRef.current = window.setTimeout(() => {
      ecgReadTimerRef.current = 0
      setEcgReadingLoading(false)
      clearEcgSelection()
    }, ECG_READING_MS)
  }

  const skipDoctorNoteToHeart = () => {
    revokeDoctorNotePreview()
    navigate(ROUTE_PATHS.heart)
  }

  const handleReadDoctorNote = () => {
    setMeshInfo(null)
    navigate(ROUTE_PATHS.heart)
    setDoctorNoteFollowUpDraft('')
    setDoctorNoteFollowUpShowPlaceholder(false)
    setDoctorNoteOcrLoading(true)
    setDoctorNoteOcrResult(null)
    setHeartInteractive(false)
    if (readDoctorNoteTimerRef.current) {
      window.clearTimeout(readDoctorNoteTimerRef.current)
    }
    readDoctorNoteTimerRef.current = window.setTimeout(() => {
      readDoctorNoteTimerRef.current = 0
      setDoctorNoteOcrLoading(false)
      setDoctorNoteOcrResult(MOCK_DOCTOR_NOTE_OCR)
    }, DOCTOR_NOTE_READING_MS)
  }

  const submitDoctorNoteFollowUp = (e?: FormEvent<HTMLFormElement>) => {
    e?.preventDefault()
    if (!doctorNoteOcrResult || !doctorNoteFollowUpDraft.trim()) return
    setDoctorNoteFollowUpShowPlaceholder(true)
    setDoctorNoteFollowUpDraft('')
  }

  const handlePregnancyRiskSubmit = async () => {
    setPregnancyRiskSubmitMessage(null)

    if (riskFactors.pregnancyMode === 'postpartum') {
      setPregnancyRiskSubmitMessage(
        'Postpartum risk screening is coming soon. For now, please review your recent symptoms with your OB or primary care team.',
      )
      return
    }

    const validationMessage = getPrenatalValidationMessage(riskFactors)
    if (validationMessage) {
      setPregnancyRiskSubmitMessage(validationMessage)
      return
    }

    const payload = toPrenatalRequest(riskFactors)
    if (!payload) {
      setPregnancyRiskSubmitMessage(
        'Some answers are missing or invalid. Please review your profile and try again.',
      )
      return
    }

    setMeshInfo(null)
    setPregnancyRiskAnalyzing(true)
    setPregnancyRiskResult(null)
    setHeartInteractive(false)

    try {
      const minimumSpinnerMs = new Promise<void>((resolve) => {
        if (riskAnalysisTimerRef.current) {
          window.clearTimeout(riskAnalysisTimerRef.current)
        }
        riskAnalysisTimerRef.current = window.setTimeout(() => {
          riskAnalysisTimerRef.current = 0
          resolve()
        }, PREGNANCY_RISK_ANALYSIS_MS)
      })

      const [response] = await Promise.all([
        submitPrenatalCvdScreening(payload),
        minimumSpinnerMs,
      ])

      setOnboardingSubStep('question')
      navigate(ROUTE_PATHS.heart)
      setHeartReveal(true)
      setPregnancyRiskResult(response)
    } catch (error) {
      setOnboardingSubStep('riskFactors')
      navigate(ROUTE_PATHS.riskProfile)
      if (error instanceof ScreeningApiError) {
        setPregnancyRiskSubmitMessage(error.userMessage)
      } else {
        setPregnancyRiskSubmitMessage(
          'We could not complete your screening right now. Please try again shortly.',
        )
      }
    } finally {
      setPregnancyRiskAnalyzing(false)
    }
  }

  useEffect(() => {
    if (location.pathname !== ROUTE_PATHS.landing || landingIntroComplete) {
      return
    }
    const particleEndMs = PARTICLE_DURATION_S * 1000
    const tParticlesDone = window.setTimeout(() => {
      setLandingIntroComplete(true)
      setOnboardingSubStep('question')
      navigate(ROUTE_PATHS.onboarding)
    }, particleEndMs)

    return () => {
      window.clearTimeout(tParticlesDone)
    }
  }, [location.pathname, landingIntroComplete, navigate])

  useEffect(() => {
    if (location.pathname !== ROUTE_PATHS.landing || !landingIntroComplete) return
    navigate(heartReveal ? ROUTE_PATHS.heart : ROUTE_PATHS.onboarding, { replace: true })
  }, [location.pathname, landingIntroComplete, heartReveal, navigate])

  useEffect(() => {
    if (!dismissPregnancyOnboarding) return
    const t = window.setTimeout(() => {
      setHeartReveal(true)
      setOnboardingSubStep('question')
      setPregnancyMode(null)
      setDismissPregnancyOnboarding(false)
      navigate(ROUTE_PATHS.heart)
    }, ONBOARDING_EXIT_DURATION_S * 1000)
    return () => window.clearTimeout(t)
  }, [dismissPregnancyOnboarding, navigate])

  useEffect(() => {
    if (!heartVisible) return
    const ctaMs =
      (HEART_FADE_DURATION_S + CTA_DELAY_AFTER_HEART_S) * 1000
    const tCta = window.setTimeout(() => setShowCta(true), ctaMs)
    return () => window.clearTimeout(tCta)
  }, [heartVisible])

  useEffect(() => {
    if (
      !heartVisible ||
      doctorNoteOcrLoading ||
      ecgReadingLoading ||
      pregnancyRiskAnalyzing
    )
      return
    const t = window.setTimeout(
      () => setHeartInteractive(true),
      HEART_FADE_DURATION_S * 1000,
    )
    return () => window.clearTimeout(t)
  }, [heartVisible, doctorNoteOcrLoading, ecgReadingLoading, pregnancyRiskAnalyzing])

  const cx = dims.w / 2
  const cy = dims.h / 2

  const resetToPregnancyOnboarding = () => {
    setHeartReveal(false)
    setHeartInteractive(false)
    setShowCta(false)
    setMeshInfo(null)
    setDismissPregnancyOnboarding(false)
    setPregnancyMode(null)
    setRiskFactors(createEmptyRiskFactors('prenatal'))
    setOnboardingSubStep('question')
    clearEcgSelection()
    revokeDoctorNotePreview()
    setDoctorNoteOcrLoading(false)
    setDoctorNoteOcrResult(null)
    setDoctorNoteFollowUpDraft('')
    setDoctorNoteFollowUpShowPlaceholder(false)
    setEcgReadingLoading(false)
    if (readDoctorNoteTimerRef.current) {
      window.clearTimeout(readDoctorNoteTimerRef.current)
      readDoctorNoteTimerRef.current = 0
    }
    if (ecgReadTimerRef.current) {
      window.clearTimeout(ecgReadTimerRef.current)
      ecgReadTimerRef.current = 0
    }
    if (riskAnalysisTimerRef.current) {
      window.clearTimeout(riskAnalysisTimerRef.current)
      riskAnalysisTimerRef.current = 0
    }
    setPregnancyRiskAnalyzing(false)
    setPregnancyRiskResult(null)
    setPregnancyRiskSubmitMessage(null)
    revokeProfileAvatar()
    setProfileDisplayName('')
    setProfileAge('')
    setProfileWeeksPregnant('')
    setProfileWeeksPostpartum('')
    setProfileMedications('')
    setProfileAllergies('')
    setProfileLatestVisit('')
    navigate(ROUTE_PATHS.onboarding)
  }

  const showEditProfileButton =
    heartVisible && !isOnboardingSurface

  const showProfilePanel = heartVisible && !isOnboardingSurface

  const showLandingCta =
    showCta &&
    !showDoctorNoteUpload &&
    !showEcgUpload &&
    !doctorNoteOcrLoading &&
    !ecgReadingLoading &&
    doctorNoteOcrResult === null &&
    !pregnancyRiskAnalyzing &&
    pregnancyRiskResult === null


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

      {showProfilePanel ? (
        <ProfilePanel
          profileAvatarInputRef={profileAvatarInputRef}
          profileAvatarUrl={profileAvatarUrl}
          onProfileAvatarChange={onProfileAvatarChange}
          pregnancyMode={pregnancyMode}
          profileDisplayName={profileDisplayName}
          setProfileDisplayName={setProfileDisplayName}
          profileAge={profileAge}
          setProfileAge={setProfileAge}
          profileWeeksPregnant={profileWeeksPregnant}
          setProfileWeeksPregnant={setProfileWeeksPregnant}
          profileWeeksPostpartum={profileWeeksPostpartum}
          setProfileWeeksPostpartum={setProfileWeeksPostpartum}
          profileMedications={profileMedications}
          setProfileMedications={setProfileMedications}
          profileAllergies={profileAllergies}
          setProfileAllergies={setProfileAllergies}
          profileLatestVisit={profileLatestVisit}
          setProfileLatestVisit={setProfileLatestVisit}
        />
      ) : null}

      <motion.div
        className="fixed inset-0 z-0"
        initial={{ opacity: 0 }}
        animate={{ opacity: heartVisible ? 1 : 0 }}
        transition={{
          duration: HEART_FADE_DURATION_S,
          ease: easeSoftOut,
        }}
        style={{
          pointerEvents:
            heartInteractive &&
            !doctorNoteOcrLoading &&
            !ecgReadingLoading &&
            !pregnancyRiskAnalyzing
              ? 'auto'
              : 'none',
        }}
      >
        <motion.div
          className="h-full w-full"
          animate={{
            opacity:
              doctorNoteOcrLoading ||
              ecgReadingLoading ||
              pregnancyRiskAnalyzing
                ? [0.3, 0.36, 0.3]
                : 1,
          }}
          transition={{
            duration:
              doctorNoteOcrLoading ||
              ecgReadingLoading ||
              pregnancyRiskAnalyzing
                ? 2.8
                : 0.5,
            repeat:
              doctorNoteOcrLoading ||
              ecgReadingLoading ||
              pregnancyRiskAnalyzing
                ? Infinity
                : 0,
            ease: 'easeInOut',
          }}
        >
          <HeartModel onSelect={setMeshInfo} />
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
        ) : ecgReadingLoading ? (
          <motion.div
            key="reading-ecg"
            className="pointer-events-none fixed inset-x-0 bottom-[20%] z-[44] flex justify-center px-6 md:bottom-[24%]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.4, ease: easeSoftOut }}
          >
            <div
              className="flex flex-col items-center gap-3"
              style={{ fontFamily: dmSans }}
            >
              <motion.div
                animate={{ scale: [1, 1.14, 1] }}
                transition={{
                  duration: 1.15,
                  repeat: Infinity,
                  ease: 'easeInOut',
                }}
                className="text-[#E88080]"
                aria-hidden
              >
                <EcgHeartGlyph className="text-current" />
              </motion.div>
              <p
                className="text-center font-normal tracking-[0.02em] text-[#9B7B7B]"
                style={{ fontSize: 12 }}
              >
                Reading your ECG...
              </p>
            </div>
          </motion.div>
        ) : pregnancyRiskAnalyzing ? (
          <motion.div
            key="analyzing-risk"
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
              <span>Analyzing your risk profile</span>
              <ReadingNoteEllipsis />
            </p>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        {doctorNoteOcrResult ? (
          <DoctorNoteInsightPanel
            result={doctorNoteOcrResult}
            draft={doctorNoteFollowUpDraft}
            showPlaceholder={doctorNoteFollowUpShowPlaceholder}
            setDraft={setDoctorNoteFollowUpDraft}
            onSubmitFollowUp={submitDoctorNoteFollowUp}
          />
        ) : pregnancyRiskResult ? (
          <RiskResultPanel result={pregnancyRiskResult} />
        ) : meshInfo ? (
          <HeartInsightPanel meshInfo={meshInfo} />
        ) : null}
      </AnimatePresence>

      <AppRoutes
        landing={<LandingRoute showParticles={showParticlesLayer} particles={particles} cx={cx} cy={cy} />}
        onboarding={
          <OnboardingRoute
            bg={BG}
            dismissing={dismissPregnancyOnboarding}
            subStep={onboardingSubStep}
            pregnancyMode={pregnancyMode}
            riskFactors={riskFactors}
            setSubStep={(step) => {
              setOnboardingSubStep(step)
              navigate(step === 'riskFactors' ? ROUTE_PATHS.riskProfile : ROUTE_PATHS.onboarding)
            }}
            setPregnancyMode={setPregnancyMode}
            setDismiss={setDismissPregnancyOnboarding}
            setRiskFactors={setRiskFactors}
            createEmptyRiskFactors={createEmptyRiskFactors}
            onSubmitRisk={handlePregnancyRiskSubmit}
            riskSubmitMessage={pregnancyRiskSubmitMessage}
          />
        }
        riskProfile={
          <RiskProfileRoute
            bg={BG}
            dismissing={dismissPregnancyOnboarding}
            pregnancyMode={pregnancyMode ?? 'prenatal'}
            riskFactors={riskFactors}
            setSubStep={(step) => {
              setOnboardingSubStep(step)
              navigate(step === 'riskFactors' ? ROUTE_PATHS.riskProfile : ROUTE_PATHS.onboarding)
            }}
            setPregnancyMode={setPregnancyMode}
            setDismiss={setDismissPregnancyOnboarding}
            setRiskFactors={setRiskFactors}
            createEmptyRiskFactors={createEmptyRiskFactors}
            onSubmitRisk={handlePregnancyRiskSubmit}
            riskSubmitMessage={pregnancyRiskSubmitMessage}
          />
        }
        heart={
          <HeartRoute
            showLandingCta={showLandingCta}
            onOpenEcg={() => navigate(ROUTE_PATHS.ecgUpload)}
            onOpenDoctorNote={() => navigate(ROUTE_PATHS.doctorNoteUpload)}
          />
        }
        ecgUpload={
          <EcgRoute
            ecgFileInputRef={ecgFileInputRef}
            ecgFile={ecgFile}
            onEcgFileChange={onEcgFileChange}
            onAnalyzeEcg={handleAnalyzeEcg}
            onSkip={skipEcgToHeart}
          />
        }
        doctorNoteUpload={
          <DoctorNoteRoute
            doctorNoteFileInputRef={doctorNoteFileInputRef}
            doctorNotePreviewUrl={doctorNotePreviewUrl}
            onDoctorNoteFileChange={onDoctorNoteFileChange}
            onReadDoctorNote={handleReadDoctorNote}
            onSkip={skipDoctorNoteToHeart}
          />
        }
      />
    </div>
  )
}
