import { cn, formatLastUpdated } from '@/lib/utils'

export function Card({
  children,
  className,
  style,
}: {
  children: React.ReactNode
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <div
      style={style}
      className={cn(
        'animate-fade-up rounded-lg border border-line bg-panel p-5 shadow-[0_1px_2px_rgba(15,39,71,0.04)]',
        className,
      )}
    >
      {children}
    </div>
  )
}

/**
 * Ortak sayfa başlığı.
 * Son Güncelleme: 25 Temmuz 2026
 */
export function PageHeader({
  title,
  actions,
  updatedAt,
  className,
}: {
  title: string
  description?: string
  actions?: React.ReactNode
  /** ISO datetime — veri / analiz güncelliği */
  updatedAt?: string | null
  className?: string
}) {
  return (
    <div className={cn('mb-5 flex flex-wrap items-end justify-between gap-4', className)}>
      <div className="min-w-0">
        <h1 className="text-[32px] font-semibold leading-tight tracking-tight text-ink">
          {title}
        </h1>
        {updatedAt ? (
          <p className="mt-1.5 text-[14px] leading-snug text-muted">
            Son Güncelleme: {formatLastUpdated(updatedAt)}
          </p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  )
}
