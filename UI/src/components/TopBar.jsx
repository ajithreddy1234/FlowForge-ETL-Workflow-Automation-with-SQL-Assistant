import { useRef, useState, useEffect } from 'react'
import {
  Play, Undo2, Redo2, Download, CheckCircle, AlertTriangle,
  Save, Copy, ClipboardPaste, Upload, X, ArrowLeft, ShieldCheck,
  CalendarClock, MoreHorizontal, Maximize,
} from 'lucide-react'
import { useStore } from '../store'
import { graphToReport } from '../reportSerializer'
import { reportToGraph } from '../reportImporter'
import { graphToIndexFlow } from '../indexFlowSerializer'
import { validatePipeline } from '../utils/pipelineValidation'
import * as pipelineApi from '../services/pipelineApi'
import { ApiError } from '../services/apiClient'

const CLIPBOARD_KEY = 'etl-pipeline-copy-buffer'

export default function TopBar({
  onRun, running, onStartAreaCopy, onSaved, currentUser,
  onBack, onFitView, onOpenSchedule, onValidationResult,
}) {
  const {
    pipelineName, setPipelineName, undo, redo, history, future, getGraph, nodes,
    loadGraph, getCanvasGraph, getCopiedGraph, pasteGraph,
    currentPipelineKey, setCurrentPipelineKey, dirty, markSaved, edges,
  } = useStore()
  const [editing, setEditing] = useState(false)
  const [completed, setCompleted] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  const [statusText, setStatusText] = useState('')
  const [saveOpen, setSaveOpen] = useState(false)
  const [saveName, setSaveName] = useState('')
  const importInputRef = useRef(null)
  const moreRef = useRef(null)

  const canUndo = history.length > 0
  const canRedo = future.length > 0
  const runnableNodes = nodes.filter(n => n.type !== 'credential')
  const doneCount = runnableNodes.filter(n => n.data?.runStatus === 'done').length
  const errorCount = runnableNodes.filter(n => n.data?.runStatus === 'error').length
  const total = runnableNodes.length
  const finishedCount = doneCount + errorCount
  const pct = total > 0 ? Math.round((finishedCount / total) * 100) : 0
  const hasError = errorCount > 0
  const isAdmin = currentUser?.role === 'admin'

  useEffect(() => {
    if (!running && finishedCount > 0 && finishedCount === total && total > 0) {
      setCompleted(true)
      const t = setTimeout(() => setCompleted(false), 2500)
      return () => clearTimeout(t)
    }
  }, [running, finishedCount, total])

  useEffect(() => {
    if (!statusText) return
    const t = setTimeout(() => setStatusText(''), 2500)
    return () => clearTimeout(t)
  }, [statusText])

  useEffect(() => {
    if (!moreOpen) return
    const close = (e) => { if (!moreRef.current?.contains(e.target)) setMoreOpen(false) }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [moreOpen])

  const openSaveDialog = () => {
    setSaveName(pipelineName === 'Untitled Pipeline' ? '' : pipelineName)
    setSaveOpen(true)
  }

  const savePipeline = async ({ useDialogName = false, updateCurrent = false } = {}) => {
    try {
      const indexedPipeline = graphToIndexFlow(getCanvasGraph())
      const finalName = !useDialogName
        ? (pipelineName || indexedPipeline.report_name || 'Untitled Pipeline')
        : (saveName.trim() || pipelineName || 'Untitled Pipeline')
      indexedPipeline.report_name = finalName
      const shouldUpdate = updateCurrent && currentPipelineKey && isAdmin
      const res = shouldUpdate
        ? await pipelineApi.updatePipeline(currentPipelineKey, indexedPipeline)
        : await pipelineApi.createPipeline(indexedPipeline)
      setPipelineName(finalName)
      setCurrentPipelineKey(res.name)
      markSaved()
      setSaveOpen(false)
      onSaved?.(res)
      setStatusText(`Saved ${res.pipeline_name || finalName}`)
    } catch (e) {
      setStatusText(e instanceof ApiError ? e.message : 'Save failed')
    }
  }

  const handlePrimarySave = () => {
    if (currentPipelineKey && isAdmin) {
      savePipeline({ updateCurrent: true })
      return
    }
    openSaveDialog()
  }

  const handleValidate = () => {
    const issues = validatePipeline(nodes, edges)
    onValidationResult?.(issues)
    setMoreOpen(false)
    if (issues.length === 0) setStatusText('Pipeline looks valid')
  }

  const handleCopyFull = () => {
    const graph = getCopiedGraph()
    if (!graph.nodes.length) {
      setStatusText('Nothing to copy')
      return
    }
    localStorage.setItem(CLIPBOARD_KEY, JSON.stringify(graph))
    setMoreOpen(false)
    setStatusText('Copied full pipeline')
  }

  const handleSelectAreaCopy = () => {
    setMoreOpen(false)
    onStartAreaCopy?.()
    setStatusText('Drag a rectangle on the canvas')
  }

  const handlePaste = () => {
    const raw = localStorage.getItem(CLIPBOARD_KEY)
    if (!raw) {
      setStatusText('Nothing copied')
      return
    }
    try {
      pasteGraph(JSON.parse(raw))
      setStatusText('Pasted copied pipeline')
    } catch (e) {
      setStatusText('Paste failed')
    }
    setMoreOpen(false)
  }

  const handleDownload = () => {
    const report = graphToReport(getGraph())
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${pipelineName.replace(/\s+/g, '_') || 'pipeline'}.json`
    a.click()
    URL.revokeObjectURL(url)
    setMoreOpen(false)
  }

  const handleImportJson = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    try {
      const parsed = JSON.parse(await file.text())
      const graph = parsed.nodes && parsed.edges ? parsed : reportToGraph(parsed)
      loadGraph(graph, null)
      setStatusText(`Imported ${graph.pipeline_name || 'pipeline'}`)
    } catch (e) {
      setStatusText('Import failed')
    }
  }

  let btnBg = 'bg-accent hover:bg-accent-hover'
  let btnContent = <><Play size={13} fill="white" />Run Pipeline</>

  if (running) {
    btnBg = 'bg-white/10'
    btnContent = <><span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white/20 border-t-accent-light" />{total > 0 ? `${finishedCount} / ${total} nodes...` : 'Running...'}</>
  } else if (completed && !hasError) {
    btnBg = 'bg-emerald-500'
    btnContent = <><CheckCircle size={13} />Done!</>
  } else if (completed && hasError) {
    btnBg = 'bg-red-500'
    btnContent = <><AlertTriangle size={13} />{errorCount} error{errorCount > 1 ? 's' : ''}</>
  }

  return (
    <div className="void-glass relative z-30 flex h-14 shrink-0 items-center gap-1.5 rounded-b-2xl px-3">
      <button
        type="button"
        onClick={onBack}
        title="Back to pipelines"
        aria-label="Back to pipelines"
        className="void-focus flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium text-white/60 hover:bg-white/5"
      >
        <ArrowLeft size={14} />
        <span className="hidden sm:inline">Pipelines</span>
      </button>

      <div className="mx-1 h-5 w-px bg-white/10" />

      {editing ? (
        <input
          autoFocus
          className="void-focus w-48 bg-transparent text-sm text-white outline-none"
          style={{ borderBottom: '1.5px solid #8B5CF6' }}
          value={pipelineName}
          onChange={e => setPipelineName(e.target.value)}
          onBlur={() => setEditing(false)}
          onKeyDown={e => e.key === 'Enter' && setEditing(false)}
        />
      ) : (
        <button onClick={() => setEditing(true)} className="void-focus rounded text-sm text-white/80 transition-opacity hover:opacity-80">
          {pipelineName}
        </button>
      )}
      <span
        title={dirty ? 'Unsaved changes' : 'Saved'}
        aria-label={dirty ? 'Unsaved changes' : 'Saved'}
        className={`h-1.5 w-1.5 shrink-0 rounded-full ${dirty ? 'bg-amber-400' : 'bg-emerald-400'}`}
      />

      <div className="mx-1 h-5 w-px bg-white/10" />

      <div className="flex items-center gap-0.5">
        <IconBtn onClick={undo} disabled={!canUndo} title={`Undo (${history.length})`}><Undo2 size={14} /></IconBtn>
        <IconBtn onClick={redo} disabled={!canRedo} title={`Redo (${future.length})`}><Redo2 size={14} /></IconBtn>
        <IconBtn onClick={onFitView} title="Fit view"><Maximize size={14} /></IconBtn>
      </div>

      <div className="ml-auto flex items-center gap-1.5">
        {statusText && <span className="hidden text-xs text-white/40 sm:inline">{statusText}</span>}

        <button onClick={handleValidate} title="Validate pipeline" className="void-focus flex items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs font-medium text-white/70 transition-all hover:bg-white/5">
          <ShieldCheck size={13} />
          <span className="hidden md:inline">Validate</span>
        </button>

        {currentPipelineKey && (
          <button onClick={onOpenSchedule} title="Schedule this pipeline" className="void-focus flex items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs font-medium text-white/70 transition-all hover:bg-white/5">
            <CalendarClock size={13} />
            <span className="hidden md:inline">Schedule</span>
          </button>
        )}

        <button onClick={handlePrimarySave} title={currentPipelineKey && !isAdmin ? 'Save as a new pipeline' : 'Save editable pipeline'} className="void-focus flex items-center gap-1.5 rounded-lg border border-white/10 px-2.5 py-1.5 text-xs font-medium text-white/70 transition-all hover:bg-white/5">
          <Save size={13} />
          <span className="hidden md:inline">{currentPipelineKey && !isAdmin ? 'Save As New' : 'Save'}</span>
        </button>

        <input ref={importInputRef} type="file" accept="application/json,.json" onChange={handleImportJson} style={{ display: 'none' }} />

        <div className="relative" ref={moreRef}>
          <IconBtn onClick={() => setMoreOpen(v => !v)} title="More actions"><MoreHorizontal size={15} /></IconBtn>
          {moreOpen && (
            <div className="void-glass absolute right-0 top-10 z-50 w-56 overflow-hidden rounded-xl py-1 text-xs">
              {currentPipelineKey && isAdmin && (
                <MenuItem icon={Save} label="Save As…" onClick={() => { setMoreOpen(false); openSaveDialog() }} />
              )}
              <MenuItem icon={Upload} label="Import JSON" onClick={() => { importInputRef.current?.click(); setMoreOpen(false) }} />
              <MenuItem icon={Download} label="Export JSON" onClick={handleDownload} />
              <MenuItem icon={Copy} label="Copy entire pipeline" onClick={handleCopyFull} />
              <MenuItem icon={Copy} label="Select area to copy" onClick={handleSelectAreaCopy} />
              <MenuItem icon={ClipboardPaste} label="Paste copied pipeline" onClick={handlePaste} />
            </div>
          )}
        </div>

        <button onClick={onRun} disabled={running} className={`void-focus flex min-w-[132px] items-center justify-center gap-2 rounded-lg px-4 py-1.5 text-sm font-semibold text-white transition-all ${btnBg} ${running ? 'cursor-not-allowed' : ''}`}>
          {btnContent}
        </button>
      </div>

      {(running || completed) && (
        <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, height: 2, background: 'rgba(255,255,255,0.06)' }}>
          <div className={running && !hasError ? 'pipeline-glow' : ''} style={{ height: '100%', width: `${pct}%`, background: hasError ? '#f87171' : completed ? '#34d399' : '#8B5CF6', transition: 'width 0.5s ease, background 0.4s ease', borderRadius: '0 2px 2px 0' }} />
        </div>
      )}

      {saveOpen && (
        <div className="pointer-events-none absolute inset-x-0 top-14 z-50 flex justify-center">
          <div className="void-glass pointer-events-auto flex items-center gap-2 rounded-xl px-3 py-2 shadow-[0_16px_40px_rgba(0,0,0,0.5)]">
            <span className="text-xs font-semibold text-white/70">Pipeline name</span>
            <input autoFocus value={saveName} onChange={e => setSaveName(e.target.value)} onKeyDown={e => e.key === 'Enter' && savePipeline({ useDialogName: true, updateCurrent: Boolean(currentPipelineKey && isAdmin) })} className="void-focus min-w-[220px] rounded-md border border-white/10 bg-white/[0.04] px-2 py-1 text-sm text-white outline-none" placeholder="Untitled Pipeline" />
            <button onClick={() => savePipeline({ useDialogName: true, updateCurrent: Boolean(currentPipelineKey && isAdmin) })} className="void-focus rounded-md bg-accent px-3 py-1.5 text-xs font-semibold text-white hover:bg-accent-hover">Save</button>
            <button onClick={() => setSaveOpen(false)} aria-label="Cancel save" className="void-focus rounded-md p-1.5 text-white/40 hover:bg-white/5 hover:text-white"><X size={14} /></button>
          </div>
        </div>
      )}
    </div>
  )
}

function IconBtn({ onClick, disabled, title, children }) {
  return (
    <button onClick={onClick} disabled={disabled} title={title} aria-label={title} className="void-focus rounded-lg p-1.5 text-white/60 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-30">
      {children}
    </button>
  )
}

function MenuItem({ icon: Icon, label, onClick }) {
  return (
    <button type="button" onClick={onClick} className="void-focus flex w-full items-center gap-2 px-3 py-2 text-left text-white/75 hover:bg-white/5">
      <Icon size={13} aria-hidden="true" />
      {label}
    </button>
  )
}
