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
  HEART_FADE_DURATION_S,
  ONBOARDING_EXIT_DURATION_S,
  PARTICLE_DURATION_S,
  PREGNANCY_RISK_ANALYSIS_MS,
  easeSoftOut,
} from './shared/animation'
import { dmSans, editProfilePillButton } from './shared/styles'
import { generateParticles } from './features/landing/particles'
import { MOCK_DOCTOR_NOTE_OCR } from './features/doctor-note/doctorNote.mock'
import { DEMO_DOCTOR_NOTE_RECORDS, toDoctorNoteOcrResult, type DemoDoctorNoteRecord } from './features/doctor-note/demoDoctorNotes'
import type { DoctorNoteOcrResult } from './features/doctor-note/doctorNote.types'
import DoctorNoteInsightPanel from './features/doctor-note/DoctorNoteInsightPanel'
import {
  createEmptyRiskFactors,
  toPostnatalFollowupRequest,
  toPrenatalCvdRequest,
  validatePostnatalRiskFactors,
  validatePrenatalRiskFactors,
} from './features/risk-profile/riskProfilePayload'
import type { PregnancyRiskResult, RiskFactors } from './features/risk-profile/riskProfile.types'
import { AgentChatApiError, submitAgentChat } from './api/agentChat'
import { DoctorNoteScreeningApiError, submitDoctorNoteScreening } from './api/doctorNoteScreening'
import { submitAppleWatchEcgInference } from './api/ecg'
import { submitPostnatalFollowupScreening, submitPrenatalCvdScreening } from './api/screening'
import { parseAppleWatchEcgUpload } from './features/ecg/appleWatchEcgParsing'
import {
  AppleWatchEcgApiError,
  type AppleWatchEcgInferResponse,
  type AppleWatchEcgRecordSummary,
  type AppleWatchEcgWindowPolicy,
  type ParsedAppleWatchEcgUpload,
} from './types/ecg'
import { ScreeningApiError } from './types/screening'
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

