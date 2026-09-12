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

export function TestsPage() {
  const { projectId, querySuffix } = useProjectFilter()
  const [searchParams] = useSearchParams()
  const [rows, setRows] = useState<Record<string, unknown>[]>([])
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null)

  const result = searchParams.get('result') ?? ''
  const executedFrom = searchParams.get('executed_from') ?? ''
  const executedTo = searchParams.get('executed_to') ?? ''
  const q = searchParams.get('q') ?? ''

  useEffect(() => {
    const params = new URLSearchParams()
    params.set('limit', '500')
    if (result) params.set('result', result)
    if (executedFrom) params.set('executed_from', executedFrom)
    if (executedTo) params.set('executed_to', executedTo)
    const extra = params.toString()
    api.tests(`?${extra}${querySuffix}`).then(setRows).catch(console.error)
  }, [querySuffix, result, executedFrom, executedTo])

  const fromData = useMemo(() => latestTimestamp(rows, ['executed_at']), [rows])
  const updatedAt = useLastUpdated(projectId, fromData, 'tests')

  return (
    <div>
      <PageHeader title="Testler" updatedAt={updatedAt} />
      <DataTable
        rows={rows}
        initialFilters={result ? { result } : {}}
        initialSearch={q}
        searchKeys={['external_id', 'title', 'project_code', 'requirement_external_id']}
        filterOptions={[
          {
            key: 'result',
            label: 'Sonuç',
            values: [
              { value: 'failed', label: 'Başarısız' },
              { value: 'passed', label: 'Geçti' },
              { value: 'skipped', label: 'Atlandı' },
            ],
          },
        ]}
        columns={[
          {
            key: 'external_id',
            label: 'Test ID',
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
          {
            key: 'title',
            label: 'Test Adı',
            className: 'max-w-[280px]',
            render: (r) => (
              <span className="line-clamp-2 whitespace-normal text-[16px]">{String(r.title)}</span>
            ),
          },
          {
            key: 'result',
            label: 'Sonuç',
            render: (r) => (
              <Badge tone={toneForStatus(String(r.result))}>{statusLabel(String(r.result))}</Badge>
            ),
          },
          {
            key: 'updated_at',
            label: 'Son Güncelleme',
            className: 'whitespace-nowrap',
            render: (r) => (
              <span className="text-[15px] tabular-nums text-muted">
                {formatRowUpdatedAt(
                  (r.updated_at as string) || (r.executed_at as string),
                )}
              </span>
            ),
          },
        ]}
      />
      <DetailPanel
        open={!!selected}
        title={String(selected?.title ?? 'Test')}
        subtitle={String(selected?.external_id ?? '')}
        onClose={() => setSelected(null)}
      >
        {selected ? (
          <>
            <DetailField label="Proje" value={String(selected.project_name ?? '—')} />
            <DetailField
              label="Sonuç"
              value={
                <Badge tone={toneForStatus(String(selected.result))}>
                  {statusLabel(String(selected.result))}
                </Badge>
              }
            />
            <DetailField
              label="Gereksinim"
              value={
                <span className="font-mono">{String(selected.requirement_external_id ?? '—')}</span>
              }
            />
            <DetailField
              label="Son Güncelleme"
              value={formatRowUpdatedAt(
                (selected.updated_at as string) || (selected.executed_at as string),
              )}
            />
          </>
        ) : null}
      </DetailPanel>
    </div>
  )
}
