import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Download, FileBarChart2, Loader2 } from 'lucide-react'
import { api, type ExecutiveSummary } from '@/lib/api'
import { Card, PageHeader } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { cn, formatLastUpdated } from '@/lib/utils'
import { useProjectFilter } from '@/lib/project-filter'
import {
  exportExecutiveReport,
  type ExportFormat,
} from '@/lib/executive-export'

type Period = 'today' | 'week' | 'month'

const PERIODS: { id: Period; label: string }[] = [
  { id: 'today', label: 'Bugün' },
  { id: 'week', label: 'Bu Hafta' },
  { id: 'month', label: 'Bu Ay' },
]

const SCAN_STEPS = [
  'Görevler analiz ediliyor',
  'Test sonuçları inceleniyor',
  'Hatalar değerlendiriliyor',
  'Release durumu analiz ediliyor',
  'AI yönetici özeti hazırlanıyor',
]

const STEP_MS = 450

const EXPORT_OPTIONS: { id: ExportFormat; label: string }[] = [
  { id: 'pdf', label: 'PDF' },
  { id: 'docx', label: 'Word (.docx)' },
  { id: 'xlsx', label: 'Excel (.xlsx)' },
  { id: 'md', label: 'Markdown (.md)' },
]

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

function RecordLinks({
  id,
  withProject,
}: {
  id: string
  withProject: (p: string) => string
}) {
  const deepen = `${id} için kök neden ve etki analizi yap`
  return (
    <span className="inline-flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5">
      <Link
        to={recordHref(id, withProject)}
        className="font-mono font-semibold text-navy-mid hover:underline"
      >
        {id}
      </Link>
      <Link
        to="/analiz"
        state={{ prompt: deepen }}
        className="text-[12px] font-medium text-muted hover:text-navy-mid hover:underline"
        title="AI Analiz Merkezi’nde derinleştir"
      >
        Analiz
      </Link>
    </span>
  )
}

function linkifyIds(text: string, withProject: (p: string) => string) {
  const parts = text.split(/(REQ-\d+|TASK-\d+|TEST-\d+|BUG-\d+|REL-[\w.-]+)/gi)
  return parts.map((part, i) => {
    if (/^(REQ|TASK|TEST|BUG|REL)-/i.test(part)) {
      return <RecordLinks key={`${part}-${i}`} id={part} withProject={withProject} />
    }
    return <span key={i}>{part}</span>
  })
}

function trendTone(direction: string) {
  if (direction === 'up') return 'text-ok'
  if (direction === 'down') return 'text-danger'
  return 'text-muted'
}

/** Emoji oklar CSS rengini almaz; ▲/▼ ile değiştir. */
function changeLabel(metric: {
  change_display?: string
  delta: string
  direction?: string
}) {
  const raw = metric.change_display || metric.delta || ''
  return raw
    .replace(/🔺|🟢/g, '▲')
    .replace(/🔻/g, '▼')
}

