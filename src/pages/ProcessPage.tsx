import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { api, type ProcessChain, type ProcessNode } from '@/lib/api'
import { Card, PageHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { DetailPanel, DetailField } from '@/components/ui/detail-panel'
import { cn, statusLabel, toneForStatus, type StatusTone } from '@/lib/utils'
import { useProjectFilter } from '@/lib/project-filter'
import { useLastUpdated } from '@/lib/use-last-updated'

const KIND_LABEL: Record<string, string> = {
  requirement: 'Gereksinim',
  task: 'Görev',
  commit: 'Kod Değişikliği',
  test: 'Test',
  bug: 'Hata',
  release: 'Sürüm',
}

const KIND_PATH: Record<string, string> = {
  requirement: '/gereksinimler',
  task: '/gorevler',
  commit: '/kod-degisiklikleri',
  test: '/testler',
  bug: '/hatalar',
  release: '/release',
}

function severityBorder(severity: string) {
  if (severity === 'critical') return 'border-danger/40 bg-[#FDF6F6]'
  if (severity === 'warning') return 'border-warn/40 bg-[#FFFBF5]'
  return 'border-line bg-panel'
}

function reasonTone(severity: string): StatusTone {
  if (severity === 'critical') return 'danger'
  if (severity === 'warning') return 'warn'
  if (severity === 'done') return 'ok'
  return 'neutral'
}

/** Kartta kısa etiket; tam metin detay panelinde */
function shortReason(reason: string | null | undefined, status: string): string {
  if (!reason) return statusLabel(status)
  const r = reason.toLowerCase()
  if (r.includes('yüksek') && r.includes('risk')) return 'Yüksek risk'
  if (r.includes('orta') && r.includes('risk')) return 'Orta risk'
  if (r.includes('yayında')) return 'Yayında'
  if (r.includes('bloke')) return 'Bloke'
  if (r.includes('gecikme') || r.includes('süre aş')) return 'Gecikme'
  if (r.includes('başarısız')) return 'Başarısız'
  if (r.includes('kritik')) return 'Kritik açık'
  if (r.includes('revize')) return 'Revize'
  if (r.includes('değişti')) return 'Değişti'
  if (r.includes('tamamlanmadı')) return 'Açık'
  if (reason.length > 22) return `${reason.slice(0, 20)}…`
  return reason
}

function shortTitle(title: string) {
  const t = title.trim()
  if (t.length <= 36) return t
  return `${t.slice(0, 34)}…`
}

function NodeCard({
  node,
  active,
  onClick,
}: {
  node: ProcessNode
  active: boolean
  onClick: () => void
}) {
  const badgeLabel = shortReason(node.reason, node.status)
  const badgeTone = node.reason
    ? reasonTone(node.severity)
    : toneForStatus(node.status)

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'flex h-[128px] w-[158px] shrink-0 flex-col rounded-lg border px-3 py-2.5 text-left transition duration-150',
        'hover:shadow-sm hover:border-navy-mid/35',
        severityBorder(node.severity),
        active && 'ring-2 ring-navy-mid/45',
      )}
    >
      <div className="text-[12px] font-semibold uppercase tracking-wide text-muted">
        {KIND_LABEL[node.kind] ?? node.kind}
      </div>
      <div className="mt-1 truncate font-mono text-[15px] font-semibold text-ink">{node.id}</div>
      <div className="mt-1 line-clamp-1 text-[14px] leading-snug text-ink/75" title={node.title}>
        {shortTitle(node.title)}
      </div>
      <div className="mt-auto pt-2">
        <Badge tone={badgeTone} className="max-w-full truncate px-2 py-0.5 text-[13px]">
          {badgeLabel}
        </Badge>
      </div>
    </button>
  )
}

