import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(value?: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleDateString('tr-TR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}

/** Tablo sütunu standardı — Örn: 25 Tem 2026 14:35 */
export function formatRowUpdatedAt(value?: string | null) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  const date = d.toLocaleDateString('tr-TR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
  const time = d.toLocaleTimeString('tr-TR', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  return `${date} ${time}`
}

/** Sayfa başlığı standardı — Örn: 25 Temmuz 2026 */
export function formatLastUpdated(value?: string | null) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('tr-TR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

/** Örn: 23 Temmuz 2026, 10:15 */
export function formatDateTime(value?: string | null) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  const date = formatLastUpdated(value)
  const time = d.toLocaleTimeString('tr-TR', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  return `${date}, ${time}`
}

/** Örn: 25 Temmuz 2026 - 20:25 */
export function formatDateTimeLong(value?: string | null) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  const date = d.toLocaleDateString('tr-TR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
  const time = d.toLocaleTimeString('tr-TR', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  return `${date} - ${time}`
}

/** Örn: 20–25 Temmuz 2026 veya 25 Temmuz 2026 (tek gün) */
export function formatPeriodRange(start?: string | null, end?: string | null) {
  if (!start || !end) return '—'
  const s = new Date(start)
  const e = new Date(end)
  if (Number.isNaN(s.getTime()) || Number.isNaN(e.getTime())) return '—'
  const sameDay =
    s.getFullYear() === e.getFullYear() &&
    s.getMonth() === e.getMonth() &&
    s.getDate() === e.getDate()
  if (sameDay) {
    return s.toLocaleDateString('tr-TR', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    })
  }
  const sameMonth =
    s.getFullYear() === e.getFullYear() && s.getMonth() === e.getMonth()
  if (sameMonth) {
    const monthYear = e.toLocaleDateString('tr-TR', {
      month: 'long',
      year: 'numeric',
    })
    return `${s.getDate()}–${e.getDate()} ${monthYear}`
  }
  const left = s.toLocaleDateString('tr-TR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
  const right = e.toLocaleDateString('tr-TR', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
  return `${left} – ${right}`
}

/** Satır listesinden en güncel ISO zaman damgasını seçer. */
export function latestTimestamp(
  rows: Array<Record<string, unknown> | null | undefined>,
  keys: string[] = ['updated_at', 'created_at', 'committed_at', 'executed_at', 'release_date'],
): string | null {
  let best: number | null = null
  let bestIso: string | null = null
  for (const row of rows) {
    if (!row) continue
    for (const key of keys) {
      const raw = row[key]
      if (typeof raw !== 'string' || !raw) continue
      const t = new Date(raw).getTime()
      if (Number.isNaN(t)) continue
      if (best == null || t > best) {
        best = t
        bestIso = raw
      }
    }
  }
  return bestIso
}

/** Yerel takvim gününü YYYY-MM-DD olarak verir (UTC kayması yok). */
export function toLocalDateKey(d: Date) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** ISO tarihinin bir sonraki takvim günü (YYYY-MM-DD). */
export function nextCalendarDayKey(iso: string) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!m) return null
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]))
  d.setDate(d.getDate() + 1)
  return toLocalDateKey(d)
}

/** ISO datetime/date → takvim günü (saat dilimi kayması olmadan). */
export function formatDayLabel(value?: string | null) {
  if (!value) return '—'
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value)
  if (!m) return formatDate(value)
  const y = Number(m[1])
  const mo = Number(m[2])
  const d = Number(m[3])
  return new Date(y, mo - 1, d).toLocaleDateString('tr-TR', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

/** Liste ekranlarında kısa proje kodu (detayda project_name kullanılır). */
export function projectCode(value?: unknown) {
  return String(value ?? '—')
}

export function riskLabel(level: string) {
  const map: Record<string, string> = {
    low: 'Düşük',
    medium: 'Orta',
    high: 'Yüksek',
    critical: 'Kritik',
  }
  return map[level] ?? level
}

export function formatHours(value?: number | string | null) {
  if (value == null || value === '') return '—'
  const n = typeof value === 'number' ? value : Number(value)
  if (Number.isNaN(n)) return '—'
  return `${n.toLocaleString('tr-TR', {
    minimumFractionDigits: Number.isInteger(n) ? 0 : 1,
    maximumFractionDigits: 1,
  })} saat`
}

export function formatDelay(estimated?: number | null, actual?: number | null, blocked?: boolean) {
  if (blocked && (actual == null || estimated == null || actual <= estimated)) {
    return { label: 'Bloke', tone: 'danger' as const, hours: null as number | null }
  }
  if (actual == null || estimated == null) {
    return { label: '—', tone: 'neutral' as const, hours: null as number | null }
  }
  const diff = actual - estimated
  if (diff <= 0) {
    return {
      label: diff < 0 ? 'Erken' : 'Zamanında',
      tone: 'ok' as const,
      hours: diff,
    }
  }
  // 1 gün ≈ 8 iş saati
  if (diff >= 8) {
    const days = Math.round((diff / 8) * 10) / 10
    return {
      label: `${days.toLocaleString('tr-TR', { maximumFractionDigits: 1 })} gün gecikmiş`,
      tone: diff >= 16 ? ('danger' as const) : ('warn' as const),
      hours: diff,
    }
  }
  return {
    label: `+${diff.toLocaleString('tr-TR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} saat`,
    tone: diff > estimated * 0.2 ? ('danger' as const) : ('warn' as const),
    hours: diff,
  }
}

export function statusLabel(status: string) {
  const map: Record<string, string> = {
    active: 'Aktif',
    planning: 'Planlama',
    testing: 'Testte',
    ready_for_release: 'Yayına Hazır',
    maintenance: 'Bakım',
    on_hold: 'Beklemede',
    completed: 'Tamamlandı',
    draft: 'Taslak',
    approved: 'Onaylı',
    in_progress: 'Devam Ediyor',
    done: 'Tamamlandı',
    changed: 'Revize Edildi',
    todo: 'Yapılacak',
    blocked: 'Bloke',
    passed: 'Geçti',
    failed: 'Başarısız',
    skipped: 'Atlandı',
    open: 'Açık',
    reviewing: 'İnceleniyor',
    in_development: 'Çözüm Geliştiriliyor',
    in_test: 'Testte',
    resolved: 'Çözüldü',
    closed: 'Kapatıldı',
    planned: 'Planlandı',
    ready: 'Yayın İçin Hazır',
    released: 'Yayında',
    delayed: 'Gecikmiş',
    low: 'Düşük',
    medium: 'Orta',
    high: 'Yüksek',
    critical: 'Kritik',
    normal: 'Normal',
    warning: 'Uyarı',
    warn: 'Uyarı',
  }
  return map[status] ?? status
}

/** Release durumları — görevlerdeki in_progress ile karışmasın */
export function releaseStatusLabel(status: string) {
  const map: Record<string, string> = {
    planned: 'Planlandı',
    in_progress: 'Hazırlanıyor',
    ready: 'Yayın İçin Hazır',
    delayed: 'Gecikmiş',
    released: 'Yayında',
  }
  return map[status] ?? statusLabel(status)
}

export type StatusTone = 'neutral' | 'info' | 'ok' | 'warn' | 'danger' | 'critical'

export function toneForStatus(status: string): StatusTone {
  const s = status.toLowerCase()
  if (
    [
      'passed',
      'done',
      'released',
      'ready',
      'ready_for_release',
      'closed',
      'resolved',
      'completed',
      'ok',
      'low',
    ].includes(s)
  )
    return 'ok'
  if (['critical'].includes(s)) return 'critical'
  if (['failed', 'blocked', 'delayed', 'open', 'danger'].includes(s)) return 'danger'
  if (
    [
      'high',
      'changed',
      'in_progress',
      'reviewing',
      'in_development',
      'in_test',
      'testing',
      'warning',
      'warn',
      'medium',
      'planning',
    ].includes(s)
  )
    return 'warn'
  if (['active', 'approved', 'info', 'normal', 'maintenance'].includes(s)) return 'info'
  return 'neutral'
}
