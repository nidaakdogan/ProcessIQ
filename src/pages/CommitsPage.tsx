import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'
import { PageHeader } from '@/components/ui/card'
import { DataTable } from '@/components/ui/data-table'
import { Badge, toneForStatus } from '@/components/ui/badge'
import { DetailPanel, DetailField } from '@/components/ui/detail-panel'
import { formatRowUpdatedAt, latestTimestamp, projectCode, riskLabel } from '@/lib/utils'
import { useProjectFilter } from '@/lib/project-filter'
import { useLastUpdated } from '@/lib/use-last-updated'

function shortHash(hash: unknown) {
  const h = String(hash ?? '')
  return h.length > 8 ? `${h.slice(0, 7)}` : h
}

export function CommitsPage() {
  const { projectId, querySuffix } = useProjectFilter()
  const [searchParams] = useSearchParams()
  const [rows, setRows] = useState<Record<string, unknown>[]>([])
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null)

  const withinDays = searchParams.get('within_days')
  const committedFrom = searchParams.get('committed_from')
  const q = searchParams.get('q') ?? ''

  const sinceIso = useMemo(() => {
    if (committedFrom) return committedFrom
    if (withinDays) {
      const d = new Date()
      d.setDate(d.getDate() - Number(withinDays))
      return d.toISOString()
    }
    return null
  }, [committedFrom, withinDays])

  useEffect(() => {
    const params = new URLSearchParams()
    params.set('limit', '1000')
    if (sinceIso) params.set('since', sinceIso)
    api.commits(`?${params.toString()}${querySuffix}`).then(setRows).catch(console.error)
  }, [querySuffix, sinceIso])

  const fromData = useMemo(() => latestTimestamp(rows, ['committed_at']), [rows])
  const updatedAt = useLastUpdated(projectId, fromData, 'commits')

  return (
    <div>
      <PageHeader title="Kod Değişiklikleri" updatedAt={updatedAt} />
      <DataTable
        rows={rows}
        onRowClick={setSelected}
        initialSearch={q}
        searchKeys={[
          'commit_hash',
          'message',
          'branch',
          'developer',
          'project_code',
          'requirement_external_id',
          'task_external_id',
        ]}
        filterOptions={[
          {
            key: 'risk_level',
            label: 'Risk',
            values: [
              { value: 'high', label: 'Yüksek' },
              { value: 'medium', label: 'Orta' },
              { value: 'low', label: 'Düşük' },
            ],
          },
        ]}
        columns={[
          {
            key: 'commit_hash',
            label: 'Commit',
            className: 'w-[1%] pr-2',
            render: (r) => (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation()
                  setSelected(r)
                }}
                className="font-mono text-[15px] font-semibold text-navy-mid underline-offset-2 hover:underline"
                title={String(r.commit_hash)}
              >
                {shortHash(r.commit_hash)}
              </button>
            ),
          },
          {
            key: 'project_code',
            label: 'Proje',
            className: 'w-[1%] whitespace-nowrap',
            render: (r) => (
              <span className="font-mono text-[15px] font-medium">{projectCode(r.project_code)}</span>
            ),
          },
          {
            key: 'message',
            label: 'Açıklama',
            // max-w-0: tablo hücresinde truncate’in çalışması için gerekli
            className: 'w-[42%] max-w-0',
            render: (r) => (
              <span className="block truncate text-[16px]" title={String(r.message)}>
                {String(r.message)}
              </span>
            ),
          },
          {
            key: 'branch',
            label: 'Dal',
            className: 'w-[12%] max-w-0',
            render: (r) => (
              <span className="block truncate font-mono text-[14px] text-muted" title={String(r.branch)}>
                {String(r.branch)}
              </span>
            ),
          },
          {
            key: 'developer',
            label: 'Geliştirici',
            className: 'w-[11%] max-w-0',
            render: (r) => (
              <span className="block truncate text-[15px]" title={String(r.developer)}>
                {String(r.developer)}
              </span>
            ),
          },
          {
            key: 'files_changed',
            label: 'Dosya',
            className: 'w-[1%] tabular-nums',
            render: (r) => <span className="text-[15px] tabular-nums">{String(r.files_changed ?? '—')}</span>,
          },
          {
            key: 'risk_level',
            label: 'Risk',
            className: 'w-[1%]',
            render: (r) => (
              <Badge tone={toneForStatus(String(r.risk_level))}>
                {riskLabel(String(r.risk_level))}
              </Badge>
            ),
          },
          {
            key: 'updated_at',
            label: 'Son Güncelleme',
            className: 'w-[1%] whitespace-nowrap',
            render: (r) => (
              <span className="text-[15px] tabular-nums text-muted">
                {formatRowUpdatedAt(
                  (r.updated_at as string) || (r.committed_at as string),
                )}
              </span>
            ),
          },
        ]}
      />
      <DetailPanel
        open={!!selected}
        title={shortHash(selected?.commit_hash) || 'Kod değişikliği'}
        subtitle={String(selected?.commit_hash ?? '')}
        onClose={() => setSelected(null)}
      >
        {selected ? (
          <>
            <DetailField
              label="Açıklama"
              value={
                <span className="whitespace-normal break-words">{String(selected.message ?? '—')}</span>
              }
            />
            <DetailField label="Proje" value={String(selected.project_name ?? '—')} />
            <DetailField
              label="Commit"
              value={<span className="font-mono text-[16px]">{String(selected.commit_hash)}</span>}
            />
            <DetailField
              label="Dal"
              value={<span className="font-mono text-[16px]">{String(selected.branch)}</span>}
            />
            <DetailField label="Geliştirici" value={String(selected.developer)} />
            <DetailField label="Dosya" value={String(selected.files_changed ?? '—')} />
            <DetailField
              label="Değişiklik"
              value={
                <span className="font-mono text-[16px]">
                  <span className="text-ok">+{String(selected.additions ?? 0)}</span>
                  {' / '}
                  <span className="text-danger">−{String(selected.deletions ?? 0)}</span>
                </span>
              }
            />
            <DetailField
              label="Risk"
              value={
                <Badge tone={toneForStatus(String(selected.risk_level))}>
                  {riskLabel(String(selected.risk_level))}
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
              label="Görev"
              value={<span className="font-mono">{String(selected.task_external_id ?? '—')}</span>}
            />
            <DetailField
              label="Son Güncelleme"
              value={formatRowUpdatedAt(
                (selected.updated_at as string) || (selected.committed_at as string),
              )}
            />
          </>
        ) : null}
      </DetailPanel>
    </div>
  )
}
