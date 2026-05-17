import type { DoctorNoteOcrResult } from './doctorNote.types'

export const MOCK_DOCTOR_NOTE_OCR: DoctorNoteOcrResult = {
  condition: 'Hypertension',
  region: 'Left Ventricle',
  risk: 'HIGH',
  description:
    'Your doctor noted high blood pressure. During pregnancy this puts extra strain on the left side of your heart which has to work harder to pump blood for both you and your baby.',
  doctorScript:
    'My blood pressure has been high. I want to discuss what this means for my heart health during my pregnancy and what warning signs I should watch for.',
  questions: [
    'What blood pressure range is safe during my pregnancy?',
    'Should I be monitoring my heart rate at home?',
    'Could this affect my baby?',
  ],
}
