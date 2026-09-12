import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  FolderKanban,
  Timer,
  FlaskConical,
  AlertTriangle,
  Rocket,
  GitCommitHorizontal,
  Sparkles,
} from 'lucide-react'
import { api, type DashboardData } from '@/lib/api'
import { Card, PageHeader } from '@/components/ui/card'
import { useProjectFilter } from '@/lib/project-filter'
import { useLastUpdated } from '@/lib/use-last-updated'

const CARD_META = [
  {
    key: 'active_projects',
    label: 'Aktif Projeler',
    icon: FolderKanban,
    href: '/projeler?status=active',
  },
  {
    key: 'delayed_tasks',
    label: 'Geciken Görevler',
    icon: Timer,
    href: '/gorevler?is_delayed=true',
  },
  {
    key: 'failed_tests',
    label: 'Başarısız Testler',
    icon: FlaskConical,
    href: '/testler?result=failed',
  },
  {
    key: 'critical_bugs',
    label: 'Kritik Hatalar',
    icon: AlertTriangle,
    href: '/hatalar?severity=critical&status=active',
  },
  {
    key: 'risky_releases',
    label: 'Riskli Sürümler',
    icon: Rocket,
    href: '/release?is_risky=true',
  },
  {
    key: 'recent_commits_14d',
    label: 'Son 14 Gün',
    icon: GitCommitHorizontal,
    href: '/kod-degisiklikleri?within_days=14',
  },
] as const

const RISK_FILL: Record<string, string> = {
  Yüksek: '#C94040',
  Orta: '#64748B',
  Düşük: '#1E4E79',
}
const RISK_ORDER = ['Yüksek', 'Orta', 'Düşük'] as const
const TEST_COLORS = ['#2E7D5B', '#C94040', '#94A3B8']

function formatTrNumber(value: number, digits = 0) {
  return value.toLocaleString('tr-TR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

function RiskTrendTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean
  payload?: { payload?: Record<string, unknown> }[]
  label?: string
}) {
  if (!active || !payload?.length) return null
  const row = payload[0]?.payload ?? {}
  const risk = Number(row.risk_index ?? 0)
  const failed = Number(row.failed_tests ?? 0)
  const critical = Number(row.critical_bugs ?? 0)
  const delayed = Number(row.delayed_tasks ?? 0)
  const level = String(row.risk_level ?? '')
  return (
    <div className="rounded-md border border-line bg-panel px-3 py-2 text-[15px] shadow-md">
      <div className="font-semibold text-ink">{label}</div>
      <div className="mt-1 tabular-nums text-navy">
        Risk Endeksi: <strong>{formatTrNumber(risk)}</strong>
        {level ? <span className="text-muted"> · {level}</span> : null}
      </div>
      <div className="mt-1 space-y-0.5 text-[15px] text-muted">
        <div>Başarısız test: {formatTrNumber(failed)}</div>
        <div>Açık kritik hata: {formatTrNumber(critical)}</div>
        <div>Geciken görev: {formatTrNumber(delayed)}</div>
      </div>
    </div>
  )
}

function verifyPath(
  base: string,
  params: Record<string, string | number> | undefined,
  projectId?: number | null,
): string {
  const q = new URLSearchParams()
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v == null || v === '') continue
      q.set(k, String(v))
    }
  }
  if (projectId != null) q.set('project_id', String(projectId))
  const s = q.toString()
  return s ? `${base}?${s}` : base
}

