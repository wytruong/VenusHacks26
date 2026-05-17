import { useState, type ChangeEvent, type Dispatch, type RefObject, type SetStateAction } from 'react'
import { motion } from 'framer-motion'
import { dmSans, glassFieldCardStyle, glassNumberInputStyle, glassPillButton, glassTogglePill, profilePanelGlassInputStyle } from '../../shared/styles'
import { easeSoftOut, ONBOARDING_EXIT_DURATION_S } from '../../shared/animation'
import type { RiskFactors } from '../risk-profile/riskProfile.types'

type OnboardingSubStep = 'question' | 'pregnancyStage' | 'profileDetails' | 'riskFactors'

type OnboardingFlowProps = {
  bg: string
  show: boolean
  dismissing: boolean
  subStep: OnboardingSubStep
  pregnancyMode: 'prenatal' | 'postpartum' | null
  riskFactors: RiskFactors
  setSubStep: (step: OnboardingSubStep) => void
  setPregnancyMode: (mode: 'prenatal' | 'postpartum') => void
  setDismiss: (value: boolean) => void
  setRiskFactors: Dispatch<SetStateAction<RiskFactors>>
  createEmptyRiskFactors: (mode: 'prenatal' | 'postpartum') => RiskFactors
  onSubmitRisk: () => void
  riskSubmitMessage: string | null
  profileAvatarInputRef: RefObject<HTMLInputElement | null>
  profileAvatarUrl: string | null
  onProfileAvatarChange: (event: ChangeEvent<HTMLInputElement>) => void
  profileDisplayName: string
  setProfileDisplayName: (value: string) => void
  profileAge: string
  setProfileAge: (value: string) => void
  profileWeeksPregnant: string
  setProfileWeeksPregnant: (value: string) => void
  profileWeeksPostpartum: string
  setProfileWeeksPostpartum: (value: string) => void
  profileMedications: string
  setProfileMedications: (value: string) => void
  profileAllergies: string
  setProfileAllergies: (value: string) => void
  profileLatestVisit: string
  setProfileLatestVisit: (value: string) => void
}

function GlassYesNo({ value, onPick }: { value: boolean | null; onPick: (v: boolean) => void }) {
  return (
    <div className="mt-3 flex flex-row gap-3">
      <button
        type="button"
        className={`${glassTogglePill} ${value === true ? 'bg-white/[0.15]' : 'bg-white/[0.08]'}`}
        style={{ fontFamily: dmSans }}
        onClick={() => onPick(true)}
      >
        Yes
      </button>
      <button
        type="button"
        className={`${glassTogglePill} ${value === false ? 'bg-white/[0.15]' : 'bg-white/[0.08]'}`}
        style={{ fontFamily: dmSans }}
        onClick={() => onPick(false)}
      >
        No
      </button>
    </div>
  )
}

function hasInvalidNumber(value: string) {
  return value.trim() !== '' && Number.isNaN(Number(value))
}

