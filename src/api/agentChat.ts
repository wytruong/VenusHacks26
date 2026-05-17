import type { AgentChatRequest, AgentChatResponse } from '../types/agentChat'
import { API_BASE_URL } from './screening'

const AGENT_CHAT_TIMEOUT_MS = 45_000

function createAgentChatRequestId() {
  return `agent-chat-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

export class AgentChatApiError extends Error {
  readonly userMessage: string

  constructor(userMessage: string) {
    super(userMessage)
    this.name = 'AgentChatApiError'
    this.userMessage = userMessage
  }
}

function isAgentChatResponse(data: unknown): data is AgentChatResponse {
  if (!data || typeof data !== 'object') return false
  const candidate = data as Record<string, unknown>

  return (
    typeof candidate.assistantText === 'string' &&
    typeof candidate.messageCount === 'number' &&
    typeof candidate.threadId === 'string'
  )
}

export async function submitAgentChat(payload: AgentChatRequest): Promise<AgentChatResponse> {
  let response: Response
  const requestId = createAgentChatRequestId()
  const startedAt = performance.now()
  const url = `${API_BASE_URL}/api/agents/chat`
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), AGENT_CHAT_TIMEOUT_MS)

  console.info('[agent-chat] request:start', {
    requestId,
    url,
    surface: payload.surface,
    sessionId: payload.sessionId,
    messageCount: payload.messages.length,
    hasDoctorNote: Boolean(payload.doctorNote),
  })

  try {
    response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Request-ID': requestId,
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
  } catch (error) {
    const elapsedMs = Math.round(performance.now() - startedAt)
    if (error instanceof DOMException && error.name === 'AbortError') {
      console.error('[agent-chat] request:timeout', { requestId, elapsedMs })
      throw new AgentChatApiError(
        'The chat service is taking too long to respond. Please try again shortly.',
      )
    }

    console.error('[agent-chat] request:network-error', { requestId, elapsedMs, error })
    throw new AgentChatApiError(
      'We could not connect to the chat service. Please try again shortly.',
    )
  } finally {
    window.clearTimeout(timeoutId)
  }

  console.info('[agent-chat] request:response', {
    requestId,
    status: response.status,
    ok: response.ok,
    elapsedMs: Math.round(performance.now() - startedAt),
  })

  if (response.status === 422) {
    throw new AgentChatApiError('Please enter a question before sending.')
  }

  if (response.status === 503) {
    throw new AgentChatApiError(
      'The chat service is temporarily unavailable. Please try again later or ask your care team.',
    )
  }

  if (!response.ok) {
    throw new AgentChatApiError(
      'We could not answer that question right now. Please try again shortly.',
    )
  }

  const data: unknown = await response.json()

  if (!isAgentChatResponse(data)) {
    console.error('[agent-chat] request:invalid-response', { requestId, data })
    throw new AgentChatApiError(
      'We received an unexpected chat response. Please try again later.',
    )
  }

  console.info('[agent-chat] request:success', {
    requestId,
    threadId: data.threadId,
    messageCount: data.messageCount,
    elapsedMs: Math.round(performance.now() - startedAt),
  })

  return data
}
