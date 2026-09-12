import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { PageHeader } from '@/components/ui/card'
import { DataTable } from '@/components/ui/data-table'
import { Badge, toneForStatus } from '@/components/ui/badge'
import { DetailPanel, DetailField } from '@/components/ui/detail-panel'
import { formatDate, formatRowUpdatedAt, latestTimestamp, projectCode, statusLabel } from '@/lib/utils'
import { useProjectFilter } from '@/lib/project-filter'
import { useLastUpdated } from '@/lib/use-last-updated'

export function BugsPage() {
  const { projectId, querySuffix } = useProjectFilter()
  const [searchParams] = useSearchParams()
  const [rows, setRows] = useState<Record<string, unknown>[]>([])
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null)

  const severity = searchParams.get('severity') ?? ''
  const status = searchParams.get('status') ?? ''
  const createdFrom = searchParams.get('created_from') ?? ''
  const createdTo = searchParams.get('created_to') ?? ''
  const q = searchParams.get('q') ?? ''

  useEffect(() => {
    const params = new URLSearchParams()
    params.set('limit', '500')
    if (severity) params.set('severity', severity)
    // status=active → API OPEN+IN_PROGRESS (Dashboard kritik KPI ile aynı)
    if (status) params.set('status', status)
    if (createdFrom) params.set('created_from', createdFrom)
    if (createdTo) params.set('created_to', createdTo)
    api.bugs(`?${params.toString()}${querySuffix}`).then(setRows).catch(console.error)
  }, [querySuffix, severity, status, createdFrom, createdTo])

  const initialFilters = useMemo(() => {
    const f: Record<string, string> = {}
    if (severity) f.severity = severity
    if (status === 'active') f.is_active = 'true'
    else if (status) f.status = status
    return f
  }, [severity, status])

  const fromData = useMemo(
    () => latestTimestamp(rows, ['updated_at', 'created_at']),
    [rows],
  )
  const updatedAt = useLastUpdated(projectId, fromData, 'bugs')

  return (
    <div>
      <PageHeader title="Hatalar" updatedAt={updatedAt} />
      <DataTable
        rows={rows}
        initialFilters={initialFilters}
        initialSearch={q}
        searchKeys={[
          'external_id',
          'title',
          'project_code',
          'requirement_external_id',
          'test_external_id',
        ]}
        filterOptions={[
          {
            key: 'is_active',
            label: 'Akış',
            values: [
              { value: 'true', label: 'Aktif (açık)' },
              { value: 'false', label: 'Kapalı akış' },
            ],
          },
          {
            key: 'status',
            label: 'Durum',
            values: [
              { value: 'open', label: 'Açık' },
              { value: 'reviewing', label: 'İnceleniyor' },
              { value: 'in_development', label: 'Çözüm Geliştiriliyor' },
              { value: 'in_test', label: 'Testte' },
              { value: 'closed', label: 'Kapatıldı' },
            ],
          },
          {
            key: 'severity',
            label: 'Etki Seviyesi',
            values: [
              { value: 'critical', label: 'Kritik' },
              { value: 'high', label: 'Yüksek' },
              { value: 'medium', label: 'Orta' },
              { value: 'low', label: 'Düşük' },
            ],
          },
        ]}
        columns={[
          {
            key: 'external_id',
            label: 'Bug ID',
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
            key: 'title',
            label: 'Başlık',
            className: 'max-w-[240px]',
            render: (r) => (
              <span className="line-clamp-2 whitespace-normal text-[16px]">{String(r.title)}</span>
            ),
          },
          {
            key: 'priority',
            label: 'Öncelik',
            render: (r) => (
              <Badge tone={toneForStatus(String(r.priority))}>{statusLabel(String(r.priority))}</Badge>
            ),
          },
          {
            key: 'severity',
            label: 'Etki Seviyesi',
            render: (r) => (
              <Badge tone={toneForStatus(String(r.severity))}>{statusLabel(String(r.severity))}</Badge>
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
            key: 'requirement_external_id',
            label: 'Gereksinim',
            render: (r) => (
              <span className="font-mono text-[16px]">{String(r.requirement_external_id ?? '—')}</span>
            ),
          },
          {
            key: 'test_external_id',
            label: 'Test',
            render: (r) => (
              <span className="font-mono text-[16px]">{String(r.test_external_id ?? '—')}</span>
            ),
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
        title={String(selected?.title ?? '')}
        subtitle={String(selected?.external_id ?? '')}
        onClose={() => setSelected(null)}
      >
        {selected ? (
          <>
            <DetailField label="Proje" value={String(selected.project_name ?? '—')} />
            <DetailField
              label="Öncelik"
              value={
                <Badge tone={toneForStatus(String(selected.priority))}>
                  {statusLabel(String(selected.priority))}
                </Badge>
              }
            />
            <DetailField
              label="Etki Seviyesi"
              value={
                <Badge tone={toneForStatus(String(selected.severity))}>
                  {statusLabel(String(selected.severity))}
                </Badge>
              }
            />
            <DetailField
              label="Durum"
              value={
                <Badge tone={toneForStatus(String(selected.status))}>
                  {statusLabel(String(selected.status))}
                </Badge>
              }
            />
            <DetailField label="Atanan" value={String(selected.assignee ?? '—')} />
            <DetailField label="Açılma Tarihi" value={formatDate(selected.created_at as string)} />
            <DetailField
              label="Son Güncelleme"
              value={formatRowUpdatedAt(
                (selected.updated_at as string) || (selected.created_at as string),
              )}
            />
            <DetailField
              label="Gereksinim"
              value={
                <span className="font-mono">{String(selected.requirement_external_id ?? '—')}</span>
              }
            />
            <DetailField
              label="Test"
              value={<span className="font-mono">{String(selected.test_external_id ?? '—')}</span>}
            />
          </>
        ) : null}
      </DetailPanel>
    </div>
  )
}
