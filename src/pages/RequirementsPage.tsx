import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { PageHeader } from '@/components/ui/card'
import { DataTable } from '@/components/ui/data-table'
import { Badge, toneForStatus } from '@/components/ui/badge'
import { DetailPanel, DetailField } from '@/components/ui/detail-panel'
import { formatRowUpdatedAt, latestTimestamp, projectCode, statusLabel } from '@/lib/utils'
import { useProjectFilter } from '@/lib/project-filter'
import { useLastUpdated } from '@/lib/use-last-updated'

export function RequirementsPage() {
  const { projectId, querySuffix } = useProjectFilter()
  const [searchParams] = useSearchParams()
  const [rows, setRows] = useState<Record<string, unknown>[]>([])
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null)
  const q = searchParams.get('q') ?? ''

  useEffect(() => {
    api.requirements(`?limit=500${querySuffix}`).then(setRows).catch(console.error)
  }, [querySuffix])

  const fromData = useMemo(() => latestTimestamp(rows, ['updated_at']), [rows])
  const updatedAt = useLastUpdated(projectId, fromData, 'requirements')

  return (
    <div>
      <PageHeader title="Gereksinimler" updatedAt={updatedAt} />
      <DataTable
        rows={rows}
        initialSearch={q}
        searchKeys={['external_id', 'title', 'project_code', 'project_name', 'module']}
        filterOptions={[
          {
            key: 'status',
            label: 'Durum',
            values: [
              { value: 'changed', label: 'Revize Edildi' },
              { value: 'in_progress', label: 'Devam Ediyor' },
              { value: 'approved', label: 'Onaylı' },
              { value: 'done', label: 'Tamamlandı' },
              { value: 'draft', label: 'Taslak' },
            ],
          },
          {
            key: 'priority',
            label: 'Öncelik',
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
          { key: 'title', label: 'Başlık', className: 'max-w-[280px] truncate' },
          {
            key: 'priority',
            label: 'Öncelik',
            render: (r) => (
              <Badge tone={toneForStatus(String(r.priority))}>{statusLabel(String(r.priority))}</Badge>
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
            key: 'updated_at',
            label: 'Son Güncelleme',
            className: 'whitespace-nowrap',
            render: (r) => {
              const revisions = Number(r.revision_count ?? 0)
              return (
                <span className="inline-flex flex-col gap-0.5">
                  <span className="tabular-nums text-muted">
                    {formatRowUpdatedAt(r.updated_at as string)}
                  </span>
                  {revisions > 0 ? (
                    <span className="text-[13px] text-muted">{revisions} revizyon</span>
                  ) : null}
                </span>
              )
            },
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
            <DetailField label="Modül" value={String(selected.module ?? '—')} />
            <DetailField
              label="Öncelik"
              value={
                <Badge tone={toneForStatus(String(selected.priority))}>
                  {statusLabel(String(selected.priority))}
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
            <DetailField
              label="Son Güncelleme"
              value={formatRowUpdatedAt(selected.updated_at as string)}
            />
            <DetailField
              label="Revizyon"
              value={`${Number(selected.revision_count ?? 0)} revizyon`}
            />
          </>
        ) : null}
      </DetailPanel>
    </div>
  )
}