function ReportView({
  report,
  withProject,
}: {
  report: ExecutiveSummary
  withProject: (p: string) => string
}) {
  const o = report.overview
  const t = report.trends
  const lastUp = report.last_updated || report.generated_at

  return (
    <div className="space-y-5">
      <Card className="!p-4 border-navy-mid/20 bg-[#F5F8FB]">
        <div className="grid gap-2 text-[15px] sm:grid-cols-3">
          <div>
            <div className="text-[12px] font-semibold uppercase tracking-wide text-muted">
              Rapor Dönemi
            </div>
            <p className="mt-0.5 font-medium text-ink">
              {report.period_label}
              {report.period_range_label ? (
                <span className="ml-1.5 font-normal text-muted">
                  ({report.period_range_label})
                </span>
              ) : null}
            </p>
          </div>
          <div>
            <div className="text-[12px] font-semibold uppercase tracking-wide text-muted">
              Analiz Edilen Kayıt
            </div>
            <p className="mt-0.5 font-medium tabular-nums text-ink">{report.records_scanned}</p>
          </div>
          <div>
            <div className="text-[12px] font-semibold uppercase tracking-wide text-muted">
              Son Güncelleme
            </div>
            <p className="mt-0.5 font-medium text-ink">{formatLastUpdated(lastUp)}</p>
          </div>
        </div>
        {report.project_name ? (
          <p className="mt-3 border-t border-line/80 pt-2 text-[14px] text-muted">
            Proje:{' '}
            <span className="font-medium text-ink">{report.project_name}</span>
          </p>
        ) : null}
      </Card>

      <Card className="!p-5">
        <h3 className="text-[16px] font-semibold text-ink">📊 Genel Durum</h3>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { label: 'Tamamlanan görev', value: o.completed_tasks },
            { label: 'Yeni açılan bug', value: o.new_bugs },
            { label: 'Başarısız test', value: o.failed_tests },
            {
              label: 'Kalite skoru',
              value: `${o.quality_score}`,
              sub: o.quality_label,
            },
          ].map((m) => (
            <div key={m.label} className="rounded-md border border-line bg-panel px-3 py-3">
              <div className="text-[12px] font-medium uppercase tracking-wide text-muted">
                {m.label}
              </div>
              <div className="mt-1 text-[22px] font-semibold tabular-nums text-navy">
                {m.value}
                {'sub' in m && m.sub ? (
                  <span className="ml-2 text-[13px] font-medium text-muted">{m.sub}</span>
                ) : null}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-4 border-t border-line pt-3">
          <div className="text-[12px] font-semibold uppercase tracking-wide text-muted">
            Release durumu
          </div>
          <p className="mt-1 text-[15px] text-ink">{o.release_status}</p>
          <p className="mt-2 text-[15px] leading-relaxed text-ink/85">{o.quality_assessment}</p>
        </div>
      </Card>

      <Card className="!p-5">
        <h3 className="text-[16px] font-semibold text-ink">⚠ Kritik Gelişmeler</h3>
        <ul className="mt-3 space-y-3">
          {report.critical_developments.map((item) => (
            <li key={item.title} className="border-l-2 border-[#C47A1A]/70 pl-3">
              <div className="text-[14px] font-semibold text-ink">{item.title}</div>
              <p className="mt-0.5 text-[15px] leading-relaxed text-ink/85">
                {linkifyIds(item.detail, withProject)}
              </p>
            </li>
          ))}
        </ul>
      </Card>

      <Card className="!p-5 border-navy-mid/20 bg-[#F5F8FB]">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-[16px] font-semibold text-ink">🤖 AI Değerlendirmesi</h3>
          {report.confidence != null ? (
            <Badge tone="info">AI Güven Skoru: %{report.confidence}</Badge>
          ) : null}
        </div>
        <p className="mt-3 text-[15px] leading-relaxed text-ink">
          {linkifyIds(report.assessment, withProject)}
        </p>
      </Card>

      <Card className="!p-5">
        <h3 className="text-[16px] font-semibold text-ink">💡 AI Önerileri</h3>
        <ol className="mt-3 list-decimal space-y-2 pl-5">
          {report.recommendations.map((rec) => (
            <li key={rec} className="text-[15px] leading-relaxed text-ink">
              {linkifyIds(rec, withProject)}
            </li>
          ))}
        </ol>
      </Card>

      <Card className="!p-5">
        <h3 className="text-[16px] font-semibold text-ink">📈 Trend</h3>
        <p className="mt-1 text-[13px] text-muted">
          {t.period_label} → {t.current_period_label || report.period_label} karşılaştırması
        </p>
        <div className="mt-4 overflow-x-auto rounded-md border border-line">
          <table className="w-full min-w-[520px] border-collapse text-left text-[14px]">
            <thead>
              <tr className="border-b border-line bg-[#F5F8FB] text-[12px] font-semibold uppercase tracking-wide text-muted">
                <th className="px-3 py-2.5 font-semibold">Metrik</th>
                <th className="px-3 py-2.5 font-semibold tabular-nums">Önceki Dönem</th>
                <th className="px-3 py-2.5 font-semibold tabular-nums">Bu Dönem</th>
                <th className="px-3 py-2.5 font-semibold">Değişim</th>
              </tr>
            </thead>
            <tbody>
              {(
                [
                  ['failed_tests', 'Başarısız Test', t.failed_tests],
                  ['critical_bugs', 'Kritik Bug', t.critical_bugs],
                  ['completed_tasks', 'Tamamlanan Görev', t.completed_tasks],
                  ['quality_score', 'Kalite Skoru', t.quality_score],
                ] as const
              ).map(([key, label, metric]) => (
                <tr key={key} className="border-b border-line last:border-b-0">
                  <td className="px-3 py-2.5 font-medium text-ink">{label}</td>
                  <td className="px-3 py-2.5 tabular-nums text-ink/90">{metric.previous}</td>
                  <td className="px-3 py-2.5 tabular-nums text-ink/90">{metric.current}</td>
                  <td
                    className={cn(
                      'px-3 py-2.5 font-semibold tabular-nums',
                      trendTone(metric.direction),
                    )}
                  >
                    {changeLabel(metric)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {t.commentary ? (
          <div className="mt-4 rounded-md border border-navy-mid/15 bg-[#F5F8FB] px-3.5 py-3">
            <div className="text-[12px] font-semibold uppercase tracking-wide text-muted">
              AI Trend Yorumu
            </div>
            <p className="mt-1.5 text-[15px] leading-relaxed text-ink">
              {t.commentary}
            </p>
          </div>
        ) : null}
      </Card>

      {report.priorities?.length ? (
        <Card className="!p-5">
          <h3 className="text-[16px] font-semibold text-ink">🎯 AI Öncelikleri</h3>
          <p className="mt-1 text-[13px] text-muted">
            Yöneticinin ilk odaklanması gereken konular
          </p>
          <ol className="mt-3 list-decimal space-y-2 pl-5">
            {report.priorities.map((p) => (
              <li key={p} className="text-[15px] leading-relaxed text-ink">
                {linkifyIds(p, withProject)}
              </li>
            ))}
          </ol>
        </Card>
      ) : null}
    </div>
  )
}

export function ExecutiveSummaryPage() {
  const { projectId, withProject } = useProjectFilter()
  const [period, setPeriod] = useState<Period>('week')
  const [report, setReport] = useState<ExecutiveSummary | null>(null)
  const [generating, setGenerating] = useState(false)
  const [scanStep, setScanStep] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [downloadOpen, setDownloadOpen] = useState(false)
  const [exporting, setExporting] = useState(false)
  const requestId = useRef(0)
  const downloadRef = useRef<HTMLDivElement>(null)

  async function generate(nextPeriod: Period = period) {
    const id = ++requestId.current
    setError(null)
    setGenerating(true)
    setScanStep(0)
    setReport(null)
    setDownloadOpen(false)

    const timers = SCAN_STEPS.map((_, i) =>
      window.setTimeout(() => {
        if (requestId.current === id) setScanStep(i)
      }, i * STEP_MS),
    )
    const minDelay = new Promise((r) => setTimeout(r, SCAN_STEPS.length * STEP_MS + 200))

    try {
      const [res] = await Promise.all([
        api.executiveSummary(nextPeriod, projectId),
        minDelay,
      ])
      if (requestId.current !== id) return
      setReport(res)
    } catch {
      if (requestId.current !== id) return
      setError(
        'Yönetici özeti şu anda oluşturulamadı. Lütfen daha sonra tekrar deneyin.',
      )
    } finally {
      timers.forEach(clearTimeout)
      if (requestId.current === id) setGenerating(false)
    }
  }

  useEffect(() => {
    // Dönem veya proje değişince eski raporu temizle — yeniden üretmek için butona basılmalı
    setReport(null)
    setError(null)
    setDownloadOpen(false)
  }, [period, projectId])

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!downloadRef.current?.contains(e.target as Node)) setDownloadOpen(false)
    }
    if (downloadOpen) document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [downloadOpen])

  function onSelectPeriod(p: Period) {
    if (generating) return
    setPeriod(p)
  }

  async function onExport(format: ExportFormat) {
    if (!report) return
    setExporting(true)
    setDownloadOpen(false)
    try {
      await exportExecutiveReport(report, format)
    } catch {
      setError('Rapor indirilemedi. Lütfen tekrar deneyin.')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <PageHeader
          title="AI Yönetici Özeti"
          className="mb-0"
          updatedAt={report?.generated_at || report?.last_updated || null}
        />
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            onClick={() => void generate(period)}
            disabled={generating}
            className="h-10 bg-[#0F2747] text-white hover:bg-[#1E4E79]"
          >
            {generating ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <FileBarChart2 className="h-4 w-4" />
            )}
            AI Raporu Oluştur
          </Button>

          <div className="relative" ref={downloadRef}>
            <Button
              type="button"
              variant="outline"
              disabled={!report || generating || exporting}
              onClick={() => setDownloadOpen((v) => !v)}
              className="h-10"
            >
              {exporting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              Raporu İndir
            </Button>
            {downloadOpen ? (
              <div className="absolute right-0 z-20 mt-1 min-w-[180px] rounded-md border border-line bg-panel py-1 shadow-md">
                {EXPORT_OPTIONS.map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    className="block w-full px-3 py-2 text-left text-[14px] text-ink hover:bg-[#F4F7FA]"
                    onClick={() => void onExport(opt.id)}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="mb-5 flex flex-wrap gap-2">
        {PERIODS.map((p) => (
          <button
            key={p.id}
            type="button"
            onClick={() => onSelectPeriod(p.id)}
            disabled={generating}
            className={cn(
              'rounded-md border px-3 py-1.5 text-[14px] font-medium transition',
              period === p.id
                ? 'border-navy-mid bg-[#E8EEF5] text-navy'
                : 'border-line bg-panel text-ink hover:border-navy-mid/35',
              generating && 'opacity-50',
            )}
          >
            {p.label}
          </button>
        ))}
      </div>

      {generating ? (
        <Card className="mb-5 !p-5">
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin text-navy-mid" />
            <h3 className="text-[16px] font-semibold text-ink">AI yönetici raporu hazırlanıyor</h3>
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
      ) : null}

      {error ? (
        <div className="mb-4 rounded-lg border border-danger/30 bg-[#F8EAEA] p-4 text-sm text-danger">
          {error}
        </div>
      ) : null}

      {!generating && !report && !error ? (
        <Card className="!p-8 text-center">
          <p className="mx-auto max-w-2xl text-[15px] leading-relaxed text-muted">
            Lütfen rapor dönemi seçin ve{' '}
            <span className="font-medium text-ink">AI Raporu Oluştur</span> butonuna tıklayın. AI
            seçilen dönemdeki görev, test, hata, release ve gereksinim verilerini analiz ederek
            yönetici özetini hazırlayacaktır.
          </p>
        </Card>
      ) : null}

      {!generating && report ? <ReportView report={report} withProject={withProject} /> : null}
    </div>
  )
}
