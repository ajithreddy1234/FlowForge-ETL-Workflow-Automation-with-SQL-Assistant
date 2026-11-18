import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Terminal } from 'lucide-react'
import AppShell from '../components/layout/AppShell'
import LoadingState from '../components/common/LoadingState'
import ErrorState from '../components/common/ErrorState'
import LogFilters from '../components/logs/LogFilters'
import LogHistoryList from '../components/logs/LogHistoryList'
import LogTerminal from '../components/logs/LogTerminal'
import LogDetails from '../components/logs/LogDetails'
import { useToast } from '../components/common/Toast'
import { useAuth } from '../hooks/useAuth'
import * as logsApi from '../services/logsApi'
import * as pipelineApi from '../services/pipelineApi'
import { runPipeline } from '../services/executionApi'
import { ApiError } from '../services/apiClient'
import { isTerminalStatus } from '../utils/statusMap'
import { reportToGraph } from '../reportImporter'

const POLL_MS = 4000

export default function RuntimeLogsPage() {
  const { user, logout } = useAuth()
  const { runId } = useParams()
  const navigate = useNavigate()
  const toast = useToast()

  const [runs, setRuns] = useState([])
  const [selectedRun, setSelectedRun] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('all')
  const [search, setSearch] = useState('')
  const [rerunning, setRerunning] = useState(false)
  const pollRef = useRef(null)

  const loadList = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const rows = await logsApi.listRuntimeLogs({ status, search })
      setRuns(rows)
      return rows
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load runtime logs')
      return []
    } finally {
      setLoading(false)
    }
  }, [status, search])

  useEffect(() => {
    let cancelled = false
    loadList().then(rows => {
      if (cancelled) return
      if (runId) {
        const numeric = Number(runId)
        const match = rows.find(r => r.id === numeric)
        setSelectedRun(match || null)
        if (!match) logsApi.getRuntimeLog(numeric).then(setSelectedRun).catch(() => {})
      } else if (rows.length) {
        setSelectedRun(rows[0])
      } else {
        setSelectedRun(null)
      }
    })
    return () => { cancelled = true }
  }, [status, search]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!runId) return
    logsApi.getRuntimeLog(Number(runId)).then(setSelectedRun).catch(() => {})
  }, [runId])

  // Poll while the selected run is still in flight.
  useEffect(() => {
    clearInterval(pollRef.current)
    if (!selectedRun || isTerminalStatus(selectedRun.status)) return
    pollRef.current = setInterval(async () => {
      try {
        const fresh = await logsApi.getRuntimeLog(selectedRun.id)
        setSelectedRun(fresh)
        if (isTerminalStatus(fresh.status)) loadList()
      } catch {
        clearInterval(pollRef.current)
      }
    }, POLL_MS)
    return () => clearInterval(pollRef.current)
  }, [selectedRun, loadList])

  const selectRun = (id) => {
    navigate(`/logs/${id}`)
  }

  const rerun = async () => {
    if (!selectedRun?.pipeline_slug) return
    setRerunning(true)
    try {
      const report = await pipelineApi.getPipeline(selectedRun.pipeline_slug)
      const graph = reportToGraph(report)
      await new Promise((resolve, reject) => {
        runPipeline(graph, {
          onComplete: (errors) => (errors.length ? reject(new Error(errors[0].message)) : resolve()),
          onError: (errors) => reject(new Error(errors[0]?.message || 'Run failed')),
          onAuthRequired: () => reject(new Error('Your session expired. Please sign in again.')),
        })
      })
      toast.push('Pipeline ran successfully', { type: 'success' })
      loadList()
    } catch (err) {
      toast.push(err.message || 'Run failed', { type: 'error' })
    } finally {
      setRerunning(false)
    }
  }

  return (
    <AppShell user={user} onLogout={logout} scroll={false}>
      <div className="flex h-screen flex-col px-6 pt-20 pb-24 sm:px-10">
        <div className="mb-4 flex items-center gap-2.5">
          <Terminal size={17} className="text-accent-light" aria-hidden="true" />
          <h1 className="font-mono text-sm font-bold uppercase tracking-[0.2em] text-white">
            FlowForge · Logs
          </h1>
        </div>

        <LogFilters status={status} onStatusChange={setStatus} search={search} onSearchChange={setSearch} />

        <div className="mt-4 flex-1 min-h-0">
          {loading && runs.length === 0 ? (
            <LoadingState label="Loading logs" rows={5} />
          ) : error ? (
            <ErrorState description={error} onRetry={loadList} />
          ) : (
            <div className="grid h-full min-h-0 grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
              <div className="void-card min-h-0 overflow-y-auto rounded-2xl p-3">
                <LogHistoryList runs={runs} selectedId={selectedRun?.id} onSelect={selectRun} />
              </div>
              <div className="void-card flex min-h-0 flex-col rounded-2xl">
                <div className="min-h-0 flex-1 p-3">
                  <LogTerminal run={selectedRun} />
                </div>
                <LogDetails run={selectedRun} onRerun={rerun} rerunning={rerunning} />
              </div>
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
