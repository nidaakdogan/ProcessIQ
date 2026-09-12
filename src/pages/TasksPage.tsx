import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { PageHeader } from '@/components/ui/card'
import { DataTable } from '@/components/ui/data-table'
import { Badge, toneForStatus } from '@/components/ui/badge'
import { DetailPanel, DetailField } from '@/components/ui/detail-panel'
import { cn, formatDelay, formatHours, formatRowUpdatedAt, latestTimestamp, projectCode, statusLabel } from '@/lib/utils'
import { useProjectFilter } from '@/lib/project-filter'
import { useLastUpdated } from '@/lib/use-last-updated'

export function TasksPage() {
  const { projectId, querySuffix } = useProjectFilter()
  const [searchParams] = useSearchParams()
  const [rows, setRows] = useState<Record<string, unknown>[]>([])
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null)

  const isDelayed = searchParams.get('is_delayed') ?? ''
  const isOverrun = searchParams.get('is_overrun') ?? ''
  const statusFilter = searchParams.get('status') ?? ''
  const reqStatus = searchParams.get('req_status') ?? ''
  const hasFailedTest = searchParams.get('has_failed_test') ?? ''
  const updatedFrom = searchParams.get('updated_from') ?? ''
  const updatedTo = searchParams.get('updated_to') ?? ''
  const q = searchParams.get('q') ?? ''

  useEffect(() => {
    const params = new URLSearchParams()
    params.set('limit', '500')
    if (statusFilter) params.set('status', statusFilter)
    if (updatedFrom) params.set('updated_from', updatedFrom)
    if (updatedTo) params.set('updated_to', updatedTo)
    if (isDelayed === 'true' || isDelayed === 'false') params.set('is_delayed', isDelayed)
    if (isOverrun === 'true' || isOverrun === 'false') params.set('is_overrun', isOverrun)
    if (reqStatus) params.set('req_status', reqStatus)
    if (hasFailedTest === 'true' || hasFailedTest === 'false') {
      params.set('has_failed_test', hasFailedTest)
    }
    api.tasks(`?${params.toString()}${querySuffix}`).then(setRows).catch(console.error)
  }, [
    querySuffix,
    updatedFrom,
    updatedTo,
    statusFilter,
    isDelayed,
    isOverrun,
    reqStatus,
    hasFailedTest,
  ])

  const initialFilters = useMemo(() => {
    const f: Record<string, string> = {}
    if (isDelayed) f.is_delayed = isDelayed
    if (isOverrun) f.is_overrun = isOverrun
    if (statusFilter) f.status = statusFilter
    if (reqStatus) f.requirement_status = reqStatus
    if (hasFailedTest) f.has_failed_test = hasFailedTest
    return f
  }, [isDelayed, isOverrun, statusFilter, reqStatus, hasFailedTest])

  const fromData = useMemo(() => latestTimestamp(rows, ['updated_at']), [rows])
  const updatedAt = useLastUpdated(projectId, fromData, 'tasks')

  return (
    <div>
      <PageHeader title="Görevler" updatedAt={updatedAt} />
      <DataTable
        rows={rows}
        initialFilters={initialFilters}
        initialSearch={q}
        searchKeys={[
          'external_id',
          'title',
          'assignee',
          'project_code',
          'requirement_external_id',
          'sprint',
        ]}
        filterOptions={[
          {
            key: 'is_delayed',
            label: 'Gecikme',
            values: [
              { value: 'true', label: 'Geciken' },
              { value: 'false', label: 'Zamanında' },
            ],
          },
          {
            key: 'is_overrun',
            label: 'Süre Aşımı',
            values: [
              { value: 'true', label: 'Aşım var' },
              { value: 'false', label: 'Aşım yok' },
            ],
          },
          {
            key: 'has_failed_test',
            label: 'Başarısız Test Bağı',
            values: [
              { value: 'true', label: 'Var' },
              { value: 'false', label: 'Yok' },
            ],
          },
          {
            key: 'requirement_status',
            label: 'Gereksinim Durumu',
            values: [
              { value: 'changed', label: 'Revize Edildi' },
              { value: 'in_progress', label: 'Devam Ediyor' },
              { value: 'approved', label: 'Onaylı' },
              { value: 'done', label: 'Tamamlandı' },
            ],
          },
          {
            key: 'status',
            label: 'Durum',
            values: [
              { value: 'todo', label: 'Yapılacak' },
              { value: 'in_progress', label: 'Devam Ediyor' },
              { value: 'blocked', label: 'Bloke' },
              { value: 'done', label: 'Tamamlandı' },
            ],
          },
        ]}
        columns={[
          {
            key: 'external_id',
            label: 'ID',
            render: (r) => (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  setSelected(r)
                }}
                className="font-mono text-[16px] font-semibold text-navy-mid underline-offset-2 hover:underline"
              >
                {String(r.external_id)}
              </button>
            ),
          },
          {
            key: 'project_code',
            label: 'Proje',
            render: (r) => (
              <span className="font-mono text-[16px] font-medium">{projectCode(r.project_code)}</span>
            ),
          },
          {
            key: 'requirement_external_id',
            label: 'Gereksinim',
            render: (r) => (
              <span className="font-mono text-[16px]">{String(r.requirement_external_id ?? '—')}</span>
            ),
          },
          { key: 'assignee', label: 'Sorumlu' },
          {
            key: 'status',
            label: 'Durum',
            render: (r) => (
              <Badge tone={toneForStatus(String(r.status))}>{statusLabel(String(r.status))}</Badge>
            ),
          },
          { key: 'sprint', label: 'Sprint' },
          {
            key: 'estimated_hours',
            label: 'Tahmini Süre',
            render: (r) => (
              <span className="tabular-nums">{formatHours(r.estimated_hours as number)}</span>
            ),
          },
          {
            key: 'actual_hours',
            label: 'Gerçek Süre',
            render: (r) => {
              const overrun = Boolean(r.is_overrun)
              const severe =
                typeof r.actual_hours === 'number' &&
                typeof r.estimated_hours === 'number' &&
                r.actual_hours > r.estimated_hours * 1.2
              return (
                <span
                  className={cn(
                    'tabular-nums font-medium',
                    overrun && (severe ? 'text-danger' : 'text-warn'),
                  )}
                >
                  {formatHours(r.actual_hours as number | null)}
                </span>
              )
            },
          },
          {
            key: 'delay_hours',
            label: 'Gecikme',
            sortable: true,
            render: (r) => {
              const delay = formatDelay(
                r.estimated_hours as number | null,
                r.actual_hours as number | null,
                r.status === 'blocked',
              )
              const toneClass =
                delay.tone === 'danger'
                  ? 'text-danger'
                  : delay.tone === 'warn'
                    ? 'text-warn'
                    : delay.tone === 'ok'
                      ? 'text-ok'
                      : 'text-muted'
              return <span className={cn('tabular-nums text-[16px] font-medium', toneClass)}>{delay.label}</span>
            },
          },
          {
            key: 'updated_at',
            label: 'Son Güncelleme',
            className: 'whitespace-nowrap',
            render: (r) => (
              <span className="text-[15px] tabular-nums text-muted">
                {formatRowUpdatedAt(r.updated_at as string)}
              </span>
            ),
          },
        ]}
      />
      <DetailPanel
        open={!!selected}
        title={String(selected?.title ?? '')}
        subtitle={String(selected?.external_id ?? '')}
        onClose={() => setSelected(null)}
      >
        {selected ? (
          <>
            <DetailField label="Proje" value={String(selected.project_name ?? '—')} />
            <DetailField
              label="Gereksinim"
              value={
                <span className="font-mono">{String(selected.requirement_external_id ?? '—')}</span>
              }
            />
            <DetailField label="Sorumlu" value={String(selected.assignee)} />
            <DetailField label="Sprint" value={String(selected.sprint ?? '—')} />
            <DetailField
              label="Durum"
              value={
                <Badge tone={toneForStatus(String(selected.status))}>
                  {statusLabel(String(selected.status))}
                </Badge>
              }
            />
            <DetailField label="Tahmini Süre" value={formatHours(selected.estimated_hours as number)} />
            <DetailField
              label="Gerçek Süre"
              value={
                <span className={cn(Boolean(selected.is_overrun) && 'font-medium text-danger')}>
                  {formatHours(selected.actual_hours as number | null)}
                </span>
              }
            />
            <DetailField
              label="Gecikme"
              value={
                formatDelay(
                  selected.estimated_hours as number | null,
                  selected.actual_hours as number | null,
                  selected.status === 'blocked',
                ).label
              }
            />
            <DetailField
              label="Son Güncelleme"
              value={formatRowUpdatedAt(selected.updated_at as string)}
            />
          </>
        ) : null}
      </DetailPanel>
    </div>
  )
}
