import { type ChangeEvent, type RefObject } from 'react'
import { motion } from 'framer-motion'
import { dmSans, doctorNoteUploadZoneStyle, glassPillButton } from '../../shared/styles'
import { easeSoftOut } from '../../shared/animation'

type DoctorNoteUploadOverlayProps = {
  show: boolean
  doctorNoteFileInputRef: RefObject<HTMLInputElement | null>
  doctorNotePreviewUrl: string | null
  onDoctorNoteFileChange: (e: ChangeEvent<HTMLInputElement>) => void
  handleReadDoctorNote: () => void
  skipDoctorNoteToHeart: () => void
}

export function DoctorNoteUploadOverlay({
  show,
  doctorNoteFileInputRef,
  doctorNotePreviewUrl,
  onDoctorNoteFileChange,
  handleReadDoctorNote,
  skipDoctorNoteToHeart,
}: DoctorNoteUploadOverlayProps) {
  if (!show) return null

  return (
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
  )
}
