import type { AnalysisResult } from '@/lib/api'

export type ChatMessage =
  | { id: string; role: 'user'; content: string }
  | { id: string; role: 'assistant'; content: string; result: AnalysisResult }

const STORAGE_PREFIX = 'processiq.analysis.chat.v1'

function storageKey(projectId: number | null | undefined) {
  return `${STORAGE_PREFIX}:${projectId ?? 'all'}`
}

export function loadAnalysisChat(projectId: number | null | undefined): ChatMessage[] {
  try {
    const raw = sessionStorage.getItem(storageKey(projectId))
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) return []
    return parsed.filter(isChatMessage)
  } catch {
    return []
  }
}

export function saveAnalysisChat(
  projectId: number | null | undefined,
  messages: ChatMessage[],
) {
  try {
    sessionStorage.setItem(storageKey(projectId), JSON.stringify(messages))
  } catch {
    // quota / private mode — sessizce yut
  }
}

export function clearAnalysisChat(projectId: number | null | undefined) {
  try {
    sessionStorage.removeItem(storageKey(projectId))
  } catch {
    // ignore
  }
}

function isChatMessage(value: unknown): value is ChatMessage {
  if (!value || typeof value !== 'object') return false
  const m = value as Record<string, unknown>
  if (typeof m.id !== 'string' || (m.role !== 'user' && m.role !== 'assistant')) return false
  if (m.role === 'user') return typeof m.content === 'string'
  return typeof m.content === 'string' && m.result != null && typeof m.result === 'object'
}

/** Sohbetteki tamamlanmış analiz çiftleri (yeniden açmak için). */
export function listSessionAnalyses(messages: ChatMessage[]) {
  const items: {
    id: string
    question: string
    title: string
    risk_level: string
    messageId: string
  }[] = []
  for (let i = 0; i < messages.length; i++) {
    const m = messages[i]
    if (m.role !== 'assistant') continue
    const prev = messages[i - 1]
    const question = prev?.role === 'user' ? prev.content : m.content
    items.push({
      id: m.id,
      question,
      title: m.result.analysis_type_label || m.result.title || 'Analiz',
      risk_level: m.result.risk_level,
      messageId: m.id,
    })
  }
  return items.reverse()
}