export function DashboardPage() {
  const { projectId, withProject } = useProjectFilter()
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const updatedAt = useLastUpdated(projectId, data?.last_updated ?? null, 'dashboard')

  useEffect(() => {
    setData(null)
    api
      .dashboard(projectId)
      .then(setData)
      .catch((e) => setError(e.message))
  }, [projectId])

  if (error) {
    return (
      <div className="rounded-lg border border-danger/30 bg-[#F8EAEA] p-6 text-sm text-danger">
        Gösterge paneli yüklenemedi: {error}
      </div>
    )
  }

  if (!data) {
    return <div className="py-20 text-center text-sm text-muted">Yükleniyor…</div>
  }

  const testPie = [
    { name: 'Geçti', value: data.charts.test_counts.passed },
    { name: 'Başarısız', value: data.charts.test_counts.failed },
    { name: 'Atlandı', value: data.charts.test_counts.skipped },
  ]

  const riskDist = RISK_ORDER.map((label) => {
    const row = data.charts.release_risk_distribution.find((r) => r.label === label)
    return { label, count: row?.count ?? 0 }
  })
  const riskDistTotal = riskDist.reduce((s, r) => s + r.count, 0)
  const riskyFromChart = riskDist.find((r) => r.label === 'Yüksek')?.count ?? 0
  const releaseCounts = data.charts.release_counts ?? {
    total: riskDistTotal,
    not_released: riskDistTotal,
    risky: data.cards.risky_releases,
  }
  const insight = data.charts.risk_trend_insight

  return (
    <div className="pb-10">
      <PageHeader
        title="Gösterge Paneli"
        updatedAt={updatedAt}
        actions={
          <Link
            to="/analiz"
            className="inline-flex h-11 items-center rounded-md bg-navy px-5 text-[16px] font-medium text-white transition hover:bg-navy-mid"
          >
            AI Analiz Merkezi
          </Link>
        }
      />

      {/* Kompakt KPI şeridi — tıklanınca aynı filtreyle detay */}
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 xl:grid-cols-6">
        {CARD_META.map(({ key, label, icon: Icon, href }, idx) => {
          const value = data.cards[key]
          const emphasize =
            (key === 'critical_bugs' || key === 'risky_releases' || key === 'failed_tests') &&
            value > 0
          const link = data.card_links?.[key]
          const to = link
            ? verifyPath(link.path, link.query, projectId)
            : withProject(href)
          return (
            <Link
              key={key}
              to={to}
              className="group block transition hover:opacity-95"
              style={{ animationDelay: `${idx * 30}ms` }}
            >
              <Card className="animate-fade-up flex items-center gap-2.5 px-3 py-3">
                <div
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-md ${
                    emphasize ? 'bg-[#F8EAEA] text-danger' : 'bg-[#E8EEF5] text-navy-mid'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-[15px] font-medium leading-tight text-muted">
                    {label}
                  </div>
                  <div className="mt-0.5 text-[36px] font-semibold tabular-nums leading-none text-ink">
                    {formatTrNumber(value)}
                  </div>
                  <div className="mt-1 text-[12px] font-medium text-navy-mid group-hover:underline">
                    Detaya Git →
                  </div>
                </div>
              </Card>
            </Link>
          )
        })}
      </div>

      {/* Tam genişlik grafikler — kart alanını dolduran yerleşim */}
      <div className="mt-5 space-y-4">
        <Card className="animate-chart overflow-visible !p-4">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <h2 className="text-[18px] font-semibold text-ink">Sürüm Risk Dağılımı</h2>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[15px] text-muted">
              <Link
                to={withProject('/release?is_active=true')}
                className="tabular-nums hover:text-navy-mid hover:underline"
              >
                Yayında olmayan: {formatTrNumber(releaseCounts.not_released)}
              </Link>
              <span aria-hidden>·</span>
              <Link to={withProject('/release')} className="tabular-nums hover:text-navy-mid hover:underline">
                Tüm sürümler: {formatTrNumber(releaseCounts.total)}
              </Link>
              <span aria-hidden>·</span>
              <Link
                to={withProject('/release?is_risky=true')}
                className="tabular-nums font-medium text-danger hover:underline"
              >
                Yüksek risk: {formatTrNumber(releaseCounts.risky)}
              </Link>
              {riskyFromChart !== data.cards.risky_releases ||
              riskDistTotal !== releaseCounts.not_released ? (
                <span className="text-danger"> · sayılar uyumsuz</span>
              ) : null}
            </div>
          </div>
          <div className="h-[200px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={riskDist}
                layout="vertical"
                margin={{ top: 8, right: 40, left: 4, bottom: 4 }}
                barCategoryGap="12%"
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#DDE3EA" horizontal={false} />
                <XAxis
                  type="number"
                  allowDecimals={false}
                  tick={{ fontSize: 15, fill: '#64748B' }}
                  domain={[0, (max: number) => Math.max(Math.ceil(max * 1.2), 1)]}
                />
                <YAxis
                  type="category"
                  dataKey="label"
                  width={78}
                  tick={{ fontSize: 15, fill: '#475569', fontWeight: 500 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Bar dataKey="count" name="Adet" radius={[0, 6, 6, 0]} barSize={52}>
                  {riskDist.map((row) => (
                    <Cell key={row.label} fill={RISK_FILL[row.label] ?? '#64748B'} />
                  ))}
                  <LabelList
                    dataKey="count"
                    position="right"
                    formatter={(v) => formatTrNumber(Number(v ?? 0))}
                    style={{ fill: '#334155', fontSize: 16, fontWeight: 600 }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="animate-chart overflow-visible !p-4" style={{ animationDelay: '40ms' }}>
          <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-[18px] font-semibold text-ink">Test Başarı Oranı</h2>
              <div className="mt-1 text-[36px] font-semibold tabular-nums leading-none text-navy">
                {formatTrNumber(data.charts.test_pass_rate, 1)}%
              </div>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-[16px] tabular-nums text-muted">
              <span>
                <strong className="text-ink">{formatTrNumber(data.charts.test_counts.total)}</strong>{' '}
                Test
              </span>
              <Link to={withProject('/testler?result=passed')} className="hover:text-navy-mid hover:underline">
                <strong className="text-ink">{formatTrNumber(data.charts.test_counts.passed)}</strong>{' '}
                Geçti
              </Link>
              <Link
                to={withProject('/testler?result=failed')}
                className="font-medium text-danger hover:underline"
              >
                <strong>{formatTrNumber(data.charts.test_counts.failed)}</strong> Başarısız
              </Link>
              <Link to={withProject('/testler?result=skipped')} className="hover:text-navy-mid hover:underline">
                <strong className="text-ink">{formatTrNumber(data.charts.test_counts.skipped)}</strong>{' '}
                Atlandı
              </Link>
            </div>
          </div>
          <div className="flex flex-col items-stretch gap-4 sm:flex-row sm:items-center">
            <div className="h-[300px] w-full shrink-0 sm:w-[58%] lg:w-[55%]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                  <Pie
                    data={testPie}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius="34%"
                    outerRadius="92%"
                    paddingAngle={1.5}
                  >
                    {testPie.map((_, i) => (
                      <Cell key={i} fill={TEST_COLORS[i % TEST_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => formatTrNumber(Number(value))} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex min-w-0 flex-1 flex-col justify-center gap-2.5">
              {testPie.map((row, i) => {
                const href =
                  row.name === 'Geçti'
                    ? '/testler?result=passed'
                    : row.name === 'Başarısız'
                      ? '/testler?result=failed'
                      : '/testler?result=skipped'
                return (
                  <Link
                    key={row.name}
                    to={withProject(href)}
                    className="flex items-center justify-between gap-3 rounded-lg border border-line bg-[#F8FAFC] px-4 py-3.5 transition hover:border-navy-mid/40"
                  >
                    <div className="flex items-center gap-2.5">
                      <span
                        className="h-3 w-3 rounded-full"
                        style={{ background: TEST_COLORS[i] }}
                      />
                      <span className="text-[16px] font-medium text-ink">{row.name}</span>
                    </div>
                    <span className="text-[16px] font-semibold tabular-nums text-ink">
                      {formatTrNumber(row.value)}
                    </span>
                  </Link>
                )
              })}
            </div>
          </div>
        </Card>

        <Card className="animate-chart overflow-visible !p-4" style={{ animationDelay: '80ms' }}>
          <h2 className="mb-3 text-[18px] font-semibold text-ink">Gecikme Nedenleri</h2>
          <div className="h-[240px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data.charts.delay_reasons}
                layout="vertical"
                margin={{ top: 4, right: 44, left: 4, bottom: 4 }}
                barCategoryGap="14%"
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#DDE3EA" horizontal={false} />
                <XAxis
                  type="number"
                  allowDecimals={false}
                  tick={{ fontSize: 15, fill: '#64748B' }}
                  domain={[0, (max: number) => Math.max(Math.ceil(max * 1.15), 1)]}
                />
                <YAxis
                  type="category"
                  dataKey="reason"
                  width={200}
                  tick={{ fontSize: 15, fill: '#475569' }}
                  axisLine={false}
                  tickLine={false}
                />
                <Bar dataKey="count" name="Adet" fill="#1E4E79" radius={[0, 4, 4, 0]} barSize={42}>
                  <LabelList
                    dataKey="count"
                    position="right"
                    formatter={(v) => formatTrNumber(Number(v ?? 0))}
                    style={{ fill: '#334155', fontSize: 16, fontWeight: 600 }}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 border-t border-line pt-2 text-[15px]">
            {data.charts.delay_reasons.map((row) => (
              <Link
                key={row.reason}
                to={verifyPath('/gorevler', row.verify, projectId)}
                className="text-navy-mid hover:underline"
              >
                {row.reason}: {row.count} →
              </Link>
            ))}
          </div>
        </Card>

        <Card className="animate-chart overflow-visible !p-4" style={{ animationDelay: '120ms' }}>
          <h2 className="mb-3 text-[18px] font-semibold text-ink">Son 14 Günlük Risk Trendi</h2>
          <div className="h-[280px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={data.charts.risk_trend_14d}
                margin={{ top: 8, right: 12, left: 0, bottom: 4 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#DDE3EA" />
                <XAxis dataKey="period" tick={{ fontSize: 15, fill: '#64748B' }} />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 15, fill: '#64748B' }}
                  width={40}
                  domain={[0, (max: number) => Math.max(Math.ceil(max * 1.1), 1)]}
                />
                <Tooltip content={<RiskTrendTooltip />} />
                <Line
                  type="monotone"
                  dataKey="risk_index"
                  name="Risk Endeksi"
                  stroke="#0F2747"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: '#1E4E79' }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {insight?.text ? (
          <Card className="border-[#C5D4E5] bg-gradient-to-br from-[#F7FAFC] to-white !p-4">
            <div className="flex gap-3">
              <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-navy text-white">
                <Sparkles className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-semibold uppercase tracking-[0.08em] text-navy-mid">
                  AI Özeti
                  {insight.period_label ? ` · ${insight.period_label}` : ''}
                  {insight.risk_index != null
                    ? ` · Endeks ${formatTrNumber(insight.risk_index)}`
                    : ''}
                  {insight.risk_level ? ` · ${insight.risk_level}` : ''}
                </div>
                <p className="mt-2 text-[16px] leading-relaxed text-ink">{insight.text}</p>
                {insight.verify ? (
                  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[16px]">
                    <Link
                      to={verifyPath('/testler', insight.verify.tests, projectId)}
                      className="font-medium text-navy-mid hover:underline"
                    >
                      {insight.failed_tests ?? 0} başarısız testi doğrula
                    </Link>
                    <Link
                      to={verifyPath('/hatalar', insight.verify.bugs, projectId)}
                      className="font-medium text-navy-mid hover:underline"
                    >
                      {insight.critical_bugs ?? 0} kritik hatayı doğrula
                    </Link>
                    <Link
                      to={verifyPath('/gorevler', insight.verify.tasks, projectId)}
                      className="font-medium text-navy-mid hover:underline"
                    >
                      {insight.delayed_tasks ?? 0} geciken görevi doğrula
                    </Link>
                  </div>
                ) : null}
                <Link
                  to="/analiz"
                  className="mt-3 inline-block text-[16px] font-medium text-navy-mid hover:underline"
                >
                  AI Analiz Merkezi’nde derinleştir →
                </Link>
              </div>
            </div>
          </Card>
        ) : null}
      </div>
    </div>
  )
}
