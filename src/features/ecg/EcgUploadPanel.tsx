import type { ChangeEvent, RefObject } from 'react'
import { motion } from 'framer-motion'
import { easeSoftOut } from '../../shared/animation'
import { dmSans, doctorNoteUploadZoneStyle, glassPillButton } from '../../shared/styles'
import type {
  AppleWatchEcgInferResponse,
  AppleWatchEcgRecordSummary,
  AppleWatchEcgWindowPolicy,
} from '../../types/ecg'

function EcgHeartGlyph({ className }: { className?: string }) {
  return (
    <svg className={className} width={20} height={18} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
    </svg>
  )
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

function formatRecordLabel(summary: AppleWatchEcgRecordSummary) {
  return `Record ${summary.index + 1}`
}

function RecordSummaryDetails({ summary }: { summary: AppleWatchEcgRecordSummary }) {
  return (
    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] font-normal text-[#9B7B7B]">
      {summary.start ? <span>Start: {summary.start}</span> : null}
      {summary.end ? <span>End: {summary.end}</span> : null}
      {summary.classification ? <span>Classification: {summary.classification}</span> : null}
      {summary.samplingFrequency ? <span>Sampling: {summary.samplingFrequency}</span> : null}
      {summary.averageHeartRate ? <span>Avg HR: {summary.averageHeartRate}</span> : null}
      <span>{summary.voltageMeasurementCount.toLocaleString()} voltage samples</span>
    </div>
  )
}

type EcgUploadPanelProps = {
  show: boolean
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

export default function EcgUploadPanel({
  show,
  ecgFileInputRef,
  ecgFile,
  recordSummaries,
  selectedRecordIndex,
  parseError,
  analysisError,
  analysisResult,
  isAnalyzing,
  windowPolicy,
  threshold,
  onEcgFileChange,
  onSelectedRecordIndexChange,
  onWindowPolicyChange,
  onThresholdChange,
  onAnalyzeEcg,
  onReset,
  onSkip,
}: EcgUploadPanelProps) {
  if (!show) return null

  const selectedSummary = recordSummaries.find((summary) => summary.index === selectedRecordIndex)
  const canAnalyze = Boolean(ecgFile && selectedSummary && !parseError && !isAnalyzing)

  return (
    <motion.div key="ecg-upload" className="fixed inset-0 z-[42] flex flex-col items-center justify-center overflow-y-auto px-6 py-16" style={{ backgroundColor: '#1A0A0A' }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.45, ease: easeSoftOut }}>
      <motion.h2 className="mb-3 max-w-xl text-center font-normal leading-snug text-[#FDF0F0]" style={{ fontFamily: dmSans, fontSize: 16 }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.55, ease: easeSoftOut, delay: 0.08 }}>
        Upload your Apple Watch ECG export.
      </motion.h2>

      <p className="mb-8 max-w-md text-center font-normal leading-snug text-[#9B7B7B]" style={{ fontFamily: dmSans, fontSize: 12 }}>
        Choose a Health Auto Export JSON file, select the ECG record to analyze, and view experimental model probabilities.
      </p>

      <input ref={ecgFileInputRef} type="file" accept=".json,application/json" className="sr-only" aria-hidden tabIndex={-1} onChange={onEcgFileChange} />

      <div
        role="button"
        tabIndex={0}
        aria-label="Choose Apple Watch ECG JSON file"
        className="flex cursor-pointer flex-col items-center justify-center px-4 outline-none transition-[opacity] duration-300 focus-visible:ring-2 focus-visible:ring-[#F4C2C2]/60"
        style={doctorNoteUploadZoneStyle}
        onClick={() => ecgFileInputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            ecgFileInputRef.current?.click()
          }
        }}
      >
        {ecgFile ? (
          <div className="max-w-[340px] text-center">
            <EcgHeartGlyph className="mx-auto mb-2 text-[#F4C2C2]" />
            <p className="truncate font-normal text-[#FDF0F0]" style={{ fontFamily: dmSans, fontSize: 12 }} title={ecgFile.name}>
              {ecgFile.name}
            </p>
            <p className="mt-2 font-normal text-[#9B7B7B]" style={{ fontFamily: dmSans, fontSize: 11 }}>
              {recordSummaries.length > 0 ? `${recordSummaries.length} ECG record${recordSummaries.length === 1 ? '' : 's'} found` : 'Waiting for a valid ECG record'}
            </p>
          </div>
        ) : (
          <>
            <EcgHeartGlyph className="mb-2 shrink-0 text-[#9B7B7B]" />
            <p className="max-w-[260px] text-center font-normal leading-snug text-[#9B7B7B]" style={{ fontFamily: dmSans, fontSize: 12 }}>
              Tap to upload Apple Watch ECG JSON
            </p>
          </>
        )}
      </div>

      {parseError ? (
        <p className="mt-4 max-w-md text-center font-normal leading-snug text-[#F4C2C2]" style={{ fontFamily: dmSans, fontSize: 12 }}>
          {parseError}
        </p>
      ) : null}

      {recordSummaries.length > 0 ? (
        <div className="mt-6 w-full max-w-2xl" style={{ fontFamily: dmSans }}>
          <h3 className="mb-3 text-center text-[12px] font-normal uppercase tracking-[0.18em] text-[#F4C2C2]">
            Select ECG record
          </h3>
          <div className="grid max-h-[24vh] gap-3 overflow-y-auto pr-1">
            {recordSummaries.map((summary) => {
              const selected = summary.index === selectedRecordIndex
              return (
                <button key={summary.index} type="button" className={`cursor-pointer rounded-2xl border p-4 text-left transition-[background-color,border-color] duration-300 ${selected ? 'border-[#F4C2C2]/70 bg-white/[0.1]' : 'border-white/15 bg-white/[0.06] hover:border-[#F4C2C2]/55 hover:bg-white/[0.1]'}`} onClick={() => onSelectedRecordIndexChange(summary.index)}>
                  <div className="font-normal text-[#FDF0F0]" style={{ fontSize: 13 }}>
                    {formatRecordLabel(summary)}
                  </div>
                  <RecordSummaryDetails summary={summary} />
                </button>
              )
            })}
          </div>
        </div>
      ) : null}

      {selectedSummary ? (
        <div className="mt-6 w-full max-w-2xl rounded-2xl border border-white/15 bg-white/[0.06] p-4" style={{ fontFamily: dmSans }}>
          <div className="flex flex-wrap items-end gap-4">
            <label className="flex flex-col gap-2 text-[11px] font-normal uppercase tracking-[0.16em] text-[#F4C2C2]">
              Window policy
              <select className="rounded-full border border-white/20 bg-[#2A1212] px-4 py-2 text-[12px] normal-case tracking-normal text-[#FDF0F0] outline-none focus-visible:ring-2 focus-visible:ring-[#F4C2C2]/60" value={windowPolicy} onChange={(e) => onWindowPolicyChange(e.target.value as AppleWatchEcgWindowPolicy)}>
                <option value="first">First window</option>
                <option value="sliding">Sliding windows</option>
              </select>
            </label>
            <label className="flex flex-col gap-2 text-[11px] font-normal uppercase tracking-[0.16em] text-[#F4C2C2]">
              Threshold
              <input className="w-28 rounded-full border border-white/20 bg-transparent px-4 py-2 text-[12px] normal-case tracking-normal text-[#FDF0F0] outline-none focus-visible:ring-2 focus-visible:ring-[#F4C2C2]/60" type="number" min="0" max="1" step="0.01" value={threshold} onChange={(e) => onThresholdChange(e.target.value)} />
            </label>
          </div>
        </div>
      ) : null}

      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        <button type="button" disabled={!canAnalyze} className={`${glassPillButton} ${!canAnalyze ? 'pointer-events-none opacity-35' : 'opacity-100'}`} style={{ fontFamily: dmSans }} onClick={onAnalyzeEcg}>
          {isAnalyzing ? 'Analyzing ECG...' : 'Analyze my ECG →'}
        </button>
        {ecgFile ? (
          <button type="button" className={glassPillButton} style={{ fontFamily: dmSans }} onClick={onReset}>
            Choose another file
          </button>
        ) : null}
      </div>

      {analysisError ? (
        <p className="mt-4 max-w-md text-center font-normal leading-snug text-[#F4C2C2]" style={{ fontFamily: dmSans, fontSize: 12 }}>
          {analysisError}
        </p>
      ) : null}

      {analysisResult ? <EcgResultPanel result={analysisResult} /> : null}

      <button type="button" className="mt-6 cursor-pointer border-none bg-transparent p-0 text-[12px] font-normal text-[#9B7B7B] underline underline-offset-2" style={{ fontFamily: dmSans }} onClick={onSkip}>
        Skip for now
      </button>
    </motion.div>
  )
}

