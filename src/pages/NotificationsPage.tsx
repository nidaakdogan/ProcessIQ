import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { api, type AiNotification } from '@/lib/api'
import { Card, PageHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn, formatDate, type StatusTone } from '@/lib/utils'
import { useProjectFilter } from '@/lib/project-filter'

const CATEGORY_FILTERS: { id: string; label: string }[] = [
  { id: '', label: 'Tümü' },
  { id: 'critical_risk', label: 'Kritik Risk' },
  { id: 'process_warning', label: 'Süreç Uyarısı' },
  { id: 'performance', label: 'Performans' },
  { id: 'ai_suggestion', label: 'AI Önerisi' },
]

const SCAN_STEPS = [
  'Gereksinimler analiz ediliyor',
  'Test sonuçları inceleniyor',
  'Kod değişiklikleri kontrol ediliyor',
  'Hatalar analiz ediliyor',
  'Release durumu değerlendiriliyor',
  'AI bildirimleri oluşturuluyor',
]

/** ~2.5 sn toplam animasyon */
const STEP_MS = 400

function categoryTone(category: string): StatusTone {
  if (category === 'critical_risk') return 'critical'
  if (category === 'process_warning') return 'warn'
  if (category === 'performance') return 'warn'
  if (category === 'ai_suggestion') return 'ok'
  return 'info'
}

function categoryBorder(category: string) {
  if (category === 'critical_risk') return 'border-l-[#A83232] bg-[#FDF6F6]'
  if (category === 'process_warning') return 'border-l-[#C47A1A] bg-[#FFFBF5]'
  if (category === 'performance') return 'border-l-[#B8860B] bg-[#FFFDF5]'
  if (category === 'ai_suggestion') return 'border-l-[#2F6B4F] bg-[#F5FAF7]'
  return 'border-l-[#1E4E79] bg-[#F5F8FB]'
}

function recordHref(id: string, withProject: (p: string) => string) {
  const upper = id.toUpperCase()
  if (upper.startsWith('REQ-')) return withProject(`/gereksinimler?q=${encodeURIComponent(id)}`)
  if (upper.startsWith('TASK-')) return withProject(`/gorevler?q=${encodeURIComponent(id)}`)
  if (upper.startsWith('TEST-') || upper.startsWith('TC-')) {
    return withProject(`/testler?q=${encodeURIComponent(id)}`)
  }
  if (upper.startsWith('BUG-')) return withProject(`/hatalar?q=${encodeURIComponent(id)}`)
  if (upper.startsWith('REL-')) {
    return withProject(`/release?q=${encodeURIComponent(id.replace(/^REL-/i, ''))}`)
  }
  return withProject('/analiz')
}

function triggerChips(item: AiNotification): string[] {
  if (item.triggers?.length) {
    return item.triggers.map((t) => (t.value ? `${t.label} ${t.value}`.trim() : t.label)).filter(Boolean)
  }
  if (item.trigger) return item.trigger.split(' · ').map((s) => s.trim()).filter(Boolean)
  return []
}

