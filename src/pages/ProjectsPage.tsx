import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { FolderKanban, AlertTriangle, Timer } from 'lucide-react'
import { api } from '@/lib/api'
import { Card, PageHeader } from '@/components/ui/card'
import { DataTable } from '@/components/ui/data-table'
import { Badge, toneForStatus } from '@/components/ui/badge'
import { DetailPanel, DetailField } from '@/components/ui/detail-panel'
import { cn, formatRowUpdatedAt, latestTimestamp, releaseStatusLabel, statusLabel } from '@/lib/utils'
import { useProjectFilter } from '@/lib/project-filter'
import { useLastUpdated } from '@/lib/use-last-updated'

function StatusDot({
  tone,
  title,
}: {
  tone: 'ok' | 'warn' | 'danger' | 'neutral'
  title: string
}) {
  const colors = {
    ok: 'bg-ok',
    warn: 'bg-warn',
    danger: 'bg-danger',
    neutral: 'bg-slate-300',
  }
  return (
    <span
      title={title}
      className={cn('inline-block h-2 w-2 shrink-0 rounded-full', colors[tone])}
      aria-label={title}
    />
  )
}

export function ProjectsPage() {
  const { projectId, setProjectId } = useProjectFilter()
  const [searchParams, setSearchParams] = useSearchParams()
  const [rows, setRows] = useState<Record<string, unknown>[]>([])
  const [portfolio, setPortfolio] = useState<Record<string, unknown>[]>([])
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null)
  const statusFilter = searchParams.get('status') ?? ''
  const isRisky = searchParams.get('is_risky') ?? ''

  useEffect(() => {
    api.projects().then(setPortfolio).catch(console.error)
  }, [])

  useEffect(() => {
    const params = new URLSearchParams()
    if (statusFilter) params.set('status', statusFilter)
    if (isRisky === 'true' || isRisky === 'false') params.set('is_risky', isRisky)
    const q = params.toString()
    api.projects(q ? `?${q}` : '').then(setRows).catch(console.error)
  }, [statusFilter, isRisky])

  const visibleRows = useMemo(() => {
    if (projectId == null) return rows
    return rows.filter((r) => Number(r.id) === projectId)
  }, [rows, projectId])

  const fromData = useMemo(
    () =>
      latestTimestamp(visibleRows.length ? visibleRows : portfolio, [
        'created_at',
        'updated_at',
      ]),
    [visibleRows, portfolio],
  )
  const pageUpdatedAt = useLastUpdated(projectId, fromData, 'all')

  const stats = useMemo(() => {
    const base = projectId == null ? portfolio : portfolio.filter((r) => Number(r.id) === projectId)
    const total = base.length
    const risky = base.filter((r) => Boolean(r.is_risky)).length
    const activeSprints = base.filter((r) => Boolean(r.active_sprint)).length
    return { total, risky, activeSprints }
  }, [portfolio, projectId])

  const initialFilters = useMemo((): Record<string, string> => {
    const f: Record<string, string> = {}
    if (statusFilter) f.status = statusFilter
    if (isRisky) f.is_risky = isRisky
    return f
  }, [statusFilter, isRisky])

  function openProject(row: Record<string, unknown>) {
    setSelected(row)
    setProjectId(Number(row.id))
  }

  return (
    <div>
      <PageHeader title="Projeler" updatedAt={pageUpdatedAt} />

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Link to="/projeler" className="block transition hover:opacity-95">
          <Card className="flex items-center gap-3 py-4">
            <div className="rounded-md bg-[#E8EEF5] p-2 text-navy-mid">
              <FolderKanban className="h-4 w-4" />
            </div>
            <div>
              <div className="text-[15px] font-medium tracking-wide text-muted">Toplam Proje</div>
              <div className="text-[36px] font-semibold tabular-nums leading-none text-ink">
                {stats.total}
              </div>
              <div className="mt-1 text-[12px] font-medium text-navy-mid">Detaya Git →</div>
            </div>
          </Card>
        </Link>
        <Link to="/projeler?is_risky=true" className="block transition hover:opacity-95">
          <Card className="flex items-center gap-3 py-4">
            <div className="rounded-md bg-[#F8EAEA] p-2 text-danger">
              <AlertTriangle className="h-4 w-4" />
            </div>
            <div>
              <div className="text-[15px] font-medium tracking-wide text-muted">Riskli Proje</div>
              <div className="text-[36px] font-semibold tabular-nums leading-none text-ink">
                {stats.risky}
              </div>
              <div className="mt-1 text-[12px] font-medium text-navy-mid">Detaya Git →</div>
            </div>
          </Card>
        </Link>
        <Card className="flex items-center gap-3 py-4">
          <div className="rounded-md bg-[#E8EEF5] p-2 text-navy-mid">
            <Timer className="h-4 w-4" />
          </div>
          <div>
            <div className="text-[15px] font-medium tracking-wide text-muted">Aktif Sprint</div>
            <div className="text-[36px] font-semibold tabular-nums leading-none text-ink">
              {stats.activeSprints}
            </div>
          </div>
        </Card>
      </div>

      <DataTable
        rows={visibleRows}
        initialFilters={initialFilters}
        searchKeys={['code', 'name', 'active_sprint']}
        filterOptions={[
          {
            key: 'is_risky',
            label: 'Risk',
            values: [
              { value: 'true', label: 'Riskli' },
              { value: 'false', label: 'Normal' },
            ],
          },
          {
            key: 'status',
            label: 'Durum',
            values: [
              { value: 'active', label: 'Aktif' },
              { value: 'planning', label: 'Planlama' },
              { value: 'testing', label: 'Testte' },
              { value: 'ready_for_release', label: 'Yayına Hazır' },
              { value: 'maintenance', label: 'Bakım' },
              { value: 'on_hold', label: 'Beklemede' },
              { value: 'completed', label: 'Tamamlandı' },
            ],
          },
        ]}
        onFilterChange={(next) => {
          const params = new URLSearchParams()
          if (next.is_risky) params.set('is_risky', next.is_risky)
          if (next.status) params.set('status', next.status)
          setSearchParams(params, { replace: true })
        }}
        columns={[
          {
            key: 'code',
            label: 'Kod',
            render: (r) => <span className="font-mono text-[16px] font-medium">{String(r.code)}</span>,
          },
          {
            key: 'name',
            label: 'Proje',
            render: (r) => (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  openProject(r)
                }}
                className="text-left font-medium text-navy-mid underline-offset-2 hover:underline"
              >
                {String(r.name)}
              </button>
            ),
          },
          {
            key: 'status',
            label: 'Durum',
            render: (r) => (
              <Badge tone={toneForStatus(String(r.status))}>{statusLabel(String(r.status))}</Badge>
            ),
          },
          {
            key: 'active_sprint',
            label: 'Aktif Sprint',
            render: (r) => {
              const sprint = String(r.active_sprint ?? '—')
              const done = Number(r.sprint_done ?? 0)
              const total = Number(r.sprint_total ?? 0)
              const pct = Number(r.sprint_progress_pct ?? 0)
              const hasSprint = Boolean(r.active_sprint)
              return (
                <span className="inline-flex flex-col gap-0.5">
                  <span className="inline-flex items-center gap-2">
                    <StatusDot
                      tone={hasSprint ? (pct >= 70 ? 'ok' : 'warn') : 'neutral'}
                      title={hasSprint ? `Sprint ilerleme %${pct}` : 'Sprint yok'}
                    />
                    {sprint}
                  </span>
                  {total > 0 ? (
                    <span className="pl-4 text-[13px] tabular-nums text-muted">
                      {done}/{total} görev · %{pct}
                    </span>
                  ) : null}
                </span>
              )
            },
          },
          {
            key: 'requirement_count',
            label: 'Gereksinim',
            render: (r) => (
              <Link
                to="/gereksinimler"
                onClick={() => setProjectId(Number(r.id))}
                className="tabular-nums font-medium text-navy-mid hover:underline"
                title="Gereksinimler ekranında doğrula"
              >
                {Number(r.requirement_count ?? 0)}
              </Link>
            ),
          },
          {
            key: 'open_bugs',
            label: 'Açık Hata',
            render: (r) => {
              const open = Number(r.open_bugs ?? 0)
              const c = Number(r.bugs_critical ?? r.critical_bugs ?? 0)
              const h = Number(r.bugs_high ?? 0)
              const m = Number(r.bugs_medium ?? 0)
              const l = Number(r.bugs_low ?? 0)
              const title = `${open} açık · ${c} kritik · ${h} yüksek · ${m} orta · ${l} düşük`
              return (
                <span className="inline-flex flex-col gap-0.5" title={title}>
                  <span className="inline-flex items-center gap-2">
                    <StatusDot
                      tone={c > 0 ? 'danger' : open > 0 ? 'warn' : 'ok'}
                      title={title}
                    />
                    <span className="tabular-nums">{open} açık</span>
                  </span>
                  {open > 0 ? (
                    <span className="pl-4 text-[12px] text-muted">
                      {c > 0 ? <span className="text-danger">{c} kritik</span> : null}
                      {c > 0 && (h > 0 || m > 0 || l > 0) ? ' · ' : null}
                      {h > 0 ? `${h} yüksek` : null}
                      {h > 0 && (m > 0 || l > 0) ? ' · ' : null}
                      {m > 0 ? `${m} orta` : null}
                      {(c > 0 || h > 0 || m > 0) && l > 0 ? ' · ' : null}
                      {l > 0 ? `${l} düşük` : null}
                    </span>
                  ) : null}
                </span>
              )
            },
          },
          {
            key: 'updated_at',
            label: 'Son Güncelleme',
            className: 'whitespace-nowrap',
            render: (r) => (
              <span className="text-[15px] tabular-nums text-muted">
                {formatRowUpdatedAt((r.updated_at as string) || (r.created_at as string))}
              </span>
            ),
          },
        ]}
      />

      <DetailPanel
        open={!!selected}
        title={String(selected?.name ?? '')}
        subtitle={String(selected?.code ?? '')}
        onClose={() => setSelected(null)}
      >
        {selected ? (
          <>
            <DetailField
              label="Durum"
              value={
                <Badge tone={toneForStatus(String(selected.status))}>
                  {statusLabel(String(selected.status))}
                </Badge>
              }
            />
            <DetailField
              label="Son Güncelleme"
              value={formatRowUpdatedAt(
                (selected.updated_at as string) || (selected.created_at as string),
              )}
            />
            <DetailField
              label="Risk"
              value={
                <Badge tone={selected.is_risky ? 'danger' : 'ok'}>
                  {selected.is_risky ? 'Riskli' : 'Normal'}
                </Badge>
              }
            />
            <DetailField
              label="Sprint"
              value={
                selected.active_sprint
                  ? `${String(selected.active_sprint)} · ${Number(selected.sprint_done ?? 0)}/${Number(selected.sprint_total ?? 0)} görev (%${Number(selected.sprint_progress_pct ?? 0)})`
                  : '—'
              }
            />
            <DetailField
              label="Son sürüm"
              value={
                selected.latest_release
                  ? `REL-${String((selected.latest_release as { version: string }).version)} · ${releaseStatusLabel(String((selected.latest_release as { status: string }).status))}`
                  : '—'
              }
            />
            <DetailField label="Açıklama" value={String(selected.description ?? '—')} />

            <div className="mt-4 border-t border-line pt-3">
              <div className="mb-2 text-[13px] font-semibold uppercase tracking-wide text-muted">
                Modül geçişleri
              </div>
              <div className="flex flex-col gap-2 text-[15px]">
                <Link
                  to="/gereksinimler"
                  onClick={() => setProjectId(Number(selected.id))}
                  className="font-medium text-navy-mid hover:underline"
                >
                  Gereksinimler ({Number(selected.requirement_count ?? 0)}) →
                </Link>
                <Link
                  to="/gorevler"
                  onClick={() => setProjectId(Number(selected.id))}
                  className="font-medium text-navy-mid hover:underline"
                >
                  Görevler ({Number(selected.task_count ?? 0)}) →
                </Link>
                <Link
                  to="/kod-degisiklikleri"
                  onClick={() => setProjectId(Number(selected.id))}
                  className="font-medium text-navy-mid hover:underline"
                >
                  Commitler ({Number(selected.commit_count ?? 0)}) →
                </Link>
                <Link
                  to="/testler"
                  onClick={() => setProjectId(Number(selected.id))}
                  className="font-medium text-navy-mid hover:underline"
                >
                  Testler ({Number(selected.test_count ?? 0)} · {Number(selected.failed_tests ?? 0)}{' '}
                  başarısız) →
                </Link>
                <Link
                  to="/hatalar?status=active"
                  onClick={() => setProjectId(Number(selected.id))}
                  className="font-medium text-navy-mid hover:underline"
                >
                  Açık hatalar ({Number(selected.open_bugs ?? 0)} · {Number(selected.critical_bugs ?? 0)}{' '}
                  kritik) →
                </Link>
                <Link
                  to="/release"
                  onClick={() => setProjectId(Number(selected.id))}
                  className="font-medium text-navy-mid hover:underline"
                >
                  Sürümler →
                </Link>
                <Link
                  to="/analiz"
                  onClick={() => setProjectId(Number(selected.id))}
                  className="font-medium text-navy-mid hover:underline"
                >
                  AI Analizi →
                </Link>
              </div>
            </div>
          </>
        ) : null}
      </DetailPanel>
    </div>
  )
}
