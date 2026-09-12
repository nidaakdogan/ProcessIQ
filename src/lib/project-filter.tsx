import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '@/lib/api'

export type ProjectOption = {
  id: number
  code: string
  name: string
}

type ProjectFilterContextValue = {
  projects: ProjectOption[]
  projectId: number | null
  projectCode: string | null
  setProjectId: (id: number | null) => void
  querySuffix: string
  /** Dashboard → detay linklerine proje kapsamını ekler */
  withProject: (path: string) => string
}

const ProjectFilterContext = createContext<ProjectFilterContextValue | null>(null)

const STORAGE_KEY = 'spip.projectFilterId'

export function ProjectFilterProvider({ children }: { children: ReactNode }) {
  const [searchParams] = useSearchParams()
  const [projects, setProjects] = useState<ProjectOption[]>([])
  const [projectId, setProjectIdState] = useState<number | null>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return null
      const n = Number(raw)
      return Number.isFinite(n) ? n : null
    } catch {
      return null
    }
  })

  useEffect(() => {
    api
      .projects()
      .then((rows) => {
        setProjects(
          rows.map((r) => ({
            id: Number(r.id),
            code: String(r.code),
            name: String(r.name),
          })),
        )
      })
      .catch(console.error)
  }, [])

  // URL'deki project_id (Dashboard doğrulama linkleri) → global filtre
  useEffect(() => {
    const raw = searchParams.get('project_id')
    if (raw == null || raw === '') return
    const n = Number(raw)
    if (!Number.isFinite(n)) return
    setProjectIdState((prev) => {
      if (prev === n) return prev
      try {
        localStorage.setItem(STORAGE_KEY, String(n))
      } catch {
        /* ignore */
      }
      return n
    })
  }, [searchParams])

  const setProjectId = useCallback((id: number | null) => {
    setProjectIdState(id)
    try {
      if (id == null) localStorage.removeItem(STORAGE_KEY)
      else localStorage.setItem(STORAGE_KEY, String(id))
    } catch {
      /* ignore */
    }
  }, [])

  const projectCode = useMemo(() => {
    if (projectId == null) return null
    return projects.find((p) => p.id === projectId)?.code ?? null
  }, [projectId, projects])

  const querySuffix = useMemo(() => {
    if (projectId == null) return ''
    return `&project_id=${projectId}`
  }, [projectId])

  const withProject = useCallback(
    (path: string) => {
      if (projectId == null) return path
      const sep = path.includes('?') ? '&' : '?'
      return `${path}${sep}project_id=${projectId}`
    },
    [projectId],
  )

  const value = useMemo(
    () => ({ projects, projectId, projectCode, setProjectId, querySuffix, withProject }),
    [projects, projectId, projectCode, setProjectId, querySuffix, withProject],
  )

  return (
    <ProjectFilterContext.Provider value={value}>{children}</ProjectFilterContext.Provider>
  )
}

export function useProjectFilter() {
  const ctx = useContext(ProjectFilterContext)
  if (!ctx) {
    throw new Error('useProjectFilter must be used within ProjectFilterProvider')
  }
  return ctx
}

/** Global Proje: Tümü seçici */
export function ProjectFilterSelect({ className }: { className?: string }) {
  const { projects, projectId, setProjectId } = useProjectFilter()
  return (
    <select
      value={projectId ?? ''}
      onChange={(e) => setProjectId(e.target.value ? Number(e.target.value) : null)}
      className={
        className ??
        'h-11 rounded-md border border-line bg-panel px-3 text-[16px] text-ink outline-none focus:border-navy-mid'
      }
      aria-label="Proje filtresi"
    >
      <option value="">Proje: Tümü</option>
      {projects.map((p) => (
        <option key={p.id} value={p.id}>
          {p.code}
        </option>
      ))}
    </select>
  )
}