function EcgResultPanel({ result }: { result: AppleWatchEcgInferResponse }) {
  return (
    <div className="mt-6 w-full max-w-3xl rounded-2xl border border-white/15 bg-white/[0.06] p-4" style={{ fontFamily: dmSans }}>
      <div className="mb-4">
        <h3 className="m-0 font-normal text-[#FDF0F0]" style={{ fontSize: 16 }}>
          Model probability output
        </h3>
        <p className="mt-2 font-normal leading-snug text-[#F4C2C2]" style={{ fontSize: 12 }}>
          {result.caveat}
        </p>
        <p className="mt-2 font-normal leading-snug text-[#9B7B7B]" style={{ fontSize: 11 }}>
          Record {result.record_index + 1} · {result.window_policy} · threshold {result.threshold} · {result.target_samples.toLocaleString()} target samples · {result.checkpoint_sampling_rate_hz} Hz · {result.duration_sec}s windows
        </p>
      </div>

      <div className="grid gap-3">
        {result.predictions.map((prediction) => (
          <div key={prediction.window_index} className="rounded-2xl border border-white/15 bg-black/10 p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-[13px] font-normal text-[#FDF0F0]">Window {prediction.window_index + 1}</div>
                <div className="mt-1 text-[11px] font-normal text-[#9B7B7B]">
                  Samples {prediction.window_start_sample.toLocaleString()}-{prediction.window_end_sample.toLocaleString()}
                </div>
              </div>
              <div className="text-right">
                <div className="text-[12px] font-normal text-[#F4C2C2]">{formatPercent(prediction.prob_any_abnormal)}</div>
                <div className="mt-1 text-[11px] font-normal text-[#9B7B7B]">
                  {prediction.pred_any_abnormal ? 'Above threshold' : 'Below threshold'}
                </div>
              </div>
            </div>

            <div className="mb-3 flex flex-wrap gap-2">
              {prediction.labels_above_threshold.length > 0 ? (
                prediction.labels_above_threshold.map((label) => (
                  <span key={label} className="rounded-full border border-[#F4C2C2]/40 px-3 py-1 text-[11px] font-normal text-[#F4C2C2]">
                    {label.replaceAll('_', ' ')}
                  </span>
                ))
              ) : (
                <span className="text-[11px] font-normal text-[#9B7B7B]">No labels above threshold</span>
              )}
            </div>

            <div className="grid gap-2 sm:grid-cols-2">
              {result.target_names.map((targetName) => (
                <div key={targetName} className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2">
                  <div className="text-[11px] font-normal text-[#D4B8B8]">{targetName.replaceAll('_', ' ')}</div>
                  <div className="mt-1 text-[12px] font-normal text-[#FDF0F0]">{formatPercent(prediction.probabilities[targetName] ?? 0)}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <details className="mt-4 rounded-2xl border border-white/15 bg-black/10 p-4">
        <summary className="cursor-pointer text-[12px] font-normal text-[#F4C2C2]">Raw model response</summary>
        <pre className="mt-3 max-h-[36vh] overflow-auto whitespace-pre-wrap break-words rounded-xl bg-black/20 p-3 text-[11px] leading-relaxed text-[#D4B8B8]">
          {JSON.stringify(result, null, 2)}
        </pre>
      </details>
    </div>
  )
}
