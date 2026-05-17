import type {
  AppleWatchEcgRecord,
  AppleWatchEcgRecordSummary,
  AppleWatchHealthExportPayload,
  ParsedAppleWatchEcgUpload,
} from '../../types/ecg'

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function finitePositiveNumber(value: unknown): number | null {
  const parsed = typeof value === 'number' || typeof value === 'string' ? Number(value) : NaN
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

function optionalText(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined
  const trimmed = value.trim()
  return trimmed || undefined
}

function optionalDisplayValue(value: unknown): string | undefined {
  if (value === null || value === undefined) return undefined
  if (typeof value === 'string') return value.trim() || undefined
  if (typeof value === 'number' && Number.isFinite(value)) return String(value)
  return undefined
}

export function hasVoltageMeasurements(value: unknown): value is AppleWatchEcgRecord {
  if (!isRecord(value)) return false
  if (!Array.isArray(value.voltageMeasurements) || value.voltageMeasurements.length === 0) {
    return false
  }
  return finitePositiveNumber(value.samplingFrequency) !== null
}

function healthExportFrom(value: unknown): AppleWatchHealthExportPayload | null {
  if (!isRecord(value) || !isRecord(value.data) || !Array.isArray(value.data.ecg)) {
    return null
  }
  if (value.data.ecg.length === 0) return null
  if (!value.data.ecg.every(hasVoltageMeasurements)) return null
  return value as AppleWatchHealthExportPayload
}

export function summarizeAppleWatchEcgRecord(
  record: AppleWatchEcgRecord,
  index: number,
): AppleWatchEcgRecordSummary {
  const samplingFrequency = optionalDisplayValue(record.samplingFrequency)
  const averageHeartRate = optionalDisplayValue(record.averageHeartRate)

  return {
    index,
    start: optionalText(record.start),
    end: optionalText(record.end),
    classification: optionalText(record.classification),
    averageHeartRate,
    samplingFrequency: samplingFrequency ? `${samplingFrequency} Hz` : undefined,
    voltageMeasurementCount: record.voltageMeasurements.length,
  }
}

export function parseAppleWatchEcgUpload(data: unknown): ParsedAppleWatchEcgUpload {
  if (!isRecord(data)) {
    throw new Error('Upload a valid Apple Watch ECG JSON export.')
  }

  const wrappedHealthExport = healthExportFrom(data.healthExport)
  if (wrappedHealthExport) {
    return {
      kind: 'healthExport',
      healthExport: wrappedHealthExport,
      recordSummaries: wrappedHealthExport.data.ecg.map(summarizeAppleWatchEcgRecord),
    }
  }

  const directHealthExport = healthExportFrom(data)
  if (directHealthExport) {
    return {
      kind: 'healthExport',
      healthExport: directHealthExport,
      recordSummaries: directHealthExport.data.ecg.map(summarizeAppleWatchEcgRecord),
    }
  }

  const wrappedRecord = data.ecgRecord
  if (hasVoltageMeasurements(wrappedRecord)) {
    return {
      kind: 'ecgRecord',
      ecgRecord: wrappedRecord,
      recordSummaries: [summarizeAppleWatchEcgRecord(wrappedRecord, 0)],
    }
  }

  if (hasVoltageMeasurements(data)) {
    return {
      kind: 'ecgRecord',
      ecgRecord: data,
      recordSummaries: [summarizeAppleWatchEcgRecord(data, 0)],
    }
  }

  throw new Error(
    'We could not find ECG records with samplingFrequency and voltageMeasurements in this JSON file.',
  )
}