export default function OnboardingFlow({
  bg,
  show,
  dismissing,
  subStep,
  pregnancyMode,
  riskFactors,
  setSubStep,
  setPregnancyMode,
  setDismiss,
  setRiskFactors,
  createEmptyRiskFactors,
  onSubmitRisk,
  riskSubmitMessage,
  profileAvatarInputRef,
  profileAvatarUrl,
  onProfileAvatarChange,
  profileDisplayName,
  setProfileDisplayName,
  profileAge,
  setProfileAge,
  profileWeeksPregnant,
  setProfileWeeksPregnant,
  profileWeeksPostpartum,
  setProfileWeeksPostpartum,
  profileMedications,
  setProfileMedications,
  profileAllergies,
  setProfileAllergies,
  profileLatestVisit,
  setProfileLatestVisit,
}: OnboardingFlowProps) {
  const [profileValidationMessage, setProfileValidationMessage] = useState<string | null>(null)

  if (!show) return null

  const continueToRiskFactors = () => {
    setProfileValidationMessage(null)

    if (hasInvalidNumber(profileAge) || Number(profileAge) < 0) {
      setProfileValidationMessage('Please enter a valid non-negative age, or leave it blank.')
      return
    }

    if (pregnancyMode === 'prenatal') {
      const weeks = Number(profileWeeksPregnant)
      if (
        hasInvalidNumber(profileWeeksPregnant) ||
        (profileWeeksPregnant.trim() !== '' && (weeks < 0 || weeks > 42))
      ) {
        setProfileValidationMessage('Please enter pregnancy weeks from 0 to 42, or leave it blank.')
        return
      }
    }

    if (pregnancyMode === 'postpartum') {
      const weeks = Number(profileWeeksPostpartum)
      if (
        hasInvalidNumber(profileWeeksPostpartum) ||
        (profileWeeksPostpartum.trim() !== '' && weeks < 0)
      ) {
        setProfileValidationMessage('Please enter a valid non-negative postpartum week, or leave it blank.')
        return
      }
    }

    setSubStep('riskFactors')
  }

  return (
    <motion.div
      key="pregnancy-onboarding"
      className="fixed inset-0 z-[38] flex flex-col items-center justify-center overflow-y-auto px-6 py-12"
      style={{ backgroundColor: bg }}
      initial={{ opacity: 0 }}
      animate={{ opacity: dismissing ? 0 : 1 }}
      transition={{
        duration: dismissing ? ONBOARDING_EXIT_DURATION_S : 0.55,
        ease: easeSoftOut,
      }}
    >
      {subStep === 'question' ? (
        <>
          <p className="mb-10 max-w-xl text-center font-normal leading-snug text-[#FDF0F0]" style={{ fontFamily: dmSans, fontSize: 18 }}>
            Are you currently pregnant or postpartum?
          </p>
          <div className="flex flex-row flex-wrap items-center justify-center gap-4">
            <button type="button" className={glassPillButton} onClick={() => setSubStep('pregnancyStage')}>
              Yes, I am
            </button>
            <button type="button" className={glassPillButton} onClick={() => setDismiss(true)}>
              No, continue
            </button>
          </div>
          <button
            type="button"
            className="mt-8 cursor-pointer border-none bg-transparent p-0 text-[0.6875rem] font-normal text-[#9B7B7B] underline-offset-2 hover:underline"
            style={{ fontFamily: dmSans }}
            onClick={() => setDismiss(true)}
          >
            Prefer not to say
          </button>
        </>
      ) : subStep === 'pregnancyStage' ? (
        <>
          <p className="mb-10 max-w-xl text-center font-normal leading-snug text-[#FDF0F0]" style={{ fontFamily: dmSans, fontSize: 18 }}>
            What stage are you in?
          </p>
          <div className="flex flex-row flex-wrap items-center justify-center gap-4">
            <button
              type="button"
              className={glassPillButton}
              onClick={() => {
                setPregnancyMode('prenatal')
                setRiskFactors(createEmptyRiskFactors('prenatal'))
                setSubStep('profileDetails')
              }}
            >
              I am currently pregnant
            </button>
            <button
              type="button"
              className={glassPillButton}
              onClick={() => {
                setPregnancyMode('postpartum')
                setRiskFactors(createEmptyRiskFactors('postpartum'))
                setSubStep('profileDetails')
              }}
            >
              I recently gave birth
            </button>
          </div>
          <button
            type="button"
            className="mt-8 cursor-pointer border-none bg-transparent p-0 text-[0.6875rem] font-normal text-[#9B7B7B] underline underline-offset-2"
            style={{ fontFamily: dmSans }}
            onClick={() => setDismiss(true)}
          >
            Skip for now
          </button>
        </>
      ) : subStep === 'profileDetails' ? (
        <motion.div key="profile-details" className="flex w-full max-w-xl flex-col items-center pb-8" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.55, ease: easeSoftOut }}>
          <motion.h2 className="mb-2 text-center font-normal leading-snug text-[#FDF0F0]" style={{ fontFamily: dmSans, fontSize: 18 }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5, ease: easeSoftOut, delay: 0.06 }}>
            Profile details
          </motion.h2>
          <p className="mb-8 max-w-lg text-center text-[12px] font-normal leading-snug text-[#D4B8B8]" style={{ fontFamily: dmSans }}>
            This profile helps personalize your app experience. Your profile details are not sent to the prenatal screening model.
          </p>

          <div className="flex w-full flex-col gap-4" role="group" aria-labelledby="profile-details-heading">
            <span id="profile-details-heading" className="sr-only">
              Profile details form
            </span>
            <input ref={profileAvatarInputRef} id="profile-avatar-file" type="file" accept="image/*" className="hidden" onChange={onProfileAvatarChange} />
            <label className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }} htmlFor="profile-avatar-file">
              Profile photo
            </label>
            <button type="button" onClick={() => profileAvatarInputRef.current?.click()} className="flex items-center gap-3 text-left" style={profilePanelGlassInputStyle} aria-label="Upload profile photo">
              {profileAvatarUrl ? (
                <img src={profileAvatarUrl} alt="Profile preview" className="h-8 w-8 rounded-full object-cover" />
              ) : (
                <span className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-[#F4C2C2] text-[11px] text-[#D4B8B8]" aria-hidden>+</span>
              )}
              <span className="text-[11px] text-[#D4B8B8]">Upload profile photo</span>
            </button>
            <label className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }} htmlFor="profile-name">Display name</label>
            <input id="profile-name" type="text" value={profileDisplayName} onChange={(e) => setProfileDisplayName(e.target.value)} placeholder="Your name" className="placeholder:text-[#D4B8B8]" style={profilePanelGlassInputStyle} />
            <label className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }} htmlFor="profile-age">Age (optional)</label>
            <input id="profile-age" type="number" inputMode="numeric" min={0} value={profileAge} onChange={(e) => setProfileAge(e.target.value)} placeholder="Age" className="placeholder:text-[#D4B8B8] tabular-nums" style={profilePanelGlassInputStyle} />

            {pregnancyMode === 'prenatal' ? (
              <>
                <label className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }} htmlFor="profile-weeks-pregnant">Weeks pregnant (optional)</label>
                <input id="profile-weeks-pregnant" type="number" inputMode="numeric" min={0} max={42} value={profileWeeksPregnant} onChange={(e) => setProfileWeeksPregnant(e.target.value)} placeholder="0 to 42" className="placeholder:text-[#D4B8B8] tabular-nums" style={profilePanelGlassInputStyle} />
              </>
            ) : null}

            {pregnancyMode === 'postpartum' ? (
              <>
                <label className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }} htmlFor="profile-weeks-postpartum">Weeks postpartum (optional)</label>
                <input id="profile-weeks-postpartum" type="number" inputMode="numeric" min={0} value={profileWeeksPostpartum} onChange={(e) => setProfileWeeksPostpartum(e.target.value)} placeholder="e.g. 6" className="placeholder:text-[#D4B8B8] tabular-nums" style={profilePanelGlassInputStyle} />
              </>
            ) : null}

            <label className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }} htmlFor="profile-medications">Current medications</label>
            <textarea id="profile-medications" value={profileMedications} onChange={(e) => setProfileMedications(e.target.value)} placeholder="List any medications you're taking" rows={2} className="placeholder:text-[#D4B8B8]" style={{ ...profilePanelGlassInputStyle, height: 60, minHeight: 60, resize: 'none' }} />
            <label className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }} htmlFor="profile-allergies">Allergies</label>
            <textarea id="profile-allergies" value={profileAllergies} onChange={(e) => setProfileAllergies(e.target.value)} placeholder="List any known allergies" rows={2} className="placeholder:text-[#D4B8B8]" style={{ ...profilePanelGlassInputStyle, height: 40, minHeight: 40, resize: 'none' }} />
            <label className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }} htmlFor="profile-latest-visit">Latest doctor visit</label>
            <textarea id="profile-latest-visit" value={profileLatestVisit} onChange={(e) => setProfileLatestVisit(e.target.value)} placeholder="Latest doctor visit notes" rows={2} className="placeholder:text-[#D4B8B8]" style={{ ...profilePanelGlassInputStyle, height: 60, minHeight: 60, resize: 'none' }} />
          </div>

          <button type="button" className={`${glassPillButton} mt-8`} onClick={continueToRiskFactors}>Continue to heart risk questions →</button>
          {profileValidationMessage ? (
            <p className="mt-4 max-w-md text-center text-[12px] font-normal leading-snug text-[#E8B6B6]" style={{ fontFamily: dmSans }} role="alert">
              {profileValidationMessage}
            </p>
          ) : null}
          <button type="button" className="mt-6 cursor-pointer border-none bg-transparent p-0 text-[0.6875rem] font-normal text-[#9B7B7B] underline-offset-2 hover:underline" style={{ fontFamily: dmSans }} onClick={() => setSubStep('riskFactors')}>
            Skip for now
          </button>
        </motion.div>
      ) : (
        <motion.div key="risk-factors" className="flex w-full max-w-lg flex-col items-center pb-8" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.55, ease: easeSoftOut }}>
          <motion.h2 className="mb-8 text-center font-normal leading-snug text-[#FDF0F0]" style={{ fontFamily: dmSans, fontSize: 16 }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5, ease: easeSoftOut, delay: 0.06 }}>
            Let&apos;s understand your heart better.
          </motion.h2>

          <p className="mb-6 text-center text-[11px] font-normal text-[#9B7B7B]" style={{ fontFamily: dmSans }}>
            {pregnancyMode === 'prenatal' ? 'Prenatal pathway' : 'Postpartum pathway'}
          </p>

          <div className="flex w-full flex-col gap-4">
            {!profileAge.trim() ? (
              <div className="px-4 py-3" style={glassFieldCardStyle}>
                <label className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }} htmlFor="rf-age">How old are you?</label>
                <input id="rf-age" type="number" inputMode="numeric" min={0} className="tabular-nums" style={glassNumberInputStyle} value={riskFactors.age} onChange={(e) => setRiskFactors((d) => ({ ...d, age: e.target.value }))} />
              </div>
            ) : (
              <div className="px-4 py-3" style={glassFieldCardStyle}>
                <p className="text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }}>
                  Age from profile: {profileAge}
                </p>
              </div>
            )}

            <div className="px-4 py-3" style={glassFieldCardStyle}>
              <label className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }} htmlFor="rf-bmi">What is your pre-pregnancy BMI?</label>
              <input id="rf-bmi" type="number" inputMode="decimal" min={0} step="any" className="tabular-nums" style={glassNumberInputStyle} value={riskFactors.prepregnancyBmi} onChange={(e) => setRiskFactors((d) => ({ ...d, prepregnancyBmi: e.target.value }))} />
              <p className="mt-2 text-[11px] font-normal leading-snug text-[#9B7B7B]" style={{ fontFamily: dmSans }}>Ask your doctor if unsure</p>
            </div>

            <div className="px-4 py-3" style={glassFieldCardStyle}><span className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }}>Do you have chronic high blood pressure?</span><GlassYesNo value={riskFactors.chronicHypertension} onPick={(v) => setRiskFactors((d) => ({ ...d, chronicHypertension: v }))} /></div>
            <div className="px-4 py-3" style={glassFieldCardStyle}><span className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }}>Do you have diabetes?</span><GlassYesNo value={riskFactors.diabetes} onPick={(v) => setRiskFactors((d) => ({ ...d, diabetes: v }))} /></div>
            <div className="px-4 py-3" style={glassFieldCardStyle}><span className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }}>Have you had a preterm birth or stillbirth before?</span><GlassYesNo value={riskFactors.priorPretermOrStillbirth} onPick={(v) => setRiskFactors((d) => ({ ...d, priorPretermOrStillbirth: v }))} /></div>

            <div className="px-4 py-3" style={glassFieldCardStyle}>
              <label className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }} htmlFor="rf-live-births">How many live births have you had?</label>
              <input id="rf-live-births" type="number" inputMode="numeric" min={0} className="tabular-nums" style={glassNumberInputStyle} value={riskFactors.liveBirthsCount} onChange={(e) => setRiskFactors((d) => ({ ...d, liveBirthsCount: e.target.value }))} />
            </div>

            <div className="px-4 py-3" style={glassFieldCardStyle}><span className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }}>Did you smoke before or during pregnancy?</span><GlassYesNo value={riskFactors.smokedPregnancy} onPick={(v) => setRiskFactors((d) => ({ ...d, smokedPregnancy: v }))} /></div>
            <div className="px-4 py-3" style={glassFieldCardStyle}><span className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }}>Are you carrying more than one baby?</span><GlassYesNo value={riskFactors.multipleGestation} onPick={(v) => setRiskFactors((d) => ({ ...d, multipleGestation: v }))} /></div>

            {riskFactors.pregnancyMode === 'postpartum' ? (
              <>
                <div className="px-4 py-3" style={glassFieldCardStyle}><span className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }}>Did you develop high blood pressure during pregnancy?</span><GlassYesNo value={riskFactors.gestationalHypertension} onPick={(v) => setRiskFactors((d) => ({ ...d, gestationalHypertension: v }))} /></div>
                <div className="px-4 py-3" style={glassFieldCardStyle}><span className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }}>Did you develop gestational diabetes?</span><GlassYesNo value={riskFactors.gestationalDiabetes} onPick={(v) => setRiskFactors((d) => ({ ...d, gestationalDiabetes: v }))} /></div>
                <div className="px-4 py-3" style={glassFieldCardStyle}><span className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }}>Did you have any severe pregnancy complications?</span><GlassYesNo value={riskFactors.severeComplications} onPick={(v) => setRiskFactors((d) => ({ ...d, severeComplications: v }))} /><p className="mt-2 text-[11px] font-normal leading-snug text-[#9B7B7B]" style={{ fontFamily: dmSans }}>ICU stay, blood transfusion, or emergency surgery</p></div>
                <div className="px-4 py-3" style={glassFieldCardStyle}><span className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }}>Was your baby born before 37 weeks?</span><GlassYesNo value={riskFactors.birthBefore37Weeks} onPick={(v) => setRiskFactors((d) => ({ ...d, birthBefore37Weeks: v }))} /></div>
                <div className="px-4 py-3" style={glassFieldCardStyle}><span className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }}>Was your baby under 5.5 lbs at birth?</span><GlassYesNo value={riskFactors.birthUnder5_5lbs} onPick={(v) => setRiskFactors((d) => ({ ...d, birthUnder5_5lbs: v }))} /></div>
              </>
            ) : null}
          </div>

          <button type="button" className={`${glassPillButton} mt-8`} onClick={onSubmitRisk}>Check my heart risk →</button>
          {riskSubmitMessage ? (
            <p className="mt-4 max-w-md text-center text-[12px] font-normal leading-snug text-[#E8B6B6]" style={{ fontFamily: dmSans }}>
              {riskSubmitMessage}
            </p>
          ) : null}
          <button type="button" className="mt-6 cursor-pointer border-none bg-transparent p-0 text-[0.6875rem] font-normal text-[#9B7B7B] underline-offset-2 hover:underline" style={{ fontFamily: dmSans }} onClick={() => setDismiss(true)}>
            Skip for now.
          </button>
        </motion.div>
      )}
    </motion.div>
  )
}
