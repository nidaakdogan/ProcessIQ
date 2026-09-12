import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { ProjectFilterProvider } from '@/lib/project-filter'
import { DashboardPage } from '@/pages/DashboardPage'
import { ProjectsPage } from '@/pages/ProjectsPage'
import { RequirementsPage } from '@/pages/RequirementsPage'
import { TasksPage } from '@/pages/TasksPage'
import { CommitsPage } from '@/pages/CommitsPage'
import { TestsPage } from '@/pages/TestsPage'
import { BugsPage } from '@/pages/BugsPage'
import { ReleasesPage } from '@/pages/ReleasesPage'
import { ProcessPage } from '@/pages/ProcessPage'
import { AnalysisPage } from '@/pages/AnalysisPage'
import { NotificationsPage } from '@/pages/NotificationsPage'
import { ExecutiveSummaryPage } from '@/pages/ExecutiveSummaryPage'

export default function App() {
  return (
    <BrowserRouter>
      <ProjectFilterProvider>
        <Routes>
          <Route element={<AppLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="projeler" element={<ProjectsPage />} />
            <Route path="gereksinimler" element={<RequirementsPage />} />
            <Route path="gorevler" element={<TasksPage />} />
            <Route path="kod-degisiklikleri" element={<CommitsPage />} />
            <Route path="testler" element={<TestsPage />} />
            <Route path="hatalar" element={<BugsPage />} />
            <Route path="release" element={<ReleasesPage />} />
            <Route path="surec" element={<ProcessPage />} />
            <Route path="analiz" element={<AnalysisPage />} />
            <Route path="bildirimler" element={<NotificationsPage />} />
            <Route path="yonetici-ozeti" element={<ExecutiveSummaryPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </ProjectFilterProvider>
    </BrowserRouter>
  )
}
