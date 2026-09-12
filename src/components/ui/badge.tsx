import { cn, type StatusTone } from '@/lib/utils'

const TONES: Record<StatusTone, string> = {
  neutral: 'bg-slate-100 text-slate-700 border-slate-200',
  info: 'bg-[#E8EEF5] text-navy-mid border-[#C9D6E5]',
  ok: 'bg-[#E8F3ED] text-ok border-[#C5DFD1]',
  warn: 'bg-[#FBF3E4] text-warn border-[#EFD7A8]',
  danger: 'bg-[#F8EAEA] text-danger border-[#E8C4C4]',
  // Koyu kritik — yüksek (turuncu/warn) ile net ayrışır
  critical: 'bg-[#F0DADA] text-[#7A1515] border-[#A83232]',
}

export function Badge({
  children,
  tone = 'neutral',
  className,
}: {
  children: React.ReactNode
  tone?: StatusTone
  className?: string
}) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded border px-2.5 py-1 text-[15px] font-medium leading-none',
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  )
}

export { toneForStatus } from '@/lib/utils'
