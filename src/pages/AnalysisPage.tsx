import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Loader2, Send, Trash2 } from 'lucide-react'
import {
  api,
  type AnalysisHistoryTurn,
  type AnalysisResult,
  type Finding,
  type PromptCard,
} from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, PageHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn, riskLabel, toneForStatus } from '@/lib/utils'
import { useProjectFilter } from '@/lib/project-filter'
import {
  clearAnalysisChat,
  loadAnalysisChat,
  saveAnalysisChat,
  type ChatMessage,
} from '@/lib/analysis-chat'

const LOADING_STEPS = [
  'Testler analiz ediliyor',
  'Gereksinimler inceleniyor',
  'Kod değişiklikleri analiz ediliyor',
  'AI analiz oluşturuyor',
]

const SOURCE_SUMMARY: { key: keyof NonNullable<AnalysisResult['data_sources']>; label: string }[] =
  [
    { key: 'tests', label: 'test' },
    { key: 'requirements', label: 'gereksinim' },
    { key: 'commits', label: 'commit' },
    { key: 'bugs', label: 'hata' },
    { key: 'tasks', label: 'görev' },
    { key: 'releases', label: 'sürüm' },
  ]

function asFindings(items?: Array<string | Finding>): Finding[] {
  if (!items?.length) return []
  return items.map((item) => {
    if (typeof item === 'string') {
      const match = item.match(/^([A-Z]+-[\w.]+)\s*[:：-]?\s*(.*)$/)
      if (match) return { id: match[1], text: match[2] || match[1], note: match[2] }
      return { id: '—', text: item, note: item }
    }
    return { id: item.id, text: item.text ?? item.note, note: item.note ?? item.text }
  })
}

function uid() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function recordPath(id: string): { path: string; q: string } | null {
  const raw = id.trim()
  if (!raw || raw === '—') return null
  const upper = raw.toUpperCase()
  if (upper.startsWith('REQ-')) return { path: '/gereksinimler', q: raw }
  if (upper.startsWith('TASK-')) return { path: '/gorevler', q: raw }
  if (upper.startsWith('TEST-')) return { path: '/testler', q: raw }
  if (upper.startsWith('BUG-')) return { path: '/hatalar', q: raw }
  if (upper.startsWith('REL-')) return { path: '/release', q: raw.replace(/^REL-/i, '') }
  if (/^[a-f0-9]{7,40}$/i.test(raw)) return { path: '/kod-degisiklikleri', q: raw }
  return null
}

function buildIntro(result: AnalysisResult): string {
  const type = result.analysis_type || result.intent || ''
  const focus = result.focus_entity
  const conclusion = (result.conclusion || result.summary || '').trim()

  const openings: Record<string, string> = {
    root_cause: 'Son sprint ve kalite verilerini taradım.',
    impact: focus
      ? `${focus} için bağlı görev, commit, test ve hata kayıtlarını çıkardım.`
      : 'Etki zincirini çıkardım.',
    release_readiness: focus
      ? `${focus} hazırlığını risk skoru, test ve hata sinyalleriyle değerlendirdim.`
      : 'Sürüm hazırlığını değerlendirdim.',
    risk: 'Risk skorlarını ve bağlı kalite sinyallerini inceledim.',
    executive_summary: 'Portföy genelinde KPI sinyallerini derledim.',
    sprint: 'Aktif sprintteki gecikme ve engel sinyallerini inceledim.',
    anomaly: 'Süreçlerde olağandışı sapmaları taradım.',
    requirement_revisions: 'Gereksinim revizyonlarını sıraladım.',
    failed_tests: 'Başarısız test kayıtlarını ve bağlantılarını inceledim.',
    risky_releases: 'Sürüm risk skorlarını değerlendirdim.',
    change_risk: 'Son dönem değişikliklerine bağlı canlıya çıkış riskini inceledim.',
    critical_bugs: 'Kritik açık hataları taradım.',
  }

  const open = openings[type] || 'İlgili süreç verilerini analiz ettim.'
  if (!conclusion) return open
  if (conclusion.toLowerCase().startsWith(open.toLowerCase().slice(0, 20))) return conclusion
  return `${open} ${conclusion}`
}

