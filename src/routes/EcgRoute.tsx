import type { ChangeEvent, RefObject } from 'react'
import EcgUploadPanel from '../features/ecg/EcgUploadPanel'

type EcgRouteProps = {
  ecgFileInputRef: RefObject<HTMLInputElement | null>
  ecgFile: File | null
  onEcgFileChange: (e: ChangeEvent<HTMLInputElement>) => void
  onAnalyzeEcg: () => void
  onSkip: () => void
}

export function EcgRoute(props: EcgRouteProps) {
  return <EcgUploadPanel {...props} show />
}
