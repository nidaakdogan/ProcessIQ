import { useEffect, useState } from 'react'
import { api } from '@/lib/api'

/**
 * Sayfa Son Güncelleme tarihi.
 * Önce ekrandaki veriden gelen zaman damgası; yoksa /api/last-updated.
 */
export function useLastUpdated(
  projectId: number | null | undefined,
  dataTimestamp?: string | null,
  scope = 'all',
) {
  const [fallback, setFallback] = useState<string | null>(null)

  useEffect(() => {
    if (dataTimestamp) {
      setFallback(null)
      return
    }
    let cancelled = false
    api
      .lastUpdated(projectId ?? null, scope)
      .then((r) => {
        if (!cancelled) setFallback(r.last_updated)
      })
      .catch(() => {
        if (!cancelled) setFallback(null)
      })
    return () => {
      cancelled = true
    }
  }, [projectId, dataTimestamp, scope])

  return dataTimestamp || fallback
}
