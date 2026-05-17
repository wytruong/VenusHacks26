import { useState, type ChangeEvent, type RefObject } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { easeSoftOut } from '../../shared/animation'
import { dmSans, doctorNoteUploadZoneStyle, glassPillButton } from '../../shared/styles'
import type { DemoDoctorNoteRecord } from './demoDoctorNotes'

type DoctorNoteUploadPanelProps = {
  show: boolean
  doctorNoteFileInputRef: RefObject<HTMLInputElement | null>
  doctorNotePreviewUrl: string | null
  demoDoctorNoteRecords: readonly DemoDoctorNoteRecord[]
  onDoctorNoteFileChange: (e: ChangeEvent<HTMLInputElement>) => void
  onReadDoctorNote: () => void
  onSelectDemoDoctorNote: (record: DemoDoctorNoteRecord) => void
  onSkip: () => void
}

export default function DoctorNoteUploadPanel({ show, doctorNoteFileInputRef, doctorNotePreviewUrl, demoDoctorNoteRecords, onDoctorNoteFileChange, onReadDoctorNote, onSelectDemoDoctorNote, onSkip }: DoctorNoteUploadPanelProps) {
  const [showDemoRecords, setShowDemoRecords] = useState(false)

  if (!show) return null

  return (
    <motion.div key="doctor-note-upload" className="fixed inset-0 z-[42] flex flex-col items-center justify-center overflow-y-auto px-6 py-16" style={{ backgroundColor: '#1A0A0A' }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.45, ease: easeSoftOut }}>
      <motion.h2 className="mb-8 text-center font-normal leading-snug text-[#FDF0F0]" style={{ fontFamily: dmSans, fontSize: 16 }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.55, ease: easeSoftOut, delay: 0.08 }}>
        Upload your doctor&apos;s note.
      </motion.h2>

      <input ref={doctorNoteFileInputRef} type="file" accept="image/*" className="sr-only" aria-hidden tabIndex={-1} onChange={onDoctorNoteFileChange} />

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
          <img src={doctorNotePreviewUrl} alt="Doctor note preview" className="max-h-[210px] max-w-full rounded-lg object-contain" draggable={false} />
        ) : (
          <>
            <span className="mb-2 text-2xl" aria-hidden>
              📷
            </span>
            <p className="max-w-[260px] text-center font-normal leading-snug text-[#9B7B7B]" style={{ fontFamily: dmSans, fontSize: 12 }}>
              Take a photo or upload your note
            </p>
          </>
        )}
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <button type="button" disabled={!doctorNotePreviewUrl} className={`${glassPillButton} ${!doctorNotePreviewUrl ? 'pointer-events-none opacity-35' : 'opacity-100'}`} style={{ fontFamily: dmSans }} onClick={onReadDoctorNote}>
          Read my note →
        </button>
        <button type="button" className={glassPillButton} style={{ fontFamily: dmSans }} onClick={() => setShowDemoRecords(true)}>
          Demo - Real Doc Note
        </button>
      </div>

      <button type="button" className="mt-6 cursor-pointer border-none bg-transparent p-0 text-[12px] font-normal text-[#9B7B7B] underline underline-offset-2" style={{ fontFamily: dmSans }} onClick={onSkip}>
        Skip for now
      </button>

      <AnimatePresence>
        {showDemoRecords ? (
          <motion.div key="demo-doctor-note-records" className="fixed inset-0 z-[43] flex items-center justify-center overflow-y-auto px-5 py-10" style={{ backgroundColor: 'rgba(26,10,10,0.94)' }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.3, ease: easeSoftOut }}>
            <motion.div className="w-full max-w-3xl" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 12 }} transition={{ duration: 0.35, ease: easeSoftOut }}>
              <div className="mb-5 flex items-start justify-between gap-4">
                <div>
                  <h3 className="m-0 font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans, fontSize: 18 }}>
                    Demo doctor-note threads
                  </h3>
                  <p className="mt-2 max-w-2xl font-normal leading-snug text-[#9B7B7B]" style={{ fontFamily: dmSans, fontSize: 12 }}>
                    This prototype mode loads {demoDoctorNoteRecords.length} translated obstetric EHR notes from backend/data/external/mendeley-obstetric-maternal-ehr/demo_doctor_notes_50_translated.csv so demonstrators can choose a realistic record and test the follow-up chat flow without uploading an image.
                  </p>
                </div>
                <button type="button" className="shrink-0 cursor-pointer border-none bg-transparent p-0 text-[12px] font-normal text-[#F4C2C2] underline underline-offset-2" style={{ fontFamily: dmSans }} onClick={() => setShowDemoRecords(false)}>
                  Close
                </button>
              </div>

              <div className="grid max-h-[68vh] gap-3 overflow-y-auto pr-1">
                {demoDoctorNoteRecords.map((record) => (
                  <button key={record.demoId} type="button" className="cursor-pointer rounded-2xl border border-white/15 bg-white/[0.06] p-4 text-left transition-[background-color,border-color] duration-300 hover:border-[#F4C2C2]/55 hover:bg-white/[0.1]" style={{ fontFamily: dmSans }} onClick={() => onSelectDemoDoctorNote(record)}>
                    <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px] font-normal text-[#F4C2C2]">
                      <span>{record.demoId}</span>
                      <span>Patient {record.patientId}</span>
                      <span>{record.noteDate}</span>
                      <span>{record.group === 'cv_risk' ? 'CV risk' : 'Control'}</span>
                    </div>
                    <div className="font-normal text-[#FDF0F0]" style={{ fontSize: 13 }}>
                      {record.noteTitle || record.category}
                    </div>
                    <p className="m-0 mt-2 line-clamp-4 font-normal leading-snug text-[#D4B8B8]" style={{ fontSize: 12 }}>
                      {record.englishDemoNote}
                    </p>
                    <p className="m-0 mt-2 font-normal text-[#9B7B7B]" style={{ fontSize: 11 }}>
                      Codes: {record.conditionCodes || 'not listed'} · Category: {record.category.replaceAll('_', ' ')}
                    </p>
                  </button>
                ))}
              </div>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.div>
  )
}
