const BASE = ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export type Finding = { id: string; note?: string; text?: string }

export type DashboardData = {
  cards: {
    active_projects: number
    delayed_tasks: number
    failed_tests: number
    critical_bugs: number
    risky_releases: number
    recent_commits_14d: number
  }
  last_updated?: string | null
  charts: {
    release_risk_distribution: { label: string; count: number }[]
    release_counts?: {
      total: number
      not_released: number
      risky: number
    }
    test_pass_rate: number
    test_counts: { passed: number; failed: number; skipped: number; total: number }
    delay_reasons: {
      reason: string
      count: number
      metric?: string
      verify?: Record<string, string>
    }[]
    risk_trend_14d: {
      period: string
      period_label?: string
      period_start?: string
      period_end?: string
      risk_index: number
      risk_level?: string
      failed_tests: number
      critical_bugs?: number
      delayed_tasks?: number
    }[]
    risk_trend_insight?: {
      period?: string
      period_label?: string
      period_start?: string
      period_end?: string
      kind: string
      text: string
      risk_index?: number
      risk_level?: string
      failed_tests?: number
      critical_bugs?: number
      delayed_tasks?: number
      verify?: {
        tests?: Record<string, string | number>
        bugs?: Record<string, string | number>
        tasks?: Record<string, string | number>
      }
    } | null
  }
  card_links?: Record<string, { path: string; query?: Record<string, string> }>
  recent_analyses: {
    id?: number
    title: string
    question?: string
    risk_level: string
    summary: string
    created_at: string | null
  }[]
}

export type AnalysisResult = {
  risk_level: string
  title: string
  summary: string
  conclusion?: string
  findings?: string[]
  analysis_type?: string
  analysis_type_label?: string
  focus_entity?: string | null
  modules_used?: string[]
  impact_chain?: { kind: string; label: string; count: number }[]
  related_records?: Finding[]
  summary_stats?: Record<string, number | string>
  intent?: string
  risk_reasons: Array<string | Finding>
  affected_requirements?: Finding[]
  delayed_tasks?: Finding[]
  failed_tests?: Finding[]
  critical_bugs?: Finding[]
  affected_releases: Array<string | Finding>
  affected_records?: Finding[]
  affected_items?: Finding[]
  recommended_actions: string[]
  metrics: Record<string, number | string>
  data_sources?: {
    requirements?: number
    tasks?: number
    commits?: number
    tests?: number
    bugs?: number
    releases?: number
  }
  tools_used: { tool: string; args: Record<string, unknown>; count?: number }[]
  mode: string
  note?: string
}

export type AnalysisHistoryTurn = {
  role: 'user' | 'assistant'
  content: string
  focus_entity?: string | null
  intent?: string | null
  summary?: string | null
}

export type PromptCard = {
  id: string
  title: string
  prompt: string
}

export type AiNotification = {
  id: string
  category: string
  category_label: string
  category_emoji: string
  priority: number
  title: string
  /** Tek satırlık tetikleyici açıklaması */
  trigger?: string
  analysis: string
  triggers: { label: string; value: string }[]
  recommended_action: string
  related_records: Finding[]
  affected?: Partial<
    Record<'releases' | 'tests' | 'tasks' | 'requirements' | 'bugs' | 'commits', number>
  >
  confidence?: number
  deepen_prompt?: string
  focus_entity?: string | null
  created_at: string
}

export type ExecutiveSummary = {
  generated_at: string
  last_updated?: string | null
  period: 'today' | 'week' | 'month'
  period_label: string
  period_start: string
  period_end: string
  period_range_label?: string
  records_scanned: number
  confidence?: number
  project_id?: number | null
  project_name?: string | null
  project_code?: string | null
  overview: {
    completed_tasks: number
    new_bugs: number
    failed_tests: number
    commits?: number
    changed_requirements?: number
    release_status: string
    quality_score: number
    quality_label: string
    quality_assessment: string
  }
  critical_developments: { title: string; detail: string }[]
  assessment: string
  recommendations: string[]
  priorities?: string[]
  trends: {
    period_label: string
    current_period_label?: string
    commentary?: string
    failed_tests: TrendMetric
    critical_bugs: TrendMetric
    completed_tasks: TrendMetric
    quality_score: TrendMetric
  }
  focus_entities?: string[]
}

export type TrendMetric = {
  current: number
  previous: number
  delta: string
  abs_change?: number
  pct_change?: number | null
  change_display?: string
  direction: 'up' | 'down' | 'flat'
  higher_is_bad?: boolean
}

export type NotificationsResponse = {
  generated_at: string | null
  count: number
  summary?: {
    records_scanned: number
    notifications_created: number
    critical_count: number
    text: string
  }
  items: AiNotification[]
}

export type ProcessNode = {
  kind: string
  id: string
  title: string
  status: string
  severity: string
  reason?: string | null
}

export type ProcessChain = {
  requirement_id: string
  project: string | null
  project_code?: string | null
  release_version?: string | null
  severity: string
  score: number
  nodes: ProcessNode[]
}

export const api = {
  dashboard: (projectId?: number | null) =>
    request<DashboardData>(
      `/api/dashboard${projectId != null ? `?project_id=${projectId}` : ''}`,
    ),
  lastUpdated: (projectId?: number | null, scope = 'all') => {
    const params = new URLSearchParams({ scope })
    if (projectId != null) params.set('project_id', String(projectId))
    return request<{ last_updated: string | null; scope: string }>(
      `/api/last-updated?${params}`,
    )
  },
  projects: (params?: string) => request<Record<string, unknown>[]>(`/api/projects${params ?? ''}`),
  requirements: (q = '') => request<Record<string, unknown>[]>(`/api/requirements${q}`),
  tasks: (q = '') => request<Record<string, unknown>[]>(`/api/tasks${q}`),
  commits: (q = '') => request<Record<string, unknown>[]>(`/api/commits${q}`),
  tests: (q = '') => request<Record<string, unknown>[]>(`/api/tests${q}`),
  bugs: (q = '') => request<Record<string, unknown>[]>(`/api/bugs${q}`),
  releases: (q = '') => request<Record<string, unknown>[]>(`/api/releases${q}`),
  processChains: (limit = 12, projectId?: number | null) =>
    request<ProcessChain[]>(
      `/api/process-chains?limit=${limit}${projectId != null ? `&project_id=${projectId}` : ''}`,
    ),
  prompts: () => request<PromptCard[]>('/api/analysis/prompts'),
  notifications: (projectId?: number | null, category?: string) => {
    const params = new URLSearchParams()
    if (projectId != null) params.set('project_id', String(projectId))
    if (category) params.set('category', category)
    const q = params.toString()
    return request<NotificationsResponse>(`/api/notifications${q ? `?${q}` : ''}`)
  },
  executiveSummary: (period: 'today' | 'week' | 'month' = 'week', projectId?: number | null) => {
    const params = new URLSearchParams({ period })
    if (projectId != null) params.set('project_id', String(projectId))
    return request<ExecutiveSummary>(`/api/executive-summary?${params}`)
  },
  ask: (
    question: string,
    projectId?: number | null,
    history?: AnalysisHistoryTurn[],
  ) =>
    request<AnalysisResult>('/api/analysis/ask', {
      method: 'POST',
      body: JSON.stringify({
        question,
        ...(projectId != null ? { project_id: projectId } : {}),
        ...(history?.length ? { history } : {}),
      }),
    }),
}
