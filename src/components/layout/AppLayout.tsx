import { NavLink, Outlet } from 'react-router-dom'
import {
  LayoutDashboard,
  FolderKanban,
  FileText,
  ListTodo,
  GitCommitHorizontal,
  FlaskConical,
  Bug,
  Rocket,
  BrainCircuit,
  GitBranch,
  Network,
  BellRing,
  FileBarChart2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { ProjectFilterSelect } from '@/lib/project-filter'

const NAV = [
  { to: '/', label: 'Gösterge Paneli', icon: LayoutDashboard },
  { to: '/projeler', label: 'Projeler', icon: FolderKanban },
  { to: '/gereksinimler', label: 'Gereksinimler', icon: FileText },
  { to: '/gorevler', label: 'Görevler', icon: ListTodo },
  { to: '/kod-degisiklikleri', label: 'Kod Değişiklikleri', icon: GitCommitHorizontal },
  { to: '/testler', label: 'Testler', icon: FlaskConical },
  { to: '/hatalar', label: 'Hatalar', icon: Bug },
  { to: '/release', label: 'Sürümler', icon: Rocket },
  { to: '/surec', label: 'Süreç Görünümü', icon: GitBranch },
  { to: '/analiz', label: 'AI Analiz Merkezi', icon: BrainCircuit },
  { to: '/bildirimler', label: 'AI Bildirim Merkezi', icon: BellRing },
  { to: '/yonetici-ozeti', label: 'AI Yönetici Özeti', icon: FileBarChart2 },
]

export function AppLayout() {
  return (
    <div className="flex h-full min-h-screen bg-surface">
      <aside className="sticky top-0 z-20 flex h-screen w-[280px] shrink-0 flex-col bg-sidebar text-white">
        <div className="border-b border-white/10 px-5 py-5">
          <div className="flex items-start gap-3">
            <div
              className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white/10 ring-1 ring-white/15"
              aria-hidden
            >
              <Network className="h-5 w-5 text-white" strokeWidth={1.75} />
            </div>
            <div className="min-w-0">
              <div className="text-[26px] font-bold leading-none tracking-tight text-white">
                ProcessIQ
              </div>
              <p className="mt-2 text-[12px] font-normal leading-snug text-white/45">
                Yapay Zekâ Destekli Yazılım Süreç Analiz Platformu
              </p>
            </div>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 overflow-y-auto px-3 py-4">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 rounded-md px-3 py-3 text-[18px] font-medium transition-colors duration-200',
                  isActive
                    ? 'bg-sidebar-active text-white'
                    : 'text-white/65 hover:bg-sidebar-hover hover:text-white',
                )
              }
            >
              <Icon className="h-5 w-5 shrink-0 opacity-85" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-white/10 px-5 py-4 text-xs text-white/45">
          ProcessIQ · MVP
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-y-auto">
        <div className="sticky top-0 z-10 border-b border-line bg-surface/95 px-6 py-3 backdrop-blur lg:px-8">
          <div className="mx-auto flex max-w-[1280px] items-center justify-end gap-3">
            <ProjectFilterSelect />
          </div>
        </div>
        <div className="mx-auto max-w-[1280px] px-6 py-7 lg:px-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
