import type { ChangeEvent, RefObject } from 'react'
import DoctorNoteUploadPanel from '../features/doctor-note/DoctorNoteUploadPanel'
import type { DemoDoctorNoteRecord } from '../features/doctor-note/demoDoctorNotes'

type DoctorNoteRouteProps = {
  doctorNoteFileInputRef: RefObject<HTMLInputElement | null>
  doctorNotePreviewUrl: string | null
  demoDoctorNoteRecords: readonly DemoDoctorNoteRecord[]
  onDoctorNoteFileChange: (e: ChangeEvent<HTMLInputElement>) => void
  onReadDoctorNote: () => void
  onSelectDemoDoctorNote: (record: DemoDoctorNoteRecord) => void
  onSkip: () => void
}

export function DoctorNoteRoute(props: DoctorNoteRouteProps) {
  return <DoctorNoteUploadPanel {...props} show />
}