function followUpSuggestions(result: AnalysisResult): string[] {
  const fe = result.focus_entity
  const type = result.analysis_type || result.intent || ''
  const out: string[] = []

  if (fe?.toUpperCase().startsWith('REQ-')) {
    out.push(`${fe} değişirse neler etkilenir?`)
    out.push(`${fe} hangi sürümü etkiliyor?`)
    out.push(`${fe} ile ilgili açık bugları listele`)
    out.push(`${fe} için kök neden nedir?`)
  } else if (fe?.toUpperCase().startsWith('REL-')) {
    out.push(`${fe} yayınlanabilir mi?`)
    out.push(`${fe} için başarısız testleri göster`)
    out.push('Bu sürümdeki kritik hataları listele')
  } else if (fe?.toUpperCase().startsWith('BUG-')) {
    out.push(`${fe} hangi gereksinime bağlı?`)
    out.push('Kritik açık hataları listele')
  } else if (type === 'root_cause' || type === 'failed_tests') {
    out.push('En riskli gereksinim hangisi?')
    out.push('İlgili commitleri göster')
    out.push('Açık bugları listele')
  } else if (type === 'sprint' || type === 'delayed_tasks') {
    out.push('Bloke görevleri listele')
    out.push('Risk neden yüksek?')
  } else {
    out.push('En riskli gereksinim hangisi?')
    out.push('Riskli sürümleri göster')
    out.push('Başarısız testleri analiz et')
  }

  if (!out.some((s) => s.toLowerCase().includes('risk'))) {
    out.push('Risk neden yüksek?')
  }

  return [...new Set(out)].slice(0, 4)
}

function RecordLink({
  id,
  withProject,
}: {
  id: string
  withProject: (path: string) => string
}) {
  const target = recordPath(id)
  if (!target) {
    return <span className="font-mono text-[14px] font-semibold text-navy-mid">{id}</span>
  }
  const href = withProject(`${target.path}?q=${encodeURIComponent(target.q)}`)
  return (
    <Link
      to={href}
      className="shrink-0 font-mono text-[14px] font-semibold text-navy-mid underline-offset-2 hover:underline"
    >
      {id}
    </Link>
  )
}

