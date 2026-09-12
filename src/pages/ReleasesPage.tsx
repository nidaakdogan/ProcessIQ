import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { Card, PageHeader } from '@/components/ui/card'
import { DataTable } from '@/components/ui/data-table'
import { Badge, toneForStatus } from '@/components/ui/badge'
import { DetailPanel, DetailField } from '@/components/ui/detail-panel'
import { cn, formatDate, formatRowUpdatedAt, latestTimestamp, releaseStatusLabel, type StatusTone } from '@/lib/utils'
import { useProjectFilter } from '@/lib/project-filter'
import { useLastUpdated } from '@/lib/use-last-updated'

function riskTone(score: number): StatusTone {
  if (score >= 70) return 'danger'
  if (score >= 40) return 'warn'
  return 'ok'
}

function riskBandLabel(score: number) {
  if (score >= 70) return 'Yüksek'
  if (score >= 40) return 'Orta'
  return 'Düşük'
}

export function ReleasesPage() {
  const { projectId, querySuffix } = useProjectFilter()
  const [searchParams, setSearchParams] = useSearchParams()
  const [rows, setRows] = useState<Record<string, unknown>[]>([])
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null)
  const isRisky = searchParams.get('is_risky') ?? ''
  const isActive = searchParams.get('is_active') ?? ''
  const q = searchParams.get('q') ?? ''

  useEffect(() => {
    const params = new URLSearchParams()
    params.set('limit', '200')
    // Riskli KPI: skor ≥70 ve durum ≠ yayında (is_risky zaten is_active içerir)
    if (isRisky === 'true' || isRisky === 'false') {
      params.set('is_risky', isRisky)
    } else if (isActive === 'true' || isActive === 'false') {
      // Grafik kapsamı: yalnızca yayında olmayan
      params.set('is_active', isActive)
    }
    api.releases(`?${params.toString()}${querySuffix}`).then(setRows).catch(console.error)
  }, [querySuffix, isRisky, isActive])

  const initialFilters = useMemo((): Record<string, string> => {
    const f: Record<string, string> = {}
    if (isRisky) f.is_risky = isRisky
    if (isActive && !isRisky) f.is_active = isActive
    return f
  }, [isRisky, isActive])

  const fromData = useMemo(
    () => latestTimestamp(rows, ['release_date', 'created_at', 'updated_at']),
    [rows],
  )
  const updatedAt = useLastUpdated(projectId, fromData, 'releases')

  return (
    <div>
      <PageHeader title="Sürümler" updatedAt={updatedAt} />

      <Card className="mb-4 py-3">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[15px] text-muted">
          <span className="font-semibold text-ink">Risk Skoru:</span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-ok" />
            0–39 Düşük
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-warn" />
            40–69 Orta
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-danger" />
            70–100 Yüksek
          </span>
          <span className="text-muted/80">
            Yayında kayıtlar için skor, canlı risk değil; yayın anındaki değerlendirmedir.
          </span>
        </div>
      </Card>

      <DataTable
        rows={rows}
        initialFilters={initialFilters}
        initialSearch={q}
        searchKeys={['version', 'project_code', 'project_name', 'status']}
        filterOptions={[
          {
            key: 'is_risky',
            label: 'Riskli KPI',
            values: [
              { value: 'true', label: 'Riskli (≥70, yayında değil)' },
              { value: 'false', label: 'Riskli değil' },
            ],
          },
          {
            key: 'is_active',
            label: 'Yayın',
            values: [
              { value: 'true', label: 'Yayında değil' },
              { value: 'false', label: 'Yayında' },
            ],
          },
          {
            key: 'status',
            label: 'Durum',
            values: [
              { value: 'planned', label: 'Planlandı' },
              { value: 'in_progress', label: 'Hazırlanıyor' },
              { value: 'ready', label: 'Yayın İçin Hazır' },
              { value: 'delayed', label: 'Gecikmiş' },
              { value: 'released', label: 'Yayında' },
            ],
          },
        ]}
        onFilterChange={(next) => {
          const params = new URLSearchParams(searchParams)
          if (next.is_risky) {
            params.set('is_risky', next.is_risky)
            params.delete('is_active')
          } else {
            params.delete('is_risky')
            if (next.is_active) params.set('is_active', next.is_active)
            else params.delete('is_active')
          }
          setSearchParams(params, { replace: true })
        }}
        columns={[
          {
            key: 'version',
            label: 'Sürüm',
            render: (r) => (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  setSelected(r)
                }}
                className="font-mono text-[16px] font-semibold text-navy-mid underline-offset-2 hover:underline"
              >
                REL-{String(r.version)}
              </button>
            ),
          },
          {
            key: 'project_code',
            label: 'Proje',
            render: (r) => (
              <span className="font-mono text-[16px] font-medium">{String(r.project_code ?? '—')}</span>
            ),
          },
          {
            key: 'release_date',
            label: 'Yayın Tarihi',
            render: (r) => formatDate(r.release_date as string),
          },
          {
            key: 'status',
            label: 'Durum',
            render: (r) => (
              <Badge tone={toneForStatus(String(r.status))}>{releaseStatusLabel(String(r.status))}</Badge>
            ),
          },
          {
            key: 'risk_score',
            label: 'Risk Skoru',
            render: (r) => {
              const score = Number(r.risk_score)
              const historical = Boolean(r.risk_is_historical)
              return (
                <span className="inline-flex flex-col gap-0.5">
                  <Badge tone={riskTone(score)}>
                    {score.toLocaleString('tr-TR')} · {riskBandLabel(score)}
                  </Badge>
                  {historical ? (
                    <span className="text-[13px] text-muted">Yayın anı</span>
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
                {formatRowUpdatedAt(
                  (r.updated_at as string) || (r.created_at as string),
                )}
              </span>
            ),
          },
        ]}
      />

      <DetailPanel
        open={!!selected}
        title={`Sürüm ${String(selected?.version ?? '')}`}
        subtitle={`REL-${String(selected?.version ?? '')}`}
        onClose={() => setSelected(null)}
      >
        {selected ? (
          <>
            <DetailField label="Proje" value={String(selected.project_name ?? '—')} />
            <DetailField label="Sürüm" value={`REL-${String(selected.version)}`} />
            <DetailField label="Yayın Tarihi" value={formatDate(selected.release_date as string)} />
            <DetailField
              label="Son Güncelleme"
              value={formatRowUpdatedAt(
                (selected.updated_at as string) || (selected.created_at as string),
              )}
            />
            <DetailField
              label="Durum"
              value={
                <Badge tone={toneForStatus(String(selected.status))}>
                  {releaseStatusLabel(String(selected.status))}
                </Badge>
              }
            />
            <DetailField
              label="Risk Skoru"
              value={
                <div className="space-y-1">
                  <Badge tone={riskTone(Number(selected.risk_score))}>
                    {Number(selected.risk_score).toLocaleString('tr-TR')} ·{' '}
                    {riskBandLabel(Number(selected.risk_score))}
                  </Badge>
                  <p className={cn('text-xs text-muted')}>
                    {selected.risk_is_historical
                      ? 'Bu skor yayın anındaki risk değerlendirmesidir; canlı ortam riskini temsil etmez.'
                      : '0–39 Düşük · 40–69 Orta · 70–100 Yüksek'}
                  </p>
                </div>
              }
            />
            <DetailField label="Notlar" value={String(selected.notes ?? '—')} />
          </>
        ) : null}
      </DetailPanel>
    </div>
  )
}
