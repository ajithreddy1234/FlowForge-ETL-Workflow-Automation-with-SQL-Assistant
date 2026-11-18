import { useState } from 'react'
import { Bot, Database, Eye, RefreshCw, Sparkles, CheckCircle, AlertTriangle } from 'lucide-react'

import * as connectionApi from '../../services/connectionApi'
import * as sqlAssistantApi from '../../services/sqlAssistantApi'
import { ApiError } from '../../services/apiClient'
import { Field, StatusBox } from './CredentialPanel'

function errorMessage(error, fallback) {
  return error instanceof ApiError ? error.message : (error?.message || fallback)
}

export default function SqlAssistantPanel({ credential, onUseSql }) {
  const connectionId = credential?.data?.connection_id
  const connectionReady = Boolean(connectionId)
  const [open, setOpen] = useState(true)
  const [requirement, setRequirement] = useState('')
  const [candidate, setCandidate] = useState(null)
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [catalogStatus, setCatalogStatus] = useState('')

  const syncMetadata = async () => {
    if (!connectionReady) return
    setBusy('catalog')
    setError('')
    try {
      const catalog = await connectionApi.syncCatalog(connectionId)
      setCatalogStatus(`${catalog.table_count} tables and ${catalog.column_count} columns discovered`)
    } catch (err) {
      setError(errorMessage(err, 'Metadata sync failed'))
    } finally {
      setBusy('')
    }
  }

  const generate = async () => {
    if (!connectionReady || requirement.trim().length < 3) return
    setBusy('generate')
    setError('')
    setPreview(null)
    try {
      const result = await sqlAssistantApi.generateSql(connectionId, requirement.trim())
      setCandidate(result)
    } catch (err) {
      setError(errorMessage(err, 'SQL generation failed'))
    } finally {
      setBusy('')
    }
  }

  const runPreview = async () => {
    if (!candidate) return
    setBusy('preview')
    setError('')
    try {
      setPreview(await sqlAssistantApi.previewSql(candidate.id, 100))
    } catch (err) {
      setError(errorMessage(err, 'Query preview failed'))
    } finally {
      setBusy('')
    }
  }

  const approve = async () => {
    if (!candidate) return
    setBusy('approve')
    setError('')
    try {
      const approved = await sqlAssistantApi.approveSql(candidate.id)
      setCandidate(approved)
      onUseSql(approved.sql)
    } catch (err) {
      setError(errorMessage(err, 'Could not approve this query'))
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="rounded-xl border border-violet-400/20 bg-violet-500/[0.06] p-3">
      <button
        type="button"
        onClick={() => setOpen(value => !value)}
        className="void-focus flex w-full items-center justify-between text-left"
      >
        <span className="flex items-center gap-2 text-sm font-semibold text-violet-200">
          <Bot size={15} /> SQL Assistant
        </span>
        <span className="text-xs text-violet-200/60">{open ? 'Hide' : 'Build from plain English'}</span>
      </button>

      {open && (
        <div className="mt-3 space-y-3 border-t border-violet-300/10 pt-3">
          <div className="flex items-center justify-between gap-2 rounded-lg bg-black/15 px-2.5 py-2">
            <div className="min-w-0">
              <p className="truncate text-xs font-medium text-white/70">
                {connectionReady
                  ? (credential?.data?.connection_name || credential?.data?.label || 'Saved database')
                  : 'Database connection required'}
              </p>
              <p className="text-[11px] text-white/35">
                {connectionReady ? 'Metadata only · read-only SQL' : 'Write the requirement now; connect and save to generate'}
              </p>
            </div>
            <button
              type="button"
              onClick={syncMetadata}
              disabled={Boolean(busy) || !connectionReady}
              className="void-focus flex shrink-0 items-center gap-1 rounded-md border border-white/10 px-2 py-1 text-xs text-white/60 hover:bg-white/5 disabled:opacity-40"
            >
              <RefreshCw size={11} className={busy === 'catalog' ? 'animate-spin' : ''} />
              Scan schema
            </button>
          </div>

          {!connectionReady && (
            <StatusBox tone="warning" icon={AlertTriangle}>
              Connect a Credential node, check the connection, and click Save Connection Securely. Your requirement below will remain available while you do that.
            </StatusBox>
          )}

          {catalogStatus && <StatusBox tone="success" icon={Database}>{catalogStatus}</StatusBox>}

          <Field label="What data do you need?" hint="Mention the business metric, date range, grouping, and filters.">
            <textarea
              rows={4}
              value={requirement}
              onChange={event => { setRequirement(event.target.value); setCandidate(null); setPreview(null) }}
              placeholder="Example: Show weekly revenue by franchise for the last 90 days, excluding cancelled orders."
              className="void-focus w-full resize-y rounded-lg border border-violet-300/20 bg-black/20 px-3 py-2 text-xs leading-relaxed text-white outline-none placeholder:text-white/25"
            />
          </Field>

          <button
            type="button"
            onClick={generate}
            disabled={Boolean(busy) || !connectionReady || requirement.trim().length < 3}
            className="void-focus flex w-full items-center justify-center gap-2 rounded-lg bg-violet-500 px-3 py-2 text-sm font-semibold text-white hover:bg-violet-400 disabled:opacity-40"
          >
            {busy === 'generate' ? <RefreshCw size={13} className="animate-spin" /> : <Sparkles size={13} />}
            {busy === 'generate'
              ? 'Reading metadata and generating…'
              : connectionReady
                ? 'Generate safe SQL'
                : 'Save a database connection to generate'}
          </button>

          {candidate && (
            <div className="space-y-2">
              <StatusBox tone="info" icon={CheckCircle}>{candidate.explanation}</StatusBox>
              <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-lg border border-white/10 bg-black/30 p-3 font-mono text-[11px] leading-relaxed text-violet-100">{candidate.sql}</pre>
              <div className="flex flex-wrap gap-1">
                {candidate.referenced_tables?.map(table => (
                  <span key={table} className="rounded-full bg-white/[0.06] px-2 py-1 font-mono text-[10px] text-white/50">{table}</span>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={runPreview}
                  disabled={Boolean(busy)}
                  className="void-focus flex items-center justify-center gap-1.5 rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold text-white/70 hover:bg-white/5 disabled:opacity-40"
                >
                  <Eye size={12} /> Preview
                </button>
                <button
                  type="button"
                  onClick={approve}
                  disabled={Boolean(busy)}
                  className="void-focus flex items-center justify-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-400 disabled:opacity-40"
                >
                  <CheckCircle size={12} /> Use this SQL
                </button>
              </div>
            </div>
          )}

          {preview?.columns?.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-white/10">
              <table className="min-w-max text-[10px]">
                <thead className="bg-white/[0.05] text-white/55">
                  <tr>{preview.columns.map(column => <th key={column} className="px-2 py-1.5 text-left">{column}</th>)}</tr>
                </thead>
                <tbody>
                  {preview.rows.slice(0, 5).map((row, index) => (
                    <tr key={index} className="border-t border-white/[0.05] text-white/65">
                      {preview.columns.map(column => <td key={column} className="max-w-48 truncate px-2 py-1.5 font-mono">{String(row[column] ?? '')}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {error && <StatusBox tone="error" icon={AlertTriangle}>{error}</StatusBox>}
        </div>
      )}
    </div>
  )
}