function AnswerCards({
  result,
  onFollowUp,
}: {
  result: AnalysisResult
  onFollowUp: (q: string) => void
}) {
  const { withProject } = useProjectFilter()
  const intro = buildIntro(result)
  const findings =
    result.findings?.length
      ? result.findings
      : asFindings(result.risk_reasons).map((f) => f.text || f.note || f.id)
  const related = asFindings(
    result.related_records ??
      result.affected_records ?? [
        ...(result.affected_requirements ?? result.affected_items ?? []),
        ...(result.delayed_tasks ?? []),
        ...(result.failed_tests ?? []),
        ...(result.critical_bugs ?? []),
        ...(result.affected_releases ?? []),
      ],
  )
  const chain = result.impact_chain?.filter((c) => c.count > 0) ?? []
  const sources = SOURCE_SUMMARY.filter(
    (s) => (result.data_sources?.[s.key] ?? 0) > 0,
  )
  const suggestions = followUpSuggestions(result)
  const conclusion = result.conclusion || result.summary

  return (
    <div className="w-full space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {result.analysis_type_label ? (
          <Badge tone="info">{result.analysis_type_label}</Badge>
        ) : null}
        <Badge tone={toneForStatus(result.risk_level)}>{riskLabel(result.risk_level)}</Badge>
        {result.focus_entity ? (
          <RecordLink id={result.focus_entity} withProject={withProject} />
        ) : null}
      </div>

      <p className="text-[16px] leading-relaxed text-ink/90">{intro}</p>

      <Card className="!p-4">
        <div className="text-[13px] font-semibold uppercase tracking-wide text-muted">Sonuç</div>
        <p className="mt-1.5 text-[16px] font-medium leading-relaxed text-ink">{conclusion}</p>
      </Card>

      {findings.length > 0 ? (
        <Card className="!p-4">
          <div className="text-[13px] font-semibold uppercase tracking-wide text-muted">
            Bulgular
          </div>
          <ul className="mt-2 space-y-1.5">
            {findings.map((f, i) => (
              <li key={i} className="flex gap-2 text-[15px] text-ink">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-navy-mid" />
                <span>{f}</span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {chain.length > 0 ? (
        <Card className="!p-4">
          <div className="text-[13px] font-semibold uppercase tracking-wide text-muted">
            Etki Zinciri
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {chain.map((node, i) => (
              <div key={node.kind} className="flex items-center gap-2">
                <div className="rounded-md border border-line bg-surface px-3 py-2 text-center">
                  <div className="text-[20px] font-semibold tabular-nums text-navy">{node.count}</div>
                  <div className="text-[13px] text-muted">{node.label}</div>
                </div>
                {i < chain.length - 1 ? (
                  <span className="text-[18px] text-muted" aria-hidden>
                    →
                  </span>
                ) : null}
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      <Card className="!p-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[13px] font-semibold uppercase tracking-wide text-muted">Risk</div>
          <div className="mt-1 text-[18px] font-semibold text-ink">
            {riskLabel(result.risk_level)}
          </div>
        </div>
        <Badge tone={toneForStatus(result.risk_level)} className="px-3 py-1.5 text-[15px]">
          {riskLabel(result.risk_level)}
        </Badge>
      </Card>

      {result.recommended_actions?.length ? (
        <Card className="!p-4">
          <div className="text-[13px] font-semibold uppercase tracking-wide text-muted">Öneri</div>
          <ul className="mt-2 space-y-1.5">
            {result.recommended_actions.map((a, i) => (
              <li key={i} className="text-[15px] text-ink">
                {a}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {related.length > 0 ? (
        <Card className="!p-4">
          <div className="text-[13px] font-semibold uppercase tracking-wide text-muted">
            İlgili Kayıtlar
          </div>
          <ul className="mt-2 space-y-2">
            {related.slice(0, 12).map((item, i) => (
              <li
                key={`${item.id}-${i}`}
                className="flex gap-3 rounded-md border border-line bg-surface/60 px-3 py-2"
              >
                <RecordLink id={item.id} withProject={withProject} />
                <span className="text-[14px] text-ink">{item.text ?? item.note ?? '—'}</span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {sources.length > 0 ? (
        <Card className="!p-4">
          <div className="text-[13px] font-semibold uppercase tracking-wide text-muted">
            Analiz Edilen Veri
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {sources.map((s) => (
              <div
                key={s.key}
                className="rounded-md border border-line bg-surface px-3 py-2 text-[15px]"
              >
                <span className="font-semibold tabular-nums text-navy">
                  {result.data_sources?.[s.key] ?? 0}
                </span>{' '}
                {s.label}
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      {suggestions.length > 0 ? (
        <div>
          <div className="text-[13px] font-semibold uppercase tracking-wide text-muted">
            Devam soruları
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {suggestions.map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => onFollowUp(q)}
                className="rounded-md border border-line bg-panel px-3 py-2 text-left text-[14px] font-medium text-ink transition hover:border-navy-mid/40 hover:bg-[#F4F7FA]"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}

export function AnalysisPage() {
  const location = useLocation()
  const { projectId } = useProjectFilter()
  const [question, setQuestion] = useState('')
  const [prompts, setPrompts] = useState<PromptCard[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadAnalysisChat(projectId))
  const [loading, setLoading] = useState(false)
  const [step, setStep] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [hydrated, setHydrated] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const lastAutoPrompt = useRef<string | null>(null)
  const skipScrollOnHydrate = useRef(true)
  const skipNextSave = useRef(false)

  useEffect(() => {
    skipNextSave.current = true
    setMessages(loadAnalysisChat(projectId))
    setHydrated(true)
    skipScrollOnHydrate.current = true
    setLastUpdated(null)
  }, [projectId])

  useEffect(() => {
    if (!hydrated) return
    if (skipNextSave.current) {
      skipNextSave.current = false
      return
    }
    saveAnalysisChat(projectId, messages)
  }, [messages, projectId, hydrated])

  useEffect(() => {
    api.prompts().then(setPrompts).catch(() => setPrompts([]))
  }, [])

  useEffect(() => {
    const prompt = (location.state as { prompt?: string } | null)?.prompt
    if (prompt && prompt !== lastAutoPrompt.current) {
      lastAutoPrompt.current = prompt
      void run(prompt)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state])

  useEffect(() => {
    if (!loading) return
    setStep(0)
    const timers = LOADING_STEPS.map((_, i) =>
      window.setTimeout(() => setStep(i), i * 750),
    )
    return () => timers.forEach(clearTimeout)
  }, [loading])

  useEffect(() => {
    if (skipScrollOnHydrate.current) {
      skipScrollOnHydrate.current = false
      return
    }
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, loading])

  function historyPayload(): AnalysisHistoryTurn[] {
    const turns: AnalysisHistoryTurn[] = []
    for (const m of messages) {
      if (m.role === 'user') {
        turns.push({ role: 'user', content: m.content })
      } else {
        turns.push({
          role: 'assistant',
          content: m.result.conclusion || m.result.summary || m.content,
          focus_entity: m.result.focus_entity,
          intent: m.result.intent || m.result.analysis_type,
          summary: m.result.summary,
        })
      }
    }
    return turns.slice(-8)
  }

  async function run(q: string) {
    const text = q.trim()
    if (!text || loading) return
    setQuestion('')
    setLoading(true)
    setError(null)
    const userMsg: ChatMessage = { id: uid(), role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg])
    try {
      const history = [...historyPayload(), { role: 'user' as const, content: text }]
      const minDelay = new Promise((r) => setTimeout(r, 3200))
      const [res] = await Promise.all([api.ask(text, projectId, history), minDelay])
      setLastUpdated(new Date().toISOString())
      setMessages((prev) => [
        ...prev,
        {
          id: uid(),
          role: 'assistant',
          content: res.conclusion || res.summary,
          result: res,
        },
      ])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Analiz başarısız')
    } finally {
      setLoading(false)
    }
  }

  const canSubmit = Boolean(question.trim()) && !loading

  function clearChat() {
    if (loading) return
    clearAnalysisChat(projectId)
    setMessages([])
    setError(null)
    setLastUpdated(null)
  }

  return (
    <div className="pb-8">
      <PageHeader title="AI Analiz Merkezi" className="mb-3" updatedAt={lastUpdated} />

      <div>
        <h2 className="text-[15px] font-semibold tracking-wide text-muted">
          Önerilen Analizler
        </h2>
        <div className="mt-2.5 flex flex-wrap gap-2">
          {prompts.map((p) => (
            <button
              key={p.id}
              type="button"
              disabled={loading}
              onClick={() => void run(p.prompt)}
              className={cn(
                'rounded-md border border-line bg-panel px-3.5 py-2 text-[14px] font-medium text-ink transition',
                'hover:border-navy-mid/40 hover:bg-[#F4F7FA]',
                'disabled:cursor-not-allowed disabled:opacity-50',
              )}
            >
              {p.title}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-[15px] font-semibold tracking-wide text-muted">
            Sohbet / Analiz Geçmişi
          </h2>
          {messages.length > 0 ? (
            <button
              type="button"
              onClick={clearChat}
              disabled={loading}
              className="inline-flex items-center gap-1.5 text-[14px] font-medium text-muted transition hover:text-danger disabled:opacity-50"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Sohbeti temizle
            </button>
          ) : null}
        </div>

        {messages.length === 0 && !loading ? (
          <Card className="mt-3 !p-6">
            <p className="text-[16px] text-muted">
              Hazır bir analiz seçin veya aşağıdan soru sorun. Cevaplar kartlar halinde burada
              görünür.
            </p>
          </Card>
        ) : null}

        <div className="mt-3 space-y-5">
          {messages.map((m) =>
            m.role === 'user' ? (
              <div key={m.id} id={`analysis-msg-${m.id}`} className="flex justify-end">
                <div className="max-w-[min(100%,720px)] rounded-lg bg-[#0F2747] px-4 py-3 text-[15px] text-white">
                  <div className="mb-1 text-[12px] font-semibold uppercase tracking-wide text-white/70">
                    Kullanıcı
                  </div>
                  {m.content}
                </div>
              </div>
            ) : (
              <div key={m.id} id={`analysis-msg-${m.id}`} className="w-full max-w-5xl">
                <div className="mb-2 text-[12px] font-semibold uppercase tracking-wide text-muted">
                  AI
                </div>
                <AnswerCards result={m.result} onFollowUp={(q) => void run(q)} />
              </div>
            ),
          )}

          {loading ? (
            <Card className="max-w-5xl !p-5">
              <div className="flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-navy-mid" />
                <h3 className="text-[16px] font-semibold text-ink">Analiz yürütülüyor</h3>
              </div>
              <ul className="mt-4 space-y-2.5">
                {LOADING_STEPS.map((label, i) => (
                  <li key={label} className="flex items-center gap-3 text-[15px]">
                    <span
                      className={cn(
                        'flex h-6 w-6 items-center justify-center rounded-full border text-[11px] font-semibold',
                        i < step
                          ? 'border-ok bg-[#E8F3ED] text-ok'
                          : i === step
                            ? 'border-navy-mid bg-[#E8EEF5] text-navy-mid'
                            : 'border-line bg-panel text-muted',
                      )}
                    >
                      {i < step ? '✓' : i + 1}
                    </span>
                    <span className={cn(i === step ? 'font-medium text-ink' : 'text-muted')}>
                      {label}
                      {i === step ? '…' : ''}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}

          {error ? (
            <div className="rounded-lg border border-danger/30 bg-[#F8EAEA] p-4 text-sm text-danger">
              {error}
            </div>
          ) : null}

          <div ref={bottomRef} />
        </div>
      </div>

      <div className="sticky bottom-0 mt-6 border-t border-line bg-surface/95 py-4 backdrop-blur-sm">
        <div className="rounded-lg border border-line bg-panel p-4 shadow-[0_1px_2px_rgba(15,39,71,0.04)]">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="min-w-0 flex-1">
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    void run(question)
                  }
                }}
                placeholder="Bana süreçlerle ilgili bir soru sorun..."
                className="h-12 w-full rounded-md border border-line bg-surface px-4 text-[16px] text-ink outline-none transition focus:border-navy-mid focus:ring-2 focus:ring-navy-mid/15"
              />
            </div>
            <Button
              onClick={() => void run(question)}
              disabled={!canSubmit}
              className={cn(
                'h-12 min-w-[160px] shrink-0 text-[16px] font-semibold',
                canSubmit
                  ? 'bg-[#0F2747] text-white hover:bg-[#1E4E79]'
                  : 'bg-slate-200 text-slate-500',
              )}
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Analizi Başlat
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
