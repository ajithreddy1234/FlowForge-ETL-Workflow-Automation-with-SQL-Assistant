import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import { AuthProvider } from './hooks/useAuth'
import { ToastProvider } from './components/common/Toast'
import RequireAuth from './components/RequireAuth'
import LandingPage from './pages/LandingPage'
import WorkspacePage from './pages/WorkspacePage'
import DashboardPage from './pages/DashboardPage'
import PipelineListPage from './pages/PipelineListPage'
import PipelineEditorPage from './pages/PipelineEditorPage'
import RuntimeLogsPage from './pages/RuntimeLogsPage'
import SettingsPage from './pages/SettingsPage'

const router = createBrowserRouter([
  { path: '/', element: <LandingPage /> },
  {
    element: <RequireAuth />,
    children: [
      { path: '/workspaces', element: <WorkspacePage /> },
      { path: '/dashboard', element: <DashboardPage /> },
      { path: '/pipelines', element: <PipelineListPage /> },
      { path: '/pipelines/new', element: <PipelineEditorPage /> },
      { path: '/pipelines/:pipelineId', element: <PipelineEditorPage /> },
      { path: '/logs', element: <RuntimeLogsPage /> },
      { path: '/logs/:runId', element: <RuntimeLogsPage /> },
      { path: '/settings', element: <SettingsPage /> },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </AuthProvider>
  )
}
