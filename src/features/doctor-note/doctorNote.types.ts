export type DoctorNoteOcrResult = {
  condition: string
  region: string
  risk: string
  description: string
  doctorScript: string
  questions: readonly string[]
}
