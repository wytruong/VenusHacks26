import type { DoctorNoteOcrResult } from '../features/doctor-note/doctorNote.types'

export type AgentChatMessage = {
  role: 'assistant' | 'user'
  content: string
}

export type AgentChatRequest = {
  sessionId: string
  surface: 'general_health_companion' | 'maternal_risk'
  messages: AgentChatMessage[]
  doctorNote?: DoctorNoteOcrResult
  doctorNoteScreening?: DoctorNoteOcrResult['screening']
}

export type AgentChatResponse = {
  assistantText: string
  messageCount: number
  threadId: string
}
