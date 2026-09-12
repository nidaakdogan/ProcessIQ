import { useEffect, useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

export type Column<T> = {
  key: string
  label: string
  sortable?: boolean
  render?: (row: T) => React.ReactNode
  className?: string
}

type Props<T extends Record<string, unknown>> = {
  columns: Column<T>[]
  rows: T[]
  searchKeys?: string[]
  filterOptions?: { key: string; label: string; values: { value: string; label: string }[] }[]
  initialFilters?: Record<string, string>
  initialSearch?: string
  pageSize?: number
  empty?: string
  onRowClick?: (row: T) => void
  onFilterChange?: (filters: Record<string, string>) => void
  getRowId?: (row: T, index: number) => string
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  rows,
  searchKeys = [],
  filterOptions = [],
  initialFilters = {},
  initialSearch = '',
  pageSize = 10,
  empty = 'Kayıt bulunamadı',
  onRowClick,
  onFilterChange,
  getRowId,
}: Props<T>) {
  const [search, setSearch] = useState(initialSearch)
  const [filters, setFilters] = useState<Record<string, string>>(initialFilters)
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  const [page, setPage] = useState(0)

  // Dashboard → detay tıklanınca URL filtreleri her seferinde uygulanır
  const initialFiltersKey = JSON.stringify(initialFilters)
  useEffect(() => {
    setFilters(initialFilters)
    setPage(0)
  }, [initialFiltersKey]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setSearch(initialSearch)
    setPage(0)
  }, [initialSearch])

  const filtered = useMemo(() => {
    let data = [...rows]

    if (search.trim() && searchKeys.length) {
      const q = search.toLowerCase()
      data = data.filter((row) =>
        searchKeys.some((k) => String(row[k] ?? '').toLowerCase().includes(q)),
      )
    }

    for (const [key, value] of Object.entries(filters)) {
      if (!value) continue
      data = data.filter((row) => String(row[key]) === value)
    }

    if (sortKey) {
      data.sort((a, b) => {
        const av = a[sortKey]
        const bv = b[sortKey]
        if (av == null && bv == null) return 0
        if (av == null) return 1
        if (bv == null) return -1
        if (typeof av === 'number' && typeof bv === 'number') {
          return sortDir === 'asc' ? av - bv : bv - av
        }
        const cmp = String(av).localeCompare(String(bv), 'tr')
        return sortDir === 'asc' ? cmp : -cmp
      })
    }

    return data
  }, [rows, search, searchKeys, filters, sortKey, sortDir])

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const pageRows = filtered.slice(safePage * pageSize, safePage * pageSize + pageSize)

  function toggleSort(key: string) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('asc')
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {searchKeys.length > 0 ? (
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(0)
              }}
              placeholder="Ara…"
              className="h-11 w-full rounded-md border border-line bg-panel pl-9 pr-3 text-[16px] outline-none transition focus:border-navy-mid focus:ring-2 focus:ring-navy-mid/15"
            />
          </div>
        ) : null}
        {filterOptions.map((f) => (
          <select
            key={f.key}
            value={filters[f.key] ?? ''}
            onChange={(e) => {
              const value = e.target.value
              setFilters((prev) => {
                const next = { ...prev, [f.key]: value }
                onFilterChange?.(next)
                return next
              })
              setPage(0)
            }}
            className="h-11 rounded-md border border-line bg-panel px-3 text-[16px] text-ink outline-none focus:border-navy-mid"
          >
            <option value="">{f.label}: Tümü</option>
            {f.values.map((v) => (
              <option key={v.value} value={v.value}>
                {v.label}
              </option>
            ))}
          </select>
        ))}
        <div className="ml-auto text-[15px] text-muted">{filtered.length} kayıt</div>
      </div>

      <div className="overflow-hidden rounded-lg border border-line bg-panel">
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-[16px]">
            <thead className="border-b border-line bg-[#F8FAFC] text-[16px] font-semibold tracking-wide text-muted">
              <tr>
                {columns.map((c) => (
                  <th key={c.key} className={cn('whitespace-nowrap px-4 py-4', c.className)}>
                    {c.sortable !== false ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(c.key)}
                        className="inline-flex items-center gap-1 hover:text-ink"
                      >
                        {c.label}
                        {sortKey === c.key ? (
                          <span className="text-[12px]">{sortDir === 'asc' ? '▲' : '▼'}</span>
                        ) : null}
                      </button>
                    ) : (
                      c.label
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pageRows.length === 0 ? (
                <tr>
                  <td colSpan={columns.length} className="px-4 py-16 text-center text-[16px] text-muted">
                    {empty}
                  </td>
                </tr>
              ) : (
                pageRows.map((row, i) => (
                  <tr
                    key={getRowId?.(row, i) ?? String(row.id ?? row.external_id ?? i)}
                    onClick={() => onRowClick?.(row)}
                    className={cn(
                      'border-t border-line transition-colors',
                      i % 2 === 1 && 'bg-[#FAFBFC]',
                      onRowClick && 'cursor-pointer hover:bg-[#EEF3F8]',
                    )}
                  >
                    {columns.map((c) => (
                      <td
                        key={c.key}
                        className={cn('whitespace-nowrap px-4 py-4 text-[16px] leading-snug text-ink', c.className)}
                      >
                        {c.render ? c.render(row) : String(row[c.key] ?? '—')}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between border-t border-line px-4 py-3.5">
          <span className="text-[15px] text-muted">
            Sayfa {safePage + 1} / {pageCount}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={safePage === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              <ChevronLeft className="h-4 w-4" />
              Önceki
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={safePage >= pageCount - 1}
              onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            >
              Sonraki
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