function NotificationCard({
  item,
  withProject,
}: {
  item: AiNotification
  withProject: (p: string) => string
}) {
  const chips = triggerChips(item)
  const deepen =
    item.deepen_prompt ||
    (item.focus_entity ? `${item.focus_entity} değişirse neler etkilenir?` : item.title)
  const related = (item.related_records ?? []).filter((r) => r.id && r.id !== '—')

  return (
    <Card className={cn('!p-0 overflow-hidden border-l-4', categoryBorder(item.category))}>
      <div className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Badge tone={categoryTone(item.category)}>
            {item.category_emoji} {item.category_label}
          </Badge>
          <span className="text-[13px] text-muted">{formatDate(item.created_at)}</span>
        </div>

        <h3 className="mt-3 text-[18px] font-semibold leading-snug text-ink">{item.title}</h3>

        {chips.length > 0 ? (
          <div className="mt-4">
            <div className="text-[12px] font-semibold uppercase tracking-wide text-muted">
              Tetikleyici
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {chips.map((chip) => (
                <span
                  key={chip}
                  className="rounded-md border border-line bg-panel px-2.5 py-1 text-[13px] font-medium text-ink"
                >
                  {chip}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        <div className="mt-4">
          <div className="text-[12px] font-semibold uppercase tracking-wide text-muted">
            AI Yorumu
          </div>
          <p className="mt-1.5 text-[15px] leading-relaxed text-ink/90">{item.analysis}</p>
        </div>

        <div className="mt-4">
          <div className="text-[12px] font-semibold uppercase tracking-wide text-muted">
            Önerilen Aksiyon
          </div>
          <p className="mt-1.5 text-[15px] leading-relaxed text-ink">{item.recommended_action}</p>
        </div>

        {related.length > 0 ? (
          <div className="mt-4">
            <div className="text-[12px] font-semibold uppercase tracking-wide text-muted">
              İlgili Kayıtlar
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[14px]">
              {related.slice(0, 8).map((r, i) => (
                <span key={`${r.id}-${i}`} className="inline-flex items-center gap-2">
                  {i > 0 ? <span className="text-muted">·</span> : null}
                  <Link
                    to={recordHref(r.id, withProject)}
                    className="font-mono font-semibold text-navy-mid hover:underline"
                  >
                    {r.id}
                  </Link>
                </span>
              ))}
            </div>
          </div>
        ) : null}

        <div className="mt-4 border-t border-line pt-3">
          <Link
            to="/analiz"
            state={{ prompt: deepen }}
            className="text-[14px] font-medium text-navy-mid hover:underline"
          >
            AI Analiz Merkezi’nde derinleştir →
          </Link>
        </div>
      </div>
    </Card>
  )
}

export function NotificationsPage() {
  const { projectId, withProject } = useProjectFilter()
  const [items, setItems] = useState<AiNotification[]>([])
  const [scanning, setScanning] = useState(true)
  const [scanStep, setScanStep] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [category, setCategory] = useState('')
  const [scanMeta, setScanMeta] = useState<{
    records: number
    notifications: number
  } | null>(null)
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const timers: number[] = []

    async function autoScan() {
      setError(null)
      setScanning(true)
      setScanStep(0)
      setItems([])
      setScanMeta(null)
      setLastUpdated(null)

      SCAN_STEPS.forEach((_, i) => {
        timers.push(window.setTimeout(() => {
          if (!cancelled) setScanStep(i)
        }, i * STEP_MS))
      })

      const minDelay = new Promise((r) => setTimeout(r, SCAN_STEPS.length * STEP_MS + 150))

      try {
        const [res] = await Promise.all([api.notifications(projectId), minDelay])
        if (cancelled) return
        setItems(res.items)
        setScanMeta({
          records: res.summary?.records_scanned ?? 0,
          notifications: res.summary?.notifications_created ?? res.count,
        })
        setLastUpdated(res.generated_at || new Date().toISOString())
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Bildirimler yüklenemedi')
        }
      } finally {
        if (!cancelled) {
          setScanning(false)
          setScanStep(SCAN_STEPS.length)
        }
      }
    }

    void autoScan()
    return () => {
      cancelled = true
      timers.forEach(clearTimeout)
    }
  }, [projectId])

  const counts = useMemo(() => {
    const map: Record<string, number> = {}
    for (const n of items) map[n.category] = (map[n.category] ?? 0) + 1
    return map
  }, [items])

  const filtered = useMemo(
    () => (category ? items.filter((n) => n.category === category) : items),
    [items, category],
  )

  return (
    <div>
      <PageHeader title="AI Bildirim Merkezi" className="mb-3" updatedAt={lastUpdated} />

      {scanning ? (
        <Card className="mb-5 !p-5">
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-navy-mid" />
            <h3 className="text-[16px] font-semibold text-ink">AI sistemi tarıyor</h3>
          </div>
          <ul className="mt-4 space-y-2.5">
            {SCAN_STEPS.map((label, i) => (
              <li key={label} className="flex items-center gap-3 text-[15px]">
                <span
                  className={cn(
                    'flex h-6 w-6 items-center justify-center rounded-full border text-[11px] font-semibold',
                    i < scanStep
                      ? 'border-ok bg-[#E8F3ED] text-ok'
                      : i === scanStep
                        ? 'border-navy-mid bg-[#E8EEF5] text-navy-mid'
                        : 'border-line bg-panel text-muted',
                  )}
                >
                  {i < scanStep ? '✓' : i + 1}
                </span>
                <span className={cn(i === scanStep ? 'font-medium text-ink' : 'text-muted')}>
                  {label}
                  {i === scanStep ? '…' : ''}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      ) : (
        <>
          {scanMeta ? (
            <p className="mb-4 text-[14px] text-muted">
              Son tarama: Az önce
              <span className="mx-1.5 text-line">•</span>
              <span className="tabular-nums text-ink/80">{scanMeta.records}</span> kayıt analiz edildi
              <span className="mx-1.5 text-line">•</span>
              <span className="tabular-nums text-ink/80">{scanMeta.notifications}</span> AI bildirimi
              oluşturuldu
            </p>
          ) : null}

          <div className="mb-5 flex flex-wrap gap-2">
            {CATEGORY_FILTERS.map((f) => (
              <button
                key={f.id || 'all'}
                type="button"
                onClick={() => setCategory(f.id)}
                className={cn(
                  'rounded-md border px-3 py-1.5 text-[14px] font-medium transition',
                  category === f.id
                    ? 'border-navy-mid bg-[#E8EEF5] text-navy'
                    : 'border-line bg-panel text-ink hover:border-navy-mid/35',
                )}
              >
                {f.label}
                {f.id && counts[f.id] ? (
                  <span className="ml-1.5 tabular-nums text-muted">({counts[f.id]})</span>
                ) : null}
              </button>
            ))}
          </div>

          {error ? (
            <div className="mb-4 rounded-lg border border-danger/30 bg-[#F8EAEA] p-4 text-sm text-danger">
              {error}
            </div>
          ) : null}

          {filtered.length === 0 && !error ? (
            <Card className="!p-8 text-center text-[15px] text-muted">
              Şu an tetiklenen bildirim yok. Sistem olayları izlemeye devam ediyor.
            </Card>
          ) : null}

          <div className="space-y-4">
            {filtered.map((item) => (
              <NotificationCard key={item.id} item={item} withProject={withProject} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}
