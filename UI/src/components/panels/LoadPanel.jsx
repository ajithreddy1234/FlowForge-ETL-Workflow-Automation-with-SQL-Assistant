import { useState } from 'react'
import { apiClient } from '../../services/apiClient'
import { AlertTriangle, Plus, Trash2 } from 'lucide-react'
import { useStore } from '../../store'
import { SectionHeader, Field, TextInput, InfoBox, StatusBox } from './CredentialPanel'

export default function LoadPanel({ node }) {
  const updateNodeData = useStore(s => s.updateNodeData)
  const d = node.data
  const [downloadError, setDownloadError] = useState('')
  const [downloading, setDownloading] = useState(false)
  const tabNames = d.tab_names?.length ? d.tab_names : [d.tab_name || '']

  const updateTab = (index, value) => {
    const next = [...tabNames]
    next[index] = value
    updateNodeData(node.id, { tab_names: next, tab_name: next[0] || '' })
  }

  const addTab = () => {
    updateNodeData(node.id, { tab_names: [...tabNames, ''] })
  }

  const removeTab = (index) => {
    const next = tabNames.filter((_, i) => i !== index)
    const safeNext = next.length ? next : ['']
    updateNodeData(node.id, { tab_names: safeNext, tab_name: safeNext[0] || '' })
  }

  const filledTabs = tabNames.map(t => t.trim()).filter(Boolean)
  const missingSheet = !(d.google_sheet_url || '').trim()
  const missingTabs = filledTabs.length === 0

  if (import.meta.env.VITE_PUBLIC_DEMO === 'true') return <div className="p-4 space-y-4"><SectionHeader title="CSV destination" subtitle="Server-written output" /><Field label="Output label"><TextInput value={d.label || ''} onChange={label => updateNodeData(node.id, { label, google_sheet_url: 'sandbox://csv', tab_names: ['output'] })} /></Field><InfoBox>Run the pipeline to write the result on the server. Download retrieves the latest completed output from this shared sandbox.</InfoBox><button disabled={downloading} className="void-focus rounded-lg bg-accent px-4 py-2 text-sm disabled:opacity-50" onClick={async () => { setDownloadError(''); setDownloading(true); try { const response = await apiClient.get('/api/demo/output', { responseType: 'blob' }); const url = URL.createObjectURL(response.data); const link = document.createElement('a'); link.href = url; link.download = 'flowforge-output.csv'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000) } catch { setDownloadError('Run a pipeline successfully before downloading its output.') } finally { setDownloading(false) } }}>{downloading ? 'Downloading…' : 'Download latest CSV'}</button>{downloadError && <p role="alert" className="text-xs text-red-300">{downloadError}</p>}</div>

  return (
    <div className="p-4 space-y-4">
      <SectionHeader title="Sink" subtitle="Write the table to one or more Google Sheet tabs" />

      <Field label="Node Label">
        <TextInput
          value={d.label || ''}
          onChange={v => updateNodeData(node.id, { label: v })}
          placeholder="Write to Sheet"
        />
      </Field>

      <Field
        label="Google Sheet URL or ID"
        hint={import.meta.env.VITE_LOCAL_CSV === 'true'
          ? 'Paste a Google Sheet URL, or use csv://name to write local CSV files (local mode).'
          : 'Paste the full URL from your browser address bar.'}
        required
      >
        <TextInput
          mono
          value={d.google_sheet_url || ''}
          onChange={v => updateNodeData(node.id, { google_sheet_url: v })}
          placeholder="https://docs.google.com/spreadsheets/d/..."
          style={{ border: `1px solid ${missingSheet ? 'rgba(239,68,68,0.4)' : 'rgba(255,255,255,0.12)'}` }}
        />
        {missingSheet && (
          <StatusBox tone="error" icon={AlertTriangle}>
            Google Sheet URL or ID is required before running this Sink node.
          </StatusBox>
        )}
      </Field>

      <Field label="Write Mode" hint="Overwrite removes stale rows; append adds new rows after existing data.">
        <select
          className="void-focus w-full rounded-lg px-3 py-2 text-sm outline-none"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.12)', color: '#fff' }}
          value={d.write_mode || 'overwrite'}
          onChange={event => updateNodeData(node.id, { write_mode: event.target.value })}
        >
          <option value="overwrite">Overwrite tab</option>
          <option value="append">Append rows</option>
        </select>
      </Field>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium text-white/60">
            Tab Names <span style={{ color: '#f87171' }}>*</span>
          </span>
          <button
            type="button"
            onClick={addTab}
            className="void-focus flex items-center gap-1 rounded-md px-2 py-1 text-xs"
            style={{ background: 'rgba(16,185,129,0.1)', color: '#34d399', border: '1px solid rgba(16,185,129,0.25)' }}
          >
            <Plus size={12} /> Add
          </button>
        </div>

        {tabNames.map((tab, index) => (
          <div key={index} className="flex items-center gap-2">
            <TextInput
              value={tab}
              onChange={v => updateTab(index, v)}
              placeholder={index === 0 ? 'Daily Sales' : `Tab ${index + 1}`}
              style={{ border: `1px solid ${missingTabs ? 'rgba(239,68,68,0.4)' : 'rgba(255,255,255,0.12)'}` }}
            />
            <button
              type="button"
              onClick={() => removeTab(index)}
              title="Remove tab"
              aria-label={`Remove tab ${index + 1}`}
              className="void-focus shrink-0 rounded-md p-2"
              style={{ background: 'rgba(239,68,68,0.1)', color: '#f87171', border: '1px solid rgba(239,68,68,0.25)' }}
            >
              <Trash2 size={13} />
            </button>
          </div>
        ))}
        {missingTabs && (
          <StatusBox tone="error" icon={AlertTriangle}>
            Add at least one tab name so the pipeline knows where to write data.
          </StatusBox>
        )}
        <p className="text-xs text-white/35">
          Data is written from cell A1 in each selected tab.
        </p>
      </div>

      {d.google_sheet_url && filledTabs.length > 0 && (
        <div className="space-y-1 rounded-lg p-3" style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.25)' }}>
          <p className="text-xs font-semibold text-emerald-400">Output</p>
          <p className="truncate text-xs text-emerald-300">{d.google_sheet_url}</p>
          <p className="text-xs text-emerald-300">
            Tabs: <strong>{filledTabs.join(', ')}</strong>
          </p>
        </div>
      )}

      <InfoBox>
        Make sure the Google Sheet is shared with the service account as Editor
        before running the pipeline.
      </InfoBox>
    </div>
  )
}
