import type { ChangeEvent, RefObject } from 'react'
import EcgUploadPanel from '../features/ecg/EcgUploadPanel'
import type {
  AppleWatchEcgInferResponse,
  AppleWatchEcgRecordSummary,
  AppleWatchEcgWindowPolicy,
} from '../types/ecg'

type EcgRouteProps = {
  ecgFileInputRef: RefObject<HTMLInputElement | null>
  ecgFile: File | null
  recordSummaries: AppleWatchEcgRecordSummary[]
  selectedRecordIndex: number
  parseError: string | null
  analysisError: string | null
  analysisResult: AppleWatchEcgInferResponse | null
  isAnalyzing: boolean
  windowPolicy: AppleWatchEcgWindowPolicy
  threshold: string
  onEcgFileChange: (e: ChangeEvent<HTMLInputElement>) => void
  onSelectedRecordIndexChange: (index: number) => void
  onWindowPolicyChange: (policy: AppleWatchEcgWindowPolicy) => void
  onThresholdChange: (threshold: string) => void
  onAnalyzeEcg: () => void
  onReset: () => void
  onSkip: () => void
}

export function EcgRoute(props: EcgRouteProps) {
  return <EcgUploadPanel {...props} show />
}
