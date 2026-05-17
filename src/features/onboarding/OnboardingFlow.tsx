import { type Dispatch, type SetStateAction } from 'react'
import { motion } from 'framer-motion'
import { dmSans, glassFieldCardStyle, glassNumberInputStyle, glassPillButton, glassTogglePill } from '../../shared/styles'
import { easeSoftOut, ONBOARDING_EXIT_DURATION_S } from '../../shared/animation'
import type { RiskFactors } from '../risk-profile/riskProfile.types'

type OnboardingSubStep = 'question' | 'pregnancyStage' | 'riskFactors'

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
}: OnboardingFlowProps) {
  if (!show) return null

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
                setSubStep('riskFactors')
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
                setSubStep('riskFactors')
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
      ) : (
        <motion.div key="risk-factors" className="flex w-full max-w-lg flex-col items-center pb-8" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.55, ease: easeSoftOut }}>
          <motion.h2 className="mb-8 text-center font-normal leading-snug text-[#FDF0F0]" style={{ fontFamily: dmSans, fontSize: 16 }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5, ease: easeSoftOut, delay: 0.06 }}>
            Let&apos;s understand your heart better.
          </motion.h2>

          <p className="mb-6 text-center text-[11px] font-normal text-[#9B7B7B]" style={{ fontFamily: dmSans }}>
            {pregnancyMode === 'prenatal' ? 'Prenatal pathway' : 'Postpartum pathway'}
          </p>

          <div className="flex w-full flex-col gap-4">
            <div className="px-4 py-3" style={glassFieldCardStyle}>
              <label className="block text-sm font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans }} htmlFor="rf-age">How old are you?</label>
              <input id="rf-age" type="number" inputMode="numeric" min={0} className="tabular-nums" style={glassNumberInputStyle} value={riskFactors.age} onChange={(e) => setRiskFactors((d) => ({ ...d, age: e.target.value }))} />
            </div>

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
