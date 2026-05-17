import type { ChangeEvent, RefObject } from 'react'
import DoctorNoteUploadPanel from '../features/doctor-note/DoctorNoteUploadPanel'

type DoctorNoteRouteProps = {
  doctorNoteFileInputRef: RefObject<HTMLInputElement | null>
  doctorNotePreviewUrl: string | null
  onDoctorNoteFileChange: (e: ChangeEvent<HTMLInputElement>) => void
  onReadDoctorNote: () => void
  onSkip: () => void
}

export function DoctorNoteRoute(props: DoctorNoteRouteProps) {
  return <DoctorNoteUploadPanel {...props} show />
}