export function ProcessPage() {
  const { projectId, projects, setProjectId } = useProjectFilter()
  const [chains, setChains] = useState<ProcessChain[]>([])
  const [selected, setSelected] = useState<ProcessNode | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [releaseFilter, setReleaseFilter] = useState('')
  const [riskFilter, setRiskFilter] = useState('')
  const [dataLoadedAt, setDataLoadedAt] = useState<string | null>(null)

  useEffect(() => {
    setChains([])
    setDataLoadedAt(null)
    api
      .processChains(20, projectId)
      .then((rows) => {
        setChains(rows)
        setDataLoadedAt(new Date().toISOString())
      })
      .catch((e) => setError(e.message))
  }, [projectId])

  const updatedAt = useLastUpdated(projectId, dataLoadedAt, 'process')

  const releases = useMemo(() => {
    const set = new Set<string>()
    chains.forEach((c) => {
      if (c.release_version) set.add(c.release_version)
    })
    return [...set].sort()
  }, [chains])

  const filtered = useMemo(() => {
    return chains.filter((c) => {
      if (releaseFilter && c.release_version !== releaseFilter) return false
      if (riskFilter && c.severity !== riskFilter) return false
      return true
    })
  }, [chains, releaseFilter, riskFilter])

  const selectedChain = useMemo(() => {
    if (!selected) return null
    return (
      chains.find((c) => c.nodes.some((n) => n.id === selected.id && n.kind === selected.kind)) ??
      null
    )
  }, [chains, selected])

  function scopeProjectFromChain() {
    if (!selectedChain?.project_code) return
    const p = projects.find((x) => x.code === selectedChain.project_code)
    if (p) setProjectId(p.id)
  }

  return (
    <div>
      <PageHeader title="Süreç Görünümü" updatedAt={updatedAt} />

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <select
          value={releaseFilter}
          onChange={(e) => setReleaseFilter(e.target.value)}
          className="h-10 rounded-md border border-line bg-panel px-3 text-[15px] outline-none focus:border-navy-mid"
        >
          <option value="">Sürüm: Tümü</option>
          {releases.map((v) => (
            <option key={v} value={v}>
              {v}
            </option>
          ))}
        </select>
        <select
          value={riskFilter}
          onChange={(e) => setRiskFilter(e.target.value)}
          className="h-10 rounded-md border border-line bg-panel px-3 text-[15px] outline-none focus:border-navy-mid"
        >
          <option value="">Risk: Tümü</option>
          <option value="critical">Kritik</option>
          <option value="warning">Uyarı</option>
          <option value="normal">Normal</option>
        </select>
        <div className="ml-auto flex flex-wrap gap-3 text-[14px] text-muted">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-slate-300" /> Normal
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-warn" /> Uyarı
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-danger" /> Kritik
          </span>
        </div>
      </div>

      {error ? (
        <div className="rounded-lg border border-danger/30 bg-[#F8EAEA] p-4 text-[15px] text-danger">
          {error}
        </div>
      ) : null}

      <div className="space-y-3">
        {filtered.map((chain, idx) => (
          <Card
            key={chain.requirement_id}
            className="!p-3.5"
            style={{ animationDelay: `${idx * 35}ms` }}
          >
            <div className="mb-2.5 flex flex-wrap items-center gap-2">
              <span className="font-mono text-[15px] font-semibold text-navy">{chain.requirement_id}</span>
              {chain.project_code ? (
                <span className="font-mono text-[15px] font-medium text-ink" title={chain.project ?? undefined}>
                  {chain.project_code}
                </span>
              ) : null}
              {chain.release_version ? (
                <span className="font-mono text-[14px] text-muted">{chain.release_version}</span>
              ) : null}
              <Badge tone={toneForStatus(chain.severity === 'warning' ? 'warn' : chain.severity)}>
                {statusLabel(chain.severity === 'warning' ? 'warn' : chain.severity)}
              </Badge>
            </div>
            <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5">
              {chain.nodes.map((node, i) => (
                <div key={`${node.kind}-${node.id}`} className="flex items-center gap-1.5">
                  <NodeCard
                    node={node}
                    active={selected?.id === node.id && selected?.kind === node.kind}
                    onClick={() => setSelected(node)}
                  />
                  {i < chain.nodes.length - 1 ? (
                    <ChevronRight className="h-4 w-4 shrink-0 text-muted/70" aria-hidden />
                  ) : null}
                </div>
              ))}
            </div>
          </Card>
        ))}
        {!chains.length && !error ? (
          <div className="py-14 text-center text-[15px] text-muted">Süreç zinciri yükleniyor…</div>
        ) : null}
        {chains.length > 0 && filtered.length === 0 ? (
          <div className="py-14 text-center text-[15px] text-muted">Filtreye uygun zincir yok.</div>
        ) : null}
      </div>

      <DetailPanel
        open={!!selected}
        title={selected?.title ?? ''}
        subtitle={selected ? `${KIND_LABEL[selected.kind]} · ${selected.id}` : undefined}
        onClose={() => setSelected(null)}
      >
        {selected ? (
          <div>
            <DetailField label="Kayıt ID" value={<span className="font-mono">{selected.id}</span>} />
            <DetailField label="Tür" value={KIND_LABEL[selected.kind]} />
            {selectedChain?.project ? (
              <DetailField label="Proje" value={selectedChain.project} />
            ) : null}
            {selectedChain?.release_version ? (
              <DetailField label="Sürüm" value={selectedChain.release_version} />
            ) : null}
            <DetailField
              label="Durum"
              value={
                <Badge tone={toneForStatus(selected.status)}>{statusLabel(selected.status)}</Badge>
              }
            />
            <DetailField
              label="Süreç sinyali"
              value={
                selected.reason ? (
                  <Badge tone={reasonTone(selected.severity)}>
                    {shortReason(selected.reason, selected.status)}
                  </Badge>
                ) : (
                  <Badge tone="neutral">Normal</Badge>
                )
              }
            />
            {selected.reason ? (
              <DetailField label="Açıklama" value={selected.reason} />
            ) : (
              <DetailField label="Açıklama" value="Bu aşamada belirgin risk sinyali yok." />
            )}
            <DetailField label="Başlık" value={selected.title} />
            {KIND_PATH[selected.kind] ? (
              <div className="mt-4 border-t border-line pt-3">
                <Link
                  to={KIND_PATH[selected.kind]}
                  onClick={() => scopeProjectFromChain()}
                  className="text-[16px] font-medium text-navy-mid hover:underline"
                >
                  {KIND_LABEL[selected.kind]} listesinde aç →
                </Link>
              </div>
            ) : null}
          </div>
        ) : null}
      </DetailPanel>
    </div>
  )
}
