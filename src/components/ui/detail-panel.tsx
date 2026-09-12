import { X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function DetailPanel({
  open,
  title,
  subtitle,
  onClose,
  children,
}: {
  open: boolean
  title: string
  subtitle?: string
  onClose: () => void
  children: React.ReactNode
}) {
  if (!open) return null

  return (
    <>
      <button
        type="button"
        aria-label="Kapat"
        className="fixed inset-0 z-40 bg-navy/20 backdrop-blur-[1px] transition-opacity"
        onClick={onClose}
      />
      <aside
        className={cn(
          'animate-slide-panel fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l border-line bg-panel shadow-xl',
        )}
      >
        <div className="flex items-start justify-between border-b border-line px-6 py-5">
          <div className="min-w-0 pr-3">
            <div className="font-mono text-[15px] text-navy-mid">{subtitle}</div>
            <h2 className="mt-1.5 text-[24px] font-semibold leading-snug text-ink">{title}</h2>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Kapat">
            <X className="h-5 w-5" />
          </Button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5 text-[17px]">{children}</div>
      </aside>
    </>
  )
}

export function DetailField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="border-b border-line py-3.5 last:border-0">
      <div className="text-[13px] font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-1.5 text-[17px] leading-snug text-ink">{value ?? '—'}</div>
    </div>
  )
}