function createDoctorNoteChatSessionId() {
  return `doctor-note-${Date.now()}-${Math.random().toString(36).slice(2)}`
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
    'question' | 'pregnancyStage' | 'profileDetails' | 'riskFactors'
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
  const [parsedEcgUpload, setParsedEcgUpload] = useState<ParsedAppleWatchEcgUpload | null>(null)
  const [ecgRecordSummaries, setEcgRecordSummaries] = useState<AppleWatchEcgRecordSummary[]>([])
  const [selectedEcgRecordIndex, setSelectedEcgRecordIndex] = useState(0)
  const [ecgParseError, setEcgParseError] = useState<string | null>(null)
  const [ecgAnalysisError, setEcgAnalysisError] = useState<string | null>(null)
  const [ecgAnalysisResult, setEcgAnalysisResult] = useState<AppleWatchEcgInferResponse | null>(null)
  const [ecgWindowPolicy, setEcgWindowPolicy] = useState<AppleWatchEcgWindowPolicy>('first')
  const [ecgThreshold, setEcgThreshold] = useState('0.5')
  const [doctorNotePreviewUrl, setDoctorNotePreviewUrl] = useState<
    string | null
  >(null)
  const doctorNoteFileInputRef = useRef<HTMLInputElement>(null)
  const ecgFileInputRef = useRef<HTMLInputElement>(null)
  const readDoctorNoteTimerRef = useRef(0)
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
  const [doctorNoteFollowUpResponse, setDoctorNoteFollowUpResponse] = useState<string | null>(null)
  const [doctorNoteFollowUpError, setDoctorNoteFollowUpError] = useState<string | null>(null)
  const [doctorNoteFollowUpLoading, setDoctorNoteFollowUpLoading] = useState(false)
  const [doctorNoteScreeningLoading, setDoctorNoteScreeningLoading] = useState(false)
  const [doctorNoteScreeningError, setDoctorNoteScreeningError] = useState<string | null>(null)
  const [doctorNoteChatSessionId, setDoctorNoteChatSessionId] = useState(() =>
    createDoctorNoteChatSessionId(),
  )
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

  const onEcgFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] ?? null
    setEcgFile(file)
    setParsedEcgUpload(null)
    setEcgRecordSummaries([])
    setSelectedEcgRecordIndex(0)
    setEcgParseError(null)
    setEcgAnalysisError(null)
    setEcgAnalysisResult(null)

    if (!file) return

    try {
      const data: unknown = JSON.parse(await file.text())
      const parsed = parseAppleWatchEcgUpload(data)
      setParsedEcgUpload(parsed)
      setEcgRecordSummaries(parsed.recordSummaries)
    } catch (error) {
      setEcgParseError(
        error instanceof Error
          ? error.message
          : 'Upload a valid Apple Watch ECG JSON export.',
      )
    }
  }

  const clearEcgSelection = () => {
    setEcgFile(null)
    setParsedEcgUpload(null)
    setEcgRecordSummaries([])
    setSelectedEcgRecordIndex(0)
    setEcgParseError(null)
    setEcgAnalysisError(null)
    setEcgAnalysisResult(null)
    setEcgReadingLoading(false)
    setEcgWindowPolicy('first')
    setEcgThreshold('0.5')
    const input = ecgFileInputRef.current
    if (input) input.value = ''
  }

  const skipEcgToHeart = () => {
    clearEcgSelection()
    navigate(ROUTE_PATHS.heart)
  }

  const handleAnalyzeEcg = async () => {
    if (!parsedEcgUpload || ecgReadingLoading) return

    const threshold = Number(ecgThreshold)
    if (!Number.isFinite(threshold) || threshold < 0 || threshold > 1) {
      setEcgAnalysisError('Choose a threshold between 0 and 1.')
      return
    }

    setEcgReadingLoading(true)
    setEcgAnalysisError(null)
    setEcgAnalysisResult(null)

    try {
      const response = await submitAppleWatchEcgInference(
        parsedEcgUpload.kind === 'healthExport'
          ? {
              healthExport: parsedEcgUpload.healthExport,
              recordIndex: selectedEcgRecordIndex,
              windowPolicy: ecgWindowPolicy,
              threshold,
            }
          : {
              ecgRecord: parsedEcgUpload.ecgRecord,
              windowPolicy: ecgWindowPolicy,
              threshold,
            },
      )
      setEcgAnalysisResult(response)
    } catch (error) {
      if (error instanceof AppleWatchEcgApiError) {
        setEcgAnalysisError(error.userMessage)
      } else {
        setEcgAnalysisError('We could not analyze this ECG file right now. Please try again shortly.')
      }
    } finally {
      setEcgReadingLoading(false)
    }
  }

  const skipDoctorNoteToHeart = () => {
    revokeDoctorNotePreview()
    navigate(ROUTE_PATHS.heart)
  }

  const resetDoctorNoteChatState = () => {
    setDoctorNoteFollowUpDraft('')
    setDoctorNoteFollowUpResponse(null)
    setDoctorNoteFollowUpError(null)
    setDoctorNoteFollowUpLoading(false)
    setDoctorNoteScreeningLoading(false)
    setDoctorNoteScreeningError(null)
    setDoctorNoteChatSessionId(createDoctorNoteChatSessionId())
  }

  const handleReadDoctorNote = () => {
    setMeshInfo(null)
    navigate(ROUTE_PATHS.heart)
    resetDoctorNoteChatState()
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

  const selectDemoDoctorNote = async (record: DemoDoctorNoteRecord) => {
    const sessionId = createDoctorNoteChatSessionId()
    setMeshInfo(null)
    navigate(ROUTE_PATHS.heart)
    revokeDoctorNotePreview()
    resetDoctorNoteChatState()
    setDoctorNoteChatSessionId(sessionId)
    setDoctorNoteOcrLoading(false)
    setDoctorNoteOcrResult(toDoctorNoteOcrResult(record))
    setDoctorNoteScreeningLoading(true)
    setDoctorNoteScreeningError(null)
    setHeartInteractive(false)
    if (readDoctorNoteTimerRef.current) {
      window.clearTimeout(readDoctorNoteTimerRef.current)
      readDoctorNoteTimerRef.current = 0
    }

    try {
      const screening = await submitDoctorNoteScreening({ sessionId, record })
      setDoctorNoteOcrResult((current) => (current ? { ...current, screening } : current))
    } catch (error) {
      if (error instanceof DoctorNoteScreeningApiError) {
        setDoctorNoteScreeningError(error.userMessage)
      } else {
        setDoctorNoteScreeningError(
          'We could not process this note for screening right now. You can still ask about the note summary.',
        )
      }
    } finally {
      setDoctorNoteScreeningLoading(false)
    }
  }

  const submitDoctorNoteFollowUp = async (e?: FormEvent<HTMLFormElement>) => {
    e?.preventDefault()
    const question = doctorNoteFollowUpDraft.trim()
    if (!doctorNoteOcrResult || !question || doctorNoteFollowUpLoading) return

    setDoctorNoteFollowUpLoading(true)
    setDoctorNoteFollowUpError(null)
    setDoctorNoteFollowUpResponse(null)

    try {
      const response = await submitAgentChat({
        sessionId: doctorNoteChatSessionId,
        surface: 'general_health_companion',
        doctorNote: doctorNoteOcrResult,
        doctorNoteScreening: doctorNoteOcrResult.screening ?? null,
        messages: [{ role: 'user', content: question }],
      })
      setDoctorNoteFollowUpResponse(response.assistantText)
      setDoctorNoteFollowUpDraft('')
    } catch (error) {
      if (error instanceof AgentChatApiError) {
        setDoctorNoteFollowUpError(error.userMessage)
      } else {
        setDoctorNoteFollowUpError(
          'We could not answer that question right now. Please try again shortly.',
        )
      }
    } finally {
      setDoctorNoteFollowUpLoading(false)
    }
  }

  const handlePregnancyRiskSubmit = async () => {
    setPregnancyRiskSubmitMessage(null)

    const validationMessage =
      riskFactors.pregnancyMode === 'prenatal'
        ? validatePrenatalRiskFactors(riskFactors, profileAge)
        : validatePostnatalRiskFactors(riskFactors, profileAge)

    if (validationMessage) {
      setPregnancyRiskSubmitMessage(validationMessage)
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

      const screeningRequest =
        riskFactors.pregnancyMode === 'prenatal'
          ? submitPrenatalCvdScreening(toPrenatalCvdRequest(riskFactors, profileAge))
          : submitPostnatalFollowupScreening(
              toPostnatalFollowupRequest(riskFactors, profileAge),
            )

      const [response] = await Promise.all([screeningRequest, minimumSpinnerMs])

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
    setDoctorNoteFollowUpResponse(null)
    setDoctorNoteFollowUpError(null)
    setDoctorNoteFollowUpLoading(false)
    setDoctorNoteScreeningLoading(false)
    setDoctorNoteScreeningError(null)
    setDoctorNoteChatSessionId(createDoctorNoteChatSessionId())
    setEcgReadingLoading(false)
    if (readDoctorNoteTimerRef.current) {
      window.clearTimeout(readDoctorNoteTimerRef.current)
      readDoctorNoteTimerRef.current = 0
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
            response={doctorNoteFollowUpResponse}
            error={doctorNoteFollowUpError}
            isLoading={doctorNoteFollowUpLoading}
            screeningLoading={doctorNoteScreeningLoading}
            screeningError={doctorNoteScreeningError}
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
            profileAvatarInputRef={profileAvatarInputRef}
            profileAvatarUrl={profileAvatarUrl}
            onProfileAvatarChange={onProfileAvatarChange}
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
            profileAvatarInputRef={profileAvatarInputRef}
            profileAvatarUrl={profileAvatarUrl}
            onProfileAvatarChange={onProfileAvatarChange}
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
            recordSummaries={ecgRecordSummaries}
            selectedRecordIndex={selectedEcgRecordIndex}
            parseError={ecgParseError}
            analysisError={ecgAnalysisError}
            analysisResult={ecgAnalysisResult}
            isAnalyzing={ecgReadingLoading}
            windowPolicy={ecgWindowPolicy}
            threshold={ecgThreshold}
            onEcgFileChange={onEcgFileChange}
            onSelectedRecordIndexChange={setSelectedEcgRecordIndex}
            onWindowPolicyChange={setEcgWindowPolicy}
            onThresholdChange={setEcgThreshold}
            onAnalyzeEcg={handleAnalyzeEcg}
            onReset={clearEcgSelection}
            onSkip={skipEcgToHeart}
          />
        }
        doctorNoteUpload={
          <DoctorNoteRoute
            doctorNoteFileInputRef={doctorNoteFileInputRef}
            doctorNotePreviewUrl={doctorNotePreviewUrl}
            demoDoctorNoteRecords={DEMO_DOCTOR_NOTE_RECORDS}
            onDoctorNoteFileChange={onDoctorNoteFileChange}
            onReadDoctorNote={handleReadDoctorNote}
            onSelectDemoDoctorNote={selectDemoDoctorNote}
            onSkip={skipDoctorNoteToHeart}
          />
        }
      />
    </div>
  )
}
