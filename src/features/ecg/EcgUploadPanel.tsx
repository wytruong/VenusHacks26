import type { ChangeEvent, RefObject } from 'react'
import { motion } from 'framer-motion'
import { easeSoftOut } from '../../shared/animation'
import { dmSans, ecgUploadZoneStyle, glassPillButton } from '../../shared/styles'

function EcgHeartGlyph({ className }: { className?: string }) {
  return (
    <svg className={className} width={20} height={18} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
    </svg>
  )
}

type EcgUploadPanelProps = {
  show: boolean
  ecgFileInputRef: RefObject<HTMLInputElement | null>
  ecgFile: File | null
  onEcgFileChange: (e: ChangeEvent<HTMLInputElement>) => void
  onAnalyzeEcg: () => void
  onSkip: () => void
}

export default function EcgUploadPanel({ show, ecgFileInputRef, ecgFile, onEcgFileChange, onAnalyzeEcg, onSkip }: EcgUploadPanelProps) {
  if (!show) return null

  return (
    <motion.div key="ecg-upload" className="fixed inset-0 z-[42] flex flex-col items-center justify-center overflow-y-auto px-6 py-16" style={{ backgroundColor: '#1A0A0A' }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.45, ease: easeSoftOut }}>
      <motion.h2 className="mb-3 max-w-xl text-center font-normal leading-snug text-[#FDF0F0]" style={{ fontFamily: dmSans, fontSize: 16 }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.65, ease: easeSoftOut, delay: 0.06 }}>
        Upload your ECG file.
      </motion.h2>

      <p className="mb-8 max-w-md text-center font-normal leading-snug text-[#9B7B7B]" style={{ fontFamily: dmSans, fontSize: 12 }}>
        Export your ECG from Apple Health and upload it here.
      </p>

      <input ref={ecgFileInputRef} type="file" accept=".pdf,.csv,application/pdf,text/csv" className="sr-only" aria-hidden tabIndex={-1} onChange={onEcgFileChange} />

      <div
        role="button"
        tabIndex={0}
        aria-label="Choose ECG file"
        className="flex max-w-full cursor-pointer flex-col items-center justify-center px-4 outline-none transition-opacity duration-300 focus-visible:ring-2 focus-visible:ring-[#F4C2C2]/60"
        style={ecgUploadZoneStyle}
        onClick={() => ecgFileInputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            ecgFileInputRef.current?.click()
          }
        }}
      >
        {ecgFile ? (
          <p className="max-w-[340px] truncate text-center font-normal text-[#9B7B7B]" style={{ fontFamily: dmSans, fontSize: 12 }} title={ecgFile.name}>
            {ecgFile.name}
          </p>
        ) : (
          <>
            <EcgHeartGlyph className="mb-2 shrink-0 text-[#9B7B7B]" />
            <p className="max-w-[280px] text-center font-normal leading-snug text-[#9B7B7B]" style={{ fontFamily: dmSans, fontSize: 12 }}>
              Tap to upload your ECG file
            </p>
          </>
        )}
      </div>

      <button type="button" disabled={!ecgFile} className={`${glassPillButton} mt-8 ${!ecgFile ? 'pointer-events-none cursor-not-allowed opacity-35' : 'cursor-pointer opacity-100'}`} style={{ fontFamily: dmSans }} onClick={onAnalyzeEcg}>
        Analyze my ECG →
      </button>

      <button type="button" className="mt-6 cursor-pointer border-none bg-transparent p-0 text-[12px] font-normal text-[#9B7B7B] underline-offset-4 hover:underline" style={{ fontFamily: dmSans }} onClick={onSkip}>
        Skip for now
      </button>
    </motion.div>
  )
}
